# user_guide_dialog.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QScrollArea, QWidget, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

class UserGuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OmniPull - User Guide")
        self.setStyleSheet(self.dark_stylesheet())
        self.setMinimumSize(600, 500)
        self.setup_ui()

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

        QWidget#scrollContent {
            background-color: transparent;  /* or try a dark color like #111 for solid */
        }

        QScrollArea {
            background-color: transparent;
            border: none;
        }
        QScrollArea > QWidget > QWidget {
            background-color: transparent;
        }



        """

    def setup_ui(self):
        layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")
        scroll_layout = QVBoxLayout(scroll_content)

        sections = [
            ("💡 Getting Started",
             "• Copy a download link which gets automatically detected from clipboard. \n"
             "• Choose a folder to save the file.\n"
             "• For YouTube videos or playlists, OmniPull automatically detects available formats."),

            ("⏬ Download Management",
             "• Downloads appear in the main table with real-time progress.\n"
             "• Use the sidebar to switch between Add Downloads, Download Table, and Logs."),

            ("📂 Queues",
             "• You can add static files to queues.\n"
             "• Queued items will download sequentially or on schedule.\n"
             "• Right-click an item to add/remove from a queue."),

            ("🗓 Scheduling",
             "• Schedule downloads by right-clicking and selecting 'Schedule Download'.\n"
             "• Queued items can be started at specific times automatically."),

            ("📹 YouTube & Streaming",
             "• OmniPull uses yt-dlp to process YouTube/streaming content.\n"
             "• These downloads cannot be added to queues (streaming limitations).\n"
             "• Merging (via FFmpeg) is handled automatically after download."),

            ("🧩 Browser Extension",
             "• Install the OmniPull extension for Chrome, Firefox, or Edge via the Tools menu.\n"
             "• Enables 'Download with OmniPull' from browser context menus."),

            ("⚙ Settings",
             "• Access global or local settings (theme, clipboard monitoring, download folder).\n"
             "• Settings are saved per system or per user depending on your scope."),

            ("🆕 Updates",
             "• OmniPull checks for updates periodically in the background.\n"
             "• You can manually check via Help → Check for Updates."),

            ("❓ Tips",
             "• Right-click any row in the table for powerful actions (Open, Watch, Schedule).\n"
             "• Use the menubar or toolbar buttons to manage all downloads at once."),
        ]

        icon_paths = {
            "Getting Started": ":/icons/started.svg",
            "Download Management": ":/icons/d_window.png",
            "Queues": ":/icons/queues.png",
            "Scheduling": ":/icons/gnome-schedule.svg",
            "YouTube & Streaming": ":/icons/youtube.svg",
            "Browser Extension": ":/icons/internet-web-browser.svg",
            "Settings": ":/icons/setting.svg",
            "Updates": ":/icons/system-upgrade.svg",
            "Tips": ":/icons/tips.svg"
        }

        for title, body in sections:
            section_name = title.split(' ', 1)[-1]  # Get name without emoji
            icon_path = icon_paths.get(section_name)

            # Layout for title row
            title_row = QHBoxLayout()

            if icon_path:
                icon_label = QLabel()
                pixmap = QPixmap(icon_path).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_label.setPixmap(pixmap)
                icon_label.setFixedSize(21, 21)
                title_row.addWidget(icon_label)

            text_label = QLabel(section_name)
            text_label.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 2px;")
            title_row.addWidget(text_label)
            title_row.addStretch()

            scroll_layout.addLayout(title_row)

            body_label = QLabel(body)
            body_label.setWordWrap(True)
            body_label.setStyleSheet("font-size: 13px; margin-bottom: 8px;")
            scroll_layout.addWidget(body_label)

        # for title, body in sections:
        #     title_label = QLabel(title)
        #     title_label.setStyleSheet("font-weight: bold; font-size: 15px; margin-top: 12px;")
        #     text = QLabel(body)
        #     text.setWordWrap(True)
        #     text.setStyleSheet("font-size: 13px; margin-bottom: 8px;")

        #     scroll_layout.addWidget(title_label)
        #     scroll_layout.addWidget(text)

        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
