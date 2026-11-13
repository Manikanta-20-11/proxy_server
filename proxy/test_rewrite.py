from processor import rewrite_links

base = "http://example.com/docs/page.html"

cases = [
    ('<img src="/logo.png">',            '<img src="http://example.com/logo.png">'),
    ("<img src='pic.jpg'>",              "<img src='http://example.com/docs/pic.jpg'>"),
    ("<script src=/s.js></script>",      "<script src=http://example.com/s.js></script>"),
    ('<a href="//cdn.site.com/a.js">',   '<a href="http://cdn.site.com/a.js">'),
    ('<a href="http://other.com/x">',    '<a href="http://other.com/x">'),
    ('<a href="#top">',                  '<a href="#top">'),
    ('<a href="mailto:a@b.com">',        '<a href="mailto:a@b.com">'),
    ('<img src="data:image/png;base64,AAA">', '<img src="data:image/png;base64,AAA">'),
    ('<div data-src="/x.png">',          '<div data-src="/x.png">'),
]

for given, expected in cases:
    got = rewrite_links(given, base)
    print("PASS" if got == expected else "FAIL", "|", given, "->", got)