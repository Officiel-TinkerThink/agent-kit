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

PROJECT=""; IMPORT="auto"; UPDATE=0; DRY=0; NOORCH=0
while [ $# -gt 0 ]; do
  case "$1" in
    -Project|-project) [ $# -ge 2 ] || param_error "missing value for -Project"; PROJECT="$2"; shift 2 ;;
    -Import|-import)   [ $# -ge 2 ] || param_error "missing value for -Import";  IMPORT="$2"; shift 2 ;;
    -Update|-update)   UPDATE=1; shift ;;
    -DryRun|-dryrun)   DRY=1; shift ;;
    -NoOrchestration|-noorchestration) NOORCH=1; shift ;;
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
[ "$IMPORT" = none ] && { echo "IMPORT skipped (-Import none)"; echo "ORCHESTRATION skipped (-Import none)"; echo "DONE"; exit 0; }
case "$IMPORT" in
  claude) TARGET="CLAUDE.md" ;;
  agents) TARGET="AGENTS.md" ;;
  *) if [ -f "$ROOT/CLAUDE.md" ]; then TARGET="CLAUDE.md"; elif [ -f "$ROOT/AGENTS.md" ]; then TARGET="AGENTS.md"; else TARGET="CLAUDE.md"; fi ;;
esac
TF="$ROOT/$TARGET"
if [ -L "$TF" ]; then refuse "$TARGET is a symbolic link; edit its target by hand"; fi
if [ -f "$TF" ] && [ ! -w "$TF" ]; then refuse "$TARGET is read-only; make it writable first"; fi
# refuse damaged orchestration markers up front, so a refused run has written nothing to $TARGET
if [ "$NOORCH" = 0 ] && [ -f "$TF" ]; then
  PB=$(grep -c '^<!-- agent-kit:orchestration:begin' "$TF"); PE=$(grep -c '^<!-- agent-kit:orchestration:end -->' "$TF")
  if [ "$PB" != 0 ] || [ "$PE" != 0 ]; then
    if [ "$PB" != 1 ] || [ "$PE" != 1 ] || [ "$(grep -n '^<!-- agent-kit:orchestration:begin' "$TF" | cut -d: -f1)" -ge "$(grep -n '^<!-- agent-kit:orchestration:end -->' "$TF" | cut -d: -f1)" ]; then
      refuse "the orchestration markers in $TARGET are damaged ($PB begin line(s), $PE end line(s), or the end comes first); fix them by hand or remove both marker lines and the text between them"
    fi
  fi
fi
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

# --- step 3: the orchestration block = the shipped AGENTS.md text, verbatim, between two marker lines, in the same file as the import.
# Everything already in the file stays byte for byte. -Update replaces only what sits between the markers (backup first).
if [ "$NOORCH" = 1 ]; then
  echo "ORCHESTRATION skipped (-NoOrchestration)"
else
  OTEMPLATE="$KIT_SCRIPT_DIR/../templates/AGENTS.md"
  [ -f "$OTEMPLATE" ] || fail_internal "template not found: $OTEMPLATE"
  OBEGIN='<!-- agent-kit:orchestration:begin (managed by /haiku-delegation:subagents-init; the text between the markers is replaced by -Update, everything outside is yours) -->'
  OEND='<!-- agent-kit:orchestration:end -->'
  tr -d '\r' < "$OTEMPLATE" | awk '{ print }' > "$TMP/tpl" || fail_internal "cannot read the template"
  { printf '%s\n' "$OBEGIN"; cat "$TMP/tpl"; printf '%s\n' "$OEND"; } > "$TMP/block"
  NB=0; NE=0; CRLF=0
  if [ -f "$TF" ]; then
    NB=$(grep -c '^<!-- agent-kit:orchestration:begin' "$TF"); NE=$(grep -c '^<!-- agent-kit:orchestration:end -->' "$TF")
    [ "$(tr -cd '\r' < "$TF" | wc -c | tr -d ' ')" -gt 0 ] && CRLF=1   # tr reads raw bytes; grep on Windows hides carriage returns
  fi
  [ "$CRLF" = 1 ] && { awk '{ printf "%s\r\n", $0 }' "$TMP/block" > "$TMP/block.eol" && mv "$TMP/block.eol" "$TMP/block"; }
  if [ "$NB" = 0 ] && [ "$NE" = 0 ]; then
    if [ -s "$TF" ] && awk -v RS='\001' 'NR == FNR { gsub(/\r/, ""); sub(/\n+$/, ""); t = $0; next } { gsub(/\r/, ""); exit !index($0, t) }' "$TMP/tpl" "$TF"; then
      echo "ORCHESTRATION already present in $TARGET (verbatim; no markers added)"
    elif [ "$DRY" = 1 ]; then
      echo "WOULD ADD orchestration to $TARGET"
    else
      # keep the file's own text byte for byte; start the block on a fresh line after one blank line
      if [ -s "$TF" ] && [ "$(tail -c1 "$TF" | wc -l | tr -d ' ')" = 0 ]; then if [ "$CRLF" = 1 ]; then printf '\r\n' >> "$TF"; else printf '\n' >> "$TF"; fi || fail_internal "cannot write $TF"; fi
      if [ -s "$TF" ]; then if [ "$CRLF" = 1 ]; then printf '\r\n' >> "$TF"; else printf '\n' >> "$TF"; fi || fail_internal "cannot write $TF"; fi
      cat "$TMP/block" >> "$TF" || fail_internal "cannot write $TF"
      echo "ORCHESTRATION added to $TARGET"
    fi
  elif [ "$NB" = 1 ] && [ "$NE" = 1 ] && [ "$(grep -n '^<!-- agent-kit:orchestration:begin' "$TF" | cut -d: -f1)" -lt "$(grep -n '^<!-- agent-kit:orchestration:end -->' "$TF" | cut -d: -f1)" ]; then
    awk '/^<!-- agent-kit:orchestration:begin/ { f = 1; next } /^<!-- agent-kit:orchestration:end -->/ { f = 0 } f' "$TF" | tr -d '\r' > "$TMP/inner"
    if cmp -s "$TMP/inner" "$TMP/tpl"; then
      echo "ORCHESTRATION up to date in $TARGET"
    elif [ "$UPDATE" = 0 ]; then
      echo "ORCHESTRATION outdated in $TARGET; run again with -Update to refresh the block (text outside the markers is never touched)"
    elif [ "$DRY" = 1 ]; then
      echo "WOULD UPDATE orchestration in $TARGET (backup first)"
    else
      awk -v blk="$TMP/block" '/^<!-- agent-kit:orchestration:begin/ && !done { while ((getline l < blk) > 0) print l; skip = 1; done = 1; next } skip && /^<!-- agent-kit:orchestration:end -->/ { skip = 0; next } !skip { print }' "$TF" > "$TMP/newtf" || fail_internal "cannot build the updated $TARGET"
      BAK="$TF.bak-$(date -u +%Y%m%dT%H%M%SZ)"
      cp "$TF" "$BAK" || fail_internal "cannot write the backup"
      cp "$TMP/newtf" "$TF" || fail_internal "cannot write $TF"
      echo "ORCHESTRATION updated in $TARGET (previous version: $(basename "$BAK"))"
    fi
  else
    refuse "the orchestration markers in $TARGET are damaged ($NB begin line(s), $NE end line(s), or the end comes first); fix them by hand or remove both marker lines and the text between them"
  fi
fi
echo "DONE"
exit 0
