#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Usage:
#   ./run_one_policy.sh <policy_name> <threads> <cpu_list> [runs] [warmup] [bin]
#
# Examples:
#   ./run_one_policy.sh P1_single_A710_cpu4       1 4
#   ./run_one_policy.sh P2_2T_same_cluster_4_6    2 4,6 40 10
#   ./run_one_policy.sh P4_2T_cross_cluster_4_1   2 4,1 40 10
#
# Notes:
# - This script expects program output line like:
#   "Threads: 2  Time: 0.733305 seconds"
# - It stores per-run latency (seconds) into CSV.

POLICY="${1:-}"
THREADS="${2:-}"
CPULIST="${3:-}"
RUNS="${4:-40}"
WARMUP="${5:-10}"
BIN="${6:-./burn_llm_fenced3}"

if [[ -z "$POLICY" || -z "$THREADS" || -z "$CPULIST" ]]; then
  echo "Usage: $0 <policy_name> <threads> <cpu_list> [runs] [warmup] [bin]" >&2
  exit 1
fi

if [[ ! -x "$BIN" ]]; then
  echo "Error: BIN not found or not executable: $BIN" >&2
  echo "Tip: chmod +x $BIN" >&2
  exit 2
fi

# If RUN_ID is set, reuse it to put all policies under one folder.
# Example:
#   export RUN_ID=20260110_clean_v1
#   ./run_one_policy.sh ...
RUN_ID="${RUN_ID:-}"
if [[ -z "$RUN_ID" ]]; then
  RUN_ID="$(date +%Y%m%d_%H%M%S)"
fi

OUTDIR="results/raw/${RUN_ID}"
mkdir -p "$OUTDIR"

CSV="${OUTDIR}/${POLICY}.csv"
LOG="${OUTDIR}/${POLICY}.log"

# CSV header
echo "policy,run_idx,is_warmup,threads,cpu_list,latency_sec" > "$CSV"

echo "[RUN] policy=$POLICY threads=$THREADS cpus=$CPULIST runs=$RUNS warmup=$WARMUP bin=$BIN" | tee "$LOG"
echo "[OUT] $CSV" | tee -a "$LOG"

TOTAL=$((RUNS + WARMUP))

for i in $(seq 1 "$TOTAL"); do
  # Run and capture full output to log (append)
  OUT="$($BIN "$THREADS" "$CPULIST" 2>&1 | tee -a "$LOG")"

  # Parse latency from "Time: X seconds"
  LAT="$(echo "$OUT" | sed -n 's/.*Time:[[:space:]]*\([0-9.]\+\)[[:space:]]*seconds.*/\1/p' | tail -n 1)"

  if [[ -z "$LAT" ]]; then
    echo "Error: failed to parse latency at run $i. See log: $LOG" >&2
    exit 3
  fi

  if [[ "$i" -le "$WARMUP" ]]; then
    IS_WARMUP=1
  else
    IS_WARMUP=0
  fi

  echo "${POLICY},${i},${IS_WARMUP},${THREADS},\"${CPULIST}\",${LAT}" >> "$CSV"

  # Small pause to reduce scheduling burst noise (keep tiny)
  sleep 0.05
done

echo "[DONE] Saved: $CSV" | tee -a "$LOG"
