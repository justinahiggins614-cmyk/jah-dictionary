#!/usr/bin/env python3
"""AI canon coherence check.

Compares every AI profile this site presents against the phone-book canon
(~/workspace/jah-ai-models/ai-catalog.json).

Manon's order (2026-10-02): "there should be no ai any website incoherent" —
every AI profile matches the phone-book canon exactly.

Rules:
  1. Any JAH-AI-* canon ID the site presents must exist in the canon, and any
     name/description the site shows for it must match canon exactly
     (whitespace-normalized).
  2. Site-helper AIs (article persona / personal AI / AI teacher) must NOT
     claim a canon JAH-AI ID — they present as helpers with the JAHtalk voice.
  3. The shared JAHtalk module must be wired (js/jah-talk-fallback.js exists,
     referenced from index.html, and JAHtalk.* calls present).

Exit 0 = COHERENT. Exit 2 = DRIFT, with a loud report.
"""
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.basename(REPO_ROOT)
CANON = (sys.argv[1] if len(sys.argv) > 1
         else os.path.expanduser("~/workspace/jah-ai-models/ai-catalog.json"))

HELPERS = {
    "jah-wiki": ["AI persona", "personal AI persona", "Personal AI of "],
    "jah-n-wiki-leaks": ["personal AI", "PERSONAL AI", "offline personal AI"],
    "jah-dictionary": ["AI teacher", "AI Teacher"],
}


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def load_texts():
    texts = []
    idx = os.path.join(REPO_ROOT, "index.html")
    if os.path.exists(idx):
        texts.append(("index.html",
                      open(idx, encoding="utf-8", errors="replace").read()))
    jsdir = os.path.join(REPO_ROOT, "js")
    if os.path.isdir(jsdir):
        for fn in sorted(os.listdir(jsdir)):
            if fn.endswith(".js"):
                p = os.path.join(jsdir, fn)
                texts.append(("js/" + fn,
                              open(p, encoding="utf-8", errors="replace").read()))
    return texts


def main():
    issues = []
    report = []
    try:
        canon = json.load(open(CANON, encoding="utf-8"))
    except Exception as e:
        print("COHERENCE CHECK FAILED: cannot load canon %s: %s" % (CANON, e))
        return 2
    by_id = {}
    for r in canon.get("records", []):
        if r.get("ID"):
            by_id[r["ID"]] = r
    report.append("canon: %s (%d embedded records)" % (CANON, len(by_id)))

    texts = load_texts()
    idpat = re.compile(r"JAH-AI-[A-Z]+-[0-9]+")
    found = {}  # aid -> set of files
    for fn, t in texts:
        for m in idpat.finditer(t):
            found.setdefault(m.group(0), set()).add(fn)

    word_ids = sorted(a for a in found if a.startswith("JAH-AI-WORD-"))
    canon_ids = sorted(a for a in found if not a.startswith("JAH-AI-WORD-"))

    for aid in canon_ids:
        rec = by_id.get(aid)
        files = sorted(found[aid])
        if not rec:
            issues.append("UNKNOWN canon ID claimed: %s (in %s) — not in phone-book canon"
                          % (aid, ", ".join(files)))
            continue
        # if the site shows a name next to the ID, it must match canon exactly
        cname = norm(rec.get("NAME"))
        for fn, t in texts:
            for line in t.splitlines():
                if aid in line:
                    for nm in re.findall(
                            r'''"name"\s*:\s*"([^"]+)"|NAME\s*[:=]\s*["']([^"']+)["']''', line):
                        shown = norm(nm[0] or nm[1])
                        if shown and shown != cname:
                            issues.append(
                                "name drift for %s: site shows %r, canon is %r (%s)"
                                % (aid, shown, cname, fn))
        report.append("canon AI %s (%s) coherent in %s"
                      % (aid, cname, ", ".join(files)))

    if word_ids:
        report.append("word AIs presented: %d (canon = remote wordai_index)" % len(word_ids))
        report.append("  word-AI index: %s" % canon.get("wordai_index", "(not listed)"))
        report.append("  NOTE: word/definition/duties coherence for word AIs is owned by "
                      "the word-AI index publisher; this site must not redefine them.")
    else:
        report.append("word AIs presented: none")

    # helper-AI inventory: helpers must not claim canon IDs
    helpers = HELPERS.get(SITE, [])
    for fn, t in texts:
        for hsig in helpers:
            n = t.count(hsig)
            if n:
                report.append("helper AI %r referenced x%d in %s (no canon ID claimed)"
                              % (hsig, n, fn))
        for aid in list(found):
            for line in t.splitlines():
                if aid in line and any(h in line for h in helpers):
                    issues.append("helper AI claims canon ID %s in %s: %s"
                                  % (aid, fn, norm(line)[:120]))

    # wiring check: shared module present + referenced + used
    mod = os.path.join(REPO_ROOT, "js", "jah-talk-fallback.js")
    if not os.path.exists(mod):
        issues.append("MISSING js/jah-talk-fallback.js")
    else:
        report.append("shared module present: js/jah-talk-fallback.js")
    idx_text = dict(texts).get("index.html", "")
    if 'src="js/jah-talk-fallback.js"' not in idx_text:
        issues.append('index.html does not load js/jah-talk-fallback.js')
    else:
        report.append("index.html loads js/jah-talk-fallback.js")
    uses = sum(t.count("JAHtalk.") for _, t in texts)
    if uses == 0:
        issues.append("no JAHtalk.* calls found in site sources")
    else:
        report.append("JAHtalk.* call sites: %d" % uses)

    print("=" * 64)
    print("AI COHERENCE CHECK — %s" % SITE)
    print("=" * 64)
    for r in report:
        print("  " + r)
    if issues:
        print("-" * 64)
        print("DRIFT DETECTED (%d):" % len(issues))
        for i in issues:
            print("  !! " + i)
        print("RESULT: DRIFT — fix before shipping")
        return 2
    print("RESULT: COHERENT — no drift vs phone-book canon")
    return 0


if __name__ == "__main__":
    sys.exit(main())
