import ssl, socket, certifi

ctx = ssl.create_default_context()
ctx.load_verify_locations(certifi.where())   # add certifi's list

with socket.create_connection(("example.com", 443), timeout=10) as s:
    try:
        with ctx.wrap_socket(s, server_hostname="example.com") as t:
            print("OK:", t.getpeercert()["issuer"])
    except ssl.SSLError as e:
        print("FAIL:", e)