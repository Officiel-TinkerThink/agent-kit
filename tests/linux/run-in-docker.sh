#!/bin/sh
# Run the whole agent-kit test suite on Ubuntu 24.04 in a throwaway container.
# Usage (from a Linux shell or WSL with Docker): sh tests/linux/run-in-docker.sh [run_all.py args]
# The repository is mounted read-only and copied inside the container, so the host tree is never written to.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
docker build -q -t agent-kit-ubuntu-test "$here" >/dev/null
docker run --rm -v "$repo":/src:ro agent-kit-ubuntu-test \
  sh -c 'cp -r /src /work/repo && cd /work/repo && find . -name __pycache__ -prune -exec rm -rf {} + ; python tests/run_all.py "$@"' sh "$@"
