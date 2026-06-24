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

from PySide6.QtCore import QThread, Signal

from modules import config
from modules.helpers import change_cursor
from modules.setting import save_setting
from modules.updater import get_changelog, update, update_yt_dlp
from modules.utils import compare_versions, log


class CheckUpdateAppThread(QThread):
    """
    Handles version verification by comparing local state with remote manifests.

    Polls the server for the latest changelog, updates global version variables,
    and signals the UI if a higher version number is detected.
    """
    app_update = Signal(bool)

    def __init__(self, remote: bool = True):
        super().__init__()
        self.remote = remote
        self.new_version_available = False
        self.new_version_description = None
        self.ctx = "APP-UPDATE-CHECK"

    def run(self):
        """Executes the update check and notifies the UI of the result."""
        log("Checking for application updates...", log_level=1, context=self.ctx)
        self.check_for_update()
        self.app_update.emit(self.new_version_available)

    def check_for_update(self):
        """Orchestrates version comparison and state updates."""
        change_cursor('busy')
        current_version = config.APP_VERSION
        try:
            info = get_changelog()
            if info:
                latest_version, version_description = info
                newer_version = compare_versions(current_version, latest_version)

                if not newer_version or newer_version == current_version:
                    self.new_version_available = False
                else:
                    log(f"New version found: {latest_version} (Current: {current_version})",
                        log_level=1, context=self.ctx)
                    self.new_version_available = True

                config.APP_LATEST_VERSION = latest_version
                self.new_version_description = version_description
            else:
                log("Failed to retrieve remote version manifest", log_level=2, context=self.ctx)
                self.new_version_available = False

        except Exception as e:
            log(f"Update verification process failed: {e}", log_level=3, context=self.ctx)
            self.new_version_available = False

        finally:
            change_cursor('normal')
            save_setting()


class YtDlpUpdateThread(QThread):
    """
    Specialized thread for self-updating the yt-dlp binary or library.

    Invokes the internal update mechanism and signals the UI with the
    result of the operation.
    """
    update_finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = "YTDL-BINARY-UPGRADE"

    def run(self):
        """Executes the yt-dlp upgrade process and reports status."""
        log("Initiating yt-dlp binary update check...", log_level=1, context=self.ctx)
        success, message = update_yt_dlp()

        if success:
            log(f"yt-dlp update successful: {message}", log_level=1, context=self.ctx)
        else:
            log(f"yt-dlp update failed or not required: {message}", log_level=2, context=self.ctx)

        self.update_finished.emit(success, message)


class UpdateThread(QThread):
    """
    General purpose update execution thread.

    Typically used for downloading and applying full application patches
    or secondary dependencies.
    """
    update_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx = "CORE-UPDATE-EXEC"

    def run(self):
        """Triggers the global update routine."""
        log("Executing core application update...", log_level=1, context=self.ctx)
        try:
            update()
            if config.confirm_update:
                log("Update logic complete; awaiting user confirmation for restart.",
                    log_level=1, context=self.ctx)
                self.update_finished.emit()
        except Exception as e:
            log(f"Core update execution failed: {e}", log_level=3, context=self.ctx)
