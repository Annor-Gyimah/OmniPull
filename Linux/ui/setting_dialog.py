from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QCheckBox,
    QSpinBox, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QStackedWidget, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QCoreApplication, QTranslator
import os, sys

from modules import config, setting

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(720, 500)
        self.setStyleSheet(self.dark_stylesheet())


        setting.load_setting()

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
            "General": ":/icons/general.svg",
            "Connection": ":/icons/cil-link.png",
            "Browser": ":/icons/extension.png",
            "Updates": ":/icons/updates.svg"
        }

        for key, icon in icon_map.items():
            translated_text = self.tr(key)
            item = QListWidgetItem(QIcon(icon), translated_text)
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

        self.ok_button = QPushButton("OK")
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

        self.cancel_button = QPushButton("Cancel")
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
        self.setup_connection_tab()
        self.setup_browser_tab()
        self.setup_updates_tab()

        
        
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

        self.language_combo = QComboBox()
        self.language_combo.addItems(["English","Chinese", "Spanish", "Korean", "French", "Japanese"])

        self.setting_scope_combo = QComboBox()
        self.setting_scope_combo.addItems(["Global", "Local"])

        self.monitor_clipboard_cb = QCheckBox("Monitor Copied URLs")
        self.show_download_window_cb = QCheckBox("Show Download Window")
        self.auto_close_cb = QCheckBox("Auto Close DL Window")
        self.show_thumbnail_cb = QCheckBox("Show Thumbnail")
        self.on_startup_cb = QCheckBox("On Startup")

        self.segment_linedit = QLineEdit()
        self.segment_linedit.setPlaceholderText("")
        self.segment_unit_combo = QComboBox()
        self.segment_unit_combo.addItems(["KB", "MB"])

        segment_row = QHBoxLayout()
        segment_row.addWidget(self.segment_linedit)
        segment_row.addWidget(self.segment_unit_combo)
        
        general_layout.addRow(QLabel("Choose Language:"), self.language_combo)
        general_layout.addRow(QLabel("Choose Setting:"), self.setting_scope_combo)
        general_layout.addRow(self.monitor_clipboard_cb)
        general_layout.addRow(self.show_download_window_cb)
        general_layout.addRow(self.auto_close_cb)
        general_layout.addRow(self.show_thumbnail_cb)
        general_layout.addRow(self.on_startup_cb)
        general_layout.addRow(QLabel("Segment:"), segment_row)
        self.stack.addWidget(general_widget)

    def setup_connection_tab(self):
        conn_widget = QWidget()
        conn_layout = QFormLayout(conn_widget)
        conn_layout.setSpacing(16)

        # Speed Limit checkbox + input
        self.speed_checkBox = QCheckBox("Speed Limit")
        self.speed_limit_input = QLineEdit()
        self.speed_limit_input.setPlaceholderText("e.g., 50k, 10k...")
        self.speed_limit_input.setEnabled(False)  # initially disabled
        self.speed_checkBox.toggled.connect(self.speed_limit_input.setEnabled)

        # Max Concurrent Downloads
        self.max_concurrent_combo = QComboBox()
        self.max_concurrent_combo.addItems(["1", "2", "3", "4", "5"])

        # Max Connection Settings
        self.max_conn_settings_combo = QComboBox()
        self.max_conn_settings_combo.addItems(["8", "16", "32", "64"])

        # Proxy checkbox + input + type combo
        self.checkBox_proxy = QCheckBox("Proxy")
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("Enter proxy...")
        self.proxy_input.setEnabled(False)

        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["http", "https", "socks5"])
        self.proxy_type_combo.setEnabled(False)

        self.checkBox_proxy.toggled.connect(self.proxy_input.setEnabled)
        self.checkBox_proxy.toggled.connect(self.proxy_type_combo.setEnabled)

        # Row layout for proxy
        proxy_row = QHBoxLayout()
        proxy_row.addWidget(self.proxy_input)
        proxy_row.addWidget(self.proxy_type_combo)

        # Add to form layout
        conn_layout.addRow(self.speed_checkBox, self.speed_limit_input)
        conn_layout.addRow(QLabel("Max Concurrent Downloads:"), self.max_concurrent_combo)
        conn_layout.addRow(QLabel("Max Connection Settings:"), self.max_conn_settings_combo)
        conn_layout.addRow(self.checkBox_proxy, proxy_row)

        # Info label under proxy
        self.label_proxy_info = QLabel("Enter a proxy address and select its type. \n Example: 127.0.0.1:8080")
        self.label_proxy_info.setStyleSheet("color: #aaa; font-size: 11px; margin-left: 4px;")
        conn_layout.addRow("", self.label_proxy_info)

        # --- Scheduled Download Retry Section ---
        self.retry_schedule_cb = QCheckBox("Retry failed scheduled downloads")
        #self.retry_schedule_cb.setChecked(True)
        

        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(1, 10)
        self.retry_count_spin.setValue(3)
        self.retry_count_spin.setEnabled(False)

        self.retry_interval_spin = QSpinBox()
        self.retry_interval_spin.setRange(1, 60)
        self.retry_interval_spin.setValue(5)
        self.retry_interval_spin.setEnabled(False)

        # Enable/disable retry spin boxes based on checkbox state
        self.retry_schedule_cb.toggled.connect(self.retry_count_spin.setEnabled)
        self.retry_schedule_cb.toggled.connect(self.retry_interval_spin.setEnabled)

        retry_layout = QHBoxLayout()
        retry_layout.addWidget(QLabel("Max retries:"))
        retry_layout.addWidget(self.retry_count_spin)
        retry_layout.addSpacing(20)
        retry_layout.addWidget(QLabel("Interval (mins):"))
        retry_layout.addWidget(self.retry_interval_spin)

        conn_layout.addRow(self.retry_schedule_cb)
        conn_layout.addRow(retry_layout)
        


        self.stack.addWidget(conn_widget)
        

    def setup_browser_tab(self):
        browser_widget = QWidget()
        browser_layout = QFormLayout(browser_widget)
        browser_layout.setSpacing(16)

        self.browser_integration_cb = QCheckBox("Enable Browser Integration")
        browser_layout.addRow(self.browser_integration_cb)

        self.stack.addWidget(browser_widget)


    def setup_updates_tab(self):
        updates_widget = QWidget()
        updates_layout = QFormLayout(updates_widget)
        updates_layout.setSpacing(16)

        self.check_interval_combo = QComboBox()
        self.check_interval_combo.addItems(["1", "3", "7", "14"])

        self.version_label = QLabel("App Version: 1.2.24")
        self.check_update_btn = QPushButton("Check for update")

        updates_layout.addRow(QLabel("Check for update every (days):"), self.check_interval_combo)
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

        """

    
    def load_values(self, config):
        self.language_combo.setCurrentText(str(config.lang))
        self.monitor_clipboard_cb.setChecked(config.monitor_clipboard)
        self.show_download_window_cb.setChecked(config.show_download_window)
        self.auto_close_cb.setChecked(config.auto_close_download_window)
        self.show_thumbnail_cb.setChecked(config.show_thumbnail)
        self.on_startup_cb.setChecked(config.on_startup)
        self.setting_scope_combo.setCurrentText('Global' if config.sett_folder == config.global_sett_folder else 'Local')

        seg_size = config.segment_size // 1024
        if seg_size >= 1024:
            seg_size = seg_size // 1024
            seg_unit = 'MB'
        else:
            seg_unit = 'KB'
        self.segment_linedit.setText(str(seg_size))
        self.segment_unit_combo.setCurrentText(seg_unit)

        self.speed_limit_input.setText(str(config.speed_limit))
        self.max_concurrent_combo.setCurrentText(str(config.max_concurrent_downloads))
        self.max_conn_settings_combo.setCurrentText(str(config.max_connections))
        self.proxy_input.setText(config.proxy or '')
        self.proxy_type_combo.setCurrentText(config.proxy_type or 'http')
        self.check_interval_combo.setCurrentText(str(config.update_frequency))

        self.retry_schedule_cb.setChecked(config.retry_scheduled_enabled)
        self.retry_count_spin.setValue(config.retry_scheduled_max_tries)
        self.retry_interval_spin.setValue(config.retry_scheduled_interval_mins)
        self.browser_integration_cb.setChecked(config.browser_integration_enabled)



    
    def accept(self):
        """Override the accept method to apply and save settings when OK is clicked."""
        config.lang = self.language_combo.currentText()
        config.monitor_clipboard = self.monitor_clipboard_cb.isChecked()
        config.show_download_window = self.show_download_window_cb.isChecked()
        config.auto_close_download_window = self.auto_close_cb.isChecked()
        config.show_thumbnail = self.show_thumbnail_cb.isChecked()
        config.on_startup = self.on_startup_cb.isChecked()
        #config.sett_folder = config.global_sett_folder if self.setting_scope_combo.currentText() == "Global" else "Local"
        config.sett_folder = config.global_sett_folder if self.setting_scope_combo.currentText() == "Global" else config.current_directory

        # Segment
        try:
            seg_size = int(self.segment_linedit.text())
            seg_multiplier = 1024 if self.segment_unit_combo.currentText() == "KB" else 1024 * 1024
            config.segment_size = seg_size * seg_multiplier
        except ValueError:
            config.segment_size = 512 * 1024  # fallback default

        # Connection settings
        config.speed_limit = self.speed_limit_input.text()
        config.max_concurrent_downloads = int(self.max_concurrent_combo.currentText())
        config.max_connections = int(self.max_conn_settings_combo.currentText())
        config.proxy = self.proxy_input.text() if self.checkBox_proxy.isChecked() else ""
        config.proxy_type = self.proxy_type_combo.currentText()
        config.update_frequency = int(self.check_interval_combo.currentText())

        config.retry_scheduled_enabled = self.retry_schedule_cb.isChecked()
        config.retry_scheduled_max_tries = self.retry_count_spin.value()
        config.retry_scheduled_interval_mins = self.retry_interval_spin.value()
        config.browser_integration_enabled = self.browser_integration_cb.isChecked()



        # Save settings to disk
        setting.save_setting()

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

        # General Tab
        self.sidebar.item(0).setText(self.tr("General"))
        self.sidebar.item(1).setText(self.tr("Connection"))
        self.sidebar.item(2).setText(self.tr("Browser"))
        self.sidebar.item(3).setText(self.tr("Updates"))

        self.monitor_clipboard_cb.setText(self.tr("Monitor Copied URLs"))
        self.show_download_window_cb.setText(self.tr("Show Download Window"))
        self.auto_close_cb.setText(self.tr("Auto Close DL Window"))
        self.show_thumbnail_cb.setText(self.tr("Show Thumbnail"))
        self.on_startup_cb.setText(self.tr("On Startup"))

        self.segment_unit_combo.setItemText(0, self.tr("KB"))
        self.segment_unit_combo.setItemText(1, self.tr("MB"))

        # Connection Tab
        self.speed_checkBox.setText(self.tr("Speed Limit"))
        self.checkBox_proxy.setText(self.tr("Proxy"))
        self.label_proxy_info.setText(self.tr("Enter a proxy address and select its type. Example: 127.0.0.1:8080"))
        self.retry_schedule_cb.setText(self.tr("Retry failed scheduled downloads"))

        # Retry labels
        self.stack.widget(1).layout().labelForField(self.max_concurrent_combo).setText(self.tr("Max Concurrent Downloads:"))
        self.stack.widget(1).layout().labelForField(self.max_conn_settings_combo).setText(self.tr("Max Connection Settings:"))

        # Updates Tab
        self.check_update_btn.setText(self.tr("Check for update"))
        self.stack.widget(3).layout().labelForField(self.check_interval_combo).setText(self.tr("Check for update every (days):"))

        # Language label and others
        self.stack.widget(0).layout().labelForField(self.language_combo).setText(self.tr("Choose Language:"))
        self.stack.widget(0).layout().labelForField(self.setting_scope_combo).setText(self.tr("Choose Setting:"))
        # self.stack.widget(0).layout().labelForField(self.segment_linedit.parent()).setText(self.tr("Segment:"))



