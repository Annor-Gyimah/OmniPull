
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
import re
import sys
import copy
import json
import math
import time
import shlex
import shutil
import asyncio
import zipfile
import platform
import subprocess
from modules import config
from typing import Dict, Any
from urllib.parse import urljoin
from modules.threadpool import executor
from modules.config import get_effective_ffmpeg
from modules.downloaditem import DownloadItem, Segment
from modules.utils import log, validate_file_name, get_headers, size_format, run_command, \
    delete_file, download, process_thumbnail, popup, delete_folder


# yt-dlp
ytdl = None  # yt-dlp will be imported in a separate thread to save loading time


class Logger(object):
    """used for capturing yt-dlp stdout/stderr output"""

    def debug(self, msg):
        log(msg)

    def error(self, msg):
        log(msg)

    def warning(self, msg):
        log(msg)

    def __repr__(self):
        return "yt-dlp Logger"



def get_ytdl_options():
    ydl_opts = {
        'prefer_insecure': True, 
        'no_warnings': config.ytdlp_config.get('no_warnings', True),
        'logger': Logger(),
        'formats': 'bv*+ba/best',
        'listformats': config.ytdlp_config.get('list_formats', False),
        'noplaylist': config.ytdlp_config.get('no_playlist', True),
        'ignoreerrors': config.ytdlp_config.get('ignore_errors', True),
        'cookies': config.ytdlp_config['cookiesfile'],
        'verbose': True,


        
    }
    if config.proxy != "":
        proxy_url = config.proxy
        if config.proxy_user and config.proxy_pass:
            # Inject basic auth into the proxy URL
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(proxy_url)
            proxy_url = urlunparse(parsed._replace(netloc=f"{config.proxy_user}:{config.proxy_pass}@{parsed.hostname}:{parsed.port}"))

        ydl_opts['proxy'] = proxy_url

    ydl_opts['no_playlist'] = True

    return ydl_opts






# def extract_info_blocking(url, ydl_opts):
#     import yt_dlp as ytdl
#     with ytdl.YoutubeDL(ydl_opts) as ydl:
#         return ydl.extract_info(url, download=False, process=True)
    
def _ydl_opts_to_args(ydl_opts: dict, allow_listformats: bool = False) -> list[str]:
    """
    Convert ydl_opts to CLI args. If allow_listformats is False, do not emit --list-formats
    because it prints human output and breaks --dump-single-json.
    """
    args = []

    # Cookie file
    cookiefile = ydl_opts.get("cookiefile") or ydl_opts.get("cookies") or ydl_opts.get("cookiesfile")
    if cookiefile:
        args += ["--cookies", str(cookiefile)]

    # Proxy
    if ydl_opts.get("proxy"):
        args += ["--proxy", str(ydl_opts["proxy"])]

    # No warnings
    if ydl_opts.get("no_warnings", False):
        args.append("--no-warnings")

    # Ignore errors
    if ydl_opts.get("ignore_errors", False):
        args.append("--ignore-errors")

    # Playlist handling
    if ydl_opts.get("noplaylist", False) or ydl_opts.get("no_playlist", False):
        args.append("--no-playlist")

    # List formats: only add if explicitly allowed (we won't allow it when requesting JSON)
    if allow_listformats and ydl_opts.get("listformats", False):
        args.append("--list-formats")

    # Formats / format
    fmt = ydl_opts.get("formats") or ydl_opts.get("formats")
    if fmt:
        args += ["-f", str(fmt)]

    # Prefer insecure
    if ydl_opts.get("prefer_insecure", False):
        args.append("--prefer-insecure")

    return args

# Helper: turn bytes into human-readable size
def _human_filesize(num_bytes):
    try:
        if num_bytes is None:
            return ""
        n = float(num_bytes)
    except Exception:
        return ""
    if n <= 0:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = int(math.floor(math.log(n, 1024)))
    idx = min(idx, len(units) - 1)
    value = n / (1024 ** idx)
    # show one decimal for >=KB
    if idx == 0:
        return f"{int(value)}{units[idx]}"
    else:
        return f"{value:.1f}{units[idx]}"

# ANSI color helpers
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"

def formats_to_table_html(info: dict) -> str:
    formats = info.get("formats", [])
    if not formats:
        return '<span style="color: orange;">[yt-dlp] No formats available</span>'

    header = (
        f"<b>{'ID':<8}{'EXT':<6}{'RES':<10}{'FPS':<5}{'VCODEC':<15}{'ACODEC':<10}{'SIZE':<10}{'TBR':<6}</b>"
    )
    lines = [header, "-" * 80]

    for f in formats:
        fid = f.get("format_id", "")
        ext = f.get("ext", "")
        res = f.get("resolution", "") or f"{f.get('width', '')}x{f.get('height', '')}"
        fps = str(f.get("fps", "")) if f.get("fps") else ""
        vcodec = f.get("vcodec", "unknown")
        acodec = f.get("acodec", "unknown")
        size = f.get("filesize") or f.get("filesize_approx") or ""
        if isinstance(size, int):
            size = f"{size/1024/1024:.1f}MiB"
        tbr = str(f.get("tbr", ""))

        line = (
            f"{fid:<8}"
            f"<span style='color: teal;'>{ext:<6}</span>"
            f"{res:<10}{fps:<5}"
            f"<span style='color: green;'>{vcodec:<15}</span>"
            f"<span style='color: green;'>{acodec:<10}</span>"
            f"<span style='color: blue;'>{size:<10}</span>"
            f"{tbr:<6}"
        )
        lines.append(line)

    return "<pre>" + "\n".join(lines) + "</pre>"




def _run_ytdlp_python_api(url: str, ydl_opts: dict):
    import yt_dlp as ytdl
    safe_opts = dict(ydl_opts)
    safe_opts.pop("logger", None)
    with ytdl.YoutubeDL(safe_opts) as ydl:
        return ydl.extract_info(url, download=False, process=True)






def extract_info_blocking(url: str, ydl_opts: dict = None, exe_timeout: float = 15.0):
    """
    Extract info for `url` using either the configured standalone exe or the Python API.

    If listformats=True in ydl_opts:
      - prefer Python API (structured formats)
      - log() the human-readable formats table in addition to returning JSON
    """
    if ydl_opts is None:
        ydl_opts = get_ytdl_options()

    wants_listformats = bool(ydl_opts.get("listformats", False))

    # -----------------------
    # Executable path
    # -----------------------
    if config.get_effective_ytdlp() and getattr(config, "use_ytdlp_exe", False):
        exe_path = config.get_effective_ytdlp()
        if not exe_path or not os.path.isfile(exe_path):
            raise FileNotFoundError(f"yt-dlp executable not found: {exe_path}")

        if wants_listformats:
            # Force Python API instead so we can pretty-print formats
            log("[yt-dlp.exe] Using Python API for listformats")
            info = _run_ytdlp_python_api(url, ydl_opts)
            log(formats_to_table_html(info))   # dump the table to your custom log
            return info

        # Normal JSON extraction via exe
        cli_args = _ydl_opts_to_args(ydl_opts, allow_listformats=False)
        forced = ["--dump-single-json", "--no-warnings", "--no-progress"]
        cmd = [exe_path] + cli_args + forced + [url]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=exe_timeout)
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                pass

        # salvage JSON if mixed output
        combined = stdout + "\n" + stderr
        first_lbrace = combined.find("{")
        last_rbrace = combined.rfind("}")
        if first_lbrace != -1 and last_rbrace > first_lbrace:
            try:
                return json.loads(combined[first_lbrace:last_rbrace + 1])
            except json.JSONDecodeError:
                pass

        raise RuntimeError(
            f"yt-dlp executable did not return valid JSON.\n"
            f"Exit code: {proc.returncode}\n"
            f"Command: {shlex.join(cmd)}\n"
            f"Stdout:\n{stdout[:500]}\n\nStderr:\n{stderr[:500]}"
        )

    # -----------------------
    # Python API fallback
    # -----------------------
    log("[yt-dlp] Using Python API")
    info = _run_ytdlp_python_api(url, ydl_opts)

    if wants_listformats:
        log(formats_to_table_html(info))

    return info

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
import re
import sys
import copy
import json
import math
import time
import shlex
import shutil
import asyncio
import zipfile
import platform
import subprocess
from pathlib import Path
from modules import config
from typing import Dict, Any
from urllib.parse import urljoin
from modules.threadpool import executor
from modules.config import get_effective_ffmpeg
from modules.downloaditem import DownloadItem, Segment
from modules.utils import log, validate_file_name, get_headers, size_format, run_command, \
    delete_file, download, process_thumbnail, popup, delete_folder


# yt-dlp
ytdl = None  # yt-dlp will be imported in a separate thread to save loading time


class Logger(object):
    """used for capturing yt-dlp stdout/stderr output"""

    def debug(self, msg):
        log(msg)

    def error(self, msg):
        log(msg)

    def warning(self, msg):
        log(msg)

    def __repr__(self):
        return "yt-dlp Logger"



def get_ytdl_options():
    ydl_opts = {
        'prefer_insecure': True, 
        'no_warnings': config.ytdlp_config.get('no_warnings', True),
        'logger': Logger(),
        'formats': 'bv*+ba/best',
        'listformats': config.ytdlp_config.get('list_formats', False),
        'noplaylist': config.ytdlp_config.get('no_playlist', True),
        'ignoreerrors': config.ytdlp_config.get('ignore_errors', True),
        'cookies': config.ytdlp_config['cookiesfile'],
        'verbose': True,


        
    }
    if config.proxy != "":
        proxy_url = config.proxy
        if config.proxy_user and config.proxy_pass:
            # Inject basic auth into the proxy URL
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(proxy_url)
            proxy_url = urlunparse(parsed._replace(netloc=f"{config.proxy_user}:{config.proxy_pass}@{parsed.hostname}:{parsed.port}"))

        ydl_opts['proxy'] = proxy_url

    ydl_opts['no_playlist'] = True

    return ydl_opts






# def extract_info_blocking(url, ydl_opts):
#     import yt_dlp as ytdl
#     with ytdl.YoutubeDL(ydl_opts) as ydl:
#         return ydl.extract_info(url, download=False, process=True)
    
def _ydl_opts_to_args(ydl_opts: dict, allow_listformats: bool = False) -> list[str]:
    """
    Convert ydl_opts to CLI args. If allow_listformats is False, do not emit --list-formats
    because it prints human output and breaks --dump-single-json.
    """
    args = []

    # Cookie file
    cookiefile = ydl_opts.get("cookiefile") or ydl_opts.get("cookies") or ydl_opts.get("cookiesfile")
    if cookiefile:
        args += ["--cookies", str(cookiefile)]

    # Proxy
    if ydl_opts.get("proxy"):
        args += ["--proxy", str(ydl_opts["proxy"])]

    # No warnings
    if ydl_opts.get("no_warnings", False):
        args.append("--no-warnings")

    # Ignore errors
    if ydl_opts.get("ignore_errors", False):
        args.append("--ignore-errors")

    # Playlist handling
    if ydl_opts.get("noplaylist", False) or ydl_opts.get("no_playlist", False):
        args.append("--no-playlist")

    # List formats: only add if explicitly allowed (we won't allow it when requesting JSON)
    if allow_listformats and ydl_opts.get("listformats", False):
        args.append("--list-formats")

    # Formats / format
    fmt = ydl_opts.get("formats") or ydl_opts.get("formats")
    if fmt:
        args += ["-f", str(fmt)]

    # Prefer insecure
    if ydl_opts.get("prefer_insecure", False):
        args.append("--prefer-insecure")

    return args

# Helper: turn bytes into human-readable size
def _human_filesize(num_bytes):
    try:
        if num_bytes is None:
            return ""
        n = float(num_bytes)
    except Exception:
        return ""
    if n <= 0:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = int(math.floor(math.log(n, 1024)))
    idx = min(idx, len(units) - 1)
    value = n / (1024 ** idx)
    # show one decimal for >=KB
    if idx == 0:
        return f"{int(value)}{units[idx]}"
    else:
        return f"{value:.1f}{units[idx]}"

# ANSI color helpers
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"

def formats_to_table_html(info: dict) -> str:
    formats = info.get("formats", [])
    if not formats:
        return '<span style="color: orange;">[yt-dlp] No formats available</span>'

    header = (
        f"<b>{'ID':<8}{'EXT':<6}{'RES':<10}{'FPS':<5}{'VCODEC':<15}{'ACODEC':<10}{'SIZE':<10}{'TBR':<6}</b>"
    )
    lines = [header, "-" * 80]

    for f in formats:
        fid = f.get("format_id", "")
        ext = f.get("ext", "")
        res = f.get("resolution", "") or f"{f.get('width', '')}x{f.get('height', '')}"
        fps = str(f.get("fps", "")) if f.get("fps") else ""
        vcodec = f.get("vcodec", "unknown")
        acodec = f.get("acodec", "unknown")
        size = f.get("filesize") or f.get("filesize_approx") or ""
        if isinstance(size, int):
            size = f"{size/1024/1024:.1f}MiB"
        tbr = str(f.get("tbr", ""))

        line = (
            f"{fid:<8}"
            f"<span style='color: teal;'>{ext:<6}</span>"
            f"{res:<10}{fps:<5}"
            f"<span style='color: green;'>{vcodec:<15}</span>"
            f"<span style='color: green;'>{acodec:<10}</span>"
            f"<span style='color: blue;'>{size:<10}</span>"
            f"{tbr:<6}"
        )
        lines.append(line)

    return "<pre>" + "\n".join(lines) + "</pre>"




def _run_ytdlp_python_api(url: str, ydl_opts: dict):
    import yt_dlp as ytdl
    safe_opts = dict(ydl_opts)
    safe_opts.pop("logger", None)
    with ytdl.YoutubeDL(safe_opts) as ydl:
        return ydl.extract_info(url, download=False, process=True)






def extract_info_blocking(url: str, ydl_opts: dict = None, exe_timeout: float = 15.0):
    """
    Extract info for `url` using either the configured standalone exe or the Python API.

    If listformats=True in ydl_opts:
      - prefer Python API (structured formats)
      - log() the human-readable formats table in addition to returning JSON
    """
    if ydl_opts is None:
        ydl_opts = get_ytdl_options()

    wants_listformats = bool(ydl_opts.get("listformats", False))

    # -----------------------
    # Executable path
    # -----------------------
    if config.get_effective_ytdlp() and getattr(config, "use_ytdlp_exe", False):
        exe_path = config.get_effective_ytdlp()
        if not exe_path or not os.path.isfile(exe_path):
            raise FileNotFoundError(f"yt-dlp executable not found: {exe_path}")

        if wants_listformats:
            # Force Python API instead so we can pretty-print formats
            log("[yt-dlp.exe] Using Python API for listformats")
            info = _run_ytdlp_python_api(url, ydl_opts)
            log(formats_to_table_html(info))   # dump the table to your custom log
            return info

        # Normal JSON extraction via exe
        cli_args = _ydl_opts_to_args(ydl_opts, allow_listformats=False)
        forced = ["--dump-single-json", "--no-warnings", "--no-progress"]
        cmd = [exe_path] + cli_args + forced + [url]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=exe_timeout)
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                pass

        # salvage JSON if mixed output
        combined = stdout + "\n" + stderr
        first_lbrace = combined.find("{")
        last_rbrace = combined.rfind("}")
        if first_lbrace != -1 and last_rbrace > first_lbrace:
            try:
                return json.loads(combined[first_lbrace:last_rbrace + 1])
            except json.JSONDecodeError:
                pass

        raise RuntimeError(
            f"yt-dlp executable did not return valid JSON.\n"
            f"Exit code: {proc.returncode}\n"
            f"Command: {shlex.join(cmd)}\n"
            f"Stdout:\n{stdout[:500]}\n\nStderr:\n{stderr[:500]}"
        )

    # -----------------------
    # Python API fallback
    # -----------------------
    log("[yt-dlp] Using Python API")
    info = _run_ytdlp_python_api(url, ydl_opts)

    if wants_listformats:
        log(formats_to_table_html(info))

    return info



class Video(DownloadItem):
    """represent a youtube video object, interface for yt-dlp"""

    def __init__(self, url, vid_info=None, get_size=True):
        super().__init__(folder=config.download_folder)
        self.url = url
        self.resumable = True
        self.vid_info = vid_info  # a yt-dlp dictionary contains video information

        # let yt-dlp fetch video info
        if self.vid_info is None:
            raise ValueError("vid_info must be provided when using Video.__init__. Use Video.create() instead.")
            # with ytdl.YoutubeDL(get_ytdl_options()) as ydl:
            #     self.vid_info = ydl.extract_info(self.url, download=False, process=True)

        self.webpage_url = url  # self.vid_info.get('webpage_url')
        self.title = validate_file_name(self.vid_info.get('title', f'video{int(time.time())}'))
        self.name = self.title

        # streams
        self.stream_names = []  # names in a list
        self.raw_stream_names = [] # names but without size
        self.stream_list = []  # streams in a list
        self.video_streams = {}
        self.mp4_videos = {}
        self.other_videos = {}
        self.audio_streams = {}
        self._streams = {}
        self.raw_streams = {}

        self.stream_menu = []  # it will be shown in video quality combo box != self.stream.names
        self.raw_stream_menu = [] # same as self.stream_menu but without size
        self._selected_stream = None

        self.thumbnail_url = self.vid_info.get('thumbnail', '')
        self.thumbnail = None  # base64 string

        # self.audio_url = None  # None for non dash videos
        # self.audio_size = 0

        self.setup()

    def setup(self):
        self._process_streams()


    @classmethod
    async def create(cls, url, get_size=True):
        loop = asyncio.get_running_loop()
        ydl_opts = get_ytdl_options()
        vid_info = await loop.run_in_executor(executor, extract_info_blocking, url, ydl_opts)
        return cls(url, vid_info=vid_info, get_size=get_size)
    
    @classmethod
    async def extract_metadata(cls, url):
        loop = asyncio.get_running_loop()
        ydl_opts = get_ytdl_options()
        return await loop.run_in_executor(executor, extract_info_blocking, url, ydl_opts)


    def url_expired(self) -> bool:
        """
        Check if video or audio stream URL is likely expired.
        This is a rough heuristic, based on age or erroring headers (advanced).
        """
        # Option 1: Timestamp check (you can store a fetched time and compare)
        max_age_secs = 3600 * 3  # assume 3 hours max age
        return (time.time() - getattr(self, "last_update", 0)) > max_age_secs


    def _process_streams(self):
        """ Create Stream object lists"""
        
    
        if not self.vid_info or 'formats' not in self.vid_info:
            log(f"[Video] Skipping: no 'formats' found for {self.url}")
            self._streams = {}
            self.stream_names = []
            self.selected_stream = None
            return
        

        
    
        all_streams = [Stream(x) for x in self.vid_info['formats']]

        # prepare some categories
        normal_streams = {stream.raw_name: stream for stream in all_streams if stream.mediatype == 'normal'}
        dash_streams = {stream.raw_name: stream for stream in all_streams if stream.mediatype == 'dash'}

        # normal streams will overwrite same streams names in dash
        video_streams = {**dash_streams, **normal_streams}

        # sort streams based on quality
        video_streams = {k: v for k, v in sorted(video_streams.items(), key=lambda item: item[1].quality, reverse=True)}

        # sort based on mp4 streams first
        mp4_videos = {stream.name: stream for stream in video_streams.values() if stream.extension == 'mp4'}
        other_videos = {stream.name: stream for stream in video_streams.values() if stream.extension != 'mp4'}
        video_streams = {**mp4_videos, **other_videos}

        audio_streams = {stream.name: stream for stream in all_streams if stream.mediatype == 'audio'}

        # collect all in one dictionary of stream.name: stream pairs
        streams = {**video_streams, **audio_streams}

        stream_menu = ['● Video streams:                     '] + list(mp4_videos.keys()) + list(other_videos.keys()) \
                    + ['', '● Audio streams:                 '] + list(audio_streams.keys())

        # assign variables
        self.stream_list = list(streams.values())
        self.stream_names = [stream.name for stream in self.stream_list]
        self.raw_stream_names = [stream.raw_name for stream in self.stream_list]
        self.video_streams = video_streams
        self.mp4_videos = mp4_videos
        self.other_videos = other_videos
        self.audio_streams = audio_streams

        self._streams = streams
        self.raw_streams = {stream.raw_name: stream for stream in streams.values()}
        self.stream_menu = stream_menu
        self.raw_stream_menu = [x.rsplit(' -', 1)[0] for x in stream_menu]

    @property
    def streams(self):
        """ Returns dictionary of all streams sorted  key=stream.name, value=stream object"""
        if not self._streams:
            self._process_streams()

        return self._streams

    @property
    def selected_stream_index(self):
        return self.stream_list.index(self.selected_stream)

    @property
    def selected_stream(self):
        if not self._selected_stream:
            self._selected_stream = self.stream_list[0]  # select first stream

        return self._selected_stream

    @selected_stream.setter
    def selected_stream(self, stream):
        if type(stream) is not Stream:
            raise TypeError

        self._selected_stream = stream

        self.update_param()

    def get_thumbnail(self):
        if self.thumbnail_url and not self.thumbnail:
            self.thumbnail = process_thumbnail(self.thumbnail_url)

    def update_param(self):
        # do some parameter updates
        stream = self.selected_stream
        self.name = self.title + '.' + stream.extension
        self.eff_url = stream.url
        self.type = stream.mediatype
        self.size = stream.size
        self.fragment_base_url = stream.fragment_base_url
        self.fragments = stream.fragments
        self.protocol = stream.protocol
        self.format_id = stream.format_id
        self.manifest_url = stream.manifest_url
        self.last_update = time.time()
        
        
        # ---- choose an audio stream robustly ----
        # compatibility map by video extension
        compat = {
            "mp4":  {"m4a", "mp4", "aac"},
            "m4v":  {"m4a", "mp4", "aac"},
            "webm": {"webm", "opus"},
            "mkv":  {"webm", "opus", "m4a", "aac"},  # mkv can mux many
            "mov":  {"m4a", "mp4", "aac"},
            "ts":   {"aac", "mp4", "m4a"},
        }
        vext = (stream.extension or "").lower()
        allowed_aext = compat.get(vext, {"m4a", "aac", "mp4", "webm", "opus"})

        # candidate audios: same container family OR generally muxable
        audio_candidates = [
            a for a in self.audio_streams.values()
            if (a.acodec != "none") and ((a.extension or "").lower() in allowed_aext)
        ]

        if not audio_candidates:
            # fallback: any audio at all
            audio_candidates = [a for a in self.audio_streams.values() if a.acodec != "none"]

        if not audio_candidates:
            log("No suitable audio stream found!")
            return

        # Prefer higher abr / tbr, then by protocol closeness (same as video), then by presence of fragments
        def score(a):
            abr = (a.abr or 0)
            tbr = (a.tbr or 0)
            # prefer same protocol family
            proto_bonus = 10 if (a.protocol or "").split("+")[0] == (stream.protocol or "").split("+")[0] else 0
            # de-prioritize weird containers
            ext_bonus = 5 if (a.extension or "").lower() in allowed_aext else 0
            return (abr or tbr, proto_bonus, ext_bonus)

        audio_stream = sorted(audio_candidates, key=score, reverse=True)[0]

        # ⚠️ DO NOT require size>0 here; HLS/DASH audio has size==0 by design in the Stream.__init__
        self.audio_stream = audio_stream
        self.audio_url = audio_stream.url
        self.audio_size = audio_stream.size
        self.audio_fragment_base_url = audio_stream.fragment_base_url
        self.audio_fragments = audio_stream.fragments
        self.audio_format_id = audio_stream.format_id


        


        # # Filter audio streams based on extension compatibility
        # audio_streams = [audio for audio in self.audio_streams.values()
        #                 if audio.extension == stream.extension or
        #                 (audio.extension == 'm4a' and stream.extension == 'mp4')]

        # if not audio_streams:  # Ensure there are available audio streams
        #     log("No suitable audio stream found!")
        #     return

        # audio_stream = None  # Initialize as None
        # if stream.mediatype == 'dash' and self.protocol.startswith('http'):
        #     # If it's DASH video and protocol is HTTP, try to select audio stream by index
        #     for idx in [1, 2, 3, 4]:  # Try index 2 first, then 3
        #         if idx < len(audio_streams) and audio_streams[idx].size > 0:
        #             audio_stream = audio_streams[idx]
        #             break
        # else:
        #     # For other protocols, select the first valid audio stream
        #     # If protocol is 'm3u8_native' or other formats
        #     audio_stream = audio_streams[0]
        #     # for audio in audio_streams:
        #     #     if audio.size > 0:
        #     #         audio_stream = audio
        #     #         break

        # if audio_stream is None:
        #     log("No valid audio stream found with non-zero size!")
        #     return  # Handle the case where no valid audio stream is found

        # log(audio_stream)
        # self.audio_stream = audio_stream
        # self.audio_url = audio_stream.url
        # self.audio_size = audio_stream.size
        # self.audio_fragment_base_url = audio_stream.fragment_base_url
        # self.audio_fragments = audio_stream.fragments
        # self.audio_format_id = audio_stream.format_id

    def clone(self):
        v = Video(self.url)
        v.name = self.name
        v.type = self.type
        v.protocol = self.protocol
        v.size = self.size
        v.ext = self.ext
        v.resumable = self.resumable
        v.vid_info = copy.deepcopy(self.vid_info)
        v.stream_names = copy.deepcopy(self.stream_names)
        v.selected_stream_name = self.selected_stream_name
        v._selected_stream = copy.deepcopy(self._selected_stream)  # ✅ better
        v._segments = self._segments.copy() if self._segments else []
        v.audio_url = self.audio_url
        v.audio_size = self.audio_size
        v.audio_fragments = copy.deepcopy(self.audio_fragments)
        v.audio_fragment_base_url = self.audio_fragment_base_url
        return v


    

class Stream:
    def __init__(self, stream_info):
        # fetch data from yt-dlp stream_info dictionary
        self.format_id = stream_info.get('format_id', None)
        self.url = stream_info.get('url', None)
        self.player_url = stream_info.get('player_url', None)
        self.extension = stream_info.get('ext', None)
        self.width = stream_info.get('width', None)
        self.fps = stream_info.get('fps', None)
        self.height = stream_info.get('height', 0)
        self.format_note = stream_info.get('format_note', None)
        self.acodec = stream_info.get('acodec', None)
        self.abr = stream_info.get('abr', 0)
        self.size = stream_info.get('filesize', None)
        self.tbr = stream_info.get('tbr', None)
        # self.quality = stream_info.get('quality', None)
        self.vcodec = stream_info.get('vcodec', None)
        self.res = stream_info.get('resolution', None)
        self.downloader_options = stream_info.get('downloader_options', None)
        self.format = stream_info.get('format', None)
        self.container = stream_info.get('container', None)

        # protocol
        self.protocol = stream_info.get('protocol', '')

        # calculate some values
        #self.rawbitrate = stream_info.get('abr', 0) * 1024
        self._mediatype = None
        self.resolution = f'{self.width}x{self.height}' if (self.width and self.height) else ''

        # fragmented video streams
        self.fragment_base_url = stream_info.get('fragment_base_url', None)
        self.fragments = stream_info.get('fragments', None)

        # get missing size
        if self.fragments or 'm3u8' in self.protocol:
            # ignore fragmented streams, since the size coming from headers is for first fragment not whole file
            self.size = 0
        if not isinstance(self.size, int):
            self.size = self.get_size()

        # hls stream specific
        self.manifest_url = stream_info.get('manifest_url', '')

        # print(self.name, self.size, isinstance(self.size, int))

    def get_size(self):
        headers = get_headers(self.url)
        size = int(headers.get('content-length', 0))
        print('stream.get_size()>', self.name)
        return size

    @property
    def name(self):
        return f'      ›  {self.extension} - {self.quality} - {size_format(self.size)}'  # ¤ » ›

    @property
    def raw_name(self):
        return f'      ›  {self.extension} - {self.quality}'

    @property
    def quality(self):
        try:
            if self.mediatype == 'audio':
                return int(self.abr)
            else:
                return int(self.height)
        except:
            return 0

    def __repr__(self, include_size=True):
        return self.name

    @property
    def mediatype(self):
        if not self._mediatype:
            if self.vcodec == 'none':
                self._mediatype = 'audio'
            elif self.acodec == 'none':
                self._mediatype = 'dash'
            else:
                self._mediatype = 'normal'

        return self._mediatype


def download_ffmpeg(destination=config.sett_folder):
    """it should download ffmpeg.exe for windows os"""

    # set download folder
    config.ffmpeg_download_folder = destination

    # first check windows 32 or 64
    import platform
    # ends with 86 for 32 bit and 64 for 64 bit i.e. Win7-64: AMD64 and Vista-32: x86
    if platform.machine().endswith('64'):
        # 64 bit link
        url = 'https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v6.1/ffmpeg-6.1-win-64.zip'
    else:
        # 32 bit link
        url = 'https://www.videohelp.com/download/ffmpeg-4.3.1-win32-static.zip'

    log('downloading: ', url)

    # create a download object, will store ffmpeg in setting folder
    # print('config.sett_folder = ', config.sett_folder)
    d = DownloadItem(url=url, folder=config.ffmpeg_download_folder)
    d.update(url)
    d.name = 'ffmpeg.zip'  # must rename it for unzip to find it
    # print('d.folder = ', d.folder)

    # post download
    d.callback = 'unzip_ffmpeg'

    # send download request to main window
    config.main_window_q.put(('download', (d, False)))


def download_aria2c_with_wget(url, save_dir, filename):
    """Download aria2c.zip using python-wget and update GUI progress if emitter is provided."""
    os.makedirs(save_dir, exist_ok=True)
    output_path = os.path.join(save_dir, filename)
    import wget

    try:
        log(f"[aria2c] Downloading aria2c from {url}")
        downloaded_path = wget.download(url, out=output_path)
        log(f"[aria2c] Download complete: {downloaded_path}")
        if os.path.exists(output_path):
            unzip_aria2c()
        return True
    except Exception as e:
        log(f"[aria2c] Download failed: {e}")
        return False

def download_aria2c(destination=config.sett_folder):
    import platform
    if platform.machine().endswith('64'):
        url = 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip'
    else:
        url = 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-32bit-build1.zip'

    filename = "aria2c.zip"
    download_aria2c_with_wget(url, destination, filename)




def unzip_ffmpeg():
    log('unzip_ffmpeg:', 'unzipping')
    try:
        folder = config.ffmpeg_download_folder
        file_name = os.path.join(folder, 'ffmpeg.zip')

        # List folders before extraction
        before = set(os.listdir(folder))

        # Extract zip file
        with zipfile.ZipFile(file_name, 'r') as zip_ref:
            zip_ref.extractall(folder)

        # List folders after extraction
        after = set(os.listdir(folder))
        new_items = after - before

        # Find the new folder (could be more than one, but usually just one)
        extracted_folder = None
        for item in new_items:
            path = os.path.join(folder, item)
            if os.path.isdir(path):
                extracted_folder = path
                break

        log('ffmpeg update:', f'Extracted folder: {extracted_folder}')

        # Optionally, move/copy ffmpeg.exe from extracted_folder to folder, or update config
        # Example: find ffmpeg.exe inside extracted_folder
        ffmpeg_exe = None
        for root, dirs, files in os.walk(extracted_folder):
            for file in files:
                if file.lower() == "ffmpeg":
                    ffmpeg_exe = os.path.join(root, file)
                    break
            if ffmpeg_exe:
                break

        if ffmpeg_exe:
            dest = os.path.join(folder, "ffmpeg")
            shutil.move(ffmpeg_exe, dest)
            log('ffmpeg update:', f'ffmpeg moved to {dest}')
        else:
            log('ffmpeg update:', 'ffmpeg not found in extracted folder')

        # Clean up zip file
        delete_file(file_name)
        delete_folder(extracted_folder, verbose=True)
        
        param = dict(title='Ffmpeg Info', msg='Ffmpeg is now available. Please try download again.', type_='info')
        config.main_window_q.put(('popup', param))
        log('ffmpeg update:', 'ffmpeg .. is ready at: ', folder)
    except Exception as e:
        log('unzip_ffmpeg: error ', e)




def unzip_aria2c():
    log('unzip_aria2c:', 'unzipping')
    config.aria2_download_folder = config.sett_folder
    try:
        file_name = os.path.join(config.aria2_download_folder, 'aria2c.zip')

        # Extract the zip
        with zipfile.ZipFile(file_name, 'r') as zip_ref:
            zip_ref.extractall(config.aria2_download_folder)

        # Find the extracted folder (assumes only one folder is extracted)
        extracted_items = os.listdir(config.aria2_download_folder)
        extracted_folder = next((item for item in extracted_items
                                 if os.path.isdir(os.path.join(config.aria2_download_folder, item)) and 'aria2' in item), None)

        if extracted_folder:
            extracted_folder_path = os.path.join(config.aria2_download_folder, extracted_folder)
            exe_path = os.path.join(extracted_folder_path, 'aria2c.exe')
            dest_path = os.path.join(config.aria2_download_folder, 'aria2c.exe')

            # Move aria2c.exe to the parent folder
            if os.path.exists(exe_path):
                shutil.move(exe_path, dest_path)
                log('aria2c update:', f'aria2c.exe moved to {config.aria2_download_folder}')
            else:
                log('aria2c update:', 'aria2c.exe not found in extracted folder')
            shutil.rmtree(extracted_folder_path)

        # Delete zip file
        log('aria2c update:', 'delete zip file')
        delete_file(file_name)
        # os.removedirs(extracted_folder)

        log('aria2c update:', 'aria2c is ready at:', config.aria2_download_folder)
        config.aria2_verified = True
        param = dict(title='Aria2c Update', msg='Aria2c is now available. Please try download again.', type_='info')
        config.main_window_q.put(('popup', param))

    except Exception as e:
        log('unzip_aria2c: error', e)



def check_ffmpeg():
    """Check for ffmpeg availability, and cache result to avoid re-checking."""

    # ✅ If previously verified, skip check
    if config.ffmpeg_verified:
        return True

    log('Checking FFmpeg availability...')
    found = False
    

    
    # APPIMAGE_PATH = f"{Path.home()}/.local/share/{config.APP_NAME}/aria2c"
    USER_CURRENT = f"{Path.home()}/.local/share/{config.APP_NAME}/current"
    FFMPEG_FOLDER = config.get_ffmpeg_folder()

    try:
        for folder in [config.current_directory, config.global_sett_folder, USER_CURRENT, FFMPEG_FOLDER]:
            if not folder: continue  # skip if not set
            for file in os.listdir(folder):
                if file.lower().startswith("ffmpeg"):
                    full_path = os.path.join(folder, file)
                    if os.path.isfile(full_path):
                        found = True
                        # config.ffmpeg_actual_path = full_path
                        break
            if found:
                break
    except Exception as e:
        log(f"Error while checking folders for ffmpeg: {e}")

    # Try system PATH
    if not found:
        from shutil import which
        path = which("ffmpeg")
        if path:
            # config.ffmpeg_actual_path = os.path.realpath(path)
            found = True

    if found:
        config.ffmpeg_verified = True  # ✅ Cache success
        # log('FFmpeg found:', config.ffmpeg_actual_path)
        return True
    else:
        # config.ffmpeg_actual_path = None
        log('FFmpeg not found. Will prompt user.')
        return False
    

def check_aria2_exe():
    """Check for aria2c availability, and cache result to avoid re-checking."""

    # ✅ If previously verified, skip check
    if config.aria2_verified:
        return True

    log('Checking aria2c availability...')
    found = False


    try:
        for folder in [config.current_directory, config.global_sett_folder]:
            if not folder: continue  # skip if not set
            for file in os.listdir(folder):
                if file.lower().startswith("aria2c.exe"):
                    full_path = os.path.join(folder, file)
                    if os.path.isfile(full_path):
                        found = True
                        config.aria2_actual_path = full_path
                        break
            if found:
                break
    except Exception as e:
        log(f"Error while checking folders for aria2c: {e}")

    # Try system PATH
    if not found:
        from shutil import which
        path = which("aria2c")
        if path:
            config.aria2_actual_path = os.path.realpath(path)
            found = True

    if found:
        config.aria2_verified = True  # ✅ Cache success
        log('aria2c found:', config.aria2_actual_path)
        return True
    else:
        config.aria2_actual_path = None
        log('aria2c not found. Will prompt user.')
        return False


def is_download_complete(d):
    return all(seg.completed for seg in d.segments)


def merge_video_audio(video, audio, output, d):
    """merge video file and audio file into output file, d is a reference for current DownloadItem object"""
    log('merging video and audio')

    # ffmpeg file full location
    ffmpeg = config.ffmpeg_actual_path

    # very fast audio just copied, format must match [mp4, m4a] and [webm, webm]
    cmd1 = f'"{ffmpeg}" -y -i "{video}" -i "{audio}" -c copy "{output}"'

    # slow, mix different formats
    cmd2 = f'"{ffmpeg}" -y -i "{video}" -i "{audio}" "{output}"'

    verbose = True if config.log_level >= 3 else False

    # run command with shell=False if failed will use shell=True option
    error, output = run_command(cmd1, verbose=verbose, shell=False, hide_window=True, d=d)

    if error:
        error, output = run_command(cmd1, verbose=verbose, shell=True, hide_window=True, d=d)

    if error:
        error, output = run_command(cmd2, verbose=verbose, shell=True, hide_window=True, d=d)

    return error, output
            

def import_ytdl():
    # import youtube_dl using thread because it takes sometimes 20 seconds to get imported and impact app startup time
    start = time.time()
    global ytdl, ytdl_version
    #import youtube_dl as ytdl
    import yt_dlp as ytdl
    config.ytdl_VERSION = ytdl.version.__version__

    load_time = time.time() - start
    log(f'yt-dlp load_time= {load_time}')


def parse_bytes(bytestr):
    """Parse a string indicating a byte quantity into an integer., example format: 536.71KiB,
    modified from original source at yt-dlp.common"""
    matchobj = re.match(r'(?i)^(\d+(?:\.\d+)?)([kMGTPEZY]\S*)?$', bytestr)
    if matchobj is None:
        return None
    number = float(matchobj.group(1))
    unit = matchobj.group(2).lower()[0:1] if  matchobj.group(2) else ''
    multiplier = 1024.0 ** 'bkmgtpezy'.index(unit)
    return int(round(number * multiplier))





def hls_downloader(d):
    """using ffmpeg to download hls streams ---- NOT IMPLEMENTED ----"""

    cmd = f'"ffmpeg" -y -i "{d.eff_url}" -c copy -f mp4 "file:{d.temp_file}"'
    subprocess.Popen(cmd)
    # error, output = run_command(cmd)
    # if error:
    #     return False
    # else:
    #     return True


def pre_process_hls(d):
    """handle m3u8 list and build a url list of file segments"""

    log('pre_process_hls()> start processing', d.name)

    # get correct url of m3u8 file
    def get_correct_m3u8_url(master_m3u8_doc, media='video'):
        if not master_m3u8_doc:
            return False

        lines = master_m3u8_doc.splitlines()
        for i, line in enumerate(lines):

            if media == 'video' and (str(d.selected_stream.width) in line and str(
                    d.selected_stream.height) in line or d.format_id in line):
                correct_url = urljoin(d.manifest_url, lines[i + 1])
                return correct_url
            elif media == 'audio' and (str(d.audio_stream.abr) in line or str(
                    d.selected_stream.tbr) in line or d.format_id in line):
                correct_url = urljoin(d.manifest_url, lines[i + 1])
                return correct_url

    def extract_url_list(m3u8_doc):
        # url_list
        url_list = []
        keys = []  # for encrypted streams

        for line in m3u8_doc.splitlines():
            line.strip()
            if line and not line.startswith('#'):
                url_list.append(line)
            elif line.startswith('#EXT-X-KEY'):
                # '#EXT-X-KEY:METHOD=AES-128,URI="https://content-aus...62a9",IV=0x00000000000000000000000000000000'
                match = re.search(r'URI="(.*)"', line)
                if match:
                    url = match.group(1)
                    keys.append(url)

        # log('process hls> url list:', url_list)
        return url_list, keys

    def download_m3u8(url):
        # download the manifest from m3u8 file descriptor located at url
        buffer = download(url)  # get BytesIO object

        if buffer:
            # convert to string
            buffer = buffer.getvalue().decode('utf-8')
            if '#EXT' in repr(buffer):
                return buffer

        log('pre_process_hls()> received invalid m3u8 file from server')
        if config.log_level >= 3:
            log('---------------------------------------\n', buffer, '---------------------------------------\n')
        return None
    
    
    # download m3u8 files
    master_m3u8 = download_m3u8(d.manifest_url)
    video_m3u8 = download_m3u8(d.eff_url)
    audio_m3u8 = download_m3u8(d.audio_url)

    if not video_m3u8:
        eff_url = get_correct_m3u8_url(master_m3u8, media='video')
        if not eff_url:
            log('pre_process_hls()> Failed to get correct video m3u8 url, quitting!')
            return False
        else:
            d.eff_url = eff_url
            video_m3u8 = download_m3u8(d.eff_url)

    if d.type == 'dash' and not audio_m3u8:
        eff_url = get_correct_m3u8_url(master_m3u8, media='audio')
        if not eff_url:
            log('pre_process_hls()> Failed to get correct audio m3u8 url, quitting!')
            return False
        else:
            d.audio_url = eff_url
            audio_m3u8 = download_m3u8(d.audio_url)

    # first lets handle video stream
    video_url_list, video_keys_url_list = extract_url_list(video_m3u8)

    # get absolute path from url_list relative path
    video_url_list = [urljoin(d.eff_url, seg_url) for seg_url in video_url_list]
    video_keys_url_list = [urljoin(d.eff_url, seg_url) for seg_url in video_keys_url_list]

    # create temp_folder if doesn't exist
    if not os.path.isdir(d.temp_folder):
        os.makedirs(d.temp_folder)

    
    # 👇 pre-create the container files so "Watch" can see them immediately
    try:
        # ensure parent dir exists (it should, but be defensive)
        os.makedirs(os.path.dirname(d.temp_file), exist_ok=True)
        # touch video temp file
        with open(d.temp_file, "ab"):
            pass
        # for DASH (separate audio), touch the audio temp file too
        if d.type == 'dash' and getattr(d, "audio_file", None):
            os.makedirs(os.path.dirname(d.audio_file), exist_ok=True)
            with open(d.audio_file, "ab"):
                pass
    except Exception as e:
        log(f"pre_process_hls()> could not pre-create temp files: {e}", log_level=2)

    # save m3u8 file to disk
    with open(os.path.join(d.temp_folder, 'remote_video.m3u8'), 'w') as f:
        f.write(video_m3u8)

    # build video segments
    d.segments = [Segment(name=os.path.join(d.temp_folder, str(i) + '.ts'), num=i, range=None, size=0,
                          url=seg_url, tempfile=d.temp_file, merge=True)
                  for i, seg_url in enumerate(video_url_list)]

    # add video crypt keys
    vkeys = [Segment(name=os.path.join(d.temp_folder, 'crypt' + str(i) + '.key'), num=i, range=None, size=0,
                          url=seg_url, seg_type='video_key', merge=False)
                  for i, seg_url in enumerate(video_keys_url_list)]

    # add to d.segments
    d.segments += vkeys

    # handle audio stream in case of dash videos
    if d.type == 'dash':
        audio_url_list, audio_keys_url_list = extract_url_list(audio_m3u8)

        # get absolute path from url_list relative path
        audio_url_list = [urljoin(d.audio_url, seg_url) for seg_url in audio_url_list]
        audio_keys_url_list = [urljoin(d.audio_url, seg_url) for seg_url in audio_keys_url_list]

        # save m3u8 file to disk
        with open(os.path.join(d.temp_folder, 'remote_audio.m3u8'), 'w') as f:
            f.write(audio_m3u8)

        # build audio segments
        audio_segments = [Segment(name=os.path.join(d.temp_folder, str(i) + '_audio.ts'), num=i, range=None, size=0,
                                  url=seg_url, tempfile=d.audio_file, merge=False)
                          for i, seg_url in enumerate(audio_url_list)]

        # audio crypt segments
        akeys = [Segment(name=os.path.join(d.temp_folder, 'audio_crypt' + str(i) + '.key'), num=i, range=None, size=0,
                                  url=seg_url, seg_type='audio_key', merge=False)
                          for i, seg_url in enumerate(audio_keys_url_list)]

        # add to video segments
        d.segments += audio_segments + akeys

    # load previous segment information from disk - resume download -
    d.load_progress_info()

    log('pre_process_hls()> done processing', d.name)

    return True


def post_process_hls(d):
    """ffmpeg will process m3u8 files"""

    log('post_process_hls()> start processing', d.name)

    def create_local_m3u8(remote_file, local_file, local_names, crypt_key_names=None):

        with open(remote_file, 'r') as f:
            lines = f.readlines()

        names = [f'{name}\n' for name in local_names]
        names.reverse()

        crypt_key_names.reverse()

        # log(len([a for a in lines if not a.startswith('#')]))

        for i, line in enumerate(lines[:]):
            if line and not line.startswith('#'):
                try:
                    name = names.pop()
                    lines[i] = name
                except:
                    pass
            elif line.startswith('#EXT-X-KEY'):
                # '#EXT-X-KEY:METHOD=AES-128,URI="https://content-aus...62a9",IV=0x00000000000000000000000000000000'
                match = re.search(r'URI="(.*)"', line)
                if match:
                    try:
                        key_name = crypt_key_names.pop()
                        key_name = key_name.replace('\\', '/')
                        lines[i] = line.replace(match.group(1), key_name)
                    except:
                        pass

        with open(local_file, 'w') as f:
            f.writelines(lines)
            # print(lines)

    # create local m3u8 version - video
    remote_video_m3u8_file = os.path.join(d.temp_folder, 'remote_video.m3u8')
    local_video_m3u8_file = os.path.join(d.temp_folder, 'local_video.m3u8')

    try:
        names = [seg.name for seg in d.segments if seg.tempfile == d.temp_file]
        crypt_key_names = [seg.name for seg in d.segments if seg.seg_type == 'video_key']
        create_local_m3u8(remote_video_m3u8_file, local_video_m3u8_file, names, crypt_key_names)
    except Exception as e:
        log('post_process_hls()> error', e)
        popup(title="Filename Error", msg="Please retry the download however the filename should not contain special characters.", type_="critical")
        return False

    if d.type == 'dash':
        # create local m3u8 version - audio
        remote_audio_m3u8_file = os.path.join(d.temp_folder, 'remote_audio.m3u8')
        local_audio_m3u8_file = os.path.join(d.temp_folder, 'local_audio.m3u8')

        try:
            names = [seg.name for seg in d.segments if seg.tempfile == d.audio_file]
            crypt_key_names = [seg.name for seg in d.segments if seg.seg_type == 'audio_key']
            create_local_m3u8(remote_audio_m3u8_file, local_audio_m3u8_file, names, crypt_key_names)
        except Exception as e:
            log('post_process_hls()> error', e)
            return False

    # now processing with ffmpeg
    # note: ffmpeg doesn't support socks proxy, also proxy must start with "http://"
    # currently will download crypto keys manually and use ffmpeg for merging only

    # proxy = f'-http_proxy "{config.proxy}"' if config.proxy else ''

    # cmd = f'"{config.ffmpeg_actual_path}" -y -protocol_whitelist "file,http,https,tcp,tls,crypto"  ' \
    #       f'-allowed_extensions ALL -i "{local_video_m3u8_file}" -c copy -f mp4 "file:{d.temp_file}"'
    
    cmd = f'"{config.ffmpeg_actual_path}" -y -protocol_whitelist "file,http,https,tcp,tls,crypto"  ' \
          f'-allowed_extensions ALL -i "{local_video_m3u8_file}" -c copy -f mp4 "file:{d.temp_file}"'

    error, output = run_command(cmd, d=d)
    if error:
        log('post_process_hls()> ffmpeg failed:', output)
        return False

    if d.type == 'dash':
        # cmd = f'"{config.ffmpeg_actual_path}" -y -protocol_whitelist "file,http,https,tcp,tls,crypto"  ' \
        #       f'-allowed_extensions ALL -i "{local_audio_m3u8_file}" -c copy -f mp4 "file:{d.audio_file}"'

        cmd = f'"{config.ffmpeg_actual_path}" -y -protocol_whitelist "file,http,https,tcp,tls,crypto"  ' \
              f'-allowed_extensions ALL -i "{local_audio_m3u8_file}" -c copy -f mp4 "file:{d.audio_file}"'

        error, output = run_command(cmd, d=d)
        if error:
            log('post_process_hls()> ffmpeg failed:', output)
            return False

    log('post_process_hls()> done processing', d.name)

    return True