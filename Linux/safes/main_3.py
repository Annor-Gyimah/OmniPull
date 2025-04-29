import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QMenuBar, QMenu, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QProgressBar
)
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QRectF, QSize
import psutil


class DownloadTable(QTableWidget):
    def __init__(self, rows, columns, parent=None):
        super().__init__(rows, columns, parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

    def open_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return

        row = index.row()
        menu = QMenu(self)

        resume = menu.addAction("▶ Resume")
        pause = menu.addAction("⏸ Pause")
        delete = menu.addAction("🗑 Delete")
        open_file = menu.addAction("📂 Open File")

        action = menu.exec_(self.mapToGlobal(pos))

        if action == resume:
            print(f"[Row {row}] Resume clicked")
        elif action == pause:
            print(f"[Row {row}] Pause clicked")
        elif action == delete:
            print(f"[Row {row}] Delete clicked")
        elif action == open_file:
            print(f"[Row {row}] Open File clicked")


class SemiCircularDiskWidget(QWidget):
    def __init__(self, used=60, total=100, parent=None):
        super().__init__(parent)
        self.used = used
        self.total = total
        self.percent = int((used / total) * 100) if total else 0
        self.setMinimumSize(200, 100)

    def set_usage(self, used, total):
        self.used = used
        self.total = total
        self.percent = int((used / total) * 100) if total else 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)

            width = self.width()
            height = self.height()
            margin = 20
            arc_rect = QRectF(margin, margin, width - 2 * margin, (height * 2) - 2 * margin)

            # Background arc
            pen = QPen(Qt.gray, 10)
            painter.setPen(pen)
            painter.drawArc(arc_rect, 0 * 16, 180 * 16)

            # Used arc (green)
            pen = QPen(QColor("#00C853"), 10)
            painter.setPen(pen)
            span = int(180 * self.percent / 100)
            painter.drawArc(arc_rect, 0 * 16, span * 16)

            # Text positions
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(Qt.white)

            # Used text (left)
            used_text = f"Used: {self.used} GB"
            painter.drawText(10, height - 10, used_text)

            # Center percent
            percent_text = f"{self.percent}%"
            percent_width = painter.fontMetrics().horizontalAdvance(percent_text)
            painter.drawText((width - percent_width) // 2, height - 10, percent_text)

            # Total text (right)
            total_text = f"Total: {self.total} GB"
            total_width = painter.fontMetrics().horizontalAdvance(total_text)
            painter.drawText(width - total_width - 10, height - 10, total_text)
        finally:
            painter.end()

class DownloadManagerUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Download Manager Clone")
        self.resize(1200, 750)
        self.setMinimumSize(800, 600)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #121212;
            }
            QLabel, QPushButton {
                color: white;
                font-size: 13px;
                font-family: 'Segoe UI';
            }
            QPushButton {
                padding: 6px 12px;
                border: none;
                background-color: transparent;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #1f1f1f;
            }
            QFrame#TopFrame {
                background-color: transparent;
            }
            QMenuBar {
                background: qlineargradient(x1:1, y1:0, x2:0, y2:0,
                    stop: 0 #00C853, stop: 1 #003d1f);
                color: white;
                font-size: 13px;
            }
            QMenuBar::item {
                padding: 6px 18px;
                background: transparent;
            }
            QMenuBar::item:selected {
                background: rgba(255,255,255,0.1);
            }
            QMenu {
                background-color: #1f1f1f;
                color: white;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #333;
            }
            QFrame#SidebarFrame {
                background-color: #121212;
                padding: 20px 10px;
            }
            QFrame#ToolbarFrame {
                background-color: #1a1a1a;
                padding: 10px 20px;
            }
            QFrame#TableFrame {
                background-color: #1e1e1e;
                padding: 10px;
            }
            QTableWidget {
                background-color: #1f1f1f;
                border: none;
                color: white;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                padding: 8px;
                border: none;
            }
        """)

        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top gradient header with menu
        top_frame = QFrame()
        top_frame.setObjectName("TopFrame")
        top_frame.setFixedHeight(35)

        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)

        menubar = QMenuBar()
        task_menu = menubar.addMenu("Task")
        task_menu.addAction("Add New Download")
        task_menu.addAction("Import List")

        file_menu = menubar.addMenu("File")
        file_menu.addAction("Open File")
        file_menu.addAction("Exit")

        downloads_menu = menubar.addMenu("Downloads")
        downloads_menu.addAction("Start All")
        downloads_menu.addAction("Pause All")

        view_menu = menubar.addMenu("View")
        view_menu.addAction("Refresh")

        help_menu = menubar.addMenu("Help")
        help_menu.addAction("About")
        help_menu.addAction("Check for Updates")

        top_layout.addWidget(menubar)
        main_layout.addWidget(top_frame)

        # Main content layout: sidebar + body
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        # Sidebar
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("SidebarFrame")
        sidebar_frame.setFixedWidth(200)

        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setSpacing(10)

        for section in [
            "All Downloads", "Compressed", "Documents", "Music",
            "Programs", "Video", "Unfinished", "Finished", "Grabber Projects", "Queues"
        ]:
            sidebar_layout.addWidget(QPushButton(section))

        sidebar_layout.addStretch()

        # Disk Usage Widget
        disk_container = QVBoxLayout()
        disk_container.setSpacing(4)

        total, used, free, percent = self.get_disk_usage("/")

        disk_label_text = f"Free: {free} GB / {total} GB"

        total, used, free, percent = self.get_disk_usage("/")

        semi_disk_widget = SemiCircularDiskWidget(used, total)
        sidebar_layout.addWidget(semi_disk_widget, alignment=Qt.AlignHCenter)

        content_layout.addWidget(sidebar_frame)

        # Body (Toolbar + Table)
        body_frame = QFrame()
        body_layout = QVBoxLayout(body_frame)
        body_layout.setSpacing(10)
        body_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("ToolbarFrame")
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setSpacing(10)

        for label in [
            "Add URL", "Resume", "Stop", "Stop All",
            "Delete", "Delete All", "Options",
            "Scheduler", "Start Queue", "Stop Queue", "Grabber", "Tell a Friend"
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2e2e2e;
                    border-radius: 4px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background-color: #388e3c;
                }
            """)
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        body_layout.addWidget(toolbar_frame)

        # Table
        table_frame = QFrame()
        table_frame.setObjectName("TableFrame")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        table = DownloadTable(5, 9)
        table.setSelectionBehavior(QTableWidget.SelectRows)   # Selects full row
        table.setSelectionMode(QTableWidget.SingleSelection)  # Only one row at a time

        table.setHorizontalHeaderLabels([
            "ID", "Name", "Progress", "Speed", "Left", "Done", "Size", "Status", "I"
        ])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)

        for row in range(5):
            for col in range(9):
                table.setItem(row, col, QTableWidgetItem(f"Sample {row}-{col}"))

        table_layout.addWidget(table)
        body_layout.addWidget(table_frame)

        content_layout.addWidget(body_frame)
        main_layout.addWidget(content_frame)

    
    def get_disk_usage(self, path="/"):
        usage = psutil.disk_usage(path)
        total_gb = usage.total // (1024**3)
        used_gb = usage.used // (1024**3)
        free_gb = total_gb - used_gb
        percent = usage.percent
        return total_gb, used_gb, free_gb, percent



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DownloadManagerUI()
    window.show()
    sys.exit(app.exec())
