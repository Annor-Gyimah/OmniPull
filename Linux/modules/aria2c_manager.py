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
import time
import psutil
import aria2p
import subprocess
from pathlib import Path
from modules.utils import log
from modules import config, setting
from modules.config import _find_tool
from modules.setting import load_d_list
from modules.settings_manager import SettingsManager


class Aria2cManager:
    def __init__(self):
        self.api = None
        self.client = None
        #self.settings_manager = SettingsManager()
        self.session_path =  Path.home() / ".config" / config.APP_NAME
        self.session_file = self.session_path / "aria2c.session"
        config.aria2c_path = self._get_aria2c_path()  # "/opt/omnipull/aria2c"
        self._ensure_session_file()
        setting.load_setting()
        #self.settings_manager.load_settings()
        
        self._start_rpc_server()
        self._connect_api()

    # def _get_aria2c_path(self):
    #     # Check common installation paths
    #     common_paths = [
    #         "/usr/bin/aria2c",
    #         "/usr/local/bin/aria2c",
    #         "/opt/homebrew/bin/aria2c",  # macOS with Homebrew on M1
    #         "/opt/omnipull/aria2c",      # Custom path for OmniPull package
    #         f"{Path.home()}/.local/share/{config.APP_NAME}/aria2c" # for appimage insall
    #     ]
    #     for path in common_paths:
    #         if os.path.exists(path):
    #             return path
    #     return None

    

    def _get_aria2c_path(self, chosen: bool = True) -> str | None:
        aria2c_selected_path: str | None = None  # if you expose a manual picker
        selected = aria2c_selected_path if chosen else None
        return _find_tool(
            "aria2c",
            selected=selected,
            bundled_name="aria2c",  # also shipped in the bootstrap/update tar
            extra_paths=[
                "/usr/bin/aria2c",
                "/usr/local/bin/aria2c",
                f"{Path.home()}/.local/share/{config.APP_NAME}/aria2c"
                "/opt/homebrew/bin/aria2c",
            ],
        )


    def _ensure_session_file(self):
        self.session_path.mkdir(parents=True, exist_ok=True)
        self.session_file.touch(exist_ok=True)
            

    def _terminate_existing_processes(self):
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and 'aria2c' in proc.info['name'].lower():
                    proc.terminate()
                    proc.wait(timeout=3)
                    log(f'Terminated {proc.info['name']}', log_level=1)
            except Exception:
                continue

    def _start_rpc_server(self):
        
        if not config.aria2c_path or not os.path.exists(config.aria2c_path):
            log("[aria2c] Executable not found. RPC server will not start.", log_level=2)
            return
        else:
            log("[aria2c] Executable found. Starting RPC server.", log_level=1)
        
        max_conn = config.aria2c_config.get("max_connections", 16)
        if not isinstance(max_conn, int) or not (1 <= max_conn <= 16):
            max_conn = 16
            log("[aria2c] Warning: Invalid 'max_connections'. Reset to 16.", log_level=3)

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
            # f"--bt-save-metadata=true"
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
            
            # self.cleanup_orphaned_paused_downloads()
            # self.force_clean_and_save_session()
            log("[aria2c] RPC server connected.", log_level=1)
        except Exception as e:
            log(f"[aria2c] Failed to connect to RPC server: {e}", log_level=3)
            self.api = None

    def get_api(self):
        if not self.api:
            self._start_rpc_server()
            valid_gids = [d.aria_gid for d in load_d_list() if getattr(d, "aria_gid", None)]
            self.clean_session_file(valid_gids)

            self._connect_api()
        return self.api

    def pause(self, gid):
        try:
            download = self.api.get_download(gid)
            if download and not download.is_complete:
                download.pause()
                return True
        except Exception as e:
            log(f"[aria2c] Failed to pause GID#{gid}: {e}", log_level=3)
        return False

    def resume(self, gid):
        try:
            download = self.api.get_download(gid)
            if download and not download.is_complete:
                download.resume()
                return True
        except Exception as e:
            log(f"[aria2c] Failed to resume GID#{gid}: {e}", log_level=3)
        return False

    def remove(self, gid):
        try:
            download = self.api.get_download(gid)
            if download:
                download.remove(force=True, files=True)
                return True
        except Exception as e:
            log(f"[aria2c] Failed to remove GID#{gid}: {e}", log_level=3)
        return False
    
    def get_progress(self, gid):
        try:
            download = self.api.get_download(gid)
            return int(download.progress)
        except:
            return 0

    def get_downloaded_size(self, gid):
        try:
            download = self.api.get_download(gid)
            return int(download.completed_length)
        except:
            return 0


    def save_session_only(self):
        """Lightweight: save current aria2 state without pausing/resuming or purging."""
        api = self.api
        if not api:
            log("[aria2c] Cannot save session. API not available.", log_level=2)
            return
        try:
            result = api.client.call("aria2.saveSession")
            log(f"[aria2c] Session saved (light). Result: {result}", log_level=1)
        except Exception as e:
            log(f"[aria2c] save_session_only failed: {e}", log_level=3)




    def remove_if_complete(self, gid):
        try:
            download = self.api.get_download(gid)
            if download and download.is_complete:
                download.remove(force=True, files=False)
                # self.force_clean_and_save_session()
                self.save_session_only()
        except Exception:
            pass

    

    def cleanup_orphaned_paused_downloads(self):
        """
        Remove any downloads from RPC that are not in the app's known GID list,
        handling paused/active correctly, and purge their results. Then save session.
        """
        if not self.api:
            return

        
        d_list = load_d_list()
        active_gids = {d.aria_gid for d in d_list if getattr(d, "aria_gid", None)}

        api = self.api
        try:
            downloads = api.get_downloads()
            for dl in downloads:
                gid = dl.gid
                if gid in active_gids:
                    continue

                # 1) Force-remove live tasks (paused/active/waiting)
                st = (getattr(dl, "status", "") or "").lower()
                if st in ("active", "waiting", "paused"):
                    try:
                        # aria2p Download has .remove(force=True, files=False), but we prefer RPC to be explicit:
                        api.client.call("aria2.forceRemove", gid)
                        log(f"[aria2c] Force-removed orphan GID: {gid}", log_level=1)
                    except Exception as e:
                        log(f"[aria2c] Failed to forceRemove GID#{gid}: {e}", log_level=2)

                # 2) Purge the result entry (works for complete/removed/error)
                try:
                    if hasattr(api, "remove_download_result"):
                        api.remove_download_result(gid)
                    else:
                        api.client.call("aria2.removeDownloadResult", gid)
                    log(f"[aria2c] Purged orphan result GID: {gid}", log_level=1)
                except Exception as e:
                    log(f"[aria2c] Failed to remove orphaned paused result: {e}", log_level=2)

            # 3) Save session after cleanup
            try:
                api.client.call("aria2.saveSession")
                valid_gids = [d.aria_gid for d in load_d_list() if getattr(d, "aria_gid", None)]
                self.clean_session_file(valid_gids)
                log("[aria2c] Session saved after orphan cleanup", log_level=1)
            except Exception as e:
                log(f"[aria2c] saveSession failed: {e}", log_level=2)

            # ❌ Do NOT kill aria2c here; it causes races/stale session
            # self._terminate_existing_processes()

        except Exception as e:
            log(f"[aria2c] Cleanup failed: {e}", log_level=3)





    def clean_stale_downloads(self, valid_gids: list):
        """Remove any downloads not in your valid GID list before saving session."""
        if not self.api:
            log("[aria2c] Cannot clean. API not initialized.", log_level=3)
            return

        try:
            for download in self.api.get_downloads():
                if download.gid not in valid_gids:
                    if download.status in ["removed", "error", "complete"]:
                        try:
                            download.remove(force=True, files=False)
                            log(f"[aria2c] Removed stale GID#{download.gid} from memory before session save", log_level=1)
                        except Exception as e:
                            log(f"[aria2c] Could not remove GID#{download.gid}: {e}", log_level=3)
        except Exception as e:
            log(f"[aria2c] clean_stale_downloads() error: {e}")


    
    def clean_session_file(self, valid_gids):
        """
        Rewrites aria2.session keeping only entries whose block contains a gid in valid_gids.
        Works for both HTTP URLs and local file (e.g., .torrent) URIs.
        """
        if not os.path.exists(self.session_file):
            return

        valid_gids = set(g for g in valid_gids if g)

        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()

            cleaned = []
            block = []
            keep = False

            def flush():
                nonlocal block, keep, cleaned
                if block:
                    if keep:
                        cleaned.extend(block)
                    block = []
                    keep = False

            for line in lines:
                # A new block starts at any line that does NOT start with a space
                if line and not line.startswith(' '):
                    # finish previous
                    flush()
                    block = [line]
                    keep = False
                else:
                    # continuation line (indented key=val lines)
                    block.append(line)
                    # check if any gid in this block is valid
                    if line.startswith(" gid="):
                        gid_val = line.split("=", 1)[1].strip()
                        if gid_val in valid_gids:
                            keep = True

            # flush last block
            flush()

            with open(self.session_file, 'w', encoding='utf-8') as f:
                if cleaned and cleaned[-1] != '':
                    cleaned.append('')
                f.write('\n'.join(cleaned))

            log(f"[aria2c] Session cleaned. Retained {len(valid_gids)} active GIDs.", log_level=1)

        except Exception as e:
            log(f"[aria2c] Failed to clean session file: {e}", log_level=3)

    
    def shutdown_freeze_and_save(self, purge=True):
        """
        Shutdown path: pause all, (optionally) purge stale results, save session.
        Do NOT resume here; the app is exiting.
        """
        api = self.api
        if not api:
            log("[aria2c] Cannot freeze/save on shutdown. API not available.", log_level=2)
            return
        # 1) Freeze
        try:
            api.pause_all(force=False)
            log("[aria2c] pause_all issued for shutdown", log_level=1)
        except Exception as e:
            log(f"[aria2c] pause_all failed: {e}", log_level=2)

        # 2) Purge finished/removed (optional)
        if purge:
            try:
                def _has_relations(dl):
                    for k in ("following", "followed_by", "followedBy"):
                        v = getattr(dl, k, None)
                        if v:
                            if isinstance(v, (list, tuple)):
                                if any(v):
                                    return True
                            else:
                                return True
                    return False

                for dl in api.get_downloads() or []:
                    st = (getattr(dl, "status", "") or "").lower()
                    is_bt = getattr(dl, "bittorrent", None) is not None

                    # Keep resumables
                    if st in ("active", "waiting", "paused"):
                        continue
                    # Keep torrent parents/children for linkage safety
                    if is_bt or _has_relations(dl):
                        continue

                    if st in ("complete", "removed"):
                        try:
                            if hasattr(api, "remove_download_result"):
                                api.remove_download_result(dl.gid)
                            elif hasattr(dl, "remove_result"):
                                dl.remove_result()
                            else:
                                api.client.call("aria2.removeDownloadResult", dl.gid)
                            log(f"[aria2c] Purged stale result GID#{dl.gid}", log_level=1)
                        except Exception as e:
                            log(f"[aria2c] Failed to purge result GID#{dl.gid}: {e}", log_level=3)
            except Exception as e:
                log(f"[aria2c] purge loop failed: {e}", log_level=2)

        # 3) Save snapshot
        try:
            result = api.client.call("aria2.saveSession")
            log(f"[aria2c] Session saved (shutdown). Result: {result}", log_level=1)
        except Exception as e:
            log(f"[aria2c] saveSession (shutdown) failed: {e}", log_level=3)

        




# Global instance
aria2c_manager = Aria2cManager()