from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QCheckBox,
    QSpinBox, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QStackedWidget, QFrame, QMessageBox,
    QGroupBox,  QTabWidget, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QCoreApplication, QTranslator
import os, sys

from modules.utils import log, delete_file
from modules import config, setting
from modules.settings_manager import SettingsManager

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
            padding-left: 6px;
            margin: 0px;
            border: none;
            }
        """)

        icon_map = {
            self.tr("General"): "icons/general.png",
            self.tr("Engine Config"): "icons/cil-link.png",
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
        self.setup_browser_tab()
        self.setup_updates_tab()
        self.check_update_btn.clicked.connect(self.on_call_update)


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
        self.language_combo.addItems(["English","Chinese", "Spanish", "Korean", "French", "Japanese"])

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
        download_engine.addItems(["yt-dlp", "aria2", "wget", "curl"])
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
        # general_layout.addRow(self.monitor_clipboard_cb)
        # general_layout.addRow(self.show_download_window_cb)
        # general_layout.addRow(self.auto_close_cb)
        # general_layout.addRow(self.show_thumbnail_cb)
        # general_layout.addRow(self.on_startup_cb)
        # Add rows to general_layout
        general_layout.addRow(row1_layout)
        general_layout.addRow(row2_layout) 
        general_layout.addRow(row3_layout)
        # general_layout.addRow(row4_layout)
        general_layout.addRow(QLabel("Download Engine:"), download_engine)
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
        self.curl_speed_limit.setPlaceholderText(self.tr("e.g., 50k, 10k..."))
        self.curl_speed_limit.setToolTip(self.tr("Set a speed limit for curl downloads."))
        self.curl_speed_limit.setEnabled(False)  # initially disabled
        self.curl_speed_checkBox.toggled.connect(self.curl_speed_limit.setEnabled)
        curl_speed_layout.addWidget(self.curl_speed_checkBox)
        curl_speed_layout.addWidget(self.curl_speed_limit)
        curl_group_layout.addLayout(curl_speed_layout)

        # Max Concurrent Downloads & Max Connections
        # Max Concurrent Downloads row
        curl_concurrent_layout = QHBoxLayout()
        self.curl_conn_label = QLabel(self.tr("Max Concurrent Downloads:"))
        self.curl_max_concurrent = QComboBox()
        self.curl_max_concurrent.addItems(["1", "2", "3", "4", "5"])
        curl_concurrent_layout.addWidget(self.curl_conn_label)
        curl_concurrent_layout.addWidget(self.curl_max_concurrent)
        curl_group_layout.addLayout(curl_concurrent_layout)

        # Max Connections row
        curl_connections_layout = QHBoxLayout()
        self.curl_conn_label2 = QLabel(self.tr("Max Connections Settings:"))
        self.curl_max_connections = QComboBox()
        self.curl_max_connections.addItems(["8", "16", "32", "64"])
        curl_connections_layout.addWidget(self.curl_conn_label2)
        curl_connections_layout.addWidget(self.curl_max_connections)
        curl_group_layout.addLayout(curl_connections_layout)

        # Segment Size row
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

        # Enable/disable retry spin boxes based on checkbox state
        self.curl_retry_schedule_cb.toggled.connect(self.curl_retry_count_spin.setEnabled)
        self.curl_retry_schedule_cb.toggled.connect(self.curl_retry_interval_spin.setEnabled)

        curl_group_layout.addWidget(self.curl_retry_schedule_cb)

        self.curl_retry_row = QHBoxLayout()
        self.curl_retry_row.addWidget(QLabel(self.tr("Max retries:")))
        self.curl_retry_row.addWidget(self.curl_retry_count_spin)
        self.curl_retry_row.addSpacing(20)
        self.curl_retry_row.addWidget(QLabel(self.tr("Interval (Days):")))
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

        ytdlp_group = QGroupBox(self.tr("General"))
        ytdlp_group_layout = QVBoxLayout()

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

        # Arrange checkboxes in 2 rows of 3
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
        


        # Assemble layout
        ytdlp_group_layout.addLayout(out_layout)
        ytdlp_group_layout.addLayout(format_layout)
        ytdlp_group_layout.addLayout(proxy_layout)
        ytdlp_group_layout.addLayout(frag_layout)
        ytdlp_group_layout.addLayout(ytdlp_checkbox_row1)
        ytdlp_group_layout.addLayout(ytdlp_checkbox_row2)
        ytdlp_group_layout.addLayout(cookie_layout)
        ytdlp_group.setLayout(ytdlp_group_layout)
        ytdlp_layout.addWidget(ytdlp_group)
        self.engine_tabs.addTab(self.ytdlp_tab, "YT-DLP")

        # === ARIA2C CONFIG TAB ===
        self.aria2c_tab = QWidget()
        aria_layout = QVBoxLayout(self.aria2c_tab)
        aria_group = QGroupBox(self.tr("General"))
        aria_group_layout = QVBoxLayout()

        # Max connections
        max_layout = QHBoxLayout()
        max_label = QLabel(self.tr("Max connections per server:"))
        self.aria_max_spin = QSpinBox()
        self.aria_max_spin.setRange(1, 16)
        self.aria_max_spin.setValue(16)
        self.aria_max_spin.setToolTip(self.tr("Max simultaneous connections per download."))
        max_layout.addWidget(max_label)
        max_layout.addWidget(self.aria_max_spin)

        # Other settings
        self.aria_enable_dht = QCheckBox(self.tr("Enable DHT"))
        self.aria_enable_dht.setToolTip(self.tr("Enable peer discovery via DHT for torrents."))
        self.aria_follow_torrent = QCheckBox(self.tr("Follow torrent"))
        self.aria_follow_torrent.setToolTip(self.tr("Automatically follow and fetch data from .torrent files."))

        # Session save interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel(self.tr("Session Save Interval (s):"))
        self.aria_save_interval_spin = QSpinBox()
        self.aria_save_interval_spin.setRange(10, 3600)
        self.aria_save_interval_spin.setValue(60)
        self.aria_save_interval_spin.setToolTip(self.tr("How often to save active downloads to session file."))
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.aria_save_interval_spin)

        # File allocation
        alloc_layout = QHBoxLayout()
        alloc_label = QLabel("File Allocation:")
        self.aria_alloc_combo = QComboBox()
        self.aria_alloc_combo.addItems(["none", "prealloc", "trunc", "falloc"])
        self.aria_alloc_combo.setCurrentText("falloc")
        self.aria_alloc_combo.setToolTip(self.tr("Preallocation method: none, prealloc, trunc, falloc."))
        alloc_layout.addWidget(alloc_label)
        alloc_layout.addWidget(self.aria_alloc_combo)

        # Split
        split_layout = QHBoxLayout()
        split_label = QLabel(self.tr("Download Split Parts:"))
        self.aria_split_spin = QSpinBox()
        self.aria_split_spin.setRange(1, 64)
        self.aria_split_spin.setValue(32)
        self.aria_split_spin.setToolTip(self.tr("Split each download into this number of parts."))
        split_layout.addWidget(split_label)
        split_layout.addWidget(self.aria_split_spin)

        # RPC Port
        rpc_layout = QHBoxLayout()
        rpc_label = QLabel(self.tr("RPC Port:"))
        self.aria_rpc_spin = QSpinBox()
        self.aria_rpc_spin.setRange(1024, 65535)
        self.aria_rpc_spin.setValue(6800)
        self.aria_rpc_spin.setToolTip(self.tr("Port for the internal aria2c RPC server."))
        rpc_layout.addWidget(rpc_label)
        rpc_layout.addWidget(self.aria_rpc_spin)

        # Assemble aria layout
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

        # Add all to layout
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

    
        updates_layout.addRow(QLabel(self.tr("Check for update every (days):")), self.check_interval_combo)
        updates_layout.addRow(self.version_label)
        updates_layout.addRow(self.check_update_btn)
        self.stack.addWidget(updates_widget)

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
        if config.proxy:
            proxy_url = config.proxy
            if config.proxy_user and config.proxy_pass:
                # Inject basic auth into the proxy URL
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(proxy_url)
                proxy_url = urlunparse(parsed._replace(netloc=f"{config.proxy_user}:{config.proxy_pass}@{parsed.hostname}:{parsed.port}"))

                print(f"Proxy URL: {proxy_url}")
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
        config.speed_limit = self.curl_speed_limit.text()
        config.max_concurrent_downloads = int(self.curl_max_concurrent.currentText())
        config.max_connections = int(self.curl_max_connections.currentText())
        config.retry_scheduled_enabled = self.curl_retry_schedule_cb.isChecked()
        config.retry_scheduled_max_tries = self.curl_retry_count_spin.value()
        config.retry_scheduled_interval_mins = self.curl_retry_interval_spin.value()

        # YT-DLP settings
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
        }

        if language in file_map:
            qm_path = self.resource_path2(f"../modules/translations/{file_map[language]}")
            if self.translator.load(qm_path):
                QCoreApplication.instance().installTranslator(self.translator)
                print(f"[Language] Loaded {language} translation.")
            else:
                print(f"[Language] Failed to load {qm_path}")

       

        self.retrans()

    def retrans(self):
        self.setWindowTitle(self.tr("Settings"))
        # self.ok_button.setText(self.tr("OK"))
        # self.cancel_button.setText(self.tr("Cancel"))

        self.sidebar.item(0).setText(self.tr("General"))
        self.sidebar.item(1).setText(self.tr("Engine Config"))
        self.sidebar.item(2).setText(self.tr("Browser"))
        self.sidebar.item(3).setText(self.tr("Updates"))

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
        self.stack.widget(3).layout().labelForField(self.check_interval_combo).setText(self.tr("Check for update every (days):"))

        # Language label and others
        self.stack.widget(0).layout().labelForField(self.language_combo).setText(self.tr("Choose Language:"))
        self.stack.widget(0).layout().labelForField(self.setting_scope_combo).setText(self.tr("Choose Setting:"))
        # self.stack.widget(0).layout().labelForField(self.segment_linedit.parent()).setText(self.tr("Segment:"))


    def on_call_update(self):
        # Call the update function from the main window
        config.main_window_q.put(("update call", ""))
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
