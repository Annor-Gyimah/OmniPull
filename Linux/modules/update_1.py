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
import tarfile
import wget
import subprocess
from . import config
import os
import time
import tempfile
import httpx
import socket
import uuid
import requests
from . import video
from .downloaditem import DownloadItem
from .utils import log, download, run_command, delete_folder, delete_file, popup, get_mac_id
import webbrowser


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

        return latest_version, contents

    else:
        log("check_for_update() --> couldn't check for update, url is unreachable")
        return None
    

# def get_changelog():
#     """download ChangeLog.txt from github, extract latest version number, return a tuple of (latest_version, contents)
#     """

#     # url will be chosen depend on frozen state of the application
#     source_code_url = 'http://localhost/lite/ChangeLog.txt'
#     new_release_url = 'http://localhost/lite/ChangeLog.txt'
#     url = new_release_url if config.FROZEN else source_code_url

#     # url = new_release_url

#     # get BytesIO object
#     buffer = download(url)

#     if buffer:
#         # convert to string
#         contents = buffer.getvalue().decode()

#         # extract version number from contents
#         latest_version = contents.splitlines()[0].replace(':', '').strip()

#         return latest_version, contents
#     else:
#         log("check_for_update() --> couldn't check for update, url is unreachable")
#         return None


def get_changelog():
    """download ChangeLog.txt from github, extract latest version number, return a tuple of (latest_version, contents)
    """

    # Get latest release info from GitHub API
    content = httpx.get(url="https://api.github.com/repos/Annor-Gyimah/Li-Dl/releases/latest", headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64"},
                        follow_redirects=True).json()

    # Extract tagName and remove any unwanted characters like leading dots
    tagName = content["tag_name"].lstrip('v').lstrip('.').rstrip('[').lstrip(']')  # Remove 'v' or any leading dots
    

    
    # currentVersion = list(map(int, config.APP_VERSION.split(".")))
    
    # url will be chosen depend on frozen state of the application
    source_code_url = 'https://github.com/Annor-Gyimah/Li-Dl/raw/refs/heads/master/Linux/ChangeLog.txt'
    new_release_url = 'https://github.com/Annor-Gyimah/Li-Dl/raw/refs/heads/master/Linux/ChangeLog.txt'

    url = new_release_url if config.FROZEN else source_code_url


    # get BytesIO object
    buffer = download(url)

    if buffer:
        # convert to string
        contents = buffer.getvalue().decode()

        # extract version number from contents
        #latest_version = contents.splitlines()[0].replace(':', '').strip()
        latest_version = tagName

        config.latest_version = latest_version
       

        return latest_version, contents
    else:
        log("check_for_update() --> couldn't check for update, url is unreachable")
        return None

def update():
    # Get the latest release from GitHub API
    content = httpx.get(
        url="https://api.github.com/repos/Annor-Gyimah/Li-Dl/releases/latest", 
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64"
        },
        follow_redirects=True
    ).json()

    tagName = content["tag_name"].lstrip('.')  # Remove 'v' and any leading dots
    
    
    update_script_url = "https://github.com/Annor-Gyimah/Li-Dl/raw/refs/heads/master/Linux/update.sh"  # URL for update.sh
    main_tar_url = f"https://github.com/Annor-Gyimah/Li-Dl/releases/download/{tagName}/main.tar.gz"     # URL for main.tar.gz

    # update_script_url = "http://localhost/lite/update.sh"  # URL for update.sh
    # main_tar_url = f"http://localhost/lite/main.tar.gz"     # URL for main.tar.gz

    

    # Create a hidden temporary directory in the user's home directory
    temp_dir = tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~"))
    download_path = os.path.join(temp_dir, "main.tar.gz")
    update_script_path = os.path.join(temp_dir, "update.sh")

    try:
        # Download update files to the temporary directory
        log("Downloading update files...")
        wget.download(update_script_url, update_script_path)
        wget.download(main_tar_url, download_path)
        log("\nDownload completed.")

        # Extract the downloaded tar.gz file in the temporary directory
        log("Extracting update package...")
        with tarfile.open(download_path, 'r:gz') as tar_ref:
            tar_ref.extractall(temp_dir)
        log("Extraction completed.")

        # Make the update script executable
        os.chmod(update_script_path, 0o755)
        source_file = os.path.join(temp_dir, "main")

        # Schedule update.sh to run at next reboot with cron
        cron_job = f"@reboot /bin/bash {update_script_path} {source_file} && rm -rf {temp_dir}"  # remove temp folder after execution
        try:
            popup(msg="Please authenticate to install updates on reboot", title=config.APP_NAME, type_="info")
            subprocess.run(f'(pkexec crontab -u root -l; echo "{cron_job}") | pkexec crontab -u root -', shell=True, check=True)
            log("Update scheduled to run on the next reboot.")
            config.confirm_update = True

        except subprocess.CalledProcessError as e:
            log(f"Failed to schedule update: {e}")
            config.confirm_update = False

        # cron_job = f"@reboot /bin/bash {update_script_path} {source_file} && rm -rf {temp_dir}"  # remove temp folder after execution
        # try:
        #     popup(msg="Please authenticate to install updates on reboot", title=config.APP_NAME, type_="info")
        #     subprocess.run(f'echo "{cron_job}" | pkexec crontab -u root -', shell=True, check=True)
        #     log("Update scheduled to run on the next reboot.")
        #     config.confirm_update = True

        # except subprocess.CalledProcessError as e:
        #     log(f"Failed to schedule update: {e}")
        #     config.confirm_update = False


    except Exception as e:
        log(f"An error occurred during update: {e}")

# def update():
#     #url = config.LATEST_RELEASE_URL if config.FROZEN else config.APP_URL
#     update_script_url = "http://localhost/lite/update.sh"  # URL for update.sh script
#     main_tar_url = "http://localhost/lite/main.tar.gz"     # URL for main.tar.gz

#     # Define paths on the Desktop for downloading
#     temp_dir = os.path.join(os.path.expanduser("~"), "Desktop", "temp")
#     if os.path.exists(temp_dir):
#         pass
#     else:
#         os.mkdir(temp_dir)
#     download_path = os.path.join(temp_dir, "main.tar.gz")
#     update_script_path = os.path.join(temp_dir, "update.sh")
    
    

#     try:
#         # Download update files
#         log("Downloading update files...")
#         wget.download(update_script_url, update_script_path)
#         wget.download(main_tar_url, download_path)
#         log("\nDownload completed.")

#         # Extract the downloaded tar.gz file
#         log("Extracting update package...")
#         with tarfile.open(download_path, 'r:gz') as tar_ref:
#             tar_ref.extractall(temp_dir)
#         log("Extraction completed.")
#         os.chmod(update_script_path, 0o755) 
#         schedule_update()
        
#         # Schedule update.sh to run at the next reboot
#         # Use `sudo crontab -u root` to add job directly to root's crontab
#         cron_job = f"@reboot /bin/bash {update_script_path} {temp_dir} && rm -rf {temp_dir}"  # delete temp folder after execution
#         try:
#             subprocess.run(f'(crontab -l; echo "{cron_job}") | crontab -', shell=True, check=True)
#             log("Update scheduled to run on the next reboot.")
#         except subprocess.CalledProcessError as e:
#             log(f"Failed to schedule update: {e}")


#         # # Define the path to the new 'main' file (adjust as necessary)
#         # new_main_path = os.path.join(extract_path, "main")  # Adjust if main file is in a different location

       

#     except Exception as e:
#         log(f"An error occurred during update: {e}")
    


def schedule_update():
    source_file = os.path.join(os.path.expanduser("~"), "Desktop", "temp", "main")
    update_script = os.path.join(os.path.expanduser("~"), "Desktop", "temp", "update.sh")

    # Define the cron job with explicit `root` crontab
    cron_job = f"@reboot /bin/bash {update_script} {source_file}"
    
    # Use `sudo crontab -u root` to add job directly to root's crontab
    try:
        
        subprocess.run(f'(pkexec crontab -u root -l; echo "{cron_job}") | pkexec crontab -u root -', shell=True, check=True)
        log("Update scheduled to run on the next reboot.")
    except subprocess.CalledProcessError as e:
        log(f"Failed to schedule update: {e}")

def on_exit():
    log("Preparing to start updater service...")

    source_file = os.path.join(os.path.expanduser("~"), "Desktop", "AppUpdate", "main")  # Path to new 'main'
    destination_dir = "/opt/main/"  # Directory where 'main' should go
    updater_script = os.path.join(os.path.expanduser("~"), "Desktop", "AppUpdate", "updater_service.py")

    try:
        # Launch the updater service
        subprocess.Popen(["python3", updater_script, source_file, destination_dir])
        
        log("Updater service started successfully.")
        time.sleep(2)  # Brief wait to allow updater to initialize

    except Exception as e:
        log(f"Failed to start updater service: {e}")


    # first check windows 32 or 64
#     import platform
#     # ends with 86 for 32 bit and 64 for 64 bit i.e. Win7-64: AMD64 and Vista-32: x86
#     if platform.machine().endswith('64'):
#         # 64 bit link
#         url = 'http://localhost/lite/pyiconic/main.tar.gz'
#     else:
#         # 32 bit link
#         url = 'http://localhost/lite/pyiconic/main.tar.gz'

#     log('downloading: ', url)

#     # create a download object, will store ffmpeg in setting folder
#     # print('config.sett_folder = ', config.sett_folder)
#     d = DownloadItem(url=url, folder=config.update_folder)
#     d.update(url)
#     d.name = 'main.tar.gz'  # must rename it for unzip to find it
#     # print('d.folder = ', d.folder)

#     # post download
#     d.callback = 'unzip_main'

#     # send download request to main window
#     config.main_window_q.put(('download', (d, True)))

# def unzip_main():
#     log('unzip_main:', 'unzipping')

#     try:
#         file_name = os.path.join(config.update_folder, 'main.tar.gz')
#         with zipfile.ZipFile(file_name, 'r') as zip_ref:  # extract zip file
#             zip_ref.extractall(config.update_folder)

#         log('main update:', 'delete zip file')
#         delete_file(file_name)
#         log('main update:', 'main .. is ready at: ', config.update_folder)
#     except Exception as e:
#         log('unzip_main: error ', e)


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
                    print(f"Update required: {update_status.get('new_version')}")
                else:
                    print(f"You are up to date. Version: {self.software_version}")
            else:
                print("Error checking update status")
        except requests.RequestException as e:
            pass
            print(f"Error connecting to the server: {e}")