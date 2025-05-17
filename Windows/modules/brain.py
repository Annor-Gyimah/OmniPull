
import io
import os
import time
from threading import Thread
from modules.video import merge_video_audio, is_download_complete, youtube_dl_downloader, unzip_ffmpeg, pre_process_hls, post_process_hls  # unzip_ffmpeg required here for ffmpeg callback
from modules import config
from modules.config import Status, active_downloads, APP_NAME
from modules.utils import (log, size_format, popup, notify, delete_folder, delete_file, rename_file, load_json, save_json)
from modules.worker import Worker
from modules.downloaditem import Segment
from modules.aria2c_manager import aria2c_manager

import socket
import subprocess
import shlex
import re


def has_internet_connection(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        log("No internet connection:", ex)
        return False
    
# brain.py
signal_emitter = None

def set_signal_emitter(emitter):
    global signal_emitter
    signal_emitter = emitter

# brain.py
def brain(d=None, emitter=None):
    log(f"brain() started for: {d.name} | current status: {d.status}")
    # Check which engine to use
    ################# YET TO ADD TO LINUX ############
    if getattr(config, "download_engine", "yt-dlp").lower() == "aria2": 
    
        # If the URL is static, use aria2c
        if d.type not in ("youtube", "dash", "hls", "m3u8", "streaming"):
            run_aria2c_download(d, emitter=None)
            return
        else:
            log(f"Falling back to yt-dlp for: {d.name}")

    d.status = Status.downloading
    log('-' * 100)
    log(f'start downloading file: "{d.name}", size: {size_format(d.size)}, to: {d.folder}')

    d.load_progress_info()

    if 'm3u8' in d.protocol:
        keep_segments = True
        success = pre_process_hls(d)
        if not success:
            d.status = Status.error
            return
    else:
        keep_segments = False

    # Start managers
    Thread(target=file_manager, daemon=True, args=(d, keep_segments, emitter)).start()
    Thread(target=thread_manager, daemon=True, args=(d, emitter)).start()


    start_time = time.time()
    max_timeout = 180  # 2 minutes timeout


    # Start monitoring
    while True:
        #time.sleep(1)

        time.sleep(0.1)

        if time.time() - start_time > max_timeout and d.progress == 0:
            d.status = Status.error
            log(f"Timeout reached for {d.name}. Marking as failed.")
            if emitter:
                emitter.status_changed.emit("error")     # ✅ tell DownloadWindow
                emitter.failed.emit(d)                   # ✅ tell DownloadWorker
            break

        # ✅ Cancellation Check
        if d.status == Status.cancelled:
            log(f"brain() cancelled manually for: {d.name}")
            if d.in_queue:
                d.status = Status.queued
            break

        # ✅ Completion Check
        if d.status == Status.completed:
            config.main_window_q.put(('restore_window', ''))
            notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
            break

        # ✅ Error Check
        if d.status == Status.error:
            log(f"brain() error detected for: {d.name}")
            break

    


    if d.callback and d.status == Status.completed:
        globals()[d.callback]()

    # if emitter and d.status in (Status.error, Status.failed, Status.cancelled):
    #     emitter.status_changed.emit("error")
    #     emitter.failed.emit(d)


    log(f'brain {d.num}: quitting')


################# YET TO ADD TO LINUX ############
def run_aria2c_download(d, emitter=None):
    log(f"[Aria2c] Starting: {d.name}")
    d.status = Status.downloading
    d._progress = 0
    d.remaining_parts = 1
    d.last_known_progress = 0

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

        if not d.aria_gid:
            added = aria2.add_uris([d.url], options={"dir": d.folder, 
                "out": d.name, 
                "pause": "false",
                "file-allocation": config.aria2c_config["file_allocation"], 
                "max-connection-per-server": config.aria2c_config["max_connections"],
                                                     
            })
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

            percent = int(download.progress)
            d._progress = percent
            d.last_known_progress = percent

            d._total_size = int(download.total_length)
            d._downloaded = int(download.completed_length)
            d._speed = int(download.download_speed)
            d.remaining_time = download.eta if download.eta != -1 else 0

            if emitter:
                emitter.progress_changed.emit(percent)
                emitter.log_updated.emit(f"⬇ {size_format(d.speed, '/s')} | Done: {size_format(d.downloaded)} / {size_format(d.total_size)}")

            if download.is_complete:
                d.status = Status.completed
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
                error, output = merge_video_audio(d.temp_file, d.audio_file, output_file, d)
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
