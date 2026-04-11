


#####################################################################################
#    OmniPull – queue_runner.py
#
#    Fixes applied in this revision
#    ─────────────────────────────
#    1. Queue chain stalls after first item completes (curl/sparse engine)
#       Root cause: brain() for the curl/sparse path spawns daemon threads and
#       returns immediately.  DownloadWorker.run() now polls until d.status reaches
#       a terminal state before emitting finished/failed, so _on_item_finished fires
#       only after the real download is done and start_next() works correctly.
#
#    2. Effective concurrency = min(queue max_concurrent, global max_concurrent_downloads)
#       Previously only the queue-level cap was checked inside start_next(); the
#       global setting was only enforced in the curl-specific branch and only against
#       currently-downloading items inside this runner's own list.  Now the effective
#       slot limit is computed once and respected everywhere.
#
#    3. Download window shown reliably for every queued item
#       Root cause: _show_window was scheduled via QTimer.singleShot(0, …) AFTER
#       thread.start().  On fast machines the worker could emit finished before the
#       timer fired, causing _close_window to run first and then _show_window to
#       open a ghost window for an already-finished item.
#       Fix: _show_window is called synchronously, right before thread.start().
#####################################################################################

import os

from modules.config import Status
from modules.utils import log
from modules import config as _config

from ui.download_worker import DownloadWorker
from ui.download_window import DownloadProgressDialog
from PySide6.QtCore import QObject, QThread, Signal, Slot


class QueueRunner(QObject):
    # ── Public signals (consumed by QueueDialog / main window) ──────────────────
    queue_finished    = Signal(str)     # queue_id
    download_started  = Signal(object)  # DownloadItem
    download_finished = Signal(object)  # DownloadItem
    download_failed   = Signal(object)  # DownloadItem
    thread_created    = Signal(QThread)

    # ── Private marshalling signals ──────────────────────────────────────────────
    # worker.finished / worker.failed are emitted from background threads.
    # Connecting those directly to _on_item_finished/_on_item_failed would invoke
    # them on the worker thread, where QThread(self.parent()) creation fails
    # silently and the queue stalls.
    #
    # By connecting to these Signal objects Qt delivers them as QueuedConnections
    # automatically (because QueueRunner lives on the main thread), so the slots
    # always execute on the main thread.
    _item_finished = Signal(object)
    _item_failed   = Signal(object)

    def __init__(self, queue_id, queue_items, max_concurrent=1, parent=None):
        super().__init__(parent)
        self.queue_id       = queue_id
        self.queue_items    = list(queue_items)   # local copy; indices stay stable
        self.queue_max      = max(1, int(max_concurrent))   # queue-level limit
        self.index          = 0       # next position to consider
        self.active_count   = 0       # slots currently occupied by this runner
        self.paused         = False   # soft-kill flag set by stop_queue_downloads
        self.threads        = []
        self.worker_refs    = {}      # d.id → DownloadWorker
        self.thread_refs    = {}      # d.id → QThread
        self.main_window    = parent
        # IDs of items that were just paused by the user.  They are back in
        # Status.queued but must NOT be re-launched in the same start_next() call
        # that fired because their old workers/files are still winding down.
        # Each ID is removed from this set the next time start_next() is called
        # from a *different* completion event (or when the queue is restarted).
        self._just_paused_ids: set = set()

        self._item_finished.connect(self._on_item_finished)
        self._item_failed.connect(self._on_item_failed)

    # ── Effective concurrency cap ─────────────────────────────────────────────────
    @property
    def _effective_max(self) -> int:
        """
        The actual number of simultaneous downloads allowed for this queue.

        The queue has its own max_concurrent setting, but the user also has a
        global max_concurrent_downloads preference.  We honour whichever is
        more restrictive so that the global setting always acts as a ceiling.
        """
        global_max = int(getattr(_config, "max_concurrent_downloads", 4))
        return min(self.queue_max, global_max)

    # ─────────────────────────────────────────────────────────────────────────────
    def start(self):
        self.start_next()

    def start_next(self):
        """
        Fill all available concurrent slots with queued items.

        Called from start() and from _on_item_finished/_on_item_failed.
        Always runs on the main thread (guaranteed by the marshalling signals).
        """
        if self.paused:
            log(f"[QueueRunner] start_next() skipped — runner is paused.", log_level=2)
            return

        effective_max = self._effective_max

        log(
            f"[QueueRunner] start_next() index={self.index} "
            f"active={self.active_count}/{effective_max} "
            f"(queue_max={self.queue_max}, global_max={int(getattr(_config, 'max_concurrent_downloads', 4))})",
            log_level=2,
        )

        # On each call we clear the just-paused guard so that a subsequent
        # completion event (a different item finishing) can re-evaluate them.
        # We do NOT clear it before the scan below — it must still block the
        # item that was paused in the same event that triggered this call.
        paused_guard = set(self._just_paused_ids)
        self._just_paused_ids.clear()

        # Linear scan starting from self.index.  We use a local cursor so we
        # can reset self.index without losing our place for the outer while loop.
        scan_index = self.index

        while self.active_count < effective_max:

            # Advance past items that are not eligible to start:
            #   • not in Status.queued
            #   • already running (present in worker_refs)
            #   • just paused this tick (in paused_guard) — old workers still alive
            while scan_index < len(self.queue_items):
                candidate = self.queue_items[scan_index]
                if (candidate.status == Status.queued
                        and candidate.id not in self.worker_refs
                        and candidate.id not in paused_guard):
                    break
                scan_index += 1

            if scan_index >= len(self.queue_items):
                # No more eligible items in the list.
                # Emit queue_finished only when every slot has also drained.
                if self.active_count == 0:
                    log(f"[QueueRunner] Queue {self.queue_id} completed.", log_level=2)
                    self.queue_finished.emit(self.queue_id)
                return

            d = self.queue_items[scan_index]
            scan_index += 1   # advance cursor BEFORE launching to prevent double-start

            log(
                f"[QueueRunner] Starting '{d.name}' "
                f"(slot {self.active_count + 1}/{effective_max})",
                log_level=2,
            )

            self._refresh_urls_if_needed(d)
            self.download_started.emit(d)
            self._launch(d)

        # Persist cursor so the next call doesn't re-scan already-started items.
        self.index = scan_index

    def _launch(self, d):
        """
        Create QThread + DownloadWorker for one item and start it.

        Must run on the main thread (called from start_next which is always main).

        The progress window is opened HERE, synchronously, BEFORE thread.start().
        Previously it was scheduled via QTimer.singleShot(0, …) after start(),
        which created a race: on fast machines the worker emitted finished before
        the timer fired, _close_window ran first, and then _show_window opened a
        ghost window for an already-completed download.
        """
        thread = QThread(self.parent())
        worker = DownloadWorker(d)
        worker.moveToThread(thread)

        self.worker_refs[d.id] = worker
        self.thread_refs[d.id] = thread

        # Wire completion signals to private marshalling signals so the slots
        # always execute on the main thread via Qt's queued connection mechanism.
        worker.finished.connect(self._item_finished)
        worker.failed.connect(self._item_failed)

        thread.started.connect(worker.run)
        thread.finished.connect(
            lambda t=thread: self.threads.remove(t) if t in self.threads else None
        )
        thread.finished.connect(
            lambda name=d.name: log(
                f"[QueueRunner] Thread for '{name}' exited.", log_level=2
            )
        )

        # ── Stamp last_try_date and transition status ──
        # This is the earliest safe point to do this — the worker is about to run.
        from datetime import datetime
        d.last_try_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d.status = Status.downloading

        # ── Open the progress window BEFORE starting the thread ──
        # This guarantees the window exists and all signals are connected before
        # the worker begins emitting progress/status updates.
        self._show_window(d, worker)

        thread.start()
        self.active_count += 1
        self.threads.append(thread)
        self.thread_created.emit(thread)

    # ─────────────────────────────────────────────────────────────────────────────
    # Private slots — ALWAYS on the main thread via queued delivery
    # ─────────────────────────────────────────────────────────────────────────────

    @Slot(object)
    def _on_item_finished(self, d):
        """Called on main thread when a worker emits finished."""
        log(f"[QueueRunner] Finished: {d.name}", log_level=2)
        self._close_window(d)
        self.download_finished.emit(d)
        self.worker_refs.pop(d.id, None)
        self.thread_refs.pop(d.id, None)
        self.active_count = max(0, self.active_count - 1)
        self.start_next()   # fill the freed slot

    @Slot(object)
    def _on_item_failed(self, d):
        """Called on main thread when a worker emits failed (error, cancel, or paused)."""
        log(f"[QueueRunner] Failed/paused: {d.name}", log_level=2)
        self._close_window(d)
        self.download_failed.emit(d)
        self.worker_refs.pop(d.id, None)
        self.thread_refs.pop(d.id, None)
        self.active_count = max(0, self.active_count - 1)

        # If the whole queue was stopped (self.paused), don't advance.
        if self.paused:
            log(f"[QueueRunner] Runner paused — not advancing after '{d.name}'.", log_level=2)
            return

        if d.status == Status.queued:
            # The item was paused by the user — it is back in Status.queued.
            # We must NOT re-launch it immediately: its old pycurl workers are
            # still unwinding (curl error 42 callbacks in flight) and the sparse
            # file is still locked.  Add its ID to the just-paused guard so that
            # the start_next() call below skips it, then reset the scan to 0 so
            # the NEXT item in the queue (if any) is found.
            log(
                f"[QueueRunner] Item '{d.name}' paused → re-queued. "
                f"Guarding ID {d.id} from immediate re-launch; resetting scan index.",
                log_level=2,
            )
            self._just_paused_ids.add(d.id)
            self.index = 0

        self.start_next()   # fill the freed slot

    # Public aliases so any external code that connected to these still works
    def handle_finished(self, d):
        self._on_item_finished(d)

    def handle_failed(self, d):
        self._on_item_failed(d)

    # ─────────────────────────────────────────────────────────────────────────────

    def _show_window(self, d, worker):
        """Create and show a DownloadProgressDialog for a started item."""
        if not _config.show_download_window:
            return

        main_window = self.parent()
        if main_window is None:
            return
        if not hasattr(main_window, "download_windows"):
            main_window.download_windows = {}

        # Close any stale window for this item before opening a fresh one
        if d.id in main_window.download_windows:
            try:
                main_window.download_windows[d.id].close()
                main_window.download_windows[d.id].deleteLater()
            except Exception:
                pass

        win = DownloadProgressDialog(d)
        main_window.download_windows[d.id] = win

        # Connect all worker signals the window knows about
        worker.progress_changed.connect(win.on_progress_changed)
        worker.status_changed.connect(win.on_status_changed)
        if hasattr(worker, "progress_mode_changed") and hasattr(win, "on_progress_mode_changed"):
            worker.progress_mode_changed.connect(win.on_progress_mode_changed)
        if hasattr(worker, "log_updated") and hasattr(win, "on_log_updated"):
            worker.log_updated.connect(win.on_log_updated)

        win.show()
        log(f"[QueueRunner] Opened window for: {d.name}", log_level=2)

    def _close_window(self, d):
        """Close the progress window for a completed/failed item."""
        main_window = self.parent()
        if hasattr(main_window, "download_windows") and d.id in main_window.download_windows:
            try:
                win = main_window.download_windows.pop(d.id)
                win.close()
            except Exception as e:
                log(f"[QueueRunner] Close window error for {d.name}: {e}", log_level=2)

    # ─────────────────────────────────────────────────────────────────────────────

    def _refresh_urls_if_needed(self, d):
        """Refresh YouTube/streaming URLs before starting a queued download."""
        try:
            
            has_original = hasattr(d, 'original_url') and d.original_url
            is_youtube = has_original and (
                "youtube.com" in d.original_url
                or "googlevideo.com" in d.original_url
            )
            if not is_youtube:
                return

            eff_url = getattr(d, "eff_url", None) or d.url
            is_page_url = (
                "youtube.com/watch" in eff_url
                or "youtube.com/shorts" in eff_url
                or "youtu.be/" in eff_url
                or eff_url == d.original_url
            )
            needs_refresh = is_page_url
            if not needs_refresh and hasattr(self.main_window, '_youtube_url_expired'):
                needs_refresh = (
                    self.main_window._youtube_url_expired(eff_url)
                    or (
                        getattr(d, 'audio_url', None)
                        and self.main_window._youtube_url_expired(d.audio_url)
                    )
                )
            if not needs_refresh:
                return

            log(f"[QueueRunner] Refreshing URLs for: {d.name}", log_level=2)
            if not hasattr(self.main_window, 'get_video_info'):
                return

            original_format_id       = getattr(d, 'format_id', None)
            original_audio_format_id = getattr(d, 'audio_format_id', None)
            fresh_d = self.main_window.get_video_info(d.original_url or d.url)

            if original_format_id and hasattr(fresh_d, 'stream_list'):
                for stream in fresh_d.stream_list:
                    if stream.format_id == original_format_id:
                        fresh_d.selected_stream = stream
                        break

            for attr in [
                'url', 'eff_url', 'audio_url', 'audio_size', 'vid_info',
                'protocol', 'type', 'size', 'fragments', 'fragment_base_url',
                'audio_fragments', 'audio_fragment_base_url',
                'manifest_url', 'webpage_url',
            ]:
                if hasattr(fresh_d, attr):
                    setattr(d, attr, getattr(fresh_d, attr))

            # Fix 3F — sync title from fresh extraction when original was a video-ID stub
            if not getattr(d, "_title_resolved", False):
                fresh_title = getattr(fresh_d, "name", None)
                if fresh_title and fresh_title != d.name:
                    # Get extension from d.ext or use default
                    d.name = fresh_title
                    d._title_resolved = True
                    log(f"[QueueRunner] Title synced from refresh: {d.name}", log_level=2)
            
            else:
                log(f"[QueueRunner] Preserving pre-resolved title: {d.name}", log_level=2)

            if getattr(fresh_d, 'audio_url', None):
                base_name = os.path.splitext(d.name)[0]
                d.audio_file = os.path.join(d.temp_folder, f"{base_name}_audio")

            if original_format_id:
                d.format_id = original_format_id
            if original_audio_format_id:
                d.audio_format_id = original_audio_format_id

            if d.engine == "aria2c":
                for f in [
                    d.temp_file,
                    d.temp_file + '.aria2',
                    d.audio_file,
                    (d.audio_file + '.aria2' if getattr(d, 'audio_file', None) else None),
                ]:
                    if f and os.path.exists(f):
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                d.aria_gid = None

            if hasattr(self.main_window, 'settings_manager'):
                self.main_window.settings_manager.save_d_list(self.main_window.d_list)

        except Exception as e:
            log(f"[QueueRunner] Failed to refresh URLs for {d.name}: {e}", log_level=2)