import threading
from datetime import datetime


class Logger:
    def __init__(self, filename="proxy.log"):
        self.filename = filename
        self.lock = threading.Lock()   # one lock shared by all threads

    def log(self, client, url, result):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} | {client} | {url} | {result}\n"

        with self.lock:                # only one thread can be inside at a time
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(line)