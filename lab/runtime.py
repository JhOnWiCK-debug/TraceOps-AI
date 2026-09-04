import json
from pathlib import Path
from typing import Dict


CONTEXT_PATH = Path(__file__).resolve().parent / "data" / "run_context.json"


def read_run_context() -> Dict[str, str]:
    if not CONTEXT_PATH.exists():
        return {"incident_id": "INC-001", "run_id": "legacy"}
    with CONTEXT_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def log_line(message: str) -> str:
    context = read_run_context()
    run_id = context.get("run_id", "legacy")
    incident_id = context.get("incident_id", "INC-001")
    if message.startswith("["):
        closing_bracket = message.find("]")
        if closing_bracket >= 0:
            return f"{message[:closing_bracket + 1]} run_id={run_id}; incident_id={incident_id};{message[closing_bracket + 1:]}"
    return f"run_id={run_id}; incident_id={incident_id}; {message}"
