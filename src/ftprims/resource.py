"""Resource estimation - logical & physical layers."""

from __future__ import annotations

from qualtran import Bloq
from qualtran.resource_counting import QECGatesCost, QubitCount, get_cost_value

from ftprims.algorithms._base import LogicalCosts, PhysicalCosts


def estimate_physical(
    logical: LogicalCosts,
    *,
    error_budget: float = 1e-3,
    cycle_time_us: float = 1.0,
) -> PhysicalCosts:
    """
    Estimate physical costs using Qualtran's PhysicalCostModel.

    This is a thin wrapper — the heavy lifting is done by
    ``qualtran.surface_code.PhysicalCostModel``.
    """
    ...


def extract_logical_costs(bloq: Bloq) -> LogicalCosts:
    """Pull qubit count and gate costs from a Qualtran Bloq."""
    qubits = get_cost_value(bloq, QubitCount())
    gates = get_cost_value(bloq, QECGatesCost())
    return LogicalCosts(
        qubits=int(qubits),
        t_count=int(gates.total_t_count()),
        clifford_count=int(
            gates.total_clifford_count()
            if hasattr(gates, "total_clifford_count")
            else 0
        ),
        rotation_count=int(
            gates.rotation_count if hasattr(gates, "rotation_count") else 0
        ),
    )
