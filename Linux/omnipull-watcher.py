#!/usr/bin/env python3
import sys
import struct
import json
import os

QUEUE_PATH = os.path.expanduser("~/.config/OmniPull/.omnipull_url_queue.json")



# Initialize queue file if it doesn't exist
def init_queue_file():
    if not os.path.exists(QUEUE_PATH):
        os.makedirs(os.path.dirname(QUEUE_PATH), exist_ok=True)
        # Create the file with an empty queue
        with open(QUEUE_PATH, "w") as f:
            json.dump([], f)
        print(f"Created queue file at: {QUEUE_PATH}")
    return os.path.exists(QUEUE_PATH)

# ...existing code...


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
            except json.JSONDecodeError:
                print("Error reading queue file, creating new queue")
                queue = []
    queue.append(data)
    with open(QUEUE_PATH, "w") as f:
        json.dump(queue, f)
    print(f"Added to queue: {data}")

if __name__ == "__main__":

    # Initialize the queue file first
    if init_queue_file():
        print("Queue file ready")
    else:
        print("Failed to create queue file")
        sys.exit(1)

    try:
        msg = read_message()
        append_to_queue(msg)
        send_response({"status": "queued", "url": msg.get("url")})
    except Exception as e:
        send_response({"status": "error", "message": str(e)})
