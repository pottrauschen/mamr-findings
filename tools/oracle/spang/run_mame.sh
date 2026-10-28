#!/bin/sh
# Run MAME 0.285 headless (set spang) with spfh_mame.lua. Usage:
#   run_mame.sh OUT [FRAMES]
# writes the hash lines to OUT (docs/spang-oracle-format.md). Environment:
#   SPANG_ROMS   directory with the unpacked set (default: roms/spang of
#                this checkout); files are found by name or SHA-1
#   SPANG_YM2413 a dump of the YM2413 instrument ROM (144 bytes); without
#                it the placeholder from the vendored ymfm is used
#                (docs/spang-oracles.md section 3)
#   SPANG_EEPROM a 128-byte EEPROM image in the layout of the set's default
#                (64 big-endian words) to start from instead of the
#                default; written as MAME's nvram file (little-endian
#                words). spang_headless takes the same file (--eeprom)
#   SPANG_WAV    a file: MAME records its sound output there (-wavwrite,
#                48 kHz stereo); only for the plausibility check of
#                docs/spang-oracles.md section 9
#   MAME         MAME executable (default: mame in PATH)
#   MAME_WORK    private directory for the ROM path, cfg and nvram
#                (default: $XDG_CACHE_HOME/mamr-mame-spang-work); cfg and
#                nvram are removed before every run, so neither the
#                battery-backed work RAM nor the EEPROM of an earlier run
#                leaks into this one
#   FH_INPUT, FH_IMG, FH_IOLOG, FH_DUMP_DIR, FH_DUMP_AT, FH_DUMP_EVERY:
#                see spfh_mame.lua
#   FH_VIEWS     a directory: run views_mame.lua instead (MAME's decrypted
#                Kabuki views, no hash lines; OUT is not written)
# Exit 2 when MAME or a ROM file is missing (counted as skipped by ctest).
set -eu
if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "usage: $0 OUT [FRAMES]" >&2
  exit 64
fi
mame=${MAME:-$(command -v mame || true)}
if [ -z "$mame" ]; then
  echo "run_mame.sh: mame not found (set MAME)" >&2
  exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../../.." && pwd)
roms=${SPANG_ROMS:-$repo/roms/spang}
work=${MAME_WORK:-${XDG_CACHE_HOME:-$HOME/.cache}/mamr-mame-spang-work}
case $1 in /*) out=$1 ;; *) out=$(pwd)/$1 ;; esac
frames=${2:-${FH_FRAMES:-3000}}

rm -rf "$work/cfg" "$work/nvram" "$work/rompath"
mkdir -p "$work/cfg" "$work/nvram" "$work/rompath"
rc=0
ym=$(python3 -I "$here/romset.py" prepare "$work/rompath" "$roms" --ym2413 "${SPANG_YM2413:-}") || rc=$?
if [ $rc -ne 0 ]; then
  echo "$ym" >&2
  exit $rc
fi
ym=${ym#ym2413=}
if [ -n "${SPANG_EEPROM:-}" ]; then
  mkdir -p "$work/nvram/spang"
  python3 -I -c 'import sys
d = open(sys.argv[1], "rb").read()
if len(d) != 128:
    sys.exit("SPANG_EEPROM: 128 bytes expected")
open(sys.argv[2], "wb").write(bytes(d[i ^ 1] for i in range(128)))' "$SPANG_EEPROM" "$work/nvram/spang/eeprom"
fi

input_sha1=-
if [ -n "${FH_INPUT:-}" ]; then
  case $FH_INPUT in /*) ;; *) FH_INPUT=$(pwd)/$FH_INPUT ;; esac
  input_sha1=$(sha1sum "$FH_INPUT" | cut -d' ' -f1)
fi
wav=
if [ -n "${SPANG_WAV:-}" ]; then
  case $SPANG_WAV in /*) wav=$SPANG_WAV ;; *) wav=$(pwd)/$SPANG_WAV ;; esac
fi
for v in FH_IOLOG FH_DUMP_DIR FH_VIEWS; do
  eval "p=\${$v:-}"
  case $p in ''|/*) ;; *) eval "$v=\$(pwd)/\$p" ;; esac
done
if [ -n "${FH_DUMP_DIR:-}" ]; then mkdir -p "$FH_DUMP_DIR"; fi
script=$here/spfh_mame.lua
if [ -n "${FH_VIEWS:-}" ]; then
  mkdir -p "$FH_VIEWS"
  script=$here/views_mame.lua
  frames=1
fi

cd "$work"
# 3000 frames are 52.2 s of machine time; the script ends the run itself.
FH_OUT=$out FH_FRAMES=$frames FH_YM2413=$ym FH_INPUT_SHA1=$input_sha1 \
  FH_INPUT=${FH_INPUT:-} FH_IOLOG=${FH_IOLOG:-} FH_DUMP_DIR=${FH_DUMP_DIR:-} FH_VIEWS=${FH_VIEWS:-} \
  LC_ALL=C "$mame" spang -rompath "$work/rompath" -noreadconfig \
  -cfg_directory "$work/cfg" -nvram_directory "$work/nvram" -skip_gameinfo \
  -video none -sound none -nothrottle -seconds_to_run $((frames / 57 + 5)) \
  ${wav:+-wavwrite "$wav"} -autoboot_script "$script" > "$work/mame_stdout.txt" 2>&1 || rc=$?
if [ $rc -ne 0 ]; then
  echo "run_mame.sh: MAME exited with $rc (log: $work/mame_stdout.txt)" >&2
  exit 1
fi
if [ -z "${FH_VIEWS:-}" ] && ! grep -q "^F $frames " "$out"; then
  echo "run_mame.sh: $out has fewer than $frames F lines" >&2
  exit 1
fi
