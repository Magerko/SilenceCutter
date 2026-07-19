"""Экран загрузки модели распознавания.

Модель весит около трёх гигабайт и качается при первом открытии вкладки.
Голая полоса прогресса на такой срок читается как зависшая программа, поэтому
экран отвечает на четыре вопроса: что качается, сколько осталось, можно ли
прервать и почему это происходит один раз.
"""
import time
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)


def _format_size(megabytes: float) -> str:
    if megabytes >= 1024:
        return f'{megabytes / 1024:.1f} ГБ'
    return f'{megabytes:.0f} МБ'


def _format_remaining(seconds: float) -> str:
    if seconds <= 0:
        return ''
    if seconds < 60:
        return 'осталось меньше минуты'
    minutes = int(seconds // 60)
    if minutes < 60:
        return f'осталось ~{minutes} мин'
    hours, rest = divmod(minutes, 60)
    if rest == 0:
        return f'осталось ~{hours} ч'
    return f'осталось ~{hours} ч {rest} мин'


class ModelDownloadPanel(QWidget):
    """Показывает ход загрузки модели и даёт её прервать."""

    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._started_at: Optional[float] = None
        self._started_mb = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.title = QLabel('Загрузка модели распознавания речи')
        self.title.setStyleSheet(
            'background: transparent; font-size: 14px; font-weight: 600;')
        layout.addWidget(self.title)

        self.explanation = QLabel(
            'Нужна один раз, чтобы находить слова в звуке. '
            'После загрузки работает без интернета.')
        self.explanation.setWordWrap(True)
        self.explanation.setStyleSheet('background: transparent; color: #aab0ba;')
        layout.addWidget(self.explanation)

        self.bar = QProgressBar()
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        status_row = QHBoxLayout()
        self.amount = QLabel('Подготовка...')
        self.amount.setStyleSheet('background: transparent;')
        status_row.addWidget(self.amount)
        status_row.addStretch()

        self.rate = QLabel('')
        self.rate.setStyleSheet('background: transparent; color: #868c96;')
        status_row.addWidget(self.rate)

        self.cancel_btn = QPushButton('Отменить')
        self.cancel_btn.setObjectName('dangerButton')
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        status_row.addWidget(self.cancel_btn)
        layout.addLayout(status_row)

        self.note = QLabel(
            'Это происходит один раз: модель останется на диске, '
            'и в следующий раз вкладка откроется сразу.')
        self.note.setWordWrap(True)
        self.note.setStyleSheet('background: transparent; color: #868c96;')
        layout.addWidget(self.note)

        self.setVisible(False)

    def start(self, model_name: str, total_mb: float):
        self._started_at = None
        self._started_mb = 0.0
        self.title.setText(f'Загрузка модели распознавания речи — {_format_size(total_mb)}')
        self.bar.setValue(0)
        self.amount.setText('Подготовка...')
        self.rate.setText('')
        self.cancel_btn.setEnabled(True)
        self.setVisible(True)

    def update_progress(self, percent: int, done_mb: float, total_mb: float):
        self.bar.setValue(percent)
        self.amount.setText(
            f'{_format_size(done_mb)} из {_format_size(total_mb)} · {percent}%')

        # Скорость считаем от первого замера, а не от запуска: пока
        # huggingface_hub раскладывает файлы, размер папки ещё не растёт, и
        # ранние секунды занизили бы оценку.
        now = time.monotonic()
        if self._started_at is None:
            if done_mb > 0:
                self._started_at = now
                self._started_mb = done_mb
            return

        elapsed = now - self._started_at
        gained = done_mb - self._started_mb
        if elapsed < 2 or gained <= 0:
            return

        speed = gained / elapsed
        remaining = max(0.0, total_mb - done_mb) / speed if speed > 0 else 0
        self.rate.setText(f'{speed:.1f} МБ/с · {_format_remaining(remaining)}')

    def finish(self):
        self.setVisible(False)

    def show_cancelled(self):
        self.amount.setText('Загрузка отменена')
        self.rate.setText('')
        self.cancel_btn.setEnabled(False)
