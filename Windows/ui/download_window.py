
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

from modules import config
from modules.utils import truncate, size_format, size_splitter, time_format, log

from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, 
QHBoxLayout, QWidget, QFrame)


# Modernized DownloadWindow UI to match dark theme and new style
class DownloadWindow(QWidget):
    def __init__(self, d=None):
        super().__init__()
        self.setStyleSheet("""
            QWidget {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
                border-radius: 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
            QProgressBar {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                color: white;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #00C853;
                border-radius: 4px;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #00C853;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        self.d = d
        #self.q = d.q
        self.timeout = 10
        self.timer = 0
        self._progress_mode = 'determinate'
        self.init_ui()
        self.resize(500, 330)
        self.setWindowTitle("Download Window")
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)      

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

    def init_ui(self):
        self.frame = QFrame(self)
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setSpacing(10)
        self.frame_layout.setContentsMargins(15, 15, 15, 15)

        self.out_label = QLabel(self.frame)
        self.out_label.setFixedHeight(140)
        self.out_label.setStyleSheet("font-size: 11px;")
        self.out_label.setWordWrap(True)
        self.frame_layout.addWidget(self.out_label)

        self.percent_label = QLabel(self.frame)
        self.percent_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #00C853;")
        self.percent_label.setAlignment(Qt.AlignCenter)
        self.frame_layout.addWidget(self.percent_label)

        self.progress_bar = QProgressBar(self.frame)
        self.progress_bar.setRange(0, 100)
        self.frame_layout.addWidget(self.progress_bar)

        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)

        self.status_label = QLabel(self.frame)
        self.button_layout.addWidget(self.status_label)

        self.hide_button = QPushButton('Hide', self.frame)
        self.hide_button.setStyleSheet("background-color: #2962FF; color: white;")
        self.hide_button.clicked.connect(self.hide)
        self.button_layout.addWidget(self.hide_button)

        self.cancel_button = QPushButton('Cancel', self.frame)
        self.cancel_button.setStyleSheet('background-color: #D32F2F; color: white;')
        self.cancel_button.clicked.connect(self.cancel)
        self.button_layout.addWidget(self.cancel_button)

        self.frame_layout.addLayout(self.button_layout)

        self.log_display = QTextEdit(self.frame)
        self.log_display.setReadOnly(True)
        self.log_display.setFixedHeight(60)
        self.frame_layout.addWidget(self.log_display)

        self.setLayout(self.frame_layout)
        self.setMinimumSize(700, 300)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(500)

    

    def update_gui(self):
        name = truncate(self.d.name, 50)
        out = (f"\n File: {name} \n"
            f"\n Downloaded: {size_format(self.d.downloaded)} out of {size_format(self.d.total_size)} \n"
            f"\n Speed: {size_format(self.d.speed, '/s')}  {time_format(self.d.time_left)} left \n"
            f"\n Live connections: {getattr(self.d, 'live_connections', 0)} - Remaining parts: {getattr(self.d, 'remaining_parts', 0)} \n")
        self.out_label.setText(out)

        # Use numeric progress property; treat > 0 as determinate
        try:
            prog = float(getattr(self.d, "progress", 0.0) or 0.0)
        except Exception:
            prog = 0.0

        if prog > 0.0:
            self.set_progress_mode('determinate')
            # clamp 0-100
            prog_clamped = max(0.0, min(100.0, prog))
            self.progress_bar.setValue(int(prog_clamped))
            self.percent_label.setText(f"{prog_clamped:.1f}%")
        else:
            # show indeterminate only if truly no progress
            self.set_progress_mode('indeterminate')
            # show 0.0% visually too
            self.percent_label.setText("0.0%")

        # rest unchanged...
        if self.d.status in (config.Status.completed, config.Status.cancelled, config.Status.error) and config.auto_close_download_window:
            self.close()

        if self.d.status in (config.Status.completed, config.Status.cancelled, config.Status.error):
            self.hide_button.setStyleSheet("background-color: white; color: black;")
            self.cancel_button.setText(self.tr('Done'))
            self.cancel_button.setStyleSheet('background-color: grey; color: white;')

        self.log_display.setPlainText(config.log_entry)
        self.percent_label.setStyleSheet("QLabel { color: white; }")
        self.status_label.setText(f"{self.d.status}  {self.d.i}")

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
        self.update_gui()

    def close(self):
        self.timer.stop()
        super().close()

    def closeEvent(self, event):
        try:
            if hasattr(self, "timer") and self.timer.isActive():
                self.timer.stop()
        except Exception as e:
            log(f"[DownloadWindow] Failed to stop timer: {e}")

        # try:
        #     self.disconnect()  # Only if you've connected custom signals manually
        # except Exception as e:
        #     log(f"[DownloadWindow] Failed to disconnect signals: {e}")

        super().closeEvent(event)


    # def close(self):
    #     # Safely post a close event to run in main thread
    #     QCoreApplication.postEvent(self, QEvent(QEvent.Close))
    
    @Slot(float)
    def on_progress_changed(self, value):
        self.set_progress_mode('determinate')
        self.progress_bar.setValue(int(value))
        self.percent_label.setText(f"{value:.1f}%")

    @Slot(str)
    def on_status_changed(self, status):
        self.status_label.setText(status)
        if status in ("completed", "cancelled", "error"):
            self.hide_button.setStyleSheet("background-color: white; color: black;")
            self.cancel_button.setText(self.tr('Done'))
            self.cancel_button.setStyleSheet('background-color: grey; color: white;')
            if config.auto_close_download_window:
                self.close()

    @Slot(str)
    def on_log_updated(self, text):
        self.log_display.append(text)

