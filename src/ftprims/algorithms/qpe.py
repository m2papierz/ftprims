"""QPE benchmark: Textbook Quantum Phase Estimation.

Uses ``ZPowGate(exponent=2·phi)`` as a toy unitary whose eigenstate
|1⟩ has eigenvalue e^(2πi·phi). Verification runs Cirq simulation
and checks the most-probable measurement outcome against the true phase.
"""

from __future__ import annotations

import cirq
import numpy as np
from qualtran import Bloq
from qualtran.bloqs.basic_gates import ZPowGate
from qualtran.bloqs.phase_estimation.qpe_window_state import RectangularWindowState
from qualtran.bloqs.phase_estimation.text_book_qpe import TextbookQPE

from ftprims.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)
from ftprims.resource import extract_logical_costs


__all__ = ["QPEBenchmark"]

_MAX_VERIFY_M = 8


def _build_qpe(*, m: int, phi: float) -> Bloq:
    """Construct a TextbookQPE for a single-qubit phase gate.

    Parameters
    ----------
    m:
        Number of precision bits.
    phi:
        Phase of the toy unitary (0 ≤ phi < 1).  The unitary is
        ``ZPowGate(exponent=2·phi)`` whose eigenstate |1⟩ has
        eigenvalue e^(2πi·phi).
    """
    if m < 1:
        raise ValueError(f"Precision bits must be ≥ 1, got {m}")
    if not 0.0 <= phi < 1.0:
        raise ValueError(f"Phase must be in [0, 1), got {phi}")

    unitary = ZPowGate(exponent=2 * phi)
    return TextbookQPE(
        unitary=unitary,
        ctrl_state_prep=RectangularWindowState(bitsize=m),
    )


@register
class QPEBenchmark(Benchmark):
    """Benchmark wrapper for Textbook Quantum Phase Estimation."""

    name = "qpe"

    def build_bloq(self, *, m: int = 8, phi: float = 0.25) -> Bloq:
        return _build_qpe(m=int(m), phi=float(phi))

    def logical_costs(self, bloq: Bloq) -> LogicalCosts:
        return extract_logical_costs(bloq)

    def verify_small(self, *, m: int = 4, phi: float = 0.25) -> VerificationResult:
        """Verify QPE via Cirq simulation on the eigenstate |1⟩.

        Uses exact phases (multiples of 1/2^m) so the QPE output is
        deterministic. Checks that the most-probable measurement
        outcome reconstructs the true phase.
        """
        m = int(m)
        phi = float(phi)

        if m > _MAX_VERIFY_M:
            return VerificationResult(
                passed=False,
                detail=f"m={m} too large for simulation (max {_MAX_VERIFY_M})",
            )

        bloq = self.build_bloq(m=m, phi=phi)

        try:
            circuit = bloq.decompose_bloq().to_cirq_circuit()
        except Exception as exc:
            return VerificationResult(
                passed=False, detail=f"Circuit construction failed: {exc}"
            )

        qubits = sorted(circuit.all_qubits())

        # Identify the target qubit by name. TextbookQPE names it 'q'
        # (single-qubit unitary register). We need it at position LSB
        # so that ``best >> 1`` extracts the QPE register correctly.
        target_names = {q for q in qubits if str(q) == "q"}
        if len(target_names) != 1 or qubits[-1] not in target_names:
            return VerificationResult(
                passed=False,
                detail=(
                    "Cannot identify target qubit 'q' as LSB in sorted order; "
                    "qubit naming may have changed in Qualtran. "
                    f"Sorted qubits: {[str(q) for q in qubits]}"
                ),
            )

        # Initial state: qpe_reg = |0…0⟩, q = |1⟩ (eigenstate).
        # Sorted order puts NamedQubit('q') last => LSB = 1.
        sim = cirq.Simulator()
        result = sim.simulate(circuit, initial_state=1, qubit_order=qubits)
        probs = np.abs(result.final_state_vector) ** 2
        best = int(np.argmax(probs))

        # Extract the QPE register (all bits except q which is the LSB).
        qpe_val = best >> 1
        estimated_phi = qpe_val / (1 << m)

        if not np.isclose(estimated_phi, phi, atol=1.0 / (1 << m)):
            return VerificationResult(
                passed=False,
                detail=(
                    f"Phase mismatch: estimated={estimated_phi:.6f} "
                    f"true={phi:.6f} (prob={probs[best]:.4f})"
                ),
            )

        return VerificationResult(
            passed=True,
            detail=(
                f"QPE(m={m}, phi={phi}): estimated={estimated_phi:.6f} "
                f"prob={probs[best]:.4f}"
            ),
        )
