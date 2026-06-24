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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout,
)

from modules.helpers import get_file_icon
from modules.utils import log, size_format


class FilePropertiesDialog(QDialog):
    """
    UI Dialog for inspecting granular download metadata.

    Displays technical properties of a DownloadItem including file system
    location, network protocol, engine-specific status, and icon previews.
    Supports dynamic localization through a shared translation dictionary.
    """

    def __init__(self, d, parent=None, language="English"):
        super().__init__(parent)
        from modules.helpers import FILE_PROPERTIES_TRANSLATIONS

        self.language = language
        self.ctx = "PROPERTIES-UI"

        log(f"Initializing properties inspector for item: {d.name}",
            log_level=1, context=self.ctx)

        self.setWindowTitle("File Properties")
        self.setMinimumWidth(520)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(16)

        # ── Visual Identification (Icon) ──────────────────────────────────────
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        ext = getattr(d, "ext", "")

        pixmap = get_file_icon(f".{ext}")
        icon_label.setPixmap(pixmap.scaled(100, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        top_layout.addWidget(icon_label)

        # ── Metadata Grid ─────────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        def add_row(row, label_key, value):
            translated_label = FILE_PROPERTIES_TRANSLATIONS.get(label_key, {}).get(self.language, label_key)
            lbl = QLabel(translated_label)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
            lbl.setStyleSheet("font-weight: bold;")

            val = QLabel(str(value) if value else "-")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            val.setWordWrap(True)

            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)

        row = 0
        add_row(row, "Name:", d.name); row += 1
        add_row(row, "Folder:", d.folder); row += 1
        add_row(row, "Download engine:", d.engine); row += 1
        add_row(row, "Progress:", f"{d._progress}%"); row += 1
        add_row(row, "Downloaded:", size_format(d.downloaded)); row += 1
        add_row(row, "Total size:", size_format(d.total_size)); row += 1
        add_row(row, "Status:", d.status); row += 1

        resumable_text = (FILE_PROPERTIES_TRANSLATIONS["Yes"][self.language] if d.resumable
                          else FILE_PROPERTIES_TRANSLATIONS["No"][self.language])
        add_row(row, "Resumable:", resumable_text); row += 1

        add_row(row, "Type:", d.type); row += 1
        add_row(row, "Protocol:", d.protocol); row += 1

        webpage_url = d.original_url if d.engine in {"aria2", "aria2c"} else d.url
        add_row(row, "Webpage URL:", webpage_url)

        top_layout.addLayout(grid)
        main_layout.addLayout(top_layout)

        # ── UI Elements ───────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(divider)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton(FILE_PROPERTIES_TRANSLATIONS["Close"][self.language])
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        main_layout.addLayout(btn_layout)

    def accept(self):
        """Finalizes the dialog session and logs the closure."""
        log("Closing properties inspector", log_level=1, context=self.ctx)
        super().accept()
