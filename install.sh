#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
DRY_RUN=0
LIST_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    --list)
      LIST_ONLY=1
      ;;
  esac
done

"$KIT_DIR/scripts/install-codex-skills.sh" "$@"

if [[ "$LIST_ONLY" -eq 1 ]]; then
  exit 0
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "would install commands into $BIN_DIR"
  exit 0
fi

mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/grounded-manual" <<EOF
#!/usr/bin/env bash
exec python3 "$KIT_DIR/scripts/grounded_manual.py" "\$@"
EOF
chmod +x "$BIN_DIR/grounded-manual"

cat > "$BIN_DIR/citation-auditor" <<EOF
#!/usr/bin/env bash
exec python3 "$KIT_DIR/scripts/grounded_manual.py" audit-claims "\$@"
EOF
chmod +x "$BIN_DIR/citation-auditor"

echo "Installed commands into $BIN_DIR"
echo "Run: grounded-manual doctor"
