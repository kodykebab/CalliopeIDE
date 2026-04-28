#!/bin/sh
# Calliope IDE — Sandbox Entrypoint
# Receives Python source on stdin, writes to a temp file, executes it, exits.
# Network is disabled at the compose/run level (--network none).

set -e

SCRIPT_FILE="/sandbox/user_code_$$.py"

# Write stdin to script file
cat > "$SCRIPT_FILE"

# Execute with a hard CPU-time limit via the shell's ulimit.
# Memory is capped by Docker's --memory flag at the run level.
# ulimit -t is CPU seconds, not wall clock — belt-and-suspenders alongside timeout.
ulimit -t 10 2>/dev/null || true   # CPU seconds (may not work in all kernels)
ulimit -f 512 2>/dev/null || true  # Max file size (512 * 512 = 256 KB)
ulimit -n 32  2>/dev/null || true  # Max open file descriptors

exec python3 "$SCRIPT_FILE"