import socket
import sys

url = sys.argv[1] if len(sys.argv) > 1 else "http://example.com"

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

text = data.decode("utf-8", errors="replace")
status, _, body = text.partition("\n")
print("Status:", status)
print("Body length:", len(body), "characters")
print("Preview:", body[:80].replace("\n", " "))