from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QFileDialog, QSpacerItem, QSizePolicy, QMessageBox, QApplication, QProgressBar
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QLocalServer, QLocalSocket
from PySide6.QtGui import QAction, QIcon, QPixmap, QImage, QClipboard
from PySide6.QtCore import Qt, QSize, QUrl
from ui.youtube_thread import YouTubeThread  # new thread
from modules import config, downloaditem
from modules.video import(Video)
from threading import Thread, Timer
import os

import time

class AddDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        )

        self.setWindowTitle("Add Download")
        self.setFixedSize(600, 450)

        self.init_ui()
        self.setStyleSheet(self.stylesheet())
        self.url_timer = None  # usage: Timer(0.5, self.refresh_headers, args=[self.d.url])
        self.bad_headers = [0, range(400, 404), range(405, 418), range(500, 506)]  # response codes
        self.filename_set_by_program = False
        self.network_manager = QNetworkAccessManager()
        self.network_manager.finished.connect(self.on_thumbnail_downloaded)

        self.showEvent = lambda e: self.url_text_change()
        self.d = downloaditem.DownloadItem()
        self.folder_input.setText(config.download_folder)
        self.current_thumbnail = None
        self.filename_input.textChanged.connect(self.on_filename_changed)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # URL input row
        link_row = QHBoxLayout()
        self.link_input = QLineEdit()
        self.retry_btn = QPushButton("Retry")
        link_row.addWidget(QLabel("URL:"))
        link_row.addWidget(self.link_input)
        link_row.addWidget(self.retry_btn)
        layout.addLayout(link_row)

        # Folder path row
        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.open_btn = QPushButton("📂")
        folder_row.addWidget(QLabel("Save to:"))
        folder_row.addWidget(self.folder_input)
        folder_row.addWidget(self.open_btn)
        layout.addLayout(folder_row)

        # Filename row
        name_row = QHBoxLayout()
        self.filename_input = QLineEdit()
        name_row.addWidget(QLabel("Filename:"))
        name_row.addWidget(self.filename_input)
        layout.addLayout(name_row)

        # Progress Bar (slim)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Thumbnail + ComboBoxes
        thumb_combo_row = QHBoxLayout()

        # Thumbnail
        self.thumbnail_label = QLabel("Thumbnail")
        self.thumbnail_label.setFixedSize(100, 80)
        icon = QPixmap("icons/thumbnail-default.png")
        
        self.thumbnail_label.setPixmap(icon.scaled(150, 150, Qt.KeepAspectRatio))
        # self.thumbnail_label.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;")
        thumb_combo_row.addWidget(self.thumbnail_label)

        # ComboBox stack
        combo_stack = QVBoxLayout()
        self.quality_combo = QComboBox()
        self.format_combo = QComboBox()
        self.quality_combo.setPlaceholderText("Quality")
        self.format_combo.setPlaceholderText("Format")

        combo_stack.addWidget(self.quality_combo)
        combo_stack.addWidget(self.format_combo)
        thumb_combo_row.addLayout(combo_stack)

        layout.addLayout(thumb_combo_row)

        # Metadata labels row 1 (Size, Type)
        meta_row1 = QHBoxLayout()
        self.size_label = QLabel("Size:")
        self.size_value = QLabel("-")
        self.type_label = QLabel("Type:")
        self.type_value = QLabel("-")
        meta_row1.addWidget(self.size_label)
        meta_row1.addWidget(self.size_value)
        meta_row1.addSpacing(40)
        meta_row1.addWidget(self.type_label)
        meta_row1.addWidget(self.type_value)
        layout.addLayout(meta_row1)

        # Metadata labels row 2 (Protocol, Resumable)
        meta_row2 = QHBoxLayout()
        self.protocol_label = QLabel("Protocol:")
        self.protocol_value = QLabel("-")
        self.resumable_label = QLabel("Resumable:")
        self.resumable_value = QLabel("-")
        meta_row2.addWidget(self.protocol_label)
        meta_row2.addWidget(self.protocol_value)
        meta_row2.addSpacing(40)
        meta_row2.addWidget(self.resumable_label)
        meta_row2.addWidget(self.resumable_value)
        layout.addLayout(meta_row2)

        # Action buttons
        button_row = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.download_btn = QPushButton("Download")
        self.cancel_btn = QPushButton("Cancel")
        button_row.addStretch()
        button_row.addWidget(self.add_btn)
        button_row.addWidget(self.download_btn)
        button_row.addWidget(self.cancel_btn)
        layout.addLayout(button_row)

        # Connect cancel
        self.cancel_btn.clicked.connect(self.reject)





















    def on_filename_changed(self, text):
        """Handle manual changes to the filename line edit."""
        # Only update the download item if the change was made manually
        if not self.filename_set_by_program:
            self.d.name = text

    def url_text_change(self):
        """Handle URL changes in the QLineEdit."""
        url = self.link_input.text().strip()
        if url == self.d.url:
            return

        self.reset()
        try:
            self.d.eff_url = self.d.url = url
            print(f"New URL set: {url}")
            # Update the DownloadItem with the new URL
            # schedule refresh header func
            if isinstance(self.url_timer, Timer):
                self.url_timer.cancel()  # cancel previous timer

            self.url_timer = Timer(0.5, self.refresh_headers, args=[url])
            self.url_timer.start()
            # Trigger the progress bar update and GUI refresh
        except AttributeError as e:
            print(f"Error setting URLs in the object 'self.d': {e}")
            return  # Early return if we can't set URLs properly

    def process_url(self):
        """Simulate processing the URL and update the progress bar.""" 
        progress_steps = [10, 50, 100]  # Define the progress steps
        for step in progress_steps:
            time.sleep(1)  # Simulate processing time
            # Update the progress bar in the main thread
            self.update_progress_bar_value(step)  

    def update_progress_bar_value(self, value):
        """Update the progress bar value in the GUI."""
        self.progress_bar.setValue(value)   

    def update_progress_bar(self):
        """Update the progress bar based on URL processing."""
        # Start a new thread for the progress updates
        Thread(target=self.process_url, daemon=True).start()


    def retry(self):
        self.d.url = ''
        self.url_text_change()

    def reset(self):
        # create new download item, the old one will be garbage collected by python interpreter
        self.d = downloaditem.DownloadItem()

        # reset some values
        self.playlist = []
        self.video = None

    

    
    def refresh_headers(self, url):
        if self.d.url != '':
            #self.change_cursor('busy')
            Thread(target=self.get_header, args=[url], daemon=True).start()

    def get_header(self, url):
        self.d.update(url)

        if url == self.d.url:
            if self.d.status_code not in self.bad_headers and self.d.type != 'text/html':
                self.download_btn.setEnabled(True)

            # Use QThread for YouTube function
            self.yt_thread = YouTubeThread(url)
            self.yt_thread.finished.connect(self.on_youtube_finished)
            # self.yt_thread.finished.connect(self.handle_video_info)
            self.yt_thread.progress.connect(self.update_progress_bar_value)  # Connect progress signal to update progress bar
            self.yt_thread.start()

    def handle_video_info(self, video):
        self.d = video
        self.filename_set_by_program = True
        self.filename_input.setText(video.name)
        self.filename_set_by_program = False

        # Send updates to main window queue manager
        updates = {
            "filename": video.name,
            "size": video.size,
            "type": video.type,
            "protocol": video.protocol,
            "resumable": video.resumable
        }

        for k, v in updates.items():
            config.main_window_q.put((k, v))  # Add to queue

        # self.quality_combo.clear()
        # self.quality_combo.addItems(video.stream_names)
        # self.format_combo.clear()
        # self.format_combo.addItems(video.formats)
        # self.show_thumbnail(video.thumbnail_url)


    def on_youtube_finished(self, result):
        if isinstance(result, list):
            self.playlist = result
            if self.playlist:
                self.d = self.playlist[0]
        elif isinstance(result, Video):
            self.playlist = [result]
            self.d = result
        else:
            print("Error: YouTube extraction failed")
            self.change_cursor('normal')
            self.download_btn.setEnabled(True)
            self.quality_combo.clear()
            self.format_combo.clear()
            self.reset_to_default_thumbnail()
            return

        self.update_pl_menu()
        self.update_stream_menu()

    

    def change_cursor(self, cursor_type):
        """Change cursor to busy or normal."""
        if cursor_type == 'busy':
            QApplication.setOverrideCursor(Qt.WaitCursor)  # Busy cursor
        elif cursor_type == 'normal':
            QApplication.restoreOverrideCursor()  # Restore normal cursor

    def show_thumbnail(self, thumbnail=None):
        """Show video thumbnail in thumbnail image widget in main tab, call without parameter to reset thumbnail."""

        try:
            if thumbnail is None or thumbnail == "":
                # Reset to default thumbnail if no new thumbnail is provided
                default_pixmap = QPixmap("icons/thumbnail-default.png")
                self.thumbnail_label.setPixmap(default_pixmap.scaled(150, 150, Qt.KeepAspectRatio))
                print("Resetting to default thumbnail")
            elif thumbnail != self.current_thumbnail:
                self.current_thumbnail = thumbnail

                if thumbnail.startswith(('http://', 'https://')):
                    # If it's a URL, download the image
                    request = QNetworkRequest(QUrl(thumbnail))
                    self.network_manager.get(request)
                else:
                    # If it's a local file path
                    pixmap = QPixmap(thumbnail)
                    if not pixmap.isNull():
                        self.thumbnail_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio))
                    else:
                        self.reset_to_default_thumbnail()

        except Exception as e:
            print('show_thumbnail() error:', e)
            self.reset_to_default_thumbnail()

    def on_thumbnail_downloaded(self, reply):
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            image = QImage()
            if image.loadFromData(data):
                pixmap = QPixmap.fromImage(image)
                self.thumbnail_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio))
            else:
                self.reset_to_default_thumbnail()
        else:
            self.reset_to_default_thumbnail()

    def reset_to_default_thumbnail(self):
        default_pixmap = QPixmap("icons/thumbnail-default.png")
        self.thumbnail_label.setPixmap(default_pixmap.scaled(150, 150, Qt.KeepAspectRatio))
        print("Reset to default thumbnail due to error")
        #widgets.monitor_clipboard.setChecked(True)


    def update_pl_menu(self):
        """Update the playlist combobox after processing."""
        try:
            print("Updating playlist menu")
            if not hasattr(self, 'playlist') or not self.playlist:
                print("Error: Playlist is empty or not initialized")
                return

            # Set the playlist combobox with video titles
            self.quality_combo.clear()  # Clear existing items
            for i, video in enumerate(self.playlist):
                if hasattr(video, 'title') and video.title:
                    self.quality_combo.addItem(f'{i + 1} - {video.title}')
                else:
                    print(f"Warning: Video at index {i} has no title")

            # Automatically select the first video in the playlist
            if self.playlist:
                self.playlist_OnChoice(self.playlist[0])

        except Exception as e:
            print(f"Error updating playlist menu: {e}")
            import traceback
            print('Traceback:', traceback.format_exc())

    def update_stream_menu(self):
        """Update the stream combobox after selecting a video."""
        try:
            print("Updating stream menu")
            
            if not hasattr(self, 'd') or not self.d:
                print("Error: No video selected")
                return
            
            if not hasattr(self.d, 'stream_names') or not self.d.stream_names:
                print("Error: Selected video has no streams")
                return

            # Set the stream combobox with available stream options
            self.format_combo.clear()  # Clear existing items
            self.format_combo.addItems(self.d.stream_names)

            # Automatically select the first stream
            if self.d.stream_names:
                selected_stream = self.d.stream_names[0]
                self.format_combo.setCurrentText(selected_stream)
                self.stream_OnChoice(selected_stream)

        except Exception as e:
            print(f"Error updating stream menu: {e}")
            import traceback
            print('Traceback:', traceback.format_exc())

    def playlist_OnChoice(self, selected_video):
        """Handle playlist item selection."""
        if selected_video not in self.playlist:
            return

        # Find the selected video index and set it as the current download item
        index = self.playlist.index(selected_video)
        self.video = self.playlist[index]
        self.d = self.video  # Update current download item to the selected video

        # Update the stream menu based on the selected video
        self.update_stream_menu()

        # Optionally load the video thumbnail in a separate thread
        if config.show_thumbnail:
            Thread(target=self.video.get_thumbnail).start()
        
            self.show_thumbnail(thumbnail=self.video.thumbnail_url)
        
        
    def stream_OnChoice(self, selected_stream):
        """Handle stream selection."""
    
        # Check if the selected stream is different from the current one
        if selected_stream == getattr(self.video, 'selected_stream_name', None):
            # If it's the same stream as the current one, skip further processing
            print(f"Stream '{selected_stream}' is already selected. No update needed.")
            return

        # Check if the selected stream exists in the available stream names
        if selected_stream not in self.video.stream_names:
            print(f"Warning: Selected stream '{selected_stream}' is not valid, defaulting to the first stream.")
            selected_stream = self.video.stream_names[0]  # Default to the first stream if invalid
        
        # Update the selected stream in the video object
        self.video.selected_stream = self.video.streams[selected_stream]  # Update with stream object
        self.video.selected_stream_name = selected_stream  # Keep track of the selected stream name

        print(f"Stream '{selected_stream}' selected for video {self.video.title}")


    def stylesheet(self):
        return """
        QDialog {
            background-color: #1e1e1e;
        }
        QLabel, QLineEdit, QPushButton, QCheckBox {
            font-size: 13px;
            color: #ffffff;
        }
        QLineEdit {
            background-color: #2e2e2e;
            border: 1px solid #444;
            border-radius: 4px;
            padding: 6px;
            
        }
        QLineEdit:hover {
            border: 1px solid #00C853;
        }
        QPushButton {
            background-color: #333;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 6px 12px;
            color: white;
        }
        QPushButton:hover {
            background-color: #444;
        }
        QComboBox {
            background-color: #2e2e2e;
            color: white;
            border-radius: 4px;
            padding: 6px;
        }
        QCheckBox::indicator:checked {
            background-color: #00C853;
            border: 1px solid #00C853;
        }
        """
























# class AddDownloadDialog(QDialog):
#     def __init__(self, parent=None):
        
#         super().__init__(parent)
#         self.showEvent = lambda e: self.start_info_thread()

#         self.setWindowTitle("Add Download")
#         self.setFixedSize(600, 280)
#         self.setStyleSheet(self.stylesheet())

#         layout = QVBoxLayout(self)
#         layout.setSpacing(15)

#         # Download Link Input
#         self.link_input = QLineEdit()
#         self.link_input.setPlaceholderText("Download link")
#         retry_btn = QPushButton("↻")
#         retry_btn.setFixedWidth(40)
#         retry_btn.clicked.connect(self.retry_fetch_info)

#         row1 = QHBoxLayout()
#         row1.addWidget(QLabel("Download link"))
#         row1.addStretch()
#         layout.addLayout(row1)

#         row2 = QHBoxLayout()
#         row2.addWidget(self.link_input)
#         row2.addWidget(retry_btn)
#         layout.addLayout(row2)

#         # Category
#         self.use_category_cb = QCheckBox("Use Category")
#         self.category_combo = QComboBox()
#         self.category_combo.addItems(["Compressed", "Documents", "Music", "Programs", "Video"])
#         self.category_combo.setEnabled(False)
#         self.use_category_cb.toggled.connect(self.category_combo.setEnabled)

#         row3 = QHBoxLayout()
#         row3.addWidget(self.use_category_cb)
#         row3.addWidget(self.category_combo)
#         row3.addStretch()
#         layout.addLayout(row3)

#         # Download Folder
#         self.folder_input = QLineEdit()
#         self.folder_input.setPlaceholderText("Download folder path")
#         folder_btn = QPushButton("📂")
#         folder_btn.setFixedWidth(40)
#         folder_btn.clicked.connect(self.select_folder)

#         row4 = QHBoxLayout()
#         row4.addWidget(self.folder_input)
#         row4.addWidget(folder_btn)
#         layout.addLayout(row4)

#         # Filename
#         self.name_input = QLineEdit()
#         self.name_input.setPlaceholderText("Filename")
#         layout.addWidget(self.name_input)

#         # Buttons (Add, Download, Cancel)
#         row5 = QHBoxLayout()
#         self.add_btn = QPushButton("Add")
#         self.download_btn = QPushButton("Download")
#         self.cancel_btn = QPushButton("Cancel")

#         self.cancel_btn.clicked.connect(self.reject)

#         row5.addWidget(self.add_btn)
#         row5.addWidget(self.download_btn)
#         row5.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
#         row5.addWidget(self.cancel_btn)
#         layout.addLayout(row5)

#         self.d = downloaditem.DownloadItem()
#         self.filename_set_by_program = False
#         #self.name_input.connect(self.on_filename_changed)

#     def retry_fetch_info(self):
#         # Placeholder for retry logic
#         print("Retry clicked!")

#     def select_folder(self):
#         """Open a dialog to select a folder and update the line edit."""
#         # Open a folder selection dialog
#         folder_path = QFileDialog.getExistingDirectory(self, "Select Download Folder")

#         # If a folder is selected, update the line edit with the absolute path
#         if folder_path:
#             self.folder_input.setText(folder_path)
#             config.download_folder = os.path.abspath(folder_path)
#         else:
#             # If no folder is selected, reset to the default folder (config.download_folder)
#             self.folder_input.setText(config.download_folder)

#     # def on_filename_changed(self, text):
#     #     """Handle manual changes to the filename line edit."""
#     #     # Only update the download item if the change was made manually
#     #     if not self.filename_set_by_program:
#     #         self.d.name = text

#     def start_info_thread(self):
#         url = self.link_input.text().strip()
#         if not url:
#             return

#         self.yt_thread = YouTubeThread(url)
#         self.yt_thread.finished.connect(self.handle_video_info)
#         self.yt_thread.error_signal.connect(self.handle_video_error)
#         self.yt_thread.start()

#     def on_youtube_finished(self, result):
#         if isinstance(result, list):
#             self.playlist = result
#             if self.playlist:
#                 self.d = self.playlist[0]
#         elif isinstance(result, Video):
#             self.playlist = [result]
#             self.d = result
#         else:
#             print("Error: YouTube extraction failed")
#             self.change_cursor('normal')
#             self.download_btn.setEnabled(True)
            
#             return

#         # self.update_pl_menu()
#         # self.update_stream_menu()

#     def change_cursor(self, cursor_type):
#         """Change cursor to busy or normal."""
#         if cursor_type == 'busy':
#             QApplication.setOverrideCursor(Qt.WaitCursor)  # Busy cursor
#         elif cursor_type == 'normal':
#             QApplication.restoreOverrideCursor()  # Restore normal cursor

#     def handle_video_info(self, video):
#         self.name_input.setText(video.name)
#         # Populate streams, quality, etc. if needed

#     def handle_video_error(self, message):
#         QMessageBox.critical(self, "Error", f"Failed to retrieve video info:\n{message}")

#     def stylesheet(self):
#         return """
#         QDialog {
#             background-color: #1e1e1e;
#         }
#         QLabel, QLineEdit, QPushButton, QCheckBox {
#             font-size: 13px;
#             color: #ffffff;
#         }
#         QLineEdit {
#             background-color: #2e2e2e;
#             border: 1px solid #444;
#             border-radius: 4px;
#             padding: 6px;
            
#         }
#         QLineEdit:hover {
#             border: 1px solid #00C853;
#         }
#         QPushButton {
#             background-color: #333;
#             border: 1px solid #555;
#             border-radius: 4px;
#             padding: 6px 12px;
#             color: white;
#         }
#         QPushButton:hover {
#             background-color: #444;
#         }
#         QComboBox {
#             background-color: #2e2e2e;
#             color: white;
#             border-radius: 4px;
#             padding: 6px;
#         }
#         QCheckBox::indicator:checked {
#             background-color: #00C853;
#             border: 1px solid #00C853;
#         }
#         """
