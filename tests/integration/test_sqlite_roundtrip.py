from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aeroworkbench_api.repositories.sqlite import (
    ArtifactReference,
    ImmutableRecordError,
    SQLiteRepository,
)


def _digest(character: str) -> str:
    return character * 64


def test_revision_and_provenance_survive_a_database_reopen(tmp_path: Path) -> None:
    database = tmp_path / "workbench.sqlite3"
    repository = SQLiteRepository(database)
    repository.save_revision(
        design_id="edf-70",
        revision_id="rev-a",
        content_hash=_digest("a"),
        parent_revision_hash=None,
        document={"parameters": {"tip_clearance_m": 0.0007}},
    )
    event = repository.append_provenance(
        event_id="evt-1",
        event_type="design.created",
        subject_hash=_digest("a"),
        actor="engineer",
        occurred_at="2026-09-09T18:00:00.000Z",
        details={"fidelity": "analytical"},
        artifacts=[
            ArtifactReference(
                format="step",
                uri="artifacts/edf.step",
                sha256=_digest("b"),
                bytes=128,
            )
        ],
    )
    repository.close()

    reopened = SQLiteRepository(database)
    revision = reopened.get_revision("edf-70", "rev-a")
    events = reopened.list_provenance(_digest("a"))
    reopened.close()

    assert revision is not None
    assert revision.document == {"parameters": {"tip_clearance_m": 0.0007}}
    assert revision.content_hash == _digest("a")
    assert event.sequence == 1
    assert event.previous_event_hash is None
    assert len(events) == 1
    assert events[0].event_hash == event.event_hash
    assert events[0].artifacts[0].uri == "artifacts/edf.step"


def test_revision_and_provenance_rows_are_append_only(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "immutable.sqlite3")
    repository.save_revision(
        design_id="edf-70",
        revision_id="rev-a",
        content_hash=_digest("a"),
        parent_revision_hash=None,
        document={"value": 1},
    )

    with pytest.raises(ImmutableRecordError, match="immutable"):
        repository.save_revision(
            design_id="edf-70",
            revision_id="rev-a",
            content_hash=_digest("b"),
            parent_revision_hash=None,
            document={"value": 2},
        )

    repository.append_provenance(
        event_id="evt-1",
        event_type="design.created",
        subject_hash=_digest("a"),
        actor="engineer",
        occurred_at="2026-09-09T18:00:00.000Z",
        details={},
        artifacts=[],
    )
    with pytest.raises(ImmutableRecordError, match="immutable"):
        repository.append_provenance(
            event_id="evt-1",
            event_type="design.rewritten",
            subject_hash=_digest("a"),
            actor="engineer",
            occurred_at="2026-09-09T18:01:00.000Z",
            details={},
            artifacts=[],
        )
    repository.close()


def test_large_artifacts_are_references_not_database_blobs(tmp_path: Path) -> None:
    database = tmp_path / "artifacts.sqlite3"
    repository = SQLiteRepository(database)
    repository.append_provenance(
        event_id="evt-artifacts",
        event_type="result.published",
        subject_hash=_digest("c"),
        actor="worker:local",
        occurred_at="2026-09-09T18:02:00.000Z",
        details={"eligible": False},
        artifacts=[
            ArtifactReference(
                format=format_name,
                uri=f"artifacts/result.{suffix}",
                sha256=_digest(str(index)),
                bytes=index * 100,
            )
            for index, (format_name, suffix) in enumerate(
                [
                    ("parquet", "parquet"),
                    ("vtk", "vtu"),
                    ("gltf", "glb"),
                    ("brep", "brep"),
                    ("hdf5", "h5"),
                    ("zarr", "zarr"),
                ],
                start=1,
            )
        ],
    )
    repository.close()

    connection = sqlite3.connect(database)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(artifact_refs)")}
    stored = connection.execute(
        "SELECT format, uri, sha256, bytes FROM artifact_refs ORDER BY id"
    ).fetchall()
    connection.close()

    assert columns == {"id", "event_id", "format", "uri", "sha256", "bytes"}
    assert [row[0] for row in stored] == ["parquet", "vtk", "gltf", "brep", "hdf5", "zarr"]
    assert all(isinstance(row[1], str) and isinstance(row[2], str) for row in stored)
