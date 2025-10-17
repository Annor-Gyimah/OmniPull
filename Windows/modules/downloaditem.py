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

from threading import Thread, Lock
from urllib.parse import urljoin
from modules.utils import validate_file_name, get_headers, translate_server_code, size_splitter, get_seg_size, log, \
    delete_file, delete_folder, save_json, load_json


# lock used with downloaded property
lock = Lock()


# define a class to hold all the required queues
class Communication:
    """it serve as communication between threads"""

    def __init__(self):
        # queues
        self.d_window = Queue()  # download window, required for log messages
        self.jobs = Queue()  # required for failed worker jobs

        # self.worker = []
        # self.data = []
        # self.brain = Queue()  # brain queue
        # self.thread_mngr = Queue()
        # self.completed_jobs = Queue()

    @staticmethod
    def clear(q):
        """clear individual queue"""
        try:
            while True:
                q.get_nowait()  # it will raise an exception when empty
        except:
            pass

    def reset(self):
        """clear all queues"""
        self.clear(self.d_window)
        self.clear(self.jobs)
        

    def log(self, *args):
        """print log msgs to download window"""
        s = ' '
        s = s.join(str(arg) for arg in args)
       
        s = s[:-1]  # remove last space

        if s[-1] != '\n':
            s += '\n'

        self.d_window.put(('log', s))


class Segment:
    def __init__(self, name=None, num=None, range=None, size=None, url=None, tempfile=None, seg_type='', merge=True):
        self.num = num
        self.size = size
        self.range = range
        self.downloaded = False
        self.completed = False  # done downloading and merging into tempfile
        self.name = name
        self.tempfile = tempfile
        self.headers = {}
        self.url = url
        self.seg_type = seg_type
        self.merge = merge

    def get_size(self):
        self.headers = get_headers(self.url)
        try:
            self.size = int(self.headers.get('content-length', 0))
            print('Segment num:', self.num, 'getting size:', self.size)
        except:
            pass
        return self.size

    def __repr__(self):
        return repr(self.__dict__)


class DownloadItem:

    # animation ['►►   ', '  ►►'] › ► ⤮ ⇴ ↹ ↯  ↮  ₡ ['⯈', '▼', '⯇', '▲']
    # ['⏵⏵', '  ⏵⏵'] ['›', '››', '›››', '››››', '›››››']
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
    }

    def __init__(self, id_=0, url='', name='', folder=''):
        self.id = id_
        self._name = name
        self.ext = ''

        self.folder = os.path.abspath(folder)

        self.url = url
        self.eff_url = ''
        self.playlist_url = ''
        self.original_url = self.url  

        self.size = 0
        self.resumable = False
        self.type = ''

        self._segment_size = config.segment_size

        self.live_connections = 0
        self._downloaded = 0
        self._status = config.Status.cancelled
        self.remaining_parts = 0

        self.q = Communication()  # queue

        # connection status
        self.status_code = 0
        self.status_code_description = ''

        # animation
        self.animation_index = 0  # self.id % 2  # to give it a different start point than neighbour items

        # audio
        self.audio_stream = None
        self.audio_url = None
        self.audio_size = 0
        self.is_audio = False

        # postprocessing callback is a string represent any function name need to be called after done downloading
        # this function must be available or imported in brain.py namespace
        self.callback = ''

        # schedule download
        self.sched = None  # should be time in (hours, minutes) tuple for scheduling download
        self.schedule_retries = 0


        # speed
        self._speed = 0
        self.prev_downloaded_value = 0
        self.speed_buffer = deque()  # store some speed readings for calculating average speed afterwards
        self.speed_timer = 0
        self.speed_refresh_rate = 1  # calculate speed every n time

        # segments
        self._segments = []

        # fragmented video parameters will be updated from video subclass object / update_param()
        self.fragment_base_url = None
        self.fragments = None

        # fragmented audio parameters will be updated from video subclass object / update_param()
        self.audio_fragment_base_url = None
        self.audio_fragments = None

        # protocol
        self.protocol = ''

        self.format_id = None
        self.audio_format_id = None

        # some downloads will have their progress and total size calculated and we can't store these values in self.size
        # since it will affect self.segments, workaround: use self.last_known_size, and self.last_known_progress so it
        # will be showed when loading self.d_list from disk, other solution is to load progress info
        
        self.last_known_size = 0
        self.last_known_progress = 0

        self.animation_timer = 0

        self.manifest_url = '' 

        self.in_queue = True
        self.queue_name = ""
        self.queue_position = 0  # order in queue
        self.queue_id = None  # unique identifier if you plan to support multiple queues
        self._progress = 0 

        self.engine = config.download_engine
        self.aria_gid = None
        self.audio_gid = None

        self._RE_BYTES_NUM = re.compile(r"([\d\.,]+)\s*([KMGTP]?i?B)?", re.IGNORECASE)








    def get_persistent_properties(self):
        """return a dict of important parameters to be saved in file"""
        a = dict(id=self.id, _name=self._name, ext=self.ext, folder=self.folder, url=self.url, eff_url=self.eff_url,
                 playlist_url=self.playlist_url, original_url=self.original_url, size=self.size, resumable=self.resumable,
                 _segment_size=self._segment_size, _downloaded=self._downloaded, _status=self._status,
                 remaining_parts=self.remaining_parts, audio_url=self.audio_url, audio_size=self.audio_size,
                 type=self.type, fragments=self.fragments, fragment_base_url=self.fragment_base_url,
                 audio_fragments=self.audio_fragments, audio_fragment_base_url=self.audio_fragment_base_url,
                 last_known_size=self.last_known_size, last_known_progress=self.last_known_progress,
                 protocol=self.protocol, manifest_url=self.manifest_url, scheduled=self.sched, schedule_retries=self.schedule_retries,
                 in_queue=self.in_queue, queue_id=self.queue_id, queue_name=self.queue_name, queue_position=self.queue_position,
                 engine=self.engine, aria_gid=self.aria_gid, audio_gid=self.audio_gid,
                )
        return a

    def reset_segments(self):
        """reset each segment properties "downloaded and merged" """
        for seg in self._segments:
            seg.downloaded = False
            seg.completed = False

    @property
    def segments(self):
        if not self._segments:
            # handle fragmented video
            if self.fragments:
                # print(self.fragments)
                # example 'fragments': [{'path': 'range/0-640'}, {'path': 'range/2197-63702', 'duration': 9.985},]
                self._segments = [Segment(name=os.path.join(self.temp_folder, str(i)), num=i, range=None, size=0,
                                          url=urljoin(self.fragment_base_url, x['path']), tempfile=self.temp_file)
                                  for i, x in enumerate(self.fragments)]

            else:
                if self.resumable and self.size:
                    # get list of ranges i.e. ['0-100', 101-2000' ... ]
                    range_list = size_splitter(self.size, self.segment_size)
                else:
                    range_list = [None]  # add None in a list to make one segment with range=None

                self._segments = [
                    Segment(name=os.path.join(self.temp_folder, str(i)), num=i, range=x, size=get_seg_size(x),
                            url=self.eff_url, tempfile=self.temp_file)
                    for i, x in enumerate(range_list)]

            # get an audio stream to be merged with dash video
            if self.type == 'dash':
                # handle fragmented audio
                if self.audio_fragments:
                    # example 'fragments': [{'path': 'range/0-640'}, {'path': 'range/2197-63702', 'duration': 9.985},]
                    audio_segments = [
                        Segment(name=os.path.join(self.temp_folder, str(i) + '_audio'), num=i, range=None, size=0,
                                url=urljoin(self.audio_fragment_base_url, x['path']), tempfile=self.audio_file)
                        for i, x in enumerate(self.audio_fragments)]

                else:
                    range_list = size_splitter(self.audio_size, self.segment_size)

                    audio_segments = [
                        Segment(name=os.path.join(self.temp_folder, str(i) + '_audio'), num=i, range=x,
                                size=get_seg_size(x), url=self.audio_url, tempfile=self.audio_file)
                        for i, x in enumerate(range_list) if get_seg_size(x) > 0
                    ]


                    # audio_segments = [
                    #     Segment(name=os.path.join(self.temp_folder, str(i) + '_audio'), num=i, range=x,
                    #             size=get_seg_size(x), url=self.audio_url, tempfile=self.audio_file)
                    #     for i, x in enumerate(range_list)]

                # append to main list
                self._segments += audio_segments

        return self._segments

    @segments.setter
    def segments(self, value):
        self._segments = value

    def save_progress_info(self):
        """save segments info to disk"""
        seg_list = [{'name': seg.name, 'downloaded':seg.downloaded, 'completed':seg.completed, 'size':seg.size} for seg in self.segments]
        file = os.path.join(self.temp_folder, 'progress_info.txt')
        save_json(file, seg_list)

    def load_progress_info(self):
        """load saved progress info from disk"""
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
        if self.type == 'dash':
            size = self.size + self.audio_size
        else:
            size = self.size

        # estimate size based on size of downloaded fragments
        if not size and self._segments:
            sizes = [seg.size for seg in self.segments if seg.size]
            if sizes:
                avg_seg_size = sum(sizes)//len(sizes)
                size = avg_seg_size * len(self._segments)  # estimated

        if not size:
            return self.last_known_size

        self.last_known_size = size  # to be loaded when restarting application
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
        m = self._RE_BYTES_NUM.search(s)
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

            with lock:
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
        if getattr(self, "status", None) != config.Status.downloading:
            with lock:
                self._speed = float(0.0)
            return float(self._speed or 0.0)

        # compute delta only occasionally to reduce noise
        now = time.time()
        time_passed = now - self.speed_timer if hasattr(self, "speed_timer") else 0.0
        if time_passed >= getattr(self, "speed_refresh_rate", 0.5):
            # sample new speed
            with lock:
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

            with lock:
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
            with lock:
                self._speed = float(max(0.0, v))
        except Exception:
            return

    # ---------- progress property (thread-safe, numeric) ----------
    @property
    def progress(self) -> float:
        """
        Compute percent downloaded:
        - If completed -> 100
        - If fragmented and total_size == 0: compute by finished segments / total segments (guard zero len)
        - else: downloaded/total_size * 100 (guard zero total_size)
        Always returns float (0.0 - 100.0).
        Maintains last_known_progress so that temporary 0 values don't reset UI.
        """
        try:
            # Completed -> 100
            if getattr(self, "status", None) == config.Status.completed:
                p = 100.0
            else:
                total = int(getattr(self, "total_size", 0) or getattr(self, "size", 0) or 0)
                downloaded = int(getattr(self, "_downloaded", getattr(self, "downloaded", 0) or 0))

                if total == 0:
                    # fragmented (HLS etc.) -> use segments if available
                    segs = getattr(self, "segments", None)
                    if segs and isinstance(segs, (list, tuple)) and len(segs) > 0:
                        finished = sum(1 for seg in segs if getattr(seg, "completed", False))
                        p = round((finished * 100.0) / max(1, len(segs)), 1)
                    else:
                        # no size & no segments: return last known progress (avoid flipping to 0)
                        p = float(getattr(self, "last_known_progress", 0.0) or 0.0)
                else:
                    p = round((float(downloaded) * 100.0) / float(total), 1)

            # clamp
            if p > 100.0:
                p = 100.0
            elif p < 0.0:
                p = 0.0

            # If p==0, return last known progress (so UI does not jump to indeterminate)
            if p == 0.0:
                # ensure last_known_progress exists
                last = float(getattr(self, "last_known_progress", 0.0) or 0.0)
                return last

            # update last_known_progress
            with lock:
                self.last_known_progress = float(p)

            return float(self.last_known_progress)
        except Exception:
            # defensive default
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
            with lock:
                self._progress = v
                if v > 0.0:
                    self.last_known_progress = v
        except Exception:
            return
        

    

    @property
    def time_left(self):
        if self.status == config.Status.downloading and self.total_size:
            return (self.total_size - self.downloaded) / self.speed if self.speed else -1
        else:
            return '---'

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        # import traceback
        # print(f"[status debug] {self.name} changing status from {self._status} to {value}")
        # traceback.print_stack(limit=3)  # See where it's coming from
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
        """set name and folder from full path"""
        self.folder, self._name = os.path.split(value)
        self.folder = os.path.abspath(self.folder)
        self._name = validate_file_name(self._name)

    @property
    def temp_file(self):
        """return temp file name including path"""
        name = f'_temp_{self.name}'.replace(' ', '_')
        return os.path.join(self.folder, name)

    @property
    def audio_file(self):
        """return temp file name including path"""
        name = f'audio_for_{self.name}'.replace(' ', '_')
        return os.path.join(self.folder, name)
    
    @audio_file.setter
    def audio_file(self, value):
        """set name and folder from full path"""
        self.folder, self._name = os.path.split(value)
        self.folder = os.path.abspath(self.folder)
        self._name = validate_file_name(self._name)

    @property
    def temp_folder(self):
        return f'{self.temp_file}_parts_'

    @property
    def i(self):
        # This is where we put the animation letter
        if self.sched:
            selected_image = self.sched_string
        else:
            icon_list = self.animation_icons.get(self.status, [''])

            if time.time() - self.animation_timer > 0.5:
                self.animation_timer = time.time()
                self.animation_index += 1

            if self.animation_index >= len(icon_list):
                self.animation_index = 0

            selected_image = icon_list[self.animation_index]

        return selected_image

    @property
    def segment_size(self):
        self._segment_size = config.segment_size
        return self._segment_size

    @segment_size.setter
    def segment_size(self, value):
        self._segment_size = value if value <= self.size else self.size
        # print('segment size = ', self._segment_size)



    @property
    def sched_string(self):
        _, t = self.sched
        return t  # e.g., "01:21"
    
    

    def update(self, url):
        """get headers and update properties (eff_url, name, ext, size, type, resumable, status code/description)"""

        if url in ('', None):
            return

        self.url = url
        headers = get_headers(url)
        log(f'update d parameters: headers', log_level=3)

        # update headers only if no other update thread created with different url
        if url == self.url:
            self.eff_url = headers.get('eff_url')
            self.status_code = headers.get('status_code', '')
            self.status_code_description = f"{self.status_code} - {translate_server_code(self.status_code)}"

            # update file info

            # get file name
            name = ''
            if 'content-disposition' in headers:  # example content-disposition : attachment; filename=ffmpeg.zip
                try:
                    name = headers['content-disposition'].split('=')[1].strip('"')
                except:
                    pass

            elif 'file-name' in headers:
                name = headers['file-name']
            else:
                clean_url = url.split('?')[0] if '?' in url else url
                name = clean_url.split('/')[-1].strip()

            # file size
            size = int(headers.get('content-length', 0))

            # type
            content_type = headers.get('content-type', 'N/A').split(';')[0]
            # fallback, guess type from file name extension
            guessed_content_type = mimetypes.guess_type(name, strict=False)[0]
            if not content_type:
                content_type = guessed_content_type

            # file extension:
            ext = os.path.splitext(name)[1]
            if not ext:  # if no ext in file name
                ext = mimetypes.guess_extension(content_type, strict=False) if content_type not in ('N/A', None) else ''
                
                if ext:
                    name += ext

            # check for resume support
            resumable = headers.get('accept-ranges', 'none') != 'none'

            self.name = name
            self.ext = ext
            self.size = size
            self.type = content_type
            self.resumable = resumable
        log(f'Done with url {url}', log_level=1)

    def __repr__(self):
        """used with functions like print, it will return all properties in this object"""
        output = ''
        for k, v in self.__dict__.items():
            output += f"{k}: {v} \n"
        return output

    def delete_tempfiles(self):
        """delete temp files and folder for a given download item"""
        delete_file(self.temp_file)
        delete_folder(self.temp_folder)

        if self.type == 'dash':
            delete_file(self.audio_file)

