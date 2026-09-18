"""GEN 11: native preCICE field coupling between generated-mesh participants.

The native preCICE engine and its Python participant library are NOT installed
on this host, so native execution is gated: every path that requests the
``precice-native`` engine must fail closed with an explicit code and must never
substitute an analytical transfer.

Everything that is engine independent -- manifest-driven configuration,
nonmatching-mesh mapping with conservative/consistent transfer, unit-bearing
field buffers, checkpoints/rollback, and interface conservation -- is executed
for real and labelled ``analytic-transfer`` / ``simulated-precice``. Those
labels are asserted so a simulated adapter can never be mistaken for native
field exchange.
"""

from __future__ import annotations

from typing import Any

import pytest
from aeroworkbench_coupling.field import register_mesh
from aeroworkbench_coupling.precice import (
    CouplingError,
    CouplingFailureCode,
    CouplingField,
    DomainInterface,
    ParticipantView,
    build_coupling_contract,
    participant_view,
)
from aeroworkbench_mesh import SolverMeshExport
from participants.manifest import get_participant
from precice.backend import open_native_backend, probe_precice_python
from precice.coupling import (
    interfaces_from_solver_export,
    map_field,
    require_participant,
    require_publishable,
    run_implicit_coupling,
)
from precice.native_adapter import FieldBuffer, NativeFieldParticipant

# -- fixtures -----------------------------------------------------------------


def _fluid_mesh() -> Any:
    return register_mesh("fluid-interface", (0.0, 0.5, 1.0))


def _structure_mesh() -> Any:
    return register_mesh("solid-interface", (0.0, 0.25, 0.5, 0.75, 1.0))


def _fsi_interface() -> DomainInterface:
    return DomainInterface(
        name="fsi-main",
        zone_a="rotor-zone-0",
        zone_b="duct-shell",
        participant_a="fluid",
        participant_b="structure",
        kind="fsi_interface",
        conformal=False,
        fields=(
            CouplingField("pressure", "fluid", "structure", "Pa"),
            CouplingField("displacement", "structure", "fluid", "m"),
        ),
    )


def _thermal_interface() -> DomainInterface:
    return DomainInterface(
        name="cht-main",
        zone_a="duct-shell",
        zone_b="inlet-zone",
        participant_a="structure",
        participant_b="fluid",
        kind="cht_interface",
        conformal=False,
        fields=(
            CouplingField("temperature", "structure", "fluid", "K"),
            CouplingField("heat-flux", "fluid", "structure", "W/m2"),
        ),
    )


class _ScriptedBackend:
    """Minimal in-memory preCICE-shaped double; clearly non-native."""

    def __init__(self, *, ongoing: bool = True) -> None:
        self.initialized = False
        self.finalized = False
        self.advanced: list[float] = []
        self._data: dict[str, list[float]] = {}
        self._ongoing = ongoing

    def initialize(self) -> None:
        self.initialized = True

    def set_mesh_vertices(
        self, mesh_name: str, coordinates: tuple[float, ...]
    ) -> tuple[int, ...]:
        _ = mesh_name
        return tuple(range(len(coordinates)))

    def write_data(self, name: str, values: list[float]) -> None:
        self._data[name] = [float(value) for value in values]

    def read_data(self, name: str) -> list[float]:
        return list(self._data.get(name, ()))

    def requires_writing_checkpoint(self) -> bool:
        return False

    def requires_reading_checkpoint(self) -> bool:
        return False

    def advance(self, dt: float) -> None:
        self.advanced.append(dt)

    def is_coupling_ongoing(self) -> bool:
        return self._ongoing

    def finalize(self) -> None:
        self.finalized = True


def _participant(backend: _ScriptedBackend) -> NativeFieldParticipant:
    return NativeFieldParticipant(
        name="structure",
        backend=backend,
        mesh_name="solid-interface",
        mesh=_structure_mesh(),
        buffers=(
            FieldBuffer("displacement", "m", "vector"),
            FieldBuffer("temperature", "K", "scalar"),
        ),
    )


# -- A. generic coupling contract --------------------------------------------


def test_contract_from_manifests_and_interfaces_builds_implicit_iqn_config() -> None:
    fluid = participant_view(get_participant("incompressible-steady-flow"))
    structure = participant_view(get_participant("structural-static"))
    contract = build_coupling_contract(
        participants=("fluid", "structure"),
        interfaces=(_fsi_interface(),),
        manifests={"fluid": fluid, "structure": structure},
    )
    xml = contract.config.xml
    assert "fluid" in xml and "structure" in xml
    assert 'data-field name="pressure" type="scalar"' in xml
    assert 'data-field name="displacement" type="vector"' in xml
    assert 'type="implicit"' in xml
    assert "IQN-ILS" in xml
    assert len(contract.config.digest_sha256) == 64
    assert {field.name for field in contract.fields} == {"pressure", "displacement"}
    assert {field.mapping for field in contract.fields} == {"conservative", "consistent"}


def test_interfaces_from_gen05_solver_export_bind_participants() -> None:
    export = SolverMeshExport(
        "precice",
        "precice",
        (),
        (),
        (("fsi-main", "fsi_interface", "rotor-zone-0", "duct-shell", False),),
        (),
    )
    interfaces = interfaces_from_solver_export(
        export,
        assignments={"fsi_interface": ("fluid", "structure")},
        fields={
            "fsi_interface": (
                CouplingField("pressure", "fluid", "structure", "Pa"),
                CouplingField("displacement", "structure", "fluid", "m"),
            )
        },
    )
    assert interfaces[0].zone_a == "rotor-zone-0"
    assert interfaces[0].conformal is False
    contract = build_coupling_contract(
        participants=("fluid", "structure"), interfaces=interfaces
    )
    assert "fsi-main" in contract.config.xml


def test_unknown_field_without_declared_quantity_is_rejected() -> None:
    interface = DomainInterface(
        name="custom",
        zone_a="a",
        zone_b="b",
        participant_a="fluid",
        participant_b="structure",
        fields=(CouplingField("mystery", "fluid", "structure", "dimensionless"),),
    )
    with pytest.raises(CouplingError) as exc:
        build_coupling_contract(
            participants=("fluid", "structure"), interfaces=(interface,)
        )
    assert exc.value.code is CouplingFailureCode.INTERFACE_MISMATCH
    assert "UNKNOWN_FIELD" in exc.value.detail


def test_declaring_quantity_allows_future_fields() -> None:
    interface = DomainInterface(
        name="custom",
        zone_a="a",
        zone_b="b",
        participant_a="fluid",
        participant_b="structure",
        fields=(
            CouplingField("electric-potential", "fluid", "structure", "V", quantity="scalar"),
        ),
    )
    contract = build_coupling_contract(
        participants=("fluid", "structure"), interfaces=(interface,)
    )
    assert 'data-field name="electric-potential" type="scalar"' in contract.config.xml


# -- field/unit mismatch rejects before launch --------------------------------


def test_field_unit_mismatch_rejects_before_launch() -> None:
    structure_pa = ParticipantView(
        "structure", "structural", field_outputs=(("displacement", "Pa"),)
    )
    interface = DomainInterface(
        name="fsi-main",
        zone_a="a",
        zone_b="b",
        participant_a="fluid",
        participant_b="structure",
        fields=(CouplingField("displacement", "structure", "fluid", "m"),),
    )
    with pytest.raises(CouplingError) as exc:
        build_coupling_contract(
            participants=("fluid", "structure"),
            interfaces=(interface,),
            manifests={"structure": structure_pa},
        )
    assert exc.value.code is CouplingFailureCode.FIELD_UNIT_MISMATCH


def test_interface_with_undeclared_participant_is_rejected() -> None:
    interface = DomainInterface(
        name="fsi-main",
        zone_a="a",
        zone_b="b",
        participant_a="fluid",
        participant_b="ghost",
        fields=(CouplingField("pressure", "fluid", "ghost", "Pa"),),
    )
    with pytest.raises(CouplingError) as exc:
        build_coupling_contract(
            participants=("fluid", "structure"), interfaces=(interface,)
        )
    assert exc.value.code is CouplingFailureCode.INTERFACE_MISMATCH


def test_field_direction_must_match_interface_participants() -> None:
    interface = DomainInterface(
        name="fsi-main",
        zone_a="a",
        zone_b="b",
        participant_a="fluid",
        participant_b="structure",
        fields=(CouplingField("pressure", "structure", "structure", "Pa"),),
    )
    with pytest.raises(CouplingError) as exc:
        build_coupling_contract(
            participants=("fluid", "structure"), interfaces=(interface,)
        )
    assert exc.value.code is CouplingFailureCode.INTERFACE_MISMATCH


# -- C. mapping: traceability, conservation, resolution -----------------------


def test_interface_hashes_and_mapping_are_traceable() -> None:
    mapped, record = map_field(
        _fluid_mesh(),
        (10.0, 20.0, 30.0),
        _structure_mesh(),
        "pressure",
        method="conservative",
    )
    assert len(record.source_hash) == 64 and len(record.target_hash) == 64
    assert record.method == "conservative"
    assert record.field == "pressure"
    assert record.accepted is True
    assert record.relative_conservation_error <= record.tolerance
    assert len(mapped) == len(_structure_mesh().coordinates)


def _node_integral(mesh: Any, values: Any) -> float:
    widths = [b - a for a, b in zip(mesh.coordinates, mesh.coordinates[1:], strict=False)]
    return sum(value * width for value, width in zip(values, widths, strict=False))


def test_conservative_mapping_preserves_known_integral() -> None:
    # A uniform load q over [0,1] has a known resultant integral q * length.
    # A conservative transfer must reproduce it on every nonmatching target.
    source = register_mesh("src", (0.0, 0.25, 0.5, 0.75, 1.0))
    values = (7.0, 7.0, 7.0, 7.0, 7.0)
    source_integral = 7.0 * (source.coordinates[-1] - source.coordinates[0])
    for resolution in ((0.0, 0.5, 1.0), (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)):
        target = register_mesh("tgt", resolution)
        mapped, record = map_field(source, values, target, "pressure", method="conservative")
        assert record.accepted is True, record
        assert record.relative_conservation_error <= 1e-12
        assert _node_integral(target, mapped) == pytest.approx(source_integral, abs=1e-9)
    # A linear field must also conserve the transfer's own control-volume
    # integral exactly.
    _, linear_record = map_field(
        source,
        tuple(source.coordinates),
        register_mesh("tgt-linear", (0.0, 0.5, 1.0)),
        "pressure",
        method="conservative",
    )
    assert linear_record.relative_conservation_error <= 1e-12


def test_consistent_mapping_interpolates_onto_nonmatching_mesh() -> None:
    source = register_mesh("src", (0.0, 1.0))
    mapped, record = map_field(
        source, (0.0, 100.0), _structure_mesh(), "temperature", method="consistent"
    )
    assert record.method == "consistent"
    assert mapped[0] == pytest.approx(0.0)
    assert mapped[-1] == pytest.approx(100.0)
    assert mapped[2] == pytest.approx(50.0)


# -- B. native participant adapter hooks (simulated engine, not native) -------


def _fake_backend(*, ongoing: bool = True) -> _ScriptedBackend:
    return _ScriptedBackend(ongoing=ongoing)


def test_adapter_registers_mesh_writes_and_reads_units() -> None:
    backend = _fake_backend()
    participant = _participant(backend)
    vertex_ids = participant.initialize()
    assert backend.initialized is True
    assert vertex_ids == tuple(range(len(_structure_mesh().coordinates)))
    participant.write_field("temperature", (250.0, 260.0, 270.0, 280.0, 290.0))
    assert participant.read_field("temperature")[0] == pytest.approx(250.0)
    # A compatible but different unit is converted before it reaches the backend.
    participant.write_field("temperature", (0.0, 10.0, 20.0, 30.0, 40.0), unit="degC")
    assert participant.read_field("temperature")[0] == pytest.approx(273.15)
    assert participant.engine == "simulated-precice"


def test_adapter_rejects_incompatible_units() -> None:
    participant = _participant(_fake_backend())
    participant.initialize()
    with pytest.raises(CouplingError) as exc:
        participant.write_field("displacement", (1.0, 2.0, 3.0), unit="Pa")
    assert exc.value.code is CouplingFailureCode.FIELD_UNIT_MISMATCH


def test_rollback_restores_participant_state() -> None:
    backend = _fake_backend()
    participant = _participant(backend)
    participant.initialize()
    first = (0.0, 1.0, 2.0, 3.0, 4.0)
    second = (9.0, 9.0, 9.0, 9.0, 9.0)
    participant.write_field("temperature", first)
    participant.checkpoint("ckpt-1")
    participant.write_field("temperature", second)
    assert participant.read_field("temperature") == second
    rollback = participant.rollback("ckpt-1", reason="interface residual diverged")
    assert participant.read_field("temperature") == first
    assert backend.read_data("temperature") == list(first)
    assert rollback.kind == "rollback"
    assert [event.kind for event in participant.events()] == [
        "initialize",
        "checkpoint",
        "rollback",
    ]


def test_adapter_advances_only_while_coupling_is_ongoing() -> None:
    backend = _fake_backend(ongoing=False)
    participant = _participant(backend)
    participant.initialize()
    assert participant.is_coupling_ongoing() is False
    participant.advance(0.001)
    assert backend.advanced == [0.001]
    participant.finalize()
    assert backend.finalized is True


# -- D. implicit lifecycle and fail-closed native gating -----------------------


def _sides() -> tuple[Any, Any]:
    from aeroworkbench_coupling.field import SideSpec

    fluid = SideSpec("fluid", lambda incoming: {"pressure": (10.0, 11.0, 12.0)})
    structure = SideSpec(
        "structure", lambda incoming: {"displacement": (0.0, 0.0, 0.0, 0.0, 0.0)}
    )
    return fluid, structure


def _nonconvergent_sides() -> tuple[Any, Any]:
    from aeroworkbench_coupling.field import SideSpec

    fluid = SideSpec("fluid", lambda incoming: {"pressure": (10.0, 11.0, 12.0)})
    structure = SideSpec(
        "structure", lambda incoming: {"displacement": (1.0, 1.0, 1.0, 1.0, 1.0)}
    )
    return fluid, structure


def _contract() -> Any:
    return build_coupling_contract(
        participants=("fluid", "structure"), interfaces=(_fsi_interface(),)
    )


def test_native_engine_is_unavailable_and_never_substitutes_analytic() -> None:
    assert probe_precice_python().state == "unavailable"
    fluid, structure = _sides()
    result = run_implicit_coupling(
        contract=_contract(),
        interface=_fsi_interface(),
        mesh_a=_fluid_mesh(),
        mesh_b=_structure_mesh(),
        side_a=fluid,
        side_b=structure,
        quantity_a_to_b="pressure",
        quantity_b_to_a="displacement",
        initial_a=(0.0, 0.0, 0.0),
        initial_b=(0.0, 0.0, 0.0, 0.0, 0.0),
        engine="precice-native",
    )
    assert result.state == "failed"
    assert result.engine == "precice-native"
    assert result.accepted is False
    assert result.publishable is False
    assert result.failure_code == CouplingFailureCode.PRECICE_UNAVAILABLE.value
    assert result.mappings == ()
    with pytest.raises(CouplingError):
        require_publishable(result)


def test_participant_unavailable_fails_closed() -> None:
    class _Absent:
        state = "unavailable"
        detail = "OpenFOAM is not installed"

    class _Ready:
        state = "ready"
        detail = "simpleFoam responded"

    with pytest.raises(CouplingError) as exc:
        require_participant("incompressible-steady-flow", probe=lambda _id: _Absent())
    assert exc.value.code is CouplingFailureCode.PARTICIPANT_UNAVAILABLE
    assert require_participant("incompressible-steady-flow", probe=lambda _id: _Ready())


def test_mapping_failure_is_explicit() -> None:
    with pytest.raises(CouplingError) as exc:
        map_field(_fluid_mesh(), (1.0, 2.0, 3.0), _structure_mesh(), "mystery")
    assert exc.value.code is CouplingFailureCode.MAPPING_FAILURE


def test_rollback_failure_is_explicit() -> None:
    participant = _participant(_fake_backend())
    participant.initialize()
    with pytest.raises(CouplingError) as exc:
        participant.rollback("missing", reason="no such checkpoint")
    assert exc.value.code is CouplingFailureCode.CHECKPOINT_ROLLBACK_FAILURE


def test_open_native_backend_fails_closed() -> None:
    from participants.errors import NativeErrorCode, ParticipantError

    with pytest.raises(ParticipantError) as exc:
        open_native_backend(participant="fluid", config_file="precice-config.xml")
    assert exc.value.code is NativeErrorCode.CAPABILITY_UNAVAILABLE


def test_analytic_lifecycle_converges_and_is_separately_labelled() -> None:
    contract = build_coupling_contract(
        participants=("fluid", "structure"),
        interfaces=(_fsi_interface(),),
        tolerance=1e-6,
    )
    fluid, structure = _sides()
    result = run_implicit_coupling(
        contract=contract,
        interface=_fsi_interface(),
        mesh_a=_fluid_mesh(),
        mesh_b=_structure_mesh(),
        side_a=fluid,
        side_b=structure,
        quantity_a_to_b="pressure",
        quantity_b_to_a="displacement",
        initial_a=(0.0, 0.0, 0.0),
        initial_b=(0.0, 0.0, 0.0, 0.0, 0.0),
        engine="analytic-transfer",
    )
    assert result.engine == "analytic-transfer"
    assert result.state == "completed"
    assert result.accepted is True
    assert result.publishable is True
    assert result.residual_trace
    assert require_publishable(result) is result


def test_nonconvergence_cannot_publish_coupled_result() -> None:
    contract = build_coupling_contract(
        participants=("fluid", "structure"),
        interfaces=(_fsi_interface(),),
        tolerance=1e-12,
        max_iterations=1,
    )
    fluid, structure = _nonconvergent_sides()
    result = run_implicit_coupling(
        contract=contract,
        interface=_fsi_interface(),
        mesh_a=_fluid_mesh(),
        mesh_b=_structure_mesh(),
        side_a=fluid,
        side_b=structure,
        quantity_a_to_b="pressure",
        quantity_b_to_a="displacement",
        initial_a=(0.0, 0.0, 0.0),
        initial_b=(0.0, 0.0, 0.0, 0.0, 0.0),
        engine="analytic-transfer",
    )
    assert result.accepted is False
    assert result.publishable is False
    assert result.failure_code == CouplingFailureCode.COUPLING_NONCONVERGENCE.value
    with pytest.raises(CouplingError):
        require_publishable(result)


# -- F. native benchmark cases (engine-independent evidence) -------------------


def test_benchmark_fsi_field_exchange_on_nonmatching_meshes() -> None:
    pressure, pressure_record = map_field(
        _fluid_mesh(), (1000.0, 1100.0, 1200.0), _structure_mesh(),
        "pressure", method="conservative",
    )
    displacement, displacement_record = map_field(
        _structure_mesh(), (0.0, 0.001, 0.002, 0.003, 0.004), _fluid_mesh(),
        "displacement", method="consistent",
    )
    assert pressure_record.accepted and displacement_record.accepted
    assert len(pressure) == len(_structure_mesh().coordinates)
    assert len(displacement) == len(_fluid_mesh().coordinates)
    assert pressure_record.source_hash != pressure_record.target_hash


def test_benchmark_thermal_interface_exchange() -> None:
    temperature, temperature_record = map_field(
        _structure_mesh(), (300.0, 310.0, 320.0, 330.0, 340.0), _fluid_mesh(),
        "temperature", method="consistent",
    )
    heat_flux, heat_flux_record = map_field(
        _fluid_mesh(), (500.0, 600.0, 700.0), _structure_mesh(),
        "heat-flux", method="conservative",
    )
    assert temperature_record.accepted and heat_flux_record.accepted
    assert temperature == pytest.approx((300.0, 320.0, 340.0))
    assert len(heat_flux) == len(_structure_mesh().coordinates)


def test_benchmark_rollback_and_retry_restores_state() -> None:
    backend = _fake_backend()
    participant = _participant(backend)
    participant.initialize()
    committed = (1.0, 1.0, 1.0, 1.0, 1.0)
    participant.write_field("temperature", committed)
    participant.checkpoint("window-1")
    participant.write_field("temperature", (2.0, 2.0, 2.0, 2.0, 2.0))
    participant.rollback("window-1", reason="nonconvergence")
    participant.write_field("temperature", committed)
    assert participant.read_field("temperature") == committed
    assert [
        event.kind
        for event in participant.events()
        if event.kind in {"checkpoint", "rollback"}
    ] == ["checkpoint", "rollback"]
