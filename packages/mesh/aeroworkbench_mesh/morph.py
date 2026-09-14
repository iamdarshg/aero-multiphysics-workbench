"""Guarded mesh update: morph small changes, remesh everything else.

A morph is an honest node displacement of the *existing* mesh, accepted only
when every gate passes:

1. semantic correspondence is valid (no missing/ambiguous entities);
2. no split/merged identity change (those require remesh);
3. maximum node displacement is within the motion budget;
4. post-morph quality gates pass (no inverted elements, SICN floor).

Any gate failure falls back to remeshing the affected domain. The receipt
always records which path was taken; a regenerated mesh is never labelled
``morphed``.
"""

from __future__ import annotations

import hashlib
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from aeroworkbench_semantics import TopologyReport

UpdateDecision = Literal["morph_candidate", "remesh_required"]


@dataclass(frozen=True, slots=True)
class UpdatePolicy:
    """Tunable gates for the morph/remesh decision."""

    max_displacement_mm: float = 1.0
    minimum_sicn: float = 0.05
    morph_scale_limit: float = 1.10


@dataclass(frozen=True, slots=True)
class MorphReceipt:
    state: Literal["morphed", "remeshed", "failed"]
    mesh_path: str | None
    mesh_hash: str | None
    max_displacement_mm: float
    min_sicn_after: float | None
    detail: str


def decide_update_strategy(
    report: TopologyReport, *, max_param_shift_mm: float, policy: UpdatePolicy
) -> tuple[UpdateDecision, str]:
    """Decide morph versus remesh from reconciliation plus parameter shift."""

    if not report.valid:
        return "remesh_required", (
            f"correspondence invalid:{report.reason}:remesh affected domains"
        )
    if report.requires_remesh:
        return "remesh_required", (
            f"topology identity changed:{report.reason}:remesh affected domains"
        )
    if max_param_shift_mm > policy.max_displacement_mm:
        return "remesh_required", (
            f"parameter shift {max_param_shift_mm}mm exceeds morph budget "
            f"{policy.max_displacement_mm}mm:remesh affected domains"
        )
    return "morph_candidate", (
        f"small change within budget:{report.reason}:attempt morph"
    )


def morph_affine(
    mesh_path: Path,
    product_path: Path,
    *,
    scale: float = 1.0,
    translation_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
    minimum_sicn: float = 0.05,
) -> MorphReceipt:
    """Displace existing mesh nodes by an affine map and gate the result.

    The element connectivity is untouched: only ``$Nodes`` coordinates move.
    Quality is re-measured in Gmsh before acceptance.
    """

    try:
        import gmsh  # noqa: PLC0415
    except ImportError as exc:
        return MorphReceipt("failed", None, None, 0.0, None,
                            f"GMSH_UNAVAILABLE:{exc}")
    if not 1.0 / 2.0 <= scale <= 2.0:
        return MorphReceipt("failed", None, None, 0.0, None,
                            "MORPH_SCALE_OUT_OF_BOUNDS")
    text = mesh_path.read_text(encoding="utf-8")
    if "$Nodes" not in text:
        return MorphReceipt("failed", None, None, 0.0, None,
                            "MORPH_NEEDS_ASCII_MSH4")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    index = 0
    max_displacement = 0.0
    while index < len(lines):
        out.append(lines[index])
        if lines[index].strip() == "$Nodes":
            header = lines[index + 1]
            out.append(header)
            parts = header.split()
            try:
                n_blocks = int(parts[0])
            except (ValueError, IndexError):
                return MorphReceipt("failed", None, None, 0.0, None,
                                    "MORPH_NODES_HEADER_UNREADABLE")
            index += 2
            for _ in range(n_blocks):
                block_header = lines[index]
                out.append(block_header)
                n_nodes = int(block_header.split()[3])
                index += 1
                tags: list[str] = []
                for _ in range(n_nodes):
                    tags.append(lines[index])
                    index += 1
                coords: list[tuple[float, float, float]] = []
                for _ in range(n_nodes):
                    words = lines[index].split()
                    coords.append((float(words[0]), float(words[1]), float(words[2])))
                    index += 1
                out.extend(tags)
                for x, y, z in coords:
                    nx, ny, nz = (
                        x * scale + translation_mm[0],
                        y * scale + translation_mm[1],
                        z * scale + translation_mm[2],
                    )
                    displacement = (
                        (nx - x) ** 2 + (ny - y) ** 2 + (nz - z) ** 2
                    ) ** 0.5
                    max_displacement = max(max_displacement, displacement)
                    out.append(f"{nx:.9f} {ny:.9f} {nz:.9f}\n")
            continue
        index += 1
    product_path.write_text("".join(out), encoding="utf-8")

    from .native_mesh import _MESH_LOCK  # noqa: PLC0415
    from .quality import compute_quality  # noqa: PLC0415

    with _MESH_LOCK:
        gmsh.initialize()
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.open(str(product_path))
            quality = compute_quality(gmsh, boundary_layer=(False, "morph:unchanged"))
        finally:
            with suppress(Exception):
                gmsh.finalize()
    if quality.inverted_count:
        product_path.unlink(missing_ok=True)
        return MorphReceipt(
            "failed", None, None, max_displacement, quality.min_sicn,
            f"MORPH_QUALITY_GATE:inverted={quality.inverted_count}:remesh required",
        )
    if quality.min_sicn is not None and quality.min_sicn < minimum_sicn:
        product_path.unlink(missing_ok=True)
        return MorphReceipt(
            "failed", None, None, max_displacement, quality.min_sicn,
            f"MORPH_QUALITY_GATE:min SICN {quality.min_sicn:.4f}:remesh required",
        )
    return MorphReceipt(
        "morphed",
        str(product_path),
        hashlib.sha256(product_path.read_bytes()).hexdigest(),
        max_displacement,
        quality.min_sicn,
        f"morph accepted:max displacement {max_displacement:.4f}mm, "
        f"min SICN {quality.min_sicn}",
    )
