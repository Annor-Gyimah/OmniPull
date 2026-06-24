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


class TerminalMixin:
    """Mixin providing Terminal methods for DownloadManagerWindow."""

    def toggle_terminal_view(self, checked: bool):
        """Switches the main view between the Download Table and the yt-dlp Terminal."""
        if checked:
            self.ui.stack.setCurrentWidget(self.ui.terminal_page)
            self.ui.btn_terminal.setIcon(QIcon(":/icons/database.png"))
            log("Switched to Embedded Terminal view", log_level=1, context=self.ctx)
        else:
            self.ui.stack.setCurrentWidget(self.ui.downloads_page)
            self.ui.btn_terminal.setIcon(QIcon(":/icons/terminal.png"))


    def _terminal_exec(self):
        """
        Parses and executes user input from the terminal.
        Handles internal commands (clear, abort) or delegates to the yt-dlp subprocess.
        """
        cmd = self.ui.terminal_input.text().strip()
        if not cmd:
            return
    
        if getattr(self, "_terminal_busy", False):
            log("Terminal is currently busy; ignoring new command input", 
                log_level=2, context=self.ctx)
            return
    
        self.ui.terminal_output.appendPlainText(f"> {cmd}")
        self.ui.terminal_input.clear()
    
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
    
        self.ui.terminal_input.history.append(cmd)
        self.ui.terminal_input.history_index = len(self.ui.terminal_input.history)


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
            self.ui.terminal_output.clear()
            return True
    
        if cmd == "history":
            for i, h in enumerate(self.ui.terminal_input.history, 1):
                config.main_window_q.put(("log", f"{i}: {h}"))
            return True
    
        if cmd == "abort":
            if self._current_proc:
                self._current_proc.terminate()
                log("Manual abortion of yt-dlp process requested by user", 
                    log_level=1, context=self.ctx)
            return True
    
        return False
