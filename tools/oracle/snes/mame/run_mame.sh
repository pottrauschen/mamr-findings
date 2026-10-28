#!/bin/sh
# Run MAME 0.285 headless with snesfh_mame.lua. Usage:
#   run_mame.sh rom.sfc
# Environment: FH_OUT, FH_FRAMES (see snesfh_mame.lua), and
#   MAME        MAME executable (default: mame in PATH)
#   MAME_IPL    a user-supplied dump of the 64-byte SPC700 IPL ROM. MAME
#               refuses to start without snes/spc700.rom. Without a dump
#               this script installs a 64-byte zero placeholder in a
#               private ROM path: MAME then starts with a checksum warning,
#               only the CPU side is meaningful and every SPC-side field
#               of the hash lines is "-". The IPL is Sony's and never part
#               of the repository.
#   MAME_WORK   private directory for the ROM path, cfg and nvram
#               (default: $XDG_CACHE_HOME/mamr-mame-work)
set -eu
if [ $# -ne 1 ]; then
  echo "usage: $0 rom.sfc" >&2
  exit 64
fi
mame=${MAME:-$(command -v mame || true)}
if [ -z "$mame" ]; then
  echo "run_mame.sh: mame not found (set MAME)" >&2
  exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
work=${MAME_WORK:-${XDG_CACHE_HOME:-$HOME/.cache}/mamr-mame-work}
mkdir -p "$work/roms/snes" "$work/cfg" "$work/nvram"
if [ -n "${MAME_IPL:-}" ]; then
  cp "$MAME_IPL" "$work/roms/snes/spc700.rom"
  FH_SPC=1
else
  head -c 64 /dev/zero > "$work/roms/snes/spc700.rom"
  FH_SPC=0
fi
export FH_SPC
# Cartridges are not keyed by name: -cart loads the file as is.
exec "$mame" snes -cart "$1" -rompath "$work/roms" -cfg_directory "$work/cfg" \
  -nvram_directory "$work/nvram" -video none -sound none -nothrottle \
  -skip_gameinfo -seconds_to_run 100000 -autoboot_script "$here/snesfh_mame.lua"
