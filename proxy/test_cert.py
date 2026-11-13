from processor import fetch

for url in ["https://expired.badssl.com", "https://self-signed.badssl.com", "https://wrong.host.badssl.com"]:
    ok, result = fetch(url, timeout=20)
    print(url, "->", ok, "|", result[:80])