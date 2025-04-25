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
                    if not hasattr(main_window, "download_windows"):
                        return  # safely skip if main_window is invalid

                    win = DownloadWindow(d)
                    main_window.download_windows[d.id] = win
                    win.show()

                    # Connect signals
                    worker.progress_changed.connect(win.on_progress_changed)
                    worker.status_changed.connect(win.on_status_changed)
                    worker.log_updated.connect(win.on_log_updated)

                QTimer.singleShot(200, show_window)  # 200ms delay for safety

    def handle_finished(self, d):
        if d.status == config.Status.error:
            print(f"[QueueRunner] Warning: Download failed for {d.name}.")
        else:
            print(f"[QueueRunner] Successfully finished: {d.name}")

        self.download_finished.emit(d)
        self.index += 1
        self.start_next()





# def start_next(self):
#         print(f"[QueueRunner] Attempting to start next. Current active: {len(self.active_items)}, Max allowed: {self.max_concurrent}, Current index: {self.index}")

#         while len(self.active_items) < self.max_concurrent and self.index < len(self.queue_items):
#             d = self.queue_items[self.index]
#             print(f"[QueueRunner] Considering item: {d.name} with status: {d.status}")

#             if d.status not in (config.Status.queued, config.Status.pending):
#                 print(f"[QueueRunner] Skipping item {d.name} because status={d.status}")
#                 self.index += 1
#                 continue

#             self.download_started.emit(d)
#             d.status = config.Status.downloading

#             thread = QThread()
#             worker = DownloadWorker(d)
#             worker.moveToThread(thread)

#             # 🚀 Add this connection
#             worker.finished.connect(self.handle_finished)

#             def show_window(worker=worker, d=d):
#                 main_window = self.parent()
#                 if hasattr(main_window, "download_windows"):
#                     win = DownloadWindow(d)
#                     main_window.download_windows[d.id] = win
#                     win.show()
#                     worker.progress_changed.connect(win.on_progress_changed)
#                     worker.status_changed.connect(win.on_status_changed)
#                     worker.log_updated.connect(win.on_log_updated)

#             thread.started.connect(worker.run)
#             thread.finished.connect(thread.deleteLater)

#             if config.show_download_window:
#                 QTimer.singleShot(200, show_window)

#             thread.start()
#             self.threads.append(thread)
#             self.active_items.append(d)
#             self.index += 1

#             print(f"[QueueRunner] Started downloading {d.name}, new index={self.index}")


        

#     def handle_finished(self, d):
#         print(f"[QueueRunner] Finished: {d.name}")
        
#         if d in self.active_items:
#             self.active_items.remove(d)
#             print(f"[QueueRunner] Removed {d.name} from active_items")

#         self.download_finished.emit(d)

#         print(f"[QueueRunner] Current index: {self.index}, Total items: {len(self.queue_items)}, Active: {len(self.active_items)}")
        
#         if self.index >= len(self.queue_items) and not self.active_items:
#             print(f"[QueueRunner] Queue {self.queue_id} finished all downloads!")
#             self.queue_finished.emit(self.queue_id)
#         else:
#             print(f"[QueueRunner] Starting next item...")
#             self.start_next()
