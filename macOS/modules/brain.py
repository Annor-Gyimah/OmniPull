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
import time
import socket
import yt_dlp
import asyncio
import traceback
import subprocess
from threading import Thread

from modules import config
from modules.video import Stream
from modules.worker import Worker
from modules.threadpool import executor
from modules.helper import safe_filename
from modules.aria2c_manager import aria2c_manager
from modules.postprocessing import async_merge_video_audio
from modules.config import Status, APP_NAME, get_ffmpeg_path 
from modules.utils import (log, size_format, popup, notify, delete_folder, delete_file, rename_file, validate_file_name)
from modules.video import (is_download_complete, get_ytdl_options, extract_info_blocking, pre_process_hls, post_process_hls, unzip_ffmpeg) 




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
    global signal_emitter
    signal_emitter = emitter


def _select_streams_for_aria2(d, vid_info, preferred_langs=None):
    """
    Choose video/audio streams for aria2 respecting user selection + language.
    Returns (video_stream, audio_stream) or (None, None) if not suitable.
    """
    if preferred_langs is None:
        preferred_langs = ["en-US", "en", "eng", None]  # None -> unlabeled

    # Wrap yt-dlp formats with Stream class
    streams = [Stream(f) for f in vid_info.get("formats", [])]
    videos  = [s for s in streams if s.mediatype in ("dash", "normal") and s.vcodec != "none"]
    audios  = [s for s in streams if s.mediatype in ("dash", "audio") and s.acodec != "none"]

    # If user provided explicit ids, honor them
    v = next((s for s in videos if getattr(d, "format_id", None) and s.format_id == d.format_id), None)
    a = next((s for s in audios if getattr(d, "audio_format_id", None) and s.format_id == d.audio_format_id), None)

    # Fallback: pick a sane video for aria2 (avoid m3u8)
    def is_ok_for_aria2(s):
        proto = (s.protocol or "").lower()
        # aria2 handles http(s) progressive URLs well; m3u8 is a no-go here
        return ("m3u8" not in proto)

    if v is None:
        # prefer the user’s selected resolution if its on d.selected_stream
        target_w  = getattr(getattr(d, "selected_stream", None), "width", None)
        target_h  = getattr(getattr(d, "selected_stream", None), "height", None)

        candidates = [s for s in videos if is_ok_for_aria2(s)]
        if target_w and target_h:
            # closest by resolution
            def vscore(s):
                dw = abs((s.width or 0) - target_w)
                dh = abs((s.height or 0) - target_h)
                # prefer mp4-ish for easier mux
                ext_bonus = 10 if (s.extension or "").lower() in {"mp4", "m4v", "mov"} else 0
                return (-ext_bonus, dw + dh, -(s.tbr or 0))
            v = min(candidates, key=vscore) if candidates else None
        else:
            # generic best non-m3u8
            def vscore2(s):
                ext_bonus = 10 if (s.extension or "").lower() in {"mp4", "m4v", "mov"} else 0
                return (-(s.quality or 0), -(s.tbr or 0), -ext_bonus)
            v = sorted(candidates, key=vscore2)[0] if candidates else None

    # If chosen video is m3u8, do not proceed with aria2
    if not v or "m3u8" in (v.protocol or "").lower():
        return None, None

    # Fallback: pick audio by preferred language and container compatibility
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
        # try language-preferred audio first, then best bitrate
        def ascore(s):
            lang = (getattr(s, "language", None) or getattr(s, "lang", None) or None)
            try:
                lang_rank = preferred_langs.index(lang) if lang in preferred_langs else len(preferred_langs)
            except Exception:
                lang_rank = len(preferred_langs)
            # favor compatible container, higher abr/tbr
            ext_ok = 1 if (s.extension or "").lower() in allowed_aext else 0
            return (lang_rank, -int(s.abr or s.tbr or 0), -ext_ok)

        a_candidates = [s for s in audios if (s.extension or "").lower() in allowed_aext]
        if not a_candidates:
            a_candidates = audios[:]  # any audio

        a = sorted(a_candidates, key=ascore)[0] if a_candidates else None

    return v, a



def brain(d=None, emitter=None):
    log(f"[brain] ENGINE DEBUG — d.engine={d.engine} | d.type={d.type} | protocol={d.protocol} | url={d.url}")

    # Check which engine to use

    if d.engine in ["aria2", "aria2c"] or d.ext in ['torrent'] or d.url.startswith("magnet:?"):
        log(f"[brain] aria2c selected for: {d.name}")

        # Ensure original_url is stored before overriding d.url
        if ("youtube.com" in d.url or "youtu.be" in d.url):
            if not getattr(d, "original_url", None) or "googlevideo.com" in d.url:
                d.original_url = d.url  # backup the original YouTube URL

        if ("youtube.com" in d.original_url or "youtu.be" in d.original_url) and not getattr(d, "vid_info", None):
            log(f"[brain] Extracting stream info from YouTube original URL for aria2c...")
            ydl_opts = get_ytdl_options()
            vid_info = extract_info_blocking(d.original_url, ydl_opts)
            d.vid_info = vid_info

        elif getattr(d, "vid_info", None):
            log(f"[brain] Reusing existing vid_info for {d.name}")

        
        if getattr(d, "vid_info", None):
            # Pick streams that match user’s choice and avoid m3u8 for aria2
            v, a = _select_streams_for_aria2(d, d.vid_info, preferred_langs=getattr(config, "preferred_audio_langs", None))

            if not v:
                log("[brain] Selected stream is m3u8 or none suitable for aria2 — using yt-dlp/native HLS")
                run_ytdlp_download(d, emitter)  
                return

            # Set URLs/ids for the aria2 pair
            d.eff_url = v.url
            d.url = d.eff_url
            d.format_id = v.format_id

            if a:
                d.audio_url = a.url
                d.audio_format_id = a.format_id
            else:
                d.audio_url = None
                d.audio_format_id = None

            # Safe final name (keep original title if present)
            title = d.vid_info.get("title") or d.name
            d.name = validate_file_name(title)

            run_aria2c_video_audio_download(d, emitter)

        else:
            log("[Aria2c] Running normal static file download")
            d.original_url = d.url
            run_aria2c_download(d, emitter=emitter)
        return



    elif d.engine == "yt-dlp":
        log(f"[brain] yt-dlp selected for: {d.name}")
        run_ytdlp_download(d, emitter)
        return

    elif d.engine == "curl":
        log(f"[brain] Using curl/pycurl for: {d.name}")
        pass  # Let it fall through

    

    # else:
    #     log(f"[brain] Unknown engine '{d.engine}'. Defaulting to curl.")
    #     pass  # Still go with curl logic

    # ✅ pycurl or native logic continues here
    d.status = Status.downloading
    log('-' * 100)
    log(f'start downloading file: "{d.name}", size: {size_format(d.size)}, to: {d.folder} with engine: {d.engine}') 

    d.load_progress_info()

    if 'm3u8' in d.protocol:
        keep_segments = True
        success = pre_process_hls(d)
        if not success:
            d.status = Status.error
            return
    else:
        keep_segments = False


    
    executor.submit(file_manager, d, keep_segments, emitter)
    executor.submit(thread_manager, d, emitter)

    start_time = time.time()
    max_timeout = 180  # 2 minutes


    async def monitor_download(d, emitter):
        while True:
            await asyncio.sleep(0.1)

            if time.time() - start_time > max_timeout and d.progress == 0:
                
                d.status = Status.error
                log(f"Timeout reached for {d.name}. Marking as failed.")
                if emitter:
                    emitter.status_changed.emit("error")
                    emitter.failed.emit(d)
                break

            if d.status == Status.cancelled:
                log(f"brain() cancelled manually for: {d.name}")
                if d.in_queue:
                    d.status = Status.queued
                break

            if d.status == Status.completed:
                config.main_window_q.put(('restore_window', ''))
                notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
                watch_file = f"{d.folder}/_temp_{d.name}.watch"
                if os.path.exists(watch_file):
                    os.remove(watch_file)
                break

            if d.status == Status.error:
                log(f"brain() error detected for: {d.name}")
                break

        if d.callback and d.status == Status.completed:
            globals()[d.callback]()

        log(f'brain {d.num}: quitting')

    def run_async_monitor():
        asyncio.run(monitor_download(d, emitter))

    Thread(target=run_async_monitor, daemon=True).start()





def run_aria2c_download(d,  emitter=None):
    """
    Start/monitor a download via aria2c RPC (supports static URLs, .torrent files, and magnet links).

    Args:
        d       : DownloadItem (has fields like url, name, folder, size, downloaded, protocol, etc.)
        aria2   : an aria2p.API instance (connected to aria2c --enable-rpc)
        emitter : optional UI signals object with .status_changed, .progress_changed, .log_updated
    """

    # --- small helpers --------------------------------------------------------
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
        try:
            return int(x)
        except Exception:
            return 0
        
    aria2 = aria2c_manager.get_api()

    def _pick_content_download(api, current_gid):
        """
        Return the aria2p.Download representing the actual torrent content,
        not the .torrent side download. Prefer entries with bittorrent metadata
        and a non-.torrent first file path.
        """
        def is_content(dl):
            try:
                f0 = dl.files[0].path if dl.files and dl.files[0].path else ""
            except Exception:
                f0 = ""
            # treat as content if there's a non-zero length and first file isn't a .torrent
            if _safe_int(dl.total_length) > 0 and not f0.lower().endswith(".torrent"):
                return True
            # or bittorrent metadata exists (multi-file) and first file isn't .torrent
            if getattr(dl, "bittorrent", None) is not None and not f0.lower().endswith(".torrent"):
                return True
            return False

        # try current GID first
        try:
            dl = api.get_download(current_gid)
            if dl and is_content(dl):
                return dl
        except Exception:
            pass

        # otherwise scan active + waiting
        try:
            cand = (api.get_active() or []) + (api.get_waiting() or [])
            for dl in cand:
                if is_content(dl):
                    return dl
        except Exception:
            pass

        # also scan stopped (sometimes the content switches status quickly)
        try:
            for dl in api.get_stopped(max_results=100):
                if is_content(dl):
                    return dl
        except Exception:
            pass

        return None

    # --- prep & classify ------------------------------------------------------
    url = d.url or d.eff_url or ""
    name = d.name
    folder = d.folder

    is_torrent_file = url.lower().endswith(".torrent") or name.lower().endswith(".torrent")
    is_magnet_link = url.startswith("magnet:?")

    # Common aria2 options
    options = {
        "dir": folder,        # download directory
        "out": name,          # file name (ignored by multi-file torrents)
        # Add more options to use elsewhere: "max-connection-per-server": "16", etc.
    }

    # --- start the download ---------------------------------------------------
    try:
        emit_status("pending")

        if is_torrent_file:
            # If URL is a remote .torrent, fetch it to disk, then add_torrent
            torrent_path = os.path.join(folder, name if name.lower().endswith(".torrent") else (name + ".torrent"))
            if url.lower().endswith(".torrent"):
                try:
                    import requests
                    r = requests.get(url, timeout=30)
                    r.raise_for_status()
                    with open(torrent_path, "wb") as f:
                        f.write(r.content)
                except Exception as e:
                    emit_log(f"Failed to fetch .torrent: {e}")
                    d.status = config.Status.error
                    emit_status("error")
                    return

            # Add torrent to aria2
            added = aria2.add_torrent(torrent_path, options=options)
            d.aria_gid = added.gid

            # mark as bittorrent & clear bogus size from .torrent response
            d.protocol = "bittorrent"
            d.size = 0
            d.last_known_size = 0
            emit_log(f"[Aria2c] Added .torrent, GID={d.aria_gid}")

        elif is_magnet_link:
            added = aria2.add_magnet(url, options=options)
            d.aria_gid = added.gid

            # mark as bittorrent & clear bogus size
            d.protocol = "bittorrent"
            d.size = 0
            d.last_known_size = 0
            emit_log(f"[Aria2c] Added magnet, GID={d.aria_gid}")

        else:
            # Static/regular URL
            added = aria2.add_uris([url], options=options)
            d.aria_gid = added.gid
            emit_log(f"[Aria2c] Added URL, GID={d.aria_gid}")

        d.status = config.Status.downloading
        emit_status("downloading")

    except Exception as e:
        emit_log(f"Failed to start aria2 download: {e}")
        d.status = config.Status.error
        emit_status("error")
        return

    # --- monitor loop ---------------------------------------------------------
    last_emit_time = 0
    idle_start_ts = None  # when we first detect "done bytes but still 'active'"

    try:
        while True:
            time.sleep(0.5)

            # current download object (may switch for torrents)
            try:
                download = aria2.get_download(d.aria_gid)
            except Exception:
                download = None

            if not download:
                # Could be removed or finished; check stopped list
                found = None
                for dl in aria2.get_stopped(max_results=100) or []:
                    if dl.gid == d.aria_gid:
                        found = dl
                        break
                # --- inside the monitor loop when `download` is None and not found in stopped:
                if not found:
                    # If the user paused/cancelled in the app, do NOT recreate the task
                    if getattr(d, "status", None) in (config.Status.cancelled, "cancelled"):
                        emit_log("Aria2 task missing but item is paused/cancelled; not re-adding.")
                        return  # exit the monitor cleanly

                    emit_log("Aria2 GID not found; re-adding download.")
                    d.aria_gid = None
                    # Re-enter the start logic:
                    try:
                        # Re-run the add logic already above
                        url = d.url or d.eff_url or ""
                        is_torrent_file = url.lower().endswith(".torrent") or d.name.lower().endswith(".torrent")
                        is_magnet_link = url.startswith("magnet:?")
                        options = {"dir": d.folder, "out": d.name}

                        if is_torrent_file:
                            torrent_path = os.path.join(d.folder, d.name if d.name.lower().endswith(".torrent") else d.name + ".torrent")
                            if url.lower().endswith(".torrent"):
                                import requests
                                r = requests.get(url, timeout=30); r.raise_for_status()
                                with open(torrent_path, "wb") as f:
                                    f.write(r.content)
                            added = aria2.add_torrent(torrent_path, options=options)
                            d.aria_gid = added.gid
                        elif is_magnet_link:
                            added = aria2.add_magnet(url, options=options)
                            d.aria_gid = added.gid
                        else:
                            added = aria2.add_uris([url], options=options)
                            d.aria_gid = added.gid

                        emit_status("downloading")
                        continue  # go back to the loop with a fresh gid
                    except Exception as e:
                        emit_log(f"Failed to re-add aria2 task: {e}")
                        d.status = config.Status.error
                        emit_status("error")
                        return

                download = found

            # If torrent, lock onto the REAL content download
            if is_torrent_file or is_magnet_link:
                content = _pick_content_download(aria2, download.gid)
                if content is None:
                    emit_log("Waiting for torrent metadata...")
                    # don't fake 100%; keep showing partial info if any
                else:
                    if content.gid != d.aria_gid:
                        emit_log(f"[Aria2c] Switching to content GID: {content.gid}")
                        d.aria_gid = content.gid
                    download = content

            # Sync fields from aria2 → DownloadItem
            try:
                total = _safe_int(download.total_length)
                done  = _safe_int(download.completed_length)
                spd   = _safe_int(download.download_speed)

                # Keep these fresh; the progress property uses them
                d._speed = spd
                if total > 0:
                    d.size = total
                d.downloaded = done

                # Optional: adopt single-file torrent's real name/folder
                try:
                    if download.files and download.files[0].path:
                        rp = download.files[0].path
                        if os.path.isabs(rp) and os.path.basename(rp):
                            d.folder = os.path.dirname(rp) or d.folder
                            # Respect validate_file_name logic via the setter
                            d.name = os.path.basename(rp)
                except Exception:
                    pass

                # Periodic UI update
                now = time.time()
                if now - last_emit_time > 0.5:
                    last_emit_time = now
                    emit_progress(d.progress)
                    emit_log(f"{done}/{total} bytes @ {spd} B/s")

            except Exception as e:
                emit_log(f"Sync error: {e}")

                
            try:
                total = _safe_int(download.total_length)
                done  = _safe_int(download.completed_length)
                spd   = _safe_int(download.download_speed)
                st    = (getattr(download, "status", "") or "").lower()

                # If aria2 reports we fully got the bytes
                if total > 0 and done >= total:
                    # consider "idle" only if speed is ~zero
                    if spd <= 1 and st in ("active", "waiting"):
                        if idle_start_ts is None:
                            idle_start_ts = time.time()
                        # wait a little to allow hash-checking etc.
                        if time.time() - idle_start_ts >= 10:   # 10s dwell
                            # Treat as finished even if aria2 didn't flip yet
                            d.status = config.Status.completed
                            emit_status("completed")
                            emit_progress(100)
                            notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
                            return
                    else:
                        # reset the idle timer if speed resumes / state changes
                        idle_start_ts = None
                else:
                    idle_start_ts = None
            except Exception:
                idle_start_ts = None

            # Map aria2 status to our states
            st = (getattr(download, "status", "") or "").lower()
            if st in ("complete", "seeding"):
                d.status = config.Status.completed
                emit_status("completed")
                emit_progress(100)
                notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
                return
            
            vl = _safe_int(getattr(download, "verified_length", 0))

            if vl and total and vl >= total:
                d.status = config.Status.completed
                emit_status("completed")
                emit_progress(100)
                notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
                return

            if st in ("error", "removed"):
                d.status = config.Status.error
                emit_status("error")
                return

            if st == "paused":
                d.status = config.Status.cancelled
                
                log(f"[brain] cancelled manually for: {d.name}")
                if d.in_queue:
                    d.status = Status.queued

                emit_status("paused")
                emit_log("Aria2 paused; monitor exiting.")
                return
                # continue to monitor
            
            # Treat 'waiting' like an active state (metadata fetching/queueing)
            if st == "waiting":
                d.status = config.Status.downloading
                emit_status("downloading")
                # keep looping

            # active / waiting keep looping
            # (no-op here; loop continues)

    except Exception as e:
        emit_log("Fatal aria2 monitor error:\n" + traceback.format_exc())
        d.status = config.Status.error
        emit_status("error")
        return


def run_aria2c_video_audio_download(d, emitter=None):
    """
    aria2-driven download of separate video/audio HTTP streams (e.g., YouTube DASH direct links).
    - Uses distinct part files: <base>.video.mp4 and <base>.audio.(m4a/webm)
    - Resumes via 'continue:true'
    - Attaches to existing tasks by output filename when possible (prevents duplicates)
    - Merges parts into a temp file, then moves to final target (never in-place)
    """
    
    # -------- emitter helpers --------
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

    def _safe_int(x):
        try: return int(x)
        except: return 0

    # -------- derive paths / names --------
    base = safe_filename(os.path.splitext(d.name)[0]) or "download"
    # final user-visible target
    final_target = d.target_file or os.path.join(d.folder, base + ".mp4")
    if not final_target.lower().endswith(".mp4"):
        final_target = os.path.splitext(final_target)[0] + ".mp4"
    d.target_file = final_target

    # part files (NEVER equal to final_target)
    video_part = os.path.join(d.folder, base + ".video.mp4")
    audio_is_present = bool(d.audio_url and d.audio_url != d.url)
    if audio_is_present:
        audio_ext = ".m4a" if video_part.lower().endswith((".mp4", ".m4v", ".mov")) else ".webm"
        audio_part = os.path.join(d.folder, base + ".audio" + audio_ext)
        d.audio_file = audio_part
    else:
        audio_part = None

    video_aria2 = video_part + ".aria2"
    audio_aria2 = (audio_part + ".aria2") if audio_part else None

    # -------- connect aria2 --------
    aria2 = aria2c_manager.get_api()
    if not aria2:
        d.status = Status.error
        emit_status("error")
        emit_log("[Aria2c] API unavailable")
        return

    d.status = Status.downloading
    emit_status("downloading")
    emit_progress(0)
    d._progress = 0
    d.remaining_parts = 1
    d.last_known_progress = 0

    # -------- helpers to attach/add --------
    def _attach_gid_by_out(out_name):
        """Find an existing aria2 task whose first file path basename == out_name."""
        try:
            for dl in aria2.get_downloads() or []:
                try:
                    f0 = dl.files[0].path if dl.files and dl.files[0].path else ""
                    if os.path.basename(f0) == out_name:
                        return dl.gid
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _get_download(gid):
        if not gid:
            return None
        try:
            return aria2.get_download(gid)
        except Exception:
            return None

    # -------- VIDEO task: attach or add --------
    v_dl = None
    if getattr(d, "aria_gid", None):
        v_dl = _get_download(d.aria_gid)
        if v_dl and getattr(v_dl, "status", "").lower() == "paused":
            try: v_dl.resume()
            except: pass
        if not v_dl or getattr(v_dl, "status", "").lower() == "removed":
            v_dl = None
            d.aria_gid = None

    if not v_dl:
        attach_v = _attach_gid_by_out(os.path.basename(video_part))
        if attach_v:
            d.aria_gid = attach_v
            v_dl = _get_download(attach_v)

    if not v_dl:
        opts_v = {
            "dir": d.folder,
            "out": os.path.basename(video_part),
            "continue": "true",
            "always-resume": "true",
            "max-connection-per-server": str(config.aria2c_config["max_connections"]),
            "file-allocation": config.aria2c_config["file_allocation"],
        }
        added_video = aria2.add_uris([d.url], options=opts_v)
        d.aria_gid = added_video.gid
        emit_log(f"[Aria2c] Video GID: {d.aria_gid}")
        v_dl = _get_download(d.aria_gid)

    # -------- AUDIO task: attach or add --------
    a_dl = None
    if audio_is_present:
        if getattr(d, "audio_gid", None):
            a_dl = _get_download(d.audio_gid)
            if a_dl and getattr(a_dl, "status", "").lower() == "paused":
                try: a_dl.resume()
                except: pass
            if not a_dl or getattr(a_dl, "status", "").lower() == "removed":
                a_dl = None
                d.audio_gid = None

        if not a_dl:
            attach_a = _attach_gid_by_out(os.path.basename(audio_part))
            if attach_a:
                d.audio_gid = attach_a
                a_dl = _get_download(attach_a)

        if not a_dl:
            opts_a = {
                "dir": d.folder,
                "out": os.path.basename(audio_part),
                "continue": "true",
                "always-resume": "true",
                "max-connection-per-server": str(config.aria2c_config["max_connections"]),
                "file-allocation": config.aria2c_config["file_allocation"],
            }
            added_audio = aria2.add_uris([d.audio_url], options=opts_a)
            d.audio_gid = added_audio.gid
            emit_log(f"[Aria2c] Audio GID: {d.audio_gid}")
            a_dl = _get_download(d.audio_gid)

    # -------- monitor loop --------
    last_progress = -1
    try:
        while True:
            time.sleep(0.5)

            # refresh handles (they can change)
            v_dl = _get_download(d.aria_gid)
            a_dl = _get_download(d.audio_gid) if audio_is_present else None

            # early exit on paused
            try:
                if v_dl and (getattr(v_dl, "status", "") or "").lower() == "paused":
                    d.status = Status.cancelled
                    emit_status("paused")
                    emit_log(f"[Aria2c] Video paused; exiting monitor for {d.name}")
                    return
            except Exception:
                pass
            if audio_is_present:
                try:
                    if a_dl and (getattr(a_dl, "status", "") or "").lower() == "paused":
                        d.status = Status.cancelled
                        emit_status("paused")
                        emit_log(f"[Aria2c] Audio paused; exiting monitor for {d.name}")
                        return
                except Exception:
                    pass

            # progress & completion flags
            v_done = False
            a_done = not audio_is_present

            # VIDEO state
            if v_dl:
                v_status = (getattr(v_dl, "status", "") or "").lower()
                v_done = v_status in ("complete", "seeding")
                v_percent = _safe_int(getattr(v_dl, "progress", 0))
                d._downloaded = _safe_int(getattr(v_dl, "completed_length", 0))
                v_total = _safe_int(getattr(v_dl, "total_length", 0))
                if v_total > 0:
                    d.size = v_total
                d._speed = _safe_int(getattr(v_dl, "download_speed", 0))
                try:
                    d.remaining_time = v_dl.eta if v_dl.eta != -1 else 0
                except:
                    pass
            else:
                v_percent = 100 if (os.path.exists(video_part) and not os.path.exists(video_aria2)) else 0
                v_done = v_percent == 100

            # AUDIO state
            if audio_is_present:
                if a_dl:
                    a_status = (getattr(a_dl, "status", "") or "").lower()
                    a_done = a_status in ("complete", "seeding")
                    a_percent = _safe_int(getattr(a_dl, "progress", 0))
                else:
                    a_percent = 100 if (os.path.exists(audio_part) and not os.path.exists(audio_aria2)) else 0
                    a_done = a_percent == 100
            else:
                a_percent = 0

            # combined progress for UI
            combined = (v_percent + (a_percent if audio_is_present else 0)) // (2 if audio_is_present else 1)
            d._progress = combined
            d.last_known_progress = combined

            if emitter and combined != last_progress:
                emit_progress(combined)
                emit_log(f"⬇ {size_format(getattr(d,'downloaded',0))} | Video: {v_percent}% | Audio: {a_percent if audio_is_present else '—'}%")
                last_progress = combined

            # completion → merge/finalize
            if v_done and a_done:
                # single progressive file: just move to final if needed
                if not audio_is_present:
                    if os.path.abspath(video_part) != os.path.abspath(final_target):
                        try:
                            if os.path.exists(final_target):
                                os.remove(final_target)
                            rename_file(video_part, final_target)
                        except Exception as e:
                            log(f"[Aria2c] Finalize move failed: {e}", log_level=3)
                            d.status = Status.error
                            emit_status("error")
                            return
                    d.status = Status.completed
                    emit_status("completed")
                    emit_progress(100)
                    notify(f"File: {os.path.basename(final_target)} \n saved at: {d.folder}", title=f'{APP_NAME} - Download completed')
                    return

                # separate A/V → MERGE parts to a TEMP then move to final
                d.status = Status.merging_audio
                emit_status("merging_audio")
                temp_out = os.path.join(d.folder, base + ".merge.tmp.mp4")
                if os.path.exists(temp_out):
                    try: os.remove(temp_out)
                    except: pass

                # sanity checks
                if not os.path.exists(video_part):
                    log(f"[Aria2c] Missing video part: {video_part}")
                    d.status = Status.error
                    emit_status("error")
                    return
                if not os.path.exists(audio_part):
                    log(f"[Aria2c] Missing audio part: {audio_part}")
                    d.status = Status.error
                    emit_status("error")
                    return

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                error, output = loop.run_until_complete(
                    async_merge_video_audio(video_part, audio_part, temp_out, d)
                )

                if error:
                    log(f"[Merge] FFmpeg merge failed: {output}", log_level=3)
                    d.status = Status.error
                    emit_status("error")
                    return

                # finalize: temp_out → final_target
                try:
                    if os.path.exists(final_target):
                        os.remove(final_target)
                    rename_file(temp_out, final_target)
                    d.target_file = final_target
                    # cleanup parts + .aria2 sidecars
                    try:
                        for f in (video_part, audio_part, video_aria2, audio_aria2):
                            if f and os.path.exists(f):
                                os.remove(f)
                    except Exception:
                        pass
                    d.name = os.path.basename(final_target)
                except Exception as e:
                    log(f"[Aria2c] Post-merge move failed: {e}", log_level=3)
                    d.status = Status.error
                    emit_status("error")
                    return

                d.status = Status.completed
                emit_status("completed")
                emit_progress(100)
                notify(f"File: {d.name} \n saved at: {d.folder}", title=f'{APP_NAME} - Download completed')
                return

            # user cancelled mid-way
            if d.status == Status.cancelled:
                log(f"[Aria2c] Download cancelled: {d.name}")
                return

    except Exception as e:
        d.status = Status.error
        emit_status("error")
        log(f"[Aria2c] Exception during download: {e}", log_level=3)
    finally:
        emit_log(f"[Aria2c] Done processing {d.name}")
        log(f"[Aria2c] Done processing {d.name}")


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




def run_ytdlp_download(d, emitter=None):
    log(f"[yt-dlp] Starting download: {d.name}")
    d.status = Status.downloading
    d._progress = 0
    d.remaining_parts = 1
    d.last_known_progress = 0

    def progress_hook(info):
        if d.status == Status.cancelled:
            raise yt_dlp.utils.DownloadCancelled("User cancelled download.")

        if info["status"] == "downloading":
            percent = info.get("_percent_str", "0%").strip().replace('%', '')
            percent = re.sub(r'\x1b\[[0-9;]*m', '', percent)
            d._progress = float(percent)

            d.downloaded = info.get("downloaded_bytes", 0)
            d.size = info.get("total_bytes") or info.get("total_bytes_estimate", 0)
            d._speed = info.get("speed", 0)
            d.remaining_time = info.get("eta", 0)

            if emitter:
                emitter.progress_changed.emit(int(d._progress))
                emitter.status_changed.emit("downloading")
                emitter.log_updated.emit(
                    f"⬇ {size_format(d.speed, '/s')} | Done: {size_format(d.downloaded)} / {size_format(d.total_size)}"
                )

    # Define paths
    output_path = os.path.join(d.folder, d.name)
    ffmpeg_path = os.path.join(config.sett_folder, "ffmpeg.exe")

    # Prepare format code
    format_code = None
    if getattr(d, "format_id", None) and getattr(d, "audio_format_id", None):
        format_code = f"{d.format_id}+{d.audio_format_id}"
    elif getattr(d, "format_id", None):
        format_code = d.format_id

    # Configure proxy
    proxy_url = None
    if config.proxy != "":
        proxy_url = config.proxy
        if config.proxy_user and config.proxy_pass:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(proxy_url)
            proxy_url = urlunparse(parsed._replace(netloc=f"{config.proxy_user}:{config.proxy_pass}@{parsed.hostname}:{parsed.port}"))

    # yt-dlp options
    ydl_opts = {
        "outtmpl": output_path,
        "progress_hooks": [progress_hook],
        "quiet": config.ytdlp_config["quiet"],
        "no_warnings": config.ytdlp_config["no_warnings"],
        "retries": config.ytdlp_config["retries"],
        "continuedl": True,
        "nopart": False,
        "concurrent_fragment_downloads": config.ytdlp_config["concurrent_fragment_downloads"],
        "ffmpeg_location": get_ffmpeg_path(),
        "format": format_code,
        "writeinfojson": config.ytdlp_config["writeinfojson"],
        "writedescription": config.ytdlp_config["writedescription"],
        "writeannotations": config.ytdlp_config["writeannotations"],
        "writemetadata": config.ytdlp_config["writemetadata"],
        "merge_output_format": "mp4",
        "proxy": proxy_url,
        "cookiesfile": config.ytdlp_config["cookiesfile"],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([d.url])

        # ✅ Only mark complete after yt-dlp finishes and merges
        d.status = Status.completed
        d._progress = 100

        if emitter:
            emitter.progress_changed.emit(100)
            emitter.status_changed.emit("completed")

        delete_folder(d.temp_folder)
        log(f"[yt-dlp] Finished and merged: {d.name}")
        notify(f"File: {d.name} \nsaved at: {d.folder}", title=f"{APP_NAME} - Download completed")
        

    except yt_dlp.utils.DownloadCancelled:
        d.status = Status.cancelled
        log(f"[yt-dlp] Cancelled by user: {d.name}")

    except Exception as e:
        log(f"[yt-dlp] Error: {e}")

        # Fallback only for known merge error
        if "Postprocessing: Error opening input files" in str(e):
            log("[yt-dlp] Detected FFmpeg postprocessing error – attempting fallback merge")

            try:
                base_name = os.path.splitext(d.name)[0]
                video_file = os.path.join(d.folder, f"{base_name}.f{d.format_id}.mp4")
                audio_file = os.path.join(d.folder, f"{base_name}.f{d.audio_format_id}.mp4")
                output_file = os.path.join(d.folder, d.name)

                if os.path.exists(video_file) and os.path.exists(audio_file):
                    d.status = Status.merging_audio
                    log("[yt-dlp] Found both audio and video files, initiating fast fallback merge")

                    cmd = [
                        get_ffmpeg_path(),
                        "-i", video_file,
                        "-i", audio_file,
                        "-c:v", "copy",
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-shortest",
                        output_file
                    ]

                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                    if result.returncode == 0:
                        d.status = Status.completed
                        d._progress = 100

                        if emitter:
                            emitter.progress_changed.emit(100)
                            emitter.status_changed.emit("completed")

                        delete_folder(d.temp_folder)

                        # Cleanup fragment files if any
                        try:
                            os.remove(video_file)
                            os.remove(audio_file)
                        except Exception as cleanup_error:
                            log(f"[cleanup] Could not delete fragments: {cleanup_error}")

                        notify(f"File: {d.name} \nsaved at: {d.folder}", title=f"{APP_NAME} - Download completed")
                        log(f"[yt-dlp] Fallback merge succeeded for: {d.name}")
                        return
                    else:
                        log(f"[yt-dlp] Fallback merge failed: {result.stderr}")
            except Exception as fallback_e:
                log(f"[yt-dlp] Fallback merge exception: {fallback_e}")

        # Fallback also failed, now mark as failed
        d.status = Status.error
        if emitter:
            emitter.status_changed.emit("error")



    finally:
        log(f"[yt-dlp] Done processing {d.name}")
        if emitter:
            emitter.log_updated.emit(f"[yt-dlp] Done processing {d.name}")



def file_manager(d, keep_segments=False, emitter=None):
    while True:
        time.sleep(0.1)

        job_list = [seg for seg in d.segments if not seg.completed]

        for seg in job_list:
            if seg.completed:
                continue
            if not seg.downloaded:
                break

            try:
                if seg.merge:
                    with open(seg.tempfile, 'ab') as trgt_file:
                        with open(seg.name, 'rb') as src_file:
                            trgt_file.write(src_file.read())
                seg.completed = True
                log('>> completed segment: ', os.path.basename(seg.name))

                if not keep_segments:
                    delete_file(seg.name)

                if emitter:
                    progress = d.progress
                    emitter.progress_changed.emit(progress)
                    emitter.log_updated.emit(f"Completed: {os.path.basename(seg.name)}")

            except Exception as e:
                log('failed to merge segment', seg.name, ' - ', e)

        if not job_list:
            # Handle m3u8 streams (HLS)
            if 'm3u8' in d.protocol:
                d.status = Status.merging_audio
                log(f"[Merge] Merging started for for this video", log_level=1)
                success = post_process_hls(d)
                if not success:
                    d.status = Status.error
                    break
                else:
                    rename_file(d.temp_file, d.target_file)
                    delete_folder(d.temp_folder)

            # Handle DASH (separate audio/video)
            if d.type == 'dash':
                output_file = d.target_file.replace(' ', '_')
                if not is_download_complete(d):
                    log(f"Skipping merge: {d.name} is not fully downloaded.")
                    d.status = Status.error
                    break

                d.status = Status.merging_audio
                log(f"This is the temp_file{d.temp_file} and audio {d.audio_file}", log_level=3)
                # error, output = merge_video_audio(d.temp_file, d.audio_file, output_file, d)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                error, output = loop.run_until_complete(
                    async_merge_video_audio(d.temp_file, d.audio_file, output_file, d)
                )

                if not error:
                    rename_file(output_file, d.target_file)
                    d.delete_tempfiles()
                else:
                    d.status = Status.error
                    # show_critical(title="Merge Error", msg="FFmpeg merge failed, needs re-merging. Right click on the download item to select remerged.")
                    break

            # Handle "normal" single-stream downloads
            if not ('m3u8' in d.protocol or d.type == 'dash'):
                log(f"This is the temp_file{d.temp_file} and audio {d.audio_file} and target file {d.target_file}", log_level=3)
                rename_file(d.temp_file, d.target_file)
                delete_folder(d.temp_folder)
                
            d.status = Status.completed
            if emitter:
                emitter.status_changed.emit("completed")
                emitter.progress_changed.emit(100.0)
            break


        if d.status != Status.downloading:
            break

    if d.status != Status.completed:
        d.save_progress_info()

    log(f'file_manager {d.num}: quitting')


def thread_manager(d, emitter=None):

    workers = [Worker(tag=i, d=d) for i in range(config.max_connections)]
    free_workers = list(reversed(range(config.max_connections)))
    busy_workers = []
    live_threads = []

    job_list = [seg for seg in d.segments if not seg.downloaded]
    job_list.reverse()

    while True:
        time.sleep(0.1)

        for _ in range(d.q.jobs.qsize()):
            job = d.q.jobs.get()
            job_list.append(job)

        allowable_connections = min(config.max_connections, d.remaining_parts)
        try:
            speed_limit_int = int(config.speed_limit)
        except (ValueError, TypeError):
            speed_limit_int = 0
        worker_sl = speed_limit_int * 1024 // allowable_connections if allowable_connections else 0

        if free_workers and job_list and d.status == config.Status.downloading:
            for _ in free_workers[:]:
                try:
                    worker_num, seg = free_workers.pop(), job_list.pop()
                    busy_workers.append(worker_num)
                    worker = workers[worker_num]
                    worker.reuse(seg=seg, speed_limit=worker_sl)
                    t = Thread(target=worker.run, daemon=True, name=str(worker_num))
                    live_threads.append(t)
                    t.start()
                except:
                    break

        d.live_connections = len(busy_workers)
        d.remaining_parts = len(busy_workers) + len(job_list) + d.q.jobs.qsize()

        for t in live_threads:
            if not t.is_alive():
                worker_num = int(t.name)
                live_threads.remove(t)
                busy_workers.remove(worker_num)
                free_workers.append(worker_num)

        if d.status != config.Status.downloading:
            break

        if not busy_workers and not job_list and not d.q.jobs.qsize():
            break

    log(f'thread_manager {d.num}: quitting')
