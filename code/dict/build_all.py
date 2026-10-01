#!/usr/bin/env python3
"""Build JAH Dictionary data (Project 5).

Words: headword list with original IWB Dictionary definitions (data/definitions/all.jsonl);
  code/dict/build/dictionary.json  ->  build cache code/dict/build/words.jsonl
Terms: one dictionary entry per spec (signature-one-archive + shard-2 indexes)
  and per public patent (cyber-patent-catalog index).

Outputs:
  data/dict/dict-cNNNNN.jsonl.gz   (1000 entries per chunk, sorted by key)
  data/index/dict.idx.json.gz      ([[key, chunkFile, lineNo], ...] sorted)
  data/index/stats.json

Idempotent: re-runnable; the daily cron re-runs it. Stamp numbers are stable
because words are stamped alphabetically (static set) and terms are stamped
by (spec numeric id, then patent rid) order.
"""
import bisect
import datetime
import gzip
import json
import os
import re

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
BUILD = os.path.join(ROOT, "code", "dict", "build")
DICT_JSON = os.path.join(BUILD, "dictionary.json")
WORDS_CACHE = os.path.join(BUILD, "words.jsonl")
DATADIR = os.path.join(ROOT, "data", "dict")
IDXDIR = os.path.join(ROOT, "data", "index")
SPEC_IDXS = [
    os.path.expanduser("~/workspace/signature-one-archive/data/index/specs.idx.json.gz"),
    os.path.expanduser("~/workspace/signature-one-archive-shard-2/data/index/specs.idx.json.gz"),
]
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
                                   "links": r.get("links") or []}
    return defs

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
                      "defsrc": rec.get("src", "") or "pending"})
    words.sort(key=lambda e: e["key"])
    for i, e in enumerate(words, 1):
        e["st"] = "JAH-DICT-W-%06d" % i
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


def spec_rows():
    """Stream (spec_id, title, abstract, cpc) from both spec indexes."""
    for path in SPEC_IDXS:
        if not os.path.exists(path):
            log("WARN: missing spec index %s" % path)
            continue
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


def build_terms():
    specs = list(spec_rows())
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
    for i, e in enumerate(terms, 1):
        e["st"] = "JAH-DICT-T-%06d" % i
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
                           "links": e.get("links", [])}
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
    stats = {
        "dictionary_version": "1.0",
        "schema_version": "1.0",
        "entry_count": n_words + n_terms,
        "words": n_words,
        "terms": n_terms,
        "total": n_words + n_terms,
        "last_updated": datetime.date.today().isoformat(),
        "data_hash": data_hash,
        "source": "IWB Dictionary (original definitions)",
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
    terms, spec_titles, pat_titles, n_spec_terms, n_pat_terms = build_terms()
    wordset = set(e["key"] for e in words)
    spec_counts, pat_counts = build_counts(wordset, spec_titles, pat_titles)
    for e in words:
        e["s"] = spec_counts.get(e["key"], 0)
        e["p"] = pat_counts.get(e["key"], 0)
    log("usage counts: words hit by spec titles=%d, by patent titles=%d" %
        (sum(1 for v in spec_counts.values() if v), sum(1 for v in pat_counts.values() if v)))
    entries = words + terms
    entries.sort(key=lambda e: (e["key"], e["k"]))  # word ("w") before term ("t") on collision
    index, n_chunks = write_chunks(entries)
    ipath = write_index(index)
    write_stats(len(words), len(terms))
    verify(index, ipath)
    # data size
    total = 0
    for dp, _, fns in os.walk(os.path.join(ROOT, "data")):
        for n in fns:
            total += os.path.getsize(os.path.join(dp, n))
    log("RESULT: words=%d spec_terms=%d patent_terms=%d chunks=%d total_entries=%d data_size=%.1fMB" %
        (len(words), n_spec_terms, n_pat_terms, n_chunks, len(entries), total / 1048576.0))


if __name__ == "__main__":
    main()
