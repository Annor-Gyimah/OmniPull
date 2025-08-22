"""
    OmniPull - a free and open source download manager for Windows, Linux, and MacOS.
    OmniPull is a cross-platform, multi-threaded, multi-segment, and multi-connections internet download manager, based on "pyCuRL/curl", "yt-dlp", and "PySide6"

    :copyright: (c) 2019-2020 by Mahmoud Elshahat.
    :license: GNU LGPLv3, see LICENSE for more details.
"""

# configurations
from queue import Queue
import os
import sys
import shutil
import subprocess
from pathlib import Path
import platform
from modules.version import __version__
from modules.utils import log


# CONSTANTS
APP_NAME = "OmniPull"
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
APP_VERSION = __version__ 
APP_DEC = "Free download manager"
APP_TITLE = f'{APP_NAME} version {APP_VERSION} .. an open source download manager'
APP_FONT_DPI = 60
DEFAULT_DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), 'Downloads')
DEFAULT_THEME = 'DarkGrey2'
DEFAULT_CONNECTIONS = 64
DEFAULT_SEGMENT_SIZE = 524288  # 1048576  in bytes
DEFAULT_CONCURRENT_CONNECTIONS = 3

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3721.3'
DEFAULT_LOG_LEVEL = 3
 
APP_LATEST_VERSION = ''  # get value from update module
ytdl_VERSION = 'xxx'  # will be loaded once youtube-dl get imported
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
tutorial_completed = False

# download engine
download_engine = 'yt-dlp'  # download engine to be used, aria2c or yt-dlp


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
global_sett_folder = None
download_folder = DEFAULT_DOWNLOAD_FOLDER

# ffmpeg
#ffmpeg_actual_path = None
# ---- Config-like vars (adapt to your config module if you prefer) ----
# Let these be populated from your settings or config module.
ffmpeg_actual_path = ""          # explicit override (if user set)
ffmpeg_selected_path = None      # user-picked path via UI (if any)
ffmpeg_download_folder = sett_folder
ffmpeg_verified = False # ffmpeg is verified or not
# -----------------------------------------------------------------------


def _app_bundle_resources_dir() -> Path:
    """
    Return the Resources directory for a frozen app bundle, or a sensible
    dev fallback when running from source.
    """
    if getattr(sys, "frozen", False):  # running from PyInstaller bundle
        exe = Path(sys.executable).resolve()  # .../Contents/MacOS/OmniPull
        return exe.parent.parent / "Resources"
    else:
        # Dev fallback: look for a local 'resources/bin/ffmpeg' or similar.
        # Adjust to where you keep the bundled tools when running from source.
        return Path(__file__).resolve().parent.parent / "macOS" / "resources"

def _possible_system_paths() -> list[Path]:
    """Likely system ffmpeg locations on macOS (Intel + Apple Silicon)."""
    return [
        Path("/usr/local/bin/ffmpeg"),   # Homebrew on Intel
        Path("/opt/homebrew/bin/ffmpeg"),# Homebrew on Apple Silicon
        Path("/usr/bin/ffmpeg"),         # sometimes present
    ]

def ensure_ffmpeg_installed(app_name: str = APP_NAME) -> Path | None:
    """
    If a bundled ffmpeg exists inside the app, copy it to:
      ~/Library/Application Support/<app_name>/ffmpeg
    strip quarantine, chmod +x, and return its path.
    If nothing to copy, return None.
    """
    res_dir = _app_bundle_resources_dir()
    bundled = res_dir / "bin" / "ffmpeg"
    dest = APP_SUPPORT_DIR / "ffmpeg"

    try:
        if bundled.exists():
            # Copy WITHOUT metadata (avoid carrying quarantine flags)
            shutil.copy(str(bundled), str(dest))
            os.chmod(dest, 0o755)
            # Best-effort remove quarantine on the user copy
            try:
                subprocess.run(
                    ["xattr", "-d", "com.apple.quarantine", str(dest)],
                    check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
            except Exception:
                pass
            return dest
    except Exception as e:
        print(f"[FFmpeg] install failed: {e}")

    return None

def get_ffmpeg_path(chosen: bool = True) -> str | None:
    """
    Resolve a usable ffmpeg path on macOS:
    1) user-selected path (settings)
    2) explicit override (ffmpeg_actual_path)
    3) per-user copy in App Support
    4) bundled inside app (Resources/bin/ffmpeg)
    5) PATH search
    6) common Homebrew paths
    """
    # 1) user-selected via settings dialog
    if chosen and ffmpeg_selected_path:
        p = Path(ffmpeg_selected_path)
        if p.is_file() and os.access(p, os.X_OK):
            log("A: Using user-selected ffmpeg path")
            return str(p)

    # 2) explicit override in config
    if ffmpeg_actual_path:
        p = Path(ffmpeg_actual_path)
        if p.is_file() and os.access(p, os.X_OK):
            log("B: Using config ffmpeg path")
            return str(p)

    # 3) App Support copy (preferred runtime location)
    app_support_ffmpeg = APP_SUPPORT_DIR / "ffmpeg"
    if app_support_ffmpeg.is_file() and os.access(app_support_ffmpeg, os.X_OK):
        log("C: Using App Support ffmpeg path")
        return str(app_support_ffmpeg)

    # 4) Bundled in the app (use it if present; or trigger a copy)
    res_dir = _app_bundle_resources_dir()
    bundled = res_dir / "bin" / "ffmpeg"
    if bundled.is_file() and os.access(bundled, os.X_OK):
        # Optionally copy to App Support for cleaner execution
        copied = ensure_ffmpeg_installed(APP_NAME)
        if copied:
            log("D: Using freshly installed App Support ffmpeg")
            return str(copied)
        log("D: Using bundled ffmpeg directly")
        return str(bundled)

    # 5) PATH search
    from shutil import which
    found = which("ffmpeg")
    if found:
        log("E: Using ffmpeg found in PATH")
        return found

    # 6) Common Homebrew paths
    for candidate in _possible_system_paths():
        if candidate.is_file() and os.access(candidate, os.X_OK):
            log("F: Using common Homebrew ffmpeg path")
            return str(candidate)

    # Not found
    log("Z: ffmpeg not found")
    return None



# aria2c
aria2_download_folder = sett_folder
aria2_actual_path = None
aria2_verified = False  # aria2c is verified or not
aria2c_path = aria2_actual_path 
#os.path.join('Miscellaneous', 'aria2c.exe')
aria2c_config = {
    "max_connections": 1,
    "enable_dht": True,
    "follow_torrent": False,
    "save_interval": 10,
    "file_allocation": "falloc",
    "split": 32,
    "rpc_port": 6800
}


ytdlp_fragments = 5  # default number of threads/fragments
ytdlp_config = {
    "no_playlist": True,
    'list_formats': True,
    'ignore_errors': True,
    "concurrent_fragment_downloads": 5,
    "merge_output_format": "mp4",
    "outtmpl": '%(title)s.%(ext)s',
    "retries": 3,
    "ffmpeg_location": get_ffmpeg_path(),
    "postprocessors": [
        {
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4'
        }
    ],
    'quiet': True,
    'writeinfojson': True,
    'writedescription': True,
    'writeannotations': True,
    "writemetadata": True,
    "no_warnings": True,
    "cookiesfile": ""
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
                 'aria2_verified', 'ytdlp_config', 'ffmpeg_actual_path']


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








