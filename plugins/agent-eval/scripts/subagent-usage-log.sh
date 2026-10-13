#!/bin/sh
# SubagentStop hook, POSIX sh port of subagent-usage-log.ps1 (same contract, same agent-usage/2 record).
# Appends ONE metadata record per finished subagent run to usage/agent-usage.jsonl and runs the Layer 1
# mechanical contract checks (deterministic, no model). Metadata only: no prompts, no answers, no file content,
# never a matched secret value. Fails open: any error exits 0 and never blocks the agent.
# Usage: subagent-usage-log.sh [-SelfTestInput <file>]    (stdin: the SubagentStop hook JSON)
# Needs sh, awk (POSIX/mawk), grep, sed, tr, wc, sha256sum, mkdir, mktemp. No PowerShell, no Python.
# Bytes, not characters, whatever the user's locale: the awk programs spell UTF-8 by hand (checks.awk matches byte
# ranges such as [\200-\277]). gawk rejects those in a UTF-8 locale ("Invalid collation character"), the checks stage
# exited 1 and no run record was ever written on Ubuntu (en_US.UTF-8, C.UTF-8). mawk always reads bytes; C makes gawk do too.
LC_ALL=C
export LC_ALL
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

SCRIPT_NAME=subagent-usage-log
SELF_TEST=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -SelfTestInput)
      if [ "$#" -lt 2 ]; then
        hook_error "$SCRIPT_NAME" "run record not written: -SelfTestInput needs a file"
        exit 0
      fi
      SELF_TEST="$2"
      shift 2
      ;;
    *) shift ;;
  esac
done

WORK="$(mktemp -d "${TMPDIR:-/tmp}/subagent-usage.XXXXXX" 2>/dev/null)" || {
  hook_error "$SCRIPT_NAME" "run record not written: no temporary folder"
  exit 0
}
trap 'rm -rf -- "$WORK"' EXIT
trap 'exit 0' HUP INT TERM
TAB="$(printf '\t')"

# --- awk programs (written to the temp folder; quoted heredocs keep every character literal) -----------------
cat > "$WORK/json.awk" <<'AWK_JSON'
# Strict JSON parser shared by all awk stages. Globals: s (text), n (length), i (position), ERR (1 on error).
# leaf(path, kind, value, start) is defined by each stage; kind is o (object), a (array), s (string), n (number),
# l (true/false), z (null). value is decoded for strings and raw for numbers and literals.
BEGIN { for (k = 1; k < 256; k++) ORD[sprintf("%c", k)] = k }
function jws(   c) {
  while (i <= n) {
    c = substr(s, i, 1)
    if (c == " " || c == "\t" || c == "\r" || c == "\n") { i++ } else break
  }
  return 0
}
function isdig(c) { return c ~ /^[0-9]$/ }
function ishex(c) { return c ~ /^[0-9A-Fa-f]$/ }
function hex4(p,   k) {
  for (k = 0; k < 4; k++) if (!ishex(substr(s, p + k, 1))) return 0
  return 1
}
function hexval(h,   k, v) {
  v = 0; h = tolower(h)
  for (k = 1; k <= length(h); k++) v = v * 16 + index("0123456789abcdef", substr(h, k, 1)) - 1
  return v
}
function utf8(code) {
  if (code < 128) return sprintf("%c", code)
  if (code < 2048) return sprintf("%c%c", 192 + int(code / 64), 128 + code % 64)
  if (code < 65536) return sprintf("%c%c%c", 224 + int(code / 4096), 128 + int(code / 64) % 64, 128 + code % 64)
  return sprintf("%c%c%c%c", 240 + int(code / 262144), 128 + int(code / 4096) % 64, 128 + int(code / 64) % 64, 128 + code % 64)
}
function pstr(   r, c, e, u, lo) {
  r = ""; i++
  while (1) {
    if (i > n) { ERR = 1; return r }
    if (!match(substr(s, i), /["\\[:cntrl:]]/)) { ERR = 1; return r }
    r = r substr(s, i, RSTART - 1); i += RSTART - 1
    c = substr(s, i, 1)
    if (c == "\"") { i++; return r }
    if (c != "\\") {
      if (ORD[c] < 32) { ERR = 1; return r }
      r = r c; i++; continue
    }
    e = substr(s, i + 1, 1); i += 2
    if (e == "n") r = r "\n"
    else if (e == "t") r = r "\t"
    else if (e == "r") r = r "\r"
    else if (e == "b") r = r sprintf("%c", 8)
    else if (e == "f") r = r sprintf("%c", 12)
    else if (e == "/" || e == "\\" || e == "\"") r = r e
    else if (e == "u") {
      if (!hex4(i)) { ERR = 1; return r }
      u = hexval(substr(s, i, 4)); i += 4
      if (u >= 55296 && u <= 56319 && substr(s, i, 2) == "\\u" && hex4(i + 2)) {
        lo = hexval(substr(s, i + 2, 4))
        if (lo >= 56320 && lo <= 57343) { u = 65536 + (u - 55296) * 1024 + (lo - 56320); i += 6 }
      }
      r = r utf8(u)
    } else { ERR = 1; return r }
  }
}
function pnum(   st) {
  st = i
  if (substr(s, i, 1) == "-") i++
  if (substr(s, i, 1) == "0") { i++ }
  else if (isdig(substr(s, i, 1))) { while (isdig(substr(s, i, 1))) i++ }
  else { ERR = 1; return "" }
  if (substr(s, i, 1) == ".") {
    i++
    if (!isdig(substr(s, i, 1))) { ERR = 1; return "" }
    while (isdig(substr(s, i, 1))) i++
  }
  if (substr(s, i, 1) == "e" || substr(s, i, 1) == "E") {
    i++
    if (substr(s, i, 1) == "+" || substr(s, i, 1) == "-") i++
    if (!isdig(substr(s, i, 1))) { ERR = 1; return "" }
    while (isdig(substr(s, i, 1))) i++
  }
  return substr(s, st, i - st)
}
function pvalue(path,   c, st, key, idx, v) {
  jws(); if (ERR) return
  c = substr(s, i, 1); st = i
  if (c == "{") {
    i++; jws()
    if (substr(s, i, 1) == "}") { i++ }
    else {
      while (1) {
        jws(); if (substr(s, i, 1) != "\"") { ERR = 1; return }
        key = pstr(); if (ERR) return
        jws(); if (substr(s, i, 1) != ":") { ERR = 1; return }
        i++
        pvalue(path == "" ? key : path "." key); if (ERR) return
        jws(); c = substr(s, i, 1); i++
        if (c == "}") break
        if (c != ",") { ERR = 1; return }
      }
    }
    leaf(path, "o", "", st)
  } else if (c == "[") {
    i++; jws(); idx = 0
    if (substr(s, i, 1) == "]") { i++ }
    else {
      while (1) {
        pvalue(path == "" ? idx : path "." idx); if (ERR) return
        idx++
        jws(); c = substr(s, i, 1); i++
        if (c == "]") break
        if (c != ",") { ERR = 1; return }
      }
    }
    leaf(path, "a", "", st)
  } else if (c == "\"") {
    v = pstr(); if (ERR) return
    leaf(path, "s", v, st)
  } else if (c == "-" || isdig(c)) {
    v = pnum(); if (ERR) return
    leaf(path, "n", v, st)
  } else if (substr(s, i, 4) == "true") { i += 4; leaf(path, "l", "true", st) }
  else if (substr(s, i, 5) == "false") { i += 5; leaf(path, "l", "false", st) }
  else if (substr(s, i, 4) == "null") { i += 4; leaf(path, "z", "null", st) }
  else ERR = 1
}
function parse_text(txt) {
  s = txt; n = length(s); i = 1; ERR = 0
  pvalue("")
  jws()
  if (!ERR && i <= n) ERR = 1
  return !ERR
}
AWK_JSON

cat > "$WORK/validate.awk" <<'AWK_VALIDATE'
# Reads the whole hook input and prints EMPTY, OK or INVALID.
function leaf(p, k, v, st) { }
BEGIN { RS = "\001" }
{ SRC = (NR > 1) ? SRC "\001" $0 : $0 }
END {
  s = SRC; n = length(s); i = 1; ERR = 0
  jws()
  if (i > n) { print "EMPTY"; exit }
  if (parse_text(SRC)) print "OK"; else print "INVALID"
}
AWK_VALIDATE

cat > "$WORK/usage.awk" <<'AWK_USAGE'
# Stage A: one pass over the transcript (JSONL). Prints stat lines (TAB separated) and writes the last
# SubagentHandback text to OUTF. Assistant usage is de-duplicated by message id (last record wins).
function truthy(kind, val) {
  if (kind == "o" || kind == "a") return 1
  if (kind == "s") return val != ""
  if (kind == "n") return (val + 0) != 0
  if (kind == "l") return val == "true"
  return 0
}
function num(kind, val) { return (kind == "n" || kind == "s") ? val + 0 : 0 }
function leaf(path, kind, val, st,   rest, N, fld, raw) {
  if (path == "timestamp") TSV = (kind == "s") ? val : ""
  else if (path == "type") TYPE = (kind == "s") ? tolower(val) : ""
  else if (path == "uuid") UUID = (kind == "s" || kind == "n") ? val : ""
  else if (path == "message") MSG_T = truthy(kind, val)
  else if (path == "message.id") MID = (kind == "s" || kind == "n") ? val : ""
  else if (path == "message.model") { MOD_T = truthy(kind, val); MODEL = (kind == "s" || kind == "n") ? val : "" }
  else if (path == "message.content") CONTENT_ARR = (kind == "a")
  else if (path == "message.usage") USAGE_T = truthy(kind, val)
  else if (path == "message.usage.input_tokens") UIN = num(kind, val)
  else if (path == "message.usage.output_tokens") UOUT = num(kind, val)
  else if (path == "message.usage.cache_read_input_tokens") UCR = num(kind, val)
  else if (path == "message.usage.cache_creation_input_tokens") UCW = num(kind, val)
  else if (substr(path, 1, 16) == "message.content.") {
    rest = substr(path, 17)
    if (rest ~ /^[0-9]+$/) {
      N = rest + 0
      if (N + 1 > NB) NB = N + 1
    } else if (match(rest, /^[0-9]+\./)) {
      N = substr(rest, 1, RLENGTH - 1) + 0
      fld = substr(rest, RLENGTH + 1)
      if (fld == "type") BT[N] = (kind == "s") ? tolower(val) : ""
      else if (fld == "name") BN[N] = (kind == "s" || kind == "n") ? val : ""
      else if (fld == "is_error") BERR[N] = ((kind == "l" && val == "true") || (kind == "s" && tolower(val) == "true"))
      else if (fld == "input.message") {
        BMSGSET[N] = 1
        BMSG[N] = (kind == "o" || kind == "a") ? substr(s, st, i - st) : val
      } else if (fld == "content") {
        BCONT[N] = (kind == "o" || kind == "a") ? substr(s, st, i - st) : val
      }
    }
  }
}
function epoch(t,   y, mo, d, h, mi, se, fr, rest, off, sg, era, yoe, mp, doy, doe, days) {
  if (!match(t, /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9][Tt ][0-9][0-9]:[0-9][0-9]:[0-9][0-9]/)) return -1
  y = substr(t, 1, 4) + 0; mo = substr(t, 6, 2) + 0; d = substr(t, 9, 2) + 0
  h = substr(t, 12, 2) + 0; mi = substr(t, 15, 2) + 0; se = substr(t, 18, 2) + 0
  rest = substr(t, 20); fr = 0
  if (match(rest, /^\.[0-9]+/)) { fr = ("0" substr(rest, 1, RLENGTH)) + 0; rest = substr(rest, RLENGTH + 1) }
  off = 0
  if (rest == "" || rest == "Z" || rest == "z") off = 0
  else if (match(rest, /^[+-][0-9][0-9]:?[0-9][0-9]$/)) {
    sg = (substr(rest, 1, 1) == "-") ? -1 : 1
    off = sg * ((substr(rest, 2, 2) + 0) * 3600 + (substr(rest, length(rest) - 1, 2) + 0) * 60)
  } else return -1
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return -1
  if (mo <= 2) y--
  era = int(y / 400); yoe = y - era * 400
  mp = (mo + 9) % 12
  doy = int((153 * mp + 2) / 5) + d - 1
  doe = yoe * 365 + int(yoe / 4) - int(yoe / 100) + doy
  days = era * 146097 + doe - 719468
  return days * 86400 + h * 3600 + mi * 60 + se + fr - off
}
function reset_line() {
  TSV = ""; TYPE = ""; UUID = ""; MSG_T = 0; MID = ""; MOD_T = 0; MODEL = ""; CONTENT_ARR = 0; USAGE_T = 0
  UIN = 0; UOUT = 0; UCR = 0; UCW = 0; NB = 0
  delete BT; delete BN; delete BERR; delete BMSG; delete BMSGSET; delete BCONT
}
function addtool(nm,   key) {
  key = tolower(nm)
  if (!(key in TK)) { TK[key] = nm; TORD[++NT] = key }
  TCNT[key]++
}
function addmodel(nm,   key) {
  key = tolower(nm)
  if (!(key in MK)) { MK[key] = nm; MORD[++NM] = key }
}
function clean(x) { gsub(/[[:cntrl:]]/, "?", x); return x }
function endline(   e, mid, key, k, nm) {
  if (TSV != "") {
    e = epoch(TSV)
    if (e >= 0) {
      if (!HASTS || e < TMIN) TMIN = e
      if (!HASTS || e > TMAX) TMAX = e
      HASTS = 1
    }
  }
  if (TYPE == "assistant" && MSG_T) {
    mid = MID; if (mid == "") mid = UUID
    key = tolower(mid)
    if (USAGE_T) { CK[key] = 1; CIN[key] = UIN; COUT[key] = UOUT; CCR[key] = UCR; CCW[key] = UCW }
    if (MOD_T && MODEL != "") addmodel(MODEL)
    if (CONTENT_ARR) {
      for (k = 0; k < NB; k++) {
        if (BT[k] != "tool_use") continue
        nm = BN[k]
        if (tolower(nm) == "subagenthandback") { HB = 1; OUT = BMSG[k] }
        else { TOOLCALLS++; addtool(nm) }
      }
    }
  } else if (TYPE == "user" && CONTENT_ARR) {
    for (k = 0; k < NB; k++)
      if (BT[k] == "tool_result" && BERR[k] && index(tolower(BCONT[k]), "blocked") > 0) BLOCKED++
  }
}
BEGIN { HB = 0; BLOCKED = 0; TOOLCALLS = 0; NT = 0; NM = 0; HASTS = 0; OUT = "" }
/^[[:space:]]*$/ { next }
{
  reset_line()
  if (parse_text($0)) endline()
}
END {
  for (key in CK) { CALLS++; TIN += CIN[key]; TOUT += COUT[key]; TCR += CCR[key]; TCW += CCW[key] }
  COST = (TIN * 0.10 + TCW * 0.125 + TCR * 0.01 + TOUT * 0.50) / 1000000
  if (HASTS) printf "DUR\t%.1f\n", TMAX - TMIN
  else printf "DUR\tnull\n"
  printf "CALLS\t%d\nTOOLCALLS\t%d\nTIN\t%d\nTCW\t%d\nTCR\t%d\nTOUT\t%d\nCOST\t%.5f\n", CALLS, TOOLCALLS, TIN, TCW, TCR, TOUT, COST
  printf "HB\t%d\nBLOCKED\t%d\n", HB, BLOCKED
  for (j = 1; j <= NM; j++) printf "MODEL\t%s\n", clean(MK[MORD[j]])
  for (j = 1; j <= NT; j++) printf "TOOL\t%d\t%s\n", TCNT[TORD[j]], clean(TK[TORD[j]])
  OF = ENVIRON["OUTF"]
  printf "%s", OUT > OF
  close(OF)
}
AWK_USAGE

cat > "$WORK/checks.awk" <<'AWK_CHECKS'
# Stage C: Get-Flags equivalent on the decoded hand-back text (file OUTF). Prints F (flag), C (citation candidate)
# and OUTCHARS lines in the order the flags are recorded.
function leaf(p, k, v, st) { }
function emit(code, sev, detail) { printf "F\t%s\t%s\t%s\n", code, sev, detail }
function trim(x) { sub(/^[[:space:]]+/, "", x); sub(/[[:space:]]+$/, "", x); return x }
function u16(x,   t, cont, n4, L) {
  L = length(x); t = x; cont = gsub(/[\200-\277]/, "", t); t = x; n4 = gsub(/[\360-\364]/, "", t)
  return L - cont + n4
}
function isword(c) { return c ~ /^[A-Za-z0-9_]$/ }
function isbody(c) {
  if (c == "" || c ~ /[[:space:]]/) return 0
  return index("`'\"|<>*?():", c) == 0
}
function first_match(H, re, lead, trail, lb,   pos, hl, st, en, ok) {
  hl = length(H); pos = 1; MLEN = 0
  while (pos <= hl && match(substr(H, pos), re)) {
    st = pos + RSTART - 1; en = st + RLENGTH - 1
    ok = 1
    if (lead && st > 1 && isword(substr(H, st - 1, 1))) ok = 0
    if (ok && trail && en < hl && isword(substr(H, en + 1, 1))) ok = 0
    if (ok && lb) {
      if (st > 4 && (substr(H, st - 4, 4) == "not " || substr(H, st - 4, 4) == "n't ")) ok = 0
      if (st > 6 && substr(H, st - 6, 6) == "never ") ok = 0
    }
    if (ok) { MLEN = RLENGTH; return st }
    pos = st + 1
  }
  return 0
}
# rep(x, k): x repeated k times. Used instead of interval expressions: mawk misreads {n,} when more pattern follows.
function rep(x, k,   r, j) { r = ""; for (j = 0; j < k; j++) r = r x; return r }
function secrets(   hx) {
  if (O ~ ("AKIA" rep("[0-9A-Z]", 16))) emit("secret_pattern", "fail", "output contains something shaped like: aws_access_key")
  if (O ~ ("squ_" rep("[0-9a-f]", 20) "[0-9a-f]*")) emit("secret_pattern", "fail", "output contains something shaped like: sonarqube_token")
  if (O ~ ("gh[pousr]_" rep("[A-Za-z0-9]", 30) "[A-Za-z0-9]*")) emit("secret_pattern", "fail", "output contains something shaped like: github_token")
  if (O ~ ("xox[abprs]-" rep("[A-Za-z0-9-]", 10) "[A-Za-z0-9-]*")) emit("secret_pattern", "fail", "output contains something shaped like: slack_token")
  if (O ~ /-----BEGIN [A-Z ]*PRIVATE KEY-----/) emit("secret_pattern", "fail", "output contains something shaped like: private_key_block")
  if (O ~ ("://[^/[:space:]:@]+:" rep("[^@[:space:]]", 4) "[^@[:space:]]*@")) emit("secret_pattern", "fail", "output contains something shaped like: credential_in_url")
  hx = "(^|[^a-z0-9_])password[[:space:]]*[=:][[:space:]]*[^[:space:]<`\"']"
  if (LO ~ (hx rep("[^[:space:]<`\"']", 5) "[^[:space:]<`\"']*")) emit("secret_pattern", "fail", "output contains something shaped like: password_assignment")
}
function forbidden(   p, re, lead, trail, lb, st, ws0, wl, w) {
  for (p = 1; p <= 4; p++) {
    if (p == 1) { re = "no known vulnerabilit"; lead = 1; trail = 0; lb = 0 }
    else if (p == 2) { re = "(is|are) (now )?(safe|secure)"; lead = 1; trail = 1; lb = 1 }
    else if (p == 3) { re = "safe to (ship|upgrade|deploy|use)"; lead = 1; trail = 1; lb = 0 }
    else { re = "(is|are) (fully )?(part 11 )?compliant"; lead = 1; trail = 1; lb = 0 }
    st = first_match(LO, re, lead, trail, lb)
    if (st == 0) continue
    ws0 = st - 41; if (ws0 < 0) ws0 = 0
    wl = Ln - ws0; if (wl > 80) wl = 80
    w = substr(LO, ws0 + 1, wl)
    if (w ~ /(never|not|n't|no)[[:space:]]+(say|says|write|writes|mean|means|a verdict|determin)/) continue
    emit("forbidden_phrase", "warn", "matched: " trim(substr(O, st, MLEN)))
    return
  }
}
function json_part(   t, L, inner, lk) {
  t = T; L = length(t)
  if (L >= 6 && substr(t, 1, 3) == "```" && substr(t, L - 2, 3) == "```") {
    inner = substr(t, 4, L - 6)
    if (tolower(substr(inner, 1, 4)) == "json") inner = substr(inner, 5)
    t = trim(inner)
  }
  lk = (substr(t, 1, 1) == "{" || substr(t, 1, 1) == "[")
  if (lk && !parse_text(t)) emit("json_invalid", "fail", "answer starts like JSON but does not parse")
  return lk
}
function recon(   pos, mt, g1, g2, rest) {
  pos = 1
  while (pos <= Ln && match(substr(LO, pos), /expected[[:space:]]+[0-9]+[[:space:]]*\/[[:space:]]*listed[[:space:]]+[0-9]+/)) {
    mt = substr(LO, pos + RSTART - 1, RLENGTH)
    pos = pos + RSTART - 1 + RLENGTH
    match(mt, /[0-9]+/); g1 = substr(mt, RSTART, RLENGTH)
    rest = substr(mt, RSTART + RLENGTH)
    match(rest, /[0-9]+/); g2 = substr(rest, RSTART, RLENGTH)
    if (g1 != g2) emit("reconciliation_mismatch", "fail", "expected " g1 " / listed " g2)
  }
}
function footers(AT,   need_rec, need_cov) {
  need_rec = (AT == "schema-reader" || AT == "contract-reader" || AT == "pipeline-reader")
  need_cov = need_rec || AT == "inventory-extractor" || AT == "module-mapper" || AT == "repo-scout"
  if (need_rec && index(LO, "reconciliation") == 0) emit("footer_missing", "warn", "no Reconciliation line")
  if (need_cov && index(LO, "coverage") == 0) emit("footer_missing", "warn", "no Coverage line")
}
# try_cite(a): match of the citation regex starting at position a of O, or 0. Sets CP (path) and CL (line).
function try_cite(a,   c, b, pc, e, q, el, g, h, c2, endp, ln) {
  c = substr(O, a, 1); pc = (a > 1) ? substr(O, a - 1, 1) : ""
  if (c ~ /[A-Za-z]/) {
    if (substr(O, a + 1, 1) != ":") return 0
    c2 = substr(O, a + 2, 1)
    if (c2 != "/" && c2 != "\\") return 0
    if (pc ~ /[A-Za-z0-9]/) return 0
    b = a + 3
  } else {
    if (pc ~ /[A-Za-z0-9._~\/\\-]/) return 0
    b = a + 1
  }
  e = b
  while (e <= Ln && isbody(substr(O, e, 1))) e++
  if (substr(O, e, 1) != ":") return 0
  q = e - 1
  while (q >= b && substr(O, q, 1) ~ /[A-Za-z0-9]/) q--
  q++
  el = e - q
  if (el < 1 || el > 8) return 0
  if (q - 1 < b + 1) return 0
  if (substr(O, q - 1, 1) != ".") return 0
  g = e + 1
  while (g <= Ln && substr(O, g, 1) ~ /[0-9]/) g++
  if (g == e + 1) return 0
  ln = substr(O, e + 1, g - e - 1)
  endp = g - 1
  c2 = substr(O, g, 1)
  if (c2 == "-" || c2 == ",") {
    h = g + 1
    if (substr(O, h, 1) ~ /[0-9]/) {
      while (h <= Ln && substr(O, h, 1) ~ /[0-9]/) h++
      endp = h - 1
    }
  }
  CP = substr(O, a, e - a)
  CL = (length(ln) > 9) ? 2147483647 : ln + 0
  return endp
}
function citations(   pos, a, endp, key, nuniq) {
  pos = 1; nuniq = 0
  while (pos <= Ln && match(substr(O, pos), /[A-Za-z]:[\/\\]|\//)) {
    a = pos + RSTART - 1
    endp = try_cite(a)
    if (endp > 0) {
      key = tolower(CP) ":" CL
      if (!(key in SEEN)) {
        SEEN[key] = 1; nuniq++
        if (nuniq > 80) break
        printf "C\t%s\t%d\n", CP, CL
      }
      pos = endp + 1
    } else pos = a + 1
  }
}
BEGIN { RS = "\001" }
{ O = (NR > 1) ? O "\001" $0 : $0 }
END {
  HBv = (ENVIRON["HB"] == "1"); BL = ENVIRON["BLOCKED"] + 0; AT = tolower(ENVIRON["ATYPE"])
  T = trim(O); tl = u16(T); ol = u16(O)
  LO = tolower(O); Ln = length(O)
  if (!HBv) emit("no_final_answer", "fail", "run ended without a SubagentHandback result")
  else if (tl < 15) emit("empty_output", "fail", "answer is " tl " characters")
  if (BL > 0) emit("guard_blocked", "info", BL " tool call(s) were blocked by a hook")
  if (ol > 20000) emit("oversized_output", "warn", "answer is " ol " characters")
  if (HBv && tl >= 15) {
    secrets()
    forbidden()
    lk = json_part()
    recon()
    if (!lk) footers(AT)
    citations()
  }
  printf "OUTCHARS\t%d\n", ol
}
AWK_CHECKS

cat "$WORK/json.awk" "$WORK/validate.awk" > "$WORK/validate_full.awk"
cat "$WORK/json.awk" "$WORK/usage.awk" > "$WORK/usage_full.awk"
cat "$WORK/json.awk" "$WORK/checks.awk" > "$WORK/checks_full.awk"

# --- helpers ----------------------------------------------------------------------------------------------------
lower() { printf '%s' "$1" | tr 'A-Z' 'a-z'; }

# field <dotted.path>: the decoded value of the hook input, empty when absent.
field() {
  _fv="$(json_get "$INPUT" "$1" 2>/dev/null)" || _fv=""
  printf '%s' "$_fv"
}

# add_flag <code> <sev> <detail>: appends one flag object (JSON) to FLAGS, keeps NONINFO for fail/warn flags.
add_flag() {
  _afc="$(json_str "$1")"; _afs="$(json_str "$2")"; _afd="$(json_str "$3")"
  FLAGS="${FLAGS:+$FLAGS,}{\"code\":$_afc,\"sev\":$_afs,\"detail\":$_afd}"
  [ "$2" = info ] || NONINFO=1
}

# cite_check <path> <line>: POSIX absolute paths only. A drive-letter path cannot resolve on POSIX and is reported
# as missing, the same as the ps1 reports an unknown file.
cite_check() {
  _cc_path="$1"; _cc_line="$2"
  case "$_cc_path" in
    /*) ;;
    *) add_flag citation_file_missing fail "file not found: $_cc_path"; return 0 ;;
  esac
  if [ ! -f "$_cc_path" ]; then
    add_flag citation_file_missing fail "file not found: $_cc_path"
    return 0
  fi
  _cc_size="$(wc -c 2>/dev/null < "$_cc_path")" || return 0
  _cc_size="${_cc_size##* }"
  if [ "$_cc_size" -gt 5242880 ]; then return 0; fi
  _cc_count="$(awk 'END { print NR + 0 }' "$_cc_path" 2>/dev/null)" || return 0
  if [ "$_cc_line" -gt "$_cc_count" ] || [ "$_cc_line" -lt 1 ]; then
    add_flag citation_line_out_of_range fail "$_cc_path:$_cc_line but the file has $_cc_count lines"
  fi
}

# kinds_text <json-line>: the kinds array (or string) joined with ', ' as the ps1 -join does.
kinds_text() {
  _kt_json="$1"; _kt_out=""; _kt_i=0
  if json_has "$_kt_json" "kinds.0"; then
    while _kt_v="$(json_get "$_kt_json" "kinds.$_kt_i" 2>/dev/null)"; do
      _kt_out="${_kt_out:+$_kt_out, }$_kt_v"
      _kt_i=$((_kt_i + 1))
    done
  else
    _kt_out="$(json_get "$_kt_json" kinds 2>/dev/null)"
  fi
  printf '%s' "$_kt_out"
}

# --- read the hook input ------------------------------------------------------------------------------------------
IN="$WORK/in.json"
if [ -n "$SELF_TEST" ]; then
  if ! cat -- "$SELF_TEST" > "$IN" 2>/dev/null; then
    hook_error "$SCRIPT_NAME" "run record not written: cannot read $SELF_TEST"
    exit 0
  fi
else
  cat > "$IN"
fi
VERDICT="$(awk -f "$WORK/validate_full.awk" "$IN" 2>/dev/null)" || VERDICT=INVALID
case "$VERDICT" in
  EMPTY) exit 0 ;;
  OK) ;;
  *) hook_error "$SCRIPT_NAME" "run record not written: hook input is not valid JSON"; exit 0 ;;
esac
INPUT="$(cat "$IN")"

AGENT_ID="$(field agent_id)"
[ -n "$AGENT_ID" ] || exit 0
SESSION_ID="$(field session_id)"
AGENT_TYPE="$(field agent_type)"
EFFORT="$(field effort.level)"
CWD="$(field cwd)"
TP="$(field agent_transcript_path)"

LOG="${AGENT_USAGE_LOG:-}"
[ -n "$LOG" ] || LOG="$(kit_data)/usage/agent-usage.jsonl"
if ! mkdir -p "$(dirname "$LOG")" 2>/dev/null; then
  hook_error "$SCRIPT_NAME" "run record not written: cannot create the log folder"
  exit 0
fi

# --- stage A: transcript statistics ----------------------------------------------------------------------------
SRC=/dev/null
if [ -n "$TP" ] && [ -f "$TP" ]; then SRC="$TP"; fi
OUTF="$WORK/output.txt"
if ! OUTF="$OUTF" awk -f "$WORK/usage_full.awk" "$SRC" > "$WORK/stats" 2> "$WORK/usage.err"; then
  hook_error "$SCRIPT_NAME" "run record not written: transcript could not be read ($(head -c 200 "$WORK/usage.err" | tr '\n' ' '))"
  exit 0
fi

DUR=null; CALLS=0; TOOLCALLS=0; TIN=0; TCW=0; TCR=0; TOUT=0; COST=0.00000; HB=0; BLOCKED=0
MODELS_JSON=""; TOOLS_JSON=""
while IFS="$TAB" read -r S_K S_A S_B; do
  case "$S_K" in
    DUR) DUR="$S_A" ;;
    CALLS) CALLS="$S_A" ;;
    TOOLCALLS) TOOLCALLS="$S_A" ;;
    TIN) TIN="$S_A" ;;
    TCW) TCW="$S_A" ;;
    TCR) TCR="$S_A" ;;
    TOUT) TOUT="$S_A" ;;
    COST) COST="$S_A" ;;
    HB) HB="$S_A" ;;
    BLOCKED) BLOCKED="$S_A" ;;
    MODEL) _sj="$(json_str "$S_A")"; MODELS_JSON="${MODELS_JSON:+$MODELS_JSON,}$_sj" ;;
    TOOL) _sj="$(json_str "$S_B")"; TOOLS_JSON="${TOOLS_JSON:+$TOOLS_JSON,}$_sj:$S_A" ;;
  esac
done < "$WORK/stats"

# --- stage C: Get-Flags checks on the hand-back text ----------------------------------------------------------
[ -f "$OUTF" ] || : > "$OUTF"
ATYPE="$(printf '%s' "$AGENT_TYPE" | sed 's/^.*://')"
if ! HB="$HB" BLOCKED="$BLOCKED" ATYPE="$ATYPE" awk -f "$WORK/checks_full.awk" "$OUTF" > "$WORK/checks" 2> "$WORK/checks.err"; then
  # The awk error says why (it used to go to /dev/null, which hid a whole class of failures).
  hook_error "$SCRIPT_NAME" "run record not written: output checks failed ($(head -c 200 "$WORK/checks.err" | tr '\n' ' '))"
  exit 0
fi

FLAGS=""; NONINFO=0; OUTCHARS=0
while IFS="$TAB" read -r KIND F_A F_B F_C; do
  case "$KIND" in
    F) add_flag "$F_A" "$F_B" "$F_C" ;;
    C) cite_check "$F_A" "$F_B" ;;
    OUTCHARS) OUTCHARS="$F_A" ;;
  esac
done < "$WORK/checks"

# --- secret-guard events for this agent (kinds and counts only) -----------------------------------------------
SG="${SECRET_GUARD_AUDIT:-}"
[ -n "$SG" ] || SG="$(kit_data)/audit/secret-guard-audit.jsonl"
if [ -f "$SG" ]; then
  grep -F -- "$AGENT_ID" "$SG" > "$WORK/sg" 2>/dev/null
  AID_L="$(lower "$AGENT_ID")"
  while IFS= read -r LINE; do
    EID="$(json_get "$LINE" agent_id 2>/dev/null)" || continue
    [ "$(lower "$EID")" = "$AID_L" ] || continue
    ACT="$(lower "$(json_get "$LINE" action 2>/dev/null)")"
    case "$ACT" in
      redacted)
        add_flag secret_redacted warn "$(json_get "$LINE" count 2>/dev/null) value(s) redacted at hand-back: $(kinds_text "$LINE")" ;;
      blocked)
        add_flag secret_exfil_blocked fail "$(json_get "$LINE" tool 2>/dev/null) call blocked: $(kinds_text "$LINE")" ;;
    esac
  done < "$WORK/sg"
fi

# --- record ---------------------------------------------------------------------------------------------------
TS="$(now_utc)"
FLAGGED=false
[ "$NONINFO" = 1 ] && FLAGGED=true
SHA="$(sha256_of "$TP")"
if [ -n "$SHA" ]; then SHA_J="$(json_str "$SHA")"; else SHA_J=null; fi

REC="{\"schema\":\"agent-usage/2\",\"type\":\"run\",\"ts\":$(json_str "$TS"),\"session_id\":$(json_str "$SESSION_ID"),\"agent_id\":$(json_str "$AGENT_ID"),\"agent_type\":$(json_str "$AGENT_TYPE"),\"effort\":$(json_str "$EFFORT"),\"models\":[$MODELS_JSON],\"cwd\":$(json_str "$CWD"),\"duration_s\":$DUR,\"api_calls\":$CALLS,\"tool_calls\":$TOOLCALLS,\"tools\":{$TOOLS_JSON},\"tokens\":{\"input\":$TIN,\"cache_write\":$TCW,\"cache_read\":$TCR,\"output\":$TOUT},\"est_cost_usd\":$COST,\"output_chars\":$OUTCHARS,\"flagged\":$FLAGGED,\"flags\":[$FLAGS],\"transcript\":$(json_str "$TP"),\"transcript_sha256\":$SHA_J}"

if ! append_line "$LOG" "$REC"; then
  hook_error "$SCRIPT_NAME" "run record not written: cannot append to the usage log"
fi
exit 0
