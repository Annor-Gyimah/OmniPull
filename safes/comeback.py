# def download_playlist(self):
    #     """Download playlist with video stream selection using PyQt."""

    #     # Check if there is a video file or quit
    #     if not self.video:
    #         self.show_information(self.tr("Play Download"), self.tr("Please check the url"),  self.tr("Playlist is empty, nothing to download :", ))
    #         #QMessageBox.information(self, "Playlist Download", "Playlist is empty, nothing to download :)")
    #         return

    #     # Prepare lists for video and audio streams
    #     mp4_videos = {}
    #     other_videos = {}
    #     audio_streams = {}

    #     # Collect streams from all videos in playlist
    #     for video in self.playlist:
    #         mp4_videos.update({stream.raw_name: stream for stream in video.mp4_videos.values()})
    #         other_videos.update({stream.raw_name: stream for stream in video.other_videos.values()})
    #         audio_streams.update({stream.raw_name: stream for stream in video.audio_streams.values()})

    #     # Sort streams based on quality
    #     mp4_videos = {k: v for k, v in sorted(mp4_videos.items(), key=lambda item: item[1].quality, reverse=True)}
    #     other_videos = {k: v for k, v in sorted(other_videos.items(), key=lambda item: item[1].quality, reverse=True)}
    #     audio_streams = {k: v for k, v in sorted(audio_streams.items(), key=lambda item: item[1].quality, reverse=True)}

    #     raw_streams = {**mp4_videos, **other_videos, **audio_streams}

    #     # Create a QDialog
    #     dialog = QDialog(self)
    #     dialog.setStyleSheet("""
    #         QWidget {
    #             background-color: rgb(33, 37, 43);
    #             color: white;
                
    #         }
    #     """)
        
    #     dialog.setWindowTitle(self.tr('Playlist Download'))
    #     layout = QVBoxLayout(dialog)

    #     # Master stream combo box
    #     master_stream_menu = ['● Video streams:'] + list(mp4_videos.keys()) + list(other_videos.keys()) + \
    #                         ['', '● Audio streams:'] + list(audio_streams.keys())
    #     master_stream_combo = QComboBox()
    #     master_stream_combo.addItems(master_stream_menu)

    #     # General options layout
    #     select_all_checkbox = QCheckBox(self.tr('Select All'))
    #     general_options_layout = QHBoxLayout()
    #     general_options_layout.addWidget(select_all_checkbox)
    #     general_options_layout.addWidget(QLabel(self.tr('Choose quality for all videos:')))
    #     general_options_layout.addWidget(master_stream_combo)

    #     layout.addLayout(general_options_layout)

    #     # Video layout inside a scrollable area
    #     scroll_area = QScrollArea(dialog)
    #     scroll_content = QFrame()
    #     scroll_layout = QVBoxLayout(scroll_content)

    #     video_checkboxes = []
    #     stream_combos = []

    #     for num, video in enumerate(self.playlist):
    #         # Create a checkbox for each video
    #         video_checkbox = QCheckBox(video.title[:40], scroll_content)
    #         video_checkbox.setToolTip(video.title)
    #         video_checkboxes.append(video_checkbox)

    #         # Create a combo box for stream selection
    #         stream_combo = QComboBox(scroll_content)
    #         stream_combo.addItems(video.raw_stream_menu)
    #         stream_combos.append(stream_combo)

    #         # Size label
    #         size_label = QLabel(size_format(video.total_size), scroll_content)

    #         # Create a row for each video
    #         video_row = QHBoxLayout()
    #         video_row.addWidget(video_checkbox)
    #         video_row.addWidget(stream_combo)
    #         video_row.addWidget(size_label)

    #         scroll_layout.addLayout(video_row)

    #     scroll_content.setLayout(scroll_layout)
    #     scroll_area.setWidget(scroll_content)
    #     scroll_area.setWidgetResizable(True)
    #     scroll_area.setFixedHeight(250)

    #     layout.addWidget(scroll_area)

    #     # OK and Cancel buttons
    #     button_layout = QHBoxLayout()
    #     ok_button = QPushButton(self.tr('OK'), dialog)
    #     cancel_button = QPushButton(self.tr('Cancel'), dialog)
    #     button_layout.addWidget(ok_button)
    #     button_layout.addWidget(cancel_button)

    #     layout.addLayout(button_layout)

    #     dialog.setLayout(layout)

    #     # Handle button actions
    #     def on_ok():
    #         chosen_videos = []
    #         for num, video in enumerate(self.playlist):
    #             selected_text = stream_combos[num].currentText()
    #             video.selected_stream = video.raw_streams[selected_text]
    #             if video_checkboxes[num].isChecked():
    #                 chosen_videos.append(video)

    #         dialog.accept()

    #         # Start download for the selected videos
    #         for video in chosen_videos:
    #             video.folder = config.download_folder
    #             self.start_download(video, silent=True)

    #     def on_cancel():
    #         dialog.reject()

    #     # Connect button actions
    #     ok_button.clicked.connect(on_ok)
    #     cancel_button.clicked.connect(on_cancel)

    #     # Select All functionality
    #     def on_select_all():
    #         for checkbox in video_checkboxes:
    #             checkbox.setChecked(select_all_checkbox.isChecked())

    #     select_all_checkbox.stateChanged.connect(on_select_all)

    #     # Master stream selection changes all streams
    #     def on_master_stream_combo_change():
    #         selected_text = master_stream_combo.currentText()
    #         if selected_text in raw_streams:
    #             for num, stream_combo in enumerate(stream_combos):
    #                 video = self.playlist[num]
    #                 if selected_text in video.raw_streams:
    #                     stream_combo.setCurrentText(selected_text)
    #                     video.selected_stream = video.raw_streams[selected_text]

    #     master_stream_combo.currentTextChanged.connect(on_master_stream_combo_change)

    #     # Show the dialog and process result
    #     if dialog.exec():
    #         self.change_page(btn=widgets.btn_widgets, btnName="btn_downloads", page=widgets.widgets)
   





















# def download_playlist(self):
#     if not self.video:
#         self.show_information(
#             self.tr("Playlist Download"), 
#             self.tr("Please check the URL."), 
#             self.tr("Playlist is empty, nothing to download.")
#         )
#         return

#     mp4_videos = {s.raw_name: s for v in self.playlist for s in v.mp4_videos.values()}
#     other_videos = {s.raw_name: s for v in self.playlist for s in v.other_videos.values()}
#     audio_streams = {s.raw_name: s for v in self.playlist for s in v.audio_streams.values()}
#     raw_streams = {**mp4_videos, **other_videos, **audio_streams}

#     dialog = QDialog(self)
#     dialog.setWindowTitle(self.tr("Playlist Download"))
#     dialog.setMinimumWidth(700)
#     dialog.setStyleSheet("""
#         QDialog {
#             background-color: qlineargradient(
#                 x1: 0, y1: 0, x2: 1, y2: 1,
#                 stop: 0 #0F1B14,
#                 stop: 1 #050708
#             );
#             color: white;
#             border-radius: 14px;
#         }
#         QCheckBox, QLabel, QComboBox, QPushButton {
#             font-size: 13px;
#             background: transparent;
#         }
#         QComboBox {
#             background-color: rgba(28, 28, 30, 0.85);
#             color: #e0e0e0;
#             border: 1px solid rgba(255, 255, 255, 0.05);
#             border-radius: 6px;
#             padding: 5px;
#         }
#         QComboBox QAbstractItemView {
#             background-color: rgba(20, 25, 20, 0.95);
#             border: 1px solid rgba(60, 200, 120, 0.25);
#             selection-background-color: #2DE099;
#             color: white;
#         }
#         QComboBox::drop-down {
#             border: none;
#             background: transparent;
#         }
#         QCheckBox {
#             spacing: 8px;
#             color: white;
#         }
#         QCheckBox::indicator {
#             width: 16px;
#             height: 16px;
#         }
#         QPushButton {
#             background-color: rgba(0, 128, 96, 0.4);
#             color: white;
#             border: 1px solid rgba(0, 255, 180, 0.1);
#             padding: 8px 16px;
#             border-radius: 6px;
#         }
#         QPushButton:hover {
#             background-color: rgba(0, 192, 128, 0.6);
#         }
#         QScrollArea {
#             border: none;
#         }
#         QWidget#scroll_item_row {
#             background-color: rgba(255, 255, 255, 0.02);
#             border-radius: 6px;
#             padding: 6px;
#         }
#     """)

#     layout = QVBoxLayout(dialog)
#     layout.setSpacing(16)

#     master_combo = QComboBox()
#     master_combo.addItems([
#         '● Video Streams:'
#     ] + list(mp4_videos) + list(other_videos) + [
#         '', '● Audio Streams:'
#     ] + list(audio_streams))

#     select_all = QCheckBox(self.tr("Select All"))
#     master_layout = QHBoxLayout()
#     master_layout.addWidget(select_all)
#     master_layout.addStretch()
#     master_layout.addWidget(QLabel(self.tr("Apply to all:")))
#     master_layout.addWidget(master_combo)

#     layout.addLayout(master_layout)

#     scroll = QScrollArea()
#     scroll.setWidgetResizable(True)
#     scroll_content = QWidget()
#     scroll_layout = QVBoxLayout(scroll_content)

#     video_checkboxes = []
#     stream_combos = []

#     for video in self.playlist:
#         cb = QCheckBox(video.title[:40])
#         cb.setToolTip(video.title)
#         video_checkboxes.append(cb)

#         combo = QComboBox()
#         combo.addItems(video.raw_stream_menu)
#         stream_combos.append(combo)

#         size = QLabel(size_format(video.total_size))

#         row = QHBoxLayout()
#         row.addWidget(cb)
#         row.addStretch()
#         row.addWidget(combo)
#         row.addWidget(size)

#         scroll_layout.addLayout(row)

#     scroll_content.setLayout(scroll_layout)
#     scroll.setWidget(scroll_content)
#     scroll.setMinimumHeight(250)

#     layout.addWidget(scroll)

#     buttons = QHBoxLayout()
#     ok_btn = QPushButton(self.tr("Download"))
#     cancel_btn = QPushButton(self.tr("Cancel"))
#     labela = QLabel("Please click on the video streams to select the video resolution and \n then click on the videos to select the video \n in this playlist and click on 'Download'")
#     buttons.addStretch()
#     buttons. addWidget(labela)
#     buttons.addWidget(ok_btn)
#     buttons.addWidget(cancel_btn)
    
    
#     layout.addLayout(buttons)

#     def on_ok():
#         chosen = []
#         for i, video in enumerate(self.playlist):
#             selected = stream_combos[i].currentText()
#             video.selected_stream = video.raw_streams[selected]
#             if video_checkboxes[i].isChecked():
#                 chosen.append(video)

#         dialog.accept()

#         for video in chosen:
#             video.folder = config.download_folder
#             # Check concurrent download limit BEFORE calling start_download
#             if len(self.active_downloads) >= config.max_concurrent_downloads:
#                 video.status = config.Status.pending
#                 self.pending.append(video)
#             else:
#                 self.start_download(video, silent=True)

#     def on_cancel():
#         dialog.reject()

#     def on_select_all():
#         for cb in video_checkboxes:
#             cb.setChecked(select_all.isChecked())

#     def on_master_combo_change():
#         selected = master_combo.currentText()
#         if selected in raw_streams:
#             for i, combo in enumerate(stream_combos):
#                 video = self.playlist[i]
#                 if selected in video.raw_streams:
#                     combo.setCurrentText(selected)
#                     video.selected_stream = video.raw_streams[selected]

#     ok_btn.clicked.connect(on_ok)
#     cancel_btn.clicked.connect(on_cancel)
#     select_all.stateChanged.connect(on_select_all)
#     master_combo.currentTextChanged.connect(on_master_combo_change)

#     if dialog.exec():
#         self.change_page(btn=None, btnName=None, idx=1)




# def check_scheduled(self):
#     t = time.localtime()
#     c_t = (t.tm_hour, t.tm_min)
#     for d in self.d_list:
#         if d.sched and d.sched[0] <= c_t[0] and d.sched[1] <= c_t[1]:
#             self.start_download(d, silent=True)  # send for download
#             d.sched = None  # cancel schedule time
#             d.status = config.Status.cancelled

    
# def check_scheduled(self):
#     t = time.localtime()
#     c_t = (t.tm_hour, t.tm_min)
#     for d in self.d_list:
#         if d.sched and d.sched[0] <= c_t[0] and d.sched[1] <= c_t[1]:
#             self.start_download(d, silent=True)  # send for download
#             d.sched = None  # cancel schedule time