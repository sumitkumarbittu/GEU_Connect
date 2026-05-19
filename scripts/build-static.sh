#!/usr/bin/env bash
set -euo pipefail

api_base_url="${API_BASE_URL:-${GEU_API_BASE:-}}"

rm -rf public
mkdir -p public/static

cp index.html public/index.html
cp -R static/. public/static/

cat > public/static/config.js <<EOF
window.GEU_API_BASE = "${api_base_url}";
EOF

echo "Static config generated with API base: ${api_base_url:-same-origin}"
