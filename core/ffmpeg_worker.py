import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from core.silence_detector import detect_silence, get_trim_times, get_segments_without_silence
from utils.ffmpeg_locator import (ffmpeg_path, subprocess_kwargs,
                                  video_encoder_args, encoder_ffmpeg_path)
from utils.file_utils import get_output_filename


class FFmpegWorker(QThread):
    progress_total = pyqtSignal(int, int)
    progress_file = pyqtSignal(int, str)
    file_started = pyqtSignal(str)
    file_completed = pyqtSignal(str, bool, str)
    all_completed = pyqtSignal(int, int)
    log_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files: List[str] = []
        self.output_folder: str = ""
        self.noise_threshold: str = "-50dB"
        self.min_silence_duration: float = 1.0
        self.remove_internal_silence: bool = False
        self.internal_silence_threshold: float = 2.0
        self.precise_cut: bool = True
        self._cancelled = False
        # Пути результатов, занятые в текущем запуске.
        self._used_outputs = set()

    def set_files(self, files: List[str], output_folder: str):
        self.files = files
        self.output_folder = output_folder
        self._used_outputs = set()

    def set_options(
        self,
        noise_db: float,
        min_duration: float,
        remove_internal: bool,
        internal_threshold: float,
        precise_cut: bool
    ):
        self.noise_threshold = f"{int(noise_db)}dB"
        self.min_silence_duration = min_duration
        self.remove_internal_silence = remove_internal
        self.internal_silence_threshold = internal_threshold
        self.precise_cut = precise_cut

    def cancel(self):
        self._cancelled = True

    def run(self):
        self._cancelled = False
        successful = 0
        failed = 0
        total = len(self.files)

        for i, file_path in enumerate(self.files):
            if self._cancelled:
                self.log_message.emit("Processing cancelled by user")
                break

            filename = Path(file_path).name
            self.file_started.emit(filename)
            self.progress_total.emit(i + 1, total)
            self.progress_file.emit(0, filename)

            success, message = self._process_file(file_path, i, total)

            if success:
                successful += 1
            else:
                failed += 1

            self.file_completed.emit(filename, success, message)

        self.all_completed.emit(successful, failed)

    def _process_file(self, file_path: str, index: int, total: int) -> Tuple[bool, str]:
        filename = Path(file_path).name

        self.log_message.emit(f"Analyzing silence in {filename}...")
        self.progress_file.emit(10, filename)

        silence_info, error = detect_silence(
            file_path,
            self.noise_threshold,
            self.min_silence_duration
        )

        if error:
            return False, f"Silence detection failed: {error}"

        if silence_info is None:
            return False, "Could not analyze video"

        output_path = get_output_filename(file_path, self.output_folder, self._used_outputs)
        self._used_outputs.add(output_path)
        if Path(output_path).name != f'{Path(file_path).stem}_trimmed{Path(file_path).suffix}':
            # Совпадение имён — не редкость: у записей с экрана и с телефона
            # они часто одинаковые. Раз файл назван иначе, чем ожидается,
            # об этом надо сказать, иначе человек будет искать его по
            # привычному имени.
            self.log_message.emit(
                f'Имя занято, результат сохраняется как {Path(output_path).name}')
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if self.remove_internal_silence:
            segments = get_segments_without_silence(
                silence_info,
                self.internal_silence_threshold,
                trim_edges=True
            )

            if len(segments) == 1:
                start_time, end_time = segments[0]
                if start_time < 0.1 and abs(end_time - silence_info.total_duration) < 0.1:
                    return self._report_no_silence(file_path, output_path, filename)

                self.log_message.emit(f"Trimming edges: {start_time:.2f}s - {end_time:.2f}s")
                self.progress_file.emit(30, filename)
                return self._trim_video_simple(file_path, output_path, start_time, end_time, filename)
            else:
                total_removed = silence_info.total_duration - sum(e - s for s, e in segments)
                self.log_message.emit(f"Removing {len(segments)-1} internal pauses ({total_removed:.1f}s total)")
                self.progress_file.emit(30, filename)
                return self._trim_video_segments(file_path, output_path, segments, filename)
        else:
            start_time, end_time = get_trim_times(silence_info)

            self.log_message.emit(f"Обнаружена тишина: начало={start_time:.2f}s, конец={end_time:.2f}s, всего={silence_info.total_duration:.2f}s")

            if start_time < 0.1 and abs(end_time - silence_info.total_duration) < 0.1:
                return self._report_no_silence(file_path, output_path, filename)

            self.log_message.emit(f"Обрезка: {start_time:.2f}s - {end_time:.2f}s")
            self.progress_file.emit(30, filename)

            saved = start_time + (silence_info.total_duration - end_time)
            success, msg = self._trim_video_simple(file_path, output_path, start_time, end_time, filename)
            if success:
                return True, f"Обрезано {saved:.1f}s тишины"
            return success, msg

    def _suggest_threshold(self, file_path: str):
        """Порог, при котором в этой записи тишина всё-таки нашлась бы.

        Спрашиваем ровно тот же детектор, который потом и будет работать, —
        перебираем пороги вверх от текущего, пока тишина не найдётся.

        Считать по своей огибающей нельзя, хотя это было бы быстрее: она
        снимается с моно 8 кГц и показывает систематически тише, чем
        silencedetect. На проверяемой записи она обещала тишину уже при
        -60 dB, тогда как на деле её нет и при -50. Совет, разошедшийся с
        поведением программы, хуже отсутствия совета.
        """
        current = int(str(self.noise_threshold).replace('dB', '') or -50)
        for threshold in range(current + 5, -14, 5):
            if self._cancelled:
                return None
            info, error = detect_silence(file_path, f'{threshold}dB',
                                         self.min_silence_duration)
            if error or info is None:
                return None
            if info.all_silences:
                return threshold
        return None

    def _deliver_unchanged(self, file_path: str, output_path: str, filename: str):
        """Кладёт видео в папку результата, когда резать нечего.

        Раньше в этом случае не появлялось ничего: приложение писало «файл не
        изменён» и считало его обработанным, а человек открывал папку и не
        находил там видео. Просили обработать несколько штук — значит в папке
        должны лежать все, включая те, где резать было нечего.
        """
        try:
            if os.path.abspath(file_path) != os.path.abspath(output_path):
                shutil.copy2(file_path, output_path)
        except Exception as exc:
            return False, f'Не удалось сохранить копию: {exc}'
        self.progress_file.emit(100, filename)
        return True, 'Тишина не найдена, файл скопирован без изменений'

    def _report_no_silence(self, file_path: str, output_path: str, filename: str):
        self.log_message.emit(f'Тишина не обнаружена в {filename}')
        suggestion = self._suggest_threshold(file_path)
        if suggestion is not None:
            self.log_message.emit(
                f'Фон в этой записи громче текущего порога {self.noise_threshold}. '
                f'Чтобы тишина нашлась, попробуйте порог около {suggestion} dB.')
        return self._deliver_unchanged(file_path, output_path, filename)

    @staticmethod
    def _abort(process, output_path: str):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        # ffmpeg was killed mid-write, so whatever landed on disk is a broken file.
        try:
            os.remove(output_path)
        except OSError:
            pass

    def _trim_video_simple(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
        filename: str
    ) -> Tuple[bool, str]:
        if self.precise_cut:
            # Точная обрезка перекодирует видео, поэтому берём ту сборку
            # ffmpeg, которая умеет аппаратное кодирование.
            cmd = [
                encoder_ffmpeg_path(),
                '-y',
                '-i', input_path,
                '-ss', str(start_time),
                '-to', str(end_time),
                *video_encoder_args(),
                '-c:a', 'aac',
                '-b:a', '192k',
                '-async', '1',
                output_path
            ]
        else:
            cmd = [
                ffmpeg_path(),
                '-y',
                '-ss', str(start_time),
                '-i', input_path,
                '-t', str(end_time - start_time),
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                output_path
            ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **subprocess_kwargs()
            )

            duration = max(0.0, end_time - start_time)
            stderr_lines = []

            while True:
                if self._cancelled:
                    self._abort(process, output_path)
                    return False, "Cancelled"

                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                stderr_lines.append(line)

                time_match = re.search(r'time=(\d+):(\d+):(\d+\.?\d*)', line)
                if time_match:
                    hours = int(time_match.group(1))
                    minutes = int(time_match.group(2))
                    seconds = float(time_match.group(3))
                    current_time = hours * 3600 + minutes * 60 + seconds

                    if duration > 0:
                        progress = min(99, int(30 + (current_time / duration) * 70))
                        self.progress_file.emit(progress, filename)

            process.wait()
            stderr_text = "".join(stderr_lines)

            if process.returncode == 0:
                self.progress_file.emit(100, filename)
                if os.path.exists(output_path):
                    return True, "Success"
                else:
                    return False, f"File not created. Log: {stderr_text[-200:]}"
            else:
                return False, f"FFMPEG error (code {process.returncode}): {stderr_text[-300:]}"

        except Exception as e:
            return False, f"Exception: {str(e)}"

    def _trim_video_segments(
        self,
        input_path: str,
        output_path: str,
        segments: List[Tuple[float, float]],
        filename: str
    ) -> Tuple[bool, str]:
        try:
            filter_parts = []
            for i, (start, end) in enumerate(segments):
                filter_parts.append(
                    f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];"
                    f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}];"
                )

            concat_v = "".join(f"[v{i}]" for i in range(len(segments)))
            concat_a = "".join(f"[a{i}]" for i in range(len(segments)))
            filter_parts.append(f"{concat_v}concat=n={len(segments)}:v=1:a=0[outv];")
            filter_parts.append(f"{concat_a}concat=n={len(segments)}:v=0:a=1[outa]")

            filter_complex = "".join(filter_parts)

            cmd = [
                encoder_ffmpeg_path(),
                '-y',
                '-i', input_path,
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-map', '[outa]',
                *video_encoder_args(),
                '-c:a', 'aac',
                '-b:a', '192k',
                output_path
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **subprocess_kwargs()
            )

            total_duration = sum(end - start for start, end in segments)
            stderr_lines = []

            while True:
                if self._cancelled:
                    self._abort(process, output_path)
                    return False, "Cancelled"

                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                stderr_lines.append(line)

                time_match = re.search(r'time=(\d+):(\d+):(\d+\.?\d*)', line)
                if time_match:
                    hours = int(time_match.group(1))
                    minutes = int(time_match.group(2))
                    seconds = float(time_match.group(3))
                    current_time = hours * 3600 + minutes * 60 + seconds

                    if total_duration > 0:
                        progress = min(99, int(30 + (current_time / total_duration) * 70))
                        self.progress_file.emit(progress, filename)

            process.wait()
            stderr_text = "".join(stderr_lines)

            if process.returncode == 0:
                self.progress_file.emit(100, filename)
                return True, f"Removed {len(segments)-1} pauses"
            else:
                return False, f"FFMPEG error (code {process.returncode}): {stderr_text[-300:]}"

        except Exception as e:
            return False, str(e)


class MergeWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files: List[str] = []
        self.output_path: str = ""
        self._cancelled = False

    def set_files(self, files: List[str], output_path: str):
        self.files = files
        self.output_path = output_path

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self.progress.emit(5, "Подготовка списка файлов...")

            list_file = Path(self.output_path).parent / "concat_list.txt"
            with open(list_file, 'w', encoding='utf-8') as f:
                for file_path in self.files:
                    safe_path = file_path.replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")

            self.progress.emit(10, "Склейка видео...")

            cmd = [
                ffmpeg_path(),
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(list_file),
                '-c', 'copy',
                self.output_path
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **subprocess_kwargs()
            )

            stderr_lines = []
            while True:
                if self._cancelled:
                    process.terminate()
                    list_file.unlink(missing_ok=True)
                    self.finished_signal.emit(False, "Отменено")
                    return

                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                stderr_lines.append(line)

                time_match = re.search(r'time=(\d+):(\d+):(\d+\.?\d*)', line)
                if time_match:
                    self.progress.emit(50, "Склейка...")

            process.wait()
            list_file.unlink(missing_ok=True)

            if process.returncode == 0 and os.path.exists(self.output_path):
                self.progress.emit(100, "Готово!")
                self.finished_signal.emit(True, f"Видео сохранено:\n{self.output_path}")
            else:
                stderr_text = "".join(stderr_lines)
                self.finished_signal.emit(False, f"Ошибка ffmpeg: {stderr_text[-300:]}")

        except Exception as e:
            self.finished_signal.emit(False, f"Ошибка: {str(e)}")
