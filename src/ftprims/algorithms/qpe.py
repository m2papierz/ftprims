"""QPE benchmark: Textbook Quantum Phase Estimation.

The default unitary is ``ZPowGate(exponent=2*phi)``. The benchmark
layer accepts any single-qubit ``Bloq`` as ``unitary``, but the CLI
preset uses ZPowGate.

Verification enforces exact phases so that QPE output is deterministic
and the check is bit-exact.  Register identification uses
``to_cirq_circuit_and_quregs()`` instead of fragile qubit-name heuristics.
"""

from __future__ import annotations

import functools
import operator

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


def _build_qpe(*, m: int, phi: float, unitary: Bloq | None = None) -> Bloq:
    """Construct a TextbookQPE for a single-qubit phase gate.

    Parameters
    ----------
    m:
        Number of precision bits.
    phi:
        Phase of the toy unitary (0 ≤ phi < 1).  The unitary is
        ``ZPowGate(exponent=2·phi)`` whose eigenstate |1⟩ has
        eigenvalue e^(2πi·phi).
    unitary:
        Optional custom unitary bloq.  When ``None`` (the default),
        uses ``ZPowGate(exponent=2·phi)``.
    """
    if m < 1:
        raise ValueError(f"Precision bits must be ≥ 1, got {m}")
    if not 0.0 <= phi < 1.0:
        raise ValueError(f"Phase must be in [0, 1), got {phi}")

    if unitary is None:
        unitary = ZPowGate(exponent=2 * phi)

    return TextbookQPE(
        unitary=unitary,
        ctrl_state_prep=RectangularWindowState(bitsize=m),
    )


def _is_exact_phase(phi: float, m: int) -> bool:
    """Check whether *phi* is an exact multiple of 1/2^m."""
    scaled = phi * (1 << m)
    return abs(scaled - round(scaled)) < 1e-12


def _total_qubits_from_signature(bloq: Bloq) -> int:
    """Derive the total qubit count from the bloq's register signature."""
    total = 0
    for reg in bloq.signature:
        size = int(reg.bitsize)
        shape = tuple(int(s) for s in reg.shape) if reg.shape else ()
        n_entries = functools.reduce(operator.mul, shape, 1)
        total += size * n_entries
    return total


def _tensor_to_unitary(bloq: Bloq) -> np.ndarray:
    """Extract a 2D unitary matrix from a bloq's tensor contraction.

    Qualtran's ``tensor_contract`` may return a higher-dimensional
    tensor when the bloq has multiple named registers.  This function
    reshapes the result into a square 2D unitary.

    Tries the bloq directly first, then one level of decomposition.
    """
    n_qubits = _total_qubits_from_signature(bloq)
    dim = 1 << n_qubits

    for source_name, source in [
        ("bloq", bloq),
        ("decompose_bloq", bloq.decompose_bloq()),
    ]:
        try:
            tensor = source.tensor_contract()
            U = np.reshape(tensor, (dim, dim))
            return U
        except Exception:
            continue

    raise RuntimeError(
        f"tensor_contract failed for QPE bloq ({n_qubits} qubits, dim={dim})"
    )


@register
class QPEBenchmark(Benchmark):
    """Benchmark wrapper for Textbook Quantum Phase Estimation."""

    name = "qpe"

    def build_bloq(
        self,
        *,
        m: int = 8,
        phi: float = 0.25,
        unitary: Bloq | None = None,
    ) -> Bloq:
        return _build_qpe(m=int(m), phi=float(phi), unitary=unitary)

    def logical_costs(
        self,
        bloq: Bloq,
        *,
        rotation_synthesis_epsilon: float | None = None,
    ) -> LogicalCosts:
        return extract_logical_costs(
            bloq,
            rotation_synthesis_epsilon=rotation_synthesis_epsilon,
        )

    def verify_small(self, *, m: int = 4, phi: float = 0.25) -> VerificationResult:
        """Verify QPE via Cirq simulation on the eigenstate |1⟩.

        Only exact phases (multiples of 1/2^m) are accepted for
        deterministic verification.  For inexact phases, use the
        benchmark ``run`` command instead.

        Uses ``to_cirq_circuit_and_quregs()`` to identify registers
        by name rather than relying on qubit sort order.
        """
        m = int(m)
        phi = float(phi)

        if m > _MAX_VERIFY_M:
            return VerificationResult(
                status="skip",
                detail=f"m={m} too large for simulation (max {_MAX_VERIFY_M})",
            )

        if not _is_exact_phase(phi, m):
            return VerificationResult(
                status="skip",
                detail=(
                    f"phi={phi} is not an exact multiple of 1/2^{m}; "
                    f"verification requires exact phases for deterministic output"
                ),
            )

        bloq = self.build_bloq(m=m, phi=phi)

        # Build circuit with register map - fall back to tensor_contract
        # if Cirq circuit construction fails (some Qualtran versions
        # raise errors on register name collisions).
        try:
            cbloq = bloq.decompose_bloq()
            circuit, quregs = cbloq.to_cirq_circuit_and_quregs()
        except Exception:
            return self._verify_via_tensor(bloq, m=m, phi=phi)

        # Identify registers from quregs map by name.
        # TextbookQPE signature: qpe_reg (m qubits) + unitary target register(s).
        available = list(quregs.keys())

        if "qpe_reg" not in quregs:
            return VerificationResult(
                status="fail",
                detail=(
                    f"Cannot find 'qpe_reg' in circuit registers; "
                    f"available: {available}"
                ),
            )

        qpe_qubits = list(quregs["qpe_reg"].flat)

        # Target register: the first named register that is not qpe_reg.
        target_names = [k for k in available if k != "qpe_reg"]
        if not target_names:
            return VerificationResult(
                status="fail",
                detail="No target register found in quregs besides qpe_reg",
            )

        target_qubits = []
        for name in target_names:
            target_qubits.extend(list(quregs[name].flat))

        # Build qubit order: qpe_reg first, then target
        # This way the top bits of the state vector index are the QPE
        # register and the bottom bits are the target.
        qubit_order = qpe_qubits + target_qubits
        n_target = len(target_qubits)

        # Prepare initial state
        # QPE register: |0...0⟩, target: |1⟩ (eigenstate of ZPowGate).
        # With our qubit order, target is in the lowest bits.
        initial_state = 1  # |0...0⟩|1⟩

        # Simulate
        sim = cirq.Simulator()
        result = sim.simulate(
            circuit,
            initial_state=initial_state,
            qubit_order=qubit_order,
        )
        probs = np.abs(result.final_state_vector) ** 2
        best = int(np.argmax(probs))

        # Extract QPE register value
        # State index layout: [qpe_reg bits | target bits]
        qpe_val = best >> n_target
        estimated_phi = qpe_val / (1 << m)

        expected_val = round(phi * (1 << m))
        expected_phi = expected_val / (1 << m)

        if qpe_val != expected_val:
            return VerificationResult(
                status="fail",
                detail=(
                    f"Phase mismatch: measured QPE register={qpe_val} "
                    f"(phi={estimated_phi:.6f}), expected={expected_val} "
                    f"(phi={expected_phi:.6f}), prob={probs[best]:.4f}"
                ),
            )

        return VerificationResult(
            status="pass",
            detail=(
                f"QPE(m={m}, phi={phi}): register={qpe_val}, "
                f"estimated_phi={estimated_phi:.6f}, prob={probs[best]:.4f}"
            ),
        )

    @staticmethod
    def _verify_via_tensor(bloq: Bloq, *, m: int, phi: float) -> VerificationResult:
        """Fallback QPE verification using tensor_contract().

        Used when Cirq circuit construction fails. Applies the QPE
        unitary to |0...0⟩|1⟩ and checks that the QPE register encodes
        the expected phase.

        Qualtran's tensor_contract() may return a multi-dimensional
        tensor for bloqs with multiple named registers, so we derive
        the expected dimension from the signature and reshape.
        """
        try:
            U = _tensor_to_unitary(bloq)
        except Exception as exc:
            return VerificationResult(
                status="fail",
                detail=f"tensor_contract failed: {exc}",
            )

        dim = U.shape[0]
        n_total = int(round(np.log2(dim)))
        n_target = n_total - m  # remaining qubits are target

        if n_target < 1:
            return VerificationResult(
                status="fail",
                detail=(
                    f"Unexpected dimensions: total qubits={n_total}, m={m}, "
                    f"target qubits={n_target} (must be ≥ 1)"
                ),
            )

        # Initial state: QPE register |0...0⟩, target |1⟩ (LSBs).
        initial = np.zeros(dim, dtype=complex)
        initial[1] = 1.0  # |0...01⟩

        final = U @ initial
        probs = np.abs(final) ** 2
        best_idx = int(np.argmax(probs))
        qpe_val = best_idx >> n_target
        estimated_phi = qpe_val / (1 << m)

        expected_val = round(phi * (1 << m))

        if qpe_val != expected_val:
            return VerificationResult(
                status="fail",
                detail=(
                    f"Phase mismatch (tensor fallback): qpe_reg={qpe_val} "
                    f"(phi={estimated_phi:.6f}), expected={expected_val}, "
                    f"prob={probs[best_idx]:.4f}"
                ),
            )

        return VerificationResult(
            status="pass",
            detail=(
                f"QPE(m={m}, phi={phi}): register={qpe_val}, "
                f"phi={estimated_phi:.6f}, prob={probs[best_idx]:.4f} "
                f"(tensor fallback)"
            ),
        )
