import time
import socket
import queue
import threading

from cache import Cache
from logger import Logger
from processor import fetch

HOST = "127.0.0.1"
PORT = 9000
BACKLOG = 20
NUM_WORKERS = 7

# Shared objects: every worker uses these same ones
connection_queue = queue.Queue()
cache = Cache(max_pages=20, ttl_seconds=300)
logger = Logger("proxy.log")


def read_line(sock):
    """Read bytes until a newline. Returns the line as text."""
    data = b""
    while not data.endswith(b"\n"):
        chunk = sock.recv(1024)
        if not chunk:          # client closed early
            break
        data += chunk
        if len(data) > 4096:   # a URL should never be this long
            break
    return data.decode("utf-8", errors="replace").strip()


def handle_client(client_sock, addr, worker_name):
    """Serve one client: read URL, get the page, reply."""
    client_label = f"{addr[0]}:{addr[1]}"
    start = time.time()
    try:
        line = read_line(client_sock)

        if not line.startswith("GET "):
            client_sock.sendall(b"ERROR Bad request, use: GET <url>\n")
            logger.log(client_label, line, "BAD REQUEST")
            return

        url = line[4:].strip()

        # 1. Try the cache first
        content = cache.get(url)
        if content is not None:
            took = time.time() - start
            header = f"OK CACHE {worker_name} {took:.3f}\n"
            client_sock.sendall(header.encode() + content.encode("utf-8"))
            logger.log(client_label, url, f"CACHE HIT ({worker_name})")
            return

        # 2. Not cached: fetch from the real website
        ok, result = fetch(url)
        if ok:
            cache.put(url, result)
            took = time.time() - start
            header = f"OK FETCHED {worker_name} {took:.3f}\n"
            client_sock.sendall(header.encode() + result.encode("utf-8"))
            logger.log(client_label, url, f"FETCHED ({worker_name})")
        else:
            client_sock.sendall(f"ERROR {result}\n".encode("utf-8"))
            logger.log(client_label, url, f"ERROR: {result} ({worker_name})")

    except Exception as e:
        logger.log(client_label, "-", f"CRASH: {e} ({worker_name})")
    finally:
        client_sock.close()


def worker():
    """Runs forever: take a connection from the queue, serve it, repeat."""
    name = threading.current_thread().name
    while True:
        client_sock, addr = connection_queue.get()
        handle_client(client_sock, addr, name)


def start_server():
    # Create the worker pool ONCE, at startup
    for i in range(NUM_WORKERS):
        threading.Thread(target=worker, name=f"Worker-{i+1}", daemon=True).start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(BACKLOG)
    server.settimeout(1)
    print(f"Proxy listening on {HOST}:{PORT} with {NUM_WORKERS} workers")

    try:
        while True:
            try:
                client_sock, addr = server.accept()
            except socket.timeout:
                continue
            print(f"[main] connection from {addr}, adding to queue")
            connection_queue.put((client_sock, addr))
    except KeyboardInterrupt:
        print("\nShutting down")
    finally:
        server.close()


if __name__ == "__main__":
    start_server()