#!/usr/bin/env python3
import sys
import struct
import json
import os

QUEUE_PATH = os.path.expanduser("~/.pyiconic_url_queue.json")

def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        sys.exit(0)
    message_length = struct.unpack('=I', raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    return json.loads(message)

def send_response(data):
    response = json.dumps(data).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('=I', len(response)))
    sys.stdout.buffer.write(response)
    sys.stdout.buffer.flush()

def append_to_queue(data):
    queue = []
    if os.path.exists(QUEUE_PATH):
        with open(QUEUE_PATH, "r") as f:
            try:
                queue = json.load(f)
            except:
                pass
    queue.append(data)
    with open(QUEUE_PATH, "w") as f:
        json.dump(queue, f)

if __name__ == "__main__":
    try:
        msg = read_message()
        append_to_queue(msg)
        send_response({"status": "queued", "url": msg.get("url")})
    except Exception as e:
        send_response({"status": "error", "message": str(e)})
