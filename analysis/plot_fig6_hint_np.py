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

def parse_pf_hint(s):
    pf = None; h = None
    m1 = re.search(r"(?:pf)[^\d]*([0-9]+)", s)
    if m1: pf = int(m1.group(1))
    m2 = re.search(r"(?:h|hint)[^\d]*([0-9]+)", s)
    if m2: h = int(m2.group(1))
    return pf, h

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--title", default="Hint tradeoff (PF1): p50/p90")
args = ap.parse_args()

with open(args.csv, newline="") as f:
    rd = csv.DictReader(f)
    rows = list(rd)
    if not rows:
        print("[ERROR] empty csv:", args.csv); sys.exit(2)
    cols = rows[0].keys()

p50col = pick(cols, ["p50","median","P50","lat_p50","p50_s"])
p90col = pick(cols, ["p90","tail","P90","lat_p90","p90_s"])
pfcol  = pick(cols, ["prefetch_cl","pf","prefetch"])
hcol   = pick(cols, ["hint","prefetch_hint","PREFETCH_HINT"])
namecol = pick(cols, ["policy","name","label","config","variant","run","workload"])

data = {}  # hint -> (p50,p90)
for r in rows:
    pf = None; h = None
    if pfcol and r.get(pfcol,"").strip() != "":
        try: pf = int(float(r[pfcol]))
        except: pf = None
    if hcol and r.get(hcol,"").strip() != "":
        try: h = int(float(r[hcol]))
        except: h = None
    if (pf is None or h is None) and namecol:
        pf2, h2 = parse_pf_hint(str(r.get(namecol,"")))
        if pf is None: pf = pf2
        if h is None:  h = h2

    # Prefer PF1 rows if pf info exists
    if pf is not None and pf != 1:
        continue
    if h is None:
        continue
    try:
        p50 = float(r[p50col]); p90 = float(r[p90col])
    except:
        continue
    data[h] = (p50, p90)

# we want hint=3 and hint=0
xs = []
y50 = []
y90 = []
for h in [3, 0]:
    if h in data:
        xs.append(f"PF1 (Hint={h})")
        y50.append(data[h][0])
        y90.append(data[h][1])

if not xs:
    print("[ERROR] No PF1 Hint rows found.")
    print("Columns:", list(cols))
    sys.exit(2)

import numpy as np
ind = np.arange(len(xs))
width = 0.35

plt.figure()
plt.bar(ind - width/2, y50, width, label="p50")
plt.bar(ind + width/2, y90, width, label="p90")
plt.xticks(ind, xs)
plt.ylabel("Latency (s)")
plt.title(args.title)
plt.legend()
plt.tight_layout()
plt.savefig(args.out, dpi=200)
print("[OK] wrote", args.out)
