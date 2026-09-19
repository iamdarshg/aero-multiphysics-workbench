"""Solver-ready fluid domains around real turbomachinery solids.

A fluid domain is built from the same meridional/section contracts as the
solids and exposes semantic boundary groups (inlet, outlet, hub, shroud,
blade pressure/suction/leading/trailing/tip/root, periodic sectors, and
sliding interfaces) so no solver has to hand-author patch names. Open
boundaries are declared, never invented.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from math import cos, pi, sin

from aeroworkbench_mesh.domains import InterfaceSpec, ZoneSpec
from aeroworkbench_semantics import SemanticAssignment

from .blade_rows import BladeRowGeometry
from .body import GeometryBody, SurfacePatch
from .robustness import (
    GeometryDiagnostic,
    check_manifold,
    check_required_roles,
)
from .sections import linspace

_BLADE_WALL_ROLES: tuple[str, ...] = (
    "blade.pressure",
    "blade.suction",
    "blade.leading_edge",
    "blade.trailing_edge",
    "blade.tip",
    "blade.root",
)


@dataclass(frozen=True, slots=True)
class FluidDomain:
    """One solver-ready fluid domain with semantic zones and boundaries."""

    domain_id: str
    body: GeometryBody
    zones: tuple[ZoneSpec, ...]
    interfaces: tuple[InterfaceSpec, ...] = ()
    periodicity: int = 1
    rotating_zone: str | None = None
    required_roles: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.domain_id.strip():
            raise ValueError("FLUID_DOMAIN_ID_REQUIRED")
        if self.body.domain != "fluid":
            raise ValueError("FLUID_DOMAIN_BODY_MUST_BE_FLUID")
        if self.periodicity < 1:
            raise ValueError("FLUID_DOMAIN_PERIODICITY_MUST_BE_POSITIVE")

    def semantic_assignments(self) -> tuple[SemanticAssignment, ...]:
        return tuple(
            SemanticAssignment(
                surface_id=patch.patch_id,
                semantic_key=f"{self.domain_id}.{patch.role}",
                role=patch.role,
                boundary=patch.kind,
            )
            for patch in self.body.patches
        )

    def patch_kinds(self) -> dict[str, str]:
        return {patch.patch_id: patch.kind for patch in self.body.patches}

    def interface_semantic_keys(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple((item.name, item.semantic_keys) for item in self.interfaces)

    def digest(self) -> str:
        encoded = json.dumps(
            {
                "domainId": self.domain_id,
                "body": self.body.digest(),
                "periodicity": self.periodicity,
                "rotatingZone": self.rotating_zone,
                "zones": [
                    [zone.name, zone.motion, zone.domain, list(zone.components)]
                    for zone in self.zones
                ],
                "interfaces": [
                    [
                        item.name,
                        item.kind,
                        item.zone_a,
                        item.zone_b,
                        item.conformal,
                        list(item.semantic_keys),
                    ]
                    for item in self.interfaces
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate(self) -> tuple[GeometryDiagnostic, ...]:
        findings: list[GeometryDiagnostic] = []
        findings.extend(check_manifold(self.body))
        findings.extend(
            check_required_roles(self.body, required_roles=self.required_roles)
        )
        zone_names = {zone.name for zone in self.zones}
        for interface in self.interfaces:
            if interface.zone_a not in zone_names or interface.zone_b not in zone_names:
                findings.append(
                    GeometryDiagnostic(
                        "FLUID_INTERFACE_ZONE_UNKNOWN",
                        f"{interface.name}:{interface.zone_a}/{interface.zone_b}",
                    )
                )
        return tuple(findings)


def _sec(theta: float) -> tuple[float, float]:
    return (cos(theta), sin(theta))


def build_annular_passage(
    *,
    passage_id: str,
    hub_points: tuple[tuple[float, float], ...],
    shroud_points: tuple[tuple[float, float], ...],
    periodicity: int = 1,
    n_theta: int = 9,
    n_stations: int | None = None,
    n_span: int = 3,
) -> GeometryBody:
    """Build one sector of an annular meridional passage as a fluid body.

    ``hub_points``/``shroud_points`` are ``(z_mm, r_mm)`` meridional contours
    with equal station counts. The sector spans ``2*pi/periodicity``.
    """

    if periodicity < 1:
        raise ValueError("ANNULAR_PASSAGE_PERIODICITY_MUST_BE_POSITIVE")
    if len(hub_points) != len(shroud_points):
        raise ValueError("ANNULAR_PASSAGE_CONTOUR_LENGTH_MISMATCH")
    stations = n_stations if n_stations is not None else len(hub_points)
    if stations < 2 or stations > len(hub_points):
        raise ValueError("ANNULAR_PASSAGE_STATIONS_OUT_OF_RANGE")
    if n_theta < 2 or n_span < 2:
        raise ValueError("ANNULAR_PASSAGE_RESOLUTION_TOO_LOW")
    sector = 2.0 * pi / periodicity

    def sample(index: int) -> tuple[tuple[float, float], ...]:
        return (hub_points[index], shroud_points[index])

    def point(theta: float, station: int, span: int) -> tuple[float, float, float]:
        (zh, rh), (zs, rs) = sample(station)
        fraction = span / (n_span - 1)
        radius = rh + (rs - rh) * fraction
        z = zh + (zs - zh) * fraction
        c, s = _sec(theta)
        return (radius * c, radius * s, z)

    thetas = tuple(sector * index / (n_theta - 1) for index in range(n_theta))

    def grid(
        u_count: int, v_count: int, function: Callable[[int, int], tuple[float, float, float]]
    ) -> tuple[tuple[float, float, float], ...]:
        return tuple(
            function(u_index, v_index)
            for v_index in range(v_count)
            for u_index in range(u_count)
        )

    hub = grid(
        n_theta,
        stations,
        lambda u, v: point(thetas[u], v, 0),
    )
    shroud = grid(
        n_theta,
        stations,
        lambda u, v: point(thetas[u], v, n_span - 1),
    )
    inlet = grid(
        n_theta,
        n_span,
        lambda u, v: point(thetas[u], 0, v),
    )
    outlet = grid(
        n_theta,
        n_span,
        lambda u, v: point(thetas[u], stations - 1, v),
    )
    periodic_low = grid(
        n_span,
        stations,
        lambda u, v: point(thetas[0], v, u),
    )
    periodic_high = grid(
        n_span,
        stations,
        lambda u, v: point(thetas[-1], v, u),
    )
    patches = (
        SurfacePatch(f"{passage_id}.hub", "hub", "wall", n_theta, stations, hub),
        SurfacePatch(f"{passage_id}.shroud", "shroud", "wall", n_theta, stations, shroud),
        SurfacePatch(f"{passage_id}.inlet", "inlet", "inlet", n_theta, n_span, inlet),
        SurfacePatch(f"{passage_id}.outlet", "outlet", "outlet", n_theta, n_span, outlet),
        SurfacePatch(
            f"{passage_id}.periodic_low", "periodic_low", "periodic", n_span, stations,
            periodic_low,
        ),
        SurfacePatch(
            f"{passage_id}.periodic_high", "periodic_high", "periodic", n_span, stations,
            periodic_high,
        ),
    )
    return GeometryBody(body_id=passage_id, domain="fluid", patches=patches)


def build_row_fluid_domain(
    geometry: BladeRowGeometry,
    *,
    domain_id: str | None = None,
    n_theta: int = 9,
    n_stations: int = 3,
    n_span: int = 3,
    required_roles: tuple[str, ...] | None = None,
    ports: tuple[SurfacePatch, ...] = (),
) -> FluidDomain:
    """Wrap a :class:`BladeRowGeometry` sector as a solver-ready fluid domain."""

    identifier = domain_id or f"{geometry.row_id}.fluid"
    z0 = geometry.axial_location_mm - geometry.axial_half_width_mm
    z1 = geometry.axial_location_mm + geometry.axial_half_width_mm
    z_stations = linspace(z0, z1, n_stations)
    hub_points = tuple((z, geometry.hub_radius_mm) for z in z_stations)
    shroud_points = tuple((z, geometry.shroud_radius_mm) for z in z_stations)
    passage = build_annular_passage(
        passage_id=identifier,
        hub_points=hub_points,
        shroud_points=shroud_points,
        periodicity=geometry.blade_count,
        n_theta=n_theta,
        n_stations=n_stations,
        n_span=n_span,
    )
    blade_patches = tuple(
        patch
        for patch in geometry.blade_body(0).patches
        if patch.role in _BLADE_WALL_ROLES
    )
    body = GeometryBody(
        body_id=identifier,
        domain="fluid",
        patches=(*passage.patches, *blade_patches, *ports),
    )
    motion = "rotating" if geometry.frame == "rotating" else "stationary"
    zone = ZoneSpec(
        name=identifier,
        motion=motion,  # type: ignore[arg-type]
        domain="fluid",
        components=(geometry.row_id,),
    )
    required = required_roles if required_roles is not None else (
        "inlet",
        "outlet",
        "hub",
        "shroud",
        "periodic_low",
        "periodic_high",
        *_BLADE_WALL_ROLES,
    )
    required = tuple([*required, *sorted({patch.role for patch in ports})])
    return FluidDomain(
        domain_id=identifier,
        body=body,
        zones=(zone,),
        interfaces=(),
        periodicity=geometry.blade_count,
        rotating_zone=identifier if geometry.frame == "rotating" else None,
        required_roles=required,
    )


def sliding_interface(
    *,
    name: str,
    zone_a: str,
    zone_b: str,
    semantic_keys: tuple[str, ...] = (),
    conformal: bool = False,
) -> InterfaceSpec:
    """Declare a sliding (non-matching) interface between two zones."""

    return InterfaceSpec(
        name=name,
        kind="interface",
        zone_a=zone_a,
        zone_b=zone_b,
        conformal=conformal,
        semantic_keys=semantic_keys,
    )


def port_patch(
    *,
    patch_id: str,
    kind: str,
    radius_mm: float,
    z_mm: float,
    theta_rad: float,
    width_rad: float,
    half_height_mm: float,
    n_theta: int = 3,
) -> SurfacePatch:
    """A declared cooling/bleed port patch on a casing (kind: bleed|cooling)."""

    if kind not in ("bleed", "cooling"):
        raise ValueError(f"UNKNOWN_PORT_KIND:{kind}")
    if radius_mm <= 0.0 or width_rad <= 0.0 or half_height_mm <= 0.0:
        raise ValueError("PORT_DIMENSIONS_MUST_BE_POSITIVE")
    points: list[tuple[float, float, float]] = []
    for axial in (-half_height_mm, half_height_mm):
        for index in range(n_theta):
            theta = theta_rad + width_rad * (index / (n_theta - 1))
            points.append(
                (radius_mm * cos(theta), radius_mm * sin(theta), z_mm + axial)
            )
    return SurfacePatch(
        patch_id=patch_id,
        role=kind,
        kind=kind,
        nu=n_theta,
        nv=2,
        points=tuple(points),
    )


def build_stage_fluid_domain(
    rotor: FluidDomain,
    stator: FluidDomain,
    *,
    stage_id: str,
    conformal: bool = False,
) -> FluidDomain:
    """Compose rotor + stator sectors with a declared sliding interface."""

    if rotor.rotating_zone is None:
        raise ValueError("STAGE_ROTOR_NEEDS_ROTATING_ZONE")
    stator_zone = stator.zones[0].name
    patches = tuple(
        {patch.patch_id: patch for patch in (*rotor.body.patches, *stator.body.patches)}.values()
    )
    interface = sliding_interface(
        name=f"{stage_id}.sliding",
        zone_a=rotor.rotating_zone,
        zone_b=stator_zone,
        semantic_keys=(f"{rotor.domain_id}.outlet", f"{stator.domain_id}.inlet"),
        conformal=conformal,
    )
    required = tuple(sorted({*rotor.required_roles, *stator.required_roles}))
    return FluidDomain(
        domain_id=stage_id,
        body=GeometryBody(body_id=stage_id, domain="fluid", patches=patches),
        zones=(*rotor.zones, *stator.zones),
        interfaces=(interface,),
        periodicity=max(rotor.periodicity, stator.periodicity),
        rotating_zone=rotor.rotating_zone,
        required_roles=required,
    )
