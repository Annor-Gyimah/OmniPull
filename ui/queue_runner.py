# queue_runner.py (to be imported in queue_dialog.py or kept in same file)
from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer
from ui.download_worker import DownloadWorker  # Assuming you separated worker class
from ui.download_window import DownloadWindow
from modules import config


class QueueRunner(QObject):
    queue_finished = Signal(str)  # queue_id
    download_started = Signal(object)
    download_finished = Signal(object)

    def __init__(self, queue_id, queue_items, parent=None):
        super().__init__(parent)
        self.queue_id = queue_id
        self.queue_items = queue_items
        self.index = 0
        self.threads = []

    def start(self):
        self.start_next()

    def start_next(self):
        while self.index < len(self.queue_items):
            d = self.queue_items[self.index]
            if d.status == config.Status.queued:
                break
            self.index += 1

            
        if self.index >= len(self.queue_items):
            self.queue_finished.emit(self.queue_id)
            return

        d = self.queue_items[self.index]
        self.download_started.emit(d)

        thread = QThread()
        worker = DownloadWorker(d)
        worker.moveToThread(thread)

        worker.finished.connect(lambda d=d: self.handle_finished(d))
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        thread.start()

        self.threads.append(thread)

        # Show DownloadWindow with a slight delay to ensure dialog is gone
        if config.show_download_window:
            def show_window():
                main_window = self.parent()
                win = DownloadWindow(d)
                main_window.download_windows[d.id] = win
                win.show()
                worker.progress_changed.connect(win.on_progress_changed)
                worker.status_changed.connect(win.on_status_changed)
                worker.log_updated.connect(win.on_log_updated)

            QTimer.singleShot(200, show_window)  # 200ms delay for safety

    def handle_finished(self, d):
        self.download_finished.emit(d)
        self.index += 1
        self.start_next()

