"""Регрессионные тесты детектора мата.

Запуск без сторонних зависимостей:
    python tests/test_profanity.py

Проверяет две вещи: настоящий мат распознаётся, невинные слова — нет.
Набор украинских форм собран из разбора реальных видео, где мат писался
через и/і/ї/є.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.profanity import ProfanityDetector, normalize  # noqa: E402

MUST_FLAG = [
    # русский
    "хуй", "хуя", "хуёво", "нахуй", "похуй", "хуйня", "пизда", "пиздец",
    "блядь", "бля", "блять", "ебать", "ебал", "заебись", "наебал", "выеб",
    "проеб", "уебан", "ёбаный", "долбоеб", "пидор", "підор",
    # украинский (и/і/ї/є)
    "похуєм", "ніхуя", "хує", "хуї", "піздець", "піздять", "пізда",
    "виїбу", "виїбати", "заєбись", "наїбав", "доїбався", "зйобав", "підйоб",
    "розйобати", "їбати", "їбало", "йобаний", "єбать", "єебать", "пиздят",
    "похуй", "хуйта",
]

MUST_NOT_FLAG = [
    "себе", "себя", "тебе", "веб", "вебка", "вебінар", "вебинар",
    "хліб", "хліба", "хлеб", "область", "команда", "требе", "небо", "зебра",
    "вибори", "виборах", "забути", "забув", "працює", "робити", "вивчати",
    "розповісти", "донатили", "стрімив", "існують", "зрозумів", "погнали",
    "учеба", "хлебушек", "требник", "серебро", "потреблять", "мандарин",
    "індустрії", "погана", "приємно", "виїзд", "поїзд", "заєць",
    # «бля» как подстрока — не мат
    "оскорбляти", "оскорбляют", "корабля", "кораблях", "рубля", "рублях",
    # Обломки украинского прохода на русском «наиболее» — встречены на реальной
    # записи, где мата не было вовсе.
    "іболі", "найболі",
]


def _detector():
    return ProfanityDetector(["strong", "rude"])


def test_real_profanity_is_flagged():
    det = _detector()
    missed = [w for w in MUST_FLAG if not det._check(normalize(w))]
    assert not missed, f"не распознан мат: {missed}"


def test_innocent_words_are_not_flagged():
    det = _detector()
    false_hits = [(w, det._check(normalize(w)))
                  for w in MUST_NOT_FLAG if det._check(normalize(w))]
    assert not false_hits, f"ложные срабатывания: {false_hits}"


def test_normalisation_handles_obfuscation():
    # Латинские гомоглифы и растянутые буквы должны сводиться к тому же корню.
    det = _detector()
    assert det._check(normalize("хуууй")), "растянутое написание не распознано"
    assert det._check(normalize("xyй")), "латинские гомоглифы не распознаны"


if __name__ == "__main__":
    detector = _detector()
    not_found = [w for w in MUST_FLAG if not detector._check(normalize(w))]
    false_positives = [(w, detector._check(normalize(w)))
                       for w in MUST_NOT_FLAG if detector._check(normalize(w))]
    print(f"Распознано мата      : {len(MUST_FLAG) - len(not_found)}/{len(MUST_FLAG)}")
    if not_found:
        print("  НЕ распознано:", not_found)
    print(f"Ложных срабатываний  : {len(false_positives)}/{len(MUST_NOT_FLAG)}")
    if false_positives:
        print("  Ложно помечено:", false_positives)

    try:
        test_normalisation_handles_obfuscation()
        print("Обфускация           : распознаётся")
        obfuscation_ok = True
    except AssertionError as exc:
        print("Обфускация           :", exc)
        obfuscation_ok = False

    if not_found or false_positives or not obfuscation_ok:
        sys.exit(1)
    print("OK: все проверки пройдены.")
