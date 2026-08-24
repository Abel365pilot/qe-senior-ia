"""Adaptador loopback: elimina parámetros OpenAI que Gemini rechaza."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

from provider_factory import ProviderSettings


UNSUPPORTED_GEMINI_FIELDS = frozenset({"frequency_penalty", "presence_penalty"})


def sanitize_payload(payload: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if key not in UNSUPPORTED_GEMINI_FIELDS}


def _handler(upstream_base: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:  # noqa: N802 - API de BaseHTTPRequestHandler
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                body = json.dumps(sanitize_payload(payload), ensure_ascii=False).encode("utf-8")
                headers = {
                    "Authorization": self.headers.get("Authorization", ""),
                    "Content-Type": "application/json",
                }
                request = urllib.request.Request(
                    upstream_base.rstrip("/") + self.path,
                    data=body,
                    headers=headers,
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=120) as response:
                        status = response.status
                        response_body = response.read()
                        content_type = response.headers.get("Content-Type", "application/json")
                except urllib.error.HTTPError as exc:
                    status = exc.code
                    response_body = exc.read()
                    content_type = exc.headers.get("Content-Type", "application/json")
            except Exception as exc:  # Respuesta local segura; nunca incluye headers/credenciales.
                status = 502
                response_body = json.dumps(
                    {"error": {"message": f"Compatibility proxy error: {type(exc).__name__}"}}
                ).encode("utf-8")
                content_type = "application/json"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


@contextmanager
def gemini_compatible_settings(settings: ProviderSettings) -> Iterator[ProviderSettings]:
    if settings.provider != "openai_compatible" or "generativelanguage.googleapis.com" not in str(
        settings.base_url
    ):
        yield settings
        return
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(str(settings.base_url)))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name="gemini-compat-proxy", daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield replace(settings, base_url=f"http://{host}:{port}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
