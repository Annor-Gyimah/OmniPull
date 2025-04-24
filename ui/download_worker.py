
from modules import brain, config
from PySide6.QtCore import QObject, QThread, Signal, Slot, QTime, Qt

class DownloadWorker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    progress_changed = Signal(float)
    status_changed = Signal(str)
    log_updated = Signal(str)

    def __init__(self, d):
        super().__init__()
        self.d = d

    @Slot()
    def run(self):
        # Give 'brain' a hook to emit signals
        brain.set_signal_emitter(self)
        self.status_changed.emit("starting")

        try:
            self.d.update(self.d.url)
            brain.brain(self.d, emitter=self)

            if self.d.status == config.Status.cancelled:
                self.status_changed.emit("cancelled")
                self.failed.emit(self.d)
            else:
                self.status_changed.emit("completed")
                self.progress_changed.emit(100.0)
                self.finished.emit(self.d)
        except Exception as e:
            self.log_updated.emit(f"Error: {e}")
            self.failed.emit(self.d)
