"""Declared reference frames and deterministic frame transforms.

Frames form a strict parent chain (``inertial`` -> ``ecef`` -> ``ned`` ->
``body`` -> ``wind``). Every frame declares the convention that maps a vector in
its parent frame into itself, so a transform is a composition of unit-defining
rotations and never an implicit assumption. Mixed or unknown conventions fail
closed instead of silently reinterpreting an axis.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin

from .units import Quantity, Vec3, from_si, require_dimension

FRAME_KINDS: tuple[str, ...] = ("inertial", "ecef", "ned", "body", "wind")

FRAME_PARENT_KIND: dict[str, str | None] = {
    "inertial": None,
    "ecef": "inertial",
    "ned": "ecef",
    "body": "ned",
    "wind": "body",
}

FRAME_CONVENTIONS: dict[str, tuple[str, ...]] = {
    "inertial": (),
    "ecef": (),
    "ned": ("geodetic",),
    "body": ("euler_321", "quaternion"),
    "wind": ("alpha_beta",),
}

_CONVENTION_PARAMETERS: dict[str, tuple[tuple[str, str], ...]] = {
    "euler_321": (("yaw", "angle"), ("pitch", "angle"), ("roll", "angle")),
    "quaternion": (
        ("qw", "dimensionless"),
        ("qx", "dimensionless"),
        ("qy", "dimensionless"),
        ("qz", "dimensionless"),
    ),
    "alpha_beta": (("alpha", "angle"), ("beta", "angle")),
    "geodetic": (("latitude", "angle"), ("longitude", "angle")),
}

Mat3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
IDENTITY: Mat3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


@dataclass(frozen=True, slots=True)
class Frame:
    """One declared reference frame plus the convention from its parent frame."""

    frame_id: str
    kind: str
    parent: str | None = None
    convention: str | None = None
    parameters: tuple[tuple[str, Quantity], ...] = ()

    def __post_init__(self) -> None:
        if not self.frame_id.strip():
            raise ValueError("FRAME_ID_REQUIRED")
        if self.kind not in FRAME_KINDS:
            raise ValueError(f"UNKNOWN_FRAME_KIND:{self.kind}")
        if self.parent != FRAME_PARENT_KIND[self.kind]:
            raise ValueError(f"FRAME_PARENT_KIND_MISMATCH:{self.frame_id}:{self.parent}")
        allowed = FRAME_CONVENTIONS[self.kind]
        if allowed:
            if self.convention not in allowed:
                raise ValueError(f"FRAME_CONVENTION_REQUIRED:{self.frame_id}")
        elif self.convention is not None:
            raise ValueError(f"FRAME_CONVENTION_NOT_ALLOWED:{self.frame_id}")
        names = [name for name, _ in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError(f"DUPLICATE_FRAME_PARAMETER:{self.frame_id}")
        if self.convention is None:
            if names:
                raise ValueError(f"FRAME_PARAMETERS_NOT_ALLOWED:{self.frame_id}")
            return
        expected = dict(_CONVENTION_PARAMETERS[self.convention])
        if set(names) != set(expected):
            raise ValueError(f"FRAME_PARAMETERS_INCOMPLETE:{self.frame_id}")
        for name, quantity in self.parameters:
            require_dimension(quantity, expected[name], f"{self.frame_id}.{name}")

    def parameter(self, name: str) -> float:
        for key, quantity in self.parameters:
            if key == name:
                return quantity.value_si
        raise ValueError(f"FRAME_PARAMETER_MISSING:{self.frame_id}:{name}")

    def canonical(self) -> dict[str, object]:
        return {
            "id": self.frame_id,
            "kind": self.kind,
            "parent": self.parent,
            "convention": self.convention,
            "parameters": {
                name: quantity.canonical() for name, quantity in sorted(self.parameters)
            },
        }


def matmul(left: Mat3, right: Mat3) -> Mat3:
    return (
        (
            left[0][0] * right[0][0] + left[0][1] * right[1][0] + left[0][2] * right[2][0],
            left[0][0] * right[0][1] + left[0][1] * right[1][1] + left[0][2] * right[2][1],
            left[0][0] * right[0][2] + left[0][1] * right[1][2] + left[0][2] * right[2][2],
        ),
        (
            left[1][0] * right[0][0] + left[1][1] * right[1][0] + left[1][2] * right[2][0],
            left[1][0] * right[0][1] + left[1][1] * right[1][1] + left[1][2] * right[2][1],
            left[1][0] * right[0][2] + left[1][1] * right[1][2] + left[1][2] * right[2][2],
        ),
        (
            left[2][0] * right[0][0] + left[2][1] * right[1][0] + left[2][2] * right[2][0],
            left[2][0] * right[0][1] + left[2][1] * right[1][1] + left[2][2] * right[2][1],
            left[2][0] * right[0][2] + left[2][1] * right[1][2] + left[2][2] * right[2][2],
        ),
    )


def transpose(matrix: Mat3) -> Mat3:
    return (
        (matrix[0][0], matrix[1][0], matrix[2][0]),
        (matrix[0][1], matrix[1][1], matrix[2][1]),
        (matrix[0][2], matrix[1][2], matrix[2][2]),
    )


def matvec(matrix: Mat3, vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        matrix[0][0] * vector[0] + matrix[0][1] * vector[1] + matrix[0][2] * vector[2],
        matrix[1][0] * vector[0] + matrix[1][1] * vector[1] + matrix[1][2] * vector[2],
        matrix[2][0] * vector[0] + matrix[2][1] * vector[1] + matrix[2][2] * vector[2],
    )


def _rx(angle: float) -> Mat3:
    c, s = cos(angle), sin(angle)
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def _ry(angle: float) -> Mat3:
    c, s = cos(angle), sin(angle)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def _rz(angle: float) -> Mat3:
    c, s = cos(angle), sin(angle)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def frame_rotation(frame: Frame) -> Mat3:
    """Return the rotation mapping a parent-frame vector into this frame."""
    if frame.convention is None:
        return IDENTITY
    if frame.convention == "euler_321":
        body_from_ned = matmul(_ry(frame.parameter("pitch")), _rz(frame.parameter("yaw")))
        return matmul(_rx(frame.parameter("roll")), body_from_ned)
    if frame.convention == "quaternion":
        w = frame.parameter("qw")
        x = frame.parameter("qx")
        y = frame.parameter("qy")
        z = frame.parameter("qz")
        return (
            (1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
            (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
            (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)),
        )
    if frame.convention == "alpha_beta":
        alpha = frame.parameter("alpha")
        beta = frame.parameter("beta")
        ca, sa, cb, sb = cos(alpha), sin(alpha), cos(beta), sin(beta)
        return ((ca * cb, sb, sa * cb), (-ca * sb, cb, -sa * sb), (-sa, 0.0, ca))
    if frame.convention == "geodetic":
        latitude = frame.parameter("latitude")
        longitude = frame.parameter("longitude")
        sp, cp = sin(latitude), cos(latitude)
        sl, cl = sin(longitude), cos(longitude)
        return (
            (-sp * cl, -sp * sl, cp),
            (-sl, cl, 0.0),
            (-cp * cl, -cp * sl, -sp),
        )
    raise ValueError(f"UNKNOWN_FRAME_CONVENTION:{frame.convention}")


def frame_index(frames: tuple[Frame, ...]) -> dict[str, Frame]:
    """Validate a frame set and index it by id, failing closed on bad structure."""
    if not frames:
        raise ValueError("FRAMES_REQUIRED")
    index: dict[str, Frame] = {}
    for frame in frames:
        if frame.frame_id in index:
            raise ValueError(f"DUPLICATE_FRAME_ID:{frame.frame_id}")
        index[frame.frame_id] = frame
    for frame in frames:
        if frame.parent is not None and frame.parent not in index:
            raise ValueError(f"FRAME_PARENT_UNKNOWN:{frame.frame_id}:{frame.parent}")
    for frame in frames:
        seen = {frame.frame_id}
        cursor = frame.parent
        while cursor is not None:
            if cursor in seen:
                raise ValueError(f"FRAME_CYCLE:{frame.frame_id}")
            seen.add(cursor)
            parent = index[cursor]
            cursor = parent.parent
    return index


def frame_path(index: dict[str, Frame], from_id: str, to_id: str) -> tuple[Frame, ...]:
    """Return the child-first chain of frames from ``from_id`` up to ``to_id``."""
    if from_id not in index:
        raise ValueError(f"UNKNOWN_FRAME:{from_id}")
    if to_id not in index:
        raise ValueError(f"UNKNOWN_FRAME:{to_id}")
    path: list[Frame] = []
    cursor: str | None = from_id
    while cursor is not None:
        frame = index[cursor]
        path.append(frame)
        if cursor == to_id:
            return tuple(path)
        cursor = frame.parent
    raise ValueError(f"NO_FRAME_PATH:{from_id}:{to_id}")


def rotation_between(frames: tuple[Frame, ...], from_id: str, to_id: str) -> Mat3:
    """Return ``R`` such that ``v_to = R @ v_from`` for a declared frame set."""
    return rotation_between_index(frame_index(frames), from_id, to_id)


def _rotation_to_root(index: dict[str, Frame], frame_id: str) -> Mat3:
    if frame_id not in index:
        raise ValueError(f"UNKNOWN_FRAME:{frame_id}")
    result = IDENTITY
    cursor: str | None = frame_id
    while cursor is not None:
        frame = index[cursor]
        result = matmul(transpose(frame_rotation(frame)), result)
        cursor = frame.parent
    return result


def rotation_between_index(index: dict[str, Frame], from_id: str, to_id: str) -> Mat3:
    return matmul(transpose(_rotation_to_root(index, to_id)), _rotation_to_root(index, from_id))


def rotate_vector(vec: Vec3, frames: tuple[Frame, ...], to_frame: str) -> Vec3:
    """Re-express a vector in another declared frame without changing its dimension."""
    if vec.frame == to_frame:
        return vec
    index = frame_index(frames)
    rotation = rotation_between_index(index, vec.frame, to_frame)
    x, y, z = matvec(rotation, vec.value_si)
    return Vec3(
        x=from_si(x, vec.unit),
        y=from_si(y, vec.unit),
        z=from_si(z, vec.unit),
        unit=vec.unit,
        frame=to_frame,
    )
