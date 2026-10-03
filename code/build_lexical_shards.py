#!/usr/bin/env python3
"""Lexical shard + static A-Z fallback builder (Site #3 diagnostic, 2026-10-02).

Re-runnable. Called by the 2h iwb-definitions drip via code/dict/build_all.py
main() (after verify), and directly:  python3 code/build_lexical_shards.py

Outputs (all derived from data, never hardcoded):
  data/lexical/shard-<L>.json   one compact JSON array per first letter
      (L = a..z, or "0" for non-alphabetic headwords such as -able).
      Each row: [word, pos, pronunciation, first_sense, stamp].
      For machine crawlers / RAG ingest: the whole headword lexicon split
      into ~27 small files instead of one monolith.
  data/lexical/shards.json      manifest: {letter: {file, count}} + totals.
  az/<L>.html                   pre-rendered static A-Z pages: every headword
      with part of speech, first definition, and a ?w= deep link — readable
      by non-JS bots and humans with JavaScript disabled.
  sitemap-lexical.xml           dedicated lexical sitemap (urlset) listing
      every shard JSON and every static A-Z page; registered in
      sitemap-index.xml (idempotent).

Scope note: only English headwords (k=="w", JAH-DICT-W-######) are sharded
here. Spec/patent catalog terms (k=="t") are NOT duplicated: they are
covered by the sitemap files of their home catalogs, per the dictionary's
sitemap methodology comment in sitemap-index.xml.
"""
import gzip
import json
import os
import re
import sys

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
DATADIR = os.path.join(ROOT, "data", "dict")
LEXDIR = os.path.join(ROOT, "data", "lexical")
AZDIR = os.path.join(ROOT, "az")
BASE = "https://justinahiggins614-cmyk.github.io/jah-dictionary/"
TODAY = None


def log(msg):
    print(msg, flush=True)


def letter_of(word):
    c = (word[:1] or "").lower()
    return c if "a" <= c <= "z" else "0"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def collect():
    """Scan chunks in order; return {letter: [(word,pos,pron,sense,stamp)]}."""
    shards = {}
    files = sorted(f for f in os.listdir(DATADIR)
                   if f.startswith("dict-c") and f.endswith(".jsonl.gz"))
    n = 0
    for fn in files:
        with gzip.open(os.path.join(DATADIR, fn), "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("k") != "w":
                    continue
                w = rec.get("w", "")
                d = rec.get("d") or []
                sense = str(d[0]).strip() if d else ""
                sense = re.sub(r"^\d+\.\s*", "", sense)
                row = [w, rec.get("pos") or "", rec.get("pron") or "",
                       sense, rec.get("st") or ""]
                shards.setdefault(letter_of(w), []).append(row)
                n += 1
    return shards, n


def write_json_shards(shards):
    os.makedirs(LEXDIR, exist_ok=True)
    manifest = {"shards": {}, "total": 0}
    for L in sorted(shards):
        rows = shards[L]
        path = os.path.join(LEXDIR, "shard-%s.json" % L)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
        manifest["shards"][L] = {"file": "data/lexical/shard-%s.json" % L,
                                 "count": len(rows)}
        manifest["total"] += len(rows)
    with open(os.path.join(LEXDIR, "shards.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return manifest


AZ_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — The Signature Dictionary (static A-Z)</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<style>
body{{margin:0;font-family:Georgia,'Times New Roman',serif;background:#faf6ec;color:#2b2118;line-height:1.6}}
.wrap{{max-width:900px;margin:0 auto;padding:18px 16px 60px}}
h1{{color:#1a4d2e;font-family:Arial,sans-serif}}
dt{{font-family:Arial,sans-serif;font-weight:bold;margin-top:10px}}
dt .pos{{font-style:italic;font-weight:normal;color:#6b5f3e}}
dd{{margin:2px 0 8px 0}}
.nav{{font-family:Arial,sans-serif;margin:10px 0}}
.nav a{{margin-right:8px}}
a{{color:#1a4d2e}}
</style>
</head>
<body><div class="wrap">
<p class="nav"><a href="../">IWB Dictionary</a> &rsaquo; static A-Z index</p>
<h1>{heading}</h1>
<p class="nav">{letterlinks}</p>
<dl>
{rows}
</dl>
<p class="nav">{letterlinks}</p>
<p style="font-family:Arial;font-size:.85em;color:#6b5f3e">Static index page generated from the IWB Dictionary data for crawlers and no-JavaScript readers. Full entries (stamps, programs, AI teachers) live at each word's page.</p>
</div></body>
</html>
"""


def write_static_az(shards):
    os.makedirs(AZDIR, exist_ok=True)
    letters = sorted(shards)
    links = " ".join(
        '<a href="%s.html">%s</a>' % (L, L.upper() if L != "0" else "#")
        for L in letters)
    for L in letters:
        rows = shards[L]
        parts = []
        for w, pos, pron, sense, st in rows:
            url = "../?w=" + w.replace(" ", "%20")
            bits = ['<dt><a href="%s">%s</a>' % (esc(url), esc(w))]
            if pos:
                bits.append(' <span class="pos">%s</span>' % esc(pos))
            bits.append('</dt>')
            if sense:
                bits.append('<dd>%s</dd>' % esc(sense[:300]))
            parts.append("".join(bits))
        heading = ("Words beginning with " + L.upper()
                   if L != "0" else "Symbols, affixes and numbers")
        html = AZ_TEMPLATE.format(
            title=esc(heading),
            desc=esc("%d dictionary headwords (%s)" % (len(rows), heading)),
            canon=BASE + "az/%s.html" % L,
            heading=esc(heading),
            letterlinks=links,
            rows="\n".join(parts))
        with open(os.path.join(AZDIR, "%s.html" % L), "w",
                  encoding="utf-8") as f:
            f.write(html)
    return letters


def write_sitemap(letters):
    import datetime
    today = datetime.date.today().isoformat()
    urls = []
    for L in letters:
        urls.append(BASE + "data/lexical/shard-%s.json" % L)
        urls.append(BASE + "az/%s.html" % L)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<!-- LEXICAL SITEMAP (IWB Dictionary): per-letter JSON shards '
             'for machine crawlers + pre-rendered static A-Z pages for '
             'non-JS bots. Rebuilt by code/build_lexical_shards.py on every '
             'dictionary build. -->',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append("  <url><loc>%s</loc><lastmod>%s</lastmod></url>"
                     % (u, today))
    lines.append("</urlset>")
    with open(os.path.join(ROOT, "sitemap-lexical.xml"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    # register in sitemap-index.xml (idempotent)
    idx = os.path.join(ROOT, "sitemap-index.xml")
    with open(idx, encoding="utf-8") as f:
        txt = f.read()
    loc = BASE + "sitemap-lexical.xml"
    if loc not in txt:
        entry = "  <sitemap><loc>%s</loc></sitemap>\n" % loc
        txt = txt.replace("</sitemapindex>", entry + "</sitemapindex>")
        with open(idx, "w", encoding="utf-8") as f:
            f.write(txt)
        log("registered sitemap-lexical.xml in sitemap-index.xml")
    return len(urls)


def build():
    shards, n = collect()
    if not shards:
        log("LEXICAL SHARDS: no headwords found — skipping")
        return
    manifest = write_json_shards(shards)
    letters = write_static_az(shards)
    n_urls = write_sitemap(letters)
    log("LEXICAL SHARDS: %d headwords -> %d letter shards, %d static A-Z "
        "pages, sitemap-lexical.xml (%d urls)" %
        (manifest["total"], len(letters), len(letters), n_urls))


if __name__ == "__main__":
    build()
