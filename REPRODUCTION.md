# Artifact Evaluation & Reproduction Guide

This guide provides complete instructions for reproducing all 6 figures in the Mini-ASPLOS paper: **"Topology-aware Bottleneck Diagnosis and Guarded Policy for Mobile LLM Inference"**.

## Quick Start (TL;DR)

```bash
# 1. Clone/extract artifact to Dimensity 9000 device
cd /path/to/artifact

# 2. Run one-shot reproduction script (~45-60 minutes)
chmod +x reproduce_all_figs.sh
./reproduce_all_figs.sh

# 3. Verify output
ls -lh figs/2*_Fig*.png  # Should have 6 files (Fig.1 through Fig.6)
```

---

## Prerequisites

### Hardware
- **Required**: MediaTek Dimensity 9000 SoC
  - Core topology: A510 (0-3), A710 (4-6), X2 (7)
  - Tested on: OPPO Find X5 Pro, Vivo X80
- **Alternative**: Results may vary on other SoCs but methodology applies

### Software
- **OS**: Android with Termux (or rooted Linux shell)
- **Compiler**: `clang++ -O3` with `-std=c++17 -pthread` support
- **Python**: Python 3.7+ with `matplotlib`
- **Privileges**: `sched_setaffinity()` syscall access (no root required)

### Installation (Termux)
```bash
# Install dependencies
pkg update && pkg upgrade
pkg install clang python

# Install matplotlib
pip install matplotlib

# Verify setup
clang++ --version  # Should show Clang 14+
python3 -c "import matplotlib; print('OK')"
```

---

## Artifact Structure

```
d9000_llm_policy_diag_20260121/
├── reproduce_all_figs.sh      # One-shot reproduction script
├── REPRODUCTION.md             # This file
├── 10_mini_asplos.md           # Main paper
├── src/                        # Source code
�?  ├── burn_llm_fenced3.cpp               # Baseline workload
�?  ├── burn_llm_fenced3_addCompute.cpp    # Compute perturbation variant
�?  └── burn_llm_fenced3_prefetch.cpp      # Prefetch variant
├── scripts/
�?  └── run_one_policy.sh       # Per-policy experiment runner
├── analysis/                   # Plotting scripts
�?  ├── summarize_and_plot.py
�?  ├── plot_hist_one_policy.py
�?  ├── plot_compute_delta.py
�?  ├── plot_wsweep.py
�?  ├── plot_fig5_prefetch_np.py
�?  └── plot_fig6_hint_np.py
├── results/                    # Generated data (created by script)
�?  ├── raw/<RUN_ID>/*.csv      # Per-run latency traces
�?  ├── tables/*.csv            # Aggregated summaries
�?  └── figs/*.png              # Intermediate plots
└── figs/                       # Final figures (created by script)
    ├── 20_Fig1_same_cluster_sweetspot.png
    ├── 21_Fig2_cross_cluster_bimodal.png
    ├── 22_Fig3_compute_insensitivity.png
    ├── 23_Fig4_workset_sweep.png
    ├── 24_Fig5_Mechanism_Analysis.png
    └── 25_Fig6_Tail_Risk.png
```

---

## Complete Workflow Explanation

### Step 1: Binary Compilation
The script compiles multiple binary variants:

| Binary | Purpose | Compile Flags |
|--------|---------|---------------|
| `b_base` | Baseline workload (64MB, no mods) | Default |
| `burn_pf{0,1,2,4,8,16,32}` | Prefetch distance sweep | `-DPREFETCH_CL=N` |
| `b_pf1_h3`, `b_pf1_h0` | Locality hint variants | `-DPREFETCH_HINT={3,0}` |
| `b_comp{0,1000,2000,4000,8000}` | Compute intensity sweep | `-DCOMPUTE_ITERS_DEFAULT=N` |
| `b_ws{16,32,64,128}` | Workset size variants | `-DWORKSET_MB=N` |

**Why separate binaries?** To avoid complex parameter passing through `run_one_policy.sh` and ensure reproducibility.

### Step 2-6: Data Collection (5 Experiments)

Each experiment runs 10 warmup + 40 measured iterations per policy configuration:

#### Experiment 1: Topology Scaling (Fig.1-2)
- **RUN_ID**: `20260109_clean_v1`
- **Policies**:
  - P1: 1T @ CPU4 (baseline)
  - P2: 2T @ CPU4,6 (same-cluster, **sweet spot**)
  - P3: 3T @ CPU4,5,6 (same-cluster, regression)
  - P4: 2T @ CPU4,1 (cross-cluster, bimodal)
- **Output**: `results/raw/20260109_clean_v1/P*.csv`

#### Experiment 2: Compute Perturbation (Fig.3)
- **RUN_ID**: `20260109_compute_v2`
- **Knob**: `compute_iters` �?{0, 1000, 2000, 4000, 8000}
- **Purpose**: Rule out compute-bound hypothesis
- **Output**: CSV with `compute_iters` column for `plot_compute_delta.py`

#### Experiment 3: Workset Sweep (Fig.4)
- **RUN_IDs**: `20260110_wsweep_v1_ws{16,32,64,128}`
- **Knob**: Memory footprint 16MB �?128MB
- **Purpose**: Verify policy ranking invariance
- **Output**: 4 independent summary CSVs

#### Experiment 4: Prefetch Distance Sweep (Fig.5)
- **RUN_ID**: `20260118_prefetch_gated_v1`
- **Knob**: Prefetch distance (cache lines) �?{0, 1, 2, 4, 8, 16, 32}
- **Purpose**: Test MLP-starved hypothesis
- **Output**: Monotonic degradation curve

#### Experiment 5: Locality Hint Tail Risk (Fig.6)
- **RUN_ID**: `20260118_prefetch_hint_ab_v1`
- **Configs**: PF1+hint=3 vs. PF1+hint=0
- **Purpose**: Demonstrate L2 pollution tail risk
- **Output**: P90 regression (~1.8s) for hint=0

### Step 7: Summary Generation
`summarize_and_plot.py` processes raw CSVs to compute:
- **P50** (median latency)
- **P90** (tail latency)
- **Mean, Min, Max**

Output: `results/tables/summary_<RUN_ID>.csv`

### Step 8: Figure Generation
Each figure is generated by a specific script:

| Figure | Script | Input | Key Claim |
|--------|--------|-------|-----------|
| Fig.1 | `summarize_and_plot.py` | `20260109_clean_v1` | 2T@(4,6) is sweet spot |
| Fig.2 | `plot_hist_one_policy.py` | P4 CSV | Cross-cluster is bimodal |
| Fig.3 | `plot_compute_delta.py` | `20260109_compute_v2` | Compute-insensitive |
| Fig.4 | `plot_wsweep.py` | 4 wsweep CSVs | Ranking invariant |
| Fig.5 | `plot_fig5_prefetch_np.py` | prefetch_gated CSV | Monotonic degradation |
| Fig.6 | `plot_fig6_hint_np.py` | hint_ab CSV | Low-locality �?P90 spike |

---

## Expected Results & Verification

After running `reproduce_all_figs.sh`, verify the key claims:

### Claim 1: Sweet Spot (Fig.1)
```bash
cat results/tables/summary_20260109_clean_v1.md
```
**Expected**: `P2_2T_same_cluster_4_6` has **lowest P50** among P1/P2/P3.

### Claim 2: Bimodality (Fig.2)
Open `figs/21_Fig2_cross_cluster_bimodal.png`.  
**Expected**: Histogram shows **two distinct peaks** (fast mode ~0.7s, slow mode ~1.6s).

### Claim 3: Compute Insensitivity (Fig.3)
Open `figs/22_Fig3_compute_insensitivity.png`.  
**Expected**: Lines are **nearly flat** from compute_iters=0 to 8000.

### Claim 4: Workset Invariance (Fig.4)
Open `figs/23_Fig4_workset_sweep.png`.  
**Expected**: **Ranking preserved** (P2 < P1, P2 < P3) across 16-128MB.

### Claim 5: Prefetch Degradation (Fig.5)
```bash
cat results/tables/summary_20260118_prefetch_gated_v1.md | awk '{print $1, $4}'
```
**Expected**: P50 values **monotonically increase** (PF0 < PF1 < ... < PF32).

### Claim 6: Tail Risk (Fig.6)
```bash
cat results/tables/summary_20260118_prefetch_hint_ab_v1.md
```
**Expected**: `pf1_h0` P90 >> `pf1_h3` P90 (�?× difference, reaching ~1.8s).

---

## Troubleshooting

### Issue: Figures Missing
**Symptom**: `figs/` has fewer than 6 PNG files.  
**Diagnosis**:
```bash
# Check intermediate outputs
ls results/figs/
# Check for Python errors
python3 analysis/plot_fig5_prefetch_np.py --csv results/tables/summary_20260118_prefetch_gated_v1.csv --out test.png
```
**Solution**: Re-run the specific plotting step manually.

### Issue: CPU Pinning Failed
**Symptom**: Logs show `[PIN-FAIL]` or latency variance > 30%.  
**Diagnosis**:
```bash
grep PIN results/raw/20260109_clean_v1/*.log
```
**Solution**:
- Check CPU topology: `cat /proc/cpuinfo | grep processor`
- Ensure no governor interference: `echo performance > /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`
- Disable background services (enable airplane mode)

### Issue: Thermal Throttling
**Symptom**: Latency increases over time or P90 >> P50.  
**Diagnosis**:
```bash
# Monitor thermal zones during run
watch -n 1 cat /sys/class/thermal/thermal_zone*/temp
```
**Solution**:
- Let device cool (< 40°C) before each experiment
- Run experiments in shorter batches
- Use active cooling (fan)

### Issue: Unexpected Latency Values
**Symptom**: All policies show ~0.1s (too fast) or >5s (too slow).  
**Possible Causes**:
- **Too fast**: Workset cached in L3 �?increase workset to 128MB
- **Too slow**: Thermal throttling or background apps �?reboot device
- **Inconsistent**: Scheduling noise �?verify airplane mode enabled

---

## Manual Step-by-Step Reproduction

If the one-shot script fails, run steps individually:

```bash
# Step 1: Build binaries
clang++ -O3 -std=c++17 -pthread src/burn_llm_fenced3.cpp -o b_base
# ... (see script for full list)

# Step 2: Run one experiment
export RUN_ID=20260109_clean_v1
bash scripts/run_one_policy.sh P2_2T_same_cluster_4_6 2 4,6 40 10 ./b_base

# Step 3: Generate summary
python3 analysis/summarize_and_plot.py results/raw/$RUN_ID

# Step 4: Plot figure
cp results/figs/same_cluster_${RUN_ID}.png figs/20_Fig1_same_cluster_sweetspot.png
```

---

## Modifying Experiments

### Change Number of Runs
Edit `reproduce_all_figs.sh` or call `run_one_policy.sh` directly:
```bash
bash scripts/run_one_policy.sh <policy> <threads> <cpus> <runs> <warmup> <binary>
# Example: 100 runs + 20 warmup
bash scripts/run_one_policy.sh test_policy 2 4,6 100 20 ./b_base
```

### Test Different CPU Configurations
```bash
# Example: Test 4T on all A710 cores
bash scripts/run_one_policy.sh P_4T_A710 4 4,5,6,7 40 10 ./b_base
```

### Add New Prefetch Distances
```bash
clang++ -O3 -std=c++17 -pthread -DPREFETCH_CL=64 \
    src/burn_llm_fenced3_prefetch.cpp -o burn_pf64
bash scripts/run_one_policy.sh P2_pf64 2 4,6 40 10 ./burn_pf64
```

---

## Performance Expectations

On a well-conditioned Dimensity 9000 device:

| Policy | Expected P50 | Expected P90 |
|--------|--------------|--------------|
| P1 (1T @ 4) | ~0.90s | ~0.95s |
| P2 (2T @ 4,6) | **~0.72s** | ~0.75s |
| P3 (3T @ 4,5,6) | ~0.78s | ~0.82s |
| P4 (2T @ 4,1) | ~0.72s / ~1.59s (bimodal) | ~1.70s |

**Variance tolerance**: P50 should be within ±10% across runs. Higher variance indicates system noise.

---

## Contact & Support

For issues or questions about artifact reproduction:
1. Check logs: `results/raw/<RUN_ID>/*.log`
2. Verify CSV format: `head results/raw/<RUN_ID>/P2_*.csv`
3. Consult main paper: `10_mini_asplos.md` Section 2 (Experimental Setup)

---

## Artifact Checklist (for Reviewers)

- [ ] All 6 figures generated (`figs/2{0-5}_Fig*.png`)
- [ ] P2 (2T@4,6) is fastest in Fig.1
- [ ] Fig.2 shows clear bimodal distribution
- [ ] Fig.3 shows flat lines (compute-insensitive)
- [ ] Fig.4 preserves ranking across worksets
- [ ] Fig.5 shows monotonic increase (PF0→PF32)
- [ ] Fig.6 shows P90 spike for hint=0
- [ ] Summary tables match figure trends
- [ ] Raw CSVs contain 40 non-warmup runs per policy
- [ ] Logs show `[PIN-OK]` for all runs

**Estimated evaluation time**: 1-2 hours (including 45min data collection + validation).
