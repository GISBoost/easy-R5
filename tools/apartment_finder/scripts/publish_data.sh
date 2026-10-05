#!/usr/bin/env bash
# Publish <easy>/gdzie-mieszkac-lodz-data to GISBoost/gdzie-mieszkac-lodz-data (branch gh-pages) WITHOUT history.
#
#   bash scripts/publish_data.sh          # dry run: builds the one-commit repo in a temp dir, reports size
#   bash scripts/publish_data.sh --push   # also force-pushes it (replaces the branch)
#
# Why an orphan commit + force push: a regenerated data set is ~250 MB of incompressible binary, so normal commits
# would grow the repo history past the ~1 GB recommended size within a few runs. A single-commit branch keeps the
# repo at the size of the CURRENT data (old objects become unreachable and GitHub garbage-collects them).
# Pages limits: site <= 1 GB, 10 builds/hour, ~100 GB/month soft bandwidth; a page query reads one Range-ed row.
# Alternative if updates ever become frequent (variant 2): data zip as a Release asset + an Actions workflow that
# deploys it with upload-pages-artifact/deploy-pages, so nothing but code lives in git.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/../../../.." && pwd)/gdzie-mieszkac-lodz-data"
REPO="https://github.com/GISBoost/gdzie-mieszkac-lodz-data.git"
[ -f "$SRC/manifest.json" ] || { echo "no manifest.json in $SRC - run export_web.py first"; exit 1; }
MB=$(du -sm "$SRC" | cut -f1)
[ "$MB" -le 900 ] || { echo "data is ${MB} MB, over the 900 MB guard (Pages limit 1 GB)"; exit 1; }
BIG=$(find "$SRC" -type f -size +50M | head -1); [ -z "$BIG" ] || { echo "file over 50 MB: $BIG"; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
cp -r "$SRC/." "$TMP/"; rm -rf "$TMP/.git"; cd "$TMP"
git init -q -b gh-pages
git add -A
git -c user.name="${GIT_AUTHOR_NAME:-GISBoost}" -c user.email="${GIT_AUTHOR_EMAIL:-noreply@users.noreply.github.com}" \
    commit -q -m "data: $(date +%F)"
echo "built one-commit repo from ${MB} MB of data: $(git count-objects -vH | grep size-pack)"
if [ "${1:-}" = "--push" ]; then git push --force "$REPO" gh-pages; else echo "dry run only (add --push to publish)"; fi
