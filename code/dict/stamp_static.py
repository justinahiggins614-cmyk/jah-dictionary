#!/usr/bin/env python3
"""Site #3 fix-list: stamp the no-JavaScript static snapshot in index.html.

The static "Dictionary counts" drawer is hand-typed HTML that goes stale the
moment the 2h iwb-definitions-drip grows the dataset (it was showing 577,742
while the real index held 738,298). This module rewrites that section from
data/index/stats.json + data/definitions/coverage.json on every build_all.py
run, so the static fallback is never a lie.

Stamps, idempotently:
  - entries / headwords / catalog-term static counts
  - defined (authored + template) / pending-definition counts (new stat rows)
  - "Snapshot as of <date>" line + "last synchronized" timestamp
  - meta description entry count
All replacements are asserted; a missed marker fails loudly, never silently.
"""
import json
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", ".."))
IDXDIR = os.path.join(ROOT, "data", "index")
DEFPATH = os.path.join(ROOT, "data", "definitions", "coverage.json")


def fmt(n):
    return "{:,}".format(int(n))


def main():
    stats = json.load(open(os.path.join(IDXDIR, "stats.json"), encoding="utf-8"))
    try:
        cov = json.load(open(DEFPATH, encoding="utf-8"))
    except Exception:
        cov = {"defined": 0, "authored": 0, "templates": 0, "pending": 0}
    entries = stats["total"]
    words = stats["words"]
    terms = stats["terms"]
    defined = cov.get("defined", 0)
    authored = cov.get("authored", 0)
    templated = cov.get("templates", 0)
    pending = cov.get("pending", 0)
    date = stats.get("last_updated", "")
    gen_at = stats.get("generated_at", "")
    rev = stats.get("catalog_revision", "")

    p = os.path.join(ROOT, "index.html")
    html = open(p, encoding="utf-8").read()
    orig = html

    # --- meta description count ---
    meta_pat = re.compile(r'(<meta name="description" content="The Signature Dictionary: )[\d,]+( entries)')
    assert meta_pat.search(html), "meta description count marker not found"
    html = meta_pat.sub(lambda m: m.group(1) + fmt(entries) + m.group(2), html, count=1)

    # --- snapshot date line ---
    date_pat = re.compile(r'Snapshot as of <b>\d{4}-\d{2}-\d{2}</b>')
    assert date_pat.search(html), "snapshot date marker not found"
    html = date_pat.sub('Snapshot as of <b>' + date + '</b>', html, count=1)

    # --- the three static stat numbers ---
    def stat(label_pat, value):
        nonlocal html
        pat = re.compile(r'(<div class="stat" role="listitem"><div class="n">)[\d,]+(</div><div class="l">' + label_pat + r'[^<]*</div></div>)')
        assert pat.search(html), "stat marker not found: " + label_pat
        html = pat.sub(lambda m: m.group(1) + fmt(value) + m.group(2), html, count=1)

    stat(r'Entries', entries)
    stat(r'Headwords', words)
    stat(r'Catalog terms', terms)

    # --- defined/pending stat rows (added once, then re-stamped) ---
    defined_block = (
        '<div class="stat" role="listitem" data-stat="defined"><div class="n">' + fmt(defined) +
        '</div><div class="l">Defined headwords &mdash; ' + fmt(authored) +
        ' authored by IWB editors, ' + fmt(templated) +
        ' template-derived. The rest await their authored definition.</div></div>\n' +
        '<div class="stat" role="listitem" data-stat="pending"><div class="n">' + fmt(pending) +
        '</div><div class="l">Headwords pending &mdash; real headwords whose authored definition the IWB editors are still writing. They carry a deterministic JAH reading now.</div></div>'
    )
    if 'data-stat="defined"' in html:
        dp_pat = re.compile(r'<div class="stat" role="listitem" data-stat="defined">.*?</div></div>\n'
                       r'<div class="stat" role="listitem" data-stat="pending">.*?</div></div>', re.S)
        assert dp_pat.search(html), "defined/pending stat markers not found"
        html = dp_pat.sub(lambda m: defined_block, html, count=1)
    else:
        anchor = '</div></details>\n<p class="jahstatus"><b>Word programs:</b>'
        assert anchor in html, "stat drawer anchor not found"
        html = html.replace(anchor, '</div>\n' + defined_block + '</details>\n<p class="jahstatus"><b>Word programs:</b>', 1)

    # --- last-synchronized line (added once, then re-stamped) ---
    sync_line = ('<p class="jahstatus" data-sync="1">Last synchronized: <b>' + date +
                 '</b>' + (' at ' + gen_at[:16].replace('T', ' ') + ' UTC' if gen_at else '') +
                 (' &middot; catalog revision <b>r' + str(rev) + '</b>' if rev else '') +
                 ' &middot; counts generated from the dataset above, never hand-typed.</p>')
    if 'data-sync="1"' in html:
        sync_pat = re.compile(r'<p class="jahstatus" data-sync="1">.*?</p>', re.S)
        assert sync_pat.search(html), "sync line marker not found"
        html = sync_pat.sub(lambda m: sync_line, html, count=1)
    else:
        anchor2 = '<p class="jahstatus"><b>Word programs:</b>'
        assert anchor2 in html, "sync line anchor not found"
        html = html.replace(anchor2, sync_line + '\n' + anchor2, 1)

    if html != orig:
        open(p, "w", encoding="utf-8").write(html)
    print("stamp_static: entries=%s words=%s terms=%s defined=%s pending=%s date=%s rev=%s"
          % (fmt(entries), fmt(words), fmt(terms), fmt(defined), fmt(pending), date, rev))


if __name__ == "__main__":
    main()
