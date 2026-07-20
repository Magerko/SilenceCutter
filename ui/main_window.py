import os
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import (QDragEnterEvent, QDropEvent, QIcon, QPainter,
                         QColor, QFont)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QPushButton,
    QProgressBar, QLineEdit, QFileDialog, QFrame,
    QStatusBar, QMessageBox, QSizePolicy, QCheckBox,
    QDoubleSpinBox, QMenu, QTabWidget, QComboBox, QPlainTextEdit,
    QScrollArea, QApplication
)

from core.ffmpeg_worker import FFmpegWorker
from core.profanity_worker import ProfanityWorker
from core.loudness import WINDOW_SECONDS, compute_envelope, segments_below
from core import transcribe
from ui.track import LoudnessTrack, MarkersTrack, RangesTrack, BUSY, EMPTY, ERROR, READY
from ui.model_download import ModelDownloadPanel
from utils.paths import resource_path
from utils import links


# Окно применяет тёмное оформление, поэтому берётся тёмный набор иконок.
# Наборы различаются только цветом контура: один общий серый давал на светлом
# фоне 3,4:1, тогда как раздельные значения дают 8–10:1 в обеих темах.
ICON_THEME = 'dark'


class EnvelopeWorker(QThread):
    """Замер громкости файла. В основном потоке подвесил бы окно на пару секунд."""
    ready = pyqtSignal(list, float)
    failed = pyqtSignal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            levels, duration = compute_envelope(
                self.path, cancel_check=lambda: self._cancelled)
            if not self._cancelled:
                self.ready.emit(levels, duration)
        except InterruptedError:
            pass
        except Exception as error:
            self.failed.emit(str(error))


def icon(name: str) -> QIcon:
    """Иконка из набора дизайн-системы; при отсутствии файла — пустая."""
    path = resource_path(os.path.join('resources', 'icons', ICON_THEME, f'{name}.svg'))
    return QIcon(path) if os.path.exists(path) else QIcon()
from utils.file_utils import (
    is_video_file, get_video_files_from_folder,
    format_duration, get_video_duration, check_ffmpeg_available
)


class FileListWidget(QListWidget):
    """Список видео, он же зона перетаскивания.

    Раньше над списком висела отдельная рамка «перетащите сюда»: она занимала
    полтораста пикселей высоты и делала ровно то же, что теперь делает сам
    список. Пока файлов нет, подсказка рисуется прямо на пустом месте.
    """

    EMPTY_TITLE = "Перетащите видео или папки сюда"
    EMPTY_HINT = "или нажмите «Добавить файлы»"

    def __init__(self, main_window=None):
        super().__init__(main_window)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setObjectName("fileList")

    def _accepts(self, event) -> bool:
        return event.mimeData().hasUrls()

    def dragEnterEvent(self, event: QDragEnterEvent):
        # Внутреннее перетаскивание меняет порядок файлов — его не трогаем.
        if self._accepts(event):
            event.acceptProposedAction()
            self._set_active(True)
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._accepts(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._set_active(False)
        super().dragLeaveEvent(event)

    def _set_active(self, active: bool):
        self.setProperty("dragActive", "yes" if active else "no")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        if not self._accepts(event):
            super().dropEvent(event)
            return
        self._set_active(False)

        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path) and is_video_file(path):
                files.append(path)
            elif os.path.isdir(path):
                files.extend(get_video_files_from_folder(path))

        if files and self.main_window:
            self.main_window.add_files(files)
        event.acceptProposedAction()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count():
            return
        # Подсказка на пустом списке: без неё рамка выглядит просто дырой и не
        # сообщает, что в неё можно бросать файлы.
        painter = QPainter(self.viewport())
        painter.setPen(QColor(self.palette().color(self.foregroundRole())))
        area = self.viewport().rect()

        pixmap = icon('scissors').pixmap(40, 40)
        if not pixmap.isNull():
            painter.setOpacity(0.55)
            painter.drawPixmap(area.center().x() - pixmap.width() // 2,
                               area.center().y() - 52, pixmap)
            painter.setOpacity(1.0)

        # Размер шрифта берём в пикселях: стили задают его через font-size в px,
        # и тогда pointSize() возвращает -1 — прибавка к нему давала текст в
        # один пункт, то есть пару чёрточек вместо подсказки.
        font = painter.font()
        base = font.pixelSize() if font.pixelSize() > 0 else 13
        font.setPixelSize(base + 3)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(area.adjusted(0, 8, 0, 0), Qt.AlignmentFlag.AlignCenter,
                         self.EMPTY_TITLE)

        font.setPixelSize(base)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setOpacity(0.7)
        painter.drawText(area.adjusted(0, 52, 0, 0), Qt.AlignmentFlag.AlignCenter,
                         self.EMPTY_HINT)
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.files: List[str] = []
        self.output_folder: str = str(Path.home() / "Videos" / "Trimmed")
        self.worker: Optional[FFmpegWorker] = None
        self.merge_worker = None
        self.envelope_worker: Optional[EnvelopeWorker] = None

        self.init_ui()
        self.check_ffmpeg()

    def init_ui(self):
        self.setWindowTitle("SilenceCutter")
        # Минимум 1200x1000 не помещался на ноутбуках: рабочая область там
        # около 1366x730, и нижняя часть окна уезжала за экран. Подгоняемся
        # под доступное место, а содержимое кладём в прокрутку.
        available = QApplication.primaryScreen().availableGeometry()
        self.setMinimumSize(900, 560)
        # Занимаем большую часть экрана. Жёсткий потолок в 1000 px оставлял на
        # мониторе 2560x1440 половину высоты пустой, и окно приходилось тянуть
        # руками каждый запуск.
        self.resize(min(1400, int(available.width() * 0.70)),
                    max(560, int(available.height() * 0.88)))
        self.move(available.left() + (available.width() - self.width()) // 2,
                  available.top() + (available.height() - self.height()) // 2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)

        central = QWidget()
        scroll.setWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Название приложения внутри окна не пишем: система уже показывает его
        # в заголовке.
        btn_layout = QHBoxLayout()

        self.add_files_btn = QPushButton(icon('file'), " Добавить файлы")
        self.add_files_btn.clicked.connect(self.add_files_dialog)
        btn_layout.addWidget(self.add_files_btn)

        self.add_folder_btn = QPushButton(icon('folder'), " Добавить папку")
        self.add_folder_btn.clicked.connect(self.add_folder_dialog)
        btn_layout.addWidget(self.add_folder_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        files_label = QLabel("Файлы для обработки:")
        layout.addWidget(files_label)

        # Сам список и есть зона перетаскивания: отдельная рамка над ним
        # занимала полтораста пикселей высоты и делала ровно то же самое.
        self.file_list = FileListWidget(self)
        self.file_list.setMinimumHeight(220)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.file_list.model().rowsMoved.connect(self.on_rows_moved)
        layout.addWidget(self.file_list, 1)

        list_controls_layout = QHBoxLayout()
        list_controls_layout.setSpacing(8)

        self.move_up_btn = QPushButton("Вверх")
        self.move_up_btn.setMinimumWidth(70)
        self.move_up_btn.clicked.connect(self.move_item_up)
        self.move_up_btn.setToolTip("Переместить вверх")
        list_controls_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("Вниз")
        self.move_down_btn.setMinimumWidth(70)
        self.move_down_btn.clicked.connect(self.move_item_down)
        self.move_down_btn.setToolTip("Переместить вниз")
        list_controls_layout.addWidget(self.move_down_btn)

        list_controls_layout.addStretch()
        layout.addLayout(list_controls_layout)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Папка назначения:"))

        self.output_edit = QLineEdit(self.output_folder)
        self.output_edit.setReadOnly(True)
        output_layout.addWidget(self.output_edit, 1)

        self.change_output_btn = QPushButton("Изменить")
        self.change_output_btn.clicked.connect(self.change_output_folder)
        output_layout.addWidget(self.change_output_btn)

        self.open_folder_btn = QPushButton(icon('folder'), " Открыть")
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.open_folder_btn.setToolTip("Открыть папку назначения в проводнике")
        output_layout.addWidget(self.open_folder_btn)

        layout.addLayout(output_layout)

        # Список файлов и папка назначения общие для обеих задач, а настройки
        # у каждой свои — поэтому вкладки начинаются здесь.
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_silence_tab(), "Вырезать тишину")
        self.tabs.addTab(self._build_profanity_tab(), "Удалить мат")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.tabs)

        # Дорожка должна отвечать на настройки сразу, а не после запуска.
        self.noise_spin.valueChanged.connect(self.on_threshold_spin_changed)
        self.min_duration_spin.valueChanged.connect(self.refresh_track_segments)
        self.file_list.currentRowChanged.connect(self.on_file_selected)

        self._build_progress_and_actions(layout)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово. Добавьте видео для обработки.")

    def _build_silence_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Дорожка стоит выше настроек: она объясняет, что делает порог, и
        # смотреть на неё нужно раньше, чем крутить ползунок.
        self.track = LoudnessTrack()
        self.track.set_state(EMPTY, 'Выберите файл в списке, чтобы увидеть громкость')
        self.track.threshold_changed.connect(self.on_track_threshold)
        layout.addWidget(self.track)

        self.track_summary = QLabel(
            'Бирюзовым — что останется, коралловым — что вырежется. '
            'Порог можно тянуть прямо по дорожке.')
        self.track_summary.setWordWrap(True)
        self.track_summary.setStyleSheet('background: transparent; color: #868c96;')
        layout.addWidget(self.track_summary)

        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(12)

        noise_label = QLabel("Порог тишины:")
        noise_label.setStyleSheet("background: transparent;")
        settings_layout.addWidget(noise_label)

        self.noise_spin = QDoubleSpinBox()
        self.noise_spin.setRange(-60, -10)
        self.noise_spin.setValue(-50)
        self.noise_spin.setSuffix(" dB")
        self.noise_spin.setSingleStep(5)
        self.noise_spin.setFixedWidth(90)
        self.noise_spin.setToolTip("Порог громкости для определения тишины\n-50 dB — только полная тишина (безопасно)\n-30 dB — агрессивнее, режет больше")
        settings_layout.addWidget(self.noise_spin)

        min_dur_label = QLabel("Мин. длительность:")
        min_dur_label.setStyleSheet("background: transparent;")
        settings_layout.addWidget(min_dur_label)

        self.min_duration_spin = QDoubleSpinBox()
        self.min_duration_spin.setRange(0.1, 5.0)
        self.min_duration_spin.setValue(1.0)
        self.min_duration_spin.setSuffix(" сек")
        self.min_duration_spin.setSingleStep(0.1)
        self.min_duration_spin.setFixedWidth(90)
        self.min_duration_spin.setToolTip("Минимальная длительность тишины для обнаружения\nКороткие паузы < этого значения игнорируются")
        settings_layout.addWidget(self.min_duration_spin)

        self.remove_internal_cb = QCheckBox("Удалять паузы >=")
        self.remove_internal_cb.setStyleSheet("background: transparent;")
        self.remove_internal_cb.toggled.connect(self.on_internal_toggle)
        settings_layout.addWidget(self.remove_internal_cb)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.5, 30.0)
        self.threshold_spin.setValue(2.0)
        self.threshold_spin.setSuffix(" сек")
        self.threshold_spin.setSingleStep(0.5)
        self.threshold_spin.setEnabled(False)
        self.threshold_spin.setFixedWidth(80)
        self.threshold_spin.setToolTip("Паузы короче этого значения не вырезаются")
        settings_layout.addWidget(self.threshold_spin)

        self.merge_after_cb = QCheckBox("Склеить после")
        self.merge_after_cb.setStyleSheet("background: transparent;")
        self.merge_after_cb.setToolTip("После обрезки всех видео — склеить их в один файл")
        settings_layout.addWidget(self.merge_after_cb)

        settings_layout.addStretch()
        layout.addLayout(settings_layout)

        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        self.precise_cut_cb = QCheckBox("Точная обрезка (перекодирование)")
        self.precise_cut_cb.setStyleSheet("background: transparent;")
        self.precise_cut_cb.setChecked(True)
        self.precise_cut_cb.setToolTip("Включено: точные границы, но медленнее\nВыключено: быстро, но возможны глюки в начале")
        options_layout.addWidget(self.precise_cut_cb)

        options_layout.addStretch()

        layout.addLayout(options_layout)
        layout.addStretch()
        return tab

    def _build_profanity_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        explanation = QLabel(
            "Находит нецензурные слова в речи и заглушает их. "
            "Видео не перекодируется — меняется только звук."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("background: transparent;")
        layout.addWidget(explanation)

        scope_layout = QHBoxLayout()
        scope_layout.setSpacing(12)
        scope_label = QLabel("Обрабатывать:")
        scope_label.setStyleSheet("background: transparent;")
        scope_layout.addWidget(scope_label)

        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Всё видео", "all")
        self.scope_combo.addItem("Только указанные участки", "ranges")
        self.scope_combo.currentIndexChanged.connect(self.on_scope_changed)
        scope_layout.addWidget(self.scope_combo)

        self.categories_cb = QCheckBox("Также грубые слова")
        self.categories_cb.setStyleSheet("background: transparent;")
        self.categories_cb.setToolTip(
            "Помимо мата — бранная лексика вроде «говно», «сука»")
        scope_layout.addWidget(self.categories_cb)

        scope_layout.addStretch()
        layout.addLayout(scope_layout)

        self.ranges_widget = QWidget()
        ranges_layout = QVBoxLayout(self.ranges_widget)
        ranges_layout.setContentsMargins(0, 0, 0, 0)

        # Участки отмечают мышью, а не набирают текстом: положение на
        # длительности видно сразу, и промахнуться в формате невозможно.
        self.ranges_track = RangesTrack()
        self.ranges_track.set_state(EMPTY, 'Выберите файл в списке, чтобы отметить участки')
        self.ranges_track.ranges_changed.connect(self.on_ranges_changed)
        ranges_layout.addWidget(self.ranges_track)

        self.ranges_summary = QLabel(
            'Протяните мышью по дорожке, чтобы отметить участок. '
            'Края можно двигать, сам участок — перетаскивать, '
            'выделенный удаляется клавишей Delete.')
        self.ranges_summary.setWordWrap(True)
        self.ranges_summary.setStyleSheet('background: transparent; color: #868c96;')
        ranges_layout.addWidget(self.ranges_summary)

        self.ranges_widget.setVisible(False)
        layout.addWidget(self.ranges_widget)

        # Модель качается при первом запуске распознавания; пока её нет,
        # человек должен видеть что происходит, а не гадать.
        self.model_status = QLabel()
        self.model_status.setWordWrap(True)
        self.model_status.setStyleSheet("background: transparent;")
        layout.addWidget(self.model_status)

        self.model_panel = ModelDownloadPanel()
        self.model_panel.cancel_requested.connect(self.cancel_processing)
        layout.addWidget(self.model_panel)

        # Дорожка показывает, где по ролику разбросаны заглушения, — по списку
        # времён это не читается. Подтверждения перед обработкой нет, поэтому
        # увидеть картину целиком человеку нужно тем более.
        self.report_track = MarkersTrack()
        self.report_track.set_state(EMPTY, 'Здесь будут отмечены заглушённые места')
        layout.addWidget(self.report_track)

        self.profanity_report = QPlainTextEdit()
        self.profanity_report.setReadOnly(True)
        self.profanity_report.setPlaceholderText(
            "После обработки здесь будет список заглушённых слов с их временем.")
        layout.addWidget(self.profanity_report, 1)

        self._refresh_model_status()
        return tab

    def _build_progress_and_actions(self, layout):
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(8)

        self.total_progress_label = QLabel("Общий прогресс:")
        progress_layout.addWidget(self.total_progress_label)

        self.total_progress = QProgressBar()
        self.total_progress.setValue(0)
        progress_layout.addWidget(self.total_progress)

        self.file_progress_label = QLabel("Текущий файл:")
        progress_layout.addWidget(self.file_progress_label)

        self.file_progress = QProgressBar()
        self.file_progress.setObjectName("fileProgress")
        self.file_progress.setValue(0)
        progress_layout.addWidget(self.file_progress)

        layout.addLayout(progress_layout)

        action_layout = QHBoxLayout()

        self.clear_btn = QPushButton(icon('delete'), " Очистить")
        self.clear_btn.clicked.connect(self.clear_files)
        action_layout.addWidget(self.clear_btn)

        action_layout.addStretch()

        self.cancel_btn = QPushButton(icon('close'), " Отменить")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.hide()
        action_layout.addWidget(self.cancel_btn)

        self.process_btn = QPushButton(icon('play'), " Обработать все")
        self.process_btn.setObjectName("primaryButton")
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)
        self.process_btn.setToolTip(
            "Выполняет действие открытой вкладки: вырезать тишину или удалить мат.")
        action_layout.addWidget(self.process_btn)

        layout.addLayout(action_layout)

        self.links_label = QLabel(
            f'Больше программ в Telegram-канале: '
            f'<a href="{links.TELEGRAM}">@magerdev1</a>'
            f' · <a href="{links.DONATE}">поддержать</a>'
            f' · <a href="{links.DONATE_UAH}">в гривнах</a>')
        self.links_label.setTextFormat(Qt.TextFormat.RichText)
        self.links_label.setOpenExternalLinks(True)
        self.links_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.links_label.setStyleSheet('background: transparent; color: #868c96;')
        layout.addWidget(self.links_label)

    def on_tab_changed(self, index: int):
        is_profanity = index == 1
        self.process_btn.setText(
            " Удалить мат" if is_profanity else " Обработать все")
        if is_profanity:
            self._refresh_model_status()

    def on_scope_changed(self):
        self.ranges_widget.setVisible(self.scope_combo.currentData() == "ranges")

    def _refresh_model_status(self):
        if transcribe.is_model_ready(transcribe.DEFAULT_MODEL):
            self.model_status.setText("Модель распознавания готова к работе.")
            return
        size_mb = transcribe.MODEL_SIZES_MB.get(transcribe.DEFAULT_MODEL, 0)
        self.model_status.setText(
            f"Модель распознавания ещё не загружена — около {size_mb / 1024:.1f} ГБ. "
            "Она скачается один раз, при первом запуске, и останется на компьютере."
        )

    def parse_ranges(self) -> List[Tuple[float, float]]:
        """Отмеченные участки. Пустой список означает всё видео."""
        if self.scope_combo.currentData() != "ranges":
            return []
        return list(self.ranges_track.segments)

    def on_ranges_changed(self, ranges: list):
        if not ranges:
            self.ranges_summary.setText(
                'Протяните мышью по дорожке, чтобы отметить участок. '
                'Края можно двигать, сам участок — перетаскивать, '
                'выделенный удаляется клавишей Delete.')
            return

        def as_time(seconds: float) -> str:
            return f'{int(seconds) // 60}:{int(seconds) % 60:02d}'

        total = sum(end - start for start, end in ranges)
        listed = ', '.join(f'{as_time(s)}–{as_time(e)}' for s, e in ranges[:4])
        if len(ranges) > 4:
            listed += f' и ещё {len(ranges) - 4}'
        self.ranges_summary.setText(
            f'Отмечено участков: {len(ranges)}, всего {as_time(total)} — {listed}')

    # --- дорожка громкости ------------------------------------------------
    def on_file_selected(self, row: int):
        if 0 <= row < len(self.files):
            self.show_track_for(self.files[row])
        else:
            self.track.set_state(EMPTY, 'Выберите файл в списке, чтобы увидеть громкость')

    def show_track_for(self, path: str):
        """Замерить громкость выбранного файла и показать её на дорожке."""
        if getattr(self, 'envelope_worker', None) is not None:
            self.envelope_worker.cancel()
            self.envelope_worker.wait(3000)

        self.track.set_state(BUSY, 'Анализ громкости...')
        self.track.set_progress(0)
        self.track_summary.setText(f'Анализ: {Path(path).name}')

        self.envelope_worker = EnvelopeWorker(path, self)
        self.envelope_worker.ready.connect(self.on_envelope_ready)
        self.envelope_worker.failed.connect(self.on_envelope_failed)
        self.envelope_worker.start()

    def on_envelope_ready(self, levels: list, duration: float):
        if not levels:
            self.on_envelope_failed('В файле нет звуковой дорожки')
            return
        self.track.set_envelope(levels, duration, WINDOW_SECONDS)
        self.track.set_threshold(self.noise_spin.value())
        self.track.set_state(READY)
        self.refresh_track_segments()

        # Участки для антимата размечаются по той же длительности.
        self.ranges_track.set_duration(duration)
        self.ranges_track.set_state(READY)

    def on_envelope_failed(self, message: str):
        self.track.set_state(ERROR, message)
        self.track_summary.setText(message)

    def on_track_threshold(self, db: float):
        """Порог потянули по дорожке — ползунок должен показать то же значение."""
        self.noise_spin.blockSignals(True)
        self.noise_spin.setValue(round(db))
        self.noise_spin.blockSignals(False)
        self.refresh_track_segments()

    def on_threshold_spin_changed(self):
        self.track.set_threshold(self.noise_spin.value())
        self.refresh_track_segments()

    def refresh_track_segments(self):
        """Пересчитать, что уйдёт под нож, и подписать это словами."""
        if self.track.state != READY or not self.track.levels:
            return
        cut = segments_below(self.track.levels, self.noise_spin.value(),
                             WINDOW_SECONDS, self.min_duration_spin.value())
        self.track.set_segments(cut)

        total = self.track.duration
        removed = sum(end - start for start, end in cut)
        kept = max(0.0, total - removed)

        def as_time(seconds: float) -> str:
            return f'{int(seconds) // 60}:{int(seconds) % 60:02d}'

        if removed >= total - 0.5:
            # Порог выше уровня речи: под нож уходит вся запись.
            self.track_summary.setText(
                f'При этом пороге вырежется всё — {as_time(total)} из {as_time(total)}. '
                'Порог выше уровня речи, его нужно понизить.')
            return
        self.track_summary.setText(
            f'Останется {as_time(kept)} из {as_time(total)}, '
            f'вырежется {as_time(removed)} — участков: {len(cut)}')

    def check_ffmpeg(self):
        available, message = check_ffmpeg_available()
        if not available:
            QMessageBox.critical(
                self,
                "FFMPEG не найден",
                f"Для работы приложения требуется FFMPEG.\n\n{message}\n\n"
                "Установите FFMPEG и добавьте его в PATH."
            )

    def add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите видео файлы",
            "",
            "Видео файлы (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.mpeg *.mpg);;Все файлы (*.*)"
        )
        if files:
            self.add_files(files)

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с видео"
        )
        if folder:
            files = get_video_files_from_folder(folder)
            if files:
                self.add_files(files)
            else:
                QMessageBox.information(
                    self,
                    "Нет видео",
                    "В выбранной папке не найдено видео файлов."
                )

    def add_files(self, files: List[str]):
        added = 0
        for file_path in files:
            if file_path not in self.files:
                self.files.append(file_path)
                self.add_file_to_list(file_path)
                added += 1

        self.update_ui_state()
        if added > 0:
            self.status_bar.showMessage(f"Добавлено файлов: {added}. Всего: {len(self.files)}")

    def add_file_to_list(self, file_path: str):
        filename = Path(file_path).name
        duration = get_video_duration(file_path)
        duration_str = format_duration(duration)

        item = QListWidgetItem(f"○  {filename}    [{duration_str}]")
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        item.setToolTip(file_path)
        self.file_list.addItem(item)

    def change_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения",
            self.output_folder
        )
        if folder:
            self.output_folder = folder
            self.output_edit.setText(folder)

    def open_output_folder(self):
        os.makedirs(self.output_folder, exist_ok=True)
        if os.name == 'nt':
            os.startfile(self.output_folder)
        else:
            import subprocess
            subprocess.run(['xdg-open', self.output_folder])

    def show_context_menu(self, position):
        selected = self.file_list.selectedItems()
        if not selected:
            return

        menu = QMenu(self)

        remove_action = menu.addAction(icon('delete'), "Удалить из списка")
        menu.addSeparator()
        open_folder_action = menu.addAction(icon('folder'), "Открыть расположение файла")

        action = menu.exec(self.file_list.mapToGlobal(position))

        if action == remove_action:
            self.remove_selected_files()
        elif action == open_folder_action:
            if selected:
                file_path = selected[0].data(Qt.ItemDataRole.UserRole)
                folder = str(Path(file_path).parent)
                if os.name == 'nt':
                    os.startfile(folder)
                else:
                    import subprocess
                    subprocess.run(['xdg-open', folder])

    def remove_selected_files(self):
        selected = self.file_list.selectedItems()
        for item in selected:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path in self.files:
                self.files.remove(file_path)
            row = self.file_list.row(item)
            self.file_list.takeItem(row)

        self.update_ui_state()
        self.status_bar.showMessage(f"Удалено: {len(selected)}. Осталось: {len(self.files)}")

    def on_rows_moved(self):
        self.sync_files_from_list()

    def sync_files_from_list(self):
        self.files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path:
                self.files.append(file_path)

    def move_item_up(self):
        current_row = self.file_list.currentRow()
        if current_row > 0:
            item = self.file_list.takeItem(current_row)
            self.file_list.insertItem(current_row - 1, item)
            self.file_list.setCurrentRow(current_row - 1)
            self.sync_files_from_list()

    def move_item_down(self):
        current_row = self.file_list.currentRow()
        if current_row < self.file_list.count() - 1:
            item = self.file_list.takeItem(current_row)
            self.file_list.insertItem(current_row + 1, item)
            self.file_list.setCurrentRow(current_row + 1)
            self.sync_files_from_list()

    def on_internal_toggle(self, checked: bool):
        self.threshold_spin.setEnabled(checked)

    def clear_files(self):
        self.files.clear()
        self.file_list.clear()
        self.total_progress.setValue(0)
        self.file_progress.setValue(0)
        self.update_ui_state()
        self.status_bar.showMessage("Список очищен")

    def update_ui_state(self):
        has_files = len(self.files) > 0
        self.process_btn.setEnabled(has_files and not self.is_processing())
        self.clear_btn.setEnabled(has_files and not self.is_processing())

    def is_processing(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def start_processing(self):
        if not self.files:
            return

        os.makedirs(self.output_folder, exist_ok=True)

        self.total_progress.setValue(0)
        self.file_progress.setValue(0)

        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            text = item.text()
            if text.startswith(("○", "✓", "⏳", "✗")):
                text = "○" + text[1:]
                item.setText(text)

        if self.tabs.currentIndex() == 1:
            try:
                ranges = self.parse_ranges()
            except ValueError as error:
                QMessageBox.warning(self, "Проверьте участки времени", str(error))
                return
            if self.scope_combo.currentData() == "ranges" and not ranges:
                QMessageBox.warning(
                    self, "Участки не указаны",
                    "Выбрана обработка отдельных участков, но ни один не задан.")
                return
            self.worker = self._make_profanity_worker(ranges)
        else:
            self.worker = FFmpegWorker(self)
            self.worker.set_files(self.files, self.output_folder)
            self.worker.set_options(
                self.noise_spin.value(),
                self.min_duration_spin.value(),
                self.remove_internal_cb.isChecked(),
                self.threshold_spin.value(),
                self.precise_cut_cb.isChecked()
            )
            self.worker.progress_total.connect(self.on_progress_total)
            self.worker.progress_file.connect(self.on_progress_file)

        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_completed.connect(self.on_file_completed)
        self.worker.all_completed.connect(self.on_all_completed)
        self.worker.log_message.connect(self.on_log_message)

        self.process_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.show()
        self.status_bar.showMessage("Обработка...")

        self.worker.start()

    def _make_profanity_worker(self, ranges) -> ProfanityWorker:
        worker = ProfanityWorker(self)
        worker.set_files(self.files, self.output_folder)
        categories = ["strong", "rude"] if self.categories_cb.isChecked() else ["strong"]
        worker.set_options(transcribe.DEFAULT_MODEL, categories,
                           dual_language=True, ranges=ranges)

        worker.progress.connect(self.on_profanity_progress)
        worker.model_download_started.connect(self.on_model_download_started)
        worker.model_progress.connect(self.on_model_progress)
        worker.report.connect(self.on_profanity_report)

        self.profanity_report.clear()
        return worker

    def on_profanity_progress(self, percent: int, message: str):
        self.file_progress.setValue(percent)
        self.file_progress_label.setText(message)

    def on_model_download_started(self, model_name: str, size_mb: float):
        self.model_status.setText('')
        self.model_panel.start(model_name, size_mb)
        self.status_bar.showMessage("Скачивание модели распознавания...")

    def on_model_progress(self, percent: int, done_mb: float, total_mb: float):
        self.model_panel.update_progress(percent, done_mb, total_mb)
        if percent >= 100:
            self.model_panel.finish()
            self._refresh_model_status()

    def on_profanity_report(self, filename: str, duration: float, muted: list):
        self.report_track.set_duration(duration)
        self.report_track.set_segments([(start, end) for start, end, _ in muted])
        self.report_track.set_state(READY)

        if not muted:
            self.report_track.set_state(EMPTY, f'{filename}: мат не найден')
            self.profanity_report.appendPlainText(
                f"{filename}: мат не найден, файл не изменён.")
            return

        self.profanity_report.appendPlainText(f"{filename}: заглушено {len(muted)}")
        for start, end, word in muted:
            minutes, seconds = divmod(int(start), 60)
            self.profanity_report.appendPlainText(
                f"    {minutes:02d}:{seconds:02d}  «{word}»  ({end - start:.2f} с)")

    def cancel_processing(self):
        if self.worker:
            self.worker.cancel()
            self.status_bar.showMessage("Отмена...")

    def on_progress_total(self, current: int, total: int):
        progress = int((current / total) * 100) if total > 0 else 0
        self.total_progress.setValue(progress)
        self.total_progress_label.setText(f"Общий прогресс: {current}/{total}")

    def on_progress_file(self, percent: int, filename: str):
        self.file_progress.setValue(percent)
        self.file_progress_label.setText(f"Текущий файл: {filename}")

    def on_file_started(self, filename: str):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if filename in item.text():
                text = item.text()
                if text.startswith("○"):
                    text = "⏳" + text[1:]
                    item.setText(text)
                break

        self.status_bar.showMessage(f"Обработка: {filename}")

    def on_file_completed(self, filename: str, success: bool, message: str):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if filename in item.text():
                text = item.text()
                if text.startswith("⏳"):
                    icon = "✓" if success else "✗"
                    text = icon + text[1:]
                    item.setText(text)
                    if message:
                        item.setToolTip(f"{item.toolTip()}\n{message}")
                break

        if not success and message:
            self.status_bar.showMessage(f"Ошибка: {message[:100]}")

    def on_all_completed(self, successful: int, failed: int):
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.hide()

        self.total_progress.setValue(100)

        msg = f"Завершено! Успешно: {successful}"
        if failed > 0:
            msg += f", Ошибок: {failed}"
        self.status_bar.showMessage(msg)

        if self.merge_after_cb.isChecked() and successful >= 2:
            self.start_merge_after_processing()
        else:
            self.process_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)

            if successful > 0:
                QMessageBox.information(
                    self,
                    "Обработка завершена",
                    f"Успешно обработано: {successful} файлов\n"
                    f"Ошибок: {failed}\n\n"
                    f"Результаты сохранены в:\n{self.output_folder}"
                )

    def start_merge_after_processing(self):
        from utils.file_utils import get_output_filename

        trimmed_files = []
        for file_path in self.files:
            output_path = get_output_filename(file_path, self.output_folder)
            if os.path.exists(output_path):
                trimmed_files.append(output_path)
            elif os.path.exists(file_path):
                trimmed_files.append(file_path)

        if len(trimmed_files) < 2:
            self.status_bar.showMessage("Недостаточно файлов для склейки")
            self.process_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            return

        merged_path = str(Path(self.output_folder) / "merged.mp4")
        counter = 1
        while os.path.exists(merged_path):
            merged_path = str(Path(self.output_folder) / f"merged_{counter}.mp4")
            counter += 1

        self.status_bar.showMessage("Склейка видео...")

        from core.ffmpeg_worker import MergeWorker
        self.merge_worker = MergeWorker(self)
        self.merge_worker.set_files(trimmed_files, merged_path)
        self.merge_worker.progress.connect(self.on_merge_progress)
        self.merge_worker.finished_signal.connect(self.on_merge_finished)
        self.merge_worker.start()

    def on_merge_progress(self, percent: int, message: str):
        self.file_progress.setValue(percent)
        self.status_bar.showMessage(message)

    def on_merge_finished(self, success: bool, message: str):
        self.process_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.file_progress.setValue(100 if success else 0)

        if success:
            QMessageBox.information(self, "Готово", f"Обработка и склейка завершены!\n\n{message}")
        else:
            QMessageBox.critical(self, "Ошибка склейки", message)

        self.status_bar.showMessage("Готово" if success else "Ошибка")

    def on_log_message(self, message: str):
        self.status_bar.showMessage(message)

    def closeEvent(self, event):
        # A QThread still running when its owner is destroyed takes the whole
        # process down, which in a windowed build looks like a silent crash.
        for worker in (self.worker, self.merge_worker, self.envelope_worker):
            if worker is None or not worker.isRunning():
                continue
            worker.cancel()
            if not worker.wait(10000):
                worker.terminate()
                worker.wait()
        event.accept()
