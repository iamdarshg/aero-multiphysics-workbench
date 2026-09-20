"""Deterministic tiny fixtures for platform94 recursive composition tests."""

from __future__ import annotations

import threading
import time
from dataclasses import replace

from aeroworkbench_core.assembly import synthesize_subassembly
from aeroworkbench_core.composition import (
    AssemblyLink,
    Binding,
    DesignVariable,
    MassProperties,
    OperatingState,
    Requirement,
    SolverCapability,
    SystemRecord,
    control_port,
    electrical_port,
    fluid_port,
    mechanical_port,
    thermal_port,
)
from aeroworkbench_core.physical import RigidTransform
from aeroworkbench_coupling.hierarchy import LeafModel

VEH = "veh"


def _install(child: str, parent: str, position: tuple[float, float, float]) -> RigidTransform:
    return RigidTransform(f"{child}-body", f"{parent}-body",
                          ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), position)


def build_mechanical() -> tuple[SystemRecord, dict[str, LeafModel], dict[str, float]]:
    comp_a = SystemRecord(
        system_id="compA", revision="a1", system_type="force-source",
        capabilities=("mechanical",), transform=_install("compA", "assembly", (0.0, 0.0, 0.0)),
        ports=(mechanical_port("preload_in", "force", "N", "in", "frameA"),
               mechanical_port("force_out", "force", "N", "out", "frameA")),
        mass=MassProperties(2.0, (0.0, 0.0, 0.0), (0.1, 0.1, 0.1)),
        design_vars=(DesignVariable("preload", 10.0, "N", 0.0, 50.0),),
        requirements=(Requirement("A1", "deliver force", "force_out", "N", 8.0, ">="),),
        operating=OperatingState("cruise", {"preload_N": 10.0}),
        solvers=(SolverCapability("mech-a", ("static",), "analytical", False),),
    )
    comp_b = SystemRecord(
        system_id="compB", revision="b1", system_type="compliant-mount",
        capabilities=("mechanical",), transform=_install("compB", "assembly", (1.0, 0.0, 0.0)),
        ports=(mechanical_port("force_in", "force", "N", "in", "frameB"),
               mechanical_port("disp_out", "displacement", "mm", "out", "bench")),
        mass=MassProperties(3.0, (0.0, 0.0, 0.0), (0.2, 0.2, 0.2)),
        requirements=(Requirement("B1", "limit input force", "force_in", "N", 20.0, "<="),),
        solvers=(SolverCapability("mech-b", ("static",), "analytical", False),),
    )
    link = AssemblyLink("compA", "force_out", "compB", "force_in",
                        RigidTransform("frameA", "frameB",
                                       ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
                                       (-1.0, 0.0, 0.0)))
    record = synthesize_subassembly(
        system_id="assembly", revision="r1", system_type="mechanical-assembly",
        children=(comp_a, comp_b), links=(link,),
        ports=(mechanical_port("result_disp", "displacement", "mm", "out", "bench"),),
        bindings=(Binding("compB", "disp_out", "result_disp"),),
        requirements=(Requirement("M1", "limit deflection", "result_disp", "mm", 3.0, "<=",
                                  margin=1.0 / 3.0),),
        operating=OperatingState("cruise", {"preload_N": 10.0}),
    )

    def model_a(inputs: dict[str, float]) -> dict[str, float]:
        return {"force_out": inputs["preload_in"]}

    def model_b(inputs: dict[str, float]) -> dict[str, float]:
        return {"disp_out": inputs["force_in"] * 0.2}

    models = {
        "compA": LeafModel("compA", model_a, {"force_out": "N"}),
        "compB": LeafModel("compB", model_b, {"disp_out": "mm"}),
    }
    return record, models, {"preload_in": 10.0}


def build_propulsion() -> tuple[SystemRecord, dict[str, LeafModel], dict[str, float]]:
    source = SystemRecord(
        system_id="source", revision="s1", system_type="energy-source",
        capabilities=("electrical",), transform=_install("source", "propulsion", (0.0, 0.0, 0.0)),
        ports=(electrical_port("power_out", "power", "W", "out", "busA"),),
        mass=MassProperties(4.0, (0.0, 0.0, 0.0), (0.1, 0.1, 0.1)),
        requirements=(Requirement("S1", "deliver power", "power_out", "W", 1000.0, "=="),),
        solvers=(SolverCapability("elec-src", ("dc",), "analytical", False),),
    )
    motor = SystemRecord(
        system_id="motor", revision="m1", system_type="motor",
        capabilities=("electrical", "mechanical"),
        transform=_install("motor", "propulsion", (0.2, 0.0, 0.0)),
        ports=(electrical_port("motor_power", "power", "W", "in", "busA"),
               mechanical_port("shaft_out", "power", "W", "out", "shaftA"),
               thermal_port("heat_out", "heat", "W", "out", "shaftA")),
        mass=MassProperties(1.5, (0.0, 0.0, 0.0), (0.05, 0.05, 0.05)),
        requirements=(Requirement("MO1", "deliver shaft power", "shaft_out", "W", 700.0, ">="),),
        solvers=(SolverCapability("em-motor", ("electromechanical",), "analytical", False),),
    )
    propulsor = SystemRecord(
        system_id="propulsor", revision="p1", system_type="propulsor",
        capabilities=("mechanical", "fluid"),
        transform=_install("propulsor", "propulsion", (0.5, 0.0, 0.0)),
        ports=(mechanical_port("shaft_in", "power", "W", "in", "shaftA"),
               mechanical_port("thrust_out", "force", "N", "out", VEH),
               fluid_port("wake_out", "velocity", "m/s", "out", VEH)),
        mass=MassProperties(1.0, (0.0, 0.0, 0.0), (0.02, 0.02, 0.02)),
        requirements=(Requirement("P1", "deliver thrust", "thrust_out", "N", 300.0, ">=",
                                  margin=0.2),),
        solvers=(SolverCapability("disk", ("propulsion",), "analytical", False),),
    )
    record = synthesize_subassembly(
        system_id="propulsion", revision="r1", system_type="propulsion-system",
        children=(source, motor, propulsor),
        links=(AssemblyLink("source", "power_out", "motor", "motor_power"),
               AssemblyLink("motor", "shaft_out", "propulsor", "shaft_in")),
        ports=(mechanical_port("thrust", "force", "N", "out", VEH),),
        bindings=(Binding("propulsor", "thrust_out", "thrust"),),
        requirements=(Requirement("PS1", "installed thrust", "thrust", "N", 300.0, ">=",
                                  margin=0.2),),
    )

    def model_source(inputs: dict[str, float]) -> dict[str, float]:
        return {"power_out": 1000.0}

    def model_motor(inputs: dict[str, float]) -> dict[str, float]:
        power = inputs["motor_power"]
        return {"shaft_out": power * 0.9, "heat_out": power * 0.1}

    def model_propulsor(inputs: dict[str, float]) -> dict[str, float]:
        thrust = inputs["shaft_in"] * 0.4
        return {"thrust_out": thrust, "wake_out": thrust * 0.01}

    models = {
        "source": LeafModel("source", model_source, {"power_out": "W"}),
        "motor": LeafModel("motor", model_motor, {"shaft_out": "W", "heat_out": "W"}),
        "propulsor": LeafModel("propulsor", model_propulsor,
                               {"thrust_out": "N", "wake_out": "m/s"}),
    }
    return record, models, {}


def _propulsion_nested() -> SystemRecord:
    motor = SystemRecord(
        system_id="motor", revision="m1", system_type="motor",
        capabilities=("electrical", "mechanical"),
        transform=_install("motor", "propulsion", (0.3, 0.0, 0.0)),
        ports=(electrical_port("motor_power", "power", "W", "in", VEH),
               control_port("throttle_in", "throttle", "1", "in", VEH),
               mechanical_port("shaft_out", "power", "W", "out", VEH),
               thermal_port("heat_out", "heat", "W", "out", VEH)),
        mass=MassProperties(1.5, (0.0, 0.0, 0.0), (0.05, 0.05, 0.05)),
        requirements=(Requirement("MO1", "shaft delivery", "shaft_out", "W", 50.0, ">=",
                                  margin=0.4),),
        solvers=(SolverCapability("em-motor", ("electromechanical",), "analytical", False),),
    )
    propulsor = SystemRecord(
        system_id="propulsor", revision="p1", system_type="propulsor",
        capabilities=("mechanical", "fluid"),
        transform=_install("propulsor", "propulsion", (0.6, 0.0, 0.0)),
        ports=(mechanical_port("shaft_in", "power", "W", "in", VEH),
               fluid_port("inlet_in", "velocity", "m/s", "in", VEH),
               mechanical_port("thrust_out", "force", "N", "out", VEH),
               fluid_port("wake_out", "velocity", "m/s", "out", "duct")),
        mass=MassProperties(1.0, (0.0, 0.0, 0.0), (0.02, 0.02, 0.02)),
        requirements=(Requirement("P1", "thrust delivery", "thrust_out", "N", 10.0, ">=",
                                  margin=1.0),),
        solvers=(SolverCapability("disk", ("propulsion",), "analytical", False),),
    )
    return synthesize_subassembly(
        system_id="propulsion", revision="r1", system_type="propulsion-system",
        children=(motor, propulsor),
        links=(AssemblyLink("propulsion", "power_bus", "motor", "motor_power"),
               AssemblyLink("propulsion", "throttle_bus", "motor", "throttle_in"),
               AssemblyLink("propulsion", "inlet_bus", "propulsor", "inlet_in"),
               AssemblyLink("motor", "shaft_out", "propulsor", "shaft_in")),
        ports=(electrical_port("power_bus", "power", "W", "in", VEH),
               control_port("throttle_bus", "throttle", "1", "in", VEH),
               fluid_port("inlet_bus", "velocity", "m/s", "in", VEH),
               mechanical_port("thrust_out", "force", "N", "out", VEH),
               fluid_port("wake_out", "velocity", "m/s", "out", "duct"),
               thermal_port("heat_out", "heat", "W", "out", VEH)),
        bindings=(Binding("motor", "heat_out", "heat_out"),
                  Binding("propulsor", "thrust_out", "thrust_out"),
                  Binding("propulsor", "wake_out", "wake_out")),
        requirements=(Requirement("PS1", "installed thrust", "thrust_out", "N", 10.0, ">=",
                                  margin=1.0),),
    )


def build_aircraft() -> tuple[SystemRecord, dict[str, LeafModel], dict[str, float]]:
    propulsion = replace(_propulsion_nested(),
                         transform=_install("propulsion", "vehicle", (0.2, 0.0, 0.0)))
    energy = SystemRecord(
        system_id="energy", revision="e1", system_type="battery",
        capabilities=("electrical",), transform=_install("energy", "vehicle", (0.5, 0.0, 0.0)),
        ports=(electrical_port("power_avail", "power", "W", "out", VEH),),
        mass=MassProperties(2.0, (0.0, 0.0, 0.0), (0.05, 0.05, 0.05)),
        solvers=(SolverCapability("batt", ("electrothermal",), "analytical", False),),
    )
    airframe = SystemRecord(
        system_id="airframe", revision="f1", system_type="airframe",
        capabilities=("aerodynamics", "structures"),
        transform=_install("airframe", "vehicle", (0.0, 0.0, 0.0)),
        ports=(mechanical_port("thrust_in", "force", "N", "in", VEH),
               fluid_port("wake_in", "velocity", "m/s", "in", VEH),
               thermal_port("heat_in", "heat", "W", "in", VEH),
               control_port("attitude_in", "angle", "rad", "in", VEH),
               fluid_port("freestream_ms", "velocity", "m/s", "in", VEH),
               mechanical_port("weight_N", "force", "N", "in", VEH),
               mechanical_port("drag_out", "force", "N", "out", VEH),
               mechanical_port("lift_out", "force", "N", "out", VEH),
               mechanical_port("moment_out", "moment", "N.m", "out", VEH),
               fluid_port("inlet_out", "velocity", "m/s", "out", VEH),
               mechanical_port("lift_resid_out", "force", "N", "out", VEH),
               mechanical_port("thrust_resid_out", "force", "N", "out", VEH)),
        mass=MassProperties(6.0, (0.0, 0.0, 0.0), (0.5, 0.5, 0.5)),
        design_vars=(DesignVariable("wing_area", 1.0, "m2", 0.5, 2.0),),
        requirements=(Requirement("F1", "carry lift", "lift_out", "N", 90.0, ">=",
                                  margin=0.05),),
        solvers=(SolverCapability("vortex", ("aerodynamics",), "analytical", False),),
    )
    controls = SystemRecord(
        system_id="controls", revision="c1", system_type="flight-controls",
        capabilities=("control",), transform=_install("controls", "vehicle", (-0.8, 0.0, 0.2)),
        ports=(mechanical_port("drag_in", "force", "N", "in", VEH),
               mechanical_port("thrust2_in", "force", "N", "in", VEH),
               fluid_port("freestream_ms", "velocity", "m/s", "in", VEH),
               mechanical_port("weight_N", "force", "N", "in", VEH),
               fluid_port("inlet2_in", "velocity", "m/s", "in", VEH),
               fluid_port("wake2_in", "velocity", "m/s", "in", VEH),
               mechanical_port("moment_in", "moment", "N.m", "in", VEH),
               control_port("attitude_out", "angle", "rad", "out", VEH),
               control_port("throttle_out", "throttle", "1", "out", VEH)),
        mass=MassProperties(0.5, (0.0, 0.0, 0.0), (0.01, 0.01, 0.01)),
        solvers=(SolverCapability("trim", ("control",), "analytical", False),),
    )
    wake_link = AssemblyLink(
        "propulsion", "wake_out", "airframe", "wake_in",
        RigidTransform("duct", VEH,
                       ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.4, 0.0, 0.0)))
    record = synthesize_subassembly(
        system_id="vehicle", revision="v1", system_type="aircraft",
        children=(airframe, propulsion, energy, controls),
        links=(AssemblyLink("energy", "power_avail", "propulsion", "power_bus"),
               AssemblyLink("controls", "throttle_out", "propulsion", "throttle_bus"),
               AssemblyLink("airframe", "inlet_out", "propulsion", "inlet_bus"),
               AssemblyLink("propulsion", "thrust_out", "airframe", "thrust_in"),
               wake_link,
               AssemblyLink("propulsion", "heat_out", "airframe", "heat_in"),
               AssemblyLink("airframe", "drag_out", "controls", "drag_in"),
               AssemblyLink("propulsion", "thrust_out", "controls", "thrust2_in"),
               AssemblyLink("airframe", "moment_out", "controls", "moment_in"),
               AssemblyLink("airframe", "inlet_out", "controls", "inlet2_in"),
               AssemblyLink("controls", "attitude_out", "airframe", "attitude_in"),
               AssemblyLink("propulsion", "wake_out", "controls", "wake2_in",
                            RigidTransform("duct", VEH,
                                           ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
                                           (0.4, 0.0, 0.0)))),
        ports=(mechanical_port("lift_out", "force", "N", "out", VEH),
               mechanical_port("drag_out", "force", "N", "out", VEH),
               mechanical_port("thrust_out", "force", "N", "out", VEH),
               fluid_port("freestream_ms", "velocity", "m/s", "in", VEH),
               mechanical_port("weight_N", "force", "N", "in", VEH)),
        bindings=(Binding("airframe", "lift_out", "lift_out"),
                  Binding("airframe", "drag_out", "drag_out"),
                  Binding("propulsion", "thrust_out", "thrust_out")),
        requirements=(Requirement("V1", "sustain climb lift", "lift_out", "N", 90.0, ">=",
                                  margin=0.05),
                      Requirement("V2", "bound drag", "drag_out", "N", 80.0, "<=", margin=0.5)),
        operating=OperatingState("cruise", {"freestream_ms": 30.0, "weight_N": 98.1}),
    )

    def model_energy(inputs: dict[str, float]) -> dict[str, float]:
        return {"power_avail": 3000.0}

    def model_motor(inputs: dict[str, float]) -> dict[str, float]:
        available = min(inputs["throttle_in"] * 2000.0, inputs["motor_power"] * 0.95)
        return {"shaft_out": available * 0.9, "heat_out": available * 0.1}

    def model_propulsor(inputs: dict[str, float]) -> dict[str, float]:
        thrust = inputs["shaft_in"] * 0.4 * (inputs["inlet_in"] / 30.0)
        return {"thrust_out": thrust, "wake_out": thrust * 0.01}

    def model_airframe(inputs: dict[str, float]) -> dict[str, float]:
        velocity = inputs["freestream_ms"]
        thrust = inputs["thrust_in"]
        attitude = inputs["attitude_in"]
        wake = inputs["wake_in"]
        heat = inputs["heat_in"]
        weight = inputs["weight_N"]
        inlet = velocity - 0.002 * thrust
        area = 1.0
        dyn = 0.5 * 1.225 * velocity * velocity * area
        coef = 0.5 + 2.0 * attitude + 0.0005 * thrust + 0.01 * wake
        lift = dyn * coef
        drag = dyn * (0.05 + 0.05 * coef * coef) + 0.01 * thrust + 0.005 * heat
        moment = dyn * 0.3 * (0.1 - 0.5 * attitude) + 0.05 * thrust
        return {"drag_out": drag, "lift_out": lift, "moment_out": moment,
                "inlet_out": inlet, "lift_resid_out": lift - weight,
                "thrust_resid_out": thrust - drag}

    def model_controls(inputs: dict[str, float]) -> dict[str, float]:
        velocity = inputs["freestream_ms"]
        dyn = 0.5 * 1.225 * velocity * velocity
        attitude = ((inputs["weight_N"] / dyn) - 0.5 - 0.0005 * inputs["thrust2_in"]
                    - 0.01 * inputs["wake2_in"]) / 2.0
        denom = 720.0 * (inputs["inlet2_in"] / 30.0)
        throttle = inputs["drag_in"] / denom if denom > 1e-9 else 0.0
        throttle = min(1.0, max(0.0, throttle))
        return {"attitude_out": attitude, "throttle_out": throttle}

    models = {
        "energy": LeafModel("energy", model_energy, {"power_avail": "W"}),
        "motor": LeafModel("motor", model_motor, {"shaft_out": "W", "heat_out": "W"}),
        "propulsor": LeafModel("propulsor", model_propulsor,
                               {"thrust_out": "N", "wake_out": "m/s"}),
        "airframe": LeafModel("airframe", model_airframe,
                              {"drag_out": "N", "lift_out": "N", "moment_out": "N.m",
                               "inlet_out": "m/s", "lift_resid_out": "N",
                               "thrust_resid_out": "N"}),
        "controls": LeafModel("controls", model_controls,
                              {"attitude_out": "rad", "throttle_out": "1"}),
    }
    return record, models, {"freestream_ms": 30.0, "weight_N": 98.1}


def build_chain(depth: int) -> tuple[SystemRecord, dict[str, LeafModel], dict[str, float]]:
    leaf = SystemRecord(
        system_id="chain-leaf", revision="1", system_type="signal",
        ports=(mechanical_port("x_out", "force", "N", "out", VEH),),
        solvers=(SolverCapability("const", ("static",), "analytical", False),),
    )
    models: dict[str, LeafModel] = {
        "chain-leaf": LeafModel("chain-leaf", lambda inputs: {"x_out": 1.0}, {"x_out": "N"}),
    }
    node = leaf
    for level in range(1, depth):
        node = synthesize_subassembly(
            system_id=f"chain-{level}", revision="1", system_type="passthrough",
            children=(node,),
            ports=(mechanical_port("x_out", "force", "N", "out", VEH),),
            bindings=(Binding(node.system_id, "x_out", "x_out"),),
        )
    return node, models, {}


def build_parallel() -> tuple[SystemRecord, dict[str, LeafModel], dict[str, float], dict[str, int]]:
    children: list[SystemRecord] = []
    models: dict[str, LeafModel] = {}
    seen: dict[str, int] = {}
    for index in range(3):
        name = f"cell{index}"

        def make_fn(value: float, label: str) -> object:
            def fn(inputs: dict[str, float]) -> dict[str, float]:
                seen[label] = threading.get_ident()
                time.sleep(0.02)
                return {"x_out": value}
            return fn

        children.append(SystemRecord(
            system_id=name, revision="1", system_type="cell",
            ports=(mechanical_port("x_out", "force", "N", "out", VEH),),
            solvers=(SolverCapability("const", ("static",), "analytical", False),)))
        models[name] = LeafModel(name, make_fn(float(index + 1), name), {"x_out": "N"})
    record = synthesize_subassembly(
        system_id="bench3", revision="1", system_type="bench",
        children=tuple(children),
        ports=tuple(mechanical_port(f"out{index}", "force", "N", "out", VEH) for index in range(3)),
        bindings=tuple(Binding(f"cell{index}", "x_out", f"out{index}") for index in range(3)),
    )
    return record, models, {}, seen


def build_rom_replacement() -> SystemRecord:
    return SystemRecord(
        system_id="propulsion", revision="rom1", system_type="propulsion-rom",
        capabilities=("rom",),
        ports=(electrical_port("power_bus", "power", "W", "in", VEH),
               control_port("throttle_bus", "throttle", "1", "in", VEH),
               fluid_port("inlet_bus", "velocity", "m/s", "in", VEH),
               mechanical_port("thrust_out", "force", "N", "out", VEH),
               fluid_port("wake_out", "velocity", "m/s", "out", "duct"),
               thermal_port("heat_out", "heat", "W", "out", VEH)),
        mode="rom", lineage=("validated:propulsion-r1",),
        solvers=(SolverCapability("rom-map", ("propulsion",), "surrogate", False),),
        fidelity="surrogate",
    )


def rom_models() -> dict[str, LeafModel]:
    def fn(inputs: dict[str, float]) -> dict[str, float]:
        thrust = inputs["throttle_bus"] * 600.0 * (inputs["inlet_bus"] / 30.0) + 5.0
        return {"thrust_out": thrust, "wake_out": thrust * 0.009,
                "heat_out": inputs["throttle_bus"] * 150.0}

    return {"propulsion": LeafModel("propulsion", fn,
                                   {"thrust_out": "N", "wake_out": "m/s", "heat_out": "W"},
                                   solver=("rom-map", "2"))}
