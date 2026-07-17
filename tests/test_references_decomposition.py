"""2019 → 2025 decomposition (arXiv:2505.15917).

Asserts the decomposition rows computed once by ``reproduce_2019_to_2025()``:
G2025's counts through the same CCZ2T model, the structural gap to the published
< 1M headline, and the algorithmic (logical-qubit) reduction the model does
capture. Tolerances come from ``G2025_TOL`` in ``values.py``.
"""

from __future__ import annotations

import pytest

from ftprims.references import reproduce_2019_to_2025
from ftprims.references.values import G2025_FTPRIMS, G2025_TOL


@pytest.fixture(scope="module")
def decomposition():
    return reproduce_2019_to_2025()


@pytest.mark.parametrize("n_factories", [1, 16])
def test_g2025_through_model_reproduces(decomposition, n_factories):
    """G2025 counts through the same CCZ2T model reproduce the achieved numbers.

    rel=0.20 (G2025_TOL): guards against gross drift, not a paper target — the
    paper's < 1M is explicitly NOT reproducible by this model (yoked codes +
    cultivation are out of scope), so we assert only that the model lands where
    it landed live: 1-factory 3.68M, 16-factory 5.19M.
    """
    g2025 = decomposition.by_factories(n_factories).g2025
    key = (
        "g2025_through_model_1f_qubits_M"
        if n_factories == 1
        else "g2025_through_model_16f_qubits_M"
    )
    assert g2025.physical_qubits / 1e6 == pytest.approx(
        G2025_FTPRIMS[key], rel=G2025_TOL["rel_qubits"]
    )


def test_g2025_below_published_headline(decomposition):
    """The model CANNOT reach G2025's published < 1M — that gap is the finding.

    Even at 1 factory the ftprims CCZ2T model gives millions of physical qubits;
    the published < 1e6 requires yoked surface codes + magic state cultivation,
    which this cost model structurally cannot represent. Asserting the model
    stays well above 1e6 documents the structural gap.
    """
    g2025 = decomposition.by_factories(1).g2025
    assert g2025.physical_qubits > 2e6  # far above the paper's < 1e6 headline


@pytest.mark.parametrize("n_factories", [1, 16])
def test_2019_to_2025_algorithmic_ratio(decomposition, n_factories):
    """The algorithmic (logical-qubit) reduction the model DOES capture.

    Feeding GE19 vs G2025 counts through the SAME factory count (apples-to-
    apples) yields the algorithmic share. Asserted in [2.5, 6.0] (G2025_TOL):
    the honest range spanned by the factory-count sweep — ~3.0x at 16 factories,
    ~4.9x at 1 factory. The residual reduction down to the published < 1M is the
    unmodelable QEC stack.
    """
    ratio = decomposition.by_factories(n_factories).algorithmic_ratio
    assert G2025_TOL["algo_ratio_lo"] <= ratio <= G2025_TOL["algo_ratio_hi"]
