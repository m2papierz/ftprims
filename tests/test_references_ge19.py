"""GE19 reproduction (arXiv:1905.09749v3).

Logical-count reconciliation and the physical rows, asserted against targets in
``ftprims.references.values``. Sources, conventions and achieved deviations:
ASSUMPTIONS.md.
"""

from __future__ import annotations

import pytest

from ftprims.references import reproduce_ge19_logical, reproduce_ge19_physical
from ftprims.references.values import (
    GE19,
    GE19_FTPRIMS,
    GE19_FTPRIMS_ACHIEVED,
    GE19_TOL,
)


@pytest.fixture(scope="module")
def logical():
    return reproduce_ge19_logical()


@pytest.fixture(scope="module")
def physical():
    return reproduce_ge19_physical()


# ── Logical counts ────────────────────────────────────────────────────────────


def test_ge19_logical_qubits_formula(logical):
    """3n + 0.002·n·lg n rounds to the abstract's 6189 at n=2048."""
    assert round(logical.logical_qubits_formula) == GE19["logical_qubits"]


def test_ge19_toffoli_formula_matches_table1(logical):
    """The abstract formula evaluates 2.9% below Table 1's rounded 2.7e9."""
    assert logical.toffoli_formula == pytest.approx(GE19["toffoli_count"], rel=0.05)


def test_modexp_call_graph_count_pinned(logical):
    """Regression literal: a dependency bump that moves it must surface.

    ``n_ccz`` = And + Toffoli + CSwap. The and_bloq-only count is pinned
    separately below because CMODMULK_AUDIT.md and main_003.md quote it.
    """
    assert logical.modexp_ccz_count == GE19["modexp_qualtran_toffoli"]


def test_modexp_and_only_count_pinned():
    """The and_bloq-only count, 0.0049% below the n_ccz total (the ne·n CSwaps).

    Pinned so the two currencies cannot silently drift apart — the audit and
    the blog both quote the AND-only figure.
    """
    from qualtran.resource_counting import QECGatesCost, get_cost_value

    from ftprims.algorithms.factoring import make_shor_modexp

    gates = get_cost_value(make_shor_modexp(GE19["n"]), QECGatesCost())
    assert int(gates.and_bloq) == GE19["modexp_qualtran_and_only"]
    assert int(gates.cswap) == 2 * GE19["n"] * GE19["n"]  # ne·n, ne = 2n
    assert (
        GE19["modexp_qualtran_and_only"] + int(gates.cswap)
        == GE19["modexp_qualtran_toffoli"]
    )


def test_modexp_coefficient_converges(logical):
    """n_ccz/(ne·n²) converges to a constant — the reference regime.

    A windowed construction would fall like 1/lg²n across this range; a
    constant identifies the non-windowed regime on the scaling alone.
    """
    coeffs = [c for _, c in sorted(logical.coefficient_series)]
    assert coeffs, "coefficient series must be populated"
    assert all(a >= b for a, b in zip(coeffs, coeffs[1:])), coeffs
    assert coeffs[-1] == pytest.approx(10.0, rel=0.01), coeffs
    assert (coeffs[0] - coeffs[-1]) / coeffs[-1] < 0.02, coeffs


def test_modexp_matches_fitted_half_reference(logical):
    """Regression pin on the fitted 10·ne·n² coefficient.

    In n_ccz currency the exact closed form is 10·ne·n² + 5·ne·n (the +5 is
    +4 from the And-per-controlled-modular-addition terms and +1 from the
    CSwap), so the coefficient is 10 + 5/n = 10.002441 at n=2048.

    Not evidence — the coefficient is fitted. Attribution rests on
    test_modexp_coefficient_converges.
    """
    assert logical.modexp_ccz_count == pytest.approx(
        logical.half_reference_fitted, rel=0.02
    )
    assert logical.measured_coefficient == pytest.approx(
        logical.ge19_reference_coefficient / 2, rel=0.01
    )


def test_modexp_vs_formula_divergence(logical):
    """The ~64x logical divergence, asserted in a band robust to the denominator."""
    assert (
        GE19_TOL["divergence_lo"]
        <= logical.divergence_ratio
        <= GE19_TOL["divergence_hi"]
    )


# ── Physical layer ────────────────────────────────────────────────────────────


def test_ge19_uses_papers_own_inputs(physical):
    """Both free parameters are GE19's published values, not choices."""
    assert physical.error_budget == GE19_FTPRIMS["error_budget"] == 0.31
    assert physical.retry_risk == GE19["physical_rows"]["table3_authoritative"]["retry"]
    assert physical.one_factory.n_factories == 1
    assert physical.parallel.n_factories == 28


def test_ge19_grid_search_finds_papers_own_factory(physical):
    """At GE19's own budget and factory count the search picks GE19's factory.

    Direct refutation of "GE19's factory lies outside the model's family".
    """
    t3 = GE19["physical_rows"]["table3_authoritative"]
    assert physical.parallel.factory_l1_d == t3["d1"] == 15
    assert physical.parallel.factory_l2_d == t3["d2"] == 27


def test_ge19_one_factory_qubits(physical):
    """1-factory qubits vs Table 2's 16 M (+12.3%)."""
    ph = physical.one_factory
    achieved = GE19_FTPRIMS_ACHIEVED["one_factory"]
    assert ph.physical_qubits / 1e6 == pytest.approx(
        GE19["physical_rows"]["one_factory"]["qubits_M"], rel=GE19_TOL["rel_qubits"]
    )
    assert ph.physical_qubits / 1e6 == pytest.approx(achieved["qubits_M"], rel=0.02)
    assert ph.code_distance == achieved["code_distance"]


def test_ge19_one_factory_runtime(physical):
    """1-factory runtime vs Table 2's 6 days (-11.2%).

    Conventions cannot be matched here: GE19 publishes only an *expected*
    runtime for this scenario. See ASSUMPTIONS.md §4.
    """
    assert physical.one_factory_runtime_hr == pytest.approx(
        physical.one_factory_target_runtime_hr_expected, rel=GE19_TOL["rel_runtime"]
    )


def test_ge19_parallel_qubits(physical):
    """28-factory qubits vs Table 2/3's 20 M (-13.7%)."""
    ph = physical.parallel
    assert ph.physical_qubits / 1e6 == pytest.approx(
        GE19["physical_rows"]["parallel"]["qubits_M"], rel=GE19_TOL["rel_qubits"]
    )
    assert ph.physical_qubits / 1e6 == pytest.approx(
        GE19_FTPRIMS_ACHIEVED["parallel"]["qubits_M"], rel=0.02
    )


def test_ge19_parallel_runtime_per_run(physical):
    """Per run vs Table 3's 5.1 hr/run (-10.5%) — the like-for-like comparison."""
    assert physical.parallel_runtime_hr == pytest.approx(
        physical.parallel_target_runtime_hr_per_run, rel=GE19_TOL["rel_runtime"]
    )


def test_ge19_parallel_runtime_expected(physical):
    """Converted to GE19's expected convention vs Table 2's 0.31 day (-11.0%)."""
    assert physical.parallel_runtime_hr_expected == pytest.approx(
        physical.parallel_target_runtime_hr_expected, rel=GE19_TOL["rel_runtime"]
    )


def test_ge19_tables_2_and_3_are_consistent():
    """Table 2 and Table 3 reconcile exactly via the published retry risk.

    A property of the paper, asserted so "the two tables disagree" cannot be
    reintroduced.
    """
    t3 = GE19["physical_rows"]["table3_authoritative"]
    t2 = GE19["physical_rows"]["parallel"]
    assert t3["runtime_hr_per_run"] / (1 - t3["retry"]) / 24 == pytest.approx(
        t2["runtime_days"], rel=0.01
    )
    assert t3["vol_megaqubitdays_per_run"] / (1 - t3["retry"]) == pytest.approx(
        t2["vol_mqd"], rel=0.01
    )
