############################################

# PROJECT DEVELOPER: EMMANUEL GYIMAH ANNOR

#############################################

# region Libraries import
import sys
import webbrowser
import os
import subprocess
import time
import re
from threading import Thread, Timer
import copy
import requests
import json
from collections import deque

# region Third Parties import
from PySide6.QtWidgets import QApplication, QMainWindow
from ui.ui_main import Ui_MainWindow  
from ui.table import DownloadTable    
from ui.setting_dialog import SettingsWindow

from modules.video import (Video, check_ffmpeg, download_ffmpeg, get_ytdl_options)
from modules.utils import (size_format, validate_file_name, compare_versions, 
    log, delete_file, time_format, truncate, 
    notify, run_command, handle_exceptions)
from modules import config, brain, setting, video, update, startup
from modules.downloaditem import DownloadItem

os.environ["QT_FONT_DPI"] = "96"  # FIX Problem for High DPI and Scale above 100%


widgets = None

# region Main Downloader UI
class DownloadManagerUI(QMainWindow):
    def __init__(self, d_list):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121212;
            }
            QLabel, QPushButton {
                color: white;
                font-size: 13px;
                font-family: 'Segoe UI';
            }
            QPushButton {
                padding: 6px 12px;
                border: none;
                background-color: transparent;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #1f1f1f;
            }
            QFrame#TopFrame {
                background-color: transparent;
            }
            QMenuBar {
                background: qlineargradient(x1:1, y1:0, x2:0, y2:0,
                    stop: 0 #00C853, stop: 1 #003d1f);
                color: white;
                font-size: 13px;
            }
            QMenuBar::item {
                padding: 6px 18px;
                background: transparent;
            }
            QMenuBar::item:selected {
                background: rgba(255,255,255,0.1);
            }
            QMenu {
                background-color: #1f1f1f;
                color: white;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #333;
            }
            QFrame#SidebarFrame {
                background-color: #121212;
                padding: 20px 10px;
            }
            QFrame#ToolbarFrame {
                background-color: #1a1a1a;
                padding: 10px 20px;
            }
            QFrame#TableFrame {
                background-color: #1e1e1e;
                padding: 10px;
            }
            QTableWidget {
                background-color: #1f1f1f;
                border: none;
                color: white;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                padding: 8px;
                border: none;
            }
            QFrame#StatusFrame {
                background-color: #1a1a1a;
            }
            QLabel {
                font-size: 11px;
                color: #cccccc;
            }

        """)

        # Global widgets
        global widgets
        widgets = self.ui
        global widgets_settings
        widgets_settings = SettingsWindow(self)


        # init parameters
        self.d = DownloadItem() # current download_item

        # Setup YouTube thread and connect signals
        self.yt_thread = None


        # download windows
        self.download_windows = {}  # dict that holds Download_Window() objects --> {d.id: Download_Window()}

        # url
        self.url_timer = None  # usage: Timer(0.5, self.refresh_headers, args=[self.d.url])
        self.bad_headers = [0, range(400, 404), range(405, 418), range(500, 506)]  # response codes

        # youtube specific
        # download
        self.pending = deque()
        self.disabled = True  # for download button
        

        # widgets.toolbar_buttons["Add URL"].clicked.connect(self.retry)
        widgets.toolbar_buttons["Settings"].clicked.connect(self.open_settings)

        widgets_settings.language_combo.currentText()
        widgets_settings.auto_close_cb.isChecked()
        # widgets_settings.max_conn_settings_combo.currentText()


    def retry(self):
        print("This button was clicked.")

    


    def open_settings(self):
        dialog = SettingsWindow(self)
        dialog.exec()


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = DownloadManagerUI(config.d_list)
    window.show()
    sys.exit(app.exec())







