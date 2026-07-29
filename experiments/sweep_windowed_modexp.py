"""Sweep GE19's windowed modexp over the window grid and over modulus size.

CSV panels: ``window_grid`` (whole grid at n=2048), ``falloff``
(``n_ccz/(n_e·n²)`` at the per-n cost argmin), ``default_window`` (argmin vs
GE19 L690's published ``(5, 5)``, per tabulated n). Conventions: ASSUMPTIONS.md §6.

Outputs:
  results/sweeps/sweep_windowed_modexp.csv
  results/charts/windowed_modexp_sweep.png
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt

from _style import FIG_DUAL, PALETTE, apply_theme, light_grid, savefig
from ftprims.algorithms.windowed_factoring import (
    ge19_exponent_bitsize,
    make_ge19_windowed_modexp,
    windowed_term_breakdown,
)
from ftprims.references.ge19_windowed import WINDOW_GRID, windowed_best_window
from ftprims.references.values import GE19, GE19_WINDOWED, WINDOWED_COEFFICIENT_SIZES

GRID_N = GE19["n"]  # 2048
GE19_DEFAULT_WINDOW = (GE19_WINDOWED["exp_window"], GE19_WINDOWED["mul_window"])

#: Sizes GE19 tabulates in Table 1, i.e. the sizes the reproduction reports.
TABULATED_SIZES = (1024, 2048, 3072)


def _total_ccz(n: int, we: int, wm: int) -> int:
    return windowed_term_breakdown(
        make_ge19_windowed_modexp(n, exp_window=we, mul_window=wm)
    ).total_ccz


def collect() -> tuple[list[dict], list[dict], list[dict]]:
    """Window-grid rows at n=2048, the falloff series, and the default-window
    comparison at every size GE19 tabulates."""
    grid_rows: list[dict] = []
    for we, wm in WINDOW_GRID:
        bloq = make_ge19_windowed_modexp(GRID_N, exp_window=we, mul_window=wm)
        terms = windowed_term_breakdown(bloq)
        total = terms.total_ccz
        grid_rows.append(
            dict(
                n=GRID_N,
                exp_window=we,
                mul_window=wm,
                lookup_bits=we + wm,
                table_entries=2 ** (we + wm),
                total_ccz=total,
                adder_ccz=terms.adder_ccz,
                lookup_ccz=terms.lookup_ccz,
                unlookup_ccz=terms.unlookup_ccz,
                adder_share=round(terms.adder_ccz / total, 4),
                lookup_share=round(terms.lookup_ccz / total, 4),
                unlookup_share=round(terms.unlookup_ccz / total, 4),
                bridged_ccz=terms.adder_bridged_total_ccz,
                ratio_vs_table1=round(
                    total / (GE19["table1_toffoli_billions"]["n2048"] * 1e9), 4
                ),
            )
        )

    falloff_rows: list[dict] = []
    for n in WINDOWED_COEFFICIENT_SIZES:
        we, wm = windowed_best_window(n)
        ne = ge19_exponent_bitsize(n)
        total = windowed_term_breakdown(
            make_ge19_windowed_modexp(n, exp_window=we, mul_window=wm)
        ).total_ccz
        coeff = total / (ne * n**2)
        falloff_rows.append(
            dict(
                n=n,
                exp_bitsize=ne,
                best_exp_window=we,
                best_mul_window=wm,
                total_ccz=total,
                coefficient=round(coeff, 6),
                coefficient_times_lg2n=round(coeff * math.log2(n) ** 2, 4),
            )
        )

    default_rows: list[dict] = []
    for n in TABULATED_SIZES:
        table1 = GE19["table1_toffoli_billions"][f"n{n}"] * 1e9
        best_we, best_wm = windowed_best_window(n)
        argmin_total = _total_ccz(n, best_we, best_wm)
        default_total = _total_ccz(n, *GE19_DEFAULT_WINDOW)
        default_rows.append(
            dict(
                n=n,
                exp_window=GE19_DEFAULT_WINDOW[0],
                mul_window=GE19_DEFAULT_WINDOW[1],
                total_ccz=default_total,
                ratio_vs_table1=round(default_total / table1, 4),
                best_exp_window=best_we,
                best_mul_window=best_wm,
                argmin_total_ccz=argmin_total,
                argmin_ratio_vs_table1=round(argmin_total / table1, 4),
            )
        )
    return grid_rows, falloff_rows, default_rows


def write_csv(
    grid_rows: list[dict],
    falloff_rows: list[dict],
    default_rows: list[dict],
    path: Path,
) -> None:
    """One CSV holding all three panels, tagged by a `panel` column."""
    every = grid_rows + falloff_rows + default_rows
    fields = sorted({k for r in every for k in r} | {"panel"})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in grid_rows:
            writer.writerow({**row, "panel": "window_grid"})
        for row in falloff_rows:
            writer.writerow({**row, "panel": "falloff"})
        for row in default_rows:
            writer.writerow({**row, "panel": "default_window"})
    print(f"Saved {path}")


def plot(grid_rows: list[dict], falloff_rows: list[dict], path: Path) -> None:
    apply_theme()
    fig, (ax_grid, ax_fall) = plt.subplots(1, 2, figsize=FIG_DUAL)

    # ── Panel 1: cost vs window, one line per w_e ─────────────────────────────
    by_we: dict[int, list[dict]] = {}
    for row in grid_rows:
        by_we.setdefault(row["exp_window"], []).append(row)
    colours = list(PALETTE.values())
    for i, we in enumerate(sorted(by_we)):
        rows = sorted(by_we[we], key=lambda r: r["mul_window"])
        ax_grid.plot(
            [r["mul_window"] for r in rows],
            [r["total_ccz"] / 1e9 for r in rows],
            marker="o",
            color=colours[i % len(colours)],
            label=f"$w_e$={we}",
        )
    best = min(grid_rows, key=lambda r: r["total_ccz"])
    ax_grid.scatter(
        [best["mul_window"]],
        [best["total_ccz"] / 1e9],
        s=220,
        facecolors="none",
        edgecolors=PALETTE["red"],
        linewidths=2,
        zorder=5,
        label=f"minimum ({best['exp_window']}, {best['mul_window']})",
    )
    ax_grid.set_yscale("log")
    ax_grid.set_xlabel("multiplication window $w_m$")
    ax_grid.set_ylabel("magic states (billion CCZ)")
    ax_grid.set_title(
        f"Window grid at n={GRID_N}\n"
        f"minimum at {GE19_DEFAULT_WINDOW} = GE19's own default (L690)"
    )
    ax_grid.legend(ncol=2)
    light_grid(ax_grid)

    # ── Panel 2: the 1/lg²n falloff ──────────────────────────────────────────
    ns = [r["n"] for r in falloff_rows]
    coeffs = [r["coefficient"] for r in falloff_rows]
    ax_fall.plot(
        ns, coeffs, marker="o", color=PALETTE["blue"], label="windowed (measured)"
    )
    # The non-windowed regime is a constant (ASSUMPTIONS.md §3).
    reference = GE19["modexp_qualtran_toffoli"] / ((2 * GRID_N) * GRID_N**2)
    ax_fall.axhline(
        reference,
        color=PALETTE["gray"],
        linestyle="--",
        label=f"non-windowed ModExp = {reference:.1f} (constant)",
    )
    ax_fall.set_xscale("log", base=2)
    ax_fall.set_yscale("log")
    ax_fall.set_xlabel("modulus bits $n$")
    ax_fall.set_ylabel(r"$n_{ccz} / (n_e \cdot n^2)$")
    ax_fall.set_title(
        "Regime identification\n"
        r"windowed $\sim 1/\lg^2 n$; non-windowed is constant"
    )
    ax_fall.legend()
    light_grid(ax_fall)

    fig.tight_layout()
    savefig(fig, path)


def main() -> None:
    results = Path("results")
    (results / "sweeps").mkdir(parents=True, exist_ok=True)
    (results / "charts").mkdir(parents=True, exist_ok=True)

    grid_rows, falloff_rows, default_rows = collect()
    write_csv(
        grid_rows,
        falloff_rows,
        default_rows,
        results / "sweeps" / "sweep_windowed_modexp.csv",
    )
    plot(grid_rows, falloff_rows, results / "charts" / "windowed_modexp_sweep.png")

    best = min(grid_rows, key=lambda r: r["total_ccz"])
    print(
        f"\nCost minimum at n={GRID_N}: "
        f"(w_e, w_m) = ({best['exp_window']}, {best['mul_window']}), "
        f"{best['total_ccz'] / 1e9:.4f}e9 CCZ"
    )
    print(f"GE19 published default (L690): {GE19_DEFAULT_WINDOW}")

    print("\nargmin window vs GE19's published (5, 5), per tabulated n:")
    for row in default_rows:
        print(
            f"  n={row['n']:5d}  argmin ({row['best_exp_window']}, "
            f"{row['best_mul_window']}) = {row['argmin_ratio_vs_table1']:.4f} x Table 1"
            f"   |   (5, 5) = {row['ratio_vs_table1']:.4f} x Table 1"
        )


if __name__ == "__main__":
    main()
