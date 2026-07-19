"""Профиль громкости записи — данные для дорожки.

Считается по сырому PCM, а не по выводу silencedetect: дорожка должна
показывать саму запись, а не то, что уже решил детектор. Тогда, двигая порог,
человек видит последствия до запуска обработки.
"""
import array
import math
import os
import subprocess
import tempfile
import wave
from typing import Callable, List, Optional, Tuple

from utils.ffmpeg_locator import ffmpeg_path, subprocess_kwargs

# Окно замера. 50 мс — компромисс: короткие паузы между словами уже видно,
# а точек не столько, чтобы отрисовка стала заметной.
WINDOW_SECONDS = 0.05
SILENCE_FLOOR_DB = -120.0


def compute_envelope(
        video_path: str,
        window: float = WINDOW_SECONDS,
        cancel_check: Optional[Callable[[], bool]] = None,
) -> Tuple[List[float], float]:
    """Вернуть (уровни в дБ по окнам, длительность в секундах)."""
    with tempfile.TemporaryDirectory(prefix='silencecutter_env_') as temp_dir:
        wav_path = os.path.join(temp_dir, 'audio.wav')
        # 8 кГц моно достаточно: нужна огибающая, а не звук.
        subprocess.run(
            [ffmpeg_path(), '-y', '-loglevel', 'error', '-i', video_path,
             '-vn', '-ac', '1', '-ar', '8000', '-c:a', 'pcm_s16le', wav_path],
            capture_output=True, check=True, **subprocess_kwargs())

        with wave.open(wav_path, 'rb') as handle:
            rate = handle.getframerate()
            raw = handle.readframes(handle.getnframes())

    samples = array.array('h')
    samples.frombytes(raw)
    if not samples:
        return [], 0.0

    per_window = max(1, int(rate * window))
    levels: List[float] = []
    for start in range(0, len(samples), per_window):
        if cancel_check and cancel_check():
            raise InterruptedError('Анализ громкости отменён')
        chunk = samples[start:start + per_window]
        if not chunk:
            continue
        total = 0
        for value in chunk:
            total += value * value
        rms = math.sqrt(total / len(chunk))
        levels.append(20 * math.log10(rms / 32768.0) if rms > 0 else SILENCE_FLOOR_DB)

    return levels, len(samples) / rate


def segments_below(levels: List[float], threshold_db: float, window: float,
                   min_duration: float) -> List[Tuple[float, float]]:
    """Отрезки тише порога и длиннее минимальной длительности.

    Приблизительная оценка для показа: настоящую резку делает ffmpeg. Нужна,
    чтобы человек видел последствия порога до запуска.
    """
    spans: List[Tuple[float, float]] = []
    start_index = None
    for index, level in enumerate(levels):
        if level <= threshold_db:
            if start_index is None:
                start_index = index
        elif start_index is not None:
            spans.append((start_index, index))
            start_index = None
    if start_index is not None:
        spans.append((start_index, len(levels)))

    result = []
    for first, last in spans:
        start, end = first * window, last * window
        if end - start >= min_duration:
            result.append((start, end))
    return result
