
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
import ctypes
from modules import config
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox



def safe_filename(name):
    """Sanitize filename to remove problematic characters."""
    name = re.sub(r'[\\/*?:"<>|]', "_", name)  # Remove bad chars
    return name.strip()

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


def change_cursor(cursor_type: str):
    """Change cursor to busy or normal."""
    if cursor_type == 'busy':
        QApplication.setOverrideCursor(Qt.WaitCursor)  # Busy cursor
    elif cursor_type == 'normal':
        QApplication.restoreOverrideCursor()  # Restore normal cursor


def show_information(title, inform, msg):
    information_box = QMessageBox()
    information_box.setStyleSheet(get_msgbox_style("information"))
    information_box.setText(msg)
    information_box.setWindowTitle(title)
    information_box.setInformativeText(inform)
    information_box.setIcon(QMessageBox.Information)
    information_box.setStandardButtons(QMessageBox.Ok)
    information_box.exec()
    return




def show_critical(title, msg):
    critical_box = QMessageBox()
    critical_box.setStyleSheet(get_msgbox_style("critical"))
    critical_box.setWindowTitle(title)
    critical_box.setText(msg)
    critical_box.setIcon(QMessageBox.Critical)
    critical_box.setStandardButtons(QMessageBox.Ok)
    critical_box.exec()

def show_warning(title, msg):
    warning_box = QMessageBox()
    warning_box.setStyleSheet(get_msgbox_style("warning"))
    warning_box.setWindowTitle(title)
    warning_box.setText(msg)
    warning_box.setIcon(QMessageBox.Warning)
    warning_box.setStandardButtons(QMessageBox.Ok)
    
    warning_box.exec()

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

def toolbar_buttons_state(status: str) -> dict:
    status_map = {
        config.Status.completed: {
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
        config.Status.cancelled: {
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
        config.Status.error: { 
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
        config.Status.paused: {
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
        config.Status.failed: {
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
        config.Status.deleted: {
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
        config.Status.scheduled: {
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
        config.Status.downloading: {
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
        config.Status.pending: {
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
        config.Status.merging_audio: {
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




def get_msgbox_style(msg_type: str) -> str:
    base_style = """
        QMessageBox {
            background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
            );
            color: white;
            font-family: 'Segoe UI';
            font-size: 13px;
            border-radius: 12px;
        }
        QLabel {
            color: white;
        }
    """

    button_styles = {
        "critical": """
            QPushButton {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                );
                color: white;
                padding: 6px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #B71C1C;
            }
        """,
        "warning": """
            QPushButton {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                );
                color: white;
                padding: 6px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #FF8F00;
            }
        """,
        "information": """
            QPushButton {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                );
                color: white;
                padding: 6px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #00B248;
            }
        """,
        "inputdial": """

            QInputDialog {
                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                );
                color: white;
                font-family: 'Segoe UI';
                font-size: 13px;
                border-radius: 12px;
            }
            QLabel {
                color: white;
            }
            QLineEdit {
                background-color: rgba(28, 28, 30, 0.55);  /* Neutral frosted charcoal */
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 6px 10px;
            }
            QPushButton {

                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                ); 
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            
            }
            QPushButton:hover {
                background-color: #00B248;
            }
            QComboBox, QSpinBox, QLineEdit {
                background-color: rgba(28, 28, 30, 0.55);  /* Neutral frosted charcoal */
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 6px 10px;
            }

            QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
                border: 1px solid rgba(111, 255, 176, 0.18);  /* subtle emerald glow on hover */
            }

            QComboBox::drop-down {
                border: none;
                background-color: transparent;
            }
        """,
        "conflict": """
            QPushButton {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
                padding: 6px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1B5E20;
            }
        """,
        "overwrite": """
            QPushButton {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0F1B14,
                    stop: 1 #050708
                );
                color: white;
                padding: 6px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #C62828;  /* deep red on hover for overwrite alert */
            }
        """,
        "question": """
            QPushButton {

                background-color: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #0F1B14,
                stop: 1 #050708
                ); 
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
            
            }
            QPushButton:hover {
                background-color: #00B248;
            }


        """


    }

    return base_style + button_styles.get(msg_type, "")
