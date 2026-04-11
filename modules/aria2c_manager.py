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

from modules.utils import log
from modules import config
from modules.setting import load_d_list, load_setting, save_setting




class Aria2cManager:
    """
    Manages the lifecycle of the aria2c RPC daemon and its connection.
    
    This manager handles:
    1. Session persistence (saving and loading .session files).
    2. Daemon process isolation (preventing terminal popups).
    3. RPC Server configuration (Ports, Connections, and Intervals).
    """

    def __init__(self):
        self.api = None
        self.client = None
        self.session_dir = config.ARIA2C_SESSION_DIR
        self.session_file = config.ARIA2C_SESSION_FILE
        
        # Initialize filesystem requirements
        self._ensure_session_file()
        load_setting()

        # Bootstrap the RPC backend
        self._start_rpc_server()
        self._connect_api()

    def _ensure_session_file(self):
        """Ensures the directory structure and session file exist for persistence."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file.touch(exist_ok=True)

    def _terminate_existing_processes(self):
        """
        Scans the OS process list for orphaned aria2c instances and terminates them.
        
        This prevents 'Port Already in Use' errors by ensuring a fresh start 
        for the current application session.
        """
        ctx = "ARIA2-DAEMON"
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and 'aria2c' in proc.info['name'].lower():
                    proc.terminate()
                    proc.wait(timeout=3)
                    log(f"Terminated orphaned daemon (PID: {proc.info['pid']})", 
                        log_level=1, context=ctx)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue

    def _start_rpc_server(self):
        """
        Spawns the aria2c binary as a background RPC server.
        
        Configures the daemon with optimized parameters for multi-connection 
        downloads, session auto-saving, and local-only RPC listening.
        """
        ctx = "ARIA2-DAEMON"
        
        # Verify executable existence
        if not config.aria2c_path or not os.path.exists(config.aria2c_path):
            log("Daemon initialization failed: Binary not found.", log_level=2, context=ctx)
            config.aria2_verified = False
            return

        config.aria2_verified = True
        save_setting()

        # Helper to safely parse integer configurations
        def _cfg_int(x, default=0):
            try:
                return int(float(x))
            except (ValueError, TypeError):
                return default

        # Validate connection limits (Aria2c hardware cap is 16)
        max_conn = _cfg_int(config.aria2c_config.get("max_connections", 16))
        if not (1 <= max_conn <= 16):
            log(f"Invalid connection cap ({max_conn}). Resetting to 16.", log_level=3, context=ctx)
            max_conn = 16

        # Build Subprocess execution flags
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        if config.IS_WIN:
            # Prevent command prompt window from appearing on Windows
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            # Detach process from the current terminal session on Unix/macOS
            kwargs["start_new_session"] = True

        # Construct Daemon Launch Arguments
        args = [
            config.aria2c_path,
            "--enable-rpc",
            "--rpc-listen-all=false",  # Security: Listen only on localhost
            f"--rpc-listen-port={config.aria2c_config['rpc_port']}",
            "--rpc-allow-origin-all",
            "--continue=true",         # Global resume support
            f"--save-session={self.session_file}",
            f"--input-file={self.session_file}",
            f"--save-session-interval={config.aria2c_config['save_interval']}",
            f"--max-connection-per-server={max_conn}",
            f"--file-allocation={config.aria2c_config['file_allocation']}",
        ]

        try:
            subprocess.Popen(args, **kwargs)
            log(f"Aria2c RPC server started on port {config.aria2c_config['rpc_port']}", 
                log_level=1, context=ctx)
            # Allow the daemon a moment to initialize its socket
            time.sleep(1.5)
        except Exception as e:
            log(f"Fatal error during daemon launch: {e}", log_level=3, context=ctx)

    # ── API Connection & Session Management ──────────────────────────────────

    def _connect_api(self):
        """
        Establishes the JSON-RPC connection to the local aria2c daemon.
        
        Uses the aria2p client to interface with the backend. If the connection 
        fails, the API is set to None, triggering a re-launch attempt on the 
        next request.
        """
        ctx = "ARIA2-RPC"
        try:
            self.client = aria2p.Client(
                host="http://localhost",
                port=config.aria2c_config['rpc_port'],
                secret="" # No secret for local-only RPC
            )
            self.api = aria2p.API(self.client)
            log("RPC server connection established.", log_level=1, context=ctx)
        except Exception as e:
            log(f"RPC connection failed: {e}", log_level=3, context=ctx)
            self.api = None

    def get_api(self):
        """
        Gateway method to retrieve the active API instance.
        
        If the API is missing or the daemon has crashed, this method 
        orchestrates a full reset: re-starting the server, purging orphaned 
        GIDs from the session file, and re-connecting.
        """
        if not self.api:
            self._start_rpc_server()
            
            # Identify GIDs that are actually tracked in our application database
            valid_gids = [d.aria_gid for d in load_d_list() if getattr(d, "aria_gid", None)]
            self.clean_session_file(valid_gids)

            self._connect_api()
        return self.api

    # ── Task Lifecycle Control ───────────────────────────────────────────────

    def pause(self, gid):
        """Suspends an active download by its GID."""
        try:
            download = self.api.get_download(gid)
            if download and not download.is_complete:
                download.pause()
                return True
        except Exception as e:
            log(f"Pause command failed for GID {gid}: {e}", log_level=3, context="ARIA2-RPC")
        return False

    def resume(self, gid):
        """Resumes a paused download by its GID."""
        try:
            download = self.api.get_download(gid)
            if download and not download.is_complete:
                download.resume()
                return True
        except Exception as e:
            log(f"Resume command failed for GID {gid}: {e}", log_level=3, context="ARIA2-RPC")
        return False

    # ── Advanced GID Relationship Mapping ───────────────────────────────────

    def _collect_related_gids(self, root_gid):
        """
        Navigates the download dependency tree to find all related tasks.
        
        This is critical for:
        1. Meta-downloads (Control files followed by data files).
        2. Torrents (Sharing a common InfoHash).
        3. Segmented streams (Parent DASH files and their children).
        """
        api = self.api
        if not api or not root_gid:
            return set()

        related = set()
        stack = [root_gid]
        seen = set()

        # Step 1: Detect InfoHash for sibling matching (common in BitTorrent)
        root_infohash = None
        try:
            root = api.get_download(root_gid)
            if root:
                root_infohash = getattr(root, "info_hash", None) or getattr(root, "infoHash", None)
        except Exception:
            pass

        # Step 2: Depth-first search through the relation graph
        while stack:
            gid = stack.pop()
            if gid in seen: continue
            
            seen.add(gid)
            related.add(gid)
            
            try:
                dl = api.get_download(gid)
                if not dl: continue

                # Traverse standard relationship fields
                rel_keys = ("following", "followed_by", "followedBy", "belongsTo")
                for key in rel_keys:
                    rel = getattr(dl, key, None)
                    if not rel: continue
                    
                    if isinstance(rel, (list, tuple)):
                        for g in rel:
                            if g and g not in seen: stack.append(g)
                    elif isinstance(rel, str) and rel not in seen:
                        stack.append(rel)

                # Step 3: Match siblings by InfoHash (shared torrent metadata)
                if root_infohash:
                    for other in api.get_downloads() or []:
                        ih = getattr(other, "info_hash", None) or getattr(other, "infoHash", None)
                        if ih and ih == root_infohash and other.gid not in related:
                            stack.append(other.gid)
                            
            except Exception:
                continue

        return related
    
    # ── Advanced Task Control ────────────────────────────────────────────────

    def pause_family(self, root_gid):
        """
        Forces a recursive suspension of a download and all its dependencies.
        
        This is particularly important for torrents or segmented downloads 
        where multiple GIDs are linked. It first attempts a 'forcePause' via 
        direct RPC for maximum reliability, then falls back to the standard 
        API pause.
        """
        ctx = "ARIA2-RPC"
        api = self.api
        if not api or not root_gid:
            return False

        # Gather all related GIDs (siblings, children, followed-by)
        gids = self._collect_related_gids(root_gid)
        paused_any = False

        for gid in gids:
            try:
                # Tier 1: Direct RPC forcePause (Overcomes most 'busy' states)
                api.client.call("aria2.forcePause", gid)
                paused_any = True
            except Exception:
                try:
                    # Tier 2: Standard API pause fallback
                    dl = api.get_download(gid)
                    if dl and not dl.is_complete:
                        dl.pause()
                        paused_any = True
                except Exception:
                    pass

        # Trigger an immediate session save to persist the 'Paused' state to disk
        self.save_session_only()
        
        if paused_any:
            log(f"Successfully suspended task family for GID: {root_gid}", 
                log_level=1, context=ctx)
        return paused_any

    def remove(self, gid):
        """
        Permanently removes a task from the aria2c queue.
        
        Forcefully stops the process and deletes associated control files 
        to ensure the GID is purged from the active session.
        """
        try:
            download = self.api.get_download(gid)
            if download:
                download.remove(force=True, files=True)
                log(f"Task removed from engine: {gid}", log_level=1, context="ARIA2-RPC")
                return True
        except Exception as e:
            log(f"Removal failed for GID {gid}: {e}", log_level=3, context="ARIA2-RPC")
        return False

    # ── Real-time Data Retrieval ─────────────────────────────────────────────

    def get_progress(self, gid):
        """Returns the current completion percentage for a specific GID."""
        try:
            download = self.api.get_download(gid)
            return int(download.progress)
        except Exception:
            return 0

    def get_downloaded_size(self, gid):
        """Returns the total number of bytes successfully written for a specific GID."""
        try:
            download = self.api.get_download(gid)
            return int(download.completed_length)
        except Exception:
            return 0

    # ── Session Management ───────────────────────────────────────────────────

    def save_session_only(self):
        """
        Triggers a manual write of the current aria2c state to the session file.
        
        This is a 'lightweight' save that ensures if the app crashes, 
        progress for all GIDs can be resumed on the next boot.
        """
        ctx = "ARIA2-RPC"
        if not self.api:
            return
            
        try:
            self.api.client.call("aria2.saveSession")
            log("Session state persisted to disk.", log_level=1, context=ctx)
        except Exception as e:
            log(f"Session save failed: {e}", log_level=3, context=ctx)

    def remove_if_complete(self, gid):
        """
        Cleans up the engine's internal queue by removing completed entries.
        
        This prevents the aria2c session from becoming bloated with 
        historical data while keeping the physical files intact.
        """
        try:
            download = self.api.get_download(gid)
            if download and download.is_complete:
                # Remove from engine list but DO NOT delete files
                download.remove(force=True, files=False)
                self.save_session_only()
        except Exception:
            pass
    
    # ── Orphaned Task Cleanup ────────────────────────────────────────────────

    def cleanup_orphaned_paused_downloads(self):
        """
        Forcefully removes tasks from the RPC server that the app no longer tracks.
        
        Logic Flow:
        1. Compares active GIDs in the app's database with the daemon's current list.
        2. Force-removes live orphans (Active/Waiting/Paused).
        3. Purges historical results (Complete/Error/Removed).
        4. Rewrites the session file to ensure the disk state matches the memory state.
        """
        ctx = "ARIA2-DAEMON"
        if not self.api: return

        # Load fresh list to identify what we actually want to keep
        d_list = load_d_list()
        active_gids = {d.aria_gid for d in d_list if getattr(d, "aria_gid", None)}

        api = self.api
        try:
            downloads = api.get_downloads()
            for dl in downloads:
                gid = dl.gid
                if gid in active_gids:
                    continue

                # Stage 1: Force-remove active/paused tasks from the engine
                st = (getattr(dl, "status", "") or "").lower()
                if st in ("active", "waiting", "paused"):
                    try:
                        api.client.call("aria2.forceRemove", gid)
                        log(f"Force-removed orphan GID: {gid}", log_level=1, context=ctx)
                    except Exception as e:
                        log(f"Failed to forceRemove GID {gid}: {e}", log_level=2, context=ctx)

                # Stage 2: Purge the result record (history)
                try:
                    if hasattr(api, "remove_download_result"):
                        api.remove_download_result(gid)
                    else:
                        api.client.call("aria2.removeDownloadResult", gid)
                    log(f"Purged orphan result for GID: {gid}", log_level=1, context=ctx)
                except Exception as e:
                    log(f"Failed to purge orphan result {gid}: {e}", log_level=2, context=ctx)

            # Stage 3: Synchronize Disk State
            try:
                api.client.call("aria2.saveSession")
                self.clean_session_file(list(active_gids))
                log("Session sanitized after orphan cleanup.", log_level=1, context=ctx)
            except Exception as e:
                log(f"Post-cleanup session save failed: {e}", log_level=2, context=ctx)

        except Exception as e:
            log(f"Orphan cleanup sequence failed: {e}", log_level=3, context=ctx)

    # ── Advanced Session Rewriting ──────────────────────────────────────────

    def clean_session_file(self, valid_gids):
        """
        Performs a block-level rewrite of the aria2.session file.
        
        This method parses the indented session format, retaining only the 
        multi-line blocks that contain a valid GID. This ensures the engine 
        doesn't re-load deleted tasks on the next restart.
        """
        if not os.path.exists(self.session_file):
            return

        valid_gids = set(g for g in valid_gids if g)
        log(f"Rewriting session file. Retaining {len(valid_gids)} active tasks.", 
            log_level=1, context="ARIA2-DAEMON")

        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()

            cleaned, block = [], []
            keep = False

            def flush():
                nonlocal block, keep, cleaned
                if block:
                    if keep: cleaned.extend(block)
                    block, keep = [], False

            for line in lines:
                # A new task block starts with a non-indented line (typically the URI)
                if line and not line.startswith(' '):
                    flush()
                    block = [line]
                    keep = False
                else:
                    block.append(line)
                    # Check if the indented property matches a valid GID
                    if line.startswith(" gid="):
                        if line.split("=", 1)[1].strip() in valid_gids:
                            keep = True

            flush() # Flush the final task block

            with open(self.session_file, 'w', encoding='utf-8') as f:
                if cleaned and cleaned[-1] != '': cleaned.append('')
                f.write('\n'.join(cleaned))

        except Exception as e:
            log(f"Critical: Session file rewrite failed: {e}", log_level=3, context="ARIA2-DAEMON")

    # ── Shutdown Sequence ────────────────────────────────────────────────────

    def shutdown_freeze_and_save(self, purge=True):
        """
        Safely halts the engine during application exit.
        
        1. Pauses all active downloads to preserve 'Range' headers.
        2. Optionally purges non-BitTorrent completed results.
        3. Commits the final memory state to the session file.
        """
        ctx = "APP-LIFECYCLE"
        api = self.api
        if not api: return

        # 1. Freeze active workers
        try:
            api.pause_all(force=False)
            log("Freeze command issued: All active streams suspended.", log_level=1, context=ctx)
        except Exception as e:
            log(f"Global pause failed during shutdown: {e}", log_level=2, context=ctx)

        # 2. Cleanup non-resumable history
        if purge:
            try:
                for dl in api.get_downloads() or []:
                    st = (getattr(dl, "status", "") or "").lower()
                    is_bt = getattr(dl, "bittorrent", None) is not None
                    
                    # Safety: Never purge active/resumable tasks or complex torrent trees
                    if st in ("active", "waiting", "paused") or is_bt:
                        continue
                        
                    if st in ("complete", "removed"):
                        try:
                            # Use authority-level RPC for the purge
                            api.client.call("aria2.removeDownloadResult", dl.gid)
                        except Exception:
                            pass
            except Exception:
                pass

        # 3. Final disk commit
        try:
            self.api.client.call("aria2.saveSession")
            log("Final shutdown snapshot saved to disk.", log_level=1, context=ctx)
        except Exception as e:
            log(f"Final session save failed: {e}", log_level=3, context=ctx)



# Global instance
aria2c_manager = Aria2cManager()

