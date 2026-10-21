#!/bin/sh
# Runs inside the container started by proof-lab-e2e.sh. $1 is "user" or "root".
mode="$1"
fail=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }
setup='node /work/repo/plugins/proof-lab/scripts/setup.mjs'
if [ "$mode" = user ]; then
  useradd -m tester
  run() { su tester -c "PROOF_LAB_DATA=/home/tester/pl $1"; }
  out=$(run "$setup" 2>&1); code=$?
  if [ "$code" -eq 2 ] && echo "$out" | grep -q "sudo node '.*cli.js' install-deps chromium"; then ok "a normal user without the libraries is refused with the exact apt command"; else bad "no hint (exit $code): $out"; fi
  # The command is printed with the path in single quotes: take the path out of the first "sudo node '...'" and run it as root.
  cli=$(echo "$out" | sed -n "s/.*sudo node '\([^']*\)' install-deps.*/\1/p" | head -1)
  if [ -n "$cli" ] && node "$cli" install-deps chromium >/dev/null 2>&1; then ok "the printed command installs the libraries"; else bad "the printed command failed (path '$cli')"; fi
  out=$(run "$setup" 2>&1); code=$?
  if [ "$code" -eq 0 ] && echo "$out" | grep -q '^ready: proof-lab'; then ok "setup is ready once the libraries are installed"; else bad "not ready (exit $code): $out"; fi
  home=$(ls -d /home/tester/pl/checkouts/*)
  out=$(run "cd $home && node demo/run-demo.mjs" 2>&1); code=$?
else
  out=$(PROOF_LAB_DATA=/root/pl $setup 2>&1); code=$?
  if [ "$code" -eq 0 ] && echo "$out" | grep -q '^ready: proof-lab'; then ok "root: setup installs the libraries itself and is ready"; else bad "root not ready (exit $code): $out"; fi
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
