"""Benchmark protocol - thin contract every primitive implements."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

import attrs
from qualtran import Bloq


@attrs.define(frozen=True)
class BreakdownItem:
    """One component in a structural cost breakdown."""

    component: str
    invocations: int
    direct_t: int = 0
    clifford_count: int = 0
    rotation_count: int = 0
    est_t_ftqc: int = 0


@attrs.define(frozen=True)
class LogicalCosts:
    """Logical-level resource counts."""

    logical_qubits_estimate: int
    t_count_direct: int
    t_count_ftqc: int
    raw_t: int = 0
    ccz_count: int = 0
    clifford_count: int = 0
    rotation_count: int = 0
    rotation_synthesis_epsilon: float | None = None
    breakdown: tuple[BreakdownItem, ...] = ()


@attrs.define(frozen=True)
class PhysicalCosts:
    """Surface-code physical resource estimates."""

    physical_qubits: int
    wall_time_us: float
    code_distance: int
    error_budget: float
    failure_prob: float
    budget_satisfied: bool
    profile: str = "gidney_fowler"
    data_block: str = "simple"
    factory: str = "ccz2t"


@attrs.define(frozen=True)
class VerificationResult:
    """Outcome of a small-scale Cirq simulation check."""

    status: Literal["pass", "fail", "skip"]
    detail: str = ""


@runtime_checkable
class Benchmark(Protocol):
    """Every ftprims primitive exposes this interface."""

    name: str

    def build_bloq(self, **params: Any) -> Bloq: ...

    def logical_costs(
        self,
        bloq: Bloq,
        *,
        rotation_synthesis_epsilon: float | None = None,
    ) -> LogicalCosts: ...

    def verify_small(self, **params: Any) -> VerificationResult: ...


# Simple name => instance registry filled by each module on import
registry: dict[str, Benchmark] = {}


def register(cls: type[Benchmark]) -> type[Benchmark]:
    """Add given benchmark class to the global registry."""
    registry[cls.name] = cls()
    return cls
