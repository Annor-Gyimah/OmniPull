

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

from modules.config import Status
from PySide6.QtCore import QObject, Signal, Slot, QTimer


# Statuses that mean brain() is still running background threads.
# DownloadWorker must keep waiting while d.status is one of these.
_TRANSIENT_STATUSES = {
    Status.downloading,
    Status.stitching,
    Status.merging_audio,
    Status.merging,
    Status.pending,
}

# Statuses that are definitively done — we can emit and exit.
_TERMINAL_STATUSES = {
    Status.completed,
    Status.cancelled,
    Status.queued,
    Status.error,
    Status.failed,
    Status.deleted,
}

# How long to wait between polls (seconds)
_POLL_INTERVAL = 0.25

# Absolute upper-bound safeguard: if we wait this long something is stuck.
_MAX_WAIT_SECONDS = 7200  # 2 hours


class DownloadWorker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    progress_changed = Signal(float)
    status_changed = Signal(str)
    log_updated = Signal(str)
    progress_mode_changed = Signal(str)   # 'indeterminate' | 'determinate'

    TIMEOUT_SECONDS = 60  # No progress for 60s → timeout

    def __init__(self, d):
        super().__init__()
        self.d = d
        self.last_progress_time = time.time()
        self.last_gui_update = 0  # For throttling GUI updates
        self.timeout_timer = QTimer()
        self.timeout_timer.setInterval(5000)
        self.timeout_timer.timeout.connect(self.check_timeout)

    @Slot()
    def run(self):
        from modules.brain import set_signal_emitter, brain

        set_signal_emitter(self)
        self.status_changed.emit("starting")

        try:
            # self.d.update(self.d.url)
            if not getattr(self.d, "_title_resolved", False):
                self.d.update(self.d.url)
            brain(self.d, emitter=self)

            # ── Wait for brain's background threads to reach a terminal state ──
            #
            # brain() for the curl/sparse engine spawns daemon threads and returns
            # immediately. d.status will be 'downloading', 'stitching', etc. while
            # those threads are still running. We must NOT emit finished/failed until
            # d.status settles into a terminal state, otherwise the QueueRunner sees
            # the slot fire too early, calls start_next(), the curl-cap check says
            # "still downloading", breaks — and the next queued item never starts.
            #
            # Progress signals are forwarded while we wait so the UI stays live.
            waited = 0.0
            while self.d.status in _TRANSIENT_STATUSES and waited < _MAX_WAIT_SECONDS:
                time.sleep(_POLL_INTERVAL)
                waited += _POLL_INTERVAL

                # Keep the activity timestamp alive so check_timeout() doesn't
                # fire during a healthy but slow download.  Do NOT emit
                # progress_changed here — brain()'s own worker threads already
                # call on_progress_changed() which emits it.  Emitting a second
                # copy from the polling loop causes the progress bar to flicker
                # (it sees the stale _progress snapshot interleaved with the live
                # value coming from the real workers).
                self.last_progress_time = time.time()

            if waited >= _MAX_WAIT_SECONDS:
                self.log_updated.emit(
                    f"[DownloadWorker] Safety timeout reached after {_MAX_WAIT_SECONDS}s "
                    f"for '{self.d.name}'. Marking as error."
                )
                self.d.status = Status.error

            # ── Emit the appropriate terminal signal ──
            if self.d.status == Status.completed:
                self.status_changed.emit("completed")
                self.progress_changed.emit(100.0)
                self.finished.emit(self.d)

            elif self.d.status == Status.queued:
                # Item was paused by the user; return it to the queue cleanly.
                self.status_changed.emit("cancelled")
                self.failed.emit(self.d)

            elif self.d.status in (Status.cancelled, Status.error, Status.failed):
                self.status_changed.emit("error" if self.d.status == Status.error else "cancelled")
                self.failed.emit(self.d)

            else:
                self.status_changed.emit("error")
                self.failed.emit(self.d)

        except Exception as e:
            self.log_updated.emit(f"Error: {e}")
            self.d.status = Status.error
            self.status_changed.emit("error")
            self.failed.emit(self.d)

    @Slot()
    def check_timeout(self):
        elapsed = time.time() - self.last_progress_time
        if elapsed > self.TIMEOUT_SECONDS:
            self.log_updated.emit(f"Timeout: No progress for {self.TIMEOUT_SECONDS} seconds")
            self.timeout_timer.stop()
            self.d.status = Status.error
            self.failed.emit(self.d)

    @Slot(float)
    def on_progress_changed(self, value):
        now = time.time()

        self.last_progress_time = now  # Always update when progress happens

        # Throttle GUI progress updates to max every 0.3s
        if now - self.last_gui_update > 0.3:
            self.progress_changed.emit(value)
            self.last_gui_update = now