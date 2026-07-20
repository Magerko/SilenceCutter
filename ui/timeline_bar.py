"""Полоса обзора под дорожкой громкости.

Работает как в монтажных программах: прямоугольник показывает, какая часть
записи видна сейчас. Его можно тащить за середину, чтобы прокрутить, и за
края, чтобы менять масштаб. Обычной полосы прокрутки было бы мало: она
позволяет только листать, а на записи в полчаса нужно ещё и приближать.
"""
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget

EDGE_GRIP_PX = 7
MIN_SPAN_SECONDS = 0.5


class TimelineBar(QWidget):
    view_changed = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.duration = 0.0
        self.view_start = 0.0
        self.view_span = 0.0
        self._mode = None
        self._grab_offset = 0.0

    # --- данные ---------------------------------------------------------
    def set_duration(self, seconds: float):
        self.duration = max(0.0, seconds)
        self.view_start = 0.0
        self.view_span = self.duration
        self.update()

    def set_view(self, start: float, span: float):
        if self.duration <= 0:
            return
        span = max(MIN_SPAN_SECONDS, min(span or self.duration, self.duration))
        start = max(0.0, min(start, self.duration - span))
        self.view_start, self.view_span = start, span
        self.update()

    # --- геометрия ------------------------------------------------------
    def _handle_rect(self) -> QRectF:
        if self.duration <= 0:
            return QRectF(0, 0, self.width(), self.height())
        left = self.width() * (self.view_start / self.duration)
        width = self.width() * (min(self.view_span, self.duration) / self.duration)
        return QRectF(left, 3, max(12.0, width), self.height() - 6)

    def _time_for_x(self, x: float) -> float:
        if self.width() <= 0 or self.duration <= 0:
            return 0.0
        return max(0.0, min(self.duration, self.duration * x / self.width()))

    # --- отрисовка ------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QColor('#1c1e23'))
        painter.drawRoundedRect(QRectF(0, 3, self.width(), self.height() - 6), 5, 5)

        if self.duration <= 0:
            painter.end()
            return

        handle = self._handle_rect()
        painter.setBrush(QColor('#0d7c72'))
        painter.drawRoundedRect(handle, 5, 5)

        # Засечки по краям подсказывают, что за них можно тянуть.
        painter.setBrush(QColor('#4ecdc4'))
        for x in (handle.left() + 3, handle.right() - 5):
            painter.drawRoundedRect(QRectF(x, handle.top() + 4, 2, handle.height() - 8), 1, 1)
        painter.end()

    # --- мышь -----------------------------------------------------------
    def _zone(self, x: float) -> str:
        handle = self._handle_rect()
        if abs(x - handle.left()) <= EDGE_GRIP_PX:
            return 'left'
        if abs(x - handle.right()) <= EDGE_GRIP_PX:
            return 'right'
        if handle.left() < x < handle.right():
            return 'move'
        return 'jump'

    def mouseMoveEvent(self, event):
        x = event.position().x()
        if self._mode is None:
            zone = self._zone(x)
            self.setCursor(Qt.CursorShape.SizeHorCursor if zone in ('left', 'right')
                           else Qt.CursorShape.PointingHandCursor)
            return

        moment = self._time_for_x(x)
        if self._mode == 'move':
            self.set_view(moment - self._grab_offset, self.view_span)
        elif self._mode == 'left':
            right = self.view_start + self.view_span
            start = min(moment, right - MIN_SPAN_SECONDS)
            self.set_view(start, right - start)
        elif self._mode == 'right':
            self.set_view(self.view_start,
                          max(MIN_SPAN_SECONDS, moment - self.view_start))
        self.view_changed.emit(self.view_start, self.view_span)

    def mousePressEvent(self, event):
        if self.duration <= 0 or event.button() != Qt.MouseButton.LeftButton:
            return
        x = event.position().x()
        zone = self._zone(x)
        if zone == 'jump':
            # Клик мимо окна переносит его в это место, сохраняя масштаб.
            self.set_view(self._time_for_x(x) - self.view_span / 2, self.view_span)
            self.view_changed.emit(self.view_start, self.view_span)
            zone = 'move'
        self._mode = zone
        self._grab_offset = self._time_for_x(x) - self.view_start

    def mouseReleaseEvent(self, event):
        self._mode = None

    def wheelEvent(self, event):
        if self.duration <= 0:
            return
        steps = event.angleDelta().y() / 120.0
        if not steps:
            return
        moment = self._time_for_x(event.position().x())
        span = max(MIN_SPAN_SECONDS, min(self.view_span / (1.25 ** steps), self.duration))
        ratio = 0.5 if self.view_span <= 0 else (moment - self.view_start) / self.view_span
        self.set_view(moment - ratio * span, span)
        self.view_changed.emit(self.view_start, self.view_span)
        event.accept()
