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
import json
import wget
import time
import httpx
import shutil
import zipfile
import tempfile
import subprocess
import py_compile
from pathlib import Path
from typing import Tuple
from modules import config
from datetime import datetime, timedelta
from PySide6.QtCore import QCoreApplication
from modules.utils import log, download, run_command, delete_folder, popup, _normalize_version_str


def get_changelog() -> Tuple[str | None, str | None]:
    """
    Returns (latest_version, contents) or (None, None) on failure.
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
        changelog_url = (
            assets.get("ChangeLog.txt") or
            "https://github.com/Annor-Gyimah/OmniPull/raw/refs/heads/master/Windows/ChangeLog.txt"
        )

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

        if not latest:
            log("Unable to parse latest version from GitHub response.", log_level=2)

        return latest, text

    except httpx.HTTPStatusError as e:
        log(f"GitHub API error: {e}", log_level=3)
        return config.APP_VERSION, None
    except httpx.RequestError as e:
        log(f"Network error while checking release: {e}", log_level=3)
        return config.APP_VERSION, None
    except Exception as e:
        log(f"Unexpected error in get_changelog: {e}", log_level=3)
        return config.APP_VERSION, None



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




def _safe_extract_all(zip_path: Path, dest_dir: Path):
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            target = dest_dir / member.filename
            # prevent zip slip
            if not str(target.resolve()).startswith(str(dest_dir.resolve())):
                raise RuntimeError(f"Unsafe path in zip: {member.filename}")
        zf.extractall(dest_dir)

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

def update():
    rel = get_app_latest_release()
    tag = rel["tag_name"].lstrip(".")
    # Prefer assets attached to the release:
    # e.g., look up 'main.zip', 'update.bat', 'cleanup.bat' in rel["assets"]
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    main_zip_url = assets.get("main.zip") or f"https://github.com/Annor-Gyimah/OmniPull/releases/download/{tag}/main.zip"
    update_cleanup_script_url = assets.get("update_and_cleanup.bat") or f"https://github.com/Annor-Gyimah/OmniPull/releases/download/{tag}/update_and_cleanup.bat"


    temp_dir = Path(tempfile.mkdtemp(prefix=".update_tmp_", dir=os.path.expanduser("~")))
    download_zip = temp_dir / "main.zip"
    update_cleanup_bat = Path(os.path.expanduser("~")) / "update_and_cleanup.bat"

    try:
        log("Downloading update files...", log_level=1)
        msg = QCoreApplication.translate('updater', 'Downloading updates. Please wait…')
        popup(title="Update", msg=f"{msg}", type_="info")

        # Download scripts with httpx (avoid mixing wget)
        download_with_resume(main_zip_url, download_zip, type_update_file='main.zip')
        log('')
        if os.path.exists(update_cleanup_script_url): os.remove(update_cleanup_bat)
        download_with_resume(update_cleanup_script_url, update_cleanup_bat, type_update_file='Update and Cleanup')

        log("Extracting update package…", log_level=1)
        _safe_extract_all(download_zip, temp_dir)
        exe_path = find_exe(temp_dir, "main.exe")
        log(f"Found executable: {exe_path}")

        # Schedule tasks – one-time run 5 minutes from now
        today = datetime.now()

        # Set time to 12:00 PM 
        when = today.replace(hour=12, minute=5, second=0, microsecond=0)

        # now = datetime.now()
        # when = now.replace(hour=1, minute=10, second=0, microsecond=0)
        # if now >= when:
        #     when += timedelta(days=1)

        schedule_one_shot_update(exe_path, temp_dir, when)

        ab = QCoreApplication.translate('updater', 'Update scheduled at')
        popup(title=config.APP_NAME, msg=f"{ab} {when.strftime('%Y-%m-%d %H:%M')}.", type_="info")
        config.confirm_update = True
    except Exception as e:
        config.confirm_update = False
        log(f"Update failed: {e}", log_level=3)
        uf = QCoreApplication.translate('updater', 'Update failed')
        de = QCoreApplication.translate('updater', 'Details:')
        ift = QCoreApplication.translate('updater', 'If this keeps happening, check your network and antivirus exclusions for')
        popup(
            msg=f"{uf}\n\n{de}\n{e}\n\n {ift} {config.APP_NAME}.",
            title=config.APP_NAME,
            type_="critical"
        )



def schedule_one_shot_update(exe_path: Path, temp_dir: Path, when: datetime):
    task_name = f"{config.APP_NAME}_UpdateOnce"
    st = when.strftime("%H:%M")
    sd = when.strftime("%Y/%m/%d")

    bat = Path(os.path.expanduser("~")) / "update_and_cleanup.bat"  # write or download this once

    subprocess.run(["powershell","-NoProfile","-Command", f"Unblock-File -LiteralPath '{bat}'"], check=True)

    # Action: run via cmd.exe for reliability; pass both args: exe and temp_dir
    tr = (
        f"\"%SystemRoot%\\System32\\cmd.exe\" /c "
        f"\"\"{bat}\" \"{exe_path}\" \"{temp_dir}\"\""
    )

    # Create one-shot task that self-deletes after run
    create = [
        "schtasks","/create",
        "/tn", task_name,
        "/tr", tr,
        "/sc", "daily",
        #"/sd", sd,
        "/st", st,
        "/rl", "HIGHEST",
        "/f"
    ]
    # Run as current user and prompt for password if you need “run when not logged on”:
    # create += ["/ru", os.getlogin(), "/rp", "*"]

    subprocess.run(
        ["powershell","-NoProfile","-Command",
         f"Start-Process -Verb RunAs cmd -ArgumentList '/c {subprocess.list2cmdline(create)}'"],
        shell=True, check=True
    )




def run_daily_task_now():
    task_name = f"{config.APP_NAME}_UpdateDaily"
    subprocess.run(
        ["powershell","-NoProfile","-Command",
         f"Start-Process cmd -ArgumentList '/c schtasks /run /tn \"{task_name}\"' -Verb RunAs"],
        shell=True, check=True
    )


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
    yt_dlp_path = getattr(config, "yt_dlp_exe", "") or config.yt_dlp_actual_path
    if not yt_dlp_path or not os.path.isfile(yt_dlp_path):
        # popup(
        #     msg="yt-dlp not set\nNo yt-dlp executable is configured.",
        #     title=config.APP_NAME,
        #     type_="critical"
        # )
        return False, "yt-dlp not set or not found."

    target_exe = Path(yt_dlp_path)
    tmp_exe = target_exe.with_suffix('.exe.tmp')
    pending_exe = target_exe.with_suffix('.exe.new')

    # get current version
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

    # get latest release info
    try:
        log('Checking for latest version')
        rel = get_ytdlp_latest_release()
        tag = rel.get("tag_name", "")
        latest_version = tag
        log(f'Latest version: {latest_version}')
    except Exception as e:
        return False, f"Failed to check latest yt-dlp version: {e}"

    if not latest_version or not current_version or latest_version.lstrip("v") == current_version.lstrip("v"):
        log(f'Current version: {current_version}')
        msg = QCoreApplication.translate("updater", "yt-dlp is up to date.")
        return False, msg
        # return False, "yt-dlp is up to date."

    # Download URL (your source)
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    exe_url = assets.get('yt-dlp.exe') or f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/yt-dlp.exe"
    log(f"Updating yt-dlp from {current_version} to {latest_version}", log_level=1)

    # ensure any leftover tmp file is removed (optional)
    try:
        if tmp_exe.exists():
            tmp_exe.unlink()
    except Exception:
        pass

    try:
        # download to tmp file first
        download_with_resume(exe_url, tmp_exe, type_update_file='yt-dlp.exe')

        # Attempt to atomically replace (preferred)
        try:
            # os.replace is atomic on same filesystem
            os.replace(str(tmp_exe), str(target_exe))
            msg = QCoreApplication.translate("updater", f"yt-dlp has been updated to the latest version ({latest_version}).")
            return True, msg

        except PermissionError:
            # target EXE is in use -> move tmp to .exe.new (pending)
            try:
                shutil.move(str(tmp_exe), str(pending_exe))
            except Exception as e_move:
                # if move fails, try to clean tmp and return a failure
                try:
                    if tmp_exe.exists():
                        tmp_exe.unlink()
                except Exception:
                    pass
                msg = QCoreApplication.translate("updater", f"yt-dlp is in use and the update could not be staged: {e_move}")
                return False, f"{msg}"
            # success: staged update for next restart
            msg = QCoreApplication.translate("updater", f"yt-dlp is currently in use. Update downloaded and will be applied on next app restart ({latest_version}).")
            return False, msg
        except Exception:
            # fallback: try shutil.move as a last attempt
            try:
                shutil.move(str(tmp_exe), str(target_exe))
                msg = QCoreApplication.translate("updater", f'yt-dlp has been updated to the latest version ({latest_version}).')
                return True, msg
            except PermissionError:
                # same as above: move to pending
                try:
                    shutil.move(str(tmp_exe), str(pending_exe))
                except Exception as e_move:
                    try:
                        if tmp_exe.exists():
                            tmp_exe.unlink()
                    except Exception:
                        pass
                    msg = QCoreApplication.translate("updater", f"yt-dlp is in use and the update could not be staged: {e_move}")
                    return False, msg
                msg = QCoreApplication.translate("updater", f"yt-dlp is currently in use. Update downloaded and will be applied on next app restart ({latest_version}).")
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
        # download failed or other unexpected error
        try:
            if tmp_exe.exists():
                tmp_exe.unlink()
        except Exception:
            pass
        msg = QCoreApplication.translate("updater", f"Failed to download new yt-dlp executable: {e}")
        return False, msg