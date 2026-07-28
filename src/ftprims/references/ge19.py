"""GE19 reproduction (arXiv:1905.09749v3): factor 2048-bit RSA.

Two stages: reconcile GE19's closed form against Qualtran's ``ModExp``
call-graph count (the ~64x divergence), then feed the GE19 *formula* count
through the surface-code layer to reproduce Table 2/3's rows plus sensitivity
sweeps. Inputs and conventions: ASSUMPTIONS.md §2/§3.
"""

from __future__ import annotations

from ftprims.algorithms._base import LogicalCosts
from ftprims.algorithms.factoring import make_shor_modexp, modexp_logical_costs
from ftprims.physical import estimate_physical_grid_search
from ftprims.references._base import (
    GE19LogicalReproduction,
    GE19PhysicalReproduction,
)
from ftprims.references.values import (
    GE19,
    GE19_FTPRIMS,
    MODEXP_COEFFICIENT_SIZES,
    ge19_logical_qubits,
    ge19_toffoli_count,
    modexp_toffoli_reference,
)


def ge19_formula_logical_costs() -> LogicalCosts:
    """LogicalCosts carrying GE19's formula Toffoli count and qubit count."""
    return LogicalCosts.from_toffoli_count(
        GE19["toffoli_count"], logical_qubits=GE19["logical_qubits"]
    )


def modexp_coefficient_series(
    sizes: tuple[int, ...] = MODEXP_COEFFICIENT_SIZES,
) -> tuple[tuple[int, float], ...]:
    """Measured ``n_ccz / (ne·n²)`` for ``ModExp`` at each ``n`` in *sizes*."""
    return tuple(
        (
            n,
            modexp_logical_costs(make_shor_modexp(n), logical_qubits=3 * n).and_count
            / ((2 * n) * n**2),
        )
        for n in sizes
    )


def reproduce_ge19_logical() -> GE19LogicalReproduction:
    """Reconcile GE19's closed form with Qualtran's ModExp call-graph count.

    ``QubitCount`` / ``AlgorithmSummary.from_bloq`` / ``decompose_bloq`` are
    never called on ``ModExp`` -- they walk the wires and hang at n≥128 -- so
    the qubit count comes from GE19's abstract formula.
    """
    n = GE19["n"]
    modexp_logical = modexp_logical_costs(
        make_shor_modexp(n), logical_qubits=GE19["logical_qubits"]
    )
    ne = 2 * n  # Shor original
    return GE19LogicalReproduction(
        n=n,
        logical_qubits_formula=ge19_logical_qubits(n),
        toffoli_formula=ge19_toffoli_count(n),
        modexp_ccz_count=modexp_logical.and_count,
        half_reference_fitted=modexp_toffoli_reference(n, ne) / 2,
        divergence_ratio=modexp_logical.and_count / GE19["toffoli_count"],
        coefficient_series=modexp_coefficient_series(),
    )


def reproduce_ge19_physical() -> GE19PhysicalReproduction:
    """Reproduce GE19's 1-factory and parallel rows plus sensitivity sweeps.

    Both rows use the same grid search; only ``n_factories`` differs.
    """
    logical = ge19_formula_logical_costs()
    eb = GE19_FTPRIMS["error_budget"]
    n_one = GE19_FTPRIMS["one_factory_n_factories"]
    n_par = GE19_FTPRIMS["parallel_n_factories"]

    def _grid(n_factories: int, error_budget: float):
        return estimate_physical_grid_search(
            logical,
            n_factories=n_factories,
            error_budget=error_budget,
            phys_err=GE19["phys_err"],
            cycle_time_us=GE19["cycle_us"],
        )

    one_row = GE19["physical_rows"]["one_factory"]
    parallel_row = GE19["physical_rows"]["parallel"]
    table3 = GE19["physical_rows"]["table3_authoritative"]
    return GE19PhysicalReproduction(
        error_budget=eb,
        one_factory=_grid(n_one, eb),
        parallel=_grid(n_par, eb),
        sweep=tuple(
            (budget, _grid(n_one, budget), _grid(n_par, budget))
            for budget in GE19_FTPRIMS["error_budget_sweep"]
        ),
        factory_sweep=tuple(
            (nf, _grid(nf, eb)) for nf in GE19_FTPRIMS["factory_count_sweep"]
        ),
        one_factory_target_qubits_M=one_row["qubits_M"],
        one_factory_target_runtime_hr_expected=one_row["runtime_days"] * 24,
        parallel_target_qubits_M=parallel_row["qubits_M"],
        parallel_target_runtime_hr_expected=parallel_row["runtime_days"] * 24,
        parallel_target_runtime_hr_per_run=table3["runtime_hr_per_run"],
        retry_risk=table3["retry"],
    )
