import json
from datetime import datetime
from typing import Any, Dict, List


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def compute_metrics(retrieved_ids: List[str], gold_ids: List[str]) -> Dict[str, float]:
    relevant_in_top = [item for item in retrieved_ids if item in gold_ids]
    precision = len(relevant_in_top) / len(retrieved_ids) if retrieved_ids else 0.0
    recall = len(relevant_in_top) / len(gold_ids) if gold_ids else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
    }


def _matches(row: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    for field in ("incident_id", "run_id", "service", "source_type", "event_type", "severity"):
        if field in rule and row.get(field) != rule[field]:
            return False
    message = row.get("message", "")
    return all(term in message for term in rule.get("message_contains_all", [])) and (
        not rule.get("message_contains_any")
        or any(term in message for term in rule["message_contains_any"])
    )


def _has_temporal_chain(rows: List[Dict[str, Any]], categories: Dict[str, Dict[str, Any]]) -> bool:
    matched = {
        category: sorted(
            datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            for row in rows
            if _matches(row, categories[category]["match"])
        )
        for category in ("ROOT_CAUSE", "PAYMENT_IMPACT", "CHECKOUT_IMPACT")
    }
    if not all(matched.values()):
        return False
    return any(
        root < payment < checkout
        for root in matched["ROOT_CAUSE"]
        for payment in matched["PAYMENT_IMPACT"]
        for checkout in matched["CHECKOUT_IMPACT"]
    )


def _category_coverage(rows: List[Dict[str, Any]], evaluation: Dict[str, Any]) -> Dict[str, bool]:
    categories = evaluation["categories"]
    coverage = {
        category: any(_matches(row, categories[category]["match"]) for row in rows)
        for category in evaluation["required_categories"]
        if category != "TEMPORAL_CHAIN"
    }
    coverage["TEMPORAL_CHAIN"] = _has_temporal_chain(rows, categories)
    return coverage


def run_evaluation(
    retrieval_results: List[Dict[str, Any]],
    incident_path: str,
    incident_id: str,
    run_id: str,
):
    incident = load_json(incident_path)
    evaluation = incident["ground_truth"]["evaluation"]
    scoped_results = [
        item for item in retrieval_results
        if item.get("incident_id") == incident_id and item.get("run_id") == run_id
    ]

    def metrics(limit: int) -> Dict[str, float]:
        rows = scoped_results[:limit]
        coverage = _category_coverage(rows, evaluation)
        covered = sum(coverage.values())
        required = len(evaluation["required_categories"])
        concrete_categories = [category for category in evaluation["required_categories"] if category != "TEMPORAL_CHAIN"]
        relevant_records = sum(
            any(_matches(row, evaluation["categories"][category]["match"]) for category in concrete_categories)
            for row in rows
        )
        return {
            "category_recall": round(covered / required if required else 0.0, 4),
            "temporal_chain_valid": coverage["TEMPORAL_CHAIN"],
            "precision": round(relevant_records / len(rows) if rows else 0.0, 4),
        }

    top3 = metrics(3)
    top5 = metrics(5)
    return {
        "category_recall_at_3": top3["category_recall"],
        "category_recall_at_5": top5["category_recall"],
        "temporal_chain_valid_at_3": top3["temporal_chain_valid"],
        "temporal_chain_valid_at_5": top5["temporal_chain_valid"],
        "precision_at_5": top5["precision"],
    }


def evaluate_root_cause(result: Dict[str, Any], evidence_rows: List[Dict[str, Any]], incident_path: str) -> Dict[str, Any]:
    incident = load_json(incident_path)
    expected_root = incident["root_cause"]
    expected_services = set(incident["affected_services"])
    predicted_services = set(result["affected_services"])
    valid_ids = {row["evidence_id"] for row in evidence_rows}
    citations = result.get("citations", [])
    valid_citations = [citation for citation in citations if citation in valid_ids]
    ranked_names = [hypothesis["name"] for hypothesis in result["hypotheses"]]
    return {
        "root_cause_top_1_accuracy": result["root_cause"] == expected_root,
        "root_cause_top_3_recall": expected_root in ranked_names[:3],
        "affected_service_precision": round(len(predicted_services & expected_services) / len(predicted_services) if predicted_services else 0.0, 4),
        "affected_service_recall": round(len(predicted_services & expected_services) / len(expected_services) if expected_services else 0.0, 4),
        "evidence_citation_validity": round(len(valid_citations) / len(citations) if citations else 0.0, 4),
    }
