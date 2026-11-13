import os
import re
import socket
import json
import threading
import secrets
from datetime import datetime
from urllib.parse import urlparse

from flask import Flask, render_template, request, jsonify, send_from_directory

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 9000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "saved_pages")
HISTORY_FILE = os.path.join(SAVE_DIR, "history.json")
os.makedirs(SAVE_DIR, exist_ok=True)

history_lock = threading.Lock()

app = Flask(__name__)


def load_history():
    """Read history.json under lock. Returns empty list if missing or corrupt."""
    with history_lock:
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception:
            return []


def save_history_atomically(entries):
    """Write entries to history.json.tmp then os.replace under lock."""
    with history_lock:
        tmp_file = HISTORY_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        os.replace(tmp_file, HISTORY_FILE)


def append_history(entry):
    """Append entry to history.json under lock, keeping newest 50 entries."""
    with history_lock:
        entries = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        entries = data
            except Exception:
                entries = []
        entries.append(entry)
        if len(entries) > 50:
            entries = entries[-50:]
        tmp_file = HISTORY_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        os.replace(tmp_file, HISTORY_FILE)


def ask_proxy(url):
    """Send 'GET <url>' to the proxy over TCP. Returns (ok, content_or_error)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(30)
        s.connect((PROXY_HOST, PROXY_PORT))
        s.sendall(f"GET {url}\n".encode("utf-8"))

        data = b""
        while True:                      # proxy closes the connection when done
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        s.close()
    except ConnectionRefusedError:
        return False, "Cannot reach the proxy. Is proxy_server.py running?", {}
    except socket.timeout:
        return False, "The proxy took too long to reply", {}
    except OSError as e:
        return False, f"Connection problem: {e}",{}

    text = data.decode("utf-8", errors="replace")
    status, _, body = text.partition("\n")

    if status.startswith("OK"):
        parts = status.split()          # ["OK", "FETCHED", "Worker-1", "0.340"]
        info = {}
        if len(parts) >= 4:
            info = {"source": parts[1], "worker": parts[2], "seconds": parts[3]}
        return True, body, info
    if status.startswith("ERROR"):
        return False, status[len("ERROR"):].strip(), {}
    return False, "Unexpected reply from proxy", {}


def make_filename(url):
    """Site-based name, e.g. example.com_2026-11-12_151240_a3f9.html"""
    if "://" not in url:
        url = "http://" + url
    host = urlparse(url).hostname or "page"
    host = re.sub(r"[^A-Za-z0-9.-]", "_", host)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    rand_suffix = secrets.token_hex(2)
    return f"{host}_{stamp}_{rand_suffix}.html"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/fetch", methods=["POST"])
def fetch_page():
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    if not url:
        return jsonify(ok=False, error="Please enter a URL")

    ok, result, info = ask_proxy(url)
    if not ok:
        return jsonify(ok=False, error=result)

    filename = make_filename(url)
    while os.path.exists(os.path.join(SAVE_DIR, filename)):
        filename = make_filename(url)

    with open(os.path.join(SAVE_DIR, filename), "w", encoding="utf-8") as f:
        f.write(result)

    try:
        append_history({
            "filename": filename,
            "url": url,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": info.get("source", ""),
            "worker": info.get("worker", ""),
            "seconds": info.get("seconds", ""),
        })
    except Exception:
        pass

    return jsonify(ok=True, content=result, filename=filename, info=info)


@app.route("/history", methods=["GET"])
def get_history():
    entries = load_history()
    valid_items = [
        item for item in reversed(entries)
        if os.path.isfile(os.path.join(SAVE_DIR, item.get("filename", "")))
    ]
    return jsonify(items=valid_items)


@app.route("/saved/<path:filename>", methods=["GET"])
def get_saved_file(filename):
    if "/" in filename or "\\" in filename or ".." in filename:
        return "Not found", 404

    entries = load_history()
    if not any(item.get("filename") == filename for item in entries):
        return "Not found", 404

    filepath = os.path.join(SAVE_DIR, filename)
    if not os.path.isfile(filepath):
        return "Not found", 404

    try:
        response = send_from_directory(SAVE_DIR, filename, mimetype="text/plain")
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        return response
    except Exception:
        return "Not found", 404


@app.route("/history/clear", methods=["POST"])
def clear_history():
    save_history_atomically([])
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)