from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QMenuBar, QMenu, QPushButton,
    QLabel, QTableWidgetItem, QProgressBar, QTableWidget, QSizePolicy
)
from ui.table import DownloadTable  # Assuming you place DownloadTable class in table.py
from PySide6.QtGui import QIcon
import os
import psutil
from random import randint


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setWindowTitle("Download Manager Clone")
        MainWindow.resize(1200, 750)
        MainWindow.setMinimumSize(800, 600)

        self.central = QWidget(MainWindow)
        MainWindow.setCentralWidget(self.central)

        self.main_layout = QVBoxLayout(self.central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Top Frame (gradient header with menu)
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

        # Content Area: Sidebar + Body
        self.content_frame = QFrame()
        self.content_layout = QHBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(10)

        # Sidebar
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("SidebarFrame")
        self.sidebar_frame.setFixedWidth(200)
        self.sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_layout.setSpacing(10)

        self.sidebar_buttons = []
        for section in [
            "All Downloads", "Compressed", "Documents", "Music",
            "Programs", "Video", "Unfinished", "Finished", "Grabber Projects", "Queues"
        ]:
            btn = QPushButton(section)
            self.sidebar_buttons.append(btn)
            self.sidebar_layout.addWidget(btn)
        

        self.sidebar_layout.addStretch()

        # Disk usage
        total_gb, used_gb, free_gb, percent = self.get_disk_usage("/")
        self.disk_label = QLabel(f"Free: {free_gb} GB / {total_gb} GB    {percent} %")
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

        # Body layout (toolbar + table)
        self.body_frame = QFrame()
        self.body_layout = QVBoxLayout(self.body_frame)
        self.body_layout.setSpacing(10)
        self.body_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.toolbar_frame = QFrame()
        self.toolbar_frame.setObjectName("ToolbarFrame")
        self.toolbar_layout = QHBoxLayout(self.toolbar_frame)
        self.toolbar_layout.setSpacing(10)

        
        self.toolbar_buttons = {}

        icon_map = {
            "Add URL": "icons/add.svg",
            "Resume": "icons/play.svg",
            "Pause": "icons/pause.svg",
            "Stop": "icons/stop.svg",
            "Stop All": "icons/stop_all.svg",
            "Delete": "icons/trash.svg",
            "Delete All": "icons/multi_trash.svg",
            "Refresh": "icons/refresh.svg",
            "Scheduler": "icons/sche.png", 
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
                btn.setIconSize(QSize(42, 42))  # Bigger and cleaner
                btn.setFixedSize(50, 50)        # Match icon, give a little padding
            else:
                btn.setText(label)  # fallback in dev mode

            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                    padding: 6px;
                }
                QPushButton:hover {
                    background-color: #2e2e2e;
                }
            """)

            self.toolbar_buttons[label] = btn
            self.toolbar_layout.addWidget(btn)

        self.toolbar_layout.addStretch()
        self.body_layout.addWidget(self.toolbar_frame)

        # Table
        self.table_frame = QFrame()
        self.table_frame.setObjectName("TableFrame")
        self.table_layout = QVBoxLayout(self.table_frame)
        self.table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = DownloadTable(5, 9)
        #self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Progress", "Speed", "Left", "Done", "Size", "Status", "I"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
       # self.table.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.table.setAlternatingRowColors(True)

        for row in range(5):
            for col in range(9):
                if col == 2:  # Progress column
                    progress = QProgressBar()
                    progress.setRange(0, 100)
                    progress_value = randint(10, 90)
                    progress.setValue(progress_value)
                    progress.setTextVisible(True)
                    progress.setFormat(f"{progress_value}%")
                    progress.setStyleSheet("""
                        QProgressBar {
                            background-color: #2a2a2a;
                            border: 1px solid #444;
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


        self.table_layout.addWidget(self.table)
        self.body_layout.addWidget(self.table_frame)

        # Status / Queue bar
        self.status_frame = QFrame()
        self.status_frame.setObjectName("StatusFrame")
        self.status_layout = QHBoxLayout(self.status_frame)
        self.status_layout.setContentsMargins(10, 4, 10, 4)
        self.status_layout.setSpacing(30)

        self.brand_label = QLabel("YourBrand")
        self.status_label = QLabel("Status:")
        self.status_value = QLabel("Idle")
        self.speed_label = QLabel("Speed:")
        self.speed_value = QLabel("0 KB/s")
        self.version_label = QLabel("v1.0.0")

        self.status_layout.addWidget(self.brand_label)
        self.status_layout.addStretch(1)

        self.status_layout.addWidget(self.status_label)
        self.status_layout.addWidget(self.status_value)
        self.status_layout.addStretch(1)

        self.status_layout.addWidget(self.speed_label)
        self.status_layout.addWidget(self.speed_value)
        self.status_layout.addStretch(1)

        self.status_layout.addWidget(self.version_label)


        self.status_layout.addStretch()
        self.body_layout.addWidget(self.status_frame)


        self.content_layout.addWidget(self.body_frame)
        self.main_layout.addWidget(self.content_frame)

    def get_disk_usage(self, path="/"):
        usage = psutil.disk_usage(path)
        total_gb = usage.total // (1024**3)
        used_gb = usage.used // (1024**3)
        free_gb = total_gb - used_gb
        percent = usage.percent
        return total_gb, used_gb, free_gb, percent

