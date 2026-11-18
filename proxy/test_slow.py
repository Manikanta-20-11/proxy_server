import socket
import threading
import time
import secrets
from collections import defaultdict

NUM_REQUESTS = 12
RUN_TAG = secrets.token_hex(4)
URLS = [f"http://127.0.0.1:8080/page{i}?run={RUN_TAG}" for i in range(NUM_REQUESTS)]

results = []
lock = threading.Lock()


def do_request(i, url, t0):
    t_submit = time.perf_counter() - t0
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(30)
        s.connect(("127.0.0.1", 9000))
        s.sendall(f"GET {url}\n".encode())
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    except Exception as e:
        with lock:
            results.append((i, "?", 0, 0, time.perf_counter() - t0, str(e)))
        return
    finally:
        if s is not None:
            s.close()

    t_done = time.perf_counter() - t0
    text = data.decode("utf-8", errors="replace")
    status_line = text.split("\n", 1)[0]
    parts = status_line.split()

    if len(parts) != 4 or parts[0] != "OK":
        with lock:
            results.append((i, "?", 0, 0, t_done, status_line or "Empty reply"))
        return

    worker = parts[2] if len(parts) >= 4 else "?"
    try:
        service = float(parts[3]) if len(parts) >= 4 else 0.0
    except ValueError:
        service = 0.0
    queue_wait = max(0.0, (t_done - service) - t_submit)

    with lock:
        results.append((i, worker, queue_wait, service, t_done, ""))


t0 = time.perf_counter()
threads = [threading.Thread(target=do_request, args=(i, u, t0)) for i, u in enumerate(URLS)]
for t in threads:
    t.start()
for t in threads:
    t.join()

total = time.perf_counter() - t0
print(f"Total time: {total:.2f}s  (one at a time would be about 24s)\n")

# ---- Table sorted by request number ----
results.sort(key=lambda r: r[0])
print(f"{'req':>4}  {'worker':<10}  {'queue wait':>10}  {'service':>8}  {'finished':>9}")
print(f"{'----':>4}  {'----------':<10}  {'----------':>10}  {'--------':>8}  {'---------':>9}")
for i, worker, qw, svc, done, err in results:
    if err:
        print(f"{i:4d}  {'ERROR':<10}  {err}")
    else:
        print(f"{i:4d}  {worker:<10}  {qw:9.3f}s  {svc:7.3f}s  {done:8.3f}s")

# ---- Timeline ----
print("\nTimeline (each # = 0.25s):\n")

worker_requests = defaultdict(list)
for i, worker, qw, svc, done, err in results:
    if not err:
        service_start = done - svc
        worker_requests[worker].append((i, service_start, svc))

SCALE = 0.25
LINE_WIDTH = max(32, int(total / SCALE) + 8)
sorted_workers = [f"Worker-{i}" for i in range(1, 6)]

for w in sorted_workers:
    line = list(" " * LINE_WIDTH)
    ordered = sorted(worker_requests[w], key=lambda r: r[1])
    for req_i, start, svc in ordered:
        col = int(start / SCALE)
        length = max(1, round(svc / SCALE))
        for c in range(col, min(col + length, LINE_WIDTH)):
            line[c] = "#"
    order = " -> ".join(str(req_i) for req_i, _, _ in ordered)
    print(f"{w:<10}|{''.join(line)}| requests: {order}")

# Scale line
ruler = list(" " * LINE_WIDTH)
max_s = int(total) + 1
for s in range(0, max_s + 1):
    pos = int(s / SCALE)
    label = f"{s}s"
    for ci, ch in enumerate(label):
        if pos + ci < LINE_WIDTH:
            ruler[pos + ci] = ch
print(f"{'':10} {''.join(ruler)}")
