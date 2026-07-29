"""2019 -> 2025 decomposition (arXiv:2505.15917).

Both Toffoli conventions are exercised, which bounds the convention mismatch
instead of hiding it. See ASSUMPTIONS.md §3.
"""

from __future__ import annotations

import pytest

from qrepro.references import reproduce_2019_to_2025
from qrepro.references.decomposition import CONVENTIONS, _toffoli_counts
from qrepro.references.values import G2025, G2025_QREPRO, G2025_TOL, GE19

_FACTORY_COUNTS = (1, 16, 28)


@pytest.fixture(scope="module")
def decompositions():
    return {conv: reproduce_2019_to_2025(conv) for conv in CONVENTIONS}


def test_conventions_normalise_as_documented():
    """Each convention puts both papers' Toffoli counts on one footing."""
    shots = G2025["expected_shots"]
    retry = GE19["physical_rows"]["table3_authoritative"]["retry"]
    assert shots == 9.2  # arXiv:2505.15917 Table 5, n=2048 "E(shots)"

    ge19_pr, g2025_pr = _toffoli_counts("per_run")
    assert ge19_pr == GE19["toffoli_count"]
    assert g2025_pr == pytest.approx(G2025["toffoli_count"] / shots)

    ge19_ex, g2025_ex = _toffoli_counts("expected")
    assert ge19_ex == pytest.approx(GE19["toffoli_count"] / (1 - retry))
    assert g2025_ex == G2025["toffoli_count"]


@pytest.mark.parametrize("convention", CONVENTIONS)
@pytest.mark.parametrize("n_factories", _FACTORY_COUNTS)
def test_g2025_through_model_reproduces(decompositions, convention, n_factories):
    """G2025 counts through the model reproduce the achieved numbers.

    rel=0.20 guards drift only; the paper's < 1M is not reproducible here.
    """
    g2025 = decompositions[convention].by_factories(n_factories).g2025
    expected = G2025_QREPRO[convention][f"g2025_{n_factories}f_qubits_M"]
    assert g2025.physical_qubits / 1e6 == pytest.approx(
        expected, rel=G2025_TOL["rel_qubits"]
    )


@pytest.mark.parametrize("convention", CONVENTIONS)
def test_g2025_stays_above_published_qubit_target(decompositions, convention):
    """The model floors out in the millions, above G2025's published < 1e6."""
    g2025 = decompositions[convention].by_factories(1).g2025
    assert g2025.physical_qubits > 2e6


@pytest.mark.parametrize("convention", CONVENTIONS)
@pytest.mark.parametrize("n_factories", _FACTORY_COUNTS)
def test_2019_to_2025_algorithmic_ratio(decompositions, convention, n_factories):
    """The algorithmic reduction the model captures.

    Asserted in [2.5, 6.0]: the achieved span across factory counts
    {1, 16, 28} x conventions {per_run, expected} is 2.63x .. 5.64x.
    """
    ratio = decompositions[convention].by_factories(n_factories).algorithmic_ratio
    assert G2025_TOL["algo_ratio_lo"] <= ratio <= G2025_TOL["algo_ratio_hi"]


def test_convention_choice_is_recorded(decompositions):
    """A decomposition carries the convention it was computed under."""
    for conv, d in decompositions.items():
        assert d.convention == conv
        assert d.error_budget == G2025_QREPRO["error_budget"] == 0.31
