#!/usr/bin/env python3
"""Lexical shard + A-Z word archive builder (Site #3).

Re-runnable. Called by the 2h iwb-definitions-drip via code/dict/build_all.py
main() (after verify), and directly:  python3 code/build_lexical_shards.py

Outputs (all derived from data, never hardcoded):
  data/lexical/shard-<L>.json   one compact JSON array per first letter
      (L = a..z, or "0" for non-alphabetic headwords).
      Each row: [word, pos, pronunciation, first_sense, stamp].
      For machine crawlers / RAG ingest: the whole headword lexicon split
      into ~27 small files instead of one monolith.
  data/lexical/loc-<L>.json     per-letter word-location map for the archive's
      lazy full-entry preview: {word: [chunk_file, line_no]}. The archive page
      fetches this small map, then only the one gz dict chunk holding the
      tapped word — the archive never loads all chunks at once.
  data/lexical/shards.json      manifest: {letter: {file, count}} + totals.
  az/<L>.html                   the A-Z word archive: the full headword
      catalog as collapsible <details> lists grouped by first two letters
      (phone-friendly), every entry showing its phonetic construction, part
      of speech, deterministic stamp and a ?w= deep link; a filter-as-you-type
      search box; a count header stamped from the dataset; and a lazy
      full-entry preview that loads the word's gz dict chunk on demand.
      Readable by non-JS bots and humans with JavaScript disabled.
  sitemap-lexical.xml           dedicated lexical sitemap (urlset) listing
      every machine shard JSON; registered in sitemap-index.xml (idempotent).
      The human-readable az/<L>.html archive pages live in
      sitemap-pages.xml (built by code/qa/build_sitemaps.py).

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
from urllib.parse import quote

ROOT = os.path.expanduser("~/workspace/jah-dictionary")
DATADIR = os.path.join(ROOT, "data", "dict")
LEXDIR = os.path.join(ROOT, "data", "lexical")
AZDIR = os.path.join(ROOT, "az")
STATSPATH = os.path.join(ROOT, "data", "index", "stats.json")
BASE = "https://justinahiggins614-cmyk.github.io/jah-dictionary/"
TODAY = None


def log(msg):
    print(msg, flush=True)


def fmt(n):
    return "{:,}".format(int(n))


def letter_of(word):
    c = (word[:1] or "").lower()
    return c if "a" <= c <= "z" else "0"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def w_url(word):
    # mirror JS encodeURIComponent() used by linkW() in index.html
    return "../?w=" + quote(word, safe="-_.!~*'()")


def collect():
    """Scan chunks in order.

    Return (shards, locs, n):
      shards {letter: [(word,pos,pron,sense,stamp), ...]}
      locs   {letter: {word: [chunk_file, line_no]}}
    First occurrence wins (stable stamps).
    """
    shards, locs = {}, {}
    files = sorted(f for f in os.listdir(DATADIR)
                   if f.startswith("dict-c") and f.endswith(".jsonl.gz"))
    n = 0
    for fn in files:
        with gzip.open(os.path.join(DATADIR, fn), "rt", encoding="utf-8") as f:
            for lineno, line in enumerate(f):
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
                L = letter_of(w)
                if w not in locs.setdefault(L, {}):
                    locs[L][w] = [fn, lineno]
                    shards.setdefault(L, []).append(row)
                    n += 1
    return shards, locs, n


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


def write_loc_maps(locs):
    os.makedirs(LEXDIR, exist_ok=True)
    for L in sorted(locs):
        path = os.path.join(LEXDIR, "loc-%s.json" % L)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(locs[L], f, ensure_ascii=False, separators=(",", ":"))
    return len(locs)


def az_count_html(L, n, total_w):
    """The stamped count header block (also re-stamped by stamp_static)."""
    if L == "0":
        scope = "<b>%s</b> headwords (symbols, affixes and numbers)" % fmt(n)
    else:
        scope = "<b>%s</b> headwords beginning with <b>%s</b>" % (fmt(n),
                                                                  esc(L.upper()))
    return ('<p class="azcount" data-azcount="%s">%s &mdash; of <b>%s</b> '
            'total headwords in The Signature Dictionary. '
            'Counts generated from the dataset, never hand-typed.</p>'
            % (esc(L), scope, fmt(total_w)))


def az_search_html(n, total_e):
    return ('<p class="azsearch" role="search">'
            '<label for="azq">Filter the %s words on this page:</label><br>'
            '<input type="search" id="azq" autocomplete="off" '
            'placeholder="start typing a word&#8230;">'
            '<span class="azhit" id="azhit" aria-live="polite"></span></p>'
            '<p class="azall">Every entry below shows its phonetic construction. '
            'Tap any word for its full page &mdash; stamp, word program, '
            'read-aloud and the AI teacher. '
            '<a href="../">Search all <b class="alln">%s</b> entries on the '
            'main dictionary page &rarr;</a></p>'
            % (fmt(n), fmt(total_e)))


def entry_row(w, pos, pron, sense, st):
    h = ['<dt data-w="%s"><a href="%s">%s</a>'
         % (esc(w), esc(w_url(w)), esc(w))]
    if pron:
        h.append(' <span class="pron" title="IWB phonetic respelling '
                 '&mdash; approximate pronunciation">%s</span>' % esc(pron))
    if pos:
        h.append(' <span class="pos">%s</span>' % esc(pos))
    if st:
        h.append(' <span class="stamp">%s</span>' % esc(st))
    h.append('</dt>')
    dd = '<dd>'
    if sense:
        dd += esc(sense[:300])
    dd += (' <button type="button" class="azprev" data-w="%s">'
           'full entry &#9656;</button>'
           '<div class="azfull" data-open="0" data-loaded="0" '
           'style="display:none"></div></dd>' % esc(w))
    h.append(dd)
    return "".join(h)


def groups_html(rows):
    groups, order = {}, []
    for r in rows:
        w = r[0]
        pfx = w[:2].lower() if len(w) >= 2 else w.lower()
        if pfx not in groups:
            groups[pfx] = []
            order.append(pfx)
        groups[pfx].append(r)
    parts = []
    for pfx in order:
        grows = groups[pfx]
        label = "%d words" % len(grows) if len(grows) != 1 else "1 word"
        parts.append('<details class="azgrp"><summary>%s '
                     '<span class="n">&middot; %s</span></summary><dl>'
                     % (esc(pfx), label))
        parts.extend(entry_row(*r) for r in grows)
        parts.append("</dl></details>")
    return "\n".join(parts)


AZ_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>@@TITLE@@</title>
<meta name="description" content="@@DESC@@">
<link rel="canonical" href="@@CANON@@">
<style>
body{margin:0;font-family:Georgia,'Times New Roman',serif;background:#faf6ec;color:#2b2118;line-height:1.6}
.wrap{max-width:900px;margin:0 auto;padding:18px 16px 60px}
h1{color:#1a4d2e;font-family:Arial,sans-serif}
.nav{font-family:Arial,sans-serif;margin:10px 0}
.nav a{margin-right:8px}
a{color:#1a4d2e}
.azcount{font-family:Arial,sans-serif;background:#fff;border:1px solid #e4dcc4;border-radius:6px;padding:10px 12px}
.azsearch{font-family:Arial,sans-serif;margin:14px 0 4px}
.azsearch input{font-size:1em;padding:9px 10px;width:min(94%,360px);border:1px solid #cbbf9a;border-radius:6px;margin-top:6px}
.azhit{font-size:.9em;color:#6b5f3e;margin-left:8px}
.azall{font-family:Arial,sans-serif;font-size:.92em}
details.azgrp{border-bottom:1px solid #e4dcc4}
details.azgrp summary{cursor:pointer;font-family:Arial,sans-serif;font-weight:bold;padding:12px 6px;font-size:1.1em;color:#1a4d2e;min-height:44px}
details.azgrp summary .n{font-weight:normal;color:#6b5f3e;font-size:.82em}
dt{font-family:Arial,sans-serif;font-weight:bold;margin-top:10px}
dt .pos{font-style:italic;font-weight:normal;color:#6b5f3e}
dt .pron{font-style:italic;font-weight:normal;color:#6b5f3e}
dt .stamp{font-size:.75em;font-weight:normal;color:#8a7a4d}
dd{margin:2px 0 8px 0;font-size:.95em}
.azprev{font-family:Arial,sans-serif;font-size:.8em;margin-left:8px;padding:5px 12px;border:1px solid #cbbf9a;background:#fff;border-radius:20px;color:#1a4d2e;cursor:pointer;min-height:32px}
.azfull{background:#fffdf6;border:1px solid #e4dcc4;border-radius:6px;padding:4px 12px;margin:8px 0 12px 0;font-family:Arial,sans-serif}
.azfull ol{margin:8px 0;padding-left:22px}
.azload{font-style:italic;color:#6b5f3e}
.bestofbest{font-family:Arial,sans-serif;background:#fffdf6;border:2px solid #c9a227;border-radius:10px;padding:16px 18px;margin:18px 0}
.bestofbest h2{margin:0 0 4px;color:#1a4d2e}
.bestofbest .whybest{background:#fdf6e3;border-left:3px solid #c9a227;padding:8px 12px;border-radius:0 8px 8px 0;margin:10px 0;font-size:.92em}
.bestofbest .beststats{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.bestofbest .beststat{background:#faf6ec;border:1px solid #e4dcc4;border-radius:8px;padding:6px 12px;font-size:.85em}
.bestofbest .beststat b{color:#1a4d2e}
.bestofbest .toolbar{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.bestofbest .btn{font-family:Arial,sans-serif;padding:8px 14px;border:1px solid #cbbf9a;background:#1a4d2e;color:#fff;border-radius:20px;cursor:pointer;font-size:.9em;text-decoration:none;display:inline-block}
.bestofbest .btn:hover{background:#2a6b40}
.bestofbest dt{font-size:1.15em}
.bestflow{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:12px 0;justify-content:center;font-size:.82em}
.bestflow .bnode{background:#faf6ec;border:1px solid #c9a227;border-radius:8px;padding:8px 12px;text-align:center;max-width:150px}
.bestflow .bnode b{display:block;color:#1a4d2e;margin-bottom:2px}
.bestflow .barrow{color:#c9a227;font-size:18px;font-weight:700}
</style>
</head>
<body><div class="wrap">
<p class="nav"><a href="../">The Signature Dictionary</a> &rsaquo; A&ndash;Z word archive</p>
<h1>@@HEADING@@</h1>
<p class="nav">@@LETTERLINKS@@</p>
@@COUNT@@
@@SEARCH@@
@@BEST@@
@@GROUPS@@
<p class="nav">@@LETTERLINKS@@</p>
<p style="font-family:Arial;font-size:.85em;color:#6b5f3e">Archive page generated from The Signature Dictionary data for crawlers and no-JavaScript readers. Full entries (stamps, word programs, read-aloud, AI teachers) live at each word's page.</p>
</div>
<script>
@@SCRIPT@@
</script>
</body>
</html>
"""

AZ_SCRIPT = """(function(){
"use strict";
var LETTER="@@LETTER@@";
var q=document.getElementById("azq"),hit=document.getElementById("azhit");
function lw(s){return (s||"").toLowerCase();}
/* filter-as-you-type: show matching entries, auto-expand their groups */
q.addEventListener("input",function(){
  var t=lw(q.value).replace(/^\\s+|\\s+$/g,""),n=0,i,j;
  var groups=document.querySelectorAll("details.azgrp");
  for(i=0;i<groups.length;i++){
    var g=groups[i],dts=g.getElementsByTagName("dt"),vis=0;
    for(j=0;j<dts.length;j++){
      var dt=dts[j],dd=dt.nextElementSibling;
      var show=!t||lw(dt.getAttribute("data-w")||"").indexOf(t)!==-1;
      dt.style.display=show?"":"none";
      if(dd&&dd.tagName==="DD")dd.style.display=show?"":"none";
      if(show){vis++;n++;}
    }
    g.style.display=vis?"":"none";
    g.open=!!t&&vis>0;
  }
  hit.textContent=t?(n+" match"+(n===1?"":"es")):"";
});
/* Lazy full-entry preview: fetch the tiny per-letter location map, then only
   the one gz dict chunk holding the tapped word. Never loads all chunks. */
var locMap=null,locTried=false,chunkCache={};
function escH(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function failHtml(w){return '<p class="azload">Could not load the preview &mdash; <a href="../?w='+encodeURIComponent(w)+'">open the full entry &rarr;</a></p>';}
function fetchText(url){return fetch(url).then(function(r){if(!r.ok)throw new Error("http "+r.status);return r.text();});}
function fetchGz(url){return fetch(url).then(function(r){
  if(!r.ok)throw new Error("http "+r.status);
  if(typeof DecompressionStream==="undefined")throw new Error("no gzip support");
  return new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).text();
});}
function getLoc(cb){
  if(locMap){cb(locMap);return;}
  if(locTried){cb(null);return;}
  locTried=true;
  fetchText("../data/lexical/loc-"+LETTER+".json").then(function(t){
    try{locMap=JSON.parse(t);}catch(e){locMap=null;}
    cb(locMap);
  }).catch(function(){cb(null);});
}
function entryInner(e){
  var h='<p style="margin:.2em 0"><b>'+escH(e.w)+'</b>';
  if(e.pron)h+=' <span class="pron">'+escH(e.pron)+'</span>';
  if(e.pos)h+=' <span class="pos">'+escH(e.pos)+'</span>';
  if(e.st)h+=' <span class="stamp">'+escH(e.st)+'</span>';
  h+='</p>';
  var d=e.d||[],i;
  if(d.length){h+="<ol>";for(i=0;i<d.length;i++)h+="<li>"+escH(String(d[i]).replace(/^\\d+\\.\\s*/,""))+"</li>";h+="</ol>";}
  h+='<p style="margin:.4em 0"><a href="../?w='+encodeURIComponent(e.w)+'">Open the full entry &rarr;</a></p>';
  return h;
}
document.addEventListener("click",function(ev){
  var b=ev.target;
  if(!b||!b.classList||!b.classList.contains("azprev"))return;
  var w=b.getAttribute("data-w")||"";
  var box=b.parentNode.querySelector(".azfull");
  if(!box)return;
  if(box.getAttribute("data-open")==="1"){box.style.display="none";box.setAttribute("data-open","0");b.textContent="full entry \\u25B8";return;}
  if(box.getAttribute("data-loaded")==="1"){box.style.display="block";box.setAttribute("data-open","1");b.textContent="hide \\u25B2";return;}
  b.textContent="loading\\u2026";
  getLoc(function(L){
    var show=function(html){
      box.innerHTML=html;box.style.display="block";
      box.setAttribute("data-open","1");box.setAttribute("data-loaded","1");
      b.textContent="hide \\u25B2";
    };
    if(!L||!L[w]){show(failHtml(w));return;}
    var cf=L[w][0],ln=L[w][1];
    var use=function(txt){
      var e=null;try{e=JSON.parse(txt.split("\\n")[ln]);}catch(x){}
      show((!e||e.w!==w)?failHtml(w):entryInner(e));
    };
    if(chunkCache[cf]){use(chunkCache[cf]);return;}
    fetchGz("../data/dict/"+cf).then(function(t){chunkCache[cf]=t;use(t);})
      .catch(function(){show(failHtml(w));});
  });
});
})();
"""


BEST_HTML = """<section class="bestofbest" aria-labelledby="besth">
<h2 id="besth">★ Best of the Best</h2>
<p style="margin:4px 0;font-size:.9em;color:#6b5f3e">The AI's top pick from this archive — the single entry that best shows what The Signature Dictionary does. Popped open for you.</p>
<details open>
<summary style="cursor:pointer;font-size:1.05em"><b>spring</b> <span class="pron" style="font-style:italic;color:#6b5f3e">spring</span> <span class="pos" style="font-style:italic;color:#6b5f3e">noun</span> <span class="stamp" style="font-size:.75em;color:#8a7a4d">JAH-DICT-W-085532</span></summary>
<div style="padding-top:8px">
<p class="whybest"><b>Why this is the best:</b> the richest single-word entry in the whole dictionary — three full senses in one headword (a season, a coil, a water source). One word, three meanings, each defined in plain words: this is a complete Signature Dictionary entry.</p>
<div class="bestflow" aria-hidden="true"><div class="bnode"><b>The word</b>spring</div><div class="barrow">→</div><div class="bnode"><b>How it sounds</b>phonetic respelling</div><div class="barrow">→</div><div class="bnode"><b>Its job</b>part of speech</div><div class="barrow">→</div><div class="bnode"><b>What it means</b>every sense, plain words</div></div>
<p><b>What this entry does:</b> gives you the headword, how to say it, what part of speech it is, and every sense of the word — each in one plain sentence.</p>
<p><b>Implications:</b> all <b>102,223</b> headwords in this dictionary get exactly this treatment — original definitions (never copied), a word program, read-aloud, and a personal AI teacher on the full entry page.</p>
<dl>
<dt>spring <span class="pron">spring</span> <span class="pos">noun</span> <span class="stamp">JAH-DICT-W-085532</span></dt>
<dd><ol><li>The season between winter and summer when plants begin to grow.</li><li>A coiled piece of metal that stretches and returns to its shape, used to absorb shock or store energy.</li><li>A place where water flows naturally out of the ground.</li></ol></dd>
</dl>
<div class="beststats"><span class="beststat"><b>102,223</b> headwords in dictionary</span><span class="beststat"><b>3</b> senses — richest single word</span><span class="beststat">Stamp: <b>JAH-DICT-W-085532</b></span></div>
<div class="toolbar">
<button class="btn" id="best-speak" type="button">🔊 Read aloud</button>
<button class="btn" id="best-copy" type="button">⧉ Copy</button>
<button class="btn" id="best-dl" type="button">⤓ Download</button>
<a class="btn" href="../?w=spring">Open full entry →</a>
</div>
</div>
</details>
</section>
<script>
(function(){
"use strict";
var plain="Best of the Best — spring, noun. JAH-DICT-W-085532. Sense 1: The season between winter and summer when plants begin to grow. Sense 2: A coiled piece of metal that stretches and returns to its shape, used to absorb shock or store energy. Sense 3: A place where water flows naturally out of the ground.";
var dl="spring — noun — JAH-DICT-W-085532 — The Signature Dictionary\\n\\n1. The season between winter and summer when plants begin to grow.\\n2. A coiled piece of metal that stretches and returns to its shape, used to absorb shock or store energy.\\n3. A place where water flows naturally out of the ground.";
function copyText(t,btn){function done(ok){var o=btn.textContent;btn.textContent=ok?"Copied ✓":"Copy failed";setTimeout(function(){btn.textContent=o;},1500);}if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(function(){done(true);},function(){done(false);});}else{var ta=document.createElement("textarea");ta.value=t;document.body.appendChild(ta);ta.select();try{document.execCommand("copy");done(true);}catch(e){done(false);}document.body.removeChild(ta);}}
function download(name,text){try{var url=URL.createObjectURL(new Blob([text],{type:"text/plain"}));var a=document.createElement("a");a.href=url;a.download=name;document.body.appendChild(a);a.click();setTimeout(function(){document.body.removeChild(a);try{URL.revokeObjectURL(url);}catch(e){}},800);}catch(e){}}
var speakTimer=null;
function speakStop(){try{if(window.speechSynthesis)window.speechSynthesis.cancel();}catch(e){}if(speakTimer){clearTimeout(speakTimer);speakTimer=null;}}
var speakBtn=document.getElementById("best-speak");
speakBtn.onclick=function(){
  speakStop();
  try{
    if(!("speechSynthesis" in window)){speakBtn.textContent="No voice on this device";setTimeout(function(){speakBtn.textContent="🔊 Read aloud";},1800);return;}
    if(window.speechSynthesis.speaking){speakBtn.textContent="🔊 Read aloud";return;}
    var u=new SpeechSynthesisUtterance(plain);
    speakBtn.textContent="⏹ Stop";
    u.onend=function(){speakBtn.textContent="🔊 Read aloud";};
    u.onerror=function(){speakBtn.textContent="🔊 Read aloud";};
    window.speechSynthesis.speak(u);
    speakTimer=setTimeout(function(){speakBtn.textContent="🔊 Read aloud";},30000);
  }catch(e){speakBtn.textContent="🔊 Read aloud";}
};
document.getElementById("best-copy").onclick=function(){copyText(dl,this);};
document.getElementById("best-dl").onclick=function(){download("spring-JAH-DICT-W-085532.txt",dl);};
})();
</script>"""


def write_static_az(shards, total_w, total_e):
    os.makedirs(AZDIR, exist_ok=True)
    letters = sorted(shards)
    links = " ".join(
        '<a href="%s.html">%s</a>' % (L, L.upper() if L != "0" else "#")
        for L in letters)
    for L in letters:
        rows = shards[L]
        heading = ("Words beginning with " + L.upper()
                   if L != "0" else "Symbols, affixes and numbers")
        page = AZ_PAGE
        page = page.replace("@@TITLE@@", esc(heading) +
                            " \u2014 The Signature Dictionary (A\u2013Z word archive)")
        page = page.replace("@@DESC@@", esc(
            "%s headwords (%s) \u2014 each with phonetic construction, part "
            "of speech and first sense; full entries via ?w= deep links"
            % (fmt(len(rows)), heading)))
        page = page.replace("@@CANON@@", BASE + "az/%s.html" % L)
        page = page.replace("@@HEADING@@", esc(heading))
        page = page.replace("@@LETTERLINKS@@", links)
        page = page.replace("@@COUNT@@", az_count_html(L, len(rows), total_w))
        page = page.replace("@@SEARCH@@", az_search_html(len(rows), total_e))
        page = page.replace("@@BEST@@", BEST_HTML)
        page = page.replace("@@GROUPS@@", groups_html(rows))
        page = page.replace("@@SCRIPT@@",
                            AZ_SCRIPT.replace("@@LETTER@@", L))
        with open(os.path.join(AZDIR, "%s.html" % L), "w",
                  encoding="utf-8") as f:
            f.write(page)
    return letters


def write_sitemap(letters):
    import datetime
    today = datetime.date.today().isoformat()
    urls = []
    for L in letters:
        urls.append(BASE + "data/lexical/shard-%s.json" % L)
        urls.append(BASE + "data/lexical/loc-%s.json" % L)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<!-- LEXICAL SITEMAP (The Signature Dictionary): per-letter '
             'machine JSON shards + archive lazy-preview location maps for '
             'crawlers/RAG ingest. Human-readable az/<L>.html archive pages '
             'live in sitemap-pages.xml. Rebuilt by '
             'code/build_lexical_shards.py on every dictionary build. -->',
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
    shards, locs, n = collect()
    if not shards:
        log("LEXICAL SHARDS: no headwords found — skipping")
        return
    manifest = write_json_shards(shards)
    n_loc = write_loc_maps(locs)
    try:
        stats = json.load(open(STATSPATH, encoding="utf-8"))
        total_w, total_e = stats["words"], stats["total"]
    except Exception:
        total_w, total_e = manifest["total"], manifest["total"]
    letters = write_static_az(shards, total_w, total_e)
    n_urls = write_sitemap(letters)
    log("LEXICAL SHARDS: %d headwords -> %d letter shards, %d loc maps, "
        "%d static A-Z archive pages, sitemap-lexical.xml (%d urls)"
        % (manifest["total"], len(letters), n_loc, len(letters), n_urls))


if __name__ == "__main__":
    build()
