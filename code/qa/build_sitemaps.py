#!/usr/bin/env python3
"""Polish pass 3: public discoverability + machine readability.

Rebuilds the dictionary's XML sitemaps from the shipped data and exports
the headword CSV.

METHODOLOGY (also written as a comment into sitemap-index.xml):
  - The dictionary index holds every entry (headwords + catalog terms), but
    only the headwords (~102k) are sitemapped here as ?w= deep links,
    split into 50k-URL files (the sitemap protocol limit).
  - Spec/patent catalog term entries (JAH-DICT-T-######) are NOT duplicated
    here: they are covered by the sitemap files of their home catalogs
    (the Signature Spec Catalog and the Globally Rejustered Patent Catalog),
    which are the authoritative records. The dictionary still serves every
    term through its ?w= and ?id= deep links, and every term entry page
    cross-links its home catalog.
  - A-Z browse pages and the home page are sitemapped in sitemap-pages.xml.

All counts derived from data, never hardcoded.
"""
import csv
import gzip
import json
import os
import sys
from urllib.parse import quote

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
DATADIR = os.path.join(ROOT, "data", "dict")
IDXDIR = os.path.join(ROOT, "data", "index")
BASE = "https://justinahiggins614-cmyk.github.io/jah-dictionary/"
CHUNK_SIZE = 50000  # sitemap protocol limit per file


def esc_xml(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def w_url(word):
    # mirror JS encodeURIComponent() used by linkW() in index.html
    return BASE + "?w=" + quote(word, safe="-_.!~*'()")


def collect_headwords():
    """Headwords from the freshly-built lexical shards (fast path), falling
    back to a full chunk scan when the shards are absent. Returns
    (word, pos, stamp) with first occurrence kept (stable stamps).

    NOTE: build_all.py runs build_lexical_shards BEFORE this module, so the
    shards always reflect the current run — the sitemap never goes
    one-run-behind.
    """
    sharddir = os.path.join(ROOT, "data", "lexical")
    letters = sorted(f[6:-5] for f in os.listdir(sharddir)
                     if f.startswith("shard-") and f.endswith(".json")) \
        if os.path.isdir(sharddir) else []
    out, seen = [], set()
    if letters:
        for L in letters:
            rows = json.load(open(os.path.join(sharddir, "shard-%s.json" % L),
                                  encoding="utf-8"))
            for row in rows:
                w = row[0]
                if w in seen:  # keep first occurrence (stable stamps)
                    continue
                seen.add(w)
                out.append((w, row[1], row[4]))
        print("collect_headwords: %d from lexical shards" % len(out))
        return out
    # fallback: full chunk scan (old behavior)
    files = sorted(f for f in os.listdir(DATADIR)
                   if f.startswith("dict-c") and f.endswith(".jsonl.gz"))
    for fn in files:
        path = os.path.join(DATADIR, fn)
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("k") != "w":
                    continue
                w = rec["w"]
                if w in seen:  # keep first occurrence (stable stamps)
                    continue
                seen.add(w)
                out.append((w, rec.get("pos", ""), rec.get("st", "")))
    print("collect_headwords: %d from chunk scan (shards absent)" % len(out))
    return out


def write_csv(headwords):
    path = os.path.join(IDXDIR, "..", "headwords.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word", "pos", "stamp"])
        for word, pos, stamp in headwords:
            w.writerow([word, pos, stamp])
    return path


def url_entry(loc, freq):
    return "  <url><loc>" + esc_xml(loc) + "</loc><changefreq>" + freq + "</changefreq></url>\n"


def write_word_sitemaps(headwords):
    files = []
    for i in range(0, len(headwords), CHUNK_SIZE):
        part = headwords[i:i + CHUNK_SIZE]
        name = "sitemap-words-%d.xml" % (i // CHUNK_SIZE + 1)
        body = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
                "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"]
        for word, _pos, _stamp in part:
            body.append(url_entry(w_url(word), "monthly").strip())
        body.append("</urlset>")
        path = os.path.join(ROOT, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")
        files.append(name)
    return files


def write_pages_sitemap():
    name = "sitemap-pages.xml"
    body = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"]
    body.append(url_entry(BASE + "index.html", "weekly").strip())
    for c in range(65, 91):  # A-Z browse pages (?az=A ... ?az=Z)
        body.append(url_entry(BASE + "?az=" + chr(c), "weekly").strip())
    # the A-Z word archive: static az/<L>.html collapsible catalog pages
    azdir = os.path.join(ROOT, "az")
    for L in ["0"] + [chr(c) for c in range(97, 123)]:
        if os.path.exists(os.path.join(azdir, L + ".html")):
            body.append(url_entry(BASE + "az/%s.html" % L, "weekly").strip())
    body.append("</urlset>")
    path = os.path.join(ROOT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n")
    return name


METHODOLOGY_COMMENT = """<!-- SITEMAP METHODOLOGY (The Signature Dictionary)
     Only headwords (English words, JAH-DICT-W-###### stamps) are listed as
     ?w= deep links here, in 50,000-URL files (the sitemap protocol limit).
     The dictionary also indexes spec/patent catalog terms (JAH-DICT-T-######),
     but those are NOT duplicated here: they are covered by the sitemap files
     of their home catalogs — the Signature Spec Catalog
     (signature-one-archive) and the Globally Rejustered Patent Catalog
     (cyber-patent-catalog) — which are the authoritative records for those
     titles. Every term is still reachable on this site through its ?w= and
     ?id= deep links, and each term entry page cross-links its home catalog.
     A-Z browse pages (?az=A..Z), the static A-Z word archive pages
     (az/a.html .. az/z.html, az/0.html) and the home page are sitemapped in
     sitemap-pages.xml. Machine-readable per-letter JSON shards are sitemapped
     in sitemap-lexical.xml. -->"""


def write_index(files):
    lines = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", METHODOLOGY_COMMENT,
             "<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"]
    for name in files:
        lines.append("  <sitemap><loc>" + esc_xml(BASE + name) + "</loc></sitemap>")
    lines.append("</sitemapindex>")
    path = os.path.join(ROOT, "sitemap-index.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def remove_legacy():
    for name in os.listdir(ROOT):
        if (name.startswith("sitemap-records-") or name == "sitemap.xml") \
                and name.endswith(".xml"):
            os.remove(os.path.join(ROOT, name))
            print("removed legacy " + name)


def main():
    stats = json.load(open(os.path.join(IDXDIR, "stats.json"), encoding="utf-8"))
    headwords = collect_headwords()
    print("headwords collected: %d (stats.json words=%s)" % (len(headwords), stats.get("words")))
    assert len(headwords) == stats.get("words"), \
        "COUNT MISMATCH: sitemap headwords=%d but stats.json words=%s" % (len(headwords), stats.get("words"))
    csv_path = write_csv(headwords)
    print("wrote %s (%d rows)" % (csv_path, len(headwords)))
    files = write_word_sitemaps(headwords)
    files = [write_pages_sitemap()] + files
    print("sitemap files: " + ", ".join(files))
    write_index(files)
    print("wrote sitemap-index.xml")
    remove_legacy()


if __name__ == "__main__":
    main()
