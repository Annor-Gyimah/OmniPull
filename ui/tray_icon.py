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


import platform
from modules.utils import notify
from modules.config import APP_NAME, APP_VERSION

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

class TrayIconManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.tray_icon = None
        self.tray_menu = None  # Keep reference to prevent garbage collection
        self.init_tray_icon()

    def init_tray_icon(self):


        self.tray_icon = QSystemTrayIcon(QIcon(':/icons/omnipull.ico'), self.main_window)

        # Create menu with explicit parent to prevent deletion issues on macOS
        self.tray_menu = QMenu(self.main_window)

        restore_action = QAction(QIcon(':/icons/window.svg'), "Restore", self.main_window)
        restore_action.triggered.connect(self.restore_window)


        quit_action = QAction(QIcon(':/icons/exit.svg'), "Quit", self.main_window)
        quit_action.triggered.connect(self.quit_application)

        self.tray_menu.addAction(restore_action)
        self.tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.setToolTip(f"{APP_NAME} {APP_VERSION}")

        # Connect double-click to restore window
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        """Handle tray icon activation (click, double-click, etc.)"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_window()

    def restore_window(self):
        """Restore window from tray (cross-platform compatible)"""
        # macOS-specific fix: Need to properly restore window state
        if platform.system() == "Darwin":
            # On macOS, we need to:
            # 1. Show the window first
            # 2. Set window state to normal (not minimized)
            # 3. Raise it to front
            # 4. Activate it to get focus
            self.main_window.show()
            self.main_window.setWindowState(
                self.main_window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive
            )
            self.main_window.raise_()
            self.main_window.activateWindow()
        else:
            # Windows/Linux: showNormal() works fine
            self.main_window.showNormal()
            self.main_window.raise_()
            self.main_window.activateWindow()

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
        notify("Application is running in the tray", title=f"{APP_NAME} {APP_VERSION}", timeout=1)
        

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

    def show_browser_download_intercepted(self, filename):
        """Show notification when browser download is intercepted"""
        self.tray_icon.showMessage(
            "Download Intercepted",
            f"Browser download intercepted:\n{filename}\n\nAdd Download dialog opening...",
            QSystemTrayIcon.Information,
            4000
        )