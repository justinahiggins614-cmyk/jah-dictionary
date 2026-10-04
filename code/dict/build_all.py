#!/usr/bin/env python3
"""Build JAH Dictionary data (Project 5).

Words: headword list with original IWB Dictionary definitions (data/definitions/all.jsonl);
  code/dict/build/dictionary.json  ->  build cache code/dict/build/words.jsonl
Terms: one dictionary entry per spec (signature-one-archive + ALL its shard clones,
  enumerated dynamically so new shards are picked up automatically) and per public
  patent (cyber-patent-catalog index).

Outputs:
  data/dict/dict-cNNNNN.jsonl.gz   (1000 entries per chunk, sorted by key)
  data/index/dict.idx.json.gz      ([[key, chunkFile, lineNo], ...] sorted)
  data/index/stats.json

Idempotent: re-runnable; the daily cron re-runs it. Stamp numbers are stable:
words are stamped alphabetically (static set); term stamps (JAH-DICT-T-######)
are preserved by (record-type, record-id) across rebuilds — previously shipped
stamps are re-read from the existing chunks and reused, new terms continue from
the highest shipped number. Stamps are never renumbered.
"""
import bisect
import datetime
import glob
import gzip
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from enrich import build_families, enrich_entry  # noqa: E402

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
BUILD = os.path.join(ROOT, "code", "dict", "build")
DICT_JSON = os.path.join(BUILD, "dictionary.json")
WORDS_CACHE = os.path.join(BUILD, "words.jsonl")
DATADIR = os.path.join(ROOT, "data", "dict")
IDXDIR = os.path.join(ROOT, "data", "index")
def spec_index_paths():
    """All spec catalog index files: main repo + every shard clone, enumerated
    dynamically (new shards are picked up automatically)."""
    paths = []
    for clone in sorted(glob.glob(os.path.expanduser("~/workspace/signature-one-archive*"))):
        p = os.path.join(clone, "data", "index", "specs.idx.json.gz")
        if os.path.isdir(clone) and os.path.exists(p):
            paths.append(p)
        else:
            log("WARN: no spec index at %s" % p)
    return paths


SPEC_IDXS = None  # resolved per-run via spec_index_paths()
PAT_IDX = os.path.expanduser("~/workspace/cyber-patent-catalog/data/patents.idx.json.gz")
CHUNK_SIZE = 1000


def log(msg):
    print(msg, flush=True)


DEF_JSONL = os.path.join(ROOT, "data", "definitions", "all.jsonl")

def load_iwb_defs():
    """Load IWB Dictionary definitions: {key: {'d':[senses],'pos':pos,'src':src}}."""
    defs = {}
    if os.path.exists(DEF_JSONL):
        with open(DEF_JSONL, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                w = str(r.get("w", ""))
                if not w:
                    continue
                d = r.get("d") or []
                d = [str(s).strip() for s in d if str(s).strip()][:3]
                defs[w.lower()] = {"d": d, "pos": str(r.get("pos", "") or ""),
                                   "src": str(r.get("src", "") or ""),
                                   "links": r.get("links") or [],
                                   "unsure": bool(r.get("unsure", False))}
    return defs

def load_old_word_stamps():
    """Re-read word stamps from the currently shipped chunks: {key: stamp}
    plus the highest shipped W-number. Word stamps are permanent entry IDs
    and are never renumbered across rebuilds (same rule as term stamps in
    load_old_term_stamps) — adding a headword must not shift 90k existing
    IDs."""
    stamps = {}
    maxn = 0
    if not os.path.isdir(DATADIR):
        return stamps, maxn
    for n in sorted(os.listdir(DATADIR)):
        if not (n.startswith("dict-c") and n.endswith(".jsonl.gz")):
            continue
        with gzip.open(os.path.join(DATADIR, n), "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("k") == "w" and e.get("st") and e.get("w"):
                    stamps[str(e["w"]).lower()] = e["st"]
                    m = re.search(r"(\d+)$", str(e["st"]))
                    if m:
                        maxn = max(maxn, int(m.group(1)))
    return stamps, maxn


def parse_words():
    """Headwords from dictionary.json (word list only); definitions from the
    IWB definitions file (data/definitions/all.jsonl). Words whose IWB
    definition is still being written ship with d=[] and defsrc='pending'."""
    with open(DICT_JSON, encoding="utf-8") as f:
        raw = json.load(f)
    log("dictionary.json entries: %d" % len(raw))
    iwb = load_iwb_defs()
    log("IWB definitions loaded: %d" % len(iwb))
    words = []
    seen_keys = set()
    for word in raw.keys():
        if not word:
            continue
        word = str(word)
        key = word.lower()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        rec = iwb.get(key, {})
        senses = rec.get("d", [])
        words.append({"w": word, "k": "w", "key": key, "d": senses,
                      "pos": rec.get("pos", ""),
                      "links": rec.get("links", []),
                      "unsure": bool(rec.get("unsure", False)),
                      "defsrc": rec.get("src", "") or "pending"})
    words.sort(key=lambda e: e["key"])
    # Stable word stamps: keep every existing stamp (the stamp is the entry's
    # permanent machine identity); brand-new headwords continue from the
    # highest shipped W-number. Never renumber.
    old_stamps, max_w = load_old_word_stamps()
    nxt = max_w + 1
    for e in words:
        if e["key"] in old_stamps:
            e["st"] = old_stamps[e["key"]]
        else:
            e["st"] = "JAH-DICT-W-%06d" % nxt
            nxt += 1
    log("word stamps: %d preserved, %d new (from W-%06d)" %
        (len(old_stamps), nxt - max_w - 1, max_w + 1))
    ndef = sum(1 for e in words if e["d"])
    log("words with IWB definitions: %d / %d" % (ndef, len(words)))
    return words


def write_words_cache(words):
    os.makedirs(BUILD, exist_ok=True)
    with open(WORDS_CACHE, "w", encoding="utf-8") as f:
        for e in words:
            f.write(json.dumps({"w": e["w"], "d": e["d"]}, ensure_ascii=False) + "\n")
    with open(os.path.join(ROOT, "code", "dict", ".gitignore"), "w") as f:
        f.write("build/\n")
    log("words cache: %s (%d entries)" % (WORDS_CACHE, len(words)))


def spec_rows(spec_idx_paths):
    """Stream (spec_id, title, abstract, cpc) from all spec indexes."""
    for path in spec_idx_paths:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                rid = r[0] if len(r) > 0 else ""
                title = r[1] if len(r) > 1 and r[1] else ""
                abstract = r[2] if len(r) > 2 and r[2] else ""
                cpc = r[4] if len(r) > 4 and r[4] else ""
                yield (str(rid), str(title), str(abstract), str(cpc))


def patent_rows():
    """Load [(pubnum, title, cpc, assignee)] from the patent index."""
    with gzip.open(PAT_IDX, "rt", encoding="utf-8") as f:
        pats = json.load(f)
    out = []
    for p in pats:
        pub = str(p[0]) if len(p) > 0 and p[0] is not None else ""
        title = str(p[1]) if len(p) > 1 and p[1] else ""
        cpc = str(p[2]) if len(p) > 2 and p[2] else ""
        assignee = str(p[3]) if len(p) > 3 and p[3] else ""
        out.append((pub, title, cpc, assignee))
    return out


def load_old_term_stamps():
    """Re-read term stamps from the currently shipped chunks: {(rt, rid): stamp}
    plus the highest shipped T-number. Stamps are permanent entry IDs and are
    never renumbered across rebuilds."""
    stamps = {}
    maxn = 0
    if not os.path.isdir(DATADIR):
        return stamps, maxn
    for n in sorted(os.listdir(DATADIR)):
        if not (n.startswith("dict-c") and n.endswith(".jsonl.gz")):
            continue
        with gzip.open(os.path.join(DATADIR, n), "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("k") == "t" and e.get("st") and e.get("rid"):
                    stamps[(str(e.get("rt", "")), str(e["rid"]))] = e["st"]
                    m = re.search(r"(\d+)$", str(e["st"]))
                    if m:
                        maxn = max(maxn, int(m.group(1)))
    return stamps, maxn


def build_counts(wordset, spec_titles, pat_titles):
    spec_counts = {}
    for t in spec_titles:
        for tok in re.findall(r"[a-z]{3,}", t.lower()):
            if tok in wordset:
                spec_counts[tok] = spec_counts.get(tok, 0) + 1
    pat_counts = {}
    for t in pat_titles:
        for tok in re.findall(r"[a-z]{3,}", t.lower()):
            if tok in wordset:
                pat_counts[tok] = pat_counts.get(tok, 0) + 1
    return spec_counts, pat_counts


def spec_num(rid):
    m = re.search(r"(\d+)", str(rid))
    return int(m.group(1)) if m else 0


def build_terms(old_stamps, next_t):
    """Build term entries. Stamps are permanent: records shipped before keep
    their stamps (looked up by (rt, rid)); brand-new terms continue numbering
    from next_t."""
    paths = spec_index_paths()
    log("spec indexes: %d" % len(paths))
    specs = list(spec_rows(paths))
    log("spec rows read: %d" % len(specs))
    pats = patent_rows()
    log("patent rows read: %d" % len(pats))
    seen = set()
    spec_terms = []
    spec_titles = []
    for rid, title, abstract, cpc in specs:
        if title:
            spec_titles.append(title)
        if not title or not rid or ("spec", rid) in seen:
            continue
        seen.add(("spec", rid))
        spec_terms.append({
            "w": title, "k": "t", "rt": "spec", "rid": rid,
            "key": title.lower(), "d": abstract[:500], "cpc": cpc,
        })
    spec_terms.sort(key=lambda e: spec_num(e["rid"]))
    pat_terms = []
    pat_titles = []
    for pub, title, cpc, assignee in pats:
        if title:
            pat_titles.append(title)
        if not title or not pub or ("pat", pub) in seen:
            continue
        seen.add(("pat", pub))
        dtext = ("Public patent " + pub + " \u2014 " + title +
                 ". Assignee: " + assignee + ". Class: " + cpc)[:600]
        pat_terms.append({
            "w": title, "k": "t", "rt": "pat", "rid": pub,
            "key": title.lower(), "d": dtext, "cpc": cpc,
        })
    pat_terms.sort(key=lambda e: str(e["rid"]))
    terms = spec_terms + pat_terms
    for e in terms:
        key = (e["rt"], e["rid"])
        if key in old_stamps:
            e["st"] = old_stamps[key]
        else:
            e["st"] = "JAH-DICT-T-%06d" % next_t
            next_t += 1
    log("term stamps reused: %d, newly assigned: %d" %
        (sum(1 for e in terms if (e["rt"], e["rid"]) in old_stamps),
         sum(1 for e in terms if (e["rt"], e["rid"]) not in old_stamps)))
    return terms, spec_titles, pat_titles, len(spec_terms), len(pat_terms)


def write_chunks(entries):
    os.makedirs(DATADIR, exist_ok=True)
    # clean stale chunk files from older (larger) runs
    for n in os.listdir(DATADIR):
        if n.startswith("dict-c") and n.endswith(".jsonl.gz"):
            os.remove(os.path.join(DATADIR, n))
    index = []
    n_chunks = 0
    for ci in range(0, len(entries), CHUNK_SIZE):
        chunk = entries[ci:ci + CHUNK_SIZE]
        n_chunks += 1
        cname = "dict-c%05d.jsonl.gz" % n_chunks
        with gzip.open(os.path.join(DATADIR, cname), "wt", encoding="utf-8") as f:
            for li, e in enumerate(chunk):
                if e["k"] == "w":
                    obj = {"w": e["w"], "k": "w", "st": e["st"], "d": e["d"],
                           "s": e.get("s", 0), "p": e.get("p", 0),
                           "pos": e.get("pos", ""), "defsrc": e.get("defsrc", "pending"),
                           "links": e.get("links", []),
                           "unsure": bool(e.get("unsure", False)),
                           "pron": e.get("pron", ""), "hist": e.get("hist", ""),
                           "histsrc": e.get("histsrc", "composed"),
                           "desc": e.get("desc", []), "ex": e.get("ex", []),
                           "rel": e.get("rel", []), "ant": e.get("ant", []),
                           "forms": e.get("forms", {})}
                else:
                    obj = {"w": e["w"], "k": "t", "st": e["st"], "rt": e["rt"],
                           "rid": e["rid"], "d": e["d"], "cpc": e.get("cpc", "")}
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                index.append([e["key"], cname, li])
    log("chunks written: %d" % n_chunks)
    return index, n_chunks


def write_index(index):
    os.makedirs(IDXDIR, exist_ok=True)
    ipath = os.path.join(IDXDIR, "dict.idx.json.gz")
    with gzip.open(ipath, "wt", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    log("index written: %s (%d rows)" % (ipath, len(index)))
    return ipath


def write_stamp_index(entries):
    """stamp.idx.json.gz: {"W":[idxPos,...],"T":[idxPos,...]} — element n-1 is the
    dict.idx row position of JAH-DICT-W/T-<n padded to 6>; -1 marks a gap.
    Lets the page resolve a typed or pasted stamp ID straight to its entry
    (ID-aware search). Regenerated on every rebuild so positions stay exact."""
    pat = re.compile(r"^JAH-DICT-([WT])-(\d+)$")
    buckets = {"W": {}, "T": {}}
    for pos, e in enumerate(entries):  # entries order == dict.idx row order
        m = pat.match(str(e.get("st", "")))
        if m:
            buckets[m.group(1)][int(m.group(2))] = pos
    out = {}
    for k in ("W", "T"):
        d = buckets[k]
        out[k] = [d.get(i, -1) for i in range(1, (max(d) if d else 0) + 1)]
    spath = os.path.join(IDXDIR, "stamp.idx.json.gz")
    with gzip.open(spath, "wt", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    log("stamp index written: %s (W=%d T=%d)" %
        (spath, len(out["W"]), len(out["T"])))


def write_rid_index(entries):
    """rid.idx.json.gz: sorted [[RID_UPPER, idxPos], ...] for catalog terms.

    Lets the page resolve a typed/pasted catalog record ID (JAH-SPEC-######,
    JAH-WORD-######, or a patent pub number like US10992705B2) straight to
    its entry. Lazy-fetched by the page only on record-ID-shaped queries, so
    it never slows the normal boot path. Regenerated on every rebuild so
    positions stay exact."""
    pairs = []
    for pos, e in enumerate(entries):  # entries order == dict.idx row order
        if e.get("k") == "t":
            rid = str(e.get("rid") or "").strip().upper()
            if rid:
                pairs.append([rid, pos])
    pairs.sort(key=lambda p: p[0])
    dedup, seen = [], set()
    for p in pairs:
        if p[0] not in seen:
            seen.add(p[0])
            dedup.append(p)
    rpath = os.path.join(IDXDIR, "rid.idx.json.gz")
    with gzip.open(rpath, "wt", encoding="utf-8") as f:
        json.dump(dedup, f, separators=(",", ":"))
    log("record-ID index written: %s (%d record IDs)" % (rpath, len(dedup)))


def refresh_api(stats):
    """Keep api.json counts honest: derive records_approx/records_as_of from
    the freshly built stats (never hardcoded)."""
    apath = os.path.join(ROOT, "api.json")
    try:
        with open(apath, encoding="utf-8") as f:
            api = json.load(f)
    except Exception as e:
        log("api.json refresh skipped: %s" % e)
        return
    api["records_approx"] = stats["total"]
    api["records_as_of"] = stats["last_updated"]
    # Site #3 fix-list (2026-10-03): machine-readable freshness + per-record
    # lookup recipe, all derived from the same dataset as the website.
    api["schema_version"] = stats.get("schema_version")
    api["catalog_revision"] = stats.get("catalog_revision")
    api["generated_at"] = stats.get("generated_at")
    api["defined"] = stats.get("defined")
    api["defined_authored"] = stats.get("defined_authored")
    api["defined_template"] = stats.get("defined_template")
    api["pending_definitions"] = stats.get("pending_definitions")
    if not any("stamp.idx" in str(ep.get("path", "")) for ep in api.get("endpoints", [])):
        api.setdefault("endpoints", []).append({
            "path": "data/index/stamp.idx.json.gz",
            "format": "gzipped json",
            "desc": "Permanent stamp-ID lookup: {\"W\":{\"JAH-DICT-W-######\":[idxPos...]},\"T\":{...}}. "
                    "Resolve a stamp to an index position, then read that row of dict.idx.json.gz "
                    "(word, chunk-file, line) and fetch the record line from data/dict/<chunk>.jsonl.gz. "
                    "That is the machine-readable per-record endpoint."})
    if not any("rid.idx" in str(ep.get("path", "")) for ep in api.get("endpoints", [])):
        api.setdefault("endpoints", []).append({
            "path": "data/index/rid.idx.json.gz",
            "format": "gzipped json",
            "desc": "Catalog record-ID lookup: sorted [[RID_UPPER, idxPos], ...] "
                    "for catalog terms (record IDs like JAH-SPEC-###### or patent "
                    "pub numbers). Lazy-fetched by the page only when a search "
                    "query looks like a record ID. Binary-search the ID, then "
                    "read that row of dict.idx.json.gz."})
    # the sitemap moved to sitemap-index.xml in polish pass 3 (robots.txt
    # agrees); keep the api.json pointer honest on every rebuild.
    api["sitemap"] = ("https://justinahiggins614-cmyk.github.io/jah-dictionary/"
                      "sitemap-index.xml")
    # keep the endpoint description honest about chunking
    n_chunks = sum(1 for n in os.listdir(DATADIR)
                   if n.startswith("dict-c") and n.endswith(".jsonl.gz"))
    for ep in api.get("endpoints", []):
        if isinstance(ep, dict) and "data/dict/" in str(ep.get("path", "")):
            ep["desc"] = re.sub(r"\(\d+ chunks",
                                "(%d chunks" % n_chunks, ep.get("desc", ""))
    if not any("?id=" in str(d.get("pattern", "")) for d in api.get("deep_links", [])):
        api.setdefault("deep_links", []).append({
            "pattern": "?id=<JAH-DICT-W-######|JAH-DICT-T-######>",
            "desc": "Open an entry directly by its permanent stamp ID."})
    if not any("record ID" in str(d.get("desc", "")) for d in api.get("deep_links", [])):
        api.setdefault("deep_links", []).append({
            "pattern": "?q=<record ID>",
            "desc": "Search by catalog record ID (JAH-SPEC-######, JAH-WORD-######, "
                    "or a patent publication number) — resolves to the term entry."})
    with open(apath, "w", encoding="utf-8") as f:
        json.dump(api, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log("api.json refreshed: records_approx=%d as_of=%s" %
        (stats["total"], stats["last_updated"]))


def write_stats(n_words, n_terms):
    spath = os.path.join(IDXDIR, "stats.json")
    # Authoritative dictionary metadata: every visible count on the page
    # reads from this single object (audit 2026-09-30). data_hash is the
    # sha256 of the shipped index file, so any consumer can verify the
    # exact dataset the counts describe.
    ipath = os.path.join(IDXDIR, "dict.idx.json.gz")
    data_hash = ""
    if os.path.exists(ipath):
        import hashlib
        h = hashlib.sha256()
        with open(ipath, "rb") as f:
            for blk in iter(lambda: f.read(1 << 20), b""):
                h.update(blk)
        data_hash = "sha256:" + h.hexdigest()
    # Site #3 fix-list (2026-10-03): defined/authored/template/pending from
    # the definitions coverage file, so "defined" vs "listed" are two
    # distinct machine-readable statuses, never conflated.
    try:
        cov = json.load(open(os.path.join(ROOT, "data", "definitions",
                                          "coverage.json"), encoding="utf-8"))
    except Exception as e:
        log("coverage.json unreadable (%s); definition counts zeroed" % e)
        cov = {"defined": 0, "authored": 0, "templates": 0, "pending": 0}
    # catalog revision: monotonically increasing build counter.
    prev_rev = 0
    if os.path.exists(spath):
        try:
            prev_rev = int(json.load(open(spath, encoding="utf-8"))
                           .get("catalog_revision", 0))
        except Exception:
            prev_rev = 0
    import datetime as _dt
    stats = {
        "dictionary_version": "1.0",
        "schema_version": "1.1",
        "entry_count": n_words + n_terms,
        "words": n_words,
        "terms": n_terms,
        "total": n_words + n_terms,
        "defined": int(cov.get("defined", 0)),
        "defined_authored": int(cov.get("authored", 0)),
        "defined_template": int(cov.get("templates", 0)),
        "pending_definitions": int(cov.get("pending", 0)),
        "last_updated": datetime.date.today().isoformat(),
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "catalog_revision": prev_rev + 1,
        "data_hash": data_hash,
        "source": "The Signature Dictionary (original definitions)",
    }
    with open(spath, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    log("stats: %s" % json.dumps(stats, ensure_ascii=False))
    return stats


def verify(index, ipath):
    log("--- verification ---")
    # 1. index sorted
    keys = [r[0] for r in index]
    assert all(keys[i] <= keys[i + 1] for i in range(len(keys) - 1)), "index not sorted"
    log("index sorted: OK (%d rows)" % len(index))
    # 2. chunk line counts match
    total_lines = 0
    with gzip.open(ipath, "rt", encoding="utf-8") as f:
        idx2 = json.load(f)
    assert len(idx2) == len(index), "index row count mismatch"
    chunk_files = sorted(set(r[1] for r in index))
    for cname in chunk_files:
        with gzip.open(os.path.join(DATADIR, cname), "rt", encoding="utf-8") as f:
            total_lines += sum(1 for _ in f)
    assert total_lines == len(index), "chunk lines %d != index rows %d" % (total_lines, len(index))
    log("chunk lines == index rows: OK (%d)" % total_lines)

    def resolve(key, want_k=None, want_rt=None):
        i = bisect.bisect_left(keys, key)
        while i < len(keys) and keys[i] == key:
            cname, lineno = index[i][1], index[i][2]
            with gzip.open(os.path.join(DATADIR, cname), "rt", encoding="utf-8") as f:
                for ln, line in enumerate(f):
                    if ln == lineno:
                        e = json.loads(line)
                        if (want_k is None or e.get("k") == want_k) and \
                           (want_rt is None or e.get("rt") == want_rt):
                            return e
                        break
            i += 1
        return None

    # 3. spot-check "rug"
    rug = resolve("rug", want_k="w")
    assert rug is not None, "'rug' word entry not found"
    assert rug.get("defsrc") == "iwb", "'rug' should carry an authored IWB definition"
    assert len(rug["d"]) >= 1, "'rug' has no IWB senses"
    log("'rug' resolves: OK (st=%s, senses=%d, s=%d, p=%d)" %
        (rug["st"], len(rug["d"]), rug.get("s", 0), rug.get("p", 0)))
    # 3b. schema v1.1 enrichment present on the word entry
    for f in ("pron", "hist", "histsrc", "desc", "ex", "rel", "ant", "forms"):
        assert f in rug, "enriched field missing: %s" % f
    assert rug["pron"], "'rug' has no pronunciation"
    assert rug["desc"], "'rug' has no worded description"
    assert rug["forms"].get("plural"), "'rug' has no plural form"
    log("schema v1.1 enrichment: OK (pron=%s, senses=%d, examples=%d)" %
        (rug["pron"], len(rug["desc"]), len(rug["ex"])))
    # 4. spot-check one spec term and one patent term
    spec_e = None
    for r in index:
        e_cname, e_line = r[1], r[2]
        with gzip.open(os.path.join(DATADIR, e_cname), "rt", encoding="utf-8") as f:
            for ln, line in enumerate(f):
                if ln == e_line:
                    e = json.loads(line)
                    if e.get("k") == "t" and e.get("rt") == "spec":
                        spec_e = e
                    break
        if spec_e:
            break
    assert spec_e is not None, "no spec term found"
    log("spec term resolves: OK (%s | %s)" % (spec_e["rid"], spec_e["w"][:60]))
    pat_e = None
    for r in index:
        e_cname, e_line = r[1], r[2]
        with gzip.open(os.path.join(DATADIR, e_cname), "rt", encoding="utf-8") as f:
            for ln, line in enumerate(f):
                if ln == e_line:
                    e = json.loads(line)
                    if e.get("k") == "t" and e.get("rt") == "pat":
                        pat_e = e
                    break
        if pat_e:
            break
    assert pat_e is not None, "no patent term found"
    log("patent term resolves: OK (%s | %s)" % (pat_e["rid"], pat_e["w"][:60]))
    log("ALL VERIFICATIONS PASSED")


def main():
    assert os.path.exists(DICT_JSON), "missing input: %s" % DICT_JSON
    words = parse_words()
    write_words_cache(words)
    # schema v1.1: enrich every headword with the full dictionary apparatus
    # (pronunciation, history, description, examples, relations, forms).
    # Deterministic and pure: safe to re-run on every rebuild, including the
    # 2h iwb-definitions-drip (new words are enriched automatically).
    log("enriching %d headwords..." % len(words))
    wordset = set(e["key"] for e in words)
    fams = build_families([e["key"] for e in words], wordset)
    for e in words:
        enrich_entry(e, wordset, fams)
    log("enrichment complete")
    old_stamps, max_t = load_old_term_stamps()
    log("old term stamps loaded: %d (max T-number %d)" % (len(old_stamps), max_t))
    terms, spec_titles, pat_titles, n_spec_terms, n_pat_terms = build_terms(old_stamps, max_t + 1)
    wordset = set(e["key"] for e in words)
    spec_counts, pat_counts = build_counts(wordset, spec_titles, pat_titles)
    for e in words:
        e["s"] = spec_counts.get(e["key"], 0)
        e["p"] = pat_counts.get(e["key"], 0)
    log("usage counts: words hit by spec titles=%d, by patent titles=%d" %
        (sum(1 for v in spec_counts.values() if v), sum(1 for v in pat_counts.values() if v)))
    entries = words + terms
    # Word ("w") before term ("t") on collision: the English word wins the
    # primary slot and shadowed catalog terms stay reachable by stamp ID.
    # (NB: "t" < "w" in ASCII, so sort explicitly on kind rank.)
    entries.sort(key=lambda e: (e["key"], 0 if e["k"] == "w" else 1))
    index, n_chunks = write_chunks(entries)
    ipath = write_index(index)
    write_stamp_index(entries)
    write_rid_index(entries)
    stats = write_stats(len(words), len(terms))
    refresh_api(stats)
    # Site #3 fix-list (2026-10-03): consistency gate — the build FAILS if
    # the published stats disagree with the actual shipped index/chunks.
    # Never let a stale or hand-typed number reach the page.
    assert stats["total"] == len(index), \
        "COUNT MISMATCH: stats.total=%d but index rows=%d" % (stats["total"], len(index))
    assert stats["words"] + stats["terms"] == stats["total"], \
        "COUNT MISMATCH: words+terms != total"
    log("consistency gate: stats.total == index rows == %d" % stats["total"])
    # Re-stamp the no-JS static snapshot in index.html from the fresh stats
    # so crawlers never see a stale hand-typed count. Fail-safe: a stamp
    # failure is logged loudly, never blocks the data build.
    try:
        sys.path.insert(0, os.path.join(ROOT, "code", "dict"))
        import stamp_static
        stamp_static.main()
    except Exception as ex:  # noqa: BLE001
        log("STAMP_STATIC: FAILED (%r) — will retry next run" % ex)
    verify(index, ipath)
    # Site #3 diagnostic (2026-10-02): rebuild the per-letter lexical JSON
    # shards + A-Z word archive pages + lexical sitemap on every build so
    # the 2h iwb-definitions-drip keeps them fresh automatically. Fail-safe:
    # the dictionary data above is the primary artifact; a shard failure is
    # logged loudly and retried on the next run, never blocks the build.
    try:
        sys.path.insert(0, os.path.join(ROOT, "code"))
        import build_lexical_shards
        build_lexical_shards.build()
    except Exception as ex:  # noqa: BLE001
        log("LEXICAL SHARDS: FAILED (%r) — will retry next run" % ex)
    # Sitemap refresh (2026-10-04): ?w= deep links (sitemap-words-*.xml) +
    # archive/browse pages (sitemap-pages.xml) + sitemap-index.xml, rebuilt
    # from the fresh lexical shards on every run — AFTER the shard flush —
    # so sitemap URLs never go one-run-behind. Fail-safe: logged loudly,
    # never blocks the build.
    try:
        sys.path.insert(0, os.path.join(ROOT, "code", "qa"))
        import build_sitemaps
        build_sitemaps.main()
    except Exception as ex:  # noqa: BLE001
        log("SITEMAPS: FAILED (%r) — will retry next run" % ex)
    # Archive count re-stamp (2026-10-04, stamp_static pattern): refresh the
    # A-Z archive count headers AFTER the new index + shards flush — never
    # one-run-behind. Fail-safe: logged loudly, never blocks the build.
    try:
        import stamp_static
        stamp_static.stamp_archive()
    except Exception as ex:  # noqa: BLE001
        log("STAMP_ARCHIVE: FAILED (%r) — will retry next run" % ex)
    # data size
    total = 0
    for dp, _, fns in os.walk(os.path.join(ROOT, "data")):
        for n in fns:
            total += os.path.getsize(os.path.join(dp, n))
    log("RESULT: words=%d spec_terms=%d patent_terms=%d chunks=%d total_entries=%d data_size=%.1fMB" %
        (len(words), n_spec_terms, n_pat_terms, n_chunks, len(entries), total / 1048576.0))


if __name__ == "__main__":
    main()
