from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QLineEdit,
    QProgressBar, QComboBox, QGridLayout, QPushButton, QSizePolicy, QDialog
)
import resources_rc  # keep this if you use :/icons paths


class AddDownloadPage(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # this matches old: self.page_add = QWidget()
        self.setObjectName("page_add")
        self.setStyleSheet("""
            QWidget#page_add {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                border-radius: 14px;
            }
        """)

        self.page_add_layout = QVBoxLayout(self)
        self.page_add_layout.setContentsMargins(40, 40, 40, 40)
        self.page_add_layout.setSpacing(20)

        # === LINK + Retry (copied from your Page 0)
        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("Place download link here")
        self.link_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(28, 28, 30, 0.55);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 6px 10px;
            }
            QLineEdit:hover {
                border: 1px solid rgba(111, 255, 176, 0.18);
            }
        """)

        self.retry_btn = QPushButton("")
        self.retry_btn.setIcon(QIcon(":/icons/retry.png"))
        self.retry_btn.setIconSize(QSize(42, 42))
        self.retry_btn.setFixedSize(50, 50)
        self.retry_btn.setStyleSheet("""
            QPushButton {
                color: white;
                border-radius: 20px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 180, 0.1);
            }
        """)

        link_row = QHBoxLayout()
        link_row.addWidget(self.link_input)
        link_row.addWidget(self.retry_btn)
        self.page_add_layout.addLayout(link_row)

        # === PROGRESS BAR (same as before)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("0%")
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 5px;
                height: 20px;
                color: white;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #ff33cc;
                border-radius: 5px;
            }
        """)
        self.page_add_layout.addWidget(self.progress)

        # === FOLDER INPUT (copy from ui_main Page 0)
        folder_section = QVBoxLayout()
        folder_section.setSpacing(6)

        self.folder_label = QLabel("CHOOSE FOLDER")
        self.folder_label.setStyleSheet("color: #aaa; font-size: 11px;")
        folder_section.addWidget(self.folder_label)

        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit("/home/username/Downloads")
        self.folder_input.setStyleSheet(self.link_input.styleSheet())
        self.folder_btn = QPushButton()
        self.folder_btn.setIcon(QIcon(":/icons/folder.png"))
        self.folder_btn.setIconSize(QSize(42, 42))
        self.folder_btn.setFixedSize(55, 55)
        self.folder_btn.setStyleSheet(self.retry_btn.styleSheet())
        folder_row.addWidget(self.folder_input)
        folder_row.addWidget(self.folder_btn)
        folder_section.addLayout(folder_row)

        self.page_add_layout.addLayout(folder_section)

        # === FILENAME INPUT
        filename_section = QVBoxLayout()
        filename_section.setSpacing(6)

        self.filename_label = QLabel("FILENAME")
        self.filename_label.setStyleSheet("color: #aaa; font-size: 11px;")
        filename_section.addWidget(self.filename_label)

        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Filename goes here")
        self.filename_input.setStyleSheet(self.link_input.styleSheet())
        filename_section.addWidget(self.filename_input)

        self.page_add_layout.addLayout(filename_section)

        # === CONTENT ROW (Thumbnail + Right Panel)
        content_row = QHBoxLayout()
        content_row.setSpacing(20)

        # LEFT PANEL (Thumbnail)
        left_frame = QFrame()
        left_frame.setFrameShape(QFrame.StyledPanel)
        left_frame.setStyleSheet("""
            QFrame {
                
                border-radius: 10px;
                
            }
        """)
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setAlignment(Qt.AlignCenter)

        self.thumbnail = QLabel()
        self.thumbnail.setPixmap(QIcon(":/icons/thumbnail-default.png").pixmap(400, 350))
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.thumbnail.setFixedSize(400, 350)
        self.thumbnail.setStyleSheet("border-radius: 8px;")
        left_layout.addWidget(self.thumbnail)

        

        # RIGHT PANEL
        right_frame = QFrame()
        right_frame.setFrameShape(QFrame.StyledPanel)
        right_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #333;
                border-radius: 10px;
                background-color: rgba(20, 20, 20, 0.2);
            }
        """)
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        self.combo1 = QComboBox()
        self.combo2 = QComboBox()
        self.combo3 = QComboBox()
        self.combo1.setStyleSheet(
            
            """

            QLineEdit, QComboBox {
                background-color: rgba(28, 28, 30, 0.55);  /* Neutral frosted charcoal */
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 6px 10px;
            }

            QLineEdit:hover, QComboBox:hover {
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
        """
        )
        self.combo2.setStyleSheet(self.combo1.styleSheet())
        self.combo3.setStyleSheet(self.combo1.styleSheet())

        self.combo1.setFixedWidth(360)
        self.combo2.setFixedWidth(360)
        self.combo3.setFixedWidth(360)

        combo1_row = QHBoxLayout()
        self.combo1_label = QLabel("Download Item:")
        self.combo1_label.setStyleSheet("color: #ccc; font-size: 12px;")
        combo1_row.addWidget(self.combo1_label)
        combo1_row.addWidget(self.combo1)

        combo2_row = QHBoxLayout()
        self.combo2_label = QLabel("Resolution:")
        self.combo2_label.setStyleSheet("color: #ccc; font-size: 12px;")
        combo2_row.addWidget(self.combo2_label)
        combo2_row.addWidget(self.combo2)

        combo3_row = QHBoxLayout()
        self.combo3_label = QLabel("Queue:")
        self.combo3_label.setStyleSheet("color: #ccc; font-size: 12px;")
        combo3_row.addWidget(self.combo3_label)
        combo3_row.addWidget(self.combo3)

        right_layout.addLayout(combo1_row)
        right_layout.addLayout(combo2_row)
        right_layout.addLayout(combo3_row)

        # METADATA
        info_row = QGridLayout()
        info_row.setHorizontalSpacing(16)

        self.size_label = QLabel("Size:")
        self.size_value = QLabel("Unknown")
        self.type_label = QLabel("Type:")
        self.type_value = QLabel("Unknown")
        self.protocol_label = QLabel("Protocol:")
        self.protocol_value = QLabel("--")
        self.resume_label = QLabel("Resumable:")
        self.resume_value = QLabel("No")

        labels = [self.size_label, self.type_label, self.protocol_label, self.resume_label]
        values = [self.size_value, self.type_value, self.protocol_value, self.resume_value]

        for lbl in labels:
            lbl.setStyleSheet("color: #eee; font-size: 12px; background: transparent; border: none;")
        for val in values:
            val.setStyleSheet("color: #eee; font-size: 12px; background: transparent; border: none;")

        info_row.addWidget(self.size_label, 0, 0)
        info_row.addWidget(self.size_value, 0, 1)
        info_row.addWidget(self.type_label, 0, 2)
        info_row.addWidget(self.type_value, 0, 3)
        info_row.addWidget(self.protocol_label, 1, 0)
        info_row.addWidget(self.protocol_value, 1, 1)
        info_row.addWidget(self.resume_label, 1, 2)
        info_row.addWidget(self.resume_value, 1, 3)

        right_layout.addLayout(info_row)

        # BUTTONS
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.setContentsMargins(4, 1, 4, 4)
        self.playlist_btn = QPushButton("")
        self.playlist_btn.setIcon(QIcon(":/icons/playlist.png"))
        self.playlist_btn.setIconSize(QSize(62, 62))
        self.playlist_btn.setFixedSize(75, 75)
        self.playlist_btn.setStyleSheet(self.retry_btn.styleSheet())
        self.playlist_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border-radius: 20px;
                padding: 5px; /* 👈 required to prevent offset */
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 180, 0.08);  /* clean, modern hover */
            }
        """)
        self.download_btn = QPushButton()
        
        self.download_btn.setText("")  # Clear hidden text
        self.download_btn.setIcon(QIcon(":/icons/download.png"))
        self.download_btn.setIconSize(QSize(62, 62))
        self.download_btn.setFixedSize(75, 75)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border-radius: 20px;
                padding: 5px; /* 👈 required to prevent offset */
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 180, 0.08);  /* clean, modern hover */
            }
        """)

        self.download_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.download_btn.setContentsMargins(0, 0, 0, 0)

        



        button_row.addWidget(self.playlist_btn)
        button_row.addWidget(self.download_btn)
        right_layout.addLayout(button_row)


        # NEW: Middle Frame
        middle_frame = QFrame()
        middle_frame.setFrameShape(QFrame.StyledPanel)
        middle_layout = QVBoxLayout(middle_frame)
        middle_layout.setContentsMargins(12, 12, 12, 12)
        middle_layout.setSpacing(8)

        # Optional placeholder content
        middle_label = QLabel("Subtitles / Extras")
        middle_label.setStyleSheet("color: white;")
        middle_layout.addWidget(middle_label)

        # content_row.addWidget(middle_frame, stretch=1)  # 👈 NEW PANEL
        content_row.addWidget(left_frame, stretch=1)
       
        content_row.addWidget(right_frame, stretch=1)

        # === WRAP CONTENT IN CONTAINER THAT STRETCHES
        content_container = QVBoxLayout()
        content_container.setContentsMargins(0, 0, 0, 0)
        content_container.setSpacing(0)
        content_container.addLayout(content_row)
        content_container.addStretch(1)

        self.page_add_layout.addLayout(content_container)