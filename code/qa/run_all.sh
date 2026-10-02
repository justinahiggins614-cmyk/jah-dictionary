#!/bin/sh
# TIER 2-8: run all dictionary QA checkers. Exit 1 if any fail.
set -u
cd "$(dirname "$0")"
rc=0
for c in check_counts.py check_dupe_ids.py check_missing_ids.py check_links.py; do
  echo "########## $c ##########"
  python3 "$c" || rc=1
  echo
done
if [ "$rc" -eq 0 ]; then echo "ALL QA CHECKERS PASSED"; else echo "QA FAILURES PRESENT"; fi
exit "$rc"
