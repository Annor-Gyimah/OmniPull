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

import platform
import os
import sys
from modules.utils import log
from modules.Os import OS
from pathlib import Path

# Platform detection
home_address = os.path.expanduser("~")
os_type = platform.system()

if os_type == OS.WINDOWS:
    import winreg

# Consistent key name for Windows Registry
STARTUP_KEY_NAME = 'OmniPull'
ctx = "STARTUP"

def checkStartUp():
    """Checks if the startup value exists in the Registry/Config."""
    if os_type in OS.UNIX_LIKE:
        return os.path.exists(home_address + f"/.config/autostart/{STARTUP_KEY_NAME.lower()}.desktop")

    elif os_type == OS.OSX:
        return os.path.exists(home_address + f"/Library/LaunchAgents/com.{STARTUP_KEY_NAME.lower()}.plist")

    elif os_type == OS.WINDOWS:
        try:
            # Open with KEY_READ to avoid permission issues during a simple check
            aKey = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, 
                "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                0, winreg.KEY_READ
            )
            # This throws FileNotFoundError if 'OmniPull' doesn't exist
            winreg.QueryValueEx(aKey, STARTUP_KEY_NAME)
            winreg.CloseKey(aKey)
            return True
        except Exception:
            return False
    return False

def addStartUp():
    """Adds the application to the OS startup sequence."""
    if os_type in OS.UNIX_LIKE:
        entry = f'''[Desktop Entry]
Name=OmniPull
Exec={sys.argv[0]} --tray
Terminal=false
Type=Application
Icon=OmniPull
'''
        if not os.path.exists(home_address + "/.config/autostart"):
            os.makedirs(home_address + "/.config/autostart", 0o755)
        
        file_path = home_address + f"/.config/autostart/{STARTUP_KEY_NAME.lower()}.desktop"
        with open(file_path, 'w+') as f:
            f.write(entry)
        os.chmod(file_path, 0o644)

    elif os_type == OS.WINDOWS:
        try:
            # Open with ALL_ACCESS to allow writing
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                0, winreg.KEY_ALL_ACCESS
            )
            
            # FIX: Ensure we use the actual executable path
            if getattr(sys, 'frozen', False):
                # If running as .exe
                OmniPull_path = sys.executable
            else:
                # If running as .py
                OmniPull_path = os.path.abspath(sys.argv[0])
            
            exec_string = f'"{OmniPull_path}" --tray'

            winreg.SetValueEx(key, STARTUP_KEY_NAME, 0, winreg.REG_SZ, exec_string)
            winreg.CloseKey(key)
            log(f"Windows Registry key '{STARTUP_KEY_NAME}' established.", log_level=1, context=ctx)
        except Exception as e:
            log(f"Failed to add startup key: {e}", log_level=2, context=ctx)

def removeStartUp():
    """Removes the application from the OS startup sequence."""
    if os_type in OS.UNIX_LIKE:
        file_path = home_address + f"/.config/autostart/{STARTUP_KEY_NAME.lower()}.desktop"
        if os.path.exists(file_path):
            os.remove(file_path)

    elif os_type == OS.WINDOWS:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, 
                "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                0, winreg.KEY_ALL_ACCESS
            )
            winreg.DeleteValue(key, STARTUP_KEY_NAME)
            winreg.CloseKey(key)
            log(f"Windows Registry key '{STARTUP_KEY_NAME}' deleted.", log_level=1, context=ctx)
        except Exception as e:
            log(f"Error removing startup entry: {e}", log_level=2, context=ctx)