"""Log-log plot of physical_qubits vs wall_time with convex hulls per primitive
variant, over every primitive x variant x param x surface-code config. Writes
results/charts/landscape.png and the repo-root landscape.png the README embeds."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from scipy.spatial import ConvexHull

from _style import apply_theme, light_grid, savefig

# Full 2 x 3 x 2 product: 12 configurations.
PROFILES = ("gidney_fowler", "beverland")
DATA_BLOCKS = ("simple", "compact", "fast")
FACTORIES = ("ccz2t", "fifteen_to_one")

CONFIGS = [
    dict(profile=p, data_block=d, factory=f)
    for p in PROFILES
    for d in DATA_BLOCKS
    for f in FACTORIES
]

# Visually distinct domains: colour and marker per primitive variant.
DOMAINS: dict[str, dict] = {
    "QFT Textbook": {
        "cases": [("qft", dict(n=n, variant="textbook")) for n in [16, 32, 64, 128]],
        "color": "#2563EB",  # blue
        "marker": "o",
    },
    "QFT Approximate": {
        "cases": [("qft", dict(n=n, variant="approx")) for n in [8, 16, 32, 64, 128]],
        "color": "#0891B2",  # cyan
        "marker": "D",
    },
    "QPE": {
        "cases": [("qpe", dict(m=m, phi=0.25)) for m in [6, 8, 10, 12]],
        "color": "#D97706",  # amber
        "marker": "^",
    },
    "Adder": {
        "cases": [
            ("arithmetic", dict(n=n, op=op))
            for op in ("add", "add_oop")
            for n in [16, 32, 64, 128, 256]
        ],
        "color": "#059669",  # emerald
        "marker": "s",
    },
    "Multiplier": {
        "cases": [("arithmetic", dict(n=n, op="mul")) for n in [8, 16, 32, 64]],
        "color": "#7C3AED",  # violet
        "marker": "P",
    },
    "Comparator": {
        "cases": [("arithmetic", dict(n=n, op="leq")) for n in [16, 32, 64, 128, 256]],
        "color": "#E11D48",  # rose
        "marker": "v",
    },
    "QROM Basic": {
        "cases": [
            ("qrom", dict(data_size=N, variant="basic")) for N in [64, 256, 1024]
        ],
        "color": "#DC2626",  # red
        "marker": "h",
    },
}


def collect() -> dict[str, list[tuple[float, float]]]:
    from qrepro.algorithms import registry
    from qrepro.physical import PhysicalModelSpec, estimate_physical

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


def _hull_polygon(
    points: np.ndarray,
    pad_log: float = 0.04,
) -> np.ndarray | None:
    """Convex hull in log-space with small outward padding."""
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
    (1e-3, "1 ms"),
    (1, "1 s"),
    (60, "1 min"),
    (3600, "1 h"),
]


def plot(results: dict[str, list[tuple[float, float]]], *paths: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 8.5))

    legend_handles: list[Line2D] = []

    all_xs: list[float] = []
    all_ys: list[float] = []

    for domain, spec in DOMAINS.items():
        pts = results.get(domain, [])
        if not pts:
            continue
        color = spec["color"]
        marker = spec["marker"]
        arr = np.array(pts)
        xs, ys = arr[:, 0], arr[:, 1]
        all_xs.extend(xs.tolist())
        all_ys.extend(ys.tolist())

        # Scatter - large markers, semi-opaque.
        ax.scatter(
            xs,
            ys,
            c=color,
            marker=marker,
            s=55,
            alpha=0.55,
            zorder=3,
            edgecolors="white",
            linewidths=0.3,
        )

        # Convex hull region.
        hull = _hull_polygon(arr)
        if hull is not None:
            ax.fill(
                hull[:, 0],
                hull[:, 1],
                color=color,
                alpha=0.08,
                zorder=1,
            )
            ax.plot(
                hull[:, 0],
                hull[:, 1],
                color=color,
                alpha=0.45,
                lw=1.4,
                zorder=1,
            )

        # Legend entry - marker + filled hull swatch.
        legend_handles.append(
            Line2D(
                [0],
                [0],
                marker=marker,
                color=color,
                markerfacecolor=color,
                markersize=12,
                markeredgecolor="white",
                markeredgewidth=0.5,
                linewidth=7,
                alpha=0.45,
                label=domain,
            )
        )

    ax.set_xscale("log")
    ax.set_yscale("log")

    # Tight axis limits.
    if all_xs and all_ys:
        pad = 0.3
        ax.set_xlim(
            10 ** (np.log10(min(all_xs)) - pad),
            10 ** (np.log10(max(all_xs)) + pad),
        )
        ax.set_ylim(
            10 ** (np.log10(min(all_ys)) - pad),
            10 ** (np.log10(max(all_ys)) + pad),
        )

    # Time reference lines.
    ylims = ax.get_ylim()
    xlims = ax.get_xlim()
    for t_sec, label in _TIME_MARKERS:
        if xlims[0] <= t_sec <= xlims[1]:
            ax.axvline(t_sec, color="#D1D5DB", lw=0.7, ls=":", zorder=0)
            ax.text(
                t_sec,
                ylims[0] * 1.25,
                label,
                fontsize=8.5,
                color="#9CA3AF",
                ha="center",
                va="bottom",
                zorder=0,
            )

    ax.set_xlabel("Wall time (seconds)", fontsize=13)
    ax.set_ylabel("Physical qubits", fontsize=13)
    ax.set_title(
        "FTQC Primitive Resource Landscape",
        fontsize=16,
        fontweight="semibold",
        pad=12,
    )

    light_grid(ax, which="both")

    # Single legend - marker + colour band, 2 columns, right side.
    ax.legend(
        handles=legend_handles,
        fontsize=11,
        loc="lower right",
        framealpha=0.94,
        ncol=2,
        columnspacing=1.2,
        borderpad=0.8,
        handletextpad=0.6,
        handlelength=2.2,
    )

    plt.tight_layout()
    savefig(fig, *paths)


def main() -> None:
    apply_theme()
    chart_dir = Path("results/charts")
    chart_dir.mkdir(parents=True, exist_ok=True)
    results = collect()
    # The repo-root copy is what README embeds; write both so they cannot drift.
    plot(results, chart_dir / "landscape.png", Path("landscape.png"))


if __name__ == "__main__":
    main()
