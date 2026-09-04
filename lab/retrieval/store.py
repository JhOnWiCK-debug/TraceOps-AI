import sqlite3
from pathlib import Path
from typing import List, Dict, Any


class EvidenceStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(evidence)").fetchall()}
        if columns and "run_id" not in columns:
            self.conn.execute("ALTER TABLE evidence RENAME TO evidence_legacy")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT NOT NULL,
                incident_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                service TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                raw_source_path TEXT,
                normalized_text TEXT NOT NULL,
                PRIMARY KEY (run_id, evidence_id)
            )
            """
        )
        if columns and "run_id" not in columns:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO evidence (
                    evidence_id, incident_id, run_id, timestamp, service, source_type, source,
                    event_type, message, severity, raw_source_path, normalized_text
                )
                SELECT evidence_id, incident_id, 'legacy', timestamp, service, source_type, source,
                       event_type, message, severity, raw_source_path, normalized_text
                FROM evidence_legacy
                """
            )
            self.conn.execute("DROP TABLE evidence_legacy")
        self.conn.commit()

    def insert_many(self, rows: List[Dict[str, Any]]):
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO evidence (
                evidence_id, incident_id, run_id, timestamp, service, source_type, source,
                event_type, message, severity, raw_source_path, normalized_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["evidence_id"],
                    row["incident_id"],
                    row.get("run_id", "legacy"),
                    row["timestamp"],
                    row["service"],
                    row["source_type"],
                    row["source"],
                    row["event_type"],
                    row["message"],
                    row["severity"],
                    row["raw_source_path"],
                    row["normalized_text"],
                )
                for row in rows
            ],
        )
        self.conn.commit()

    def fetch_all(self, incident_id: str = None, run_id: str = None):
        query = "SELECT evidence_id, incident_id, run_id, timestamp, service, source_type, source, event_type, message, severity, raw_source_path, normalized_text FROM evidence"
        filters = []
        parameters = []
        if incident_id is not None:
            filters.append("incident_id = ?")
            parameters.append(incident_id)
        if run_id is not None:
            filters.append("run_id = ?")
            parameters.append(run_id)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY timestamp ASC"
        rows = self.conn.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def close(self):
        self.conn.close()
