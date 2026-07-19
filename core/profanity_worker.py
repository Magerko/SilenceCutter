"""Конвейер удаления мата: звук -> распознавание -> детект -> заглушение.

Видео не перекодируется: меняется только звуковая дорожка, поэтому обработка
быстрая и не портит картинку.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from core import transcribe
from core.profanity import ProfanityDetector, merge_matches
from utils.ffmpeg_locator import ffmpeg_path, subprocess_kwargs
from utils.file_utils import get_output_filename

# Отступы вокруг слова. Намеренно узкие: с широкими глохли соседние слова, и
# в записи появлялись провалы. Глушим ровно найденное слово.
PAD_BEFORE = 0.03
PAD_AFTER = 0.03


def merge_intervals(intervals: List[Tuple[float, float]], pad_before: float,
                    pad_after: float, total: float) -> List[Tuple[float, float]]:
    """Расширить интервалы отступами и склеить пересекающиеся."""
    padded = []
    for start, end in sorted(intervals):
        padded.append((max(0.0, start - pad_before),
                       min(total, end + pad_after) if total else end + pad_after))

    merged: List[Tuple[float, float]] = []
    for start, end in padded:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def build_mute_filter(intervals: List[Tuple[float, float]]) -> str:
    condition = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in intervals)
    return f"[0:a]volume=enable='{condition}':volume=0[a]"


class ProfanityWorker(QThread):
    progress = pyqtSignal(int, str)
    file_started = pyqtSignal(str)
    file_completed = pyqtSignal(str, bool, str)
    all_completed = pyqtSignal(int, int)
    log_message = pyqtSignal(str)
    # Сообщает, что именно заглушено: список (начало, конец, слово)
    report = pyqtSignal(str, list)
    model_progress = pyqtSignal(int, float, float)
    model_download_started = pyqtSignal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files: List[str] = []
        self.output_folder = ""
        self.model_size = transcribe.DEFAULT_MODEL
        self.categories = ["strong"]
        self.dual_language = True
        # Пустой список означает «всё видео».
        self.ranges: List[Tuple[float, float]] = []
        self._cancelled = False

    def set_files(self, files: List[str], output_folder: str):
        self.files = files
        self.output_folder = output_folder

    def set_options(self, model_size: str, categories: List[str],
                    dual_language: bool, ranges: Optional[List] = None):
        self.model_size = model_size
        self.categories = categories
        self.dual_language = dual_language
        self.ranges = list(ranges or [])

    def cancel(self):
        self._cancelled = True

    def _cancelled_check(self):
        return self._cancelled

    def run(self):
        self._cancelled = False
        successful = failed = 0

        for file_path in self.files:
            if self._cancelled:
                self.log_message.emit("Обработка отменена")
                break
            name = Path(file_path).name
            self.file_started.emit(name)
            try:
                ok, message = self._process(file_path, name)
            except InterruptedError:
                self.file_completed.emit(name, False, "Отменено")
                break
            except Exception as e:
                ok, message = False, str(e)
            successful += 1 if ok else 0
            failed += 0 if ok else 1
            self.file_completed.emit(name, ok, message)

        self.all_completed.emit(successful, failed)

    def _extract_audio(self, source: str, destination: str,
                       start: Optional[float] = None, end: Optional[float] = None):
        cmd = [ffmpeg_path(), '-y', '-loglevel', 'error']
        if start is not None:
            cmd += ['-ss', f'{start:.3f}']
        cmd += ['-i', source]
        if end is not None and start is not None:
            cmd += ['-t', f'{max(0.0, end - start):.3f}']
        cmd += ['-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', destination]
        subprocess.run(cmd, capture_output=True, check=True, **subprocess_kwargs())

    def _collect_matches(self, file_path: str, temp_dir: str) -> list:
        """Распознать и найти мат, с учётом выбранных участков."""
        detector = ProfanityDetector(self.categories)
        # Пустой список участков означает «весь файл»: один отрезок без сдвига.
        segments = self.ranges or [(None, None)]
        languages = list(transcribe.LANGUAGE_PAIR) if self.dual_language else [None]

        found = []
        for index, (start, end) in enumerate(segments):
            audio = os.path.join(temp_dir, f'chunk{index}.wav')
            self._extract_audio(file_path, audio, start, end)
            offset = start or 0.0

            for language in languages:
                if self._cancelled:
                    raise InterruptedError
                label = {'ru': 'русский', 'uk': 'украинский'}.get(language, '')
                self.progress.emit(
                    40, f'Распознавание речи{" (" + label + ")" if label else ""}...')
                words, _ = transcribe.transcribe(
                    audio, self.model_size, language=language,
                    download_started=lambda name, mb: self.model_download_started.emit(name, mb),
                    download_progress=lambda p, done, total: self.model_progress.emit(p, done, total),
                    cancel_check=self._cancelled_check)
                # Таймкоды отрезка отсчитываются от его начала.
                for word in words:
                    word.start += offset
                    word.end += offset
                found.append(detector.detect(words))

        return merge_matches(*found) if found else []

    def _process(self, file_path: str, name: str) -> Tuple[bool, str]:
        with tempfile.TemporaryDirectory(prefix='silencecutter_') as temp_dir:
            self.progress.emit(10, f'Извлечение звука из {name}...')
            matches = self._collect_matches(file_path, temp_dir)

            if not matches:
                self.report.emit(name, [])
                return True, 'Мат не найден, файл не изменён'

            duration = get_video_duration_safe(file_path)
            intervals = merge_intervals(
                [(m.start, m.end) for m in matches], PAD_BEFORE, PAD_AFTER, duration)

            self.progress.emit(70, f'Заглушение {len(matches)} слов...')
            output_path = get_output_filename(file_path, self.output_folder)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Фильтр пишем в файл: при большом числе интервалов строка
            # аргумента упирается в лимит длины командной строки Windows.
            script = os.path.join(temp_dir, 'filter.txt')
            with open(script, 'w', encoding='utf-8') as f:
                f.write(build_mute_filter(intervals))

            cmd = [
                ffmpeg_path(), '-y', '-loglevel', 'error',
                '-i', file_path,
                '-filter_complex_script', script,
                '-map', '0:v', '-map', '[a]',
                # Видео копируется как есть: заглушение трогает только звук.
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, **subprocess_kwargs())
            if result.returncode != 0:
                return False, f'FFMPEG error: {(result.stderr or "")[-300:]}'

            self.progress.emit(100, 'Готово')
            self.report.emit(name, [(m.start, m.end, m.word) for m in matches])
            return True, f'Заглушено слов: {len(matches)}'


def get_video_duration_safe(path: str) -> float:
    from utils.file_utils import get_video_duration
    return get_video_duration(path) or 0.0
