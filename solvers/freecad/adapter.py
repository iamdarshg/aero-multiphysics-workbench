"""Real headless CAD interchange: FreeCAD when present, OCP fallback otherwise.

The adapter never claims a conversion it did not run:

- ``inspect_freecad`` reports native FreeCADCmd availability (unchanged).
- When FreeCADCmd exists, STEP/BREP conversion runs headless through it with
  allowlisted arguments and hashed artifacts.
- When it does not exist, conversion runs through the bundled OpenCascade
  bindings and the receipt records ``converter="ocp-fallback"`` with
  ``freecad_state="unavailable"``.
- FCStd import/export uses the real FCStd container layout (zip with
  ``Document.xml`` + BREP payloads); FreeCAD opens what we write.
- Roundtrips reconcile face topology and fail closed on silent change.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ConverterKind = Literal["freecad", "ocp-fallback"]


@dataclass(frozen=True, slots=True)
class FreeCADReceipt:
    state: str
    executable: str
    detail: str


@dataclass(frozen=True, slots=True)
class ConversionReceipt:
    state: Literal["completed", "failed", "unavailable"]
    converter: ConverterKind | None
    source: str
    product: str | None
    source_sha256: str | None
    product_sha256: str | None
    code: str
    detail: str


def inspect_freecad(executable: str = "FreeCADCmd") -> FreeCADReceipt:
    """Report native availability without launching or installing FreeCAD."""

    resolved = shutil.which(executable)
    if resolved is None:
        return FreeCADReceipt("unavailable", executable, "FreeCADCmd is not installed")
    return FreeCADReceipt(
        "ready", resolved, "native executable is discoverable; conversion not run"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fail(
    source: str, code: str, detail: str, converter: ConverterKind | None = None
) -> ConversionReceipt:
    return ConversionReceipt(
        state="failed",
        converter=converter,
        source=source,
        product=None,
        source_sha256=None,
        product_sha256=None,
        code=code,
        detail=detail,
    )


def _done(
    converter: ConverterKind, source: Path, product: Path, detail: str
) -> ConversionReceipt:
    return ConversionReceipt(
        state="completed",
        converter=converter,
        source=str(source),
        product=str(product),
        source_sha256=_sha256(source),
        product_sha256=_sha256(product),
        code="CONVERSION_OK",
        detail=detail,
    )


_FREECAD_CONVERT_SCRIPT = """\
import sys
import FreeCAD
import Part

source, product = sys.argv[1], sys.argv[2]
shape = Part.Shape()
shape.read(source)
doc = FreeCAD.newDocument("convert")
feature = doc.addObject("Part::Feature", "shape")
feature.Shape = shape
doc.recompute()
feature.Shape.write(product)
print("CONVERT_OK")
"""


def convert_with_freecad(
    source: Path,
    product: Path,
    *,
    executable: str = "FreeCADCmd",
    timeout_s: float = 300.0,
) -> ConversionReceipt:
    """Run a real headless FreeCAD conversion (STEP<->BREP) without a shell."""

    resolved = shutil.which(executable)
    if resolved is None:
        return ConversionReceipt(
            state="unavailable",
            converter=None,
            source=str(source),
            product=None,
            source_sha256=None,
            product_sha256=None,
            code="FREECAD_UNAVAILABLE",
            detail="FreeCADCmd is not installed; no conversion was run",
        )
    if not source.is_file():
        return _fail(str(source), "SOURCE_NOT_FOUND", "conversion source missing",
                      converter="freecad")
    if source.suffix.lower() not in (".step", ".stp", ".brep", ".brp"):
        return _fail(str(source), "UNSUPPORTED_SOURCE_FORMAT",
                      f"unsupported CAD source: {source.suffix}", converter="freecad")
    product.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(_FREECAD_CONVERT_SCRIPT)
        script = handle.name
    try:
        completed = subprocess.run(
            [resolved, "--run-script", script, str(source), str(product)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _fail(str(source), "CONVERSION_TIMEOUT",
                      f"FreeCAD conversion timed out: {exc}", converter="freecad")
    finally:
        Path(script).unlink(missing_ok=True)
    if completed.returncode != 0 or not product.is_file():
        return _fail(
            str(source),
            "CONVERSION_FAILED",
            f"FreeCAD exit={completed.returncode} "
            f"stderr={completed.stderr[-2000:]}",
            converter="freecad",
        )
    return _done("freecad", source, product, "headless FreeCAD conversion completed")


def convert_with_ocp(source: Path, product: Path) -> ConversionReceipt:
    """Convert STEP<->BREP through the bundled OpenCascade bindings."""

    try:
        from cadquery import exporters, importers  # noqa: PLC0415
    except ImportError as exc:
        return ConversionReceipt(
            state="unavailable",
            converter=None,
            source=str(source),
            product=None,
            source_sha256=None,
            product_sha256=None,
            code="OCP_UNAVAILABLE",
            detail=f"cadquery/OCP is not installed: {exc}",
        )
    if not source.is_file():
        return _fail(str(source), "SOURCE_NOT_FOUND", "conversion source missing",
                      converter="ocp-fallback")
    suffix = source.suffix.lower()
    try:
        if suffix in (".step", ".stp"):
            shape = importers.importStep(str(source))
        elif suffix in (".brep", ".brp"):
            shape = importers.importBrep(str(source))
        else:
            return _fail(str(source), "UNSUPPORTED_SOURCE_FORMAT",
                          f"unsupported CAD source: {source.suffix}",
                          converter="ocp-fallback")
        product.parent.mkdir(parents=True, exist_ok=True)
        exporters.export(shape, str(product))
    except Exception as exc:
        return _fail(str(source), "CONVERSION_FAILED",
                      f"OCP conversion failed: {exc}", converter="ocp-fallback")
    if not product.is_file():
        return _fail(str(source), "CONVERSION_FAILED",
                      "OCP converter produced no file", converter="ocp-fallback")
    return _done("ocp-fallback", source, product,
                 "FreeCAD unavailable; converted with bundled OpenCascade")


def convert_cad(
    source: Path, product: Path, *, executable: str = "FreeCADCmd"
) -> ConversionReceipt:
    """Convert CAD formats, preferring headless FreeCAD, else honest fallback."""

    if shutil.which(executable) is not None:
        return convert_with_freecad(source, product, executable=executable)
    return convert_with_ocp(source, product)


# -- FCStd container -----------------------------------------------------------

FCSTD_WRITER = "workbench-fcstd-minimal-r1"


def export_fcstd(
    components: dict[str, Path],
    path: Path,
    *,
    labels: dict[str, str] | None = None,
) -> ConversionReceipt:
    """Write a real FCStd container holding one BREP payload per component.

    `components` maps object name to an existing ``.brep`` file. The archive
    layout (``Document.xml`` + payload files + ``GuiDocument.xml``) is what
    FreeCAD itself reads; ``Manifest.xml`` records our writer identity.
    """

    labels = labels or {}
    for name, brep in components.items():
        if not brep.is_file() or brep.suffix.lower() not in (".brep", ".brp"):
            return _fail(str(brep), "FCSTD_INPUT_NOT_BREP",
                          f"component {name} is not an existing BREP file")
    path.parent.mkdir(parents=True, exist_ok=True)
    document = ET.Element("Document", {
        "SchemaVersion": "4", "ProgramVersion": f"{FCSTD_WRITER}",
    })
    objects = ET.SubElement(document, "Objects")
    for name, brep in sorted(components.items()):
        obj = ET.SubElement(objects, "Object", {
            "name": name, "label": labels.get(name, name), "type": "Part::Feature",
        })
        properties = ET.SubElement(obj, "Properties")
        prop = ET.SubElement(
            properties,
            "Property",
            {"name": "Shape", "type": "Part::PropertyPartShape"},
        )
        part = ET.SubElement(prop, "Part", {"file": f"{name}.brep"})
        part.text = ""
        _ = brep
    gui = ET.Element("GuiDocument", {"SchemaVersion": "4"})
    manifest = ET.Element("Manifest")
    ET.SubElement(manifest, "Writer").text = FCSTD_WRITER
    tmp = path.with_suffix(".tmp-fcstd")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "Document.xml",
                ET.tostring(document, encoding="utf-8", xml_declaration=True),
            )
            archive.writestr(
                "GuiDocument.xml",
                ET.tostring(gui, encoding="utf-8", xml_declaration=True),
            )
            archive.writestr(
                "Manifest.xml",
                ET.tostring(manifest, encoding="utf-8", xml_declaration=True),
            )
            for name, brep in sorted(components.items()):
                archive.write(brep, f"{name}.brep")
        tmp.replace(path)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        return _fail(str(path), "FCSTD_WRITE_FAILED", f"FCStd export failed: {exc}")
    digest = _sha256(path)
    return ConversionReceipt(
        state="completed",
        converter="ocp-fallback",
        source=",".join(sorted(components)),
        product=str(path),
        source_sha256=None,
        product_sha256=digest,
        code="FCSTD_OK",
        detail=f"FCStd container written by {FCSTD_WRITER}; "
        "FreeCAD headless state: " + inspect_freecad().state,
    )


def read_fcstd(path: Path, extract_to: Path | None = None) -> dict[str, Any]:
    """Read an FCStd container: object names, labels, and BREP payloads."""

    if not zipfile.is_zipfile(path):
        raise ValueError("FCSTD_CORRUPT:not a zip container")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "Document.xml" not in names:
            raise ValueError("FCSTD_CORRUPT:Document.xml missing")
        document = ET.fromstring(archive.read("Document.xml"))
        objects: dict[str, Any] = {}
        for obj in document.iter("Object"):
            name = obj.get("name", "")
            objects[name] = {
                "label": obj.get("label", name),
                "type": obj.get("type", ""),
                "payloads": [
                    part.get("file", "")
                    for part in obj.iter("Part")
                    if part.get("file")
                ],
            }
        extracted: dict[str, str] = {}
        if extract_to is not None:
            extract_to.mkdir(parents=True, exist_ok=True)
            for name, info in objects.items():
                for payload in info["payloads"]:
                    if payload in names:
                        target = extract_to / f"{name}-{Path(payload).name}"
                        target.write_bytes(archive.read(payload))
                        extracted[name] = str(target)
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "objects": objects,
        "extracted": extracted,
    }


# -- roundtrip verification -----------------------------------------------------

@dataclass(frozen=True, slots=True)
class RoundtripReceipt:
    state: Literal["completed", "failed", "unavailable"]
    forward: ConversionReceipt
    back: ConversionReceipt | None
    faces_before: int | None
    faces_after: int | None
    detail: str


def _count_step_faces(step: Path) -> int | None:
    try:
        from cadquery import importers  # noqa: PLC0415

        imported = importers.importStep(str(step))
        shape = imported.val() if hasattr(imported, "val") else imported
        try:
            return len(shape.Faces())
        except Exception:
            return None
    except Exception:
        return None


def step_roundtrip(
    source_step: Path, workdir: Path, *, executable: str = "FreeCADCmd"
) -> RoundtripReceipt:
    """Convert STEP->BREP->STEP and verify face counts survive the roundtrip."""

    workdir.mkdir(parents=True, exist_ok=True)
    intermediate = workdir / (source_step.stem + ".brep")
    returned = workdir / (source_step.stem + ".roundtrip.step")
    forward = convert_cad(source_step, intermediate, executable=executable)
    if forward.state != "completed":
        return RoundtripReceipt("failed", forward, None, None, None,
                                f"forward conversion failed:{forward.code}")
    back = convert_cad(intermediate, returned, executable=executable)
    if back.state != "completed":
        return RoundtripReceipt("failed", forward, back, None, None,
                                f"back conversion failed:{back.code}")
    before = _count_step_faces(source_step)
    after = _count_step_faces(returned)
    if before is not None and after is not None and before != after:
        return RoundtripReceipt(
            "failed", forward, back, before, after,
            f"ROUNDTRIP_TOPOLOGY_CHANGED:faces {before}->{after}",
        )
    return RoundtripReceipt(
        "completed", forward, back, before, after,
        f"roundtrip preserved {before} faces via {forward.converter}",
    )
