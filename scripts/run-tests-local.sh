#!/usr/bin/env bash
# Run the ipmininet test suite without root privileges.
#
# Tests that require root are automatically skipped thanks to the
# `require_root` marker (see ipmininet/tests/__init__.py), so this script can
# be run by any user to exercise the rootless (pure unit) tests locally.
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
    echo "WARNING: you are running as root; root-requiring tests will run." >&2
    echo "         Run as a non-root user to run only the rootless tests." >&2
fi

cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
    exec uv run python -m pytest "$@"
fi
exec python3 -m pytest "$@"
