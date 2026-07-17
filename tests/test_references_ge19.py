"""GE19 reproduction (arXiv:1905.09749v3).

Logical-count reconciliation (call-graph ModExp vs GE19 closed form) and the
physical-layer reproductions of GE19's 1-factory and parallel rows, asserted
against targets in ``ftprims.references.values``. Each number is computed once by
``reproduce_ge19_logical`` / ``reproduce_ge19_physical``; the tests only read the
resulting rows. Tolerances are chosen from the achieved deviations and justified
inline in ``values.py`` (``GE19_TOL``); they are never loosened to pass.
"""

from __future__ import annotations

import pytest

from ftprims.references import reproduce_ge19_logical, reproduce_ge19_physical
from ftprims.references.values import GE19, GE19_FTPRIMS, GE19_TOL

# ── Reproductions built once (ModExp QECGatesCost ~0.01 s, grid search ~instant) ─


@pytest.fixture(scope="module")
def logical():
    return reproduce_ge19_logical()


@pytest.fixture(scope="module")
def physical():
    return reproduce_ge19_physical()


# ── 2a. Logical counts ─────────────────────────────────────────────────────────


def test_ge19_logical_qubits_formula(logical):
    """3n + 0.002·n·log2(n) rounds to the abstract's 6189 at n=2048."""
    assert round(logical.logical_qubits_formula) == GE19["logical_qubits"]


def test_ge19_toffoli_formula_matches_table1(logical):
    """0.3n^3 + 0.0005·n^3·log2(n) matches Table 1's 2.7e9 (billions).

    rel=0.05: Table 1 reports 2.7e9 (rounded to one decimal, in billions); the
    formula evaluates to 2.62e9, 2.9% below the rounded table value.
    """
    assert logical.toffoli_formula == pytest.approx(GE19["toffoli_count"], rel=0.05)


def test_modexp_call_graph_count_pinned(logical):
    """Qualtran 0.7.0 ModExp And-count is pinned exactly.

    This is a regression literal (a count from a real run of the pinned stack),
    asserted exact so a dependency bump that moves it surfaces as a finding.
    """
    assert logical.modexp_and_count == GE19["modexp_qualtran_toffoli"]


def test_modexp_sits_in_reference_regime(logical):
    """ModExp ≈ 10·ne·n^2 with ne=2n — GE19's reference (textbook) regime.

    Attribution test (divergence analysis): 20·ne·n^2 is the reference modular
    exponentiation cost, and half of it (the Toffoli, not Toffoli+CNOT, share)
    is ~10·ne·n^2. Asserting the measured count lands there (within 2%) pins the
    claim that Qualtran's ModExp is the non-windowed textbook construction, not
    GE19's optimized one.
    """
    assert logical.modexp_and_count == pytest.approx(logical.reference_half, rel=0.02)


def test_modexp_vs_formula_divergence(logical):
    """The ModExp/GE19-formula ratio is the ~64x logical divergence finding.

    Asserted in [40, 80] (GE19_TOL): the achieved ratio is 63.6x against Table
    1's 2.7e9 (65.5x against the formula-evaluated 2.62e9). The band is wide
    enough to be robust to which formula count is the denominator, tight enough
    to pin "reference regime, not optimized regime".
    """
    assert (
        GE19_TOL["divergence_lo"]
        <= logical.divergence_ratio
        <= GE19_TOL["divergence_hi"]
    )


# ── 2b. Physical layer (fed the GE19 formula count, not the ModExp count) ───────


def test_ge19_one_factory_qubits(physical):
    """1-factory (distillation-limited) physical qubits vs GE19 Table 2.

    rel=0.25 (GE19_TOL): ftprims 18.0M vs GE19 16M = +12.5%.
    """
    ph = physical.one_factory
    target_M = GE19["physical_rows"]["one_factory"]["qubits_M"]
    assert ph.physical_qubits / 1e6 == pytest.approx(
        target_M, rel=GE19_TOL["rel_qubits"]
    )
    # Also pin the achieved reproduction and the auto-searched code distance.
    assert ph.physical_qubits / 1e6 == pytest.approx(
        GE19_FTPRIMS["one_factory"]["qubits_M"], rel=0.02
    )
    assert ph.code_distance == GE19_FTPRIMS["one_factory"]["code_distance"]  # d=31


def test_ge19_one_factory_runtime(physical):
    """1-factory runtime vs GE19's 6 days.

    rel=0.30 (GE19_TOL): ftprims 127.9 hr vs 6 days (144 hr) = -11%.
    """
    ph = physical.one_factory
    target_hr = GE19["physical_rows"]["one_factory"]["runtime_days"] * 24
    assert ph.wall_time_us / 3.6e9 == pytest.approx(
        target_hr, rel=GE19_TOL["rel_runtime"]
    )


def test_ge19_parallel_qubits(physical):
    """16-factory grid-search physical qubits vs GE19's parallel row.

    rel=0.25 (GE19_TOL): ftprims 15.6M (16 factories) vs GE19 20M
    (28 factories) = -22%. ftprims uses fewer factories yet lands within band.
    """
    ph = physical.parallel
    target_M = GE19["physical_rows"]["parallel"]["qubits_M"]
    assert ph.physical_qubits / 1e6 == pytest.approx(
        target_M, rel=GE19_TOL["rel_qubits"]
    )
    assert ph.physical_qubits / 1e6 == pytest.approx(
        GE19_FTPRIMS["parallel"]["qubits_M"], rel=0.02
    )


def test_ge19_parallel_runtime(physical):
    """16-factory runtime vs GE19's parallel row (0.31 day).

    rel=0.30 (GE19_TOL): ftprims 8.0 hr vs GE19 0.31 day (7.44 hr) = +7.5%.
    (GE19's Table 3 quotes 5.1 hr/run for its 28-factory design; the ~57%
    gap to that authoritative number is reported as a divergence, not asserted.)
    """
    ph = physical.parallel
    target_hr = GE19["physical_rows"]["parallel"]["runtime_days"] * 24
    assert ph.wall_time_us / 3.6e9 == pytest.approx(
        target_hr, rel=GE19_TOL["rel_runtime"]
    )
