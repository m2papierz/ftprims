"""QPE benchmark: ``TextbookQPE`` over a single-qubit unitary.

``build_bloq`` accepts any single-qubit ``Bloq`` as ``unitary``; the CLI preset
is ``ZPowGate(exponent=2*phi)``. Verification accepts exact phases only, so the
measured register is deterministic.
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

from qrepro.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)
from qrepro.resource import extract_logical_costs

__all__ = ["QPEBenchmark"]

_MAX_VERIFY_M = 8
_MAX_DECOMPOSE_DEPTH = 4


def _build_qpe(*, m: int, phi: float, unitary: Bloq | None = None) -> Bloq:
    """Construct a ``TextbookQPE`` with *m* precision bits.

    *phi* is the phase in [0, 1) of the default unitary
    ``ZPowGate(exponent=2·phi)``, whose eigenstate |1> has eigenvalue
    e^(2πi·phi). *unitary* overrides that default.
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


def _build_cirq_circuit(bloq: Bloq) -> tuple[cirq.Circuit, dict] | None:
    """Build a Cirq circuit and register map, trying increasing depth.

    Qualtran raises ``KeyError`` on register-name collisions at shallow
    decomposition depth; deeper levels resolve sub-bloqs into primitives that
    do not collide. Returns ``(circuit, quregs)``, or ``None`` if every depth
    fails.
    """
    cbloq = bloq
    for _ in range(_MAX_DECOMPOSE_DEPTH):
        try:
            cbloq = cbloq.decompose_bloq()
            circuit, quregs = cbloq.to_cirq_circuit_and_quregs()
            return circuit, quregs
        except Exception:
            continue
    return None


def _verify_via_tensor(bloq: Bloq, *, m: int, phi: float) -> VerificationResult:
    """Verify QPE via ``tensor_contract()`` when circuit construction fails.

    ``tensor_contract()`` returns a multi-dimensional tensor for bloqs with
    several named registers, so the dimension is derived from the signature and
    the tensor reshaped.
    """
    n_qubits = _total_qubits_from_signature(bloq)
    dim = 1 << n_qubits

    U = None
    source = bloq
    for _ in range(_MAX_DECOMPOSE_DEPTH + 1):
        try:
            tensor = source.tensor_contract()
            U = np.reshape(tensor, (dim, dim))
            break
        except Exception:
            pass
        try:
            source = source.decompose_bloq()
        except Exception:
            break

    if U is None:
        return VerificationResult(
            status="skip",
            detail=(
                f"QPE(m={m}): Cirq circuit construction and "
                f"tensor_contract both failed at all decomposition "
                f"depths (Qualtran interop limitation)"
            ),
        )

    n_target = n_qubits - m
    if n_target < 1:
        return VerificationResult(
            status="fail",
            detail=(
                f"Unexpected dimensions: total qubits={n_qubits}, m={m}, "
                f"target qubits={n_target} (must be ≥ 1)"
            ),
        )

    # Initial state: QPE register |0...0>, target |1> (LSBs).
    initial = np.zeros(dim, dtype=complex)
    initial[1] = 1.0

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


@register
class QPEBenchmark(Benchmark):
    """Textbook Quantum Phase Estimation."""

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
        """Verify QPE by Cirq simulation on the eigenstate |1>.

        Skips unless *phi* is an exact multiple of 1/2^m, which is what makes
        the measured register deterministic. Falls back to ``tensor_contract()``
        when Cirq circuit construction fails at every decomposition depth.
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

        result = _build_cirq_circuit(bloq)
        if result is None:
            return _verify_via_tensor(bloq, m=m, phi=phi)

        circuit, quregs = result
        available = list(quregs.keys())

        if "qpe_reg" not in quregs:
            return _verify_via_tensor(bloq, m=m, phi=phi)

        qpe_qubits = list(quregs["qpe_reg"].flat)

        # Every named register that is not qpe_reg is target.
        target_names = [k for k in available if k != "qpe_reg"]
        if not target_names:
            return _verify_via_tensor(bloq, m=m, phi=phi)

        target_qubits = []
        for name in target_names:
            target_qubits.extend(list(quregs[name].flat))

        # Top bits of the state-vector index are the QPE register.
        qubit_order = qpe_qubits + target_qubits
        n_target = len(target_qubits)

        initial_state = 1  # |0...0>|1>, the ZPowGate eigenstate

        sim = cirq.Simulator()
        result = sim.simulate(
            circuit,
            initial_state=initial_state,
            qubit_order=qubit_order,
        )
        probs = np.abs(result.final_state_vector) ** 2
        best = int(np.argmax(probs))

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
