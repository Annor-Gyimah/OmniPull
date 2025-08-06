"""
    pyIDM

    multi-connections internet download manager, based on "pyCuRL/curl", "youtube_dl", and "PySimpleGUI"

    :copyright: (c) 2019-2020 by Mahmoud Elshahat.
    :license: GNU LGPLv3, see LICENSE for more details.
"""

# check and update application
# import io
import py_compile
import shutil
import sys
import zipfile
import tempfile
import wget
import subprocess
from . import config
import os
from datetime import datetime, timedelta
from . import video
from .utils import log, download, run_command, delete_folder, popup, get_mac_id
import webbrowser
import httpx
import socket
import uuid
import requests

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
    try:
        # Get latest release info from GitHub API
        content = httpx.get(url="https://api.github.com/repos/Annor-Gyimah/Li-Dl/releases/latest", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64"},
            follow_redirects=True).json()

        # Extract tagName and remove any unwanted characters like leading dots
        tagName = content["tag_name"].lstrip('v').lstrip('.').rstrip('[').lstrip(']')  # Remove 'v' or any leading dots
        

        # url will be chosen depend on frozen state of the application
        source_code_url = 'https://github.com/Annor-Gyimah/Li-Dl/raw/refs/heads/development/Windows/ChangeLog.txt'
        new_release_url = 'https://github.com/Annor-Gyimah/Li-Dl/raw/refs/heads/development/Windows/ChangeLog.txt'
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
    
    


def update():

    # Get the latest release from GitHub API
    content = httpx.get(
        url="https://api.github.com/repos/Annor-Gyimah/Li-Dl/releases/latest", 
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64"
        },
        follow_redirects=True
    ).json()

    tagName = content["tag_name"].lstrip('.')  # Remove any leading dots
    
     
    # url = config.LATEST_RELEASE_URL if config.FROZEN else config.APP_URL
    update_script_url = "https://github.com/Annor-Gyimah/Li-Dl/raw/refs/heads/development/Windows/update.bat"  # URL for update.sh
    cleanup_script_url = "https://github.com/Annor-Gyimah/Li-Dl/raw/refs/heads/development/Windows/cleanup.bat"
    main_zip_url = f"https://github.com/Annor-Gyimah/Li-Dl/releases/download/{tagName}/main.zip"


    
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
                #f'schtasks /create /tn "{task_name}" /tr "{update_command}" /sc minute /mo 3 /rl HIGHEST /f'

                # f'schtasks /create /tn "{task_name}" /tr "{update_command}" /sc ONSTART /rl HIGHEST /f'

                f'schtasks /create /tn "{task_name}" /tr "{update_command}" /sc daily /st 12:00:00 /rl HIGHEST /f'

                #f'schtasks /create /tn "{task_name}" /tr "{update_command}" /sc once /st {formatted_time} /f'

                # f'schtasks /create /tn "{task_name}" /tr "{update_command}" 'f'/sc daily /st 12:00 /ri 60 /du 24:00 /rl HIGHEST /f'

            
                
            )

            
            

            # Schedule the cleanup task
            task_name_cleanup = f"{config.APP_NAME}_Cleanup"
            task_command_cleanup = (
                f'schtasks /create /tn "{task_name_cleanup}" /tr "{cleanup_command}" /sc daily /st 12:05:00 /f'
            )
            
            # Run the command as administrator
            popup(msg="Please authenticate to install updates", title=config.APP_NAME, type_="info")
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


class SoftwareUpdateChecker:
    def __init__(self, api_url, software_version):
        self.api_url = api_url
        self.software_version = software_version
        self.machine_id = self.get_machine_id()


    def get_machine_id(self):
        # Check if machine_id already exists in a local file
        # config_file = 'machine_config.json'
        # if os.path.exists(config_file):
        #     with open(config_file, 'r') as file:
        #         data = json.load(file)
        #         return data.get('machine_id')
        
        # If no machine_id found, generate it based on the MAC address or UUID
        mac_address = get_mac_id()
        machine_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, mac_address))  # Stable machine ID based on MAC
        config.machine_id = machine_id

        # Save it for future use
        # with open(config_file, 'w') as file:
        #     json.dump({'machine_id': machine_id}, file)

        return machine_id

    def get_machine_info(self):
        # Get the system information (for example: MAC address, computer name, etc.)
        mac_address = get_mac_id()
        computer_name = socket.gethostname()
        operating_system = config.operating_system_info

        return {
            'mac_address': mac_address,
            'computer_name': computer_name,
            'operating_system': operating_system,
            'software_version': self.software_version,
            'machine_id': f'{str(uuid.uuid5(uuid.NAMESPACE_DNS, get_mac_id))}' if config.machine_id == None else self.machine_id
        }


    def server_check_update(self):
        machine_info = self.get_machine_info()

        try:
            response = requests.post(
                f"{self.api_url}/software-update/",
                json=machine_info
            )
            if response.status_code == 200:
                update_status = response.json()
                print(update_status)
                if update_status.get('update_needed'):
                    log(f"Update required: {update_status.get('new_version')}")
                else:
                    log(f"You are up to date. Version: {self.software_version}")
            else:
                log("Error checking update status")
        except requests.RequestException as e:
            log(f"Error connecting to the server: {e}")