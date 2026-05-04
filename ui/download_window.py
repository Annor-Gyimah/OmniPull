
#####################################################################################
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

#   © 2024 Emmanuel Gyimah Annor. All rights reserved.
#####################################################################################

import os
import sys
from modules import config
from modules.utils import  size_format, time_format, log

from PySide6.QtCore import QTimer, Qt, Slot, QCoreApplication, QTranslator
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QProgressBar, QPushButton,
QHBoxLayout, QWidget, QFrame, QTableWidget, QTableWidgetItem, QStyledItemDelegate, QStyle, QDialog, QTabWidget, QFormLayout)

from ui.styles import get_stylesheet
from ui.language_manager import LanguageManager


class NoFocusDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if option.state & QStyle.State_HasFocus:
            option.state = option.state ^ QStyle.State_HasFocus
        super().paint(painter, option, index)


class DownloadProgressDialog(QDialog):
    
    def __init__(self, d=None, parent=None):
        super().__init__(parent)

        self.d = d
        self.timeout = 10
        self.timer = 0
        self._progress_mode = 'determinate'
        

        self.setObjectName("DownloadProgressDialog")
        self.resize(640, 420)
        self.setMinimumSize(520, 360)
        self.setWindowModality(Qt.NonModal)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)

        # internal state for title bar
        self._filename = "Unknown file"
        self._percent = 0
        self._update_window_title()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # ========== TABS ==========
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 0)

        # --- Download status tab ---
        status_tab = QWidget()
        status_layout = QVBoxLayout(status_tab)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.setSpacing(6)

        # URL (selectable text)
        self.url_label = QLabel("")
        self.url_label.setObjectName("DownloadUrlLabel")
        self.url_label.setWordWrap(True)
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        status_layout.addWidget(self.url_label)

        # Status row
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.status_lbl = QLabel(self.tr("Status:"))
        status_row.addWidget(self.status_lbl)
        self.status_value_label = QLabel("Queued...")
        self.status_value_label.setObjectName("DownloadStatusLink")
        status_row.addWidget(self.status_value_label)
        status_row.addStretch()
        status_layout.addLayout(status_row)

        # File info grid
        info_form = QFormLayout()
        info_form.setSpacing(4)

        self.file_size_value = QLabel("0 B")
        self.downloaded_value = QLabel("0 B (0%)")
        self.transfer_rate_value = QLabel("0 KB/s")
        self.time_left_value = QLabel("calculating...")
        self.resume_capability_value = QLabel("Unknown")

        self.file_size_lbl = QLabel(self.tr("File size:"))
        self.downloaded_lbl = QLabel(self.tr("Downloaded:"))
        self.transfer_rate_lbl = QLabel(self.tr("Transfer rate:"))
        self.time_left_lbl = QLabel(self.tr("Time left:"))
        self.resume_capability_lbl = QLabel(self.tr("Resume capability:"))

        info_form.addRow(self.file_size_lbl, self.file_size_value)
        info_form.addRow(self.downloaded_lbl, self.downloaded_value)
        info_form.addRow(self.transfer_rate_lbl, self.transfer_rate_value)
        info_form.addRow(self.time_left_lbl, self.time_left_value)
        info_form.addRow(self.resume_capability_lbl, self.resume_capability_value)

        status_layout.addLayout(info_form)
        status_layout.addStretch()

        self.tabs.addTab(status_tab, self.tr("Download status"))

        # --- Speed Limiter tab (placeholder) ---
        limiter_tab = QWidget()
        limiter_layout = QVBoxLayout(limiter_tab)
        limiter_layout.setContentsMargins(8, 8, 8, 8)
        limiter_layout.addWidget(
            QLabel("Speed limiter settings will appear here (UI only for now).")
        )
        limiter_layout.addStretch()
        # self.tabs.addTab(limiter_tab, "Speed Limiter")

        # --- Options on completion tab (placeholder) ---
        completion_tab = QWidget()
        completion_layout = QVBoxLayout(completion_tab)
        completion_layout.setContentsMargins(8, 8, 8, 8)
        completion_layout.addWidget(
            QLabel("Completion options will appear here (UI only for now).")
        )
        completion_layout.addStretch()
        

        # ========== MAIN PROGRESS BAR ==========
        prog_row = QHBoxLayout()
        prog_row.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.progress_percent_label.setFixedWidth(50)

        prog_row.addWidget(self.progress_bar, 1)
        prog_row.addWidget(self.progress_percent_label)

        main_layout.addLayout(prog_row)

        # ========== BUTTON ROW ==========
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_toggle_details = QPushButton(self.tr("<< Hide details"))
        self.btn_pause = QPushButton(self.tr("Pause"))
        self.btn_cancel = QPushButton(self.tr("Cancel"))

        btn_row.addWidget(self.btn_toggle_details)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_row)

        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(sep)

        # ========== DETAILS AREA ==========
        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(6)

        
        # table for per-connection info
        self.connections_table = QTableWidget(0, 3)
        self.connections_table.setHorizontalHeaderLabels(["N.", "Downloaded", "Info"])
        self.connections_table.verticalHeader().setVisible(False)
        self.connections_table.setShowGrid(False)
        self.connections_table.horizontalHeader().setStretchLastSection(True)
        self.connections_table.horizontalHeader().setDefaultSectionSize(130)
        self.connections_table.setItemDelegate(NoFocusDelegate())

        details_layout.addWidget(self.connections_table)

        main_layout.addWidget(self.details_widget, 1)

        

        # button wiring
        self.btn_toggle_details.clicked.connect(self._toggle_details)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_pause.clicked.connect(self.pause)
        

        # Periodic refresh
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(200)

        self.current_theme = config.current_theme  # default theme 
        
        self._apply_styles()
        self.current_language = config.lang
        self.lang_manager = LanguageManager()
        self.lang_manager.apply_language(self.current_language)
        self.retrans()
        

    # ========== INTERNAL HELPERS ==========

    @property
    def progress_mode(self):
        return self._progress_mode

    @progress_mode.setter
    def progress_mode(self, mode):
        if self._progress_mode != mode:
            self.progress_bar.setFormat(mode)
            self._progress_mode = mode

    def set_progress_mode(self, mode):
        if mode == 'determinate':
            self.progress_bar.setRange(0, 100)
        else:
            self.progress_bar.setRange(0, 0)

    def _apply_styles(self):
        """Apply the stylesheet based on current theme."""
        qss = get_stylesheet(self.current_theme)
        self.setStyleSheet(qss)



    def _update_window_title(self):
        self.setWindowTitle(f"{self._percent}% {self._filename}")

    def _toggle_details(self):
        if self.details_widget.isVisible():
            self.details_widget.hide()
            self.btn_toggle_details.setText(self.tr("Show details >>"))
        else:
            self.details_widget.show()
            self.btn_toggle_details.setText(self.tr("<< Hide details"))

    
    # ========== PUBLIC API FOR BACKEND ==========
    def set_filename(self, filename: str):
        self._filename = filename or "Unknown file"
        self._update_window_title()

    def set_url(self, url: str):
        self.url_label.setText(url or "")

    def set_status(self, text: str):
        self.status_value_label.setText(text or "")

    def set_file_size(self, text: str):
        self.file_size_value.setText(text or "0 B")

    def set_resume_capability(self, text: str):
        self.resume_capability_value.setText(text or "Unknown")

    def update_progress(self):
        """
        Update main progress + basic info.
        """
        percent = self.d.progress
        downloaded_text = size_format(self.d.downloaded)
        total_text = size_format(self.d.total_size)
        speed_text = size_format(self.d.speed, '/s')
        time_left_text = time_format(self.d.time_left)
        status_text = self.d.status
        url_text = self.d.url
        resumable = self.d.resumable

        if percent > 0:
            self.set_progress_mode('determinate')
            self._percent = max(0, min(100, percent))
            self.progress_bar.setValue(self._percent)
            self.progress_percent_label.setText(f"{self._percent}%")
        else:
            self.set_progress_mode('indeterminate')     
            self.progress_percent_label.setText("0%")
        
        self.set_filename(self.d.name)
        self._update_window_title()

        if downloaded_text or total_text:
            if total_text:
                self.downloaded_value.setText(f"{downloaded_text} ({self._percent}%)")
                self.file_size_value.setText(total_text)
            else:
                self.downloaded_value.setText(downloaded_text)
        if speed_text:
            self.transfer_rate_value.setText(speed_text)
        if time_left_text:
            self.time_left_value.setText(time_left_text)
        
        if resumable:
            self.set_resume_capability('Yes')
        else:
            self.set_resume_capability('Unknown')
        
        self.set_url(url_text)
        self.set_status(status_text)
        
        # 🔹 NEW: update IDM-style connections table
        self._update_connections_table()
        
        # Auto-close / status styling
        if self.d.status in (config.Status.completed, config.Status.cancelled, config.Status.error) and config.auto_close_download_window:
            self.close()

        
    def update_connections_bar(self, percent: int):
        self.connections_bar.setValue(max(0, min(100, percent)))

    def _update_connections_table(self):
        """
        Use d.connection_stats if present.
        Each element is {"downloaded": int, "info": str}.
        If stats not present, fall back to one row showing total downloaded.
        """
        stats = getattr(self.d, "connection_stats", None)

        if isinstance(stats, list) and stats:
            rows = len(stats)
            self.connections_table.setRowCount(rows)
            for i, st in enumerate(stats):
                downloaded = int(st.get("downloaded", 0) or 0)
                info_text = st.get("info") or "Receiving data..."

                # No.
                item_no = QTableWidgetItem(str(i + 1))
                item_no.setTextAlignment(Qt.AlignCenter)
                self.connections_table.setItem(i, 0, item_no)

                # Downloaded
                item_size = QTableWidgetItem(size_format(downloaded))
                item_size.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.connections_table.setItem(i, 1, item_size)

                # Info
                self.connections_table.setItem(i, 2, QTableWidgetItem(info_text))
            return

        # Fallback: single "whole download" row
        total_downloaded = int(getattr(self.d, "downloaded", 0) or 0)
        status = getattr(self.d, "status", None)

        if total_downloaded <= 0 and status not in (
            config.Status.downloading,
            config.Status.completed,
            config.Status.cancelled,
            config.Status.error,
        ):
            self.connections_table.setRowCount(0)
            return

        self.connections_table.setRowCount(1)
        self.connections_table.setItem(0, 0, QTableWidgetItem("1"))
        self.connections_table.setItem(0, 1, QTableWidgetItem(size_format(total_downloaded)))

        if status == config.Status.downloading:
            info_text = "Receiving data..."
        elif status == config.Status.completed:
            info_text = "Completed"
        elif status == config.Status.cancelled:
            info_text = "Cancelled"
        elif status == config.Status.error:
            info_text = "Error"
        else:
            info_text = str(status) if status is not None else ""
        self.connections_table.setItem(0, 2, QTableWidgetItem(info_text))


    def pause(self):
        config.main_window_q.put(('pause_btn', ''))
        self.close()
    
    def cancel(self):
        if self.d.status not in (config.Status.error, config.Status.completed):
            self.d.status = config.Status.cancelled
        self.close()

    def hide(self):
        self.close()

    def focus(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()
        self.update_progress()

    def close(self):
        self.timer.stop()
        super().close()

    def closeEvent(self, event):
        try:
            if hasattr(self, "timer") and self.timer.isActive():
                self.timer.stop()
        except Exception as e:
            log(f"[DownloadWindow] Failed to stop timer: {e}")
        super().closeEvent(event)

    @Slot(float)
    def on_progress_changed(self, value):
        self.set_progress_mode('determinate')
        self.progress_bar.setValue(int(value))
        self.progress_percent_label.setText(f"{value:.1f}%")
    
    @Slot(str)
    def on_status_changed(self, status):
        self.set_status(status)
    


    def retrans(self):
        # Update window title and labels
        self.status_lbl.setText(self.tr("Status:"))
        self.file_size_lbl.setText(self.tr("File size:"))
        self.downloaded_lbl.setText(self.tr("Downloaded:"))
        self.transfer_rate_lbl.setText(self.tr("Transfer rate:"))
        self.time_left_lbl.setText(self.tr("Time left:"))
        self.resume_capability_lbl.setText(self.tr("Resume capability:"))

        self.tabs.setTabText(0, self.tr("Download status"))
        self.btn_toggle_details.setText(self.tr("<< Hide details"))
        self.btn_toggle_details.setText(self.tr("Show details >>"))
        self.btn_pause.setText(self.tr("Pause"))
        self.btn_cancel.setText(self.tr("Cancel"))


        

