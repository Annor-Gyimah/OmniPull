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

import os

from PySide6.QtCore import QThread, Signal

from modules import config


class LogRecorderThread(QThread):
    """
    Background worker for persistent file logging.

    Monitors 'log_recorder_q' and flushes messages to disk periodically.
    File I/O runs off the main GUI thread. Handles exit gracefully with a
    final flush before the application terminates.
    """
    error_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.buffer = ''
        self.file = os.path.join(config.sett_folder, 'log.txt')
        self._stop = False
        self.ctx = "LOG-WRITER"
        self.mode = "w" if getattr(config, "LOG_MODE", "append") == "overwrite" else "a"

        # Clear file only once at startup
        if self.mode == "w":
            try:
                with open(self.file, "w", encoding="utf-8", errors="ignore") as f:
                    f.write('')
            except Exception:
                pass

        # After init, always append
        self.mode = "a"

    def stop(self):
        """Triggers the thread to finalize current work and exit."""
        self._stop = True

    def run(self):
        """Continuously polls the log queue and appends data to the log file."""
        try:
            while True:
                if self._stop or self.isInterruptionRequested() or getattr(config, "terminate", False):
                    break

                try:
                    q = config.log_recorder_q
                    while not q.empty():
                        self.buffer += q.get()

                    if self.buffer:
                        with open(self.file, self.mode, encoding="utf-8", errors="ignore") as f:
                            f.write(self.buffer)
                            self.buffer = ''

                    self.msleep(100)

                except Exception as e:
                    self.error_signal.emit(f'Internal log recorder error: {e}')
                    self.msleep(200)

        finally:
            self._final_flush()

    def _final_flush(self):
        """Ensures any remaining logs in the buffer are saved during shutdown."""
        try:
            if self.buffer:
                with open(self.file, self.mode, encoding="utf-8", errors="ignore") as f:
                    f.write(self.buffer)
                    self.buffer = ''
        except Exception:
            pass
