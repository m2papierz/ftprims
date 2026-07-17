"""GE19 reproduction (arXiv:1905.09749v3): factor 2048-bit RSA.

Two stages, each computed once:

* :func:`reproduce_ge19_logical` reconciles GE19's closed-form Toffoli count
  with Qualtran's ``ModExp`` call-graph count (the ~64× logical-divergence
  finding), extracting the call-graph count with the scale-safe,
  QubitCount-free ``modexp_logical_costs``.
* :func:`reproduce_ge19_physical` feeds the **GE19 formula count** (not the
  ModExp count) through the surface-code physical layer to reproduce GE19's
  1-factory and parallel rows, with an ``error_budget`` sensitivity sweep.
"""

from __future__ import annotations

from ftprims.algorithms._base import LogicalCosts
from ftprims.algorithms.factoring import make_shor_modexp, modexp_logical_costs
from ftprims.physical import (
    PhysicalModelSpec,
    estimate_physical,
    estimate_physical_grid_search,
)
from ftprims.references._base import (
    GE19LogicalReproduction,
    GE19PhysicalReproduction,
)
from ftprims.references.values import (
    GE19,
    GE19_FTPRIMS,
    ge19_logical_qubits,
    ge19_toffoli_count,
    modexp_toffoli_reference,
)


def ge19_formula_logical_costs() -> LogicalCosts:
    """LogicalCosts carrying GE19's *formula* Toffoli count (2.7e9) and 3n qubits."""
    return LogicalCosts.from_toffoli_count(
        GE19["toffoli_count"], logical_qubits=GE19["logical_qubits"]
    )


def reproduce_ge19_logical() -> GE19LogicalReproduction:
    """Reconcile GE19's closed form with Qualtran's ModExp call-graph count.

    The ModExp And-count is obtained with ``QECGatesCost`` via
    ``modexp_logical_costs`` (~0.01 s); ``QubitCount`` / ``AlgorithmSummary.from_bloq``
    / ``decompose_bloq`` are never called on ``ModExp`` (they hang at n≥128), so
    the logical-qubit count comes from GE19's ``3n`` formula.
    """
    n = GE19["n"]
    modexp = make_shor_modexp(n)
    modexp_logical = modexp_logical_costs(modexp, logical_qubits=GE19["logical_qubits"])
    ne = 2 * n  # Shor original: 2n exponent qubits
    reference_half = modexp_toffoli_reference(n, ne) / 2  # 10·ne·n²
    return GE19LogicalReproduction(
        n=n,
        logical_qubits_formula=ge19_logical_qubits(n),
        toffoli_formula=ge19_toffoli_count(n),
        modexp_and_count=modexp_logical.and_count,
        reference_half=reference_half,
        divergence_ratio=modexp_logical.and_count / GE19["toffoli_count"],
    )


def reproduce_ge19_physical() -> GE19PhysicalReproduction:
    """Reproduce GE19's 1-factory and parallel physical rows + sensitivity sweep.

    Fed the GE19 formula Toffoli count (2.7e9), not the ModExp count, at
    ``phys_err=1e-3``, ``cycle_time_us=1.0``, ``n_algo_qubits=6189``. The CCZ2T
    grid search uses ``error_budget=0.5`` as a documented proxy for GE19's ~31%
    per-run retry / skewed-volume optimization; the sweep documents how the rows
    move across ``{0.1, 0.33, 0.5}``.
    """
    logical = ge19_formula_logical_costs()
    eb = GE19_FTPRIMS["error_budget_proxy"]
    n_factories = GE19_FTPRIMS["parallel"]["n_factories"]

    def _one(error_budget: float):
        return estimate_physical(
            logical,
            spec=PhysicalModelSpec(
                error_budget=error_budget,
                physical_error=GE19["phys_err"],
                cycle_time_us=GE19["cycle_us"],
            ),
        )

    def _parallel(error_budget: float):
        return estimate_physical_grid_search(
            logical,
            n_factories=n_factories,
            error_budget=error_budget,
            phys_err=GE19["phys_err"],
            cycle_time_us=GE19["cycle_us"],
        )

    sweep = tuple(
        (budget, _one(budget), _parallel(budget))
        for budget in GE19_FTPRIMS["error_budget_sweep"]
    )
    one_row = GE19["physical_rows"]["one_factory"]
    parallel_row = GE19["physical_rows"]["parallel"]
    return GE19PhysicalReproduction(
        error_budget=eb,
        one_factory=_one(eb),
        parallel=_parallel(eb),
        sweep=sweep,
        one_factory_target_qubits_M=one_row["qubits_M"],
        one_factory_target_runtime_hr=one_row["runtime_days"] * 24,
        parallel_target_qubits_M=parallel_row["qubits_M"],
        parallel_target_runtime_hr=parallel_row["runtime_days"] * 24,
    )
