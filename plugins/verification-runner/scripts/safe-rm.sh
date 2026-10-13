#!/bin/sh
# safe-rm.sh - the executor behind `rm` for guarded agents (POSIX sh port of safe-rm.ps1). It NEVER deletes: it validates
# against safe-rm-policy.json, records the operation (path, size, SHA-256) in the audit file and a manifest FIRST, then MOVES
# the items into the quarantine folder (<quarantineRoot>/<id>/data/<absolute path>). Restore with safe-rm-restore.sh.
# Usage: sh safe-rm.sh [-Recurse] [-DryRun] [-Agent <name>] [-Session <id>] [-PolicyFile <file>] <absolute-path>...
# Exit codes: 0 ok / nothing to do, 2 refused, 3 partial or failed move (see output).
LC_ALL=C
export LC_ALL
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"
. "$KIT_SCRIPT_DIR/safe-rm-lib.sh"

# ---- JSON writers (every string through json_str) ----------------------------------------------------------------
# srm_tsv_split <line>: TS_1..TS_8 from a TAB-separated item record (path kind files bytes sha256 quarantinePath status error).
srm_tsv_split() {
  ts_r=$1
  TS_1=${ts_r%%"$SRM_TAB"*}; ts_r=${ts_r#*"$SRM_TAB"}
  TS_2=${ts_r%%"$SRM_TAB"*}; ts_r=${ts_r#*"$SRM_TAB"}
  TS_3=${ts_r%%"$SRM_TAB"*}; ts_r=${ts_r#*"$SRM_TAB"}
  TS_4=${ts_r%%"$SRM_TAB"*}; ts_r=${ts_r#*"$SRM_TAB"}
  TS_5=${ts_r%%"$SRM_TAB"*}; ts_r=${ts_r#*"$SRM_TAB"}
  TS_6=${ts_r%%"$SRM_TAB"*}; ts_r=${ts_r#*"$SRM_TAB"}
  TS_7=${ts_r%%"$SRM_TAB"*}; ts_r=${ts_r#*"$SRM_TAB"}
  TS_8=$ts_r
}

# srm_make_id: yyyyMMddTHHmmssfff-xxxx (the format safe-rm-restore.ps1 validates).
srm_make_id() {
  mi_d=$(date -u +%Y%m%dT%H%M%S)
  mi_ms=$(date -u +%N 2>/dev/null)
  case "$mi_ms" in
    [0-9][0-9][0-9]*) mi_ms=$(printf '%s' "$mi_ms" | cut -c1-3) ;;
    *) mi_ms=000 ;;
  esac
  mi_hex=$(od -An -N2 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')
  case "$mi_hex" in
    [0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
    *) mi_hex=$(printf '%04x' $(( ($$ * 40503 + $(date +%s)) % 65536 ))) ;;
  esac
  printf '%s%s-%s' "$mi_d" "$mi_ms" "$mi_hex"
}

# srm_item_json: JSON object for the TS_* record (manifest form, with status and optional error).
srm_item_json() {
  printf '{"path": %s, "kind": %s, "files": %s, "bytes": %s, "sha256": %s, "quarantinePath": %s, "status": %s' \
    "$(json_str "$TS_1")" "$(json_str "$TS_2")" "$TS_3" "$TS_4" "$(json_str "$TS_5")" "$(json_str "$TS_6")" "$(json_str "$TS_7")"
  if [ -n "$TS_8" ]; then printf ', "error": %s' "$(json_str "$TS_8")"; fi
  printf '}'
}

# sr_manifest <file> <id> <ts> <user> <agent> <session> <recurse 0|1> <status> <items-file>
sr_manifest() {
  sm_f=$1; sm_items=$9
  sm_body=""; sm_sep=""
  while IFS= read -r sm_l; do
    [ -n "$sm_l" ] || continue
    srm_tsv_split "$sm_l"
    sm_obj=$(srm_item_json)
    sm_body="$sm_body$sm_sep    $sm_obj"
    sm_sep=",$SRM_NL"
  done < "$sm_items"
  if [ -n "$sm_body" ]; then sm_arr="[$SRM_NL$sm_body$SRM_NL  ]"; else sm_arr="[]"; fi
  sm_rec=false
  [ "$7" = 1 ] && sm_rec=true
  {
    printf '{\n'
    printf '  "schema": "safe-rm/1",\n'
    printf '  "id": %s,\n' "$(json_str "$2")"
    printf '  "ts": %s,\n' "$(json_str "$3")"
    printf '  "user": %s,\n' "$(json_str "$4")"
    printf '  "agent": %s,\n' "$(json_str "$5")"
    printf '  "session": %s,\n' "$(json_str "$6")"
    printf '  "recurse": %s,\n' "$sm_rec"
    printf '  "status": %s,\n' "$(json_str "$8")"
    printf '  "items": %s\n' "$sm_arr"
    printf '}\n'
  } > "$sm_f" 2>/dev/null || return 1
  return 0
}

# sr_audit_planned <id> <ts> <user> <agent> <session> <items-file>: one JSONL line (no newline).
sr_audit_planned() {
  sp_body=""; sp_sep=""
  while IFS= read -r sp_l; do
    [ -n "$sp_l" ] || continue
    srm_tsv_split "$sp_l"
    sp_body="$sp_body$sp_sep{\"path\":$(json_str "$TS_1"),\"kind\":$(json_str "$TS_2"),\"files\":$TS_3,\"bytes\":$TS_4,\"sha256\":$(json_str "$TS_5")}"
    sp_sep=","
  done < "$6"
  printf '{"schema":"safe-rm/1","op":"delete","phase":"planned","id":%s,"ts":%s,"user":%s,"agent":%s,"session":%s,"items":[%s]}' \
    "$(json_str "$1")" "$(json_str "$2")" "$(json_str "$3")" "$(json_str "$4")" "$(json_str "$5")" "$sp_body"
}

# ---- arguments ---------------------------------------------------------------------------------------------------
sr_recurse=0; sr_agent=""; sr_session=""; sr_policy=""; sr_dry=0; sr_dd=0
sr_n=$#; sr_i=0
while [ "$sr_i" -lt "$sr_n" ]; do
  sr_a=$1
  shift
  sr_i=$((sr_i + 1))
  if [ "$sr_dd" = 1 ]; then set -- "$@" "$sr_a"; continue; fi
  case "$sr_a" in
    -Recurse) sr_recurse=1 ;;
    -DryRun) sr_dry=1 ;;
    -Agent|-Session|-PolicyFile)
      if [ "$sr_i" -ge "$sr_n" ]; then printf 'REFUSED: missing value for %s\n' "$sr_a" >&2; exit 2; fi
      sr_v=$1
      shift
      sr_i=$((sr_i + 1))
      case "$sr_a" in
        -Agent) sr_agent=$sr_v ;;
        -Session) sr_session=$sr_v ;;
        *) sr_policy=$sr_v ;;
      esac
      ;;
    --) sr_dd=1 ;;
    -*) printf "REFUSED: unknown option '%s'\n" "$sr_a" >&2; exit 2 ;;
    *) set -- "$@" "$sr_a" ;;
  esac
done

SR_TMP=$(mktemp -d 2>/dev/null) || { echo 'ERROR: cannot create a temp folder' >&2; exit 3; }
trap 'rm -rf "$SR_TMP"' EXIT
trap 'exit 3' HUP INT TERM

if ! srm_load_policy "$sr_policy"; then printf 'ERROR: %s\n' "$SRM_REASON" >&2; exit 3; fi
if [ $# -eq 0 ]; then echo 'REFUSED: no path given' >&2; exit 2; fi
if ! srm_resolve "$sr_recurse" "$@"; then printf 'REFUSED: %s\n' "$SRM_REASON" >&2; exit 2; fi
if [ -z "$SRM_ITEMS" ]; then
  printf 'NOTHING TO DELETE. Skipped: %s\n' "$(srm_join_skipped)"
  exit 0
fi
printf '%s' "$SRM_ITEMS" > "$SR_TMP/items"

if [ "$sr_dry" = 1 ]; then
  while IFS= read -r sr_l; do
    [ -n "$sr_l" ] || continue
    srm_tsv_split "$sr_l"
    printf 'WOULD QUARANTINE %s (%s files, %s bytes)\n' "$TS_1" "$TS_4" "$TS_5"
  done < "$SR_TMP/items"
  exit 0
fi

# ---- identity, quarantine folder (unique: mkdir fails on a clash) ------------------------------------------------
sr_user=${USERNAME:-}
[ -n "$sr_user" ] || sr_user=${USER:-}
sr_ts=$(now_utc)
sr_qroot=$SRM_QUARANTINE_ROOT
if ! mkdir -p "$sr_qroot" 2>/dev/null; then
  echo 'REFUSED: could not write the audit record or manifest, so nothing was moved. (cannot create the quarantine folder)' >&2
  exit 2
fi
sr_try=0
while :; do
  sr_id=$(srm_make_id)
  if mkdir "$sr_qroot/$sr_id" 2>/dev/null; then break; fi
  sr_try=$((sr_try + 1))
  if [ "$sr_try" -ge 10 ]; then echo 'ERROR: cannot create a unique quarantine folder' >&2; exit 3; fi
done
sr_qdir="$sr_qroot/$sr_id"

# ---- hash everything first (files are capped, so this is bounded) -----------------------------------------------
: > "$SR_TMP/pending"
while IFS= read -r sr_l; do
  [ -n "$sr_l" ] || continue
  # items record: path TAB root TAB isdir TAB files TAB bytes
  srm_tsv_split "$sr_l"
  sr_src=$TS_1; sr_files=$TS_4; sr_bytes=$TS_5
  sr_dest="$sr_qdir/data$sr_src"
  if [ "$TS_3" = 1 ]; then
    sr_kind=dir
    sr_digest=$(srm_dir_digest "$sr_src")
  else
    sr_kind=file
    sr_digest=$(srm_sha256_file "$sr_src")
  fi
  if [ -z "$sr_digest" ]; then echo "ERROR: cannot hash '$sr_src'" >&2; exit 3; fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\tpending\t\n' "$sr_src" "$sr_kind" "$sr_files" "$sr_bytes" "$sr_digest" "$sr_dest" >> "$SR_TMP/pending"
done < "$SR_TMP/items"

# ---- record BEFORE moving; if the record cannot be written nothing is moved ---------------------------------------
if ! sr_manifest "$sr_qdir/manifest.json" "$sr_id" "$sr_ts" "$sr_user" "$sr_agent" "$sr_session" "$sr_recurse" pending "$SR_TMP/pending"; then
  echo 'REFUSED: could not write the audit record or manifest, so nothing was moved. (manifest write failed)' >&2
  exit 2
fi
sr_line=$(sr_audit_planned "$sr_id" "$sr_ts" "$sr_user" "$sr_agent" "$sr_session" "$SR_TMP/pending")
if ! append_line "$SRM_AUDIT_FILE" "$sr_line"; then
  echo 'REFUSED: could not write the audit record or manifest, so nothing was moved. (audit write failed)' >&2
  exit 2
fi

# ---- move --------------------------------------------------------------------------------------------------------
sr_failed=0
: > "$SR_TMP/final"
while IFS= read -r sr_l; do
  [ -n "$sr_l" ] || continue
  srm_tsv_split "$sr_l"
  sr_st=moved; sr_er=""
  if [ -e "$TS_6" ] || [ -L "$TS_6" ]; then
    sr_st=failed; sr_er="destination already exists"
  elif ! mkdir -p "${TS_6%/*}" 2>/dev/null; then
    sr_st=failed; sr_er="cannot create the quarantine folder"
  else
    if sr_out=$(mv -- "$TS_1" "$TS_6" 2>&1); then
      sr_st=moved
    else
      sr_st=failed
      sr_er=$(printf '%s' "$sr_out" | tr '\t\n' '  ')
    fi
  fi
  if [ "$sr_st" = failed ]; then sr_failed=$((sr_failed + 1)); fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$TS_1" "$TS_2" "$TS_3" "$TS_4" "$TS_5" "$TS_6" "$sr_st" "$sr_er" >> "$SR_TMP/final"
done < "$SR_TMP/pending"

sr_status=done
[ "$sr_failed" -eq 0 ] || sr_status=partial
if ! sr_manifest "$sr_qdir/manifest.json" "$sr_id" "$sr_ts" "$sr_user" "$sr_agent" "$sr_session" "$sr_recurse" "$sr_status" "$SR_TMP/final"; then
  echo "ERROR: could not rewrite the manifest in $sr_qdir" >&2
  exit 3
fi
awk -F "$SRM_TAB" '$7 == "moved" { print $1 }' "$SR_TMP/final" > "$SR_TMP/moved"
awk -F "$SRM_TAB" '$7 == "failed" { print $1 }' "$SR_TMP/final" > "$SR_TMP/failed"
sr_moved_json=$(srm_json_array < "$SR_TMP/moved")
sr_failed_json=$(srm_json_array < "$SR_TMP/failed")
sr_cline=$(printf '{"schema":"safe-rm/1","op":"delete","phase":"completed","id":%s,"ts":%s,"status":%s,"moved":%s,"failed":%s}' \
  "$(json_str "$sr_id")" "$(json_str "$(now_utc)")" "$(json_str "$sr_status")" "$sr_moved_json" "$sr_failed_json")
if ! append_line "$SRM_AUDIT_FILE" "$sr_cline"; then
  echo "ERROR: could not write the completion record for $sr_id" >&2
  exit 3
fi

sr_moved_count=$(awk -F "$SRM_TAB" '$7 == "moved" { n++ } END { print n + 0 }' "$SR_TMP/final")
printf 'QUARANTINED id=%s items=%s (restorable, not permanently deleted)\n' "$sr_id" "$sr_moved_count"
while IFS= read -r sr_l; do
  [ -n "$sr_l" ] || continue
  srm_tsv_split "$sr_l"
  case "$TS_7" in
    moved) sr_up=MOVED ;;
    failed) sr_up=FAILED ;;
    *) sr_up=PENDING ;;
  esac
  printf '  %s  %s (%s files, %s bytes)\n' "$sr_up" "$TS_1" "$TS_3" "$TS_4"
done < "$SR_TMP/final"
if [ -n "$SRM_SKIPPED" ]; then printf 'Skipped: %s\n' "$(srm_join_skipped)"; fi
if [ "$sr_failed" -gt 0 ]; then
  printf 'PARTIAL: %s item(s) could not be moved; see the manifest in %s\n' "$sr_failed" "$sr_qdir" >&2
  exit 3
fi
exit 0
