"""Vývojový server bez cache: python data/serve.py  ->  http://localhost:8765"""
import http.server, os, functools

class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(NoCache, directory=root)).serve_forever()
