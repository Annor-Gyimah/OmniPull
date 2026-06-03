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
import wget
import time
import stat
import httpx
import shutil
import zipfile
import tarfile
import tempfile
import subprocess
import py_compile
import platform
import requests
from pathlib import Path
from typing import Tuple
from modules import config
from modules.app_signals import app_signals
from modules.setting import save_setting
from modules.aria2c_manager import aria2c_manager
import threading
from datetime import datetime
from PySide6.QtCore import QCoreApplication
from modules.utils import log, download, run_command, delete_folder, popup, _normalize_version_str


def get_changelog() -> Tuple[str | None, str | None]:
    """
    Returns (latest_version, contents) or (None, None) on failure.
    Tries GitHub first, then falls back to local ChangeLog.txt.
    """
    try:
        r = httpx.get(
            "https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"{config.APP_NAME}-Updater"
            },
            follow_redirects=True, timeout=30.0
        )
        r.raise_for_status()
        data = r.json()

        raw_tag = (data.get("tag_name") or "").strip()
        latest = _normalize_version_str(raw_tag)  # reuse helper above

        # Prefer a versioned ChangeLog from release assets if available; otherwise fallback
        assets = {a.get("name"): a.get("browser_download_url") for a in data.get("assets", []) if a}
        # changelog_url = (
        #     assets.get("ChangeLog.txt") or
        #     "https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Windows/ChangeLog.txt"
        # )
        changelog_url = "https://raw.githubusercontent.com/Annor-Gyimah/OmniPull/refs/heads/master/ChangeLog.txt"

        # Fetch changelog text (best-effort)
        text = None
        try:
            c = httpx.get(changelog_url, headers={"User-Agent": f"{config.APP_NAME}-Updater"},
                follow_redirects=True, timeout=30.0)
            if c.status_code == 200:
                text = c.text
            else:
                log(f"Changelog HTTP {c.status_code} at {changelog_url}", log_level=2)
        except httpx.RequestError as e:
            log(f"Changelog fetch error: {e}", log_level=2)

        # Fallback to local ChangeLog.txt if remote fetch failed
        if not text:
            try:
                local_changelog_path = Path(__file__).parent.parent / "ChangeLog.txt"
                if local_changelog_path.exists():
                    text = local_changelog_path.read_text(encoding="utf-8")
                    log(f"Using local changelog from {local_changelog_path}", log_level=1)
            except Exception as e:
                log(f"Failed to read local changelog: {e}", log_level=2)

        if not latest:
            log("Unable to parse latest version from GitHub response.", log_level=2)

        return latest, text

    except httpx.HTTPStatusError as e:
        log(f"GitHub API error: {e}", log_level=3)
        # Try local changelog as fallback
        try:
            local_changelog_path = Path(__file__).parent.parent / "ChangeLog.txt"
            if local_changelog_path.exists():
                text = local_changelog_path.read_text(encoding="utf-8")
                log(f"Using local changelog as fallback from {local_changelog_path}", log_level=1)
                return config.APP_VERSION, text
        except Exception as local_e:
            log(f"Failed to read local changelog: {local_e}", log_level=2)
        return config.APP_VERSION, None
    except httpx.RequestError as e:
        log(f"Network error while checking release: {e}", log_level=3)
        # Try local changelog as fallback
        try:
            local_changelog_path = Path(__file__).parent.parent / "ChangeLog.txt"
            if local_changelog_path.exists():
                text = local_changelog_path.read_text(encoding="utf-8")
                log(f"Using local changelog as fallback from {local_changelog_path}", log_level=1)
                return config.APP_VERSION, text
        except Exception as local_e:
            log(f"Failed to read local changelog: {local_e}", log_level=2)
        return config.APP_VERSION, None
    except Exception as e:
        log(f"Unexpected error in get_changelog: {e}", log_level=3)
        return config.APP_VERSION, None


############## For testing purposes ##########################################
# def get_changelog():

#     source_code_url = "http://localhost/lite/ChangeLog.txt"
#     new_release_url = "http://localhost/lite/ChangeLog.txt"

#     url = new_release_url if config.FROZEN else source_code_url

#     buffer = download(url)

#     if buffer:
#         contents = buffer.getvalue().decode()

#         latest_version = contents.splitlines()[0].replace(':', '').strip()

#         config.APP_LATEST_VERSION = latest_version

#         return latest_version, contents

#     else:
#         return None

################## For testing purposes ###############################################




def human_bytes(n):  # keep your sizeof_fmt if you prefer
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024 or unit == "TB":
            return f"{n:,.1f} {unit}"
        n /= 1024

def format_progress_bar(percentage, bar_length=20):
    filled_length = int(bar_length * percentage // 100)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    return f"{percentage:3.0f}%|{bar}"

def download_with_resume(url: str, dest: Path, progress_cb=None, type_update_file=None, timeout=60.0):
    """
    Resume-safe download.
    - Respects 206 with Content-Range
    - If server returns 200 when we requested a range, restarts cleanly to avoid corruption
    - Optionally reports progress via progress_cb(percent, speed_bps, downloaded, total)
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    existing = dest.stat().st_size if dest.exists() else 0

    headers = {}
    mode = "wb"
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"
        log(f"Resuming from {existing} bytes")

    start = time.time()
    last_tick = -1

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        r = client.get(url, headers=headers)
        if r.status_code == 206:
            # Range honored
            cr = r.headers.get("Content-Range", "")
            # format: bytes start-end/total
            try:
                total = int(cr.split("/")[-1])
            except Exception:
                total = None
        elif r.status_code in [200, 416]:
            # Server ignored our Range. If we had a partial, start fresh.
            if existing > 0 and dest.exists():
                log("Server ignored Range; restarting full download to avoid corruption.")
                dest.unlink()
                existing = 0
                mode = "wb"
                r = client.get(url)  # full
            total = int(r.headers.get("Content-Length", "0") or "0") or None
        
        else:
            raise RuntimeError(f"Unexpected status code {r.status_code}")

        downloaded = existing
        total = total or downloaded  # avoid div-by-zero

        with open(dest, mode) as f:
            for chunk in r.iter_bytes():
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)

                # Progress (integer % steps)
                if total:
                    pct = int(downloaded * 100 / total)
                else:
                    pct = 0
                now_tick = pct // 5  # log every 5%
                elapsed = max(0.0001, time.time() - start)
                speed = downloaded / elapsed

                if now_tick != last_tick or downloaded == total:
                    bar = format_progress_bar(pct)
                    log(f"Downloading {type_update_file}: {bar} | "
                        f"{human_bytes(downloaded)}/{human_bytes(total)} "
                        f"[{elapsed:0.0f}s, {human_bytes(speed)}/s]")
                    last_tick = now_tick

                if progress_cb:
                    progress_cb(pct, speed, downloaded, total)

        # Best-effort final size check
        if total and downloaded != total:
            raise RuntimeError(f"Incomplete download: got {downloaded} of {total} bytes")

    return dest




def _safe_extract_all(zip_path: Path, dest_dir: Path) -> Path:
    """
    Safely extracts a ZIP file and returns the path to the main executable.
    
    Args:
        zip_path: Path to the ZIP file to extract
        dest_dir: Destination directory for extraction
        
    Returns:
        Path to the found main.exe file
        
    Raises:
        FileNotFoundError: If main.exe is not found in the extracted contents
        RuntimeError: If unsafe paths are detected in the ZIP
    """
    log("Extracting update package…", log_level=1)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            target = dest_dir / member.filename
            # prevent zip slip
            if not str(target.resolve()).startswith(str(dest_dir.resolve())):
                raise RuntimeError(f"Unsafe path in zip: {member.filename}")
        zf.extractall(dest_dir)
    
    # Find the executable BEFORE logging it
    new_exe_path = find_exe(dest_dir, "main.exe")
    log(f"Found new executable: {new_exe_path}", log_level=1)
    
    return new_exe_path

    

def find_exe(dest_dir: Path, exe_name="main.exe") -> Path:
    for p in dest_dir.rglob(exe_name):
        if p.is_file():
            return p
    raise FileNotFoundError(f"{exe_name} not found in extracted contents.")




def get_app_latest_release():
    r = httpx.get(
        "https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "OmniPull-Updater"},
        follow_redirects=True, timeout=30.0
    )
    r.raise_for_status()
    return r.json()


def download_updates(main_zip_url, destination_folder=None, callback=None, file_name=None):
    """
    Unified cross-platform download function.
    
    Args:
        main_zip_url: URL of the file to download
        destination_folder: Folder where file will be saved (auto-generated if None)
        callback: Function to call after download completes (receives DownloadItem)
        file_name: Override filename (auto-detected if None)
    """
    from modules.downloaditem import DownloadItem
    
    system = platform.system()
    log("Downloading update files...", log_level=1)
    
    try:
        # Auto-detect destination if not provided
        if destination_folder is None:
            destination_folder = str(Path(tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~"))))
        
        # Auto-detect filename if not provided
        if file_name is None:
            if system == "Windows":
                file_name = "main.zip"
            else:
                mode = detect_install_mode()
                file_name = "main.tar.gz" if mode == "deb" else "OmniPull.AppImage"
        
        # Create and configure DownloadItem
        d = DownloadItem(url=main_zip_url, folder=destination_folder)
        d.update(main_zip_url)
        d.is_internal = True
        d.name = file_name
        
        # Attach callback if provided
        if callback:
            d.callback = callback
        
        # Queue the download
        config.main_window_q.put(('download', (d, False)))
        log(f"Queued download: {file_name} to {destination_folder}", log_level=1)
        
    except Exception as e:
        log(f"Error queuing download: {e}", log_level=3)
        error_msg = QCoreApplication.translate(
            "Update",
            "Failed to start update download\n\nDetails:\n%1"
        ).replace("%1", str(e))
        popup(msg=error_msg, title=config.APP_NAME, type_="critical")


    


# ====================================================================================
# WINDOWS UPDATE LOGIC
# ====================================================================================



def create_update_script(path: Path):
    """Generates the update.bat script locally."""
    content = (
        "@echo off\n"
        "set NEW_EXE=%~1\n"
        "set CURRENT_EXE=%~2\n"
        "set PID=%~3\n"
        "set TEMP_DIR=%~4\n\n"
        ":: Use %LOCALAPPDATA% to dynamically find the user's path\n"
        "set RUST_UPDATER=%LOCALAPPDATA%\\Annorion\\OmniPull\\omnipull-updater.exe\n\n"
        ":: Launch Rust and exit immediately\n"
        'start "" /b "%RUST_UPDATER%" --new-exe "%NEW_EXE%" --current-exe "%CURRENT_EXE%" --pid %PID% --temp-dir "%TEMP_DIR%" --relaunch\n'
        "exit /b 0"
    )
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _execute_windows_core_update(d):
    """
    Callback executed after OmniPull update package is downloaded.
    Extracts the package, locates the new executable, and triggers the updater.
    """
    ctx = "CORE-UPDATE-EXEC"
    temp_dir = Path(d.folder)
    update_bat = Path.home() / "update.bat"
    
    try:
        log("Executing core application update...", log_level=1, context=ctx)
        log("Starting Windows update process...", log_level=1, context=ctx)
        
        # Generate update script first
        log("Generating local update script...", log_level=1, context=ctx)
        create_update_script(update_bat)
        
        # Extract the downloaded zip to the temp folder
        # The file should be at d.target_file or temp_dir/d.name
        zip_path = Path(d.target_file) if hasattr(d, 'target_file') and d.target_file else temp_dir / d.name
        
        log(f"Extracting update package from {zip_path}…", log_level=1, context=ctx)
        if not zip_path.exists():
            raise FileNotFoundError(f"Update package not found at {zip_path}")
        
        # Extract and get the new executable path
        new_exe_path = _safe_extract_all(zip_path, temp_dir)
        log(f"Located new executable: {new_exe_path}", log_level=1, context=ctx)
        
        # Get the current target executable path
        local_app_data = os.getenv('LOCALAPPDATA')
        app_dir = Path(local_app_data) / "Annorion" / "OmniPull"
        target_exe = app_dir / "main.exe"
        
        # Save original hide_app setting to restore after update
        original_hide_app = config.hide_app
        
        # Temporarily disable hide_app to allow clean exit during update
        config.hide_app = False
        save_setting()
        
        # Prepare clean environment
        clean_env = os.environ.copy()
        clean_env.pop("_MEIPASS", None)
        clean_env.pop("PYTHONPATH", None)
        clean_env.pop("PYTHONHOME", None)
        
        # Log the update parameters for debugging
        current_pid = os.getpid()
        log("=== OmniPull Update Started ===", log_level=1, context=ctx)
        log(f"NEW_EXE={new_exe_path}", log_level=1, context=ctx)
        log(f"CURRENT_EXE={target_exe}", log_level=1, context=ctx)
        log(f"PID={current_pid}", log_level=1, context=ctx)
        log(f"TEMP_DIR={temp_dir}", log_level=1, context=ctx)
        log(f"RUST_UPDATER path set to: {app_dir / 'omnipull-updater.exe'}", log_level=1, context=ctx)
        
        # Shutdown aria2 if running
        if config.aria2_verified is True:
            aria2c_manager.cleanup_orphaned_paused_downloads()
            aria2c_manager.shutdown_freeze_and_save(purge=True)
            aria2c_manager._terminate_existing_processes()
        
        # Launch the update batch script
        log("Triggering update batch with clean environment...", log_level=1, context=ctx)
        bat_path = Path.home() / "update.bat"
        
        # Remove ONLY the problematic variables
        vars_to_scrub = ["_MEIPASS", "_MEIPASS2", "PYTHONPATH", "PYTHONHOME"]
        for var in vars_to_scrub:
            clean_env.pop(var, None)

        # Ensure APPDATA and USERPROFILE are definitely there
        if "APPDATA" not in clean_env:
            clean_env["APPDATA"] = os.environ.get("APPDATA", "")
        if "USERPROFILE" not in clean_env:
            clean_env["USERPROFILE"] = os.environ.get("USERPROFILE", "")
        
        cmd_to_run = [
            "cmd.exe", "/c",
            str(bat_path),
            str(new_exe_path),
            str(target_exe),
            str(current_pid),
            str(temp_dir)
        ]
        
        subprocess.Popen(
            cmd_to_run,
            env=clean_env,
            creationflags=0x08000000 | 0x00000008,
            close_fds=True
        )
        
        log("Update batch triggered. Exiting application...", log_level=1, context=ctx)
        os._exit(3)
        
    except Exception as e:
        config.confirm_update = False
        log(f"Core update execution failed: {e}", log_level=3, context=ctx)
        
        # Remove from internal list
        try:
            config.main_window_q.put(('remove_internal_download', d.id))
        except:
            pass
        
        error_msg = QCoreApplication.translate(
            "Update",
            "Update failed\n\nDetails:\n%1\n\nIf this keeps happening, check your network and antivirus exclusions."
        ).replace("%1", str(e))
        
        popup(
            msg=error_msg,
            title=config.APP_NAME,
            type_="critical"
        )


def windows_update():
    """
    Initiates OmniPull core update using the download engine (Windows).
    Downloads the update package and queues extraction/updater logic via callback.
    """
    # main_zip_url = "http://localhost/lite/main.zip"
    # temp_dir = Path(tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~")))

    rel = get_app_latest_release()
    tag = rel["tag_name"].lstrip(".")
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}

    main_zip_url = assets.get("main.zip") or f"https://github.com/Annor-Gyimah/OmniPull/releases/download/{tag}/main.zip"

    temp_dir = Path(tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~")))
    download_zip = temp_dir / "main.zip"
    update_bat = Path.home() / "update.bat"

    try:
        popup(
            title=config.APP_NAME,
            msg=QCoreApplication.translate(
                "Update", 
                "Updating your application...\n\nThis may take about 1 minute.\n\nPlease do not interrupt the process."
            ),
            type_="info"
        )

        download_updates(
            main_zip_url=main_zip_url,
            destination_folder=str(temp_dir),
            callback=_execute_windows_core_update,
            file_name="main.zip"
        )
        
    except Exception as e:
        config.confirm_update = False
        log(f"Network error during update: {e}", log_level=3)
        
        error_msg = QCoreApplication.translate(
            "Update",
            "Network error during update\n\nDetails:\n%1\n\nPlease check your connection and try again."
        ).replace("%1", str(e))

        popup(
            msg=error_msg,
            title=config.APP_NAME,
            type_="critical"
        )
        




# ====================================================================================
# LINUX UPDATE LOGIC
# ====================================================================================

def sizeof_fmt(num, suffix="B"):
    """Format bytes to human-readable string."""
    for unit in ['','K','M','G','T']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}P{suffix}"


def detect_install_mode() -> str:
    """
    Detect Linux installation mode.
    Returns one of: 'appimage', 'deb'
    - 'appimage' if running from an AppImage (APPIMAGE env is set)
    - otherwise 'deb' (user-space symlink/versions layout)
    """
    if os.environ.get("APPIMAGE"):
        return "appimage"

    # Heuristic: deb/launcher layout creates ~/.local/share/OmniPull/{versions,current}
    base = Path.home() / ".local" / "share" / "OmniPull"
    if (base / "current" / "omnipull").exists() or (base / "versions").exists():
        return "deb"

    # Fallback to deb updater; it's the safer default for a non-AppImage run
    return "deb"


def download_linux_with_progress(url: str, dest_path: Path, *, chunk_size: int = 1024 * 1024):
    """
    Download URL -> dest_path with resume support and progress logging.
    Works for both .deb and AppImage downloads.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    file_mode = "wb"
    existing_size = 0

    if dest_path.exists():
        existing_size = dest_path.stat().st_size
        if existing_size > 0:
            headers["Range"] = f"bytes={existing_size}-"
            file_mode = "ab"
            log(f"Resuming download from byte {existing_size}")
        else:
            log("Existing zero-byte temp file; starting fresh download")
            file_mode = "wb"
    else:
        log("Starting new download")

    timeout = httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=60.0)

    try:
        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=timeout) as r:
            if r.status_code not in (200, 206):
                raise RuntimeError(f"Unexpected status code: {r.status_code}")

            # Determine total size
            if "Content-Range" in r.headers:
                total_size = int(r.headers["Content-Range"].split("/")[-1])
            else:
                total_size = int(r.headers.get("Content-Length") or 0)

            bytes_downloaded = existing_size
            start_time = time.time()
            last_logged_bucket = -1

            # Ensure parent dir exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            with open(dest_path, file_mode) as f:
                for chunk in r.iter_bytes(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    bytes_downloaded += len(chunk)

                    elapsed = max(time.time() - start_time, 1e-6)
                    speed = bytes_downloaded / elapsed

                    if total_size > 0:
                        percent = (bytes_downloaded / total_size) * 100.0
                        eta = (total_size - bytes_downloaded) / speed if speed > 0 else 0
                        bucket = int(percent // 5)
                        if bucket != last_logged_bucket or bytes_downloaded == total_size:
                            bar = format_progress_bar(percent)
                            log(f"Downloading update: {bar} | "
                                f"{sizeof_fmt(bytes_downloaded)}/{sizeof_fmt(total_size)} "
                                f"[{elapsed:05.0f}s<{eta:02.0f}s, {sizeof_fmt(speed)}/s]")
                            last_logged_bucket = bucket
                    else:
                        # Unknown total size -> log every ~5MB increment
                        if bytes_downloaded % (5 * 1024 * 1024) < chunk_size:
                            log(f"Downloading update: {sizeof_fmt(bytes_downloaded)} "
                                f"[{elapsed:05.0f}s, {sizeof_fmt(speed)}/s]")
    except Exception as e:
        raise RuntimeError(f"Failed to download {url}: {e}")



def _execute_appimage_core_update(d):
    """
    Callback executed after AppImage update package is downloaded.
    Makes it executable and atomically replaces the current AppImage.
    """
    ctx = "CORE-UPDATE-EXEC"
    
    try:
        log("Executing AppImage update...", log_level=1, context=ctx)
        
        # Get the downloaded file
        appimage_file = Path(d.target_file) if hasattr(d, 'target_file') and d.target_file else Path(d.folder) / d.name
        target_path = Path(_appimage_path())
        
        if not appimage_file.exists():
            raise FileNotFoundError(f"AppImage not found at {appimage_file}")
        
        log(f"Making AppImage executable...", log_level=1, context=ctx)
        st = os.stat(appimage_file)
        os.chmod(appimage_file, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        
        log(f"Replacing current AppImage...", log_level=1, context=ctx)
        shutil.move(str(appimage_file), str(target_path))
        
        tag, contents = get_changelog()
        popup(
            title=QCoreApplication.translate("Update", "Update"),
            msg=QCoreApplication.translate("Update", f"Updated to version {tag}. Restart OmniPull to use the new version."),
            type_="info"
        )
        
        # Remove from internal list
        try:
            config.main_window_q.put(('remove_internal_download', d.id))
        except:
            pass
            
    except Exception as e:
        log(f"AppImage update failed: {e}", log_level=3, context=ctx)
        
        # Remove from internal list
        try:
            config.main_window_q.put(('remove_internal_download', d.id))
        except:
            pass
        
        popup(
            title='Update Error',
            msg=f'AppImage update failed: {e}',
            type_='error'
        )


def deb_update():
    """
    Initiates OmniPull core update using the download engine (Linux deb mode).
    """
    main_tar_url = "http://localhost/lite/main.tar.gz"
    temp_dir = Path(tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~")))

    #     # 1) Discover latest tag
    #     content = httpx.get(
    #         url="https://api.github.com/repos/Annor-Gyimah/OmniPull/releases/latest",
    #         headers={"User-Agent": "Mozilla/5.0"},
    #         follow_redirects=True
    #     ).json()
    #     tag = content["tag_name"].lstrip('.').lstrip('v')
    #     main_tar_url = f"https://github.com/Annor-Gyimah/OmniPull/releases/download/v{tag}/main.tar.gz"

    #     ############ TESTING UPDATES #############################################################

    #     # main_tar_url = "http://localhost/lite/main.tar.gz"  # 
    #     # temp_dir = Path(tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~")))
    #     # tag, contents = get_changelog()

    #     ############ TESTING UPDATES #############################################################
    
    try:
        popup(
            title=config.APP_NAME,
            msg=QCoreApplication.translate(
                "Update",
                "Updating your application...\n\nThis may take about 1 minute.\n\nPlease do not interrupt the process."
            ),
            type_="info"
        )
        
        download_updates(
            main_zip_url=main_tar_url,
            destination_folder=str(temp_dir),
            callback=_execute_deb_core_update,
            file_name="main.tar.gz"
        )
    except Exception as e:
        log(f"Deb update init failed: {e}", log_level=3)
        error_msg = QCoreApplication.translate(
            "Update",
            "Update failed\n\nDetails:\n%1"
        ).replace("%1", str(e))
        popup(msg=error_msg, title=config.APP_NAME, type_="critical")


def _execute_deb_core_update(d):
    """
    Callback executed after OmniPull update package is downloaded (Linux deb mode).
    Extracts the package, updates symlink, and prepares for restart.
    """
    ctx = "CORE-UPDATE-EXEC"
    temp_dir = Path(d.folder)
    
    # Use the actual downloaded file path
    tar_path = Path(d.target_file) if hasattr(d, 'target_file') and d.target_file else temp_dir / d.name

    tag, contents = get_changelog()

    base = config.DATA_ROOT
    versions = base / "versions"
    current = base / "current"
    versions.mkdir(parents=True, exist_ok=True)

    
        

    try:
        log("Executing core application update...", log_level=1, context=ctx)
        log("Starting Linux deb update process...", log_level=1, context=ctx)
        
        # Verify tar file exists
        if not tar_path.exists():
            raise FileNotFoundError(f"Update package not found at {tar_path}")
        
        # Unpack to a temporary folder first
        unpack = Path(tempfile.mkdtemp(prefix=".omni_unpack_"))
        log(f'Unpacking to {unpack}', log_level=1, context=ctx)
        with tarfile.open(str(tar_path), "r:gz") as tar:
            tar.extractall(path=unpack)

        # Detect the runnable top
        entries = [p for p in unpack.iterdir() if not p.name.startswith(".")]
        if len(entries) == 1 and entries[0].is_dir():
            top = entries[0]
        else:
            top = unpack

        # Read version from VERSION if present, else use tag
        ver = None
        vfile = top / "VERSION"
        if vfile.exists():
            try:
                ver = vfile.read_text().strip().split()[0]
            except Exception:
                ver = None
        ver = ver or tag

        # Target dir for this version
        verdir = versions / ver
        if verdir.exists():
            shutil.rmtree(verdir, ignore_errors=True)

        # Move the actual runnable dir
        shutil.move(str(top), str(verdir))
        log(f'Moved to {verdir}')
        popup(
            title=QCoreApplication.translate("Update", "Update Info"),
            msg=QCoreApplication.translate("Update", "Download complete. Finalizing update..."),
            type_='info'
        )
        # Ensure executable bit on the app binary and helpers
        for name in ("omnipull", "ffmpeg", "aria2c", "omnipull-watcher"):
            p = verdir / name
            if p.exists():
                p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Atomically flip current -> verdir
        tmp_link = base / ".current.new"
        if tmp_link.exists():
            tmp_link.unlink()
        os.symlink(verdir, tmp_link)
        os.replace(tmp_link, current)

        # Optional: prune old versions (keep 2)
        keep = 2
        kids = sorted([d for d in versions.iterdir() if d.is_dir()],
                    key=lambda p: p.stat().st_mtime, reverse=True)
        for d in kids[keep:]:
            shutil.rmtree(d, ignore_errors=True)

        # Success message
        popup(
            title=QCoreApplication.translate("Update", "Update"),
            msg=QCoreApplication.translate("Update", f"Updated to version {tag}. Restart OmniPull to use the new version."),
            type_="info"
        )
        
        # Remove from internal list
        try:
            config.main_window_q.put(('remove_internal_download', d.id))
        except:
            pass

    except Exception as e:
        log(f"Core update execution failed: {e}", log_level=3, context=ctx)
        
        # Remove from internal list
        try:
            config.main_window_q.put(('remove_internal_download', d.id))
        except:
            pass
        
        error_msg = QCoreApplication.translate(
            "Update",
            "Update failed\n\nDetails:\n%1\n\nPlease try again or update manually."
        ).replace("%1", str(e))
        
        popup(
            msg=error_msg,
            title=config.APP_NAME,
            type_="critical"
        )
    
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
        try:
            shutil.rmtree(unpack, ignore_errors=True)
        except:
            pass
            

def _appimage_path() -> str:
    """Get the AppImage path from environment or default location."""
    return os.environ.get("APPIMAGE") or str(Path.home() / "Applications" / "OmniPull.AppImage")


def _tmp_download_path(target_path: str) -> str:
    """Create a temporary download path next to the target file."""
    d = os.path.dirname(target_path)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f".OmniPull.{int(time.time())}.download")


def appimage_update():
    """
    Initiates OmniPull core update using the download engine (Linux AppImage mode).
    """
    OWNER = "Annor-Gyimah"
    REPO = "OmniPull"
    ARCH_TAG = "x86_64"

    # Get download URL from GitHub
    try:
        # api = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
        # r = requests.get(api, headers={"Accept": "application/vnd.github+json"}, timeout=30)
        # r.raise_for_status()
        # rel = r.json()

        # # Pick the AppImage asset by name
        # assets = rel.get("assets", [])
        # asset = next(a for a in assets if a["name"].endswith(f"{ARCH_TAG}.AppImage"))
        # url = asset["browser_download_url"]
        url = f"http://localhost/lite/OmniPull-portable-{config.APP_LATEST_VERSION}-x86_64.AppImage" 
    #     # tag, contents = get_changelog()
    except Exception as e:
        log(f"Failed to get AppImage download URL: {e}", log_level=3)
        popup(
            title='Update Error',
            msg=f'Failed to check for updates: {e}',
            type_='error'
        )
        return

    # Prepare destination folder
    target_path = Path(_appimage_path())
    temp_folder = str(target_path.parent)

    try:
        popup(
            title=config.APP_NAME,
            msg=QCoreApplication.translate(
                "Update",
                "Updating your application...\n\nThis may take about 1 minute.\n\nPlease do not interrupt the process."
            ),
            type_="info"
        )

        download_updates(
            main_zip_url=url,
            destination_folder=temp_folder,
            callback=_execute_appimage_core_update,
            file_name=target_path.name
        )

    except Exception as e:
        log(f"AppImage update init failed: {e}", log_level=3)
        popup(
            title='Update Error',
            msg=f'Update failed: {e}',
            type_='error'
        )


def linux_update(via: str | None = None):
    """
    Auto-selects the right Linux updater unless 'via' is explicitly provided.
    """
    mode = via or detect_install_mode()
    log(f"Linux updater mode detected: {mode} (APPIMAGE={'set' if os.environ.get('APPIMAGE') else 'unset'})")

    try:
        if mode == "appimage":
            appimage_update()
        elif mode == "deb":
            deb_update()
        else:
            log(f"Unknown update mode: {mode}, defaulting to deb")
            deb_update()
    except Exception as e:
        log(f"Linux update failed in mode={mode}: {e}", log_level=3)
        popup(title='Update Error', msg=f'Update failed: {e}', type_='error')


# ====================================================================================
# MACOS UPDATE LOGIC
# ====================================================================================

def macos_update():
    """
    macOS update function.
    For now, directs users to download manually.

    Future implementation could:
    - Download .dmg file from GitHub releases
    - Mount DMG automatically
    - Copy app to Applications folder
    - Unmount DMG and cleanup

    Note: macOS grace period logic is handled separately by
    check_for_updates_cross_platform() in the startup check.
    """
    log("macOS manual update initiated", log_level=1)

    try:
        # Get latest release info
        rel = get_app_latest_release()
        tag = rel.get("tag_name", "").lstrip("v").lstrip(".")

        # Look for DMG asset
        assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        dmg_asset = None
        for name, url in assets.items():
            if name.endswith(".dmg"):
                dmg_asset = {"name": name, "url": url}
                break

        if dmg_asset:
            # DMG found - could implement automatic download here
            msg = (f"A new version ({tag}) is available.\n\n"
                   f"Download: {dmg_asset['name']}\n\n"
                   f"Visit: https://github.com/Annor-Gyimah/OmniPull/releases/latest")
        else:
            # No DMG found - direct to releases page
            msg = (f"A new version ({tag}) is available.\n\n"
                   f"Please download it from:\n"
                   f"https://github.com/Annor-Gyimah/OmniPull/releases/latest")

        popup(
            title="Update Available",
            msg=msg,
            type_="info"
        )

    except Exception as e:
        log(f"macOS update check failed: {e}", log_level=3)
        popup(
            title="Update Available",
            msg="A new version is available.\n\nPlease download it from:\nhttps://github.com/Annor-Gyimah/OmniPull/releases/latest",
            type_="info"
        )


# ====================================================================================
# UNIFIED UPDATE FUNCTION (CROSS-PLATFORM)
# ====================================================================================

def update():
    """
    Cross-platform update dispatcher.
    Routes to platform-specific update logic:
    - Windows: windows_update() (scheduled task)
    - Linux: linux_update() (AppImage or .deb)
    - macOS: macos_update() (manual download for now)
    """
    system = platform.system()

    if system == "Windows":
        log("Starting Windows update process...", log_level=1)
        windows_update()
    elif system == "Linux":
        log("Starting Linux update process...", log_level=1)
        linux_update()
    elif system == "Darwin":
        log("Starting macOS update process...", log_level=1)
        macos_update()
    else:
        log(f"Unsupported platform for auto-update: {system}", log_level=3)


def start_grace_period(version: str):
    """
    Start the grace period for a deferred update.
    
    Args:
        version: The version the user deferred
    """
    config.update_dismissed_version = version
    config.update_dismissed_timestamp = datetime.now().isoformat()
    config.update_grace_period_days = 7
    log(f"Grace period started for version {version}", log_level=1)


def check_update_grace_period() -> Tuple[bool, int, str | None]:
    """
    Check if the update grace period has expired.
    
    Returns:
        Tuple of (expired: bool, days_remaining: int, first_notified: str | None)
        - expired: True if 7+ days have passed since dismissal
        - days_remaining: Days until aggressive message appears (0 if expired)
        - first_notified: ISO timestamp of when user first deferred (or None)
    """
    dismissed_timestamp = getattr(config, 'update_dismissed_timestamp', None)
    grace_period_days = getattr(config, 'update_grace_period_days', 7)
    
    if not dismissed_timestamp:
        return False, grace_period_days, None
    
    try:
        dismissed_dt = datetime.fromisoformat(dismissed_timestamp)
        now = datetime.now()
        days_elapsed = (now - dismissed_dt).days
        days_remaining = max(0, grace_period_days - days_elapsed)
        
        expired = days_elapsed >= grace_period_days
        
        log(
            f"Grace period check: {days_elapsed}/{grace_period_days} days elapsed | Expired: {expired}",
            log_level=2
        )
        
        return expired, days_remaining, dismissed_timestamp
    
    except (ValueError, TypeError) as e:
        log(f"Error parsing grace period timestamp: {e}", log_level=2)
        return False, grace_period_days, None
        popup(
            title="Update Error",
            msg=f"Auto-update not supported on {system}.\nPlease update manually.",
            type_="error"
        )


# ====================================================================================
# YT-DLP UPDATE LOGIC (CROSS-PLATFORM)
# ====================================================================================

def get_ytdlp_latest_release():
    r = httpx.get(
        "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "OmniPull-Updater"},
        follow_redirects=True, timeout=30.0
    )
    r.raise_for_status()
    return r.json()

def safe_replace_exe(new_exe_path: Path, target_exe_path: Path):
    try:
        os.replace(str(new_exe_path), str(target_exe_path))
        return True, "yt-dlp has been updated successfully."
    except PermissionError:
        pending_update = target_exe_path.with_suffix('.exe.new')
        try:
            shutil.move(str(new_exe_path), str(pending_update))
            return False, "yt-dlp is currently in use. Update saved and will be applied on next app restart."
        except Exception as e:
            return False, f"PermissionError and failed to save pending update: {e}"
    except Exception as e:
        return False, f"Failed to replace yt-dlp: {e}"


def update_yt_dlp():
    """
    Cross-platform yt-dlp updater.
    - Windows: Downloads yt-dlp.exe
    - Linux: Downloads yt-dlp_linux
    - macOS: Downloads yt-dlp_macos
    """
    yt_dlp_path = getattr(config, "yt_dlp_exe", "") or config.yt_dlp_actual_path
    if not yt_dlp_path or not os.path.isfile(yt_dlp_path):
        return False, QCoreApplication.translate("updater", "yt-dlp not set or not found.")

    target_exe = Path(yt_dlp_path)

    # Platform-specific temp file suffix
    system = platform.system()
    if system == "Windows":
        tmp_exe = target_exe.with_suffix('.exe.tmp')
        pending_exe = target_exe.with_suffix('.exe.new')
    else:
        # Linux/macOS: no .exe suffix
        tmp_exe = Path(str(target_exe) + '.tmp')
        pending_exe = Path(str(target_exe) + '.new')

    # Get current version
    try:
        kwargs = dict(capture_output=True, text=True, timeout=8)
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = si
        proc = subprocess.run([str(target_exe), "--version"], **kwargs)
        current_version = proc.stdout.strip().splitlines()[0] if proc.stdout else ""
    except Exception as e:
        return False, f"Failed to get yt-dlp version: {e}"

    # Get latest release info
    try:
        log('Checking for latest yt-dlp version')
        rel = get_ytdlp_latest_release()
        tag = rel.get("tag_name", "")
        latest_version = tag
        log(f'Latest yt-dlp version: {latest_version}')
    except Exception as e:
        return False, f"Failed to check latest yt-dlp version: {e}"

    if not latest_version or not current_version or latest_version.lstrip("v") == current_version.lstrip("v"):
        log(f'Current yt-dlp version: {current_version}')
        msg = QCoreApplication.translate("updater", "yt-dlp is up to date.")
        return False, msg

    # Platform-specific download URL
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}

    if system == "Windows":
        exe_url = assets.get('yt-dlp.exe') or f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/yt-dlp.exe"
        download_name = 'yt-dlp.exe'
    elif system == "Darwin":
        exe_url = assets.get('yt-dlp_macos') or f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/yt-dlp_macos"
        download_name = 'yt-dlp_macos'
    else:  # Linux
        exe_url = assets.get('yt-dlp_linux') or f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/yt-dlp_linux"
        download_name = 'yt-dlp_linux'

    log(f"Updating yt-dlp from {current_version} to {latest_version}", log_level=1)

    # Ensure any leftover tmp file is removed
    try:
        if tmp_exe.exists():
            tmp_exe.unlink()
    except Exception:
        pass

    try:
        # Download to tmp file first
        if system == "Windows":
            download_with_resume(exe_url, tmp_exe, type_update_file=download_name)
        else:
            # Linux/macOS: use Linux download function
            download_linux_with_progress(exe_url, tmp_exe)

        # Attempt to atomically replace
        try:
            os.replace(str(tmp_exe), str(target_exe))

            # Linux/macOS: Set executable permissions
            if system != "Windows":
                st = os.stat(target_exe)
                os.chmod(target_exe, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            msg = QCoreApplication.translate("updater", f"yt-dlp has been updated to the latest version ({latest_version}).")
            return True, msg

        except PermissionError:
            # Binary is in use -> stage for next restart
            try:
                shutil.move(str(tmp_exe), str(pending_exe))
                msg = QCoreApplication.translate("updater", f"yt-dlp is currently in use. Update downloaded and will be applied on next app restart ({latest_version}).")
                return False, msg
            except Exception as e_move:
                try:
                    if tmp_exe.exists():
                        tmp_exe.unlink()
                except Exception:
                    pass
                msg = QCoreApplication.translate("updater", f"yt-dlp is in use and the update could not be staged: {e_move}")
                return False, msg

        except Exception:
            # Fallback: try shutil.move
            try:
                shutil.move(str(tmp_exe), str(target_exe))

                # Linux/macOS: Set executable permissions
                if system != "Windows":
                    st = os.stat(target_exe)
                    os.chmod(target_exe, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

                msg = QCoreApplication.translate("updater", f'yt-dlp has been updated to the latest version ({latest_version}).')
                return True, msg
            except PermissionError:
                try:
                    shutil.move(str(tmp_exe), str(pending_exe))
                    msg = QCoreApplication.translate("updater", f"yt-dlp is currently in use. Update downloaded and will be applied on next app restart ({latest_version}).")
                    return False, msg
                except Exception as e_move:
                    try:
                        if tmp_exe.exists():
                            tmp_exe.unlink()
                    except Exception:
                        pass
                    msg = QCoreApplication.translate("updater", f"yt-dlp is in use and the update could not be staged: {e_move}")
                    return False, msg
            except Exception as e_fallback:
                try:
                    if tmp_exe.exists():
                        tmp_exe.unlink()
                except Exception:
                    pass
                msg = QCoreApplication.translate("updater", f"Failed to replace yt-dlp: {e_fallback}")
                return False, msg

    except Exception as e:
        # Download failed or other unexpected error
        try:
            if tmp_exe.exists():
                tmp_exe.unlink()
        except Exception:
            pass
        msg = QCoreApplication.translate("updater", f"Failed to download new yt-dlp executable: {e}")
        return False, msg


# ====================================================================================
# CROSS-PLATFORM UPDATE MANAGEMENT
# ====================================================================================

def check_update_grace_period():
    """
    Check if macOS grace period has expired.
    Returns (expired: bool, days_remaining: int, first_notified: datetime | None)
    """
    if platform.system() != "Darwin":
        return False, 0, None

    if not config.update_first_notified:
        return False, config.update_grace_period_days, None

    try:
        # Parse the stored timestamp
        if isinstance(config.update_first_notified, str):
            first_notified = datetime.fromisoformat(config.update_first_notified)
        else:
            first_notified = config.update_first_notified

        now = datetime.now()
        days_passed = (now - first_notified).days
        days_remaining = config.update_grace_period_days - days_passed

        expired = days_remaining <= 0
        return expired, max(0, days_remaining), first_notified

    except Exception as e:
        log(f"Error checking grace period: {e}", log_level=3)
        return False, config.update_grace_period_days, None


def should_check_for_update():
    """
    Determine if we should check for updates based on frequency settings.
    Returns True if it's time to check for updates.
    """
    try:
        today = datetime.now()
        day_of_year = today.timetuple().tm_yday

        # Check if enough days have passed since last check
        days_since_check = day_of_year - config.last_update_check

        # Handle year rollover
        if days_since_check < 0:
            days_since_check = 366 + days_since_check

        return days_since_check >= config.update_frequency

    except Exception as e:
        log(f"Error checking update frequency: {e}", log_level=3)
        return True  # Default to checking if error occurs


def mark_update_checked():
    """Mark that we've checked for updates today."""
    try:
        today = datetime.now()
        config.last_update_check = today.timetuple().tm_yday

        # Import setting module to save
        from modules import setting
        setting.save_setting()
    except Exception as e:
        log(f"Error marking update check: {e}", log_level=3)


def start_grace_period(version: str):
    """
    Start the 7-day grace period for macOS update notification.

    Args:
        version: The version that triggered the grace period
    """
    if platform.system() != "Darwin":
        return

    try:
        # Only start grace period if not already started for this version
        if config.update_dismissed_version != version:
            config.update_first_notified = datetime.now().isoformat()
            config.update_dismissed_version = version

            from modules import setting
            setting.save_setting()

            log(f"Started {config.update_grace_period_days}-day grace period for version {version}", log_level=1)

    except Exception as e:
        log(f"Error starting grace period: {e}", log_level=3)


def reset_grace_period():
    """Reset the grace period (user updated or dismissed)."""
    try:
        config.update_first_notified = None
        config.update_dismissed_version = None

        from modules import setting
        setting.save_setting()

        log("Reset update grace period", log_level=2)

    except Exception as e:
        log(f"Error resetting grace period: {e}", log_level=3)


def get_platform_update_behavior():
    """
    Get update behavior based on platform.
    Returns: dict with update behavior settings
    """
    system = platform.system()

    if system == "Darwin":
        # macOS: Notification + 7-day grace period
        return {
            "platform": "macOS",
            "force_update": False,  # Never force immediately
            "grace_period_days": config.update_grace_period_days,
            "show_countdown": True,
            "block_on_expiry": True  # Block app after grace period
        }

    elif system == "Windows":
        # Windows: Existing behavior (prompt to update, scheduled task)
        return {
            "platform": "Windows",
            "force_update": False,
            "grace_period_days": 0,
            "show_countdown": False,
            "block_on_expiry": False,
            "use_scheduled_task": True
        }

    else:  # Linux and others
        # Linux: Similar to Windows but without scheduled tasks
        return {
            "platform": "Linux",
            "force_update": False,
            "grace_period_days": 0,
            "show_countdown": False,
            "block_on_expiry": False,
            "use_scheduled_task": False
        }


def compare_versions(current: str, latest: str) -> int:
    """
    Compare version strings.
    Returns: 1 if latest > current, 0 if equal, -1 if current > latest
    """
    try:
        # Normalize versions (remove 'v' prefix, split by '.')
        current = current.lstrip('v').strip()
        latest = latest.lstrip('v').strip()

        current_parts = [int(x) for x in current.split('.')]
        latest_parts = [int(x) for x in latest.split('.')]

        # Pad shorter version with zeros
        max_len = max(len(current_parts), len(latest_parts))
        current_parts += [0] * (max_len - len(current_parts))
        latest_parts += [0] * (max_len - len(latest_parts))

        # Compare parts
        for c, l in zip(current_parts, latest_parts):
            if l > c:
                return 1
            elif l < c:
                return -1

        return 0

    except Exception as e:
        log(f"Error comparing versions: {e}", log_level=3)
        return 0  # Assume equal on error


def check_for_updates_cross_platform():
    """
    Cross-platform update checker that respects platform-specific behavior.
    Returns: (has_update: bool, version: str, behavior: dict, grace_info: dict)
    """
    try:
        # Get latest version
        latest_version, _ = get_changelog()

        if not latest_version:
            log("Could not retrieve latest version", log_level=2)
            return False, None, None, None

        # Compare versions
        comparison = compare_versions(config.APP_VERSION, latest_version)
        has_update = comparison > 0

        if not has_update:
            log(f"App is up to date (current: {config.APP_VERSION}, latest: {latest_version})", log_level=2)
            return False, latest_version, None, None

        log(f"Update available: {config.APP_VERSION} → {latest_version}", log_level=1)

        # Get platform-specific behavior
        behavior = get_platform_update_behavior()

        # Check grace period (macOS only)
        grace_info = None
        if behavior["platform"] == "macOS":
            expired, days_remaining, first_notified = check_update_grace_period()

            grace_info = {
                "expired": expired,
                "days_remaining": days_remaining,
                "first_notified": first_notified,
                "total_days": config.update_grace_period_days
            }

            # If this is a new version, reset grace period
            if config.update_dismissed_version != latest_version:
                grace_info["is_new_version"] = True

        return has_update, latest_version, behavior, grace_info

    except Exception as e:
        log(f"Error checking for updates: {e}", log_level=3)
        return False, None, None, None