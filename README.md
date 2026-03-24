# ftprims
Fault-tolerant quantum computing (FTQC) primitives benchmark suite. Built on [Qualtran](https://qualtran.readthedocs.io/) + [Cirq](https://quantumai.google/cirq) with native [QREF](https://github.com/PsiQ/qref) / [Bartiq](https://github.com/PsiQ/bartiq) export. Benchmark canonical FTQC building blocks, extract logical & physical resource costs via Qualtran, verify correctness with Cirq simulation, and export results as QREF programs for cost propagation in Bartiq.

> [!NOTE]
> Learning project - built to deepen hands-on understanding of FTQC resource estimation, Qualtran's bloq abstractions, and the QREF/Bartiq toolchain. Simplifications and approximations often appear in the design.

<p align="center">
  <img src="landscape.png" width="850" alt="FTQC Primitive Resource Landscape">
</p>

<p align="center">
  <em>Physical resource landscape: each region shows the qubits x time footprint of a primitive variant as problem size scales. Every primitive is evaluated across 9 surface-code configurations: 2 QEC profiles (Gidney-Fowler, Beverland) x data blocks (simple, compact, fast) x magic-state factories (CCZ2T, 15-to-1). Inspired by [Beverland et al.](https://arxiv.org/abs/2211.07629)</em>
</p>

### Primitives

| Primitive | Variants | Key metric |
|-----------|----------|------------|
| **QFT** | Textbook, Approximate | T-count vs n (incl. rotation synthesis) |
| **QPE** | Textbook (pluggable U) | T-count vs precision bits |
| **Arithmetic** | Add, OutOfPlaceAdder, LessThanEqual, Product, ModAdd | T-count vs bitsize |
| **QROM** | QROM, SelectSwapQROM | T-count vs table size, T/ancilla Pareto |

## Installation

Requires Python 3.10–3.12.

```bash
git clone https://github.com/m2papierz/ftprims.git && cd ftprims

# with uv (recommended)
uv sync

# or with pip
pip install -e ".[dev]"
```

## Quick start - run everything

The `run_all.sh` script runs every benchmark, verification, QREF export, consistency check, and experiment sweep in one go:

```bash
./run_all.sh
```

Results land in organized subfolders:

```
results/
├── runs/           # Individual benchmark JSONs
├── qref/
│   ├── numeric/    # QREF exports with concrete values (authoritative)
│   └── symbolic/   # QREF exports with analytic formulas (approximate)
├── sweeps/         # CSV sweep data
├── charts/         # All generated PNG plots
└── configs/        # Default configuration dump
```

## Usage

### Run a benchmark

```bash
# Logical costs only
ftprims run qft -p n=32

# Include surface-code physical estimate
ftprims run qft -p n=32 --physical

# Arithmetic
ftprims run arithmetic -p n=64 -p op=mul

# QROM with SelectSwap trade-off
ftprims run qrom -p data_size=256 -p variant=selectswap -p log_block_sizes=4

# Save results to JSON
ftprims run qft -p n=32 --physical --out results/runs/qft_n32.json
```

### Structural cost breakdown

The `--breakdown` flag decomposes costs into component categories via Qualtran's `call_graph` showing where T-gates actually come from:

```bash
ftprims run qft -p n=16 -p variant=textbook --breakdown
```

This adds a `breakdown` array and `breakdown_summary` to the JSON output. Categories: `rotations`, `qft_qpe_core`, `qrom_core`, `arithmetic_core`, `controlled_nonclifford`, `clifford_scaffolding`, `other`.

Gate classification is cost-aware: parameterised `*PowGate` bloqs are classified as `rotations` when their exponent is non-Clifford (requires synthesis), and bloqs from rotation modules that decompose to pure Toffoli gates (e.g. `AddIntoPhaseGrad` in approximate QFT) are reclassified as `controlled_nonclifford`.

### Example output

```bash
ftprims run arithmetic -p n=16 -p op=add --breakdown --physical --explain-json
```

```json
{
  "primitive": "arithmetic",
  "params": {"n": 8, "op": "modadd"},
  "logical": {
    "logical_qubits_estimate": 34,
    "t_count_direct": 124,
    "t_count_ftqc": 124,
    "raw_t": 0,
    "ccz_count": 31,
    "clifford_count": 248,
    "rotation_count": 0,
    "rotation_synthesis_epsilon": 1e-10
  },
  "breakdown": [
    {
      "component": "arithmetic_core",
      "invocations": 3,
      "direct_t": 96,
      "clifford_count": 187,
      "rotation_count": 0,
      "est_t_ftqc": 96
    },
    {
      "component": "clifford_scaffolding",
      "invocations": 1,
      "direct_t": 0,
      "clifford_count": 1,
      "rotation_count": 0,
      "est_t_ftqc": 0
    },
    {
      "component": "other",
      "invocations": 1,
      "direct_t": 28,
      "clifford_count": 60,
      "rotation_count": 0,
      "est_t_ftqc": 28
    }
  ],
  "breakdown_summary": {
    "dominant_component": "arithmetic_core",
    "dominant_share": 0.7741935483870968,
    "rotation_share": 0.0,
    "arithmetic_core_share": 0.7741935483870968,
    "clifford_scaffolding_share": 0.0,
    "other_share": 0.22580645161290322
  },
  "physical": {
    "profile": "gidney_fowler",
    "data_block": "simple",
    "factory": "ccz2t",
    "physical_qubits": 170854,
    "wall_time_us": 5286.0,
    "code_distance": 15,
    "error_budget": 0.001,
    "failure_prob": 0.00026958765332920015,
    "budget_satisfied": true
  },
  "explain": {
    "headline": "Modular adder",
    "observations": [
      "Cost derives from composing multiple sub-operations; growth is faster than for add/comparator."
    ],
    "metrics": {
      "dominant_component": "arithmetic_core",
      "dominant_share": 0.774,
      "rotation_share": 0.0,
      "ftqc_overhead": 1.0,
      "physical_qubits": 170854,
      "budget_satisfied": true
    }
  }
}
```

### Physical model variants

Physical estimation supports multiple surface-code configurations:

```bash
# Beverland profile with fast data block and 15-to-1 factory
ftprims run qft -p n=32 --physical \
  --profile beverland --data-block fast --factory fifteen_to_one

# Fixed code distance
ftprims run qft -p n=32 --physical --data-d 21

# Custom error budget
ftprims run qft -p n=32 --physical --error-budget 1e-2

# Override physical error rate and cycle time
ftprims run qft -p n=32 --physical --physical-error 1e-4 --cycle-time-us 1.0
```

Available profiles: `gidney_fowler` (default), `beverland`. Data blocks: `simple` (default), `compact`, `fast`. Factories: `ccz2t` (default), `fifteen_to_one`.

### Interpret results

The `--explain` flag generates a short rule-based interpretation:

```bash
ftprims run qft -p n=16 --breakdown --physical --explain
```

Use `--explain-json` to embed the explanation in the JSON output instead.

### Verify (small-scale Cirq simulation)

```bash
ftprims verify qft        -p n=4 -p variant=textbook
ftprims verify qft        -p n=4 -p variant=approx
ftprims verify arithmetic -p n=4 -p op=add
ftprims verify arithmetic -p n=4 -p op=modadd
ftprims verify qrom       -p data_size=8 -p target_bitsize=4 -p variant=basic
ftprims verify qrom       -p data_size=8 -p target_bitsize=4 -p variant=selectswap
```

### Export to QREF / Bartiq

```bash
# Numeric export (concrete values from the Qualtran benchmark - authoritative)
ftprims export-qref qft -p n=32 --out results/qref/numeric/qft.yaml

# Symbolic export (approximate analytic formulas for Bartiq compilation)
ftprims export-qref qft -p n=32 --symbolic --out results/qref/symbolic/qft_sym.yaml

# Symbolic + consistency check against numeric benchmark
ftprims export-qref qft -p n=32 --symbolic --check --out results/qref/symbolic/qft_sym.yaml

# Compile and evaluate with Bartiq
ftprims bartiq results/qref/symbolic/qft_sym.yaml --assign n=64
```

> [!IMPORTANT]
> Symbolic mode (`--symbolic`) exports **approximate analytic formulas** - textbook-level scaling terms that may diverge from the numeric benchmark at concrete parameter values. Use `--check` to compare the approximation against the real Qualtran numbers. Numeric export is always the authoritative cost source.

### Parameter sweep experiments

```bash
python experiments/sweep_qft.py
python experiments/sweep_qpe.py
python experiments/sweep_arithmetic.py
python experiments/sweep_qrom.py

# Compare physical configs for any primitive
python experiments/compare_physical_configs.py qft n=16 variant=textbook
```

Each sweep writes CSV data to `results/sweeps/` and PNG charts to `results/charts/`.

### Configuration

```bash
# Print default config
ftprims dump-config

# Save and edit
ftprims dump-config --out config.yaml
# then pass to any command:
ftprims run qft -p n=32 --physical --config config.yaml
```

Key config options: `rotation_synthesis_epsilon` (default `1e-10`), `error_budget`, `physical_error`, `cycle_time_us`, `data_d`.

## Output format

Logical costs report two T-count metrics:

- **`t_count_direct`** - raw T-gates + 4xCCZ/And. Accurate for pure Clifford+T circuits.
- **`t_count_ftqc`** - includes rotation synthesis cost. This is the primary FTQC metric.

When `--breakdown` is used, the output includes per-component cost attribution with estimated FTQC T-cost and a summary identifying the dominant component.

Physical estimates include `failure_prob` and `budget_satisfied` - the model never silently masks an unmet error budget. The output also records which `profile`, `data_block`, and `factory` were used, so results are reproducible across runs.

## Known limitations

- **QPE verification**: `tensor_contract` / Cirq interop fails for `TextbookQPE`  (Qualtran limitation, not an ftprims bug). QPE numeric benchmarks and breakdown are correct; only the small-scale unitary verification is skipped.
- **Symbolic export divergence**: symbolic formulas are hand-written textbook-level approximations. They capture dominant asymptotic scaling but may diverge significantly (up to 100%) from Qualtran's concrete gate counts at specific parameter values. The `--check` flag reports divergence but does not fail the pipeline. Numeric export is always authoritative.
- **Approximate QFT cost structure**: `ApproximateQFT` uses phase-gradient additions (`AddIntoPhaseGrad`) that live in Qualtran's `rotations.phase_gradient` module but decompose entirely to Toffoli gates with zero rotation count. The breakdown correctly reclassifies these as `controlled_nonclifford`.

## Architecture

```
ftprims/
├── run_all.sh                  # Run every benchmark, verify, export, sweep
├── src/ftprims/
│   ├── algorithms/             # Benchmark implementations (QFT, QPE, Arithmetic, QROM)
│   │   └── _base.py            # Protocol, data models (LogicalCosts, PhysicalCosts, BreakdownItem)
│   ├── breakdown.py            # Structural cost breakdown via call_graph
│   ├── physical.py             # Surface-code physical model variants
│   ├── resource.py             # Logical cost extraction from Qualtran
│   ├── explain.py              # Rule-based result interpretation
│   ├── export.py               # QREF/Bartiq export (numeric + approximate symbolic)
│   ├── cli.py                  # Click CLI
│   └── config.py               # Configuration
├── experiments/                # Parameter sweep scripts (CSV + PNG output)
│   └── _style.py               # Shared plot theme and palette
└── tests/                      # Integration tests (89 tests, no mocks)
    ├── test_integration.py     # Regression, consistency, physical, scaling, invariants
    ├── test_cli.py             # CLI round-trip: JSON matches Python API
    └── test_export_breakdown.py # QREF export + per-item breakdown verification
```

## License

MIT License - see [LICENSE](LICENSE).
