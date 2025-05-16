# aria2c_manager.py
# This script manages the aria2c download manager, providing functionality to start the RPC server,
# pause, resume downloads, and match download GIDs.
# This file is part of the application and is licensed under the MIT License.
import os
import subprocess
import time
import psutil
import aria2p

from modules.config import aria2c_path, sett_folder, aria2c_config
from modules.utils import log

class Aria2cManager:
    def __init__(self):
        self.api = None
        self.client = None

        self.session_file = os.path.join(sett_folder, "aria2c.session")
        os.makedirs(sett_folder, exist_ok=True)
        if not os.path.exists(self.session_file):
            with open(self.session_file, 'w') as f:
                pass

        self._kill_existing_aria2c()
        self._start_aria2c_with_session()
        self._connect_api()

    def _kill_existing_aria2c(self):
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'aria2c' in proc.info['name']:
                    proc.terminate()
                    proc.wait(timeout=2)
                    log(f"[aria2c] Terminated existing process (PID {proc.pid})")
            except Exception as e:
                log(f"[aria2c] Could not terminate aria2c (PID {proc.pid}): {e}")

    def _start_aria2c_with_session(self):
        cmd = [
            aria2c_path,
            "--enable-rpc",
            "--rpc-listen-all=false",
            f"--rpc-listen-port={aria2c_config['rpc_port']}",
            "--rpc-allow-origin-all",
            "--continue=true",
            f"--save-session={self.session_file}",
            f"--input-file={self.session_file}",
            f"--save-session-interval={aria2c_config['save_interval']}",
            f"--max-connection-per-server={aria2c_config['max_connections']}",
            "--file-allocation=none"

        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("[aria2c] Started aria2c with session support")
        time.sleep(1)

    def _connect_api(self):
        try:
            self.client = aria2p.Client(host="http://localhost", port=6800, secret="")
            self.api = aria2p.API(self.client)
            log("[aria2c] RPC server connected.")
        except Exception as e:
            log(f"[aria2c] Failed to connect to RPC server: {e}")
            self.api = None

    def get_api(self):
        if not self.api:
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
                download.resume()  # not `unpause()`, correct method is `resume()`
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

    def force_save_session(self):
        try:
            if self.api:
                result = self.api.client.call("aria2.saveSession")
                log(f"[aria2c] Session save result: {result}")
            else:
                log("[aria2c] Cannot save session. API is not available.")
        except Exception as e:
            log(f"[aria2c] Failed to save session: {e}")


# Global instance
aria2c_manager = Aria2cManager()
