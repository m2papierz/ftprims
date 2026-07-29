"""Beverland et al. reproduction (arXiv:2211.07629).

Plumbing check, not independent convergence: Qualtran ships the Beverland
model. Targets and the quantum-dynamics paper defect: ASSUMPTIONS.md §1.
"""

from __future__ import annotations

import pytest

from ftprims.references import reproduce_beverland
from ftprims.references.values import BEVERLAND_TOL

_INSTANCES = list(reproduce_beverland().instances)
_IDS = [inst.name for inst in _INSTANCES]


@pytest.mark.parametrize("inst", _INSTANCES, ids=_IDS)
def test_beverland_c_min(inst):
    """Minimum time steps reproduce eq.(D3) (worst achieved +0.43%)."""
    assert inst.c_min == pytest.approx(
        inst.expect_c_min, rel=BEVERLAND_TOL["rel_c_min"]
    ), f"{inst.name}: c_min={inst.c_min} vs {inst.expect_c_min}"


@pytest.mark.parametrize("inst", _INSTANCES, ids=_IDS)
def test_beverland_t_states(inst):
    """T-states reproduce eq.(D4) (worst achieved +0.22%)."""
    assert inst.t_states == pytest.approx(
        inst.expect_t_states, rel=BEVERLAND_TOL["rel_t_states"]
    ), f"{inst.name}: t_states={inst.t_states} vs {inst.expect_t_states}"


@pytest.mark.parametrize("inst", _INSTANCES, ids=_IDS)
def test_beverland_code_distance(inst):
    """Code distance reproduces the paper exactly; no tolerance."""
    assert inst.code_distance == inst.expect_code_distance, (
        f"{inst.name}: {inst.code_distance} vs {inst.expect_code_distance}"
    )
