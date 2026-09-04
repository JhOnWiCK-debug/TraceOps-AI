import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_PATH = BASE_DIR / "logs" / "request_generator.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _write_log(message: str):
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")


def _send_checkout_request(target_url: str, request_id: str):
    payload = {
        "request_id": request_id,
        "cart_total": 49.99,
        "currency": "USD",
        "items": ["book", "gift_card"],
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{target_url}/checkout",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            status = response.status
            result = json.loads(response.read().decode("utf-8"))
            _write_log(f"[{datetime.now(timezone.utc).isoformat()}] request_id={request_id}; status={status}; response={result}")
            return status, result
    except Exception as exc:
        _write_log(f"[{datetime.now(timezone.utc).isoformat()}] request_id={request_id}; exception={exc}")
        return None, {"error": str(exc)}


def run(target_url: str, count: int, interval_seconds: float):
    for idx in range(count):
        request_id = f"REQ-{idx:04d}"
        _send_checkout_request(target_url, request_id)
        if interval_seconds > 0:
            time.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description="Generate load against the checkout service.")
    parser.add_argument("--target", default="http://127.0.0.1:8001")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()

    run(args.target, args.count, args.interval)


if __name__ == "__main__":
    main()
