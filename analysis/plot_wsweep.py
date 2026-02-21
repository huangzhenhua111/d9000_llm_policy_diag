#!/usr/bin/env python3
import os, sys, csv, math

def read_summary_csv(path):
    rows = {}
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows[row["policy"]] = row
    return rows

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 plot_wsweep.py <base_run_id>")
        sys.exit(1)

    base = sys.argv[1]
    worksets = [16, 32, 64, 128]
    policies = [
        "P1_single_A710_cpu4",
        "P2_2T_same_cluster_4_6",
        "P3_3T_same_cluster_4_5_6",
    ]

    data = {p: {"ws": [], "p50": [], "p90": []} for p in policies}

    for ws in worksets:
        run_id = f"{base}_ws{ws}"
        summary = f"results/tables/summary_{run_id}.csv"
        if not os.path.isfile(summary):
            raise RuntimeError(f"Missing {summary}")
        rows = read_summary_csv(summary)
        for p in policies:
            if p not in rows:
                raise RuntimeError(f"Missing policy {p} in {summary}")
            data[p]["ws"].append(ws)
            data[p]["p50"].append(float(rows[p]["p50_s"]))
            data[p]["p90"].append(float(rows[p]["p90_s"]))

    import matplotlib.pyplot as plt
    plt.figure(figsize=(8,4.5))
    for p in policies:
        plt.plot(data[p]["ws"], data[p]["p50"], marker="o", label=f"{p} p50")
        plt.plot(data[p]["ws"], data[p]["p90"], marker="o", linestyle="--", label=f"{p} p90")

    plt.xlabel("workset_mb")
    plt.ylabel("Latency (s)")
    plt.title("Workset sweep: latency vs memory footprint (batch=1)")
    plt.legend()
    plt.tight_layout()

    os.makedirs("results/figs", exist_ok=True)
    out = f"results/figs/wsweep_{base}.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print("[OK] Wrote:", out)

if __name__ == "__main__":
    main()
