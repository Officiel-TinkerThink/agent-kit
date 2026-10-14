#!/bin/sh
# PreToolUse hook (matcher: SubagentHandback|WebFetch|WebSearch). Deterministic secret-leak gate for subagents.
# POSIX sh port of guard-secret-leak.ps1 (same behaviour, stdin/stdout/stderr contract and exit codes).
#  * SubagentHandback (the ONLY way a subagent's answer reaches the main model): secret values are REDACTED from the message
#    (updatedInput), whether they match a known credential format OR equal a secret-looking value the agent itself read in
#    this run (taint taken from its transcript).
#  * WebFetch / WebSearch: a call whose URL, query or prompt contains such a value is BLOCKED (exit 2).
# Audit: <kit data>/audit/secret-guard-audit.jsonl records agent, tool, count and KINDS only. It never stores a secret value.
# Known limits: as the ps1 (values with no recognisable format outside key=value / flag / URL-credential / CLI-positional
# shapes are not detected; pure lowercase values of 9 characters or fewer are ordinary words; redaction is exact-match).
# Lookbehinds of the ps1 are emulated by checking the character before each match. Matching is byte-based (mawk, C locale).
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"
set -f

SELFTEST=""
while [ $# -gt 0 ]; do
  case "$1" in
    -SelfTestInput|-selftestinput)
      if [ $# -lt 2 ]; then break; fi
      SELFTEST="$2"
      shift 2 ;;
    *) shift ;;
  esac
done

if [ -n "$SELFTEST" ]; then
  INPUT=$(cat -- "$SELFTEST" 2>/dev/null) || exit 0
else
  INPUT=$(cat) || exit 0
fi
_compact=$(printf '%s' "$INPUT" | tr -d ' \t\r\n')
case "$_compact" in
  "{"*"}") ;;
  *) exit 0 ;;
esac

TMPD=$(mktemp -d "${TMPDIR:-/tmp}/secret-guard.XXXXXX" 2>/dev/null) || TMPD=""
trap '[ -n "$TMPD" ] && rm -rf "$TMPD"' 0

# get_field <dotted.path>: decoded value of a hook-input field ("" when absent).
get_field() { json_get "$INPUT" "$1" 2>/dev/null || true; }

fail_closed() {
  printf '%s\n' "BLOCKED by secret-guard: internal error while checking the answer ($1); the answer was withheld. Retry the hand-back with the answer shortened to path:line references only." >&2
  exit 2
}

# safe_seg <name>: a transcript path segment must not escape its folder.
safe_seg() {
  case "$1" in
    ''|.|..|*/*) return 1 ;;
  esac
  return 0
}

# taint_path: prints the agent transcript path when it exists (agent id, session id and transcript_path all present).
taint_path() {
  _tp=$(get_field transcript_path)
  _aid=$(get_field agent_id)
  _sid=$(get_field session_id)
  [ -n "$_tp" ] && [ -n "$_aid" ] && [ -n "$_sid" ] || return 0
  safe_seg "$_aid" && safe_seg "$_sid" || return 0
  case "$_tp" in
    */*) _dir="${_tp%/*}" ;;
    *) _dir="." ;;
  esac
  [ -n "$_dir" ] || _dir="/"
  _cand="$_dir/$_sid/subagents/agent-$_aid.jsonl"
  if [ -f "$_cand" ]; then printf '%s' "$_cand"; fi
  return 0
}

# audit_write <tool> <count> <action> <kinds: newline-separated list>
audit_write() {
  _af="${SECRET_GUARD_AUDIT:-}"
  [ -n "$_af" ] || _af="$(kit_data)/audit/secret-guard-audit.jsonl"
  _kj="["
  _ks=""
  for _k in $4; do
    _kj="$_kj$_ks$(json_str "$_k")"
    _ks=","
  done
  _kj="$_kj]"
  _rec=$(printf '{"schema":"secret-guard/1","ts":%s,"session_id":%s,"agent_id":%s,"agent_type":%s,"tool":%s,"action":%s,"count":%s,"kinds":%s}' \
    "$(json_str "$(now_utc)")" "$(json_str "$AUD_SID")" "$(json_str "$AUD_AID")" "$(json_str "$AUD_ATYPE")" \
    "$(json_str "$1")" "$(json_str "$3")" "$2" "$_kj")
  append_line "$_af" "$_rec" || hook_error "guard-secret-leak" "audit write failed: $_af"
}

# scan_run <mode: handback|web> <transcript path or ""> <message file> <redacted output file>
# Writes the awk report to $TMPD/scan.out: "COUNT n" then one "KIND k" line per matched value. Values never leave awk.
scan_run() {
  SG_MODE="$1" SG_TX="$2" SG_MSG="$3" SG_OUT="$4" awk "$SG_PROG" > "$TMPD/scan.out" 2> "$TMPD/scan.err"
}

# read_scan: sets SCAN_CNT (integer) and SCAN_KINDS (sorted, unique, newline-separated). Returns 1 when the report is malformed.
read_scan() {
  SCAN_CNT=$(sed -n 's/^COUNT //p' "$TMPD/scan.out" | head -n 1)
  case "$SCAN_CNT" in
    ''|*[!0-9]*) return 1 ;;
  esac
  SCAN_KINDS=$(sed -n 's/^KIND //p' "$TMPD/scan.out" | LC_ALL=C sort -u)
  return 0
}

handback() {
  _msg=$(get_field tool_input.message)
  if [ -z "$_msg" ]; then exit 0; fi
  [ -n "$TMPD" ] || fail_closed "no temp folder"
  printf '%s' "$_msg" > "$TMPD/msg" || fail_closed "cannot write the message to a temp file"
  _tx=$(taint_path)
  scan_run handback "$_tx" "$TMPD/msg" "$TMPD/redacted" || fail_closed "secret scan failed"
  read_scan || fail_closed "malformed secret scan report"
  if [ "$SCAN_CNT" -eq 0 ]; then exit 0; fi

  _toolin=$(get_field tool_input)
  printf '%s' "$_toolin" > "$TMPD/toolin" || fail_closed "cannot write tool input to a temp file"
  json_str "$(cat "$TMPD/redacted")" > "$TMPD/repl" || fail_closed "cannot encode the redacted answer"
  _ui=$(SG_IN="$TMPD/toolin" SG_REPL="$TMPD/repl" awk "$SPLICE_PROG") || fail_closed "cannot splice updatedInput"
  if [ -z "$_ui" ]; then fail_closed "cannot splice updatedInput"; fi

  audit_write "$1" "$SCAN_CNT" redacted "$SCAN_KINDS"
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"secret-guard: secret values redacted","updatedInput":%s}}\n' "$_ui"
  exit 0
}

web_check() {
  _url=$(get_field tool_input.url)
  _query=$(get_field tool_input.query)
  _prompt=$(get_field tool_input.prompt)
  [ -n "$TMPD" ] || exit 0
  printf '%s\n%s\n%s' "$_url" "$_query" "$_prompt" > "$TMPD/msg" || exit 0
  _tx=$(taint_path)
  scan_run web "$_tx" "$TMPD/msg" "$TMPD/unused" || exit 0
  read_scan || exit 0
  if [ "$SCAN_CNT" -eq 0 ]; then exit 0; fi

  _kjoin=$(printf '%s\n' "$SCAN_KINDS" | awk 'NF { printf "%s%s", (n++ ? ", " : ""), $0 }')
  audit_write "$1" "$SCAN_CNT" blocked "$SCAN_KINDS"
  printf 'BLOCKED by secret-guard: this %s call contains %s value(s) that look like credentials (%s). Remove them and retry; credentials must never be sent to a web service.\n' \
    "$1" "$SCAN_CNT" "$_kjoin" >&2
  exit 2
}

AUD_SID=$(get_field session_id)
AUD_AID=$(get_field agent_id)
AUD_ATYPE=$(get_field agent_type)
TOOL=$(get_field tool_name)

# ---- awk programs (heredocs keep every regex character literal) --------------------------------------------------------
# Scanner. Reads the message file (and, when SG_TX is set, the agent transcript for taint). Emits COUNT / KIND lines.
SG_PROG=$(cat <<'AWKPROG'
function ci(w,   r, k, c) {
  r = ""
  for (k = 1; k <= length(w); k++) {
    c = substr(w, k, 1)
    if (c ~ /[A-Za-z]/) r = r "[" toupper(c) tolower(c) "]"
    else r = r c
  }
  return r
}
# ge: the regex for "x repeated at least n times" (mawk 1.3.4 does not accept the open interval x{n,}).
function ge(x, n,   r, k) {
  r = ""
  for (k = 1; k <= n; k++) r = r x
  return r x "*"
}
function trimv(v) {
  sub("^[" WS "]+", "", v)
  sub("[" WS "]+$", "", v)
  while (v != "" && index(".,)]}", substr(v, length(v), 1)) > 0) v = substr(v, 1, length(v) - 1)
  return v
}
function worth(v) {
  if (length(v) < 6) return 0
  if (v ~ /^[a-z]+$/ && length(v) <= 9) return 0
  if (v ~ /^[0-9a-fA-F]+$/ && length(v) >= 32) return 0
  return 1
}
function isref(v) {
  if (v ~ /^([$]|[{][{]|<|%|@[(])/) return 1
  if (v ~ REF1) return 1
  if (index(v, "${") > 0 || index(v, "{{") > 0) return 1
  if (v ~ REF2) return 1
  if (v ~ REF3) return 1
  if (v ~ /^[A-Za-z_][A-Za-z0-9_.]*</) return 1   # a generic type such as Record<string, ...> or Promise<void>, not a value
  return 0
}
# addv: trim, then keep the value when it is worth redacting and not a reference. Later assignments overwrite the kind.
function addv(tid, v, k) {
  v = trimv(v)
  if (worth(v) && !isref(v)) F[tid SUBSEP v] = k
}
# fnd: first match of re at or after absolute position p; sets MS (absolute start) and ML (length).
function fnd(t, re, p) {
  if (p > length(t)) return 0
  if (match(substr(t, p), re)) { MS = p + RSTART - 1; ML = RLENGTH; return 1 }
  return 0
}
function prevc(t, p) { return p > 1 ? substr(t, p - 1, 1) : "" }
function repl(s, f, r,   out, q) {
  out = ""
  while ((q = index(s, f)) > 0) { out = out substr(s, 1, q - 1) r; s = substr(s, q + length(f)) }
  return out s
}
function keysof(tid, arr,   kk, pr, nn) {
  nn = 0
  for (kk in F) { split(kk, pr, SUBSEP); if (pr[1] == tid) arr[++nn] = pr[2] }
  return nn
}
function find(t, tid,   fi, p, m, v, g1, b, en, name, rl) {
  for (fi = 1; fi <= NFX; fi++) {
    p = 1
    while (fnd(t, FXRE[fi], p)) { addv(tid, substr(t, MS, ML), FXK[fi]); p = MS + ML }
  }
  p = 1
  while (fnd(t, PEMB, p)) {
    b = MS
    if (fnd(t, PEME, MS + ML)) en = MS + ML
    else en = length(t) + 1
    addv(tid, substr(t, b, en - b), "private_key")
    p = en
  }
  p = 1
  while (fnd(t, URLRE, p)) {
    m = substr(t, MS, ML); p = MS + ML
    match(m, URLPFX); v = substr(m, RLENGTH + 1)
    addv(tid, substr(v, 1, length(v) - 1), "url_credential")
  }
  p = 1
  while (fnd(t, BEARRE, p)) {
    if (prevc(t, MS) ~ /[A-Za-z0-9_]/) { p = MS + 1; continue }
    m = substr(t, MS, ML); p = MS + ML
    match(m, BEARPFX); addv(tid, substr(m, RLENGTH + 1), "bearer_token")
  }
  p = 1
  while (fnd(t, BASRE, p)) {
    if (prevc(t, MS) ~ /[A-Za-z0-9_]/) { p = MS + 1; continue }
    m = substr(t, MS, ML); p = MS + ML
    match(m, BASPFX); addv(tid, substr(m, RLENGTH + 1), "basic_auth")
  }
  p = 1
  while (fnd(t, ASGRE, p)) {
    m = substr(t, MS, ML); p = MS + ML
    match(m, ASGNAME); g1 = RLENGTH; name = substr(m, 1, g1)
    if (match(substr(m, g1 + 1), ASGSEP) == 0) continue
    v = substr(m, g1 + RLENGTH + 1)
    if (tolower(name) ~ /(id|ids|name|names|file|path|dir|ref|var|variable|env|type|mode|policy|header|field|label|prefix|suffix|url|uri|endpoint|host|provider|store|manager|usage|scope|expiry|expires|ttl)s?$/) continue
    addv(tid, v, "secret_assignment")
  }
  p = 1
  while (fnd(t, CLIRE, p)) {
    if (prevc(t, MS) ~ /[A-Za-z0-9_-]/) { p = MS + 1; continue }
    m = substr(t, MS, ML); p = MS + ML
    match(m, CLIPFX); addv(tid, substr(m, RLENGTH + 1), "cli_credential_flag")
  }
  p = 1
  while (fnd(t, POSRE, p)) {
    if (prevc(t, MS) ~ /[A-Za-z0-9_]/) { p = MS + 1; continue }
    m = substr(t, MS, ML); p = MS + ML
    if (split(m, toks, "[" WS "]+") >= 6) {
      addv(tid, toks[5], "cli_positional_credential")
      addv(tid, toks[6], "cli_positional_credential")
    }
  }
  p = 1
  while (fnd(t, CURLRE, p)) {
    if (prevc(t, MS) ~ /[A-Za-z0-9_]/ || substr(t, MS + 4, 1) ~ /[A-Za-z0-9_]/) { p = MS + 1; continue }
    m = substr(t, MS, ML); p = MS + ML
    match(m, CURLPFX); addv(tid, substr(m, RLENGTH + 1), "cli_basic_auth")
  }
}
function slurp(f,   l, r, first) {
  r = ""; first = 1
  while ((getline l < f) > 0) { r = first ? l : r "\001" l; first = 0 }
  close(f)
  return r
}
function hexval(h,   k, c, v) {
  v = 0; h = tolower(h)
  for (k = 1; k <= length(h); k++) { c = index("0123456789abcdef", substr(h, k, 1)) - 1; v = v * 16 + c }
  return v
}
function utf8(code) {
  if (code < 128) return sprintf("%c", code)
  if (code < 2048) return sprintf("%c%c", 192 + int(code / 64), 128 + code % 64)
  if (code < 65536) return sprintf("%c%c%c", 224 + int(code / 4096), 128 + int(code / 64) % 64, 128 + code % 64)
  return sprintf("%c%c%c%c", 240 + int(code / 262144), 128 + int(code / 4096) % 64, 128 + int(code / 64) % 64, 128 + code % 64)
}
function skipws() { while (i <= n && index(" \t\r\n", substr(s, i, 1)) > 0) i++ }
# pstr: decodes the JSON string whose opening quote is at i.
function pstr(   r, c, e, u, lo) {
  r = ""; i++
  while (i <= n) {
    c = substr(s, i, 1)
    if (c == "\"") { i++; return r }
    if (c == "\\") {
      e = substr(s, i + 1, 1); i += 2
      if (e == "n") r = r "\n"; else if (e == "t") r = r "\t"; else if (e == "r") r = r "\r"
      else if (e == "b") r = r "\b"; else if (e == "f") r = r "\f"
      else if (e == "u") {
        u = hexval(substr(s, i, 4)); i += 4
        if (u >= 55296 && u <= 56319 && substr(s, i, 2) == "\\u") {
          lo = hexval(substr(s, i + 2, 4)); u = 65536 + (u - 55296) * 1024 + (lo - 56320); i += 6
        }
        r = r utf8(u)
      } else r = r e
    } else { r = r c; i++ }
  }
  return r
}
# walk: records every node path in E (exists) and every string value in S (decoded).
function walk(path,   c, key, idx) {
  skipws(); c = substr(s, i, 1); E[path] = 1
  if (c == "{") {
    i++; skipws()
    if (substr(s, i, 1) == "}") { i++; return }
    while (i <= n) {
      skipws(); key = pstr(); skipws(); i++
      walk(path == "" ? key : path "." key)
      skipws(); c = substr(s, i, 1); i++
      if (c == "}") return
    }
  } else if (c == "[") {
    i++; idx = 0; skipws()
    if (substr(s, i, 1) == "]") { i++; return }
    while (i <= n) {
      walk(path == "" ? idx : path "." idx); idx++
      skipws(); c = substr(s, i, 1); i++
      if (c == "]") return
    }
  } else if (c == "\"") {
    S[path] = pstr()
  } else {
    while (i <= n && index(",}] \t\r\n", substr(s, i, 1)) == 0) i++
  }
}
function parseline(line) {
  delete E; delete S
  s = line; n = length(s); i = 1
  walk("")
}
BEGIN {
  WS = " \t\r\n\f\013"
  NW = "[^" WS "]"
  IDC = "[A-Za-z0-9_.-]"
  VALCLS = "[^]" WS "\"'`,;)}]"
  VCLI = "[^" WS "\"'`]"
  PEMB = "-----BEGIN [A-Z ]*PRIVATE KEY-----"
  PEME = "-----END [A-Z ]*PRIVATE KEY-----"

  NFX = 7
  FXRE[1] = "A[KS]IA[0-9A-Z]{16}";                    FXK[1] = "aws_access_key"
  FXRE[2] = "sq[upa]_" ge("[0-9a-f]", 20);            FXK[2] = "sonarqube_token"
  FXRE[3] = "gh[pousr]_" ge("[A-Za-z0-9]", 30);       FXK[3] = "github_token"
  FXRE[4] = "github_pat_" ge("[A-Za-z0-9_]", 40);     FXK[4] = "github_token"
  FXRE[5] = "xox[abprs]-" ge("[A-Za-z0-9-]", 10);     FXK[5] = "slack_token"
  FXRE[6] = "AIza[0-9A-Za-z_-]{35}";                  FXK[6] = "google_api_key"
  FXRE[7] = "eyJ" ge("[A-Za-z0-9_-]", 8) "[.]eyJ" ge("[A-Za-z0-9_-]", 8) "[.]" ge("[A-Za-z0-9_-]", 8); FXK[7] = "jwt"

  URLRE = "://[^/:@'\"" WS "]+:" ge("[^@/'\"" WS "]", 3) "@"
  URLPFX = "^://[^/:@'\"" WS "]+:"
  BEARRE = ci("bearer") "[" WS "]+" ge("[A-Za-z0-9._~+/=-]", 16)
  BEARPFX = "^" ci("bearer") "[" WS "]+"
  BASRE = ci("basic") "[" WS "]+" ge("[A-Za-z0-9+/=]", 16)
  BASPFX = "^" ci("basic") "[" WS "]+"

  KWI = "(" ci("password") "|" ci("passwd") "|" ci("pwd") "|" ci("secret") "|" ci("token") "|" ci("api") "[_-]?" ci("key") "|" ci("apikey") "|" ci("access") "[_-]?" ci("key") "|" ci("private") "[_-]?" ci("key") "|" ci("credential") "|" ci("auth") "[_-]?" ci("key") ")"
  ASGRE = IDC "*" KWI IDC "*[\"']?[" WS "]*[:=][" WS "]*[\"']?" ge(VALCLS, 6)
  ASGNAME = "^" IDC "*" KWI IDC "*"
  ASGSEP = "^[\"']?[" WS "]*[:=][" WS "]*[\"']?"

  KWC = "(" ci("password") "|" ci("passwd") "|" ci("token") "|" ci("secret") "|" ci("api") "-" ci("key") "|" ci("apikey") "|" ci("client") "-" ci("secret") ")"
  CLIRE = "-" "-?" KWC "[= ]+[\"']?" ge(VCLI, 6)
  CLIPFX = "^-" "-?" KWC "[= ]+[\"']?"

  NW5 = NW NW NW NW NW "*"
  POSRE = ci("alias") "[" WS "]+" ci("set") "[" WS "]+" NW "+[" WS "]+" NW "+[" WS "]+" NW5 "[" WS "]+" NW5
  CURLRE = ci("curl") "[^\r\n]*[" WS "]-[Uu][" WS "]+[\"']?[^" WS ":'\"]+:" ge("[^" WS "\"']", 4)
  CURLPFX = "^" ci("curl") "[^\r\n]*[" WS "]-[Uu][" WS "]+[\"']?[^" WS ":'\"]+:"

  REF1 = "^(" ci("os") "[.]" ci("environ") "|" ci("environ") "|" ci("getenv") "|" ci("process") "[.]" ci("env") "|" ci("secrets") "[.]|" ci("vars") "[.]|" ci("env") "[.]|" ci("credentials") "[(]|" ci("system") "[.]" ci("getenv") "|" ci("env") "[[]|" ci("params") "[.]|" ci("var") "[.]|" ci("data") "[.]|" ci("file") "[(])"
  REF2 = "^([Xx][Xx][Xx][Xx]*|[*][*][*][*]*|[.][.][.][.]*|" ci("changeme") "|" ci("change_me") "|" ci("your") "[-_].*|" ci("example") ".*|" ci("placeholder") "|" ci("redacted") "|" ci("none") "|" ci("null") "|" ci("true") "|" ci("false") "|" ci("string") "|" ci("required") "|" ci("todo") "|" ci("secret") "|" ci("password") "|" ci("token") "|" ci("apikey") "|" ci("api_key") ")$"
  REF3 = "<" ci("redacted")

  MODE = ENVIRON["SG_MODE"]; TXF = ENVIRON["SG_TX"]; MSGF = ENVIRON["SG_MSG"]; OUTF = ENVIRON["SG_OUT"]
  RS = "\001"; msg = slurp(MSGF); RS = "\n"

  if (TXF != "") {
    budget = 4194304
    while (budget > 0 && (getline line < TXF) > 0) {
      if (index(line, "tool_result") == 0) continue
      parseline(line)
      if (!(("message.content") in E) || (("message.content") in S)) continue
      if (!(("type") in S) || S["type"] != "user") continue
      for (bi = 0; (("message.content." bi) in E); bi++) {
        bp = "message.content." bi
        if (!((bp ".type") in S) || S[bp ".type"] != "tool_result") continue
        txt = ""
        if ((bp ".content") in S) txt = S[bp ".content"]
        else {
          for (j = 0; ((bp ".content." j) in E); j++) {
            if (((bp ".content." j ".text") in S) && S[bp ".content." j ".text"] != "")
              txt = (txt == "" ? "" : txt "\n") S[bp ".content." j ".text"]
          }
        }
        if (txt == "") continue
        if (index(tolower(txt), "report delivered to your caller") > 0) continue
        budget -= length(txt)
        find(txt, "T")
      }
    }
    close(TXF)
  }

  if (MODE == "web") {
    find(msg, "V")
    nv = keysof("V", VK); nh = 0
    for (i = 1; i <= nv; i++) if (index(msg, VK[i]) > 0) HK[++nh] = VK[i]
    if (TXF != "") {
      nt = keysof("T", TK)
      for (i = 1; i <= nt; i++) if (index(msg, TK[i]) > 0) { HK[++nh] = TK[i]; F["V" SUBSEP TK[i]] = F["T" SUBSEP TK[i]] }
    }
    print "COUNT " nh
    for (i = 1; i <= nh; i++) print "KIND " F["V" SUBSEP HK[i]]
    exit 0
  }

  find(msg, "V")
  nt = keysof("T", TK)
  for (i = 1; i <= nt; i++) if (index(msg, TK[i]) > 0) F["V" SUBSEP TK[i]] = F["T" SUBSEP TK[i]]
  nv = keysof("V", VK); np = 0
  for (i = 1; i <= nv; i++) if (index(msg, VK[i]) > 0) PV[++np] = VK[i]
  for (i = 2; i <= np; i++) {
    x = PV[i]; j = i - 1
    while (j >= 1 && length(PV[j]) < length(x)) { PV[j + 1] = PV[j]; j-- }
    PV[j + 1] = x
  }
  print "COUNT " np
  if (np == 0) exit 0
  nw = msg
  for (i = 1; i <= np; i++) { nw = repl(nw, PV[i], "<redacted:secret>"); KK[F["V" SUBSEP PV[i]]] = 1 }
  while (length(nw) > 0 && index(" \t\r\n\f\013", substr(nw, length(nw), 1)) > 0) nw = substr(nw, 1, length(nw) - 1)
  final = nw "\n\n[secret-guard: " np " secret value(s) were redacted from this answer by a hook. Use the cited source locations; the values themselves are never passed on.]"
  printf "%s", final > OUTF
  close(OUTF)
  for (k in KK) print "KIND " k
  exit 0
}
AWKPROG
)

# Splices the redacted message (JSON string literal in SG_REPL) into the raw tool_input object (SG_IN); other members are kept byte for byte.
SPLICE_PROG=$(cat <<'AWKPROG'
function slurp(f,   l, r, first) {
  r = ""; first = 1
  while ((getline l < f) > 0) { r = first ? l : r "\001" l; first = 0 }
  close(f)
  return r
}
function skipws() { while (i <= n && index(" \t\r\n", substr(s, i, 1)) > 0) i++ }
function skipstr() {
  i++
  while (i <= n) {
    c = substr(s, i, 1)
    if (c == "\\") i += 2
    else if (c == "\"") { i++; return }
    else i++
  }
}
function skipval(   c, d) {
  skipws(); c = substr(s, i, 1)
  if (c == "\"") { skipstr(); return }
  if (c == "{" || c == "[") {
    d = 0
    while (i <= n) {
      c = substr(s, i, 1)
      if (c == "\"") { skipstr(); continue }
      if (c == "{" || c == "[") d++
      else if (c == "}" || c == "]") { d--; if (d == 0) { i++; return } }
      i++
    }
    return
  }
  while (i <= n && index(",}] \t\r\n", substr(s, i, 1)) == 0) i++
}
BEGIN {
  RS = "\001"
  s = slurp(ENVIRON["SG_IN"]); r = slurp(ENVIRON["SG_REPL"])
  n = length(s); i = 1; vs = 0
  skipws()
  if (substr(s, i, 1) != "{") exit 1
  i++
  while (1) {
    skipws(); c = substr(s, i, 1)
    if (c == "}") break
    if (c != "\"") exit 1
    ks = i + 1; skipstr(); key = substr(s, ks, i - 1 - ks)
    skipws(); if (substr(s, i, 1) != ":") exit 1
    i++
    skipws(); vstart = i; skipval(); vend = i - 1
    if (key == "message") { vs = vstart; ve = vend }
    skipws(); c = substr(s, i, 1); i++
    if (c == "}") break
    if (c != ",") exit 1
  }
  if (vs == 0) exit 1
  printf "%s%s%s", substr(s, 1, vs - 1), r, substr(s, ve + 1)
  exit 0
}
AWKPROG
)

case "$TOOL" in
  SubagentHandback) handback "$TOOL" ;;
  WebFetch|WebSearch) web_check "$TOOL" ;;
esac
exit 0
