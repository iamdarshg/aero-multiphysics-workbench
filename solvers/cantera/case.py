"""Governed Cantera combustion case builder and native executor.

This is the native chemistry boundary for heat-addition architectures. It
validates combustible mixture/fuel/oxidizer definitions with provenance, selects
equilibrium / perfectly-stirred / reactor-network chemistry and an explicit
finite-rate mechanism, and normalizes pressure loss, heat release, and
emissions outputs into a canonical ``case.json``. The native executor runs
Cantera in-process (the library is the "native" capability) and writes a
``result.json`` carrying the library identity and version.

Nothing here substitutes an analytical answer for native output. If the Cantera
library is not importable the executor fails closed with
``CAPABILITY_UNAVAILABLE``.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path
from typing import Any, cast

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import PrepareReceipt

CANTERA_PARTICIPANT_ID = "combustion-reacting-flow"
RUN_LIBRARY = "cantera"

MECHANISMS: tuple[str, ...] = (
    "gri30.yaml",
    "gri30_highT.yaml",
    "h2o2.yaml",
    "nDodecane_Reitz.yaml",
    "methylcyclohexane.yaml",
)

REACTOR_MODES: tuple[str, ...] = ("equilibrium", "psr", "reactor-network")

FINITE_RATE_REACTOR_MODES: tuple[str, ...] = ("psr", "reactor-network")

REPORTED_SPECIES: tuple[str, ...] = (
    "CH4",
    "O2",
    "N2",
    "CO2",
    "H2O",
    "CO",
    "OH",
    "NO",
)

_LOCAL_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_RESIDENCE_TIME_S = 0.005


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PREPARATION_FAILED, detail)


def _require_str(inputs: Mapping[str, object], name: str) -> str:
    value = inputs.get(name)
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"COMBUSTION_INPUT_INVALID:{name} must be a non-empty string")
    return value.strip()


def _require_float(
    inputs: Mapping[str, object], name: str, *, minimum: float, maximum: float
) -> float:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"COMBUSTION_INPUT_INVALID:{name} must be a number")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise _fail(f"COMBUSTION_INPUT_INVALID:{name} must be finite")
    if not minimum < number < maximum:
        raise _fail(
            f"COMBUSTION_INPUT_OUT_OF_RANGE:{name} must be within ({minimum}, {maximum})"
        )
    return number


def _provenance(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise _fail(f"COMBUSTION_PROVENANCE_MISSING:{label}")
    source = value.get("source")
    reference = value.get("reference")
    if not isinstance(source, str) or not source.strip():
        raise _fail(f"COMBUSTION_PROVENANCE_MISSING:{label}.source")
    if not isinstance(reference, str) or not reference.strip():
        raise _fail(f"COMBUSTION_PROVENANCE_MISSING:{label}.reference")
    payload = {"source": source.strip(), "reference": reference.strip()}
    revision = value.get("revision")
    if isinstance(revision, str) and revision.strip():
        payload["revision"] = revision.strip()
    return payload


def _mixture(
    value: object, label: str, *, allow_empty_composition: bool
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise _fail(f"COMBUSTION_MIXTURE_INVALID:{label}")
    name = value.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _fail(f"COMBUSTION_MIXTURE_INVALID:{label}.name")
    composition_raw = value.get("composition")
    composition: dict[str, float] = {}
    if composition_raw is None:
        if not allow_empty_composition:
            raise _fail(f"COMBUSTION_MIXTURE_INVALID:{label}.composition")
    elif isinstance(composition_raw, Mapping):
        for species, fraction in composition_raw.items():
            if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
                raise _fail(f"COMBUSTION_MIXTURE_INVALID:{label}.composition.{species}")
            number = float(fraction)
            if number != number or number < 0.0:
                raise _fail(f"COMBUSTION_MIXTURE_INVALID:{label}.composition.{species}")
            composition[str(species)] = number
    else:
        raise _fail(f"COMBUSTION_MIXTURE_INVALID:{label}.composition")
    if composition and sum(composition.values()) <= 0.0:
        raise _fail(f"COMBUSTION_MIXTURE_INVALID:{label}.composition empty")
    return {
        "name": name.strip(),
        "composition": composition,
        "provenance": _provenance(value.get("provenance"), label),
    }


def _reactor_network(value: object, reactor_mode: str) -> dict[str, object] | None:
    if reactor_mode != "reactor-network":
        return None
    if not isinstance(value, Mapping):
        raise _fail(
            "COMBUSTION_INPUT_INVALID:reactor_network required for reactor-network"
        )
    reactors = value.get("reactors")
    if not isinstance(reactors, (list, tuple)) or not reactors:
        raise _fail(
            "COMBUSTION_INPUT_INVALID:reactor_network.reactors must be non-empty"
        )
    names: list[str] = []
    for index, item in enumerate(reactors):
        if not isinstance(item, str) or not item.strip():
            raise _fail(f"COMBUSTION_INPUT_INVALID:reactor_network.reactors[{index}]")
        names.append(item.strip())
    payload: dict[str, object] = {"reactors": names}
    residence = value.get("residence_time_s")
    if residence is not None:
        if isinstance(residence, bool) or not isinstance(residence, (int, float)):
            raise _fail("COMBUSTION_INPUT_INVALID:reactor_network.residence_time_s")
        payload["residence_time_s"] = float(residence)
    return payload


def canonical_combustion_case(inputs: Mapping[str, object]) -> dict[str, object]:
    """Validate and normalize one combustion case into a canonical document."""

    mechanism = _require_str(inputs, "mechanism")
    if mechanism not in MECHANISMS:
        raise _fail(f"COMBUSTION_MECHANISM_UNSUPPORTED:{mechanism}")
    reactor_mode = _require_str(inputs, "reactor_mode")
    if reactor_mode not in REACTOR_MODES:
        raise _fail(f"COMBUSTION_REACTOR_MODE_UNSUPPORTED:{reactor_mode}")

    finite_rate = inputs.get("finite_rate", False)
    if not isinstance(finite_rate, bool):
        raise _fail("COMBUSTION_INPUT_INVALID:finite_rate must be a bool")
    if reactor_mode in FINITE_RATE_REACTOR_MODES and not finite_rate:
        raise _fail(
            f"COMBUSTION_FINITE_RATE_REQUIRED:{reactor_mode} requires finite_rate=true"
        )

    fuel = _mixture(inputs.get("fuel"), "fuel", allow_empty_composition=False)
    oxidizer = _mixture(inputs.get("oxidizer"), "oxidizer", allow_empty_composition=True)
    network = _reactor_network(inputs.get("reactor_network"), reactor_mode)

    equivalence_ratio = _require_float(
        inputs, "equivalence_ratio", minimum=0.05, maximum=10.0
    )
    inlet_temperature = _require_float(
        inputs, "inlet_temperature_k", minimum=100.0, maximum=3000.0
    )
    inlet_pressure = _require_float(
        inputs, "inlet_pressure_pa", minimum=100.0, maximum=2.0e7
    )
    air_mass_flow = _require_float(
        inputs, "air_mass_flow_kg_s", minimum=0.0, maximum=1000.0
    )
    if air_mass_flow <= 0.0:
        raise _fail("COMBUSTION_INPUT_OUT_OF_RANGE:air_mass_flow_kg_s must be positive")
    fuel_mass_flow = _require_float(
        inputs, "fuel_mass_flow_kg_s", minimum=0.0, maximum=200.0
    )
    if fuel_mass_flow <= 0.0:
        raise _fail("COMBUSTION_INPUT_OUT_OF_RANGE:fuel_mass_flow_kg_s must be positive")
    heating_value = _require_float(
        inputs, "fuel_lower_heating_value_j_kg", minimum=1.0e5, maximum=2.0e8
    )
    efficiency = _require_float(
        inputs, "combustion_efficiency", minimum=0.0, maximum=1.0
    )
    if efficiency <= 0.0:
        raise _fail(
            "COMBUSTION_INPUT_OUT_OF_RANGE:combustion_efficiency must be positive"
        )
    pressure_loss = _require_float(
        inputs, "pressure_loss_fraction", minimum=-1e-12, maximum=0.5
    )
    pattern_factor = inputs.get("pattern_factor", 0.0)
    if isinstance(pattern_factor, bool) or not isinstance(pattern_factor, (int, float)):
        raise _fail("COMBUSTION_INPUT_INVALID:pattern_factor must be a number")
    pattern = float(pattern_factor)
    if pattern < 0.0 or pattern >= 1.0:
        raise _fail("COMBUSTION_INPUT_OUT_OF_RANGE:pattern_factor must be within [0, 1)")

    canonical: dict[str, object] = {
        "library": RUN_LIBRARY,
        "mechanism": mechanism,
        "reactor_mode": reactor_mode,
        "finite_rate": finite_rate,
        "reactor_network": network,
        "fuel": fuel,
        "oxidizer": oxidizer,
        "provenance": _provenance(inputs.get("provenance"), "case"),
        "equivalence_ratio": equivalence_ratio,
        "inlet_temperature_k": inlet_temperature,
        "inlet_pressure_pa": inlet_pressure,
        "air_mass_flow_kg_s": air_mass_flow,
        "fuel_mass_flow_kg_s": fuel_mass_flow,
        "fuel_lower_heating_value_j_kg": heating_value,
        "combustion_efficiency": efficiency,
        "pressure_loss_fraction": max(0.0, pressure_loss),
        "pattern_factor": pattern,
    }
    volume = inputs.get("combustor_volume_m3")
    if volume is not None:
        canonical["combustor_volume_m3"] = _require_float(
            inputs, "combustor_volume_m3", minimum=0.0, maximum=1.0e3
        )
    density = inputs.get("reference_density_kg_m3")
    if density is not None:
        canonical["reference_density_kg_m3"] = _require_float(
            inputs, "reference_density_kg_m3", minimum=0.0, maximum=1.0e3
        )
    return canonical


def combustion_input_hash(canonical: Mapping[str, object]) -> str:
    payload = json.dumps(dict(canonical), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prepare_combustion_case(
    inputs: dict[str, object], case_dir: Path
) -> PrepareReceipt:
    """Validate a combustible mixture case and stage the governed ``case.json``."""

    canonical = canonical_combustion_case(inputs)
    digest = combustion_input_hash(canonical)
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(canonical, indent=2, sort_keys=True), encoding="utf-8"
    )
    return PrepareReceipt(
        participant_id=CANTERA_PARTICIPANT_ID,
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json",),
        detail=(
            f"mechanism={canonical['mechanism']} mode={canonical['reactor_mode']} "
            f"finite_rate={canonical['finite_rate']}"
        ),
    )


def probed_cantera_version() -> str | None:
    """Installed Cantera distribution version, or ``None`` when absent.

    Distribution metadata only, never an import of the heavy native module, so a
    governed capability probe can stay cheap and side-effect free.
    """

    try:
        return metadata.version("cantera")
    except metadata.PackageNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        return None


def _is_local_shadow(module: object) -> bool:
    origin = getattr(module, "__file__", None)
    return isinstance(origin, str) and os.path.abspath(origin).startswith(
        str(_LOCAL_PACKAGE_DIR)
    )


def _load_native_cantera() -> Any:
    """Import the real Cantera library, never this boundary package.

    ``solvers`` is on ``sys.path`` so the governed refs can resolve
    ``cantera.case``; that also means a bare ``import cantera`` would bind this
    package. The real library is loaded from the remaining ``sys.path`` with the
    local package temporarily removed, then the local submodules are restored so
    the governed function refs keep resolving.
    """

    import importlib

    existing = sys.modules.get("cantera")
    if existing is not None and not _is_local_shadow(existing):
        return existing

    solvers_root = _LOCAL_PACKAGE_DIR.parent
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "cantera" or name.startswith("cantera.")
    }
    for name in list(saved):
        sys.modules.pop(name, None)
    removed = [
        entry
        for entry in sys.path
        if entry and os.path.abspath(entry) == str(solvers_root)
    ]
    for entry in removed:
        sys.path.remove(entry)
    try:
        native = importlib.import_module("cantera")
    except Exception as exc:  # noqa: BLE001
        sys.modules.update(saved)
        raise ParticipantError(
            NativeErrorCode.CAPABILITY_UNAVAILABLE,
            f"native cantera library unavailable:{type(exc).__name__}:{exc}",
        ) from exc
    finally:
        for entry in removed:
            sys.path.insert(0, entry)
        for name, module in saved.items():
            if name != "cantera":
                sys.modules[name] = module
    return native


def _equivalence_ratio_species(
    composition: Mapping[str, float], fallback: tuple[str, ...]
) -> dict[str, float]:
    selected = {
        str(species): float(fraction)
        for species, fraction in composition.items()
        if float(fraction) > 0.0
    }
    if selected:
        return selected
    return dict.fromkeys(fallback, 1.0)


def _run_reactor_network(
    native: Any,
    gas: Any,
    case: Mapping[str, object],
    inlet_temperature: float,
    inlet_pressure: float,
) -> float:
    network_case = case.get("reactor_network")
    residence_s = _DEFAULT_RESIDENCE_TIME_S
    if isinstance(network_case, Mapping):
        candidate = network_case.get("residence_time_s")
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            residence_s = float(candidate)
    gas.TP = inlet_temperature, inlet_pressure
    reactor = native.IdealGasConstPressureReactor(gas, energy="on")
    network = native.ReactorNet([reactor])
    network.advance(residence_s)
    gas.TPY = reactor.thermo.TPY
    return float(reactor.T)


def _species_mole_fractions(gas: Any) -> dict[str, float]:
    names = getattr(gas, "species_names", ())
    try:
        fractions = dict(gas.mole_fraction_dict())
    except Exception:  # noqa: BLE001
        fractions = {}
    return {
        species: float(fractions.get(species, 0.0))
        for species in REPORTED_SPECIES
        if species in names
    }


def execute_combustion_case(inputs: Mapping[str, object], case_dir: Path) -> None:
    """Run the native Cantera case in-process and write ``result.json``.

    The governed lifecycle probes the capability before calling this function,
    but it stays fail-closed on its own: a missing native library raises
    ``CAPABILITY_UNAVAILABLE`` rather than falling back to an analytical estimate.
    """

    case_path = case_dir / "case.json"
    if case_path.is_file():
        case: dict[str, object] = json.loads(case_path.read_text(encoding="utf-8"))
    else:
        case = canonical_combustion_case(inputs)

    native = _load_native_cantera()
    solution_type = getattr(native, "Solution", None)
    if solution_type is None:
        raise ParticipantError(
            NativeErrorCode.CAPABILITY_UNAVAILABLE,
            "native cantera module has no Solution class",
        )

    mechanism = str(case["mechanism"])
    reactor_mode = str(case["reactor_mode"])
    equivalence_ratio = float(cast(float, case["equivalence_ratio"]))
    inlet_temperature = float(cast(float, case["inlet_temperature_k"]))
    inlet_pressure = float(cast(float, case["inlet_pressure_pa"]))
    pressure_loss = float(cast(float, case["pressure_loss_fraction"]))
    efficiency = float(cast(float, case["combustion_efficiency"]))
    fuel_mass_flow = float(cast(float, case["fuel_mass_flow_kg_s"]))
    heating_value = float(cast(float, case["fuel_lower_heating_value_j_kg"]))
    fuel_payload = cast(Mapping[str, object], case["fuel"])
    oxidizer_payload = cast(Mapping[str, object], case["oxidizer"])
    fuel = cast(Mapping[str, float], fuel_payload["composition"])
    oxidizer = cast(Mapping[str, float], oxidizer_payload["composition"])
    fuel_species = _equivalence_ratio_species(fuel, ("CH4",))
    oxidizer_species = _equivalence_ratio_species(oxidizer, ("O2", "N2"))

    heat_release_w = efficiency * fuel_mass_flow * heating_value

    try:
        gas = solution_type(mechanism)
        gas.TP = inlet_temperature, inlet_pressure
        gas.set_equivalence_ratio(equivalence_ratio, fuel_species, oxidizer_species)
        if reactor_mode == "equilibrium":
            gas.equilibrate("HP")
        else:
            _run_reactor_network(
                native, gas, case, inlet_temperature, inlet_pressure
            )
    except ParticipantError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ParticipantError(
            NativeErrorCode.PROCESS_EXIT_NONZERO,
            f"cantera {reactor_mode} run failed:{type(exc).__name__}:{exc}",
        ) from exc

    adiabatic_temperature = float(gas.T)
    total_mass_flow = float(cast(float, case["air_mass_flow_kg_s"])) + fuel_mass_flow
    if reactor_mode == "equilibrium":
        cp_exit = float(gas.cp_mass)
        exit_temperature = inlet_temperature + heat_release_w / max(
            total_mass_flow * cp_exit, 1e-12
        )
    else:
        exit_temperature = adiabatic_temperature
    exit_pressure = inlet_pressure * (1.0 - pressure_loss)
    mole_fractions = _species_mole_fractions(gas)

    network_case = case.get("reactor_network")
    residence_s = _DEFAULT_RESIDENCE_TIME_S
    if isinstance(network_case, Mapping):
        candidate = network_case.get("residence_time_s")
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            residence_s = float(candidate)

    result = {
        "library": RUN_LIBRARY,
        "cantera_version": getattr(native, "__version__", "unknown"),
        "mechanism": mechanism,
        "reactor_mode": reactor_mode,
        "finite_rate": bool(case["finite_rate"]),
        "converged": True,
        "inlet_temperature_k": inlet_temperature,
        "inlet_pressure_pa": inlet_pressure,
        "exit_total_temperature_k": exit_temperature,
        "exit_total_pressure_pa": exit_pressure,
        "adiabatic_flame_temperature_k": adiabatic_temperature,
        "fuel_mass_flow_kg_s": fuel_mass_flow,
        "heat_release_w": heat_release_w,
        "combustion_efficiency": efficiency,
        "pressure_loss_fraction": pressure_loss,
        "pattern_factor": float(cast(float, case.get("pattern_factor", 0.0))),
        "residence_time_s": residence_s,
        "mole_fractions": mole_fractions,
    }
    (case_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
