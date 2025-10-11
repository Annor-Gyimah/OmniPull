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
import sys
import shutil
import platform

from queue import Queue
from pathlib import Path
from typing import Optional
from modules.utils import log
from modules.version import __version__




# CONSTANTS
APP_NAME = 'OmniPull'
APP_VERSION = __version__ 
APP_DEC = "Free download manager"
APP_TITLE = f'{APP_NAME} version {APP_VERSION} .. an open source download manager'
APP_FONT_DPI = 96
DEFAULT_DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), 'Downloads')
DEFAULT_THEME = 'DarkGrey2'
DEFAULT_CONNECTIONS = 64
DEFAULT_SEGMENT_SIZE = 524288  # 1048576  in bytes
DEFAULT_CONCURRENT_CONNECTIONS = 3

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3721.3'
DEFAULT_LOG_LEVEL = 1
 
APP_LATEST_VERSION = ''  # get value from update module
ytdl_VERSION = 'xxx'  # will be loaded once yt-dlp get imported
ytdl_LATEST_VERSION = None  # get value from update module

TEST_MODE = False
FROZEN = getattr(sys, "frozen", False)  # check if app is being compiled by cx_freeze
# -------------------------------------------------------------------------------------

# current operating system  ('Windows', 'Linux', 'Darwin')
operating_system = platform.system()
operating_system_info = f'{platform.platform()} - {platform.machine()}'   # i.e. Win7-64 and Vista-32
machine_id = None

# application exit flag
terminate = False 

# download engine
download_engine = 'curl'  # download engine to be used, aria2c or yt-dlp


# settings parameters
current_theme = DEFAULT_THEME
all_themes = []
lang = "English"
monitor_clipboard = True
show_download_window = True
auto_close_download_window = True
segment_size = DEFAULT_SEGMENT_SIZE  # in bytes
show_thumbnail = True  # auto preview video thumbnail at main tab
on_startup = False
hide_app = False
tutorial_completed = False  # used to show tutorial on first run

# connection / network
enable_speed_limit = False
speed_limit = 0  # in kbytes, zero == no limit  todo: make it in bytes instead of kb
max_concurrent_downloads = DEFAULT_CONCURRENT_CONNECTIONS
max_connections = DEFAULT_CONNECTIONS

retry_scheduled_enabled = True
retry_scheduled_max_tries = 3
retry_scheduled_interval_mins = 5

# Browser Integration
browser_integration_enabled = True


# update
update_frequency = 7  # 'every day'=1, every week=7, every month=30 and so on
last_update_check = 0  # day number in the year range from 1 to 366
update_frequency_map = {'every day': 1, 'every week': 7, 'every month': 30}
confirm_update = False
# version_check_number = None

# proxy
proxy = ''  # must be string example: 127.0.0.1:8080
proxy_type = 'http'  # socks4, socks5
raw_proxy = ''  # unprocessed from user input
proxy_user = ""  # optional
proxy_pass = ""  # optional
enable_proxy = False

# logging
log_entry = ''  # one log line
max_log_size = 1024 * 1024 * 5  # 5 MB
log_level = DEFAULT_LOG_LEVEL  # standard=1, verbose=2, debug=3
log_recorder_q = Queue()
show_all_logs = False
# -------------------------------------------------------------------------------------

# folders
if hasattr(sys, 'frozen'):  # like if application froen by cx_freeze
    current_directory = os.path.dirname(sys.executable)
else:
    path = os.path.realpath(os.path.abspath(__file__))
    current_directory = os.path.dirname(path)
sys.path.insert(0, os.path.dirname(current_directory))
sys.path.insert(0, current_directory)


sett_folder = os.path.dirname(os.path.abspath(__file__))
# location where user-specific bundled binaries might live:
USER_CURRENT = Path(sett_folder) 
global_sett_folder = None
download_folder = DEFAULT_DOWNLOAD_FOLDER

# user-selected overrides (UI should set these when user browses)
user_selected_ffmpeg: Optional[str] = None
user_selected_ytdlp: Optional[str] = None

# helper to pick a tool path

def _find_tool(name: str, *, selected: Optional[str] = None, bundled_name: str, extra_paths: list[str] = []) -> Optional[str]:
    # 1) user-chosen
    if selected:
        p = Path(selected)
        if p.exists():
            return str(p)

    # 2) bundled (user-space)
    bundled = os.path.join(sett_folder, bundled_name)
    if os.path.exists(bundled):
        return str(bundled)

    # 3) system PATH
    on_path = shutil.which(name)
    if on_path:
        return on_path

    # 4) extra known paths
    for p in extra_paths:
        pp = Path(p)
        if pp.exists():
            return str(pp)

    return None


# ---------- ffmpeg resolution ----------
# Provide some reasonable extra lookup paths for ffmpeg on common installs (adjust as needed)
_ffmpeg_extra_paths = [
    # Windows common places
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    # *nix (if running cross-platform)
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
]

# Resolve effective ffmpeg path at import time (user-selected path might be None)
ffmpeg_actual_path = _find_tool(
    "ffmpeg",
    selected=user_selected_ffmpeg,
    bundled_name="ffmpeg.exe",
    extra_paths=_ffmpeg_extra_paths,
)

# keep an alias for legacy code that expects ffmpeg_actual_path_2 or ffmpeg_download_folder
ffmpeg_actual_path_2 = global_sett_folder
ffmpeg_download_folder = sett_folder
ffmpeg_verified = False  # will be set True after runtime verification if you choose to verify

# ---------- aria2c (keep as before) ----------
aria2_download_folder = sett_folder
aria2_actual_path = None
aria2_verified = False
aria2c_path = aria2_actual_path
aria2c_config = {
    "max_connections": 1,
    "enable_dht": True,
    "follow_torrent": True,
    "save_interval": 10,
    "file_allocation": "falloc",
    "split": 32,
    "rpc_port": 6800,
}

# ---------- yt-dlp resolution ----------
# Provide some extra lookup paths for yt-dlp if you want
_ytdlp_extra_paths = [
    os.path.join(sett_folder, "yt-dlp.exe"),
    os.path.join(sett_folder, "bin", "yt-dlp.exe"),
]

# By default the global config variable `yt_dlp_exe` may be used by UI to store user selection;
# keep the variable name for compatibility but resolve the "actual" path via _find_tool.
preferred_audio_langs = ["en-US", "en", "eng", None]
ytdlp_fragments = 5  # default number of threads/fragments
yt_dlp_exe = ""       # stores user-chosen path (UI may set)
use_ytdlp_exe = False # default preference flag
enable_ytdlp_exe = False

yt_dlp_actual_path = _find_tool(
    "yt-dlp",
    selected=(yt_dlp_exe or user_selected_ytdlp),
    bundled_name="yt-dlp.exe",
    extra_paths=_ytdlp_extra_paths,
)


# ---------- helper setters so UI can update selections at runtime ----------
def set_user_ffmpeg(path: Optional[str]):
    """Call this when user picks a custom ffmpeg path from the UI."""
    global user_selected_ffmpeg, ffmpeg_actual_path
    user_selected_ffmpeg = str(path) if path else None
    ffmpeg_actual_path = _find_tool("ffmpeg", selected=user_selected_ffmpeg, bundled_name="ffmpeg.exe", extra_paths=_ffmpeg_extra_paths)
    return ffmpeg_actual_path


def set_user_ytdlp(path: Optional[str]):
    """Call this when user picks a custom yt-dlp executable from the UI."""
    global user_selected_ytdlp, yt_dlp_exe, yt_dlp_actual_path
    user_selected_ytdlp = str(path) if path else None
    # keep the legacy variable in sync as some code may refer to yt_dlp_exe
    yt_dlp_exe = user_selected_ytdlp or ""
    yt_dlp_actual_path = _find_tool("yt-dlp", selected=user_selected_ytdlp or yt_dlp_exe, bundled_name="yt-dlp.exe", extra_paths=_ytdlp_extra_paths)
    return yt_dlp_actual_path


# ---------- convenience getters for other modules ----------
def get_effective_ffmpeg() -> Optional[str]:
    """Return the best ffmpeg path found (user -> bundled -> system)"""
    return ffmpeg_actual_path

def get_effective_ytdlp() -> Optional[str]:
    """Return best yt-dlp path found (user -> bundled -> system)"""
    return yt_dlp_actual_path




# def get_effective_ytdlp() -> Optional[str]:
#     """Return best yt-dlp path found (user -> bundled -> system)"""
#     path = yt_dlp_actual_path
#     if not path:
#         # Try bundled path directly as a fallback
#         bundled = USER_CURRENT / "yt-dlp.exe"
#         if bundled.exists():
#             return str(bundled)
#     return path


browser = 'edge'
browser_profile = 'Default'



ytdlp_config = {
    "no_playlist": True,
    'list_formats': True,
    'ignore_errors': True,
    "concurrent_fragment_downloads": 5,
    # "merge_output_format": "mp4",
    "outtmpl": '%(title)s.%(ext)s',
    "retries": 3,
    "ffmpeg_location": ffmpeg_actual_path, 
    'quiet': True,
    'writeinfojson': True,
    'writedescription': True,
    'writeannotations': True,
    "writemetadata": True,
    "no_warnings": True,
    "cookiesfile": "",
}


# downloads
active_downloads = set()  # indexes for active downloading items
d_list = []

# queues
main_window_q = Queue()  # queue for Main application window

# settings parameters to be saved on disk
settings_keys = ['current_theme','machine_id', 'tutorial_completed', 'download_engine', 'APP_FONT_DPI', 'lang', 'monitor_clipboard', 'show_download_window', 'auto_close_download_window',
                 'segment_size', 'show_thumbnail', 'on_startup', 'show_all_logs', 'hide_app', 'enable_speed_limit', 'speed_limit', 'max_concurrent_downloads', 'max_connections',
                 'update_frequency', 'last_update_check','APP_LATEST_VERSION', 'confirm_update', 'proxy', 'proxy_type', 'raw_proxy', 'proxy_user', 'proxy_pass', 'enable_proxy',
                 'log_level', 'download_folder', 'retry_scheduled_enabled', 'retry_scheduled_max_tries', 'retry_scheduled_interval_mins', 'aria2c_config',
                 'aria2_verified', 'ytdlp_config', 'preferred_audio_langs', 'enable_ytdlp_exe', 'use_ytdlp_exe', 'yt_dlp_exe']

# -------------------------------------------------------------------------------------


# status class as an Enum
class Status:
    """used to identify status, work as an Enum"""
    downloading = 'downloading'
    paused = 'paused'
    cancelled = 'cancelled'
    completed = 'completed'
    pending = 'pending'
    merging_audio = 'merging_audio'
    error = 'error'
    scheduled = 'scheduled'
    failed = "failed"
    deleted = "deleted"
    queued = "queued"













