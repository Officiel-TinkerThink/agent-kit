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
  if [ "$code" -eq 2 ] && echo "$out" | grep -q 'sudo node ".*install-deps chromium"'; then ok "a normal user without the libraries is refused with the exact apt command"; else bad "no hint (exit $code): $out"; fi
  cli=$(echo "$out" | sed -n 's/.*sudo node "\([^"]*\)" install-deps.*/\1/p' | head -1)
  node "$cli" install-deps chromium >/dev/null 2>&1 || bad "the printed command failed"
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
if [ "$code" -eq 0 ] && echo "$out" | grep -q 'VALID'; then ok "the proof-lab demo runs on Ubuntu (exit 0, chain checked)"; else bad "demo failed (exit $code): $(echo "$out" | tail -8)"; fi
exit "$fail"
