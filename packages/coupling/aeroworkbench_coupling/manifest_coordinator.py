"""Real OpenMDAO-backed scalar coordinator built from participant declarations.

The dependency-light fixed-point loop in ``openmdao_problem.py`` remains
available as an explicitly labelled fallback/screening solver; everything in
this module executes through an actual ``openmdao.api.Problem`` and labels
itself ``engine="openmdao"`` with the measured OpenMDAO version.

Participant graphs are arbitrary: any number of participants, explicit
coupling links between scalar ports, shared/promoted design inputs, and
cyclic dependencies resolved by a real nonlinear solver (Block-Gauss-Seidel
or Newton with a linear solver where required).

Units are enforced by the adapter (see ``units.py``); OpenMDAO itself carries
plain floats so vendor-specific unit spellings (``Pa.s``, ``W/m.K``,
``A.h``) never reach the OpenMDAO unit library. Every link records the
source unit and converts into the target participant's declared unit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite

from participants.manifest import ParticipantManifest

from .units import convert_value, units_compatible

ScalarFunction = Callable[[Mapping[str, float]], Mapping[str, float]]
ClosureFunction = Callable[[Mapping[str, float]], float]


@dataclass(frozen=True, slots=True)
class VariableSpec:
    """One scalar variable with units and an initial guess."""

    name: str
    unit: str
    initial: float = 0.0


@dataclass(frozen=True, slots=True)
class ScalarParticipantSpec:
    """One participant's scalar contract plus its evaluation function."""

    participant_id: str
    physics_domain: str
    fidelity: str
    solver_identity: str
    solver_version: str
    inputs: tuple[VariableSpec, ...]
    outputs: tuple[VariableSpec, ...]
    function: ScalarFunction


@dataclass(frozen=True, slots=True)
class CouplingLink:
    """Explicit directed connection between two scalar ports."""

    source: str
    source_var: str
    target: str
    target_var: str


@dataclass(frozen=True, slots=True)
class CoordinatorPolicy:
    """Nonlinear/linear solver settings derived from the coupling policy."""

    nonlinear_solver: str = "block-gs"  # "block-gs" | "newton"
    linear_solver: str = "direct"  # "direct" | "none"
    tolerance: float = 1e-6
    max_iterations: int = 50
    relaxation: float = 1.0  # 1.0 is direct substitution; <1 enables Aitken relaxation

    def __post_init__(self) -> None:
        if self.nonlinear_solver not in {"block-gs", "newton"}:
            raise ValueError(f"UNKNOWN_NONLINEAR_SOLVER:{self.nonlinear_solver}")
        if self.linear_solver not in {"direct", "none"}:
            raise ValueError(f"UNKNOWN_LINEAR_SOLVER:{self.linear_solver}")
        if not isfinite(self.tolerance) or self.tolerance <= 0:
            raise ValueError("INVALID_COORDINATOR_TOLERANCE")
        if self.max_iterations <= 0:
            raise ValueError("INVALID_COORDINATOR_MAX_ITERATIONS")
        if not 0.0 < self.relaxation <= 1.0:
            raise ValueError("INVALID_COORDINATOR_RELAXATION")


@dataclass(frozen=True, slots=True)
class IterationRecord:
    iteration: int
    values: tuple[tuple[str, float], ...]
    residual: float


@dataclass(frozen=True, slots=True)
class CoordinatorResult:
    values: tuple[tuple[str, float], ...]
    iterations: int
    converged: bool
    residual_norm: float
    closure_residual: float
    engine: str
    solver_name: str
    openmdao_version: str
    history: tuple[IterationRecord, ...]
    checkpoint: str
    detail: str


@dataclass(frozen=True, slots=True)
class CoordinatorCheckpoint:
    digest: str
    values: tuple[tuple[str, float], ...]
    iterations: int


def _sanitize(name: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in name)


def _as_float(value: object) -> float:
    """Extract a Python float from an OpenMDAO scalar (ndarray or scalar)."""
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return float(item())
        except (ValueError, TypeError):
            pass
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise ValueError("EXPECTED_SCALAR_VALUE")
        return _as_float(value[0])
    return float(value)  # type: ignore[arg-type]


def participant_from_manifest(
    manifest: ParticipantManifest, function: ScalarFunction
) -> ScalarParticipantSpec:
    """Derive a scalar participant spec from a ParticipantManifest declaration.

    Only ``float`` scalar ports participate; integer/boolean/string ports and
    field ports fail closed because the scalar coordinator cannot drive them.
    """

    participant_id = str(manifest.participant_id)
    inputs: list[VariableSpec] = []
    for port in manifest.inputs:
        if str(port.kind) != "scalar":
            continue
        if str(port.data_type) != "float":
            raise ValueError(f"NONFLOAT_PORT_NOT_SUPPORTED:{participant_id}:{port.name}")
        inputs.append(VariableSpec(str(port.name), str(port.unit)))
    outputs: list[VariableSpec] = []
    for port in manifest.outputs:
        if str(port.kind) != "scalar":
            continue
        if str(port.data_type) != "float":
            raise ValueError(f"NONFLOAT_PORT_NOT_SUPPORTED:{participant_id}:{port.name}")
        outputs.append(VariableSpec(str(port.name), str(port.unit)))
    if not outputs:
        raise ValueError(f"PARTICIPANT_HAS_NO_SCALAR_OUTPUT:{participant_id}")
    return ScalarParticipantSpec(
        participant_id=participant_id,
        physics_domain=str(manifest.physics_domain),
        fidelity=";".join(manifest.fidelity_levels),
        solver_identity=str(manifest.executable.solver_id),
        solver_version="declared-by-manifest",
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        function=function,
    )


def _checkpoint_digest(values: Mapping[str, float], iterations: int) -> str:
    payload = json.dumps(
        {"iterations": iterations, "values": dict(sorted(values.items()))},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ManifestCoordinator:
    """Coordinate arbitrary scalar participant graphs with real OpenMDAO."""

    def __init__(
        self,
        participants: tuple[ScalarParticipantSpec, ...],
        links: tuple[CouplingLink, ...] = (),
        policy: CoordinatorPolicy | None = None,
        *,
        shared: tuple[str, ...] = (),
        closure: ClosureFunction | None = None,
    ) -> None:
        names = [participant.participant_id for participant in participants]
        if not participants or len(set(names)) != len(names):
            raise ValueError("PARTICIPANTS_REQUIRED_AND_UNIQUE")
        self._participants = {
            participant.participant_id: participant for participant in participants
        }
        self._policy = policy or CoordinatorPolicy()
        self._shared = tuple(shared)
        if len(set(self._shared)) != len(self._shared):
            raise ValueError("DUPLICATE_SHARED_INPUT")
        for name in self._shared:
            if not name.strip() or "." in name:
                raise ValueError(f"INVALID_SHARED_INPUT:{name}")
        for participant in participants:
            for var in (*participant.inputs, *participant.outputs):
                if not var.name.strip():
                    raise ValueError(f"VARIABLE_NAME_REQUIRED:{participant.participant_id}")
        self._closure = closure or (lambda _state: 0.0)
        self._links = tuple(links)
        # Validate links and record per-target connection units.
        self._targets: dict[tuple[str, str], tuple[str, str]] = {}
        for link in self._links:
            try:
                source = self._participants[link.source]
                target = self._participants[link.target]
            except KeyError:
                raise ValueError(
                    f"UNKNOWN_LINK_ENDPOINT:{link.source}.{link.source_var}"
                    f"->{link.target}.{link.target_var}"
                ) from None
            source_units = {var.name: var.unit for var in source.outputs}
            target_units = {var.name: var.unit for var in target.inputs}
            if link.source_var not in source_units:
                raise ValueError(f"UNKNOWN_LINK_SOURCE:{link.source}.{link.source_var}")
            if link.target_var not in target_units:
                raise ValueError(f"UNKNOWN_LINK_TARGET:{link.target}.{link.target_var}")
            key = (link.target, link.target_var)
            if key in self._targets:
                raise ValueError(f"CONFLICTING_LINK:{link.target}.{link.target_var}")
            source_unit = source_units[link.source_var]
            target_unit = target_units[link.target_var]
            if not units_compatible(source_unit, target_unit):
                raise ValueError(f"UNIT_MISMATCH:{source_unit}:{target_unit}")
            self._targets[key] = (link.source, link.source_var)
        for participant in participants:
            for var in participant.inputs:
                driven = (participant.participant_id, var.name) in self._targets
                if var.name in self._shared and driven:
                    raise ValueError(
                        f"SHARED_INPUT_IS_DRIVEN:{participant.participant_id}.{var.name}"
                    )
        for name in self._shared:
            declarers = [
                participant.participant_id
                for participant in participants
                if any(var.name == name for var in participant.inputs)
            ]
            if len(declarers) < 2:
                raise ValueError(f"SHARED_INPUT_NEEDS_TWO_DECLARERS:{name}")
            units = {
                var.unit
                for participant in participants
                if participant.participant_id in declarers
                for var in participant.inputs
                if var.name == name
            }
            first_unit = next(iter(units))
            if any(not units_compatible(unit, first_unit) for unit in units):
                raise ValueError(f"SHARED_INPUT_UNIT_MISMATCH:{name}")

    @property
    def policy(self) -> CoordinatorPolicy:
        return self._policy

    def checkpoint_of(self, result: CoordinatorResult) -> CoordinatorCheckpoint:
        return CoordinatorCheckpoint(result.checkpoint, result.values, result.iterations)

    def solve(
        self,
        initial: Mapping[str, float],
        *,
        warm_start: CoordinatorCheckpoint | None = None,
    ) -> CoordinatorResult:
        """Execute the coupled problem through OpenMDAO and return the result."""

        from importlib import metadata as _metadata

        import openmdao.api as om  # function-local: keeps module import light

        openmdao_version = _metadata.version("openmdao")
        start_values = self._resolve_start_values(initial, warm_start)
        problem, comp_paths, indep_map, output_paths = self._build_problem(om, start_values)
        problem.setup()
        for path, value in start_values["set"].items():
            problem.set_val(path, value)
        policy = self._policy
        history: list[IterationRecord] = []
        current = self._initial_values(start_values)
        history.append(IterationRecord(0, tuple(sorted(current.items())), float("inf")))
        residual = float("inf")
        iteration = 0
        for step in range(1, policy.max_iterations + 1):
            iteration = step
            problem.run_model()
            current = self._read_values(problem, comp_paths, indep_map, output_paths)
            previous = dict(history[-1].values)
            keys = set(current) | set(previous)
            residual = max(abs(current[key] - previous.get(key, 0.0)) for key in keys)
            history.append(
                IterationRecord(step, tuple(sorted(current.items())), residual)
            )
            if residual <= policy.tolerance:
                break
        closure_residual = abs(float(self._closure(dict(current))))
        if not isfinite(closure_residual):
            raise ValueError("NONFINITE_CLOSURE_RESIDUAL")
        converged = residual <= policy.tolerance and closure_residual <= policy.tolerance
        if converged:
            detail = f"converged in {iteration} openmdao sweeps"
        elif residual > policy.tolerance:
            detail = f"interface residual {residual:.3g} above tolerance after {iteration} sweeps"
        else:
            detail = f"energy closure {closure_residual:.3g} blocked acceptance"
        return CoordinatorResult(
            values=tuple(sorted(current.items())),
            iterations=iteration,
            converged=converged,
            residual_norm=residual,
            closure_residual=closure_residual,
            engine="openmdao",
            solver_name=self._solver_name(),
            openmdao_version=openmdao_version,
            history=tuple(history),
            checkpoint=_checkpoint_digest(current, iteration),
            detail=detail,
        )

    def _solver_name(self) -> str:
        if self._policy.nonlinear_solver == "newton":
            return "NewtonSolver+DirectSolver"
        return "NonlinearBlockGS"

    def _resolve_start_values(
        self,
        initial: Mapping[str, float],
        warm_start: CoordinatorCheckpoint | None,
    ) -> dict[str, dict[str, float]]:
        """Resolve every driven value; keys are OpenMDAO paths (filled later)."""

        driven_inputs = set(self._targets)
        needed_indep: dict[str, str] = {}
        for participant in self._participants.values():
            for var in participant.inputs:
                if (participant.participant_id, var.name) in driven_inputs:
                    continue
                if var.name in self._shared:
                    needed_indep[var.name] = var.name
                else:
                    needed_indep[f"{participant.participant_id}.{var.name}"] = (
                        f"{participant.participant_id}.{var.name}"
                    )
        allowed = set(needed_indep)
        provided = set(initial)
        unknown = provided - allowed
        if unknown:
            raise ValueError(f"UNKNOWN_INITIAL_VARIABLE:{sorted(unknown)[0]}")
        missing = allowed - provided
        warmed = dict(warm_start.values) if warm_start is not None else {}
        if warm_start is None and missing:
            raise ValueError(f"MISSING_INITIAL_VALUE:{sorted(missing)[0]}")
        resolved: dict[str, float] = {}
        for key in needed_indep:
            if key in initial:
                value = float(initial[key])
            elif key in warmed:
                value = float(warmed[key])
            else:
                raise ValueError(f"MISSING_INITIAL_VALUE:{key}")
            if not isfinite(value):
                raise ValueError("NONFINITE_INITIAL_STATE")
            resolved[key] = value
        output_guesses: dict[str, float] = {}
        for participant in self._participants.values():
            for var in participant.outputs:
                qualified = f"{participant.participant_id}.{var.name}"
                guess = float(warmed[qualified]) if qualified in warmed else float(var.initial)
                if not isfinite(guess):
                    raise ValueError("NONFINITE_INITIAL_STATE")
                output_guesses[qualified] = guess
        return {"indep": resolved, "outputs": output_guesses, "set": {}}

    def _build_problem(
        self, om: object, start_values: dict[str, dict[str, float]]
    ) -> tuple[object, dict[str, str], dict[str, str], dict[str, str]]:
        participants = self._participants
        connection_unit: dict[tuple[str, str], str] = {}
        for (target_id, target_var), (source_id, source_var) in self._targets.items():
            source_unit = next(
                var.unit
                for var in participants[source_id].outputs
                if var.name == source_var
            )
            connection_unit[(target_id, target_var)] = source_unit

        coordinator = self

        class _ParticipantComp(om.ExplicitComponent):  # type: ignore[valid-type, misc]
            def __init__(self, spec: ScalarParticipantSpec) -> None:
                super().__init__()
                self._spec = spec

            def setup(self) -> None:
                for var in self._spec.inputs:
                    self.add_input(_sanitize(var.name), val=0.0)
                for var in self._spec.outputs:
                    self.add_output(_sanitize(var.name), val=0.0)
                if self._spec.inputs and self._spec.outputs:
                    self.declare_partials("*", "*", method="fd")

            def compute(self, inputs: object, outputs: object) -> None:
                state: dict[str, float] = {}
                for var in self._spec.inputs:
                    raw = _as_float(inputs[_sanitize(var.name)])  # type: ignore[index]
                    unit = connection_unit.get(
                        (self._spec.participant_id, var.name), var.unit
                    )
                    state[var.name] = convert_value(raw, unit, var.unit)
                proposed = self._spec.function(state)
                for var in self._spec.outputs:
                    if var.name not in proposed:
                        raise ValueError(
                            f"MISSING_PARTICIPANT_OUTPUT:{self._spec.participant_id}:{var.name}"
                        )
                    value = float(proposed[var.name])
                    if not isfinite(value):
                        raise ValueError(
                            f"NONFINITE_PARTICIPANT_OUTPUT:{self._spec.participant_id}:{var.name}"
                        )
                    outputs[_sanitize(var.name)] = value  # type: ignore[index]

        problem = om.Problem(reports=False)
        model = problem.model
        comp_paths: dict[str, str] = {}
        for participant in participants.values():
            path = f"comp_{_sanitize(participant.participant_id)}"
            model.add_subsystem(path, _ParticipantComp(participant))
            comp_paths[participant.participant_id] = path
        indep = om.IndepVarComp()
        indep_map: dict[str, str] = {}
        for key in start_values["indep"]:
            out_name = f"in_{_sanitize(key)}"
            indep.add_output(out_name, val=0.0)
            indep_map[key] = f"design_inputs.{out_name}"
        has_indep = bool(indep_map)
        if has_indep:
            model.add_subsystem("design_inputs", indep)
        for key in start_values["indep"]:
            if "." in key and key not in coordinator._shared:
                participant_id, _, var_name = key.partition(".")
                model.connect(
                    indep_map[key],
                    f"{comp_paths[participant_id]}.{_sanitize(var_name)}",
                )
            else:
                for participant in participants.values():
                    for var in participant.inputs:
                        if var.name == key and (
                            participant.participant_id,
                            var.name,
                        ) not in coordinator._targets:
                            model.connect(
                                indep_map[key],
                                f"{comp_paths[participant.participant_id]}."
                                f"{_sanitize(var.name)}",
                            )
        for (target_id, target_var), (source_id, source_var) in coordinator._targets.items():
            model.connect(
                f"{comp_paths[source_id]}.{_sanitize(source_var)}",
                f"{comp_paths[target_id]}.{_sanitize(target_var)}",
            )
        policy = self._policy
        if policy.nonlinear_solver == "newton":
            solver = om.NewtonSolver(solve_subsystems=True)
            solver.options["maxiter"] = 1
            solver.options["err_on_non_converge"] = False
            solver.options["iprint"] = 0
            model.nonlinear_solver = solver
            if policy.linear_solver == "direct":
                model.linear_solver = om.DirectSolver()
        else:
            solver = om.NonlinearBlockGS()
            solver.options["maxiter"] = 1
            solver.options["err_on_non_converge"] = False
            solver.options["iprint"] = 0
            if policy.relaxation < 1.0:
                solver.options["use_aitken"] = True
                solver.options["aitken_initial_factor"] = policy.relaxation
            model.nonlinear_solver = solver
        output_paths = {
            f"{participant_id}.{var.name}": f"{path}.{_sanitize(var.name)}"
            for participant_id, participant in participants.items()
            for var in participant.outputs
            for path in (comp_paths[participant_id],)
        }
        start_values["set"].update(
            {indep_map[key]: value for key, value in start_values["indep"].items()}
        )
        start_values["set"].update(
            {
                output_paths[qualified]: value
                for qualified, value in start_values["outputs"].items()
            }
        )
        return problem, comp_paths, indep_map, output_paths

    def _initial_values(self, start_values: dict[str, dict[str, float]]) -> dict[str, float]:
        """Analytic iteration-0 state: guesses, resolved inputs, driven inputs
        converted from the source guesses. Deterministic, so a warm start
        replays the checkpoint exactly."""
        current = dict(start_values["outputs"])
        current.update(start_values["indep"])
        guesses = dict(start_values["outputs"])
        for (target_id, target_var), (source_id, source_var) in self._targets.items():
            source_unit = next(
                item.unit
                for item in self._participants[source_id].outputs
                if item.name == source_var
            )
            target_unit = next(
                item.unit
                for item in self._participants[target_id].inputs
                if item.name == target_var
            )
            current[f"{target_id}.{target_var}"] = convert_value(
                guesses[f"{source_id}.{source_var}"], source_unit, target_unit
            )
        return current

    def _read_values(
        self,
        problem: object,
        comp_paths: dict[str, str],
        indep_map: dict[str, str],
        output_paths: dict[str, str],
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        get_val = problem.get_val  # type: ignore[attr-defined]
        for qualified, path in output_paths.items():
            values[qualified] = _as_float(get_val(path))
        for key, path in indep_map.items():
            if "." in key and key not in self._shared or key in self._shared:
                values[key] = _as_float(get_val(path))
        for participant in self._participants.values():
            for var in participant.inputs:
                if (participant.participant_id, var.name) in self._targets:
                    source_id, source_var = self._targets[(participant.participant_id, var.name)]
                    source_unit = next(
                        item.unit
                        for item in self._participants[source_id].outputs
                        if item.name == source_var
                    )
                    raw = _as_float(
                        get_val(  # type: ignore[attr-defined]
                            f"{comp_paths[participant.participant_id]}.{_sanitize(var.name)}"
                        )
                    )
                    values[f"{participant.participant_id}.{var.name}"] = convert_value(
                        raw, source_unit, var.unit
                    )
        return values
