#!/usr/bin/env python3
"""Static server + one write endpoint, for the "edit → reload → look" loop.

    python3 serve.py <scene-dir> [port]

ES modules need http (file:// won't load them). Besides static files it accepts
`POST /save?name=x.png` and writes the body verbatim into <scene-dir>/out/ — so the
page can drop renders / params / GLB straight on disk, no download folder detour.
Binds 127.0.0.1 only.

Sends `Cache-Control: no-store` on everything: SimpleHTTPRequestHandler sends no
cache headers and Chrome heuristically caches ES modules — "I changed the code,
reloaded, the picture didn't change" then gets blamed on the wrong file.
"""
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5181
OUT = os.path.join(ROOT, "out")
SAFE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        path, _, query = self.path.partition("?")
        if path != "/save":
            self.send_error(404)
            return
        name = dict(kv.partition("=")[::2] for kv in query.split("&")).get("name", "")
        if not SAFE.match(name) or not name.endswith((".png", ".jpg", ".json", ".glb")):
            self.send_error(400, "bad name")
            return
        n = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(n)
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(data)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")
        sys.stderr.write(f"saved out/{name} ({len(data)} bytes)\n")
        sys.stderr.flush()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"serving {ROOT} at http://127.0.0.1:{PORT}  (POST /save → out/)", flush=True)
    srv.serve_forever()
