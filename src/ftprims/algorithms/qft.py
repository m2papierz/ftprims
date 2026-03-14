"""QFT benchmark of Textbook and Approximate variants.

Wraps ``qualtran.bloqs.qft`` to expose a uniform ``Benchmark`` interface
with logical resource estimation and small-scale Cirq verification.
"""

from __future__ import annotations

import numpy as np
from qualtran import Bloq
from qualtran.bloqs.qft.approximate_qft import ApproximateQFT
from qualtran.bloqs.qft.qft_text_book import QFTTextBook

from ftprims.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)
from ftprims.resource import extract_logical_costs


__all__ = ["QFTBenchmark"]

_VARIANTS = {"textbook", "approx"}
_MAX_VERIFY_N = 10


def _build_qft(*, n: int, variant: str = "textbook") -> Bloq:
    """Construct a QFT bloq for the requested variant.

    Parameters
    ----------
    n:
        Number of qubits (bitsize).
    variant:
        ``"textbook"`` for the exact QFT or ``"approx"`` for the
        approximate version that truncates small-angle rotations
        (phase_bitsize = n // 2).
    """
    if variant not in _VARIANTS:
        raise ValueError(
            f"Unknown QFT variant {variant!r}; choose from {sorted(_VARIANTS)}"
        )

    if n < 1:
        raise ValueError(f"Bitsize must be ≥ 1, got {n}")

    if variant == "textbook":
        return QFTTextBook(bitsize=n)

    phase_bitsize = max(n // 2, 1)
    return ApproximateQFT(bitsize=n, phase_bitsize=phase_bitsize)


@register
class QFTBenchmark(Benchmark):
    """Benchmark wrapper for the Quantum Fourier Transform."""

    name = "qft"

    def build_bloq(self, *, n: int = 32, variant: str = "textbook") -> Bloq:
        return _build_qft(n=int(n), variant=str(variant))

    def logical_costs(self, bloq: Bloq) -> LogicalCosts:
        return extract_logical_costs(bloq)

    def verify_small(
        self,
        *,
        n: int = 4,
        variant: str = "textbook",
    ) -> VerificationResult:
        """Verify the QFT unitary via ``tensor_contract`` for small *n*.

        For textbook QFT the unitary is compared against the analytic DFT
        matrix (up to global phase).  For approximate QFT only unitarity is
        checked — the circuit intentionally drops small-angle rotations.
        """
        n = int(n)
        if n > _MAX_VERIFY_N:
            return VerificationResult(
                passed=False,
                detail=f"n={n} too large for exact verification (max {_MAX_VERIFY_N})",
            )

        bloq = self.build_bloq(n=n, variant=variant)

        try:
            U = bloq.tensor_contract()
        except Exception as exc:
            return VerificationResult(
                passed=False, detail=f"tensor_contract failed: {exc}"
            )

        # ApproximateQFT uses ancilla qubits, so the matrix dimension can
        # exceed 2**n. Derive it from the actual tensor.
        dim = U.shape[0]

        if not np.allclose(U @ U.conj().T, np.eye(dim), atol=1e-6):
            return VerificationResult(passed=False, detail="Matrix is not unitary")

        if variant == "textbook":
            N = 1 << n
            omega = np.exp(2j * np.pi / N)
            jk = np.outer(np.arange(N), np.arange(N))
            F = omega**jk / np.sqrt(N)

            # Global-phase-invariant overlap: |tr(F† U)| / N ≈ 1.
            overlap = np.abs(np.trace(F.conj().T @ U)) / N
            if not np.isclose(overlap, 1.0, atol=1e-4):
                return VerificationResult(
                    passed=False,
                    detail=f"Unitary does not match DFT (overlap={overlap:.6f})",
                )

        detail = f"QFT({n}, {variant}): unitary OK ({dim}×{dim})"
        if variant == "textbook":
            detail += ", matches analytic DFT"
        return VerificationResult(passed=True, detail=detail)
