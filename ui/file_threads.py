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

from modules import config, native_engine
from modules.utils import log, run_command


class FileOpenThread(QThread):
    """
    Handles OS-level file opening requests in a separate thread.

    Verifies file existence before attempting to invoke system handlers.
    Provides cross-platform support for Windows, Linux, and macOS.
    """
    critical_signal = Signal(str, str)

    def __init__(self, file_path: str, parent=None):
        super(FileOpenThread, self).__init__(parent)
        self.file_path = file_path
        self.ctx = "SHELL-EXEC"

    def run(self):
        """Attempts to open the file using the host operating system's default handler."""
        try:
            if not os.path.exists(self.file_path):
                log(f"Target file missing from disk: {self.file_path}",
                    log_level=3, context=self.ctx)
                self.critical_signal.emit('not_found', self.file_path)
                return

            log(f"Invoking system handler for path: {self.file_path}",
                log_level=1, context=self.ctx)

            if config.operating_system == 'Windows':
                os.startfile(self.file_path)
            elif config.operating_system == 'Linux':
                run_command(f'xdg-open "{self.file_path}"')
            elif config.operating_system == 'Darwin':
                run_command(f'open "{self.file_path}"')

        except PermissionError:
            log(f"Access denied to file: {self.file_path}",
                log_level=3, context=self.ctx)
            self.critical_signal.emit('Permission Error', 'Access denied.')
        except Exception as e:
            log(f"System shell failed to open file: {e}",
                log_level=3, context=self.ctx)
            self.critical_signal.emit(
                'OS Error',
                f"An OS error occurred while opening the file: {e}"
            )


class FileChecksum(QThread):
    """Computes a SHA-256 checksum for a file using the native Nim engine."""
    checksum_computed = Signal(str, str)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        try:
            checksum = native_engine.compute_sha256(self.file_path)
            self.checksum_computed.emit(self.file_path, checksum)
        except Exception:
            self.checksum_computed.emit(self.file_path, "Error")
