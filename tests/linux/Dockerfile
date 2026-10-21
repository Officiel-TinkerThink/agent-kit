# Ubuntu 24.04 test image for agent-kit: Python + git + Node 24 (for proof-lab's setup script) + POSIX sh only. NO PowerShell, no pwsh, no shim.
# Every capability runs its native .sh version through plugins/<plugin>/scripts/run.sh.
# Build/run through tests/linux/run-in-docker.sh
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git python3 python-is-python3 \
 && rm -rf /var/lib/apt/lists/*
# Node 24 from the official tarball (the proof-lab plugin needs Node 24 or later); the checksum comes from the same release.
ARG NODE_VERSION=24.22.1
RUN set -e; f=node-v${NODE_VERSION}-linux-x64.tar.gz; cd /tmp  && curl -fsSLO https://nodejs.org/dist/v${NODE_VERSION}/$f  && curl -fsSL https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt | grep " $f\$" | sha256sum -c -  && tar -xzf $f -C /usr/local --strip-components=1 --no-same-owner && rm $f  && node --version
WORKDIR /work
