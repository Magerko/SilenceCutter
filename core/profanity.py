"""Детектор нецензурной лексики (русский + украинский / суржик).

Перенесён из проекта Antimat того же автора. Whisper отдаёт слова с
таймкодами; каждое слово нормализуется (нижний регистр, схлопывание повторов
«бляяять» -> «блять», гомоглифы) и проверяется по корням-регуляркам.

Чтобы не ловились «хлеб/учёба/себе», корни «еб»-семейства якорятся к началу
слова и требуют приставку, а «бля» якорится к началу — иначе совпадает
внутри «корабля/рубля/оскорбляти». Плюс белый список частых слов.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional

from utils.paths import user_data_dir

CUSTOM_WORDS_FILE = 'custom_words.txt'
WHITELIST_FILE = 'whitelist.txt'


def custom_words_path() -> str:
    return os.path.join(user_data_dir(), CUSTOM_WORDS_FILE)


def whitelist_path() -> str:
    return os.path.join(user_data_dir(), WHITELIST_FILE)


# --- нормализация -----------------------------------------------------------

_HOMOGLYPHS = str.maketrans({
    "a": "а", "e": "е", "o": "о", "c": "с", "x": "х", "p": "р",
    "y": "у", "k": "к", "m": "м", "h": "н", "b": "в", "t": "т", "n": "п",
})
_REPEAT_RE = re.compile(r"(.)\1+")
_CLEAN_RE = re.compile(r"[^а-яёіїєґ]+")


def normalize(word: str) -> str:
    """Привести слово к виду, удобному для матчинга по корням."""
    w = word.lower().replace("ё", "е").translate(_HOMOGLYPHS)
    w = _CLEAN_RE.sub("", w)          # оставляем только кириллицу
    w = _REPEAT_RE.sub(r"\1", w)      # «хуууй» -> «хуй», «сссука» -> «сука»
    return w


# --- словарь корней ---------------------------------------------------------
# (regex по нормализованному слову, человекочитаемая метка, категория)
# strong — собственно мат; rude — грубое, по умолчанию выключено.

_ROOTS: list[tuple[str, str, str]] = [
    # После «ху» идёт гласная, включая украинские є/і/ї. «Художник/хустка»
    # не совпадают — там согласная; «хліб/хлеб» отсекает белый список.
    (r"ху[йяеюиєіїё]", "хуй", "strong"),
    (r"пизд|пезд|пізд", "пизда", "strong"),
    # Якорь к началу обязателен: иначе ловит «корабля/рубля/оскорбляти».
    (r"^бля", "блядь", "strong"),
    # Приставка обязательна, «б» сразу за гласной — это и отсекает
    # «себе/себя, вебінар, зебра, небо, приємно, виїзд, поїзд».
    (r"^(?:вы|ви|за|на|по|про|до|от|од|уві|у|об|съ|въ|зъ|зі|роз|під|подъ|под|разъ|раз|пере|недо|при|изъ)[ъь]?[еэєїіё]б", "ебать", "strong"),
    (r"^[еэєїі]б|єеб|ееб|оеб|оёб|оїб|йоб|ебуч|ебош|ебыр|ебан|еблан|мудоеб", "ебать", "strong"),
    (r"\bманд[аеоу]|мандавош|мандобл", "манда", "strong"),
    (r"муд[аоеи]к|мудил|мудоз|муде", "мудак", "strong"),
    (r"залуп", "залупа", "strong"),
    (r"гондон|гандон", "гондон", "strong"),
    (r"пид[ао]р|пидр|підар|підор|педрил", "пидор", "strong"),
    (r"\bйоб|йобан|йобн|зйоб|прийоб|выйоб|підйоб|розйоб|уйоб", "йоб", "strong"),
    (r"\bсук[аиоую]\b|сучар|сученьк|сучоныш|сучье", "сука", "rude"),
    (r"гавн|говн|гімн|гивн", "говно", "rude"),
    (r"дерьм", "дерьмо", "rude"),
    (r"\bсрак|насра|обосра|посра|усра|обсыр", "срать", "rude"),
    (r"\bдрист|обдрист", "дристать", "rude"),
    (r"шлюх", "шлюха", "rude"),
    (r"\bкурв", "курва", "rude"),
    (r"гнид", "гнида", "rude"),
    (r"\bсцук", "сука", "rude"),
    (r"\bлайно", "лайно", "rude"),
]

# Слова, которые НЕ являются матом, но попадают под корни выше.
_WHITELIST_BUILTIN = {
    "хлеб", "хлеба", "хлебать", "хлебушек", "хлебом",
    "учеба", "учебе", "учебу", "учебой", "учебник", "учебный",
    "погреб", "погреба", "ущерб", "ущерба", "ущербный",
    "гребень", "грести", "гребет", "гребля", "требник", "потребность",
    "употреблять", "потреблять", "теребить", "колеблется", "серебро",
    "команда", "командир", "мандарин", "мандат", "мандала", "мандолина",
    "сукно", "сукна", "сучок", "сучка", "сухой",
    "область", "областях", "благо", "обляпать",
    # Обломки, которые Whisper выдаёт на украинском проходе, разбирая русское
    # «наиболее»: «є найболі удачним» вместо «является наиболее удачным».
    # Под корень «еб»-семейства попадает «і» + «б», хотя мата не звучало.
    "іболі", "найболі",
}


def _compile(roots: Iterable[tuple[str, str, str]]):
    return [(re.compile(rx), label, cat) for rx, label, cat in roots]


@dataclass
class Match:
    index: int          # порядковый номер слова в транскрипте
    word: str           # как распознал Whisper
    start: float
    end: float
    label: str          # к какому корню отнесли
    category: str       # strong / rude / custom
    context: str        # соседние слова, чтобы решение было осознанным


class ProfanityDetector:
    def __init__(self, categories: Optional[list] = None):
        self.categories = set(categories or ["strong"])
        self.patterns = _compile(_ROOTS)
        self.whitelist = set(_WHITELIST_BUILTIN)
        self.custom: list = []
        self._load_user_files()

    def _load_user_files(self) -> None:
        whitelist = whitelist_path()
        if os.path.exists(whitelist):
            with open(whitelist, encoding="utf-8") as f:
                for line in f:
                    w = normalize(line.strip())
                    if w:
                        self.whitelist.add(w)

        custom = custom_words_path()
        if os.path.exists(custom):
            with open(custom, encoding="utf-8") as f:
                for line in f:
                    raw = line.strip()
                    norm = normalize(raw)
                    if norm:
                        self.custom.append((re.compile(re.escape(norm)), raw))

    def _check(self, norm: str):
        """Вернуть (label, category), если слово — мат подходящей категории."""
        if not norm or norm in self.whitelist:
            return None
        for rx, label in self.custom:
            if rx.search(norm):
                return label, "custom"
        for rx, label, cat in self.patterns:
            if cat in self.categories and rx.search(norm):
                return label, cat
        return None

    def detect(self, words: list) -> list:
        """words — объекты с .text/.start/.end (см. core.transcribe.Word)."""
        results = []
        for i, w in enumerate(words):
            hit = self._check(normalize(w.text))
            if hit:
                label, cat = hit
                results.append(Match(i, w.text.strip(), w.start, w.end,
                                     label, cat, self._context(words, i)))
        return results

    @staticmethod
    def _context(words: list, i: int, radius: int = 4) -> str:
        lo = max(0, i - radius)
        hi = min(len(words), i + radius + 1)
        parts = []
        for j in range(lo, hi):
            text = words[j].text.strip()
            parts.append(f"[{text}]" if j == i else text)
        return " ".join(parts)


def merge_matches(*match_lists, gap: float = 0.05) -> list:
    """Объединить совпадения нескольких проходов (например RU и UA), убрав дубли.

    Разные проходы Whisper слышат разные короткие вставки, поэтому объединение
    повышает полноту; пересечение по времени означает одно и то же слово.
    """
    everything = sorted((m for lst in match_lists for m in lst),
                        key=lambda m: (m.start, m.end))
    out = []
    for m in everything:
        if out and m.start < out[-1].end + gap:
            continue
        out.append(m)
    return out


def _append_line(path: str, word: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(word.strip() + "\n")


def add_custom_word(word: str) -> None:
    _append_line(custom_words_path(), word)


def add_whitelist_word(word: str) -> None:
    _append_line(whitelist_path(), word)
