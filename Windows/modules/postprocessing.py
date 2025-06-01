import asyncio
from modules.threadpool import executor
from modules.utils import log
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
