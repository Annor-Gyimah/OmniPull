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
import io
import re
import sys
import time
import json
import plyer
import base64
import pycurl
import shutil
import certifi
import hashlib
import platform
import subprocess
import pyperclip as clipboard


# from PIL import Image
from notifypy import Notify
from functools import lru_cache

from modules import config

try:
    from packaging.version import Version, InvalidVersion
except Exception:
    Version = None
    InvalidVersion = Exception    

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QPainter




# def resource_path2(relative_path):
#     """ Get absolute path to resource, works for dev and for PyInstaller """
#     base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
#     return os.path.join(base_path, relative_path)

def resource_path(relative_path):
    """
    Resolves the absolute path to a resource. 
    Supports both standard development environments and PyInstaller bundles (via _MEIPASS).
    """
    try:
        # PyInstaller creates a temporary folder for bundled assets
        base_path = sys._MEIPASS
    except Exception:
        # Fallback to the local directory of the script file
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, relative_path)

def notify(msg, title='', timeout=2):
    """
    Dispatches a system-level notification using the notifypy library.
    
    Attempts to locate the application logo in the bundled resources or local 
    directory before sending the non-blocking notification.
    """
    ctx = "NOTIFY"
    try:
        if config.IS_WIN:
            # Attempt to resolve the branding icon path
            icon_path = resource_path("logo1.png")
            
            if not os.path.exists(icon_path):
                current_dir = os.path.dirname(os.path.abspath(__file__))
                icon_path = os.path.join(current_dir, "logo1.png")
            
            if not os.path.exists(icon_path):
                log(f"Notification icon not found. Using system default.", log_level=2, context=ctx)

            # Initialize and configure the notification object
            notification = Notify()
            notification.application_name = f"{config.APP_NAME}"
            notification.title = f"{title}"
            notification.message = f"{msg}"
            notification.icon = icon_path
            notification.send(block=False)
        else:
            plyer.notification.notify(title=title, message=msg, app_name=config.APP_TITLE)
        
    except Exception as e:
        handle_exceptions(f'Notification failure: {e}')


def handle_exceptions(error):
    """
    Global exception router. 
    Rethrows errors in TEST_MODE for debugging, otherwise logs them silently.
    """
    if config.TEST_MODE:
        raise error
    else:
        log(error)


def set_curl_options(c):
    """
    Configures a pycurl object with standard connection and security parameters.
    
    Sets user agents, proxy settings, redirection limits, and SSL certificate 
    paths (via certifi) for secure multi-threaded transfers.
    """
    c.setopt(pycurl.USERAGENT, config.USER_AGENT)
    c.setopt(pycurl.PROXY, config.proxy)

    # Redirection handling
    c.setopt(pycurl.FOLLOWLOCATION, 1)
    c.setopt(pycurl.MAXREDIRS, 10)

    # Thread safety and SSL configuration
    c.setopt(pycurl.NOSIGNAL, 1) 
    c.setopt(pycurl.NOPROGRESS, 1)
    c.setopt(pycurl.CAINFO, certifi.where()) 

    # Connection timing and stall protection
    c.setopt(pycurl.CONNECTTIMEOUT, 30) 
    c.setopt(pycurl.LOW_SPEED_LIMIT, 1)
    c.setopt(pycurl.LOW_SPEED_TIME, 60)

    # Verbosity control based on global log levels
    if config.log_level >= 3:
        c.setopt(pycurl.VERBOSE, 1)
    else:
        c.setopt(pycurl.VERBOSE, 0)

    c.setopt(pycurl.HEADEROPT, 0)
    c.setopt(pycurl.TIMEOUT, 300)
    c.setopt(pycurl.AUTOREFERER, 1)

def get_headers(url, verbose=False):
    """
    Performs a lightweight HEAD request to retrieve server response headers.
    
    Returns a dictionary containing normalized header keys, the HTTP 
    status code, and the final effective URL (after redirects).
    """
    ctx = "CURL-HEADERS"
    curl_headers = {}

    def header_callback(header_line):
        """Internal callback to parse individual header lines into a dictionary."""
        if config.terminate:
            return

        header_line = header_line.decode('iso-8859-1').lower()

        if ':' not in header_line:
            return

        name, value = header_line.split(':', 1)
        curl_headers[name.strip()] = value.strip()
        
        if verbose:
            print(f"{name.strip()} : {value.strip()}")

    def debug_callback(handle, type, data, size=0, userdata=''):
        """Intercepts curl verbose output and routes it to the application log."""
        try:
            log(data.decode("utf-8"), context=ctx)
        except:
            pass
        return 0

    # Initialize curl handle
    c = pycurl.Curl()
    set_curl_options(c)

    # Configure handle for header-only inspection
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.NOBODY, 1)
    c.setopt(pycurl.HEADERFUNCTION, header_callback)

    try:
        c.perform()
    except Exception as e:
        log(f'Header request error for {url}: {e}', context=ctx)

    # Capture final response metadata before closing the connection
    try:
        curl_headers['status_code'] = c.getinfo(pycurl.RESPONSE_CODE)
        curl_headers['eff_url'] = c.getinfo(pycurl.EFFECTIVE_URL)
    except Exception:
        curl_headers['status_code'] = 0
        curl_headers['eff_url'] = url

    try:
        c.close()
    except Exception:
        pass

    return curl_headers



def download(url, file_name=None, headers=None):
    """
    Performs a simple file download.
    
    :param url: The target URL string.
    :param file_name: Path to save file on disk. If None, data is buffered to memory.
    :param headers: Optional dictionary of HTTP headers.
    :return: True if saved to file, BytesIO buffer if memory mode, or False if failed.
    """
    ctx = "DOWNLOAD-UTIL"
    if not url:
        log('Download failed: URL is not valid.', log_level=2, context=ctx)
        return False

    log(f'Initiating download: {url}', log_level=3, context=ctx)

    def set_options():
        """Internal helper to configure pycurl options."""
        if 'set_curl_options' in globals():
            set_curl_options(c)
        else:
            # Fallback security defaults if global options are missing
            c.setopt(pycurl.FOLLOWLOCATION, 1)
            c.setopt(pycurl.SSL_VERIFYPEER, 0)
            c.setopt(pycurl.SSL_VERIFYHOST, 0)

        c.setopt(pycurl.URL, url)
        
        # Apply custom HTTP headers if provided
        if headers and isinstance(headers, dict):
            # Convert dict to PyCurl-compatible list: ["Key: Value", ...]
            header_list = [f"{k}: {v}" for k, v in headers.items()]
            c.setopt(pycurl.HTTPHEADER, header_list)

    file = None
    buffer = None
    c = pycurl.Curl()
    set_options()

    # Route output to disk or memory buffer
    if file_name:
        file = open(file_name, 'wb')
        c.setopt(c.WRITEDATA, file)
    else:
        buffer = io.BytesIO()
        c.setopt(c.WRITEDATA, buffer)

    try:
        c.perform()
        
        # Verify successful HTTP response
        code = c.getinfo(pycurl.RESPONSE_CODE)
        if code >= 400:
            log(f"Download aborted: HTTP Error {code}", log_level=2, context=ctx)
            return False

    except Exception as e:
        log(f'Download exception: {e}', log_level=2, context=ctx)
        return False
    finally:
        c.close()
        if file:
            file.close()

    log('Download completed successfully.', log_level=1, context=ctx)

    # Return True for disk mode, otherwise return the memory buffer
    if file_name:
        return True

    return buffer

def size_format(size, tail=''):
    """
    Converts a byte count into a human-readable string (KB, MB, GB).
    """
    try:
        if size == 0: 
            return '...'
        
        if size < 1024:
            s = f'{round(size)} bytes'
        elif 1_048_576 > size >= 1024:
            s = f'{round(size / 1024)} KB'
        elif 1_073_741_824 > size >= 1_048_576:
            s = f'{round(size / 1_048_576, 1)} MB'
        else:
            s = f'{round(size / 1_073_741_824, 2)} GB'
            
        return f'{s}{tail}'
    except Exception:
        return size

def time_format(t, tail=''):
    """
    Converts a second count into a human-readable duration string.
    """
    if t == -1:
        return '...'

    try:
        if t <= 60:
            s = f'{round(t)} seconds'
        elif 60 < t <= 3600:
            s = f'{round(t / 60)} minutes'
        elif 3600 < t <= 86400:
            s = f'{round(t / 3600, 1)} hours'
        elif 86400 < t <= 2592000:
            s = f'{round(t / 86400, 1)} days'
        elif 2592000 < t <= 31536000:
            s = f'{round(t / 2592000, 1)} months'
        else:
            s = f'{round(t / 31536000, 1)} years'

        return f'{s}{tail}'
    except Exception:
        return t


def log(*args, context: str = None, log_level: int = 1):
    # 1. Performance Gate (Existing Logic)
    if log_level == 4:
        if config.show_all_logs or config.log_level != 4: return
    else:
        if not config.show_all_logs and log_level < config.log_level: return

    # 2. Build the Message
    inner_text = ' '.join(str(arg) for arg in args)
    
    # 3. Apply Static Context
    # Format: [CONTEXT] >> MESSAGE
    prefix = f"[{context.upper()}] " if context else ""
    text = f">> {prefix}{inner_text}"

    # 4. Thread-Safe Dispatch
    try:
        print(text)
        config.log_entry = text
        config.log_recorder_q.put(text + '\n')
        config.main_window_q.put(('log', text + '\n'))
    except Exception as e:
        print(f"Logging fail: {e}")


def echo_stdout(func):
    """Copy stdout / stderr and send it to gui"""

    def echo(text):
        try:
            config.main_window_q.put(('log', text))
            return func(text)
        except:
            return func(text)

    return echo


def echo_stderr(func):
    """Copy stdout / stderr and send it to gui"""

    def echo(text):
        try:
            config.main_window_q.put(('log', text))
            return func(text)
        except:
            return func(text)

    return echo

@lru_cache(maxsize=128)
def validate_file_name(f_name):
    """""
    Sanitizes filenames by removing illegal characters and restricting length.
    
    1. Filters characters to remain within the Tkinter-safe Unicode range.
    2. Replaces OS-prohibited characters with underscores.
    3. Truncates the filename to approximately 100 characters for filesystem compatibility.
    """""
    # Filter for Tkinter-safe character range (BMP)
    f_name = ''.join([c for c in f_name if ord(c) in range(65536)])
    
    safe_string = str()
    char_count = 0
    
    for c in str(f_name):
        # Replace OS-reserved illegal characters
        if c in ['\\', '/', ':', '?', '<', '>', '"', '|', '*']:
            safe_string += '_'
        else:
            safe_string += c

        # Length safety limit
        if char_count > 100:
            break
        else:
            char_count += 1
            
    return safe_string

def size_splitter(size, part_size):
    """
    Calculates a list of byte-range strings for segmented downloads.
    
    Example: size_splitter(100, 40) -> ['0-39', '40-79', '80-99']
    
    :param size: Total size of the file in bytes.
    :param part_size: The desired size of each segment in bytes.
    :return: A list of strings in 'start-end' format.
    """
    result = []

    if size == 0:
        result.append('0-0')
        return result

    # Determine the span per part, capped at total file size
    span = part_size if part_size <= size else size
    
    # Calculate initial number of parts
    parts = max(size // span, 1)

    x = 0
    # Adjust size for 0-based indexing (last byte is size - 1)
    size = size - 1 
    
    for i in range(parts):
        y = x + span - 1
        
        # Ensure the final segment captures all remaining bytes
        if size - y < span:
            y = size
            
        result.append(f'{x}-{y}')
        x = y + 1

    return result


def idm_style_splitter(size, max_connections=10):
    """
    IDM-style initial segmentation: Start with few large segments (2-4)
    and let dynamic splitting handle the rest during download.

    Returns list of size ranges for initial segments.
    Note: Ignores max_connections < 2 since dynamic splitting needs at least 2 initial segments.
    """
    result = []

    if size == 0:
        result.append('0-0')
        return result

    # Ensure max_connections is an integer
    try:
        max_connections = int(max_connections)
    except (ValueError, TypeError):
        max_connections = 10

    # Start with 2-4 initial segments based on file size
    if size < 10 * 1024 * 1024:  # < 10MB
        initial_parts = 2
    elif size < 100 * 1024 * 1024:  # < 100MB
        initial_parts = 3
    else:  # >= 100MB
        initial_parts = 4

    # For IDM-style dynamic segmentation, we need at least 2 initial segments
    # even if max_connections is 1, otherwise dynamic splitting can't work
    initial_parts = max(2, min(initial_parts, max_connections))

    span = size // initial_parts
    x = 0
    size = size - 1  # when we start counting from zero the last byte number should be size - 1

    for i in range(initial_parts):
        y = x + span - 1
        if i == initial_parts - 1:  # last segment gets any remainder
            y = size
        result.append(f'{x}-{y}')
        x = y + 1

    return result


def delete_folder(folder, verbose=False):
    """
    Recursively deletes a directory and all of its contents.
    
    :param folder: Path to the directory.
    :param verbose: If True, logs success or error messages.
    :return: True if deletion succeeded, False otherwise.
    """
    ctx = "FS-UTILS"
    try:
        shutil.rmtree(folder)
        if verbose:
            log(f'Successfully deleted folder: {folder}', log_level=1, context=ctx)
        return True
    except Exception as e:
        if verbose:
            log(f'delete_folder error: {e}', log_level=3, context=ctx)
        return False

def delete_file(file, verbose=False):
    """
    Removes a single file from the filesystem.
    
    :param file: Path to the file.
    :param verbose: If True, logs success or error messages.
    :return: True if deletion succeeded, False otherwise.
    """
    ctx = "FS-UTILS"
    try:
        os.unlink(file)
        if verbose:
            log(f'Successfully deleted file: {file}', log_level=1, context=ctx)
        return True
    except Exception as e:
        if verbose:
            log(f'delete_file error: {e}', log_level=3, context=ctx)
        return False

def rename_file(oldname=None, newname=None):
    """
    Renames or moves a file to a new destination.
    
    :param oldname: Current file path.
    :param newname: Target file path.
    :return: True if successful or names are identical, False on failure.
    """
    ctx = "FS-UTILS"
    if oldname == newname:
        return True

    try:
        os.rename(oldname, newname)
        log(f"Renamed file: {oldname} to {newname}", log_level=1, context=ctx)
        return True
    except Exception as e:
        log(f'rename_file error: {e}', log_level=1, context=ctx)
        return False

def get_seg_size(seg):
    """
    Calculates the byte count from a range string (e.g., '200-1000' returns 801).
    
    The calculation is inclusive: (End - Start + 1).
    :param seg: Range string in 'start-end' format.
    :return: Integer size in bytes, or 0 if parsing fails.
    """
    try:
        # Split the range string into start and end integers
        parts = seg.split('-')
        a, b = int(parts[0]), int(parts[1])
        
        # Calculate inclusive size
        size = b - a + 1 if b > 0 else 0
        return size
    except Exception:
        return 0





def run_command_2(cmd, verbose=True, hide_window=False, d=None):
    import subprocess, sys
    
    # 1. Handle NoneType in list and convert all to strings
    if isinstance(cmd, (list, tuple)):
        if None in cmd:
            return True, "Error: Command list contains None values (File not found)"
        cmd = [str(x) for x in cmd]
    
    # 2. Allow strings by setting shell=True if it's a string
    is_shell = isinstance(cmd, str)

    startupinfo = None
    if hide_window and sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        # Using Popen + communicate is safer for long FFmpeg outputs
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=is_shell,
            startupinfo=startupinfo,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )

        output, _ = process.communicate()
        
        if verbose and output:
            for line in output.splitlines():
                log(f"[FFmpeg] {line}", log_level=1)

        if d and getattr(d, "status", None) == config.Status.cancelled:
            process.kill()
            return True, "Cancelled by user"

        return (process.returncode != 0), output

    except Exception as e:
        return True, f"Exception running command: {e}"

def run_command(cmd, d=None, cwd=None):
    """Runs a command and captures all output. Supports strings and CWD."""
    import subprocess
    import sys

    # Ensure command is a string for shell=True on Windows
    if isinstance(cmd, (list, tuple)):
        import shlex
        cmd = ' '.join(shlex.quote(x) for x in cmd)

    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        # Use Popen + communicate to prevent buffer deadlocks
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True, # Required for string commands on Windows
            cwd=cwd,    # Required so FFmpeg finds mylist.txt and .ts files
            startupinfo=startupinfo,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )

        stdout, _ = process.communicate()
        
        # Log output for debugging
        if stdout:
            for line in stdout.splitlines():
                log(f"[FFmpeg] {line}", log_level=1)

        error = process.returncode != 0
        return error, stdout

    except Exception as e:
        return True, f"Exception running command: {e}"


def print_object(obj):
    if obj is None:
        print(obj, 'is None')
        return
    for k, v in vars(obj).items():
        try:
            print(k, '=', v)
        except:
            pass


def update_object(obj, new_values):
    """
    Updates an object's attributes from a supplied dictionary.
    
    This method verifies that an attribute exists on the object before attempting 
    to set it, preventing the accidental creation of new, non-standard attributes.
    """
    for k, v in new_values.items():
        if hasattr(obj, k):
            try:
                setattr(obj, k, v)
            except AttributeError:
                # Occurs if the property is read-only (e.g., @property without a setter)
                log(f"update_object(): Cannot update read-only property: {k}", log_level=3)
            except Exception as e:
                log(f'update_object(): Error updating {k}: {e}', log_level=3)
    return obj

def truncate(string, length):
    """
    Shortens a string to a specified length by inserting an ellipsis (...) 
    in the center, preserving the beginning and end of the text.
    """
    sep = '...'
    if length < len(sep) + 2:
        # If the target length is too short for an ellipsis, perform a simple cut
        string = string[:length]
    elif len(string) > length:
        # Calculate segments to preserve around the center ellipsis
        part = (length - len(sep)) // 2
        remainder = (length - len(sep)) % 2
        string = string[:part + remainder] + sep + string[-part:]
        
    return string

def sort_dictionary(dictionary, descending=True):
    """Sorts a dictionary by its keys and returns a new dictionary."""
    return {k: v for k, v in sorted(dictionary.items(), key=lambda item: item[0], reverse=descending)}


def popup(msg, title='', type_=''):
    """
    Signals the main UI thread to spawn a popup dialog.
    """
    param = dict(title=title, msg=msg, type_=type_)
    config.main_window_q.put(('popup', param))

def translate_server_code(code):
    """
    Maps numeric HTTP status codes to human-readable descriptions.
    """
    server_codes = {
        # 1xx: Informational
        100: ('continue',),
        101: ('switching_protocols',),
        102: ('processing',),
        103: ('checkpoint',),
        122: ('uri_too_long',),
        
        # 2xx: Success
        200: ('ok', '✓'),
        201: ('created',),
        202: ('accepted',),
        204: ('no_content',),
        206: ('partial_content',),
        
        # 3xx: Redirection
        300: ('multiple_choices',),
        301: ('moved_permanently',),
        302: ('found',),
        304: ('not_modified',),
        307: ('temporary_redirect',),
        308: ('permanent_redirect',),

        # 4xx: Client Errors
        400: ('bad_request',),
        401: ('unauthorized',),
        403: ('forbidden',),
        404: ('not_found',),
        405: ('method_not_allowed',),
        408: ('request_timeout',),
        413: ('payload_too_large',),
        416: ('range_not_satisfiable',),
        429: ('too_many_requests',),

        # 5xx: Server Errors
        500: ('internal_server_error', '✗'),
        501: ('not_implemented',),
        502: ('bad_gateway',),
        503: ('service_unavailable',),
        504: ('gateway_timeout',),
    }

    # Returns the primary description or a blank space if code is unknown
    return server_codes.get(code, (' ',))[0]

def validate_url(url):
    """
    Performs a basic regex check to determine if a string is a valid HTTP/HTTPS URL.
    Note: Requires improvement for non-standard or naked 'www' formats.
    """
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    match = re.match(pattern, url)
    return True if match else False


def open_file(file):
    try:
        if config.operating_system == 'Windows':
            os.startfile(file)

        elif config.operating_system == 'Linux':
            run_command(f'xdg-open "{file}"', verbose=False)

        elif config.operating_system == 'Darwin':
            run_command(f'open "{file}"', verbose=False)
    except Exception as e:
        print('MainWindow.open_file(): ', e)


def clipboard_read():
    """Retrieves the current text content from the system clipboard."""
    return clipboard.paste()

def clipboard_write(value):
    """Copies the specified text value to the system clipboard."""
    clipboard.copy(value)

def compare_versions(x, y):
    """
    Compares two version strings and returns the higher version.
    
    Example: compare_versions('2020.10.6', '2020.3.7') returns '2020.10.6'.
    Returns None if both versions are identical or if parsing fails.
    
    The logic splits strings by '.' and compares the first three numeric components.
    """
    try:
        # Parse version strings into lists of integers (Major.Minor.Patch)
        a = [int(val) for val in x.split('.')[:3]]
        b = [int(val) for val in y.split('.')[:3]]

        # Iterative comparison of version segments
        for i in range(3):
            if a[i] > b[i]:
                return x
            elif a[i] < b[i]:
                return y
    except Exception:
        # Fallback if version strings do not follow the expected numeric format
        pass

    return None


def load_json(file=None):
    """
    Reads and parses a JSON file from the specified path.
    
    Returns the parsed data (typically a list or dictionary) on success, 
    or None if the file is missing, corrupted, or inaccessible.
    """
    ctx = "JSON-LOAD"
    try:
        with open(file, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        # Logs specific error details (e.g., FileNotFoundError or JSONDecodeError)
        log(f'error: {e}', log_level=3, context=ctx)
        return None


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that skips non-serializable objects like ResumeTracker."""
    def default(self, obj):
        # Skip ResumeTracker and other non-serializable objects
        if hasattr(obj, '__module__') and ('ResumeTracker' in str(type(obj)) or 
                                           'NativeWriter' in str(type(obj))):
            return None  # Skip these objects
        # For dicts, filter out non-serializable values
        if isinstance(obj, dict):
            return {k: v for k, v in obj.items() if not (hasattr(v, '__module__') and 
                    ('ResumeTracker' in str(type(v)) or 'NativeWriter' in str(type(v))))}
        try:
            return super().default(obj)
        except TypeError:
            return None  # Skip unserializable objects

def save_json(file=None, data=None):
    """
    Serializes data to a JSON file. 
    Uses a CustomJSONEncoder and a string fallback for non-serializable objects.
    """
    ctx = "JSON-SAVE"
    try:
        with open(file, 'w') as f:
            # Custom encoder handles specialized types; default=str handles remaining objects
            json.dump(data, f, cls=CustomJSONEncoder, default=str)
    except Exception as e:
        log(f'save_json error: {e}', log_level=3, context=ctx)

def natural_sort(my_list):
    """
    Sorts a list in 'natural' order (e.g., 'item2' comes before 'item10').
    Standard alphabetical sorting would place 'item10' before 'item2'.
    """
    # Helper to convert numeric strings to integers during comparison
    convert = lambda text: int(text) if text.isdigit() else text
    # Splits the string into chunks of text and numbers
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    
    return sorted(my_list, key=alphanum_key)


def log_recorder():
    """
    Continuously monitors the log queue and writes messages to log.txt on disk.
    This runs as a background process to ensure disk I/O doesn't block the UI.
    """
    ctx = "LOG-RECORDER"
    q = config.log_recorder_q
    buffer = ''
    file = os.path.join(config.sett_folder, 'log.txt')

    # Initialize/Clear the existing log file at startup based on LOG_MODE
    mode = "w" if getattr(config, "LOG_MODE", "append") == "overwrite" else "a"

    # Only clear file if overwrite mode
    if mode == "w":
        with open(file, mode, encoding="utf-8", errors="ignore") as f:
            f.write('')

    while True:
        time.sleep(0.1)  # Polling interval to prevent CPU spikes
        
        if config.terminate:
            break

        # Drain all currently pending messages from the queue into a local buffer
        for _ in range(q.qsize()):
            buffer += q.get()

        # Batch-write the buffer to disk to minimize file access overhead
        if buffer:
            try:
                mode = "a"  # always append after initialization
                with open(file, mode, encoding="utf-8", errors="ignore") as f:
                    f.write(buffer)
                    buffer = ''  # Reset buffer after successful write
            except Exception as e:
                # Use print here as a fallback if the logging system itself is failing
                print(f'log_recorder error: {e}')


def process_thumbnail(url):
    ctx = "THUMBNAIL"

    try:
        # Load background from base64
        bg_bytes = base64.b64decode(config.THUMBNAIL_BG_BASE64)
        bg = QPixmap()
        bg.loadFromData(bg_bytes)

        if bg.isNull():
            return None

        # Download thumbnail
        buffer = download(url)
        if not buffer:
            return None

        fg = QPixmap()
        fg.loadFromData(buffer.getvalue())

        if fg.isNull():
            return None

        # Resize foreground with aspect ratio
        fg = fg.scaled(
            bg.width() - 10,
            bg.height() - 10,
            aspectMode=1,   # Qt.KeepAspectRatio
            mode=1          # Qt.SmoothTransformation
        )

        # Draw onto background
        painter = QPainter(bg)

        x = (bg.width() - fg.width()) // 2
        y = (bg.height() - fg.height()) // 2

        painter.drawPixmap(x, y, fg)
        painter.end()

        # Export to base64 PNG
        ba = QByteArray()
        qbuffer = QBuffer(ba)
        qbuffer.open(QIODevice.WriteOnly)

        bg.save(qbuffer, "PNG")

        return base64.b64encode(bytes(ba))

    except Exception as e:
        log(f'error: {e}', log_level=3, context=ctx)


def get_machine_id_raw():
    """Return the raw OS-level machine identifier (platform-dependent)."""
    system = platform.system().lower()

    if system == "windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography"
            )
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return value
        except Exception:
            return None

    elif system == "linux":
        for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
            try:
                with open(path, "r") as f:
                    return f.read().strip()
            except FileNotFoundError:
                continue
        return None

    elif system == "darwin":  # macOS
        try:
            output = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                text=True
            )
            for line in output.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        except Exception:
            return None

    return None


def get_machine_id(hashed=True):
    """
    Return a stable, cross-platform machine ID.
    By default, the raw ID is SHA-256 hashed.
    """
    raw_id = get_machine_id_raw()
    if not raw_id:
        return None
    if hashed:
        return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
    return raw_id




def _normalize_version_str(s: str | None) -> str | None:
    if not s:
        return None
    # strip common prefixes/wrappers like v, [ ], spaces
    s = s.strip().lstrip('v').lstrip('.').strip('[](){} ').strip()
    return s or None

def _parse_version(s: str | None):
    s = _normalize_version_str(s)
    if not s:
        return None
    if Version:
        try:
            return Version(s)
        except InvalidVersion:
            pass
    # fallback: parse numbers only (1.2.3 → (1,2,3))
    nums = re.findall(r'\d+', s)
    if not nums:
        return None
    return tuple(int(n) for n in nums)

def compare_versions_2(a: str | None, b: str | None) -> int | None:
    """
    Returns 1 if a>b, 0 if a==b, -1 if a<b, None if either unparsable.
    """
    va, vb = _parse_version(a), _parse_version(b)
    if va is None or vb is None:
        return None
    if Version and isinstance(va, Version) and isinstance(vb, Version):
        return (va > vb) - (va < vb)
    # tuple fallback: pad to same length
    la, lb = list(va), list(vb)
    L = max(len(la), len(lb))
    la += [0]*(L-len(la))
    lb += [0]*(L-len(lb))
    return (la > lb) - (la < lb)




__all__ = [
    'notify', 'handle_exceptions', 'get_headers', 'download', 'size_format', 'time_format', 'log',
    'validate_file_name', 'size_splitter', 'delete_folder', 'get_seg_size',
    'run_command', 'print_object', 'update_object', 'truncate', 'sort_dictionary', 'popup', 'compare_versions',
    'translate_server_code', 'validate_url', 'open_file', 'clipboard_read', 'clipboard_write', 'delete_file',
    'rename_file', 'load_json', 'save_json', 'echo_stdout', 'echo_stderr', 'log_recorder', 'natural_sort',
    'process_thumbnail', 'compare_version_2'

]
