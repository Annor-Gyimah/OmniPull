

from PySide6.QtWidgets import (QVBoxLayout, QLabel, QPushButton, QHBoxLayout,  QDialog, 
QComboBox, QDateTimeEdit)
from PySide6.QtCore import Qt,  QDateTime, QTime, QDate
from PySide6.QtWidgets import QCalendarWidget, QTimeEdit


# Redesigned ScheduleDialog with modern, sleek UI look
class ScheduleDialog(QDialog):
    def __init__(self, msg='', parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Schedule Download'))
        self.resize(420, 200)
        self.setStyleSheet("""
            QDialog {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
                border-radius: 14px;
            }
            QLabel {
                color: white;
                font-size: 12px;
            }
            QComboBox {
                background-color: rgba(28, 28, 30, 0.85);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 5px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(20, 25, 20, 0.95);
                border: 1px solid rgba(60, 200, 120, 0.25);
                selection-background-color: #2DE099;
                color: white;
            }
            QPushButton {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                ); 
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33d47c;
            }
            QPushButton#CancelBtn {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
            }
            QPushButton#CancelBtn:hover {
                background-color: #666;
            }
            QDateTimeEdit {
                background-color: rgba(28, 28, 30, 0.85);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 6px;
            }

            QDateTimeEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left: 1px solid rgba(255, 255, 255, 0.05);
            }

            QDateTimeEdit QAbstractItemView {
                background-color: rgba(20, 25, 20, 0.95);
                border: 1px solid rgba(60, 200, 120, 0.25);
                selection-background-color: #2DE099;
                color: white;
            }

            QCalendarWidget QAbstractItemView {
                background-color: rgba(20, 25, 20, 0.95);
                color: white;
                selection-background-color: #2DE099;
                selection-color: black;
                border: 1px solid rgba(60, 200, 120, 0.25);
            }

            QTimeEdit {
                background-color: rgba(28, 28, 30, 0.85);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 6px;
            }


        """)
        

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self.message_label = QLabel(msg)
        layout.addWidget(self.message_label)

        # row_layout = QHBoxLayout()
        # row_layout.setSpacing(10)

        # self.hour_label = QLabel(self.tr("Hours:"))
        # row_layout.addWidget(self.hour_label)
        # self.hours_combo = QComboBox(self)
        # self.hours_combo.addItems([str(i) for i in range(1, 13)])
        # row_layout.addWidget(self.hours_combo)

        # self.minute_label = QLabel(self.tr("Minutes:"))
        # row_layout.addWidget(self.minute_label)
        # self.minutes_combo = QComboBox(self)
        # self.minutes_combo.addItems([f"{i:02d}" for i in range(0, 60)])
        # row_layout.addWidget(self.minutes_combo)

        # layout.addLayout(row_layout)

        # am_pm_layout = QHBoxLayout()
        # am_pm_layout.setAlignment(Qt.AlignCenter)
        # self.am_pm_combo = QComboBox(self)
        # self.am_pm_combo.addItems(['AM', 'PM'])
        # am_pm_layout.addWidget(self.am_pm_combo)
        # layout.addLayout(am_pm_layout)

        # dateti = QHBoxLayout()
        # self.datetime_edit = QDateTimeEdit(self)
        # self.datetime_edit.setCalendarPopup(True)
        # self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        # dateti.addWidget(self.datetime_edit)
        # layout.addLayout(dateti)

        self.calendar = QCalendarWidget(self)
        self.calendar.setGridVisible(True)
        layout.addWidget(self.calendar)

        self.time_edit = QTimeEdit(self)
        self.time_edit.setDisplayFormat("hh:mm AP")  # or "HH:mm" for 24-hour
        self.time_edit.setTime(QTime.currentTime())
        layout.addWidget(self.time_edit)

        # Label showing selected date & time
        self.datetime_label = QLabel(self)
        self.update_datetime_label()
        layout.addWidget(self.datetime_label)

        # Connect calendar & time to update label
        self.calendar.selectionChanged.connect(self.update_datetime_label)
        self.calendar.selectionChanged.connect(self.restrict_past_time_if_today)
        self.time_edit.timeChanged.connect(self.update_datetime_label)
        


        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        button_layout.setAlignment(Qt.AlignRight)

        self.ok_button = QPushButton(self.tr('Ok'), self)
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton(self.tr('Cancel'), self)
        self.cancel_button.setObjectName("CancelBtn")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # self.hours_combo.setCurrentIndex(0)
        # self.minutes_combo.setCurrentIndex(0)
        # self.am_pm_combo.setCurrentIndex(0)

        today = QDate.currentDate()
        self.calendar.setMinimumDate(today)



    def update_datetime_label(self):
        selected_date = self.calendar.selectedDate()
        selected_time = self.time_edit.time()
        formatted = f"Selected: {selected_date.toString('yyyy-MM-dd')} {selected_time.toString('hh:mm AP')}"
        self.datetime_label.setText(formatted)

    

    def restrict_past_time_if_today(self):
        selected_date = self.calendar.selectedDate()
        today = QDate.currentDate()
        current_time = QTime.currentTime()

        if selected_date == today:
            self.time_edit.setMinimumTime(current_time)
        else:
            self.time_edit.setMinimumTime(QTime(0, 0))  # Reset to allow all times

    

    @property
    def response(self):
        selected_date = self.calendar.selectedDate()
        selected_time = self.time_edit.time()
        combined_dt = QDateTime(selected_date, selected_time)

        date_str = combined_dt.date().toString("yyyy-MM-dd")
        time_str = combined_dt.time().toString("HH:mm:ss")

        print(f"Date and Time selected: {date_str}, {time_str}")
        return date_str, time_str


    # @property
    # def response(self):
    #     h = int(self.hours_combo.currentText())
    #     m = int(self.minutes_combo.currentText())
    #     am_pm = self.am_pm_combo.currentText()

    #     # print(f'FROM AD {self.datetime_edit}')

    #     if am_pm == 'PM' and h != 12:
    #         h += 12
    #     elif am_pm == 'AM' and h == 12:
    #         h = 0

    #     return h, m
