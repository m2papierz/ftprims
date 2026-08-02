"""2019 -> 2025 decomposition (arXiv:2505.15917).

Runs GE19's and G2025's logical counts through the same CCZ2T grid search at a
fixed factory count, separating the physical-qubit improvement the model
captures (fewer logical qubits) from what it cannot (yoked codes, cultivation).
The papers' Toffoli conventions differ and are normalised first
(ASSUMPTIONS.md sec. 3).
"""

from __future__ import annotations

import attrs

from qrepro.algorithms._base import LogicalCosts, PhysicalCosts
from qrepro.physical import estimate_physical_grid_search
from qrepro.references._base import ReproductionRow
from qrepro.references.values import G2025, G2025_QREPRO, GE19

_FACTORY_COUNTS = (1, 16, 28)

#: Toffoli-count normalisations (ASSUMPTIONS.md sec. 3).
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
    """Reproduce the GE19 -> G2025 algorithmic-vs-QEC-stack decomposition."""
    ge19_toffolis, g2025_toffolis = _toffoli_counts(convention)
    ge19_logical = LogicalCosts.from_magic_state_count(
        ge19_toffolis, logical_qubits=GE19["logical_qubits"]
    )
    g2025_logical = LogicalCosts.from_magic_state_count(
        g2025_toffolis, logical_qubits=G2025["logical_qubits"]
    )
    error_budget = G2025_QREPRO["error_budget"]

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


@attrs.define(frozen=True)
class DecompositionRow:
    """GE19 and G2025 through the same grid search at one factory count."""

    n_factories: int
    ge19: PhysicalCosts
    g2025: PhysicalCosts

    @property
    def algorithmic_ratio(self) -> float:
        return self.ge19.physical_qubits / self.g2025.physical_qubits


@attrs.define(frozen=True)
class DecompositionReproduction:
    """The decomposition rows, tagged with the Toffoli normalisation used."""

    error_budget: float
    factory_rows: tuple[DecompositionRow, ...]
    convention: str = "per_run"

    def by_factories(self, n_factories: int) -> DecompositionRow:
        for row in self.factory_rows:
            if row.n_factories == n_factories:
                return row
        raise KeyError(f"no decomposition row for n_factories={n_factories}")

    @property
    def rows(self) -> tuple[ReproductionRow, ...]:
        return tuple(
            ReproductionRow.make(
                f"{row.n_factories} factories",
                "algorithmic_ratio",
                row.algorithmic_ratio,
            )
            for row in self.factory_rows
        )
