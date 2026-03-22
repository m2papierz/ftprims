"""Compare physical model configurations for a given primitive.

Runs one primitive with fixed parameters across multiple physical
presets and produces a CSV + scatter plot of physical_qubits vs
wall_time_us.

Outputs:
  results/compare_physical.csv
  results/chart_physical_compare.png

Usage:
  python experiments/compare_physical_configs.py [PRIMITIVE] [PARAMS...]

Example:
  python experiments/compare_physical_configs.py qft n=16 variant=textbook
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from ftprims.algorithms import registry
from ftprims.physical import PhysicalModelSpec, estimate_physical


PRESETS: list[dict[str, str]] = [
    {"profile": "gidney_fowler", "data_block": "simple", "factory": "ccz2t"},
    {"profile": "gidney_fowler", "data_block": "compact", "factory": "ccz2t"},
    {"profile": "gidney_fowler", "data_block": "fast", "factory": "ccz2t"},
    {"profile": "gidney_fowler", "data_block": "simple", "factory": "fifteen_to_one"},
    {"profile": "gidney_fowler", "data_block": "fast", "factory": "fifteen_to_one"},
    {"profile": "beverland", "data_block": "simple", "factory": "ccz2t"},
    {"profile": "beverland", "data_block": "fast", "factory": "ccz2t"},
    {"profile": "beverland", "data_block": "simple", "factory": "fifteen_to_one"},
    {"profile": "beverland", "data_block": "fast", "factory": "fifteen_to_one"},
]

# Short labels for chart annotations: "profile data_block factory"
# abbreviated to single letters where possible.
_PROFILE_SHORT = {"gidney_fowler": "GF", "beverland": "Bev"}
_BLOCK_SHORT = {"simple": "S", "compact": "C", "fast": "F"}
_FACTORY_SHORT = {"ccz2t": "ccz2t", "fifteen_to_one": "15→1"}


def _short_label(r: dict) -> str:
    return (
        f"{_PROFILE_SHORT.get(r['profile'], r['profile'])}/"
        f"{_BLOCK_SHORT.get(r['data_block'], r['data_block'])}/"
        f"{_FACTORY_SHORT.get(r['factory'], r['factory'])}"
    )


def _parse_params(args: list[str]) -> dict[str, int | float | str]:
    params: dict[str, int | float | str] = {}
    for item in args:
        k, _, v = item.partition("=")
        try:
            params[k] = int(v)
        except ValueError:
            try:
                params[k] = float(v)
            except ValueError:
                params[k] = v
    return params


def collect(primitive: str, params: dict) -> list[dict]:
    bench = registry[primitive]
    bloq = bench.build_bloq(**params)
    logical = bench.logical_costs(bloq)

    rows: list[dict] = []
    for preset in PRESETS:
        spec = PhysicalModelSpec(**preset)
        phys = estimate_physical(logical, spec=spec)
        label = f"{preset['profile']}/{preset['data_block']}/{preset['factory']}"
        rows.append(
            {
                "label": label,
                "profile": phys.profile,
                "data_block": phys.data_block,
                "factory": phys.factory,
                "physical_qubits": phys.physical_qubits,
                "wall_time_us": phys.wall_time_us,
                "code_distance": phys.code_distance,
                "failure_prob": phys.failure_prob,
                "budget_satisfied": phys.budget_satisfied,
            }
        )
        ok = "✓" if phys.budget_satisfied else "✗"
        print(
            f"  {ok} {label:45s}  "
            f"q={phys.physical_qubits:>10,}  "
            f"t={phys.wall_time_us:>14,.0f}µs  "
            f"d={phys.code_distance}"
        )
    return rows


def save_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {path}")


def plot_scatter(rows: list[dict], primitive: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 7))

    for idx, r in enumerate(rows):
        color = "#2ecc71" if r["budget_satisfied"] else "#e74c3c"
        marker = "o" if r["factory"] == "ccz2t" else "^"
        ax.scatter(
            r["physical_qubits"],
            r["wall_time_us"],
            c=color,
            marker=marker,
            s=140,
            edgecolors="black",
            linewidths=0.5,
            zorder=3,
        )
        # Indexed label — compact, no overlap.
        ax.annotate(
            str(idx + 1),
            (r["physical_qubits"], r["wall_time_us"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=8,
            fontweight="bold",
        )

    ax.set_xlabel("Physical qubits")
    ax.set_ylabel("Wall time (µs)")
    ax.set_title(f"Physical Config Comparison: {primitive}")
    ax.grid(True, alpha=0.3)

    # Legend: shape/color semantics.
    legend_elements = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#2ecc71",
            markersize=10,
            markeredgecolor="black",
            label="budget met",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#e74c3c",
            markersize=10,
            markeredgecolor="black",
            label="budget NOT met",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="gray",
            markersize=10,
            markeredgecolor="black",
            label="ccz2t",
        ),
        Line2D(
            [0],
            [0],
            marker="^",
            color="w",
            markerfacecolor="gray",
            markersize=10,
            markeredgecolor="black",
            label="fifteen_to_one",
        ),
    ]
    ax.legend(handles=legend_elements, fontsize=8, loc="upper left")

    # Table below chart: index → config label + key numbers.
    table_lines = []
    for idx, r in enumerate(rows):
        short = _short_label(r)
        ok = "✓" if r["budget_satisfied"] else "✗"
        table_lines.append(
            f"  {idx + 1:2d}. {short:18s}  "
            f"q={r['physical_qubits']:>9,}  "
            f"t={r['wall_time_us']:>12,.0f}µs  "
            f"d={r['code_distance']}  {ok}"
        )

    table_text = "\n".join(table_lines)
    fig.text(
        0.05,
        -0.02,
        table_text,
        fontsize=7,
        fontfamily="monospace",
        verticalalignment="top",
    )

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def main() -> None:
    if len(sys.argv) < 2:
        primitive = "qft"
        params = {"n": 16, "variant": "textbook"}
    else:
        primitive = sys.argv[1]
        params = _parse_params(sys.argv[2:])

    print(f"Comparing physical configs for {primitive} with {params}\n")

    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)

    rows = collect(primitive, params)
    save_csv(rows, out_dir / "compare_physical.csv")
    plot_scatter(rows, primitive, out_dir / "chart_physical_compare.png")


if __name__ == "__main__":
    main()
