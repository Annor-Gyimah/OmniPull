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
from modules import setting, config, brain
from modules.settings_manager import SettingsManager

from ui.queue_runner import QueueRunner
from ui.download_window import DownloadWindow


from PySide6.QtGui import QIcon
from PySide6.QtCore import Slot, QTime, Qt, QCoreApplication, QTranslator
from PySide6.QtWidgets import (
    QDialog, QListWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QLineEdit, QSpinBox, QCheckBox, QTimeEdit, QTabWidget, QWidget, QFrame, QGroupBox,
    QListWidgetItem, QTableWidgetItem, QMessageBox, QStyledItemDelegate, QStyle
)

class NoFocusDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if option.state & QStyle.State_HasFocus:
            option.state = option.state ^ QStyle.State_HasFocus
        super().paint(painter, option, index)

class QueueDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Queues")
        self.setMinimumSize(800, 500)
        # self.queues = setting.load_queues()
        self.settings_manager = SettingsManager()
        self.queues = self.settings_manager.load_queues()
        self.d_list = self.settings_manager.d_list


        # self.main_window.running_queues = {}  # key: queue_id, value: True/False
        # if self.queues:
        #     first_queue = self.queues[0]
        #     self.current_queue_id = first_queue.get("id")
        #     self.populate_queue_items()
        # else:
        #     self.current_queue_id = None
        self.translator = QTranslator()



        self.main_window = parent

        self.active_queue_threads = []  # Track currently running downloads

        self.queue_processing = False  # whether the queue is currently running
        self.current_running_item = None  # the item currently downloading


        
        self.setStyleSheet("""
            QDialog {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                );
                border-radius: 16px;
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
            QLineEdit, QSpinBox, QTimeEdit {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: transparent;
                padding: 6px 12px;
                margin-right: 1px;
                color: white;
            }
            QTabBar::tab:selected {
                background: #005c4b;
                border-radius: 4px;
            }
            QGroupBox {
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 10px;
                margin-top: 20px;
            }
            QGroupBox:title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 10px;
                color: #9eeedc;
                font-weight: bold;
            }
            
                           
            QListWidget {
            background-color: transparent;
            color: white;
            font-size: 14px;
            border: none;
            }

            QListWidget::item {
                padding: 10px;
                height: 32px;
            }

            QListWidget::item:hover {
                background-color: rgba(111, 255, 176, 0.08);
                color: #88ffaa;
            }

            QListWidget::item:selected {
                background-color: rgba(45, 224, 153, 0.1);
                color: #6FFFB0;
                padding-left: 6px;
                margin: 0px;
                border: none;
            }
                           
            QToolTip {
                color: white;
                background-color: #444444;
                border: 1px solid white;
                padding: 4px;
                border-radius: 4px;
            }
        """)

        # self.queues = []  # or use a dict if storing config too: self.queues = {}

        


        main_layout = QHBoxLayout(self)
        

        # Left: Queue List
        self.queue_list = QListWidget()
        self.queue_list.setItemDelegate(NoFocusDelegate())
        self.queue_list.addItems(["Main", "Main2"])
        self.queue_list.setMaximumWidth(100)

        left_buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(58, 58)
        self.add_button.clicked.connect(self.create_new_queue)
        self.delete_button = QPushButton("🗑")
        self.delete_button.clicked.connect(self.delete_selected_queue)
        self.delete_button.setFixedSize(58, 58)
        left_buttons_layout.addWidget(self.add_button)
        left_buttons_layout.addWidget(self.delete_button)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.queue_list)
        left_layout.addLayout(left_buttons_layout)

        left_frame = QFrame()
        left_frame.setLayout(left_layout)
        left_frame.setFixedWidth(160)
        left_frame.setStyleSheet("background-color: #121212;")

        # Right: Tabs
        self.tabs = QTabWidget()

        # Config Tab
        self.config_tab = QWidget()
        config_layout = QVBoxLayout(self.config_tab)

        general_box = QGroupBox(self.tr("General"))
        general_layout = QVBoxLayout()

        name_layout = QHBoxLayout()
        name_label = QLabel(self.tr("Queue name is:"))
        self.name_edit = QLineEdit("Main")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)

        max_layout = QHBoxLayout()
        max_label = QLabel("Max concurrent download")
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 10)
        self.max_spin.setValue(2)
        max_layout.addWidget(max_label)
        max_layout.addWidget(self.max_spin)

        self.auto_stop = QCheckBox(self.tr("Automatic Stop"))

        general_layout.addLayout(name_layout)
        general_layout.addLayout(max_layout)
        general_layout.addWidget(self.auto_stop)
        general_box.setLayout(general_layout)

        scheduler_box = QGroupBox(self.tr("Scheduler"))
        scheduler_layout = QVBoxLayout()
        self.enable_sched = QCheckBox(self.tr("Enable Scheduler"))

        time_layout = QHBoxLayout()
        time_label = QLabel(self.tr("Auto Start Time"))
        self.start_time = QTimeEdit(QTime(0, 0))
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.start_time)

        scheduler_layout.addWidget(self.enable_sched)
        scheduler_layout.addLayout(time_layout)
        scheduler_box.setLayout(scheduler_layout)

        config_layout.addWidget(general_box)
        config_layout.addWidget(scheduler_box)

        # Items Tab
        


        # Items Tab (empty placeholder for now)
        self.items_tab = QWidget()
        self.items_tab_layout = QVBoxLayout()
        self.items_tab.setLayout(self.items_tab_layout)

        self.queue_items_table = QTableWidget()
        self.queue_items_table.setColumnCount(5)
        self.queue_items_table.setHorizontalHeaderLabels([self.tr("Pos"), self.tr("Name"), self.tr("Size"), self.tr("Status"), self.tr("Delete")])

        # Optional: Set consistent column widths
        self.queue_items_table.setColumnWidth(0, 40)   # Queue position
        self.queue_items_table.setColumnWidth(1, 100)  # Name
        self.queue_items_table.setColumnWidth(2, 100)  # Size
        self.queue_items_table.setColumnWidth(3, 100)  # Status
        self.queue_items_table.setColumnWidth(4, 20)   # Delete button
        
        self.queue_items_table.verticalHeader().setVisible(False)
        self.queue_items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.queue_items_table.setAlternatingRowColors(True)
        self.queue_items_table.setShowGrid(False)
        self.queue_items_table.horizontalHeader().setStretchLastSection(True)

        self.queue_items_table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(15, 25, 20, 0.6);
                color: white;
                font-size: 13px;
                border: 1px solid rgba(0, 255, 180, 0.2);
                gridline-color: rgba(255, 255, 255, 0.08);
            }
            QHeaderView::section {
                background-color: rgba(0, 255, 180, 0.1);
                padding: 6px;
                border: none;
                color: #9eeedc;
            }
            QTableWidget::item:selected {
                background-color: rgba(0, 255, 180, 0.2);
            }
        """)


        self.move_buttons_layout = QHBoxLayout()
        movu, movd = self.tr('Move Up'), self.tr('Move Down')
        self.up_button = QPushButton(f"↑ {movu}")
        self.down_button = QPushButton(f"↓ {movd}")
        self.up_button.clicked.connect(self.move_selected_row_up)
        self.down_button.clicked.connect(self.move_selected_row_down)
        self.move_buttons_layout.addWidget(self.up_button)
        self.move_buttons_layout.addWidget(self.down_button)

        
        self.items_tab_layout.addWidget(self.queue_items_table)
        self.items_tab_layout.addLayout(self.move_buttons_layout)

        self.tabs.addTab(self.config_tab, self.tr("Config"))
        self.tabs.addTab(self.items_tab, self.tr("Items"))

        # Bottom buttons
        self.start_stop_queue_btn = QPushButton(self.tr("Start Queue"))
        self.start_stop_queue_btn.clicked.connect(self.toggle_queue_download)
        self.close_btn = QPushButton(self.tr("Close"))
        self.close_btn.clicked.connect(self.save_and_close)


        bottom_btns = QHBoxLayout()
        bottom_btns.addStretch()
        bottom_btns.addWidget(self.start_stop_queue_btn)
        bottom_btns.addWidget(self.close_btn)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.tabs)
        right_layout.addLayout(bottom_btns)

        main_layout.addWidget(left_frame)
        main_layout.addLayout(right_layout)

        self.setLayout(main_layout)
        self.close_btn.clicked.connect(self.close)
        self.queue_list.currentRowChanged.connect(self.update_queue_config)
        
        self.d_list = setting.load_d_list()
        self.populate_queue_list()
        self.queue_list.currentRowChanged.connect(
            lambda index: self.on_queue_selected(self.queue_list.currentItem(), None)
        )
        self.name_edit.textChanged.connect(self.on_name_edit_changed)
        self.queue_list.itemChanged.connect(self.on_queue_name_edited)

        self.current_language = config.lang
        self.apply_language(self.current_language)


    

    def on_name_edit_changed(self, text):
        row = self.queue_list.currentRow()
        if row < 0 or row >= len(self.queues):
            return

        new_name = text.strip()
        if not new_name:
            return

        # Prevent duplicate names
        for i, q in enumerate(self.queues):
            if i != row and q["name"].strip().lower() == new_name.lower():
                QMessageBox.warning(self, self.tr("Duplicate Name"), self.tr("A queue with this name already exists."))
                self.name_edit.setText(self.queues[row]["name"])
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

        # setting.save_queues(self.queues)
        # setting.save_d_list(self.d_list)
        self.settings_manager.queues = self.queues
        self.settings_manager.d_list = self.d_list
        self.settings_manager.save_settings()

        # self.populate_queue_list()
        # self.populate_queue_items()


    def on_queue_name_edited(self, item):
        row = self.queue_list.row(item)
        new_name = item.text().strip()

        if row < 0 or row >= len(self.queues):
            return

        for i, q in enumerate(self.queues):
            if i != row and q["name"].strip().lower() == new_name.lower():
                oqne1, oqne2 = self.tr('A queue named'), self.tr('already exists.')
                QMessageBox.warning(self, self.tr("Duplicate Name"), f"{oqne1} '{new_name}' {oqne2}")
                item.setText(self.queues[row]["name"])
                return

        old_name = self.queues[row]["name"]
        old_queue_id = self.get_queue_id(old_name)
        new_queue_id = self.get_queue_id(new_name)

        self.queues[row]["name"] = new_name
        self.queues[row]["id"] = new_queue_id
        self.name_edit.setText(new_name)
        self.current_queue = new_name
        self.current_queue_id = new_queue_id

        for d in self.d_list:
            if d.in_queue and d.queue_id == old_queue_id:
                d.queue_id = new_queue_id
                d.queue_name = new_name

        # setting.save_queues(self.queues)
        # setting.save_d_list(self.d_list)

        self.settings_manager.queues = self.queues
        self.settings_manager.d_list = self.d_list
        self.settings_manager.save_settings()

        # self.populate_queue_list()
        # self.populate_queue_items()



        
    
    def move_selected_row_up(self):
        selected_row = self.queue_items_table.currentRow()
        if selected_row <= 0:
            return  # Can't move up the first item

        items = self.get_sorted_queue_items()
        if selected_row >= len(items):
            return

        # Swap positions
        items[selected_row].queue_position, items[selected_row - 1].queue_position = \
            items[selected_row - 1].queue_position, items[selected_row].queue_position

        setting.save_d_list(self.d_list)
        self.populate_queue_items()
        self.queue_items_table.selectRow(selected_row - 1)

    def move_selected_row_down(self):
        selected_row = self.queue_items_table.currentRow()
        items = self.get_sorted_queue_items()
        
        if selected_row < 0 or selected_row >= len(items) - 1:
            return  # Can't move down the last item

        # Swap positions
        items[selected_row].queue_position, items[selected_row + 1].queue_position = \
            items[selected_row + 1].queue_position, items[selected_row].queue_position

        setting.save_d_list(self.d_list)
        self.populate_queue_items()
        self.queue_items_table.selectRow(selected_row + 1)


    def get_sorted_queue_items(self):
        return sorted(
            [d for d in self.d_list if d.in_queue and d.queue_id == self.current_queue_id],
            key=lambda d: d.queue_position
        )


    def create_new_queue(self):
        base_name = "Queue"
        count = 1
        existing_names = [self.queue_list.item(i).text() for i in range(self.queue_list.count())]
        new_name = f"{base_name} {count}"

        while new_name in existing_names:
            count += 1
            new_name = f"{base_name} {count}"

        new_id = self.get_queue_id(new_name)

        new_item = QListWidgetItem(new_name)
        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.queue_list.addItem(new_item)
        self.queue_list.setCurrentItem(new_item)
        self.queue_list.editItem(new_item)

        self.queues.append({
            "id": new_id,
            "name": new_name,
            "max_concurrent": 1,
            "auto_stop": False,
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

        # ✅ Remove the queue from the list and UI
        del self.queues[row]
        self.queue_list.takeItem(row)

        # ✅ Save updated queue list
        setting.save_queues(self.queues)

        # ✅ Remove downloads assigned to the deleted queue (or unassign them)
        for d in self.d_list:
            if d.queue_id == deleted_queue_id:
                d.in_queue = False
                d.queue_id = None
                d.queue_name = ""
                d.queue_position = 0
        # setting.save_d_list(self.d_list)
        self.settings_manager.d_list = self.d_list
        self.settings_manager.save_settings()

        # ✅ Refresh queue combo box in main UI (optional, but best UX)
        if hasattr(self.parent(), "update_queue_combobox"):
            self.parent().update_queue_combobox()

        # ✅ Clear or update config panel
        if self.queue_list.count() > 0:
            self.queue_list.setCurrentRow(0)
            self.update_queue_config(0)
        else:
            self.name_edit.clear()
            self.max_spin.setValue(1)
            self.auto_stop.setChecked(False)
            self.enable_sched.setChecked(False)
            self.start_time.setTime(QTime(0, 0))

        QMessageBox.information(self, self.tr("Queue Deleted"), self.tr("Queue was successfully deleted."))

    def populate_queue_list(self):
        self.queue_list.clear()
        for q in self.queues:
            self.queue_list.addItem(q["name"])
            item = self.queue_list.item(self.queue_list.count() - 1)
            item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        # ✅ Force-select the first queue to trigger population
        if self.queue_list.count() > 0:
            self.queue_list.setCurrentRow(0)
            self.on_queue_selected(self.queue_list.currentItem(), None)

            self.update_queue_config(0)  # Reflect data in config tab

    def update_queue_config(self, index):
        if index < 0 or index >= len(self.queues):
            return

        q = self.queues[index]
        self.name_edit.setText(q.get("name", ""))
        self.max_spin.setValue(q.get("max_concurrent", 1))
        self.auto_stop.setChecked(q.get("auto_stop", False))

        sched = q.get("schedule")
        if sched:
            self.enable_sched.setChecked(True)
            h, m = sched
            self.start_time.setTime(QTime(h, m))
        else:
            self.enable_sched.setChecked(False)
            self.start_time.setTime(QTime(0, 0))

    
    def save_and_close(self):
        row = self.queue_list.currentRow()
        if row < 0 or row >= len(self.queues):
            return
        
        for i, q in enumerate(self.queues):
            if i == row:
                q["name"] = self.queue_list.item(i).text()
                q["max_concurrent"] = self.max_spin.value()
                q["auto_stop"] = self.auto_stop.isChecked()
                q["schedule"] = (
                    self.start_time.time().hour(),
                    self.start_time.time().minute()
                ) if self.enable_sched.isChecked() else None

        # setting.save_queues(self.queues)
        self.settings_manager.queues = self.queues
        self.settings_manager.save_settings()
        config.main_window_q.put(("queue_list", ''))
        self.close()

    def get_queue_id(self, name: str) -> str:
        import hashlib

        return hashlib.md5(name.encode()).hexdigest()[:8]
    
    

    def on_queue_selected(self, current, previous):
        if not current:
            return

        queue_name = current.text()
        self.current_queue = queue_name
        self.current_queue_id = self.get_queue_id(queue_name)

        # Load queue metadata
        for q in self.queues:
            if q["name"] == queue_name:
                self.name_edit.setText(q["name"])
                # self.max_spin(q.get("max_concurrent", 1))
                # self.auto_stop(q.get("auto_stop", False))
                break

        self.populate_queue_items()

        # Update button label according to the queue's state
        if self.main_window.running_queues.get(self.current_queue_id, False):
            self.start_stop_queue_btn.setText(self.tr("Stop Queue"))
            self.delete_button.setEnabled(False)
            self.name_edit.setEnabled(False)
            self.max_spin.setEnabled(False)
            self.auto_stop.setEnabled(False)
            self.enable_sched.setEnabled(False)
            self.start_time.setEnabled(False)

            # 🚫 Disable move controls
            self.up_button.setEnabled(False)
            self.down_button.setEnabled(False)

        else:
            self.start_stop_queue_btn.setText(self.tr("Start Queue"))
            self.delete_button.setEnabled(True)
            self.name_edit.setEnabled(True)
            self.max_spin.setEnabled(True)
            self.auto_stop.setEnabled(True)
            self.enable_sched.setEnabled(True)
            self.start_time.setEnabled(True)

            # ✅ Enable move controls
            self.up_button.setEnabled(True)
            self.down_button.setEnabled(True)

    
    def populate_queue_items(self):
        self.queue_items_table.setRowCount(0)

        # Get relevant downloads
        items = [
            d for d in self.d_list
            if d.in_queue and d.queue_id == self.current_queue_id
        ]

        # Sort by queue position
        items.sort(key=lambda d: d.queue_position)

        self.queue_items_table.setRowCount(len(items))

        for row, d in enumerate(items):
            self.queue_items_table.setItem(row, 0, QTableWidgetItem(str(d.queue_position)))
            self.queue_items_table.setItem(row, 1, QTableWidgetItem(d.name))
            self.queue_items_table.setItem(row, 2, QTableWidgetItem(f"{d.size/1024/1024:.2f} MB"))
            self.queue_items_table.setItem(row, 3, QTableWidgetItem(str(d.status)))

            btn = QPushButton()
            btn.setIcon(QIcon.fromTheme("edit-delete"))
            btn.setFixedSize(48, 28)
            btn.setStyleSheet("background-color: transparent;")
            btn.setToolTip("Delete this item")

            if d.status == config.Status.downloading:
                btn.setEnabled(False)

            btn.clicked.connect(lambda _, item=d: self.delete_queue_item(item))
            self.queue_items_table.setCellWidget(row, 4, btn)


                
    
        

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

        # 🔥 NEW: Filter only items that are queued
        items_to_download = [d for d in all_items if d.status in (config.Status.queued, config.Status.pending)]

        if not items_to_download:
            QMessageBox.warning(self, self.tr("Nothing to Download"), self.tr("All items are completed or failed. Nothing to download."))
            self.start_stop_queue_btn.setText(self.tr("Start Queue"))
            return

        self.queue_processing = True
        queue_id = self.current_queue_id

        self.queue_runner = QueueRunner(queue_id, items_to_download, parent=self.main_window)
        self.queue_runner.download_started.connect(self.on_first_download_started)
        self.queue_runner.download_finished.connect(self.on_download_finished)
        self.queue_runner.download_failed.connect(self.on_download_failed)
        self.queue_runner.download_finished.connect(self.on_queue_item_finished)
        self.queue_runner.queue_finished.connect(self.on_queue_finished)
        self.queue_runner.start()

        self.main_window.running_queues[queue_id] = True
        self.start_stop_queue_btn.setText(self.tr("Stop Queue"))

        self.accept()

    def stop_queue_downloads(self):
        queue_id = self.current_queue_id
        self.queue_processing = False
        self.main_window.running_queues[queue_id] = False

        for d in self.d_list:
            if d.in_queue and d.queue_id == queue_id:
                if d.status in (config.Status.downloading, config.Status.pending, config.Status.queued):
                    d.status = config.Status.queued

        # setting.save_d_list(self.d_list)
        self.settings_manager.save_d_list(self.d_list)
        self.populate_queue_items()

        # If a runner is active, terminate its thread safely
        if hasattr(self, "queue_runner") and self.queue_runner:
            self.queue_runner.paused = True  # acts like a soft kill
        self.accept()

        

    


    # Example slot methods:
    def on_download_finished(self, d):
        log(f"[main] Download finished: {d.name}", log_level=1)
        self.populate_queue_items()
        self.settings_manager.save_d_list(self.d_list)
        # setting.save_d_list(self.d_list)
        self.on_queue_item_finished(d)  # <- call this here in on_download_finished()

    @Slot(str)
    def on_queue_finished(self, queue_id):
        if queue_id == self.current_queue_id:
            self.queue_processing = False
            self.main_window.running_queues[self.current_queue_id] = False
            self.start_stop_queue_btn.setText(self.tr("Start Queue"))


        

    @Slot(object)
    def on_first_download_started(self, d):
        if self.isVisible():
            self.accept()  # ✅ This will close the dialog gracefully



    def on_download_failed(self, d):
        log(f"[main] Download failed or cancelled: {d.name}", log_level=1)
        self.populate_queue_items()
        # setting.save_d_list(self.d_list)
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
        # os.makedirs(d.temp_folder, exist_ok=True)
        



        # Show window if enabled
        if config.show_download_window:
            main_window.download_windows[d.id] = DownloadWindow(d)
            main_window.download_windows[d.id].show()

        # Start the actual download thread
        Thread(target=brain.brain, daemon=True, args=(d,)).start()

        self.populate_queue_items()
        # setting.save_d_list(self.d_list)
        self.settings_manager.save_d_list(self.d_list)
        self.active_queue_threads.append(d)
        

    def on_queue_item_finished(self, d):
        self.current_running_item = None
        self.populate_queue_items()
        # setting.save_d_list(self.d_list)
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

    
    def resource_path2(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)


    def apply_language(self, language):
        QCoreApplication.instance().removeTranslator(self.translator)

        file_map = {
            "French": "app_fr.qm",
            "Spanish": "app_es.qm",
            "Chinese": "app_zh.qm",
            "Korean": "app_ko.qm",
            "Japanese": "app_ja.qm",
            "English": "app_en.qm",
        }

        if language in file_map:
            qm_path = self.resource_path2(f"../modules/translations/{file_map[language]}")
            if self.translator.load(qm_path):
                QCoreApplication.instance().installTranslator(self.translator)
                
            else:
                log(f"[Language] Failed to load {qm_path}", log_level=1)

       

        self.retrans()

    def retrans(self):
        self.setWindowTitle("Queues")
        self.start_stop_queue_btn.setText(self.tr('Start Queue'))




# def on_queue_name_edited(self, item):
#     row = self.queue_list.row(item)
#     new_name = item.text().strip()

#     if row >= 0 and row < len(self.queues):
#         # Prevent duplicate names
#         for i, q in enumerate(self.queues):
#             if i != row and q["name"].strip().lower() == new_name.lower():
#                 QMessageBox.warning(self, "Duplicate Name", f"A queue named '{new_name}' already exists.")
#                 item.setText(self.queues[row]["name"])  # revert name
#                 return

#         old_name = self.queues[row]["name"]
#         queue_id = self.queues[row].get("id")

#         # Update queue data
#         self.queues[row]["name"] = new_name
#         self.name_edit.setText(new_name)
#         self.current_queue = new_name
#         self.current_queue_id = queue_id

#         # Update all download items with matching queue_id
#         print(queue_id)
#         for d in self.d_list:
#             if d.queue_id == queue_id:
#                 d.queue = new_name
#                 d.queue_name = new_name

#         setting.save_queues(self.queues)
#         setting.save_d_list(self.d_list)

# def delete_selected_queue(self):
#     row = self.queue_list.currentRow()
#     if row < 0 or row >= len(self.queues):
#         return

#     # Remove from the internal list and the UI list
#     del self.queues[row]
#     self.queue_list.takeItem(row)

#     # Update the config tab display
#     if self.queue_list.count() > 0:
#         self.queue_list.setCurrentRow(0)
#         self.update_queue_config(0)
#     else:
#         self.name_edit.clear()
#         self.max_spin.setValue(1)
#         self.auto_stop.setChecked(False)
#         self.enable_sched.setChecked(False)
#         self.start_time.setTime(QTime(0, 0))

# def populate_queue_items(self):
#     self.queue_items_table.setRowCount(0)

#     # Get relevant downloads
#     items = [
#         d for d in self.d_list
#         if d.in_queue and d.queue_id == self.current_queue_id
#     ]

#     # Sort by queue position
#     items.sort(key=lambda d: d.queue_position)

#     self.queue_items_table.setRowCount(len(items))
#     btn = QPushButton("🗑")
#     btn.setFixedSize(30, 25)
#     btn.setStyleSheet("color: red; font-weight: bold;")
#     btn.clicked.connect(lambda _, row=row, item=item: self.delete_queue_item(item))
#     self.queue_items_table.setCellWidget(row, column_index, btn)



#     for row, d in enumerate(items):
#         self.queue_items_table.setItem(row, 0, QTableWidgetItem(str(d.queue_position)))
#         self.queue_items_table.setItem(row, 1, QTableWidgetItem(d.name))
#         self.queue_items_table.setItem(row, 2, QTableWidgetItem(f"{d.size/1024/1024:.2f} MB"))
#         self.queue_items_table.setItem(row, 3, QTableWidgetItem(str(d.status)))


# def start_queue_downloads(self):
#     if self.queue_processing:
#         return

#     self.queue_processing = True
#     queue_id = self.current_queue_id
#     items = self.get_sorted_queue_items()
#     all_items = self.get_sorted_queue_items()
#     if not items:
#         QMessageBox.warning(self, "Empty Queue", "This queue has no downloads to start.")
#         self.start_stop_queue_btn.setText("Start Queue")
#         return 
    
#     # 🔥 NEW: Filter only items that are queued
#     items_to_download = [d for d in all_items if d.status in (config.Status.queued, config.Status.pending)]

#     if not items_to_download:
#         QMessageBox.warning(self, "Nothing to Download", "All items are completed or failed. Nothing to download.")
#         return

#     self.queue_runner = QueueRunner(queue_id, items, parent=self.main_window)
#     self.queue_runner.download_started.connect(self.on_first_download_started)
#     self.queue_runner.download_finished.connect(self.on_download_finished)
#     self.queue_runner.download_failed.connect(self.on_download_failed)   
#     self.queue_runner.download_finished.connect(self.on_queue_item_finished)
#     self.queue_runner.queue_finished.connect(self.on_queue_finished)
#     self.queue_runner.start()

#     self.main_window.running_queues[queue_id] = True
#     self.start_stop_queue_btn.setText("Stop Queue")

#     self.accept()  # ✅ Closes the dialog right after queue starts

# def run_download_with_qthread(self, d):
#         self.download_thread = QThread()
#         self.download_worker = DownloadWorker(d)

#         self.download_worker.moveToThread(self.download_thread)
#         self.download_thread.started.connect(self.download_worker.run)


#         main_window = self.parent()
#         win = None
#         if config.show_download_window:
#             win = DownloadWindow(d)
#             main_window.download_windows[d.id] = win
#             win.show()

#         # Only connect signals if window is created
#         if win:
#             self.download_worker.progress_changed.connect(win.on_progress_changed)
#             self.download_worker.status_changed.connect(win.on_status_changed)
#             self.download_worker.log_updated.connect(win.on_log_updated)


#         # Connect signals back to main GUI thread
#         self.download_worker.finished.connect(self.on_download_finished)
#         self.download_worker.failed.connect(self.on_download_failed)

#         self.download_worker.finished.connect(self.download_thread.quit)
#         self.download_worker.failed.connect(self.download_thread.quit)
#         self.download_worker.finished.connect(self.download_worker.deleteLater)
#         self.download_worker.failed.connect(self.download_worker.deleteLater)
#         self.download_thread.finished.connect(self.download_thread.deleteLater)


#         self.download_thread.start()



# # class DownloadWorker(QObject):
# #     finished = Signal(object)
# #     failed = Signal(object)

#     progress_changed = Signal(float)
#     status_changed = Signal(str)
#     log_updated = Signal(str)

#     def __init__(self, download_item):
#         super().__init__()
#         self.d = download_item

#     @Slot()
#     def run(self):
#         try:
#             print(f"[worker] Starting download for: {self.d.name}")
#             self.d.update(self.d.url)  # ensure segments are initialized
#             os.makedirs(self.d.temp_folder, exist_ok=True)
#             brain.brain(self.d)

#             if self.d.status == config.Status.cancelled:
#                 print(f"[worker] Download cancelled: {self.d.name}")
#                 self.failed.emit(self.d)
#             else:
#                 print(f"[worker] Download completed: {self.d.name}")
#                 self.finished.emit(self.d)

#         except Exception as e:
#             print(f"[worker] Exception: {e}")
#             self.failed.emit(self.d)

