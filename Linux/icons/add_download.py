
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from youtube_thread import YouTubeThread


class AddDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Download")
        self.setFixedSize(600, 500)
        self.manager = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # URL input
        url_layout = QHBoxLayout()
        self.link_input = QLineEdit()
        self.retry_btn = QPushButton("Retry")
        url_layout.addWidget(QLabel("URL:"))
        url_layout.addWidget(self.link_input)
        url_layout.addWidget(self.retry_btn)
        layout.addLayout(url_layout)

        # Folder input
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.open_btn = QPushButton("📂")
        folder_layout.addWidget(QLabel("Save to:"))
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.open_btn)
        layout.addLayout(folder_layout)

        # Filename input
        filename_layout = QHBoxLayout()
        self.filename_input = QLineEdit()
        filename_layout.addWidget(QLabel("Filename:"))
        filename_layout.addWidget(self.filename_input)
        layout.addLayout(filename_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Thumbnail + ComboBoxes
        thumb_row = QHBoxLayout()
        self.thumbnail_label = QLabel("Thumbnail")
        self.thumbnail_label.setFixedSize(100, 80)
        self.thumbnail_label.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;")
        thumb_row.addWidget(self.thumbnail_label)

        combo_col = QVBoxLayout()
        self.quality_combo = QComboBox()
        self.format_combo = QComboBox()
        combo_col.addWidget(self.quality_combo)
        combo_col.addWidget(self.format_combo)
        thumb_row.addLayout(combo_col)
        layout.addLayout(thumb_row)

        # Metadata rows
        meta1 = QHBoxLayout()
        self.size_value = QLabel("-")
        self.type_value = QLabel("-")
        meta1.addWidget(QLabel("Size:"))
        meta1.addWidget(self.size_value)
        meta1.addSpacing(40)
        meta1.addWidget(QLabel("Type:"))
        meta1.addWidget(self.type_value)
        layout.addLayout(meta1)

        meta2 = QHBoxLayout()
        self.protocol_value = QLabel("-")
        self.resumable_value = QLabel("-")
        meta2.addWidget(QLabel("Protocol:"))
        meta2.addWidget(self.protocol_value)
        meta2.addSpacing(40)
        meta2.addWidget(QLabel("Resumable:"))
        meta2.addWidget(self.resumable_value)
        layout.addLayout(meta2)

        # Action buttons
        btns = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.download_btn = QPushButton("Download")
        self.cancel_btn = QPushButton("Cancel")
        btns.addStretch()
        btns.addWidget(self.add_btn)
        btns.addWidget(self.download_btn)
        btns.addWidget(self.cancel_btn)
        layout.addLayout(btns)

        self.retry_btn.clicked.connect(self.start_info_thread)
        self.link_input.textChanged.connect(self.start_info_thread)
        self.cancel_btn.clicked.connect(self.reject)

    def start_info_thread(self):
        url = self.link_input.text().strip()
        if not url:
            return

        self.yt_thread = YouTubeThread(url)
        self.yt_thread.progress_signal.connect(self.progress_bar.setValue)
        self.yt_thread.result_signal.connect(self.handle_video_info)
        self.yt_thread.error_signal.connect(self.handle_video_error)
        self.yt_thread.start()

    def handle_video_info(self, video):
        self.filename_input.setText(video.name)
        self.size_value.setText(getattr(video, 'size_text', "Unknown"))
        self.type_value.setText(getattr(video, 'type', "Unknown"))
        self.protocol_value.setText(getattr(video, 'protocol', "HTTP"))
        self.resumable_value.setText("Yes" if getattr(video, 'resumable', False) else "No")

        self.quality_combo.clear()
        self.quality_combo.addItems(getattr(video, 'stream_names', []))

        self.format_combo.clear()
        self.format_combo.addItems(getattr(video, 'formats', []))

        if hasattr(video, 'thumbnail_url'):
            self.load_thumbnail(video.thumbnail_url)

    def handle_video_error(self, message):
        QMessageBox.critical(self, "Error", f"Failed to retrieve video info:\n{message}")

    def load_thumbnail(self, url):
        self.manager = QNetworkAccessManager(self)
        self.manager.finished.connect(self._on_thumbnail_loaded)
        self.manager.get(QNetworkRequest(QUrl(url)))

    def _on_thumbnail_loaded(self, reply):
        image = QImage()
        image.loadFromData(reply.readAll())
        pixmap = QPixmap.fromImage(image)
        self.thumbnail_label.setPixmap(pixmap.scaled(100, 80, Qt.KeepAspectRatio))
