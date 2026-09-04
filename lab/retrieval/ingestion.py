import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from lab.runtime import read_run_context
except ModuleNotFoundError:
    from runtime import read_run_context


@dataclass
class EvidenceRecord:
    evidence_id: str
    incident_id: str
    run_id: str
    timestamp: str
    service: str
    source_type: str
    source: str
    event_type: str
    message: str
    severity: str
    raw_source_path: str
    normalized_text: str


class EvidenceIngestion:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.incident_path = self.base_dir / "data" / "incidents" / "incident_001.json"
        self.logs_dir = self.base_dir / "logs"
        self.evidence_dir = self.base_dir / "data" / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def _parse_iso_timestamp(self, raw: str) -> str:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.astimezone().isoformat()
        except Exception:
            return raw

    def _slugify(self, text: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
        return cleaned or "event"

    def _normalize_message(self, message: str) -> str:
        return re.sub(r"\s+", " ", message).strip()

    def _extract_incident_metadata(self) -> Dict[str, Any]:
        if not self.incident_path.exists():
            raise FileNotFoundError(f"Incident file not found: {self.incident_path}")
        with self.incident_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _read_log_lines(self, file_path: Path) -> List[str]:
        if not file_path.exists():
            return []
        return file_path.read_text(encoding="utf-8").splitlines()

    def _parse_fault_injector_log(self, log_lines: List[str], incident_id: str, run_id: str) -> List[EvidenceRecord]:
        records: List[EvidenceRecord] = []
        for idx, line in enumerate(log_lines, start=1):
            if not line.strip() or self._extract_run_id(line) != run_id:
                continue
            evidence_id = f"EVID-{incident_id}-FAULT-{idx:03d}"
            timestamp = self._extract_timestamp_from_text(line)
            message = self._normalize_message(line)
            records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    incident_id=incident_id,
                    run_id=run_id,
                    timestamp=timestamp,
                    service="Redis",
                    source_type="fault_injector",
                    source="fault_injector.log",
                    event_type="fault_state",
                    message=message,
                    severity="critical",
                    raw_source_path=str(self.logs_dir / "fault_injector.log"),
                    normalized_text=self._normalize_message(message),
                )
            )
        return records

    def _parse_payment_log(self, log_lines: List[str], incident_id: str, run_id: str) -> List[EvidenceRecord]:
        records: List[EvidenceRecord] = []
        for idx, line in enumerate(log_lines, start=1):
            if not line.strip() or self._extract_run_id(line) != run_id:
                continue
            evidence_id = f"EVID-{incident_id}-PAY-{idx:03d}"
            timestamp = self._extract_timestamp_from_text(line)
            message = self._normalize_message(line)
            event_type = "payment_failure" if "Payment failure" in line else "payment_success"
            severity = "critical" if "Payment failure" in line else "info"
            records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    incident_id=incident_id,
                    run_id=run_id,
                    timestamp=timestamp,
                    service="Payment Service",
                    source_type="payment_log",
                    source="payment.log",
                    event_type=event_type,
                    message=message,
                    severity=severity,
                    raw_source_path=str(self.logs_dir / "payment.log"),
                    normalized_text=self._normalize_message(message),
                )
            )
        return records

    def _parse_checkout_log(self, log_lines: List[str], incident_id: str, run_id: str) -> List[EvidenceRecord]:
        records: List[EvidenceRecord] = []
        for idx, line in enumerate(log_lines, start=1):
            if not line.strip() or self._extract_run_id(line) != run_id:
                continue
            evidence_id = f"EVID-{incident_id}-CHECKOUT-{idx:03d}"
            timestamp = self._extract_timestamp_from_text(line)
            message = self._normalize_message(line)
            event_type = "checkout_failure" if "Checkout request failed" in line else "checkout_success"
            severity = "critical" if "Checkout request failed" in line else "info"
            records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    incident_id=incident_id,
                    run_id=run_id,
                    timestamp=timestamp,
                    service="Checkout Service",
                    source_type="checkout_log",
                    source="checkout.log",
                    event_type=event_type,
                    message=message,
                    severity=severity,
                    raw_source_path=str(self.logs_dir / "checkout.log"),
                    normalized_text=self._normalize_message(message),
                )
            )
        return records

    def _extract_timestamp_from_text(self, line: str) -> str:
        match = re.search(r"\[(.*?)\]", line)
        if match:
            return self._parse_iso_timestamp(match.group(1))
        return "1970-01-01T00:00:00Z"

    def _extract_run_id(self, line: str) -> str:
        match = re.search(r"run_id=([^;\s]+)", line)
        return match.group(1) if match else "legacy"

    def ingest(self, incident_id: str = None, run_id: str = None) -> List[EvidenceRecord]:
        incident_meta = self._extract_incident_metadata()
        context = read_run_context()
        incident_id = incident_id or context.get("incident_id", incident_meta.get("incident_id", "INC-001"))
        run_id = run_id or context.get("run_id", "legacy")
        evidence: List[EvidenceRecord] = []

        evidence.extend(self._parse_fault_injector_log(self._read_log_lines(self.logs_dir / "fault_injector.log"), incident_id, run_id))
        evidence.extend(self._parse_payment_log(self._read_log_lines(self.logs_dir / "payment.log"), incident_id, run_id))
        evidence.extend(self._parse_checkout_log(self._read_log_lines(self.logs_dir / "checkout.log"), incident_id, run_id))
        evidence.extend(self._parse_redis_log(self._read_log_lines(self.logs_dir / "redis.log"), incident_id, run_id))

        self._write_evidence_records(evidence)
        return evidence

    def _parse_redis_log(self, log_lines: List[str], incident_id: str, run_id: str) -> List[EvidenceRecord]:
        records: List[EvidenceRecord] = []
        for idx, line in enumerate(log_lines, start=1):
            if not line.strip() or self._extract_run_id(line) != run_id:
                continue
            evidence_id = f"EVID-{incident_id}-REDIS-{idx:03d}"
            timestamp = self._extract_timestamp_from_text(line) if "[" in line else "1970-01-01T00:00:00Z"
            message = self._normalize_message(line)
            event_type = "redis_command" if "Received command" in line else "redis_startup"
            severity = "info" if "Received command" in line or "ready" in line.lower() else "warning"
            records.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    incident_id=incident_id,
                    run_id=run_id,
                    timestamp=timestamp,
                    service="Redis",
                    source_type="redis_log",
                    source="redis.log",
                    event_type=event_type,
                    message=message,
                    severity=severity,
                    raw_source_path=str(self.logs_dir / "redis.log"),
                    normalized_text=self._normalize_message(message),
                )
            )
        return records

    def _write_evidence_records(self, evidence: List[EvidenceRecord]):
        output_path = self.evidence_dir / "incident_001_evidence.json"
        payload = [
            {
                "evidence_id": item.evidence_id,
                "incident_id": item.incident_id,
                "run_id": item.run_id,
                "timestamp": item.timestamp,
                "service": item.service,
                "source_type": item.source_type,
                "source": item.source,
                "event_type": item.event_type,
                "message": item.message,
                "severity": item.severity,
                "raw_source_path": item.raw_source_path,
                "normalized_text": item.normalized_text,
            }
            for item in evidence
        ]
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
