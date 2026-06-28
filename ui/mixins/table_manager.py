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


class TableManagerMixin:
    """Mixin providing TableManager methods for DownloadManagerWindow."""

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
                self.d_list.sort(key=k, reverse=False)
            elif key == 'name':
                self.d_list.sort(key=lambda d: (d.name or '').lower())
            elif key == 'status':
                self.d_list.sort(key=lambda d: str(getattr(d, 'status', '')).lower())
            elif key == 'size':
                self.d_list.sort(key=lambda d: getattr(d, 'total_size', getattr(d, 'size', 0)) or 0, reverse=True)
            
            self.populate_table()
        except Exception as e:
            log(f"Sorting operation failed: {e}", log_level=3, context=self.ctx)


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


    def filter_download_table(self, text: str):
        """
        Performs a real-time global search across all visible table columns.
        
        Iterates through the QTableWidget and hides rows that do not contain 
        the target substring. Clears filters if the search box is empty.
        """
        text = text.strip().lower()
        table = self.ui.table
    
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
        table = self.ui.table
    
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


    def populate_table(self):
        """
        Initiates the asynchronous table rendering process.
        
        Spawns a PopulateTableWorker on a dedicated QThread to prevent 
        the UI from freezing when processing large download lists.
        """
        # If the previous populate thread is still running, skip this cycle rather than
        # blocking the UI thread for up to 2 s waiting for it to finish.
        # Guard against RuntimeError: PySide6 raises isRunning() on a QThread whose C++
        # object was already destroyed by a prior deleteLater() call.
        t = getattr(self, "table_thread", None)
        if t is not None:
            try:
                if t.isRunning():
                    return
            except RuntimeError:
                pass  # C++ object deleted; safe to create a new thread

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
        if hasattr(self.ui, "table_loading_overlay"):
            self.ui.table_loading_overlay.hide()
    
        self.ui.table.setRowCount(len(prepared_rows))
        
        for row_idx, data in enumerate(prepared_rows):
            # 1. ID Column (Column 0) - Reverse Display Index
            id_val = len(prepared_rows) - row_idx
            id_item = QTableWidgetItem(str(id_val))
            id_item.setData(Qt.UserRole, data['id']) # Store real ID for logic
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            id_item.setTextAlignment(Qt.AlignCenter)
            self.ui.table.setItem(row_idx, 0, id_item)
    
            # 2. Name Column (Column 1) + Category Metadata
            name_item = QTableWidgetItem(validate_file_name(data['name']))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            
            # Cache category/status metadata for sidebar filtering
            status_bucket, type_cat = self._categorize_download(data['name'], data['status'])
            name_item.setData(Qt.UserRole, status_bucket)
            name_item.setData(Qt.UserRole + 1, type_cat)
            self.ui.table.setItem(row_idx, 1, name_item)
    
            # 3. Progress Percentage (Column 2)
            prog_item = QTableWidgetItem(f"{int(data['progress'])}%")
            prog_item.setFlags(prog_item.flags() & ~Qt.ItemIsEditable)
            prog_item.setTextAlignment(Qt.AlignCenter)
            
            # Apply dynamic status-based coloring (Green, Red, Blue, etc.)
            color_hex = get_progress_bar_color(data['status'])
            prog_item.setForeground(QColor(color_hex))
            self.ui.table.setItem(row_idx, 2, prog_item)
    
            # 4. Technical Metadata (Speed, ETA, Size)
            speed_txt = size_format(data['speed'], '/s') if data['speed'] else ""
            self.ui.table.setItem(row_idx, 3, self._create_readonly_item(speed_txt))
            
            eta_txt = time_format(data['time_left'])
            self.ui.table.setItem(row_idx, 4, self._create_readonly_item(eta_txt))
            
            self.ui.table.setItem(row_idx, 5, self._create_readonly_item(size_format(data['downloaded'])))
            self.ui.table.setItem(row_idx, 6, self._create_readonly_item(size_format(data['total_size'])))
            
            # 5. Status & Context (Columns 7-9)
            self.ui.table.setItem(row_idx, 7, self._create_readonly_item(data['status']))
            self.ui.table.setItem(row_idx, 8, self._create_readonly_item(data['i']))
            
            last_try = str(data.get('last_try_date', ""))
            self.ui.table.setItem(row_idx, 9, self._create_readonly_item(last_try))

        # Rebuild O(1) lookup index for update_table_progress
        self._d_index = {d.id: d for d in self.d_list}


    def _create_readonly_item(self, text: str) -> QTableWidgetItem:
        """Helper to generate a centered, non-editable table cell."""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        return item


    def update_table_progress(self):
        """
        Refreshes live columns (progress %, speed, ETA, done, size, status) for active
        downloads every tick.  Uses _d_index for O(1) lookup instead of O(n) linear scan.

        Three tiers per row:
        - active: update all live columns every tick
        - just-finished (in cache but not in active_ids): one final flush of terminal values,
          then mark as finalized so subsequent ticks skip it without a populate_table call
        - finalized/never-started: skip
        """
        try:
            active_ids = self.active_downloads
            table = self.ui.table
            d_index = getattr(self, '_d_index', {})
            finalized = getattr(self, '_finalized_downloads', set())

            for row in range(table.rowCount()):
                try:
                    id_item = table.item(row, 0)
                    if not id_item:
                        continue

                    download_id = id_item.data(Qt.UserRole)
                    is_active = download_id in active_ids

                    # Fully finalized inactive rows need no further work
                    if not is_active and download_id in finalized:
                        continue

                    # Skip rows that were never active and have no cached value
                    if not is_active and download_id not in self._last_progress_values:
                        continue

                    d = d_index.get(download_id)
                    if not d or d.progress is None:
                        continue

                    progress_pct = int(d.progress)
                    last_pct = self._last_progress_values.get(download_id)

                    # Update progress % whenever the integer value changed
                    if last_pct != progress_pct:
                        progress_item = table.item(row, 2)
                        if progress_item:
                            progress_item.setText(f"{progress_pct}%")
                            progress_item.setForeground(QColor(get_progress_bar_color(d.status)))
                            self._last_progress_values[download_id] = progress_pct

                    # Refresh speed / ETA / done / size / status
                    speed_item = table.item(row, 3)
                    if speed_item:
                        speed_item.setText(size_format(d.speed, '/s') if (is_active and d.speed) else "")

                    eta_item = table.item(row, 4)
                    if eta_item:
                        eta_item.setText(time_format(d.time_left) if is_active else "")

                    done_item = table.item(row, 5)
                    if done_item:
                        done_item.setText(size_format(d.downloaded))

                    size_item = table.item(row, 6)
                    if size_item:
                        size_item.setText(size_format(d.total_size))

                    status_item = table.item(row, 7)
                    if status_item and status_item.text() != d.status:
                        status_item.setText(d.status)
                        status_item.setForeground(QColor(get_progress_bar_color(d.status)))

                    # Once a non-active download has been flushed, mark it finalized
                    if not is_active:
                        finalized.add(download_id)

                    # If a download restarts, remove it from finalized so it tracks again
                    if is_active:
                        finalized.discard(download_id)

                except Exception:
                    continue

            self._finalized_downloads = finalized
        except Exception as e:
            log(f"High-frequency progress update failed: {e}", log_level=3, context="GUI-TABLE")


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
    
        for col in range(self.ui.table.columnCount()):
            item = self.ui.table.item(row, col)
            if item:
                item.setForeground(color)


    def refresh_table_row(self, d):
        """Refresh only the specific row for a download without repainting the whole table."""
        target_row = None
    
        # First find the row that matches the download ID
        for row in range(self.ui.table.rowCount()):
            id_item = self.ui.table.item(row, 0)
            if id_item and id_item.data(Qt.UserRole) == d.id:
                target_row = row
                break
    
        if target_row is not None:
            # Update only the status column
            status_col = self.d_headers.index("status")
            status_item = self.ui.table.item(target_row, status_col)
            if status_item:
                status_item.setText(d.status)
    
            # Update the color styling
            self.set_row_color(target_row, d.status)


    def update_toolbar_buttons_for_selection(self):
        """
        Enables or disables toolbar actions based on the current table selection.
        
        If multiple rows are selected, it performs a logical AND operation on 
        the available states (e.g., 'Resume' is only enabled if ALL selected 
        items are in a resumable state).
        """
        selected_rows = self.ui.table.selectionModel().selectedRows()
        ui = self.ui # Shortcut to global self.ui
    
        if not selected_rows:
            # Revert to default 'No-Selection' state
            ui.btn_resume.setEnabled(False)
            ui.btn_pause.setEnabled(False)
            return
    
        # Map selected rows back to d_list IDs
        selected_ids = [self.ui.table.item(r.row(), 0).data(Qt.UserRole) for r in selected_rows]
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
