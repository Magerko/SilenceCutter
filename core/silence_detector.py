import re
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple, List

from utils.ffmpeg_locator import ffmpeg_path, subprocess_kwargs


@dataclass
class SilenceInfo:
    start_silence_end: Optional[float]
    end_silence_start: Optional[float]
    total_duration: float
    all_silences: List[Tuple[float, float]]


# Ниже этой длины тишина по краям не считается: обрезка ради сотых долей
# секунды означала бы перекодирование впустую.
EDGE_MIN_DURATION = 0.2

# Мёртвый воздух в начале и конце записи почти всегда разорван щелчком мыши,
# вдохом или стуком клавиши. Для ffmpeg это звук, и тишина распадается на два
# блока: первый оказывается короче порога, и не срезается ничего. Островки
# звука короче этой длительности при поиске краёв пропускаем.
EDGE_MERGE_GAP = 0.35


def detect_silence(
    file_path: str,
    noise_threshold: str = "-30dB",
    min_duration: float = 0.5,
    progress_callback=None
) -> Tuple[Optional[SilenceInfo], Optional[str]]:
    # Ищем тишину коротким окном, а порог пользователя применяем потом, к
    # паузам внутри записи. Если передать его прямо сюда, полсекунды тишины в
    # конце при пороге в секунду не будут найдены вовсе — а хвост обрезать надо
    # всегда, в отличие от паузы посреди речи, которая может быть осмысленной.
    # Ищем мелким шагом, независимо от порога человека: у краёв тишина часто
    # разорвана щелчком на куски по одной-две десятых секунды, и при крупном
    # окне ffmpeg о них просто не сообщает. Отбор по длительности делаем сами,
    # уже после склейки.
    scan_window = 0.05
    cmd = [
        ffmpeg_path(),
        '-i', file_path,
        '-af', f'silencedetect=noise={noise_threshold}:d={scan_window}',
        '-f', 'null',
        '-'
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **subprocess_kwargs()
        )

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            return None, f"FFMPEG error: {stderr[-300:]}"

        silence_starts = []
        silence_ends = []

        start_pattern = r'silence_start:\s*([\d.]+)'
        end_pattern = r'silence_end:\s*([\d.]+)'

        for match in re.finditer(start_pattern, stderr):
            silence_starts.append(float(match.group(1)))

        for match in re.finditer(end_pattern, stderr):
            silence_ends.append(float(match.group(1)))

        duration_pattern = r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)'
        duration_match = re.search(duration_pattern, stderr)

        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2))
            seconds = float(duration_match.group(3))
            total_duration = hours * 3600 + minutes * 60 + seconds
        else:
            time_pattern = r'time=(\d+):(\d+):(\d+\.?\d*)'
            time_matches = list(re.finditer(time_pattern, stderr))
            if time_matches:
                last_match = time_matches[-1]
                hours = int(last_match.group(1))
                minutes = int(last_match.group(2))
                seconds = float(last_match.group(3))
                total_duration = hours * 3600 + minutes * 60 + seconds
            else:
                return None, "Could not determine video duration"

        all_silences = []
        for i, start in enumerate(silence_starts):
            if i < len(silence_ends):
                all_silences.append((start, silence_ends[i]))
            else:
                all_silences.append((start, total_duration))

        # Склеиваем соседние блоки тишины, разделённые коротким звуком.
        merged = []
        for begin, finish in all_silences:
            if merged and begin - merged[-1][1] <= EDGE_MERGE_GAP:
                merged[-1] = (merged[-1][0], finish)
            else:
                merged.append((begin, finish))

        start_silence_end = None
        if merged and merged[0][0] < 0.15:
            start_silence_end = merged[0][1]

        end_silence_start = None
        if merged:
            last_begin, last_finish = merged[-1]
            # Тишина считается концевой, если она упирается в конец записи.
            if total_duration - last_finish < 0.35:
                end_silence_start = last_begin

        # Внутренние паузы отдаём уже отфильтрованными по порогу человека:
        # иначе короткое окно поиска резало бы речь на куски.
        internal = [(a, b) for a, b in all_silences if b - a >= min_duration]

        # Слишком короткий хвост не трогаем: разница в сотые доли секунды
        # означала бы перекодирование ради ничего.
        if start_silence_end is not None and start_silence_end < EDGE_MIN_DURATION:
            start_silence_end = None
        if (end_silence_start is not None
                and total_duration - end_silence_start < EDGE_MIN_DURATION):
            end_silence_start = None

        return SilenceInfo(
            start_silence_end=start_silence_end,
            end_silence_start=end_silence_start,
            total_duration=total_duration,
            all_silences=internal
        ), None

    except FileNotFoundError:
        return None, "FFMPEG not found. Please install FFMPEG and add it to PATH."
    except Exception as e:
        return None, str(e)


def get_trim_times(silence_info: SilenceInfo) -> Tuple[float, float]:
    start_time = silence_info.start_silence_end if silence_info.start_silence_end else 0.0
    end_time = silence_info.end_silence_start if silence_info.end_silence_start else silence_info.total_duration
    return start_time, end_time


def get_segments_without_silence(
    silence_info: SilenceInfo,
    min_internal_silence: float = 2.0,
    trim_edges: bool = True
) -> List[Tuple[float, float]]:
    if trim_edges:
        start_time, end_time = get_trim_times(silence_info)
    else:
        start_time = 0.0
        end_time = silence_info.total_duration

    internal_silences = []
    for s_start, s_end in silence_info.all_silences:
        if s_start <= start_time + 0.1:
            continue
        if s_end >= end_time - 0.1:
            continue
        duration = s_end - s_start
        if duration >= min_internal_silence:
            internal_silences.append((s_start, s_end))

    if not internal_silences:
        return [(start_time, end_time)]

    segments = []
    current_start = start_time

    for s_start, s_end in internal_silences:
        if s_start > current_start:
            segments.append((current_start, s_start))
        current_start = s_end

    if current_start < end_time:
        segments.append((current_start, end_time))

    return segments
