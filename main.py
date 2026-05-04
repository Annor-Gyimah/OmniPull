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
from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import (QTimer, QPoint, QThread, Signal, Slot, QUrl, QTranslator, 
QCoreApplication, Qt, QTime, QProcess, QEvent, QItemSelectionModel, QStringListModel, QDateTime)
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
    CATEGORY_TRANSLATIONS, nuclear_scrub, update_native_manifests, fix_browser_integration, mark_install_healthy)




# Trigger scrub IMMEDIATELY upon execution
nuclear_scrub()

# os.environ.setdefault("QT_QPA_PLATFORMTHEME", "gtk3")

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






class YouTubeThread(QThread):
    """
    Asynchronous execution thread for YouTube metadata extraction.
    
    This class manages the lifecycle of yt-dlp extraction tasks, supporting 
    both single-video URLs and multi-entry playlists. It utilizes an asyncio 
    event loop to handle non-blocking network calls and provides a mechanism 
    to terminate subprocesses immediately via a shared stop_event.
    """
    finished       = Signal(object)   # Video | list[Video] | None
    progress       = Signal(int)      # 0-100
    error_occurred = Signal(str)

    def __init__(self, url: str, stop_event: threading.Event = None):
        super().__init__()
        self.url = url
        self.stop_event = stop_event or threading.Event()
        self.error_message = None
        self._proc_holder = [None]
        self.ctx = "YTDL-EXTRACT"

    def run(self):
        """Initializes the asyncio loop and executes the extraction lifecycle."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_async())
        except Exception as e:
            self.error_message = str(e)
            log(f"Critical failure in extraction loop: {self.error_message}", 
                log_level=3, context=self.ctx)
            self.error_occurred.emit(self.error_message)
            self.finished.emit(None)

    def _cancelled(self) -> bool:
        """Returns True if the external stop_event has been triggered."""
        return self.stop_event.is_set()

    def _kill_current_proc(self):
        """Forces termination of the active yt-dlp subprocess."""
        proc = self._proc_holder[0]
        if proc is not None:
            try:
                proc.kill()
                log(f"Subprocess terminated successfully (PID: {proc.pid})", 
                    log_level=1, context=self.ctx)
            except Exception as e:
                log(f"Failed to terminate subprocess: {e}", 
                    log_level=2, context=self.ctx)

    async def _run_async(self):
        """Coordinates the transition between playlist and single-video processing."""
        try:
            widgets_add_download.download_btn.setEnabled(False)
            widgets_settings.monitor_clipboard_chk.setChecked(False)
            widgets_add_download.resolution_combo.clear()
            change_cursor("busy")

            if self._cancelled():
                self.finished.emit(None)
                return

            log(f"Initiating metadata extraction for URL: {self.url}", 
                log_level=1, context=self.ctx)

            loop = asyncio.get_running_loop()
            stubs = await loop.run_in_executor(
                executor,
                Video.extract_playlist_entries_streaming,
                self.url,
                self.stop_event,
                self._proc_holder,
            )

            if self._cancelled():
                log("Extraction aborted by user during playlist discovery", 
                    log_level=1, context=self.ctx)
                self.finished.emit(None)
                return

            if not stubs:
                log("No playlist detected; falling back to single video extraction", 
                    log_level=1, context=self.ctx)
                await self._process_single()
                return

            if len(stubs) == 1:
                stub = stubs[0]
                if stub.get("formats"):
                    try:
                        v = Video(
                            stub.get("webpage_url") or stub.get("url") or self.url,
                            vid_info=stub,
                            get_size=False,
                        )
                        self.progress.emit(100)
                        self.finished.emit(v)
                        return
                    except Exception as e:
                        log(f"Format recovery failed for single-stub playlist: {e}", 
                            log_level=2, context=self.ctx)

            await self._process_playlist(stubs)

        except Exception as e:
            self.error_message = str(e)
            log(f"Extraction engine encountered an error: {self.error_message}", 
                log_level=3, context=self.ctx)
            self.error_occurred.emit(self.error_message)
            self.finished.emit(None)
        finally:
            change_cursor("normal")
            widgets_add_download.download_btn.setEnabled(True)
            widgets_settings.monitor_clipboard_chk.setChecked(True)

    async def _process_single(self):
        """Fetches detailed format and metadata for a standalone video URL."""
        log(f"Performing deep metadata fetch for target: {self.url}", 
            log_level=1, context=self.ctx)
        loop = asyncio.get_running_loop()
        ydl_opts = get_ytdl_options()
        try:
            vid_info = await loop.run_in_executor(
                executor, extract_info_blocking, self.url, ydl_opts
            )
        except Exception as e:
            log(f"Network request failed for single video: {e}", 
                log_level=2, context=self.ctx)
            self.error_occurred.emit(str(e))
            self.finished.emit(None)
            return

        if self._cancelled() or not vid_info:
            return

        try:
            video_obj = Video(self.url, vid_info=vid_info)
            self.progress.emit(100)
            self.finished.emit(video_obj)
        except Exception as e:
            log(f"Object instantiation failed for video metadata: {e}", 
                log_level=2, context=self.ctx)
            self.error_occurred.emit(str(e))
            self.finished.emit(None)

    async def _process_playlist(self, stubs: list[dict]):
        """Iteratively resolves flat playlist stubs into full Video objects."""
        total = len(stubs)
        playlist = []
        skipped = []
        last_pct = -1
        UPDATE_STEP = 5

        log(f"Playlist detected: processing {total} items", 
            log_level=1, context=self.ctx)

        for index, stub in enumerate(stubs):
            if self._cancelled():
                log(f"Playlist resolution halted. Finalized {len(playlist)} of {total} items.", 
                    log_level=1, context=self.ctx)
                self.finished.emit(playlist if playlist else None)
                return

            if not stub:
                continue

            video_obj = await Video.fetch_single_entry(
                stub, self.stop_event, self._proc_holder
            )

            if self._cancelled():
                return

            if video_obj is not None:
                playlist.append(video_obj)
            else:
                vid_id = stub.get("id") or stub.get("title") or f"Index {index + 1}"
                skipped.append(vid_id)
                log(f"Excluding unreachable item: {vid_id}", 
                    log_level=2, context=self.ctx)

            pct = int((index + 1) * 100 / total)
            if pct // UPDATE_STEP > last_pct // UPDATE_STEP:
                self.progress.emit(pct)
                last_pct = pct

        if skipped:
            log(f"Extraction complete. Successfully resolved {len(playlist)} items; {len(skipped)} items were skipped due to errors.", 
                log_level=1, context=self.ctx)

        self.progress.emit(100)
        self.finished.emit(playlist)


class FileOpenThread(QThread):
    """
    Handles OS-level file opening requests in a separate thread.
    
    Verifies file existence before attempting to invoke system handlers. 
    Provides cross-platform support for Windows, Linux, and macOS.
    """
    critical_signal = Signal(str, str)

    def __init__(self, file_path: str, parent=None):
        super(FileOpenThread, self).__init__(parent)
        self.file_path = file_path
        self.ctx = "SHELL-EXEC"

    def run(self):
        """Attempts to open the file using the host operating system's default handler."""
        try:
            if not os.path.exists(self.file_path):
                log(f"Target file missing from disk: {self.file_path}", 
                    log_level=3, context=self.ctx)
                self.critical_signal.emit('not_found', self.file_path)
                return

            log(f"Invoking system handler for path: {self.file_path}", 
                log_level=1, context=self.ctx)

            if config.operating_system == 'Windows':
                os.startfile(self.file_path)
            elif config.operating_system == 'Linux':
                run_command(f'xdg-open "{self.file_path}"')
            elif config.operating_system == 'Darwin':
                run_command(f'open "{self.file_path}"')

        except PermissionError:
            log(f"Access denied to file: {self.file_path}", 
                log_level=3, context=self.ctx)
            self.critical_signal.emit('Permission Error', 'Access denied.')
        except Exception as e:
            log(f"System shell failed to open file: {e}", 
                log_level=3, context=self.ctx)
            self.critical_signal.emit(
                'OS Error', 
                f"An OS error occurred while opening the file: {e}"
            )


class FileChecksum(QThread):
    checksum_computed = Signal(str, str)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            # Native Nim execution - 7GB will be scanned at SSD limit
            checksum = native_engine.compute_sha256(self.file_path)
            self.checksum_computed.emit(self.file_path, checksum)
        except Exception as e:
            self.checksum_computed.emit(self.file_path, "Error")


class FilePropertiesDialog(QDialog):
    """
    UI Dialog for inspecting granular download metadata.
    
    Displays technical properties of a DownloadItem including file system 
    location, network protocol, engine-specific status, and icon previews. 
    Supports dynamic localization through a shared translation dictionary.
    """
    
    def __init__(self, d, parent=None, language="English"):
        super().__init__(parent)
        from modules.helpers import FILE_PROPERTIES_TRANSLATIONS
        
        self.language = language
        self.ctx = "PROPERTIES-UI"
        
        log(f"Initializing properties inspector for item: {d.name}", 
            log_level=1, context=self.ctx)

        self.setWindowTitle("File Properties")
        self.setMinimumWidth(520)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(16)

        # ── Visual Identification (Icon) ──────────────────────────────────────
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        ext = getattr(d, "ext", "")
        
        pixmap = get_file_icon(f".{ext}")
        icon_label.setPixmap(pixmap.scaled(100, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        top_layout.addWidget(icon_label)

        # ── Metadata Grid ─────────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        def add_row(row, label_key, value):
            """Appends a translated label and its value to the metadata grid."""
            translated_label = FILE_PROPERTIES_TRANSLATIONS.get(label_key, {}).get(self.language, label_key)
            lbl = QLabel(translated_label)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
            lbl.setStyleSheet("font-weight: bold;") # Added for better readability

            val = QLabel(str(value) if value else "-")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            val.setWordWrap(True)

            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)

        # Populate rows with DownloadItem data
        row = 0
        add_row(row, "Name:", d.name); row += 1
        add_row(row, "Folder:", d.folder); row += 1
        add_row(row, "Download engine:", d.engine); row += 1
        add_row(row, "Progress:", f"{d._progress}%"); row += 1
        add_row(row, "Downloaded:", size_format(d.downloaded)); row += 1
        add_row(row, "Total size:", size_format(d.total_size)); row += 1
        add_row(row, "Status:", d.status); row += 1
        
        # Localized boolean for resumability
        resumable_text = (FILE_PROPERTIES_TRANSLATIONS["Yes"][self.language] if d.resumable 
            else FILE_PROPERTIES_TRANSLATIONS["No"][self.language])
        add_row(row, "Resumable:", resumable_text); row += 1
        
        add_row(row, "Type:", d.type); row += 1
        add_row(row, "Protocol:", d.protocol); row += 1
        
        webpage_url = d.original_url if d.engine in {"aria2", "aria2c"} else d.url
        add_row(row, "Webpage URL:", webpage_url)

        top_layout.addLayout(grid)
        main_layout.addLayout(top_layout)

        # ── UI Elements ───────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(divider)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton(FILE_PROPERTIES_TRANSLATIONS["Close"][self.language])
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        main_layout.addLayout(btn_layout)

    def accept(self):
        """Finalizes the dialog session and logs the closure."""
        log("Closing properties inspector", log_level=1, context=self.ctx)
        super().accept()

class SubtitleFailedDialog(QDialog):
    """
    User-intervention dialog for terminal subtitle download failures.
    
    Triggered when the automated subtitle fallback mechanism exhausts all 
    retry attempts (typically due to HTTP 429 rate-limiting). It provides 
    the user with the raw extraction URL to facilitate manual recovery 
    via an external web browser or clipboard transfer.
    """
    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.ctx = "SUB-FALLBACK-UI"
        
        self.subtitle_url = payload.get("url", "")
        lang  = payload.get("lang", "?")
        title = payload.get("title", "Unknown")
        
        log(f"Displaying manual recovery options for {lang} subtitle: {title}", 
            log_level=1, context=self.ctx)

        self.setWindowTitle(self.tr("Subtitle Download Failed"))
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Header ───────────────────────────────────────────────────────────────
        header = QLabel(self.tr("⚠  Subtitle Could Not Be Downloaded"))
        header.setStyleSheet("font-size:14px; font-weight:700;")
        layout.addWidget(header)

        # ── Info text ─────────────────────────────────────────────────────────────
        info = QLabel(
            self.tr(
                f"YouTube returned <b>HTTP 429 (Too Many Requests)</b> for the "
                f"<b>{lang}</b> subtitle of:<br>"
                f"<i>{title}</i><br><br>"
                "The subtitle URL is still valid. You can open it in your browser "
                "to view or save it manually."
            )
        )
        info.setWordWrap(True)
        info.setOpenExternalLinks(False)
        layout.addWidget(info)

        # ── URL Display ──────────────────────────────────────────────────────────
        url_box = QTextEdit()
        url_box.setReadOnly(True)
        url_box.setPlainText(self.subtitle_url)
        url_box.setFixedHeight(70)
        url_box.setStyleSheet("font-size:10px; font-family: monospace;")
        layout.addWidget(url_box)

        # ── Action Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        copy_btn = QPushButton(self.tr("Copy Link"))
        copy_btn.setToolTip(self.tr("Copy subtitle URL to clipboard"))
        copy_btn.clicked.connect(self._copy_link)
        btn_row.addWidget(copy_btn)

        open_btn = QPushButton(self.tr("Open in Browser"))
        open_btn.setDefault(True)
        open_btn.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        open_btn.setToolTip(self.tr("Open the subtitle URL in your default browser"))
        open_btn.clicked.connect(self._open_browser)
        btn_row.addWidget(open_btn)

        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _copy_link(self):
        """Transfers the subtitle resource URL to the system clipboard."""
        QApplication.clipboard().setText(self.subtitle_url)
        log("Subtitle resource URL transferred to system clipboard", 
            log_level=1, context=self.ctx)

    def _open_browser(self):
        """Invokes the default system browser to access the subtitle stream."""
        log(f"Delegating subtitle recovery to external browser: {self.subtitle_url}", 
            log_level=1, context=self.ctx)
        QDesktopServices.openUrl(QUrl(self.subtitle_url))
        self.accept()



class LogRecorderThread(QThread):
    """
    Background worker for persistent file logging.
    
    This thread monitors the 'log_recorder_q' and flushes messages to the disk
    periodically. It ensures that file I/O operations do not block the main 
    GUI thread. It handles exit conditions gracefully to ensure a final 
    flush of the buffer before the application terminates.
    """
    error_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.buffer = ''
        self.file = os.path.join(config.sett_folder, 'log.txt')
        self._stop = False
        self.ctx = "LOG-WRITER"
        self.mode = "w" if getattr(config, "LOG_MODE", "append") == "overwrite" else "a"

        # Clear file only once at startup
        if self.mode == "w":
            try:
                with open(self.file, "w", encoding="utf-8", errors="ignore") as f:
                    f.write('')
            except Exception:
                pass

        # After init, always append
        self.mode = "a"

    def stop(self):
        """Triggers the thread to finalize current work and exit."""
        self._stop = True

    def run(self):
        """Continuously polls the log queue and appends data to the log file."""
        try:
            while True:
                if self._stop or self.isInterruptionRequested() or getattr(config, "terminate", False):
                    break

                try:
                    q = config.log_recorder_q
                    # Drain the queue into the local buffer
                    while not q.empty():
                        self.buffer += q.get()

                    if self.buffer:
                        # with open(self.file, 'a', encoding="utf-8", errors="ignore") as f:
                        with open(self.file, self.mode, encoding="utf-8", errors="ignore") as f:
                            f.write(self.buffer)
                            self.buffer = ''

                    self.msleep(100)

                except Exception as e:
                    # Non-breaking log as we don't want the recorder to crash
                    self.error_signal.emit(f'Internal log recorder error: {e}')
                    self.msleep(200)

        finally:
            self._final_flush()

    def _final_flush(self):
        """Ensures any remaining logs in the buffer are saved during shutdown."""
        try:
            if self.buffer:
                # with open(self.file, 'a', encoding="utf-8", errors="ignore") as f:
                with open(self.file, self.mode, encoding="utf-8", errors="ignore") as f:
                    f.write(self.buffer)
                    self.buffer = ''
        except Exception:
            pass


class MarqueeLabel(QLabel):
    """
    An auto-scrolling QLabel for handling long text strings.
    
    Used primarily in menu actions or file lists where full filenames 
    exceed available space. Scrolling activates on mouse hover and 
    resets to the original state when the mouse leaves the widget area.
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.full_text = text
        self.offset = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scroll_text)
        self.setText(text)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def enterEvent(self, event):
        """Initiates the scrolling animation when the mouse enters the widget."""
        self.timer.start(100)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Stops the animation and resets text position when mouse leaves."""
        self.timer.stop()
        self.offset = 0
        self.setText(self.full_text)
        super().leaveEvent(event)

    def scroll_text(self):
        """Circularly shifts the text string to create a marquee effect."""
        if len(self.full_text) <= 30:
            return
        self.offset = (self.offset + 1) % len(self.full_text)
        text = self.full_text[self.offset:] + "   " + self.full_text[:self.offset]
        self.setText(text)


class CheckUpdateAppThread(QThread):
    """
    Handles version verification by comparing local state with remote manifests.
    
    Polls the server for the latest changelog, updates global version variables, 
    and signals the UI if a higher version number is detected.
    """
    app_update = Signal(bool)

    def __init__(self, remote: bool = True):
        super().__init__()
        self.remote = remote
        self.new_version_available = False
        self.new_version_description = None
        self.ctx = "APP-UPDATE-CHECK"

    def run(self):
        """Executes the update check and notifies the UI of the result."""
        log("Checking for application updates...", log_level=1, context=self.ctx)
        self.check_for_update()
        self.app_update.emit(self.new_version_available)

    def check_for_update(self):
        """Orchestrates version comparison and state updates."""
        change_cursor('busy')
        current_version = config.APP_VERSION
        try:
            info = get_changelog()
            if info:
                latest_version, version_description = info
                # Determine if remote version is strictly newer
                newer_version = compare_versions(current_version, latest_version)
                
                if not newer_version or newer_version == current_version:
                    self.new_version_available = False
                else:
                    log(f"New version found: {latest_version} (Current: {current_version})", 
                        log_level=1, context=self.ctx)
                    self.new_version_available = True
                
                config.APP_LATEST_VERSION = latest_version
                self.new_version_description = version_description
            else:
                log("Failed to retrieve remote version manifest", log_level=2, context=self.ctx)
                self.new_version_available = False
        
        except Exception as e:
            log(f"Update verification process failed: {e}", log_level=3, context=self.ctx)
            self.new_version_available = False
        
        finally:
            change_cursor('normal')
            save_setting()


class YtDlpUpdateThread(QThread):
    """
    Specialized thread for self-updating the yt-dlp binary or library.
    
    Invokes the internal update mechanism and signals the UI with the 
    result of the operation.
    """
    update_finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = "YTDL-BINARY-UPGRADE"

    def run(self):
        """Executes the yt-dlp upgrade process and reports status."""
        log("Initiating yt-dlp binary update check...", log_level=1, context=self.ctx)
        success, message = update_yt_dlp()
        
        if success:
            log(f"yt-dlp update successful: {message}", log_level=1, context=self.ctx)
        else:
            log(f"yt-dlp update failed or not required: {message}", log_level=2, context=self.ctx)
            
        self.update_finished.emit(success, message)


class UpdateThread(QThread):
    """
    General purpose update execution thread.
    
    Typically used for downloading and applying full application patches 
    or secondary dependencies.
    """
    update_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = "CORE-UPDATE-EXEC"

    def run(self):
        """Triggers the global update routine."""
        log("Executing core application update...", log_level=1, context=self.ctx)
        try:
            update()
            if config.confirm_update:
                log("Update logic complete; awaiting user confirmation for restart.", 
                    log_level=1, context=self.ctx)
                self.update_finished.emit()
        except Exception as e:
            log(f"Core update execution failed: {e}", log_level=3, context=self.ctx)




class DownloadManagerWindow(QMainWindow):
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
        threading.Thread(target=self.plugin_mgr.load_all, daemon=True, name="plugin-loader").start()
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







        


        
    # ── UI Updates & Status ──────────────────────────────────────────────────

    def update_datetime(self):
        """Refreshes the global status bar clock with the current system time."""
        current = QDateTime.currentDateTime()
        widgets.datetime_label.setText(current.toString("yyyy-MM-dd HH:mm:ss"))

    def update_summary(self):
        """
        Recalculates daily statistics for the dashboard info card.
        Aggregates total initiated and successfully finalized downloads for the current day.
        """
        try:
            total_today, completed_today = get_today_download_stats(self.d_list)
            widgets.lbl_summary.setText(f"{total_today} downloads\n{completed_today} completed")
        except Exception as e:
            log(f"Dashboard summary update failed: {e}", log_level=3, context=self.ctx)

    def on_sort_changed(self, text):
        """
        Reorders the main download list based on user-selected criteria.
        Supported keys: Time (Last Activity), Name (A-Z), Status, and Size.
        """
        try:
            key = (text or '').strip().lower()
            log(f"Re-sorting download table by criteria: {key}", log_level=1, context=self.ctx)
            
            if key == 'time':
                def k(d):
                    l = getattr(d, 'last_try_date', None)
                    if not l: return datetime.min
                    try: return datetime.fromisoformat(l)
                    except Exception:
                        try: return datetime.strptime(l, "%Y-%m-%d %H:%M:%S")
                        except Exception: return datetime.min
                self.d_list.sort(key=k, reverse=True)
            elif key == 'name':
                self.d_list.sort(key=lambda d: (d.name or '').lower())
            elif key == 'status':
                self.d_list.sort(key=lambda d: str(getattr(d, 'status', '')).lower())
            elif key == 'size':
                self.d_list.sort(key=lambda d: getattr(d, 'total_size', getattr(d, 'size', 0)) or 0, reverse=True)
            
            self.populate_table()
        except Exception as e:
            log(f"Sorting operation failed: {e}", log_level=3, context=self.ctx)

    # ── Dialog Navigation ────────────────────────────────────────────────────

    def show_add_dialog(self):
        """
        Prepares and displays the primary Add Download dialog.
        Synchronizes folder paths, queues, and categories before rendering.
        """
        widgets_add_download.save_to_edit.setText(config.download_folder)
        self.queue_combo()
        self.category_list(language=config.lang)
        self.ui_add_download.setStyleSheet(get_stylesheet(self.current_theme))
        self.ui_add_download.show()
        self.ui_add_download.raise_()
        if getattr(self, '_is_playlist_mode', False) and getattr(self, 'playlist', None):
            widgets_add_download.download_btn.setText(self.tr("Start Playlist"))

    def show_add_dialog_only(self):
        """
        Renders the Add Download dialog as a standalone window.
        Specifically utilized for browser-intercepted links when the main UI is minimized.
        """
        log("Intercepting remote download request; spawning standalone dialog", 
            log_level=1, context=self.ctx)
        widgets_add_download.save_to_edit.setText(config.download_folder)
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
    

    # ── File Interaction & Menu Logic ────────────────────────────────────────

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
        widgets.open_file_menu.clear()

        # Verify file existence on disk to avoid 'ghost' entries
        completed_dl = [
            d for d in self.d_list 
            if d.status == "completed" and os.path.exists(d.target_file)
        ]

        if not completed_dl:
            no_files = QAction(self.tr("No completed downloads"), self)
            no_files.setEnabled(False)
            widgets.open_file_menu.addAction(no_files)
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
        action_widget = QWidgetAction(widgets.open_file_menu)
        action_widget.setDefaultWidget(list_widget)
        widgets.open_file_menu.addAction(action_widget)

    # ── Application & External Resources ─────────────────────────────────────

    

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

    def exit_app(self):
        """Terminates the application and triggers clean shutdown logic."""
        log("Initiating application shutdown sequence", log_level=1, context=self.ctx)
        QtWidgets.QApplication.quit()

    # Resource mapping for browser-side integration
    EXTENSION_URLS = {
        "Chrome": "https://chrome.google.com/webstore/detail/CHROME_EXTENSION_ID", 
        "Firefox": "https://addons.mozilla.org/en-US/firefox/addon/omnipull-downloader/",
        "Edge": "https://microsoftedge.microsoft.com/addons/detail/mkhncokjlhefbbnjlgmnifmgejdclbhj"
    }

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

    # ── Terminal Engine & Logic ──────────────────────────────────────────────

    def toggle_terminal_view(self, checked: bool):
        """Switches the main view between the Download Table and the yt-dlp Terminal."""
        if checked:
            widgets.stack.setCurrentWidget(widgets.terminal_page)
            widgets.btn_terminal.setIcon(QIcon(":/icons/database.png"))
            log("Switched to Embedded Terminal view", log_level=1, context=self.ctx)
        else:
            widgets.stack.setCurrentWidget(widgets.downloads_page)
            widgets.btn_terminal.setIcon(QIcon(":/icons/terminal.png"))

    def _terminal_exec(self):
        """
        Parses and executes user input from the terminal.
        Handles internal commands (clear, abort) or delegates to the yt-dlp subprocess.
        """
        cmd = widgets.terminal_input.text().strip()
        if not cmd:
            return

        if getattr(self, "_terminal_busy", False):
            log("Terminal is currently busy; ignoring new command input", 
                log_level=2, context=self.ctx)
            return

        widgets.terminal_output.appendPlainText(f"> {cmd}")
        widgets.terminal_input.clear()

        # Handle built-in shell commands first
        if self._handle_internal_command(cmd):
            return

        # Pre-execution check for active downloads
        if any(d.status == config.Status.downloading for d in self.d_list):
            # 1. Create instance for full translation support
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setWindowTitle(self.tr("System Busy"))
            msg_box.setText(self.tr(
                "Downloads are currently running. "
                "Pause them to proceed with terminal execution?"
            ))

            # 2. Add and translate buttons manually
            yes_btn = msg_box.addButton(QMessageBox.Yes)
            no_btn = msg_box.addButton(QMessageBox.No)
            
            yes_btn.setText(self.tr("Yes"))
            no_btn.setText(self.tr("No"))
            
            msg_box.setDefaultButton(no_btn)
            msg_box.exec()
            # 3. Check selection
            if msg_box.clickedButton() != yes_btn:
                return

        self._terminal_busy = True
        self.pause_all_downloads()

        log(f"Spawning shell subprocess for command: {cmd}", log_level=1, context=self.ctx)
        threading.Thread(
            target=self._run_ytdlp_command,
            args=(cmd,),
            daemon=True
        ).start()

        widgets.terminal_input.history.append(cmd)
        widgets.terminal_input.history_index = len(widgets.terminal_input.history)

    def pause_all_downloads(self):
        """Forcibly transitions all active or pending downloads to a cancelled state."""
        active_downloads = [
            d for d in self.d_list
            if d.status in (config.Status.downloading, config.Status.pending, config.Status.merging_audio)
        ]
        if active_downloads:
            log(f"Suspending {len(active_downloads)} active downloads for terminal priority", 
                log_level=1, context=self.ctx)
            for d in active_downloads:
                if d.status == config.Status.downloading:
                    d.status = config.Status.cancelled
            self.pending.clear()

    def _run_ytdlp_command(self, cmd: str):
        """
        Low-level subprocess handler for yt-dlp CLI execution.
        Captures stdout/stderr in real-time and pipes it to the terminal output.
        """
        try:
            DEFAULT_FLAGS = ["--newline", "--progress", "--no-color"]
            exe = config.yt_dlp_actual_path 
            args = [exe] + DEFAULT_FLAGS + shlex.split(cmd)

            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            self._current_proc = proc

            for line in proc.stdout:
                config.main_window_q.put(("log", line.rstrip()))

            proc.wait()
            log(f"Subprocess finished with exit code: {proc.returncode}", 
                log_level=1, context=self.ctx)

        except Exception as e:
            log(f"Shell execution failed: {e}", log_level=3, context=self.ctx)
        finally:
            self._terminal_busy = False

    def load_ytdlp_options(self):
        """Returns a list of supported yt-dlp flags for terminal autocompletion."""
        return [
            "--help", "--version", "--update", "-f", "--format", "-o", "--output",
            "--merge-output-format", "--extract-audio", "--audio-format",
            "--audio-quality", "--write-thumbnail", "--embed-metadata",
            "--yes-playlist", "--no-playlist", "--playlist-items", "--cookies",
            "--proxy", "--limit-rate", "--concurrent-fragments",
        ]

    def _handle_internal_command(self, cmd: str) -> bool:
        """Processes built-in terminal shortcuts without spawning a subprocess."""
        cmd = cmd.lower().strip()

        if cmd in {"help", "?"}:
            help_text = [
                "Terminal Help:",
                "  clear    : Wipe terminal screen",
                "  history  : View previous commands",
                "  abort    : Kill active yt-dlp process",
                "  [other]  : Passed to yt-dlp directly"
            ]
            for line in help_text: config.main_window_q.put(("log", line))
            return True

        if cmd == "clear":
            widgets.terminal_output.clear()
            return True

        if cmd == "history":
            for i, h in enumerate(widgets.terminal_input.history, 1):
                config.main_window_q.put(("log", f"{i}: {h}"))
            return True

        if cmd == "abort":
            if self._current_proc:
                self._current_proc.terminate()
                log("Manual abortion of yt-dlp process requested by user", 
                    log_level=1, context=self.ctx)
            return True

        return False


    
    # ── Theme & Visual Engine ────────────────────────────────────────────────

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
            widgets.action_theme_dark.setChecked(True)
            widgets.action_theme_light.setChecked(False)
        else:
            self.current_theme = "light"
            widgets.action_theme_light.setChecked(True)
            widgets.action_theme_dark.setChecked(False)

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
        is_visible = widgets_add_download.details_panel.isVisible()
        widgets_add_download.details_panel.setVisible(not is_visible)

    # region Menu bar Actions


    # region Queue Handling

    # ── Queue Management & Scheduling ────────────────────────────────────────

    def on_selection_queue(self):
        # It's safer to check the index or the text
        current_text = widgets_add_download.queue_combo.currentText()
        btn = widgets_add_download.download_btn
        
        if current_text != self.tr("None") and current_text != "None": 
            btn.setText(self.tr("Add to Queue"))
            
        else:
            btn.setText(self.tr("Start Download"))
            

    
    def on_import_file_clicked(self):
        """Triggered when the user selects a text file for batch import."""
        selected_queue = widgets_add_download.queue_combo.currentText()

    
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
        widgets_add_download.url_edit.blockSignals(True)
        widgets_add_download.url_edit.setText(file_path)
        widgets_add_download.url_edit.blockSignals(False)

        # Fix 1 — clear stale single-URL metadata before batch mode takes over
        widgets_add_download.filename_edit.clear()
        widgets_add_download.resolution_combo.clear()
        widgets_add_download.thumbnail_label.clear()
        widgets_add_download.thumbnail_label.setText("")
    
        widgets_add_download.lbl_size_value.setText(self.tr("Calculating…"))
        widgets_add_download.url_progress.setRange(0, 0)   # indeterminate
        widgets_add_download.url_progress.show()
        widgets_add_download.download_btn.setText(self.tr("Start Download"))
        widgets_add_download.download_btn.setEnabled(False)
    
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
        widgets_add_download.lbl_size_value.setText(
            f"{count} link{'s' if count != 1 else ''} — {size_txt}"
        )


    def start_queue_by_id(self, queue_id):
        """
        Activates a specific download queue and initiates its processing.
        
        Sets the global running state for the queue and synchronizes the 
        QueueDialog UI to reflect the currently active selection.
        """
        log(f"Manual override: Initiating queue process for ID: {queue_id}", 
            log_level=1, context=self.ctx)
            
        self.running_queues[queue_id] = True
        self.ui_queues.current_queue_id = queue_id
        
        # Align the UI list selection with the starting queue
        idx = next((i for i, q in enumerate(self.queues) 
                    if self.get_queue_id(q["name"]) == queue_id), 0)
        self.ui_queues.queue_list.setCurrentRow(idx)
        
        self.ui_queues.start_queue_downloads()


    def _refresh_batch_button_label(self):
        """Update batch download button label when queue selection changes."""
        if not getattr(self, '_is_batch_mode', False):
            return
        count = len(getattr(self, '_batch_items', []))
        if count == 0:
            return
        selected_queue = widgets_add_download.queue_combo.currentText()
        has_queue = selected_queue and selected_queue != "None"
        if has_queue:
            widgets_add_download.download_btn.setText(self.tr(f"Add {count} to Queue"))
        else:
            widgets_add_download.download_btn.setText(self.tr(f"Start {count} Download{'s' if count != 1 else ''}"))
    

    @Slot()
    def _on_batch_finished(self):
        count    = len(self._batch_items)
        size_txt = (
            size_format(self._batch_total_size)
            if self._batch_total_size > 0
            else self.tr("Unknown size")
        )
        widgets_add_download.lbl_size_value.setText(
            f"{count} link{'s' if count != 1 else ''} — {size_txt}"
        )
        widgets_add_download.url_progress.setRange(0, 100)
        widgets_add_download.url_progress.setValue(100)
        QTimer.singleShot(1500, widgets_add_download.url_progress.hide)

        # Label depends on whether a queue is selected
        selected_queue = widgets_add_download.queue_combo.currentText()
        has_queue = selected_queue and selected_queue != "None"

        if has_queue:
            label = self.tr(f"Add {count} to Queue") if count else self.tr("Start Download")
        else:
            label = self.tr(f"Start {count} Download{'s' if count != 1 else ''}") if count else self.tr("Start Download")

        widgets_add_download.download_btn.setText(label)
        widgets_add_download.download_btn.setEnabled(True)
        log(f"[BatchImport] UI finalised – {count} items ready", log_level=1)
    
    @Slot(str)
    def _on_batch_failed(self, reason):
        self._batch_ui_active = False
        self._is_batch_mode   = False
        widgets_add_download.url_progress.setRange(0, 100)
        widgets_add_download.url_progress.setValue(0)
        widgets_add_download.url_progress.hide()
        widgets_add_download.lbl_size_value.setText(self.tr("Import failed"))
        widgets_add_download.download_btn.setText(self.tr("Start Download"))
        widgets_add_download.download_btn.setEnabled(True)
        show_critical(self.ui_add_download, self.tr("Batch Import Error"), reason)

    def check_scheduled_queues(self):
        """
        Evaluates queue schedules against the current system time.
        
        Iterates through registered queues to find matches for the current 
        HH:mm. Includes a safety check (last_schedule_check) to prevent 
        multiple triggers within the same minute.
        """
        now = QTime.currentTime()

        for q in self.queues:
            queue_id = self.get_queue_id(q["name"])
            schedule = q.get("schedule")

            # Skip if no schedule is set or if the queue is already active
            if not schedule or self.running_queues.get(queue_id, False):
                continue

            hour, minute = schedule
            if now.hour() == hour and now.minute() == minute:
                last_time = self.last_schedule_check.get(queue_id)

                # Prevent re-triggering if already activated in the current minute
                if last_time and last_time.hour() == hour and last_time.minute() == minute:
                    continue

                # Verify there are eligible items before starting
                items = [d for d in self.d_list 
                    if d.in_queue and d.queue_id == queue_id 
                        and d.status == config.Status.queued]
                         
                if items:
                    log(f"Schedule Match: Automatically starting queue '{q['name']}'", 
                        log_level=1, context=self.ctx)
                        
                    self.start_queue_by_id(queue_id)
                    self.last_schedule_check[queue_id] = now
                    
                    # Localized user notification
                    csq1, csq2 = self.tr('Queue'), self.tr('has started automatically')
                    show_information(
                        self, 
                        title=self.tr('Queue Scheduler'), 
                        inform='', 
                        msg=f"{csq1} '{q['name']}' {csq2}"
                    )

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

        widgets_add_download.queue_combo.clear()
        widgets_add_download.queue_combo.addItem("None")
        
        for queue in self.queues:
            name = queue.get("name")
            if name:
                widgets_add_download.queue_combo.addItem(name)

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


    # endregion

    # region Category Handling

    
    # ── Category & Classification Logic ──────────────────────────────────────

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

        widgets.category_list.clear()
        default_categories = list(CATEGORY_TRANSLATIONS.keys())

        # 1. Add localized system categories
        for category in default_categories:
            item = QtWidgets.QListWidgetItem()
            # UserRole stores the non-translated ID for internal logic
            item.setData(Qt.UserRole, category)
            
            translated_text = CATEGORY_TRANSLATIONS.get(category, {}).get(language, category)
            item.setText(translated_text)
            widgets.category_list.addItem(item)

        # 2. Add custom user-defined categories
        for cat in self.categories:
            name = cat.get("name")
            if name and name not in default_categories:
                item = QtWidgets.QListWidgetItem(name)
                item.setData(Qt.UserRole, name)
                widgets.category_list.addItem(item)

        # Default selection to 'All' or first available
        if widgets.category_list.count() > 0:
            widgets.category_list.setCurrentRow(0)

    def update_category_combo(self):
        """
        Synchronizes the Add Download dialog's category selection box.
        
        Combines the standard industrial classifications with active 
        user categories to ensure the 'Save To' metadata is accurate 
        during task initiation.
        """
        self.categories = self.settings_manager.categories
        widgets_add_download.category_combo.clear()
        
        # Standard system-level classification keys
        default_categories = ["General", "Compressed", "Documents", "Music", "Video", "Programs"]
        
        custom_names = [c['name'] for c in self.categories if 'name' in c]
        widgets_add_download.category_combo.addItems(default_categories + custom_names)

    def update_category_list(self):
        """
        Trigger-point for refreshing the category UI.
        
        Typically called after a settings change or language switch 
        to force a redraw of the category sidebar.
        """
        log(f"Refreshing category taxonomy (Language: {config.lang})", 
            log_level=2, context=self.ctx)
        self.category_list(language=config.lang)

    # endregion


    # region Language Department

    # ── Localization & Internationalization Engine ───────────────────────────


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
        widgets.file_menu.setTitle(self.tr('&File'))
        widgets.exit_action.setText(self.tr('&Exit'))
        widgets.open_file_menu.setTitle(self.tr('Open'))
        widgets.add_action.setText(self.tr("Add new download"))
        
        widgets.downloads_menu.setTitle(self.tr('&Downloads'))
        # Using specific indices for menu stability
        actions = widgets.downloads_menu.actions()
        if len(actions) >= 3:
            actions[0].setText(self.tr('Resume All'))
            actions[1].setText(self.tr('Stop All'))
            actions[2].setText(self.tr('Delete All'))
            
        widgets.view_menu.setTitle(self.tr('&View'))
        widgets.theme_menu.setTitle(self.tr('Theme'))
        widgets.action_theme_dark.setText(self.tr('Dark'))
        widgets.action_theme_light.setText(self.tr('Light'))
        
        widgets.tools_menu.setTitle(self.tr("&Tools"))
        widgets.scheduler_action.setText(self.tr("Scheduler"))
        widgets.category_action.setText(self.tr("Categories"))
        widgets.queue_action.setText(self.tr("Queues"))
        widgets.settings_action.setText(self.tr('Settings'))
        widgets.install_deno_action.setText(self.tr('Install deno'))
        widgets.install_ffmpeg_action.setText(self.tr('Install ffmpeg'))
        widgets.install_ytdlp_action.setText(self.tr('Install yt-dlp'))
        widgets.marketplace_action.setText(self.tr('Marketplace'))
        
        widgets.browser_ext_menu.setTitle(self.tr('Browser Extension'))
        
        widgets.help_menu.setTitle(self.tr('&Help'))
        h_actions = widgets.help_menu.actions()
        if len(h_actions) >= 6:
            h_actions[1].setText(self.tr('About'))
            h_actions[2].setText(self.tr('Help'))
            h_actions[3].setText(self.tr('Check for Updates'))
            h_actions[4].setText(self.tr("Report Issues"))
            h_actions[5].setText(self.tr('WhatsNew'))

        # ── Dashboard & Toolbars ─────────────────────────────────────────────
        widgets.btn_add.setText(self.tr("Add"))
        widgets.btn_resume.setText(self.tr("Resume"))
        widgets.btn_pause.setText(self.tr("Pause"))
        widgets.btn_stop_all.setText(self.tr("Stop All"))
        widgets.btn_delete_all.setText(self.tr("Delete All"))
        widgets.btn_scheduler.setText(self.tr("Scheduler"))
        widgets.btn_refresh.setText(self.tr("Refresh"))
        widgets.btn_terminal.setText(self.tr("Terminal"))
        widgets.btn_resume_all.setText(self.tr("Resume All"))
        widgets.btn_settings.setText(self.tr("Settings"))

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
        widgets.table.setHorizontalHeaderLabels(translated_headers)

        # ── Static Labels & Tooltips ────────────────────────────────────────
        widgets.title_label.setText(self.tr("Downloads"))
        widgets.sort_by.setText(self.tr("Sort by:"))
        widgets.t_label.setText(self.tr("Terminal"))
        widgets.log_clear_btn.setText(self.tr("Clear"))
        widgets.log_level_label.setText(self.tr("Log Level:"))
        
        widgets.lbl_http_status.setToolTip(self.tr("Last HTTP response status"))
        widgets.lbl_speed.setToolTip(self.tr("Current total download speed"))
        widgets.lbl_title.setText(self.tr("Today"))
        widgets.lbl_summary.setText(self.tr("downloads\n completed"))
        widgets.dock.setWindowTitle(self.tr("Categories"))
        widgets.search_label.setText(self.tr("   Search: "))
        
        widgets.terminal_input.setPlaceholderText(self.tr(
            "Enter command here... You can start with helpful commands like 'help' or 'yt-dlp --help'."
        ))
        widgets.filter_edit.setPlaceholderText(self.tr("Search downloads..."))

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
        for i in range(widgets.category_list.count()):
            item = widgets.category_list.item(i)
            if item:
                english_key = item.data(Qt.UserRole)
                translated_text = CATEGORY_TRANSLATIONS.get(english_key, {}).get(config.lang, english_key)
                item.setText(translated_text)

    



    # region logs out & close

    # ── Application Lifecycle & Shutdown ─────────────────────────────────────

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

    # ── Miscellaneous Controls ───────────────────────────────────────────────

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
        widgets.terminal_output.clear()
    
    def set_log(self):
        """Updates the application logging verbosity threshold."""
        config.log_level = int(widgets.log_level_combo.currentText())
        log(f"System log verbosity updated to level: {config.log_level}", 
            log_level=1, context=self.ctx)
        self.settings_manager.save_settings()

    # region Folder & Filename

    def open_folder_dialog(self):
        """Open a dialog to select a folder and update the line edit."""
        # Open a folder selection dialog
        folder_path = QFileDialog.getExistingDirectory(self, "Select Download Folder")

        if folder_path:
            widgets_add_download.save_to_edit.setText(folder_path)
            config.download_folder = os.path.abspath(folder_path)
        
        self.ui_add_download.activateWindow()
        self.ui_add_download.raise_()
            
    

    def on_filename_changed(self, text: str) -> str:
        """Handle manual changes to the filename line edit."""

        # Only update the download item if the change was made manually
        if not self.filename_set_by_program:
            self.d.name = text

    
    # endregion

    # region Url Processing

    # ── URL Detection & Interception ─────────────────────────────────────────

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

    # ── URL Sanitization & Analysis ──────────────────────────────────────────

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

    # ── Fast URL Processing (Hybrid Logic) ───────────────────────────────────

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
        widgets_add_download.filename_edit.setText(self.d.name)
        widgets_add_download.lbl_size_value.setText(
            size_format(self.d.size) if self.d.size else "Unknown"
        )
        
        self.category_checker(self.d)
        widgets_add_download.url_progress.setRange(0, 100)
        self.reset_to_default_thumbnail()
        widgets_add_download.url_progress.setValue(100)
        
        log(f"Fast URL resolution success. Size: {size_format(self.d.size)}", 
            log_level=1, context=ctx)
        return True



    # ── URL Lifecycle & Validation ───────────────────────────────────────────

    def url_text_change(self, referrer=None, trusted_size=None, trusted_name=None):
        """
        Orchestrates the metadata extraction sequence when the URL input changes.
        
        Logic Flow:
        1. Sanitizes the URL based on site sensitivity (token preservation).
        2. Validates external dependencies (e.g., Deno for YouTube JS challenges).
        3. Attempts the Rust 'Fast Path' for immediate metadata resolution.
        4. Falls back to the yt-dlp 'Deep Path' via a debounced timer if needed.
        """
        url = widgets_add_download.url_edit.text().strip()
        ctx = "URL-PROC"

        # 1. Sanitization Logic (Sensitive Site Token Preservation)
        sensitive_sites = ["licdn.com", "linkedin.com", "kwik.cx", "instagram.com"]
        is_sensitive = any(site in url.lower() for site in sensitive_sites)

        if config.ytdlp_config['no_playlist'] and not is_sensitive:
            url = self.clean_url(url)
        
        if url == self.d.url:
            return

        # UI State: Transition to 'Processing' mode
        widgets_add_download.url_progress.show()
        widgets_add_download.url_progress.setRange(0, 0)  # Indeterminate state
        self._show_cancel_button()
        
        self._url_processing = True
        self._processing_cancel_requested = False
        widgets_add_download.thumbnail_label.clear()
        widgets_add_download.resolution_combo.clear()

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
        widgets_add_download.url_progress.show()
        progress_steps = [10, 50, 100]  
        for step in progress_steps:
            time.sleep(1) 
            self.update_progress_bar_value(step)  
    
    def update_progress_bar_value(self, value):
        """Update the progress bar value in the Add Download dialog."""
        widgets_add_download.url_progress.setValue(value)

        #  where url_status_label = ⏳
    

    def update_progress_bar(self):
        """Update the progress bar based on URL processing."""
        Thread(target=self.process_url, daemon=True).start()


    # ── User Intervention & Cancellation ─────────────────────────────────────

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
 
        widgets_add_download.url_progress.hide()
        self.d.url = ""
        log("URL processing sequence successfully aborted.", log_level=1, context="URL-PROC")

    def on_cancel_close_clicked(self):
        """Toggles button functionality between 'Cancel Task' and 'Close Window'."""
        if self._url_processing:
            self._cancel_url_processing()
        else:
            widgets_add_download.close()

    # ── Internal State Management ────────────────────────────────────────────

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
            widgets_add_download.download_btn.setText(self.tr("Start Download"))
        except Exception:
            pass

    def retry(self):
        """Forces a re-processing of the current URL string."""
        log("Manual extraction retry initiated by user", log_level=1, context="URL-PROC")
        self.d.url = ''
        self._url_processing = True
        self._processing_cancel_requested = False
        self._show_cancel_button()
        widgets_add_download.url_progress.show()
        widgets_add_download.url_progress.setRange(0, 0)
        self.url_text_change()

    def _show_cancel_button(self):
        """Updates the Add Download dialog to show the 'Cancel' state."""
        widgets_add_download.cancel_close_btn.setText(self.tr("Cancel"))
        widgets_add_download.cancel_close_btn.setToolTip(self.tr("Cancel URL processing"))

    def _show_close_button(self):
        """Updates the Add Download dialog to show the 'Close' state."""
        widgets_add_download.cancel_close_btn.setText(self.tr("Close"))
        widgets_add_download.cancel_close_btn.setToolTip("")

    def refresh_headers(self, url):
        """Initiates a header-only network request to probe file metadata."""
        if self.d.url != '':
            Thread(target=self.get_header, args=[url], daemon=True).start()

    
    
    # ── Download Engine Selection ───────────────────────────────────────────

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
            combo = widgets_add_download.engine_combo
            idx = combo.findText(engine_display)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        except Exception:
            pass

    # ── Metadata Classification ──────────────────────────────────────────────

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
        
        widgets_add_download.category_combo.setCurrentText(d.category)
        self.category_onChoice(d.category)

    # ── Thread Callbacks & Finalization ──────────────────────────────────────

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
                widgets_add_download.download_btn.setEnabled(True)

            log(f"Spawning Deep Extraction thread for: {url[:40]}...", 
                log_level=1, context="URL-EXTRACT")
            
            self._processing_cancel_requested = False
            self.yt_thread = YouTubeThread(url, stop_event=threading.Event())
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
        widgets_add_download.url_progress.setValue(100)

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
            widgets_add_download.download_btn.setText(self.tr("Start Playlist"))
            self._is_playlist_mode = True
            widgets_add_download.advance_btn.setEnabled(True)

        # ── Handle Single Video Logic ──
        elif isinstance(result, Video):
            log(f"Single video resolved: {result.name}", log_level=1, context=ctx)
            self.playlist = [result]
            self.d = result
            self.d.status_code = 200
            self._is_playlist_mode = False
            if not self.d.ext:
                self.d.ext = self.extract_ext_from_url(self.d.url, self.d)
            widgets_add_download.advance_btn.setEnabled(True)
        
        else:
            log("Extraction failed to return valid media objects", log_level=3, context=ctx)
            self.update_http_status(0)
            return

        # ── Post-Extraction UI ──
        self.update_http_status(200)
        self.update_pl_menu()
        self.update_stream_menu()
        
        if config.show_thumbnail and hasattr(self.d, 'thumbnail_url'):
            Thread(target=self.d.get_thumbnail, daemon=True).start()
            self.show_thumbnail(thumbnail=self.d.thumbnail_url)

        QTimer.singleShot(1000, lambda: widgets_add_download.url_progress.hide())

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
        dlg.exec()


    
    # region GUI Updates


    # ── GUI Synchronization Engine ───────────────────────────────────────────

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
                    
                    # # 2. Update the UI table
                    # self.populate_table() 
                    
                    
                    # 3. Save the clean list
                    self.settings_manager.save_d_list(self.d_list)
                    log(f"Cleaned up internal dependency task (ID: {item_id})")

    
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

    def check_for_gui_updates(self):
        """
        Emits the accumulated pending updates to the GUI signal handler.
        
        By bundling updates into a single signal, we reduce 'GUI jitter' 
        and lower CPU overhead compared to updating individual labels.
        """
        if self.pending_updates:
            self.update_gui_signal.emit(self.pending_updates)
            self.pending_updates.clear()

    # ── Metadata Visualizers ─────────────────────────────────────────────────

    def update_http_status(self, code: int):
        """
        Renders a color-coded HTML status indicator for network responses.
        
        Green: Success (2xx) | Orange: Redirect (3xx) | Red: Error (4xx/5xx)
        """
        if code == 0:
            widgets.lbl_http_status.setText('<span style="color:gray;">—</span>')
            return

        status_map = {
            2: ("green", "OK"),
            3: ("orange", "Redirect"),
            4: ("red", "Client Error"),
            5: ("darkred", "Server Error")
        }
        
        color, text = status_map.get(code // 100, ("gray", "Unknown"))
        widgets.lbl_http_status.setText(f'<span style="color:{color};">{code} {text}</span>')

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

    

    # endregion

    # region Add-ons Check

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

        
    

    
    # region Toolbar buttons

    

    # ── Media URL Validation & Refresh ───────────────────────────────────────

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

    # ── Toolbar Actions: Resume ──────────────────────────────────────────────

    

    def resume_btn(self):
        """
        Resume paused, queued, or errored downloads.
        Ensures the progress window is re-initialized to capture fresh signals.
        """
        ctx = "ENGINE-RESUME"
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self, self.tr("Error"), self.tr("No download item selected"))
            return

        # Map UI row to data list index
        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        if d.status not in (config.Status.cancelled, config.Status.queued, config.Status.error):
            return

        # ── 1. Engine Specific Pre-Processing ──
        
        if d.engine == "aria2c":
            # YouTube Link Refresh Logic
            is_yt = "youtube.com" in (d.original_url or d.url) or "googlevideo.com" in (d.url or "")
            if is_yt and d.type in ("dash", "normal"):
                if self._youtube_url_expired(getattr(d, "eff_url", d.url)) or \
                   (d.audio_url and self._youtube_url_expired(d.audio_url)):
                    
                    log(f"Refreshing expired tokens for: {d.name}", log_level=1, context=ctx)
                    try:
                        fresh_d = self.get_video_info(d.original_url or d.url)
                        # Sync volatile fields
                        attrs = ['url','audio_url','audio_file','name','target_file',
                                 'temp_file','vid_info','eff_url','protocol','type']
                        for attr in attrs:
                            setattr(d, attr, getattr(fresh_d, attr, getattr(d, attr)))

                        # Purge .aria2 control files to force a clean stream restart
                        for f in [d.temp_file, d.temp_file + '.aria2', d.audio_file, 
                                  (d.audio_file + '.aria2' if d.audio_file else None)]:
                            if f and os.path.exists(f): os.remove(f)
                        d.aria_gid = None
                    except Exception as e:
                        log(f"Refresh failed: {e}", log_level=3, context=ctx)
                        return
            
            # Verify existing GID with aria2 daemon
            if getattr(d, "aria_gid", None):
                try:
                    aria2 = aria2c_manager.get_api()
                    dl = aria2.get_download(d.aria_gid)
                    if not dl or getattr(dl, "status", "") == "removed":
                        d.aria_gid = None
                except Exception:
                    d.aria_gid = None

        elif d.engine == "yt-dlp":
            d.status = config.Status.downloading

        # ── 2. Progress Window Initialization (The Fix) ──
        
        # We always recreate or re-show the window here to ensure it's 
        # correctly bound to the DownloadItem 'd' before the thread starts.
        if config.show_download_window:
            # If a window exists but is frozen, close it to reset the signal bus
            if d.id in self.download_windows:
                try:
                    self.download_windows[d.id].close()
                    self.download_windows[d.id].deleteLater()
                except Exception:
                    pass
            
            # Create a fresh dialog instance
            self.download_windows[d.id] = DownloadProgressDialog(d)
            self.download_windows[d.id].show()
            log(f"Progress window re-initialized for: {d.name}", log_level=1, context=ctx)

        # ── 3. Lifecycle Finalization & Thread Spawn ──
        
        try:
            d.last_try_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.settings_manager.save_d_list(self.d_list)
            self.update_summary()
        except Exception:
            pass

        # Use the specific engine logic or fallback to PyCURL
        if d.engine in ("aria2c", "yt-dlp"):
            Thread(target=brain, args=(d,), daemon=True).start()
            log(f"Engine ({d.engine}) resumed: {d.name}", log_level=1, context=ctx)
        else:
            # Native PyCURL / Fallback path
            self.start_download(d, silent=True)

        widgets.btn_pause.setEnabled(True)
        widgets.btn_resume.setEnabled(False)



    # ── Task Suspension (Pause) ──────────────────────────────────────────────

    def pause_btn(self):
        """
        Suspends the currently selected download task.
        
        For aria2c, this initiates a 'Family Pause,' which halts the parent GID 
        and all associated segments/metadata downloads. For yt-dlp/Native, 
        it transitions the status to 'Cancelled' to break the worker loop.
        """
        ctx = "ENGINE-PAUSE"
        selected_row = widgets.table.currentRow()
        
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self, self.tr("Action Required"), self.tr("No download item selected"))
            return

        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        if d.status == config.Status.completed:
            return

        # ── Engine Path: aria2c ──
        if d.engine == "aria2c" and getattr(d, "aria_gid", None):
            try:
                log(f"Requesting suspension for aria2c family: {d.name}", 
                    log_level=1, context=ctx)
                
                # Attempt to pause the entire download family (siblings/children)
                paused = aria2c_manager.pause_family(d.aria_gid)
                
                target_status = (config.Status.queued if getattr(d, "in_queue", False)
                     else config.Status.cancelled)
                if paused:
                    d.status = target_status
                    log(f"Aria2c session successfully suspended for: {d.name}",
                        log_level=1, context=ctx)
                else:
                    # Fallback: Individual GID pause
                    aria2 = aria2c_manager.get_api()
                    dl = aria2.get_download(d.aria_gid)
                    if dl: dl.pause()
                    d.status = target_status

                aria2c_manager.save_session_only()

            except Exception as e:
                log(f"Aria2c suspension failed: {e}", log_level=3, context=ctx)
                d.status = config.Status.error

        # ── Engine Path: Native / yt-dlp ──
        else:
            if d.status in (config.Status.downloading, config.Status.pending):
                log(f"Halting native/yt-dlp worker for: {d.name}",
                    log_level=1, context=ctx)
                if d.status == config.Status.pending:
                    self.pending.pop(d.id, None)
                # If the item belongs to a queue, return it to queued state so
                # the queue can restart it cleanly.  Otherwise mark cancelled.
                if getattr(d, "in_queue", False):
                    d.status = config.Status.queued
                    log(f"Queued item paused → returned to Status.queued: {d.name}",
                        log_level=1, context=ctx)
                else:
                    d.status = config.Status.cancelled

        widgets.btn_pause.setEnabled(False)
        widgets.btn_resume.setEnabled(True)
        self.settings_manager.save_d_list(self.d_list)
        self.populate_table()

    # ── Task Deletion & Disk Cleanup ─────────────────────────────────────────
    

    def delete_btn(self):
        """
        Removes selected tasks from the application and performs disk cleanup.
        
        Identifies all selected rows, verifies that none are active, and 
        invokes the 'Janitor' process to remove temporary files and 
        metadata from the system.
        """
        ctx = "JANITOR"
        selected_rows = list(set(index.row() for index in widgets.table.selectedIndexes()))

        if not selected_rows:
            return

        if self.active_downloads:
            show_critical(self, self.tr("Active Tasks"), 
                self.tr("Cannot delete items while downloads are active. Please stop all tasks first."))
            return
        
    

        # 1. Create the box
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle(self.tr("Confirm Deletion"))
        msg_box.setText(self.tr("Are you sure you want to delete the selected items and their associated temporary files?"))

        # 2. Add buttons and capture the objects
        # The addButton method returns a QPushButton object
        yes_button = msg_box.addButton(QMessageBox.Yes)
        no_button = msg_box.addButton(QMessageBox.No)

        # 3. Set text directly on the button objects (Standard PySide6 way)
        yes_button.setText(self.tr("Yes"))
        no_button.setText(self.tr("No"))

        msg_box.setDefaultButton(no_button)
        msg_box.exec()

        if msg_box.clickedButton() != yes_button:
            return

        try:
            selected_rows.sort(reverse=True)
            log(f"Initiating batch deletion for {len(selected_rows)} items", 
                log_level=1, context=ctx)
            
            for row in selected_rows:
                d_index = len(self.d_list) - 1 - row
                d = self.d_list.pop(d_index)

                
                # Sync deletion to DB
                self.settings_manager._db.delete_download(d.id)

                widgets.table.removeRow(row)
                
                # Perform disk cleanup (removing .part, .aria2, and temp segments)
                janitor(d)
                log(f"Task and local cache purged: {d.name}", log_level=1, context=ctx)

            widgets.table.clearSelection()
            self.settings_manager.save_d_list(self.d_list)

        except Exception as e:
            log(f"Batch deletion encountered an error: {e}", log_level=3, context=ctx)

    

    def delete_all_downloads(self):
        """
        Performs a global wipe of the download list and all temporary data.
        """
        ctx = "JANITOR"
        if self.active_downloads:
            show_critical(self, self.tr("Active Tasks"), 
                self.tr("Global wipe blocked. Stop active downloads before proceeding."))
            return

        # 1. Create the InputDialog instance
        dialog = QInputDialog(self)
        dialog.setWindowTitle(self.tr("Global Wipe"))
        
        prompt = self.tr("This will delete ALL items and their progress files.\nType 'delete' to confirm.")
        dialog.setLabelText(prompt)

        # 2. Manually set and translate the button text
        # This ensures auto_translate.py picks up "OK" and "Cancel"
        dialog.setOkButtonText(self.tr("OK"))
        dialog.setCancelButtonText(self.tr("Cancel"))
        
        # Optional: Match app's styling 
        # dialog.setStyleSheet(get_msgbox_style('critical')) 

        # 3. Execute and get results
        if dialog.exec():
            text = dialog.textValue()
            
            # Security Check: We keep the keyword 'delete' as a hard-coded string 
            # because it acts as a 'password'/command, but the prompt explaining it is translated.
            if text.strip().lower() != 'delete':
                return

            log("Global wipe initiated. Purging all tasks and temporary data...", 
                log_level=1, context=ctx)

            self.stop_all_downloads()
            self.selected_row_num = None

            # Asynchronous cleanup of physical files
            for d in self.d_list:
                janitor(d)
                # (Note: Using a context manager or a pool might be safer for many threads)
                Thread(target=d.delete_tempfiles, daemon=True).start()
                self.settings_manager._db.delete_download(d.id)

            self.d_list.clear()
            widgets.table.setRowCount(0)
            self.settings_manager.save_d_list(self.d_list)
            log("Global wipe complete. Download list is empty.", log_level=1, context=ctx)
    
    # ── Global Task Management ───────────────────────────────────────────────

    def stop_all_downloads(self):
        """
        Broadly terminates all currently active or transitioning download tasks.
        
        Filters the download list for items in 'downloading', 'pending', or 
        'merging' states. Once confirmed, it transitions their status to 
        'cancelled', effectively breaking the engine worker loops. Scheduled, 
        completed, and queued items remain unaffected.
        """
        ctx = "ENGINE-STOP"
        
        # Identify tasks currently utilizing system resources
        active_downloads = [
            d for d in self.d_list
            if d.status in (config.Status.downloading, 
                config.Status.pending, 
                config.Status.merging_audio
            )
        ]

        if not active_downloads:
            log("Stop All request ignored: No active tasks detected.", 
                log_level=1, context=ctx)
            show_information(
                self, 
                self.tr("Stop All"), 
                self.tr("There are no active downloads to stop.")
            )
            return

       # UI Confirmation Dialog
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle(self.tr("Stop All Downloads?"))
        
        # COMBINED STRING: This is easier for the API to translate naturally
        msg_box.setText(self.tr(
            "Active tasks (Downloading, Pending, or Merging) were detected.\n\n"
            "Do you want to stop all active processes?"
        ))

        # MANUAL BUTTON TRANSLATION
        yes_btn = msg_box.addButton(QMessageBox.Yes)
        no_btn = msg_box.addButton(QMessageBox.No)
        
        yes_btn.setText(self.tr("Yes"))
        no_btn.setText(self.tr("No"))
        
        msg_box.setDefaultButton(no_btn)
        msg_box.setStyleSheet(get_msgbox_style('question'))

        msg_box.exec()

        if msg_box.clickedButton() == yes_btn:
            log(f"Global stop initiated. Terminating {len(active_downloads)} active tasks.", 
                log_level=1, context=ctx)
            
            for d in active_downloads:
                d.status = config.Status.cancelled
            
            # Flush the pending queue to prevent new tasks from starting
            self.pending.clear()

            self.populate_table()
            # self.settings_manager.save_d_list(self.d_list)

            # DATABASE SYNC
            # Since this is a batch update, upsert_many is most efficient
            props_list = [d.get_persistent_properties() for d in active_downloads]
            self.settings_manager._db.upsert_many(props_list)
                
            log("Global stop complete. All active workers have been signaled to halt.", 
                log_level=1, context=ctx)
            
            show_information(
                self, 
                self.tr("Stopped"), 
                self.tr("All active downloads have been successfully cancelled.")
            )

    def _handle_version_status(self):
        latest = getattr(config, "APP_LATEST_VERSION", None)
        current = getattr(config, "APP_VERSION", None)

        cmp = compare_versions_2(latest, current)

        if cmp == 0:
            # up to date
            widgets.lbl_version.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-weight: bold;
                    padding: 5px 10px;
                    border-radius: 10px;
                    background: rgba(76, 175, 80, 0.1);
                }
            """)
            widgets.lbl_version.setToolTip('No new updates')
        elif cmp == 1:
            # newer available
            widgets.lbl_version.setStyleSheet("""
                QLabel {
                    color: #F44336;
                    padding: 6px 16px;
                    font-weight: bold;
                    border-radius: 10px;
                    background: rgba(244, 67, 54, 0.1);  
                }
            """)
            widgets.lbl_version.setToolTip(f'New version available: {latest}')
        elif cmp == -1:
            # current > latest (dev build ahead)
            widgets.lbl_version.setStyleSheet("""
                QLabel {
                    color: #2196F3;
                    padding: 6px 16px;
                    font-weight: bold;
                    border-radius: 10px;
                    background: rgba(33, 150, 243, 0.1);
                }
            """)
            widgets.lbl_version.setToolTip(f'Running a newer/dev build ({current})')
        else:
            # Unknown (None / unparsable)
            widgets.lbl_version.setStyleSheet("""
                QLabel {
                    color: #9E9E9E;
                    font-weight: bold;
                    padding: 5px 10px;
                    border-radius: 10px;
                    background: rgba(158, 158, 158, 0.1);
                }
            """)
            widgets.lbl_version.setToolTip('Unable to determine latest version')


    

    

    # ── Task Scheduling & Automated Retries ──────────────────────────────────

    def check_scheduled(self):
        """
        Monitors the download list for tasks reaching their scheduled execution time.
        
        If a match is found for the current date and second, the download is initiated.
        Includes an automated retry mechanism: if a scheduled task fails, it is 
        re-scheduled for a future time based on user-defined intervals until 
        the maximum retry count is reached.
        """
        ctx = "SCHEDULER"
        now = datetime.now().replace(microsecond=0)
        current_date_str = now.strftime("%Y-%m-%d")
        current_time_str = now.strftime("%H:%M:%S")

        for d in self.d_list:
            if d.status == config.Status.scheduled and getattr(d, "sched", None):
                sched_date, sched_time = d.sched

                if sched_date == current_date_str and sched_time == current_time_str:
                    log(f"Schedule match detected for '{d.name}'. Initiating automated start.", 
                        log_level=1, context=ctx)
                    
                    self.start_download(d, silent=True)

                    # Check if the execution resulted in a failure state
                    if d.status in [config.Status.failed, config.Status.scheduled, 
                                    config.Status.cancelled, config.Status.error]:
                        
                        log(f"Scheduled execution failed for '{d.name}'.", 
                            log_level=3, context=ctx)

                        if config.retry_scheduled_enabled:
                            d.schedule_retries = getattr(d, "schedule_retries", 0)
                            
                            if d.schedule_retries < config.retry_scheduled_max_tries:
                                d.schedule_retries += 1
                                retry_time = now + timedelta(minutes=config.retry_scheduled_interval_mins)
                                
                                d.sched = (
                                    retry_time.strftime("%Y-%m-%d"),
                                    retry_time.strftime("%H:%M:%S")
                                )
                                d.status = config.Status.scheduled
                                
                                log(f"Rescheduling '{d.name}' for {d.sched[0]} {d.sched[1]} (Attempt {d.schedule_retries})", 
                                    log_level=2, context=ctx)
                                
                                show_information(
                                    self, 
                                    title=self.tr("Scheduled Retry"), 
                                    msg=self.tr(f"Task '{d.name}' failed. Retrying at {d.sched[1]} [Attempt {d.schedule_retries}]")
                                )
                            else:
                                d.status = config.Status.cancelled
                                log(f"Task '{d.name}' reached maximum scheduled retries. Aborting.", 
                                    log_level=2, context=ctx)
                        else:
                            d.status = config.Status.cancelled

        self.queue_update("populate_table", None)

    def schedule_all(self):
        """
        Opens a scheduling dialog for all currently 'Pending' or 'Cancelled' tasks.
        
        Bulk updates the selected tasks with the user-provided date/time and 
        transitions them to the 'Scheduled' state to be picked up by the check_scheduled loop.
        """
        # Filter for items that haven't successfully completed yet
        schedulable = [d for d in self.d_list if d.status in (config.Status.pending, config.Status.cancelled)]

        if not schedulable:
            show_information(
                self, 
                self.tr("No Downloads to Schedule"), 
                self.tr("There are no valid 'Pending' or 'Cancelled' tasks available for scheduling.")
            )
            return

        try:
            response = self.ask_for_sched_time(self.tr('Bulk Schedule Configuration'))

            if response:
                log(f"Bulk scheduling {len(schedulable)} tasks for {response[0]} at {response[1]}", 
                    log_level=1, context="SCHEDULER")
                for d in schedulable:
                    d.sched = response
                    d.status = config.Status.scheduled

                self.queue_update("populate_table", None)

        except Exception as e:
            log(f"Global scheduling operation failed: {e}", log_level=3, context="SCHEDULER")
            show_warning(self, self.tr("Schedule Error"), str(e))

    # ── Token & Link Refresh Logic ───────────────────────────────────────────


    def refresh_link_btn(self):
        """
            Re-injects a task's URL into the extraction pipeline to refresh expired tokens.
            
            This is essentially a 're-add' of an existing item. It preserves the 
            original destination folder while re-triggering the URL metadata 
            extraction process (Rust or yt-dlp) to get fresh media stream links.
        """
        ctx = "URL-REFRESH"
        selected_row = widgets.table.currentRow()
        
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
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
        widgets_add_download.save_to_edit.setText(folder)

        # Block url_edit signals so setText doesn't fire url_text_change prematurely
        widgets_add_download.url_edit.blockSignals(True)
        widgets_add_download.url_edit.setText(url)
        widgets_add_download.url_edit.blockSignals(False)

        # 2. Reset state
        self.reset()

        # 3. Defer extraction so the window fully renders first (200ms grace period)
        def _deferred_start():
            widgets_add_download.url_progress.show()
            widgets_add_download.url_progress.setRange(0, 0)
            widgets_add_download.save_to_edit.setText(folder)
            self.url_text_change()

        QTimer.singleShot(200, _deferred_start)
    

    def resume_all_downloads(self):
        """Resume all downloads that were previously cancelled or failed."""
        targets = [d for d in self.d_list if d.status in (config.Status.cancelled, config.Status.error, config.Status.failed)]
        for d in targets:
            self.start_download(d, silent=True)


    # endregion


    # region Downloads methods


    def file_in_d_list(self, target_file):
        for i, d in enumerate(self.d_list):
            if d.target_file == target_file:
                return i
        return None



    def get_queue_id(self, name: str) -> str:
        """Generate a unique ID for the queue based on its name."""
        return hashlib.md5(name.encode()).hexdigest()[:8]

    
    # ── Download Queue & Concurrency Management ──────────────────────────────

    @property
    def active_downloads(self):
        """
        Maintains a live cache of currently active download IDs.
        
        To prevent CPU spikes from constant list scanning, this property 
        caches results for 200ms. This is critical for the main event 
        loop which checks concurrency limits frequently.
        """
        current_time = time.time()
        if current_time - self._active_downloads_cache_time > 0.2:
            self._active_downloads_cache = set(
                d.id for d in self.d_list if d.status == config.Status.downloading
            )
            self._active_downloads_cache_time = current_time
            config.active_downloads = self._active_downloads_cache
        return self._active_downloads_cache
    
    def pending_jobs(self):
        """Processes the waitlist when concurrent download slots become available."""
        if self.pending and len(self.active_downloads) < int(config.max_concurrent_downloads):
            log("Concurrent slot available. Promoting next pending job.", 
                log_level=1, context="ENGINE-START")
            self.start_download(self.pending.popleft(), silent=True)

    
    def get_yt_id(self, url):
        """Extracts the 11-character YouTube ID."""
        if not url: return None
        pattern = r"(?:v=|\/|embed\/|youtu\.be\/)([0-9A-Za-z_-]{11})"
        match = re.search(pattern, url)
        return match.group(1) if match else None

    
    # ── Download Logic & Conflict Resolution ────────────────────────────────

    def _prompt_file_conflict(self, d_name: str) -> str:
        """
        Displays a modal dialog when a filename conflict is detected.
        """
        
        msg_text = self.tr(
            "File with the same name:\n%1\nalready exists in download list.\n"
            "Do you want to resume this file?\n\n"
            "Resume: Continue partial download.\n"
            "Overwrite: Delete old data and start fresh.\n"
            "Note: To keep both, rename the file or change the folder."
        ).replace("%1", d_name)

        msg = QMessageBox(parent=self.ui_add_download)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle(self.tr("File Already Exists"))
        msg.setText(msg_text)

        resume_btn = msg.addButton(self.tr("Resume"), QMessageBox.YesRole)
        overwrite_btn = msg.addButton(self.tr("Overwrite"), QMessageBox.NoRole)
        cancel_btn = msg.addButton(self.tr("Cancel"), QMessageBox.RejectRole)
        
        msg.setDefaultButton(resume_btn)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == resume_btn:
            return 'Resume'
        if clicked == overwrite_btn:
            return 'Overwrite'
        return 'Cancel'

    def start_download(self, d, silent: bool = False, downloader: Any = None):
        """
        Initiates a download task after performing dependency and filesystem checks.
        
        Validates the environment for FFmpeg (if streaming), checks folder 
        write permissions, and resolves filename conflicts. Spawns the 
        background 'brain' worker upon successful validation.
        """
        if d is None: return
        ctx = "ENGINE-START"

        # 1. Dependency Validation (FFmpeg)
        if d.type == 'dash' or 'm3u8' in d.protocol:
            if not d.ext:
                d.ext = self.extract_ext_from_url(d.url, d)
            
            ok = self.ensure_dependency(
                name="FFmpeg", 
                check_func=check_ffmpeg, 
                download_func=download_ffmpeg, 
                recommended_dir=config.global_sett_folder, 
                local_dir=config.current_directory,
                non_windows_msg=self.tr('"ffmpeg" is required for stream merging.')
            )
            if not ok:
                log("FFmpeg dependency missing; aborting stream download.", 
                    log_level=2, context=ctx)
                return 'cancelled'

        # 2. Filesystem Write Test
        folder = d.folder or config.download_folder
        try:
            test_path = os.path.join(folder, f'.omnipull_test_{d.id}')
            with open(test_path, 'w') as f: f.write('0')
            os.unlink(test_path)
            d.folder = folder
        except (FileNotFoundError, PermissionError) as e:
            log(f"Write permission denied for folder: {folder}", log_level=3, context=ctx)
            show_critical(self.ui_add_download, self.tr("Folder Error"), str(e))
            return

        # 3. Filename Sanitization
        if not d.name.strip() or len(d.name) > 200:
            show_warning(self.ui_add_download, self.tr("Download Error"), self.tr("Invalid filename."))
            return

        # 4. Conflict Check
        found_index = self.file_in_d_list(d.target_file)

        

        if found_index is None:
            # Get the ID of the new download we are trying to start
            new_yt_id = self.get_yt_id(getattr(d, 'original_url', d.url))

            for i, od in enumerate(self.d_list):
                # Existing checks (temp_file or name+folder)
                same_folder = os.path.normpath(od.folder) == os.path.normpath(d.folder)

                match_by_file = (
                    same_folder and
                    getattr(od, 'temp_file', None) == getattr(d, 'temp_file', None)
                )

                match_by_path = (
                    same_folder and
                    od.name == d.name
                )

                match_by_yt = False
                if new_yt_id and same_folder:
                    existing_yt_id = self.get_yt_id(getattr(od, 'original_url', od.url))
                    if existing_yt_id and existing_yt_id == new_yt_id:
                        match_by_yt = True

                if match_by_file or match_by_path or match_by_yt:
                    found_index = i
                    break
                
        if found_index is not None:
            log(f"File conflict detected for: {d.name}", log_level=2, context="CONFLICT-RESOLVER")
            d_from_list = self.d_list[found_index]
            d.id = d_from_list.id
            
            response = "Resume" if silent else self._prompt_file_conflict(d.name)

            if response == 'Resume':
                if d.size == d_from_list.size:
                    log(f"Resuming {d.name}; matching segment sizes found.", log_level=1, context="ENGINE-START")
                    d.segment_size = d_from_list.segment_size
                    d.downloaded = d_from_list.downloaded
                else:
                    log(f"Size mismatch for {d.name}. Purging stale data for fresh start.", log_level=1, context="JANITOR")
                    d.delete_tempfiles()
                self.d_list[found_index] = d

            elif response == 'Overwrite':
                log(f"Overwriting {d.name}. Purging existing cache.", log_level=1, context="JANITOR")
                d.delete_tempfiles()
                self.d_list[found_index] = d
            
            else:
                log("Download cancelled by user during conflict resolution.", log_level=1, context="CONFLICT-RESOLVER")
                return
        else:
            # d.id = len(self.d_list)
            # self.d_list.append(d)
            d.id = max((item.id for item in self.d_list), default=-1) + 1
            self.d_list.append(d)

        # 5. Concurrency Check
        max_conc = int(config.max_concurrent_downloads)
        if len(self.active_downloads) >= max_conc:
            log(f"Max concurrent reached ({max_conc}). Queueing: {d.name}", log_level=1, context=ctx)
            d.status = config.Status.pending
            self.pending.append(d)
            return

        # 6. Final Execution
        d.status = config.Status.downloading
        d.last_try_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if config.show_download_window:
            self.download_windows[d.id] = DownloadProgressDialog(d)
            self.download_windows[d.id].show()

        log(f"Spawning worker for task: {d.name}", log_level=1, context=ctx)
        self.settings_manager.save_d_list(self.d_list)
        self.update_summary()
        Thread(target=brain, daemon=True, args=(d, downloader)).start()

    # ── Interaction & Event Handlers ─────────────────────────────────────────

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
            selected_queue = widgets_add_download.queue_combo.currentText()
            has_queue = selected_queue and selected_queue != "None"

            if not self._batch_items:
                show_warning(
                    self.ui_add_download,
                    self.tr("Nothing to Add"),
                    self.tr("No links have been resolved yet. Please wait for processing to finish."),
                )
                return

            folder   = widgets_add_download.save_to_edit.text() or config.download_folder
            category = widgets_add_download.category_combo.currentText()

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
            widgets_add_download.download_btn.setText(self.tr("Start Download"))
            widgets_add_download.url_edit.blockSignals(True)
            widgets_add_download.url_edit.clear()
            widgets_add_download.url_edit.blockSignals(False)
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
        selected_category = widgets_add_download.category_combo.currentText()
        d.category = selected_category
        
        if selected_category and hasattr(widgets_add_download, '_category_map'):
            category_info = widgets_add_download._category_map.get(selected_category)
            if category_info and category_info.get('path'):
                d.folder = category_info.get('path')
            else:
                d.folder = widgets_add_download.save_to_edit.text() or config.download_folder
        else:
            d.folder = widgets_add_download.save_to_edit.text() or config.download_folder
        
        # 2. Handle Queue Logic or Immediate Download
        selected_queue = widgets_add_download.queue_combo.currentText()
        
        # Ensure the original URL is stored so we can compare YouTube IDs later
        d.original_url = self.d.url


        if selected_queue and selected_queue != "None":
            # Apply engine choice before queuing
            selected_engine = widgets_add_download.engine_combo.currentText()
            if selected_engine:
                d.engine = selected_engine
            self._add_to_selected_queue(d, selected_queue)
        else:
            # Apply engine choice from the selector
            selected_engine = widgets_add_download.engine_combo.currentText()
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
    
    

    
    # region Youtube Specifics

    # ── Thumbnail & Visual Asset Management ──────────────────────────────────

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
                        widgets_add_download.thumbnail_label.setPixmap(
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
        widgets_add_download.thumbnail_label.clear()
        widgets_add_download.thumbnail_label.setAlignment(Qt.AlignCenter)

        # Retrieve extension from the active download item
        ext = getattr(self.d, "ext", "")
        if ext and not ext.startswith("."):
            ext = f".{ext}"

        # Fallback to 'No preview' text if no icon is found
        if not self.show_filetype_thumbnail(ext):
            widgets_add_download.thumbnail_label.setText(self.tr("No preview"))

    def show_filetype_thumbnail(self, ext: str | None) -> bool:
        """
        Loads a standard icon pixmap based on the provided file extension.
        """
        pixmap = get_file_icon(ext)
        if pixmap.isNull():
            return False
        
        widgets_add_download.thumbnail_label.setPixmap(
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
                widgets_add_download.thumbnail_label.setPixmap(
                    pixmap.scaled(140, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            else:
                self.reset_to_default_thumbnail()
        else:
            self.reset_to_default_thumbnail()

    # ── Selection & Menu Synchronization ─────────────────────────────────────

    def update_pl_menu(self):
        """
        Synchronizes the playlist selection UI with the extracted playlist data.
        """
        try:
            if not hasattr(self, 'playlist') or not self.playlist:
                log("Playlist menu update skipped: No data available.", 
                    log_level=2, context="UI-SELECTION")
                return
            
            # Implementation for populating playlist-specific widgets goes here
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

            widgets_add_download.resolution_combo.clear()
            widgets_add_download.resolution_combo.addItems(self.d.stream_names)

            # Default to the first available stream (typically highest quality)
            selected_stream = self.d.stream_names[0]
            widgets_add_download.resolution_combo.setCurrentText(selected_stream)
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


    # ── Playlist Download Orchestration ──────────────────────────────────────

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
                widgets_add_download.close()
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










    # region Table control

    # ── Table Selection & Properties ─────────────────────────────────────────

    @property
    def selected_d(self):
        """Returns the DownloadItem currently focused in the UI."""
        if self.selected_row_num is not None and 0 <= self.selected_row_num < len(self.d_list):
            self._selected_d = self.d_list[self.selected_row_num]
        else:
            self._selected_d = None
        return self._selected_d

    @selected_d.setter
    def selected_d(self, value):
        self._selected_d = value

    # ── Search & Filtering Logic ─────────────────────────────────────────────

    def filter_download_table(self, text: str):
        """
        Performs a real-time global search across all visible table columns.
        
        Iterates through the QTableWidget and hides rows that do not contain 
        the target substring. Clears filters if the search box is empty.
        """
        text = text.strip().lower()
        table = widgets.table

        # Show all rows if search query is cleared
        if not text:
            for row in range(table.rowCount()):
                table.setRowHidden(row, False)
            return

        for row in range(table.rowCount()):
            match_found = False
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item and text in item.text().lower():
                    match_found = True
                    break
            table.setRowHidden(row, not match_found)

    def _categorize_download(self, filename: str, status: str):
        """
        Determines the internal 'Status Bucket' and 'Type Category' for a task.
        
        This metadata is stored directly on table items to allow fast sidebar 
        filtering without re-calculating logic for every row.
        """
        status_clean = (status or "").strip().lower()

        # Resolve Status Bucket
        if status_clean in ("completed", "finished", "done"):
            status_bucket = "Completed"
        elif "cancelled" in status_clean:
            status_bucket = "Cancelled"
        elif "queued" in status_clean:
            status_bucket = "Queued"
        elif status_clean in ("paused", "stopped"):
            status_bucket = "Paused"
        elif any(s in status_clean for s in ("error", "failed")):
            status_bucket = "Error"
        else:
            status_bucket = "Downloading"

        # Resolve Type Category (Priority: Explicit metadata > Extension detection)
        type_cat = getattr(self.d, 'category', "General")
        
        if type_cat == "General":
            f = (filename or "").lower()
            ext = f.rsplit(".", 1)[-1] if "." in f else ""
            
            mapping = {
                "Compressed": ("zip", "rar", "7z", "tar", "gz", "bz2", "xz"),
                "Documents": ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"),
                "Music": ("mp3", "flac", "aac", "ogg", "wav"),
                "Video": ("mp4", "mkv", "avi", "mov", "webm"),
                "Programs": ("exe", "msi", "deb", "rpm", "apk", "dmg")
            }
            for category, exts in mapping.items():
                if ext in exts:
                    type_cat = category
                    break

        return status_bucket, type_cat

    def _filter_by_category(self, current: QListWidgetItem, previous: QListWidgetItem | None):
        """
        Filters the table view based on sidebar selection (Category or Status).
        
        Uses pre-calculated metadata stored in UserRole and UserRole+1 
        on the Name column to perform near-instantaneous UI filtering.
        """
        if current is None: return
        selected = current.data(Qt.UserRole)
        table = widgets.table

        for row in range(table.rowCount()):
            # Locate the ID and Name items for metadata retrieval
            id_item = table.item(row, 0)
            name_item = table.item(row, 1)
            if not id_item or not name_item: continue
            
            # Find the actual data object to verify user-custom categories
            download_id = id_item.data(Qt.UserRole)
            d = next((x for x in self.d_list if x.id == download_id), None)
            if not d: continue

            # Retrieve cached categorization metadata
            row_status_bucket = name_item.data(Qt.UserRole)
            row_type_category = name_item.data(Qt.UserRole + 1)

            show = False
            if selected == "All Downloads":
                show = True
            elif selected in ("Completed", "Cancelled", "Downloading", "Queued", "Paused", "Error"):
                show = (row_status_bucket == selected)
            else:
                # Custom User Category priority, fallback to File Type category
                show = (d.category == selected or row_type_category == selected)

            table.setRowHidden(row, not show)

    # ── Threaded Table Population ──────────────────────────────────────────

    def populate_table(self):
        """
        Initiates the asynchronous table rendering process.
        
        Spawns a PopulateTableWorker on a dedicated QThread to prevent 
        the UI from freezing when processing large download lists.
        """
        # Ensure only one population thread runs at a time
        t = getattr(self, "table_thread", None)
        if t and t.isRunning():
            t.quit()
            t.wait(2000)

        self.table_thread = QThread(self)
        self.worker = PopulateTableWorker(self.d_list)
        self.worker.moveToThread(self.table_thread)

        # Lifecycle management
        self.table_thread.started.connect(self.worker.run)
        self.worker.data_ready.connect(self.populate_table_apply)
        self.worker.finished.connect(self.table_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.table_thread.finished.connect(self.table_thread.deleteLater)

        self.table_thread.start()

    @Slot(list)
    def populate_table_apply(self, prepared_rows):
        """
        Commits the worker's prepared data to the QTableWidget.
        
        This method runs on the Main Thread and handles icon rendering, 
        color-coding, and metadata tagging for every row.
        """
        if hasattr(widgets, "table_loading_overlay"):
            widgets.table_loading_overlay.hide()

        widgets.table.setRowCount(len(prepared_rows))
        
        for row_idx, data in enumerate(prepared_rows):
            # 1. ID Column (Column 0) - Reverse Display Index
            id_val = len(prepared_rows) - row_idx
            id_item = QTableWidgetItem(str(id_val))
            id_item.setData(Qt.UserRole, data['id']) # Store real ID for logic
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            id_item.setTextAlignment(Qt.AlignCenter)
            widgets.table.setItem(row_idx, 0, id_item)

            # 2. Name Column (Column 1) + Category Metadata
            name_item = QTableWidgetItem(validate_file_name(data['name']))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            
            # Cache category/status metadata for sidebar filtering
            status_bucket, type_cat = self._categorize_download(data['name'], data['status'])
            name_item.setData(Qt.UserRole, status_bucket)
            name_item.setData(Qt.UserRole + 1, type_cat)
            widgets.table.setItem(row_idx, 1, name_item)

            # 3. Progress Percentage (Column 2)
            prog_item = QTableWidgetItem(f"{int(data['progress'])}%")
            prog_item.setFlags(prog_item.flags() & ~Qt.ItemIsEditable)
            prog_item.setTextAlignment(Qt.AlignCenter)
            
            # Apply dynamic status-based coloring (Green, Red, Blue, etc.)
            color_hex = get_progress_bar_color(data['status'])
            prog_item.setForeground(QColor(color_hex))
            widgets.table.setItem(row_idx, 2, prog_item)

            # 4. Technical Metadata (Speed, ETA, Size)
            speed_txt = size_format(data['speed'], '/s') if data['speed'] else ""
            widgets.table.setItem(row_idx, 3, self._create_readonly_item(speed_txt))
            
            eta_txt = time_format(data['time_left'])
            widgets.table.setItem(row_idx, 4, self._create_readonly_item(eta_txt))
            
            widgets.table.setItem(row_idx, 5, self._create_readonly_item(size_format(data['downloaded'])))
            widgets.table.setItem(row_idx, 6, self._create_readonly_item(size_format(data['total_size'])))
            
            # 5. Status & Context (Columns 7-9)
            widgets.table.setItem(row_idx, 7, self._create_readonly_item(data['status']))
            widgets.table.setItem(row_idx, 8, self._create_readonly_item(data['i']))
            
            last_try = str(data.get('last_try_date', ""))
            widgets.table.setItem(row_idx, 9, self._create_readonly_item(last_try))

        self.settings_manager.save_d_list(self.d_list)
        self.update_summary()

    def _create_readonly_item(self, text: str) -> QTableWidgetItem:
        """Helper to generate a centered, non-editable table cell."""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        return item

    # ── High-Frequency UI Updates ──────────────────────────────────────────

    def update_table_progress(self):
        """
        Refreshes the progress column with optimized differential rendering.
        
        To maintain 60FPS UI performance, this method only updates rows for 
        active downloads and skips any whose percentage hasn't shifted since 
        the last tick. This prevents redundant Qt layout recalculations.
        """
        try:
            active_ids = self.active_downloads
            table = widgets.table

            for row in range(table.rowCount()):
                try:
                    # Retrieve the underlying Download ID from Column 0
                    id_item = table.item(row, 0)
                    if not id_item:
                        continue

                    download_id = id_item.data(Qt.UserRole)

                    # Optimization: Skip inactive rows that have already been cached
                    if download_id not in active_ids and download_id in self._last_progress_values:
                        continue

                    d = find_download_by_id(self.d_list, download_id)
                    if not d or d.progress is None:
                        continue

                    progress_pct = int(d.progress)

                    # Optimization: Only touch the widget if the numerical value has changed
                    if download_id in self._last_progress_values and \
                       self._last_progress_values[download_id] == progress_pct:
                        continue

                    progress_item = table.item(row, 2)
                    if progress_item:
                        progress_item.setText(f"{progress_pct}%")
                        
                        # Apply status-specific color-coding (e.g., Green for OK, Red for Error)
                        color_hex = get_progress_bar_color(d.status)
                        progress_item.setForeground(QColor(color_hex))

                        # Cache the new value for the next comparison
                        self._last_progress_values[download_id] = progress_pct
                except Exception:
                    continue
        except Exception as e:
            log(f"High-frequency progress update failed: {e}", log_level=3, context="GUI-TABLE")

    # ── Context Menu Management ──────────────────────────────────────────────

    def setup_context_menu_actions(self):
        """
        Initializes the global action registry for the download table.
        
        Maps icons, translated text, and keyboard shortcuts to their 
        respective slot functions. These actions are shared between the 
        right-click context menu and the main application menu.
        """
        def create_action(icon_path, text, shortcut, slot):
            action = QAction(QIcon(icon_path), self.tr(text), self)
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ApplicationShortcut)
            action.triggered.connect(slot)
            self.addAction(action)
            return action

        # File Operations
        self.action_open_file = create_action(":/icons/cil-file.png", "Open File", "Ctrl+O", self.open_item)
        self.action_open_file_with = create_action(":/icons/open_with.png", "Open File With", "Ctrl+A", self.open_item_with)
        self.action_open_location = create_action(":/icons/folder.png", "Open File Location", "Ctrl+L", self.open_file_location)
        self.action_watch_downloading = create_action(":/icons/vlc.svg", "Watch while downloading", "Ctrl+W", self.watch_downloading)
        
        # Scheduling & Queueing
        self.action_schedule_download = create_action(":/icons/schedule.svg", "Schedule download", "Ctrl+S", self.schedule_download)
        self.action_cancel_schedule = create_action(":/icons/cancel-schedule.svg", "Cancel schedule!", "Ctrl+C", self.cancel_schedule)
        self.action_add_to_queue = create_action(":/icons/add-queue.svg", "Add to Queue", "Ctrl+Q", self.add_to_queue_from_context)
        self.action_remove_from_queue = create_action(":/icons/remove-queue.svg", "Remove from Queue", "Ctrl+R", self.remove_from_queue_from_context)
        
        # Maintenance & Maintenance
        self.action_remerge = create_action(":/icons/ffmpeg.svg", "Re-merge audio/video", "Ctrl+M", self.remerge_audio_video)
        self.action_file_properties = create_action(":/icons/file_properties.png", "File Properties", "Ctrl+P", self.file_properties)
        self.action_file_checksum = create_action(":/icons/checksum.png", "File CheckSum!", "Ctrl+H", self.start_file_checksum)
        self.action_pop_file_from_table = create_action(":/icons/remove_data.png", "Remove from Table", "Ctrl+T", self.pop_download_item)
        self.action_delete_file_from_table = create_action(":/icons/trash.svg", "Delete", "Ctrl+D", self.delete_btn)

    


    def update_context_menu_actions_state(self, d):
        """
        Dynamically enables/disables context menu actions based on task status.
        """
        s = d.status
        is_active = s in {"downloading", "pending", "merging_audio", "paused", "queued"}
        is_completed = s == "completed"
        playable = self.is_playable_media(d)
        
        # NEW: Enable watch-while-downloading for yt-dlp
        is_ytdlp = (getattr(d, "engine", "") == "yt-dlp")

        # Map logic to action states
        self.action_open_file.setEnabled(is_completed)
        self.action_open_file_with.setEnabled(is_completed)
        self.action_open_location.setEnabled(is_completed)
        
        # Enable for yt-dlp OR m3u8/HLS streams
        can_watch_while_dl = (
            (not is_completed) and playable and 
            (is_ytdlp or 'm3u8' in (getattr(d, 'protocol', '') or ''))
        )
        self.action_watch_downloading.setEnabled(can_watch_while_dl)
        
        self.action_schedule_download.setEnabled(s in {"paused", "pending", "cancelled", "error", "failed"})
        self.action_cancel_schedule.setEnabled(s in {"scheduled", "pending", "downloading", "paused"})
        self.action_add_to_queue.setEnabled(s == "cancelled" and not d.in_queue)
        self.action_remove_from_queue.setEnabled(s == "queued" and d.in_queue)
        self.action_remerge.setEnabled(s == "error" and playable)
        self.action_file_checksum.setEnabled(is_completed and os.path.exists(d.target_file))
        self.action_pop_file_from_table.setEnabled(not is_active)
        self.action_delete_file_from_table.setEnabled(not is_active)

    def show_table_context_menu(self, pos: QPoint):
        """
        Orchestrates the display of the right-click context menu.
        """
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

        # Refresh availability states based on this specific item
        self.update_context_menu_actions_state(d)

        menu = QMenu(widgets.table)
        menu.setStyleSheet("QMenu::item { padding: 6px 20px; } QMenu::item:disabled { color: #6A6A6A; }")

        # Construct menu layout with logical separators
        menu.addAction(self.action_open_file)
        menu.addAction(self.action_open_location)
        menu.addAction(self.action_open_file_with)
        menu.addAction(self.action_watch_downloading)
        menu.addSeparator()
        menu.addAction(self.action_schedule_download)
        menu.addAction(self.action_cancel_schedule)
        menu.addAction(self.action_pop_file_from_table) 
        menu.addSeparator()
        menu.addAction(self.action_delete_file_from_table)
        menu.addSeparator()
        menu.addAction(self.action_add_to_queue)
        menu.addAction(self.action_remove_from_queue)
        menu.addAction(self.action_remerge)
        menu.addSeparator()
        menu.addAction(self.action_file_checksum)
        menu.addAction(self.action_file_properties)

        menu.exec(widgets.table.viewport().mapToGlobal(pos))

    def is_playable_media(self, d) -> bool:
        """Determines if the file extension is supported for streaming playback."""
        media_exts = {"mp4", "webm", "mkv", "avi", "mov", "flv", "ts"}
        return bool(d and d.ext and d.ext.lower() in media_exts and d.progress >= 30)

    # ── External File Execution ──────────────────────────────────────────────

    def open_item(self):
        """
        Launches the completed file using the operating system's default handler.
        
        Uses an asynchronous FileOpenThread to prevent UI hangs if the system 
        shell or target application is slow to respond.
        """
        ctx = "FILE-SHELL"
        selected_row = widgets.table.currentRow()
        self.selected_row_num = len(self.d_list) - 1 - selected_row

        try:
            d = self.selected_d
            if d.status == config.Status.completed:
                log(f"Executing default shell open for: {d.target_file}", 
                    log_level=1, context=ctx)
                
                self.file_open_thread = FileOpenThread(d.target_file, self)
                self.file_open_thread.critical_signal.connect(self._on_file_thread_error)
                self.file_open_thread.start()
                self.background_threads.append(self.file_open_thread)
                
            elif d.status == config.Status.deleted:
                show_critical(self, self.tr('File Not Found'), 
                    self.tr("The selected file could not be found on disk."))
            else:
                show_warning(self, self.tr("Download Incomplete"), 
                    self.tr("Please wait for the download to finish before opening."))
        except Exception as e:
            log(f"Shell execution failed: {e}", log_level=3, context=ctx)

    
    
    def open_item_with(self):
        """
        Triggers the platform-specific 'Open With' dialog for a completed file.
        
        On Windows, it invokes the shell 'OpenWith' dialog. On macOS and Linux, 
        it falls back to the default handler as command-line 'Open With' 
        dialogs are not standard across distributions.
        """
        ctx = "FILE-SHELL"
        selected_row = widgets.table.currentRow()
        self.selected_row_num = len(self.d_list) - 1 - selected_row

        try:
            d = self.selected_d
            file_path = d.target_file

            if not os.path.exists(file_path):
                show_critical(self, self.tr("File Not Found"), 
                              f"{self.tr('The file does not exist:')}\n{file_path}")
                return

            if d.status == config.Status.completed:
                system_platform = platform.system()

                if system_platform == "Windows":
                    log(f"Invoking Windows 'OpenWith' dialog for: {file_path}", 
                        log_level=1, context=ctx)
                    if not open_with_dialog_windows(self, file_path):
                        log(f"Windows OpenWith dialog failed for: {file_path}", 
                            log_level=3, context=ctx)
                else:
                    # Unix Fallback (macOS/Linux)
                    log(f"Standard shell open (Fallback) for: {file_path}", 
                        log_level=1, context=ctx)
                    self.file_open_thread = FileOpenThread(file_path, self)
                    self.file_open_thread.critical_signal.connect(self._on_file_thread_error)
                    self.file_open_thread.start()
                    self.background_threads.append(self.file_open_thread)

            elif d.status == config.Status.deleted:
                show_critical(self, self.tr('File Not Found'), 
                    self.tr("The selected file could not be found on disk."))
            else:
                show_warning(self, self.tr("Download Incomplete"), 
                    self.tr("Please wait for the download to finish before opening."))
        except Exception as e:
            log(f"OpenWith operation failed: {e}", log_level=3, context=ctx)
    

    def _on_file_thread_error(self, error_key, detail):
        """Processes raw errors from the thread and displays translated messages."""
        if error_key == 'not_found':
            title = self.tr("File Not Found")
            # Use Python's .replace() to fill the Qt placeholder
            msg = self.tr("The file '%1' could not be found or has been deleted.").replace("%1", detail)
        
        elif error_key == 'permission_denied':
            title = self.tr("Permission Error")
            msg = self.tr("Access denied: %1").replace("%1", detail)
            
        else: # os_error
            title = self.tr("OS Error")
            msg = self.tr("An OS error occurred: %1").replace("%1", detail)

        show_critical(self, title, msg)

    # ── Media Preview (Watch While Downloading) ──────────────────────────────

    
    def watch_downloading(self):
        """
        Enables media playback of a file currently in progress.
        
        To avoid file-locking conflicts between the downloader and the media 
        player, this method creates an 'atomic refresh copy' (.watch file). 
        The player opens the copy while the engine continues writing to the 
        main temporary file.
        """
        ctx = "MEDIA-WATCH"
        selected_row = widgets.table.currentRow()
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

    # ── Shell & OS Integration ───────────────────────────────────────────────

    def open_file_location(self):
        """
        Opens the destination folder in the OS file explorer.
        
        Attempts to highlight the specific file within the explorer window 
        using platform-specific flags (Explorer /select, Finder -R). Falls 
        back to opening the parent directory if the file is missing or on Linux.
        """
        ctx = "FILE-SHELL"
        selected_row = widgets.table.currentRow() 
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self, self.tr("Action Required"), self.tr("No download item selected"))
            return

        # Map UI row to data list index (Reverse Order)
        self.selected_row_num = len(self.d_list) - 1 - selected_row
        d = self.selected_d

        try:
            folder = os.path.abspath(d.folder)
            file = d.target_file
            log(f"Requesting shell explorer for: {folder}", log_level=1, context=ctx)

            if config.operating_system == 'Windows':
                if not os.path.isfile(file):
                    os.startfile(folder)
                else:
                    # Highlights the file in Windows Explorer
                    cmd = f'explorer /select, "{file}"'
                    run_command(cmd)

            elif config.operating_system == 'Darwin':
                # macOS Finder integration
                if not os.path.isfile(file):
                    cmd = f'open "{folder}"'
                else:
                    # Reveals the file in Finder
                    cmd = f'open -R "{file}"'
                run_command(cmd)

            else:
                # Linux standard: xdg-open typically opens the directory
                cmd = f'xdg-open "{folder}"'
                run_command(cmd)

        except Exception as e:
            log(f"Failed to open file location: {e}", log_level=3, context=ctx)
            handle_exceptions(e)

    # ── Individual Task Scheduling ───────────────────────────────────────────

    def schedule_download(self):
        """
        Assigns a specific execution time to the selected download task.
        
        Opens a date/time picker dialog and transitions the item to 
        'Scheduled' status. The background check_scheduled loop will 
        monitor this task for execution.
        """
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            show_warning(self, self.tr("Action Required"), self.tr("No download item selected"))
            return

        self.selected_row_num = len(self.d_list) - 1 - selected_row
        d = self.selected_d

        response = self.ask_for_sched_time(msg=d.name)
        if response:
            d.status = config.Status.scheduled
            d.sched = response
            
            log(f"Task '{d.name}' scheduled for execution at {response[0]} {response[1]}", 
                log_level=1, context="SCHEDULER")
            
            self.settings_manager.save_d_list(self.d_list)
            self.populate_table()
    
    def cancel_schedule(self):
        """Removes the schedule timer from a task and returns it to a 'Cancelled' state."""
        selected_row = widgets.table.currentRow()
        if selected_row < 0 or selected_row >= widgets.table.rowCount():
            return

        self.selected_row_num = len(self.d_list) - 1 - selected_row
        d = self.selected_d
        
        d.sched = None
        d.status = config.Status.cancelled
        
        log(f"Schedule removed for task: {d.name}", log_level=1, context="SCHEDULER")
        self.settings_manager.save_d_list(self.d_list)
        self.populate_table()

    # ── Task Metadata Inspector ──────────────────────────────────────────────

    def file_properties(self):
        """
        Displays the detailed metadata inspector for the selected download.
        
        Provides granular information including original URL, engine logs, 
        and detailed filesystem paths.
        """
        selected_row = widgets.table.currentRow()
        if selected_row < 0: return
        
        self.selected_row_num = len(self.d_list) - 1 - selected_row
        d = self.selected_d
        if not d: return

        log(f"Opening property inspector for: {d.name}", log_level=1, context="FILE-SHELL")
        dlg = FilePropertiesDialog(d, self, language=config.lang)
        dlg.exec()

    # ── Contextual Queue Orchestration ───────────────────────────────────────

    def add_to_queue_from_context(self):
        """
        Transitions a selected task into a specific download queue via the context menu.
        
        Includes validation to ensure YouTube tasks aren't assigned to the 'cURL' 
        engine (which lacks refresh capabilities) and preserves original webpage 
        metadata to facilitate future stream key renewals.
        """
        ctx = "ENGINE-QUEUE"
        selected_items = widgets.table.selectedItems()
        if not selected_items:
            show_warning(self, self.tr("No Selection"), 
                         self.tr("Please select a download to add to the queue."))
            return

        # Retrieve task data via UserRole metadata
        selected_row = selected_items[0].row()
        id_item = widgets.table.item(selected_row, 0)
        download_id = id_item.data(Qt.UserRole)
        d = next((x for x in self.d_list if x.id == download_id), None)
        
        if not d: return

        # ── 1. Engine & Platform Validation ──
        is_youtube = d.type in ("dash", "normal") and (
            "youtube.com" in (getattr(d, 'original_url', None) or d.url or "") or 
            "googlevideo.com" in (d.url or "")
        )
        
        if is_youtube and d.engine == "curl":
            log(f"Queue rejection: YouTube task '{d.name}' uses incompatible cURL engine.", 
                log_level=2, context=ctx)
            show_warning(self, self.tr("Queue Error"),
                         self.tr("YouTube videos in queues require aria2c or yt-dlp engine.\n\n"
                                 "cURL cannot refresh expired YouTube stream keys during queued execution."))
            return

        if not self.queues:
            show_warning(self, self.tr("No Queues Available"),
                         self.tr("Please create a queue in the Queue Manager before adding items."))
            return

        # ── 2. User Selection Dialog ──
        queue_names = [q["name"] for q in self.queues]
        dialog = QInputDialog(self)
        dialog.setWindowTitle(self.tr("Select Queue"))
        dialog.setLabelText(self.tr("Choose a destination queue:"))
        dialog.setComboBoxItems(queue_names)
        dialog.setStyleSheet(get_msgbox_style("inputdial"))

        if dialog.exec() == QInputDialog.Accepted:
            queue_name = dialog.textValue()
            if not queue_name: return

            log(f"Routing task '{d.name}' to queue: {queue_name}", 
                log_level=1, context=ctx)

            # ── 3. Metadata & State Update ──
            d.in_queue = True
            d.queue_name = queue_name
            d.queue_id = self.get_queue_id(queue_name)
            d.status = config.Status.queued

            # Preserve Source URL for Refresh Logic
            if is_youtube:
                d.original_url = getattr(d, 'webpage_url', d.url)
                log(f"Preserved YouTube source URL for token refresh: {d.original_url[:40]}...", 
                    log_level=3, context=ctx)

            # Assign Serialized Position (End of Queue)
            existing_positions = [
                item.queue_position for item in self.d_list
                if item.in_queue and item.queue_name == queue_name
            ]
            d.queue_position = max(existing_positions, default=0) + 1

            # Persist and Refresh UI
            self.settings_manager.save_queues(self.queues)
            self.populate_table()
            self.refresh_table_row(d)

    def remove_from_queue_from_context(self):
        """
        Extracts a task from its current queue and returns it to a 'Cancelled' state.
        
        Clears all queue-related metadata (ID, Position, Name) to allow the task 
        to be managed as a standard standalone download again.
        """
        ctx = "ENGINE-QUEUE"
        selected_items = widgets.table.selectedItems()
        if not selected_items:
            show_warning(self, self.tr("No Selection"), 
                         self.tr("Please select a download to remove from the queue."))
            return

        selected_row = selected_items[0].row()
        id_item = widgets.table.item(selected_row, 0)
        download_id = id_item.data(Qt.UserRole)
        d = next((x for x in self.d_list if x.id == download_id), None)
        
        if not d: return

        log(f"Removing task '{d.name}' from queue: {d.queue_name}", 
            log_level=1, context=ctx)

        # Strip Queue metadata
        d.in_queue = False
        d.queue_name = ""
        d.queue_id = ""
        d.queue_position = 0
        d.status = config.Status.cancelled

        self.populate_table()
        self.refresh_table_row(d)
    
    # ── FFmpeg Stream Discovery ──────────────────────────────────────────────

    def _find_audio_file_for(self, d) -> str | None:
        """
        Locates the best matching audio file for a given download item.
        
        Priority Logic:
        1. Exact Convention: Checks for 'audio_for_<TITLE>.*' using normalized names.
        2. Fuzzy Scan: Scans the folder for 'audio_for_' prefixes and scores 
           filenames based on Jaccard-like token overlap with the video title.
        3. Legacy Fallback: Uses the explicitly stored 'audio_file' property.
        """
        ctx = "ENGINE-REMERGE"
        folder = getattr(d, 'folder', None) or os.path.dirname(
            getattr(d, 'target_file', '') or getattr(d, 'temp_file', '') or ''
        )
        if not folder:
            return None

        explicit = getattr(d, 'audio_file', None)
        title_norm = _norm_title(getattr(d, 'name', '') or os.path.basename(getattr(d, 'target_file', '') or ''))
        
        # Tier 1: Exact normalization match
        _video_candidates, audio_candidates = _expected_paths(folder, title_norm)
        audio = _best_existing(audio_candidates)
        if audio:
            return audio

        # Tier 2: Fuzzy Filename Scoring
        candidates = []
        try:
            for p in glob.glob(os.path.join(folder, '*')):
                if not os.path.isfile(p): continue
                bn = os.path.basename(p)
                # Filter by title containment
                if _norm_title(bn).find(title_norm) != -1:
                    candidates.append(p)
        except Exception:
            candidates = [p for p in glob.glob(os.path.join(folder, 'audio_for_*.*')) if os.path.isfile(p)]

        if candidates:
            scored = []
            for p in candidates:
                t = _extract_title_from_pattern(p, "audio_for_") or ""
                # Score based on token intersection
                if t == title_norm:
                    score = 100
                else:
                    a = set(title_norm.split('_'))
                    b = set(t.split('_'))
                    score = len(a & b)
                scored.append((score, p))
            
            if scored:
                # Sort by score DESC, then size DESC, then name ASC
                scored.sort(key=lambda x: (-x[0], -os.path.getsize(x[1]), x[1]))
                if scored[0][0] > 0:
                    return scored[0][1]

        # Tier 3: Fallback to explicit metadata
        if explicit and os.path.exists(explicit):
            return explicit

        return None

    def _find_video_file_for(self, d, audio_path: str | None) -> str | None:
        """
        Locates the best matching video file for a given download item.
        
        Priority Logic:
        1. Exact Convention: Checks for '_temp_<TITLE>.*'.
        2. Target Proxy: Checks if the final target file exists (likely video-only).
        3. Fuzzy Temp Scan: Searches for '_temp_' prefixes with best title overlap.
        4. Media Signature: Scans for large media extensions with the target title.
        """
        folder = getattr(d, 'folder', None) or os.path.dirname(
            getattr(d, 'target_file', '') or getattr(d, 'temp_file', '') or ''
        )
        if not folder:
            return None

        title_norm = _norm_title(getattr(d, 'name', '') or os.path.basename(getattr(d, 'target_file', '') or ''))
        video_candidates, _audio_candidates = _expected_paths(folder, title_norm)

        # Tier 1: Exact naming convention
        video = _best_existing(video_candidates)
        if video and (not audio_path or os.path.abspath(video) != os.path.abspath(audio_path)):
            return video

        # Tier 2: Existing target check
        tgt = getattr(d, 'target_file', None)
        if tgt and os.path.exists(tgt) and (not audio_path or os.path.abspath(tgt) != os.path.abspath(audio_path)):
            return tgt

        # Tier 3: Fuzzy Temp matching
        candidates = []
        try:
            for p in glob.glob(os.path.join(folder, "*")):
                if not os.path.isfile(p): continue
                bn = os.path.basename(p)
                if bn.lower().startswith("_temp_") or _norm_title(bn).find(title_norm) != -1:
                    candidates.append(p)
        except Exception:
            candidates = [p for p in glob.glob(os.path.join(folder, "_temp_*.*")) if os.path.isfile(p)]
        
        if candidates:
            scored = []
            for p in candidates:
                t = _extract_title_from_pattern(p, "_temp_") or ""
                score = 100 if t == title_norm else len(set(title_norm.split('_')) & set(t.split('_')))
                if audio_path and os.path.abspath(p) == os.path.abspath(audio_path):
                    continue
                scored.append((score, p))
            
            if scored:
                scored.sort(key=lambda x: (-x[0], -os.path.getsize(x[1]), x[1]))
                if scored[0][0] > 0:
                    return scored[0][1]

        # Tier 4: Large Media Signature (Last Resort)
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
        """Determines the final merged container based on the source video extension."""
        out_ext = _pick_container_from_video(video_path)
        return os.path.join(d.folder, f"{d.name}.{out_ext}")

    # ── FFmpeg Execution & Cleanup ───────────────────────────────────────────

    def _cleanup_separate_streams(self, audio_path: str | None, video_path: str | None, keep_inputs=False):
        """
        Removes temporary stream files after a successful merge operation.
        
        By default, it targets the audio stream for removal to save space, 
        while preserving the video source unless explicitly told otherwise, 
        ensuring no data is lost if the user wants to re-try a different container.
        """
        if keep_inputs:
            return
            
        # Cleanup audio stream (usually the most redundant after merge)
        if audio_path and os.path.exists(audio_path):
            try:
                # os.remove(audio_path) # Logic preserved but kept commented as per original
                log(f"Stream cleanup: {os.path.basename(audio_path)} marked for removal.", 
                    log_level=1, context="ENGINE-REMERGE")
            except Exception:
                pass

    def _start_ffmpeg_remerge(self, d, video_path: str, audio_path: str, output_path: str, row_index: int):
        """
        Invokes FFmpeg via QProcess to mux audio and video streams.
        
        This is a non-blocking operation. It tracks the process ID to prevent 
        duplicate muxing tasks and provides signals for success/failure 
        to update the UI table and system notifications.
        """
        ctx = "ENGINE-REMERGE"
        ffmpeg = config.get_effective_ffmpeg()
        
        if not ffmpeg or not os.path.exists(ffmpeg):
            show_warning(self, self.tr("FFmpeg Missing"), 
                         self.tr("FFmpeg is required for merging. Please configure it in Settings."))
            return

        # Initialize process tracking map
        if not hasattr(self, "_remux_procs"):
            self._remux_procs = {}

        # Kill any existing muxing process for this specific download ID
        if d.id in self._remux_procs:
            try:
                self._remux_procs[d.id].kill()
            except Exception:
                pass
            self._remux_procs.pop(d.id, None)

        proc = QProcess(self)
        self._remux_procs[d.id] = proc

        # FFmpeg Arguments: Stream Copy (No Re-encoding) for speed
        args = [
            "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c", "copy",
            output_path,
        ]

        # Update UI state to 'Merging'
        old_status = d.status
        d.status = "merging_audio" 
        self.update_table_progress()
        log(f"Starting FFmpeg muxing for: {d.name}", log_level=1, context=ctx)

        def on_finished(exit_code, exit_status):
            self._remux_procs.pop(d.id, None)

            if exit_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                log(f"Muxing successful: {output_path}", log_level=1, context=ctx)
                
                d.status = "completed"
                d.progress = 100
                d.name = os.path.basename(output_path)
                d.folder = os.path.dirname(output_path) or d.folder

                # Post-success cleanup: Remove all associated temp files
                try:
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                    delete_folder(d.temp_folder)
                    delete_file(d.temp_file)
                    log(f"[CLEANUP] Removed temp files after successful remerge: {d.name}", log_level=2)
                except Exception as e:
                    log(f"[CLEANUP] Post-remerge cleanup failed: {e}", log_level=2)

                self.settings_manager.save_d_list(self.d_list)
                self.update_table_progress()
                notify(self.tr("Streams merged successfully."), self.tr("Merge Complete"))
            else:
                # Failure Path: Revert status and capture FFmpeg stderr
                d.status = old_status or "error"
                self.update_table_progress()
                error_log = proc.readAllStandardError().data().decode("utf-8", errors="ignore")
                log(f"FFmpeg failed with exit code {exit_code}: {error_log}", log_level=3, context=ctx)
                show_warning(self, self.tr("Merge Failed"), 
                             f"{self.tr('FFmpeg encountered an error during muxing.')}\n\n{error_log[:500]}")

        def on_error(process_error):
            self._remux_procs.pop(d.id, None)
            d.status = "error"
            self.update_table_progress()
            log(f"FFmpeg process error occurred: {process_error}", log_level=3, context=ctx)

        proc.finished.connect(on_finished)
        proc.errorOccurred.connect(on_error)
        proc.start(ffmpeg, args)

    # ── Context Menu Action: Re-merge ────────────────────────────────────────

    def remerge_audio_video(self):
        """
        Action triggered from the context menu to manually pair streams.
        
        Validates the selection, locates the orphaned audio/video components, 
        and initiates the FFmpeg muxing sequence.
        """
        selected_items = widgets.table.selectedItems()
        if not selected_items:
            show_warning(self, self.tr("No Selection"), 
                         self.tr("Please select a task to re-merge."))
            return

        # Map UI Selection to DownloadItem
        selected_row = selected_items[0].row()
        id_item = widgets.table.item(selected_row, 0)
        if not id_item: return
        download_id = id_item.data(Qt.UserRole)
        d = next((x for x in self.d_list if x.id == download_id), None)
        if not d: return

        # Stream Discovery logic
        audio_path = self._find_audio_file_for(d)
        if not audio_path or not os.path.exists(audio_path):
            show_warning(self, self.tr("Audio Missing"), 
                         self.tr("Could not find the associated audio file."))
            return

        video_path = self._find_video_file_for(d, audio_path)
        if not video_path or not os.path.exists(video_path):
            show_warning(self, self.tr("Video Missing"), 
                         self.tr("Could not find the associated video file."))
            return

        # Logic to ensure the output filename doesn't overwrite an input stream
        output_path = self._build_output_path(d, video_path)
        if os.path.abspath(output_path) == os.path.abspath(video_path):
            root, ext = os.path.splitext(video_path)
            output_path = f"{root}_merged{ext}"

        self._start_ffmpeg_remerge(d, video_path, audio_path, output_path, selected_row)

    
    
    # ── Verification & Maintenance ────────────────────────────────────────

    def start_file_checksum(self):
        """
        Computes a SHA-256 hash for the selected file to verify data integrity.
        
        Spawns a FileChecksum thread to handle the IO-heavy hashing process 
        without blocking the main GUI thread.
        """
        ctx = "VERIFY"
        selected_row = widgets.table.currentRow()
        if selected_row < 0:
            show_warning(self, self.tr("No Selection"), self.tr("Please select a completed download."))
            return

        # Reverse mapping: table row to d_list index
        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        if d.status != config.Status.completed:
            show_warning(self, self.tr("Invalid Status"), self.tr("Checksum is only available for completed downloads."))
            return

        log(f"Initiating SHA-256 computation for: {d.name}", log_level=1, context=ctx)
        
        self.checksum_thread = FileChecksum(d.target_file)
        self.checksum_thread.checksum_computed.connect(self.show_file_checksum_result)
        self.checksum_thread.start()
        self.background_threads.append(self.checksum_thread)

    def show_file_checksum_result(self, file_path, checksum):
        """Displays the computed hash in a modal dialog with a copy-to-clipboard feature."""
        if checksum == "Error":
            show_warning(self, self.tr("Checksum Error"), self.tr("Failed to read the file for hashing."))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("SHA-256 Checksum"))
        dialog.setFixedWidth(450)
        layout = QVBoxLayout(dialog)

        # UI Components
        layout.addWidget(QLabel(f"<b>{self.tr('File:')}</b> {os.path.basename(file_path)}"))
        layout.addWidget(QLabel("SHA-256 Hash:"))
        
        hash_edit = QLineEdit(checksum)
        hash_edit.setReadOnly(True)
        layout.addWidget(hash_edit)

        # Footer Actions
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton(self.tr("Copy Hash"))
        close_btn = QPushButton(self.tr("Close"))
        status_lbl = QLabel("") # "Copied!" feedback
        
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(status_lbl)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        def do_copy():
            QApplication.clipboard().setText(checksum)
            status_lbl.setText(f" <font color='green'>{self.tr('Copied!')}</font>")

        copy_btn.clicked.connect(do_copy)
        close_btn.clicked.connect(dialog.accept)
        dialog.exec()

    # ── Table Integrity & Styling  ────────────────────────────────────────

    def pop_download_item(self):
        """Removes the selected metadata entry from the UI and internal list."""
        selected_row = widgets.table.currentRow()
        if selected_row < 0: return

        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]

        log(f"Removing record for '{d.name}' from table.", log_level=1, context="GUI-TABLE")
        self.d_list.remove(d)
        # Sync to DB — ID is permanent, just remove the row
        self.settings_manager._db.delete_download(d.id)
        widgets.table.removeRow(selected_row)
        self.settings_manager.save_d_list(self.d_list)
    

    def set_row_color(self, row, status):
        """
        Applies consistent color themes to table rows based on download state.
        
        Green: Completed | Red: Error/Cancelled | Blue: Active | 
        Amber: Paused | Purple: Queued | Orange: Merging
        """
        color_map = {
            config.Status.completed:     QColor(0, 200, 83),   # Success Green
            config.Status.error:         QColor(244, 67, 54),  # Material Red
            config.Status.failed:        QColor(244, 67, 54),
            config.Status.cancelled:     QColor(244, 67, 54),
            config.Status.downloading:   QColor(33, 150, 243), # Processing Blue
            config.Status.paused:        QColor(255, 193, 7),  # Warning Amber
            config.Status.queued:        QColor(156, 39, 176), # Logic Purple
            config.Status.merging_audio: QColor(255, 109, 0),  # Action Orange
        }

        color = color_map.get(status, QColor(200, 200, 200)) # Default Grey

        for col in range(widgets.table.columnCount()):
            item = widgets.table.item(row, col)
            if item:
                item.setForeground(color)

    
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

    
    # ── Toolbar & Navigation ────────────────────────────────────────

    def update_toolbar_buttons_for_selection(self):
        """
        Enables or disables toolbar actions based on the current table selection.
        
        If multiple rows are selected, it performs a logical AND operation on 
        the available states (e.g., 'Resume' is only enabled if ALL selected 
        items are in a resumable state).
        """
        selected_rows = widgets.table.selectionModel().selectedRows()
        ui = widgets # Shortcut to global widgets

        if not selected_rows:
            # Revert to default 'No-Selection' state
            ui.btn_resume.setEnabled(False)
            ui.btn_pause.setEnabled(False)
            return

        # Map selected rows back to d_list IDs
        selected_ids = [widgets.table.item(r.row(), 0).data(Qt.UserRole) for r in selected_rows]
        items = [d for d in self.d_list if d.id in selected_ids]

        if not items: return

        # Aggregate states across selection
        combined = toolbar_buttons_state(items[0].status).copy()
        for d in items[1:]:
            state = toolbar_buttons_state(d.status)
            for key in combined:
                combined[key] = combined[key] and state.get(key, False)

        # Apply results to UI
        ui.btn_resume.setEnabled(combined.get("Resume", False))
        ui.btn_pause.setEnabled(combined.get("Pause", False))

    def change_page(self, idx: int):
        """Transitions the main UI stack to the specified page index."""
        widgets.stack.setCurrentIndex(idx)
            
    

    # region update

    # ── Startup & Configuration  ────────────────────────────────────────

    def on_startup(self):
        """
        Manages the 'Launch on Startup' integration with the OS.
        
        If checked, it invokes the platform-specific logic to add OmniPull 
        to the startup registry/folder. If unchecked, it cleans up 
        any existing startup entries.
        """
        ctx = "APP-LIFECYCLE"
        checked = widgets_settings.on_startup_chk.isChecked()
        
        if checked:
            if not (checkStartUp()): 
                log("Enabling OS startup integration.", log_level=1, context=ctx)
                addStartUp()
        else:
            if checkStartUp():
                log("Removing OS startup integration.", log_level=1, context=ctx)
                removeStartUp()

        # config.on_startup = checked

    def check_update_frequency(self):
        """Updates the global config for how often the app polls the server for updates."""
        try:
            selected = int(widgets_settings.update_interval_combo.currentText())
            config.update_frequency = selected
        except (ValueError, TypeError):
            pass

    
    # ── Update Orchestration  ────────────────────────────────────────

    def update_available(self):
        """
        Polls the remote server for the latest changelog and version data.
        
        Compares the current APP_VERSION with the remote latest_version. 
        If a mismatch is detected, it triggers the update handler to 
        prompt the user.
        """
        ctx = "UPDATE-ENGINE"
        change_cursor('busy')

        current_version = config.APP_VERSION
        info = get_changelog()

        if info:
            latest_version, version_description = info
            # Semantic version comparison (returns None if identical)
            newer_version = compare_versions(current_version, latest_version)
    
            if not newer_version or newer_version == current_version:
                self.new_version_available = False
                log(f"Version check: App is up-to-date (Server: {latest_version})", 
                    log_level=1, context=ctx)
            else:
                log(f"Update detected: {current_version} -> {latest_version}", 
                    log_level=1, context=ctx)
                self.new_version_available = True
                self.handle_update()
                
            # Synchronize global version state
            config.APP_LATEST_VERSION = latest_version if latest_version else current_version
            self.new_version_description = version_description

        else:
            log("Update check failed: Remote server unreachable or invalid response.", 
                log_level=2, context=ctx)
            self.new_version_description = None
            self.new_version_available = False

        self.settings_manager.save_settings()
        change_cursor('normal')
    

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

    # ── File System Finalization  ────────────────────────────────────────

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

    
    # ── Update Callbacks & Dialogs  ────────────────────────────────────────
    
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
            new_version = widgets_settings.get_ytdlp_version(force_refresh=True)
            widgets_settings.ytdlp_version_label.setText(self.tr("yt-dlp version: %1").replace("%1", new_version))
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
    

    # ── Update Execution  ────────────────────────────────────────

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
    

    # endregion

def load_initial_translator(app):
    """Loads the language saved in config before the main window is created."""
    from modules.config import lang
    import os
    
    # Map your config language to the filename
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
    path = os.path.join(os.path.dirname(__file__), "modules", "translations", file_map.get(lang, "app_en.qm"))
    
    if translator.load(path):
        app.installTranslator(translator)
    return translator # Keep reference to prevent garbage collection




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

