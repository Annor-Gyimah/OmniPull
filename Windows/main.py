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

# region Standard Lib import
import os
import sys
import copy
import glob
import time
import json
import uuid
import gzip
import base64
import socket
import shutil
import asyncio
import hashlib
import platform
import requests
from typing import Any
from pathlib import Path
from collections import deque
from threading import Thread, Timer
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote, parse_qs, urlencode, urlunparse

# region 3rd Parties import
from PySide6 import QtGui, QtWidgets
from yt_dlp.utils import DownloadError, ExtractorError
from PySide6.QtCore import (QTimer, QPoint, QThread, Signal, Slot, QUrl, QTranslator, 
QCoreApplication, Qt, QTime, QProcess)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QLocalServer, QLocalSocket
from PySide6.QtGui import QAction, QIcon, QPixmap, QImage, QDesktopServices, QActionGroup, QKeySequence, QColor
from PySide6.QtWidgets import (QMainWindow, QApplication, QFileDialog, QMessageBox, QLineEdit,
QVBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, QHBoxLayout, QWidget, QTableWidgetItem, QDialog, 
QComboBox, QInputDialog, QMenu, QRadioButton, QButtonGroup, QScrollArea, QCheckBox, QListWidget, QListWidgetItem, QWidgetAction, QLabel)

# region UI import
from ui.ui_main import Ui_MainWindow 
from ui.about_dialog import AboutDialog
from ui.queue_dialog import QueueDialog
from ui.tray_icon import TrayIconManager
from ui.setting_dialog import SettingsWindow
from ui.download_window import DownloadWindow
from ui.schedule_dialog import ScheduleDialog
from ui.user_guide_dialog import UserGuideDialog
from ui.populate_worker import PopulateTableWorker
from ui.tutorial_window import TutorialOverlay, tutorial_steps

# region modules import

from modules.downloaditem import DownloadItem
from modules.aria2c_manager import aria2c_manager
from modules.settings_manager import SettingsManager
from modules import config, brain, setting, video, updater, setting
from modules.video import (Video, check_ffmpeg, download_ffmpeg, download_aria2c)
from modules.utils import (size_format, validate_file_name, compare_versions, compare_versions_2, log, time_format,
    notify, run_command, handle_exceptions, get_machine_id)
from modules.helper import (toolbar_buttons_state, get_msgbox_style, change_cursor, show_information,
    show_critical, show_warning, open_with_dialog_windows, safe_filename, get_ext_from_format, _best_existing, 
    _norm_title, _pick_container_from_video, _expected_paths, _extract_title_from_pattern)







os.environ["QT_FONT_DPI"] = f"{config.APP_FONT_DPI}"  # FIX Problem for High DPI and Scale above 100%


widgets = None
widgets_settings = None
widgets_about = None




class InternetChecker(QThread):
    """
    Thread for checking the internet
    """
    internet_status_changed = Signal(bool) # Define a signal to send the result back to the main thread

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_connected = False  # A flag to store the connection status

    def run(self):
        """Runs the internet check in the background."""
        url = "https://www.google.com"
        timeout = 10
        try:
            requests.get(url, timeout=timeout) # Requesting URL to check for internet connectivity
            self.is_connected = True  # Update the connection status
            self.internet_status_changed.emit(True)
        except (requests.ConnectionError, requests.Timeout):
            self.is_connected = False  # Update the connection status
            self.internet_status_changed.emit(False)


class SingleInstanceApp:
    """
    Class for only a single OmniPull app to run at a time
    """
    def __init__(self, app_id):
        self.app_id = app_id
        self.server = QLocalServer()

    def is_running(self):
        socket = QLocalSocket()
        socket.connectToServer(self.app_id)
        is_running = socket.waitForConnected(500)
        socket.close()
        return is_running

    def start_server(self):
        if not self.server.listen(self.app_id):
            QLocalServer.removeServer(self.app_id) # Clean up any leftover server instance if it wasn't closed properly
            self.server.listen(self.app_id)


    

class FileChecksum(QThread):
    """
    Thread to handle completed file checksum
    """

    checksum_computed = Signal(str, str)  # Signal(file_path, checksum)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            hasher = hashlib.sha256()
            with open(self.file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            checksum = hasher.hexdigest()
            self.checksum_computed.emit(self.file_path, checksum)
        except Exception as e:
            log(f"[Checksum] Error computing checksum: {e}", log_level=3)
            self.checksum_computed.emit(self.file_path, "Error")


class YouTubeThread(QThread):
    """
    Thread to handle YouTube video extraction and downloading.
    """
    finished = Signal(object)  # Signal when the process is complete
    progress = Signal(int)  # Signal to update progress bar (0-100%)

    def __init__(self, url: str):
        """Initialize the YouTubeThread with the URL."""
        super().__init__()
        self.url = url

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_async())
        except Exception as e:
            log(f'Unexpected error: {e}', log_level=3)
            self.finished.emit(None)
    
    async def _run_async(self):
        try:
            widgets.download_btn.setEnabled(False)
            widgets.playlist_btn.setEnabled(False)
            widgets_settings.monitor_clipboard_cb.setChecked(False)
            widgets.combo1.clear()
            widgets.combo2.clear()
            change_cursor('busy')
            log(f"[AsyncYTDL] Extracting info for URL: {self.url}", log_level=1)
            vid_info = await video.Video.extract_metadata(self.url)
              
            if vid_info.get('_type') == 'playlist':
                playlist = []
                entries = list(vid_info.get('entries', []))
                last_emit = -1  # initialize outside loop
                UPDATE_INTERVAL = 10  # Update every 10%
                
                for index, item in enumerate(entries):
                    try:
                        url = item.get('webpage_url') or item.get('url') or item.get('id')
                        if not url:
                            continue
                        
                        v = video.Video(url, vid_info=item, get_size=False)
                        playlist.append(v)
                        percent = int((index + 1) * 100 / len(entries)) # Emit the app_update signal with the result
                        if percent // UPDATE_INTERVAL > last_emit // UPDATE_INTERVAL:
                            self.progress.emit(percent)
                            last_emit = percent
                            
                    except Exception as e:
                        log(f"[AsyncYTDL] Skipping playlist item {index}: {e}", log_level=2)
                        
                self.finished.emit(playlist)
                self.progress.emit(100)


            else:
                video_obj = video.Video(self.url, vid_info=vid_info)
                self.progress.emit(50)
                await asyncio.sleep(1)  # simulate additional processing
                self.progress.emit(100)
                self.finished.emit(video_obj)

        except (DownloadError, ExtractorError) as e:
            log(f'[AsyncYTDL] yt-dlp error: {e}', log_level=3)
            self.finished.emit(None)
        except Exception as e:
            log(f'[AsyncYTDL] Error: {e}', log_level=3)
            self.finished.emit(None)
        finally:
            change_cursor('normal')
            widgets.download_btn.setEnabled(True)
            widgets_settings.monitor_clipboard_cb.setChecked(True)


    


class CheckUpdateAppThread(QThread):
    """
    Thread to check if a new version of the app is available.
    """
    app_update = Signal(bool)  # Emits True if a new version is available

    def __init__(self, remote: bool = True):
        """Initialize the thread with an option to check remotely."""
        super().__init__()
        self.remote = remote
        self.new_version_available = False
        self.new_version_description = None

    def run(self):
        """Run the thread to check for updates."""
        self.check_for_update()
        self.app_update.emit(self.new_version_available) # Emit the app_update signal with the result

    def check_for_update(self):
        """Check for a new version and update internal state."""
        change_cursor('busy') # Change cursor to busy
        current_version = config.APP_VERSION # Retrieve current version and changelog information
        try:
            info = updater.get_changelog()
            if info:
                latest_version, version_description = info
                newer_version = compare_versions(current_version, latest_version) # Compare versions
                if not newer_version or newer_version == current_version:
                    self.new_version_available = False
                else:  # newer_version == latest_version
                    self.new_version_available = True
                config.APP_LATEST_VERSION = latest_version # Update global values
                self.new_version_description = version_description
            else:
                self.new_version_available = False
                self.new_version_description = None
        
        except Exception as e:
            log(f"Error checking for updates: {e}", log_level=3)
            self.new_version_available = False
            self.new_version_description = None
            
        change_cursor('normal') # Revert cursor to normal
        setting.save_setting()

    
class UpdateThread(QThread):
    """
    Thread to perform an update and signal when it is finished.
    """
    update_finished = Signal()  # Signal to indicate that the update is finished

    def run(self):
        """Run the update process and emit the signal when finished."""
        updater.update()  # Perform the update here
        if config.confirm_update:
            self.update_finished.emit()  # Emit the signal when done


class ServerSoftwareCheckThread(QThread):
    """
    Sends machine info + software version to the server.
    Optionally includes a 'snapshot' payload.
    """
    def __init__(self, d_list=None, parent=None):
        super().__init__(parent)
        self.software_version = config.APP_VERSION
        self.machine_id = self._get_machine_id()
        self.d_list = d_list or []   

    def _get_machine_id(self):
        mid = getattr(config, "machine_id", None)
        if mid:
            return mid
        mid = get_machine_id(hashed=True)
        config.machine_id = mid
        return mid

    def _get_snapshot(self):
        """Builds optional snapshot block; return None to omit."""
        try:
            export_data = [d.get_persistent_properties() for d in self.d_list]
            return {
                "items": export_data,
                "items_count": len(export_data),
                "format": "json",
            }
        except Exception:
            return None

    def _get_machine_info(self):
        return {
            "computer_name": socket.gethostname(),
            "operating_system": getattr(config, "operating_system_info", platform.platform()),
            "software_version": self.software_version,
            "machine_id": self.machine_id,
            "snapshot": self._get_snapshot(),  # include or None
        }

    def run(self):
        try:
            url = "https://omnipull.pythonanywhere.com/api/software-update/"
            data = self._get_machine_info()
            if data.get("snapshot") is None:
                data.pop("snapshot", None)

            # simple retry for transient failures
            for attempt in range(3):
                try:
                    resp = requests.post(url, json=data, timeout=10)
                    if resp.ok:
                        upd = resp.json()
                        if upd.get("update_needed"):
                            log(f"Update required: {upd.get('new_version')}")
                        else:
                            log(f"You are up to date. Version: {self.software_version}")
                        return
                    else:
                        log(f"Error checking update status: {resp.status_code}", log_level=3)
                        return
                except requests.RequestException as e:
                    if attempt == 2:
                        raise
                    time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            log(f"Error sending software info to server: {e}", log_level=3)




class FileOpenThread(QThread):
    """
    Thread to open a file and signal errors if the file doesn't exist.
    """
    critical_signal = Signal(str, str)  # Signal to communicate with the main window

    def __init__(self, file_path: str, parent=None):
        """Initialize the thread with the file path."""
        super(FileOpenThread, self).__init__(parent)
        self.file_path = file_path

    def run(self):
        """Run the thread to open the specified file."""
        try:
            if not os.path.exists(self.file_path):
                self.critical_signal.emit('File Not Found', f"The file '{self.file_path}' could not be found or has been deleted.") # Emit the signal if the file doesn't exist
                return  # Exit the thread if the file doesn't exist

            # Opening the file
            if config.operating_system == 'Windows':
                os.startfile(self.file_path)
            elif config.operating_system == 'Linux':
                run_command(f'xdg-open "{self.file_path}"', verbose=False)
            elif config.operating_system == 'Darwin':
                run_command(f'open "{self.file_path}"', verbose=False)

        except FileNotFoundError:
            log(f"File not found: {self.file_path}", log_level=3)
            self.critical_signal.emit(
                'File Not Found', 
                f"The file '{self.file_path}' could not be found."
            )
            
        except PermissionError:
            log(f"Permission error accessing: {self.file_path}", log_level=3)
            self.critical_signal.emit(
                'Permission Error', 
                f"Permission denied while trying to access '{self.file_path}'."
            )
            
        except OSError as e:
            log(f"OS error occurred while opening file: {e}", log_level=3)
            self.critical_signal.emit(
                'OS Error', 
                f"An OS error occurred while opening the file: {e}"
            )


class LogRecorderThread(QThread):
    error_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.buffer = ''
        self.file = os.path.join(config.sett_folder, 'log.txt')
        self._stop = False  # <-- add

    # optional public API
    def stop(self):
        self._stop = True

    def run(self):
        """Continuously write log messages to file."""
        try:
            while True:
                # Exit condition: any of these triggers stop
                if self._stop or self.isInterruptionRequested() or getattr(config, "terminate", False):
                    break

                try:
                    q = config.log_recorder_q
                    for _ in range(q.qsize()):
                        self.buffer += q.get()

                    if self.buffer:
                        with open(self.file, 'a', encoding="utf-8", errors="ignore") as f:
                            f.write(self.buffer)
                            self.buffer = ''

                    self.msleep(100)

                except Exception as e:
                    self.error_signal.emit(f'Log recorder error: {e}')
                    self.msleep(100)

        finally:
            # Final flush on exit
            try:
                if self.buffer:
                    with open(self.file, 'a', encoding="utf-8", errors="ignore") as f:
                        f.write(self.buffer)
                        self.buffer = ''
            except Exception:
                pass




class MarqueeLabel(QLabel):
    """
    Class for displaying files name via the open menu action in the file menu
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.full_text = text
        self.offset = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scroll_text)
        self.setText(text)
        self.setStyleSheet("color: white;")
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def enterEvent(self, event):
        self.timer.start(100)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.timer.stop()
        self.offset = 0
        self.setText(self.full_text)
        super().leaveEvent(event)

    def scroll_text(self):
        if len(self.full_text) <= 30:
            return
        self.offset = (self.offset + 1) % len(self.full_text)
        text = self.full_text[self.offset:] + "   " + self.full_text[:self.offset]
        self.setText(text)


# region Main Downloader UI
class DownloadManagerUI(QMainWindow):
    update_gui_signal = Signal(dict)
    
    def __init__(self, d_list):
        QMainWindow.__init__(self)
        
        # Intialization 
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui_settings = SettingsWindow(self)
        self.last_schedule_check = {}  # queue_id: QTime
        self.running_queues = {}
        self.download_windows = {}
        self.background_threads = []  # 🧠 New list to track QThreads
        self.ui_queues = QueueDialog(self)
        self._remux_procs = {}  # {d.id: QProcess}
        self.ui.table.itemSelectionChanged.connect(self.update_toolbar_buttons_for_selection)

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
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
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
            QTableWidget::item:focus {
                outline: none;
                border: none;
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
            
            QMenu::item:disabled {
                color: #777777;
            }



        """)

        # Global widgets
        global widgets
        widgets = self.ui
        global widgets_settings
        
        widgets_settings = self.ui_settings
        self.setWindowTitle(config.APP_TITLE)
        self.d = DownloadItem() # current download_item
        self.yt_thread = None # Setup YouTube thread and connect signals
        self.download_windows = {}  # dict that holds Download_Window() objects --> {d.id: Download_Window()}
        self.setup()

        self.url_timer = None  # usage: Timer(0.5, self.refresh_headers, args=[self.d.url])
        self.bad_headers = [0, range(400, 404), range(405, 418), range(500, 506)]  # response codes
        self.pending = deque()
        self.disabled = True  # for download button


        # download list table
        self.d_headers = ['id', 'name', 'progress', 'speed', 'time_left', 'downloaded', 'total_size', 'status', 'i']
        self.d_list = d_list  # list of DownloadItem() objects
        self.selected_row_num = None
        self._selected_d = None

        # update
        self.new_version_available = False
        self.new_version_description = None

        # youtube specific
        self.video = None
        self.yt_id = 0  # unique id for each youtube thread
        self.playlist = []
        self.pl_title = ''
        self.pl_quality = None
        self._pl_menu = []
        self._stream_menu = []
        self.stream_menu_selection = ''

        # thumbnail
        self.current_thumbnail = None


        # Initialize and start log recorder thread
        self.log_recorder_thread = LogRecorderThread()
        self.log_recorder_thread.start()
        self.background_threads.append(self.log_recorder_thread)  # ✅ Track it

        # Setup clipboard monitoring
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.old_clipboard_data = ''

        # Initialize the PyQt run loop with a timer (to replace the PySimpleGUI event loop)
        self.run_timer = QTimer(self)
        self.run_timer.timeout.connect(self.run)
        self.run_timer.start(900)  # Runs every 500ms

        # self.retry_button_clicked = False
        self.filename_set_by_program = False

        widgets.brand.setText("Annorion - Never Cease To Amaze")
        widgets.retry_btn.clicked.connect(self.retry)
        widgets.toolbar_buttons["Resume"].clicked.connect(self.resume_btn)
        widgets.toolbar_buttons["Delete"].clicked.connect(self.delete_btn)
        widgets.toolbar_buttons["Pause"].clicked.connect(self.pause_btn)
        widgets.toolbar_buttons["Refresh"].clicked.connect(self.refresh_link_btn)
        widgets.toolbar_buttons["Stop All"].clicked.connect(self.stop_all_downloads)
        widgets.toolbar_buttons["Delete All"].clicked.connect(self.delete_all_downloads)
        widgets.toolbar_buttons["Resume All"].clicked.connect(self.resume_all_downloads)
        widgets.toolbar_buttons["Schedule All"].clicked.connect(self.schedule_all)
        widgets.toolbar_buttons["Download Window"].clicked.connect(self.download_window)
        widgets.folder_btn.clicked.connect(self.open_folder_dialog)
        widgets.folder_input.setText(config.download_folder)
        widgets.filename_input.textChanged.connect(self.on_filename_changed)
        widgets.download_btn.clicked.connect(self.on_download_button_clicked)
        widgets.playlist_btn.clicked.connect(self.download_playlist)
        # Enable custom context menu on the table widget
        widgets.table.setContextMenuPolicy(Qt.CustomContextMenu)
        widgets.table.customContextMenuRequested.connect(self.show_table_context_menu)
        widgets.log_clear_btn.clicked.connect(self.clear_log)
        

        widgets.combo2.currentTextChanged.connect(self.stream_OnChoice)

        widgets.version_value.setText(f"App Version: {config.APP_VERSION}")


        # load stored setting from disk
        os.chdir(config.current_directory)

        # load stored setting from disk
        # setting.load_setting()
        # self.d_list = setting.load_d_list()
        self.settings_manager = SettingsManager()
        self.settings_manager.load_settings()
        self.d_list = self.settings_manager.load_d_list()
        self.ui_queues.main_window = self
        
        self.tray_manager = TrayIconManager(self)

        widgets.folder_input.setText(config.download_folder)
        widgets.log_level_combo.currentTextChanged.connect(self.set_log)
        widgets.log_level_combo.setCurrentText(str(config.log_level))
    
        widgets.toolbar_buttons["Settings"].clicked.connect(self.open_settings)

        widgets.export_dl.triggered.connect(self.export_downloads_list)
        widgets.quitt.triggered.connect(self.exit_app)


        
        widgets.downloads_menu.actions()[0].triggered.connect(self.resume_all_downloads)
        widgets.downloads_menu.actions()[1].triggered.connect(self.stop_all_downloads)
        widgets.downloads_menu.actions()[2].triggered.connect(self.clear_all_completed_downloads)

        widgets.settings_action.triggered.connect(self.open_settings)

        chrome_action = widgets.browser_extension_menu.actions()[0]
        firefox_action = widgets.browser_extension_menu.actions()[1]
        edge_action = widgets.browser_extension_menu.actions()[2]

        # chrome_action.triggered.connect(lambda: self.install_browser_extension("Chrome"))
        chrome_action.setEnabled(False)  # Disable Chrome action for now
        firefox_action.triggered.connect(lambda: self.install_browser_extension("Firefox"))
        edge_action.triggered.connect(lambda: self.install_browser_extension("Edge"))

       
    
        widgets.view_menu.actions()[0].triggered.connect(self.refresh_table) 
        sort_actions = widgets.view_menu.actions()[-1].menu().actions()  # last added menu is "Sort By"
        sort_actions[0].triggered.connect(lambda: self.sort_table("status"))
        sort_actions[1].triggered.connect(lambda: self.sort_table("name"))
        sort_actions[2].triggered.connect(lambda: self.sort_table("progress"))
        # Disable the View menu if any download is in progress, otherwise enable it
        if any(d.status in [config.Status.downloading, config.Status.merging_audio, config.Status.pending, config.Status.queued] for d in self.d_list):
            widgets.view_menu.menuAction().setToolTip("Disabled while downloads are active") 
            widgets.view_menu.menuAction().setEnabled(False)
        else:
            widgets.view_menu.menuAction().setEnabled(True)

        
        widgets.open_file_menu.aboutToShow.connect(self.populate_open_menu) # Connect the Open menu to populate when shown

        self.sort_action_group = QActionGroup(self)
        self.sort_action_group.setExclusive(True)  # Only one checked at a time

        # Make actions checkable
        widgets.status_action.setCheckable(True)
        widgets.name_action.setCheckable(True)
        widgets.progress_action.setCheckable(True)

        # Add to group
        self.sort_action_group.addAction(widgets.status_action)
        self.sort_action_group.addAction(widgets.name_action)
        self.sort_action_group.addAction(widgets.progress_action)

        widgets.help_menu.actions()[0].triggered.connect(self.show_about_dialog)
        widgets.help_menu.actions()[1].triggered.connect(self.start_update)
        widgets.help_menu.actions()[2].triggered.connect(self.show_user_guide)
        widgets.help_menu.actions()[3].triggered.connect(self.show_visual_tutorial)
        widgets.help_menu.actions()[4].triggered.connect(self.open_github_issues)
        widgets.toolbar_buttons["Queues"].clicked.connect(self.show_queue_dialog)


        self.update_gui_signal.connect(self.process_gui_updates)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_for_gui_updates)
        self.update_timer.start(100)  # Check for updates every 100ms
        self.pending_updates = {}
        
        self.network_manager = QNetworkAccessManager()
        self.network_manager.finished.connect(self.on_thumbnail_downloaded)
        self.one_time, self.check_time = True, True
    
        self.translator = QTranslator() # Translator

        # Load saved language
        self.setup_context_menu_actions()
        self.current_language = config.lang
        self.apply_language(self.current_language)
        
        self.queue_combo()

        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_scheduled_queues)
        self.scheduler_timer.start(60000)  # Every 60 seconds
    

    def show_visual_tutorial(self):
        """Show a visual tutorial overlay with multiple steps."""
        overlay = TutorialOverlay(self, tutorial_steps, show_exit_button=True)
        overlay.show()



    # region Menu bar     
    def export_downloads_list(self):
        """Export downloads list to CFG file"""
        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setNameFilter("CFG Files (*.cfg)")
        file_dialog.setDefaultSuffix("cfg")
        
        if file_dialog.exec():
            save_path = file_dialog.selectedFiles()[0]
            try:
                export_data = [d.get_persistent_properties() for d in self.d_list]

                with open(save_path, "w") as f:
                    json.dump(export_data, f, indent=4)

                show_information("Export Successful", f"File saved in {save_path}", "Downloads list exported successfully.")

            except Exception as e:
                show_warning("Export Failed", f"Error: {e}")

    def exit_app(self):
        QtWidgets.QApplication.quit()
    
    def show_user_guide(self):
        dialog = UserGuideDialog(self)
        dialog.exec()

    def show_about_dialog(self):
        dialog = AboutDialog()
        dialog.exec()



    def sort_table(self, by="status"):
        """Sort the table by status, name or progress"""
        if not self.d_list:
            return

        # Perform sorting
        if by == "status":
            self.d_list.sort(key=lambda d: d.status.lower() if isinstance(d.status, str) else "", reverse=False)
            widgets.status_action.setChecked(True)
        elif by == "name":
            self.d_list.sort(key=lambda d: d.name.lower() if isinstance(d.name, str) else "", reverse=False)
            widgets.name_action.setChecked(True)
        elif by == "progress":
            self.d_list.sort(key=lambda d: d.progress if isinstance(d.progress, (int, float)) else 0, reverse=True)
            widgets.progress_action.setChecked(True)

        self.populate_table()

    def refresh_table(self):
        """Reloads the original download list without sorting."""
        self.d_list = self.settings_manager.load_d_list()
        self.populate_table()

    # --- Extension Install URLs ---
    EXTENSION_URLS = {
        "Chrome": "https://chrome.google.com/webstore/detail/CHROME_EXTENSION_ID", 
        "Firefox": "https://addons.mozilla.org/en-US/firefox/addon/omnipull-downloader/",
        "Edge": "https://microsoftedge.microsoft.com/addons/detail/mkhncokjlhefbbnjlgmnifmgejdclbhj"
    }

    def install_browser_extension(self, browser_name):
        url = self.EXTENSION_URLS.get(browser_name)
        if url:
            show_information("Opening Browser", f"Redirecting you to install the {browser_name} extension.", "Follow the instructions there.")
            QDesktopServices.openUrl(QUrl(url))
        else:
            show_warning("Extension Error", f"No URL available for {browser_name}.")

    def open_github_issues(self):
        """Open the GitHub issues page in the default browser."""
        url = 'https://github.com/Annor-Gyimah/OmniPull/issues'
        if url:
            QDesktopServices.openUrl(QUrl(url))
            show_information("Opening Browser", f"Redirecting you to github. Please let us know if you encounter any issues.", "Follow the instructions there.")
            
    def clear_all_completed_downloads(self):
        """Clears all completed downloads from the download list."""
        completed_dl = [d for d in self.d_list if d.status == "completed"]
        for d in completed_dl:
            self.d_list.remove(d)
        if not completed_dl:
            show_information(self.tr("Clear Downloads"), self.tr("No completed downloads to clear."), self.tr("All downloads are still active or paused."))
            return
        
    def open_completed_file(self, file_path):
        self.file_open_thread = FileOpenThread(file_path, self)
        self.file_open_thread.critical_signal.connect(show_critical)
        self.file_open_thread.start()
        self.background_threads.append(self.file_open_thread)

    def populate_open_menu(self):
        widgets.open_file_menu.clear()

        completed_dl = [d for d in self.d_list if d.status == "completed" and os.path.exists(d.target_file)]

        if not completed_dl:
            no_files = QAction(self.tr("No completed downloads"), self)
            no_files.setEnabled(False)
            widgets.open_file_menu.addAction(no_files)
            return

        # Custom widget to hold scrollable list
        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
            );
            }
            QListWidget::item {
                padding: 4px;
            }
        """)
        list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        list_widget.setFixedSize(300, 200)  # Set menu size

        for d in completed_dl:
            item = QListWidgetItem()
            label = MarqueeLabel(d.name)
            label.setToolTip(f"Size: {size_format(d.total_size)}")

            container = QWidget()
            layout = QHBoxLayout(container)
            layout.addWidget(label)
            layout.setContentsMargins(5, 2, 5, 2)
            container.setLayout(layout)

            list_widget.addItem(item)
            list_widget.setItemWidget(item, container)

            # Store path in item for later retrieval
            item.setData(Qt.UserRole, d.target_file)

        def on_item_clicked(item):
            file_path = item.data(Qt.UserRole)
            self.open_completed_file(file_path)

        list_widget.itemClicked.connect(on_item_clicked)

        # Add list widget to QMenu using QWidgetAction
        action_widget = QWidgetAction(widgets.open_file_menu)
        action_widget.setDefaultWidget(list_widget)
        widgets.open_file_menu.addAction(action_widget)

    # endregion
        


    # region Language Department

    def resource_path2(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)

    def apply_language(self, language):
        QCoreApplication.instance().removeTranslator(self.translator)

        file_map = {
            "English": "app_en.qm",
            "French": "app_fr.qm",
            "Spanish": "app_es.qm",
            "Chinese": "app_zh.qm",
            "Korean": "app_ko.qm",
            "Japanese": "app_ja.qm"
        }

        if language in file_map:
            qm_path = self.resource_path2(f"modules/translations/{file_map[language]}")
            if self.translator.load(qm_path):
                QCoreApplication.instance().installTranslator(self.translator)
                log(f"[Language] Loaded {language}", log_level=2)
            else:
                log(f"[Language] Failed to load {qm_path}", log_level=3)

        self.retrans()

    def retrans(self):
        """Texts, objects, buttons, etc to translate"""
        # Home Translations
        # widgets.home_link_label.setText(self.tr("LINK"))
        widgets.retry_btn.setText(self.tr("Retry"))
        widgets.folder_btn.setText(self.tr("Open"))
        widgets.folder_label.setText(self.tr("CHOOSE FOLDER"))
        widgets.filename_label.setText(self.tr("FILENAME"))
        widgets.link_input.setPlaceholderText(self.tr("Place download link here"))
        widgets.filename_input.setPlaceholderText(self.tr("Filename goes here"))
        widgets.combo1_label.setText(self.tr("Download Item:"))
        widgets.combo2_label.setText(self.tr("Resolution:"))
        widgets.combo3_label.setText(self.tr("Queue:"))
        widgets.playlist_btn.setText(self.tr("Playlist"))
        widgets.download_btn.setText(self.tr("Download"))
        widgets.size_label.setText(self.tr("Size:"))
        widgets.type_label.setText(self.tr("Type:"))
        widgets.protocol_label.setText(self.tr("Protocol:"))
        widgets.resume_label.setText(self.tr("Resumable:"))
        widgets.file_menu.setTitle(self.tr('File'))
        widgets.export_dl.setText(self.tr('Export Downloads List'))
        widgets.quitt.setText(self.tr('Exit'))
        widgets.open_file_menu.setTitle(self.tr('Open'))
        widgets.open_file_menu.actions()[0].setText(self.tr(''))
        widgets.downloads_menu.setTitle(self.tr('Downloads'))
        widgets.downloads_menu.actions()[0].setText(self.tr('Resume All'))
        widgets.downloads_menu.actions()[1].setText(self.tr('Stop All'))
        widgets.downloads_menu.actions()[2].setText(self.tr('Clear Completed'))
        widgets.view_menu.setTitle(self.tr('View'))
        widgets.view_menu.actions()[0].setText(self.tr('Refresh Table'))
        widgets.sort_menu.setTitle(self.tr('Sort By'))
        widgets.status_action.setText(self.tr('Sort by Status'))
        widgets.name_action.setText(self.tr('Sort by Name'))
        widgets.progress_action.setText(self.tr('Sort by Progress'))
        widgets.tools_menu.setTitle(self.tr("Tools"))
        widgets.settings_action.setText(self.tr('Settings'))
        widgets.browser_extension_menu.setTitle(self.tr('Browser Extension'))
        widgets.help_menu.setTitle(self.tr('Help'))
        widgets.help_menu.actions()[0].setText(self.tr('About'))
        widgets.help_menu.actions()[1].setText(self.tr('Check for Updates'))
        widgets.help_menu.actions()[2].setText(self.tr('User Guide'))
        widgets.help_menu.actions()[3].setText(self.tr('Visual Tutorials'))
        widgets.help_menu.actions()[4].setText(self.tr("Report Issues"))

        # Update context menu actions' text
        self.action_open_file.setText(self.tr("Open File"))
        self.action_open_file_with.setText(self.tr("Open File With"))
        self.action_open_location.setText(self.tr("Open File Location"))
        self.action_watch_downloading.setText(self.tr("Watch while downloading"))
        self.action_schedule_download.setText(self.tr("Schedule download"))
        self.action_cancel_schedule.setText(self.tr("Cancel schedule!"))
        self.action_remerge.setText(self.tr("Re-merge audio/video"))
        self.action_file_properties.setText(self.tr("File Properties"))
        self.action_add_to_queue.setText(self.tr("Add to Queue"))
        self.action_remove_from_queue.setText(self.tr("Remove from Queue"))
        self.action_file_checksum.setText(self.tr("File CheckSum!"))
        self.action_pop_file_from_table.setText(self.tr("Delete from Table"))

        
        

    # region Queues Control

    def start_queue_by_id(self, queue_id):
        # Find the queue by ID and set it active
        self.running_queues[queue_id] = True
        self.ui_queues.current_queue_id = queue_id
        self.ui_queues.queue_list.setCurrentRow(
            next((i for i, q in enumerate(self.queues) if self.get_queue_id(q["name"]) == queue_id), 0)
        )
        self.ui_queues.start_queue_downloads()

    def check_scheduled_queues(self):
        now = QTime.currentTime()

        for q in self.queues:
            queue_id = self.get_queue_id(q["name"])
            schedule = q.get("schedule")

            if not schedule or self.running_queues.get(queue_id, False):
                continue

            hour, minute = schedule
            if now.hour() == hour and now.minute() == minute:
                last_time = self.last_schedule_check.get(queue_id)

                if last_time and last_time.hour() == hour and last_time.minute() == minute:
                    continue  # Already triggered this minute

                items = [d for d in self.d_list if d.in_queue and d.queue_id == queue_id and d.status == config.Status.queued]
                if items:
                    self.start_queue_by_id(queue_id)
                    self.last_schedule_check[queue_id] = now
                    csq1, csq2 = self.tr('Queue'), self.tr('has started automatically')
                    show_information(title=self.tr('Queue Scheduler'), inform='', msg=f"{csq1} '{q['name']}' {csq2}")
                    

    def update_queue_combobox(self):
        # self.queues = setting.load_queues()
        # self.queues = self.settings_manager.load_queues()
        self.queues = self.settings_manager.queues
        widgets.combo3.clear()
        widgets.combo3.addItems(["None"] + [q["name"] for q in self.queues])

    def queue_combo(self):
        # self.queues = setting.load_queues()
        self.queues = self.settings_manager.queues
        
        if not self.queues:
            return

        widgets.combo3.clear()

        widgets.combo3.addItem("None")
        for queue in self.queues:
            name = queue.get("name")
            if name:
                widgets.combo3.addItem(name)
    
    # endregion
    

    def update_toolbar_buttons_for_selection(self):
        selected_rows = widgets.table.selectionModel().selectedRows()

        if not selected_rows:
            # Enable only global buttons
            for key in widgets.toolbar_buttons:
                widgets.toolbar_buttons[key].setEnabled(key in {
                    "Stop All", "Resume All", "Settings", "Schedule All", "Queues",
                })
            return

        selected_ids = [
            widgets.table.item(row.row(), 0).data(Qt.UserRole)
            for row in selected_rows
        ]

        selected_items = [d for d in self.d_list if d.id in selected_ids]
        if not selected_items:
            return

        # Combine all button states across selected items
        combined_states = toolbar_buttons_state(selected_items[0].status).copy()

        for d in selected_items[1:]:
            state = toolbar_buttons_state(d.status)
            for key in combined_states:
                combined_states[key] = combined_states[key] and state.get(key, False)

        for key, enabled in combined_states.items():
            if key in widgets.toolbar_buttons:
                widgets.toolbar_buttons[key].setEnabled(enabled)


    




    def setup(self):
        """initial setup"""     
        # download folder
        if not self.d.folder:
            self.d.folder = config.download_folder



    
    # region GUI Updates
    
    def read_q(self):
        """Read from the queue and update the GUI."""
        while not config.main_window_q.empty():
            k, v = config.main_window_q.get()

            if k == 'log':
                try:
                    contents = widgets.terminal_log.toPlainText()
                    if len(contents) > config.max_log_size:
                        # delete 20% of contents to keep size under max_log_size
                        slice_size = int(config.max_log_size * 0.2)
                        widgets.terminal_log.setPlainText(contents[slice_size:])

                    # parse youtube output while fetching playlist info with option "process=True"
                    if '[download]' in v and 'Downloading video' in v and 'of' in v:
                        try:
                            b = v.rsplit(maxsplit=3)
                            total_num = int(b[-1])
                            num = int(b[-3])
                            percent = int(num * 100 / total_num)
                            percent = percent // 2
                        except Exception as e:
                            log(f"[read_q] Error parsing download progress: {e}", log_level=3)

                    widgets.terminal_log.append(v)
                except Exception as e:
                    log(f"{e}", log_level=3)

            elif k == 'url':
                # Update the QLineEdit with the new URL
                widgets.link_input.setText(v)
                self.url_text_change()
                #self.update_progress_bar()   
            elif k == "download":
                self.start_download(*v)
            elif k == "monitor":
                widgets_settings.monitor_clipboard_cb.setChecked(v)               
            elif k == 'show_update_gui':  # show update gui
                self.show_update_gui()    
            elif k == 'popup':
                type_ = v['type_']
                if type_ == 'info':
                    show_information(title=v['title'], inform="", msg=v['msg'])
                elif type_ == 'warning':
                    show_warning(title=v['title'], msg=v['msg'])
                elif type_ == 'critical':
                    show_critical(title=v['title'], msg=v['msg'])
            elif k == "queue_list":
                self.queue_combo()
            elif k == "queue_download":
                self._queue_or_start_download(*v)
            elif k == "update call":
                self.start_update(*v)


    def run(self):
        """Handle the event loop."""
        try:
            self.read_q()  # Handle queue read operation
        except (AttributeError, TypeError) as e:
            log(f"Error reading queue: {e}", log_level=3)
        
        try:
            self.queue_updates()  # Update the GUI components
        except (AttributeError, RuntimeError) as e:
            log(f"Error updating GUI components: {e}", log_level=3)
        
        if self.one_time:
            self.one_time = False
            
            try:
                # Check availability of ffmpeg in the system or in the same folder as this script
                t = time.localtime()
                today = t.tm_yday  # Today number in the year range (1 to 366)
            except (ValueError, TypeError) as e:
                log(f"Error with date/time operation: {e}", log_level=3)
                return
            
            try:
                days_since_last_update = today - config.last_update_check
                log('Days since last check for update:', days_since_last_update, 'day(s).', log_level=1)
                
                if days_since_last_update >= config.update_frequency:
                    log('Checking for software updates...', log_level=1)
                    Thread(target=self.update_available, daemon=True).start()
                    self.server_check_update = ServerSoftwareCheckThread(d_list=self.d_list)
                    self.server_check_update.start()
                    self.background_threads.append(self.server_check_update)
                    config.last_update_check = today
            except (TypeError, ValueError) as e:
                log(f"Error in update check calculations: {e}", log_level=3)
            except Exception as e:
                log(f"Error in run loop: {e}", log_level=3)
    
    def check_for_gui_updates(self):
        if self.pending_updates:
            self.update_gui_signal.emit(self.pending_updates)
            self.pending_updates.clear()

    def queue_update(self, key, value):
        self.pending_updates[key] = value

    @Slot(dict)
    def process_gui_updates(self, updates: dict[str, Any]) -> None:
        try:
            for key, value in updates.items():
                if key == 'filename':
                    if widgets.filename_input.text() != value:
                        self.filename_set_by_program = True
                        widgets.filename_input.setText(value)
                        self.filename_set_by_program = False
                elif key == 'status_code':
                    cod = "ok" if value == 200 else ""
                    widgets.status_value.setText(f"{value} {cod}")
                elif key == 'size':
                    size_text = size_format(value) if value else "Unknown"
                    widgets.size_value.setText(size_text)
                elif key == 'type':
                    widgets.type_value.setText(value)
                elif key == 'protocol':
                    widgets.protocol_value.setText(value)
                elif key == 'resumable':
                    widgets.resume_value.setText("Yes" if value else "No")
                elif key == 'total_speed':
                    speed_text = f'⬇⬆ {size_format(value, "/s")}' if value else '⬇⬆ 0 bytes'
                    widgets.speed_value.setText(speed_text)
                elif key == 'populate_table':
                    self.populate_table()
                elif key == 'check_scheduled':
                    self.check_scheduled()
                elif key == 'pending_jobs':
                    self.pending_jobs()
                elif key == 'check_browser_queue':
                    self.check_browser_queue()
                elif key == '_handle_version_status':
                    self._handle_version_status()
        
            # Save settings 
            # setting.save_setting()
            # setting.save_d_list(self.d_list)
            self.settings_manager.save_settings()
            self.settings_manager.save_d_list(self.d_list)

        except Exception as e:
            log(f'MainWindow.process_gui_updates() error: {str(e)}', log_level=3)

    def queue_updates(self):
        """Queue updates instead of directly modifying GUI"""
        self.queue_update('filename', self.d.name)
        self.queue_update('status_code', self.d.status_code)
        self.queue_update('size', self.d.total_size)
        self.queue_update('type', self.d.type)
        self.queue_update('protocol', self.d.protocol)
        self.queue_update('resumable', self.d.resumable)

        # total_speed = sum(self.d_list[i].speed for i in self.active_downloads)
        total_speed = sum(self.d_list[i].speed for i in self.active_downloads if i < len(self.d_list))

        self.queue_update('total_speed', total_speed)

        # Queue other updates
        self.queue_update('populate_table', None)
        self.queue_update('check_scheduled', None)
        self.queue_update('pending_jobs', None)
        self.queue_update('check_browser_queue', None)
        self.queue_update('_handle_version_status', None)
        self.update_table_progress()
        
        #self.queue_update('thumbnail', None)

    # endregion



    # region Url Processing

    def on_clipboard_change(self):
        """
        Monitors the clipboard for changes.
        """
        try:
            new_data = self.clipboard.text()

            # Check for instance message
            if new_data == 'any one there?':
                self.clipboard.setText('yes')
                self.show()
                self.raise_()
                return

            # Check for URLs if monitoring is active
            if config.monitor_clipboard and new_data != self.old_clipboard_data:
                if new_data.startswith('http') and ' ' not in new_data:
                    config.main_window_q.put(('url', new_data))                    
                self.old_clipboard_data = new_data

        except (AttributeError, TypeError) as e:
            log(f"Clipboard error due to incorrect data type or attribute access: {str(e)}", log_level=2)


    def clean_url(self, original_url):
        parsed = urlparse(original_url)
        query = parse_qs(parsed.query)
        
        # Keep only the video ID (v=)
        clean_query = {}
        if 'v' in query:
            clean_query['v'] = query['v']

        # Rebuild the cleaned URL
        new_query = urlencode(clean_query, doseq=True)
        cleaned_url = urlunparse(parsed._replace(query=new_query))
        return cleaned_url

    def url_text_change(self):
        """Handle URL changes in the QLineEdit."""
        url = widgets.link_input.text().strip()

        url = self.clean_url(url) if config.ytdlp_config['no_playlist'] else url

        if url == self.d.url:
            return
        

        self.reset()
        try:
            self.d.eff_url = self.d.url = url
            log(f"New URL set: {url}", log_level=1)
            # Update the DownloadItem with the new URL
            # schedule refresh header func
            if isinstance(self.url_timer, Timer):
                self.url_timer.cancel()  # cancel previous timer

            self.url_timer = Timer(0.5, self.refresh_headers, args=[url])
            self.url_timer.start()
            # Trigger the progress bar update and GUI refresh
        except AttributeError as e:
            log(f"Error setting URLs in the object 'self.d': {e}", log_level=3)
            return  # Early return if we can't set URLs properly

    def process_url(self):
        """Simulate processing the URL and update the progress bar.""" 
        progress_steps = [10, 50, 100]  # Define the progress steps
        for step in progress_steps:
            time.sleep(1)  # Simulate processing time
            self.update_progress_bar_value(step)  # Update the progress bar in the main thread  
    
    def update_progress_bar_value(self, value):
        """Update the progress bar value in the GUI."""
        widgets.progress.setValue(value)       

    def retry(self):
        self.d.url = ''
        self.url_text_change()

    def reset(self):
        self.d = DownloadItem() # create new download item, the old one will be garbage collected by python interpreter
        # reset some values
        self.playlist = []
        self.video = None

    def update_progress_bar(self):
        """Update the progress bar based on URL processing."""
        Thread(target=self.process_url, daemon=True).start() # Start a new thread for the progress updates

    
    def refresh_headers(self, url):
        if self.d.url != '':
            #self.change_cursor('busy')
            Thread(target=self.get_header, args=[url], daemon=True).start()


    def decide_download_engine(self):
        preferred_engine = getattr(config, "download_engine", "yt-dlp").lower()

        if preferred_engine == "aria2":
            if config.aria2c_path and os.path.exists(config.aria2c_path):
                self.d.engine = "aria2c"
                if not hasattr(self.d, "aria_gid"):
                    self.d.aria_gid = None  # Set only if missing
            else:
                log("[Engine] aria2c selected, but executable not found. Falling back to curl.", log_level=2)
                self.d.engine = "curl"
                
        elif preferred_engine == "yt-dlp":
            self.d.engine = "yt-dlp"

        elif preferred_engine == "curl":
            self.d.engine = "curl"

        log(f"[Engine] Using: {self.d.engine} for {self.d.name}", log_level=1)
        # setting.save_d_list(self.d_list)
        self.settings_manager.save_d_list(self.d_list)

    
    
    def extract_ext_from_url(self, url: str, d=None) -> str:
        
        media_exts = {"mp4","m4v","webm","mkv","avi","mov","flv","ts","m4a","aac","mp3","opus","wav"}
        file_exts  = {"pdf":"application/pdf","zip":"application/zip","exe":"application/x-msdownload",
                    "7z":"application/x-7z-compressed","rar":"application/vnd.rar",
                    "csv":"text/csv","txt":"text/plain","json":"application/json","xml":"application/xml",
                    "jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","gif":"image/gif"}
        # reverse map for quick lookup
        ctype_to_ext = {v:k for k,v in file_exts.items()}

        def _norm(ext): return (ext or "").lower().lstrip(".")

        if d is None:
            d = getattr(self, "d", None)

        # Prefer local file paths if they exist (most reliable)
        for p in (getattr(d, "target_file", None), getattr(d, "temp_file", None)):
            if p and os.path.exists(p):
                return _norm(os.path.splitext(p)[1])

        # Try yt-dlp info (for streams) — omitted here for brevity if you already added it

        # URL path or query filename (works well for static files)
        try:
            parsed = urlparse(url or getattr(d, "url", "") or getattr(d, "eff_url", ""))
            fname  = unquote(os.path.basename(parsed.path or ""))
            ext    = _norm(os.path.splitext(fname)[1])
            if ext:
                return ext
            q = parse_qs(parsed.query or "")
            for k in ("filename","file","name","title"):
                if k in q and q[k]:
                    ext = _norm(os.path.splitext(unquote(q[k][0]))[1])
                    if ext:
                        return ext
        except Exception:
            pass

        # Content-Type fallback for static files
        ctype = (getattr(d, "type", "") or "").lower()
        if ctype in ctype_to_ext:
            return ctype_to_ext[ctype]

        # As a safe default, return 'mp4' (keeps media actions working)
        return "mp4"

    
    

    
    def get_header(self, url):
        self.d.update(url)

        # ✅ Set ext for static URL
        self.d.ext = self.extract_ext_from_url(self.d.url, self.d)

        self.decide_download_engine()

        if url == self.d.url:
            if self.d.status_code not in self.bad_headers and self.d.type != 'text/html':
                widgets.download_btn.setEnabled(True)

            # Use QThread for YouTube function
            self.yt_thread = YouTubeThread(url)
            self.yt_thread.finished.connect(self.on_youtube_finished)
            self.yt_thread.progress.connect(self.update_progress_bar_value)  # Connect progress signal to update progress bar
            self.yt_thread.start()
            self.background_threads.append(self.yt_thread)
            
    

    def on_youtube_finished(self, result):
        if isinstance(result, list):
            self.playlist = result
            if self.playlist:
                self.d = self.playlist[0]
            widgets.download_btn.setEnabled(False)
            widgets.playlist_btn.setEnabled(True)
        elif isinstance(result, Video):
            self.playlist = [result]
            self.d = result
            
            # # ✅ Set ext from filename
            if not self.d.ext:
                self.d.ext = self.extract_ext_from_url(self.d.url, self.d)
                log(f"[Engine] Guessed extension from URL: {self.d.ext}", log_level=1)
            
            widgets.download_btn.setEnabled(True)
            widgets.playlist_btn.setEnabled(False)
        else:
            log("Error: YouTube extraction failed", log_level=3)
            change_cursor('normal')
            #widgets.download_btn.setEnabled(True)
            widgets.download_btn.setEnabled(True)
            widgets.playlist_btn.setEnabled(True)

            widgets.combo1.clear()
            widgets.combo2.clear()
            self.reset_to_default_thumbnail()
            return
        
        self.yt_thread.quit()
        self.yt_thread.wait()

        # ✅ Warn user if aria2c is selected for YouTube streams
        engine = config.download_engine.lower()
        if engine in ["aria2", "aria2c"]:
            url = self.d.url if isinstance(self.d, Video) else self.d.vid_info.get("webpage_url", "")
            if "youtube.com" in url or "youtu.be" in url:
                
                reply = QMessageBox(self)
                reply.setStyleSheet(get_msgbox_style("warning"))
                reply.setWindowTitle(self.tr("Aria2c Warning"))
                oyf1, oyf2 = self.tr("This method is experimental and may not download or merge properly."), self.tr("Do you want to continue?")
                reply.setText(self.tr("You selected Aria2c for downloading a YouTube video.\n"
                    f"{oyf1}\n\n"
                    f"{oyf2}"))
                reply.setIcon(QMessageBox.Question)
                reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                reply.exec()
                
                if reply == QMessageBox.No:
                    log("[Main] User cancelled YouTube download with aria2c.", log_level=2)
                    widgets.download_btn.setEnabled(False)
                    widgets.playlist_btn.setEnabled(False)
                    return



        self.update_pl_menu()
        self.update_stream_menu()

    # endregion

    # region Folder & Filename

    def open_folder_dialog(self):
        """Open a dialog to select a folder and update the line edit."""
        # Open a folder selection dialog
        folder_path = QFileDialog.getExistingDirectory(self, "Select Download Folder")

        # If a folder is selected, update the line edit with the absolute path
        if folder_path:
            widgets.folder_input.setText(folder_path)
            config.download_folder = os.path.abspath(folder_path)
        else:
            # If no folder is selected, reset to the default folder (config.download_folder)
            widgets.folder_input.setText(config.download_folder)
    

    def on_filename_changed(self, text: str) -> str:
        """Handle manual changes to the filename line edit."""

        # Only update the download item if the change was made manually
        if not self.filename_set_by_program:
            self.d.name = text

    
    # endregion
   
    
    
    
    # region Downloads methods

    @property
    def active_downloads(self):
        # update active downloads
        _active_downloads = set(d.id for d in self.d_list if d.status == config.Status.downloading)
        config.active_downloads = _active_downloads

        return _active_downloads
    
    def pending_jobs(self):
        # process pending jobs
        if self.pending and len(self.active_downloads) < config.max_concurrent_downloads:
            self.start_download(self.pending.popleft(), silent=True)


    def start_download(self, d, silent: bool = False, downloader: Any = None):
        # if self.check_time:
        #     self.check_time = False
        #     server_check = update.SoftwareUpdateChecker(api_url="https://dynamite0.pythonanywhere.com/api/licenses", software_version=config.APP_VERSION)
        #     server_check.server_check_update()
        # aria2c_path_exist = os.path.join(config.sett_folder, 'aria2c.exe') 

        if d is None:
            return
        
        # check for ffmpeg availability in case this is a dash video
        if d.type == 'dash' or 'm3u8' in d.protocol:
            # log('Dash video detected')
            if not self.ffmpeg_check():
                log('Download cancelled, FFMPEG is missing', log_level=2)
                return 'cancelled'

        folder = d.folder or config.download_folder
        # validate destination folder for existence and permissions
        # in case of missing download folder value will fallback to current download folder
        fe = self.tr('Folder Error')
        try:
            with open(os.path.join(folder, 'test'), 'w') as test_file:
                test_file.write('0')
            os.unlink(os.path.join(folder, 'test'))

            # update download item
            d.folder = folder
        except FileNotFoundError:
            df, dne = self.tr('destination folder'), self.tr('does not exist')
            show_information(f'{fe}', self.tr('Please enter a valid folder name'), f'{df} {folder} {dne}')
            return
        
        except PermissionError:
            ydh = self.tr("you don't have enough permission for destination folder")
            show_information(f'{fe}', f"{ydh} {folder}", "")
            return
        
        except Exception as e:
            pidf = self.tr("problem in destination folder")
            show_warning(f'{fe}',f'{pidf} {repr(e)}')
        
        # validate file name
        if d.name == '':
            show_warning(self.tr('Download Error'), self.tr('File name is invalid. Please enter a valid filename'))
            return
            

        # if os.path.isfile(d.target_file):
        #     # Localized strings
        #     fwtsnaei = self.tr("File with the same name already exists in")
        #     dywtof = self.tr("Do you want to overwrite the file?")

        #     # Styled dialog setup
        #     msg_box = QMessageBox(self)
        #     msg_box.setWindowTitle(self.tr("File Overwrite"))
        #     msg_box.setText(f"{fwtsnaei}:\n\n{d.folder}\n\n{dywtof}")
        #     msg_box.setIcon(QMessageBox.Question)
        #     msg_box.setStyleSheet(get_msgbox_style("overwrite"))

        #     # Add Yes and No buttons
        #     yes_btn = msg_box.addButton(self.tr("Overwrite"), QMessageBox.YesRole)
        #     no_btn = msg_box.addButton(self.tr("Cancel"), QMessageBox.NoRole)
        #     msg_box.setDefaultButton(no_btn)

        #     # Show the dialog
        #     msg_box.exec()

        #     if msg_box.clickedButton() != yes_btn:
        #         log('Download cancelled by user')
        #         return 'cancelled'
        #     else:
        #         delete_file(d.target_file)

        # ------------------------------------------------------------------
        # search current list for previous item with same name, folder
        found_index = self.file_in_d_list(d.target_file)
        if found_index is not None: # might be zero, file already exist in d_list
            log('donwload item', d.num, 'already in list, check resume availability')
            d_from_list = self.d_list[found_index]
            d.id = d_from_list.id

            # default
            response = "Resume"

            if not silent:
                # show dialogue
                msg_text_a = self.tr("File with the same name:")
                msg_text_b = self.tr("already exists in download list")
                msg_text_c = self.tr("Do you want to resume this file?")
                msg_text_d = self.tr("Resume ==> continue if it has been partially downloaded ...")
                msg_text_e = self.tr("Overwrite ==> delete old downloads and overwrite existing item... ")
                msg_text_f = self.tr("Note: if you need a fresh download, you have to change file name ")
                msg_text_g = self.tr("or target folder, or delete the same entry from the download list.")
                msg_text = (f'{msg_text_a} \n{self.d.name},\n {msg_text_b}\n'
                f'{msg_text_c}\n'
                f'{msg_text_d} \n'
                f'{msg_text_e}\n'
                f'{msg_text_f}\n'
                f'{msg_text_g}')

                # Create a QMessageBox
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Question)
                msg.setStyleSheet(get_msgbox_style("conflict"))
                msg.setWindowTitle(self.tr("File Already Exists"))
                msg.setText(msg_text)

                # Add buttons
                resume_button = msg.addButton(self.tr("Resume"), QMessageBox.YesRole)
                overwrite_button = msg.addButton(self.tr("Overwrite"), QMessageBox.NoRole)
                cancel_button = msg.addButton(self.tr("Cancel"), QMessageBox.RejectRole)

                msg.setDefaultButton(overwrite_button)


                # Execute the dialog and get the result
                msg.exec()

                # Check which button was clicked
                if msg.clickedButton() == resume_button:
                    response = 'Resume'
                elif msg.clickedButton() == overwrite_button:
                    response = 'Overwrite'
                else:
                    response = 'Cancel'

            # Handle responses
            match response:
                case 'Resume':
                    log('resuming')

                    # to resume, size must match, otherwise it will just overwrite
                    if d.size == d_from_list.size:
                        log('resume is possible')
                        # get the same segment size
                        d.segment_size = d_from_list.segment_size
                        d.downloaded = d_from_list.downloaded
                    else:
                        log(f'file: {d.name} has a different size and will be downloaded from beginning')
                        d.delete_tempfiles()

                    # Replace old item in download list
                    self.d_list[found_index] = d
                
                case 'Overwrite':

                    log('overwrite')
                    d.delete_tempfiles()

                    # Replace old item in download list
                    self.d_list[found_index] = d

                case _:

                    log('Download cancelled by user')
                    d.status = config.Status.cancelled
                    return
            
        # ------------------------------------------------------------------
        else:
            # generate unique id number for each download
            d.id = len(self.d_list)

            # add to download list
            self.d_list.append(d)

        # if max concurrent downloads exceeded, this download job will be added to pending queue
        if len(self.active_downloads) >= config.max_concurrent_downloads:
            d.status = config.Status.pending
            self.pending.append(d)
            return


        # just before creating the window
        if d.status in (config.Status.cancelled, config.Status.completed, config.Status.error):
            d.status = config.Status.downloading  # or config.Status.downloading if you prefer

        # Show window if allowed, or if it's a resumed download (for progress visibility)
        should_show_window = config.show_download_window and (not silent or d.downloaded)

        if should_show_window:
            self.download_windows[d.id] = DownloadWindow(d)
            self.download_windows[d.id].show()


        # start downloading
        # if config.show_download_window and not silent:
        #     # create download window
        #     self.download_windows[d.id] = DownloadWindow(d)
        #     self.download_windows[d.id].show()  

        # Using this will not make the progress bar work for resuming downloads.
        # if config.show_download_window and not silent:
        #     # create download window
        #     self.download_windows[d.id] = DownloadWindow(d)
        #     self.download_windows[d.id].show()

        if d.engine not in ['aria2c', 'aria2', 'yt-dlp']:
            os.makedirs(d.temp_folder, exist_ok=True)



        # create and start brain in a separate thread
        Thread(target=brain.brain, daemon=True, args=(d, downloader)).start()


    def file_in_d_list(self, target_file):
        for i, d in enumerate(self.d_list):
            if d.target_file == target_file:
                return i
        return None


    def get_queue_id(self, name: str) -> str:
        """Generate a unique ID for the queue based on its name."""
        return hashlib.md5(name.encode()).hexdigest()[:8]


    

    def on_download_button_clicked(self, downloader=None):
        """Handle DownloadButton click event."""
        if self.d.url == "":
            show_information(self.tr("Download Error"), self.tr("Nothing to download"), self.tr("Check your URL or click Retry."))
            return
        
        d = copy.copy(self.d)
        d.folder = config.download_folder
        selected_queue = widgets.combo3.currentText()

        # Check for YouTube/streaming videos first
        if isinstance(self.d, Video) and selected_queue and selected_queue != "None":
            show_warning(self.tr("Queue Error"), self.tr("YouTube and streaming videos cannot be added to a queue. Please download directly."))
            return

        # Check if it's a queued download
        if selected_queue and selected_queue != "None":
            # Check if download is completed
            if d.status == config.Status.completed:
                show_warning(self.tr("Queue Error"), self.tr("Cannot add completed download to queue."),self.tr("This item has already been downloaded."))
                return

            # Check if file exists in target directory
            target_path = os.path.join(d.folder, d.name)
            if os.path.exists(target_path):
                existing_queue = None
                # Check if this file exists in any queue
                for existing_d in self.d_list:
                    if (existing_d.in_queue and 
                        existing_d.name == d.name and 
                        os.path.exists(os.path.join(existing_d.folder, existing_d.name))):
                        existing_queue = existing_d.queue_name
                        break
                if existing_queue == selected_queue:
                    # File exists and is in the same queue
                    odbc1, odbc2 = self.tr('This file already exists in queue:'),  self.tr('Please choose a different queue or rename the file.')
                    show_warning(

                        self.tr("Queue Error"),
                        
                        f"{odbc1} {selected_queue} \n {odbc2}",
                    )
                    return
                elif existing_queue:
                    # File exists but in a different queue
                    odbc3 = self.tr('A file cannot be in multiple queues. Please remove it from the other queue first.')
                    show_warning(
                        self.tr("Queue Error"),

                        f"{odbc1} {existing_queue} \n {odbc3}",
                    )
                    return
                else:
                    # File exists but not in any queue
                    odbc4 = 'Cannot add to queue because the target file already exists:'
                    show_warning(
                        self.tr("File Exists"),
                        f" {odbc4} {target_path}",
                    )
                    return

            # Check for same filename in different queues
            for existing_d in self.d_list:
                if existing_d.in_queue and existing_d.name == d.name:
                    # Only block if same filename AND same target folder
                    if existing_d.folder == d.folder:
                        if existing_d.queue_name == selected_queue:
                            odbc5 = 'Please choose a different filename or target folder.'
                            show_warning(
                                self.tr("Queue Error"),
                                f"{odbc1} {selected_queue} \n {odbc5}",
                                
                            )
                            return
                        else:
                            show_warning(
                                self.tr("Queue Error"), 
                                f"{odbc1} {existing_d.queue_name} \n {odbc5}",
    
                            )
                            return


            # If all checks pass, proceed with queue setup
            d.in_queue = True 
            d.queue_name = selected_queue
            d.queue_id = self.get_queue_id(selected_queue)
            d.status = config.Status.queued
            d.last_known_progress = 0
            d.last_known_size = 0
            d._segments = []  # Clear old segment info

            # Assign next available position in the queue
            existing_positions = [
                item.queue_position for item in self.d_list
                if item.in_queue and item.queue_name == selected_queue
            ]
            d.queue_position = max(existing_positions, default=0) + 1

            # Add to download list
            d.id = len(self.d_list)
            self.d_list.append(d)
            self.settings_manager.save_d_list(self.d_list)
            self.queue_update("populate_table", None)

            item = d.name
            title = self.tr("Added to Queue")
            inform = self.tr(f"{item} has been added to queue:")
            msg = self.tr("Start it from the Queues Dialog.")
            show_information(title, inform, msg)
            self.change_page(btn=None, btnName=None, idx=1)
        
        else:
            # Direct download
            d.queue = None
            r = self.start_download(d, downloader=downloader)
            if r not in ('error', 'cancelled', False):
                self.change_page(btn=None, btnName=None, idx=1)


    # endregion

    # region Youtube Specifics

    def show_thumbnail(self, thumbnail=None):
        """Show video thumbnail in thumbnail image widget in main tab, call without parameter to reset thumbnail."""

        try:
            if thumbnail is None or thumbnail == "":
                # Reset to default thumbnail if no new thumbnail is provided
                default_pixmap = QPixmap(":/icons/thumbnail-default.png")
                widgets.thumbnail.setPixmap(default_pixmap.scaled(400, 350, Qt.KeepAspectRatio))
                log("Resetting to default thumbnail", log_level=2)
            elif thumbnail != self.current_thumbnail:
                self.current_thumbnail = thumbnail

                if thumbnail.startswith(('http://', 'https://')):
                    # If it's a URL, download the image
                    request = QNetworkRequest(QUrl(thumbnail))
                    self.network_manager.get(request)
                else:
                    # If it's a local file path
                    pixmap = QPixmap(thumbnail)
                    if not pixmap.isNull():
                        widgets.thumbnail.setPixmap(pixmap.scaled(400, 350, Qt.KeepAspectRatio))
                    else:
                        self.reset_to_default_thumbnail()

        except Exception as e:
            log(f'show_thumbnail() error: {str(e)}', log_level=3)
            self.reset_to_default_thumbnail()
    
    def on_thumbnail_downloaded(self, reply):
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            image = QImage()
            if image.loadFromData(data):
                pixmap = QPixmap.fromImage(image)
                widgets.thumbnail.setPixmap(pixmap.scaled(400, 350, Qt.KeepAspectRatio))
            else:
                self.reset_to_default_thumbnail()
        else:
            self.reset_to_default_thumbnail()

    def reset_to_default_thumbnail(self):
        default_pixmap = QPixmap(":/icons/thumbnail-default.png")
        widgets.thumbnail.setPixmap(default_pixmap.scaled(400, 350, Qt.KeepAspectRatio))
        log("Reset to default thumbnail due to error", log_level=2)
        widgets_settings.monitor_clipboard_cb.setChecked(True)


    def update_pl_menu(self):
        """Update the playlist combobox after processing."""
        try:
            log("Updating playlist menu", log_level=1)
            if not hasattr(self, 'playlist') or not self.playlist:
                log("Error: Playlist is empty or not initialized", log_level=3)
                return

            # Set the playlist combobox with video titles
            widgets.combo1.clear()  # Clear existing items
            for i, video in enumerate(self.playlist):
                if hasattr(video, 'title') and video.title:
                    widgets.combo1.addItem(f'{i + 1} - {video.title}')
                else:
                    log(f"Warning: Video at index {i} has no title", log_level=2)

            # Automatically select the first video in the playlist
            if self.playlist:
                self.playlist_OnChoice(self.playlist[0])

        except Exception as e:
            log(f"Error updating playlist menu: {e}", log_level=3)
            import traceback
            log('Traceback:', traceback.format_exc())

    def update_stream_menu(self):
        """Update the stream combobox after selecting a video."""
        try:
            log("Updating stream menu", log_level=1)

            if not hasattr(self, 'd') or not self.d:
                log("Error: No video selected", log_level=3)
                return
            
            if not hasattr(self.d, 'stream_names') or not self.d.stream_names:
                log("Error: Selected video has no streams", log_level=3)
                return

            # Set the stream combobox with available stream options
            widgets.combo2.clear()  # Clear existing items
            widgets.combo2.addItems(self.d.stream_names)

            # Automatically select the first stream
            if self.d.stream_names:
                selected_stream = self.d.stream_names[0]
                widgets.combo2.setCurrentText(selected_stream)
                self.stream_OnChoice(selected_stream)

        except Exception as e:
            log(f"Error updating stream menu: {e}", log_level=3)
            import traceback
            log('Traceback:', traceback.format_exc())



    def playlist_OnChoice(self, selected_video):
        """Handle playlist item selection."""
        if selected_video not in self.playlist:
            return

        # Find the selected video index and set it as the current download item
        index = self.playlist.index(selected_video)
        self.video = self.playlist[index]
        self.d = self.video  # Update current download item to the selected video

        # Update the stream menu based on the selected video
        self.update_stream_menu()

        # Optionally load the video thumbnail in a separate thread
        if config.show_thumbnail:
            Thread(target=self.video.get_thumbnail).start()
        
            self.show_thumbnail(thumbnail=self.video.thumbnail_url)
        
        
    def stream_OnChoice(self, selected_stream):
        """Handle stream selection."""
    
        # Check if the selected stream is different from the current one
        if selected_stream == getattr(self.video, 'selected_stream_name', None):
            # If it's the same stream as the current one, skip further processing
            log(f"Stream '{selected_stream}' is already selected. No update needed.", log_level=2)
            return

        # Check if the selected stream exists in the available stream names
        if selected_stream not in self.video.stream_names:
            log(f"Warning: Selected stream '{selected_stream}' is not valid, defaulting to the first stream.", log_level=2)
            selected_stream = self.video.stream_names[0]  # Default to the first stream if invalid
        
        # Update the selected stream in the video object
        self.video.selected_stream = self.video.streams[selected_stream]  # Update with stream object
        self.video.selected_stream_name = selected_stream  # Keep track of the selected stream name

        log(f"Stream '{selected_stream}' selected for video {self.video.title}", log_level=1)



    def download_playlist(self):
        if not self.video:
            show_information(
                self.tr("Playlist Download"), 
                self.tr("Please check the URL."), 
                self.tr("Playlist is empty, nothing to download.")
            )
            return

        mp4_videos = {s.raw_name: s for v in self.playlist for s in v.mp4_videos.values()}
        other_videos = {s.raw_name: s for v in self.playlist for s in v.other_videos.values()}
        audio_streams = {s.raw_name: s for v in self.playlist for s in v.audio_streams.values()}
        raw_streams = {**mp4_videos, **other_videos, **audio_streams}

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Playlist Download"))
        dialog.setMinimumWidth(700)
        dialog.setStyleSheet("""
            QDialog {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
                border-radius: 14px;
            } 
            QCheckBox, QLabel, QComboBox, QPushButton {
                font-size: 13px;
                background: transparent;
            }
            QLabel#instruction_label {
                font-size: 12px;
                color: rgba(200, 255, 240, 0.9);
                padding: 12px 16px;
                background-color: rgba(255, 255, 255, 0.015);
                border-left: 2px solid #00C896;
                border-radius: 6px;
            }
            QComboBox {
                background-color: rgba(28, 28, 30, 0.85);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(20, 25, 20, 0.95);
                border: 1px solid rgba(60, 200, 120, 0.25);
                selection-background-color: #2DE099;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
                background: transparent;
            }
            QCheckBox {
                spacing: 8px;
                color: white;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QPushButton {
                background-color: rgba(0, 128, 96, 0.4);
                color: white;
                border: 1px solid rgba(0, 255, 180, 0.1);
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(0, 192, 128, 0.6);
            }
            QWidget#scroll_item_row {
                background-color: rgba(255, 255, 255, 0.02);
                border-radius: 6px;
                padding: 6px;
            }
                             
            QWidget#scrollContent {
            background-color: transparent;  /* or try a dark color like #111 for solid */
            }

            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)

        master_combo = QComboBox()
        master_combo.addItems([
            '● Video Streams:'
        ] + list(mp4_videos) + list(other_videos) + [
            '', '● Audio Streams:'
        ] + list(audio_streams))

        select_all = QCheckBox(self.tr("Select All"))
        master_layout = QHBoxLayout()
        master_layout.addWidget(select_all)
        master_layout.addStretch()
        master_layout.addWidget(QLabel(self.tr("Apply to all:")))
        master_layout.addWidget(master_combo)

        master_widget = QWidget()
        master_widget.setLayout(master_layout)
        master_widget.setStyleSheet("background-color: rgba(255, 255, 255, 0.02); padding: 6px; border-radius: 6px;")

        layout.addWidget(master_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        video_checkboxes = []
        stream_combos = []

        for video in self.playlist:
            cb = QCheckBox(video.title[:40])
            cb.setToolTip(video.title)
            video_checkboxes.append(cb)

            combo = QComboBox()
            combo.addItems(video.raw_stream_menu)
            stream_combos.append(combo)

            size = QLabel(size_format(video.total_size))

            row_container = QWidget()
            row_container.setObjectName("scroll_item_row")
            row_layout = QHBoxLayout(row_container)
            row_layout.setContentsMargins(8, 6, 8, 6)

            row_layout.addWidget(cb)
            row_layout.addStretch()
            row_layout.addWidget(combo)
            row_layout.addWidget(size)

            scroll_layout.addWidget(row_container)

        scroll_content.setLayout(scroll_layout)
        scroll.setWidget(scroll_content)
        scroll.setMinimumHeight(250)

        layout.addWidget(scroll)

        # 🟢 Instruction label
        instruction = QLabel(self.tr("Please click on the video streams to select the video resolution and then click on the checkboxes to select the video in this playlist and click on 'Download'"))
        instruction.setWordWrap(True)
        instruction.setObjectName("instruction_label")
        layout.addWidget(instruction)

        # Buttons
        buttons = QHBoxLayout()
        ok_btn = QPushButton(self.tr("Download"))
        cancel_btn = QPushButton(self.tr("Cancel"))
        buttons.addStretch()
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)

        layout.addLayout(buttons)

        def queue_or_start_download(v):
            if len(self.active_downloads) >= config.max_concurrent_downloads:
                v.status = config.Status.pending
                self.pending.append(v)
            else:
                self.start_download(v, silent=True)

        def on_ok():
            chosen = []
            for i, video in enumerate(self.playlist):
                selected = stream_combos[i].currentText()
                # video.selected_stream = video.raw_streams[selected]

                if not selected or selected not in video.raw_streams:
                    log(f"[Playlist] Skipping {video.title} — no format selected.")
                    continue  # ⬅ safely skip this video
                video.selected_stream = video.raw_streams[selected]

                if video_checkboxes[i].isChecked():
                    chosen.append(video)

            dialog.accept()

            for video in chosen:
                video.folder = config.download_folder
                QTimer.singleShot(0, lambda v=video: queue_or_start_download(v))

        def on_cancel():
            dialog.reject()

        def on_select_all():
            for cb in video_checkboxes:
                cb.setChecked(select_all.isChecked())

        def on_master_combo_change():
            selected = master_combo.currentText()
            if selected in raw_streams:
                for i, combo in enumerate(stream_combos):
                    video = self.playlist[i]
                    if selected in video.raw_streams:
                        combo.setCurrentText(selected)
                        video.selected_stream = video.raw_streams[selected]

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(on_cancel)
        select_all.stateChanged.connect(on_select_all)
        master_combo.currentTextChanged.connect(on_master_combo_change)

        if dialog.exec():
            self.change_page(btn=None, btnName=None, idx=1)


    # endregion


    # region Add-ons Check

    def ffmpeg_check(self):
        """Check if ffmpeg is available, if not, prompt user to download."""
        
        if not check_ffmpeg():
            if config.operating_system == 'Windows':
                # Create the dialog
                dialog = QDialog(self)
                dialog.setWindowTitle(self.tr('FFmpeg is missing'))
                dialog.setStyleSheet("""
                    QDialog {
                        background-color: qlineargradient(
                            x1: 0, y1: 0, x2: 1, y2: 1,
                            stop: 0 #0F1B14,
                            stop: 1 #050708
                        );
                        color: white;
                        border-radius: 14px;
                    }
                    QLabel {
                        color: white;
                        font-size: 12px;
                    }
                    QRadioButton {
                        padding: 4px;
                    }
                    
                """)

                # Layout setup
                layout = QVBoxLayout(dialog)

                # Label for missing FFmpeg
                label = QLabel(self.tr('"ffmpeg" is missing!! and needs to be downloaded:'))
                layout.addWidget(label)

                # Radio buttons for choosing destination folder
                recommended, local_fd = self.tr("Recommended:"), self.tr("Local folder:")
                recommended_radio = QRadioButton(f"{recommended} {config.global_sett_folder}")
                recommended_radio.setChecked(True)
                local_radio = QRadioButton(f"{local_fd} {config.current_directory}")

                # Group radio buttons
                radio_group = QButtonGroup(dialog)
                radio_group.addButton(recommended_radio)
                radio_group.addButton(local_radio)

                # Layout for radio buttons
                radio_layout = QVBoxLayout()
                radio_layout.addWidget(recommended_radio)
                radio_layout.addWidget(local_radio)

                layout.addLayout(radio_layout)

                # Buttons for Download and Cancel
                button_layout = QHBoxLayout()
                download_button = QPushButton(self.tr('Download'))
                download_button.setStyleSheet("""
                    QPushButton {
                        background-color: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 1,
                        stop: 0 #0F1B14,
                        stop: 1 #050708
                        ); 
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 16px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #33d47c;
                    }
                """)
                cancel_button = QPushButton(self.tr('Cancel'))
                cancel_button.setStyleSheet("""
                    QPushButton {
                        background-color: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 1,
                        stop: 0 #0F1B14,
                        stop: 1 #050708
                        ); 
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 16px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #3c3c3c;
                    }
                """)
                button_layout.addWidget(download_button)
                button_layout.addWidget(cancel_button)

                layout.addLayout(button_layout)

                # Set layout and show the dialog
                dialog.setLayout(layout)

                # Handle button actions
                def on_download():
                    selected_folder = config.global_sett_folder if recommended_radio.isChecked() else config.current_directory
                    download_ffmpeg(destination=selected_folder)
                    dialog.accept()  # Close the dialog after download

                def on_cancel():
                    dialog.reject()  # Close dialog on cancel

                # Connect button signals
                download_button.clicked.connect(on_download)
                cancel_button.clicked.connect(on_cancel)

                # Execute the dialog
                dialog.exec()

            else:
                # Show error popup for non-Windows systems
                s2 = self.tr('"ffmpeg" is required to merge an audio stream with your video.')
                s3, s3a = self.tr('Executable must be found at'), self.tr("folder or add the ffmpeg path to system PATH.")
                s4 = self.tr("Please do 'sudo apt-get update' and 'sudo apt-get install ffmpeg' on Linux or 'brew install ffmpeg' on MacOS.")
                QMessageBox.critical(self, 
                                    self.tr('FFmpeg is missing'),
                                    f'{s2} \n'
                                    f'{s3} {config.ffmpeg_actual_path_2} {s3a} \n'
                                    f"{s4}")

            return False
        else:
            return True
        

    
    
    def _browser_queue_base(self, app_name=".OmniPull") -> Path:
        home = Path.home()
        if sys.platform.startswith("win"):
            return home / "AppData" / "Roaming" / app_name
        elif sys.platform == "darwin":
            return home / "Library" / "Application Support" / app_name
        else:
            return home / ".config" / app_name

    def get_browser_queue_paths(self, app_name=".OmniPull"):
        base = self._browser_queue_base(app_name)
        return {
            "latest": base / ".omnipull_url_latest.json",
            "ndjson": base / ".omnipull_url_queue.ndjson",
        }

    def _read_latest_json(self, latest_path: Path):
        try:
            if latest_path.exists() and latest_path.stat().st_size > 0:
                with latest_path.open("r", encoding="utf-8") as f:
                    obj = json.load(f)  # expects {"url": "..."}
                url = (obj or {}).get("url")
                return url if url else None
        except Exception as e:
            # log if you have a logger
            pass
        return None

    def _read_ndjson_last(self, ndjson_path: Path):
        try:
            if not ndjson_path.exists(): return None
            last = None
            with ndjson_path.open("r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s: continue
                    last = s
            if last:
                obj = json.loads(last)
                return obj.get("url")
        except Exception:
            pass
        return None

    def check_browser_queue(self):
        if not config.browser_integration_enabled:
            return

        paths = self.get_browser_queue_paths(".OmniPull")
        url = self._read_latest_json(paths["latest"])
        if not url:
            # fallback: read the last line of NDJSON if present
            url = self._read_ndjson_last(paths["ndjson"])

        if not url:
            return

        # Process exactly one URL (the latest)
        try:
            widgets.link_input.setText(url)
            self.url_text_change()
        except Exception as e:
            log(f"Failed to inject URL from browser queue: {e}", log_level=3)
            return

        # Clear the latest file so we don't process the same URL twice
        try:
            # either empty it:
            paths["latest"].write_text("{}", encoding="utf-8")
            # and optionally truncate NDJSON to truly want "replace, don't append"
            paths["ndjson"].unlink(missing_ok=True)
        except Exception:
            pass
    
    # endregion

    # region logs out & close

    def quit_app(self):
        if hasattr(self, 'tray_manager'):
            self.tray_manager.hide()
        QApplication.quit()
    
    def _debug_threads(self, tag):
        try:
            log(f"DEBUG[{tag}] table_thread running?",
                getattr(self, "table_thread", None) and self.table_thread.isRunning())
        except Exception:
            log(f"DEBUG[{tag}] table_thread unknown (deleted)")

        if hasattr(self, "background_threads"):
            for idx, th in enumerate(list(self.background_threads)):
                try:
                    log(f"DEBUG[{tag}] bg[{idx}] {type(th).__name__} running? {th.isRunning()}")
                except Exception as e:
                    log(f"DEBUG[{tag}] bg[{idx}] invalid: {e}")

    def closeEvent(self, event):
        if event.spontaneous() and config.hide_app == True:
            self.tray_manager.handle_window_close()
            event.ignore()
        else:
            self._debug_threads("before-close")
            try:
                config.terminate = True  # used by multiple threads
                log("Application is closing, shutting down background threads...", log_level=1)
                # ---- stop table thread safely (already advised) ----
                t = getattr(self, "table_thread", None)
                if t is not None:
                    try:
                        if t.isRunning():
                            # if your worker supports it:
                            if hasattr(self, "worker") and hasattr(self.worker, "requestInterruption"):
                                try:
                                    self.worker.requestInterruption()
                                except Exception:
                                    pass
                            t.quit()
                            t.wait(5000)
                    except RuntimeError:
                        pass

                # ---- stop log recorder thread explicitly ----
                log_t = getattr(self, "log_recorder_thread", None)
                if log_t is not None:
                    try:
                        # tell it to stop via all supported paths
                        if hasattr(log_t, "stop"):
                            log_t.stop()
                        log_t.requestInterruption()
                        # quit() does nothing for custom run loops, but harmless to call
                        log_t.quit()
                        # give it a moment to flush and exit
                        log_t.wait(5000)
                    except RuntimeError:
                        pass

                # ---- generic background cleanup (keep, but make it tolerant) ----
                if hasattr(self, "background_threads"):
                    for th in list(self.background_threads):
                        try:
                            if th is None:
                                continue
                            try:
                                running = th.isRunning()
                            except RuntimeError:
                                # already deleteLater'ed
                                continue
                            if running:
                                if hasattr(th, "stop"):
                                    th.stop()
                                th.requestInterruption()
                                th.quit()
                                th.wait(5000)
                        except RuntimeError:
                            pass
                    # optional prune
                    self.background_threads = [
                        th for th in self.background_threads
                        if th is not None and hasattr(th, "isRunning") and th.isRunning()
                    ]

                if config.aria2_verified is True: aria2c_manager.cleanup_orphaned_paused_downloads(); aria2c_manager.shutdown_freeze_and_save(purge=True); aria2c_manager._terminate_existing_processes()
                self.quit_app()
                super().closeEvent(event)
                
                    
            except Exception:
                # don't block window close on errors
                try:
                    super().closeEvent(event)
                except Exception:
                    pass
            finally:
                self._debug_threads("after-close")


    # Clear Log
    def clear_log(self):
        widgets.terminal_log.clear()

    # Set Log level 
    def set_log(self):
        config.log_level = int(widgets.log_level_combo.currentText())
        log('Log Level changed to:', config.log_level, log_level=1)
        self.settings_manager.save_settings()
        

    
    

    

    # endregion

    def _queue_or_start_download(self, d, refresh_if_needed=False):
        # ✅ 1. Optionally refresh stream info if it's a video and refresh_if_needed is True
        if refresh_if_needed and isinstance(d, Video):
            try:
                if d.url_expired():
                    log(f"[Refresh] Stream info expired for {d.name}, refreshing...")
                    d.update_param()
                    d.last_update = time.time()  # Update the timestamp
                    log(f"[Refresh] Stream info updated for {d.name}")
            except Exception as e:
                log(f"[!] Failed to refresh stream info: {e}")
                show_warning(self.tr("Error"), self.tr("Could not refresh stream info"))
                return

        # ✅ 2. Fallback — if segments are missing or empty, rebuild them
        if not d.segments or len(d.segments) < 1:
            try:
                d.update(d.url)
            except Exception as e:
                log(f"[!] Failed to update download segments: {e}")
                show_warning("Error", "Unable to prepare download segments.")
                return

        # ✅ 3. Decide whether to queue or start immediately
        if len(self.active_downloads) >= config.max_concurrent_downloads:
            d.status = config.Status.pending
            self.pending.append(d)
        else:
            if config.show_download_window:
                self.download_windows[d.id] = DownloadWindow(d)
                self.download_windows[d.id].show()

            os.makedirs(d.temp_folder, exist_ok=True)
            Thread(target=brain.brain, daemon=True, args=(d,)).start()

    # region Toolbar buttons
    
    def get_video_info(self, url) -> DownloadItem:
        from yt_dlp import YoutubeDL
        """Extract fresh video/audio URLs and metadata using yt-dlp"""
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_warnings': True,
            'format': 'bestvideo+bestaudio/best',
            'forcejson': True,
            'forceurl': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        d = DownloadItem()
        d.url = info['url']
        d.name = safe_filename(info['title'])
        d.folder = os.path.join(os.getcwd(), "Downloads")  # Or user-defined folder
        d.temp_file = os.path.join(d.folder, d.name)
        d.target_file = d.temp_file + "." + get_ext_from_format(info['ext'])

        d.vid_info = info
        d.type = "dash" if '+' in info['format_id'] else "normal"
        d.protocol = info.get('protocol', 'https')
        d.eff_url = d.url

        # Handle separate audio stream
        formats = info.get('formats', [])
        best_audio = next((f for f in formats if f.get('vcodec') == 'none'), None)
        if best_audio:
            d.audio_url = best_audio['url']
            d.audio_file = os.path.join(d.folder, f"audio_for_{d.name}.{best_audio['ext']}")

        return d
    

    def _youtube_url_expired(self, url: str) -> bool:
        """Return True iff a signed YT media URL looks expired."""
        if not url:
            return True
        try:
            q = parse_qs(urlparse(url).query)
            # YouTube signed URLs often carry 'expire' epoch seconds
            if "expire" in q:
                try:
                    exp = int(q["expire"][0])
                    # allow small skew
                    return time.time() > (exp - 60)
                except Exception:
                    pass
            # Fallback: attempt a HEAD with Range; 403/410 usually means expired
            try:
                r = requests.head(url, headers={"Range": "bytes=0-0"}, timeout=6, allow_redirects=True)
                if r.status_code in (403, 410):
                    return True
                # 2xx or 206 is fine
                return False
            except Exception:
                # network issues: be conservative and refresh only if the .aria2 isn’t present
                return False
        except Exception:
            return True
    

    def resume_btn(self):
        """Resume paused or queued downloads."""

        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self.tr("Error"), self.tr("No download item selected"))
            return

        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        if d.status not in (config.Status.cancelled, config.Status.queued):
            return
        
        
        # ✅ Resume aria2c download
        if d.engine == "aria2c":
            # Only refresh signed media URLs if they are ACTUALLY expired
            needs_refresh = False
            if d.type in ("dash", "normal") and ("youtube.com" in (d.original_url or d.url) or "googlevideo.com" in (d.url or "")):
                if self._youtube_url_expired(getattr(d, "eff_url", d.url)) or (d.audio_url and self._youtube_url_expired(d.audio_url)):
                    needs_refresh = True

            if needs_refresh:
                fresh_d = self.get_video_info(d.original_url or d.url)
                # sync updated fields (keep folder/id)
                for attr in ['url','audio_url','audio_file','name','target_file','temp_file','vid_info','eff_url','protocol','type','format_id','audio_format_id']:
                    setattr(d, attr, getattr(fresh_d, attr, getattr(d, attr)))
                log(f"[Resume] Refreshed signed URLs for: {d.name}", log_level=2)

                # IMPORTANT: only wipe partials if refreshing (we are restarting)
                for f in [d.temp_file, d.temp_file + '.aria2', d.audio_file, (d.audio_file + '.aria2' if d.audio_file else None)]:
                    if f and os.path.exists(f):
                        try:
                            os.remove(f)
                            log(f"[Resume] Deleted stale file: {f}")
                        except Exception:
                            pass
                d.aria_gid = None  # let the worker add anew
                self.settings_manager.save_d_list(self.d_list)

            else:
                # DO NOT delete .aria2 or temp files; we want Range resume
                # also keep the gid if aria2 still knows it
                if getattr(d, "aria_gid", None):
                    try:
                        aria2 = aria2c_manager.get_api()
                        dl = aria2.get_download(d.aria_gid)
                        if (dl is None) or (getattr(dl, "status", "") == "removed"):
                            d.aria_gid = None
                    except Exception:
                        d.aria_gid = None

            # (Re)start worker
            Thread(target=brain.brain, args=(d,), daemon=True).start()
            log(f"[Resume] aria2c resumed: {d.name}", log_level=2)


        elif d.engine == "yt-dlp":
            # ✅ Resume yt-dlp download
            try:
                d.status = config.Status.downloading
                log(f"[Resume] yt-dlp resumed: {d.name}", log_level=1)
                Thread(target=brain.brain, args=(d,), daemon=True).start()
            except Exception as e:
                log(f"[Resume] Failed to resume yt-dlp: {e}", log_level=3)
                d.status = config.Status.error
        else:
            # ✅ Fallback: PyCURL download
            self.start_download(d, silent=True)
        
        widgets.toolbar_buttons['Pause'].setEnabled(True)
        widgets.toolbar_buttons['Resume'].setEnabled(False)

    
    

    def pause_btn(self):
        """Pause the selected download item (YT-DLP or aria2c)."""

        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self.tr("Error"), self.tr("No download item selected"))
            return

        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        # Skip completed
        if d.status == config.Status.completed:
            return

        # ✅ Aria2c pause
        # if d.engine == "aria2c" and hasattr(d, "aria_gid"):
        #     try:
        #         aria2 = aria2c_manager.get_api()
        #         download = aria2.get_download(d.aria_gid)
        #         if download:
        #             download.pause()
        #             # aria2c_manager.force_save_session()
        #             # aria2c_manager.force_clean_and_save_session()
        #             aria2c_manager.save_session_only()
        #             d.status = config.Status.cancelled
        #             time.sleep(0.5)  # Give the file_manager and thread_manager time to clean up
        #             log(f"[Pause] Aria2c paused: {d.name}", log_level=1)
        #     except Exception as e:
        #         log(f"[Pause] Failed to pause aria2c: {e}", log_level=3)
        #         d.status = config.Status.error
        # ✅ Aria2c pause (torrent-aware)
        if d.engine == "aria2c" and getattr(d, "aria_gid", None):
            try:
                aria2 = aria2c_manager.get_api()
                # Pause the whole family: parent/children/siblings
                paused = aria2c_manager.pause_family(d.aria_gid)
                if paused:
                    d.status = config.Status.cancelled  # your UI color mapping
                    log(f"[Pause] Aria2c torrent family paused: {d.name}", log_level=1)
                else:
                    # Fallback: try pausing just the single GID
                    try:
                        dl = aria2.get_download(d.aria_gid)
                        if dl:
                            dl.pause()
                            d.status = config.Status.cancelled
                    except Exception:
                        pass

                # lightweight session save (no resume_all)
                aria2c_manager.save_session_only()

            except Exception as e:
                log(f"[Pause] Failed to pause aria2c: {e}", log_level=3)
                d.status = config.Status.error

        else:
            # ✅ Fallback: yt-dlp or native downloads
            if d.status in (config.Status.downloading, config.Status.pending):
                d.status = config.Status.cancelled
                log(f"[Pause] Cancelled: {d.name}")
                if d.status == config.Status.pending:
                    self.pending.pop(d.id, None)

        widgets.toolbar_buttons['Pause'].setEnabled(False)
        widgets.toolbar_buttons['Resume'].setEnabled(True)
        # setting.save_d_list(self.d_list)
        self.settings_manager.save_d_list(self.d_list)
        self.populate_table()


    def delete_btn(self):
        """Delete selected downloads from the download table"""
        # Get all selected rows
        selected_rows = [index.row() for index in widgets.table.selectedIndexes()]
        selected_rows = list(set(selected_rows))  # Remove duplicates, as some items may be selected in multiple columns

        if not selected_rows:
            return

        # Ensure no downloads are active
        if self.active_downloads:
            show_critical(self.tr("Error"), self.tr("Can't delete items while downloading. Stop or cancel all downloads first!"))
            return
        
        # Prepare the warning message
        warn, asf = self.tr("Warning!!!"), self.tr("Are you sure you want to delete these items?")
        msg = f"{warn}\n {asf}?"
        
        confirmation_box = QMessageBox(self)
        confirmation_box.setStyleSheet(get_msgbox_style("information"))
        confirmation_box.setWindowTitle(self.tr('Delete files?'))
        confirmation_box.setText(msg)
        confirmation_box.setIcon(QMessageBox.Question)
        confirmation_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reply = confirmation_box.exec()

        if reply != QMessageBox.Yes:
            return

        try:
            # Sort the rows in reverse order to avoid issues with shifting rows when deleting
            selected_rows.sort(reverse=True)
            
            # Remove each selected item from the list and table
            for row in selected_rows:
                d_index = len(self.d_list) - 1 - row  # since we're reversing in the table
                d = self.d_list.pop(d_index)


                # Update the remaining items' IDs
                for i, item in enumerate(self.d_list):
                    item.id = i

                # Log the deleted item (for debugging)
                log(f"D:  {d}")

                # Remove the row from the table
                widgets.table.removeRow(row)

                # Notify user about the deleted file
                nt1, nt2 = self.tr("File:"), self.tr("has been deleted.")
                notification = f"{nt1} {d.name} {nt2}"
                notify(notification, title=f'{config.APP_NAME}')

                # Clean up the deleted item
                # d.delete_tempfiles()
                # os.remove(f"{d.folder}/{d.name}")
                self.janitor(d)
                widgets.table.clearSelection()
                self.update_toolbar_buttons_for_selection()

        except Exception as e:
            log(f"Error deleting items: {e}", log_level=3)

    
    def janitor(self, d):
        """Delete all related files of the download item (aria2c, yt-dlp, curl, .torrent, temp, parts dirs, etc.) WITHOUT touching unrelated folders/files."""
        import os, glob, shutil, re

        def _log_ok(msg):  log(msg)
        def _log_err(msg): log(msg, log_level=2)

        def _rm_file(path):
            try:
                if path and os.path.isfile(path) and os.path.exists(path):
                    os.remove(path)
                    _log_ok(f"[Janitor] Removed file: {path}")
            except Exception as e:
                _log_err(f"[Janitor] Failed to remove file: {path} ({e})")

        def _rm_glob(pattern):
            for p in glob.glob(pattern):
                _rm_file(p)

        def _rmtree(path):
            try:
                if path and os.path.isdir(path) and os.path.exists(path):
                    shutil.rmtree(path, ignore_errors=False)
                    _log_ok(f"[Janitor] Removed directory: {path}")
            except Exception as e:
                _log_err(f"[Janitor] Failed to remove directory: {path} ({e})")

        def _norm_title(s: str) -> str:
            base = os.path.splitext(os.path.basename(s))[0]
            base = base.lower()
            base = re.sub(r'[^a-z0-9]+', '_', base)
            base = re.sub(r'_+', '_', base).strip('_')
            return base

        def _belongs_to_stem(name: str, stems_norm: set[str]) -> bool:
            """Return True iff the filename/dirname (sans-ext, normalized) looks like it's for this item."""
            n = _norm_title(name)
            # exact or prefix/suffix relation (covers _temp_<stem>... and ...<stem>_parts_)
            return any(n == s or n.startswith(s + "_") or n.endswith("_" + s) or s in n for s in stems_norm)

        try:
            # --- 0) Build roots and stems -----------------------------------------
            main_file = os.path.join(d.folder, d.name)

            # Folders to search (only where this item actually wrote files)
            roots = set()
            for base in [
                main_file,
                getattr(d, "temp_file", ""),
                getattr(d, "audio_file", ""),
                getattr(d, "target_file", ""),
            ]:
                if base:
                    roots.add(os.path.dirname(base) or d.folder)
            temp_folder = getattr(d, "temp_folder", None)
            if temp_folder:
                roots.add(temp_folder)

            # Stems (with/without ext) + normalized variants
            stems_raw = set()
            for base in [main_file, getattr(d, "temp_file", ""), getattr(d, "audio_file", ""), getattr(d, "target_file", "")]:
                if not base:
                    continue
                fname = os.path.basename(base)       # e.g. "Title.mp4"
                stem_noext, _ext = os.path.splitext(fname)
                stems_raw.add(fname)                 # with ext
                stems_raw.add(stem_noext)            # without ext

            stems_norm = { _norm_title(s) for s in stems_raw if s }

            # --- 1) Let the item clear its tempfiles first ------------------------
            try:
                d.delete_tempfiles()
            except Exception as e:
                _log_err(f"[Janitor] delete_tempfiles() failed: {e}")

            # --- 2) Remove primary files ------------------------------------------
            _rm_file(main_file)
            for base in [getattr(d, "target_file", ""), getattr(d, "temp_file", ""), getattr(d, "audio_file", "")]:
                if base and os.path.abspath(base) != os.path.abspath(main_file):
                    _rm_file(base)

            # --- 3) aria2c sidecars ------------------------------------------------
            aria_suffixes_exact = [".aria2", ".aria2.resume", ".aria2.log", ".meta", ".mtd"]
            for root in list(roots):
                for stem in list(stems_raw):
                    for suf in aria_suffixes_exact:
                        _rm_file(os.path.join(root, f"{stem}{suf}"))
                    _rm_glob(os.path.join(root, f"{stem}.aria2*"))
                    _rm_glob(os.path.join(root, f"{stem}.mtd*"))
                    _rm_glob(os.path.join(root, f"{stem}.meta*"))

            # --- 4) yt-dlp artifacts (strict to stems) -----------------------------
            yt_suffix_patterns = [
                ".part", ".part-*", ".f*", ".ytdl", ".ytdl-part", ".ytdl.*",
                ".info", ".info.json", ".description", ".annotations.xml",
                ".thumb", ".jpg", ".jpeg", ".png", ".webp",
                ".srt", ".vtt", ".lrc",
            ]
            for root in list(roots):
                for stem in list(stems_raw):
                    for suf in yt_suffix_patterns:
                        _rm_glob(os.path.join(root, f"{stem}{suf}"))

            # --- 5) STRICT temp/parts folders (only if they BELONG to this item) ---
            # Allowed folder name forms to try for each stem (raw + normalized)
            #   _temp_<stem>..._parts_   (curl style)
            #   <stem>_parts_
            #   <stem>.temp
            #   <stem>_temp
            for root in list(roots):
                # Scan only directories in root and test them against stems_norm
                try:
                    entries = [e for e in glob.glob(os.path.join(root, "*")) if os.path.isdir(e)]
                except Exception:
                    entries = []

                for dpath in entries:
                    dname = os.path.basename(dpath)
                    if not _belongs_to_stem(dname, stems_norm):
                        continue  # skip unrelated directories

                    # Safety: if dir contains files that clearly don't belong to this stem, skip deletion
                    try:
                        foreign = False
                        for p in glob.glob(os.path.join(dpath, "**"), recursive=True):
                            if os.path.isdir(p):
                                continue
                            base = os.path.basename(p)
                            if not _belongs_to_stem(base, stems_norm):
                                foreign = True
                                break
                        if foreign:
                            continue
                    except Exception:
                        # if we can't scan, fall back to delete (you can change to 'continue' if you prefer ultra-safety)
                        pass

                    _rmtree(dpath)

            # --- 6) .watch helper files -------------------------------------------
            for root in list(roots):
                for stem in list(stems_raw):
                    _rm_file(os.path.join(root, f"{stem}.watch"))
                    _rm_glob(os.path.join(root, f"{stem}.watch.*"))

            # --- 7) .torrent cleanup ----------------------------------------------
            for root in list(roots):
                for stem in list(stems_raw):
                    _rm_file(os.path.join(root, f"{stem}.torrent"))
                    _rm_glob(os.path.join(root, f"{stem}.torrent.*"))

            if main_file.lower().endswith(".torrent"):
                _rm_file(main_file)
                paired = main_file[:-8]  # remove ".torrent"
                _rm_file(paired)

            # --- 8) Generic loose leftovers (strict to stems) ---------------------
            loose_suffixes = [".tmp", ".temp", ".download"]
            for root in list(roots):
                for stem in list(stems_raw):
                    for suf in loose_suffixes:
                        _rm_file(os.path.join(root, f"{stem}{suf}"))

            _log_ok(f"[Janitor] Cleanup completed for: {d.name}")

        except Exception as e:
            log(f"[Janitor] General error cleaning up files for {getattr(d, 'name', '?')}: {e}", log_level=3)

    
    
    def delete_all_downloads(self):
        """Delete all downloads on the download table"""

        # Check if there are any active downloads
        if self.active_downloads:
            show_critical(
                self.tr("Error"),
                self.tr("Can't delete items while downloading. Stop or cancel all downloads first!")
            )
            return

        # Confirmation dialog - user has to write "delete" to proceed
        dai = self.tr("Delete all items and their progress temp files")
        ttw = self.tr("Type the word 'delete' and hit OK to proceed.")
        msg = f'{dai} \n\n{ttw}'

        input_dialog = QInputDialog(self)
        input_dialog.setStyleSheet(get_msgbox_style("inputdial"))
        input_dialog.setWindowTitle(self.tr("Warning!!"))
        input_dialog.setLabelText(msg)
        input_dialog.setTextValue("")  # empty by default

        ok = input_dialog.exec()  # Show the dialog

        if not ok or input_dialog.textValue().strip().lower() != 'delete':
            return

        # Log the deletion process
        log('Start deleting all download items', log_level=2)

        self.stop_all_downloads()
        self.selected_row_num = None
        n = len(self.d_list)

        for i in range(n):
            d = self.d_list[i]
            self.janitor(d)
            Thread(target=d.delete_tempfiles, daemon=True).start()

        self.d_list.clear()
        widgets.table.setRowCount(0)
    
    def refresh_link_btn(self):
        """Refresh a download list item for a re-download or resume especially for streaming media"""
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self.tr("Error"), self.tr("No download item selected"))
            return

        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        config.download_folder = d.folder
        # widgets.link_input.setText(d.url)
        widgets.link_input.setText(d.original_url if d.engine in ['aria2c', 'aria2'] else d.url)


        self.url_text_change()
        widgets.folder_input.setText(config.download_folder)

        self.change_page(btn=None, btnName=None, idx=0)
        log(f"Link refreshing for {d.name} at index {d_index}", log_level=1)


    def stop_all_downloads(self):
        """Stop (cancel) all active downloads but leave scheduled/completed/queued untouched."""
        active_downloads = [
            d for d in self.d_list
            if d.status in (config.Status.downloading, config.Status.pending, config.Status.merging_audio)
        ]

        if not active_downloads:
            show_information(self.tr("Stop All"), self.tr("There are no active downloads to stop."), "")
            return

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle(self.tr("Stop All Downloads?"))
        sad1, sad2 = self.tr('Some downloads are currently active (Downloading, Pending, Merging).'), self.tr('Do you want to stop all?')
        msg_box.setText(f"{sad1} \n\n {sad2}")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setStyleSheet(get_msgbox_style('question'))


        reply = msg_box.exec()

        if reply == QMessageBox.Yes:
            for d in active_downloads:
                d.status = config.Status.cancelled
            self.pending.clear()

            # setting.save_d_list(self.d_list)
            self.populate_table()
            show_information(self.tr("Stopped"), self.tr("All active downloads have been cancelled."), "")


    def resume_all_downloads(self):
        """Resume all downloads that were previously cancelled or failed."""
        targets = [d for d in self.d_list if d.status in (config.Status.cancelled, config.Status.error, config.Status.failed)]
        for d in targets:
            self.start_download(d, silent=True)
        


    def schedule_all(self):
        # Filter downloads eligible for scheduling
        schedulable = [d for d in self.d_list if d.status in (config.Status.pending, config.Status.cancelled)]

        if not schedulable:
            show_information(
                self.tr("No Downloads to Schedule"),
                self.tr("No valid downloads found."),
                self.tr("There are currently no downloads with status 'Pending' or 'Cancelled' that can be scheduled.")
            )
            return

        try:
            response = ask_for_sched_time(self.tr('Download scheduled for...'))

            if response:
                for d in schedulable:
                    d.sched = response
                    d.status = config.Status.scheduled
                    log(f'Scheduled {d.name} for {response[0]}:{response[1]}')

                self.queue_update("populate_table", None)

        except Exception as e:
            log(f'Error in scheduling: {e}', log_level=3)
            show_warning(self.tr("Schedule Error"), str(e))

    def download_window(self):
        selected_row = widgets.table.currentRow()
        
        if selected_row < 0 or selected_row >= len(self.d_list):
            show_warning(self.tr("Error"), self.tr("No download item selected"))
        # Set selected_row_num to the selected row
        self.selected_row_num = selected_row

        if self.selected_d:
            if config.auto_close_download_window and self.selected_d.status != config.Status.downloading:
                msg1, msg2 = self.tr("To open download window offline"), self.tr("go to setting tab, then uncheck auto close download window")
                show_information(title=self.tr('Information'),inform="", msg=f"{msg1} \n {msg2}")
                
            else:
                d = self.selected_d
                if d.id not in self.download_windows:
                    self.download_windows[d.id] = DownloadWindow(d=d)
                else:
                    self.download_windows[d.id].focus()
    
    def open_settings(self):
        dialog = SettingsWindow(self)
        if dialog.exec():
            self.queue_updates()
   
   
    def show_queue_dialog(self):
        self.ui_queues.d_list = self.d_list  # Update d_list for the dialog
        self.ui_queues.populate_queue_items()
        self.ui_queues.exec() # Show the existing instance

    # endregion



    # region Table Control

    @property
    def selected_d(self):
        self._selected_d = self.d_list[self.selected_row_num] if self.selected_row_num is not None else None
        return self._selected_d

    @selected_d.setter
    def selected_d(self, value):
        self._selected_d = value

    def populate_table(self):
        # If a previous table thread is still running, stop it first
        t = getattr(self, "table_thread", None)
        if t is not None:
            try:
                if t.isRunning():
                    t.quit()
                    t.wait(5000)
            except RuntimeError:
                pass

        self.table_thread = QThread(self)  # parent = self
        self.worker = PopulateTableWorker(self.d_list)
        self.worker.moveToThread(self.table_thread)

        self.table_thread.started.connect(self.worker.run)
        self.worker.data_ready.connect(self.populate_table_apply)
        self.worker.finished.connect(self.table_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.table_thread.finished.connect(self.table_thread.deleteLater)
        

        self.table_thread.start()

    @Slot(list)
    def populate_table_apply(self, prepared_rows):
        """Apply the populated data to the GUI."""
        widgets.table.setRowCount(len(prepared_rows))

        for row_idx, row_data in enumerate(prepared_rows):

            # ID
            id_item = QTableWidgetItem(str(len(prepared_rows) - row_idx))
            id_item.setData(Qt.UserRole, row_data['id'])
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            widgets.table.setItem(row_idx, 0, id_item)

            # Name
            name_item = QTableWidgetItem(validate_file_name(row_data['name']))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            widgets.table.setItem(row_idx, 1, name_item)

            # Progress Bar (column 2)
            progress = widgets.table.cellWidget(row_idx, 2)
            if not isinstance(progress, QProgressBar):
                progress = QProgressBar()
                progress.setRange(0, 100)
                progress.setTextVisible(True)
                progress.setStyleSheet("""
                    QProgressBar {
                        background-color: #2a2a2a;
                        border: 1px solid #444;
                        border-radius: 4px;
                        text-align: center;
                        color: white;
                    }
                    QProgressBar::chunk {
                        background-color: #00C853;
                        border-radius: 4px;
                    }
                """)
                widgets.table.setCellWidget(row_idx, 2, progress)

            progress.setValue(int(row_data['progress']))
            progress.setFormat(f"{int(row_data['progress'])}%")

            # Speed
            speed_item = QTableWidgetItem(size_format(row_data['speed'], '/s') if row_data['speed'] else "")
            speed_item.setFlags(speed_item.flags() & ~Qt.ItemIsEditable)
            widgets.table.setItem(row_idx, 3, speed_item)

            # Time Left
            time_item = QTableWidgetItem(str(time_format(row_data['time_left'])))
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            widgets.table.setItem(row_idx, 4, time_item)

            # Downloaded
            downloaded_item = QTableWidgetItem(size_format(row_data['downloaded']) if row_data['downloaded'] else "")
            downloaded_item.setFlags(downloaded_item.flags() & ~Qt.ItemIsEditable)
            widgets.table.setItem(row_idx, 5, downloaded_item)

            # Total Size
            total_size_item = QTableWidgetItem(size_format(row_data['total_size']) if row_data['total_size'] else "")
            total_size_item.setFlags(total_size_item.flags() & ~Qt.ItemIsEditable)
            widgets.table.setItem(row_idx, 6, total_size_item)

            # Status
            status_item = QTableWidgetItem(row_data['status'])
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            widgets.table.setItem(row_idx, 7, status_item)

            # "i" Column
            i_item = QTableWidgetItem(row_data['i'])
            i_item.setFlags(i_item.flags() & ~Qt.ItemIsEditable)
            i_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
            widgets.table.setItem(row_idx, 8, i_item)

        # setting.save_d_list(self.d_list)
        self.settings_manager.save_d_list(self.d_list)
        self.table_thread.quit()


    def update_table_progress(self):
        for row in range(widgets.table.rowCount()):
            try:
                id_item = widgets.table.item(row, 0)
                if not id_item:
                    continue

                download_id = id_item.data(Qt.UserRole)
                d = next((x for x in self.d_list if x.id == download_id), None)
                if not d:
                    continue
                progress_widget = widgets.table.cellWidget(row, 2)
                if isinstance(progress_widget, QProgressBar):
                    if d.progress is not None:
                        progress_widget.setValue(int(d.progress))
                        progress_widget.setFormat(f"{int(d.progress)}%")

                        # Change bar color based on status
                        color = "#00C853"  # default: green
                        if d.status == "downloading":
                            color = "#2962FF"
                        elif d.status == "completed":
                            color = "#00C853"
                        elif d.status == "cancelled":
                            color = "#D32F2F"
                        elif d.status == "pending":
                            color = "#FDD835"
                        elif d.status == "error":
                            color = "#9E9E9E"
                        elif d.status == "merging_audio":
                            color = "#FF9800"
                        elif d.status == "scheduled":
                            color = "#F7DC6F"
                        elif d.status == "queued":
                            color = "#9C27B0"  # purple
                        

                    elif d.progress is None:
                        if d.status == "queued":
                            color = "#9C27B0"
                        elif d.status == "error":
                            color = "#9E9E9E"
                    progress_widget.setStyleSheet(f"""
                        QProgressBar {{
                            background-color: #2a2a2a;
                            border: 1px solid #444;
                            border-radius: 4px;
                            text-align: center;
                            color: white;
                        }}
                        QProgressBar::chunk {{
                            background-color: {color};
                            border-radius: 4px;
                        }}
                    """)

            except Exception as e:
                log(f"Error updating progress bar at row {row}: {e}", log_level=3)

    

    def setup_context_menu_actions(self):
        def create_action(icon_path, text, shortcut, slot):
            action = QAction(QIcon(icon_path), self.tr(text), self)
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ApplicationShortcut)
            action.triggered.connect(slot)
            self.addAction(action)
            return action

        self.action_open_file = create_action(":/icons/cil-file.png", self.tr("Open File"), "Ctrl+O", self.open_item)
        self.action_open_file_with = create_action(":/icons/cil-file.png", self.tr("Open File With"), "Ctrl+A", self.open_item_with)
        self.action_open_location = create_action(":/icons/folder.png", self.tr("Open File Location"), "Ctrl+L", self.open_file_location)
        self.action_watch_downloading = create_action(":/icons/vlc.svg", self.tr("Watch while downloading"), "Ctrl+W", self.watch_downloading)
        self.action_schedule_download = create_action(":/icons/schedule.svg", self.tr("Schedule download"), "Ctrl+S", self.schedule_download)
        self.action_cancel_schedule = create_action(":/icons/cancel-schedule.svg", self.tr("Cancel schedule!"), "Ctrl+C", self.cancel_schedule)
        self.action_remerge = create_action(":/icons/ffmpeg.svg", self.tr("Re-merge audio/video"), "Ctrl+M", self.remerge_audio_video)
        self.action_file_properties = create_action(":/icons/info.svg", self.tr("File Properties"), "Ctrl+P", self.file_properties)
        self.action_add_to_queue = create_action(":/icons/add-queue.svg", self.tr("Add to Queue"), "Ctrl+Q", self.add_to_queue_from_context)
        self.action_remove_from_queue = create_action(":/icons/remove-queue.svg", self.tr("Remove from Queue"), "Ctrl+R", self.remove_from_queue_from_context)
        self.action_file_checksum = create_action(":/icons/info.svg", self.tr("File CheckSum!"), "Ctrl+H", self.start_file_checksum)
        self.action_pop_file_from_table = create_action(":/icons/trash.svg", self.tr("Delete from Table"), "Ctrl+D", self.pop_download_item)

        
    def is_playable_media(self, d):
        """Check if download item has a playable media extension."""
        media_exts = {"mp4", "webm", "mkv", "avi", "mov", "flv", "ts"}
        return bool(d and d.ext and d.ext.lower() in media_exts and d.progress >= 30)
    
    


    def context_menu_actions_state(self, status: str, d=None) -> dict:
        return {
            "open_file": status == "completed",
            "open_file_with": status == "completed",
            "open_location": status == "completed",
            "watch": bool(status in {"downloading", "paused", "pending"} and self.is_playable_media(d)),
            "schedule": status in {"paused", "pending", "cancelled", "error", "failed", "deleted"},
            "cancel_schedule": status in {"scheduled", "pending", "downloading", "paused"},
            "pop_download_item": status not in {"downloading", "pending", "merging_audio", "paused", "queued"},
            "remerge": bool(status in {"error"} and self.is_playable_media(d)),
            "add_to_queue": status == "cancelled" and (d is not None) and (not d.in_queue),
            "remove_from_queue": status == "queued" and (d is not None) and d.in_queue,
            "properties": True,
            "file_checksum": status == "completed" and os.path.exists(d.target_file)
        }

    def update_context_menu_actions_state(self, d):
        states = self.context_menu_actions_state(d.status, d)
        self.action_open_file.setEnabled(states["open_file"])
        self.action_open_file_with.setEnabled(states["open_file_with"])
        self.action_open_location.setEnabled(states["open_location"])
        self.action_watch_downloading.setEnabled(states["watch"])
        self.action_schedule_download.setEnabled(states["schedule"])
        self.action_cancel_schedule.setEnabled(states["cancel_schedule"])
        self.action_add_to_queue.setEnabled(states["add_to_queue"])
        self.action_remove_from_queue.setEnabled(states["remove_from_queue"])
        self.action_remerge.setEnabled(states["remerge"])
        self.action_file_properties.setEnabled(states["properties"])
        self.action_file_checksum.setEnabled(states["file_checksum"])
        self.action_pop_file_from_table.setEnabled(states["pop_download_item"])  

    def show_table_context_menu(self, pos: QPoint):
        index = widgets.table.indexAt(pos)
        if not index.isValid():
            return

        id_item = widgets.table.item(index.row(), 0)
        if not id_item:
            return

        download_id = id_item.data(Qt.UserRole)
        d = next((x for x in self.d_list if x.id == download_id), None)
        if not d:
            return

        # Update state before showing menu
        self.update_context_menu_actions_state(d)

        context_menu = QMenu(widgets.table)
        context_menu.setStyleSheet("""
            background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
            );
            color: white;
            border-radius: 14px;                                 
        """)
        context_menu.addAction(self.action_open_file)
        context_menu.addAction(self.action_open_location)
        context_menu.addAction(self.action_open_file_with)
        context_menu.addAction(self.action_watch_downloading)
        context_menu.addAction(self.action_schedule_download)
        context_menu.addAction(self.action_cancel_schedule)
        context_menu.addAction(self.action_pop_file_from_table) 
        context_menu.addSeparator()
        context_menu.addAction(self.action_add_to_queue)
        context_menu.addAction(self.action_remove_from_queue)
        context_menu.addAction(self.action_remerge)
        context_menu.addSeparator()
        context_menu.addAction(self.action_file_checksum)
        context_menu.addAction(self.action_file_properties)
        context_menu.exec(widgets.table.viewport().mapToGlobal(pos))

    def open_item(self):
        selected_row = widgets.table.currentRow()

        self.selected_row_num = len(self.d_list) - 1 - selected_row

        try:
            if self.selected_d.status == config.Status.completed:
                # Create and start the file opening thread
                self.file_open_thread = FileOpenThread(self.selected_d.target_file, self)

                # Connect the thread's signal to a slot in the main window to show the message
                self.file_open_thread.critical_signal.connect(show_critical)
                # Start the thread
                self.file_open_thread.start()
                # Append the thread to background_threads so it can be closed gracefully
                self.background_threads.append(self.file_open_thread)

                log(f"Opening completed file: {self.selected_d.target_file}", log_level=1)
            elif self.selected_d.status == config.Status.deleted:
                show_critical(self.tr('File Not Found'), self.tr("The selected file could not be found or has been deleted."))
            else:
                show_warning(self.tr("Warning!!!"), self.tr("This download is not yet completed"))
        except Exception as e:
            log(f"Error opening file: {e}")

    
    def open_item_with(self):
        selected_row = widgets.table.currentRow()
        self.selected_row_num = len(self.d_list) - 1 - selected_row

        try:
            file_path = self.selected_d.target_file
            if not os.path.exists(file_path):
                oiw = self.tr('The file does not exist:')
                show_critical(self.tr("File Not Found"), f"{oiw} \n{file_path}")
                return

            if self.selected_d.status == config.Status.completed:
                system_platform = platform.system().lower()

                if "windows" in system_platform:
                    try:
                        success = open_with_dialog_windows(self, file_path)
                        if not success:
                            log(f"[Open With Dialog] Failed for: {file_path}", log_level=3)
                    except Exception as e:
                        log(f"Error showing Open With dialog: {e}", log_level=3)
                else:
                    # Fallback for Linux/macOS — just open normally
                    self.file_open_thread = FileOpenThread(file_path, self)
                    self.file_open_thread.critical_signal.connect(show_critical)
                    self.file_open_thread.start()
                    self.background_threads.append(self.file_open_thread)
                    log(f"[Open] Fallback open: {file_path}", log_level=1)

            elif self.selected_d.status == config.Status.deleted:
                show_critical(self.tr("File Not Found"), self.tr("The selected file has been deleted."))
            else:
                show_warning(self.tr("Warning"), self.tr("This download is not yet completed."))
        except Exception as e:
            log(f"Error opening file: {e}", log_level=3)


    def watch_downloading(self):
        selected_row = widgets.table.currentRow()
        self.selected_row_num = len(self.d_list) - 1 - selected_row

        try:
            d = self.selected_d

            if 'm3u8' in (d.protocol or '') and (not getattr(d, "temp_file", None) or not os.path.exists(d.temp_file)):
                import time
                for _ in range(10):  # up to ~1s
                    if getattr(d, "temp_file", None) and os.path.exists(d.temp_file):
                        break
                    time.sleep(0.1)

            if not d or not getattr(d, "temp_file", None) or not os.path.exists(d.temp_file):
                show_warning(self.tr("No Temp File"), self.tr("The temporary media file was not found yet."))
                return

            if getattr(d, "progress", 0) < 30:
                show_warning(self.tr("Too Early"), self.tr("Please wait until at least '30%' is downloaded before watching."))
                return

            src = d.temp_file
            base_watch = src + ".watch"  # preferred name

            # Helper: atomic refresh copy; if locked, create a new unique name
            def _atomic_refresh_copy(src_path: str, dst_path: str) -> str:
                """
                Try to copy src -> dst atomically (copy to dst.tmp then os.replace).
                If os.replace fails (e.g., dst is locked by player), create a new unique path and copy there.
                Returns the path actually copied to.
                """
                folder = os.path.dirname(dst_path)
                tmp = dst_path + ".tmp"

                # Ensure parent exists
                os.makedirs(folder, exist_ok=True)

                try:
                    shutil.copy2(src_path, tmp)
                    os.replace(tmp, dst_path)  # atomic on Windows/NTFS and POSIX
                    return dst_path
                except Exception as e:
                    # Clean up tmp (best-effort)
                    try:
                        if os.path.exists(tmp):
                            os.remove(tmp)
                    except Exception:
                        pass

                    # Destination likely locked by player; create a new unique file name
                    n = 2
                    while True:
                        alt = f"{dst_path}.{n}"
                        try:
                            shutil.copy2(src_path, alt)
                            return alt
                        except Exception as e2:
                            n += 1
                            if n > 50:
                                raise e2

            # Always refresh the watch copy so it represents latest bytes
            watch_path = _atomic_refresh_copy(src, base_watch)

            # Launch (always use the path we actually copied to)
            self.file_open_thread = FileOpenThread(watch_path, self)
            self.file_open_thread.start()
            self.background_threads.append(self.file_open_thread)
            log(f"Watching in-progress copy: {watch_path}", log_level=1)

        except Exception as e:
            log(f"Error watching in-progress download: {e}", log_level=3)

    

    def open_file_location(self):
        selected_row = widgets.table.currentRow() 
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self.tr("Error"), self.tr("No download item selected"))
            return

        # Set selected_row_num to the selected row
        self.selected_row_num = len(self.d_list) - 1 - selected_row

        d = self.selected_d

        try:
            folder = os.path.abspath(d.folder)
            
            
            file = d.target_file

            if config.operating_system == 'Windows':
                if not os.path.isfile(file):
                    os.startfile(folder)
                else:
                    cmd = f'explorer /select, "{file}"'
                    run_command(cmd)
            else:
                # linux
                cmd = f'xdg-open "{folder}"'
                # os.system(cmd)
                run_command(cmd)
        except Exception as e:
            handle_exceptions(e)


    def schedule_download(self):
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self.tr("Error"), self.tr("No download item selected"))
            return

        # Set selected_row_num to the selected row
        self.selected_row_num = len(self.d_list) - 1 - selected_row

        response = ask_for_sched_time(msg=self.selected_d.name)
        if response:
            # setting.save_d_list(self.d_list)
            self.settings_manager.save_d_list(self.d_list)
            self.selected_d.status = config.Status.scheduled
            self.selected_d.sched = response

    
    def cancel_schedule(self):
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self.tr("Error"), self.tr("No download item selected"))
            return

        # Set selected_row_num to the selected row
        self.selected_row_num = len(self.d_list) - 1 - selected_row
        
        self.selected_d.sched = None
        self.selected_d.status = config.Status.cancelled

    def file_properties(self):
        selected_row = widgets.table.currentRow()
        
        # Set selected_row_num to the selected row
        self.selected_row_num = len(self.d_list) - 1 - selected_row

        d = self.selected_d
        if d:
            d_name = self.tr("Name:")
            d_folder = self.tr("Folder:")
            d_engine = self.tr("Download Engine:")
            d_progress = self.tr("Progress:")
            d_total_size = self.tr("Total size:")
            d_status = self.tr("Status:")
            d_resumable = self.tr("Resumable:")
            d_type = self.tr("Type:")
            d_protocol = self.tr("Protocol:")
            d_webpage_url = self.tr("Webpage url:")

            text = f'{d_name} {d.name} \n' \
                f'{d_folder} {d.folder} \n' \
                f'{d_engine} {d.engine} \n'  \
                f'{d_progress} {d.progress}% \n' \
                f'{d_total_size} {size_format(d.downloaded)} \n' \
                f'{d_total_size} {size_format(d.total_size)} \n' \
                f'{d_status} {d.status} \n' \
                f'{d_resumable} {d.resumable} \n' \
                f'{d_type} {d.type} \n' \
                f'{d_protocol} {d.protocol} \n' \
                f"{d_webpage_url} {d.original_url if d.engine in ['aria2c', 'aria2'] else d.url}"
            show_information(self.tr("File Properties"), inform="", msg=f"{text}")

    def add_to_queue_from_context(self):
        selected_items = widgets.table.selectedItems()
        if not selected_items:
            show_warning(self.tr("No Selection"), self.tr("Please select a download to add to the queue."))
            return

        selected_row = selected_items[0].row()
        id_item = widgets.table.item(selected_row, 0)
        download_id = id_item.data(Qt.UserRole)
        d = next((x for x in self.d_list if x.id == download_id), None)
        if not d:
            return

        if d.type in ["dash", "m3u8", "hls", "streaming", "youtube"]:
            show_critical(title=self.tr("Streaming Downloads"), msg=self.tr("Streaming or YouTube downloads cannot be added to Queues"))
            return

        if not self.queues:
            show_warning(
                title=self.tr("No Queues Available"),
                msg=self.tr("You haven't created any queues yet. Please create one from the Queue Manager.")
            )
            return

        queue_names = [q["name"] for q in self.queues]

        dialog = QInputDialog(self)
        dialog.setWindowTitle(self.tr("Select Queue"))
        dialog.setLabelText(self.tr("Choose a queue to add to:"))
        dialog.setComboBoxItems(queue_names)
        dialog.setStyleSheet(get_msgbox_style("inputdial"))

        if dialog.exec() == QInputDialog.Accepted:
            queue_name = dialog.textValue()
            if queue_name:
                d.in_queue = True
                d.queue_name = queue_name
                d.queue_id = self.get_queue_id(queue_name)
                d.status = config.Status.queued

                existing_positions = [
                    item.queue_position for item in self.d_list
                    if item.in_queue and item.queue_name == queue_name
                ]
                d.queue_position = max(existing_positions, default=0) + 1

                # setting.save_d_list(self.d_list)
                # setting.save_queues(self.queues)
                self.settings_manager.save_queues(self.queues)
                self.populate_table()
                self.refresh_table_row(d)

    def remove_from_queue_from_context(self):
        selected_items = widgets.table.selectedItems()
        if not selected_items:
            show_warning(self.tr("No Selection"), self.tr("Please select a download to remove from the queue."))
            return

        selected_row = selected_items[0].row()
        id_item = widgets.table.item(selected_row, 0)
        download_id = id_item.data(Qt.UserRole)
        d = next((x for x in self.d_list if x.id == download_id), None)
        if not d:
            return

        d.in_queue = False
        d.queue_name = ""
        d.queue_id = ""
        d.queue_position = 0
        d.status = config.Status.cancelled

        # setting.save_d_list(self.d_list)
        self.populate_table()
        self.refresh_table_row(d)
        
   

    # --- helper: safest way to pick an output extension consistent with input ---
    

    def _find_audio_file_for(self, d) -> str | None:
        """
        Priority:
        1) exact "audio_for_<TITLE>.*" using normalized d.name
        2) scan folder for files starting 'audio_for_' and pick the one whose <TITLE> matches d.name best
        3) if d.audio_file exists, use it (legacy)
        """
        folder = getattr(d, 'folder', None) or os.path.dirname(getattr(d, 'target_file', '') or getattr(d, 'temp_file', '') or '')
        if not folder:
            return None

        # 3) Legacy explicit field (kept but lowered in priority to prefer user's new convention)
        explicit = getattr(d, 'audio_file', None)
        if explicit and os.path.exists(explicit):
            # we will still try convention first; fallback to explicit later
            pass

        title_norm = _norm_title(getattr(d, 'name', '') or os.path.basename(getattr(d, 'target_file', '') or ''))
        video_candidates, audio_candidates = _expected_paths(folder, title_norm)

        # 1) Exact by normalized title
        audio = _best_existing(audio_candidates)
        if audio:
            return audio

        # 2) Scan folder for any audio_for_*.* and choose the best title match
        pattern = os.path.join(folder, "audio_for_*.*")
        candidates = [p for p in glob.glob(pattern) if os.path.isfile(p)]
        if candidates:
            # compute normalized titles and compare to title_norm
            scored = []
            for p in candidates:
                t = _extract_title_from_pattern(p, "audio_for_") or ""
                # Higher score for exact match; otherwise Jaccard-like overlap on tokens
                if t == title_norm:
                    score = 100
                else:
                    a = set(title_norm.split('_'))
                    b = set(t.split('_'))
                    inter = len(a & b)
                    score = inter
                scored.append((score, p))
            if scored:
                scored.sort(key=lambda x: (-x[0], -os.path.getsize(x[1]), x[1]))
                if scored[0][0] > 0:
                    return scored[0][1]

        # 3) Fallback to explicit
        if explicit and os.path.exists(explicit):
            return explicit

        return None

    def _find_video_file_for(self, d, audio_path: str | None) -> str | None:
        """
        Priority:
        1) exact "_temp_<TITLE>.*" using normalized d.name
        2) if not found, use d.target_file when it exists and looks like video-only
        3) scan folder for _temp_* candidates and pick best title match
        4) scan folder for <TITLE>.* large media if still missing
        """
        folder = getattr(d, 'folder', None) or os.path.dirname(getattr(d, 'target_file', '') or getattr(d, 'temp_file', '') or '')
        if not folder:
            return None

        title_norm = _norm_title(getattr(d, 'name', '') or os.path.basename(getattr(d, 'target_file', '') or ''))
        video_candidates, _audio_candidates = _expected_paths(folder, title_norm)

        # 1) Exact by normalized title (_temp_<TITLE>.*)
        video = _best_existing(video_candidates)
        if video and (not audio_path or os.path.abspath(video) != os.path.abspath(audio_path)):
            return video

        # 2) Use target_file if it exists
        tgt = getattr(d, 'target_file', None)
        if tgt and os.path.exists(tgt) and (not audio_path or os.path.abspath(tgt) != os.path.abspath(audio_path)):
            return tgt

        # 3) Scan folder for any _temp_*.* and choose the best title match
        pattern = os.path.join(folder, "_temp_*.*")
        candidates = [p for p in glob.glob(pattern) if os.path.isfile(p)]
        if candidates:
            scored = []
            for p in candidates:
                t = _extract_title_from_pattern(p, "_temp_") or ""
                if t == title_norm:
                    score = 100
                else:
                    a = set(title_norm.split('_'))
                    b = set(t.split('_'))
                    inter = len(a & b)
                    score = inter
                if audio_path and os.path.abspath(p) == os.path.abspath(audio_path):
                    continue
                scored.append((score, p))
            if scored:
                scored.sort(key=lambda x: (-x[0], -os.path.getsize(x[1]), x[1]))
                if scored[0][0] > 0:
                    return scored[0][1]

        # 4) Last resort: largest media with <TITLE>.* (avoid choosing the audio file)
        media_exts = ('mp4', 'm4v', 'mov', 'webm', 'mkv', 'ts')
        pattern = os.path.join(folder, f"{title_norm}.*")
        loose = []
        for p in glob.glob(pattern):
            if audio_path and os.path.abspath(p) == os.path.abspath(audio_path):
                continue
            ext = os.path.splitext(p)[1].lower().lstrip('.')
            if ext in media_exts:
                loose.append(p)
        if loose:
            loose.sort(key=lambda p: (-os.path.getsize(p), p))
            return loose[0]

        return None
    
    
    def _build_output_path(self, d, video_path: str) -> str:
        out_ext = _pick_container_from_video(video_path)
        # Keep in the same folder with a clear suffix to avoid clobbering inputs
        return os.path.join(d.folder, f"{d.name}.{out_ext}")

    def _cleanup_separate_streams(self, audio_path: str | None, video_path: str | None, keep_inputs=False):
        if keep_inputs:
            return
        for p in (audio_path,):
            try:
                if p and os.path.exists(p):
                    pass
                    #os.remove(p)
            except Exception:
                pass
        # We usually keep the video input to avoid surprising the user; 
        #     if video_path and os.path.exists(video_path):
        #         os.remove(video_path)
        # except Exception:
        #     pass

    
    def _start_ffmpeg_remerge(self, d, video_path: str, audio_path: str, output_path: str, row_index: int):
        ffmpeg = config.get_ffmpeg_path()
        if not ffmpeg or not os.path.exists(ffmpeg):
            show_warning(self.tr("FFmpeg not found"), self.tr("Please install or configure FFmpeg in Settings."))
            return

        # Ensure proc map
        if not hasattr(self, "_remux_procs"):
            self._remux_procs = {}

        # Kill any previous proc for this item
        if d.id in self._remux_procs:
            try:
                self._remux_procs[d.id].kill()
            except Exception:
                pass
            self._remux_procs.pop(d.id, None)

        proc = QProcess(self)
        self._remux_procs[d.id] = proc

        args = [
            "-y",
            "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c", "copy",
            output_path,
        ]

        # UI: show "merging"
        old_status = d.status
        d.status = "merging_audio"   # matches update_table_progress color map
        self.update_table_progress()

        def on_finished(exit_code, exit_status):
            # detach proc
            self._remux_procs.pop(d.id, None)

            if exit_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                d.status = "completed"
                d.progress = 100
                
                # Point to the merged file by updating fields used by the property
                d.name = os.path.basename(output_path)
                d.folder = os.path.dirname(output_path) or d.folder

                # optional: clean separate audio (and/or video) files
                try:
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                except Exception:
                    pass
                # To also remove the _temp_ video:
                # try:
                #     if os.path.exists(video_path):
                #         os.remove(video_path)
                # except Exception:
                #     pass

                # persist
                try:
                    if hasattr(self, "settings_manager") and self.settings_manager:
                        self.settings_manager.save_d_list(self.d_list)
                    else:
                        # Fallback if you use a different settings API
                        # SettingsManager().save_download_list(self.d_list)
                        pass
                except Exception as e:
                    log(f"Save after re-merge failed: {e}", log_level=2)

                self.update_table_progress()
                notify(self.tr("Audio and video were merged successfully."), self.tr("Re-merge complete"))
               
            else:
                # failed → revert to error (or prior)
                d.status = old_status or "error"
                self.update_table_progress()

                err = proc.readAllStandardError().data().decode("utf-8", errors="ignore")
                show_warning(self.tr("Re-merge failed"), (self.tr("FFmpeg could not merge the files.\n\nDetails:\n") + (err or ""))[:3000])

        def on_error(process_error):
            # failure path similar to above
            self._remux_procs.pop(d.id, None)
            d.status = "error"
            self.update_table_progress()
            err = proc.readAllStandardError().data().decode("utf-8", errors="ignore")
            show_warning(self.tr("Re-merge failed"), (self.tr("FFmpeg process error.\n\nDetails:\n") + (err or ""))[:3000])

        proc.finished.connect(on_finished)
        proc.errorOccurred.connect(on_error)

        proc.start(ffmpeg, args)


    def remerge_audio_video(self):
        selected_items = widgets.table.selectedItems()
        if not selected_items:
            show_warning(self.tr("No Selection"), self.tr("Please select a download that has separate audio and video files."))
            return

        selected_row = selected_items[0].row()
        id_item = widgets.table.item(selected_row, 0)
        if not id_item:
            return
        download_id = id_item.data(Qt.UserRole)
        d = next((x for x in self.d_list if x.id == download_id), None)
        if not d:
            return

        # Must have been an error or an unmerged video-only file
        if d.status not in (config.Status.error, getattr(config.Status, "merging_audio", None), getattr(config.Status, "completed", "completed")):
            # You can relax this check if you want to allow re-merge anytime
            pass

        # Locate audio + video inputs
        audio_path = self._find_audio_file_for(d)
        if not audio_path or not os.path.exists(audio_path):
            show_warning(self.tr("Audio Missing"), self.tr("Could not find the separate audio file for this download."))
            return

        video_path = self._find_video_file_for(d, audio_path)
        if not video_path or not os.path.exists(video_path):
            show_warning(self.tr("Video Missing"), self.tr("Could not find the separate video file for this download."))
            return

        # Avoid merging an already-merged file
        output_path = self._build_output_path(d, video_path)
        if os.path.abspath(output_path) == os.path.abspath(video_path):
            # ensure different filename
            root, ext = os.path.splitext(video_path)
            output_path = root + "_merged" + ext

        # Start non-blocking ffmpeg merge
        self._start_ffmpeg_remerge(d, video_path, audio_path, output_path, selected_row)
            

    def start_file_checksum(self, d):
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self.tr("No Selection"), self.tr("Please select a completed download first."))
            return

        # Reverse mapping from table to d_list
        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        if d.status != config.Status.completed:
            show_warning(self.tr("Invalid Selection"), self.tr("Checksum is only available for completed downloads."))
            return

        self.checksum_thread = FileChecksum(d.target_file)
        self.checksum_thread.checksum_computed.connect(self.show_file_checksum_result)
        self.checksum_thread.start()
        self.background_threads.append(self.checksum_thread)

    def show_file_checksum_result(self, file_path, checksum):
        if checksum == "Error":
            show_warning(self.tr("Checksum Error"), self.tr("Failed to compute checksum for file."))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("SHA-256 Checksum")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet("""

            QDialog {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
                border-radius: 14px;
            }


        """)

        layout = QVBoxLayout(dialog)

        file_label = QLabel(f"<b>File:</b> {file_path}")
        layout.addWidget(file_label)

        checksum_label = QLabel("SHA-256:")
        layout.addWidget(checksum_label)

        checksum_line = QLineEdit()
        checksum_line.setText(checksum)
        checksum_line.setReadOnly(True)
        layout.addWidget(checksum_line)

        # Buttons
        button_layout = QHBoxLayout()
        copy_btn = QPushButton(self.tr("Copy"))
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                ); 
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33d47c;
            }

        """)
        close_btn = QPushButton(self.tr("Close"))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                ); 
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
        """)
        empty_label = QLabel("")
        button_layout.addWidget(copy_btn)
        button_layout.addWidget(empty_label)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        # Connections
        def copy_to_clipboard():
            QApplication.clipboard().setText(checksum)
            empty_label.setText(self.tr("COPIED !!!"))
            empty_label.setStyleSheet("color: whITE;")
        
        copy_btn.clicked.connect(copy_to_clipboard)
        close_btn.clicked.connect(dialog.accept)

        dialog.exec()

    def pop_download_item(self):
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self.tr("No Selection"), self.tr("Please select a download to remove."))
            return

        # Reverse mapping from table to d_list
        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        self.d_list.remove(d)
        widgets.table.removeRow(selected_row)
    

    def set_row_color(self, row, status):
        """Apply color coding based on status."""
        color = QtGui.QColor()

        if status == config.Status.completed:
            color = QtGui.QColor(0, 200, 83)  # Green
        elif status in (config.Status.error, config.Status.failed, config.Status.cancelled):
            color = QtGui.QColor(244, 67, 54)  # Red
        elif status == config.Status.downloading:
            color = QtGui.QColor(33, 150, 243)  # Blue
        elif status == config.Status.paused:
            color = QtGui.QColor(255, 193, 7)  # Amber
        elif status == config.Status.queued:
            color = QtGui.QColor(156, 39, 176)  # Purple
        elif status == config.Status.deleted:
            color = QtGui.QColor(158, 158, 158)  # Grey
        elif status == config.Status.merging_audio:
            color = QtGui.QColor(255, 109, 0)  # Deep Orange
        else:
            color = QtGui.QColor(255, 255, 255)  # Default white

        for col in range(widgets.table.columnCount()):
            item = widgets.table.item(row, col)
            if item:
                item.setForeground(color)

    # endregion


    def refresh_table_row(self, d):
        """Refresh only the specific row for a download without repainting the whole table."""
        target_row = None

        # First find the row that matches the download ID
        for row in range(widgets.table.rowCount()):
            id_item = widgets.table.item(row, 0)
            if id_item and id_item.data(Qt.UserRole) == d.id:
                target_row = row
                break

        if target_row is not None:
            # Update only the status column
            status_col = self.d_headers.index("status")
            status_item = widgets.table.item(target_row, status_col)
            if status_item:
                status_item.setText(d.status)

            # Update the color styling
            self.set_row_color(target_row, d.status)

    # endregion



    def _handle_version_status(self):
        latest = getattr(config, "APP_LATEST_VERSION", None)
        current = getattr(config, "APP_VERSION", None)

        cmp = compare_versions_2(latest, current)

        if cmp == 0:
            # up to date
            widgets.version_value.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-weight: bold;
                    padding: 5px 10px;
                    border-radius: 10px;
                    background: rgba(76, 175, 80, 0.1);
                }
            """)
            widgets.version_value.setToolTip('No new updates')
        elif cmp == 1:
            # newer available
            widgets.version_value.setStyleSheet("""
                QLabel {
                    color: #F44336;
                    padding: 6px 16px;
                    font-weight: bold;
                    border-radius: 10px;
                    background: rgba(244, 67, 54, 0.1);  
                }
            """)
            widgets.version_value.setToolTip(f'New version available: {latest}')
        elif cmp == -1:
            # current > latest (dev build ahead)
            widgets.version_value.setStyleSheet("""
                QLabel {
                    color: #2196F3;
                    padding: 6px 16px;
                    font-weight: bold;
                    border-radius: 10px;
                    background: rgba(33, 150, 243, 0.1);
                }
            """)
            widgets.version_value.setToolTip(f'Running a newer/dev build ({current})')
        else:
            # Unknown (None / unparsable)
            widgets.version_value.setStyleSheet("""
                QLabel {
                    color: #9E9E9E;
                    font-weight: bold;
                    padding: 5px 10px;
                    border-radius: 10px;
                    background: rgba(158, 158, 158, 0.1);
                }
            """)
            widgets.version_value.setToolTip('Unable to determine latest version')


    def check_scheduled(self):
        now = datetime.now().replace(microsecond=0)
        current_date_str = now.strftime("%Y-%m-%d")
        current_time_str = now.strftime("%H:%M:%S")

        for d in self.d_list:
            if d.status == config.Status.scheduled and getattr(d, "sched", None):
                sched_date, sched_time = d.sched  # Assuming ('2025-07-02', '01:31:15')
                

                if sched_date == current_date_str and sched_time == current_time_str:
                    log(f"Scheduled time matched for {d.name}, attempting download...", log_level=1)
                    result = self.start_download(d, silent=True)

                    if d.status in [config.Status.failed, config.Status.scheduled, config.Status.cancelled, config.Status.error]:
                        log(f"Scheduled download failed for {d.name}.", log_level=3)

                        if config.retry_scheduled_enabled:
                            d.schedule_retries = getattr(d, "schedule_retries", 0)
                            if d.schedule_retries < config.retry_scheduled_max_tries:
                                d.schedule_retries += 1
                                retry_time = now + timedelta(minutes=config.retry_scheduled_interval_mins)
                                log(f"The retry time is {retry_time}")
                                d.sched = (
                                    retry_time.strftime("%Y-%m-%d"),
                                    retry_time.strftime("%H:%M:%S")
                                )
                                d.status = config.Status.scheduled
                                log(f"Retrying {d.name} at {d.sched[0]}, {d.sched[1]} [Attempt {d.schedule_retries}]", log_level=2)
                                show_information(title="Scheduled Retry", inform="", msg=f"Retrying {d.name} at {d.sched[0]}, {d.sched[1]} [Attempt {d.schedule_retries}]")
                            else:
                                d.status = config.Status.cancelled
                                log(f"{d.name} has reached max retries.", log_level=2)
                        else:
                            d.status = config.Status.cancelled

        self.queue_update("populate_table", None)
    
    


    def change_page(self, btn=None, btnName=None, idx=None):
        """ Change stack pages automatically using this method """
        if idx is not None:
            widgets.stacked_widget.setCurrentIndex(idx)
            for i, b in enumerate(widgets.page_buttons):
                b.setChecked(i == idx)


    # region update

    def check_update_frequency(self):
        selected = int(widgets_settings.check_interval_combo.currentText())
        config.update_frequency = selected

    def update_available(self):
        change_cursor('busy')

        # check for update
        current_version = config.APP_VERSION
        info = updater.get_changelog()

        if info:
            latest_version, version_description = info

            # compare with current application version
            newer_version = compare_versions(current_version, latest_version)  # return None if both equal
    
            if not newer_version or newer_version == current_version:
                self.new_version_available = False
                log(f"check_for_update() --> App. is up-to-date, server version= {latest_version}", log_level=1)
            else:  # newer_version == latest_version
                self.new_version_available = True
                #show_information('Updates', '', 'Updates available')
                self.handle_update()
                
            # update global values
            config.APP_LATEST_VERSION = latest_version if latest_version is not None else config.APP_VERSION
            
            self.new_version_description = version_description

        else:
            self.new_version_description = None
            self.new_version_available = False

        self.settings_manager.save_settings()
        change_cursor('normal')
    

    def start_update(self):
        # Initialize and start the update thread
        self.start_update_thread = CheckUpdateAppThread()
        self.start_update_thread.app_update.connect(self.update_app)
        self.start_update_thread.start()

    def update_app(self, new_version_available):
        """Show changelog with latest version and ask user for update."""
        if new_version_available:
            config.main_window_q.put(('show_update_gui', ''))
        else:
            cv, sv = self.tr("Current version: "), self.tr("Server version: ")
            show_information(
                title=self.tr("App Update"),
                inform=self.tr("App is up-to-date"),
                msg=f"{cv} {config.APP_VERSION}\n {sv} {config.APP_LATEST_VERSION}"
            )

            if not self.start_update_thread.new_version_description:
                ccu, cyi = self.tr("Couldn't check for update"), self.tr("Check your internet connection")
                show_critical(
                    title=self.tr("App Update"),
                    msg=f"{ccu} \n {cyi}"
                )
    
    def show_update_gui(self):
        # Create a QDialog (modal window)
        dialog = QDialog(self)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #121212;
                color: white;
                border-radius: 12px;
                font-family: 'Segoe UI';
                font-size: 13px;
                border: 1px solid #3A3F44;
            }
            QLabel {
                font-size: 14px;
                padding: 6px;
            }
            QTextEdit {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                );
                border-radius: 16px;
                color: white;
                border: 1px solid #333;
                font-family: Consolas, Courier New, monospace;
                font-size: 12px;
                padding: 10px;
            }
        """)


        dialog.setWindowTitle(self.tr('Update Application'))
        dialog.setModal(True)  # Keep the window on top

        # Create the layout for the dialog
        layout = QVBoxLayout()

        # Add a label to indicate the new version
        label = QLabel(self.tr('New version available:'))
        layout.addWidget(label)

        # Add a QTextEdit to show the new version description (read-only)
        description_edit = QTextEdit()
        description_edit.setText(self.start_update_thread.new_version_description or "")
        description_edit.setReadOnly(True)
        description_edit.setFixedSize(400, 200)  # Set the size similar to size=(50, 10) in PySimpleGUI
        layout.addWidget(description_edit)

        # Create buttons for "Update" and "Cancel"
        button_layout = QHBoxLayout()
        update_button = QPushButton(self.tr('Update'), dialog)
        update_button.setStyleSheet(
            """
            QPushButton {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                ); 
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33d47c;
            }
            """
        )
        cancel_button = QPushButton(self.tr('Cancel'), dialog)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                ); 
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
        """)
        button_layout.addWidget(update_button)
        button_layout.addWidget(cancel_button)

        # Add the buttons to the layout
        layout.addLayout(button_layout)

        # Set the main layout of the dialog
        dialog.setLayout(layout)
        
        # Connect buttons to actions
        def on_ok():
            dialog.accept()
            self.handle_update()
            dialog.close()

        def on_cancel():
            dialog.reject()
            dialog.close()

        update_button.clicked.connect(on_ok)  # Call the update function when "Update" is clicked
        cancel_button.clicked.connect(on_cancel)  # Close the dialog when "Cancel" is clicked

        # Show the dialog
        dialog.exec()

    def handle_update(self):
        self.update_thread = UpdateThread()  # Create an instance of the UpdateThread
        self.update_thread.update_finished.connect(self.on_update_finished)  # Connect the signal
        self.update_thread.start()  # Start the thread
        self.change_page(btn=None, btnName=None, idx=2)

    def on_update_finished(self):
        log("Updates finished")
    

    # endregion


def ask_for_sched_time(msg=''):
    dialog = ScheduleDialog(msg)
    result = dialog.exec()  # Show the dialog as a modal

    if result == QDialog.Accepted:
        return dialog.response  # Return the (hours, minutes) tuple
    return None



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(":/icons/logo1.png"))
    app_id = "omnipull.exe"
    single_instance = SingleInstanceApp(app_id)

    if single_instance.is_running():
        QMessageBox.warning(None, ("Warning"), "Another instance of this application is already running.")
        sys.exit(0)

    # Start the server to mark this instance as active
    single_instance.start_server()
    window = DownloadManagerUI(config.d_list)
    window.show()

    QTimer.singleShot(0, video.import_ytdl)

    if not getattr(config, "tutorial_completed", False):
        window.tutorial = TutorialOverlay(window, tutorial_steps)

    sys.exit(app.exec())







