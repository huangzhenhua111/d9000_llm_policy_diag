#!/usr/bin/env python3
import argparse, csv, re, sys
import matplotlib.pyplot as plt

def pick(d, keys):
    for k in keys:
        if k in d: return k
    lk = {k.lower(): k for k in d}
    for k in keys:
        if k.lower() in lk: return lk[k.lower()]
    return None

def parse_pf(s):
    m = re.search(r"(?:pf|prefetch[_-]?cl|PREFETCH[_-]?CL)[^\d]*([0-9]+)", s)
    return int(m.group(1)) if m else None

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--title", default="Prefetch distance sweep (2T@4,6)")
args = ap.parse_args()

with open(args.csv, newline="") as f:
    rd = csv.DictReader(f)
    rows = list(rd)
    if not rows:
        print("[ERROR] empty csv:", args.csv); sys.exit(2)
    cols = rows[0].keys()

# Try columns
xcol = pick(cols, ["prefetch_cl","prefetch_distance_cl","distance_cl","cl","prefetch_distance"])
p50col = pick(cols, ["p50","median","P50","lat_p50","p50_s"])
p90col = pick(cols, ["p90","tail","P90","lat_p90","p90_s"])
namecol = pick(cols, ["policy","name","label","config","variant","run","workload"])

data = []
for r in rows:
    pf = None
    if xcol and r.get(xcol,"").strip() != "":
        try: pf = int(float(r[xcol]))
        except: pf = None
    if pf is None and namecol:
        pf = parse_pf(str(r.get(namecol,"")))
    if pf is None: 
        continue
    try:
        p50 = float(r[p50col]); p90 = float(r[p90col])
    except:
        continue
    data.append((pf, p50, p90))

if not data:
    print("[ERROR] Cannot infer columns/rows for Fig5.")
    print("Columns:", list(cols))
    sys.exit(2)

data.sort(key=lambda x: x[0])
xs = [d[0] for d in data]
y50 = [d[1] for d in data]
y90 = [d[2] for d in data]

plt.figure()
plt.plot(xs, y50, marker="o", label="p50")
plt.plot(xs, y90, marker="o", linestyle="--", label="p90")
plt.xlabel("Prefetch distance (cache lines)")
plt.ylabel("Latency (s)")
plt.title(args.title)
plt.legend()
plt.tight_layout()
plt.savefig(args.out, dpi=200)
print("[OK] wrote", args.out)
