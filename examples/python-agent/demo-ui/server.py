from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


STATIC_ROOT = Path(__file__).parent / "static"
MAX_REQUEST_BYTES = 1_000_000


class DemoHandler(BaseHTTPRequestHandler):
    agent_url = "http://127.0.0.1:8088"

    def do_GET(self) -> None:
        if self.path == "/api/readiness":
            self._proxy("GET", "/readiness")
            return

        requested_path = "/index.html" if self.path == "/" else self.path.split("?", 1)[0]
        file_path = (STATIC_ROOT / requested_path.lstrip("/")).resolve()
        if STATIC_ROOT.resolve() not in file_path.parents or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        if self.path != "/api/responses":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request size."})
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be valid JSON."})
            return

        payload["stream"] = False
        payload["store"] = False
        self._proxy("POST", "/responses", json.dumps(payload).encode("utf-8"))

    def _proxy(self, method: str, path: str, body: bytes | None = None) -> None:
        request = Request(
            f"{self.agent_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=120) as response:
                self._relay(response.status, response.read(), response.headers.get("Content-Type"))
        except HTTPError as error:
            self._relay(error.code, error.read(), error.headers.get("Content-Type"))
        except (TimeoutError, URLError) as error:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "error": (
                        "The local agent is unavailable. Start main.py on port 8088, then retry. "
                        f"Details: {error.reason if isinstance(error, URLError) else error}"
                    )
                },
            )

    def _relay(self, status: int, content: bytes, content_type: str | None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type or "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: int, payload: dict[str, str]) -> None:
        content = json.dumps(payload).encode("utf-8")
        self._relay(status, content, "application/json")

    def log_message(self, format: str, *args: object) -> None:
        print(f"[demo-ui] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Citadel Toolbox browser demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8090, type=int)
    parser.add_argument("--agent-url", default="http://127.0.0.1:8088")
    args = parser.parse_args()

    DemoHandler.agent_url = args.agent_url.rstrip("/")
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"Citadel Toolbox demo: http://{args.host}:{args.port}")
    print(f"Proxying agent requests to: {DemoHandler.agent_url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()