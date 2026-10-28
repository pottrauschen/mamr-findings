#!/bin/sh
# Build mameref: MAME 0.285 with the patches in patches/mame/ at the top of
# this repository, or MAMEREF_PATCHES (the judge of
# docs/arcade-oracles.md section 2), only the drivers of the arcade games
# MAMR compares against MAME (snk.cpp for Ikari Warriors, m72.cpp for
# R-Type).
#
#   build_mameref.sh [--fetch] MAME_DIR
#
# MAME_DIR must be a git checkout of mamedev/mame at the tag mame0285
# (--fetch makes a shallow clone there first). The patches are applied to
# its working tree once; a later run with the same patches skips, a run
# with changed patches restores the patched files from git first. The
# binary is MAME_DIR/mameref. Needs what a MAME build needs on the host
# (GNU make, python3, a C++17 compiler, the SDL2 and fontconfig
# development files). MAMEREF_JOBS sets the parallel jobs (default 3: a
# MAME compile unit can take more than 1 GB).
set -eu
MAME_TAG=mame0285
MAME_COMMIT=f379cd06
MAME_URL=https://github.com/mamedev/mame.git
here=$(cd "$(dirname "$0")" && pwd)
patches=${MAMEREF_PATCHES:-$here/../../../patches/mame}

fetch=0
if [ "${1:-}" = "--fetch" ]; then fetch=1; shift; fi
if [ $# -ne 1 ]; then
  echo "usage: $0 [--fetch] MAME_DIR" >&2
  exit 64
fi
mame=$1

if [ ! -e "$mame/.git" ]; then
  if [ $fetch -eq 0 ]; then
    echo "build_mameref.sh: $mame is not a MAME checkout (use --fetch)" >&2
    exit 2
  fi
  git clone --depth 1 --branch "$MAME_TAG" "$MAME_URL" "$mame"
fi
head=$(git -C "$mame" rev-parse --short=8 HEAD)
if [ "$head" != "$MAME_COMMIT" ]; then
  echo "build_mameref.sh: $mame is at $head, expected $MAME_COMMIT ($MAME_TAG)" >&2
  exit 2
fi

# The applied patch set is recorded in MAME_DIR/.mameref-patches (checksum,
# then the files it touches), as build_aresref.sh does.
stamp=$mame/.mameref-patches
want=$(cat "$patches"/*.patch | sha256sum | cut -c1-64)
if [ -f "$stamp" ] && [ "$(head -n 1 "$stamp")" = "$want" ]; then
  echo "patches already applied"
else
  if [ -f "$stamp" ]; then
    tail -n +2 "$stamp" | while read -r f; do
      git -C "$mame" checkout -q -- "$f"
    done
    rm -f "$stamp"
  fi
  if ! git -C "$mame" diff --quiet; then
    echo "build_mameref.sh: $mame has local changes; expected a clean checkout" >&2
    exit 2
  fi
  for p in "$patches"/*.patch; do
    if ! git -C "$mame" apply "$p"; then
      echo "build_mameref.sh: $(basename "$p") does not apply" >&2
      exit 1
    fi
    echo "applied: $(basename "$p")"
  done
  { echo "$want"
    for p in "$patches"/*.patch; do git -C "$mame" apply --numstat "$p" | cut -f3; done | sort -u
  } > "$stamp"
fi

make -C "$mame" SUBTARGET=mameref SOURCES=src/mame/snk/snk.cpp,src/mame/irem/m72.cpp \
  OPTIMIZE=2 SYMBOLS=0 NOWERROR=1 TOOLS=0 NO_USE_PORTAUDIO=1 NO_USE_PIPEWIRE=1 \
  USE_QTDEBUG=0 -j "${MAMEREF_JOBS:-3}"
echo "mameref: $mame/mameref"
