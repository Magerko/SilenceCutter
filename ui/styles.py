DARK_STYLE = """
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0f0c29, stop:0.5 #302b63, stop:1 #24243e);
}

QWidget {
    background: transparent;
    color: #e0e0e0;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}

QLabel {
    background: transparent;
    color: #e0e0e0;
    padding: 2px;
}

QLabel#titleLabel {
    font-size: 28px;
    font-weight: bold;
    color: #ff6b6b;
    background: transparent;
    padding: 10px 0;
}

QLabel#subtitleLabel {
    font-size: 12px;
    color: #8b8b9a;
    background: transparent;
}

QFrame#dropZone {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 107, 107, 0.1), stop:1 rgba(78, 205, 196, 0.1));
    border: 2px dashed #ff6b6b;
    border-radius: 20px;
    min-height: 120px;
}

QFrame#dropZone:hover {
    border-color: #4ecdc4;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(255, 107, 107, 0.2), stop:1 rgba(78, 205, 196, 0.2));
}

QFrame#dropZoneActive {
    border: 3px solid #4ecdc4;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(78, 205, 196, 0.3), stop:1 rgba(255, 107, 107, 0.3));
}

QListWidget {
    background-color: rgba(48, 43, 99, 0.6);
    border: 1px solid rgba(255, 107, 107, 0.4);
    border-radius: 16px;
    padding: 8px;
    outline: none;
}

QListWidget::item {
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 16px;
    margin: 4px 2px;
    border-left: 3px solid transparent;
}

QListWidget::item:selected {
    background-color: rgba(255, 107, 107, 0.25);
    border-left: 3px solid #ff6b6b;
}

QListWidget::item:hover {
    background-color: rgba(78, 205, 196, 0.2);
}

QListWidget QScrollBar:vertical {
    background: transparent;
}

QPushButton {
    background-color: rgba(48, 43, 99, 0.8);
    color: #e0e0e0;
    border: 1px solid rgba(255, 107, 107, 0.4);
    border-radius: 12px;
    padding: 12px 24px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: rgba(78, 205, 196, 0.3);
    border: 1px solid #4ecdc4;
    color: #fff;
}

QPushButton:pressed {
    background-color: rgba(78, 205, 196, 0.5);
}

QPushButton:disabled {
    background-color: rgba(30, 30, 50, 0.5);
    color: #555;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ff6b6b, stop:1 #ff8e53);
    color: #fff;
    border: none;
    font-weight: bold;
    font-size: 15px;
}

QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ff8e53, stop:1 #ff6b6b);
}

QPushButton#primaryButton:pressed {
    background: #e55a5a;
}

QPushButton#primaryButton:disabled {
    background: rgba(255, 107, 107, 0.3);
    color: rgba(255, 255, 255, 0.5);
}

QPushButton#dangerButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #fc4a4a, stop:1 #f54ea2);
    color: #fff;
    border: none;
}

QPushButton#dangerButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #f54ea2, stop:1 #fc4a4a);
}

QProgressBar {
    background-color: rgba(48, 43, 99, 0.6);
    border: 1px solid rgba(255, 107, 107, 0.3);
    border-radius: 8px;
    height: 18px;
    text-align: center;
    color: #fff;
    font-weight: bold;
    font-size: 11px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ff6b6b, stop:0.5 #ff8e53, stop:1 #ffcc5c);
    border-radius: 7px;
    margin: 1px;
}

QProgressBar#fileProgress {
    background-color: rgba(48, 43, 99, 0.6);
    border: 1px solid rgba(78, 205, 196, 0.3);
}

QProgressBar#fileProgress::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4ecdc4, stop:1 #44bd9e);
    border-radius: 7px;
    margin: 1px;
}

QLineEdit {
    background-color: rgba(48, 43, 99, 0.6);
    border: 1px solid rgba(255, 107, 107, 0.3);
    border-radius: 10px;
    padding: 10px 14px;
    color: #e0e0e0;
    selection-background-color: #ff6b6b;
}

QLineEdit:focus {
    border: 1px solid #ff6b6b;
    background-color: rgba(255, 107, 107, 0.15);
}

QLineEdit:read-only {
    background-color: rgba(36, 36, 62, 0.8);
    color: #bbb;
    border: 1px solid rgba(78, 205, 196, 0.3);
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
    margin: 4px 0;
}

QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ff6b6b, stop:1 #4ecdc4);
    border-radius: 4px;
    min-height: 40px;
}

QScrollBar::handle:vertical:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ff8e53, stop:1 #44bd9e);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QStatusBar {
    background: rgba(0, 0, 0, 0.3);
    color: #8b8b9a;
    padding: 6px 12px;
    border-top: 1px solid rgba(255, 107, 107, 0.2);
}

QToolTip {
    background: rgba(15, 12, 41, 0.95);
    color: #e0e0e0;
    border: 1px solid #ff6b6b;
    border-radius: 8px;
    padding: 8px 12px;
}

QMessageBox {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0f0c29, stop:0.5 #302b63, stop:1 #24243e);
}

QMessageBox QLabel {
    color: #e0e0e0;
    background: transparent;
}

QMessageBox QPushButton {
    min-width: 100px;
    padding: 8px 20px;
}

QCheckBox {
    background: transparent;
    color: #e0e0e0;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid rgba(255, 107, 107, 0.5);
    background-color: rgba(48, 43, 99, 0.6);
}

QCheckBox::indicator:hover {
    border: 2px solid #ff6b6b;
    background-color: rgba(255, 107, 107, 0.2);
}

QCheckBox::indicator:checked {
    background-color: #ff6b6b;
    border: 2px solid #ff6b6b;
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iI2ZmZiIgZD0iTTkgMTYuMTdMNC44MyAxMmwtMS40MiAxLjQxTDkgMTkgMjEgN2wtMS40MS0xLjQxeiIvPjwvc3ZnPg==);
}

QCheckBox:disabled {
    color: #555;
}

QDoubleSpinBox {
    background-color: rgba(48, 43, 99, 0.6);
    border: 1px solid rgba(255, 107, 107, 0.3);
    border-radius: 8px;
    padding: 6px 10px;
    color: #e0e0e0;
}

QDoubleSpinBox:focus {
    border: 1px solid #ff6b6b;
}

QDoubleSpinBox:disabled {
    background-color: rgba(30, 30, 50, 0.5);
    color: #555;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: rgba(255, 107, 107, 0.3);
    border: none;
    width: 20px;
    border-radius: 4px;
}

QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: rgba(255, 107, 107, 0.5);
}

QDoubleSpinBox::up-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 5px solid #e0e0e0;
    width: 0;
    height: 0;
}

QDoubleSpinBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #e0e0e0;
    width: 0;
    height: 0;
}

QMenu {
    background-color: rgba(30, 27, 60, 0.95);
    border: 1px solid rgba(255, 107, 107, 0.4);
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    background-color: transparent;
    padding: 8px 24px;
    border-radius: 4px;
    color: #e0e0e0;
}

QMenu::item:selected {
    background-color: rgba(255, 107, 107, 0.3);
}

QMenu::separator {
    height: 1px;
    background: rgba(255, 107, 107, 0.3);
    margin: 4px 8px;
}
"""

LIGHT_STYLE = """
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ffecd2, stop:1 #fcb69f);
}

QWidget {
    background: transparent;
    color: #2d3436;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}

QLabel {
    background: transparent;
    color: #2d3436;
    padding: 2px;
}

QLabel#titleLabel {
    font-size: 28px;
    font-weight: bold;
    color: #e17055;
    background: transparent;
}

QFrame#dropZone {
    background: rgba(255, 255, 255, 0.4);
    border: 2px dashed #e17055;
    border-radius: 20px;
}

QListWidget {
    background: rgba(255, 255, 255, 0.5);
    border: 1px solid rgba(225, 112, 85, 0.3);
    border-radius: 16px;
}

QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #e17055, stop:1 #f39c7a);
    color: #fff;
    border: none;
    font-weight: bold;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #e17055, stop:1 #f39c7a);
}

QStatusBar {
    background: rgba(255, 255, 255, 0.3);
    color: #636e72;
}
"""


def get_style(dark_mode: bool = True) -> str:
    return DARK_STYLE if dark_mode else LIGHT_STYLE
