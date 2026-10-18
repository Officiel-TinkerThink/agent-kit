"""Sandbox tests for safe-rm.ps1 / safe-rm-lib.ps1 / safe-rm-restore.ps1. Real files, real junctions, a throwaway policy.
Run: python test_safe_rm.py   (creates and removes a folder under %LOCALAPPDATA%\\Temp; never touches your real policy, quarantine or audit file)."""
import sys as _sys
import json, os, pathlib, random, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from capability import run_capability   # the OS adapter picks the implementation (PowerShell on Windows, sh on Linux)

HOOKS = pathlib.Path(__file__).resolve().parents[2] / 'plugins' / 'verification-runner' / 'scripts'
RM = HOOKS / "safe-rm.ps1"
RESTORE = HOOKS / "safe-rm-restore.ps1"
IS_WIN = _sys.platform == 'win32'
import tempfile
LONG_TEMP = (pathlib.Path(os.path.expanduser("~")) / "AppData" / "Local" / "Temp") if IS_WIN else pathlib.Path(tempfile.gettempdir())   # Windows: long (non-8.3) path on purpose
SB = LONG_TEMP / f"srm-test-{random.randrange(10**8):08d}"
results = []


def posix(p) -> str:
    return str(p).replace("\\", "/")


def make_policy(name="policy.json", **caps_over):
    caps = {"maxFiles": 50, "maxBytes": 1_000_000, "maxGlobMatches": 5, "maxTokens": 20}
    caps.update(caps_over)
    pol = {
        "version": 1,
        "quarantineRoot": posix(SB / "q"),
        "auditFile": posix(SB / "audit.jsonl"),
        "allowedRoots": [
            {"path": posix(SB / "logs"), "minDepth": 1, "allowGlob": False, "maxItems": 1},
            {"path": posix(SB / "proj"), "minDepth": 2, "allowGlob": True, "maxItems": 4},
        ],
        "protectedComponents": [".git", ".venv", "quarantine"],
        "protectedNames": [".env", ".env.*", "*.pem", "_deletions.jsonl", "*.db"],
        "caps": caps,
    }
    p = SB / name
    p.write_text(json.dumps(pol), encoding="utf8")
    return p


def ps(script, *args):
    r = run_capability(script, *args, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def rm(*paths, recurse=False, dry=False, policy=None):
    args = ["-PolicyFile", str(policy or POLICY)]
    if recurse: args.append("-Recurse")
    if dry: args.append("-DryRun")
    args += ["-Agent", "test", "-Session", "t1"]
    args += [posix(p) if isinstance(p, pathlib.Path) else p for p in paths]
    return ps(RM, *args)


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else f"   <-- {detail}"))


def write(p, text="x"):
    p = pathlib.Path(p); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text); return p


def audit_lines():
    f = SB / "audit.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf8").splitlines()] if f.exists() else []


def refused(name, r, still):
    check(name + " -> refused", r[0] == 2 and "REFUSED" in r[2], f"code={r[0]} err={r[2][:160]}")
    check(name + " -> untouched", all(pathlib.Path(p).exists() for p in still), "an item vanished")


if SB.exists(): shutil.rmtree(SB)
(SB / "logs").mkdir(parents=True); (SB / "proj").mkdir(); (SB / "other").mkdir()
POLICY = make_policy()
P = SB / "proj"

try:
    # ---- happy paths ----
    f = write(P / "app" / "sub" / "a.txt", "hello")
    r = rm(f)
    check("file: moved", r[0] == 0 and not f.exists() and "QUARANTINED" in r[1], f"{r}")
    qdirs = [d for d in (SB / "q").iterdir() if d.is_dir()]
    check("file: quarantine entry + manifest", len(qdirs) == 1 and (qdirs[0] / "manifest.json").exists())
    man = json.loads((qdirs[0] / "manifest.json").read_text(encoding="utf8"))
    check("file: manifest has sha256 and status", man["status"] == "done" and len(man["items"][0]["sha256"]) == 64)
    moved = pathlib.Path(man["items"][0]["quarantinePath"])
    check("file: content preserved in quarantine", moved.exists() and moved.read_text() == "hello")
    a = audit_lines()
    check("file: audit planned+completed, no BOM", [x["phase"] for x in a] == ["planned", "completed"] and not (SB / "audit.jsonl").read_bytes().startswith(b"\xef\xbb\xbf"))
    check("file: audit records agent/session", a[0]["agent"] == "test" and a[0]["session"] == "t1")

    d = P / "app" / "cache"; write(d / "x.pyc"); write(d / "deep" / "y.pyc")
    refused("dir without -r", rm(d), [d])
    r = rm(d, recurse=True)
    check("dir with -r: moved", r[0] == 0 and not d.exists(), f"{r}")

    for n in ("1.tmp", "2.tmp", "keep.txt"): write(P / "app" / "g" / n)
    r = rm(P / "app" / "g" / "*.tmp")
    check("glob: only matches moved", r[0] == 0 and not (P / "app/g/1.tmp").exists() and not (P / "app/g/2.tmp").exists() and (P / "app/g/keep.txt").exists(), f"{r}")

    r = rm(P / "app" / "g" / "*.zzz")
    check("glob: no match is a no-op", r[0] == 0 and "NOTHING TO DELETE" in r[1])
    r = rm(P / "app" / "nope.txt")
    check("nonexistent: no-op", r[0] == 0 and "NOTHING TO DELETE" in r[1])

    f = write(P / "app" / "dry.txt")
    r = rm(f, dry=True)
    check("dry run: nothing moved", r[0] == 0 and f.exists() and "WOULD QUARANTINE" in r[1])

    f = write(P / "app" / "gb.txt")
    if IS_WIN:
        gb = "/" + posix(f)[0].lower() + posix(f)[2:]
        r = rm(gb)
        check("git-bash style /c/... path accepted", r[0] == 0 and not f.exists(), f"{r}")

    # ---- zone rules ----
    f = write(SB / "other" / "o.txt")
    refused("outside zones", rm(f), [f])
    refused("zone root itself", rm(P, recurse=True), [P])
    f = write(P / "top.txt")
    refused("too shallow (minDepth 2)", rm(f), [f])
    f = write(P / "app" / "t.txt")
    refused("traversal out of zone", rm(posix(P / "app" / ".." / ".." / "other" / "o.txt")), [SB / "other" / "o.txt"])
    f1 = write(SB / "logs" / "one.log"); f2 = write(SB / "logs" / "two.log")
    refused("glob in no-glob zone", rm(SB / "logs" / "*.log"), [f1, f2])
    r = rm(f1)
    check("single named item in logs zone ok", r[0] == 0 and not f1.exists(), f"{r}")
    refused("two items in maxItems=1 zone", rm(f2, SB / "logs" / "three.log"), [f2]) if False else None
    write(SB / "logs" / "three.log")
    refused("maxItems=1 zone, two named items", rm(f2, SB / "logs" / "three.log"), [f2, SB / "logs" / "three.log"])

    # ---- protected ----
    g = write(P / "app" / ".git" / "config")
    refused("protected folder .git (file inside)", rm(g), [g])
    refused("protected folder .git itself", rm(P / "app" / ".git", recurse=True), [g])
    pr = P / "app" / "withgit"; gg = write(pr / "ok.txt"); write(pr / ".git" / "HEAD")
    refused("tree containing .git", rm(pr, recurse=True), [gg])
    e = write(P / "app" / "cfg" / ".env")
    refused(".env file", rm(e), [e])
    e2 = write(P / "app" / "cfg" / ".env.local")
    refused(".env.* file", rm(e2), [e2])
    k = write(P / "app" / "cfg" / "server.pem")
    refused("*.pem key", rm(k), [k])
    tr = P / "app" / "withdb"; w = write(tr / "ok.txt"); write(tr / "data.db")
    refused("tree containing *.db", rm(tr, recurse=True), [w])
    v = write(P / "app" / ".venv" / "lib.py")
    refused("protected .venv", rm(v), [v])
    au = write(SB / "logs" / "_deletions.jsonl")
    refused("audit file protected", rm(au), [au])

    # ---- path hygiene ----
    base = write(P / "app" / "h" / "f.txt")
    refused("relative path", rm("app/h/f.txt"), [base])
    refused("UNC path", rm("//server/share/x.txt"), [base])
    if IS_WIN:
        refused("alternate data stream", rm(posix(base) + ":stream"), [base])
        refused("trailing dot component", rm(posix(base) + "."), [base])
        refused("8.3 short name", rm(posix(P).replace("proj", "PROJ~1") + "/app/h/f.txt"), [base])
        refused("reserved device name", rm(posix(P / "app" / "h" / "NUL")), [base])
    else:
        refused("backslash in path", rm(posix(P / "app" / "h") + "\\f.txt"), [base])
        refused("filesystem root", rm("/"), [str(base)])
        refused("system path outside zones", rm("/etc/passwd"), [base])
    refused("dollar sign", rm(posix(P / "app" / "h" / "$HOME")), [base])
    refused("wildcard in a middle segment", rm(posix(P / "app" / "*" / "f.txt")), [base])
    refused("one bad item refuses the whole command", rm(base, SB / "other" / "o.txt"), [base, SB / "other" / "o.txt"])

    # ---- junctions / links ----
    tgt = write(SB / "other" / "inside" / "t.txt")
    lk = P / "app" / "link"
    def mklink(link, target):
        if IS_WIN: subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        else: os.symlink(str(target), str(link))
    mklink(lk, SB / "other" / "inside")
    if lk.exists():
        refused("junction itself", rm(lk), [tgt])
        refused("junction as directory with -r", rm(lk, recurse=True), [tgt])
        refused("path below a junction", rm(posix(lk) + "/t.txt"), [tgt])
        holder = P / "app" / "holder"; write(holder / "a.txt"); mklink(holder / "jl", SB / "other" / "inside")
        refused("tree containing a junction", rm(holder, recurse=True), [tgt, holder / "a.txt"])
    else:
        check("junction tests (skipped: link creation unavailable)", True)

    # ---- caps ----
    big = P / "app" / "big"
    for i in range(60): write(big / f"f{i}.txt")
    refused("too many files (maxFiles=50)", rm(big, recurse=True), [big / "f0.txt"])
    pol_bytes = make_policy("bytes.json", maxBytes=100)
    bf = write(P / "app" / "bytes" / "b.bin", "x" * 500)
    refused("too large (maxBytes=100)", rm(bf, policy=pol_bytes), [bf])
    for i in range(8): write(P / "app" / "globs" / f"m{i}.tmp")
    refused("too many glob matches", rm(P / "app" / "globs" / "*.tmp"), [P / "app/globs/m0.tmp"])
    few = [write(P / "app" / "five" / f"z{i}.txt") for i in range(5)]
    refused("maxItems=4 in proj zone", rm(*few), few)

    # ---- audit failure: nothing moves ----
    bad_audit = SB / "blocker"; bad_audit.write_text("i am a file, not a folder")
    pol = json.loads(POLICY.read_text()); pol["auditFile"] = posix(bad_audit / "audit.jsonl")
    pbad = SB / "badaudit.json"; pbad.write_text(json.dumps(pol))
    af = write(P / "app" / "au" / "keep.txt")
    r = rm(af, policy=pbad)
    check("audit cannot be written -> refused, nothing moved", r[0] == 2 and af.exists(), f"{r}")

    # ---- restore ----
    rf = write(P / "app" / "rst" / "r.txt", "restore me")
    r = rm(rf)
    rid = [l for l in r[1].splitlines() if l.startswith("QUARANTINED")][0].split("id=")[1].split()[0]
    code, out, err = ps(RESTORE, "-PolicyFile", POLICY, "-List")
    check("restore: list shows the entry", code == 0 and rid in out, out[:200])
    code, out, err = ps(RESTORE, "-PolicyFile", POLICY, "-Id", rid)
    check("restore: item back with content", code == 0 and rf.exists() and rf.read_text() == "restore me", f"{code} {out} {err}")
    code, out, err = ps(RESTORE, "-PolicyFile", POLICY, "-Id", rid)
    check("restore twice: refuses to overwrite", code == 3 and "not overwritten" in err, f"{code} {err}")
    code, out, err = ps(RESTORE, "-PolicyFile", POLICY, "-Id", "../../etc")
    check("restore: bad id rejected", code == 2, f"{code} {err}")
    check("audit has a restore record", any(x.get("op") == "restore" for x in audit_lines()))
finally:
    shutil.rmtree(SB, ignore_errors=True)

n = len(results)
print(f"\n{sum(results)}/{n} passed")
sys.exit(0 if all(results) else 1)
