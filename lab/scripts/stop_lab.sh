#!/usr/bin/env bash
set -euo pipefail

for pid in $(ps -eo pid,cmd --no-headers | awk '/redis_mock.py|payment.app.py|checkout.app.py/ {print $1}'); do
  kill "$pid" 2>/dev/null || true
done

python - <<'PY'
from pathlib import Path
import json
state = {"redis_down": False, "updated_at": "2026-09-03T00:00:00Z"}
root = Path(__file__).resolve().parents[1]
(root / "data" / "fault_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
print("Lab stopped and fault state reset.")
PY
