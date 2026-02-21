# Topology-aware Bottleneck Diagnosis for Mobile LLM Inference

Research artifact for the mini-ASPLOS paper. Targets MediaTek Dimensity 9000.

## Quick Start
```bash
pkg install clang python
pip install matplotlib

chmod +x reproduce_all_figs.sh
./reproduce_all_figs.sh
```

This takes about 45-60 min. Output goes to `figs/` - should see Fig1-6.

## What it does

Reproduces all experiments from the paper. Main findings:

- 2 threads on same cluster (CPU 4+6) gives best latency
- Cross-cluster scheduling has weird bimodal behavior 
- Workload is memory-bound (adding compute ops does nothing)
- Policy ranking doesn't change with different memory footprints (16-128MB)
- Prefetching makes things worse (counterintuitive but true)
- Bad speculation causes nasty P90 tail latency (~1.8s)

See `10_mini_asplos.md` for full details.

## Requirements

**Hardware**: You need a Dimensity 9000 device. Tested on OPPO Find X5 Pro and Vivo X80. 8GB+ RAM recommended for the 128MB workset tests.

**Software**: Android 12+, Termux (or rooted shell), Clang 14+, Python 3.7+ with matplotlib. 

No root needed if using Termux - just need sched_setaffinity to work.

**Tips**: 
- Turn on airplane mode to reduce noise
- Keep battery >50% and plugged in
- Let device cool if it gets hot (throttling will mess up results)

## Files
```
.
├── 10_mini_asplos.md           # paper
├── reproduce_all_figs.sh       # main script
├── REPRODUCTION.md             # detailed guide
├── src/                        # implementations
│   ├── burn_llm_fenced3.cpp
│   ├── burn_llm_fenced3_addCompute.cpp
│   └── burn_llm_fenced3_prefetch.cpp
├── scripts/
│   └── run_one_policy.sh
├── analysis/                    # plotting scripts
└── results/                     # generated data
```

## How it works

The script runs these experiments:

1. Builds ~15 binary variants
2. Tests different thread configs (1T, 2T, 3T, cross-cluster)
3. Adds compute load to test if compute-bound
4. Sweeps memory footprint (16-128MB)
5. Tests different prefetch distances
6. Tests locality hint impact

Each test runs 10 warmup + 40 measured iterations with strict CPU pinning.

## Checking results

Quick check:
```bash
cat results/tables/summary_20260109_clean_v1.md
```

Policy P2 (2T @ CPU 4,6) should have lowest P50.

Or just look at the figures:
- Fig1: P2 line is lowest
- Fig2: two peaks in histogram (fast ~0.7s, slow ~1.6s)
- Fig3: flat lines (compute doesn't matter)
- Fig4: curves stay in same order across worksets
- Fig5: goes up as prefetch increases
- Fig6: hint=0 has much higher P90 bar

## Troubleshooting

**High variance?** Background apps, thermal throttling, or scheduling issues. Check `results/raw/*/*.log` for PIN-OK messages.

**Wrong numbers?** Expected P50 ranges on D9000:
- P1 (1T): ~0.85-0.95s
- P2 (2T): ~0.68-0.78s (best)
- P3 (3T): ~0.75-0.85s

If way off, device might be throttling or workload isn't memory-bound.

**Missing figures?** Check `results/figs/` for intermediate outputs. See REPRODUCTION.md for manual steps.

## Custom experiments

Test different CPUs:
```bash
bash scripts/run_one_policy.sh my_test 4 4,5,6,7 40 10 ./b_base
```

More runs:
```bash
bash scripts/run_one_policy.sh test 2 4,6 100 20 ./b_base
```

New prefetch distance:
```bash
clang++ -O3 -std=c++17 -pthread -DPREFETCH_CL=48 \
    src/burn_llm_fenced3_prefetch.cpp -o burn_pf48
bash scripts/run_one_policy.sh test_pf48 2 4,6 40 10 ./burn_pf48
```

## Citation
```bibtex
@inproceedings{d9000-llm-policy,
  title={Topology-aware Bottleneck Diagnosis and Guarded Policy for Mobile LLM Inference},
  author={[Authors]},
  booktitle={Mini-ASPLOS},
  year={2026}
}
```

Check REPRODUCTION.md if you run into issues. Logs are in `results/raw/<RUN_ID>/`.