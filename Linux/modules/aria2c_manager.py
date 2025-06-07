# aria2c_manager.py
# This script manages the aria2c download manager, providing functionality to start the RPC server,
# pause, resume downloads, and match download GIDs.
# This file is part of the application and is licensed under the MIT License.

# aria2c_manager.py
# Manages the aria2c RPC server and download lifecycle, including resume, pause, remove and session handling

import os
import subprocess
import time
import psutil
import aria2p
from pathlib import Path
from modules import config, setting
from modules.utils import log
from modules.settings_manager import SettingsManager

class Aria2cManager:
    def __init__(self):
        self.api = None
        self.client = None
        #self.settings_manager = SettingsManager()
        self.home_folder = os.path.expanduser('~')
        self.session_path =  Path.home() / ".config" / config.APP_NAME
        self.session_file = self.session_path / "aria2c.session"
        config.aria2c_path = "/usr/bin/aria2c" 
        self._ensure_session_file()
        setting.load_setting()
        #self.settings_manager.load_settings()
        
        self._start_rpc_server()
        self._connect_api()

    def _ensure_session_file(self):
        self.session_path.mkdir(parents=True, exist_ok=True)
        self.session_file.touch(exist_ok=True)
            

    def _terminate_existing_processes(self):
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and 'aria2c' in proc.info['name'].lower():
                    proc.terminate()
                    proc.wait(timeout=3)
                    log(f'Terminated {proc.info['name']}')
            except Exception:
                continue

    def _start_rpc_server(self):
        if not config.aria2c_path or not os.path.exists(config.aria2c_path):
            log("[aria2c] Executable not found. RPC server will not start.")
            return
        else:
            log("[aria2c] Executable found. Starting RPC server.")
        
        max_conn = config.aria2c_config.get("max_connections", 16)
        if not isinstance(max_conn, int) or not (1 <= max_conn <= 16):
            max_conn = 16
            log("[aria2c] Warning: Invalid 'max_connections'. Reset to 16.")

        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == 'nt':
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs["preexec_fn"] = os.setsid
        # Start aria2c RPC server

        subprocess.Popen([
            config.aria2c_path,
            "--enable-rpc",
            "--rpc-listen-all=false",
            f"--rpc-listen-port={config.aria2c_config['rpc_port']}",
            "--rpc-allow-origin-all",
            "--continue=true",
            f"--save-session={self.session_file}",
            f"--input-file={self.session_file}",
            f"--save-session-interval={config.aria2c_config['save_interval']}",
            f"--max-connection-per-server={max_conn}",
            f"--file-allocation={config.aria2c_config['file_allocation']}",
        ], **kwargs)

        time.sleep(1.5)

    def _connect_api(self):

        try:
            self.client = aria2p.Client(
                host="http://localhost",
                port=config.aria2c_config['rpc_port'],
                secret=""
            )
            self.api = aria2p.API(self.client)
            
            #self.cleanup_orphaned_paused_downloads()
            # self.force_clean_and_save_session()
            log("[aria2c] RPC server connected.")
        except Exception as e:
            log(f"[aria2c] Failed to connect to RPC server: {e}")
            self.api = None

    def get_api(self):
        if not self.api:
            self._start_rpc_server()
            self._connect_api()
        return self.api

    def pause(self, gid):
        try:
            download = self.api.get_download(gid)
            if download and not download.is_complete:
                download.pause()
                return True
        except Exception as e:
            log(f"[aria2c] Failed to pause GID#{gid}: {e}")
        return False

    def resume(self, gid):
        try:
            download = self.api.get_download(gid)
            if download and not download.is_complete:
                download.resume()
                return True
        except Exception as e:
            log(f"[aria2c] Failed to resume GID#{gid}: {e}")
        return False

    def remove(self, gid):
        try:
            download = self.api.get_download(gid)
            if download:
                download.remove(force=True, files=True)
                return True
        except Exception as e:
            log(f"[aria2c] Failed to remove GID#{gid}: {e}")
        return False

    # def force_save_session(self):
    #     try:
    #         if self.api:
    #             result = self.api.client.call("aria2.saveSession")
    #             log(f"[aria2c] Session save result: {result}")
    #         else:
    #             log("[aria2c] Cannot save session. API not available.")
    #     except Exception as e:
    #         log(f"[aria2c] Failed to save session: {e}")

    def force_clean_and_save_session(self):
        """Clean up stale downloads and force-save the session."""
        try:
            if not self.api:
                log("[aria2c] Cannot clean/save session. API not available.")
                return

            all_downloads = self.api.get_downloads()
            for d in all_downloads:
                # Remove completed, error, or removed downloads from session
                if d.is_complete or d.is_removed or d.status in ["complete", "removed", "error"]:
                    try:
                        d.remove(force=True, files=False)
                        log(f"[aria2c] Removed stale GID#{d.gid} before session save")
                    except Exception as e:
                        log(f"[aria2c] Failed to remove GID#{d.gid}: {e}")

            result = self.api.client.call("aria2.saveSession")
            self._terminate_existing_processes()
            log(f"[aria2c] Session saved. Result: {result}")
        except Exception as e:
            log(f"[aria2c] force_clean_and_save_session error: {e}")


    def remove_if_complete(self, gid):
        try:
            download = self.api.get_download(gid)
            if download and download.is_complete:
                download.remove(force=True, files=False)
                self.force_clean_and_save_session()
        except Exception:
            pass

    def cleanup_orphaned_paused_downloads(self):
        """
        Removes any paused downloads from RPC that are not found in the app's known GID list.
        """
        if not self.api:
            return
        from modules.setting import load_d_list
        d_list = load_d_list() # self.settings_manager.d_list # load_d_list()
        active_gids = [d.aria_gid for d in d_list if getattr(d, "aria_gid", None)]
        try:
            downloads = self.api.get_downloads()
            for d in downloads:
                if d.status == "paused" and d.gid not in active_gids:
                    log(f"[aria2c] Removing orphaned paused GID: {d.gid}")
                    d.remove(force=True, files=False)
            self.force_clean_and_save_session()
        except Exception as e:
            log(f"[aria2c] Cleanup failed: {e}")




    def clean_stale_downloads(self, valid_gids: list):
        """Remove any downloads not in your valid GID list before saving session."""
        if not self.api:
            log("[aria2c] Cannot clean. API not initialized.")
            return

        try:
            for download in self.api.get_downloads():
                if download.gid not in valid_gids:
                    if download.status in ["removed", "error", "complete"]:
                        try:
                            download.remove(force=True, files=False)
                            log(f"[aria2c] Removed stale GID#{download.gid} from memory before session save")
                        except Exception as e:
                            log(f"[aria2c] Could not remove GID#{download.gid}: {e}")
        except Exception as e:
            log(f"[aria2c] clean_stale_downloads() error: {e}")

    
    def clean_session_file(self, valid_gids):
        """
        Rewrites the session file keeping only the entries with valid GIDs.
        """
        if not os.path.exists(self.session_file):
            return

        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()

            cleaned_lines = []
            current_block = []
            keep = False

            for line in lines:
                if line.startswith('http'):
                    if current_block and keep:
                        cleaned_lines.extend(current_block)
                    current_block = [line]
                    keep = False  # reset
                else:
                    current_block.append(line)
                    if any(gid_line.startswith(f" gid={gid}") for gid in valid_gids for gid_line in current_block):
                        keep = True

            # Add the last block if needed
            if current_block and keep:
                cleaned_lines.extend(current_block)

            with open(self.session_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(cleaned_lines) + '\n')

            log(f"[aria2c] Session cleaned. Retained {len(valid_gids)} active GIDs.")

        except Exception as e:
            log(f"[aria2c] Failed to clean session file: {e}")


# Global instance
aria2c_manager = Aria2cManager()


