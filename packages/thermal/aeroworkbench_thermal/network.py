"""Deterministic steady thermal RC network with energy-balance receipt."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThermalResult:
    temperatures_c: tuple[tuple[str, float], ...]
    energy_residual_w: float
    converged: bool
    iterations: int


class ThermalNetwork:
    def __init__(self, *, ambient_c: float = 25.0, tolerance_w: float = 1e-6) -> None:
        if tolerance_w <= 0:
            raise ValueError("INVALID_THERMAL_TOLERANCE")
        self.ambient_c = ambient_c
        self.tolerance_w = tolerance_w
        self._conductances: dict[tuple[str, str], float] = {}
        self._loads: dict[str, float] = {}

    def connect(self, first: str, second: str, resistance_k_w: float) -> None:
        if not first or not second or first == second or resistance_k_w <= 0:
            raise ValueError("INVALID_THERMAL_EDGE")
        self._conductances[(first, second)] = 1.0 / resistance_k_w
        self._conductances[(second, first)] = 1.0 / resistance_k_w

    def add_load(self, node: str, watts: float) -> None:
        if not node or watts < 0:
            raise ValueError("INVALID_THERMAL_LOAD")
        self._loads[node] = self._loads.get(node, 0.0) + watts

    def solve(self, *, max_iterations: int = 200) -> ThermalResult:
        nodes = sorted(set(self._loads) | {node for edge in self._conductances for node in edge})
        if not nodes:
            raise ValueError("THERMAL_NETWORK_EMPTY")
        temperatures = {node: self.ambient_c for node in nodes}
        iteration = 0
        for step in range(1, max_iterations + 1):
            iteration = step
            previous = dict(temperatures)
            for node in nodes:
                if node == "ambient":
                    continue
                neighbors = [
                    (other, conductance)
                    for (source, other), conductance in self._conductances.items()
                    if source == node
                ]
                conductance_sum = sum(conductance for _, conductance in neighbors)
                if conductance_sum:
                    flow = sum(
                        conductance * previous[other] for other, conductance in neighbors
                    )
                    temperatures[node] = (self._loads.get(node, 0.0) + flow) / conductance_sum
            if max(abs(temperatures[node] - previous[node]) for node in nodes) <= self.tolerance_w:
                break
        residual = sum(self._loads.get(node, 0.0) for node in nodes) - sum(
            conductance * (temperatures[source] - temperatures[target])
            for (source, target), conductance in self._conductances.items()
            if target == "ambient"
        )
        # Networks without an explicit ambient edge are still useful for a
        # relative result, but cannot claim global heat rejection.
        ambient_edges = any(target == "ambient" for _, target in self._conductances)
        if not ambient_edges:
            residual = float("inf")
        converged = residual == residual and abs(residual) <= self.tolerance_w
        return ThermalResult(
            tuple(sorted(temperatures.items())), abs(residual), converged, iteration
        )
