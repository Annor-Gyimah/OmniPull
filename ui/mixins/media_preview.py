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


class MediaPreviewMixin:
    """Mixin providing MediaPreview methods for DownloadManagerWindow."""

    def show_thumbnail(self, thumbnail=None):
        """
        Updates the preview image in the 'Add Download' dialog.
        
        If a URL is provided, it initiates an asynchronous network request. 
        If a local path is provided, it loads the pixmap directly. If no 
        parameter is passed, it resets the view to a generic filetype icon.
        """
        ctx = "GUI-ASSETS"
        try:
            if not thumbnail:
                log("Resetting preview to default state.", log_level=2, context=ctx)
                self.reset_to_default_thumbnail()
                return
    
            if thumbnail != self.current_thumbnail:
                self.current_thumbnail = thumbnail
    
                if thumbnail.startswith(('http://', 'https://')):
                    # Asynchronous remote fetch via QNetworkAccessManager
                    request = QNetworkRequest(QUrl(thumbnail))
                    self.network_manager.get(request)
                else:
                    # Direct local file load
                    pixmap = QPixmap(thumbnail)
                    if not pixmap.isNull():
                        self.ui_add_download.thumbnail_label.setPixmap(
                            pixmap.scaled(140, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        )
                    else:
                        self.reset_to_default_thumbnail()
    
        except Exception as e:
            log(f"Thumbnail rendering failed: {e}", log_level=3, context=ctx)
            self.reset_to_default_thumbnail()


    def reset_to_default_thumbnail(self):
        """
        Clears the current preview and attempts to display a filetype-specific icon.
        
        Uses the extension of the current DownloadItem (self.d) to find a 
        matching system icon (e.g., a music note for .mp3).
        """
        self.ui_add_download.thumbnail_label.clear()
        self.ui_add_download.thumbnail_label.setAlignment(Qt.AlignCenter)
    
        # Retrieve extension from the active download item
        ext = getattr(self.d, "ext", "")
        if ext and not ext.startswith("."):
            ext = f".{ext}"
    
        # Fallback to 'No preview' text if no icon is found
        if not self.show_filetype_thumbnail(ext):
            self.ui_add_download.thumbnail_label.setText(self.tr("No preview"))


    def show_filetype_thumbnail(self, ext: str | None) -> bool:
        """
        Loads a standard icon pixmap based on the provided file extension.
        """
        pixmap = get_file_icon(ext)
        if pixmap.isNull():
            return False
        
        self.ui_add_download.thumbnail_label.setPixmap(
            pixmap.scaled(100, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        return True


    def on_thumbnail_downloaded(self, reply):
        """
        Callback for the QNetworkAccessManager when a remote thumbnail fetch completes.
        """
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            image = QImage()
            if image.loadFromData(data):
                pixmap = QPixmap.fromImage(image)
                self.ui_add_download.thumbnail_label.setPixmap(
                    pixmap.scaled(140, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            else:
                self.reset_to_default_thumbnail()
        else:
            self.reset_to_default_thumbnail()


    def is_playable_media(self, d) -> bool:
        """Determines if the file extension is supported for streaming playback."""
        media_exts = {"mp4", "webm", "mkv", "avi", "mov", "flv", "ts"}
        return bool(d and d.ext and d.ext.lower() in media_exts and d.progress >= 30)


    def watch_downloading(self):
        """
        Enables media playback of a file currently in progress.
        
        To avoid file-locking conflicts between the downloader and the media 
        player, this method creates an 'atomic refresh copy' (.watch file). 
        The player opens the copy while the engine continues writing to the 
        main temporary file.
        """
        ctx = "MEDIA-WATCH"
        selected_row = self.ui.table.currentRow()
        self.selected_row_num = len(self.d_list) - 1 - selected_row
    
        try:
            d = self.selected_d
            
            # --- NEW: Enhanced detection for yt-dlp downloads ---
            is_ytdlp = (getattr(d, "engine", "") == "yt-dlp")
            
            if is_ytdlp:
                # For yt-dlp, look for the partial download in the folder
                # yt-dlp typically saves to the final filename (or .part file)
                import glob
                
                # Try to find the in-progress file
                base_name = os.path.splitext(d.name)[0] if d.name else "download"
                possible_files = []
                
                # Look for .part files first (yt-dlp's incomplete downloads)
                part_pattern = os.path.join(d.folder, f"{base_name}*.part")
                possible_files.extend(glob.glob(part_pattern))
                
                # Also check for the target file itself (yt-dlp might write directly)
                if d.target_file and os.path.exists(d.target_file):
                    possible_files.append(d.target_file)
                
                # Look for any matching filename without .part
                no_part_pattern = os.path.join(d.folder, f"{base_name}*")
                for f in glob.glob(no_part_pattern):
                    if not f.endswith('.part') and not f.endswith('.watch') and os.path.isfile(f):
                        # Check if it's a video file
                        ext = os.path.splitext(f)[1].lower()
                        if ext in ('.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.ts', '.m4v'):
                            possible_files.append(f)
                
                if not possible_files:
                    show_warning(self, self.tr("No Temp File"), 
                        self.tr("The yt-dlp download file is not yet available on disk.\n"
                            "Please wait a few moments for the download to create the file."))
                    return
                
                # Use the largest file (most likely the actual download)
                src = max(possible_files, key=lambda f: os.path.getsize(f) if os.path.exists(f) else 0)
                
                log(f"[MEDIA-WATCH] Found yt-dlp partial file: {src}", log_level=1, context=ctx)
                
            else:
                # Handle m3u8 stream detection (wait briefly for first segments)
                if 'm3u8' in (d.protocol or '') and (not os.path.exists(getattr(d, "temp_file", ""))):
                    for _ in range(10):
                        if os.path.exists(getattr(d, "temp_file", "")): break
                        time.sleep(0.1)
    
                if not d or not os.path.exists(getattr(d, "temp_file", "")):
                    show_warning(self, self.tr("No Temp File"), 
                                self.tr("The temporary media file is not yet available on disk."))
                    return
                
                src = d.temp_file
    
            # Prevent players from crashing on nearly-empty files
            try:
                file_size = os.path.getsize(src)
                if file_size < 1024 * 1024:  # Less than 1MB
                    show_warning(self, self.tr("File Too Small"), 
                                self.tr("Please wait for more data to download before watching.\n"
                                    f"Current size: {size_format(file_size)}"))
                    return
            except Exception:
                pass
    
            # Check progress threshold for non-yt-dlp downloads
            if not is_ytdlp and getattr(d, "progress", 0) < 30:
                show_warning(self, self.tr("Buffer Low"), 
                            self.tr("Please wait for 30% progress to ensure a stable playback buffer."))
                return
    
            base_watch = src + ".watch"
    
            def _atomic_refresh_copy(src_path: str, dst_path: str) -> str:
                """
                Attempts an atomic copy-replace to refresh the playback file.
                If the .watch file is locked by the player, generates a unique numbered version.
                """
                folder = os.path.dirname(dst_path)
                tmp = dst_path + ".tmp"
                os.makedirs(folder, exist_ok=True)
    
                try:
                    shutil.copy2(src_path, tmp)
                    os.replace(tmp, dst_path)
                    return dst_path
                except Exception:
                    # Destination likely locked by the player (VLC/MPV); use a numbered fallback
                    n = 2
                    while n <= 50:
                        alt = f"{dst_path}.{n}"
                        try:
                            shutil.copy2(src_path, alt)
                            return alt
                        except Exception:
                            n += 1
                    raise RuntimeError("Unable to create a unique playback copy (max retries reached).")
    
            # Refresh the playback copy with the latest downloaded bytes
            watch_path = _atomic_refresh_copy(src, base_watch)
    
            # Launch the preview in a separate thread
            self.file_open_thread = FileOpenThread(watch_path, self)
            self.file_open_thread.start()
            self.background_threads.append(self.file_open_thread)
            
            log(f"Media preview initiated via: {watch_path}", log_level=1, context=ctx)
            
            # --- NEW: Auto-refresh mechanism for yt-dlp ---
            if is_ytdlp and d.status == config.Status.downloading:
                def _auto_refresh_watch_file():
                    """Background thread that periodically updates the .watch file."""
                    refresh_interval = 10  # seconds
                    last_size = 0
                    
                    while d.status == config.Status.downloading:
                        try:
                            time.sleep(refresh_interval)
                            
                            current_size = os.path.getsize(src) if os.path.exists(src) else 0
                            
                            # Only refresh if the file has grown
                            if current_size > last_size:
                                try:
                                    _atomic_refresh_copy(src, base_watch)
                                    last_size = current_size
                                    log(f"[MEDIA-WATCH] Auto-refreshed watch file: {size_format(current_size)}", 
                                        log_level=2, context=ctx)
                                except Exception as e:
                                    log(f"[MEDIA-WATCH] Refresh failed: {e}", log_level=3, context=ctx)
                        except Exception:
                            break
                    
                    log("[MEDIA-WATCH] Auto-refresh thread exiting", log_level=2, context=ctx)
                
                refresh_thread = Thread(target=_auto_refresh_watch_file, daemon=True, name="watch-refresh")
                refresh_thread.start()
                self.background_threads.append(refresh_thread)
    
        except Exception as e:
            log(f"Media preview failed: {e}", log_level=3, context=ctx)
