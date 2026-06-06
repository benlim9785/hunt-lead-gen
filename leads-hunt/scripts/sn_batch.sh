#!/bin/bash
# Batch Sales Navigator lookup — for ad-hoc verification.
# Usage: sn_batch.sh "Company A" "Company B" ...
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for c in "$@"; do
  echo "=== $c ==="
  python3 "$SCRIPT_DIR/sales_nav_query.py" "$c" 2>&1
  echo
done
