#!/usr/bin/env python3
"""TIER 2-8 checker: count-vs-data.
Compares data/index/stats.json against the actual shipped data:
  - number of data/dict/dict-cNNNNN.jsonl.gz chunks and their line counts
  - length of data/index/dict.idx.json.gz
  - words (k=='w') vs terms (k=='t') split
Fails (exit 1) on any mismatch. All counts derived from data, never hardcoded.
"""
import gzip
import json
import os
import sys

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
DATADIR = os.path.join(ROOT, "data", "dict")
IDXDIR = os.path.join(ROOT, "data", "index")

failures = []


def fail(msg):
    failures.append(msg)
    print("FAIL: " + msg)


def ok(msg):
    print("ok: " + msg)


def main():
    stats_path = os.path.join(IDXDIR, "stats.json")
    idx_path = os.path.join(IDXDIR, "dict.idx.json.gz")
    stats = json.load(open(stats_path, encoding="utf-8"))
    with gzip.open(idx_path, "rt", encoding="utf-8") as f:
        idx = json.load(f)

    # count real entries in chunks
    chunk_files = sorted(f for f in os.listdir(DATADIR)
                         if f.startswith("dict-c") and f.endswith(".jsonl.gz"))
    n_entries = 0
    n_words = n_terms = 0
    for cf in chunk_files:
        with gzip.open(os.path.join(DATADIR, cf), "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                n_entries += 1
                try:
                    e = json.loads(line)
                except Exception:
                    fail("unparseable line in %s" % cf)
                    continue
                if e.get("k") == "w":
                    n_words += 1
                elif e.get("k") == "t":
                    n_terms += 1
    ok("chunks=%d entries=%d words=%d terms=%d" %
       (len(chunk_files), n_entries, n_words, n_terms))

    if len(idx) != n_entries:
        fail("dict.idx length %d != chunk entry total %d" % (len(idx), n_entries))
    else:
        ok("dict.idx length matches chunk total (%d)" % len(idx))

    for field, actual in (("entry_count", n_entries), ("total", n_entries),
                          ("words", n_words), ("terms", n_terms)):
        if stats.get(field) != actual:
            fail("stats.json %s=%r != data %d" % (field, stats.get(field), actual))
        else:
            ok("stats.json %s=%d matches data" % (field, actual))

    # every idx row must point at a real chunk+line
    bad = 0
    for r in idx:
        if len(r) != 3 or not isinstance(r[2], int):
            bad += 1
    if bad:
        fail("%d malformed idx rows" % bad)
    else:
        ok("all %d idx rows well-formed [key, chunk, line]" % len(idx))

    keys = [r[0] for r in idx]
    if any(keys[i] > keys[i + 1] for i in range(len(keys) - 1)):
        fail("dict.idx not sorted by key")
    else:
        ok("dict.idx sorted by key")

    if failures:
        print("\n%d FAILURES" % len(failures))
        return 1
    print("\nALL COUNT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
