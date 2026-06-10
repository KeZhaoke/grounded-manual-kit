#!/usr/bin/env bash
set -euo pipefail

MODE="symlink"
FORCE=0
DRY_RUN=0
LIST_ONLY=0
DEST=""

usage() {
  cat <<'USAGE'
Usage: scripts/install-codex-skills.sh [options]

Install this repository's skills into the Codex global skills directory.

Options:
  --symlink        Install skills as symlinks (default)
  --copy           Copy skills as snapshots
  --dest DIR       Install into DIR (default: ${CODEX_HOME:-$HOME/.codex}/skills)
  --force          Replace an existing conflicting target
  --dry-run        Show what would change without writing anything
  --list           List discovered skills and target status
  -h, --help       Show this help
USAGE
}

die() {
  echo "error: $*" >&2
  exit 1
}

resolve_existing_dir() {
  local path=$1
  (cd "$path" && pwd -P)
}

resolve_maybe_missing() {
  local path=$1

  if command -v realpath >/dev/null 2>&1; then
    realpath -m "$path"
    return
  fi

  local dir base
  dir=$(dirname "$path")
  base=$(basename "$path")
  if [[ -d "$dir" ]]; then
    printf '%s/%s\n' "$(cd "$dir" && pwd -P)" "$base"
  else
    printf '%s\n' "$path"
  fi
}

resolve_link_target() {
  local link=$1
  local raw
  raw=$(readlink "$link")

  if [[ "$raw" = /* ]]; then
    resolve_maybe_missing "$raw"
  else
    resolve_maybe_missing "$(dirname "$link")/$raw"
  fi
}

metadata_value() {
  local file=$1
  local key=$2
  local k v

  [[ -f "$file" ]] || return 1
  while IFS='=' read -r k v; do
    if [[ "$k" == "$key" ]]; then
      printf '%s\n' "$v"
      return 0
    fi
  done < "$file"

  return 1
}

make_temp_path() {
  local prefix=$1
  local candidate="${DEST}/.${prefix}.$$"
  local i=0

  while [[ -e "$candidate" || -L "$candidate" ]]; do
    i=$((i + 1))
    candidate="${DEST}/.${prefix}.$$.${i}"
  done

  printf '%s\n' "$candidate"
}

replace_target() {
  local staged=$1
  local target=$2
  local backup=""
  local status

  if [[ -e "$target" || -L "$target" ]]; then
    backup=$(make_temp_path "$(basename "$target").old")
    mv "$target" "$backup"
    if mv "$staged" "$target"; then
      rm -rf -- "$backup"
    else
      status=$?
      if [[ -e "$backup" || -L "$backup" ]]; then
        mv "$backup" "$target"
      fi
      return "$status"
    fi
  else
    mv "$staged" "$target"
  fi
}

target_description() {
  local target=$1
  local metadata current mode

  if [[ -L "$target" ]]; then
    printf 'symlink -> %s\n' "$(resolve_link_target "$target")"
  elif [[ -d "$target" ]]; then
    metadata="$target/.codex-skill-source"
    current=$(metadata_value "$metadata" "source_skill_path" || true)
    mode=$(metadata_value "$metadata" "mode" || true)
    if [[ -n "$current" ]]; then
      printf 'directory copied from %s' "$current"
      if [[ -n "$mode" ]]; then
        printf ' (%s)' "$mode"
      fi
      printf '\n'
    else
      printf 'directory with unknown source\n'
    fi
  elif [[ -e "$target" ]]; then
    printf 'file or special path\n'
  else
    printf 'missing\n'
  fi
}

conflict() {
  local skill_name=$1
  local source_real=$2
  local target=$3

  {
    echo "conflict: ${target} already exists for skill '${skill_name}'"
    echo "current: $(target_description "$target")"
    echo "source:  ${source_real}"
    echo "use --force to replace it"
  } >&2
  exit 1
}

assert_skill_allowed() {
  local skill_dir=$1
  local skill_name=$2
  local source_real target current metadata

  source_real=$(resolve_existing_dir "$skill_dir")
  target="$DEST/$skill_name"

  if [[ -L "$target" ]]; then
    current=$(resolve_link_target "$target")
    if [[ "$MODE" == "symlink" && "$current" == "$source_real" ]]; then
      return
    fi
    [[ "$FORCE" -eq 1 ]] || conflict "$skill_name" "$source_real" "$target"
  elif [[ -d "$target" ]]; then
    metadata="$target/.codex-skill-source"
    current=$(metadata_value "$metadata" "source_skill_path" || true)
    if [[ "$MODE" == "copy" && "$current" == "$source_real" ]]; then
      return
    fi
    [[ "$FORCE" -eq 1 ]] || conflict "$skill_name" "$source_real" "$target"
  elif [[ -e "$target" ]]; then
    [[ "$FORCE" -eq 1 ]] || conflict "$skill_name" "$source_real" "$target"
  fi
}

should_refresh_copy() {
  local target=$1
  local source_real=$2
  local metadata current

  [[ "$MODE" == "copy" && -d "$target" ]] || return 1
  metadata="$target/.codex-skill-source"
  current=$(metadata_value "$metadata" "source_skill_path" || true)
  [[ "$current" == "$source_real" ]]
}

write_copy_metadata() {
  local staged=$1
  local source_real=$2
  local installed_at
  installed_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  {
    printf 'source_repo=%s\n' "$KIT_DIR_REAL"
    printf 'source_skill_path=%s\n' "$source_real"
    printf 'mode=copy\n'
    printf 'installed_at=%s\n' "$installed_at"
    printf 'installer=install-codex-skills.sh\n'
  } > "$staged/.codex-skill-source"
}

stage_skill() {
  local skill_name=$1
  local source_real=$2
  local staged

  staged=$(make_temp_path "${skill_name}.tmp")

  if [[ "$MODE" == "symlink" ]]; then
    ln -s "$source_real" "$staged"
  else
    cp -a "$source_real" "$staged"
    write_copy_metadata "$staged" "$source_real"
  fi

  printf '%s\n' "$staged"
}

install_skill() {
  local skill_dir=$1
  local skill_name=$2
  local source_real target current metadata staged refresh

  source_real=$(resolve_existing_dir "$skill_dir")
  target="$DEST/$skill_name"
  refresh=0

  if [[ "$LIST_ONLY" -eq 1 ]]; then
    echo "- $skill_name"
    echo "  source: $source_real"
    echo "  target: $target"
    echo "  status: $(target_description "$target")"
    return
  fi

  if [[ -L "$target" ]]; then
    current=$(resolve_link_target "$target")
    if [[ "$MODE" == "symlink" && "$current" == "$source_real" ]]; then
      echo "ok: $skill_name already linked to $source_real"
      return
    fi
    [[ "$FORCE" -eq 1 ]] || conflict "$skill_name" "$source_real" "$target"
  elif [[ -d "$target" ]]; then
    metadata="$target/.codex-skill-source"
    current=$(metadata_value "$metadata" "source_skill_path" || true)
    if [[ "$MODE" == "copy" && "$current" == "$source_real" ]]; then
      :
    else
      [[ "$FORCE" -eq 1 ]] || conflict "$skill_name" "$source_real" "$target"
    fi
  elif [[ -e "$target" ]]; then
    [[ "$FORCE" -eq 1 ]] || conflict "$skill_name" "$source_real" "$target"
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    if should_refresh_copy "$target" "$source_real"; then
      echo "would refresh: $target with copy from $source_real"
    elif [[ -e "$target" || -L "$target" ]]; then
      echo "would replace: $target with $MODE from $source_real"
    else
      echo "would install: $target with $MODE from $source_real"
    fi
    return
  fi

  if should_refresh_copy "$target" "$source_real"; then
    refresh=1
  fi

  staged=$(stage_skill "$skill_name" "$source_real")
  replace_target "$staged" "$target"
  if [[ "$refresh" -eq 1 ]]; then
    echo "refreshed: $skill_name -> $target ($MODE)"
  else
    echo "installed: $skill_name -> $target ($MODE)"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --symlink)
      MODE="symlink"
      shift
      ;;
    --copy)
      MODE="copy"
      shift
      ;;
    --dest)
      [[ $# -ge 2 ]] || die "--dest requires a directory"
      DEST=$2
      shift 2
      ;;
    --dest=*)
      DEST=${1#--dest=}
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --list)
      LIST_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
KIT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
KIT_DIR_REAL=$(resolve_existing_dir "$KIT_DIR")
SKILLS_DIR_REAL=$(resolve_existing_dir "$KIT_DIR/skills")

if [[ -z "$DEST" ]]; then
  CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
  DEST="$CODEX_HOME/skills"
fi
DEST=$(resolve_maybe_missing "$DEST")

case "$DEST/" in
  "$SKILLS_DIR_REAL"/*)
    die "destination must not be inside source skills directory: $SKILLS_DIR_REAL"
    ;;
esac

shopt -s nullglob
skill_files=("$KIT_DIR"/skills/*/SKILL.md)
[[ ${#skill_files[@]} -gt 0 ]] || die "no skills found under $KIT_DIR/skills"

if [[ "$LIST_ONLY" -eq 0 ]]; then
  for skill_md in "${skill_files[@]}"; do
    skill_dir=$(dirname "$skill_md")
    skill_name=$(basename "$skill_dir")
    [[ "$skill_name" =~ ^[A-Za-z0-9._-]+$ ]] || die "unsafe skill name: $skill_name"
    assert_skill_allowed "$skill_dir" "$skill_name"
  done
fi

if [[ "$DRY_RUN" -eq 0 && "$LIST_ONLY" -eq 0 ]]; then
  mkdir -p "$DEST"
fi

if [[ "$LIST_ONLY" -eq 1 ]]; then
  echo "Skills from $KIT_DIR/skills"
  echo "Destination: $DEST"
fi

for skill_md in "${skill_files[@]}"; do
  skill_dir=$(dirname "$skill_md")
  skill_name=$(basename "$skill_dir")
  [[ "$skill_name" =~ ^[A-Za-z0-9._-]+$ ]] || die "unsafe skill name: $skill_name"
  install_skill "$skill_dir" "$skill_name"
done

if [[ "$LIST_ONLY" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
  echo "Installed skills into $DEST"
  echo "Restart Codex to pick up new skills."
fi
