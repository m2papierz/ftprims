"""QROM benchmark: unary-iteration ``QROM`` over a random lookup table."""

from __future__ import annotations

import numpy as np
from qualtran import Bloq
from qualtran.bloqs.data_loading.qrom import QROM

from qrepro.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)
from qrepro.resource import extract_logical_costs

__all__ = ["QROMBenchmark"]

_VARIANTS = {"basic"}
_MAX_VERIFY_DATA_SIZE = 32
_RNG_SEED = 42


def _generate_data(data_size: int, target_bitsize: int) -> tuple[int, ...]:
    """Deterministic random lookup table fitting in *target_bitsize* bits."""
    rng = np.random.default_rng(_RNG_SEED)
    return tuple(int(x) for x in rng.integers(0, 1 << target_bitsize, size=data_size))


def _build_qrom(
    *,
    data_size: int,
    target_bitsize: int = 8,
    variant: str = "basic",
) -> Bloq:
    """Construct a ``QROM`` bloq.

    *data_size* is the number of table entries and must be a power of two >= 2.
    """
    if variant not in _VARIANTS:
        raise ValueError(
            f"Unknown QROM variant {variant!r}; choose from {sorted(_VARIANTS)}"
        )
    if data_size < 2:
        raise ValueError(f"data_size must be >= 2, got {data_size}")
    if data_size & (data_size - 1):
        raise ValueError(f"data_size must be a power of two, got {data_size}")
    if target_bitsize < 1:
        raise ValueError(f"target_bitsize must be >= 1, got {target_bitsize}")

    data = _generate_data(data_size, target_bitsize)
    return QROM.build_from_data(data, target_bitsizes=(target_bitsize,))


@register
class QROMBenchmark(Benchmark):
    """Quantum read-only memory."""

    name = "qrom"

    def build_bloq(
        self,
        *,
        data_size: int = 256,
        target_bitsize: int = 8,
        variant: str = "basic",
    ) -> Bloq:
        return _build_qrom(
            data_size=int(data_size),
            target_bitsize=int(target_bitsize),
            variant=str(variant),
        )

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

    def verify_small(
        self,
        *,
        data_size: int = 8,
        target_bitsize: int = 4,
        variant: str = "basic",
    ) -> VerificationResult:
        """Verify QROM via ``call_classically`` on every table entry."""
        data_size = int(data_size)
        if data_size > _MAX_VERIFY_DATA_SIZE:
            return VerificationResult(
                status="skip",
                detail=(
                    f"data_size={data_size} too large for verification "
                    f"(max {_MAX_VERIFY_DATA_SIZE})"
                ),
            )

        target_bitsize = int(target_bitsize)
        data = _generate_data(data_size, target_bitsize)
        bloq = self.build_bloq(
            data_size=data_size,
            target_bitsize=target_bitsize,
            variant=variant,
        )

        for sel in range(data_size):
            try:
                result = bloq.call_classically(selection=sel, target0_=0)
            except Exception as exc:
                return VerificationResult(
                    status="fail",
                    detail=f"call_classically(sel={sel}) failed: {exc}",
                )

            reg_names = [reg.name for reg in bloq.signature]
            result_dict = dict(zip(reg_names, result))
            actual = int(result_dict["target0_"])
            if actual != data[sel]:
                return VerificationResult(
                    status="fail",
                    detail=(
                        f"Mismatch at sel={sel}: expected={data[sel]} got={actual}"
                    ),
                )

        return VerificationResult(
            status="pass",
            detail=(
                f"QROM({variant}, N={data_size}, bits={target_bitsize}): "
                f"all {data_size} entries OK"
            ),
        )
