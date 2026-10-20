"""scripts/setup.mjs --check-only: refuses a proof-lab checkout that does not match the pin, and accepts one that does.

The test copies the setup script and a pin file into a temporary plugin folder, so the real pin is never changed.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SETUP = ROOT / "plugins" / "proof-lab" / "scripts" / "setup.mjs"
failed = 0


def check(name, cond, extra=""):
    global failed
    if cond:
        print(f"ok   {name}")
    else:
        failed += 1
        print(f"FAIL {name} {extra}")


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
        cwd=cwd, capture_output=True, text=True, check=True,
    ).stdout.strip()


RUNNER = 'console.log("ran " + process.argv.slice(2).join(" ")); process.exitCode = process.argv.includes("--fail") ? 1 : 0;\n'


def make_checkout(root, name="proof-lab", deps=True):
    home = root / "lab"
    (home / "src").mkdir(parents=True)
    (home / "package.json").write_text(f'{{"name": "{name}"}}\n', encoding="utf-8")
    (home / "src" / "run-spec.js").write_text(RUNNER, encoding="utf-8")
    (home / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    git(home, "init", "-q")
    git(home, "add", "package.json", "src/run-spec.js", ".gitignore")
    git(home, "commit", "-q", "-m", "init")
    if deps:
        (home / "node_modules").mkdir()
    return home, git(home, "rev-parse", "HEAD")


def make_plugin(root, pin_text):
    plugin = root / "plugin"
    (plugin / "scripts").mkdir(parents=True)
    shutil.copy(SETUP, plugin / "scripts" / "setup.mjs")
    (plugin / "proof-lab.pin").write_text(pin_text, encoding="utf-8")
    return plugin / "scripts" / "setup.mjs"


def run(script, env_home, extra_env=None, args=("--check-only",)):
    env = {k: v for k, v in os.environ.items() if k not in ("PROOF_LAB_HOME", "PROOF_LAB_RECEIPTS")}
    if env_home is not None:
        env["PROOF_LAB_HOME"] = env_home
    env.update(extra_env or {})
    p = subprocess.run(["node", str(script), *args], capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    return p.returncode, p.stdout, p.stderr


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)

    home, head = make_checkout(tmp)
    script = make_plugin(tmp, f"# test pin\n{head}\n")
    code, out, err = run(script, str(home))
    check("matching pin and clean tree: ready", code == 0 and "ready: proof-lab" in out, f"exit {code} err {err!r}")
    check("ready line names the receipts folder", "receipts go to" in out and str(home / "receipts") in out, out)

    code, out, err = run(script, str(home), {"PROOF_LAB_RECEIPTS": str(tmp / "r")})
    check("PROOF_LAB_RECEIPTS overrides the receipts folder", code == 0 and str(tmp / "r") in out, out)

    other = make_plugin(tmp / "other", "0" * 40 + "\n")
    code, out, err = run(other, str(home))
    check("mismatched pin is refused and names both hashes", code == 2 and "pinned to" in err and head in err, f"exit {code} err {err!r}")

    (home / "dirty.txt").write_text("x", encoding="utf-8")
    code, out, err = run(script, str(home))
    check("uncommitted changes are refused", code == 2 and "uncommitted changes" in err, f"exit {code} err {err!r}")
    (home / "dirty.txt").unlink()

    code, out, err = run(script, None)
    check("unset PROOF_LAB_HOME is refused", code == 2 and "not set" in err, f"exit {code} err {err!r}")

    code, out, err = run(script, "relative/path")
    check("a relative PROOF_LAB_HOME is refused", code == 2 and "absolute" in err, f"exit {code} err {err!r}")

    (tmp / "wrong_name").mkdir()
    wrong, _ = make_checkout(tmp / "wrong_name", name="something-else")
    code, out, err = run(script, str(wrong))
    check("a checkout that is not proof-lab is refused", code == 2 and "not a proof-lab checkout" in err, f"exit {code} err {err!r}")

    bad_pin = make_plugin(tmp / "badpin", "not-a-hash\n")
    code, out, err = run(bad_pin, str(home))
    check("a pin that is not a commit hash is refused", code == 2 and "40-character" in err, f"exit {code} err {err!r}")

    code, out, err = run(script, str(home), args=("--run", "--spec", "s.json"))
    check("--run passes the arguments to run-spec.js on a matching checkout", code == 0 and "ran --spec s.json" in out, f"exit {code} out {out!r} err {err!r}")

    code, out, err = run(script, str(home), args=("--run", "--fail"))
    check("--run returns the run's exit code", code == 1 and "ran --fail" in out, f"exit {code} out {out!r} err {err!r}")

    code, out, err = run(other, str(home), args=("--run", "--spec", "s.json"))
    check("--run refuses a mismatched checkout before it runs", code == 2 and "pinned to" in err and "ran" not in out, f"exit {code} out {out!r} err {err!r}")

    (home / "dirty.txt").write_text("x", encoding="utf-8")
    code, out, err = run(script, str(home), args=("--run", "--spec", "s.json"))
    check("--run refuses a dirty checkout before it runs", code == 2 and "uncommitted changes" in err and "ran" not in out, f"exit {code} out {out!r} err {err!r}")
    (home / "dirty.txt").unlink()

    bare, bare_head = make_checkout(tmp / "bare", deps=False)
    bare_script = make_plugin(tmp / "bare", f"{bare_head}\n")
    code, out, err = run(bare_script, str(bare), args=("--run", "--spec", "s.json"))
    check("--run refuses a checkout with no node_modules before it runs", code == 2 and "has no node_modules" in err and "ran" not in out, f"exit {code} out {out!r} err {err!r}")
    code, out, err = run(bare_script, str(bare))
    check("setup without --run does not refuse a checkout with no node_modules", "has no node_modules" not in err, f"exit {code} err {err!r}")

sys.exit(1 if failed else 0)
