import threading
from logger import Logger

logger = Logger("test.log")

def work(n):
    for i in range(20):
        logger.log(f"client{n}", "http://example.com", "OK")

threads = [threading.Thread(target=work, args=(n,)) for n in range(5)]
for t in threads: t.start()
for t in threads: t.join()

print(sum(1 for _ in open("test.log")), "lines (expected 100)")