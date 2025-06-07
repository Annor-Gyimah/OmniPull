
from PySide6.QtCore import QThread, Signal, Qt
import time
from modules import video, config
from modules.utils import log
from modules.video import Video
from yt_dlp.utils import DownloadError, ExtractorError
from PySide6.QtWidgets import QMainWindow, QApplication

class YouTubeThread(QThread):
    finished = Signal(object)  # Signal when the process is complete
    progress = Signal(int)  # Signal to update progress bar (0-100%)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def change_cursor(self, cursor_type: str):
        if cursor_type == 'busy':
            QApplication.setOverrideCursor(Qt.WaitCursor)
        elif cursor_type == 'normal':
            QApplication.restoreOverrideCursor()

    def run(self):
        try:
            if video.ytdl is None:
                log('youtube-dl module still loading, please wait')
                while not video.ytdl:
                    time.sleep(0.1)

            log(f"Extracting info for URL: {self.url}")
            self.change_cursor('busy')

            with video.ytdl.YoutubeDL(video.get_ytdl_options()) as ydl:
                info = ydl.extract_info(self.url, download=False, process=True)
                log('Media info:', info, log_level=3)

                if info.get('_type') == 'playlist' or 'entries' in info:
                    pl_info = list(info.get('entries', []))
                    playlist = []
                    for index, item in enumerate(pl_info):
                        url = item.get('url') or item.get('webpage_url') or item.get('id')
                        if url:
                            playlist.append(Video(url, vid_info=item))
                        self.progress.emit(int((index + 1) * 100 / len(pl_info)))
                    result = playlist
                else:
                    result = Video(self.url, vid_info=None)
                    self.progress.emit(50)
                    time.sleep(1)
                    self.progress.emit(100)

                self.finished.emit(result)
                self.change_cursor('normal')

        except DownloadError as e:
            log('DownloadError:', e)
            self.finished.emit(None)
        except ExtractorError as e:
            log('ExtractorError:', e)
            self.finished.emit(None)
        except Exception as e:
            log('Unexpected error:', e)
            self.finished.emit(None)
