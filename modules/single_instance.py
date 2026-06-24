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

from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstanceApp:
    """Ensures only one instance of OmniPull runs at a time."""

    def __init__(self, app_id):
        self.app_id = app_id
        self.server = QLocalServer()

    def is_running(self):
        socket = QLocalSocket()
        socket.connectToServer(self.app_id)
        is_running = socket.waitForConnected(500)
        socket.close()
        return is_running

    def start_server(self):
        if not self.server.listen(self.app_id):
            QLocalServer.removeServer(self.app_id)  # Clean up stale server
            self.server.listen(self.app_id)
