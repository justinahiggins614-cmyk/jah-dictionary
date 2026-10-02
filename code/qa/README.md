# Dictionary QA checkers (TIER 2-8)

Re-runnable checkers for the Signature Dictionary site. Run all four before
declaring any polish pass done:

    ./run_all.sh
    # or individually:
    python3 check_counts.py
    python3 check_dupe_ids.py
    python3 check_missing_ids.py
    python3 check_links.py

## What each checker does

- **check_counts.py** — count-vs-data: decompresses every `data/dict` chunk and
  compares real entry/word/term totals against `data/index/stats.json` and the
  length/sort-order of `data/index/dict.idx.json.gz`. Fails on any mismatch.
  All counts are derived from data; nothing is hardcoded.
- **check_dupe_ids.py** — scans every chunk for duplicate stamps (`e.st`).
  Stamps are permanent entry IDs: any duplicate is a FAIL. Also reports keys
  shared by >1 entry (word-vs-term and term-vs-term collisions) as INFO and
  writes the full list to `dupe_keys.json`; the page renders an "Also filed
  under this headword" disambiguation row for those.
- **check_missing_ids.py** — word stamps `JAH-DICT-W-######` must be fully
  contiguous (FAIL on any gap); term stamps `JAH-DICT-T-######` are never
  renumbered so gaps are legal and reported as INFO only. Also validates the
  stamp format on every entry.
- **check_links.py** — full link audit: extracts every http(s) URL from
  `index.html` + `api.json`, probes each live (200/3xx = fine), and
  statically verifies the in-page wiring for search, A-Z browse, random
  word, read-aloud, copy/download buttons, word program, word patent,
  AI teacher, the `?w=` / `?dict=` / `?id=` / `?q=` routes, wiki/leaks
  cross-links, the JAH NETWORK bar, the provenance label, the Last-updated
  line, the YOU-ARE-HERE marker, and the a11y additions. Probes use curl:
  python's urllib hangs on some hosts behind this sandbox's egress proxy.
  The `raw_github_base` prefix in api.json is documentation, not a link,
  and is excluded from probing.

## Related

- **build_stamp_index.py** — one-shot (re)builder for
  `data/index/stamp.idx.json.gz` (stamp ID -> `dict.idx` row) from shipped
  data. The daily refresh regenerates it via `build_all.py`
  (`write_stamp_index`); this script is for manual regeneration. Verifies
  every stamp resolves back to its own entry.
- `../tests/dict_qa.js` — DOM-level suite for the page scripts (node).
  Extracts the real `<script>` blocks from `index.html` and runs them
  against a DOM stub + real dictionary data.

## Notes

- `data/definitions/` is owned by the `iwb-definitions-drip` cron — these
  checkers never write there.
- The daily `jah-dictionary-daily-update` cron (04:37 EDT) re-runs
  `code/dict/build_all.py` and commits with `git add -A`, so new files
  under `data/index/` (e.g. `stamp.idx.json.gz`) and the refreshed
  `api.json` are picked up automatically.
