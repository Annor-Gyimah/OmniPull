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
import re
import json
import mmap
import sys
import time
import queue
import socket
import yt_dlp
import asyncio
import threading
import subprocess
from threading import Thread, Lock

from modules import config
from modules.worker import Worker
from modules import native_engine
from modules.threadpool import executor
from modules.helpers import safe_filename
from modules.aria2c_manager import aria2c_manager
from modules.postprocessing import async_merge_video_audio, _apply_postprocessing
from modules.config import Status, APP_NAME, get_effective_ffmpeg
from modules.utils import (log, size_format, popup, notify, delete_folder, delete_file, rename_file, validate_file_name)
from modules.video import (Stream, is_download_complete, get_ytdl_options, extract_info_blocking, pre_process_hls, post_process_hls, unzip_ffmpeg, 
    unzip_deno, remove_internal_item) 
from modules.resume_tracker import ResumeTracker 
from modules.subtitles import get_advanced_opts, fetch_subtitle_with_retry





lock = Lock()

def has_internet_connection(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        log("No internet connection:", ex)
        return False
    
# Signal emitter for status updates
signal_emitter = None

def set_signal_emitter(emitter):
    """
    Assigns the global Qt signal emitter used for UI updates and logging.
    """
    global signal_emitter
    signal_emitter = emitter


def _select_streams_for_aria2(d, vid_info, preferred_langs=None):
    """
    Selects the optimal video and audio stream pair for the aria2 engine.
    
    Prioritizes:
    1. User-explicit format IDs (if set in d.format_id).
    2. Progressive HTTP(s) streams (aria2 cannot handle m3u8/HLS manifests).
    3. Container compatibility (e.g., matching mp4 video with m4a audio for muxing).
    4. Language preferences for audio tracks.
    
    Returns: (video_stream, audio_stream) or (None, None)
    """
    ctx = "STREAM-SELECT"
    
    if preferred_langs is None:
        preferred_langs = ["en-US", "en", "eng", None]  # None handles unlabeled tracks

    # Wrap raw format dictionaries into Stream objects for easier attribute access
    streams = [Stream(f) for f in vid_info.get("formats", [])]
    videos  = [s for s in streams if s.mediatype in ("dash", "normal") and s.vcodec != "none"]
    audios  = [s for s in streams if s.mediatype in ("dash", "audio") and s.acodec != "none"]

    # 1. Check for explicit User Selection via format IDs
    v = next((s for s in videos if getattr(d, "format_id", None) and s.format_id == d.format_id), None)
    a = next((s for s in audios if getattr(d, "audio_format_id", None) and s.format_id == d.audio_format_id), None)

    # 2. Filter for aria2-compatible protocols (Must be progressive, no manifests like m3u8)
    def is_ok_for_aria2(s):
        proto = (s.protocol or "").lower()
        return ("m3u8" not in proto)

    # 3. Automatic Video Selection Fallback
    if v is None:
        target_w = getattr(getattr(d, "selected_stream", None), "width", None)
        target_h = getattr(getattr(d, "selected_stream", None), "height", None)

        candidates = [s for s in videos if is_ok_for_aria2(s)]
        
        if target_w and target_h:
            # Score based on resolution delta and container type
            def vscore(s):
                dw = abs((s.width or 0) - target_w)
                dh = abs((s.height or 0) - target_h)
                ext_bonus = 10 if (s.extension or "").lower() in {"mp4", "m4v", "mov"} else 0
                return (-ext_bonus, dw + dh, -(s.tbr or 0))
            
            v = min(candidates, key=vscore) if candidates else None
        else:
            # Generic fallback: pick best available quality
            def vscore2(s):
                ext_bonus = 10 if (s.extension or "").lower() in {"mp4", "m4v", "mov"} else 0
                return (-(s.quality or 0), -(s.tbr or 0), -ext_bonus)
            
            v = sorted(candidates, key=vscore2)[0] if candidates else None

    # CRITICAL: If the result is HLS (m3u8), aria2c cannot download it. 
    # Logic will return (None, None) to trigger a fallback to the yt-dlp engine.
    if not v or "m3u8" in (v.protocol or "").lower():
        log("[STREAM-SELECT] No suitable progressive video stream found for aria2.", log_level=2, context=ctx)
        return None, None

    # 4. Automatic Audio Selection Fallback (Container Matching)
    compat = {
        "mp4":  {"m4a", "mp4", "aac"},
        "m4v":  {"m4a", "mp4", "aac"},
        "mov":  {"m4a", "mp4", "aac"},
        "webm": {"webm", "opus"},
        "mkv":  {"webm", "opus", "m4a", "aac"},
    }
    
    vext = (v.extension or "").lower()
    allowed_aext = compat.get(vext, {"m4a", "aac", "mp4", "webm", "opus"})

    if a is None:
        def ascore(s):
            # Sort by language rank, then bitrate, then container compatibility
            lang = (getattr(s, "language", None) or getattr(s, "lang", None) or None)
            try:
                lang_rank = preferred_langs.index(lang) if lang in preferred_langs else len(preferred_langs)
            except Exception:
                lang_rank = len(preferred_langs)
            
            ext_ok = 1 if (s.extension or "").lower() in allowed_aext else 0
            return (lang_rank, -int(s.abr or s.tbr or 0), -ext_ok)

        a_candidates = [s for s in audios if (s.extension or "").lower() in allowed_aext]
        if not a_candidates:
            a_candidates = audios[:]  # Fallback to any available audio track

        a = sorted(a_candidates, key=ascore)[0] if a_candidates else None

    log(f"[STREAM-SELECT] Selected V:{v.format_id} ({v.extension}) | A:{a.format_id if a else 'None'}", log_level=1, context=ctx)
    return v, a

def _sync_title_to_ui(d, new_title: str):
    """
    Updates the DownloadItem's display name and notifies the UI.
    Called when yt-dlp resolves the actual video title.
    """
    if new_title and new_title != d.name:
        old_name = d.name
        d.name = validate_file_name(new_title)
        log(f"[Title Sync] Updated: '{old_name}' → '{d.name}'", log_level=1, context="YTDLP-TITLE")
        
        # Trigger UI table refresh
        try:
            config.main_window_q.put(('populate_table', None))
        except Exception:
            pass
        

def _init_sparse_file(d):
    """
    Pre-allocates the target file using Windows Sparse File APIs.
    
    By creating a sparse file, the system reserves the full file size instantly
    on the disk without writing zeros, preventing fragmentation and ensuring
    disk space availability before the download workers start.
    """
    ctx = "SPARSE-PREP"
    try:
        if d.size <= 0:
            log(f"[SPARSE] Cannot pre-allocate: file size unknown ({d.size})", 
                log_level=2, context=ctx)
            return False
        
        os.makedirs(d.temp_folder, exist_ok=True)

        # RESUME GUARD: If the sparse file already exists at the correct size,
        # do NOT recreate it — doing so would zero out bytes that were already
        # written by a previous session, causing corruption on resume.
        if os.path.exists(d.temp_file):
            existing_size = os.path.getsize(d.temp_file)
            if existing_size == d.size:
                log(f"[SPARSE] Resuming: sparse file already exists at correct size "
                    f"({size_format(existing_size)}), skipping pre-allocation.",
                    log_level=1, context=ctx)
                return True
            else:
                log(f"[SPARSE] Existing temp file size mismatch "
                    f"({size_format(existing_size)} vs {size_format(d.size)}), "
                    f"re-allocating.", log_level=2, context=ctx)
                # Wipe the sidecar before recreating the file so that stale
                # resume offsets from the previous (incomplete) session cannot
                # survive into the new allocation.  Without this, the tracker
                # would tell workers to seek past zero-filled regions.
                for ext in (".opdownload", ".opdownload.tmp"):
                    stale = d.temp_file + ext
                    try:
                        if os.path.exists(stale):
                            os.remove(stale)
                            log(f"[SPARSE] Removed stale sidecar: {stale}", log_level=2, context=ctx)
                    except Exception:
                        pass

        log(f"Pre-allocating {size_format(d.size)} sparse file...", 
            log_level=1, context=ctx)
        log(f"Running in thread: {threading.current_thread().name}", 
            log_level=3, context=ctx)
        
        # Native Windows API Call
        success = native_engine.preallocate_file(d.temp_file, d.size)
        
        if success:
            log(f"✓ Sparse file pre-allocated (instant on Windows)", 
                log_level=1, context=ctx)
            return True
        else:
            log(f"✗ Failed to pre-allocate sparse file", 
                log_level=2, context=ctx)
            return False
            
    except Exception as e:
        log(f"[SPARSE] Exception during pre-allocation: {e}", 
            log_level=2, context=ctx)
        return False


def _init_resume_tracker(d):
    """
    Initializes the .opdownload sidecar for byte-level progress tracking.
    
    This tracker maps segments to the sparse file offsets, allowing the 
    engine to detect exactly which bytes were already downloaded in a 
    previous session and skip them during a resume.
    """
    ctx = "SPARSE-PREP"
    try:
        # Ensure temp_folder exists for the sidecar file
        os.makedirs(d.temp_folder, exist_ok=True)
        
        # Access segments (triggers lazy initialization in the DownloadItem)
        segs = d.segments
        
        if not segs:
            log(f"[SPARSE] Warning: No segments available for resume tracker", 
                log_level=2, context=ctx)
            return None
        
        # Debugging: Log high-level segment metadata
        log(f"[SPARSE] Initializing resume tracker with {len(segs)} segments", 
            log_level=3, context=ctx)
        for i, seg in enumerate(segs[:3]):  # Log sample of first 3 segments
            log(f"[SPARSE]   Seg {i}: num={seg.num}, range={seg.range} "
                f"(type: {type(seg.range).__name__}), size={seg.size}", 
                log_level=3, context=ctx)
        
        # Create and initialize the ResumeTracker instance
        tracker = ResumeTracker(d.temp_file)
        tracker.init_segments(segs)
        d.resume_tracker = tracker
        
        # Sync d.downloaded to the sidecar's ground truth.
        # CRITICAL: This must happen unconditionally.  If the previous session
        # was cancelled, d.downloaded still holds the stale cumulative value
        # from the old workers.  Without resetting it here, the overshoot guard
        # (d.downloaded >= d.size) will trigger prematurely during resume,
        # killing workers before they finish and leaving holes in the file.
        total_downloaded = tracker.calculate_total_downloaded()
        d.downloaded = total_downloaded
        if total_downloaded > 0:
            pct = 100 * total_downloaded / d.size if d.size > 0 else 0
            log(f"[SPARSE] Resume detected: {size_format(total_downloaded)} "
                f"already downloaded ({pct:.1f}%)", log_level=1, context=ctx)
        
        log(f"[SPARSE] ✓ Resume tracker initialized successfully", 
            log_level=1, context=ctx)
        return tracker
        
    except Exception as e:
        log(f"[SPARSE] Exception initializing resume tracker: {e}", 
            log_level=2, context=ctx)
        import traceback
        log(f"[SPARSE] Traceback: {traceback.format_exc()}", 
            log_level=3, context=ctx)
        return None



def _thread_manager_sparse(d, emitter=None, workers_done_event=None):
    """
    Manages the lifecycle of worker threads for sparse-mode downloads.
    
    Design principles:
    - Worker Isolation: Each worker runs on a dedicated daemon thread to avoid pool contention.
    - Fault Tolerance: Implements a re-queueing system for segments that fail due to 
      network or server hiccups.
    - Loop Guard: Uses MAX_SEG_RETRIES to prune unrecoverable segments.
    """
    ctx = "SPARSE-ENGINE"
    from modules.worker_sparse import Worker_Sparse

    MAX_SEG_RETRIES = 3  # Total attempts allowed per segment
    max_conn = int(config.max_connections)
    segment_queue = list(d.segments)

    # Track how many times each segment has been attempted: {seg_num: count}
    retry_counts: dict = {}

    # Initialize a fixed pool of reusable workers
    workers = [Worker_Sparse(tag=i, d=d)
               for i in range(min(max_conn, len(d.segments)))]

    # Active map: {Worker_Sparse instance: its running Thread}
    active: dict = {}

    while (segment_queue or active) and d.status == Status.downloading:

        # --- Phase 1: Assign segments to idle workers ---
        idle = [w for w in workers if w not in active]
        for worker in idle:
            if not segment_queue:
                break
            
            seg = segment_queue.pop(0)
            worker.reuse(seg=seg, speed_limit=0)
            
            t = Thread(
                target=worker.run,
                daemon=True,
                name=f"sparse-worker-{worker.tag}"
            )
            active[worker] = t
            t.start()
            
            log(f"[SPARSE] Worker {worker.tag} → segment {seg.num} "
                f"(attempt {retry_counts.get(seg.num, 0) + 1})", 
                log_level=3, context=ctx)

        # --- Phase 2: Retire finished workers and handle re-queuing ---
        for worker in list(active):
            t = active[worker]
            if not t.is_alive():
                t.join()
                del active[worker]

                seg = worker.seg
                if seg is None:
                    continue

                if seg.downloaded:
                    # Successful download
                    log(f"[SPARSE] Segment {seg.num} finished OK", 
                        log_level=3, context=ctx)
                else:
                    # Handle segment failure (Network/Server errors)
                    attempts = retry_counts.get(seg.num, 0) + 1
                    retry_counts[seg.num] = attempts

                    if attempts < MAX_SEG_RETRIES:
                        log(f"[SPARSE] Segment {seg.num} failed (attempt {attempts}/"
                            f"{MAX_SEG_RETRIES}). Re-queuing...", 
                            log_level=2, context=ctx)
                        
                        # Reset in_progress flag so the segment is eligible for pick-up
                        seg.in_progress = False
                        segment_queue.append(seg)
                    else:
                        log(f"[SPARSE] Segment {seg.num} reached MAX_RETRIES. Aborting.", 
                            log_level=2, context=ctx)
                        
                        # Terminal error for this task
                        d.status = Status.error
                        if emitter:
                            try: emitter.status_changed.emit('error')
                            except Exception: pass
                        break  # Stop the manager loop

        time.sleep(0.05)

    # Wait for any lingering worker threads to exit cleanly
    for worker, t in list(active.items()):
        t.join(timeout=300)
        if t.is_alive():
            log(f"[SPARSE] Worker {worker.tag} timed out waiting to finish",
                log_level=2, context=ctx)

    # Signal that all worker file handles are now closed
    if workers_done_event is not None:
        workers_done_event.set()
        log(f"[SPARSE] All workers finished, file handles released", log_level=3, context=ctx)


def _file_manager_sparse(d, keep_segments=False, emitter=None, workers_done_event=None):
    """
    Simplified file manager for sparse downloads (no stitching required).
    
    This manager monitors the resume_tracker to confirm byte-level completion
    and performs the final atomic rename from temp file to target file.
    """
    ctx = "SPARSE-IO"
    
    # --- Phase 1: Completion Monitoring ---
    while d.status == Status.downloading:
        # Check if the sidecar tracker confirms all segments are complete
        if hasattr(d, 'resume_tracker') and d.resume_tracker.is_complete():
            log(f"[SPARSE] Resume tracker: all segments complete", 
                log_level=1, context=ctx)
            d.status = Status.completed
            break
        
        # Hard safety check: ensure we don't exceed expected file size
        if d.size > 0 and d.downloaded >= d.size:
            log(f"[SPARSE] Download reached 100%: {size_format(d.downloaded)}/"
                f"{size_format(d.size)}", log_level=1, context=ctx)
            d.status = Status.completed
            break
        
        time.sleep(0.05)
    
    # Transition: Abort if status is not 'completed' (e.g., cancelled or error)
    if d.status != Status.completed:
        log(f"[SPARSE] Skipping finalization: status={d.status}", 
            log_level=2, context=ctx)
        return
    
    # --- Phase 2: Finalization & Atomic Swap ---
    try:
        target = d.target_file or os.path.join(d.folder, d.name)
        log(f"[SPARSE] Finalizing: renaming to {os.path.basename(target)}", 
            log_level=1, context=ctx)
        
        # Remove collision file if target already exists
        if os.path.exists(target):
            try: os.remove(target)
            except Exception: pass
        
        # CRITICAL: Wait for all worker threads to fully close their file handles
        # before we fsync or rename.  The thread_manager sets this event only after
        # every worker thread's finally block (which calls close_file) has returned.
        # Without this wait, shutil.move can run while a Nim writer is still open,
        # producing a truncated copy if the OS flushes sparse extents lazily.
        if workers_done_event is not None:
            log(f"[SPARSE] Waiting for all worker file handles to close...", log_level=3, context=ctx)
            workers_done_event.wait(timeout=60)

        # fsync the sparse temp file before renaming so that every byte written
        # by the worker threads is guaranteed to be on physical media.  Without
        # this, a rename that crosses a power-failure or abrupt-close boundary
        # can leave the target file with zero-holes even though the workers all
        # reported success.
        try:
            with open(d.temp_file, 'r+b') as _f:
                _f.flush()
                os.fsync(_f.fileno())
            log(f"[SPARSE] fsync complete before rename", log_level=3, context=ctx)
        except Exception as _fe:
            log(f"[SPARSE] fsync warning (non-fatal): {_fe}", log_level=2, context=ctx)

        # Instant rename (uses shutil.move for cross-device support)
        start_time = time.time()
        import shutil
        shutil.move(d.temp_file, target)
        elapsed = time.time() - start_time
        
        log(f"[SPARSE] ✓ Renamed in {elapsed:.3f}s", log_level=1, context=ctx)
        
        # --- Phase 3: Final Size Verification ---
        if os.path.exists(target):
            final_size = os.path.getsize(target)
            if final_size == d.size:
                log(f"[SPARSE] ✓ Verified: {size_format(final_size)}", 
                    log_level=1, context=ctx)
                
                d.status = Status.completed
                d._progress = 100
                
                if emitter:
                    try:
                        emitter.status_changed.emit("completed")
                        emitter.progress_changed.emit(100.0)
                    except Exception: pass

                # CRITICAL: Always check for and execute the callback here
                if d.status == Status.completed:
                    cb = getattr(d, "callback", None)
                    if cb:
                        # Pass both the callback reference and the item itself
                        _execute_callback(cb, d)
                
                notify(f"File: {d.name} \nsaved at: {d.folder}", 
                       title=f"{APP_NAME} - Download completed")
            else:
                log(f"[SPARSE] ✗ Size mismatch: {size_format(final_size)} vs "
                    f"{size_format(d.size)}", log_level=2, context=ctx)
                d.status = Status.failed
        else:
            d.status = Status.failed
    
    except Exception as e:
        log(f"[SPARSE] Finalization error: {e}", log_level=2, context=ctx)
        d.status = Status.failed
    
    finally:
        # Final Cleanup: Remove sidecars and temp artifacts
        try:
            if hasattr(d, 'resume_tracker'):
                d.resume_tracker.cleanup()
            delete_folder(d.temp_folder)
        except Exception:
            pass




def brain(d=None, emitter=None):
    """
    Main orchestration logic that selects the best download engine based on 
    the provided metadata (engine, type, protocol, and URL).
    """
    ctx = "ENGINE-BRAIN"
    log(f"[brain] ENGINE DEBUG — d.engine={getattr(d, 'engine', None)} | d.type={getattr(d, 'type', None)} | "
        f"protocol={getattr(d, 'protocol', None)} | url={getattr(d, 'url', None)}", context=ctx)

    # Resolve the original URL fallback
    orig_url = getattr(d, "original_url", None) or getattr(d, "url", "")

    # =========================================================================
    # BRANCH 1: ARIA2C / TORRENT / MAGNET
    # =========================================================================
    if (getattr(d, "engine", "") in ["aria2", "aria2c"]
            or getattr(d, "ext", "") in ['torrent']
            or (getattr(d, "url", "") or "").startswith("magnet:?")):

        log(f"[brain] aria2c selected for: {d.name}", context=ctx)

        # Ensure original_url is stored for YouTube persistence
        if ("youtube.com" in (d.url or "") or "youtu.be" in (d.url or "")):
            if not getattr(d, "original_url", None) or "googlevideo.com" in (d.url or ""):
                d.original_url = d.url  

        orig_url = getattr(d, "original_url", d.url)

        # YouTube Stream Extraction for Aria2c
        if ("youtube.com" in orig_url or "youtu.be" in orig_url) and not getattr(d, "vid_info", None):
            log(f"[brain] Extracting stream info from YouTube for aria2c...", context=ctx)
            try:
                ydl_opts = get_ytdl_options()
                vid_info = extract_info_blocking(orig_url, ydl_opts)
                d.vid_info = vid_info
            except Exception as e:
                log(f"[brain] Failed to extract info for aria2 decision: {e}", log_level=2, context=ctx)
                d.vid_info = None 

        elif getattr(d, "vid_info", None):
            log(f"[brain] Reusing existing vid_info for {d.name}", context=ctx)

        # Stream Selection Logic
        if getattr(d, "vid_info", None):
            v, a = _select_streams_for_aria2(d, d.vid_info, preferred_langs=getattr(config, "preferred_audio_langs", None))

            if not v:
                log("[brain] No suitable progressive stream for aria2 — falling back to yt-dlp", context=ctx)
                executor.submit(run_ytdlp_download, d, emitter)
                return

            # Update download item with selected stream URLs
            d.eff_url = v.url
            d.url = d.eff_url
            d.format_id = v.format_id
            d.audio_url = a.url if a else None
            d.audio_format_id = a.format_id if a else None

            # Finalize safe filename
            title = d.vid_info.get("title") or d.name
            d.name = validate_file_name(title)

            executor.submit(run_aria2c_video_audio_download, d, emitter)
            return
        else:
            log("[Aria2c] Running normal static file download", context=ctx)
            d.original_url = d.url
            executor.submit(run_aria2c_download, d, emitter)
            return

    # =========================================================================
    # BRANCH 2: YT-DLP (PYTHON API OR EXECUTABLE)
    # =========================================================================
    elif getattr(d, "engine", "") == "yt-dlp":
        log(f"[brain] yt-dlp selected for: {d.name}", context=ctx)

        # Fix 3E — pre-compute format string from batch picker height choice
        if (not getattr(d, "format_id", None)
                and not getattr(d, "_ytdlp_format_override", None)
                and hasattr(d, "_desired_height")):
            dh = d._desired_height
            if dh == 0:
                d._ytdlp_format_override = "bestaudio/best"
            elif dh is not None:
                d._ytdlp_format_override = f"bestvideo[height<={dh}]+bestaudio[height<={dh}]/best"
                
        if config.get_effective_ytdlp() and getattr(config, "use_ytdlp_exe", False):
            log(f'[brain] Running yt-dlp executable for {d.name}', context=ctx)
            executor.submit(run_ytdlp_download_exe, d, emitter)
        else:
            log(f'[brain] Running yt-dlp python api for {d.name}', context=ctx)
            executor.submit(run_ytdlp_download, d, emitter)
        return

    # =========================================================================
    # BRANCH 3: CURL / SPARSE ENGINE
    # =========================================================================
    # elif getattr(d, "engine", "") == "curl":
    #     # Check for DASH compatibility
    #     has_separate_audio = bool(d.audio_url and d.audio_url != d.url)
        
    #     if has_separate_audio:
    #         log(f'[DASH] DASH detected: routing to aria2 video+audio handler', context=ctx)
    #         executor.submit(run_curl_download, d, emitter)
    #         return
    #     else:
    #         # Sparse pre-allocation sequence for multi-connection downloads
    #         if d.size > 0 and int(config.max_connections) > 1:
    #             d.status = Status.stitching
    #             if emitter:
    #                 try:
    #                     from PySide6.QtCore import QMetaObject, Qt, Q_ARG
    #                     # Safe UI updates via QueuedConnection to the main thread
    #                     QMetaObject.invokeMethod(emitter, "progress_mode_changed",
    #                                            Qt.QueuedConnection, Q_ARG(str, 'indeterminate'))
    #                     QMetaObject.invokeMethod(emitter, "status_changed",
    #                                            Qt.QueuedConnection, Q_ARG(str, 'stitching'))
    #                 except Exception:
    #                     emitter.progress_mode_changed.emit('indeterminate')
    #                     emitter.status_changed.emit("stitching")

    #             def _prep_and_download():
    #                 """Background preparation thread for Sparse-mode initialization."""
    #                 try:
    #                     if not _init_sparse_file(d):
    #                         d.status = Status.error
    #                         if emitter: emitter.status_changed.emit('error')
    #                         return
                        
    #                     tracker = _init_resume_tracker(d)
    #                     if tracker is None:
    #                         d.status = Status.error
    #                         if emitter: emitter.status_changed.emit('error')
    #                         return

    #                     d.status = Status.downloading
    #                     if emitter:
    #                         try:
    #                             emitter.progress_mode_changed.emit('determinate')
    #                             emitter.status_changed.emit('downloading')
    #                         except Exception: pass

    #                     # Shared event: thread_manager sets it after all worker
    #                     # file handles are closed; file_manager waits on it
    #                     # before fsync/rename to avoid racing a still-open handle.
    #                     _workers_done = threading.Event()

    #                     # Launch dedicated Sparse manager threads
    #                     fm = threading.Thread(target=_file_manager_sparse, 
    #                                         kwargs=dict(d=d, keep_segments=False, emitter=emitter, workers_done_event=_workers_done),
    #                                         daemon=True, name="sparse-file-mgr")
    #                     tm = threading.Thread(target=_thread_manager_sparse,
    #                                         args=(d, emitter, _workers_done), 
    #                                         daemon=True, name="sparse-thread-mgr")
    #                     fm.start()
    #                     tm.start()

    #                 except Exception as e:
    #                     log(f"[SPARSE] Prep thread error: {e}", log_level=2, context="ENGINE-SPARSE")
    #                     d.status = Status.error
    #                     if emitter: emitter.status_changed.emit('error')

    #             t = threading.Thread(target=_prep_and_download, daemon=True, name="sparse-prep")
    #             t.start()

    elif getattr(d, "engine", "") == "curl":
        protocol = (getattr(d, "protocol", "") or "").lower()
        has_separate_audio = bool(d.audio_url and d.audio_url != d.url)

        # m3u8 / HLS streams cannot use sparse pre-allocation — route directly to run_curl_download
        if 'm3u8' in protocol:
            log(f'[cURL] HLS/m3u8 detected (protocol={protocol}): routing to run_curl_download', context=ctx)
            executor.submit(run_curl_download, d, emitter)
            return

        if has_separate_audio:
            log(f'[DASH] DASH detected: routing to run_curl_download', context=ctx)
            executor.submit(run_curl_download, d, emitter)
            return

        # Sparse pre-allocation sequence for multi-connection static downloads
        if d.size > 0 and int(config.max_connections) > 1:
            d.status = Status.stitching
            if emitter:
                try:
                    from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                    QMetaObject.invokeMethod(emitter, "progress_mode_changed",
                                           Qt.QueuedConnection, Q_ARG(str, 'indeterminate'))
                    QMetaObject.invokeMethod(emitter, "status_changed",
                                           Qt.QueuedConnection, Q_ARG(str, 'stitching'))
                except Exception:
                    emitter.progress_mode_changed.emit('indeterminate')
                    emitter.status_changed.emit("stitching")

            def _prep_and_download():
                """Background preparation thread for Sparse-mode initialization."""
                try:
                    if not _init_sparse_file(d):
                        d.status = Status.error
                        if emitter: emitter.status_changed.emit('error')
                        return
                    
                    tracker = _init_resume_tracker(d)
                    if tracker is None:
                        d.status = Status.error
                        if emitter: emitter.status_changed.emit('error')
                        return

                    d.status = Status.downloading
                    if emitter:
                        try:
                            emitter.progress_mode_changed.emit('determinate')
                            emitter.status_changed.emit('downloading')
                        except Exception: pass

                    _workers_done = threading.Event()

                    fm = threading.Thread(target=_file_manager_sparse, 
                                        kwargs=dict(d=d, keep_segments=False, emitter=emitter, workers_done_event=_workers_done),
                                        daemon=True, name="sparse-file-mgr")
                    tm = threading.Thread(target=_thread_manager_sparse,
                                        args=(d, emitter, _workers_done), 
                                        daemon=True, name="sparse-thread-mgr")
                    fm.start()
                    tm.start()

                except Exception as e:
                    log(f"[SPARSE] Prep thread error: {e}", log_level=2, context="ENGINE-SPARSE")
                    d.status = Status.error
                    if emitter: emitter.status_changed.emit('error')

            t = threading.Thread(target=_prep_and_download, daemon=True, name="sparse-prep")
            t.start()
        else:
            # Small file or single connection — go direct
            log(f'[cURL] Static file: routing directly to run_curl_download', context=ctx)
            executor.submit(run_curl_download, d, emitter)
   


def run_curl_download(d, emitter=None):
    """
    Initiates the native multi-connection download sequence.
    
    This function acts as a launcher that:
    1. Pre-processes HLS (m3u8) manifests if necessary.
    2. Spawns the 'file_manager' to handle segment stitching on disk.
    3. Spawns the 'thread_manager' to coordinate concurrent network workers.
    4. Runs a background 'monitor_download_sync' thread to handle timeouts and finalization.
    """
    ctx = "ENGINE-CURL"
    d.status = Status.downloading
    
    log('-' * 100)
    log(f'Start downloading file: "{d.name}", size: {size_format(getattr(d, "size", 0))}, '
        f'to: {d.folder} with engine: {d.engine}', context=ctx) 

    # Restore any existing progress metadata
    d.load_progress_info()

    # --- HLS / Manifest Pre-processing ---
    if 'm3u8' in (getattr(d, "protocol", "") or ""):
        keep_segments = True
        # Parse the manifest and build the initial segment list
        success = pre_process_hls(d)
        if not success:
            log(f"HLS Pre-processing failed for {d.name}", log_level=2, context=ctx)
            d.status = Status.error
            return
    else:
        # Standard static file; segments are usually byte-ranges
        keep_segments = False

    # ── Launch Management Sub-Systems ──
    # file_manager handles disk I/O; thread_manager handles network I/O
    executor.submit(file_manager, d, keep_segments, emitter)
    executor.submit(thread_manager, d, emitter)

    start_time = time.time()
    max_timeout = 180  # 3-minute stall protection

    # =========================================================================
    # MONITORING THREAD
    # =========================================================================
    def monitor_download_sync():
        """
        Observes the download lifecycle from a detached thread.
        Handles timeouts, manual cancellations, and final notification/cleanup.
        """
        while True:
            # Polling interval (0.5s) balanced for UI responsiveness and CPU usage
            time.sleep(0.5) 

            # Normalize progress attribute access
            progress_val = getattr(d, "progress", None)
            if progress_val is None:
                progress_val = getattr(d, "_progress", 0)

            # 1. Timeout Check: If no progress is made within 3 minutes of start
            if time.time() - start_time > max_timeout and progress_val == 0:
                d.status = Status.error
                log(f"Timeout reached for {d.name}. Marking as failed.", context=ctx)
                if emitter:
                    emitter.status_changed.emit("error")
                    emitter.failed.emit(d)
                break

            # 2. Manual Cancellation
            if d.status == Status.cancelled:
                log(f"Cancelled manually for: {d.name}", context=ctx)

                if getattr(d, "in_queue", False):
                    d.status = Status.queued
                break


            # 3. Successful Completion
            if d.status == Status.completed:
                try:
                    # Signal main window for potential restoration (e.g., from tray)
                    config.main_window_q.put(('restore_window', ''))
                except Exception: pass
                
                notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
                
                # Cleanup .watch sentinel files used for monitoring
                watch_file = os.path.join(d.folder, f"_temp_{d.name}.watch")
                if os.path.exists(watch_file):
                    try: os.remove(watch_file)
                    except Exception: pass
                break

            # 4. Error State
            if d.status == Status.error:
                log(f"Error detected for: {d.name}", context=ctx)
                break

        # Post-Download Callback Dispatcher
        if d.status == Status.completed:
            cb = getattr(d, "callback", None)
            if cb:
                # Pass both the callback reference and the item itself
                _execute_callback(cb, d)
       

        log(f'Brain monitor {getattr(d, "num", "?")} exiting.', context=ctx)

    # Launch monitor thread immediately
    Thread(target=monitor_download_sync, daemon=True).start()




def run_aria2c_download(d, emitter=None):
    """
    Orchestrates and monitors an aria2c RPC task (Static, Torrent, or Magnet).
    
    Includes an automatic content-switching sentinel for BitTorrent tasks where
    the initial GID only handles metadata extraction before spawning the real payload.
    """
    ctx = "ARIA2-MONITOR"
    
    # ── Signal Helpers ──
    def emit_status(s):
        if emitter:
            try: emitter.status_changed.emit(s)
            except Exception: pass

    def emit_log(msg):
        if emitter:
            try: emitter.log_updated.emit(str(msg))
            except Exception: pass

    def emit_progress(pct):
        if emitter:
            try: emitter.progress_changed.emit(int(pct))
            except Exception: pass

    def _safe_int(x):
        try: return int(x)
        except Exception: return 0

    aria2 = aria2c_manager.get_api()

    def _pick_content_download(api, current_gid):
        """
        Detects the 'Real' download entry for torrents.
        Aria2 often spawns a secondary GID for the content once metadata is fetched.
        """
        def is_content(dl):
            try:
                f0 = dl.files[0].path if dl.files else ""
                # Content has length and isn't just a .torrent metadata file
                return _safe_int(dl.total_length) > 0 and not f0.lower().endswith(".torrent")
            except Exception: return False

        # 1. Check current GID
        try:
            dl = api.get_download(current_gid)
            if dl and is_content(dl): return dl
        except Exception: pass

        # 2. Scan for orphaned content GIDs in the daemon
        try:
            for dl in (api.get_active() or []) + (api.get_waiting() or []):
                if is_content(dl): return dl
        except Exception: pass
        return None

    # ── Initialization Path ──
    url = d.url or d.eff_url or ""
    is_torrent = url.lower().endswith(".torrent") or d.name.lower().endswith(".torrent")
    is_magnet = url.startswith("magnet:?")
    options = {"dir": d.folder, "out": d.name}

    try:
        emit_status("pending")
        if is_torrent:
            # Handle remote .torrent fetching
            torrent_path = os.path.join(d.folder, d.name if d.name.lower().endswith(".torrent") else (d.name + ".torrent"))
            if url.startswith("http"):
                import requests
                r = requests.get(url, timeout=30); r.raise_for_status()
                with open(torrent_path, "wb") as f: f.write(r.content)
            
            added = aria2.add_torrent(torrent_path, options=options)
            d.protocol = "bittorrent"
        elif is_magnet:
            added = aria2.add_magnet(url, options=options)
            d.protocol = "bittorrent"
        else:
            added = aria2.add_uris([url], options=options)

        d.aria_gid = added.gid
        d.status = config.Status.downloading
        emit_status("downloading")
        log(f"Aria2c task started: GID={d.aria_gid}", log_level=1, context=ctx)

    except Exception as e:
        log(f"Aria2c start failed: {e}", log_level=3, context=ctx)
        d.status = config.Status.error
        emit_status("error")
        return

    # ── Persistent Monitor Loop ──
    last_emit = 0
    idle_dwell_start = None # Tracks 100% completion before status flip

    try:
        while True:
            time.sleep(0.5)
            
            # Retrieve current status from RPC
            try: download = aria2.get_download(d.aria_gid)
            except Exception: download = None

            # Self-Healing: Re-add if task vanished unexpectedly
            if not download:
                if d.status in (config.Status.cancelled, "paused"): return # Exit if user-stopped
                log(f"GID {d.aria_gid} lost. Attempting recovery...", log_level=2, context=ctx)
                # (Re-add logic implementation same as start logic...)
                continue

            # Content Switching: Lock onto the real payload GID
            if is_torrent or is_magnet:
                content = _pick_content_download(aria2, download.gid)
                if content and content.gid != d.aria_gid:
                    log(f"Switching tracking to content GID: {content.gid}", log_level=1, context=ctx)
                    d.aria_gid = content.gid
                    download = content

            # Data Sync: RPC → DownloadItem
            d.size = _safe_int(download.total_length)
            d.downloaded = _safe_int(download.completed_length)
            d._speed = _safe_int(download.download_speed)
            status_raw = (getattr(download, "status", "") or "").lower()

            # Handle Filename adoption from Torrent metadata
            try:
                if download.files and download.files[0].path:
                    d.name = os.path.basename(download.files[0].path)
            except Exception: pass

            # UI Update Throttle
            if time.time() - last_emit > 0.5:
                last_emit = time.time()
                emit_progress(d.progress)

            # ── Terminal State Detection ──
            
            # Path 1: Logic-based Completion (Dwell Timer)
            # Sometimes aria2c finishes but stays 'active' while checking files
            if d.size > 0 and d.downloaded >= d.size:
                if d._speed <= 1 and status_raw in ("active", "waiting"):
                    if idle_dwell_start is None: idle_dwell_start = time.time()
                    if time.time() - idle_dwell_start >= 8: # 8s validation dwell
                        status_raw = "complete"
                else: idle_dwell_start = None

            # Path 2: Official Status completion
            if status_raw in ("complete", "seeding"):
                d.status = config.Status.completed
                emit_status("completed")
                emit_progress(100)
                notify(f"File: {d.name}\nSaved: {d.folder}", title="Download Complete")
                break

            if status_raw in ("error", "removed"):
                d.status = config.Status.error
                emit_status("error")
                break

            if status_raw == "paused":
                d.status = config.Status.cancelled if not d.in_queue else config.Status.queued
                emit_status("paused")
                return
            

    except Exception as e:
        log(f"Fatal monitor crash: {e}", log_level=3, context=ctx)
        d.status = config.Status.error
        emit_status("error")

    finally:
        if d.status == Status.completed:
            cb = getattr(d, "callback", None)
            if cb:
                # Pass both the callback reference and the item itself
                _execute_callback(cb, d)


def run_aria2c_video_audio_download(d, emitter=None):
    """
    Manages dual-stream HTTP downloads (DASH) via aria2c.
    
    Workflow:
    1. Derive temporary part filenames (.video.mp4 and .audio.m4a).
    2. Attach to existing GIDs or spawn two new aria2c tasks.
    3. Monitor both tasks simultaneously and calculate aggregate progress.
    4. Validate part integrity (check for .aria2 sidecar removal).
    5. Execute asynchronous FFmpeg merge into a .tmp file.
    6. Atomically swap .tmp for the final target file.
    """
    ctx = "ARIA2-DASH"
    
    # ── Signal Helpers ──
    def emit_status(s):
        if emitter:
            try: emitter.status_changed.emit(s)
            except: pass

    def emit_progress(p):
        if emitter:
            try: emitter.progress_changed.emit(int(p))
            except: pass

    def emit_log(msg):
        if emitter:
            try: emitter.log_updated.emit(str(msg))
            except: pass

    # ── Path & Filename Derivation ──
    # Strip any extension that aria2c may have already added to d.name (e.g. ".audio.m4a")
    # We always derive the base from the original title, not from whatever aria2c sets later.
    raw_name = d.name or "download"
    # Remove known part-file suffixes so we always get the clean title
    for suffix in (".video.mp4", ".audio.m4a", ".audio.webm", ".merge.tmp.mp4"):
        if raw_name.lower().endswith(suffix):
            raw_name = raw_name[: -len(suffix)]
            break
    base = safe_filename(os.path.splitext(raw_name)[0]) or "download"

    final_target = d.target_file or os.path.join(d.folder, base + ".mp4")
    if not final_target.lower().endswith(".mp4"):
        final_target = os.path.splitext(final_target)[0] + ".mp4"
    d.target_file = final_target

    # Define temporary part paths
    video_part = os.path.join(d.folder, base + ".video.mp4")
    audio_is_present = bool(d.audio_url and d.audio_url != d.url)
    
    if audio_is_present:
        # Match audio container to video for easier muxing
        a_ext = ".m4a" if video_part.lower().endswith((".mp4", ".m4v", ".mov")) else ".webm"
        audio_part = os.path.join(d.folder, base + ".audio" + a_ext)
        d.audio_file = audio_part
    else:
        audio_part = None

    video_aria2 = video_part + ".aria2"
    audio_aria2 = (audio_part + ".aria2") if audio_part else None

    # Snapshot the clean title so aria2c file-name adoption cannot corrupt d.name
    _clean_base = base

    # ── Daemon Connection ──
    aria2 = aria2c_manager.get_api()
    if not aria2:
        d.status = Status.error
        emit_status("error")
        log("Aria2c API unavailable for DASH task.", log_level=3, context=ctx)
        return

    d.status = Status.downloading
    emit_status("downloading")

    # ── Task Initialization (Attach or Add) ──
    
    def _get_dl(gid):
        try: return aria2.get_download(gid) if gid else None
        except: return None

    # Video Task Setup
    v_dl = _get_dl(getattr(d, "aria_gid", None))
    if not v_dl:
        opts_v = {
            "dir": d.folder,
            "out": os.path.basename(video_part),
            "continue": "true",
            "max-connection-per-server": str(config.aria2c_config["max_connections"]),
        }
        added_v = aria2.add_uris([d.url], options=opts_v)
        d.aria_gid = added_v.gid
        v_dl = _get_dl(d.aria_gid)

    # Audio Task Setup
    a_dl = None
    if audio_is_present:
        a_dl = _get_dl(getattr(d, "audio_gid", None))
        if not a_dl:
            opts_a = {
                "dir": d.folder,
                "out": os.path.basename(audio_part),
                "continue": "true",
                "max-connection-per-server": str(config.aria2c_config["max_connections"]),
            }
            added_a = aria2.add_uris([d.audio_url], options=opts_a)
            d.audio_gid = added_a.gid
            a_dl = _get_dl(d.audio_gid)

    # ── Concurrent Monitor Loop ──
    last_ui_update = -1

    def _safe_bytes(val):
        """Convert aria2c's string byte values to int safely."""
        try:
            return int(val or 0)
        except (TypeError, ValueError):
            return 0

    def _safe_pct(val):
        """Convert aria2c's progress (may be '34.50%' string or float/int) to a 0-100 float."""
        try:
            s = str(val or "0").replace("%", "").strip()
            return float(s)
        except (TypeError, ValueError):
            return 0.0

    try:
        while True:
            time.sleep(0.5)
            v_dl = _get_dl(d.aria_gid)
            a_dl = _get_dl(d.audio_gid) if audio_is_present else None

            # Handle Manual Pause/Cancel
            if (v_dl and v_dl.status == "paused") or (a_dl and a_dl.status == "paused"):
                d.status = Status.cancelled
                emit_status("paused")
                log(f"DASH task paused manually: {_clean_base}", log_level=1, context=ctx)
                return

            v_done = v_dl.status in ("complete", "seeding") if v_dl else False
            a_done = (a_dl.status in ("complete", "seeding")) if a_dl else (not audio_is_present)

            # Combined Stats Calculation — always use safe integer conversion
            try:
                v_dl_bytes = _safe_bytes(v_dl.completed_length if v_dl else 0)
                v_total_bytes = _safe_bytes(v_dl.total_length if v_dl else 0)
                v_speed_bytes = _safe_bytes(v_dl.download_speed if v_dl else 0)
                a_dl_bytes = _safe_bytes(a_dl.completed_length if a_dl else 0)
                a_total_bytes = _safe_bytes(a_dl.total_length if a_dl else 0)
                a_speed_bytes = _safe_bytes(a_dl.download_speed if a_dl else 0)

                v_stats = {"speed": v_speed_bytes, "downloaded": v_dl_bytes, "size": v_total_bytes}
                a_stats = {"speed": a_speed_bytes, "downloaded": a_dl_bytes, "size": a_total_bytes}

                stats = native_engine.calculate_stats([v_stats, a_stats] if audio_is_present else [v_stats])
                combined_pct = int(stats.get("progress", 0))
                d._speed = stats.get("total_speed", 0)
                d.remaining_time = stats.get("eta_seconds", 0)

                # Update d.downloaded / d.size for the table progress bar
                d.downloaded = v_dl_bytes + a_dl_bytes
                d.size = (v_total_bytes + a_total_bytes) if (v_total_bytes + a_total_bytes) > 0 else d.size

            except Exception:
                # Fallback: parse progress strings from aria2c directly
                v_pct = _safe_pct(getattr(v_dl, "progress", 0)) if v_dl else 0.0
                a_pct = _safe_pct(getattr(a_dl, "progress", 0)) if a_dl else 0.0
                combined_pct = int((v_pct + a_pct) / (2 if audio_is_present else 1))

            if combined_pct != last_ui_update:
                emit_progress(combined_pct)
                d._progress = combined_pct
                last_ui_update = combined_pct

            # Guard: never let aria2c's filename adoption overwrite our clean title
            d.name = _clean_base + ".mp4"

            # ── Transition to Merging ──
            if v_done and a_done:
                if not audio_is_present:
                    # Single stream finalize
                    if os.path.exists(video_part):
                        rename_file(video_part, final_target)
                    d.status = Status.completed
                    break

                # Multi-stream merge logic
                d.status = Status.merging_audio
                emit_status("merging_audio")
                log(f"Download complete. Initiating FFmpeg merge for: {_clean_base}", log_level=1, context=ctx)

                temp_merge = os.path.join(d.folder, _clean_base + ".merge.tmp.mp4")

                # Validation: Ensure aria2c has released file locks and finished writing
                if os.path.exists(video_aria2) or (audio_aria2 and os.path.exists(audio_aria2)):
                    log("Merge blocked: Part files still marked as active by engine.", log_level=2, context=ctx)
                    d.status = Status.error
                    break

                # Verify both part files actually exist before merging
                if not os.path.exists(video_part):
                    log(f"Merge aborted: video part missing: {video_part}", log_level=2, context=ctx)
                    d.status = Status.error
                    break
                if audio_is_present and not os.path.exists(audio_part):
                    log(f"Merge aborted: audio part missing: {audio_part}", log_level=2, context=ctx)
                    d.status = Status.error
                    break

                # Run Merge — pass the explicit paths, bypassing fuzzy file-finder
                ffmpeg_path = config.get_effective_ffmpeg()
                merge_ok = False
                merge_err_msg = ""
                for cmd_args in [
                    # Attempt 1: explicit stream-copy mapping
                    [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
                     "-i", video_part, "-i", audio_part,
                     "-map", "0:v:0", "-map", "1:a:0",
                     "-c", "copy", "-movflags", "+faststart", temp_merge],
                    # Attempt 2: wildcard mapping
                    [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
                     "-i", video_part, "-i", audio_part,
                     "-map", "0:v", "-map", "1:a",
                     "-c", "copy", "-movflags", "+faststart", temp_merge],
                    # Attempt 3: re-encode audio for compatibility
                    [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
                     "-i", video_part, "-i", audio_part,
                     "-map", "0:v:0", "-map", "1:a:0",
                     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                     "-movflags", "+faststart", temp_merge],
                ]:
                    try:
                        kwargs = {"capture_output": True, "text": True}
                        if os.name == "nt":
                            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                        result = subprocess.run(cmd_args, **kwargs)
                        if result.returncode == 0 and os.path.exists(temp_merge) and os.path.getsize(temp_merge) > 0:
                            merge_ok = True
                            break
                        else:
                            merge_err_msg = (result.stderr or "").strip()
                            log(f"[ARIA2-DASH] FFmpeg attempt failed: {merge_err_msg[:200]}", log_level=2, context=ctx)
                    except Exception as fe:
                        merge_err_msg = str(fe)
                        log(f"[ARIA2-DASH] FFmpeg subprocess error: {fe}", log_level=2, context=ctx)

                if not merge_ok:
                    log(f"FFmpeg Merge Failure: {merge_err_msg}", log_level=3, context=ctx)
                    d.status = Status.error
                    break

                # ── Finalization ──
                if os.path.exists(final_target): os.remove(final_target)
                rename_file(temp_merge, final_target)

                _apply_postprocessing(d, emitter)

                # Cleanup temporary segments
                for f in (video_part, audio_part, video_aria2, audio_aria2):
                    if f and os.path.exists(f):
                        try: os.remove(f)
                        except Exception: pass

                d.name = _clean_base + ".mp4"
                d.status = Status.completed
                emit_progress(100)
                notify(f"DASH Merged: {d.name}", title="Download Complete")
                break

            if d.status == Status.cancelled: break

    except Exception as e:
        log(f"DASH Monitor Exception: {e}", log_level=3, context=ctx)
        d.status = Status.error
    finally:
        emit_status(d.status)


def probe_ffmpeg_file(file_path: str, ffmpeg_path: str) -> bool:
    """Returns True if file is valid and ffmpeg can read it."""
    try:
        result = subprocess.run(
            [ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-i", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except Exception as e:
        log(f"[ffprobe] Failed to probe {file_path}: {e}")
        return False

# ---------- Helpers (place near top of module or in same file) ----------
_RE_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\%")
_RE_DOWNLOAD_BYTES = re.compile(r"([\d\.]+(?:[KMGTP]?i?B))\s*/\s*([\d\.]+(?:[KMGTP]?i?B))", re.IGNORECASE)
_RE_SPEED = re.compile(r"([\d\.,]+(?:[KMGTP]?i?B))/s", re.IGNORECASE)
_RE_ETA = re.compile(r"ETA\s+([0-9:\-]+)", re.IGNORECASE)
_RE_BYTES_NUM = re.compile(r"([\d\.,]+)\s*([KMGTP]?i?B)", re.IGNORECASE)
_RE_PURE_NUM = re.compile(r"[-+]?\d*\.?\d+")
# matches lines like: " 98.3% of  566.23MiB" or "1.3% of ~  34.42MiB"
_RE_PERCENT_OF_TOTAL = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%\s+of\s+~?\s*([\d\.]+(?:[KMGTP]?i?B))", re.IGNORECASE)


def parse_human_size_to_bytes(s):
    """
    Converts strings like '34.42MiB' or '1.2GiB' into raw integer bytes.
    Supports binary units (KiB, MiB, etc.) commonly used by yt-dlp.
    """
    if not s or not isinstance(s, (str, int, float)):
        return None
    
    s = str(s).strip().replace("~", "").replace(",", "")
    match = _RE_BYTES_NUM.search(s)
    
    if not match:
        try: return int(float(s))
        except: return None
        
    value = float(match.group(1))
    unit = match.group(2).lower()
    
    # Binary power multipliers
    multipliers = {
        "kb": 1024, "kib": 1024,
        "mb": 1024**2, "mib": 1024**2,
        "gb": 1024**3, "gib": 1024**3,
        "tb": 1024**4, "tib": 1024**4
    }
    
    return int(value * multipliers.get(unit, 1))

def parse_speed_to_bps(s):
    """Convert speed strings like '66.47KiB/s' or '1.56MiB/s' to bytes/sec (float)."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if not s:
        return None
    # remove trailing '/s' if present
    s_clean = s.replace("/s", "").strip()
    # try parse as size then convert to bytes (per second)
    b = parse_human_size_to_bytes(s_clean)
    if b is not None:
        return float(b)
    # fallback: extract pure numeric
    m = _RE_PURE_NUM.search(s_clean)
    if m:
        try:
            return float(m.group(0))
        except Exception:
            return None
    return None

def _enqueue_output(stream, q):
    """
    Background reader that feeds stdout/stderr into a thread-safe Queue.
    
    Crucial for avoiding 'Deadlock' where the executable stops running 
    because its output buffer is full and the main app hasn't read it yet.
    """
    try:
        # readline returns an empty string only at EOF
        for line in iter(stream.readline, ""):
            if not line: break
            q.put(line)
    except Exception:
        pass
    finally:
        try: stream.close()
        except: pass

def _build_cli_args_for_download(d, ydl_opts: dict, use_progress_template: bool = True):
    args = []
    outtmpl = ydl_opts.get("outtmpl")
    if outtmpl:
        args += ["-o", outtmpl]
    if ydl_opts.get("format"):
        args += ["-f", str(ydl_opts["format"])]
    ffmpeg_location = ydl_opts.get("ffmpeg_location")
    if ffmpeg_location:
        args += ["--ffmpeg-location", str(ffmpeg_location)]
    if ydl_opts.get("retries") is not None:
        args += ["--retries", str(ydl_opts.get("retries"))]
    if ydl_opts.get("continuedl", False):
        args.append("--continue")
    if ydl_opts.get("nopart", False):
        args.append("--no-part")
    cfd = ydl_opts.get("concurrent_fragment_downloads")
    if cfd is not None:
        # newer flag name; adjust if your yt-dlp version differs
        args += ["--concurrent-fragments", str(cfd)]
    if ydl_opts.get("proxy"):
        args += ["--proxy", str(ydl_opts.get("proxy"))]
    cookiefile = ydl_opts.get("cookiesfile") or ydl_opts.get("cookiefile") or ydl_opts.get("cookies")
    if cookiefile:
        args += ["--cookies", str(cookiefile)]
    if ydl_opts.get("writeinfojson"):
        args.append("--write-info-json")
    if ydl_opts.get("writedescription"):
        args.append("--write-description")
    if ydl_opts.get("writeannotations"):
        args.append("--write-annotations")
    if ydl_opts.get("writemetadata"):
        args.append("--write-metadata")
    if ydl_opts.get("merge_output_format"):
        args += ["--merge-output-format", str(ydl_opts.get("merge_output_format"))]
    if ydl_opts.get("ignore_errors", False):
        args.append("--ignore-errors")
    if ydl_opts.get("prefer_insecure", False):
        args.append("--prefer-insecure")

    # Respect a special quiet_for_background flag but otherwise ensure progress visible
    if ydl_opts.get("quiet_for_background", False):
        args.append("--quiet")
    else:
        if ydl_opts.get("no_warnings", True):
            args.append("--no-warnings")

    # ensure newline-terminated progress lines
    args.append("--newline")

    # optional: progress-template for machine-friendly progress
    if use_progress_template:
        # Template returns JSON-ish line that we try to parse
        template = '{"progress":%(progress._percent_str)r,"downloaded":%(progress.downloaded_bytes)d,"total":%(progress.total_bytes)d,"speed":%(progress.speed)r,"eta":%(progress.eta)r}'
        args += ["--progress-template", template]

    return args

# ---------- Patched run_ytdlp_download_exe ----------
def run_ytdlp_download_exe(d, emitter=None, exe_timeout: float = 3600.0, use_progress_template: bool = False):
    """
    Download via yt-dlp executable while streaming progress to `emitter`.
    Must be executed in a worker thread (do not call on main/UI thread).
    """
    log(f"[yt-dlp-exe] Starting download: {getattr(d, 'name', 'unknown')}")
    d.status = Status.downloading
    # ensure numeric defaults exist
    d._progress = 0
    d.remaining_parts = 1
    d.last_known_progress = 0
    d.downloaded = getattr(d, "downloaded", 0) or 0
    d.size = getattr(d, "size", 0) or 0
    # keep compatibility with code that uses d.total_size
    if not getattr(d, "total_size", None):
        try:
            d.total_size = d.size
        except Exception:
            pass
    
    ctx = "yt-dlp-exe"

    # --- NEW: single “connection” row for yt-dlp in the download window ---
    try:
        if not hasattr(d, "connection_stats") or not isinstance(d.connection_stats, list):
            d.connection_stats = []
        if not d.connection_stats:
            d.connection_stats.append(
                {"downloaded": int(d.downloaded or 0), "info": "Receiving data..."}
            )
        else:
            d.connection_stats[0]["downloaded"] = int(d.downloaded or 0)
            d.connection_stats[0]["info"] = "Receiving data..."
    except Exception:
        pass

    # Update d.name from video title if available (preserves original title for video files)
    if hasattr(d, 'vid_info') and d.vid_info:
        title = d.vid_info.get("title") or d.name
        d.name = validate_file_name(title)
        log(f"[yt-dlp-exe] Updated filename from video title: {d.name}", log_level=2)

    # output_path = os.path.join(d.folder, d.name)
    ffmpeg_path = get_effective_ffmpeg() or os.path.join(getattr(config, "sett_folder", ""), "ffmpeg.exe")

    # Always split the extension to get a clean base for the template
    bare_title, original_ext = os.path.splitext(d.name)

    is_media_site = any(x in d.url for x in ["youtube.com", "youtu.be", "vimeo.com", "tiktok.com"])


    if getattr(d, 'vid_info', None):
        # Scenario: Manual download with full info
        output_template = os.path.join(d.folder, f"{bare_title}.%(ext)s")
    else:
        # Check if this is a YouTube/Media link or a direct static file
        is_media_site = any(x in d.url for x in ["youtube.com", "youtu.be", "vimeo.com", "tiktok.com"])
        
        if is_media_site:
            # Scenario: Batch YouTube (Forces yt-dlp to fetch the real title)
            output_template = os.path.join(d.folder, "%(title)s.%(ext)s")
        else:
            # Scenario: Static Files (e.g. Kingdom...zip)
            # Using d.name directly prevents the ".unknown_video" bug
            output_template = os.path.join(d.folder, d.name)

    log(f'Output template: {output_template}', context=ctx)

    # Fix 3C — honour format chosen in the batch resolution picker
    format_code = None
    if getattr(d, "format_id", None) and getattr(d, "audio_format_id", None):
        format_code = f"{d.format_id}+{d.audio_format_id}"
    elif getattr(d, "format_id", None):
        format_code = d.format_id
    elif getattr(d, "_ytdlp_format_override", None):
        format_code = d._ytdlp_format_override
    else:
        dh = getattr(d, "_desired_height", None)
        if dh is None:
            format_code = "bestvideo+bestaudio/best"
        elif dh == 0:
            format_code = "bestaudio/best"
        else:
            format_code = f"bestvideo[height<={dh}]+bestaudio[height<={dh}]/best"

    # prepare proxy url if needed
    proxy_url = None
    if getattr(config, "proxy", ""):
        proxy_url = config.proxy
        if getattr(config, "proxy_user", None) and getattr(config, "proxy_pass", None):
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(proxy_url)
            proxy_url = urlunparse(parsed._replace(netloc=f"{config.proxy_user}:{config.proxy_pass}@{parsed.hostname}:{parsed.port}"))

    # build ydl_opts similar to python api version
    def _cfg_int(x, default=0):
        try:
            return int(x)
        except Exception:
            try:
                return int(float(x))
            except Exception:
                return default

    ydl_opts = {
        "outtmpl": output_template,
        "retries": _cfg_int(config.ytdlp_config.get("retries", 10), 10),
        "continuedl": True,
        "nopart": False,
        "concurrent_fragment_downloads": _cfg_int(config.ytdlp_config.get("concurrent_fragment_downloads", 5), 5),
        "ffmpeg_location": ffmpeg_path,
        "format": format_code,
        "writeinfojson": bool(config.ytdlp_config.get("writeinfojson", True)),
        "writedescription": bool(config.ytdlp_config.get("writedescription", False)),
        "writeannotations": bool(config.ytdlp_config.get("writeannotations", False)),
        "writemetadata": bool(config.ytdlp_config.get("writemetadata", False)),
        "proxy": proxy_url,
        "cookiesfile": config.ytdlp_config.get("cookiesfile", None),
        "ignore_errors": bool(config.ytdlp_config.get("ignore_errors", True)),
        "prefer_insecure": bool(config.ytdlp_config.get("prefer_insecure", False)),
        "quiet_for_background": False,
        "no_warnings": bool(config.ytdlp_config.get("no_warnings", True)),
    }


    # Merge Advanced options from user settings
    try:
        advanced = get_advanced_opts(d)
        if advanced: ydl_opts.update(advanced)
    except Exception as e:
        log(f"Could not apply advanced opts: {e}", log_level=2, context=ctx)


    exe = config.get_effective_ytdlp() #getattr(config, "yt_dlp_exe", None)
    if not exe or not os.path.isfile(exe):
        raise FileNotFoundError(f"yt-dlp executable not found: {exe}")

    cli_args = _build_cli_args_for_download(d, ydl_opts, use_progress_template=use_progress_template)
    cmd = [exe] + cli_args + [d.url]
    
    # Launch process combining stderr into stdout so we capture everything
    kwargs = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si

    proc = subprocess.Popen(cmd, **kwargs)

    # proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

    q = queue.Queue()
    reader = Thread(target=_enqueue_output, args=(proc.stdout, q), daemon=True)
    reader.start()

    try:
        start_time = time.time()
        last_progress_emit = 0.0

        while True:
            # 1. CRITICAL: Check status at the start of EVERY iteration
            # This handles both Cancel (cancelled) and Pause (queued)
            current_status = getattr(d, "status", None)
            if current_status in (Status.cancelled, Status.queued):
                try:
                    # Use kill() for an immediate stop; terminate() can be ignored by some processes
                    proc.kill() 
                    log(f"[yt-dlp-exe] Stopped process for {d.name} (Status: {current_status})")
                except Exception:
                    pass
                
                # If it was a manual pause, don't emit 'error', just break
                if emitter and current_status == Status.cancelled:
                    emitter.status_changed.emit("cancelled")
                break

            # 2. Check if the process died on its own
            if proc.poll() is not None and q.empty():
                break

            try:
                # Use a shorter timeout (0.1s) for much faster UI responsiveness
                line = q.get(timeout=0.1) 
            except queue.Empty:
                continue

            

            raw_line = (line or "").strip()
            if not raw_line:
                continue

            # forward raw logs to app log
            log(f"[yt-dlp-exe] {raw_line}", log_level=4)
            if emitter:
                try:
                    emitter.log_updated.emit(raw_line)
                except Exception:
                    pass

            # if progress-template enabled, try to parse JSON-ish line
            parsed_template = False
            if use_progress_template:
                try:
                    candidate = raw_line.strip()
                    if candidate.startswith("{") and candidate.endswith("}"):
                        try:
                            parsed = json.loads(candidate)
                        except Exception:
                            parsed = json.loads(candidate.replace("'", '"'))
                        # progress percent often comes like "1.2%"
                        pct_raw = parsed.get("progress") or parsed.get("progress_percent") or parsed.get("pct") or ""
                        pct_val = None
                        if pct_raw:
                            # strip non-digit
                            m = _RE_PURE_NUM.search(str(pct_raw))
                            pct_val = float(m.group(0)) if m else None
                        if pct_val is not None:
                            d._progress = pct_val
                        # numeric fields
                        try:
                            d.downloaded = int(parsed.get("downloaded") or parsed.get("downloaded_bytes") or d.downloaded or 0)
                        except Exception:
                            dd = parse_human_size_to_bytes(parsed.get("downloaded") or parsed.get("downloaded_bytes"))
                            if dd is not None:
                                d.downloaded = dd
                        
                        # --- NEW: keep yt-dlp's single connection row in sync ---
                        try:
                            stats = getattr(d, "connection_stats", None)
                            if isinstance(stats, list) and stats:
                                stats[0]["downloaded"] = int(d.downloaded or 0)
                                if getattr(d, "status", None) == Status.downloading:
                                    stats[0]["info"] = "Receiving data..."
                        except Exception:
                            pass
                        try:
                            total_val = parsed.get("total") or parsed.get("total_bytes") or parsed.get("total_bytes_estimate")
                            if total_val is not None:
                                d.size = int(total_val)
                                d.total_size = d.size
                        except Exception:
                            tt = parse_human_size_to_bytes(parsed.get("total") or parsed.get("total_bytes"))
                            if tt is not None:
                                d.size = tt
                                d.total_size = tt
                        raw_speed = parsed.get("speed") or parsed.get("speed_str") or parsed.get("speed_text")
                        sp = parse_speed_to_bps(raw_speed)
                        if sp is not None:
                            d.speed = sp
                            d._speed = sp
                        parsed_template = True
                        # emit progress (throttle)
                        now = time.time()
                        if now - last_progress_emit > 0.18:
                            last_progress_emit = now
                            if emitter:
                                try:
                                    emitter.progress_changed.emit(int(d._progress))
                                    emitter.status_changed.emit("downloading")
                                    emitter.log_updated.emit(f"⬇ {size_format(getattr(d, 'speed', 0), '/s')} | Done: {size_format(getattr(d, 'downloaded', 0))} / {size_format(getattr(d, 'size', 0))}")
                                except Exception:
                                    pass
                        continue
                except Exception:
                    # fallthrough to regex parsing
                    parsed_template = False

            # Regex parsing fallback (handles common yt-dlp textual progress)
            # percent
            m_pct = _RE_PERCENT.search(raw_line)
            if m_pct:
                try:
                    pct = float(m_pct.group(1))
                except Exception:
                    pct = 0.0
                d._progress = pct

                # bytes like "3.4MiB/10.0MiB"
                m_bytes = _RE_DOWNLOAD_BYTES.search(raw_line)
                if m_bytes:
                    downloaded_h = m_bytes.group(1)
                    total_h = m_bytes.group(2)
                    dd = parse_human_size_to_bytes(downloaded_h)
                    tt = parse_human_size_to_bytes(total_h)

                    log(f"[yt-dlp-exe][DBG] matched downloaded/total -> {downloaded_h} / {total_h} => {dd} / {tt}", log_level=4)

                    if dd is not None:
                        # use property setter (robust) - it will coerce and lock
                        try:
                            d.downloaded = dd
                        except Exception:
                            with lock:
                                d._downloaded = int(dd)
                    if tt is not None:
                        d.size = tt
                        d.total_size = tt

                    # compute percent if possible
                    if dd is not None and tt:
                        pct = round(dd * 100.0 / tt, 1) if tt else 0.0
                        d.progress = pct
                    # parse speed & eta below (continue to next iteration after emitting)
                    # fall through to parse speed/eta below

                else:
                    # 2) Try "percent of <total>" e.g. "98.3% of 566.23MiB"
                    m_pct_of = _RE_PERCENT_OF_TOTAL.search(raw_line)
                    if m_pct_of:
                        pct_str = m_pct_of.group(1)
                        total_h = m_pct_of.group(2)
                        try:
                            pct_val = float(pct_str)
                        except Exception:
                            pct_val = 0.0
                        tt = parse_human_size_to_bytes(total_h)
                        # compute downloaded from percent if total known
                        if tt is not None:
                            dd = int(round(pct_val / 100.0 * tt))
                            log(f"[yt-dlp-exe][DBG] matched percent-of-total -> pct={pct_val} total={total_h} ({tt}) => downloaded={dd}", log_level=4)
                            try:
                                d.downloaded = dd
                            except Exception:
                                with lock:
                                    d._downloaded = int(dd)
                            d.size = tt
                            d.total_size = tt
                        # always set progress from pct_val
                        d.progress = pct_val

                # 3) speed parsing (separate; independent)
                m_speed = _RE_SPEED.search(raw_line)
                if m_speed:
                    raw_speed = m_speed.group(1)
                    # convert to bytes/sec
                    sp = parse_speed_to_bps(raw_speed + "/s") or parse_speed_to_bps(raw_speed)
                    if sp is not None:
                        d.speed = sp
                    else:
                        # fallback keep text in _speed but don't break math
                        try:
                            d._speed = raw_speed
                        except Exception:
                            pass

                # 4) ETA parsing
                m_eta = _RE_ETA.search(raw_line)
                if m_eta:
                    d.remaining_time = m_eta.group(1)

                # 5) emit UI updates (throttle to avoid flooding)
                now = time.time()
                if now - last_progress_emit > 0.18:
                    last_progress_emit = now
                    if emitter:
                        try:
                            emitter.progress_changed.emit(int(getattr(d, "_progress", getattr(d, "progress", 0))))
                            emitter.status_changed.emit("downloading")
                            emitter.log_updated.emit(f"⬇ {size_format(getattr(d, 'speed', 0), '/s')} | Done: {size_format(getattr(d, 'downloaded', 0))} / {size_format(getattr(d, 'total_size', getattr(d, 'size', 0)))}")
                        except Exception:
                            pass
                continue

            # Completion hints
            if "100%" in raw_line or "has already been downloaded" in raw_line or raw_line.lower().startswith("destination:"):
                log(f"[yt-dlp-exe] Completion hint: {raw_line}")
                continue

            # postprocessing error detection
            if "Postprocessing: Error opening input files" in raw_line or "Postprocessing: Unable to open" in raw_line:
                log(f"[yt-dlp-exe] Detected ffmpeg postprocessing error in output: {raw_line}")
                continue

            # Other logging lines are just forwarded above

        # process finished: wait for exit code
        proc.wait(timeout=exe_timeout)

        # success
        if proc.returncode == 0:
            # Update d.name to match the actual downloaded file (yt-dlp may add extension during merge)
            try:
                import glob
                _SKIP_PAT = re.compile(r'\.f\d+\.[a-z0-9]+$|\.part$|\.ytdl$|\.temp$', re.I)
                pattern = os.path.join(d.folder, glob.escape(bare_title) + ".*")
                matches = [f for f in glob.glob(pattern) if not _SKIP_PAT.search(f)]
                
                # Extract original extension from URL path or d.ext FIRST
                orig_ext = None
                if hasattr(d, 'ext') and d.ext:
                    orig_ext = f".{d.ext.lower()}"
                elif hasattr(d, 'url') and d.url:
                    from urllib.parse import urlparse, unquote
                    parsed = urlparse(unquote(d.url))
                    path_ext = os.path.splitext(parsed.path)[1].lower()
                    if path_ext and len(path_ext) <= 5:
                        orig_ext = path_ext
                
                # If no matches, check for .unknown_video directly
                if not matches:
                    unknown_path = os.path.join(d.folder, f"{bare_title}.unknown_video")
                    if os.path.exists(unknown_path):
                        matches = [unknown_path]
                
                if matches:
                    chosen = matches[0]  # Simplified, take first
                    
                    # Fix .unknown_video immediately
                    if chosen.endswith('.unknown_video'):
                        if orig_ext:
                            corrected = chosen[:-14] + orig_ext  # Remove '.unknown_video', add real ext
                            try:
                                os.rename(chosen, corrected)
                                chosen = corrected
                                log(f"Corrected unknown_video → {orig_ext}", log_level=1)
                            except Exception as e:
                                log(f"Rename failed: {e}", log_level=2)
                        else:
                            # No extension info, keep as-is but warn
                            log(f"Cannot determine correct extension for {chosen}", log_level=2)
                    
                    d.name = os.path.basename(chosen)
                    d.target_file = chosen
            except Exception as e:
                log(f"[yt-dlp-exe] Error updating filename: {e}", log_level=3)

            d.status = Status.completed
            d._progress = 100
            try:
                d.downloaded = getattr(d, "size", getattr(d, "total_size", d.downloaded))
            except Exception:
                pass

            # --- NEW: finalise connection row for yt-dlp ---
            try:
                stats = getattr(d, "connection_stats", None)
                if isinstance(stats, list) and stats:
                    stats[0]["downloaded"] = int(d.downloaded or 0)
                    stats[0]["info"] = "Completed"
            except Exception:
                pass

            if emitter:
                try:
                    emitter.progress_changed.emit(100)
                    emitter.status_changed.emit("completed")
                except Exception:
                    pass
            try:
                delete_folder(d.temp_folder)
            except Exception:
                pass
            log(f"[yt-dlp-exe] Finished download: {d.name}")
            try:
                notify(f"File: {d.name} \nsaved at: {d.folder}", title=f"{APP_NAME} - Download completed")
            except Exception:
                pass
            return

        # non-zero exit: collect remaining queue contents for diagnostics
        stderr_excerpt = ""
        try:
            parts = []
            while not q.empty():
                parts.append(q.get_nowait())
            stderr_excerpt = "".join(parts)[:4000]
        except Exception:
            stderr_excerpt = ""

        log(f"[yt-dlp-exe] Process exited with code {proc.returncode}. Output excerpt:\n{stderr_excerpt}")

        # FFmpeg fallback merge detection & attempt
        if "Postprocessing: Error opening input files" in stderr_excerpt or ("Postprocessing" in stderr_excerpt and "Error opening" in stderr_excerpt):
            log("[yt-dlp-exe] Detected FFmpeg postprocessing error – attempting fallback merge")
            try:
                base_name = os.path.splitext(d.name)[0]
                video_file = os.path.join(d.folder, f"{base_name}.f{d.format_id}.mp4")
                audio_file = os.path.join(d.folder, f"{base_name}.f{d.audio_format_id}.mp4")
                output_file = os.path.join(d.folder, d.name)

                if os.path.exists(video_file) and os.path.exists(audio_file):
                    d.status = Status.merging_audio
                    log("[yt-dlp-exe] Found both audio and video files, initiating fallback merge (ffmpeg)")

                    cmd_ff = [
                        get_effective_ffmpeg(),
                        "-i", video_file,
                        "-i", audio_file,
                        "-c:v", "copy",
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-shortest",
                        output_file
                    ]
                    kwargs = dict(capture_output=True, text=True)
                    if sys.platform.startswith("win"):
                        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                    result = subprocess.run(cmd_ff, **kwargs)
                    if result.returncode == 0:
                        d.status = Status.completed
                        d._progress = 100
                        if emitter:
                            try:
                                emitter.progress_changed.emit(100)
                                emitter.status_changed.emit("completed")
                            except Exception:
                                pass
                        try:
                            delete_folder(d.temp_folder)
                        except Exception:
                            pass
                        try:
                            os.remove(video_file)
                            os.remove(audio_file)
                        except Exception as cleanup_error:
                            log(f"[cleanup] Could not delete fragments: {cleanup_error}")
                        try:
                            notify(f"File: {d.name} \nsaved at: {d.folder}", title=f"{APP_NAME} - Download completed")
                        except Exception:
                            pass
                        log(f"[yt-dlp-exe] Fallback merge succeeded for: {d.name}")
                        return
                    else:
                        log(f"[yt-dlp-exe] Fallback merge failed: {result.stderr[:1000]}")
            except Exception as fallback_e:
                log(f"[yt-dlp-exe] Fallback merge exception: {fallback_e}")

    except Exception as exc:
        log(f"[yt-dlp-exe] Exception during download: {exc}")
        error_msg = str(e).lower()
        
        # Transient network errors → keep as "cancelled" for retry
        transient_errors = [
            'timeout', 'connection', 'network', 'temporary failure',
            'http error 429', 'http error 503', 'http error 504'
        ]

        is_transient = any(err in error_msg for err in transient_errors)
        
        if is_transient:
            log(f"Transient network error for {d.name}: {e}", log_level=2, context=ctx)
            d.status = Status.cancelled  # Allow clean retry
        else:
            # Fatal errors (extraction failure, unsupported format, etc.)
            log(f"Fatal yt-dlp error for {d.name}: {e}", log_level=3, context=ctx)
            d.status = Status.error
            
        if emitter:
            emitter.status_changed.emit(d.status)


    finally:
        try:
            if proc and proc.poll() is None:
                proc.terminate()
        except Exception:
            pass
        log(f"[yt-dlp-exe] Done processing {getattr(d, 'name', 'unknown')}")
        if emitter:
            try:
                emitter.log_updated.emit(f"[yt-dlp-exe] Done processing {getattr(d, 'name', 'unknown')}")
            except Exception:
                pass
        if d.status == Status.completed:
            cb = getattr(d, "callback", None)
            if cb:
                # Pass both the callback reference and the item itself
                _execute_callback(cb, d)
        


def _manual_ffmpeg_remux_fallback(d, emitter=None):
    """
    Manually attempts to merge orphaned video and audio fragments.
    
    Triggered when yt-dlp's internal post-processor fails. It scans for 
    fragment files (e.g., .f137.mp4 and .f140.m4a) and uses a fast 
    'stream copy' remux to produce the final target file.
    """
    ctx = "ENGINE-YTDLP"
    try:
        base_name = os.path.splitext(d.name)[0]
        # Locate fragments based on the IDs stored during extraction
        v_frag = os.path.join(d.folder, f"{base_name}.f{d.format_id}.mp4")
        a_frag = os.path.join(d.folder, f"{base_name}.f{d.audio_format_id}.mp4")
        output = os.path.join(d.folder, d.name)

        if os.path.exists(v_frag) and os.path.exists(a_frag):
            log(f"Fallback: Manually remuxing {v_frag} + {a_frag}", log_level=1, context=ctx)
            d.status = Status.merging_audio
            if emitter: emitter.status_changed.emit("merging_audio")

            # Build the FFmpeg command for a fast lossless copy
            cmd = [
                config.get_effective_ffmpeg(),
                "-y", "-v", "error",
                "-i", v_frag,
                "-i", a_frag,
                "-c", "copy",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                output
            ]

            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if result.returncode == 0:
                log("Manual fallback merge succeeded.", log_level=1, context=ctx)
                d.status = Status.completed
                d._progress = 100
                if emitter:
                    emitter.progress_changed.emit(100)
                    emitter.status_changed.emit("completed")
                
                # Cleanup fragments
                for f in (v_frag, a_frag):
                    try: os.remove(f)
                    except: pass
                
                notify(f"File: {d.name}\nStatus: Fixed & Merged", title="OmniPull - Fallback")
                return True
            else:
                log(f"Manual merge failed: {result.stderr}", log_level=3, context=ctx)
    
    except Exception as e:
        log(f"Critical error during fallback merge: {e}", log_level=3, context=ctx)
    
    # If we get here, both yt-dlp AND our manual fix failed
    d.status = Status.error
    if emitter: emitter.status_changed.emit("error")
    return False


def _execute_callback(callback, d):
    """
    Executes a post-download task, passing the DownloadItem 'd' for context.
    """
    ctx = "ENGINE-BRAIN"
    if not callback:
        return

    try:
        func = None
        
        if callable(callback):
            func = callback
        elif isinstance(callback, str):
            # Resolve the string name to the actual function in this module
            func = globals().get(callback)
        
        if func and callable(func):
            log(f"Executing callback: {callback}", log_level=1, context=ctx)
            # Pass the DownloadItem 'd' so the callback can access d.id, d.folder, etc.
            func(d)
        else:
            log(f"Callback '{callback}' could not be resolved to a callable function.", 
                log_level=2, context=ctx)
                
    except Exception as e:
        log(f"Callback execution failed: {e}", log_level=3, context=ctx)



def run_ytdlp_download(d, emitter=None):
    """
    Executes a media download using the yt-dlp Python API.
    
    Key features:
    1. Connection Tracking: Updates a dedicated UI row for yt-dlp status.
    2. Dynamic Filename Resolution: Detects the final merged filename post-extraction.
    3. FFmpeg Fallback: Manually attempts a fast-remux merge if yt-dlp's internal 
       post-processor fails.
    4. Subtitle Recovery: Triggers a retry if selected subtitles are missing.
    """

    ctx = "ENGINE-YTDLP"
    log(f"Starting API extraction: {d.name}", log_level=1, context=ctx)
    
    d.status = Status.downloading
    d._progress = 0
    
    # ── 1. UI Connection State Initialization ──
    try:
        if not hasattr(d, "connection_stats") or not isinstance(d.connection_stats, list):
            d.connection_stats = []
        if not d.connection_stats:
            d.connection_stats.append({"downloaded": int(d.downloaded or 0), "info": "Initializing..."})
        else:
            d.connection_stats[0].update({"downloaded": int(d.downloaded or 0), "info": "Initializing..."})
    except Exception: pass

    # ── 2. The Progress Hook ──
    def progress_hook(info):
        if not getattr(d, "_title_resolved", False):
            idict = info.get("info_dict") or {}
            real_title = (idict.get("title") or idict.get("fulltitle") or idict.get("alt_title"))
            if real_title:
                # Only update name if it currently looks like a URL or ID
                if d.name.startswith("http") or len(d.name) <= 12:
                    d.name = validate_file_name(real_title)
                d._title_resolved = True

        if d.status in (Status.cancelled, Status.queued):
            raise yt_dlp.utils.DownloadCancelled("Download stopped by user.")

        if info["status"] == "downloading":
            raw_pct = info.get("_percent_str", "0%").strip().replace('%', '')
            clean_pct = re.sub(r'\x1b\[[0-9;]*m', '', raw_pct)
            
            d._progress = float(clean_pct)
            d.downloaded = info.get("downloaded_bytes", 0)
            d.size = info.get("total_bytes") or info.get("total_bytes_estimate", 0)
            d._speed = info.get("speed", 0)
            d.remaining_time = info.get("eta", 0)

            try:
                stats = getattr(d, "connection_stats", [])
                if stats:
                    stats[0]["downloaded"] = int(d.downloaded or 0)
                    stats[0]["info"] = "Receiving media data..."
            except Exception: pass
            
            if emitter:
                emitter.progress_changed.emit(int(d._progress))
                emitter.log_updated.emit(
                    f"⬇ {size_format(d._speed, '/s')} | {size_format(d.downloaded)} / {size_format(d.size)}"
                )

    # ── 3. Path & Template Setup (CRITICAL FIX) ──
    if getattr(d, 'vid_info', None):
        title = d.vid_info.get("title") or d.name
        d.name = validate_file_name(title)

    # Always split the extension to get a clean base for the template
    bare_title, original_ext = os.path.splitext(d.name)

    is_media_site = any(x in d.url for x in ["youtube.com", "youtu.be", "vimeo.com", "tiktok.com"])

    # FIX: Always use %(ext)s. This ensures yt-dlp manages the .part files correctly.
    # If we use a hardcoded name without %(ext)s, resuming often fails on direct links.
    # if is_media_site and not getattr(d, 'vid_info', None):
    #     output_template = os.path.join(d.folder, f"{bare_title}.%(ext)s")
    # else:
    #     output_template = os.path.join(d.folder, f"{bare_title}{d.ext}")


    if getattr(d, 'vid_info', None):
        # Scenario: Manual download with full info
        output_template = os.path.join(d.folder, f"{bare_title}.%(ext)s")
    else:
        # Check if this is a YouTube/Media link or a direct static file
        is_media_site = any(x in d.url for x in ["youtube.com", "youtu.be", "vimeo.com", "tiktok.com"])
        
        if is_media_site:
            # Scenario: Batch YouTube (Forces yt-dlp to fetch the real title)
            output_template = os.path.join(d.folder, "%(title)s.%(ext)s")
        else:
            # Scenario: Static Files (e.g. Kingdom...zip)
            # Using d.name directly prevents the ".unknown_video" bug
            output_template = os.path.join(d.folder, d.name)

    log(f'Output template: {output_template}', context=ctx)

    format_code = None
    if getattr(d, "format_id", None) and getattr(d, "audio_format_id", None):
        format_code = f"{d.format_id}+{d.audio_format_id}"
    elif getattr(d, "format_id", None):
        format_code = d.format_id
    elif getattr(d, "_ytdlp_format_override", None):
        format_code = d._ytdlp_format_override
    else:
        dh = getattr(d, "_desired_height", None)
        if dh is None:
            format_code = "bestvideo+bestaudio/best"
        elif dh == 0:
            format_code = "bestaudio/best"
        else:
            format_code = f"bestvideo[height<={dh}]+bestaudio[height<={dh}]/best"


    # ── 4. Configuration Assembly ──
    ydl_opts = {
        "outtmpl": output_template,
        "progress_hooks": [progress_hook],
        "quiet": bool(config.ytdlp_config.get("quiet", True)),
        "no_warnings": bool(config.ytdlp_config.get("no_warnings", True)),
        "retries": int(config.ytdlp_config.get("retries", 10)),
        "continuedl": True,
        "concurrent_fragment_downloads": int(config.ytdlp_config.get("concurrent_fragment_downloads", 5)),
        "ffmpeg_location": config.ffmpeg_actual_path,
        "format": format_code,
        "writeinfojson": bool(config.ytdlp_config.get("writeinfojson", True)),
        "merge_output_format": config.ytdlp_config.get('merge_output_format', 'mp4'),
        "proxy": config.proxy if config.proxy else None,
        "cookiesfile": config.ytdlp_config.get("cookiesfile", None),
    }

    # Merge Advanced options from user settings
    try:
        advanced = get_advanced_opts(d)
        if advanced: ydl_opts.update(advanced)
    except Exception as e:
        log(f"Could not apply advanced opts: {e}", log_level=2, context=ctx)


    # ── 5. Execution & Resolution ──
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([d.url])
        
        # Resolve filename
        try:
            import glob
            _SKIP_PAT = re.compile(r'\.f\d+\.[a-z0-9]+$|\.part$|\.ytdl$|\.temp$', re.I)
            pattern = os.path.join(d.folder, glob.escape(bare_title) + ".*")
            matches = [f for f in glob.glob(pattern) if not _SKIP_PAT.search(f)]
            
            if matches:
                # Logic: If it's a media site, look for the merge format (mp4). 
                # If it's a static file, look for the original extension (zip).
                target_ext = original_ext.lower() if not is_media_site else f".{ydl_opts['merge_output_format'].lower()}"
                preferred = [f for f in matches if f.lower().endswith(target_ext)]
                chosen = preferred[0] if preferred else max(matches, key=os.path.getmtime)
                
                # Fix .unknown_video
                if chosen.endswith('.unknown_video') and original_ext:
                    corrected = chosen.replace('.unknown_video', original_ext)
                    log(f'This was the log {corrected}')
                    os.rename(chosen, corrected)
                    chosen = corrected

                d.name = os.path.basename(chosen)
                log(f'This is the finale name {d.name}')
                d.target_file = chosen
        except Exception as e:
            log(f"Resolution error: {e}", log_level=2, context=ctx)

        d.status = Status.completed
        d._progress = 100
        if emitter:
            emitter.progress_changed.emit(100)
            emitter.status_changed.emit("completed")
        
        delete_folder(d.temp_folder)
        notify(f"Download Finished: {d.name}", title="OmniPull - yt-dlp")

    except yt_dlp.utils.DownloadCancelled:
        # Preserve Status.queued if the item was paused rather than fully cancelled.
        # Overwriting queued→cancelled would remove it from the queue on next restart.
        if d.status != Status.queued:
            d.status = Status.cancelled
        log(
            f"Download stopped: {d.name} (status kept as {d.status})",
            log_level=1, context=ctx,
        )

    except Exception as e:
        error_msg = str(e).lower()
        
        # Transient network errors → keep as "cancelled" for retry
        transient_errors = [
            'timeout', 'connection', 'network', 'temporary failure',
            'http error 429', 'http error 503', 'http error 504'
        ]
        
        is_transient = any(err in error_msg for err in transient_errors)
        
        if is_transient:
            log(f"Transient network error for {d.name}: {e}", log_level=2, context=ctx)
            d.status = Status.cancelled  # Allow clean retry
        else:
            # Fatal errors (extraction failure, unsupported format, etc.)
            log(f"Fatal yt-dlp error for {d.name}: {e}", log_level=3, context=ctx)
            d.status = Status.error
            
        if emitter:
            emitter.status_changed.emit(d.status)

    finally:
        if d.status == Status.completed:
            cb = getattr(d, "callback", None)
            if cb:
                # Pass both the callback reference and the item itself
                _execute_callback(cb, d)



#


def mmap_append(dest, src):
    """
    Appends a source segment to a destination file using memory mapping.
    
    1. Expands the destination file to accommodate the new data.
    2. Maps both files into memory.
    3. Performs a fast memory-to-memory block transfer.
    """
    src_size = os.path.getsize(src)

    # Calculate current offset before expansion
    with open(dest, "ab") as d:
        dest_offset = d.tell()

    with open(dest, "r+b") as d, open(src, "rb") as s:
        # Resize destination to fit the incoming segment
        d.truncate(dest_offset + src_size)

        dest_map = mmap.mmap(d.fileno(), dest_offset + src_size)
        src_map = mmap.mmap(s.fileno(), 0, access=mmap.ACCESS_READ)

        # Slice-based block transfer
        dest_map[dest_offset:dest_offset + src_size] = src_map[:]

        src_map.close()
        dest_map.close()


def file_manager(d, keep_segments=False, emitter=None):
    """
    Coordinates segment stitching and final file assembly.
    
    Strictly follows the sequential merging gate: Segment N will not 
    merge until Segments 0 through N-1 are marked as completed.
    """
    try:
        import omnipull_url_processor
        use_rust = True
    except ImportError:
        use_rust = False    
    
    # Initialization: Purge stale temp files if starting fresh
    if d.progress == 0:
        if os.path.exists(d.temp_file): 
            os.remove(d.temp_file)
        if hasattr(d, 'audio_file') and d.audio_file and os.path.exists(d.audio_file): 
            os.remove(d.audio_file)
    else:
        log(f"[file_manager] Resuming: Preserving existing data in {d.temp_file}")

    loop_count_fm = 0
    while True:
        time.sleep(0.1)
        loop_count_fm += 1

        # 1. State Check: Transition to 'Stitching' phase
        all_downloaded = all(seg.downloaded for seg in d.segments)
        any_not_merged = any(not seg.completed for seg in d.segments)

        if all_downloaded and any_not_merged:
            if d.status != config.Status.stitching:
                d.status = config.Status.stitching
                if emitter:
                    emitter.status_changed.emit("stitching")

        job_list = [seg for seg in d.segments if not seg.completed]

        # 2. Progress Aggregation (Nim-Accelerated every ~0.5s)
        if loop_count_fm % 5 == 0 and d.segments:
            try:
                seg_data = []
                for seg in d.segments:
                    seg_data.append({
                        "speed": 0,
                        "downloaded": seg.size if seg.completed else 0,
                        "size": seg.size or 0
                    })
                
                if seg_data:
                    stats = native_engine.calculate_stats(seg_data)
                    if isinstance(stats, dict) and "progress" in stats:
                        d.progress = stats.get("progress", 0)
            except Exception as e:
                log(f"[file_manager] Nim stats error: {e}", log_level=3)

        # 3. Stitching Loop with Safety Gate
        for seg in job_list:
            if seg.completed: continue
            
            # THE SAFETY GATE: Enforce strict numerical order of merging
            first_unfinished = next((s for s in d.segments if not s.completed), None)
            if first_unfinished and first_unfinished != seg:
                break 

            if not seg.downloaded: break 

            try:
                if seg.merge:
                    if not os.path.exists(seg.name):
                        log(f"Stitcher Warning: {seg.name} not found. Skipping loop.")
                        break

                    t_start = time.perf_counter()
                    engine_used = "NONE"

                    # Priority 1: Rust
                    if use_rust:
                        engine_used = "RUST"
                        omnipull_url_processor.append_segment(str(seg.tempfile), str(seg.name))
                    
                    # Priority 2: Nim
                    elif hasattr(native_engine, 'append_segment'):
                        engine_used = "NIM"
                        native_engine.append_segment(str(seg.tempfile), str(seg.name))
                    
                    # Priority 3: Python mmap
                    # else:
                    #     engine_used = "PYTHON"
                    #     mmap_append(seg.tempfile, seg.name)
                    
                    duration_ms = (time.perf_counter() - t_start) * 1000
                    log(f"[Stitcher] Engine: {engine_used} | Seg: {seg.num} | Size: {seg.size/1024/1024:.2f}MB | Time: {duration_ms:.3f}ms", log_level=1)
                
                seg.completed = True
                if not keep_segments: 
                    delete_file(seg.name)
                
                if emitter: 
                    emitter.progress_changed.emit(d.progress)
                    emitter.log_updated.emit(f"Merged: {os.path.basename(seg.name)}")
            except Exception as e:
                log('failed to merge segment', seg.name, e)
                break

        # 4. Completion Health Check & Finalization
        if not job_list:
            missing = []
            for seg in d.segments:
                if not seg.completed and not os.path.exists(seg.name):
                    missing.append(seg)
            
            if missing:
                if not hasattr(d, 'retry_count'): d.retry_count = 0
                if d.retry_count < 3:
                    d.retry_count += 1
                    log(f"Health Check: {len(missing)} files missing! Retry {d.retry_count}/3")
                    for seg in missing:
                        seg.completed = False
                        seg.downloaded = False
                    d.status = Status.downloading
                    continue
                else:
                    log("Health Check: Max retries reached. Failing download.")
                    d.status = Status.error
                    break

            log(f'The protocol is {d.protocol} and type is {d.type}')
            
            # --- FINALIZATION PATHS ---

            # Path A: HLS/m3u8
            if 'm3u8' in d.protocol:
                from modules.video import post_process_hls
                d.status = Status.merging_audio
                if post_process_hls(d):
                    time.sleep(1) 
                    log(f"Finalizing HLS: {d.temp_file} -> {d.target_file}")
                    if os.path.exists(d.temp_file):
                        try:
                            import shutil
                            if os.path.exists(d.target_file): os.remove(d.target_file)
                            shutil.move(d.temp_file, d.target_file)
                            delete_folder(d.temp_folder)
                            d.status = Status.completed
                        except Exception as move_err:
                            log(f"Error moving final HLS file: {move_err}")
                            d.status = Status.error
                    else:
                        log(f"Error: FFmpeg finished but {d.temp_file} is missing!")
                        d.status = Status.error
                else:
                    log("HLS post-processing failed")
                    d.status = Status.error
                break

            # Path B: DASH
            elif d.type == 'dash':
                output = d.target_file.replace(' ', '_')
                if any(not seg.completed for seg in d.segments):
                    d.status = config.Status.stitching
                    from modules.video import post_process_hls_custom
                    v_segs = [os.path.join(d.temp_folder, s.name) for s in d.segments if s.tempfile == d.temp_file]
                    a_segs = [os.path.join(d.temp_folder, s.name) for s in d.segments if hasattr(d, 'audio_file') and s.tempfile == d.audio_file]
                    if v_segs: post_process_hls_custom(d, v_segs, d.temp_file)
                    if a_segs: post_process_hls_custom(d, a_segs, d.audio_file)

                d.status = config.Status.merging_audio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                err, out = loop.run_until_complete(async_merge_video_audio(d.temp_file, d.audio_file, output, d))
                
                if not err:
                    if os.path.exists(d.target_file): os.remove(d.target_file)
                    import shutil
                    shutil.move(output, d.target_file)
                    d.delete_tempfiles()
                    delete_folder(d.temp_folder)
                    d.status = config.Status.completed
                else:
                    log(f"DASH Merge failed: {out}")
                    d.status = config.Status.error
                break

            # Path C: STATIC FILE
            else:
                if not os.path.exists(d.temp_file):
                    if len(d.segments) >= 1 and os.path.exists(d.segments[0].name):
                         try: os.rename(d.segments[0].name, d.temp_file)
                         except: pass
                rename_file(d.temp_file, d.target_file)
                delete_folder(d.temp_folder)
                d.status = Status.completed
                break

        if d.status not in [config.Status.downloading, config.Status.stitching, config.Status.merging_audio]: 
            break

    if d.status == Status.completed and emitter:
        emitter.status_changed.emit("completed")
        emitter.progress_changed.emit(100.0)
    
    _apply_postprocessing(d, emitter)

    log(f'file_manager {d.num}: quitting')






def thread_manager(d, emitter=None):
    """
    Orchestrates high-concurrency segment downloads and dynamic workload balancing.
    
    Key Systems:
    1. NIM Accel Stats: High-speed aggregation of throughput across all active workers.
    2. Adaptive Chunking: Identifies 'straggler' threads (slow connections) and 
       splits their remaining workload for faster workers to assist.
    3. Dynamic Splitting: Re-splits large in-progress segments when free threads 
       are available, mimicking Internet Download Manager (IDM) behavior.
    4. Speed Throttling: Dynamically calculates and distributes per-worker 
       speed limits based on global user settings.
    """
    ctx = "ENGINE-THREADS"
    
    # ── 1. Connection Initialization ──
    try:
        max_conn = int(config.max_connections)
    except Exception:
        # Robust fallback for config parsing
        max_conn = int(float(getattr(config, 'max_connections', 64)))
    
    log(f"Initializing manager for Task {d.num} with {max_conn} connections.", 
        log_level=3, context=ctx)

    try:
        # Initialize the fixed worker pool
        workers = [Worker(tag=i, d=d) for i in range(max_conn)]
        free_workers = list(reversed(range(max_conn)))
        busy_workers = []
        live_threads = []

        # Initial job queue construction
        job_list = [seg for seg in d.segments if not seg.downloaded]
        job_list.reverse() # Prepare for LIFO popping
        
    except Exception as e:
        log(f"Fatal initialization error: {e}", log_level=1, context=ctx)
        return

    loop_count = 0
    loop_start = time.perf_counter()

    # ── 2. The Main Management Loop ──
    while True:
        time.sleep(0.3) # 300ms polling interval for UI stability
        loop_count += 1

        # Periodic Diagnostic Logging
        if loop_count % 10 == 0:
            log(f"State: Free={len(free_workers)} | Busy={len(busy_workers)} | Remaining={len(job_list)}", 
                log_level=3, context=ctx)

        # Ingest new jobs from the shared queue (e.g., from browser extension interrupts)
        while not d.q.jobs.empty():
            job_list.append(d.q.jobs.get())

        # ── 3. NIM ACCELERATED STATS & ADAPTIVE CHUNKING ──
        if busy_workers and d.status == config.Status.downloading:
            try:
                # Prepare payload for the Nim-based native decision engine
                worker_payload = []
                for w_num in busy_workers:
                    w = workers[w_num]
                    if w.seg:
                        worker_payload.append({
                            "speed": float(w.current_speed),
                            "downloaded": int(w.downloaded),
                            "size": int(w.seg.size or 0),
                            "can_split": bool(w.seg.can_split())
                        })

                if worker_payload:
                    t_eval_start = time.perf_counter()
                    
                    # Invoke Nim to identify connections falling behind (threshold: 1.5x slower)
                    struggler_idx = native_engine.find_struggler(worker_payload, 1.5)
                    
                    eval_ms = (time.perf_counter() - t_eval_start) * 1000
                    
                    if struggler_idx != -1:
                        # Extract the struggler and trigger a split
                        worker_num = busy_workers[struggler_idx]
                        struggler = workers[worker_num]
                        
                        next_num = max(s.num for s in d.segments) + 1
                        new_seg = struggler.seg.split(next_num)
                        
                        if new_seg:
                            d.segments.append(new_seg)
                            job_list.append(new_seg)
                            log(f"NIM Accel: Identified straggler in {eval_ms:.4f}ms. Splitting Seg {struggler.seg.num}", 
                                log_level=1, context="NIM-ACCEL")

            except Exception as e:
                log(f"Nim Decision Engine Error: {e}", log_level=3, context="NIM-ACCEL")

        # ── 4. Speed Limit Calculation ──
        active_slots = min(max_conn, d.remaining_parts)
        try:
            global_limit = int(config.speed_limit)
        except:
            global_limit = 0

        # Divide the global limit equally across active connections
        worker_sl = (global_limit * 1024 // active_slots) if active_slots > 0 else 0

        # ── 5. IDM-STYLE DYNAMIC SPLITTING (Passive) ──
        # If we have free connections but no new jobs, steal work from the largest active segment
        if free_workers and not job_list and busy_workers and d.status == config.Status.downloading:
            largest_seg = None
            largest_size = 0

            for seg in d.segments:
                if seg.in_progress and seg.can_split():
                    if (seg.size or 0) > largest_size:
                        largest_seg = seg
                        largest_size = seg.size

            if largest_seg:
                next_num = max(s.num for s in d.segments) + 1
                new_seg = largest_seg.split(next_num)
                if new_seg:
                    d.segments.append(new_seg)
                    job_list.append(new_seg)
                    log(f"✂️ Dynamic Split: Re-partitioned Seg {largest_seg.num} ({size_format(largest_size)})", 
                        log_level=1, context=ctx)

        # ── 6. ASSIGN WORKERS ──
        while free_workers and job_list and d.status == config.Status.downloading:
            try:
                worker_num = free_workers.pop()
                seg = job_list.pop()
                busy_workers.append(worker_num)

                seg.in_progress = True
                worker = workers[worker_num]
                worker.reuse(seg=seg, speed_limit=worker_sl)

                # Each worker runs on its own daemon thread
                t = Thread(target=worker.run, daemon=True, name=str(worker_num))
                live_threads.append(t)
                t.start()
                
                log(f"Worker {worker_num} deployed to Segment {seg.num}", log_level=3, context=ctx)

            except Exception as e:
                log(f"Worker assignment failed: {e}", log_level=2, context=ctx)
                break

        # ── 7. HOUSEKEEPING: Cleanup Finished Threads ──
        d.live_connections = len(busy_workers)
        d.remaining_parts = len(busy_workers) + len(job_list) + d.q.jobs.qsize()

        for t in live_threads[:]:
            if not t.is_alive():
                worker_num = int(t.name)
                worker = workers[worker_num]
                
                if hasattr(worker, "seg") and worker.seg:
                    worker.seg.in_progress = False # Release lock
                
                live_threads.remove(t)
                if worker_num in busy_workers: busy_workers.remove(worker_num)
                free_workers.append(worker_num)

        # ── 8. Exit Conditions ──
        if d.status != config.Status.downloading: break
        if not busy_workers and not job_list and d.q.jobs.empty(): break
    
    loop_end = time.perf_counter()
    log(f"Manager session concluded for Task {d.num} in {(loop_end-loop_start)*1000:.2f}ms", 
        log_level=1, context=ctx)