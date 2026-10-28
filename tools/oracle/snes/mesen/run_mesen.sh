#!/bin/sh
# Start MesenCE 2.2.1 headless in test-runner mode with the switches that
# make it deterministic. Usage:
#   run_mesen.sh rom.sfc script.lua [extra Mesen switches...]
# Environment:
#   MESEN       path to the Mesen executable (default: Mesen in PATH)
#   MESEN_HOME  private HOME for Mesen (default: $XDG_CACHE_HOME/mamr-mesen-home)
#   MESEN_TIMEOUT  test-runner timeout in seconds (default 600)
#   MESEN_FILL  power-on RAM state: 00 (AllZeros, default) or ff (AllOnes)
#
# Trap: without $HOME/.config/MesenCE/settings.json Mesen ignores
# --testrunner and opens its graphical setup wizard. This script creates the
# file (content "{}") in a private HOME and refuses to start without it.
# Second trap: with that empty configuration no SNES controller is plugged
# in (emu.setInput has no effect); --snes.port1.type=SnesController fixes it.
# Mesen is run under xvfb-run when available, otherwise with DISPLAY and
# WAYLAND_DISPLAY unset, so no window can appear on the user's desktop.
set -eu
if [ $# -lt 2 ]; then
  echo "usage: $0 rom.sfc script.lua [switches...]" >&2
  exit 64
fi
rom=$1; script=$2; shift 2
mesen=${MESEN:-$(command -v Mesen || true)}
if [ -z "$mesen" ] || [ ! -x "$mesen" ]; then
  echo "run_mesen.sh: Mesen not found (set MESEN)" >&2
  exit 2
fi
home=${MESEN_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/mamr-mesen-home}
mkdir -p "$home/.config/MesenCE"
[ -f "$home/.config/MesenCE/settings.json" ] || printf '{}\n' > "$home/.config/MesenCE/settings.json"
if [ ! -s "$home/.config/MesenCE/settings.json" ]; then
  echo "run_mesen.sh: cannot create $home/.config/MesenCE/settings.json" >&2
  exit 2
fi
case ${MESEN_FILL:-00} in
  00) ram_state=AllZeros ;;
  ff) ram_state=AllOnes ;;
  *) echo "run_mesen.sh: MESEN_FILL must be 00 or ff" >&2; exit 64 ;;
esac
# Battery saves and debugger files of an earlier run must not leak into
# this one: MesenCE loads Saves/<rom>.srm at start.
rm -rf "$home/.config/MesenCE/Saves" "$home/.config/MesenCE/Debugger"
# Mesen resolves relative paths against its own data folder: pass absolute ones.
case $rom in /*) ;; *) rom=$(pwd)/$rom ;; esac
case $script in /*) ;; *) script=$(pwd)/$script ;; esac
set -- --testrunner "$rom" "$script" --timeout="${MESEN_TIMEOUT:-600}" \
  --debug.scriptWindow.allowIoOsAccess=true \
  --snes.ramPowerOnState="$ram_state" \
  --snes.disableFrameSkipping=true \
  --snes.port1.type=SnesController "$@"
if command -v xvfb-run >/dev/null 2>&1; then
  exec env HOME="$home" FH_FILL="${MESEN_FILL:-00}" xvfb-run -a "$mesen" "$@"
fi
exec env -u DISPLAY -u WAYLAND_DISPLAY HOME="$home" FH_FILL="${MESEN_FILL:-00}" "$mesen" "$@"
