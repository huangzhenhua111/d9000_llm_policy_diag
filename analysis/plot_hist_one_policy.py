
#!/usr/bin/env python3
import os, sys, csv

def read_latencies(path):
    vals = []
    with open(path, "r", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            if int(row.get("is_warmup","0")) == 1:
                continue
            vals.append(float(row["latency_sec"]))
    return vals

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 plot_hist_one_policy.py <raw_dir> <policy_csv_name>")
        sys.exit(1)

    raw_dir = sys.argv[1].rstrip("/")
    csv_name = sys.argv[2]
    path = os.path.join(raw_dir, csv_name)
    if not os.path.isfile(path):
        print("Missing:", path)
        sys.exit(2)

    import matplotlib.pyplot as plt
    vals = read_latencies(path)

    plt.figure(figsize=(7,4))
    plt.hist(vals, bins=20)
    plt.xlabel("Latency (s)")
    plt.ylabel("Count")
    plt.title(csv_name.replace(".csv",""))
    plt.tight_layout()

    os.makedirs("results/figs", exist_ok=True)
    tag = os.path.basename(raw_dir)
    out = f"results/figs/hist_{csv_name.replace('.csv','')}_{tag}.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print("[OK] Wrote:", out)

if __name__ == "__main__":
    main()

