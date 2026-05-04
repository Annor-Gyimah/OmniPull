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
import stat
import time
import shlex
import shutil
import asyncio
import tarfile
import zipfile
import requests
import platform
import threading
import subprocess
from modules import config
from urllib.parse import urljoin
from modules.threadpool import executor
from modules.config import get_effective_ffmpeg
from modules.downloaditem import DownloadItem, Segment
from modules.utils import log, validate_file_name, get_headers, size_format, run_command, \
    delete_file, download, process_thumbnail, popup, delete_folder, run_command_2
from modules.helpers import _norm_title, _expected_paths, _best_existing, _extract_title_from_pattern

from PySide6.QtCore import QCoreApplication

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
        'formats': 'bv*+ba/best', #'bv*,ba/b',
        'listformats': config.ytdlp_config.get('list_formats', False),
        'noplaylist': config.ytdlp_config.get('no_playlist', True),
        'ignoreerrors': config.ytdlp_config.get('ignore_errors', True),
        'cookies': config.ytdlp_config['cookiesfile'],
        'verbose': True,
        'abort_on_error': False,
        'skip_unavailable_fragments': True,
        'skip_playlist_after_errors': 5, 
        'ignore_no_formats_error': True,
        'js_runtimes': {
           'deno': {
                'executable': config.get_effective_deno()
            },
            # Optional fallbacks (use PATH if you omit 'executable'):
            # 'node': {},
            # 'quickjs': {},
            # 'bun': {},
        },
        # Extract subtitle metadata (manual and auto-generated captions)
        # This populates the 'subtitles' and 'automatic_captions' keys in the info dict
        'writesubtitles': True,
        'writeautomaticsub': True,
        'skip_unavailable_fragments': True,
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



def _format_js_runtimes_cli(jsr) -> str | None:
    # Accept dict (API-style), list/tuple (preformatted), or string (already CLI-style)
    if isinstance(jsr, dict):
        parts = []
        for name, cfg in jsr.items():
            exe = None
            if isinstance(cfg, dict):
                exe = cfg.get('executable') or cfg.get('path')
            if exe:
                parts.append(f"{name}:{exe}")
            else:
                parts.append(name)
        return ",".join(parts) if parts else None
    if isinstance(jsr, (list, tuple)):
        return ",".join(str(x) for x in jsr) if jsr else None
    if isinstance(jsr, str):
        return jsr or None
    return None

    
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

    # JS runtimes (Deno/Node/QuickJS/Bun)
    jsr = ydl_opts.get("js_runtimes")
    cli_jsr = _format_js_runtimes_cli(jsr)
    if cli_jsr:
        args += ["--js-runtimes", cli_jsr]

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
            log(formats_to_table_html(info))   # dump the table to the custom log
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


    
    def extract_playlist_entries_streaming(url: str, stop_event: threading.Event,
        proc_holder: list) -> list[dict]:
        """
        Launch yt-dlp with --flat-playlist and stream one JSON stub per line.
    
        Returns a list of entry dicts (keys: url/webpage_url, title, id).
        Checks stop_event between every line; if set, kills the subprocess and
        returns whatever stubs have been collected so far.
    
        proc_holder is a single-element list [None] that we fill with the Popen
        object so the caller can also kill it from another thread if needed.
    
        Falls back to Python API (uninterruptible) if no exe is configured.
        """
        exe_path = config.get_effective_ytdlp() if getattr(config, "use_ytdlp_exe", False) else None
        if not exe_path or not os.path.isfile(exe_path):
            # No exe available — fall back to Python API (blocking, no mid-cancel)
            log("[yt-dlp] No exe; using Python API for flat playlist (not interruptible)", log_level=2)
            ydl_opts = get_ytdl_options()
            ydl_opts["extract_flat"] = "in_playlist"
            ydl_opts["noplaylist"]   = False
            ydl_opts["no_playlist"]  = False
            info = _run_ytdlp_python_api(url, ydl_opts)
            return list(info.get("entries") or [])
    
        # Build CLI: emit one JSON object per playlist entry, then exit.
        # --flat-playlist  → do not recurse into each video
        # --print "%()j"   → print the full entry info-dict as compact JSON
        base_args = _ydl_opts_to_args(get_ytdl_options(), allow_listformats=False)
        cmd = (
            [exe_path]
            + base_args
            + ["--flat-playlist", "--no-warnings", "--no-progress",
            "--print", "%()j",          # one JSON object per entry
            "--yes-playlist",
            url]
        )
    
        log(f"[yt-dlp] Streaming flat playlist: {' '.join(cmd[:6])} …", log_level=2)
    
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            proc_holder[0] = proc          # expose to caller for external kill
        except Exception as e:
            log(f"[yt-dlp] Failed to start yt-dlp process: {e}", log_level=2)
            return []
    
        entries = []
        try:
            for raw_line in proc.stdout:
                # ── Cancel check between every entry ──────────────────────────────
                if stop_event.is_set():
                    log(f"[yt-dlp] stop_event set – killing yt-dlp process (pid {proc.pid})", log_level=1)
                    proc.kill()
                    break
    
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                    log(f"[yt-dlp] Flat entry {len(entries)}: {entry.get('title', '?')[:60]}", log_level=3)
                except json.JSONDecodeError:
                    log(f"[yt-dlp] Non-JSON flat output (ignored): {line[:120]}", log_level=3)
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass
            proc.wait()
            proc_holder[0] = None
    
        log(f"[yt-dlp] Flat playlist done: {len(entries)} entries collected", log_level=1)
        return entries
    


    @classmethod
    async def fetch_single_entry(cls, entry: dict, stop_event: threading.Event,
        proc_holder: list):
        """
        Fully resolve a flat playlist stub into a rich info dict.
        Uses Popen so the process can be killed via stop_event.
 
        Returns a Video object, or None if cancelled / failed.
        """
        entry_url = entry.get("webpage_url") or entry.get("url") or entry.get("id")
        if not entry_url:
            log(f"[yt-dlp] Entry has no URL, skipping: {entry}", log_level=2)
            return None
 
        loop = asyncio.get_running_loop()
 
        def _blocking_fetch():
            exe_path = (config.get_effective_ytdlp()
                        if getattr(config, "use_ytdlp_exe", False) else None)
            if exe_path and os.path.isfile(exe_path):
                # ── exe path: Popen so we can kill it ────────────────────────
                ydl_opts = get_ytdl_options()
                ydl_opts["noplaylist"] = True
                ydl_opts["no_playlist"] = True
                base_args = _ydl_opts_to_args(ydl_opts, allow_listformats=False)
                cmd = (
                    [exe_path]
                    + base_args
                    + ["--dump-single-json", "--no-warnings",
                       "--no-progress", "--no-playlist", entry_url]
                )
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    proc_holder[0] = proc
                    stdout, stderr = proc.communicate()   # blocks until done
                    proc_holder[0] = None
                except Exception as e:
                    proc_holder[0] = None
                    raise
 
                if stop_event.is_set():
                    return None            # killed externally; discard result
 
                try:
                    return json.loads(stdout.strip())
                except json.JSONDecodeError:
                    raise RuntimeError(
                        f"yt-dlp returned no JSON for {entry_url}\\n"
                        f"stderr: {stderr[:300]}"
                    )
            else:
                # ── Python API path (uninterruptible, last resort) ───────────
                ydl_opts = get_ytdl_options()
                ydl_opts["noplaylist"] = True
                ydl_opts["no_playlist"] = True
                return _run_ytdlp_python_api(entry_url, ydl_opts)
 
        try:
            raw_info = await loop.run_in_executor(executor, _blocking_fetch)
        except Exception as e:
            log(f"[yt-dlp] fetch_single_entry failed for {entry_url}: {e}", log_level=2)
            return None
 
        if raw_info is None:
            return None
 
        try:
            return cls(entry_url, vid_info=raw_info, get_size=False)
        except Exception as e:
            log(f"[yt-dlp] Video() construction failed for {entry_url}: {e}", log_level=2)
            return None

    


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




        # Filter out invalid formats (mhtml storyboards only)
        def is_valid_format(fmt):
            ext = fmt.get('ext', '')
            vcodec = fmt.get('vcodec', '')
            format_id = fmt.get('format_id', '')

            # Skip mhtml storyboards
            if ext == 'mhtml':
                return False
            # Skip formats with vcodec "images" (storyboards)
            if vcodec == 'images':
                return False
            # Skip storyboard format IDs
            if format_id and format_id.startswith('sb'):
                return False
            return True

        valid_formats = [fmt for fmt in self.vid_info['formats'] if is_valid_format(fmt)]

        all_streams = [Stream(x) for x in valid_formats]

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

        # DO NOT require size>0 here; HLS/DASH audio has size==0 by design in the Stream.__init__
        self.audio_stream = audio_stream
        self.audio_url = audio_stream.url
        self.audio_size = audio_stream.size
        self.audio_fragment_base_url = audio_stream.fragment_base_url
        self.audio_fragments = audio_stream.fragments
        self.audio_format_id = audio_stream.format_id


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

        

    def get_size(self):
        headers = get_headers(self.url)
        size = int(headers.get('content-length', 0))
        log('stream.get_size()>', self.name)
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



DEFAULT_DEST = getattr(config, 'sett_folder', '.')

def _gh_latest_asset(owner_repo: str, *, match_any, token: str | None = None):
    """
    Return (asset_name, asset_browser_download_url) for the first asset whose
    name matches any of the provided predicates (in order).
    """
    api = f"https://api.github.com/repos/{owner_repo}/releases/latest"
    headers = {'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = f"Bearer {token}"
    r = requests.get(api, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    assets = data.get('assets') or []
    # Try each predicate until one matches
    for pred in match_any:
        for a in assets:
            name = a.get('name') or ''
            if pred(name):
                return name, a.get('browser_download_url')
    raise RuntimeError(f"No matching assets found in {owner_repo} latest release")

def _is_win():
    return platform.system().lower().startswith('win')

def _cpu():
    # normalize to strings we use
    m = platform.machine().lower()
    # common normalizations
    if m in ('amd64', 'x86_64', 'x64'):
        return 'x86_64'
    if m in ('arm64', 'aarch64'):
        return 'arm64'
    if m in ('x86', 'i386', 'i686'):
        return 'x86'
    return m

def check_dependency_installed(name: str) -> bool:
    """
    Checks if a specific dependency is already present in the settings folder.
    """

    IS_WIN = platform.system().lower().startswith("win")
    dest_folder = config.CONFIG_BIN if not IS_WIN else config.DATA_ROOT
    
    # Define the expected filename for each dependency
    filename_map = {
        'yt-dlp': "yt-dlp.exe" if IS_WIN else "yt-dlp",
        'ffmpeg': "ffmpeg.exe" if IS_WIN else "ffmpeg",
        'deno': "deno.exe" if IS_WIN else "deno"
    }
    
    exe_name = filename_map.get(name.lower())
    if not exe_name:
        return False
        
    full_path = os.path.join(dest_folder, exe_name)
        
    return os.path.isfile(full_path) and os.path.getsize(full_path) > 0


def remove_internal_item(d):
    """
    Callback to remove an internal dependency item from the UI after completion.
    """
    if d and hasattr(d, 'id'):
        log(f"Removing internal download item: {d.id}", context="ENGINE-BRAIN")
        config.main_window_q.put(('remove_internal_download', d.id))
    

def make_executable(d):
    """Sets +x permissions and then removes the item from the internal list."""
    try:
        path = os.path.join(d.folder, d.name)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        log(f"Permissions set for {path}")
            
        # Perform cleanup after setting permissions
        # remove_internal_item(d)
    except Exception as e:
        log(f"Failed to make executable: {e}", log_level=3)



def download_dependency(*, name: str, destination: str = DEFAULT_DEST):
    """
    Download latest Windows ZIP for yt-dlp FFmpeg builds or Deno from GitHub releases.
    - name: 'ffmpeg' or 'deno'
    - destination: where DownloadItem should store the file
    Sets the right filename and callback for unzip logic.
    """
    # expose both folders for unzip code 
    config.ffmpeg_download_folder = destination
    config.deno_download_folder = destination


    
    
    token = getattr(config, 'github_token', None)
    arch = _cpu()
    sys_name = platform.system().lower()

    # --- Case: yt-dlp ---
    if name.lower() == 'yt-dlp':
        def want_ytdlp(asset_name: str) -> bool:
            an = asset_name.lower()
            # Windows logic
            if "win" in sys_name:
                if arch == 'x86_64': return an == "yt-dlp.exe"
                if arch == 'x86':    return an == "yt-dlp_x86.exe"
                if arch == 'arm64':  return an == "yt-dlp_arm64.exe"
            # Linux logic
            elif "linux" in sys_name:
                if arch == 'x86_64': return an == "yt-dlp_linux"
                if arch == 'arm64':  return an == "yt-dlp_linux_aarch64"
            # MacOS logic
            elif "darwin" in sys_name:
                return an == "yt-dlp_macos"
            return False

        asset_name, url = _gh_latest_asset("yt-dlp/yt-dlp", match_any=[want_ytdlp], token=token)
        # url = "http://localhost/lite/yt-dlp.exe"
        
        log(f"Initiating yt-dlp download: {url}", log_level=1, context="DEPENDENCY")
        d = DownloadItem(url=url, folder=destination)
        d.update(url)
        d.is_internal = True  # <--- Mark as internal
        # Force a clean filename for the executable
        clean_name = "yt-dlp.exe" if _is_win() else "yt-dlp"
        
        server_name = url.split("/")[-1]   
        d.name = server_name
        d.original_name = server_name   

        def _rename_and_chmod(d):
            clean_name = "yt-dlp.exe" if _is_win() else "yt-dlp"
            folder = d.folder

            try:
                # Find actual binary (ignore .json, .part, etc.)
                for fname in os.listdir(folder):
                    if fname.startswith("yt-dlp") and not fname.endswith((".json", ".part")):
                        src = os.path.join(folder, fname)
                        dst = os.path.join(folder, clean_name)

                        os.rename(src, dst)
                        log(f"Renamed {src} → {dst}")

                        if not _is_win():
                            mode = os.stat(dst).st_mode
                            os.chmod(dst, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                            log(f"Permissions set for {dst}")

                        d.name = clean_name
                        break
                else:
                    raise FileNotFoundError("yt-dlp binary not found after download")

            except Exception as e:
                log(f"Post-download rename/chmod failed: {e}", log_level=3)

            finally:
                remove_internal_item(d)
                config.yt_dlp_actual_path = config.DATA_ROOT / "yt-dlp.exe" if _is_win() else os.path.join(config.CONFIG_BIN, "yt-dlp")
                config.yt_dlp_exe = os.path.join(config.DATA_ROOT, "yt-dlp.exe") if _is_win() else os.path.join(config.CONFIG_BIN, "yt-dlp")
                log(f"yt-dlp is ready at {config.yt_dlp_exe}", log_level=1, context="DEPENDENCY")

        d.callback = _rename_and_chmod
        config.main_window_q.put(('download', (d, False)))
        return

    if name.lower() == 'ffmpeg':
        # yt-dlp’s FFmpeg builds: yt-dlp/FFmpeg-Builds (latest release)
        # Choose gpl variant, prefer the “master/latest” flavor, fall back to any N-*-gpl.zip
        def want_ffmpeg(asset_name: str) -> bool:
            """
            Cross-platform matcher for yt-dlp/FFmpeg-Builds.
            Targeting static GPL builds for the current OS and Arch.
            """
            an = asset_name.lower()

            # 1. Filter by extension and variant
            # We avoid "-shared" because we want the standalone static binaries.
            expected_ext = ".zip" if "win" in sys_name else ".tar.xz"
            if not an.endswith(expected_ext) or "gpl" not in an or "-shared" in an:
                return False

            # 2. Windows logic
            if "win" in sys_name:
                if arch == 'x86_64': return "win64" in an
                if arch == 'x86':    return "win32" in an
                if arch == 'arm64':  return "winarm64" in an

            # 3. Linux logic
            elif "linux" in sys_name:
                if arch == 'x86_64': return "linux64" in an
                if arch == 'arm64':  return "linuxarm64" in an
                
            # 4. MacOS logic (Note: yt-dlp/FFmpeg-Builds doesn't always have Mac binaries,
            # but if they did, they usually follow the linux naming or a 'macos' string)
            elif "darwin" in sys_name:
                return "macos" in an

            return False

        # Two-pass picker: prefer the 'master-latest' builds for stability, 
        # then fall back to the 'N-xxxx' auto-builds.
        pickers = [
            lambda n: "master-latest" in n.lower() and want_ffmpeg(n),
            lambda n: want_ffmpeg(n),
        ]

        asset_name, url = _gh_latest_asset("yt-dlp/FFmpeg-Builds", match_any=pickers, token=token)
        # asset_name, url = _gh_latest_asset("BtbN/FFmpeg-Builds", match_any=pickers, token=token)
        # url = "http://localhost/lite/ffmpeg.zip"
        # Build DownloadItem
        log("downloading (ffmpeg): ", url)
        d = DownloadItem(url=url, folder=config.ffmpeg_download_folder)
        d.update(url)
        d.is_internal = True  # <--- Mark as internal
        d.name = 'ffmpeg.zip' if _is_win() else 'ffmpeg.tar.xz'      # unzip_ffmpeg expects this
        d.callback = 'unzip_ffmpeg'   
        # d.callback = lambda: unzip_ffmpeg(d) 
        config.main_window_q.put(('download', (d, False)))
        return

    if name.lower() == 'deno':
        # Official deno release: denoland/deno (latest)
        # We want deno-x86_64-pc-windows-msvc.zip on Windows x64
        # (No official 32-bit Windows archive; handle gracefully.)
        
        def want_deno(asset_name: str) -> bool:
            an = asset_name.lower()

            # Skip source code, debug symbols, and the 'denort' runtime-only binaries
            if not an.endswith(".zip") or an.startswith("denort"):
                return False

            # Windows logic
            if "win" in sys_name:
                if arch == 'x86_64': 
                    return an == "deno-x86_64-pc-windows-msvc.zip"
                if arch == 'arm64':  
                    return an == "deno-aarch64-pc-windows-msvc.zip"

            # Linux logic
            elif "linux" in sys_name:
                if arch == 'x86_64': 
                    return an == "deno-x86_64-unknown-linux-gnu.zip"
                if arch == 'arm64':  
                    return an == "deno-aarch64-unknown-linux-gnu.zip"

            # MacOS logic
            elif "darwin" in sys_name:
                if arch == 'x86_64': 
                    return an == "deno-x86_64-apple-darwin.zip"
                if arch == 'arm64':  
                    # Deno uses aarch64 for Apple Silicon (M1/M2/M3)
                    return an == "deno-aarch64-apple-darwin.zip"

            return False

        

        asset_name, url = _gh_latest_asset("denoland/deno", match_any=[want_deno], token=token)
        # url = "http://localhost/lite/deno.zip"

        log("downloading (deno): ", url)
        d = DownloadItem(url=url, folder=config.deno_download_folder)
        d.update(url)
        d.is_internal = True  # <--- Mark as internal
        d.name = 'deno.zip'           
        d.callback = unzip_deno
        # d.callback = lambda: unzip_deno(d)
        config.main_window_q.put(('download', (d, False)))
        return

    raise ValueError(f"Unsupported dependency name: {name!r}")


def download_deno(destination):
    download_dependency(name='deno', destination=destination)

def download_ffmpeg(destination):
    download_dependency(name='ffmpeg', destination=destination)




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
    if platform.machine().endswith('64'):
        url = 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip'
    else:
        url = 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-32bit-build1.zip'

    filename = "aria2c.zip"
    download_aria2c_with_wget(url, destination, filename)


def unzip_dependency(
    d,
    *,
    zip_basename: str,
    exe_name: str,
    folder_attr: str,
    popup_title: str,
    popup_msg: str,
    on_installed=None,
):
    log(f'unzip_dependency[{exe_name}]', 'extracting archive')
    d.status = config.Status.unzipping

    try:
        folder = getattr(config, folder_attr)
        os.makedirs(folder, exist_ok=True)

        archive_path = os.path.join(folder, zip_basename)

        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        main_exe_path = None

        # =========================================================
        # ZIP HANDLER
        # =========================================================
        if archive_path.endswith(".zip"):
            if not zipfile.is_zipfile(archive_path):
                os.remove(archive_path)
                raise zipfile.BadZipFile("Downloaded ZIP is corrupted.")

            with zipfile.ZipFile(archive_path, 'r') as archive:
                members = archive.infolist()

                bin_members = [
                    m for m in members
                    if '/bin/' in m.filename and not m.is_dir()
                ]

                extract_members = bin_members or members

                for member in extract_members:
                    if member.is_dir():
                        continue

                    base_name = os.path.basename(member.filename)
                    target_path = os.path.join(folder, base_name)

                    with archive.open(member) as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)

                    if base_name.lower() == exe_name.lower():
                        main_exe_path = target_path

        # =========================================================
        # TAR HANDLER (.tar.xz / .tar.gz / .tgz)
        # =========================================================
        elif tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, 'r:*') as archive:
                members = archive.getmembers()

                bin_members = [
                    m for m in members
                    if '/bin/' in m.name and m.isfile()
                ]

                extract_members = bin_members or members

                for member in extract_members:
                    if not member.isfile():
                        continue

                    base_name = os.path.basename(member.name)
                    target_path = os.path.join(folder, base_name)

                    src = archive.extractfile(member)
                    if src:
                        with src, open(target_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)

                    if base_name.lower() == exe_name.lower():
                        main_exe_path = target_path

        else:
            raise RuntimeError("Unsupported archive format.")
        
        d.status = config.Status.completed

        # =========================================================
        # CLEANUP
        # =========================================================
        try:
            os.remove(archive_path)
        except Exception as e:
            log(f"Could not delete archive: {e}")

        if not main_exe_path:
            raise RuntimeError(f"Could not find {exe_name} inside archive.")

        # =========================================================
        # POST INSTALL
        # =========================================================
        if callable(on_installed):
            on_installed(main_exe_path)

        if not _is_win():
            mode = os.stat(main_exe_path).st_mode
            os.chmod(
                main_exe_path,
                mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )
            log(f"Executable set: {main_exe_path}")

        config.main_window_q.put(('remove_internal_download', d.id))

        param = dict(title=popup_title, msg=popup_msg, type_='info')
        config.main_window_q.put(('popup', param))

        log(
            f'unzip_dependency[{exe_name}]',
            f'Installation successful: {main_exe_path}'
        )
          # yt-dlp is bundled, so path is constant
        config.ffmpeg_actual_path = config.DATA_ROOT / "ffmpeg.exe" if _is_win() else os.path.join(config.CONFIG_BIN, "ffmpeg")
        config.deno_actual_path = config.DATA_ROOT / "deno.exe" if _is_win() else os.path.join(config.CONFIG_BIN, "deno")
        config.deno_exe = os.path.join(config.DATA_ROOT, "deno.exe") if _is_win() else os.path.join(config.CONFIG_BIN, "deno")
        

    except Exception as e:
        log(f'unzip_dependency[{exe_name}] error', str(e))

        param = dict(
            title=f"{popup_title} (Error)",
            msg=f"Failed to extract {exe_name}: {str(e)}",
            type_='error'
        )
        config.main_window_q.put(('popup', param))


def unzip_ffmpeg(d):
    def _on_ffmpeg(dest):
        config.ffmpeg_actual_path = dest
    return unzip_dependency(
        d,
        zip_basename='ffmpeg.zip' if _is_win() else 'ffmpeg.tar.xz',
        exe_name='ffmpeg.exe' if _is_win() else 'ffmpeg',
        folder_attr='ffmpeg_download_folder',
        popup_title=QCoreApplication.translate('FFmpeg Info', 'FFmpeg Info'),
        popup_msg=QCoreApplication.translate('FFmpeg Info', 'FFmpeg is now available. Please try downloading the video again.'),
        on_installed=_on_ffmpeg,
    )


def unzip_deno(d):
    def _on_deno(dest):
        # remember deno path so yt-dlp can use it
        config.deno_actual_path = dest
        config.deno_verified = True
        
        #   if getattr(config, 'deno_executable', None):
        #       ydl_opts['js_runtimes'] = {'deno': {'executable': config.deno_executable}}
    return unzip_dependency(
        d,
        zip_basename='deno.zip',
        exe_name='deno.exe' if _is_win() else 'deno',
        folder_attr='deno_download_folder',
        popup_title=QCoreApplication.translate("Deno Info", "Deno Info"),
        popup_msg=QCoreApplication.translate(
            "Deno Info", 
            "Deno is now available. YouTube extraction should work on the next attempt."
        ),
        on_installed=_on_deno,
    )





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


def check_deno():
    """Check for deno availability, and cache result to avoid re-checking."""

    # If previously verified, skip check
    if config.deno_verified:
        return True

    log('Checking Deno availability...')
    found = False

    try:
        for folder in [config.current_directory, config.global_sett_folder]:
            if not folder: continue  # skip if not set
            for file in os.listdir(folder):
                if file.lower().startswith("deno"):
                    full_path = os.path.join(folder, file)
                    if os.path.isfile(full_path):
                        found = True
                        config.deno_actual_path = full_path
                        break
            if found:
                break
    except Exception as e:
        log(f"Error while checking folders for deno: {e}")

    # Try system PATH
    if not found:
        from shutil import which
        path = which("deno")
        if path:
            config.deno_actual_path = os.path.realpath(path)
            found = True

    if found:
        config.deno_verified = True  # Cache success
        log('Deno found:', config.deno_actual_path)
        return True
    else:
        config.deno_actual_path = None
        log('Deno not found. Will prompt user.')
        return False

def check_ffmpeg():
    """Check for ffmpeg availability, and cache result to avoid re-checking."""

    # If previously verified, skip check
    if config.ffmpeg_verified:
        return True

    log('Checking FFmpeg availability...')
    found = False

    try:
        for folder in [config.current_directory, config.global_sett_folder]:
            if not folder: continue  # skip if not set
            for file in os.listdir(folder):
                if file.lower().startswith("ffmpeg"):
                    full_path = os.path.join(folder, file)
                    if os.path.isfile(full_path):
                        found = True
                        config.ffmpeg_actual_path = full_path
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
            config.ffmpeg_actual_path = os.path.realpath(path)
            found = True

    if found:
        config.ffmpeg_verified = True  # Cache success
        log('FFmpeg found:', config.ffmpeg_actual_path)
        return True
    else:
        config.ffmpeg_actual_path = None
        log('FFmpeg not found. Will prompt user.')
        return False
    

def check_aria2_exe():
    """Check for aria2c availability, and cache result to avoid re-checking."""

    # If previously verified, skip check
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
        config.aria2_verified = True  # Cache success
        log('aria2c found:', config.aria2_actual_path)
        return True
    else:
        config.aria2_actual_path = None
        log('aria2c not found. Will prompt user.')
        return False


def is_download_complete(d):
    return all(seg.completed for seg in d.segments)





def _find_audio_file_for(d) -> str | None:
    import glob
    """
    Priority:
    1) exact "audio_for_<TITLE>.*" using normalized d.name
    2) scan folder for files starting 'audio_for_' and pick the one whose <TITLE> matches d.name best
    3) if d.audio_file exists, use it (legacy)
    """
    folder = getattr(d, 'folder', None) or os.path.dirname(getattr(d, 'target_file', '') or getattr(d, 'temp_file', '') or '')
    if not folder:
        return None

    # 3) Legacy explicit field (kept but lowered in priority to prefer user's new convention)
    explicit = getattr(d, 'audio_file', None)
    if explicit and os.path.exists(explicit):
        # we will still try convention first; fallback to explicit later
        pass

    title_norm = _norm_title(getattr(d, 'name', '') or os.path.basename(getattr(d, 'target_file', '') or ''))
    video_candidates, audio_candidates = _expected_paths(folder, title_norm)

    # 1) Exact by normalized title
    audio = _best_existing(audio_candidates)
    if audio:
        return audio

    # 2) Scan folder for any audio_for_*.* and choose the best title match
    candidates = []
    try:
        for p in glob.glob(os.path.join(folder, '*')):
            if not os.path.isfile(p): continue
            bn = os.path.basename(p)
            # accept if normalized basename contains normalized title (handles spaces vs underscores)
            if _norm_title(bn).find(title_norm) != -1:
                candidates.append(p)
    except Exception as e:
        candidates = [p for p in glob.glob(os.path.join(folder, 'audio_for_*.*')) if os.path.isfile(p)]

    if candidates:
        # compute normalized titles and compare to title_norm
        scored = []
        for p in candidates:
            t = _extract_title_from_pattern(p, "audio_for_") or ""
            # Higher score for exact match; otherwise Jaccard-like overlap on tokens
            if t == title_norm:
                score = 100
            else:
                a = set(title_norm.split('_'))
                b = set(t.split('_'))
                inter = len(a & b)
                score = inter
            scored.append((score, p))
        if scored:
            scored.sort(key=lambda x: (-x[0], -os.path.getsize(x[1]), x[1]))
            if scored[0][0] > 0:
                return scored[0][1]

    # 3) Fallback to explicit
    if explicit and os.path.exists(explicit):
        return explicit

    return None

def _find_video_file_for(d, audio_path: str | None) -> str | None:
    import glob
    """
    Priority:
    1) exact "_temp_<TITLE>.*" using normalized d.name
    2) if not found, use d.target_file when it exists and looks like video-only
    3) scan folder for _temp_* candidates and pick best title match
    4) scan folder for <TITLE>.* large media if still missing
    """
    folder = getattr(d, 'folder', None) or os.path.dirname(getattr(d, 'target_file', '') or getattr(d, 'temp_file', '') or '')
    if not folder:
        return None

    title_norm = _norm_title(getattr(d, 'name', '') or os.path.basename(getattr(d, 'target_file', '') or ''))
    video_candidates, _audio_candidates = _expected_paths(folder, title_norm)

    # 1) Exact by normalized title (_temp_<TITLE>.*)
    video = _best_existing(video_candidates)
    if video and (not audio_path or os.path.abspath(video) != os.path.abspath(audio_path)):
        return video

    # 2) Use target_file if it exists
    tgt = getattr(d, 'target_file', None)
    if tgt and os.path.exists(tgt) and (not audio_path or os.path.abspath(tgt) != os.path.abspath(audio_path)):
        return tgt

    # 3) Scan folder for any _temp_*.* and choose the best title match
    candidates = []
    try:
        for p in glob.glob(os.path.join(folder, "*")):
            if not os.path.isfile(p):
                continue
            bn = os.path.basename(p)
            # accept files that look like temp parts or contain the normalized title
            if bn.lower().startswith("_temp_") or _norm_title(bn).find(title_norm) != -1:
                candidates.append(p)
    except Exception:
        candidates = [p for p in glob.glob(os.path.join(folder, "_temp_*.*")) if os.path.isfile(p)]
    if candidates:
        scored = []
        for p in candidates:
            t = _extract_title_from_pattern(p, "_temp_") or ""
            if t == title_norm:
                score = 100
            else:
                a = set(title_norm.split('_'))
                b = set(t.split('_'))
                inter = len(a & b)
                score = inter
            if audio_path and os.path.abspath(p) == os.path.abspath(audio_path):
                continue
            scored.append((score, p))
        if scored:
            scored.sort(key=lambda x: (-x[0], -os.path.getsize(x[1]), x[1]))
            if scored[0][0] > 0:
                return scored[0][1]

    # 4) Last resort: largest media with <TITLE>.* (avoid choosing the audio file)
    media_exts = ('mp4', 'm4v', 'mov', 'webm', 'mkv', 'ts')
    pattern = os.path.join(folder, f"{title_norm}.*")
    loose = []
    for p in glob.glob(pattern):
        if audio_path and os.path.abspath(p) == os.path.abspath(audio_path):
            continue
        ext = os.path.splitext(p)[1].lower().lstrip('.')
        if ext in media_exts:
            loose.append(p)
    if loose:
        loose.sort(key=lambda p: (-os.path.getsize(p), p))
        return loose[0]

    return None


def merge_video_audio(video, audio, output, d):
    """
    Muxes separate video and audio streams into a single container.
    
    Includes an automatic 'Input Swap' safeguard: If the inputs are 
    provided out of order (audio as Input 0), it flips them to ensure 
    the mapping '-map 0:v:0' remains valid.
    """
    ctx = "MERGE"
    log("Initiating FFmpeg muxing sequence...", log_level=1, context=ctx)

    # 1. Path Resolution
    found_audio = _find_audio_file_for(d)
    found_video = _find_video_file_for(d, found_audio)
    
    video = found_video or video
    audio = found_audio or audio
    
    # 2. Critical Path Validation
    if not video or not audio or not os.path.exists(video) or not os.path.exists(audio):
        msg = f"Merge failed: Missing component. V:{video} | A:{audio}"
        log(msg, log_level=0, context=ctx)
        return True, msg

    # 3. File Integrity Verification
    try:
        v_size = os.path.getsize(video)
        a_size = os.path.getsize(audio)
        log(f"Component Sizes -> Video: {size_format(v_size)} | Audio: {size_format(a_size)}", 
            log_level=2, context=ctx)
        
        if v_size < 1024 or a_size < 1024:
            msg = "Components appear truncated or incomplete."
            return True, msg
    except Exception as e:
        log(f"Pre-merge size check failed: {e}", log_level=2, context=ctx)

    # --- THE FIX: INPUT SWAP SAFEGUARD ---
    # Sometimes d.url (video) and d.audio_url get swapped. 
    # We ensure 'video' actually contains a video stream before mapping.
    if video.lower().endswith(('.m4a', '.mp3', '.aac', '.opus')):
        log("Detected swapped inputs. Correcting V/A order for FFmpeg mapping.", log_level=2, context=ctx)
        video, audio = audio, video

    output = os.path.normpath(output)
    
    
    ffmpeg = get_effective_ffmpeg()
    
    # ── Attempt 1: Fast Stream Copy (Lossless) ──
    cmd_copy = [
        ffmpeg, "-nostdin", "-y",
        "-loglevel", "error",
        "-fflags", "+genpts+igndts",
        "-i", video,
        "-i", audio,
        # "-map", "0:v:0",   # Map video from first input
        # "-map", "1:a:0",   # Map audio from second input
        "-c", "copy",
        "-movflags", "+faststart",
        "-strict", "experimental",
        output
    ]

    error, out = run_command_2(cmd_copy, verbose=True, hide_window=True, d=d)
    
    # ── Attempt 2: Wildcard Mapping (If indices fail) ──
    if error:
        log("Specific mapping failed. Retrying with wildcard mapping...", log_level=2, context=ctx)
        cmd_auto = [
            ffmpeg, "-nostdin", "-y",
            "-loglevel", "error",
            "-fflags", "+genpts+igndts",
            "-i", video,
            "-i", audio,
            "-c", "copy",
            "-movflags", "+faststart",
            output
        ]
        error, out = run_command_2(cmd_auto, verbose=True, hide_window=True, d=d)
    
    # ── Attempt 3: Audio Re-encode (Compatibility fallback) ──
    if error:
        log("Copy failed. Retrying with AAC audio re-encoding...", log_level=2, context=ctx)
        cmd_reencode = [
            ffmpeg, "-nostdin", "-y",
            "-loglevel", "error",
            "-i", video,
            "-i", audio,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", 
            output
        ]
        error, out = run_command_2(cmd_reencode, verbose=True, hide_window=True, d=d)

    # ── Final Resolution ──
    if not error:
        log(f"Successfully merged DASH streams into {os.path.basename(output)}", log_level=1, context=ctx)
    else:
        log(f"All muxing attempts exhausted. FFmpeg Error: {out}", log_level=0, context=ctx)
    
    return error, out







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
            line = line.strip()  # FIX: strip() returns a new string
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
    
    manifest_headers = {'User-Agent': config.USER_AGENT, 'Accept': '*/*'}

    def download_m3u8(url):
        # download the manifest from m3u8 file descriptor located at url
        buffer = download(url, headers=manifest_headers)  # get BytesIO object

        if buffer:
            # convert to string
            try:
                decoded = buffer.getvalue().decode('utf-8')
            except Exception:
                # If cannot decode, likely binary (direct stream), not an m3u8
                return None

            if '#EXT' in repr(decoded):
                return decoded

        log('pre_process_hls()> received invalid m3u8 file from server (or direct binary stream)')
        return None
    
    
    # download m3u8 files
    master_m3u8 = download_m3u8(d.manifest_url)
    video_m3u8 = download_m3u8(d.eff_url)
    
    # Try downloading audio m3u8, but if it returns None, we might fallback to direct download later
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
        if eff_url:
             d.audio_url = eff_url
             audio_m3u8 = download_m3u8(d.audio_url)
        # If still no audio_m3u8, we assume it is a direct DASH stream and proceed below

    # first lets handle video stream
    if not video_m3u8:
        # Critical failure if we can't get video
         log('pre_process_hls()> No video m3u8 found.')
         return False

    video_url_list, video_keys_url_list = extract_url_list(video_m3u8)

    # get absolute path from url_list relative path
    video_url_list = [urljoin(d.eff_url, seg_url) for seg_url in video_url_list]
    video_keys_url_list = [urljoin(d.eff_url, seg_url) for seg_url in video_keys_url_list]

    # create temp_folder if doesn't exist
    if not os.path.isdir(d.temp_folder):
        os.makedirs(d.temp_folder)

    
    # pre-create the container files so "Watch" can see them immediately
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
        if audio_m3u8:
            # Case A: Audio is a valid HLS/m3u8 playlist
            audio_url_list, audio_keys_url_list = extract_url_list(audio_m3u8)

            # get absolute path from url_list relative path
            audio_url_list = [urljoin(d.audio_url, seg_url) for seg_url in audio_url_list]
            audio_keys_url_list = [urljoin(d.audio_url, seg_url) for seg_url in audio_keys_url_list]

            # save m3u8 file to disk
            with open(os.path.join(d.temp_folder, 'remote_audio.m3u8'), 'w') as f:
                f.write(audio_m3u8)

            # build audio segments (merge=False, post_process_hls will merge them via ffmpeg)
            audio_segments = [Segment(name=os.path.join(d.temp_folder, str(i) + '_audio.ts'), num=i, range=None, size=0,
                                      url=seg_url, tempfile=d.audio_file, merge=False)
                              for i, seg_url in enumerate(audio_url_list)]

            # audio crypt segments
            akeys = [Segment(name=os.path.join(d.temp_folder, 'audio_crypt' + str(i) + '.key'), num=i, range=None, size=0,
                                      url=seg_url, seg_type='audio_key', merge=False)
                              for i, seg_url in enumerate(audio_keys_url_list)]

            # add to video segments
            d.segments += audio_segments + akeys
        
        else:
            # Case B: Audio is NOT an m3u8 (likely direct DASH/mp4 stream)
            log("pre_process_hls()> Audio appears to be a direct stream. Adding as single segment.")
            
            # Create a single segment for the entire audio file
            # merge=True means file_manager will append downloaded data to tempfile (d.audio_file)
            audio_segments = [Segment(
                name=os.path.join(d.temp_folder, 'direct_audio.ts'), # name doesn't matter much for direct
                num=0, 
                range=None, 
                size=d.audio_size if d.audio_size else 0,
                url=d.audio_url, 
                tempfile=d.audio_file, 
                merge=True
            )]
            
            d.segments += audio_segments

    # load previous segment information from disk - resume download -
    d.load_progress_info()

    log('pre_process_hls()> done processing', d.name)

    return True


def post_process_hls(d):
    log('post_process_hls()> starting concat merge', d.name)

    # 1. Create mylist.txt (The Concat Demuxer list)
    concat_list_path = os.path.join(d.temp_folder, 'mylist.txt')
    try:
        # Get all segments for this video
        video_segments = [seg.name for seg in d.segments if seg.tempfile == d.temp_file]
        
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for seg_path in video_segments:
                # IMPORTANT: Use filename only, NOT full path
                f.write(f"file '{os.path.basename(seg_path)}'\n")
    except Exception as e:
        log('post_process_hls()> error creating mylist.txt:', e)
        return False

    # 2. Run Concat with Fallback Logic
    primary_ffmpeg = config.get_effective_ffmpeg()
    fallback_ffmpeg = r"C:\Users\Annorion\Desktop\Apps\dist\ffmpeg.exe" 

    success = False
    for ffmpeg_path in [fallback_ffmpeg, primary_ffmpeg]:
        if not os.path.exists(ffmpeg_path): continue
        
        log(f"Attempting merge with: {os.path.basename(ffmpeg_path)}")
        
        cmd = f'"{ffmpeg_path}" -nostdin -y -loglevel error -f concat -safe 0 -i "mylist.txt" -c copy -fflags +genpts -f mp4 "{d.temp_file}"'
        
        # We pass cwd=d.temp_folder so FFmpeg 'stands' in the folder with the files
        error, output = run_command(cmd, d=d, cwd=d.temp_folder)
        
        if not error:
            success = True
            log('post_process_hls()> successfully merged')
            break
        else:
            log(f"FFmpeg failed with {os.path.basename(ffmpeg_path)}: {output}")

    return success

def post_process_hls_custom(d, segment_paths, output_file):
    """Combines segments by binary appending. Best for DASH/HTTPS fragments."""
    if not segment_paths:
        return True
    
    def get_num(path):
        # This looks for digits specifically at the very end of the string
        match = re.search(r'(\d+)$', os.path.basename(path))
        if not match:
            # Fallback for filenames like "0_audio"
            match = re.search(r'(\d+)', os.path.basename(path))
        return int(match.group(1)) if match else 0
        
    segment_paths.sort(key=get_num)

    try:
        log(f"Binary stitching {len(segment_paths)} segments into {output_file}")
        with open(output_file, 'wb') as target:
            for path in segment_paths:
                if os.path.exists(path):
                    with open(path, 'rb') as source:
                        # Use a buffer to handle large files efficiently
                        shutil.copyfileobj(source, target)
                else:
                    log(f"Warning: Segment missing during stitch: {path}", log_level=2)
                    return False
        return True
    except Exception as e:
        log(f"Stitching failed: {e}", log_level=0)
        return False



