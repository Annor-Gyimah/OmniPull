
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
import socket


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

    # Pass emitter explicitly
    Thread(target=file_manager, daemon=True, args=(d, keep_segments, emitter)).start()
    Thread(target=thread_manager, daemon=True, args=(d, emitter)).start()

    while True:
        time.sleep(0.1)

        if d.status == Status.completed:
            config.main_window_q.put(('restore_window', ''))
            notify(f"File: {d.name} \nsaved at: {d.folder}", title=f'{APP_NAME} - Download completed')
            break
        elif d.status == Status.cancelled:
            break
        elif d.status == Status.error:
            break

    if d.callback and d.status == Status.completed:
        globals()[d.callback]()

    log(f'brain {d.num}: quitting')


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
                error, output = merge_video_audio(d.temp_file, d.audio_file, output_file, d)
                if not error:
                    rename_file(output_file, d.target_file)
                    d.delete_tempfiles()
                else:
                    d.status = Status.error
                    break

            # Handle "normal" single-stream downloads
            if not ('m3u8' in d.protocol or d.type == 'dash'):
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
