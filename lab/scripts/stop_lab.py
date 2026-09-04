import json
import os
import signal
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
PROCESSES_PATH = DATA_DIR / "lab_processes.json"


def stop_processes():
    if PROCESSES_PATH.exists():
        data = json.loads(PROCESSES_PATH.read_text(encoding="utf-8"))
        for service in ["redis", "payment", "checkout"]:
            pid = data.get(service, {}).get("pid")
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
    else:
        print("No running lab processes recorded.")

    state = {"redis_down": False, "updated_at": "2026-09-03T00:00:00Z"}
    (DATA_DIR / "fault_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("Lab stopped and fault state reset.")


if __name__ == "__main__":
    stop_processes()
