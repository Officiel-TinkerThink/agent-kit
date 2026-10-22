#!/bin/sh
# Makes plugins/proof-lab/browsers.sha256.json: the digest of every browser folder that the pinned proof-lab's Playwright
# installs for `install chromium`, for every build it knows (Linux x64 and arm64, macOS x64 and arm64, Windows x64).
# Run it when the pin moves to a proof-lab commit with another Playwright. Usage (from a Linux shell or WSL with Docker):
#   sh tests/linux/browser-digests.sh
# It downloads every build (about 2 GB) from Playwright's servers. Then check the table on a real machine of another kind:
# there the plugin compares the folders it installed with it (node plugins/proof-lab/scripts/setup.mjs refuses on a mismatch).
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
pin=$(grep -v '^ *#' "$repo/plugins/proof-lab/proof-lab.pin" | grep -m1 '[0-9a-f]')
out="$repo/plugins/proof-lab/browsers.sha256.json"
docker build -q -t agent-kit-ubuntu-test "$here" >/dev/null || exit 1
docker run --rm -v "$repo":/src:ro agent-kit-ubuntu-test sh -c '
  set -e
  git init -q /work/pl && cd /work/pl
  git fetch -q --depth 1 https://github.com/Officiel-TinkerThink/proof-lab.git "$1" && git checkout -q --detach FETCH_HEAD
  [ "$(git rev-parse HEAD)" = "$1" ]
  npm ci --ignore-scripts --silent >&2
  mkdir /work/b
  node /src/tests/proof-lab/browser_digests.mjs /work/pl /work/b' sh "$pin" > "$out.new" || { rm -f "$out.new"; exit 1; }
mv "$out.new" "$out"
echo "wrote $out"
