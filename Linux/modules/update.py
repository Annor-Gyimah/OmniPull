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
import py_compile
import shutil
import sys
import tarfile
import zipfile
import time
import tempfile
import wget
import subprocess
from . import config
import os
from datetime import datetime, timedelta
from . import video
from .utils import log, download, run_command, delete_folder, popup
import webbrowser
import httpx
import socket
import uuid
import requests
import stat
from pathlib import Path


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
    content = httpx.get(url="https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest", headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64"},
                        follow_redirects=True).json()

    # Extract tagName and remove any unwanted characters like leading dots
    tagName = content["tag_name"].lstrip('v').lstrip('.').rstrip('[').lstrip(']')  # Remove 'v' or any leading dots
    

    
    # currentVersion = list(map(int, config.APP_VERSION.split(".")))
    
    source_code_url = 'https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Linux/ChangeLog.txt'
    new_release_url = 'https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Linux/ChangeLog.txt'

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



def detect_install_mode() -> str:
    """
    Returns one of: 'appimage', 'deb'
    - 'appimage' if running from an AppImage (APPIMAGE env is set)
    - otherwise 'deb' (your user-space symlink/versions layout)
    """
    if os.environ.get("APPIMAGE"):
        return "appimage"

    # Heuristic: your deb/launcher layout creates ~/.local/share/OmniPull/{versions,current}
    base = Path.home() / ".local" / "share" / "OmniPull"
    if (base / "current" / "omnipull").exists() or (base / "versions").exists():
        return "deb"

    # Fallback to deb updater; it’s the safer default for a non-AppImage run
    return "deb"


def update(via: str | None = None):
    """
    Auto-selects the right updater unless 'via' is explicitly provided.
    """
    mode = via or detect_install_mode()
    log(f"Updater mode detected: {mode} (APPIMAGE={'set' if os.environ.get('APPIMAGE') else 'unset'})")
    try:
        if mode == "appimage":
            appimage_update()
        elif mode == "deb":
            deb_update()
        else:
            log(f"Unknown update mode: {mode}, defaulting to deb")
            deb_update()
    except Exception as e:
        log(f"Update failed in mode={mode}: {e}", log_level=3)


############################# deb #################################################

def deb_update():
    """
    User-space update for .deb installs:
    - Download app payload (tar.gz) to ~/.local/share/OmniPull/versions/<tag>/
    - Atomically switch ~/.local/share/OmniPull/current -> that folder
    """
    

    # 1) discover latest tag
    content = httpx.get(
        url="https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest",
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True
    ).json()
    tag = content["tag_name"].lstrip('.').lstrip('v')  
    main_tar_url = f"https://github.com/Annor-Gyimah/OmniPull/releases/download/v{tag}/main.tar.gz"


    # 2) paths in user space
    base = Path.home() / ".local" / "share" / "OmniPull"
    versions = base / "versions"
    current = base / "current"
    versions.mkdir(parents=True, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp(prefix=".omni_up_"))
    tar_path = tmpdir / "main.tar.gz"

    try:
        # download
        log('Downloading update from', main_tar_url)
        popup(title="Update Info", msg='Downloading update, please wait... \n Do not close the app yet.', type_='info')
        with requests.get(main_tar_url, stream=True) as r:
            r.raise_for_status()
            with open(tar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        # unpack to a temporary folder first
        unpack = Path(tempfile.mkdtemp(prefix=".omni_unpack_"))
        log('Unpacking to', unpack)
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=unpack)

        # detect the runnable top
        # Case A: single top-level dir -> use it
        # Case B: flat tar -> use the unpack dir
        entries = [p for p in unpack.iterdir() if not p.name.startswith(".")]
        if len(entries) == 1 and entries[0].is_dir():
            top = entries[0]
        else:
            top = unpack

        # read version from VERSION if present, else use tag
        ver = None
        vfile = top / "VERSION"
        if vfile.exists():
            try:
                ver = vfile.read_text().strip().split()[0]
            except Exception:
                ver = None
        ver = ver or tag

        # target dir for this version
        verdir = versions / ver
        if verdir.exists():
            shutil.rmtree(verdir, ignore_errors=True)

        # move the actual runnable dir so that omnipull is directly under verdir/
        # If the tar had a top folder (like "OmniPull"), moving `top` to `verdir` yields
        # ~/.local/share/OmniPull/versions/<ver>/omnipull  (correct)
        shutil.move(str(top), str(verdir))
        log('Moved to', verdir)
        popup(title="Update Info", msg='Download complete. Finalizing update...', type_='info')

        # ensure executable bit on the app binary (and helpers if present)
        for name in ("omnipull", "ffmpeg", "aria2c", "omnipull-watcher"):
            p = verdir / name
            if p.exists():
                p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # atomically flip current -> verdir
        tmp_link = base / ".current.new"
        if tmp_link.exists():
            tmp_link.unlink()
        os.symlink(verdir, tmp_link)
        os.replace(tmp_link, current)

        # optional: prune old versions (keep 2)
        keep = 2
        kids = sorted([d for d in versions.iterdir() if d.is_dir()],
                      key=lambda p: p.stat().st_mtime, reverse=True)
        for d in kids[keep:]:
            shutil.rmtree(d, ignore_errors=True)

        # success note
        popup(title="Update", msg=f"Updated to {tag}. Restart OmniPull to use the new version.", type_="info")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        # remove the unpack dir, but only if we created it
        try:
            shutil.rmtree(unpack, ignore_errors=True)
        except Exception:
            pass



############################## APP IMAGE ###########################################

def _appimage_path() -> str:
    return os.environ.get("APPIMAGE") or str(Path.home() / "Applications" / "OmniPull.AppImage")

def appimage_update():
    OWNER = "Annor-Gyimah"
    REPO  = "OmniPull"
    TARGET = _appimage_path() # os.path.expanduser("~/Applications/OmniPull.AppImage")
    ARCH_TAG = "x86_64"  # or detect via platform.machine()

    api = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
    r = requests.get(api, headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    rel = r.json()

    # Pick the AppImage asset by name
    assets = rel.get("assets", [])
    asset = next(a for a in assets if a["name"].endswith(f"{ARCH_TAG}.AppImage"))
    url = asset["browser_download_url"]
    try:

        # Download to a temp file next to target
        os.makedirs(os.path.dirname(TARGET), exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".OmniPull.", dir=os.path.dirname(TARGET))
        os.close(fd)
        popup(title="Update Info", msg='Downloading update, please wait... \n Do not close the app yet.', type_='info')
        log(f"Downloading {url} to {tmp}")
        with requests.get(url, stream=True) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)

        # Make executable and swap atomically
        st = os.stat(tmp)
        os.chmod(tmp, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        shutil.move(tmp, TARGET)


        log(f"Updated {TARGET} to {asset['name']}")
        
        popup(title="Update Info", msg='Update was successfull. Please restart the app to reflect the changes.', type_='info')
    except Exception as e:
        popup(title='Update Error', msg=f'Update failed. Please try again later. {e}', type_='error')
        


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




