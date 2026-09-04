from datetime import datetime
from typing import Any, Dict, List


class RootCauseEngine:
    HYPOTHESES = [
        "Redis connection failure",
        "Payment Service failure",
        "Checkout Service failure",
    ]

    def __init__(self, evidence_rows: List[Dict[str, Any]], incident_id: str, run_id: str):
        self.evidence_rows = [
            row for row in evidence_rows
            if row.get("incident_id") == incident_id and row.get("run_id") == run_id
        ]
        self.incident_id = incident_id
        self.run_id = run_id

    def _kind(self, row: Dict[str, Any]) -> str:
        message = row.get("message", "")
        if row.get("service") == "Redis" and ("redis_down': True" in message or "redis_down=True" in message or "Redis connection failure" in message):
            return "root"
        if row.get("service") == "Payment Service" and ("Redis unavailable" in message or "refusing payment operation" in message):
            return "payment"
        if row.get("service") == "Checkout Service" and ("HTTP Error 503" in message or "HTTP 503" in message or "payment_downstream_failure" in message):
            return "checkout"
        return "other"

    def _timestamp(self, row: Dict[str, Any]) -> datetime:
        return datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))

    def analyze(self) -> Dict[str, Any]:
        evidence_by_kind = {kind: [row for row in self.evidence_rows if self._kind(row) == kind] for kind in ("root", "payment", "checkout")}
        chain_valid = bool(
            evidence_by_kind["root"] and evidence_by_kind["payment"] and evidence_by_kind["checkout"]
            and any(
                self._timestamp(root) < self._timestamp(payment) < self._timestamp(checkout)
                for root in evidence_by_kind["root"]
                for payment in evidence_by_kind["payment"]
                for checkout in evidence_by_kind["checkout"]
            )
        )
        scores = {
            "Redis connection failure": 6 * bool(evidence_by_kind["root"]) + 2 * bool(evidence_by_kind["payment"]) + 2 * bool(evidence_by_kind["checkout"]) + 2 * chain_valid,
            "Payment Service failure": 4 * bool(evidence_by_kind["payment"]) + 1 * bool(evidence_by_kind["checkout"]) - 4 * bool(evidence_by_kind["root"]),
            "Checkout Service failure": 4 * bool(evidence_by_kind["checkout"]) - 3 * bool(evidence_by_kind["root"]) - 2 * bool(evidence_by_kind["payment"]),
        }
        maximum = max(max(scores.values()), 1)
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        normalized = {name: round(max(score, 0) / maximum, 4) for name, score in scores.items()}
        top_name, top_raw = ranked[0]
        second_raw = ranked[1][1]
        sufficient = top_raw >= 6 and (top_raw - second_raw) / maximum >= 0.15
        root_cause = top_name if sufficient else "insufficient_evidence"
        hypotheses = []
        for name, _ in ranked:
            if name == "Redis connection failure":
                supporting = evidence_by_kind["root"] + evidence_by_kind["payment"] + evidence_by_kind["checkout"]
                contradictory = []
            elif name == "Payment Service failure":
                supporting = evidence_by_kind["payment"] + evidence_by_kind["checkout"]
                contradictory = evidence_by_kind["root"]
            else:
                supporting = evidence_by_kind["checkout"]
                contradictory = evidence_by_kind["root"] + evidence_by_kind["payment"]
            hypotheses.append({
                "name": name,
                "score": normalized[name],
                "supporting_evidence": [row["evidence_id"] for row in supporting],
                "contradictory_evidence": [row["evidence_id"] for row in contradictory],
            })

        ordered = sorted(self.evidence_rows, key=self._timestamp)
        timeline = [
            {"timestamp": row["timestamp"], "event": self._kind(row).upper(), "evidence_id": row["evidence_id"]}
            for row in ordered
            if self._kind(row) in {"root", "payment", "checkout"}
        ]
        affected_services = sorted({row["service"] for kind in ("payment", "checkout") for row in evidence_by_kind[kind]})
        citations = [row["evidence_id"] for row in evidence_by_kind["root"] + evidence_by_kind["payment"] + evidence_by_kind["checkout"]]
        return {
            "incident_id": self.incident_id,
            "run_id": self.run_id,
            "root_cause": root_cause,
            "confidence": "high" if sufficient else "insufficient_evidence",
            "hypotheses": hypotheses,
            "affected_services": affected_services,
            "timeline": timeline,
            "recommended_action": "Restore Redis connectivity and verify Payment/Checkout recovery.",
            "citations": citations,
        }
