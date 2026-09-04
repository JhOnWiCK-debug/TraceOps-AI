import json
import os
import socketserver
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from runtime import log_line

BASE_DIR = Path(__file__).resolve().parents[2]
STATE_PATH = BASE_DIR / "data" / "fault_state.json"
LOG_PATH = BASE_DIR / "logs" / "redis.log"

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _write_log(message: str):
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(log_line(message + "\n"))


def _read_fault_state():
    if not STATE_PATH.exists():
        STATE_PATH.write_text(json.dumps({"redis_down": False, "updated_at": "1970-01-01T00:00:00Z"}), encoding="utf-8")
    with STATE_PATH.open("r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            return {"redis_down": False, "updated_at": "1970-01-01T00:00:00Z"}


class RedisMockHandler(socketserver.BaseRequestHandler):
    def handle(self):
        state = _read_fault_state()
        if state.get("redis_down"):
            _write_log("[REDIS_MOCK] Redis is intentionally down; closing connection.")
            self.request.close()
            return

        data = self.request.recv(4096)
        command = data.decode("utf-8", errors="ignore").strip()
        _write_log(f"[REDIS_MOCK] Received command: {command}")

        if command.upper() == "PING":
            self.request.sendall(b"+PONG\r\n")
        else:
            self.request.sendall(b"-ERR unsupported command\r\n")


class ThreadedRedisServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def main():
    host = "127.0.0.1"
    port = 6380
    _write_log("[REDIS_MOCK] Starting mock Redis on 127.0.0.1:6380")
    server = ThreadedRedisServer((host, port), RedisMockHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    _write_log("[REDIS_MOCK] Redis mock is ready.")
    server_thread.join()


if __name__ == "__main__":
    main()
