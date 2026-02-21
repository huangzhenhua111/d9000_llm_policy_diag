# table_summary

Device: Dimensity 9000 (A710/A510)  
Workload: Batch=1 token proxy  
Metric: latency (s)

## Policy search

| Policy | Threads | P50 | P90 | Comment |
| :--- | :---: | :---: | :---: | :--- |
| P2_2T_same_cluster_4_6 | 2 | 0.668 | 0.680 | best / stable |
| P3_3T_same_cluster_4_5_6 | 3 | 0.720 | 0.733 | regression (+7.8%) |
| P1_single_A710_cpu4 | 1 | 0.839 | 0.857 | baseline |
| P4_2T_cross_cluster_4_1 | 2 | 1.567 | 1.596 | bimodal / unstable |

One-line: 2T same-cluster is the best operating point; adding a 3rd thread hurts.

---

## Prefetch distance sweep (2T@4,6; gated prefetch)

| Prefetch dist (CL) | P50 | P90 | ΔP50 vs PF0 |
| :---: | :---: | :---: | :---: |
| PF0 | 0.658 | 0.706 | - |
| PF1 | 0.923 | 0.969 | +40% |
| PF2 | 0.924 | 0.976 | +40% |
| PF4 | 1.535 | 1.823 | +133% |
| PF32 | 1.783 | 1.868 | +171% |

One-line: latency worsens monotonically as prefetch distance increases.

---

## Locality hint (prefetch dist = 1; 2T@4,6)

| Variant | P50 | P90 | Comment |
| :--- | :---: | :---: | :--- |
| PF1 + hint=3 | 0.921 | 0.929 | stable slowdown |
| PF1 + hint=0 | 0.928 | 1.800 | tail regression |

One-line: hint=0 keeps median similar but blows up tail (P90 ~1.8s).
