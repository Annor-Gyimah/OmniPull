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


class URLProcessorMixin:
    """Mixin providing URLProcessor methods for DownloadManagerWindow."""

    def on_import_file_clicked(self):
        """Triggered when the user selects a text file for batch import."""
        selected_queue = self.ui_add_download.queue_combo.currentText()
    
    
        file_path, _ = QFileDialog.getOpenFileName(
            self.ui_add_download,
            self.tr("Select Links File"),
            "",
            "Text Files (*.txt *.lst);;All Files (*)",
        )
        if not file_path:
            return
    
        # ── Reset batch state ──────────────────────────────────────────────
        self._is_batch_mode    = True
        self._batch_items      = []
        self._batch_total_size = 0
        self._processing_cancel_requested = False
    
        # Suppress the 900-ms queue_updates() 'size' overwrite
        self._batch_ui_active = True
    
        # Write file path into url_edit WITHOUT firing url_text_change
        self.ui_add_download.url_edit.blockSignals(True)
        self.ui_add_download.url_edit.setText(file_path)
        self.ui_add_download.url_edit.blockSignals(False)
    
        # Fix 1 — clear stale single-URL metadata before batch mode takes over
        self.ui_add_download.filename_edit.clear()
        self.ui_add_download.resolution_combo.clear()
        self.ui_add_download.thumbnail_label.clear()
        self.ui_add_download.thumbnail_label.setText("")
    
        self.ui_add_download.lbl_size_value.setText(self.tr("Calculating…"))
        self.ui_add_download.url_progress.setRange(0, 0)   # indeterminate
        self.ui_add_download.url_progress.show()
        self.ui_add_download.download_btn.setText(self.tr("Start Download"))
        self.ui_add_download.download_btn.setEnabled(False)
    
        # Cancel any leftover worker from a previous import
        if getattr(self, "_batch_worker", None) and self._batch_worker.isRunning():
            self._batch_worker.cancel()
            self._batch_worker.wait(2000)
    
        self._batch_worker = BatchImportWorker(file_path, parent=self)
        self._batch_worker.item_ready.connect(self._on_batch_item_ready)
        self._batch_worker.progress_text.connect(
            lambda txt: log(f"[BatchImport] {txt}", log_level=1)
        )
        self._batch_worker.finished_ok.connect(self._on_batch_finished)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_worker.start()


    @Slot(object)
    def _on_batch_item_ready(self, item):
        """Called on the main thread each time one URL is resolved."""
        self._batch_items.append(item)
        self._batch_total_size += item.size or 0
    
        count    = len(self._batch_items)
        size_txt = (
            size_format(self._batch_total_size)
            if self._batch_total_size > 0
            else self.tr("Unknown size")
        )
        self.ui_add_download.lbl_size_value.setText(
            f"{count} link{'s' if count != 1 else ''} — {size_txt}"
        )


    def _refresh_batch_button_label(self):
        """Update batch download button label when queue selection changes."""
        if not getattr(self, '_is_batch_mode', False):
            return
        count = len(getattr(self, '_batch_items', []))
        if count == 0:
            return
        selected_queue = self.ui_add_download.queue_combo.currentText()
        has_queue = selected_queue and selected_queue != "None"
        if has_queue:
            self.ui_add_download.download_btn.setText(self.tr(f"Add {count} to Queue"))
        else:
            self.ui_add_download.download_btn.setText(self.tr(f"Start {count} Download{'s' if count != 1 else ''}"))


    @Slot()
    def _on_batch_finished(self):
        count    = len(self._batch_items)
        size_txt = (
            size_format(self._batch_total_size)
            if self._batch_total_size > 0
            else self.tr("Unknown size")
        )
        self.ui_add_download.lbl_size_value.setText(
            f"{count} link{'s' if count != 1 else ''} — {size_txt}"
        )
        self.ui_add_download.url_progress.setRange(0, 100)
        self.ui_add_download.url_progress.setValue(100)
        QTimer.singleShot(1500, self.ui_add_download.url_progress.hide)
    
        # Label depends on whether a queue is selected
        selected_queue = self.ui_add_download.queue_combo.currentText()
        has_queue = selected_queue and selected_queue != "None"
    
        if has_queue:
            label = self.tr(f"Add {count} to Queue") if count else self.tr("Start Download")
        else:
            label = self.tr(f"Start {count} Download{'s' if count != 1 else ''}") if count else self.tr("Start Download")
    
        self.ui_add_download.download_btn.setText(label)
        self.ui_add_download.download_btn.setEnabled(True)
        log(f"[BatchImport] UI finalised – {count} items ready", log_level=1)


    @Slot(str)
    def _on_batch_failed(self, reason):
        self._batch_ui_active = False
        self._is_batch_mode   = False
        self.ui_add_download.url_progress.setRange(0, 100)
        self.ui_add_download.url_progress.setValue(0)
        self.ui_add_download.url_progress.hide()
        self.ui_add_download.lbl_size_value.setText(self.tr("Import failed"))
        self.ui_add_download.download_btn.setText(self.tr("Start Download"))
        self.ui_add_download.download_btn.setEnabled(True)
        show_critical(self.ui_add_download, self.tr("Batch Import Error"), reason)


    def clean_url(self, original_url: str) -> str:
        """Removes tracking parameters and keeps essential identifiers like video IDs."""
        parsed = urlparse(original_url)
        query = parse_qs(parsed.query)
        
        clean_query = {}
        if 'v' in query:
            clean_query['v'] = query['v']
    
        new_query = urlencode(clean_query, doseq=True)
        return urlunparse(parsed._replace(query=new_query))


    def is_youtube_url(self, url: str) -> bool:
        """Determines if a URL belongs to the YouTube domain suite."""
        netloc = urlparse(url).netloc.lower()
        return any(netloc.endswith(d) for d in ('youtube.com', 'youtu.be', 'music.youtube.com'))


    def fast_process_url(self, url: str, referrer: str = None, 
                         trusted_size: int = None, trusted_name: str = None) -> bool:
        """
        Executes high-speed metadata extraction using the Rust processor.
        
        This 'Fast Path' attempts to resolve direct stream URLs and file 
        metadata without invoking the heavier yt-dlp engine. It utilizes 
        a hybrid logic that prioritizes 'Trusted' browser metadata over 
        extracted data to bypass common 403 Forbidden errors.
        """
        ctx = "URL-FAST-PATH"
        self.d.url = url
        self.d.update(url) 
        self.d.referrer = referrer
    
        # 1. Primary Extraction via Rust Processor
        result = omnipull_url_processor.process_url(url, 15, referrer)
        rust_succeeded = result.is_supported
    
        # 2. URL Hot-Swap Logic: Handle TikTok/Social Stream redirection
        if rust_succeeded and result.real_url:
            log(f"Real stream detected; swapping {url[:20]}... for {result.real_url[:20]}...", 
                log_level=1, context=ctx)
            self.d.url = result.real_url
            self.d.update(result.real_url) 
    
        # 3. Hybrid Reliability Logic
        if not rust_succeeded:
            if not trusted_size:
                log(f"Rust extraction rejected: {result.last_error or 'Unsupported platform'}", 
                    log_level=2, context=ctx)
                return False
            log("Engine rejected URL, but recovering via trusted browser metadata.", 
                log_level=1, context=ctx)
    
        elif (result.size or 0) < 5120 and trusted_size and trusted_size > 1024 * 1024:
            log(f"Detected 'Soft 403' in Rust ({result.size} bytes). Overriding with browser data.", 
                log_level=1, context=ctx)
        
        elif rust_succeeded and (result.size or 0) == 0 and not trusted_size:
            if "instagram.com" in url.lower():
                log("Instagram size mismatch (0 bytes). Delegating to yt-dlp.", 
                    log_level=1, context=ctx)
                return False
    
        # 4. Final Metadata Assignment (Priority: Trusted > Rust > Extracted)
        self.d.name = trusted_name if trusted_name else (result.filename or self.d.name)
        self.d.size = trusted_size if trusted_size else (result.size or 0)
        
        if result.content_type and "html" not in result.content_type:
            self.d.type = result.content_type
    
        # 5. UI Finalization
        self.d.ext = self.extract_ext_from_url(self.d.url, self.d)
        self.ui_add_download.filename_edit.setText(self.d.name)
        self.ui_add_download.lbl_size_value.setText(
            size_format(self.d.size) if self.d.size else "Unknown"
        )
        btn = self.ui_add_download.advance_btn
        btn.setStyleSheet("border: 1px solid #3a3d42; border-radius: 4px; padding: 6px 14px; font-size: 13px;")  
        self.ui_add_download.advance_btn.setEnabled(False)
        self._show_close_button()
        
        self.category_checker(self.d)
        self.ui_add_download.url_progress.setRange(0, 100)
        self.reset_to_default_thumbnail()
        self.ui_add_download.url_progress.setValue(100)
        
        log(f"Fast URL resolution success. Size: {size_format(self.d.size)}", 
            log_level=1, context=ctx)
        return True


    def url_text_change(self, referrer=None, trusted_size=None, trusted_name=None):
        """
        Orchestrates the metadata extraction sequence when the URL input changes.
        
        Logic Flow:
        1. Sanitizes the URL based on site sensitivity (token preservation).
        2. Validates external dependencies (e.g., Deno for YouTube JS challenges).
        3. Attempts the Rust 'Fast Path' for immediate metadata resolution.
        4. Falls back to the yt-dlp 'Deep Path' via a debounced timer if needed.
        """
        url = self.ui_add_download.url_edit.text().strip()
        ctx = "URL-PROC"
    
        # 1. Sanitization Logic (Sensitive Site Token Preservation)
        sensitive_sites = ["licdn.com", "linkedin.com", "kwik.cx", "instagram.com"]
        is_sensitive = any(site in url.lower() for site in sensitive_sites)
    
        if config.ytdlp_config['no_playlist'] and not is_sensitive:
            url = self.clean_url(url)
        
        if url == self.d.url:
            return
    
        # UI State: Transition to 'Processing' mode
        self.ui_add_download.url_progress.show()
        self.ui_add_download.url_progress.setRange(0, 0)  # Indeterminate state
        self._show_cancel_button()
        
        self._url_processing = True
        self._processing_cancel_requested = False
        self.ui_add_download.thumbnail_label.clear()
        self.ui_add_download.resolution_combo.clear()
    
        # 2. Dependency Verification (YouTube JavaScript Solver)
        if self.is_youtube_url(url):
            ok = self.ensure_dependency(
                name="Deno",
                check_func=check_deno,
                download_func=download_deno,
                recommended_dir=config.global_sett_folder,
                local_dir=config.current_directory,
                non_windows_msg=self.tr(
                    '"Deno" is required to solve JavaScript challenges for YouTube.\n'
                    "Install from the official docs or add the deno executable to PATH."
                ),
            )
            if not ok:
                log("Deno dependency check failed; aborting YouTube extraction", 
                    log_level=3, context=ctx)
                return
    
        self.reset()
    
        # 3. Execution: Rust Fast Path Attempt
        if self.fast_process_url(url, referrer=referrer, 
            trusted_size=trusted_size, 
            trusted_name=trusted_name):
            log(f"Metadata resolved instantly via fast path. Skipping yt-dlp extraction.", 
                log_level=1, context=ctx)
            return
    
        # 4. Fallback: yt-dlp Deep Path (Debounced)
        log(f"Engaging deep extraction fallback.", log_level=1, context=ctx)
    
        self.d.eff_url = self.d.url = url
        
        if isinstance(self.url_timer, Timer):
            self.url_timer.cancel()
    
        # Debounce timer prevents rapid API calls while user is typing
        self.url_timer = Timer(0.5, self.refresh_headers, args=[url])
        self.url_timer.start()


    def process_url(self):
        """Simulate processing the URL and update the progress bar.""" 
        self.ui_add_download.url_progress.show()
        progress_steps = [10, 50, 100]  
        for step in progress_steps:
            time.sleep(1) 
            self.update_progress_bar_value(step)


    def update_progress_bar_value(self, value):
        """Update the progress bar value in the Add Download dialog."""
        self.ui_add_download.url_progress.setValue(value)


    def update_progress_bar(self):
        """Update the progress bar based on URL processing."""
        Thread(target=self.process_url, daemon=True).start()


    def _cancel_url_processing(self):
        """
        Immediately halts all background metadata extraction tasks.
        
        This sets a global cancellation flag, terminates any active yt-dlp 
        subprocesses, and kills the URL debounce timer. It ensures the 
        application remains responsive even during heavy network stalls.
        """
        self._processing_cancel_requested = True
        self._url_processing = False
        self._show_close_button()
     
        if self.yt_thread is not None:
            log("User requested interruption. Signaling worker threads and killing subprocesses.", 
                log_level=1, context="URL-PROC")
            self.yt_thread.stop_event.set()
            self.yt_thread._kill_current_proc()
     
        if isinstance(self.url_timer, Timer):
            self.url_timer.cancel()
            self.url_timer = None
     
        if self.yt_thread and self.yt_thread.isRunning():
            self.yt_thread.wait(3000)
     
        self.ui_add_download.url_progress.hide()
        self.d.url = ""
        log("URL processing sequence successfully aborted.", log_level=1, context="URL-PROC")


    def on_cancel_close_clicked(self):
        """Toggles button functionality between 'Cancel Task' and 'Close Window'."""
        if self._url_processing:
            self._cancel_url_processing()
        else:
            self.ui_add_download.close()


    def reset(self):
        """
        Clears the current extraction state to prepare for a new URL.
        
        Wipes the existing DownloadItem, resets playlist/video metadata, 
        and restores the primary action button to its default text.
        """
        self.d = DownloadItem() 
        self.playlist = []
        self.video = None
        self._is_playlist_mode = False
        try:
            self.ui_add_download.download_btn.setText(self.tr("Start Download"))
        except Exception:
            pass


    def retry(self):
        """Forces a re-processing of the current URL string."""
        log("Manual extraction retry initiated by user", log_level=1, context="URL-PROC")
        self.d.url = ''
        self._url_processing = True
        self._processing_cancel_requested = False
        self._show_cancel_button()
        self.ui_add_download.url_progress.show()
        self.ui_add_download.url_progress.setRange(0, 0)
        self.url_text_change()


    def _show_cancel_button(self):
        """Updates the Add Download dialog to show the 'Cancel' state."""
        self.ui_add_download.cancel_close_btn.setText(self.tr("Cancel"))
        self.ui_add_download.cancel_close_btn.setToolTip(self.tr("Cancel URL processing"))


    def _show_close_button(self):
        """Updates the Add Download dialog to show the 'Close' state."""
        self.ui_add_download.cancel_close_btn.setText(self.tr("Close"))
        self.ui_add_download.cancel_close_btn.setToolTip("")


    def refresh_headers(self, url):
        """Initiates a header-only network request to probe file metadata."""
        if self.d.url != '':
            Thread(target=self.get_header, args=[url], daemon=True).start()


    def decide_download_engine(self):
        """
            Determines the optimal backend engine based on user preference and availability.
            
            Logic priority:
            1. If Aria2 is preferred and the binary exists, use aria2c.
            2. Fallback to 'curl' if Aria2 is missing.
            3. Use 'yt-dlp' natively for streaming media or if specifically requested.
        """
        preferred = getattr(config, "download_engine", "yt-dlp").lower()
        ctx = "URL-ENGINE"
    
        if preferred == "aria2":
            if config.aria2c_path and os.path.exists(config.aria2c_path):
                self.d.engine = "aria2c"
                if not hasattr(self.d, "aria_gid"):
                    self.d.aria_gid = None
            else:
                log("Aria2c binary not found; falling back to curl", 
                    log_level=2, context=ctx)
                self.d.engine = "curl"
        else:
            self.d.engine = preferred
    
        log(f"Engine selection finalized: {self.d.engine} for {self.d.name}", 
            log_level=1, context=ctx)
        self.settings_manager.save_d_list(self.d_list)
    
        try:
            engine_display = self.d.engine.replace("aria2c", "aria2c")
            combo = self.ui_add_download.engine_combo
            idx = combo.findText(engine_display)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        except Exception:
            pass


    def extract_ext_from_url(self, url: str, d=None) -> str:
        """
        Deduces the file extension from URL paths, query parameters, or Content-Type.
        
        Prioritizes existing local files (temp/target) first, then parses 
        the URL structure for filename hints. Falls back to 'mp4' for 
        unrecognized media to maintain UI functionality.
        """
        def _norm(ext): return (ext or "").lower().lstrip(".")
        d = d or getattr(self, "d", None)
    
        # 1. Check existing disk markers
        for p in (getattr(d, "target_file", None), getattr(d, "temp_file", None)):
            if p and os.path.exists(p):
                return _norm(os.path.splitext(p)[1])
    
        # 2. Parse URL and Query strings
        try:
            parsed = urlparse(url or getattr(d, "url", "") or getattr(d, "eff_url", ""))
            fname = unquote(os.path.basename(parsed.path or ""))
            ext = _norm(os.path.splitext(fname)[1])
            if ext: return ext
            
            q = parse_qs(parsed.query or "")
            for k in ("filename", "file", "name", "title"):
                if k in q and q[k]:
                    ext = _norm(os.path.splitext(unquote(q[k][0]))[1])
                    if ext: return ext
        except Exception:
            pass
    
        # 3. MIME-Type Fallback
        ctype_map = {"application/pdf": "pdf", "application/zip": "zip", "image/png": "png"} # Extensible
        ctype = (getattr(d, "type", "") or "").lower()
        return ctype_map.get(ctype, "mp4")


    def category_checker(self, d):
        """Automatically assigns a DownloadItem to a category based on its extension."""
        d.ext = self.extract_ext_from_url(d.url, d)
        
        mapping = {
            "Compressed": ("zip", "rar", "7z", "tar", "gz", "bz2", "xz"),
            "Documents": ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"),
            "Music": ("mp3", "flac", "aac", "ogg", "wav"),
            "Video": ("mp4", "mkv", "avi", "mov", "webm"),
            "Programs": ("exe", "msi", "deb", "rpm", "apk", "dmg")
        }
    
        d.category = "General"
        for cat, exts in mapping.items():
            if d.ext in exts:
                d.category = cat
                break
        
        self.ui_add_download.category_combo.setCurrentText(d.category)
        self.category_onChoice(d.category)


    def get_header(self, url):
        """Performs a synchronous header probe and spawns the deep extraction thread."""
        self.d.update(url)
        try:
            headers = get_headers(self.d.url)
            self.d.status_code = int(headers.get('status_code', 0) or 0)
            self.d.status_code_description = headers.get('status', '')
            self.queue_update('status_code', self.d.status_code)
        except Exception:
            pass
    
        self.category_checker(self.d)
        self.decide_download_engine()
    
        # Check if URL matches current input and trigger yt-dlp deep extraction
        if url == self.d.url:
            if self.d.status_code not in self.bad_headers and self.d.type != 'text/html':
                self.ui_add_download.download_btn.setEnabled(True)
    
            log(f"Spawning Deep Extraction thread for: {url[:40]}...", 
                log_level=1, context="URL-EXTRACT")
            
            self._processing_cancel_requested = False
            self.yt_thread = YouTubeThread(url, stop_event=threading.Event(),
                                           w_add=self.ui_add_download, w_settings=self.ui_settings)
            self.yt_thread.finished.connect(self.on_youtube_finished)
            self.yt_thread.error_occurred.connect(self.on_youtube_error)
            self.yt_thread.progress.connect(self.update_progress_bar_value)
            self.yt_thread.start()
            self.background_threads.append(self.yt_thread)


    def on_youtube_finished(self, result):
        """Processes the resulting Video or Playlist object from the extraction thread."""
        ctx = "URL-EXTRACT-FINISH"
        self._url_processing = False
        self._show_close_button()
        self.ui_add_download.url_progress.setValue(100)
    
        if self.yt_thread:
            self.yt_thread.stop_event.clear()
    
        if self._processing_cancel_requested:
            log("Post-extraction cleanup: Processing was halted by user.", 
                log_level=1, context=ctx)
            return
    
        # ── Handle Playlist Logic ──
        if isinstance(result, list):
            if not result:
                log("Extraction yielded an empty playlist stub", log_level=2, context=ctx)
                show_warning(self, self.tr("Empty Playlist"), self.tr("The playlist appears to be empty or restricted."))
                return
            
            log(f"Playlist resolved: {len(result)} items identified.", log_level=1, context=ctx)
            self.playlist = result
            self.d = self.playlist[0]
            self.d.status_code = 200
            self.ui_add_download.download_btn.setText(self.tr("Start Playlist"))
            self._is_playlist_mode = True
            self.ui_add_download.advance_btn.setEnabled(True)
            # Highlight effect: add a glowing border
            highlight_style = (
                "QPushButton {"
                "  border: 2px solid #00bfff;"
                "}"
            )
            btn = self.ui_add_download.advance_btn
            old_style = btn.styleSheet()
            btn.setStyleSheet(highlight_style)
            # Remove highlight after 1 second
            # def remove_highlight():
            #     btn.setStyleSheet(old_style)
            # QTimer.singleShot(5000, remove_highlight)
    
        # ── Handle Single Video Logic ──
        elif isinstance(result, Video):
            log(f"Single video resolved: {result.name}", log_level=1, context=ctx)
            self.playlist = [result]
            self.d = result
            self.d.status_code = 200
            self._is_playlist_mode = False
            if not self.d.ext:
                self.d.ext = self.extract_ext_from_url(self.d.url, self.d)
            self.ui_add_download.advance_btn.setEnabled(True)
    
            highlight_style = (
                "QPushButton {"
                "  border: 2px solid #00bfff;"
                "}"
            )
            btn = self.ui_add_download.advance_btn
            old_style = btn.styleSheet()
            btn.setStyleSheet(highlight_style)
            # Remove highlight after 1 second
            # def remove_highlight():
            #     btn.setStyleSheet(old_style)
            # QTimer.singleShot(5000, remove_highlight)
        
        else:
            log("Extraction failed to return valid media objects", log_level=1, context=ctx)
            self.ui_add_download.advance_btn.setEnabled(False)
            self.update_http_status(0)
            return
    
        # ── Post-Extraction UI ──
        self.update_http_status(200)
        self.update_pl_menu()
        self.update_stream_menu()
        
        if config.show_thumbnail and hasattr(self.d, 'thumbnail_url'):
            Thread(target=self.d.get_thumbnail, daemon=True).start()
            self.show_thumbnail(thumbnail=self.d.thumbnail_url)
    
        QTimer.singleShot(1000, lambda: self.ui_add_download.url_progress.hide())


    def on_youtube_error(self, error_msg: str):
        """Translates technical yt-dlp exceptions into user-friendly UI dialogs."""
        log(f"Deep extraction reported error: {error_msg}", log_level=2, context="URL-EXTRACT")
        
        err = error_msg.lower()
        if any(x in err for x in ('failed to resolve', 'connection failed', 'timeout')):
            msg = self.tr("Network Error: Connectivity lost or blocked by firewall.")
        elif 'api' in err:
            msg = self.tr("YouTube API Error: The server rejected the metadata request.")
        elif 'unavailable' in err or 'copyright' in err:
            msg = self.tr("Media Unavailable: Removed, private, or geo-blocked.")
        else:
            msg = self.tr("An unexpected error occurred during URL processing.")
    
        show_critical(self, self.tr("Extraction Failed"), msg)


    def on_advanced_button_clicked(self):
        """Displays the granular metadata inspector for the resolved Video object."""
        if not self.d or not isinstance(self.d, Video):
            return
        
        log(f"Opening advanced metadata inspector for: {self.d.name}", 
            log_level=1, context="URL-EXTRACT-FINISH")
        dlg = AdvancedMetadataDialog(self.d, self)
        dlg.apply_language_advancemetada(config.lang)
        dlg.exec()


    def get_video_info(self, url: str) -> DownloadItem:
        """
        Extracts fresh media streams and metadata using the yt-dlp backend.
        
        This is used primarily to 're-arm' expired signed URLs. It retrieves 
        the latest DASH/Normal stream links and synchronizes them with an 
        existing DownloadItem to allow a resume without losing progress.
        """
        from yt_dlp import YoutubeDL
        
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_warnings': True,
            'format': 'bestvideo+bestaudio/best',
        }
    
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    
        d = DownloadItem()
        d.url = info['url']
        d.name = safe_filename(info['title'])
        d.folder = os.path.join(os.getcwd(), "Downloads")
        d.temp_file = os.path.join(d.folder, d.name)
        d.target_file = d.temp_file + "." + get_ext_from_format(info['ext'])
        d.vid_info = info
        d.type = "dash" if '+' in info['format_id'] else "normal"
        d.protocol = info.get('protocol', 'https')
        d.eff_url = d.url
    
        # Logic for separate high-quality audio streams (DASH)
        formats = info.get('formats', [])
        best_audio = next((f for f in formats if f.get('vcodec') == 'none'), None)
        if best_audio:
            d.audio_url = best_audio['url']
            d.audio_file = os.path.join(d.folder, f"audio_for_{d.name}.{best_audio['ext']}")
    
        return d


    def _youtube_url_expired(self, url: str) -> bool:
        """
        Determines if a signed YouTube media URL is no longer valid.
        
        Checks the 'expire' timestamp in the URL query parameters or 
        performs a lightweight HEAD request with a byte-range probe 
        to verify if the server returns 403 (Forbidden) or 410 (Gone).
        """
        if not url:
            return True
        try:
            parsed = urlparse(url)
            q = parse_qs(parsed.query)
            
            # 1. Check timestamp-based expiration
            if "expire" in q:
                try:
                    exp = int(q["expire"][0])
                    # Allow a 60-second buffer for clock skew
                    if time.time() > (exp - 60):
                        return True
                except (ValueError, IndexError):
                    pass
            
            # 2. Live Probe Fallback (Lightweight Range Request)
            try:
                r = requests.head(url, headers={"Range": "bytes=0-0"}, 
                                  timeout=6, allow_redirects=True)
                return r.status_code in (403, 410)
            except Exception:
                # Network fluctuation: assume valid if metadata is present
                return False
        except Exception:
            return True


    def refresh_link_btn(self):
        """
            Re-injects a task's URL into the extraction pipeline to refresh expired tokens.
            
            This is essentially a 're-add' of an existing item. It preserves the 
            original destination folder while re-triggering the URL metadata 
            extraction process (Rust or yt-dlp) to get fresh media stream links.
        """
        ctx = "URL-REFRESH"
        selected_row = self.ui.table.currentRow()
        
        if selected_row < 0 or selected_row >= self.ui.table.rowCount():
            show_warning(self, self.tr("Action Required"), self.tr("No download item selected"))
            return
    
        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]
    
        url = d.original_url if d.engine in ['aria2c', 'aria2'] else d.url
        folder = d.folder
        config.download_folder = folder
    
        log(f"Initiating link refresh for '{d.name}' (Source: {d.engine})", 
            log_level=1, context=ctx)
    
        # 1. Prepare UI entry point — show dialog first so it can paint
        self.show_add_dialog()
        self.ui_add_download.save_to_edit.setText(folder)
    
        # Block url_edit signals so setText doesn't fire url_text_change prematurely
        self.ui_add_download.url_edit.blockSignals(True)
        self.ui_add_download.url_edit.setText(url)
        self.ui_add_download.url_edit.blockSignals(False)
    
        # 2. Reset state
        self.reset()
    
        # 3. Defer extraction so the window fully renders first (200ms grace period)
        def _deferred_start():
            self.ui_add_download.url_progress.show()
            self.ui_add_download.url_progress.setRange(0, 0)
            self.ui_add_download.save_to_edit.setText(folder)
            self.url_text_change()
    
        QTimer.singleShot(200, _deferred_start)


    def _show_youtube_batch_picker(self, yt_items: list) -> bool:
        """
        Shows a per-item resolution picker for YouTube URLs found in a batch import.
        Fetches real available formats from YouTube for each item.
        Updates each item's engine / _desired_height in-place.
        Returns True if the user confirmed, False if they cancelled.
        """
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
            QPushButton, QScrollArea, QWidget, QFrame, QProgressBar,
        )
        import threading
    
        if not yt_items:
            return True
    
        # ── Phase 1: Fetch real format data for all items (background threads) ──
        # We use extract_flat=False here specifically to get format lists.
        _format_cache = {}   # url → list of format dicts
        _fetch_errors = {}   # url → error string
        _lock = threading.Lock()
    
        def _fetch_formats(item):
            try:
                import yt_dlp
                opts = {
                    "quiet": True, "no_warnings": True,
                    "skip_download": True,
                    "socket_timeout": 20,
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(item.url, download=False)
                if info:
                    formats = info.get("formats", [])
                    with _lock:
                        _format_cache[item.url] = formats
                        # Also update item name if not yet resolved
                        if not getattr(item, "_title_resolved", False):
                            title = info.get("title")
                            if title:
                                from modules.utils import validate_file_name
                                merge_ext = "mp4"
                                item.name = f"{validate_file_name(title)}.{merge_ext}"
                                item._title_resolved = True
                        # Store vid_info on the item for brain() later
                        item.vid_info = info
            except Exception as e:
                with _lock:
                    _fetch_errors[item.url] = str(e)
    
        # Show a loading dialog while fetching
        loading_dlg = QDialog(self)
        loading_dlg.setWindowTitle(self.tr("Fetching Resolutions…"))
        loading_dlg.setModal(True)
        loading_dlg.setFixedSize(360, 100)
        ll = QVBoxLayout(loading_dlg)
        ll.addWidget(QLabel(self.tr(f"Fetching format data for {len(yt_items)} YouTube item(s)…")))
        pbar = QProgressBar()
        pbar.setRange(0, 0)  # indeterminate
        ll.addWidget(pbar)
    
        fetch_threads = []
        for item in yt_items:
            t = threading.Thread(target=_fetch_formats, args=(item,), daemon=True)
            fetch_threads.append(t)
            t.start()
    
        def _all_done():
            return all(
                item.url in _format_cache or item.url in _fetch_errors
                for item in yt_items
            )
    
        # Poll until all fetches complete, keeping the UI alive via processEvents
        loading_dlg.show()
        while not _all_done():
            QApplication.processEvents()
            time.sleep(0.05)
        loading_dlg.accept()
    
        # ── Phase 2: Build format label lists per item ──
        def _build_format_labels(formats: list) -> tuple[list[str], dict[str, dict]]:
            """
            Returns (label_list, label→format_dict) for the combobox.
            Deduplicates by resolution, keeps highest-tbr entry per height.
            """
            seen_heights = {}
            for f in formats:
                # Only video streams (has height, has video codec)
                if not f.get("height") or f.get("vcodec") == "none":
                    continue
                h = f["height"]
                tbr = f.get("tbr") or f.get("vbr") or 0
                if h not in seen_heights or tbr > (seen_heights[h].get("tbr") or 0):
                    seen_heights[h] = f
    
            labels = []
            label_map = {}
    
            # Sort heights descending
            for h in sorted(seen_heights.keys(), reverse=True):
                f = seen_heights[h]
                ext = f.get("ext", "mp4")
                fps = f.get("fps") or ""
                fps_str = f" {int(fps)}fps" if fps else ""
                vcodec = f.get("vcodec", "")
                codec_str = f" [{vcodec.split('.')[0]}]" if vcodec and vcodec != "none" else ""
                label = f"{h}p{fps_str}{codec_str} ({ext})"
                labels.append(label)
                label_map[label] = f
    
            # Add audio-only option
            # Find best audio-only stream
            audio_only = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"]
            if audio_only:
                best_audio = max(audio_only, key=lambda f: f.get("abr") or 0)
                abr = int(best_audio.get("abr") or 0)
                aext = best_audio.get("ext", "m4a")
                alabel = f"Audio only ({abr}kbps {aext})" if abr else f"Audio only ({aext})"
                labels.append(alabel)
                label_map[alabel] = best_audio
    
            # Fallback if nothing parsed
            if not labels:
                labels = ["Best available"]
                label_map["Best available"] = {}
    
            return labels, label_map
    
        # ── Phase 3: Build the picker dialog ──
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("YouTube Resolution Selection"))
        dialog.setMinimumSize(700, 460)
        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)
    
        # Summary header
        n_ok = sum(1 for item in yt_items if item.url in _format_cache)
        n_err = len(yt_items) - n_ok
        header_text = (
            f"<b>{len(yt_items)} YouTube link(s)</b> — "
            f"{n_ok} resolved"
            + (f", <span style='color:red'>{n_err} failed (will use best available)</span>" if n_err else "")
            + "<br>Choose a resolution for each item before adding to the queue."
        )
        header = QLabel(header_text)
        header.setWordWrap(True)
        main_layout.addWidget(header)
    
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(sep)
    
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        clayout = QVBoxLayout(content)
        clayout.setSpacing(8)
    
        combos = []          # list of (item, combo, label_map)
        _format_label_maps = {}
    
        for item in yt_items:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
    
            title = item.name if item.name else item.url
            lbl = QLabel(title[:65] + ("…" if len(title) > 65 else ""))
            lbl.setToolTip(title)
            lbl.setMinimumWidth(300)
            rl.addWidget(lbl)
    
            combo = QComboBox()
            combo.setMinimumWidth(240)
    
            formats = _format_cache.get(item.url, [])
            if formats:
                labels, label_map = _build_format_labels(formats)
            else:
                # Fallback for failed fetches
                labels = ["Best available", "1080p", "720p", "480p", "360p", "Audio only"]
                label_map = {}
    
            combo.addItems(labels)
            _format_label_maps[id(item)] = label_map
    
            # Status indicator
            status_lbl = QLabel()
            if item.url in _fetch_errors:
                status_lbl.setText("⚠ fetch failed")
                status_lbl.setStyleSheet("color: orange; font-size: 10px;")
            elif formats:
                status_lbl.setText(f"✓ {len(labels)} options")
                status_lbl.setStyleSheet("color: green; font-size: 10px;")
            status_lbl.setMinimumWidth(90)
    
            rl.addWidget(combo)
            rl.addWidget(status_lbl)
            combos.append((item, combo, label_map))
            clayout.addWidget(row)
    
        clayout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)
    
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self.tr("Cancel"))
        ok_btn = QPushButton(self.tr("Add to Queue"))
        ok_btn.setDefault(True)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        main_layout.addLayout(btn_row)
    
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
    
        if dialog.exec() != QDialog.Accepted:
            return False
    
        # ── Phase 4: Apply selections back to items ──
        import re as _re
        for item, combo, label_map in combos:
            chosen = combo.currentText()
    
            if chosen == "Best available" or not label_map:
                item._desired_height = None
                item._ytdlp_format_override = "bestvideo+bestaudio/best"
            elif "Audio only" in chosen:
                item._desired_height = 0
                item._ytdlp_format_override = "bestaudio/best"
            elif chosen in label_map:
                fmt = label_map[chosen]
                h = fmt.get("height")
                fmt_id = fmt.get("format_id")
                item._desired_height = h
    
                # Try to pair with best matching audio
                formats = _format_cache.get(item.url, [])
                audio_only = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"]
                if fmt_id and audio_only:
                    best_audio = max(audio_only, key=lambda f: f.get("abr") or 0)
                    item.format_id = fmt_id
                    item.audio_format_id = best_audio.get("format_id")
                    item._ytdlp_format_override = None  # use explicit IDs instead
                elif h:
                    item._ytdlp_format_override = f"bestvideo[height<={h}]+bestaudio/best"
            else:
                # Parse height from label string as fallback
                m = _re.search(r"(\d{3,4})p", chosen)
                item._desired_height = int(m.group(1)) if m else None
                if item._desired_height:
                    item._ytdlp_format_override = f"bestvideo[height<={item._desired_height}]+bestaudio/best"
    
            # YouTube must always use yt-dlp
            item.engine = "yt-dlp"
    
        return True


    def on_download_button_clicked(self, downloader=None):
        """
        Routes the UI 'Download' action to either the Playlist or Single-task engine.
        
        Performs initial URL validation and folder resolution based on the 
        selected category before delegating to the appropriate logic path.
        """
    
    
        # ── BATCH MODE  (must be first – url_edit holds a file path here) ──
        if getattr(self, '_is_batch_mode', False):
            selected_queue = self.ui_add_download.queue_combo.currentText()
            has_queue = selected_queue and selected_queue != "None"
    
            if not self._batch_items:
                show_warning(
                    self.ui_add_download,
                    self.tr("Nothing to Add"),
                    self.tr("No links have been resolved yet. Please wait for processing to finish."),
                )
                return
    
            folder   = self.ui_add_download.save_to_edit.text() or config.download_folder
            category = self.ui_add_download.category_combo.currentText()
    
            # ── YouTube resolution picker (shared by both paths) ──────────────────
            _yt_batch = [
                item for item in self._batch_items
                if "youtube.com" in (item.url or "") or "youtu.be" in (item.url or "")
            ]
            if _yt_batch:
                if not self._show_youtube_batch_picker(_yt_batch):
                    return
    
            if has_queue:
                # ── Existing queue path (unchanged) ──────────────────────────────
                queue_id = self.get_queue_id(selected_queue)
                added = 0
                for item in self._batch_items:
                    if any(d.url == item.url for d in self.d_list):
                        log(f"[BatchCommit] Skipping duplicate: {item.url[:60]}", log_level=2)
                        continue
                    item.in_queue       = True
                    item.queue_name     = selected_queue
                    item.queue_id       = queue_id
                    item.status         = config.Status.queued
                    item.folder         = folder
                    item.category       = category
                    item.id             = len(self.d_list)
                    item.last_try_date  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    item.queue_position = item.id + 1
                    self.d_list.append(item)
                    added += 1
    
                self.settings_manager.save_d_list(self.d_list)
                self.queue_update("populate_table", None)
                show_information(
                    self.ui_add_download,
                    self.tr("Batch Added"),
                    self.tr(f"Successfully staged {added} item(s) into '{selected_queue}'."),
                )
    
            else:
                # ── NEW: Direct start path ────────────────────────────────────────
                added = 0
                for item in self._batch_items:
                    if any(d.url == item.url for d in self.d_list):
                        log(f"[BatchDirect] Skipping duplicate: {item.url[:60]}", log_level=2)
                        continue
                    item.in_queue      = False
                    item.queue_name    = ""
                    item.queue_id      = None
                    item.folder        = folder
                    item.category      = category
                    item.last_try_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # start_download handles id assignment and concurrency queuing
                    self.start_download(item, silent=True)
                    added += 1
    
            
    
            # ── Shared cleanup (both paths) ───────────────────────────────────────
            self._is_batch_mode    = False
            self._batch_items      = []
            self._batch_total_size = 0
            self._batch_ui_active  = False
            self.ui_add_download.download_btn.setText(self.tr("Start Download"))
            self.ui_add_download.url_edit.blockSignals(True)
            self.ui_add_download.url_edit.clear()
            self.ui_add_download.url_edit.blockSignals(False)
            self.ui_add_download.close()
            return
        
    
        if self.d.url == "":
            show_information(self.ui_add_download, self.tr("Download Error"), 
                 self.tr("Nothing to download"), self.tr("Check your URL or click Retry."))
            return
    
        # Handle Playlist redirection
        if getattr(self, '_is_playlist_mode', False) and getattr(self, 'playlist', None):
            self.download_playlist()
            return
        
    
        
    
        # Prepare a clean copy of the current DownloadItem metadata
        d = copy.copy(self.d)
        
        # 1. Resolve Destination Folder (Category Path Priority)
        selected_category = self.ui_add_download.category_combo.currentText()
        d.category = selected_category
        
        if selected_category and hasattr(self.ui_add_download, '_category_map'):
            category_info = self.ui_add_download._category_map.get(selected_category)
            if category_info and category_info.get('path'):
                d.folder = category_info.get('path')
            else:
                d.folder = self.ui_add_download.save_to_edit.text() or config.download_folder
        else:
            d.folder = self.ui_add_download.save_to_edit.text() or config.download_folder
        
        # 2. Handle Queue Logic or Immediate Download
        selected_queue = self.ui_add_download.queue_combo.currentText()
        
        # Ensure the original URL is stored so we can compare YouTube IDs later
        d.original_url = self.d.url
    
    
        if selected_queue and selected_queue != "None":
            # Apply engine choice before queuing
            selected_engine = self.ui_add_download.engine_combo.currentText()
            if selected_engine:
                d.engine = selected_engine
            self._add_to_selected_queue(d, selected_queue)
        else:
            # Apply engine choice from the selector
            selected_engine = self.ui_add_download.engine_combo.currentText()
            if selected_engine:
                d.engine = selected_engine
            # Direct Download Path
            d.queue = None
            result = self.start_download(d, downloader=downloader)
            if result not in ('error', 'cancelled', False):
                self.ui_add_download.close()


    def _add_to_selected_queue(self, d, queue_name):
        """
        Configures a task for serialized execution within a named queue.
        
        Includes exhaustive validation for duplicates, cross-queue conflicts,
        and engine compatibility for streaming media.
        """
        ctx = "ENGINE-START"
    
        # ── 1. Engine Compatibility Check ──
        if isinstance(self.d, Video) and d.engine == "curl":
            show_warning(self, self.tr("Queue Error"), 
                         self.tr("YouTube videos in queues require aria2c or yt-dlp engine."))
            return
    
        # ── 2. Status & Duplicate Validation ──
        if d.status == config.Status.completed:
            show_warning(self, self.tr("Queue Error"), 
                         self.tr("Cannot add completed download to queue."))
            return
    
        # Check for physical file existence and cross-queue registration
        target_path = os.path.join(d.folder, d.name)
        if os.path.exists(target_path):
            existing_queue = None
            for existing_d in self.d_list:
                if (existing_d.in_queue and existing_d.name == d.name and 
                    os.path.exists(os.path.join(existing_d.folder, existing_d.name))):
                    existing_queue = existing_d.queue_name
                    break
            
            if existing_queue:
                msg = self.tr(f"This file already exists in queue: {existing_queue}")
                show_warning(self, self.tr("Queue Error"), msg)
                return
            else:
                msg = self.tr(f"Cannot add to queue; target file already exists: {target_path}")
                show_warning(self, self.tr("File Exists"), msg)
                return
    
        # ── 3. Filename Conflict across Queues ──
        for existing_d in self.d_list:
            if existing_d.in_queue and existing_d.name == d.name and existing_d.folder == d.folder:
                q_name = existing_d.queue_name
                msg = self.tr(f"Filename conflict in queue: {q_name}. Please rename or change folder.")
                show_warning(self, self.tr("Queue Error"), msg)
                return
    
        # ── 4. Final Queue Registration ──
        d.in_queue = True
        d.queue_name = queue_name
        d.queue_id = self.get_queue_id(queue_name)
        d.status = config.Status.queued
        d.last_known_progress = 0
        d.last_known_size = 0
        d.last_try_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d._segments = []
    
        
    
        if isinstance(self.d, Video):
            d.original_url = self.d.url 
    
        # Assign serialized position
        existing_positions = [item.queue_position for item in self.d_list 
            if item.in_queue and item.queue_name == queue_name]
        d.queue_position = max(existing_positions, default=0) + 1
    
        # d.id = len(self.d_list)
        d.id = max((item.id for item in self.d_list), default=-1) + 1
        self.d_list.append(d)
        
        log(f"Task '{d.name}' successfully routed to queue: {queue_name}", 
            log_level=1, context=ctx)
    
        self.settings_manager.save_d_list(self.d_list)
        self.queue_update("populate_table", None)
        
        show_information(self.ui_add_download, self.tr("Added to Queue"), 
            self.tr(f"'{d.name}' has been added to {queue_name}."))
        self.ui_add_download.close()


    def update_pl_menu(self):
        """
        Synchronizes the playlist selection UI with the extracted playlist data.
        """
        try:
            if not hasattr(self, 'playlist') or not self.playlist:
                log("Playlist menu update skipped: No data available.", 
                    log_level=2, context="UI-SELECTION")
                return
            
            # Implementation for populating playlist-specific self.ui goes here
            log("Playlist metadata synchronized with UI.", log_level=1, context="UI-SELECTION")
    
        except Exception as e:
            log(f"Playlist menu update failed: {e}", log_level=3, context="UI-SELECTION")


    def update_stream_menu(self):
        """
        Refreshes the resolution/quality combobox for the currently active video.
        """
        try:
            if not self.d or not hasattr(self.d, 'stream_names') or not self.d.stream_names:
                log("Stream menu update skipped: No streams found for current item.", 
                    log_level=2, context="UI-SELECTION")
                return
    
            self.ui_add_download.resolution_combo.clear()
            self.ui_add_download.resolution_combo.addItems(self.d.stream_names)
    
            # Default to the first available stream (typically highest quality)
            selected_stream = self.d.stream_names[0]
            self.ui_add_download.resolution_combo.setCurrentText(selected_stream)
            self.stream_OnChoice(selected_stream)
    
            log(f"Resolution menu updated with {len(self.d.stream_names)} options.", 
                log_level=1, context="UI-SELECTION")
    
        except Exception as e:
            log(f"Stream menu update failed: {e}", log_level=3, context="UI-SELECTION")


    def playlist_OnChoice(self, selected_video):
        """
        Handles user selection of a specific video within a playlist.
        """
        if selected_video not in self.playlist:
            return
    
        index = self.playlist.index(selected_video)
        self.video = self.playlist[index]
        self.d = self.video  # Point primary download pointer to selection
    
        self.update_stream_menu()
    
        if config.show_thumbnail:
            Thread(target=self.video.get_thumbnail, daemon=True).start()
            self.show_thumbnail(thumbnail=self.video.thumbnail_url)


    def category_onChoice(self, selected_category):
        """Updates the category metadata for the current download item."""
        self.d.category = selected_category


    def stream_OnChoice(self, selected_stream):
        """
        Updates the selected media stream (Resolution/Bitrate) for the active video.
        """
        ctx = "UI-SELECTION"
        video = getattr(self, 'video', None) or getattr(self, 'd', None)
        
        if video is None or not hasattr(video, 'stream_names'):
            return
    
        # Optimization: prevent redundant processing if the selection hasn't changed
        if selected_stream == getattr(video, 'selected_stream_name', None):
            return
    
        if selected_stream not in video.stream_names:
            log(f"Stream '{selected_stream}' unavailable; reverting to default.", 
                log_level=2, context=ctx)
            selected_stream = video.stream_names[0]
    
        try:
            # Map the string selection back to the actual Stream object
            video.selected_stream = video.streams[selected_stream]
            video.selected_stream_name = selected_stream
            self.video = video
            
            log(f"Quality profile adjusted: {selected_stream}", 
                log_level=1, context=ctx)
        except Exception as e:
            log(f"Stream selection error: {e}", log_level=3, context=ctx)


    def download_playlist(self):
        """
        Launches a dynamic multi-selector dialog for batch playlist processing.
        
        This method constructs a scrollable UI allowing users to:
        1. Select/Deselect specific videos from a processed playlist.
        2. Apply a 'Master Format' (resolution/bitrate) to all capable items.
        3. Individually override formats for specific videos.
        4. Bulk-add the resulting selection to the download or pending queue.
        """
        ctx = "URL-PLAYLIST"
        if not self.video or not self.playlist:
            log("Playlist extraction missing; aborting dialog launch.", 
                log_level=2, context=ctx)
            show_information(
                self.ui_add_download,
                self.tr("Playlist Download"), 
                self.tr("Please check the URL."), 
                self.tr("Playlist is empty, nothing to download.")
            )
            return
    
        # Map available streams across the entire playlist for the Master Combo
        mp4_videos = {s.raw_name: s for v in self.playlist for s in v.mp4_videos.values()}
        other_videos = {s.raw_name: s for v in self.playlist for s in v.other_videos.values()}
        audio_streams = {s.raw_name: s for v in self.playlist for s in v.audio_streams.values()}
        raw_streams = {**mp4_videos, **other_videos, **audio_streams}
    
        # ── UI Construction ──
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Playlist Download"))
        dialog.setMinimumSize(760, 420)
        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(12)
    
        # Header: Global Select and Master Format
        header_layout = QHBoxLayout()
        select_all = QCheckBox(self.tr("Select all videos"))
        header_layout.addWidget(select_all)
        header_layout.addStretch()
        header_layout.addWidget(QLabel(self.tr("Apply format to all:")))
        
        master_combo = QComboBox()
        master_combo.setMinimumWidth(260)
        master_combo.addItems(
            ['● Video Streams:'] + list(mp4_videos) + list(other_videos) + 
            ['', '● Audio Streams:'] + list(audio_streams)
        )
        header_layout.addWidget(master_combo)
        main_layout.addLayout(header_layout)
    
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(sep)
    
        # Scrollable Content: Individual Video Rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        video_checkboxes = []
        stream_combos = []
    
        for video in self.playlist:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            
            cb = QCheckBox(video.title[:45])
            cb.setToolTip(video.title)
            cb.setMinimumWidth(280)
            video_checkboxes.append(cb)
    
            combo = QComboBox()
            combo.addItems(video.raw_stream_menu)
            combo.setMinimumWidth(200)
            stream_combos.append(combo)
    
            size_lbl = QLabel(size_format(video.total_size))
            size_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            size_lbl.setMinimumWidth(70)
    
            row_layout.addWidget(cb)
            row_layout.addStretch()
            row_layout.addWidget(combo)
            row_layout.addWidget(size_lbl)
            scroll_layout.addWidget(row)
    
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)
    
        # Footer instructions and buttons
        instruction = QLabel(self.tr("Select videos and formats. Use the master option to apply settings globally."))
        instruction.setWordWrap(True)
        main_layout.addWidget(instruction)
    
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = QPushButton(self.tr("Cancel"))
        ok_btn = QPushButton(self.tr("Download"))
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        main_layout.addLayout(button_layout)
    
        # ── Internal Logic Handlers ──
    
        def queue_or_start_download(v):
            """Internal dispatcher to handle concurrency limits during batch starts."""
            try:
                max_conc = int(config.max_concurrent_downloads)
            except Exception:
                max_conc = 1
                
            if len(self.active_downloads) >= max_conc:
                v.status = config.Status.pending
                self.pending.append(v)
            else:
                self.start_download(v, silent=True)
    
        def on_ok():
            chosen = []
            for i, video in enumerate(self.playlist):
                selected = stream_combos[i].currentText()
    
                # Safety check: Ensure the selected format exists for this specific video
                if not selected or selected not in video.raw_streams:
                    log(f"Skipping {video.title}: Format mismatch.", log_level=2, context=ctx)
                    continue 
                
                video.selected_stream = video.raw_streams[selected]
                if video_checkboxes[i].isChecked():
                    chosen.append(video)
    
            log(f"Batch initiation: {len(chosen)} items selected from playlist.", 
                log_level=1, context=ctx)
            dialog.accept()
    
            # Clean up the parent entry dialog
            try:
                self.ui_add_download.close()
            except Exception:
                pass
    
            # Sequence the downloads to avoid UI locking
            for video in chosen:
                video.folder = config.download_folder
                QTimer.singleShot(0, lambda v=video: queue_or_start_download(v))
    
        def on_select_all():
            state = select_all.isChecked()
            for cb in video_checkboxes:
                cb.setChecked(state)
    
        def on_master_combo_change():
            selected = master_combo.currentText()
            # Iterate through all rows and apply the master format if available
            if selected in raw_streams:
                for i, combo in enumerate(stream_combos):
                    video = self.playlist[i]
                    if selected in video.raw_streams:
                        combo.setCurrentText(selected)
                        video.selected_stream = video.raw_streams[selected]
    
        # ── Signal Connections ──
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(lambda: dialog.reject())
        select_all.stateChanged.connect(on_select_all)
        master_combo.currentTextChanged.connect(on_master_combo_change)
    
        dialog.exec()
