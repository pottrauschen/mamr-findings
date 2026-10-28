#!/bin/sh
# Start MesenCE 2.2.1 headless in test-runner mode for the NES with the
# switches that make it deterministic. Usage:
#   run_mesen.sh rom.nes script.lua [extra Mesen switches...]
# Environment:
#   MESEN          path to the Mesen executable (default: Mesen in PATH)
#   MESEN_NES_HOME private HOME for Mesen (default:
#                  $XDG_CACHE_HOME/mamr-mesen-nes-home)
#   MESEN_TIMEOUT  test-runner timeout in seconds (default 600)
#   MESEN_FILL     power-on RAM state: 00 (AllZeros, default) or ff (AllOnes)
#   MESEN_REGION   console: Ntsc (default) or Pal (docs/nes-oracles.md
#                  section 8); Mesen's Auto is never used, its choice
#                  would depend on the file name
#
# Traps (docs/nes-oracles.md section 2): without
# $HOME/.config/MesenCE/settings.json Mesen ignores --testrunner and opens
# its graphical setup wizard. This script writes that file in a private
# HOME before every run; it holds one setting, Nes.UserPalette, a 512-entry
# palette that maps every pen (colour index plus emphasis bits) to the RGB
# value of the pen number, so the Lua screen buffer yields indices. Mesen
# never writes the file back in test-runner mode. Without
# --nes.port1.type=NesController no controller is plugged in and
# emu.setInput has no effect. Mesen runs under xvfb-run when available,
# otherwise with DISPLAY and WAYLAND_DISPLAY unset.
set -eu
if [ $# -lt 2 ]; then
  echo "usage: $0 rom.nes script.lua [switches...]" >&2
  exit 64
fi
rom=$1; script=$2; shift 2
mesen=${MESEN:-$(command -v Mesen || true)}
if [ -z "$mesen" ] || [ ! -x "$mesen" ]; then
  echo "run_mesen.sh: Mesen not found (set MESEN)" >&2
  exit 2
fi
home=${MESEN_NES_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/mamr-mesen-nes-home}
cfg=$home/.config/MesenCE
mkdir -p "$cfg"
pal=0
entries=""
while [ $pal -lt 512 ]; do
  if [ -z "$entries" ]; then entries=$pal; else entries="$entries, $pal"; fi
  pal=$((pal + 1))
done
printf '{\n  "Nes": {\n    "UserPalette": [%s]\n  }\n}\n' "$entries" > "$cfg/settings.json"
if [ ! -s "$cfg/settings.json" ]; then
  echo "run_mesen.sh: cannot write $cfg/settings.json" >&2
  exit 2
fi
case ${MESEN_REGION:-Ntsc} in
  Ntsc|Pal) ;;
  *) echo "run_mesen.sh: MESEN_REGION must be Ntsc or Pal" >&2; exit 64 ;;
esac
case ${MESEN_FILL:-00} in
  00) ram_state=AllZeros ;;
  ff) ram_state=AllOnes ;;
  *) echo "run_mesen.sh: MESEN_FILL must be 00 or ff" >&2; exit 64 ;;
esac
# Battery saves and debugger files of an earlier run must not leak into
# this one.
rm -rf "$cfg/Saves" "$cfg/Debugger" "$cfg/SaveStates"
case $rom in /*) ;; *) rom=$(pwd)/$rom ;; esac
case $script in /*) ;; *) script=$(pwd)/$script ;; esac
set -- --testrunner "$rom" "$script" --timeout="${MESEN_TIMEOUT:-600}" \
  --debug.scriptWindow.allowIoOsAccess=true \
  --nes.ramPowerOnState="$ram_state" \
  --nes.region="${MESEN_REGION:-Ntsc}" \
  --nes.autoConfigureInput=false \
  --nes.port1.type=NesController "$@"
if command -v xvfb-run >/dev/null 2>&1; then
  exec env HOME="$home" FH_FILL="${MESEN_FILL:-00}" xvfb-run -a "$mesen" "$@"
fi
exec env -u DISPLAY -u WAYLAND_DISPLAY HOME="$home" FH_FILL="${MESEN_FILL:-00}" "$mesen" "$@"
