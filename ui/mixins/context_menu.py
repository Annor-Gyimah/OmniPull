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


class ContextMenuMixin:
    """Mixin providing ContextMenu methods for DownloadManagerWindow."""

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
        index = self.ui.table.indexAt(pos)
        if not index.isValid():
            return
    
        id_item = self.ui.table.item(index.row(), 0)
        if not id_item:
            return
    
        download_id = id_item.data(Qt.UserRole)
        d = next((x for x in self.d_list if x.id == download_id), None)
        if not d:
            return
    
        # Refresh availability states based on this specific item
        self.update_context_menu_actions_state(d)
    
        menu = QMenu(self.ui.table)
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
    
        menu.exec(self.ui.table.viewport().mapToGlobal(pos))


    def open_item(self):
        """
        Launches the completed file using the operating system's default handler.
        
        Uses an asynchronous FileOpenThread to prevent UI hangs if the system 
        shell or target application is slow to respond.
        """
        ctx = "FILE-SHELL"
        selected_row = self.ui.table.currentRow()
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
        selected_row = self.ui.table.currentRow()
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


    def open_file_location(self):
        """
        Opens the destination folder in the OS file explorer.
        
        Attempts to highlight the specific file within the explorer window 
        using platform-specific flags (Explorer /select, Finder -R). Falls 
        back to opening the parent directory if the file is missing or on Linux.
        """
        ctx = "FILE-SHELL"
        selected_row = self.ui.table.currentRow() 
        if selected_row < 0 or selected_row >= self.ui.table.rowCount():
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


    def schedule_download(self):
        """
        Assigns a specific execution time to the selected download task.
        
        Opens a date/time picker dialog and transitions the item to 
        'Scheduled' status. The background check_scheduled loop will 
        monitor this task for execution.
        """
        selected_row = self.ui.table.currentRow()
        if selected_row < 0 or selected_row >= self.ui.table.rowCount():
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
        selected_row = self.ui.table.currentRow()
        if selected_row < 0 or selected_row >= self.ui.table.rowCount():
            return
    
        self.selected_row_num = len(self.d_list) - 1 - selected_row
        d = self.selected_d
        
        d.sched = None
        d.status = config.Status.cancelled
        
        log(f"Schedule removed for task: {d.name}", log_level=1, context="SCHEDULER")
        self.settings_manager.save_d_list(self.d_list)
        self.populate_table()


    def file_properties(self):
        """
        Displays the detailed metadata inspector for the selected download.
        
        Provides granular information including original URL, engine logs, 
        and detailed filesystem paths.
        """
        selected_row = self.ui.table.currentRow()
        if selected_row < 0: return
        
        self.selected_row_num = len(self.d_list) - 1 - selected_row
        d = self.selected_d
        if not d: return
    
        log(f"Opening property inspector for: {d.name}", log_level=1, context="FILE-SHELL")
        dlg = FilePropertiesDialog(d, self, language=config.lang)
        dlg.exec()


    def add_to_queue_from_context(self):
        """
        Transitions a selected task into a specific download queue via the context menu.
        
        Includes validation to ensure YouTube tasks aren't assigned to the 'cURL' 
        engine (which lacks refresh capabilities) and preserves original webpage 
        metadata to facilitate future stream key renewals.
        """
        ctx = "ENGINE-QUEUE"
        selected_items = self.ui.table.selectedItems()
        if not selected_items:
            show_warning(self, self.tr("No Selection"), 
                         self.tr("Please select a download to add to the queue."))
            return
    
        # Retrieve task data via UserRole metadata
        selected_row = selected_items[0].row()
        id_item = self.ui.table.item(selected_row, 0)
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
        selected_items = self.ui.table.selectedItems()
        if not selected_items:
            show_warning(self, self.tr("No Selection"), 
                         self.tr("Please select a download to remove from the queue."))
            return
    
        selected_row = selected_items[0].row()
        id_item = self.ui.table.item(selected_row, 0)
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
                    d.delete_tempfiles()
                    delete_folder(d.temp_folder)
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


    def remerge_audio_video(self):
        """
        Action triggered from the context menu to manually pair streams.
        
        Validates the selection, locates the orphaned audio/video components, 
        and initiates the FFmpeg muxing sequence.
        """
        selected_items = self.ui.table.selectedItems()
        if not selected_items:
            show_warning(self, self.tr("No Selection"), 
                         self.tr("Please select a task to re-merge."))
            return
    
        # Map UI Selection to DownloadItem
        selected_row = selected_items[0].row()
        id_item = self.ui.table.item(selected_row, 0)
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


    def start_file_checksum(self):
        """
        Computes a SHA-256 hash for the selected file to verify data integrity.
        
        Spawns a FileChecksum thread to handle the IO-heavy hashing process 
        without blocking the main GUI thread.
        """
        ctx = "VERIFY"
        selected_row = self.ui.table.currentRow()
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


    def pop_download_item(self):
        """Removes the selected metadata entry from the UI and internal list."""
        selected_row = self.ui.table.currentRow()
        if selected_row < 0: return
    
        d_index = len(self.d_list) - 1 - selected_row
        d = self.d_list[d_index]
    
        log(f"Removing record for '{d.name}' from table.", log_level=1, context="GUI-TABLE")
        self.d_list.remove(d)
        # Sync to DB — ID is permanent, just remove the row
        self.settings_manager._db.delete_download(d.id)
        self.ui.table.removeRow(selected_row)
        self.settings_manager.save_d_list(self.d_list)
