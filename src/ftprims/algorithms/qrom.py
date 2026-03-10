"""QROM / SelectSwapQROM benchmark."""

from __future__ import annotations

from qualtran import Bloq

from ftprims.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)


__all__ = ["QROMBenchmark"]


@register
class QROMBenchmark(Benchmark):
    name = "qrom"

    def build_bloq(
        self,
        *,
        data_size: int,
        target_bitsizes: tuple[int, ...] = (8,),
        variant: str = "basic",
        k: int = 1,
    ) -> Bloq: ...

    def logical_costs(self, bloq: Bloq) -> LogicalCosts: ...

    def verify_small(
        self,
        *,
        data_size: int,
        target_bitsizes: tuple[int, ...] = (8,),
    ) -> VerificationResult: ...
