
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

from PySide6.QtCore import Qt,  QDateTime, QTime, QDate
from PySide6.QtWidgets import QCalendarWidget, QTimeEdit
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QPushButton, QHBoxLayout,  QDialog)

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


#####################################################################################