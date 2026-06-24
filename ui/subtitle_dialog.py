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

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QVBoxLayout,
)

from modules.utils import log


class SubtitleFailedDialog(QDialog):
    """
    User-intervention dialog for terminal subtitle download failures.

    Triggered when the automated subtitle fallback mechanism exhausts all
    retry attempts (typically due to HTTP 429 rate-limiting). It provides
    the user with the raw extraction URL to facilitate manual recovery
    via an external web browser or clipboard transfer.
    """

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.ctx = "SUB-FALLBACK-UI"

        self.subtitle_url = payload.get("url", "")
        lang  = payload.get("lang", "?")
        title = payload.get("title", "Unknown")

        log(f"Displaying manual recovery options for {lang} subtitle: {title}",
            log_level=1, context=self.ctx)

        self.setWindowTitle(self.tr("Subtitle Download Failed"))
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Header ───────────────────────────────────────────────────────────────
        header = QLabel(self.tr("⚠  Subtitle Could Not Be Downloaded"))
        header.setStyleSheet("font-size:14px; font-weight:700;")
        layout.addWidget(header)

        # ── Info text ─────────────────────────────────────────────────────────────
        info = QLabel(
            self.tr(
                f"YouTube returned <b>HTTP 429 (Too Many Requests)</b> for the "
                f"<b>{lang}</b> subtitle of:<br>"
                f"<i>{title}</i><br><br>"
                "The subtitle URL is still valid. You can open it in your browser "
                "to view or save it manually."
            )
        )
        info.setWordWrap(True)
        info.setOpenExternalLinks(False)
        layout.addWidget(info)

        # ── URL Display ──────────────────────────────────────────────────────────
        url_box = QTextEdit()
        url_box.setReadOnly(True)
        url_box.setPlainText(self.subtitle_url)
        url_box.setFixedHeight(70)
        url_box.setStyleSheet("font-size:10px; font-family: monospace;")
        layout.addWidget(url_box)

        # ── Action Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        copy_btn = QPushButton(self.tr("Copy Link"))
        copy_btn.setToolTip(self.tr("Copy subtitle URL to clipboard"))
        copy_btn.clicked.connect(self._copy_link)
        btn_row.addWidget(copy_btn)

        open_btn = QPushButton(self.tr("Open in Browser"))
        open_btn.setDefault(True)
        open_btn.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        open_btn.setToolTip(self.tr("Open the subtitle URL in your default browser"))
        open_btn.clicked.connect(self._open_browser)
        btn_row.addWidget(open_btn)

        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _copy_link(self):
        """Transfers the subtitle resource URL to the system clipboard."""
        QApplication.clipboard().setText(self.subtitle_url)
        log("Subtitle resource URL transferred to system clipboard",
            log_level=1, context=self.ctx)

    def _open_browser(self):
        """Invokes the default system browser to access the subtitle stream."""
        log(f"Delegating subtitle recovery to external browser: {self.subtitle_url}",
            log_level=1, context=self.ctx)
        QDesktopServices.openUrl(QUrl(self.subtitle_url))
        self.accept()
