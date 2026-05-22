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
import requests
from modules.utils import log
from modules import config





def get_advanced_opts(d) -> dict:
    opts: dict = {}

    # Subtitles
    selected_subtitle = getattr(d, "selected_subtitle", None)
    if selected_subtitle:
        opts["writesubtitles"]    = True
        opts["subtitleslangs"]    = [selected_subtitle]
        opts["subtitlesformat"]   = getattr(d, "subtitle_format", "best")
        opts["writeautomaticsub"] = bool(getattr(d, "is_auto_sub", False))
        # Keep warnings visible so subtitle 429s appear in the log
        opts["no_warnings"]       = config.ytdlp_config.get('no_warnings', True)
        opts["ignoreerrors"]      = config.ytdlp_config.get('ignore_errors', True)
        opts["sleep_interval_requests"] = config.ytdlp_config.get('sleep_interval_requests', 10)
        opts["max_sleep_interval"] = config.ytdlp_config.get('max_sleep_interval', 10)
        opts["sleep_subtitles"] = config.ytdlp_config.get('sleep_interval_subtitles', 60)

        embed_subtitle = bool(getattr(d, 'embed_subtitles', False))
        if embed_subtitle:
            opts['postprocessors'] = [{
                'key': 'FFmpegEmbedSubtitle',
            }]
            opts["embedsubtitles"] = True

    opts["postprocessors"] = []

    conv_mode  = getattr(d, "conv_mode",     "None (Original)")
    target_ext = getattr(d, "target_format", "mp3")

    if conv_mode == "Extract Audio":
        opts["postprocessors"].append({
            "key":             "FFmpegExtractAudio",
            "preferredcodec":  target_ext,          # mp3 / m4a / wav / flac
            "preferredquality": "5",
            "nopostoverwrites": False,
        })
        opts["keepvideo"] = bool(getattr(d, "keep_video", False))

    elif conv_mode == "Remux Video":
        opts["postprocessors"].append({
            "key":             "FFmpegVideoRemuxer",
            "preferedformat":  target_ext,           # note yt-dlp's typo: prefered
        })

    elif conv_mode == "Recode Video":
        opts["postprocessors"].append({
            "key":             "FFmpegVideoConvertor",
            "preferedformat":  target_ext,
        })

    # Metadata / chapters
    if getattr(d, "embed_metadata", False) or getattr(d, "embed_chapters", False):
        opts["addmetadata"]  = True
        opts["addchapters"]  = True
        opts["writeinfojson"] = True
        opts["postprocessors"].append({
            "key":          "FFmpegMetadata",
            "add_chapters": bool(getattr(d, "embed_chapters", False)),
            "add_metadata": bool(getattr(d, "embed_metadata", False)),
        })

    # Thumbnail embedding
    if getattr(d, "embed_thumbnail", False):
        opts["writethumbnail"] = True
        opts["postprocessors"].append({"key": "EmbedThumbnail"})

    # Comments
    if getattr(d, "download_comments", False):
        opts["getcomments"]   = True
        opts["writecomments"] = True

    if not opts["postprocessors"]:
        del opts["postprocessors"]

    return opts




def _pick_subtitle_url(sub_entries: list, preferred_fmt: str) -> tuple:
    """
    From vid_info['subtitles'][lang] or vid_info['automatic_captions'][lang],
    return (url, ext) for the best match to preferred_fmt.
    """
    if not sub_entries:
        return None, None

    by_ext = {e.get("ext", ""): e for e in sub_entries if e.get("url")}
    PRIORITY = ["srt", "vtt", "ttml", "srv3", "srv2", "srv1", "json3"]

    if preferred_fmt and preferred_fmt != "best":
        if preferred_fmt in by_ext:
            e = by_ext[preferred_fmt]
            return e["url"], preferred_fmt
        if "vtt" in by_ext:
            return by_ext["vtt"]["url"], "vtt"

    for ext in PRIORITY:
        if ext in by_ext:
            return by_ext[ext]["url"], ext

    first = sub_entries[0]
    return first.get("url"), first.get("ext", "vtt")


def fetch_subtitle_with_retry(d) -> bool:
    """
    Download the subtitle selected on `d` with a fixed back-off schedule.
 
    Retry schedule (total wait ≤ 60 s):
        Attempt 1 → immediate
        429 → sleep 10 s → Attempt 2
        429 → sleep 20 s → Attempt 3
        429 → sleep 30 s → Attempt 4
        429 → give up, post subtitle_failed to UI queue
 
    Returns True if the subtitle file was successfully written.
    """
    RETRY_DELAYS = [10, 20, 30]   # sleeps BETWEEN attempts; len+1 = max attempts
 
    lang    = getattr(d, "selected_subtitle", None)
    fmt     = getattr(d, "subtitle_format",   "best")
    is_auto = getattr(d, "is_auto_sub",       False)
 
    if not lang:
        return False
 
    vid_info = getattr(d, "vid_info", None) or {}
 
    # ── Locate subtitle entries in vid_info ───────────────────────────────────────
    sub_entries = None
    if is_auto:
        sub_entries = (vid_info.get("automatic_captions") or {}).get(lang)
    if not sub_entries:
        sub_entries = (vid_info.get("subtitles") or {}).get(lang)
    if not sub_entries:
        sub_entries = (
            (vid_info.get("automatic_captions") or {}).get(lang)
            or (vid_info.get("subtitles") or {}).get(lang)
        )
 
    if not sub_entries:
        log(f"[Subtitle] No entries in vid_info for lang=\'{lang}\'", log_level=2)
        return False
 
    url, actual_ext = _pick_subtitle_url(sub_entries, fmt)
    if not url:
        log(f"[Subtitle] No usable URL for lang=\'{lang}\' fmt=\'{fmt}\'", log_level=2)
        return False
 
    bare     = os.path.splitext(d.name)[0]
    out_ext  = actual_ext or "vtt"
    out_path = os.path.join(d.folder, f"{bare}.{lang}.{out_ext}")
    max_attempts = len(RETRY_DELAYS) + 1   # 4
 
    log(f"[Subtitle] Fetching → {os.path.basename(out_path)}", log_level=1)
 
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept":          "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://www.youtube.com/",
        "Origin":          "https://www.youtube.com",
    }
 
    for attempt in range(1, max_attempts + 1):
        try:
            log(f"[Subtitle] Attempt {attempt}/{max_attempts} …", log_level=2)
            resp = requests.get(url, headers=headers, timeout=30)
 
            if resp.status_code == 200:
                os.makedirs(d.folder, exist_ok=True)
                with open(out_path, "wb") as fh:
                    fh.write(resp.content)
                log(f"[Subtitle] ✓ Saved: {os.path.basename(out_path)}", log_level=1)
                return True
 
            elif resp.status_code == 429:
                if attempt > len(RETRY_DELAYS):          # no more delays left
                    log(f"[Subtitle] ✗ Still 429 after {max_attempts} attempts.", log_level=2)
                    break
                delay = RETRY_DELAYS[attempt - 1]        # 10, 20, 30
                log(f"[Subtitle] HTTP 429 – sleeping {delay}s (attempt {attempt}/{max_attempts}) …", log_level=1)
                time.sleep(delay)
 
            else:
                log(f"[Subtitle] ✗ HTTP {resp.status_code} – aborting.", log_level=2)
                break
 
        except requests.RequestException as exc:
            log(f"[Subtitle] Network error on attempt {attempt}: {exc}", log_level=2)
            if attempt <= len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt - 1]
                time.sleep(delay)
 
    # ── All attempts failed — notify the UI ──────────────────────────────────────
    log(f"[Subtitle] All attempts failed for lang=\'{lang}\'. Notifying UI.", log_level=1)
    try:
        config.main_window_q.put((
            "subtitle_failed",
            {
                "title":    getattr(d, "title", d.name),
                "lang":     lang,
                "fmt":      out_ext,
                "url":      url,
                "out_path": out_path,
            }
        ))
    except Exception as e:
        log(f"[Subtitle] Could not post subtitle_failed to queue: {e}", log_level=2)
 
    return False


