import socket
import threading
import time

URLS = [f"http://127.0.0.1:8080/page{i}" for i in range(12)]   # all different, so no cache hits
results = []
lock = threading.Lock()


def request(i, url, t0):
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
    with lock:
        results.append((time.time() - t0, i, status))


t0 = time.time()
threads = [threading.Thread(target=request, args=(i, u, t0)) for i, u in enumerate(URLS)]
for t in threads: t.start()
for t in threads: t.join()

print(f"Total time: {time.time() - t0:.2f}s  (one at a time would be about 24s)\n")
for finished, i, status in sorted(results):
    print(f"request {i:2} finished at {finished:.2f}s | {status}")