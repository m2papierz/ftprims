"""Beverland et al. reproduction (arXiv:2211.07629).

Asserts the rows computed once by ``reproduce_beverland()`` against the targets
in ``ftprims.references.values``.

This is a *plumbing* check, not an independent convergence: Qualtran ships the
Beverland model, so ``reproduce_beverland`` calls the same model the targets
were read from. Near-exact agreement is expected and is what validates that
ftprims wires the model up correctly.
"""

from __future__ import annotations

import pytest

from ftprims.references import reproduce_beverland
from ftprims.references.values import BEVERLAND_TOL

_INSTANCES = list(reproduce_beverland().instances)
_IDS = [inst.name for inst in _INSTANCES]


@pytest.mark.parametrize("inst", _INSTANCES, ids=_IDS)
def test_beverland_c_min(inst):
    """Minimum time steps reproduce the paper instance.

    rel=0.10 (BEVERLAND_TOL): worst achieved deviation is quantum_dynamics
    c_min (1.44e6 vs 1.5e6 = 4.0%); 0.10 matches the band Qualtran's own
    beverland_et_al_model_test.py asserts these at.
    """
    assert inst.c_min == pytest.approx(
        inst.expect_c_min, rel=BEVERLAND_TOL["rel_c_min"]
    ), f"{inst.name}: c_min={inst.c_min} vs {inst.expect_c_min}"


@pytest.mark.parametrize("inst", _INSTANCES, ids=_IDS)
def test_beverland_t_states(inst):
    """T-states consumed reproduce the paper instance (rel=0.10, as above)."""
    assert inst.t_states == pytest.approx(
        inst.expect_t_states, rel=BEVERLAND_TOL["rel_t_states"]
    ), f"{inst.name}: t_states={inst.t_states} vs {inst.expect_t_states}"


@pytest.mark.parametrize("inst", _INSTANCES, ids=_IDS)
def test_beverland_code_distance(inst):
    """Code distance reproduces the paper instance EXACTLY.

    Asserted exact (not within a band) because code_distance is a small
    integer the model computes deterministically: quantum_chemistry=17,
    factoring=13, and quantum_dynamics=9 when d is asked at the tabulated
    time_steps (1.5e5) rather than at the computed c_min. An off-by-one here
    would be a real wiring regression, so no tolerance is granted.
    """
    assert inst.code_distance == inst.expect_code_distance, (
        f"{inst.name}: code_distance={inst.code_distance} vs {inst.expect_code_distance}"
    )
