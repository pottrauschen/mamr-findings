#!/bin/sh
# Run MAME headless for an arcade set with its hash line writer
# (docs/arcade-oracle-format.md). Usage:
#   run_mame.sh SET OUT [FRAMES]
# SET is ikari or rtype; the writer is SET_mame.lua next to this script.
# Environment:
#   MAME         MAME executable (default: mame in PATH); a mameref build
#                (docs/arcade-oracles.md section 2) is given the same way
#   MAME_WORK    private directory for the ROM path, cfg and nvram
#                (default: $XDG_CACHE_HOME/mamr-mame-arcade-work/SET); cfg
#                and nvram are removed before every run
#   ARCADE_ROMS  directory with the unpacked set (default: roms/SET of this
#                checkout); files are found by name or SHA-1 (romset.py)
#   FH_JUDGE     header key judge= (default: the MAME version string and
#                the basename of the executable)
#   FH_REPLAY, FH_IMG, FH_ACCLOG, FH_DUMP_DIR, FH_DUMP_AT, FH_DUMP_EVERY:
#                see the writer
# Exit 2 when MAME or a ROM file is missing (counted as skipped by ctest).
set -eu
if [ $# -lt 2 ] || [ $# -gt 3 ]; then
  echo "usage: $0 SET OUT [FRAMES]" >&2
  exit 64
fi
set_name=$1
case $set_name in
  ikari) rate=60 ;;
  rtype) rate=55 ;;
  *) echo "run_mame.sh: unknown set $set_name" >&2; exit 64 ;;
esac
mame=${MAME:-$(command -v mame || true)}
if [ -z "$mame" ] || ! [ -x "$mame" ]; then
  echo "run_mame.sh: mame not found (set MAME)" >&2
  exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../../.." && pwd)
roms=${ARCADE_ROMS:-$repo/roms/$set_name}
work=${MAME_WORK:-${XDG_CACHE_HOME:-$HOME/.cache}/mamr-mame-arcade-work/$set_name}
case $2 in /*) out=$2 ;; *) out=$(pwd)/$2 ;; esac
frames=${3:-${FH_FRAMES:-3000}}

rm -rf "$work/cfg" "$work/nvram" "$work/rompath"
mkdir -p "$work/cfg" "$work/nvram" "$work/rompath"
rc=0
python3 -I "$here/romset.py" prepare "$work/rompath" "$set_name" "$roms" --mame "$mame" || rc=$?
if [ $rc -ne 0 ]; then
  exit $rc
fi

input_sha1=-
if [ -n "${FH_REPLAY:-}" ]; then
  case $FH_REPLAY in /*) ;; *) FH_REPLAY=$(pwd)/$FH_REPLAY ;; esac
  input_sha1=$(sha1sum "$FH_REPLAY" | cut -d' ' -f1)
fi
for v in FH_ACCLOG FH_DUMP_DIR; do
  eval "p=\${$v:-}"
  case $p in ''|/*) ;; *) eval "$v=\$(pwd)/\$p" ;; esac
done
if [ -n "${FH_DUMP_DIR:-}" ]; then mkdir -p "$FH_DUMP_DIR"; fi
judge=${FH_JUDGE:-$(basename "$mame")-$("$mame" -version | cut -d' ' -f1)}

cd "$work"
FH_OUT=$out FH_FRAMES=$frames FH_INPUT_SHA1=$input_sha1 FH_JUDGE=$judge \
  FH_REPLAY=${FH_REPLAY:-} FH_ACCLOG=${FH_ACCLOG:-} FH_DUMP_DIR=${FH_DUMP_DIR:-} \
  LC_ALL=C "$mame" "$set_name" -rompath "$work/rompath" -noreadconfig \
  -cfg_directory "$work/cfg" -nvram_directory "$work/nvram" -skip_gameinfo \
  -video none -sound none -nothrottle -seconds_to_run $((frames / rate + 5)) \
  -autoboot_script "$here/${set_name}_mame.lua" > "$work/mame_stdout.txt" 2>&1 || rc=$?
if [ $rc -ne 0 ]; then
  echo "run_mame.sh: MAME exited with $rc (log: $work/mame_stdout.txt)" >&2
  exit 1
fi
if ! grep -q "^F $frames " "$out"; then
  echo "run_mame.sh: $out has fewer than $frames F lines (log: $work/mame_stdout.txt)" >&2
  exit 1
fi
