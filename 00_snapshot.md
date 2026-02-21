# Batch=1 Token Latency on Dimensity 9000: Diagnosis & Guarded Policy

**Punchline**
**2×A710 same-cluster** is the robust sweet spot. A minimally invasive prefetch experiment **is inconsistent with the "MLP-starved" hypothesis**, suggesting the bottleneck is **L2 Handling/Interference limited**. Crucially, low-locality prefetching triggers **severe tail latency regressions**, necessitating **OS-level guardrails**.

---

## **Core Mechanism Evidence (New Findings)**

### **Fig.5: Mechanism Analysis---Falsifying MLP-starved**
![](figs/24_Fig5_Mechanism_Analysis.png)
Latency **degrades monotonically** with increasing prefetch distance (PF1 slows down by +40%, and PF4+ by >130%), **is inconsistent with the MLP-starved hypothesis**. The system operates in a **Handling/Interference limited** regime where extra concurrency primarily amplifies L2 congestion.

### **Fig.6: Tail Risk---Hint Tradeoff Guardrail**
![](figs/25_Fig6_Tail_Risk.png)
Low-locality prefetch (Hint=0) triggers a **sharp P90 regression (~1.8s vs Baseline 0.67s)** despite a stable median. This **motivates a clear need** for **Tail Guardrails**, as aggressive memory speculation hits state-dependent slow paths, directly violating SLA.

---

## **Diagnosis Context (Foundation)**

* **Fig.1 (Scaling):** **2T@4,6 is optimal.** 3T regresses (+7.8%), consistent with **Shared L2 contention** capping parallelism.  
![](figs/20_Fig1_same_cluster_sweetspot.png)

* **Fig.2 (Cross-cluster):** 
![](figs/21_Fig2_cross_cluster_bimodal.png)
Policy 4,1 exhibits **Bimodal Latency**, indicating cross-cluster scheduling can be **unstable**.

* **Fig.3 & 4 (Robustness):** 
![](figs/22_Fig3_compute_insensitivity.png)
![](figs/23_Fig4_workset_sweep.png)
Compute perturbation and footprint sweep are consistent with a **Memory-side** bottleneck that remains **Robust** across workloads.

---

## **3 Strategic Takeaways**

1.  **Methodology (Transferable Causal Diagnosis):**
    Established a **Memory-side Bound** via a PMU-free causal chain: **Topology-aware scaling** exposed contention, while **In-binary perturbations** (compute/footprint sweeps) argue against compute-bound behavior and global bandwidth/LLC (L3) capacity limits, yielding a transferable black-box diagnosis workflow for mobile SoCs.

2.  **Mechanism (Evidence-driven Reversal):**
    **Evidence is inconsistent with the MLP-starved hypothesis.** Prefetch sweep indicates the system is **Handling/Interference limited**: increasing concurrency consistently worsens congestion. **Tail risks** are traced to cache pollution (Hint=0), linking micro-arch states to SLA violations.

3.  **Policy (Sweet Spot + Guardrails):**
    **Core:** Pin to **2×A710 same-cluster**.
    **Guardrail:** Disable SW prefetch; avoid Cross-cluster placement; avoid low locality caused by interference from other threads.
---

*Full reproduction scripts, Mini-paper, and Raw Data are attached.*
