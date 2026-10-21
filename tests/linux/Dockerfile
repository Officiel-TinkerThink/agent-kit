# Ubuntu 24.04 test image for agent-kit: Python + git + Node 24 (for proof-lab's setup script) + POSIX sh only. NO PowerShell, no pwsh, no shim.
# Every capability runs its native .sh version through plugins/<plugin>/scripts/run.sh.
# Build/run through tests/linux/run-in-docker.sh
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git python3 python-is-python3 \
 && rm -rf /var/lib/apt/lists/*
# Node 24 from the official tarball (the proof-lab plugin needs Node 24 or later); the SHA-256 is pinned here (from the release's SHASUMS256.txt), so a changed download fails the build; change both lines together when the version moves.
ARG NODE_VERSION=24.22.1
ARG NODE_SHA256=eb6728e77c576a35162c122c45ccadf224d89ff00abc8dae46cc2897c6002d7c
RUN set -e; f=node-v${NODE_VERSION}-linux-x64.tar.gz; cd /tmp  && curl -fsSLO https://nodejs.org/dist/v${NODE_VERSION}/$f  && echo "${NODE_SHA256}  $f" | sha256sum -c -  && tar -xzf $f -C /usr/local --strip-components=1 --no-same-owner && rm $f  && node --version
WORKDIR /work
