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
def _locate(tool: str) -> Optional[str]:
    exe = f"{tool}.exe" if os.name == 'nt' else tool

    subfolders = ('', 'vendor', 'ffmpeg', os.path.join('ffmpeg', 'bin'))
    for root in _search_roots():
        for folder in (os.path.join(root, sub) for sub in subfolders):
            candidate = os.path.join(folder, exe)
            if os.path.isfile(candidate):
                return candidate

    return shutil.which(tool)


def ffmpeg_path() -> str:
    return _locate('ffmpeg') or 'ffmpeg'


def is_available() -> bool:
    return _locate('ffmpeg') is not None


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
