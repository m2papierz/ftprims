"""Cirq-based small-scale verification utilities."""

from __future__ import annotations

import cirq
import numpy as np
from qualtran import Bloq


def bloq_unitary(bloq: Bloq) -> np.ndarray:
    """Extract the unitary matrix of a bloq (small instances only)."""
    cbloq = bloq.decompose_bloq()
    circuit, _ = cbloq.to_cirq_circuit()

    return cirq.unitary(circuit)


def simulate_bloq(bloq: Bloq, initial_state: int = 0) -> np.ndarray:
    """Simulate a bloq on *initial_state* and return the final state vector."""
    cbloq = bloq.decompose_bloq()
    circuit, _ = cbloq.to_cirq_circuit()

    sim = cirq.Simulator()
    result = sim.simulate(circuit, initial_state=initial_state)
    return result.final_state_vector
