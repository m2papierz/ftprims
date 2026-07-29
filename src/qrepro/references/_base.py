"""The comparison-table row every reproduction exposes as ``.rows``.

Tests assert the typed fields, the notebook renders them and the CLI prints
them, so no reproduced number is computed in more than one place.
"""

from __future__ import annotations

import attrs


@attrs.define(frozen=True)
class ReproductionRow:
    """One line of a reproduction comparison table.

    ``reproduced`` is the qrepro number and ``target`` the paper value, or
    ``None`` where there is no single paper target. ``deviation`` is
    ``(reproduced - target) / target`` when both are present.
    """

    label: str
    metric: str
    reproduced: float
    target: float | None = None
    deviation: float | None = None

    @classmethod
    def make(
        cls,
        label: str,
        metric: str,
        reproduced: float,
        target: float | None = None,
    ) -> "ReproductionRow":
        deviation = None
        if target is not None and target != 0:
            deviation = (reproduced - target) / target
        return cls(
            label=label,
            metric=metric,
            reproduced=reproduced,
            target=target,
            deviation=deviation,
        )
