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


class DownloadControllerMixin:
    """Mixin providing DownloadController methods for DownloadManagerWindow."""

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


    def resume_btn(self):
        """
        Resume paused, queued, or errored downloads.
        Ensures the progress window is re-initialized to capture fresh signals.
        """
        ctx = "ENGINE-RESUME"
        selected_row = self.ui.table.currentRow()
        if selected_row < 0 or selected_row >= self.ui.table.rowCount():
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
        except Exception:
            pass
    
        # Use the specific engine logic or fallback to PyCURL
        if d.engine in ("aria2c", "yt-dlp"):
            Thread(target=brain, args=(d,), daemon=True).start()
            log(f"Engine ({d.engine}) resumed: {d.name}", log_level=1, context=ctx)
        else:
            # Native PyCURL / Fallback path
            self.start_download(d, silent=True)
    
        self.ui.btn_pause.setEnabled(True)
        self.ui.btn_resume.setEnabled(False)


    def pause_btn(self):
        """
        Suspends the currently selected download task.
        
        For aria2c, this initiates a 'Family Pause,' which halts the parent GID 
        and all associated segments/metadata downloads. For yt-dlp/Native, 
        it transitions the status to 'Cancelled' to break the worker loop.
        """
        ctx = "ENGINE-PAUSE"
        selected_row = self.ui.table.currentRow()
        
        if selected_row < 0 or selected_row >= self.ui.table.rowCount():
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
    
        self.ui.btn_pause.setEnabled(False)
        self.ui.btn_resume.setEnabled(True)
        self.settings_manager.save_d_list(self.d_list)
        self.populate_table()


    def delete_btn(self):
        """
        Removes selected tasks from the application and performs disk cleanup.
        
        Identifies all selected rows, verifies that none are active, and 
        invokes the 'Janitor' process to remove temporary files and 
        metadata from the system.
        """
        ctx = "JANITOR"
        selected_rows = list(set(index.row() for index in self.ui.table.selectedIndexes()))
    
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
    
                self.ui.table.removeRow(row)
                
                # Perform disk cleanup (removing .part, .aria2, and temp segments)
                janitor(d)
                log(f"Task and local cache purged: {d.name}", log_level=1, context=ctx)
    
            self.ui.table.clearSelection()
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
            self.ui.table.setRowCount(0)
            self.settings_manager.save_d_list(self.d_list)
            log("Global wipe complete. Download list is empty.", log_level=1, context=ctx)


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


    def resume_all_downloads(self):
        """Resume all downloads that were previously cancelled or failed."""
        targets = [d for d in self.d_list if d.status in (config.Status.cancelled, config.Status.error, config.Status.failed)]
        for d in targets:
            self.start_download(d, silent=True)


    def file_in_d_list(self, target_file):
        for i, d in enumerate(self.d_list):
            if d.target_file == target_file:
                return i
        return None


    def get_queue_id(self, name: str) -> str:
        """Generate a unique ID for the queue based on its name."""
        return hashlib.md5(name.encode()).hexdigest()[:8]


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
        Thread(target=brain, daemon=True, args=(d, downloader)).start()
