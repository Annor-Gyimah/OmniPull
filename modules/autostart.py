#####################################################################################
# Auto-Start Module
# Handles automatic startup of OmniPull on system boot
# Cross-platform: Windows, macOS, Linux
#####################################################################################

import os
import sys
import shutil
from pathlib import Path
from modules.utils import log


class AutoStart:
    """Manages auto-start functionality for OmniPull"""

    def __init__(self, app_name="OmniPull", app_path=None):
        """
        Initialize AutoStart manager

        Args:
            app_name (str): Name of the application
            app_path (str): Path to the main script (defaults to main_2.py in current directory)
        """
        self.app_name = app_name

        # Get the main script path
        
        if app_path is None:
            if sys.platform == 'win32':
                current_dir = Path(os.path.expanduser("~")) / "AppData" / "Local" / "Annorion" / "OmniPull"
                self.app_path = current_dir / 'main.exe'
            elif sys.platform == 'darwin':
                self.app_path = Path(app_path)
            else:
                self.app_path = Path(app_path)

        # Get Python executable
        self.python_exe = sys.executable

    def is_enabled(self):
        """Check if auto-start is currently enabled"""
        if sys.platform == 'win32':
            return self._is_enabled_windows()
        elif sys.platform == 'darwin':
            return self._is_enabled_macos()
        else:
            return self._is_enabled_linux()

    def enable(self):
        """Enable auto-start"""
        log(f"[AutoStart] Enabling auto-start for {self.app_name}")

        if sys.platform == 'win32':
            return self._enable_windows()
        elif sys.platform == 'darwin':
            return self._enable_macos()
        else:
            return self._enable_linux()

    def disable(self):
        """Disable auto-start"""
        log(f"[AutoStart] Disabling auto-start for {self.app_name}")

        if sys.platform == 'win32':
            return self._disable_windows()
        elif sys.platform == 'darwin':
            return self._disable_macos()
        else:
            return self._disable_linux()

    # Windows implementation
    def _is_enabled_windows(self):
        """Check if auto-start is enabled on Windows (registry)"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run',
                0,
                winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, self.app_name)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception as e:
            log(f"[AutoStart] Error checking Windows auto-start: {e}", level='error')
            return False

    def _enable_windows(self):
        """Enable auto-start on Windows via registry"""
        try:
            import winreg

            # Create command to run (with --tray flag to start minimized)
            command = f'"{self.app_path}" --tray'

            # Open registry key
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run',
                0,
                winreg.KEY_SET_VALUE
            )

            # Set value
            winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)

            log(f"[AutoStart] Windows auto-start enabled: {command}")
            return True
        except Exception as e:
            log(f"[AutoStart] Error enabling Windows auto-start: {e}", level='error')
            return False

    def _disable_windows(self):
        """Disable auto-start on Windows"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run',
                0,
                winreg.KEY_SET_VALUE
            )
            try:
                winreg.DeleteValue(key, self.app_name)
                winreg.CloseKey(key)
                log(f"[AutoStart] Windows auto-start disabled")
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return True  # Already disabled
        except Exception as e:
            log(f"[AutoStart] Error disabling Windows auto-start: {e}", level='error')
            return False

    # macOS implementation
    def _is_enabled_macos(self):
        """Check if auto-start is enabled on macOS (LaunchAgent)"""
        plist_path = self._get_macos_plist_path()
        return plist_path.exists()

    def _get_macos_plist_path(self):
        """Get path to macOS LaunchAgent plist"""
        home = Path.home()
        launch_agents = home / 'Library' / 'LaunchAgents'
        return launch_agents / f'com.annorion.{self.app_name.lower()}.plist'

    def _enable_macos(self):
        """Enable auto-start on macOS via LaunchAgent"""
        try:
            plist_path = self._get_macos_plist_path()

            # Ensure LaunchAgents directory exists
            plist_path.parent.mkdir(parents=True, exist_ok=True)

            # Create plist content
            plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.annorion.{self.app_name.lower()}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{self.python_exe}</string>
        <string>{self.app_path}</string>
        <string>--tray</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>'''

            # Write plist file
            with open(plist_path, 'w') as f:
                f.write(plist_content)

            log(f"[AutoStart] macOS auto-start enabled: {plist_path}")
            return True
        except Exception as e:
            log(f"[AutoStart] Error enabling macOS auto-start: {e}", level='error')
            return False

    def _disable_macos(self):
        """Disable auto-start on macOS"""
        try:
            plist_path = self._get_macos_plist_path()
            if plist_path.exists():
                plist_path.unlink()
                log(f"[AutoStart] macOS auto-start disabled")
            return True
        except Exception as e:
            log(f"[AutoStart] Error disabling macOS auto-start: {e}", level='error')
            return False

    # Linux implementation
    def _is_enabled_linux(self):
        """Check if auto-start is enabled on Linux (desktop file)"""
        desktop_path = self._get_linux_desktop_path()
        return desktop_path.exists()

    def _get_linux_desktop_path(self):
        """Get path to Linux autostart desktop file"""
        home = Path.home()
        autostart = home / '.config' / 'autostart'
        return autostart / f'{self.app_name.lower()}.desktop'

    def _enable_linux(self):
        """Enable auto-start on Linux via autostart desktop file"""
        try:
            desktop_path = self._get_linux_desktop_path()

            # Ensure autostart directory exists
            desktop_path.parent.mkdir(parents=True, exist_ok=True)

            # Create desktop file content
            desktop_content = f'''[Desktop Entry]
Type=Application
Name={self.app_name}
Comment=Start {self.app_name} Download Manager
Exec={self.python_exe} {self.app_path} --tray
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
'''

            # Write desktop file
            with open(desktop_path, 'w') as f:
                f.write(desktop_content)

            # Make executable
            os.chmod(desktop_path, 0o755)

            log(f"[AutoStart] Linux auto-start enabled: {desktop_path}")
            return True
        except Exception as e:
            log(f"[AutoStart] Error enabling Linux auto-start: {e}", level='error')
            return False

    def _disable_linux(self):
        """Disable auto-start on Linux"""
        try:
            desktop_path = self._get_linux_desktop_path()
            if desktop_path.exists():
                desktop_path.unlink()
                log(f"[AutoStart] Linux auto-start disabled")
            return True
        except Exception as e:
            log(f"[AutoStart] Error disabling Linux auto-start: {e}", level='error')
            return False
