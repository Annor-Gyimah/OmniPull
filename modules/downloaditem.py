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

import re
import os
import time
import mimetypes

from queue import Queue
from collections import deque

from modules import config

from threading import Lock
from urllib.parse import urljoin
from modules.utils import validate_file_name, get_headers, translate_server_code, size_splitter, idm_style_splitter, get_seg_size, log, \
    delete_file, delete_folder, save_json, load_json, size_format


# Compiled once at module level — not per-instance
_RE_BYTES_NUM = re.compile(r"([\d\.,]+)\s*([KMGTP]?i?B)?", re.IGNORECASE)


class Communication:
    """
    Handles thread-safe communication between download workers and the UI.
    
    This class manages two primary queues:
    1. d_window: Sends log messages and status updates to the Download Window.
    2. jobs: Acts as a re-circulation queue for segments that need to be re-attempted.
    """

    def __init__(self):
        # UI Messaging Queue (Logs, Connection Stats)
        self.d_window = Queue()  
        
        # Segment Recovery Queue (Dynamic Splitting & Retries)
        self.jobs = Queue()  

    @staticmethod
    def clear(q):
        """
        Drains all items from a specific queue until it is empty.
        Uses get_nowait() to prevent blocking the calling thread.
        """
        try:
            while True:
                q.get_nowait()  # Throws Empty exception when finished
        except Exception:
            pass

    def reset(self):
        """
        Clears both the UI log queue and the segment job queue.
        Typically called when a download is restarted or moved back to the queue.
        """
        self.clear(self.d_window)
        self.clear(self.jobs)

    def log(self, *args):
        """
        Formats and sends log strings to the download window's text display.
        
        Logic:
        - Joins multiple arguments with spaces.
        - Ensures the final string ends with a single newline character.
        - Packs the message into a tuple format ('log', message) for the UI consumer.
        """
        s = ' '
        s = s.join(str(arg) for arg in args)
       
        # Note: Original logic removes the trailing space added by join()
        s = s[:-1]  

        # Ensure the UI appendText call triggers a new line
        if s[-1] != '\n':
            s += '\n'

        self.d_window.put(('log', s))


class Segment:
    """
    Represents a single byte-range chunk of a download.
    
    This class supports IDM-style dynamic splitting, allowing a slow segment 
    to be halved mid-download so a free worker can take over the second half.
    """
    def __init__(self, name=None, num=None, range=None, size=None, url=None, tempfile=None, seg_type='', merge=True):
        self.num = num
        self.size = size
        self.range = range  
        self.downloaded = False
        self.completed = False  
        self.name = name
        self.tempfile = tempfile
        self.headers = {}
        self.url = url
        self.seg_type = seg_type
        self.merge = merge
        self.in_progress = False  # Lock to prevent multiple workers from picking the same segment

    def can_split(self, min_split_size=102400):  # 100KB minimum
        """
        Determines if the segment is large enough to be split into two.
        
        Prevents splitting segments that are already finished or are too 
        small to justify the overhead of a new network connection.
        """
        if self.downloaded or self.completed:
            return False
        if self.range is None or self.size is None:
            return False
        return self.size > min_split_size

    def split(self, next_num):
        """
        Splits this segment at its midpoint and returns a new Segment 
        representing the second half.
        """
        if not self.can_split():
            return None

        # Calculate midpoint for the byte range
        start, end = self.range
        midpoint = start + ((end - start) // 2)

        # Create the new segment for the second half
        new_seg = Segment(
            name=self.name.replace(f'{self.num}.', f'{next_num}.'),
            num=next_num,
            range=(midpoint + 1, end),
            size=end - midpoint,
            url=self.url,
            tempfile=self.tempfile,
            seg_type=self.seg_type,
            merge=self.merge
        )

        # Update current segment to represent only the first half
        self.range = (start, midpoint)
        self.size = (midpoint - start) + 1

        return new_seg

    def get_size(self):
        """
        Fetches the content-length for this specific segment's URL.
        Used primarily for manifest-based downloads (HLS/DASH).
        """
        ctx = "SEGMENT-INFO"
        self.headers = get_headers(self.url)
        try:
            self.size = int(self.headers.get('content-length', 0))
            log(f"Segment {self.num} resolved size: {size_format(self.size)}", 
                log_level=3, context=ctx)
        except Exception:
            pass
        return self.size

    def __repr__(self):
        return repr(self.__dict__)


class DownloadItem:
    """
    The core data model representing a single download task.
    
    Contains all metadata required for:
    1. Multi-engine routing (Aria2c, yt-dlp, cURL).
    2. Dynamic UI updates (Animations, Progress, Speed).
    3. Persistence (Saving/Loading from disk).
    4. Queuing and Scheduling.
    """
    
    # UI State Icons: Used for animating the 'Status' column in the download list
    animation_icons = {
        config.Status.downloading: ['❯', '❯❯', '❯❯❯', '❯❯❯❯'],
        config.Status.pending: ['⏳'],
        config.Status.completed: ['✔'],
        config.Status.cancelled: ['-x-'],
        config.Status.merging_audio: ['↯', '↯↯', '↯↯↯'],
        config.Status.error: ['err'],
        config.Status.paused: ['⏸', '⏸⏸'],
        config.Status.failed: ['⚠', '❌'],
        config.Status.scheduled: ['🕒', '🕞', '🕘'],
        config.Status.deleted: ['🗑', '🗑️'],
        config.Status.queued: ['➤', '➤➤', '➤➤➤'],
        config.Status.stitching: ['🧵', '🧵🧵', '🧵🧵🧵'],
        config.Status.unzipping: ['📦', '📦📦', '📦📦📦'],
    }

    def __init__(self, id_=0, url='', name='', folder='', callback=None):
        # --- Basic Identity ---
        self.id = id_
        self._name = name
        self.ext = ''
        self.folder = os.path.abspath(folder)

        # --- URL & Stream Metadata ---
        self.url = url
        self.eff_url = ''      # Resolved direct link
        self.playlist_url = '' # Parent playlist if applicable
        self.original_url = url  

        # --- File Attributes ---
        # self.size = 0
        self._size = 0
        self.resumable = False
        self.type = ''         # e.g., 'dash', 'hls', 'static'
        self.category = None   # User-defined category

        # --- Engine & Protocol ---
        self.engine = config.download_engine
        self.protocol = ''     # e.g., 'http', 'm3u8', 'magnet'
        self.format_id = None
        self.audio_format_id = None
        self.aria_gid = None   # GID for main Aria2c task
        self.audio_gid = None  # GID for secondary Aria2c audio task
        self.manifest_url = '' 

        # --- Audio (Optional Stream) ---
        self.audio_stream = None
        self.audio_url = None
        self.audio_size = 0
        self.is_audio = False

        # --- Progress & Connection State ---
        self.live_connections = 0
        self._downloaded = 0
        self._progress = 0 
        self._status = config.Status.cancelled
        self.remaining_parts = 0
        self.status_code = 0
        self.status_code_description = ''
        
        # Connection-level detail for the 'Details' window
        self.connection_stats = [] # List of {"downloaded": int, "info": str}

        # --- Communication & Logic ---
        self.q = Communication()   # Internal signal/queue hub
        self.callback = ''         # Post-download function name
        self.resume_tracker = None # Sparse engine sidecar tracker

        # --- Animation & UI ---
        self.animation_index = 0 
        self.animation_timer = 0

        # --- Speed & Throttling ---
        self._speed = 0
        self.prev_downloaded_value = 0
        self.speed_buffer = deque() # Rolling average buffer
        self.speed_timer = 0
        self.speed_refresh_rate = 1 

        # --- Segment Management ---
        self._segments = []
        self._segment_size = config.segment_size

        # --- DASH/Fragment Parameters ---
        self.fragment_base_url = None
        self.fragments = None
        self.audio_fragment_base_url = None
        self.audio_fragments = None

        # --- Resume & Persistence ---
        self.last_known_size = 0
        self.last_known_progress = 0
        self.last_try_date = None
        self.retry_count = 0

        # --- Queue & Scheduling ---
        self.in_queue = True
        self.queue_name = ""
        self.queue_position = 0 
        self.queue_id = None 
        self.sched = None       # Tuple: (hours, minutes)
        self.schedule_retries = 0
        
        # Per-instance lock so concurrent downloads don't contend on each other
        self._lock = Lock()
        self.referrer = None
        self.callback = callback









    def get_persistent_properties(self):
        """
        Returns a dictionary of critical parameters for serialization.
        
        This dictionary is used to rebuild the DownloadItem state 
        when the application restarts.
        """
        # Add any new numeric fields in the db_manager.py the _INT_COLUMNS variable if numeric field
        a = dict(id=self.id, _name=self._name, ext=self.ext, folder=self.folder, url=self.url, eff_url=self.eff_url,
            playlist_url=self.playlist_url, original_url=self.original_url, size=self.size, resumable=self.resumable,
            _segment_size=self._segment_size, _downloaded=self._downloaded, _status=self._status,
            remaining_parts=self.remaining_parts, audio_url=self.audio_url, audio_size=self.audio_size,
            type=self.type, fragments=self.fragments, fragment_base_url=self.fragment_base_url,
            audio_fragments=self.audio_fragments, audio_fragment_base_url=self.audio_fragment_base_url,
            last_known_size=self.last_known_size, last_known_progress=self.last_known_progress,
            protocol=self.protocol, manifest_url=self.manifest_url, scheduled=self.sched, schedule_retries=self.schedule_retries,
            in_queue=self.in_queue, queue_id=self.queue_id, queue_name=self.queue_name, queue_position=self.queue_position,
            engine=self.engine, aria_gid=self.aria_gid, audio_gid=self.audio_gid, category=self.category, last_try_date=self.last_try_date,
            referrer=self.referrer, retry_count=self.retry_count, callback=self.callback, 
        )
            # CRITICAL FIX: Convert function objects to their string names
        cb = a.get("callback")
        if callable(cb):
            try:
                # If it's a function, get its name (e.g., unzip_deno)
                a["callback"] = cb.__name__
            except AttributeError:
                # If it's a lambda, we can't save it reliably
                log("Warning: Cannot save lambda callback to JSON. Use a string name instead.", log_level=2)
                a["callback"] = None
        return a


    def reset_segments(self):
        """
        Resets the download and merge status for all segments. Used when a download needs to be restarted from scratch.
        """
        for seg in self._segments:
            seg.downloaded = False
            seg.completed = False
    
    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        try:
            self._size = int(value) if value is not None else 0
        except (TypeError, ValueError):
            self._size = 0

    @property
    def segments(self):
        """
        Initializes or retrieves the list of segments for the download item.
        Handles fragmented video (HLS/DASH) and static files with IDM-style range splitting.
        """
        ctx = "ITEM-SEGMENTS"
        if not self._segments:
            # Handle fragmented video streams (e.g., HLS or DASH manifests)
            if self.fragments:
                # Example fragment structure: [{'path': 'range/0-640'}, {'path': 'range/2197-63702'}]
                self._segments = [
                    Segment(
                        name=os.path.join(self.temp_folder, str(i)), 
                        num=i, range=None, size=0,
                        url=urljoin(self.fragment_base_url, x['path']), 
                        tempfile=self.temp_file
                    ) for i, x in enumerate(self.fragments)
                ]

            else:
                # Handle static file downloads
                if self.resumable and self.size:
                    # Generate a list of byte ranges using IDM-style initial segmentation
                    range_list = idm_style_splitter(self.size, max_connections=config.max_connections)
                else:
                    # Non-resumable files are treated as a single segment
                    range_list = [None]  

                self._segments = [
                    Segment(
                        name=os.path.join(self.temp_folder, str(i)), 
                        num=i, range=x, size=get_seg_size(x),
                        url=self.eff_url, tempfile=self.temp_file
                    ) for i, x in enumerate(range_list)
                ]

            # Process auxiliary audio streams for DASH video merging
            if self.type == 'dash':
                if self.audio_fragments:
                    # Handle manifest-based audio fragments
                    audio_segments = [
                        Segment(
                            name=os.path.join(self.temp_folder, str(i) + '_audio'), 
                            num=i, range=None, size=0,
                            url=urljoin(self.audio_fragment_base_url, x['path']), 
                            tempfile=self.audio_file
                        ) for i, x in enumerate(self.audio_fragments)
                    ]
                else:
                    # Use IDM-style segmentation for audio byte ranges
                    range_list = idm_style_splitter(self.audio_size, max_connections=config.max_connections)

                    audio_segments = [
                        Segment(
                            name=os.path.join(self.temp_folder, str(i) + '_audio'), 
                            num=i, range=x,
                            size=get_seg_size(x), url=self.audio_url, tempfile=self.audio_file
                        ) for i, x in enumerate(range_list) if get_seg_size(x) > 0
                    ]

                # Consolidate video and audio segments into the master segment list
                self._segments += audio_segments

        return self._segments

    @segments.setter
    def segments(self, value):
        self._segments = value

    def save_progress_info(self):
        """
        Serializes the current state of all segments to 'progress_info.txt'.
        Ensures resume capabilities across application restarts.
        """
        seg_list = [
            {'name': seg.name, 'downloaded': seg.downloaded, 
             'completed': seg.completed, 'size': seg.size} 
            for seg in self.segments
        ]
        file = os.path.join(self.temp_folder, 'progress_info.txt')
        save_json(file, seg_list)

    def load_progress_info(self):
        """
        Restores segment completion status from 'progress_info.txt'.
        """
        file = os.path.join(self.temp_folder, 'progress_info.txt')
        if os.path.isfile(file):
            seg_list = load_json(file)
            for seg, item in zip(self.segments, seg_list):
                if seg.name in item['name']:
                    seg.size = item['size']
                    seg.downloaded = item['downloaded']
                    seg.completed = item['completed']

    @property
    def total_size(self):
        """
        Calculates the full size of the download.
        
        If the size is unknown (HLS/Fragments), it calculates an estimate based 
        on the average size of segments already downloaded.
        """
        if self.type == 'dash':
            size = self.size + self.audio_size
        else:
            size = self.size

        # --- Fragment Size Estimation Logic ---
        if not size and self._segments:
            sizes = [seg.size for seg in self.segments if seg.size]
            if sizes:
                avg_seg_size = sum(sizes) // len(sizes)
                size = avg_seg_size * len(self._segments)

        # Fallback to the last verified size from disk
        if not size:
            return self.last_known_size

        self.last_known_size = size 
        return size
    
    @total_size.setter
    def total_size(self, value):
        self._total_size = value
    
    

    

    

    def _human_to_bytes(self, s):
        """Convert strings like '34.4MiB' or '123.4KiB' or '1024' to integer bytes; return None if unparsable."""
        if s is None:
            return None
        if isinstance(s, (int, float)):
            return int(s)
        s = str(s).strip()
        if not s:
            return None
        s = s.replace("~", "").replace(",", "").strip()
        m = _RE_BYTES_NUM.search(s)
        if not m:
            try:
                return int(float(s))
            except Exception:
                return None
        val = float(m.group(1))
        unit = (m.group(2) or "").lower()
        mul = 1
        if unit in ("kb", "kib"):
            mul = 1024
        elif unit in ("mb", "mib"):
            mul = 1024 ** 2
        elif unit in ("gb", "gib"):
            mul = 1024 ** 3
        elif unit in ("tb", "tib"):
            mul = 1024 ** 4
        elif unit in ("pb", "pib"):
            mul = 1024 ** 5
        return int(val * mul)

    @property
    def downloaded(self):
        # return integer bytes (0 if unknown)
        return getattr(self, "_downloaded", 0) or 0

    @downloaded.setter
    def downloaded(self, value):
        """
        Accept:
        - int / float (will convert to int bytes)
        - numeric strings like "12345" or "12.3"
        - human size strings like "34.4MiB" or "66.47KiB"
        Reject other values silently to avoid crashes.
        """
        try:
            if value is None:
                return
            # if it's already int/float -> cast to int
            if isinstance(value, (int, float)):
                new_val = int(value)
            else:
                # try parse human string -> bytes
                maybe = self._human_to_bytes(value)
                if maybe is None:
                    # try plain int conversion as last resort
                    try:
                        new_val = int(float(str(value)))
                    except Exception:
                        return
                else:
                    new_val = maybe

            with self._lock:
                # store as int
                self._downloaded = int(new_val)
        except Exception:
            # defensive: don't propagate exceptions from background threads
            return
        
    # ---------- speed property (thread-safe, numeric) ----------
    @property
    def speed(self) -> float:
        """
        Return a smoothed bytes/second numeric speed.
        This computes incremental speeds at most once per `speed_refresh_rate` seconds,
        stores the recent values in speed_buffer, and returns the averaged speed.
        Always returns a float (0.0 if unknown).
        """
        # ensure attributes exist
        if not hasattr(self, "speed_buffer"):
            self.speed_buffer = deque(maxlen=10)
        if not hasattr(self, "speed_timer"):
            self.speed_timer = time.time()
        if not hasattr(self, "prev_downloaded_value"):
            self.prev_downloaded_value = getattr(self, "downloaded", 0) or 0
        if not hasattr(self, "speed_refresh_rate"):
            self.speed_refresh_rate = 0.5

        # If not downloading, keep speed at 0.0 (do not attempt to compute)
        # Simple float assignment is GIL-atomic; no lock needed on the fast path.
        if getattr(self, "status", None) != config.Status.downloading:
            self._speed = 0.0
            return 0.0

        # compute delta only occasionally to reduce noise
        now = time.time()
        time_passed = now - self.speed_timer if hasattr(self, "speed_timer") else 0.0
        if time_passed >= getattr(self, "speed_refresh_rate", 0.5):
            # sample new speed
            with self._lock:
                current_downloaded = int(getattr(self, "_downloaded", getattr(self, "downloaded", 0) or 0))
            # protect prev_downloaded_value initialization
            if not getattr(self, "prev_downloaded_value", None):
                self.prev_downloaded_value = current_downloaded
                self.speed_timer = now
                return float(getattr(self, "_speed", 0.0) or 0.0)

            delta = current_downloaded - int(self.prev_downloaded_value or 0)
            # avoid negative delta
            if delta < 0:
                delta = 0
            # avoid division by zero
            if time_passed <= 0:
                instant_speed = 0.0
            else:
                instant_speed = float(delta) / float(time_passed)

            # update trackers
            self.prev_downloaded_value = current_downloaded
            self.speed_timer = now

            # push to buffer and compute average
            try:
                self.speed_buffer.append(instant_speed)
            except Exception:
                # fallback: recreate buffer
                self.speed_buffer = deque([instant_speed], maxlen=10)

            avg_speed = float(sum(self.speed_buffer) / len(self.speed_buffer)) if self.speed_buffer else 0.0

            with self._lock:
                self._speed = float(avg_speed or 0.0)

        # always return numeric float
        return float(getattr(self, "_speed", 0.0) or 0.0)

    @speed.setter
    def speed(self, value):
        """
        Allow external assignment of numeric speeds. Accept ints/floats (bytes/sec)
        and numeric-like strings; coerce to float. If invalid, ignore.
        """
        try:
            if value is None:
                return
            if isinstance(value, (int, float)):
                v = float(value)
            else:
                # try to extract a number from a string like '66.47KiB/s' not handled here;
                # prefer letting the downloader logic use parse_speed_to_bps and set numeric bytes/sec.
                s = str(value).strip()
                # try a pure numeric parse
                m = re.search(r"[-+]?\d*\.?\d+", s)
                v = float(m.group(0)) if m else None
                if v is None:
                    return
            with self._lock:
                self._speed = float(max(0.0, v))
        except Exception:
            return

    
    # @property
    # def progress(self) -> float:
    #     """
    #     Compute percent downloaded:
    #     - If completed -> 100
    #     - If fragmented and total_size == 0: compute by finished segments / total segments (guard zero len)
    #     - else: downloaded/total_size * 100 (guard zero total_size)
    #     Always returns float (0.0 - 100.0).
    #     Maintains last_known_progress so that temporary 0 values don't reset UI.
    #     """
    #     try:
    #         # Completed -> 100
    #         if getattr(self, "status", None) == config.Status.completed:
    #             p = 100.0
    #         else:
    #             total = int(getattr(self, "total_size", 0) or getattr(self, "size", 0) or 0)
    #             downloaded = int(getattr(self, "_downloaded", getattr(self, "downloaded", 0) or 0))

    #             if total == 0:
    #                 # fragmented (HLS etc.) -> use segments if available
    #                 segs = getattr(self, "segments", None)
    #                 if segs and isinstance(segs, (list, tuple)) and len(segs) > 0:
    #                     finished = sum(1 for seg in segs if getattr(seg, "completed", False))
    #                     p = round((finished * 100.0) / max(1, len(segs)), 1)
    #                 else:
    #                     # no size & no segments: return last known progress (avoid flipping to 0)
    #                     p = float(getattr(self, "last_known_progress", 0.0) or 0.0)
    #             else:
    #                 p = round((float(downloaded) * 100.0) / float(total), 1)

    #         # clamp
    #         if p > 100.0:
    #             p = 100.0
    #         elif p < 0.0:
    #             p = 0.0

    #         # If p==0, return last known progress (so UI does not jump to indeterminate)
    #         if p == 0.0:
    #             # ensure last_known_progress exists
    #             last = float(getattr(self, "last_known_progress", 0.0) or 0.0)
    #             return last

    #         # update last_known_progress
    #         with lock:
    #             self.last_known_progress = float(p)

    #         return float(self.last_known_progress)
    #     except Exception:
    #         # defensive default
    #         return float(getattr(self, "_progress", 0.0) or 0.0)

    @property
    def progress(self) -> float:
        try:
            if getattr(self, "status", None) == config.Status.completed:
                return 100.0

            # Trust _progress if it was explicitly set to 100 (e.g. after DB load)
            stored = float(getattr(self, "_progress", 0.0) or 0.0)
            if stored >= 100.0:
                return 100.0

            total = int(getattr(self, "total_size", 0) or getattr(self, "size", 0) or 0)
            downloaded = int(getattr(self, "_downloaded", 0) or 0)

            if total == 0:
                segs = getattr(self, "_segments", None)
                if segs and len(segs) > 0:
                    finished = sum(1 for seg in segs if getattr(seg, "completed", False))
                    p = round((finished * 100.0) / max(1, len(segs)), 1)
                else:
                    p = float(getattr(self, "last_known_progress", 0.0) or 0.0)
            else:
                p = round((float(downloaded) * 100.0) / float(total), 1)

            p = max(0.0, min(100.0, p))

            if p == 0.0:
                return float(getattr(self, "last_known_progress", 0.0) or 0.0)

            with self._lock:
                self.last_known_progress = float(p)
            return float(self.last_known_progress)

        except Exception:
            return float(getattr(self, "_progress", 0.0) or 0.0)

    @progress.setter
    def progress(self, value):
        """
        Accept numeric or numeric-string; coerce to float and store in _progress and last_known_progress.
        Keep thread-safety.
        """
        try:
            if value is None:
                return
            if isinstance(value, (int, float)):
                v = float(value)
            else:
                s = str(value).strip().rstrip("%")
                m = re.search(r"[-+]?\d*\.?\d+", s)
                v = float(m.group(0)) if m else None
                if v is None:
                    return
            v = max(0.0, min(100.0, v))
            with self._lock:
                self._progress = v
                if v > 0.0:
                    self.last_known_progress = v
        except Exception:
            return

    @property
    def time_left(self):
        """
        Calculates the estimated time remaining in seconds.
        Returns -1 if the speed is zero, or '---' if not currently downloading.
        """
        if self.status == config.Status.downloading and self.total_size:
            # Standard ETA formula: (Remaining Bytes) / (Bytes per Second)
            return (self.total_size - self.downloaded) / self.speed if self.speed else -1
        else:
            return '---'

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value

    @property
    def num(self):
        return self.id + 1 if isinstance(self.id, int) else self.id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_value):
        # validate new name
        self._name = validate_file_name(new_value)

    @property
    def target_file(self):
        """return file name including path"""
        return os.path.join(self.folder, self.name)
    
    @target_file.setter
    def target_file(self, value):
        """Updates both folder and name attributes from a full file path."""
        self.folder, self._name = os.path.split(value)
        self.folder = os.path.abspath(self.folder)
        self._name = validate_file_name(self._name)

    @property
    def temp_file(self):
        """Returns the path to the temporary video/data file."""
        name = f'_temp_{self.name}'.replace(' ', '_')
        return os.path.join(self.folder, name)

    @property
    def audio_file(self):
        """Returns the path to the temporary audio file (used in DASH/Separate streams)."""
        name = f'audio_for_{self.name}'.replace(' ', '_')
        return os.path.join(self.folder, name)
    
    @audio_file.setter
    def audio_file(self, value):
        """Updates internal naming based on an absolute audio file path."""
        self.folder, self._name = os.path.split(value)
        self.folder = os.path.abspath(self.folder)
        self._name = validate_file_name(self._name)

    @property
    def temp_folder(self):
        """Returns the directory path where individual segments are stored before stitching."""
        return f'{self.temp_file}_parts_'

    @property
    def i(self):
        """
        Handles the UI animation state. 
        Cycles through the icon list every 0.5 seconds to create a loading effect.
        """
        if self.sched:
            # If scheduled, show the target time instead of an icon
            selected_image = self.sched_string
        else:
            # Fetch the appropriate icon list from the class-level animation_icons dict
            icon_list = self.animation_icons.get(self.status, [''])

            # Only advance the animation frame if 0.5s has elapsed
            if time.time() - self.animation_timer > 0.5:
                self.animation_timer = time.time()
                self.animation_index += 1

            # Loop back to the start of the icon list
            if self.animation_index >= len(icon_list):
                self.animation_index = 0

            selected_image = icon_list[self.animation_index]

        return selected_image

    @property
    def segment_size(self):
        """Synchronizes the item's segment size with global configuration."""
        self._segment_size = config.segment_size
        return self._segment_size

    # @segment_size.setter
    # def segment_size(self, value):
    #     """Caps the segment size at the total file size to prevent logical errors."""
    #     self._segment_size = value if value <= self.size else self.size
    

    @segment_size.setter
    def segment_size(self, value):
        """Caps the segment size at the total file size to prevent logical errors."""
        try:
            value = int(value)          # guard against str coming from SQLite
        except (TypeError, ValueError):
            value = self._segment_size
        self._segment_size = value if value <= self.size else self.size

    @property
    def sched_string(self):
        """Returns the formatted time string for scheduled downloads (e.g., '14:30')."""
        _, t = self.sched
        return t
    
    

    def update(self, url):
        """
        Retrieves remote headers and updates item properties including effective URL, 
        filename, extension, size, MIME type, and resumability.
        """
        ctx = "ITEM-UPDATE"
        if url in ('', None):
            return

        self.url = url
        headers = get_headers(url)
        log(f'Fetching metadata for: {url}', log_level=3, context=ctx)

        # Update properties only if the URL hasn't been changed by another thread
        if url == self.url:
            self.eff_url = headers.get('eff_url')
            self.status_code = headers.get('status_code', '')
            self.status_code_description = f"{self.status_code} - {translate_server_code(self.status_code)}"

            # Resolve filename from Content-Disposition, custom headers, or URL path
            name = ''
            if 'content-disposition' in headers:
                try:
                    # Extracts filename from 'attachment; filename="example.zip"'
                    name = headers['content-disposition'].split('=')[1].strip('"')
                except Exception:
                    pass
            elif 'file-name' in headers:
                name = headers['file-name']
            else:
                # Strip query parameters and extract the last part of the URL
                clean_url = url.split('?')[0] if '?' in url else url
                name = clean_url.split('/')[-1].strip()

            # Resolve file size from headers
            size = int(headers.get('content-length', 0))

            # Determine MIME type with fallback to extension guessing
            content_type = headers.get('content-type', 'N/A').split(';')[0]
            guessed_content_type = mimetypes.guess_type(name, strict=False)[0]
            
            if not content_type:
                content_type = guessed_content_type

            # Resolve file extension and verify naming
            ext = os.path.splitext(name)[1]
            if not ext:
                # Guess extension based on MIME type if missing from filename
                ext = mimetypes.guess_extension(content_type, strict=False) if content_type not in ('N/A', None) else ''
                if ext:
                    name += ext

            # Check for server-side resume support (Accept-Ranges)
            resumable = headers.get('accept-ranges', 'none') != 'none'

            # Apply resolved parameters to the object
            self.name = name
            self.ext = ext
            self.size = size
            self.type = content_type
            self.resumable = resumable
            
        log(f'Metadata update complete for {self.name}', log_level=1, context=ctx)

    def __repr__(self):
        """Returns a string representation of all object properties."""
        output = ''
        for k, v in self.__dict__.items():
            output += f"{k}: {v} \n"
        return output

    def delete_tempfiles(self):
        """Cleans up temporary files and directories associated with this download."""
        delete_file(self.temp_file)
        delete_folder(self.temp_folder)

        # Purge temporary audio buffers for DASH streams
        if self.type == 'dash':
            delete_file(self.audio_file)

