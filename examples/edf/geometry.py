"""Reference EDF geometry used by lightweight demos and API fixtures."""

from aeroworkbench_geometry import GeometryModel, make_edf_geometry


def build_reference_edf() -> GeometryModel:
    return make_edf_geometry(diameter_mm=70.0, hub_diameter_mm=24.0, blade_count=12.0)


if __name__ == "__main__":
    geometry = build_reference_edf()
    print(geometry.canonical_payload())
