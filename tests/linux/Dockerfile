# Ubuntu 24.04 test image for agent-kit: Python + git only (NO PowerShell).
# `pwsh` here is a test shim that runs the native Python version of each script.
# Build/run through tests/linux/run-in-docker.sh
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git python3 python-is-python3 \
 && rm -rf /var/lib/apt/lists/*
COPY --chmod=755 pwsh /usr/local/bin/pwsh
WORKDIR /work
