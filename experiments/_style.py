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
FIG_DUAL = (13, 5)


def light_grid(ax, which: str = "both", axis: str = "both") -> None:
    """Turn on a light background grid."""
    ax.grid(True, which=which, axis=axis, color="#E5E7EB", alpha=0.7, linewidth=0.6)


def savefig(fig, *paths: Path, **kwargs) -> None:
    """Save the figure to every *path* with tight bbox, then close it once."""
    for path in paths:
        fig.savefig(path, bbox_inches="tight", **kwargs)
        print(f"Saved {path}")
    plt.close(fig)
