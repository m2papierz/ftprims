"""QROM benchmark: basic QROM and SelectSwapQROM.

Quantum Read-Only Memory is a central primitive in FTQC algorithms:
state preparation, SELECT oracles, quantum chemistry. SelectSwapQROM
trades ancilla qubits for fewer T-gates, controlled by ``log_block_sizes``.
"""

from __future__ import annotations

import numpy as np
from qualtran import Bloq
from qualtran.bloqs.data_loading.qrom import QROM
from qualtran.bloqs.data_loading.select_swap_qrom import SelectSwapQROM

from ftprims.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)
from ftprims.resource import extract_logical_costs


__all__ = ["QROMBenchmark"]

_VARIANTS = {"basic", "selectswap"}
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
    log_block_sizes: int | None = None,
) -> Bloq:
    """Construct a QROM or SelectSwapQROM bloq.

    Parameters
    ----------
    data_size:
        Number of entries in the lookup table (must be ≥ 2).
    target_bitsize:
        Bit-width of each output value.
    variant:
        ``"basic"`` for QROM or ``"selectswap"`` for SelectSwapQROM.
    log_block_sizes:
        Block-size exponent for SelectSwapQROM (controls the T-gates
        vs ancilla trade-off).  Ignored for basic QROM.
    """
    if variant not in _VARIANTS:
        raise ValueError(
            f"Unknown QROM variant {variant!r}; choose from {sorted(_VARIANTS)}"
        )
    if data_size < 2:
        raise ValueError(f"data_size must be ≥ 2, got {data_size}")
    if target_bitsize < 1:
        raise ValueError(f"target_bitsize must be ≥ 1, got {target_bitsize}")

    data = _generate_data(data_size, target_bitsize)

    if variant == "basic":
        return QROM.build_from_data(data, target_bitsizes=(target_bitsize,))

    kwargs: dict = {"target_bitsizes": (target_bitsize,)}
    if log_block_sizes is not None:
        kwargs["log_block_sizes"] = (int(log_block_sizes),)
    return SelectSwapQROM.build_from_data(data, **kwargs)


@register
class QROMBenchmark(Benchmark):
    """Benchmark wrapper for Quantum Read-Only Memory."""

    name = "qrom"

    def build_bloq(
        self,
        *,
        data_size: int = 256,
        target_bitsize: int = 8,
        variant: str = "basic",
        log_block_sizes: int | None = None,
    ) -> Bloq:
        return _build_qrom(
            data_size=int(data_size),
            target_bitsize=int(target_bitsize),
            variant=str(variant),
            log_block_sizes=(
                int(log_block_sizes) if log_block_sizes is not None else None
            ),
        )

    def logical_costs(self, bloq: Bloq) -> LogicalCosts:
        return extract_logical_costs(bloq)

    def verify_small(
        self,
        *,
        data_size: int = 8,
        target_bitsize: int = 4,
        variant: str = "basic",
        log_block_sizes: int | None = None,
    ) -> VerificationResult:
        """Verify QROM via ``call_classically`` on every table entry."""
        data_size = int(data_size)
        if data_size > _MAX_VERIFY_DATA_SIZE:
            return VerificationResult(
                passed=False,
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
            log_block_sizes=log_block_sizes,
        )

        for sel in range(data_size):
            try:
                result = bloq.call_classically(selection=sel, target0_=0)
            except Exception as exc:
                return VerificationResult(
                    passed=False,
                    detail=f"call_classically(sel={sel}) failed: {exc}",
                )

            # Map positional results to register names for robustness.
            reg_names = [reg.name for reg in bloq.signature]
            result_dict = dict(zip(reg_names, result))
            actual = int(result_dict["target0_"])
            if actual != data[sel]:
                return VerificationResult(
                    passed=False,
                    detail=(
                        f"Mismatch at sel={sel}: expected={data[sel]} got={actual}"
                    ),
                )

        return VerificationResult(
            passed=True,
            detail=(
                f"QROM({variant}, N={data_size}, bits={target_bitsize}): "
                f"all {data_size} entries OK"
            ),
        )
