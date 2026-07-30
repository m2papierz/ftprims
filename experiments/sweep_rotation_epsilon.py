"""Sweep rotation-synthesis epsilon against QFT T-equivalent counts; the
approximate QFT has no arbitrary-angle rotations, so the textbook/approx ratio
measures synthesis cost alone (ASSUMPTIONS.md §2).

Writes results/sweeps/sweep_rotation_epsilon.csv and
results/charts/rotation_epsilon.png.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from _style import FIG_DUAL, PALETTE, apply_theme, light_grid, savefig
from qrepro.algorithms import registry
from qrepro.resource import rotation_synthesis_t_cost

EPSILONS = [1e-3, 1e-6, 1e-8, 1e-10, 1e-12, 1e-15]
BITSIZES = [8, 16, 32, 64, 128]
CHART_N = 32


def qualtran_default_row(n: int) -> dict:
    """Textbook/approx T-equivalent at Qualtran's default precision (~11 T/rot)."""
    from qualtran.bloqs.qft.approximate_qft import ApproximateQFT
    from qualtran.bloqs.qft.qft_text_book import QFTTextBook
    from qualtran.resource_counting import QECGatesCost, get_cost_value

    tb = get_cost_value(QFTTextBook(bitsize=n), QECGatesCost())
    ap = get_cost_value(ApproximateQFT(bitsize=n, phase_bitsize=n // 2), QECGatesCost())
    tb_c = tb.total_t_and_ccz_count()
    ap_c = ap.total_t_and_ccz_count()
    tb_t = tb_c["n_t"] + 4 * tb_c["n_ccz"]
    ap_t = ap_c["n_t"] + 4 * ap_c["n_ccz"]
    rotations = int(tb.rotation)
    direct = int(tb.t) + 4 * int(tb.and_bloq)
    return {
        "n": n,
        "epsilon": "qualtran_default",
        "t_per_rotation": round((tb_t - direct) / rotations, 3) if rotations else 0,
        "textbook_t_equiv": tb_t,
        "approx_t_equiv": ap_t,
        "ratio": round(tb_t / ap_t, 3) if ap_t else 0,
        "textbook_rotations": rotations,
    }


def collect(bench) -> list[dict]:
    rows: list[dict] = []
    for n in BITSIZES:
        rows.append(qualtran_default_row(n))
        for eps in EPSILONS:
            tb = bench.logical_costs(
                bench.build_bloq(n=n, variant="textbook"),
                rotation_synthesis_epsilon=eps,
            )
            ap = bench.logical_costs(
                bench.build_bloq(n=n, variant="approx"),
                rotation_synthesis_epsilon=eps,
            )
            rows.append(
                {
                    "n": n,
                    "epsilon": eps,
                    "t_per_rotation": rotation_synthesis_t_cost(eps),
                    "textbook_t_equiv": tb.t_count_ftqc,
                    "approx_t_equiv": ap.t_count_ftqc,
                    "ratio": (
                        round(tb.t_count_ftqc / ap.t_count_ftqc, 3)
                        if ap.t_count_ftqc
                        else 0
                    ),
                    "textbook_rotations": tb.rotation_count,
                }
            )
    for r in rows:
        print(
            f"n={r['n']:4d}  eps={str(r['epsilon']):>17s}  "
            f"T/rot={r['t_per_rotation']:>7}  "
            f"TB={r['textbook_t_equiv']:>10,}  AP={r['approx_t_equiv']:>9,}  "
            f"ratio={r['ratio']:>7}x"
        )
    return rows


def save_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {path}")


def plot(rows: list[dict], path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_DUAL)

    numeric = [r for r in rows if r["epsilon"] != "qualtran_default"]

    # Left: ratio vs epsilon at the charted bitsize.
    subset = sorted(
        (r for r in numeric if r["n"] == CHART_N), key=lambda r: r["epsilon"]
    )
    eps = [r["epsilon"] for r in subset]
    ratios = [r["ratio"] for r in subset]
    ax1.semilogx(eps, ratios, "o-", color=PALETTE["green"])
    for x, y in zip(eps, ratios):
        ax1.annotate(
            f"{y:.1f}×",
            (x, y),
            textcoords="offset points",
            xytext=(0, 9),
            ha="center",
            fontsize=8,
            color=PALETTE["green"],
            fontweight="bold",
        )
    qd = next(
        r for r in rows if r["n"] == CHART_N and r["epsilon"] == "qualtran_default"
    )
    ax1.axhline(
        y=qd["ratio"],
        color=PALETTE["red"],
        linestyle="--",
        alpha=0.8,
        label=f"Qualtran default ({qd['ratio']:.1f}×)",
    )
    ax1.set_xlabel("Rotation synthesis ε")
    ax1.set_ylabel("Textbook / Approximate T-equivalent")
    ax1.set_title(f"QFT(n={CHART_N}): textbook/approx ratio vs ε")
    ax1.legend(fontsize=9)
    light_grid(ax1, which="both")

    # Right: textbook T-equivalent vs n, one line per epsilon.
    for eps_val in EPSILONS:
        sub = sorted(
            (r for r in numeric if r["epsilon"] == eps_val), key=lambda r: r["n"]
        )
        ax2.loglog(
            [r["n"] for r in sub],
            [r["textbook_t_equiv"] for r in sub],
            "o-",
            label=f"ε={eps_val:g}",
            alpha=0.9,
        )
    ax2.set_xlabel("Bitsize (n)")
    ax2.set_ylabel("Textbook QFT T-equivalent")
    ax2.set_title("Textbook QFT T-equivalent vs n, per ε")
    ax2.legend(fontsize=8)
    light_grid(ax2, which="both")

    plt.tight_layout()
    savefig(fig, path)


def main() -> None:
    apply_theme()
    csv_dir = Path("results/sweeps")
    chart_dir = Path("results/charts")
    csv_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)

    rows = collect(registry["qft"])
    save_csv(rows, csv_dir / "sweep_rotation_epsilon.csv")
    plot(rows, chart_dir / "rotation_epsilon.png")


if __name__ == "__main__":
    main()
