"""Cost-coefficient regimes of modular exponentiation: Qualtran's stock ModExp
(flat) against GE19's windowed construction (falling as 1/lg^2n, ASSUMPTIONS.md
sec. 6), on one size grid. Writes results/charts/regime_identification.png."""

from __future__ import annotations

import math
from pathlib import Path
from typing import NamedTuple

import matplotlib.pyplot as plt

from _style import PALETTE, apply_theme, light_grid, savefig
from qrepro.references.ge19 import modexp_coefficient_series, reproduce_ge19_logical
from qrepro.references.ge19_windowed import reproduce_ge19_windowed
from qrepro.references.values import GE19, WINDOWED_COEFFICIENT_SIZES


class RegimeSeries(NamedTuple):
    """Both measured n_ccz/(n_e*n^2) series over WINDOWED_COEFFICIENT_SIZES,
    plus the count ratio between the two constructions at GE19's n."""

    modexp: tuple[tuple[int, float], ...]
    windowed: tuple[tuple[int, float], ...]
    gap: float


def collect() -> RegimeSeries:
    """Measure both constructions on one domain, so the regimes are comparable
    (their pinned defaults differ: ModExp's own grid stops at n=2048)."""
    windowed = reproduce_ge19_windowed()
    logical = reproduce_ge19_logical()
    n_ref = GE19["n"]
    series = RegimeSeries(
        modexp=modexp_coefficient_series(WINDOWED_COEFFICIENT_SIZES),
        windowed=windowed.coefficient_series,
        gap=logical.modexp_ccz_count / windowed.by_n(n_ref).total_ccz,
    )
    print(f"n={n_ref}: windowed is {series.gap:.1f}x cheaper than stock ModExp")
    return series


def plot(series: RegimeSeries, *paths: Path) -> None:
    """Draw both series on one log-log axis with the 1/lg^2n asymptote."""
    fig, ax = plt.subplots(figsize=(8, 5.2))

    ns, cs = zip(*series.modexp)
    ax.plot(ns, cs, "o-", color=PALETTE["red"], ms=6, lw=2)
    wn, wc = zip(*series.windowed)
    ax.plot(wn, wc, "o-", color=PALETTE["blue"], ms=6, lw=2)

    # 1/lg^2n reference anchored at the large-n end, so it reads as the
    # asymptote; subleading terms stay visible at small n, as in the tables.
    scale = wc[-1] * math.log2(wn[-1]) ** 2
    reference = [scale / math.log2(n) ** 2 for n in wn]
    ax.plot(wn, reference, "--", color=PALETTE["gray"], lw=1.6)

    # Series labels in place of a legend; anchors are hand-placed against the
    # pinned size grid.
    ax.annotate(
        "Qualtran ModExp\n"
        r"constant $\approx 10$ (reference, non-windowed construction)",
        xy=(132, 6.6),
        color=PALETTE["red"],
        fontsize=10,
        va="top",
    )
    ax.annotate(
        "WindowedModExp\n" r"falls as $1/\lg^2 n$ (windowed construction)",
        xy=(560, 0.42),
        color=PALETTE["blue"],
        fontsize=10,
    )
    ax.annotate(
        r"$\propto 1/\lg^2 n$",
        xy=(136, 0.212),
        color=PALETTE["gray"],
        fontsize=9.5,
    )

    # Gap callout: a double arrow spanning the two series at GE19's n.
    n_ref = GE19["n"]
    top = dict(series.modexp)[n_ref] * 0.86
    bottom = dict(series.windowed)[n_ref] * 1.15
    ax.annotate(
        "",
        xy=(n_ref, bottom),
        xytext=(n_ref, top),
        arrowprops=dict(arrowstyle="<->", color=PALETTE["dark_gray"], lw=1.2),
    )
    ax.annotate(
        f"{series.gap:.0f}x at n = {n_ref}",
        xy=(n_ref * 1.15, math.sqrt(top * bottom)),  # beside the arrow's midpoint
        fontsize=10,
        color=PALETTE["dark_gray"],
    )

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("modulus size n (bits)")
    ax.set_ylabel(r"$n_{ccz} \, / \, (n_e \cdot n^2)$")
    ax.set_title("Modular exponentiation: measured cost coefficient vs modulus size")
    light_grid(ax, which="major")
    ax.set_ylim(0.06, 14)  # headroom for the labels above and below the series
    savefig(fig, *paths)


def main() -> None:
    apply_theme()
    chart_dir = Path("results/charts")
    chart_dir.mkdir(parents=True, exist_ok=True)
    plot(collect(), chart_dir / "regime_identification.png")


if __name__ == "__main__":
    main()
