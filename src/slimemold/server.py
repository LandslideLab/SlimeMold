"""Headless HTTP server exposing the JSON protocol.

The engine is a plain JSON service: POST a spec, get a result. The web testbed
talks to it through this interface in development (the Vite dev server proxies
``/api`` to it); on Vercel the same handlers are exposed as serverless
functions (see the ``api/`` directory).

Endpoints
---------
* ``GET  /api/health``                     -> {"status": "ok", "version": ...}
* ``POST /api/simulate``                   body: spec JSON   -> full result JSON
* ``POST /api/experiment``                 body: {mode: compare|scan, ...}
* ``POST /api/report``                     body: {spec, seed, note} -> ODD report text
* ``GET  /api/spec/example``               -> an example customer-service spec
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .experiments import compare, scan
from .protocol import run_command
from .report import engine_version


class _Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        return data

    def log_message(self, fmt, *args):  # quieter logs
        pass

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(200, {"status": "ok", "engine_version": engine_version()})
        elif path == "/api/spec/example":
            from .demo import EXAMPLE_SPEC

            self._json(200, EXAMPLE_SPEC)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/simulate":
                body = self._read_body()
                spec = body.get("spec")
                if not isinstance(spec, dict):
                    raise ValueError("body.spec must be an object")
                seed = body.get("seed")
                turns = body.get("turns")
                result = run_command(spec, seed=seed, turns=turns)
                self._json(200, result)
            elif path == "/api/experiment":
                body = self._read_body()
                mode = body.get("mode")
                if mode == "compare":
                    self._json(200, compare(
                        body["spec_a"], body["spec_b"],
                        metric=body.get("metric", "throughput"),
                        reps=body.get("reps", 8),
                        seed=body.get("seed", 42),
                        test=body.get("test", "mann_whitney"),
                        turns=body.get("turns"),
                    ).to_dict())
                elif mode == "scan":
                    self._json(200, scan(
                        body["spec"], body["parameter"], body.get("values", []),
                        metric=body.get("metric", "throughput"),
                        seed=body.get("seed", 42),
                        turns=body.get("turns"),
                        reps=body.get("reps", 1),
                    ).to_dict())
                else:
                    self._json(400, {"error": "mode must be compare or scan"})
            elif path == "/api/report":
                body = self._read_body()
                spec = body.get("spec")
                if not isinstance(spec, dict):
                    raise ValueError("body.spec must be an object")
                from .report import ODDReport

                report = ODDReport(spec, seed=body.get("seed"), note=body.get("note", ""))
                self._json(200, {"odd": report.render(), "engine_version": engine_version()})
            else:
                self._json(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": str(exc)})


def make_server(host: str = "127.0.0.1", port: int = 8642) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    return server


def serve(host: str = "127.0.0.1", port: int = 8642) -> None:
    server = make_server(host, port)
    print(f"SlimeMold engine listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
