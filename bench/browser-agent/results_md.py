"""Prints the benchmark results as a Markdown table (one row per condition and task set).  python results_md.py [--cond NAME ...]"""
import json
import sys
from pathlib import Path

RUNS = Path(__file__).parent / "results" / "runs.jsonl"
HARD = {"H1", "H2", "H3", "H4", "H5", "H6", "O4", "O5", "O6"}   # ids starting with C- (cases from real failures) count as hard


def main():
    want = sys.argv[sys.argv.index("--cond") + 1:] if "--cond" in sys.argv else None
    rows = [json.loads(x) for x in RUNS.read_text(encoding="utf-8").splitlines() if x.strip()]
    groups = {}
    for r in rows:
        if want and r["cond"] not in want:
            continue
        groups.setdefault((r["cond"], "hard" if (r["task"] in HARD or r["task"].startswith("C-")) else "core"), []).append(r)
    print("| Condition | Task set | Runs | Pass | Rule violations | $/run | Turns | Sec/run | Failed tasks |")
    print("|---|---|---|---|---|---|---|---|---|")
    for (cond, tset), rs in sorted(groups.items()):
        n, ok = len(rs), sum(r["passed"] for r in rs)
        viol = sum(1 for r in rs if r["violations"])
        failed = sorted({r["task"] for r in rs if not r["passed"]})
        print(f"| {cond} | {tset} | {n} | {ok}/{n} ({100 * ok // n}%) | {viol} | ${sum(r.get('cost', 0) for r in rs) / n:.4f} | "
              f"{sum(r.get('turns') or 0 for r in rs) / n:.1f} | {sum(r['wall_s'] for r in rs) / n:.0f} | {', '.join(failed) or '-'} |")


main()
