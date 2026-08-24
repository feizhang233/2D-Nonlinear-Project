#!/usr/bin/env bash
# Clone the frozen linear-core revisions used by CI and production Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/dependencies"
mkdir -p "$DEST"

clone_pin() {
  local url="$1" dir="$2" sha="$3"
  if [ ! -d "$DEST/$dir/.git" ]; then
    git clone --filter=blob:none "$url" "$DEST/$dir"
  fi
  git -C "$DEST/$dir" fetch --filter=blob:none origin
  git -C "$DEST/$dir" checkout --detach "$sha"
}

clone_pin git@github.com:feizhang233/2D-Continuum-Project.git continuum 01468920c19e468d0719714cde8b6168e78d0cd8
clone_pin git@github.com:feizhang233/2D-Frame-Project.git frame b8276a1ced4fd5a2913efb23c981f4ec43e59f6e
clone_pin git@github.com:feizhang233/2d-plate-analysis-api.git plate c30bee97a8efa7d1a0d9732bee84fef4f7383913
clone_pin git@github.com:feizhang233/2D-Shell-Project.git shell 814f68c038f5e72f4c886f00baf064b2794e097a
