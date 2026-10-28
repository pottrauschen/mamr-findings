# The machine interface

Phase S7 of the SNES path (docs/snes-architecture.md section 8) and the
first layer shared by every system MAMR runs: one C++ contract between a
game and whatever presents it. The SDL front end (`tools/mamr_play`,
docs/frontend.md), the headless tests and a later libretro adapter all
talk to a `jf::machine::Machine` and nothing else. The header is
`runtime/machine/machine.h`; this document is the rationale and the
rules an implementation keeps.

## 1. Principles

- **The game runs in console time.** Every machine counts its own master
  clock; `run_frame` advances it by exactly one frame of that clock. The
  host never asks for "as much as fits into 16 ms": it runs frames and
  decides on its side how to pace them (docs/frontend.md section 4).
- **The host presents, the machine produces.** Picture and sound of a
  frame are results of `run_frame`, read afterwards; the machine never
  touches a window, an audio device or a file.
- **Inputs are latched by the game.** The host sets the pad state before
  the frame; the game reads it where the hardware reads it (the
  auto-joypad read of the SNES, the input poll of the arcade program).
  There is no per-sample input timing in the interface.
- **Save states are explicit.** A state is a versioned list of named
  fields taken at a frame boundary, with the ROM identity, never an
  image of process memory or of a native stack.
- **Thin adapters later.** The calls map one to one onto the libretro
  API (section 8), so that adapter stays a table lookup and a few
  callbacks; it is not implemented yet.
- **Hardware and game are separate.** One runtime per system (the SNES
  runtime with its PPU, APU, timing and cartridge models; the arcade
  runtimes) and one front end; the recompiled game is a small loadable
  artefact, a shared library with the native code and a manifest, that
  the runtime loads over a versioned C ABI (section 10). Without an
  artefact the runtime interprets.

## 2. Description

`Machine::describe()` returns a `Description` that does not change after
`power()` (options may change it before):

| Field | Meaning |
|---|---|
| `name`, `system`, `id`, `region` | title; "snes", "nes" or "arcade"; a stable identifier for file names ("snes-<sha1>", "nes-<sha1>" of the iNES file, "ikari"); "ntsc", "pal" or "" |
| `width`, `height` | the largest picture the machine produces; a frame may be smaller (SNES: 512 x 239; a normal frame is 256 x 224) |
| `pixel_aspect` | shape of one pixel as displayed, width over height: 8:7 for the SNES on a 4:3 screen, 1:1 for Ikari Warriors (216 x 288 is already the 3:4 monitor), 8:9 for R-Type (384 x 256 on a 4:3 monitor) |
| `master_clock_hz` | the clock every time stamp of the machine counts, as a fraction (SNES NTSC 236250000/11, PAL 21281370/1, NES NTSC 236250000/11 with 12 per CPU cycle, Ikari 4 MHz sound CPU, R-Type 8 MHz main CPU) |
| `frame_clocks` | master clocks per frame, as a fraction; `frame_rate_hz()` divides the two (SNES NTSC 714732/2 clocks = 60.0988 Hz, PAL 425568 clocks = 50.0070 Hz, NES NTSC 714732/2 as well: 262 lines of 341 dots of 4 clocks, one dot less in every other frame while rendering; Ikari 60 Hz, R-Type 145408 clocks = 55.017 Hz) |
| `audio_rate_hz` | sample rate of `audio()` as a fraction (SNES: the DSP rate option, 32040 Hz by default; NES NTSC 236250000/5280 = 44744.3 Hz, the CPU clock / 40, since phase N4 (48000 Hz of silence in phase N3); Ikari 4 MHz / 72; R-Type 3579545 / 64) |
| `ports`, `port_desc` | controller ports read and, per port, which pad buttons the game uses for what, and what the sticks do |
| `system_buttons` | cabinet switches that belong to no pad: service credit, test |
| `has_sram`, `has_save_states` | what the save calls support |
| `options` | key, description with the accepted values, default |

## 3. Lifecycle

```text
factory open -> set_option* -> power -> [set_sram]
  -> (set_pad* / set_system_buttons, run_frame, frame, audio, sram_dirty)*
  -> reset / serialize / deserialize between frames
```

- A factory (`machine_open`) takes a ROM path or a machine name and
  returns a machine that has loaded its ROM but not started. Factories
  are registered by the program (`register_snes_machine_linked`,
  `register_ikari_machine`, `register_rtype_machine`); there is no
  static registration, so a program links exactly the machines it wants.
- `set_option` before `power`; options are strings (key, value) and
  listed in the description. Unknown keys and values fail with a message.
- `power` starts from the cold state. `reset` is the reset button: what
  the hardware's reset line does, SRAM kept. `Description::reset_kind`
  says which it is: `Line` for the consoles (their reset line keeps the
  RAM; section 7.1, 7.2), `ColdStart` for the arcade boards, which have
  no reset button (a cold start that keeps the battery memory, section
  7.2). The frame count goes on over a reset; a front end that wants a
  power cycle calls `power` and gives the save RAM back with `set_sram`
  (docs/frontend.md section 3, Shift+F1).
- `run_frame` is the only call that advances time. For the SNES a frame
  runs from the sampling point of the hash lines (the first instruction
  boundary at or after V = vdisp, H = 0; docs/snes-oracle-format.md) to
  the next one, so the picture is complete and the auto-joypad read of
  the field follows right after the frame boundary. For the arcade
  machines a frame is the frame their schedulers already use.

## 4. Outputs

- `frame()`: XRGB8888, row by row, with a pitch in pixels; valid until
  the next `run_frame`. The size may change per frame (SNES hi-res, PAL
  overscan).
- `audio()`: interleaved stereo int16 at `audio_rate_hz`, exactly as many
  frames as the sound hardware produced in the frame's master clocks.
  The count varies by one from frame to frame where the rates do not
  divide (the SNES DSP at 32040 Hz gives 640 or 641 frames per PAL
  field); nothing is padded or dropped. Resampling to the host device is
  the host's job (docs/frontend.md section 5).

## 5. Inputs

`PadState` is one fixed layout, the RetroPad order of libretro (bit 0 B,
Y, Select, Start, Up, Down, Left, Right, A, X, L, R, L2, R2, L3, R3) plus
four stick axes (left x, y, right x, y; -32767..32767). A machine maps
it to its own ports and says in `port_desc` what each button does, so a
front end can show or remap them without knowing the game. Pads set
with `set_pad` apply to every following frame until set again.

SNES: the twelve buttons go to the standard joypad's shift register in
JOY1 bit order (B = bit 15 ... R = bit 4). Port 2 is empty by default,
as in the oracle runs: an empty port reads 0 before and after the 16th
bit where a pad reads 1 after it, and games test that (Donkey Kong
Country every frame; docs/snes-hardware-spec.md section 2.6). The option
`port2=pad` plugs a second joypad in; the description then lists two
ports. The choice is configuration, set at `power()`, not part of the
save state. NES: the eight buttons of the controller go to its shift
register in report order (A, B, Select, Start, Up, Down, Left, Right);
RetroPad A and B are the controller's A and B. Controller 2 reads as not
connected (the board's choice, docs/nes-hardware-spec.md section 3.6).
Ikari Warriors:
d-pad or left stick walk, right stick aims through the rotary knob, L/R
turn it, B/R2 fire, A/L2 grenade, Select coin, Start start. R-Type:
d-pad or left stick, B/R2 fire, A force pod, Y/X buttons 3 and 4,
Select coin, Start start; port 2 drives the cocktail player bits.
Super Pang: d-pad or left stick, B/R2 fire, A button 2 (service mode
only), Select coin (one coin slot for both ports), Start start (port 1
player 1, port 2 player 2); the system buttons are the service credit
and the service mode switch.

## 6. Battery memory and save states

**SRAM** is a linear byte image (`sram()`, `sram_size()`, `set_sram()`),
the `.srm` convention: the bytes as the game addresses them, nothing
else. Super Pang has two battery-backed parts, so its image is the
8 KiB work RAM (E000-FFFF) followed by the 93C46's 64 words big-endian
(the layout of the set's EEPROM file); its settings and high scores live
in both. `sram_dirty()` reports and clears "changed since the last call";
the SNES adapter compares against a shadow copy once per frame. The
host writes the image atomically (temporary file, fsync, rename) when
it is dirty and at exit.

**Save states** (`serialize`, `deserialize`) are taken and restored only
between frames. The container (`machine.h`): the magic "MAMRSAVE", a
container format number, the system and the game id, the machine's
state version, then the machine's payload. A state loads only into the
same game and the same state version; a wrong system, id or version is
refused before any field is touched.

The payload is written through `StateArchive`
(`runtime/machine/state_archive.h`): one function per part names its
fields in a fixed order, the same function writes and reads; integers
little-endian at their own width, booleans one byte, enums as their
underlying type, memories as byte blocks, variable parts with a length
prefix. Parts are framed as tagged chunks ("CPU ", "TIME", "PPU ", ...)
with their length, so a reader notices a layout it does not know
instead of misreading it. No pointers, no padding, no host layout.

What the SNES state holds (`runtime/snes/snes_state.cpp`,
`SNES_STATE_VERSION`): the 65816 registers, the emulation bit, WAI/STP,
the pending interrupt and the master clock; the time skeleton with
every register ($4200-$421F), the field position, the NMI/IRQ latches
and hold windows, the auto-joypad state, the clock grid origin and the
position of every scheduled event; the eight DMA channels and the DMA
unit's flags; WRAM, WMADD, the open-bus value, MEMSEL; SRAM; the PPU
(VRAM, OAM, CGRAM, every register and latch, the output of the field,
the line pipeline's cursors); the S-SMP (SPC700 registers, APU RAM, the
I/O page, the timers, the clock relation, the queued port writes) and
the S-DSP (register file, voices, envelopes, echo, the step counter);
the system's own bookkeeping (the sampling window, the cycle grid, the
stall). For stage E the coupling state (DMA edge, refresh, ALU steps)
comes on top. The board's hooks, the ROM, the page table and the block
tables are wired by `power()` and are not state.

**The recompiler's continuation point.** States are taken at an
instruction boundary where no emitted block is in progress
(`System::run_to_sample` returns there). The dispatcher re-enters the
code from the state alone: PB:PC with the register widths M and X and
the emulation bit select the block or resume point
(`runtime/w65816_cpu.h`), `int_pending` and the WAI/STP flags decide
what runs first. Nothing of the native call stack is saved, which is
why a state from the native build loads into the interpreter build and
back (tests/machine, `snes_machine_zelda_native`).

**The NES** (`runtime/nes/nes_state.cpp`, `NES_STATE_VERSION` 2 since
phase N4, version 1 states refused with their version named; a PAL
machine (phase P, docs/nes-architecture.md section 11) writes version 3
(`NES_STATE_VERSION_REGION`): a first chunk `REGN` with the region (1
PAL) before the version 2 payload, while an NTSC machine keeps writing
version 2 byte for byte; a version 2 state reads as NTSC, and a state of
the other region is refused with both regions named; about
136 KB with Super Mario Bros. 3's 8 KiB of PRG RAM, 120 KB of it the
PPU's picture): the CPU with its continuation point
(A, X, Y, S, P, PC, the pending interrupt, the jam flag, the cycle
count), the board (RAM, CIRAM, the external and internal data buses, the
time line's next cycle start and end, the NMI edge and IRQ samples, the
joypad's last read and shift register, the strobe, OAM DMA), the PPU
(position, the odd-frame flag, every register, latch and delayed effect,
the background and sprite pipelines, OAM, secondary OAM, palette, the
picture), the APU (frame counter, length counters, DMC with its DMA
request; since version 2 the pulse, triangle and noise channels with
envelopes, sweeps, linear counter, timers and sequencers, and the
position of the native samples), the adapter's audio output stage
(chunk NAUD: FIR history and phase, the filter states;
docs/nes-audio-spec.md section 9) and the mapper (registers, the MMC3 IRQ counter and A12
filter, the MMC1 shift register and last write cycle, PRG RAM, CHR RAM,
cartridge VRAM; the memory sizes must be the cartridge's). The bank
state of the dispatcher's key lives in the mapper registers, so the
blocks are found again from the state alone; a state of a run on blocks
loads into the interpreter and back (`play_roundtrip_smb3`). Loading
keeps the saved controller state (the loading host's pad is set before
the next frame), so a state serialized again right after the load equals
the one loaded (`machine_state_smb3_game`).

**The arcade machines** keep their whole state in plain structures, so
their states list fields like the SNES one. The shared parts are in
`runtime/machine/chip_state.h`: a Z80 or V30 runner is its registers,
the cycle counter, the interrupt lines with the NMI latch and the
runner's interrupt shadow (`ei_shadow`, the V30's `no_interrupt` and its
REP continuation and prefetch state); the 8259 is its registers and
latches; a YM3526 or YM2151 is ymfm's own `save_restore` image of the
chip (registers, operators, envelopes, phases, the timers' run flags,
little-endian in ymfm's fixed order; MAME saves the same image) plus
the wrapper's clock, sample count and timer deadlines
(`Ym3526::save_state`, `Ym2151::save_state`; the YM2413 likewise, it has
no timers); the OKI MSM6295 is its four voices (ROM address, nibble
position and count, attenuation, ADPCM signal and step index), the
pending phrase command and its sample count; the 93C46 EEPROM is its
contents and its state machine (state, pins, lock, command, the bit,
command, address and shift registers, the end of a programming
operation). Samples a chip has made but the machine not yet taken are
saved with it. One local change to ymfm
(`opm_registers::save_restore`, marked in `third_party/ymfm/ymfm_opm.cpp`):
the YM2151 image also holds the LFO's noise waveform, a 256-entry table
the chip fills with LFSR bits while it runs (`clock_noise_and_lfo`).
Upstream ymfm and MAME leave it out, so a restored chip reads its
power-on zeros there; R-Type selects that waveform (register 0x1B = 3)
during play, and its audio after a load differed from the original
within one frame until the table was saved (found by
`machine_state_rtype_game`, section 9). The YM3526 has no such table.
ymfm's `save_restore` also marks every channel for re-evaluation at the
next sample, in the running chip as well; a run that saves a state
after every frame was checked to give the same hashes as one that saves
none (3000 frames of both games with the pad scripts of section 9). Fields that are only
valid while a block runs (`block_t`, `budget`, stop requests), the
wiring and the statistics are not state.

- Ikari Warriors (`games/ikari/ikari_play.cpp`, `IKARI_STATE_VERSION`
  1, about 19 KB): the frame counter, the shared RAM of CPU A and B,
  the sound RAM, the sound latch and status, the hard flags position,
  the write-only video registers, the inputs as last latched, the three
  Z80s, both YM3526, and the front-end mapping's rotary memory (knob
  position, held turn, aim steps). The picture is rendered from that
  state alone.
- R-Type (`games/rtype/rtype_play.cpp`, `RTYPE_STATE_VERSION` 2, about
  124 KB; version 1 lacked the LFO noise waveform): the frame and line event counters, work RAM, sprite RAM and
  the sprite buffer the DMA copied, both palettes and video RAMs, scroll
  and raster registers, port 0x02, the inputs, the V30 and the 8259;
  the sound board's RAM, latch, acknowledge and reset state, its Z80 and
  the YM2151. The renderer starts every frame at row 0 and holds nothing
  between frames. The option `ym_reset` is configuration, not state.
- Super Pang (`games/spang/spang_play.cpp`, `SPANG_STATE_VERSION` 1,
  about 23 KB): the frame counter and the end of the current VBLANK,
  work RAM, tile, attribute, sprite and palette RAM, the port registers
  (ROM bank 0x02, gfxctrl 0x00 with flip, OKI bank and palette bank,
  video bank 0x07), the IRQ source bit and line, the inputs as last
  latched, the sound mixing position (YM2413 samples mixed, the first
  OKI sample kept); the Z80, the EEPROM, the YM2413 and the OKI. The
  renderer draws from that state alone. The recompiled blocks are
  looked up by (bank, PC) from the state's bank register, so a state
  needs no block-related field.

A state loads into a freshly wired machine first and replaces the
running one only when every chunk was read exactly; a refused state
leaves the game as it was.

**Overclock.** A SNES state of a run with the option `overclock`
(docs/frontend.md section 2) names the factor in the container's game
id, "snes-<sha1>/overclock=2"; the container format, the payload and the
states of normal runs are unchanged. A run at another factor refuses it
with both factors in the message; file names keep using the plain id.

## 7. Implementations

| Machine | Files | Notes |
|---|---|---|
| SNES, stage S and E | `runtime/machine/snes_machine.{h,cpp}`, `runtime/snes/snes_state.{h,cpp}` | factory "snes" (.sfc/.smc); options stage, region, dsp_rate, smp_clock, ipl, blocks, sram_fill, port2, overclock (stage S, docs/frontend.md section 2); emitted blocks of a native build through `register_snes_machine_linked` (the manifest of `tools/snes_headless/snes_headless_blocks.h`) |
| Ikari Warriors | `games/ikari/ikari_play.{h,cpp}` | factory "ikari" (also its set folder, ikari.zip, ikari.mamr); the ROM set loaded at power-on, the code of the artefact ikari.mamrcart or the interpreter (section 10); option follow_walk; save states (section 6); also the program `ikari_sdl` (docs/frontend.md) |
| R-Type | `games/rtype/rtype_play.{h,cpp}` | factory "rtype", set and code as for Ikari (rtype.mamrcart); option ym_reset; save states; also the program `rtype_sdl` |
| Super Pang | `games/spang/spang_play.{h,cpp}` | factory "spang", set (decrypted at load time) and code as for Ikari (spang.mamrcart); save RAM (work RAM and EEPROM); save states; 384 x 240, pixel 5:6, 57.42 Hz (MAME's frame of 139,324.28 Z80 cycles), audio 55,556 Hz |
| NES (phases N3, N4) | `runtime/machine/nes_game.{h,cpp}`, `runtime/nes/nes_state.{h,cpp}`, `runtime/nes/nes_palette.{h,cpp}`, `runtime/nes/nes_audio_out.{h,cpp}` | factory "nes" (.nes, iNES and NES 2.0; the boards of runtime/nes); options stage (s, the line renderer where allowed, or e), blocks and region (auto: the cartridge database, then the header; ntsc; pal; phase P); emitted blocks of a native build (`register_nes_machine_linked`) or of a cartridge (`set_nes_blocks`); picture 256 x 240 through an RGB palette computed from the 2C02's documented NTSC signal levels (a presentation CHOICE, `nes_palette.h`); audio (phase N4) the APU's native samples through the output stage of docs/nes-audio-spec.md section 9, stereo int16 at CPU clock / 40; SRAM is the PRG RAM of boards with a battery |

Every machine's `reset()` is defined in 7.1 and 7.2, with the
provenance classes of the hardware specifications (DATASHEET, MEASURED,
TEST-ROM-HW, DOC, IMPL, INFERENCE, UNKNOWN, CHOICE; docs/snes-hardware-
spec.md, introduction).

### 7.1 The SNES reset button

`SnesMachine::reset()` presses the console's reset button between two
frames, in stage S (`System::reset_button`) and stage E
(`SystemExact::reset_button`) alike. The release time t is the present
master clock, the sampling point the frame ended at; how long the
button is held is not modelled (the counters stand at 0 while it is
held and start at the release, so one release time covers it). In this
order:

| Step | What | Class |
|---|---|---|
| `Board::reset(t)` | `Timing::reset(t)`: the PPU counters from V=0 H=0 of field 0 at t, interlace and overscan off, the clock grids (8-clock DMA counter, joypad grid) from t; NMITIMEN, WRIO, MEMSEL, RDNMI, TIMEUP, JOY1-4 and the auto-joypad state to their reset values; `Dma::reset` (MDMAEN, HDMAEN and the HDMA flags clear); WMADD 0 | counters DATASHEET + INFERENCE (S-PPU netlists) with MEASURED support (spla: the button pulls /RESET of both PPUs), hardware-spec 5.4; the register table DOC [FS "SNES I/O Map"] with DATASHEET support [RGALLAND], hardware-spec 2.8 |
| kept | HTIME/VTIME, the maths operands and results, the $43xx channel parameters, WRAM, SRAM | DATASHEET [RGALLAND] (no reset input) + DOC; WRAM and SRAM have no reset input (DRAM and the cartridge's SRAM) |
| `Ppu::reset_line(t)` | SETINI bits 0, 2, 6 and 7 cleared, force blank set, the field flip-flop 0, the pipeline at V=0 H=0 at t; VRAM, OAM, CGRAM and every other register and latch kept | DATASHEET + INFERENCE (hardware-spec 5.4); the rest of the register state is open there and kept (CHOICE) |
| `Smp::reset()` at the S-SMP's clock for t | CONTROL $B0, TEST $0A, the CPU-to-SMP port latches 0, the timers stopped, the DSP restarted at step 0, the SPC700's reset sequence into the IPL; ARAM kept | the reset sequence's shape MEASURED [SRG320 LA] (hardware-spec 5.5, three stack reads, no write, not modelled as bus cycles); the register values DOC (SNESdev wiki, docs/snes-audio-spec.md); the S-SMP's clock phase against the CPU after the release CHOICE (its resonator runs on; hardware-spec 5.4) |
| CPU reset sequence | 132 clocks, a dummy read of PB:PC, an internal cycle, three stack reads at S, S-1, S-2, the vector $FFFC; E = M = X = I = 1, D flag 0, D = DBR = PB = 0, S.h = 1, X.h = Y.h = 0; A, X.l, Y.l kept, S.l three lower | stack cycles and S.l MEASURED [SRG320 LA] + DATASHEET (WDC W65C816S 2.25); the 132 clocks IMPL (ares); A, X.l, Y.l kept CHOICE (the data sheet says "not initialized", UNKNOWN on the 5A22), hardware-spec 2.8, 5.5 |
| stage E only | the S-CPU's DMA and maths sequencing restart (a multiply or divide in progress stops; its registers keep what they hold) | DATASHEET + INFERENCE [RGALLAND] (~MRST), hardware-spec 5.4 |

The next frame ends at V = vdisp of the field that starts at t, so the
first frame after the button is shorter than a field by the lines from
the old field's V = vdisp to its end. The save state needs no new field
(`SNES_STATE_VERSION` unchanged): the reset leaves ordinary state
behind, which `machine_reset` checks (section 9). A CPU stopped by STP
runs again after the button. What no runner presses yet: the button in
`snes_headless` and in aresref (`--reset-at F[:HOLD]`, so that the
second half of a test ROM runs; ares resets HTIME/VTIME and the maths
registers, `like_ares`), and therefore the test ROMs that ask for it:
blargg's `timer_at_power_reset` (prints $000E at power-on and expects
$000E again after the button, the CPU/dot clock phase after an H-IRQ
sync; hardware-spec 5.4), PeterLemon's (krom) CPUMSC from SNES-CPUTest
(stops with STP and asks for the reset button to pass; ares and bsnes
fail it), undisbeliever's `reset-position-test.asm` (results not
published), and a pattern test of our own (values into HTIME/VTIME,
WRMPY/WRDIV, $43xx and the PPU write registers, press reset, read back)
for the open register list of hardware-spec 5.4.

### 7.2 The reset of the NES and the arcade boards

**NES** (`NesGame::reset`, `NesMachine::soft_reset`): the reset line of
the front-loading NES-001, which reaches the 2A03 and the 2C02.

| What | Class |
|---|---|
| CPU: seven cycles (two reads of PC, three stack reads with S decremented, the vector $FFFC); I set; A, X, Y kept; S three lower; a jammed CPU runs again | DOC [WIKI "CPU power up state"] (docs/nes-hardware-spec.md 4.4) |
| APU: the channel enables cleared (the length counters of pulse, noise and the DMC's bytes with them), the triangle's length counter kept, the frame IRQ flag cleared, $4017 written again with its last value 10 cycles before the first instruction, the DMC output level keeps bit 0, the triangle restarts at step 0 | DOC (wiki) + TEST-ROM-HW: blargg's apu_reset suite (the author's console expectations), 6 of 6 pass in MAMR (docs/nes-test-evidence.md) |
| PPU: PPUCTRL, PPUMASK, the write toggle, the scroll latch and the read buffer 0, the writes to $2000/$2001/$2005/$2006 ignored until the end of the first vertical blank where the board option says so; OAM, palette, CIRAM, CHR RAM, OAMADDR and PPUADDR kept | DOC [WIKI "PPU power up state"] (docs/nes-ppu-spec.md 12) |
| PPU position: the picture starts again at the top (the pre-render line's last dot, then line 0 of an even frame) | CHOICE: the NES-001 wires the reset button to the 2C02's reset input (the Famicom and the NES-101 do not); where the counters stand afterwards is not documented beyond "starts at the top" |
| kept | the 2 KiB RAM, the mapper registers (no reset input on MMC1/MMC3 as modelled), PRG RAM | DOC (wiki: RAM unchanged on reset) + TEST-ROM-HW (blargg cpu_reset/ram_after_reset, the author's expectation) |

**Arcade boards** (Ikari Warriors, R-Type, Super Pang): a JAMMA cabinet
has no reset button and the specifications document none on these
boards (docs/hardware-spec.md, docs/rtype-hardware-spec.md section 3: a
power-on RC on the sound board's reset net; docs/spang-hardware-spec.md:
no watchdog in MAME). An operator restarts the game by switching the
cabinet off and on, so `reset()` is a **cold start**: the machine is
built again exactly as `power()` builds it from the loaded set and the
artefact, and only the battery memory survives (Super Pang's work RAM
and EEPROM; Ikari Warriors and R-Type have none). Class: CHOICE (a cold
start, named so in the front end's message "reset (cold start)"). A
watchdog that would reset a board when the program stops kicking it is
not modelled on any of the three.

## 8. Mapping onto libretro (not implemented)

| libretro | here |
|---|---|
| `retro_get_system_av_info` | `Description`: geometry from width, height and pixel_aspect; `fps` = `frame_rate_hz()`; `sample_rate` = `audio_rate_hz` |
| `retro_load_game` | factory + `set_option` from the core options + `power` |
| `retro_run` | input poll into `set_pad` per port (RetroPad ids = PadButton bits), `run_frame`, `video_refresh(frame())`, `audio_sample_batch(audio())` |
| `retro_reset` | `reset` |
| `retro_get_memory_data/size(SAVE_RAM)` | `sram`, `sram_size` (the front end's .srm handling) |
| `retro_serialize_size/serialize/unserialize` | `serialize` into a buffer; the size is the last serialized size (constant per game and version) |
| `retro_set_controller_port_device` | ports are standard pads; nothing to do |

The frame-by-frame contract (one `retro_run` is one frame, audio as a
batch per frame, input polled before the frame) is why `run_frame`
produces exactly one frame's audio and picture and takes no host
timing.

## 9. Tests

`tests/machine` (ctest labels oracle-free and local):

- `snes_machine_gilyon_s`, `_e`: gilyon's cputest-full through the
  interface, 600 frames, the F lines of docs/snes-oracle-format.md
  identical to `snes_headless`, save state at frame 300 and the frames
  301..600 repeated exactly (F lines, picture, audio sample count and
  bytes), a second serialize after the load byte-identical, a corrupted
  header refused.
- `snes_machine_zelda_s`, `_e`: the same on the local Zelda ROM
  (`SNES_ZELDA_ROM`).
- `snes_machine_zelda_native`: with the emitted blocks of
  `MAMR_SNES_BLOCKS_CPP` linked, against the interpreter run of
  `snes_headless`; the state crosses block boundaries.

- `snes_machine_zelda_cartridge`: the interpreter build loads the
  Zelda artefact (`zelda.mamrcart`, section 10) through the cartridge
  ABI and runs on its blocks, with the same checks; the loader must
  refuse the ROM file itself.

- `play_roundtrip_*` (docs/frontend.md section 9): the front end
  against `machine_hash`, which runs any registered machine through this
  interface without a front end; per-frame picture and audio hashes
  (`frame_hash`, `audio_hash` in `machine.h`), the save state through
  its file, the save RAM through its .srm.
- `play_roundtrip_smb3_interp`, `play_roundtrip_smb3` (local ROM
  `NES_SMB3_ROM`): Super Mario Bros. 3, 1200 frames, the state of frame
  600 through its file; the second with the artefact `smb3.mamrcart`
  that tests/nes builds from the ROM, so the front end runs the native
  code and `machine_hash` the interpreter. Since phase N4 both programs
  get the pad script `tests/machine/smb3-game.pads` (`mamr_play
  --pads`), the game is played into World 1-1 and at least 600 different
  audio hashes are required, so the comparison covers the sound.
- `machine_reset_gilyon_s`, `_e` (oracle-free), `machine_reset_zelda_s`,
  `_e`, `machine_reset_smb3`, `machine_reset_ikari`, `_rtype`, `_spang`
  (local; `tests/machine/machine_reset.cpp`): a machine runs K frames
  and is reset, a second one starts cold. For the reset line (SNES,
  NES) the memories and registers the hardware keeps must be unchanged
  and the CPU, board, PPU and sound unit at their reset values (section
  7.1, 7.2); for a cold start (the arcade boards) the state after the
  reset must equal the cold machine's state after power-on (with the
  battery memory the reset kept) byte for byte, and the frames after it
  must be equal in picture and audio. For every machine the state taken
  right after the reset loads into a third machine that repeats the
  frames after the reset exactly. The reset line need not give the cold
  start's pictures (RAM, VRAM and the S-SMP's phase survive), but the
  games' start-up clears what they show: Zelda (reset after frame 700)
  shows the cold start's picture in all 600 frames after the button,
  stage S and E, and the cold start's audio in 313 of them (the S-SMP's
  phase and ARAM differ); gilyon's cputest (after frame 200) in all 300;
  Super Mario Bros. 3 (after frame 900, on the map) from the 13th frame
  on (`--pictures-from`). The arcade cold starts are equal in state,
  picture and audio, also in the middle of a game played with the pad
  scripts below (Ikari after frame 1800, R-Type 2050, Super Pang 2200).
- `machine_state_smb3_game` (phase N4): `machine_hash --state-check` at
  six points of the same played run (map with its tune, entering the
  level, in the level with jumps), as for the arcade games below.

The arcade adapters build without ROMs; their tests and artefacts need
the ROM sets at build time (`roms/ikari`, `roms/rtype`, `roms/spang`).
Besides their existing headless tests (which load the set from
`roms/<set>` and link the blocks) they get `play_roundtrip_ikari`,
`play_roundtrip_rtype` and `play_roundtrip_spang` (1200 frames, the
state of frame 600 through its file; Super Pang's save RAM through its
.srm; the front end on the game artefact, `machine_hash` in the
interpreter, so native code and interpreter agree frame by frame), the
tests of the artefacts (section 10):

- `arcade_no_rom_data_<set>` (`cart_scan`): no aligned 64-byte window
  of a file or region of the set in the artefact file.
- `arcade_needed_<set>` (`check_needed.py`, ELF only): the artefact's
  NEEDED entries are libc.so.6 at most (Ikari and Super Pang need none,
  R-Type libc since its V30 blocks take the interpreter through hooks).
- `arcade_native_<set>` (`check_arcade.py native`): `machine_hash` with
  the artefact (`--expect-native`: every unit in a block) against
  `machine_hash` without one (`--expect-interpreter`), over the game
  played by the pad script below, identical picture and audio hashes in
  every frame.
- `arcade_sets_<set>` (`check_arcade.py sets`): 300 frames from the set
  folder, from a zip archive of it (deflated and stored entries, one in a
  folder inside), from the ES-DE placeholder next to the archive and
  from a copy with every file renamed (found by SHA-1), all identical.
- `arcade_errors` (`check_arcade.py errors`, Ikari): the messages for a
  missing set, a missing file, a file of another SHA-1 and of another
  size, a file missing in an archive, an artefact of ABI version 1 and
  one of another set identity (`fake_cartridge.cpp`), and in the front
  end an artefact of another game (refused), no artefact (the
  interpreter runs), the artefact found by set name in the cartridge
  folder with the set found below `--rom-dir` (the ES-DE command), no
  set (refused).

and the save-state tests, on the artefact (`--expect-native`):

- `machine_state_ikari`, `machine_state_rtype`, `machine_state_spang`
  (`machine_hash --state-check`): 3000 frames of attract mode with
  sound, the state after frame 1777 loaded into a second machine,
  serialized again to the same bytes, frames 1778..3000 repeated
  exactly in picture and audio; a state with a damaged header and one
  cut short by a byte are refused, and the refused load leaves the
  first machine's state byte for byte as it was.
- `machine_state_ikari_game`, `machine_state_rtype_game`,
  `machine_state_spang_game`: the same checks in the middle of a game
  played with input. `machine_hash
  --pads FILE` sets the pads through `set_pad` before every frame from a
  pad script (`tests/machine/ikari-game.pads`, `rtype-game.pads`; one
  line per change: frame, port, buttons by name with an optional pulse
  period such as `b:4`, optional stick axes; format in
  `runtime/machine/pad_script.h`, read by `machine_hash` and, since phase
  N4, by `mamr_play --pads`; `spang-game.pads`). The pad of a frame depends on its
  number alone, so the machine loaded from a state gets the same input
  as the original. `--state-check` takes several points and checks each
  against the one run. Ikari Warriors: coin, start, walking up the map
  with fire, grenades, the right stick aiming and L/R held; 2600
  frames, states after frames 1250 (first scroll, enemy squads, the
  opening tune), 1382 (knob steps of an aim change in progress), 1463
  (held turn between two knob steps), 1545 (a life lost), 1800 (second
  scroll) and 2300. R-Type: coin, start, moving and firing through
  stage 1, the wave cannon charged, the force pod button; 3000 frames,
  states after frames 1130 (fire held, beam charging), 1420 (enemy
  waves), 1650 (ship lost), 2050 (after the restart) and 2600. The
  scenes were checked in the pictures of the runs; the default DIP
  switches stay, so lives are lost and the R-Type game ends at about
  frame 2900. Super Pang: the input of the oracle kit's coin/start route
  (so the game is the one checked against MAME), panic mode, walking and
  firing; 3000 frames, states after frames 1000 (the game started),
  1170 (a shot under way), 1700 and 2200 (balls split), 2480 (the player
  hit) and 2700 (game over). Each point prints the loudest sample of the second before
  it (sound active at every point). A state of R-Type taken anywhere
  before frame 1535 failed here in the audio of frame 1535 until the
  YM2151 image held the LFO noise waveform (section 6).

## 10. Game artefacts: the cartridge ABI

The portable form of a recompiled game is the C++ the recompiler
emitted, compiled natively for the host; there is no bytecode and no
JIT. A game artefact ("cartridge", `<name>.mamrcart`) is a shared
library that holds that code and a manifest, and nothing of the
hardware and nothing of the ROM: the ROM (for an arcade game the ROM
set) stays with the user and is loaded and checked by the runtime when
the game starts. The header is `runtime/machine/cartridge_abi.h` (plain
C). Three systems stand behind it: the SNES, the NES (phase N3) and the
arcade boards (Ikari Warriors, R-Type, Super Pang).

**Entry.** The library exports one symbol, `mamr_cartridge`, a function
without arguments that returns a pointer to its `MamrCartridgeManifest`;
nothing else is exported (the artefact builds with hidden visibility,
the arcade artefacts on ELF also with the version script
`runtime/machine/cartridge_exports.map`, which hides what the C++
library headers instantiate). The artefact depends on no runtime
symbol: the emitted code calls the bus only through the function
pointers it is handed (`W65816Bus`, `M65Bus`, `Bus`, `V30Bus`) and
touches only the state it is handed. The Zelda artefact has one
undefined symbol, the stack protector of libc; the Ikari and Super Pang
artefacts have none. The V30 blocks of R-Type call two routines of the
interpreter (`v30_interrupt`, the interrupt entry, and `v30_trap_after`,
the single-step trap after POP PSW / RETI, runtime/v30_ops.h). Until
2026-10-27 they were compiled into the R-Type artefact from
recompiler/v30_exec.cpp and v30_decode.cpp, which brought the C++
library (libstdc++, libgcc_s, libm) in. Since then the artefact holds
two trampolines in their place (runtime/v30_hooks.cpp) that call through
a table of function pointers in its manifest, which the runtime fills
with its own routines when it takes the blocks (kind
`MAMR_CODE_V30_BLOCKS_HOOKED`, below); the R-Type artefact then needs
libc only (`ldd`: libc and the loader; one undefined symbol, the stack
protector, like Zelda). The arcade artefacts are linked with
`--as-needed` (`mamr_cartridge_exports`, runtime/machine/machine.cmake),
so they name only the libraries they use with any compiler: Clang's
driver adds the C++ library to every link and GCC on Ubuntu passes
`--as-needed` by default (test `arcade_needed_<set>`).

**Manifest** (`MamrCartridgeManifest`):

| Field | Meaning |
|---|---|
| `abi_version` | `MAMR_CARTRIDGE_ABI_VERSION`, 2 |
| `struct_size` | `sizeof` of the writer's struct; a reader refuses another size |
| `name`, `system`, `region` | title, "snes", "nes" or "arcade", "pal"/"ntsc"/"" |
| `rom_sha1`, `rom_size` | the ROM the code was translated from; the runtime binds the user's ROM only when its SHA-1 is this one. For an arcade artefact the identity of the ROM set (`MamrRomSet::sha1`, below) and the bytes of all its files |
| `section_count`, `sections` | code sections (`MamrCodeSection`: kind, the runtime's mapping id, table, count), the kinds in the table below; a runtime skips kinds it does not know |
| `generator` | the tool that wrote it (informative) |
| `frame_width`, `frame_height` | 0: the system's picture; for systems whose geometry is per game |
| `rom_set` | version 2: the ROM set description of an arcade artefact (`MamrRomSet`), NULL for a console |

Code kinds:

| Kind | Table | Keyed |
|---|---|---|
| `MAMR_CODE_W65816_BLOCKS` (1) | `jf::W65BlockInfo[]` (runtime/w65816_block.h: block start, decode context, function, resume points) | in the static ROM map, mapping 0 |
| `MAMR_CODE_W65816_WRAM_BLOCKS` (2) | reserved (section 11) | |
| `MAMR_CODE_M6502_BLOCKS` (3) | `jf::M65BlockInfo[]` (runtime/m6502_block.h) | (8 KiB PRG bank of the block's window, PC) as docs/nes-architecture.md section 3, mapping 0 |
| `MAMR_CODE_Z80_BLOCKS` (4) | `JfEmittedBlock[]` (runtime/emit_manifest.h: name, start, end, function, code bytes, instruction addresses) | start address in the CPU's flat map |
| `MAMR_CODE_Z80_KEYED_BLOCKS` (5) | `JfKeyedBlock[]` (runtime/emit_manifest.h) | (bank, PC) of a banked Z80, `z80_bank_key` of runtime/z80_cpu.h |
| `MAMR_CODE_V30_BLOCKS` (6) | `JfV30Block[]` (runtime/v30_manifest.h); the artefact carries `v30_interrupt` and `v30_trap_after` itself | physical address |
| `MAMR_CODE_V30_BLOCKS_HOOKED` (7) | one `MamrHookedBlocks`: `blocks` the `JfV30Block[count]` of kind 6, `hooks` a writable table of `hook_count` function pointers in the artefact, which the runtime fills before the first block runs (`MAMR_V30_HOOK_INTERRUPT`, `MAMR_V30_HOOK_TRAP_AFTER`) | physical address |
| `MAMR_CODE_V30_REP_CONT` (8) | none (table NULL, count 0): a mark that the V30 blocks of the same mapping (kind 6 or 7) continue a REP without its 2 clocks when the runtime marks the continuation (`V30_REP_CONT_FREE`, below) | the mapping of the blocks it marks |

Kind 7 was added within ABI version 2, as the header allows for new
kinds: romtool writes it for every V30 since 2026-10-27, and the runtime
(`games/rtype/rtype_generated.h`, `main_blocks`) takes kind 6 or 7. An
artefact of kind 6 (made before that change) loads and runs as
before; the hooks are optional for the runtime, not for the artefact. A
runtime from before 2026-10-27 does not know kind 7 and skips it, so with
a new R-Type artefact it runs the V30 in the interpreter and the sound
Z80 on its blocks (checked: 300 frames, exit 0, the same hash lines);
the native V30 needs the runtime of this change. The version stays 2:
nothing an older reader knows changed. Programs that link the blocks
statically (`rtype_headless`, the tests) fill the table too and call the
interpreter's routines directly, since only the artefact compiles the
trampolines.

Kind 8 was added within ABI version 2 in the same change as kind 7, with
its own meaning: it is a property of the emitted code, not of how the
blocks reach the interpreter. A REP the runner split at one of its own
run targets (R-Type's line events, the frame end) is continued in the
next run (`V30State::rep_params` set, IP on the prefix). On the chip and
in mameref the continuation does not charge the REP's 2 clocks again; in
MAME 0.285 it does (docs/arcade-oracles.md findings F7 and E7). The game
build of R-Type runs without the second charge, its stage M in mode
stock with it (`V30Cpu::rep_cont_charge`). Since the choice is made at
run time, the runner tells the block: just before it calls the block of
such a continuation without the charge it sets bit 16 of `rep_params`
(`V30_REP_CONT_FREE`, runtime/v30_context.h); the block reads and clears
the bit as its first step, before the instruction hook, and passes
`charge = false` to `v30_rep`. The bit is never part of a state (save
states, hash lines and hooks see `rep_params` as before), and the layout
of `V30State` does not change. romtool writes the mark next to every V30
block table since 2026-10-27. Older artefacts:

- An artefact without the mark (an older kind 6 artefact, or kind 7 made
  before the mark) has blocks that ignore the bit and would charge the 2
  clocks again. The runtime never sets the bit for them
  (`V30Cpu::blocks_cont_free` false): it runs these continuations in its
  interpreter, with the same result, and counts them as interpreted
  units. Test `arcade_older_rtype` (with `MAMR_RTYPE_OLDER_CARTRIDGE`, a
  kind 6 artefact from before 2026-10-27): the hash lines of 3000 frames with the pad script
  equal those of the current artefact, and the older one reports
  interpreted units (35,831 there).
- A runtime that does not know kind 8 (one from before 2026-10-27) skips the
  mark and never sets the bit; the new blocks then charge the 2 clocks
  again, as that runtime's interpreter does (MAME 0.285), so blocks and
  interpreter stay equal there.

The version stays 2: no layout changed, and the helpers' semantics
change only behind the bit that only a runtime knowing kind 8 sets.

For the arcade kinds `mapping` is the position of the CPU's `[[cpu]]`
entry in the game file (`games/<set>/<set>.toml`), from 0: Ikari Warriors
has its main CPU under 0, the sub CPU under 1 and the sound CPU under 2;
R-Type the V30 under 0 and the sound Z80 under 1; Super Pang its one
Kabuki Z80 under 0. The `bytes` member of the Z80 and V30 tables is NULL
in an artefact: the code bytes are ROM data; the runtime does not need
them, and the differential tests take them from the loaded set.

**The ROM set description** (`MamrRomSet`, version 2). MAME's ROM_START
table of one set, written by romtool from the game file (never ROM
data): the files with name, size, CRC-32 (0 where the game file gives
none) and SHA-1, the regions the board uses (`MamrRomRegion`: name,
size, fill byte, loads of `length` bytes from `file_offset` of a file
to `offset`, `offset + stride`, ... of the region), and for a Kabuki CPU
the decryption (`MamrKabuki`: the raw region, the fixed part and the
bank layout, the keys `swap_key1`, `swap_key2`, `addr_key`, `xor_key`,
after MAME 0.285 capcom/kabuki.cpp and mitchell.cpp, BSD-3-Clause,
third_party/mame/LICENSE). A plain Z80 `[[cpu]]` becomes a region of
64 KiB with the file's first `mapped_end` bytes, a V30 `[[cpu]]` the
1 MiB image with its 16-bit lanes and mirrors (a mirror becomes loads of
the same files at the mirrored offset), a banked Z80 its raw region plus
the Kabuki entry, every `[[region]]` a region. `sha1` is the set's
identity: the SHA-1 of the lines `<sha1> <size>\n` of the files in
order, so it changes with any file and with nothing else. Excerpt of the
Ikari manifest (`generated/ikari/ikari_cartridge.cpp` and
`ikari_romset.cpp`, as romtool writes them):

```
static const MamrRomFile files[] = {
    {"1.4p", 0x10000, 0x52A8B2DD, "a896387d68ed9a55c313bdb81acdf8d68b7a1264"},
    {"2.8p", 0x10000, 0x45364D55, "323b998f782a4681ceb18016c5fb0fa1d6361aac"},
    ...                                        (20 files)
};
static const MamrRomLoad loads_0[] = {{0, 0x0, 0xC000, 0x0, 1}};   (maincpu)
static const MamrRomRegion regions[] = {{"maincpu", 0x10000, 0x00, 1, loads_0}, ... (8 regions)};
const MamrRomSet ikari_rom_set = {"ikari", "c6b73b3cd45b135f2ad250150e24733a52b7879f",
                                  20, files, 8, regions, 0, nullptr};

static const MamrCodeSection sections[] = {
    {MAMR_CODE_Z80_BLOCKS, 0, ikari_maincpu_blocks, 1687},
    {MAMR_CODE_Z80_BLOCKS, 1, ikari_sub_blocks, 214},
    {MAMR_CODE_Z80_BLOCKS, 2, ikari_audiocpu_blocks, 149},
};
static const MamrCartridgeManifest manifest = {
    MAMR_CARTRIDGE_ABI_VERSION, sizeof(MamrCartridgeManifest),
    "Ikari Warriors", "arcade", "", "c6b73b3cd45b135f2ad250150e24733a52b7879f", 642048,
    3, sections, "romtool", 0, 0, &ikari_rom_set};
```

The Super Pang description carries the Kabuki entry
`{0, 0x0, 0x8000, 0x10000, 16, 0x4000, 0x8000, 0x45670123, 0x45670123,
0x5852, 0x43}` (region maincpu, fixed part, 16 banks of 16 KiB at the
window 0x8000, keys); the keys live in the game file and in every
description made from it, in the runtime as in the artefact.

**What the version covers.** The struct and the entry symbol, the ROM
set description, and per code kind the layout of the tables and of the
state and bus structures the code functions take (`W65BlockInfo`,
`W65ResumePoint`, `W65816State`, `W65816Bus`; `M65BlockInfo`,
`M6502State`, `M65Bus`; `JfEmittedBlock`, `JfKeyedBlock`, `Z80State`,
`Bus`; `JfV30Block`, `V30State`, `V30Bus`) together with the semantics of
the inline helpers the code was compiled with (`w65b_*`, `m65b_*`,
runtime/z80_ops.h, runtime/v30_ops.h). A change to any of them bumps the
version; a runtime refuses an artefact of another version or of another
struct size before it touches a table, and skips sections of a kind it
does not know. A block table for another mapping id or for WRAM code
comes as a new section kind, not as a layout change. Version 2 added
`rom_set` and the arcade kinds; artefacts of version 1 (the SNES and NES
artefacts built before) are refused with "cartridge ABI version 1, this
runtime speaks 2" and are rebuilt from their ROM.

Two changes within version 2 touch what the version covers without a
bump, because nothing an existing artefact relies on changed:

- NES PAL (phase P, docs/nes-architecture.md section 11) appended
  `M65Bus::stall_sync_only` (the RP2A07's DMA halts the CPU only in the
  SYNC cycle) and changed `m65b_stall` (no stall before a non-fetch read
  when the flag is set) and `m65b_fetch` (it calls the stall hook itself,
  then reads). The field is appended, so older blocks never read it; with
  the flag clear (every NTSC run) the helpers behave as before, and the
  artefact of Super Mario Bros. 3 USA built before the change gives
  byte-identical hash lines on the new runtime (3000 frames with input, 0 misses). Older NES
  blocks do not know the flag: run on a PAL console (a PAL release, or
  `region` forced to pal) they would stall the CPU before every read. The
  NES artefacts that existed before phase P are NTSC releases only;
  rebuild an artefact before running it as PAL.
- The V30 REP continuation of code kind 8 (above): a mark section, not a
  layout change.

The manifest's `region` of an NES artefact is the console the runtime
resolves for the ROM (nes_recomp uses `nes_cart_region`: the cartridge
database before the header), so Super Mario Bros. 3 Europe, whose header
says NTSC, is "pal".

**Loader** (`runtime/machine/cartridge_loader.h`): `Cartridge::open`
loads the library (`dlopen` with `RTLD_NOW | RTLD_LOCAL`, `LoadLibrary`
on Windows), resolves the entry, calls it, checks version, size, code
kind, system and hash length, for an arcade artefact the ROM set
description (`rom_set_valid`: indices, bounds, hash lengths, and that its
identity is the hash of its files and the manifest's `rom_sha1`), and
keeps the library loaded as long as the `Cartridge` lives, because the
tables point into it. The SNES runtime takes the table through
`set_snes_blocks` and registers it in the dispatcher at `power()` only
when the SHA-1 is the ROM's; `SnesMachine::blocks_active()` says whether
it did. The front end runs `mamr_play --cartridge zelda.mamrcart
"Zelda.sfc"` and refuses a ROM the artefact was not made from;
`test_snes_machine --cartridge` does the same in the tests.

**The arcade runtime: the set at run time.** The arcade machines
(`games/<set>/<set>_play.cpp`) are built without ROMs: the ROM set
description comes from the game file (`romtool <set>.toml --set-source`,
compiled into the machine), the ROM data from the user when the machine
powers on (`runtime/machine/rom_set.h`):

- *Where.* The factory takes the set name (`ikari`), a folder of the set
  (`.../roms/ikari`), its archive (`.../ikari.zip`) or the ES-DE
  placeholder (`.../ikari.mamr`, whose folder is searched first). For a
  bare name the set is looked for, in order, in the folders of the
  search path, as a folder `<set>/` or an archive `<set>.zip`: the
  front end's `--rom-dir`, then `$XDG_DATA_HOME/mamr/roms` (default
  `~/.local/share/mamr/roms`; `%APPDATA%\mamr\roms` on Windows), then
  `roms/` below the working folder. The first place that has the set is
  taken.
- *Which file.* Every file of the description by its MAME name (any
  case, folders inside an archive ignored) when its size and SHA-1
  match, otherwise any file of the same size and SHA-1 under another
  name, as romtool does (the old Ikari names `1.rom` ... are found this
  way). SHA-1 decides; the CRC-32 is not trusted on its own.
- *Refusal.* A missing file or one of another size or SHA-1 refuses the
  set; the message names every such file with its expected size and
  SHA-1, `power()` fails with it and the front end exits with 1:

  ```
  ROM set ikari not found: no folder ikari/ and no ikari.zip in <dir>, ...
  ROM set ikari in <dir>/ikari: 1 of 20 files missing or wrong
    1.4p: missing (size 0x10000, SHA-1 a896387d68ed9a55c313bdb81acdf8d68b7a1264; looked by name and by SHA-1)
  ROM set ikari in <dir>/ikari: 1 of 20 files missing or wrong
    1.4p: SHA-1 838e3f41..., expected a896387d68ed9a55c313bdb81acdf8d68b7a1264 (another revision or a bad dump)
    1.4p: 100 bytes, expected size 0x10000, SHA-1 a896387d68ed9a55c313bdb81acdf8d68b7a1264
  ```
- *Regions.* The regions are built from the files as the description
  says; a Kabuki entry decrypts its region into the views `<name>_op`
  and `<name>_data` (the fixed part at its own Z80 addresses, every bank
  as if it sat in the window; tools/romtool/kabuki.h, the same code
  romtool and the oracle kit's views are checked with). The machine
  takes pointers into these images, which live as long as the machine.
- *Code.* The host hands the manifest of a loaded artefact to the
  machines before `power()` (`set_arcade_cartridge`,
  `runtime/machine/arcade_code.h`); a machine takes it only when its
  `rom_set` names the machine's set, and refuses it when the identity
  differs ("the game artefact was made from another ikari set (identity
  ..., this runtime's set is ...): rebuild it from this set"). Without
  an artefact every CPU runs in the interpreter: the same game, slower
  (the interpreter fallback of section 11 item 1, here for the whole
  program). `Machine::code_counters` reports the units run in blocks and
  the ROM instructions the interpreter took (Super Pang's code in RAM is
  interpreted by design and not counted).
- *Without a file system library* (the original Xbox,
  docs/xbox-port.md) `rom_set_load_named` reads every file by its MAME
  name through a callback, with the same checks and messages; the lookup
  in folders and archives is `runtime/machine/rom_set_find.cpp`, the
  rest `rom_set.cpp`.

**Zip archives: read directly.** MAME sets come as `<set>.zip`, so the
runtime reads them in place (decision 2026-10-26): `runtime/machine/
zip_reader.{h,cpp}`, a reader of the central directory with an own
inflater after RFC 1951 (stored, fixed and dynamic Huffman blocks), each
entry checked against its CRC-32, no new dependency. Neither SDL 3 nor
the repository had one (SDL reads no archives; the builder kit unpacks
with Windows' tar.exe). Refused with a message: encrypted entries,
methods other than stored and deflate, ZIP64, archives split over
several files. A merged or non-merged MAME set works as long as the
files of the set are in it; a split clone set that keeps files in its
parent's archive does not (the three sets are parent sets).

**Producing one.** `snes_recomp` writes the code, the manifest and the
entry into its output file (under `generated/`); the build
makes three things from that one file: the static native programs
(`snes_headless_native`, `mamr_play_native`), the static test
(`test_snes_machine_native`) and the artefact `mamr_cartridge`
(`<name>.mamrcart`, name from `MAMR_SNES_CARTRIDGE_NAME`, default the
file stem without `_blocks`). The static programs are the same code
linked in, so the artefact adds no second code path: the dispatcher and
the blocks are identical, only the loading differs (verified by
`snes_machine_zelda_native` and `snes_machine_zelda_cartridge` against
the same headless run). `snes_headless --cartridge FILE` runs any SNES
artefact in the interpreter build, which is how the artefacts of
docs/snes-ram-code.md are gated. For the arcade games `romtool <set>.toml
roms/<set> --emit generated/<set>` writes one block source per CPU
(no ROM image, no data region, no code bytes in the tables),
`<set>_romset.cpp` (the description), `<set>_cartridge.cpp` (the
manifest, `<set>_cartridge()`) and `<set>_entry.cpp` (the entry,
artefact only). The build compiles the blocks and the manifest once
(object library `<set>_code`) into the static library `<set>_blocks`
of the headless programs and tests and into the artefact
`<set>_cartridge`, `$BUILD/cartridges/<set>.mamrcart`; only with the
set present at build time (`roms/<set>`). On Windows the builder kit
(tools/builder) does the same on the user's machine and installs the
artefact into mamr_play's cartridge folder.

**No ROM data in an artefact** (ctest `arcade_no_rom_data_<set>`,
`tests/machine/cart_scan.cpp`). The test loads the set the artefact's
manifest describes and searches the artefact file at every byte offset
for the aligned 64-byte windows (offsets 0, 64, 128, ...) of every file
and of every region the runtime builds (program images, Kabuki views,
graphics, samples); a window counts when it has at least four different
byte values (fill and blank graphics would match anything). Any
contiguous copy of 127 bytes or more of a file or region contains a
whole aligned window and is found unless all of it is of that low
variety. Operands the emitter folds into the native code of a block (a
constant, an address, a table target) are no such copy and are allowed:
the criterion is a contiguous 64-byte stretch. A self-check plants one
window into a copy of the artefact and must find it. Result
(2026-10-26): Ikari 16094 windows counted, R-Type 31417, Super Pang
41519, 0 hits in each artefact; the static libraries of the build before
(`libikari_blocks.a`, `librtype_blocks.a`, `libspang_rom.a` with the
compiled-in arrays) give 19746, 34628 and 35960 hits.

**The NES (phase N3).** The second system behind the ABI, with the code
kind `MAMR_CODE_M6502_BLOCKS`, manifest system "nes", `rom_sha1` the
SHA-1 of the whole iNES file and `rom_size` its length; the code
functions take `jf::M6502State` and `jf::M65Bus` (runtime/m6502_context.h,
runtime/m6502_bus.h) and the inline helpers `m65b_*` of
runtime/m6502_block.h, which the version covers as for the 65816. A new
kind needs no version bump (section above). `nes_recomp` writes the code
and the manifest; unlike the SNES file the entry symbol is compiled only
in the artefact build (`MAMR_CARTRIDGE_BUILD`), so one native program may
link the blocks of both systems. Artefacts come from three places: the
build of `MAMR_NES_BLOCKS_CPP` (`mamr_nes_cartridge`, `<name>.mamrcart`,
with `nes_headless_native`), the local ROMs in tests/nes (`smb3`,
`accuracycoin`, `nestest`, from their seed lists), and
`tools/nes_recomp/nes_rounds.py` (rounds of recomp, compile and miss
log for any ROM). The NES runtime takes the table through `set_nes_blocks`
and uses it at `power()` only for the ROM it was made from
(`NesGame::blocks_active()`); `mamr_play --cartridge FILE` and
`--cartridge auto` (the cartridge directory, by system and SHA-1) work for
both systems, and `nes_headless --cartridge FILE` and the nestest test
run any NES artefact. The Super Mario Bros. 3 artefact has one undefined
symbol, the stack protector of libc, and exports only `mamr_cartridge`.

**Not in this step.** A signature or checksum of the artefact itself; a
manifest file next to the library for launchers that do not load code
(the entry can be read by a small tool without running any block); the
libretro adapter, which would load the artefact the same way; clone sets
whose files live in the parent's archive; reading a set from 7z or
other archives.

## 11. Contract requirements from the ROM survey

docs/snes-rom-survey.md (22 ROMs through the loader, aresref, the
block discovery and the tracer) derives five requirements for the
cartridge contract and the runtime. Where each stands:

1. **Block discovery from the miss log is part of the artefact build.**
   The vectors alone find 0 to 452 of the 2000 to 14000 blocks a game
   has; the table of an artefact grows from trace runs. Implemented:
   the runtime's interpreter fallback logs every dispatch miss
   (`W65816Cpu::miss_log`), `mamr_play --miss-log FILE` and
   `snes_headless --miss-log` write it as seed text, `snes_recomp
   --seeds` turns it into the next artefact's table; the Zelda artefact
   was built from 12000 frames of both releases this way (8429 blocks,
   0 misses over 600 frames). Open: the loop is manual (no build target
   that runs, collects and rebuilds), and a table cannot grow inside an
   artefact (a new artefact replaces the old; an artefact keeps no
   per-user state).
2. **Code in WRAM and in the low-RAM mirror, with page generations.**
   Secret of Mana runs 1786 seed blocks and its NMI/IRQ handlers from
   WRAM, Chrono Trigger 212, Final Fantasy III 281. Open: the runtime's
   dispatcher keys blocks by PB:PC in one static mapping only
   (docs/snes-architecture.md section 3, "code in WRAM"); the ABI
   reserves `MAMR_CODE_W65816_WRAM_BLOCKS` for tables keyed by the
   content of the page the code was translated from, which the runtime
   would bind to a WRAM page while the page holds that content and
   drop at the first write to it (a generation counter per page). No
   such table is produced or consumed yet; the games above run in the
   interpreter for that code. Since 2026-10-27 the three have artefacts
   of their ROM code (`ct`, `ff3`, `som`, built from miss logs) whose
   gates require no miss in ROM and print the interpreted share; the
   measurement (`snes_headless --ram-stats`), the shares per part of the
   game and the decision to keep RAM code in the interpreter for
   version 1 are in docs/snes-ram-code.md.
3. **Board and region per artefact by ROM hash.** Implemented: the
   manifest names `rom_sha1`, `rom_size` and `region`; the runtime
   binds the table only when the user's ROM has that hash
   (`SnesMachine::blocks_active`, `mamr_play` exits with 1 otherwise),
   and takes board and region from its own cartridge database by that
   hash (`runtime/snes/snes_cart`, docs/snes-cartridge-db.md), never
   from the artefact.
4. **The save state holds the dispatcher's continuation point, no host
   pointers.** Implemented: section 6; the state carries PB:PC, M, X,
   E, the pending interrupt and WAI/STP, which select the block or
   resume point at the next frame, and a state from the artefact build
   loads into the interpreter build and back (`snes_machine_zelda_native`,
   `snes_machine_zelda_cartridge`).
5. **Interrupt entries and vectors belong to the runtime.** Implemented:
   the runner takes NMI, IRQ and the reset sequence in the interpreter
   (`runtime/w65816_cpu`), reads the vectors through the bus, and
   enters a block only at an instruction boundary with no interrupt
   pending; an artefact holds no entry code. A game whose vectors point
   into WRAM (Secret of Mana) is covered by this rule and by item 2 for
   the handler code itself.

ABI version 1 covered items 3 to 5 and the ROM-code section of item 1;
item 2 is a new section kind (additive), the page generations are
runtime state and not part of the ABI. Version 2 (section 10) adds the
ROM set description of the arcade artefacts and their code kinds; the
items above hold for it unchanged (an arcade artefact binds to its set
by the set's identity, the runtime keeps board, memory map and
interrupt entries).
