[![CI](https://github.com/devqubit-labs/devqubit/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/devqubit-labs/devqubit/actions/workflows/ci.yaml)
[![Python](https://img.shields.io/pypi/pyversions/devqubit)](https://pypi.org/project/devqubit/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

# ftprims
Fault-tolerant quantum computing (FTQC) primitives benchmark suite. Built on [Qualtran](https://qualtran.readthedocs.io/) + [Cirq](https://quantumai.google/cirq) with native [QREF](https://github.com/PsiQ/qref) / [Bartiq](https://github.com/PsiQ/bartiq) export.

> [!NOTE]
> Learning project — built to deepen hands-on understanding of FTQC resource estimation, Qualtran's bloq abstractions, and the QREF/Bartiq toolchain.

> [!IMPORTANT]
> Project is under active development.
>
> ### What works
> - [x] Project scaffold, CLI skeleton, benchmark protocol & registry
>
> ### In progress
> - [ ] Arithmetic benchmark (Add, OutOfPlaceAdder, LessThanEqual, Multiplier, ModAdd)
> - [ ] QFT benchmark (Textbook + Approximate) — `build_bloq` / `logical_costs` / `verify_small`
> - [ ] QPE benchmark (Textbook, pluggable U)
> - [ ] QROM benchmark (QROM + SelectSwapQROM, T vs ancille trade-off)
> - [ ] Logical resource extraction (`get_cost_value` + `QECGatesCost`)
> - [ ] QREF export + Bartiq cost compilation
>
> ### Planned
> - [ ] Physical cost estimation (surface code model via `PhysicalCostModel`)
> - [ ] Cirq small-scale verification for all primitives
> - [ ] Parameter sweep experiments + plots (T-count vs n, qubits vs n)
> - [ ] Call-graph SVG artifacts


## What it does

Benchmark canonical FTQC building blocks, extract logical & physical resource costs via Qualtran, verify correctness with Cirq simulation, and export results as QREF programs for cost propagation in Bartiq.

### Primitives

| Primitive | Variants | Key metric |
|-----------|----------|------------|
| **Arithmetic** | Add, OutOfPlaceAdder, LessThanEqual, Multiplier, ModAdd | T-count vs bitsize |
| **QFT** | Textbook, Approximate | T-count vs n |
| **QPE** | Textbook (pluggable U, QFT⁻¹) | T-count vs precision bits |
| **QROM** | QROM, SelectSwapQROM | T-count vs table size, T/ancille trade-off |

## Quick start

```bash
uv sync

# run a benchmark
uv run ftprims run qft -p n=32

# verify (small-scale Cirq simulation)
uv run ftprims verify qft -p n=4

# export to QREF
uv run ftprims export-qref qft -p n=32 --out results/qft.qref.yaml

# compile costs with Bartiq
uv run ftprims bartiq results/qft.qref.yaml --assign n=64
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
