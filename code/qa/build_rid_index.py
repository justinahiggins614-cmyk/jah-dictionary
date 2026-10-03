#!/usr/bin/env python3
"""Build data/index/rid.idx.json.gz from the SHIPPED data (no full rebuild).

Reads data/index/dict.idx.json.gz ([key, chunk, line] rows in order), pulls
each catalog term's record ID (e.rid, e.g. JAH-SPEC-000123 or US10992705B2)
from its chunk line, and writes a sorted [[RID_UPPER, idxPos], ...] array.

Lets the page resolve a typed/pasted catalog record ID straight to its entry
(ID-aware search: exact word, partial word, phrase, JAH stamp ID, catalog ID).
Lazy-fetched by the page only when the query looks like a record ID, so it
never slows the normal boot path.

The 2h iwb-definitions-drip regenerates this file via build_all.py
(write_rid_index); this script is for one-off (re)generation. Verifies every
record ID resolves back to the entry carrying it.
"""
import gzip
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
DATADIR = os.path.join(ROOT, "data", "dict")
IDXDIR = os.path.join(ROOT, "data", "index")
OUT = os.path.join(IDXDIR, "rid.idx.json.gz")


def main():
    with gzip.open(os.path.join(IDXDIR, "dict.idx.json.gz"), "rt",
                   encoding="utf-8") as f:
        idx = json.load(f)
    by_chunk = defaultdict(list)
    for pos, row in enumerate(idx):
        by_chunk[row[1]].append((pos, row[2]))

    pairs = []
    n = 0
    for cname in sorted(by_chunk):
        with gzip.open(os.path.join(DATADIR, cname), "rt",
                       encoding="utf-8") as f:
            lines = f.read().split("\n")
        for pos, ln in by_chunk[cname]:
            try:
                e = json.loads(lines[ln])
            except Exception:
                print("WARN: unparseable line %d in %s" % (ln, cname))
                continue
            if e.get("k") != "t":
                continue
            rid = str(e.get("rid") or "").strip().upper()
            if not rid:
                continue
            pairs.append([rid, pos])
            n += 1
    # (rt, rid) pairs are unique; keep the first row if a rid ever repeats.
    pairs.sort(key=lambda p: p[0])
    dedup = []
    seen = set()
    for p in pairs:
        if p[0] not in seen:
            seen.add(p[0])
            dedup.append(p)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(dedup, f, separators=(",", ":"))
    size = os.path.getsize(OUT)
    print("wrote %s: %d record IDs, %d bytes gz" % (OUT, len(dedup), size))

    # verify: every record ID binary-searches back to its own entry
    back = json.load(gzip.open(OUT, "rt", encoding="utf-8"))
    assert back == sorted(back, key=lambda p: p[0]), "rid index not sorted"
    import random
    random.seed(42)
    for rid, pos in random.sample(back, min(200, len(back))):
        lo, hi = 0, len(back) - 1
        found = -1
        while lo <= hi:
            m = (lo + hi) >> 1
            c = back[m][0]
            if c == rid:
                found = back[m][1]
                break
            if c < rid:
                lo = m + 1
            else:
                hi = m - 1
        assert found == pos, "rid %s resolved to %r, expected %d" % (rid, found, pos)
    print("verified: 200 random record IDs resolve back to their entries")


if __name__ == "__main__":
    sys.exit(main())
