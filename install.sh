#!/usr/bin/env bash
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILL_DIR="$CODEX_HOME/skills"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "$SKILL_DIR" "$BIN_DIR"

ln -sfn "$KIT_DIR/skills/grounded-manual" "$SKILL_DIR/grounded-manual"
ln -sfn "$KIT_DIR/skills/citation-auditor" "$SKILL_DIR/citation-auditor"

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

echo "Installed skills into $SKILL_DIR"
echo "Installed commands into $BIN_DIR"
echo "Run: grounded-manual doctor"

