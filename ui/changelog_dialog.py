
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

from modules.config import __version__

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QTextEdit
)

class WhatsNewDialog(QDialog):
    """
    'What's new' dialog with a simple carousel of release cards.

    Each card shows:
        - Version (e.g. v1.2.0)
        - Release date
        - Highlights (short bullet/summary)
        - Details (multi-line text area)
    Navigation:
        - Previous / Next buttons
        - "Current release" vs "Past release" label
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("What's new")
        self.setObjectName("WhatsNewDialog")
        self.resize(520, 420)
        self.setMinimumSize(440, 360)

        self._releases = []   # list of dicts
        self._current_index = 0

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header row
        header_row = QHBoxLayout()
        header_title = QLabel("What’s new")
        header_title.setObjectName("WhatsNewTitleLabel")
        header_row.addWidget(header_title)
        header_row.addStretch()

        self.position_label = QLabel("")  # e.g. "Current release (1 of 3)"
        self.position_label.setObjectName("WhatsNewPositionLabel")
        header_row.addWidget(self.position_label)

        main_layout.addLayout(header_row)

        # Card frame
        self.card_frame = QFrame()
        self.card_frame.setObjectName("WhatsNewCard")
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        # Version / date row
        row_top = QHBoxLayout()
        self.version_label = QLabel("Version: -")
        self.version_label.setObjectName("WhatsNewVersionLabel")
        row_top.addWidget(self.version_label)

        row_top.addStretch()

        self.date_label = QLabel("Date: -")
        self.date_label.setObjectName("WhatsNewDateLabel")
        row_top.addWidget(self.date_label)

        card_layout.addLayout(row_top)

        # Highlights
        highlights_title = QLabel("Highlights")
        highlights_title.setObjectName("WhatsNewHighlightsTitle")
        card_layout.addWidget(highlights_title)

        self.highlights_label = QLabel("-")
        self.highlights_label.setObjectName("WhatsNewHighlightsLabel")
        self.highlights_label.setWordWrap(True)
        card_layout.addWidget(self.highlights_label)

        # Details
        details_title = QLabel("Details")
        details_title.setObjectName("WhatsNewDetailsTitle")
        card_layout.addWidget(details_title)

        self.details_text = QTextEdit()
        self.details_text.setObjectName("WhatsNewDetailsText")
        self.details_text.setReadOnly(True)
        self.details_text.setMinimumHeight(160)
        card_layout.addWidget(self.details_text)

        main_layout.addWidget(self.card_frame, 1)

        # Carousel controls
        nav_row = QHBoxLayout()
        self.btn_prev = QPushButton("Previous")
        self.btn_next = QPushButton("Next")
        nav_row.addWidget(self.btn_prev)
        nav_row.addWidget(self.btn_next)
        nav_row.addStretch()

        self.btn_close = QPushButton("Close")
        nav_row.addWidget(self.btn_close)

        main_layout.addLayout(nav_row)

        # Connections
        self.btn_prev.clicked.connect(self._go_prev)
        self.btn_next.clicked.connect(self._go_next)
        self.btn_close.clicked.connect(self.accept)

        # Example placeholder data (you can remove this and call set_releases yourself)
        self.set_releases([
            {
                "version": f'{__version__}',
                'date': '2025-11-27',
                "highlights": "🔧 Updated bundled yt-dlp to nightly, 🛡️ Fixed startup crash, and ⚙️ Minor stability and startup",
                "details": (
                    "-🎉 This release updates the bundled yt-dlp to the latest nightly (2025.11.24.232953.dev0).\n\n"
                    "This fixes a startup crash caused by an invalid or missing `merge_output_format` setting.\n\n"
                    "The crash occurred when the app attempted to use the config value directly without validation, causing an unhandled exception during startup. The app now validates `merge_output_format`,"
                    "coerces invalid values to a safe default (mp4), and logs a non-blocking warning instead of raising.\n\n"
                    "- Additional logging and input validation reduce startup latency and improve overall stability."
                ),
            },
            {
                'version': '2.0.3',
                "date": "2025-10-25",
                "highlights": "🧩 Custom yt-dlp.exe, Support 📂 Cookies.txt 🎬 Format Selection and 🌏 Hindi Added",
                "details": (
                    "-🎉 Another massive OmniPull update is here — packed with new features, flexibility, and smoother usability! \n\n"
                    "-🧩 **Custom YT-DLP Executable:** You can now specify and use your own `yt-dlp` binary instead of the built-in library, giving you complete control over updates, features, and performance tweaks.\n\n"
                    "-📂 **Full Cookies.txt Support:** OmniPull now supports importing and using `cookies.txt`, allowing seamless downloads from sites that require authentication or custom login sessions.\n\n"
                    "-🎬 **Choose Your Video Format:** Prefer `.mp4`, `.mkv`, or `.avi`? You can now select your desired output format for YouTube videos and enjoy personalized downloads.\n\n"
                    "-🧠 **New YT-DLP Log Level:** Introduces a dedicated log level for `yt-dlp.exe` logs and stderr messages to keep your console cleaner and more organized.\n\n"
                    "-🆕 **“What’s New” Toolbar Button:** Stay informed about every release! Instantly view highlights, features, and fixes directly within the app.\n\n"
                    "-✅ **Mark Complete for Tutorial Overlay:** Added a *Mark Complete* button to close the tutorial overlay once finished — no more blocked navigation.\n\n"
                    "-⬇️ **YT-DLP Binary Updater:** You can now download and update your `yt-dlp` executable directly within OmniPull — fast, easy, and automatic. 🔄\n\n"
                    "-🌏 **Hindi Language Added:** OmniPull now supports Hindi 🇮🇳 — expanding accessibility and welcoming more users worldwide!\n\n"
                    "-This release continues our commitment to flexibility, usability, and performance — giving you more control than ever over how you download, manage, and enjoy content. 🚀"
                ),
            },
            {
                "version": "2.0.0",
                'date': '2025-09-12', 
                "highlights": "Complete UI Redesign, 50% Faster Performance, and Better Resource Management",
                "details": (
                    "-  A major upgrade has arrived 🚀, rebuilt completely from the ground up to deliver faster speed, stronger stability, and a sleek modern interface.\n\n"
                    "- 🆕 The update introduces exciting new features, including a complete UI redesign for a cleaner look, brand-new download protocols, and even a built-in file converter for added convenience.\n\n"
                    "- 🐞 All previously reported issues have been resolved, such as playlist handling freezes, resume failures, and inaccurate progress reporting in certain video and audio streams.\n\n"
                    "- ⚡ On top of that, the architecture has been fully rewritten, resulting in performance that is up to 50% faster. Users can also expect better resource management, ensuring smoother multitasking across devices.\n\n"
                    "- Finally, enhanced security features provide greater protection, making this upgrade the most reliable and efficient version yet..\n\n"
                ),
            },
        ])

    # ===== PUBLIC API =====
    def set_releases(self, releases: list[dict]):
        """
        releases: list of dicts with keys:
            - version (str)
            - date (str)
            - highlights (str)
            - details (str)
        """
        self._releases = releases[:] if releases else []
        self._current_index = 0
        self._update_ui()

    # ===== INTERNAL HELPERS =====
    def _update_ui(self):
        if not self._releases:
            self.version_label.setText("Version: -")
            self.date_label.setText("Date: -")
            self.highlights_label.setText("No release notes available.")
            self.details_text.setPlainText("")
            self.position_label.setText("No releases")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        idx = max(0, min(self._current_index, len(self._releases) - 1))
        self._current_index = idx
        rel = self._releases[idx]

        version = rel.get("version", "-")
        date = rel.get("date", "-")
        highlights = rel.get("highlights", "-")
        details = rel.get("details", "")

        self.version_label.setText(f"Version: {version}")
        self.date_label.setText(f"Date: {date}")
        self.highlights_label.setText(highlights)
        self.details_text.setPlainText(details)

        total = len(self._releases)
        if idx == 0:
            pos_text = f"Current release (1 of {total})"
        else:
            pos_text = f"Past release ({idx + 1} of {total})"
        self.position_label.setText(pos_text)

        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setEnabled(idx < total - 1)

    def _go_prev(self):
        if self._current_index > 0:
            self._current_index -= 1
            self._update_ui()

    def _go_next(self):
        if self._current_index < len(self._releases) - 1:
            self._current_index += 1
            self._update_ui()
