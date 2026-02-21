#!/usr/bin/env python3
import os, sys, csv, math, statistics
from datetime import datetime

def percentile(sorted_vals, p):
    """p in [0,100]"""
    if not sorted_vals:
        return float("nan")
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1

def read_policy_csv(path):
    vals = []
    with open(path, "r", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            # support both our new format and older simple csvs
            if "latency_sec" in row:
                is_warmup = int(row.get("is_warmup", "0"))
                if is_warmup == 1:
                    continue
                vals.append(float(row["latency_sec"]))
            else:
                # fallback: try parse a column named "Time" or first numeric column
                for k, v in row.items():
                    try:
                        vals.append(float(v))
                        break
                    except:
                        pass
    return vals

def summarize(vals):
    vals = [v for v in vals if v == v]  # drop NaN
    if not vals:
        return None
    s = sorted(vals)
    return {
        "n": len(s),
        "mean": statistics.mean(s),
        "p50": percentile(s, 50),
        "p90": percentile(s, 90),
        "min": s[0],
        "max": s[-1],
    }

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def write_csv(path, rows, header):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def write_md_table(path, rows):
    header = ["policy", "n", "mean_s", "p50_s", "p90_s", "min_s", "max_s"]
    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for r in rows:
        lines.append("| {policy} | {n} | {mean_s:.4f} | {p50_s:.4f} | {p90_s:.4f} | {min_s:.4f} | {max_s:.4f} |".format(**r))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

def try_plot_same_cluster(out_png, rows_by_policy):
    # optional plotting: only if matplotlib exists
    try:
        import matplotlib.pyplot as plt
    except Exception as e:
        return False, str(e)

    # We want the "sweet spot" plot: 1T@4 vs 2T@4,6 vs 3T@4,5,6
    # Use whichever policies exist in folder.
    # You can rename policies freely; we match by substring.
    def find_policy(substrs):
        for name in rows_by_policy.keys():
            ok = True
            for s in substrs:
                if s not in name:
                    ok = False
                    break
            if ok:
                return name
        return None

    p1 = find_policy(["P1"]) or find_policy(["single", "cpu4"]) or find_policy(["1T", "4"])
    p2 = find_policy(["P2", "4_6"]) or find_policy(["4,6"]) or find_policy(["same_cluster", "4_6"])
    p3 = find_policy(["P3"]) or find_policy(["3T"]) or find_policy(["4_5_6"])

    picks = []
    labels = []
    if p1: picks.append(p1); labels.append("1T@4")
    if p2: picks.append(p2); labels.append("2T@4,6")
    if p3: picks.append(p3); labels.append("3T@4,5,6")

    if len(picks) < 2:
        return False, "Not enough same-cluster policies found to plot."

    means = [rows_by_policy[p]["mean_s"] for p in picks]
    p50s  = [rows_by_policy[p]["p50_s"] for p in picks]
    p90s  = [rows_by_policy[p]["p90_s"] for p in picks]

    x = list(range(len(picks)))
    plt.figure()
    plt.plot(x, means, marker="o", label="mean")
    plt.plot(x, p50s, marker="o", label="p50")
    plt.plot(x, p90s, marker="o", label="p90")
    plt.xticks(x, labels)
    plt.ylabel("Latency (s)")
    plt.title("Same-cluster scaling: 1T vs 2T vs 3T")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    plt.close()
    return True, ""

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 summarize_and_plot.py <results/raw/DATE_TAG>")
        sys.exit(1)

    raw_dir = sys.argv[1].rstrip("/")
    if not os.path.isdir(raw_dir):
        print(f"Error: not a directory: {raw_dir}")
        sys.exit(2)

    csvs = [f for f in os.listdir(raw_dir) if f.endswith(".csv")]
    if not csvs:
        print(f"Error: no .csv found in {raw_dir}")
        sys.exit(3)

    # Output dirs (repo-relative): results/tables and results/figs
    ensure_dir("results/tables")
    ensure_dir("results/figs")

    rows = []
    rows_by_policy = {}

    for fn in sorted(csvs):
        policy = fn[:-4]
        path = os.path.join(raw_dir, fn)
        vals = read_policy_csv(path)
        s = summarize(vals)
        if not s:
            continue
        row = {
            "policy": policy,
            "n": s["n"],
            "mean_s": s["mean"],
            "p50_s": s["p50"],
            "p90_s": s["p90"],
            "min_s": s["min"],
            "max_s": s["max"],
        }
        rows.append(row)
        rows_by_policy[policy] = row

    # sort rows by p50
    rows.sort(key=lambda r: r["p50_s"])

    tag = os.path.basename(raw_dir)
    out_csv = f"results/tables/summary_{tag}.csv"
    out_md  = f"results/tables/summary_{tag}.md"
    write_csv(out_csv, rows, ["policy","n","mean_s","p50_s","p90_s","min_s","max_s"])
    write_md_table(out_md, rows)

    out_png = f"results/figs/same_cluster_{tag}.png"
    ok, msg = try_plot_same_cluster(out_png, rows_by_policy)

    print(f"[OK] Wrote table CSV: {out_csv}")
    print(f"[OK] Wrote table MD : {out_md}")
    if ok:
        print(f"[OK] Wrote figure  : {out_png}")
    else:
        print("[WARN] Figure not generated (matplotlib missing or insufficient policies).")
        print(f"       Reason: {msg}")
        print("       You can still use the tables, or install matplotlib:")
        print("       pkg install python -y && pip install matplotlib")

if __name__ == "__main__":
    main()
