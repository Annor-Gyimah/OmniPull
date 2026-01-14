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

from modules.version import __version__
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QUrl, QSize
from PySide6.QtGui import QFont, QMouseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QTextEdit, QSizePolicy, QLineEdit, QFrame, QApplication,
    QSpacerItem, QSizePolicy as QSP
)


def dark_stylesheet() -> str:
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
        background-color: rgba(28, 28, 30, 0.55);
        color: #e0e0e0;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 6px;
        padding: 6px 10px;
    }

    QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
        border: 1px solid rgba(111, 255, 176, 0.18);
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

    QFrame#changelogCard {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(10,18,22,0.95), stop:1 rgba(3,6,8,0.95));
        border-radius: 14px;
        padding: 12px;
    }
    QLabel#chip {
        background: rgba(255,255,255,0.03);
        color: rgba(170, 255, 210, 1);
        padding:6px 10px;
        border-radius:12px;
        font-size: 12px;
    }
    QTextEdit {
        color: rgba(220,255,230,0.95);
        background: transparent;
        border: none;
    }
    QPushButton#carouselNav {
        background-color: rgba(0,0,0,0.35);
        color: rgba(220,255,230,0.95);
        border-radius: 10px;
        font-weight: bold;
    }
    """


class Card(QFrame):
    def __init__(self, version: str, date: str, highlights: list[str], details: str, url: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("changelogCard")
        self.version = version
        self.date = date
        self.highlights = highlights
        self.details = details
        self.url = url
        self._build_ui()

    def _build_ui(self):
        self.setFixedSize(560, 360)
        self.setFrameShape(QFrame.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(self.version)
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet('color: #4CAF50; background: rgba(76, 175, 80, 0.1);')
        sub = QLabel(self.date)
        sub.setFont(QFont("Segoe UI", 12, QFont.Weight.Normal))
        sub.setStyleSheet("color: rgba(170, 255, 210, 0.6);")

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(sub)

        body = QVBoxLayout()
        chips = QHBoxLayout()
        chips.setSpacing(8)
        for h in self.highlights[:4]:
            chip = QLabel(h)
            chip.setObjectName("chip")
            chip.setStyleSheet("padding:6px 10px; border-radius:12px;")
            chips.addWidget(chip)
        chips.addStretch(1)

        details = QTextEdit()
        details.setReadOnly(True)
        details.setFont(QFont("Segoe UI", 14, QFont.Weight.Normal))
        details.setText(self.details)
        details.setFixedHeight(170)
        details.setFrameStyle(QFrame.NoFrame)
        details.setStyleSheet("background: transparent; border: none;")

        body.addLayout(chips)
        body.addWidget(details)

        footer = QHBoxLayout()
        footer.addStretch(1)
        more = QPushButton("More")
        more.setCursor(Qt.PointingHandCursor)
        more.setObjectName("moreBtn")
        more.clicked.connect(self.open_link)
        footer.addWidget(more)

        layout.addLayout(header)
        layout.addLayout(body)
        layout.addLayout(footer)

    def open_link(self):
        if self.url:
            QDesktopServices.openUrl(QUrl(self.url))


class CardCarousel(QWidget):
    def __init__(self, cards: list[Card], parent=None):
        super().__init__(parent)
        self.cards = cards
        self._build_ui()
        self._install_gesture()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameStyle(QFrame.NoFrame)

        self.container = QWidget()
        self.hlay = QHBoxLayout(self.container)
        self.hlay.setContentsMargins(40, 8, 40, 8)
        self.hlay.setSpacing(20)

        for c in self.cards:
            self.hlay.addWidget(c)

        spacer = QSpacerItem(20, 20, QSP.Expanding, QSP.Minimum)
        self.hlay.addItem(spacer)
        self.container.setLayout(self.hlay)
        self.scroll.setWidget(self.container)

        root.addWidget(self.scroll)

        # Navigation layout
        nav = QHBoxLayout()
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(10)  # add some space between buttons

        # Create buttons with bigger icons
        icon_size = 32  # make icons larger (default is usually 16px)

        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(QIcon(":icons/previous.png"))
        self.prev_btn.setIconSize(QSize(icon_size, icon_size))

        self.next_btn = QPushButton()
        self.next_btn.setIcon(QIcon(":icons/next.png"))
        self.next_btn.setIconSize(QSize(icon_size, icon_size))

        # self.prev_btn.setFlat(True)
        # self.next_btn.setFlat(True)


        # Common styling for both
        for b in (self.prev_btn, self.next_btn):
            b.setFixedSize(52, 52)  # slightly larger button to fit the bigger icon
            b.setCursor(Qt.PointingHandCursor)
            b.setObjectName("carouselNav")
            b.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 30); /* subtle hover highlight */
                    border-radius: 26px; /* keeps it circular */
                }
            """)

        # Connect signals
        self.prev_btn.clicked.connect(self.page_prev)
        self.next_btn.clicked.connect(self.page_next)

        nav.addStretch(1)
        nav.addWidget(self.prev_btn)
        nav.addSpacing(8)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)

        root.addLayout(nav)

        self.anim = QPropertyAnimation(self.scroll.horizontalScrollBar(), b"value")
        self.anim.setDuration(360)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

        self.current_index = 0
        self._update_nav_visibility()

    def _install_gesture(self):
        self._dragging = False
        self._start_x = 0
        self.container.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.container:
            if isinstance(event, QMouseEvent):
                if event.type() == QMouseEvent.MouseButtonPress:
                    self._dragging = True
                    self._start_x = event.globalX()
                    return True
                elif event.type() == QMouseEvent.MouseMove and self._dragging:
                    dx = self._start_x - event.globalX()
                    self.scroll.horizontalScrollBar().setValue(self.scroll.horizontalScrollBar().value() + dx)
                    self._start_x = event.globalX()
                    return True
                elif event.type() == QMouseEvent.MouseButtonRelease and self._dragging:
                    self._dragging = False
                    card_w = self.cards[0].width() + self.hlay.spacing()
                    pos = self.scroll.horizontalScrollBar().value()
                    target_index = round(pos / card_w)
                    target_index = max(0, min(target_index, len(self.cards)-1))
                    self.scroll_to_index(target_index)
                    return True
        return super().eventFilter(obj, event)

    def scroll_to_index(self, idx: int):
        self.current_index = idx
        card_w = self.cards[0].width() + self.hlay.spacing()
        target = int(idx * card_w)
        self.anim.stop()
        self.anim.setStartValue(self.scroll.horizontalScrollBar().value())
        self.anim.setEndValue(target)
        self.anim.start()
        self._update_nav_visibility()

    def page_next(self):
        self.scroll_to_index(min(self.current_index + 1, len(self.cards)-1))

    def page_prev(self):
        self.scroll_to_index(max(self.current_index - 1, 0))

    def _update_nav_visibility(self):
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.cards)-1)


class WhatsNew(QDialog):
    def __init__(self, changelog: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("What's New"))
        self.setFixedSize(800, 520)
        self.setModal(True)

        if changelog is None:
            changelog = [
                {'version': f'{__version__}',
                    'date': '2026-01-14',
                    'highlights': [
                        '🔧 Updated bundled yt-dlp to nightly (2026.1.6.233142.dev0)',
                        '🛡️ Change download page to use a convenient simpler add download popup',
                        '🔧 Updated deno version to 2.6.4',
                        '🔁 Improved functionalities and logic',
                    ],
                    'details': (
                        "This long awaited release updates the bundled yt-dlp to the latest nightly (2026.1.6.233142.dev0) "
                        "and deno a js runtime engine to 2.6.4"
                        " The download page has changed from being a stacked widget to a simple popup."
                        " This is to ensure it follows the general download logic and UI/UX flow. Same design though. It has however introduced a slight delay of about 1.5 secs in the loading of the download table"
                        "but will be fixed in the subsequent updates. Yt-dlp.exe has also been updated to the latest which of this time was version 2025.12.08"
                        " There have been an improvement in overall download logic and the stuatus quo. Annoying popups from ffmpeg when downloading youtube videos have been stopped."
                    ),
                    'url': 'https://github.com/Annor-Gyimah/OmniPull/releases/tag/v.2.1.1'
                },
                {'version': f'2.0.8',
                    'date': '2025-11-27',
                    'highlights': [
                        '🔧 Updated bundled yt-dlp to nightly (2025.11.24.232953.dev0)',
                        '🛡️ Fixed startup crash caused by invalid merge_output_format',
                        '✅ Safer config validation with sensible fallbacks (merge_output_format -> mp4)',
                        '🔁 Improved yt-dlp updater logic (safe replace / schedule update when exe is in-use)',
                        '⚙️ Minor stability and startup performance improvements'
                    ],
                    'details': (
                        "This release updates the bundled yt-dlp to the latest nightly (2025.11.24.232953.dev0) "
                        "and fixes a startup crash caused by an invalid or missing `merge_output_format` setting. "
                        "The crash occurred when the app attempted to use the config value directly without validation, "
                        "causing an unhandled exception during startup. The app now validates `merge_output_format`, "
                        "coerces invalid values to a safe default (mp4), and logs a non-blocking warning instead of raising. "
                        "The yt-dlp updater has also been hardened: new binaries are downloaded to a temporary file, "
                        "a safe replacement is attempted, and updates are scheduled (via `.exe.new`) if the file is in use. "
                        "Additional logging and input validation reduce startup latency and improve overall stability."
                    ),
                    'url': 'https://github.com/Annor-Gyimah/OmniPull/releases/tag/v.2.0.8'
                },
                {'version': f'2.0.7',
                'date': '2025-11-14' ,
                'highlights': [
                    '🛠️ Bug Fixes & Improvements',
                    '🚀 Performance Enhancements',
                    '🌐 UI/UX Tweaks',
                    '🆕 Deno Added and Enabled by Default'
                ],
                'details': 'We are excited to announce the release of OmniPull version 2.0.7! This update focuses on enhancing stability, performance, and user experience. \n\n'
                            '🛠️ **Bug Fixes & Improvements:** We have addressed several bugs reported by our users, ensuring a smoother and more reliable experience. \n\n'
                            '🚀 **Performance Enhancements:** Significant optimizations have been made to improve download speeds and overall application responsiveness. \n\n'
                            '🌐 **UI/UX Tweaks:** We have refined the user interface to make it more intuitive and visually appealing, enhancing your interaction with the app. \n\n'
                            '🆕 **Deno Added and Enabled by Default:** Deno, a secure runtime for JavaScript and TypeScript, has been integrated into OmniPull and is now enabled by default. This addition enhances the app\'s capabilities and performance when handling JavaScript-based content as required by YT-DLP. \n User\'s might have to download and install it system wide or use the settings to point to path. \n\n',
                'url': 'https://github.com/Annor-Gyimah/OmniPull/releases/tag/v.2.0.7'
                
                },
                {'version': f'2.0.3', 
                'date': '2025-10-25', 
                'highlights': [
                    '🧩 Custom yt-dlp.exe \n Support',
                    '📂 Cookies.txt \n Enabled',
                    '🎬 Format Selection',
                    '🌏 Hindi Added'
                ],
                'details': '🎉 Another massive OmniPull update is here — packed with new features, flexibility, and smoother usability! \n\n'
                            '🧩 **Custom YT-DLP Executable:** You can now specify and use your own `yt-dlp` binary instead of the built-in library, giving you complete control over updates, features, and performance tweaks.\n\n'
                            '📂 **Full Cookies.txt Support:** OmniPull now supports importing and using `cookies.txt`, allowing seamless downloads from sites that require authentication or custom login sessions.\n\n'
                            '🎬 **Choose Your Video Format:** Prefer `.mp4`, `.mkv`, or `.avi`? You can now select your desired output format for YouTube videos and enjoy personalized downloads.\n\n'
                            '🧠 **New YT-DLP Log Level:** Introduces a dedicated log level for `yt-dlp.exe` logs and stderr messages to keep your console cleaner and more organized.\n\n'
                            '🆕 **“What’s New” Toolbar Button:** Stay informed about every release! Instantly view highlights, features, and fixes directly within the app.\n\n'
                            '✅ **Mark Complete for Tutorial Overlay:** Added a *Mark Complete* button to close the tutorial overlay once finished — no more blocked navigation.\n\n'
                            '⬇️ **YT-DLP Binary Updater:** You can now download and update your `yt-dlp` executable directly within OmniPull — fast, easy, and automatic. 🔄\n\n'
                            '🌏 **Hindi Language Added:** OmniPull now supports Hindi 🇮🇳 — expanding accessibility and welcoming more users worldwide!\n\n'
                            'This release continues our commitment to flexibility, usability, and performance — giving you more control than ever over how you download, manage, and enjoy content. 🚀', 
                'url': 'https://github.com/Annor-Gyimah/OmniPull/releases/tag/v.2.0.3'},
                {'version': f'2.0.0',
                 'date': '2025-09-12', 
                 'highlights': ['Complete UI Redesign', '50% Faster Performance', 'Better Resource Management'], 
                 'details': 'A major upgrade has arrived 🚀, rebuilt completely from the ground up to deliver faster speed, stronger stability, and a sleek modern interface. 🆕 The update introduces exciting new features, including a complete UI redesign for a cleaner look, brand-new download protocols, and even a built-in file converter for added convenience. 🐞 All previously reported issues have been resolved, such as playlist handling freezes, resume failures, and inaccurate progress reporting in certain video and audio streams. ⚡ On top of that, the architecture has been fully rewritten, resulting in performance that is up to 50% faster. Users can also expect better resource management, ensuring smoother multitasking across devices. Finally, enhanced security features provide greater protection, making this upgrade the most reliable and efficient version yet.', 
                 'url': 'https://github.com/Annor-Gyimah/OmniPull/releases/tag/v.2.0.0'}
                # {'version': '1.9.0',
                #  'date': '2025-05-30', 
                #  'highlights': ['yt-dlp integration', 'Progress UI improvements'], 
                #  'details': 'Introduced yt-dlp.', 
                #  'url': 'https://github.com/yourrepo/releases/tag/v1.9.0'}
            ]

        self.changelog = changelog
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("What's new")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        subtitle = QLabel("Swipe to browse recent releases")
        subtitle.setStyleSheet("color: rgba(170, 255, 210, 0.6);")

        head = QVBoxLayout()
        head.addWidget(title)
        head.addWidget(subtitle)

        root.addLayout(head)

        card_objs = [Card(e['version'], e['date'], e['highlights'], e['details'], e.get('url', "")) for e in self.changelog]
        self.carousel = CardCarousel(card_objs)
        root.addWidget(self.carousel)

        foot = QHBoxLayout()
        foot.addStretch(1)
        close = QPushButton("Close")
        close.setFixedHeight(40)
        close.clicked.connect(self.accept)
        foot.addWidget(close)
        root.addLayout(foot)

        self.setStyleSheet(dark_stylesheet())

    def exec_and_center(self):
        if self.parent():
            geom = self.parent().frameGeometry()
            center = geom.center()
            self.move(center - self.rect().center())
        return self.exec()

