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

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel,  QPushButton, QScrollArea, QWidget, QHBoxLayout


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

        getting_started = self.tr("Getting Started")
        download_management = self.tr("Download Management")
        queues = self.tr("Queues")
        schedulling = self.tr("Scheduling")
        youtube_streaming = self.tr("YouTube & Streaming")
        browser_extension = self.tr("Browser Extension")
        settings = self.tr("Settings")
        updates = self.tr("Updates")
        tips = self.tr("Tips")

        a1 = self.tr("• Copy a download link which gets automatically detected from clipboard.")
        b1 = self.tr("• Choose a folder to save the file.")
        c1 = self.tr("• For YouTube videos or playlists, OmniPull automatically detects available formats.")

        a2 = self.tr("• Downloads appear in the main table with real-time progress.")
        b2 = self.tr("• Use the sidebar to switch between Add Downloads, Download Table, and Logs.")

        a3 = self.tr("• You can add static files to queues.")
        b3 = self.tr("• Queued items will download sequentially or on schedule.")
        c3 = self.tr("• Right-click an item to add/remove from a queue.")

        a4 = self.tr("• Schedule downloads by right-clicking and selecting 'Schedule Download'.")
        b4 = self.tr("• Queued items can be started at specific times automatically.")

        a5 = self.tr("• OmniPull uses yt-dlp to process YouTube/streaming content.")
        b5 = self.tr("• These downloads cannot be added to queues (streaming limitations)")
        c5 = self.tr("• Merging (via FFmpeg) is handled automatically after download.")

        a6 = self.tr("• Install the OmniPull extension for Chrome, Firefox, or Edge via the Tools menu.")
        b6 = self.tr("• Enables 'Download with OmniPull' from browser context menus.")

        a7 = self.tr("• Access global or local settings (theme, clipboard monitoring, download folder).")
        b7 = self.tr("• Settings are saved per system or per user depending on your scope.")

        a8 = self.tr("• OmniPull checks for updates periodically in the background.")
        b8 = self.tr("• You can manually check via Help → Check for Updates.")

        a9 = self.tr('• Right-click any row in the table for powerful actions (Open, Watch, Schedule).')
        b9 = self.tr("• Use the menubar or toolbar buttons to manage all downloads at once.")


        sections = [
            (f"💡 {getting_started}",
             f"{a1} \n"
             f"{b1} \n"
             f"{c1}"),

            (f"⏬ {download_management}",
             f"{a2}\n"
             f"{b2}"),

            (f"📂 {queues}",
             f"{a3}\n"
             f"{b3}\n"
             f"{c3}"),

            (f"🗓 {schedulling}",
             f"{a4}\n"
             f"{b4}"),

            (f"📹 {youtube_streaming}",
             f"{a5}\n"
             f"{b5}\n"
             f"{c5}"),

            (f"🧩 {browser_extension}",
             f"{a6}\n"
             f"{b6}"),

            (f"⚙ {settings}",
             f"{a7}\n"
             f"{b7}"),

            (f"🆕 {updates}",
             f"{a8}\n"
             f"{b8}"),

            (f"❓ {tips}",
             f"{a9}\n"
             f"{b9}"),
        ]

        icon_paths = {
           self.tr("Getting Started"): ":/icons/started.svg",
           self.tr("Download Management"): ":/icons/d_window.png",
           self.tr("Queues"): ":/icons/queues.png",
           self.tr("Scheduling"): ":/icons/gnome-schedule.svg",
           self.tr("YouTube & Streaming"): ":/icons/youtube.svg",
           self.tr("Browser Extension"): ":/icons/internet-web-browser.svg",
           self.tr("Settings"): ":/icons/setting.svg",
           self.tr("Updates"): ":/icons/system-upgrade.svg",
           self.tr("Tips"): ":/icons/tips.svg"
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

        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)