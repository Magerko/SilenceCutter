import os
import sys

APP_NAME = 'SilenceCutter'


def user_data_dir() -> str:
    """Куда программа пишет: словари пользователя, модели, настройки."""
    if os.name == 'nt':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin':
        base = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:
        base = os.environ.get('XDG_DATA_HOME') or os.path.join(
            os.path.expanduser('~'), '.local', 'share')
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def models_dir() -> str:
    """Модели распознавания речи качаются сюда при первом использовании."""
    path = os.path.join(user_data_dir(), 'models')
    os.makedirs(path, exist_ok=True)
    return path


def resource_path(relative_path: str) -> str:
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)
