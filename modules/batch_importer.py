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


from __future__ import annotations

import os
import re
from threading import Event
from typing import List
from urllib.parse import urlparse, unquote


import omnipull_url_processor

from PySide6.QtCore import QThread, Signal

from modules import config
from modules.downloaditem import DownloadItem
from modules.utils import log, size_format


# ─────────────────────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────────────────────

# Characters that are never legal inside a URL but frequently appear when
# a user pastes a comma-separated list, a spreadsheet export, etc.
_INVALID_URL_CHARS = re.compile(r'[,;\t|"\'<>{}\\^`\[\]]')

# A URL must start with a scheme we can handle.
_VALID_SCHEMES = frozenset({"http", "https", "ftp", "ftps", "magnet"})

# Minimum sanity: must contain at least one dot (or be a magnet link)
_HAS_DOT_OR_MAGNET = re.compile(r'(\.|magnet:)')


def _check_url_line(line: str, line_no: int) -> str | None:
    """
    Validate a single non-comment, non-empty line from the import file.

    Returns an error string if the line is invalid, None if it is fine.
    """
    # ── multiple URLs on one line (common copy/paste mistake) ──────────────
    # Detect patterns like "http://a.com, http://b.com" or space-separated
    # pairs that both look like URLs.
    parts_comma  = [p.strip() for p in line.split(",") if p.strip()]
    parts_space  = line.split()

    if len(parts_comma) > 1:
        # All comma-separated parts that look url-ish → user used commas as separator
        url_like = [p for p in parts_comma if p.lower().startswith(("http", "ftp", "magnet"))]
        if len(url_like) > 1:
            return (
                f"Line {line_no}: multiple URLs on one line separated by commas — "
                f"each URL must be on its own line."
            )

    if len(parts_space) > 1:
        url_like = [p for p in parts_space if p.lower().startswith(("http", "ftp", "magnet"))]
        if len(url_like) > 1:
            return (
                f"Line {line_no}: multiple URLs on one line separated by spaces — "
                f"each URL must be on its own line."
            )

    # ── invalid characters ──────────────────────────────────────────────────
    m = _INVALID_URL_CHARS.search(line)
    if m:
        char = m.group(0)
        return (
            f"Line {line_no}: invalid character {char!r} in URL — "
            f"remove any commas, quotes, or brackets between links."
        )

    # ── scheme check ────────────────────────────────────────────────────────
    try:
        parsed = urlparse(line)
        scheme = (parsed.scheme or "").lower()
    except Exception:
        return f"Line {line_no}: cannot parse URL — {line[:80]!r}"

    if not scheme:
        return (
            f"Line {line_no}: missing URL scheme (expected http://, https://, etc.) — "
            f"got: {line[:80]!r}"
        )

    if scheme not in _VALID_SCHEMES:
        return (
            f"Line {line_no}: unsupported scheme {scheme!r} — "
            f"only http, https, ftp, ftps, and magnet links are supported."
        )

    # ── basic structure ─────────────────────────────────────────────────────
    if scheme != "magnet" and not parsed.netloc:
        return (
            f"Line {line_no}: URL has no host/domain — "
            f"got: {line[:80]!r}"
        )

    if not _HAS_DOT_OR_MAGNET.search(line):
        return (
            f"Line {line_no}: URL looks malformed (no dot in host) — "
            f"got: {line[:80]!r}"
        )

    return None  # valid


# ─────────────────────────────────────────────────────────────────────────────
# Worker  (pure computation – zero UI calls)
# ─────────────────────────────────────────────────────────────────────────────

class BatchImportWorker(QThread):
    """
    Validates, then resolves name + size metadata for every URL in a text file.

    Signals (all delivered on the main thread via Qt's queued connection):
        item_ready(DownloadItem)   – one per resolved URL
        progress_text(str)         – e.g. "Processing 3 / 12 …"
        finished_ok()              – all done
        failed(str)                – fatal error (validation failure or I/O error)
    """

    item_ready    = Signal(object)   # DownloadItem
    progress_text = Signal(str)
    finished_ok   = Signal()
    failed        = Signal(str)

    FAST_TIMEOUT_SEC  = 10
    YTDLP_TIMEOUT_SEC = 30

    _MEDIA_EXTS = frozenset(
        "mp4 mkv avi mov webm m4v flv ts mp3 aac flac ogg opus wav m4a".split()
    )

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path  = file_path
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    # ── private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _read_raw_lines(path: str) -> List[tuple[int, str]]:
        """
        Return (1-based line number, stripped content) for every non-blank,
        non-comment line in the file.
        """
        result: List[tuple[int, str]] = []
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line_no, raw in enumerate(fh, 1):
                stripped = raw.strip()
                if stripped and not stripped.startswith("#"):
                    result.append((line_no, stripped))
        return result

    @staticmethod
    def _validate_lines(lines: List[tuple[int, str]]) -> List[str]:
        """
        Validate every line and return a list of human-readable error strings.
        An empty list means the file is clean.
        """
        errors: List[str] = []
        for line_no, content in lines:
            err = _check_url_line(content, line_no)
            if err:
                errors.append(err)
        return errors

    @staticmethod
    def _is_youtube(url: str) -> bool:
        try:
            return any(
                urlparse(url).netloc.lower().endswith(d)
                for d in ("youtube.com", "youtu.be", "music.youtube.com")
            )
        except Exception:
            return False

    @staticmethod
    def _is_media(url: str) -> bool:
        ext = os.path.splitext(url.split("?")[0])[1].lower().lstrip(".")
        return ext in BatchImportWorker._MEDIA_EXTS

    def _rust(self, url: str, item: DownloadItem) -> bool:
        """Try the fast Rust processor. Returns True on success."""
        try:
            r = omnipull_url_processor.process_url(url, self.FAST_TIMEOUT_SEC)
            if r.is_supported:
                if r.real_url:
                    item.url = r.real_url
                item.name       = r.filename or item.name
                item.size       = r.size or 0
                item.total_size = item.size
                if r.content_type and "html" not in r.content_type:
                    item.type = r.content_type
                return True
        except Exception as exc:
            log(f"[BatchImport] Rust error {url[:50]}: {exc}", log_level=2)
        return False

    

    def _ytdlp(self, url: str, item: DownloadItem) -> bool:
        """
        Flat-extract title + size via yt-dlp.
        On success the item's name is set to the video title **with** the
        expected output extension appended so the queue always shows a
        complete filename (e.g. "My Video.mp4" instead of "My Video").
        Returns True if a title was obtained.
        """
        try:
            from yt_dlp import YoutubeDL
            opts = {
                "quiet": True, "no_warnings": True,
                "skip_download": True, "extract_flat": "in_playlist",
                "socket_timeout": self.YTDLP_TIMEOUT_SEC,
            }
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                return False

            if info.get("entries"):
                # Playlist stub — use playlist title, size unknown
                title = info.get("title") or item.name
                item.size       = 0
                item.total_size = 0
            else:
                title = info.get("title") or item.name
                sz = info.get("filesize") or info.get("filesize_approx") or 0
                item.size       = sz
                item.total_size = sz

            # ── FIXED: Store name WITH proper extension ──
            merge_ext = (
                config.ytdlp_config.get("merge_output_format", "mp4")
                if hasattr(config, "ytdlp_config")
                else "mp4"
            )
            
            # Clean the title first
            from modules.utils import validate_file_name
            clean_title = validate_file_name(title) if title else item.name
            
            # Only add extension if not already present
            if clean_title and not os.path.splitext(clean_title)[1]:
                item.name = f"{clean_title}.{merge_ext}"
            else:
                item.name = clean_title or item.name
            
            # NEW: Store the extension explicitly
            item.ext = merge_ext

            item.engine = "yt-dlp"
            item._title_resolved = True
            return bool(item.name)

        except Exception as exc:
            log(f"[BatchImport] yt-dlp error {url[:50]}: {exc}", log_level=2)
        return False

    @staticmethod
    def _ext(url: str) -> str:
        return os.path.splitext(url.split("?")[0])[1].lower().lstrip(".")

    # ── thread entry ─────────────────────────────────────────────────────────

    def run(self):
        # ── Step 1: read raw lines ────────────────────────────────────────
        try:
            raw_lines = self._read_raw_lines(self._file_path)
        except Exception as exc:
            self.failed.emit(f"Cannot open file:\n{exc}")
            return

        if not raw_lines:
            self.failed.emit(
                "The selected file contains no URLs.\n"
                "Add one URL per line (lines starting with # are treated as comments)."
            )
            return

        # ── Step 2: validate every line before doing any network work ─────
        errors = self._validate_lines(raw_lines)
        if errors:
            # Cap the report at the first 10 problems to avoid huge dialogs.
            shown   = errors[:10]
            trailer = f"\n…and {len(errors) - 10} more issue(s)." if len(errors) > 10 else ""
            self.failed.emit(
                f"The file contains {len(errors)} formatting error(s) "
                f"and was not imported:\n\n"
                + "\n".join(f"• {e}" for e in shown)
                + trailer
                + "\n\nFix the issues and try again.\n"
                  "Rules: one URL per line, no commas between links, "
                  "each URL must start with http://, https://, ftp://, or magnet:."
            )
            return

        # ── Step 3: resolve metadata for each valid URL ───────────────────
        urls   = [content for _, content in raw_lines]
        total  = len(urls)
        log(f"[BatchImport] Validation passed — processing {total} URL(s)", log_level=1)

        

        for idx, url in enumerate(urls, 1):
            if self._stop_event.is_set():
                break

            self.progress_text.emit(f"Processing {idx} / {total} …")

            item            = DownloadItem()
            item.url        = url
            item.name       = os.path.basename(url.split("?")[0]) or f"link_{idx}"
            item.name       = unquote(item.name)   # decode %20 → space, %5B → [ etc.
            item.size       = 0
            item.total_size = 0
            item.engine     = config.download_engine
            


            if self._is_youtube(url):
                log(f"[BatchImport] yt-dlp [{idx}/{total}]: {url[:60]}", log_level=1)
                self._ytdlp(url, item)
                item.engine = "yt-dlp"
                # Don't override ext if _ytdlp already set it
                if not item.ext:
                    item.ext = "mp4"  # fallback
            else:
                log(f"[BatchImport] Rust [{idx}/{total}]: {url[:60]}", log_level=1)
                ok = self._rust(url, item)
                if not ok and self._is_media(url):
                    log(
                        f"[BatchImport] Rust rejected media URL, trying yt-dlp [{idx}/{total}]",
                        log_level=2,
                    )
                    self._ytdlp(url, item)
                    # Don't override ext if _ytdlp already set it
                    if not item.ext:
                        item.ext = "mp4"  # fallback

            # For non-YouTube items the ext comes from the URL path; for YouTube
            # items _ytdlp() has already embedded the extension in item.name so
            # _ext() will return "" and the fallback "mp4" is irrelevant here.
            # if not getattr(item, "_title_resolved", False):
            #     item.ext = self._ext(item.url) or item.ext or "mp4"

            # Ensure eff_url is set — segments use this as their download URL
            if not item.eff_url:
                item.eff_url = item.url

            # Thread-safe delivery to main thread
            self.item_ready.emit(item)

        log("[BatchImport] Done", log_level=1)
        self.finished_ok.emit()