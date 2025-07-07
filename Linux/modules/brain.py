
import io
import os
import re
import socket
import time
import subprocess
import yt_dlp
import requests
from threading import Thread
from modules.video import merge_video_audio, is_download_complete, youtube_dl_downloader, unzip_ffmpeg, pre_process_hls, post_process_hls  # unzip_ffmpeg required here for ffmpeg callback
from modules import config
from modules.config import Status, active_downloads, APP_NAME
from modules.utils import (log, size_format, popup, notify, delete_folder, delete_file, rename_file, load_json, save_json, validate_file_name)
from modules.worker import Worker
from modules.downloaditem import Segment
from modules.postprocessing import async_merge_video_audio
from modules.aria2c_manager import aria2c_manager
from modules.threadpool import executor
import asyncio
from modules.helper import safe_filename




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

# brain.py
def brain(d=None, emitter=None):
    log(f"[brain] ENGINE DEBUG — d.engine={d.engine} | d.type={d.type} | protocol={d.protocol} | url={d.url}")

    # Check which engine to use

    if d.engine in ["aria2", "aria2c"]:
        log(f"[brain] aria2c selected for: {d.name}")

        # Ensure original_url is stored before overriding d.url
        if ("youtube.com" in d.url or "youtu.be" in d.url):
            if not getattr(d, "original_url", None) or "googlevideo.com" in d.url:
                d.original_url = d.url  # backup the original YouTube URL

        if ("youtube.com" in d.original_url or "youtu.be" in d.original_url) and not getattr(d, "vid_info", None):
            log(f"[brain] Extracting stream info from YouTube original URL for aria2c...")
            from modules.video import get_ytdl_options, extract_info_blocking, Stream

            ydl_opts = get_ytdl_options()
            vid_info = extract_info_blocking(d.original_url, ydl_opts)
            d.vid_info = vid_info

        elif getattr(d, "vid_info", None):
            log(f"[brain] Reusing existing vid_info for {d.name}")

        if getattr(d, "vid_info", None):
            from modules.video import Stream
            streams = [Stream(f) for f in d.vid_info.get("formats", [])]
            dash_streams = [s for s in streams if s.mediatype == 'dash']
            audio_streams = [s for s in streams if s.mediatype == 'audio']

            best_dash = max(dash_streams, key=lambda s: s.quality, default=None)
            best_audio = max(audio_streams, key=lambda s: s.quality, default=None)

            if not best_dash or not best_audio:
                log("[brain] Could not find valid dash/audio streams — falling back to yt-dlp.")
                run_ytdlp_download(d, emitter)
                return

            d.eff_url = best_dash.url
            d.audio_url = best_audio.url
            d.format_id = best_dash.format_id
            d.audio_format_id = best_audio.format_id

            d.name = validate_file_name(d.vid_info.get("title"))
            

            d.url = d.eff_url  # Set after original_url is saved

            run_aria2c_video_audio_download(d, emitter)
        else:
            log("[Aria2c] Running normal static file download")
            d.original_url = d.url
            run_aria2c_download(d, emitter)
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


# def run_aria2c_download(d, emitter=None):
#     log(f"[Aria2c] Starting: {d.name}")
#     d.status = Status.downloading
#     d._progress = 0
#     d.remaining_parts = 1
#     d.last_known_progress = 0

#     try:
#         aria2 = aria2c_manager.get_api()

#         download = None
#         if d.aria_gid:
#             try:
#                 download = aria2.get_download(d.aria_gid)
#                 if download is None or download.status == 'removed':
#                     raise Exception("GID not found or removed")
#                 if download.status == 'paused':
#                     download.resume()
#             except Exception as e:
#                 log(f"[Aria2c] Resume failed or GID not valid: {e}")
#                 d.aria_gid = None  # fallback to new

#         if not d.aria_gid:
#             added = aria2.add_uris([d.url], options={
#                 "dir": d.folder, 
#                 "out": d.name, 
#                 "pause": "false",
#                 "file-allocation": config.aria2c_config["file_allocation"], 
#                 "max-connection-per-server": config.aria2c_config["max_connections"],
#                 "follow-torrent": "true" if config.aria2c_config["follow_torrent"] else "false",
#                 "enable-dht": "true" if config.aria2c_config["enable_dht"] else "false",
                                                     
#             })
#             d.aria_gid = added.gid
#             log(f"[Aria2c] New GID assigned: {d.aria_gid}")

#         if emitter:
#             emitter.status_changed.emit("downloading")
#             emitter.progress_changed.emit(0)

#         while True:
#             try:
#                 download = aria2.get_download(d.aria_gid)
#             except Exception as e:
#                 log(f"[Aria2c] Error fetching download: {e}")
#                 d.status = Status.error
#                 break

#             percent = int(download.progress)
#             d._progress = percent
#             d.last_known_progress = percent

#             d._total_size = int(download.total_length)
#             d._downloaded = int(download.completed_length)
#             d._speed = int(download.download_speed)
#             d.remaining_time = download.eta if download.eta != -1 else 0

#             if emitter:
#                 emitter.progress_changed.emit(percent)
#                 emitter.log_updated.emit(f"⬇ {size_format(d.speed, '/s')} | Done: {size_format(d.downloaded)} / {size_format(d.total_size)}")

#             if download.is_complete:
#                 d.status = Status.completed
#                 log(f"[Aria2c] Completed: {d.name}")
#                 if emitter:
#                     emitter.progress_changed.emit(100)
#                     emitter.status_changed.emit("completed")
#                 delete_folder(d.temp_folder)
#                 notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
#                 break

#             elif download.is_removed:
#                 d.status = Status.error
#                 log(f"[Aria2c] Error or removed: {d.name}")
#                 if emitter:
#                     emitter.status_changed.emit("error")
#                 break

#             elif download.is_paused:
#                 if d.status == Status.cancelled:
#                     log(f"brain() cancelled manually for: {d.name}")
#                     if d.in_queue:
#                         d.status = Status.queued
#                     break

#             time.sleep(1)

#     except Exception as e:
#         d.status = Status.error
#         log(f"[Aria2c] Exception during download: {e}")
#         if emitter:
#             emitter.status_changed.emit("error")

#     finally:
#         if emitter:
#             emitter.log_updated.emit(f"[Aria2c] Done processing {d.name}")
#         log(f"[Aria2c] Done processing {d.name}")




# def run_aria2c_download(d, emitter=None):
    
    
#     log(f"[Aria2c] Starting: {d.name}")
#     d.status = Status.downloading
#     d._progress = 0
#     d.remaining_parts = 1
#     d.last_known_progress = 0

    

#     aria2 = aria2c_manager.get_api()
#     # d.started = time.time()

#     is_torrent_file = d.url.endswith(".torrent") or d.name.endswith(".torrent")
#     is_magnet_link = d.url.startswith("magnet:?")

#     try:
#         download = None
#         if d.aria_gid:
#             try:
#                 download = aria2.get_download(d.aria_gid)
#                 if download is None or download.status == 'removed':
#                     raise Exception("GID not found or removed")
#                 if download.status == 'paused':
#                     download.resume()
#             except Exception as e:
#                 log(f"[Aria2c] Resume failed or GID not valid: {e}")
#                 d.aria_gid = None  # fallback to new

#         if not d.aria_gid:
#             options = {
#                 "dir": d.folder,
#                 "pause": "false",
#                 "file-allocation": config.aria2c_config["file_allocation"],
#                 "max-connection-per-server": config.aria2c_config["max_connections"],
#                 "follow-torrent": "true" if config.aria2c_config["follow_torrent"] else "false",
#                 "enable-dht": "true" if config.aria2c_config["enable_dht"] else "false",
#             }

            
#             # if is_torrent_file:
#             #     # ⛔ Avoid downloading .torrent twice
#             #     torrent_path = os.path.join(d.folder, d.name)
#             #     if not os.path.exists(torrent_path):
#             #         log(f"[Aria2c] Downloading .torrent file: {d.url}")
#             #         r = requests.get(d.url)
#             #         r.raise_for_status()
#             #         with open(torrent_path, 'wb') as f:
#             #             f.write(r.content)
#             #     added = aria2.add_torrent(torrent_path, options=options)

#             if is_torrent_file:
#                 torrent_path = os.path.join(d.folder, d.name)
#                 log(f"[Aria2c] Downloading .torrent file: {torrent_path}")
#                 response = requests.get(d.url)
#                 response.raise_for_status()
#                 with open(torrent_path, 'wb') as f:
#                     f.write(response.content)

#                 added = aria2.add_torrent(torrent_path, options=options)
#                 d.aria_gid = added.gid
#                 log(f"[Aria2c] Initial GID (metadata): {d.aria_gid}")

#                 # 🔁 Poll until real payload GID is assigned via followed_by
#                 for _ in range(15):
#                     try:
#                         meta_dl = aria2.get_download(d.aria_gid)
#                         if meta_dl.followed_by:
#                             real_gid = meta_dl.followed_by[0]
#                             log(f"[Aria2c] Found real GID: {real_gid}")
#                             d.aria_gid = real_gid
#                             break
#                     except Exception as e:
#                         log(f"[Aria2c] Waiting for followed_by GID...: {e}")
#                     time.sleep(1)
#                 else:
#                     log("[Aria2c] ❗ Failed to switch to real GID — fallback to metadata GID")


            
#             # Link is a magnet link
#             elif is_magnet_link:
#                 added = aria2.add_magnet(d.url, options=options)
#                 log(f"[Aria2c] Added magnet link: {d.url}")
                
#             # ✅ Regular HTTP/FTP file download
#             else:
#                 options["out"] = d.name
#                 added = aria2.add_uris([d.url], options=options)
#                 log(f'[Aria2c] The else statement took control {added}')

#             d.aria_gid = added.gid

            
            

#             log(f"[Aria2c] New GID assigned: {d.aria_gid}")

            



#         if emitter:
#             emitter.status_changed.emit("downloading")
#             emitter.progress_changed.emit(0)

#         while True:
#             try:
#                 download = aria2.get_download(d.aria_gid)
#             except Exception as e:
#                 log(f"[Aria2c] Error fetching download: {e}")
#                 d.status = Status.error
#                 break

#             percent = int(download.progress)
#             d._progress = percent
#             d.last_known_progress = percent

#             # d._total_size = int(download.total_length)
#             # d._downloaded = int(download.completed_length)


#             # Aggregate actual download progress from all files (useful for torrents)
#             if download.files:
               
#                 total_size = sum(int(f.length) for f in download.files)
#                 completed_size = sum(int(f.completed_length) for f in download.files)
#                 d._total_size = total_size
#                 d._downloaded = completed_size
#                 print(f"[Aria2c] Total size: {size_format(total_size)}, Downloaded: {size_format(completed_size)}, Percent: {percent}")
#                 print(f"[Aria2c] D.TOTAL SIZE: {d._total_size}, D.DOWNLOADED: {d._downloaded}, D.PROGRESS: {d._progress}, D.LAST_KS: {d.last_known_progress}")

                
#             else:
#                 d._total_size = int(download.total_length)
#                 d._downloaded = int(download.completed_length)

#             if d._total_size > 0:
#                 d._progress = int((d._downloaded / d._total_size) * 100)


#             d._speed = int(download.download_speed)
#             d.remaining_time = download.eta if download.eta != -1 else 0

#             if emitter:
#                 emitter.progress_changed.emit(percent)
#                 emitter.log_updated.emit(f"⬇ {size_format(d.speed, '/s')} | Done: {size_format(d.downloaded)} / {size_format(d.total_size)}")

#             if download.is_complete:
#                 d.status = Status.completed
#                 log(f"[Aria2c] Completed: {d.name}")
#                 if emitter:
#                     emitter.progress_changed.emit(100)
#                     emitter.status_changed.emit("completed")
#                 delete_folder(d.temp_folder)
#                 notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
#                 break

#             elif download.is_removed:
#                 d.status = Status.error
#                 log(f"[Aria2c] Error or removed: {d.name}")
#                 if emitter:
#                     emitter.status_changed.emit("error")
#                 break

#             elif download.is_paused:
#                 if d.status == Status.cancelled:
#                     log(f"brain() cancelled manually for: {d.name}")
#                     if d.in_queue:
#                         d.status = Status.queued
#                     break

#             time.sleep(1)

#     except Exception as e:
#         d.status = Status.error
#         log(f"[Aria2c] Exception during download: {e}")
#         if emitter:
#             emitter.status_changed.emit("error")

#     finally:
#         if emitter:
#             emitter.log_updated.emit(f"[Aria2c] Done processing {d.name}")
#         log(f"[Aria2c] Done processing {d.name}")



def run_aria2c_download(d, emitter=None):
    log(f"[Aria2c] Starting: {d.name}")
    d.status = Status.downloading
    d._progress = 0
    d.remaining_parts = 1
    d.last_known_progress = 0

    aria2 = aria2c_manager.get_api()

    is_torrent_file = d.url.endswith(".torrent") or d.name.endswith(".torrent")
    is_magnet_link = d.url.startswith("magnet:?")

    try:
        download = None
        if d.aria_gid:
            try:
                download = aria2.get_download(d.aria_gid)
                if download is None or download.status == 'removed':
                    raise Exception("GID not found or removed")
                if download.status == 'paused':
                    download.resume()
            except Exception as e:
                log(f"[Aria2c] Resume failed or GID not valid: {e}")
                d.aria_gid = None  # fallback to new

        if not d.aria_gid:
            options = {
                "dir": d.folder,
                "pause": "false",
                "file-allocation": config.aria2c_config["file_allocation"],
                "max-connection-per-server": config.aria2c_config["max_connections"],
                "follow-torrent": "true" if config.aria2c_config["follow_torrent"] else "false",
                #"follow-torrent": "mem",  # ✅ THIS IS THE CRITICAL FIX
                "enable-dht": "true" if config.aria2c_config["enable_dht"] else "false",
            }

            if is_torrent_file:
                torrent_path = os.path.join(d.folder, d.name)
                log(f"[Aria2c] Downloading .torrent file: {torrent_path}")
                response = requests.get(d.url)
                response.raise_for_status()
                with open(torrent_path, 'wb') as f:
                    f.write(response.content)

                added = aria2.add_torrent(torrent_path, options=options)
                d.aria_gid = added.gid
                log(f"[Aria2c] Initial GID (metadata): {d.aria_gid}")

                # 🔁 Poll until real payload GID is assigned via followed_by
                for _ in range(15):
                    try:
                        meta_dl = aria2.get_download(d.aria_gid)
                        if meta_dl.followed_by:
                            real_gid = meta_dl.followed_by[0]
                            log(f"[Aria2c] Found real GID: {real_gid}")
                            d.aria_gid = real_gid

                            # --- PATCH: Reset progress and size for real payload ---
                            d.progress = 0
                            d.downloaded = 0
                            d.total_size = 0
                            # ------------------------------------------------------

                            break
                    except Exception as e:
                        log(f"[Aria2c] Waiting for followed_by GID...: {e}")
                    time.sleep(1)
   
            elif is_magnet_link:
                added = aria2.add_magnet(d.url, options=options)
                log(f"[Aria2c] Added magnet link: {d.url}")

            else:
                options["out"] = d.name
                added = aria2.add_uris([d.url], options=options)
                log(f'[Aria2c] The else statement took control {added}')

            d.aria_gid = added.gid
            log(f"[Aria2c] New GID assigned: {d.aria_gid}")

        if emitter:
            emitter.status_changed.emit("downloading")
            emitter.progress_changed.emit(0)

        while True:
            try:
                download = aria2.get_download(d.aria_gid)
            except Exception as e:
                log(f"[Aria2c] Error fetching download: {e}")
                d.status = Status.error
                break

            # --- Aggregate progress for torrents and normal files ---
            if download.files and len(download.files) > 1:
                d.total_size = sum(int(f.length) for f in download.files)
                d.downloaded = sum(int(f.completed_length) for f in download.files)
            else:
                d.total_size = int(download.total_length)
                d.downloaded = int(download.completed_length)

            if d.total_size > 0:
                d.progress = int((d.downloaded / d.total_size) * 100)
            else:
                d.progress = 0



            # ...emit signals, update GUI, etc...

            d.last_known_progress = d._progress
            d._speed = int(download.download_speed)
            d.remaining_time = download.eta if download.eta != -1 else 0

            # Print debug info
            #print(f"[Aria2c] Total size: {size_format(d.total_size)}, Downloaded: {size_format(completed_size)}, Progress: {d._progress}%")

            if emitter:
                emitter.progress_changed.emit(d._progress)
                emitter.log_updated.emit(f"⬇ {size_format(d.speed, '/s')} | Done: {size_format(d.downloaded)} / {size_format(d.total_size)}")

            if download.is_complete:
                d.status = Status.completed
                d.progress = 100
                log(f"[Aria2c] Completed: {d.name}")
                if emitter:
                    emitter.progress_changed.emit(100)
                    emitter.status_changed.emit("completed")
                delete_folder(d.temp_folder)
                notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
                break

            elif download.is_removed:
                d.status = Status.error
                log(f"[Aria2c] Error or removed: {d.name}")
                if emitter:
                    emitter.status_changed.emit("error")
                break

            elif download.is_paused:
                if d.status == Status.cancelled:
                    log(f"brain() cancelled manually for: {d.name}")
                    if d.in_queue:
                        d.status = Status.queued
                    break

            time.sleep(1)

    except Exception as e:
        d.status = Status.error
        log(f"[Aria2c] Exception during download: {e}")
        if emitter:
            emitter.status_changed.emit("error")

    finally:
        if emitter:
            emitter.log_updated.emit(f"[Aria2c] Done processing {d.name}")
        log(f"[Aria2c] Done processing {d.name}")








def run_aria2c_video_audio_download(d, emitter=None):
    log(f"[Aria2c] Starting: {d.name}")
    d.status = Status.downloading
    d._progress = 0
    d.remaining_parts = 1
    d.last_known_progress = 0

    video_path = os.path.join(d.folder, d.name)
    aria2_temp = video_path + '.aria2'

    if os.path.exists(video_path) or os.path.exists(aria2_temp):
        log(f"[Aria2c] Video part already exists: {video_path}, skipping add_uris")
    # else:
    #     added_video = aria2.add_uris([...])
    #     d.aria_gid = added_video.gid



    try:
        aria2 = aria2c_manager.get_api()

        download = None
        if d.aria_gid:
            try:
                download = aria2.get_download(d.aria_gid)
                if download is None or download.status == 'removed':
                    raise Exception("GID not found or removed")
                if download.status == 'paused':
                    download.resume()
            except Exception as e:
                log(f"[Aria2c] Resume failed or GID not valid: {e}")
                d.aria_gid = None  # fallback to new

        # ---- Handle single or dual download case ----
        audio_is_present = bool(d.audio_url and d.audio_url != d.url)

        # Submit video file
        added_video = aria2.add_uris([d.url], options={
            "dir": d.folder,
            "out": d.name,
            "pause": "false",
            "file-allocation": config.aria2c_config["file_allocation"],
            "max-connection-per-server": config.aria2c_config["max_connections"],
            "follow-torrent": "true" if config.aria2c_config["follow_torrent"] else "false",
            "enable-dht": "true" if config.aria2c_config["enable_dht"] else "false",
        })
        d.aria_gid = added_video.gid
        log(f"[Aria2c] Video GID assigned: {d.aria_gid}")

        # Submit audio file separately
        if audio_is_present:
            #audio_out = f"audio_for_{d.name}"
            audio_out = os.path.basename(d.audio_file)  # 👈 Matches exactly

            added_audio = aria2.add_uris([d.audio_url], options={
                "dir": d.folder,
                "out": audio_out,
                "pause": "false",
                "file-allocation": config.aria2c_config["file_allocation"],
                "max-connection-per-server": config.aria2c_config["max_connections"],
            })
            d.audio_gid = added_audio.gid
            log(f"[Aria2c] Audio GID assigned: {d.audio_gid}")

        if emitter:
            emitter.status_changed.emit("downloading")
            emitter.progress_changed.emit(0)

        video_complete = False
        audio_complete = not audio_is_present  # mark true if no audio
        last_progress = -1

        while True:
            # Video progress
            try:
                v = aria2.get_download(d.aria_gid)
                video_complete = v.is_complete
                v_percent = int(v.progress)
            except:
                v_percent = 0
            
            d._downloaded = int(v.completed_length)
            d.size = int(v.total_length) if v.total_length else 0
    

            # d._total_size = int(v.total_length)
            d._speed = int(v.download_speed)
            d.remaining_time = v.eta if v.eta != -1 else 0


            # Audio progress
            if audio_is_present:
                try:
                    a = aria2.get_download(d.audio_gid)
                    audio_complete = a.is_complete
                    a_percent = int(a.progress)
                except:
                    a_percent = 0
            else:
                a_percent = 0

            # Average progress
            combined = (v_percent + a_percent) // (2 if audio_is_present else 1)
            print(combined, v_percent, a_percent, d._downloaded, d.size)
            d._progress = combined
            d.last_known_progress = combined

            if emitter and combined != last_progress:
                emitter.progress_changed.emit(combined)
                emitter.log_updated.emit(
                    f"⬇ {size_format(d.downloaded)} | Video: {v_percent}% | Audio: {a_percent if audio_is_present else '—'}%"
                )
                last_progress = combined


            if video_complete and audio_complete:

                # Both video and audio are complete

                if d.type == 'dash' or 'm3u8' in d.protocol:
                    log(f"[Aria2c] Both video and audio completed for: {d.name}")
                    # output_file = d.target_file.replace(' ', '_')

                    # Force clean filename and extension
                    safe_name = safe_filename(d.name)
                    if not safe_name.endswith('.mp4'):
                        safe_name += '.mp4'
                        # safe_name = config.ytdlp_config['merge_output_format']

                    output_file = os.path.join(d.folder, safe_name)
                    video_path = os.path.join(d.folder, d.name)

                    # if not is_download_complete(d):
                    #     log(f"Skipping merge: {d.name} is not fully downloaded.")
                    #     d.status = Status.error
                    #     break

                    d.status = Status.merging_audio
                    log(f"This is the temp_file{video_path} and audio {d.audio_file}", log_level=3)
                    # error, output = merge_video_audio(d.temp_file, d.audio_file, output_file, d)
                    if not os.path.exists(video_path):
                        log(f"[Aria2c] ERROR: Video file not found at {video_path}")
                        d.status = Status.error
                        break

                    if not os.path.exists(d.audio_file):
                        log(f"[Aria2c] ERROR: Audio file not found at {d.audio_file}")
                        d.status = Status.error
                        break

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    error, output = loop.run_until_complete(
                        async_merge_video_audio(video_path, d.audio_file, output_file, d)
                    )
                    if error:
                        log(f"[Merge] FFmpeg merge failed: {output}")
                        d.status = Status.error
                        break

                    # if not error:
                    #     rename_file(output_file, d.target_file)
                    #     d.delete_tempfiles()
                    # else:
                    #     d.status = Status.error
                    #     break

                    if not error:
                        print(f'[Aria2c] Renaming output file to: {output_file} from {d.target_file}')
                        if os.path.exists(d.target_file):
                            os.remove(d.target_file)  # Prevent WinError 183
                        # rename_file(output_file, d.target_file)
                        rename_file(d.target_file, output_file)
                        d.delete_tempfiles()
                        d.name = safe_name
                    else:
                        d.status = Status.error
                        break


                d.status = Status.completed
                log(f"[Aria2c] Download completed for: {d.name}")
                if emitter:
                    emitter.status_changed.emit("completed")
                    emitter.progress_changed.emit(100)
                notify(f"File: {d.name} \n saved at: {d.folder}", title=f'{APP_NAME} - Download completed')
                break

           
            if d.status == Status.cancelled:
                log(f"[Aria2c] Download cancelled: {d.name}")
                break

            time.sleep(1)

    except Exception as e:
        d.status = Status.error
        log(f"[Aria2c] Exception during download: {e}")
        if emitter:
            emitter.status_changed.emit("error")

    finally:
        if emitter:
            emitter.log_updated.emit(f"[Aria2c] Done processing {d.name}")
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
    if config.proxy:
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
        "ffmpeg_location": ffmpeg_path,
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
        notify(f"File: {d.name} \nsaved at: {d.folder}", title=f"{APP_NAME} - Download completed")
        log(f"[yt-dlp] Finished and merged: {d.name}")

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
                        config.ffmpeg_actual_path,
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
                # d.status = Status.merging
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
                success = post_process_hls(d)
                if not success:
                    d.status = Status.error
                    break

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
    # from worker import Worker
    # import config

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
