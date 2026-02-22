"""Benchmark protocol - thin contract every primitive implements."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import attrs
from qualtran import Bloq


@attrs.define(frozen=True)
class LogicalCosts:
    """Logical-level resource counts."""

    qubits: int
    t_count: int
    clifford_count: int = 0
    rotation_count: int = 0


@attrs.define(frozen=True)
class PhysicalCosts:
    """Surface-code physical resource estimates."""

    physical_qubits: int
    wall_time_us: float
    code_distance: int
    error_budget: float = 1e-3


@attrs.define(frozen=True)
class VerificationResult:
    """Outcome of a small-scale Cirq simulation check."""

    passed: bool
    detail: str = ""


@runtime_checkable
class Benchmark(Protocol):
    """Every ftprims primitive exposes this interface."""

    name: str

    def build_bloq(self, **params: Any) -> Bloq: ...

    def logical_costs(self, bloq: Bloq) -> LogicalCosts: ...

    def verify_small(self, **params: Any) -> VerificationResult: ...


# Simple name => instance registry filled by each module on import
registry: dict[str, Benchmark] = {}


def register(cls: type[Benchmark]) -> type[Benchmark]:
    """Add given benchmark class to the global registry."""
    registry[cls.name] = cls()
    return cls
