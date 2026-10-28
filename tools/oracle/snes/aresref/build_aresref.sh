#!/bin/sh
# Build aresref against an external ares checkout.
#
#   build_aresref.sh [--fetch] ARES_DIR [BUILD_DIR]
#
# ARES_DIR must be a git checkout (a clone or a git worktree) of
# ares-emulator/ares at the pinned
# commit below (--fetch clones it there first). The patches in
# patches/ares/ at the top of this repository (or ARESREF_PATCHES) are
# applied to its working tree once; a later run with the same patches
# skips, a run with changed patches restores the patched files first. BUILD_DIR defaults to ARES_DIR/build-aresref; the binary ends up
# in BUILD_DIR/aresref/aresref. Needs cmake, a C++20 compiler and the
# development headers ares links against without its GUI (no GTK).
set -eu
ARES_COMMIT=c76aaffa6e69778baf9a66d1da04298ac2ed7d1d
ARES_URL=https://github.com/ares-emulator/ares.git
here=$(cd "$(dirname "$0")" && pwd)
patches=${ARESREF_PATCHES:-$here/../../../../patches/ares}

fetch=0
if [ "${1:-}" = "--fetch" ]; then fetch=1; shift; fi
if [ $# -lt 1 ]; then
  echo "usage: $0 [--fetch] ARES_DIR [BUILD_DIR]" >&2
  exit 64
fi
ares=$1
build=${2:-$ares/build-aresref}

if [ ! -e "$ares/.git" ]; then
  if [ $fetch -eq 0 ]; then
    echo "build_aresref.sh: $ares is not an ares checkout (use --fetch)" >&2
    exit 2
  fi
  git clone --filter=blob:none "$ARES_URL" "$ares"
  git -C "$ares" checkout -q "$ARES_COMMIT"
fi
head=$(git -C "$ares" rev-parse HEAD)
if [ "$head" != "$ARES_COMMIT" ]; then
  echo "build_aresref.sh: $ares is at $head, expected $ARES_COMMIT" >&2
  exit 2
fi

# The applied patch set is recorded in ARES_DIR/.aresref-patches (checksum,
# then the files it touches). A different recorded set is undone first by
# restoring those files from git.
stamp=$ares/.aresref-patches
want=$(cat "$patches"/*.patch | sha256sum | cut -c1-64)
if [ -f "$stamp" ] && [ "$(head -n 1 "$stamp")" = "$want" ]; then
  echo "patches already applied"
else
  if [ -f "$stamp" ]; then
    tail -n +2 "$stamp" | while read -r f; do
      if git -C "$ares" ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
        git -C "$ares" checkout -q -- "$f"
      else
        rm -f "$ares/$f"
      fi
    done
    rm -f "$stamp"
  fi
  if ! git -C "$ares" diff --quiet; then
    echo "build_aresref.sh: $ares has local changes; expected a clean checkout" >&2
    exit 2
  fi
  for p in "$patches"/*.patch; do
    if ! git -C "$ares" apply "$p"; then
      echo "build_aresref.sh: $(basename "$p") does not apply" >&2
      exit 1
    fi
    echo "applied: $(basename "$p")"
  done
  { echo "$want"
    for p in "$patches"/*.patch; do git -C "$ares" apply --numstat "$p" | cut -f3; done | sort -u
  } > "$stamp"
fi

cmake -S "$ares" -B "$build" -DCMAKE_BUILD_TYPE=Release \
  -DARES_CORES=sfc -DARES_SKIP_DEPS=ON -DARES_BUILD_LOCAL=ON \
  -DARESREF_SOURCE_DIR="$here"
cmake --build "$build" --target aresref -j "${ARESREF_JOBS:-$(nproc 2>/dev/null || echo 4)}"
echo "aresref: $build/aresref/aresref"
