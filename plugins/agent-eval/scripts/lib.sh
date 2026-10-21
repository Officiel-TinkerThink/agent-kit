# agent-kit shell helpers (POSIX sh: dash, busybox ash, bash --posix). Sourced by every .sh hook of this plugin.
# This file is identical in all five plugins (a test enforces it). Needs only sh, awk, sed, grep, coreutils.
# Before sourcing, a script sets KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)".

# --- kit data folder (KIT_DATA): $AGENT_KIT_DATA > <CLAUDE_CONFIG_DIR>/agent-kit > config folder derived from the
# --- plugin's own .../plugins/cache/... path > ~/.claude/agent-kit. Printed without a trailing slash.
kit_data() {
  _d="${AGENT_KIT_DATA:-}"
  if [ -z "$_d" ]; then
    _c="${CLAUDE_CONFIG_DIR:-}"
    if [ -z "$_c" ]; then
      case "$KIT_SCRIPT_DIR" in */plugins/cache/*) _c="${KIT_SCRIPT_DIR%%/plugins/cache/*}" ;; esac
    fi
    [ -n "$_c" ] || _c="${HOME:-/root}/.claude"
    _d="$_c/agent-kit"
  fi
  printf '%s' "${_d%/}"
}

# --- JSON ------------------------------------------------------------------------------------------------
# json_get <json-text> <path>   prints the decoded value at a dotted path (keys, array indexes: "tool_input.command",
# "messages.0.role"). Strings are decoded (\n, \t, \", \\, \uXXXX); numbers/true/false/null are printed as written;
# an object or array is printed as its raw JSON text. Prints nothing (exit 1) when the path does not exist.
json_get() {
  printf '%s' "$1" | awk -v want="$2" '
    function skipws() { while (i <= n && index(" \t\r\n", substr(s, i, 1))) i++ }
    function hexval(h,   k, c, v) { v = 0; h = tolower(h); for (k = 1; k <= length(h); k++) { c = index("0123456789abcdef", substr(h, k, 1)) - 1; v = v * 16 + c } return v }
    function chr(code) { if (code < 128) return sprintf("%c", code); if (code < 2048) return sprintf("%c%c", 192 + int(code / 64), 128 + code % 64); return sprintf("%c%c%c", 224 + int(code / 4096), 128 + int(code / 64) % 64, 128 + code % 64) }
    function pstring(   r, c, e, u, hi, lo) {
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
            if (u >= 55296 && u <= 56319 && substr(s, i, 2) == "\\u") { lo = hexval(substr(s, i + 2, 4)); u = 65536 + (u - 55296) * 1024 + (lo - 56320); i += 6; r = r sprintf("%c%c%c%c", 240 + int(u / 262144), 128 + int(u / 4096) % 64, 128 + int(u / 64) % 64, 128 + u % 64) }
            else r = r chr(u)
          } else r = r e
        } else { r = r c; i++ }
      }
      return r
    }
    function pvalue(path,   c, start, key, idx, tok, v) {
      skipws(); c = substr(s, i, 1); start = i
      if (c == "{") {
        i++; skipws()
        if (substr(s, i, 1) == "}") { i++ } else {
          while (i <= n) {
            skipws(); key = pstring(); skipws(); i++   # skip the colon
            pvalue(path == "" ? key : path "." key); skipws()
            c = substr(s, i, 1); i++
            if (c == "}") break
          }
        }
        if (path == want && !found) { found = 1; out = substr(s, start, i - start) }
      } else if (c == "[") {
        i++; idx = 0; skipws()
        if (substr(s, i, 1) == "]") { i++ } else {
          while (i <= n) {
            pvalue(path == "" ? idx : path "." idx); idx++; skipws()
            c = substr(s, i, 1); i++
            if (c == "]") break
          }
        }
        if (path == want && !found) { found = 1; out = substr(s, start, i - start) }
      } else if (c == "\"") {
        v = pstring()
        if (path == want && !found) { found = 1; out = v }
      } else {
        tok = ""
        while (i <= n && index(",}] \t\r\n", substr(s, i, 1)) == 0) { tok = tok substr(s, i, 1); i++ }
        if (path == want && !found) { found = 1; out = tok }
      }
    }
    BEGIN { RS = "\001"; found = 0 }
    { s = $0; n = length(s); i = 1; pvalue(""); if (found) { printf "%s", out; exit 0 } else exit 1 }
    END { if (!found) exit 1 }
  '
}

# json_has <json-text> <path>   true when the path exists.
json_has() { json_get "$1" "$2" >/dev/null 2>&1; }

# json_str <text>   prints the text as a JSON string literal (with the surrounding quotes).
json_str() {
  printf '%s' "$1" | awk 'BEGIN { RS = "\001"; ORS = "" }
    { gsub(/\\/, "\\\\"); gsub(/"/, "\\\""); gsub(/\t/, "\\t"); gsub(/\r/, "\\r"); gsub(/\n/, "\\n"); gsub(/\b/, "\\b"); gsub(/\f/, "\\f"); printf "\"%s\"", $0 }
    END { if (NR == 0) printf "\"\"" }'
}

# --- small helpers ---------------------------------------------------------------------------------------
# now_utc  ->  2026-10-13T12:34:56.000Z
now_utc() { date -u +%Y-%m-%dT%H:%M:%S.000Z; }

# agent_is <agent_type> <name>...  true when the type equals a name or ends in ":<name>" (plugin agents report "<plugin>:<name>").
agent_is() {
  _t="$1"; shift
  for _n in "$@"; do
    case "$_t" in "$_n"|*":$_n") return 0 ;; esac
  done
  return 1
}

# append_line <file> <text>   appends one line, creating the folder; returns non-zero when the write fails.
append_line() {
  mkdir -p "$(dirname "$1")" 2>/dev/null || return 1
  printf '%s\n' "$2" >> "$1" 2>/dev/null
}

# hook_error <script> <message>   traces why an audit write or hook step failed (never blocks).
hook_error() {
  append_line "$(kit_data)/hook-errors.log" "$(now_utc) $1: $2" 2>/dev/null || true
}

# sha256_of <file>  prints the lower-case SHA-256 of a file ("" when it does not exist).
sha256_of() { [ -f "$1" ] && sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
