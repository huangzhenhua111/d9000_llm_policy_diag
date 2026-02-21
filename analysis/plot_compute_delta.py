#!/usr/bin/env python3
import os, sys, csv, math, statistics

def percentile(sorted_vals, p):
    if not sorted_vals: return float("nan")
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k); c = math.ceil(k)
    if f == c: return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)

def read_file(path):
    vals=[]
    comp=None
    with open(path, newline="") as f:
        r=csv.DictReader(f)
        for row in r:
            if int(row.get("is_warmup","0"))==1:
                continue
            vals.append(float(row["latency_sec"]))
            comp=int(row["compute_iters"])
    vals.sort()
    return comp, vals

def summarize(vals):
    return {
        "n": len(vals),
        "p50": percentile(vals, 50),
        "p90": percentile(vals, 90),
        "mean": statistics.mean(vals),
    }

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 plot_compute_delta.py <raw_dir> <policy_prefix1> [policy_prefix2 ...]")
        sys.exit(1)

    raw_dir=sys.argv[1].rstrip("/")
    prefixes=sys.argv[2:]

    import matplotlib.pyplot as plt

    rows=[]
    for pref in prefixes:
        files=[f for f in os.listdir(raw_dir) if f.startswith(pref) and f.endswith(".csv")]
        if not files:
            raise RuntimeError(f"No csv found for {pref} in {raw_dir}")
        items=[]
        for fn in sorted(files):
            comp, vals = read_file(os.path.join(raw_dir, fn))
            s=summarize(vals)
            items.append((comp, s))
        items.sort(key=lambda x:x[0])
        rows.append((pref, items))

    # plot: each policy as its own series over compute_iters
    plt.figure(figsize=(8,4.5))
    for pref, items in rows:
        xs=[c for c,_ in items]
        ys=[s["p50"] for _,s in items]
        y90=[s["p90"] for _,s in items]
        plt.plot(xs, ys, marker="o", label=f"{pref} p50")
        plt.plot(xs, y90, marker="o", linestyle="--", label=f"{pref} p90")

    plt.xlabel("Added ALU iterations per step (compute_iters)")
    plt.ylabel("Latency (s)")
    plt.title("Compute-insensitivity across policies (batch=1)")
    plt.legend()
    plt.tight_layout()

    os.makedirs("results/figs", exist_ok=True)
    tag=os.path.basename(raw_dir)
    out=f"results/figs/compute_delta_{tag}.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print("[OK] Wrote:", out)

if __name__ == "__main__":
    main()
