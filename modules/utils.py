
import base64
import os
import sys
import io
import pycurl
import time

import plyer
import certifi
import shutil
import zipfile
import subprocess
import py_compile
import shlex
import re
import uuid
import json
import pyperclip as clipboard
from getmac import get_mac_address
import psutil
try:
    from PIL import Image
except:
    print('pillow module is missing try to install it to display video thumbnails')

from . import config



def notify(msg, title='', timeout=5):
    # show os notification at tray icon area
    # title=f'{APP_NAME}'
    try:
        plyer.notification.notify(title=title, message=msg, app_name=config.APP_TITLE)
    except Exception as e:
        handle_exceptions(f'plyer notification: {e}')


def handle_exceptions(error):
    if config.TEST_MODE:
        raise error
    else:
        log(error)


def set_curl_options(c):
    """take pycurl object as an argument and set basic options"""
    c.setopt(pycurl.USERAGENT, config.USER_AGENT)

    # set proxy, must be string empty '' means no proxy
    c.setopt(pycurl.PROXY, config.proxy)

    # re-directions
    c.setopt(pycurl.FOLLOWLOCATION, 1)
    c.setopt(pycurl.MAXREDIRS, 10)

    c.setopt(pycurl.NOSIGNAL, 1)  # option required for multithreading safety
    c.setopt(pycurl.NOPROGRESS, 1)
    c.setopt(pycurl.CAINFO, certifi.where())  # for https sites and ssl cert handling

    # time out
    c.setopt(pycurl.CONNECTTIMEOUT, 30)  # limits the connection phase, it has no impact once it has connected.

    # abort if download speed slower than 1 byte/sec during 60 seconds
    c.setopt(pycurl.LOW_SPEED_LIMIT, 1)
    c.setopt(pycurl.LOW_SPEED_TIME, 60)

    # verbose
    if config.log_level >= 3:
        c.setopt(pycurl.VERBOSE, 1)
    else:
        c.setopt(pycurl.VERBOSE, 0)

    # it tells curl not to include headers with the body
    c.setopt(pycurl.HEADEROPT, 0)

    c.setopt(pycurl.PROXY, config.proxy)  # set proxy, must be string empty '' means no proxy

    c.setopt(pycurl.TIMEOUT, 300)
    c.setopt(pycurl.AUTOREFERER, 1)


def get_headers(url, verbose=False):
    """return dictionary of headers"""

    # log('get_headers()> getting headers for:', url)

    curl_headers = {}

    def header_callback(header_line):
        # quit if main window terminated
        if config.terminate:
            return

        header_line = header_line.decode('iso-8859-1')
        header_line = header_line.lower()

        if ':' not in header_line:
            return

        name, value = header_line.split(':', 1)
        name = name.strip()
        value = value.strip()
        curl_headers[name] = value
        if verbose:
            print(name, ':', value)

    def write_callback(data):
        return -1  # send terminate flag

    def debug_callback(handle, type, data, size=0, userdata=''):
        """it takes output from curl verbose and pass it to my log function"""
        try:
            log(data.decode("utf-8"))
        except:
            pass
        return 0

    # region curl options
    c = pycurl.Curl()

    # set general curl options
    set_curl_options(c)

    # set special curl options
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.WRITEFUNCTION, write_callback)
    c.setopt(pycurl.HEADERFUNCTION, header_callback)
    # endregion

    try:
        c.perform()
    except Exception as e:
        if 'Failed writing body' not in str(e):
            log('get_headers()>', e)

    # add status code and effective url to headers
    curl_headers['status_code'] = c.getinfo(pycurl.RESPONSE_CODE)
    curl_headers['eff_url'] = c.getinfo(pycurl.EFFECTIVE_URL)

    # return headers
    return curl_headers


def download(url, file_name=None):
    """simple file download, return False if failed,
    :param url: text url link
    :param file_name: if specified it will save file to disk, otherwise it will buffer to memory
    it will return True / buffer or False"""

    if not url:
        log('download()> url not valid:', url)
        return None

    log('download()> downloading', url, '\n')

    def set_options():
        # set general curl options
        set_curl_options(c)

        # set special curl options
        c.setopt(pycurl.URL, url)

    file = None
    buffer = None

    # pycurl
    c = pycurl.Curl()
    set_options()

    if file_name:
        file = open(file_name, 'wb')
        c.setopt(c.WRITEDATA, file)
    else:
        buffer = io.BytesIO()
        c.setopt(c.WRITEDATA, buffer)

    try:
        c.perform()

    except Exception as e:
        log('download():', e)
        return False
    finally:
        c.close()
        if file:
            file.close()

    log('download(): done downloading')

    return buffer


def size_format(size, tail=''):
    # 1 kb = 1024 byte, 1MB = 1024 KB, 1GB = 1024 MB
    # 1 MB = 1024 * 1024 = 1_048_576 bytes
    # 1 GB = 1024 * 1024 * 1024 = 1_073_741_824 bytes

    try:
        if size == 0: return '...'
        """take size in num of byte and return representation string"""
        if size < 1024:  # less than KB
            s = f'{round(size)} bytes'

        elif 1_048_576 > size >= 1024:  # more than or equal 1 KB and less than MB
            s = f'{round(size / 1024)} KB'
        elif 1_073_741_824 > size >= 1_048_576:  # MB
            s = f'{round(size / 1_048_576, 1)} MB'
        else:  # GB
            s = f'{round(size / 1_073_741_824, 2)} GB'
        return f'{s}{tail}'
    except:
        return size


def time_format(t, tail=''):
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
    except:
        return t


def log(*args, log_level=1):
    if log_level > config.log_level:
        return

    text = ''
    for arg in args:
        text += str(arg)
        text += ' '
    text = text[:-1]  # remove last space
    text = '>> ' + text

    try:
        print(text)
        config.log_entry = text
        config.log_recorder_q.put(text + '\n')
        config.main_window_q.put(('log', text + '\n'))
    except Exception as e:
        print(e)


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


def validate_file_name(f_name):
    # filter for tkinter safe character range
    f_name = ''.join([c for c in f_name if ord(c) in range(65536)])
    safe_string = str()
    char_count = 0
    for c in str(f_name):
        if c in ['\\', '/', ':', '?', '<', '>', '"', '|', '*']:
            safe_string += '_'
        else:
            safe_string += c

        if char_count > 100:
            break
        else:
            char_count += 1
    return safe_string


def size_splitter(size, part_size):
    """Receive file size and return a list of size ranges"""
    result = []

    if size == 0:
        result.append('0-0')
        return result

    # decide num of parts
    span = part_size if part_size <= size else size
    # print(f'span={span}, part size = {part_size}')
    parts = max(size // span, 1)  # will be one part if size < span

    x = 0
    size = size - 1  # when we start counting from zero the last byte number should be size - 1
    for i in range(parts):
        y = x + span - 1
        if size - y < span:  # last remaining bytes
            y = size
        result.append(f'{x}-{y}')
        x = y + 1

    return result


def delete_folder(folder, verbose=False):
    try:
        shutil.rmtree(folder)
        if verbose:
            log('done deleting folder:', folder)
        return True
    except Exception as e:
        if verbose:
            log('delete_folder()> ', e)
        return False


def delete_file(file, verbose=False):
    try:
        os.unlink(file)
        if verbose:
            log('done deleting file:', file)
        return True
    except Exception as e:
        if verbose:
            log('delete_file()> ', e)
        return False


def rename_file(oldname=None, newname=None):
    if oldname == newname:
        return True

    try:
        os.rename(oldname, newname)
        log('done renaming file:', oldname, '... to:', newname)
        return True
    except Exception as e:
        log('rename_file()> ', e)
        return False


def get_seg_size(seg):
    # calculate segment size from segment name i.e. 200-1000  gives 801 byte
    try:
        a, b = int(seg.split('-')[0]), int(seg.split('-')[1])
        size = b - a + 1 if b > 0 else 0
        return size
    except:
        return 0


def run_command(cmd, verbose=True, shell=False, hide_window=False, d=None):
    """run command in as a subprocess
    :param d, DownloadItem reference, if exist will monitor user cancel action for terminating process
    """

    if verbose:
        log('running command:', cmd)

    error, output = True, f'error running command {cmd}'

    try:

        # split command if shell parameter set to False
        if not shell:
            cmd = shlex.split(cmd)

        # startupinfo to hide terminal window on windows
        if hide_window and config.operating_system == 'Windows':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        else:
            startupinfo = None

        # start subprocess using Popen instead of subprocess.run() to get a real-time output
        # since run() gets the output only when finished
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8',
                                   errors='replace', shell=shell, startupinfo=startupinfo)

        output = ''

        for line in process.stdout:
            line = line.strip()
            output += line
            if verbose:
                log(line)

            # monitor kill switch
            if d and d.status == config.Status.cancelled:
                log('terminate run_command()>', cmd)
                process.kill()
                return 1, 'Cancelled by user'

        # wait for subprocess to finish, process.wait() is not recommended
        process.communicate()

        # get return code
        process.poll()
        error = process.returncode != 0  # True or False

    except Exception as e:
        log('error running command: ', e, ' - cmd:', cmd)

    return error, output


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
    """update an object attributes from a supplied dictionary"""
    # avoiding obj.__dict__.update(new_values) as it will set a new attribute if it doesn't exist

    for k, v in new_values.items():
        if hasattr(obj, k):
            try:
                setattr(obj, k, v)
            except AttributeError:  # in case of read only attribute
                log(f"update_object(): can't update property: {k}, with value: {v}")
            except Exception as e:
                log(f'update_object(): error, {e}, property: {k}, value: {v}')
    return obj


def truncate(string, length):
    """truncate a string to specified length by adding ... in the middle of the string"""
    # print(len(string), string)
    sep = '...'
    if length < len(sep) + 2:
        string = string[:length]
    elif len(string) > length:
        part = (length - len(sep)) // 2
        remainder = (length - len(sep)) % 2
        string = string[:part + remainder] + sep + string[-part:]
    # print(len(string), string)
    return string


def sort_dictionary(dictionary, descending=True):
    return {k: v for k, v in sorted(dictionary.items(), key=lambda item: item[0], reverse=descending)}


def popup(msg, title='', type_=''):
    """Send message to main window to spawn a popup"""
    param = dict(title=title, msg=msg, type_=type_)
    config.main_window_q.put(('popup', param))


def translate_server_code(code):
    """Lookup server code and return a readable code description"""
    server_codes = {

        # Informational.
        100: ('continue',),
        101: ('switching_protocols',),
        102: ('processing',),
        103: ('checkpoint',),
        122: ('uri_too_long', 'request_uri_too_long'),
        200: ('ok', 'okay', 'all_ok', 'all_okay', 'all_good', '\\o/', '✓'),
        201: ('created',),
        202: ('accepted',),
        203: ('non_authoritative_info', 'non_authoritative_information'),
        204: ('no_content',),
        205: ('reset_content', 'reset'),
        206: ('partial_content', 'partial'),
        207: ('multi_status', 'multiple_status', 'multi_stati', 'multiple_stati'),
        208: ('already_reported',),
        226: ('im_used',),

        # Redirection.
        300: ('multiple_choices',),
        301: ('moved_permanently', 'moved', '\\o-'),
        302: ('found',),
        303: ('see_other', 'other'),
        304: ('not_modified',),
        305: ('use_proxy',),
        306: ('switch_proxy',),
        307: ('temporary_redirect', 'temporary_moved', 'temporary'),
        308: ('permanent_redirect',),

        # Client Error.
        400: ('bad_request', 'bad'),
        401: ('unauthorized',),
        402: ('payment_required', 'payment'),
        403: ('forbidden',),
        404: ('not_found', '-o-'),
        405: ('method_not_allowed', 'not_allowed'),
        406: ('not_acceptable',),
        407: ('proxy_authentication_required', 'proxy_auth', 'proxy_authentication'),
        408: ('request_timeout', 'timeout'),
        409: ('conflict',),
        410: ('gone',),
        411: ('length_required',),
        412: ('precondition_failed', 'precondition'),
        413: ('request_entity_too_large',),
        414: ('request_uri_too_large',),
        415: ('unsupported_media_type', 'unsupported_media', 'media_type'),
        416: ('requested_range_not_satisfiable', 'requested_range', 'range_not_satisfiable'),
        417: ('expectation_failed',),
        418: ('im_a_teapot', 'teapot', 'i_am_a_teapot'),
        421: ('misdirected_request',),
        422: ('unprocessable_entity', 'unprocessable'),
        423: ('locked',),
        424: ('failed_dependency', 'dependency'),
        425: ('unordered_collection', 'unordered'),
        426: ('upgrade_required', 'upgrade'),
        428: ('precondition_required', 'precondition'),
        429: ('too_many_requests', 'too_many'),
        431: ('header_fields_too_large', 'fields_too_large'),
        444: ('no_response', 'none'),
        449: ('retry_with', 'retry'),
        450: ('blocked_by_windows_parental_controls', 'parental_controls'),
        451: ('unavailable_for_legal_reasons', 'legal_reasons'),
        499: ('client_closed_request',),

        # Server Error.
        500: ('internal_server_error', 'server_error', '/o\\', '✗'),
        501: ('not_implemented',),
        502: ('bad_gateway',),
        503: ('service_unavailable', 'unavailable'),
        504: ('gateway_timeout',),
        505: ('http_version_not_supported', 'http_version'),
        506: ('variant_also_negotiates',),
        507: ('insufficient_storage',),
        509: ('bandwidth_limit_exceeded', 'bandwidth'),
        510: ('not_extended',),
        511: ('network_authentication_required', 'network_auth', 'network_authentication'),
    }

    return server_codes.get(code, ' ')[0]


def validate_url(url):
    # below pattern is not tested as a starter it doesn't recognize www. urls
    # improvement required
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    match = re.match(pattern, url)
    if match:
        return True
    else:
        return False


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
    return clipboard.paste()


def clipboard_write(value):
    clipboard.copy(value)


def compare_versions(x, y):
    """it will compare 2 version numbers and return the higher value
    example compare_versions('2020.10.6', '2020.3.7') will return '2020.10.6'
    return None if 2 versions are equal
    """
    try:
        a = [int(x) for x in x.split('.')[:3]]
        b = [int(x) for x in y.split('.')[:3]]

        for i in range(3):
            if a[i] > b[i]:
                return x
            elif a[i] < b[i]:
                return y
    except:
        pass

    return None

# VERSION_MAPPING = {
#     "2025.1.25": "1.0.1",  # Map date-based versions to semantic versions
#     #"2025.1.30": "1.0.2",
# }

# def compare_versions(version1, version2):
#     """
#     Compare two versions (date or semantic).
#     Supports mapping date-based versions to semantic equivalents.
#     Returns the higher version or None if versions are equal.
#     """
#     def map_version(version):
#         # Map date-based versions to semantic versions if present
#         return VERSION_MAPPING.get(version, version)

#     try:
#         # Map versions to their semantic equivalents
#         v1_mapped = map_version(version1)
#         v2_mapped = map_version(version2)

#         # Split versions into parts
#         v1_parts = [int(part) for part in v1_mapped.split('.')]
#         v2_parts = [int(part) for part in v2_mapped.split('.')]

#         # Compare each part
#         for v1, v2 in zip(v1_parts, v2_parts):
#             if v1 > v2:
#                 return version1
#             elif v1 < v2:
#                 return version2

#         # Compare lengths if versions have different lengths
#         if len(v1_parts) > len(v2_parts):
#             return version1
#         elif len(v1_parts) < len(v2_parts):
#             return version2

#         # Versions are equal
#         return None
#     except ValueError:
#         raise ValueError("Invalid version format. Ensure valid numeric components or mapping.")



def load_json(file=None):
    try:
        with open(file, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        log('load_json() > error: ', e)
        return None


def save_json(file=None, data=None):
    try:
        with open(file, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        log('save_json() > error: ', e)


def log_recorder():
    """write log to disk in real-time"""
    q = config.log_recorder_q
    buffer = ''
    file = os.path.join(config.sett_folder, 'log.txt')

    # clear previous file
    with open(file, 'w') as f:
        f.write(buffer)

    while True:
        time.sleep(0.1)
        if config.terminate:
            break

        # read log messages from queue
        for _ in range(q.qsize()):
            buffer += q.get()

        # write buffer to file
        if buffer:
            try:
                with open(file, 'a', encoding="utf-8", errors="ignore") as f:
                    f.write(buffer)
                    buffer = ''  # reset buffer
            except Exception as e:
                print('log_recorder()> error:', e)


def natural_sort(my_list):
    """ Sort the given list in the way that humans expect.
    source: https://blog.codinghorror.com/sorting-for-humans-natural-sort-order/	"""
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(my_list, key=alphanum_key)


def process_thumbnail(url):
    """take url of thumbnail and return thumbnail overlayed ontop of baseplate"""

    # check if pillow module installed and working
    try:
        # dummy operation will kick in error if module not PIL found
        _ = Image.Image()
    except:
        log('pillow module is missing try to install it to display video thumbnails')
        return None

    try:
        # load background image
        bg = io.BytesIO(base64.b64decode())
        bg = Image.open(bg)

        # downloading thumbnail
        buffer = download(url)  # get BytesIO object
        if not buffer:
            return None

        # read thumbnail image and call it fg "foreground"
        fg = Image.open(buffer)

        # create thumbnail less 10 pixels from background size
        fg.thumbnail((bg.size[0]-10, bg.size[1] - 10))

        # calculate centers
        fg_center_x, fg_center_y = fg.size[0] // 2, fg.size[1] // 2
        bg_center_x, bg_center_y = bg.size[0] // 2, bg.size[1] // 2

        # calculate the box coordinates where we should paset our thumbnail
        x = bg_center_x - fg_center_x
        y = bg_center_y - fg_center_y
        box = (x, y, x + fg.size[0], y + fg.size[1])

        # paste foreground "thumbnail" on top of base plate "background"
        bg.paste(fg, box)
        # bg.show()

        # encode final thumbnail into base64 string
        buffered = io.BytesIO()
        bg.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue())

        return img_str
    except Exception as e:
        log('process_thumbnail()> error', e)
        return None
    
def get_available_interfaces():
    """Detect all available network interfaces on the system."""
    interfaces = []
    
    # Get interfaces using psutil (works across OSes)
    for interface, addrs in psutil.net_if_addrs().items():
        interfaces.append(interface)
    
    return interfaces

def get_mac_by_interface(interface):
    """Get the MAC address for a specified interface using the getmac library."""
    try:
        mac = get_mac_address(interface=interface)
        if mac:
            return mac
        else:
            return None
    except Exception as e:
        return None

def get_mac_id():
    """Get a hashed machine ID based on the MAC address of a specified interface."""
    interfaces = get_available_interfaces()
    
    if 'wlo1' in interfaces:
        interface = 'wlo1'  # Wi-Fi interface on Linux
    elif 'enp0s25' in interfaces:
        interface = 'enp0s25'  # Ethernet interface on Linux
    elif 'Ethernet' in interfaces:
        interface = 'Ethernet'  # Ethernet on Windows
    elif 'Wi-Fi' in interfaces:
        interface = 'Wi-Fi'  # Wi-Fi on Windows
    elif 'en0' in interfaces:
        interface = 'en0'  # Ethernet or Wi-Fi on macOS
    elif 'en1' in interfaces:
        interface = 'en1'  # Secondary network interface on macOS
    else:
        return None

    mac = get_mac_by_interface(interface)
    if mac:
        return mac
        
    else:
        return None
    

def get_machine_id(self):
    """Get a hashed machine ID based on the MAC address of a specified interface."""
    mac_address = get_mac_id()
    machine_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, mac_address))  # Stable machine ID based on MAC

    
    return machine_id


__all__ = [
    'notify', 'handle_exceptions', 'get_headers', 'download', 'size_format', 'time_format', 'log',
    'validate_file_name', 'size_splitter', 'delete_folder', 'get_seg_size',
    'run_command', 'print_object', 'update_object', 'truncate', 'sort_dictionary', 'popup', 'compare_versions',
    'translate_server_code', 'validate_url', 'open_file', 'clipboard_read', 'clipboard_write', 'delete_file',
    'rename_file', 'load_json', 'save_json', 'echo_stdout', 'echo_stderr', 'log_recorder', 'natural_sort',
    'process_thumbnail'

]
