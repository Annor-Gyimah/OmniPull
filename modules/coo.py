import subprocess

def merge_video_audio(video_path, audio_path, output_path):
    command = [
        "C:\\Users\\Annorion\\AppData\\Roaming\\.OmniPull\\ffmpeg.exe",
        "-y",  # overwrite output if exists
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",   # copy video (no re-encoding)
        "-c:a", "aac",    # encode audio to AAC (safe for mp4)
        "-strict", "experimental",
        output_path
    ]

    subprocess.run(command, check=True)

# Example usage
merge_video_audio("C:\\Users\\Annorion\\Desktop\\Test\GERMAN\\Twins fall in love.video.mp4", "C:\\Users\\Annorion\\Desktop\\Test\\GERMAN\\Twins fall in love.audio.m4a", "C:\\Users\\Annorion\\Desktop\\Test\\GERMAN\\output.mp4")


# C:\\Users\\Annorion\\AppData\\Roaming\\.OmniPull\\ffprobe.exe -i "C:\\Users\\Annorion\\Desktop\\Test\\GERMAN\\Dating In Korea as a Foreigner.mp4"