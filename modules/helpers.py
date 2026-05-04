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


import re
import os
import sys
import glob
import json
import ctypes
import shutil


import platform
import mimetypes
from pathlib import Path
from threading import Thread
from datetime import datetime
from typing import Tuple, Dict


from modules.config import Status
from modules.utils import log
from modules.updater import detect_install_mode

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QPixmap, QImage, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox


from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtCore import QFileInfo



def change_cursor(cursor_type: str):
    """Change cursor to busy or normal."""
    if cursor_type == 'busy':
        QApplication.setOverrideCursor(Qt.WaitCursor)  # Busy cursor
    elif cursor_type == 'normal':
        QApplication.restoreOverrideCursor()  # Restore normal cursor


# --- Windows imports ---
if platform.system() == "Windows":
    import win32gui # type: ignore
    import win32ui # type: ignore
    import winreg
    from ctypes import Structure, c_void_p, c_wchar, c_uint, c_int, sizeof, byref, windll

    class SHFILEINFO(Structure):
        _fields_ = [
            ("hIcon", c_void_p),
            ("iIcon", c_int),
            ("dwAttributes", c_uint),
            ("szDisplayName", c_wchar * 260),
            ("szTypeName", c_wchar * 80)
        ]
    shell32 = windll.shell32
    FILE_ATTRIBUTE_NORMAL = 0x80
    SHGFI_ICON = 0x000000100
    SHGFI_LARGEICON = 0x000000000
    SHGFI_USEFILEATTRIBUTES = 0x10

# --- macOS imports ---
if platform.system() == "Darwin":
    import objc  # type: ignore
    from AppKit import NSWorkspace # type: ignore



def get_file_icon(extension):
    # Create a dummy file info to trick the provider into giving us the icon for that type
    icon_provider = QFileIconProvider()
    
    # We create a temporary empty file name with the extension
    dummy_file = QFileInfo(f"dummy{extension}")
    icon = icon_provider.icon(dummy_file)
    
    # Request a high-resolution pixmap (e.g., 256px)
    # Qt will automatically give you the best quality available on the system
    return icon.pixmap(256, 256)


# ============================================================================
# TABLE & UI UTILITIES
# ============================================================================

def get_progress_bar_color(status: str) -> str:
    """Map download status to color hex code."""
    status_colors = {
        "downloading": "#2962FF",
        "completed": "#00C853",
        "cancelled": "#D32F2F",
        "pending": "#FDD835",
        "error": "#9E9E9E",
        "merging_audio": "#FF9800",
        "scheduled": "#F7DC6F",
        "queued": "#9C27B0",
    }
    return status_colors.get(status, "#00C853")



def calculate_total_speed(d_list: list, active_ids: set) -> int:
    """Calculate total download speed from active download IDs."""
    try:
        return sum(d.speed for d in d_list if d.id in active_ids)
    except Exception:
        return 0


def build_download_lookup(d_list: list) -> Dict[int, int]:
    """Create ID -> list index mapping for O(1) lookups."""
    return {d.id: i for i, d in enumerate(d_list)}


def find_download_by_id(d_list: list, download_id: int):
    """Find download by ID (returns first match or None)."""
    try:
        return next((x for x in d_list if x.id == download_id), None)
    except Exception:
        return None


def filter_downloads_by_status(d_list: list, *statuses: str) -> list:
    """Return list of downloads matching any of the given statuses."""
    return [d for d in d_list if d.status in statuses]

def toolbar_buttons_state(status: str) -> dict:
    status_map = {
        Status.completed: {
            "Add Download": True,
            "Resume": False,
            "Pause": False,
            "Delete": True,
            "Delete All": True,
            "Refresh": True,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": False,
            "Settings": True,
            "Download Window": False,
        },
        Status.cancelled: {
            "Add Download": True,
            "Resume": True,
            "Pause": False,
            "Delete": True,
            "Delete All": True,
            "Refresh": True,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": True,
            "Settings": True,
            "Download Window": False,
        },
        Status.error: { 
            "Add Download": True,
            "Resume": True,
            "Pause": False,
            "Delete": True,
            "Delete All": True,
            "Refresh": True,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": False,
            "Settings": True,
            "Download Window": False,
        },
        Status.paused: {
            "Add Download": True,
            "Resume": True,
            "Pause": False,
            "Delete": True,
            "Delete All": True,
            "Refresh": True,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": False,
            "Settings": True,
            "Download Window": False,
        },  
        Status.failed: {
            "Add Download": True,
            "Resume": True,
            "Pause": False,
            "Delete": True,
            "Delete All": True,
            "Refresh": True,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": False,
            "Settings": True,
            "Download Window": False,
        }, 
        Status.deleted: {
            "Add Download": True,
            "Resume": False,
            "Pause": False,
            "Delete": True,
            "Delete All": True,
            "Refresh": True,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": False,
            "Settings": True,
            "Download Window": False,
        },
        Status.scheduled: {
            "Add Download": True,
            "Resume": False,
            "Pause": False,
            "Delete": True,
            "Delete All": True,
            "Refresh": True,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": False,
            "Settings": True,
            "Download Window": False,
        },
        Status.downloading: {
            "Add Download": True,
            "Resume": False,
            "Pause": True,
            "Delete": False,
            "Delete All": True,
            "Refresh": False,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": False,
            "Settings": True,
            "Download Window": True,
        },
        Status.pending: {
            "Add Download": True,
            "Resume": False,
            "Pause": True,
            "Delete": False,
            "Delete All": True,
            "Refresh": False,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": False,
            "Settings": True,
            "Download Window": False,
        },
        Status.merging_audio: {
            "Add Download": True,
            "Resume": False,
            "Pause": False,
            "Delete": False,
            "Delete All": True,
            "Refresh": False,
            "Resume All": False,
            "Stop All": False,
            "Schedule All": False,
            "Settings": True,
            "Download Window": False,
        },
    }

    return status_map.get(status, {})



# ============================================================================
# FILE OPERATIONS
# ============================================================================

def validate_destination_folder(folder: str) -> Tuple[bool, str]:
    """
    Test folder write permissions. 
    Returns (success: bool, error_msg: str).
    """
    try:
        test_path = os.path.join(folder, 'test')
        with open(test_path, 'w') as f:
            f.write('0')
        os.unlink(test_path)
        return True, ""
    except FileNotFoundError:
        return False, f"Folder does not exist: {folder}"
    except PermissionError:
        return False, f"No write permission: {folder}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def safe_file_remove(filepath: str) -> bool:
    """Safely remove file, return True if successful."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            return True
    except Exception as e:
        log(f"Failed to remove {filepath}: {e}", log_level=2)
    return False


def safe_file_exists(filepath: str) -> bool:
    """Check file existence safely (returns False on error)."""
    try:
        return bool(filepath and os.path.exists(filepath))
    except Exception:
        return False


def safe_filename(name):
    """Sanitize filename to remove problematic characters."""
    name = re.sub(r'[\\/*?:"<>|]', "_", name)  # Remove bad chars
    return name.strip()


def open_with_dialog_windows(self, file_path):
    """Trigger native 'Open With...' dialog on Windows using ShellExecuteEx"""
    SEE_MASK_INVOKEIDLIST = 0x0000000C
    ShellExecuteEx = ctypes.windll.shell32.ShellExecuteExW

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("fMask", ctypes.c_ulong),
            ("hwnd", ctypes.c_void_p),
            ("lpVerb", ctypes.c_wchar_p),
            ("lpFile", ctypes.c_wchar_p),
            ("lpParameters", ctypes.c_wchar_p),
            ("lpDirectory", ctypes.c_wchar_p),
            ("nShow", ctypes.c_int),
            ("hInstApp", ctypes.c_void_p),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", ctypes.c_wchar_p),
            ("hkeyClass", ctypes.c_void_p),
            ("dwHotKey", ctypes.c_ulong),
            ("hIcon", ctypes.c_void_p),
            ("hProcess", ctypes.c_void_p),
        ]

    execute_info = SHELLEXECUTEINFO()
    execute_info.cbSize = ctypes.sizeof(execute_info)
    execute_info.fMask = SEE_MASK_INVOKEIDLIST
    execute_info.hwnd = None
    execute_info.lpVerb = "openas"
    execute_info.lpFile = file_path
    execute_info.lpParameters = None
    execute_info.lpDirectory = None
    execute_info.nShow = 1
    execute_info.hInstApp = None

    result = ShellExecuteEx(ctypes.byref(execute_info))
    return result

def _pick_container_from_video(video_path: str) -> str:
    ext = os.path.splitext(video_path)[1].lower().lstrip('.')
    # Favor mp4/mkv if uncertain. WebM video + m4a audio → mkv is safest for stream copy.
    if ext in ('mp4', 'm4v', 'mov'):
        return 'mp4'
    if ext in ('webm',):
        return 'mkv'
    if ext in ('mkv', 'ts'):
        return 'mkv'
        # default
        return 'mp4'
    
def _norm_title(s: str) -> str:
    """
    Normalize a title for robust filename matching:
    - strip path + extension
    - lower
    - replace non-alnum with single underscore
    - collapse multiple underscores
    - trim underscores
    """
    base = os.path.splitext(os.path.basename(s))[0]
    base = base.lower()
    base = re.sub(r'[^a-z0-9]+', '_', base)
    base = re.sub(r'_+', '_', base).strip('_')
    return base

def _extract_title_from_pattern(filename: str, prefix: str) -> str | None:
    """
    Given a filename and a known prefix ('_temp_' or 'audio_for_'),
    return the normalized <TITLE> portion if it follows the pattern.
    """
    base = os.path.splitext(os.path.basename(filename))[0]
    if not base.startswith(prefix):
        return None
    title_raw = base[len(prefix):]
    return _norm_title(title_raw)

def _expected_paths(folder: str, title_norm: str):
    # Allowed containers/codecs for stream-copy merges
    video_exts = ('mp4', 'm4v', 'mov', 'webm', 'mkv', 'ts')
    audio_exts = ('m4a', 'mp4', 'aac', 'webm', 'opus', 'mp3', 'wav')  # include common audio
    video_candidates = [os.path.join(folder, f"_temp_{title_norm}.{ext}") for ext in video_exts]
    audio_candidates = [os.path.join(folder, f"audio_for_{title_norm}.{ext}") for ext in audio_exts]
    return video_candidates, audio_candidates

def _best_existing(paths: list[str]) -> str | None:
    # Pick the first existing path, else None
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def janitor(d):
    """Delete all related files of the download item (aria2c, yt-dlp, curl, .torrent, temp, parts dirs, etc.) WITHOUT touching unrelated folders/files."""
    
    def _log_ok(msg):  log(msg)
    def _log_err(msg): log(msg, log_level=2)

    def _rm_file(path):
        try:
            if path and os.path.isfile(path) and os.path.exists(path):
                os.remove(path)
                _log_ok(f"[Janitor] Removed file: {path}")
        except Exception as e:
            _log_err(f"[Janitor] Failed to remove file: {path} ({e})")

    def _rm_glob(pattern):
        for p in glob.glob(pattern):
            _rm_file(p)

    def _rmtree(path):
        try:
            if path and os.path.isdir(path) and os.path.exists(path):
                shutil.rmtree(path, ignore_errors=False)
                _log_ok(f"[Janitor] Removed directory: {path}")
        except Exception as e:
            _log_err(f"[Janitor] Failed to remove directory: {path} ({e})")

    def _norm_title(s: str) -> str:
        base = os.path.splitext(os.path.basename(s))[0]
        base = base.lower()
        base = re.sub(r'[^a-z0-9]+', '_', base)
        base = re.sub(r'_+', '_', base).strip('_')
        return base

    def _belongs_to_stem(name: str, stems_norm: set[str]) -> bool:
        """Return True iff the filename/dirname (sans-ext, normalized) looks like it's for this item."""
        n = _norm_title(name)
        # exact or prefix/suffix relation (covers _temp_<stem>... and ...<stem>_parts_)
        return any(n == s or n.startswith(s + "_") or n.endswith("_" + s) or s in n for s in stems_norm)

    try:
        # --- 0) Build roots and stems -----------------------------------------
        main_file = os.path.join(d.folder, d.name)

        # Folders to search (only where this item actually wrote files)
        roots = set()
        for base in [
            main_file,
            getattr(d, "temp_file", ""),
            getattr(d, "audio_file", ""),
            getattr(d, "target_file", ""),
        ]:
            if base:
                roots.add(os.path.dirname(base) or d.folder)
        temp_folder = getattr(d, "temp_folder", None)
        if temp_folder:
            roots.add(temp_folder)

        # Stems (with/without ext) + normalized variants
        stems_raw = set()
        for base in [main_file, getattr(d, "temp_file", ""), getattr(d, "audio_file", ""), getattr(d, "target_file", "")]:
            if not base:
                continue
            fname = os.path.basename(base)       # e.g. "Title.mp4"
            stem_noext, _ext = os.path.splitext(fname)
            stems_raw.add(fname)                 # with ext
            stems_raw.add(stem_noext)            # without ext

        stems_norm = { _norm_title(s) for s in stems_raw if s }

        # --- 1) Let the item clear its tempfiles first ------------------------
        try:
            d.delete_tempfiles()
        except Exception as e:
            _log_err(f"[Janitor] delete_tempfiles() failed: {e}")

        # --- 2) Remove primary files ------------------------------------------
        _rm_file(main_file)
        for base in [getattr(d, "target_file", ""), getattr(d, "temp_file", ""), getattr(d, "audio_file", "")]:
            if base and os.path.abspath(base) != os.path.abspath(main_file):
                _rm_file(base)

        # --- 3) aria2c sidecars ------------------------------------------------
        aria_suffixes_exact = [".aria2", ".aria2.resume", ".aria2.log", ".meta", ".mtd"]
        for root in list(roots):
            for stem in list(stems_raw):
                for suf in aria_suffixes_exact:
                    _rm_file(os.path.join(root, f"{stem}{suf}"))
                _rm_glob(os.path.join(root, f"{stem}.aria2*"))
                _rm_glob(os.path.join(root, f"{stem}.mtd*"))
                _rm_glob(os.path.join(root, f"{stem}.meta*"))

        # --- 4) yt-dlp artifacts (strict to stems) -----------------------------
        yt_suffix_patterns = [
            ".part", ".part-*", ".f*", ".ytdl", ".ytdl-part", ".ytdl.*",
            ".info", ".info.json", ".description", ".annotations.xml",
            ".thumb", ".jpg", ".jpeg", ".png", ".webp",
            ".srt", ".vtt", ".lrc",
        ]
        for root in list(roots):
            for stem in list(stems_raw):
                for suf in yt_suffix_patterns:
                    _rm_glob(os.path.join(root, f"{stem}{suf}"))

        # --- 5) STRICT temp/parts folders (only if they BELONG to this item) ---
        # Allowed folder name forms to try for each stem (raw + normalized)
        #   _temp_<stem>..._parts_   (curl style)
        #   <stem>_parts_
        #   <stem>.temp
        #   <stem>_temp
        for root in list(roots):
            # Scan only directories in root and test them against stems_norm
            try:
                entries = [e for e in glob.glob(os.path.join(root, "*")) if os.path.isdir(e)]
            except Exception:
                entries = []

            for dpath in entries:
                dname = os.path.basename(dpath)
                if not _belongs_to_stem(dname, stems_norm):
                    continue  # skip unrelated directories

                # Safety: if dir contains files that clearly don't belong to this stem, skip deletion
                try:
                    foreign = False
                    for p in glob.glob(os.path.join(dpath, "**"), recursive=True):
                        if os.path.isdir(p):
                            continue
                        base = os.path.basename(p)
                        if not _belongs_to_stem(base, stems_norm):
                            foreign = True
                            break
                    if foreign:
                        continue
                except Exception:
                    # if we can't scan, fall back to delete (you can change to 'continue' if you prefer ultra-safety)
                    pass

                _rmtree(dpath)

        # --- 6) .watch helper files -------------------------------------------
        for root in list(roots):
            for stem in list(stems_raw):
                _rm_file(os.path.join(root, f"{stem}.watch"))
                _rm_glob(os.path.join(root, f"{stem}.watch.*"))

        # --- 7) .torrent cleanup ----------------------------------------------
        for root in list(roots):
            for stem in list(stems_raw):
                _rm_file(os.path.join(root, f"{stem}.torrent"))
                _rm_glob(os.path.join(root, f"{stem}.torrent.*"))

        if main_file.lower().endswith(".torrent"):
            _rm_file(main_file)
            paired = main_file[:-8]  # remove ".torrent"
            _rm_file(paired)

        # --- 8) Generic loose leftovers (strict to stems) ---------------------
        loose_suffixes = [".tmp", ".temp", ".download", ".opdownload"]
        for root in list(roots):
            for stem in list(stems_raw):
                for suf in loose_suffixes:
                    _rm_file(os.path.join(root, f"{stem}{suf}"))

        _log_ok(f"[Janitor] Cleanup completed for: {d.name}")

    except Exception as e:
        log(f"[Janitor] General error cleaning up files for {getattr(d, 'name', '?')}: {e}", log_level=3)



# ============================================================================
# DOWNLOAD SEARCH UTILITIES
# ============================================================================

def find_matching_download(d_list: list, name: str, folder: str):
    """
    Find download by name + folder normalization.
    Useful for resume detection.
    """
    try:
        norm_folder = os.path.normpath(folder or "")
        for d in d_list:
            d_folder = os.path.normpath(d.folder or "")
            if d.name == name and d_folder == norm_folder:
                return d
    except Exception:
        pass
    return None


def find_by_temp_file(d_list: list, temp_file: str):
    """Find download by temp_file path."""
    try:
        for d in d_list:
            if getattr(d, 'temp_file', None) == temp_file:
                return d
    except Exception:
        pass
    return None


def find_by_target_file(d_list: list, target_file: str):
    """Find download by target_file path."""
    try:
        for d in d_list:
            if getattr(d, 'target_file', None) == target_file:
                return d
    except Exception:
        pass
    return None

def get_ext_from_format(fmt: dict):
    ext = fmt.get("ext")
    if not ext:
        mime = fmt.get("mime_type", "")
        if "mp4" in mime:
            ext = "mp4"
        elif "webm" in mime:
            ext = "webm"
        else:
            ext = "mp4"
    return ext


# ============================================================================
# SETTINGS & SERIALIZATION
# ============================================================================

def load_json_safe(filepath: str, default=None):
    """
    Load JSON file safely without blocking UI.
    Returns default on any error.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        log(f"Invalid JSON in {filepath}", log_level=2)
        return default
    except Exception as e:
        log(f"Failed to load {filepath}: {e}", log_level=2)
        return default


def save_json_background(filepath: str, data: dict):
    """
    Save JSON file in background thread to avoid UI blocking.
    """
    def _save():
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log(f"Failed to save {filepath}: {e}", log_level=2)
    
    Thread(target=_save, daemon=True).start()


# ============================================================================
# DOWNLOAD STATISTICS
# ============================================================================

def get_today_download_stats(d_list: list) -> Tuple[int, int]:
    """
    Calculate downloads started today and completed today.
    Returns (total_today, completed_today).
    """
    try:
        today = datetime.now().date()
        total_today = 0
        completed_today = 0
        
        for d in d_list:
            last_try = getattr(d, 'last_try_date', None)
            if not last_try:
                continue
            
            # Try parsing different formats
            dt = None
            try:
                dt = datetime.strptime(last_try, "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    dt = datetime.fromisoformat(last_try)
                except Exception:
                    continue
            
            if dt and dt.date() == today:
                total_today += 1
                if getattr(d, 'status', None) == Status.completed:
                    completed_today += 1
        
        return total_today, completed_today
    except Exception as e:
        log(f"get_today_download_stats error: {e}", log_level=3)
        return 0, 0


def count_downloads_by_status(d_list: list, status: str) -> int:
    """Count downloads with a specific status."""
    try:
        return sum(1 for d in d_list if d.status == status)
    except Exception:
        return 0


# ============================================================================
# QUEUE UTILITIES
# ============================================================================

def get_queue_items(d_list: list, queue_id: str) -> list:
    """Get all queued items for a specific queue ID."""
    try:
        return [
            d for d in d_list 
            if getattr(d, 'in_queue', False) 
            and getattr(d, 'queue_id', None) == queue_id
            and d.status == Status.queued
        ]
    except Exception:
        return []


def get_next_queue_position(d_list: list, queue_name: str) -> int:
    """Calculate next available position in queue."""
    try:
        positions = [
            item.queue_position for item in d_list
            if getattr(item, 'in_queue', False) 
            and getattr(item, 'queue_name', None) == queue_name
        ]
        return max(positions, default=0) + 1
    except Exception:
        return 1



# ============================================================================
# MESSAGE UTILITIES
# ============================================================================

def get_tr(parent, text):
    """Helper to safely get translation even if parent is None."""
    if parent:
        return parent.tr(text)
    # Fallback to global translation if no parent is provided
    return QCoreApplication.translate("helper", text)

def show_information(parent=None, title="", inform="", msg=""):
    information_box = QMessageBox(parent)
    information_box.setStyleSheet(get_msgbox_style("information"))
    information_box.setIcon(QMessageBox.Information)
    
    information_box.setWindowTitle(title)
    information_box.setText(msg)
    information_box.setInformativeText(inform)

    # Manual button translation
    ok_btn = information_box.addButton(QMessageBox.Ok)
    ok_btn.setText(get_tr(parent, "OK"))
    
    information_box.exec()

def show_critical(parent=None, title="", msg=""):
    critical_box = QMessageBox(parent)
    critical_box.setStyleSheet(get_msgbox_style("critical"))
    critical_box.setIcon(QMessageBox.Critical)
    
    critical_box.setWindowTitle(title)
    critical_box.setText(msg)

    # Manual button translation
    ok_btn = critical_box.addButton(QMessageBox.Ok)
    ok_btn.setText(get_tr(parent, "OK"))
    
    critical_box.exec()

def show_warning(parent=None, title="", msg=""):
    warning_box = QMessageBox(parent)
    warning_box.setStyleSheet(get_msgbox_style("warning"))
    warning_box.setIcon(QMessageBox.Warning)
    
    warning_box.setWindowTitle(title)
    warning_box.setText(msg)

    # Manual button translation
    ok_btn = warning_box.addButton(QMessageBox.Ok)
    ok_btn.setText(get_tr(parent, "OK"))
    
    warning_box.exec()


def get_msgbox_style(msg_type: str) -> str:
    from modules import config
    
    if getattr(config, 'current_theme', 'Dark'):
        bg = getattr(config, 'bg_color_dark', '#14161a')
    else:
        bg = getattr(config, 'bg_color_dark', '#f4f5f7')
    menu_bg = getattr(config, 'menu_bg', '#1f2227')
    toolbar_bg = getattr(config, 'toolbar_bg', '#1b1e23')
    text = getattr(config, 'text_color', '#e8eaed')
    accent = getattr(config, 'accent_color', '#2b80ff')
    progress_col = getattr(config, 'progress_color', accent)

    base_style = """

    QMessageBox {
        
        color: white;
        font-family: 'Segoe UI';
        font-size: 13px;
        border-radius: 12px;
    }
        
    """

    button_styles = {
        "critical": f"""
            QPushButton {{
                background: #2a2d31;
                color: white;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:default {{
                border: 1px solid {accent};
                color: #bfe0ff;
            }}
        """,
        "warning": f"""
            QPushButton {{
                background: #2a2d31;
                color: white;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:default {{
                border: 1px solid {accent};
                color: #bfe0ff;
            }}
        """,
        "information":f"""
            QPushButton {{
                background: #2a2d31;
                color: white;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:default {{
                border: 1px solid {accent};
                color: #bfe0ff;
            }}
        """,
        "inputdial": f"""

            QInputDialog {{
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                );
                color: white;
                font-family: 'Segoe UI';
                font-size: 13px;
                border-radius: 12px;
            }}
            QLabel {{
                color: white;
            }}
            QLineEdit {{
                background-color: rgba(28, 28, 30, 0.55);  /* Neutral frosted charcoal */
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 6px 10px;
            }}
            QPushButton {{
                background: #2a2d31;
                color: white;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:default {{
                border: 1px solid {accent};
                color: #bfe0ff;
            }}
        """,
        "conflict": f"""
            QPushButton {{
                background: #2a2d31;
                color: white;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:default {{
                border: 1px solid {accent};
                color: #bfe0ff;
            }}
        """,
        "overwrite": f"""
            QPushButton {{
                background: #2a2d31;
                color: white;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:default {{
                border: 1px solid {accent};
                color: #bfe0ff;
            }}
        """,
        "question": f"""
            QPushButton {{
                background: #2a2d31;
                color: white;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:default {{
                border: 1px solid {accent};
                color: #bfe0ff;
            }}


        """


    }

    return base_style + button_styles.get(msg_type, "")

# Full translation map for category_list items
CATEGORY_TRANSLATIONS = {
    "All Downloads": {
        "French": "Tous les téléchargements",
        "Spanish": "Todas las descargas",
        "Korean": "모든 다운로드",
        "Japanese": "すべてのダウンロード",
        "Chinese": "所有下载",
        "Hindi": "सभी डाउनलोड",
        "Russian": "Все загрузки"
    },
    "Completed": {
        "French": "Terminés",
        "Spanish": "Completadas",
        "Korean": "완료됨",
        "Japanese": "完了",
        "Chinese": "已完成",
        "Hindi": "पूर्ण",
        "Russian": "Завершенные"
    },
    "Cancelled": {
        "French": "Annulés",
        "Spanish": "Canceladas",
        "Korean": "취소됨",
        "Japanese": "キャンセル済み",
        "Chinese": "已取消",
        "Hindi": "रद्द किया गया",
        "Russian": "Отмененные"
    },
    "Downloading": {
        "French": "Téléchargement",
        "Spanish": "Descargando",
        "Korean": "다운로드 중",
        "Japanese": "ダウンロード中",
        "Chinese": "下载中",
        "Hindi": "डाउनलोड हो रहा है",
        "Russian": "Загрузка"
    },
    "Queued": {
        "French": "En file d’attente",
        "Spanish": "En cola",
        "Korean": "대기 중",
        "Japanese": "キュー待ち",
        "Chinese": "排队中",
        "Hindi": "कतारबद्ध",
        "Russian": "В очереди"
    },
    "Paused": {
        "French": "En pause",
        "Spanish": "En pausa",
        "Korean": "일시중지됨",
        "Japanese": "一時停止中",
        "Chinese": "已暂停",
        "Hindi": "विराम दिया गया",
        "Russian": "Приостановленные"
    },
    "Error": {
        "French": "Erreur",
        "Spanish": "Error",
        "Korean": "오류",
        "Japanese": "エラー",
        "Chinese": "错误",
        "Hindi": "त्रुटि",
        "Russian": "Ошибки"
    },
    "General": {
        "French": "Général",
        "Spanish": "General",
        "Korean": "일반",
        "Japanese": "一般",
        "Chinese": "常规",
        "Hindi": "सामान्य",
        "Russian": "Общие"
    },
    "Compressed": {
        "French": "Compressé",
        "Spanish": "Comprimidos",
        "Korean": "압축됨",
        "Japanese": "圧縮済み",
        "Chinese": "压缩",
        "Hindi": "संकुचित",
        "Russian": "Сжатые"
    },
    "Documents": {
        "French": "Documents",
        "Spanish": "Documentos",
        "Korean": "문서",
        "Japanese": "ドキュメント",
        "Chinese": "文档",
        "Hindi": "दस्तावेज़",
        "Russian": "Документы"
    },
    "Music": {
        "French": "Musique",
        "Spanish": "Música",
        "Korean": "음악",
        "Japanese": "音楽",
        "Chinese": "音乐",
        "Hindi": "संगीत",
        "Russian": "Музыка"
    },
    "Video": {
        "French": "Vidéo",
        "Spanish": "Video",
        "Korean": "비디오",
        "Japanese": "ビデオ",
        "Chinese": "视频",
        "Hindi": "वीडियो",
        "Russian": "Видео"
    },
    "Programs": {
        "French": "Programmes",
        "Spanish": "Programas",
        "Korean": "프로그램",
        "Japanese": "プログラム",
        "Chinese": "程序",
        "Hindi": "कार्यक्रम",
        "Russian": "Программы"
    }
}

FILE_PROPERTIES_TRANSLATIONS = {
    "Name:": {
        "Englis": "Name :",
        "French": "Nom :",
        "Spanish": "Nombre:",
        "Korean": "이름:",
        "Japanese": "名前:",
        "Chinese": "名称:",
        "Hindi": "नाम:",
        "Russian": "Имя:"
    },
    "Folder:": {
        "English": "Folder :",
        "French": "Dossier :",
        "Spanish": "Carpeta:",
        "Korean": "폴더:",
        "Japanese": "フォルダー:",
        "Chinese": "文件夹:",
        "Hindi": "फ़ोल्डर:",
        "Russian": "Папка:"
    },
    "Download engine:": {
        "English": "Download engine :",
        "French": "Moteur de téléchargement :",
        "Spanish": "Motor de descarga:",
        "Korean": "다운로드 엔진:",
        "Japanese": "ダウンロードエンジン:",
        "Chinese": "下载引擎:",
        "Hindi": "डाउनलोड इंजन:",
        "Russian": "Движок загрузки:"
    },
    "Progress:": {
        "English": "Progress :",
        "French": "Progression :",
        "Spanish": "Progreso:",
        "Korean": "진행률:",
        "Japanese": "進行状況:",
        "Chinese": "进度:",
        "Hindi": "प्रगति:",
        "Russian": "Прогресс:"
    },
    "Downloaded:": {
        "English": "Downloaded :",
        "French": "Téléchargé :",
        "Spanish": "Descargado:",
        "Korean": "다운로드됨:",
        "Japanese": "ダウンロード済み:",
        "Chinese": "已下载:",
        "Hindi": "डाउनलोड हुआ:",
        "Russian": "Загружено:"
    },
    "Total size:": {
        "English": "Total size:",
        "French": "Taille totale :",
        "Spanish": "Tamaño total:",
        "Korean": "전체 크기:",
        "Japanese": "合計サイズ:",
        "Chinese": "总大小:",
        "Hindi": "कुल आकार:",
        "Russian": "Общий размер:"  
    },
    "Status:": {
        "English": "Status:",
        "French": "Statut :",
        "Spanish": "Estado:",
        "Korean": "상태:",
        "Japanese": "ステータス:",
        "Chinese": "状态:",
        "Hindi": "स्थिति:",
        "Russian": "Статус:"
    },
    "Resumable:": {
        "English": "Resumable:",
        "French": "Reprise possible :",
        "Spanish": "Reanudable:",
        "Korean": "재개 가능:",
        "Japanese": "再開可能:",
        "Chinese": "可续传:",
        "Hindi": "पुनः आरंभ योग्य:",
        "Russian": "Можно возобновить:"
    },
    "Type:": {
        "English": "Type:",
        "French": "Type :",
        "Spanish": "Tipo:",
        "Korean": "종류:",
        "Japanese": "種類:",
        "Chinese": "类型:",
        "Hindi": "प्रकार:",
        "Russian": "Тип:"
    },
    "Protocol:": {
        "English": "Protocol:",
        "French": "Protocole :",
        "Spanish": "Protocolo:",
        "Korean": "프로토콜:",
        "Japanese": "プロトコル:",
        "Chinese": "协议:",
        "Hindi": "प्रोटोकॉल:",
        "Russian": "Протокол:"
    },
    "Webpage URL:": {
        "English": "Webpage URL:",
        "French": "URL de la page :",
        "Spanish": "URL de la página:",
        "Korean": "웹페이지 URL:",
        "Japanese": "ウェブページ URL:",
        "Chinese": "网页 URL:",
        "Hindi": "वेबपृष्ठ URL:",
        "Russian": "URL страницы:"
    },
    "Yes": {
        "English": "Yes",
        "French": "Oui",
        "Spanish": "Sí",
        "Korean": "예",
        "Japanese": "はい",
        "Chinese": "是",
        "Hindi": "हाँ",
        "Russian": "Да"
    },
    "No": {
        "English": "No",
        "French": "Non",
        "Spanish": "No",
        "Korean": "아니오",
        "Japanese": "いいえ",
        "Chinese": "否",
        "Hindi": "नहीं",
        "Russian": "Нет"
    },
    "Close": {
        "English": "Close",
        "French": "Fermer",
        "Spanish": "Cerrar",
        "Korean": "닫기",
        "Japanese": "閉じる",
        "Chinese": "关闭",
        "Hindi": "बंद करें",
        "Russian": "Закрыть"
    }
}


def nuclear_scrub():
    """
    Checks for PyInstaller environment poisoning and forces a clean restart.
    Must be called before any heavy imports (like PyQt6).
    """
    if getattr(sys, 'frozen', False):
        current_mei = getattr(sys, '_MEIPASS', None)
        env_mei = os.environ.get("_MEIPASS")
        
        # If the environment variable is pointing to a different folder than 
        # the one this specific EXE extracted to, we are poisoned.
        if env_mei and env_mei != current_mei:
            # Rebuild a 'Safe' environment block
            safe_keys = [
                "SYSTEMROOT", "PATH", "TEMP", "TMP", "APPDATA", 
                "LOCALAPPDATA", "USERPROFILE", "USERNAME", "COMPUTERNAME", 
                "COMSPEC", "SYSTEMDRIVE", "PROGRAMFILES", "PROGRAMFILES(X86)"
            ]
            
            # Filter the current environment
            new_env = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}
            
            # Ensure _MEIPASS is physically removed from the restart env
            new_env.pop("_MEIPASS", None)
            new_env.pop("_MEIPASS2", None)

            # Force an immediate restart with the clean environment
            # os.execve replaces the current process - no need for sys.exit()
            os.execve(sys.executable, [sys.executable] + sys.argv[1:], new_env)




def update_native_manifests():
    import json
    # 1. Dynamically get the watcher path for the current user
    local_app_data = os.getenv('LOCALAPPDATA')
    watcher_path = os.path.join(local_app_data, "Annorion", "OmniPull", "omnipull-watcher.exe")
    app_folder = os.path.join(local_app_data, "Annorion", "OmniPull")

    # 2. Define the three browser manifests
    manifests = {
        "com.omnipull.downloader.edge.json": {
            "name": "com.omnipull.downloader",
            "description": "OmniPull Download Manager Native Messaging Host",
            "path": watcher_path,
            "type": "stdio",
            "allowed_origins": ["chrome-extension://ikekemmfgciimbhfjjbmcbmdabklplon/"]
        },
        "com.omnipull.downloader.chrome.json": {
            "name": "com.omnipull.downloader",
            "description": "OmniPull Download Manager Native Messaging Host",
            "path": watcher_path,
            "type": "stdio",
            "allowed_origins": ["chrome-extension://jcejngknfkpiehljlhcdojhacodpbcie/"]
        },
        "com.omnipull.downloader.firefox.json": {
            "name": "com.omnipull.downloader",
            "description": "OmniPull Download Manager Native Messaging Host",
            "path": watcher_path,
            "type": "stdio",
            "allowed_origins": ["omnipull@annorion.dev"]
        }
    }

    # 3. Write/Update the files if the path is incorrect
    for filename, content in manifests.items():
        manifest_path = os.path.join(app_folder, filename)
        try:
            write_needed = True
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    existing = json.load(f)
                    if existing.get("path") == watcher_path:
                        write_needed = False

            if write_needed:
                with open(manifest_path, 'w') as f:
                    json.dump(content, f, indent=2)
                log(f"Native manifest updated: {filename}")
        except Exception as e:
            log(f"Failed to update {filename}: {e}", log_level=3)


def mark_install_healthy():
    try:
        current_dir = Path.home() / ".local/share/OmniPull/current"
        healthy_file = current_dir / ".healthy"
        healthy_file.touch(exist_ok=True)
        log(f"Marked install healthy: {healthy_file}", context="APP-LIFECYCLE")
    except Exception as e:
        log(f"Failed to mark install healthy: {e}", log_level=2)



def fix_browser_integration():
    """
    Ensures JSON manifests and registry keys (Windows) or native messaging
    host directories (Linux/macOS) are correct for Edge, Chrome, and Firefox.
    Cross-platform: works on Windows, Linux, and macOS.
    """
    

    system = platform.system()

    # ── Resolve the watcher executable path ──────────────────────────────────
    if system == "Windows":
        local_app_data = os.getenv('LOCALAPPDATA', '')
        app_folder = os.path.join(local_app_data, "Annorion", "OmniPull")
        program_files_x86 = os.getenv("ProgramFiles(x86)") or os.getenv("ProgramFiles")
        watcher_path = os.path.join(program_files_x86, "Annorion", "OmniPull", "omnipull-watcher.exe")

    elif system == "Darwin":  # macOS
        app_folder  = os.path.expanduser("~/Library/Application Support/OmniPull")
        watcher_path = os.path.join(app_folder, "omnipull-watcher")

    else:  # Linux
        mode = detect_install_mode()
        log(f"OmniPull installed mode detected: {mode} (APPIMAGE={'set' if os.environ.get('APPIMAGE') else 'unset'})")

        try:
            if mode == "appimage":
                app_folder  = os.path.expanduser("~/.local/share/OmniPull/current")
            elif mode == "deb":
                app_folder  = os.path.expanduser("~/.local/share/OmniPull/current")
            else:
                log(f"Unknown installed mode: {mode}, defaulting to deb")
                app_folder  = os.path.expanduser("~/.local/share/OmniPull/current")
        except Exception as e:
            log(f'Error: {e}')
        
        watcher_path = os.path.join(app_folder, "omnipull-watcher")

    os.makedirs(app_folder, exist_ok=True)

    # ── Native messaging host directories per browser/platform ───────────────
    #
    # Chrome/Chromium:
    #   Linux   → ~/.config/google-chrome/NativeMessagingHosts/
    #             ~/.config/chromium/NativeMessagingHosts/
    #   macOS   → ~/Library/Application Support/Google/Chrome/NativeMessagingHosts/
    #   Windows → Registry only (handled below)
    #
    # Firefox:
    #   Linux   → ~/.mozilla/native-messaging-hosts/
    #   macOS   → ~/Library/Application Support/Mozilla/NativeMessagingHosts/
    #   Windows → Registry only (handled below)
    #
    # Edge (Chromium-based):
    #   Linux   → ~/.config/microsoft-edge/NativeMessagingHosts/
    #   macOS   → ~/Library/Application Support/Microsoft Edge/NativeMessagingHosts/
    #   Windows → Registry only (handled below)

    if system == "Linux":
        nmh_dirs = {
            "chrome": [
                os.path.expanduser("~/.config/google-chrome/NativeMessagingHosts"),
                os.path.expanduser("~/.config/chromium/NativeMessagingHosts"),
            ],
            "firefox": [
                os.path.expanduser("~/usr/lib/mozilla/native-messaging-hosts"),
                os.path.expanduser("~/.mozilla/native-messaging-hosts"),
            ],
            "edge": [
                os.path.expanduser("~/.config/microsoft-edge/NativeMessagingHosts"),
            ],
        }
    elif system == "Darwin":
        nmh_dirs = {
            "chrome": [
                os.path.expanduser(
                    "~/Library/Application Support/Google/Chrome/NativeMessagingHosts"
                ),
                os.path.expanduser(
                    "~/Library/Application Support/Chromium/NativeMessagingHosts"
                ),
            ],
            "firefox": [
                os.path.expanduser(
                    "~/Library/Application Support/Mozilla/NativeMessagingHosts"
                ),
            ],
            "edge": [
                os.path.expanduser(
                    "~/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
                ),
            ],
        }
    else:
        nmh_dirs = {}  # Windows uses the registry; no directory needed

    # ── Browser configs ───────────────────────────────────────────────────────
    configs = {
        "chrome": {
            "filename":  "com.omnipull.downloader.json",
            "origin_key": "allowed_origins",
            "origin_val": "chrome-extension://plgjkbjkoghinocjocajenokiklfmkaj/",
            "reg_path":   r"Software\Google\Chrome\NativeMessagingHosts\com.omnipull.downloader",
        },
        "edge": {
            "filename":  "com.omnipull.downloader.json",
            "origin_key": "allowed_origins",
            "origin_val": "chrome-extension://mkhncokjlhefbbnjlgmnifmgejdclbhj/",
            "reg_path":   r"Software\Microsoft\Edge\NativeMessagingHosts\com.omnipull.downloader",
        },
        "firefox": {
            "filename":  "com.omnipull.downloader.json",
            "origin_key": "allowed_extensions",
            "origin_val": "{e899b50f-2a29-4bad-ab4d-b192447a10d0}",
            "reg_path":   r"Software\Mozilla\NativeMessagingHosts\com.omnipull.downloader",
        },
    }

    # ── Write manifests ───────────────────────────────────────────────────────
    for browser, cfg in configs.items():
        manifest = {
            "name":        "com.omnipull.downloader",
            "description": "OmniPull Native Messaging Host",
            "path":        watcher_path,
            "type":        "stdio",
            cfg["origin_key"]: [cfg["origin_val"]],
        }

        if system == "Windows":
            # One manifest file in the app folder; registry points to it
            manifest_path = os.path.join(app_folder, f"com.omnipull.downloader.{browser}.json")
            try:
                with open(manifest_path, "w") as f:
                    json.dump(manifest, f, indent=2)

                import winreg
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, cfg["reg_path"])
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, manifest_path)
                winreg.CloseKey(key)
                log(f"[BrowserIntegration] Fixed {browser} (Windows registry)")
            except Exception as e:
                log(f"[BrowserIntegration] Failed {browser} on Windows: {e}", log_level=3)

        else:
            # Linux / macOS: drop manifest into each NMH directory
            dirs = nmh_dirs.get(browser, [])
            for nmh_dir in dirs:
                try:
                    os.makedirs(nmh_dir, exist_ok=True)
                    manifest_path = os.path.join(nmh_dir, cfg["filename"])
                    with open(manifest_path, "w") as f:
                        json.dump(manifest, f, indent=2)
                    log(f"[BrowserIntegration] Wrote {browser} manifest → {manifest_path}")
                except Exception as e:
                    log(f"[BrowserIntegration] Failed writing {browser} to {nmh_dir}: {e}",
                        log_level=3)