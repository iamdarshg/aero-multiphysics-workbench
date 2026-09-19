"""User-owned remote-compute authorization and cost planning/accounting.

Remote work is impossible unless an interactive operator sets
``AERO_ALLOW_REMOTE_COMPUTE=1`` with immutable limits. No AI/MCP/tool payload
can enable remote compute or raise a limit: a request that carries a remote or
cost field is rejected structurally by :func:`reject_remote_escalation`, and
the API/MCP schemas forbid unknown fields independently.

The module is provider-neutral: it prices generic machine classes so a plan can
be produced and admitted before launch, then settled with estimated/actual
attributable cost after termination. It never talks to a cloud provider.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field

from participants.errors import GovernanceErrorCode, NativeErrorCode, ParticipantError

# Provider-neutral reference rates (USD/hour). Values are deliberately small
# and are only used to plan and account; they are not a billing source of truth.
MACHINE_HOURLY_RATES_USD: dict[str, float] = {
    "e2-standard-2": 0.10,
    "e2-standard-4": 0.20,
    "c2-standard-4": 0.24,
    "n1-standard-2": 0.09,
    "n1-standard-4": 0.19,
}

GPU_HOURLY_RATES_USD: dict[str, float] = {
    "nvidia-tesla-t4": 0.35,
    "nvidia-tesla-v100": 2.48,
    "nvidia-l4": 0.71,
}

# Fields that only a user-owned policy may set. Their presence in AI/tool input
# is a privilege-escalation attempt and is rejected rather than forwarded.
_ESCALATION_KEYS = frozenset(
    {
        "remote",
        "remotecompute",
        "allowremote",
        "costceilingusd",
        "costceiling",
        "budgetusd",
        "maxcostusd",
        "maxcost",
        "vcpu",
        "maxvcpu",
        "gpucount",
        "gputype",
        "imagedigest",
        "allowedregions",
        "allowedprojects",
    }
)


def reject_remote_escalation(inputs: Mapping[str, object]) -> None:
    """Fail closed on any AI/tool payload that tries to enable/raise remote cost."""

    offending = sorted(key for key in inputs if key.lower() in _ESCALATION_KEYS)
    if offending:
        raise ParticipantError(
            GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
            f"ai/tool input cannot set remote/cost fields:{','.join(offending)}",
        )


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"INVALID_REMOTE_LIMIT:{name}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"INVALID_REMOTE_LIMIT:{name}")
    return value


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    value = _env_float(env, name, float(default))
    if value != int(value):
        raise ValueError(f"INVALID_REMOTE_LIMIT:{name}")
    return int(value)


def _env_csv(env: Mapping[str, str], name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class RemoteLimits:
    """Immutable ceilings a user-owned policy may raise only by editing env."""

    max_vcpu: float = 2.0
    max_memory_mib: float = 4096.0
    machine_type: str = "e2-standard-2"
    gpu_type: str | None = None
    max_gpu_count: int = 0
    max_concurrency: int = 1
    max_wall_time_s: float = 1800.0
    max_job_cost_usd: float = 0.15
    max_session_cost_usd: float = 0.49
    max_daily_cost_usd: float = 0.49
    max_project_cost_usd: float = 0.49
    allowed_regions: tuple[str, ...] = ("us-central1",)
    allowed_projects: tuple[str, ...] = ()
    allowed_image_digests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.max_vcpu > 0:
            raise ValueError("INVALID_REMOTE_LIMIT:max_vcpu")
        if not self.max_memory_mib > 0:
            raise ValueError("INVALID_REMOTE_LIMIT:max_memory_mib")
        if self.max_gpu_count < 0:
            raise ValueError("INVALID_REMOTE_LIMIT:max_gpu_count")
        if not self.machine_type.strip():
            raise ValueError("INVALID_REMOTE_LIMIT:machine_type")
        if self.max_gpu_count > 0 and not self.gpu_type:
            raise ValueError("INVALID_REMOTE_LIMIT:gpu_type_required")
        if self.max_concurrency < 1:
            raise ValueError("INVALID_REMOTE_LIMIT:max_concurrency")
        if not self.max_wall_time_s > 0:
            raise ValueError("INVALID_REMOTE_LIMIT:max_wall_time_s")
        for label, value in (
            ("max_job_cost_usd", self.max_job_cost_usd),
            ("max_session_cost_usd", self.max_session_cost_usd),
            ("max_daily_cost_usd", self.max_daily_cost_usd),
            ("max_project_cost_usd", self.max_project_cost_usd),
        ):
            if value < 0 or value != value:
                raise ValueError(f"INVALID_REMOTE_LIMIT:{label}")
        if any(not item.strip() for item in self.allowed_regions):
            raise ValueError("INVALID_REMOTE_LIMIT:allowed_regions")
        if any(not item.strip() for item in self.allowed_image_digests):
            raise ValueError("INVALID_REMOTE_LIMIT:allowed_image_digests")


@dataclass(frozen=True, slots=True)
class RemoteResourceRequest:
    """Provider-neutral resource envelope for one remote attempt."""

    vcpu: float
    memory_mib: float
    wall_time_s: float
    machine_type: str
    gpu_type: str | None = None
    gpu_count: int = 0

    def __post_init__(self) -> None:
        if not self.vcpu > 0:
            raise ValueError("INVALID_REMOTE_RESOURCE:vcpu")
        if not self.memory_mib > 0:
            raise ValueError("INVALID_REMOTE_RESOURCE:memory_mib")
        if not self.wall_time_s > 0:
            raise ValueError("INVALID_REMOTE_RESOURCE:wall_time_s")
        if self.gpu_count < 0:
            raise ValueError("INVALID_REMOTE_RESOURCE:gpu_count")
        if self.gpu_count > 0 and not self.gpu_type:
            raise ValueError("INVALID_REMOTE_RESOURCE:gpu_type")
        if not self.machine_type.strip():
            raise ValueError("INVALID_REMOTE_RESOURCE:machine_type")


@dataclass(frozen=True, slots=True)
class RemoteComputePolicy:
    """One immutable user-owned remote authorization snapshot."""

    enabled: bool = False
    limits: RemoteLimits = field(default_factory=RemoteLimits)

    @classmethod
    def disabled(cls) -> RemoteComputePolicy:
        return cls(enabled=False, limits=RemoteLimits())

    @classmethod
    def from_environment(
        cls, env: Mapping[str, str] | None = None
    ) -> RemoteComputePolicy:
        source = os.environ if env is None else env
        enabled = source.get("AERO_ALLOW_REMOTE_COMPUTE", "0").strip() == "1"
        limits = RemoteLimits(
            max_vcpu=_env_float(source, "AERO_REMOTE_MAX_VCPU", 2.0),
            max_memory_mib=_env_float(source, "AERO_REMOTE_MAX_RAM_MIB", 4096.0),
            machine_type=(source.get("AERO_REMOTE_MACHINE_TYPE", "").strip() or "e2-standard-2"),
            gpu_type=(source.get("AERO_REMOTE_GPU_TYPE", "").strip() or None),
            max_gpu_count=_env_int(source, "AERO_REMOTE_MAX_GPU_COUNT", 0),
            max_concurrency=_env_int(source, "AERO_REMOTE_MAX_CONCURRENCY", 1),
            max_wall_time_s=_env_float(source, "AERO_REMOTE_MAX_WALL_S", 1800.0),
            max_job_cost_usd=_env_float(
                source,
                "AERO_REMOTE_MAX_JOB_COST_USD",
                _env_float(source, "AERO_REMOTE_COST_CEILING_USD", 0.15),
            ),
            max_session_cost_usd=_env_float(
                source, "AERO_REMOTE_MAX_SESSION_COST_USD", 0.49
            ),
            max_daily_cost_usd=_env_float(
                source, "AERO_REMOTE_MAX_DAILY_COST_USD", 0.49
            ),
            max_project_cost_usd=_env_float(
                source, "AERO_REMOTE_MAX_PROJECT_COST_USD", 0.49
            ),
            allowed_regions=_env_csv(
                source, "AERO_REMOTE_ALLOWED_REGIONS", ("us-central1",)
            ),
            allowed_projects=_env_csv(source, "AERO_REMOTE_ALLOWED_PROJECTS", ()),
            allowed_image_digests=_env_csv(
                source, "AERO_REMOTE_ALLOWED_IMAGE_DIGESTS", ()
            ),
        )
        return cls(enabled=enabled, limits=limits)

    def require_enabled(self) -> None:
        if not self.enabled:
            # A disabled remote capability fails closed exactly like any other
            # unavailable native capability; it never falls back to local.
            raise ParticipantError(
                NativeErrorCode.CAPABILITY_UNAVAILABLE,
                "remote compute is not authorized by the user-owned policy",
            )

    def assert_within_limits(self, request: RemoteResourceRequest) -> None:
        limits = self.limits
        if request.vcpu > limits.max_vcpu + 1e-9:
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                f"vcpu {request.vcpu:g} exceeds user limit {limits.max_vcpu:g}",
            )
        if request.memory_mib > limits.max_memory_mib + 1e-9:
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                f"memory {request.memory_mib:g} MiB exceeds user limit",
            )
        if request.wall_time_s > limits.max_wall_time_s + 1e-9:
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                f"wall time {request.wall_time_s:g}s exceeds user limit",
            )
        if request.gpu_count > limits.max_gpu_count:
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                "gpu count exceeds user limit",
            )
        if request.gpu_count > 0 and request.gpu_type != limits.gpu_type:
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                f"gpu type {request.gpu_type!r} not in user policy",
            )
        if limits.allowed_regions and request.machine_type not in MACHINE_HOURLY_RATES_USD:
            # Unknown machine classes are still priceable, but an empty rate
            # table entry would make planning dishonest; fail closed.
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                f"unpriced machine type:{request.machine_type}",
            )

    def assert_placement_allowed(self, *, region: str | None, project: str | None) -> None:
        limits = self.limits
        if region is None or region not in limits.allowed_regions:
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                f"region not allowed by user policy:{region}",
            )
        if limits.allowed_projects and (project is None or project not in limits.allowed_projects):
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                f"project not allowed by user policy:{project}",
            )

    def assert_image_allowed(self, image_digest: str | None) -> None:
        limits = self.limits
        if not limits.allowed_image_digests:
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                "user policy pins no allowed worker image digest",
            )
        if image_digest is None or image_digest not in limits.allowed_image_digests:
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                f"image digest not allowed by user policy:{image_digest}",
            )


def _hourly_rate(request: RemoteResourceRequest) -> float:
    rate = MACHINE_HOURLY_RATES_USD.get(request.machine_type)
    if rate is None:
        raise ParticipantError(
            GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
            f"unpriced machine type:{request.machine_type}",
        )
    if request.gpu_count > 0 and request.gpu_type:
        gpu_rate = GPU_HOURLY_RATES_USD.get(request.gpu_type)
        if gpu_rate is None:
            raise ParticipantError(
                GovernanceErrorCode.REMOTE_COMPUTE_NOT_AUTHORIZED,
                f"unpriced gpu type:{request.gpu_type}",
            )
        rate += gpu_rate * request.gpu_count
    return rate


@dataclass(frozen=True, slots=True)
class CostPlan:
    """Planned maximum attributable cost, produced before launch."""

    job_id: str
    request: RemoteResourceRequest
    hourly_rate_usd: float
    planned_max_cost_usd: float

    @classmethod
    def build(cls, job_id: str, request: RemoteResourceRequest) -> CostPlan:
        rate = _hourly_rate(request)
        planned = round(rate * request.wall_time_s / 3600.0, 6)
        return cls(
            job_id=job_id,
            request=request,
            hourly_rate_usd=round(rate, 6),
            planned_max_cost_usd=planned,
        )


@dataclass(frozen=True, slots=True)
class CostReceipt:
    """Post-termination accounting for one attempt; never mutates history."""

    job_id: str
    planned_max_cost_usd: float
    estimated_cost_usd: float
    actual_cost_usd: float | None
    runtime_s: float
    machine_type: str
    released: bool
    preempted: bool = False


@dataclass(slots=True)
class _Reservation:
    plan: CostPlan


class CostLedger:
    """Bounded, thread-safe cost reservation and accounting for remote work.

    A reservation is taken before launch and can only be settled once. A
    preemption settles with the actual attributable cost and does not reset the
    user's cumulative budget, so a resume must reserve fresh headroom.
    """

    def __init__(
        self,
        limits: RemoteLimits,
        *,
        project_spent_usd: float = 0.0,
        daily_spent_usd: float = 0.0,
        session_spent_usd: float = 0.0,
    ) -> None:
        self._limits = limits
        self._lock = threading.Lock()
        self._reservations: dict[str, _Reservation] = {}
        self._project_spent = max(0.0, float(project_spent_usd))
        self._daily_spent = max(0.0, float(daily_spent_usd))
        self._session_spent = max(0.0, float(session_spent_usd))
        self._reserved = 0.0
        self._settled: dict[str, CostReceipt] = {}

    def plan(self, job_id: str, request: RemoteResourceRequest) -> CostPlan:
        return CostPlan.build(job_id, request)

    def reserve(self, plan: CostPlan) -> CostPlan:
        limits = self._limits
        with self._lock:
            if plan.planned_max_cost_usd > limits.max_job_cost_usd + 1e-9:
                raise ParticipantError(
                    GovernanceErrorCode.COST_LIMIT_EXCEEDED,
                    f"planned cost {plan.planned_max_cost_usd} exceeds per-job ceiling",
                )
            if len(self._reservations) >= limits.max_concurrency:
                raise ParticipantError(
                    GovernanceErrorCode.COST_LIMIT_EXCEEDED,
                    "remote concurrency ceiling reached",
                )
            for label, spent, ceiling in (
                ("session", self._session_spent, limits.max_session_cost_usd),
                ("daily", self._daily_spent, limits.max_daily_cost_usd),
                ("project", self._project_spent, limits.max_project_cost_usd),
            ):
                if spent + self._reserved + plan.planned_max_cost_usd > ceiling + 1e-9:
                    raise ParticipantError(
                        GovernanceErrorCode.COST_LIMIT_EXCEEDED,
                        f"{label} cost ceiling would be exceeded by the plan",
                    )
            self._reservations[plan.job_id] = _Reservation(plan)
            self._reserved += plan.planned_max_cost_usd
            return plan

    def settle(
        self,
        job_id: str,
        *,
        actual_cost_usd: float | None,
        runtime_s: float,
        machine_type: str,
        preempted: bool = False,
    ) -> CostReceipt:
        with self._lock:
            reservation = self._reservations.pop(job_id, None)
            if reservation is None:
                raise KeyError(f"COST_RESERVATION_NOT_FOUND:{job_id}")
            self._reserved = max(0.0, self._reserved - reservation.plan.planned_max_cost_usd)
            if actual_cost_usd is None:
                estimated = round(
                    reservation.plan.hourly_rate_usd * max(0.0, runtime_s) / 3600.0, 6
                )
                estimated = min(estimated, reservation.plan.planned_max_cost_usd)
                spent = estimated
                actual: float | None = None
            else:
                actual = max(0.0, float(actual_cost_usd))
                estimated = actual
                spent = actual
            self._session_spent += spent
            self._daily_spent += spent
            self._project_spent += spent
            receipt = CostReceipt(
                job_id=job_id,
                planned_max_cost_usd=reservation.plan.planned_max_cost_usd,
                estimated_cost_usd=estimated,
                actual_cost_usd=actual,
                runtime_s=round(max(0.0, runtime_s), 6),
                machine_type=machine_type,
                released=True,
                preempted=preempted,
            )
            self._settled[job_id] = receipt
            return receipt

    def release(self, job_id: str) -> None:
        """Drop a reservation that never incurred cost (admission/cancel)."""

        with self._lock:
            reservation = self._reservations.pop(job_id, None)
            if reservation is not None:
                self._reserved = max(
                    0.0, self._reserved - reservation.plan.planned_max_cost_usd
                )

    def spend(self, job_id: str) -> CostReceipt | None:
        return self._settled.get(job_id)

    def totals(self) -> dict[str, float]:
        with self._lock:
            return {
                "session_spent_usd": round(self._session_spent, 6),
                "daily_spent_usd": round(self._daily_spent, 6),
                "project_spent_usd": round(self._project_spent, 6),
                "reserved_usd": round(self._reserved, 6),
                "remaining_session_usd": round(
                    max(
                        0.0,
                        self._limits.max_session_cost_usd
                        - self._session_spent
                        - self._reserved,
                    ),
                    6,
                ),
            }

    def remaining_for(self, plan: CostPlan) -> float:
        """Headroom against the tightest user ceiling after this plan."""

        with self._lock:
            ceilings = (
                self._limits.max_session_cost_usd - self._session_spent,
                self._limits.max_daily_cost_usd - self._daily_spent,
                self._limits.max_project_cost_usd - self._project_spent,
                self._limits.max_job_cost_usd,
            )
            return round(max(0.0, min(ceilings) - self._reserved), 6)


def elapsed_seconds(started_at: float, finished_at: float) -> float:
    if finished_at <= 0 or started_at <= 0:
        return 0.0
    return max(0.0, finished_at - started_at)


def monotonic() -> float:
    return time.monotonic()


__all__ = [
    "CostLedger",
    "CostPlan",
    "CostReceipt",
    "GPU_HOURLY_RATES_USD",
    "MACHINE_HOURLY_RATES_USD",
    "RemoteComputePolicy",
    "RemoteLimits",
    "RemoteResourceRequest",
    "elapsed_seconds",
    "reject_remote_escalation",
]
