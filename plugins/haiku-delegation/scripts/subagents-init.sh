#!/bin/sh
# Operator tool behind /subagents-init (haiku-delegation). Copies the shipped SUBAGENTS.md roster to a project root and
# imports it from CLAUDE.md or AGENTS.md. POSIX sh port of subagents-init.ps1 (same flags, stdout, files and exit codes).
#   subagents-init.sh [-Project <dir>] [-Import auto|claude|agents|none] [-Update] [-DryRun]
# Never overwrites: an existing SUBAGENTS.md that differs is kept unless -Update is given, and -Update replaces only the
# part above "## Project facts" (the project's own facts are kept) after writing SUBAGENTS.md.bak-<UTC timestamp>.
# The import line (@SUBAGENTS.md) is added once, to CLAUDE.md when it exists, else AGENTS.md, else a new CLAUDE.md.
# Exit codes: 0 ok, 1 refused (bad input), 2 internal error.
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$KIT_SCRIPT_DIR/../templates/SUBAGENTS.md"
MARKER='## Project facts'

refuse() { printf 'REFUSED: %s\n' "$1" >&2; exit 1; }
fail_internal() { printf 'subagents-init failed: %s\n' "$1" >&2; exit 2; }
param_error() { printf 'subagents-init: %s\n' "$1" >&2; exit 1; }

PROJECT=""; IMPORT="auto"; UPDATE=0; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    -Project|-project) [ $# -ge 2 ] || param_error "missing value for -Project"; PROJECT="$2"; shift 2 ;;
    -Import|-import)   [ $# -ge 2 ] || param_error "missing value for -Import";  IMPORT="$2"; shift 2 ;;
    -Update|-update)   UPDATE=1; shift ;;
    -DryRun|-dryrun)   DRY=1; shift ;;
    *) param_error "unknown argument: $1" ;;
  esac
done
case "$IMPORT" in auto|claude|agents|none) ;; *) param_error "-Import '$IMPORT' is not one of auto, claude, agents, none" ;; esac
[ -f "$TEMPLATE" ] || fail_internal "template not found: $TEMPLATE"

# --- project root: -Project as given, else the git top level of the current folder, else the current folder
if [ -n "$PROJECT" ]; then
  [ -d "$PROJECT" ] || refuse "-Project is not a folder: $PROJECT"
  ROOT="$(cd "$PROJECT" && pwd)"
else
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || ROOT=""
  [ -n "$ROOT" ] && [ -d "$ROOT" ] || ROOT="$(pwd)"
fi
[ -w "$ROOT" ] || refuse "the project folder is not writable: $ROOT"
printf 'ROOT: %s\n' "$ROOT"

TMP=$(mktemp -d 2>/dev/null) || fail_internal "cannot create a temp folder"
trap 'rm -rf "$TMP"' EXIT
trap 'exit 2' HUP INT TERM

DEST="$ROOT/SUBAGENTS.md"
if [ -L "$DEST" ]; then refuse "SUBAGENTS.md in the project root is a symbolic link; replace it with a real file first"; fi

# --- step 1: SUBAGENTS.md
if [ ! -e "$DEST" ]; then
  if [ "$DRY" = 1 ]; then echo "WOULD CREATE SUBAGENTS.md"; else cp "$TEMPLATE" "$DEST" || fail_internal "cannot write $DEST"; echo "CREATED SUBAGENTS.md"; fi
elif cmp -s "$TEMPLATE" "$DEST"; then
  echo "UNCHANGED SUBAGENTS.md (identical to the shipped version)"
elif [ "$UPDATE" = 0 ]; then
  echo "EXISTS SUBAGENTS.md differs from the shipped version; kept as it is (run again with -Update to refresh everything above '$MARKER')"
else
  grep -q "^$MARKER" "$DEST" || refuse "SUBAGENTS.md has no '$MARKER' section, so the project's own text cannot be told apart; merge by hand"
  grep -q "^$MARKER" "$TEMPLATE" || fail_internal "the shipped template has no '$MARKER' section"
  awk -v m="^$MARKER" '$0 ~ m { exit } { print }' "$TEMPLATE" > "$TMP/new" || fail_internal "cannot split the template"
  awk -v m="^$MARKER" '$0 ~ m { f = 1 } f { print }' "$DEST" >> "$TMP/new" || fail_internal "cannot split SUBAGENTS.md"
  if cmp -s "$TMP/new" "$DEST"; then
    echo "UNCHANGED SUBAGENTS.md (shipped part already up to date)"
  elif [ "$DRY" = 1 ]; then
    echo "WOULD UPDATE SUBAGENTS.md (backup first)"
  else
    BAK="$DEST.bak-$(date -u +%Y%m%dT%H%M%SZ)"
    cp "$DEST" "$BAK" || fail_internal "cannot write the backup"
    cp "$TMP/new" "$DEST" || fail_internal "cannot write $DEST"
    echo "UPDATED SUBAGENTS.md (previous version: $(basename "$BAK"))"
  fi
fi

# --- step 2: the @SUBAGENTS.md import
[ "$IMPORT" = none ] && { echo "IMPORT skipped (-Import none)"; echo "DONE"; exit 0; }
case "$IMPORT" in
  claude) TARGET="CLAUDE.md" ;;
  agents) TARGET="AGENTS.md" ;;
  *) if [ -f "$ROOT/CLAUDE.md" ]; then TARGET="CLAUDE.md"; elif [ -f "$ROOT/AGENTS.md" ]; then TARGET="AGENTS.md"; else TARGET="CLAUDE.md"; fi ;;
esac
TF="$ROOT/$TARGET"
if [ -L "$TF" ]; then refuse "$TARGET is a symbolic link; edit its target by hand"; fi
if [ -f "$TF" ] && grep -q '@SUBAGENTS\.md' "$TF"; then
  echo "IMPORT already in $TARGET"
elif [ "$DRY" = 1 ]; then
  if [ -f "$TF" ]; then echo "WOULD ADD import to $TARGET"; else echo "WOULD CREATE $TARGET with the import"; fi
else
  if [ -f "$TF" ]; then
    # keep the file's own text byte for byte; only make sure the new block starts on a fresh line
    if [ -s "$TF" ] && [ "$(tail -c1 "$TF" | wc -l | tr -d ' ')" = 0 ]; then printf '\n' >> "$TF" || fail_internal "cannot write $TF"; fi
    [ -s "$TF" ] && { printf '\n' >> "$TF" || fail_internal "cannot write $TF"; }
    printf '## Subagents\n\n@SUBAGENTS.md\n' >> "$TF" || fail_internal "cannot write $TF"
    echo "IMPORT added to $TARGET"
  else
    printf '## Subagents\n\n@SUBAGENTS.md\n' > "$TF" || fail_internal "cannot write $TF"
    echo "IMPORT created $TARGET"
  fi
fi
echo "DONE"
exit 0
