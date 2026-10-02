#!/usr/bin/env python3
"""TIER 2-8 checker: missing IDs in the stamp sequences.
Word stamps JAH-DICT-W-###### are assigned alphabetically over a static set,
so 1..N must be fully contiguous -- any gap is a FAIL.
Term stamps JAH-DICT-T-###### are preserved forever and never renumbered, so
gaps are legal (a withdrawn term leaves a hole); they are reported as INFO.
"""
import gzip
import json
import os
import re
import sys

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
DATADIR = os.path.join(ROOT, "data", "dict")


def main():
    w_nums, t_nums = set(), set()
    bad_fmt = 0
    pat = re.compile(r"^JAH-DICT-([WT])-(\d{6})$")
    for cf in sorted(os.listdir(DATADIR)):
        if not (cf.startswith("dict-c") and cf.endswith(".jsonl.gz")):
            continue
        with gzip.open(os.path.join(DATADIR, cf), "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                st = json.loads(line).get("st", "")
                m = pat.match(st)
                if not m:
                    bad_fmt += 1
                    continue
                (w_nums if m.group(1) == "W" else t_nums).add(int(m.group(2)))

    rc = 0
    if bad_fmt:
        print("FAIL: %d stamps with bad format" % bad_fmt)
        rc = 1
    else:
        print("ok: all stamps match JAH-DICT-[WT]-######")

    if w_nums:
        lo, hi = min(w_nums), max(w_nums)
        missing_w = [i for i in range(lo, hi + 1) if i not in w_nums]
        print("word stamps: %d entries, range %06d..%06d" % (len(w_nums), lo, hi))
        if missing_w:
            print("FAIL: %d missing word-stamp numbers: %s%s" %
                  (len(missing_w), missing_w[:20],
                   "..." if len(missing_w) > 20 else ""))
            rc = 1
        else:
            print("ok: word-stamp sequence fully contiguous (no gaps)")
    if t_nums:
        lo, hi = min(t_nums), max(t_nums)
        missing_t = [i for i in range(lo, hi + 1) if i not in t_nums]
        print("term stamps: %d entries, range %06d..%06d, gaps (legal): %d" %
              (len(t_nums), lo, hi, len(missing_t)))
        if missing_t[:10]:
            print("  first gaps: %s" %
                  ", ".join("JAH-DICT-T-%06d" % i for i in missing_t[:10]))

    print("\nMISSING-ID CHECK %s" % ("FAILED" if rc else "PASSED"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
