#!/usr/bin/env bash
# Start the DynaMem dev container on Jarvis: GPU, host network, X display forwarded,
# and this repo mounted at /app. Uses the local snapshot image (deps upgraded, av removed).
#
# Usage: learning/run_dynamem_container.sh [image]
set -euo pipefail

IMAGE="${1:-stretch-ai-dynamem:local}"
NAME="dynamem"

# Mount the repo root no matter where this is run from.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${DISPLAY:-}" ]]; then
  echo "Error: \$DISPLAY is not set, so no windows can open."
  echo "Reconnect with X forwarding (ssh -Y enyu@<jarvis>) or run from Jarvis's desktop."
  exit 1
fi

# Over SSH the cookie is in ~/.Xauthority; on a local desktop session it's in $XAUTHORITY.
XAUTH_FILE="${XAUTHORITY:-$HOME/.Xauthority}"
if [[ ! -f "$XAUTH_FILE" ]]; then
  echo "Error: X cookie file $XAUTH_FILE not found."
  exit 1
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Error: image $IMAGE not found. Build it once from a running container with:"
  echo "  pip install -e src && pip uninstall -y av   # inside the container"
  echo "  docker commit <container> stretch-ai-dynamem:local   # on Jarvis"
  exit 1
fi

if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "Error: a container named '$NAME' already exists."
  echo "  Open another shell in it:  docker exec -it $NAME bash"
  echo "  Or remove it first:        docker rm -f $NAME"
  exit 1
fi

# Model weights (Hugging Face, torch hub, CLIP) download to /root/.cache. The container is
# --rm, so keep that cache on the host or every start re-downloads them.
# HF_HUB_DISABLE_XET: the xet downloader stalled at ~45 kB/s here; plain HTTP does ~7 MB/s.
CACHE_DIR="$HOME/.cache/dynamem-docker"
mkdir -p "$CACHE_DIR"

echo "Starting $IMAGE as '$NAME' (DISPLAY=$DISPLAY, repo → /app, model cache → $CACHE_DIR)"
exec docker run -it --rm --name "$NAME" --gpus all --network host --privileged \
  -v /dev:/dev -v /dev/shm:/dev/shm \
  -e DISPLAY="$DISPLAY" \
  -v "$XAUTH_FILE:/root/.Xauthority:ro" -e XAUTHORITY=/root/.Xauthority \
  -v "$REPO_ROOT:/app" \
  -v "$CACHE_DIR:/root/.cache" \
  -e HF_HUB_DISABLE_XET=1 \
  "$IMAGE"
