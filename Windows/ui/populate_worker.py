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

from modules import config
from modules.utils import size_format, log
from PySide6.QtCore import QObject, Signal, Slot

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

            # ensure numeric fallbacks
            progress_val = getattr(d, "progress", 0.0) or 0.0
            speed_val = getattr(d, "speed", 0.0) or 0.0
            downloaded_val = getattr(d, "downloaded", 0) or 0
            total_val = getattr(d, "total_size", None)
            if total_val is None:
                # try d.size if used elsewhere
                total_val = getattr(d, "size", 0) or 0

            # build display-ready 'done' string (you can also keep raw numeric if UI expects it)
            done_display = f"{size_format(downloaded_val)} / {size_format(total_val)}" if total_val else f"{size_format(downloaded_val)}"

            row_data = {
                'id': d.id,
                'name': d.name[:-8] if d.name.endswith('.torrent') else d.name,
                'progress': float(progress_val),
                'speed': float(speed_val),
                'time_left': getattr(d, 'time_left', ''),
                'downloaded': int(downloaded_val),
                'total_size': int(total_val or 0),
                'done_display': done_display,   
                'status': d.status,
                'i': "✔"  if d.status == config.Status.completed else d.i, 
                'folder': getattr(d, 'folder', ''),
            }
            prepared_rows.append(row_data)


        self.data_ready.emit(prepared_rows)
