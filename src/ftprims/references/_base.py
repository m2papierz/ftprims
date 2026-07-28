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

    ``half_reference_fitted`` is a FITTED coefficient (half GE19's §2.2
    ``20·ne·n²``) and is a regression pin only, not evidence.
    ``coefficient_series`` is the non-circular attribution -- see
    ASSUMPTIONS.md §3.
    """

    n: int
    logical_qubits_formula: float
    toffoli_formula: float
    modexp_and_count: int
    half_reference_fitted: float
    divergence_ratio: float
    coefficient_series: tuple[tuple[int, float], ...] = ()
    ge19_reference_coefficient: float = 20.0

    @property
    def measured_coefficient(self) -> float:
        """Measured ``and_count / (ne·n²)`` at ``ne = 2n``."""
        ne = 2 * self.n
        return self.modexp_and_count / (ne * self.n**2)

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
            ReproductionRow.make(
                "measured coefficient",
                "and_count/(ne·n²)",
                self.measured_coefficient,
                self.ge19_reference_coefficient,
            ),
        )


@attrs.define(frozen=True)
class GE19PhysicalReproduction:
    """GE19 physical rows (1-factory + parallel) plus sensitivity sweeps.

    Both rows come from the same grid search; only ``n_factories`` differs.
    ftprims emits a PER-RUN duration, so ``*_per_run`` targets come from GE19
    Table 3 and ``*_expected`` from Table 2 -- see ASSUMPTIONS.md §3.
    """

    error_budget: float
    one_factory: PhysicalCosts
    parallel: PhysicalCosts
    sweep: tuple[tuple[float, PhysicalCosts, PhysicalCosts], ...]
    factory_sweep: tuple[tuple[int, PhysicalCosts], ...]
    one_factory_target_qubits_M: float
    one_factory_target_runtime_hr_expected: float
    parallel_target_qubits_M: float
    parallel_target_runtime_hr_expected: float
    parallel_target_runtime_hr_per_run: float
    retry_risk: float

    @property
    def one_factory_runtime_hr(self) -> float:
        return self.one_factory.wall_time_us / 3.6e9

    @property
    def parallel_runtime_hr(self) -> float:
        return self.parallel.wall_time_us / 3.6e9

    @property
    def parallel_runtime_hr_expected(self) -> float:
        """Our per-run duration converted to GE19's expected convention."""
        return self.parallel_runtime_hr / (1.0 - self.retry_risk)

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
                "runtime_hr/run [vs T2exp]",
                self.one_factory_runtime_hr,
                self.one_factory_target_runtime_hr_expected,
            ),
            ReproductionRow.make(
                "parallel",
                "physical_qubits_M",
                self.parallel.physical_qubits / 1e6,
                self.parallel_target_qubits_M,
            ),
            ReproductionRow.make(
                "parallel",
                "runtime_hr/run [vs T3]",
                self.parallel_runtime_hr,
                self.parallel_target_runtime_hr_per_run,
            ),
            ReproductionRow.make(
                "parallel",
                "runtime_hr exp [vs T2]",
                self.parallel_runtime_hr_expected,
                self.parallel_target_runtime_hr_expected,
            ),
        )


# ── 2019 => 2025 decomposition (arXiv:2505.15917) ──────────────────────────────


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
    """The 2019→2025 decomposition rows, computed once.

    ``convention`` records which Toffoli normalisation produced them.
    """

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
