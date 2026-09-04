import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from runtime import log_line

BASE_DIR = Path(__file__).resolve().parents[2]
STATE_PATH = BASE_DIR / "data" / "fault_state.json"
LOG_PATH = BASE_DIR / "logs" / "payment.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _write_log(message: str):
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(log_line(message + "\n"))


def _read_fault_state():
    if not STATE_PATH.exists():
        STATE_PATH.write_text(json.dumps({"redis_down": False, "updated_at": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    with STATE_PATH.open("r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            return {"redis_down": False, "updated_at": datetime.now(timezone.utc).isoformat()}


def _redis_ready():
    state = _read_fault_state()
    if state.get("redis_down"):
        _write_log(f"[{datetime.now(timezone.utc).isoformat()}] Redis marked down in fault state; refusing payment operation.")
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    try:
        sock.connect(("127.0.0.1", 6380))
        sock.sendall(b"PING\r\n")
        response = sock.recv(1024).decode("utf-8", errors="ignore")
        sock.close()
        if response.startswith("+PONG"):
            return True
        return False
    except Exception as exc:
        _write_log(f"[{datetime.now(timezone.utc).isoformat()}] Redis connection failure: {exc}")
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


class PaymentHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "payment"}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/pay":
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

        if not _redis_ready():
            latency_ms = round((time.time() - start) * 1000, 2)
            _write_log(f"[{datetime.now(timezone.utc).isoformat()}] Payment failure: Redis unavailable; latency_ms={latency_ms}")
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "service": "payment",
                "error": "redis_connection_failure",
                "latency_ms": latency_ms
            }).encode("utf-8"))
            return

        latency_ms = round((time.time() - start) * 1000, 2)
        _write_log(f"[{datetime.now(timezone.utc).isoformat()}] Payment success: request_id={payload.get('request_id', 'unknown')}; latency_ms={latency_ms}")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "success",
            "service": "payment",
            "request_id": payload.get("request_id", "unknown"),
            "latency_ms": latency_ms
        }).encode("utf-8"))

    def log_message(self, format, *args):
        return


def run_server(host="127.0.0.1", port=8002):
    server = ThreadingHTTPServer((host, port), PaymentHandler)
    _write_log(f"[{datetime.now(timezone.utc).isoformat()}] Payment service started on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
