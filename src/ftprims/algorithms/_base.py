"""The ``Benchmark`` protocol, its result records, and the primitive registry."""

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
    """Logical-level resource counts.

    ``magic_state_count`` is the aggregate ``And + Toffoli + CSwap`` count, one
    CCZ each (ASSUMPTIONS.md §3).
    """

    logical_qubits_estimate: int
    t_count_direct: int
    t_count_ftqc: int
    raw_t: int = 0
    magic_state_count: int = 0
    clifford_count: int = 0
    rotation_count: int = 0
    rotation_synthesis_epsilon: float | None = None
    breakdown: tuple[BreakdownItem, ...] = ()

    @classmethod
    def from_magic_state_count(
        cls,
        magic_states: float,
        *,
        logical_qubits: int,
        raw_t: int = 0,
    ) -> "LogicalCosts":
        """Build a ``LogicalCosts`` from a magic-state count and a qubit count.

        Parameters
        ----------
        magic_states:
            Aggregate magic-state count (ASSUMPTIONS.md §3); the shared
            ``raw_t + 4*magic_states`` T-equivalent convention applies.
        logical_qubits:
            Logical-qubit count, from a paper's analytic formula rather than a
            traced ``QubitCount``, which is O(gates) and hangs at n >= 128.
        raw_t:
            Additional raw T-gates; factoring is Toffoli-dominated.
        """
        magic_state_count = int(magic_states)
        t_direct = raw_t + 4 * magic_state_count
        return cls(
            logical_qubits_estimate=int(logical_qubits),
            t_count_direct=t_direct,
            t_count_ftqc=t_direct,  # modular exponentiation has no arbitrary rotations
            raw_t=raw_t,
            magic_state_count=magic_state_count,
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
    """The interface every ftprims primitive exposes."""

    name: str

    def build_bloq(self, **params: Any) -> Bloq: ...

    def logical_costs(
        self,
        bloq: Bloq,
        *,
        rotation_synthesis_epsilon: float | None = None,
    ) -> LogicalCosts: ...

    def verify_small(self, **params: Any) -> VerificationResult: ...


# name -> instance, filled by each algorithm module on import
registry: dict[str, Benchmark] = {}


def register(cls: type[Benchmark]) -> type[Benchmark]:
    """Instantiate *cls* into the registry under its ``name``."""
    registry[cls.name] = cls()
    return cls
