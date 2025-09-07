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
from modules.setting import load_d_list

class Aria2cManager:
    def __init__(self):
        self.api = None
        self.client = None
        #self.settings_manager = SettingsManager()
        self.session_path =  Path.home() / ".config" / config.APP_NAME
        self.session_file = self.session_path / "aria2c.session"
        config.aria2c_path = "/opt/omnipull/aria2c"
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


    
    def force_clean_and_save_session(self):
        """
        Freeze aria2 state and save session without nuking resumable tasks.
        - Keeps active/waiting/paused items (so GIDs survive restarts).
        - Skips torrent parents/children and relation-linked entries.
        - Purges only truly stale *results* (complete/removed), not live tasks.
        """
        try:
            api = self.api
            if not api:
                log("[aria2c] Cannot clean/save session. API not available.", log_level=2)
                return

            # 1) Freeze current state so the session snapshot is consistent.
            try:
                api.pause_all(force=False)
                log("[aria2c] pause_all issued before save", log_level=1)
            except Exception as e:
                log(f"[aria2c] pause_all failed: {e}", log_level=2)

            # 2) Purge only stale results; KEEP anything resumable or relation-linked.
            def _has_relations(dl) -> bool:
                # Parent/child relationships (naming varies by aria2p/version)
                for k in ("following", "followed_by", "followedBy"):
                    v = getattr(dl, k, None)
                    if v:
                        if isinstance(v, (list, tuple)):
                            if any(v):  # non-empty
                                return True
                        else:
                            return True
                return False

            downloads = []
            try:
                downloads = api.get_downloads()
            except Exception as e:
                log(f"[aria2c] get_downloads failed: {e}", log_level=2)

            for dl in downloads or []:
                st = (getattr(dl, "status", "") or "").lower()
                is_bt = getattr(dl, "bittorrent", None) is not None

                # Keep anything that could be resumed
                if st in ("active", "waiting", "paused"):
                    continue

                # Be conservative with torrents and relation-linked entries
                if is_bt or _has_relations(dl):
                    # Even if 'complete' or 'error', skip purging here to preserve linkage.
                    continue

                # Only purge finished/removed *results* (do not delete files)
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

                # Note: do NOT purge 'error' here; leaving it keeps metadata/relations intact
                # so a later resume can re-attach correctly.

            # 3) Save the session snapshot
            try:
                result = api.client.call("aria2.saveSession")
                log(f"[aria2c] Session saved. Result: {result}", log_level=1)
            except Exception as e:
                log(f"[aria2c] saveSession failed: {e}", log_level=3)

            # 4) Optionally resume all (light-touch) — comment out if you prefer manual control
            try:
                api.resume_all()
            except Exception:
                pass

        except Exception as e:
            log(f"[aria2c] force_clean_and_save_session error: {e}", log_level=3)



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



# Global instance
aria2c_manager = Aria2cManager()


