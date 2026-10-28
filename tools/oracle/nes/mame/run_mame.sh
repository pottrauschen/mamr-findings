#!/bin/sh
# Run MAME 0.285 headless (driver nes) with nesfh_mame.lua. Usage:
#   run_mame.sh rom.nes
# Environment: FH_* (see nesfh_mame.lua), and
#   MAME        MAME executable (default: mame in PATH)
#   MAME_DRIVER nes (default, NTSC) or nespal (the PAL console,
#               docs/nes-oracles.md section 8)
#   MAME_WORK   private directory for the ROM path, cfg and nvram
#               (default: $XDG_CACHE_HOME/mamr-mame-nes-work); cfg and
#               nvram are removed before every run, so no saved setting
#               or battery RAM of an earlier run leaks into this one
# The nes driver needs no BIOS. -cart loads the file as is; the board
# comes from the iNES header (MAME's software list is not consulted for a
# file given by path).
set -eu
if [ $# -ne 1 ]; then
  echo "usage: $0 rom.nes" >&2
  exit 64
fi
mame=${MAME:-$(command -v mame || true)}
if [ -z "$mame" ]; then
  echo "run_mame.sh: mame not found (set MAME)" >&2
  exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
work=${MAME_WORK:-${XDG_CACHE_HOME:-$HOME/.cache}/mamr-mame-nes-work}
rm -rf "$work/cfg" "$work/nvram"
mkdir -p "$work/roms" "$work/cfg" "$work/nvram"
case $1 in /*) rom=$1 ;; *) rom=$(pwd)/$1 ;; esac
# MAME's SDL front end connects to the desktop's display even with
# -video none; a busy or stuck desktop session then blocks it at start-up (seen
# 2026-10-27: MAME waiting on the display socket with 0% CPU). The run
# needs no display: it gets none, and SDL's dummy drivers.
unset DISPLAY WAYLAND_DISPLAY
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
driver=${MAME_DRIVER:-nes}
case $driver in nes|nespal) ;; *) echo "run_mame.sh: MAME_DRIVER must be nes or nespal" >&2; exit 64 ;; esac
exec "$mame" "$driver" -cart "$rom" -rompath "$work/roms" -cfg_directory "$work/cfg" \
  -nvram_directory "$work/nvram" -video none -sound none -nothrottle \
  -skip_gameinfo -seconds_to_run 100000 -autoboot_script "$here/nesfh_mame.lua"
