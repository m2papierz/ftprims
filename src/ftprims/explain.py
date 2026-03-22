"""Deterministic rule-based interpretation of benchmark results.

Generates a short headline and up to 3 observations based on the
logical costs, breakdown summary, and physical costs.
"""

from __future__ import annotations

from ftprims.algorithms._base import LogicalCosts, PhysicalCosts
from ftprims.breakdown import BreakdownItem, summarize_breakdown


def explain_run(
    primitive: str,
    params: dict,
    logical: LogicalCosts,
    physical: PhysicalCosts | None = None,
    breakdown: tuple[BreakdownItem, ...] = (),
) -> dict[str, object]:
    """Build an explanation dict for a benchmark run.

    Returns
    -------
    dict with keys:
        headline: str — one-line characterisation
        observations: list[str] — up to 3 interpretive sentences
        metrics: dict — numeric summary values
    """
    summary = summarize_breakdown(breakdown) if breakdown else {}
    dominant = summary.get("dominant_component", "")
    dominant_share = summary.get("dominant_share", 0.0)
    rotation_share = summary.get("rotation_share", 0.0)

    headline = _headline(primitive, params, logical, dominant, dominant_share)

    observations: list[str] = []
    if physical is not None:
        observations.extend(_physical_observations(physical))
    observations.extend(_primitive_observations(primitive, params, logical, summary))
    observations.extend(
        _generic_observations(logical, dominant, dominant_share, rotation_share)
    )

    # Cap at 3.
    observations = observations[:3]

    metrics: dict[str, object] = {}
    if summary:
        metrics["dominant_component"] = dominant
        metrics["dominant_share"] = round(dominant_share, 3)
        metrics["rotation_share"] = round(rotation_share, 3)
    if logical.t_count_direct > 0:
        metrics["ftqc_overhead"] = round(
            logical.t_count_ftqc / logical.t_count_direct, 2
        )
    if physical is not None:
        metrics["physical_qubits"] = physical.physical_qubits
        metrics["budget_satisfied"] = physical.budget_satisfied

    return {
        "headline": headline,
        "observations": observations,
        "metrics": metrics,
    }


def _headline(
    primitive: str,
    params: dict,
    logical: LogicalCosts,
    dominant: str,
    dominant_share: float,
) -> str:
    variant = params.get("variant", "")
    op = params.get("op", "")

    if primitive == "qft":
        if variant == "approx":
            return "Approximate QFT — reduced rotation overhead"
        if dominant == "rotations" and dominant_share > 0.5:
            return "Rotation-heavy textbook QFT"
        return "Textbook QFT"

    if primitive == "qpe":
        if dominant == "controlled_nonclifford":
            return "Controlled-U dominated QPE"
        if dominant == "qft_qpe_core":
            return "QFT-dominated QPE"
        return "Textbook QPE"

    if primitive == "arithmetic":
        _OP_LABELS = {
            "add": "In-place adder",
            "add_oop": "Out-of-place adder",
            "leq": "Comparator",
            "mul": "Multiplier",
            "modadd": "Modular adder",
        }
        return _OP_LABELS.get(str(op), f"Arithmetic ({op})")

    if primitive == "qrom":
        if variant == "selectswap":
            return "SelectSwapQROM — ancilla/T trade-off"
        return "Basic QROM lookup"

    return f"{primitive} benchmark"


def _primitive_observations(
    primitive: str,
    params: dict,
    logical: LogicalCosts,
    summary: dict,
) -> list[str]:
    obs: list[str] = []
    variant = params.get("variant", "")
    op = params.get("op", "")
    rotation_share = summary.get("rotation_share", 0.0)

    if primitive == "qft":
        if variant == "textbook" and rotation_share > 0.5:
            obs.append(
                "Cost is dominated by rotation synthesis; "
                "t_count_ftqc is much larger than t_count_direct."
            )
        if variant == "approx":
            obs.append(
                "Approximate QFT truncates small-angle rotations; "
                "savings appear mainly in t_count_ftqc."
            )

    elif primitive == "qpe":
        qft_share = summary.get("qft_qpe_core_share", 0.0)
        ctrl_share = summary.get("controlled_nonclifford_share", 0.0)
        if qft_share > ctrl_share:
            obs.append(
                "The estimation/QFT part costs more than the "
                "toy controlled-U in this configuration."
            )
        elif ctrl_share > qft_share and ctrl_share > 0:
            obs.append("Controlled-U cost dominates over the inverse QFT.")

    elif primitive == "arithmetic":
        if op in ("add", "add_oop"):
            obs.append("A pure building block; costs grow regularly with bitsize.")
        elif op in ("mul", "modadd"):
            obs.append(
                "Cost derives from composing multiple sub-operations; "
                "growth is faster than for add/comparator."
            )

    elif primitive == "qrom":
        if variant == "basic":
            obs.append(
                "Basic lookup is qubit-efficient but offers no "
                "ancilla-vs-T trade-off."
            )
        elif variant == "selectswap":
            obs.append(
                "SelectSwap trades more ancillae for fewer non-Clifford gates; "
                "see log_block_sizes and breakdown."
            )

    return obs


def _generic_observations(
    logical: LogicalCosts,
    dominant: str,
    dominant_share: float,
    rotation_share: float,
) -> list[str]:
    obs: list[str] = []

    if logical.t_count_direct > 0 and logical.t_count_ftqc > 2 * logical.t_count_direct:
        obs.append(
            f"FTQC T-count ({logical.t_count_ftqc:,}) is "
            f"{logical.t_count_ftqc / logical.t_count_direct:.1f}x the direct "
            f"T-count ({logical.t_count_direct:,}) due to rotation synthesis."
        )

    if dominant and dominant_share >= 0.8:
        obs.append(
            f"Cost is concentrated in '{dominant}' "
            f"({dominant_share:.0%} of estimated FTQC T-cost)."
        )

    return obs


def _physical_observations(physical: PhysicalCosts) -> list[str]:
    obs: list[str] = []

    if not physical.budget_satisfied:
        obs.append(
            "The chosen physical configuration does not meet the error "
            "budget; treat the result as a reference point, not a "
            "deployable design."
        )

    if physical.data_block == "fast":
        obs.append(
            "Fast data block increases qubit footprint but can reduce "
            "the magic-state consumption bottleneck."
        )

    if physical.factory == "fifteen_to_one":
        obs.append(
            "The 15-to-1 T-factory changes the space/time trade-off "
            "compared to CCZ2T."
        )

    return obs
