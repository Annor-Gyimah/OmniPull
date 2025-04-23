
import io
import os
import time
from threading import Thread
from .video import merge_video_audio, is_download_complete, youtube_dl_downloader, unzip_ffmpeg, pre_process_hls, post_process_hls  # unzip_ffmpeg required here for ffmpeg callback
from . import config
from .config import Status, active_downloads, APP_NAME
from .utils import (log, size_format, popup, notify, delete_folder, delete_file, rename_file, load_json, save_json)
from .worker import Worker
from .downloaditem import Segment
import socket


def has_internet_connection(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        log("No internet connection:", ex)
        return False


def brain(d=None, downloader=None):
    """main brain for a single download, it controls thread manger, file manager, and get data from workers
    and communicate with download window Gui, Main frame gui"""

    q = d.q

    # Check internet connection before attempting download
    # if not has_internet_connection():
    #     log(f"No internet — cannot download {d.name}")
    #     d.status = Status.failed
    #     return


    # in case of re-downloading a completed file will reset segment flags
    if d.status == Status.completed:
        d.reset_segments()
        d.downloaded = 0

    



    # set status
    # if d.status == Status.downloading:
    #     log('another brain thread may be running')
    #     return
    # else:
    #     d.status = Status.downloading
    # Set status explicitly at the start of brain
    log(f'brain() started for: {d.name} | current status: {d.status}')
    d.status = Status.downloading


    # # add item index to active download set
    # active_downloads.add(d.id)

    log('-' * 100)
    log(f'start downloading file: "{d.name}", size: {size_format(d.size)}, to: {d.folder}')

    # load previous saved progress info
    d.load_progress_info()

    # experimental m3u8 protocols
    if 'm3u8' in d.protocol:  # todo: use better way to identify HLS streams
        keep_segments = True  # don't delete segments after completed, it will be post-processed by ffmpeg
        success = pre_process_hls(d)
        if not success:
            d.status = Status.error
            return
    else:
        keep_segments = False

    # run file manager in a separate thread
    Thread(target=file_manager, daemon=True, args=(d, keep_segments)).start()

    # run thread manager in a separate thread
    Thread(target=thread_manager, daemon=True, args=(d,)).start()

    while True:
        time.sleep(0.1)  # a sleep time to make the program responsive

        if d.status == Status.completed:
            config.main_window_q.put(('restore_window', ''))
            # os notification popup
            notification = f"File: {d.name} \nsaved at: {d.folder}"
            notify(notification, title=f'{APP_NAME} - Download completed')
            log(f'File: "{d.name}", completed.')
            break
        elif d.status == Status.cancelled:
            log(f'brain {d.num}: Cancelled download')
            break
        elif d.status == Status.error:
            log(f'brain {d.num}: download error')
            break

    # todo: should find a better way to handle callback.
    # callback, a method or func "name" to call if download completed, it is stored as a string to be able to save it
    # on disk with other downloaditem parameters
    if d.callback and d.status == Status.completed:
        # d.callback()
        globals()[d.callback]()

    # ✅ Now it's safe to notify the queue dialog
    if hasattr(config, "queue_dialog") and config.queue_dialog:
        config.queue_dialog.on_queue_item_finished(d)

    # report quitting
    log(f'brain {d.num}: quitting')


def thread_manager(d):
    q = d.q

    # create worker/connection list
    workers = [Worker(tag=i, d=d) for i in range(config.max_connections)]

    free_workers = [i for i in range(config.max_connections)]
    free_workers.reverse()
    busy_workers = []
    live_threads = []  # hold reference to live threads

    # job_list
    job_list = [seg for seg in d.segments if not seg.downloaded]
    # print('thread manager job list:', job_list)

    # reverse job_list to process segments in proper order use pop()
    job_list.reverse()

    while True:
        time.sleep(0.1)  # a sleep time to while loop to make the app responsive

        # getting jobs which might be returned from workers as failed
        for _ in range(q.jobs.qsize()):
            job = q.jobs.get()
            job_list.append(job)
            # print('thread managaer jobs q:', job)

        # speed limit
        allowable_connections = min(config.max_connections, d.remaining_parts)
        if allowable_connections:
            try:
                speed_limit_int = int(config.speed_limit)
            except (ValueError, TypeError):
                speed_limit_int = 0  # fallback to no limit if invalid

            worker_sl = speed_limit_int * 1024 // int(allowable_connections) if allowable_connections else 0

        else:
            worker_sl = 0

        # reuse a free worker to handle a job from job_list
        if free_workers and job_list and d.status == Status.downloading:
            for _ in free_workers[:]:
                try:
                    worker_num, seg = free_workers.pop(), job_list.pop()  # get available tag # get a new job
                    busy_workers.append(worker_num)  # add number to busy workers

                    # create new threads
                    worker = workers[worker_num]
                    worker.reuse(seg=seg, speed_limit=worker_sl)
                    t = Thread(target=worker.run, daemon=True, name=str(worker_num))
                    live_threads.append(t)
                    t.start()
                except:
                    break

        # update d param
        d.live_connections = len(busy_workers)
        d.remaining_parts = len(busy_workers) + len(job_list) + q.jobs.qsize()

        # Monitor active threads and add the offline to a free_workers
        for t in live_threads:
            if not t.is_alive():
                worker_num = int(t.name)
                live_threads.remove(t)
                busy_workers.remove(worker_num)
                free_workers.append(worker_num)

        # change status
        if d.status != Status.downloading:
            # print('--------------thread manager cancelled-----------------')
            break

        # done downloading
        if not busy_workers and not job_list and not q.jobs.qsize():
            # print('--------------thread manager done----------------------')
            break

    log(f'thread_manager {d.num}: quitting')


def file_manager(d, keep_segments=False):

    while True:
        time.sleep(0.1)

        job_list = [seg for seg in d.segments if not seg.completed]
        # print(job_list)

        for seg in job_list:
            # process segments in order

            if seg.completed:  # skip completed segment
                continue

            if not seg.downloaded:  # if the first non completed segments is not downloaded will exit for loop
                break

            # append downloaded segment to temp file, mark as completed, then delete it.
            try:
                if seg.merge:
                    with open(seg.tempfile, 'ab') as trgt_file:
                        with open(seg.name, 'rb') as src_file:
                            trgt_file.write(src_file.read())

                seg.completed = True
                log('>> completed segment: ',  os.path.basename(seg.name))

                if not keep_segments:
                    delete_file(seg.name)

            except Exception as e:
                log('failed to merge segment', seg.name, ' - ', e)

        # check if all segments already merged
        if not job_list:

            # handle HLS streams
            if 'm3u8' in d.protocol:
                log('handling hls videos')
                # Set status to merging
                d.status = Status.merging_audio  # todo: should be renamed to merging instead of merging_audio

                success = post_process_hls(d)
                if not success:
                    log('file_manager()>  post_process_hls() failed, file:', d.target_file)
                    d.status = Status.error
                    break

            # handle dash video
            if d.type == 'dash':
                log('handling dash videos')
                # merge audio and video
                output_file = d.target_file.replace(' ', '_')  # remove spaces from target file

                if not is_download_complete(d):
                    log(f"Skipping merge: {d.name} is not fully downloaded.")
                    return


                # set status to merge
                d.status = Status.merging_audio
                error, output = merge_video_audio(d.temp_file, d.audio_file, output_file, d)

                if not error:
                    log('done merging video and audio for: ', d.target_file)

                    rename_file(output_file, d.target_file)

                    # delete temp files
                    d.delete_tempfiles()

                else:  # error merging
                    msg = f'failed to merge audio for file: {d.target_file}'
                    popup(msg, title='merge error')
                    d.status = Status.error
                    break

            else:
                rename_file(d.temp_file, d.target_file)
                delete_folder(d.temp_folder)

            # at this point all done successfully
            d.status = Status.completed
            # print('---------file manager done merging segments---------')
            break

        # change status
        if d.status != Status.downloading:
            # print('--------------file manager cancelled-----------------')
            break

    # save progress info for future resuming
    if d.status != Status.completed:
        d.save_progress_info()

    # Report quitting
    log(f'file_manager {d.num}: quitting')
