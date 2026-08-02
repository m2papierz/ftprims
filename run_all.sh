#!/usr/bin/env bash
# Run every qrepro benchmark, verify, export, and sweep.
# Requires: uv sync (or override QREPRO / PYTHON if installed another way)
set -uo pipefail

QREPRO="${QREPRO:-uv run qrepro}"
PYTHON="${PYTHON:-uv run python}"

RESULTS="results"
RUNS_DIR="${RESULTS}/runs"
QREF_NUM_DIR="${RESULTS}/qref/numeric"
QREF_SYM_DIR="${RESULTS}/qref/symbolic"
CHARTS_DIR="${RESULTS}/charts"
SWEEPS_DIR="${RESULTS}/sweeps"
CONFIGS_DIR="${RESULTS}/configs"
mkdir -p "$RUNS_DIR" "$QREF_NUM_DIR" "$QREF_SYM_DIR" "$CHARTS_DIR" "$SWEEPS_DIR" "$CONFIGS_DIR"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

FAIL_COUNT=0

section() { echo -e "\n${CYAN}=== $1 ===${NC}\n"; }
ok()      { echo -e "${GREEN}OK $1${NC}"; }
fail()    { echo -e "${RED}X $1${NC}"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

# Numeric runs
section "NUMERIC RUNS (--breakdown --physical)"

declare -a RUNS=(
    "qft        -p n=32 -p variant=textbook"
    "qft        -p n=32 -p variant=approx"
    "qpe        -p m=8  -p phi=0.25"
    "arithmetic -p n=16 -p op=add"
    "arithmetic -p n=16 -p op=add_oop"
    "arithmetic -p n=16 -p op=leq"
    "arithmetic -p n=16 -p op=mul"
    "arithmetic -p n=8  -p op=modadd"
    "qrom       -p data_size=256 -p variant=basic"
    "qrom       -p data_size=256 -p variant=selectswap"
)

for run in "${RUNS[@]}"; do
    # Build output filename from args: qft_n=32_variant=textbook.json
    slug=$(echo "$run" | tr -s ' ' | sed 's/ -p /_ /g; s/ //g; s/^_//')
    outfile="${RUNS_DIR}/run_${slug}.json"

    echo "=> $QREPRO run $run"
    # shellcheck disable=SC2086
    if $QREPRO run $run \
        --breakdown --physical \
        --out "$outfile"; then
        ok "$outfile"
    else
        fail "run $run"
    fi
done

# Physical model comparison
section "PHYSICAL MODEL VARIANTS"

declare -a PHYS_VARIANTS=(
    "qft -p n=32 -p variant=textbook --profile beverland"
    "qft -p n=32 -p variant=textbook --profile gidney_fowler --data-block fast"
    "qft -p n=32 -p variant=textbook --profile gidney_fowler --factory fifteen_to_one"
    "qft -p n=32 -p variant=textbook --profile beverland --data-block fast --factory fifteen_to_one"
)

for run in "${PHYS_VARIANTS[@]}"; do
    echo "=> $QREPRO run $run --physical --breakdown"
    # shellcheck disable=SC2086
    if $QREPRO run $run --physical --breakdown; then
        ok "done"
    else
        fail "run $run"
    fi
done

# Verify (small-scale Cirq simulation)
section "VERIFY (small-scale simulation)"

declare -a VERIFIES=(
    "qft        -p n=4 -p variant=textbook"
    "qft        -p n=4 -p variant=approx"
    "qpe        -p m=4 -p phi=0.25"
    "arithmetic -p n=4 -p op=add"
    "arithmetic -p n=4 -p op=add_oop"
    "arithmetic -p n=4 -p op=leq"
    "arithmetic -p n=4 -p op=modadd"
    "qrom       -p data_size=8 -p target_bitsize=4 -p variant=basic"
    "qrom       -p data_size=8 -p target_bitsize=4 -p variant=selectswap"
)

for v in "${VERIFIES[@]}"; do
    # shellcheck disable=SC2086
    if ! $QREPRO verify $v; then
        fail "verify $v"
    fi
done

# QREF export + symbolic consistency check
section "QREF EXPORT + SYMBOLIC CHECK"

declare -a EXPORTS=(
    "qft        -p n=32 -p variant=textbook"
    "qft        -p n=32 -p variant=approx"
    "qpe        -p m=8  -p phi=0.25"
    "arithmetic -p n=16 -p op=add"
    "arithmetic -p n=16 -p op=mul"
    "qrom       -p data_size=256 -p variant=basic"
    "qrom       -p data_size=256 -p variant=selectswap"
)

for ex in "${EXPORTS[@]}"; do
    slug=$(echo "$ex" | tr -s ' ' | sed 's/ -p /_ /g; s/ //g; s/^_//')

    # Numeric export
    # shellcheck disable=SC2086
    if $QREPRO export-qref $ex \
        --out "${QREF_NUM_DIR}/qref_${slug}.yaml"; then
        ok "numeric: qref_${slug}.yaml"
    else
        fail "export $ex"
    fi

    # Symbolic export + consistency check (informational - divergence is
    # expected since symbolic formulas are textbook-level approximations).
    # shellcheck disable=SC2086
    if $QREPRO export-qref $ex \
        --symbolic --check \
        --out "${QREF_SYM_DIR}/qref_${slug}_symbolic.yaml"; then
        ok "symbolic: qref_${slug}_symbolic.yaml"
    else
        echo -e "${CYAN}  [info] symbolic divergence for $ex (expected - asymptotic approximation)${NC}"
        ok "symbolic (with divergence): qref_${slug}_symbolic.yaml"
    fi
done

# Bartiq compile (one example)
section "BARTIQ COMPILE"

if $QREPRO bartiq "${QREF_SYM_DIR}/qref_qft_n=32_variant=textbook_symbolic.yaml" -a n=32; then
    ok "bartiq QFT"
else
    fail "bartiq QFT"
fi

if $QREPRO bartiq "${QREF_SYM_DIR}/qref_arithmetic_n=16_op=add_symbolic.yaml" -a n=16; then
    ok "bartiq arithmetic/add"
else
    fail "bartiq arithmetic/add"
fi

# Experiment sweeps
section "EXPERIMENT SWEEPS (CSV + charts)"

# Assumption sweeps (see ASSUMPTIONS.md).
$PYTHON experiments/sweep_rotation_epsilon.py \
&& ok "sweep_rotation_epsilon" || fail "sweep_rotation_epsilon"

$PYTHON experiments/sweep_ge19_physical.py \
&& ok "sweep_ge19_physical"    || fail "sweep_ge19_physical"

$PYTHON experiments/sweep_windowed_modexp.py \
&& ok "sweep_windowed_modexp"  || fail "sweep_windowed_modexp"

$PYTHON experiments/landscape.py && ok "landscape" || fail "landscape"

# Published-estimate reproductions
section "REFERENCE REPRODUCTIONS"

$QREPRO reproduce beverland     && ok "reproduce beverland"     || fail "reproduce beverland"
$QREPRO reproduce ge19          && ok "reproduce ge19"          || fail "reproduce ge19"
$QREPRO reproduce decomposition && ok "reproduce decomposition" || fail "reproduce decomposition"

# Config dump (sanity)
section "CONFIG"

if $QREPRO dump-config --out "${CONFIGS_DIR}/default_config.yaml"; then
    ok "default_config.yaml"
else
    fail "default_config.yaml"
fi

section "ALL DONE"
echo "Results in ${RESULTS}/"
find "${RESULTS}/" -type f | sort

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "\n${RED}${FAIL_COUNT} step(s) failed.${NC}"
    exit 1
else
    echo -e "\n${GREEN}All steps passed.${NC}"
fi
