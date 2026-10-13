# safe-rm-lib.sh - shared parsing and validation for safe-rm (POSIX sh port of safe-rm-lib.ps1, POSIX branches only).
# Sourced by safe-rm.sh, safe-rm-restore.sh and guard-verification-runner.sh, after lib.sh. The caller sets KIT_SCRIPT_DIR.
# Needs only sh, awk, sed, grep, tr, find, sort, mktemp, od, stat (GNU or BSD form), date, cut, coreutils mv/mkdir/rm.
# Nothing here changes the filesystem: the functions only read, except srm_resolve*/srm_measure_tree, which create and
# remove their own temp files, and srm_dir_digest, which does the same.
#
# POSIX rules (as in the .ps1): absolute /-separated paths only; a backslash is refused; a path starting with // is refused;
# matching of zones is case-sensitive; zones whose path is not absolute are ignored; rm of / is refused; symlinks are
# refused (also as a parent of the item, and inside a tree); protected names are matched case-insensitively (as in the .ps1).
#
# Calling convention (sh has no arrays and no local): every function returns 0 on success and 1 on refusal or failure.
# On refusal the reason is in $SRM_REASON. Lists are newline-separated strings; fields inside a list line are TAB-separated.
# A path containing a control character (including TAB and newline) is refused, so the TAB/newline framing is unambiguous.
#
#   srm_load_policy [policy_file]
#       policy: argument > <kit data>/safe-rm-policy.json > <scripts>/../policy/safe-rm-policy.default.json.
#       ${DATA} is replaced by the kit data folder. Sets SRM_DATA, SRM_POLICY_FILE, SRM_QUARANTINE_ROOT, SRM_AUDIT_FILE,
#       SRM_ROOTS (lines: root TAB minDepth TAB allowGlob(0|1) TAB maxItems), SRM_PROT_COMPONENTS_CI and SRM_PROT_NAMES_CI
#       (lines: policy text TAB case-insensitive shell pattern), SRM_MAX_FILES, SRM_MAX_BYTES, SRM_MAX_GLOB, SRM_MAX_TOKENS.
#   srm_parse_command <command-line>
#       Strict parse of one `rm [-rRfv] <path>...` string, no expansion. Sets SRM_RECURSE (0|1) and SRM_TOKENS (lines, raw
#       tokens, never containing a control character). Hand SRM_TOKENS to srm_resolve_lines.
#   srm_full_path <raw-token>          sets SRM_PATH (canonical absolute path; a wildcard stays in the last segment).
#   srm_find_root <full-path>          sets SRM_ROOT, SRM_RULE_MINDEPTH, SRM_RULE_ALLOWGLOB, SRM_RULE_MAXITEMS.
#   srm_protected <name>               returns 0 when the component is protected (sets SRM_PROT_WHY). Used per component.
#   srm_protect_rel <rel-path>         returns 0 when any component of the zone-relative path is protected (SRM_PROT_WHY).
#   srm_measure_tree <dir>             sets SRM_FILES, SRM_BYTES; refuses symlinks, protected names and caps inside the tree.
#   srm_resolve <recurse 0|1> <raw-token>...   all-or-nothing validation of argv tokens (preferred entry point).
#   srm_resolve_lines <recurse 0|1> <lines>    same for srm_parse_command output (one token per line).
#       Both set SRM_ITEMS (lines: full TAB root TAB isdir(0|1) TAB files TAB bytes) and SRM_SKIPPED (lines of text).
#   srm_join_skipped                   prints SRM_SKIPPED joined with "; ".
#   srm_has_ctl <text>                 returns 0 when the text contains a control character (0x01-0x1f).
#   srm_has_forbidden <text>           returns 0 when the text contains a shell-special or control character.
#   srm_size <file>                    prints the byte size (empty on failure).
#   srm_sha256_file <file>             prints the upper-case SHA-256 (empty on failure). srm_sha256_stdin: same for stdin.
#   srm_dir_digest <dir>               prints the upper-case SHA-256 of the sorted "rel|bytes|sha256" lines (empty on failure).
#   srm_json_array                     stdin lines -> JSON array of strings on stdout.
#   srm_expand_data <text>             replaces ${DATA} with SRM_DATA.
#   srm_normalize <absolute-path>      lexical GetFullPath for POSIX paths (., .., repeated slashes).

LC_ALL=C
export LC_ALL

command -v kit_data >/dev/null 2>&1 || . "$KIT_SCRIPT_DIR/lib.sh"

SRM_TAB=$(printf '\t')
SRM_CR=$(printf '\r')
SRM_VT=$(printf '\013')
SRM_FF=$(printf '\014')
SRM_NL=$(printf '\n_')
SRM_NL=${SRM_NL%_}

srm_has_ctl() {
  # 0 when $1 contains a control character (tr deletes them; any difference means one was present)
  [ "$(printf '%s' "$1" | tr -d '\001-\037')" = "$1" ] || return 0
  return 1
}

srm_has_forbidden() {
  case "$1" in
    *'$'*|*'`'*|*'%'*|*';'*|*'&'*|*'|'*|*'<'*|*'>'*|*"'"*|*'"'*) return 0 ;;
  esac
  srm_has_ctl "$1" && return 0
  return 1
}

srm_trim() {
  _tr_s=$1
  while :; do
    case "$_tr_s" in
      " "*|"$SRM_TAB"*|"$SRM_NL"*|"$SRM_CR"*|"$SRM_VT"*|"$SRM_FF"*) _tr_s=${_tr_s#?} ;;
      *) break ;;
    esac
  done
  while :; do
    case "$_tr_s" in
      *" "|*"$SRM_TAB"|*"$SRM_NL"|*"$SRM_CR"|*"$SRM_VT"|*"$SRM_FF") _tr_s=${_tr_s%?} ;;
      *) break ;;
    esac
  done
  printf '%s' "$_tr_s"
}

srm_normalize() {
  SRM_P=$1 awk 'BEGIN {
    p = ENVIRON["SRM_P"]
    n = split(p, a, "/"); k = 0
    for (i = 1; i <= n; i++) {
      c = a[i]
      if (c == "" || c == ".") continue
      if (c == "..") { if (k > 0) k--; continue }
      st[++k] = c
    }
    out = ""
    for (i = 1; i <= k; i++) out = out "/" st[i]
    if (out == "") out = "/"
    printf "%s", out
  }'
}

srm_abs_normalize() {
  case "$1" in
    /*) srm_normalize "$1" ;;
    *) srm_normalize "$(pwd)/$1" ;;
  esac
}

srm_expand_data() {
  _ed_in=$1
  _ed_out=""
  while :; do
    case "$_ed_in" in
      *'${DATA}'*)
        _ed_out="$_ed_out${_ed_in%%'${DATA}'*}$SRM_DATA"
        _ed_in=${_ed_in#*'${DATA}'}
        ;;
      *) break ;;
    esac
  done
  printf '%s%s' "$_ed_out" "$_ed_in"
}

# srm_opt_int <json> <dotted-path>: prints the value, 0 when absent; returns 1 when present but not a non-negative integer.
srm_opt_int() {
  if ! json_has "$1" "$2"; then printf '0'; return 0; fi
  _oi_v=$(json_get "$1" "$2")
  case "$_oi_v" in
    ''|*[!0-9]*) return 1 ;;
  esac
  printf '%s' "$_oi_v"
}

# srm_json_strings <json> <array-key>: one line per string element (${DATA} expanded). Returns 1 on a control character.
srm_json_strings() {
  _js_i=0
  while json_has "$1" "$2.$_js_i"; do
    _js_v=$(json_get "$1" "$2.$_js_i")
    srm_has_ctl "$_js_v" && return 1
    printf '%s\n' "$(srm_expand_data "$_js_v")"
    _js_i=$((_js_i + 1))
  done
  return 0
}

# srm_ci_lines <mode name|literal>: stdin lines -> "text TAB pattern". Letters become [xX] so matching is ASCII case-insensitive.
# name: wildcard pattern (* ? [..] kept), literal: exact text (glob characters escaped).
srm_ci_lines() {
  SRM_MODE=$1 awk '
    BEGIN { mode = ENVIRON["SRM_MODE"] }
    length($0) > 0 {
      s = $0; out = ""; inb = 0
      for (i = 1; i <= length(s); i++) {
        c = substr(s, i, 1)
        if (mode == "name" && c == "[") inb = 1
        if (mode == "name" && c == "]") inb = 0
        if (c ~ /[A-Za-z]/ && mode == "literal") out = out "[" tolower(c) toupper(c) "]"
        else if (c ~ /[A-Za-z]/ && mode == "name" && !inb) out = out "[" tolower(c) toupper(c) "]"
        else if (mode == "literal" && index("*?[]\\", c) > 0) out = out "\\" c
        else out = out c
      }
      print s "\t" out
    }'
}

srm_load_policy() {
  SRM_REASON=""
  SRM_DATA=$(kit_data)
  lp_file=$1
  if [ -z "$lp_file" ]; then
    lp_file="$SRM_DATA/safe-rm-policy.json"
    [ -e "$lp_file" ] || lp_file="$KIT_SCRIPT_DIR/../policy/safe-rm-policy.default.json"
  fi
  SRM_POLICY_FILE=$lp_file
  if [ ! -f "$lp_file" ] || [ ! -r "$lp_file" ]; then SRM_REASON="cannot read policy file '$lp_file'"; return 1; fi
  lp_json=$(cat "$lp_file" 2>/dev/null) || { SRM_REASON="cannot read policy file '$lp_file'"; return 1; }
  lp_bom=$(printf '\357\273\277')
  lp_json=${lp_json#"$lp_bom"}
  lp_t=$(srm_trim "$lp_json")
  case "$lp_t" in
    "{"*) ;;
    *) SRM_REASON="policy is not a JSON object ('$lp_file')"; return 1 ;;
  esac

  lp_v=$(json_get "$lp_json" quarantineRoot) || lp_v=""
  if [ -z "$lp_v" ] || srm_has_ctl "$lp_v"; then SRM_REASON="policy has no valid quarantineRoot"; return 1; fi
  SRM_QUARANTINE_ROOT=$(srm_abs_normalize "$(srm_expand_data "$lp_v")")

  lp_v=$(json_get "$lp_json" auditFile) || lp_v=""
  if [ -z "$lp_v" ] || srm_has_ctl "$lp_v"; then SRM_REASON="policy has no valid auditFile"; return 1; fi
  SRM_AUDIT_FILE=$(srm_abs_normalize "$(srm_expand_data "$lp_v")")

  lp_roots=""; lp_i=0
  while json_has "$lp_json" "allowedRoots.$lp_i.path"; do
    lp_p=$(json_get "$lp_json" "allowedRoots.$lp_i.path")
    lp_p=$(srm_expand_data "$lp_p")
    if [ -z "$lp_p" ] || srm_has_ctl "$lp_p"; then SRM_REASON="invalid policy: allowedRoots.$lp_i.path"; return 1; fi
    lp_md=$(srm_opt_int "$lp_json" "allowedRoots.$lp_i.minDepth") || { SRM_REASON="invalid policy: allowedRoots.$lp_i.minDepth"; return 1; }
    lp_mi=$(srm_opt_int "$lp_json" "allowedRoots.$lp_i.maxItems") || { SRM_REASON="invalid policy: allowedRoots.$lp_i.maxItems"; return 1; }
    lp_ag=0
    if json_has "$lp_json" "allowedRoots.$lp_i.allowGlob"; then
      case "$(json_get "$lp_json" "allowedRoots.$lp_i.allowGlob")" in true|1) lp_ag=1 ;; esac
    fi
    case "$lp_p" in /*) lp_p=$(srm_normalize "$lp_p") ;; esac
    lp_roots="$lp_roots$lp_p$SRM_TAB$lp_md$SRM_TAB$lp_ag$SRM_TAB$lp_mi$SRM_NL"
    lp_i=$((lp_i + 1))
  done
  SRM_ROOTS=$lp_roots

  lp_pc=$(srm_json_strings "$lp_json" protectedComponents) || { SRM_REASON="invalid policy: protectedComponents"; return 1; }
  lp_pn=$(srm_json_strings "$lp_json" protectedNames) || { SRM_REASON="invalid policy: protectedNames"; return 1; }
  SRM_PROT_COMPONENTS_CI=$(printf '%s\n' "$lp_pc" | srm_ci_lines literal)
  SRM_PROT_NAMES_CI=$(printf '%s\n' "$lp_pn" | srm_ci_lines name)

  SRM_MAX_FILES=$(srm_opt_int "$lp_json" caps.maxFiles) || { SRM_REASON="invalid policy: caps.maxFiles"; return 1; }
  SRM_MAX_BYTES=$(srm_opt_int "$lp_json" caps.maxBytes) || { SRM_REASON="invalid policy: caps.maxBytes"; return 1; }
  SRM_MAX_GLOB=$(srm_opt_int "$lp_json" caps.maxGlobMatches) || { SRM_REASON="invalid policy: caps.maxGlobMatches"; return 1; }
  SRM_MAX_TOKENS=$(srm_opt_int "$lp_json" caps.maxTokens) || { SRM_REASON="invalid policy: caps.maxTokens"; return 1; }
  [ "$SRM_MAX_TOKENS" -gt 0 ] || SRM_MAX_TOKENS=20
  return 0
}

srm_join_skipped() {
  printf '%s' "$SRM_SKIPPED" | awk 'length($0) > 0 { if (n++) printf "; "; printf "%s", $0 }'
}

# srm_parse_command <command-line>: strict tokenizer, same rules as ConvertFrom-SafeRmCommand.
srm_parse_command() {
  SRM_REASON=""; SRM_RECURSE=0; SRM_TOKENS=""
  [ -n "${SRM_MAX_TOKENS:-}" ] || SRM_MAX_TOKENS=20
  pc_c=$(srm_trim "$1")
  case "$pc_c" in
    rm|"rm "*|"rm$SRM_TAB"*|"rm$SRM_NL"*|"rm$SRM_CR"*) ;;
    *) SRM_REASON='not an rm command'; return 1 ;;
  esac
  pc_r=${pc_c#rm}
  pc_flags=1; pc_n=0
  while :; do
    while :; do
      case "$pc_r" in
        " "*|"$SRM_TAB"*|"$SRM_NL"*|"$SRM_CR"*|"$SRM_VT"*|"$SRM_FF"*) pc_r=${pc_r#?} ;;
        *) break ;;
      esac
    done
    [ -n "$pc_r" ] || break
    pc_ch=${pc_r%"${pc_r#?}"}
    case "$pc_ch" in
      '"'|"'")
        pc_after=${pc_r#?}
        case "$pc_after" in
          *"$pc_ch"*) ;;
          *) SRM_REASON='unterminated quote'; return 1 ;;
        esac
        pc_tok=${pc_after%%"$pc_ch"*}
        pc_r=${pc_after#*"$pc_ch"}
        if [ -n "$pc_r" ]; then
          case "$pc_r" in
            " "*|"$SRM_TAB"*|"$SRM_NL"*|"$SRM_CR"*|"$SRM_VT"*|"$SRM_FF"*) ;;
            *) SRM_REASON='text glued to a quoted argument'; return 1 ;;
          esac
        fi
        if srm_has_forbidden "$pc_tok"; then SRM_REASON='forbidden character in quoted path'; return 1; fi
        [ -n "$pc_tok" ] || { SRM_REASON='empty path'; return 1; }
        pc_flags=0
        ;;
      *)
        pc_tok=""
        while [ -n "$pc_r" ]; do
          pc_c2=${pc_r%"${pc_r#?}"}
          case "$pc_c2" in
            " "|"$SRM_TAB"|"$SRM_NL"|"$SRM_CR"|"$SRM_VT"|"$SRM_FF") break ;;
          esac
          pc_tok="$pc_tok$pc_c2"
          pc_r=${pc_r#?}
        done
        case "$pc_tok" in
          -*)
            if [ "$pc_flags" = 1 ] && printf '%s' "$pc_tok" | grep -Eq '^-[A-Za-z]+$'; then
              if ! printf '%s' "$pc_tok" | grep -Eq '^-[rRfv]+$'; then
                SRM_REASON="unsupported rm option '$pc_tok' (only -r, -R, -f, -v)"; return 1
              fi
              case "$pc_tok" in *[rR]*) SRM_RECURSE=1 ;; esac
              continue
            fi
            SRM_REASON="unsupported rm option '$pc_tok'"; return 1
            ;;
        esac
        if ! printf '%s' "$pc_tok" | grep -Eq '^[A-Za-z0-9_./:@+=,*?-]+$'; then
          SRM_REASON="unquoted path has shell-special characters ('$pc_tok'); use plain /-separated paths or quote the path"
          return 1
        fi
        pc_flags=0
        ;;
    esac
    SRM_TOKENS="$SRM_TOKENS$pc_tok$SRM_NL"
    pc_n=$((pc_n + 1))
  done
  [ "$pc_n" -gt 0 ] || { SRM_REASON='no path given'; return 1; }
  if [ "$pc_n" -gt "$SRM_MAX_TOKENS" ]; then SRM_REASON="too many paths ($pc_n > $SRM_MAX_TOKENS)"; return 1; fi
  return 0
}

# srm_full_path <raw>: ConvertTo-SafeRmFullPath, POSIX branch.
srm_full_path() {
  SRM_PATH=""
  fp_raw=$1
  fp_s=$(srm_trim "$fp_raw")
  [ -n "$fp_s" ] || { SRM_REASON='empty path'; return 1; }
  if srm_has_forbidden "$fp_s"; then SRM_REASON="forbidden character in path '$fp_raw'"; return 1; fi
  case "$fp_s" in
    //*) SRM_REASON="network/UNC and device paths are not allowed ('$fp_raw')"; return 1 ;;
  esac
  case "$fp_s" in
    *'\'*) SRM_REASON="backslashes are not allowed in paths on this platform ('$fp_raw')"; return 1 ;;
  esac
  case "$fp_s" in
    /*) ;;
    *) SRM_REASON="path must be absolute (start with /): '$fp_raw'"; return 1 ;;
  esac
  fp_leafglob=""
  fp_last=${fp_s##*/}
  case "$fp_last" in
    *[*?]*)
      fp_leafglob=$fp_last
      fp_s=${fp_s%"$fp_last"}
      ;;
  esac
  case "$fp_s" in
    *[*?]*) SRM_REASON="wildcards are only allowed in the last path segment ('$fp_raw')"; return 1 ;;
  esac
  fp_full=$(srm_normalize "$fp_s")
  if [ -n "$fp_leafglob" ]; then
    fp_base=${fp_full%/}
    fp_full="$fp_base/$fp_leafglob"
  fi
  SRM_PATH=$fp_full
  return 0
}

# srm_protected <name>: case-insensitive match against protectedComponents (literal) and protectedNames (wildcard).
srm_protected() {
  _pr_c=$1
  while IFS="$SRM_TAB" read -r _pr_o _pr_p; do
    [ -n "$_pr_p" ] || continue
    case "$_pr_c" in
      $_pr_p) SRM_PROT_WHY="protected folder '$_pr_c'"; return 0 ;;
    esac
  done <<SRM_PC
$SRM_PROT_COMPONENTS_CI
SRM_PC
  while IFS="$SRM_TAB" read -r _pr_o _pr_p; do
    [ -n "$_pr_p" ] || continue
    case "$_pr_c" in
      $_pr_p) SRM_PROT_WHY="protected name '$_pr_c' (matches '$_pr_o')"; return 0 ;;
    esac
  done <<SRM_PN
$SRM_PROT_NAMES_CI
SRM_PN
  return 1
}

# srm_protect_rel <rel>: returns 0 when a component of the zone-relative path is protected.
srm_protect_rel() {
  _pq_rest=$1
  _pq_last=0
  while :; do
    case "$_pq_rest" in
      */*) _pq_c=${_pq_rest%%/*}; _pq_rest=${_pq_rest#*/} ;;
      *) _pq_c=$_pq_rest; _pq_last=1 ;;
    esac
    if srm_protected "$_pq_c"; then return 0; fi
    [ "$_pq_last" = 1 ] && break
  done
  return 1
}

# srm_find_root <full>: first allowed zone that strictly contains the path (ZoneRoot + "/" prefix, case-sensitive).
srm_find_root() {
  fr_full=$1
  SRM_ROOT=""; SRM_RULE_MINDEPTH=0; SRM_RULE_ALLOWGLOB=0; SRM_RULE_MAXITEMS=0
  while IFS="$SRM_TAB" read -r fr_p fr_md fr_ag fr_mi; do
    [ -n "$fr_p" ] || continue
    case "$fr_p" in /*) ;; *) continue ;; esac
    fr_root=$fr_p
    [ "$fr_root" = / ] && fr_root=""
    if [ "${#fr_full}" -gt "${#fr_root}" ]; then
      case "$fr_full" in
        "$fr_root"/*)
          SRM_ROOT=$fr_root
          SRM_RULE_MINDEPTH=$fr_md
          SRM_RULE_ALLOWGLOB=$fr_ag
          SRM_RULE_MAXITEMS=$fr_mi
          return 0
          ;;
      esac
    fi
  done <<SRM_RT
$SRM_ROOTS
SRM_RT
  return 1
}

srm_size() {
  stat -c %s "$1" 2>/dev/null || stat -f %z "$1" 2>/dev/null
}

srm_sha256_stdin() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{ print $1 }'
  else
    shasum -a 256 | awk '{ print $1 }'
  fi | tr 'a-f' 'A-F'
}

srm_sha256_file() {
  [ -r "$1" ] || return 1
  srm_sha256_stdin < "$1"
}

# srm_dir_digest <dir>: same algorithm as the .ps1 (sorted "rel|bytes|sha256" lines joined by LF, SHA-256 of the UTF-8 text).
srm_dir_digest() {
  dd_dir=$1
  dd_tmp=$(mktemp -d) || return 1
  dd_list="$dd_tmp/list"
  dd_lines="$dd_tmp/lines"
  if ! find "$dd_dir" -mindepth 1 -type f > "$dd_list" 2>/dev/null; then rm -rf "$dd_tmp"; return 1; fi
  : > "$dd_lines"
  while IFS= read -r dd_f; do
    dd_rel=${dd_f#"$dd_dir"/}
    dd_sz=$(srm_size "$dd_f")
    dd_h=$(srm_sha256_file "$dd_f")
    if [ -z "$dd_sz" ] || [ -z "$dd_h" ]; then rm -rf "$dd_tmp"; return 1; fi
    printf '%s|%s|%s\n' "$dd_rel" "$dd_sz" "$dd_h" >> "$dd_lines"
  done < "$dd_list"
  dd_text=$(LC_ALL=C sort "$dd_lines")
  printf '%s' "$dd_text" | srm_sha256_stdin
  rm -rf "$dd_tmp"
}

srm_count_segments() {
  SRM_NCOMP=1
  _cs_rest=$1
  while :; do
    case "$_cs_rest" in
      */*) SRM_NCOMP=$((SRM_NCOMP + 1)); _cs_rest=${_cs_rest#*/} ;;
      *) break ;;
    esac
  done
}

# srm_measure_tree <dir>: walk without following links (find lists, never descends a symlink).
srm_measure_tree() {
  mt_dir=$1
  SRM_FILES=0; SRM_BYTES=0
  mt_fail=""
  mt_tmp=$(mktemp) || { SRM_REASON='cannot create a temp file'; return 1; }
  if ! find "$mt_dir" -mindepth 1 > "$mt_tmp" 2>/dev/null; then
    rm -f "$mt_tmp"; SRM_REASON="cannot list '$mt_dir'"; return 1
  fi
  if LC_ALL=C grep -q '[[:cntrl:]]' "$mt_tmp"; then
    rm -f "$mt_tmp"; SRM_REASON="'$mt_dir' contains a file name with a control character"; return 1
  fi
  mt_pre="$mt_dir/"
  while IFS= read -r mt_e; do
    case "$mt_e" in
      "$mt_pre"?*) ;;
      *) mt_fail="'$mt_dir' contains a file name with a line break"; break ;;
    esac
    if [ -L "$mt_e" ]; then mt_fail="contains a symlink or junction ('$mt_e')"; break; fi
    if srm_protected "${mt_e##*/}"; then mt_fail="contains a $SRM_PROT_WHY ('$mt_e')"; break; fi
    if [ ! -d "$mt_e" ]; then
      SRM_FILES=$((SRM_FILES + 1))
      mt_sz=$(srm_size "$mt_e")
      case "$mt_sz" in
        ''|*[!0-9]*) mt_fail="cannot read the size of '$mt_e'"; break ;;
      esac
      SRM_BYTES=$((SRM_BYTES + mt_sz))
      if [ "$SRM_FILES" -gt "$SRM_MAX_FILES" ]; then mt_fail="too many files (> $SRM_MAX_FILES)"; break; fi
      if [ "$SRM_BYTES" -gt "$SRM_MAX_BYTES" ]; then mt_fail="too large (> $SRM_MAX_BYTES bytes)"; break; fi
    fi
  done < "$mt_tmp"
  rm -f "$mt_tmp"
  if [ -n "$mt_fail" ]; then SRM_REASON=$mt_fail; return 1; fi
  return 0
}

# srm_resolve_cand <recurse> <candidate> <token>: one existing or missing candidate path (Resolve-SafeRmPaths inner loop).
srm_resolve_cand() {
  rc_rec=$1; rc_c=$2; rc_tok=$3
  if srm_has_ctl "$rc_c"; then SRM_REASON="'$rc_c' contains a control character"; return 1; fi
  if ! srm_find_root "$rc_c"; then
    SRM_REASON="'$rc_c' is outside the allowed zones (or is a zone root itself)"; return 1
  fi
  rc_root=$SRM_ROOT; rc_md=$SRM_RULE_MINDEPTH; rc_mi=$SRM_RULE_MAXITEMS
  rc_rel=${rc_c#"$rc_root"/}
  srm_count_segments "$rc_rel"
  if [ "$SRM_NCOMP" -lt "$rc_md" ]; then
    SRM_REASON="'$rc_c' is too close to the zone root (minimum depth $rc_md)"; return 1
  fi
  if srm_protect_rel "$rc_rel"; then SRM_REASON="'$rc_c' is blocked: $SRM_PROT_WHY"; return 1; fi
  if [ ! -e "$rc_c" ] && [ ! -L "$rc_c" ]; then
    SRM_SKIPPED="$SRM_SKIPPED$rc_c (does not exist)$SRM_NL"; return 0
  fi
  if [ -L "$rc_c" ]; then SRM_REASON="'$rc_c' is a symlink or junction"; return 1; fi
  rc_w=${rc_c%/*}
  while [ -n "$rc_w" ] && [ "${#rc_w}" -gt "${#rc_root}" ]; do
    if [ -L "$rc_w" ]; then SRM_REASON="'$rc_c' sits below a symlink or junction ('$rc_w')"; return 1; fi
    rc_w=${rc_w%/*}
  done
  if [ -d "$rc_c" ]; then
    rc_isdir=1
    if [ "$rc_rec" != 1 ]; then SRM_REASON="'$rc_c' is a directory; use rm -r"; return 1; fi
    if ! srm_measure_tree "$rc_c"; then SRM_REASON="'$rc_c': $SRM_REASON"; return 1; fi
    rc_files=$SRM_FILES; rc_bytes=$SRM_BYTES
  else
    rc_isdir=0; rc_files=1
    rc_bytes=$(srm_size "$rc_c")
    case "$rc_bytes" in
      ''|*[!0-9]*) SRM_REASON="cannot read the size of '$rc_c'"; return 1 ;;
    esac
    if [ "$rc_bytes" -gt "$SRM_MAX_BYTES" ]; then
      SRM_REASON="'$rc_c' is too large (> $SRM_MAX_BYTES bytes)"; return 1
    fi
  fi
  rc_key=${rc_root:-/}
  rc_cnt=$(printf '%s' "$SRM_PER_ROOT" | grep -c -x -F -- "$rc_key" 2>/dev/null)
  rc_cnt=$((${rc_cnt:-0} + 1))
  if [ "$rc_cnt" -gt "$rc_mi" ]; then
    SRM_REASON="too many items in zone '$rc_root' (max $rc_mi per command)"; return 1
  fi
  SRM_PER_ROOT="$SRM_PER_ROOT$rc_key$SRM_NL"
  SRM_ITEMS="$SRM_ITEMS$rc_c$SRM_TAB$rc_key$SRM_TAB$rc_isdir$SRM_TAB$rc_files$SRM_TAB$rc_bytes$SRM_NL"
  return 0
}

# srm_resolve_one <recurse> <raw-token>: expands a leaf wildcard (only in allowGlob zones), then validates each candidate.
srm_resolve_one() {
  ro_rec=$1; ro_tok=$2
  srm_full_path "$ro_tok" || return 1
  ro_full=$SRM_PATH
  if [ "$ro_full" = / ]; then SRM_REASON="a filesystem root cannot be deleted ('$ro_tok')"; return 1; fi
  ro_leaf=${ro_full##*/}
  ro_parent=${ro_full%/*}
  [ -n "$ro_parent" ] || ro_parent=/
  case "$ro_parent" in
    *[*?]*) SRM_REASON="wildcards are only allowed in the last path segment ('$ro_tok')"; return 1 ;;
  esac
  ro_isglob=0
  case "$ro_leaf" in *[*?]*) ro_isglob=1 ;; esac
  if [ "$ro_isglob" = 1 ]; then
    ro_pp=${ro_parent%/}
    if ! srm_find_root "$ro_pp/x"; then SRM_REASON="'$ro_tok' is outside the allowed zones"; return 1; fi
    if [ "$SRM_RULE_ALLOWGLOB" != 1 ]; then
      SRM_REASON="wildcards are not allowed in this zone; name each item ('$ro_tok')"; return 1
    fi
    ro_list=""; ro_n=0
    if [ -d "$ro_parent" ]; then
      for ro_e in "$ro_pp"/* "$ro_pp"/.[!.]* "$ro_pp"/..?*; do
        if [ -e "$ro_e" ] || [ -L "$ro_e" ]; then
          ro_nm=${ro_e##*/}
          case "$ro_nm" in
            $ro_leaf) ro_list="$ro_list$ro_e$SRM_NL"; ro_n=$((ro_n + 1)) ;;
          esac
        fi
      done
    fi
    if [ "$ro_n" -gt "$SRM_MAX_GLOB" ]; then
      SRM_REASON="'$ro_tok' matches too many items ($ro_n > $SRM_MAX_GLOB)"; return 1
    fi
    if [ "$ro_n" -eq 0 ]; then
      SRM_SKIPPED="$SRM_SKIPPED$ro_tok (no match)$SRM_NL"; return 0
    fi
  else
    ro_list="$ro_full$SRM_NL"
  fi
  while IFS= read -r ro_c; do
    [ -n "$ro_c" ] || continue
    srm_resolve_cand "$ro_rec" "$ro_c" "$ro_tok" || return 1
  done <<SRM_RO
$ro_list
SRM_RO
  return 0
}

# srm_resolve <recurse> <raw-token>...: argv tokens, all or nothing.
srm_resolve() {
  SRM_ITEMS=""; SRM_SKIPPED=""; SRM_PER_ROOT=""
  rs_rec=$1
  shift
  [ $# -gt 0 ] || { SRM_REASON='no path given'; return 1; }
  for rs_t in "$@"; do
    srm_resolve_one "$rs_rec" "$rs_t" || return 1
  done
  return 0
}

# srm_resolve_lines <recurse> <lines>: tokens from srm_parse_command (one per line).
srm_resolve_lines() {
  SRM_ITEMS=""; SRM_SKIPPED=""; SRM_PER_ROOT=""
  rl_rec=$1
  rl_n=0
  while IFS= read -r rl_t; do
    [ -n "$rl_t" ] || continue
    rl_n=$((rl_n + 1))
    srm_resolve_one "$rl_rec" "$rl_t" || return 1
  done <<SRM_RL
$2
SRM_RL
  [ "$rl_n" -gt 0 ] || { SRM_REASON='no path given'; return 1; }
  return 0
}

# srm_json_array: stdin lines -> ["a","b"] (json_str from lib.sh quotes and escapes each value).
srm_json_array() {
  printf '['
  ja_sep=""
  while IFS= read -r ja_l; do
    [ -n "$ja_l" ] || continue
    printf '%s%s' "$ja_sep" "$(json_str "$ja_l")"
    ja_sep=","
  done
  printf ']'
}
