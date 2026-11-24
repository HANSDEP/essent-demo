"""Essent-demo: serveert de demopagina en zet /nc/* door naar Neople Chat.

De inbox praat met de publieke chat-API van Neople Chat. Die staat geen CORS toe, dus de
browser vraagt het aan deze server en die stuurt het door. Starten: python3 server.py
en open http://localhost:8793
"""
import http.server
import os
import time
import urllib.error
import urllib.request

PORT = 8793
UPSTREAM = "https://chat.endpoints.neople-chat.cloud.goog"
ORIGIN = f"http://localhost:{PORT}"
HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def _proxy(self):
        url = UPSTREAM + self.path[len("/nc"):]
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {"Origin": ORIGIN, "Content-Type": self.headers.get("Content-Type", "application/json")}
        if self.headers.get("Authorization"):
            headers["Authorization"] = self.headers["Authorization"]
        # A GET is retried on a network hiccup; a POST only when it never reached the server (connect/TLS failed).
        status, data, ctype = 502, b'{"detail":"upstream onbereikbaar"}', "application/json"
        for attempt in range(3):
            req = urllib.request.Request(url, data=body, headers=headers, method=self.command)
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    status, data, ctype = r.status, r.read(), r.headers.get("Content-Type", "application/json")
                break
            except urllib.error.HTTPError as e:
                status, data, ctype = e.code, e.read(), e.headers.get("Content-Type", "application/json")
                break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                reason = getattr(e, "reason", e)
                never_sent = "handshake" in str(reason) or "refused" in str(reason) or "nodename" in str(reason)
                if self.command != "GET" and not never_sent:
                    break
                time.sleep(0.5 * (attempt + 1))
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/nc/"):
            return self._proxy()
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/nc/"):
            return self._proxy()
        self.send_error(404)

    def log_message(self, fmt, *args):
        if args and "/nc/" in str(args[0]):
            return
        super().log_message(fmt, *args)


if __name__ == "__main__":
    print(f"Essent-demo op {ORIGIN}")
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
