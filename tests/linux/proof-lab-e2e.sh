#!/bin/sh
# End-to-end check of the proof-lab plugin on a stock Ubuntu 24.04 container (Node 24, git, no browser libraries).
# Usage (from a Linux shell or WSL with Docker): sh tests/linux/proof-lab-e2e.sh
# It needs the network: the plugin fetches the pinned proof-lab commit from GitHub and downloads Chromium.
# Three fresh containers: a normal user (the plugin must refuse with the exact apt command, then work once the libraries are
# installed), root (the plugin installs the libraries itself) and root on a checkout a normal user owns (the plugin does nothing as root). The first two then run the whole proof-lab demo.
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
docker build -q -t agent-kit-ubuntu-test "$here" >/dev/null || exit 1
status=0
for mode in user root untrusted; do
  echo "=== $mode"
  docker run --rm -v "$repo":/src:ro agent-kit-ubuntu-test \
    sh -c 'cp -r /src /work/repo && sh /work/repo/tests/linux/proof-lab-e2e-inside.sh "$1"' sh "$mode" || status=1
done
exit "$status"
