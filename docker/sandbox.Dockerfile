# ── Calliope IDE — Secure Code Execution Sandbox ──────────────────────────────
# Minimal Python image. No network, no host FS, ephemeral per execution.
# Built once; containers are created and destroyed per code-run request.

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="" \
    HOME=/sandbox \
    PATH=/usr/local/bin

# Non-root sandbox user with no login shell
RUN groupadd --gid 65534 sandbox && \
    useradd  --uid 65534 --gid sandbox \
             --no-create-home --shell /usr/sbin/nologin \
             sandbox && \
    mkdir -p /sandbox && \
    chown sandbox:sandbox /sandbox

COPY docker/sandbox-entrypoint.sh /usr/local/bin/sandbox-entrypoint.sh
RUN chmod +x /usr/local/bin/sandbox-entrypoint.sh

USER sandbox
WORKDIR /sandbox

# Receives Python source on stdin, executes it, then exits.
ENTRYPOINT ["/usr/local/bin/sandbox-entrypoint.sh"]
