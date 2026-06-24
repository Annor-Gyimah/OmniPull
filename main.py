#######################################################################################
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
import re
import sys
import copy
import glob
import time
import json
import shlex
import shutil
import asyncio
import hashlib
import platform
import threading
import requests
import subprocess
import omnipull_url_processor

from typing import Any
from pathlib import Path
from collections import deque
from threading import Thread, Timer
from typing import Callable, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote, parse_qs, urlencode, urlunparse

# region 3rd Parties import
from PySide6 import QtWidgets
from PySide6.QtCore import (QTimer, QPoint, QThread, Signal, Slot, QUrl, QTranslator, 
QCoreApplication, Qt, QTime, QProcess, QEvent, QStringListModel, QDateTime)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QLocalServer, QLocalSocket
from PySide6.QtGui import QAction, QIcon, QPixmap, QImage, QDesktopServices, QKeySequence, QColor
from PySide6.QtWidgets import (QMainWindow, QApplication, QFileDialog, QMessageBox, QLineEdit,
QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout, QWidget, QTableWidgetItem, QDialog, 
QComboBox, QInputDialog, QMenu, QRadioButton, QButtonGroup, QScrollArea, QCheckBox, QListWidget, QListWidgetItem, QWidgetAction, 
QFrame, QGridLayout, QCompleter)



from ui.ui_main import Ui_MainWindow
from ui.help_window import HelpWindow
from ui.about_dialog import AboutDialog
from ui.queue_dialog import QueueDialog
from ui.tray_icon import TrayIconManager
from ui.setting_dialog import SettingsDialog
from ui.schedule_dialog import ScheduleDialog
from ui.category_dialog import CategoryDialog
from ui.add_downloads import AddDownloadWindow
from ui.changelog_dialog import WhatsNewDialog
from ui.populate_worker import PopulateTableWorker
from ui.download_window import DownloadProgressDialog
from ui.advanced_metadata_dialog import AdvancedMetadataDialog
from ui.plugin_bar import PluginBar



from ui.styles import get_stylesheet
from ui.language_manager import LanguageManager



from modules.brain import brain
from modules.threadpool import executor
from modules.setting import save_setting
from modules.plugin_manager import PluginManager
from modules.batch_importer import BatchImportWorker
from modules import config, native_engine
from modules.downloaditem import DownloadItem
from modules.aria2c_manager import aria2c_manager
from modules.settings_manager import SettingsManager
from modules.updater import update, update_yt_dlp, get_changelog
from modules.startup import addStartUp, checkStartUp, removeStartUp
from modules.video import (Video, check_ffmpeg, check_deno,check_dependency_installed, download_dependency, download_deno, download_ffmpeg, import_ytdl, get_ytdl_options, extract_info_blocking)
from modules.utils import (size_format, validate_file_name, compare_versions, compare_versions_2, log, time_format,
    notify, run_command, handle_exceptions, get_headers, delete_folder, delete_file)
from modules.helpers import (toolbar_buttons_state, get_msgbox_style, change_cursor, show_information,
    show_critical, show_warning, open_with_dialog_windows, safe_filename, get_ext_from_format, _best_existing, 
    _norm_title, _pick_container_from_video, _expected_paths, _extract_title_from_pattern, janitor, get_today_download_stats,
    calculate_total_speed, get_progress_bar_color, find_download_by_id, get_file_icon, 
    CATEGORY_TRANSLATIONS, UPDATE_AVAILABLE_TRANSLATIONS, nuclear_scrub, update_native_manifests, fix_browser_integration, mark_install_healthy)

from modules.log_recorder import LogRecorderThread
from modules.single_instance import SingleInstanceApp
from ui.file_properties_dialog import FilePropertiesDialog
from ui.file_threads import FileChecksum, FileOpenThread
from ui.subtitle_dialog import SubtitleFailedDialog
from ui.update_threads import CheckUpdateAppThread, UpdateThread, YtDlpUpdateThread
from ui.widgets import MarqueeLabel
from ui.youtube_thread import YouTubeThread



# Trigger scrub IMMEDIATELY upon execution
nuclear_scrub()

# os.environ.setdefault("QT_QPA_PLATFORMTHEME", "gtk3")

from ui.mixins.ui_manager import UIManagerMixin
from ui.mixins.terminal import TerminalMixin
from ui.mixins.update_controller import UpdateControllerMixin
from ui.mixins.download_controller import DownloadControllerMixin
from ui.mixins.url_processor import URLProcessorMixin
from ui.mixins.media_preview import MediaPreviewMixin
from ui.mixins.context_menu import ContextMenuMixin
from ui.mixins.table_manager import TableManagerMixin

class DownloadManagerWindow(
    UIManagerMixin,
    TerminalMixin,
    UpdateControllerMixin,
    DownloadControllerMixin,
    URLProcessorMixin,
    MediaPreviewMixin,
    ContextMenuMixin,
    TableManagerMixin,
    QMainWindow,
):
    """
    The primary UI controller and orchestrator for the OmniPull application.
    
    This class manages the main application lifecycle, including theme 
    normalization, sub-window instantiation (Settings, Queues, Add Download), 
    and the coordination of background threads (LogRecorder, BrowserMonitor). 
    It serves as the central hub for signal-slot connections between the 
    UI components and the download engine.
    """
    update_gui_signal = Signal(dict)


    def __init__(self, d_list):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ctx = "MAIN-WINDOW"

        log("Initializing Main Window and verifying configuration...", 
            log_level=1, context=self.ctx)

        # ── Theme Normalization ───────────────────────────────────────────────
        # Ensures legacy theme names are mapped to the modern dark/light system.
        theme = config.current_theme.lower()
        if theme not in ["dark", "light", "system"]:
            if "dark" in theme or "grey" in theme:
                config.current_theme = "dark"
            else:
                config.current_theme = "light"
        
        self.current_theme = config.current_theme
        self.ui.setupUi(self)

       

        # ── Plugin Bar Manager ───────────────────────────────────────────────
        # Initialize the plugin bar to display installed plugins
        self.plugin_bar_manager = PluginBar(
            container_layout=self.ui.plugins_container,
            no_plugins_label=self.ui.no_plugins_label,
            main_window=self
        )

        # ── UI State & Sub-Windows ───────────────────────────────────────────
        # Instantiate secondary windows and initialize their default states.
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        
        self.ui_add_download = AddDownloadWindow(self)
        self.ui_add_download.advance_btn.setEnabled(False)
        self.ui_add_download.advance_btn.clicked.connect(self.on_advanced_button_clicked)
        
        self.ui_settings = SettingsDialog(self)
        # self.ui_queues = QueueDialog(self)
        self.ui_schedule_dia = ScheduleDialog(self)
        
        # Internal state tracking
        self.last_schedule_check = {} 
        self.running_queues = {}
        self.download_windows = {}
        self.background_threads = [] 
        self.ui_queues = QueueDialog(self)
        self._remux_procs = {} 

        self.ui.table.itemSelectionChanged.connect(self.update_toolbar_buttons_for_selection)

        # Global widget references for cross-module accessibility
        global widgets, widgets_add_download, widgets_settings
        widgets = self.ui
        widgets_settings = self.ui_settings
        widgets_add_download = self.ui_add_download

        # ── Core Engine State ────────────────────────────────────────────────
        self.setWindowTitle(config.APP_TITLE)
        self.d = DownloadItem() 
        self.yt_thread = None 
        self.url_timer = None 
        self.bad_headers = [0, range(400, 404), range(405, 418), range(500, 506)]
        self.pending = deque()
        self.disabled = True 

        # Data model initialization
        self.d_headers = ['id', 'name', 'progress', 'speed', 'time_left', 'downloaded', 'total_size', 'status', 'i']
        self.d_list = d_list 
        self.selected_row_num = None
        self._selected_d = None
        self._active_downloads_cache = set()
        self._active_downloads_cache_time = 0
        self._last_progress_values = {}
        self._is_batch_mode = False
        self._batch_items = []
        self._batch_total_size = 0
        self._batch_worker   = None
        self._batch_ui_active = False

        # ── YouTube & Media State ────────────────────────────────────────────
        self.video = None
        self.yt_id = 0
        self.playlist = []
        self.pl_title = ''
        self.pl_quality = None
        self._pl_menu = []
        self._stream_menu = []
        self._is_playlist_mode = False
        self.current_thumbnail = None
        self.filename_set_by_program = False
        self._url_processing = False
        self._processing_cancel_requested = False

        # ── Signals & System Tasks ───────────────────────────────────────────
        self.update_gui_signal.connect(self.process_gui_updates)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_for_gui_updates)
        self.update_timer.start(250)
        self.pending_updates = {}
        
        self.network_manager = QNetworkAccessManager()
        self.network_manager.finished.connect(self.on_thumbnail_downloaded)
        self.one_time, self.check_time = True, True

        # Launch persistent background services
        self._start_background_services()

        # UI refresh timer (900ms cycle)
        self.run_timer = QTimer(self)
        self.run_timer.timeout.connect(self.run)
        self.run_timer.start(900)

        # ── IO & Persistence ─────────────────────────────────────────────────
        log("Loading persistent settings and download history from disk...", 
            log_level=1, context=self.ctx)
        os.chdir(config.current_directory)
        self.settings_manager = SettingsManager()
        self.settings_manager.load_settings()
        self.d_list = self.settings_manager.load_d_list()
        self.plugin_mgr = PluginManager.instance()
        self.plugin_mgr.setup(
            d_list=self.d_list,
            main_q=config.main_window_q,
            plugins_dir=str(config.DATA_ROOT / "plugins"),
        )
        
        # Set callback to refresh UI when plugins change
        self.plugin_mgr.on_plugins_changed = self._on_plugins_changed
        
        def _load_plugins_and_refresh():
            self.plugin_mgr.load_all()
            config.main_window_q.put(("_refresh_plugin_bar", None))

        threading.Thread(target=_load_plugins_and_refresh, daemon=True, name="plugin-loader").start()
        
        self.ui_queues.main_window = self
        self.tray_manager = TrayIconManager(self)

        # ── Interaction Mapping ──────────────────────────────────────────────
        self._connect_signals()
        
        # ── Final Initialization ─────────────────────────────────────────────
        # self.translator = QTranslator() 
        self.setup_context_menu_actions()
        self.current_language = config.lang
        self.lang_manager = LanguageManager()

        # Apply language
        self.lang_manager.apply_language_global(self.current_language)
        self.lang_manager.apply_language(self.current_language)
        self.retrans()
        

        self.set_theme(self.current_theme)
        self._apply_styles()
        self.queue_combo()
        
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_scheduled_queues)
        self.scheduler_timer.start(60000) 
        
        self.category_list(language=config.lang)
        
        try:
            self.populate_table()
        except Exception as e:
            log(f"Initial table population failed: {e}", log_level=2, context=self.ctx)

        self._setup_terminal_interface()
        log("OmniPull core initialized and ready.", log_level=1, context=self.ctx)

    def _start_background_services(self):
        """Initializes and tracks threads responsible for logging and browser integration."""
        # Log Recorder
        self.log_recorder_thread = LogRecorderThread()
        self.log_recorder_thread.start()
        self.background_threads.append(self.log_recorder_thread)

        # Browser Monitor
        from modules.browser_queue_monitor import BrowserQueueMonitor
        self.browser_queue_monitor = BrowserQueueMonitor()
        self.browser_queue_monitor.download_detected.connect(self.on_browser_download_detected)
        self.browser_queue_monitor.start()
        self.background_threads.append(self.browser_queue_monitor)

        # Setup clipboard monitoring
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.old_clipboard_data = ''
        log("Background services (Logging, Browser Monitoring, Clipboard Monitoring) active.", 
            log_level=1, context=self.ctx)

    def _on_plugins_changed(self):
        """
        Callback invoked by PluginManager when plugins are loaded or modified.
        Refreshes the plugin bar UI to reflect the current installed plugins.
        Ensures UI updates happen on the main thread.
        """
        if hasattr(self, 'plugin_bar_manager'):
            try:
                # Defer to main thread if called from background thread
                from PySide6.QtCore import QCoreApplication, QThread
                app = QCoreApplication.instance()
                log(f"_on_plugins_changed: current_thread={QThread.currentThread().objectName() if QThread.currentThread() else 'Unknown'}, main_thread={self.thread().objectName() if self.thread() else 'Unknown'}", 
                    log_level=1, context=self.ctx)
                if app and app.thread() == QThread.currentThread():
                    log("_on_plugins_changed: calling refresh from main thread", log_level=1, context=self.ctx)
                    self.plugin_bar_manager.refresh(self.plugin_mgr)
                else:
                    from PySide6.QtCore import QTimer
                    log("_on_plugins_changed: deferring refresh to main thread", log_level=1, context=self.ctx)
                    QTimer.singleShot(0, lambda: self.plugin_bar_manager.refresh(self.plugin_mgr))
            except Exception as e:
                log(f"Error refreshing plugin bar: {e}", log_level=2, context=self.ctx)
                import traceback
                log(traceback.format_exc(), log_level=3, context=self.ctx)

    def _connect_signals(self):
        """Maps UI signals to their respective handler functions."""
        # Actions & Toolbars
        widgets.add_action.triggered.connect(self.show_add_dialog)
        widgets.open_file_menu.aboutToShow.connect(self.populate_open_menu)
        widgets.settings_action.triggered.connect(self.show_settings_dialog)
        widgets.queue_action.triggered.connect(self.show_queue_dialog)
        widgets.category_action.triggered.connect(self.show_category_dialog)
        widgets.category_list.currentItemChanged.connect(self._filter_by_category)
        widgets.action_theme_dark.triggered.connect(lambda: self.set_theme("dark"))
        widgets.action_theme_light.triggered.connect(lambda: self.set_theme("light"))
        widgets.whats_new_action.triggered.connect(self.show_whatsnew_dialog)
        widgets.about_action.triggered.connect(self.show_about_dialog)
        widgets.scheduler_action.triggered.connect(self.schedule_all)
        widgets.install_ytdlp_action.triggered.connect(self.install_ytdlp)
        widgets.install_deno_action.triggered.connect(self.install_deno)
        widgets.install_ffmpeg_action.triggered.connect(self.install_ffmpeg)
        widgets.marketplace_action.triggered.connect(self.show_marketplace)
        widgets.resume_all_action.triggered.connect(self.resume_all_downloads)
        widgets.stop_all_action.triggered.connect(self.stop_all_downloads)
        widgets.delete_all_action.triggered.connect(self.delete_all_downloads)
        widgets.report_issue_action.triggered.connect(self.open_github_issues)
        widgets.tutorials_action.triggered.connect(self.open_help)
        widgets.browser_ext_chrome_action.setEnabled(False)  
        widgets.browser_ext_firefox_action.triggered.connect(lambda: self.install_browser_extension("Firefox"))
        widgets.browser_ext_edge_action.triggered.connect(lambda: self.install_browser_extension("Edge"))
        widgets.exit_action.triggered.connect(self.exit_app)
        widgets.check_for_updates_action.triggered.connect(self.start_update)
        
        
        
        # Controls
        widgets_add_download.download_btn.clicked.connect(self.on_download_button_clicked)
        widgets_add_download.filename_edit.textChanged.connect(self.on_filename_changed)
        widgets_add_download.change_folder_btn.clicked.connect(self.open_folder_dialog)
        widgets_add_download.import_btn.clicked.connect(self.on_import_file_clicked)
        widgets_add_download.retry_btn.clicked.connect(self.retry)
        widgets_add_download.cancel_close_btn.clicked.connect(self.on_cancel_close_clicked)
        widgets_add_download.resolution_combo.currentTextChanged.connect(self.stream_OnChoice)
        widgets_add_download.category_combo.currentTextChanged.connect(self.category_onChoice)
        widgets_add_download.queue_combo.currentTextChanged.connect(self.on_selection_queue)
        widgets_add_download.queue_combo.currentTextChanged.connect(self._refresh_batch_button_label)
        widgets.btn_add.triggered.connect(self.show_add_dialog)
        widgets.btn_delete_all.triggered.connect(self.delete_all_downloads)
        widgets.btn_pause.triggered.connect(self.pause_btn)
        widgets.btn_resume.triggered.connect(self.resume_btn)
        widgets.btn_stop_all.triggered.connect(self.stop_all_downloads)
        widgets.btn_settings.triggered.connect(self.show_settings_dialog)
        widgets.btn_refresh.triggered.connect(self.refresh_link_btn)
        widgets.btn_resume_all.triggered.connect(self.resume_all_downloads)
        widgets.btn_scheduler.triggered.connect(self.schedule_all)
        widgets.btn_terminal.toggled.connect(self.toggle_terminal_view)
        
        
       
        
        # Terminal & Table
        widgets.table.setContextMenuPolicy(Qt.CustomContextMenu)
        widgets.filter_edit.textChanged.connect(self.filter_download_table)
        widgets.sort_combo.currentTextChanged.connect(self.on_sort_changed)
        widgets.log_level_combo.currentTextChanged.connect(self.set_log)
        widgets.log_level_combo.setCurrentText(str(config.log_level))
        widgets.log_clear_btn.clicked.connect(self.clear_log)
        widgets.table.customContextMenuRequested.connect(self.show_table_context_menu)
        widgets.terminal_input.returnPressed.connect(self._terminal_exec)

        widgets.lbl_version.setText(f"App Version: {config.APP_VERSION}")

        
        def _maybe_restore_banner():
            dismissed_ts = getattr(config, 'update_dismissed_timestamp', None)
            latest = getattr(config, 'APP_LATEST_VERSION', None)
            current = config.APP_VERSION
            if not dismissed_ts or not latest:
                return
            if compare_versions(current, latest) not in (None, current):
                self._show_update_banner()

        QTimer.singleShot(0, _maybe_restore_banner)
        
        log("Signal-slot connections established.", log_level=2, context=self.ctx)

    def _setup_terminal_interface(self):
        """Configures the embedded terminal with autocompletion and history."""
        self._ytdlp_options = self.load_ytdlp_options()
        model = QStringListModel(self._ytdlp_options)
        self._terminal_completer = QCompleter(model, self)
        self._terminal_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._terminal_completer.setCompletionMode(QCompleter.PopupCompletion)
        widgets.terminal_input.setCompleter(self._terminal_completer)
        
        self._terminal_history = []
        self._history_index = -1
        self._current_proc = None
        
        fix_browser_integration()
        log("Embedded terminal environment ready.", log_level=1, context=self.ctx)

    def read_q(self):
        """
        Consumes messages from the primary thread-safe communication queue.
        
        This method acts as the 'Post Office' for the application. It receives 
        commands (keys) and data (values) from background workers and 
        dispatches them to the appropriate UI methods on the main thread.
        """
        ctx = "GUI-SYNC"
        while not config.main_window_q.empty():
            k, v = config.main_window_q.get()

            # 1. Terminal / Logging Redirection
            if k == 'log':
                try:
                    contents = widgets.terminal_output.toPlainText()
                    # Circular buffer logic: prevent memory exhaustion from long logs
                    if len(contents) > config.max_log_size:
                        slice_size = int(config.max_log_size * 0.2)
                        widgets.terminal_output.setPlainText(contents[slice_size:])

                    # Heuristic parsing for yt-dlp playlist extraction progress
                    if '[download]' in v and 'of' in v:
                        try:
                            # Extract current/total to update the extraction progress bar
                            parts = v.rsplit(maxsplit=3)
                            num, total = int(parts[-3]), int(parts[-1])
                            percent = (num * 100 // total) // 2
                            self.update_progress_bar_value(percent)
                        except Exception:
                            pass

                    widgets.terminal_output.appendPlainText(v)
                except Exception as e:
                    log(f"Terminal output failed: {e}", log_level=3, context=ctx)

            # 2. Automated Download Triggers (Clipboard/Browser)
            elif k == 'url':
                url = (v or "").strip()
                if not url: continue
                
                log(f"Queue signal: Processing external URL request: {url[:40]}...", 
                    log_level=1, context=ctx)
                widgets_add_download.url_progress.show()
                widgets_add_download.url_progress.setRange(0, 0)
                widgets_add_download.url_edit.setText(url)
                self.url_text_change()

            # 3. Dialog & UI State Management
            elif k == "popup":
                # Centralized handler for Info/Warning/Critical popups
                handlers = {
                    'info': show_information,
                    'warning': show_warning,
                    'critical': show_critical
                }
                handler = handlers.get(v.get('type_'), show_information)
                handler(self, title=v.get('title'), msg=v.get('msg'))

            elif k == "subtitle_failed":
                self.show_subtitle_failed_dialog(v)

            # 4. Global Action Dispatching
            elif k == "download":
                self.start_download(*v)
            elif k == "queue_download":
                self._queue_or_start_download(*v)
            elif k == "pause_btn":
                self.pause_btn()
            elif k == "monitor":
                widgets_settings.monitor_clipboard_chk.setChecked(v)
            elif k == "category_list":
                self.category_list(language=config.lang)
            elif k == "queue_list":
                self.queue_combo()
            elif k == 'show_update_gui':
                self.show_update_gui()
            elif k == "update call":
                self.start_update(*v)
            elif k == "yt-dlp update call":
                self.start_update_yt_dlp(*v)
            elif k == 'remove_internal_download':
                item_id = v
                # 1. Find the item in d_list
                item_to_remove = next((item for item in self.d_list if item.id == item_id), None)
                if item_to_remove:
                    delete_folder(self.d.temp_folder)
                    self.d_list.remove(item_to_remove)
                    # 2. Save the clean list
                    self.settings_manager.save_d_list(self.d_list)
                    log(f"Cleaned up internal dependency task (ID: {item_id})")
            elif k == "_refresh_plugin_bar":
                if hasattr(self, "plugin_bar_manager") and hasattr(self, "plugin_mgr"):
                    self.plugin_bar_manager.refresh(self.plugin_mgr)

    def run(self):
        """
        The heartbeat of the UI thread loop.
        
        Executes on a regular interval (900ms) to drain the communication 
        queues and trigger bulk GUI component updates.
        """
        try:
            self.read_q()
        except Exception as e:
            log(f"Task queue consumption failed: {e}", log_level=3, context=self.ctx)
        
        try:
            self.queue_updates()
        except Exception as e:
            log(f"GUI batch update failed: {e}", log_level=3, context=self.ctx)

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
                    config.last_update_check = today
            except (TypeError, ValueError) as e:
                log(f"Error in update check calculations: {e}", log_level=3)
            except Exception as e:
                log(f"Error in run loop: {e}", log_level=3)

    def check_for_gui_updates(self):
        """
        Emits the accumulated pending updates to the GUI signal handler.
        
        By bundling updates into a single signal, we reduce 'GUI jitter' 
        and lower CPU overhead compared to updating individual labels.
        """
        if self.pending_updates:
            self.update_gui_signal.emit(self.pending_updates)
            self.pending_updates.clear()

    def queue_update(self, key, value):
        self.pending_updates[key] = value

    @Slot(dict)
    def process_gui_updates(self, updates: dict[str, Any]) -> None:
        """
        Final execution point for UI modifications on the Main Thread.
        
        Receives a dictionary of pending changes and applies them to 
        the physical widgets (labels, tables, and progress bars).
        """
        try:
            for key, value in updates.items():
                if key == 'filename':
                    if widgets_add_download.filename_edit.text() != value:
                        self.filename_set_by_program = True
                        widgets_add_download.filename_edit.setText(value)
                        self.filename_set_by_program = False
                
                elif key == 'status_code':
                    self.update_http_status(value)
                
                elif key == 'size':
                    if not getattr(self, '_batch_ui_active', False):  # ← add this line
                        size_text = size_format(value) if value else "Unknown"
                        widgets_add_download.lbl_size_value.setText(size_text)

                elif key == 'total_speed':
                    speed_text = f'{size_format(value, "/s")}' if value else '0 bytes'
                    widgets.lbl_speed.setText(speed_text)
                
                elif key == 'populate_table':
                    self.populate_table()
                
                # Internal maintenance tasks
                
                elif key == 'check_scheduled': self.check_scheduled()
                elif key == 'pending_jobs': self.pending_jobs()
                elif key == 'on_startup': self.on_startup()
                elif key == '_handle_version_status': self._handle_version_status()
        
            # Persistence: Periodic auto-save of the download list state
            self.settings_manager.save_settings()
            self.settings_manager.save_d_list(self.d_list)

        except Exception as e:
            log(f"GUI signal processing error: {e}", log_level=3, context="GUI-SYNC")

    def queue_updates(self):
        """
        Collects current DownloadItem state and prepares it for the next GUI sync.
        
        This method gathers live data (speed, progress, metadata) and stores 
        it in the 'pending_updates' buffer to be processed by the main thread.
        """
        # Core metadata sync
        self.queue_update('filename', self.d.name)
        self.queue_update('status_code', self.d.status_code)
        self.queue_update('size', self.d.total_size)
        self.queue_update('type', self.d.type)
        self.queue_update('protocol', self.d.protocol)
        self.queue_update('resumable', self.d.resumable)
        
        # Calculate aggregate bandwidth across all active tasks
        total_speed = calculate_total_speed(self.d_list, self.active_downloads)
        self.queue_update('total_speed', total_speed)

        # Maintenance Flags
        
        self.queue_update('populate_table', None)
        self.queue_update('check_scheduled', None)
        self.queue_update('_handle_version_status', None)
        self.queue_update('pending_jobs', None)
        self.queue_update('on_startup', None)
        
        self.update_table_progress()


def load_initial_translator(app):
    """Loads the language saved in config before the main window is created."""
    from modules.config import lang
    import os

    file_map = {
        "French": "app_fr.qm",
        "Spanish": "app_es.qm",
        "Chinese": "app_zh.qm",
        "Korean": "app_ko.qm",
        "Japanese": "app_ja.qm",
        "English": "app_en.qm",
        "Hindi": "app_hi.qm",
        "Russian": "app_ru.qm"
    }

    translator = QTranslator(app)
    path = os.path.join(os.path.dirname(__file__), "translations", file_map.get(lang, "app_en.qm"))

    if translator.load(path):
        app.installTranslator(translator)
    return translator  # Keep reference to prevent garbage collection


# ── Application Entry & Lifecycle  ────────────────────────────────────────

def main():
    """
    The main execution entry point for OmniPull.

    Orchestrates the following startup sequence:
    1. Socket Collision Prevention: Brief sleep to allow OS port cleanup.
    2. Instance Locking: Ensures only one copy of OmniPull is active.
    3. Argument Parsing: Detects post-update or tray-start flags.
    4. Window Initialization: Sets up the Main Window and Tray logic.
    5. Lazy Loading: Defers heavy library imports (yt-dlp) to keep startup snappy.
    """
    ctx = "APP-LIFECYCLE"

    # Brief pause to prevent socket collisions during rapid restarts/updates
    time.sleep(1.5)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(":/icons/omnipull.ico"))

    # ── 1. Single Instance Enforcement ──
    app_id = "omnipull"
    single_instance = SingleInstanceApp(app_id)

    if single_instance.is_running():
        # Avoid annoying the user with a popup if this is an automated update restart
        if '--updated' not in sys.argv:
            msg = QCoreApplication.translate("Main", "Another instance of the application is already running.")
            QMessageBox.warning(None, "OmniPull", msg)

        log("Startup aborted: Another instance is active.", log_level=2, context=ctx)
        sys.exit(0)

    # Begin listening for external URL signals (from browser extensions)
    single_instance.start_server()

    # ── 2. Startup State Detection ──
    is_post_update = '--updated' in sys.argv
    start_to_tray = '--tray' in sys.argv or is_post_update

    # Initialize the main UI with the existing download list
    win = DownloadManagerWindow(config.d_list)

    # ── 3. Visibility Management ──
    if is_post_update:
        log("Post-update restart detected. Initializing silently in system tray.",
            log_level=1, context=ctx)
        win.hide()
        config.hide_app = True

    elif start_to_tray:
        log("System tray startup detected. Window hidden.",
            log_level=1, context=ctx)
        win.hide()

    else:
        log("Standard startup: Opening main dashboard.",
            log_level=1, context=ctx)
        win.show()

    # ── 4. Performance Optimization ──
    # Defer heavy imports (like yt-dlp) until the UI loop is already spinning.
    QTimer.singleShot(0, import_ytdl)

    if not config.IS_WIN:
        # Mark healthy after stable startup
        QTimer.singleShot(5000, mark_install_healthy)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
