"""qrepro CLI: run benchmarks, verify, export QREF, compile with Bartiq,
and print the published-estimate reproductions."""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import click

from qrepro.algorithms import registry
from qrepro.config import DEFAULT_CONFIG, QreproConfig


def _load_config(path: str | None) -> QreproConfig:
    if path is not None:
        return QreproConfig.load(path)
    return DEFAULT_CONFIG


@click.group()
@click.version_option(package_name="qrepro")
def main() -> None:
    """qrepro - FTQC primitives benchmark suite."""


@main.command()
@click.argument("primitive", type=click.Choice(list(registry)))
@click.option("--param", "-p", multiple=True, help="key=value parameter pairs")
@click.option(
    "--out", type=click.Path(), default=None, help="Save JSON results to file"
)
@click.option("--physical", is_flag=True, help="Include surface-code physical estimate")
@click.option(
    "--profile",
    type=click.Choice(["gidney_fowler", "beverland"]),
    default="gidney_fowler",
    show_default=True,
    help="QEC profile preset",
)
@click.option(
    "--data-block",
    type=click.Choice(["simple", "compact", "fast"]),
    default="simple",
    show_default=True,
    help="Surface-code data block type",
)
@click.option(
    "--factory",
    type=click.Choice(["ccz2t", "fifteen_to_one"]),
    default="ccz2t",
    show_default=True,
    help="Magic-state factory",
)
@click.option(
    "--data-d",
    type=int,
    default=None,
    help="Fixed code distance (auto-search if omitted)",
)
@click.option(
    "--error-budget",
    type=float,
    default=None,
    help="Error budget (default from config: 1e-3)",
)
@click.option(
    "--physical-error", type=float, default=None, help="Override physical error rate"
)
@click.option(
    "--cycle-time-us", type=float, default=None, help="Override cycle time (us)"
)
@click.option("--breakdown", is_flag=True, help="Include structural cost breakdown")
@click.option(
    "--rotation-eps",
    type=float,
    default=None,
    help="Rotation synthesis epsilon (default from config: 1e-10)",
)
@click.option(
    "--config", "config_path", type=click.Path(), default=None, help="Config YAML"
)
def run(
    primitive: str,
    param: tuple[str, ...],
    out: str | None,
    physical: bool,
    profile: str,
    data_block: str,
    factory: str,
    data_d: int | None,
    error_budget: float | None,
    physical_error: float | None,
    cycle_time_us: float | None,
    breakdown: bool,
    rotation_eps: float | None,
    config_path: str | None,
) -> None:
    """Run a single benchmark and report resource costs."""
    cfg = _load_config(config_path)
    bench = registry[primitive]
    params = _parse_params(param)
    click.echo(f"Building {primitive} with {params}")

    # CLI overrides config, config overrides the dataclass defaults.
    eps = (
        rotation_eps
        if rotation_eps is not None
        else cfg.surface_code.rotation_synthesis_epsilon
    )
    _error_budget = (
        error_budget if error_budget is not None else cfg.surface_code.error_budget
    )
    _physical_error = (
        physical_error
        if physical_error is not None
        else cfg.surface_code.physical_error
    )
    _cycle_time_us = (
        cycle_time_us if cycle_time_us is not None else cfg.surface_code.cycle_time_us
    )
    _data_d = data_d if data_d is not None else cfg.surface_code.data_d

    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq, rotation_synthesis_epsilon=eps)

    result: dict = {
        "primitive": primitive,
        "params": params,
        "logical": {
            "logical_qubits_estimate": costs.logical_qubits_estimate,
            "t_count_direct": costs.t_count_direct,
            "t_count_ftqc": costs.t_count_ftqc,
            "raw_t": costs.raw_t,
            "magic_state_count": costs.magic_state_count,
            "clifford_count": costs.clifford_count,
            "rotation_count": costs.rotation_count,
            "rotation_synthesis_epsilon": costs.rotation_synthesis_epsilon,
        },
    }

    if breakdown:
        import attrs

        from qrepro.breakdown import extract_structural_breakdown, summarize_breakdown

        items = extract_structural_breakdown(
            bloq,
            rotation_eps=eps,
        )
        result["breakdown"] = [attrs.asdict(item) for item in items]
        result["breakdown_summary"] = summarize_breakdown(items)

        _check_logical_breakdown_consistency(
            costs.t_count_ftqc, items, primitive, params
        )

    if physical:
        from qrepro.physical import PhysicalModelSpec
        from qrepro.physical import estimate_physical as phys_estimate

        spec = PhysicalModelSpec(
            profile=profile,
            data_block=data_block,
            factory=factory,
            data_d=_data_d,
            error_budget=_error_budget,
            physical_error=_physical_error,
            cycle_time_us=_cycle_time_us,
        )
        phys_result = phys_estimate(costs, spec=spec)
        result["physical"] = {
            "profile": phys_result.profile,
            "data_block": phys_result.data_block,
            "factory": phys_result.factory,
            "physical_qubits": phys_result.physical_qubits,
            "wall_time_us": phys_result.wall_time_us,
            "code_distance": phys_result.code_distance,
            "error_budget": phys_result.error_budget,
            "failure_prob": phys_result.failure_prob,
            "budget_satisfied": phys_result.budget_satisfied,
        }

    click.echo(json.dumps(result, indent=2))

    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=2))
        click.echo(f"Saved => {out}")


def _check_logical_breakdown_consistency(
    logical_ftqc: int,
    items: tuple,
    primitive: str,
    params: dict,
) -> None:
    """Warn when the breakdown total diverges from ``t_count_ftqc`` by >10%.

    The two come from the same bloq by different extraction paths, so a large
    gap means one of them is wrong.
    """
    breakdown_ftqc = sum(item.est_t_ftqc for item in items)

    # Both zero is consistent, e.g. Clifford-only circuits.
    if logical_ftqc == 0 and breakdown_ftqc == 0:
        return

    denom = max(logical_ftqc, breakdown_ftqc, 1)
    relative = abs(logical_ftqc - breakdown_ftqc) / denom

    if relative > 0.10:
        warnings.warn(
            f"[{primitive} {params}] logical t_count_ftqc={logical_ftqc:,} vs "
            f"breakdown total={breakdown_ftqc:,} (delta={relative:.1%}). "
            f"The two extraction paths disagree; check resource.py and "
            f"breakdown.py.",
            stacklevel=2,
        )


@main.command()
@click.argument("primitive", type=click.Choice(list(registry)))
@click.option("--param", "-p", multiple=True, help="key=value parameter pairs")
def verify(primitive: str, param: tuple[str, ...]) -> None:
    """Run small-scale Cirq verification for a primitive."""
    bench = registry[primitive]
    params = _parse_params(param)
    result = bench.verify_small(**params)
    icons = {"pass": "[OK] PASS", "fail": "[X] FAIL", "skip": "[-] SKIP"}
    click.echo(f"{icons[result.status]}  {result.detail}")

    if result.status == "fail":
        sys.exit(1)


_PORT_SIZE_KEYS: dict[str, list[str]] = {
    "qft": ["n"],
    "qpe": ["m"],
    "arithmetic": ["n"],
    "qrom": ["target_bitsize"],
}


def _infer_port_size(primitive: str, params: dict) -> int | None:
    """QREF port size from *params*, or ``None`` when no key applies."""
    for key in _PORT_SIZE_KEYS.get(primitive, []):
        val = params.get(key)
        if val is not None:
            return int(val)
    return None


@main.command("export-qref")
@click.argument("primitive", type=click.Choice(list(registry)))
@click.option("--param", "-p", multiple=True, help="key=value parameter pairs")
@click.option("--out", type=click.Path(), required=True, help="Output YAML path")
@click.option(
    "--symbolic",
    is_flag=True,
    default=False,
    help=(
        "Export approximate analytic expressions for Bartiq "
        "(not a faithful export of the numeric benchmark)"
    ),
)
@click.option(
    "--check",
    is_flag=True,
    default=False,
    help="Compare symbolic approximation against numeric benchmark",
)
@click.option(
    "--config", "config_path", type=click.Path(), default=None, help="Config YAML"
)
def export_qref(
    primitive: str,
    param: tuple[str, ...],
    out: str,
    symbolic: bool,
    check: bool,
    config_path: str | None,
) -> None:
    """Export a benchmark as a QREF v1 program.

    Numeric mode embeds concrete resource values. --symbolic writes analytic
    expressions for ``qrepro bartiq`` to compile; --check compares them
    against the Qualtran benchmark at the given parameters.
    """
    from qrepro.export import build_qref_program, save_qref

    cfg = _load_config(config_path)
    bench = registry[primitive]
    params = _parse_params(param)

    # Numeric mode needs these directly; symbolic mode needs them for --check.
    need_numeric = (not symbolic) or check
    numeric_costs = None
    if need_numeric:
        bloq = bench.build_bloq(**params)
        numeric_costs = bench.logical_costs(bloq)

    if symbolic:
        from qrepro.algorithms._base import LogicalCosts

        # Symbolic mode reads its costs from the formula table, not from here.
        costs = LogicalCosts(
            logical_qubits_estimate=0,
            t_count_direct=0,
            t_count_ftqc=0,
        )
    else:
        assert numeric_costs is not None
        costs = numeric_costs

    port_size = _infer_port_size(primitive, params)
    program = build_qref_program(
        primitive,
        params,
        costs,
        symbolic=symbolic,
        port_size=port_size,
        cfg=cfg.qref,
    )

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    save_qref(program, out)
    mode = "symbolic (approximate analytic)" if symbolic else "numeric"
    click.echo(f"QREF exported ({mode}) => {out}")

    if symbolic:
        click.echo(
            "  [!] Symbolic formulas are textbook-level approximations, "
            "not a faithful export of the numeric benchmark."
        )

    if check and symbolic and numeric_costs is not None:
        from qrepro.export import check_symbolic_consistency

        _SYMBOLIC_ERROR_THRESHOLD = 0.20

        report = check_symbolic_consistency(primitive, params, numeric_costs)
        if not report.get("available"):
            click.echo(f"  Check skipped: {report.get('reason', 'unknown')}")
        else:
            max_rel = report.get("max_relative_error", 0.0)
            ok = "[OK] consistent" if report["consistent"] else "[X] DIVERGENT"
            click.echo(f"\n  Symbolic <===> Numeric consistency: {ok}")
            for field, comp in report["comparisons"].items():
                if comp.get("match") is None:
                    continue
                sym = comp["symbolic"]
                num = comp["numeric"]
                icon = "[OK]" if comp["match"] else "[X]"
                rel = comp.get("relative_error")
                rel_str = f"  (delta={rel:.1%})" if rel and not comp["match"] else ""
                click.echo(
                    f"    {icon} {field:20s}  "
                    f"symbolic={sym:>10,}  numeric={num:>10,}{rel_str}"
                )

            if max_rel > _SYMBOLIC_ERROR_THRESHOLD:
                click.echo(
                    f"\n  [!] Max relative error {max_rel:.1%} exceeds "
                    f"threshold {_SYMBOLIC_ERROR_THRESHOLD:.0%}. "
                    f"Symbolic export is unreliable at these parameters."
                )


@main.command()
@click.argument("qref_yaml", type=click.Path(exists=True))
@click.option("--assign", "-a", multiple=True, help="key=value assignments for Bartiq")
def bartiq(qref_yaml: str, assign: tuple[str, ...]) -> None:
    """Compile a QREF YAML with Bartiq and evaluate resource expressions."""
    import yaml
    from bartiq import compile_routine, evaluate
    from qref import SchemaV1

    with open(qref_yaml) as f:
        raw = yaml.safe_load(f)

    schema = SchemaV1(**raw)
    compiled = compile_routine(schema)

    click.echo("Compiled resources (symbolic):")
    for name, res in compiled.routine.resources.items():
        click.echo(f"  {name} = {res.value}")

    if assign:
        assignments = {k: int(v) for k, v in (a.split("=") for a in assign)}
        result = evaluate(compiled.routine, assignments=assignments)
        click.echo(f"\nEvaluated with {assignments}:")
        for name, res in result.routine.resources.items():
            click.echo(f"  {name} = {res.value}")


@main.command("dump-config")
@click.option("--out", type=click.Path(), default=None, help="Save to YAML file")
def dump_config(out: str | None) -> None:
    """Print (or save) the default configuration."""
    import yaml

    data = DEFAULT_CONFIG.to_dict()
    text = yaml.safe_dump(data, sort_keys=False)

    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text)
        click.echo(f"Config saved => {out}")
    else:
        click.echo(text)


@main.group()
def reproduce() -> None:
    """Reproduce published FTQC resource estimates and print the tables."""


def _print_rows(rows) -> None:
    """Render reproduction rows as an aligned comparison table."""
    header = f"{'label':18} {'metric':18} {'reproduced':>14} {'target':>14} {'dev':>8}"
    click.echo(header)
    click.echo("-" * len(header))
    for row in rows:
        target = "-" if row.target is None else f"{row.target:14.4g}"
        dev = "-" if row.deviation is None else f"{row.deviation:+7.1%}"
        click.echo(
            f"{row.label:18} {row.metric:18} {row.reproduced:14.4g} {target:>14} {dev:>8}"
        )


@reproduce.command("beverland")
def reproduce_beverland_cmd() -> None:
    """Beverland et al. (arXiv:2211.07629): three application data points."""
    from qrepro.references import reproduce_beverland

    click.echo("Beverland et al. (arXiv:2211.07629)")
    _print_rows(reproduce_beverland().rows)


@reproduce.command("ge19")
@click.option(
    "--skip-windowed",
    is_flag=True,
    help="Skip the windowed-construction rows (the window sweep costs ~1 s).",
)
def reproduce_ge19_cmd(skip_windowed: bool) -> None:
    """GE19 (arXiv:1905.09749v3): factor 2048-bit RSA."""
    from qrepro.references import (
        reproduce_ge19_logical,
        reproduce_ge19_physical,
        reproduce_ge19_windowed,
    )

    click.echo("GE19 (arXiv:1905.09749v3) - logical reconciliation")
    _print_rows(reproduce_ge19_logical().rows)
    if not skip_windowed:
        click.echo()
        click.echo(
            "GE19 (arXiv:1905.09749v3) - windowed construction (sec. 2.3-2.5), "
            "from Qualtran components"
        )
        windowed = reproduce_ge19_windowed()
        _print_rows(windowed.rows)
        we, wm = windowed.window_argmin
        click.echo(
            f"  cost minimum over the window grid at n={windowed.instances[1].n}: "
            f"(w_e, w_m) = ({we}, {wm}); GE19's own default (L690) is (5, 5)"
        )
        click.echo(
            "  'bridged' doubles the adder term only, converting Qualtran's "
            "Gidney AND-adder to GE19's Cuccaro convention (ASSUMPTIONS.md sec. 6)"
        )
    click.echo()
    click.echo("GE19 (arXiv:1905.09749v3) - physical rows")
    _print_rows(reproduce_ge19_physical().rows)


@reproduce.command("decomposition")
@click.option(
    "--convention",
    type=click.Choice(["per_run", "expected", "both"]),
    default="both",
    show_default=True,
    help=(
        "Toffoli-count normalisation. GE19 Table 1 is per-run; G2025 Table 5 is "
        "expected over E(shots)=9.2. 'both' prints each."
    ),
)
def reproduce_decomposition_cmd(convention: str) -> None:
    """2019 => 2025 decomposition (arXiv:2505.15917)."""
    from qrepro.references import reproduce_2019_to_2025
    from qrepro.references.decomposition import CONVENTIONS

    conventions = CONVENTIONS if convention == "both" else (convention,)
    for conv in conventions:
        click.echo(f"2019 => 2025 decomposition (arXiv:2505.15917) - {conv}")
        _print_rows(reproduce_2019_to_2025(conv).rows)
        click.echo()


def _parse_params(raw: tuple[str, ...]) -> dict[str, int | float | str]:
    """Parse 'key=value' strings into a typed dict."""
    params: dict[str, int | float | str] = {}
    for item in raw:
        k, _, v = item.partition("=")
        try:
            params[k] = int(v)
        except ValueError:
            try:
                params[k] = float(v)
            except ValueError:
                params[k] = v
    return params
