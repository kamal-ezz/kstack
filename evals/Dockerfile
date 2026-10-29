FROM node:24-bookworm-slim@sha256:be8204d4bd327363357f532187b752ff62759c31bedf98e9e18fc08c9cbd605c
ARG CODEX_VERSION=0.165.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 chromium fonts-liberation ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global @openai/codex@${CODEX_VERSION} \
    && npm cache clean --force
ENV HOME=/home/agent CODEX_HOME=/home/agent/.codex PYTHONDONTWRITEBYTECODE=1
USER node
WORKDIR /workspace
CMD ["sleep", "infinity"]
