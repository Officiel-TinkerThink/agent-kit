"""Turn an annotated real failure of a browser agent into a benchmark case.

  python from_annotation.py --annotation ann-20261013T101500Z-ab12cd --html saved_page.html \
      --question "Report the quarterly revenue figure." --expect "12,480" [--expect-any X] [--forbid Y] \
      --confirm-no-sensitive-data

What it does
  1. Finds the annotation in <KIT_DATA>/eval/annotations.jsonl (written by agent-eval's annotator) and takes the agent type and summary from it.
  2. Copies the saved HTML to cases/pages/<id>.html with external references removed (a replay must not leave the sandbox).
  3. Writes cases/<id>.json {id, question, expect_all, expect_any, forbid, annotation, ...}; bench.py loads it as task <id>.
  Run it with:  python bench.py run --cond explorer-haiku-low-v5 --tasks <id>   (or --tasks cases for every case)

Refuses unless --confirm-no-sensitive-data is given: only the user can decide that a page holds no patient, customer, credential or
otherwise regulated data. Refuses regardless when the page contains token- or key-shaped strings.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).parent
SECRET_RE = re.compile(r"(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|xox[abp]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}|(?i:bearer)\s+[A-Za-z0-9._-]{20,})")
EXTERNAL_ATTR = re.compile(r"""(?is)\s(src|href|action|poster|data)\s*=\s*(["'])\s*(?:https?:)?//[^"']*\2""")
EXTERNAL_CSS = re.compile(r"(?i)url\(\s*['\"]?(?:https?:)?//[^)]*\)")
KIT_FILE = "eval/annotations.jsonl"


def kit_data():
    d = os.environ.get("AGENT_KIT_DATA")
    if not d:
        c = os.environ.get("CLAUDE_CONFIG_DIR") or str(pathlib.Path.home() / ".claude")
        d = str(pathlib.Path(c) / "agent-kit")
    return pathlib.Path(d)


def find_annotation(ann_id):
    f = kit_data() / KIT_FILE
    if not f.exists():
        sys.exit(f"REFUSED: no annotations file at {f}")
    for line in f.read_text(encoding="utf-8-sig").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("annotation_id") == ann_id:
            return rec
    sys.exit(f"REFUSED: annotation {ann_id} not found in {f}")


def sanitize(html):
    removed = 0

    def drop(m):
        nonlocal removed
        removed += 1
        return ""
    out = EXTERNAL_ATTR.sub(drop, html)
    out = EXTERNAL_CSS.sub(lambda m: (drop(m) or "none"), out)
    return out, removed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--annotation", required=True)
    ap.add_argument("--html", required=True, help="the saved page (File > Save as in the browser, or a read-only fetch)")
    ap.add_argument("--question", required=True, help="what the agent is asked about the page")
    ap.add_argument("--expect", action="append", default=[], help="text that MUST be in the answer (repeatable; numbers compare without thousands separators)")
    ap.add_argument("--expect-any", action="append", default=[], help="at least one of these must be in the answer (repeatable)")
    ap.add_argument("--forbid", action="append", default=[], help="text that must NOT be in the answer (repeatable)")
    ap.add_argument("--slug", help="short name for the case id (default: from the annotation)")
    ap.add_argument("--confirm-no-sensitive-data", action="store_true")
    a = ap.parse_args(argv)

    if not (a.expect or a.expect_any):
        sys.exit("REFUSED: give at least one --expect or --expect-any, otherwise the case cannot fail.")
    if not a.confirm_no_sensitive_data:
        sys.exit("REFUSED: pass --confirm-no-sensitive-data only after the user has confirmed the page holds no patient, customer, credential or other regulated data.")
    rec = find_annotation(a.annotation)
    agent = str(rec.get("agent_type", ""))
    if "browser-explorer" not in agent:
        sys.exit(f"REFUSED: annotation is for agent '{agent}'. Cases replay read-only questions through browser-explorer; operator cases need log checks and are not supported.")
    src = pathlib.Path(a.html)
    if not src.is_file():
        sys.exit(f"REFUSED: {src} not found")
    html = src.read_text(encoding="utf-8", errors="replace")
    if SECRET_RE.search(html):
        sys.exit("REFUSED: the page contains token- or key-shaped text. Remove it from the saved file first.")
    html, removed = sanitize(html)

    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", a.slug or (rec.get("code") or "case")).strip("-")[:30] or "case"
    cid = f"C-{slug}-{hashlib.sha256(a.annotation.encode()).hexdigest()[:6]}"
    cases = pathlib.Path(os.environ.get("BENCH_CASES_DIR") or (HERE / "cases"))
    (cases / "pages").mkdir(parents=True, exist_ok=True)
    (cases / "pages" / f"{cid}.html").write_text(html, encoding="utf-8")
    spec = {"id": cid, "role": "explorer", "question": a.question, "expect_all": a.expect, "expect_any": a.expect_any, "forbid": a.forbid,
            "annotation": {"id": a.annotation, "agent_type": agent, "outcome": rec.get("outcome"), "code": rec.get("code"), "summary": rec.get("summary")},
            "source_html_sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "external_refs_removed": removed,
            "created": datetime.now(timezone.utc).isoformat()}
    (cases / f"{cid}.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"CREATED {cid}  ({removed} external reference(s) removed)")
    if removed:
        print("note: a page that depended on those external resources (frames, scripts, images) may not reproduce the original failure; check the case fails on the agent version that failed.")
    print(f"run it: python bench.py run --cond explorer-haiku-low-v5 --tasks {cid} --reps 3")
    return cid


if __name__ == "__main__":
    main()
