from PySide6.QtCore import QObject, QThread, Signal, QTimer
from ui.download_worker import DownloadWorker
from ui.download_window import DownloadWindow
from modules import config
from modules.utils import log
from PySide6.QtCore import QMetaObject, Qt, Slot, Q_ARG

class QueueRunner(QObject):
    queue_finished = Signal(str)  # queue_id
    download_started = Signal(object)
    download_finished = Signal(object)
    download_failed = Signal(object)

    def __init__(self, queue_id, queue_items, parent=None):
        super().__init__(parent)
        self.queue_id = queue_id
        self.queue_items = queue_items
        self.index = 0
        self.threads = []
        self.worker_refs = {}  # d.id → worker
        self.thread_refs = {}  # d.id → thread

    def start(self):
        self.start_next()

    def start_next(self):
        log(f"[QueueRunner] start_next() called at index: {self.index}")

        while self.index < len(self.queue_items):
            d = self.queue_items[self.index]
            if d.status == config.Status.queued:
                break
            self.index += 1

        if self.index >= len(self.queue_items):
            log(f"[QueueRunner] Queue {self.queue_id} completed.")
            self.queue_finished.emit(self.queue_id)
            return

        d = self.queue_items[self.index]
        log(f"[QueueRunner] Starting download for: {d.name} (index {self.index})")
        
        self.download_started.emit(d)

        thread = QThread()
        worker = DownloadWorker(d)
        worker.moveToThread(thread)

        self.worker_refs[d.id] = worker
        self.thread_refs[d.id] = thread

        worker.finished.connect(lambda d=d: self.handle_finished(d))
        worker.failed.connect(lambda d=d: self.handle_failed(d))
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)

        log(f"[QueueRunner] Thread object: {thread}, Worker: {worker}")
        log(f"[QueueRunner] thread.isRunning: {thread.isRunning()}")

        thread.start()

         # Optional: show download popup window
        # if config.show_download_window:
        #     self._show_popup(d, worker)
        # DEBUGGING SIGNALS
        def log_unhandled_thread_error():
            log(f"[QueueRunner] Thread {d.name} finished unexpectedly without emitting signal.")

        thread.finished.connect(log_unhandled_thread_error)
        self.threads.append(thread)

       

        
        # if config.show_download_window:
        #     def show_window():
        #         main_window = self.parent()
        #         if hasattr(main_window, "download_windows"):
        #             if d.id in main_window.download_windows:
        #                 old_win = main_window.download_windows.pop(d.id)
        #                 try:
        #                     old_win.close()
        #                 except Exception as e:
        #                     log(f"[QueueRunner] Warning closing previous window: {e}")

        #             win = DownloadWindow(d)
        #             main_window.download_windows[d.id] = win
        #             win.show()

        #             # Connect worker signals to the download window
        #             worker.progress_changed.connect(win.on_progress_changed)
        #             worker.status_changed.connect(win.on_status_changed)
        #             worker.log_updated.connect(win.on_log_updated)
        #             win = DownloadWindow(d)
        #             main_window.download_windows[d.id] = win
        #             win.setAttribute(Qt.WA_DeleteOnClose)
        #             win.show()

        #             ✅ NO SIGNALS CONNECTED YET


        #     QTimer.singleShot(300, show_window)

    def handle_finished(self, d):
        log(f"[QueueRunner] Successfully finished: {d.name}")
        self._close_window(d)

        self.download_finished.emit(d)
        self.worker_refs.pop(d.id, None)
        self.thread_refs.pop(d.id, None)

        self.index += 1
        self.start_next()

    def handle_failed(self, d):
        log(f"[QueueRunner] Download failed or cancelled: {d.name}")
        self._close_window(d)

        self.download_failed.emit(d)
        self.worker_refs.pop(d.id, None)
        self.thread_refs.pop(d.id, None)

        self.index += 1  # ✅ critical fix
        self.start_next()

        if self.index >= len(self.queue_items):
            self.queue_finished.emit(self.queue_id)

    def _close_window(self, d):
        main_window = self.parent()
        if hasattr(main_window, "download_windows"):
            if d.id in main_window.download_windows:
                try:
                    win = main_window.download_windows.pop(d.id)
                    win.close()
                except Exception as e:
                    log(f"[QueueRunner] Failed to close DownloadWindow for {d.name}: {e}")


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