#!/bin/bash
# Update and publish AI Revenue Monitor to GitHub Pages
# Usage: bash publish.sh "optional commit message"

set -e
cd "$(git rev-parse --show-toplevel)"

echo "1. Regenerating dashboard data..."
python scripts/generate_dashboard.py

echo "2. Syncing to docs/..."
rm -rf docs
cp -r dashboard docs

echo "3. Committing and pushing..."
MSG="${1:-update: refresh dashboard data}"
git add docs/ data/
git commit -m "$MSG" || echo "No changes to commit"
git push

echo ""
echo "Done! Site will update at https://notalways123.github.io/ai-revenue-monitor/ within 1-2 min."
