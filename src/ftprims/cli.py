"""ftprims CLI — run benchmarks, verify, export QREF, compile with Bartiq."""

from __future__ import annotations

import json
from pathlib import Path

import click

from ftprims.algorithms import registry


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
def run(
    primitive: str,
    param: tuple[str, ...],
    out: str | None,
    physical: bool,
) -> None:
    """Run a single benchmark and report resource costs."""
    from ftprims.resource import estimate_physical

    bench = registry[primitive]
    params = _parse_params(param)
    click.echo(f"Building {primitive} with {params}")

    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq)

    result: dict = {
        "primitive": primitive,
        "params": params,
        "logical": {
            "qubits": costs.qubits,
            "t_count": costs.t_count,
            "clifford_count": costs.clifford_count,
            "rotation_count": costs.rotation_count,
        },
    }

    if physical:
        phys = estimate_physical(costs)
        result["physical"] = {
            "physical_qubits": phys.physical_qubits,
            "wall_time_us": phys.wall_time_us,
            "code_distance": phys.code_distance,
            "error_budget": phys.error_budget,
        }

    click.echo(json.dumps(result, indent=2))

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
    status = "✓ PASS" if result.passed else "✗ FAIL"
    click.echo(f"{status}  {result.detail}")


@main.command("export-qref")
@click.argument("primitive", type=click.Choice(list(registry)))
@click.option("--param", "-p", multiple=True, help="key=value parameter pairs")
@click.option("--out", type=click.Path(), required=True, help="Output YAML path")
def export_qref(primitive: str, param: tuple[str, ...], out: str) -> None:
    """Export benchmark as a QREF v1 program."""
    from ftprims.export import build_qref_program, save_qref

    bench = registry[primitive]
    params = _parse_params(param)
    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq)

    port_size = params.get("n") or params.get("m")
    program = build_qref_program(
        primitive,
        params,
        costs,
        port_size=int(port_size) if port_size is not None else None,
    )

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    save_qref(program, out)
    click.echo(f"QREF exported → {out}")


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
