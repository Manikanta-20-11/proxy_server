from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import time


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(2)                      # pretend to be a slow website
        body = f"<html><body>Slow page: {self.path}</body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):          # keep the terminal quiet
        pass


print("Slow server on http://127.0.0.1:8080 (2 seconds per reply)")
ThreadingHTTPServer(("127.0.0.1", 8080), Handler).serve_forever()