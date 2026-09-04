import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
STATE_PATH = BASE_DIR / "data" / "fault_state.json"


def _reset_state():
    payload = {"redis_down": False, "updated_at": "2026-09-03T00:00:00Z"}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload), encoding="utf-8")


def test_fault_state_can_be_set_to_down():
    _reset_state()
    subprocess.run([sys.executable, str(BASE_DIR / "scripts" / "fault_injector.py"), "--action", "fail"], check=True)
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    assert state["redis_down"] is True


def test_fault_state_can_be_reset():
    _reset_state()
    subprocess.run([sys.executable, str(BASE_DIR / "scripts" / "fault_injector.py"), "--action", "fail"], check=True)
    subprocess.run([sys.executable, str(BASE_DIR / "scripts" / "fault_injector.py"), "--action", "recover"], check=True)
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    assert state["redis_down"] is False
