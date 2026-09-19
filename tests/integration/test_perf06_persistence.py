"""PERF 06: persistence and artifact I/O overhead reduction (measured).

Covers the safe SQLite tuning, single-transaction lifecycle transitions,
bounded provenance batch writes with an intact hash chain, streaming/bounded
artifact hashing with digest reuse, and range-friendly verified retrieval.
Everything is bounded (<= 16 MiB fixtures, <= 300 events) and emits timings.
Append-only/immutable provenance and mandatory hash verification are asserted,
not relaxed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from participants.lifecycle import NativeJobManager
from participants.store import JobLedger

from aeroworkbench_api.main import create_app
from aeroworkbench_api.repositories.sqlite import (
    ImmutableRecordError,
    ProvenanceWrite,
    SQLiteRepository,
)

_JOB_ROOT_ENV = "AEROWORKBENCH_JOB_ROOT"


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _spm_inputs() -> dict[str, object]:
    return {
        "model": "spm",
        "parameter_set": "Chen2020",
        "discharge_current_a": 1.0,
        "duration_s": 60.0,
        "n_series": 1,
        "n_parallel": 1,
    }


# -- A. safe SQLite tuning ----------------------------------------------------


def test_sqlite_tuning_and_lookup_indexes_are_applied(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "tuning.sqlite3")
    ledger = JobLedger(tmp_path / "ledger-tuning.sqlite3")
    try:
        for connection in (repository.connection, ledger._connection):
            assert str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
            assert int(connection.execute("PRAGMA synchronous").fetchone()[0]) == 1
            assert int(connection.execute("PRAGMA busy_timeout").fetchone()[0]) == 5000
        provenance_indexes = {
            str(row[1])
            for row in repository.connection.execute("PRAGMA index_list(provenance_events)")
        }
        assert "idx_provenance_subject" in provenance_indexes
        assert "idx_artifact_refs_event" in {
            str(row[1])
            for row in repository.connection.execute("PRAGMA index_list(artifact_refs)")
        }
        assert "idx_native_job_events_job" in {
            str(row[1])
            for row in ledger._connection.execute("PRAGMA index_list(native_job_events)")
        }
    finally:
        ledger.close()
        repository.close()


# -- B. one commit per lifecycle transition ----------------------------------


def test_lifecycle_transition_is_a_single_commit(tmp_path: Path) -> None:
    ledger = JobLedger(tmp_path / "ledger.sqlite3")
    try:
        ledger.create_with_event(
            job_id="job-a",
            participant_id="p",
            design_id="d",
            state="QUEUED",
            created_at="2026-01-01T00:00:00+00:00",
            inputs={"seed": 0},
            detail="input_hash=seed0",
        )
        base = int(ledger.metrics()["commits"])
        ledger.create_with_event(
            job_id="job-b",
            participant_id="p",
            design_id="d",
            state="QUEUED",
            created_at="2026-01-01T00:00:00+00:00",
            inputs={"seed": 1},
            detail="input_hash=abc",
        )
        assert int(ledger.metrics()["commits"]) == base + 1
        ledger.transition(
            "job-a",
            state="FAILED",
            updated_at="2026-01-01T00:00:01+00:00",
            detail="boom",
            fields={"error_code": "ADMISSION_REJECTED", "error_detail": "boom"},
        )
        assert int(ledger.metrics()["commits"]) == base + 2
        events = ledger.events("job-a")
        assert [event.state for event in events] == ["QUEUED", "FAILED"]
        row = ledger.get("job-a")
        assert row is not None
        assert row.state == "FAILED"
        assert row.error_code == "ADMISSION_REJECTED"
        # The row and its event can never drift: both were written together.
        assert row.updated_at == events[-1].at
    finally:
        ledger.close()


def test_many_job_status_reads_are_bounded(tmp_path: Path, capsys: Any) -> None:
    ledger = JobLedger(tmp_path / "reads.sqlite3")
    try:
        jobs = 200
        for index in range(jobs):
            ledger.create_with_event(
                job_id=f"job-{index}",
                participant_id="p",
                design_id="d",
                state="QUEUED",
                created_at="2026-01-01T00:00:00+00:00",
                inputs={"seed": index},
                detail="seeded",
            )
        start = time.perf_counter()
        for index in range(2000):
            assert ledger.get(f"job-{index % jobs}") is not None
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        with capsys.disabled():
            print(f"\n[perf06] 2000 job-status reads over 200 jobs: {elapsed_ms:.3f} ms")
        assert elapsed_ms < 5000.0
    finally:
        ledger.close()


# -- B. batched provenance writes (measured) ---------------------------------


def _writes(count: int, subject: str, prefix: str) -> list[ProvenanceWrite]:
    return [
        ProvenanceWrite(
            event_id=f"{prefix}-{index}",
            event_type="perf.benchmark",
            subject_hash=subject,
            actor="perf",
            occurred_at="2026-01-01T00:00:00+00:00",
            details={"index": index},
            artifacts=(),
        )
        for index in range(count)
    ]


def test_batched_provenance_reduces_commits_and_preserves_chain(
    tmp_path: Path, capsys: Any
) -> None:
    repository = SQLiteRepository(tmp_path / "provenance.sqlite3")
    try:
        events = 300
        subject_individual = hashlib.sha256(b"individual").hexdigest()
        base_commits = int(repository.metrics()["commits"])
        start = time.perf_counter()
        for write in _writes(events, subject_individual, "ind"):
            repository.append_provenance(
                event_id=write.event_id,
                event_type=write.event_type,
                subject_hash=write.subject_hash,
                actor=write.actor,
                occurred_at=write.occurred_at,
                details=write.details,
                artifacts=[],
            )
        individual_ms = (time.perf_counter() - start) * 1000.0
        individual_commits = int(repository.metrics()["commits"]) - base_commits
        assert individual_commits == events

        subject_batch = hashlib.sha256(b"batch").hexdigest()
        before = int(repository.metrics()["commits"])
        start = time.perf_counter()
        committed = repository.append_provenance_many(_writes(events, subject_batch, "bat"))
        batch_ms = (time.perf_counter() - start) * 1000.0
        assert int(repository.metrics()["commits"]) == before + 1
        assert len(committed) == events
        for previous, current in zip(committed[:-1], committed[1:], strict=True):
            assert current.previous_event_hash == previous.event_hash
        stored = repository.list_provenance(subject_batch)
        assert len(stored) == events
        assert [event.event_hash for event in stored] == [event.event_hash for event in committed]
        with capsys.disabled():
            print(
                f"\n[perf06] provenance x{events}: individual={individual_ms:.3f} ms/"
                f"{individual_commits} commits, batch={batch_ms:.3f} ms/1 commit"
            )
        assert batch_ms < individual_ms
    finally:
        repository.close()


def test_batched_provenance_rolls_back_atomically_on_duplicate(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "atomic.sqlite3")
    try:
        subject = hashlib.sha256(b"first").hexdigest()
        repository.append_provenance(
            event_id="dup",
            event_type="perf.benchmark",
            subject_hash=subject,
            actor="perf",
            occurred_at="2026-01-01T00:00:00+00:00",
            details={},
            artifacts=[],
        )
        new_subject = hashlib.sha256(b"new").hexdigest()
        with pytest.raises(ImmutableRecordError):
            repository.append_provenance_many(
                [
                    ProvenanceWrite(
                        event_id="fresh",
                        event_type="perf.benchmark",
                        subject_hash=new_subject,
                        actor="perf",
                        occurred_at="2026-01-01T00:00:00+00:00",
                        details={},
                    ),
                    ProvenanceWrite(
                        event_id="dup",
                        event_type="perf.benchmark",
                        subject_hash=new_subject,
                        actor="perf",
                        occurred_at="2026-01-01T00:00:00+00:00",
                        details={},
                    ),
                ]
            )
        # The whole batch rolled back: the non-duplicate event did not persist.
        assert repository.list_provenance(new_subject) == []
    finally:
        repository.close()


# -- D. streaming hashing with bounded memory + digest reuse -----------------


def test_streaming_hash_is_bounded_and_throughput_is_measured(
    tmp_path: Path, capsys: Any
) -> None:
    from participants import lifecycle as lifecycle_mod

    size = 16 * 1024 * 1024
    fixture = tmp_path / "stream.bin"
    block = os.urandom(1024 * 1024)
    with fixture.open("wb") as stream:
        for _ in range(size // len(block)):
            stream.write(block)
    tracemalloc.start()
    start = time.perf_counter()
    digest, hashed = lifecycle_mod._sha256_file(fixture)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert hashed == size and len(digest) == 64
    mib_per_second = (size / (1024 * 1024)) / (elapsed_ms / 1000.0)
    with capsys.disabled():
        print(
            f"\n[perf06] streaming sha256 of {size // (1024 * 1024)} MiB: "
            f"{elapsed_ms:.3f} ms ({mib_per_second:.1f} MiB/s), peak alloc "
            f"{peak / (1024 * 1024):.3f} MiB"
        )
    assert mib_per_second > 1.0
    assert peak < 8 * 1024 * 1024, "RSS/allocation scaled with the full artifact size"


def test_digest_cache_reuses_an_unchanged_artifact(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from participants import lifecycle as lifecycle_mod

    fixture = tmp_path / "cache.bin"
    fixture.write_bytes(b"a" * 2048)
    calls = {"count": 0}
    original = lifecycle_mod._sha256_file

    def _counting(path: Path) -> tuple[str, int]:
        calls["count"] += 1
        return original(path)

    monkeypatch.setattr(lifecycle_mod, "_sha256_file", _counting)
    first, size_one = lifecycle_mod._sha256_file_cached(fixture)
    second, size_two = lifecycle_mod._sha256_file_cached(fixture)
    assert first == second and size_one == size_two == 2048
    assert calls["count"] == 1, "unchanged artifact was hashed more than once"
    time.sleep(0.02)
    fixture.write_bytes(b"b" * 4096)
    third, size_three = lifecycle_mod._sha256_file_cached(fixture)
    assert third != first and size_three == 4096
    assert calls["count"] == 2, "a changed artifact must be re-hashed"
    metrics = lifecycle_mod._DIGEST_CACHE.metrics()
    assert metrics["hits"] >= 1


# -- F. metrics exposure ------------------------------------------------------


def test_manager_exposes_persistence_metrics(tmp_path: Path) -> None:
    manager = NativeJobManager(tmp_path / "jobs")
    try:
        metrics = manager.persistence_metrics()
        assert set(metrics) == {
            "ledger",
            "repository",
            "hash_bytes",
            "hash_ms",
            "artifact_read_bytes",
            "artifact_read_ms",
            "digest_cache",
        }
        assert "commit_ms" in metrics["ledger"]
        assert "metadata_serialize_ms" in metrics["ledger"]
        assert "commit_ms" in metrics["repository"]
        assert "metadata_serialize_ms" in metrics["repository"]
    finally:
        manager.close()


# -- E. range-friendly verified artifact retrieval ---------------------------


def _seed_completed_job(
    tmp_path: Path, monkeypatch: Any
) -> tuple[TestClient, str, bytes]:
    root = tmp_path / "api-jobs"
    monkeypatch.setenv(_JOB_ROOT_ENV, str(root))
    client = TestClient(create_app())
    client.__enter__()
    submitted = client.post(
        "/v1/native/analyses",
        json={"participant_id": "cell-spm-discharge", "inputs": _spm_inputs(), "deferred": True},
    )
    assert submitted.status_code == 202
    job_id = str(submitted.json()["job_id"])
    manager = NativeJobManager(root)
    try:
        payload = os.urandom(256 * 1024)
        case_dir = manager._job_root / f"case-{job_id[:12]}"
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "result.json").write_bytes(payload)
        envelope = {
            "source": "native_solver",
            "fidelity": "spm",
            "run_id": "run-1",
            "provenance_id": "prov-1",
            "artifacts": [
                {"name": "result.json", "sha256": _digest(payload), "bytes": len(payload)}
            ],
        }
        manager._ledger.update(
            job_id,
            state="COMPLETED",
            updated_at=datetime.now(UTC).isoformat(),
            envelope_json=json.dumps(envelope, sort_keys=True),
            run_id="run-1",
            result_id=_digest(b"result"),
            provenance_id="prov-1",
        )
    finally:
        manager.close()
    return client, job_id, payload


def test_artifact_retrieval_streams_and_supports_ranges(
    tmp_path: Path, monkeypatch: Any
) -> None:
    client, job_id, payload = _seed_completed_job(tmp_path, monkeypatch)
    try:
        full = client.get(f"/v1/native/artifacts/{job_id}/result.json")
        assert full.status_code == 200
        assert full.content == payload
        assert full.headers["accept-ranges"] == "bytes"

        ranged = client.get(
            f"/v1/native/artifacts/{job_id}/result.json",
            headers={"Range": "bytes=100-199"},
        )
        assert ranged.status_code == 206
        assert ranged.content == payload[100:200]
        assert ranged.headers["content-range"] == f"bytes 100-199/{len(payload)}"

        suffix = client.get(
            f"/v1/native/artifacts/{job_id}/result.json",
            headers={"Range": "bytes=-16"},
        )
        assert suffix.status_code == 206
        assert suffix.content == payload[-16:]
    finally:
        client.__exit__(None, None, None)


def test_streaming_download_still_fails_closed_on_tamper(
    tmp_path: Path, monkeypatch: Any
) -> None:
    client, job_id, payload = _seed_completed_job(tmp_path, monkeypatch)
    try:
        root = Path(os.environ[_JOB_ROOT_ENV])
        target = root / f"case-{job_id[:12]}" / "result.json"
        target.write_bytes(payload + b"tampered")
        response = client.get(f"/v1/native/artifacts/{job_id}/result.json")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "ARTIFACT_HASH_MISMATCH"
    finally:
        client.__exit__(None, None, None)
