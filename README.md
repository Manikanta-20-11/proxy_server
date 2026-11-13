# Multi-Threaded HTTP/HTTPS Proxy Server and Client

## 1. Overview
This project implements a multi-threaded HTTP/HTTPS proxy server and a companion Flask web client in Python for Windows. The client submits target URLs over a direct TCP socket connection to the proxy server. The proxy server retrieves the web resource using worker threads, processes and sanitises the response (including link rewriting and header separation), caches successful pages in memory, and returns the content to the client. The client renders the received HTML, displays request metadata, allows interactive browsing, and automatically saves a local copy in a dedicated directory. This directly satisfies the course project requirements for client-server communication, multi-threaded request processing, and local file storage.

## 2. Architecture

```text
+-------------------+        HTTP POST /fetch        +-------------------+
|   Web Browser     | -----------------------------> |   Flask Client    |
| (Interactive UI)  | <----------------------------- | (client_app.py)   |
+-------------------+      HTML + JSON Status        +-------------------+
                                                               |
                                                  TCP Socket   | GET <url>\n
                                                Port 9000      v
+-------------------+        HTTP / HTTPS            +-------------------+
|  Target Website   | <----------------------------- |   Proxy Server    |
|    (Internet)     | -----------------------------> | (proxy_server.py) |
+-------------------+         HTML Body              +-------------------+
                                                        |      |      |
                                                  Thread Pool  Cache  Logger
```

### Component and File Breakdown
- `proxy/proxy_server.py`: Main proxy listener on `127.0.0.1:9000`. Manages a bounded thread pool and dispatches incoming TCP connections to worker threads.
- `proxy/processor.py`: Network fetch engine. Handles HTTP/HTTPS connections, SSL validation with `certifi`, redirect following, and HTML relative link rewriting.
- `proxy/cache.py`: Thread-safe, in-memory cache with time-to-live (TTL) expiration and size capping.
- `proxy/logger.py`: Thread-safe file logger recording timestamps, client endpoints, URLs, and status strings into `proxy.log`.
- `client/client_app.py`: Flask application on `127.0.0.1:5000`. Exposes UI routes (`/`, `/fetch`, `/history`, `/saved/<filename>`, `/history/clear`) and communicates with the proxy over raw TCP.
- `client/templates/index.html`: Web interface featuring live rendered preview, HTML source inspector, script sandboxing controls, and a persistent history viewer.
- `client/saved_pages/`: Local folder storing saved HTML pages and `history.json`.

## 3. Communication Protocol
The Flask client and the proxy communicate over a custom text-based TCP protocol on port 9000:

1. **Client Request**:
   ```text
   GET <url>\n
   ```
   *Example*: `GET http://example.com\n`

2. **Proxy Success Reply**:
   ```text
   OK <source> <worker> <seconds>\n<page body>
   ```
   *Example*: `OK FETCHED Worker-2 0.131\n<!doctype html>...`
   *Example*: `OK CACHE Worker-1 0.001\n<!doctype html>...`

3. **Proxy Error Reply**:
   ```text
   ERROR <reason>\n
   ```
   *Example*: `ERROR HTTP 404 Not Found\n`

After sending the status line and response body (or error line), the proxy closes the TCP connection.

**Why a newline delimiter?**
TCP is a byte-stream transport protocol without built-in message framing. Packets can be fragmented or coalesced by the operating system network stack. Terminating the request line with `\n` provides an explicit delimiter so `read_line()` knows when the URL ends without waiting for the socket to close.

## 4. Operating System Concepts

| OS Concept | Implementation in Code | Location | Explanation |
|---|---|---|---|
| Sockets | `socket.socket()`, `bind()`, `listen()`, `accept()` | `proxy/proxy_server.py` (`start_server`) | Creates the TCP listening socket, binds to `127.0.0.1:9000`, and accepts client connections. |
| Producer-Consumer Queue | `queue.Queue()`, `put()`, `get()` | `proxy/proxy_server.py` (`start_server`, `worker`) | The main thread acts as producer pushing accepted sockets; worker threads act as consumers pulling tasks. |
| Thread Pool | `threading.Thread()`, `NUM_WORKERS = 5` | `proxy/proxy_server.py` (`start_server`, `worker`) | Pre-allocates 5 reusable worker threads at startup instead of spawning a new OS thread per connection. |
| Mutex Locks | `threading.Lock()` with `with self.lock:` | `proxy/cache.py` (`get`, `put`), `proxy/logger.py` (`log`), `client/client_app.py` (`history_lock`) | Ensures mutual exclusion during reads and writes to shared memory and files. |
| Blocking Calls | `connection_queue.get()`, `server.accept()` | `proxy/proxy_server.py` (`worker`, `start_server`) | Puts threads to sleep until events occur; workers consume zero CPU cycles while idle. |
| Timeouts | `server.settimeout(1)`, `s.settimeout(30)`, `timeout=10` | `proxy/proxy_server.py`, `client/client_app.py`, `proxy/processor.py` | Prevents indefinite thread blocking on unresponsive sockets or ungraceful network drops. |
| Resource Cleanup | `try ... finally: sock.close()` | `proxy/proxy_server.py` (`handle_client`), `client/client_app.py` (`ask_proxy`) | Guarantees release of socket descriptors back to the OS even when runtime exceptions occur. |
| Daemon Threads | `threading.Thread(..., daemon=True)` | `proxy/proxy_server.py` (`start_server`) | Marks background worker threads as daemon so the process exits cleanly on `KeyboardInterrupt`. |

### Race Conditions and Lock Necessity
- **Cache Lock (`proxy/cache.py`)**: Without locking, concurrent worker threads inserting and evicting items in `OrderedDict` would corrupt internal doubly-linked pointers and raise dictionary mutation runtime errors.
- **Logger Lock (`proxy/logger.py`)**: Multiple threads writing to `proxy.log` simultaneously would interleave buffer flushes, corrupting log lines.
- **History Lock (`client/client_app.py`)**: Flask handles requests on multiple threads. The lock and atomic `.tmp` + `os.replace` write pattern prevent corrupted or half-written `history.json` files.

## 5. Features
- **In-Memory Cache**: Capacity capped at 20 pages with a 300-second (5 minute) TTL (`Cache(max_pages=20, ttl_seconds=300)`). Oldest entries are evicted first (FIFO order) when full.
- **Thread-Safe Logging**: Logs every request with format `YYYY-MM-DD HH:MM:SS | client_ip:port | url | result`.
- **Header Stripping**: The proxy fetches HTTP resources, verifies status codes, and returns only the clean HTML body to the client.
- **Redirect Following**: Automatically follows 301, 302, 303, 307, and 308 redirect chains up to 3 hops (`MAX_REDIRECTS = 3`).
- **HTML Link Rewriting**: Uses regular expressions to convert relative `src` and `href` links into absolute URLs using the final target host.
- **HTTPS & SSL Verification**: Validates SSL/TLS certificates against the Mozilla CA bundle provided by `certifi`.
- **History Management**: Tracks the 50 newest fetches with metadata; supports re-opening cached/saved pages and downloading original HTML.
- **Collision-Resistant Filenames**: Generates saved page filenames formatted as `<host>_<YYYY-MM-DD>_<HHMMSS>_<4_hex_chars>.html` using `secrets.token_hex(2)` with collision detection loops.

## 6. Setup and Execution (Windows)

### Prerequisites
Install dependencies using Python 3:
```powershell
pip install -r requirements.txt
```

### Running the Services
Open two separate PowerShell terminal windows:

1. **Terminal 1 - Proxy Server**:
   ```powershell
   cd d:\SRM\Sem-5\OS_Project\proxy
   python proxy_server.py
   ```
2. **Terminal 2 - Flask Client**:
   ```powershell
   cd d:\SRM\Sem-5\OS_Project\client
   python client_app.py
   ```
3. Open your browser and navigate to `http://127.0.0.1:5000`.

*Note: Each program must be run from inside its own folder. Running `proxy_server.py` from `proxy/` ensures `proxy.log` is created in that folder.*

## 7. Test Suite
The following test scripts exist in the `proxy/` folder:

- `test_connect.py`: Connects directly to the proxy port 9000, sends a raw `GET` command, and verifies receipt of the status line and HTML payload.
- `test_logger.py`: Spawns 5 threads logging 20 entries each concurrently; proves thread safety by verifying exactly 100 unbroken lines in `test.log`.
- `test_cache.py`: Verifies cache storage, cache miss, TTL expiration after 2 seconds, and eviction of the oldest entry when exceeding capacity (3 items).
- `test_processor.py`: Tests the fetch engine against valid HTTP/HTTPS URLs, 404 pages, nonexistent domains, and SSL certificate failures.
- `test_rewrite.py`: Tests regex link rewriting across 9 cases including relative paths, root-relative links, protocol-relative links, anchors, and data URIs.
- `test_cert.py`: Tests SSL error handling against invalid certificate endpoints from `badssl.com` (expired, self-signed, wrong host).
- `test_concurrent.py`: Fires 12 simultaneous requests across 6 distinct URLs; demonstrates parallel worker processing and cache hit acceleration.
- `slow_server.py` and `test_slow.py`: `slow_server.py` serves dummy pages on port 8080 with a 2-second sleep. `test_slow.py` dispatches 12 simultaneous requests to the proxy; with 5 workers, requests complete in 3 waves (at ~2s, ~4s, and ~6s, total ~6s) rather than 24s sequentially.
- `test.py`: Verifies raw socket SSL handshake and certificate validation with `certifi`.

## 8. Known Limitations
- **Dynamic JavaScript Content**: Client-side single page applications (SPAs) that require a JavaScript engine to render markup will not display fully in the static iframe preview.
- **CSS and Complex Assets**: Relative URLs inside CSS `url(...)` declarations, `srcset` image attributes, and inline scripts are not rewritten.
- **Existing Base Tags**: Does not parse or merge existing `<base>` tags defined inside the fetched document.
- **Anti-Bot Gating**: Websites using Cloudflare Turnstile, CAPTCHAs, or blocking automated user-agents will refuse connection.
- **Non-Persistent Cache**: The proxy cache is stored in memory and resets whenever the server process restarts.

## 9. Future Improvements
1. Implement persistent on-disk or SQLite caching with LRU cache expiration.
2. Add support for HTTP chunked transfer encoding and streaming large responses.
3. Support CSS `@import` and `url()` link rewriting.
4. Implement basic authentication between the client app and proxy server.
5. Provide a configuration file or CLI arguments for port numbers, cache TTL, and worker pool size.

## 10. Team Members and Contributions
- **Team Members**: `<name 1>`, `<name 2>`, `<name 3>`
- **Planned Work Allocation**:
  - *Client and Web Page*: Flask routes, HTML/CSS/JS frontend, iframe preview, history view (`<name 1>`).
  - *Proxy Core*: Socket server, producer-consumer queue, thread pool dispatching, protocol definition (`<name 2>`).
  - *Cache, Processor, and Testing*: In-memory cache, logging, redirect/rewrite processor, test scripts (`<name 3>`).

