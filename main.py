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
from PySide6.QtWidgets import (QMainWindow, QApplication, QFileDialog, QMessageBox, 
                               QVBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, 
                               QHBoxLayout, QWidget, QFrame, QTableWidgetItem, QDialog, 
                               QComboBox, QInputDialog, QMenu, QRadioButton, QButtonGroup, 
                               QHeaderView, QScrollArea, QCheckBox, QSystemTrayIcon)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QLocalServer, QLocalSocket
from yt_dlp.utils import DownloadError, ExtractorError
from PySide6.QtCore import QTimer, QPoint, QThread, Signal, Slot, QUrl, QTranslator, QCoreApplication, Qt
from PySide6 import QtCore, QtGui
from PySide6.QtGui import QAction, QIcon, QPixmap, QImage, QClipboard


from ui.ui_main import Ui_MainWindow    
from ui.setting_dialog import SettingsWindow
from ui.about_dialog import AboutDialog




from modules.video import (Video, check_ffmpeg, download_ffmpeg, get_ytdl_options)
from modules.utils import (size_format, validate_file_name, compare_versions, log, delete_file, time_format, truncate, 
    notify, run_command, handle_exceptions)
from modules import config, brain, setting, video, update, startup
from modules.downloaditem import DownloadItem
from pathlib import Path
import json

os.environ["QT_FONT_DPI"] = "96"  # FIX Problem for High DPI and Scale above 100%


widgets = None
widgets_settings = None
widgets_about = None



class InternetChecker(QThread):
    """
    This class for checking the internet
    """
    # Define a signal to send the result back to the main thread
    internet_status_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_connected = False  # Add a flag to store the connection status

    def run(self):
        """Runs the internet check in the background."""
        url = "https://www.google.com"
        timeout = 10
        try:
            # Requesting URL to check for internet connectivity
            requests.get(url, timeout=timeout)
            self.is_connected = True  # Update the connection status
            self.internet_status_changed.emit(True)
        except (requests.ConnectionError, requests.Timeout):
            self.is_connected = False  # Update the connection status
            self.internet_status_changed.emit(False)


class SingleInstanceApp:
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
            # Clean up any leftover server instance if it wasn't closed properly
            QLocalServer.removeServer(self.app_id)
            self.server.listen(self.app_id)


class YouTubeThread(QThread):
    """Thread to handle YouTube video extraction and downloading."""
    finished = Signal(object)  # Signal when the process is complete
    progress = Signal(int)  # Signal to update progress bar (0-100%)

    def __init__(self, url: str):
        """Initialize the YouTubeThread with the URL."""
        super().__init__()
        self.url = url

    def change_cursor(self, cursor_type: str):
        """Change cursor to busy or normal."""
        if cursor_type == 'busy':
            QApplication.setOverrideCursor(Qt.WaitCursor)  # Busy cursor
        elif cursor_type == 'normal':
            QApplication.restoreOverrideCursor()  # Restore normal cursor

    def run(self):
        """Run the thread to process the video URL."""
        try:
            # Ensure youtube-dl is loaded
            if video.ytdl is None:
                log('youtube-dl module still loading, please wait')
                while not video.ytdl:
                    time.sleep(0.1)
            widgets.download_btn.setEnabled(False)
            widgets_settings.monitor_clipboard_cb.setChecked(False)
            widgets.combo1.clear()
            widgets.combo2.clear()

            log(f"Extracting info for URL: {self.url}")
            self.change_cursor('busy')

            with video.ytdl.YoutubeDL(get_ytdl_options()) as ydl:
                info = ydl.extract_info(self.url, download=False, process=True)
                log('Media info:', info, log_level=3)

                if info.get('_type') == 'playlist' or 'entries' in info:
                    pl_info = list(info.get('entries', []))
                    playlist = []
                    for index, item in enumerate(pl_info):
                        url = item.get('url') or item.get('webpage_url') or item.get('id')
                        if url:
                            playlist.append(Video(url, vid_info=item))
                        # Emit progress as we process each playlist entry
                        self.progress.emit(int((index + 1) * 100 / len(pl_info)))
                    result = playlist
                else:
                    # For a single video, update progress on extraction
                    result = Video(self.url, vid_info=None)
                    self.progress.emit(50)  # Just after extracting the info
                    time.sleep(1)  # Simulating some processing
                    self.progress.emit(100)  # Video info extraction complete

                self.finished.emit(result)
                self.change_cursor('normal')
                widgets.download_btn.setEnabled(True)
                widgets_settings.monitor_clipboard_cb.setChecked(True)

        except DownloadError as e:
            log('DownloadError:', e)
            self.finished.emit(None)
        except ExtractorError as e:
            log('ExtractorError:', e)
            self.finished.emit(None)
        except Exception as e:
            log('Unexpected error:', e)
            self.finished.emit(None)

            
class CheckUpdateAppThread(QThread):
    """Thread to check if a new version of the app is available."""
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
        # Emit the app_update signal with the result
        self.app_update.emit(self.new_version_available)

    def check_for_update(self):
        """Check for a new version and update internal state."""
        # Change cursor to busy
        self.change_cursor('busy')

        # Retrieve current version and changelog information
        current_version = config.APP_VERSION
        info = update.get_changelog()

        if info:
            latest_version, version_description = info

            # Compare versions
            newer_version = compare_versions(current_version, latest_version)
            if not newer_version or newer_version == current_version:
                self.new_version_available = False
            else:  # newer_version == latest_version
                self.new_version_available = True

            # Update global values
            config.APP_LATEST_VERSION = latest_version
            self.new_version_description = version_description
        else:
            self.new_version_available = False
            self.new_version_description = None

        # Revert cursor to normal
        self.change_cursor('normal')

    def change_cursor(self, cursor_type: str):
        """Change cursor to busy or normal."""
        if cursor_type == 'busy':
            QApplication.setOverrideCursor(Qt.WaitCursor)  # Busy cursor
        elif cursor_type == 'normal':
            QApplication.restoreOverrideCursor()  # Restore normal cursor
    
class UpdateThread(QThread):
    """Thread to perform an update and signal when it is finished."""
    update_finished = Signal()  # Signal to indicate that the update is finished

    def run(self):
        """Run the update process and emit the signal when finished."""
        update.update()  # Perform the update here
        if config.confirm_update:
            self.update_finished.emit()  # Emit the signal when done


class FileOpenThread(QThread):
    """Thread to open a file and signal errors if the file doesn't exist."""
    critical_signal = Signal(str, str)  # Signal to communicate with the main window

    def __init__(self, file_path: str, parent=None):
        """Initialize the thread with the file path."""
        super(FileOpenThread, self).__init__(parent)
        self.file_path = file_path

    def run(self):
        """Run the thread to open the specified file."""
        try:
            if not os.path.exists(self.file_path):
                # Emit the signal if the file doesn't exist
                self.critical_signal.emit('File Not Found', f"The file '{self.file_path}' could not be found or has been deleted.")
                return  # Exit the thread if the file doesn't exist

            # Opening the file
            if config.operating_system == 'Windows':
                os.startfile(self.file_path)
            elif config.operating_system == 'Linux':
                run_command(f'xdg-open "{self.file_path}"', verbose=False)
            elif config.operating_system == 'Darwin':
                run_command(f'open "{self.file_path}"', verbose=False)

        except FileNotFoundError:
            log(f"File not found: {self.file_path}")
            self.critical_signal.emit(
                'File Not Found', 
                f"The file '{self.file_path}' could not be found."
            )
        except PermissionError:
            log(f"Permission error accessing: {self.file_path}")
            self.critical_signal.emit(
                'Permission Error', 
                f"Permission denied while trying to access '{self.file_path}'."
            )
        except OSError as e:
            log(f"OS error occurred while opening file: {e}")
            self.critical_signal.emit(
                'OS Error', 
                f"An OS error occurred while opening the file: {e}"
            )


class LogRecorderThread(QThread):
    """Thread to record logs and write them to a file."""
    error_signal = Signal(str)  # Signal to report errors to the main thread

    def __init__(self):
        """Initialize the log recorder with an empty buffer and prepare the log file."""
        super().__init__()
        self.buffer = ''
        self.file = os.path.join(config.sett_folder, 'log.txt')

        # Clear previous log file
        try:
            with open(self.file, 'w') as f:
                f.write(self.buffer)
        except Exception as e:
            self.error_signal.emit(f'Failed to clear log file: {str(e)}')

    def run(self):
        """Run the log recorder to continuously write log messages to the file."""
        while not config.terminate:
            try:
                # Read log messages from queue
                q = config.log_recorder_q
                for _ in range(q.qsize()):
                    self.buffer += q.get()

                # Write buffer to file
                if self.buffer:
                    with open(self.file, 'a', encoding="utf-8", errors="ignore") as f:
                        f.write(self.buffer)
                        self.buffer = ''  # Reset buffer

                # Sleep briefly to prevent high CPU usage
                self.msleep(100)  # QThread's msleep is more precise than time.sleep

            except Exception as e:
                self.error_signal.emit(f'Log recorder error: {str(e)}')
                self.msleep(100)


# region Main Downloader UI
class DownloadManagerUI(QMainWindow):
    update_gui_signal = Signal(dict)
    def __init__(self, d_list):
        QMainWindow.__init__(self)



        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui_settings = SettingsWindow(self)
        # Now safely connect signal
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
            
            QMenu::item:disabled {
                color: #777777;
            }



        """)

        # Global widgets
        global widgets
        widgets = self.ui
        global widgets_settings
        widgets_settings = self.ui_settings
        
        

        # region init parameters

        # App Name
        title = config.APP_TITLE
        self.setWindowTitle(title)


        self.d = DownloadItem() # current download_item
        self.yt_thread = None # Setup YouTube thread and connect signals
        self.download_windows = {}  # dict that holds Download_Window() objects --> {d.id: Download_Window()}
        self.setup()

        # url
        self.url_timer = None  # usage: Timer(0.5, self.refresh_headers, args=[self.d.url])
        self.bad_headers = [0, range(400, 404), range(405, 418), range(500, 506)]  # response codes

        # youtube specific
        # download
        self.pending = deque()
        self.disabled = True  # for download button


        # download list
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
        #self.log_recorder_thread.error_signal.connect(self.handle_log_error)
        self.log_recorder_thread.start()

        # Setup clipboard monitoring
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.old_clipboard_data = ''

        # Initialize the PyQt run loop with a timer (to replace the PySimpleGUI event loop)
        self.run_timer = QTimer(self)
        self.run_timer.timeout.connect(self.run)
        self.run_timer.start(900)  # Runs every 500ms

        # self.retry_button_clicked = False
        # Flag to indicate if the filename is being updated programmatically
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
        log(f'Starting {config.APP_NAME} version:', config.APP_VERSION, 'Frozen' if config.FROZEN else 'Non-Frozen')
        # log('starting application')
        log('operating system:', config.operating_system_info)
        log('current working directory:', config.current_directory)
        os.chdir(config.current_directory)

        # load stored setting from disk
        setting.load_setting()
        self.d_list = setting.load_d_list()

        widgets.folder_input.setText(config.download_folder)

    
        widgets.toolbar_buttons["Settings"].clicked.connect(self.open_settings)
        widgets.help_menu.actions()[0].triggered.connect(self.show_about_dialog)


        self.update_gui_signal.connect(self.process_gui_updates)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_for_updates)
        self.update_timer.start(100)  # Check for updates every 100ms
        self.pending_updates = {}
        self.network_manager = QNetworkAccessManager()
        self.network_manager.finished.connect(self.on_thumbnail_downloaded)
        self.one_time, self.check_time = True, True
        
        
        # Translator
        self.translator = QTranslator()

        # Load saved language
        self.current_language = config.lang
        self.apply_language(self.current_language)
        self.setup_context_menu_actions()
        
    

    def resource_path2(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)
        
    # def apply_language(self, language):
    #     """
    #     Applying the type of language selected by the user
    #     """
    #     # Load and apply the selected language
    #     if language == "French":
    #         if self.translator.load(self.resource_path2("app_fr.qm")):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     elif language == "Spanish":
    #         if self.translator.load(self.resource_path2("app_es.qm")):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     elif language == "Chinese":
    #         if self.translator.load(self.resource_path2("app_zh.qm")):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     elif language == "Korean":
    #         if self.translator.load(self.resource_path2("app_ko.qm")):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     elif language == "Japanese":
    #         if self.translator.load(self.resource_path2("app_ja.qm")):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     else:
    #         QCoreApplication.instance().removeTranslator(self.translator)

    #     # Update the UI
    #     self.retrans()

    # This is used when running the application from an IDE
    # def apply_language(self, language):
    #     # Load and apply the selected language
    #     if language == "French":
    #         if self.translator.load("modules/translations/app_fr.qm"):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     elif language == "Spanish":
    #         if self.translator.load("modules/translations/app_es.qm"):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     elif language == "Chinese":
    #         if self.translator.load("modules/translations/app_zh.qm"):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     elif language == "Korean":
    #         if self.translator.load("modules/translations/app_ko.qm"):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     elif language == "Japanese":
    #         if self.translator.load("modules/translations/app_ja.qm"):
    #             QCoreApplication.instance().installTranslator(self.translator)
    #     else:
    #         QCoreApplication.instance().removeTranslator(self.translator)

    #     # Update the UI
    #     self.retrans()


    

    def apply_language(self, language):
        QCoreApplication.instance().removeTranslator(self.translator)

        file_map = {
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
                print(f"[Language] Loaded {language} translation.")
            else:
                print(f"[Language] Failed to load {qm_path}")

       

        self.retrans()

    def show_about_dialog(self):
        dialog = AboutDialog()
        dialog.exec()


    def retrans(self):
        """
        Texts, objects, buttons, etc to translate
        """
        # Home Translations
        # widgets.home_link_label.setText(self.tr("LINK"))
        widgets.retry_btn.setText(self.tr("Retry"))
        widgets.folder_btn.setText(self.tr("Open"))
        widgets.folder_label.setText(self.tr("CHOOSE FOLDER"))
        widgets.filename_label.setText(self.tr("FILENAME"))
        widgets.link_input.setPlaceholderText(self.tr("Place download link here"))
        widgets.filename_input.setPlaceholderText(self.tr("Filename goes here"))
        widgets.playlist_btn.setText(self.tr("Playlist"))
        widgets.download_btn.setText(self.tr("Download"))
        widgets.size_label.setText(self.tr("Size:"))
        widgets.type_label.setText(self.tr("Type:"))
        widgets.protocol_label.setText(self.tr("Protocol:"))
        widgets.resume_label.setText(self.tr("Resumable:"))

        # Download Translations
        # widgets.resume.setText(self.tr("Resume"))
        # widgets.pause.setText(self.tr("Pause"))
        # widgets.refresh.setText(self.tr("Refresh"))
        # widgets.d_window.setText(self.tr("D. Window"))
        # widgets.resume_all.setText(self.tr("Resume All"))
        # widgets.stop_all.setText(self.tr("Stop All"))
        # widgets.delete.setText(self.tr("Delete"))
        # widgets.delete_all.setText(self.tr("Delete All"))
        # widgets.schedule_all.setText(self.tr("Schedule All"))
        # # widgets.itemLabel.setText(self.tr("Download Item: "))

        # # Sidebar Translations
        # widgets.btn_home.setText(self.tr("Home"))
        # widgets.btn_widgets.setText(self.tr("Downloads"))
        # widgets.btn_new.setText(self.tr("Logs"))
        # widgets.toggleButton.setText(self.tr("Hide"))
        # widgets.toggleLeftBox.setText(self.tr("About"))
        # Settings Translations
        # widgets.label_general.setText(self.tr("General"))
        # widgets.label_language.setText(self.tr("Choose Language:"))
        # widgets.label_setting.setText(self.tr("Choose Setting:"))
        widgets_settings.monitor_clipboard_cb.setText(self.tr("Monitor Copied Urls"))
        
        # widgets.checkBox2.setText(self.tr("Show Download Window"))
        # widgets.checkBox3.setText(self.tr("Auto close DL Window"))
        # widgets.checkBox4.setText(self.tr("Show Thumbnail"))
        # widgets.checkBox5.setText(self.tr("On Startup"))
        # widgets.label_segment.setText(self.tr("Segment"))
        # widgets.label_connection.setText(self.tr("Connection / Network"))
        # widgets.checkBox_network.setText(self.tr("Speed Limit"))
        # mxc, mxc2 = self.tr("Max Concurrent"), self.tr("Downloads:")
        # widgets.label_max_downloads.setText(f"{mxc} \n {mxc2}")
        # mxcd, mxcd1 = self.tr("Max Connection"), self.tr("Settings:")
        # widgets.label_max_connections.setText(f"{mxcd} \n {mxcd1}")
        # widgets.checkBox_proxy.setText(self.tr("Proxy"))
        # widgets.lineEdit_proxy.setPlaceholderText(self.tr("Enter Proxy IP or Domain"))
        # widgets.label_updates.setText(self.tr("Updates"))
        # widgets.label_check_every.setText(self.tr("Check for update every:"))
        # widgets.update_button.setText(self.tr("Check for update"))
        # widgets.logLevelLabel.setText(self.tr("Log Level"))
        # widgets.detailedEventsLabel.setText(self.tr("Detailed events"))
        # widgets.clearButton.setText(self.tr("Clear"))
        # widgets.tableWidget.setHorizontalHeaderLabels([("ID"), self.tr("Name"), self.tr("Progress"), self.tr("Speed"), self.tr("Left"), self.tr("Done"), self.tr("Size"), self.tr("Status"), "I"])


    
    def toolbar_buttons_state(self, status: str) -> dict:
        status_map = {
            config.Status.completed: {
                "Resume": False,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.cancelled: {
                "Resume": True,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.error: { 
                "Resume": True,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.paused: {
                "Resume": True,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },  
            config.Status.failed: {
                "Resume": True,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            }, 
            config.Status.deleted: {
                "Resume": False,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.scheduled: {
                "Resume": False,
                "Pause": False,
                "Delete": True,
                "Delete All": False,
                "Refresh": True,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.downloading: {
                "Resume": False,
                "Pause": True,
                "Delete": False,
                "Delete All": False,
                "Refresh": False,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": True,
            },
            config.Status.pending: {
                "Resume": False,
                "Pause": True,
                "Delete": False,
                "Delete All": False,
                "Refresh": False,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
            config.Status.merging_audio: {
                "Resume": False,
                "Pause": False,
                "Delete": False,
                "Delete All": False,
                "Refresh": False,
                "Resume All": False,
                "Stop All": False,
                "Schedule All": False,
                "Settings": True,
                "Download Window": False,
            },
        }

        return status_map.get(status, {})



    def update_toolbar_buttons_for_selection(self):
        selected_rows = widgets.table.selectionModel().selectedRows()

        if not selected_rows:
            # Enable only global buttons
            for key in widgets.toolbar_buttons:
                widgets.toolbar_buttons[key].setEnabled(key in {
                    "Stop All", "Resume All", "Settings", "Schedule All"
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
        combined_states = self.toolbar_buttons_state(selected_items[0].status).copy()

        for d in selected_items[1:]:
            state = self.toolbar_buttons_state(d.status)
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
            log(f"Clipboard error due to incorrect data type or attribute access: {str(e)}")

    
    


    def open_settings(self):
        dialog = SettingsWindow(self)
        if dialog.exec():
            self.queue_updates()
            # setting.save_setting()

   



            


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
                    if '[download]' in v:  # "[download] Downloading video 3 of 30"
                        b = v.rsplit(maxsplit=3)  # ['[download] Downloading video','3','of','30']
                        total_num = int(b[-1])
                        num = int(b[-3])
                        # get 50% of this value and the remaining 50% will be for other process
                        percent = int(num * 100 / total_num)
                        percent = percent // 2    
                    widgets.terminal_log.append(v)
                except Exception as e:
                    log(f"{e}")

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
            # elif k == "restore_window":
            #     config.terminate = False
            #     self.restore_window()
            elif k == 'popup':
                type_ = v['type_']
                if type_ == 'info':
                    self.show_information(title=v['title'], inform="", msg=v['msg'])
                else:
                    self.show_critical(title=v['title'], msg=v['msg'])


    def run(self):
        """Handle the event loop."""
        try:
            self.read_q()  # Handle queue read operation
        except (AttributeError, TypeError) as e:
            log(f"Error reading queue: {e}")
        
        try:
            self.queue_updates()  # Update the GUI components
        except (AttributeError, RuntimeError) as e:
            log(f"Error updating GUI components: {e}")
        
        if self.one_time:
            self.one_time = False
            
            try:
                # Check availability of ffmpeg in the system or in the same folder as this script
                t = time.localtime()
                today = t.tm_yday  # Today number in the year range (1 to 366)
            except (ValueError, TypeError) as e:
                log(f"Error with date/time operation: {e}")
                return
            
            try:
                days_since_last_update = today - config.last_update_check
                log('Days since last check for update:', days_since_last_update, 'day(s).')
                
                if days_since_last_update >= config.update_frequency:
                    Thread(target=self.update_available, daemon=True).start()
                    # Thread(target=self.check_for_ytdl_update, daemon=True).start()
                    config.last_update_check = today
            except (TypeError, ValueError) as e:
                log(f"Error in update check calculations: {e}")
            except Exception as e:
                log(f"Error in run loop: {e}")



    # region Url stuffs
    def url_text_change(self):
        """Handle URL changes in the QLineEdit."""
        url = widgets.link_input.text().strip()
        if url == self.d.url:
            return

        self.reset()
        try:
            self.d.eff_url = self.d.url = url
            log(f"New URL set: {url}")
            # Update the DownloadItem with the new URL
            # schedule refresh header func
            if isinstance(self.url_timer, Timer):
                self.url_timer.cancel()  # cancel previous timer

            self.url_timer = Timer(0.5, self.refresh_headers, args=[url])
            self.url_timer.start()
            # Trigger the progress bar update and GUI refresh
        except AttributeError as e:
            log(f"Error setting URLs in the object 'self.d': {e}")
            return  # Early return if we can't set URLs properly

    def process_url(self):
        """Simulate processing the URL and update the progress bar.""" 
        progress_steps = [10, 50, 100]  # Define the progress steps
        for step in progress_steps:
            time.sleep(1)  # Simulate processing time
            # Update the progress bar in the main thread
            self.update_progress_bar_value(step)       
    def update_progress_bar_value(self, value):
        """Update the progress bar value in the GUI."""
        widgets.progress.setValue(value)       

    def retry(self):
        self.d.url = ''
        self.url_text_change()

    def reset(self):
        # create new download item, the old one will be garbage collected by python interpreter
        self.d = DownloadItem()

        # reset some values
        self.playlist = []
        self.video = None

    def update_progress_bar(self):
        """Update the progress bar based on URL processing."""
        # Start a new thread for the progress updates
        Thread(target=self.process_url, daemon=True).start()

    
    def refresh_headers(self, url):
        if self.d.url != '':
            #self.change_cursor('busy')
            Thread(target=self.get_header, args=[url], daemon=True).start()


    
    def check_browser_queue(self):
        if not config.browser_integration_enabled:
            return

        queue_file = Path.home() / ".pyiconic_url_queue.json"
        if queue_file.exists():
            try:
                with open(queue_file) as f:
                    urls = json.load(f)
                for entry in urls:
                    url = entry.get("url")
                    if url:
                        widgets.link_input.setText(url)
                        self.url_text_change()
                # Clear the queue after processing
                queue_file.unlink()
            except Exception as e:
                log(f"Failed to process browser queue: {e}")


    def get_header(self, url):
        self.d.update(url)

        if url == self.d.url:
            if self.d.status_code not in self.bad_headers and self.d.type != 'text/html':
                widgets.download_btn.setEnabled(True)

            # Use QThread for YouTube function
            self.yt_thread = YouTubeThread(url)
            self.yt_thread.finished.connect(self.on_youtube_finished)
            self.yt_thread.progress.connect(self.update_progress_bar_value)  # Connect progress signal to update progress bar
            self.yt_thread.start()

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
            widgets.download_btn.setEnabled(True)
            widgets.playlist_btn.setEnabled(False)
        else:
            log("Error: YouTube extraction failed")
            self.change_cursor('normal')
            #widgets.download_btn.setEnabled(True)
            widgets.download_btn.setEnabled(True)
            widgets.playlist_btn.setEnabled(True)

            widgets.combo1.clear()
            widgets.combo2.clear()
            self.reset_to_default_thumbnail()
            return

        self.update_pl_menu()
        self.update_stream_menu()

    
    # region download folder
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
    

    def on_filename_changed(self, text):
        """Handle manual changes to the filename line edit."""
        # Only update the download item if the change was made manually
        if not self.filename_set_by_program:
            self.d.name = text

    
    # region update GUI
    def check_for_updates(self):
        if self.pending_updates:
            self.update_gui_signal.emit(self.pending_updates)
            self.pending_updates.clear()

    def queue_update(self, key, value):
        self.pending_updates[key] = value

    @Slot(dict)
    def process_gui_updates(self, updates):
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
                elif key == 'settings_folder':
                    self.settings_folder()
                elif key == 'check_browser_queue':
                    self.check_browser_queue()
                
                # elif key == 'monitor_clip':
                #     self.monitor_clip()
                # elif key == 'show_download_win':
                #     self.show_download_win()
                # elif key == 'auto_close_win':
                #     self.auto_close_win()
                # elif key == 'show_thumb_nail':
                #     self.show_thumb_nail()
                # elif key == 'segment_size_set':
                #     self.segment_size_set()
                # elif key == 'speed_limit_set':
                #     self.speed_limit_set()
                # elif key == 'max_current_dl':
                #     self.max_current_dl()
                # elif key == 'max_connection':
                #     self.max_connection()
                # elif key == 'proxy_settings':
                #     self.proxy_settings()
                
                # elif key == 'check_update_frequency':
                #     self.check_update_frequency()
                # elif key == 'set_log':
                #     self.set_log()
                # elif key == 'switch_language':
                #     self.switch_language()
                # elif key == 'on_startup':
                #     self.on_startup()
                
                
            # Save settings 
            setting.save_setting()
            setting.save_d_list(self.d_list)

        except Exception as e:
            log('MainWindow.process_gui_updates() error:', e)

    def queue_updates(self):
        """Queue updates instead of directly modifying GUI"""
        self.queue_update('filename', self.d.name)
        self.queue_update('status_code', self.d.status_code)
        self.queue_update('size', self.d.total_size)
        self.queue_update('type', self.d.type)
        self.queue_update('protocol', self.d.protocol)
        self.queue_update('resumable', self.d.resumable)

        total_speed = sum(self.d_list[i].speed for i in self.active_downloads)
        self.queue_update('total_speed', total_speed)

        # Queue other updates
        self.queue_update('populate_table', None)
        self.queue_update('check_scheduled', None)
        self.queue_update('pending_jobs', None)
        self.queue_update('settings_folder', None)
        self.queue_update('check_browser_queue', None)
        
        # self.queue_update('monitor_clip', None)
        # self.queue_update('show_download_win', None)
        # self.queue_update('auto_close_win', None)
        # self.queue_update('show_thumb_nail', None)
        # self.queue_update('segment_size_set', None)
        # self.queue_update('speed_limit_set', None)
        # self.queue_update('max_current_dl', None)
        # self.queue_update('max_connection', None)
        # self.queue_update('proxy_settings', None)
        # self.queue_update('check_update_frequency', None)
        # self.queue_update('set_log', None)
        # self.queue_update('switch_language', None)
        # self.queue_update('current_lang', None)
        # self.queue_update('on_startup', None)

        self.update_table_progress()
        
        #self.queue_update('thumbnail', None)
    
    
    
    # region Start download
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
    
    def start_download(self, d, silent=False, downloader=None):
        # if not self.check_internet():
        #     self.show_warning("No Internet","Please check your internet connection and try again")
        #     return

        if self.check_time:
            self.check_time = False
            server_check = update.SoftwareUpdateChecker(api_url="https://dynamite0.pythonanywhere.com/api/licenses", software_version=config.APP_VERSION)
            server_check.server_check_update() 

        if d is None:
            return
        
        # check for ffmpeg availability in case this is a dash video
        if d.type == 'dash' or 'm3u8' in d.protocol:
            # log('Dash video detected')
            if not self.ffmpeg_check():
                log('Download cancelled, FFMPEG is missing')
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
            self.show_information(f'{fe}', self.tr('Please enter a valid folder name'), f'{df} {folder} {dne}')
            return
        
        except PermissionError:
            ydh = self.tr("you don't have enough permission for destination folder")
            self.show_information(f'{fe}', f"{ydh} {folder}", "")
            return
        
        except Exception as e:
            pidf = self.tr("problem in destination folder")
            self.show_warning(f'{fe}',f'{pidf} {repr(e)}')
        
        # validate file name
        if d.name == '':
            self.show_warning(self.tr('Download Error'), self.tr('File name is invalid. Please enter a valid filename'))
            
        
        # check if file with the same name exist in destination
        # if os.path.isfile(d.target_file):
        #     #  show dialogue
        #     fwtsnaei, dywtof = self.tr("File with the same name already exist in"), self.tr("Do you want to overwrite file?")
        #     msg = QMessageBox.question(self, self.tr("File Overwrite"), f"{fwtsnaei} {d.folder}. \n {dywtof} ", QMessageBox.Yes | QMessageBox.No)
            

        #     # msg.setInformationText(f"")
        #     #msg = 'File with the same name already exist in ' + d.folder + '\n Do you want to overwrite file?'

        #     if msg != QMessageBox.Yes:
        #         log('Download cancelled by user')
        #         return 'cancelled'
        #     else:
        #         delete_file(d.target_file)
        if os.path.isfile(d.target_file):
            # Localized strings
            fwtsnaei = self.tr("File with the same name already exists in")
            dywtof = self.tr("Do you want to overwrite the file?")

            # Styled dialog setup
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(self.tr("File Overwrite"))
            msg_box.setText(f"{fwtsnaei}:\n\n{d.folder}\n\n{dywtof}")
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setStyleSheet(self.get_msgbox_style("overwrite"))

            # Add Yes and No buttons
            yes_btn = msg_box.addButton(self.tr("Overwrite"), QMessageBox.YesRole)
            no_btn = msg_box.addButton(self.tr("Cancel"), QMessageBox.NoRole)
            msg_box.setDefaultButton(no_btn)

            # Show the dialog
            msg_box.exec()

            if msg_box.clickedButton() != yes_btn:
                log('Download cancelled by user')
                return 'cancelled'
            else:
                delete_file(d.target_file)

    

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
                msg.setStyleSheet(self.get_msgbox_style("conflict"))
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
            if response == 'Resume':
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

            elif response == 'Overwrite':
                log('overwrite')
                d.delete_tempfiles()

                # Replace old item in download list
                self.d_list[found_index] = d

            else:
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

                
        os.makedirs(d.temp_folder, exist_ok=True)
        # create and start brain in a separate thread
        Thread(target=brain.brain, daemon=True, args=(d, downloader)).start()


    def file_in_d_list(self, target_file):
        for i, d in enumerate(self.d_list):
            if d.target_file == target_file:
                return i
        return None
    
    
    
    def on_download_button_clicked(self, downloader=None):
        """Handle DownloadButton click event."""
        # Check if the download button is disabled
        if self.d.url == "":
            # Use QMessageBox to display the popup in PyQt
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(self.tr('Download Error'))
            msg.setStyleSheet(self.get_msgbox_style("warning"))
            msg.setText(self.tr('Nothing to download'))
            msg.setInformativeText(self.tr('It might be a web page or an invalid URL link. Check your link or click "Retry".'))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            return
        

        # Get a copy of the current download item (self.d)
        d = copy.copy(self.d)

        # Set the folder for download
        d.folder = config.download_folder  # Ensure that config.download_folder is properly set

        # Start the download using the appropriate downloader
        r = self.start_download(d, downloader=downloader)

        
        if r not in ('error', 'cancelled', False):
            self.change_page(btn=None, btnName=None, idx=1)
            
    
   

    def change_page(self, btn=None, btnName=None, idx=None):
        if idx is not None:
            widgets.stacked_widget.setCurrentIndex(idx)
            for i, b in enumerate(widgets.page_buttons):
                b.setChecked(i == idx)



    # endregion

    # region youtube

    def show_thumbnail(self, thumbnail=None):
        """Show video thumbnail in thumbnail image widget in main tab, call without parameter to reset thumbnail."""

        try:
            if thumbnail is None or thumbnail == "":
                # Reset to default thumbnail if no new thumbnail is provided
                default_pixmap = QPixmap("icons/thumbnail-default.png")
                widgets.thumbnail.setPixmap(default_pixmap.scaled(400, 350, Qt.KeepAspectRatio))
                log("Resetting to default thumbnail")
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
            log('show_thumbnail() error:', e)
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
        default_pixmap = QPixmap("icons/thumbnail-default.png")
        widgets.thumbnail.setPixmap(default_pixmap.scaled(400, 350, Qt.KeepAspectRatio))
        log("Reset to default thumbnail due to error")
        widgets_settings.monitor_clipboard_cb.setChecked(True)


    def update_pl_menu(self):
        """Update the playlist combobox after processing."""
        try:
            log("Updating playlist menu")
            if not hasattr(self, 'playlist') or not self.playlist:
                log("Error: Playlist is empty or not initialized")
                return

            # Set the playlist combobox with video titles
            widgets.combo1.clear()  # Clear existing items
            for i, video in enumerate(self.playlist):
                if hasattr(video, 'title') and video.title:
                    widgets.combo1.addItem(f'{i + 1} - {video.title}')
                else:
                    log(f"Warning: Video at index {i} has no title")

            # Automatically select the first video in the playlist
            if self.playlist:
                self.playlist_OnChoice(self.playlist[0])

        except Exception as e:
            log(f"Error updating playlist menu: {e}")
            import traceback
            log('Traceback:', traceback.format_exc())

    def update_stream_menu(self):
        """Update the stream combobox after selecting a video."""
        try:
            log("Updating stream menu")
            
            if not hasattr(self, 'd') or not self.d:
                log("Error: No video selected")
                return
            
            if not hasattr(self.d, 'stream_names') or not self.d.stream_names:
                log("Error: Selected video has no streams")
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
            log(f"Error updating stream menu: {e}")
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
            log(f"Stream '{selected_stream}' is already selected. No update needed.")
            return

        # Check if the selected stream exists in the available stream names
        if selected_stream not in self.video.stream_names:
            log(f"Warning: Selected stream '{selected_stream}' is not valid, defaulting to the first stream.")
            selected_stream = self.video.stream_names[0]  # Default to the first stream if invalid
        
        # Update the selected stream in the video object
        self.video.selected_stream = self.video.streams[selected_stream]  # Update with stream object
        self.video.selected_stream_name = selected_stream  # Keep track of the selected stream name

        log(f"Stream '{selected_stream}' selected for video {self.video.title}")


    
    # Step 1: Style and fix concurrent download issue in `download_playlist`


    # Step 1: Style and fix concurrent download issue in `download_playlist`



    def download_playlist(self):
        if not self.video:
            self.show_information(
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
            QScrollArea {
                border: none;
            }
            QWidget#scroll_item_row {
                background-color: rgba(255, 255, 255, 0.02);
                border-radius: 6px;
                padding: 6px;
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
        instruction = QLabel("Please click on the video streams to select the video resolution and then click on the checkboxes to select the video in this playlist and click on 'Download'")
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


    def ffmpeg_check(self):
        """Check if ffmpeg is available, if not, prompt user to download."""
        
        if not check_ffmpeg():
            if config.operating_system == 'Windows':
                # Create the dialog
                dialog = QDialog(self)
                dialog.setWindowTitle(self.tr('FFmpeg is missing'))

                # Layout setup
                layout = QVBoxLayout(dialog)

                # Label for missing FFmpeg
                label = QLabel(self.tr('"ffmpeg" is missing!! and needs to be downloaded:'))
                layout.addWidget(label)

                # Radio buttons for choosing destination folder
                recommended, local_fd = self.tr("Recommended:"), self.tr("Local folder:")
                recommended_radio = QRadioButton(f"{recommended} {config.ffmpeg_actual_path_2}")
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
                cancel_button = QPushButton(self.tr('Cancel'))
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
    # endregion

    # region downloads page
    @property
    def selected_d(self):
        self._selected_d = self.d_list[self.selected_row_num] if self.selected_row_num is not None else None
        return self._selected_d

    @selected_d.setter
    def selected_d(self, value):
        self._selected_d = value

    @staticmethod
    def format_cell_data(k, v):
        """take key, value and prepare it for display in cell"""
        if k in ['size', 'total_size', 'downloaded']:
            v = size_format(v)
        elif k == 'speed':
            v = size_format(v, '/s')
        elif k in ('percent', 'progress'):
            v = f'{v}%' if v else '---'
        elif k == 'time_left':
            v = time_format(v)
        elif k == 'resumable':
            v = 'yes' if v else 'no'
        elif k == 'name':
            v = validate_file_name(v)

        return v
    
    # FINAL FIX for table progress bars always working

    def populate_table(self):
        # Adjust table row count to match d_list
        widgets.table.setRowCount(len(self.d_list))

        for row, d in enumerate(reversed(self.d_list)):
            # Always ensure there's a QProgressBar in the progress column (col=2)
            progress = widgets.table.cellWidget(row, 2)
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
                widgets.table.setCellWidget(row, 2, progress)

            file_path = os.path.join(d.folder, str(d.name))
            
            if not os.path.exists(file_path) and not d.status in ["cancelled", "error", "failed", "scheduled", "merging_audio", "paused", "downloading", "pending"]:
                d.status = config.Status.deleted


            # ID column
            id_item = QTableWidgetItem(str(len(self.d_list) - row))
            id_item.setData(Qt.UserRole, d.id)
            id_item.setFlags(id_item.flags() & ~QtCore.Qt.ItemIsEditable)
            widgets.table.setItem(row, 0, id_item)
            


            # All other columns
            for col, key in enumerate(self.d_headers[1:], 1):
                if col == 2:
                    continue  # skip progress bar column
                cell_value = self.format_cell_data(key, getattr(d, key, ''))
                item = QTableWidgetItem(cell_value)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)

                # print(file_path)
                # if not os.path.exists(file_path):
                #     d.status == config.Status.deleted

                widgets.table.setItem(row, col, item)
                

                

    


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
                # if isinstance(progress_widget, QProgressBar):
                #     if d.progress is not None:
                #         progress_widget.setValue(int(d.progress))
                #         progress_widget.setFormat(f"{int(d.progress)}%")
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
                        elif d.status == "deleted":
                            color = "#9C27B0"  # purple
                        

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
                log(f"Error updating progress bar at row {row}: {e}")

    
    
    

    # Clear Log
    def clear_log(self):
        widgets.terminal_log.clear()

    # Set Log level 
    def set_log(self):
        config.log_level = int(widgets.log_level_combo.currentText())
        log('Log Level changed to:', config.log_level)

    # region downloads functions
    dark_style = """
        QMessageBox {
            background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
            color: white;
            font-family: 'Segoe UI';
            font-size: 13px;
            border-radius: 12px;
        }
        QPushButton {
            background-color: #00C853;
            color: white;
            border: none;
            padding: 6px 16px;
            border-radius: 6px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #00B248;
        }
        QLabel {
            color: white;
        }
    """
    def get_msgbox_style(self, msg_type: str) -> str:
        base_style = """
            QMessageBox {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
                font-family: 'Segoe UI';
                font-size: 13px;
                border-radius: 12px;
            }
            QLabel {
                color: white;
            }
        """

        button_styles = {
            "critical": """
                QPushButton {
                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    );
                    color: white;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #B71C1C;
                }
            """,
            "warning": """
                QPushButton {
                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    );
                    color: black;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #FF8F00;
                }
            """,
            "information": """
                QPushButton {
                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    );
                    color: white;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #00B248;
                }
            """,
            "inputdial": """

                QInputDialog {
                    background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                    );
                    color: white;
                    font-family: 'Segoe UI';
                    font-size: 13px;
                    border-radius: 12px;
                }
                QLabel {
                    color: white;
                }
                QLineEdit {
                    background-color: rgba(28, 28, 30, 0.55);  /* Neutral frosted charcoal */
                    color: #e0e0e0;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                    padding: 6px 10px;
                }
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
                    background-color: #00B248;
                }
            """,
            "conflict": """
                QPushButton {
                    background-color: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 1,
                        stop: 0 #0F1B14,
                        stop: 1 #050708
                    );
                    color: white;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #1B5E20;
                }
            """,
            "overwrite": """
                QPushButton {
                    background-color: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 1,
                        stop: 0 #0F1B14,
                        stop: 1 #050708
                    );
                    color: white;
                    padding: 6px 16px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #C62828;  /* deep red on hover for overwrite alert */
                }
            """


        }

        return base_style + button_styles.get(msg_type, "")



    def show_critical(self,title, msg):
        critical_box = QMessageBox(self)
        critical_box.setStyleSheet(self.get_msgbox_style("critical"))
        critical_box.setWindowTitle(title)
        critical_box.setText(msg)
        critical_box.setIcon(QMessageBox.Critical)
        critical_box.setStandardButtons(QMessageBox.Ok)
        critical_box.exec()

    def show_warning(self,title, msg):
        warning_box = QMessageBox(self)
        warning_box.setStyleSheet(self.get_msgbox_style("warning"))
        warning_box.setWindowTitle(title)
        warning_box.setText(msg)
        warning_box.setIcon(QMessageBox.Warning)
        warning_box.setStandardButtons(QMessageBox.Ok)
        
        warning_box.exec()

    def show_information(self, title, inform, msg):
        information_box = QMessageBox(self)
        information_box.setStyleSheet(self.get_msgbox_style("information"))
        information_box.setText(msg)
        information_box.setWindowTitle(title)
        information_box.setInformativeText(inform)
        information_box.setIcon(QMessageBox.Information)
        information_box.setStandardButtons(QMessageBox.Ok)
        information_box.exec()
        return

    # endregion

    def resume_btn(self):
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            self.show_warning(self.tr("Error"), self.tr("No download item selected"))
            return

        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        self.start_download(d, silent=True)
        
        # If internet is available, resume the download

        # Check if the internet_checker is already running
        # if not self.internet_checker.isRunning():
        #     # Start the internet check if it's not running
        #     self.internet_checker.internet_status_changed.connect(self.on_internet_check_done)
        #     self.internet_checker.start()  # Start the thread to check internet status
        # else:
        #     # If the thread is already running, proceed directly with the result from the last check
        #     self.on_internet_check_done(self.internet_checker.is_connected)



    def delete_btn(self):
        # Get all selected rows
        selected_rows = [index.row() for index in widgets.table.selectedIndexes()]
        selected_rows = list(set(selected_rows))  # Remove duplicates, as some items may be selected in multiple columns

        if not selected_rows:
            return

        # Ensure no downloads are active
        if self.active_downloads:
            self.show_critical(self.tr("Error"), self.tr("Can't delete items while downloading. Stop or cancel all downloads first!"))
            return
        
        # Prepare the warning message
        warn, asf = self.tr("Warning!!!"), self.tr("Are you sure you want to delete these items?")
        msg = f"{warn}\n {asf}?"
        
        confirmation_box = QMessageBox(self)
        confirmation_box.setStyleSheet(self.get_msgbox_style("information"))
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
                d.delete_tempfiles()
                os.remove(f"{d.folder}/{d.name}")

        except Exception as e:
            log(f"Error deleting items: {e}")

    def delete_all_downloads(self):
        # Check if there are any active downloads
        if self.active_downloads:
            self.show_critical(
                self.tr("Error"),
                self.tr("Can't delete items while downloading. Stop or cancel all downloads first!")
            )
            return

        # Confirmation dialog - user has to write "delete" to proceed
        dai = self.tr("Delete all items and their progress temp files")
        ttw = self.tr("Type the word 'delete' and hit OK to proceed.")
        msg = f'{dai} \n\n{ttw}'

        input_dialog = QInputDialog(self)
        input_dialog.setStyleSheet(self.get_msgbox_style("inputdial"))
        input_dialog.setWindowTitle(self.tr("Warning!!"))
        input_dialog.setLabelText(msg)
        input_dialog.setTextValue("")  # empty by default

        ok = input_dialog.exec()  # Show the dialog

        if not ok or input_dialog.textValue().strip().lower() != 'delete':
            return

        # Log the deletion process
        log('Start deleting all download items')

        self.stop_all_downloads()
        self.selected_row_num = None
        n = len(self.d_list)

        for i in range(n):
            d = self.d_list[i]
            Thread(target=d.delete_tempfiles, daemon=True).start()

        self.d_list.clear()
        widgets.table.setRowCount(0)



    def pause_btn(self):
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            self.show_warning(self.tr("Error"), self.tr("No download item selected"))
            return

        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        if d.status == config.Status.completed:
            return

        d.status = config.Status.cancelled

        if d.status == config.Status.pending:
            self.pending.pop(d.id)



    def refresh_link_btn(self):
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            self.show_warning(self.tr("Error"), self.tr("No download item selected"))
            return

        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        config.download_folder = d.folder
        widgets.link_input.setText(d.url)
        self.url_text_change()
        widgets.folder_input.setText(config.download_folder)

        self.change_page(btn=None, btnName=None, idx=0)


    def stop_all_downloads(self):
        # change status of pending items to cancelled
        for d in self.d_list:
            d.status = config.Status.cancelled

        self.pending.clear()

    def resume_all_downloads(self):
        # change status of all non completed items to pending
        for d in self.d_list:
            if d.status == config.Status.cancelled:
                self.start_download(d, silent=True)


    # def schedule_all(self):
    #     try:
    #         response = ask_for_sched_time('Download scheduled for...')

    #         if response:
    #             for d in self.d_list:
    #                 if d.status in (config.Status.pending, config.Status.cancelled):
    #                     d.sched = response
    #                     log(f'Scheduled {d.name} for {response[0]}:{response[1]}')
    #     except Exception as e:
    #         log(f'Error in scheduling: {e}')

    def schedule_all(self):
        # Filter downloads eligible for scheduling
        schedulable = [d for d in self.d_list if d.status in (config.Status.pending, config.Status.cancelled)]

        if not schedulable:
            self.show_information(
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
            log(f'Error in scheduling: {e}')
            self.show_warning(self.tr("Schedule Error"), str(e))



    def setup_context_menu_actions(self):
        icon = lambda name: QIcon(os.path.join(os.path.dirname(__file__), "icons", name))

        self.action_open_file = QAction(icon("cil-file.png"), self.tr("Open File"))
        self.action_open_location = QAction(icon("cil-folder.png"), self.tr("Open File Location"))
        self.action_watch_downloading = QAction(icon("cil-media-play.png"), self.tr("Watch while downloading"))
        self.action_schedule_download = QAction(icon("cil-clock.png"), self.tr("Schedule download"))
        self.action_cancel_schedule = QAction(icon("cil-x.png"), self.tr("Cancel schedule!"))
        self.action_file_properties = QAction(icon("cil-info.png"), self.tr("File Properties"))

        # Connect triggers
        self.action_open_file.triggered.connect(self.open_item)
        self.action_open_location.triggered.connect(self.open_file_location)
        self.action_watch_downloading.triggered.connect(self.watch_downloading)
        self.action_schedule_download.triggered.connect(self.schedule_download)
        self.action_cancel_schedule.triggered.connect(self.cancel_schedule)
        self.action_file_properties.triggered.connect(self.file_properties)

    def context_menu_actions_state(self, status: str) -> dict:
        return {
            "open_file": status == "completed",
            "open_location": status == "completed",
            "watch": status in {"downloading", "paused", "pending"},
            "schedule": status in {"paused", "pending", "cancelled", "error", "failed", "deleted"},
            "cancel_schedule": status in {"scheduled", "pending", "downloading", "paused"},
            "properties": True,  # always enabled
        }


    def update_context_menu_actions_state(self, d):
        states = self.context_menu_actions_state(d.status)
        self.action_open_file.setEnabled(states["open_file"])
        self.action_open_location.setEnabled(states["open_location"])
        self.action_watch_downloading.setEnabled(states["watch"])
        self.action_schedule_download.setEnabled(states["schedule"])
        self.action_cancel_schedule.setEnabled(states["cancel_schedule"])
        self.action_file_properties.setEnabled(states["properties"])



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
        context_menu.addAction(self.action_open_file)
        context_menu.addAction(self.action_open_location)
        context_menu.addAction(self.action_watch_downloading)
        context_menu.addAction(self.action_schedule_download)
        context_menu.addAction(self.action_cancel_schedule)
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
                self.file_open_thread.critical_signal.connect(self.show_critical)

                # Start the thread
                self.file_open_thread.start()
                log(f"Opening completed file: {self.selected_d.target_file}")
            elif self.selected_d.status == config.Status.deleted:
                self.show_critical('File Not Found', f"The selected file could not be found or has been deleted.")
            else:
                self.show_warning(self.tr("Warning!!!"), self.tr("This download is not yet completed"))
        except Exception as e:
            log(f"Error opening file: {e}")




    def watch_downloading(self):
        selected_row = widgets.table.currentRow()


        self.selected_row_num = len(self.d_list) - 1 - selected_row
        try:
            # Always open the temporary file for in-progress downloads
            self.file_open_thread = FileOpenThread(self.selected_d.temp_file, self)
            self.file_open_thread.start()
            log(f"Watching in-progress download: {self.selected_d.temp_file}")
        except Exception as e:
            log(f"Error watching in-progress download: {e}")

    def open_file_location(self):
        selected_row = widgets.table.currentRow() 

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

        # Set selected_row_num to the selected row
        self.selected_row_num = len(self.d_list) - 1 - selected_row

        response = ask_for_sched_time(msg=self.selected_d.name)
        if response:
            setting.save_d_list(self.d_list)
            self.selected_d.status = config.Status.scheduled
            self.selected_d.sched = response
            print(f"THIS IS {self.selected_d.sched}")

    
    def cancel_schedule(self):
        selected_row = widgets.table.currentRow()

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
            d_progress = self.tr("Progress:")
            d_total_size = self.tr("Total size:")
            d_status = self.tr("Status:")
            d_resumable = self.tr("Resumable:")
            d_type = self.tr("Type:")
            d_protocol = self.tr("Protocol:")
            d_webpage_url = self.tr("Webpage url:")

            text = f'{d_name} {d.name} \n' \
                    f'{d_folder} {d.folder} \n' \
                    f'{d_progress} {d.progress}% \n' \
                    f'{d_total_size} {size_format(d.downloaded)} \n' \
                    f'{d_total_size} {size_format(d.total_size)} \n' \
                    f'{d_status} {d.status} \n' \
                    f'{d_resumable} {d.resumable} \n' \
                    f'{d_type} {d.type} \n' \
                    f'{d_protocol} {d.protocol} \n' \
                    f'{d_webpage_url} {d.url}'
            self.show_information(self.tr("File Properties"), inform="", msg=f"{text}")


    # region settings
    def settings_folder(self):
        # Get the currently selected value in the combo box
        selected = widgets_settings.setting_scope_combo.currentText()
        if selected == "Local":
            # Choose local folder as the settings folder
            config.sett_folder = config.current_directory

            # Remove settings.cfg from global folder
            delete_file(os.path.join(config.global_sett_folder, 'setting.cfg'))
        else:
            # Choose global folder as the settings folder
            config.sett_folder = config.global_sett_folder

            # Remove settings.cfg from local folder
            delete_file(os.path.join(config.current_directory, 'setting.cfg'))

            # Check if the global settings folder exists
            if not os.path.isdir(config.global_sett_folder):
                try:
                    # Display a confirmation dialog using QMessageBox
                    choice = QMessageBox.question(self, 'Create Folder', 
                                                f'Folder: {config.global_sett_folder}\nwill be created',
                                                QMessageBox.Ok | QMessageBox.Cancel)
                    
                    

                    # If the user cancels, raise an exception
                    if choice != QMessageBox.Cancel:
                        # Try to create the folder
                        os.mkdir(config.global_sett_folder)
                    else:
                        raise Exception('Operation Cancelled by User')

                except Exception as e:
                    # Log the error
                    log('global setting folder error:', e)

                    # If there is an error, use the current directory as the fallback
                    config.sett_folder = config.current_directory

                    # Show a popup with the error and inform the user about the fallback
                    ewc, lfw = self.tr("Error while creating global settings folder"), self.tr("Local folder will be used instead")
                    QMessageBox.critical(self, self.tr('Error'),
                                        f'{ewc} \n'
                                        f'"{config.global_sett_folder}"\n'
                                        f'{str(e)}\n'
                                        f'{lfw}')

                    # Update the combo box to reflect the local folder choice
                    widgets_settings.setting_scope_combo.setCurrentText('Local')

        # Update the combo box to reflect the current setting folder
        try:
            widgets_settings.setting_scope_combo.setCurrentText('Global' if config.sett_folder == config.global_sett_folder else 'Local')
        except:
            pass

    def button_state_table(self):
        # Connect selection change signal
        widgets.table.selectionModel().selectionChanged.connect(self.update_buttons_state)


    def update_buttons_state(self):
        # Get the number of selected rows
        selected_rows = widgets.table.selectionModel().selectedRows()
        selected_count = len(selected_rows) - 1 - selected_rows

      
        
        if selected_count == 1 or selected_count == 0:

        

            widgets.resume.setEnabled(True)
            widgets.resume_all.setEnabled(True)
            widgets.pause.setEnabled(True)
            widgets.d_window.setEnabled(True)
            widgets.stop_all.setEnabled(True)
            widgets.refresh.setEnabled(True)
            widgets.schedule_all.setEnabled(True)
            widgets.delete_all.setEnabled(True)
        
        else:
            widgets.resume.setEnabled(False)  
            widgets.resume_all.setEnabled(False)
            widgets.pause.setEnabled(False)
            widgets.d_window.setEnabled(False)
            widgets.stop_all.setEnabled(False)
            widgets.refresh.setEnabled(False)
            widgets.schedule_all.setEnabled(False)
            widgets.delete_all.setEnabled(False)

    # SWITCH LANGUAGE
    def switch_language(self):
        selected = widgets_settings.language_combo.currentText()
        if selected == "French":
            self.current_language = "French"
        elif selected == "Spanish":
            self.current_language = "Spanish"
        elif selected == "Japanese":
            self.current_language = "Japanese"
        elif selected == "Chinese":
            self.current_language = "Chinese"
        elif selected == "Korean":
            self.current_language = "Korean"
        else:
            self.current_language = "English"
        
        config.lang = self.current_language
    
            

        self.apply_language(self.current_language)

    def monitor_clip(self):
        checked = widgets_settings.monitor_clipboard_cb.isChecked()
        config.monitor_clipboard = checked
    
    def show_download_win(self):
        checked = widgets_settings.show_download_window_cb.isChecked()
        config.show_download_window = checked

    def auto_close_win(self):
        checked = widgets_settings.auto_close_cb.isChecked()
        config.auto_close_download_window = checked
    
    def show_thumb_nail(self):
        checked = widgets_settings.show_thumbnail_cb.isChecked()
        config.show_thumbnail = checked

    def on_startup(self):
        checked = widgets_settings.on_startup_cb.isChecked()
        if checked:
            if not (startup.checkStartUp()): 
                startup.addStartUp()
        else:
            if startup.checkStartUp():
                startup.removeStartUp()

        config.on_startup = checked

    def segment_size_set(self):
        selected_seg_unit = widgets_settings.segment_unit_combo.currentText()
        selected_seg_size = widgets_settings.segment_linedit.text()
        try:
            seg_size_unit = selected_seg_unit
            if seg_size_unit == 'KB':
                seg_size = int(selected_seg_size) * 1024
            else:
                seg_size = int(selected_seg_size) * 1024 * 1024
            config.segment_size = seg_size
            self.d.segment_size = seg_size
        except:
            pass

    def speed_limit_set(self):
        # Check the state of the checkbox and enable/disable the line edit accordingly
        
        if widgets_settings.speed_checkBox.isChecked():
            widgets_settings.speed_limit_input.setEnabled(True)  # Enable editing

            sl = widgets_settings.speed_limit_input.text().replace(' ', '')  # if values['speed_limit'] else 0

                    # validate speed limit,  expecting formats: number + (k, kb, m, mb) final value should be in kb
                    # pattern \d*[mk]b?

            match = re.fullmatch(r'\d+([mk]b?)?', sl, re.I)
            if match:

                digits = re.match(r"[0-9]+", sl, re.I).group()
                digits = int(digits)

                letters = re.search(r"[a-z]+", sl, re.I)
                letters = letters.group().lower() if letters else None


                if letters in ('k', 'kb', None):
                    sl = digits
                elif letters in ('m', 'mb'):
                    sl = digits * 1024
            else:
                sl = 0

            config.speed_limit = sl
            
            
        else:
            config.speed_limit = 0
            widgets_settings.speed_limit_input.setEnabled(False)  # Disable editing

    def max_current_dl(self):
        config.max_concurrent_downloads = int(widgets_settings.max_concurrent_combo.currentText())

    def max_connection(self):
        config.max_connections = int(widgets_settings.max_conn_settings_combo.currentText())

    def proxy_settings(self):
        if widgets_settings.checkBox_proxy.isChecked():
            widgets_settings.proxy_input.setEnabled(True)
            widgets_settings.proxy_type_combo.setEnabled(True)
            config.enable_proxy = True

            
            raw_proxy = widgets_settings.proxy_input.text()
            config.raw_proxy = raw_proxy

            # proxy type
            config.proxy_type = widgets_settings.proxy_type_combo.currentText()

            if raw_proxy and isinstance(raw_proxy, str):
                raw_proxy = raw_proxy.split('://')[-1]
                proxy = config.proxy_type + '://' + raw_proxy

                config.proxy = proxy
                widgets_settings.label_proxy_info.setText(config.proxy)
            
        
        else:
            config.enable_proxy = False
            config.proxy = ""
            config.raw_proxy = ""
            widgets_settings.label_proxy_info.setText(config.proxy)
            widgets_settings.proxy_input.setEnabled(False)
            widgets_settings.proxy_type_combo.setEnabled(False)

    # endregion



    
    def check_scheduled(self):
        now = time.localtime()

        for d in self.d_list:
            if d.status == config.Status.scheduled and getattr(d, "sched", None):
                if (d.sched[0], d.sched[1]) == (now.tm_hour, now.tm_min):
                    log(f"Scheduled time matched for {d.name}, attempting download...")

                    result = self.start_download(d, silent=True)

                    # Retry condition: download failed or was cancelled
                    if d.status in [config.Status.failed, config.Status.cancelled, config.Status.error]:
                        log(f"Scheduled download failed for {d.name}.")

                        if config.retry_scheduled_enabled:
                            d.schedule_retries = getattr(d, "schedule_retries", 0)

                            if d.schedule_retries < config.retry_scheduled_max_tries:
                                d.schedule_retries += 1

                                # Add retry interval
                                from datetime import datetime, timedelta
                                retry_time = datetime.now() + timedelta(
                                    minutes=config.retry_scheduled_interval_mins)
                                d.sched = (retry_time.hour, retry_time.minute)
                                d.status = config.Status.scheduled
                                log(f"Retrying {d.name} at {d.sched[0]}:{d.sched[1]} [Attempt {d.schedule_retries}]")
                            else:
                                d.status = config.Status.failed
                                log(f"{d.name} has reached max retries.")
                        else:
                            d.status = config.Status.failed

        self.queue_update("populate_table", None)





    

    # region update

    def change_cursor(self, cursor_type):
        """Change cursor to busy or normal."""
        if cursor_type == 'busy':
            QApplication.setOverrideCursor(Qt.WaitCursor)  # Busy cursor
        elif cursor_type == 'normal':
            QApplication.restoreOverrideCursor()  # Restore normal cursor

    def check_update_frequency(self):
        selected = int(widgets_settings.check_interval_combo.currentText())
        config.update_frequency = selected

    def update_available(self):
        self.change_cursor('busy')

        # check for update
        current_version = config.APP_VERSION
        info = update.get_changelog()

        if info:
            latest_version, version_description = info

            # compare with current application version
            newer_version = compare_versions(current_version, latest_version)  # return None if both equal
            

            if not newer_version or newer_version == current_version:
                self.new_version_available = False
                log("check_for_update() --> App. is up-to-date, server version=", latest_version)
            else:  # newer_version == latest_version
                self.new_version_available = True
                #self.show_information('Updates', '', 'Updates available')
                self.handle_update()
                

            # updaet global values
            config.APP_LATEST_VERSION = latest_version
            self.new_version_description = version_description
        else:
            self.new_version_description = None
            self.new_version_available = False

        self.change_cursor('normal')
    

    def download_window(self):
        selected_row = widgets.table.currentRow()
        
        if selected_row < 0 or selected_row >= len(self.d_list):
            self.show_warning(self.tr("Error"),self.tr("No download item selected"))
        # Set selected_row_num to the selected row
        self.selected_row_num = selected_row

        if self.selected_d:
            if config.auto_close_download_window and self.selected_d.status != config.Status.downloading:
                msg1, msg2 = self.tr("To open download window offline"), self.tr("go to setting tab, then uncheck auto close download window")
                self.show_information(title=self.tr('Information'),inform="", msg=f"{msg1} \n {msg2}")
    
                
                
            else:
                d = self.selected_d
                if d.id not in self.download_windows:
                    self.download_windows[d.id] = DownloadWindow(d=d)
                else:
                    self.download_windows[d.id].focus()


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
            self.show_information(
                title=self.tr("App Update"),
                inform=self.tr("App is up-to-date"),
                msg=f"{cv} {config.APP_VERSION}\n {sv} {config.APP_LATEST_VERSION}"
            )

            if not self.start_update_thread.new_version_description:
                ccu, cyi = self.tr("Couldn't check for update"), self.tr("Check your internet connection")
                self.show_critical(
                    title=self.tr("App Update"),
                    msg=f"{ccu} \n {cyi}"
                )
    

    def show_update_gui(self):
        # Create a QDialog (modal window)
        dialog = QDialog(self)
        dialog.setStyleSheet("background-color: rgb(33, 37, 43); color: white;")
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
        cancel_button = QPushButton(self.tr('Cancel'), dialog)
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

    def on_update_finished(self):
        self.show_information(title=config.APP_NAME, inform=self.tr("Update scheduled to run on the next reboot."), msg=self.tr("Please you can reboot now to install updates."))
    def check_for_ytdl_update(self):
        config.ytdl_LATEST_VERSION = update.check_for_ytdl_update()

    def update_ytdl(self):
        current_version = config.ytdl_VERSION
        latest_version = config.ytdl_LATEST_VERSION or update.check_for_ytdl_update()
        if latest_version:
            config.ytdl_LATEST_VERSION = latest_version
            log('youtube-dl update, latest version = ', latest_version, ' - current version = ', current_version)

            if latest_version != current_version:
                # select log tab
                self.change_page(btn=widgets.btn_new, btnName="btn_logs", page=widgets.new_page)

                msg = (f'Found new version of youtube-dl on github {latest_version}\n'
                    f'current version =  {current_version} \n'
                    'Install new version?')
                confirmation_box = QMessageBox(self)
                confirmation_box.setStyleSheet("background-color: rgb(33, 37, 43); color: white;")
                confirmation_box.setWindowTitle('yt-dlp module update')
                confirmation_box.setText(msg)
                confirmation_box.setIcon(QMessageBox.Question)
                confirmation_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                reply = confirmation_box.exec()

                if reply == QMessageBox.Yes:
                    try:
                        Thread(target=update.update_youtube_dl).start()
                    except Exception as e:
                        log('failed to update youtube-dl module:', e)
            else:
                self.show_information('YT-DLP', msg=f'yt-dlp is up-to-date, current version = {current_version}')       
    # endregion






# Redesigned ScheduleDialog with modern, sleek UI look
class ScheduleDialog(QDialog):
    def __init__(self, msg='', parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Schedule Download'))
        self.resize(420, 200)
        self.setStyleSheet("""
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
            QComboBox {
                background-color: rgba(28, 28, 30, 0.85);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 5px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(20, 25, 20, 0.95);
                border: 1px solid rgba(60, 200, 120, 0.25);
                selection-background-color: #2DE099;
                color: white;
            }
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
            QPushButton#CancelBtn {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
            }
            QPushButton#CancelBtn:hover {
                background-color: #666;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self.message_label = QLabel(msg)
        layout.addWidget(self.message_label)

        row_layout = QHBoxLayout()
        row_layout.setSpacing(10)

        self.hour_label = QLabel(self.tr("Hours:"))
        row_layout.addWidget(self.hour_label)
        self.hours_combo = QComboBox(self)
        self.hours_combo.addItems([str(i) for i in range(1, 13)])
        row_layout.addWidget(self.hours_combo)

        self.minute_label = QLabel(self.tr("Minutes:"))
        row_layout.addWidget(self.minute_label)
        self.minutes_combo = QComboBox(self)
        self.minutes_combo.addItems([f"{i:02d}" for i in range(0, 60)])
        row_layout.addWidget(self.minutes_combo)

        layout.addLayout(row_layout)

        am_pm_layout = QHBoxLayout()
        am_pm_layout.setAlignment(Qt.AlignCenter)
        self.am_pm_combo = QComboBox(self)
        self.am_pm_combo.addItems(['AM', 'PM'])
        am_pm_layout.addWidget(self.am_pm_combo)
        layout.addLayout(am_pm_layout)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        button_layout.setAlignment(Qt.AlignRight)

        self.ok_button = QPushButton(self.tr('Ok'), self)
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton(self.tr('Cancel'), self)
        self.cancel_button.setObjectName("CancelBtn")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.hours_combo.setCurrentIndex(0)
        self.minutes_combo.setCurrentIndex(0)
        self.am_pm_combo.setCurrentIndex(0)

    @property
    def response(self):
        h = int(self.hours_combo.currentText())
        m = int(self.minutes_combo.currentText())
        am_pm = self.am_pm_combo.currentText()

        if am_pm == 'PM' and h != 12:
            h += 12
        elif am_pm == 'AM' and h == 12:
            h = 0

        return h, m

def ask_for_sched_time(msg=''):
    dialog = ScheduleDialog(msg)
    result = dialog.exec()  # Show the dialog as a modal

    if result == QDialog.Accepted:
        return dialog.response  # Return the (hours, minutes) tuple
    return None




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
        self.q = d.q
        self.timeout = 10
        self.timer = 0
        self._progress_mode = 'determinate'
        self.init_ui()
        self.resize(500, 330)

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
               f"\n Live connections: {self.d.live_connections} - Remaining parts: {self.d.remaining_parts} \n")
        self.out_label.setText(out)

        if self.d.progress:
            self.set_progress_mode('determinate')
            self.progress_bar.setValue(int(self.d.progress))
        else:
            self.set_progress_mode('indeterminate')

        if self.d.status in (config.Status.completed, config.Status.cancelled, config.Status.error) and config.auto_close_download_window:
            self.close()

        if self.d.status in (config.Status.completed, config.Status.cancelled, config.Status.error):
            self.hide_button.setStyleSheet("background-color: white; color: black;")
            self.cancel_button.setText(self.tr('Done'))
            self.cancel_button.setStyleSheet('background-color: grey; color: white;')

        self.log_display.setPlainText(config.log_entry)
        self.percent_label.setText(f"{self.d.progress}%")
        self.percent_label.setStyleSheet("""
            QLabel {
                color: white;
            }
                                         
        """)
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









if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = DownloadManagerUI(config.d_list)
    window.show()
    # Optionally, run a method after the main window is initialized
    QTimer.singleShot(0, video.import_ytdl)
    sys.exit(app.exec())







