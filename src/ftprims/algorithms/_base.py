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
    and_count: int = 0
    clifford_count: int = 0
    rotation_count: int = 0
    rotation_synthesis_epsilon: float | None = None
    breakdown: tuple[BreakdownItem, ...] = ()

    @classmethod
    def from_toffoli_count(
        cls,
        toffoli_count: float,
        *,
        logical_qubits: int,
        raw_t: int = 0,
    ) -> "LogicalCosts":
        """Build a ``LogicalCosts`` from a Toffoli/And count and a qubit count.

        For large factoring workloads the logical-qubit count comes from the
        paper's analytic formula (e.g. GE19 ``3n``), NOT from a traced
        ``QubitCount`` (which is O(gates) and hangs at n≥128). This constructor
        assembles the frozen record directly so the physical layer can be fed a
        paper's closed-form count.

        Parameters
        ----------
        toffoli_count:
            Number of Toffoli/And gates. Counted as ``and_count`` so the shared
            ``raw_t + 4*and`` T-equivalent convention applies (1 Toffoli = 4 T).
        logical_qubits:
            Logical-qubit count, from the paper's analytic formula.
        raw_t:
            Any additional raw T-gates (default 0; factoring is Toffoli-dominated).
        """
        and_count = int(toffoli_count)
        t_direct = raw_t + 4 * and_count
        return cls(
            logical_qubits_estimate=int(logical_qubits),
            t_count_direct=t_direct,
            t_count_ftqc=t_direct,  # no arbitrary rotations in modular exponentiation
            raw_t=raw_t,
            and_count=and_count,
            rotation_count=0,
        )


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
    factory_l1_d: int | None = None
    factory_l2_d: int | None = None
    n_factories: int = 1


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
