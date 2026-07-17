"""Result containers for the published-estimate reproductions.

Each ``reproduce_*()`` function computes its numbers **once** and returns one of
these frozen records. The three consumers then read the same record: tests
assert the typed fields (and ``.rows``) against the targets in ``values.py``,
the notebooks render ``.rows`` as their comparison tables, and the CLI prints
them. No reproduced number is computed in more than one place.
"""

from __future__ import annotations

import attrs

from ftprims.algorithms._base import PhysicalCosts


@attrs.define(frozen=True)
class ReproductionRow:
    """One line of a reproduction comparison table.

    ``reproduced`` is the ftprims number; ``target`` is the paper value it is
    compared against (``None`` when there is no single paper target, e.g. a
    call-graph divergence ratio). ``deviation`` is the signed relative deviation
    ``(reproduced - target) / target`` when both are present.
    """

    label: str
    metric: str
    reproduced: float
    target: float | None = None
    deviation: float | None = None

    @classmethod
    def make(
        cls,
        label: str,
        metric: str,
        reproduced: float,
        target: float | None = None,
    ) -> "ReproductionRow":
        deviation = None
        if target is not None and target != 0:
            deviation = (reproduced - target) / target
        return cls(
            label=label,
            metric=metric,
            reproduced=reproduced,
            target=target,
            deviation=deviation,
        )


# ── Beverland et al. (arXiv:2211.07629) ───────────────────────────────────────


@attrs.define(frozen=True)
class BeverlandInstance:
    """Reproduced Beverland-model outputs for one application instance.

    Carries the reproduced ``c_min`` / ``t_states`` / ``code_distance`` and the
    paper targets they are asserted against.
    """

    name: str
    c_min: float
    t_states: float
    code_distance: int
    expect_c_min: float
    expect_t_states: float
    expect_code_distance: int

    @property
    def rows(self) -> tuple[ReproductionRow, ...]:
        return (
            ReproductionRow.make(self.name, "c_min", self.c_min, self.expect_c_min),
            ReproductionRow.make(
                self.name, "t_states", self.t_states, self.expect_t_states
            ),
            ReproductionRow.make(
                self.name,
                "code_distance",
                self.code_distance,
                self.expect_code_distance,
            ),
        )


@attrs.define(frozen=True)
class BeverlandReproduction:
    """All three Beverland application instances, computed once."""

    instances: tuple[BeverlandInstance, ...]

    @property
    def rows(self) -> tuple[ReproductionRow, ...]:
        return tuple(row for inst in self.instances for row in inst.rows)


# ── GE19 (arXiv:1905.09749v3) ─────────────────────────────────────────────────


@attrs.define(frozen=True)
class GE19LogicalReproduction:
    """GE19 logical-count reconciliation: closed form vs ModExp call graph.

    ``modexp_and_count`` is the Qualtran 0.7.0 call-graph And/Toffoli count
    (pinned regression literal); ``reference_half`` is ``10·ne·n²`` at ``ne=2n``;
    ``divergence_ratio`` is ``modexp_and_count / toffoli_formula_table1`` — the
    ~64× logical-divergence finding.
    """

    n: int
    logical_qubits_formula: float
    toffoli_formula: float
    modexp_and_count: int
    reference_half: float
    divergence_ratio: float

    @property
    def rows(self) -> tuple[ReproductionRow, ...]:
        return (
            ReproductionRow.make(
                "logical qubits", "formula", self.logical_qubits_formula
            ),
            ReproductionRow.make("Toffoli", "GE19 formula", self.toffoli_formula),
            ReproductionRow.make(
                "Toffoli", "Qualtran ModExp", float(self.modexp_and_count)
            ),
            ReproductionRow.make("ModExp / formula", "ratio", self.divergence_ratio),
        )


@attrs.define(frozen=True)
class GE19PhysicalReproduction:
    """GE19 physical rows (1-factory + parallel) plus the error-budget sweep.

    ``*_target_*`` are the GE19 paper values (Table 2) the reproduced rows are
    compared against in the display tables.
    """

    error_budget: float
    one_factory: PhysicalCosts
    parallel: PhysicalCosts
    sweep: tuple[tuple[float, PhysicalCosts, PhysicalCosts], ...]
    one_factory_target_qubits_M: float
    one_factory_target_runtime_hr: float
    parallel_target_qubits_M: float
    parallel_target_runtime_hr: float

    @property
    def rows(self) -> tuple[ReproductionRow, ...]:
        return (
            ReproductionRow.make(
                "1 factory",
                "physical_qubits_M",
                self.one_factory.physical_qubits / 1e6,
                self.one_factory_target_qubits_M,
            ),
            ReproductionRow.make(
                "1 factory",
                "runtime_hr",
                self.one_factory.wall_time_us / 3.6e9,
                self.one_factory_target_runtime_hr,
            ),
            ReproductionRow.make(
                "parallel",
                "physical_qubits_M",
                self.parallel.physical_qubits / 1e6,
                self.parallel_target_qubits_M,
            ),
            ReproductionRow.make(
                "parallel",
                "runtime_hr",
                self.parallel.wall_time_us / 3.6e9,
                self.parallel_target_runtime_hr,
            ),
        )


# ── 2019 → 2025 decomposition (arXiv:2505.15917) ──────────────────────────────


@attrs.define(frozen=True)
class DecompositionRow:
    """GE19 vs G2025 run through the SAME grid search at one factory count."""

    n_factories: int
    ge19: PhysicalCosts
    g2025: PhysicalCosts

    @property
    def algorithmic_ratio(self) -> float:
        return self.ge19.physical_qubits / self.g2025.physical_qubits


@attrs.define(frozen=True)
class DecompositionReproduction:
    """The 2019→2025 decomposition rows (one per factory count), computed once."""

    error_budget: float
    factory_rows: tuple[DecompositionRow, ...]

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
