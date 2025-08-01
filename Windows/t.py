import subprocess
import json
import struct

message = json.dumps({"url": "https://s2.profdeski.com/Kijin.Gentoushou/Kijin.Gentoushou.01.720p.PS.Bia2Anime.mkv"}).encode('utf-8')
length = struct.pack('=I', len(message))

proc = subprocess.Popen(
    ['C:\\Program Files\\Annorion\\OmniPull\\omnipull-watcher.exe'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

proc.stdin.write(length)
proc.stdin.write(message)
proc.stdin.flush()

response_length_bytes = proc.stdout.read(4)

if len(response_length_bytes) < 4:
    print("❌ No response from native app")
    stderr_output = proc.stderr.read().decode()
    print("STDERR:", stderr_output)
else:
    response_length = struct.unpack('=I', response_length_bytes)[0]
    response = proc.stdout.read(response_length).decode('utf-8')
    print("✅ Native app response:", response)
