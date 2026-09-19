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
import re
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
            {
                "name": "Pressure" if participant == first else "Displacement",
                "mesh": f"{participant}-Mesh",
            },
        )
        ElementTree.SubElement(
            node,
            "read-data",
            {
                "name": "Displacement" if participant == first else "Pressure",
                "mesh": f"{participant}-Mesh",
            },
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
    scheme = ElementTree.SubElement(interface, "coupling-scheme", {"type": "serial-implicit"})
    ElementTree.SubElement(scheme, "time-window-size", {"value": repr(coupling_dt)})
    ElementTree.SubElement(scheme, "max-iterations", {"value": str(max_iterations)})
    ElementTree.SubElement(scheme, "relative-convergence-measure", {"limit": repr(tolerance)})
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
    meshes = {node.get("name", "") for node in interface.findall("meshes/mesh")}
    for exchange in interface.findall("coupling-scheme/exchange"):
        if (
            exchange.get("from") not in declared
            or exchange.get("to") not in declared
            or exchange.get("mesh") not in meshes
            or not exchange.get("data")
        ):
            return False
    return len(interface.findall("coupling-scheme/exchange")) >= 2


def prepare_coupling_case(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
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


# -- native coupled window (GEN 11) ------------------------------------------

_IDENTIFIER = __import__("re").compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")

_COUPLING_FIELDS = {"a_to_b": "Temperature", "b_to_a": "HeatFlux"}

NATIVE_WINDOW_RUN_SCRIPT = "run_precice.py"


def _require_identifier(inputs: Mapping[str, object], name: str, default: str) -> str:
    value = inputs.get(name, default)
    if not isinstance(value, str) or _IDENTIFIER.match(value) is None:
        raise _fail(f"input {name} must be an identifier")
    return value


def render_native_window_config(
    *,
    participants: tuple[str, str],
    a_to_b: str,
    b_to_a: str,
    coupling_dt: float,
    max_iterations: int,
    tolerance: float = 1e-6,
    dimensions: int = 2,
) -> str:
    """Render a preCICE v3 solver-interface config for a native implicit window."""

    first, second = participants
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<precice-configuration>\n"
        '  <log><sink type="stream" output="stdout" filter="%Severity%"/></log>\n'
        f'  <data:scalar name="{a_to_b}"/>\n'
        f'  <data:scalar name="{b_to_a}"/>\n'
        f'  <mesh name="{first}-Mesh" dimensions="{dimensions}">\n'
        f'    <use-data name="{a_to_b}"/><use-data name="{b_to_a}"/>\n'
        "  </mesh>\n"
        f'  <mesh name="{second}-Mesh" dimensions="{dimensions}">\n'
        f'    <use-data name="{a_to_b}"/><use-data name="{b_to_a}"/>\n'
        "  </mesh>\n"
        f'  <participant name="{first}">\n'
        f'    <provide-mesh name="{first}-Mesh"/>\n'
        f'    <receive-mesh name="{second}-Mesh" from="{second}"/>\n'
        f'    <write-data name="{a_to_b}" mesh="{first}-Mesh"/>\n'
        f'    <read-data name="{b_to_a}" mesh="{first}-Mesh"/>\n'
        "  </participant>\n"
        f'  <participant name="{second}">\n'
        f'    <provide-mesh name="{second}-Mesh"/>\n'
        f'    <receive-mesh name="{first}-Mesh" from="{first}"/>\n'
        f'    <read-data name="{a_to_b}" mesh="{second}-Mesh"/>\n'
        f'    <write-data name="{b_to_a}" mesh="{second}-Mesh"/>\n'
        f'    <mapping:nearest-neighbor direction="read" from="{first}-Mesh" '
        f'to="{second}-Mesh" constraint="consistent"/>\n'
        f'    <mapping:nearest-neighbor direction="write" from="{second}-Mesh" '
        f'to="{first}-Mesh" constraint="conservative"/>\n'
        "  </participant>\n"
        f'  <m2n:sockets exchange-directory="." acceptor="{first}" connector="{second}"/>\n'
        "  <coupling-scheme:serial-implicit>\n"
        f'    <participants first="{first}" second="{second}"/>\n'
        '    <max-time-windows value="3"/>\n'
        f'    <time-window-size value="{coupling_dt!r}"/>\n'
        f'    <max-iterations value="{max_iterations}"/>\n'
        f'    <relative-convergence-measure limit="{tolerance!r}" data="{a_to_b}" '
        f'mesh="{second}-Mesh"/>\n'
        f'    <exchange data="{a_to_b}" mesh="{first}-Mesh" from="{first}" to="{second}"/>\n'
        f'    <exchange data="{b_to_a}" mesh="{second}-Mesh" from="{second}" to="{first}"/>\n'
        "  </coupling-scheme:serial-implicit>\n"
        "</precice-configuration>\n"
    )


def validate_native_window_config(xml_text: str) -> ValidityReport:
    """Structural check for a preCICE v3 native coupling configuration.

    preCICE's namespaced tags (``data:scalar``, ``coupling-scheme:...``) use
    colons without an ``xmlns`` declaration, so the document is not
    namespace-well-formed for a strict XML parser. The native engine is the real
    validator at run time; here we assert the required schema elements exist.
    """

    if not xml_text.strip().startswith("<?xml"):
        raise _fail("native coupling config is missing an XML declaration")
    if "<precice-configuration>" not in xml_text:
        raise _fail("native coupling config root must be precice-configuration")
    participant_names = re.findall(r"<participant\s+name=\"([^\"]+)\"", xml_text)
    mesh_count = len(re.findall(r"<mesh\s", xml_text))
    data_count = len(re.findall(r"<data:scalar\s", xml_text))
    scheme = "coupling-scheme:serial-implicit" in xml_text
    exchanges = len(re.findall(r"<exchange\s", xml_text))
    checks = {
        "two_participants": len(participant_names) >= 2 and all(participant_names),
        "meshes_declared": mesh_count >= 2,
        "data_declared": data_count >= 2,
        "scheme_present": scheme,
        "exchange_closed": exchanges >= 2,
    }
    return ValidityReport(
        participant_id="precice",
        passed=all(checks.values()),
        checks=checks,
        detail="native preCICE v3 coupling-schema checks",
    )


def prepare_native_window(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    """Write a native preCICE v3 config plus the governed coupling record.

    The run script (``run_precice.py``) is copied into the case directory so the
    allowlisted command ``python run_precice.py`` executes with the case as cwd.
    Nothing is executed here; the engine is capability-gated at run time.
    """

    data: Mapping[str, object] = dict(inputs)
    participants = _require_names(data, "participants")
    coupling_dt = _require_float(data, "coupling_dt_s")
    max_iterations = _require_int(data, "max_iterations")
    tolerance = _require_float(data, "tolerance")
    if coupling_dt <= 0 or max_iterations <= 0 or tolerance <= 0:
        raise _fail("coupling settings must be positive")
    n_points_raw = data.get("n_interface_points", 8)
    if isinstance(n_points_raw, bool) or not isinstance(n_points_raw, int) or n_points_raw < 3:
        raise _fail("n_interface_points must be an integer >= 3")
    a_to_b = _require_identifier(data, "field_a_to_b", _COUPLING_FIELDS["a_to_b"])
    b_to_a = _require_identifier(data, "field_b_to_a", _COUPLING_FIELDS["b_to_a"])
    if a_to_b == b_to_a:
        raise _fail("field_a_to_b and field_b_to_a must differ")

    xml_text = render_native_window_config(
        participants=participants,
        a_to_b=a_to_b,
        b_to_a=b_to_a,
        coupling_dt=coupling_dt,
        max_iterations=max_iterations,
        tolerance=tolerance,
    )
    report = validate_native_window_config(xml_text)
    if not report.passed:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, "rendered native coupling config failed validation"
        )

    from . import backend as _backend

    script_source = _backend.run_script_source(NATIVE_WINDOW_RUN_SCRIPT)
    canonical: dict[str, Any] = {
        "participants": list(participants),
        "coupling_dt_s": coupling_dt,
        "max_iterations": max_iterations,
        "tolerance": tolerance,
        "n_interface_points": int(n_points_raw),
        "field_a_to_b": a_to_b,
        "field_b_to_a": b_to_a,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "precice-config.xml").write_text(xml_text, encoding="utf-8")
    (case_dir / "run_precice.py").write_text(script_source, encoding="utf-8")
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
        files=("precice-config.xml", "case.json", "run_precice.py"),
        detail=f"participants={participants[0]},{participants[1]} n={n_points_raw}",
    )


def parse_native_window_result(case_dir: Path) -> ParseReceipt:
    """Parse the native coupling evidence written by ``run_precice.py``."""

    result_path = case_dir / "result.json"
    if not result_path.is_file():
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, "native coupling result.json is missing"
        )
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"native coupling result.json unreadable:{exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "coupling result is not an object")
    if payload.get("engine") != "precice-native":
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED,
            f"coupling result engine is not native:{payload.get('engine')!r}",
        )
    if payload.get("coupling_completed") is not True:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED,
            f"native coupling did not complete:{payload.get('detail', 'unknown')}",
        )

    def _number(key: str) -> float:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ParticipantError(
                NativeErrorCode.PARSER_FAILED, f"coupling result missing numeric {key}"
            )
        return float(value)

    scalars = {
        "interface_residual": _number("interface_residual"),
        "conservation_error": _number("conservation_error"),
        "coupling_iterations": _number("coupling_iterations"),
        "checkpoints": _number("checkpoints"),
        "rollbacks": _number("rollbacks"),
        "coupled_converged": 1.0 if payload.get("converged") is True else 0.0,
    }
    units = {
        "interface_residual": "dimensionless",
        "conservation_error": "dimensionless",
        "coupling_iterations": "dimensionless",
        "checkpoints": "dimensionless",
        "rollbacks": "dimensionless",
        "coupled_converged": "dimensionless",
    }
    return ParseReceipt(
        participant_id="precice",
        parser="precice.validate:parse_native_window_result",
        scalars=scalars,
        units=units,
        detail=(
            f"native preCICE window: iterations={int(scalars['coupling_iterations'])} "
            f"residual={scalars['interface_residual']:.3e}"
        ),
    )


def validate_native_window_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    """A native coupled window publishes only on convergence and conservation."""

    tolerance = inputs.get("tolerance", 1e-6)
    limit = float(tolerance) if isinstance(tolerance, (int, float)) and tolerance > 0 else 1e-6
    residual = float(scalars.get("interface_residual", float("nan")))
    conservation = float(scalars.get("conservation_error", float("nan")))
    converged = float(scalars.get("coupled_converged", 0.0)) == 1.0
    checks = {
        "completed": int(scalars.get("coupling_iterations", 0)) >= 1,
        "converged": converged,
        "residual_within_tolerance": residual == residual and residual <= limit,
        "interface_conservation": conservation == conservation and conservation <= limit,
    }
    return ValidityReport(
        participant_id="precice",
        passed=all(checks.values()),
        checks=checks,
        detail=(
            f"native implicit coupling residual {residual:.3e} and conservation "
            f"{conservation:.3e} within {limit:g}"
        ),
    )
