# ui/populate_worker.py



from PySide6.QtCore import QObject, Signal, Slot
from modules import config

class PopulateTableWorker(QObject):
    data_ready = Signal(list)
    finished = Signal()

    def __init__(self, d_list):
        super().__init__()
        self.d_list = d_list

    @Slot()
    def run(self):
        prepared_rows = []

        for d in reversed(self.d_list):
            # Fix invalid states here
            if d.in_queue and not getattr(d, 'queue_name', ''):
                d.in_queue = False
                d.queue_position = 0

            # --- PATCH: Correct total size for torrents ---
            total_size = getattr(d, 'total_size', 0)
            # If d.files exists and is a list (torrent), sum their lengths
            if hasattr(d, 'files') and isinstance(d.files, list) and d.files:
                try:
                    total_size = sum(int(f.length) for f in d.files if hasattr(f, 'length'))
                except Exception:
                    total_size = getattr(d, 'total_size', 0)
            # ---------------------------------------------

            row_data = {
                'id': d.id,
                'name': d.name[:-8] if d.name.endswith('.torrent') else d.name,
                'progress': d.progress or 0,
                'speed': getattr(d, 'speed', 0),
                'time_left': getattr(d, 'time_left', ''),
                'downloaded': getattr(d, 'downloaded', 0),
                'total_size': total_size,
                'status': d.status,
                'i': "✔"  if d.status == config.Status.completed else d.i, 
                'folder': getattr(d, 'folder', ''),
            }
            prepared_rows.append(row_data)

        self.data_ready.emit(prepared_rows)

# from PySide6.QtCore import QObject, Signal, Slot
# from modules import config
# class PopulateTableWorker(QObject):
#     data_ready = Signal(list)
#     finished = Signal()

#     def __init__(self, d_list):
#         super().__init__()
#         self.d_list = d_list

#     @Slot()
#     def run(self):
#         prepared_rows = []

#         for d in reversed(self.d_list):
#             # Fix invalid states here
#             if d.in_queue and not getattr(d, 'queue_name', ''):
#                 d.in_queue = False
#                 d.queue_position = 0

#             # file_name = str(d.name)
#             # if file_name.endswith('.torrent'):
#             #     file_name = file_name[:-8]  # Remove '.torrent' from the end

#             row_data = {
#                 'id': d.id,
#                 'name': d.name[:-8] if d.name.endswith('.torrent') else d.name,
#                 'progress': d.progress or 0,
#                 'speed': getattr(d, 'speed', 0),
#                 'time_left': getattr(d, 'time_left', ''),
#                 'downloaded': getattr(d, 'downloaded', 0),
#                 'total_size': getattr(d, 'total_size', 0),
#                 'status': d.status,
#                 'i': "✔"  if d.status == config.Status.completed else d.i, 
#                 'folder': getattr(d, 'folder', ''),
#             }
#             prepared_rows.append(row_data)

#         self.data_ready.emit(prepared_rows)
