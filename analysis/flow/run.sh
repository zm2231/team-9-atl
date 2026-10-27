#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
rm -f out/numbers.json
for s in capacity corridor getout medical equity scenarios storm_library; do
  echo "== $s"
  uv run python "$s.py"
done
