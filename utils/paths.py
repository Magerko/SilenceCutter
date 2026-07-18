import os
import sys


def resource_path(relative_path: str) -> str:
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)
