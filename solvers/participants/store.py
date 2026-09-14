"""Append-only sqlite ledger for governed native jobs and their events."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class JobRow:
    job_id: str
    participant_id: str
    design_id: str
    state: str
    error_code: str | None
    error_detail: str | None
    run_id: str | None
    input_hash: str | None
    envelope_json: str | None
    inputs_json: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class JobEventRow:
    sequence: int
    job_id: str
    state: str
    at: str
    detail: str


_UNSET: Any = object()


class JobLedger:
    """Thread-safe job ledger; envelopes stay queryable, blobs stay on disk."""

    def __init__(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(target, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS native_jobs (
                  job_id TEXT PRIMARY KEY,
                  participant_id TEXT NOT NULL,
                  design_id TEXT NOT NULL,
                  state TEXT NOT NULL,
                  error_code TEXT,
                  error_detail TEXT,
                  run_id TEXT,
                  input_hash TEXT,
                  envelope_json TEXT,
                  inputs_json TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS native_job_events (
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  job_id TEXT NOT NULL,
                  state TEXT NOT NULL,
                  at TEXT NOT NULL,
                  detail TEXT NOT NULL,
                  FOREIGN KEY(job_id) REFERENCES native_jobs(job_id)
                );
                """
            )
            self._connection.commit()

    def create(
        self,
        *,
        job_id: str,
        participant_id: str,
        design_id: str,
        state: str,
        created_at: str,
        inputs: dict[str, Any],
    ) -> None:
        inputs_json = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
        with self._lock:
            self._connection.execute(
                "INSERT INTO native_jobs(job_id,participant_id,design_id,state,"
                "error_code,error_detail,run_id,input_hash,envelope_json,inputs_json,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    job_id,
                    participant_id,
                    design_id,
                    state,
                    None,
                    None,
                    None,
                    None,
                    None,
                    inputs_json,
                    created_at,
                    created_at,
                ),
            )
            self._connection.commit()

    def update(
        self,
        job_id: str,
        *,
        state: str,
        updated_at: str,
        error_code: str | None | Any = _UNSET,
        error_detail: str | None | Any = _UNSET,
        run_id: str | None | Any = _UNSET,
        input_hash: str | None | Any = _UNSET,
        envelope_json: str | None | Any = _UNSET,
    ) -> None:
        assignments = ["state=?", "updated_at=?"]
        values: list[Any] = [state, updated_at]
        for column, value in (
            ("error_code", error_code),
            ("error_detail", error_detail),
            ("run_id", run_id),
            ("input_hash", input_hash),
            ("envelope_json", envelope_json),
        ):
            if value is not _UNSET:
                assignments.append(f"{column}=?")
                values.append(value)
        values.append(job_id)
        with self._lock:
            cursor = self._connection.execute(
                f"UPDATE native_jobs SET {', '.join(assignments)} WHERE job_id=?",
                values,
            )
            self._connection.commit()
            if cursor.rowcount == 0:
                raise KeyError(f"JOB_NOT_FOUND:{job_id}")

    def append_event(self, *, job_id: str, state: str, at: str, detail: str) -> int:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO native_job_events(job_id,state,at,detail) VALUES(?,?,?,?)",
                (job_id, state, at, detail),
            )
            self._connection.commit()
            sequence = cursor.lastrowid
            if sequence is None:
                raise RuntimeError("ledger did not return an event sequence")
            return sequence

    def get(self, job_id: str) -> JobRow | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT job_id,participant_id,design_id,state,error_code,error_detail,"
                "run_id,input_hash,envelope_json,inputs_json,created_at,updated_at "
                "FROM native_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        columns = set(row.keys())
        return JobRow(
            job_id=row["job_id"],
            participant_id=row["participant_id"],
            design_id=row["design_id"],
            state=row["state"],
            error_code=row["error_code"],
            error_detail=row["error_detail"],
            run_id=row["run_id"],
            input_hash=row["input_hash"],
            envelope_json=row["envelope_json"],
            inputs_json=row["inputs_json"] if "inputs_json" in columns else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def events(self, job_id: str) -> list[JobEventRow]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT sequence,job_id,state,at,detail FROM native_job_events "
                "WHERE job_id=? ORDER BY sequence",
                (job_id,),
            ).fetchall()
        return [
            JobEventRow(
                sequence=row["sequence"],
                job_id=row["job_id"],
                state=row["state"],
                at=row["at"],
                detail=row["detail"],
            )
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._connection.close()


def envelope_to_json(envelope: Any) -> str:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))
