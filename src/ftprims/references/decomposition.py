"""2019 → 2025 decomposition (arXiv:2505.15917).

Runs GE19's and G2025's logical counts through the same CCZ2T grid search at a
fixed factory count, splitting the physical-qubit improvement into what the
model captures (fewer logical qubits) and what it cannot (yoked codes,
cultivation). Toffoli conventions differ between the papers and are normalised
first -- see ASSUMPTIONS.md §3.
"""

from __future__ import annotations

from ftprims.algorithms._base import LogicalCosts
from ftprims.physical import estimate_physical_grid_search
from ftprims.references._base import DecompositionReproduction, DecompositionRow
from ftprims.references.values import G2025, G2025_FTPRIMS, GE19

_FACTORY_COUNTS = (1, 16, 28)

#: Toffoli-count normalisations (ASSUMPTIONS.md §3).
CONVENTIONS = ("per_run", "expected")


def _toffoli_counts(convention: str) -> tuple[float, float]:
    """GE19 and G2025 Toffoli counts placed on a common convention."""
    ge19_per_run = GE19["toffoli_count"]
    g2025_expected = G2025["toffoli_count"]
    shots = G2025["expected_shots"]
    retry = GE19["physical_rows"]["table3_authoritative"]["retry"]

    if convention == "per_run":
        return ge19_per_run, g2025_expected / shots
    if convention == "expected":
        return ge19_per_run / (1.0 - retry), g2025_expected
    raise ValueError(f"Unknown convention {convention!r}; choose from {CONVENTIONS}")


def reproduce_2019_to_2025(convention: str = "per_run") -> DecompositionReproduction:
    """Reproduce the GE19→G2025 algorithmic-vs-QEC-stack decomposition."""
    ge19_toffolis, g2025_toffolis = _toffoli_counts(convention)
    ge19_logical = LogicalCosts.from_toffoli_count(
        ge19_toffolis, logical_qubits=GE19["logical_qubits"]
    )
    g2025_logical = LogicalCosts.from_toffoli_count(
        g2025_toffolis, logical_qubits=G2025["logical_qubits"]
    )
    error_budget = G2025_FTPRIMS["error_budget"]

    rows = tuple(
        DecompositionRow(
            n_factories=nf,
            ge19=estimate_physical_grid_search(
                ge19_logical, n_factories=nf, error_budget=error_budget
            ),
            g2025=estimate_physical_grid_search(
                g2025_logical, n_factories=nf, error_budget=error_budget
            ),
        )
        for nf in _FACTORY_COUNTS
    )
    return DecompositionReproduction(
        error_budget=error_budget,
        factory_rows=rows,
        convention=convention,
    )
