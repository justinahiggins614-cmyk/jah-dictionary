#!/usr/bin/env python3
"""TIER 2-8 checker: duplicate IDs and duplicate keys.
Scans every data/dict chunk for:
  - duplicate stamps (e.st) -- must be zero; stamps are permanent entry IDs
  - duplicate keys (headword collisions, e.g. a word and a catalog term sharing
    a title) -- reported as INFO with the colliding stamps/kinds, since the
    renderer shows the first row and the disambiguation row links the rest.
Exits 1 only on duplicate stamps.
"""
import gzip
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
DATADIR = os.path.join(ROOT, "data", "dict")

failures = []
collisions = defaultdict(list)


def main():
    seen_stamp = {}
    n = 0
    for cf in sorted(os.listdir(DATADIR)):
        if not (cf.startswith("dict-c") and cf.endswith(".jsonl.gz")):
            continue
        with gzip.open(os.path.join(DATADIR, cf), "rt", encoding="utf-8") as f:
            for ln, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                n += 1
                e = json.loads(line)
                st = e.get("st")
                if not st:
                    failures.append("missing stamp in %s line %d (key=%r)" %
                                    (cf, ln, e.get("w")))
                    continue
                if st in seen_stamp:
                    failures.append("DUPLICATE STAMP %s: %s line %d and %s" %
                                    (st, cf, ln, seen_stamp[st]))
                else:
                    seen_stamp[st] = "%s line %d" % (cf, ln)
                # key for collision detection mirrors the builder's index key
                key = str(e.get("w", "")).lower()
                collisions[key].append((st, e.get("k"), e.get("rt") or ""))

    dup_keys = {k: v for k, v in collisions.items() if len(v) > 1}
    print("entries scanned: %d" % n)
    print("unique stamps: %d" % len(seen_stamp))
    print("duplicate-stamp failures: %d" % len(failures))
    for msg in failures[:20]:
        print("FAIL: " + msg)
    print("keys with >1 entry (disambiguation candidates): %d" % len(dup_keys))
    for k in sorted(dup_keys)[:20]:
        print("  key=%r -> %s" % (k, dup_keys[k]))
    if len(dup_keys) > 20:
        print("  ... and %d more" % (len(dup_keys) - 20))
    # stash full collision list for the page renderer / report
    with open(os.path.join(os.path.dirname(__file__), "dupe_keys.json"), "w",
              encoding="utf-8") as f:
        json.dump({k: v for k, v in sorted(dup_keys.items())}, f)
    if failures:
        print("\nDUPE-ID CHECK FAILED")
        return 1
    print("\nDUPE-ID CHECK PASSED (0 duplicate stamps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
