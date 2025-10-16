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
import sys
import json
import stat
import shlex
import subprocess
from modules import config
from functools import partial
from modules.utils import log, delete_file
from modules.settings_manager import SettingsManager

from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt, QCoreApplication, QTranslator, Signal, Slot, QThread, QTimer, QObject

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QCheckBox,
    QSpinBox, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QStackedWidget, QFrame, QMessageBox,
    QGroupBox,  QTabWidget, QFileDialog, QSizePolicy, QGroupBox
)



class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Settings"))
        self.setFixedSize(720, 500)
        self.setStyleSheet(self.dark_stylesheet())
       


        # setting.load_setting()
        self.settings_manager = SettingsManager()

        self.translator = QTranslator()

        

        

        # Layouts
        # main_layout = QHBoxLayout(self)

        outer_layout = QVBoxLayout(self)  # main vertical layout
        main_layout = QHBoxLayout()       # inside horizontal layout for sidebar + stack
        outer_layout.addLayout(main_layout)

        # Sidebar for section list
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)
        self.sidebar.setSpacing(10)
        self.sidebar.setStyleSheet(
            """
            QListWidget::item {
                padding: 10px;
                font-size: 14px;
                height: 32px;
            }
            QListWidget::item:selected {
            background-color: rgba(45, 224, 153, 0.1);
            color: #6FFFB0;
            padding-left: 10px;
            margin: -12px;
            border: none;
            }
        """)

        icon_map = {
            self.tr("General"): "icons/general.png",
            self.tr("Engine Config"): "icons/cil-link.png",
            self.tr("Backend Paths"): "icons/cli-link.png",
            self.tr("Browser"): "icons/extension.png",
            self.tr("Updates"): "icons/updates.svg",
            
        }

        for key, icon in icon_map.items():
            translated_text = self.tr(key)
            item = QListWidgetItem(translated_text)
            self.sidebar.addItem(item)


        main_layout.addWidget(self.sidebar)

        # # Sidebar list (left)
        # self.sidebar_list = QListWidget()
        # self.sidebar_list.setFixedWidth(120)

        # Divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setStyleSheet("background-color: rgba(80, 255, 180, 0.1);")
        divider.setFixedWidth(1)


        # Stack for content areas
        self.stack = QStackedWidget()
        main_layout.addWidget(divider)
        main_layout.addWidget(self.stack)


        # Buttons always at bottom
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignRight)

        self.ok_button = QPushButton(self.tr("OK"))
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setCursor(Qt.PointingHandCursor)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                ); 
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33d47c;
            }
        """)

        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                ); 
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
        """)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        outer_layout.addLayout(button_layout)

        # Initialize sections
        self.setup_general_tab()
        self.setup_engine_config_tab()
        self.setup_backend_paths_tab()
        self.setup_browser_tab()
        self.setup_updates_tab()
        
        self.check_update_btn.clicked.connect(self.on_call_update)
        self.yt_dlp_update_btn.clicked.connect(self.on_call_ytdlp_update)
        


        self.load_values(config)

        # Connect sidebar to stack switching
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)
        # Load saved language
        self.current_language = config.lang
        self.apply_language(self.current_language)

    def setup_general_tab(self):
        general_widget = QWidget()
        general_layout = QFormLayout(general_widget)
        general_layout.setSpacing(16)

        self.qt_font_dpi = QComboBox()
        self.qt_font_dpi.setToolTip(self.tr('Set value for DPI. Restart app to reflect.'))
        self.qt_font_dpi.addItems([str(i) for i in range(90, 151)])

        self.language_combo = QComboBox()
        self.language_combo.setToolTip(self.tr('Select your preferred language'))
        self.language_combo.addItems(["English","Chinese", "Spanish", "Korean", "French", "Japanese", "Hindi"])

        self.setting_scope_combo = QComboBox()
        self.setting_scope_combo.setToolTip(self.tr('Set settings to Global or Local. Recommend: Global.'))
        self.setting_scope_combo.addItems(["Global", "Local"])

        # Create container layouts for each row of checkboxes
        row1_layout = QHBoxLayout()
        row2_layout = QHBoxLayout()
        row3_layout = QHBoxLayout()
        row4_layout = QHBoxLayout()

        # First row
        self.monitor_clipboard_cb = QCheckBox(self.tr("Monitor Copied URLs"))
        self.monitor_clipboard_cb.setToolTip(self.tr("Check to monitor clipboard for copied URLS"))
        self.show_download_window_cb = QCheckBox(self.tr("Show Download Window"))
        self.show_download_window_cb.setToolTip(self.tr("Check to show download window whilst downloading"))
        row1_layout.addWidget(self.monitor_clipboard_cb)
        row1_layout.addWidget(self.show_download_window_cb)

        # Second row
        self.auto_close_cb = QCheckBox(self.tr("Auto Close DL Window"))
        self.auto_close_cb.setToolTip(self.tr("Check to close the download window when download is done.")) 
        self.show_thumbnail_cb = QCheckBox(self.tr("Show Thumbnail"))
        self.show_thumbnail_cb.setToolTip(self.tr("Check to show downloaded thumbnail of download item during URL processing."))
        row2_layout.addWidget(self.auto_close_cb)
        row2_layout.addWidget(self.show_thumbnail_cb)

        # Third row
        self.on_startup_cb = QCheckBox(self.tr("On Startup"))
        self.on_startup_cb.setToolTip(self.tr("Check for app to autostart when PC booted to desktop"))
        self.show_all_logs = QCheckBox(self.tr("Show all logs"))
        self.show_all_logs.setToolTip(self.tr("Check to see all logs regardless the level."))
        row3_layout.addWidget(self.on_startup_cb)
        row3_layout.addWidget(self.show_all_logs)

        # Fourth row
        self.hide_app_cb = QCheckBox(self.tr("Hide App"))
        self.hide_app_cb.setToolTip(self.tr("Check to hide app under the system tray on close"))
        row3_layout.addWidget(self.hide_app_cb)

        



        download_engine = QComboBox()
        download_engine.addItems(["aria2", "curl", "yt-dlp"])
        self.download_engine_combo = download_engine

        self.curl_proxy_checkBox = QCheckBox(self.tr("Use Proxy"))
        self.curl_proxy_input = QLineEdit()
        self.curl_proxy_input.setPlaceholderText("http://127.0.0.1:8080")
        self.curl_proxy_type_combo = QComboBox()
        self.curl_proxy_type_combo.addItems(["http", "https", "socks5"])
        self.curl_proxy_username = QLineEdit()
        self.curl_proxy_username.setPlaceholderText(self.tr("Username"))
        self.curl_proxy_password = QLineEdit()
        self.curl_proxy_password.setPlaceholderText(self.tr("Password"))
        self.curl_proxy_checkBox.setToolTip(self.tr("Enable proxy for downloads."))
        self.curl_proxy_input.setToolTip(self.tr("Enter the proxy address."))
        self.curl_proxy_type_combo.setToolTip(self.tr("Select the proxy type."))
        self.curl_proxy_input.setEnabled(False)
        self.curl_proxy_type_combo.setEnabled(False)
        self.curl_proxy_username.setEnabled(False)
        self.curl_proxy_password.setEnabled(False)
        self.curl_proxy_checkBox.toggled.connect(self.curl_proxy_input.setEnabled)
        self.curl_proxy_checkBox.toggled.connect(self.curl_proxy_type_combo.setEnabled)
        self.curl_proxy_checkBox.toggled.connect(self.curl_proxy_username.setEnabled)
        self.curl_proxy_checkBox.toggled.connect(self.curl_proxy_password.setEnabled)

        # Proxy row: checkbox, type, address
        proxy_row = QHBoxLayout()
        proxy_row.addWidget(self.curl_proxy_checkBox)
        proxy_row.addWidget(self.curl_proxy_type_combo)
        proxy_row.addWidget(self.curl_proxy_input)

        # Username/password row
        proxy_auth_row = QHBoxLayout()
        proxy_auth_row.addWidget(QLabel(self.tr("Proxy Username:")))
        proxy_auth_row.addWidget(self.curl_proxy_username)
        proxy_auth_row.addWidget(QLabel(self.tr("Proxy Password:")))
        proxy_auth_row.addWidget(self.curl_proxy_password)

        general_layout.addRow(QLabel("QT FONT DPI:"), self.qt_font_dpi)
        general_layout.addRow(QLabel("Choose Language:"), self.language_combo)
        general_layout.addRow(QLabel("Choose Setting:"), self.setting_scope_combo)
        # Add rows to general_layout
        general_layout.addRow(row1_layout)
        general_layout.addRow(row2_layout) 
        general_layout.addRow(row3_layout)
        # general_layout.addRow(row4_layout)
        general_layout.addRow(QLabel(self.tr("Download Engine:")), download_engine)
        general_layout.addRow(proxy_row)
        general_layout.addRow(proxy_auth_row)
        
        self.stack.addWidget(general_widget)


    def setup_engine_config_tab(self):
        self.engine_widget = QWidget()
        self.engine_layout = QVBoxLayout(self.engine_widget)

        self.engine_tabs = QTabWidget()

        # === CURL CONFIG TAB ===
        self.curl_tab = QWidget()
        curl_layout = QVBoxLayout(self.curl_tab)
        curl_group = QGroupBox("General")
        curl_group_layout = QVBoxLayout()

        # Speed Limit
        curl_speed_layout = QHBoxLayout()
        self.curl_speed_checkBox = QCheckBox(self.tr("Speed Limit"))
        self.curl_speed_checkBox.setToolTip(self.tr("Enable speed limit for curl downloads."))
        self.curl_speed_limit = QLineEdit()
        self.curl_speed_limit.setValidator(QIntValidator(1, 1000000, self))
        self.curl_speed_limit.setPlaceholderText(self.tr("e.g., 50k, 10k..."))
        self.curl_speed_limit.setToolTip(self.tr("Set a speed limit for curl downloads."))
        self.curl_speed_limit.setEnabled(False)  # initially disabled
        self.curl_speed_checkBox.toggled.connect(self.curl_speed_limit.setEnabled)
        curl_speed_layout.addWidget(self.curl_speed_checkBox)
        curl_speed_layout.addWidget(self.curl_speed_limit)
        curl_group_layout.addLayout(curl_speed_layout)

        # Max Concurrent Downloads & Max Connections
        curl_concurrent_layout = QHBoxLayout()
        self.curl_conn_label = QLabel(self.tr("Max Concurrent Downloads:"))
        self.curl_max_concurrent = QComboBox()
        self.curl_max_concurrent.addItems(["1", "2", "3", "4", "5"])
        curl_concurrent_layout.addWidget(self.curl_conn_label)
        curl_concurrent_layout.addWidget(self.curl_max_concurrent)
        curl_group_layout.addLayout(curl_concurrent_layout)

        curl_connections_layout = QHBoxLayout()
        self.curl_conn_label2 = QLabel(self.tr("Max Connections Settings:"))
        self.curl_max_connections = QComboBox()
        self.curl_max_connections.addItems(["8", "16", "32", "64"])
        curl_connections_layout.addWidget(self.curl_conn_label2)
        curl_connections_layout.addWidget(self.curl_max_connections)
        curl_group_layout.addLayout(curl_connections_layout)

        curl_segment_layout = QHBoxLayout()
        self.curl_segment_label = QLabel(self.tr("Segment Size:"))
        self.curl_segment_size = QLineEdit()
        self.curl_segment_size.setPlaceholderText("e.g., 50k, 10k...")
        self.curl_segment_size.setToolTip(self.tr("Set the segment size for curl downloads."))
        self.curl_segment_size_combo = QComboBox()
        self.curl_segment_size_combo.addItems(["KB", "MB"])
        self.curl_segment_size_combo.setToolTip(self.tr("Select the unit for segment size."))
        curl_segment_layout.addWidget(self.curl_segment_label)
        curl_segment_layout.addWidget(self.curl_segment_size)
        curl_segment_layout.addWidget(self.curl_segment_size_combo)
        curl_group_layout.addLayout(curl_segment_layout)

        # --- Scheduled Download Retry Section ---
        self.curl_retry_schedule_cb = QCheckBox(self.tr("Retry failed scheduled downloads"))
        self.curl_retry_count_spin = QSpinBox()
        self.curl_retry_count_spin.setRange(1, 10)
        self.curl_retry_count_spin.setValue(3)
        self.curl_retry_count_spin.setEnabled(False)

        self.curl_retry_interval_spin = QSpinBox()
        self.curl_retry_interval_spin.setRange(1, 60)
        self.curl_retry_interval_spin.setValue(5)
        self.curl_retry_interval_spin.setEnabled(False)

        self.curl_retry_schedule_cb.toggled.connect(self.curl_retry_count_spin.setEnabled)
        self.curl_retry_schedule_cb.toggled.connect(self.curl_retry_interval_spin.setEnabled)

        curl_group_layout.addWidget(self.curl_retry_schedule_cb)

        self.curl_retry_row = QHBoxLayout()
        self.curl_retry_row.addWidget(QLabel(self.tr("Max retries:")))
        self.curl_retry_row.addWidget(self.curl_retry_count_spin)
        self.curl_retry_row.addSpacing(20)
        self.curl_retry_row.addWidget(QLabel(self.tr("Interval (Minutes):")))
        self.curl_retry_row.addWidget(self.curl_retry_interval_spin)
        curl_group_layout.addLayout(self.curl_retry_row)

        curl_group.setStyleSheet("QGroupBox { border: 1px solid rgba(255, 255, 255, 0.06); }")
        curl_group.setContentsMargins(10, 10, 10, 10)
        curl_group.setLayout(curl_group_layout)
        curl_layout.addWidget(curl_group)
        self.engine_tabs.addTab(self.curl_tab, "cURL")

        # === YT-DLP CONFIG TAB ===
        self.ytdlp_tab = QWidget()
        ytdlp_layout = QVBoxLayout(self.ytdlp_tab)

        # Extraction Options groupbox
        extraction_group = QGroupBox(self.tr("Extraction Options"))
        extraction_group_layout = QHBoxLayout()

        self.no_playlist_cb = QCheckBox(self.tr("No Playlist"))
        self.no_playlist_cb.setToolTip(self.tr("Download only the video, not the entire playlist."))
        self.ignore_errors_cb = QCheckBox(self.tr("Ignore Errors"))
        self.ignore_errors_cb.setToolTip(self.tr("Continue downloading even if errors occur."))
        self.list_formats_cb = QCheckBox(self.tr("List Formats"))
        self.list_formats_cb.setToolTip(self.tr("List available formats for the video instead of downloading."))
        self.use_ytdlp_exe_cb = QCheckBox(self.tr("Use YT-DLP executable"))
        self.use_ytdlp_exe_cb.setToolTip(self.tr("Check to use the yt-dlp binary or use the bundled."))


        extraction_group_layout.addWidget(self.no_playlist_cb)
        extraction_group_layout.addWidget(self.ignore_errors_cb)
        extraction_group_layout.addWidget(self.list_formats_cb)
        extraction_group_layout.addWidget(self.use_ytdlp_exe_cb)
        extraction_group.setLayout(extraction_group_layout)
        ytdlp_layout.addWidget(extraction_group)

        # Download Options groupbox
        download_group = QGroupBox(self.tr("Download Options"))
        download_group_layout = QVBoxLayout()

        # Output template
        out_layout = QHBoxLayout()
        out_label = QLabel(self.tr("Output Template:"))
        self.out_template = QLineEdit("%(title)s.%(ext)s")
        self.out_template.setToolTip(self.tr("Set the naming format for downloaded files."))
        out_layout.addWidget(out_label)
        out_layout.addWidget(self.out_template)

        # Format selection
        format_layout = QHBoxLayout()
        format_label = QLabel(self.tr("Download Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["(bv*+ba/b)est", "(bv*+ba/b)est", 'mp4', 'mp3', 'mkv', 'webm', 'flv', 'avi'])
        self.format_combo.setToolTip(self.tr("Select which format yt-dlp should download."))
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)

        # Proxy
        proxy_layout = QHBoxLayout()
        proxy_label = QLabel(self.tr("Proxy:"))
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("http://127.0.0.1:8080")
        self.proxy_edit.setToolTip(self.tr("Optional: Use a proxy for downloading."))
        proxy_layout.addWidget(proxy_label)
        proxy_layout.addWidget(self.proxy_edit)
        self.ffmpeg_path = QLineEdit()
        self.ffmpeg_path.setPlaceholderText(self.tr("Path to ffmpeg"))
        self.ffmpeg_path.setToolTip(self.tr("Path to ffmpeg executable."))
        proxy_layout.addWidget(self.ffmpeg_path)

        # Fragments
        frag_layout = QHBoxLayout()
        frag_label = QLabel(self.tr("Concurrent Fragments:"))
        self.frag_spin = QSpinBox()
        self.frag_spin.setRange(1, 20)
        self.frag_spin.setValue(5)
        self.frag_spin.setToolTip(self.tr("Number of parallel connections used by yt-dlp."))
        frag_layout.addWidget(frag_label)
        frag_layout.addWidget(self.frag_spin)
        self.retries_label = QLabel(self.tr("Retries:"))
        self.retries = QSpinBox()
        self.retries.setRange(1, 10)
        frag_layout.addWidget(self.retries_label)
        frag_layout.addWidget(self.retries)

        # YT-DLP extra options: 6 checkboxes in 2 rows of 3
        self.enable_quiet = QCheckBox(self.tr("Quiet"))
        self.enable_quiet.setToolTip(self.tr("Suppress output messages."))
        self.write_metadata = QCheckBox(self.tr("Write Metadata"))
        self.write_metadata.setToolTip(self.tr("Add metadata (e.g., title, artist) to the file."))
        self.write_infojson = QCheckBox(self.tr("Write Info JSON"))
        self.write_infojson.setToolTip(self.tr("Save video metadata in JSON format."))
        self.write_description = QCheckBox(self.tr("Write Description"))
        self.write_description.setToolTip(self.tr("Save video description in a separate file."))
        self.write_annotations = QCheckBox(self.tr("Write Annotations"))
        self.write_annotations.setToolTip(self.tr("Save video annotations in a separate file."))
        self.no_warnings = QCheckBox(self.tr("No Warnings"))
        self.no_warnings.setToolTip(self.tr("Suppress warnings during download."))

        ytdlp_checkbox_row1 = QHBoxLayout()
        ytdlp_checkbox_row1.addWidget(self.enable_quiet)
        ytdlp_checkbox_row1.addWidget(self.write_metadata)
        ytdlp_checkbox_row1.addWidget(self.write_infojson)

        ytdlp_checkbox_row2 = QHBoxLayout()
        ytdlp_checkbox_row2.addWidget(self.write_description)
        ytdlp_checkbox_row2.addWidget(self.write_annotations)
        ytdlp_checkbox_row2.addWidget(self.no_warnings)

        self.cookies_path = QLineEdit()
        self.cookies_path.setPlaceholderText(self.tr("Path to cookies.txt"))
        browse_btn = QPushButton(self.tr("Browse"))
        browse_btn.clicked.connect(lambda: self.cookies_path.setText(QFileDialog.getOpenFileName(self, self.tr("Select cookies.txt"), "", self.tr("Text Files (*.txt)"))[0]))
        cookie_layout = QHBoxLayout()
        cookie_layout.addWidget(QLabel(self.tr("Cookies File:")))
        cookie_layout.addWidget(self.cookies_path)
        cookie_layout.addWidget(browse_btn)

        # Assemble download options layout
        download_group_layout.addLayout(out_layout)
        download_group_layout.addLayout(format_layout)
        download_group_layout.addLayout(proxy_layout)
        download_group_layout.addLayout(frag_layout)
        download_group_layout.addLayout(ytdlp_checkbox_row1)
        download_group_layout.addLayout(ytdlp_checkbox_row2)
        download_group_layout.addLayout(cookie_layout)
        download_group.setLayout(download_group_layout)
        ytdlp_layout.addWidget(download_group)

        self.engine_tabs.addTab(self.ytdlp_tab, "YT-DLP")

        # === ARIA2C CONFIG TAB ===
        self.aria2c_tab = QWidget()
        aria_layout = QVBoxLayout(self.aria2c_tab)
        aria_group = QGroupBox(self.tr("General"))
        aria_group_layout = QVBoxLayout()

        max_layout = QHBoxLayout()
        max_label = QLabel(self.tr("Max connections per server:"))
        self.aria_max_spin = QSpinBox()
        self.aria_max_spin.setRange(1, 16)
        self.aria_max_spin.setValue(16)
        self.aria_max_spin.setToolTip(self.tr("Max simultaneous connections per download."))
        max_layout.addWidget(max_label)
        max_layout.addWidget(self.aria_max_spin)

        self.aria_enable_dht = QCheckBox(self.tr("Enable DHT"))
        self.aria_enable_dht.setToolTip(self.tr("Enable peer discovery via DHT for torrents."))
        self.aria_follow_torrent = QCheckBox(self.tr("Follow torrent"))
        self.aria_follow_torrent.setToolTip(self.tr("Automatically follow and fetch data from .torrent files."))

        interval_layout = QHBoxLayout()
        interval_label = QLabel(self.tr("Session Save Interval (s):"))
        self.aria_save_interval_spin = QSpinBox()
        self.aria_save_interval_spin.setRange(10, 3600)
        self.aria_save_interval_spin.setValue(60)
        self.aria_save_interval_spin.setToolTip(self.tr("How often to save active downloads to session file."))
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.aria_save_interval_spin)

        alloc_layout = QHBoxLayout()
        alloc_label = QLabel(self.tr("File Allocation:"))
        self.aria_alloc_combo = QComboBox()
        self.aria_alloc_combo.addItems(["none", "prealloc", "trunc", "falloc"])
        self.aria_alloc_combo.setCurrentText("falloc")
        self.aria_alloc_combo.setToolTip(self.tr("Preallocation method: none, prealloc, trunc, falloc."))
        alloc_layout.addWidget(alloc_label)
        alloc_layout.addWidget(self.aria_alloc_combo)

        split_layout = QHBoxLayout()
        split_label = QLabel(self.tr("Download Split Parts:"))
        self.aria_split_spin = QSpinBox()
        self.aria_split_spin.setRange(1, 64)
        self.aria_split_spin.setValue(32)
        self.aria_split_spin.setToolTip(self.tr("Split each download into this number of parts."))
        split_layout.addWidget(split_label)
        split_layout.addWidget(self.aria_split_spin)

        rpc_layout = QHBoxLayout()
        rpc_label = QLabel(self.tr("RPC Port:"))
        self.aria_rpc_spin = QSpinBox()
        self.aria_rpc_spin.setRange(1024, 65535)
        self.aria_rpc_spin.setValue(6800)
        self.aria_rpc_spin.setToolTip(self.tr("Port for the internal aria2c RPC server."))
        rpc_layout.addWidget(rpc_label)
        rpc_layout.addWidget(self.aria_rpc_spin)

        aria_group_layout.addLayout(max_layout)
        aria_group_layout.addWidget(self.aria_enable_dht)
        aria_group_layout.addWidget(self.aria_follow_torrent)
        aria_group_layout.addLayout(interval_layout)
        aria_group_layout.addLayout(alloc_layout)
        aria_group_layout.addLayout(split_layout)
        aria_group_layout.addLayout(rpc_layout)
        aria_group.setLayout(aria_group_layout)
        aria_layout.addWidget(aria_group)
        self.engine_tabs.addTab(self.aria2c_tab, "Aria2c")

        self.engine_layout.addWidget(self.engine_tabs)
        self.engine_layout.addStretch()
        self.stack.addWidget(self.engine_widget)



    def setup_browser_tab(self):
        browser_widget = QWidget()
        browser_layout = QFormLayout(browser_widget)
        browser_layout.setSpacing(16)

        self.browser_integration_cb = QCheckBox(self.tr("Enable Browser Integration"))
        browser_layout.addRow(self.browser_integration_cb)

        self.stack.addWidget(browser_widget)


    def setup_updates_tab(self):
        updates_widget = QWidget()
        updates_layout = QFormLayout(updates_widget)
        updates_layout.setSpacing(16)

        self.check_interval_combo = QComboBox()
        self.check_interval_combo.addItems(["1", "3", "7", "14"])

        sut1 = self.tr('App Version:')
        self.version_label = QLabel(f"{sut1} {config.APP_VERSION}")
        self.check_update_btn = QPushButton(self.tr("Check for update"))
        self.check_update_btn.setCursor(Qt.PointingHandCursor)

        # --- yt-dlp version check ---
        yt_dlp_version = ""
        yt_dlp_path = getattr(config, "yt_dlp_exe", "") or config.yt_dlp_actual_path
        if yt_dlp_path and os.path.isfile(yt_dlp_path):
            try:
                kwargs = dict(capture_output=True, text=True, timeout=8)
                if sys.platform.startswith("win"):
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = subprocess.SW_HIDE
                    kwargs["startupinfo"] = si
                proc = subprocess.run([yt_dlp_path, "--version"], **kwargs)
                yt_dlp_version = proc.stdout.strip().splitlines()[0] if proc.stdout else ""
            except Exception:
                yt_dlp_version = self.tr("Unknown")
        else:
            yt_dlp_version = self.tr("Not set")

        self.yt_dlp_version_label = QLabel(self.tr("yt-dlp version: ") + yt_dlp_version)
        self.yt_dlp_update_btn = QPushButton(self.tr("Check yt-dlp update"))
        self.yt_dlp_update_btn.setCursor(Qt.PointingHandCursor)
        #self.yt_dlp_update_btn.clicked.connect(self.check_yt_dlp_update)

        updates_layout.addRow(QLabel(self.tr("Check for update every (days):")), self.check_interval_combo)
        # updates_layout.addRow()
        updates_layout.addRow(self.version_label, self.check_update_btn)
        updates_layout.addRow(self.yt_dlp_version_label, self.yt_dlp_update_btn)
        self.stack.addWidget(updates_widget)



    
    def setup_backend_paths_tab(self):
        # TODO Allow users to select their custom cookies.txt and ffmpeg.exe -- Next Version 
        """
        Tab allowing selection of:
        - optional custom yt-dlp executable (checkbox to enable)
        - cookies.txt file 
        - ffmpeg executable

        Adds inline validation labels under each row to show problems.
        Exposes getters:
        - self.get_custom_ytdlp_path()
        - self.get_cookies_path()
        - self.get_ffmpeg_path()
        """
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        def _select_file(target_lineedit: QLineEdit = None,
                        caption: str = "Select file",
                        file_filter: str = "All Files (*)") -> str:
            """Flexible file chooser: if target_lineedit provided, it will be updated.
            NOTE: This function is only called from Browse button handlers, not at startup."""
            initial_dir = None
            if target_lineedit and target_lineedit.text():
                initial_dir = os.path.dirname(target_lineedit.text())
            if not initial_dir or not os.path.exists(initial_dir):
                initial_dir = os.path.expanduser("~")

            parent = tab
            path, _ = QFileDialog.getOpenFileName(parent, caption, initial_dir, file_filter)
            if path and target_lineedit:
                target_lineedit.setText(path)
            return path

        def _make_row(label_text: str, placeholder: str):
            """Create a horizontal row containing a label, QLineEdit and Browse button."""
            row_container = QWidget()
            row_layout = QHBoxLayout(row_container)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            label = QLabel(label_text)
            label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

            line = QLineEdit()
            line.setPlaceholderText(placeholder)

            browse = QPushButton(self.tr("Browse"))
            browse.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            row_layout.addWidget(label)
            row_layout.addWidget(line, 1)
            row_layout.addWidget(browse)
            return row_container, line, browse

        def _make_warning_label():
            lbl = QLabel("")  # empty by default
            lbl.setWordWrap(True)
            lbl.setVisible(False)
            lbl.setStyleSheet("color: rgb(190,0,0); font-size: 11px;")
            return lbl
        
        def _make_success_label():
            lbl = QLabel("")  # empty by default
            lbl.setWordWrap(True)
            lbl.setVisible(False)
            lbl.setStyleSheet("color: rgb(0,190,0); font-size: 11px;")
            return lbl

        # ---------- validators ----------
        def _is_executable_file(path: str) -> bool:
            if not path:
                return False
            if not os.path.isfile(path):
                return False
            try:
                st = os.stat(path)
                # On Windows checking execute bit is unreliable; assume file exists is okay and has .exe
                if sys.platform.startswith("win"):
                    return path.lower().endswith(".exe")
                else:
                    return bool(st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
            except Exception:
                return False

        def _suggest_chmod_cmd(path: str) -> str:
            return f"On Unix run: chmod +x {path}"

        # Try to run '<exe> --version' to check it behaves like yt-dlp/ffmpeg.
        # Uses short timeout so UI won't hang.

        def _probe_exe_for_signature(path: str, expected_keywords: list[str], timeout: float = 8.0) -> tuple[bool, str]:
            if not path or not os.path.isfile(path):
                return False, "File not found."

            args = [path, "--version"]

            kwargs = dict(capture_output=True, text=True, timeout=timeout)
            if sys.platform.startswith("win"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                kwargs["startupinfo"] = si
        
            try:
                proc = subprocess.run(args, **kwargs)
                combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
                for kw in expected_keywords:
                    if kw.lower() in combined.lower():
                        return True, combined.strip()
                return False, combined.strip() or "No output from --version."
            except subprocess.TimeoutExpired:
                return False, "Probe timed out (the executable may block or be slow)."
            except PermissionError:
                return False, "Permission denied when attempting to run the executable."
            except Exception as exc:
                return False, f"Failed to run --version probe: {exc}"


        # ---------- validation functions ----------
        def _validate_yt_path():
            """Validate the yt-dlp path only when the custom checkbox is checked."""
            if not self.yt_checkbox.isChecked():
                self.yt_warning.setVisible(False)
                return True
            
            p = config.get_effective_ytdlp() or self.yt_lineedit.text().strip()

            # p = self.yt_lineedit.text().strip()
            if not p:
                self.yt_warning.setText(self.tr("Custom yt-dlp is enabled but no path was provided."))
                self.yt_warning.setVisible(True)
                return False
            if not os.path.exists(p):
                self.yt_warning.setText(self.tr("The selected yt-dlp path does not exist."))
                self.yt_warning.setVisible(True)
                return False
            if not os.path.isfile(p):
                self.yt_warning.setText(self.tr("Selected yt-dlp path is not a file."))
                self.yt_warning.setVisible(True)
                return False
            if not _is_executable_file(p):
                # Detailed suggestion for permissions
                if sys.platform.startswith("win"):
                    a = self.tr("The selected yt-dlp does not look like an executable (.exe). ")
                    b = self.tr("Make sure you picked the yt-dlp executable file or use the Python module instead.")
                    self.yt_warning.setText(
                        f'{a}'
                        f'{b}'
                    )
                else:
                    self.yt_warning.setText(
                        self.tr("The selected yt-dlp file is not marked executable. ") +
                        _suggest_chmod_cmd(p)
                    )
                self.yt_warning.setVisible(True)
                return False

            # Probe the exe to ensure it behaves like yt-dlp
            suggestion = ""
            if sys.platform.startswith("win"):
                suggestion = self.tr("Ensure this is the yt-dlp executable (filename ends with .exe) or leave blank to use the Python package.")
            else:
                suggestion = _suggest_chmod_cmd(p) + self.tr(" or ensure this binary is yt-dlp.")
            
            pot = self.tr('Probe output:')
            self.yt_warning.setText(
                # f"Selected file did not identify as yt-dlp when probed with '--version'.\n"
                
                f"{pot}\n {suggestion}"
            )
            self.yt_warning.setVisible(True)
            return False
        
            # BUG: Calling the _probe_exe_for_signature delays the program
            # looks_like, msg = _probe_exe_for_signature(p, expected_keywords=["yt-dlp", "yt_dlp.exe", "yt-dlp version"], timeout=8.0)
            # if not looks_like:
            #     # More detailed message: include probe output (shortened) to help debugging
            #     short = (msg[:300] + "...") if msg and len(msg) > 300 else msg
            #     suggestion = ""
            #     if sys.platform.startswith("win"):
            #         suggestion = self.tr("Ensure this is the yt-dlp executable (filename ends with .exe) or leave blank to use the Python package.")
            #     else:
            #         suggestion = _suggest_chmod_cmd(p) + self.tr(" or ensure this binary is yt-dlp.")
                
            #     pot = self.tr('Probe output:')
            #     self.yt_warning.setText(
            #         # f"Selected file did not identify as yt-dlp when probed with '--version'.\n"
                    
            #         f"{pot} {short}\n{suggestion}"
            #     )
            #     self.yt_warning.setVisible(True)
            #     return False

            # # OK
            # self.yt_warning.setVisible(False)
            # return True


        
        def _validate_cookies_path():
            p = self.cookies_lineedit.text().strip()
            if not p:
                # cookies are optional — hide warning for empty
                self.cookies_warning.setVisible(False)
                return True
            if not os.path.exists(p):
                self.cookies_warning.setText("cookies.txt not found at the selected path.")
                self.cookies_warning.setVisible(True)
                return False
            if not os.path.isfile(p):
                self.cookies_warning.setText("Selected cookies path is not a regular file.")
                self.cookies_warning.setVisible(True)
                return False
            try:
                size = os.path.getsize(p)
                if size == 0:
                    self.cookies_warning.setText("cookies.txt is empty.")
                    self.cookies_warning.setVisible(True)
                    return False
            except Exception:
                self.cookies_warning.setText("Unable to read cookies file.")
                self.cookies_warning.setVisible(True)
                return False
            # OK
            self.cookies_warning.setVisible(False)
            return True

        def _validate_ffmpeg_path():
            p = self.ffmpeg_lineedit.text().strip()
            if not p:
                # empty means "use system ffmpeg" — OK
                self.ffmpeg_warning.setVisible(False)
                return True
            if not os.path.exists(p):
                self.ffmpeg_warning.setText("ffmpeg path does not exist.")
                self.ffmpeg_warning.setVisible(True)
                return False
            if not os.path.isfile(p):
                self.ffmpeg_warning.setText("Selected ffmpeg is not a file.")
                self.ffmpeg_warning.setVisible(True)
                return False
            if not _is_executable_file(p):
                if sys.platform.startswith("win"):
                    self.ffmpeg_warning.setText(
                        "The selected ffmpeg does not look like an executable (.exe). Make sure you selected ffmpeg binary."
                    )
                else:
                    self.ffmpeg_warning.setText(
                        "The selected ffmpeg is not executable. " + _suggest_chmod_cmd(p)
                    )
                self.ffmpeg_warning.setVisible(True)
                return False

            # Probe the binary for ffmpeg signature
            looks_like, msg = _probe_exe_for_signature(p, expected_keywords=["ffmpeg", "ffmpeg version"])
            if not looks_like:
                short = (msg[:300] + "...") if msg and len(msg) > 300 else msg
                self.ffmpeg_warning.setText(
                    f"Selected file did not identify as ffmpeg when probed with '--version'.\n"
                    f"Probe output: {short}\n"
                    "If this is a wrapper, ensure it forwards --version or select the real ffmpeg binary."
                )
                self.ffmpeg_warning.setVisible(True)
                return False

            self.ffmpeg_warning.setVisible(False)
            return True

        def _validate_all():
            # returns True if everything valid
            a = _validate_yt_path()
            # b = _validate_cookies_path()
            # c = _validate_ffmpeg_path()
            return a # and b and c 

        # ---------- yt-dlp UI ----------
        yt_group = QGroupBox(self.tr("yt-dlp (optional custom path)"))
        yt_layout = QVBoxLayout(yt_group)
        yt_layout.setContentsMargins(6, 6, 6, 6)
        yt_layout.setSpacing(6)

        self.yt_checkbox = QCheckBox(self.tr("Use custom yt-dlp executable"))
        yt_layout.addWidget(self.yt_checkbox)

        yt_row_widget, self.yt_lineedit, self.yt_browse_btn = _make_row(
            "yt-dlp:", "Path to yt-dlp executable (leave blank to use bundled/default)"
        )

        # Prefill from config if available (no dialogs at startup)
        try:
            initial = getattr(config, "yt_dlp_exe", "") or ""
            if initial:
                self.yt_lineedit.setText(initial)
                # enable checkbox if user already has a saved exe
                self.yt_checkbox.setChecked(True)
        except Exception:
            pass

        self.yt_lineedit.setEnabled(self.yt_checkbox.isChecked())
        self.yt_browse_btn.setEnabled(self.yt_checkbox.isChecked())

        if sys.platform.startswith("win"):
            yt_filter = "Executables (*.exe);;All Files (*)"
        else:
            yt_filter = "All Files (*)"

        # Browse handler: called when user clicks Browse
        def _on_browse_yt():
            selected = _select_file(self.yt_lineedit, "Select yt-dlp executable", yt_filter)
            if not selected:
                return

            # Set the UI lineedit immediately
            self.yt_lineedit.setText(selected)

            # Tell config about the user-selected path and resolve the effective path
            # (this updates config.yt_dlp_exe and config.yt_dlp_actual_path via set_user_ytdlp)
            resolved = config.set_user_ytdlp(selected)

            # If resolution failed, still store the literal path in legacy var (keeps older code happy)
            if not resolved:
                config.yt_dlp_exe = selected
            else:
                # keep legacy variable in sync
                config.yt_dlp_exe = resolved

            # Optionally prefer the exe immediately when a user chooses one
            config.use_ytdlp_exe = True

            # Run the validator which will show inline warnings if the file is not executable/valid
            _validate_yt_path()


        self.yt_browse_btn.clicked.connect(_on_browse_yt)
        # toggle enabling of widgets and validate when toggled
        self.yt_checkbox.toggled.connect(lambda checked: (
            self.yt_lineedit.setEnabled(checked),
            self.yt_browse_btn.setEnabled(checked),
            _validate_yt_path()
        ))
        

        # inline warning label for yt-dlp
        self.yt_warning = _make_warning_label()
        self.yt_success = _make_success_label()
        yt_layout.addWidget(yt_row_widget)
        yt_layout.addWidget(self.yt_warning)
        yt_layout.addWidget(self.yt_success)
        main_layout.addWidget(yt_group)

        # ---------- cookies UI ----------
        cookies_group = QGroupBox("Cookies")
        cookies_layout = QVBoxLayout(cookies_group)
        cookies_layout.setContentsMargins(6, 6, 6, 6)
        cookies_layout.setSpacing(6)

        cookies_row_widget, self.cookies_lineedit, self.cookies_browse_btn = _make_row(
            "cookies.txt:", "Path to cookies.txt (Optional)"
        )
        # Prefill cookies path from config if available
        try:
            initial_c = getattr(config, "cookies_path", "") or ""
            if initial_c:
                self.cookies_lineedit.setText(initial_c)
        except Exception:
            pass

        cookies_filter = "Cookies files (*.txt);;All Files (*)"
        def _on_browse_cookies():
            selected = _select_file(self.cookies_lineedit, "Select cookies.txt file", cookies_filter)
            if not selected:
                return
            # Save chosen path to config if you want
            try:
                config.cookies_path = selected
            except Exception:
                pass
            _validate_cookies_path()

        self.cookies_browse_btn.clicked.connect(_on_browse_cookies)

        self.cookies_warning = _make_warning_label()
        cookies_layout.addWidget(cookies_row_widget)
        cookies_layout.addWidget(self.cookies_warning)
        # main_layout.addWidget(cookies_group)

        # ---------- ffmpeg UI ----------
        ffmpeg_group = QGroupBox("ffmpeg")
        ffmpeg_layout = QVBoxLayout(ffmpeg_group)
        ffmpeg_layout.setContentsMargins(6, 6, 6, 6)
        ffmpeg_layout.setSpacing(6)

        ff_row_widget, self.ffmpeg_lineedit, self.ffmpeg_browse_btn = _make_row(
            "ffmpeg:", "Path to ffmpeg executable (leave blank to use system ffmpeg)"
        )

        # Prefill ffmpeg from config if available
        try:
            initial_ff = getattr(config, "ffmpeg_path", "") or ""
            if initial_ff:
                self.ffmpeg_lineedit.setText(initial_ff)
        except Exception:
            pass

        if sys.platform.startswith("win"):
            ff_filter = "Executables (*.exe);;All Files (*)"
        else:
            ff_filter = "All Files (*)"

        def _on_browse_ffmpeg():
            selected = _select_file(self.ffmpeg_lineedit, "Select ffmpeg executable", ff_filter)
            if not selected:
                return
            try:
                config.ffmpeg_path = selected
            except Exception:
                pass
            _validate_ffmpeg_path()

        self.ffmpeg_browse_btn.clicked.connect(_on_browse_ffmpeg)

        self.ffmpeg_warning = _make_warning_label()
        ffmpeg_layout.addWidget(ff_row_widget)
        ffmpeg_layout.addWidget(self.ffmpeg_warning)
        # main_layout.addWidget(ffmpeg_group)

        main_layout.addStretch(1)

        # ---------- wire live validation ----------
        # Validate when text changes (user typed or browse set text)
        self.yt_lineedit.textChanged.connect(_validate_yt_path)
        # self.cookies_lineedit.textChanged.connect(_validate_cookies_path)
        # self.ffmpeg_lineedit.textChanged.connect(_validate_ffmpeg_path)

        # Also validate once on creation to show any initial issues
        _validate_all()

        # ---------- getters ----------
        def _get_yt_path():
            return self.yt_lineedit.text().strip() if self.yt_checkbox.isChecked() else ""

        def _get_cookies_path():
            return self.cookies_lineedit.text().strip()

        def _get_ffmpeg_path():
            return self.ffmpeg_lineedit.text().strip()

        self.get_custom_ytdlp_path = _get_yt_path
        # self.get_cookies_path = _get_cookies_path
        # self.get_ffmpeg_path = _get_ffmpeg_path

        # Add tab to the stack 
        self.stack.addWidget(tab)



    def dark_stylesheet(self):
        return """
        QDialog {
            background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
            );
            border-radius: 16px;
        }

        QLabel, QCheckBox {
            color: rgba(220, 255, 230, 210);
            font-size: 13px;
        }

        QComboBox, QSpinBox, QLineEdit {
            background-color: rgba(28, 28, 30, 0.55);  /* Neutral frosted charcoal */
            color: #e0e0e0;
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            padding: 6px 10px;
        }

        QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
            border: 1px solid rgba(111, 255, 176, 0.18);  /* subtle emerald glow on hover */
        }

        QComboBox::drop-down {
            border: none;
            background-color: transparent;
        }

        QComboBox QAbstractItemView {
            background-color: rgba(20, 25, 20, 0.95);
            border: 1px solid rgba(60, 200, 120, 0.25);
            selection-background-color: #2DE099;
            color: white;
        }


        QPushButton {
            background-color: rgba(0, 128, 96, 0.4);
            color: white;
            font-weight: bold;
            border: 1px solid rgba(0, 255, 180, 0.1);
            border-radius: 8px;
            padding: 6px 18px;
        }

        QPushButton:hover {
            background-color: rgba(0, 192, 128, 0.6);
        }

        QListWidget {
            background-color: transparent;
            color: white;
            font-size: 14px;
            border: none;
        }

        QListWidget::item {
            padding: 10px;
            height: 32px;
        }

        QListWidget::item:hover {
            background-color: rgba(111, 255, 176, 0.08);
            color: #88ffaa;
        }

        QListWidget::item:selected {
            background-color: rgba(45, 224, 153, 0.1);
            color: #6FFFB0;
            padding-left: 6px;
            margin: 0px;
            border: none;
        }
        QSPinBox {
            background-color: rgba(28, 28, 30, 0.55);
            color: #e0e0e0;
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 14px; 
            height: 30px;
        }
        QTabWidget::pane {
            border: none;
        }
        QTabBar::tab {
            background: transparent;
            padding: 6px 12px;
            margin-right: 1px;
            color: white;
        }
        QTabBar::tab:selected {
            background: #005c4b;
            border-radius: 4px;
        }
        QGroupBox {
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
            margin-top: 20px;
        }
        QGroupBox:title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 4px 10px;
            color: #9eeedc;
            font-weight: bold;
        }
        QToolTip {
            color: white;
            background-color: #444444;
            border: 1px solid white;
            padding: 4px;
            border-radius: 4px;
        }

        """

    
    def load_values(self, config):
        self.qt_font_dpi.setCurrentText(str(config.APP_FONT_DPI))
        self.language_combo.setCurrentText(str(config.lang))
        self.monitor_clipboard_cb.setChecked(config.monitor_clipboard)
        self.show_download_window_cb.setChecked(config.show_download_window)
        self.auto_close_cb.setChecked(config.auto_close_download_window)
        self.show_thumbnail_cb.setChecked(config.show_thumbnail)
        self.on_startup_cb.setChecked(config.on_startup)
        self.show_all_logs.setChecked(config.show_all_logs)
        self.hide_app_cb.setChecked(config.hide_app)
        self.download_engine_combo.setCurrentText(config.download_engine)
        self.setting_scope_combo.setCurrentText('Global' if config.sett_folder == config.global_sett_folder else 'Local')
        self.curl_proxy_checkBox.setChecked(config.enable_proxy)
        self.curl_proxy_input.setText(config.proxy or '')
        self.curl_proxy_type_combo.setCurrentText(config.proxy_type or 'http')
        self.curl_proxy_username.setText(config.proxy_user or '')
        self.curl_proxy_password.setText(config.proxy_pass or '')

        seg_size = config.segment_size // 1024
        if seg_size >= 1024:
            seg_size = seg_size // 1024
            seg_unit = 'MB'
        else:
            seg_unit = 'KB'
        
        self.curl_speed_checkBox.setChecked(config.enable_speed_limit)
        self.curl_speed_limit.setText(str(config.speed_limit))
        self.curl_max_concurrent.setCurrentText(str(config.max_concurrent_downloads))
        self.curl_max_connections.setCurrentText(str(config.max_connections))
        self.curl_segment_size.setText(str(seg_size))
        self.curl_segment_size_combo.setCurrentText(seg_unit)
        self.curl_retry_schedule_cb.setChecked(config.retry_scheduled_enabled)
        self.curl_retry_count_spin.setValue(config.retry_scheduled_max_tries)
        self.curl_retry_interval_spin.setValue(config.retry_scheduled_interval_mins)


        # YT-DLP settings
        self.no_playlist_cb.setChecked(config.ytdlp_config['no_playlist'])
        self.ignore_errors_cb.setChecked(config.ytdlp_config['ignore_errors'])
        self.list_formats_cb.setChecked(config.ytdlp_config['list_formats'])
        self.use_ytdlp_exe_cb.setChecked(config.use_ytdlp_exe)
        self.out_template.setText(config.ytdlp_config['outtmpl'])
        self.format_combo.setCurrentText(config.ytdlp_config['merge_output_format'])
        self.frag_spin.setValue(config.ytdlp_config['concurrent_fragment_downloads'])
        self.retries.setValue(config.ytdlp_config['retries'])
        self.enable_quiet.setChecked(config.ytdlp_config['quiet'])
        self.write_metadata.setChecked(config.ytdlp_config['writemetadata'])
        self.write_infojson.setChecked(config.ytdlp_config['writeinfojson'])
        self.write_description.setChecked(config.ytdlp_config['writedescription'])
        self.write_annotations.setChecked(config.ytdlp_config['writeannotations'])
        self.no_warnings.setChecked(config.ytdlp_config['no_warnings'])
        self.ffmpeg_path.setText(config.ytdlp_config['ffmpeg_location'] if config.ytdlp_config['ffmpeg_location'] else '')
        if config.proxy != "":
            proxy_url = config.proxy
            if config.proxy_user and config.proxy_pass:
                # Inject basic auth into the proxy URL
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(proxy_url)
                proxy_url = urlunparse(parsed._replace(netloc=f"{config.proxy_user}:{config.proxy_pass}@{parsed.hostname}:{parsed.port}"))

                self.proxy_edit.setText(proxy_url if proxy_url else '')
        else:
            self.proxy_edit.setText('')
       
        self.cookies_path.setText(config.ytdlp_config['cookiesfile'] if config.ytdlp_config['cookiesfile'] else '')

        # Aria2c settings
        self.aria_max_spin.setValue(config.aria2c_config['max_connections'])
        self.aria_enable_dht.setChecked(config.aria2c_config['enable_dht'])
        self.aria_follow_torrent.setChecked(config.aria2c_config['follow_torrent'])
        self.aria_save_interval_spin.setValue(config.aria2c_config['save_interval'])
        self.aria_rpc_spin.setValue(config.aria2c_config['rpc_port'])
        self.aria_split_spin.setValue(config.aria2c_config['split'])
        self.aria_alloc_combo.setCurrentText(config.aria2c_config['file_allocation'])

        # Browser Integration
        self.browser_integration_cb.setChecked(config.browser_integration_enabled)

        # Backend Paths
        self.yt_checkbox.setChecked(config.enable_ytdlp_exe)
        self.yt_lineedit.setText(config.yt_dlp_exe if config.yt_dlp_exe else '')

        # Check for updates settings
        self.check_interval_combo.setCurrentText(str(config.update_frequency))


    
    def accept(self):
        """Override the accept method to apply and save settings when OK is clicked."""

        self.settings_folder()  
        config.APP_FONT_DPI = self.qt_font_dpi.currentText()
        config.lang = self.language_combo.currentText()
        config.monitor_clipboard = self.monitor_clipboard_cb.isChecked()
        config.show_download_window = self.show_download_window_cb.isChecked()
        config.auto_close_download_window = self.auto_close_cb.isChecked()
        config.show_thumbnail = self.show_thumbnail_cb.isChecked()
        config.on_startup = self.on_startup_cb.isChecked()
        config.show_all_logs = self.show_all_logs.isChecked()
        config.hide_app = self.hide_app_cb.isChecked()
        config.download_engine = self.download_engine_combo.currentText()
        config.enable_proxy = self.curl_proxy_checkBox.isChecked()
        config.proxy = self.curl_proxy_input.text() if self.curl_proxy_checkBox.isChecked() else ""
        config.proxy_type = self.curl_proxy_type_combo.currentText()
        config.proxy_user = self.curl_proxy_username.text() if self.curl_proxy_checkBox.isChecked() else ""
        config.proxy_pass = self.curl_proxy_password.text() if self.curl_proxy_checkBox.isChecked() else ""

       

        # Segment
        try:
            seg_size = int(self.curl_segment_size.text())
            seg_multiplier = 1024 if self.curl_segment_size_combo.currentText() == "KB" else 1024 * 1024
            config.segment_size = seg_size * seg_multiplier
        except ValueError:
            config.segment_size = 512 * 1024  # fallback default

        # Engine Config settings

        # PyCurl settings
        
        config.enable_speed_limit = self.curl_speed_checkBox.isChecked()
        if config.enable_speed_limit:
            config.speed_limit = self.curl_speed_limit.text()
        else:
            config.speed_limit = ""
        # config.speed_limit = self.curl_speed_limit.text()
        config.max_concurrent_downloads = int(self.curl_max_concurrent.currentText())
        config.max_connections = int(self.curl_max_connections.currentText())
        config.retry_scheduled_enabled = self.curl_retry_schedule_cb.isChecked()
        config.retry_scheduled_max_tries = self.curl_retry_count_spin.value()
        config.retry_scheduled_interval_mins = self.curl_retry_interval_spin.value()

        # YT-DLP settings
        config.ytdlp_config['no_playlist'] = self.no_playlist_cb.isChecked()
        config.ytdlp_config['ignore_errors'] = self.ignore_errors_cb.isChecked()
        config.ytdlp_config['list_formats'] = self.list_formats_cb.isChecked()
        config.use_ytdlp_exe = self.use_ytdlp_exe_cb.isChecked()
        config.ytdlp_config['outtmpl'] = self.out_template.text()
        config.ytdlp_config['merge_output_format'] = self.format_combo.currentText()
        config.ytdlp_config['concurrent_fragment_downloads'] = self.frag_spin.value()
        config.ytdlp_config['retries'] = self.retries.value()
        config.ytdlp_config['quiet'] = self.enable_quiet.isChecked()
        config.ytdlp_config['writemetadata'] = self.write_metadata.isChecked()
        config.ytdlp_config['writeinfojson'] = self.write_infojson.isChecked()
        config.ytdlp_config['writedescription'] = self.write_description.isChecked()
        config.ytdlp_config['writeannotations'] = self.write_annotations.isChecked()
        config.ytdlp_config['no_warnings'] = self.no_warnings.isChecked()
        config.ytdlp_config['ffmpeg_location'] = self.ffmpeg_path.text() if self.ffmpeg_path.text() else None
        if config.proxy:
            proxy_url = config.proxy
            if config.proxy_user and config.proxy_pass:
                # Inject basic auth into the proxy URL
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(proxy_url)
                proxy_url = urlunparse(parsed._replace(netloc=f"{config.proxy_user}:{config.proxy_pass}@{parsed.hostname}:{parsed.port}"))
                config.ytdlp_config['proxy'] = proxy_url
            else:
                config.ytdlp_config['proxy'] = config.proxy
        
        config.ytdlp_config['cookiesfile'] = self.cookies_path.text() if self.cookies_path.text() else None


        # Aria2c settings
        config.aria2c_config['max_connections'] = self.aria_max_spin.value()
        config.aria2c_config['enable_dht'] = self.aria_enable_dht.isChecked()
        config.aria2c_config['follow_torrent'] = self.aria_follow_torrent.isChecked()
        config.aria2c_config['save_interval'] = self.aria_save_interval_spin.value()
        config.aria2c_config['rpc_port'] = self.aria_rpc_spin.value()
        config.aria2c_config['split'] = self.aria_split_spin.value()
        config.aria2c_config['file_allocation'] = self.aria_alloc_combo.currentText()
        
        
        # Browser Integration
        config.browser_integration_enabled = self.browser_integration_cb.isChecked()

        # Backend Paths
        config.yt_dlp_exe = self.yt_lineedit.text().strip()
        config.enable_ytdlp_exe = self.yt_checkbox.isChecked()

        # Check for updates settings
        config.update_frequency = int(self.check_interval_combo.currentText())
        



        # Save settings to disk
        # setting.save_setting()
        self.settings_manager.save_settings()

        main_window = self.parent()  # get reference to the main window
        if main_window:
            main_window.apply_language(config.lang)
            self.retrans()

        super().accept()


    def resource_path2(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)


    def apply_language(self, language):
        QCoreApplication.instance().removeTranslator(self.translator)

        file_map = {
            "French": "app_fr.qm",
            "Spanish": "app_es.qm",
            "Chinese": "app_zh.qm",
            "Korean": "app_ko.qm",
            "Japanese": "app_ja.qm",
            "English": "app_en.qm",
            "Hindi": "app_hi.qm"
        }

        if language in file_map:
            qm_path = self.resource_path2(f"../modules/translations/{file_map[language]}")
            if self.translator.load(qm_path):
                QCoreApplication.instance().installTranslator(self.translator)
                # log(f"[Language] Loaded {language}")
            else:
                pass

       

        self.retrans()

    def retrans(self):
        self.setWindowTitle(self.tr("Settings"))
        # self.ok_button.setText(self.tr("OK"))
        # self.cancel_button.setText(self.tr("Cancel"))

        self.sidebar.item(0).setText(self.tr("General"))
        self.sidebar.item(1).setText(self.tr("Engine Config"))
        self.sidebar.item(2).setText(self.tr("Backend Paths"))
        self.sidebar.item(3).setText(self.tr("Browser"))
        self.sidebar.item(4).setText(self.tr("Updates"))

        # General Tab
        self.monitor_clipboard_cb.setText(self.tr("Monitor Copied URLs"))
        self.show_download_window_cb.setText(self.tr("Show Download Window"))
        self.auto_close_cb.setText(self.tr("Auto Close DL Window"))
        self.show_thumbnail_cb.setText(self.tr("Show Thumbnail"))
        self.on_startup_cb.setText(self.tr("On Startup"))
        self.show_all_logs.setText(self.tr("Show all logs"))
        self.hide_app_cb.setText(self.tr('Hide App'))
        self.curl_proxy_checkBox.setText(self.tr("Use Proxy"))
        self.curl_proxy_input.setPlaceholderText(self.tr("Enter proxy..."))
        self.curl_proxy_type_combo.setItemText(0, self.tr("http"))
        self.curl_proxy_type_combo.setItemText(1, self.tr("https"))
        self.curl_proxy_type_combo.setItemText(2, self.tr("socks5"))


        # Download Engines
        self.curl_speed_checkBox.setText(self.tr("Speed Limit"))
        self.curl_conn_label.setText(self.tr("Max Concurrent Downloads:"))
        self.curl_conn_label2.setText(self.tr("Max Connections Settings:"))
        self.curl_segment_label.setText(self.tr("Segment Size:"))
        self.curl_segment_size.setPlaceholderText(self.tr("e.g., 50k, 10k..."))
        self.curl_segment_size_combo.setItemText(0, self.tr("KB"))
        self.curl_segment_size_combo.setItemText(1, self.tr("MB"))
        self.curl_proxy_checkBox.setText(self.tr("Use Proxy"))
        self.curl_proxy_input.setPlaceholderText(self.tr("Enter proxy..."))
        self.curl_retry_schedule_cb.setText(self.tr("Retry failed scheduled downloads"))

        
        
        

        # Retry labels
        # self.stack.widget(1).layout().labelForField(self.max_concurrent_combo).setText(self.tr("Max Concurrent Downloads:"))
        # self.stack.widget(1).layout().labelForField(self.max_conn_settings_combo).setText(self.tr("Max Connection Settings:"))

        # Updates Tab
        self.check_update_btn.setText(self.tr("Check for update"))
        self.stack.widget(4).layout().labelForField(self.check_interval_combo).setText(self.tr("Check for update every (days):"))

        # Language label and others
        self.stack.widget(0).layout().labelForField(self.language_combo).setText(self.tr("Choose Language:"))
        self.stack.widget(0).layout().labelForField(self.setting_scope_combo).setText(self.tr("Choose Setting:"))
        # self.stack.widget(0).layout().labelForField(self.segment_linedit.parent()).setText(self.tr("Segment:"))


    def on_call_update(self):
        # Call the update function from the main window
        config.main_window_q.put(("update call", ""))
        # Close the settings window after calling the update function
        self.close()

    def on_call_ytdlp_update(self):
        # Call the yt-dlp update function from the main window
        config.main_window_q.put(("yt-dlp update call", ""))
        # Close the settings window after calling the update function
        self.close()
        
        

    # region settings
    def settings_folder(self):
        selected = self.setting_scope_combo.currentText()

        if selected == "Local":
            config.sett_folder = config.current_directory
            delete_file(os.path.join(config.global_sett_folder, 'setting.cfg'))
        else:
            config.sett_folder = config.global_sett_folder
            delete_file(os.path.join(config.current_directory, 'setting.cfg'))

            if not os.path.isdir(config.global_sett_folder):
                try:
                    sf1, sf2 = self.tr('Folder:'), self.tr('will be created')
                    choice = QMessageBox.question(
                        self, self.tr('Create Folder'),
                        f'{sf1} {config.global_sett_folder}\n {sf2}',
                        QMessageBox.Ok | QMessageBox.Cancel
                    )

                    if choice == QMessageBox.Ok:
                        os.makedirs(config.global_sett_folder, exist_ok=True)  # ✅ This prevents error if it already exists
                    else:
                        raise Exception('Operation Cancelled by User')

                except Exception as e:
                    log(f'global setting folder error: {e}', log_level=3)
                    config.sett_folder = config.current_directory
                    sf3, sf4 = self.tr('Error while creating global settings folder'), self.tr('Local folder will be used instead')
                    QMessageBox.critical(
                        self, self.tr('Error'),
                        f'{sf3} \n"{config.global_sett_folder}"\n{str(e)}\n {sf4}'
                    )
                    self.setting_scope_combo.setCurrentText('Local')

        try:
            self.setting_scope_combo.setCurrentText('Global' if config.sett_folder == config.global_sett_folder else 'Local')
        except:
            pass
