import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import log_line

BASE_DIR = Path(__file__).resolve().parents[1]
STATE_PATH = BASE_DIR / "data" / "fault_state.json"
LOG_PATH = BASE_DIR / "logs" / "fault_injector.log"
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _read_state():
    if not STATE_PATH.exists():
        STATE_PATH.write_text(json.dumps({"redis_down": False, "updated_at": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    with STATE_PATH.open("r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            return {"redis_down": False, "updated_at": datetime.now(timezone.utc).isoformat()}


def _write_state(redis_down: bool):
    payload = {
        "redis_down": redis_down,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(log_line(f"[{datetime.now(timezone.utc).isoformat()}] fault_state={payload}\n"))


def main():
    parser = argparse.ArgumentParser(description="Toggle Redis lab fault state.")
    parser.add_argument("--action", choices=["fail", "recover"], required=True)
    args = parser.parse_args()

    if args.action == "fail":
        _write_state(True)
        print("Redis failure injected.")
    else:
        _write_state(False)
        print("Redis recovered.")


if __name__ == "__main__":
    main()
