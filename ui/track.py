"""Дорожка — отрезки на длительности ролика.

Показ громкости с вырезаемыми участками, список заглушённых слов и ввод
отрезков времени — по сути одна задача. Поэтому здесь один виджет с
собственной отрисовкой; наследники меняют только содержимое тела, а линейка,
указатель, состояния и поведение общие.
"""
from typing import List, Optional, Tuple

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

# Состояния. Виджет не исчезает ни в одном из них: пропавший элемент читается
# как поломка, а не как отсутствие данных.
EMPTY = 'empty'
BUSY = 'busy'
READY = 'ready'
ERROR = 'error'

RULER_HEIGHT = 18
PADDING = 8


class TrackWidget(QWidget):
    """Основа: линейка времени, тело, указатель, четыре состояния."""

    view_changed = pyqtSignal(float, float)

    position_clicked = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

        self.state = EMPTY
        self.message = 'Файл не выбран'
        self.progress = 0
        self.duration = 0.0
        # Окно просмотра: с какой секунды и сколько секунд показываем. На
        # длинной записи целиком не разглядеть отдельные паузы, поэтому
        # дорожку можно приблизить и прокрутить.
        self.view_start = 0.0
        self.view_span = 0.0
        self.segments: List[Tuple[float, float]] = []
        self.cursor: Optional[float] = None

        self.colours = {
            'bg': QColor('#191b20'),
            'border': QColor('#2b2f37'),
            'ruler': QColor('#868c96'),
            'body': QColor('#24272e'),
            'keep': QColor('#4ecdc4'),
            'cut': QColor('#ff6b6b'),
            'muted': QColor('#565b63'),
            'text': QColor('#aab0ba'),
            'cursor': QColor('#e9ebee'),
        }

    # --- данные ---------------------------------------------------------
    def set_state(self, state: str, message: str = ''):
        self.state = state
        if message:
            self.message = message
        self.update()

    def set_progress(self, percent: int):
        self.progress = max(0, min(100, percent))
        self.update()

    def set_duration(self, seconds: float):
        self.duration = max(0.0, seconds)
        self.view_start = 0.0
        self.view_span = self.duration
        self.update()

    def set_segments(self, segments: List[Tuple[float, float]]):
        self.segments = list(segments)
        self.update()

    def set_cursor(self, seconds: Optional[float]):
        self.cursor = seconds
        self.update()

    # --- геометрия ------------------------------------------------------
    def body_rect(self) -> QRectF:
        return QRectF(PADDING, PADDING + RULER_HEIGHT,
                      max(1, self.width() - PADDING * 2),
                      max(1, self.height() - RULER_HEIGHT - PADDING * 2))

    def visible_span(self) -> float:
        """Сколько секунд помещается в окне сейчас."""
        if self.view_span > 0:
            return min(self.view_span, self.duration or self.view_span)
        return self.duration

    def x_for_time(self, seconds: float) -> float:
        body = self.body_rect()
        span = self.visible_span()
        if span <= 0:
            return body.left()
        return body.left() + body.width() * ((seconds - self.view_start) / span)

    def time_for_x(self, x: float) -> float:
        body = self.body_rect()
        span = self.visible_span()
        if body.width() <= 0 or span <= 0:
            return 0.0
        ratio = (x - body.left()) / body.width()
        return max(0.0, min(self.duration, self.view_start + ratio * span))

    def set_view(self, start: float, span: float):
        """Показать участок записи. Значения подгоняются под её границы."""
        if self.duration <= 0:
            return
        span = max(0.5, min(span or self.duration, self.duration))
        start = max(0.0, min(start, self.duration - span))
        if abs(start - self.view_start) < 1e-6 and abs(span - self.view_span) < 1e-6:
            return
        self.view_start = start
        self.view_span = span
        self.update()

    def zoom_at(self, seconds: float, factor: float):
        """Приблизить или отдалить, удерживая указанный момент на месте."""
        if self.duration <= 0:
            return
        span = self.visible_span()
        new_span = max(0.5, min(span / factor, self.duration))
        # Точка под курсором должна остаться там же, иначе при колесе картинка
        # уезжает и попасть в нужное место становится невозможно.
        ratio = 0.5 if span <= 0 else (seconds - self.view_start) / span
        self.set_view(seconds - ratio * new_span, new_span)

    def wheelEvent(self, event):
        if self.duration <= 0:
            super().wheelEvent(event)
            return
        steps = event.angleDelta().y() / 120.0
        if not steps:
            super().wheelEvent(event)
            return
        self.zoom_at(self.time_for_x(event.position().x()), 1.25 ** steps)
        self.view_changed.emit(self.view_start, self.visible_span())
        event.accept()

    # --- отрисовка ------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(self.colours['border'], 1))
        painter.setBrush(self.colours['bg'])
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 6, 6)

        if self.state == EMPTY:
            self._paint_empty(painter)
        elif self.state == ERROR:
            self._paint_message(painter, self.message, self.colours['cut'])
        else:
            self._paint_ruler(painter)
            self.paint_body(painter, self.body_rect())
            if self.state == BUSY:
                self._paint_busy(painter)
            self._paint_cursor(painter)
        painter.end()

    def _paint_empty(self, painter: QPainter):
        body = self.body_rect()
        pen = QPen(self.colours['muted'], 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body, 4, 4)
        self._paint_message(painter, self.message, self.colours['muted'])

    def _paint_message(self, painter: QPainter, text: str, colour: QColor):
        painter.setPen(colour)
        font = QFont(painter.font())
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def _paint_busy(self, painter: QPainter):
        """Заполнение слева направо: прогресс понятнее вращающегося кружка."""
        body = self.body_rect()
        covered = body.width() * self.progress / 100.0
        veil = QColor(self.colours['bg'])
        veil.setAlpha(190)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(veil)
        painter.drawRect(QRectF(body.left() + covered, body.top(),
                                max(0.0, body.width() - covered), body.height()))
        painter.setPen(QPen(self.colours['keep'], 2))
        painter.drawLine(int(body.left() + covered), int(body.top()),
                         int(body.left() + covered), int(body.bottom()))

    def _paint_ruler(self, painter: QPainter):
        if self.duration <= 0:
            return
        painter.setPen(self.colours['ruler'])
        font = QFont(painter.font())
        font.setPointSize(8)
        painter.setFont(font)
        for index in range(5):
            seconds = self.view_start + self.visible_span() * index / 4
            x = self.x_for_time(seconds)
            label = f'{int(seconds) // 60}:{int(seconds) % 60:02d}'
            width = 46
            if index == 0:
                rect = QRectF(x, 2, width, RULER_HEIGHT)
                align = Qt.AlignmentFlag.AlignLeft
            elif index == 4:
                rect = QRectF(x - width, 2, width, RULER_HEIGHT)
                align = Qt.AlignmentFlag.AlignRight
            else:
                rect = QRectF(x - width / 2, 2, width, RULER_HEIGHT)
                align = Qt.AlignmentFlag.AlignHCenter
            painter.drawText(rect, align | Qt.AlignmentFlag.AlignVCenter, label)

    def _paint_cursor(self, painter: QPainter):
        if self.cursor is None or self.duration <= 0:
            return
        body = self.body_rect()
        x = int(self.x_for_time(self.cursor))
        painter.setPen(QPen(self.colours['cursor'], 1))
        painter.drawLine(x, int(body.top()), x, int(body.bottom()))

    def paint_body(self, painter: QPainter, body: QRectF):
        """Переопределяется наследниками."""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.colours['body'])
        painter.drawRoundedRect(body, 4, 4)
        self.paint_segments(painter, body)

    def paint_segments(self, painter: QPainter, body: QRectF, colour: QColor = None):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour or self.colours['cut'])
        for start, end in self.segments:
            left = self.x_for_time(start)
            width = max(1.0, self.x_for_time(end) - left)
            painter.drawRect(QRectF(left, body.top(), width, body.height()))

    def mousePressEvent(self, event):
        if self.duration > 0 and self.state == READY:
            self.position_clicked.emit(self.time_for_x(event.position().x()))
        super().mousePressEvent(event)


class LoudnessTrack(TrackWidget):
    """Громкость записи с порогом: видно, что именно вырежется."""

    threshold_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.levels: List[float] = []
        self.window = 0.05
        self.threshold_db = -50.0
        self.floor_db = -70.0
        self._dragging = False

    def set_envelope(self, levels: List[float], duration: float, window: float):
        self.levels = list(levels)
        self.window = window
        self.set_duration(duration)

    def set_threshold(self, db: float):
        self.threshold_db = db
        self.update()

    def _y_for_db(self, db: float, body: QRectF) -> float:
        span = max(1.0, -self.floor_db)
        value = max(0.0, min(1.0, (db - self.floor_db) / span))
        return body.bottom() - body.height() * value

    def paint_body(self, painter: QPainter, body: QRectF):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.colours['body'])
        painter.drawRoundedRect(body, 4, 4)

        if not self.levels:
            return

        # Берём только ту часть записи, которая видна сейчас. Раньше здесь
        # перебирался весь массив на всю ширину, поэтому масштаб менял линейку,
        # а сама огибающая оставалась прежней.
        span = self.visible_span()
        if span <= 0 or self.window <= 0:
            return
        first = max(0, int(self.view_start / self.window))
        last = min(len(self.levels), int((self.view_start + span) / self.window) + 1)
        visible = self.levels[first:last]
        if not visible:
            return

        # Столбик на пиксель: точек обычно больше, чем ширина виджета.
        columns = max(1, int(body.width()))
        per_column = len(visible) / columns
        for column in range(columns):
            # При сильном приближении на столбик приходится меньше одной точки,
            # поэтому границы считаем дробными и берём хотя бы один отсчёт.
            begin = int(column * per_column)
            end = max(begin + 1, int((column + 1) * per_column))
            chunk = visible[begin:end]
            if not chunk:
                break
            peak = max(chunk)
            x = body.left() + column
            top = self._y_for_db(peak, body)
            # Тише порога — то, что уйдёт под нож; выше — то, что останется.
            painter.setBrush(self.colours['cut'] if peak <= self.threshold_db
                             else self.colours['keep'])
            painter.drawRect(QRectF(x, top, 1.0, body.bottom() - top))

        y = self._y_for_db(self.threshold_db, body)
        painter.setPen(QPen(self.colours['cursor'], 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(body.left()), int(y), int(body.right()), int(y))

    def mousePressEvent(self, event):
        if self.state == READY and self.levels:
            self._dragging = True
            self._apply_threshold_from(event.position().y())
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._apply_threshold_from(event.position().y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def _apply_threshold_from(self, y: float):
        body = self.body_rect()
        if body.height() <= 0:
            return
        ratio = max(0.0, min(1.0, (body.bottom() - y) / body.height()))
        db = self.floor_db + ratio * (-self.floor_db)
        self.threshold_db = max(-60.0, min(-10.0, db))
        self.update()
        self.threshold_changed.emit(self.threshold_db)


class RangesTrack(TrackWidget):
    """Редактируемые отрезки: тянут мышью вместо ввода 1:20-2:35 текстом."""

    ranges_changed = pyqtSignal(list)

    # Насколько близко к краю нужно попасть, чтобы тянуть именно край.
    EDGE_GRIP_PX = 6
    # Отрезки короче этого считаем случайным щелчком и выбрасываем.
    MIN_RANGE_SECONDS = 0.2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.selected: Optional[int] = None
        self._drag_mode: Optional[str] = None
        self._drag_index: Optional[int] = None
        self._drag_anchor = 0.0

    # --- взаимодействие -------------------------------------------------
    def _hit_test(self, x: float):
        """Что под курсором: край отрезка, его тело или пустое место."""
        grip = abs(self.time_for_x(self.EDGE_GRIP_PX) - self.time_for_x(0))
        for index, (start, end) in enumerate(self.segments):
            seconds = self.time_for_x(x)
            if abs(seconds - start) <= grip:
                return index, 'left'
            if abs(seconds - end) <= grip:
                return index, 'right'
            if start < seconds < end:
                return index, 'body'
        return None, None

    def mousePressEvent(self, event):
        if self.state != READY or self.duration <= 0:
            return
        x = event.position().x()
        index, part = self._hit_test(x)
        seconds = self.time_for_x(x)

        if index is None:
            # Пустое место — начинаем новый отрезок.
            self.segments.append((seconds, seconds))
            self.selected = len(self.segments) - 1
            self._drag_index = self.selected
            self._drag_mode = 'right'
        else:
            self.selected = index
            self._drag_index = index
            self._drag_mode = part
            self._drag_anchor = seconds
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag_mode is None or self._drag_index is None:
            return
        seconds = self.time_for_x(event.position().x())
        start, end = self.segments[self._drag_index]

        if self._drag_mode == 'left':
            start = min(seconds, end)
        elif self._drag_mode == 'right':
            end = max(seconds, start)
        else:
            shift = seconds - self._drag_anchor
            width = end - start
            start = max(0.0, min(self.duration - width, start + shift))
            end = start + width
            self._drag_anchor = seconds

        self.segments[self._drag_index] = (max(0.0, start), min(self.duration, end))
        self.update()

    def mouseReleaseEvent(self, event):
        if self._drag_mode is None:
            return
        self._drag_mode = None
        self._drag_index = None
        self._normalise()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.selected is not None and 0 <= self.selected < len(self.segments):
                del self.segments[self.selected]
                self.selected = None
                self._normalise()
                return
        super().keyPressEvent(event)

    def _normalise(self):
        """Выбросить случайные щелчки, упорядочить и слить пересечения."""
        kept = [(start, end) for start, end in self.segments
                if end - start >= self.MIN_RANGE_SECONDS]
        kept.sort()

        merged = []
        for start, end in kept:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        self.segments = merged
        self.selected = None
        self.update()
        self.ranges_changed.emit(list(self.segments))

    def set_ranges(self, ranges: List[Tuple[float, float]]):
        self.segments = list(ranges)
        self.update()

    # --- отрисовка ------------------------------------------------------
    def paint_body(self, painter: QPainter, body: QRectF):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.colours['body'])
        painter.drawRoundedRect(body, 4, 4)

        if not self.segments:
            painter.setPen(self.colours['muted'])
            font = QFont(painter.font())
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(body, Qt.AlignmentFlag.AlignCenter,
                             'Протяните мышью, чтобы отметить участок')
            return

        # Отрезки здесь — то, что будет обработано, поэтому цвет акцентный,
        # а не коралловый: коралловым на других дорожках помечено удаляемое.
        for index, (start, end) in enumerate(self.segments):
            left = self.x_for_time(start)
            width = max(2.0, self.x_for_time(end) - left)
            rect = QRectF(left, body.top() + 3, width, body.height() - 6)
            fill = QColor(self.colours['keep'])
            fill.setAlpha(200 if index == self.selected else 150)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 3, 3)
            # Края подчёркнуты: за них тянут.
            painter.setPen(QPen(self.colours['keep'], 2))
            painter.drawLine(int(rect.left()), int(rect.top()),
                             int(rect.left()), int(rect.bottom()))
            painter.drawLine(int(rect.right()), int(rect.top()),
                             int(rect.right()), int(rect.bottom()))


class MarkersTrack(TrackWidget):
    """Метки-события: где заглушены слова."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(72)

    def paint_body(self, painter: QPainter, body: QRectF):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.colours['body'])
        painter.drawRoundedRect(body, 4, 4)
        # Метки узкие, поэтому расширяем до заметной ширины.
        painter.setBrush(self.colours['cut'])
        for start, end in self.segments:
            left = self.x_for_time(start)
            width = max(3.0, self.x_for_time(end) - left)
            painter.drawRoundedRect(QRectF(left, body.top() + 4, width,
                                           body.height() - 8), 2, 2)
