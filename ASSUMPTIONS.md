# Assumptions, sources and conventions

Every constant, free parameter and convention `qrepro` relies on, with its source location. The numbers are computed live by [`notebooks/reference_reproductions.ipynb`](notebooks/reference_reproductions.ipynb) and asserted in `tests/test_references_*.py`.

`L602` is a line of the paper's arXiv LaTeX source (`arxiv.org/e-print/<id>`); `anc:170` is a line of GE19's ancillary `estimate_costs.py`. `lg` is log base 2.

Every measured count, leaf ratio and tolerance band below is a property of one pinned toolchain: `qualtran==0.7.0`, `cirq-core==1.6.1`, `sympy==1.14.0`, `numpy==2.4.2`, CPython 3.11. Regression literals are pinned as exact integers so a dependency bump surfaces rather than hides.

| Key | Source | Reference |
|---|---|---|
| **Beverland** | Beverland et al., *Assessing requirements to scale to practical quantum advantage* | [arXiv:2211.07629](https://arxiv.org/abs/2211.07629) |
| **GE19** | Gidney & Ekera, *How to factor 2048 bit RSA integers in 8 hours using 20 million noisy qubits* | [arXiv:1905.09749v3](https://arxiv.org/abs/1905.09749) |
| **G2025** | Gidney, *How to factor 2048 bit RSA integers with less than a million noisy qubits* | [arXiv:2505.15917](https://arxiv.org/abs/2505.15917) |
| Cost model | Qualtran `surface_code` (Beverland model, CCZ2T factory) | `qualtran==0.7.0` |
| Factory | Gidney & Fowler, *Efficient magic state factories with a catalyzed \|CCZ⟩ to 2\|T⟩ transformation* | [arXiv:1812.01238](https://arxiv.org/abs/1812.01238) |

---

## 1. Published constants

Every literal in `references/values.py` appears below with its source location.

### Beverland — three application instances

Inputs (§V-A L1369, §V-B L1397, §V-C L1420) and targets:

| instance | Q_alg | C_min | T-states | code distance |
|---|---|---|---|---|
| quantum dynamics | 100 | 1.4401e6 ⚠️ | 6.02e5 ⚠️ | 9 (L1374) |
| quantum chemistry | 1318 | 4.1e11 (L1398) | 5.44e11 (L1398) | 17 (L1402) |
| factoring | 12581 | 1.23e10 (L1422) | 1.49e10 (L1422) | 13 (L1425) |

Model formulas, evaluated with the paper's own `A=0.53, B=5.3` (L1211) and `ε_syn = ε/3`:

```
C_min = (M_Meas + M_R + M_T) + ceil(A·lg(M_R/ε_syn) + B)·depth_R + 3·M_Tof   (D3, L1234)
R     = ceil(A·lg(M_R/ε_syn) + B)·M_R + 4·M_Tof + M_T                        (D4, L1243)
```

⚠️ **Paper defect — quantum dynamics.** Table I and §V-A print `C_min = 1.5e5` and `R = 2.4e6`; both contradict the paper's own (D3)/(D4). The measurement count alone (`M_Meas = 1.4e6`) exceeds the printed step count 10×, and the printed T-count is exactly 4× the formula's. (D3)/(D4) give `1.4401e6` and `6.02e5`, which is what Qualtran computes and what is targeted here. The same hand-evaluation reproduces the chemistry and factoring instances to the digit.

### GE19

| Constant | Value | Source |
|---|---|---|
| logical qubits | `3n + 0.002·n·lg n` → 6189 at n=2048 | abstract, L78 |
| Toffoli+T/2 | `0.3n³ + 0.0005·n³·lg n` → 2.62e9 | abstract, L78 |
| measurement depth | `500n² + n²·lg n` | abstract, L78 |
| physical error / cycle / reaction | 1e-3 / 1 µs / 10 µs | abstract, L73–75 |
| Toffoli+T/2 (billions) | 0.4 / **2.7** / 9.9 at n = 1024/2048/3072 | Table 1 |
| min volume (Mqubit·days) | 0.5 / **5.9** / 21 | Table 1 |
| **1 factory** | 1 CCZ, 16 M qubits, 6 days, 90 Mqd | Table 2 |
| **1 thread** | 14 CCZ, 19 M qubits, 0.36 day, 6.6 Mqd | Table 2 |
| **parallel** | **28 CCZ**, 20 M qubits, 0.31 day, 5.9 Mqd | Table 2 |
| n=2048 optimum | d1=15, d2=27, g_mul=g_exp=5, g_sep=1024, **retry risk 31%**, 20 Mqubits, **5.1 hr/run**, 4.1 Mqd/run, 5.9 Mqd expected | Table 3 |

Modular-exponentiation regimes; `n_e` is the number of exponent qubits, 2n for Shor and 1.5n for Ekera–Hastad (L731):

| regime | formula | source | at n=2048 | implemented by |
|---|---|---|---|---|
| reference | `20·n_e·n²` | §2.2 L522 | 3.436e11 (n_e=2n) | Qualtran `ModExp`, at half the constant — see §3 |
| coset | `8·n_e·n²` | §2.4 L547 | 1.374e11 (n_e=2n) | — (formula only) |
| windowed | `24·n_e·n²/lg²n` | §2.5 L602 | 2.556e9 (n_e=1.5n) | `algorithms/windowed_factoring.py` — see §6 |

Construction parameters for the windowed regime, all published by GE19:

| parameter | value | source |
|---|---|---|
| `g_exp`, `g_mul` (`w_e`, `w_m`) | 5, 5 | §2.7 L690 |
| `g_pad` (coset padding) | `2 lg n + lg n_e + 10` → 40 / 43 / 45 at n = 1024/2048/3072 | L690 |
| `g_sep` (carry-runway separation) | 1024 | L690, Table 3 — **excluded**, see §6 |
| `n_e` | `ceil(1.5·n)` (Ekera–Hastad) | L482 |
| lookup / addition / unlookup cost | `2^(w_e+w_m)` / `2N` / `2·√(2^(w_e+w_m))` | L594 / L593 / L595 |

Attribution from reference (n_e=2n) to windowed (n_e=1.5n), total 134.4×: coset **2.5×** × windowing **40.3×** (`lg²n/3`) × exponent **1.33×**.

### G2025

| Constant | Value | Source |
|---|---|---|
| Toffolis at n=2048 | 6.5e9 | Table 5 |
| logical qubits | 1399 | Table 5 |
| expected shots | 9.2 | Table 5 |
| published target | < 1e6 physical qubits, < 1 week | abstract |
| physical assumptions | identical to GE19 | abstract |
| qubit reduction sources | approximate residue arithmetic; yoked surface codes; magic state cultivation | abstract |

Only the algorithmic source (fewer logical qubits) is representable in a CCZ2T model. Yoked codes and cultivation have no representation in the open cost models checked (Qualtran, Azure QRE, pyLIQTR), so G2025's published target is decomposed rather than reproduced.

---

## 2. Free parameters

Parameters the source papers do not fix, plus the published values this repo treats as inputs rather than choices. None should be quoted without its value.

| Parameter | Default | Where | Sensitivity |
|---|---|---|---|
| `rotation_synthesis_epsilon` | `1e-10` → ~100 T/rotation via `T ≈ 3·log₂(1/ε)` | `config.py` | Large. QFT textbook/approximate T-equivalent ratio at n=32 is 17.3× here, 2.6× at Qualtran's looser default. `sweep_rotation_epsilon.py` |
| `error_budget` (GE19) | `0.31` | `values.py` | Moderate. Published, not a proxy — see §3. `sweep_ge19_physical.py` |
| `w_e`, `w_m` (windowed) | `5`, `5` | `values.py` | Large: 1.63e9 → 1.37e10 across the grid. Published (L690). `sweep_windowed_modexp.py` |
| `g_pad` (windowed) | `2 lg n + lg n_e + 10` | `windowed_factoring.py` | Low on count; it only widens the registers. Published (L690). |
| `g_sep` / carry runways (windowed) | `None` (off) | `values.py` | +3.5% at GE19's `g_sep=1024`. Excluded — see §6. |
| `input_slack_bits` (windowed) | `2` | `windowed_factoring.py` | ≤0.5%. From `anc:170`; the `+2` is unexplained in the paper text — see §6. |
| `n_factories` (GE19 parallel) | `28` | `values.py` | Large on runtime. Published (Table 2). `sweep_ge19_physical.py` |
| CCZ2T `d1`/`d2` | searched over `iter_ccz2t_factories()` | `physical.py` | Budget-dependent. Pinning Qualtran's construction defaults (15, 31) moves the GE19 1-factory row ~12% at `error_budget=0.5`, ~0.1% at the default 0.31, and produces a spurious infeasibility at 0.1. `sweep_ge19_physical.py` records the selected factory per row in `factory_l1_d` / `factory_l2_d`. |
| Toffoli convention | `per_run` | `decomposition.py` | Moderate — see §3. Both computed. |
| data block / QEC profile | `simple` / `gidney_fowler` | `physical.py` | Low for GE19: `compact` is identical on qubits, `fast` +35%. |
| uniform code distance | one `d` for all data qubits | `physical.py` | Structural. GE19 uses separate `c_mul`/`c_exp` distance factors (Table 3: both 5), which the model cannot represent. |
| routing / carry runways | not modelled in the *physical* layer | `physical.py` | Structural there. Representable in the windowed construction (`runway_sep`) but excluded from the count — see §6. |
| Beverland ε split | `ε_syn = ε/3` | Qualtran | Immaterial: `ε/3` vs `ε` moves the synthesis multiplier 20 → 19 (~5%). |

---

## 3. Conventions

**Error budget.** GE19 L1086 defines its retry risk ε as an upper bound on *"the overall probability of errors occurring"*; Qualtran documents `error_budget` as *"the acceptable chance of an error occurring at any point"*. Same quantity, so GE19's published ε = 31% (Table 3) is used directly and no proxy is required.

**Runtime: per run vs expected.** `qrepro` emits a per-run duration and has no retry model. GE19 Table 2 columns are *expected* runtime and volume; Table 3 columns are *per run*. L1096 gives the conversion (*"The `t/(1−ε)` factor is the expected runtime"*), under which the two tables agree exactly:

```
5.1 hr / (1 − 0.31) = 7.39 hr = 0.308 day  →  Table 2's 0.31 day   ✓
4.1 Mqd / (1 − 0.31) = 5.94 Mqd            →  Table 2's 5.9 Mqd     ✓
```

Compare per-run to Table 3 and converted-expected to Table 2; never across.

**Toffoli counts.** GE19 Table 1 is per run (L1788: *"does not account for the chance of retrying"*). G2025 Table 5 is expected per factoring, already aggregating E(shots) = 9.2 (Table 5 caption). The decomposition normalises both onto one convention:

- `per_run` — GE19 as-is; G2025 ÷ 9.2.
- `expected` — GE19 ÷ (1 − 0.31); G2025 as-is.

**Magic-state counting.** Costs are aggregated as `n_ccz` = And + Toffoli + CSwap (`GateCounts.total_t_and_ccz_count`), never from `and_bloq` alone: each of the three is one CCZ, and `ModExp` puts `n_e·n` of them in `cswap`. The aggregation is called with `ts_per_rotation=0` so rotations stay out of the raw-T total; `qrepro` synthesises them separately at the configured ε and would otherwise double-count them.

**T-count metrics.** `t_count_direct` = raw T + 4×`n_ccz`. `t_count_ftqc` adds rotation synthesis at the configured ε. Rotation *counts* are ε-independent; T-equivalent *ratios* are not.

**Which construction `ModExp` implements.** Qualtran's `ModExp` docstring states it follows GE19's *"reference implementation"*. Its measured `n_ccz/(n_e·n²)` converges to a constant — 10.15625 at n=32 → 10.00244 at n=2048, with no `1/lg²n` factor — which identifies the non-windowed regime from the scaling alone. That constant is 10, half the 20 GE19 derives (§2.2 L522) for the same construction. The factor of two is the adder primitive, not a missing pass: same structure, same two passes (the unmultiply is present at multiplicity 2 in `CModMulK`), same magic-state currency, but GE19 prices every addition with Cuccaro's adder (`2n` Toffolis, L520) where Qualtran's `Add` is Gidney's temporary-AND adder ([arXiv:1709.06648](https://arxiv.org/abs/1709.06648), `n−1` ANDs, carries uncomputed by measurement). Closed form `n_e·2n(5n+2) + n_e·n = 10·n_e·n² + 5·n_e·n` (`n_ccz`), exact against the call graph at every n in {32…2048}. The coefficient 10 is fitted, so its agreement is a regression pin rather than evidence; the evidence is the scaling and the leaf-level reconciliation.

---

## 4. Achieved deviations

Live against `qualtran==0.7.0`; asserted in `tests/test_references_*.py`.

### Beverland (tolerance `rel=0.01`)

| instance | c_min | t_states | d |
|---|---|---|---|
| quantum dynamics | 1.4401e6 (+0.00%) | 6.02e5 (+0.00%) | 9 ✓ |
| quantum chemistry | 4.1176e11 (+0.43%) | 5.4521e11 (+0.22%) | 17 ✓ |
| factoring | 1.2270e10 (−0.24%) | 1.4920e10 (+0.13%) | 13 ✓ |

Qualtran ships the Beverland model, so this validates wiring, not independent convergence.

### GE19 logical

| quantity | qrepro | GE19 | dev |
|---|---|---|---|
| logical qubits | 6189 | 6189 (formula) | input, not a reproduction |
| Toffoli | 2.624e9 | 2.7e9 (Table 1) | −2.9% |
| Qualtran `ModExp` | 1.718e11 | — | **63.6×** above Table 1 |

Both `ModExp` literals in `values.py`, measured at n=2048:

| literal | value | closed form |
|---|---|---|
| `modexp_qualtran_toffoli` (`n_ccz`) | 171,840,634,880 | `10·n_e·n² + 5·n_e·n` |
| `modexp_qualtran_and_only` (`and_bloq`) | 171,832,246,272 | `10·n_e·n² + 4·n_e·n` |

They differ by the `n_e·n = 8,388,608` CSwaps, i.e. 0.0049%. `n_ccz` is the authoritative total; the `and_bloq` figure is pinned only so the two cannot drift apart unnoticed.

### GE19 physical (tolerance `rel=0.18`)

Grid search for both rows, `error_budget=0.31`, nf = 1 and 28.

| row | metric | qrepro | GE19 | dev |
|---|---|---|---|---|
| 1 factory | qubits | 17.97 M | 16 M (Tbl 2) | **+12.3%** |
| 1 factory | runtime, per run | 127.88 hr | 144 hr (Tbl 2, *expected*) | −11.2% ⚠️ |
| parallel (28f) | qubits | 17.26 M | 20 M (Tbl 2/3) | **−13.7%** |
| parallel (28f) | runtime, per run | 4.567 hr | 5.1 hr (Tbl 3) | **−10.5%** |
| parallel (28f) | runtime, expected | 6.619 hr | 7.44 hr (Tbl 2) | **−11.0%** |

At GE19's own budget and factory count the search selects **d1=15, d2=27** — exactly Table 3's factory. GE19's design sits inside Qualtran's CCZ2T family; what differs is the search objective, GE19 minimising skewed expected volume `s^1.2·t/(1−ε)`.

⚠️ The 1-factory runtime comparison is unresolvable: GE19 publishes only an expected runtime for that scenario, and Table 3's per-run figure covers the n=2048 optimum only. Per-run against their expected reads −11.2%; converting ours at the optimum's 31% retry risk gives 185.3 hr and +28.7%. Resolving it needs a retry risk GE19 does not publish.

### 2019 → 2025 decomposition

`error_budget=0.31`, both papers through the same grid search at the same factory count.

| factories | `per_run` | `expected` |
|---|---|---|
| 1 | 17.97 → 3.19 M = **5.64×** | 17.97 → 3.69 M = **4.87×** |
| 16 | 17.64 → 4.55 M = **3.88×** | 17.64 → 5.48 M = **3.22×** |
| 28 | 17.26 → 5.99 M = **2.88×** | 19.15 → 7.29 M = **2.63×** |

Range 2.63× – 5.64×; factory count spreads it far more than the convention choice. The model floors out in the millions against G2025's published < 1 M, the residual being the QEC stack (yoked codes, cultivation) that this cost model cannot express. The chain does not compose to the published ~20×, because the model puts GE19 at 17.26–19.15 M against its published 20 M.

---

## 5. Known limitations

- **QPE verification** — `tensor_contract` / Cirq interop fails for `TextbookQPE` (Qualtran limitation). Costs and breakdown are correct; only small-scale unitary verification skips.
- **Symbolic export** — analytic formulas are textbook-level approximations and may diverge from concrete counts. `--check` reports divergence; numeric export is authoritative.
- **`ApproximateQFT`** — decomposes via `AddIntoPhaseGrad` to Toffolis with zero rotation count, reported under `toffoli` rather than `and_bloq`. The breakdown reclassifies these as `controlled_nonclifford`.
- **No retry model** — the physical layer emits a per-run duration only (§3).
- **No yoked codes or magic-state cultivation** — G2025's published target is structurally out of reach; the gap is measured, not worked around.
- **Logical qubits for factoring are analytic, not traced** — see §6.
- **The coset representation is not simulated** — correctness is asserted on the exact `ModAdd` variant; the padded configuration the counts are built from is not. See §6.

---

## 6. GE19's windowed construction (`algorithms/windowed_factoring.py`)

Stock `ModExp` implements GE19's reference implementation (§3), which is why it lands 63.6× above Table 1. `windowed_factoring.py` builds what GE19 actually costs — windowed exponentiation (§2.5) over windowed multiplication (§2.5) over the coset representation (§2.4) — out of stock Qualtran leaves, giving a second derivation of the 2.7e9 regime that does not go through the paper's closed forms.

```
WindowedModExp             ceil(n_e/w_e) uncontrolled multiplications  (L590)
└── WindowedModMul         2 multiply-add passes                        (anc:171, L694)
    └── WindowedMultiplyAdd  ceil((n+g_pad+2)/w_m) lookup additions      (L590)
        └── LookupAddition
            ├── QROAMClean(log_block_sizes=(0,))   lookup      (L594)
            ├── Add(QUInt(width))                  addition    (L593)
            └── QROAMClean(...).adjoint()          unlookup    (L595)
```

GE19 §2.4 L542 prices the coset representation; the construction is Zalka's ([*Shor's algorithm with fewer (pure) qubits*](https://arxiv.org/abs/quant-ph/0601097) §4 L281), which represents `k mod N` as an equal superposition over `jN + k` so that a plain non-modular adder preserves the residue and the modular reduction never has to be made reversible. Both citations belong together, as they do in Qualtran's own unmerged coset bloq.

### Leaf costs

Measured at `width = 2091` (= n + g_pad at n=2048):

| piece | GE19 assumes | source | Qualtran bloq | measured `n_ccz` | ratio |
|---|---|---|---|---|---|
| lookup, k=8 / 10 / 12 | `2^k` | L594 | `QROAMClean` | 254 / 1022 / 4094 | 1.008 / 1.002 / 1.000 |
| unlookup, k=8 / 10 / 11 / 12 | `2√(2^k)` | L595 | `QROAMCleanAdjointWrapper` | 28 / 60 / 92 / 124 | 1.143 / 1.067 / 0.984 / 1.032 |
| addition, N=2091 | `2N` | L593 | `Add(QUInt(N))` | **2090** | **2.001** |

`QROAMClean` is the only correct lookup primitive here: `QROM.adjoint()` does not use measurement-based uncomputation (1022 vs 1022 at k=10, 16× GE19's assumption), and `SelectSwapQROM` costs 2× `QROM` at these shapes.

### Magic-state field split

`QECGatesCost` splits the cost across two fields: lookup and adder land in `and_bloq`, the entire unlookup term lands in `toffoli` (1.9% of the count at (5,5), 1.35–2.2% across the grid). `cswap` is zero by construction. Extraction therefore goes through `total_t_and_ccz_count()['n_ccz']` in `factoring.modexp_logical_costs`, the single entry point for both this construction and the stock `ModExp`. `test_windowed_uses_both_gate_fields` guards the split; `test_modexp_and_only_count_pinned` pins the `and_bloq` figure so the two currencies cannot drift.

### Achieved counts

| n | window | total CCZ | adder | lookup | unlookup | ÷ Table 1 | **bridged** ÷ Table 1 |
|---|---|---|---|---|---|---|---|
| 1024 | (5,4) | 2.6595e8 | 65.7% | 31.5% | 2.7% | 0.665 | **1.102** |
| 2048 | (5,5) | 1.6348e9 | 65.9% | 32.2% | 1.9% | 0.605 | **1.004** |
| 3072 | (5,5) | 4.8305e9 | 74.2% | 24.3% | 1.4% | 0.488 | **0.850** |

The window is the per-`n` cost minimum over `w_e, w_m ∈ [3,8]`, `w_m ≤ w_e` (`sweep_windowed_modexp.py` writes the whole grid). At n=2048 and 3072 that is GE19's published `(5,5)`; at n=1024 it is `(5,4)`, which lands further from Table 1 than `(5,5)` would (0.665 vs 0.707) — the selection is cost-driven, not target-driven.

**Bridged** doubles the adder term and only the adder term, converting Qualtran's Gidney temporary-AND adder ([arXiv:1709.06648](https://arxiv.org/abs/1709.06648), `N−1` ANDs) to GE19's Cuccaro convention (`2N` Toffolis, L520). It is reported alongside the unbridged figure and never folded into it, and moves n=2048 from 0.605 to 1.004 × Table 1.

Causes of the remaining gap, in order of size:

1. **Adder primitive**, ×2 on ~66% of the count. Dominant; bridged above.
2. **GE19's parameter optimizer.** Table 1 is the minimum of a multi-parameter grid ranked on spacetime volume, not Toffoli count (`anc:357–367`), rounded up to two significant digits. Replicating it would be the free-parameter tuning this repo forbids, so it is not replicated; it is worth roughly +5% / +2% / −13% at n = 1024/2048/3072, which is why n=3072 stays 15% low even bridged.
3. **Carry runways excluded** — below.
4. **Unlookup constant.** Qualtran's `ceil(N/K)+K−4` vs GE19's `2√N`: ±7% on a term worth 1.9%, so under 0.15% of the total.

**The sweep is a triangle.** `WINDOW_GRID` enforces `w_m ≤ w_e`, visiting 21 of the 36 cells. The count factorises exactly as

```
2 · ceil(n_e/w_e) · ceil((n + g_pad + 2)/w_m) · C(w_e + w_m, width)
```

— one lookup addition per (exponent window × factor window × pass), each costing whatever a fused `w_e + w_m` address costs at that register width — verified exact against the call graph on all 36 cells at n = 1024/2048/3072. The pair enters only through the sum and the two ceilings, so swapping `w_e` and `w_m` is free apart from rounding (measured asymmetry ≤ 0.45% / 0.18% / 0.04%) and the triangle covers the square. The constraint costs one cell: the unconstrained argmin at n=1024 is `(4,5)`, 0.073% below the swept `(5,4)`, and `(5,5)` at n=2048 and 3072 either way.

### Regime identification

`total/(n_e·n²)` must fall like `1/lg²n`; the non-windowed regime gives a constant (§3). Measured at the best window per n:

| n | 128 | 256 | 512 | 1024 | 2048 | 4096 | 8192 |
|---|---|---|---|---|---|---|---|
| coefficient | 0.5010 | 0.3180 | 0.2185 | 0.1651 | 0.1269 | 0.1032 | 0.0850 |
| × lg²n | 24.55 | 20.35 | 17.70 | 16.51 | **15.35** | 14.87 | 14.37 |

The coefficient falls 5.89× while lg²n rises 3.45× (49 → 169), leaving the residual 1.71× drift the second row shows. In Qualtran's adder currency the analogue of L602's `24·n_e·n²/lg²n` is `16·n_e·n²/lg²n` — the `24 = 2×4×3` has its `3 = 2 adder + 1 lookup` become `2 = 1 + 1` — against which measured ratios are 1.032 / 0.960 / 0.932. This test uses no external number and separates windowed from non-windowed on scaling alone.

### Readings where GE19 is ambiguous

Each is a reading, not a transcription: consistent with every cost equation GE19 prints, but not stated outright by it.

- **Window nesting is given by reference, not construction.** L583 defers to [gidney2019windowedarithmetic] for *"the exact details of this nested windowed arithmetic construction"*, so how the `w_e` exponent bits and `w_m` factor bits concatenate into one `2^(w_e+w_m)`-entry address, and whether the exponent window is re-looked-up per multiply-add or hoisted, is not in GE19. Reading taken: one fused address per lookup addition, exponent window in the high `w_e` bits, one table per multiply-add — the only reading that yields the `2^(w_e+w_m)` per-lookup cost of L591/L594.
- **The register swap after a two-pass multiplication.** L514 treats it as free bookkeeping; Qualtran's `CModMulK` emits a real `CSwap` because its multiplications are controlled (`mod_multiplication.py:227-229`). GE19's are uncontrolled (L590), so no swap is emitted and `cswap == 0` by construction (`test_windowed_emits_no_cswap`). Emitting one would add `n_e/w_e · width ≈ 1.3e6` CCZ (+0.08%) and misrepresent the construction.
- **`log_block_sizes=(0,)`** pins plain unary iteration, which is what L594 costs. Qualtran's auto-selection is cheaper at large `k` (8190 vs 16382 CCZ at k=14) but buys that with junk ancilla registers GE19 does not budget. Not swept.
- **L712 prints `2^(g_exp + g_pad)`** where L591, L594, L601 and `anc:292` have `2^(g_exp + g_mul)`. Read as a typo for `g_mul`, which the ancillary code confirms. Flagged because L712 alone yields a different formula.
- **The `n_e/w_e` boundary.** `n_e = 1.5n` need not divide by `w_e` (3072/5 = 614.4). Whether the tail window needs a smaller table is unresolved in the paper; the built bloq costs it at full table width.

### Divergences from GE19

- **Carry runways (§2.6) are excluded from the count.** They cut addition depth, not magic-state count. `runway_sep` is a constructor parameter (default `None`), so the exclusion is auditable and reversible. At GE19's `g_sep=1024` they cost +3.5% here against +1.6% in GE19's ancillary model, because widening the register also widens the windowing over it (more lookup additions), which `anc:170` does not charge. Recorded rather than reconciled; runways are outside the reported counts either way.
- **Nested vs single `ceil`.** `anc:171` applies one `ceil` over the whole `n_e·2·(n+g_pad+2)/(w_e·w_m)` product; the built bloq applies `ceil` at each nesting level, which is structurally what the construction does. Worth +0.0 to +0.5%.
- **`input_slack_bits = 2`**, from `anc:170` and unexplained in the paper text; setting it to 0 moves the count by −0.37% / 0.00% / 0.00%. This is also the one structural divergence between the costed and built objects: `n_lookup_additions` charges `ceil((width+2)/w_m)` while `n_factor_windows`, what `build_composite_bloq` emits, is `ceil(width/w_m)`. The slack bits belong to no register, so the decomposition cannot represent them and refuses to run while they are set. Kept rather than reconciled. The excess is one lookup addition per multiply-add at n=1024 and none at n=2048/3072 — the whole of the −0.37% — and has no assertion of its own; the pinned totals cover it.
- **The GE19 ancillary-model literals** in `GE19_WINDOWED["anc_model_toffoli"]` are GE19's own `anc/estimate_costs.py` model, Toffoli-count path only with the physical layer stripped, evaluated at matched parameters (`g_exp = g_mul = 5`, `g_sep = 1024`, `g_pad` per n). They were transcribed by a probe not committed here, so unlike every other literal they cannot be re-derived from this repository; the transcription was cross-checked against Table 1 (+5.3% / +2.0% / −12.9%) and against the paper's three closed forms. They carry weaker provenance and are asserted in a band, not tightly. Table 1 is the authoritative comparison.

### Correctness

Asserted on the exact variant only — `coset_padding=0` with `ModAdd`, the alternative way of handling the modular reduction. The checks are classical-action checks through the real decomposition (`decompose_bloq()` → `call_classically`), so they walk the wired circuit rather than the call graph, and they are permutation-level: unlike `make verify`'s `tensor_contract` checks on the primitives they cannot detect a relative-phase error.

- `LookupAddition` against `y + table[addr]`, address restored.
- `WindowedMultiplyAdd` against `y + x·k mod N`, exhaustively.
- `WindowedModMul` against `x·k mod N`, with `bb.free` proving the unmultiply clears the source.
- `WindowedModExp` against `pow(base, e, mod)` for every exponent at three moduli. Window-indexing errors, the likely bug in a nested windowed construction, surface here as a wrong residue.

**The coset representation is not simulated.** The costed configuration — `exact_modular=False` with `coset_padding > 0`, the plain non-modular `Add` the reported counts are built from — has no correctness test, leaving two properties analytic. First, that the padding absorbs the accumulated multiples of N: every lookup addition contributes a term canonicalised into `[0, N)` (L667-670), so the register holds a representative of `y + x·k mod N` rather than the residue, and `g_pad` keeps it from wrapping. Second, the superposition itself: preparing `√(2^-g_pad) Σⱼ|jN+k⟩` has no Qualtran primitive, and only that superposition makes a register holding `jN` indistinguishable from `|0⟩` — which is why `WindowedModMul` cannot `bb.free` its source in the costed configuration and the two-pass clear is asserted in the exact variant instead. Neither property affects the gate count.

### Tolerance bands

Each band was set from the measured deviation with headroom, and its cause is named above. Literals live in `GE19_WINDOWED_TOL` / `GE19_WINDOWED_ACHIEVED` (`references/values.py`); the assertions are in `tests/test_references_ge19.py`.

| assertion | band | achieved (n = 1024 / 2048 / 3072) |
|---|---|---|
| unbridged ÷ Table 1 | [0.60,0.75] / [0.55,0.68] / [0.43,0.58] | 0.665 / 0.605 / 0.488 |
| bridged ÷ Table 1 | [0.95,1.20] / [0.95,1.10] / [0.78,0.95] | 1.102 / **1.004** / 0.850 |
| bridged ÷ GE19 `anc` model | [0.94, 1.08] | 1.047 / 0.985 / 0.976 |
| vs `16·n_e·n²/lg²n` | `rel=0.10` | 1.032 / 0.960 / 0.932 |
| `coeff(2048)·lg²2048` | [14, 17] | **15.35** |
| adder share at n=2048 | [0.60, 0.72] | 0.659 |
| runway uplift at `g_sep=1024` | `abs=0.002` | +3.53% |
| call-graph node count | `< 30` | 14 |

Everything else is asserted exactly: the total and each of the three terms per n, their sum and the bridged identity, `cswap == 0`, both gate fields non-zero, the falloff coefficient strictly decreasing over {128…8192}, the grid argmin `(5,5)`, convexity in `w_e + w_m`, windowed × 50 < stock `ModExp` (achieved 105.1×), the classical-action residues, and fail-closed parameter validation.

### Not addressed

- **Logical qubits from the bloq.** The count comes from GE19's analytic `3n + 0.002·n·lg n`, as it does for `ModExp`: `QubitCount` is O(gates) and will not terminate at n=2048. Deriving it from the bloq needs the lookup-output width and the measurement-based unlookup's ancillae, and may need the semi-classical QFT's exponent recycling as well.
- **Measurement depth** (`500n² + n²lg n`). `QECGatesCost` has no depth notion that maps onto GE19's reaction-limited model. Qualtran `main` gained `surface_code.flasq.MeasurementDepth` / `TotalMeasurementDepth` on 2026-07-28, but it is unusable here twice over: no release tag through the pinned `v0.7.0` contains `flasq`, and it reaches the circuit DAG by decomposing, which this costing path withholds (every iteration collapses onto one symbolic node, and the decomposition refuses to run while `input_slack_bits` is set).
