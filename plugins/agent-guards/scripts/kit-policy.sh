#!/bin/sh
# Operator tool behind /kit-allow (agent-guards). Records a USER-APPROVED change to the browser host allowlist,
# never an agent's own decision. POSIX sh port of kit-policy.ps1 (same flags, stdout, stderr, files and exit codes).
#   kit-policy.sh -Action list-blocked [-Max 20]
#   kit-policy.sh -Action add-host -HostName docs.example.com -Reason "..."
#   kit-policy.sh -Action show
# Commands for the verification-runner are NOT managed here: Claude Code's own permissions (settings allow / ask / deny rules) decide those.
# Every change appends one line to <KIT_DATA>/audit/policy-changes.jsonl (who, when, why, SHA-256 of the file before and after).
# Policy file: <KIT_DATA>/browser-policy.json (allowedHosts). Only the allowedHosts value is rewritten; other keys are kept byte for byte.
# Exit codes: 0 ok, 1 refused (bad input), 2 internal error.
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

TAB=$(printf '\t')

refuse() { printf 'REFUSED: %s\n' "$1" >&2; exit 1; }
fail_internal() { printf 'kit-policy failed: %s\n' "$1" >&2; exit 2; }
param_error() { printf 'kit-policy: %s\n' "$1" >&2; exit 1; }

# --- parameters (PowerShell-style -Name value; a bad parameter exits 1 like a PowerShell binding error)
ACTION=""; HOSTNAME_ARG=""; REASON=""; MAX=20
while [ $# -gt 0 ]; do
  case "$1" in
    -Action|-action)     [ $# -ge 2 ] || param_error "missing value for -Action";     ACTION="$2"; shift 2 ;;
    -HostName|-hostname) [ $# -ge 2 ] || param_error "missing value for -HostName"; HOSTNAME_ARG="$2"; shift 2 ;;
    -Reason|-reason)     [ $# -ge 2 ] || param_error "missing value for -Reason";    REASON="$2"; shift 2 ;;
    -Max|-max)           [ $# -ge 2 ] || param_error "missing value for -Max";      MAX="$2"; shift 2 ;;
    *) param_error "unknown argument: $1" ;;
  esac
done
case "$ACTION" in
  list-blocked|add-host|show) ;;
  '') param_error "-Action is required (list-blocked, add-host or show)" ;;
  *) param_error "-Action '$ACTION' is not one of list-blocked, add-host, show" ;;
esac
case "$MAX" in ''|*[!0-9]*) param_error "-Max must be a non-negative integer" ;; esac

TMP=$(mktemp -d 2>/dev/null) || fail_internal "cannot create a temp folder"
trap 'rm -rf "$TMP"' EXIT
trap 'exit 2' HUP INT TERM

KIT=$(kit_data)

# --- strict JSON validation in awk (mawk, byte mode). Shared parser: parse_doc() fills TK/TV/TS/TE for top-level members,
# --- EC/EL_T/EL_V for top-level arrays. Any syntax error, duplicate top-level key or non-object root fails.
AWK_LIB=$(cat <<'AWKLIB'
BEGIN {
  for (k = 1; k < 32; k++) CTL[sprintf("%c", k)] = 1
  HEX = "0123456789abcdef"
  BOM = sprintf("%c%c%c", 239, 187, 191)
}
function ws() {
  while (i <= n && substr(s, i, 1) ~ /[ \t\r\n]/) i++
}
function ishex4(h) {
  return (h ~ /^[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]$/)
}
function hexv(h,   k, v) {
  v = 0; h = tolower(h)
  for (k = 1; k <= 4; k++) v = v * 16 + index(HEX, substr(h, k, 1)) - 1
  return v
}
function chr(u) {
  if (u < 128) return sprintf("%c", u)
  if (u < 2048) return sprintf("%c%c", 192 + int(u / 64), 128 + u % 64)
  return sprintf("%c%c%c", 224 + int(u / 4096), 128 + int(u / 64) % 64, 128 + u % 64)
}
function pstr(   r, c, e, h, u, lh, lo) {
  r = ""; i++
  while (i <= n) {
    c = substr(s, i, 1)
    if (c == "\"") { i++; sv = r; return 1 }
    if (c in CTL) return 0
    if (c != "\\") { r = r c; i++; continue }
    e = substr(s, i + 1, 1); i += 2
    if (e == "\"" || e == "\\" || e == "/") { r = r e }
    else if (e == "n") { r = r "\n" }
    else if (e == "t") { r = r "\t" }
    else if (e == "r") { r = r "\r" }
    else if (e == "b") { r = r "\b" }
    else if (e == "f") { r = r "\f" }
    else if (e == "u") {
      h = substr(s, i, 4)
      if (!ishex4(h)) return 0
      i += 4; u = hexv(h)
      if (u >= 55296 && u <= 56319) {
        if (substr(s, i, 2) != "\\u") return 0
        lh = substr(s, i + 2, 4)
        if (!ishex4(lh)) return 0
        lo = hexv(lh)
        if (lo < 56320 || lo > 57343) return 0
        i += 6
        u = 65536 + (u - 55296) * 1024 + (lo - 56320)
        r = r sprintf("%c%c%c%c", 240 + int(u / 262144), 128 + int(u / 4096) % 64, 128 + int(u / 64) % 64, 128 + u % 64)
      } else if (u >= 56320 && u <= 57343) {
        return 0
      } else if (u == 0) {
        return 0
      } else {
        r = r chr(u)
      }
    }
    else return 0
  }
  return 0
}
function pnum(   st, t) {
  st = i
  while (i <= n && substr(s, i, 1) ~ /[-+.0-9eE]/) i++
  t = substr(s, st, i - st)
  sv = t
  return (t ~ /^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$/)
}
function pval(ck,   c, ok) {
  ws()
  if (i > n) return 0
  c = substr(s, i, 1)
  if (c == "{") { ok = pobj(0); vt = "object"; sv = ""; return ok }
  if (c == "[") { ok = parr(ck); vt = "array"; sv = ""; return ok }
  if (c == "\"") { ok = pstr(); vt = "string"; return ok }
  if (c == "-" || c ~ /[0-9]/) { ok = pnum(); vt = "number"; return ok }
  if (substr(s, i, 4) == "true") { i += 4; vt = "literal"; sv = "true"; return 1 }
  if (substr(s, i, 5) == "false") { i += 5; vt = "literal"; sv = "false"; return 1 }
  if (substr(s, i, 4) == "null") { i += 4; vt = "null"; sv = ""; return 1 }
  return 0
}
function pobj(top,   key, c, st) {
  i++; ws()
  if (substr(s, i, 1) == "}") { i++; return 1 }
  while (i <= n) {
    ws()
    if (substr(s, i, 1) != "\"") return 0
    if (!pstr()) return 0
    key = sv
    ws()
    if (substr(s, i, 1) != ":") return 0
    i++
    ws()
    st = i
    if (top) {
      if (key in SEEN) return 0
      SEEN[key] = 1
    }
    if (!pval(top ? key : "")) return 0
    if (top) { TK[key] = vt; TV[key] = sv; TS[key] = st; TE[key] = i }
    ws()
    c = substr(s, i, 1); i++
    if (c == "}") return 1
    if (c != ",") return 0
  }
  return 0
}
function parr(ck,   idx, c) {
  i++; ws()
  if (substr(s, i, 1) == "]") { i++; if (ck != "") EC[ck] = 0; return 1 }
  idx = 0
  while (i <= n) {
    if (!pval("")) return 0
    if (ck != "") { EL_T[ck, idx] = vt; EL_V[ck, idx] = sv }
    idx++
    ws()
    c = substr(s, i, 1); i++
    if (c == "]") { if (ck != "") EC[ck] = idx; return 1 }
    if (c != ",") return 0
  }
  return 0
}
function parse_doc() {
  split("", SEEN); split("", TK); split("", TV); split("", TS); split("", TE)
  split("", EC); split("", EL_T); split("", EL_V)
  n = length(s); i = 1
  if (substr(s, 1, 3) == BOM) i = 4
  ws()
  if (substr(s, i, 1) != "{") return 0
  if (!pobj(1)) return 0
  ws()
  return (i > n) ? 1 : 0
}
AWKLIB
)

# Whole-file validation. Output lines: KIND, SPAN (byte span of the value), VAL (scalar), COUNT and EL (array items).
AWK_VALIDATE=$(cat <<'AWKVAL'
BEGIN { RS = "\001" }
{ s = $0; ok = (NR == 1) && parse_doc() }
END {
  if (!ok) exit 1
  if (want in TK) {
    print "KIND\t" TK[want]
    print "SPAN\t" TS[want] "\t" TE[want]
    if (TK[want] != "array") print "VAL\t" TV[want]
  } else {
    print "KIND\tabsent"
  }
  if (want in EC) {
    print "COUNT\t" EC[want]
    for (k = 0; k < EC[want]; k++) {
      t = EL_T[want, k]; v = EL_V[want, k]
      if (t == "string") { for (c in CTL) { if (index(v, c) > 0) { t = "ctl"; break } } }
      print "EL\t" t "\t" v
    }
  }
}
AWKVAL
)

# list-blocked: one JSON object per line; keeps host blocks not yet allowed; groups case-insensitively.
# Output per group: lastTs, firstIndex, rendered line (sorted later: ts descending, first occurrence ascending).
AWK_LIST=$(cat <<'AWKLST'
BEGIN {
  RS = "\n"
  while ((getline line < allowfile) > 0) ALLOW[line] = 1
  close(allowfile)
}
{
  s = $0
  if (!parse_doc()) next
  if (!("kind" in TK) || TK["kind"] != "string" || tolower(TV["kind"]) != "host") next
  v = ("value" in TK) ? TV["value"] : ""
  key = tolower(v)
  if (key in ALLOW) next
  ts = ("ts" in TK) ? TV["ts"] : ""
  ag = ("agent" in TK) ? TV["agent"] : ""
  gsub(/[\t\r\n]/, " ", v); gsub(/[\t\r\n]/, " ", ts); gsub(/[\t\r\n]/, " ", ag)
  if (!(key in CNT)) { m++; ORDER[m] = key; FIRST[key] = m; CNT[key] = 0 }
  CNT[key]++; LV[key] = v; LTS[key] = ts; LAG[key] = ag
}
END {
  for (q = 1; q <= m; q++) {
    key = ORDER[q]
    printf "%s\t%d\t[host] %s   (x%d, last %s, agent %s)\n", LTS[key], FIRST[key], LV[key], CNT[key], LTS[key], LAG[key]
  }
}
AWKLST
)
AWK_VALIDATE="$AWK_LIB
$AWK_VALIDATE"
AWK_LIST="$AWK_LIB
$AWK_LIST"

# policy_check <file> <key> <out>  strict validation; the output file gets the KIND/SPAN/VAL/COUNT/EL lines.
policy_check() {
  LC_ALL=C awk -v want="$2" "$AWK_VALIDATE" "$1" > "$3" 2>/dev/null
}
# out_field <out-file> <LABEL>  prints the text after "LABEL<TAB>" (first match).
out_field() {
  awk -v key="$2" 'index($0, key "\t") == 1 { print substr($0, length(key) + 2); exit }' "$1"
}
# json_or_null <text>  JSON string literal, or null when empty.
json_or_null() {
  if [ -n "$1" ]; then json_str "$1"; else printf 'null'; fi
}

show_policy() {
  p="$KIT/browser-policy.json"
  printf '== %s  sha256=%s\n' "$p" "$(sha256_of "$p")"
  if [ -e "$p" ]; then cat "$p"; else echo '(absent)'; fi
}

list_blocked() {
  log="$KIT/audit/blocked-requests.jsonl"
  if [ ! -e "$log" ]; then echo 'No blocked requests recorded.'; return 0; fi
  pol="$KIT/browser-policy.json"
  : > "$TMP/allow"
  if [ -e "$pol" ]; then
    policy_check "$pol" allowedHosts "$TMP/pol" || refuse "$pol is not valid JSON; fix or remove it first"
    awk -F "$TAB" '$1 == "EL" && $2 == "string" && $3 != "" { print $3 }' "$TMP/pol" | tr 'A-Z' 'a-z' > "$TMP/allow"
  fi
  tail -n 500 "$log" > "$TMP/log" 2>/dev/null || fail_internal "cannot read $log"
  LC_ALL=C awk -v allowfile="$TMP/allow" "$AWK_LIST" "$TMP/log" > "$TMP/rows" 2>/dev/null || fail_internal "cannot parse $log"
  rows=$(LC_ALL=C sort -t "$TAB" -k1,1r -k2,2n "$TMP/rows" | head -n "$MAX" | cut -f3-)
  if [ -z "$rows" ]; then
    echo 'No pending blocked hosts (all recorded ones are already allowed).'
    return 0
  fi
  printf '%s\n' "$rows" | awk '{ print NR ". " $0 }'
}

add_host() {
  h=$(printf '%s' "$HOSTNAME_ARG" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | tr 'A-Z' 'a-z')
  if [ -z "$REASON" ]; then refuse '-Reason is required: say why this host is needed.'; fi
  if ! printf '%s\n' "$h" | grep -Eq '^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$'; then
    refuse "host '$h' is not a plain host name (no scheme, port, path or wildcard)."
  fi
  case "$h" in *..*) refuse "host '$h' is not a plain host name (no scheme, port, path or wildcard)." ;; esac

  path="$KIT/browser-policy.json"
  if [ -e "$path" ]; then
    policy_check "$path" allowedHosts "$TMP/pol" || refuse "$path is not valid JSON; fix or remove it first"
    kind=$(out_field "$TMP/pol" KIND)
  else
    kind=absent
  fi
  case "$kind" in
    absent|null)
      refuse 'browser-policy.json has no allowedHosts, which means every host is already allowed; adding one would RESTRICT the browser agents to it. Create the list deliberately by hand if you want a restriction.' ;;
    array) ;;
    *) refuse "allowedHosts in $path is not an array; fix the file by hand first." ;;
  esac

  bad=$(awk -F "$TAB" '$1 == "EL" && $2 != "string" && $2 != "null" { print $2; exit }' "$TMP/pol")
  if [ -n "$bad" ]; then
    refuse "allowedHosts in $path has an entry that is not a plain string ($bad); fix the file by hand first."
  fi
  awk -F "$TAB" '$1 == "EL" && $2 == "string" && $3 != "" { print $3 }' "$TMP/pol" | tr 'A-Z' 'a-z' > "$TMP/hosts"
  if [ ! -s "$TMP/hosts" ]; then
    refuse 'browser-policy.json has no allowedHosts, which means every host is already allowed; adding one would RESTRICT the browser agents to it. Create the list deliberately by hand if you want a restriction.'
  fi
  if grep -Fxq -- "$h" "$TMP/hosts"; then
    echo "Already allowed: $h"
    return 0
  fi

  before=$(sha256_of "$path")
  start=$(out_field "$TMP/pol" SPAN | cut -f1)
  end=$(out_field "$TMP/pol" SPAN | cut -f2)
  arr='['; sep=''
  while IFS= read -r v; do
    arr="$arr$sep$(json_str "$v")"
    sep=', '
  done < "$TMP/hosts"
  arr="$arr$sep$(json_str "$h")]"

  tmpf="$path.tmp"
  if ! { head -c "$((start - 1))" "$path" && printf '%s' "$arr" && tail -c "+$end" "$path"; } > "$tmpf" 2>/dev/null; then
    rm -f "$tmpf"
    fail_internal "cannot write $tmpf"
  fi
  if ! policy_check "$tmpf" allowedHosts "$TMP/check"; then
    rm -f "$tmpf"
    fail_internal "rewritten policy failed validation; $path left unchanged"
  fi
  mv -f "$tmpf" "$path" || fail_internal "cannot replace $path"
  after=$(sha256_of "$path")

  actor="${USERNAME:-${USER:-$(id -un 2>/dev/null)}}"
  rec=$(printf '{"ts":%s,"actor":%s,"action":"add-host","file":"browser-policy.json","before_sha256":%s,"after_sha256":%s,"entry":{"host":%s},"reason":%s,"approved":"user confirmed in chat"}' \
    "$(json_str "$(now_utc)")" "$(json_str "$actor")" "$(json_or_null "$before")" "$(json_or_null "$after")" \
    "$(json_str "$h")" "$(json_str "$REASON")")
  append_line "$KIT/audit/policy-changes.jsonl" "$rec" || fail_internal "cannot append to $KIT/audit/policy-changes.jsonl (the policy file WAS changed)"
  echo "Allowed host (browser agents): $h"
}

case "$ACTION" in
  show) show_policy ;;
  list-blocked) list_blocked ;;
  add-host) add_host ;;
esac
exit 0
