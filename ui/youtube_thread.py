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

import asyncio
import threading

from PySide6.QtCore import QThread, Signal

from modules.helpers import change_cursor
from modules.threadpool import executor
from modules.utils import log
from modules.video import Video, extract_info_blocking, get_ytdl_options


class YouTubeThread(QThread):
    """
    Asynchronous execution thread for YouTube metadata extraction.

    This class manages the lifecycle of yt-dlp extraction tasks, supporting
    both single-video URLs and multi-entry playlists. It utilizes an asyncio
    event loop to handle non-blocking network calls and provides a mechanism
    to terminate subprocesses immediately via a shared stop_event.

    Widget references (w_add, w_settings) are injected at construction time
    to avoid circular imports with main.py.
    """
    finished       = Signal(object)   # Video | list[Video] | None
    progress       = Signal(int)      # 0-100
    error_occurred = Signal(str)

    def __init__(self, url: str, stop_event: threading.Event = None,
                 w_add=None, w_settings=None):
        super().__init__()
        self.url = url
        self.stop_event = stop_event or threading.Event()
        self.error_message = None
        self._proc_holder = [None]
        self.ctx = "YTDL-EXTRACT"
        self._w_add = w_add
        self._w_settings = w_settings

    def run(self):
        """Initializes the asyncio loop and executes the extraction lifecycle."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_async())
        except Exception as e:
            self.error_message = str(e)
            log(f"Critical failure in extraction loop: {self.error_message}",
                log_level=3, context=self.ctx)
            self.error_occurred.emit(self.error_message)
            self.finished.emit(None)

    def _cancelled(self) -> bool:
        """Returns True if the external stop_event has been triggered."""
        return self.stop_event.is_set()

    def _kill_current_proc(self):
        """Forces termination of the active yt-dlp subprocess."""
        proc = self._proc_holder[0]
        if proc is not None:
            try:
                proc.kill()
                log(f"Subprocess terminated successfully (PID: {proc.pid})",
                    log_level=1, context=self.ctx)
            except Exception as e:
                log(f"Failed to terminate subprocess: {e}",
                    log_level=2, context=self.ctx)

    async def _run_async(self):
        """Coordinates the transition between playlist and single-video processing."""
        try:
            if self._w_add is not None:
                self._w_add.download_btn.setEnabled(False)
                self._w_add.resolution_combo.clear()
            if self._w_settings is not None:
                self._w_settings.monitor_clipboard_chk.setChecked(False)
            change_cursor("busy")

            if self._cancelled():
                self.finished.emit(None)
                return

            log(f"Initiating metadata extraction for URL: {self.url}",
                log_level=1, context=self.ctx)

            loop = asyncio.get_running_loop()
            stubs = await loop.run_in_executor(
                executor,
                Video.extract_playlist_entries_streaming,
                self.url,
                self.stop_event,
                self._proc_holder,
            )

            if self._cancelled():
                log("Extraction aborted by user during playlist discovery",
                    log_level=1, context=self.ctx)
                self.finished.emit(None)
                return

            if not stubs:
                log("No playlist detected; falling back to single video extraction",
                    log_level=1, context=self.ctx)
                await self._process_single()
                return

            if len(stubs) == 1:
                stub = stubs[0]
                if stub.get("formats"):
                    try:
                        v = Video(
                            stub.get("webpage_url") or stub.get("url") or self.url,
                            vid_info=stub,
                            get_size=False,
                        )
                        self.progress.emit(100)
                        self.finished.emit(v)
                        return
                    except Exception as e:
                        log(f"Format recovery failed for single-stub playlist: {e}",
                            log_level=2, context=self.ctx)

            await self._process_playlist(stubs)

        except Exception as e:
            self.error_message = str(e)
            log(f"Extraction engine encountered an error: {self.error_message}",
                log_level=3, context=self.ctx)
            self.error_occurred.emit(self.error_message)
            self.finished.emit(None)
        finally:
            change_cursor("normal")
            if self._w_add is not None:
                self._w_add.download_btn.setEnabled(True)
            if self._w_settings is not None:
                self._w_settings.monitor_clipboard_chk.setChecked(True)

    async def _process_single(self):
        """Fetches detailed format and metadata for a standalone video URL."""
        log(f"Performing deep metadata fetch for target: {self.url}",
            log_level=1, context=self.ctx)
        loop = asyncio.get_running_loop()
        ydl_opts = get_ytdl_options()
        try:
            vid_info = await loop.run_in_executor(
                executor, extract_info_blocking, self.url, ydl_opts
            )
        except Exception as e:
            log(f"Network request failed for single video: {e}",
                log_level=2, context=self.ctx)
            self.error_occurred.emit(str(e))
            self.finished.emit(None)
            return

        if self._cancelled() or not vid_info:
            return

        try:
            video_obj = Video(self.url, vid_info=vid_info)
            self.progress.emit(100)
            self.finished.emit(video_obj)
        except Exception as e:
            log(f"Object instantiation failed for video metadata: {e}",
                log_level=2, context=self.ctx)
            self.error_occurred.emit(str(e))
            self.finished.emit(None)

    async def _process_playlist(self, stubs: list[dict]):
        """Iteratively resolves flat playlist stubs into full Video objects."""
        total = len(stubs)
        playlist = []
        skipped = []
        last_pct = -1
        UPDATE_STEP = 5

        log(f"Playlist detected: processing {total} items",
            log_level=1, context=self.ctx)

        for index, stub in enumerate(stubs):
            if self._cancelled():
                log(f"Playlist resolution halted. Finalized {len(playlist)} of {total} items.",
                    log_level=1, context=self.ctx)
                self.finished.emit(playlist if playlist else None)
                return

            if not stub:
                continue

            video_obj = await Video.fetch_single_entry(
                stub, self.stop_event, self._proc_holder
            )

            if self._cancelled():
                return

            if video_obj is not None:
                playlist.append(video_obj)
            else:
                vid_id = stub.get("id") or stub.get("title") or f"Index {index + 1}"
                skipped.append(vid_id)
                log(f"Excluding unreachable item: {vid_id}",
                    log_level=2, context=self.ctx)

            pct = int((index + 1) * 100 / total)
            if pct // UPDATE_STEP > last_pct // UPDATE_STEP:
                self.progress.emit(pct)
                last_pct = pct

        if skipped:
            log(f"Extraction complete. Successfully resolved {len(playlist)} items; "
                f"{len(skipped)} items were skipped due to errors.",
                log_level=1, context=self.ctx)

        self.progress.emit(100)
        self.finished.emit(playlist)
