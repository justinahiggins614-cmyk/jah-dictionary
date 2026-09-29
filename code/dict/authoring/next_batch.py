#!/usr/bin/env python3
"""Print the next N headwords still lacking an IWB definition (alphabetical)."""
import json, os, sys
ROOT = os.path.expanduser("~/workspace/jah-dictionary")
args=[a for a in sys.argv[1:] if a!="--n"]
n = int(args[0]) if args else 800
defined=set()
for fn in ["all.jsonl"]:
    p=os.path.join(ROOT,"data","definitions",fn)
    if os.path.exists(p):
        for line in open(p,encoding="utf-8"):
            try: defined.add(json.loads(line)["w"].lower())
            except Exception: pass
raw=json.load(open(os.path.join(ROOT,"code","dict","build","dictionary.json")))
pending=sorted([w for w in raw if w and w.lower() not in defined])
print("PENDING_TOTAL %d" % len(pending))
for w in pending[:n]: print(w)
