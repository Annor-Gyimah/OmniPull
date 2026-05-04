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

import os
import sys
from threading import Thread

from modules.utils import log
from modules import config
from modules.brain import brain
from modules.setting import load_d_list, save_queues, save_d_list
from modules.settings_manager import SettingsManager

from ui.queue_runner import QueueRunner
from ui.language_manager import LanguageManager
from ui.download_window import DownloadProgressDialog


from PySide6.QtGui import QIcon
from PySide6.QtCore import Slot, QTime, Qt
from PySide6.QtWidgets import (
    QDialog, QListWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QLineEdit, QCheckBox, QTimeEdit, QTabWidget, QWidget, QListWidgetItem, QTableWidgetItem, 
    QMessageBox, QStyledItemDelegate, QStyle, QSpinBox, QStyleOptionViewItem, QAbstractItemView
)


class NoFocusDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # Create a copy of the option to avoid modifying the original
        item_option = QStyleOptionViewItem(option)
        
        # Explicitly remove the Focus state
        if item_option.state & QStyle.State_HasFocus:
            item_option.state &= ~QStyle.State_HasFocus
            
        # Draw the item using the modified option
        super().paint(painter, item_option, index)

class QueueDialog(QDialog):
   
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Queues"))
        self.resize(820, 500)
        self.setMinimumSize(650, 400)

        self.settings_manager = SettingsManager()
        # self.translator = QTranslator()
        self.queues = self.settings_manager.load_queues()
        self.d_list = self.settings_manager.d_list
        self.current_queue_id = None
        self.main_window = parent
        self.active_queue_threads = []  # Track currently running downloads
        self.queue_processing = False  # whether the queue is currently running
        self.current_running_item = None  # the item currently downloading

        self.next_queue_index = 1

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ================= LEFT: QUEUE LIST =================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        

        self.left_title = QLabel(self.tr("Queues"))
        self.left_title.setObjectName("QueueListTitle")
        left_layout.addWidget(self.left_title)

        self.queue_list = QListWidget()
        self.queue_list.setItemDelegate(NoFocusDelegate())
        self.queue_list.currentItemChanged.connect(self._on_queue_selection_changed)
        left_layout.addWidget(self.queue_list, 1)

        left_btn_row = QHBoxLayout()
        self.btn_add_queue = QPushButton(self.tr("Add queue"))
        self.btn_delete_queue = QPushButton(self.tr("Delete"))
        left_btn_row.addWidget(self.btn_add_queue)
        left_btn_row.addWidget(self.btn_delete_queue)
        left_layout.addLayout(left_btn_row)

        main_layout.addWidget(left_widget, 1)

        # ================= RIGHT: QUEUE DETAILS =================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Header row: queue name label + start/stop buttons
        header_row = QHBoxLayout()
        self.lbl_current_queue = QLabel(self.tr("No queue selected"))
        self.lbl_current_queue.setObjectName("QueueHeaderLabel")

        header_row.addWidget(self.lbl_current_queue)
        header_row.addStretch()

        self.start_stop_queue_btn = QPushButton(self.tr("Start queue"))
        self.btn_close_qdialog = QPushButton(self.tr("Close"))
        self.start_stop_queue_btn.clicked.connect(self.toggle_queue_download)
        self.btn_close_qdialog.clicked.connect(self.save_and_close)
        header_row.addWidget(self.start_stop_queue_btn)
        header_row.addWidget(self.btn_close_qdialog)

        right_layout.addLayout(header_row)

        # Tab widget
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs, 1)

        # ------------- CONFIG TAB -------------
        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        config_layout.setContentsMargins(8, 8, 8, 8)
        config_layout.setSpacing(10)

        # Queue name row
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        self.name_label = QLabel(self.tr("Queue name:"))
        self.queue_name_edit = QLineEdit()
        self.queue_name_edit.setPlaceholderText(self.tr("Enter queue name"))
        

        name_row.addWidget(self.name_label)
        name_row.addWidget(self.queue_name_edit)
        config_layout.addLayout(name_row)

        # Scheduler row: enable + time on SAME row
        sched_row = QHBoxLayout()
        sched_row.setSpacing(6)

        self.chk_enable_scheduler = QCheckBox(self.tr("Enable scheduler"))
        self.chk_enable_scheduler.toggled.connect(self._update_scheduler_controls)

        sched_row.addWidget(self.chk_enable_scheduler)

        sched_row.addSpacing(10)
        self.lbl_auto_start_time = QLabel(self.tr("Auto start time:"))
        sched_row.addWidget(self.lbl_auto_start_time)

        self.time_auto_start = QTimeEdit()
        self.time_auto_start.setDisplayFormat("HH:mm")
        self.time_auto_start.setTime(QTime.currentTime())
        sched_row.addWidget(self.time_auto_start)

        sched_row.addStretch()

        config_layout.addLayout(sched_row)
        config_layout.addStretch()

        # Concurrent downloads row
        concurrent_row = QHBoxLayout()
        concurrent_row.setSpacing(6)
        self.lbl_concurrent = QLabel(self.tr("Max concurrent downloads:"))
        concurrent_row.addWidget(self.lbl_concurrent)
 
        self.spn_concurrent = QSpinBox()
        self.spn_concurrent.setMinimum(1)
        self.spn_concurrent.setMaximum(5)
        self.spn_concurrent.setValue(1)
        self.spn_concurrent.setFixedWidth(90)
        self.spn_concurrent.setToolTip(
            self.tr("How many items in this queue can download at the same time (1 = sequential)")
        )
        self.spn_concurrent.valueChanged.connect(self._on_concurrent_changed)
        concurrent_row.addWidget(self.spn_concurrent)
        concurrent_row.addStretch()
        config_layout.addLayout(concurrent_row)
 
        config_layout.addStretch()
 
        self.tabs.addTab(config_tab, self.tr("Configuration"))

        # ------------- ITEMS TAB -------------
        items_tab = QWidget()
        items_layout = QVBoxLayout(items_tab)
        items_layout.setContentsMargins(8, 8, 8, 8)
        items_layout.setSpacing(8)

        # ------------- ITEMS TAB -------------
        items_tab = QWidget()
        items_layout = QVBoxLayout(items_tab)
        items_layout.setContentsMargins(8, 8, 8, 8)
        items_layout.setSpacing(8)

        self.table_items = QTableWidget(0, 5)
        self.table_items.setHorizontalHeaderLabels(
            ["Pos", "Name", "Size", "Status", "Delete"]
        )

        # Behavior Fixes
        self.table_items.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_items.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_items.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_items.setItemDelegate(NoFocusDelegate()) # Keep UI consistent

        self.table_items.verticalHeader().setVisible(False)
        self.table_items.setShowGrid(False)
        self.table_items.horizontalHeader().setStretchLastSection(True)
        self.table_items.horizontalHeader().setDefaultSectionSize(150)

        self.table_items.setStyleSheet("""
            QTableWidget {
                outline: 0;
            }
            QTableWidget::item:selected {
                /* This ensures no border is drawn on the individual cells when the row is selected */
                border: 0px;
                background-color: #7C4DFF;
                color: #FFFFFF; /* Ensures text is always readable */
            }
        """)

        items_layout.addWidget(self.table_items, 1)

        # Move up / Move down
        move_row = QHBoxLayout()
        move_row.addStretch()
        self.btn_move_up = QPushButton(self.tr("Move up"))
        self.btn_move_down = QPushButton(self.tr("Move down"))
        self.btn_move_up.clicked.connect(self.move_selected_row_up)
        self.btn_move_down.clicked.connect(self.move_selected_row_down)
        move_row.addWidget(self.btn_move_up)
        move_row.addWidget(self.btn_move_down)
        items_layout.addLayout(move_row)

        self.tabs.addTab(items_tab, self.tr("Items"))

        main_layout.addWidget(right_widget, 3)

        # --------- HOOK UP BUTTONS ---------
        self.btn_add_queue.clicked.connect(self.add_queue)
        self.btn_delete_queue.clicked.connect(self.delete_selected_queue)

        self.queue_list.currentRowChanged.connect(self.update_queue_config)

        self.d_list = load_d_list()
        self.populate_queue_list()
        self.queue_list.currentRowChanged.connect(
            lambda index: self.on_queue_selected(self.queue_list.currentItem(), None)
        )
        self.queue_name_edit.textChanged.connect(self._on_queue_name_edited)

        # create initial queue so it's not empty
        # self.add_queue()

        # initial scheduler state
        self._update_scheduler_controls(self.chk_enable_scheduler.isChecked())
        self.current_language = config.lang
        self.lang_manager = LanguageManager()
        self.lang_manager.apply_language(self.current_language)
        self.retrans()

    # ========== QUEUE HANDLERS ==========

    def showEvent(self, event):
        """Sync button text with the actual running state when dialog opens."""
        super().showEvent(event)
        self._sync_button_state()
 
    def _sync_button_state(self):
        """Set start/stop button text based on whether the current queue is running."""
        queue_id = self.current_queue_id
        if not queue_id:
            return
        is_running = self.main_window.running_queues.get(queue_id, False)
        if is_running:
            self.start_stop_queue_btn.setText(self.tr("Stop Queue"))
        else:
            self.start_stop_queue_btn.setText(self.tr("Start Queue"))

    

    def _on_queue_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Update right-side UI when the selected queue changes."""
        if current is None:
            self.lbl_current_queue.setText("No queue selected")
            self.queue_name_edit.blockSignals(True)
            self.queue_name_edit.clear()
            self.queue_name_edit.blockSignals(False)
            return

        name = current.text()
        self.lbl_current_queue.setText(self.tr("Queue: %s") % name) 

        # sync line edit with selected queue name, but avoid feedback loop
        self.queue_name_edit.blockSignals(True)
        self.queue_name_edit.setText(name)
        self.queue_name_edit.blockSignals(False)
        self._sync_button_state()

    def _on_queue_name_edited(self, text: str):
        """When the queue name line edit changes, update the list item text."""

        row = self.queue_list.currentRow()
        if row < 0 or row >= len(self.queues):
            return

        new_name = text.strip()
        if not new_name:
            return
        
        current_item = self.queue_list.currentItem()
        if current_item is None:
            return
        current_item.setText(text if text else "Unnamed queue")
        self.lbl_current_queue.setText(self.tr("Queue: %s") % current_item.text()) 

        # Prevent duplicate names
        for i, q in enumerate(self.queues):
            if i != row and q["name"].strip().lower() == new_name.lower():
                QMessageBox.warning(self, self.tr("Duplicate Name"), self.tr("A queue with this name already exists."))
                self.queue_name_edit.setText(self.queues[row]["name"])
                return
        
        old_name = self.queues[row]["name"]
        old_queue_id = self.get_queue_id(old_name)
        new_queue_id = self.get_queue_id(new_name)

        # Update the queue object
        self.queues[row]["name"] = new_name
        self.queues[row]["id"] = new_queue_id

        # Update the UI
        self.queue_list.item(row).setText(new_name)

        # Update the downloads that had the old queue ID
        for d in self.d_list:
            if d.in_queue and d.queue_id == old_queue_id:
                d.queue_id = new_queue_id
                d.queue_name = new_name

        self.current_queue = new_name
        self.current_queue_id = new_queue_id

        
        self.settings_manager.queues = self.queues
        self.settings_manager.d_list = self.d_list
        self.settings_manager.save_settings()
    
    def get_queue_id(self, name: str) -> str:
        import hashlib

        return hashlib.md5(name.encode()).hexdigest()[:8]


    def move_selected_row_up(self):
        selected_row = self.table_items.currentRow()
        if selected_row <= 0:
            return  # Can't move up the first item

        items = self.get_sorted_queue_items()
        if selected_row >= len(items):
            return

        # Swap positions
        items[selected_row].queue_position, items[selected_row - 1].queue_position = \
            items[selected_row - 1].queue_position, items[selected_row].queue_position

        save_d_list(self.d_list)
        self.populate_queue_items()
        self.table_items.selectRow(selected_row - 1)

    def move_selected_row_down(self):
        selected_row = self.table_items.currentRow()
        items = self.get_sorted_queue_items()
        
        if selected_row < 0 or selected_row >= len(items) - 1:
            return  # Can't move down the last item

        # Swap positions
        items[selected_row].queue_position, items[selected_row + 1].queue_position = \
            items[selected_row + 1].queue_position, items[selected_row].queue_position

        save_d_list(self.d_list)
        self.populate_queue_items()
        self.table_items.selectRow(selected_row + 1)

    def get_sorted_queue_items(self):
        return sorted(
            [d for d in self.d_list if d.in_queue and d.queue_id == self.current_queue_id],
            key=lambda d: d.queue_position
        )

    
    
    def add_queue(self):
        """Create a new queue with a default name 'Queue N' and select it."""
        name = f"Queue"
        self.next_queue_index = 1
        existing_names = [self.queue_list.item(i).text() for i in range(self.queue_list.count())]
        
        while name in existing_names:
            self.next_queue_index += 1
            name = f"{name} {self.next_queue_index}"
        
        new_id = self.get_queue_id(name)

        item = QListWidgetItem(name)
        self.queue_list.addItem(item)
        self.queue_list.setCurrentItem(item)
        self.queue_list.editItem(item)

        self.queues.append({
            "id": new_id,
            "name": name,
            "schedule": None,
            "items": []
        })


    def delete_selected_queue(self):
        row = self.queue_list.currentRow()
        if row < 0 or row >= len(self.queues):
            return
        
        # Get the queue being deleted
        deleted_queue = self.queues[row]
        deleted_queue_id = deleted_queue.get("id")

       # Remove the queue from the list and UI
        del self.queues[row]
        self.queue_list.takeItem(row)
        
        if self.queue_list.count() == 0:
            self.lbl_current_queue.setText(self.tr("No queue selected"))
            self.queue_name_edit.clear()
        else:
            new_row = min(row, self.queue_list.count() - 1)
            self.queue_list.setCurrentRow(new_row)
        
        # Save updated queue list
        save_queues(self.queues)

        # Remove downloads assigned to the deleted queue (or unassign them)
        for d in self.d_list:
            if d.queue_id == deleted_queue_id:
                d.in_queue = False
                d.queue_id = None
                d.queue_name = ""
                d.queue_position = 0
    
        self.settings_manager.d_list = self.d_list
        self.settings_manager.save_settings()

        # Refresh queue combo box in main UI (optional, but best UX)
        if hasattr(self.parent(), "update_queue_combobox"):
            self.parent().update_queue_combobox()

        # Clear or update config panel
        if self.queue_list.count() > 0:
            self.queue_list.setCurrentRow(0)
            self.update_queue_config(0)
        else:
            self.queue_name_edit.clear()
            self.chk_enable_scheduler.setChecked(False)
            self.time_auto_start.setTime(QTime(0, 0))

        QMessageBox.information(self, self.tr("Queue Deleted"), self.tr("Queue was successfully deleted."))
    



    def populate_queue_list(self):
        self.queue_list.clear()
        for q in self.queues:
            self.queue_list.addItem(q["name"])
            item = self.queue_list.item(self.queue_list.count() - 1)
            item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        # Force-select the first queue to trigger population
        if self.queue_list.count() > 0:
            self.queue_list.setCurrentRow(0)
            self.on_queue_selected(self.queue_list.currentItem(), None)

            self.update_queue_config(0)  # Reflect data in config tab


    def update_queue_config(self, index):
        if index < 0 or index >= len(self.queues):
            return
 
        q = self.queues[index]
        self.queue_name_edit.setText(q.get("name", ""))
 
        sched = q.get("schedule")
        if sched:
            self.chk_enable_scheduler.setChecked(True)
            h, m = sched
            self.time_auto_start.setTime(QTime(h, m))
        else:
            self.chk_enable_scheduler.setChecked(False)
            self.time_auto_start.setTime(QTime(0, 0))
 
        self.spn_concurrent.blockSignals(True)
        self.spn_concurrent.setValue(int(q.get("max_concurrent", 1)))
        self.spn_concurrent.blockSignals(False)



    def save_and_close(self):
        row = self.queue_list.currentRow()
        if row < 0 or row >= len(self.queues):
            return
        
        for i, q in enumerate(self.queues):
            if i == row:
                q["name"] = self.queue_list.item(i).text()
                q["schedule"] = (
                    self.time_auto_start.time().hour(),
                    self.time_auto_start.time().minute()
                ) if self.chk_enable_scheduler.isChecked() else None
                q["max_concurrent"] = self.spn_concurrent.value()

        
        self.settings_manager.queues = self.queues
        self.settings_manager.save_settings()
        config.main_window_q.put(("queue_list", ''))
        self.close()
    
    def closeEvent(self, event):
        self.save_and_close()
        super().closeEvent(event)



    def on_queue_selected(self, current, previous):
        if not current:
            return

        queue_name = current.text()
        self.current_queue = queue_name
        self.current_queue_id = self.get_queue_id(queue_name)

        # Load queue metadata
        for q in self.queues:
            if q["name"] == queue_name:
                self.queue_name_edit.setText(q["name"])
                break

        self.populate_queue_items()

        # Update button label according to the queue's state
        if self.main_window.running_queues.get(self.current_queue_id, False):
            self.start_stop_queue_btn.setText(self.tr("Stop Queue"))
            self.btn_delete_queue.setEnabled(False)
            self.queue_name_edit.setEnabled(False)
            self.chk_enable_scheduler.setEnabled(False)
            self.time_auto_start.setEnabled(False)

            # Disable move + concurrent controls
            self.btn_move_up.setEnabled(False)
            self.btn_move_down.setEnabled(False)
            self.spn_concurrent.setEnabled(False)
 
        else:
            self.start_stop_queue_btn.setText(self.tr("Start Queue"))
            self.btn_delete_queue.setEnabled(True)
            self.queue_name_edit.setEnabled(True)
            self.chk_enable_scheduler.setEnabled(True)
            self.time_auto_start.setEnabled(True)
 
            # Enable move + concurrent controls
            self.btn_move_up.setEnabled(True)
            self.btn_move_down.setEnabled(True)
            self.spn_concurrent.setEnabled(True)

        self._sync_button_state()

    def populate_queue_items(self):
        self.table_items.setRowCount(0)

        # Get relevant downloads
        items = [
            d for d in self.d_list
            if d.in_queue and d.queue_id == self.current_queue_id
        ]

        # Sort by queue position
        items.sort(key=lambda d: d.queue_position)

        self.table_items.setRowCount(len(items))

        for row, d in enumerate(items):

             # Create the item
            pos_item = QTableWidgetItem(str(d.queue_position))
            # Set the alignment to Center
            pos_item.setTextAlignment(Qt.AlignCenter)
            # Add to table
            self.table_items.setItem(row, 0, pos_item)

            # Repeat for other text columns
            name_item = QTableWidgetItem(d.name)
            name_item.setTextAlignment(Qt.AlignCenter) 
            self.table_items.setItem(row, 1, name_item)

            size_item = QTableWidgetItem(f"{d.size/1024/1024:.2f} MB")
            size_item.setTextAlignment(Qt.AlignCenter)
            self.table_items.setItem(row, 2, size_item)

            status_item = QTableWidgetItem(str(d.status))
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table_items.setItem(row, 3, status_item)


            # ... inside your loop ...
            btn = QPushButton()
            btn.setIcon(QIcon.fromTheme("edit-delete"))
            btn.setFixedSize(48, 28)
            btn.setStyleSheet("""
                QPushButton {
                    /* A very subtle grey border makes the button shape visible */
                    border: 1px solid rgba(150, 150, 150, 50);
                    border-radius: 4px;
                    background-color: rgba(200, 200, 200, 20); 
                }
                QPushButton:hover {
                    /* Turns red on hover to indicate a destructive action */
                    background-color: #ff5252;
                    border: 1px solid #e53935;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                }
                QPushButton:disabled {
                    background-color: transparent;
                    border: none;
                    opacity: 0.5;
                }
            """)

            # Create a container to handle centering
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.addWidget(btn)
            layout.setAlignment(Qt.AlignCenter)  # Centers the button inside the layout
            layout.setContentsMargins(0, 0, 0, 0) # Removes padding
            container.setLayout(layout)

            if d.status == config.Status.downloading:
                btn.setEnabled(False)

            btn.clicked.connect(lambda _, item=d: self.delete_queue_item(item))

            # Set the container as the cell widget instead of the button directly
            self.table_items.setCellWidget(row, 4, container)

    

    def toggle_queue_download(self):
        queue_id = self.current_queue_id
        if not self.main_window.running_queues.get(queue_id, False):
            self.main_window.running_queues[queue_id] = True
            self.start_stop_queue_btn.setText(self.tr("Stop Queue"))
            self.start_queue_downloads()
        else:
            self.main_window.running_queues[queue_id] = False
            self.start_stop_queue_btn.setText(self.tr("Start Queue"))
            self.stop_queue_downloads()



    def start_queue_downloads(self):
        if self.queue_processing:
            return

        all_items = self.get_sorted_queue_items()

        if not all_items:
            QMessageBox.warning(self, self.tr("Empty Queue"), self.tr("This queue has no downloads to start."))
            self.start_stop_queue_btn.setText(self.tr("Start Queue"))
            return

        
        items_to_download = [d for d in all_items if d.status in (config.Status.queued, config.Status.pending)]

        if not items_to_download:
            QMessageBox.warning(self, self.tr("Nothing to Download"), self.tr("All items are completed or failed. Nothing to download."))
            self.start_stop_queue_btn.setText(self.tr("Start Queue"))
            return

        self.queue_processing = True
        queue_id = self.current_queue_id

        # self.queue_runner = QueueRunner(queue_id, items_to_download, parent=self.main_window)
        current_q_config = next(
            (q for q in self.queues if q.get("id") == queue_id), {}
        )
        max_concurrent = int(current_q_config.get("max_concurrent", 1))
 
        self.queue_runner = QueueRunner(
            queue_id, items_to_download,
            max_concurrent=max_concurrent,
            parent=self.main_window,
        )
        self.queue_runner.download_started.connect(self.on_first_download_started)
        self.queue_runner.download_finished.connect(self.on_download_finished)
        self.queue_runner.download_failed.connect(self.on_download_failed)
        self.queue_runner.download_finished.connect(self.on_queue_item_finished)
        self.queue_runner.queue_finished.connect(self.on_queue_finished)
        # Ensure main window receives thread references before the runner starts
        self.queue_runner.thread_created.connect(self.main_window.register_queue_background_thread)
        self.queue_runner.start()
        self.main_window.running_queues[queue_id] = True
        self.start_stop_queue_btn.setText(self.tr("Stop Queue"))

        # self.accept()
    



    def stop_queue_downloads(self):
        queue_id = self.current_queue_id
        self.queue_processing = False
        self.main_window.running_queues[queue_id] = False

        for d in self.d_list:
            if d.in_queue and d.queue_id == queue_id:
                if d.status in (config.Status.downloading, config.Status.pending, config.Status.queued):
                    d.status = config.Status.queued

        
        self.settings_manager.save_d_list(self.d_list)
        self.populate_queue_items()

        # If a runner is active, terminate its thread safely
        if hasattr(self, "queue_runner") and self.queue_runner:
            self.queue_runner.paused = True  # acts like a soft kill
        
        self.start_stop_queue_btn.setText(self.tr("Start Queue"))
        # self.accept()
    

    
    def on_download_finished(self, d):
        log(f"[main] Download finished: {d.name}", log_level=1)
        self.populate_queue_items()
        self.settings_manager.save_d_list(self.d_list)
        self.on_queue_item_finished(d)  

    @Slot(str)
    def on_queue_finished(self, queue_id):
        if queue_id == self.current_queue_id:
            self.queue_processing = False
            self.main_window.running_queues[self.current_queue_id] = False
            self.start_stop_queue_btn.setText(self.tr("Start Queue"))
            self._sync_button_state()

        

    @Slot(object)
    def on_first_download_started(self, d):
        if self.isVisible():
            self.accept()  



    def on_download_failed(self, d):
        log(f"[main] Download failed or cancelled: {d.name}", log_level=1)
        self.populate_queue_items()
        self.settings_manager.save_d_list(self.d_list)
        self.on_queue_item_finished(d)  # <- call this here in on_download_finished()
        



    def run_download_for_item(self, d):
        main_window = self.parent()
        d.status = config.Status.queued  # optional, or just leave as-is

        # Update item to get segments, headers
        d.update(d.url)
        segments = d.segments  # <-- This line ensures segments are initialized

        if d.engine not in ['aria2c', 'aria2', 'yt-dlp']:
            os.makedirs(d.temp_folder, exist_ok=True)
        
        



        # Show window if enabled
        if config.show_download_window:
            main_window.download_windows[d.id] = DownloadProgressDialog(d)
            main_window.download_windows[d.id].show()

        # Start the actual download thread
        Thread(target=brain, daemon=True, args=(d,)).start()

        self.populate_queue_items()
        self.settings_manager.save_d_list(self.d_list)
        self.active_queue_threads.append(d)
        

    def on_queue_item_finished(self, d):
        self.current_running_item = None
        self.populate_queue_items()
        self.settings_manager.save_d_list(self.d_list)


    def delete_queue_item(self, item):
        dqi1, dqi2 = self.tr('Are you sure want to delete'), self.tr('from this queue?')
        confirm = QMessageBox.question(
            self,
            self.tr("Confirm Delete"),
            f"{dqi1} {item.name} {dqi2}",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.d_list.remove(item)
            # setting.save_d_list(self.d_list)
            self.settings_manager.d_list = self.d_list
            self.settings_manager.save_settings()
            self.populate_queue_items()
            if hasattr(self.parent(), "populate_table"):
                self.parent().populate_table()



    def _update_scheduler_controls(self, enabled: bool):
        self.time_auto_start.setEnabled(enabled)

    def _on_concurrent_changed(self, value: int):
        """Immediately persist the concurrent-downloads setting for the current queue."""
        row = self.queue_list.currentRow()
        if 0 <= row < len(self.queues):
            self.queues[row]["max_concurrent"] = value
            self.settings_manager.queues = self.queues
            self.settings_manager.save_settings()

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)


    def retrans(self):
        self.setWindowTitle(self.tr("Queues"))
        self.start_stop_queue_btn.setText(self.tr('Start Queue'))
        self.btn_add_queue.setText(self.tr("Add Queue"))
        self.btn_delete_queue.setText(self.tr("Delete"))
        self.btn_close_qdialog.setText(self.tr("Close"))
        self.btn_move_up.setText(self.tr("Move Up"))
        self.btn_move_down.setText(self.tr("Move Down"))
        self.tabs.setTabText(0, self.tr("Configuration"))
        self.tabs.setTabText(1, self.tr("Items"))
        self.lbl_current_queue.setText(self.tr("Queue: "))
        self.chk_enable_scheduler.setText(self.tr("Enable scheduler"))
        self.lbl_auto_start_time.setText(self.tr("Auto start time:"))
        self.name_label.setText(self.tr("Queue name:"))
        self.lbl_concurrent.setText(self.tr("Max concurrent downloads:"))
        
