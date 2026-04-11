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
import time
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from modules.utils import log


class BrowserQueueMonitor(QThread):
    """
    Background thread that monitors the browser extension queue file
    and signals when new downloads are detected
    """

    # Signal emitted when a new download URL is detected
    # Emits: (url: str, metadata: dict)
    download_detected = Signal(str, dict)

    def __init__(self):
        super().__init__()

        # Get queue file path based on platform
        self._queue_file = self._get_queue_file_path()

        # Track processed items to avoid duplicates
        self._processed_urls = set()

        # Control flags
        self._running = True
        self._paused = False

        # Check interval (seconds)
        self._check_interval = 2  # Check every 2 seconds

        log(f"[BrowserQueueMonitor] Initialized with queue file: {self._queue_file}")

    def _get_queue_file_path(self) -> Path:
        """Get the queue file path based on platform"""
        import sys
        import os

        home = Path.home()

        if sys.platform == 'win32':
            # Windows: %APPDATA%/OmniPull/download_queue.json
            appdata = os.getenv('APPDATA', home)
            omnipull_dir = Path(appdata) / 'OmniPull'
        else:
            # macOS/Linux: ~/.omnipull/download_queue.json
            omnipull_dir = home / '.omnipull'

        # Ensure directory exists
        omnipull_dir.mkdir(parents=True, exist_ok=True)

        return omnipull_dir / 'download_queue.json'

    def run(self):
        """Main monitoring loop"""
        log("[BrowserQueueMonitor] Started monitoring")

        while self._running:
            try:
                if not self._paused:
                    self._check_queue()

                # Sleep for the check interval
                time.sleep(self._check_interval)

            except Exception as e:
                log(f"[BrowserQueueMonitor] Error in monitoring loop: {e}", log_level='3')
                time.sleep(self._check_interval)

        log("[BrowserQueueMonitor] Stopped monitoring")

    def _check_queue(self):
        """Check the queue file for new downloads"""
        try:
            # Check if queue file exists
            if not self._queue_file.exists():
                return

            # Read queue file
            with open(self._queue_file, 'r', encoding='utf-8') as f:
                queue = json.load(f)

            if not isinstance(queue, list):
                log(f"[BrowserQueueMonitor] Queue file has invalid format", log_level='2')
                return

            # Process pending items
            found_new = False

            for item in queue:
                if not isinstance(item, dict):
                    continue

                url = item.get('url')
                status = item.get('status', 'pending')

                if not url:
                    continue

                # Only process pending items that we haven't processed yet
                if status == 'pending' and url not in self._processed_urls:
                    found_new = True

                    # Extract metadata
                    metadata = item.get('metadata', {})

                    # Add some useful info
                    metadata['added_from_browser'] = True
                    metadata['added_at'] = item.get('added_at', '')

                    log(f"[BrowserQueueMonitor] New download detected: {url}")

                    # Emit signal with URL and metadata
                    self.download_detected.emit(url, metadata)

                    # Mark as processed in memory
                    self._processed_urls.add(url)

            # Clear the queue file completely after processing
            # This allows the same URL to be downloaded again immediately
            if found_new:
                self._update_queue_file([])  # Write empty queue
                # Also clear the in-memory processed cache
                self._processed_urls.clear()
                log(f"[BrowserQueueMonitor] Cleared queue file and processed cache after processing")

        except json.JSONDecodeError as e:
            log(f"[BrowserQueueMonitor] Invalid JSON in queue file: {e}", log_level='3')
        except Exception as e:
            log(f"[BrowserQueueMonitor] Error checking queue: {e}", log_level='3')

    def _update_queue_file(self, queue):
        """Update the queue file with processed status"""
        try:
            # Write to temporary file first (atomic write)
            temp_file = self._queue_file.with_suffix('.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(self._queue_file)

            log(f"[BrowserQueueMonitor] Updated queue file")

        except Exception as e:
            log(f"[BrowserQueueMonitor] Error updating queue file: {e}", log_level='3')

    def pause(self):
        """Pause monitoring"""
        self._paused = True
        log("[BrowserQueueMonitor] Paused")

    def resume(self):
        """Resume monitoring"""
        self._paused = False
        log("[BrowserQueueMonitor] Resumed")

    def stop(self):
        """Stop monitoring and exit thread"""
        log("[BrowserQueueMonitor] Stopping...")
        self._running = False

        # Wait for thread to finish (with timeout)
        if not self.wait(5000):  # 5 second timeout
            log("[BrowserQueueMonitor] Thread did not stop gracefully, terminating", log_level='2')
            self.terminate()

    def clear_processed_cache(self):
        """Clear the cache of processed URLs"""
        self._processed_urls.clear()
        log("[BrowserQueueMonitor] Cleared processed URLs cache")

    def remove_from_processed_cache(self, url: str):
        """Remove a specific URL from the processed cache, allowing it to be re-downloaded"""
        if url in self._processed_urls:
            self._processed_urls.remove(url)
            log(f"[BrowserQueueMonitor] Removed URL from processed cache: {url}")

    def set_check_interval(self, seconds: int):
        """Set the check interval in seconds"""
        if seconds < 1:
            seconds = 1
        self._check_interval = seconds
        log(f"[BrowserQueueMonitor] Check interval set to {seconds} seconds")

    @property
    def is_paused(self) -> bool:
        """Check if monitoring is paused"""
        return self._paused

    @property
    def queue_file(self) -> Path:
        """Get the queue file path"""
        return self._queue_file
