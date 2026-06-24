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


class UpdateControllerMixin:
    """Mixin providing UpdateController methods for DownloadManagerWindow."""

    def install_ffmpeg(self, force=False):
        """
        Triggered by the menu action. Starts the automated download 
        and installation of deno into the app's roaming folder.
        """
        try:
    
            # Check if it already exists
            if not force and check_dependency_installed('ffmpeg'):
                log("ffmpeg is already installed. Skipping download.", log_level=1)
                
                # Inform the user via a non-intrusive message
                self.tray_manager.show_message(
                    self.tr("Dependency Ready"),
                    self.tr("ffmpeg is already installed and up to date.")
                )
                return
            
            # config.global_sett_folder is dynamic: 
            # C:\Users\{User}\AppData\Roaming\.OmniPull
            if config.IS_WIN:
                dest_folder = config.global_sett_folder
            else:
                dest_folder = config.CONFIG_BIN
            
            log(f"Installing ffmpeg to: {dest_folder}", log_level=1, context="INSTALLER")
            
            # Call the dependency downloader
            download_dependency(name='ffmpeg', destination=dest_folder)
            
            # Notify user 
            self.tray_manager.show_message(
                self.tr("Installation Started"),
                self.tr("Downloading the latest ffmpeg for your system...")
            )
        except Exception as e:
            log(f"Installation trigger failed: {e}", log_level=3)
            show_critical(self, self.tr("Install Error"), str(e))


    def install_deno(self, force=False):
        """
        Triggered by the menu action. Starts the automated download 
        and installation of deno into the app's roaming folder.
        """
        try:
    
            # Check if it already exists
            if not force and check_dependency_installed('deno'):
                log("deno is already installed. Skipping download.", log_level=1)
                
                # Inform the user via a non-intrusive message
                self.tray_manager.show_message(
                    self.tr("Dependency Ready"),
                    self.tr("deno is already installed and up to date.")
                )
                return
            
            # Resolves to C:\Users\{User}\AppData\Roaming\.OmniPull on Windows
            if config.IS_WIN:
                dest_folder = config.global_sett_folder
            else:
                dest_folder = config.CONFIG_BIN
            
            log(f"Installing Deno to: {dest_folder}", log_level=1, context="INSTALLER")
            
            # Initiates the dependency download for Deno
            download_dependency(name='deno', destination=dest_folder)
            
            # Update the message to accurately reflect the Deno installation
            self.tray_manager.show_message(
                self.tr("Installation Started"),
                self.tr("Downloading the latest Deno for your system...")
            )
        except Exception as e:
            log(f"Deno installation trigger failed: {e}", log_level=3)
            show_critical(self, self.tr("Install Error"), str(e))


    def install_ytdlp(self, force=False):
        """
        Triggered by the menu action. Starts the automated download 
        and installation of yt-dlp into the app's roaming folder.
        """
        try:
            
    
            # Check if it already exists
            if not force and check_dependency_installed('yt-dlp'):
                log("yt-dlp is already installed. Skipping download.", log_level=1)
                
                # Inform the user via a non-intrusive message
                self.tray_manager.show_message(
                    self.tr("Dependency Ready"),
                    self.tr("yt-dlp is already installed and up to date.")
                )
                return
            
            # config.global_sett_folder is dynamic: 
            # C:\Users\{User}\AppData\Roaming\.OmniPull
            if config.IS_WIN:
                dest_folder = config.global_sett_folder
            else:
                dest_folder = config.CONFIG_BIN
            
            log(f"Installing yt-dlp to: {dest_folder}", log_level=1, context="INSTALLER")
            
            # Call the dependency downloader
            download_dependency(name='yt-dlp', destination=dest_folder)
            
            # Notify user (Optional)
            self.tray_manager.show_message(
                self.tr("Installation Started"),
                self.tr("Downloading the latest yt-dlp for your system...")
            )
        except Exception as e:
            log(f"Installation trigger failed: {e}", log_level=3)
            show_critical(self, self.tr("Install Error"), str(e))


    def _handle_version_status(self):
        latest = getattr(config, "APP_LATEST_VERSION", None)
        current = getattr(config, "APP_VERSION", None)
    
        cmp = compare_versions_2(latest, current)
    
        if cmp == 0:
            # up to date
            self.ui.lbl_version.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-weight: bold;
                    padding: 5px 10px;
                    border-radius: 10px;
                    background: rgba(76, 175, 80, 0.1);
                }
            """)
            self.ui.lbl_version.setToolTip('No new updates')
        elif cmp == 1:
            # newer available
            self.ui.lbl_version.setStyleSheet("""
                QLabel {
                    color: #F44336;
                    padding: 6px 16px;
                    font-weight: bold;
                    border-radius: 10px;
                    background: rgba(244, 67, 54, 0.1);  
                }
            """)
            self.ui.lbl_version.setToolTip(f'New version available: {latest}')
        elif cmp == -1:
            # current > latest (dev build ahead)
            self.ui.lbl_version.setStyleSheet("""
                QLabel {
                    color: #2196F3;
                    padding: 6px 16px;
                    font-weight: bold;
                    border-radius: 10px;
                    background: rgba(33, 150, 243, 0.1);
                }
            """)
            self.ui.lbl_version.setToolTip(f'Running a newer/dev build ({current})')
        else:
            # Unknown (None / unparsable)
            self.ui.lbl_version.setStyleSheet("""
                QLabel {
                    color: #9E9E9E;
                    font-weight: bold;
                    padding: 5px 10px;
                    border-radius: 10px;
                    background: rgba(158, 158, 158, 0.1);
                }
            """)
            self.ui.lbl_version.setToolTip('Unable to determine latest version')


    def check_update_frequency(self):
        """Updates the global config for how often the app polls the server for updates."""
        try:
            selected = int(self.ui_settings.update_interval_combo.currentText())
            config.update_frequency = selected
        except (ValueError, TypeError):
            pass


    def update_available(self):
        """
        Polls the remote server for the latest changelog and version data.
        Shows an inline banner instead of an immediate update dialog.
        """
        ctx = "UPDATE-ENGINE"
        change_cursor('busy')
    
        current_version = config.APP_VERSION
        info = get_changelog()
    
        if info:
            latest_version, version_description = info
            newer_version = compare_versions(current_version, latest_version)
    
            if not newer_version or newer_version == current_version:
                self.new_version_available = False
                log(f"Version check: App is up-to-date (Server: {latest_version})",
                    log_level=1, context=ctx)
                # Clear dismissal state — user is on the latest version (they updated)
                config.update_dismissed_timestamp = None
                config.APP_LATEST_VERSION = latest_version
                # Hide banner on the main thread
                QTimer.singleShot(0, lambda: self.ui.update_banner.setVisible(False))
            else:
                log(f"Update detected: {current_version} -> {latest_version}",
                    log_level=1, context=ctx)
                self.new_version_available = True
                config.APP_LATEST_VERSION = latest_version
                self.new_version_description = version_description
                config.update_dismissed_timestamp = datetime.fromisoformat(datetime.now().isoformat()).isoformat() # Reset dismissal timestamp for new version
                self.settings_manager.save_settings()
                # Show banner on the main thread
                QTimer.singleShot(0, self._show_update_banner)
    
            self.new_version_description = version_description
        else:
            log("Update check failed: Remote server unreachable or invalid response.",
                log_level=2, context=ctx)
            self.new_version_description = None
            self.new_version_available = False
            # Do not touch the banner on failure — don't hide it if grace period is active
            # and don't show it if there was no prior pending update.
    
        self.settings_manager.save_settings()
        change_cursor('normal')


    def _grace_expired(self):
        dismissed_ts = getattr(config, 'update_dismissed_timestamp', None)
        grace_expired = False
    
        if dismissed_ts:
            try:
                from datetime import datetime
                dismissed_dt = datetime.fromisoformat(dismissed_ts)
                days_elapsed = (datetime.now() - dismissed_dt).days
                grace_expired = days_elapsed >= 7
            except Exception:
                grace_expired = False
    
        return grace_expired


    def _show_update_banner(self):
        """
        Displays the update notification banner above the downloads table.
        Switches to aggressive messaging after the 7-day grace period expires.
        """
        banner = self.ui.update_banner
        self.msg_label = self.ui.banner_message
        icon_label = self.ui.banner_icon
        self.language = config.lang
    
        # Determine if we're past the grace period
        grace_expired = self._grace_expired()
        
        if grace_expired:
            icon_label.setText("⚠️")
            
            self.msg_label.setText(UPDATE_AVAILABLE_TRANSLATIONS[f"aggressive"][self.language])
            self.ui.banner_update_btn.setText(self.tr('Update Now'))
            # self.ui.banner_later_btn.setText(self.tr('Later'))
            banner.setStyleSheet("""
                QWidget#UpdateBanner {
                    background-color: rgba(183, 28, 28, 0.18);
                    border-bottom: 1px solid #b71c1c;
                    border-radius: 6px;
                }
                QLabel#BannerMessage { color: #b71c1c; font-size: 15px; }
                QPushButton#BannerUpdateBtn {
                    background-color: #c62828; color: white;
                    border-radius: 4px; font-weight: bold; font-size: 11px;
                }
                QPushButton#BannerLaterBtn {
                    background: transparent; color: #ef9a9a;
                    border: 1px solid #ef9a9a; border-radius: 4px; font-size: 11px;
                }
            """)
            # Hide the Later button after grace period — nudge harder
            self.ui.banner_later_btn.setVisible(False)
        else:
            icon_label.setText("🔔")
            
            self.msg_label.setText(UPDATE_AVAILABLE_TRANSLATIONS[f"normal"][self.language])
            self.ui.banner_update_btn.setText(self.tr('Update Now'))
            self.ui.banner_later_btn.setText(self.tr('Later'))
            banner.setStyleSheet("""
                QWidget#UpdateBanner {
                    background-color: rgba(33, 150, 243, 0.12);
                    border-bottom: 1px solid #1565c0;
                    border-radius: 6px;
                }
                QLabel#BannerMessage { color: #1565c0; font-size: 15px; }
                QPushButton#BannerUpdateBtn {
                    background-color: #1565c0; color: white;
                    border-radius: 4px; font-weight: bold; font-size: 11px;
                }
                QPushButton#BannerLaterBtn {
                    background: transparent; color: #90caf9;
                    border: 1px solid #90caf9; border-radius: 4px; font-size: 11px;
                }
            """)
            self.ui.banner_later_btn.setVisible(True)
    
        # Wire buttons (disconnect first to prevent duplicate connections)
        try:
            self.ui.banner_update_btn.clicked.disconnect()
            self.ui.banner_later_btn.clicked.disconnect()
        except RuntimeError:
            pass
    
        self.ui.banner_update_btn.clicked.connect(self._on_banner_update_now)
        self.ui.banner_later_btn.clicked.connect(self._on_banner_later)
    
        banner.setVisible(True)
        log("Update banner displayed.", log_level=1, context="UPDATE-ENGINE")


    def _on_banner_update_now(self):
        """User clicked 'Update Now' on the banner."""
        self.ui.update_banner.setVisible(False)
        # Clear grace period since user chose to update
        config.update_dismissed_timestamp = None
        self.settings_manager.save_settings()
        self.handle_update()


    def _on_banner_later(self):
        """
        User clicked 'Later'. Record the dismissal timestamp to start/continue
        the grace period, then hide the banner for this session.
        """
        from datetime import datetime
        # Only set the timestamp on first dismissal, not on subsequent ones
        if not getattr(config, 'update_dismissed_timestamp', None):
            config.update_dismissed_timestamp = datetime.now().isoformat()
            self.settings_manager.save_settings()
            log("Update deferred. Grace period started.", log_level=1, context="UPDATE-ENGINE")
        else:
            log("Update deferred again. Grace period continues.", log_level=1, context="UPDATE-ENGINE")
    
        self.ui.update_banner.setVisible(False)


    def start_update(self):
        """Initiates the main application binary update thread."""
        log("Spawning CheckUpdateAppThread...", log_level=1, context="UPDATE-ENGINE")
        self.start_update_thread = CheckUpdateAppThread()
        self.start_update_thread.app_update.connect(self.update_app)
        self.start_update_thread.start()


    def start_update_yt_dlp(self):
        """Initiates the yt-dlp backend update sequence."""
        log("Spawning YtDlpUpdateThread...", log_level=1, context="UPDATE-ENGINE")
        self.yt_dlp_update_thread = YtDlpUpdateThread()
        self.yt_dlp_update_thread.update_finished.connect(self.on_yt_dlp_update_finished)
        self.yt_dlp_update_thread.start()
        self.background_threads.append(self.yt_dlp_update_thread)
        
        # Switch UI to terminal/log view for progress monitoring
        self.change_page(idx=1)


    def apply_pending_yt_dlp_update_on_startup(self):
        """
        Performs an atomic swap of the yt-dlp executable if a pending update exists.
        
        Because binaries are often locked while the app is running, updates are 
        downloaded as '.exe.new'. This method attempts to replace the old 
        binary before the engine is initialized.
        """
        ctx = "APP-LIFECYCLE"
        yt_dlp_path = getattr(config, "yt_dlp_exe", "")
        if not yt_dlp_path:
            return False, "No yt-dlp path configured."
    
        target_exe = Path(yt_dlp_path)
        pending_exe = target_exe.with_suffix('.exe.new')
    
        if pending_exe.exists():
            try:
                # Attempt atomic replacement (rename)
                os.replace(str(pending_exe), str(target_exe))
                log(f"Successfully applied pending yt-dlp update: {target_exe.name}", 
                    log_level=1, context=ctx)
                
                show_information(self, self.tr('yt-dlp Update'), 
                                 self.tr('yt-dlp backend has been successfully updated.'))
                return True, "Update applied."
            except Exception as e:
                # Keep .new file for subsequent retry on next launch
                log(f"Critical: Failed to swap yt-dlp binary: {e}", log_level=3, context=ctx)
                show_critical(self, self.tr('Update Error'), 
                              f"{self.tr('Failed to apply pending update:')} {e}")
                return False, str(e)
                
        return False, "No pending updates."


    def on_yt_dlp_update_finished(self, success: bool, message: str):
        """
        Handles the completion of the yt-dlp backend update.
        
        On success, it notifies the user and reverts the UI to the main page.
        On failure, it displays the error returned by the update thread.
        """
        ctx = "UPDATE-ENGINE"
        log("Backend update process concluded.", log_level=1, context=ctx)
        
        if success:
            show_information(self, self.tr("yt-dlp Update"), 
                self.tr("yt-dlp has been updated to the latest version."))
            new_version = self.ui_settings.get_ytdlp_version(force_refresh=True)
            self.ui_settings.ytdlp_version_label.setText(self.tr("yt-dlp version: %1").replace("%1", new_version))
        else:
            # Fallback error message if 'message' is empty
            err_msg = message or self.tr("Update failed or binary is already up to date.")
            show_warning(self, self.tr("yt-dlp Update Error"), err_msg)
        
        # Return to main download list (Index 0)
        self.change_page(idx=0)


    def update_app(self, new_version_available: bool):
        """
        Evaluates update availability and determines the appropriate UI response.
        
        If a new version is detected, it pushes a signal to open the Update GUI.
        Otherwise, it displays the current vs. server version comparison.
        """
        if new_version_available:
            config.main_window_q.put(('show_update_gui', ''))
        else:
            # Display version comparison info
            v_info = f"{self.tr('Current version:')} {config.APP_VERSION}\n" \
                     f"{self.tr('Server version:')} {config.APP_LATEST_VERSION}"
            
            show_information(self, self.tr("App Update"), self.tr("App is up-to-date"), v_info)
    
            # Integrity check: If we have no version description, the check likely failed
            if not getattr(self.start_update_thread, 'new_version_description', None):
                show_critical(self, self.tr("App Update"), 
                    self.tr("Couldn't check for update") + "\n" + self.tr("Please check your internet connection.")
                )


    def show_update_gui(self):
        """
        Displays a modal dialog with the latest changelog and update options.
        
        The dialog is fixed-size to ensure readability of the QTextEdit description 
        area and blocks input to the main window until resolved.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr('Update Application'))
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
    
        layout.addWidget(QLabel(self.tr('New version available:')))
    
        # Changelog Display (Read-Only)
        description_edit = QTextEdit()
        changelog = getattr(self.start_update_thread, 'new_version_description', "")
        description_edit.setText(changelog or self.tr("No changelog available."))
        description_edit.setReadOnly(True)
        description_edit.setFixedSize(400, 200)
        layout.addWidget(description_edit)
    
        # Action Buttons
        button_layout = QHBoxLayout()
        update_btn = QPushButton(self.tr('Update'))
        cancel_btn = QPushButton(self.tr('Cancel'))
        button_layout.addWidget(update_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
    
        # Connection logic
        update_btn.clicked.connect(lambda: [dialog.accept(), self.handle_update()])
        cancel_btn.clicked.connect(dialog.reject)
    
        dialog.exec()


    def handle_update(self):
        """
        Spawns the UpdateThread to download and prepare the installation.
        
        Redirects the UI to the log page (Index 1) so the user can see 
        the download progress of the new installer.
        """
        log("Application update initiated.", log_level=1, context="UPDATE-ENGINE")
        self.update_thread = UpdateThread()
        self.update_thread.update_finished.connect(self.on_update_finished)
        self.update_thread.start()
        
        # Switch to terminal view
        self.change_page(idx=1)


    def on_update_finished(self):
        """Final cleanup log once the binary update process completes."""
        log("Application binary download finished.", log_level=1, context="UPDATE-ENGINE")
