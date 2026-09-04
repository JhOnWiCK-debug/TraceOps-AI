import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from runtime import log_line

BASE_DIR = Path(__file__).resolve().parents[2]
LOG_PATH = BASE_DIR / "logs" / "checkout.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _write_log(message: str):
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(log_line(message + "\n"))


def _call_payment(payload):
    request_data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:8002/pay",
        data=request_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


class CheckoutHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "checkout"}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/checkout":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        start = time.time()

        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            payload = {}

        request_id = payload.get("request_id", "unknown")

        try:
            status_code, payment_response = _call_payment(payload)
            latency_ms = round((time.time() - start) * 1000, 2)
            if status_code == 200:
                _write_log(f"[{datetime.now(timezone.utc).isoformat()}] Checkout success for request_id={request_id}; latency_ms={latency_ms}; payment_status={payment_response.get('status')}")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "service": "checkout",
                    "request_id": request_id,
                    "payment_status": payment_response.get("status"),
                    "latency_ms": latency_ms
                }).encode("utf-8"))
                return

            _write_log(f"[{datetime.now(timezone.utc).isoformat()}] Checkout downstream payment failure for request_id={request_id}; status_code={status_code}; latency_ms={latency_ms}")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "service": "checkout",
                "request_id": request_id,
                "error": "payment_downstream_failure",
                "latency_ms": latency_ms,
                "payment_response": payment_response
            }).encode("utf-8"))
            return
        except Exception as exc:
            latency_ms = round((time.time() - start) * 1000, 2)
            _write_log(f"[{datetime.now(timezone.utc).isoformat()}] Checkout request failed for request_id={request_id}; error={exc}; latency_ms={latency_ms}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "service": "checkout",
                "request_id": request_id,
                "error": str(exc),
                "latency_ms": latency_ms
            }).encode("utf-8"))

    def log_message(self, format, *args):
        return


def run_server(host="127.0.0.1", port=8001):
    server = ThreadingHTTPServer((host, port), CheckoutHandler)
    _write_log(f"[{datetime.now(timezone.utc).isoformat()}] Checkout service started on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
