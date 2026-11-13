import socket
import threading
import time

URLS = [
    "http://example.com",
    "http://example.com/a",
    "http://example.com/b",
    "http://example.com/c",
    "http://example.com/d",
    "http://example.com/e",
] * 2   # 12 requests in total


def request(i, url, results):
    start = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 9000))
    s.sendall(f"GET {url}\n".encode())
    data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
    s.close()
    status = data.decode("utf-8", errors="replace").split("\n", 1)[0]
    results[i] = (url, status, time.time() - start)


results = {}
threads = [threading.Thread(target=request, args=(i, u, results)) for i, u in enumerate(URLS)]

t0 = time.time()
for t in threads: t.start()
for t in threads: t.join()
print(f"Total time: {time.time() - t0:.2f}s\n")

for i in sorted(results):
    url, status, secs = results[i]
    print(f"{i:2} | {url:25} | {status:28} | {secs:.2f}s")