#!/data/data/com.termux/files/usr/bin/bash
################################################################################
# reproduce_all_figs.sh
# Complete reproduction script for Mini-ASPLOS artifact
# Generates all 6 figures from experimental data on Dimensity 9000
#
# Usage: ./reproduce_all_figs.sh
# Time: ~45-60 minutes (40 runs × multiple configs)
# Output: figs/20_Fig1_*.png through figs/25_Fig6_*.png
################################################################################

set -euo pipefail

echo "=========================================================================="
echo "  Mini-ASPLOS Artifact: Topology-aware Bottleneck Diagnosis"
echo "  Target: MediaTek Dimensity 9000 (batch=1 LLM inference proxy)"
echo "=========================================================================="
echo ""

# ============================================================================
# STEP 0: Environment Validation
# ============================================================================
echo "[Step 0] Validating environment..."

if [[ ! -d "src" ]] || [[ ! -d "scripts" ]] || [[ ! -d "analysis" ]]; then
    echo "ERROR: Must run from artifact root (should contain src/, scripts/, analysis/)"
    echo "Current directory: $(pwd)"
    exit 1
fi

if ! command -v clang++ &> /dev/null; then
    echo "ERROR: clang++ not found. Install with: pkg install clang"
    exit 1
fi

if ! python3 -c "import matplotlib" 2>/dev/null; then
    echo "WARN: matplotlib not found, attempting install..."
    pip install matplotlib || {
        echo "ERROR: Install failed. Try: pkg install python && pip install matplotlib"
        exit 1
    }
fi

mkdir -p results/{raw,tables,figs} figs
chmod +x scripts/run_one_policy.sh

echo "  ✓ Directory structure validated"
echo "  ✓ Compiler: $(clang++ --version | head -n1)"
echo "  ✓ Python: $(python3 --version)"
echo ""

# ============================================================================
# STEP 1: Build All Binary Variants
# ============================================================================
echo "[Step 1] Compiling binaries..."

# 1.1 Baseline (no modifications)
clang++ -O3 -std=c++17 -pthread src/burn_llm_fenced3.cpp -o b_base
echo "  ✓ b_base (baseline, workset=64MB)"

# 1.2 Prefetch distance variants (PF0 to PF32)
for cl in 0 1 2 4 8 16 32; do
    clang++ -O3 -std=c++17 -pthread \
        -DPREFETCH_CL=$cl \
        src/burn_llm_fenced3_prefetch.cpp -o burn_pf${cl}
done
echo "  ✓ burn_pf{0,1,2,4,8,16,32} (prefetch distance sweep)"

# 1.3 Locality hint variants (for Fig.6)
clang++ -O3 -std=c++17 -pthread \
    -DPREFETCH_CL=1 -DPREFETCH_HINT=3 \
    src/burn_llm_fenced3_prefetch.cpp -o b_pf1_h3

clang++ -O3 -std=c++17 -pthread \
    -DPREFETCH_CL=1 -DPREFETCH_HINT=0 \
    src/burn_llm_fenced3_prefetch.cpp -o b_pf1_h0
echo "  ✓ b_pf1_h3, b_pf1_h0 (hint=3 vs hint=0)"

# 1.4 Compute perturbation variants (for Fig.3)
# CRITICAL: Compile separate binaries for each compute_iters to avoid parameter hell
for iters in 0 1000 2000 4000 8000; do
    clang++ -O3 -std=c++17 -pthread \
        -DCOMPUTE_ITERS_DEFAULT=$iters \
        src/burn_llm_fenced3_addCompute.cpp -o b_comp${iters}
done
echo "  ✓ b_comp{0,1000,2000,4000,8000} (compute perturbation)"

echo "[OK] All binaries compiled"
echo ""

# ============================================================================
# STEP 2: Data Collection for Fig.1-2 (Topology Scaling)
# ============================================================================
echo "[Step 2] Experiment 1: Topology scaling (Fig.1-2)..."
export RUN_ID=20260109_clean_v1

echo "  Running P1: 1T @ A710 CPU4 (baseline)..."
bash scripts/run_one_policy.sh P1_single_A710_cpu4 1 4 40 10 ./b_base

echo "  Running P2: 2T @ same-cluster (4,6) - THE SWEET SPOT..."
bash scripts/run_one_policy.sh P2_2T_same_cluster_4_6 2 4,6 40 10 ./b_base

echo "  Running P3: 3T @ same-cluster (4,5,6) - regression test..."
bash scripts/run_one_policy.sh P3_3T_same_cluster_4_5_6 3 4,5,6 40 10 ./b_base

echo "  Running P4: 2T cross-cluster (4,1) - bimodal latency test..."
bash scripts/run_one_policy.sh P4_2T_cross_cluster_4_1 2 4,1 40 10 ./b_base

echo "[OK] Fig.1-2 data → results/raw/$RUN_ID/"
echo ""

# ============================================================================
# STEP 3: Data Collection for Fig.3 (Compute Insensitivity)
# ============================================================================
echo "[Step 3] Experiment 2: Compute perturbation (Fig.3)..."
export RUN_ID=20260109_compute_v2

# Helper function to generate CSV with compute_iters column
run_compute_policy() {
    local policy=$1 threads=$2 cpulist=$3 iters=$4 bin=$5
    local runs=40 warmup=10
    local outdir="results/raw/${RUN_ID}"
    mkdir -p "$outdir"
    local csv="${outdir}/${policy}.csv"
    local log="${outdir}/${policy}.log"
    
    # CSV header with compute_iters column (required by plot_compute_delta.py)
    echo "policy,run_idx,is_warmup,threads,cpu_list,compute_iters,latency_sec" > "$csv"
    echo "[RUN] $policy (compute_iters=$iters)" | tee "$log"
    
    local total=$((runs + warmup))
    for i in $(seq 1 $total); do
        # Run binary (it takes: threads cpu_list compute_iters steps workset_mb)
        out=$($bin $threads "$cpulist" $iters 200 64 2>&1 | tee -a "$log")
        lat=$(echo "$out" | sed -n 's/.*Time:[[:space:]]*\([0-9.]\+\).*/\1/p' | tail -n 1)
        
        if [[ -z "$lat" ]]; then
            echo "ERROR: Failed to parse latency at run $i" | tee -a "$log"
            exit 3
        fi
        
        is_warmup=$(( i <= warmup ? 1 : 0 ))
        echo "${policy},${i},${is_warmup},${threads},\"${cpulist}\",${iters},${lat}" >> "$csv"
        sleep 0.05
    done
    echo "  ✓ $csv" | tee -a "$log"
}

# Test compute_iters: 0, 1000, 2000, 4000, 8000 for P2 (2T) and P3 (3T)
for iters in 0 1000 2000 4000 8000; do
    echo "  Testing compute_iters=${iters}..."
    run_compute_policy "P2_compute${iters}" 2 4,6 $iters ./b_comp${iters}
    run_compute_policy "P3_compute${iters}" 3 4,5,6 $iters ./b_comp${iters}
done

echo "[OK] Fig.3 data → results/raw/$RUN_ID/"
echo ""

# ============================================================================
# STEP 4: Data Collection for Fig.4 (Workset Sweep)
# ============================================================================
echo "[Step 4] Experiment 3: Workset sweep (Fig.4)..."

for ws in 16 32 64 128; do
    export RUN_ID=20260110_wsweep_v1_ws${ws}
    
    echo "  Compiling for workset=${ws}MB..."
    clang++ -O3 -std=c++17 -pthread \
        -DWORKSET_MB=${ws} \
        src/burn_llm_fenced3.cpp -o b_ws${ws}
    
    echo "  Running policies with workset=${ws}MB..."
    bash scripts/run_one_policy.sh P1_single_A710_cpu4 1 4 40 10 ./b_ws${ws}
    bash scripts/run_one_policy.sh P2_2T_same_cluster_4_6 2 4,6 40 10 ./b_ws${ws}
    bash scripts/run_one_policy.sh P3_3T_same_cluster_4_5_6 3 4,5,6 40 10 ./b_ws${ws}
    
    # Generate summary immediately
    python3 analysis/summarize_and_plot.py results/raw/$RUN_ID
    echo "  ✓ Workset ${ws}MB complete"
done

echo "[OK] Fig.4 data → 4 workset directories"
echo ""

# ============================================================================
# STEP 5: Data Collection for Fig.5 (Prefetch Mechanism)
# ============================================================================
echo "[Step 5] Experiment 4: Prefetch distance sweep (Fig.5)..."
export RUN_ID=20260118_prefetch_gated_v1

for cl in 0 1 2 4 8 16 32; do
    echo "  Testing prefetch_cl=${cl}..."
    bash scripts/run_one_policy.sh P2_2T_4_6_pf${cl} 2 4,6 40 10 ./burn_pf${cl}
done

echo "[OK] Fig.5 data → results/raw/$RUN_ID/"
echo ""

# ============================================================================
# STEP 6: Data Collection for Fig.6 (Locality Hint Tail Risk)
# ============================================================================
echo "[Step 6] Experiment 5: Locality hint tradeoff (Fig.6)..."
export RUN_ID=20260118_prefetch_hint_ab_v1

echo "  Testing PF1 + hint=3 (high locality)..."
bash scripts/run_one_policy.sh pf1_h3 2 4,6 40 10 ./b_pf1_h3

echo "  Testing PF1 + hint=0 (low locality, tail risk)..."
bash scripts/run_one_policy.sh pf1_h0 2 4,6 40 10 ./b_pf1_h0

echo "[OK] Fig.6 data → results/raw/$RUN_ID/"
echo ""

# ============================================================================
# STEP 7: Generate Summary Tables
# ============================================================================
echo "[Step 7] Generating summary tables..."

python3 analysis/summarize_and_plot.py results/raw/20260109_clean_v1
python3 analysis/summarize_and_plot.py results/raw/20260109_compute_v2
# Workset summaries already generated in Step 4
python3 analysis/summarize_and_plot.py results/raw/20260118_prefetch_gated_v1
python3 analysis/summarize_and_plot.py results/raw/20260118_prefetch_hint_ab_v1

echo "[OK] All summary tables → results/tables/"
echo ""

# ============================================================================
# STEP 8: Generate All Six Figures
# ============================================================================
echo "[Step 8] Generating final figures..."

# Fig.1: Same-cluster sweet spot (auto-generated by summarize_and_plot.py)
echo "  Generating Fig.1 (same-cluster scaling)..."
cp -v results/figs/same_cluster_20260109_clean_v1.png \
      figs/20_Fig1_same_cluster_sweetspot.png

# Fig.2: Cross-cluster bimodality
echo "  Generating Fig.2 (cross-cluster bimodal distribution)..."
python3 analysis/plot_hist_one_policy.py \
    results/raw/20260109_clean_v1 \
    P4_2T_cross_cluster_4_1.csv
cp -v results/figs/hist_P4_2T_cross_cluster_4_1_20260109_clean_v1.png \
      figs/21_Fig2_cross_cluster_bimodal.png

# Fig.3: Compute insensitivity
echo "  Generating Fig.3 (compute perturbation insensitivity)..."
python3 analysis/plot_compute_delta.py \
    results/raw/20260109_compute_v2 \
    P2_compute P3_compute
cp -v results/figs/compute_delta_20260109_compute_v2.png \
      figs/22_Fig3_compute_insensitivity.png

# Fig.4: Workset sweep
echo "  Generating Fig.4 (workset sweep invariance)..."
python3 analysis/plot_wsweep.py 20260110_wsweep_v1
cp -v results/figs/wsweep_20260110_wsweep_v1.png \
      figs/23_Fig4_workset_sweep.png

# Fig.5: Prefetch distance sweep
echo "  Generating Fig.5 (prefetch mechanism analysis)..."
python3 analysis/plot_fig5_prefetch_np.py \
    --csv results/tables/summary_20260118_prefetch_gated_v1.csv \
    --out figs/24_Fig5_Mechanism_Analysis.png

# Fig.6: Hint tradeoff
echo "  Generating Fig.6 (locality hint tail risk)..."
python3 analysis/plot_fig6_hint_np.py \
    --csv results/tables/summary_20260118_prefetch_hint_ab_v1.csv \
    --out figs/25_Fig6_Tail_Risk.png

echo "[OK] All figures generated"
echo ""

# ============================================================================
# STEP 9: Verification & Summary
# ============================================================================
echo "=========================================================================="
echo "                      REPRODUCTION COMPLETE                              "
echo "=========================================================================="
echo ""
echo "Generated Artifacts:"
echo "  Raw Data:    results/raw/<RUN_ID>/*.{csv,log}"
echo "  Tables:      results/tables/summary_*.{csv,md}"
echo "  Figures:     figs/20_Fig1_*.png through figs/25_Fig6_*.png"
echo ""
echo "Figure Verification:"
fig_count=0
for fig in figs/2{0,1,2,3,4,5}_Fig*.png; do
    if [[ -f "$fig" ]]; then
        size=$(ls -lh "$fig" | awk '{print $5}')
        echo "  ✓ $(basename $fig) ($size)"
        ((fig_count++))
    else
        echo "  ✗ $(basename $fig) (MISSING!)"
    fi
done

if [[ $fig_count -eq 6 ]]; then
    echo ""
    echo "SUCCESS: All 6 figures generated correctly!"
else
    echo ""
    echo "WARNING: Only $fig_count/6 figures generated. Check logs for errors."
fi

echo ""
echo "Key Claims to Verify:"
echo "  [Fig.1] Sweet spot: P2_2T_same_cluster_4_6 < {P1, P3}"
echo "  [Fig.2] Bimodal: P4_2T_cross_cluster_4_1 shows two peaks"
echo "  [Fig.3] Insensitive: Latency flat across compute_iters 0→8000"
echo "  [Fig.4] Invariant: Policy ranking (P2<P1, P2<P3) across 16-128MB"
echo "  [Fig.5] Monotonic: Latency increases PF0 < PF1 < ... < PF32"
echo "  [Fig.6] Tail risk: pf1_h0 P90 >> pf1_h3 P90 (~1.8s spike)"
echo ""
echo "Quick Verification Commands:"
echo "  cat results/tables/summary_20260109_clean_v1.md     # Check sweet spot"
echo "  cat results/tables/summary_20260118_prefetch_gated_v1.md | grep p50"
echo "  open figs/  # View all figures"
echo ""
echo "Troubleshooting:"
echo "  - Figure missing? Check results/figs/ for intermediate outputs"
echo "  - Data looks wrong? Verify pinning: grep PIN-OK results/raw/*/*.log"
echo "  - Thermal issues? Enable airplane mode and let device cool"
echo "  - Script failed? Re-run individual steps (see REPRODUCTION.md)"
echo "=========================================================================="
