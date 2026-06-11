
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
import json
import shutil
import platform
from queue import Queue
from pathlib import Path
from typing import Optional

# -------------------------------------------------------------------------------------
# PLATFORM DETECTION & BASE PATHS
# -------------------------------------------------------------------------------------
IS_WIN = platform.system() == "Windows"
EXE_EXT = ".exe" if IS_WIN else ""
operating_system = platform.system()
operating_system_info = f'{platform.platform()} - {platform.machine()}'


# -------------------------------------------------------------------------------------
# CREATOR & APP INFO
# -------------------------------------------------------------------------------------
APP_NAME = 'OmniPull'
APP_ID = APP_NAME
APP_CREATOR = "Emmanuel Gyimah Annor"
APP_URL = "https://omnipull.pythonanywhere.com/"
APP_DESCRIPTION = "ODM is a python open source Internet Download Manager with multi-connections,\nhigh speed engine, it downloads general files and videos from YouTube\nand tons of other streaming websites."

# Cross-platform data directory logic
if IS_WIN:
    # Windows: C:\Users\Name\AppData\Roaming\OmniPull
    DATA_ROOT = Path(os.environ.get("APPDATA", Path.home())) / f".{APP_NAME}"
else:
    # Linux/macOS: ~/.local/share/OmniPull
    DATA_ROOT = Path.home() / ".local" / "share" / APP_NAME

USER_CURRENT = DATA_ROOT / "current"
CONFIG_BIN = Path.home() / ".config" / "OmniPull"
ARIA2C_SESSION_DIR = DATA_ROOT
ARIA2C_SESSION_FILE = ARIA2C_SESSION_DIR / "aria2c.session"

# -------------------------------------------------------------------------------------
# CONSTANTS & APP INFO
# -------------------------------------------------------------------------------------
try:
    from modules.version import __version__
    APP_VERSION = __version__
except ImportError:
    APP_VERSION = "0.0.1"

APP_DEC = "Free download manager"
APP_TITLE = f'{APP_NAME} version {APP_VERSION} .. an open source download manager'
APP_FONT_DPI = 120
DEFAULT_DOWNLOAD_FOLDER = str(Path.home() / "Downloads")
DEFAULT_THEME = 'DarkGrey2'
DEFAULT_CONNECTIONS = 64
DEFAULT_SEGMENT_SIZE = 524288
DEFAULT_CONCURRENT_CONNECTIONS = 3
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3721.3'
TEST_MODE = False
FROZEN = getattr(sys, "frozen", False)  # check if app is being compiled by cx_freeze
LOG_MODE = "overwrite"   # options: "overwrite", "append"
# -------------------------------------------------------------------------------------
# TOOL RESOLUTION ENGINE
# -------------------------------------------------------------------------------------

def _find_tool(name: str, *, selected: str|None = None, bundled_name: str, extra_paths: list[str], allow_which: bool = True) -> str|None:
    """Resolution: 1. User Choice -> 2. Bundled Folder -> 3. System PATH -> 4. Extras"""
    if IS_WIN:
        if not name.lower().endswith(".exe"): name += ".exe"
        if not bundled_name.lower().endswith(".exe"): bundled_name += ".exe"

    if selected and Path(selected).exists():
        return str(Path(selected))

    
    bundled = USER_CURRENT / bundled_name if name == "aria2c" else CONFIG_BIN / bundled_name
    if bundled.exists():
        return str(bundled)

    if allow_which:
        on_path = shutil.which(name)
        if on_path: return on_path

    for p in extra_paths:
        path_obj = Path(p)
        if path_obj.exists(): return str(path_obj)
    return None

# -------------------------------------------------------------------------------------
# BINARY PATH RESOLUTION (FFMPEG, YT-DLP, ARIA2C, DENO)
# -------------------------------------------------------------------------------------




# These will be set by the UI/Settings loader
user_selected_ffmpeg: Optional[str] = None
user_selected_ytdlp: Optional[str] = None
user_selected_deno: Optional[str] = None

# FFMPEG
_ffmpeg_extra = [
    os.path.join(CONFIG_BIN, "ffmpeg"),
    str(DATA_ROOT / f"ffmpeg{EXE_EXT}"),
    "C:\\ffmpeg\\bin\\ffmpeg.exe", 
    "/usr/bin/ffmpeg",
    
]
ffmpeg_actual_path = _find_tool("ffmpeg", bundled_name="ffmpeg", extra_paths=_ffmpeg_extra)
ffmpeg_selected_path = None
ffmpeg_verified = False
ffmpeg_actual_path_2 = ffmpeg_actual_path  # Legacy variable for backward compatibility


# YT-DLP
yt_dlp_exe = ""  # Legacy UI variable
cached_ytdlp_version = None
_ytdlp_extra = [
    os.path.join(CONFIG_BIN, "yt-dlp"),
    str(DATA_ROOT / f"yt-dlp{EXE_EXT}"),
    str(USER_CURRENT / f"yt-dlp{EXE_EXT}"),
    
]
yt_dlp_actual_path = _find_tool("yt-dlp", bundled_name="yt-dlp", extra_paths=_ytdlp_extra)
use_ytdlp_exe = False
enable_ytdlp_exe = False

# ARIA2C (Required by Aria2cManager)
ARIA2C_CMD_NAME = "aria2c"
ARIA2C_BIN_NAME = "aria2c"
_aria2c_extra_paths = [
    str(DATA_ROOT / f"aria2c{EXE_EXT}"), # Look in .OmniPull/aria2c.exe
    "C:\\Program Files\\aria2\\aria2c.exe", 
    "/usr/bin/aria2c"
]
aria2_actual_path = _find_tool(ARIA2C_CMD_NAME, bundled_name=ARIA2C_BIN_NAME, extra_paths=_aria2c_extra_paths)
aria2_verified = False
aria2c_path = aria2_actual_path

# DENO
deno_exe = ""  # Legacy UI variable
_deno_extra = [
    os.path.join(CONFIG_BIN, "deno"),
    str(DATA_ROOT / f"deno{EXE_EXT}"),
    str(Path.home() / ".deno" / "bin" / f"deno{EXE_EXT}"),
    
]
deno_actual_path = _find_tool("deno", bundled_name="deno", extra_paths=_deno_extra)
deno_verified = False

# -------------------------------------------------------------------------------------
# SETTINGS & STATE
# -------------------------------------------------------------------------------------
terminate = False
download_engine = 'curl'
current_theme = DEFAULT_THEME
bg_color_dark = '#14161a'
menu_bg = '#1f2227'
toolbar_bg = '#1b1e23'
text_color = '#e8eaed'
accent_color =  '#2b80ff'
progress_color = accent_color
all_themes = []
lang = "English"
monitor_clipboard = True
show_download_window = True
auto_close_download_window = True
segment_size = DEFAULT_SEGMENT_SIZE
show_thumbnail = True
on_startup = False
hide_app = False
tutorial_completed = False

# Network
enable_speed_limit = False
speed_limit = 0
max_concurrent_downloads = DEFAULT_CONCURRENT_CONNECTIONS
max_connections = DEFAULT_CONNECTIONS
retry_scheduled_enabled = True
retry_scheduled_max_tries = 3
retry_scheduled_interval_mins = 5
browser_integration_enabled = True

# Proxy
proxy = ''
proxy_type = 'http'
raw_proxy = ''
proxy_user = ""
proxy_pass = ""
enable_proxy = False

# Updates
update_frequency = 7
last_update_check = 0
APP_LATEST_VERSION = ''
confirm_update = False
force_exit_for_update = True

# macOS-specific update tracking
update_first_notified = None  # Timestamp when user was first notified of update (macOS)
update_grace_period_days = 7  # Days before forcing update on macOS
update_dismissed_version = None  # Track which version user dismissed
update_dismissed_timestamp = None  # ISO timestamp when user deferred update (grace period start)

preferred_audio_langs = ["en-US", "en", "eng", None]

# -------------------------------------------------------------------------------------
# DIRECTORIES & LOGGING
# -------------------------------------------------------------------------------------
current_directory = os.path.dirname(os.path.abspath(__file__))
sett_folder = current_directory
download_folder = DEFAULT_DOWNLOAD_FOLDER
ffmpeg_download_folder = sett_folder
deno_download_folder = sett_folder

log_level = 1
log_entry = ''
max_log_size = 1024 * 1024 * 5
log_recorder_q = Queue()
show_all_logs = False

# -------------------------------------------------------------------------------------
# COMPONENT CONFIGURATIONS
# -------------------------------------------------------------------------------------
aria2c_config = {
    "max_connections": 1,
    "enable_dht": True,
    "follow_torrent": True,
    "save_interval": 10,
    "file_allocation": "none" if IS_WIN else "falloc",
    "split": 32,
    "rpc_port": 6800
}

ytdlp_config = {
    "no_playlist": True,
    'list_formats': True,
    'ignore_errors': True,
    "merge_output_format": "mp4",
    "concurrent_fragment_downloads": 5,
    "outtmpl": '%(title)s.%(ext)s',
    "retries": 3,
    "ffmpeg_location": ffmpeg_actual_path, 
    'quiet': True,
    'sleep_interval_requests': 10,
    'max_sleep_interval': 10,
    'sleep_interval_subtitles': 10,
    'writeinfojson': True,
    'writedescription': True,
    "writemetadata": True,
    "no_warnings": True,
    "cookiesfile": "",
}

# Queue for main window
main_window_q = Queue()
active_downloads = set()
d_list = []

# ---------- helper setters so UI can update selections at runtime ----------
def set_user_ffmpeg(path: Optional[str]):
    """Call this when user picks a custom ffmpeg path from the UI."""
    global user_selected_ffmpeg, ffmpeg_actual_path
    user_selected_ffmpeg = str(path) if path else None
    ffmpeg_actual_path = _find_tool("ffmpeg", selected=user_selected_ffmpeg, bundled_name="ffmpeg.exe", extra_paths=_ffmpeg_extra)
    return ffmpeg_actual_path


def set_user_ytdlp(path: Optional[str]):
    """Call this when user picks a custom yt-dlp executable from the UI."""
    global user_selected_ytdlp, yt_dlp_exe, yt_dlp_actual_path
    user_selected_ytdlp = str(path) if path else None
    # keep the legacy variable in sync as some code may refer to yt_dlp_exe
    yt_dlp_exe = user_selected_ytdlp or ""
    yt_dlp_actual_path = _find_tool("yt-dlp", selected=user_selected_ytdlp or yt_dlp_exe, bundled_name="yt-dlp.exe", extra_paths=_ytdlp_extra)
    return yt_dlp_actual_path


def set_user_deno(path: Optional[str]):
    """Call this when user picks a custom yt-dlp executable from the UI."""
    global user_selected_deno, deno_exe, deno_actual_path
    user_selected_deno = str(path) if path else None
    # keep the legacy variable in sync as some code may refer to deno_exe
    deno_exe = user_selected_deno or ""
    deno_actual_path = _find_tool("deno", selected=user_selected_deno or deno_exe, bundled_name="deno.exe", extra_paths=_deno_extra)
    return deno_actual_path

# ---------- convenience getters for other modules ----------
def get_effective_ffmpeg() -> Optional[str]:
    """Return the best ffmpeg path found (user -> bundled -> system)"""
    return ffmpeg_actual_path

def get_effective_ytdlp() -> Optional[str]:
    """Return best yt-dlp path found (user -> bundled -> system)"""
    return yt_dlp_actual_path

def get_effective_deno() -> Optional[str]:
    """Return best deno path found (user -> bundled -> system)"""
    return deno_actual_path

# -------------------------------------------------------------------------------------
# PERSISTENCE KEYS
# -------------------------------------------------------------------------------------
settings_keys = [
    'current_theme','machine_id', 'tutorial_completed', 'download_engine', 'APP_FONT_DPI',
    'lang', 'monitor_clipboard', 'show_download_window', 'auto_close_download_window',
    'segment_size', 'show_thumbnail', 'on_startup', 'show_all_logs', 'hide_app',
    'enable_speed_limit', 'speed_limit', 'max_concurrent_downloads', 'max_connections',
    'update_frequency','update_dismissed_timestamp', 'last_update_check','APP_LATEST_VERSION', 'confirm_update',
    'update_first_notified', 'update_grace_period_days', 'update_dismissed_version',
    'proxy', 'proxy_type', 'raw_proxy', 'proxy_user', 'proxy_pass', 'enable_proxy',
    'log_level', 'download_folder', 'retry_scheduled_enabled', 'retry_scheduled_max_tries',
    'retry_scheduled_interval_mins', 'aria2c_config', 'aria2_verified', 'ytdlp_config',
    'ffmpeg_selected_path', 'preferred_audio_langs', 'enable_ytdlp_exe', 'use_ytdlp_exe',
    'yt_dlp_exe', 'deno_verified', 'deno_exe', 'bg_color', 'menu_bg', 'toolbar_bg',
    'text_color', 'accent_color', 'progress_color', 'force_exit_for_update',
    'user_selected_ffmpeg', 'user_selected_ytdlp', 'user_selected_deno', 'deno_download_folder', 
    'ffmpeg_download_folder', 'cached_ytdlp_version', 'LOG_MODE', 'IS_WIN'
]

class Status:
    downloading = 'downloading'
    paused = 'paused'
    cancelled = 'cancelled'
    completed = 'completed'
    pending = 'pending'
    merging_audio = 'merging_audio'
    merging = 'merging'
    error = 'error'
    scheduled = 'scheduled'
    failed = "failed"
    deleted = "deleted"
    queued = "queued"
    stitching = 'stitching'
    unzipping = 'unzipping'






