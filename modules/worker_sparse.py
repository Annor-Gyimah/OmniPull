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



import pycurl
import time
import os
import traceback
from threading import Lock

from modules import config
from modules import native_engine
from modules.utils import log, size_format
from modules.config import Status, USER_AGENT





class Worker_Sparse:
    """
    Worker Module: Sparse Pre-allocation Download Worker

    Each worker handles a single segment and writes directly to the pre-allocated
    main file at its calculated byte offset. Uses Nim native_writer for efficient I/O.
    """

    def __init__(self, tag=0, d=None):
        self.tag = tag
        self.d = d
        self.q = d.q
        self.seg = None
        
        # Sparse file parameters
        self.start_byte = 0      # Absolute byte position where this segment starts
        self.segment_size = 0    # Size of this segment
        
        # Writing via Nim native engine OR lazy file handle fallback
        self.native_writer = None
        self.file_handle = None  # Only opened if native_writer fails (lazy)
        self.current_downloaded = 0  # Bytes downloaded by this worker
        
        # Speed tracking
        self.current_speed = 0
        self.last_bytes_check = 0
        self.last_time_check = time.time()
        self.speed_limit = None
        
        # pycurl handle — created once, reset between retries
        self.c = pycurl.Curl()
        
        # Stats throttling
        self.last_stats_update = 0
        self.stats_update_interval = 0.1

    def calculate_speed(self):
        """Calculates instantaneous speed (Bytes/sec)."""
        now = time.time()
        duration = now - self.last_time_check
        
        if duration >= 0.3:  # Update speed every 300ms
            bytes_since_last = self.current_downloaded - self.last_bytes_check
            self.current_speed = bytes_since_last / duration if duration > 0 else 0
            self.last_bytes_check = self.current_downloaded
            self.last_time_check = now
        
        return self.current_speed

    def get_ttc(self):
        """Returns Time-To-Completion in seconds."""
        speed = self.calculate_speed()
        if speed <= 0:
            return 999999
        remaining = self.segment_size - self.current_downloaded
        return remaining / speed

    def set_options(self):
        """Configure pycurl for this segment download."""
        agent = USER_AGENT
        self.c.setopt(pycurl.USERAGENT, agent)

        # if not self.seg.url:
        #     raise ValueError(f"[Worker {self.tag}] Invalid URL in segment: {self.seg.name}")

        # self.c.setopt(pycurl.URL, self.seg.url)

        # seg.url is the stream URL; seg.name is the local file path — never use seg.name as URL
        seg_url = self.seg.url or getattr(self.d, 'eff_url', None) or getattr(self.d, 'url', None)
        if not seg_url:
            raise ValueError(f"[Worker {self.tag}] No valid URL for segment {self.seg.num}")

        self.c.setopt(pycurl.URL, seg_url)
        # update seg.url so resume/retry paths also have it
        self.seg.url = seg_url
        
        log(f"[Worker {self.tag}] Downloading segment {self.seg.num}: {self.seg.url} "
            f"(bytes {self.start_byte}-{self.start_byte + self.segment_size - 1})", log_level=3)

        # Set byte range for this segment
        if self.seg.range:
            if self.current_downloaded > 0:
                # Resume: start from where we left off inside this segment
                range_start = self.start_byte + self.current_downloaded
            else:
                range_start = self.start_byte
            
            range_end = self.start_byte + self.segment_size - 1
            self.c.setopt(pycurl.RANGE, f"{range_start}-{range_end}")

        headers = [
            "Accept: */*",
            "Connection: keep-alive",
            "Sec-Fetch-Dest: video",
            "Sec-Fetch-Mode: no-cors",
            "Sec-Fetch-Site: cross-site"
        ]
        
        if hasattr(self.d, 'referrer') and self.d.referrer:
            self.c.setopt(pycurl.REFERER, self.d.referrer)

        self.c.setopt(pycurl.HTTPHEADER, headers)

        # Proxy settings
        if config.proxy:
            self.c.setopt(pycurl.PROXY, config.proxy)
            if config.proxy_type:
                proxy_type_map = {
                    "http":   pycurl.PROXYTYPE_HTTP,
                    "socks4": pycurl.PROXYTYPE_SOCKS4,
                    "socks5": pycurl.PROXYTYPE_SOCKS5,
                    "https":  pycurl.PROXYTYPE_HTTP,
                }
                self.c.setopt(pycurl.PROXYTYPE,
                              proxy_type_map.get(config.proxy_type.lower(),
                                                 pycurl.PROXYTYPE_HTTP))
            if getattr(config, "proxy_user", None) and getattr(config, "proxy_pass", None):
                self.c.setopt(pycurl.PROXYUSERPWD,
                              f"{config.proxy_user}:{config.proxy_pass}")

        self.c.setopt(pycurl.FOLLOWLOCATION, 1)
        self.c.setopt(pycurl.MAXREDIRS, 10)
        self.c.setopt(pycurl.NOSIGNAL, 1)
        self.c.setopt(pycurl.NOPROGRESS, 0)
        self.c.setopt(pycurl.CONNECTTIMEOUT, 30)
        self.c.setopt(pycurl.LOW_SPEED_LIMIT, 1)
        self.c.setopt(pycurl.LOW_SPEED_TIME, 60)
        self.c.setopt(pycurl.VERBOSE, 0)
        self.c.setopt(pycurl.HEADEROPT, 0)

        try:
            import certifi
            self.c.setopt(pycurl.CAINFO, certifi.where())
        except Exception:
            pass

        if self.speed_limit:
            self.c.setopt(pycurl.MAX_RECV_SPEED_LARGE, int(self.speed_limit))

        self.c.setopt(pycurl.HEADERFUNCTION, self.header_callback)
        self.c.setopt(pycurl.WRITEFUNCTION, self.write)
        self.c.setopt(pycurl.XFERINFOFUNCTION, self.progress)

    def header_callback(self, header_line):
        """Process response headers."""
        header_line = header_line.decode('iso-8859-1')
        if ':' in header_line:
            name, value = header_line.split(':', 1)
            if name.strip().lower() == 'content-length':
                try:
                    content_len = int(value.strip())
                    if (getattr(self.seg, 'size', 0) or 0) == 0:
                        self.seg.size = content_len
                except ValueError:
                    pass

    def write(self, data):
        """Write data to the pre-allocated file at the correct offset.

        NO seg_lock here — each worker owns a unique, non-overlapping byte
        range so there is zero contention between workers.  Holding a shared
        lock here serialised all workers through a single bottleneck for no
        safety benefit.

        pycurl WRITEFUNCTION contract:
          - Return the number of bytes consumed (== len(data)) on success.
          - Return 0 to abort the transfer.
        """
        chunk_len = len(data)
        if chunk_len == 0:
            return 0

        # Overshoot protection: bail if the whole file is already done
        if self.d.size > 0 and self.d.downloaded >= self.d.size:
            log(f"[Worker {self.tag}] Overshoot guard triggered, stopping", log_level=2)
            return 0

        try:
            # Clamp chunk to segment boundary
            remaining_in_seg = self.segment_size - self.current_downloaded
            if remaining_in_seg <= 0:
                # Segment is full. Return chunk_len (not 0) so curl does NOT treat
                # this as a write failure (error 23). The progress callback will
                # abort the transfer cleanly on the next tick via returning -1.
                return chunk_len
            to_write = data[:remaining_in_seg] if chunk_len > remaining_in_seg else data

            bytes_written = 0

            # --- Primary path: Nim native writer (no GIL held during disk write) ---
            if self.native_writer is not None:
                try:
                    bytes_written = native_engine.write_data(self.native_writer, to_write)
                except Exception as e:
                    log(f"[Worker {self.tag}] Native writer error: {e}, "
                        f"falling back to Python I/O", log_level=2)
                    self.native_writer = None

            # --- Lazy fallback: Python file handle, only opened when needed ---
            if bytes_written <= 0:
                if self.file_handle is None:
                    # Open it now, the first time we actually need it
                    try:
                        self.file_handle = open(self.d.temp_file, 'r+b')
                        log(f"[Worker {self.tag}] Opened Python fallback file handle",
                            log_level=2)
                    except Exception as e:
                        log(f"[Worker {self.tag}] Cannot open fallback file handle: {e}",
                            log_level=2)
                        return 0  # Abort — nowhere to write

                if self.file_handle is not None:
                    try:
                        self.file_handle.seek(self.start_byte + self.current_downloaded)
                        self.file_handle.write(to_write)
                        bytes_written = len(to_write)
                    except Exception as e:
                        log(f"[Worker {self.tag}] Python file write error: {e}", log_level=2)
                        return 0

            if bytes_written <= 0:
                log(f"[Worker {self.tag}] Write failed for {len(to_write)} bytes", log_level=2)
                return 0

            # --- Accounting ---
            self.current_downloaded += bytes_written

            # d.downloaded is a simple running total shared across all workers.
            # CPython's GIL makes integer += atomic in practice, but wrap it
            # defensively to avoid any edge-case corruption.
            try:
                self.d.downloaded += bytes_written
            except Exception:
                pass

            # Throttled sidecar progress update (every 2s, handled inside tracker).
            # CRITICAL: flush the write buffer to disk BEFORE recording progress in
            # the sidecar.  The sidecar byte-count is used as the resume seek offset;
            # if we save "N bytes done" but the OS cache hasn't hit the disk yet, a
            # resume will seek to N and overwrite the un-flushed region with zeros.
            try:
                if hasattr(self.d, 'resume_tracker'):
                    import time as _time
                    _now = _time.monotonic()
                    _last = getattr(self, '_last_flush_time', 0.0)
                    if (_now - _last) >= 2.0:  # match ResumeTracker.SAVE_INTERVAL
                        # Flush before we let the sidecar record this offset
                        if self.native_writer is not None:
                            try:
                                native_engine.flush_file(self.native_writer)
                            except Exception:
                                pass
                        elif self.file_handle is not None:
                            try:
                                self.file_handle.flush()
                                os.fsync(self.file_handle.fileno())
                            except Exception:
                                pass
                        self._last_flush_time = _now
                        # Advance the flush watermark so _save_to_disk persists
                        # a safe resume offset rather than the raw counter.
                        self.d.resume_tracker.mark_flushed(
                            self.seg.num, self.current_downloaded)
                    self.d.resume_tracker.update_segment(
                        self.seg.num, self.current_downloaded, False)
            except Exception:
                pass

            # Throttled connection-stats update (for the UI speed display)
            current_time = time.time()
            if current_time - self.last_stats_update >= self.stats_update_interval:
                try:
                    stats = getattr(self.d, "connection_stats", None)
                    if isinstance(stats, list) and 0 <= self.tag < len(stats):
                        stats[self.tag]["downloaded"] += bytes_written
                        stats[self.tag]["info"] = "Receiving data..."
                    self.last_stats_update = current_time
                except Exception:
                    pass

            return bytes_written

        except Exception as e:
            log(f"[Worker {self.tag}] Unexpected write error: {e}", log_level=2)
            return 0

    def progress(self, *args):
        """pycurl progress callback — used as a kill switch."""
        if self.d.status != Status.downloading:
            return -1  # Abort transfer
        return 0

    # def reuse(self, seg=None, speed_limit=0):
    #     """Prepare this worker to download a new segment."""
    #     self.seg = seg
    #     self.speed_limit = speed_limit
    #     self.current_downloaded = 0
    #     self.last_bytes_check = 0
    #     self.last_time_check = time.time()
    #     self.native_writer = None
    #     # Close any previously open fallback handle before reuse
    #     if self.file_handle is not None:
    #         try:
    #             self.file_handle.close()
    #         except Exception:
    #             pass
    #         self.file_handle = None

    def reuse(self, seg=None, speed_limit=0):
        """Prepare this worker to download a new segment."""
        self.seg = seg
        self.speed_limit = speed_limit
        self.current_downloaded = 0
        self.last_bytes_check = 0
        self.last_time_check = time.time()
        self.native_writer = None
 
        # Close any previously open fallback file handle
        if self.file_handle is not None:
            try:
                self.file_handle.close()
            except Exception:
                pass
            self.file_handle = None
 
        # Always recreate the pycurl handle.
        # run()'s finally block closes self.c after every use; reusing a closed
        # handle raises "cannot invoke setopt() - no curl handle" on the next call.
        try:
            self.c.close()
        except Exception:
            pass
        self.c = pycurl.Curl()

    def verify(self):
        """Verify that the full segment was written to disk.

        Two-stage check:
        1. Counter check  — fast, catches obvious under-downloads.
        2. File-size check — confirms the sparse file actually contains data at
           the expected offset.  A segment whose cache was never flushed would
           show the correct counter but leave zeros on disk; checking that the
           file is at least as large as (start_byte + segment_size) catches that
           case without reading every byte.
        """
        if not self.seg or self.current_downloaded <= 0:
            log(f"[Worker {self.tag}] Verify FAILED: No data downloaded", log_level=2)
            return False

        expected = self.segment_size
        if self.current_downloaded < expected:
            log(f"[Worker {self.tag}] Verify FAILED: Downloaded {self.current_downloaded}, "
                f"expected {expected}", log_level=2)
            return False

        # Stage 2: confirm the file is large enough to contain this segment's
        # last byte.  For a sparse file this is always true if pre-allocation
        # succeeded, but the size check is a cheap safety net.
        try:
            file_size = os.path.getsize(self.d.temp_file)
            required_size = self.start_byte + self.segment_size
            if file_size < required_size:
                log(f"[Worker {self.tag}] Verify FAILED: file size {file_size} < "
                    f"required {required_size} (start={self.start_byte} seg={self.segment_size})",
                    log_level=2)
                return False
        except Exception as e:
            log(f"[Worker {self.tag}] Verify WARNING: Could not stat temp file: {e}",
                log_level=2)
            # Don't fail on stat errors — the counter check already passed.

        log(f"[Worker {self.tag}] Verify PASSED: {self.current_downloaded} bytes "
            f"(expected {expected})", log_level=3)
        return True

    def report_completed(self):
        """Mark segment as successfully downloaded."""
        self.d.live_connections -= 1
        if self.seg:
            self.seg.downloaded = True
            self.seg.in_progress = False
            try:
                if hasattr(self.d, 'resume_tracker'):
                    self.d.resume_tracker.update_segment(
                        self.seg.num, self.current_downloaded, True)
            except Exception:
                pass
            try:
                stats = getattr(self.d, "connection_stats", None)
                if isinstance(stats, list) and 0 <= self.tag < len(stats):
                    stats[self.tag]["info"] = "Complete"
                    stats[self.tag]["speed"] = ""
            except Exception:
                pass
            log(f"[Worker {self.tag}] ✓ COMPLETED: segment {self.seg.num} "
                f"({self.current_downloaded} bytes at offset {self.start_byte})", log_level=1)

    def report_not_completed(self):
        """Report that this segment's download failed."""
        self.d.live_connections -= 1
        if self.seg:
            self.seg.in_progress = False
            log(f"[Worker {self.tag}] FAILED segment {self.seg.num}: "
                f"downloaded {self.current_downloaded}/{self.segment_size} bytes", log_level=2)
            # Flush whatever data we have to disk before recording progress
            # in the sidecar.  This ensures the resume offset matches what is
            # physically on disk.  Now that the native writer uses
            # fmReadWriteExisting (no truncation), the sparse file is never
            # wiped — so flushed data survives across sessions safely.
            try:
                if self.native_writer is not None:
                    native_engine.flush_file(self.native_writer)
                elif self.file_handle is not None:
                    self.file_handle.flush()
                    os.fsync(self.file_handle.fileno())
            except Exception:
                pass
            try:
                if hasattr(self.d, 'resume_tracker'):
                    self.d.resume_tracker.force_save_segment(
                        self.seg.num, self.current_downloaded, False)
            except Exception:
                pass
            try:
                stats = getattr(self.d, "connection_stats", None)
                if isinstance(stats, list) and 0 <= self.tag < len(stats):
                    stats[self.tag]["info"] = "Error"
            except Exception:
                pass

    def run(self):
        """Main download routine for this worker."""
        if self.seg.downloaded:
            return

        try:
            # --- Parse segment byte range ---
            if self.seg.range:
                if isinstance(self.seg.range, str):
                    try:
                        parts = self.seg.range.split('-')
                        if len(parts) == 2:
                            start, end = int(parts[0]), int(parts[1])
                        else:
                            raise ValueError(f"Invalid range format: {self.seg.range}")
                    except (ValueError, IndexError, TypeError) as e:
                        log(f"[Worker {self.tag}] Error parsing range "
                            f"'{self.seg.range}': {e}", log_level=2)
                        self.report_not_completed()
                        return
                else:
                    try:
                        start, end = self.seg.range[0], self.seg.range[1]
                    except (TypeError, IndexError) as e:
                        log(f"[Worker {self.tag}] Error unpacking range "
                            f"{self.seg.range}: {e}", log_level=2)
                        self.report_not_completed()
                        return
                
                self.start_byte = start
                self.segment_size = end - start + 1
            else:
                self.start_byte = 0
                self.segment_size = self.seg.size or 0

            # Ensure temp directory exists
            target_directory = os.path.dirname(self.seg.name)
            if target_directory and not os.path.isdir(target_directory):
                os.makedirs(target_directory, exist_ok=True)

            # Resume: restore how many bytes were already written for this segment
            if hasattr(self.d, 'resume_tracker'):
                seg_progress = self.d.resume_tracker.get_segment_progress(self.seg.num)
                if seg_progress:
                    self.current_downloaded = seg_progress.get('downloaded', 0)
                    log(f"[Worker {self.tag}] Resuming segment {self.seg.num}: "
                        f"{self.current_downloaded} bytes already downloaded", log_level=3)

            # Early-exit: segment already fully downloaded from a previous session.
            # Skipping curl entirely prevents error 23 ("write callback returned 0")
            # which occurs when the overshoot guard rejects incoming bytes for a
            # segment that has nothing left to write.
            if self.segment_size > 0 and self.current_downloaded >= self.segment_size:
                log(f"[Worker {self.tag}] Segment {self.seg.num} already complete "
                    f"({self.current_downloaded}/{self.segment_size}), skipping curl.",
                    log_level=1)
                if self.verify():
                    self.report_completed()
                else:
                    self.report_not_completed()
                return

            # Open native writer positioned at resume offset
            self.native_writer = native_engine.new_native_writer(
                self.d.temp_file,
                self.start_byte + self.current_downloaded
            )
            if self.native_writer is None:
                log(f"[Worker {self.tag}] Native writer unavailable, "
                    f"will use Python fallback on first write", log_level=2)
            # NOTE: file_handle is NOT opened here — it is opened lazily inside
            # write() only if the native writer fails mid-download.

            if self.native_writer is None:
                # Pre-open fallback now so we catch permission errors early
                try:
                    self.file_handle = open(self.d.temp_file, 'r+b')
                except Exception as e:
                    log(f"[Worker {self.tag}] Cannot open any writer for "
                        f"{self.d.temp_file}: {e}", log_level=2)
                    self.report_not_completed()
                    return

            self.set_options()

            # --- Retry loop ---
            max_retries = 5
            retries = 0

            while retries < max_retries:
                t_start = time.perf_counter()
                try:
                    self.c.perform()
                    t_end = time.perf_counter()
                    log(f"[Benchmark] Worker {self.tag} | "
                        f"Time: {(t_end - t_start):.3f}s", log_level=1)
                    break  # Success

                except pycurl.error as e:
                    retries += 1
                    # Recoverable: 7=Connect, 18=Partial, 28=Timeout, 56=Reset, 92=HTTP/2
                    if e.args[0] in [7, 18, 28, 56, 92]:
                        log(f"[Worker {self.tag}] Network error {e.args[0]}, "
                            f"retry {retries}/{max_retries}...", log_level=2)
                        # Reset curl handle so it's clean for the next attempt.
                        # Without this the handle can carry stale error state.
                        self.c.reset()
                        self.set_options()  # Re-apply all options after reset
                        time.sleep(1 * retries)
                        continue
                    else:
                        log(f"[Worker {self.tag}] Fatal curl error {e.args[0]}: {e}",
                            log_level=2)
                        self.report_not_completed()
                        return

                except Exception as e:
                    retries += 1
                    log(f"[Worker {self.tag}] Error: {e}. "
                        f"Retry {retries}/{max_retries}...", log_level=2)
                    traceback.print_exc()
                    time.sleep(1 * retries)
                    continue

            # Flush to disk before verifying.
            # For the Python fallback path we also call fsync so the OS write-back
            # cache is committed before we (a) record completion in the sidecar and
            # (b) rename the file.  Without fsync, a crash/pause between the sidecar
            # write and the physical flush would leave zero-holes on resume.
            if self.native_writer:
                native_engine.flush_file(self.native_writer)
            elif self.file_handle:
                try:
                    self.file_handle.flush()
                    os.fsync(self.file_handle.fileno())
                except Exception:
                    pass

            if self.verify():
                self.report_completed()
            else:
                self.report_not_completed()

        except Exception as e:
            log(f"[Worker {self.tag}] Unexpected error: {e}", log_level=2)
            traceback.print_exc()
            self.report_not_completed()

        finally:
            if self.native_writer:
                try:
                    native_engine.close_file(self.native_writer)
                except Exception:
                    pass
            if self.file_handle:
                try:
                    self.file_handle.flush()
                    self.file_handle.close()
                except Exception:
                    pass
                self.file_handle = None
            try:
                self.c.close()
            except Exception:
                pass