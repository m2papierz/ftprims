"""2019 → 2025 decomposition (arXiv:2505.15917, "G2025").

Runs GE19's and G2025's logical counts through the *same* 2019-style CCZ2T grid
search, holding the factory count fixed across both papers (apples-to-apples),
and splits the physical-qubit improvement into what the model captures
(algorithmic, via fewer logical qubits) and what it cannot (the QEC stack:
yoked surface codes + magic state cultivation, §3.2, structurally unmodelable
here). Both budgets are ``error_budget=0.5``; the residual gap from the ftprims
G2025 number down to the published < 1M is the finding, not a target.
"""

from __future__ import annotations

from ftprims.algorithms._base import LogicalCosts
from ftprims.physical import estimate_physical_grid_search
from ftprims.references._base import DecompositionReproduction, DecompositionRow
from ftprims.references.ge19 import ge19_formula_logical_costs
from ftprims.references.values import G2025, G2025_FTPRIMS

_FACTORY_COUNTS = (1, 16)


def reproduce_2019_to_2025() -> DecompositionReproduction:
    """Reproduce the GE19→G2025 algorithmic-vs-QEC-stack decomposition.

    For each factory count, both papers' counts run through the same grid
    search at ``error_budget=0.5``; the algorithmic ratio is the reduction the
    model captures purely through G2025's smaller logical footprint.
    """
    ge19_logical = ge19_formula_logical_costs()
    g2025_logical = LogicalCosts.from_toffoli_count(
        G2025["toffoli_count"], logical_qubits=G2025["logical_qubits"]
    )
    error_budget = G2025_FTPRIMS["error_budget"]

    rows = []
    for n_factories in _FACTORY_COUNTS:
        ge19 = estimate_physical_grid_search(
            ge19_logical, n_factories=n_factories, error_budget=error_budget
        )
        g2025 = estimate_physical_grid_search(
            g2025_logical, n_factories=n_factories, error_budget=error_budget
        )
        rows.append(DecompositionRow(n_factories=n_factories, ge19=ge19, g2025=g2025))
    return DecompositionReproduction(
        error_budget=error_budget, factory_rows=tuple(rows)
    )
