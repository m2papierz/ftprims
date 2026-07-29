"""Beverland et al. reproduction (arXiv:2211.07629).

Calls ``beverland_et_al_model`` directly rather than the ftprims auto-distance
search. Qualtran ships the Beverland model, so near-exact agreement with the
targets in ``values.py`` checks the wiring, not independent convergence.
"""

from __future__ import annotations

import attrs
from qualtran.resource_counting import GateCounts
from qualtran.surface_code import AlgorithmSummary, QECScheme, beverland_et_al_model
from qualtran.surface_code.rotation_cost_model import BeverlandEtAlRotationCost

from ftprims.references._base import ReproductionRow
from ftprims.references.values import BEVERLAND


@attrs.define(frozen=True)
class BeverlandReferenceCosts:
    """Beverland-model outputs for one instance: minimum time steps, T-states
    consumed, and code distance."""

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

    ``code_distance`` is evaluated at *time_steps_for_code_distance*, the
    paper's tabulated step count, not at the computed ``c_min``.

    Parameters
    ----------
    n_algo_qubits:
        Algorithm (logical) qubits.
    gate_counts:
        Kwargs for ``GateCounts``: ``t``, ``rotation``, ``toffoli``,
        ``measurement``.
    n_rotation_layers:
        Rotation layers.
    error_budget:
        Total error budget for the instance.
    time_steps_for_code_distance:
        Time-step count at which to evaluate the code distance.
    physical_error:
        Physical error rate; arXiv:2211.07629 uses 1e-4.
    """
    alg = AlgorithmSummary(
        n_algo_qubits=n_algo_qubits,
        n_logical_gates=GateCounts(**gate_counts),
        n_rotation_layers=n_rotation_layers,
    )

    c_min = beverland_et_al_model.minimum_time_steps(
        error_budget=error_budget,
        alg=alg,
        rotation_model=BeverlandEtAlRotationCost,
    )

    t_states = beverland_et_al_model.t_states(
        error_budget=error_budget,
        alg=alg,
        rotation_model=BeverlandEtAlRotationCost,
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
    """Reproduce all three Beverland application instances from ``BEVERLAND``."""
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


@attrs.define(frozen=True)
class BeverlandInstance:
    """One instance's reproduced ``c_min`` / ``t_states`` / ``code_distance``
    alongside the paper targets they are asserted against."""

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
    """All three Beverland application instances."""

    instances: tuple[BeverlandInstance, ...]

    @property
    def rows(self) -> tuple[ReproductionRow, ...]:
        return tuple(row for inst in self.instances for row in inst.rows)
