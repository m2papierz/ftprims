"""Physical resource landscape: all primitives x variants x params x configs.

Beverland-style log-log plot of physical_qubits vs wall_time with convex
hulls per primitive variant.

Output:
  results/charts/landscape.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import ConvexHull

from _style import PALETTE, apply_theme, light_grid, savefig
from ftprims.algorithms import registry
from ftprims.physical import PhysicalModelSpec, estimate_physical


CONFIGS = [
    dict(profile="gidney_fowler", data_block="simple", factory="ccz2t"),
    dict(profile="gidney_fowler", data_block="compact", factory="ccz2t"),
    dict(profile="gidney_fowler", data_block="fast", factory="ccz2t"),
    dict(profile="gidney_fowler", data_block="simple", factory="fifteen_to_one"),
    dict(profile="gidney_fowler", data_block="fast", factory="fifteen_to_one"),
    dict(profile="beverland", data_block="simple", factory="ccz2t"),
    dict(profile="beverland", data_block="fast", factory="ccz2t"),
    dict(profile="beverland", data_block="simple", factory="fifteen_to_one"),
    dict(profile="beverland", data_block="fast", factory="fifteen_to_one"),
]

# Each entry is a visually distinct region on the landscape.
DOMAINS: dict[str, dict] = {
    "QFT Textbook": {
        "cases": [("qft", dict(n=n, variant="textbook")) for n in [16, 32, 64, 128]],
        "color": PALETTE["blue"],
        "label_offset": (0.35, 0.15),
    },
    "QFT Approximate": {
        "cases": [("qft", dict(n=n, variant="approx")) for n in [8, 16, 32, 64, 128]],
        "color": PALETTE["teal"],
        "label_offset": (-0.05, -0.25),
    },
    "QPE": {
        "cases": [("qpe", dict(m=m, phi=0.25)) for m in [6, 8, 10, 12]],
        "color": PALETTE["orange"],
        "label_offset": (0.15, -0.28),
    },
    "Adder": {
        "cases": [("arithmetic", dict(n=n, op="add")) for n in [16, 32, 64, 128, 256]]
        + [("arithmetic", dict(n=n, op="add_oop")) for n in [16, 32, 64, 128, 256]],
        "color": PALETTE["green"],
        "label_offset": (-0.35, 0.2),
    },
    "Multiplier": {
        "cases": [("arithmetic", dict(n=n, op="mul")) for n in [8, 16, 32, 64]],
        "color": "#166534",  # dark green
        "label_offset": (0.35, 0.2),
    },
    "Comparator": {
        "cases": [("arithmetic", dict(n=n, op="leq")) for n in [16, 32, 64, 128, 256]],
        "color": "#6EE7B7",  # light green
        "label_offset": (-0.4, -0.15),
    },
    "QROM Basic": {
        "cases": [
            ("qrom", dict(data_size=N, variant="basic")) for N in [64, 256, 1024]
        ],
        "color": PALETTE["red"],
        "label_offset": (-0.25, 0.22),
    },
    "SelectSwapQROM": {
        "cases": [
            ("qrom", dict(data_size=N, variant="selectswap")) for N in [64, 256, 1024]
        ],
        "color": PALETTE["pink"],
        "label_offset": (-0.15, -0.2),
    },
}


def collect() -> dict[str, list[tuple[float, float]]]:
    results: dict[str, list[tuple[float, float]]] = {}
    for domain, spec in DOMAINS.items():
        points: list[tuple[float, float]] = []
        for name, params in spec["cases"]:
            bench = registry[name]
            bloq = bench.build_bloq(**params)
            costs = bench.logical_costs(bloq)
            if costs.t_count_ftqc == 0 and costs.rotation_count == 0:
                continue
            for cfg in CONFIGS:
                phys = estimate_physical(costs, spec=PhysicalModelSpec(**cfg))
                if phys.budget_satisfied and phys.wall_time_us > 0:
                    wall_s = phys.wall_time_us / 1_000_000
                    points.append((wall_s, phys.physical_qubits))
        results[domain] = points
        print(f"{domain:20s}: {len(points)} points")
    return results


def _hull_polygon(points: np.ndarray, pad_log: float = 0.06):
    log_pts = np.log10(points)
    if len(log_pts) < 3:
        return None
    try:
        hull = ConvexHull(log_pts)
    except Exception:
        return None
    verts = log_pts[hull.vertices]
    centroid = verts.mean(axis=0)
    dirs = verts - centroid
    norms = np.linalg.norm(dirs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    padded = verts + pad_log * dirs / norms
    padded = np.vstack([padded, padded[0]])
    return 10**padded


_TIME_MARKERS = [
    (1e-3, "ms"),
    (1, "second"),
    (60, "minute"),
    (3600, "hour"),
]


def plot(results: dict[str, list[tuple[float, float]]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 8.5))

    for domain, spec in DOMAINS.items():
        pts = results[domain]
        if not pts:
            continue
        color = spec["color"]
        arr = np.array(pts)
        xs, ys = arr[:, 0], arr[:, 1]

        ax.scatter(xs, ys, c=color, s=24, alpha=0.4, zorder=2, edgecolors="none")

        hull = _hull_polygon(arr)
        if hull is not None:
            ax.fill(hull[:, 0], hull[:, 1], color=color, alpha=0.10, zorder=1)
            ax.plot(hull[:, 0], hull[:, 1], color=color, alpha=0.40, lw=1.3, zorder=1)

        dx, dy = spec.get("label_offset", (0, 0))
        cx = 10 ** (np.log10(np.median(xs)) + dx)
        cy = 10 ** (np.log10(np.median(ys)) + dy)
        ax.text(
            cx,
            cy,
            domain,
            fontsize=10,
            fontweight="bold",
            color=color,
            alpha=0.9,
            ha="center",
            va="center",
            zorder=3,
            bbox=dict(
                boxstyle="round,pad=0.15",
                facecolor="white",
                alpha=0.75,
                edgecolor="none",
            ),
        )

    ax.set_xscale("log")
    ax.set_yscale("log")

    # Time reference lines.
    ylims = ax.get_ylim()
    for t_sec, label in _TIME_MARKERS:
        ax.axvline(t_sec, color="#D1D5DB", lw=0.7, ls=":", zorder=0)
        ax.text(
            t_sec * 1.08,
            ylims[1] * 0.85,
            label,
            fontsize=8,
            color="#9CA3AF",
            va="top",
            rotation=90,
            zorder=0,
        )

    ax.set_xlabel("Wall time (seconds)", fontsize=12)
    ax.set_ylabel("Physical qubits", fontsize=12)
    ax.set_title(
        "FTQC Primitive Resource Landscape",
        fontsize=15,
        fontweight="semibold",
        pad=14,
    )
    light_grid(ax, which="both")

    plt.tight_layout()
    savefig(fig, path)


def main() -> None:
    apply_theme()
    chart_dir = Path("results/charts")
    chart_dir.mkdir(parents=True, exist_ok=True)
    results = collect()
    plot(results, chart_dir / "landscape.png")


if __name__ == "__main__":
    main()
