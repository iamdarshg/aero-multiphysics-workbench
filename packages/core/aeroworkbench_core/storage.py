from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .design import PhysicalDesignState


class Job(BaseModel):
    job_id: str
    kind: str
    status: str


class JobEvent(BaseModel):
    sequence: int
    status: str
    payload: dict[str, Any]
    created_at: datetime


class DesignEvent(BaseModel):
    sequence: int
    design_id: str
    variant_id: str
    event_type: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class ImmutableRevisionError(ValueError):
    """Raised when a persisted design revision would be overwritten."""


class SQLiteMetadataStore:
    def __init__(self, path: str | Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS designs (
          design_id TEXT NOT NULL, variant_id TEXT NOT NULL, document TEXT NOT NULL,
          PRIMARY KEY (design_id, variant_id)
        );
        CREATE TABLE IF NOT EXISTS design_events (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          design_id TEXT NOT NULL, variant_id TEXT NOT NULL, event_type TEXT NOT NULL,
          content_hash TEXT NOT NULL, provenance_id TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(design_id, variant_id) REFERENCES designs(design_id, variant_id)
        );
        CREATE TABLE IF NOT EXISTS jobs (
          job_id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS job_events (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
          status TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
        """)

    def save_design(self, design: PhysicalDesignState) -> None:
        created_at = datetime.now(UTC).isoformat()
        try:
            self.connection.execute(
                "INSERT INTO designs VALUES (?, ?, ?)",
                (design.design_id, design.variant_id, design.model_dump_json()),
            )
            self.connection.execute(
                "INSERT INTO design_events"
                "(design_id, variant_id, event_type, content_hash, provenance_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    design.design_id,
                    design.variant_id,
                    "created",
                    design.content_hash,
                    design.content_hash,
                    created_at,
                ),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            self.connection.rollback()
            raise ImmutableRevisionError(
                f"Design revision ({design.design_id}, {design.variant_id}) is immutable"
            ) from exc

    def get_design(self, design_id: str, variant_id: str) -> PhysicalDesignState | None:
        row = self.connection.execute(
            "SELECT document FROM designs WHERE design_id=? AND variant_id=?",
            (design_id, variant_id),
        ).fetchone()
        return None if row is None else PhysicalDesignState.model_validate_json(row[0])

    def list_design_events(self, design_id: str, variant_id: str) -> list[DesignEvent]:
        rows = self.connection.execute(
            "SELECT sequence, design_id, variant_id, event_type, content_hash, provenance_id, "
            "created_at FROM design_events WHERE design_id=? AND variant_id=? ORDER BY sequence",
            (design_id, variant_id),
        ).fetchall()
        return [
            DesignEvent(
                sequence=row[0],
                design_id=row[1],
                variant_id=row[2],
                event_type=row[3],
                content_hash=row[4],
                provenance_id=row[5],
                created_at=row[6],
            )
            for row in rows
        ]

    def create_job(self, job_id: str, kind: str) -> None:
        self.connection.execute("INSERT INTO jobs VALUES (?, ?, ?)", (job_id, kind, "queued"))
        self.connection.commit()
        self.append_job_event(job_id, "queued", {})

    def append_job_event(self, job_id: str, status: str, payload: dict[str, Any]) -> None:
        import json

        self.connection.execute(
            "INSERT INTO job_events(job_id,status,payload,created_at) VALUES(?,?,?,?)",
            (job_id, status, json.dumps(payload, sort_keys=True), datetime.now(UTC).isoformat()),
        )
        self.connection.execute("UPDATE jobs SET status=? WHERE job_id=?", (status, job_id))
        self.connection.commit()

    def list_job_events(self, job_id: str) -> list[JobEvent]:
        import json

        rows = self.connection.execute(
            "SELECT sequence,status,payload,created_at FROM job_events "
            "WHERE job_id=? ORDER BY sequence",
            (job_id,),
        ).fetchall()
        return [
            JobEvent(sequence=row[0], status=row[1], payload=json.loads(row[2]), created_at=row[3])
            for row in rows
        ]

    def get_job(self, job_id: str) -> Job | None:
        row = self.connection.execute(
            "SELECT job_id,kind,status FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        return None if row is None else Job(job_id=row[0], kind=row[1], status=row[2])

    def close(self) -> None:
        self.connection.close()
