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

            row_data = {
                'id': d.id,
                'name': d.name,
                'progress': d.progress or 0,
                'speed': getattr(d, 'speed', 0),
                'time_left': getattr(d, 'time_left', ''),
                'downloaded': getattr(d, 'downloaded', 0),
                'total_size': getattr(d, 'total_size', 0),
                'status': d.status,
                'i': "✔"  if d.status == config.Status.completed else d.i, 
                'folder': getattr(d, 'folder', ''),
                'file_name': str(d.name),
            }
            prepared_rows.append(row_data)

        self.data_ready.emit(prepared_rows)
