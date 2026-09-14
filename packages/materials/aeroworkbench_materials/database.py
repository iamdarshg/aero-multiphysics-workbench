"""Content-addressed material database with real stored properties.

This is not a digest-only placeholder: every registered revision carries its
full typed property set. Digests identify revisions; the database stores them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .laminate import LaminateRevision, laminate_digest
from .properties import MaterialValue, constant, frequency_table, temperature_table
from .revision import MaterialRevision, material_digest

SCREENING_NOTE = (
    "screening values for workflow verification; "
    "verify against a qualified source before certification use"
)


def _aluminium_6061_t6() -> MaterialRevision:
    return MaterialRevision(
        material_id="aluminium-6061-t6",
        revision="screening-r1",
        symmetry="isotropic",
        provenance=f"generic handbook screening set; {SCREENING_NOTE}",
        properties={
            "density": constant(2700.0, "kg/m^3", "handbook:Al-6061-T6"),
            "youngs_modulus": constant(68.9e9, "Pa", "handbook:Al-6061-T6"),
            "poisson_ratio": constant(0.33, "1", "handbook:Al-6061-T6"),
            "shear_modulus": constant(26.0e9, "Pa", "handbook:Al-6061-T6"),
            "yield_strength": constant(276.0e6, "Pa", "handbook:Al-6061-T6"),
            "ultimate_strength": constant(310.0e6, "Pa", "handbook:Al-6061-T6"),
            "conductivity": temperature_table(
                ((293.0, 167.0), (373.0, 178.0), (473.0, 186.0)),
                "W/(m K)",
                "handbook:Al-6061-T6",
            ),
            "heat_capacity": constant(896.0, "J/(kg K)", "handbook:Al-6061-T6"),
            "thermal_expansion": constant(23.6e-6, "1/K", "handbook:Al-6061-T6"),
            "emissivity": constant(0.09, "1", "handbook:polished-Al"),
            "resistivity": constant(3.99e-8, "ohm m", "handbook:Al-6061-T6"),
        },
    )


def _structural_steel() -> MaterialRevision:
    return MaterialRevision(
        material_id="steel-structural",
        revision="screening-r1",
        symmetry="isotropic",
        provenance=f"generic handbook screening set; {SCREENING_NOTE}",
        properties={
            "density": constant(7850.0, "kg/m^3", "handbook:structural-steel"),
            "youngs_modulus": constant(210.0e9, "Pa", "handbook:structural-steel"),
            "poisson_ratio": constant(0.30, "1", "handbook:structural-steel"),
            "shear_modulus": constant(80.8e9, "Pa", "handbook:structural-steel"),
            "yield_strength": constant(355.0e6, "Pa", "handbook:S355"),
            "ultimate_strength": constant(510.0e6, "Pa", "handbook:S355"),
            "conductivity": constant(50.0, "W/(m K)", "handbook:structural-steel"),
            "heat_capacity": constant(470.0, "J/(kg K)", "handbook:structural-steel"),
            "thermal_expansion": constant(12.0e-6, "1/K", "handbook:structural-steel"),
            "resistivity": constant(1.70e-7, "ohm m", "handbook:structural-steel"),
        },
    )


def _copper_etp() -> MaterialRevision:
    return MaterialRevision(
        material_id="copper-etp",
        revision="screening-r1",
        symmetry="isotropic",
        provenance=f"generic handbook screening set; {SCREENING_NOTE}",
        properties={
            "density": constant(8960.0, "kg/m^3", "handbook:Cu-ETP"),
            "youngs_modulus": constant(117.0e9, "Pa", "handbook:Cu-ETP"),
            "poisson_ratio": constant(0.34, "1", "handbook:Cu-ETP"),
            "yield_strength": constant(70.0e6, "Pa", "handbook:Cu-ETP-annealed"),
            "ultimate_strength": constant(220.0e6, "Pa", "handbook:Cu-ETP"),
            "conductivity": constant(391.0, "W/(m K)", "handbook:Cu-ETP"),
            "heat_capacity": constant(385.0, "J/(kg K)", "handbook:Cu-ETP"),
            "thermal_expansion": constant(16.5e-6, "1/K", "handbook:Cu-ETP"),
            "resistivity": temperature_table(
                ((293.0, 1.68e-8), (373.0, 2.14e-8)),
                "ohm m",
                "handbook:Cu-ETP",
                note="linearized from temperature coefficient 3.9e-3 1/K",
            ),
            "temperature_coefficient": constant(
                3.9e-3, "1/K", "handbook:Cu-ETP"
            ),
        },
    )


def _carbon_epoxy_ply() -> MaterialRevision:
    return MaterialRevision(
        material_id="carbon-epoxy-ud-ply",
        revision="screening-r1",
        symmetry="orthotropic",
        provenance=f"generic UD carbon/epoxy screening set; {SCREENING_NOTE}",
        properties={
            "density": constant(1600.0, "kg/m^3", "handbook:carbon-epoxy-UD"),
            "youngs_modulus": constant(135.0e9, "Pa", "handbook:carbon-epoxy-UD:E1"),
            "youngs_modulus_transverse": constant(
                10.0e9, "Pa", "handbook:carbon-epoxy-UD:E2"
            ),
            "poisson_ratio": constant(0.30, "1", "handbook:carbon-epoxy-UD:nu12"),
            "shear_modulus": constant(5.0e9, "Pa", "handbook:carbon-epoxy-UD:G12"),
            "ultimate_strength": constant(
                1500.0e6, "Pa", "handbook:carbon-epoxy-UD:X-tension"
            ),
            "conductivity": constant(5.0, "W/(m K)", "handbook:carbon-epoxy-UD"),
            "heat_capacity": constant(1000.0, "J/(kg K)", "handbook:carbon-epoxy-UD"),
            "thermal_expansion": constant(-0.5e-6, "1/K", "handbook:carbon-epoxy-UD:alpha1"),
            "resistivity": constant(3.0e-5, "ohm m", "handbook:carbon-epoxy-UD"),
        },
    )


def _ndfeb_n42() -> MaterialRevision:
    return MaterialRevision(
        material_id="ndfeb-n42",
        revision="screening-r1",
        symmetry="isotropic",
        provenance=f"sintered NdFeB screening set; {SCREENING_NOTE}",
        properties={
            "density": constant(7500.0, "kg/m^3", "handbook:NdFeB-N42"),
            "youngs_modulus": constant(150.0e9, "Pa", "handbook:NdFeB"),
            "poisson_ratio": constant(0.24, "1", "handbook:NdFeB"),
            "conductivity": constant(9.0, "W/(m K)", "handbook:NdFeB"),
            "heat_capacity": constant(440.0, "J/(kg K)", "handbook:NdFeB"),
            "thermal_expansion": constant(4.0e-6, "1/K", "handbook:NdFeB"),
            "resistivity": constant(1.5e-6, "ohm m", "handbook:NdFeB"),
            "permeability": constant(1.05, "1", "handbook:NdFeB-N42:mu-rec"),
            "remanence": constant(1.30, "T", "handbook:NdFeB-N42"),
            "coercivity": constant(955.0e3, "A/m", "handbook:NdFeB-N42"),
            "core_loss": frequency_table(
                ((50.0, 0.8), (400.0, 6.5), (1000.0, 18.0)),
                "W/kg",
                "handbook:SiFe-screening",
                note="representative soft-core loss shape, 1 T peak",
            ),
        },
    )


@dataclass
class MaterialDatabase:
    """Small seeded store; revisions are immutable once registered."""

    _materials: dict[str, MaterialRevision]
    _laminates: dict[str, LaminateRevision]

    @classmethod
    def seeded(cls) -> MaterialDatabase:
        materials = {
            builder().material_id: builder()
            for builder in (
                _aluminium_6061_t6,
                _structural_steel,
                _copper_etp,
                _carbon_epoxy_ply,
                _ndfeb_n42,
            )
        }
        return cls(_materials=dict(materials), _laminates={})

    def register_material(self, material: MaterialRevision) -> str:
        digest = material_digest(material)
        existing = self._materials.get(material.material_id)
        if existing is not None and material_digest(existing) != digest:
            raise ValueError(
                f"MATERIAL_REVISION_CONFLICT:{material.identity}:"
                "material ids are immutable; use a new revision label"
            )
        self._materials[material.material_id] = material
        return digest

    def register_laminate(self, laminate: LaminateRevision) -> str:
        digest = laminate_digest(laminate)
        self._laminates[laminate.laminate_id] = laminate
        return digest

    def get_material(self, material_id: str) -> MaterialRevision:
        try:
            return self._materials[material_id]
        except KeyError as exc:
            raise KeyError(f"MATERIAL_NOT_FOUND:{material_id}") from exc

    def get_laminate(self, laminate_id: str) -> LaminateRevision:
        try:
            return self._laminates[laminate_id]
        except KeyError as exc:
            raise KeyError(f"LAMINATE_NOT_FOUND:{laminate_id}") from exc

    def material_digest(self, material_id: str) -> str:
        return material_digest(self.get_material(material_id))

    def inventory(self) -> tuple[str, ...]:
        return tuple(sorted(self._materials))


__all__ = [
    "MaterialDatabase",
    "MaterialValue",
    "constant",
    "temperature_table",
    "frequency_table",
]
