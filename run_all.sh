# Run every ftprims benchmark, verify, export, and sweep.
set -euo pipefail

RESULTS="results"
mkdir -p "$RESULTS"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

section() { echo -e "\n${CYAN}═══ $1 ═══${NC}\n"; }
ok()      { echo -e "${GREEN}✓ $1${NC}"; }
fail()    { echo -e "${RED}✗ $1${NC}"; }

# Numeric runs
section "NUMERIC RUNS (--breakdown --physical --explain-json)"

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
    slug=$(echo "$run" | tr -s ' ' | sed 's/ -p /_ /g; s/ /_/g; s/^_//')
    outfile="${RESULTS}/run_${slug}.json"

    echo "=> ftprims run $run"
    # shellcheck disable=SC2086
    ftprims run $run \
        --breakdown --physical --explain-json \
        --out "$outfile" \
    && ok "$outfile" || fail "run $run"
done

# ─Physical model comparison
section "PHYSICAL MODEL VARIANTS"

declare -a PHYS_VARIANTS=(
    "qft -p n=32 -p variant=textbook --profile beverland"
    "qft -p n=32 -p variant=textbook --profile gidney_fowler --data-block fast"
    "qft -p n=32 -p variant=textbook --profile gidney_fowler --factory fifteen_to_one"
    "qft -p n=32 -p variant=textbook --profile beverland --data-block fast --factory fifteen_to_one"
)

for run in "${PHYS_VARIANTS[@]}"; do
    echo "=> ftprims run $run --physical --breakdown"
    # shellcheck disable=SC2086
    ftprims run $run --physical --breakdown \
    && ok "done" || fail "run $run"
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
    ftprims verify $v || fail "verify $v"
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
    slug=$(echo "$ex" | tr -s ' ' | sed 's/ -p /_ /g; s/ /_/g; s/^_//')

    # Numeric export
    # shellcheck disable=SC2086
    ftprims export-qref $ex \
        --out "${RESULTS}/qref_${slug}.yaml" \
    && ok "numeric: qref_${slug}.yaml" || fail "export $ex"

    # Symbolic export + consistency check
    # shellcheck disable=SC2086
    ftprims export-qref $ex \
        --symbolic --check \
        --out "${RESULTS}/qref_${slug}_symbolic.yaml" \
    && ok "symbolic: qref_${slug}_symbolic.yaml" || fail "symbolic export $ex"
done

# Bartiq compile (one example)
section "BARTIQ COMPILE"

ftprims bartiq "${RESULTS}/qref_qft_n=32_variant=textbook_symbolic.yaml" -a n=32 \
&& ok "bartiq QFT" || fail "bartiq QFT"

ftprims bartiq "${RESULTS}/qref_arithmetic_n=16_op=add_symbolic.yaml" -a n=16 \
&& ok "bartiq arithmetic/add" || fail "bartiq arithmetic/add"

# Experiment sweeps
section "EXPERIMENT SWEEPS (CSV + charts)"

python experiments/sweep_qft.py        && ok "sweep_qft"
python experiments/sweep_qpe.py        && ok "sweep_qpe"
python experiments/sweep_arithmetic.py && ok "sweep_arithmetic"
python experiments/sweep_qrom.py       && ok "sweep_qrom"

python experiments/compare_physical_configs.py qft n=16 variant=textbook \
&& ok "compare_physical_configs"

# Config dump (sanity)
section "CONFIG"

ftprims dump-config --out "${RESULTS}/default_config.yaml" \
&& ok "default_config.yaml"

section "ALL DONE"
echo "Results in ${RESULTS}/"
ls -1 "${RESULTS}/"
