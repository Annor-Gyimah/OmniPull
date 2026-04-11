
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


from PySide6.QtCore import QDateTime, QTime, QDate
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCalendarWidget, QTimeEdit, QLabel, QPushButton)


class ScheduleDialog(QDialog):

    def __init__(self, msg='', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Schedule download")
        # self.setObjectName("ScheduleDialog")
        self.resize(380, 420)
        self.setMinimumSize(340, 360)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Calendar
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        main_layout.addWidget(self.calendar, 1)

        # Time selector (like a spinbox for time)
        time_row = QHBoxLayout()
        time_row.setSpacing(6)

        time_label = QLabel("Time:")
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime.currentTime())

        time_row.addWidget(time_label)
        time_row.addWidget(self.time_edit)
        time_row.addStretch()

        main_layout.addLayout(time_row)

        # Summary label
        self.summary_label = QLabel()
        self.summary_label.setObjectName("ScheduleSummaryLabel")
        self.summary_label.setWordWrap(True)
        main_layout.addWidget(self.summary_label)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_ok.setDefault(True)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)
        main_layout.addLayout(btn_row)

        # Connections
        self.calendar.selectionChanged.connect(self._update_summary)
        self.time_edit.timeChanged.connect(self._update_summary)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        self._update_summary()

    def _update_summary(self):
        dt = self.selected_datetime()
        self.summary_label.setText(
            f"Selected date and time is: {dt.toString('dddd, dd MMM yyyy  HH:mm')}"
        )

    def selected_datetime(self) -> QDateTime:
        """Return combined date+time as QDateTime."""
        d = self.calendar.selectedDate()
        t = self.time_edit.time()
        return QDateTime(d, t)
    

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
        return date_str, time_str
