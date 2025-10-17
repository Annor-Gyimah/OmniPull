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

import asyncio

from modules.utils import log
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
