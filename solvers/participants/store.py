"""Append-only sqlite ledger for governed native jobs and their events.

PERF 06: the ledger is tuned for safe local durability (WAL, a durability-
consistent ``synchronous`` mode, busy timeout) with lookup indexes for the
job/event read paths. A single lifecycle transition is written as ONE
transaction (state row + event row) instead of two independent commits, which
removes the largest source of avoidable write overhead while preserving the
append-only event stream and the atomic terminal metadata guarantee.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Columns a caller may set on a lifecycle transition. Anything else is a bug.
_TRANSITION_COLUMNS: tuple[str, ...] = (
    "error_code",
    "error_detail",
    "run_id",
    "input_hash",
    "envelope_json",
    "result_id",
    "provenance_id",
)


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
    owner_id: str | None = None
    revision_id: str | None = None
    result_id: str | None = None
    provenance_id: str | None = None


@dataclass(frozen=True, slots=True)
class JobEventRow:
    sequence: int
    job_id: str
    state: str
    at: str
    detail: str


_UNSET: Any = object()


def configure_connection(connection: sqlite3.Connection) -> None:
    """Apply the shared safe-local PRAGMA set to a ledger connection.

    ``journal_mode=WAL`` allows readers during a writer. ``synchronous=NORMAL``
    is the durability-consistent choice for WAL: committed transactions survive
    an application crash and remain crash-atomic; it only relaxes the extra
    fsync on power loss, which does not affect the append-only/immutable
    contract. ``busy_timeout`` bounds lock contention instead of raising
    immediately when concurrent workers touch the ledger.
    """

    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute("PRAGMA foreign_keys=ON")


class JobLedger:
    """Thread-safe job ledger; envelopes stay queryable, blobs stay on disk."""

    def __init__(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(target, check_same_thread=False, timeout=5.0)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._commit_count = 0
        self._commit_ms = 0.0
        self._serialize_ms = 0.0
        with self._lock:
            configure_connection(self._connection)
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
                CREATE INDEX IF NOT EXISTS idx_native_jobs_state
                  ON native_jobs(state);
                CREATE INDEX IF NOT EXISTS idx_native_jobs_created
                  ON native_jobs(created_at);
                CREATE INDEX IF NOT EXISTS idx_native_job_events_job
                  ON native_job_events(job_id, sequence);
                """
            )
            self._commit()
            self._migrate_job_columns()

    def _commit(self) -> None:
        start = time.perf_counter()
        self._connection.commit()
        self._commit_count += 1
        self._commit_ms += (time.perf_counter() - start) * 1000.0

    def _serialize(self, inputs: dict[str, Any]) -> str:
        start = time.perf_counter()
        try:
            return json.dumps(inputs, sort_keys=True, separators=(",", ":"))
        finally:
            self._serialize_ms += (time.perf_counter() - start) * 1000.0

    @staticmethod
    def _optional_job_columns() -> tuple[str, ...]:
        return ("owner_id", "revision_id", "result_id", "provenance_id")

    def _migrate_job_columns(self) -> None:
        existing = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(native_jobs)").fetchall()
        }
        for column in self._optional_job_columns():
            if column not in existing:
                self._connection.execute(f"ALTER TABLE native_jobs ADD COLUMN {column} TEXT")
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
        owner_id: str | None = None,
        revision_id: str | None = None,
    ) -> None:
        inputs_json = self._serialize(inputs)
        with self._lock:
            self._connection.execute(
                "INSERT INTO native_jobs(job_id,participant_id,design_id,state,"
                "error_code,error_detail,run_id,input_hash,envelope_json,inputs_json,"
                "created_at,updated_at,owner_id,revision_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                    owner_id,
                    revision_id,
                ),
            )
            self._commit()

    def create_with_event(
        self,
        *,
        job_id: str,
        participant_id: str,
        design_id: str,
        state: str,
        created_at: str,
        inputs: dict[str, Any],
        detail: str,
        owner_id: str | None = None,
        revision_id: str | None = None,
    ) -> int:
        """Insert the job row and its first event in ONE transaction."""

        inputs_json = self._serialize(inputs)
        with self._lock:
            try:
                self._connection.execute(
                    "INSERT INTO native_jobs(job_id,participant_id,design_id,state,"
                    "error_code,error_detail,run_id,input_hash,envelope_json,inputs_json,"
                    "created_at,updated_at,owner_id,revision_id) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                        owner_id,
                        revision_id,
                    ),
                )
                cursor = self._connection.execute(
                    "INSERT INTO native_job_events(job_id,state,at,detail) VALUES(?,?,?,?)",
                    (job_id, state, created_at, detail),
                )
                self._commit()
            except Exception:
                self._connection.rollback()
                raise
            sequence = cursor.lastrowid
            if sequence is None:
                raise RuntimeError("ledger did not return an event sequence")
            return sequence

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
        result_id: str | None | Any = _UNSET,
        provenance_id: str | None | Any = _UNSET,
    ) -> None:
        assignments = ["state=?", "updated_at=?"]
        values: list[Any] = [state, updated_at]
        for column, value in (
            ("error_code", error_code),
            ("error_detail", error_detail),
            ("run_id", run_id),
            ("input_hash", input_hash),
            ("envelope_json", envelope_json),
            ("result_id", result_id),
            ("provenance_id", provenance_id),
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
            self._commit()
            if cursor.rowcount == 0:
                raise KeyError(f"JOB_NOT_FOUND:{job_id}")

    def transition(
        self,
        job_id: str,
        *,
        state: str,
        updated_at: str,
        detail: str,
        fields: dict[str, Any] | None = None,
    ) -> int:
        """Apply one lifecycle transition atomically (row update + event).

        The state row (including terminal metadata such as result/error ids)
        and the event row commit together, so a poller can never observe a
        terminal state before its metadata, and the event stream can never
        drift from the job row.
        """

        supplied = dict(fields or {})
        unknown = set(supplied) - set(_TRANSITION_COLUMNS)
        if unknown:
            raise ValueError(f"UNKNOWN_TRANSITION_FIELD:{','.join(sorted(unknown))}")
        assignments = ["state=?", "updated_at=?"]
        values: list[Any] = [state, updated_at]
        for column in _TRANSITION_COLUMNS:
            if column in supplied:
                assignments.append(f"{column}=?")
                values.append(supplied[column])
        values.append(job_id)
        with self._lock:
            try:
                cursor = self._connection.execute(
                    f"UPDATE native_jobs SET {', '.join(assignments)} WHERE job_id=?",
                    values,
                )
                if cursor.rowcount == 0:
                    raise KeyError(f"JOB_NOT_FOUND:{job_id}")
                event_cursor = self._connection.execute(
                    "INSERT INTO native_job_events(job_id,state,at,detail) VALUES(?,?,?,?)",
                    (job_id, state, updated_at, detail),
                )
                self._commit()
            except Exception:
                self._connection.rollback()
                raise
            sequence = event_cursor.lastrowid
            if sequence is None:
                raise RuntimeError("ledger did not return an event sequence")
            return sequence

    def append_event(self, *, job_id: str, state: str, at: str, detail: str) -> int:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO native_job_events(job_id,state,at,detail) VALUES(?,?,?,?)",
                (job_id, state, at, detail),
            )
            self._commit()
            sequence = cursor.lastrowid
            if sequence is None:
                raise RuntimeError("ledger did not return an event sequence")
            return sequence

    def get(self, job_id: str) -> JobRow | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT job_id,participant_id,design_id,state,error_code,error_detail,"
                "run_id,input_hash,envelope_json,inputs_json,created_at,updated_at,"
                "owner_id,revision_id,result_id,provenance_id "
                "FROM native_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        columns = set(row.keys())

        def _optional(name: str) -> str | None:
            if name not in columns:
                return None
            value = row[name]
            return None if value is None else str(value)

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
            owner_id=_optional("owner_id"),
            revision_id=_optional("revision_id"),
            result_id=_optional("result_id"),
            provenance_id=_optional("provenance_id"),
        )

    def all(self) -> list[JobRow]:
        """Return every job row; used once at startup to interrupt orphans."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT job_id FROM native_jobs ORDER BY created_at"
            ).fetchall()
            job_ids = [str(row["job_id"]) for row in rows]
        jobs: list[JobRow] = []
        for job_id in job_ids:
            row = self.get(job_id)
            if row is not None:
                jobs.append(row)
        return jobs

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

    def terminal_events_since(
        self, sequence: int, *, limit: int = 0
    ) -> list[JobEventRow]:
        """Terminal-state events strictly after ``sequence``, in order.

        The sequence is a stable cursor: a campaign can consume completions
        incrementally without polling each job one by one.
        """

        sql = (
            "SELECT sequence,job_id,state,at,detail FROM native_job_events "
            "WHERE sequence > ? AND state IN ('COMPLETED','FAILED','CANCELLED') "
            "ORDER BY sequence"
        )
        params: list[Any] = [int(sequence)]
        if limit > 0:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._lock:
            rows = self._connection.execute(sql, params).fetchall()
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

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            job_count = int(
                self._connection.execute("SELECT COUNT(*) FROM native_jobs").fetchone()[0]
            )
            event_count = int(
                self._connection.execute("SELECT COUNT(*) FROM native_job_events").fetchone()[0]
            )
            return {
                "commits": self._commit_count,
                "commit_ms": round(self._commit_ms, 6),
                "metadata_serialize_ms": round(self._serialize_ms, 6),
                "jobs": job_count,
                "events": event_count,
            }

    def close(self) -> None:
        with self._lock:
            self._connection.close()


def envelope_to_json(envelope: Any) -> str:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))
