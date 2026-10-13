#!/bin/sh
# Operator tool behind /kit-doctor (agent-guards). POSIX sh port of kit-doctor.ps1 (same checks, output and exit codes).
# Read-only apart from one probe file per folder it test-writes (removed again).
# Checks: where KIT_DATA resolves and whether every candidate agrees, writability, policy files, policy drift (SHA-256 vs policy-changes.jsonl),
# recent hook errors, pending blocked requests, installed plugin versions. Prints [OK]/[WARN]/[FAIL] lines. Exit 1 if any FAIL.
#   kit-doctor.sh [-KitData <folder>]
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

TAB=$(printf '\t')
FAILS=0; WARNS=0

say() {
  printf '[%s] %s: %s\n' "$1" "$2" "$3"
  case "$1" in
    FAIL) FAILS=$((FAILS + 1)) ;;
    WARN) WARNS=$((WARNS + 1)) ;;
  esac
}
param_error() { printf 'kit-doctor: %s\n' "$1" >&2; exit 1; }

KITDATA_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    -KitData|-kitdata) [ $# -ge 2 ] || param_error "missing value for -KitData"; KITDATA_ARG="$2"; shift 2 ;;
    *) param_error "unknown argument: $1" ;;
  esac
done

TMP=$(mktemp -d 2>/dev/null) || { echo 'kit-doctor: cannot create a temp folder' >&2; exit 2; }
trap 'rm -rf "$TMP"' EXIT
trap 'exit 2' HUP INT TERM

# norm <path>: trailing slashes removed (backslashes are legal file-name characters on Linux and are kept).
norm() {
  _p="$1"
  while [ -n "$_p" ] && [ "${_p%/}" != "$_p" ]; do _p="${_p%/}"; done
  printf '%s' "$_p"
}

# epoch_of <ISO timestamp>: seconds since epoch (UTC when the stamp ends in Z or carries an offset); empty when unparseable.
epoch_of() {
  _t="$1"; _off=""
  case "$_t" in *Z) _off="+00:00" ;; esac
  if [ -z "$_off" ]; then
    _off=$(printf '%s' "$_t" | sed -n 's/.*\([+-][0-9][0-9]:\{0,1\}[0-9][0-9]\)$/\1/p')
  fi
  _base=$(printf '%s' "$_t" | cut -c1-19 | tr 'T' ' ')
  date -d "$_base $_off" +%s 2>/dev/null
}

# --- strict JSON validation in awk (same parser as kit-policy.sh; a malformed file is a FAIL, never silently accepted)
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

# last recorded change for file <want> in policy-changes.jsonl: "last<TAB>after_sha256" (or "null"), or "none".
AWK_LASTCHANGE=$(cat <<'AWKLAST'
BEGIN { RS = "\n" }
{
  s = $0
  if (!parse_doc()) next
  if (!("file" in TK) || TK["file"] != "string" || TV["file"] != want) next
  found = 1
  last = (("after_sha256" in TK) && TK["after_sha256"] == "string") ? TV["after_sha256"] : "null"
}
END { if (found) printf "last\t%s\n", last; else print "none" }
AWKLAST
)

# host-kind blocked request timestamps (one per line) from blocked-requests.jsonl lines.
AWK_HOSTTS=$(cat <<'AWKHT'
BEGIN { RS = "\n" }
{
  s = $0
  if (!parse_doc()) next
  if (!("kind" in TK) || TK["kind"] != "string" || tolower(TV["kind"]) != "host") next
  print (("ts" in TK) ? TV["ts"] : "")
}
AWKHT
)
AWK_VALIDATE="$AWK_LIB
$AWK_VALIDATE"
AWK_LASTCHANGE="$AWK_LIB
$AWK_LASTCHANGE"
AWK_HOSTTS="$AWK_LIB
$AWK_HOSTTS"

out_field() {
  awk -v key="$2" 'index($0, key "\t") == 1 { print substr($0, length(key) + 2); exit }' "$1"
}

# --- 1. KIT_DATA resolution: the same order every hook uses, plus the candidates that would be used if an env var were missing
CACHE_CFG=""
case "$KIT_SCRIPT_DIR" in */plugins/cache/*) CACHE_CFG="${KIT_SCRIPT_DIR%%/plugins/cache/*}" ;; esac

CANDS="$TMP/cands"; : > "$CANDS"
if [ -n "${AGENT_KIT_DATA:-}" ]; then
  printf 'AGENT_KIT_DATA\t%s\n' "$(norm "$AGENT_KIT_DATA")" >> "$CANDS"
fi
if [ -n "${CLAUDE_CONFIG_DIR:-}" ]; then
  printf 'CLAUDE_CONFIG_DIR\t%s/agent-kit\n' "$(norm "$CLAUDE_CONFIG_DIR")" >> "$CANDS"
fi
if [ -n "$CACHE_CFG" ]; then
  printf 'plugin cache path\t%s/agent-kit\n' "$(norm "$CACHE_CFG")" >> "$CANDS"
fi
printf 'HOME default\t%s/.claude/agent-kit\n' "$(norm "${HOME:-/root}")" >> "$CANDS"

if [ -n "$KITDATA_ARG" ]; then
  chosen=$(norm "$KITDATA_ARG")
else
  chosen=$(kit_data)
fi
say OK KIT_DATA "$chosen (first candidate in the hooks' resolution order)"

DISTINCT=$(cut -f2 "$CANDS" | awk '!seen[$0]++')
ndist=$(printf '%s\n' "$DISTINCT" | grep -c .)
if [ "$ndist" -gt 1 ]; then
  WITHDATA=""; nwith=0
  while IFS= read -r c; do
    [ -n "$c" ] || continue
    if [ -d "$c" ] && [ -n "$(find "$c" -type f 2>/dev/null | head -n 1)" ]; then
      nwith=$((nwith + 1))
      WITHDATA="${WITHDATA:+$WITHDATA | }$c"
    fi
  done <<EOF
$DISTINCT
EOF
  if [ "$nwith" -gt 1 ]; then
    say WARN 'KIT_DATA split' "more than one candidate folder holds data: $WITHDATA. Hooks and CLIs would disagree if their environment differs; consolidate or set AGENT_KIT_DATA."
  elif [ -z "${AGENT_KIT_DATA:-}" ] && [ -z "${CLAUDE_CONFIG_DIR:-}" ]; then
    cands_text=$(awk -F "$TAB" '{ printf "%s%s=%s", (NR > 1 ? "; " : ""), $1, $2 }' "$CANDS")
    say WARN environment "neither AGENT_KIT_DATA nor CLAUDE_CONFIG_DIR is set in this shell; candidates differ: $cands_text. Hooks inside Claude Code derive it from the plugin path; terminal tools would use the last one."
  fi
fi
if [ "${CLAUDE_CODE_SUBPROCESS_ENV_SCRUB:-}" = "1" ]; then
  say WARN environment 'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 removes CLAUDE_CONFIG_DIR from hooks; the plugin-path derivation covers this, but set AGENT_KIT_DATA to be explicit.'
fi

# --- 2. writable
for sub in '' audit usage verification-logs eval/inbox; do
  if [ -n "$sub" ]; then dir="$chosen/$sub"; else dir="$chosen"; fi
  probe="$dir/.doctor-probe-$$"
  if mkdir -p "$dir" 2>/dev/null && printf 'x' > "$probe" 2>/dev/null && rm -f "$probe" 2>/dev/null; then
    say OK writable "$dir"
  else
    say FAIL writable "$dir is not writable; audit and usage records would be lost"
  fi
done

# --- 3. policy files (parse and shape) and 4. drift against policy-changes.jsonl
CL="$chosen/audit/policy-changes.jsonl"
if [ -e "$chosen/verification-policy.json" ]; then
  say WARN verification-policy.json 'obsolete: the runner no longer has a command allowlist of its own (Claude Code permissions decide). The file is ignored; delete it when you no longer need it as a record.'
fi

for f in browser-policy.json safe-rm-policy.json; do
  p="$chosen/$f"
  if [ ! -e "$p" ]; then
    say OK "$f" 'absent (built-in defaults apply)'
    continue
  fi
  case "$f" in
    browser-policy.json) key=allowedHosts ;;
    *) key=allowedRoots ;;
  esac
  o="$TMP/out.$f"
  if ! LC_ALL=C awk -v want="$key" "$AWK_VALIDATE" "$p" > "$o" 2>/dev/null; then
    say FAIL "$f" 'not valid JSON (or its top level is not a JSON object)'
    continue
  fi
  kind=$(out_field "$o" KIND)
  case "$f" in
    browser-policy.json)
      case "$kind" in
        absent|null)
          say OK "$f" 'allowedHosts empty: every http(s) host is allowed' ;;
        array)
          nonnull=$(awk -F "$TAB" '$1 == "EL" && $2 != "null" { n++ } END { print n + 0 }' "$o")
          if [ "$nonnull" -eq 0 ]; then
            say OK "$f" 'allowedHosts empty: every http(s) host is allowed'
          else
            list=$(awk -F "$TAB" 'BEGIN { ORS = "" } $1 == "EL" { if (c++) printf ", "; if ($2 == "null") printf ""; else if ($2 == "object" || $2 == "array") printf "(%s)", $2; else printf "%s", $3 }' "$o")
            say OK "$f" "allowedHosts: $list"
          fi ;;
        object) say OK "$f" 'allowedHosts: (object)' ;;
        *) say OK "$f" "allowedHosts: $(out_field "$o" VAL)" ;;
      esac ;;
    safe-rm-policy.json)
      case "$kind" in
        absent|null)
          say WARN "$f" 'no allowedRoots: rm would be refused everywhere' ;;
        array)
          cnt=$(out_field "$o" COUNT)
          if [ "$cnt" -eq 0 ]; then
            say WARN "$f" 'no allowedRoots: rm would be refused everywhere'
          else
            say OK "$f" "$cnt allowed root(s)"
          fi ;;
        literal)
          if [ "$(out_field "$o" VAL)" = false ]; then say WARN "$f" 'no allowedRoots: rm would be refused everywhere'; else say OK "$f" '1 allowed root(s)'; fi ;;
        number)
          if [ "$(out_field "$o" VAL)" = 0 ]; then say WARN "$f" 'no allowedRoots: rm would be refused everywhere'; else say OK "$f" '1 allowed root(s)'; fi ;;
        string)
          if [ -z "$(out_field "$o" VAL)" ]; then say WARN "$f" 'no allowedRoots: rm would be refused everywhere'; else say OK "$f" '1 allowed root(s)'; fi ;;
        *) say OK "$f" '1 allowed root(s)' ;;
      esac ;;
  esac

  sha=$(sha256_of "$p")
  last=""
  if [ -e "$CL" ]; then
    last=$(LC_ALL=C awk -v want="$f" "$AWK_LASTCHANGE" "$CL" 2>/dev/null)
  fi
  [ -n "$last" ] || last=none
  rec=$(printf '%s' "$last" | cut -f2)
  if [ "$last" = none ]; then
    if [ "$f" != safe-rm-policy.json ]; then
      say WARN "$f integrity" "no change record: the file was never changed via /agent-guards:kit-allow (sha256 $(printf '%.12s' "$sha"))"
    fi
  elif [ "$rec" = "$sha" ]; then
    say OK "$f integrity" 'matches the last recorded change (policy-changes.jsonl)'
  else
    say WARN "$f integrity" "file differs from the last recorded change (recorded $(printf '%.12s' "$rec"), now $(printf '%.12s' "$sha")): edited outside /agent-guards:kit-allow. Review it, then record it with a reason if intended."
  fi
done

# --- 5. hook errors (last 24 h)
he="$chosen/hook-errors.log"
if [ -e "$he" ]; then
  cutoff=$(( $(date +%s) - 86400 ))
  tail -n 200 "$he" > "$TMP/he" 2>/dev/null
  recent=0; latest=""
  while IFS= read -r line; do
    ts=$(printf '%s\n' "$line" | sed -n 's/^\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}T[0-9:.+-]*\).*/\1/p')
    [ -n "$ts" ] || continue
    ep=$(epoch_of "$ts")
    [ -n "$ep" ] || continue
    if [ "$ep" -gt "$cutoff" ]; then
      recent=$((recent + 1))
      latest="$line"
    fi
  done < "$TMP/he"
  if [ "$recent" -gt 0 ]; then
    say WARN hook-errors.log "$recent error(s) in the last 24 h; latest: $latest"
  else
    say OK hook-errors.log 'no errors in the last 24 h'
  fi
else
  say OK hook-errors.log 'absent (no hook errors recorded)'
fi

# --- 6. pending blocked requests
bl="$chosen/audit/blocked-requests.jsonl"
if [ -e "$bl" ]; then
  cutoff=$(( $(date -u +%s) - 7 * 86400 ))
  tail -n 500 "$bl" > "$TMP/bl.in" 2>/dev/null
  LC_ALL=C awk "$AWK_HOSTTS" "$TMP/bl.in" > "$TMP/bl.ts" 2>/dev/null
  n=0
  while IFS= read -r t; do
    ep=$(epoch_of "$t")
    if [ -n "$ep" ] && [ "$ep" -gt "$cutoff" ]; then n=$((n + 1)); fi
  done < "$TMP/bl.ts"
  if [ "$n" -gt 0 ]; then
    say WARN 'blocked requests' "$n blocked host request(s) in the last 7 days; run /agent-guards:kit-allow to review"
  else
    say OK 'blocked requests' 'none in the last 7 days'
  fi
fi

# --- 7. installed plugin versions (stale session = restart needed)
if [ -n "$CACHE_CFG" ]; then
  root="$CACHE_CFG/plugins/cache/agent-kit"
  running=$(printf '%s' "$KIT_SCRIPT_DIR" | awk '{ if (match($0, /agent-kit[\/][^\/]+[\/][^\/]+[\/]scripts/)) { m = substr($0, RSTART, RLENGTH); split(m, p, "/"); print p[2] " " p[3] } }')
  rplug=$(printf '%s' "$running" | cut -d' ' -f1)
  rver=$(printf '%s' "$running" | cut -d' ' -f2)
  for pl in haiku-delegation agent-guards agent-eval verification-runner; do
    vd="$root/$pl"
    if [ ! -d "$vd" ]; then
      say WARN "plugin $pl" 'not installed from agent-kit'
      continue
    fi
    newest=$(for d in "$vd"/*/; do [ -d "$d" ] && basename "$d"; done | sort -V | tail -n 1)
    if [ -n "$rplug" ] && [ "$rplug" = "$pl" ] && [ "$rver" != "$newest" ]; then
      say WARN "plugin $pl" "this session runs $rver but $newest is installed: restart Claude Code"
    else
      say OK "plugin $pl" "newest installed ${newest:-none}"
    fi
  done
fi

printf 'Summary: %s FAIL, %s WARN\n' "$FAILS" "$WARNS"
if [ "$FAILS" -gt 0 ]; then exit 1; fi
exit 0
