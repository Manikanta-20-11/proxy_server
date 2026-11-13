from processor import fetch

tests = [
    "http://example.com",
    "example.com",
    "http://example.com/nothing-here",
    "https://example.com",
    "http://thisdomaindoesnotexist12345.com",
    "",
    "http://neverssl.com",
    "http://google.com",
    "https://example.com",
    "https://www.wikipedia.org",
    "https://expired.badssl.com",
]

for t in tests:
    ok, result = fetch(t)
    preview = result[:60].replace("\n", " ")
    print(f"{t!r:45} -> ok={ok} | {preview}")