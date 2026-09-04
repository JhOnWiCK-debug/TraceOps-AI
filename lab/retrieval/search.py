import math
import re
from collections import Counter
from typing import Any, Dict, List, Tuple


class RetrievalEngine:
    def __init__(self, evidence_rows: List[Dict[str, Any]]):
        self.evidence_rows = evidence_rows

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9_]+", text.lower())

    def _term_frequency(self, text: str) -> Counter:
        return Counter(self._tokenize(text))

    def keyword_bm25(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        tokens = self._tokenize(query)
        if not tokens:
            return []

        results: List[Dict[str, Any]] = []
        doc_freq = {}
        for row in self.evidence_rows:
            text = f"{row['service']} {row['source_type']} {row['event_type']} {row['message']} {row['normalized_text']}"
            terms = set(self._tokenize(text))
            for term in terms:
                doc_freq[term] = doc_freq.get(term, 0) + 1

        for row in self.evidence_rows:
            text = f"{row['service']} {row['source_type']} {row['event_type']} {row['message']} {row['normalized_text']}"
            tf = self._term_frequency(text)
            score = 0.0
            for token in tokens:
                if token not in tf:
                    continue
                tf_value = tf[token]
                df = doc_freq.get(token, 1)
                idf = math.log((len(self.evidence_rows) + 1) / (df + 1)) + 1.0
                score += tf_value * idf
            if score > 0:
                result = dict(row)
                result["relevance_score"] = round(score, 6)
                results.append(result)

        return sorted(results, key=lambda item: item["relevance_score"], reverse=True)[:limit]

    def metadata_filter(self, incident_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        results = [row for row in self.evidence_rows if row["incident_id"] == incident_id]
        ranked = []
        for row in results:
            score = 1.0
            if row["service"]:
                score += 0.5
            if row["source_type"]:
                score += 0.25
            if row["severity"] in {"critical", "warning"}:
                score += 0.25
            result = dict(row)
            result["relevance_score"] = round(score, 6)
            ranked.append(result)
        return sorted(ranked, key=lambda item: item["relevance_score"], reverse=True)[:limit]

    def combined_retrieval(self, query: str, incident_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        keyword_results = self.keyword_bm25(query, limit=limit * 3)
        keyword_by_id = {item["evidence_id"]: item["relevance_score"] for item in keyword_results}
        metadata_results = self.metadata_filter(incident_id, limit=limit * 3)
        metadata_by_id = {item["evidence_id"]: item["relevance_score"] for item in metadata_results}

        merged: Dict[str, Dict[str, Any]] = {}
        all_ids = set(keyword_by_id) | set(metadata_by_id)

        for evidence_id in all_ids:
            keyword_score = keyword_by_id.get(evidence_id, 0.0)
            metadata_score = metadata_by_id.get(evidence_id, 0.0)
            combined = keyword_score * 0.7 + metadata_score * 0.3
            row = next((row for row in self.evidence_rows if row["evidence_id"] == evidence_id), None)
            if row is None:
                continue
            out = dict(row)
            out["relevance_score"] = round(combined, 6)
            merged[evidence_id] = out

        final = sorted(merged.values(), key=lambda item: item["relevance_score"], reverse=True)
        return final[:limit]
