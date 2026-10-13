#!/bin/sh
# safe-rm-restore.sh - for YOU (not agents). Lists quarantined deletions and restores one back to its original place
# (POSIX sh port of safe-rm-restore.ps1).
#   sh safe-rm-restore.sh -List
#   sh safe-rm-restore.sh -Id <id>
# Restore refuses to overwrite anything that exists at the original path. Purging = deleting a folder under the quarantine root yourself.
# Exit codes: 0 ok, 1 policy or internal error, 2 refused (bad id, no such entry), 3 one or more problems (see stderr).
LC_ALL=C
export LC_ALL
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"
. "$KIT_SCRIPT_DIR/safe-rm-lib.sh"

sx_list=0; sx_id=""; sx_policy=""
while [ $# -gt 0 ]; do
  case "$1" in
    -List) sx_list=1; shift ;;
    -Id)
      [ $# -ge 2 ] || { echo 'REFUSED: missing value for -Id' >&2; exit 2; }
      sx_id=$2; shift 2 ;;
    -PolicyFile)
      [ $# -ge 2 ] || { echo 'REFUSED: missing value for -PolicyFile' >&2; exit 2; }
      sx_policy=$2; shift 2 ;;
    *) printf "REFUSED: unknown argument '%s'\n" "$1" >&2; exit 2 ;;
  esac
done

if ! srm_load_policy "$sx_policy"; then printf 'ERROR: %s\n' "$SRM_REASON" >&2; exit 1; fi

if [ "$sx_list" = 1 ] || [ -z "$sx_id" ]; then
  if [ ! -d "$SRM_QUARANTINE_ROOT" ]; then echo 'Quarantine is empty.'; exit 0; fi
  for sx_d in "$SRM_QUARANTINE_ROOT"/*/; do
    [ -d "$sx_d" ] || continue
    sx_mf="${sx_d}manifest.json"
    [ -f "$sx_mf" ] || continue
    sx_j=$(cat "$sx_mf" 2>/dev/null) || continue
    sx_mid=$(json_get "$sx_j" id) || sx_mid=""
    sx_mts=$(json_get "$sx_j" ts) || sx_mts=""
    sx_mag=$(json_get "$sx_j" agent) || sx_mag=""
    sx_mst=$(json_get "$sx_j" status) || sx_mst=""
    sx_cnt=0
    while json_has "$sx_j" "items.$sx_cnt.path"; do sx_cnt=$((sx_cnt + 1)); done
    sx_first=$(json_get "$sx_j" items.0.path) || sx_first=""
    printf '%s  %s  agent=%s  items=%s  status=%s  e.g. %s\n' "$sx_mid" "$sx_mts" "$sx_mag" "$sx_cnt" "$sx_mst" "$sx_first"
  done
  exit 0
fi

if [ "${#sx_id}" -ne 23 ] || ! printf '%s' "$sx_id" | grep -Eq '^[0-9]{8}T[0-9]{9}-[0-9a-f]{4}$'; then
  echo 'Invalid id.' >&2
  exit 2
fi
sx_qdir="$SRM_QUARANTINE_ROOT/$sx_id"
sx_mf="$sx_qdir/manifest.json"
if [ ! -f "$sx_mf" ]; then printf 'No such quarantine entry: %s\n' "$sx_id" >&2; exit 2; fi
sx_json=$(cat "$sx_mf" 2>/dev/null) || { echo "ERROR: cannot read $sx_mf" >&2; exit 1; }

sx_tmp=$(mktemp -d 2>/dev/null) || { echo 'ERROR: cannot create a temp folder' >&2; exit 1; }
trap 'rm -rf "$sx_tmp"' EXIT
trap 'exit 1' HUP INT TERM
: > "$sx_tmp/restored"
: > "$sx_tmp/problems"

sx_k=0
while json_has "$sx_json" "items.$sx_k.path"; do
  sx_path=$(json_get "$sx_json" "items.$sx_k.path") || sx_path=""
  sx_qp=$(json_get "$sx_json" "items.$sx_k.quarantinePath") || sx_qp=""
  sx_st=$(json_get "$sx_json" "items.$sx_k.status") || sx_st=""
  sx_k=$((sx_k + 1))
  [ "$sx_st" = moved ] || continue
  case "$sx_path" in
    /*) ;;
    *) printf 'invalid original path in manifest: %s\n' "$sx_path" >> "$sx_tmp/problems"; continue ;;
  esac
  case "$sx_qp" in
    "$sx_qdir"/*) ;;
    *) printf 'quarantine path outside the entry: %s\n' "$sx_qp" >> "$sx_tmp/problems"; continue ;;
  esac
  if [ -e "$sx_path" ] || [ -L "$sx_path" ]; then
    printf 'exists, not overwritten: %s\n' "$sx_path" >> "$sx_tmp/problems"; continue
  fi
  if [ ! -e "$sx_qp" ] && [ ! -L "$sx_qp" ]; then
    printf 'missing in quarantine: %s\n' "$sx_qp" >> "$sx_tmp/problems"; continue
  fi
  sx_par=${sx_path%/*}
  [ -n "$sx_par" ] || sx_par=/
  if ! mkdir -p "$sx_par" 2>/dev/null; then
    printf 'cannot create the folder of: %s\n' "$sx_path" >> "$sx_tmp/problems"; continue
  fi
  if mv -- "$sx_qp" "$sx_path" 2>/dev/null; then
    printf '%s\n' "$sx_path" >> "$sx_tmp/restored"
  else
    printf 'could not move back: %s\n' "$sx_path" >> "$sx_tmp/problems"
  fi
done

sx_user=${USERNAME:-}
[ -n "$sx_user" ] || sx_user=${USER:-}
sx_restored_json=$(srm_json_array < "$sx_tmp/restored")
sx_problems_json=$(srm_json_array < "$sx_tmp/problems")
sx_line=$(printf '{"schema":"safe-rm/1","op":"restore","id":%s,"ts":%s,"user":%s,"restored":%s,"problems":%s}' \
  "$(json_str "$sx_id")" "$(json_str "$(now_utc)")" "$(json_str "$sx_user")" "$sx_restored_json" "$sx_problems_json")
if ! append_line "$SRM_AUDIT_FILE" "$sx_line"; then
  echo 'ERROR: could not write the restore audit record' >&2
  exit 1
fi

while IFS= read -r sx_l; do
  [ -n "$sx_l" ] || continue
  printf 'RESTORED %s\n' "$sx_l"
done < "$sx_tmp/restored"
if [ -s "$sx_tmp/problems" ]; then
  while IFS= read -r sx_l; do
    [ -n "$sx_l" ] || continue
    printf 'PROBLEM: %s\n' "$sx_l" >&2
  done < "$sx_tmp/problems"
  exit 3
fi
exit 0
