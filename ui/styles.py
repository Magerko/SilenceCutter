"""Оформление по дизайн-системе семейства.

Значения из общей системы: бирюза #4ecdc4 — родовой акцент трёх приложений,
коралловый #ff6b6b — опасные действия, шкала отступов 4/8/12/16/24/32.

Ограничения Qt, из-за которых это не обычный CSS: нет переменных, вложенности,
calc(), transition и box-shadow, размеры только в пикселях. Всё ниже держится
в рамках поддерживаемого подмножества.
"""

DARK = {
    'bg': '#141519',
    'surface': '#1b1d21',
    'surface_alt': '#1c1e23',
    'raised': '#24272e',
    'raised_alt': '#2b2f37',
    'hover': '#2d313a',
    'border': '#3a3f49',
    'border_strong': '#4c525d',
    'text': '#e9ebee',
    'text_secondary': '#aab0ba',
    'text_muted': '#868c96',
    'accent': '#4ecdc4',
    'accent_deep': '#0d7c72',
    'accent_mid': '#0f8378',
    'accent_bg': '#12302c',
    'danger': '#ff6b6b',
    'success': '#40c463',
    'disabled_text': '#565b63',
}

LIGHT = {
    'bg': '#f4f5f7',
    'surface': '#ffffff',
    'surface_alt': '#fafbfc',
    'raised': '#ffffff',
    'raised_alt': '#eef0f3',
    'hover': '#e6e9ed',
    'border': '#d5d9e0',
    'border_strong': '#b6bcc6',
    'text': '#1b1d21',
    'text_secondary': '#4c525d',
    'text_muted': '#7c828b',
    'accent': '#0f8378',
    'accent_deep': '#0d7c72',
    'accent_mid': '#4ecdc4',
    'accent_bg': '#e2f5f2',
    'danger': '#d64545',
    'success': '#2f9e51',
    'disabled_text': '#aab0ba',
}

_TEMPLATE = """
QMainWindow, QDialog {{
    background: {bg};
}}
QWidget {{
    color: {text};
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}}
QLabel {{
    background: transparent;
    color: {text};
}}

QTabWidget::pane {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 10px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {text_secondary};
    padding: 8px 18px;
    margin-right: 4px;
    border: 1px solid transparent;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
}}
QTabBar::tab:hover {{
    color: {text};
    background: {hover};
}}
QTabBar::tab:selected {{
    color: {accent};
    background: {surface};
    border: 1px solid {border};
    border-bottom-color: {surface};
}}

QPushButton {{
    background: {raised};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 16px;
    min-height: 18px;
}}
QPushButton:hover {{
    background: {hover};
    border-color: {border_strong};
}}
QPushButton:pressed {{
    background: {raised_alt};
}}
QPushButton:disabled {{
    color: {disabled_text};
    background: {surface_alt};
    border-color: {border};
}}
QPushButton#primaryButton {{
    background: {accent_deep};
    border-color: {accent_mid};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{
    background: {accent_mid};
}}
QPushButton#primaryButton:disabled {{
    background: {surface_alt};
    border-color: {border};
    color: {disabled_text};
}}
QPushButton#dangerButton {{
    background: transparent;
    border-color: {danger};
    color: {danger};
}}
QPushButton#dangerButton:hover {{
    background: {danger};
    color: #ffffff;
}}

QLineEdit, QPlainTextEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
    background: {surface_alt};
    color: {text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {accent_deep};
    selection-color: #ffffff;
}}
QLineEdit:hover, QPlainTextEdit:hover, QDoubleSpinBox:hover,
QSpinBox:hover, QComboBox:hover {{
    border-color: {border_strong};
}}
QLineEdit:focus, QPlainTextEdit:focus, QDoubleSpinBox:focus,
QSpinBox:focus, QComboBox:focus {{
    border-color: {accent};
}}
QLineEdit[readOnly="true"] {{
    color: {text_secondary};
    background: {surface};
}}
QLineEdit:disabled, QPlainTextEdit:disabled, QDoubleSpinBox:disabled,
QSpinBox:disabled, QComboBox:disabled {{
    color: {disabled_text};
    background: {surface};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {raised};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accent_bg};
    selection-color: {text};
    outline: none;
}}
QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {{
    background: {raised};
    border: none;
    width: 16px;
}}
QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
    background: {hover};
}}

QCheckBox, QRadioButton {{
    background: transparent;
    color: {text};
    spacing: 8px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border_strong};
    background: {surface_alt};
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {accent};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {accent_deep};
    border-color: {accent};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    border-color: {border};
    background: {surface};
}}

QListWidget {{
    background: {surface_alt};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 7px 10px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background: {hover};
}}
QListWidget::item:selected {{
    background: {accent_bg};
    color: {text};
}}

QProgressBar {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 7px;
    height: 14px;
    text-align: center;
    color: {text_secondary};
    font-size: 11px;
}}
QProgressBar::chunk {{
    background: {accent_deep};
    border-radius: 6px;
}}
QProgressBar#fileProgress::chunk {{
    background: {accent};
}}

/* Область прокрутки и вложенная страница рисуются обычным QWidget, а он берёт
   фон из системной палитры: без этих правил на тёмной теме сквозь настройки
   просвечивает белая подложка. */
QScrollArea {{
    background-color: {bg};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: {bg};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {border};
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {border_strong};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {border};
    border-radius: 5px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {border_strong};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

QMenu {{
    background: {raised};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 18px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {accent_bg};
}}
QStatusBar {{
    background: {surface};
    color: {text_secondary};
    border-top: 1px solid {border};
}}
QToolTip {{
    background: {raised};
    color: {text};
    border: 1px solid {border_strong};
    border-radius: 6px;
    padding: 6px 8px;
}}
"""


def get_style(dark_mode: bool = True) -> str:
    return _TEMPLATE.format(**(DARK if dark_mode else LIGHT))


# Прежний интерфейс модуля сохранён: на него ссылается остальной код.
DARK_STYLE = get_style(True)
LIGHT_STYLE = get_style(False)
