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
import pycurl
import certifi
from modules import config
from modules.utils import log
from modules.config import Status, USER_AGENT

class Worker:
    def __init__(self, tag=0, d=None):
        self.tag = tag
        self.d = d
        self.q = d.q
        self.seg = None
        self.resume_range = None
        
        # Initialize as standard variable to avoid property setter errors
        self.current_filesize = 0

        # writing data parameters
        self.file = None
        self.mode = 'wb'  # file opening mode default to new write binary

        self.downloaded = 0
        self.speed_limit = None
        
        # Stats throttling
        self.last_stats_update = 0
        self.stats_update_interval = 0.1

        # pycurl
        self.c = pycurl.Curl()

        self.current_speed = 0
        self.last_bytes_check = 0
        self.last_time_check = time.time()
    

    def calculate_speed(self):
        """Calculates instantaneous speed (Bytes/sec)"""
        now = time.time()
        duration = now - self.last_time_check
        
        if duration >= 0.3:  # Update speed every second
            bytes_since_last = self.downloaded - self.last_bytes_check
            self.current_speed = bytes_since_last / duration
            
            # Reset for next window
            self.last_bytes_check = self.downloaded
            self.last_time_check = now
        
        return self.current_speed

    def get_ttc(self):
        """Returns Time-To-Completion in seconds"""
        speed = self.calculate_speed()
        if speed <= 0:
            return 999999  # Effectively infinite
            
        remaining = (self.seg.size or 0) - self.current_filesize
        return remaining / speed

    def set_options(self):
        agent = USER_AGENT
        self.c.setopt(pycurl.USERAGENT, agent)

        if not self.seg.url:
            raise ValueError(f"[Worker] Invalid URL in segment: {self.seg.name}")

        self.c.setopt(pycurl.URL, self.seg.url)
        
        # Log URL being downloaded
        log(f"[Worker {self.tag}] downloading URL: {self.seg.url}, range: {self.resume_range or self.seg.range}", log_level=3)

        range_ = self.resume_range or self.seg.range
        if range_:
            self.c.setopt(pycurl.RANGE, range_)

        # --- HEADER INJECTION FOR YOUTUBE/403s ---
        headers = [
            "Accept: */*",
            "Connection: keep-alive",
            "Sec-Fetch-Dest: video",
            "Sec-Fetch-Mode: no-cors",
            "Sec-Fetch-Site: cross-site"
        ]
        # Inject Referrer if available
        if hasattr(self.d, 'referrer') and self.d.referrer:
            self.c.setopt(pycurl.REFERER, self.d.referrer)

        self.c.setopt(pycurl.HTTPHEADER, headers)
        # -----------------------------------------

        # PROXY SETTINGS
        if config.proxy:
            self.c.setopt(pycurl.PROXY, config.proxy)
            if config.proxy_type:
                proxy_type_map = {
                    "http": pycurl.PROXYTYPE_HTTP,
                    "socks4": pycurl.PROXYTYPE_SOCKS4,
                    "socks5": pycurl.PROXYTYPE_SOCKS5,
                    "https": pycurl.PROXYTYPE_HTTP,
                }
                self.c.setopt(pycurl.PROXYTYPE, proxy_type_map.get(config.proxy_type.lower(), pycurl.PROXYTYPE_HTTP))

            if getattr(config, "proxy_user", None) and getattr(config, "proxy_pass", None):
                self.c.setopt(pycurl.PROXYUSERPWD, f"{config.proxy_user}:{config.proxy_pass}")

        self.c.setopt(pycurl.FOLLOWLOCATION, 1)
        self.c.setopt(pycurl.MAXREDIRS, 10)
        self.c.setopt(pycurl.NOSIGNAL, 1)
        self.c.setopt(pycurl.NOPROGRESS, 0)
        self.c.setopt(pycurl.CAINFO, certifi.where())
        self.c.setopt(pycurl.MAX_RECV_SPEED_LARGE, self.speed_limit)
        self.c.setopt(pycurl.CONNECTTIMEOUT, 30)
        self.c.setopt(pycurl.LOW_SPEED_LIMIT, 1)
        self.c.setopt(pycurl.LOW_SPEED_TIME, 60)
        self.c.setopt(pycurl.VERBOSE, 0)
        self.c.setopt(pycurl.HEADEROPT, 0)

        # callbacks
        self.c.setopt(pycurl.HEADERFUNCTION, self.header_callback)
        self.c.setopt(pycurl.WRITEFUNCTION, self.write)
        self.c.setopt(pycurl.XFERINFOFUNCTION, self.progress)

    def header_callback(self, header_line):
        header_line = header_line.decode('iso-8859-1')
        if ':' in header_line:
            name, value = header_line.split(':', 1)
            name = name.strip().lower()
            value = value.strip()
            if name == 'content-length':
                try:
                    content_len = int(value)
                    # Only set seg.size if not already set (first request).
                    # On resume with Range requests, the Content-Length reflects
                    # the size of that range, not the total segment size.
                    # We must preserve the original seg.size.
                    if (getattr(self.seg, 'size', 0) or 0) == 0:
                        self.seg.size = content_len
                except ValueError:
                    pass

    def write(self, data):
        """write to file"""
        # Determine current position before writing so we can avoid
        # writing past the declared segment size (which would cause
        # the part file to exceed the expected size).
        try:
            before_pos = self.file.tell()
        except Exception:
            before_pos = getattr(self, 'current_filesize', 0)

        chunk_len = len(data)

        # SAFE SIZE CHECK: Only write up to remaining bytes when we know seg size
        seg_size = getattr(self.seg, 'size', 0) or 0
        if seg_size > 0:
            remaining = seg_size - before_pos
            if remaining <= 0:
                return -1  # nothing to write, abort
            if chunk_len > remaining:
                # write only the needed portion to reach the exact segment size
                to_write = data[:remaining]
                self.file.write(to_write)
                written = remaining
                # update counters
                self.downloaded += written
                try:
                    self.d.downloaded += written
                except Exception:
                    pass
                self.current_filesize = before_pos + written

                # Update stats throttled
                current_time = time.time()
                if current_time - self.last_stats_update >= self.stats_update_interval:
                    try:
                        stats = getattr(self.d, "connection_stats", None)
                        if isinstance(stats, list) and 0 <= self.tag < len(stats):
                            stats[self.tag]["downloaded"] += written
                            stats[self.tag]["info"] = "Receiving data..."
                        self.last_stats_update = current_time
                    except Exception:
                        pass

                return -1  # abort after writing exact expected bytes

        # default: write whole chunk
        self.file.write(data)
        written = chunk_len
        self.downloaded += written
        try:
            self.d.downloaded += written
        except Exception:
            pass

        self.current_filesize = self.file.tell()

        # Update stats throttled
        current_time = time.time()
        if current_time - self.last_stats_update >= self.stats_update_interval:
            try:
                stats = getattr(self.d, "connection_stats", None)
                if isinstance(stats, list) and 0 <= self.tag < len(stats):
                    stats[self.tag]["downloaded"] += written
                    stats[self.tag]["info"] = "Receiving data..."
                self.last_stats_update = current_time
            except Exception:
                pass

    def progress(self, *_):
        """it receives progress from curl and can be used as a kill switch
        Returning a non-zero value from this callback will cause curl to abort the transfer
        """

        # check termination by user
        if self.d.status != Status.downloading:
            return -1  # abort


    def __del__(self):
        try:
            self.c.close()
        except Exception:
            pass

    def reuse(self, seg=None, speed_limit=0):
        self.seg = seg
        self.speed_limit = speed_limit
        self.downloaded = 0

    def verify(self):
        """verify if the downloaded file matches expectations"""
        if not os.path.exists(self.seg.name):
            log(f"[Worker {self.tag}] Verify FAILED: File doesn't exist: {self.seg.name}", log_level=2)
            return False

        disk_size = os.path.getsize(self.seg.name)
        seg_size = getattr(self.seg, 'size', 0) or 0

        # If strict size known, verify it
        if seg_size > 0:
            if disk_size != seg_size:
                log(f"[Worker {self.tag}] Verify FAILED: Size mismatch! Expected {seg_size}, got {disk_size}", log_level=2)
                return False
            log(f"[Worker {self.tag}] Verify PASSED: File size matches {disk_size} bytes", log_level=3)
        else:
            log(f"[Worker {self.tag}] Verify: Size unknown (HLS), allowing file with {disk_size} bytes", log_level=3)
        # If size unknown (HLS), allow it
        return True

    def report_completed(self):
        """mark segment as downloaded successfully"""
        self.d.live_connections -= 1
        if self.seg:
            # Only set downloaded=True; file_manager will set completed=True after merging
            self.seg.downloaded = True
            # self.seg.completed = True
            self.seg.in_progress = False
            
            try:
                stats = getattr(self.d, "connection_stats", None)
                if isinstance(stats, list) and 0 <= self.tag < len(stats):
                    stats[self.tag]["info"] = "Complete"
                    stats[self.tag]["speed"] = ""
            except Exception:
                pass
            log(f"[Worker {self.tag}] ✓ COMPLETED: downloaded segment {os.path.basename(self.seg.name)} ({self.current_filesize} bytes)", log_level=1)

    def report_not_completed(self):
        """report that the segment is not completed"""
        self.d.live_connections -= 1
        if self.seg:
            self.seg.in_progress = False
            
            seg_size = getattr(self.seg, 'size', 0) or 0
            remaining = 0
            if seg_size > 0:
                remaining = seg_size - self.current_filesize

            log(f'worker {self.tag} did not complete {self.seg.name} downloaded {self.current_filesize} target size: {seg_size} remaining: {remaining}', 
                log_level=2)
            
            try:
                stats = getattr(self.d, "connection_stats", None)
                if isinstance(stats, list) and 0 <= self.tag < len(stats):
                    stats[self.tag]["info"] = "Error"
            except Exception:
                pass

    def run(self):
        if self.seg.downloaded:
            return

        # 1. RESUME LOGIC (Before set_options)
        self.mode = 'wb'
        self.resume_range = None
        self.current_filesize = 0
        
        if os.path.exists(self.seg.name):
            try:
                current_size = os.path.getsize(self.seg.name)
                seg_size = getattr(self.seg, 'size', 0) or 0
                
                # If we have data, try to resume
                if current_size > 0:
                    if seg_size > 0 and current_size >= seg_size:
                        self.report_completed()
                        return
                    
                    # Extract start and end bytes from the segment's range
                    # Range format: "start-end" (e.g., "0-459005232")
                    start_byte = 0
                    end_byte = ""
                    if self.seg.range:
                        try:
                            parts = self.seg.range.split('-')
                            if len(parts) >= 1:
                                try:
                                    start_byte = int(parts[0])
                                except (ValueError, TypeError):
                                    start_byte = 0
                                    log(f"[Worker {self.tag}] Warning: Could not parse start byte from range '{self.seg.range}'", log_level=2)
                            if len(parts) > 1:
                                end_byte = parts[1]
                        except Exception as e:
                            log(f"[Worker {self.tag}] Error parsing range '{self.seg.range}': {e}", log_level=2)
                    
                    # Calculate resume range: from current position to end byte
                    # Resume position = start_byte + current_size (absolute position in file)
                    resume_start = start_byte + current_size
                    self.resume_range = f"{resume_start}-{end_byte}"
                    
                    self.mode = 'ab'
                    self.downloaded = current_size
                    log(f"[Worker {self.tag}] Resuming segment {self.seg.num}: file has {current_size} bytes, resuming from {resume_start}, range: {self.resume_range}", log_level=3)
            except Exception as e:
                log(f"[Worker {self.tag}] Exception during resume logic for {self.seg.name}: {e} (will truncate and restart)", log_level=2)
                import traceback
                traceback.print_exc()
                # On exception, we intentionally stay in 'wb' mode (truncate) rather than silently fail
                # This ensures we don't get corrupted partial files
                self.mode = 'wb'

        self.set_options()

        target_directory = os.path.dirname(self.seg.name)
        if not os.path.isdir(target_directory):
            os.makedirs(target_directory, exist_ok=True)

        
        # 2. NETWORK RETRY LOOP
        max_retries = 5
        retries = 0
        
        while retries < max_retries:
            t_start = time.perf_counter()
            try:

                with open(self.seg.name, self.mode) as self.file:
                    self.c.perform()
                
                t_end = time.perf_counter()
                log(f"[Benchmark] Worker {self.tag} | Engine: PYTHON | Time: {(t_end-t_start):.3f}s", log_level=1)
                break 

            except Exception as e:
                retries += 1
                log(f"[Worker {self.tag}] Error: {e}. Retrying {retries}...", log_level=2)
                time.sleep(1 * retries)
                self.mode = 'ab' 
                continue

            

        # 3. VERIFY & REPORT
        if self.verify():
            self.report_completed()
        else:
            self.report_not_completed()