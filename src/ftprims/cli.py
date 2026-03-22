"""ftprims CLI — run benchmarks, verify, export QREF, compile with Bartiq."""

from __future__ import annotations

import json
from pathlib import Path

import click

from ftprims.algorithms import registry
from ftprims.config import DEFAULT_CONFIG, FTPrimsConfig


def _load_config(path: str | None) -> FTPrimsConfig:
    if path is not None:
        return FTPrimsConfig.load(path)
    return DEFAULT_CONFIG


@click.group()
@click.version_option(package_name="ftprims")
def main() -> None:
    """ftprims — FTQC primitives benchmark suite."""


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
    "--error-budget", type=float, default=1e-3, show_default=True, help="Error budget"
)
@click.option(
    "--physical-error", type=float, default=None, help="Override physical error rate"
)
@click.option(
    "--cycle-time-us", type=float, default=None, help="Override cycle time (µs)"
)
@click.option("--breakdown", is_flag=True, help="Include structural cost breakdown")
@click.option(
    "--breakdown-depth",
    type=int,
    default=1,
    show_default=True,
    help="call_graph max_depth",
)
@click.option(
    "--rotation-eps",
    type=float,
    default=1e-10,
    show_default=True,
    help="Rotation synthesis",
)
@click.option("--explain", is_flag=True, help="Print interpretation after JSON output")
@click.option("--explain-json", is_flag=True, help="Embed explanation in JSON output")
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
    error_budget: float,
    physical_error: float | None,
    cycle_time_us: float | None,
    breakdown: bool,
    breakdown_depth: int,
    rotation_eps: float,
    explain: bool,
    explain_json: bool,
    config_path: str | None,
) -> None:
    """Run a single benchmark and report resource costs."""
    cfg = _load_config(config_path)
    bench = registry[primitive]
    params = _parse_params(param)
    click.echo(f"Building {primitive} with {params}")

    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq)

    result: dict = {
        "primitive": primitive,
        "params": params,
        "logical": {
            "logical_qubits_estimate": costs.logical_qubits_estimate,
            "t_count_direct": costs.t_count_direct,
            "t_count_ftqc": costs.t_count_ftqc,
            "raw_t": costs.raw_t,
            "ccz_count": costs.ccz_count,
            "clifford_count": costs.clifford_count,
            "rotation_count": costs.rotation_count,
            "rotation_synthesis_epsilon": costs.rotation_synthesis_epsilon,
        },
    }

    breakdown_items: tuple = ()
    if breakdown:
        import attrs

        from ftprims.breakdown import extract_structural_breakdown, summarize_breakdown

        items = extract_structural_breakdown(
            bloq,
            depth=breakdown_depth,
            rotation_eps=rotation_eps,
        )
        breakdown_items = items
        result["breakdown"] = [attrs.asdict(item) for item in items]
        result["breakdown_summary"] = summarize_breakdown(items)

    phys_result = None
    if physical:
        from ftprims.physical import PhysicalModelSpec
        from ftprims.physical import estimate_physical as phys_estimate

        spec = PhysicalModelSpec(
            profile=profile,
            data_block=data_block,
            factory=factory,
            data_d=data_d,
            error_budget=error_budget,
            physical_error=physical_error,
            cycle_time_us=cycle_time_us,
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

    if explain or explain_json:
        from ftprims.explain import explain_run

        explanation = explain_run(
            primitive,
            params,
            costs,
            physical=phys_result,
            breakdown=breakdown_items,
        )
        if explain_json:
            result["explain"] = explanation

    click.echo(json.dumps(result, indent=2))

    if explain and not explain_json:
        click.echo()
        click.echo(f"  {explanation['headline']}")
        for obs in explanation["observations"]:
            click.echo(f"  • {obs}")

    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=2))
        click.echo(f"Saved → {out}")


@main.command()
@click.argument("primitive", type=click.Choice(list(registry)))
@click.option("--param", "-p", multiple=True, help="key=value parameter pairs")
def verify(primitive: str, param: tuple[str, ...]) -> None:
    """Run small-scale Cirq verification for a primitive."""
    bench = registry[primitive]
    params = _parse_params(param)
    result = bench.verify_small(**params)
    icons = {"pass": "✓ PASS", "fail": "✗ FAIL", "skip": "⊘ SKIP"}
    click.echo(f"{icons[result.status]}  {result.detail}")


# Port-size heuristic for QREF export

_PORT_SIZE_KEYS: dict[str, list[str]] = {
    "qft": ["n"],
    "qpe": ["m"],
    "arithmetic": ["n"],
    "qrom": ["target_bitsize"],
}


def _infer_port_size(primitive: str, params: dict) -> int | None:
    """Best-effort port size from params; returns None when unknown."""
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
    help="Export symbolic expressions for Bartiq (instead of concrete values)",
)
@click.option(
    "--config", "config_path", type=click.Path(), default=None, help="Config YAML"
)
def export_qref(
    primitive: str,
    param: tuple[str, ...],
    out: str,
    symbolic: bool,
    config_path: str | None,
) -> None:
    """Export benchmark as a QREF v1 program.

    In numeric mode (default) concrete resource values are embedded.
    In symbolic mode (--symbolic) resource expressions are written so
    that ``ftprims bartiq`` can compile and evaluate them.
    """
    from ftprims.export import build_qref_program, save_qref

    cfg = _load_config(config_path)
    bench = registry[primitive]
    params = _parse_params(param)

    # In numeric mode we need to build the bloq to get costs.
    # In symbolic mode costs are formula-based; we still need params for
    # input_params list and port_size inference.
    if symbolic:
        from ftprims.algorithms._base import LogicalCosts

        # Dummy costs — symbolic mode ignores them.
        costs = LogicalCosts(
            logical_qubits_estimate=0,
            t_count_direct=0,
            t_count_ftqc=0,
        )
    else:
        bloq = bench.build_bloq(**params)
        costs = bench.logical_costs(bloq)

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
    mode = "symbolic" if symbolic else "numeric"
    click.echo(f"QREF exported ({mode}) → {out}")


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
        click.echo(f"Config saved → {out}")
    else:
        click.echo(text)


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
