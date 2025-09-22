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


# check and update application
# import io

import os
import sys
import wget
import time
import httpx
import shutil
import zipfile
import tempfile
import subprocess
import py_compile
from modules import config
from datetime import datetime, timedelta
from modules.utils import log, download, run_command, delete_folder, popup


def get_changelog():
    """download ChangeLog.txt from github, extract latest version number, return a tuple of (latest_version, contents)
    """
    try:
        # Get latest release info from GitHub API
        content = httpx.get(url="https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64"},
            follow_redirects=True).json()

        # Extract tagName and remove any unwanted characters like leading dots
        tagName = content["tag_name"].lstrip('v').lstrip('.').rstrip('[').lstrip(']')  # Remove 'v' or any leading dots
        

        # url will be chosen depend on frozen state of the application
        source_code_url = 'https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Windows/ChangeLog.txt'
        new_release_url = 'https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Windows/ChangeLog.txt'
        url = new_release_url if config.FROZEN else source_code_url
        # url = new_release_url


        # get BytesIO object
        buffer = download(url)

        if buffer:
            # convert to string
            contents = buffer.getvalue().decode()

            # extract version number from contents
            # latest_version = contents.splitlines()[0].replace(':', '').strip()
            latest_version = tagName

            return latest_version, contents
        else:
            log(f"check_for_update() --> couldn't check for update, url is unreachable", log_level=1)
            return None
    except httpx.RequestError as e:
        log(f"An error occurred while fetching the changelog: {e}", log_level=3)
        return None, None
    





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

def download_main_zip_httpx_resume(url, dest_path):
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

def is_main_zip_fully_downloaded(url, dest_path):
    try:
        r = httpx.head(url, follow_redirects=True, timeout=15.0)
        total_size = int(r.headers.get("Content-Length", 0))
        return dest_path.exists() and dest_path.stat().st_size >= total_size
    except Exception:
        return False


def update():
    # Get the latest release from GitHub API
    content = httpx.get(
        url="https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest", 
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64"
        },
        follow_redirects=True
    ).json()

    tagName = content["tag_name"].lstrip('.')  # Remove any leading dots

    # url = config.LATEST_RELEASE_URL if config.FROZEN else config.APP_URL
    update_script_url = "https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Windows/update.bat"  # URL for update.sh
    cleanup_script_url = "https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Windows/cleanup.bat"
    main_zip_url = f"https://github.com/Annor-Gyimah/OmniPull/releases/download/{tagName}/main.zip"


    
    # Create a hidden temporary directory in the user's home directory
    temp_dir = tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~"))
    download_path = os.path.join(temp_dir, "main.zip")
    update_script_path = os.path.join(temp_dir, "update.bat")
    dir = os.path.expanduser("~")
    cleanup_script_path = os.path.join(dir, "cleanup.bat")

    current_time = datetime.now()
    #run_time = current_time + timedelta(minutes=2)
    run_time2 = current_time + timedelta(minutes=5)

    try:
        # Download update files to the temporary directory
        log(f"Downloading update files...", log_level=1)
        popup(title="Update Info", msg="Downloading updates, please wait... \n Do not close the app yet.", type_="info")
        wget.download(update_script_url, update_script_path)
        download_main_zip_httpx_resume(main_zip_url, download_path)

        if not os.path.exists(cleanup_script_path): wget.download(cleanup_script_url, cleanup_script_path)

        log(f"\nDownload completed.", log_level=1)

        # Extract the downloaded tar.gz file in the temporary directory
        log(f"Extracting update package...", log_level=1)
        with zipfile.ZipFile(download_path, 'r') as zip_ref:  # extract zip file
            zip_ref.extractall(temp_dir)
        log(f"Extraction completed.", log_level=1)

        source_file = os.path.join(temp_dir, "main.exe")
        update_command = f'"{update_script_path}" "{source_file}"'
        cleanup_command = f'"{cleanup_script_path}" "{temp_dir}"'
        try:
            # Construct a command to create a scheduled task
            task_name = f"{config.APP_NAME}_Update"

            task_command = (
                
                f'schtasks /create /tn "{task_name}" /tr "{update_command}" /sc daily /st 12:00:00 /rl HIGHEST /f'

            )

        
            # Schedule the cleanup task
            task_name_cleanup = f"{config.APP_NAME}_Cleanup"
            task_command_cleanup = (
                f'schtasks /create /tn "{task_name_cleanup}" /tr "{cleanup_command}" /sc daily /st 12:05:00 /f'
            )
            
            # Run the command as administrator
            # popup(msg="Updates to be installed at 12:00:00 pm", title=config.APP_NAME, type_="info")
            subprocess.run(
                ["powershell", "-Command", f"Start-Process cmd -ArgumentList '/c {task_command}' -Verb RunAs"],
                shell=True,
                check=True
            )
            subprocess.run(
                ["powershell", "-Command", f"Start-Process cmd -ArgumentList '/c {task_command_cleanup}' -Verb RunAs"],
                shell=True,
                check=True
            )
            log(f"Update scheduled to run on the next reboot.", log_level=3)
            config.confirm_update = True
            # end_time = current_time + timedelta(seconds=5)
            # popup(msg=f"Ending the application in {end_time}", title=config.APP_NAME, type_="quit_app")

        except subprocess.CalledProcessError as e:
            log(f"Failed to schedule update: {e}", log_level=3)
            config.confirm_update = False
    except Exception as e:
        log(f"An error occurred during update: {e}", log_level=3)
        
        popup(
            msg="Windows Defender real-time protection is enabled. "
                "Please disable it temporarily and start the updating process again.",
            title=config.APP_NAME,
            type_="critical"
        )
   
   



def update():

    # Get the latest release from GitHub API
    content = httpx.get(
        url="https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest", 
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64"
        },
        follow_redirects=True
    ).json()

    tagName = content["tag_name"].lstrip('.')  # Remove any leading dots
    
     
    # url = config.LATEST_RELEASE_URL if config.FROZEN else config.APP_URL
    update_script_url = "https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Windows/update.bat"  # URL for update.sh
    cleanup_script_url = "https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Windows/cleanup.bat"
    main_zip_url = f"https://github.com/Annor-Gyimah/OmniPull/releases/download/{tagName}/main.zip"


    
    # Create a hidden temporary directory in the user's home directory
    temp_dir = tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~"))
    download_path = os.path.join(temp_dir, "main.zip")
    update_script_path = os.path.join(temp_dir, "update.bat")
    dir = os.path.expanduser("~")
    cleanup_script_path = os.path.join(dir, "cleanup.bat")

    current_time = datetime.now()
    #run_time = current_time + timedelta(minutes=2)
    run_time2 = current_time + timedelta(minutes=5)


    try:
        # Download update files to the temporary directory
        log(f"Downloading update files...", log_level=1)
        wget.download(update_script_url, update_script_path)
        wget.download(main_zip_url, download_path)
        if os.path.exists(cleanup_script_path):
            pass
        else:
            wget.download(cleanup_script_url, cleanup_script_path)
        log(f"\nDownload completed.", log_level=1)

        # Extract the downloaded tar.gz file in the temporary directory
        log(f"Extracting update package...", log_level=1)
        with zipfile.ZipFile(download_path, 'r') as zip_ref:  # extract zip file
            zip_ref.extractall(temp_dir)
        log(f"Extraction completed.", log_level=1)

        source_file = os.path.join(temp_dir, "main.exe")
        update_command = f'"{update_script_path}" "{source_file}"'
        cleanup_command = f'"{cleanup_script_path}" "{temp_dir}"'
        try:
            # Construct a command to create a scheduled task
            task_name = f"{config.APP_NAME}_Update"

            task_command = (
                
                f'schtasks /create /tn "{task_name}" /tr "{update_command}" /sc daily /st 12:00:00 /rl HIGHEST /f'

            )

        
            # Schedule the cleanup task
            task_name_cleanup = f"{config.APP_NAME}_Cleanup"
            task_command_cleanup = (
                f'schtasks /create /tn "{task_name_cleanup}" /tr "{cleanup_command}" /sc daily /st 12:05:00 /f'
            )
            
            # Run the command as administrator
            # popup(msg="Updates to be installed at 12:00:00 pm", title=config.APP_NAME, type_="info")
            subprocess.run(
                ["powershell", "-Command", f"Start-Process cmd -ArgumentList '/c {task_command}' -Verb RunAs"],
                shell=True,
                check=True
            )
            subprocess.run(
                ["powershell", "-Command", f"Start-Process cmd -ArgumentList '/c {task_command_cleanup}' -Verb RunAs"],
                shell=True,
                check=True
            )
            log(f"Update scheduled to run on the next reboot.", log_level=3)
            config.confirm_update = True
            # end_time = current_time + timedelta(seconds=5)
            # popup(msg=f"Ending the application in {end_time}", title=config.APP_NAME, type_="quit_app")

        except subprocess.CalledProcessError as e:
            log(f"Failed to schedule update: {e}", log_level=3)
            config.confirm_update = False
    except Exception as e:
        log(f"An error occurred during update: {e}", log_level=3)
        
        popup(
            msg="Windows Defender real-time protection is enabled. "
                "Please disable it temporarily and start the updating process again.",
            title=config.APP_NAME,
            type_="critical"
        )
            
def check_for_ytdl_update():
    """it will download "version.py" file from github to check for a new version, return ytdl_latest_version
    """

    url = 'https://github.com/ytdl-org/youtube-dl/raw/Windows/youtube_dl/version.py'

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
    new_module = os.path.join(current_directory, 'temp/youtube-dl-Windows/youtube_dl')

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
    url = 'https://github.com/ytdl-org/youtube-dl/archive/Windows.zip'
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

