#!/usr/bin/env python3
"""Merge IWB definitions: authored batches + drip file (last wins) + templates.
Writes data/definitions/all.jsonl and data/definitions/coverage.json."""
import json, glob, os
ROOT = os.path.expanduser("~/workspace/jah-dictionary")
DDEF = os.path.join(ROOT, "data", "definitions")
merged, order = {}, []
def add(path):
    n=0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: r=json.loads(line)
            except Exception: continue
            w=str(r.get("w",""))
            if not w: continue
            key=w.lower(); r["src"]=r.get("src") or "iwb"
            d=r.get("d") or []
            r["d"]=[str(s).strip() for s in d if str(s).strip()][:3]
            if key not in merged: order.append(key)
            merged[key]=r; n+=1
    return n
na=sum(add(f) for f in sorted(glob.glob(os.path.join(DDEF,"iwb_batch_*.jsonl"))))
nd=add(os.path.join(DDEF,"iwb_drip.jsonl")) if os.path.exists(os.path.join(DDEF,"iwb_drip.jsonl")) else 0
nt=0
with open(os.path.join(DDEF,"templates.jsonl"), encoding="utf-8") as f:
    for line in f:
        r=json.loads(line); key=r["w"].lower()
        if key not in merged: merged[key]=r; order.append(key); nt+=1
with open(os.path.join(DDEF,"all.jsonl"),"w",encoding="utf-8") as out:
    for k in order: out.write(json.dumps(merged[k],ensure_ascii=False)+"\n")
raw=json.load(open(os.path.join(ROOT,"code","dict","build","dictionary.json")))
missing=[w for w in raw if w.lower() not in merged]
json.dump({"defined":len(merged),
           "authored":sum(1 for v in merged.values() if v.get("src")=="iwb"),
           "templates":nt,"pending":len(missing)}, open(os.path.join(DDEF,"coverage.json"),"w"), indent=1)
print("authored(batch+drip): %d+%d  templates: %d  total: %d  pending: %d" % (na,nd,nt,len(merged),len(missing)))
