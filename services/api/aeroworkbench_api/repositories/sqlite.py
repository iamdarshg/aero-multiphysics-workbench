from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ArtifactFormat = Literal["parquet", "vtk", "gltf", "step", "brep", "hdf5", "zarr"]


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


class SQLiteRepository:
    """Small append-only metadata store; large engineering fields stay in artifact storage."""

    def __init__(self, path: str | Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

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
            """
        )
        self.connection.commit()

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
            self.connection.execute(
                "INSERT INTO design_revisions VALUES (?, ?, ?, ?, ?)",
                (
                    revision.design_id,
                    revision.revision_id,
                    revision.content_hash,
                    revision.parent_revision_hash,
                    _canonical_json(revision.document),
                ),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            self.connection.rollback()
            raise ImmutableRecordError(
                f"design revision ({design_id}, {revision_id}) is immutable"
            ) from exc

    def get_revision(self, design_id: str, revision_id: str) -> StoredRevision | None:
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
        if not event_id.strip() or not event_type.strip() or not actor.strip():
            raise ValueError("event identity must be non-empty")
        validated_artifacts = tuple(ArtifactReference.model_validate(item) for item in artifacts)
        previous = self.connection.execute(
            "SELECT event_hash FROM provenance_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_event_hash = None if previous is None else str(previous["event_hash"])
        body = {
            "event_id": event_id,
            "event_type": event_type,
            "subject_hash": subject_hash,
            "actor": actor,
            "occurred_at": occurred_at,
            "details": details,
            "artifacts": [artifact.model_dump(mode="json") for artifact in validated_artifacts],
            "previous_event_hash": previous_event_hash,
        }
        event_hash = _event_digest(body)
        try:
            cursor = self.connection.execute(
                "INSERT INTO provenance_events"
                "(event_id,event_type,subject_hash,actor,occurred_at,details,"
                "previous_event_hash,event_hash) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    event_id,
                    event_type,
                    subject_hash,
                    actor,
                    occurred_at,
                    _canonical_json(details),
                    previous_event_hash,
                    event_hash,
                ),
            )
            self.connection.executemany(
                "INSERT INTO artifact_refs(event_id,format,uri,sha256,bytes) VALUES(?,?,?,?,?)",
                [
                    (event_id, artifact.format, artifact.uri, artifact.sha256, artifact.bytes)
                    for artifact in validated_artifacts
                ],
            )
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            self.connection.rollback()
            raise ImmutableRecordError(f"provenance event {event_id} is immutable") from exc
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return a provenance sequence")
        return ProvenanceEvent(sequence=cursor.lastrowid, event_hash=event_hash, **body)

    def list_provenance(self, subject_hash: str) -> list[ProvenanceEvent]:
        rows = self.connection.execute(
            "SELECT sequence,event_id,event_type,subject_hash,actor,occurred_at,details,"
            "previous_event_hash,event_hash FROM provenance_events "
            "WHERE subject_hash=? ORDER BY sequence",
            (subject_hash,),
        ).fetchall()
        events: list[ProvenanceEvent] = []
        for row in rows:
            artifact_rows = self.connection.execute(
                "SELECT format,uri,sha256,bytes FROM artifact_refs WHERE event_id=? ORDER BY id",
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
        self.connection.close()
