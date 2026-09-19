from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ArtifactFormat = Literal[
    "parquet",
    "vtk",
    "gltf",
    "step",
    "brep",
    "hdf5",
    "zarr",
    "log",
    "json",
    "msh",
    "sif",
    "comm",
    "xml",
    "py",
    "txt",
    "dat",
]


class ImmutableRecordError(ValueError):
    """Raised when an immutable revision or event would be overwritten."""


class ArtifactReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    format: ArtifactFormat
    uri: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(ge=0)


class StoredRevision(BaseModel):
    model_config = ConfigDict(frozen=True)

    design_id: str
    revision_id: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    parent_revision_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    document: dict[str, Any]


class ProvenanceEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    event_id: str
    event_type: str
    subject_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    actor: str
    occurred_at: str
    details: dict[str, Any]
    previous_event_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    event_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifacts: tuple[ArtifactReference, ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _event_digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ProvenanceWrite:
    """One append-only provenance event plus its artifact references."""

    event_id: str
    event_type: str
    subject_hash: str
    actor: str
    occurred_at: str
    details: dict[str, Any]
    artifacts: tuple[ArtifactReference, ...] = field(default_factory=tuple)


class SQLiteRepository:
    """Small append-only metadata store; large engineering fields stay in artifact storage."""

    def __init__(self, path: str | Path) -> None:
        # Shared across the API request thread and the native worker threads;
        # every access is serialized below.
        self.connection = sqlite3.connect(path, check_same_thread=False, timeout=5.0)
        self.connection.row_factory = sqlite3.Row
        # PERF 06 safe-local tuning: WAL permits concurrent readers during a
        # writer; synchronous=NORMAL is the WAL durability-consistent mode and
        # does not weaken append-only/immutable semantics; busy_timeout bounds
        # contention instead of failing immediately.
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        self._commit_count = 0
        self._commit_ms = 0.0
        self._serialize_ms = 0.0
        self._migrate()

    def _commit(self) -> None:
        start = time.perf_counter()
        self.connection.commit()
        self._commit_count += 1
        self._commit_ms += (time.perf_counter() - start) * 1000.0

    def _serialize(self, value: object) -> str:
        start = time.perf_counter()
        try:
            return _canonical_json(value)
        finally:
            self._serialize_ms += (time.perf_counter() - start) * 1000.0

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version INTEGER PRIMARY KEY
            );
            INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);

            CREATE TABLE IF NOT EXISTS design_revisions (
              design_id TEXT NOT NULL,
              revision_id TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              parent_revision_hash TEXT,
              document TEXT NOT NULL,
              PRIMARY KEY (design_id, revision_id)
            );

            CREATE TABLE IF NOT EXISTS provenance_events (
              sequence INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT NOT NULL UNIQUE,
              event_type TEXT NOT NULL,
              subject_hash TEXT NOT NULL,
              actor TEXT NOT NULL,
              occurred_at TEXT NOT NULL,
              details TEXT NOT NULL,
              previous_event_hash TEXT,
              event_hash TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS artifact_refs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT NOT NULL,
              format TEXT NOT NULL,
              uri TEXT NOT NULL,
              sha256 TEXT NOT NULL,
              bytes INTEGER NOT NULL,
              FOREIGN KEY(event_id) REFERENCES provenance_events(event_id)
            );

            CREATE INDEX IF NOT EXISTS idx_provenance_subject
              ON provenance_events(subject_hash, sequence);
            CREATE INDEX IF NOT EXISTS idx_artifact_refs_event
              ON artifact_refs(event_id);
            """
        )
        self._commit()

    def save_revision(
        self,
        *,
        design_id: str,
        revision_id: str,
        content_hash: str,
        parent_revision_hash: str | None,
        document: dict[str, Any],
    ) -> None:
        revision = StoredRevision(
            design_id=design_id,
            revision_id=revision_id,
            content_hash=content_hash,
            parent_revision_hash=parent_revision_hash,
            document=document,
        )
        try:
            with self._lock:
                self.connection.execute(
                    "INSERT INTO design_revisions VALUES (?, ?, ?, ?, ?)",
                    (
                        revision.design_id,
                        revision.revision_id,
                        revision.content_hash,
                        revision.parent_revision_hash,
                        self._serialize(revision.document),
                    ),
                )
                self._commit()
        except sqlite3.IntegrityError as exc:
            with self._lock:
                self.connection.rollback()
            raise ImmutableRecordError(
                f"design revision ({design_id}, {revision_id}) is immutable"
            ) from exc

    def get_revision(self, design_id: str, revision_id: str) -> StoredRevision | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT design_id, revision_id, content_hash, parent_revision_hash, document "
                "FROM design_revisions WHERE design_id=? AND revision_id=?",
                (design_id, revision_id),
            ).fetchone()
        if row is None:
            return None
        return StoredRevision(
            design_id=row["design_id"],
            revision_id=row["revision_id"],
            content_hash=row["content_hash"],
            parent_revision_hash=row["parent_revision_hash"],
            document=json.loads(row["document"]),
        )

    def append_provenance(
        self,
        *,
        event_id: str,
        event_type: str,
        subject_hash: str,
        actor: str,
        occurred_at: str,
        details: dict[str, Any],
        artifacts: list[ArtifactReference],
    ) -> ProvenanceEvent:
        write = ProvenanceWrite(
            event_id=event_id,
            event_type=event_type,
            subject_hash=subject_hash,
            actor=actor,
            occurred_at=occurred_at,
            details=details,
            artifacts=tuple(artifacts),
        )
        return self.append_provenance_many([write])[0]

    def append_provenance_many(
        self, writes: Sequence[ProvenanceWrite]
    ) -> list[ProvenanceEvent]:
        """Append many chained provenance events in ONE bounded transaction.

        Artifact references are never blobs: only format/uri/sha256/bytes rows
        are stored. The hash chain (``previous_event_hash``) is extended across
        the whole batch, and a duplicate event id/hash rolls the entire batch
        back, preserving the append-only/immutable invariant.
        """

        prepared: list[tuple[ProvenanceWrite, tuple[ArtifactReference, ...]]] = []
        for write in writes:
            if (
                not write.event_id.strip()
                or not write.event_type.strip()
                or not write.actor.strip()
            ):
                raise ValueError("event identity must be non-empty")
            validated = tuple(
                ArtifactReference.model_validate(item) for item in write.artifacts
            )
            prepared.append((write, validated))
        if not prepared:
            return []
        with self._lock:
            previous = self.connection.execute(
                "SELECT event_hash FROM provenance_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_event_hash = None if previous is None else str(previous["event_hash"])
            bodies: list[
                tuple[ProvenanceWrite, tuple[ArtifactReference, ...], dict[str, Any], str]
            ] = []
            for write, validated in prepared:
                body = {
                    "event_id": write.event_id,
                    "event_type": write.event_type,
                    "subject_hash": write.subject_hash,
                    "actor": write.actor,
                    "occurred_at": write.occurred_at,
                    "details": write.details,
                    "artifacts": [
                        artifact.model_dump(mode="json") for artifact in validated
                    ],
                    "previous_event_hash": previous_event_hash,
                }
                event_hash = _event_digest(body)
                bodies.append((write, validated, body, event_hash))
                previous_event_hash = event_hash
            try:
                results: list[ProvenanceEvent] = []
                for write, validated, body, event_hash in bodies:
                    cursor = self.connection.execute(
                        "INSERT INTO provenance_events"
                        "(event_id,event_type,subject_hash,actor,occurred_at,details,"
                        "previous_event_hash,event_hash) "
                        "VALUES(?,?,?,?,?,?,?,?)",
                        (
                            write.event_id,
                            write.event_type,
                            write.subject_hash,
                            write.actor,
                            write.occurred_at,
                            self._serialize(write.details),
                            body["previous_event_hash"],
                            event_hash,
                        ),
                    )
                    if cursor.lastrowid is None:
                        raise RuntimeError("SQLite did not return a provenance sequence")
                    if validated:
                        self.connection.executemany(
                            "INSERT INTO artifact_refs(event_id,format,uri,sha256,bytes) "
                            "VALUES(?,?,?,?,?)",
                            [
                                (
                                    write.event_id,
                                    artifact.format,
                                    artifact.uri,
                                    artifact.sha256,
                                    artifact.bytes,
                                )
                                for artifact in validated
                            ],
                        )
                    results.append(
                        ProvenanceEvent(sequence=cursor.lastrowid, event_hash=event_hash, **body)
                    )
                self._commit()
            except sqlite3.IntegrityError as exc:
                self.connection.rollback()
                raise ImmutableRecordError("provenance event batch is immutable") from exc
            except Exception:
                self.connection.rollback()
                raise
        return results

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            events = int(
                self.connection.execute("SELECT COUNT(*) FROM provenance_events").fetchone()[0]
            )
            refs = int(
                self.connection.execute("SELECT COUNT(*) FROM artifact_refs").fetchone()[0]
            )
            return {
                "commits": self._commit_count,
                "commit_ms": round(self._commit_ms, 6),
                "metadata_serialize_ms": round(self._serialize_ms, 6),
                "provenance_events": events,
                "artifact_refs": refs,
            }

    def list_provenance(self, subject_hash: str) -> list[ProvenanceEvent]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT sequence,event_id,event_type,subject_hash,actor,occurred_at,details,"
                "previous_event_hash,event_hash FROM provenance_events "
                "WHERE subject_hash=? ORDER BY sequence",
                (subject_hash,),
            ).fetchall()
        events: list[ProvenanceEvent] = []
        for row in rows:
            with self._lock:
                artifact_rows = self.connection.execute(
                    "SELECT format,uri,sha256,bytes FROM artifact_refs "
                    "WHERE event_id=? ORDER BY id",
                    (row["event_id"],),
                ).fetchall()
            events.append(
                ProvenanceEvent(
                    sequence=row["sequence"],
                    event_id=row["event_id"],
                    event_type=row["event_type"],
                    subject_hash=row["subject_hash"],
                    actor=row["actor"],
                    occurred_at=row["occurred_at"],
                    details=json.loads(row["details"]),
                    previous_event_hash=row["previous_event_hash"],
                    event_hash=row["event_hash"],
                    artifacts=tuple(
                        ArtifactReference.model_validate(dict(item)) for item in artifact_rows
                    ),
                )
            )
        return events

    def close(self) -> None:
        with self._lock:
            self.connection.close()
