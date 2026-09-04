import json
import os
import signal
import subprocess
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
RUN_CONTEXT_PATH = DATA_DIR / "run_context.json"


def start_process(script_path: str, log_path: str):
    with LOG_DIR.joinpath(log_path).open("a", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=log_handle,
            stderr=log_handle,
            cwd=str(BASE_DIR),
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    return proc


def main():
    run_context = {
        "incident_id": "INC-001",
        "run_id": f"RUN-{uuid.uuid4().hex[:12].upper()}",
    }
    RUN_CONTEXT_PATH.write_text(json.dumps(run_context, indent=2), encoding="utf-8")
    redis_proc = start_process(str(BASE_DIR / "services" / "redis" / "redis_mock.py"), "redis_mock.out")
    payment_proc = start_process(str(BASE_DIR / "services" / "payment" / "app.py"), "payment.out")
    checkout_proc = start_process(str(BASE_DIR / "services" / "checkout" / "app.py"), "checkout.out")

    state = {
        **run_context,
        "redis": {"pid": redis_proc.pid},
        "payment": {"pid": payment_proc.pid},
        "checkout": {"pid": checkout_proc.pid},
        "updated_at": None,
    }
    (DATA_DIR / "lab_processes.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("Lab started.")
    print(f"Redis PID: {redis_proc.pid}")
    print(f"Payment PID: {payment_proc.pid}")
    print(f"Checkout PID: {checkout_proc.pid}")
    print("Use: python lab/scripts/generate_requests.py --count 30 --interval 0.5")
    print("Use: python lab/scripts/fault_injector.py --action fail")
    print("Use: python lab/scripts/fault_injector.py --action recover")


if __name__ == "__main__":
    main()
