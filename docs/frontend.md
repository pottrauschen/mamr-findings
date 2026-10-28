# mamr_play: the window front end

`tools/mamr_play` shows any game behind the machine interface
(docs/machine-interface.md) in one SDL 3 window: the SNES ROMs (stage S
by default, the emitted blocks of a native build where linked), the NES
ROMs (since phase N3; stage S, the interpreter or the blocks of a game
artefact; with sound since phase N4), Ikari Warriors, R-Type and Super
Pang (the ROM set loaded at start, the native code of the game artefact
`<set>.mamrcart` or the interpreter). It has no menu:
a launcher such as ES-DE starts it with the game and gets exit code 0
at a clean end.

`ikari_sdl` and `rtype_sdl` are the same front end built with one arcade
machine and without the SNES runtime: `games/ikari/ikari_sdl.cpp` and
`games/rtype/rtype_sdl.cpp` only set the build switches of
`mamr_play.cpp` (`MAMR_PLAY_SNES 0`, the machine, the default game) and
include it. `ikari_sdl [options]` is `mamr_play [options] ikari`. The
builder kit (`tools/builder`) ships `mamr_play.exe` itself and builds
only the game artefacts.

The arcade code does not live in `mamr_play`: each game's blocks are in
its artefact, a library of its own. Where programs link the blocks of
several games statically (the headless tools link one game each, the
tests several), all have a CPU region called "maincpu", so `romtool`
names every symbol it emits after the set and the region
(`ikari_maincpu_blocks`, `rtype_maincpu_blocks`,
`spang_maincpu_keyed_blocks`, the block functions alike); with the
region alone the linker took one game's table for both from the static
libraries, and R-Type ran on the Ikari Z80 table (found by
`play_roundtrip_rtype` on the first build with both ROM sets).

## 1. Running

```text
mamr_play [options] GAME
mamr_play "Legend of Zelda.sfc"          SNES, interpreter build
mamr_play_native "Legend of Zelda.sfc"   with the emitted blocks of the ROM
mamr_play ikari                          arcade game by set name (ikari, rtype, spang)
mamr_play ~/ROMs/arcade/ikari.zip        the same, the set from that archive (or folder)
mamr_play --cartridge none ikari         the same in the interpreter
ikari_sdl                                mamr_play ikari, Ikari Warriors only
mamr_play --load-state "Zelda.sfc"       continue from the state in slot 0
mamr_play --list                         the machines this build knows
```

`mamr_play_native` exists when the build was configured with
`-DMAMR_SNES_BLOCKS_CPP=<snes_recomp output>`; it runs the ROM the
blocks were made from on them and any other ROM in the interpreter
(the start-up message says which). The same build also makes the game
artefact `<name>.mamrcart` (docs/machine-interface.md section 10), which
the plain `mamr_play` loads with `--cartridge`:

```text
mamr_play --cartridge zelda.mamrcart "Legend of Zelda.sfc"
mamr_play --cartridge smb3.mamrcart "Super Mario Bros. 3 (USA) (Rev 1).nes"
mamr_play --cartridge auto "Super Mario Bros. 3 (USA) (Rev 1).nes"
```

`--cartridge auto` looks in the cartridge directory (`--cartridge-dir`,
default `cartridges` in the data directory) for the artefact made from
this ROM, for the SNES and the NES alike (system and SHA-1 of the
manifest), and runs the interpreter when there is none. The NES
artefact of Super Mario Bros. 3 is built by tests/nes when the ROM is
present (`smb3.mamrcart` in the build tree) or by
`-DMAMR_NES_BLOCKS_CPP` (docs/machine-interface.md section 10); that of
the European release (PAL, phase P) likewise as
`smb3-eu.mamrcart`. A PAL game runs at 50.007 frames
per second with audio at 41,565 Hz; the machine takes the region from
its cartridge database (the European file's header says NTSC), and
`-o region=pal` or `-o region=ntsc` forces it (docs/nes-architecture.md
section 11). With `--sync auto` a 60 Hz display does not match the PAL
rate, so the frames are paced by the timer (section 5).

An arcade game (docs/machine-interface.md section 10) is started by its
MAME set name, by a folder or archive of the set (`.../ikari`,
`.../ikari.zip`) or by the ES-DE placeholder `<set>.mamr` (section 11).
When the machine powers on, the ROM set is loaded: for a bare name from
the first of `--rom-dir`, the data directory's `roms` (section 7) and
`roms/` below the working directory that has a folder `<set>/` or an
archive `<set>.zip`; files are taken by their MAME name or, under any
other name, by size and SHA-1; zip archives are read directly. Every
file is checked by SHA-1; a missing or wrong one ends the start with a
message that names it with its size and expected SHA-1 (exit code 1):

```text
mamr_play: ikari: ROM set ikari not found: no folder ikari/ and no ikari.zip in
           /home/me/.local/share/mamr/roms, roms
mamr_play: ikari: ROM set ikari in /home/me/.local/share/mamr/roms/ikari: 1 of 20 files missing or wrong
  1.4p: missing (size 0x10000, SHA-1 a896387d68ed9a55c313bdb81acdf8d68b7a1264; looked by name and by SHA-1)
```

Unless `--cartridge` names an artefact or `none`, the artefact of the
set is looked up in the cartridge directory: `<set>.mamrcart`, else
the first other artefact whose manifest names the set. Without one the
game runs in the interpreter (stderr: "no game artefact ikari.mamrcart
in ...: the interpreter runs"), with one on its native code ("cartridge
.../ikari.mamrcart: Ikari Warriors (set ikari, identity ...), 3
section(s), 2050 blocks"). An artefact of another game, or one made
from another set (another identity), is refused with exit code 1; an
artefact of an older ABI version too (it is rebuilt). `mamr_play
--cartridge ikari.mamrcart` without a game starts the set the artefact
names.

A ROM the artefact was not made from is refused (exit code 1). Exit codes: 0 clean end (window closed, Esc, pad combination,
`--frames` reached), 1 a failure (ROM, window, audio, save RAM not
written), 2 usage.

## 2. Options and configuration

| Option | Setting key | Default | Meaning |
|---|---|---|---|
| `--fullscreen`, `--windowed` | fullscreen | auto | auto: fullscreen when started without a terminal (a launcher), a window otherwise; on/off force it (desktop fullscreen, F11 or Alt+Return toggles) |
| `--cartridge FILE` | cartridge | | run the ROM on the game artefact FILE (section 1); `auto`: the artefact made from this ROM (by its SHA-1) in the cartridge directory, the interpreter when there is none; `none`: the interpreter. An arcade game looks its artefact up unless FILE or `none` is given |
| `--cartridge-dir DIR` | cartridge-dir | data dir `/cartridges` | where `--cartridge auto` and the arcade games look (section 7) |
| `--rom-dir DIR` | rom-dir | | arcade ROM sets: `DIR/<set>/` or `DIR/<set>.zip`, looked for before the data dir's `roms` and `roms/` below the working directory |
| `--miss-log FILE` | miss-log | | at exit, the code the interpreter had to run, as seeds for `snes_recomp` (docs/machine-interface.md section 11) |
| `--scale N` | scale | 3 | window size, N times the picture at its pixel shape |
| `--window-size WxH` | window-size | | window size in pixels instead of `--scale` (headless runs, section 6) |
| `--scaling MODE` | scaling | integer | integer: whole multiples (the width rounded for 8:7 pixels); aspect (or fit): fill the window keeping the shape; stretch; overscan: integer, one step larger where at most `--overscan` percent is cut off (section 6) |
| `--overscan N` | overscan | 8 | percent of the picture overscan scaling may cut off, per direction |
| `--video gpu/renderer` | video | gpu | draw with SDL's GPU API (Vulkan) or with SDL's renderer; gpu falls back to the renderer where there is no Vulkan device (section 6) |
| `--picture FILE` | picture | | with `--screenshot-at N`: also write the window as shown after frame N (PNG, or BMP by the extension; tests, reports) |
| `--crt off/arcade` | crt | off | the tube at start (section 12): arcade = an RGB arcade monitor; F5 or Select + d-pad up switches it; GPU path only |
| `--crt-param K=V` | crt-param | | change one constant of the tube profile (repeatable; `crt-param=K=V` in the file) |
| `--crt-list` | | | print the profile's constants with evidence class, range and source |
| `--gpu-timing on/off` | gpu-timing | off | wait for the GPU after every frame and report the mean and largest time from the swapchain image to the finished frame (section 8) |
| `--vsync on/off` | vsync | on | present with vertical sync |
| `--sync MODE` | sync | auto | auto, vsync, timer (section 4) or none (no pacing at all, as fast as the host runs; tests) |
| `--vsync-tolerance N` | vsync-tolerance | 5 | per mille: auto picks vsync mode when the display is within N per mille of the game's rate |
| `--no-audio` | audio | on | no audio device |
| `--audio-buffer MS` | audio-buffer | 64 | FIFO length in milliseconds of device time (rounded up to a power of two frames) |
| `--drc-limit N` | drc-limit | 5 | rate-control limit in per mille (section 5) |
| `--log FILE` | log | | per-frame measurements (section 8) |
| `--frames N` | frames | | stop after N frames (tests) |
| `--screenshot-at N` | screenshot-at | | write a screenshot after frame N (tests, reports) |
| `--hash-log FILE` | hash-log | | one line per emulated frame: frame number, picture size and hash, audio frame count and hash (section 9) |
| `--pads FILE` | pads | | a pad script (runtime/machine/pad_script.h, the format of machine_hash --pads) replaces the live input of both ports, by the machine's frame count, so a run loaded from a state gets the same input (tests) |
| `--load-state` | load-state | off | start from the state in the slot (after the save RAM is loaded); a missing or refused state is reported and the game starts at power-on |
| `--save-state-at N` | save-state-at | | save the state to the slot after frame N (tests) |
| `--no-saves` | saves | on | neither read nor write save RAM and states |
| `--slot N` | slot | 0 | save-state slot 0..9 |
| `--sram-interval S` | sram-interval | 5 | seconds between save RAM checks |
| `--stick-to-dpad on/off` | stick-to-dpad | on | the left stick beyond half travel also presses the d-pad |
| `--pad-quit on/off` | pad-quit | on | Select + Start held for one second quits |
| `--pad-hotkeys on/off` | pad-hotkeys | on | the Select chords of section 3 |
| `--title TEXT` | title | | window title |
| `--overclock F` | overclock | | the CPU F times as fast (1 to 4, two decimals; the SNES in stage S only), see below |
| `-o key=value` | option | | a machine option (SNES: stage, region, dsp_rate, smp_clock, ipl, blocks, sram_fill, port2, overclock; Ikari: follow_walk; R-Type: ym_reset; Super Pang: none) |
| `--config FILE`, `--no-config` | | | the settings file |

The settings file is `mamr_play.ini` in the configuration directory
(section 7), `key=value` per line, `#` comments, the keys of the table
(booleans on/off, `option=key=value` may repeat). It is read first; the
command line wins.

**Overclock** (`--overclock F`, the SNES machine option `overclock`): an
explicit option for games that slow down on the console (Gradius III,
Super R-Type), with **no accuracy claim**. The 65816 gets F times as many
cycles per scanline; everything else keeps the console's master clock:
the PPU and its lines, DMA, HDMA and the DRAM refresh, the S-SMP and the
DSP, the joypad read, the frame rate and the audio rate. The machine
does it by charging every CPU cycle its clocks / F (a 6-, 8- and
12-clock cycle become 3, 4 and 6 clocks at F = 2, rounded, at least one
clock), in the interpreter and in the emitted blocks alike (both read the
cycle cost from the bus at run time), and samples a read at the same
fraction of the shorter cycle. What a game does with the time it gains
is its own business: a game that waits for the vertical blank only
spins longer, one whose logic lagged behind the frame catches up, and
a game that counts cycles for timing (raster effects by delay loops,
APU handshakes with timeouts) may go wrong. Only stage S has it (stage E
models every bus cycle of the 5A22 and refuses the option); factor 1 is
the console's own timing, identical in every frame. It is a run-time
option: no hash line, oracle stage or test ROM run uses it.

Save states keep the factor: a state of an overclocked run carries
`/overclock=F` after the game id in its container header (the container
format and the states without overclock are unchanged), and a run at
another factor refuses it with both factors named ("save state taken
with overclock=2, this run has overclock=1"); a state of a normal run is
refused by an overclocked one the same way. Carrying the factor rather
than forbidding states keeps quick saves for the games the option is
for; the refusal keeps a state from silently changing speed. The save
RAM is the same file with or without overclock. Other machines refuse
`--overclock` (exit code 2).

## 3. Keys, pads and hotkeys

Pads: SDL's gamepad layer with its built-in mapping database, plus
`gamecontrollerdb.txt` in the configuration directory and the
`SDL_GAMECONTROLLERCONFIG` environment variable, as SDL reads them. The
first pad is port 1, the second port 2; pads may come and go while the
game runs. On the SNES, port 2 is empty unless `-o port2=pad` plugs a
joypad in (an empty port reads differently, and games test for it;
docs/machine-interface.md section 5), so a second player needs that
option. Buttons go to the machine's pad in the RetroPad layout:
south B, east A, west Y, north X, shoulders L and R, triggers L2 and
R2, sticks L3 and R3, Back Select, Start Start, d-pad and the sticks as
axes. The machine says what it does with them (docs/machine-interface.md
section 5): on the SNES this is the SNES layout; Ikari aims with the
right stick and fires with B.

Keyboard (always port 1, on top of a pad there):

| Keys | Pad |
|---|---|
| arrows | d-pad |
| Z or Y, X | B, A |
| A, S | Y, X |
| left Ctrl, left Alt, Space, left Shift | B, A, Y, X (buttons 1 to 4 of MAME's default keys) |
| Q, W | L, R |
| Return, right Shift | Start, Select |
| 1, 2 / 5, 6 / 9 / F3 | start 1, 2 / coin 1, 2 / service / test (arcade) |
| Tab (hold) | fast-forward (8 frames per presented frame, audio off meanwhile) |

What the buttons do in the arcade games (docs/machine-interface.md
section 5):

| Game | Pad | Keyboard |
|---|---|---|
| Ikari Warriors | d-pad or left stick walk, right stick aims, L/R turn the rotary knob, B or R2 fire, A or L2 grenade, Select coin, Start start | arrows walk, Q/W turn, Z or left Ctrl fire, X or left Alt grenade, 5 coin, 1 start, 9 service |
| R-Type | d-pad or left stick move, B or R2 fire, A force pod, Y and X buttons 3 and 4, Select coin, Start start | arrows move, Z or left Ctrl fire, X or left Alt force pod, Space and left Shift buttons 3 and 4, 5 coin, 1 start, 9 service, F3 test |
| Super Pang | d-pad or left stick move, B or R2 fire, A button 2 (service mode only), Select coin, Start start (port 2: player 2 start) | arrows move, Z or left Ctrl fire, X or left Alt button 2, 5 coin, 1 and 2 start, 9 service credit, F3 service mode |

`-o follow_walk=on` lets the Ikari soldier turn towards his walking
direction when the right stick is at rest (a convenience, not arcade
behaviour).

Hotkeys: Esc quit, F1 reset, Shift+F1 power cycle, F2 save state, F4 load state, F6/F7 slot
down/up, F8 screenshot, F9 mute, F10 undo the last state load (the
state before the load comes back; F10 again returns), Shift+F10 undo
the last state save (the slot's previous file comes back), F11 or
Alt+Return fullscreen, P pause, F5 the tube on or off (section 12;
F5 was free, F3 is the arcade test switch). After a hotkey fired the
next 250 ms ignore further hotkeys, so a held key or chord acts once.

On a pad, Select is the modifier: Select + L saves the state, + R loads
it, + d-pad left/right changes the slot, + d-pad up switches the tube,
+ X resets, + Y pauses, + R2 held fast-forwards, and Select + Start
held for one second quits. The chord's second button does not reach
the game; Select itself does (a game that uses Select sees it, so a
chord may also open its menu). A chord fires once per press. `--pad-hotkeys off` and `--pad-quit off`
switch the two off for games that need those combinations.

**Reset.** F1 or Select + X press the machine's reset button
(docs/machine-interface.md section 7) without leaving the window or
loading the game again, so a game under a launcher restarts without a
return to the menu. On the SNES and the NES it is the console's reset
line: the game starts again from its reset vector, the RAM and the save
RAM survive as on the console. The arcade boards have no reset button;
there the reset is a cold start that keeps only the battery memory
(Super Pang's work RAM and EEPROM), and the message says "reset (cold
start)". Shift+F1 is a power cycle on every machine: power-on from the
cold state with the save RAM given back. The proposed chord Select + L +
R was not taken: Select + L and Select + R already save and load the
state and fire on the first of the two buttons, so the chord would save
or load before it resets; F10 is the undo of a state load. Select + X
and F1 have called `reset()` since the front end exists.

Two rules for a start from a launcher (section 11): a button or key
that is down within the first half second after start (the launcher's
"start game" button, still held) does not reach the game until it is
released; and at the end the window is hidden first and the front end
waits up to two seconds for every button and key to be released, so
the launcher does not take the quit combination as its own input.

## 4. Timing model

The game runs in its own clocks: `run_frame` is one frame of console
time (the SNES: one field from one sampling point to the next, 425568
master clocks on PAL, 357366 on average on NTSC), whatever the host
does. The host only decides when to run the next frame:

- **vsync mode**: the display refresh is within the tolerance of the
  game's frame rate (`--vsync-tolerance`, 5 per mille by default:
  60.0988 Hz NTSC on a 60 Hz display, 50.007 Hz PAL on a 50 Hz
  display). One frame per presented picture; the display's clock paces
  the game, which therefore runs at the display's rate (0.23 percent
  slow on a 59.963 Hz display), and the audio enters the resampler at
  its rate scaled the same way, so the pitch follows the speed and the
  rate control only has the drift between the display and the audio
  clock left. This is the smooth case: no frame is ever shown twice or
  skipped. The tolerance may be raised to the 5 percent RetroArch
  allows (`--vsync-tolerance 50`); the game then runs up to 5 percent
  off and the audio is pitched accordingly, audible but smooth.
- **timer mode**: otherwise (a 50 Hz game on a 60 Hz display, vsync
  off, an unknown refresh rate, SDL's dummy driver). A deadline per
  frame comes from the exact frame length (`frame_rate_hz()` of the
  description as a fraction of master clocks), the loop sleeps to it
  with the host's high-resolution timer and presents then. With vsync
  on, the presentation waits for the next refresh: a 50 Hz game on a 60
  Hz display shows every fifth frame twice (visible as a small judder
  in scrolling), the game's speed and the sound are exact. A variable
  refresh rate display (VRR, FreeSync, G-Sync) follows the presented
  cadence instead, so the game plays at its native rate without the
  repeat; the front end does nothing special for VRR beyond presenting
  on time. If the loop falls behind by more than four frames (a window
  drag, a slow machine) the deadline chain restarts from now and the
  log counts a resync; emulated frames are never skipped.
- `--sync vsync` and `--sync timer` force a mode. `--sync vsync` on a
  display far from the game's rate plays the game too fast or too slow
  (a 50 Hz game at 60 Hz runs 20 percent fast, with the audio pitched
  the same); it is for displays whose mode SDL reports wrongly.
- **R-Type (55.017 Hz)** has no matching display mode anywhere: it runs
  in timer mode on every display, at its exact rate with exact sound,
  and on a 60 Hz display every eleventh frame is shown twice (on a 120
  Hz display the repeats are half as long; a VRR display shows none).
  Ikari Warriors (60 Hz), NTSC SNES games and NTSC NES games (60.0988
  Hz, the same field rate) take vsync mode on 60 Hz displays; PAL SNES games need a 50 Hz mode or VRR for the smooth case
  and otherwise run in timer mode with every fifth frame repeated.
- **Super Pang (57.42 Hz)**, MAME's frame of 139,324.28 Z80 cycles,
  likewise runs in timer mode on a 60 Hz display (4.3 percent off, far
  outside the vsync tolerance): exact rate and sound, about every 23rd
  frame shown twice; a VRR display shows none.

Fast-forward runs eight frames per presented picture without audio;
pause presents the last picture and feeds nothing to the audio FIFO
(the device repeats the last sample).

## 5. Audio

Every frame's samples (interleaved stereo int16 at the machine's audio
rate, exactly as many as the hardware produced) go into the resampler
and bounded FIFO of `runtime/snes/snes_audio_out.h`, which the SNES
audio phase wrote for this purpose and which is generic: 4-point
Hermite interpolation from the machine rate to the device rate, a
single-producer single-consumer FIFO, and dynamic rate control. SDL's
audio thread pulls from the FIFO in the stream callback; the device is
opened at its own rate (SDL does no second resampling) and started
once the FIFO is half full.

Rate control: the resampling step is the nominal ratio times
`1 + d/2 * (2 * fill / capacity - 1)` with `d` the limit (0.5 percent
by default), plus a slow integral term bounded by `d/2` that moves the
working point back to the middle of the FIFO when the two clocks
differ by a constant amount. So the total correction stays within `d`,
a FIFO running full slows the production, one running empty speeds it
up, and nothing is ever dropped or padded (an underrun repeats the
last sample, an overrun drops frames; both are counted and logged, and
both mean the clocks differ by more than the limit allows). This is
the dynamic rate control idea of RetroArch, implemented here from the
description, not from its code.

Machine rates: the SNES DSP's 32 kHz (or the measured clock), the NES
CPU clock / 40 = 44,744.3 Hz (its samples already decimated and filtered
by the machine adapter, docs/nes-audio-spec.md section 9), the arcade
sound chips' own rates.

With the 64 ms default the FIFO holds 4096 frames at 44.1 or 48 kHz
(93 or 85 ms), the working point is half of that, so the audio latency
from `run_frame` to the device is about 45 ms plus the device's own
buffer.

## 6. Picture

The frame is uploaded to a texture of its own size (it may
change: SNES hi-res 512 pixels, PAL overscan 239 lines) and drawn
with nearest-neighbour scaling into a rectangle of the picture's shape:
width times the frame's pixel aspect over height (SNES 8:7, so 256 x
224 becomes 4:3; 512-pixel lines have 4:7 pixels; Ikari 1:1; R-Type
8:9; Super Pang 5:6, 384 x 240 on a 4:3 monitor). Integer scaling picks the largest whole multiple of the height
that fits and rounds the width (a 4:3 picture needs non-integer
horizontal scaling for 8:7 pixels; the alternative, integer in both,
would show the wrong shape), aspect scaling fills the window keeping
the shape, stretch fills it. Overscan scaling is integer scaling one
step larger where the part that falls outside the window is at most
`--overscan` percent (default 8) in each direction, cut evenly on both
sides, as a television hides a few percent at each edge: at 1080 lines
the SNES's 224 lines become 5 x 224 = 1120 (3.6 percent cut, instead of
4 x with 184 black lines), the NES's 240 lines stay 4 x (5 x would cut
10 percent), Ikari Warriors 4 x 288 = 1152 is cut 6.25 percent, R-Type
and Super Pang stay 4 x. The window opens at `--scale` times the
nominal picture (`--window-size` sets it in pixels); fullscreen is the
desktop mode (no mode switch).

**Two paths** (`shader/src/play_video.cpp`). The GPU path, the
default since stage 1 of the tube work, draws with SDL's GPU API: the
device is Vulkan with SPIR-V shaders (`SDL_CreateGPUDevice`, the window
claimed for it), the frame goes through a transfer buffer into a BGRA
texture (XRGB8888 in memory is B, G, R, X), and one triangle over the
whole swapchain image runs a fragment shader per window pixel. The
pass-through shader `shader/glsl/copy.frag` shows the frame pixel under
each window pixel's centre inside the picture rectangle and black
outside it. Present mode: FIFO with vsync, immediate (else mailbox)
without; one frame in flight, so the picture is at most one frame
behind the machine. The renderer path is the SDL_Renderer of before
(streaming texture, `SDL_SCALEMODE_NEAREST`, `SDL_RenderTexture` into
the same rectangle). `--video renderer` chooses it; `--video gpu` falls
back to it with the reason on stderr where no Vulkan device can be had
or the window cannot be claimed (SDL's dummy video driver of the tests,
a host without Vulkan). stderr names the path, the device and its
driver (`video: gpu vulkan (NVIDIA Quadro P620, ...)` or
`video: renderer opengl`), the summary line ends with `video=gpu` or
`video=renderer`.

The shaders are GLSL in `shader/glsl/`; the program embeds
their SPIR-V from `shader/spirv/*.h`, which is generated and kept in
the repository, so a build needs no shader compiler. After a change to
a shader: `cmake --build <tree> --target mamr_play_spirv` with
glslangValidator (Debian and Ubuntu package `glslang-tools`; the
target exists where CMake finds it, another one with
`-DGLSLANG_VALIDATOR=<path>`), which writes the headers again; the test
`play_spirv_current` compiles every shader and fails when a header is
not the compiled GLSL. glslang 16.2.0 made the headers in the
repository.

**Same picture on both paths.** Where a window pixel's centre falls
exactly on the edge between two frame pixels (the integer scaling of
R-Type's 8:9 and Super Pang's 5:6 pixels in some columns, 3.75 times for
Ikari's aspect scaling at 1080 lines in every other column, most aspect
and stretch scaling), either neighbour is right. A GPU renderer's choice
there depends on how its interpolation rounds: SDL's gpu, vulkan and
opengles2 renderers on Mesa's NVK driver and on lavapipe take the left
neighbour at one edge and the right one at the next. The pass-through
shader decides like exact arithmetic: it rounds the frame position to
1/256 of a pixel, as a sampler does (Vulkan's sub-texel precision,
8 bits on these drivers), and an edge goes to the right or lower pixel.
`play_video_passthrough` (section 9) checks the GPU path against the
exact nearest-neighbour picture computed from the frame, for both window
sizes and all four scaling modes: equal in every pixel off an edge, and
at an edge one of the two neighbours; and against SDL's GPU renderer on
the same device (`SDL_RENDER_DRIVER=gpu`): equal in every pixel off an
edge. Off the edges the vulkan and opengles2 renderers give the same
bytes too; the software renderer steps through the texture in fixed
point and also picks the neighbour a little away from the edges (SNES
and NES aspect scaling at 1920x1080: 498 and 3360 pixels). With
whole-number factors in both directions (Ikari's integer and overscan
scaling) there are no edges and all paths are byte-equal. At
1920x1080, Ikari's aspect scaling has 7716 edge pixels where the GPU
path and SDL's GPU renderer differ, R-Type's integer scaling 296, the
NES's integer scaling 232 (only edges with different colours on both
sides count).

**Headless.** SDL's offscreen video driver (`SDL_VIDEO_DRIVER=offscreen`)
draws its windows through Vulkan's headless surface, so the GPU path
runs without a screen; `--picture` writes the window as shown (the GPU
path renders the frame a second time into a texture of the swapchain's
size and downloads it, the renderer path reads its target back). This
needs a Vulkan driver whose headless surface can present: Mesa's (NVK,
lavapipe) can, NVIDIA's 580 driver cannot ("This surface does not
support presenting"), and there the GPU path falls back to the renderer.

## 7. Files

XDG directories on Linux (SDL's preference path on Windows):

| What | Where |
|---|---|
| settings | `$XDG_CONFIG_HOME/mamr/mamr_play.ini` (default `~/.config/mamr/`) |
| pad mappings | `$XDG_CONFIG_HOME/mamr/gamecontrollerdb.txt` |
| save RAM | `$XDG_DATA_HOME/mamr/saves/<id>.srm` (default `~/.local/share/mamr/`) |
| save states | `$XDG_DATA_HOME/mamr/states/<id>.<slot>.state` |
| screenshots | `$XDG_DATA_HOME/mamr/screenshots/<id>-<time>.bmp` |
| game artefacts for `--cartridge auto` | `$XDG_DATA_HOME/mamr/cartridges/*.mamrcart` (any name; the first in name order whose manifest names the ROM's SHA-1; an arcade game `<set>.mamrcart` first, then any whose manifest names the set) |
| arcade ROM sets | `$XDG_DATA_HOME/mamr/roms/<set>.zip` or the folder `<set>/` there (after `--rom-dir`, before `roms/` below the working directory) |

`<id>` is the machine's identifier (`snes-<sha1 of the ROM>`, `ikari`,
`rtype`, `spang`). Save RAM is the linear byte image (`.srm` convention, 8 KiB
for Zelda; for Super Pang the 8 KiB battery-backed work RAM followed by
the 128-byte EEPROM), loaded after power-on, written atomically (temporary file,
fsync, rename over the old file) whenever it changed at the check
interval and at exit; a write failure at exit gives exit code 1. Save
states are the machine's versioned state (docs/machine-interface.md
section 6) in the same atomic way; a state of another game or state
version is refused with a message in the title bar and on stderr.

## 8. Measurements

`--log FILE` writes a header (game, frame rate, audio rate, device rate,
display rate, mode, limit, FIFO size) and one line per presented frame:
frame number, host time in ms, interval since the previous
presentation, audio frames pushed so far, FIFO fill, rate deviation in
per mille, underruns, overruns; and a summary line at the end with the
totals, the minimum and maximum deviation, the mean and maximum
interval and the resync count. The same summary goes to stderr; it
ends with the picture path (`video=gpu` or `video=renderer`) and, with
`--gpu-timing on`, `gpu_ms_mean` and `gpu_ms_max`: the GPU path waits
for its fence after every frame and counts from the acquired swapchain
image to the finished frame, so the upload and the shader are in it and
the wait for the display is not (the wait costs the overlap of the CPU
and the GPU, so it is a measurement option, off by default).

Measured on the development machine (Linux, Wayland, a display at
59.963 Hz, the audio device at 44.1 kHz): Zelda USA (NTSC, 60.0988 Hz)
in a window for 900 frames took vsync mode, the game running 2.26 per
mille slow at the display's rate; the rate deviation stayed between
-2.98 and +2.73 per mille (limit 5), no underrun, no overrun, mean
frame interval 16.676 ms, the longest 16.720 ms, no resync. The tests
of section 9 check the invariants on every build.

The arcade machines on the same machine (GCC, RelWithDebInfo, SDL's
dummy drivers, two other builds running, load average about 6):
unpaced (`--sync none`), 6000 frames took 6.2 s for Ikari Warriors
(1.0 ms per frame, 16 times its 60 Hz) and 21.0 s for R-Type (3.5 ms
per frame, 5 times its 55.0176 Hz); in timer mode over 600 frames the
mean frame interval was 16.668 ms for Ikari (nominal 16.667, the
longest 17.18 ms) and 18.178 ms for R-Type (nominal 18.176, the longest
18.96 ms), no resync, no overrun, and the audio count exact (555555 of
555556 frames for Ikari, the first frame starting at power-on; 609954
of 609954 for R-Type), the rate deviation within -4.1 and +1.3 per
mille. The dummy device's underruns (18 and 2) are its sleep loop, as
in section 9. Super Pang (2026-10-26, the same setup, load average
about 5): unpaced, 6000 frames in 6.1 s (1.0 ms per frame, 17 times its
57.42 Hz; the CPU on recompiled blocks); in timer mode over 600 frames
the mean frame interval was 17.418 ms (nominal 17.416, the longest
19.50 ms), no resync, no overrun, the audio count 580517 of 580518
frames, the rate deviation within -4.1 and +1.7 per mille, one
underrun. A window at the screen and the second machine at the
television are still to be measured.

## 9. Tests

`tests/machine`:

- `play_dummy_gilyon`, `play_dummy_zelda`, `play_dummy_smb3` (phase N4,
  the interpreter), and `play_dummy_ikari`, `play_dummy_rtype`,
  `play_dummy_spang` where the ROM sets are present (the set folder as
  the game, `--cartridge` the build's artefact): `mamr_play` with
  SDL's dummy video and audio drivers, 300 frames in timer mode, in a
  private XDG data directory. The log must show 300 frames and 300 rows, the audio
  sample count of the machine's rates (one frame of slack: the first
  frame starts at power-on and ends at the first sampling point), the
  rate deviation within the limit, the mean frame interval within 2
  percent of the frame length, no resync and no overrun. Underruns are
  reported but not judged: the dummy device's clock is a sleep loop.
  They run alone (ctest RUN_SERIAL): they measure real time against the
  host timer, which parallel tests would disturb. Other work on the host
  disturbs it as well, and an unoptimized build may not reach the frame
  rate at all (the interpreter at -O0 needs about 20 ms for a 16.6 ms
  frame of `cputest-full.sfc`). The script therefore skips (exit code 2)
  with the reason printed when the build type is empty or Debug, or
  when the one-minute load in `/proc/loadavg` is above half the
  processor count; measure in a Release or RelWithDebInfo tree. The
  arcade runs (GCC, RelWithDebInfo, load average about 2): mean frame
  interval 16.669 ms for Ikari Warriors (nominal 16.667) and 18.180 ms
  for R-Type (nominal 18.176), audio 277777 of 277778 and 304977 of
  304977 frames, rate deviation within -3.6 and +1.5 per mille; Super
  Pang 17.419 ms (nominal 17.416), audio 290258 of 290259 frames, rate
  deviation within -3.5 and +1.7 per mille. Super
  Mario Bros. 3 (2026-10-26, RelWithDebInfo, load about 4.7 of 16
  processors): mean interval 16.669 ms (nominal 16.639), audio 223291
  of 223354 frames (the first frame is shorter), rate deviation within
  -3.9 and +1.1 per mille, no overrun, no underrun.

- `play_roundtrip_gilyon`, `play_roundtrip_zelda`,
  `play_roundtrip_zelda_cartridge`, and `play_roundtrip_ikari`,
  `play_roundtrip_rtype`, `play_roundtrip_spang` where the ROM sets are present
  (`check_play_roundtrip.py`): `mamr_play` with the dummy drivers and
  `--sync none` against `machine_hash`, the machine without a front end.
  The picture and audio hashes of every frame must be equal; the state
  saved at frame K (`--save-state-at`) must start with the container
  magic and, loaded from its file by a second run (`--load-state`),
  repeat frames K+1..N exactly; where the machine has save RAM, the .srm
  is seeded with a byte pattern before the run and must afterwards hold
  the machine's own image after frame N (Zelda rewrites 8 of its 8192
  bytes in 600 frames); no temporary file of the atomic writes may be
  left. The cartridge variant runs the game artefact in the front end
  and the interpreter in the reference, so it also proves the loaded
  blocks frame-identical to the interpreter through the front end.
  For Ikari Warriors, R-Type and Super Pang the run is 1200 frames of
  attract mode with sound and the state is taken after frame 600, the
  front end on the game artefact (`--cartridge`), `machine_hash` in the
  interpreter, both loading the set from its folder; for
  Ikari and R-Type the same check passes with the state after frame 1,
  37, 1777 and 2999 of 3000. Super Pang's save RAM (work RAM and
  EEPROM) goes through the .srm check like Zelda's.
  `machine_state_ikari`, `machine_state_rtype` and `machine_state_spang`
  (docs/machine-interface.md section 9) add the second serialize after
  the load and the refused states in one process;
  `machine_state_ikari_game`, `machine_state_rtype_game` and
  `machine_state_spang_game` do the same in the middle of a game played
  with input from a pad script, at six, five and six points (scrolling,
  enemies, sound, a life lost, the Ikari knob in mid-turn, Super Pang's
  balls splitting and the player hit).
  Super Mario Bros. 3 (phase N4): `play_roundtrip_smb3` (the game
  artefact in the front end) and `play_roundtrip_smb3_interp` play 1200
  frames with tests/machine/smb3-game.pads given to both programs
  (`--pads`: title, map, World 1-1, so the map and level tunes and the
  effects sound) and require at least 600 different audio hashes (791
  are seen; silence of one length has one hash), so the audio comparison
  and the state of frame 600 compare sound; `machine_state_smb3_game`
  checks six states from the map to the level in one process.

- `play_launcher_gilyon`, `play_launcher_zelda_cartridge`: the start
  from a launcher, section 11.

- `play_overclock_zelda` (local, `tests/machine/check_overclock.py`):
  `--overclock 1` for 300 frames equal to `machine_hash` without the
  option; `--overclock 2` runs 600 frames with the state saved after
  frame 300 (222 of the first 300 frames differ from factor 1: Zelda's
  lag frames are gone); that state refused by a run without overclock
  with the factor named and loaded at factor 2; stage E with overclock
  refused. By hand: the Zelda artefact (`zelda.mamrcart`) at factor 2
  gives the interpreter's hash lines in all of 600 frames.

- `play_video_passthrough` (`tools/mamr_play/tests/check_video.py`): the
  picture paths (section 6), headless with the offscreen driver, for the
  SNES test ROM, nestest and the arcade sets present (interpreter, frame
  650, its F8 screenshot and the window picture as BMP): for 1920x1080
  and 1280x720 and the four scaling modes, the GPU path's window must be
  the exact nearest-neighbour picture of the frame and equal to SDL's GPU
  renderer on the same device, every pixel off a source pixel edge (a
  centre within 1/256 pixel of an edge may show either neighbour; their
  count is printed); the renderer drivers vulkan, opengles2 and software
  are compared once per game and reported. It skips (exit code 2) with
  the reason where the GPU path falls back. `play_spirv_current` (where
  glslangValidator is found): the SPIR-V headers are the compiled
  shaders.

- `play_crt_arcade` (`tools/mamr_play/tests/check_crt.py`): the tube
  (section 12), headless like `play_video_passthrough`, the same games at
  1920x1080 with integer scaling: two runs with `--crt arcade` give the
  same bytes; `--crt off` gives the bytes of a run without the option;
  all three stages off give the pass-through picture (at most one step
  per channel allowed, none seen); beam and mask keep the light (with
  the amplifier off, the mean linear light of the window within 1
  percent of the pass-through's: 0.995 to 1.001 seen; the whole chain's
  ratio, 0.964 to 1.000, is printed); and the scanlines run the right
  way: with amplifier and mask off, no two window pixels inside one
  source pixel along the scanlines differ, while across the lines most
  do (rows for the landscape monitors, columns for Ikari). Skips where
  the GPU path falls back.

- `arcade_errors` (docs/machine-interface.md section 9) runs the front
  end too: an artefact of another game refused, the interpreter fallback
  without an artefact, the artefact found by set name with the set below
  `--rom-dir` (the command of section 11), a missing set refused.

## 10. Known limits

- No menu, no in-game configuration; a launcher does the choosing
  (section 11).
- No autosave state at exit yet (a launcher restart begins at power-on
  with the save RAM).
- The arcade save states are checked in attract mode and in the middle
  of a game played with scripted input through the machine interface
  (docs/machine-interface.md section 9); `play_roundtrip_ikari`,
  `play_roundtrip_rtype` and `play_roundtrip_spang` still run attract
  mode, although `mamr_play --pads` (phase N4) would now allow a played
  round trip as for Super Mario Bros. 3.
- The keyboard plays port 1 only; the old arcade programs had keys for
  a second player. A second player uses a pad.
- The arcade machines, `ikari_sdl` and `rtype_sdl` build without ROMs;
  the game artefacts and the arcade tests need the ROM sets at build
  time. Super Pang has no single-game program (`spang_sdl`). The builder
  kit (artefacts on Windows, docs/machine-interface.md section 10) has
  not been built with MSVC since it makes artefacts: its compile and
  link steps, the DLL export of `mamr_cartridge` and the copy of the set
  are written for MSVC and Windows but unchecked there.
- A clone set whose files live in its parent's archive is not found
  (the three sets are parent sets); 7z archives are not read.
- The arcade reset (F1, Select + X) is a cold start (the boards have no
  reset button); no watchdog is modelled.
- Overclock only on the SNES in stage S; the NES and the arcade CPUs
  have none (section 2).
- Screenshots are BMP (SDL writes those without another library);
  `--picture` writes the window as shown, PNG or BMP.
- The tube (section 12) has the arcade profile only and needs the GPU
  path; headless (the offscreen driver) the GPU path needs a Vulkan
  driver whose headless surface presents (Mesa yes, NVIDIA 580 no).
- One keyboard layout, no remapping yet; pads are remapped through
  SDL's mapping file only.
- 50 Hz on a 60 Hz display without VRR judders (section 4); the smooth
  alternatives are a 50 Hz display mode or VRR.
- Audio runs at the device's rate through one resampler; a device that
  only offers a far-off rate (8 kHz) is not refused.

## 11. Running under ES-DE

ES-DE (EmulationStation Desktop Edition, MIT) can launch `mamr_play`
like any standalone emulator; nothing in MAMR depends on it. How ES-DE
launches and what a program owes it is in docs/frontend-landscape.md
sections 1.6 and 5; in short, on Linux it runs the command through
`/bin/sh` from `popen` with ` 2>&1 &` appended, keeps its own
full-screen window open, reads the merged output until end of file,
then takes over again. It passes no fullscreen flag, never kills the
program and, because of the `&`, never sees its exit code.

**Configuration.** Two example files, to be copied into ES-DE's
`custom_systems` directory (`~/ES-DE/custom_systems/`):

- `tools/mamr_play/es-de/es_find_rules.xml` defines the emulator
  `MAMR-PLAY`: `mamr_play` in the search path, else `~/.local/bin`,
  `~/bin` or `/opt/mamr/bin`.
- `tools/mamr_play/es-de/es_systems.xml` defines the systems `snes`
  (ROM files `.sfc`/`.smc` in `~/ROMs/snes`; default command
  `--fullscreen --cartridge auto %ROM%`, a second one for the
  interpreter alone), `nes` (`.nes` files in `~/ROMs/nes`, the same two
  commands) and `arcade` (`~/ROMs/arcade/ikari.mamr`,
  `rtype.mamr` and `spang.mamr`, empty files; the command passes
  `%BASENAME%`, the set name). For an arcade game `mamr_play` then loads
  the ROM set from the data directory (`~/.local/share/mamr/roms/
  ikari.zip` or the folder `ikari/` there, section 1) and the game
  artefact from `~/.local/share/mamr/cartridges/ikari.mamrcart`, or runs
  the interpreter when that file is absent; the command is the same in
  both cases.

The systems carry the names of ES-DE's own `snes`, `nes` and `arcade` and so
replace them (a custom system wins over the bundled one of the same
name). That keeps the theme artwork of the real platforms, the scraper
platform and, for `arcade`, ES-DE's MAME title lookup, which shows
`ikari.mamr` as "Ikari Warriors (US JAMMA)" (`spang.mamr` names the
MAME set `spang` the same way; what ES-DE shows for it is not checked
yet). It matches the plan of one
runtime per system behind one menu. The price: ES-DE's bundled emulator
commands for those three systems are gone while the file is in place.
Whoever wants them side by side renames the systems (`mamr-snes`,
`mamr-nes`, `mamr-arcade`, with the `<theme>` of the real platform)
and gives each its own directory.

**What mamr_play does for a launcher:**

- the window: `--fullscreen` in the command, and without it the
  terminal check picks fullscreen anyway (stdout and stderr are the
  launcher's pipe); the window asks for focus and the top, because the
  launcher's own full-screen window stays open;
- output: stdout stays empty, the messages go to stderr, a few lines
  per run (ES-DE writes them to `~/ES-DE/logs/es_log.txt` when started
  with `--debug`);
- no child process, nothing keeps the pipe open after the exit, so the
  launcher returns as soon as the game ends;
- quit: Select + Start held for one second on a pad, or Esc; the window
  is hidden first, the save RAM written, the release of the buttons
  awaited (section 3), exit code 0;
- the launcher's "start game" button still held at start does not
  reach the game (section 3);
- `--cartridge auto` finds a game's artefact by the ROM's hash, so one
  command serves every SNES game (artefacts in the cartridge directory,
  section 7); an arcade game finds its artefact by the set name without
  the option.

**Checked without ES-DE** (section 9 style, ctest label oracle-free and
local): `play_launcher_gilyon` and `play_launcher_zelda_cartridge`
(`tests/machine/check_launcher.py`) start `mamr_play` exactly that way,
with the ROM path escaped as ES-DE escapes `%ROM%` and the dummy SDL
drivers: end of file arrives and no `mamr_play` is left, every line on
the pipe is one of `mamr_play`'s stderr lines, stdout alone is empty,
the window is full-screen by the terminal check, and with an artefact
in a private cartridge directory `--cartridge auto` runs its blocks.

**On a second machine** (a Linux machine at a television, Ubuntu 26.04,
ES-DE installed): the same `mamr_play` with all three machines starts
Ikari Warriors and R-Type from the names and Zelda through
`--cartridge auto` with the dummy drivers, 300 frames each, exit code 0
(0.72 ms per Ikari frame, 3.07 ms per R-Type frame unpaced); the
`arcade` system there has its two empty files. The start from ES-DE at
the television is still to be checked.

**Not known yet** (needs a run at the screen): whether the compositor
gives the game's window the focus over ES-DE's full-screen window (on
GNOME with Wayland a window without an activation token may open behind
it); whether ES-DE acts on any button released after the return (the
wait for release should prevent it); ES-DE's own keyboard mapping has
Escape as its Start button, which matters only when Esc is still held.
A start failure (a missing ROM, a missing or wrong file of an arcade
set, a missing machine) returns at once to the menu without a message;
the reason, with the file name and its expected SHA-1, is in ES-DE's
log with `--debug`.

## 12. The tube shader

The GPU path (section 6) can draw the picture as a tube would show it.
The aim is MAMR's own tube shader under the repository's licence with
three profiles: the arcade monitor (profile `arcade`), a PAL
television on the SNES's RGB SCART and a PAL television on the NES's
composite signal. Stage 1 is the arcade profile. The shader
(`shader/glsl/crt.frag`) and its constants (`shader/src/play_crt.cpp`)
are written for MAMR from the research of 2026-10-27
(docs/crt-research-evaluation.md: the chain every project shares, the
K7000 data, the beam measurements); crt-lottes (public domain) and crt-beans (MIT) were read
as examples of the chain, nothing is taken from the GPL shaders
(crt-guest, koko-aio, crt-royale, crt-geom, MAME's shaders, OSSC,
MiSTer).

**Use.** `--crt arcade` starts with the tube, `--crt off` (the default:
a launcher's start shows the picture as before) without; F5, or Select +
d-pad up on a pad, switches it at any time, and the window title says
"tube on" or "tube off". It needs the GPU path; on the renderer path F5
says so in the title and `--crt arcade` on stderr. `--crt-list` prints
the profile's constants with their class and source,
`--crt-param key=value` changes one (repeatable, also in the settings
file as `crt-param=key=value`), so a value can be tried at the
television without a build. The switches `lowpass`, `beam` and `mask`
(1 on, 0 off) take a stage out. At start stderr names the profile, the
pixel rate with its source and whether the monitor is rotated, and the
first frame the triad pitch in window pixels and the tile length.

**The chain**, per window pixel, in one pass (the comment at the top of
`crt.frag` has the formulas):

1. *Signal.* The frame's values are the video voltages. Along the
   scanline the video amplifier's bandwidth smears them: every source
   pixel is a box one pixel time long (the DAC holds it), convolved with
   a Gaussian impulse response of sigma_h source pixels and integrated
   in closed form (erf; the three weights depend on the position along
   the line only and are shared by all lines). sigma_h follows from the
   -3 dB bandwidth B and the pixel rate R: |H(f)| = exp(-2 pi^2 sigma_t^2
   f^2) is 1/sqrt(2) at B for sigma_t = 0.1323 / B, so sigma_h = 0.1323 R
   / B. The filter works on voltages, before the tube's power law, where
   the amplifier is; the power law then makes a blurred edge darker than
   the mean of its two sides, as on the tube (fine detail loses light:
   2.7 to 3.6 percent of the whole picture for the SNES test ROM, nestest
   and R-Type, nothing measurable for Ikari and Super Pang). The window
   pixel is sampled at its centre: a box of its width here would blur
   the voltages a second time and take light without a physical reason
   (by itself it took 3.5 percent of the SNES test ROM's light; the
   first version had it), and the amplifier's sigma alone spans 0.25 to
   0.35 window pixels at 1080 lines, enough for smooth edges at
   non-integer scaling.
2. *Tube.* The voltage becomes light with the tube's power law
   (gamma_tube 2.4): from here on linear light, per gun.
3. *Beam.* Across the lines each line is a Gaussian spot profile whose
   sigma grows with the gun's light L: sigma = beam_sigma + beam_growth *
   L lines (0.20 to 0.45), plus the window pixel's height as a box of the
   same variance (linear light, so it keeps the light). The profile is
   normalized to its area: a
   line gives the same light whatever its width, as the beam's charge
   does not depend on the spot. A dark line is thin with dark gaps
   beside it, a bright one fills them; the picture's mean brightness is
   the frame's. beam_sigma + beam_growth >= 1/sqrt(2 pi) = 0.40 keeps a
   full white line at or below full scale. The five nearest lines are
   summed.
4. *Mask.* The phosphor stripes: a tile of RGB texels drawn on the CPU
   (`crt_mask_tile`), one texel per window pixel along the scanline,
   repeated. Stripe R, G and B each cover a third of the pitch less the
   gap (mask_gap 0.15 of the pitch dark between them), each texel holds
   the part of a stripe it covers. Each channel is divided by its mean
   over the tile, so the mask neither darkens nor brightens on average,
   and mixed in with the strength: mix(1, mask / mean, k).
5. *Balance.* Where the mask would push a channel above full scale (a
   bright cell is mean x max_ratio), k is lowered per channel until the
   brightest cell just fits: k = min(strength, (1/L - 1)/(max_ratio - 1)).
   The mask fades out towards white and every triad keeps the light
   the beam gave (the crt-beans approach, in MAMR's own form; the other
   one, gain in the lit cells as MiSTer and the OSSC do it, clips).
6. *Output.* Back to the display's signal with 1/gamma_out.

Rotated monitors: the scanlines run down the window (the frame's
columns) and the stripes across it, the mask tile along the window's
vertical axis (as MiSTer's presets rotate scanlines and mask with the
monitor and MAME BGFX swaps the scanline axis). mamr_play rotates
nothing: the Ikari machine hands over the player's view, 216 x 288
(`games/ikari/ikari_video.h`, ROT270), and the tube only needs to know
that the frame's columns are the scanlines.

**Pixel rate and rotation per machine.** The machine interface carries
neither (docs/machine-interface.md is unchanged): the front end keeps
them in a table by `Description::id` (`crt_raster` in `play_crt.cpp`).
The pixel rate is the frame's nominal pixels per second of active line
time: the pixel clock where it is known, else line rate x pixels per
line.

| Machine | Pixel rate | Class | Source | sigma_h (amplifier) |
|---|---|---|---|---|
| Ikari Warriors | 60 Hz x 264 lines x 384 = 6.083 MHz | CHOICE | MAME snk.cpp: 60 Hz, no raw timing; 264 lines and 384 pixels the usual 15.8 kHz raster | 0.067 px |
| R-Type | 8 MHz | DOC | MAME m72.cpp `set_raw(MASTER_CLOCK/4, 512, ..., 284)` (docs/rtype-hardware-spec.md) | 0.088 px |
| Super Pang | 15.16452 kHz x 512 = 7.764 MHz | DOC/CHOICE | line rate from the PCB note (mitchell.cpp:68, docs/spang-hardware-spec.md), 512 pixels per line assumed | 0.086 px |
| SNES, NES (NTSC) | 21.477 MHz / 4 = 5.369 MHz | DOC | master clock / dot length | 0.059 px |
| SNES PAL / NES PAL | 21.281 MHz / 4, 26.602 MHz / 5 = 5.32 MHz | DOC | master clock / dot length | 0.059 px |
| other | 6 MHz | CHOICE | | |

Ikari is rotated (ROT270 in MAME, DOC); the others are not. A SNES
hi-res frame (512 pixels) has twice the rate. The result: at 12 MHz the
K7000's amplifier barely touches these boards (rise time 0.35 / 12 MHz
= 29 ns against a pixel of 125 to 186 ns; the monitor was built for 560
pixels per line): sigma_h is 0.06 to 0.09 source pixels, a quarter to
a third of a window pixel at 1080 lines. The softness one sees is the
beam's, across the lines, not the signal's.

**Evidence** (the class as in the emulation; `--crt-list` prints the
same table):

| Constant | Value | Class | Range | Source |
|---|---|---|---|---|
| gamma_tube | 2.4 | DOC | | ITU-R BT.1886 (2011) Annex 1: the reference EOTF of a CRT |
| gamma_out | 2.4 | CHOICE | 2.2-2.4 | the television decoding BT.1886; equal to gamma_tube, so a flat area keeps its value (2.2 for an sRGB monitor) |
| bandwidth_mhz | 12 | DATASHEET | | Wells-Gardner K7000 service manual (1987): video amplifier 12 MHz at -3 dB; the Gaussian shape of the response is a CHOICE |
| beam_sigma | 0.20 lines | CHOICE | 0.15-0.30 | spot at zero current. Gaussian form: Naiman & Makous 1992 (Proc. SPIE 1666); no width against brightness found for colour or arcade tubes; MAME crt-geom's spot 0.3 for comparison |
| beam_growth | 0.25 lines | CHOICE | 0.15-0.35 | spot grows with beam current (AAPM TG18, monochrome medical monitors); sigma 0.45 at white |
| mask_pitch_mm | 0.82 mm | DATASHEET | | K7000 service manual: stripe pitch |
| tube_width_mm | 365 mm | CHOICE | 340-390 | visible width of a 19 inch 4:3 tube (about 18 inch viewable), the picture filling it |
| mask_gap | 0.15 pitch | CHOICE | 0-0.3 | own drawing |
| mask_strength | auto | CHOICE | 0-1 | 0.15 below 5 window pixels per triad, 0.5 above (`mask_strength_fine`, `mask_strength_coarse`, `mask_fine_px`) |
| lowpass, beam, mask | on | | | stage switches |

The pitch on the screen: 365 / 0.82 = 445 triads along a scanline. At
1920x1080 with integer scaling that is 3.07 window pixels per triad
for R-Type (1365 pixels wide), 2.88 for Super Pang (1280), 2.63 for the
SNES and the NES (1170) and 1.94 for Ikari (864 pixels high, the
scanlines' direction); the tile is the pitch rounded, at least 3
texels (R, G, B), so at 1080 lines it is 3 for all of them: Ikari's
triads come out half again too coarse. At 3840x2160 the pitch is 4.5
(Ikari) to 6.5 pixels, the tile 5 or 6.

**1080p against 4K.** At 1080 lines the beam profile and the scanlines
work: 4 to 5 window pixels per line (Ikari 3 at integer scaling, 4 with
overscan). The mask does not: a triad of about 3 window pixels sits on
the television's own RGB subpixels, a strong mask gives colour fringes
and moire, so it is weak (0.15) and mostly a texture. At 4K, 6 to 7
pixels per triad draw the stripes as stripes and the coarse strength
0.5 applies; the research holds the mask believable from 4K on. The
beam simulator of the research (phosphor decay per refresh) needs 120
Hz and is not built; 50, 55 and 57 Hz on a 60 Hz television still
judder without VRR (section 4), the tube changes nothing there.

**Stages off.** With `lowpass=0` the scanline axis is the pass-through's
nearest neighbour (rounded to 1/256 pixel as in `copy.frag`), with
`beam=0` the line axis, with `mask=0` no mask; all three off give the
pass-through picture exactly (the power law and its inverse round back
to the same 8-bit values on the drivers tried; `play_crt_arcade` checks
it).

**Cost.** One pass, per window pixel 4 erf for the amplifier weights,
15 texel reads (5 lines x 3 pixels), 5 spot profiles per channel and one
mask read; no intermediate texture. `--gpu-timing on` measures it
(section 8), `tools/mamr_play/tests/measure_crt.sh MAMR_PLAY` runs the
three arcade sets with the tube off and on (1200 frames unpaced, vsync
off; headless through the offscreen driver at 1920x1080, `SCREEN=1`
fullscreen on the display). On the development machine (Mesa NVK on an
RTX 3060 in a virtual machine, offscreen, load average 6 to 11 from parallel
builds) the GPU time per frame, from the acquired swapchain image to
the finished frame, upload included, was 0.6 to 2.1 ms with the tube
and 0.5 to 1.6 ms without: Ikari 0.63 against 0.48, R-Type 2.11 against
1.56, Super Pang 0.79 against 1.04 (the noise of the busy host is
larger than the shader). The second machine at the television
(Quadro P620, NVIDIA 580.178, 1920x1080 at 60 Hz on DP-1, `SCREEN=1` with `DISPLAY=:0`, the
games on their artefacts there, 2026-10-27), GPU time per
frame, mean, tube off against on:

| Game | off | arcade | frame interval unpaced, off / on |
|---|---|---|---|
| Ikari Warriors | 0.63 ms | 1.20 ms | 1.30 / 1.91 ms |
| R-Type | 0.73 ms | 2.03 ms | 3.98 / 5.30 ms |
| Super Pang | 0.72 ms | 1.86 ms | 1.55 / 2.53 ms |

The largest GPU time, about 50 ms with and without the tube, is the
second frame after the fullscreen window opens; after the first 10
frames R-Type unpaced with the tube has a frame interval of 5.07 ms at
the median, 6.33 ms at the 99th percentile and 7.02 ms at most. Paced
as under ES-DE (600 frames, `--crt arcade`): Ikari in vsync mode 16.660
ms mean, R-Type (55.0176 Hz) and Super Pang (57.42 Hz) in timer mode
18.183 and 17.424 ms, after the first 10 frames no interval above 18.81
ms, no resync. The tube takes at most an eighth of the 16.7 ms of a
frame on the P620: 60 frames per second with a wide margin, no stage
needs switching off. Headless on that machine does not work: NVIDIA's
Vulkan headless surface cannot present ("This surface does not support
presenting"), so under the offscreen driver the GPU path falls back to
the renderer there; the measurement runs on the display. Should a
slower GPU not hold the frame rate, the stage switches take the mask
(`mask=0`) or the amplifier (`lowpass=0`) out; the beam is the stage
that makes the look.

**Open.** Ikari's triads at 1080
lines (the tile is at least 3 pixels, the pitch is 1.94); the pixel
rates of Ikari and Super Pang are CHOICE (MAME has no raw timing for
Ikari, and Super Pang's pixels per line are not known); the machine
interface could carry rotation and pixel rate (docs/machine-interface.md
is unchanged, the table is in the front end); the two PAL profiles
(SNES over RGB SCART, NES as composite with and without delay line) are
the next stages; no afterglow (the research's two time constants), no
glow, no curvature.
