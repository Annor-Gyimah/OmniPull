"""
    pyIDM

    multi-connections internet download manager, based on "pyCuRL/curl", "youtube_dl", and "PySide6"

    :copyright: (c) 2019-2020 by Mahmoud Elshahat.
    :license: GNU LGPLv3, see LICENSE for more details.
"""

# configurations
from queue import Queue
import os
import sys
import platform

from .version import __version__


# CONSTANTS
APP_NAME = 'OmniPull'
APP_VERSION = __version__ 
APP_DEC = "Free download manager"
APP_TITLE = f'{APP_NAME} version {APP_VERSION} .. an open source download manager'
DEFAULT_DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), 'Downloads')
DEFAULT_THEME = 'DarkGrey2'
DEFAULT_CONNECTIONS = 64
DEFAULT_SEGMENT_SIZE = 524288  # 1048576  in bytes
DEFAULT_CONCURRENT_CONNECTIONS = 3

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3721.3'
DEFAULT_LOG_LEVEL = 3
 
APP_LATEST_VERSION = None  # get value from update module
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

# connection / network
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

# proxy
proxy = ''  # must be string example: 127.0.0.1:8080
proxy_type = 'http'  # socks4, socks5
raw_proxy = ''  # unprocessed from user input
enable_proxy = False

# logging
log_entry = ''  # one log line
max_log_size = 1024 * 1024 * 5  # 5 MB
log_level = DEFAULT_LOG_LEVEL  # standard=1, verbose=2, debug=3
log_recorder_q = Queue()
# -------------------------------------------------------------------------------------

# folders
if hasattr(sys, 'frozen'):  # like if application froen by cx_freeze
    current_directory = os.path.dirname(sys.executable)
else:
    path = os.path.realpath(os.path.abspath(__file__))
    current_directory = os.path.dirname(path)
sys.path.insert(0, os.path.dirname(current_directory))
sys.path.insert(0, current_directory)

#sett_folder = None
sett_folder = os.path.dirname(os.path.abspath(__file__))
global_sett_folder = None
download_folder = DEFAULT_DOWNLOAD_FOLDER

# ffmpeg
#ffmpeg_actual_path = None
ffmpeg_actual_path = "/usr/bin/ffmpeg"
##ffmpeg_actual_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "/usr/bin/ffmpeg")
#ffmpeg_actual_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg/ffmpeg")
ffmpeg_actual_path_2 = "/usr/bin/"
ffmpeg_download_folder = sett_folder

# downloads
active_downloads = set()  # indexes for active downloading items
d_list = []

# queues
main_window_q = Queue()  # queue for Main application window

# settings parameters to be saved on disk
settings_keys = ['current_theme','machine_id', 'lang', 'monitor_clipboard', 'show_download_window', 'auto_close_download_window',
                 'segment_size', 'show_thumbnail', 'on_startup', 'speed_limit', 'max_concurrent_downloads', 'max_connections',
                 'update_frequency', 'last_update_check', 'confirm_update', 'proxy', 'proxy_type', 'raw_proxy', 'enable_proxy',
                 'log_level', 'download_folder', 'retry_scheduled_enabled', 'retry_scheduled_max_tries', 'retry_scheduled_interval_mins']

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
