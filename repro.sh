#!/usr/bin/env bash
# One command, no API key, $0: fetch the released run data, re-run both pre-registered analyses on it, and check
# the headline numbers against RESULTS.md and EXT_RESULTS.md. Needs Python 3.13 with pyyaml and numpy, and curl.
#
#   bash repro.sh                      # downloads the data release
#   DATA=/path/to/runs.tar.gz bash repro.sh
set -euo pipefail
cd "$(dirname "$0")"
TAG="data-v2"
SHA256="1c9a9d4c12e3d78910fb2bf3bfb6de7a5a50e9525f0df8383c490f928e6e4eba"
URL="https://github.com/TanishGudise/session-memory-bench/releases/download/${TAG}/runs.tar.gz"
PY="${PYTHON:-python3}"
OUT=".repro"
mkdir -p "$OUT"
if [ -n "${DATA:-}" ]; then
  cp "$DATA" "$OUT/runs.tar.gz"
elif [ ! -f "$OUT/runs.tar.gz" ]; then
  curl -fsSL "$URL" -o "$OUT/runs.tar.gz"
fi
echo "$SHA256  $OUT/runs.tar.gz" | shasum -a 256 -c -
rm -rf "$OUT/data" && mkdir -p "$OUT/data"
tar -xzf "$OUT/runs.tar.gz" -C "$OUT/data"
D="$OUT/data/runs"
"$PY" scripts/analyze.py "$D/eval/main" --corpus "$D/history/run1" --out "$OUT/main" > /dev/null
"$PY" scripts/analyze.py "$D/eval/main" --corpus "$D/history/run1" --exclude-tasks notify-05 --out "$OUT/main_g4" > /dev/null
"$PY" scripts/analyze_ext.py "$D/eval/ext" > /dev/null
"$PY" repro_check.py "$OUT"
