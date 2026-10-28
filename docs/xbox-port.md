# Ikari Warriors on the original Xbox

The first console target (concept.md section 19, platform phase). The
recompiled machine, the renderer, the sound chips and the input mapping are
the same code as on the PC; only the front end and the build differ.

## What runs where

| Part | PC | Xbox |
|---|---|---|
| Machine, Z80 runner, interpreter fallback, YM3526 (ymfm), renderer, input mapping | `runtime/`, `recompiler/`, `games/ikari/` | the same files, compiled with clang for i386 (Pentium III) |
| Front end | `games/ikari/ikari_sdl.cpp`, SDL 3 | `platform/xbox/main.cpp`, SDL 2.0.9 as shipped by nxdk |
| Build | CMake, MSVC | `platform/xbox/Makefile` on top of the nxdk Makefile |
| Code | the game artefact `ikari.mamrcart` (docs/machine-interface.md section 10) | the same generated block sources and manifest (`generated/ikari`), linked in |
| ROMs | the set loaded at start from a folder or zip (`runtime/machine/rom_set`) | the set's files under their MAME names in `D:\roms\ikari\` (the folder `roms\ikari\` next to the XBE), read at start by `rom_set_load_named` and checked by SHA-1; no zip, no files under other names (the lookup needs `std::filesystem`, which the port does not rely on nxdk to provide) |

The core needs no operating system: no threads, no exceptions, no file
system library, no C++20 feature; the ROM set is read with `fopen`. A
missing or wrong file is shown on the screen with its name and expected
SHA-1 (`debugPrint`) before the return to the dashboard. Not built since
the ROM data left the generated sources (2026-10-26): the Makefile and
`main.cpp` are adapted, the loader core compiles as C++17 on the PC, a
run on the console is open. Two places call `fprintf(stderr)` and `exit`
(the FATAL paths of the CPU runners); on the console stderr goes nowhere
and `exit` reboots to the dashboard.

Two compiler details of the `i386-pc-win32` target: clang defaults to
C++14 there (the Makefile passes `-std=gnu++17`), and it defines
`_MSC_VER`, so the unmodified ymfm takes its MSVC branch and calls the
`_BitScanReverse` intrinsic; `platform/xbox/nxdk_compat.h` (force-included)
declares it, clang implements it.

One libc detail: nxdk's pdclib has 23 math functions only as placeholders
that assert at run time (`lround`, `lrint`, `log2`, `exp2`, `cbrt`,
`nextafter`, `scalbn`, `fma`, the hyperbolic inverses, the gamma and error
functions, among others; the list is `grep -l 'assert(0)'` over
`lib/pdclib/platform/xbox/functions/math/`). The core used `std::lround`
in the stick-to-facing mapping, which ended the first run on the console
with an assertion on screen; it now rounds through `floor`. `printf` ignores
floating-point conversions, hence integer-only measurements.

## Toolchain

nxdk (XboxDev) is the only freely usable toolchain for the console. It is
built around clang, lld, GNU make and shell scripts and builds the Xbox
libraries, libc (pdclib) and libc++ from source, so it wants a Unix-like
host. The documented hosts are Linux and macOS; on Windows only through
MSYS2. This port is built on a Linux host and the result is copied to the
console over FTP.

Host setup (Fedora; other distributions differ only in the package names):

```text
sudo dnf install clang lld llvm cmake make git flex bison
git clone --recurse-submodules https://github.com/XboxDev/nxdk.git ~/nxdk
cd ~/nxdk && eval "$(bin/activate -s)" && make -j8 NXDK_ONLY=y
```

`llvm` is needed for `llvm-lib`, which the nxdk wrappers call. Built with
nxdk at commit 14d5ee9 (2026-05-20) and clang 22.1.8 on Fedora 44; nxdk
warns about clang 19.0 to 20.1.2, nothing else.

## Building and uploading

From the repository root on the PC, with `generated/ikari` present (the PC
build ran `romtool --emit`):

```text
platform/xbox/remote-build.sh user@linux-host <console>
```

The script copies the sources the port needs (no ROMs, no build trees, no
test data) to `~/mamr-xbox` on the host, runs `make -C platform/xbox` with
nxdk activated and, when a console address is given, uploads
`platform/xbox/bin/default.xbe` to `F/Apps/ikari/` over FTP (UnleashX
defaults `xbox` / `xbox`, overridable through the environment, see the
script header). UnleashX lists the folder under Applications.

`generated/ikari/maincpu_blocks.cpp` has about 116000 lines; clang needs a
while for it at `-O2`. The nxdk Makefile compiles without optimisation
unless the project asks, which `platform/xbox/Makefile` does.

## Front end

- Video: `XVideoSetMode(640, 480, 32)` and the picture written straight
  into the framebuffer (`XVideoGetFB`, 32 bpp, 0x00RRGGBB like the
  renderer's output, write-combined memory): the 216x288 picture scaled
  1.5 times to 324x432 and centred (a margin for the overscan of a
  television), only those pixels written, 32-bit stores row by row, then
  `XVideoFlushFB`. Two source pixels become three output pixels, the
  middle one their average; with plain nearest neighbour every other
  stroke of the 8x8 font came out twice as wide and every other source
  row lay in a single field of the interlaced picture. Integer scaling
  would give 216x288 on the 480-line screen, too small. The encoder's
  soften filter is switched on (nxdk leaves it off, XDK games run with
  it); over a composite cable it takes the colour fringes off fine white
  text. Both are toggles on the controller for comparing on a given
  television. The first version went through SDL's
  software renderer and measured 35.7 ms per frame for the picture alone
  (full-screen clear, scaled blit, 1.2 MB copy through nxdk's byte-wise
  memcpy) against 10.8 ms for machine, renderer and audio together; hence
  the direct path. No SDL video subsystem is initialised at all.
- Sound: the nxdk SDL audio device is fixed at 48 kHz, 16-bit stereo,
  1024-sample buffers. The chip output (mono, 55555.6 Hz) is resampled
  linearly in the front end; the step is nudged by up to 0.5 % to hold
  about three frames of audio in the device queue, as the SDL 3 front end
  does through the stream frequency ratio. Above twelve frames the queue
  is cleared.
- Input: SDL game controllers only (no keyboard). White and black are the
  shoulder buttons in the nxdk SDL. Mapping in the header of `main.cpp`
  (Back + X toggles the soften filter, Back + B the smooth scaling).
- Timing: 60 machine frames per second against the performance counter,
  `SDL_Delay` to the last millisecond, then a busy wait. No vertical sync.
- Measurements: `ikari-stats.txt` next to the XBE (`D:\` in nxdk is the
  directory the XBE started from), rewritten every 60 frames and at exit.
  Fetch it with `curl ftp://xbox:xbox@<console>/F/Apps/ikari/ikari-stats.txt`.
  Integers only (the printf of nxdk's libc prints nothing for floating
  point): frames, elapsed milliseconds, frames per second times 100,
  average and worst work time per frame in microseconds against the
  16667 us budget, the same per phase (machine, render, audio, present),
  frames whose work exceeded the budget, audio underruns and backlog
  drops, interpreter fallback instructions per CPU.

## Measured

Console with Pentium III 733 MHz, 64 MB, PAL, Rocky5 softmod, UnleashX;
clang 22 at -O2, two minutes of play each (2026-10-11):

```text
                    first direct-framebuffer build   renderer in tile strips
fps                 60.00                            60.00
work per frame      15034 us (worst 17143)           13166 us (worst 14952)
  machine            7157 us                          7241 us
  render             5218 us                          3271 us
  audio               182 us                           186 us
  present            2475 us                          2466 us
frames over budget  144 of 7782                      0 of 7212
```

The budget is 16667 us. With the audio queue primed, a third run of
7597 frames reported 0 underruns. Before the direct framebuffer path the
picture alone took 35679 us through SDL's software renderer. LTO changed nothing
(15066 us) and stopped the SDL audio device from draining its queue, so
the Makefile does not use it. The next lever is the machine (three Z80
cores and two YM3526 in 7.2 ms); the renderer and the present pass are
small now.

## Open

- Vertical sync. The picture is written into the single framebuffer
  while it is scanned out, so a frame can tear. With the 60 Hz mode in
  place (below) a second framebuffer flipped with `XVideoSetFB` after
  `XVideoWaitForVBlank` is the next step; the machine then runs against
  the screen's 59.94 Hz and the audio drift control absorbs the rest.
- 60 Hz on a PAL console: with `REFRESH_DEFAULT` the kernel gave 640x480
  at 50 Hz (the game ran at 60 Hz, the screen showed 50 of those frames).
  The front end asks for `REFRESH_60HZ` first, then the default, then
  50 Hz; the 60 Hz mode exists once the dashboard allows PAL-60 (UnleashX
  video settings: Force PAL60 = Yes; Enable PAL-60 alone only serves
  titles that ask for it). Measured with it: 60 Hz mode, 60.00 fps, 13.6 ms
  work per frame, 0 of 11184 frames over budget, 0 underruns, three
  minutes of play.
- The FATAL paths print to stderr, which is invisible on the console. A
  debug text overlay for them is a possible later addition.
- R-Type is not built for the console yet; `platform/xbox/` is laid out
  for a second Makefile and front end next to this one.
