from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFont, QAction
from PySide6.QtCore import Qt, Signal
import os, sys
from modules.utils import notify
from modules.config import APP_NAME, APP_VERSION

class TrayIconManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.tray_icon = None
        self.init_tray_icon()

    def init_tray_icon(self):
        

        self.tray_icon = QSystemTrayIcon(QIcon(':/icons/logo1.png'), self.main_window)
        tray_menu = QMenu()
        
        restore_action = QAction(QIcon(':/icons/window.svg'), "Restore", self.main_window)
        restore_action.triggered.connect(self.main_window.showNormal)
        
    
        quit_action = QAction(QIcon(':/icons/exit.svg'), "Quit", self.main_window)
        quit_action.triggered.connect(self.quit_application)
        
        tray_menu.addAction(restore_action)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip(f"{APP_NAME} {APP_VERSION}")
        self.tray_icon.show()

    

    def quit_application(self):
        
        self.hide()
        self.main_window.close()

    def handle_window_close(self):
       
        self.main_window.hide()
        self.show_running_message()

    def show_ffmpeg_warning(self):
        if not self.main_window.ffmpeg_found:
            self.tray_icon.showMessage(
                "FFmpeg missing",
                "Please download it from the official website.",
                QSystemTrayIcon.Critical,
                3000
            )

    def show_running_message(self):
        # notify("Application is running in the tray", title=f"{APP_NAME} {APP_VERSION}", timeout=1)
        self.tray_icon.showMessage(
            f"{APP_NAME} {APP_VERSION}",
            "Application is running in the tray",
            QSystemTrayIcon.Information,
            2000
        )

    def show_download_completed_message(self):
        self.tray_icon.showMessage(
            f"{APP_NAME} {APP_VERSION}",
            "Download Completed",
            QSystemTrayIcon.Information,
            3000
        )

    def show_download_error_message(self):
        self.tray_icon.showMessage(
            f"{APP_NAME} {APP_VERSION}",
            "Download Error Occurred",
            QSystemTrayIcon.Critical,
            3000
        )

    def show_download_cancelled_message(self):
        self.tray_icon.showMessage(
            f"{APP_NAME} {APP_VERSION}",
            "Download Cancelled",
            QSystemTrayIcon.Warning,
            3000
        )

    def show_playlist_indexing_message(self):
        self.tray_icon.showMessage(
            f"{APP_NAME} {APP_VERSION}",
            "Playlist indexing, please wait...",
            QSystemTrayIcon.Information,
            5000
        )

    def show_error_message(self, text):
        self.tray_icon.showMessage(
            f"{APP_NAME} {APP_VERSION} - Error",
            text.split("\n")[0],
            QSystemTrayIcon.Critical,
            5000
        )

    def hide(self):
        if self.tray_icon:
            self.tray_icon.hide()

    def show_message(self, title, message, icon=QSystemTrayIcon.Information):
        self.tray_icon.showMessage(
            f"{APP_NAME} {APP_VERSION}",
            message,
            icon,
            3000
        )

    def show_error(self, message):
        self.tray_icon.showMessage(
            f"{APP_NAME} {APP_VERSION} - Error",
            message,
            QSystemTrayIcon.Critical,
            3000
        ) 