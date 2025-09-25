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

            

            row_data = {
                'id': d.id,
                'name': d.name[:-8] if d.name.endswith('.torrent') else d.name,
                'progress': d.progress or 0,
                'speed': getattr(d, 'speed', 0),
                'time_left': getattr(d, 'time_left', ''),
                'downloaded': getattr(d, 'downloaded', 0),
                'total_size': getattr(d, 'total_size', 0),
                'status': d.status,
                'i': "✔"  if d.status == config.Status.completed else d.i, 
                'folder': getattr(d, 'folder', ''),
            }
            prepared_rows.append(row_data)

        self.data_ready.emit(prepared_rows)
