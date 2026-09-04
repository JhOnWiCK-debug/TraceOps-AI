import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion import EvidenceIngestion
from evaluate import evaluate_root_cause, run_evaluation
from reasoning import RootCauseEngine
from runtime import read_run_context
from search import RetrievalEngine
from store import EvidenceStore

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "evidence" / "incident_001.db"


def main():
    ingestion = EvidenceIngestion(str(BASE_DIR))
    records = ingestion.ingest()
    rows = [r.__dict__ for r in records]

    store = EvidenceStore(str(DB_PATH))
    store.insert_many(rows)
    context = read_run_context()
    stored = store.fetch_all(context["incident_id"], context["run_id"])
    engine = RetrievalEngine(stored)

    query = "What caused INC-001?"
    keyword_results = engine.keyword_bm25(query, limit=5)
    metadata_results = engine.metadata_filter("INC-001", limit=5)
    combined_results = engine.combined_retrieval(query, "INC-001", limit=5)
    final_result = RootCauseEngine(combined_results, context["incident_id"], context["run_id"]).analyze()
    root_cause_metrics = evaluate_root_cause(final_result, stored, str(BASE_DIR / "data" / "incidents" / "incident_001.json"))
    metrics = {
        name: run_evaluation(results, str(BASE_DIR / "data" / "incidents" / "incident_001.json"), context["incident_id"], context["run_id"])
        for name, results in {
            "KEYWORD": keyword_results,
            "METADATA": metadata_results,
            "COMBINED": combined_results,
        }.items()
    }
    print("CATEGORY_EVALUATION")
    for name, result in metrics.items():
        print(name, result)
    print("ROOT_CAUSE_EVALUATION")
    print(root_cause_metrics)
    print("FINAL_RESULT")
    print(json.dumps(final_result, indent=2))

    print("KEYWORD")
    for row in keyword_results:
        print({
            "evidence_id": row["evidence_id"],
            "timestamp": row["timestamp"],
            "service": row["service"],
            "source_type": row["source_type"],
            "event_type": row["event_type"],
            "message": row["message"],
            "severity": row["severity"],
            "relevance_score": row["relevance_score"],
        })

    print("METADATA")
    for row in metadata_results:
        print({
            "evidence_id": row["evidence_id"],
            "timestamp": row["timestamp"],
            "service": row["service"],
            "source_type": row["source_type"],
            "event_type": row["event_type"],
            "message": row["message"],
            "severity": row["severity"],
            "relevance_score": row["relevance_score"],
        })

    print("COMBINED")
    for row in combined_results:
        print({
            "evidence_id": row["evidence_id"],
            "timestamp": row["timestamp"],
            "service": row["service"],
            "source_type": row["source_type"],
            "event_type": row["event_type"],
            "message": row["message"],
            "severity": row["severity"],
            "relevance_score": row["relevance_score"],
        })

    store.close()


if __name__ == "__main__":
    main()
