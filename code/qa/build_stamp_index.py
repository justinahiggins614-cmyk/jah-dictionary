#!/usr/bin/env python3
"""Build data/index/stamp.idx.json.gz from the SHIPPED data (no full rebuild).

Reads data/index/dict.idx.json.gz ([key, chunk, line] rows in order), pulls each
entry's stamp from its chunk line, and writes {"W":[idxPos,...],"T":[idxPos,...]}
where element n-1 is the dict.idx row of JAH-DICT-W/T-<n padded to 6> (-1 = gap).

The daily refresh regenerates this file via build_all.py; this script is for
one-off (re)generation. Verifies every stamp resolves back to its own entry.
"""
import gzip
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
DATADIR = os.path.join(ROOT, "data", "dict")
IDXDIR = os.path.join(ROOT, "data", "index")
OUT = os.path.join(IDXDIR, "stamp.idx.json.gz")
pat = re.compile(r"^JAH-DICT-([WT])-(\d+)$")


def main():
    with gzip.open(os.path.join(IDXDIR, "dict.idx.json.gz"), "rt",
                   encoding="utf-8") as f:
        idx = json.load(f)
    by_chunk = defaultdict(list)
    for pos, row in enumerate(idx):
        by_chunk[row[1]].append((pos, row[2]))

    buckets = {"W": {}, "T": {}}
    n = 0
    for cname in sorted(by_chunk):
        with gzip.open(os.path.join(DATADIR, cname), "rt",
                       encoding="utf-8") as f:
            lines = f.read().split("\n")
        for pos, ln in by_chunk[cname]:
            st = json.loads(lines[ln]).get("st", "")
            m = pat.match(st)
            if not m:
                print("WARN: bad stamp %r at idx pos %d" % (st, pos))
                continue
            buckets[m.group(1)][int(m.group(2))] = pos
            n += 1
    out = {}
    for k in ("W", "T"):
        d = buckets[k]
        hi = max(d) if d else 0
        out[k] = [d.get(i, -1) for i in range(1, hi + 1)]
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    size = os.path.getsize(OUT)
    print("wrote %s: %d stamps (W=%d T=%d), %d bytes gz" %
          (OUT, n, len(out["W"]), len(out["T"]), size))

    # verify: every stamp resolves back to the entry carrying it
    with gzip.open(OUT, "rt", encoding="utf-8") as f:
        back = json.load(f)
    bad = 0
    chunk_cache = {}
    for k in ("W", "T"):
        for i, pos in enumerate(back[k], start=1):
            if pos < 0:
                continue
            row = idx[pos]
            cname = row[1]
            if cname not in chunk_cache:
                with gzip.open(os.path.join(DATADIR, cname), "rt",
                               encoding="utf-8") as f:
                    chunk_cache[cname] = f.read().split("\n")
            st = json.loads(chunk_cache[cname][row[2]]).get("st", "")
            want = "JAH-DICT-%s-%06d" % (k, i)
            if st != want:
                bad += 1
                if bad < 5:
                    print("MISMATCH: %s resolved to entry with stamp %s" %
                          (want, st))
    if bad:
        print("VERIFICATION FAILED: %d bad resolutions" % bad)
        return 1
    print("verification: all %d stamps resolve to their own entries" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
