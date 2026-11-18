"""Generate the Phase-15 nominal airframe, fan, ESC and manufacturing CAD.

All geometry is in millimetres and uses the Phase-15 handoff datum:
X lateral, Y vertical, Z aft, with the first rotor plane at Z=0.
This is a local CadQuery build. It exports STEP and reports only; it does not
connect to a machine or emit machine-ready G-code.
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cadquery as cq
from cadquery import Color, Vector
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables" / "phase15_geometry"
STEP_DIR = OUT / "step"
NEST_DIR = OUT / "stock_nests"
REPORT_DIR = OUT / "reports"
for folder in (STEP_DIR, NEST_DIR, REPORT_DIR):
    folder.mkdir(parents=True, exist_ok=True)


# Handoff nominal parameters, with explicit selections from permitted bands.
DUCT_OD = 82.0                  # +2 from nominal 80 to keep 2 mm radial wall
DUCT_ID = 78.0
DUCT_WALL_RADIAL = (DUCT_OD - DUCT_ID) / 2.0
DUCT_CENTRES_X = (-44.0, 44.0) # 88 mm centre spacing
DUCT_LENGTH = 110.0
NOZZLE_Z0 = 110.0
NOZZLE_Z1 = 242.0
INLET_Z0 = -110.0
INLET_MOUTH_X = 78.0
INLET_MOUTH_Y = 90.0
INLET_LIP_RADIUS = 2.5
HUB_D = 40.0
HUB_R = HUB_D / 2.0
ROTOR_TIP_R = DUCT_ID / 2.0 - 0.7
ROTOR_ROOT_R = HUB_R - 1.5
ROTOR_SPAN = ROTOR_TIP_R - ROTOR_ROOT_R
ROTOR_CHORD = 16.0
STATOR_CHORD = 8.0
ROTOR_COUNTS = (13, 12, 11)
STATOR_COUNTS = (23, 21, 19)
ROTOR_Z = (12.0, 48.0, 84.0)
STATOR_Z = (30.0, 66.0, 102.0)
ROTOR_RPM = (36000, 41000, 47000)
ROTOR_BETA_ROOT_DEG = -20.0
ROTOR_BETA_TIP_DEG = -40.0
# The Phase-15 handoff gives no stator metal-angle schedule; use a neutral,
# explicitly tunable first geometry until the final meanline angles are issued.
STATOR_BETA_ROOT_DEG = 0.0
STATOR_BETA_TIP_DEG = 0.0

BODY_LENGTH = 640.0             # upper permitted length; required to house bay
BODY_Z_MIN = -360.0
BODY_Z_MAX = 280.0
BODY_WIDTH = 186.0
BODY_HEIGHT = 88.0               # upper-side relief inside 72–90 band
BODY_EXPONENT = 2.6
BODY_SHELL = 1.2
WING_SPAN = 520.0
WING_AREA_M2 = 0.19
WING_AR = (WING_SPAN / 1000.0) ** 2 / WING_AREA_M2
WING_SWEEP_DEG = 25.0
WING_MAX_THICKNESS = 36.0
WING_ROOT_CHORD = 425.0
WING_TIP_CHORD = 305.0
WING_ROOT_LE_Z = -270.0
ELEVON_SPAN = 150.0
ELEVON_CHORD = 40.0
ELEVON_HINGE_FRACTION = 0.30
ELEVON_GAP = 0.5
FIN_HEIGHT = 70.0
FIN_CHORD = 90.0
FIN_CANT_DEG = 30.0
VANE_SIZE = (30.0, 40.0)
VANE_RING_RADIUS = 44.0
VANE_DEFLECTION_DEG = 0.0

BATTERY_BAY = (200.0, 135.0, 75.0)  # Z, X, Y in the placed model
BATTERY_Z_CENTRE = -207.5          # packs slide forward within the -300..-100 bay
BATTERY_PACK = (65.0, 55.0, 185.0) # X, Y, Z; two packs side-by-side
ESC_BOARD = (150.0, 150.0, 1.6)   # X, Z, Y-thickness
FC_BOARD = (140.0, 100.0, 1.6)
BOARD_Y = 52.0
ESC_Z_CENTRE = 220.0
FC_Z_CENTRE = 345.0
SPREADER_Y = 54.2
COOLING_TUNNEL_Z = (145.0, 395.0)

SERVO_ENVELOPE = (23.0, 12.0, 29.0)
SERVO_MASS_KG = 0.025
MOTOR_CAN_D = 42.0
MOTOR_CAN_LENGTH = 72.0
MOTOR_MASS_KG = 0.274
PAYLOAD_MASS_KG = 1.0
PAYLOAD_CG_Z_MM = -320.0          # derived: 20 mm ahead of the reserved bay
GROWTH_RESERVE_FRACTION = 0.15

SHEET_A = (250.0, 120.0, 5.0)
SHEET_B = (300.0, 120.0, 5.0)
BAR = (300.0, 50.0, 16.0)
BLANK_SPACING = 1.5
EDGE_MARGIN = 1.0
BAR_CLAMP_MARGIN = 25.0

MATERIAL_DENSITY_KG_M3 = {
    "PLA-core-CF-wrap": 1550.0,
    "high-temp-CF-composite": 1650.0,
    "6061-T6": 2700.0,
    "FR4-PCB": 1850.0,
    "copper": 8960.0,
    "servo-envelope": 1000.0,
    "electronics-envelope": 1200.0,
    "carbon-rod": 1600.0,
    "battery-envelope": 500.0,
}


@dataclass
class Part:
    name: str
    shape: cq.Shape
    material: str
    color: Color
    mass_override_kg: float | None = None
    note: str = ""


parts: list[Part] = []
assembly = cq.Assembly(name="Phase15_twin_80mm_EDF_airframe_ESC")


def add_part(name: str, shape: cq.Shape, material: str, color: Color,
             mass_override_kg: float | None = None, note: str = "") -> cq.Shape:
    if shape is None or shape.isNull():
        raise ValueError(f"Null CAD shape: {name}")
    parts.append(Part(name, shape, material, color, mass_override_kg, note))
    assembly.add(shape, name=name, color=color)
    return shape


def naca_points(chord: float, thickness_ratio: float, camber: float = 0.0,
                camber_pos: float = 0.4, samples: int = 24) -> list[tuple[float, float]]:
    """Closed NACA-4-like coordinate set scaled in millimetres."""
    xs = [(1.0 - math.cos(math.pi * i / samples)) / 2.0 for i in range(samples + 1)]

    def yt(x: float) -> float:
        return 5.0 * thickness_ratio * (
            0.2969 * math.sqrt(max(x, 0.0)) - 0.1260 * x - 0.3516 * x * x
            + 0.2843 * x**3 - 0.1015 * x**4
        )

    def yc(x: float) -> float:
        if camber == 0.0:
            return 0.0
        if x < camber_pos:
            return camber / camber_pos**2 * (2 * camber_pos * x - x * x)
        return camber / (1 - camber_pos) ** 2 * (
            (1 - 2 * camber_pos) + 2 * camber_pos * x - x * x
        )

    upper = [(x * chord, chord * (yc(x) + yt(x))) for x in xs]
    lower = [(x * chord, chord * (yc(x) - yt(x))) for x in reversed(xs)]
    return upper + lower


def superellipse_wire(z: float, width: float, height: float, exponent: float = BODY_EXPONENT,
                      x0: float = 0.0, y0: float = 0.0, samples: int = 72) -> cq.Wire:
    power = 2.0 / exponent
    points = []
    for i in range(samples):
        a = 2 * math.pi * i / samples
        x = math.copysign(abs(math.cos(a)) ** power, math.cos(a)) * width / 2
        y = math.copysign(abs(math.sin(a)) ** power, math.sin(a)) * height / 2
        points.append(Vector(x0 + x, y0 + y, z))
    return cq.Wire.makePolygon(points, close=True)


def ellipse_wire(z: float, width: float, height: float, x0: float,
                 samples: int = 64) -> cq.Wire:
    points = [Vector(x0 + width / 2 * math.cos(2 * math.pi * i / samples),
                     height / 2 * math.sin(2 * math.pi * i / samples), z)
              for i in range(samples)]
    return cq.Wire.makePolygon(points, close=True)


def annulus(ro: float, ri: float, z0: float, length: float,
            x0: float = 0.0, y0: float = 0.0) -> cq.Solid:
    outer = cq.Solid.makeCylinder(ro, length, Vector(x0, y0, z0), Vector(0, 0, 1))
    inner = cq.Solid.makeCylinder(ri, length, Vector(x0, y0, z0), Vector(0, 0, 1))
    return outer.cut(inner)


def box_at(dx: float, dy: float, dz: float, centre: tuple[float, float, float]) -> cq.Solid:
    return cq.Workplane("XY").box(dx, dy, dz).translate(centre).val()


def radial_airfoil(chord: float, zcentre: float, xcentre: float,
                   beta_root: float, beta_tip: float,
                   count_angle: float, root_r: float, tip_r: float,
                   root_tc: float, tip_tc: float, camber: float) -> cq.Solid:
    sections: list[cq.Wire] = []
    radial = (math.cos(count_angle), math.sin(count_angle))
    tangent = (-math.sin(count_angle), math.cos(count_angle))
    for u in (0.0, 0.32, 0.68, 1.0):
        radius = root_r + (tip_r - root_r) * u
        beta = math.radians(beta_root + (beta_tip - beta_root) * u)
        tc = root_tc + (tip_tc - root_tc) * u
        foil = naca_points(chord, tc, camber=camber)
        coords = []
        for c, t in foil:
            tangent_offset = (c - chord / 2) * math.sin(beta) + t * math.cos(beta)
            axial_offset = (c - chord / 2) * math.cos(beta) - t * math.sin(beta)
            coords.append(Vector(xcentre + radius * radial[0] + tangent_offset * tangent[0],
                                 radius * radial[1] + tangent_offset * tangent[1],
                                 zcentre + axial_offset))
        sections.append(cq.Wire.makePolygon(coords, close=True))
    return cq.Solid.makeLoft(sections, ruled=False)


def make_hub(zcentre: float, xcentre: float) -> cq.Solid:
    hub = cq.Solid.makeCylinder(HUB_R, ROTOR_CHORD,
                                Vector(xcentre, 0, zcentre - ROTOR_CHORD / 2),
                                Vector(0, 0, 1))
    shaft = cq.Solid.makeCylinder(2.525, ROTOR_CHORD + 0.4,
                                  Vector(xcentre, 0, zcentre - ROTOR_CHORD / 2 - 0.2),
                                  Vector(0, 0, 1))
    return hub.cut(shaft)


def make_rotor_stage(row: int, zcentre: float, xcentre: float) -> cq.Compound:
    elements: list[cq.Shape] = [make_hub(zcentre, xcentre)]
    for index in range(ROTOR_COUNTS[row]):
        theta = 2 * math.pi * index / ROTOR_COUNTS[row]
        elements.append(radial_airfoil(
            ROTOR_CHORD, zcentre, xcentre,
            ROTOR_BETA_ROOT_DEG, ROTOR_BETA_TIP_DEG,
            theta, ROTOR_ROOT_R, ROTOR_TIP_R, 0.20, 0.12, 0.025,
        ))
    return cq.Compound.makeCompound(elements)


def make_stator_stage(row: int, zcentre: float, xcentre: float) -> cq.Compound:
    elements: list[cq.Shape] = []
    root_r, tip_r = HUB_R + 1.1, DUCT_ID / 2 - 0.5
    for index in range(STATOR_COUNTS[row]):
        theta = 2 * math.pi * (index + 0.5) / STATOR_COUNTS[row]
        elements.append(radial_airfoil(
            STATOR_CHORD, zcentre, xcentre, STATOR_BETA_ROOT_DEG, STATOR_BETA_TIP_DEG,
            theta, root_r, tip_r, 0.18, 0.12, 0.015,
        ))
    elements.append(annulus(HUB_R + 1.1, HUB_R + 0.4,
                            zcentre - STATOR_CHORD / 2, STATOR_CHORD, xcentre))
    elements.append(annulus(DUCT_ID / 2, DUCT_ID / 2 - 0.7,
                            zcentre - STATOR_CHORD / 2, STATOR_CHORD, xcentre))
    return cq.Compound.makeCompound(elements)


def make_body_shell() -> cq.Solid:
    # Wide battery bay and fan pair drive the central sections. The short nose
    # and upper-length selection are called out in the generated constraint log.
    stations = [
        (BODY_Z_MIN, 2.0, 2.0), (-350.0, 54.0, 34.0), (-330.0, 126.0, 66.0),
        (-300.0, BODY_WIDTH, BODY_HEIGHT), (-200.0, BODY_WIDTH, BODY_HEIGHT),
        (-100.0, BODY_WIDTH, BODY_HEIGHT), (0.0, BODY_WIDTH, BODY_HEIGHT),
        (120.0, BODY_WIDTH, BODY_HEIGHT), (200.0, 170.0, 80.0),
        (250.0, 112.0, 54.0), (BODY_Z_MAX, 3.0, 3.0),
    ]
    outer = cq.Solid.makeLoft([superellipse_wire(z, w, h) for z, w, h in stations], ruled=False)
    inner_stations = [
        (-298.8, BODY_WIDTH - 2 * BODY_SHELL, BODY_HEIGHT - 2 * BODY_SHELL),
        (-200.0, BODY_WIDTH - 2 * BODY_SHELL, BODY_HEIGHT - 2 * BODY_SHELL),
        (-100.0, BODY_WIDTH - 2 * BODY_SHELL, BODY_HEIGHT - 2 * BODY_SHELL),
        (0.0, BODY_WIDTH - 2 * BODY_SHELL, BODY_HEIGHT - 2 * BODY_SHELL),
        (120.0, BODY_WIDTH - 2 * BODY_SHELL, BODY_HEIGHT - 2 * BODY_SHELL),
        (198.0, 167.6, 77.6), (247.0, 106.0, 50.0),
    ]
    cavity = cq.Solid.makeLoft([superellipse_wire(z, w, h) for z, w, h in inner_stations], ruled=False)
    cut_tools: list[cq.Shape] = [cavity]
    for xcentre in DUCT_CENTRES_X:
        cut_tools.append(cq.Solid.makeCylinder(42.5, 402.0,
                                               Vector(xcentre, 0, -112.0),
                                               Vector(0, 0, 1)))
    # Side-facing capture slots sit just aft of the battery pack ends. They are
    # cut from the shell before the separate S-elbows are installed.
    for side in (-1, 1):
        slot_points = [Vector(side * 66.0, 42.0 * math.cos(2 * math.pi * i / 72),
                              -70.0 + 42.0 * math.sin(2 * math.pi * i / 72))
                       for i in range(72)]
        slot_wire = cq.Wire.makePolygon(slot_points, close=True)
        slot_tool = cq.Solid.extrudeLinear(slot_wire, [], Vector(side * 40.0, 0, 0))
        cut_tools.append(slot_tool)
    # Top service aperture for the two 6S packs; the removable hatch is separate.
    cut_tools.append(box_at(139.0, 24.0, 202.0, (0, 39.5, BATTERY_Z_CENTRE)))
    shell = outer.cut(cq.Compound.makeCompound(cut_tools))
    return shell


def wing_le_and_chord(x: float) -> tuple[float, float]:
    f = abs(x) / (WING_SPAN / 2)
    sweep_shift = (WING_SPAN / 2) * math.tan(math.radians(WING_SWEEP_DEG)) * f
    le = WING_ROOT_LE_Z + sweep_shift
    chord = WING_ROOT_CHORD + (WING_TIP_CHORD - WING_ROOT_CHORD) * f
    return le, chord


def wing_wire(x: float, inner: bool = False) -> cq.Wire:
    le, chord = wing_le_and_chord(x)
    if 55.25 <= abs(x) <= 204.75:
        chord -= ELEVON_CHORD + ELEVON_GAP
    thickness = max(2.0, min(WING_MAX_THICKNESS, 0.10 * chord))
    if inner:
        chord -= 2 * BODY_SHELL
        le += BODY_SHELL
        thickness -= 2 * BODY_SHELL
    points = naca_points(chord, thickness / chord, camber=0.015)
    return cq.Wire.makePolygon([Vector(x, y, le + z) for z, y in points], close=True)


def make_wing_shell() -> cq.Solid:
    xs = (-260.0, -205.01, -204.75, -130.0, -55.25, -54.99, 0.0,
          54.99, 55.25, 130.0, 204.75, 205.01, 260.0)
    outer = cq.Solid.makeLoft([wing_wire(x) for x in xs], ruled=True)
    # The airfoil loft is a lightweight foam-core envelope. Keep a positive,
    # single material solid for STEP; shell mass is estimated from its CAD skin
    # area below, rather than treating the foam envelope as solid PLA.
    wing = outer
    for xcentre in DUCT_CENTRES_X:
        bore = cq.Solid.makeCylinder(42.5, 700.0,
                                     Vector(xcentre, 0, -350), Vector(0, 0, 1))
        wing = wing.cut(bore)
    return wing


def make_elevon(side: int) -> cq.Compound:
    x0, x1 = side * 55.25, side * 204.75
    stations = []
    for i in range(5):
        x = x0 + (x1 - x0) * i / 4
        le, chord = wing_le_and_chord(x)
        te = le + chord
        p = naca_points(ELEVON_CHORD, 0.10, camber=0.01)
        stations.append(cq.Wire.makePolygon(
            [Vector(x, y * 0.55, te - ELEVON_CHORD + z) for z, y in p], close=True))
    panel = cq.Solid.makeLoft(stations, ruled=False)
    pieces: list[cq.Shape] = [panel]
    hinge_z = (wing_le_and_chord((x0 + x1) / 2)[0]
               + wing_le_and_chord((x0 + x1) / 2)[1] - ELEVON_CHORD
               + ELEVON_HINGE_FRACTION * ELEVON_CHORD)
    # Three 3 mm hinge pins and a forward balance-horn pocket/horn.
    for x in (x0 + side * 6.0, (x0 + x1) / 2, x1 - side * 6.0):
        pin = cq.Solid.makeCylinder(1.5, 6.0, Vector(x - 3.0, 0, hinge_z), Vector(1, 0, 0))
        pieces.append(pin)
    horn_x = side * 130.0
    pieces.append(box_at(18.0, 2.0, 10.0, (horn_x, -1.0, hinge_z - 6.0)))
    # LE cavity is intentionally left as the adjustable mass-balance provision.
    return cq.Compound.makeCompound(pieces)


def make_fin(side: int) -> tuple[cq.Solid, cq.Solid]:
    cant = math.radians(FIN_CANT_DEG)
    span_vec = (side * math.sin(cant), math.cos(cant))
    normal_vec = (side * math.cos(cant), -math.sin(cant))
    xroot, yroot = side * 13.0, 0.0
    lead_z = 300.0

    def fin_section(span: float, chord: float, thick_ratio: float) -> cq.Wire:
        points = naca_points(chord, thick_ratio, camber=0.01)
        xyz = [Vector(xroot + span_vec[0] * span + normal_vec[0] * t,
                      yroot + span_vec[1] * span + normal_vec[1] * t,
                      lead_z + z) for z, t in points]
        return cq.Wire.makePolygon(xyz, close=True)

    fin = cq.Solid.makeLoft([fin_section(s, FIN_CHORD, 0.10) for s in (0.0, 35.0, FIN_HEIGHT)],
                            ruled=False)
    # One rudder at the aft 30% of the right fin. A shallow cut separates it.
    if side > 0:
        angle = 90.0 - FIN_CANT_DEG
        centre = (xroot + span_vec[0] * (FIN_HEIGHT / 2),
                  yroot + span_vec[1] * (FIN_HEIGHT / 2), lead_z + FIN_CHORD * 0.85)
        axis_start = Vector(*centre)
        axis_end = Vector(centre[0], centre[1], centre[2] + 1.0)
        relief = box_at(FIN_HEIGHT + 1.0, 2.8, FIN_CHORD * 0.31, centre).rotate(
            axis_start, axis_end, angle)
        fin = fin.cut(relief)
        rudder = box_at(FIN_HEIGHT - 1.0, 1.8, FIN_CHORD * 0.30, centre).rotate(
            axis_start, axis_end, angle)
    else:
        rudder = cq.Solid.makeBox(1.0, 1.0, 1.0)
    return fin, rudder


def make_side_inlet(xcentre: float) -> cq.Compound:
    """Modular side-port elbow, bypassing the forward battery bay."""
    side = 1 if xcentre > 0 else -1
    p0 = Vector(side * 92.0, 0.0, -70.0)
    p1 = Vector(side * 70.0, 0.0, -70.0)
    p2 = Vector(xcentre, 0.0, -20.0)
    p3 = Vector(xcentre, 0.0, 0.0)
    points = (p0, p1, p2, p3)
    outer_parts: list[cq.Shape] = []
    inner_parts: list[cq.Shape] = []
    for index, (a, b) in enumerate(zip(points, points[1:])):
        axis = (b - a).normalized()
        start = a - axis.multiply(4.0)
        length = (b - a).Length + 8.0
        ro, ri = (44.0, 42.0) if index == 0 else (41.0, 39.0)
        outer_parts.append(cq.Solid.makeCylinder(ro, length, start, axis))
        inner_parts.append(cq.Solid.makeCylinder(ri, length, start, axis))
    outer = outer_parts[0].fuse(*outer_parts[1:])
    inner = inner_parts[0].fuse(*inner_parts[1:])
    shell = outer.cut(inner)
    # A Ø84 capture throat gives 55.4 cm2 per duct; the toroidal bead models a
    # 2.5 mm rolled lip without a sharp upstream edge.
    lip_axis = Vector(-side, 0, 0)
    lip_start = Vector(side * 92.0, 0, -70.0)
    lip = cq.Solid.makeTorus(44.5, INLET_LIP_RADIUS, lip_start, lip_axis)
    return cq.Compound.makeCompound([shell, lip])


def make_vane(xcentre: float, theta: float, zcentre: float = 260.0) -> cq.Compound:
    th = math.radians(theta)
    px = xcentre + VANE_RING_RADIUS * math.cos(th)
    py = VANE_RING_RADIUS * math.sin(th)
    blade = box_at(VANE_SIZE[0], 2.0, VANE_SIZE[1], (0, 0, 0))
    blade = blade.rotate((0, 0, 0), (0, 0, 1), theta).translate((px, py, zcentre))
    radial = Vector(math.cos(th), math.sin(th), 0)
    shaft = cq.Solid.makeCylinder(1.5, 24.0,
                                  Vector(px - radial.x * 12, py - radial.y * 12, zcentre), radial)
    horn = box_at(12.0, 2.0, 2.0, (px + 7 * math.cos(th), py + 7 * math.sin(th), zcentre + 19.0))
    return cq.Compound.makeCompound([blade, shaft, horn])


def make_servo_mount(centre: tuple[float, float, float], orientation_deg: float = 0.0) -> cq.Compound:
    dx, dy, dz = SERVO_ENVELOPE
    servo = box_at(dx, dy, dz, centre)
    cradle = box_at(dx + 4.0, 2.0, dz + 4.0,
                    (centre[0], centre[1] - dy / 2 - 1.0, centre[2])).rotate(
                        (centre[0], centre[1], centre[2]),
                        (centre[0], centre[1] + 1.0, centre[2]), orientation_deg)
    feet = [box_at(4.0, 5.0, 4.0, (centre[0] + sx * (dx / 2 + 1.0),
                                    centre[1] - dy / 2 - 2.5, centre[2] + sz * dz / 2))
            for sx in (-1, 1) for sz in (-1, 1)]
    arm = box_at(2.0, 2.0, 12.0, (centre[0], centre[1] + dy / 2 + 2.0,
                                  centre[2] + dz / 2 + 6.0))
    return cq.Compound.makeCompound([servo, cradle, *feet, arm])


def make_esc_geometry() -> dict[str, cq.Shape]:
    output: dict[str, cq.Shape] = {}
    esc_pcb = box_at(150.0, 1.6, 150.0, (0, BOARD_Y, ESC_Z_CENTRE))
    for x in (-67.5, 67.5):
        for z in (ESC_Z_CENTRE - 67.5, ESC_Z_CENTRE + 67.5):
            hole = cq.Solid.makeCylinder(1.6, 2.0, Vector(x, BOARD_Y - 1, z), Vector(0, 1, 0))
            esc_pcb = esc_pcb.cut(hole)
    output["esc_pcb"] = esc_pcb

    # Six-channel placement, each with six low-profile 100 V TOLT MOSFET envelopes.
    fets: list[cq.Shape] = []
    for cell_x in (-37.5, 37.5):
        for row, zbase in enumerate((ESC_Z_CENTRE - 50.0, ESC_Z_CENTRE, ESC_Z_CENTRE + 50.0)):
            for dx in (-10.0, 0.0, 10.0):
                for dz in (-6.0, 6.0):
                    fets.append(box_at(8.0, 1.4, 11.0, (cell_x + dx, BOARD_Y + 0.8, zbase + dz)))
    output["esc_36_mosfet_packages"] = cq.Compound.makeCompound(fets)

    logic: list[cq.Shape] = []
    for cell_x in (-37.5, 37.5):
        for zbase in (ESC_Z_CENTRE - 50.0, ESC_Z_CENTRE, ESC_Z_CENTRE + 50.0):
            logic.extend((box_at(10, 1.8, 10, (cell_x, BOARD_Y + 1.7, zbase)),
                          box_at(7, 2.0, 7, (cell_x + 17, BOARD_Y + 1.8, zbase + 15)),
                          box_at(14, 2.0, 8, (cell_x - 16, BOARD_Y + 1.8, zbase - 16))))
    output["esc_logic_and_passives"] = cq.Compound.makeCompound(logic)

    fuses: list[cq.Shape] = []
    copper_bars: list[cq.Shape] = []
    for i in range(6):
        z = ESC_Z_CENTRE - 57.5 + i * 23.0
        fuses.append(box_at(18.0, 5.0, 7.0, (0, BOARD_Y + 3.0, z)))
        copper_bars.append(box_at(2.0, 1.0, 118.0, (-65.0 + i * 26.0, BOARD_Y + 1.4, ESC_Z_CENTRE)))
    output["esc_six_60A_fuse_envelopes"] = cq.Compound.makeCompound(fuses)
    output["esc_six_copper_busbars"] = cq.Compound.makeCompound(copper_bars)
    esc_connectors: list[cq.Shape] = []
    for i in range(6):
        x = -50.0 + i * 20.0
        esc_connectors.append(box_at(12.0, 4.0, 8.0, (x, BOARD_Y + 3.0, 151.0)))
        cell_x = -37.5 if i < 3 else 37.5
        row_z = (170.0, 220.0, 270.0)[i % 3]
        esc_connectors.append(box_at(14.0, 5.0, 9.0, (cell_x, BOARD_Y + 3.5, row_z)))
        esc_connectors.append(box_at(10.0, 4.0, 7.0, (-68.0 if i < 3 else 68.0,
                                                     BOARD_Y + 3.0, row_z + 8.0)))
    esc_connectors += [box_at(10.0, 4.0, 8.0, (x, BOARD_Y + 3.0, ESC_Z_CENTRE + 66.0))
                       for x in (-20.0, 0.0, 20.0)]
    output["esc_battery_motor_temp_and_CAN_connectors"] = cq.Compound.makeCompound(esc_connectors)

    spreader = box_at(150.0, 1.0, 150.0, (0, SPREADER_Y + 0.5, ESC_Z_CENTRE))
    fins = [box_at(1.5, 10.0, 128.0, (x, SPREADER_Y + 6.0, ESC_Z_CENTRE))
            for x in range(-65, 66, 10)]
    output["esc_150x150_spreader_and_flow_aligned_fins"] = cq.Compound.makeCompound([spreader, *fins])

    fc_pcb = box_at(140.0, 1.6, 100.0, (0, BOARD_Y, FC_Z_CENTRE))
    for x in (-65.0, 65.0):
        for z in (FC_Z_CENTRE - 45.0, FC_Z_CENTRE + 45.0):
            fc_pcb = fc_pcb.cut(cq.Solid.makeCylinder(1.6, 2.0,
                                                      Vector(x, BOARD_Y - 1, z), Vector(0, 1, 0)))
    output["flight_control_pcb"] = fc_pcb
    fc_parts = [box_at(12, 2.0, 12, (x, BOARD_Y + 1.8, z))
                for x, z in ((-38, 325), (0, 325), (38, 325),
                             (-38, 365), (0, 365), (38, 365))]
    fc_parts += [box_at(18, 3, 8, (x, BOARD_Y + 2.0, FC_Z_CENTRE + dz))
                 for x in (-52, 52) for dz in (-25, 25)]
    output["flight_control_components"] = cq.Compound.makeCompound(fc_parts)
    output["flight_6ch_PWM_and_feedback_headers"] = cq.Compound.makeCompound([
        box_at(8.0, 3.0, 5.0, (-48.0 + i * 19.2, BOARD_Y + 2.0, FC_Z_CENTRE - 44.0))
        for i in range(6)
    ] + [box_at(8.0, 3.0, 5.0, (-48.0 + i * 19.2, BOARD_Y + 2.0, FC_Z_CENTRE + 44.0))
         for i in range(6)])
    output["fc_100x80_spreader"] = box_at(100, 1.0, 80.0, (0, SPREADER_Y + 0.5, FC_Z_CENTRE))

    tunnel_parts: list[cq.Shape] = []
    z0, z1 = COOLING_TUNNEL_Z
    length = z1 - z0
    zmid = (z0 + z1) / 2
    tunnel_parts.append(box_at(170, 2.0, length, (0, 47.0, zmid)))
    tunnel_parts.append(box_at(170, 2.0, length, (0, 74.0, zmid)))
    for x in (-84.0, 84.0):
        tunnel_parts.append(box_at(2.0, 27.0, length, (x, 60.5, zmid)))
    # Forward rounded inlet lip and aft discharge rim (both ends remain open).
    tunnel_parts.append(box_at(170, 3.0, 4.0, (0, 60.5, z0 + 1.0)))
    tunnel_parts.append(box_at(170, 3.0, 4.0, (0, 60.5, z1 - 1.0)))
    output["esc_fc_open_ended_cooling_tunnel"] = cq.Compound.makeCompound(tunnel_parts)

    board_supports = [box_at(8.0, 3.2, 8.0, (x, 49.6, z))
                      for x in (-65.0, 65.0) for z in (160.0, 280.0, 310.0, 380.0)]
    output["board_isolator_standoffs"] = cq.Compound.makeCompound(board_supports)
    return output


def make_stock_blank(profile: list[tuple[float, float]], x: float, y: float) -> cq.Solid:
    pts = [(px + x, py + y) for px, py in profile]
    return cq.Workplane("XY").polyline(pts).close().extrude(5.0).val()


def profile_bounds(profile: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Return the parametric blank's actual XY bounds before placement."""
    xs = [point[0] for point in profile]
    ys = [point[1] for point in profile]
    return min(xs), min(ys), max(xs), max(ys)


def assert_blank_inside_stock(blank: cq.Shape, stock: tuple[float, float, float],
                              edge_margin: float, label: str) -> None:
    sx, sy, sz = stock
    bb = blank.BoundingBox()
    tol = 1e-7
    if (bb.xmin < edge_margin - tol or bb.ymin < edge_margin - tol
            or bb.xmax > sx - edge_margin + tol or bb.ymax > sy - edge_margin + tol
            or bb.zmin < -tol or bb.zmax > sz + tol):
        raise ValueError(
            f"{label} exceeds stock/edge margin: "
            f"bbox=({bb.xmin:.6f},{bb.ymin:.6f},{bb.zmin:.6f},"
            f"{bb.xmax:.6f},{bb.ymax:.6f},{bb.zmax:.6f}), "
            f"stock=({sx:g},{sy:g},{sz:g}), edge_margin={edge_margin:g}"
        )


def rotor_blank_profile() -> list[tuple[float, float]]:
    top, bottom = [], []
    for i in range(25):
        u = i / 24
        span = 29.0 * u
        width = 8.2 - 3.0 * u
        centre = 0.8 * math.sin(math.pi * u) + 0.5 * u
        top.append((span, centre + width / 2))
        bottom.append((span, centre - width / 2))
    return top + list(reversed(bottom))


def stator_blank_profile() -> list[tuple[float, float]]:
    top, bottom = [], []
    for i in range(25):
        u = i / 24
        span = 16.0 * u
        width = 7.0 - 1.4 * u
        centre = 0.35 * math.sin(math.pi * u)
        top.append((span, centre + width / 2))
        bottom.append((span, centre - width / 2))
    return top + list(reversed(bottom))


def export_nest(name: str, stock: tuple[float, float, float]) -> Path:
    sx, sy, thickness = stock
    nest = cq.Assembly(name=name)
    raw = cq.Workplane("XY").box(sx, sy, thickness, centered=(False, False, False)).val()
    nest.add(raw, name="raw_stock", color=Color(0.58, 0.64, 0.68, 0.20))
    rotor_profile = rotor_blank_profile()
    stator_profile = stator_blank_profile()
    rotor_x0, rotor_y0, rotor_x1, rotor_y1 = profile_bounds(rotor_profile)
    stator_x0, stator_y0, stator_x1, stator_y1 = profile_bounds(stator_profile)
    rotor_x_pitch = (rotor_x1 - rotor_x0) + BLANK_SPACING
    rotor_y_pitch = (rotor_y1 - rotor_y0) + BLANK_SPACING
    # Anchor the measured profile bounds to the required stock edge margin.
    rotor_x_origin = EDGE_MARGIN - rotor_x0
    rotor_y_origin = EDGE_MARGIN - rotor_y0
    rotor_rows = math.ceil(36 / 8)
    rotor_top = rotor_y_origin + (rotor_rows - 1) * rotor_y_pitch + rotor_y1
    # Keep at least the declared gap between the rotor group and the stator
    # group. The stator rows retain their existing 9.7 mm pitch (>= 1.5 mm
    # based on their actual profile envelope).
    stator_y_origin = rotor_top + BLANK_SPACING - stator_y0
    stator_x_pitch = (stator_x1 - stator_x0) + BLANK_SPACING
    stator_y_pitch = max(8.2, stator_y1 - stator_y0) + BLANK_SPACING
    # 36 rotors: 8 columns x 5 rows; only four positions in the last row used.
    for i in range(36):
        row, col = divmod(i, 8)
        x = rotor_x_origin + col * rotor_x_pitch
        y = rotor_y_origin + row * rotor_y_pitch
        blank = make_stock_blank(rotor_profile, x, y)
        assert_blank_inside_stock(blank, stock, EDGE_MARGIN, f"rotor_blank_{i + 1:02d}")
        nest.add(blank, name=f"rotor_blank_{i + 1:02d}",
                 color=Color(0.91, 0.49, 0.18, 0.95))
    # 63 stators: 12 columns x 6 rows; nine positions remain unused.
    for i in range(63):
        row, col = divmod(i, 12)
        x = EDGE_MARGIN - stator_x0 + col * stator_x_pitch
        y = stator_y_origin + row * stator_y_pitch
        blank = make_stock_blank(stator_profile, x, y)
        assert_blank_inside_stock(blank, stock, EDGE_MARGIN, f"stator_vane_blank_{i + 1:03d}")
        nest.add(blank, name=f"stator_vane_blank_{i + 1:03d}",
                 color=Color(0.20, 0.55, 0.82, 0.95))
    path = NEST_DIR / f"{name}.step"
    nest.save(str(path), exportType="STEP", tolerance=0.01, angularTolerance=0.1)
    return path


def export_hub_bar_nest() -> Path:
    sx, sy, sz = BAR
    nest = cq.Assembly(name="six_40mm_hubs_300x50x16_6061_bar")
    nest.add(cq.Workplane("XY").box(sx, sy, sz, centered=(False, False, False)).val(),
             name="raw_6061_bar", color=Color(0.58, 0.64, 0.68, 0.20))
    pitch = HUB_D + BLANK_SPACING
    first_centre = BAR_CLAMP_MARGIN + HUB_R
    for i in range(6):
        cx = first_centre + i * pitch
        hub = cq.Solid.makeCylinder(HUB_R, sz, Vector(cx, sy / 2, 0), Vector(0, 0, 1))
        hole = cq.Solid.makeCylinder(2.525, sz + 0.2, Vector(cx, sy / 2, -0.1), Vector(0, 0, 1))
        nest.add(hub.cut(hole), name=f"turned_hub_blank_{i + 1:02d}",
                   color=Color(0.87, 0.72, 0.28, 0.95))
    path = NEST_DIR / "six_hubs_300x50x16_bar.step"
    nest.save(str(path), exportType="STEP", tolerance=0.01, angularTolerance=0.1)
    return path


def make_projection() -> tuple[Polygon, dict[str, Polygon]]:
    # Orthographic X-Y projection. Through-bores are removed from body/wing;
    # the rotor/hub annuli are added as actual solid fan structure.
    body = Polygon([
        (BODY_WIDTH / 2 * math.copysign(abs(math.cos(2 * math.pi * i / 180)) ** (2 / BODY_EXPONENT),
                                        math.cos(2 * math.pi * i / 180)),
         BODY_HEIGHT / 2 * math.copysign(abs(math.sin(2 * math.pi * i / 180)) ** (2 / BODY_EXPONENT),
                                         math.sin(2 * math.pi * i / 180)))
        for i in range(180)
    ])
    holes = [Point(x, 0).buffer(42.5, quad_segs=48) for x in DUCT_CENTRES_X]
    body = body.difference(unary_union(holes))
    half = WING_SPAN / 2
    xs = [-half + i * WING_SPAN / 80 for i in range(81)]
    top, bottom = [], []
    for x in xs:
        _, chord = wing_le_and_chord(x)
        thick = min(WING_MAX_THICKNESS, 0.10 * chord)
        top.append((x, thick / 2))
        bottom.append((x, -thick / 2))
    wing = Polygon(top + list(reversed(bottom))).difference(unary_union(holes))
    components: list[Polygon] = [body, wing]
    # Duct walls and rotating/stationary gas-path metal are separately included.
    for x in DUCT_CENTRES_X:
        outer = Point(x, 0).buffer(DUCT_OD / 2, quad_segs=64)
        inner = Point(x, 0).buffer(DUCT_ID / 2, quad_segs=64)
        components.append(outer.difference(inner))
        fan_outer = Point(x, 0).buffer(ROTOR_TIP_R, quad_segs=64)
        fan_inner = Point(x, 0).buffer(HUB_R, quad_segs=64)
        components.append(fan_outer.difference(fan_inner))
        components.append(fan_inner)
    # Fin cross-section projections; finite thickness of each canted fin.
    fin_projected: list[Polygon] = []
    cant = math.radians(FIN_CANT_DEG)
    for side in (-1, 1):
        root_x = side * 13.0
        tip_x = root_x + side * FIN_HEIGHT * math.sin(cant)
        tip_y = FIN_HEIGHT * math.cos(cant)
        fin_projected.append(Polygon([(root_x - 4.5, 0), (root_x + 4.5, 0),
                                      (tip_x + 4.5, tip_y), (tip_x - 4.5, tip_y)]))
    components.extend(fin_projected)
    silhouettes = {"body": body, "wing": wing, "fins": unary_union(fin_projected)}
    return unary_union(components), silhouettes


def write_silhouette_svg(projected: Polygon, silhouettes: dict[str, Polygon]) -> None:
    minx, miny, maxx, maxy = projected.bounds
    margin = 12.0
    width, height = maxx - minx + margin * 2, maxy - miny + margin * 2
    tx, ty = margin - minx, margin + maxy

    def path_for(poly: Polygon) -> str:
        polys = list(poly.geoms) if poly.geom_type == "MultiPolygon" else [poly]
        path_commands = []
        for shape in polys:
            rings = [shape.exterior, *shape.interiors]
            for ring in rings:
                pts = list(ring.coords)
                path_commands.append("M " + " L ".join(f"{x + tx:.2f} {ty - y:.2f}" for x, y in pts) + " Z")
        return " ".join(path_commands)

    body_path = path_for(silhouettes["body"])
    wing_path = path_for(silhouettes["wing"])
    fin_path = path_for(silhouettes["fins"])
    total_path = path_for(projected)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}mm" height="{height:.1f}mm" viewBox="0 0 {width:.1f} {height:.1f}">
<rect width="100%" height="100%" fill="white"/>
<path d="{body_path}" fill="#c8d5df" fill-rule="evenodd" stroke="#293b4a" stroke-width="0.7"/>
<path d="{wing_path}" fill="#8cb8d8" fill-rule="evenodd" stroke="#244d69" stroke-width="0.7"/>
<path d="{fin_path}" fill="#e1a66b" fill-rule="evenodd" stroke="#70451e" stroke-width="0.7"/>
<path d="{total_path}" fill="none" stroke="#111" stroke-width="0.45"/>
<text x="8" y="15" font-family="sans-serif" font-size="6">Phase 15 projected frontal solid union, X-Y; fan through-bores are open except physical fan annuli</text>
<text x="8" y="23" font-family="sans-serif" font-size="5">Union area = {projected.area / 100:.1f} cm^2 | target 242-270-296 cm^2</text>
<text x="8" y="31" font-family="sans-serif" font-size="5">Duct axes X = -44,+44 mm; bore Ø78 mm; two independent paths</text>
</svg>'''
    (REPORT_DIR / "projected_frontal_silhouette.svg").write_text(svg, encoding="utf-8")


def mass_properties() -> tuple[list[dict[str, object]], dict[str, float]]:
    rows: list[dict[str, object]] = []
    total = 0.0
    mx = my = mz = 0.0
    for part in parts:
        volume_mm3 = abs(part.shape.Volume())
        if part.mass_override_kg is None:
            mass = volume_mm3 * MATERIAL_DENSITY_KG_M3[part.material] / 1e9
            basis = f"CAD volume {volume_mm3:.1f} mm^3 × {MATERIAL_DENSITY_KG_M3[part.material]:g} kg/m^3"
        else:
            mass = part.mass_override_kg
            basis = f"dimension envelope with analyst/sourced mass override {mass:.4f} kg"
        centre = part.shape.Center()
        rows.append({"component": part.name, "material": part.material,
                     "massKg": mass, "volumeMm3": volume_mm3,
                     "cgXmm": centre.x, "cgYmm": centre.y, "cgZmm": centre.z,
                     "basis": basis, "note": part.note})
        total += mass
        mx += mass * centre.x
        my += mass * centre.y
        mz += mass * centre.z
    payload_z = PAYLOAD_CG_Z_MM
    # Keep the unspecified 1 kg payload forward of the battery bay. At this
    # selected point, the modeled total CG remains inside the specified band.
    rows.append({"component": "payload_point_mass", "material": "not-geometrized",
                 "massKg": PAYLOAD_MASS_KG, "volumeMm3": 0.0,
                 "cgXmm": 0.0, "cgYmm": 0.0, "cgZmm": payload_z,
                 "basis": "1.0 kg handoff payload; analyst placement 20 mm forward of battery-bay boundary",
                 "note": "Point mass only; excluded from STEP solids"})
    total += PAYLOAD_MASS_KG
    mz += PAYLOAD_MASS_KG * payload_z
    base_cg = {"x": mx / total, "y": my / total, "z": mz / total}
    reserve = total * GROWTH_RESERVE_FRACTION
    return rows, {"hardwarePlusPayloadKg": total, "growthReserveKg": reserve,
                  "allUpWith15PercentReserveKg": total + reserve,
                  "cgXmm": base_cg["x"], "cgYmm": base_cg["y"], "cgZmm": base_cg["z"]}


def write_parameter_register() -> None:
    register = {
        "datum": {"x": "lateral", "y": "vertical", "z": "aft", "fanPlaneZmm": 0,
                  "units": "mm"},
        "sourceFiles": [
            "design/HANDOFF_GEOMETRY_AGENT.md", "design/PHASE15_DESIGN_SPEC.md",
            "design/PHASE15_CONTROL_SURFACES.md", "design/DESIGN_DECISIONS_FOR_VERDICT.md",
            "phase15/results/phase15_motor_and_rewind_v2.md",
            "phase15/configs/phase15_sourcing.json",
        ],
        "nominal": {
            "ductOuterDiameterMm": DUCT_OD, "ductInnerDiameterMm": DUCT_ID,
            "ductRadialWallMm": DUCT_WALL_RADIAL, "ductCentreSpacingMm": 88,
            "ductCentresXmm": list(DUCT_CENTRES_X), "moduleLengthMm": DUCT_LENGTH,
            "inletMouthAreaPerDuctCm2": math.pi * 42.0**2 / 100.0,
            "inletMouthAreaTotalCm2": 2 * math.pi * 42.0**2 / 100.0,
            "rotorCounts": list(ROTOR_COUNTS), "statorCounts": list(STATOR_COUNTS),
            "rotorZmm": list(ROTOR_Z), "statorZmm": list(STATOR_Z),
            "hubDiameterMm": HUB_D, "rotorTipClearanceMm": DUCT_ID / 2 - ROTOR_TIP_R,
            "rotorSpanMm": ROTOR_SPAN, "bodyLengthMm": BODY_LENGTH,
            "bodyEnvelopeMm": [BODY_WIDTH, BODY_HEIGHT], "bodySuperellipseExponent": BODY_EXPONENT,
            "bodyWallMm": BODY_SHELL, "wingSpanMm": WING_SPAN,
            "wingAreaM2": WING_AREA_M2, "wingAspectRatio": WING_AR,
            "wingSweepDeg": WING_SWEEP_DEG, "elevonMm": [ELEVON_CHORD, ELEVON_SPAN],
            "finMm": [FIN_CHORD, FIN_HEIGHT], "finCantDeg": FIN_CANT_DEG,
            "vaneCount": 4, "vaneSizeMm": list(VANE_SIZE), "vaneRingRadiusMm": VANE_RING_RADIUS,
            "batteryBayXYZmm": [BATTERY_BAY[1], BATTERY_BAY[2], BATTERY_BAY[0]],
            "escBoardXZThicknessMm": list(ESC_BOARD), "escBoardCentreYZmm": [BOARD_Y, ESC_Z_CENTRE],
            "flightBoardXZThicknessMm": list(FC_BOARD), "flightBoardCentreYZmm": [BOARD_Y, FC_Z_CENTRE],
            "coolingTunnelZmm": list(COOLING_TUNNEL_Z),
        },
        "bands": {
            "ductODmm": [72, 80, 90], "ductLengthMm": [95, 110, 130],
            "ductSpacingMm": [84, 88, 96], "bodySectionMm": [[175, 72], [186, 78], [205, 90]],
            "bodyLengthMm": [480, 560, 640], "wingAreaM2": [0.13, 0.19, 0.30],
            "wingSpanMm": [450, 520, 620], "wingAR": [1.30, 1.42, 1.80],
            "elevonChordSpanMm": [[25, 100], [40, 150], [60, 200]],
            "finHeightChordMm": [[50, 60], [70, 90], [100, 130]],
        },
        "derivedParameters": {
            "statorMetalAnglesDeg": [STATOR_BETA_ROOT_DEG, STATOR_BETA_TIP_DEG],
            "basis": "No Phase-15 stator angle schedule in source handoff; neutral seed is adjustable and not aerodynamically qualified.",
            "highTempDuctMaterial": "High-temp CF composite shell, provisional material class; select resin/core only after temperature qualification.",
            "servoMassKg": SERVO_MASS_KG,
            "servoMassBasis": "Analyst envelope allowance; control doc gives actuator count/type but no unit mass.",
            "payloadCGmm": [0, 0, 0],
            "payloadCGZmm": PAYLOAD_CG_Z_MM,
            "payloadCGBasis": "Selected 20 mm forward of the Z=-300 battery-bay boundary; hardware moments yield CG within -5..+15 mm. Payload envelope/fit remains unspecified.",
        },
    }
    (REPORT_DIR / "phase15_parameter_register.json").write_text(json.dumps(register, indent=2) + "\n", encoding="utf-8")


def write_manufacturing_report(stock_nests: Iterable[Path], projected_area_cm2: float,
                               mass: dict[str, float], roundtrip: list[dict[str, object]]) -> None:
    source = "design/HANDOFF_GEOMETRY_AGENT.md"
    report = f'''# Phase-15 geometry generation and manufacturing report

Generated from `{source}`. Coordinate convention: X lateral, Y vertical, +Z aft,
Z=0 at the first rotor plane. Units are mm unless noted. CAD is a mechanical layout
model and envelope set; it is not a fabrication or flight-release design.

## Delivered CAD

- `step/phase15_airframe_full_assembly.step` — airframe, two independent 80 mm fan paths, rotor/stator rows, effectors, battery bay, motors as sourced envelopes, and landing/board support geometry.
- `step/phase15_esc_cooling_assembly.step` — 150×150 mm six-channel ESC, 36 MOSFET envelopes, six fuses/busbars, 150×150 spreader, flight board, 100×80 spreader, open-ended cooling tunnel and mounts.
- `step/*.step` — each registered part/subassembly exported separately; all stock nests are in `stock_nests/`.
- `reports/projected_frontal_silhouette.svg` — projected union drawing with the twin through-ducts visibly open around physical fan hardware.
- `reports/mass_cg.csv`, `reports/step_reimport_validation.csv`, `reports/phase15_parameter_register.json`.

## Nominal selections and manufacturing process

- Fan tubes use Ø82 OD / Ø78 bore (2 mm radial wall), two axes at X=±44; the 82 mm OD is inside the 72–90 band and keeps a true 2 mm composite wall. The inlet mouths are Ø84 mm side-facing ports, 55.4 cm² each (110.8 cm² total), with a 2.5 mm toroidal lip and a 100 mm segmented elbow into the axial ducts.
- Body and wing are modeled as 1.2 mm skins over cold-side PLA core, with the two EDF passages kept clear. The fuselage is a 640 mm master shell with internal frames at Z=-100/+100 mm; section the master at those planes into ≤260 mm FDM pieces and use sealed scarf/flange joints. Split the 520 mm wing on the X=0 joiner web into two 260 mm panels. Main shell and wing use composite wrap; no PLA is assigned to the duct, nozzle, motor bay or hot-side insert.
- Duct/nozzle hot-side shell is represented as high-temperature CF composite; qualify core/resin service temperature and hoop strength before manufacture. A 6061 insert/capture ring is required at every rotor-retention station. The exact high-temperature material and insert fastener details are not present in the source data.
- All 72 rotor and 126 stator blanks are nested on the stated 250×120×5 and 300×120×5 sheets, split evenly (36+63 per sheet), at 1.5 mm nominal inter-part spacing and 1 mm edge margin. The nests are geometry-only: rough blanks require indexed/two-sided machining, deburring, root retention, balance and overspeed qualification. The 300 mm sheet consumes the nominal X travel of a 3018-class machine; side clamps/vacuum fixture and tool overtravel must be validated before CAM.
- Six Ø40×16 hubs fit the 300×50×16 bar inside a 250 mm usable length with 25 mm end clamp zones. Hub turning/bore finishing and rotor balancing are separate operations. No production G-code is emitted from an unverified fixture.

## Constraint audit / unavoidable incompatibilities

1. The body section height is 88 mm rather than the 78 mm nominal because the 80+ mm outer duct pair must fit; 88 mm is within the 72–90 mm section band. Body outline area is approximately 140 cm² for exponent 2.6, within the stated 126–185 cm² band.
2. The 200×135×75 mm reserved bay is aligned with Z as its 200 mm axis. The two supplied 185×65×55 packs fit side-by-side in X with 5 mm total width clearance and are slid to Z=-207.5 so their aft faces clear the side-inlet passages. Full-section body from the forward bay boundary to aft keeps this envelope inside the shell; body length is selected at the 640 mm upper bound.
3. The 72 mm motor envelopes are placed immediately aft of their rotor hubs. Rotor stations are 36 mm apart, so adjacent motor envelopes overlap axially by 36 mm. This violates physical buildability; the sourced motor size and rotor-row pitch cannot both be met with coaxial direct drive. The STEP intentionally shows the envelope collision; no overlap is hidden or boolean-subtracted.
4. Four separate vanes plus two elevons and one rudder require seven servos. All seven mounts/horns are modeled. The fixed flight-board interface has six PWM channels (F-05 remains unresolved), so one surface has no assigned command channel. No common-exit redesign is assumed.
5. The ESC and flight-board locations (Y≈52, Z≈220/345) are outside the 88 mm body section and are carried by the specified dorsal, open-ended cooling tunnel. The duct bleed-air inlet/flow rate remains a thermal design item; the tunnel has forward and aft open ports.
6. The 640 mm body length and 200 mm bay leave only about 60 mm between the forward bay boundary and the nose tip in this datum. The specified 2.5–5 nose-fineness ratio cannot be achieved simultaneously with this bay placement and length band; the nose is a packaging-driven short loft, not a drag-qualified ogive.
7. Stator vane angles are a neutral adjustable seed because no phase-15 metal-angle schedule was found in the supplied authoritative files. Blade-angle/performance, rotor containment, flutter and composite hoop strength are not validated by CAD.
8. CAD projected frontal solid union is {projected_area_cm2:.1f} cm² versus the 242–296 cm² target. The fan bores are modeled as through-holes; the physical duct rings, fan annuli, hubs and fins remain in the union. This measured CAD projection is reported as-is; no solid area is added to force the target.
9. CAD mass properties give {mass['hardwarePlusPayloadKg']:.3f} kg including the 1 kg payload, and {mass['allUpWith15PercentReserveKg']:.3f} kg with the specified 15% growth reserve. CG is ({mass['cgXmm']:.1f}, {mass['cgYmm']:.1f}, {mass['cgZmm']:.1f}) mm from the fan datum. The 1 kg payload is a point mass at Z=-320 mm, 20 mm forward of the bay; its envelope and mount must be checked against the installed part. Motor, pack and servo masses are explicit source/analyst overrides; this is not a weighed aircraft.

## STEP validation

Reimport test results: {sum(1 for row in roundtrip if row['status'] == 'PASS')}/{len(roundtrip)} files passed positive-volume/valid-solid checks. See `reports/step_reimport_validation.csv` for per-file solid counts and volumes.

## Geometry is complete, hardware compatibility is not

The requested airframe and ESC CAD, mounts, toleranced stock nests, silhouette,
mass/CG estimate and source/assumption register are present. The numbered
interference/channel issues above are design gates from mutually incompatible
inputs, not missing CAD parts.
'''
    (REPORT_DIR / "phase15_geometry_manufacturing_report.md").write_text(report, encoding="utf-8")


def build() -> None:
    print("building Phase-15 airframe geometry", flush=True)
    # These two directories are owned by this generator. Remove only its STEP
    # exports so re-runs cannot include superseded geometry in validation.
    for generated_dir in (STEP_DIR, NEST_DIR):
        for old_step in generated_dir.glob("*.step"):
            old_step.unlink()
    white = Color(0.82, 0.84, 0.86)
    body_color = Color(0.74, 0.78, 0.82)
    composite_color = Color(0.28, 0.39, 0.48)
    aluminum_color = Color(0.72, 0.72, 0.68)
    motor_color = Color(0.20, 0.22, 0.24)
    electronics_color = Color(0.18, 0.42, 0.25)
    control_color = Color(0.92, 0.48, 0.16)
    battery_color = Color(0.35, 0.38, 0.42)

    # Main cold-side body and wing.
    body_shell = make_body_shell()
    print("body shell built", flush=True)
    add_part("fuselage_battery_bay_shell", body_shell, "PLA-core-CF-wrap", body_color,
             note="640 mm shell master; split into ≤260 mm print sections at the two modeled internal frames")
    joint_parts = [box_at(2.0, 76.0, 8.0, (x, 0, z))
                   for z in (-100.0, 100.0) for x in (-88.5, 88.5)]
    add_part("fuselage_internal_bay_side_rails", cq.Compound.makeCompound(joint_parts),
             "high-temp-CF-composite", composite_color,
             note="side-reinforcement rails at Z=-100 and +100; clear of the twin duct bores")
    print("body rails placed", flush=True)
    wing = make_wing_shell()
    print("wing shell built", flush=True)
    wing_skin_mass = wing.Area() * BODY_SHELL * MATERIAL_DENSITY_KG_M3["PLA-core-CF-wrap"] / 1e9
    wing_solids = sorted(wing.Solids(), key=lambda s: s.Center().x)
    total_wing_area = sum(s.Area() for s in wing_solids)
    for index, wing_solid in enumerate(wing_solids):
        xmid = wing_solid.Center().x
        label = "left" if xmid < -10.0 else ("right" if xmid > 10.0 else "centre_bridge")
        placed_solid = wing_solid
        if label == "left":
            # Reversed orientation is the OCCT STEP-writer convention needed for
            # a positive-volume round-trip of the mirrored port wing sector.
            placed_solid = cq.Solid(wing_solid.wrapped.Reversed())
        add_part(f"lifting_wing_{label}_sector_with_duct_and_elevon_reliefs", placed_solid,
                 "PLA-core-CF-wrap", body_color,
                 wing_skin_mass * wing_solid.Area() / total_wing_area,
                 note=f"520 mm overall span; panel/central bridge sector {index + 1}/3; positive-volume STEP orientation")
    add_part("wing_center_joiner_web", box_at(6.0, 18.0, 96.0, (0.0, 0.0, -88.0)),
             "carbon-rod", composite_color, note="centre joint shear-transfer envelope; laminate schedule TBD")
    for side, label in ((-1, "left"), (1, "right")):
        add_part(f"elevon_{label}_40x150", make_elevon(side), "PLA-core-CF-wrap", control_color,
                 note="30% chord hinge, 0.5 mm gap, balance mass pocket/horn provision")

    # Ducts, inlet lips, nozzles, rotor/stator stacks, and hot-side motor envelopes.
    motor_records: list[tuple[str, cq.Shape]] = []
    for duct_index, xcentre in enumerate(DUCT_CENTRES_X):
        letter = "A" if duct_index == 0 else "B"
        print(f"building duct {letter}", flush=True)
        tube = annulus(DUCT_OD / 2, DUCT_ID / 2, 0.0, DUCT_LENGTH, xcentre)
        add_part(f"duct_{letter}_82OD_78ID_L110", tube, "high-temp-CF-composite", composite_color,
                 note="2 mm radial wall; high-temperature resin/core qualification required")
        transition = make_side_inlet(xcentre)
        add_part(f"duct_{letter}_side_inlet_100mm", transition,
                 "high-temp-CF-composite", composite_color,
                 note="side-facing Ø84 mm port; 55.4 cm2 each, 110.8 cm2 total; modular 100 mm elbow path")
        print(f"duct {letter} inlet built", flush=True)
        nozzle = annulus(DUCT_OD / 2, DUCT_ID / 2, NOZZLE_Z0, NOZZLE_Z1 - NOZZLE_Z0, xcentre)
        lip = annulus(DUCT_OD / 2, DUCT_ID / 2, NOZZLE_Z1, 3.0, xcentre)
        add_part(f"duct_{letter}_separate_nozzle_and_exit_lip", cq.Compound.makeCompound([nozzle, lip]),
                 "high-temp-CF-composite", composite_color,
                 note="separate parallel exit; internal exit area ratio 1.0 nominal")
        # Thin metal inlet/outlet capture rings and each row's high-temperature carrier.
        add_part(f"duct_{letter}_rotor_containment_collar", annulus(42.0, 40.5, 4.0, 4.0, xcentre),
                 "6061-T6", aluminum_color, note="metal rotor-retention interface; final fastener pattern TBD")
        for row, z in enumerate(ROTOR_Z):
            rotor = make_rotor_stage(row, z, xcentre)
            add_part(f"duct_{letter}_rotor_R{row + 1}_N{ROTOR_COUNTS[row]}", rotor,
                     "6061-T6", aluminum_color,
                     note=f"{ROTOR_RPM[row]} rpm design point; 16 mm chord; twisted NACA-like blades")
            hub_back = z + ROTOR_CHORD / 2
            can_start = hub_back
            can = cq.Solid.makeCylinder(MOTOR_CAN_D / 2, MOTOR_CAN_LENGTH,
                                        Vector(xcentre, 0, can_start), Vector(0, 0, 1))
            can = can.fuse(cq.Solid.makeCylinder(2.5, 8.0,
                                                 Vector(xcentre, 0, can_start - 8.0), Vector(0, 0, 1)))
            motor_name = f"motor_{letter}_R{row + 1}_3670_42x72_envelope"
            add_part(motor_name, can, "electronics-envelope", motor_color, MOTOR_MASS_KG,
                     note="Surpass Rocket 3670 4-pole envelope; overlaps adjacent coaxial cans per report")
            motor_records.append((motor_name, can))
            print(f"duct {letter} rotor/motor row {row + 1} built", flush=True)
        for row, z in enumerate(STATOR_Z):
            stator = make_stator_stage(row, z, xcentre)
            add_part(f"duct_{letter}_stator_S{row + 1}_N{STATOR_COUNTS[row]}", stator,
                     "6061-T6", aluminum_color,
                     note="8 mm chord; neutral adjustable metal-angle seed")
            print(f"duct {letter} stator row {row + 1} built", flush=True)
        # Two independent tangential vanes per duct, with bearings, horn and servo mount.
        ring = annulus(48.0, 41.0, 250.0, 4.0, xcentre)
        add_part(f"duct_{letter}_vector_vane_bearing_ring", ring, "6061-T6", aluminum_color)
        for vane_index, theta in enumerate((90.0, 270.0), start=1):
            add_part(f"duct_{letter}_vector_vane_{vane_index}_30x40", make_vane(xcentre, theta),
                     "6061-T6", control_color,
                     note="30x40 mm vane; pivot radius 44 mm; default 0 deg, parameterized to ±22 deg")
            rad = math.radians(theta)
            servo_center = (xcentre + 44.0 * math.cos(rad), 62.0 * math.sin(rad), 260.0)
            add_part(f"servo_mount_vane_{letter}{vane_index}", make_servo_mount(servo_center),
                     "electronics-envelope", control_color, SERVO_MASS_KG,
                     note="one of four jet-vane actuators; available PWM allocation unresolved")
        print(f"duct {letter} exit effectors built", flush=True)

    # Tail fins, a single rudder, and aft carrier booms.
    fin_l, unused_rudder = make_fin(-1)
    fin_r, rudder = make_fin(1)
    add_part("canted_tail_fin_left_70x90", fin_l, "PLA-core-CF-wrap", body_color)
    add_part("canted_tail_fin_right_70x90_with_rudder_cut", fin_r, "PLA-core-CF-wrap", body_color)
    add_part("single_right_fin_rudder_27mm", rudder, "PLA-core-CF-wrap", control_color,
             note="one rudder per F-10 accepted single-point yaw-degradation option")
    boom_shapes = []
    for side in (-1, 1):
        boom_shapes.append(cq.Solid.makeCylinder(4.0, 70.0,
                                                 Vector(side * 13.0, 0, 230.0), Vector(0, 0, 1)))
    add_part("twin_carbon_tail_support_booms", cq.Compound.makeCompound(boom_shapes),
             "carbon-rod", composite_color, note="8 mm provisional support diameter; fin roots at Z=300")
    add_part("servo_mount_right_fin_rudder", make_servo_mount((31.0, 18.0, 330.0)),
             "electronics-envelope", control_color, SERVO_MASS_KG,
             note="seventh total servo position; no seventh PWM channel in fixed six-channel interface")

    # Elevon actuator mounts and aerodynamic/structural pushrod representatives.
    for side, label in ((-1, "left"), (1, "right")):
        c = (side * 125.0, -27.0, 112.0)
        add_part(f"servo_mount_elevon_{label}", make_servo_mount(c),
                 "electronics-envelope", control_color, SERVO_MASS_KG)
        rod = cq.Solid.makeCylinder(1.0, 38.0,
                                    Vector(side * 125.0, -15.0, 116.0), Vector(0, 1, 0))
        add_part(f"elevon_pushrod_{label}", rod, "6061-T6", aluminum_color)

    # Battery packs, rails, restraints, and removable service hatch.
    batteries = []
    for i, xcentre in enumerate((-33.0, 33.0), start=1):
        pack = box_at(*BATTERY_PACK, (xcentre, 0.0, BATTERY_Z_CENTRE))
        batteries.append(pack)
        add_part(f"Bonka_6S_1600_pack_{i}_185x65x55", pack, "battery-envelope", battery_color, 0.28,
                 note="sourced envelope; pair mass is handoff nominal 0.56 kg")
    rail_parts = [box_at(2.0, 4.0, 185.0, (x, -31.0, BATTERY_Z_CENTRE))
                  for x in (-67.0, 67.0)]
    rail_parts += [box_at(136.0, 3.0, 2.0, (0, -28.5, z)) for z in (-295.0, -120.0)]
    add_part("battery_sliding_rails_and_6g_end_stops", cq.Compound.makeCompound(rail_parts),
             "6061-T6", aluminum_color, note="rail envelope reserves the 200x135x75 future bay")
    strap_parts = [box_at(136.0, 1.0, 5.0, (0, 31.0, z)) for z in (-275.0, -125.0)]
    add_part("battery_retention_straps", cq.Compound.makeCompound(strap_parts), "high-temp-CF-composite",
             composite_color, note="retention geometry; size/load verification required")
    hatch = box_at(143.0, 2.4, 204.0, (0, 45.0, BATTERY_Z_CENTRE))
    hatch_screws = [cq.Solid.makeCylinder(1.2, 3.0, Vector(x, 43.8, z), Vector(0, 1, 0))
                    for x in (-65.0, 65.0) for z in (-292.0, -108.0)]
    add_part("battery_service_hatch_and_fastener_envelopes",
             cq.Compound.makeCompound([hatch, *hatch_screws]), "PLA-core-CF-wrap", body_color)

    # Internal motor carriers and two carbon skids. Motor can interference remains visible.
    carrier_shapes = []
    for xcentre in DUCT_CENTRES_X:
        for z in ROTOR_Z:
            carrier_shapes.append(annulus(39.0, 37.0, z - 2.0, 4.0, xcentre))
            for theta in (0, 90, 180, 270):
                a = math.radians(theta)
                carrier_shapes.append(box_at(16.0, 2.0, 4.0,
                                             (xcentre + 31.0 * math.cos(a),
                                              31.0 * math.sin(a), z)))
    add_part("six_hot_side_motor_carrier_frames", cq.Compound.makeCompound(carrier_shapes),
             "6061-T6", aluminum_color, note="high-temperature carrier geometry; final attachment TBD")
    skid_parts = []
    for side in (-1, 1):
        skid_parts.append(cq.Solid.makeCylinder(4.0, 250.0,
                                                Vector(side * 55.0, -59.0, -135.0), Vector(0, 0, 1)))
        for z in (-105.0, 120.0):
            start = Vector(side * 55.0, -42.0, z)
            direction = Vector(0, -1, 0)
            skid_parts.append(cq.Solid.makeCylinder(3.0, 18.0, start, direction))
    add_part("twin_landing_skids_and_legs", cq.Compound.makeCompound(skid_parts),
             "carbon-rod", composite_color, note="CFRP skid envelopes; load qualification required")

    # ESC, flight board, spreaders, and the open-ended cooling tunnel.
    esc_shapes = make_esc_geometry()
    print("airframe, fan and ESC shapes built", flush=True)
    esc_materials = {
        "esc_pcb": ("FR4-PCB", electronics_color, None),
        "esc_36_mosfet_packages": ("electronics-envelope", Color(0.14, 0.17, 0.19), None),
        "esc_logic_and_passives": ("electronics-envelope", Color(0.24, 0.51, 0.30), None),
        "esc_six_60A_fuse_envelopes": ("electronics-envelope", Color(0.78, 0.48, 0.12), None),
        "esc_six_copper_busbars": ("copper", Color(0.78, 0.40, 0.14), None),
        "esc_battery_motor_temp_and_CAN_connectors": ("electronics-envelope", Color(0.78, 0.48, 0.12), None),
        "esc_150x150_spreader_and_flow_aligned_fins": ("6061-T6", aluminum_color, None),
        "flight_control_pcb": ("FR4-PCB", electronics_color, None),
        "flight_control_components": ("electronics-envelope", Color(0.24, 0.51, 0.30), None),
        "flight_6ch_PWM_and_feedback_headers": ("electronics-envelope", Color(0.78, 0.48, 0.12), None),
        "fc_100x80_spreader": ("6061-T6", aluminum_color, None),
        "esc_fc_open_ended_cooling_tunnel": ("high-temp-CF-composite", composite_color, None),
        "board_isolator_standoffs": ("high-temp-CF-composite", composite_color, None),
    }
    for name, shape in esc_shapes.items():
        material, color, override = esc_materials[name]
        add_part(name, shape, material, color, override,
                 note="board is represented as geometry envelope; final PCB routing/population is a separate design")

    # Build subassembly STEP deliverables from the registered geometries.
    for prefix, filename in (("esc_", "phase15_esc_cooling_assembly.step"),
                             ("flight_", "phase15_flight_board_assembly.step"),
                             ("fc_", "phase15_fc_spreader.step"),
                             ("duct_", "phase15_twin_ducts_and_fans.step")):
        sub = cq.Assembly(name=prefix.rstrip("_") + "_subassembly")
        for part in parts:
            if part.name.startswith(prefix):
                sub.add(part.shape, name=part.name, color=part.color)
        if prefix == "esc_":
            for part in parts:
                if (part.name.startswith("board_isolator") or part.name.startswith("flight_control")
                        or part.name.startswith("flight_6ch") or part.name.startswith("fc_")):
                    sub.add(part.shape, name=part.name, color=part.color)
        sub.save(str(STEP_DIR / filename), exportType="STEP", tolerance=0.01, angularTolerance=0.1)

    # Full assembly and one STEP per registered part.
    assembly_path = STEP_DIR / "phase15_airframe_full_assembly.step"
    print("exporting full assembly", flush=True)
    assembly.save(str(assembly_path), exportType="STEP", tolerance=0.01, angularTolerance=0.1)
    print("full assembly exported; exporting individual parts", flush=True)
    for part_index, part in enumerate(parts, start=1):
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", part.name).strip("_")
        cq.exporters.export(part.shape, str(STEP_DIR / f"{safe}.step"), exportType="STEP",
                            tolerance=0.01, angularTolerance=0.1)
        if part_index % 10 == 0:
            print(f"exported individual part {part_index}/{len(parts)}", flush=True)

    stock_files = [export_nest("sheet_A_250x120x5_36rotors_63stators", SHEET_A),
                   export_nest("sheet_B_300x120x5_36rotors_63stators", SHEET_B),
                   export_hub_bar_nest()]

    projected, silhouettes = make_projection()
    print("stock nests and frontal projection built", flush=True)
    projected_cm2 = projected.area / 100.0
    write_silhouette_svg(projected, silhouettes)
    mass_rows, mass_summary = mass_properties()
    with (REPORT_DIR / "mass_cg.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(mass_rows[0].keys()))
        writer.writeheader()
        writer.writerows(mass_rows)
    with (REPORT_DIR / "mass_cg_summary.json").open("w", encoding="utf-8") as f:
        json.dump(mass_summary, f, indent=2)
        f.write("\n")
    write_parameter_register()

    # Round-trip every generated STEP, including full/subassembly and stock files.
    roundtrip: list[dict[str, object]] = []
    step_files = sorted(STEP_DIR.glob("*.step")) + sorted(NEST_DIR.glob("*.step"))
    for path in step_files:
        try:
            imported = cq.importers.importStep(str(path)).val()
            solids = imported.Solids()
            volumes = [s.Volume() for s in solids]
            valid = imported.isValid() and bool(solids) and all(v > 0.0 for v in volumes)
            roundtrip.append({"file": str(path.relative_to(OUT)), "status": "PASS" if valid else "FAIL",
                              "solidCount": len(solids), "totalVolumeMm3": sum(volumes),
                              "valid": bool(imported.isValid())})
        except Exception as exc:  # retain individual failure evidence
            roundtrip.append({"file": str(path.relative_to(OUT)), "status": "FAIL",
                              "solidCount": 0, "totalVolumeMm3": 0.0,
                              "valid": False, "error": str(exc)})
        if len(roundtrip) % 10 == 0:
            print(f"STEP round trips {len(roundtrip)}/{len(step_files)}", flush=True)
    with (REPORT_DIR / "step_reimport_validation.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sorted({key for row in roundtrip for key in row.keys()}))
        writer.writeheader()
        writer.writerows(roundtrip)

    exceptions = {
        "nominalSpecConflicts": [
            "Ø80 duct OD + Ø78 bore gives only 1 mm radial wall; CAD uses Ø82 OD (within band) to honor the 2 mm radial composite wall.",
            "78 mm nominal fuselage height cannot enclose an 80+ mm duct pair; CAD uses 88 mm height within the specified 72–90 mm range.",
            "The specified 200 mm axial battery bay needs body section at Z=-300..-100; body length is set to the 640 mm upper band limit.",
            "42 mm motor cans at rotor stations 36 mm apart overlap by 36 mm axially; all six sourced motor envelopes are retained and the conflict is visible.",
            "4 vanes + 2 elevons + 1 rudder require seven servo channels; all seven mechanical mounts are present, while flight-board PWM allocation remains F-05 open.",
        ],
        "checks": {
            "ductCount": 2, "coaxial": False, "rotorBlanks": 72, "statorBlanks": 126,
            "hubs": 6, "servoPositions": 7, "bayReservedMm": list(BATTERY_BAY),
            "batteryPairFitsReservedCrossSection": (2 * BATTERY_PACK[0] <= BATTERY_BAY[1]
                                                    and BATTERY_PACK[1] <= BATTERY_BAY[2]
                                                    and BATTERY_PACK[2] <= BATTERY_BAY[0]),
            "actualRotorTipClearanceMm": DUCT_ID / 2 - ROTOR_TIP_R,
            "rotorSpanMm": ROTOR_SPAN,
            "frontalSolidAreaCm2": projected_cm2,
            "frontalTargetBandPass": 242.0 <= projected_cm2 <= 296.0,
            "hardwarePlusPayloadKg": mass_summary["hardwarePlusPayloadKg"],
            "allUpWithReserveKg": mass_summary["allUpWith15PercentReserveKg"],
            "massTargetPass": mass_summary["allUpWith15PercentReserveKg"] <= 8.5,
            "cgXmm": mass_summary["cgXmm"], "cgYmm": mass_summary["cgYmm"],
            "cgZmm": mass_summary["cgZmm"],
            "cgXTargetPass": abs(mass_summary["cgXmm"]) <= 3.0,
            "cgYTargetPass": -5.0 <= mass_summary["cgYmm"] <= 10.0,
            "cgZTargetPass": -5.0 <= mass_summary["cgZmm"] <= 15.0,
            "reimportPassCount": sum(r["status"] == "PASS" for r in roundtrip),
            "reimportFileCount": len(roundtrip),
            "stockNests": [str(p.relative_to(OUT)) for p in stock_files],
            "sheetBUsesFullMachineXTravel": SHEET_B[0] == 300.0,
        },
        "motorEnvelopeOverlap": {
            "canLengthMm": MOTOR_CAN_LENGTH, "rotorPitchMm": 36.0,
            "overlapMm": MOTOR_CAN_LENGTH - 36.0,
            "pairsPerDuct": 2,
        },
    }
    (REPORT_DIR / "phase15_geometry_audit.json").write_text(json.dumps(exceptions, indent=2) + "\n", encoding="utf-8")
    write_manufacturing_report(stock_files, projected_cm2, mass_summary, roundtrip)

    summary = {
        "parts": len(parts), "individualPartSteps": len(parts),
        "assemblyStep": str(assembly_path.relative_to(OUT)),
        "stockNests": len(stock_files), "stepFilesRoundtripPassed": exceptions["checks"]["reimportPassCount"],
        "stepFilesTotal": len(roundtrip), "frontalAreaCm2": projected_cm2,
        "estimatedAllUpKgWithReserve": mass_summary["allUpWith15PercentReserveKg"],
        "estimatedCgZmm": mass_summary["cgZmm"],
        "knownMotorCanOverlapMm": MOTOR_CAN_LENGTH - 36.0,
        "output": str(OUT.relative_to(ROOT)),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    build()
