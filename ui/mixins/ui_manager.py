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

from typing import Any, Callable, Optional
from pathlib import Path
from collections import deque
from threading import Thread, Timer
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote, parse_qs, urlencode, urlunparse

from PySide6 import QtWidgets
from PySide6.QtCore import (QTimer, QPoint, QThread, Signal, Slot, QUrl, QTranslator,
    QCoreApplication, Qt, QTime, QProcess, QEvent, QStringListModel, QDateTime)
from PySide6.QtNetwork import (QNetworkAccessManager, QNetworkRequest, QNetworkReply,
    QLocalServer, QLocalSocket)
from PySide6.QtGui import QAction, QIcon, QPixmap, QImage, QDesktopServices, QKeySequence, QColor
from PySide6.QtWidgets import (QMainWindow, QApplication, QFileDialog, QMessageBox, QLineEdit,
    QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout, QWidget, QTableWidgetItem, QDialog,
    QComboBox, QInputDialog, QMenu, QRadioButton, QButtonGroup, QScrollArea, QCheckBox,
    QListWidget, QListWidgetItem, QWidgetAction, QFrame, QGridLayout, QCompleter)

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
from ui.file_properties_dialog import FilePropertiesDialog
from ui.file_threads import FileChecksum, FileOpenThread
from ui.subtitle_dialog import SubtitleFailedDialog
from ui.update_threads import CheckUpdateAppThread, UpdateThread, YtDlpUpdateThread
from ui.widgets import MarqueeLabel
from ui.youtube_thread import YouTubeThread

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
from modules.video import (Video, check_ffmpeg, check_deno, check_dependency_installed,
    download_dependency, download_deno, download_ffmpeg, import_ytdl,
    get_ytdl_options, extract_info_blocking)
from modules.utils import (size_format, validate_file_name, compare_versions, compare_versions_2,
    log, time_format, notify, run_command, handle_exceptions, get_headers,
    delete_folder, delete_file)
from modules.helpers import (toolbar_buttons_state, get_msgbox_style, change_cursor,
    show_information, show_critical, show_warning, open_with_dialog_windows,
    safe_filename, get_ext_from_format, _best_existing, _norm_title,
    _pick_container_from_video, _expected_paths, _extract_title_from_pattern,
    janitor, get_today_download_stats, calculate_total_speed, get_progress_bar_color,
    find_download_by_id, get_file_icon, CATEGORY_TRANSLATIONS,
    UPDATE_AVAILABLE_TRANSLATIONS, nuclear_scrub, update_native_manifests,
    fix_browser_integration, mark_install_healthy)
from modules.log_recorder import LogRecorderThread
from modules.single_instance import SingleInstanceApp


class UIManagerMixin:
    """Mixin providing UIManager methods for DownloadManagerWindow."""

    def update_datetime(self):
        """Refreshes the global status bar clock with the current system time."""
        current = QDateTime.currentDateTime()
        self.ui.datetime_label.setText(current.toString("yyyy-MM-dd HH:mm:ss"))


    def show_add_dialog(self):
        """
        Prepares and displays the primary Add Download dialog.
        Synchronizes folder paths, queues, and categories before rendering.
        """
        self.ui_add_download.save_to_edit.setText(config.download_folder)
        self.queue_combo()
        self.category_list(language=config.lang)
        self.ui_add_download.setStyleSheet(get_stylesheet(self.current_theme))
        self.ui_add_download.show()
        self.ui_add_download.raise_()
        if getattr(self, '_is_playlist_mode', False) and getattr(self, 'playlist', None):
            self.ui_add_download.download_btn.setText(self.tr("Start Playlist"))


    def show_add_dialog_only(self):
        """
        Renders the Add Download dialog as a standalone window.
        Specifically utilized for browser-intercepted links when the main UI is minimized.
        """
        log("Intercepting remote download request; spawning standalone dialog", 
            log_level=1, context=self.ctx)
        self.ui_add_download.save_to_edit.setText(config.download_folder)
        self.queue_combo()
        self.category_list(language=config.lang)
    
        self.ui_add_download.setWindowFlags(
            self.ui_add_download.windowFlags() | Qt.WindowStaysOnTopHint
        )
        self.ui_add_download.show()
        self.ui_add_download.raise_()
        self.ui_add_download.activateWindow()


    def show_queue_dialog(self):
        """Launches the Queue Management interface."""
        self.ui_queues.d_list = self.d_list 
        self.ui_queues.populate_queue_items()
        self.ui_queues.exec()


    def show_category_dialog(self):
        """Launches the Category Editor and handles language re-translation if changed."""
        old_language = config.lang
        dlg = CategoryDialog(self)
        dlg.apply_language_add_cat(config.lang)
        if dlg.exec() == QDialog.Accepted and config.lang != old_language:
            log(f"System language changed to: {config.lang}", log_level=1, context=self.ctx)
            self.lang_manager.apply_language(config.lang)
            self.retrans()


    def show_whatsnew_dialog(self):
        """Displays the application changelog and release notes."""
        dlg = WhatsNewDialog(self)
        dlg.apply_language_whatsnew(config.lang)
        dlg.exec()


    def show_about_dialog(self):
        """Displays application branding, versioning, and license information."""
        dlg = AboutDialog(self)
        dlg.set_app_info(name=config.APP_NAME, version=config.APP_VERSION, url=config.APP_URL)
        dlg.set_creator(creator=config.APP_CREATOR)
        dlg.set_license(license_text="GPL v3 License")
        dlg.set_description(config.APP_DESCRIPTION)
        dlg.apply_language_about(config.lang)
        dlg.exec()


    def ask_for_sched_time(self, msg=''):
        """Prompts the user for a specific time to initiate a scheduled task."""
        dialog = ScheduleDialog(msg)
        if dialog.exec() == QDialog.Accepted:
            return dialog.response 
        return None


    def show_settings_dialog(self):
        """Launches the global application preferences dialog."""
        SettingsDialog(self).exec()


    def open_help(self):
        """Opens the integrated documentation and tutorial window."""
        if not hasattr(self, "_help_window"):
            self._help_window = HelpWindow(self)
        self._help_window.show()
        self._help_window.raise_()


    def show_subtitle_failed_dialog(self, payload: dict):
        """Display the SubtitleFailedDialog for a failed subtitle download."""
        dlg = SubtitleFailedDialog(payload, parent=self)
        dlg.exec()


    def show_marketplace(self):
        from ui.marketplace_dialog import MarketplaceDialog
        dlg = MarketplaceDialog(
            parent=self,
            plugins_dir=str(config.DATA_ROOT / "plugins")
        )
        dlg.apply_language_market(config.lang)
        dlg.setStyleSheet(get_stylesheet(self.current_theme))
        dlg.exec()


    def open_completed_file(self, file_path):
        """
        Asynchronously opens a finalized file using the OS default handler.
        
        Spawns a FileOpenThread to ensure that slow disk I/O or hung system 
        processes do not freeze the main UI. 
        """
        self.file_open_thread = FileOpenThread(file_path, self)
        self.file_open_thread.critical_signal.connect(show_critical)
        self.file_open_thread.start()
        
        # Tracking the thread ensures it is cleaned up on application exit
        self.background_threads.append(self.file_open_thread)


    def populate_open_menu(self):
        """
        Dynamically builds the 'Recent Downloads' list within the file menu.
        
        Filters for items with a 'completed' status that still exist on disk.
        Utilizes MarqueeLabel for long filenames and QWidgetAction to embed 
        a scrollable list directly into the QMenu.
        """
        self.ui.open_file_menu.clear()
    
        # Verify file existence on disk to avoid 'ghost' entries
        completed_dl = [
            d for d in self.d_list 
            if d.status == "completed" and os.path.exists(d.target_file)
        ]
    
        if not completed_dl:
            no_files = QAction(self.tr("No completed downloads"), self)
            no_files.setEnabled(False)
            self.ui.open_file_menu.addAction(no_files)
            return
    
        # High-density scrollable list widget for the menu
        list_widget = QListWidget()
        list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        list_widget.setFixedSize(300, 200)
    
        for d in completed_dl:
            item = QListWidgetItem()
            # Use custom scrolling label for long video/file names
            label = MarqueeLabel(d.name)
            label.setToolTip(f"Size: {size_format(d.total_size)}")
    
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.addWidget(label)
            layout.setContentsMargins(5, 2, 5, 2)
            container.setLayout(layout)
    
            list_widget.addItem(item)
            list_widget.setItemWidget(item, container)
            item.setData(Qt.UserRole, d.target_file)
    
        def on_item_clicked(item):
            file_path = item.data(Qt.UserRole)
            self.open_completed_file(file_path)
    
        list_widget.itemClicked.connect(on_item_clicked)
    
        # Encapsulate the list into a menu action
        action_widget = QWidgetAction(self.ui.open_file_menu)
        action_widget.setDefaultWidget(list_widget)
        self.ui.open_file_menu.addAction(action_widget)


    def exit_app(self):
        """Terminates the application and triggers clean shutdown logic."""
        log("Initiating application shutdown sequence", log_level=1, context=self.ctx)
        QtWidgets.QApplication.quit()


    def install_browser_extension(self, browser_name):
        """
        Redirects the user to the official web store for browser integration.
        
        Validates the browser name against the EXTENSION_URLS mapping and 
        launches the system browser to the specific addon page.
        """
        url = self.EXTENSION_URLS.get(browser_name)
        if url:
            log(f"Redirecting user to {browser_name} extension store", 
                log_level=1, context=self.ctx)
            show_information(
                self, self.tr("Opening Browser"), 
                self.tr("Redirecting you to install %1 the extension.").replace("%1", browser_name), 
                self.tr("Follow the instructions in the web store.")
            )
            QDesktopServices.openUrl(QUrl(url))
        else:
            log(f"Extension URL requested for unsupported browser: {browser_name}", 
                log_level=3, context=self.ctx)
            show_warning(self, "Extension Error", self.tr("No URL available for %1.").replace("%1", {browser_name}))


    def open_github_issues(self):
        """Opens the GitHub issue tracker to facilitate user feedback and bug reporting."""
        url = 'https://github.com/Annor-Gyimah/OmniPull/issues'
        log("Redirecting user to GitHub Issue Tracker", log_level=1, context=self.ctx)
        QDesktopServices.openUrl(QUrl(url))
        show_information(
            self, self.tr("Community Feedback"), 
            self.tr("Redirecting to GitHub. We appreciate your bug reports and feature requests."), 
            self.tr("Follow the instructions on the issues page.")
        )


    def get_system_theme(self) -> str:
        """
        Detects the host operating system's color scheme preference.
        
        Queries the macOS 'AppleInterfaceStyle' via shell, the Windows Registry 
        'AppsUseLightTheme' key, or falls back to Qt's QPalette luminance 
        detection on Linux/Unix systems.
        """
        try:
            if platform.system() == "Darwin":
                import subprocess
                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True, text=True
                )
                return "dark" if result.returncode == 0 else "light"
    
            elif platform.system() == "Windows":
                try:
                    import winreg
                    registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                    path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                    key = winreg.OpenKey(registry, path)
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    winreg.CloseKey(key)
                    return "light" if value == 1 else "dark"
                except Exception:
                    pass
    
            # Fallback for Linux or failed registry/shell queries
            try:
                from PySide6.QtGui import QPalette
                palette = QApplication.instance().palette()
                bg_color = palette.color(QPalette.Window)
                return "dark" if bg_color.lightness() < 128 else "light"
            except Exception:
                pass
    
        except Exception as e:
            log(f"System theme detection failed: {e}", log_level=3, context=self.ctx)
    
        return "light"


    def set_theme(self, theme: str):
        """
        Applies a visual theme ('system', 'dark', or 'light') to the application.
        
        If 'system' is selected, it triggers hardware-level detection to match 
        the OS. Updates the global configuration to ensure the preference 
        persists across sessions.
        """
        theme = theme.lower()
        original_choice = theme
    
        if theme == "system":
            detected = self.get_system_theme()
            log(f"Auto-aligning UI with system theme: {detected}", 
                log_level=2, context=self.ctx)
            theme = detected
    
        if theme.startswith("dark"):
            self.current_theme = "dark"
            self.ui.action_theme_dark.setChecked(True)
            self.ui.action_theme_light.setChecked(False)
        else:
            self.current_theme = "light"
            self.ui.action_theme_light.setChecked(True)
            self.ui.action_theme_dark.setChecked(False)
    
        config.current_theme = original_choice
        self._apply_styles()


    def _apply_styles(self):
        """
        Injects QSS stylesheets into the application instance.
        
        Attempts to set the stylesheet globally on the QApplication instance 
        so that orphaned dialogs and popups inherit the theme correctly.
        """
        qss = get_stylesheet(self.current_theme)
        
        try:
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss)
                log(f"Global stylesheet applied: {self.current_theme.upper()}", 
                    log_level=2, context=self.ctx)
        except Exception as e:
            # Fallback to local window styling if global injection fails
            try:
                # self.setStyleSheet(qss)
                self.ui_add_download.setStyleSheet(qss)
            except Exception:
                log(f"Critical failure applying UI styles: {e}", 
                    log_level=3, context=self.ctx)


    def toggle_details_panel(self):
        """Toggles the visibility of the advanced metadata panel in the Add Download window."""
        is_visible = self.ui_add_download.details_panel.isVisible()
        self.ui_add_download.details_panel.setVisible(not is_visible)


    def on_selection_queue(self):
        # It's safer to check the index or the text
        current_text = self.ui_add_download.queue_combo.currentText()
        btn = self.ui_add_download.download_btn
        
        if current_text != self.tr("None") and current_text != "None": 
            btn.setText(self.tr("Add to Queue"))
            
        else:
            btn.setText(self.tr("Start Download"))


    def queue_combo(self):
        """
        Synchronizes the Add Download dialog's queue selection box.
        
        Refreshes the available options from the queues to ensure 
        the user can select from the most recent list of defined queues.
        """
        self.queues = self.settings_manager.queues
        
        # High-frequency UI sync; no log needed unless error occurs
        if not self.queues:
            return
    
        self.ui_add_download.queue_combo.clear()
        self.ui_add_download.queue_combo.addItem("None")
        
        for queue in self.queues:
            name = queue.get("name")
            if name:
                self.ui_add_download.queue_combo.addItem(name)


    def register_queue_background_thread(self, thread: QThread):
        """
        Enrolls a queue-specific worker thread into the lifecycle tracker.
        
        Ensures that background tasks are monitored and automatically 
        removed from the tracking list upon completion to prevent memory leaks.
        """
        self.background_threads.append(thread)
        log(f"Registering background worker thread: {thread.objectName() or 'Queue-Worker'}", 
            log_level=2, context=self.ctx)
            
        thread.finished.connect(lambda: self.background_threads.remove(thread))


    def category_list(self, language="English"):
        """
        Refreshes the sidebar category list with localized and custom entries.
        
        Loads default categories from CATEGORY_TRANSLATIONS and appends 
        user-defined categories from the settings manager. Uses Qt.UserRole 
        to store the original 'key' for consistent filtering even when 
        the display text is translated.
        """
        self._category_map = {}
        try:
            self.categories = self.settings_manager.load_categories()
        except Exception as e:
            log(f"Failed to retrieve user categories: {e}", 
                log_level=2, context=self.ctx)
            self.categories = []
    
        self.ui.category_list.clear()
        default_categories = list(CATEGORY_TRANSLATIONS.keys())
    
        # 1. Add localized system categories
        for category in default_categories:
            item = QtWidgets.QListWidgetItem()
            # UserRole stores the non-translated ID for internal logic
            item.setData(Qt.UserRole, category)
            
            translated_text = CATEGORY_TRANSLATIONS.get(category, {}).get(language, category)
            item.setText(translated_text)
            self.ui.category_list.addItem(item)
    
        # 2. Add custom user-defined categories
        for cat in self.categories:
            name = cat.get("name")
            if name and name not in default_categories:
                item = QtWidgets.QListWidgetItem(name)
                item.setData(Qt.UserRole, name)
                self.ui.category_list.addItem(item)
    
        # Default selection to 'All' or first available
        if self.ui.category_list.count() > 0:
            self.ui.category_list.setCurrentRow(0)


    def update_category_combo(self):
        """
        Synchronizes the Add Download dialog's category selection box.
        
        Combines the standard industrial classifications with active 
        user categories to ensure the 'Save To' metadata is accurate 
        during task initiation.
        """
        self.categories = self.settings_manager.categories
        self.ui_add_download.category_combo.clear()
        
        # Standard system-level classification keys
        default_categories = ["General", "Compressed", "Documents", "Music", "Video", "Programs"]
        
        custom_names = [c['name'] for c in self.categories if 'name' in c]
        self.ui_add_download.category_combo.addItems(default_categories + custom_names)


    def update_category_list(self):
        """
        Trigger-point for refreshing the category UI.
        
        Typically called after a settings change or language switch 
        to force a redraw of the category sidebar.
        """
        log(f"Refreshing category taxonomy (Language: {config.lang})", 
            log_level=2, context=self.ctx)
        self.category_list(language=config.lang)


    def apply_language_global(self, language):
        """
        Apply language globally and refresh given windows.
        
        windows: list of window instances
        """
        self.lang_manager.apply_language(language)
    
        for widget in QCoreApplication.instance().allWidgets():
            if hasattr(widget, "retrans"):
                widget.retrans()


    def retrans(self):
        """
        Refreshes all UI text elements using the currently installed translator.
        
        This method re-assigns text to all menus, actions, buttons, and labels 
        in the main window. It must be called whenever the translator changes.
        """
        # ── Menus & Top-Level Actions ────────────────────────────────────────
        self.ui.file_menu.setTitle(self.tr('&File'))
        self.ui.exit_action.setText(self.tr('&Exit'))
        self.ui.open_file_menu.setTitle(self.tr('Open'))
        self.ui.add_action.setText(self.tr("Add new download"))
        
        self.ui.downloads_menu.setTitle(self.tr('&Downloads'))
        # Using specific indices for menu stability
        actions = self.ui.downloads_menu.actions()
        if len(actions) >= 3:
            actions[0].setText(self.tr('Resume All'))
            actions[1].setText(self.tr('Stop All'))
            actions[2].setText(self.tr('Delete All'))
            
        self.ui.view_menu.setTitle(self.tr('&View'))
        self.ui.theme_menu.setTitle(self.tr('Theme'))
        self.ui.action_theme_dark.setText(self.tr('Dark'))
        self.ui.action_theme_light.setText(self.tr('Light'))
        
        self.ui.tools_menu.setTitle(self.tr("&Tools"))
        self.ui.scheduler_action.setText(self.tr("Scheduler"))
        self.ui.category_action.setText(self.tr("Categories"))
        self.ui.queue_action.setText(self.tr("Queues"))
        self.ui.settings_action.setText(self.tr('Settings'))
        self.ui.install_deno_action.setText(self.tr('Install deno'))
        self.ui.install_ffmpeg_action.setText(self.tr('Install ffmpeg'))
        self.ui.install_ytdlp_action.setText(self.tr('Install yt-dlp'))
        self.ui.marketplace_action.setText(self.tr('Marketplace'))
        
        self.ui.browser_ext_menu.setTitle(self.tr('Browser Extension'))
        
        self.ui.help_menu.setTitle(self.tr('&Help'))
        h_actions = self.ui.help_menu.actions()
        if len(h_actions) >= 6:
            h_actions[1].setText(self.tr('About'))
            h_actions[2].setText(self.tr('Help'))
            h_actions[3].setText(self.tr('Check for Updates'))
            h_actions[4].setText(self.tr("Report Issues"))
            h_actions[5].setText(self.tr('WhatsNew'))
    
        # ── Dashboard & Toolbars ─────────────────────────────────────────────
        self.ui.btn_add.setText(self.tr("Add"))
        self.ui.btn_resume.setText(self.tr("Resume"))
        self.ui.btn_pause.setText(self.tr("Pause"))
        self.ui.btn_stop_all.setText(self.tr("Stop All"))
        self.ui.btn_delete_all.setText(self.tr("Delete All"))
        self.ui.btn_scheduler.setText(self.tr("Scheduler"))
        self.ui.btn_refresh.setText(self.tr("Refresh"))
        self.ui.btn_terminal.setText(self.tr("Terminal"))
        self.ui.btn_resume_all.setText(self.tr("Resume All"))
        self.ui.btn_settings.setText(self.tr("Settings"))
    
        translated_headers = [
            self.tr("ID"),
            self.tr("Name"),
            self.tr("Progress"),
            self.tr("Speed"),
            self.tr("ETA"),
            self.tr("Done"),
            self.tr("Size"),
            self.tr("Status"),
            self.tr("I"),                
            self.tr("Last Try Date")
        ]
    
        # Apply the new headers to the table
        self.ui.table.setHorizontalHeaderLabels(translated_headers)
    
        # ── Static Labels & Tooltips ────────────────────────────────────────
        self.ui.title_label.setText(self.tr("Downloads"))
        self.ui.sort_by.setText(self.tr("Sort by:"))
        self.ui.t_label.setText(self.tr("Terminal"))
        self.ui.log_clear_btn.setText(self.tr("Clear"))
        self.ui.log_level_label.setText(self.tr("Log Level:"))
        
        self.ui.lbl_http_status.setToolTip(self.tr("Last HTTP response status"))
        self.ui.lbl_speed.setToolTip(self.tr("Current total download speed"))
        self.ui.no_plugins_label.setText(self.tr("No plugins installed. Install via marketplace."))
        self.ui.dock.setWindowTitle(self.tr("Categories"))
        self.ui.search_label.setText(self.tr("   Search: "))
        if self._grace_expired():
            self.ui.banner_message.setText(UPDATE_AVAILABLE_TRANSLATIONS[f"aggressive"][config.lang]) 
            self.ui.banner_update_btn.setText(self.tr('Update Now'))
        else:
            self.ui.banner_message.setText(UPDATE_AVAILABLE_TRANSLATIONS[f"normal"][config.lang]) 
    
            self.ui.banner_update_btn.setText(self.tr('Update Now'))
            self.ui.banner_later_btn.setText(self.tr('Later'))
        self.ui.terminal_input.setPlaceholderText(self.tr(
            "Enter command here... You can start with helpful commands like 'help' or 'yt-dlp --help'."
        ))
        self.ui.filter_edit.setPlaceholderText(self.tr("Search downloads..."))
    
        # ── Context Menu Actions ─────────────────────────────────────────────
        self.action_open_file.setText(self.tr("Open File"))
        self.action_open_file_with.setText(self.tr("Open File With"))
        self.action_open_location.setText(self.tr("Open File Location"))
        self.action_watch_downloading.setText(self.tr("Watch while downloading"))
        self.action_schedule_download.setText(self.tr("Schedule download"))
        self.action_cancel_schedule.setText(self.tr("Cancel schedule!"))
        self.action_delete_file_from_table.setText(self.tr("Delete"))
        self.action_remerge.setText(self.tr("Re-merge audio/video"))
        self.action_file_properties.setText(self.tr("File Properties"))
        self.action_add_to_queue.setText(self.tr("Add to Queue"))
        self.action_remove_from_queue.setText(self.tr("Remove from Queue"))
        self.action_file_checksum.setText(self.tr("File CheckSum!"))
        self.action_pop_file_from_table.setText(self.tr("Delete from Table"))
        
    
        # ── Dynamic Category List ────────────────────────────────────────────
        for i in range(self.ui.category_list.count()):
            item = self.ui.category_list.item(i)
            if item:
                english_key = item.data(Qt.UserRole)
                translated_text = CATEGORY_TRANSLATIONS.get(english_key, {}).get(config.lang, english_key)
                item.setText(translated_text)


    def quit_app(self):
        """
        Finalizes the application session and terminates the process.
        
        Ensures the system tray icon is removed before the Qt event 
        loop stops to prevent ghost icons in the system notification area.
        """
        if hasattr(self, 'tray_manager'):
            self.tray_manager.hide()
        
        log("Exiting application event loop.", log_level=1, context=self.ctx)
        QApplication.quit()


    def _debug_threads(self, tag):
        """
        Diagnostic helper to audit the status of active background threads.
        
        Logs the running state of the primary table thread and all registered 
        background workers for troubleshooting shutdown hangs.
        """
        try:
            is_running = getattr(self, "table_thread", None) and self.table_thread.isRunning()
            log(f"THREAD-AUDIT [{tag}] Table thread active: {is_running}", context=self.ctx)
        except Exception:
            log(f"THREAD-AUDIT [{tag}] Table thread state unknown (deleted)", context=self.ctx)
    
        if hasattr(self, "background_threads"):
            for idx, th in enumerate(list(self.background_threads)):
                try:
                    name = type(th).__name__
                    log(f"THREAD-AUDIT [{tag}] Worker[{idx}] {name} active: {th.isRunning()}", 
                        context=self.ctx)
                except Exception as e:
                    log(f"THREAD-AUDIT [{tag}] Worker[{idx}] metadata unreachable: {e}", 
                        context=self.ctx)


    def force_exit_for_update(self):
        """
        Triggers an immediate, non-interceptable shutdown for update application.
        
        Bypasses 'minimize to tray' settings and attempts a rapid cleanup 
        of threads before forcing a process exit via the OS.
        """
        log("Initiating emergency shutdown for software update...", 
            log_level=1, context=self.ctx)
    
        config.force_exit_for_update = True
        config.hide_app = False
    
        if hasattr(self, "tray_manager"):
            self.tray_manager.hide()
    
        # Best-effort rapid thread termination
        try:
            for t in getattr(self, "background_threads", []):
                if t and t.isRunning():
                    if hasattr(t, "stop"): t.stop()
                    t.requestInterruption()
                    t.quit()
                    t.wait(1000)
        except Exception:
            pass
    
        def _final_kill():
            log("Executing terminal process exit.", log_level=1, context=self.ctx)
            import os
            os._exit(0)
    
        QTimer.singleShot(100, _final_kill)


    def closeEvent(self, event):
        """
        Handles the window close request (X button or Alt+F4).
        
        Intercepts the event to minimize to tray if configured, otherwise 
        orchestrates a clean shutdown of all background threads and 
        external managers (aria2c).
        """
        if event.spontaneous() and config.hide_app:
            # User clicked X, but 'Hide to Tray' is enabled
            self.tray_manager.handle_window_close()
            event.ignore()
            return
    
        self._debug_threads("pre-shutdown")
        
        try:
            config.terminate = True  # Signal all workers to stop
            log("System shutdown initiated. Finalizing background tasks...", 
                log_level=1, context=self.ctx)
    
            # 1. Stop Table/UI Thread
            t = getattr(self, "table_thread", None)
            if t and t.isRunning():
                if hasattr(self, "worker") and hasattr(self.worker, "requestInterruption"):
                    try: self.worker.requestInterruption()
                    except Exception: pass
                t.quit()
                t.wait(3000)
    
            
            # 2. Stop Log Recorder (Explicit flush)
            log_t = getattr(self, "log_recorder_thread", None)
            if log_t and log_t.isRunning():
                if hasattr(log_t, "stop"): log_t.stop()
                log_t.requestInterruption()
                log_t.wait(5000)  # longer wait
                
                # Force close file handle if thread hung
                if log_t.isRunning():
                    try:
                        if hasattr(log_t, 'file') and log_t.file:
                            log_t.file.close()
                    except:
                        pass
    
            # 3. Stop Browser Monitor
            queue_monitor = getattr(self, "browser_queue_monitor", None)
            if queue_monitor and queue_monitor.isRunning():
                log("Deactivating browser integration monitor...", context=self.ctx)
                if hasattr(queue_monitor, "stop"): queue_monitor.stop()
                queue_monitor.requestInterruption()
                queue_monitor.wait(3000)
    
            # 4. Final Cleanup of all registered workers
            if hasattr(self, "background_threads"):
                for th in list(self.background_threads):
                    try:
                        if th and th.isRunning():
                            if hasattr(th, "stop"): th.stop()
                            th.requestInterruption()
                            th.quit()
                            th.wait(2000)
                    except Exception:
                        pass
            
            if hasattr(self, "plugin_mgr"):
                try:
                    self.plugin_mgr.shutdown_all()
                except Exception as e:
                    log(f"Plugin shutdown error: {e}", log_level=2, context=self.ctx)
    
            # 5. External Process Management (aria2c)
            if config.aria2_verified:
                log("Finalizing aria2c state and purging temporary session data", 
                    log_level=1, context=self.ctx)
                aria2c_manager.cleanup_orphaned_paused_downloads()
                aria2c_manager.shutdown_freeze_and_save(purge=True)
                aria2c_manager._terminate_existing_processes()
    
            self.quit_app()
            super().closeEvent(event)
                    
        except Exception as e:
            log(f"Error during shutdown sequence: {e}. Forcing closure.", 
                log_level=3, context=self.ctx)
            super().closeEvent(event)
        finally:
            self._debug_threads("post-shutdown")


    def changeEvent(self, event):
        """Monitors for window state changes, such as minimization."""
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized() and config.hide_app:
                # Redirect minimize action to tray
                QTimer.singleShot(0, self._hide_to_tray)
                event.ignore()
                return
        super().changeEvent(event)


    def _hide_to_tray(self):
        """Transitions the UI visibility to the system tray."""
        self.hide()
        if config.hide_app:
            self.tray_manager.show_running_message()


    def clear_log(self):
        """Wipes the embedded terminal output."""
        self.ui.terminal_output.clear()


    def set_log(self):
        """Updates the application logging verbosity threshold."""
        config.log_level = int(self.ui.log_level_combo.currentText())
        log(f"System log verbosity updated to level: {config.log_level}", 
            log_level=1, context=self.ctx)
        self.settings_manager.save_settings()


    def open_folder_dialog(self):
        """Open a dialog to select a folder and update the line edit."""
        # Open a folder selection dialog
        folder_path = QFileDialog.getExistingDirectory(self, "Select Download Folder")
    
        if folder_path:
            self.ui_add_download.save_to_edit.setText(folder_path)
            config.download_folder = os.path.abspath(folder_path)
        
        self.ui_add_download.activateWindow()
        self.ui_add_download.raise_()


    def on_filename_changed(self, text: str) -> str:
        """Handle manual changes to the filename line edit."""
    
        # Only update the download item if the change was made manually
        if not self.filename_set_by_program:
            self.d.name = text


    def on_clipboard_change(self):
        """
        Monitors the system clipboard for actionable download links.
        
        If 'Monitor Clipboard' is enabled, it validates incoming strings as 
        potential URLs (checking for http/https prefixes and whitespace). 
        Also includes a simple 'alive' handshake for inter-process communication.
        """
        try:
            new_data = self.clipboard.text()
    
            # IPC Handshake check
            if new_data == 'any one there?':
                self.clipboard.setText('yes')
                self.show()
                self.raise_()
                return
    
            # Automated URL Capture
            if config.monitor_clipboard and new_data != self.old_clipboard_data:
                if new_data.startswith('http') and ' ' not in new_data:
                    log(f"New URL detected in clipboard: {new_data[:50]}...", 
                        log_level=1, context="CLIPBOARD")
                    config.main_window_q.put(('url', new_data))                    
                self.old_clipboard_data = new_data
    
        except (AttributeError, TypeError) as e:
            log(f"Clipboard synchronization failed: {e}", 
                log_level=2, context="CLIPBOARD")


    def on_browser_download_detected(self, url: str, metadata: dict):
        """
        Handles download interception requests from the browser extension.
        
        When a browser download is captured, this method populates the 
        AddDownload dialog with 'trusted' metadata (filename, referrer, size) 
        provided by the browser, ensuring high accuracy for direct downloads.
        
        CRITICAL: URL processing is deferred to a background thread to prevent
        GUI freezing when processing heavy URLs (e.g., YouTube links).
        """
        try:
            log(f"Intercepted browser download request: {url[:60]}...", 
                log_level=1, context="BROWSER-EXT")
            
            referrer = metadata.get('referrer')
            browser_size = metadata.get('filesize')
            browser_filename = metadata.get('filename')
    
            # User Notification via Tray
            filename = browser_filename or 'Unknown file'
            self.tray_manager.show_browser_download_intercepted(filename)
    
            # UI Transition: Show only the entry dialog
            self.show_add_dialog_only()
    
            if hasattr(self.ui_add_download, 'url_edit'):
                self.reset()
    
                # Block signals to prevent redundant extraction during text insertion
                self.ui_add_download.url_edit.blockSignals(True)
                self.ui_add_download.url_edit.setText(url)
                self.ui_add_download.url_edit.blockSignals(False)
    
                # ── CRITICAL FIX: Defer URL processing to background thread ──
                # This prevents the dialog from freezing when processing heavy URLs
                def process_url_background():
                    try:
                        self.url_text_change(
                            referrer=referrer, 
                            trusted_size=browser_size, 
                            trusted_name=browser_filename
                        )
                    except Exception as e:
                        log(f"Background URL processing failed: {e}", log_level=2, context="BROWSER-EXT")
    
                # Use QTimer to defer processing to main loop (allows UI to render first)
                QTimer.singleShot(100, lambda: executor.submit(process_url_background))
                
            else:
                log("Critical UI Error: url_edit widget missing from AddDownloadWindow", 
                    log_level=3, context="BROWSER-EXT")
    
        except Exception as e:
            log(f"Browser download interception failed: {e}", 
                log_level=3, context="BROWSER-EXT")


    def update_http_status(self, code: int):
        """
        Renders a color-coded HTML status indicator for network responses.
        
        Green: Success (2xx) | Orange: Redirect (3xx) | Red: Error (4xx/5xx)
        """
        if code == 0:
            self.ui.lbl_http_status.setText('<span style="color:gray;">—</span>')
            return
    
        status_map = {
            2: ("green", "OK"),
            3: ("orange", "Redirect"),
            4: ("red", "Client Error"),
            5: ("darkred", "Server Error")
        }
        
        color, text = status_map.get(code // 100, ("gray", "Unknown"))
        self.ui.lbl_http_status.setText(f'<span style="color:{color};">{code} {text}</span>')


    def ensure_dependency(
        self,
        *,
        name: str,                                 # e.g. "FFmpeg" or "Deno"
        check_func: Callable[[], bool],            # e.g. check_ffmpeg, check_deno
        download_func: Callable[[str], None],      # e.g. download_ffmpeg(dest), download_deno(dest)
        recommended_dir: Optional[str] = None,     # e.g. config.global_sett_folder
        local_dir: Optional[str] = None,           # e.g. config.current_directory
        missing_title: Optional[str] = None,       # dialog title on Windows
        missing_label: Optional[str] = None,       # main label on Windows
        non_windows_msg: Optional[str] = None,     # messagebox text on non-Windows
    ) -> bool:
        """
        Ensure `name` is available. If not, on Windows show a themed download dialog;
        on other OSes show a guidance MessageBox. Returns True if available/installed, else False.
        """
    
        # Already present?
        try:
            if check_func():
                return True
        except Exception:
            pass
    
        # Defaults for text
        title = missing_title or self.tr("%1 is missing").replace("%1", name)
        label_text = missing_label or self.tr("%1 is missing and needs to be downloaded:").replace("%1", name)
        
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
    
        layout = QVBoxLayout(dialog)
    
        label = QLabel(label_text)
        layout.addWidget(label)
    
        # Destination choices (fall back to current dir if recommended/local not provided)
        rec_dir = recommended_dir or getattr(config, 'global_sett_folder', getattr(config, 'current_directory', '.'))
        loc_dir = local_dir or getattr(config, 'current_directory', '.')
    
        recommended = self.tr("Recommended:")
        local_fd = self.tr("Local folder:")
        recommended_radio = QRadioButton(f"{recommended} {rec_dir}")
        recommended_radio.setChecked(True)
        local_radio = QRadioButton(f"{local_fd} {loc_dir}")
    
        radio_group = QButtonGroup(dialog)
        radio_group.addButton(recommended_radio)
        radio_group.addButton(local_radio)
    
        radio_layout = QVBoxLayout()
        radio_layout.addWidget(recommended_radio)
        radio_layout.addWidget(local_radio)
        layout.addLayout(radio_layout)
    
        # Buttons
        button_layout = QHBoxLayout()
        download_button = QPushButton(self.tr('Download'))
        cancel_button = QPushButton(self.tr('Cancel'))
        button_layout.addWidget(download_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
    
        def on_download():
            dest = rec_dir if recommended_radio.isChecked() else loc_dir
            try:
                download_func(dest)
            finally:
                dialog.accept()
    
        def on_cancel():
            dialog.reject()
    
        download_button.clicked.connect(on_download)
        cancel_button.clicked.connect(on_cancel)
    
        ok = dialog.exec()
        if not ok:
            return False
    
        # Re-check after attempted install
        try:
            return bool(check_func())
        except Exception:
            return False


    def change_page(self, idx: int):
        """Transitions the main UI stack to the specified page index."""
        self.ui.stack.setCurrentIndex(idx)


    def on_startup(self):
        """
        Manages the 'Launch on Startup' integration with the OS.
        
        If checked, it invokes the platform-specific logic to add OmniPull 
        to the startup registry/folder. If unchecked, it cleans up 
        any existing startup entries.
        """
        ctx = "APP-LIFECYCLE"
        checked = self.ui_settings.on_startup_chk.isChecked()
        
        if checked:
            if not (checkStartUp()): 
                log("Enabling OS startup integration.", log_level=1, context=ctx)
                addStartUp()
        else:
            if checkStartUp():
                log("Removing OS startup integration.", log_level=1, context=ctx)
                removeStartUp()
