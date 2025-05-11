# queue_runner.py

from PySide6.QtCore import QObject, QThread, Signal, QTimer
from ui.download_worker import DownloadWorker
from ui.download_window import DownloadWindow
from modules import config
from modules.utils import log

class QueueRunner(QObject):
    queue_finished = Signal(str)  # queue_id
    download_started = Signal(object)
    download_finished = Signal(object)
    download_failed = Signal(object)

    def __init__(self, queue_id, queue_items, parent=None):
        super().__init__(parent)
        self.queue_id = queue_id
        self.queue_items = queue_items
        self.parent_window = parent
        self.index = 0
        self.max_concurrent = self._get_max_concurrent()
        self.active_count = 0
        self.running = True

        self.worker_refs = {}
        self.thread_refs = {}

    def _get_max_concurrent(self):
        # Load the queues from settings
        from modules import setting
        self.queues = setting.load_queues()
        for q in self.queues:
            if q.get("id") == self.queue_id:
                return q.get("max_concurrent", 1)
        return 1

    def start(self):
        self._start_next_batch()

    def _start_next_batch(self):
        while self.index < len(self.queue_items) and self.active_count < self.max_concurrent:
            d = self.queue_items[self.index]
            self.index += 1

            if d.status != config.Status.queued:
                continue

            log(f"[QueueRunner] Starting download: {d.name}")
            self._start_download(d)

    def _start_download(self, d):
        thread = QThread()
        worker = DownloadWorker(d)
        worker.moveToThread(thread)

        self.worker_refs[d.id] = worker
        self.thread_refs[d.id] = thread

        worker.finished.connect(lambda d=d: self._handle_finished(d))
        worker.failed.connect(lambda d=d: self._handle_failed(d))
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)

        thread.start()
        self.active_count += 1
        self.download_started.emit(d)

        log(f"[QueueRunner] Thread started for {d.name}, active: {self.active_count}")

        # Optional: show download popup window
        if config.show_download_window:
            self._show_popup(d, worker)

    def _handle_finished(self, d):
        self._cleanup(d)
        self.download_finished.emit(d)
        log(f"[QueueRunner] Finished: {d.name}")
        self._start_next_batch()
        self._check_done()

    def _handle_failed(self, d):
        self._cleanup(d)
        self.download_failed.emit(d)
        log(f"[QueueRunner] Failed or cancelled: {d.name}")
        self._start_next_batch()
        self._check_done()

    def _cleanup(self, d):
        self.active_count = max(0, self.active_count - 1)
        self.worker_refs.pop(d.id, None)
        self.thread_refs.pop(d.id, None)
        self._close_window(d)

    def _check_done(self):
        remaining = any(item.status == config.Status.queued for item in self.queue_items[self.index:])
        if not remaining and self.active_count == 0:
            log(f"[QueueRunner] Queue {self.queue_id} fully processed.")
            self.queue_finished.emit(self.queue_id)

    def _show_popup(self, d, worker):
        def show():
            main_window = self.parent_window
            if hasattr(main_window, "download_windows"):
                win = DownloadWindow(d)
                main_window.download_windows[d.id] = win
                win.show()
                worker.progress_changed.connect(win.on_progress_changed)
                worker.status_changed.connect(win.on_status_changed)
        QTimer.singleShot(0, show)

    def _close_window(self, d):
        if hasattr(self.parent_window, "download_windows"):
            win = self.parent_window.download_windows.pop(d.id, None)
            if win:
                try:
                    win.close()
                except Exception as e:
                    log(f"[QueueRunner] Failed to close window for {d.name}: {e}")
