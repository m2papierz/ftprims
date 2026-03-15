"""Resource estimation — logical & physical layers.

Logical costs are extracted from Qualtran's ``QECGatesCost``.
Physical costs use the Gidney-Fowler surface-code model: we search
for the minimum code distance that keeps the total error below the
budget.
"""

from __future__ import annotations

from qualtran import Bloq
from qualtran.resource_counting import (
    GateCounts,
    QECGatesCost,
    QubitCount,
    get_cost_value,
)
from qualtran.surface_code import AlgorithmSummary, PhysicalCostModel

from ftprims.algorithms._base import LogicalCosts, PhysicalCosts


def extract_logical_costs(bloq: Bloq) -> LogicalCosts:
    """Pull qubit count and gate costs from a Qualtran Bloq."""
    qubits = get_cost_value(bloq, QubitCount())
    gates = get_cost_value(bloq, QECGatesCost())

    t_ccz = gates.total_t_and_ccz_count()
    t_equiv = t_ccz["n_t"] + 4 * t_ccz["n_ccz"]

    return LogicalCosts(
        qubits=int(qubits),
        t_count=int(t_equiv),
        clifford_count=int(gates.clifford),
        rotation_count=int(gates.rotation),
    )


def estimate_physical(
    logical: LogicalCosts,
    *,
    error_budget: float = 1e-3,
    cycle_time_us: float = 1.0,
) -> PhysicalCosts:
    """Estimate physical costs using the Gidney-Fowler surface-code model.

    Searches odd code distances from 3 upward until the total error
    drops below *error_budget*.

    Parameters
    ----------
    logical:
        Logical-level resource counts (from ``extract_logical_costs``).
    error_budget:
        Maximum tolerable total error probability.
    cycle_time_us:
        Duration of one surface-code cycle in microseconds.
    """
    algo = AlgorithmSummary(
        n_algo_qubits=logical.qubits,
        n_logical_gates=GateCounts(t=logical.t_count, rotation=logical.rotation_count),
    )

    for d in range(3, 100, 2):
        model = PhysicalCostModel.make_gidney_fowler(data_d=d)
        err = model.error(algo)
        if err <= error_budget:
            return PhysicalCosts(
                physical_qubits=model.n_phys_qubits(algo),
                wall_time_us=model.duration_hr(algo) * 3_600_000_000,
                code_distance=d,
                error_budget=error_budget,
            )

    # Fallback: return at d=99 if budget is extremely tight.
    model = PhysicalCostModel.make_gidney_fowler(data_d=99)
    return PhysicalCosts(
        physical_qubits=model.n_phys_qubits(algo),
        wall_time_us=model.duration_hr(algo) * 3_600_000_000,
        code_distance=99,
        error_budget=error_budget,
    )
