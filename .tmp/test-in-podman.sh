#!/usr/bin/env bash
set -euo pipefail

# Run full test suite inside a podman container.
# Preserves the host from root-requiring mininet operations.

IMAGE="${IMAGE:-ipmininet-dev}"
ARGS="${*:-}"

if ! podman image exists "$IMAGE" 2>/dev/null; then
  echo "Building container image: $IMAGE"
  podman build -t "$IMAGE" .
fi

echo "Running: uv run pytest $ARGS"
exec podman run --rm --privileged -v "$PWD:/workspace:Z" "$IMAGE" \
    sudo env "PATH=\$PATH" uv run pytest $ARGS