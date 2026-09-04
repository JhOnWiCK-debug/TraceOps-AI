import json
from pathlib import Path

from lab.retrieval.ingestion import EvidenceIngestion
from lab.retrieval.evaluate import run_evaluation
from lab.retrieval.evaluate import evaluate_root_cause
from lab.retrieval.reasoning import RootCauseEngine
from lab.retrieval.search import RetrievalEngine
from lab.retrieval.store import EvidenceStore

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "evidence" / "incident_001.db"


def test_ingestion_creates_records():
    ingestion = EvidenceIngestion(str(BASE_DIR))
    records = ingestion.ingest()
    assert records, "ingestion should produce evidence records"
    assert any(r.incident_id == "INC-001" for r in records)


def test_metadata_retrieval_keeps_incident_scope():
    ingestion = EvidenceIngestion(str(BASE_DIR))
    records = ingestion.ingest()
    rows = [
        {
            "evidence_id": r.evidence_id,
            "incident_id": r.incident_id,
            "timestamp": r.timestamp,
            "service": r.service,
            "source_type": r.source_type,
            "source": r.source,
            "event_type": r.event_type,
            "message": r.message,
            "severity": r.severity,
            "raw_source_path": r.raw_source_path,
            "normalized_text": r.normalized_text,
        }
        for r in records
    ]
    store = EvidenceStore(str(DB_PATH))
    store.insert_many(rows)
    engine = RetrievalEngine(store.fetch_all())
    result = engine.metadata_filter("INC-001", limit=5)
    store.close()
    assert result, "metadata retrieval should return evidence"
    assert all(item["incident_id"] == "INC-001" for item in result)


def test_combined_retrieval_returns_relevant_rows():
    ingestion = EvidenceIngestion(str(BASE_DIR))
    records = ingestion.ingest()
    rows = [
        {
            "evidence_id": r.evidence_id,
            "incident_id": r.incident_id,
            "timestamp": r.timestamp,
            "service": r.service,
            "source_type": r.source_type,
            "source": r.source,
            "event_type": r.event_type,
            "message": r.message,
            "severity": r.severity,
            "raw_source_path": r.raw_source_path,
            "normalized_text": r.normalized_text,
        }
        for r in records
    ]
    store = EvidenceStore(str(DB_PATH))
    store.insert_many(rows)
    engine = RetrievalEngine(store.fetch_all())
    result = engine.combined_retrieval("What caused INC-001?", "INC-001", limit=5)
    store.close()
    assert result, "combined retrieval should return evidence"
    assert all("evidence_id" in item for item in result)
    assert all("relevance_score" in item for item in result)


def test_older_run_cannot_appear_in_current_retrieval(tmp_path):
    logs_dir = tmp_path / "logs"
    incidents_dir = tmp_path / "data" / "incidents"
    logs_dir.mkdir(parents=True)
    incidents_dir.mkdir(parents=True)
    (incidents_dir / "incident_001.json").write_text(json.dumps({"incident_id": "INC-001"}), encoding="utf-8")
    (logs_dir / "fault_injector.log").write_text(
        "[2026-09-03T12:00:00+00:00] run_id=RUN-OLD; incident_id=INC-001; fault_state={'redis_down': True}\n"
        "[2026-09-03T12:01:00+00:00] run_id=RUN-CURRENT; incident_id=INC-001; fault_state={'redis_down': True}\n",
        encoding="utf-8",
    )

    records = EvidenceIngestion(str(tmp_path)).ingest(incident_id="INC-001", run_id="RUN-CURRENT")
    store = EvidenceStore(str(tmp_path / "evidence.db"))
    store.insert_many([record.__dict__ for record in records])
    current = store.fetch_all("INC-001", "RUN-CURRENT")
    engine = RetrievalEngine(current)
    result = engine.metadata_filter("INC-001", limit=5)
    store.close()

    assert len(records) == 1
    assert records[0].run_id == "RUN-CURRENT"
    assert all(item["run_id"] == "RUN-CURRENT" for item in result)
    assert all(item["evidence_id"] != "EVID-INC-001-FAULT-001" for item in result)


def _evaluation_file(tmp_path):
    payload = {
        "root_cause": "Redis connection failure",
        "affected_services": ["Payment Service", "Checkout Service"],
        "ground_truth": {
            "evaluation": {
                "required_categories": ["ROOT_CAUSE", "PAYMENT_IMPACT", "CHECKOUT_IMPACT", "TEMPORAL_CHAIN"],
                "categories": {
                    "ROOT_CAUSE": {"match": {"service": "Redis", "message_contains_any": ["redis_down=True"]}},
                    "PAYMENT_IMPACT": {"match": {"service": "Payment Service", "message_contains_any": ["Redis unavailable"]}},
                    "CHECKOUT_IMPACT": {"match": {"service": "Checkout Service", "message_contains_any": ["HTTP 503"]}},
                    "TEMPORAL_CHAIN": {"requires_categories": ["ROOT_CAUSE", "PAYMENT_IMPACT", "CHECKOUT_IMPACT"]},
                },
            }
        }
    }
    path = tmp_path / "incident.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _row(evidence_id, service, timestamp, message, run_id="RUN-CURRENT"):
    return {
        "evidence_id": evidence_id,
        "incident_id": "INC-001",
        "run_id": run_id,
        "timestamp": timestamp,
        "service": service,
        "source_type": "test",
        "event_type": "test",
        "message": message,
        "severity": "critical",
    }


def test_category_matching_and_successful_complete_coverage(tmp_path):
    rows = [
        _row("root", "Redis", "2026-09-03T12:00:00+00:00", "redis_down=True"),
        _row("payment", "Payment Service", "2026-09-03T12:01:00+00:00", "Redis unavailable"),
        _row("checkout", "Checkout Service", "2026-09-03T12:02:00+00:00", "HTTP 503"),
    ]
    result = run_evaluation(rows, _evaluation_file(tmp_path), "INC-001", "RUN-CURRENT")
    assert result["category_recall_at_3"] == 1.0
    assert result["category_recall_at_5"] == 1.0
    assert result["temporal_chain_valid_at_3"] is True
    assert result["temporal_chain_valid_at_5"] is True


def test_repeated_evidence_does_not_increase_category_coverage(tmp_path):
    rows = [_row(str(index), "Redis", f"2026-09-03T12:0{index}:00+00:00", "redis_down=True") for index in range(1, 4)]
    result = run_evaluation(rows, _evaluation_file(tmp_path), "INC-001", "RUN-CURRENT")
    assert result["category_recall_at_3"] == 0.25


def test_category_evaluation_enforces_run_isolation(tmp_path):
    rows = [_row("old", "Redis", "2026-09-03T12:00:00+00:00", "redis_down=True", "RUN-OLD")]
    result = run_evaluation(rows, _evaluation_file(tmp_path), "INC-001", "RUN-CURRENT")
    assert result["category_recall_at_3"] == 0.0
    assert result["precision_at_5"] == 0.0


def test_temporal_chain_requires_timestamp_order(tmp_path):
    rows = [
        _row("payment", "Payment Service", "2026-09-03T12:01:00+00:00", "Redis unavailable"),
        _row("root", "Redis", "2026-09-03T12:02:00+00:00", "redis_down=True"),
        _row("checkout", "Checkout Service", "2026-09-03T12:03:00+00:00", "HTTP 503"),
    ]
    result = run_evaluation(rows, _evaluation_file(tmp_path), "INC-001", "RUN-CURRENT")
    assert result["category_recall_at_3"] == 0.75
    assert result["temporal_chain_valid_at_3"] is False


def test_missing_category_reduces_category_recall(tmp_path):
    rows = [
        _row("root", "Redis", "2026-09-03T12:00:00+00:00", "redis_down=True"),
        _row("payment", "Payment Service", "2026-09-03T12:01:00+00:00", "Redis unavailable"),
    ]
    result = run_evaluation(rows, _evaluation_file(tmp_path), "INC-001", "RUN-CURRENT")
    assert result["category_recall_at_5"] == 0.5
    assert result["temporal_chain_valid_at_5"] is False


def _reasoning_rows(run_id="RUN-CURRENT"):
    rows = [
        _row("root", "Redis", "2026-09-03T12:00:00+00:00", "redis_down=True", run_id),
        _row("payment", "Payment Service", "2026-09-03T12:01:00+00:00", "Redis unavailable", run_id),
        _row("checkout", "Checkout Service", "2026-09-03T12:02:00+00:00", "HTTP 503", run_id),
    ]
    rows[0]["source_type"] = "fault_injector"
    return rows


def test_deterministic_root_cause_result_and_citations(tmp_path):
    rows = _reasoning_rows()
    result = RootCauseEngine(rows, "INC-001", "RUN-CURRENT").analyze()
    metrics = evaluate_root_cause(result, rows, _evaluation_file(tmp_path))
    assert result["root_cause"] == "Redis connection failure"
    assert result["affected_services"] == ["Checkout Service", "Payment Service"]
    assert metrics["root_cause_top_1_accuracy"] is True
    assert metrics["root_cause_top_3_recall"] is True
    assert metrics["affected_service_precision"] == 1.0
    assert metrics["affected_service_recall"] == 1.0
    assert metrics["evidence_citation_validity"] == 1.0


def test_reasoning_abstains_without_sufficient_evidence():
    rows = [_row("payment", "Payment Service", "2026-09-03T12:01:00+00:00", "Redis unavailable")]
    result = RootCauseEngine(rows, "INC-001", "RUN-CURRENT").analyze()
    assert result["root_cause"] == "insufficient_evidence"
    assert result["confidence"] == "insufficient_evidence"
