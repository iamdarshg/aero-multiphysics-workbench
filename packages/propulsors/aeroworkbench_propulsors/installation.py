"""Generic installation coupling to external-airframe flow.

A propulsor installed on a vehicle sees non-uniform, distorted, yawed inflow
and sheds a propwash/slipstream that interacts with the airframe. This module
exposes generic seams for upstream distortion, wing/fuselage/nacelle
interference, pusher wake ingestion, the downstream slipstream field, and the
transfer of thrust/torque/moment to vehicle dynamics or structures. No
airframe concept is required to use it.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, pi, sin, sqrt
from typing import Any

from aeroworkbench_core.types import Provenance

from .aero import Inflow, RotorAeroResult, RotorSpec
from .provenance import analytical_provenance
from .validity import PropulsorError, finite, nonempty


@dataclass(frozen=True, slots=True)
class Installation:
    """Airframe-side inflow distortion and interference description."""

    installation_id: str
    yaw_deg: float = 0.0
    inflow_distortion_deg: float = 0.0
    interference_velocity_m_s: float = 0.0
    pusher_ingestion_factor: float = 0.0
    upstream_wake_velocity_m_s: float = 0.0
    nacelle_radius_m: float | None = None
    wing_clearance_m: float | None = None

    def __post_init__(self) -> None:
        nonempty(self.installation_id, "installation.installation_id")
        finite(self.yaw_deg, "installation.yaw_deg", minimum=-89.0, maximum=89.0)
        finite(
            self.inflow_distortion_deg,
            "installation.inflow_distortion_deg",
            minimum=0.0,
            maximum=89.0,
        )
        finite(self.interference_velocity_m_s, "installation.interference_velocity_m_s")
        finite(
            self.pusher_ingestion_factor,
            "installation.pusher_ingestion_factor",
            minimum=0.0,
            maximum=1.0,
        )
        finite(
            self.upstream_wake_velocity_m_s,
            "installation.upstream_wake_velocity_m_s",
            minimum=0.0,
        )
        if self.nacelle_radius_m is not None:
            finite(self.nacelle_radius_m, "installation.nacelle_radius_m", positive=True)
        if self.wing_clearance_m is not None:
            finite(self.wing_clearance_m, "installation.wing_clearance_m", minimum=0.0)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "installationId": self.installation_id,
            "yawDeg": self.yaw_deg,
            "inflowDistortionDeg": self.inflow_distortion_deg,
            "interferenceVelocityMS": self.interference_velocity_m_s,
            "pusherIngestionFactor": self.pusher_ingestion_factor,
            "upstreamWakeVelocityMS": self.upstream_wake_velocity_m_s,
            "nacelleRadiusM": self.nacelle_radius_m,
            "wingClearanceM": self.wing_clearance_m,
        }


@dataclass(frozen=True, slots=True)
class InstalledInflow:
    """Effective inflow at the disk after installation effects."""

    axial_velocity_m_s: float
    swirl_velocity_m_s: float
    total_inflow_angle_deg: float
    distortion_factor: float
    ingested_wake_m_s: float
    density_kg_m3: float
    speed_of_sound_m_s: float

    def to_inflow(self) -> Inflow:
        return Inflow(
            axial_velocity_m_s=self.axial_velocity_m_s,
            density_kg_m3=self.density_kg_m3,
            speed_of_sound_m_s=self.speed_of_sound_m_s,
            swirl_velocity_m_s=self.swirl_velocity_m_s,
            yaw_deg=self.total_inflow_angle_deg,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "axialVelocityMS": self.axial_velocity_m_s,
            "swirlVelocityMS": self.swirl_velocity_m_s,
            "totalInflowAngleDeg": self.total_inflow_angle_deg,
            "distortionFactor": self.distortion_factor,
            "ingestedWakeMS": self.ingested_wake_m_s,
        }


@dataclass(frozen=True, slots=True)
class SlipstreamField:
    """Downstream propwash field for wing/fuselage interaction."""

    axial_velocity_m_s: float
    jet_velocity_m_s: float
    contraction_ratio: float
    swirl_velocity_m_s: float
    stations_m: tuple[float, ...]
    velocities_m_s: tuple[float, ...]
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "axial_velocity_m_s": "m/s",
            "jet_velocity_m_s": "m/s",
            "contraction_ratio": "dimensionless",
            "swirl_velocity_m_s": "m/s",
            "stations_m": "m",
            "velocities_m_s": "m/s",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "axialVelocityMS": self.axial_velocity_m_s,
            "jetVelocityMS": self.jet_velocity_m_s,
            "contractionRatio": self.contraction_ratio,
            "swirlVelocityMS": self.swirl_velocity_m_s,
            "stationsM": list(self.stations_m),
            "velocitiesMS": list(self.velocities_m_s),
        }


@dataclass(frozen=True, slots=True)
class VehicleLoads:
    """Installed loads transferred to vehicle dynamics/structures."""

    thrust_n: float
    normal_force_n: float
    torque_n_m: float
    pitching_moment_n_m: float
    yawing_moment_n_m: float
    total_inflow_angle_deg: float
    provenance: Provenance

    def units(self) -> dict[str, str]:
        return {
            "thrust_n": "N",
            "normal_force_n": "N",
            "torque_n_m": "N*m",
            "pitching_moment_n_m": "N*m",
            "yawing_moment_n_m": "N*m",
            "total_inflow_angle_deg": "deg",
        }

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "thrustN": self.thrust_n,
            "normalForceN": self.normal_force_n,
            "torqueNM": self.torque_n_m,
            "pitchingMomentNM": self.pitching_moment_n_m,
            "yawingMomentNM": self.yawing_moment_n_m,
            "totalInflowAngleDeg": self.total_inflow_angle_deg,
        }


def effective_inflow(installation: Installation, free_stream: Inflow) -> InstalledInflow:
    """Combine freestream, distortion, interference, and pusher ingestion."""

    ingested = installation.pusher_ingestion_factor * installation.upstream_wake_velocity_m_s
    axial = (
        free_stream.axial_velocity_m_s
        + installation.interference_velocity_m_s
        + ingested
    )
    total_angle = installation.yaw_deg + installation.inflow_distortion_deg
    distortion_factor = cos(installation.inflow_distortion_deg * pi / 180.0) * cos(
        installation.yaw_deg * pi / 180.0
    )
    axial *= distortion_factor
    swirl = free_stream.swirl_velocity_m_s + axial * sin(total_angle * pi / 180.0)
    return InstalledInflow(
        axial_velocity_m_s=axial,
        swirl_velocity_m_s=swirl,
        total_inflow_angle_deg=total_angle,
        distortion_factor=distortion_factor,
        ingested_wake_m_s=ingested,
        density_kg_m3=free_stream.density_kg_m3,
        speed_of_sound_m_s=free_stream.speed_of_sound_m_s,
    )


def slipstream_field(
    result: RotorAeroResult,
    installation: Installation,
    *,
    rotor: RotorSpec | None = None,
    axial_stations_m: tuple[float, ...] = (0.25, 0.5, 1.0),
) -> SlipstreamField:
    """Downstream propwash axial velocity, contraction, and swirl."""

    if not axial_stations_m:
        raise PropulsorError("slipstream_field needs at least one station")
    for station in axial_stations_m:
        finite(station, "slipstream.station", minimum=0.0)
    freestream = max(result.axial_velocity_m_s, 0.0)
    jet = freestream + 2.0 * result.induced_velocity_m_s
    contraction = sqrt(freestream / jet) if jet > 1e-9 and freestream > 0.0 else 0.0
    if rotor is not None and result.station_loads:
        omega = 2.0 * pi * rotor.revolutions_per_second
        swirl = max(
            abs(load.swirl_induction * omega * load.radius_m) for load in result.station_loads
        )
    else:
        swirl = 0.0
    velocities = tuple(
        freestream + (jet - freestream) * (1.0 - 1.0 / (1.0 + station / 1.0))
        for station in axial_stations_m
    )
    provenance = analytical_provenance(
        "propulsors.installation.slipstream",
        {
            "installation": installation.canonical_payload(),
            "result": result.canonical_payload(),
            "stationsM": list(axial_stations_m),
        },
        assumptions=("Actuator-disk slipstream with linear development and swirl recovery.",),
    )
    return SlipstreamField(
        axial_velocity_m_s=freestream,
        jet_velocity_m_s=jet,
        contraction_ratio=contraction,
        swirl_velocity_m_s=swirl,
        stations_m=tuple(axial_stations_m),
        velocities_m_s=velocities,
        provenance=provenance,
    )


def installed_loads(
    result: RotorAeroResult,
    installation: Installation,
    *,
    thrust_arm_m: float = 0.0,
) -> VehicleLoads:
    """Transfer installed thrust/torque/moment to the vehicle frame."""

    finite(thrust_arm_m, "installed_loads.thrust_arm_m", minimum=0.0)
    total_angle = installation.yaw_deg + installation.inflow_distortion_deg
    distortion = cos(installation.inflow_distortion_deg * pi / 180.0) * cos(
        installation.yaw_deg * pi / 180.0
    )
    thrust = result.thrust_n * distortion
    normal = result.thrust_n * sin(total_angle * pi / 180.0)
    pitching = normal * thrust_arm_m
    yawing = thrust * sin(total_angle * pi / 180.0) * thrust_arm_m
    checks = {
        "thrust_nonnegative": thrust >= 0.0,
        "finite_loads": all(
            isfinite(value) for value in (thrust, normal, pitching, yawing, result.torque_n_m)
        ),
    }
    if not all(checks.values()):
        raise PropulsorError("installed load transfer produced a nonphysical value")
    provenance = analytical_provenance(
        "propulsors.installation.loads",
        {
            "installation": installation.canonical_payload(),
            "result": result.canonical_payload(),
            "thrustArmM": thrust_arm_m,
        },
        assumptions=("Rigid disk normal force from inflow angularity; loads in vehicle axes.",),
    )
    return VehicleLoads(
        thrust_n=thrust,
        normal_force_n=normal,
        torque_n_m=result.torque_n_m,
        pitching_moment_n_m=pitching,
        yawing_moment_n_m=yawing,
        total_inflow_angle_deg=total_angle,
        provenance=provenance,
    )


__all__ = [
    "Installation",
    "InstalledInflow",
    "SlipstreamField",
    "VehicleLoads",
    "effective_inflow",
    "installed_loads",
    "slipstream_field",
]
