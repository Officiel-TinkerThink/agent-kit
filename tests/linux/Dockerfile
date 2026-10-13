# Ubuntu 24.04 test image for agent-kit: PowerShell 7 + Python + git.
# Build/run through tests/linux/run-in-docker.sh
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git python3 python-is-python3 \
 && curl -fsSL -o /tmp/ms.deb https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb \
 && dpkg -i /tmp/ms.deb && rm /tmp/ms.deb \
 && apt-get update \
 && apt-get install -y --no-install-recommends powershell \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /work
