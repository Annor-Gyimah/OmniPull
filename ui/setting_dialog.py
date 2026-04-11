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
import subprocess

from modules import config, setting
from modules.utils import log, delete_file
from modules.settings_manager import SettingsManager

from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt, QTranslator, QCoreApplication

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QComboBox,
    QDialog, QFormLayout, QCheckBox, QTabWidget,
    QGridLayout, QFileDialog, QMessageBox
)





class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Settings"))
        self.setMinimumSize(640, 420)

        self.settings_manager = SettingsManager()

        self.translator = QTranslator()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

         # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton(self.tr("Cancel"))
        btn_cancel.setObjectName("DialogButton")
        btn_ok = QPushButton(self.tr("OK"))
        btn_ok.setObjectName("DialogButton")
        btn_ok.setDefault(True)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_cancel.setCursor(Qt.PointingHandCursor)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self.accept)

        # initializing tabs
        self.general_tab()
        self.appearance_tab()
        self.engine_config_tab()
        self.backend_paths_tab()
        self.update_tab()
        
        self.current_theme = config.current_theme
        self.load_values(config)

        self.app_check_update_btn.clicked.connect(self.on_call_update)
        self.ytdlp_check_update_btn.clicked.connect(self.on_call_ytdlp_update)

        # Load saved language
        self.current_language = config.lang
        
        self.apply_language(self.current_language)




    def general_tab(self):

        # General tab
        general_tab = QWidget()
        g_layout = QVBoxLayout(general_tab)
        g_layout.setContentsMargins(8, 8, 8, 8)
        g_layout.setSpacing(10)

        # === Top: language + settings profile ===
        top_form = QFormLayout()
        top_form.setSpacing(8)

        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "System default",
            "English",
            "French",
            "Spanish",
            "Hindi",
            "Korean",
            "Chinese",
            "Japanese"
        ])

        self.settings_profile_combo = QComboBox()
        self.settings_profile_combo.addItems([
            'Global',
            'Local'
        ])

        self.language_lbl = QLabel("Choose language:")
        top_form.addRow(self.language_lbl, self.language_combo)

        self.setting_profile_combo_lbl = QLabel("Choose settings:")
        top_form.addRow(self.setting_profile_combo_lbl, self.settings_profile_combo)

        g_layout.addLayout(top_form)

        # === Behavior checkboxes (2 rows, 3 per row) ===
        behavior_grid = QGridLayout()
        behavior_grid.setHorizontalSpacing(12)
        behavior_grid.setVerticalSpacing(4)

        self.monitor_clipboard_chk = QCheckBox(self.tr("Monitor clipboard"))
        self.show_thumbnail_chk = QCheckBox(self.tr("Show thumbnail"))
        self.auto_close_dl_window_chk = QCheckBox(self.tr("Auto close download window"))
        self.show_download_window_chk = QCheckBox(self.tr("Show download window"))
        self.show_all_logs_chk = QCheckBox(self.tr("Show all logs"))
        self.hide_app_chk = QCheckBox(self.tr("Hide app when minimized"))

        behavior_checks = [
            self.monitor_clipboard_chk,
            self.show_thumbnail_chk,
            self.auto_close_dl_window_chk,
            self.show_download_window_chk,
            self.show_all_logs_chk,
            self.hide_app_chk,
        ]

        for idx, chk in enumerate(behavior_checks):
            row = idx // 3   # 0, 1
            col = idx % 3    # 0, 1, 2
            behavior_grid.addWidget(chk, row, col)

        g_layout.addLayout(behavior_grid)

        # === Download engine + browser integration ===
        self.download_engine_combo = QComboBox()
        self.download_engine_combo.addItems(["yt-dlp", "curl", "aria2c"])

        engine_row = QHBoxLayout()
        engine_row.setSpacing(6)

        self.download_engine_label = QLabel(self.tr("Download engine:"))
        engine_row.addWidget(self.download_engine_label)
        engine_row.addWidget(self.download_engine_combo)

        engine_row.addSpacing(8)
        self.max_con_lbl = QLabel(self.tr("Max concurrent:"))
        self.max_concurrent_combo = QComboBox()
        self.max_concurrent_combo.addItems(["1", "2", "3", "4", "8", "16"])
        engine_row.addWidget(self.max_con_lbl)
        engine_row.addWidget(self.max_concurrent_combo)

        engine_row.addSpacing(8)
        self.browser_integration_chk = QCheckBox(self.tr("Browser integration"))
        engine_row.addWidget(self.browser_integration_chk)

        engine_row.addSpacing(8)
        self.on_startup_chk = QCheckBox(self.tr("On Startup"))
        engine_row.addWidget(self.on_startup_chk)

        engine_row.addStretch()

        g_layout.addLayout(engine_row)


        # === Proxy settings ===
        proxy_layout = QVBoxLayout()
        proxy_layout.setSpacing(4)

        # Row 1: use proxy + type + URL all on one row
        proxy_row1 = QHBoxLayout()
        proxy_row1.setSpacing(6)

        self.use_proxy_chk = QCheckBox(self.tr("Use proxy"))

        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["HTTP", "HTTPS", "SOCKS4", "SOCKS5"])
        self.proxy_type_combo.setMinimumWidth(80)
        self.proxy_type_combo.setEnabled(False)

        self.proxy_url_edit = QLineEdit()
        self.proxy_url_edit.setPlaceholderText(self.tr("Proxy URL (host:port or full URL)"))
        self.proxy_url_edit.setEnabled(False)
        

        proxy_row1.addWidget(self.use_proxy_chk)
        proxy_row1.addSpacing(6)
        proxy_row1.addWidget(self.proxy_type_combo)
        proxy_row1.addSpacing(6)
        proxy_row1.addWidget(self.proxy_url_edit)

        proxy_layout.addLayout(proxy_row1)

        # Row 2: username + password on another row
        proxy_row2 = QHBoxLayout()
        proxy_row2.setSpacing(6)

        self.proxy_user_lbl = QLabel(self.tr("User:"))
        self.proxy_username_edit = QLineEdit()
        self.proxy_username_edit.setPlaceholderText(self.tr("Username"))
        self.proxy_username_edit.setEnabled(False)

        self.proxy_pass_lbl = QLabel(self.tr("Pass:"))
        self.proxy_password_edit = QLineEdit()
        self.proxy_password_edit.setPlaceholderText(self.tr("Password"))
        self.proxy_password_edit.setEchoMode(QLineEdit.Password)
        self.proxy_password_edit.setEnabled(False)

        
        self.use_proxy_chk.toggled.connect(self.proxy_url_edit.setEnabled)
        self.use_proxy_chk.toggled.connect(self.proxy_type_combo.setEnabled)
        self.use_proxy_chk.toggled.connect(self.proxy_username_edit.setEnabled)
        self.use_proxy_chk.toggled.connect(self.proxy_password_edit.setEnabled)

        proxy_row2.addWidget(self.proxy_user_lbl)
        proxy_row2.addWidget(self.proxy_username_edit)
        proxy_row2.addSpacing(6)
        proxy_row2.addWidget(self.proxy_pass_lbl)
        proxy_row2.addWidget(self.proxy_password_edit)

        proxy_layout.addLayout(proxy_row2)

        g_layout.addLayout(proxy_layout)

        # === Retry failed scheduled downloads ===
        retry_layout = QVBoxLayout()
        retry_layout.setSpacing(4)

        # Row 1: checkbox alone
        retry_row1 = QHBoxLayout()
        self.retry_failed_scheduled_chk = QCheckBox(self.tr("Retry failed scheduled downloads"))
        retry_row1.addWidget(self.retry_failed_scheduled_chk)
        retry_row1.addStretch()

        # Row 2: max retries + interval in one row
        retry_row2 = QHBoxLayout()
        retry_row2.setSpacing(6)

        self.max_retries_lbl = QLabel(self.tr("Max retries:"))
        self.max_retries_combo = QComboBox()
        self.max_retries_combo.addItems(["1", "2", "3", "5", "10", "Unlimited"])
        self.max_retries_combo.setMinimumWidth(80)
        self.max_retries_combo.setEnabled(False)

        self.interval_lbl = QLabel(self.tr("Interval (minutes):"))
        self.retry_interval_combo = QComboBox()
        self.retry_interval_combo.addItems(["1", "5", "10", "15", "30", "60"])
        self.retry_interval_combo.setMinimumWidth(80)
        self.retry_interval_combo.setEnabled(False)

        self.retry_failed_scheduled_chk.toggled.connect(self.max_retries_combo.setEnabled)
        self.retry_failed_scheduled_chk.toggled.connect(self.retry_interval_combo.setEnabled)

        retry_row2.addWidget(self.max_retries_lbl)
        retry_row2.addWidget(self.max_retries_combo)
        retry_row2.addSpacing(8)
        retry_row2.addWidget(self.interval_lbl)
        retry_row2.addWidget(self.retry_interval_combo)
        retry_row2.addStretch()

        retry_layout.addLayout(retry_row1)
        retry_layout.addLayout(retry_row2)

        g_layout.addLayout(retry_layout)
        g_layout.addStretch()


        self.tabs.addTab(general_tab, self.tr("General"))


    def appearance_tab(self):

        # UI tab
        ui_tab = QWidget()
        ui_layout = QFormLayout(ui_tab)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])
        self.theme_lbl = QLabel(self.tr("Theme"))
        ui_layout.addRow(self.theme_lbl, self.theme_combo)

        # Color customizations
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor

        # self.bg_color_btn = QPushButton("Background Color")
        # self.bg_color_preview = QLabel()
        # self.bg_color_preview.setFixedSize(24, 16)
        # self.bg_color_preview.setStyleSheet(f"background:{getattr(__import__('modules').config, 'bg_color_dark', '#14161a')}; border:1px solid #222;")

        self.accent_color_btn = QPushButton("Accent Color")
        self.accent_color_preview = QLabel()
        self.accent_color_preview.setFixedSize(24, 16)
        self.accent_color_preview.setStyleSheet(f"background:{getattr(__import__('modules').config, 'accent_color', '#2b80ff')}; border:1px solid #222;")

        def pick_bg():
            c = QColorDialog.getColor()
            if c.isValid():
                hexc = c.name()
                self.bg_color_preview.setStyleSheet(f"background:{hexc}; border:1px solid #222;")
                self._chosen_bg = hexc

        def pick_accent():
            c = QColorDialog.getColor()
            if c.isValid():
                hexc = c.name()
                self.accent_color_preview.setStyleSheet(f"background:{hexc}; border:1px solid #222;")
                self._chosen_accent = hexc

        # self.bg_color_btn.clicked.connect(pick_bg)
        self.accent_color_btn.clicked.connect(pick_accent)

        # row_bg = QHBoxLayout()
        # row_bg.addWidget(self.bg_color_btn)
        # row_bg.addWidget(self.bg_color_preview)
        # ui_layout.addRow("Background:", row_bg)

        row_accent = QHBoxLayout()
        row_accent.addWidget(self.accent_color_btn)
        row_accent.addWidget(self.accent_color_preview)
        self.accent_lbl = QLabel(self.tr("Accent:"))
        ui_layout.addRow(self.accent_lbl, row_accent)

        self.tabs.addTab(ui_tab, self.tr("Appearance"))



    def engine_config_tab(self):

        # === Engine Config tab (parent) ===
        engine_tab = QWidget()
        engine_layout = QVBoxLayout(engine_tab)
        engine_layout.setContentsMargins(8, 8, 8, 8)
        engine_layout.setSpacing(8)

        self.engine_tabs = QTabWidget()
        engine_layout.addWidget(self.engine_tabs)

        # ----------------- cURL SUBTAB -----------------
        curl_tab = QWidget()
        curl_layout = QVBoxLayout(curl_tab)
        curl_layout.setContentsMargins(4, 4, 4, 4)
        curl_layout.setSpacing(8)

        # Row 1: speed limit checkbox + line edit (numeric)
        curl_row1 = QHBoxLayout()
        curl_row1.setSpacing(6)

        self.curl_speed_limit_chk = QCheckBox(self.tr("Speed limit:"))
        self.curl_speed_limit_edit = QLineEdit()
        self.curl_speed_limit_edit.setPlaceholderText(self.tr("KB/s or MB/s value (numeric)"))
        self.curl_speed_limit_edit.setValidator(QIntValidator(1, 10_000_000, self))
        self.curl_speed_limit_edit.setEnabled(False)  
        self.curl_speed_limit_chk.toggled.connect(self.curl_speed_limit_edit.setEnabled)

        curl_row1.addWidget(self.curl_speed_limit_chk)
        curl_row1.addWidget(self.curl_speed_limit_edit)

        curl_layout.addLayout(curl_row1)

        # Row 2–3: max concurrent downloads, max connections, segment size
        curl_form = QFormLayout()
        curl_form.setSpacing(6)


        self.curl_max_connections_combo = QComboBox()
        self.curl_max_connections_combo.addItems(["1", "2", "4", "8", "16", "32", "64", "128"])

        # Row: max concurrent + max connections on same row
        curl_row_limits = QHBoxLayout()
        curl_row_limits.setSpacing(6)
        
        curl_row_limits.addSpacing(8)
        self.curl_max_conn_lbl = QLabel(self.tr("Max connections:"))
        curl_row_limits.addWidget(self.curl_max_conn_lbl)
        curl_row_limits.addWidget(self.curl_max_connections_combo)
        curl_row_limits.addStretch()

        curl_form.addRow(curl_row_limits)

        # segment size: numeric line edit + unit combo
        segment_row = QHBoxLayout()
        self.curl_segment_size_edit = QLineEdit()
        self.curl_segment_size_edit.setPlaceholderText(self.tr("Segment Size"))
        self.curl_segment_size_edit.setValidator(QIntValidator(1, 10_000_000, self))

        self.curl_segment_unit_combo = QComboBox()
        self.curl_segment_unit_combo.addItems(["KB", "MB"])

        segment_row.addWidget(self.curl_segment_size_edit)
        segment_row.addWidget(self.curl_segment_unit_combo)
        self.segment_size_lbl = QLabel(self.tr("Segment size:"))
        curl_form.addRow(self.segment_size_lbl, segment_row)


        curl_layout.addLayout(curl_form)
        curl_layout.addStretch()

        self.engine_tabs.addTab(curl_tab, "cURL")

        # ----------------- YTDLP SUBTAB -----------------
        ytdlp_tab = QWidget()
        ytdlp_layout = QVBoxLayout(ytdlp_tab)
        ytdlp_layout.setContentsMargins(4, 4, 4, 4)
        ytdlp_layout.setSpacing(6)

        # Row 1
        ytdlp_row1 = QHBoxLayout()
        self.ytdlp_no_playlist_chk = QCheckBox(self.tr("No playlist"))
        self.ytdlp_ignore_errors_chk = QCheckBox(self.tr("Ignore errors"))
        self.ytdlp_list_formats_chk = QCheckBox(self.tr("List formats"))
        self.ytdlp_use_exe_chk = QCheckBox(self.tr("Use yt-dlp executable"))
        self.ytdlp_quiet_chk = QCheckBox(self.tr("Quiet"))

        ytdlp_row1.addWidget(self.ytdlp_no_playlist_chk)
        ytdlp_row1.addWidget(self.ytdlp_ignore_errors_chk)
        ytdlp_row1.addWidget(self.ytdlp_list_formats_chk)
        ytdlp_row1.addWidget(self.ytdlp_use_exe_chk)
        ytdlp_row1.addWidget(self.ytdlp_quiet_chk)
        ytdlp_row1.addStretch()

        # Row 2
        ytdlp_row2 = QHBoxLayout()
        
        self.ytdlp_write_metadata_chk = QCheckBox(self.tr("Write metadata"))
        self.ytdlp_write_info_json_chk = QCheckBox(self.tr("Write info JSON"))
        self.ytdlp_write_description_chk = QCheckBox(self.tr("Write description"))
        self.ytdlp_write_annotations_chk = QCheckBox(self.tr("Write annotations"))
        self.ytdlp_no_warnings_chk = QCheckBox(self.tr("No warnings"))
        
        ytdlp_row2.addWidget(self.ytdlp_write_metadata_chk)
        ytdlp_row2.addWidget(self.ytdlp_write_info_json_chk)
        ytdlp_row2.addWidget(self.ytdlp_write_description_chk)
        ytdlp_row2.addWidget(self.ytdlp_write_annotations_chk)
        ytdlp_row2.addWidget(self.ytdlp_no_warnings_chk)
        ytdlp_row2.addStretch()


        ytdlp_layout.addLayout(ytdlp_row1)
        ytdlp_layout.addLayout(ytdlp_row2)

        # Output template + format and concurrency/retries
        ytdlp_form = QFormLayout()
        ytdlp_form.setSpacing(6)

        self.ytdlp_output_template_edit = QLineEdit()
        self.ytdlp_output_template_edit.setPlaceholderText("Output template (e.g. %(title)s.%(ext)s)")

        self.ytdlp_format_combo = QComboBox()
        self.ytdlp_format_combo.addItems(["Auto", "mp4", "mp3", "webm", "avi", "mkv"])

        self.ytdlp_concurrent_fragments_combo = QComboBox()
        self.ytdlp_concurrent_fragments_combo.addItems(["1", "2", "3", "4", "5", "10"])

        self.ytdlp_retries_combo = QComboBox()
        self.ytdlp_retries_combo.addItems(["1", "2", "3", "5", "10", "Unlimited"])

        # Row 1: output template + format
        ytdlp_row_fmt = QHBoxLayout()
        ytdlp_row_fmt.setSpacing(6)
        self.ytdlp_lbl = QLabel(self.tr("Template:"))
        ytdlp_row_fmt.addWidget(self.ytdlp_lbl)
        ytdlp_row_fmt.addWidget(self.ytdlp_output_template_edit)
        ytdlp_row_fmt.addSpacing(6)
        self.format_lbl = QLabel(self.tr("Format:"))
        ytdlp_row_fmt.addWidget(self.format_lbl)
        ytdlp_row_fmt.addWidget(self.ytdlp_format_combo)

        # Row 2: concurrent fragments + retries
        ytdlp_row_conc = QHBoxLayout()
        ytdlp_row_conc.setSpacing(6)
        self.ytdlp_concurrent_fragments_lbl = QLabel(self.tr("Concurrent fragments:"))
        ytdlp_row_conc.addWidget(self.ytdlp_concurrent_fragments_lbl)
        ytdlp_row_conc.addWidget(self.ytdlp_concurrent_fragments_combo)
        ytdlp_row_conc.addSpacing(6)
        self.ytdlp_retries_lbl = QLabel(self.tr("Retries:"))
        ytdlp_row_conc.addWidget(self.ytdlp_retries_lbl)
        ytdlp_row_conc.addWidget(self.ytdlp_retries_combo)
        ytdlp_row_conc.addStretch()

        ytdlp_form.addRow(ytdlp_row_fmt)
        ytdlp_form.addRow(ytdlp_row_conc)


        ytdlp_layout.addLayout(ytdlp_form)
        ytdlp_layout.addStretch()

        self.engine_tabs.addTab(ytdlp_tab, "YTDLP")

        # ----------------- ARIA2C SUBTAB -----------------
        aria_tab = QWidget()
        aria_layout = QVBoxLayout(aria_tab)
        aria_layout.setContentsMargins(4, 4, 4, 4)
        aria_layout.setSpacing(8)

        
        aria_form = QFormLayout()
        aria_form.setSpacing(6)

        self.aria_max_conn_per_server_combo = QComboBox()
        self.aria_max_conn_per_server_combo.addItems([str(i) for i in range(1, 17)])

        # Enable DHT & follow torrent
        aria_row_flags = QHBoxLayout()
        self.aria_enable_dht_chk = QCheckBox(self.tr("Enable DHT"))
        self.aria_follow_torrent_chk = QCheckBox(self.tr("Follow torrent"))
        aria_row_flags.addWidget(self.aria_enable_dht_chk)
        aria_row_flags.addWidget(self.aria_follow_torrent_chk)
        aria_row_flags.addStretch()

        # Session save interval 1–10
        self.aria_session_save_interval_combo = QComboBox()
        self.aria_session_save_interval_combo.addItems([str(i) for i in range(1, 11)])

        # File allocation
        self.aria_file_allocation_combo = QComboBox()
        self.aria_file_allocation_combo.addItems(["none", "falloc", "prealloc", "trunc"])

        # Download split part as combo
        self.aria_split_combo = QComboBox()
        self.aria_split_combo.addItems(["1", "2", "4", "8", "16", "32", "64", "128"])

        # RPC port as combo – common valid ports for RPC use
        self.aria_rpc_port_combo = QComboBox()
        self.aria_rpc_port_combo.addItems(["6800", "6801", "6802", "8080", "8081", "9090", "443"])

        self.aria_max_conn_lbl = QLabel(self.tr("Max connection per server:"))
        aria_form.addRow(self.aria_max_conn_lbl, self.aria_max_conn_per_server_combo)
        aria_form.addRow("", aria_row_flags)

        # ONE ROW: session interval + file allocation + split part + RPC port
        aria_row_session_all = QHBoxLayout()
        aria_row_session_all.setSpacing(6)

        self.aria_session_save_interval_lbl = QLabel(self.tr("Session interval (s):"))
        aria_row_session_all.addWidget(self.aria_session_save_interval_lbl)
        aria_row_session_all.addWidget(self.aria_session_save_interval_combo)
        aria_row_session_all.addSpacing(6)

        self.aria_file_allocation_lbl = QLabel(self.tr("File allocation:"))
        aria_row_session_all.addWidget(self.aria_file_allocation_lbl)
        aria_row_session_all.addWidget(self.aria_file_allocation_combo)
        aria_row_session_all.addSpacing(6)

        self.aria_split_part_lbl = QLabel(self.tr("Split part:"))
        aria_row_session_all.addWidget(self.aria_split_part_lbl)
        aria_row_session_all.addWidget(self.aria_split_combo)
        aria_row_session_all.addSpacing(6)

        self.aria_rpc_port_lbl = QLabel(self.tr("RPC port:"))
        aria_row_session_all.addWidget(self.aria_split_part_lbl)
        aria_row_session_all.addWidget(self.aria_rpc_port_combo)
        aria_row_session_all.addStretch()

        aria_form.addRow(aria_row_session_all)



        aria_layout.addLayout(aria_form)
        aria_layout.addStretch()

        self.engine_tabs.addTab(aria_tab, "ARIA2C")

        self.tabs.addTab(engine_tab, self.tr("Engine config"))

    
    def backend_paths_tab(self):

        # === Backend paths tab ===
        backend_tab = QWidget()
        backend_layout = QFormLayout(backend_tab)
        backend_layout.setSpacing(8)

        

        # helper — small local function
        def _browse_and_set(line_edit, title, file_filter):
            filename, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
            if filename:
                line_edit.setText(filename)
            # if cancelled -> do nothing (preserve previous text / placeholder)

        # yt-dlp
        self.ytdlp_path_edit = QLineEdit()
        # set placeholder to bundled path if it exists
        bundled_ytdlp = os.path.join(config.sett_folder, "yt-dlp.exe")
        if os.path.exists(bundled_ytdlp):
            self.ytdlp_path_edit.setPlaceholderText(self.tr("Leave blank to use bundled: ") + bundled_ytdlp)
        else:
            self.ytdlp_path_edit.setPlaceholderText(self.tr("Leave blank to use bundled"))

        self.ytdlp_path_browse_btn = QPushButton("Browse")
        self.ytdlp_path_browse_btn.clicked.connect(lambda: _browse_and_set(self.ytdlp_path_edit,
            self.tr("Select ytdlp.exe"),
            self.tr("Executable Files (*.exe)"))
        )
        row_ytdlp = QHBoxLayout()
        row_ytdlp.addWidget(self.ytdlp_path_edit)
        row_ytdlp.addWidget(self.ytdlp_path_browse_btn)
        self.ytdlp_exe_label = QLabel(self.tr("yt-dlp executable:"))
        backend_layout.addRow(self.ytdlp_exe_label, row_ytdlp)

        # deno
        self.deno_path_edit = QLineEdit()
        bundled_deno = os.path.join(config.sett_folder, "deno.exe")
        if os.path.exists(bundled_deno):
            self.deno_path_edit.setPlaceholderText(self.tr("Leave blank to use bundled: ") + bundled_deno)
        else:
            self.deno_path_edit.setPlaceholderText(self.tr("Leave blank to use bundled"))
        self.deno_path_browse_btn = QPushButton(self.tr("Browse"))
        self.deno_path_browse_btn.clicked.connect(lambda: _browse_and_set(self.deno_path_edit,
            self.tr("Select deno.exe"),
            self.tr("Executable Files (*.exe)"))
        )
        row_deno = QHBoxLayout()
        row_deno.addWidget(self.deno_path_edit)
        row_deno.addWidget(self.deno_path_browse_btn)
        self.deno_exe_label = QLabel(self.tr("deno executable:"))
        backend_layout.addRow(self.deno_exe_label, row_deno)

        # ffmpeg
        self.ffmpeg_path_edit = QLineEdit()
        bundled_ffmpeg = os.path.join(config.sett_folder, "ffmpeg.exe")
        if os.path.exists(bundled_ffmpeg):
            self.ffmpeg_path_edit.setPlaceholderText(self.tr("Leave blank to use bundled: ") + bundled_ffmpeg)
        else:
            self.ffmpeg_path_edit.setPlaceholderText(self.tr("Leave blank to use bundled"))
        self.ffmpeg_path_browse_btn = QPushButton(self.tr("Browse"))
        self.ffmpeg_path_browse_btn.clicked.connect(lambda: _browse_and_set(self.ffmpeg_path_edit,
                                                                        self.tr("Select ffmpeg.exe"),
                                                                        self.tr("Executable Files (*.exe)")))
        row_ffmpeg = QHBoxLayout()
        row_ffmpeg.addWidget(self.ffmpeg_path_edit)
        row_ffmpeg.addWidget(self.ffmpeg_path_browse_btn)
        self.ffmpeg_exe_label = QLabel(self.tr("ffmpeg executable:"))
        backend_layout.addRow(self.ffmpeg_exe_label, row_ffmpeg)
        

        # cookies file (same pattern, but allow text cleared — optional)
        self.cookies_path_edit = QLineEdit()
        self.cookies_path_edit.setPlaceholderText(self.tr("Optional cookies.txt (leave blank)"))
        self.cookies_path_browse_btn = QPushButton(self.tr("Browse"))
        self.cookies_path_browse_btn.clicked.connect(lambda: _browse_and_set(self.cookies_path_edit,
                                                                            self.tr("Select cookies.txt"),
                                                                            self.tr("Text Files (*.txt)")))
        row_cookies = QHBoxLayout()
        row_cookies.addWidget(self.cookies_path_edit)
        row_cookies.addWidget(self.cookies_path_browse_btn)
        backend_layout.addRow("Cookies file:", row_cookies)

        self.tabs.addTab(backend_tab, self.tr("Backend paths"))

    def get_ytdlp_version(self, force_refresh=False):
        """Returns the yt-dlp version, using a cache to avoid slow subprocess calls."""
        
        # 1. Check if we already have a cached version and aren't forcing a refresh
        if not force_refresh and getattr(config, "cached_ytdlp_version", None):
            return config.cached_ytdlp_version

        # 2. If no cache, perform the slow check
        yt_dlp_path = getattr(config, "yt_dlp_exe", "") or config.yt_dlp_actual_path
        
        if yt_dlp_path and os.path.isfile(yt_dlp_path):
            try:
                kwargs = dict(capture_output=True, text=True, timeout=5)
                if sys.platform.startswith("win"):
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                
                proc = subprocess.run([yt_dlp_path, "--version"], **kwargs)
                version = proc.stdout.strip().splitlines()[0] if proc.stdout else ""
                
                # 3. Save to cache for next time
                config.cached_ytdlp_version = version
                return version
            except Exception:
                return self.tr("Unknown")
        
        return self.tr("Not set")

    def update_tab(self):
        # === Updates tab ===
        updates_tab = QWidget()
        updates_layout = QVBoxLayout(updates_tab)
        updates_layout.setContentsMargins(8, 8, 8, 8)
        updates_layout.setSpacing(10)

        # Row 1: check for updates every (days)
        row_interval = QHBoxLayout()
        self.label_interval = QLabel(self.tr("Check for updates every (days):"))
        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItems(["1", "3", "5", "7"])
        self.update_interval_combo.setMinimumWidth(80)

        row_interval.addWidget(self.label_interval)
        row_interval.addWidget(self.update_interval_combo)
        row_interval.addStretch()

        updates_layout.addLayout(row_interval)

        # Row 2: App version + check button
        row_app = QHBoxLayout()
        self.app_version_label = QLabel(self.tr("App version: %1").replace("%1", config.APP_VERSION))
        self.app_check_update_btn = QPushButton(self.tr("Check for app update"))

        row_app.addWidget(self.app_version_label)
        row_app.addStretch()
        row_app.addWidget(self.app_check_update_btn)

        updates_layout.addLayout(row_app)

        # Row 3: yt-dlp version + check button
        row_ytdlp_upd = QHBoxLayout()

        current_ver = self.get_ytdlp_version()
        self.ytdlp_version_label = QLabel(self.tr("yt-dlp version: %1").replace("%1", current_ver))
        self.ytdlp_check_update_btn = QPushButton(self.tr("Check for yt-dlp update"))

        row_ytdlp_upd.addWidget(self.ytdlp_version_label)
        row_ytdlp_upd.addStretch()
        row_ytdlp_upd.addWidget(self.ytdlp_check_update_btn)

        updates_layout.addLayout(row_ytdlp_upd)
        updates_layout.addStretch()

        self.tabs.addTab(updates_tab, self.tr("Updates"))


    def load_values(self, config):
        self.language_combo.setCurrentText(str(config.lang))
        self.settings_profile_combo.setCurrentText('Global' if config.sett_folder == config.global_sett_folder else 'Local')
        self.monitor_clipboard_chk.setChecked(config.monitor_clipboard)
        self.show_thumbnail_chk.setChecked(config.show_thumbnail)
        self.auto_close_dl_window_chk.setChecked(config.auto_close_download_window)
        self.show_download_window_chk.setChecked(config.show_download_window)
        self.show_all_logs_chk.setChecked(config.show_all_logs)
        self.hide_app_chk.setChecked(config.hide_app)
        self.download_engine_combo.setCurrentText(config.download_engine)
        self.browser_integration_chk.setChecked(config.browser_integration_enabled)
        self.on_startup_chk.setChecked(config.on_startup)

        self.use_proxy_chk.setChecked(config.enable_proxy)
        self.proxy_url_edit.setText(config.proxy or '')
        self.proxy_type_combo.setCurrentText(config.proxy_type or 'http')
        self.proxy_username_edit.setText(config.proxy_user or '')
        self.proxy_password_edit.setText(config.proxy_pass or '')

        if config.proxy != "":
            proxy_url = config.proxy
            if config.proxy_user and config.proxy_pass:
                # Inject basic auth into the proxy URL
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(proxy_url)
                proxy_url = urlunparse(parsed._replace(netloc=f"{config.proxy_user}:{config.proxy_pass}@{parsed.hostname}:{parsed.port}"))

                self.proxy_url_edit.setText(proxy_url if proxy_url else '')
        else:
            self.proxy_url_edit.setText('')

        self.retry_failed_scheduled_chk.setChecked(config.retry_scheduled_enabled)
        self.max_retries_combo.setCurrentText(str(config.retry_scheduled_max_tries))
        self.retry_interval_combo.setCurrentText(str(config.retry_scheduled_interval_mins))

        # Appearance - Load theme with proper capitalization
        current_theme = config.current_theme.lower()
        if current_theme == "dark":
            self.theme_combo.setCurrentText("Dark")
        elif current_theme == "light":
            self.theme_combo.setCurrentText("Light")
        else:
            self.theme_combo.setCurrentText("System")


        # Engine Settings

        # cURL Settings
        seg_size = config.segment_size // 1024
        if seg_size >= 1024:
            seg_size = seg_size // 1024
            seg_unit = 'MB'
        else:
            seg_unit = 'KB'
        
        self.curl_speed_limit_chk.setChecked(config.enable_speed_limit)
        self.curl_speed_limit_edit.setText(str(config.speed_limit))
        self.max_concurrent_combo.setCurrentText(str(config.max_concurrent_downloads))
        self.curl_max_connections_combo.setCurrentText(str(config.max_connections))
        self.curl_segment_size_edit.setText(str(seg_size))
        self.curl_segment_unit_combo.setCurrentText(seg_unit)

        # YT-DLP Settings
        self.ytdlp_no_playlist_chk.setChecked(config.ytdlp_config['no_playlist'])
        self.ytdlp_ignore_errors_chk.setChecked(config.ytdlp_config['ignore_errors'])
        self.ytdlp_list_formats_chk.setChecked(config.ytdlp_config['list_formats'])
        self.ytdlp_use_exe_chk.setChecked(config.use_ytdlp_exe)
        self.ytdlp_output_template_edit.setText(config.ytdlp_config['outtmpl'])
        self.ytdlp_format_combo.setCurrentText(config.ytdlp_config['merge_output_format'])
        self.ytdlp_concurrent_fragments_combo.setCurrentText(str(config.ytdlp_config['concurrent_fragment_downloads']))
        self.ytdlp_retries_combo.setCurrentText(str(config.ytdlp_config['retries']))
        self.ytdlp_quiet_chk.setChecked(config.ytdlp_config['quiet'])
        self.ytdlp_write_metadata_chk.setChecked(config.ytdlp_config['writemetadata'])
        self.ytdlp_write_info_json_chk.setChecked(config.ytdlp_config['writeinfojson'])
        self.ytdlp_write_description_chk.setChecked(config.ytdlp_config['writedescription'])
        #self.ytdlp_write_annotations_chk.setChecked(config.ytdlp_config['writeannotations'])
        self.ytdlp_no_warnings_chk.setChecked(config.ytdlp_config['no_warnings'])

        # Aria2c Settings
        self.aria_max_conn_per_server_combo.setCurrentText(str(config.aria2c_config['max_connections']))
        self.aria_enable_dht_chk.setChecked(config.aria2c_config['enable_dht'])
        self.aria_follow_torrent_chk.setChecked(config.aria2c_config['follow_torrent'])
        self.aria_session_save_interval_combo.setCurrentText(str(config.aria2c_config['save_interval']))
        self.aria_rpc_port_combo.setCurrentText(str(config.aria2c_config['rpc_port']))
        self.aria_split_combo.setCurrentText(str(config.aria2c_config['split']))
        self.aria_file_allocation_combo.setCurrentText(config.aria2c_config['file_allocation'])


        # Backend Paths
        # Backend Paths: show user overrides (empty means use bundled)
        self.ytdlp_path_edit.setText(config.user_selected_ytdlp if getattr(config, 'user_selected_ytdlp', None) else '')
        self.deno_path_edit.setText(config.user_selected_deno if getattr(config, 'user_selected_deno', None) else '')
        self.ffmpeg_path_edit.setText(config.user_selected_ffmpeg if getattr(config, 'user_selected_ffmpeg', None) else '')
        self.cookies_path_edit.setText(config.ytdlp_config.get('cookiesfile') if config.ytdlp_config.get('cookiesfile') else '')



        # Check for updates settings
        self.update_interval_combo.setCurrentText(str(config.update_frequency))

    

    def accept(self):
        """Override the accept method to apply and save settings when OK is clicked."""

        self.settings_folder()  
        config.lang = self.language_combo.currentText()
        config.monitor_clipboard = self.monitor_clipboard_chk.isChecked()
        config.show_download_window = self.show_download_window_chk.isChecked()
        config.auto_close_download_window = self.auto_close_dl_window_chk.isChecked()
        config.show_thumbnail = self.show_thumbnail_chk.isChecked()
        config.on_startup = self.on_startup_chk.isChecked()
        config.show_all_logs = self.show_all_logs_chk.isChecked()
        config.hide_app = self.hide_app_chk.isChecked()
        config.download_engine = self.download_engine_combo.currentText()
        config.browser_integration_enabled = self.browser_integration_chk.isChecked()
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
        
        
        config.enable_proxy = self.use_proxy_chk.isChecked()
        config.proxy = self.proxy_url_edit.text() if self.use_proxy_chk.isChecked() else ""
        config.proxy_type = self.proxy_type_combo.currentText()
        config.proxy_user = self.proxy_username_edit.text() if self.use_proxy_chk.isChecked() else ""
        config.proxy_pass = self.proxy_password_edit.text() if self.use_proxy_chk.isChecked() else ""
        config.retry_scheduled_enabled = self.retry_failed_scheduled_chk.isChecked()
        config.retry_scheduled_max_tries = int(self.max_retries_combo.currentText())
        config.retry_scheduled_interval_mins = int(self.retry_interval_combo.currentText()) 

       

        # Segment
        try:
            seg_size = int(self.curl_segment_size_edit.text())
            seg_multiplier = 1024 if self.curl_segment_unit_combo.currentText() == "KB" else 1024 * 1024
            config.segment_size = seg_size * seg_multiplier
        except ValueError:
            config.segment_size = 512 * 1024  # fallback default


        # Appearance - Save theme in lowercase
        theme_text = self.theme_combo.currentText()
        config.current_theme = theme_text.lower()  # Store as lowercase
            

        # Engine Config settings

        # PyCurl settings
        
        config.enable_speed_limit = self.curl_speed_limit_chk.isChecked()
        if config.enable_speed_limit:
            config.speed_limit = self.curl_speed_limit_edit.text()
        else:
            config.speed_limit = ""
        
        config.max_concurrent_downloads = str(self.max_concurrent_combo.currentText())
        config.max_connections = str(self.curl_max_connections_combo.currentText())
        

        # YT-DLP settings
        config.ytdlp_config['no_playlist'] = self.ytdlp_no_playlist_chk.isChecked()
        config.ytdlp_config['ignore_errors'] = self.ytdlp_ignore_errors_chk.isChecked()
        config.ytdlp_config['list_formats'] = self.ytdlp_list_formats_chk.isChecked()
        config.use_ytdlp_exe = self.ytdlp_use_exe_chk.isChecked()
        config.ytdlp_config['outtmpl'] = self.ytdlp_output_template_edit.text()
        config.ytdlp_config['merge_output_format'] = self.ytdlp_format_combo.currentText()
        config.ytdlp_config['concurrent_fragment_downloads'] = self.ytdlp_concurrent_fragments_combo.currentText()
        config.ytdlp_config['retries'] = self.ytdlp_retries_combo.currentText()
        config.ytdlp_config['quiet'] = self.ytdlp_quiet_chk.isChecked()
        config.ytdlp_config['writemetadata'] = self.ytdlp_write_metadata_chk.isChecked()
        config.ytdlp_config['writeinfojson'] = self.ytdlp_write_info_json_chk.isChecked()
        config.ytdlp_config['writedescription'] = self.ytdlp_write_description_chk.isChecked()
        config.ytdlp_config['writeannotations'] = self.ytdlp_write_annotations_chk.isChecked()
        config.ytdlp_config['no_warnings'] = self.ytdlp_no_warnings_chk.isChecked()
        
        

        # Aria2c settings
        config.aria2c_config['max_connections'] = self.aria_max_conn_per_server_combo.currentText()
        config.aria2c_config['enable_dht'] = self.aria_enable_dht_chk.isChecked()
        config.aria2c_config['follow_torrent'] = self.aria_follow_torrent_chk.isChecked()
        config.aria2c_config['save_interval'] = self.aria_session_save_interval_combo.currentText()
        config.aria2c_config['rpc_port'] = self.aria_rpc_port_combo.currentText()
        config.aria2c_config['split'] = self.aria_split_combo.currentText()
        config.aria2c_config['file_allocation'] = self.aria_file_allocation_combo.currentText()
        
      
        # Backend Paths
        config.yt_dlp_exe = self.ytdlp_path_edit.text().strip()
        config.deno_exe = self.deno_path_edit.text().strip()
        config.ytdlp_config['cookiesfile'] = self.cookies_path_edit.text() if self.cookies_path_edit.text() else None

        # in accept()
        # Backend Paths — save user overrides (empty => fall back to bundled/system)
        chosen = self.ytdlp_path_edit.text().strip()
        if chosen:
            if hasattr(config, 'set_user_ytdlp'):
                config.set_user_ytdlp(chosen)
            else:
                config.yt_dlp_exe = chosen
        else:
            if hasattr(config, 'set_user_ytdlp'):
                config.set_user_ytdlp(None)
            else:
                config.yt_dlp_exe = ''

        chosen = self.deno_path_edit.text().strip()
        if chosen:
            if hasattr(config, 'set_user_deno'):
                config.set_user_deno(chosen)
            else:
                config.deno_exe = chosen
        else:
            if hasattr(config, 'set_user_deno'):
                config.set_user_deno(None)
            else:
                config.deno_exe = ''

        chosen = self.ffmpeg_path_edit.text().strip()
        if chosen:
            if hasattr(config, 'set_user_ffmpeg'):
                config.set_user_ffmpeg(chosen)
            else:
                config.ffmpeg_actual_path = chosen
        else:
            if hasattr(config, 'set_user_ffmpeg'):
                config.set_user_ffmpeg(None)
            else:
                config.ffmpeg_actual_path = ''
        
        # Update ffmpeg_selected_path and ffmpeg_location in ytdlp_config with resolved path
        config.ffmpeg_selected_path = config.ffmpeg_actual_path
        config.ytdlp_config['ffmpeg_location'] = config.ffmpeg_actual_path


        # Check for updates settings
        config.update_frequency = int(self.update_interval_combo.currentText())
        



        # Save settings to disk
        # setting.save_setting()
        self.settings_manager.save_settings()

        # Persist chosen colors if the user picked any
        try:
            if hasattr(self, '_chosen_bg'):
                config.bg_color_dark = self._chosen_bg
            if hasattr(self, '_chosen_accent'):
                config.accent_color = self._chosen_accent
        except Exception:
            pass
        

        main_window = self.parent()  # get reference to the main window
        if main_window:
            # Apply the theme that was just saved
            main_window.set_theme(config.current_theme)
            # Save the setting after applying theme
            main_window.apply_language_to_all_windows(config.lang)
            self.retrans()
            setting.save_setting()
        
        if hasattr(main_window, 'on_startup'):
            main_window.on_startup()

        super().accept()


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



    def resource_path(self, relative_path):
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
            qm_path = self.resource_path(f"../modules/translations/{file_map[language]}")
            if self.translator.load(qm_path):
                QCoreApplication.instance().installTranslator(self.translator)
                

       

        self.retrans()
    

    def retrans(self):
        self.setWindowTitle(self.tr("Settings"))
        # ---- Tab title ----
        self.tabs.setTabText(0, self.tr("General"))

        # ---- Top form ----
        self.language_lbl.setText(self.tr("Choose language:"))
        self.setting_profile_combo_lbl.setText(self.tr("Choose Setting:"))

        # ---- Behavior checkboxes ----
        self.monitor_clipboard_chk.setText(self.tr("Monitor clipboard"))
        self.show_thumbnail_chk.setText(self.tr("Show thumbnail"))
        self.auto_close_dl_window_chk.setText(self.tr("Auto close download window"))
        self.show_download_window_chk.setText(self.tr("Show download window"))
        self.show_all_logs_chk.setText(self.tr("Show all logs"))
        self.hide_app_chk.setText(self.tr("Hide app when minimized"))

        # ---- Download engine row ----
        # QLabel("Download engine:") was not stored → cannot update
        self.download_engine_label.setText(self.tr("Download Engine:"))
        self.browser_integration_chk.setText(self.tr("Browser integration"))
        self.on_startup_chk.setText(self.tr("On Startup"))

        # ---- Proxy ----
        self.use_proxy_chk.setText(self.tr("Use proxy"))
        self.proxy_url_edit.setPlaceholderText(self.tr("Proxy URL (host:port or full URL)"))

        self.proxy_user_lbl.setText(self.tr("User:"))
        self.proxy_username_edit.setPlaceholderText(self.tr("Username"))

        self.proxy_pass_lbl.setText(self.tr("Pass:"))
        self.proxy_password_edit.setPlaceholderText(self.tr("Password"))

        # ---- Retry scheduled downloads ----
        self.retry_failed_scheduled_chk.setText(self.tr("Retry failed scheduled downloads"))

        self.max_retries_lbl.setText(self.tr("Max retries:"))
        self.interval_lbl.setText(self.tr("Interval (minutes):"))


        self.tabs.setTabText(1, self.tr("Appearance"))

        self.theme_lbl.setText(self.tr("Theme:"))
        self.accent_lbl.setText(self.tr("Accent:"))

        self.accent_color_btn.setText(self.tr("Accent Color"))



        # ===== Parent tab =====
        self.tabs.setTabText(2, self.tr("Engine config"))

        # ===== Sub-tabs =====
        self.engine_tabs.setTabText(0, self.tr("cURL"))
        self.engine_tabs.setTabText(1, self.tr("YTDLP"))
        self.engine_tabs.setTabText(2, self.tr("ARIA2C"))

        # ===== cURL =====
        self.curl_speed_limit_chk.setText(self.tr("Speed limit:"))
        self.curl_speed_limit_edit.setPlaceholderText(self.tr("KB/s or MB/s value (numeric)"))
        self.curl_max_conn_lbl.setText(self.tr("Max connections:"))
        self.curl_segment_size_edit.setPlaceholderText(self.tr("Segment Size"))
        self.segment_size_lbl.setText(self.tr("Segment size:"))

        # ===== YTDLP checkboxes =====
        self.ytdlp_no_playlist_chk.setText(self.tr("No playlist"))
        self.ytdlp_ignore_errors_chk.setText(self.tr("Ignore errors"))
        self.ytdlp_list_formats_chk.setText(self.tr("List formats"))
        self.ytdlp_use_exe_chk.setText(self.tr("Use yt-dlp executable"))
        self.ytdlp_quiet_chk.setText(self.tr("Quiet"))

        self.ytdlp_lbl.setText(self.tr("Template:"))
        self.format_lbl.setText(self.tr("Format:"))
        self.ytdlp_concurrent_fragments_lbl.setText(self.tr("Concurrent fragments:"))
        self.ytdlp_retries_lbl.setText(self.tr("Retries:"))

        self.ytdlp_write_metadata_chk.setText(self.tr("Write metadata"))
        self.ytdlp_write_info_json_chk.setText(self.tr("Write info JSON"))
        self.ytdlp_write_description_chk.setText(self.tr("Write description"))
        self.ytdlp_write_annotations_chk.setText(self.tr("Write annotations"))
        self.ytdlp_no_warnings_chk.setText(self.tr("No warnings"))

        self.ytdlp_output_template_edit.setPlaceholderText(self.tr("Output template (e.g. %(title)s.%(ext)s)"))

        # ===== ARIA2 =====
        self.aria_enable_dht_chk.setText(self.tr("Enable DHT"))
        self.aria_follow_torrent_chk.setText(self.tr("Follow torrent"))
        self.aria_max_conn_lbl.setText(self.tr("Max connection per server:"))
        self.aria_session_save_interval_lbl.setText(self.tr("Session interval (s):"))
        self.aria_file_allocation_lbl.setText(self.tr("File allocation:"))
        self.aria_split_part_lbl.setText(self.tr("Split part:"))
        self.aria_rpc_port_lbl.setText(self.tr("RPC port:"))


        # ---- Tab title ----
        self.tabs.setTabText(3, self.tr("Backend paths"))

        # ---- Browse buttons ----
        self.ytdlp_path_browse_btn.setText(self.tr("Browse"))
        self.deno_path_browse_btn.setText(self.tr("Browse"))
        self.ffmpeg_path_browse_btn.setText(self.tr("Browse"))
        self.cookies_path_browse_btn.setText(self.tr("Browse"))

        # ---- Placeholders ----
        bundled_ytdlp = os.path.join(config.sett_folder, "yt-dlp.exe")
        self.ytdlp_path_edit.setPlaceholderText(
            self.tr("Leave blank to use bundled: ") + bundled_ytdlp
            if os.path.exists(bundled_ytdlp)
            else self.tr("Leave blank to use bundled")
        )

        bundled_deno = os.path.join(config.sett_folder, "deno.exe")
        self.deno_path_edit.setPlaceholderText(
            self.tr("Leave blank to use bundled: ") + bundled_deno
            if os.path.exists(bundled_deno)
            else self.tr("Leave blank to use bundled")
        )

        bundled_ffmpeg = os.path.join(config.sett_folder, "ffmpeg.exe")
        self.ffmpeg_path_edit.setPlaceholderText(
            self.tr("Leave blank to use bundled: ") + bundled_ffmpeg
            if os.path.exists(bundled_ffmpeg)
            else self.tr("Leave blank to use bundled")
        )

        self.cookies_path_edit.setPlaceholderText(self.tr("Optional cookies.txt (leave blank)"))
        self.ytdlp_exe_label.setText(self.tr("yt-dlp executable:"))
        self.deno_exe_label.setText(self.tr("deno executable:"))
        self.ffmpeg_exe_label.setText(self.tr('ffmpeg executable:'))

        # ---- Tab title ----
        self.tabs.setTabText(4, self.tr("Updates"))

        # ---- Interval ----
        self.label_interval.setText(self.tr("Check for updates every (days):"))

        # ---- App update ----
        self.app_version_label.setText(self.tr("App version: %s") % config.APP_VERSION)
        self.app_check_update_btn.setText(self.tr("Check for app update"))

        # ---- yt-dlp update ----
        self.ytdlp_version_label.setText(self.tr("yt-dlp version: %1").replace("%1", str(config.cached_ytdlp_version)))
        self.ytdlp_check_update_btn.setText(self.tr("Check for yt-dlp update"))



    def show_settings_dialog(self):
        dlg = SettingsDialog(self)
        # sync current theme to dialog combo
        if self.current_theme == "dark":
            dlg.theme_combo.setCurrentText("Dark")
        else:
            dlg.theme_combo.setCurrentText("Light")

        if dlg.exec() == QDialog.Accepted:
            chosen = dlg.theme_combo.currentText()
            self.set_theme(chosen)


    def settings_folder(self):
        selected = self.settings_profile_combo.currentText()

        if selected == "Local":
            config.sett_folder = config.current_directory
            delete_file(os.path.join(config.global_sett_folder, 'setting_2.cfg'))
        else:
            config.sett_folder = config.global_sett_folder
            delete_file(os.path.join(config.current_directory, 'setting_2.cfg'))

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
                    self.settings_profile_combo.setCurrentText('Local')

        try:
            self.settings_profile_combo.setCurrentText('Global' if config.sett_folder == config.global_sett_folder else 'Local')
        except:
            pass



        

       