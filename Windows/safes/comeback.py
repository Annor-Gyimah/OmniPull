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



# def toolbar_buttons_state(self, status: str) -> dict:
    #     if status == config.Status.completed:
    #         return {
    #             "Resume": False,
    #             "Pause": False,
    #             "Delete": True,
    #             "Delete All": False,
    #             "Refresh": True,
    #             "Resume All": False,
    #             "Stop All": False,
    #             "Schedule All": False,
    #             "Settings": True,
    #             "Download Window": False,
    #         }

    #     elif status in {config.Status.cancelled, config.Status.error, config.Status.paused, config.Status.failed}:

    #         return {
    #             "Resume": True,
    #             "Pause": False,
    #             "Delete": True,
    #             "Delete All": False,
    #             "Refresh": True,
    #             "Resume All": False,
    #             "Stop All": False,
    #             "Schedule All": False,
    #             "Settings": True,
    #             "Download Window": False,
    #         }
        
    #     elif status == config.Status.deleted:
    #         return {
    #             "Resume": False,
    #             "Pause": False,
    #             "Delete": True,
    #             "Delete All": False,
    #             "Refresh": True,
    #             "Resume All": False,
    #             "Stop All": False,
    #             "Schedule All": False,
    #             "Settings": True,
    #             "Download Window": False,
    #         }

    #     elif status == config.Status.scheduled:
    #         return {
    #             "Resume": False,
    #             "Pause": False,
    #             "Delete": True,
    #             "Delete All": False,
    #             "Refresh": True,
    #             "Resume All": False,
    #             "Stop All": False,
    #             "Schedule All": False,
    #             "Settings": True,
    #             "Download Window": False,
    #         }
        
    #     elif status == config.Status.downloading:
    #         return {
    #             "Resume": False,
    #             "Pause": True,
    #             "Delete": False,
    #             "Delete All": False,
    #             "Refresh": False,
    #             "Resume All": False,
    #             "Stop All": False,
    #             "Schedule All": False,
    #             "Settings": True,
    #             "Download Window": True,
    #         }
        
    #     elif status == config.Status.pending:
    #         return {
    #             "Resume": False,
    #             "Pause": True,
    #             "Delete": False,
    #             "Delete All": False,
    #             "Refresh": False,
    #             "Resume All": False,
    #             "Stop All": False,
    #             "Schedule All": False,
    #             "Settings": True,
    #             "Download Window": False,
    #         }
        
    #     elif status == config.Status.merging_audio:
    #         return {
    #             "Resume": False,
    #             "Pause": False,
    #             "Delete": False,
    #             "Delete All": False,
    #             "Refresh": False,
    #             "Resume All": False,
    #             "Stop All": False,
    #             "Schedule All": False,
    #             "Settings": True,
    #             "Download Window": False,
    #         }






    # def update_toolbar_buttons_for_selection(self):
    #     selected_rows = widgets.table.selectionModel().selectedRows()

    #     if not selected_rows:
    #         # Enable only global buttons
    #         for key in widgets.toolbar_buttons:
    #             widgets.toolbar_buttons[key].setEnabled(key in {
    #                 "Stop All", "Resume All", "Settings", "Schedule All"
    #             })
    #         return

    #     id_item = widgets.table.item(selected_rows[0].row(), 0)
    #     if not id_item:
    #         return

    #     selected_id = id_item.data(Qt.UserRole)
    #     d = next((x for x in self.d_list if x.id == selected_id), None)
    #     if not d:
    #         return

    #     states = self.toolbar_buttons_state(d.status)
    #     for key, enabled in states.items():
    #         if key in widgets.toolbar_buttons:
    #             widgets.toolbar_buttons[key].setEnabled(enabled)



# def populate_table(self):
    #     for row, d in enumerate(reversed(self.d_list)):
    #         if row >= widgets.table.rowCount():  # Check if we need to insert a new row
                
    #             widgets.table.insertRow(row)
            
    #         # Set the ID column
    #         # id_item = QTableWidgetItem(str(len(self.d_list) - row))
    #         id_item = QTableWidgetItem(str(len(self.d_list) - row))
    #         id_item.setData(Qt.UserRole, d.id)


    #         # Make the ID column non-editable
    #         id_item.setFlags(id_item.flags() & ~QtCore.Qt.ItemIsEditable)
    #         widgets.table.setItem(row, 0, id_item)  # First column is ID
            
    #         # Fill the remaining columns based on the d_headers
    #         for col, key in enumerate(self.d_headers[1:], 1):  # Skip 'id', already handled
    #             cell_value = self.format_cell_data(key, getattr(d, key, ''))
    #             item = QTableWidgetItem(cell_value)
    #             # Make the item non-editable
    #             item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
    #             widgets.table.setItem(row, col, item)

    # def update_table_progress(self):
    #     for row in range(widgets.table.rowCount()):
    #         try:
    #             # d_index = len(self.d_list) - 1 - row  # reversed index for latest-first display
    #             # d = self.d_list[d_index]

    #             id_item = widgets.table.item(row, 0)
    #             if not id_item:
    #                 continue

    #             download_id = id_item.data(Qt.UserRole)
    #             d = next((x for x in self.d_list if x.id == download_id), None)
    #             if not d:
    #                 continue


    #             progress_widget = widgets.table.cellWidget(row, 2)
    #             if isinstance(progress_widget, QProgressBar):
    #                 if d.progress is not None:
    #                     progress_widget.setValue(int(d.progress))
    #                     progress_widget.setFormat(f"{int(d.progress)}%")
    #         except Exception as e:
    #             log(f"Error updating progress bar at row {row}: {e}")

# def show_table_context_menu(self, pos: QPoint):
    #     # Get the position of the click (row)
    #     index = widgets.table.indexAt(pos)
    #     if not index.isValid():
    #         return  # No valid cell clicked

    #     # Check if the cell contains data
    #     cell_data = widgets.table.item(index.row(), index.column())
    #     if cell_data is None or cell_data.text().strip() == "":
    #         return  # Cell is empty, don't show context menu

    #     # Create the context menu
    #     context_menu = QMenu(widgets.table)

    #     # Create 
    #     icon_path_1 = os.path.join(os.path.dirname(__file__), "icons", "cil-file.png")
    #     action_open_file = QAction(QIcon(icon_path_1), self.tr('Open File'), context_menu)
    #     icon_path_2 = os.path.join(os.path.dirname(__file__), "icons", "cil-folder.png")
    #     action_open_location = QAction(QIcon(icon_path_2), self.tr('Open File Location'), context_menu)
    #     icon_path_3 = os.path.join(os.path.dirname(__file__), "icons", "cil-media-play.png")
    #     action_watch_downloading = QAction(QIcon(icon_path_3), self.tr('Watch while downloading'), context_menu)
    #     icon_path_4 = os.path.join(os.path.dirname(__file__), "icons", "cil-clock.png")
    #     action_schedule_download = QAction(QIcon(icon_path_4), self.tr('Schedule download'), context_menu)
    #     icon_path_5 = os.path.join(os.path.dirname(__file__), "icons", "cil-x.png")
    #     action_cancel_schedule = QAction(QIcon(icon_path_5), self.tr('Cancel schedule!'), context_menu)
    #     icon_path_6 = os.path.join(os.path.dirname(__file__), "icons", "cil-info.png")
    #     action_file_properties = QAction(QIcon(icon_path_6), self.tr('File Properties'), context_menu)


        


    #     # Add actions to the context menu
    #     context_menu.addAction(action_open_file)
    #     context_menu.addAction(action_open_location)
    #     context_menu.addAction(action_watch_downloading)
    #     context_menu.addAction(action_schedule_download)
    #     context_menu.addAction(action_cancel_schedule)
    #     context_menu.addAction(action_file_properties)

    #     # Connect actions to methods
    #     action_open_file.triggered.connect(self.open_item)
    #     action_open_location.triggered.connect(self.open_file_location)
    #     action_watch_downloading.triggered.connect(self.watch_downloading)
    #     action_schedule_download.triggered.connect(self.schedule_download)
    #     action_cancel_schedule.triggered.connect(self.cancel_schedule)
    #     action_file_properties.triggered.connect(self.file_properties)

        
    #     # action_view_details.triggered.connect(self.view_details)
        

    #     # Show the context menu at the cursor position
    #     context_menu.exec(widgets.table.viewport().mapToGlobal(pos))




# def check_scheduled(self):
    #     now = time.localtime()

    #     for d in self.d_list:
    #         if d.status == config.Status.scheduled and getattr(d, "sched", None):
    #             if (d.sched[0], d.sched[1]) == (now.tm_hour, now.tm_min):
    #                 log(f"Scheduled time matched for {d.name}, attempting download...")

    #                 result = self.start_download(d, silent=True)

    #                 # Retry condition: download failed or was cancelled
    #                 if d.status in [config.Status.failed, config.Status.cancelled, config.Status.error]:
    #                     log(f"Scheduled download failed for {d.name}.")

    #                     if config.retry_scheduled_enabled:
    #                         d.schedule_retries = getattr(d, "schedule_retries", 0)

    #                         if d.schedule_retries < config.retry_scheduled_max_tries:
    #                             d.schedule_retries += 1

    #                             # Add retry interval
    #                             from datetime import datetime, timedelta
    #                             retry_time = datetime.now() + timedelta(
    #                                 minutes=config.retry_scheduled_interval_mins)
    #                             d.sched = (retry_time.hour, retry_time.minute)
    #                             d.status = config.Status.scheduled
    #                             log(f"Retrying {d.name} at {d.sched[0]}:{d.sched[1]} [Attempt {d.schedule_retries}]")
    #                         else:
    #                             d.status = config.Status.failed
    #                             log(f"{d.name} has reached max retries.")
    #                     else:
    #                         d.status = config.Status.failed

    #     self.queue_update("populate_table", None)



# def resume_btn(self):
    #     selected_row = widgets.table.currentRow()
    #     if selected_row < 0 or selected_row >= widgets.table.rowCount():
    #         self.show_warning(self.tr("Error"), self.tr("No download item selected"))
    #         return

    #     d_index = len(self.d_list) - 1 - selected_row
    #     d = self.d_list[d_index]

    #     self.start_download(d, silent=True)



 # def resume_all_downloads(self):
    #     # change status of all non completed items to pending
    #     for d in self.d_list:
    #         if d.status == config.Status.cancelled:
    #             self.start_download(d, silent=True)






# def update_param(self):
    #     # do some parameter updates
    #     stream = self.selected_stream
    #     self.name = self.title + '.' + stream.extension
    #     self.eff_url = stream.url
    #     self.type = stream.mediatype
    #     self.size = stream.size
    #     self.fragment_base_url = stream.fragment_base_url
    #     self.fragments = stream.fragments
    #     self.protocol = stream.protocol
    #     self.format_id = stream.format_id
    #     self.manifest_url = stream.manifest_url

    #     #print(f"This is the PROTOCOL: {self.protocol}")

    #     # Filter audio streams based on extension compatibility
    #     audio_streams = [audio for audio in self.audio_streams.values()
    #                     if audio.extension == stream.extension or
    #                     (audio.extension == 'm4a' and stream.extension == 'mp4')]

    #     if not audio_streams:  # Ensure there are available audio streams
    #         log("No suitable audio stream found!")
    #         return

    #     # Select an audio to embed if our stream is DASH video
    #     if stream.mediatype == 'dash' and self.protocol.startswith('http'):
    #         if len(audio_streams) > 2:
    #             audio_stream = audio_streams[2]
    #         else:
    #             audio_stream = audio_streams[3]  # Fallback to first available
    #     else:
    #         # If protocol is 'm3u8_native' or other formats
    #         audio_stream = audio_streams[0]

    #     print(audio_stream)
    #     self.audio_stream = audio_stream
    #     self.audio_url = audio_stream.url
    #     self.audio_size = audio_stream.size
    #     self.audio_fragment_base_url = audio_stream.fragment_base_url
    #     self.audio_fragments = audio_stream.fragments
    #     self.audio_format_id = audio_stream.format_id

    

    # def update_param(self):
    #     # do some parameter updates
    #     stream = self.selected_stream
    #     self.name = self.title + '.' + stream.extension
    #     self.eff_url = stream.url
    #     self.type = stream.mediatype
    #     self.size = stream.size
    #     self.fragment_base_url = stream.fragment_base_url
    #     self.fragments = stream.fragments
    #     self.protocol = stream.protocol
    #     self.format_id = stream.format_id
    #     self.manifest_url = stream.manifest_url

    #     print(f"This is the PROTOCOL: {self.protocol}")

    #     # select an audio to embed if our stream is dash video
    #     if stream.mediatype == 'dash' and self.protocol == 'https':
    #         audio_stream = [audio for audio in self.audio_streams.values() if audio.extension == stream.extension
    #                         or (audio.extension == 'm4a' and stream.extension == 'mp4')][2]
    #         print(audio_stream)
    #         self.audio_stream = audio_stream
    #         self.audio_url = audio_stream.url
    #         self.audio_size = audio_stream.size
    #         self.audio_fragment_base_url = audio_stream.fragment_base_url
    #         self.audio_fragments = audio_stream.fragments
    #         self.audio_format_id = audio_stream.format_id
    #     else:
    #         #self.protocol == 'm3u8_native
    #         audio_stream = [audio for audio in self.audio_streams.values() if audio.extension == stream.extension
    #                         or (audio.extension == 'm4a' and stream.extension == 'mp4')][0]
    #         print(audio_stream)
    #         self.audio_stream = audio_stream
    #         self.audio_url = audio_stream.url
    #         self.audio_size = audio_stream.size
    #         self.audio_fragment_base_url = audio_stream.fragment_base_url
    #         self.audio_fragments = audio_stream.fragments
    #         self.audio_format_id = audio_stream.format_id














# def update_table_progress(self):
#         for row in range(widgets.table.rowCount()):
#             try:
#                 id_item = widgets.table.item(row, 0)
#                 if not id_item:
#                     continue

#                 download_id = id_item.data(Qt.UserRole)
#                 d = next((x for x in self.d_list if x.id == download_id), None)
#                 if not d:
#                     continue
                

               

                
#                 progress_widget = widgets.table.cellWidget(row, 2)
#                 if isinstance(progress_widget, QProgressBar):
#                     # Add tracking if missing
#                     if not hasattr(progress_widget, 'last_status'):
#                         progress_widget.last_status = None

#                     # Always update progress if downloading
#                     if d.status == config.Status.downloading:
#                         progress_widget.setValue(int(d.progress))
#                         progress_widget.setFormat(f"{int(d.progress)}%")
#                         color = "#2962FF"
                        
#                         progress_widget.setStyleSheet(f"""
#                             QProgressBar {{
#                                 background-color: #2a2a2a;
#                                 border: 1px solid #444;
#                                 border-radius: 4px;
#                                 text-align: center;
#                                 color: white;
#                             }}
#                             QProgressBar::chunk {{
#                                 background-color: {color};
#                                 border-radius: 4px;
#                             }}
#                         """)
#                         progress_widget.last_status = d.status  # still update status cache

#                     # For other statuses, only update when changed
#                     elif d.status != progress_widget.last_status:
#                         if d.status == config.Status.queued:
#                             progress_widget.setValue(0)
#                             progress_widget.setFormat("Queued")
#                             color = "#9C27B0"
#                         elif d.status == config.Status.completed:
#                             progress_widget.setValue(100)
#                             progress_widget.setFormat("100%")
#                             color = "#00C853"
#                         elif d.status == config.Status.cancelled:
#                             progress_widget.setValue(d.progress)
#                             # progress_widget.setFormat("Cancelled")
#                             color = "#D32F2F"
#                         elif d.status == config.Status.error:
#                             progress_widget.setValue(0)
#                             progress_widget.setFormat("Error")
#                             color = "#9E9E9E"
#                         elif d.status == config.Status.pending:
#                             progress_widget.setValue(d.progress)
#                             # progress_widget.setFormat("Pending")
#                             color = "#FDD835"
#                         elif d.status == config.Status.scheduled:
#                             # progress_widget.setValue(0)
#                             # progress_widget.setFormat("Scheduled")
#                             color = "#F7DC6F"
#                         elif d.status == config.Status.deleted:
#                             progress_widget.setValue(d.progress)
#                             # progress_widget.setFormat("Deleted")
#                             color = "#9C27B0"
#                         elif d.status == config.Status.merging_audio:
#                             progress_widget.setValue(d.progress)
#                             color = "#FF9800"
#                         else:
#                             progress_widget.setValue(0)
#                             progress_widget.setFormat("---")
#                             color = "#888888"

#                         progress_widget.setStyleSheet(f"""
#                             QProgressBar {{
#                                 background-color: #2a2a2a;
#                                 border: 1px solid #444;
#                                 border-radius: 4px;
#                                 text-align: center;
#                                 color: white;
#                             }}
#                             QProgressBar::chunk {{
#                                 background-color: {color};
#                                 border-radius: 4px;
#                             }}
#                         """)
#                         progress_widget.last_status = d.status

#                 # if isinstance(progress_widget, QProgressBar):
#                 #     if d.progress is not None:
#                 #         progress_widget.setValue(int(d.progress))
#                 #         progress_widget.setFormat(f"{int(d.progress)}%")
#                 # if isinstance(progress_widget, QProgressBar):
#                 #     if d.status == config.Status.queued:
#                 #         progress_widget.setValue(0)
#                 #         progress_widget.setFormat("Queued")
#                 #         color = "#9C27B0"
#                 #     else:
#                 #         progress_widget.setValue(int(d.progress))
#                 #         progress_widget.setFormat(f"{int(d.progress)}%")

#                 #         # Change bar color based on status
#                 #         color = "#00C853"  # default: green
#                 #         if d.status == "downloading":
#                 #             color = "#2962FF"
#                 #         elif d.status == "completed":
#                 #             color = "#00C853"
#                 #         elif d.status == "cancelled":
#                 #             color = "#D32F2F"
#                 #         elif d.status == "pending":
#                 #             color = "#FDD835"
#                 #         elif d.status == "error":
#                 #             color = "#9E9E9E"
#                 #         elif d.status == "merging_audio":
#                 #             color = "#FF9800"
#                 #         elif d.status == "scheduled":
#                 #             color = "#F7DC6F"
#                 #         elif d.status == "deleted":
#                 #             color = "#9C27B0"  # purple
                        
                        

#                 #     progress_widget.setStyleSheet(f"""
#                 #         QProgressBar {{
#                 #             background-color: #2a2a2a;
#                 #             border: 1px solid #444;
#                 #             border-radius: 4px;
#                 #             text-align: center;
#                 #             color: white;
#                 #         }}
#                 #         QProgressBar::chunk {{
#                 #             background-color: {color};
#                 #             border-radius: 4px;
#                 #         }}
#                 #     """)color = "#FF9800"
                    
                        

                

                

#             except Exception as e:
#                 log(f"Error updating progress bar at row {row}: {e}")















# class QueueRunner(QObject):
#     queue_finished = Signal(str)  # queue_id
#     download_started = Signal(object)
#     download_finished = Signal(object)

#     def __init__(self, queue_id, queue_items, parent=None):
#         super().__init__(parent)
#         self.queue_id = queue_id
#         self.queue_items = queue_items
#         self.index = 0
#         self.threads = []

#     def start(self):
#         self.start_next()

#     def start_next(self):
#         if self.index >= len(self.queue_items):
#             self.queue_finished.emit(self.queue_id)
#             return

#         d = self.queue_items[self.index]
#         self.download_started.emit(d)

#         # Setup thread + worker
#         thread = QThread()
#         worker = DownloadWorker(d)
#         worker.moveToThread(thread)

#         # Hook up thread-safe signals
#         worker.finished.connect(lambda d=d: self.handle_finished(d))

#         thread.started.connect(worker.run)
#         thread.finished.connect(thread.deleteLater)
#         thread.start()

#         self.threads.append(thread)  # Hold reference

#         # Create and connect DownloadWindow
#         if config.show_download_window:
#             main_window = self.parent()
#             win = DownloadWindow(d)
#             main_window.download_windows[d.id] = win
#             win.show()
#             worker.progress_changed.connect(win.on_progress_changed)
#             worker.status_changed.connect(win.on_status_changed)
#             worker.log_updated.connect(win.on_log_updated)

#     def handle_finished(self, d):
#         self.download_finished.emit(d)
#         self.index += 1
#         self.start_next()





# def on_download_button_clicked(self, downloader=None):
    #     if not self.d or not self.d.url:
    #         self.show_information("Download Error", "Nothing to download", "Check your URL or click Retry.")
    #         return

    #     if isinstance(self.d, Video):
    #         d = self.d.clone()  # ✅ Full deep clone, reuse parsed streams/info
    #         d.update_param()
    #     else:
    #         d = copy.copy(self.d)
    #         d.update(d.url)     # ✅ Only normal HTTP downloads refresh info

    #     d.folder = config.download_folder

    #     selected_queue = widgets.combo3.currentText()

    #     if selected_queue and selected_queue != "None":
    #         d.in_queue = True
    #         d.queue_name = selected_queue
    #         d.queue_id = self.get_queue_id(selected_queue)
    #         d.status = config.Status.queued
    #         d.last_known_progress = 0
    #         d.last_known_size = 0

    #         if not isinstance(d, Video):
    #             d._segments = []

    #         # Assign queue position
    #         existing_positions = [
    #             item.queue_position for item in self.d_list
    #             if item.in_queue and item.queue_name == selected_queue
    #         ]
    #         d.queue_position = max(existing_positions, default=0) + 1
    #         d.id = len(self.d_list)

    #         self.d_list.append(d)
    #         setting.save_d_list(self.d_list)
    #         self.queue_update("populate_table", None)

    #         self.show_information("Added to Queue", f"{d.name}", "Start it from the Queues Dialog.")
    #         self.change_page(btn=None, btnName=None, idx=1)

    #     else:
    #         # Immediate download (not queued)
    #         r = self.start_download(d, downloader=downloader)
    #         if r not in ('error', 'cancelled', False):
    #             self.change_page(btn=None, btnName=None, idx=1)



    # def on_download_button_clicked(self, downloader=None):
    #     """Handle DownloadButton click event."""
    #     # Check if the download button is disabled
    #     if self.d.url == "":
    #         # Use QMessageBox to display the popup in PyQt
    #         msg = QMessageBox()
    #         msg.setIcon(QMessageBox.Warning)
    #         msg.setWindowTitle(self.tr('Download Error'))
    #         msg.setStyleSheet(self.get_msgbox_style("warning"))
    #         msg.setText(self.tr('Nothing to download'))
    #         msg.setInformativeText(self.tr('It might be a web page or an invalid URL link. Check your link or click "Retry".'))
    #         msg.setStandardButtons(QMessageBox.Ok)
    #         msg.exec()
    #         return
        

    #     # Get a copy of the current download item (self.d)
    #     d = copy.copy(self.d)

    #     # Set the folder for download
    #     d.folder = config.download_folder  # Ensure that config.download_folder is properly set

    #     # Start the download using the appropriate downloader
    #     r = self.start_download(d, downloader=downloader)

        
    #     if r not in ('error', 'cancelled', False):
    #         self.change_page(btn=None, btnName=None, idx=1)
            
    


# def run_aria2c_download(d, emitter=None):
#     log(f"[Aria2c] Starting: {d.name}")

#     d.status = Status.downloading
#     d._progress = 0
#     d.remaining_parts = 1
#     d.last_known_progress = 0

#     try:
#         aria2 = aria2c_manager.get_api()
#         added = aria2.add_uris([d.url], options={"dir": d.folder, "out": d.name})
#         d.aria_gid = added.gid
#         log(f"[Aria2c] GID: {d.aria_gid}")
#         d.remaining_parts = 1
#         d._downloaded = 0   
#         d._progress = 0
#         d.last_known_progress = 0

#         if emitter:
#             emitter.status_changed.emit("downloading")
#             emitter.progress_changed.emit(0)  # force update


#         while True:
#             download = aria2.get_download(d.aria_gid)
#             if download is None:
#                 log(f"[Aria2c] Download not found for GID: {d.aria_gid}")
#                 d.status = Status.error
#                 break

#             percent = int(download.progress)
#             d._progress = percent
#             d.last_known_progress = percent

#             d._total_size = int(download.total_length)
#             d._downloaded = int(download.completed_length)
#             d._speed = int(download.download_speed)

#             d.remaining_time = download.eta if download.eta != -1 else 0  # optional fallback

#             if emitter:
#                 emitter.progress_changed.emit(percent)
#                 emitter.log_updated.emit(f"⬇ {size_format(d.speed, '/s')} | Done: {size_format(d.downloaded)} / {size_format(d.total_size)}")

#             if download.is_complete:
#                 d.status = Status.completed
#                 log(f"[Aria2c] Completed: {d.name}")
#                 if emitter:
#                     emitter.progress_changed.emit(100)
#                     emitter.status_changed.emit("completed")
#                 delete_folder(d.temp_folder)
#                 notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
#                 break

#             elif download.is_removed:
#                 d.status = Status.error
#                 log(f"[Aria2c] Error or removed: {d.name}")
#                 if emitter:
#                     emitter.status_changed.emit("error")
#                 break

#             time.sleep(1)

#     except Exception as e:
#         d.status = Status.error
#         log(f"[Aria2c] Exception during download: {e}")
#         if emitter:
#             emitter.status_changed.emit("error")

#     finally:
#         if emitter:
#             emitter.log_updated.emit(f"[Aria2c] Done processing {d.name}")
#         log(f"[Aria2c] Done processing {d.name}")


# def run_aria2c_download(d, emitter=None):
#     """Download static files using aria2c.exe."""
#     d.status = config.Status.downloading
#     if emitter:
#         emitter.status_changed.emit("downloading")

#     log(f"[Aria2c] Starting: {d.name}")
#     d.q.log(f"[aria2c] Starting download: {d.name}")
#     d.remaining_parts = 1


#     # Reset progress info
#     d._downloaded = 0
#     d.remaining_parts = 1
#     d._progress = 0
#     d.last_known_progress = 0

#     cmd = [
#         config.aria2c_path,
#         "--file-allocation=none",
#         "--max-connection-per-server=5",
#         "--allow-overwrite=true",
#         "--summary-interval=1",
#         "--dir", d.folder,
#         "--out", d.name,
#         d.url
#     ]
    

#     process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
#     total_size = d.size or 1  # fallback to 1 to prevent zero division
#     downloaded = 0

#     try:
#         for line in process.stdout:
#             line = line.strip()
            
#             if emitter:
#                 emitter.log_updated.emit(line)
#             log(f"[aria2c] {line}")

#             # Try to extract progress
#             match = re.search(r'\((\d+)%\)', line)
#             if match:
#                 percent = int(match.group(1))
#                 d._progress = percent
#                 d.last_known_progress = percent
#                 if emitter:
#                     emitter.progress_changed.emit(percent)

#             # Optional: fallback progress extraction by parsing downloaded size
#             match2 = re.search(r'\[#\w+\s+([\d\.]+\w?B)/([\d\.]+\w?B)\(', line)
#             if match2:
#                 # Not parsed for d._downloaded currently
#                 pass

#         process.wait()

#         if process.returncode == 0:
#             log(f"[Aria2c] Completed: {d.name}")
#             d.status = config.Status.completed
#             d.remaining_parts = 0
#             d._progress = 100
#             d.last_known_progress = 100

#             if emitter:
#                 emitter.progress_changed.emit(100)
#                 emitter.status_changed.emit("completed")
            
#             notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')

#         else:
#             log(f"[Aria2c] Failed: {d.name}")
#             d.status = config.Status.error
#             if emitter:
#                 emitter.status_changed.emit("error")

#     except Exception as e:
#         log(f"[Aria2c] Error: {e}")
#         d.status = config.Status.error
#         if emitter:
#             emitter.status_changed.emit("error")

#     finally:
#         if emitter:
#             emitter.log_updated.emit(f"[Aria2c] Done processing {d.name}")
#         log(f"[Aria2c] Done processing {d.name}")





# # aria2c_manager.py
# # This script manages the aria2c download manager, providing functionality to start the RPC server,
# # pause, resume downloads, and match download GIDs.
# # This file is part of the application and is licensed under the MIT License.
# import os
# import subprocess
# import time
# import psutil
# import aria2p

# from modules.config import aria2c_path, sett_folder, aria2c_config
# from modules.utils import log
# from modules import config

# class Aria2cManager:
#     def __init__(self):
#         self.api = None
#         self.client = None

#         self.session_file = os.path.join(sett_folder, "aria2c.session")
#         self.initialized = False
#         os.makedirs(sett_folder, exist_ok=True)
#         if not os.path.exists(self.session_file):
#             with open(self.session_file, 'w') as f:
#                 pass

#         self._kill_existing_aria2c()
#         self._start_aria2c_with_session()
#         self._connect_api()

#     def _kill_existing_aria2c(self):
#         for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
#             try:
#                 if 'aria2c' in proc.info['name']:
#                     proc.terminate()
#                     proc.wait(timeout=2)
#                     log(f"[aria2c] Terminated existing process (PID {proc.pid})")
#             except Exception as e:
#                 log(f"[aria2c] Could not terminate aria2c (PID {proc.pid}): {e}")

#     def ensure_initialized(self):
#         """Only initialize if needed."""
#         if self.initialized:
#             return

#         if not os.path.exists(config.aria2c_path):
#             log("[aria2c] Executable missing. Skipping init.")
#             return  # Let the app decide what to do (main.py will prompt user)

#         self._init_aria2c()
#         self.initialized = True

#     def _start_aria2c_with_session(self):
#         cmd = [
#             config.aria2c_path,
#             "--enable-rpc",
#             "--rpc-listen-all=false",
#             f"--rpc-listen-port={aria2c_config['rpc_port']}",
#             "--rpc-allow-origin-all",
#             "--continue=true",
#             f"--save-session={self.session_file}",
#             f"--input-file={self.session_file}",
#             f"--save-session-interval={aria2c_config['save_interval']}",
#             f"--max-connection-per-server={aria2c_config['max_connections']}",
#             "--file-allocation=none"

#         ]
#         subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#         log("[aria2c] Started aria2c with session support")
#         time.sleep(1)

#     def _connect_api(self):
#         try:
#             self.client = aria2p.Client(host="http://localhost", port=6800, secret="")
#             self.api = aria2p.API(self.client)
#             log("[aria2c] RPC server connected.")
#         except Exception as e:
#             log(f"[aria2c] Failed to connect to RPC server: {e}")
#             self.api = None

#     def get_api(self):
#         if not self.api:
#             self._connect_api()
#         return self.api

#     def pause(self, gid):
#         try:
#             download = self.api.get_download(gid)
#             if download and not download.is_complete:
#                 download.pause()
#                 return True
#         except Exception as e:
#             log(f"[aria2c] Failed to pause GID#{gid}: {e}")
#         return False

#     def resume(self, gid):
#         try:
#             download = self.api.get_download(gid)
#             if download and not download.is_complete:
#                 download.resume()  # not `unpause()`, correct method is `resume()`
#                 return True
#         except Exception as e:
#             log(f"[aria2c] Failed to resume GID#{gid}: {e}")
#         return False

#     def remove(self, gid):
#         try:
#             download = self.api.get_download(gid)
#             if download:
#                 download.remove(force=True, files=True)
#                 return True
#         except Exception as e:
#             log(f"[aria2c] Failed to remove GID#{gid}: {e}")
#         return False

#     def force_save_session(self):
#         try:
#             if self.api:
#                 result = self.api.client.call("aria2.saveSession")
#                 log(f"[aria2c] Session save result: {result}")
#             else:
#                 log("[aria2c] Cannot save session. API is not available.")
#         except Exception as e:
#             log(f"[aria2c] Failed to save session: {e}")


# # Global instance
# aria2c_manager = Aria2cManager()



























################### aria2c for youtube ###########################################################
# def run_aria2c_video_audio_download(d, emitter=None):
#     log(f"[Aria2c] Starting: {d.name}")
#     d.status = Status.downloading
#     d._progress = 0
#     d.remaining_parts = 1
#     d.last_known_progress = 0

#     try:
#         aria2 = aria2c_manager.get_api()

#         # Use the selected stream from GUI
#         selected_stream = getattr(d, "selected_stream", None)
#         if selected_stream:
#             d.url = selected_stream.url
#             if selected_stream.height:
#                 d.name = validate_file_name(f"{d.name}_{selected_stream.height}p.mp4")
#             else:
#                 d.name = validate_file_name(f"{d.name}.mp4")

#         audio_is_present = bool(d.audio_url and d.audio_url != d.url)

#         # Submit video
#         added_video = aria2.add_uris([d.url], options={
#             "dir": d.folder,
#             "out": d.name,
#             "pause": "false",
#             "file-allocation": config.aria2c_config["file_allocation"],
#             "max-connection-per-server": config.aria2c_config["max_connections"],
#             "follow-torrent": "true" if config.aria2c_config["follow_torrent"] else "false",
#             "enable-dht": "true" if config.aria2c_config["enable_dht"] else "false",
#         })
#         d.aria_gid = added_video.gid
#         log(f"[Aria2c] Video GID assigned: {d.aria_gid}")

#         # Submit audio
#         if audio_is_present:
#             audio_out = os.path.basename(d.audio_file)
#             added_audio = aria2.add_uris([d.audio_url], options={
#                 "dir": d.folder,
#                 "out": audio_out,
#                 "pause": "false",
#                 "file-allocation": config.aria2c_config["file_allocation"],
#                 "max-connection-per-server": config.aria2c_config["max_connections"],
#             })
#             d.audio_gid = added_audio.gid
#             log(f"[Aria2c] Audio GID assigned: {d.audio_gid}")

#         if emitter:
#             emitter.status_changed.emit("downloading")
#             emitter.progress_changed.emit(0)

#         video_complete = False
#         audio_complete = not audio_is_present
#         last_progress = -1

#         while True:
#             try:
#                 v = aria2.get_download(d.aria_gid)
#                 video_complete = v.is_complete
#                 v_percent = int(v.progress)
#             except:
#                 v_percent = 0

#             d._downloaded = int(v.completed_length)
#             d.size = int(v.total_length) if v.total_length else 0
#             d._speed = int(v.download_speed)
#             d.remaining_time = v.eta if v.eta != -1 else 0

#             if audio_is_present:
#                 try:
#                     a = aria2.get_download(d.audio_gid)
#                     audio_complete = a.is_complete
#                     a_percent = int(a.progress)
#                 except:
#                     a_percent = 0
#             else:
#                 a_percent = 0

#             combined = (v_percent + a_percent) // (2 if audio_is_present else 1)
#             d._progress = combined
#             d.last_known_progress = combined

#             if emitter and combined != last_progress:
#                 emitter.progress_changed.emit(combined)
#                 emitter.log_updated.emit(
#                     f"⬇ {size_format(d.downloaded)} | Video: {v_percent}% | Audio: {a_percent if audio_is_present else '—'}%"
#                 )
#                 last_progress = combined

#             # When complete, delay slightly to ensure file flush
#             if video_complete and audio_complete:
#                 log(f"[Aria2c] Both video and audio completed for: {d.name}")

#                 video_path = os.path.join(d.folder, d.name)
#                 safe_name = os.path.splitext(d.name)[0]
#                 output_file = os.path.join(d.folder, f"{safe_name}.merged.mp4")

#                 # In-place check
#                 if output_file == video_path:
#                     output_file = os.path.join(d.folder, f"{safe_name}_final.mp4")

#                 # Wait for OS to flush files
#                 for path in [video_path, d.audio_file]:
#                     for _ in range(10):
#                         if os.path.exists(path) and os.path.getsize(path) > 1024:
#                             break
#                         log(f"[Aria2c] Waiting for file write completion: {path}")
#                         time.sleep(1)
#                     else:
#                         log(f"[Aria2c] ERROR: File not ready or too small: {path}")
#                         d.status = Status.error
#                         break

#                 d.status = Status.merging_audio
#                 loop = asyncio.new_event_loop()
#                 asyncio.set_event_loop(loop)
#                 error, output = loop.run_until_complete(
#                     async_merge_video_audio(video_path, d.audio_file, output_file, d)
#                 )

#                 if error:
#                     log(f"[Merge] FFmpeg merge failed: {output}")
#                     d.status = Status.error
#                     break

#                 try:
#                     if os.path.exists(d.target_file):
#                         os.remove(d.target_file)
#                     rename_file(output_file, d.target_file)
#                 except Exception as e:
#                     log(f"[Merge] Rename error: {e}")
#                     d.status = Status.error
#                     break

#                 d.delete_tempfiles()
#                 d.status = Status.completed
#                 log(f"[Aria2c] Download completed for: {d.name}")
#                 delete_folder(d.temp_folder)
#                 if emitter:
#                     emitter.status_changed.emit("completed")
#                     emitter.progress_changed.emit(100)
#                 notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
#                 break

#             if d.status == Status.cancelled:
#                 log(f"[Aria2c] Download cancelled: {d.name}")
#                 break

#             time.sleep(1)

#     except Exception as e:
#         d.status = Status.error
#         log(f"[Aria2c] Exception during download: {e}")
#         if emitter:
#             emitter.status_changed.emit("error")

#     finally:
#         if emitter:
#             emitter.log_updated.emit(f"[Aria2c] Done processing {d.name}")
#         log(f"[Aria2c] Done processing {d.name}")






# if d.engine in ["aria2", "aria2c"]:
    #     log(f"[brain] aria2c selected for: {d.name}")

    #     # Only re-extract if we have no pre-extracted video info
    #     if ("youtube.com" in d.url or "youtu.be" in d.url) and not getattr(d, "vid_info", None):
    #         log(f"[brain] Extracting stream info from YouTube URL for aria2c...")
    #         from modules.video import get_ytdl_options, extract_info_blocking, Stream
    #         ydl_opts = get_ytdl_options()
    #         vid_info = extract_info_blocking(d.url, ydl_opts)
    #         d.vid_info = vid_info
    #     elif getattr(d, "vid_info", None):
    #         log(f"[brain] Reusing existing vid_info for {d.name}")

    #     if getattr(d, "vid_info", None):
    #         from modules.video import Stream
    #         streams = [Stream(f) for f in d.vid_info.get("formats", [])]
    #         dash_streams = [s for s in streams if s.mediatype == 'dash']
    #         audio_streams = [s for s in streams if s.mediatype == 'audio']

    #         # --- Select user-requested format if valid ---
    #         selected_stream = getattr(d, "selected_stream", None)
    #         selected_dash = None

    #         if selected_stream:
    #             for s in dash_streams:
    #                 if (
    #                     s.format_id == selected_stream.format_id
    #                     and s.url
    #                     and "m3u8" not in s.url
    #                     and "mpd" not in s.url
    #                 ):
    #                     selected_dash = s
    #                     break

    #         if not selected_dash:
    #             selected_dash = next(
    #                 (s for s in dash_streams if s.url and "m3u8" not in s.url and "mpd" not in s.url),
    #                 None,
    #             )

    #         selected_audio = max(audio_streams, key=lambda s: s.quality, default=None)

    #         if not selected_dash or not selected_audio:
    #             log("[brain] Could not find valid dash/audio streams — falling back to yt-dlp.")
    #             run_ytdlp_download(d, emitter)
    #             return

    #         d.eff_url = selected_dash.url
    #         d.audio_url = selected_audio.url
    #         d.format_id = selected_dash.format_id
    #         d.audio_format_id = selected_audio.format_id

    #         # Sanitize title and embed quality label into name
    #         #base_title = d.vid_info.get("title", f"yt_video_{int(time.time())}")
    #         base_title = validate_file_name(d.vid_info.get("title"))
    #         #quality_label = selected_dash.resolution or selected_dash.quality
    #         d.name = f"{base_title}.mp4"

    #         # Set the url for aria2c to download
    #         d.url = d.eff_url

    #         run_aria2c_video_audio_download(d, emitter)
    #     else:
    #         log("[Aria2c] Running normal static file download")
    #         run_aria2c_download(d, emitter)
    #     return


    # if d.engine in ["aria2", "aria2c"]:
    #     log(f"[brain] aria2c selected for: {d.name}")

    #     # Extract if not already extracted
    #     if ("youtube.com" in d.url or "youtu.be" in d.url) and not getattr(d, "vid_info", None):
    #         log(f"[brain] Extracting stream info from YouTube URL for aria2c...")
    #         from modules.video import get_ytdl_options, extract_info_blocking, Stream
    #         ydl_opts = get_ytdl_options()
    #         vid_info = extract_info_blocking(d.url, ydl_opts)
    #         d.vid_info = vid_info
    #     elif getattr(d, "vid_info", None):
    #         log(f"[brain] Reusing existing vid_info for {d.name}")

    #     if getattr(d, "vid_info", None):
    #         from modules.video import Stream
    #         streams = [Stream(f) for f in d.vid_info.get("formats", [])]
    #         dash_streams = [s for s in streams if s.mediatype == 'dash']
    #         audio_streams = [s for s in streams if s.mediatype == 'audio']

    #         selected_stream = getattr(d, "selected_stream", None)
    #         selected_dash = None
    #         selected_audio = None

    #         if selected_stream:
    #             selected_dash = next((s for s in dash_streams if s.format_id == selected_stream.format_id), None)
    #             if selected_dash:
    #                 selected_audio = max(audio_streams, key=lambda s: s.quality, default=None)

    #         if not selected_dash:
    #             selected_dash = max(dash_streams, key=lambda s: s.quality, default=None)
    #         if not selected_audio:
    #             selected_audio = max(audio_streams, key=lambda s: s.quality, default=None)

    #         if not selected_dash or not selected_audio:
    #             log("[brain] Could not find valid dash/audio streams — falling back to yt-dlp.")
    #             run_ytdlp_download(d, emitter)
    #             return

    #         d.eff_url = selected_dash.url
    #         d.audio_url = selected_audio.url
    #         d.format_id = selected_dash.format_id
    #         d.audio_format_id = selected_audio.format_id

    #         # Set the download name and target
    #         clean_title = validate_file_name(d.vid_info.get("title"))
    #         d.name = f"{clean_title}.mp4"
    #         d.url = d.eff_url

    #         run_aria2c_video_audio_download(d, emitter)
    #     else:
    #         log("[Aria2c] Running normal static file download")
    #         run_aria2c_download(d, emitter)
    #     return













# def run(self):
    #     """Run the thread to process the video URL."""
    #     try:
    #         # Ensure youtube-dl is loaded
    #         if video.ytdl is None:
    #             log('youtube-dl module still loading, please wait')
    #             while not video.ytdl:
    #                 time.sleep(0.1)
    #         widgets.download_btn.setEnabled(False)
    #         widgets.playlist_btn.setEnabled(False)
    #         widgets_settings.monitor_clipboard_cb.setChecked(False)
    #         widgets.combo1.clear()
    #         widgets.combo2.clear()

    #         log(f"Extracting info for URL: {self.url}")
    #         change_cursor('busy')

    #         with video.ytdl.YoutubeDL(get_ytdl_options()) as ydl:
    #             info = ydl.extract_info(self.url, download=False, process=True)
    #             log('Media info:', info, log_level=3)

    #             if info.get('_type') == 'playlist' or 'entries' in info:
    #                 pl_info = list(info.get('entries', []))
    #                 playlist = []
    #                 for index, item in enumerate(pl_info):
    #                     url = item.get('url') or item.get('webpage_url') or item.get('id')
    #                     if url:
    #                         playlist.append(Video(url, vid_info=item))
    #                     # Emit progress as we process each playlist entry
    #                     self.progress.emit(int((index + 1) * 100 / len(pl_info)))
    #                 result = playlist
    #                 self.finished.emit(result)

    #             else:
    #                 # For a single video, update progress on extraction
    #                 result = Video(self.url, vid_info=None)
    #                 self.progress.emit(50)  # Just after extracting the info
    #                 time.sleep(1)  # Simulating some processing
    #                 self.progress.emit(100)  # Video info extraction complete
    #             self.finished.emit(result)
    #             change_cursor('normal')
    #             widgets.download_btn.setEnabled(True)
    #             widgets_settings.monitor_clipboard_cb.setChecked(True)

    #     except DownloadError as e:
    #         log('DownloadError:', e)
    #         popup(title="Timeout", msg="Please retry the download.", type_="warning")
    #         self.finished.emit(None)
    #     except ExtractorError as e:
    #         log('ExtractorError:', e)
    #         self.finished.emit(None)
    #     except Exception as e:
    #         log('Unexpected error:', e)
    #         self.finished.emit(None)