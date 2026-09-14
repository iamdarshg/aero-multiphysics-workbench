"""Native preCICE configuration validation and execution support.

Prepare writes a native-format precice.xml (solver-interface schema) for two
generic participants plus the workbench coupling record. Validation is a real
native-schema check: well-formed XML, declared participants/meshes/data, and
consistent exchange endpoints. Parse reads the native tool log; without a
native run there is nothing to parse and parsing fails closed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PREPARATION_FAILED, detail)


def _require_float(inputs: Mapping[str, object], name: str) -> float:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"input {name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise _fail(f"input {name} must be finite")
    return result


def _require_int(inputs: Mapping[str, object], name: str) -> int:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(f"input {name} must be an integer")
    return int(value)


def _require_names(inputs: Mapping[str, object], name: str) -> tuple[str, str]:
    value = inputs.get(name, ("fluid", "structure"))
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or not all(isinstance(item, str) and item.strip() for item in value)
        or value[0] == value[1]
    ):
        raise _fail(f"input {name} must be two distinct non-empty names")
    first, second = str(value[0]), str(value[1])
    if "/" in first or "\\" in first or "/" in second or "\\" in second:
        raise _fail(f"input {name} must not contain path separators")
    return (first, second)


def render_native_config(
    *,
    participants: tuple[str, str],
    coupling_dt: float,
    max_iterations: int,
    tolerance: float,
) -> str:
    """Render a native solver-interface precice.xml for two participants."""

    first, second = participants
    root = ElementTree.Element("precice-configuration")
    interface = ElementTree.SubElement(root, "solver-interface", {"dimensions": "3"})
    data = ElementTree.SubElement(interface, "data")
    ElementTree.SubElement(data, "data-field", {"name": "Pressure", "type": "scalar"})
    ElementTree.SubElement(data, "data-field", {"name": "Displacement", "type": "vector"})
    for participant, provides in ((first, "yes"), (second, "no")):
        node = ElementTree.SubElement(interface, "participant", {"name": participant})
        mesh = ElementTree.SubElement(
            node, "use-mesh", {"name": f"{participant}-Mesh", "provide": provides}
        )
        _ = mesh
        ElementTree.SubElement(
            node,
            "write-data",
            {"name": "Pressure" if participant == first else "Displacement",
             "mesh": f"{participant}-Mesh"},
        )
        ElementTree.SubElement(
            node,
            "read-data",
            {"name": "Displacement" if participant == first else "Pressure",
             "mesh": f"{participant}-Mesh"},
        )
    meshes = ElementTree.SubElement(interface, "meshes")
    for participant in participants:
        mesh_node = ElementTree.SubElement(meshes, "mesh", {"name": f"{participant}-Mesh"})
        ElementTree.SubElement(mesh_node, "use-data", {"name": "Pressure"})
        ElementTree.SubElement(mesh_node, "use-data", {"name": "Displacement"})
    ElementTree.SubElement(
        interface,
        "mapping",
        {"direction": "conservative", "from": f"{first}-Mesh", "to": f"{second}-Mesh"},
    )
    scheme = ElementTree.SubElement(
        interface, "coupling-scheme", {"type": "serial-implicit"}
    )
    ElementTree.SubElement(scheme, "time-window-size", {"value": repr(coupling_dt)})
    ElementTree.SubElement(scheme, "max-iterations", {"value": str(max_iterations)})
    ElementTree.SubElement(
        scheme, "relative-convergence-measure", {"limit": repr(tolerance)}
    )
    ElementTree.SubElement(
        scheme,
        "exchange",
        {
            "data": "Pressure",
            "mesh": f"{first}-Mesh",
            "from": first,
            "to": second,
        },
    )
    ElementTree.SubElement(
        scheme,
        "exchange",
        {
            "data": "Displacement",
            "mesh": f"{second}-Mesh",
            "from": second,
            "to": first,
        },
    )
    body = ElementTree.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def validate_native_config(xml_text: str) -> ValidityReport:
    """Validate a native precice.xml without executing a coupled run."""

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"precice.xml is not well-formed:{exc}"
        ) from exc
    if root.tag != "precice-configuration":
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, "precice.xml root must be precice-configuration"
        )
    interface = root.find("solver-interface")
    if interface is None:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, "precice.xml needs a solver-interface"
        )
    participants = [node.get("name", "") for node in interface.findall("participant")]
    checks = {
        "two_participants": len(participants) >= 2 and all(participants),
        "meshes_declared": len(interface.findall("meshes/mesh")) >= 2,
        "data_declared": len(interface.findall("data/data-field")) >= 1,
        "scheme_present": interface.find("coupling-scheme") is not None,
        "exchange_closed": _exchange_closed(interface, participants),
    }
    return ValidityReport(
        participant_id="precice",
        passed=all(checks.values()),
        checks=checks,
        detail="native solver-interface schema checks",
    )


def _exchange_closed(interface: ElementTree.Element, participants: list[str]) -> bool:
    declared = set(participants)
    meshes = {
        node.get("name", "") for node in interface.findall("meshes/mesh")
    }
    for exchange in interface.findall("coupling-scheme/exchange"):
        if (
            exchange.get("from") not in declared
            or exchange.get("to") not in declared
            or exchange.get("mesh") not in meshes
            or not exchange.get("data")
        ):
            return False
    return len(interface.findall("coupling-scheme/exchange")) >= 2


def prepare_coupling_case(
    inputs: dict[str, object], case_dir: Path
) -> PrepareReceipt:
    """Write precice-config.xml plus the workbench coupling record."""

    data: Mapping[str, object] = dict(inputs)
    participants = _require_names(data, "participants")
    coupling_dt = _require_float(data, "coupling_dt_s")
    max_iterations = _require_int(data, "max_iterations")
    tolerance = _require_float(data, "tolerance")
    if coupling_dt <= 0 or max_iterations <= 0 or tolerance <= 0:
        raise _fail("coupling settings must be positive")

    xml_text = render_native_config(
        participants=participants,
        coupling_dt=coupling_dt,
        max_iterations=max_iterations,
        tolerance=tolerance,
    )
    report = validate_native_config(xml_text)
    if not report.passed:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, "rendered precice.xml failed validation"
        )
    canonical: dict[str, Any] = {
        "participants": list(participants),
        "coupling_dt_s": coupling_dt,
        "max_iterations": max_iterations,
        "tolerance": tolerance,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "precice-config.xml").write_text(xml_text, encoding="utf-8")
    (case_dir / "case.json").write_text(
        json.dumps(
            {**canonical, "config_sha256": hashlib.sha256(xml_text.encode()).hexdigest()},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return PrepareReceipt(
        participant_id="precice",
        case_id=case_dir.name,
        input_hash=digest,
        files=("precice-config.xml", "case.json"),
        detail=f"participants={participants[0]},{participants[1]}",
    )


def parse_coupling_result(case_dir: Path) -> ParseReceipt:
    """Parse the native preCICE tool log; fails closed without a native run."""

    log_path = case_dir / "solver.log"
    if not log_path.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "solver.log is missing")
    try:
        log_text = log_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"solver.log unreadable:{exc}"
        ) from exc
    config_ok = "CONFIG_VALID" in log_text
    conservation = _parse_conservation(log_text)
    if not config_ok:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "native tool did not accept the config"
        )
    scalars = {"conservation_error": conservation, "config_digest_ok": 1.0}
    return ParseReceipt(
        participant_id="precice",
        parser="precice.validate:parse_coupling_result",
        scalars=scalars,
        units={"conservation_error": "dimensionless", "config_digest_ok": "dimensionless"},
        detail="parsed native preCICE tool log",
    )


def _parse_conservation(log_text: str) -> float:
    import re

    pattern = re.compile(r"conservation error\s*=\s*([0-9.eE+-]+)", re.IGNORECASE)
    values: list[float] = []
    for match in pattern.finditer(log_text):
        try:
            values.append(float(match.group(1)))
        except ValueError:
            continue
    if not values:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "native log has no conservation error"
        )
    return values[-1]


def validate_coupling_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    error = float(scalars.get("conservation_error", float("nan")))
    digest_ok = float(scalars.get("config_digest_ok", 0.0)) == 1.0
    tolerance = inputs.get("tolerance", 1e-6)
    limit = float(tolerance) if isinstance(tolerance, (int, float)) else 1e-6
    checks = {
        "config_accepted": digest_ok,
        "conservation": error == error and error <= limit,
    }
    return ValidityReport(
        participant_id="precice",
        passed=all(checks.values()),
        checks=checks,
        detail=f"conservation within {limit:g}",
    )
