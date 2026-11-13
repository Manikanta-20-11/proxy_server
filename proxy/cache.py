import threading
import time
from collections import OrderedDict


class Cache:
    def __init__(self, max_pages=20, ttl_seconds=300):
        self.max_pages = max_pages
        self.ttl = ttl_seconds
        self.data = OrderedDict()      # url -> (content, time_saved)
        self.lock = threading.Lock()

    def get(self, url):
        with self.lock:
            if url not in self.data:
                return None
            content, saved_at = self.data[url]
            if time.time() - saved_at > self.ttl:
                del self.data[url]     # expired, remove it
                return None
            return content

    def put(self, url, content):
        with self.lock:
            if url in self.data:
                del self.data[url]     # re-insert so it counts as newest
            self.data[url] = (content, time.time())
            while len(self.data) > self.max_pages:
                self.data.popitem(last=False)   # remove the oldest