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



from ui.styles import get_stylesheet
from modules.config import current_theme

from PySide6.QtCore import  Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QListWidget, QVBoxLayout, QWidget, QLabel, 
    QStyledItemDelegate, QStyle, QApplication, QToolBar, QStackedWidget, QSplitter,
    QLineEdit
)

class HelpPage(QWidget):
    def __init__(self, title: str, content: str):
        super().__init__()
        self.search_text = f"{title} {content}".lower()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title_label = QLabel(title)
        title_label.setObjectName("HelpTitle")

        body = QLabel(content)
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        body.setObjectName("HelpBody")

        layout.addWidget(title_label)
        layout.addWidget(body)
        layout.addStretch()


class HelpWelcomePage(HelpPage):
    def __init__(self):
        super().__init__(
            "Welcome to OmniPull",
            """
            <p>
            OmniPull is a comprehensive download manager designed to unify
            multiple download engines into a single, powerful, and responsive interface.
            </p>

            <p>
            The application supports video downloads using yt-dlp, traditional
            HTTP and HTTPS file downloads, and torrent-based downloads,
            all while maintaining advanced queue control and scheduling.
            </p>

            <p>
            OmniPull is built for both casual users and power users,
            offering simple one-click downloads alongside a fully
            interactive terminal for advanced yt-dlp commands.
            </p>
            """
        )


class HelpDownloadsPage(HelpPage):
    def __init__(self):
        super().__init__(
            "Managing Downloads",
            """
            <p>
            OmniPull allows you to add downloads individually or in batches.
            Each download is tracked in real time with detailed progress
            indicators, speed monitoring, and status updates.
            </p>

            <p>
            Downloads can be paused, resumed, cancelled, queued,
            or scheduled depending on your preferences.
            </p>

            <p>
            Automatic categorization places files into appropriate folders
            such as Video, Music, Documents, or Archives, helping you
            stay organized without manual sorting.
            </p>
            """
        )

class HelpVideoPage(HelpPage):
    def __init__(self):
        super().__init__(
            "Video Downloads",
            """
            <p>
            OmniPull integrates yt-dlp to provide advanced video downloading
            capabilities for platforms such as YouTube and many others.
            </p>

            <p>
            You can select video resolutions, formats, audio-only downloads,
            subtitles, and metadata options directly from the interface.
            </p>

            <p>
            When merging audio and video streams fails automatically,
            OmniPull provides re-merging tools to fix the issue without
            restarting the download.
            </p>
            """
        )


class HelpTerminalPage(HelpPage):
    def __init__(self):
        super().__init__(
            "Terminal Usage",
            """
            <p>
            The built-in terminal allows advanced users to execute yt-dlp
            commands directly inside OmniPull without opening an external shell.
            </p>

            <p>
            Commands entered in the terminal are executed in the background
            and their output is streamed live into the terminal panel.
            </p>

            <p>
            Command history, auto-completion, and interruption controls
            make the terminal both powerful and safe to use alongside
            active downloads.
            </p>
            """
        )

class HelpSchedulePage(HelpPage):
    def __init__(self):
        super().__init__(
            "Scheduling & Queues",
            """
            <p>
            OmniPull supports advanced scheduling, allowing downloads
            to start at specific times or after other downloads complete.
            </p>

            <p>
            Queue management ensures that system resources are used efficiently
            by limiting concurrent downloads while keeping others pending.
            </p>

            <p>
            This system is ideal for large batch downloads or managing
            bandwidth usage during peak hours.
            </p>
            """
        )

class HelpSettingsPage(HelpPage):
    def __init__(self):
        super().__init__(
            "Settings & Customization",
            """
            <p>
            OmniPull provides extensive customization options,
            including theme selection, download folders,
            file naming conventions, and engine preferences.
            </p>

            <p>
            Both dark and light themes are supported and can be
            synchronized with the system appearance.
            </p>

            <p>
            Advanced users can configure download behavior,
            logging levels, and update preferences from the settings panel.
            </p>
            """
        )


class NoFocusDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if option.state & QStyle.State_HasFocus:
            option.state = option.state ^ QStyle.State_HasFocus
        super().paint(painter, option, index)

class HelpWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("OmniPull Help")
        self.resize(960, 620)
        self.setObjectName("HelpWindow")

        self._history = []
        self._history_index = -1

        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)

        self.btn_back = QAction("◀ Back", self)
        self.btn_forward = QAction("Forward ▶", self)
        self.btn_home = QAction("Home", self)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search help…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMaximumWidth(220)

        


        toolbar.addAction(self.btn_back)
        toolbar.addAction(self.btn_forward)
        toolbar.addSeparator()
        toolbar.addAction(self.btn_home)
        toolbar.addSeparator()
        toolbar.addWidget(self.search_edit)

        self.addToolBar(toolbar)

        # Layout
        splitter = QSplitter()

        self.nav = QListWidget()
        self.nav.setItemDelegate(NoFocusDelegate())
        self.nav.setFixedWidth(220)
        self.nav.addItems([
            "Welcome",
            "Managing Downloads",
            "Video Downloads",
            "Terminal Usage",
            "Scheduling & Queues",
            "Settings & Customization"
        ])

        self.pages = QStackedWidget()
        self.pages.addWidget(HelpWelcomePage())
        self.pages.addWidget(HelpDownloadsPage())
        self.pages.addWidget(HelpVideoPage())
        self.pages.addWidget(HelpTerminalPage())
        self.pages.addWidget(HelpSchedulePage())
        self.pages.addWidget(HelpSettingsPage())

        splitter.addWidget(self.nav)
        splitter.addWidget(self.pages)
        self.setCentralWidget(splitter)

        # Signals
        self.nav.currentRowChanged.connect(lambda i: self._set_page(i, record_history=True))

        self.btn_back.triggered.connect(self.go_back)
        self.btn_forward.triggered.connect(self.go_forward)
        self.btn_home.triggered.connect(lambda: self._navigate_to(0))
        self.search_edit.textChanged.connect(self._on_search)


        self.nav.setCurrentRow(0)
        self.current_theme = current_theme

    def _navigate_to(self, index):
        if index < 0:
            return
        self.pages.setCurrentIndex(index)

        if self._history_index == -1 or self._history[self._history_index] != index:
            self._history = self._history[:self._history_index + 1]
            self._history.append(index)
            self._history_index += 1

    def go_back(self):
        if self._history_index > 0:
            self._history_index -= 1
            self._set_page(self._history[self._history_index], record_history=False)

    def go_forward(self):
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._set_page(self._history[self._history_index], record_history=False)


    def _apply_theme(self):
        """Apply the stylesheet based on current theme."""
        
        qss = get_stylesheet(self.current_theme)
        try:
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss)
        except Exception:
            # fallback to per-window stylesheet
            try:
                self.setStyleSheet(qss)
            except Exception:
                pass
    
    def _set_page(self, index: int, record_history=True):
        if index < 0 or index >= self.pages.count():
            return

        # Update page
        self.pages.setCurrentIndex(index)

        # Sync navigation list WITHOUT re-triggering history
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(index)
        self.nav.blockSignals(False)

        if record_history:
            if self._history_index == -1 or self._history[self._history_index] != index:
                self._history = self._history[:self._history_index + 1]
                self._history.append(index)
                self._history_index += 1
    
    def _on_search(self, text: str):
        text = text.lower().strip()

        if not text:
            return

        for i in range(self.pages.count()):
            page = self.pages.widget(i)
            if hasattr(page, "search_text") and text in page.search_text:
                self._set_page(i)
                return




