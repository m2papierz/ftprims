"""Resource estimation — logical costs extracted from Qualtran bloqs.

T-count is reported as *T-equivalents*: raw T gates plus 4× the number
of And/CCZ operations (each CCZ decomposes into 4 T gates in the
surface-code model).
"""

from __future__ import annotations

from qualtran import Bloq
from qualtran.resource_counting import QECGatesCost, QubitCount, get_cost_value

from ftprims.algorithms._base import LogicalCosts


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
