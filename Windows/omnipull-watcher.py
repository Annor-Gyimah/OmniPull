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
import sys
import json
import time
import struct
import tempfile
import platform
from pathlib import Path

# Try importing fcntl only if available (Unix)
try:
    import fcntl  # type: ignore
except ImportError:
    fcntl = None

# Windows file locking helpers
try:
    import msvcrt  # type: ignore
except ImportError:
    msvcrt = None



def app_data_dir(APP_NAME='.OmniPull'):
    """App's own data dir for queues/logs."""
    if os.name == "nt":
        # %APPDATA%\OmniPull
        return Path.home() / "AppData" / "Roaming" / APP_NAME
    elif sys.platform == "darwin":
        # ~/Library/Application Support/OmniPull
        return Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        # Linux: $XDG_DATA_HOME/OmniPull or ~/.local/share/OmniPull
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
        return base / APP_NAME

BASE = app_data_dir()
BASE.mkdir(parents=True, exist_ok=True)

QUEUE_PATH  = BASE / ".omnipull_url_queue.json"
NDJSON_PATH = BASE / ".omnipull_url_queue.ndjson"
LATEST_PATH = BASE / ".omnipull_url_latest.json"
LOCK_PATH   = BASE / ".omnipull.lock"          # lock file for cross-process mutex (Windows-safe)


LOG_DIR  = BASE / "Logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "watcher.log"


MAX_MSG = 1_048_576
RETRIES = 8
SLEEP   = 0.08  # 80ms backoff base

def log(s: str):
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(s.rstrip() + "\n")
    except Exception:
        pass

def init_files():
    NDJSON_PATH.touch(exist_ok=True)
    if not LATEST_PATH.exists():
        LATEST_PATH.write_text("{}", encoding="utf-8")
    log(f"Paths:\n  NDJSON: {NDJSON_PATH}\n  LATEST: {LATEST_PATH}\n  LOCK: {LOCK_PATH}")

def read_exact(n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sys.stdin.buffer.read(n - len(buf))
        if not chunk:
            raise EOFError("stdin closed")
        buf.extend(chunk)
    return bytes(buf)

def read_message():
    raw_len = sys.stdin.buffer.read(4)
    if not raw_len:
        raise EOFError("no length")
    msg_len = struct.unpack('<I', raw_len)[0]
    if msg_len > MAX_MSG:
        raise ValueError("message too large")
    data = read_exact(msg_len)
    return json.loads(data.decode("utf-8"))

def send_response(obj: dict):
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_MSG:
        raw = b'{"status":"error","message":"too_large"}'
    sys.stdout.buffer.write(struct.pack("<I", len(raw)))
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()

# -------------------- locking primitives --------------------

class SimpleLock:
    """
    Cross-platform process mutex using:
      - Windows: a small lock file created with O_CREAT|O_EXCL (no msvcrt.locking on data files)
      - Unix: fcntl.flock on the lock file
    """
    def __init__(self, path: Path):
        self.path = path
        self.fd = None

    def acquire(self, retries=RETRIES, sleep=SLEEP):
        for attempt in range(retries):
            try:
                if os.name == "nt":
                    # Try to create exclusively; fail if exists
                    self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                    os.write(self.fd, b"1")
                    return True
                else:
                    # On Unix, open (create if needed), then flock
                    self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
                    if fcntl:
                        fcntl.flock(self.fd, fcntl.LOCK_EX)
                    return True
            except FileExistsError:
                # Another process holds the lock; back off
                time.sleep(sleep * (1.5 ** attempt))
            except PermissionError as e:
                # Sharing violation etc.; back off
                log(f"lock acquire permission error: {e!r}")
                time.sleep(sleep * (1.5 ** attempt))
            except Exception as e:
                log(f"lock acquire error: {e!r}")
                time.sleep(sleep * (1.5 ** attempt))
        return False

    def release(self):
        try:
            if self.fd is not None:
                if os.name != "nt" and fcntl:
                    try:
                        fcntl.flock(self.fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                os.close(self.fd)
                self.fd = None
            # On both platforms, remove the lock file (best-effort)
            try:
                os.remove(self.path)
            except Exception:
                pass
        except Exception as e:
            log(f"lock release error: {e!r}")

# -------------------- robust writers --------------------

def append_ndjson(item: dict):
    line = json.dumps(item, separators=(",", ":")) + "\n"
    lock = SimpleLock(LOCK_PATH)
    if not lock.acquire():
        raise PermissionError("could_not_acquire_lock")

    try:
        for attempt in range(RETRIES):
            try:
                with open(NDJSON_PATH, "a", encoding="utf-8", newline="\n") as f:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())
                return
            except PermissionError as e:
                # File in use by another process (e.g., AV or a watcher); retry
                log(f"append_ndjson permission error: {e!r} (attempt {attempt+1})")
                time.sleep(SLEEP * (1.5 ** attempt))
            except Exception as e:
                log(f"append_ndjson error: {e!r} (attempt {attempt+1})")
                time.sleep(SLEEP * (1.5 ** attempt))
        raise PermissionError("append_failed_after_retries")
    finally:
        lock.release()

def write_latest(item: dict):
    # Write to a temp file in BASE, then replace with retries (Windows can fail if target is open)
    tmp = None
    for attempt in range(RETRIES):
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, dir=str(BASE), encoding="utf-8") as t:
                tmp = t.name
                json.dump(item, t, separators=(",", ":"))
                t.flush()
                os.fsync(t.fileno())
            # Try atomic replace
            os.replace(tmp, LATEST_PATH)
            tmp = None
            return
        except PermissionError as e:
            log(f"write_latest permission error: {e!r} (attempt {attempt+1})")
            time.sleep(SLEEP * (1.5 ** attempt))
        except Exception as e:
            log(f"write_latest error: {e!r} (attempt {attempt+1})")
            time.sleep(SLEEP * (1.5 ** attempt))
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
    raise PermissionError("latest_replace_failed_after_retries")

# -------------------- main loop --------------------

def main():
    init_files()
    try:
        msg = read_message()
        url = str(msg.get("url", "")).strip()
        if not url:
            send_response({"status": "error", "message": "missing_url"})
            return

        item = {"url": url}

        append_ndjson(item)
        write_latest(item)

        log(f"Queued latest: {item}")
        send_response({"status": "queued"})
    except Exception as e:
        # Surface rich error detail to the extension
        err_msg = f"{e.__class__.__name__}: {e}"
        log(f"exception: {err_msg!s}")
        try:
            send_response({"status": "error", "message": err_msg})
        except Exception:
            pass

if __name__ == "__main__":
    main()
