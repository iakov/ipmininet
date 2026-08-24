#!/usr/bin/env bash
set -euo pipefail

# Install system deps inside a podman container.

IMAGE="${IMAGE:-ipmininet-dev}"

if ! podman image exists "$IMAGE" 2>/dev/null; then
  echo "Building container image: $IMAGE"
  podman build -t "$IMAGE" .
fi

exec podman run --rm --privileged -v "$PWD:/workspace:Z" "$IMAGE" \
    sudo env "PATH=\$PATH" uv run python -m ipmininet.install -a