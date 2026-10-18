#!/bin/sh
# /agent-eval:report-issue (POSIX sh twin of issue-report.ps1). Turns the kit's local error evidence into a GitHub issue, ONLY when the user asks and confirms.
#   issue-report.sh draft  [-Days N]         writes <KIT_DATA>/reports/issue-draft-<time>.md and prints DRAFT/TITLE/FINGERPRINT; sends nothing
#   issue-report.sh submit -Draft <file>     re-sanitizes the draft, looks for an issue with the same fingerprint, creates one with gh, or prints a prefilled URL
# The draft holds counts, script names, versions and sanitized hook-error messages. Never prompts, answers, transcripts or file contents.
# Overrides: AGENT_KIT_DATA (data folder), AGENT_KIT_REPO (owner/name), AGENT_KIT_GH (path of the gh program).
KIT_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_SCRIPT_DIR/lib.sh"

REPO="${AGENT_KIT_REPO:-Officiel-TinkerThink/agent-kit}"
ACTION="${1:-draft}"; [ $# -gt 0 ] && shift
DAYS=30; DRAFT=""
while [ $# -gt 0 ]; do
  case "$1" in
    -Days) DAYS="$2"; shift 2 ;;
    -Draft) DRAFT="$2"; shift 2 ;;
    *) printf 'REJECTED: unknown argument %s\n' "$1"; exit 2 ;;
  esac
done
case "$DAYS" in ''|*[!0-9]*) printf 'REJECTED: -Days must be a whole number\n'; exit 2 ;; esac
{ [ "$DAYS" -ge 1 ] && [ "$DAYS" -le 365 ]; } || { printf 'REJECTED: -Days must be 1 to 365\n'; exit 2; }
DATA="$(kit_data)"
TAB="$(printf '\t')"

# sanitize: stdin -> stdout. Order matters; the PowerShell twin applies the same rules in the same order.
sanitize() {
  sed -E \
    -e 's#://[^/@ ]+@#://<redacted:secret>@#g' \
    -e 's#(Bearer|Basic) +[A-Za-z0-9._~+/=-]+#\1 <redacted:secret>#gI' \
    -e 's#(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}|xox[a-z]-[A-Za-z0-9-]{8,}|AKIA[0-9A-Z]{8,}|AIza[A-Za-z0-9_-]{8,})#<redacted:secret>#g' \
    -e 's#((pass(word)?|pwd|secret|token|api[_-]?key|credential)[A-Za-z0-9_]*[=:] *)[^ ,;"'"'"']+#\1<redacted:secret>#gI' \
    -e 's#[A-Za-z0-9+/=_-]{32,}#<redacted:secret>#g' \
    -e 's#[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}#<email>#g' \
    -e 's#[A-Za-z]:[\\/]+Users[\\/]+[^\\/ ]+#<home>#gI' \
    -e 's#/(Users|home)/[^/ ]+#<home>#g' \
    -e 's#/root([/ ]|$)#<home>\1#g' \
    -e 's#([A-Za-z]:)?[\\/]([^ \\/"'"'"']+[\\/])+([^ \\/"'"'"']+)#<path>/\3#g' \
    -e 's# +# #g'
}

plugin_version() {
  _v=$(sed -n 's/^ *"version": *"\([0-9][0-9.]*\)".*/\1/p' "$KIT_SCRIPT_DIR/../.claude-plugin/plugin.json" 2>/dev/null | head -n 1)
  printf '%s' "${_v:-unknown}"
}

# version_of <plugin>  -> the highest installed version of a kit plugin (installed layout .../agent-kit/<plugin>/<version>/, or this repository), else "not installed"
version_of() {
  if [ "$1" = agent-eval ]; then plugin_version; return; fi
  _v=$( { ls "$KIT_SCRIPT_DIR/../../../$1"/*/.claude-plugin/plugin.json "$KIT_SCRIPT_DIR/../../$1/.claude-plugin/plugin.json"; } 2>/dev/null | while IFS= read -r _f; do sed -n 's/^ *"version": *"\([0-9][0-9.]*\)".*/\1/p' "$_f" | head -n 1; done | sort -V | tail -n 1)
  printf '%s' "${_v:-not installed}"
}

# claude_version  -> the Claude Code version (digits and dots only), else "unknown"
claude_version() {
  _c=$(command -v claude 2>/dev/null) || { printf 'unknown'; return; }
  _v=$(timeout 10 "$_c" --version 2>/dev/null | head -n 1 | sed -n 's/^\([0-9][0-9.]*\).*/\1/p')
  printf '%s' "${_v:-unknown}"
}

versions_line() {
  printf '**Versions:** agent-kit %s (agent-eval %s, agent-guards %s, haiku-delegation %s, verification-runner %s), claude-code %s, os %s' \
    "$(plugin_version)" "$(version_of agent-eval)" "$(version_of agent-guards)" "$(version_of haiku-delegation)" "$(version_of verification-runner)" "$(claude_version)" "$(os_name | sanitize)"
}

os_name() { printf '%s' "$(uname -s 2>/dev/null | tr -c 'A-Za-z0-9._-' ' ' | sed 's/ *$//') $(uname -m 2>/dev/null | tr -c 'A-Za-z0-9._-' ' ' | sed 's/ *$//')"; }

# word <text> <max-length>  -> text when it is a short plain word, otherwise "other"
word() { case "$1" in ''|*[!a-z0-9:_-]*) printf 'other' ;; *) [ "${#1}" -le 60 ] && printf '%s' "$1" || printf 'other' ;; esac; }

collect_errors() {   # prints "count<TAB>first<TAB>last<TAB>script<TAB>message<TAB>signature" sorted by count desc, signature asc
  _log="$DATA/hook-errors.log"; [ -f "$_log" ] || return 0
  _cut=$(date -u -d "@$(( $(date +%s) - DAYS * 86400 ))" +%Y-%m-%d 2>/dev/null) || return 0
  tail -n 2000 "$_log" 2>/dev/null | awk -v cut="$_cut" -v TAB="$TAB" '
    { ts = $1; sc = $2; sub(/:$/, "", sc)
      if (ts !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9:.]+/) next
      if (substr(ts, 1, 10) < cut) next
      if (sc !~ /^[A-Za-z0-9_.-]+$/ || length(sc) > 60) next
      m = $0; sub(/^[^ ]+ +[^ ]+ */, "", m); gsub(/[\t\r]/, " ", m)
      print substr(ts, 1, 19) TAB sc TAB m }' |
    sanitize |
    awk -F "$TAB" -v TAB="$TAB" '
      { n = $3; gsub(/[0-9]+/, "N", n); key = $2 "|" n
        if (!(key in cnt)) { first[key] = $1; sc[key] = $2; msg[key] = substr($3, 1, 240); sigs[key] = key } else if ($1 < first[key]) first[key] = $1
        cnt[key]++; if ($1 > last[key]) last[key] = $1 }
      END { for (k in cnt) printf "%d%s%s%s%s%s%s%s%s%s%s\n", cnt[k], TAB, first[k], TAB, last[k], TAB, sc[k], TAB, msg[k], TAB, k }' |
    LC_ALL=C sort -t "$TAB" -k1,1nr -k6,6
}

collect_annotations() {   # prints "count<TAB>agent<TAB>outcome<TAB>code<TAB>severity" sorted by count desc, key asc
  _f="$DATA/eval/annotations.jsonl"; [ -f "$_f" ] || return 0
  _cut=$(date -u -d "@$(( $(date +%s) - DAYS * 86400 ))" +%Y-%m-%d 2>/dev/null) || return 0
  tail -n 500 "$_f" 2>/dev/null | while IFS= read -r _l; do
    [ -n "$_l" ] || continue
    _ts=$(json_get "$_l" ts 2>/dev/null) || continue
    awk -v t="$_ts" -v c="$_cut" 'BEGIN { exit !(substr(t, 1, 10) < c) }' && continue
    [ "$(json_get "$_l" verified 2>/dev/null)" = "no" ] && continue
    printf '%s%s%s%s%s%s%s\n' "$(word "$(json_get "$_l" agent_type 2>/dev/null)")" "$TAB" "$(word "$(json_get "$_l" outcome 2>/dev/null)")" "$TAB" "$(word "$(json_get "$_l" code 2>/dev/null)")" "$TAB" "$(word "$(json_get "$_l" severity 2>/dev/null)")"
  done | LC_ALL=C sort | uniq -c | sed -E "s/^ *([0-9]+) /\\1$TAB/" | LC_ALL=C sort -t "$TAB" -k1,1nr -k2
}

cell() { printf '%s' "$1" | sed -e 's/|/\\|/g' -e 's/`/'"'"'/g'; }

fp_of() { printf '%s' "$1" | sha256sum | awk '{print substr($1, 1, 12)}'; }

do_draft() {
  ERR=$(collect_errors); ANN=$(collect_annotations)
  NERR=0; [ -n "$ERR" ] && NERR=$(printf '%s\n' "$ERR" | awk 'END{print NR}')
  NANN=0; [ -n "$ANN" ] && NANN=$(printf '%s\n' "$ANN" | awk 'END{print NR}')
  if [ "$NERR" -eq 0 ] && [ "$NANN" -eq 0 ]; then printf 'NO ERRORS in the last %s days (hook-errors.log and eval/annotations.jsonl). Nothing to report.\n' "$DAYS"; exit 0; fi
  SIGS=$( { [ -n "$ERR" ] && printf '%s\n' "$ERR" | awk -F "$TAB" '{print "E|" $6}'; [ -n "$ANN" ] && printf '%s\n' "$ANN" | awk -F "$TAB" '{print "A|" $2 "|" $3 "|" $4 "|" $5}'; } | LC_ALL=C sort)
  FP=$(fp_of "$SIGS")
  if [ "$NERR" -gt 0 ]; then
    TOP=$(printf '%s\n' "$ERR" | head -n 1)
    _sc=$(printf '%s' "$TOP" | awk -F "$TAB" '{print $4}'); _m=$(printf '%s' "$TOP" | awk -F "$TAB" '{print substr($5, 1, 60)}')
    TITLE="[agent-kit $(plugin_version)] Error report: $_sc: $_m"
  else
    TITLE="[agent-kit $(plugin_version)] Agent failure report: $(printf '%s' "$ANN" | head -n 1 | awk -F "$TAB" '{print $2 " " $4}')"
  fi
  TITLE=$(printf '%s' "$TITLE" | sanitize)
  OUT="$DATA/reports/issue-draft-$(date -u +%Y%m%dT%H%M%SZ).md"
  mkdir -p "$DATA/reports" || { printf 'REJECTED: cannot create %s\n' "$DATA/reports"; exit 2; }
  {
    printf '<!-- agent-kit-report fingerprint: %s -->\n<!-- title: %s -->\n' "$FP" "$TITLE"
    printf '## Error report from a plugin user (reviewed by the user before sending)\n\n'
    printf 'Contains only counts, script names, versions and sanitized error messages. No prompts, answers, transcripts or file contents.\n\n'
    printf '%s\n' "$(versions_line)"
    printf '**Window:** last %s days\n\n' "$DAYS"
    printf '### Hook errors (%s kinds)\n\n' "$NERR"
    if [ "$NERR" -gt 0 ]; then
      printf '| Count | First seen | Last seen | Script | Message |\n|---|---|---|---|---|\n'
      printf '%s\n' "$ERR" | while IFS="$TAB" read -r c f l s m k; do printf '| %s | %s | %s | `%s` | `%s` |\n' "$c" "$f" "$l" "$(cell "$s")" "$(cell "$m")"; done
    else printf 'none\n'; fi
    printf '\n### Annotated agent failures (%s kinds)\n\n' "$NANN"
    if [ "$NANN" -gt 0 ]; then
      printf '| Count | Agent | Outcome | Code | Severity |\n|---|---|---|---|---|\n'
      printf '%s\n' "$ANN" | while IFS="$TAB" read -r c a o k v; do printf '| %s | `%s` | %s | %s | %s |\n' "$c" "$a" "$o" "$k" "$v"; done
    else printf 'none\n'; fi
  } > "$OUT"
  printf 'DRAFT %s\nTITLE %s\nFINGERPRINT %s\nHOOK_ERROR_KINDS %s ANNOTATION_KINDS %s\nNOTHING SENT. Show the draft to the user; submit only after they confirm.\n' "$OUT" "$TITLE" "$FP" "$NERR" "$NANN"
}

# pct <text>: percent-encodes every byte except RFC 3986 unreserved characters (A-Z a-z 0-9 - . _ ~), upper-case hex, as the ps1 twin does
pct() { printf '%s' "$1" | LC_ALL=C od -An -v -tu1 | LC_ALL=C awk '{ for (i = 1; i <= NF; i++) { c = $i + 0
  if ((c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c == 45 || c == 46 || c == 95 || c == 126) printf "%c", c
  else printf "%%%02X", c } }'; }

do_submit() {
  [ -n "$DRAFT" ] || { printf 'REJECTED: -Draft <file> is required\n'; exit 2; }
  _dir=$(cd "$DATA/reports" 2>/dev/null && pwd) || { printf 'REJECTED: no reports folder yet; run draft first\n'; exit 2; }
  _base=$(basename "$DRAFT"); _pd=$(cd "$(dirname "$DRAFT")" 2>/dev/null && pwd)
  { [ "$_pd" = "$_dir" ] && [ -f "$DRAFT" ] && case "$_base" in issue-draft-*.md) true ;; *) false ;; esac; } || { printf 'REJECTED: the draft must be a file issue-draft-*.md inside %s\n' "$_dir"; exit 2; }
  [ "$(wc -c < "$DRAFT")" -le 60000 ] || { printf 'REJECTED: draft is larger than 60000 bytes\n'; exit 2; }
  FP=$(sed -n 's/^<!-- agent-kit-report fingerprint: \([0-9a-f]\{12\}\) -->$/\1/p' "$DRAFT" | head -n 1)
  [ -n "$FP" ] || { printf 'REJECTED: the draft has no fingerprint line on its first line\n'; exit 2; }
  BODY="$DATA/reports/.submit-body.md"
  sanitize < "$DRAFT" > "$BODY"
  # the first line is a comment that must survive sanitizing unchanged
  sed -i -e "1s#.*#<!-- agent-kit-report fingerprint: $FP -->#" -e "2d" "$BODY"
  TITLE=$(sed -n '2s/^<!-- title: \(.*\) -->$/\1/p' "$DRAFT" | sanitize | cut -c1-120)
  [ -n "$TITLE" ] || TITLE="Error report from a plugin user ($FP)"
  GH="${AGENT_KIT_GH:-}"; [ -n "$GH" ] || GH=$(command -v gh 2>/dev/null)
  if [ -n "$GH" ] && "$GH" auth status >/dev/null 2>&1; then
    FOUND=$("$GH" issue list --repo "$REPO" --state all --search "$FP in:body" --json url --limit 5 2>/dev/null | grep -o 'https://[^"]*' | head -n 1)
    if [ -n "$FOUND" ]; then printf 'DUPLICATE %s\nAn issue with this fingerprint exists; nothing created. Add a comment there if the user wants.\n' "$FOUND"; exit 0; fi
    URL=$("$GH" issue create --repo "$REPO" --title "$TITLE" --body-file "$BODY" 2>/dev/null | grep -o 'https://[^ ]*' | tail -n 1)
    [ -n "$URL" ] || { printf 'FAILED gh issue create returned no URL\n'; exit 1; }
    printf 'CREATED %s\n' "$URL"; exit 0
  fi
  SHORT=$(head -c 2200 "$BODY")
  printf 'NO_GH gh is missing or not logged in. Open this link in a browser and press "Submit new issue":\nhttps://github.com/%s/issues/new?title=%s&body=%s\n' "$REPO" "$(pct "$TITLE")" "$(pct "$SHORT")"
}

case "$ACTION" in
  draft) do_draft ;;
  submit) do_submit ;;
  *) printf 'REJECTED: action must be draft or submit\n'; exit 2 ;;
esac
