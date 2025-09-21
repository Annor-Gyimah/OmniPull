"""
    pyIDM

    multi-connections internet download manager, based on "pyCuRL/curl", "youtube_dl", and "PySimpleGUI"

    :copyright: (c) 2019-2020 by Mahmoud Elshahat.
    :license: GNU LGPLv3, see LICENSE for more details.
"""

# check and update application
# import io
import os
import sys
import time
import math
import uuid
import wget
import httpx
import shutil
import socket
import zipfile
import tempfile
import requests
import subprocess
import py_compile




from tqdm import tqdm
from pathlib import Path
from modules import video
from modules import config
from datetime import datetime, timedelta
from modules.utils import log, download, run_command, delete_folder, popup



def check_for_update():
    """download version.py from github, extract latest version number return app latest version"
    """

    # do not use, will use get_changelog() instead

    source_code_url = 'https://github.com/pyIDM/pyIDM/blob/master/pyidm/version.py'
    new_release_url = 'https://github.com/pyIDM/pyIDM/releases/download/extra/version.py'
    url = new_release_url if config.FROZEN else source_code_url

    # get BytesIO object
    buffer = download(url)

    if buffer:
        # convert to string
        contents = buffer.getvalue().decode()

        # extract version number from contents
        latest_version = contents.rsplit(maxsplit=1)[-1].replace("'", '')

        return latest_version

    else:
        log("check_for_update() --> couldn't check for update, url is unreachable")
        return None


def get_changelog():
    """download ChangeLog.txt from github, extract latest version number, return a tuple of (latest_version, contents)
    """

    # Get latest release info from GitHub API
    content = httpx.get(url="https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest", headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64"},
                        follow_redirects=True).json()

    # Extract tagName and remove any unwanted characters like leading dots
    tagName = content["tag_name"].lstrip('v').lstrip('.').rstrip('[').lstrip(']')  # Remove 'v' or any leading dots
    

    
    # currentVersion = list(map(int, config.APP_VERSION.split(".")))
    
    source_code_url = 'https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/macOS/ChangeLog.txt'
    new_release_url = 'https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/macOS/ChangeLog.txt'

    url = new_release_url if config.FROZEN else source_code_url


    # get BytesIO object
    buffer = download(url)

    if buffer:
        # convert to string
        contents = buffer.getvalue().decode()

        # extract version number from contents
        #latest_version = contents.splitlines()[0].replace(':', '').strip()
        latest_version = tagName

        config.APP_LATEST_VERSION = latest_version
       

        return latest_version, contents
    else:
        log("check_for_update() --> couldn't check for update, url is unreachable")
        return None

def download_dmg_httpx(url, dest_path):
    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)




def format_progress_bar(percentage, bar_length=20):
    filled_length = int(bar_length * percentage // 100)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    return f"{percentage:3.0f}%|{bar}"

def sizeof_fmt(num, suffix="B"):
    # Human-readable file size
    for unit in ['','K','M','G','T']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}P{suffix}"

def download_dmg_httpx_resume(url, dest_path):
    headers = {}
    file_mode = "wb"

    if dest_path.exists():
        existing_size = dest_path.stat().st_size
        headers["Range"] = f"bytes={existing_size}-"
        file_mode = "ab"
        log(f"Resuming download from byte {existing_size}")
    else:
        existing_size = 0
        log("Starting new download")

    try:
        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60.0) as r:
            if r.status_code in (200, 206):
                total_size = int(r.headers.get("Content-Range", "").split("/")[-1]) if "Content-Range" in r.headers else int(r.headers.get("Content-Length", 0))
                total_size += existing_size
                bytes_downloaded = existing_size

                start_time = time.time()
                last_log_percent = -1

                with open(dest_path, file_mode) as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
                        bytes_downloaded += len(chunk)

                        percent = (bytes_downloaded / total_size) * 100
                        now = time.time()
                        elapsed = now - start_time
                        speed = bytes_downloaded / elapsed if elapsed > 0 else 0
                        eta = (total_size - bytes_downloaded) / speed if speed > 0 else 0

                        # Only log every 5% or on last chunk
                        current_percent = int(percent // 5) * 5
                        if current_percent != last_log_percent or bytes_downloaded == total_size:
                            bar = format_progress_bar(percent)
                            log(f"Downloading update:  {bar} | {sizeof_fmt(bytes_downloaded)}/{sizeof_fmt(total_size)} "
                                f"[{elapsed:05.0f}s<{eta:02.0f}s, {sizeof_fmt(speed)}/s]")
                            last_log_percent = current_percent
            else:
                raise Exception(f"Unexpected status code: {r.status_code}")
    except Exception as e:
        raise RuntimeError(f"Failed to download {url}: {e}")

def is_dmg_fully_downloaded(url, dest_path):
    try:
        r = httpx.head(url, follow_redirects=True, timeout=15.0)
        total_size = int(r.headers.get("Content-Length", 0))
        return dest_path.exists() and dest_path.stat().st_size >= total_size
    except Exception:
        return False


def update():
    # Only run on macOS
   

    # Get the latest release from GitHub API
    content = httpx.get(
        url="https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest", 
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        },
        follow_redirects=True
    ).json()

    tagName = content["tag_name"].lstrip('.')  # Remove any leading dots
    dmg_url = f"https://github.com/Annor-Gyimah/OmniPull/releases/download/{tagName}/omnipull-intel-{tagName}.dmg"  # Assuming the DMG file is named as such

    # Create a temporary directory to store the downloaded .dmg file
    # temp_dir = tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~"))
    # dmg_path = os.path.join(temp_dir, f"Li-Dl-{tagName}.dmg")
    hidden_temp_dir = Path.home() / "Downloads" / ".omnipull_update_tmp"
    hidden_temp_dir.mkdir(parents=True, exist_ok=True)

    hidden_dmg_path = hidden_temp_dir / f"omnipull-intel-{tagName}.dmg"
    final_dmg_path = Path.home() / "Downloads" / f"omnipull-intel-{tagName}.dmg"

    dmg_path = Path.home() / 'Downloads' / f"omnipull-intel-{tagName}.dmg"  # Save to Downloads folder

    if is_dmg_fully_downloaded(dmg_url, final_dmg_path):
        popup(
            title="Update Info",
            msg=f"OmniPull {tagName} is already downloaded in your Downloads folder.\n"
                f"Please close the app, uninstall the current version, and install the update.",
            type_="info"
        )
        return


    try:
        # Download the DMG file
        log(f"Downloading update ({tagName})...", log_level=1)
        popup(title="Update Info", msg="Downloading update, please wait... \n Do not close the app yet.", type_="info")
        download_dmg_httpx_resume(dmg_url, hidden_dmg_path)

        if not is_dmg_fully_downloaded(dmg_url, hidden_dmg_path):
            raise RuntimeError("Download incomplete or corrupted.")

        # Move from hidden temp to Downloads
        shutil.move(str(hidden_dmg_path), str(final_dmg_path))
        shutil.rmtree(hidden_temp_dir)  # Optional cleanup



        log(f"\nDownload completed.", log_level=1)


        # Show a popup to inform the user that download is complete
        popup(
            title="Update Info",
            msg=f"The new version {tagName} has been downloaded to your Downloads folder.\n\n"
                f"To update:\n"
                f"1. Close OmniPull.\n"
                f"2. Delete the current version from Applications.\n"
                f"3. Open the downloaded DMG and drag the new version to Applications.",
            type_="info"
        )
        # Ask user if they want to open Downloads
        response = subprocess.run([
            'osascript', '-e',
            'display dialog "Do you want to open the Downloads folder now?" '
            'buttons {"No", "Yes"} default button "Yes"'
        ], capture_output=True, text=True)

        if "Yes" in response.stdout:
            subprocess.run(["open", str(Path.home() / "Downloads")])



    except Exception as e:
        log(f"An error occurred during update: {e}", log_level=3)
        popup(title="Update Error", msg=f"An error occurred: {str(e)}. Please try again later.", type_="critical")



            
def check_for_ytdl_update():
    """it will download "version.py" file from github to check for a new version, return ytdl_latest_version
    """

    url = 'https://github.com/ytdl-org/youtube-dl/raw/master/youtube_dl/version.py'

    # get BytesIO object
    buffer = download(url)

    if buffer:
        # convert to string
        contents = buffer.getvalue().decode()

        # extract version number from contents
        latest_version = contents.rsplit(maxsplit=1)[-1].replace("'", '')

        return latest_version

    else:
        log("check_for_update() --> couldn't check for update, url is unreachable")
        return None


def update_youtube_dl():
    """This block for updating youtube-dl module in the freezed application folder in windows"""
    # check if the application runs from a windows cx_freeze executable "folder contains lib sub folder"
    # if run from source code, we will update system installed package and exit
    current_directory = config.current_directory
    if 'lib' not in os.listdir(current_directory):
        # log('running command: python -m pip install youtube_dl --upgrade')
        cmd = f'"{sys.executable}" -m pip install youtube_dl --upgrade'
        success, output = run_command(cmd)
        if success:
            log('successfully updated youtube_dl')
        return

    if not config.FROZEN:
        return

    # make temp folder
    log('making temp folder in:', current_directory)
    if 'temp' not in os.listdir(current_directory):
        os.mkdir(os.path.join(current_directory, 'temp'))

    # paths
    old_module = os.path.join(current_directory, 'lib/youtube_dl')
    new_module = os.path.join(current_directory, 'temp/youtube-dl-master/youtube_dl')

    def compile_file(file):
        if file.endswith('.py'):
            log('compiling file:', file)
            py_compile.compile(file, cfile=file + 'c')

            os.remove(file)
        else:
            print(file, 'not .py file')

    def compile_all():
        for item in os.listdir(new_module):
            item = os.path.join(new_module, item)

            if os.path.isfile(item):
                file = item
                compile_file(file)
            else:
                folder = item
                for file in os.listdir(folder):
                    file = os.path.join(folder, file)
                    compile_file(file)
        log('new youtube-dl module compiled to .pyc files')

    def overwrite_module():
        delete_folder(old_module)
        shutil.move(new_module, old_module)
        log('new module copied to:', new_module)

    # download from github
    log('start downloading youtube-dl module from github')
    url = 'https://github.com/ytdl-org/youtube-dl/archive/master.zip'
    response = download(url, 'temp/youtube-dl.zip')
    if response is False:
        log('failed to download youtube-dl, abort update')
        return

    # extract zip file
    with zipfile.ZipFile('temp/youtube-dl.zip', 'r') as zip_ref:
        zip_ref.extractall(path=os.path.join(current_directory, 'temp'))

    log('youtube-dl.zip extracted to: ', current_directory + '/temp')

    # compile files from py to pyc
    log('compiling files, please wait')
    compile_all()

    # delete old youtube-dl module and replace it with new one
    log('overwrite old youtube-dl module')
    overwrite_module()

    # clean old files
    delete_folder('temp')
    log('delete temp folder')
    log('youtube_dl module ..... done updating')


