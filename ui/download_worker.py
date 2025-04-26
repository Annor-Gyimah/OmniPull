
# from modules import brain, config
# from PySide6.QtCore import QObject, QThread, Signal, Slot, QTime, Qt

# class DownloadWorker(QObject):
#     finished = Signal(object)
#     failed = Signal(object)

#     progress_changed = Signal(float)
#     status_changed = Signal(str)
#     log_updated = Signal(str)

#     def __init__(self, d):
#         super().__init__()
#         self.d = d

#     @Slot()
#     def run(self):
#         # Give 'brain' a hook to emit signals
#         brain.set_signal_emitter(self)
#         self.status_changed.emit("starting")

#         try:
#             self.d.update(self.d.url)
#             brain.brain(self.d, emitter=self)

#             if self.d.status == config.Status.cancelled:
#                 self.status_changed.emit("cancelled")
#                 self.failed.emit(self.d)
#             else:
#                 self.status_changed.emit("completed")
#                 self.progress_changed.emit(100.0)
#                 self.finished.emit(self.d)
#         except Exception as e:
#             self.log_updated.emit(f"Error: {e}")
#             self.d.status = config.Status.error  # Mark as error
#             self.failed.emit(self.d)




from modules import brain, config
from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer, Qt
import time

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
        self.timeout_timer = QTimer()
        self.timeout_timer.setInterval(5000)  # Check every 5 seconds
        self.timeout_timer.timeout.connect(self.check_timeout)


    @Slot()
    def run(self):
        from modules.brain import set_signal_emitter, brain  # (move here for safety in some cases)

        # Give 'brain' a hook to emit signals
        set_signal_emitter(self)

        self.status_changed.emit("starting")

        try:
            # if self.d.source == "youtube":
            #     self.d.update(self.d.url)  # 👈 Force fresh yt-dlp info

            self.d.update(self.d.url)  # This line refreshes metadata (keep)

            brain(self.d, emitter=self)

            # ✅ Here: Decide what happened based on status
            if self.d.status == config.Status.completed:
                self.status_changed.emit("completed")
                self.progress_changed.emit(100.0)
                self.finished.emit(self.d)

            elif self.d.status in (config.Status.cancelled, config.Status.error, config.Status.failed):
                self.status_changed.emit("error" if self.d.status == config.Status.error else "cancelled")
                self.failed.emit(self.d)

            else:
                # Should not happen ideally, but handle strange cases
                self.status_changed.emit("error")
                self.failed.emit(self.d)

        except Exception as e:
            self.log_updated.emit(f"Error: {e}")
            self.d.status = config.Status.error  # Force mark as error
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
        self.last_progress_time = time.time()  # 🟢 Update last progress time whenever progress happens
