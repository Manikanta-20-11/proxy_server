import time
from cache import Cache

c = Cache(max_pages=3, ttl_seconds=2)

c.put("a", "page A")
print(c.get("a"))            # page A
print(c.get("zzz"))          # None (never saved)

time.sleep(3)
print(c.get("a"))            # None (expired after 2 seconds)

for name in ["p1", "p2", "p3", "p4"]:
    c.put(name, f"page {name}")
print(c.get("p1"))           # None (oldest, removed when full)
print(c.get("p4"))           # page p4