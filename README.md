# ftprims
Fault-tolerant quantum computing (FTQC) primitives benchmark suite. Built on [Qualtran](https://qualtran.readthedocs.io/) + [Cirq](https://quantumai.google/cirq) with native [QREF](https://github.com/PsiQ/qref) / [Bartiq](https://github.com/PsiQ/bartiq) export.

Benchmark canonical FTQC building blocks, extract logical and physical resource costs, verify correctness with Cirq simulation, and export results as QREF programs for symbolic cost propagation in Bartiq.

> [!IMPORTANT]
> Learning project - built to deepen hands-on understanding of FTQC resource estimation, Qualtran's bloq abstractions, and the QREF/Bartiq toolchain. Simplifications and approximations often appear in the design.

<p align="center">
  <img src="landscape.png" width="850" alt="FTQC Primitive Resource Landscape">
</p>

<p align="center">
  <em>Physical resource landscape: each region shows the qubits x time footprint of a primitive variant as problem size scales. Every primitive is evaluated across 9 surface-code configurations spanning 2 QEC profiles (Gidney-Fowler, Beverland), 3 data blocks (simple, compact, fast), and 2 magic-state factories (CCZ2T, 15-to-1). Inspired by <a href="https://arxiv.org/abs/2211.07629">Beverland et al.</a></em>
</p>

### Primitives

| Primitive | Variants | Key metric |
|-----------|----------|------------|
| **QFT** | Textbook, Approximate | T-count vs n (incl. rotation synthesis) |
| **QPE** | Textbook (pluggable U) | T-count vs precision bits |
| **Arithmetic** | Add, OutOfPlaceAdder, LessThanEqual, Product, ModAdd | T-count vs bitsize |
| **QROM** | QROM, SelectSwapQROM | T-count vs table size, T/ancilla Pareto |

## Installation

Requires Python 3.10–3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/m2papierz/ftprims.git && cd ftprims
make install      # runs uv sync
```

For first-time contributors: `make setup` also installs pre-commit hooks.

## Quick start

```bash
make run-all      # full pipeline: benchmarks, verification, QREF export, sweeps
make test         # 89 integration tests
make verify       # small-scale Cirq simulation checks only
make sweeps       # parameter sweeps → CSV + PNG charts
```

`make run-all` calls `run_all.sh`, which writes organized output to:

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

All individual targets (`make run`, `make verify`, `make export`, `make sweeps`) are also available. See the Makefile for the full list.

## CLI usage

All commands go through `uv run ftprims` (or bare `ftprims` if you activated the venv manually).

### Run a benchmark

```bash
uv run ftprims run qft -p n=32                          # logical costs only
uv run ftprims run qft -p n=32 --physical               # + surface-code physical estimate
uv run ftprims run qft -p n=32 --physical --breakdown   # + per-component cost attribution
uv run ftprims run arithmetic -p n=64 -p op=mul
uv run ftprims run qrom -p data_size=256 -p variant=selectswap -p log_block_sizes=4
```

Add `--out results/qft.json` to save, `--explain` for a rule-based interpretation, or `--explain-json` to embed it in the output.

### Physical model variants

```bash
uv run ftprims run qft -p n=32 --physical \
  --profile beverland --data-block fast --factory fifteen_to_one
uv run ftprims run qft -p n=32 --physical --data-d 21             # fixed code distance
uv run ftprims run qft -p n=32 --physical --error-budget 1e-2     # custom error budget
```

Available profiles: `gidney_fowler` (default), `beverland`. Data blocks: `simple` (default), `compact`, `fast`. Factories: `ccz2t` (default), `fifteen_to_one`.

### Verify (small-scale simulation)

```bash
uv run ftprims verify qft        -p n=4 -p variant=textbook
uv run ftprims verify arithmetic -p n=4 -p op=add
uv run ftprims verify qrom       -p data_size=8 -p target_bitsize=4 -p variant=basic
```

### Export to QREF / Bartiq

```bash
# Numeric export (concrete Qualtran values — authoritative)
uv run ftprims export-qref qft -p n=32 --out qft.yaml

# Symbolic export (approximate analytic formulas for Bartiq)
uv run ftprims export-qref qft -p n=32 --symbolic --check --out qft_sym.yaml

# Compile and evaluate with Bartiq
uv run ftprims bartiq qft_sym.yaml --assign n=64
```

> [!IMPORTANT]
> Symbolic mode (`--symbolic`) exports **approximate analytic formulas** — textbook-level scaling terms that may diverge from the numeric benchmark. Use `--check` to compare. Numeric export is always authoritative.

### Configuration

```bash
uv run ftprims dump-config                       # print defaults
uv run ftprims dump-config --out config.yaml     # save, edit, then:
uv run ftprims run qft -p n=32 --config config.yaml
```

Key config options: `rotation_synthesis_epsilon` (default `1e-10`), `error_budget`, `physical_error`, `cycle_time_us`, `data_d`.

## Output format

Logical costs report two T-count metrics:

- **`t_count_direct`** — raw T-gates + 4×And gates. Accurate for pure Clifford+T circuits.
- **`t_count_ftqc`** — includes rotation synthesis cost (~11 T per rotation at default precision). This is the primary FTQC metric.

When `--breakdown` is used, the output includes per-component cost attribution with estimated FTQC T-cost and a summary identifying the dominant component. Categories: `rotations`, `qft_qpe_core`, `qrom_core`, `arithmetic_core`, `controlled_nonclifford`, `clifford_scaffolding`, `other`.

Physical estimates include `failure_prob` and `budget_satisfied` — the model never silently masks an unmet error budget. The output records which `profile`, `data_block`, and `factory` were used, so results are reproducible.

## Known limitations

- **QPE verification**: `tensor_contract` / Cirq interop fails for `TextbookQPE` (Qualtran limitation). QPE benchmarks and breakdown are correct; only small-scale unitary verification is skipped.
- **Symbolic export divergence**: symbolic formulas are textbook-level approximations. They capture dominant asymptotic scaling but may diverge significantly from Qualtran's concrete gate counts. The `--check` flag reports divergence. Numeric export is always authoritative.
- **Approximate QFT cost structure**: `ApproximateQFT` uses `AddIntoPhaseGrad` (from Qualtran's `rotations.phase_gradient` module) which decomposes to Toffoli gates with zero rotation count. The breakdown correctly reclassifies these as `controlled_nonclifford`.

## License

MIT License — see [LICENSE](LICENSE).
