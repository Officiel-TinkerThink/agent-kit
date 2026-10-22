#!/bin/sh
# Runs inside the container started by proof-lab-e2e.sh. $1 is "user", "root" or "untrusted".
mode="$1"
fail=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }
setup='node /work/repo/plugins/proof-lab/scripts/setup.mjs'
if [ "$mode" = user ]; then
  useradd -m tester
  run() { su tester -c "export PROOF_LAB_DATA=/home/tester/pl; $1"; }
  out=$(run "$setup" 2>&1); code=$?
  if [ "$code" -eq 2 ] && echo "$out" | grep -q "sudo node '.*cli.js' install-deps chromium"; then ok "a normal user without the libraries is refused with the exact apt command"; else bad "no hint (exit $code): $out"; fi
  # The command is printed with the path in single quotes: take the path out of the first "sudo node '...'" and run it as root.
  cli=$(echo "$out" | sed -n "s/.*sudo node '\([^']*\)' install-deps.*/\1/p" | head -1)
  if [ -n "$cli" ] && node "$cli" install-deps chromium >/dev/null 2>&1; then ok "the printed command installs the libraries"; else bad "the printed command failed (path '$cli')"; fi
  out=$(run "$setup" 2>&1); code=$?
  if [ "$code" -eq 0 ] && echo "$out" | grep -q '^ready: proof-lab' && [ -s /home/tester/pl/browsers-checked.json ]; then ok "setup checks the browser against its pinned digest and is ready once the libraries are installed"; else bad "not ready (exit $code): $out"; fi
  home=$(ls -d /home/tester/pl/checkouts/*)
  out=$(run "cd $home && node demo/run-demo.mjs" 2>&1); code=$?
elif [ "$mode" = untrusted ]; then
  # Root pointed at a checkout that a normal user owns: the browser step must do nothing as root (no apt, no browser start).
  useradd -m tester
  su tester -c "export PROOF_LAB_DATA=/home/tester/pl; $setup" >/dev/null 2>&1
  # git refuses a repository that another user owns unless root says it is safe; the test says so, to reach the browser step.
  git config --global --add safe.directory "*"
  out=$(PROOF_LAB_DATA=/home/tester/pl $setup 2>&1); code=$?
  if [ "$code" -eq 0 ] && echo "$out" | grep -q '^warning: running as root on .*npm ci and the spec run as root' && echo "$out" | grep -q 'browser step is skipped' && ! dpkg -s libnss3 >/dev/null 2>&1; then ok "root on a user-owned checkout is warned, skips the browser step and installs nothing"; else bad "untrusted root case wrong (exit $code, libnss3 present: $(dpkg -s libnss3 >/dev/null 2>&1 && echo yes || echo no)): $(echo "$out" | tail -4)"; fi
  # The warning comes before git runs in that checkout: a changed file is refused by git's check, after the warning.
  co=$(ls -d /home/tester/pl/checkouts/*/ | head -1)
  su tester -c "echo >> ${co}package.json"
  out=$(PROOF_LAB_DATA=/home/tester/pl $setup 2>&1); code=$?
  first=$(echo "$out" | grep -n -m1 '^warning: running as root' | cut -d: -f1)
  refused=$(echo "$out" | grep -n -m1 'has uncommitted changes' | cut -d: -f1)
  if [ "$code" -eq 2 ] && [ -n "$first" ] && [ -n "$refused" ] && [ "$first" -lt "$refused" ]; then ok "root on a user-owned checkout is warned before git runs in it"; else bad "no warning before git's check (exit $code): $(echo "$out" | head -4)"; fi
  su tester -c "git -C ${co} checkout -q -- package.json"
  # Root asked to fetch a new checkout into a folder that normal user owns: warned before anything is fetched or installed.
  # The repository is unreachable, so the run stops right after the warning and the first fetch.
  su tester -c "mkdir /home/tester/fresh"
  out=$(PROOF_LAB_DATA=/home/tester/fresh PROOF_LAB_REPO=/nonexistent $setup 2>&1)
  first=$(echo "$out" | grep -n -m1 '^warning: running as root' | cut -d: -f1)
  fetch=$(echo "$out" | grep -n -m1 'setting up proof-lab' | cut -d: -f1)
  if [ -n "$first" ] && [ -n "$fetch" ] && [ "$first" -lt "$fetch" ]; then ok "root fetching into a user-owned folder is warned before the fetch"; else bad "no warning before the fetch: $(echo "$out" | head -4)"; fi
  exit "$fail"
else
  out=$(PROOF_LAB_DATA=/root/pl $setup 2>&1); code=$?
  if [ "$code" -eq 0 ] && echo "$out" | grep -q '^ready: proof-lab' && [ -s /root/pl/browsers-checked.json ]; then ok "root: setup checks the browser against its pinned digest, installs the libraries itself and is ready"; else bad "root not ready (exit $code): $out"; fi
  # Browsers in a folder that a normal user owns: root refuses to start them.
  useradd -m tester
  cp -a /root/.cache/ms-playwright /home/tester/pw && chown -R tester /home/tester/pw
  out=$(PROOF_LAB_DATA=/root/pl PLAYWRIGHT_BROWSERS_PATH=/home/tester/pw $setup 2>&1); code=$?
  if [ "$code" -eq 2 ] && echo "$out" | grep -q 'can be changed by a user with fewer rights'; then ok "root: browsers in a user-owned folder are refused"; else bad "user-owned browsers not refused (exit $code): $(echo "$out" | tail -3)"; fi
  rm -rf /home/tester/pw
  # Receipts sent into a folder that normal user owns: warned, and the run goes on.
  su tester -c "mkdir /home/tester/r"
  out=$(PROOF_LAB_DATA=/root/pl PROOF_LAB_RECEIPTS=/home/tester/r $setup 2>&1); code=$?
  if [ "$code" -eq 0 ] && echo "$out" | grep -q '^warning: PROOF_LAB_RECEIPTS names /home/tester/r'; then ok "root: receipts in a user-owned folder are warned about"; else bad "no receipts warning (exit $code): $(echo "$out" | tail -3)"; fi
  # A browser folder changed after the check, and installed again as far as Playwright's marker says: refused.
  shell=$(ls -d /root/.cache/ms-playwright/chromium_headless_shell-*)
  cp -a "$shell" /tmp/shell-copy
  echo x >> "$(find "$shell" -name 'chrome-headless-shell' -type f | head -1)"
  touch "$shell/INSTALLATION_COMPLETE"
  out=$(PROOF_LAB_DATA=/root/pl $setup 2>&1); code=$?
  if [ "$code" -eq 2 ] && echo "$out" | grep -q 'does not match the digest'; then ok "root: a changed browser folder is refused"; else bad "changed browser not refused (exit $code): $(echo "$out" | tail -3)"; fi
  rm -rf "$shell" && mv /tmp/shell-copy "$shell"
  home=$(ls -d /root/pl/checkouts/*)
  out=$(cd "$home" && node demo/run-demo.mjs 2>&1); code=$?
fi
# The demo exits 0 whatever the verdicts are, so read them: the seven specs must end 0 1 1 3 0 2 2, then the chain check
# must exit 0 and print "VALID:", and the tampered copy must exit 1 and print "INVALID:" (the lines are matched from the start).
codes=$(echo "$out" | sed -n 's/^ *exit code: *\([0-9][0-9]*\).*/\1/p' | tr '\n' ' ')
if [ "$code" -eq 0 ] && [ "$codes" = "0 1 1 3 0 2 2 0 1 " ] && echo "$out" | grep -q '^VALID:' && echo "$out" | grep -q '^INVALID:'; then
  ok "the proof-lab demo runs on Ubuntu: verdicts 0 1 1 3 0 2 2, chain valid, tampered copy refused"
else
  bad "demo result wrong (exit $code, verdict codes '$codes'): $(echo "$out" | tail -8)"
fi
exit "$fail"
