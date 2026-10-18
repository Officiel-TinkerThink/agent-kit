# Ubuntu 24.04 test image for agent-kit: Python + git + POSIX sh only. NO PowerShell, no pwsh, no shim.
# Every capability runs its native .sh version through plugins/<plugin>/scripts/run.sh.
# Build/run through tests/linux/run-in-docker.sh
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git python3 python-is-python3 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /work
