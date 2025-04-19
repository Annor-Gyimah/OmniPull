from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QMenuBar, QLabel, QPushButton, QGridLayout,
    QProgressBar, QTableWidget, QTableWidgetItem, QStackedWidget, QLineEdit, QFileDialog, QComboBox, QTextEdit,
    QHeaderView,
)
from PySide6.QtGui import QIcon
from random import randint
import os
import psutil
from PySide6.QtCore import QCoreApplication


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setWindowTitle("Download Manager Clone")
        MainWindow.resize(1250, 750)
        MainWindow.setMinimumSize(800, 600)

        self.central = QWidget(MainWindow)
        MainWindow.setCentralWidget(self.central)

        self.main_layout = QVBoxLayout(self.central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Top Menu Bar
        self.top_frame = QFrame()
        self.top_frame.setObjectName("TopFrame")
        self.top_frame.setFixedHeight(35)

        self.top_layout = QHBoxLayout(self.top_frame)
        self.top_layout.setContentsMargins(0, 0, 0, 0)

        self.menubar = QMenuBar()
        self.task_menu = self.menubar.addMenu("Task")
        self.task_menu.addAction("Add New Download")
        self.task_menu.addAction("Import List")

        self.file_menu = self.menubar.addMenu("File")
        self.file_menu.addAction("Open File")
        self.file_menu.addAction("Exit")

        self.downloads_menu = self.menubar.addMenu("Downloads")
        self.downloads_menu.addAction("Start All")
        self.downloads_menu.addAction("Pause All")

        self.view_menu = self.menubar.addMenu("View")
        self.view_menu.addAction("Refresh")

        self.help_menu = self.menubar.addMenu("Help")
        self.help_menu.addAction("About")
        self.help_menu.addAction("Check for Updates")

        self.top_layout.addWidget(self.menubar)
        self.main_layout.addWidget(self.top_frame)

        # Content Area
        self.content_frame = QFrame()
        self.content_layout = QHBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(10)

        # Sidebar with square buttons
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("SidebarFrame")
        self.sidebar_frame.setFixedWidth(180)
        self.sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_layout.setSpacing(20)
        self.sidebar_layout.setContentsMargins(5, 5, 5, 5)

        self.page_buttons = []
        icon_names = ["icons/add.svg", "icons/play.svg", "icons/terminal.svg"]
        for idx, icon_path in enumerate(icon_names):
            btn = QPushButton()
            btn.setFixedSize(150, 100)
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(36, 36))
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #222;
                    border: 1px solid #333;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background-color: #2c2c2c;
                }
            """)
            self.page_buttons.append(btn)
            self.sidebar_layout.addWidget(btn)

        self.sidebar_layout.addStretch()
        total_gb, used_gb, free_gb, percent = self.get_disk_usage("/")
        self.disk_label = QLabel(f"Free: {free_gb} GB / {total_gb} GB")
        self.disk_label.setStyleSheet("color: white; font-size: 11px;")

        self.disk_bar = QProgressBar()
        self.disk_bar.setMinimum(0)
        self.disk_bar.setMaximum(100)
        self.disk_bar.setValue(percent)
        self.disk_bar.setTextVisible(False)
        self.disk_bar.setFixedHeight(10)
        self.disk_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: #00C853;
                border-radius: 5px;
            }
        """)

        self.sidebar_layout.addWidget(self.disk_label)
        self.sidebar_layout.addWidget(self.disk_bar)
        self.content_layout.addWidget(self.sidebar_frame)

        # Stacked Pages
        self.stacked_widget = QStackedWidget()

        # Page 0 - Add Download
        self.page_add = QWidget()
        self.page_add_layout = QVBoxLayout(self.page_add)
        self.page_add_layout.setContentsMargins(40, 40, 40, 40)
        self.page_add_layout.setSpacing(20)
        self.page_add.setStyleSheet("""
            QWidget#page_add {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                border-radius: 14px;
            }
        """)
        self.page_add.setObjectName("page_add")

        # === LINK + Retry
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

        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setFixedWidth(120)
        self.retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c2c2c;
                color: white;
                border: 1px solid #444;
                border-radius: 20px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)

        link_row = QHBoxLayout()
        link_row.addWidget(self.link_input)
        link_row.addWidget(self.retry_btn)
        self.page_add_layout.addLayout(link_row)

        # === PROGRESS BAR
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

        # === FOLDER INPUT
        folder_section = QVBoxLayout()
        folder_section.setSpacing(6)

        self.folder_label = QLabel("CHOOSE FOLDER")
        self.folder_label.setStyleSheet("color: #aaa; font-size: 11px;")
        folder_section.addWidget(self.folder_label)

        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit("/home/username/Downloads")
        self.folder_input.setStyleSheet(self.link_input.styleSheet())
        self.folder_btn = QPushButton("📂 Open")
        self.folder_btn.setFixedWidth(120)
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
        self.thumbnail.setPixmap(QIcon("icons/thumbnail-default.png").pixmap(400, 350))
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.thumbnail.setFixedSize(400, 350)
        self.thumbnail.setStyleSheet("border-radius: 8px;")
        left_layout.addWidget(self.thumbnail)

        content_row.addWidget(left_frame, stretch=2)

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

        self.combo1.setFixedWidth(360)
        self.combo2.setFixedWidth(360)

        combo1_row = QHBoxLayout()
        combo1_label = QLabel("Download Item:")
        combo1_label.setStyleSheet("color: #ccc; font-size: 12px;")
        combo1_row.addWidget(combo1_label)
        combo1_row.addWidget(self.combo1)

        combo2_row = QHBoxLayout()
        combo2_label = QLabel("Resolution:")
        combo2_label.setStyleSheet("color: #ccc; font-size: 12px;")
        combo2_row.addWidget(combo2_label)
        combo2_row.addWidget(self.combo2)

        right_layout.addLayout(combo1_row)
        right_layout.addLayout(combo2_row)

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

        self.playlist_btn = QPushButton("🎵 Playlist")
        self.playlist_btn.setFixedWidth(140)
        self.playlist_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c2c2c;
                color: white;
                border: 1px solid #444;
                border-radius: 14px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
         """)
        self.download_btn = QPushButton("🔄 Download")
        self.download_btn.setStyleSheet(self.retry_btn.styleSheet())
        self.download_btn.setFixedWidth(140)

        button_row.addWidget(self.playlist_btn)
        button_row.addWidget(self.download_btn)
        right_layout.addLayout(button_row)

        content_row.addWidget(right_frame, stretch=1)

        # === WRAP CONTENT IN CONTAINER THAT STRETCHES
        content_container = QVBoxLayout()
        content_container.setContentsMargins(0, 0, 0, 0)
        content_container.setSpacing(0)
        content_container.addLayout(content_row)
        content_container.addStretch(1)

        self.page_add_layout.addLayout(content_container)



        # Centered thumbnail & stacked elements
        # row = QHBoxLayout()
        # row.addSpacing(80)
        # row.setSpacing(10)

        # self.thumbnail = QLabel()
        # self.thumbnail.setPixmap(QIcon("icons/thumbnail-default.png").pixmap(140, 100))
        # self.thumbnail.setStyleSheet("border: 1px solid #333;")
        # self.thumbnail.setFixedSize(140, 100)
        # row.addWidget(self.thumbnail)

        # # Vertical layout for combo boxes & playlist
        # combo_column = QVBoxLayout()
        # combo_column.setSpacing(10)
        # self.combo1 = QComboBox()
        # self.combo1.setFixedWidth(650)
        # self.combo1.addItems(["Option 1", "Option 2"])
        # self.combo1.setStyleSheet(
            
        #     """

        #     QLineEdit, QComboBox {
        #         background-color: rgba(28, 28, 30, 0.55);  /* Neutral frosted charcoal */
        #         color: #e0e0e0;
        #         border: 1px solid rgba(255, 255, 255, 0.05);
        #         border-radius: 6px;
        #         padding: 6px 10px;
        #     }

        #     QLineEdit:hover, QComboBox:hover {
        #         border: 1px solid rgba(111, 255, 176, 0.18);  /* subtle emerald glow on hover */
        #     }

        #     QComboBox::drop-down {
        #         border: none;
        #         background-color: transparent;
        #     }

        #     QComboBox QAbstractItemView {
        #         background-color: rgba(20, 25, 20, 0.95);
        #         border: 1px solid rgba(60, 200, 120, 0.25);
        #         selection-background-color: #2DE099;
        #         color: white;
        #     }



        #     """
        # )

        # self.combo2 = QComboBox()
        # self.combo2.addItems(["Option A", "Option B"])
        # self.combo2.setFixedWidth(650)
        # self.combo2.setStyleSheet(self.combo1.styleSheet())

        # self.playlist_btn = QPushButton("\ud83c\udfb5 Playlist")
        # self.playlist_btn.setFixedSize(120, 32)
        # self.playlist_btn.setStyleSheet("""
        #     QPushButton {
        #         background-color: #2c2c2c;
        #         color: white;
        #         border: 1px solid #444;
        #         border-radius: 14px;
        #         padding: 4px 10px;
        #     }
        #     QPushButton:hover {
        #         background-color: #3a3a3a;
        #     }
        # """)
        # combo_column.addWidget(self.combo1)
        # combo_column.addWidget(self.combo2)
        # combo_column.addSpacing(8)
        # combo_column.addWidget(self.playlist_btn)

        # row.addLayout(combo_column)
        # self.page_add_layout.addLayout(row)
        # self.page_add_layout.addSpacing(20)  # Space between thumbnail/combo layout and metadata

        # # Metadata center aligned individual labels
        # self.page_add_layout.addSpacing(10)
        # meta_row = QHBoxLayout()
        # meta_row.setSpacing(40)
        # meta_row.setAlignment(Qt.AlignCenter)

        # self.size_label = QLabel("Size: ")
        # self.size_value = QLabel("Unknown")
        # self.type_label = QLabel("Type: ")
        # self.type_value = QLabel("Unknown")
        # self.protocol_label = QLabel("Protocol: ")
        # self.protocol_value = QLabel("--")
        # self.resume_label = QLabel("Resumable: ")
        # self.resume_value = QLabel("No")

        # for label in [self.size_label, self.size_value, self.type_label, self.type_value,
        #             self.protocol_label, self.protocol_value, self.resume_label, self.resume_value]:
        #     label.setStyleSheet("color: #bbb; font-size: 12px;")
        #     meta_row.addWidget(label)

        # self.page_add_layout.addLayout(meta_row)
        # self.page_add_layout.addStretch()

        # # Download button
        # self.download_btn = QPushButton("\ud83d\udd04 Download")
        # self.download_btn.setStyleSheet(self.retry_btn.styleSheet())
        # self.page_add_layout.addWidget(self.download_btn, alignment=Qt.AlignCenter)

        # Add updated page to stack
        # self.stacked_widget.insertWidget(0, self.page_add)

        self.stacked_widget.addWidget(self.page_add)
        
        # # Page 1 - Toolbar + Table
        # self.toolbar_frame = QFrame()
        # self.toolbar_layout = QHBoxLayout(self.toolbar_frame)
        # self.toolbar_layout.setSpacing(10)

        # self.toolbar_buttons = {}
        # icon_map = {
        #     "Resume": "icons/play.svg",
        #     "Pause": "icons/pause.svg",
        #     "Stop": "icons/stop.svg",
        #     "Stop All": "icons/stop_all.svg",
        #     "Delete": "icons/trash.svg",
        #     "Delete All": "icons/multi_trash.svg",
        #     "Refresh": "icons/refresh.svg",
        #     "Resume All": "icons/resume_all.svg",
        #     "Schedule All": "icons/sche.png",
        #     "Settings": "icons/setting.svg",
        #     "Download Window": "icons/d_window.png",
        #     "Stop Queue": "icons/delete_all.svg",
        #     "Grabber": "icons/delete_all.svg",
        #     "Tell a Friend": "icons/delete_all.svg"
        # }

        # for label, icon_path in icon_map.items():
        #     btn = QPushButton()
        #     btn.setToolTip(label)
        #     if os.path.exists(icon_path):
        #         icon = QIcon(icon_path)
        #         btn.setIcon(icon)
        #         btn.setIconSize(QSize(42, 42))
        #         btn.setFixedSize(50, 50)
        #     else:
        #         btn.setText(label)
        #     btn.setStyleSheet("""
        #         QPushButton {
        #             background-color: transparent;
        #             border: none;
        #             border-radius: 6px;
        #             padding: 6px;
        #         }
        #         QPushButton:hover {
        #             background-color: #2e2e2e;
        #         }
        #     """)
        #     self.toolbar_buttons[label] = btn
        #     self.toolbar_layout.addWidget(btn)

        # self.toolbar_layout.addStretch()

        # self.table = QTableWidget(5, 9)
        # self.table.setHorizontalHeaderLabels(["ID", "Name", "Progress", "Speed", "Left", "Done", "Size", "Status", "I"])
        # self.table.setSelectionBehavior(QTableWidget.SelectRows)
        # self.table.setAlternatingRowColors(True)
        # self.table.verticalHeader().setVisible(False)

        # for row in range(5):
        #     for col in range(9):
        #         if col == 2:
        #             progress = QProgressBar()
        #             progress.setRange(0, 100)
        #             # progress_value = randint(10, 90)
        #             # progress.setValue(progress_value)
        #             progress.setTextVisible(True)
                    
        #             progress.setStyleSheet("""
        #                 QProgressBar {
        #                     background-color: #2a2a2a;
        #                     border: 1px solid #444;
        #                     border-radius: 4px;
        #                     text-align: center;
        #                     color: white;
        #                 }
        #                 QProgressBar::chunk {
        #                     background-color: #00C853;
        #                     border-radius: 4px;
        #                 }
        #             """)
        #             self.table.setCellWidget(row, col, progress)
        #         else:
        #             self.table.setItem(row, col, QTableWidgetItem(f"Sample {row}-{col}"))

        # self.page_table = QWidget()
        # self.page_table_layout = QVBoxLayout(self.page_table)
        # self.page_table_layout.setContentsMargins(0, 0, 0, 0)
        # self.page_table_layout.addWidget(self.toolbar_frame)
        # self.page_table_layout.addWidget(self.table)
        # self.stacked_widget.addWidget(self.page_table)

        # Page 1 - Toolbar + Table
        self.toolbar_frame = QFrame()
        self.toolbar_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(10, 18, 15, 0.6);
                border-radius: 8px;
            }
        """)
        self.toolbar_layout = QHBoxLayout(self.toolbar_frame)
        self.toolbar_layout.setSpacing(10)
        self.toolbar_layout.setContentsMargins(10, 10, 10, 10)

        self.toolbar_buttons = {}
        icon_map = {
            "Resume": "icons/play.svg",
            "Pause": "icons/pause.svg",
            "Stop": "icons/stop.svg",
            "Stop All": "icons/stop_all.svg",
            "Delete": "icons/trash.svg",
            "Delete All": "icons/multi_trash.svg",
            "Refresh": "icons/refresh.svg",
            "Resume All": "icons/resume_all.svg",
            "Schedule All": "icons/sche.png",
            "Settings": "icons/setting.svg",
            "Download Window": "icons/d_window.png",
            "Stop Queue": "icons/delete_all.svg",
            "Grabber": "icons/delete_all.svg",
            "Tell a Friend": "icons/delete_all.svg"
        }

        for label, icon_path in icon_map.items():
            btn = QPushButton()
            btn.setToolTip(label)
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                btn.setIcon(icon)
                btn.setIconSize(QSize(42, 42))
                btn.setFixedSize(50, 50)
            else:
                btn.setText(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(30, 40, 30, 0.2);
                    border: 1px solid rgba(0, 255, 180, 0.08);
                    border-radius: 10px;
                    padding: 6px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 255, 180, 0.15);
                }
            """)
            self.toolbar_buttons[label] = btn
            self.toolbar_layout.addWidget(btn)

        self.toolbar_layout.addStretch()

        self.table = QTableWidget(5, 9)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Progress", "Speed", "Left", "Done", "Size", "Status", "I"])
        #self.table.setColumnWidth(1, 200)  # Adjust the value (e.g., 240) as needed
        

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(1, 240)  # Customize this value as needed

        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                ); 
                color: white;
                border: none;
                padding: 6px 16px;
                border: 1px solid rgba(0, 255, 180, 0.1);
                gridline-color: rgba(255, 255, 255, 0.05);
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                );
                color: white;
                padding: 4px;
                border: none;
                color: white;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: rgba(0, 255, 180, 0.25);
            }
        """)

        for row in range(5):
            for col in range(9):
                if col == 2:
                    progress = QProgressBar()
                    progress.setRange(0, 100)
                    progress.setTextVisible(True)
                    progress.setStyleSheet("""
                        QProgressBar {
                            background-color: rgba(20, 20, 20, 0.4);
                            border: 1px solid rgba(0, 255, 180, 0.1);
                            border-radius: 4px;
                            text-align: center;
                            color: white;
                        }
                        QProgressBar::chunk {
                            background-color: #00C853;
                            border-radius: 4px;
                        }
                    """)
                    self.table.setCellWidget(row, col, progress)
                else:
                    self.table.setItem(row, col, QTableWidgetItem(f"Sample {row}-{col}"))

        self.page_table = QWidget()
        self.page_table_layout = QVBoxLayout(self.page_table)
        self.page_table_layout.setContentsMargins(0, 0, 0, 0)
        self.page_table_layout.setSpacing(8)
        self.page_table_layout.addWidget(self.toolbar_frame)
        self.page_table_layout.addWidget(self.table)
        self.stacked_widget.addWidget(self.page_table)


        # Page 2 - Terminal Logs
        self.page_terminal = QWidget()
        self.page_terminal_layout = QVBoxLayout(self.page_terminal)
        # self.page_terminal.setStyleSheet("background-color: #1e1e1e;")
        self.page_terminal.setStyleSheet("""
            QWidget#page_add {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                border-radius: 14px;
            }
        """)
        self.page_terminal_layout.setSpacing(10)

        # Top controls row
        top_row = QHBoxLayout()
        top_row.setContentsMargins(10, 10, 10, 0)

        self.detailed_label = QLabel("Detailed Events")
        self.detailed_label.setStyleSheet("color: white; font-size: 12px;")

        self.log_level_label = QLabel("Log Level:")
        self.log_level_label.setStyleSheet("color: white; font-size: 12px;")

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["1", "2", "3"])
        self.log_level_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #444;
                padding: 4px;
                border-radius: 4px;
            }
        """)

        self.log_clear_btn = QPushButton("Clear")
        self.log_clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #00C853;
                color: black;
                padding: 4px 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33d47c;
            }
        """)

        top_row.addWidget(self.detailed_label)
        top_row.addStretch()
        top_row.addWidget(self.log_level_label)
        top_row.addWidget(self.log_level_combo)
        top_row.addWidget(self.log_clear_btn)

        # Log display QTextEdit
        self.terminal_log = QTextEdit()
        self.terminal_log.setReadOnly(True)
        self.terminal_log.setStyleSheet("""
            QTextEdit {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                );
                border-radius: 16px;
                color: white;
                border: 1px solid #333;
                font-family: Consolas, Courier New, monospace;
                font-size: 12px;
                padding: 10px;
            }
        """)

        self.page_terminal_layout.addLayout(top_row)
        self.page_terminal_layout.addWidget(self.terminal_log)
        self.stacked_widget.addWidget(self.page_terminal)


        for i, btn in enumerate(self.page_buttons):
            btn.clicked.connect(lambda _, idx=i: self.stacked_widget.setCurrentIndex(idx))

        self.page_buttons[1].setChecked(True)
        self.stacked_widget.setCurrentIndex(0)

        self.content_layout.addWidget(self.stacked_widget)
        self.main_layout.addWidget(self.content_frame)

        # Global footer status bar
        self.status_frame = QFrame()
        self.status_frame.setObjectName("StatusFrame")
        self.status_frame.setFixedHeight(30)
        self.status_layout = QHBoxLayout(self.status_frame)
        self.status_layout.setContentsMargins(10, 0, 10, 0)
        self.status_layout.setSpacing(30)
        self.status_frame.setSizePolicy(self.content_frame.sizePolicy())

        self.brand = QLabel("YourBrand")
        self.status_layout.addWidget(self.brand)
        self.status_layout.addStretch(1)
        
        self.status_layout.addWidget(QLabel("Status:"))
        self.status_value = QLabel("")
        self.status_layout.addWidget(self.status_value)
        self.status_layout.addStretch(1)
        self.status_layout.addWidget(QLabel("Speed:"))
        self.speed_value = QLabel("")
        self.status_layout.addWidget(self.speed_value)
        self.status_layout.addStretch(1)
        self.version_value = QLabel("")
        self.status_layout.addWidget(self.version_value)

        self.main_layout.addWidget(self.status_frame)

    def get_disk_usage(self, path="/"):
        usage = psutil.disk_usage(path)
        total_gb = usage.total // (1024**3)
        used_gb = usage.used // (1024**3)
        free_gb = total_gb - used_gb
        percent = usage.percent
        return total_gb, used_gb, free_gb, percent
