"""Распознавание речи — родительская сторона.

Сама работа идёт в отдельном процессе (core/transcribe_cli.py): Qt6 и
ctranslate2 конфликтуют при загрузке нативных библиотек, и в одном процессе с
интерфейсом распознавание падает с нарушением доступа.

Здесь только запуск дочернего процесса, разбор его прогресса и результата.
"""
import json
import logging
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from utils.ffmpeg_locator import subprocess_kwargs
from utils.paths import models_dir

logger = logging.getLogger(__name__)

# Приблизительный вес моделей на диске — для показа прогресса скачивания.
MODEL_SIZES_MB = {
    'tiny': 75,
    'base': 145,
    'small': 484,
    'medium': 1530,
    'large-v3': 3100,
}
DEFAULT_MODEL = 'large-v3'

# Whisper на одной записи слышит разные короткие вставки в зависимости от
# заявленного языка, поэтому два прохода с объединением ловят заметно больше.
LANGUAGE_PAIR = ('ru', 'uk')

WORKER_FLAG = '--transcribe-worker'


@dataclass
class Word:
    text: str
    start: float
    end: float


def model_dir_for(model_size: str) -> str:
    return os.path.join(models_dir(), model_size)


def is_model_ready(model_size: str) -> bool:
    folder = model_dir_for(model_size)
    if not os.path.isdir(folder):
        return False
    names = set(os.listdir(folder))
    return 'model.bin' in names and 'tokenizer.json' in names


def _worker_command(audio_path: str, model_size: str, language: Optional[str]) -> list:
    """Как запустить дочерний процесс — из сборки или из исходников."""
    arguments = [
        WORKER_FLAG,
        '--audio', audio_path,
        '--models-root', models_dir(),
        '--model', model_size,
        '--language', language or '',
        '--expected-mb', str(MODEL_SIZES_MB.get(model_size, 0)),
    ]
    if getattr(sys, 'frozen', False):
        # В собранном виде отдельного интерпретатора нет: перезапускаем сам
        # исполняемый файл, он распознаёт флаг до создания интерфейса.
        return [sys.executable] + arguments
    entry = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')
    return [sys.executable, entry] + arguments


def transcribe(
        audio_path: str,
        model_size: str = DEFAULT_MODEL,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        download_started: Optional[Callable[[str, float], None]] = None,
        download_progress: Optional[Callable[[int, float, float], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
) -> Tuple[List[Word], float]:
    """Распознать речь. Возвращает (слова с таймкодами, длительность)."""
    command = _worker_command(audio_path, model_size, language)
    kwargs = dict(subprocess_kwargs())
    kwargs.pop('stdin', None)

    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL, **kwargs)

    # stdout вычитывается отдельным потоком. Иначе дочерний процесс упирается
    # в переполненный буфер канала, пока родитель ждёт stderr, и оба замирают:
    # результат распознавания легко превышает размер буфера.
    collected: List[str] = []

    def drain_stdout():
        collected.append(process.stdout.read())

    reader = threading.Thread(target=drain_stdout, daemon=True)
    reader.start()

    device = 'cpu'
    try:
        for line in process.stderr:
            if cancel_check and cancel_check():
                process.kill()
                process.wait()
                raise InterruptedError('Распознавание отменено')

            parts = line.strip().split()
            if not parts:
                continue
            kind = parts[0]
            try:
                if kind == 'PROGRESS' and progress_callback:
                    progress_callback(int(parts[1]))
                elif kind == 'DOWNLOAD_START' and download_started:
                    download_started(parts[1], float(parts[2]))
                elif kind == 'DOWNLOAD' and download_progress:
                    download_progress(int(parts[1]), float(parts[2]), float(parts[3]))
                elif kind == 'DEVICE':
                    device = parts[1]
            except (IndexError, ValueError):
                continue

        process.wait()
        reader.join(timeout=30)
        stdout = collected[0] if collected else ''
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    if process.returncode != 0:
        raise RuntimeError(
            f'Распознавание завершилось с ошибкой (код {process.returncode})')

    try:
        payload = json.loads(stdout or '{}')
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'Не удалось прочитать результат распознавания: {exc}')

    logger.info(f'Transcribed on {device}: {len(payload.get("words", []))} words')
    words = [Word(w['text'], w['start'], w['end']) for w in payload.get('words', [])]
    return words, payload.get('duration', 0.0)
