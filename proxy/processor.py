import http.client
import re
from urllib.parse import urlparse, urljoin
import ssl
import certifi

MAX_REDIRECTS = 3

# Matches src=... or href=... in three styles: "double", 'single', or unquoted
LINK_PATTERN = re.compile(
    r'''(?<![\w-])((?:src|href)\s*=\s*)(?:"([^"]*)"|'([^']*)'|([^\s>"']+))''',
    re.IGNORECASE,
)

HAS_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

BLOCK_PATTERN = re.compile(
    r"(<!--.*?-->|<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>)",
    re.IGNORECASE | re.DOTALL,
)

TAG_PATTERN = re.compile(r"<[a-zA-Z][^>]*>")


def rewrite_links(html, base_url):
    """Turn relative links in the page into full addresses."""

    def fix(m):
        prefix = m.group(1)
        if m.group(2) is not None:
            value, quote = m.group(2), '"'
        elif m.group(3) is not None:
            value, quote = m.group(3), "'"
        else:
            value, quote = m.group(4), ""

        v = value.strip()
        # Leave alone: empty, #anchors, and anything with a scheme
        # (http:, https:, mailto:, data:, javascript: ...)
        if not v or v.startswith("#") or HAS_SCHEME.match(v):
            return m.group(0)

        full = urljoin(base_url, v)
        return f"{prefix}{quote}{full}{quote}"

    def rewrite_tag(tag_str):
        return LINK_PATTERN.sub(fix, tag_str)

    parts = BLOCK_PATTERN.split(html)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Captured comment, script block, or style block
            if part.startswith("<!--"):
                out.append(part)
            elif part.lower().startswith("<script"):
                m = re.match(r"(<script\b[^>]*>)(.*?)(</script>)", part, re.IGNORECASE | re.DOTALL)
                if m:
                    out.append(rewrite_tag(m.group(1)) + m.group(2) + m.group(3))
                else:
                    out.append(rewrite_tag(part))
            elif part.lower().startswith("<style"):
                m = re.match(r"(<style\b[^>]*>)(.*?)(</style>)", part, re.IGNORECASE | re.DOTALL)
                if m:
                    out.append(rewrite_tag(m.group(1)) + m.group(2) + m.group(3))
                else:
                    out.append(rewrite_tag(part))
            else:
                out.append(part)
        else:
            # Remaining parts: only rewrite attributes inside HTML start tags
            out.append(TAG_PATTERN.sub(lambda tm: rewrite_tag(tm.group(0)), part))

    return "".join(out)

def make_context():
    ctx = ssl.create_default_context()          # Windows trust store
    ctx.load_verify_locations(certifi.where())  # plus certifi's list
    return ctx

def fetch(url, timeout=10, redirects_left=MAX_REDIRECTS):
    """Fetch a URL over HTTP. Returns (ok, content_or_error_message)."""

    # Add http:// if the user typed just "example.com"
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    parsed = urlparse(url)


    if not parsed.hostname:
        return False, "Invalid URL"

    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    try:
        if parsed.scheme == "https":
            conn = http.client.HTTPSConnection(
                parsed.hostname, parsed.port or 443, timeout=timeout,
                context=make_context(),
            )
        else:
            conn = http.client.HTTPConnection(
                parsed.hostname, parsed.port or 80, timeout=timeout
            )
        conn.request("GET", path, headers={"User-Agent": "OS-Proxy/1.0"})
        response = conn.getresponse()

        # Redirects (301, 302...): follow them, up to MAX_REDIRECTS times
        if response.status in (301, 302, 303, 307, 308):
            location = response.getheader("Location")
            conn.close()
            if not location:
                return False, "Redirect without a location"
            if redirects_left == 0:
                return False, "Too many redirects"
            new_url = urljoin(url, location)
            return fetch(new_url, timeout, redirects_left - 1)

        if response.status != 200:
            conn.close()
            return False, f"HTTP {response.status} {response.reason}"

        content_type = response.getheader("Content-Type", "")
        body = response.read()      # body only, headers already separated
        conn.close()

        text = body.decode("utf-8", errors="replace")

        # Link rewriting: only for HTML, using the FINAL url (after redirects)
        if "html" in content_type.lower():
            text = rewrite_links(text, url)

        return True, text

    except TimeoutError:
        return False, "Timeout: server took too long"
    except OSError as e:
        return False, f"Connection failed: {e}"