"""Shared plot theme, palette, and helpers for experiment charts."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

PALETTE = {
    "blue": "#2563EB",
    "red": "#DC2626",
    "green": "#059669",
    "orange": "#D97706",
    "purple": "#7C3AED",
    "gray": "#6B7280",
    "teal": "#0D9488",
    "pink": "#DB2777",
}

# Ordered list for cycling through operations / variants.
CYCLE = [
    PALETTE["blue"],
    PALETTE["red"],
    PALETTE["green"],
    PALETTE["orange"],
    PALETTE["purple"],
    PALETTE["teal"],
    PALETTE["pink"],
    PALETTE["gray"],
]


_DPI = 200
_RC_OVERRIDES = {
    # Figure
    "figure.facecolor": "white",
    "figure.dpi": _DPI,
    "savefig.dpi": _DPI,
    "savefig.bbox": "tight",
    # Axes
    "axes.facecolor": "white",
    "axes.edgecolor": "#D1D5DB",
    "axes.labelcolor": "#1F2937",
    "axes.titlesize": 13,
    "axes.titleweight": "semibold",
    "axes.titlepad": 12,
    "axes.labelsize": 11,
    "axes.labelpad": 6,
    # Grid
    "axes.grid": False,  # turned on per-axis when needed
    "grid.color": "#E5E7EB",
    "grid.alpha": 0.7,
    "grid.linewidth": 0.6,
    # Ticks
    "xtick.color": "#6B7280",
    "ytick.color": "#6B7280",
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    # Legend
    "legend.framealpha": 0.9,
    "legend.edgecolor": "#D1D5DB",
    "legend.fontsize": 9,
    "legend.borderpad": 0.5,
    # Font
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
    # Lines
    "lines.linewidth": 2.0,
    "lines.markersize": 7,
}


def apply_theme() -> None:
    """Apply the shared rcParams theme. Call once per script."""
    plt.rcParams.update(_RC_OVERRIDES)


# Canonical figure sizes.
FIG_SINGLE = (7.5, 5)
FIG_DUAL = (13, 5)
FIG_TALL = (8, 6)


def light_grid(ax, which: str = "both", axis: str = "both") -> None:
    """Turn on a light background grid."""
    ax.grid(True, which=which, axis=axis, color="#E5E7EB", alpha=0.7, linewidth=0.6)


def savefig(fig, path: Path, **kwargs) -> None:
    """Save with tight bbox and print confirmation."""
    fig.savefig(path, bbox_inches="tight", **kwargs)
    plt.close(fig)
    print(f"Saved {path}")


def format_k(val: float, _pos=None) -> str:
    """Tick formatter: 1000 → '1k', 45000 → '45k'."""
    if val >= 1_000_000:
        return f"{val / 1_000_000:.0f}M"
    if val >= 1_000:
        return f"{val / 1_000:.0f}k"
    return f"{val:.0f}"
