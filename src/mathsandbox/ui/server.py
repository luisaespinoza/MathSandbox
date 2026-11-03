"""Loopback-only workbench with locally served Plotly assets."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files
import json
import secrets
import webbrowser
from .workbench import Workbench


class WorkbenchServer(HTTPServer):
    def __init__(self, address):
        if address[0] != "127.0.0.1":
            raise ValueError("The workbench binds only to 127.0.0.1")
        super().__init__(address, Handler)
        self.workbench = Workbench()
        self.token = secrets.token_urlsafe(32)


class Handler(BaseHTTPRequestHandler):
    def send(self, content, content_type="application/json", status=200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def allowed(self):
        expected = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host") == expected

    def do_GET(self):
        if not self.allowed():
            self.send(json.dumps({"error": "Unexpected host"}), status=403)
            return
        if self.path == "/":
            page = files("mathsandbox.ui").joinpath("workbench.html").read_text(encoding="utf-8")
            self.send(page.replace("__TOKEN__", self.server.token), "text/html")
        elif self.path == "/geometry.js":
            self.send(files("mathsandbox.ui").joinpath("geometry.js").read_text(encoding="utf-8"), "application/javascript")
        elif self.path == "/plotly.js":
            from plotly.offline import get_plotlyjs
            self.send(get_plotlyjs(), "application/javascript")
        elif self.path == "/api/state":
            self.send(json.dumps(self.server.workbench.state()))
        elif self.path == "/api/export":
            self.send(self.server.workbench.export())
        else:
            self.send(json.dumps({"error": "Not found"}), status=404)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if (not self.allowed() or self.headers.get("X-MathSandbox-Token") != self.server.token
                or (origin and origin != f"http://127.0.0.1:{self.server.server_port}")):
            self.send(json.dumps({"error": "Invalid local session"}), status=403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2_000_000:
                raise ValueError("Request must be between 1 byte and 2 MB")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            workbench = self.server.workbench
            if self.path == "/api/define":
                result = workbench.apply(data["definitions"])
            elif self.path == "/api/domain":
                result = workbench.set_domain(data["name"], data["domain"])
            elif self.path == "/api/render":
                result = workbench.render(data)
            elif self.path == "/api/import":
                result = workbench.restore(data["project"])
            elif self.path == "/api/demo":
                candidate = Workbench()
                candidate.choose_example(data.get("example", "composition"))
                self.server.workbench = candidate
                result = candidate.state()
            else:
                self.send(json.dumps({"error": "Not found"}), status=404)
                return
            self.send(json.dumps(result, allow_nan=False))
        except (ValueError, TypeError, KeyError, SyntaxError, RecursionError, StopIteration) as error:
            self.send(json.dumps({"error": str(error) or type(error).__name__}), status=400)


def main():
    parser = argparse.ArgumentParser(description="MathSandbox local A3 workbench")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        import plotly  # noqa: F401
    except ImportError:
        parser.error("Install the workbench extra: python -m pip install -e '.[workbench,dev]'")
    with WorkbenchServer(("127.0.0.1", args.port)) as server:
        address = f"http://127.0.0.1:{server.server_port}"
        print(f"MathSandbox A3 running at {address} — Ctrl+C to stop", flush=True)
        if not args.no_browser:
            webbrowser.open(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
