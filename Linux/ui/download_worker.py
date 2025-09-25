
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

import time

from modules import brain, config
from PySide6.QtCore import QObject, Signal, Slot, QTimer



class DownloadWorker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    progress_changed = Signal(float)
    status_changed = Signal(str)
    log_updated = Signal(str)

    TIMEOUT_SECONDS = 60  # No progress for 60s → timeout

    def __init__(self, d):
        super().__init__()
        self.d = d
        self.last_progress_time = time.time()
        self.last_gui_update = 0  # ✅ For throttling GUI updates
        self.timeout_timer = QTimer()
        self.timeout_timer.setInterval(5000)
        self.timeout_timer.timeout.connect(self.check_timeout)

    @Slot()
    def run(self):
        from modules.brain import set_signal_emitter, brain

        set_signal_emitter(self)
        self.status_changed.emit("starting")

        try:
            self.d.update(self.d.url)
            brain(self.d, emitter=self)

            if self.d.status == config.Status.completed:
                self.status_changed.emit("completed")
                self.progress_changed.emit(100.0)
                self.finished.emit(self.d)

            elif self.d.status in (config.Status.cancelled, config.Status.error, config.Status.failed):
                self.status_changed.emit("error" if self.d.status == config.Status.error else "cancelled")
                self.failed.emit(self.d)

            else:
                self.status_changed.emit("error")
                self.failed.emit(self.d)

        except Exception as e:
            self.log_updated.emit(f"Error: {e}")
            self.d.status = config.Status.error
            self.status_changed.emit("error")
            self.failed.emit(self.d)

    @Slot()
    def check_timeout(self):
        elapsed = time.time() - self.last_progress_time
        if elapsed > self.TIMEOUT_SECONDS:
            self.log_updated.emit(f"Timeout: No progress for {self.TIMEOUT_SECONDS} seconds")
            self.timeout_timer.stop()
            self.d.status = config.Status.error
            self.failed.emit(self.d)

    @Slot(float)
    def on_progress_changed(self, value):
        now = time.time()

        self.last_progress_time = now  # 🟢 Always update when progress happens

        # ✅ Throttle GUI progress updates to max every 0.3s
        if now - self.last_gui_update > 0.3:
            self.progress_changed.emit(value)
            self.last_gui_update = now