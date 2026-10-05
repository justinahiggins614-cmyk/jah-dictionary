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
    # --- social/meta card counts (stale ones here are the "count discrepancy"
    # class of bug: og:description/twitter:description showed 738,298 while
    # the dataset held 811,315) ---
    for attr in ('property="og:description"', 'name="twitter:description"'):
        soc_pat = re.compile(r'(<meta ' + attr + r' content="The Signature Dictionary: )[\d,]+( entries)')
        assert soc_pat.search(html), "social meta count marker not found: " + attr
        html = soc_pat.sub(lambda m: m.group(1) + fmt(entries) + m.group(2), html, count=1)

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

    # --- static home "N-headword ... corpus" line (was hand-typed 102,218) ---
    hw_pat = re.compile(r'(= the )[\d,]+(-headword Signature Dictionary corpus)')
    assert hw_pat.search(html), "headword corpus count marker not found"
    html = hw_pat.sub(lambda m: m.group(1) + fmt(words) + m.group(2), html, count=1)

    # --- prose "N English headwords" mentions (meta + body copy) ---
    # These went stale when the word drip grew the corpus from 102,218 ->
    # 102,223; stamp them from stats.json so they never drift again.
    # meta / og / twitter descriptions: "... original definitions for N English headwords, ..."
    hwmeta_pat = re.compile(r'(original definitions for )[\d,]+( English headwords)')
    matches = hwmeta_pat.findall(html)
    assert matches, "headword meta count marker not found"
    html = hwmeta_pat.sub(lambda m: m.group(1) + fmt(words) + m.group(2), html)
    # Machine-access line: "headwords.csv (word,pos,stamp — N rows)"
    hwcsv_pat = re.compile(r'(\(word,pos,stamp — )[\d,]+( rows\))')
    assert hwcsv_pat.search(html), "headwords.csv rows marker not found"
    html = hwcsv_pat.sub(lambda m: m.group(1) + fmt(words) + m.group(2), html, count=1)
    # Intro line: "(N headwords + JAH catalog terms)"
    hwintro_pat = re.compile(r'\([\d,]+ headwords \+ JAH catalog terms\)')
    assert hwintro_pat.search(html), "intro headword count marker not found"
    html = hwintro_pat.sub('(' + fmt(words) + ' headwords + JAH catalog terms)', html, count=1)

    # --- defined/pending stat rows (added once, then re-stamped) ---
    # Visible naming: official site name is "The Signature Dictionary"; the
    # internal drip files (iwb_drip.jsonl etc.) keep their code IDs, but every
    # user-facing word must use the official name, so a future drip run never
    # reverts the rename.
    defined_block = (
        '<div class="stat" role="listitem" data-stat="defined"><div class="n">' + fmt(defined) +
        '</div><div class="l">Defined headwords &mdash; ' + fmt(authored) +
        ' authored by Signature Dictionary editors, ' + fmt(templated) +
        ' template-derived. The rest await their authored definition.</div></div>\n' +
        '<div class="stat" role="listitem" data-stat="pending"><div class="n">' + fmt(pending) +
        '</div><div class="l">Headwords pending &mdash; real headwords whose authored definition the Signature Dictionary editors are still writing. They carry a deterministic JAH reading now.</div></div>'
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


def stamp_archive():
    """Re-stamp the A-Z archive pages' count headers (stamp_static pattern).

    Called from build_all.py main() AFTER the new index + lexical shards
    flush, so archive counts are never one-run-behind. Idempotent; fail-safe
    (logs and returns False instead of raising) so a half-written archive
    never blocks the build — the full rebuild in build_lexical_shards is the
    primary path and this is the belt-and-suspenders re-stamp.
    """
    try:
        stats = json.load(open(os.path.join(IDXDIR, "stats.json"),
                               encoding="utf-8"))
        man = json.load(open(os.path.join(ROOT, "data", "lexical",
                                          "shards.json"), encoding="utf-8"))
    except Exception as ex:
        print("stamp_archive: skipped (%r)" % ex, flush=True)
        return False
    try:
        sys.path.insert(0, os.path.join(ROOT, "code"))
        import build_lexical_shards as bls
    except Exception as ex:
        print("stamp_archive: skipped (builder import %r)" % ex, flush=True)
        return False
    total_w = stats["words"]
    total_e = stats["total"]
    count_pat = re.compile(r'<p class="azcount"[^>]*>.*?</p>', re.S)
    alln_pat = re.compile(r'(<b class="alln">)[\d,]+(</b>)')
    n = 0
    azdir = os.path.join(ROOT, "az")
    for L, info in man.get("shards", {}).items():
        p = os.path.join(azdir, L + ".html")
        try:
            html = open(p, encoding="utf-8").read()
        except Exception:
            continue
        orig = html
        if count_pat.search(html):
            html = count_pat.sub(
                lambda m: bls.az_count_html(L, info["count"], total_w),
                html, count=1)
        if alln_pat.search(html):
            html = alln_pat.sub(
                lambda m: m.group(1) + fmt(total_e) + m.group(2),
                html, count=1)
        if html != orig:
            open(p, "w", encoding="utf-8").write(html)
            n += 1
    print("stamp_archive: re-stamped %d archive pages (words=%s total=%s)"
          % (n, fmt(total_w), fmt(total_e)), flush=True)
    return True


if __name__ == "__main__":
    main()
