#!/usr/bin/env python3
"""TIER 2-8 checker: link audit for the dictionary site.
1. Extracts every http(s) URL from index.html + api.json (+ JS-built URLs for
   the 9 network sites, wiki, leaks, spec catalog, patent catalog).
2. Fetches each (GET, short timeout); reports HTTP status. 200/301/302/308 are
   fine for Pages sites (the SPA returns 200 for deep links). Anything else,
   a timeout, or a DNS failure is flagged.
3. Statically verifies the in-page interactive wiring exists: search box,
   A-Z browse, random word, read-aloud, copy/download buttons, word program,
   word patent, AI teacher, ?w= / ?dict= / ?id= routes, wiki cross-links.
No dead buttons: any missing handler is a FAIL.
"""
import concurrent.futures
import json
import os
import re
import subprocess
import sys

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
HTML = os.path.join(ROOT, "index.html")
failures = []
warnings = []


def fail(msg):
    failures.append(msg)
    print("FAIL: " + msg)


def warn(msg):
    warnings.append(msg)
    print("warn: " + msg)


def ok(msg):
    print("ok: " + msg)


def collect_urls():
    html = open(HTML, encoding="utf-8").read()
    urls = set(re.findall(r'https?://[^\s"\'<>\\]+', html))
    api = json.load(open(os.path.join(ROOT, "api.json"), encoding="utf-8"))
    def walk(o):
        if isinstance(o, str) and o.startswith("http"):
            urls.add(o.rstrip("/"))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(api)
    # canonical destinations that must resolve (may also appear in JS strings)
    for u in [
        "https://justinahiggins614-cmyk.github.io/jah-ai-models/",
        "https://justinahiggins614-cmyk.github.io/jah-calculator/",
        "https://justinahiggins614-cmyk.github.io/jah-dictionary/",
        "https://justinahiggins614-cmyk.github.io/jah-wiki/",
        "https://justinahiggins614-cmyk.github.io/jah-n-wiki-leaks/",
        "https://justinahiggins614-cmyk.github.io/cyber-patent-catalog/",
        "https://justinahiggins614-cmyk.github.io/signature-one-archive/specs.html",
        "https://justinahiggins614-cmyk.github.io/signature-llama/",
        "https://justinahiggins614-cmyk.github.io/jah-computer-systems/",
        "https://justinahiggins614-cmyk.github.io/jah-wiki/?dict=rug",
        "https://justinahiggins614-cmyk.github.io/signature-one-archive/specs.html?word=rug",
        "https://justinahiggins614-cmyk.github.io/jah-n-wiki-leaks/?dossier=JAH-SPEC-000001",
        "https://justinahiggins614-cmyk.github.io/jah-dictionary/?w=rug",
        "https://justinahiggins614-cmyk.github.io/jah-dictionary/?dict=rug",
    ]:
        urls.add(u)
    # drop TTS/code endpoints that intentionally fail plain GET probes,
    # and the raw_github_base prefix (a documented URL prefix, not a link)
    urls = {u for u in urls
            if "translate.google" not in u and "responsivevoice" not in u
            and "w3.org" not in u
            and not u.rstrip("/").endswith("jah-dictionary/master")}
    return sorted(urls)


def probe(url):
    """Probe one URL with curl (the sandbox egress proxy is reliable for curl;
    python's urllib hangs on some hosts here). Returns (url, status, err)."""
    try:
        p = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", "25", "-A", "JAH-dict-qa/1.0", url],
            capture_output=True, text=True, timeout=40)
        code = p.stdout.strip()[-3:]
        if code.isdigit() and int(code):
            return url, int(code), None
        # retry once before calling it dead
        p = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", "40", "-A", "JAH-dict-qa/1.0", url],
            capture_output=True, text=True, timeout=60)
        code = p.stdout.strip()[-3:]
        if code.isdigit() and int(code):
            return url, int(code), None
        return url, None, "curl gave %r, stderr %s" % (code, p.stderr[:80])
    except Exception as e:
        return url, None, "%s: %s" % (type(e).__name__, str(e)[:100])


def check_live_links():
    urls = collect_urls()
    print("probing %d URLs..." % len(urls))
    bad = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for url, status, err in ex.map(probe, urls):
            if status in (200, 301, 302, 303, 307, 308):
                ok("%s -> %s" % (url, status))
            else:
                bad += 1
                fail("dead/odd link %s (status=%s err=%s)" % (url, status, err))
    return bad


def check_wiring():
    html = open(HTML, encoding="utf-8").read()
    required = [
        # search
        ("search input", 'id="q"'),
        ("search button", 'id="qgo"'),
        ("search suggestions", 'id="sugg"'),
        # A-Z browse
        ("A-Z links (?az=)", '?az='),
        ("browse view fn", "function vBrowse"),
        # random
        ("random word link", 'id="randlink"'),
        ("random word fn", "function randWord"),
        # read aloud
        ("read-aloud toolbar", "function rdToolbar"),
        ("read aloud toggle", "function rdToggle"),
        ("hear word", "function sayWord"),
        # copy / download (labeled)
        ("copy entry button", "Copy entry"),
        ("download .txt", "dlEntryTxt"),
        ("download JSON", "dlEntryJson"),
        ("download CSV", "dlEntryCsv"),
        ("copy program", "Copy program"),
        ("download .py", "Download .py"),
        # word program
        ("word program fn", "function wordProgram"),
        ("run demo", "runWordDemo"),
        # word patent
        ("word patent fn", "function wordPatent"),
        ("word patent target", "specs.html?word="),
        # AI teacher
        ("teacher wiring", "function wireTeacher"),
        ("teacher replies", "function teacherReply"),
        ("teacher role label", "teaching assistant (guide)"),
        ("teacher chat log", 'id="chatlog"'),
        ("teacher input", 'id="chatin"'),
        # routes
        ("?w= route", 'qp("w")'),
        ("?dict= route", 'qp("dict")'),
        ("?id= route", 'qp("id")'),
        ("?q= route", 'qp("q")'),
        # cross-refs
        ("wiki search link", '/?q='),
        ("wiki dict link", '/?dict='),
        ("wiki article link", '/?page='),
        ("leaks dossier link", '/?dossier='),
        ("spec catalog const", 'signature-one-archive/specs.html'),
        ("patent catalog const", 'cyber-patent-catalog'),
        # JAH network bar: canonical order
        ("network bar", 'class="jahnet"'),
        # entry provenance
        ("provenance label", "Definition provenance"),
        # last-updated line
        ("last updated line", "Last updated"),
        # YOU ARE HERE marker
        ("you-are-here marker", "YOU ARE HERE"),
        # a11y
        ("focus-visible style", "focus-visible"),
        ("speed select label", 'aria-label="Reading speed"'),
    ]
    for name, needle in required:
        if needle in html:
            ok("wiring present: " + name)
        else:
            fail("wiring MISSING: " + name + " (needle %r)" % needle)


def main():
    print("== live link probes ==")
    check_live_links()
    print("\n== in-page wiring ==")
    check_wiring()
    print("\n%d failures, %d warnings" % (len(failures), len(warnings)))
    if failures:
        print("LINK CHECK FAILED")
        return 1
    print("LINK CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
