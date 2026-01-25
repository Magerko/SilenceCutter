import os
import subprocess
import json
from pathlib import Path
from typing import Optional, Tuple


VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg'}


def is_video_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS


def get_video_files_from_folder(folder_path: str) -> list[str]:
    files = []
    folder = Path(folder_path)
    if folder.is_dir():
        for file in folder.iterdir():
            if file.is_file() and is_video_file(str(file)):
                files.append(str(file))
    return sorted(files)


def get_output_filename(input_path: str, output_folder: str) -> str:
    input_file = Path(input_path)
    name = input_file.stem
    ext = input_file.suffix
    output_name = f"{name}_trimmed{ext}"
    return str(Path(output_folder) / output_name)


def get_video_duration(file_path: str) -> Optional[float]:
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data['format']['duration'])
    except Exception:
        pass
    return None


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "--:--:--"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def check_ffmpeg_available() -> Tuple[bool, str]:
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            return True, version_line
        return False, "FFMPEG not found"
    except FileNotFoundError:
        return False, "FFMPEG not installed or not in PATH"
    except Exception as e:
        return False, str(e)
