"""QFT benchmark."""

from __future__ import annotations

from qualtran import Bloq

from ftprims.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)


@register
class QFTBenchmark(Benchmark):
    name = "qft"

    def build_bloq(
        self,
        *,
        n: int,
        variant: str,
    ) -> Bloq: ...

    def logical_costs(self, bloq: Bloq) -> LogicalCosts: ...

    def verify_small(
        self,
        *,
        n: int,
    ) -> VerificationResult: ...
