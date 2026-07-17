"""Beverland et al. reproduction (arXiv:2211.07629).

Reproduces the three application instances Qualtran 0.7.0 encodes from Beverland
et al. by calling ``beverland_et_al_model`` directly (not the ftprims
auto-distance search). This is a *plumbing* check, not an independent
convergence: Qualtran ships the Beverland model, so near-exact agreement with
the targets in ``values.py`` is expected and validates that ftprims wires the
model up correctly.
"""

from __future__ import annotations

import attrs
from qualtran.resource_counting import GateCounts
from qualtran.surface_code import AlgorithmSummary, QECScheme, beverland_et_al_model
from qualtran.surface_code.rotation_cost_model import BeverlandEtAlRotationCost

from ftprims.references._base import BeverlandInstance, BeverlandReproduction
from ftprims.references.values import BEVERLAND


@attrs.define(frozen=True)
class BeverlandReferenceCosts:
    """Beverland-model logical outputs for one application instance.

    Reproduces Qualtran 0.7.0's ``beverland_et_al_model`` directly (not via the
    ftprims auto-distance search): ``c_min`` (minimum time steps), ``t_states``
    (T-states consumed), and ``code_distance``.
    """

    c_min: int
    t_states: float
    code_distance: int


def beverland_reference_costs(
    *,
    n_algo_qubits: int,
    gate_counts: dict[str, int],
    n_rotation_layers: int,
    error_budget: float,
    time_steps_for_code_distance: float,
    physical_error: float,
) -> BeverlandReferenceCosts:
    """Evaluate Qualtran's Beverland model for one application instance.

    Calls ``beverland_et_al_model.{minimum_time_steps, t_states,
    code_distance}`` on a manually-built ``AlgorithmSummary`` with the
    Beverland rotation-cost model and QEC scheme. ``code_distance`` is asked at
    *time_steps_for_code_distance* (the paper's tabulated step count), not at
    the computed ``c_min``.

    Parameters
    ----------
    n_algo_qubits:
        Number of algorithm (logical) qubits.
    gate_counts:
        Kwargs for ``GateCounts`` (e.g. ``t``, ``rotation``, ``toffoli``,
        ``measurement``).
    n_rotation_layers:
        Number of rotation layers.
    error_budget:
        Total error budget for the instance.
    time_steps_for_code_distance:
        Time-step count at which to evaluate the code distance.
    physical_error:
        Physical error rate for the code-distance calculation (2211.07629
        uses 1e-4).
    """
    alg = AlgorithmSummary(
        n_algo_qubits=n_algo_qubits,
        n_logical_gates=GateCounts(**gate_counts),
        n_rotation_layers=n_rotation_layers,
    )
    rotation_model = BeverlandEtAlRotationCost
    c_min = beverland_et_al_model.minimum_time_steps(
        error_budget=error_budget, alg=alg, rotation_model=rotation_model
    )
    t_states = beverland_et_al_model.t_states(
        error_budget=error_budget, alg=alg, rotation_model=rotation_model
    )
    code_distance = beverland_et_al_model.code_distance(
        error_budget=error_budget,
        time_steps=time_steps_for_code_distance,
        alg=alg,
        qec_scheme=QECScheme.make_beverland_et_al(),
        physical_error=physical_error,
    )
    return BeverlandReferenceCosts(
        c_min=int(c_min),
        t_states=float(t_states),
        code_distance=int(code_distance),
    )


def reproduce_beverland() -> BeverlandReproduction:
    """Reproduce all three Beverland application instances.

    Computes the reproduction rows once from ``BEVERLAND``; tests assert them
    against the paper targets, the notebook renders them, and the CLI prints
    them.
    """
    instances = []
    for name, case in BEVERLAND.items():
        costs = beverland_reference_costs(
            n_algo_qubits=case["n_algo_qubits"],
            gate_counts=case["gate_counts"],
            n_rotation_layers=case["n_rotation_layers"],
            error_budget=case["error_budget"],
            time_steps_for_code_distance=case["time_steps_for_code_distance"],
            physical_error=case["physical_error"],
        )
        instances.append(
            BeverlandInstance(
                name=name,
                c_min=costs.c_min,
                t_states=costs.t_states,
                code_distance=costs.code_distance,
                expect_c_min=case["expect_c_min"],
                expect_t_states=case["expect_t_states"],
                expect_code_distance=case["expect_code_distance"],
            )
        )
    return BeverlandReproduction(instances=tuple(instances))
