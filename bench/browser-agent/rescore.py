"""Re-applies the CURRENT scorers to stored answers of tasks whose scorer was corrected after the runs (answer-only tasks).

  python rescore.py            # prints what would change
  python rescore.py --write    # rewrites results/runs.jsonl (original verdict kept in `passed_before`)
Only tasks whose verdict depends on the answer alone are re-scored (E2, E5, E6, H1, H2, H4, H5); log-dependent tasks are left untouched.
"""
import json
import sys

from bench import BASE_Q, RUNS

ANSWER_ONLY = {"E2", "E5", "E6", "H1", "H2", "H4", "H5"}


def main():
    rows = [json.loads(x) for x in RUNS.read_text(encoding="utf-8").splitlines() if x.strip()]
    changed = 0
    for r in rows:
        if r["task"] in ANSWER_ONLY and r.get("answer") is not None and "error" not in r:
            ok, _ = BASE_Q[r["task"]][1](r["answer"], [])
            if bool(ok) != bool(r["passed"]):
                changed += 1
                print(f"{r['cond']} {r['task']} r{r['rep']}: {r['passed']} -> {ok}")
                r["passed_before"] = r["passed"]
                r["passed"] = bool(ok)
    print(f"{changed} verdict(s) changed")
    if "--write" in sys.argv and changed:
        RUNS.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        print("written")


main()
