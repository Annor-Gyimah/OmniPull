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
import json
import requests

from modules.utils import log
from modules.config import get_effective_ffmpeg
from modules.threadpool import executor
from modules.video import merge_video_audio
from modules import config

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


def _download_subtitles_post_curl(d) -> bool:
    """
    Download subtitles for curl/aria2c downloads using the existing retry mechanism.
    
    This function integrates with the subtitle download system that respects:
    - Language selection
    - Format preferences (srt, vtt, ass, lrc)
    - Auto-caption selection
    - Sleep intervals to avoid rate limiting
    
    Returns True if successful or if no subtitle download was requested.
    """
    from modules.subtitles import fetch_subtitle_with_retry
    
    selected_subtitle = getattr(d, "selected_subtitle", None)
    
    if not selected_subtitle:
        log("[POST-PROC] No subtitle download requested.", log_level=2, context="POST-PROC")
        return True  # Not an error, just skipping
    
    ctx = "POST-PROC-SUBS"
    log(f"[POST-PROC] Initiating subtitle download for: {selected_subtitle}", log_level=1, context=ctx)
    
    try:
        result = fetch_subtitle_with_retry(d)
        if result:
            log(f"[POST-PROC] ✓ Subtitle downloaded successfully.", log_level=1, context=ctx)
            return True
        else:
            log(f"[POST-PROC] ✗ Subtitle download failed; continuing with other post-processing.", log_level=2, context=ctx)
            return False
    except Exception as e:
        log(f"[POST-PROC] Exception during subtitle download: {e}", log_level=2, context=ctx)
        return False


def _download_comments_post_curl(d) -> bool:
    """
    Download comments for YouTube videos (curl/aria2c downloads).
    
    Extracts and saves comments to a JSON file. Comments are typically embedded
    in the yt-dlp info.json file or can be fetched from the video info.
    
    Saves to: <download_folder>/<video_name>.comments.json
    
    Returns True if successful or if no comments were requested.
    """
    download_comments = getattr(d, "download_comments", False)
    
    if not download_comments:
        return True  # Not an error, just skipping
    
    ctx = "POST-PROC-COMMENTS"
    log(f"[POST-PROC] Initiating comments download.", log_level=1, context=ctx)
    
    try:
        # Try to get comments from vid_info
        vid_info = getattr(d, "vid_info", None) or {}
        comments = vid_info.get("comments", [])
        
        if not comments:
            log(f"[POST-PROC] No comments found in video info.", log_level=2, context=ctx)
            return True
        
        # Build output path
        base_name = os.path.splitext(d.name)[0]
        comments_path = os.path.join(d.folder, f"{base_name}.comments.json")
        
        # Ensure directory exists
        os.makedirs(d.folder, exist_ok=True)
        
        # Save comments to JSON file
        comments_data = {
            "video_id": getattr(d, "vid_id", ""),
            "video_title": getattr(d, "title", d.name),
            "total_comments": len(comments),
            "comments": comments
        }
        
        with open(comments_path, "w", encoding="utf-8") as fh:
            json.dump(comments_data, fh, indent=2, ensure_ascii=False)
        
        log(f"[POST-PROC] ✓ Saved {len(comments)} comments to: {os.path.basename(comments_path)}", 
            log_level=1, context=ctx)
        return True
        
    except Exception as e:
        log(f"[POST-PROC] Exception during comments download: {e}", log_level=2, context=ctx)
        return False


def _embed_subtitles_in_video(video_path: str, subtitle_path: str, output_path: str) -> bool:
    """
    Embed an external subtitle file into a video using FFmpeg.
    
    Args:
        video_path: Path to the video file
        subtitle_path: Path to the subtitle file (.srt, .vtt, etc.)
        output_path: Path for the output video with embedded subtitles
    
    Returns:
        True if successful, False otherwise
    """
    ffmpeg = get_effective_ffmpeg()
    if not ffmpeg:
        log("[POST-PROC] FFmpeg not found; cannot embed subtitles.", log_level=2, context="POST-PROC-EMBED-SUB")
        return False
    
    if not os.path.exists(video_path) or not os.path.exists(subtitle_path):
        log(f"[POST-PROC] Missing files for subtitle embedding.", log_level=2, context="POST-PROC-EMBED-SUB")
        return False
    
    try:
        ctx = "POST-PROC-EMBED-SUB"
        # Get the subtitle format
        sub_ext = os.path.splitext(subtitle_path)[1].lstrip('.')
        
        # Prepare FFmpeg command to embed subtitles
        cmd = [
            ffmpeg,
            "-y",
            "-i", video_path,
            "-i", subtitle_path,
            "-c", "copy",
            "-c:s", "mov_text" if sub_ext == "srt" else "copy",
            "-metadata:s:s:0", "language=eng",  # Default to English
            output_path
        ]
        
        log(f"[POST-PROC] Embedding subtitle: {os.path.basename(subtitle_path)}", log_level=1, context=ctx)
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            log(f"[POST-PROC] ✓ Subtitles embedded successfully.", log_level=1, context=ctx)
            return True
        else:
            log(f"[POST-PROC] FFmpeg error embedding subtitles: {result.stderr[:300]}", log_level=2, context=ctx)
            return False
            
    except Exception as e:
        log(f"[POST-PROC] Exception embedding subtitles: {e}", log_level=2, context=ctx)
        return False




def _apply_postprocessing(d, emitter=None):
    """
    Apply yt-dlp-style post-processing for curl/aria2c downloads:
    - Video conversion (audio extract, remux, recode)
    - Subtitle downloading & embedding
    - Comment downloading
    
    Triggered after curl / aria2c downloads complete.
    """
    from modules.subtitles import get_advanced_opts
    ctx = "POST-PROC"
    
    conv_mode  = getattr(d, "conv_mode",     "None (Original)")
    target_ext = getattr(d, "target_format", "mp4")
    src        = d.target_file

    if not src or not os.path.exists(src):
        return
    
    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 1: Download comments (if requested)
    # ─────────────────────────────────────────────────────────────────────────
    _download_comments_post_curl(d)
    
    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 2: Download subtitles (if requested)
    # ─────────────────────────────────────────────────────────────────────────
    subtitle_downloaded = False
    selected_subtitle = getattr(d, "selected_subtitle", None)
    if selected_subtitle:
        subtitle_downloaded = _download_subtitles_post_curl(d)
    
    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 3: Video conversion (if requested)
    # ─────────────────────────────────────────────────────────────────────────
    if conv_mode == "None (Original)":
        log("[POST-PROC] No video conversion requested.", log_level=2, context=ctx)
    else:
        ffmpeg = get_effective_ffmpeg()
        if not ffmpeg:
            log("[POST-PROC] FFmpeg not found; skipping post-processing.", log_level=2, context=ctx)
        else:
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
                cmd = None

            if cmd:
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
                        src = out  # Update src for subtitle embedding
                    else:
                        log(f"[POST-PROC] FFmpeg error: {result.stderr[:300]}", log_level=2, context=ctx)
                except Exception as e:
                    log(f"[POST-PROC] Exception: {e}", log_level=2, context=ctx)
    
    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 4: Embed subtitles into video (if downloaded and embed is enabled)
    # ─────────────────────────────────────────────────────────────────────────
    embed_subtitles = getattr(d, "embed_subtitles", False)
    if subtitle_downloaded and embed_subtitles and selected_subtitle:
        try:
            # Find the downloaded subtitle file
            base_name = os.path.splitext(d.name)[0]
            lang = selected_subtitle
            
            # Try to find the subtitle file (it might have been saved with a different extension)
            subtitle_candidates = [
                os.path.join(d.folder, f"{base_name}.{lang}.srt"),
                os.path.join(d.folder, f"{base_name}.{lang}.vtt"),
                os.path.join(d.folder, f"{base_name}.{lang}.ass"),
                os.path.join(d.folder, f"{base_name}.{lang}.lrc"),
            ]
            
            subtitle_path = None
            for cand in subtitle_candidates:
                if os.path.exists(cand):
                    subtitle_path = cand
                    break
            
            if subtitle_path and os.path.exists(src):
                base, ext = os.path.splitext(src)
                output_with_subs = f"{base}_with_subs{ext}"
                
                if _embed_subtitles_in_video(src, subtitle_path, output_with_subs):
                    # Replace the original video with the one containing embedded subtitles
                    try:
                        os.remove(src)
                        os.rename(output_with_subs, src)
                        d.target_file = src
                        log(f"[POST-PROC] ✓ Subtitles embedded into video.", log_level=1, context=ctx)
                    except Exception as e:
                        log(f"[POST-PROC] Could not replace video after subtitle embedding: {e}", 
                            log_level=2, context=ctx)
                        # Keep the video with embedded subtitles as a separate file
                        d.target_file = output_with_subs
            else:
                if not subtitle_path:
                    log(f"[POST-PROC] Subtitle file not found for embedding.", log_level=2, context=ctx)
        except Exception as e:
            log(f"[POST-PROC] Exception embedding subtitles: {e}", log_level=2, context=ctx)