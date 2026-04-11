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


import json
import os
import time
from threading import Lock
from pathlib import Path
from typing import Dict, List, Optional


class SegmentProgress:
    """Represents progress of a single segment."""
    def __init__(self, seg_num: int, start_byte: int, end_byte: int, size: int):
        self.seg_num = seg_num
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.size = size
        self.downloaded = 0
        self.completed = False
        # Tracks the highest byte-offset that has been confirmed flushed to disk.
        # The sidecar only persists up to this value so that a resume never seeks
        # past data that only existed in the OS write-back cache.
        self.last_flushed_bytes = 0
    
    def to_dict(self):
        return {
            'seg_num': self.seg_num,
            'start_byte': self.start_byte,
            'end_byte': self.end_byte,
            'size': self.size,
            'downloaded': self.downloaded,
            'completed': self.completed,
            # Persist the flushed watermark so resume uses a safe offset.
            'last_flushed_bytes': self.last_flushed_bytes,
        }
    
    @staticmethod
    def from_dict(d):
        sp = SegmentProgress(d['seg_num'], d['start_byte'], d['end_byte'], d['size'])
        sp.downloaded = d.get('downloaded', 0)
        sp.completed = d.get('completed', False)
        sp.last_flushed_bytes = d.get('last_flushed_bytes', 0)
        return sp


class ResumeTracker:
    """
    Tracks download progress in a .opdownload sidecar file.

    Design notes:
    - _save_to_disk() writes to a .tmp file then renames it atomically.
      This means a crash mid-write never produces a corrupted sidecar —
      the rename only happens after the full JSON is safely on disk.
    - update_segment() is throttled: it only flushes to disk every
      SAVE_INTERVAL seconds per segment, plus immediately on completion.
      This reduces disk writes from thousands-per-second to ~1 per 2s.
    - _lock protects the in-memory segment dict.  _save_to_disk() is only
      ever called while _lock is already held.

    Sidecar file format:
    {
        "version": 1,
        "total_size": 1073741824,
        "segments": [
            {
                "seg_num": 0,
                "start_byte": 0,
                "end_byte": 524999999,
                "size": 525000000,
                "downloaded": 123456789,
                "completed": false
            },
            ...
        ]
    }
    """

    # How often (seconds) to flush interim progress per segment.
    # Completion always flushes immediately regardless of this value.
    SAVE_INTERVAL = 2.0

    def __init__(self, temp_file_path: str):
        self.temp_file = temp_file_path
        self.sidecar_file = temp_file_path + ".opdownload"
        self._lock = Lock()
        self._segments: Dict[int, SegmentProgress] = {}
        self.version = 1
        self.total_size = 0

        # Per-segment timestamp of the last disk flush, used for throttling.
        # Keyed by seg_num.
        self._last_save_time: Dict[int, float] = {}

        self._load_from_disk()

    def __repr__(self):
        """Prevent ResumeTracker from being JSON serialised accidentally."""
        return f"<ResumeTracker {self.sidecar_file}>"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_from_disk(self):
        """Load progress from the sidecar file if it exists."""
        if not os.path.exists(self.sidecar_file):
            return
        try:
            with open(self.sidecar_file, 'r') as f:
                data = json.load(f)
            self.version = data.get('version', 1)
            self.total_size = data.get('total_size', 0)
            for seg_dict in data.get('segments', []):
                sp = SegmentProgress.from_dict(seg_dict)
                self._segments[sp.seg_num] = sp
        except Exception as e:
            # Corrupted sidecar (e.g. power loss mid-write).  Log it so the
            # we can see it happened, then start fresh so the download
            # can restart cleanly rather than silently producing a bad file.
            import logging
            logging.warning(
                f"[ResumeTracker] Corrupted sidecar '{self.sidecar_file}', "
                f"starting fresh: {e}"
            )
            self._segments.clear()

    def _save_to_disk(self) -> None:
        """Atomically persist progress to the sidecar file.

        Writes to <sidecar>.tmp first, then renames it over the real file.
        os.replace() is atomic on both Windows (NTFS) and POSIX, so a crash
        mid-write will never leave a half-written / corrupted sidecar — the
        previous good version stays in place until the new one is complete.

        The 'downloaded' value written to disk is min(downloaded,
        last_flushed_bytes) for in-progress segments.  This ensures that if
        we resume, we seek to an offset that is guaranteed to be on physical
        media, avoiding zero-holes from OS write-back cache that was never
        committed.  Completed segments always use the full downloaded count
        because the worker flushes + fsyncs before marking completion.

        IMPORTANT: must only be called while self._lock is held.
        """
        tmp_path = self.sidecar_file + ".tmp"
        try:
            segments_out = []
            for sp in self._segments.values():
                d = sp.to_dict()
                # For in-progress segments, clamp the persisted byte count to
                # the last confirmed-flushed watermark so a resume offset is
                # never ahead of what is physically on disk.
                if not sp.completed:
                    safe_downloaded = min(sp.downloaded, sp.last_flushed_bytes)
                    d['downloaded'] = safe_downloaded
                segments_out.append(d)

            data = {
                "version": self.version,
                "total_size": self.total_size,
                "segments": segments_out,
            }
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
            # Atomic swap: if this succeeds the reader always sees a valid file
            os.replace(tmp_path, self.sidecar_file)
        except Exception:
            # Sidecar loss is not fatal — download continues, resume just
            # won't know how far we got.  Clean up the tmp if it exists.
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init_segments(self, segments_list: List) -> None:
        """Initialise tracker with the segment list from DownloadItem.

        Preserves existing on-disk progress so that resuming a download
        does not throw away bytes already downloaded.
        """
        with self._lock:
            saved_progress = dict(self._segments)
            self._segments.clear()

            for seg in segments_list:
                seg_num = seg.num

                start, end = 0, 0
                if seg.range:
                    try:
                        if isinstance(seg.range, (tuple, list)) and len(seg.range) == 2:
                            start, end = seg.range[0], seg.range[1]
                        elif isinstance(seg.range, dict):
                            start = seg.range.get('start', 0)
                            end = seg.range.get('end', 0)
                        elif isinstance(seg.range, str):
                            parts = seg.range.split('-')
                            if len(parts) == 2:
                                start, end = int(parts[0]), int(parts[1])
                    except (ValueError, TypeError, AttributeError):
                        start, end = 0, 0

                size = seg.size or 0

                if seg_num in saved_progress:
                    # Resume: restore prior progress but refresh range/size
                    # in case the segment layout changed.
                    sp = saved_progress[seg_num]
                    sp.start_byte = start
                    sp.end_byte = end
                    sp.size = size
                else:
                    sp = SegmentProgress(seg_num, start, end, size)

                self._segments[seg_num] = sp

                if end > self.total_size:
                    self.total_size = end + 1

            self._save_to_disk()

    def update_segment(self, seg_num: int, downloaded: int,
        completed: bool = False) -> None:
        """Update progress for a segment.

        Disk writes are throttled to SAVE_INTERVAL seconds per segment to
        avoid thousands of JSON writes per second during active downloading.
        Completion always triggers an immediate flush so no progress is lost
        when a segment finishes.

        IMPORTANT: the value persisted to disk is min(downloaded, last_flushed_bytes)
        unless completed=True.  This prevents the sidecar from recording a resume
        offset that is ahead of what was actually written to disk, which would
        cause zero-holes on the next resume.
        """
        with self._lock:
            if seg_num not in self._segments:
                return

            sp = self._segments[seg_num]
            sp.downloaded = downloaded
            sp.completed = completed

            # On completion the caller has already flushed & fsync'd, so advance
            # the flushed watermark to the full downloaded count.
            if completed:
                sp.last_flushed_bytes = downloaded

            now = time.monotonic()
            last_save = self._last_save_time.get(seg_num, 0.0)

            if completed or (now - last_save) >= self.SAVE_INTERVAL:
                self._save_to_disk()
                self._last_save_time[seg_num] = now

    def mark_flushed(self, seg_num: int, flushed_bytes: int) -> None:
        """Record that *flushed_bytes* bytes for *seg_num* are confirmed on disk.

        Called by the worker immediately after a successful flush/fsync so the
        sidecar watermark can safely advance.  The next update_segment() call
        will persist min(downloaded, last_flushed_bytes) as the safe resume
        offset.
        """
        with self._lock:
            if seg_num not in self._segments:
                return
            sp = self._segments[seg_num]
            if flushed_bytes > sp.last_flushed_bytes:
                sp.last_flushed_bytes = flushed_bytes

    def force_save_segment(self, seg_num: int, downloaded: int,
                           completed: bool = False) -> None:
        """Like update_segment but always flushes to disk immediately.

        The caller guarantees that file buffers were flushed/fsync'd before
        calling, so last_flushed_bytes is aligned with downloaded.  This
        ensures _save_to_disk persists min(downloaded, last_flushed_bytes)
        == downloaded, giving the next resume session the correct offset.
        """
        with self._lock:
            if seg_num not in self._segments:
                return
            sp = self._segments[seg_num]
            sp.downloaded = downloaded
            sp.completed = completed
            sp.last_flushed_bytes = downloaded
            self._save_to_disk()
            self._last_save_time[seg_num] = time.monotonic()

    def get_segment_progress(self, seg_num: int) -> Optional[Dict]:
        """Return current progress for a segment, or None if not found."""
        with self._lock:
            if seg_num in self._segments:
                return self._segments[seg_num].to_dict()
            return None

    def get_all_progress(self) -> Dict:
        """Return progress for all segments."""
        with self._lock:
            return {
                "total_size": self.total_size,
                "segments": [sp.to_dict() for sp in self._segments.values()]
            }

    def calculate_total_downloaded(self) -> int:
        """Return total bytes downloaded across all segments."""
        with self._lock:
            return sum(sp.downloaded for sp in self._segments.values())

    def is_complete(self) -> bool:
        """Return True only when every segment is marked completed."""
        with self._lock:
            if not self._segments:
                return False
            return all(sp.completed for sp in self._segments.values())

    def cleanup(self) -> None:
        """Remove the sidecar file after a successful download."""
        try:
            if os.path.exists(self.sidecar_file):
                os.remove(self.sidecar_file)
            # Remove the tmp file too, just in case it was left behind
            tmp = self.sidecar_file + ".tmp"
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

    def restore_incomplete_state(self) -> Dict:
        """Return a dict of ranges that still need downloading.

        Format: {seg_num: (resume_start_byte, end_byte), ...}
        """
        with self._lock:
            resume_info = {}
            for seg_num, sp in self._segments.items():
                if sp.completed:
                    continue
                resume_start = sp.start_byte + sp.downloaded
                resume_end = sp.end_byte
                if resume_start <= resume_end:
                    resume_info[seg_num] = (resume_start, resume_end)
            return resume_info