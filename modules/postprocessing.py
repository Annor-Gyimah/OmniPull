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
import asyncio
import subprocess

from modules.utils import log
from modules.config import get_effective_ffmpeg
from modules.threadpool import executor
from modules.video import merge_video_audio

async def async_merge_video_audio(video_path, audio_path, output_path, download_item):
    loop = asyncio.get_running_loop()
    log(f"[MERGE] Queued merge task for: {output_path}")
    result = await loop.run_in_executor(
        executor,
        merge_video_audio,
        video_path,
        audio_path,
        output_path,
        download_item
    )
    log(f"[MERGE] Merge completed for: {output_path} | Result: {result}")
    return result



def _apply_postprocessing(d, emitter=None):
    """
    Apply yt-dlp-style post-processing (audio extract, remux, metadata embed)
    to the finished file at d.target_file using FFmpeg directly.
    Triggered after curl / aria2c downloads complete.
    """
    from modules.subtitles import get_advanced_opts
    ctx = "POST-PROC"
    
    conv_mode  = getattr(d, "conv_mode",     "None (Original)")
    target_ext = getattr(d, "target_format", "mp4")
    src        = d.target_file

    if not src or not os.path.exists(src):
        return
    if conv_mode == "None (Original)":
        return   # nothing to do

    ffmpeg = get_effective_ffmpeg()
    if not ffmpeg:
        log("[POST-PROC] FFmpeg not found; skipping post-processing.", log_level=2, context=ctx)
        return

    base, _ = os.path.splitext(src)
    out      = f"{base}.{target_ext}"

    if conv_mode == "Extract Audio":
        # -vn = drop video; use the appropriate codec
        codec_map = {"mp3": "libmp3lame", "m4a": "aac", "wav": "pcm_s16le", "flac": "flac"}
        acodec = codec_map.get(target_ext, "copy")
        cmd = [ffmpeg, "-y", "-i", src, "-vn", "-acodec", acodec, out]

    elif conv_mode == "Remux Video":
        cmd = [ffmpeg, "-y", "-i", src, "-c", "copy", out]

    elif conv_mode == "Recode Video":
        cmd = [ffmpeg, "-y", "-i", src, out]

    else:
        return

    log(f"[POST-PROC] Running: {' '.join(cmd[:5])} …", log_level=1, context=ctx)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(out):
            log(f"[POST-PROC] ✓ Converted to {os.path.basename(out)}", log_level=1, context=ctx)
            if not getattr(d, "keep_video", False) and conv_mode == "Extract Audio":
                try: os.remove(src)
                except Exception: pass
            d.target_file = out
            d.name        = os.path.basename(out)
        else:
            log(f"[POST-PROC] FFmpeg error: {result.stderr[:300]}", log_level=2, context=ctx)
    except Exception as e:
        log(f"[POST-PROC] Exception: {e}", log_level=2, context=ctx)