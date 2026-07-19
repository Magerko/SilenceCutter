import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Распознавание речи выполняется в отдельном процессе, и запускается он этим
# же файлом с флагом. Проверка обязана стоять ДО импорта PyQt6: если Qt6
# загрузится раньше ctranslate2, распознавание падает с нарушением доступа.
if '--transcribe-worker' in sys.argv:
    from core.transcribe_cli import run
    sys.exit(run())

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from ui.main_window import MainWindow
from ui.styles import get_style
from utils.paths import resource_path


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("SilenceCutter")
    app.setStyleSheet(get_style(dark_mode=True))

    icon_path = resource_path(os.path.join('resources', 'icon.png'))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
