import os
import shutil
import subprocess
import sys
from functools import lru_cache
from typing import Optional


def _search_roots() -> list:
    roots = []
    if getattr(sys, 'frozen', False):
        # onedir keeps the binaries next to the exe while _MEIPASS points at the
        # bundled-data folder; onefile only has _MEIPASS. Check both.
        roots.append(os.path.dirname(os.path.abspath(sys.executable)))
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            roots.append(meipass)
    else:
        roots.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return roots


@lru_cache(maxsize=None)
def _all_locations(tool: str) -> tuple:
    """Every copy of the tool we can find, bundled first, then PATH."""
    exe = f"{tool}.exe" if os.name == 'nt' else tool
    found = []

    subfolders = ('', 'vendor', 'ffmpeg', os.path.join('ffmpeg', 'bin'))
    for root in _search_roots():
        for folder in (os.path.join(root, sub) for sub in subfolders):
            candidate = os.path.join(folder, exe)
            if os.path.isfile(candidate) and candidate not in found:
                found.append(candidate)

    on_path = shutil.which(tool)
    if on_path and on_path not in found:
        found.append(on_path)

    return tuple(found)


def _locate(tool: str) -> Optional[str]:
    locations = _all_locations(tool)
    return locations[0] if locations else None


def ffmpeg_path() -> str:
    return _locate('ffmpeg') or 'ffmpeg'


def is_available() -> bool:
    return _locate('ffmpeg') is not None


# Аппаратные кодировщики в порядке предпочтения, с параметрами качества,
# подобранными близко к libx264 -crf 18. Порядок: NVIDIA, Intel, AMD.
HARDWARE_ENCODERS = (
    ('h264_nvenc', ['-preset', 'p5', '-rc', 'vbr', '-cq', '21', '-b:v', '0']),
    ('h264_qsv', ['-preset', 'medium', '-global_quality', '21']),
    ('h264_amf', ['-quality', 'quality', '-rc', 'cqp', '-qp_i', '21', '-qp_p', '23']),
)
SOFTWARE_ENCODER = ('libx264', ['-preset', 'fast', '-crf', '18'])


def _probe_encoder(exe: str, codec: str) -> bool:
    """Пробная кодировка одного кадра конкретным ffmpeg.

    Списку `ffmpeg -encoders` доверять нельзя: сборки содержат nvenc, qsv и amf
    независимо от железа. Проверка ловит и несовпадение версии драйвера -
    случай, когда карта есть, а кодировщик всё равно не запускается: свежие
    сборки ffmpeg требуют более новую версию NVENC API, чем даёт драйвер.
    """
    cmd = [
        exe, '-hide_banner', '-loglevel', 'error',
        '-f', 'lavfi', '-i', 'color=black:s=256x256:d=0.1',
        '-frames:v', '1', '-c:v', codec, '-f', 'null', '-',
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=20,
                                **subprocess_kwargs())
        return result.returncode == 0
    except Exception:
        return False


@lru_cache(maxsize=None)
def encoding_setup() -> tuple:
    """Пара (ffmpeg, кодек, параметры), дающая самое быстрое кодирование.

    Перебираются все найденные копии ffmpeg, а не только предпочтительная:
    вложенная сборка может не поддерживать ускорение при текущем драйвере,
    тогда как установленная в системе - поддерживает. Аппаратное кодирование
    примерно вчетверо быстрее, так что ради него стоит взять другой бинарник.
    """
    candidates = _all_locations('ffmpeg') or ('ffmpeg',)
    for exe in candidates:
        for codec, options in HARDWARE_ENCODERS:
            if _probe_encoder(exe, codec):
                return exe, codec, list(options)
    return candidates[0], SOFTWARE_ENCODER[0], list(SOFTWARE_ENCODER[1])


def encoder_ffmpeg_path() -> str:
    return encoding_setup()[0]


def video_encoder_args() -> list:
    _, codec, options = encoding_setup()
    return ['-c:v', codec] + options


def is_hardware_accelerated() -> bool:
    return encoding_setup()[1] != SOFTWARE_ENCODER[0]


def subprocess_kwargs() -> dict:
    # ffmpeg writes UTF-8 to stderr regardless of the system codepage, so decoding
    # with the locale default raises UnicodeDecodeError on non-ASCII filenames.
    # stdin must be redirected too: a --noconsole build has no valid stdin handle
    # to hand down to the child process.
    kwargs = {
        'text': True,
        'encoding': 'utf-8',
        'errors': 'replace',
        'stdin': subprocess.DEVNULL,
    }
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    return kwargs
