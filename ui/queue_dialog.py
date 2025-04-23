# Page 1 - Queue Dialog (Improved)
from PySide6.QtWidgets import (
    QDialog, QListWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QLineEdit, QSpinBox, QCheckBox, QTimeEdit, QTabWidget, QWidget, QFrame, QGroupBox,
    QListWidgetItem, QTableWidgetItem,
)
from PySide6.QtCore import Qt, QTime

from modules import setting, config, brain
from threading import Thread
from ui.download_window import DownloadWindow
import os

class QueueDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Queues")
        self.setMinimumSize(800, 500)
        self.queues = setting.load_queues()

        self.running_queues = {}  # key: queue_id, value: True/False

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
        """)

        # self.queues = []  # or use a dict if storing config too: self.queues = {}

        


        main_layout = QHBoxLayout(self)
        

        # Left: Queue List
        self.queue_list = QListWidget()
        self.queue_list.addItems(["Main", "addl"])
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

        general_box = QGroupBox("General")
        general_layout = QVBoxLayout()

        name_layout = QHBoxLayout()
        name_label = QLabel("Queue name is:")
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

        self.auto_stop = QCheckBox("Automatic Stop")

        general_layout.addLayout(name_layout)
        general_layout.addLayout(max_layout)
        general_layout.addWidget(self.auto_stop)
        general_box.setLayout(general_layout)

        scheduler_box = QGroupBox("Scheduler")
        scheduler_layout = QVBoxLayout()
        self.enable_sched = QCheckBox("Enable Scheduler")

        time_layout = QHBoxLayout()
        time_label = QLabel("Auto Start Time")
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
        self.queue_items_table.setHorizontalHeaderLabels(["Pos", "Name", "Size", "Status"])
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
        self.up_button = QPushButton("↑ Move Up")
        self.down_button = QPushButton("↓ Move Down")
        self.up_button.clicked.connect(self.move_selected_row_up)
        self.down_button.clicked.connect(self.move_selected_row_down)
        self.move_buttons_layout.addWidget(self.up_button)
        self.move_buttons_layout.addWidget(self.down_button)

        
        self.items_tab_layout.addWidget(self.queue_items_table)
        self.items_tab_layout.addLayout(self.move_buttons_layout)

        self.tabs.addTab(self.config_tab, "Config")
        self.tabs.addTab(self.items_tab, "Items")

        # Bottom buttons
        self.start_stop_queue_btn = QPushButton("Start Queue")
        self.start_stop_queue_btn.clicked.connect(self.toggle_queue_download)
        self.close_btn = QPushButton("Close")
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
        # Auto-generate unique name
        base_name = "Queue"
        count = 1
        existing_names = [self.queue_list.item(i).text() for i in range(self.queue_list.count())]
        new_name = f"{base_name} {count}"

        while new_name in existing_names:
            count += 1
            new_name = f"{base_name} {count}"

        # Add to list widget
        new_item = QListWidgetItem(new_name)
        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.queue_list.addItem(new_item)
        self.queue_list.setCurrentItem(new_item)
        self.queue_list.editItem(new_item)

        # Track internally
        self.queues.append({
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

        # Remove from the internal list and the UI list
        del self.queues[row]
        self.queue_list.takeItem(row)

        # Update the config tab display
        if self.queue_list.count() > 0:
            self.queue_list.setCurrentRow(0)
            self.update_queue_config(0)
        else:
            self.name_edit.clear()
            self.max_spin.setValue(1)
            self.auto_stop.setChecked(False)
            self.enable_sched.setChecked(False)
            self.start_time.setTime(QTime(0, 0))

        

    def populate_queue_list(self):
        self.queue_list.clear()
        for q in self.queues:
            self.queue_list.addItem(q["name"])

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

        setting.save_queues(self.queues)
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
        if self.running_queues.get(self.current_queue_id, False):
            self.start_stop_queue_btn.setText("Stop Queue")
        else:
            self.start_stop_queue_btn.setText("Start Queue")


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

    
        

    def toggle_queue_download(self):
        queue_id = self.current_queue_id
        if not self.running_queues.get(queue_id, False):
            self.running_queues[queue_id] = True
            self.start_stop_queue_btn.setText("Stop Queue")
            self.start_queue_downloads()
        else:
            self.running_queues[queue_id] = False
            self.start_stop_queue_btn.setText("Start Queue")
            self.stop_queue_downloads()

        # if not self.queue_running:
        #     self.queue_running = True
        #     self.start_stop_queue_btn.setText("Stop Queue")
        #     self.start_queue_downloads()
        # else:
        #     self.queue_running = False
        #     self.start_stop_queue_btn.setText("Start Queue")
        #     self.stop_queue_downloads()

    

    def start_queue_downloads(self):
        config.queue_dialog = self  # inside QueueDialog before starting queue
        if self.queue_processing:
            return  # Already running

        self.queue_processing = True
        self.active_queue_threads = []

        items = self.get_sorted_queue_items()
        if not items:
            return

        # Start only the first item
        first_item = items[0]
        self.current_running_item = first_item
        self.run_download_for_item(first_item)



    def stop_queue_downloads(self):
        for d in self.active_queue_threads:
            d.status = config.Status.cancelled
        self.active_queue_threads = []
        setting.save_d_list(self.d_list)
        self.populate_queue_items()


    def run_download_for_item(self, d):
        main_window = self.parent()
        d.status = config.Status.queued  # optional, or just leave as-is

        # Update item to get segments, headers
        d.update(d.url)
        segments = d.segments  # <-- This line ensures segments are initialized
        os.makedirs(d.temp_folder, exist_ok=True)
        



        # Show window if enabled
        if config.show_download_window:
            main_window.download_windows[d.id] = DownloadWindow(d)
            main_window.download_windows[d.id].show()

        # Start the actual download thread
        Thread(target=brain.brain, daemon=True, args=(d,)).start()

        self.populate_queue_items()
        setting.save_d_list(self.d_list)
        self.active_queue_threads.append(d)
        self.accept()

    def on_queue_item_finished(self, d):
        self.current_running_item = None
        self.populate_queue_items()
        setting.save_d_list(self.d_list)

        # Start next item in queue
        remaining = self.get_sorted_queue_items()
        next_item = None
        for item in remaining:
            if item.status == config.Status.queued:
                next_item = item
                break

        if next_item:
            self.current_running_item = next_item
            self.run_download_for_item(next_item)
        else:
            self.queue_processing = False
            self.running_queues[self.current_queue_id] = False
            self.start_stop_queue_btn.setText("Start Queue")


