import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
INCIDENT_PATH = DATA_DIR / "incidents" / "incident_001.json"


def _write_default_incident():
    if not INCIDENT_PATH.parent.exists():
        INCIDENT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "incident_id": "INC-001",
        "title": "Redis connection failure during checkout",
        "start_time": "2026-09-03T12:00:00Z",
        "end_time": "2026-09-03T12:03:45Z",
        "root_cause": "Redis connection failure",
        "affected_services": ["Payment Service", "Checkout Service"],
        "remediation": "Restore Redis connectivity and retry the requests.",
        "status": "resolved",
        "environment": "lab-dev",
        "evidence": [
            "Redis connection refused",
            "Payment latency spike",
            "Payment service 503 responses",
            "Checkout downstream 5xx responses"
        ],
        "timeline": [
            "Redis connection failure starts",
            "Payment latency increases",
            "Payment service begins failing",
            "Checkout begins returning errors",
            "Redis recovered and system restored"
        ],
        "ground_truth": {
            "fault_type": "redis_connection_failure",
            "true_failure_mode": "Redis connection failure",
            "expected_evidence": [
                "Redis connection errors",
                "Payment latency increase",
                "Payment failures",
                "Checkout 5xx/errors"
            ],
            "expected_order": [
                "Redis connection failure",
                "Payment latency increase",
                "Payment service errors",
                "Checkout errors"
            ]
        }
    }
    INCIDENT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_incident_file_exists():
    _write_default_incident()
    assert INCIDENT_PATH.exists(), "incident file should exist"


def test_incident_has_expected_root_cause():
    _write_default_incident()
    payload = json.loads(INCIDENT_PATH.read_text(encoding="utf-8"))
    assert payload["root_cause"] == "Redis connection failure"
    assert "Payment Service" in payload["affected_services"]
    assert "Checkout Service" in payload["affected_services"]


def test_incident_has_expected_timeline_order():
    _write_default_incident()
    payload = json.loads(INCIDENT_PATH.read_text(encoding="utf-8"))
    assert payload["ground_truth"]["expected_order"][0] == "Redis connection failure"
    assert payload["ground_truth"]["expected_order"][-1] == "Checkout errors"
