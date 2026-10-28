# Hardware Specification: Ikari Warriors (SNK, 1986)

Technical reference for the recompiler and runtime, as required by
`docs/concept.md` section 26.

**Primary source:** MAME driver `mamedev/mame`, commit
`0c77e0bc49ff302e248dbe9be4659448f07705d9` (master, retrieved 2026-10-02):
`src/mame/snk/snk.cpp`, `snk.h`, `snk_v.cpp` (BSD-3-Clause). Line references
(`snk.cpp:1559`) refer to this commit. Secondary reference (not yet
incorporated): MiSTer `Arcade-IkariWarriors_MiSTer`.

**Reference ROM set:** `ikari` (US JAMMA, MAME parent set). Recommendation for
version 0.1, to be confirmed. Differences in the clones are noted in section 12.

---

## 1. System Overview

| Component | Chip | Clock | Source |
|---|---|---|---|
| CPU A (main) | Z80A | 13.4 MHz / 4 = 3.35 MHz ("verified on pcb") | snk.cpp:4243 |
| CPU B (sub) | Z80A | 13.4 MHz / 4 = 3.35 MHz | snk.cpp:4247 |
| Sound CPU | Z80A | 8 MHz / 2 = 4.0 MHz | snk.cpp:4251 |
| FM sound | 2x YM3526 (OPL) | 8 MHz / 2 = 4.0 MHz each | snk.cpp:4273-4277 |
| Video | SNK discrete (tx + bg + 2 sprite groups) | - | snk_v.cpp |
| Palette | 1024 entries RGB-444 from 3 PROMs, with shadow | snk.cpp:4265 |

Boards (JAMMA version): CPU `A6002UP03-02`, Middle `A5004UP02-02`,
Video `A5004UP01-02` (snk.cpp:5343-5351).

**No Z80 port I/O:** The driver configures program address spaces
(`AS_PROGRAM`) exclusively, no I/O maps. All hardware is
memory-mapped; the analyzer should log `IN`/`OUT` instructions should they
ever appear.

**Note on I/O mirroring:** In the range `0xC000-0xCFFF`, MAME maps only
the addresses actually used; the hardware presumably mirrors extensively
there (snk.cpp:486-487). For the recompiler this means: do not treat unknown
accesses in this window as errors, but log them.

---

## 2. ROM Layout (Set `ikari`, snk.cpp:5353-5396)

| Region | File | Size | CRC32 | Contents |
|---|---|---|---|---|
| maincpu | `1.4p` | 0x10000 | `52a8b2dd` | CPU A program (mapped: 0x0000-0xBFFF) |
| sub | `2.8p` | 0x10000 | `45364d55` | CPU B program (mapped: 0x0000-0xBFFF) |
| audiocpu | `3.7k` | 0x10000 | `56a26699` | Sound program (mapped: 0x0000-0xBFFF) |
| proms | `a6002-1.1k` | 0x400 | `b9bf2c2c` | Palette R (nibbles) |
| proms | `a6002-2.2l` | 0x400 | `0703a770` | Palette G |
| proms | `a6002-3.1l` | 0x400 | `0a11cdde` | Palette B |
| rjproms | `1.1d`, `1.2d` | 0x1000 each | **NO_DUMP** | LS30 rotary decode (MB7134) |
| tx_tiles | `p7.3b` | 0x4000 | `a7eb4917` | 512x 8x8, 4bpp packed |
| bg_tiles | `p17.4d` `p18.2d` `p19.4b` `p20.2b` | 4x 0x8000 | `e0dba976` `24947d5f` `9ee59e91` `5da7ec1a` | 1024x 16x16, 4bpp packed |
| sp16_tiles | `p8.3d` `p9.3f` `p10.3h` | 3x 0x8000 | `9827c14a` `545c790c` `ec9ba07e` | 1024x 16x16, 3bpp planar (1 ROM = 1 plane) |
| sp32_tiles | `p11.4m` `p14.2m` `p12.4p` `p15.2p` `p13.4r` `p16.2r` | 6x 0x8000 | `5c75ea8f` `3293fde4` `95138498` `65a61c99` `315383d7` `e9b03e07` | 512x 32x32, 3bpp planar (2 ROMs = 1 plane, **mind the load order**) |

SHA1 hashes are in the ROM_START block (snk.cpp:5353 ff.); those of the three
program ROMs are in `games/ikari/ikari.toml` and are checked by
`romtool`.

The three CPU ROMs are 64 KB in size, but only 48 KB are mapped (0x0000-0xBFFF);
no banking in the driver. **Resolved (romtool, 2026-10-05):** 0xC000-0xFFFF
is empty in all three images (0xFF throughout).

Code share according to static analysis (romtool): CPU A approx. 22.0 KB of code,
ending at 0x68DA; CPU B approx. 2.5 KB, ending at 0x0D80; sound approx. 1.9 KB,
ending at 0x07BA. The rest of the mapped range is data.

---

## 3. CPU A: Memory Map (`ikari_cpuA_map` snk.cpp:1578 + `ikari_common_map` snk.cpp:1559)

| Address | R/W | Function |
|---|---|---|
| 0x0000-0xBFFF | R | ROM `1.4p` |
| 0xC000 | R | Input IN0 (system: coins, start, sound busy) |
| 0xC100 | R | Input IN1 (P1: joystick + rotary) |
| 0xC200 | R | Input IN2 (P2: joystick + rotary) |
| 0xC300 | R | Input IN3 (buttons P1/P2) |
| 0xC300 | W | Coin counter (section 10) |
| 0xC400 | W | Sound command latch -> sound CPU (section 7) |
| 0xC500 | R | DSW1 |
| 0xC600 | R | DSW2 |
| 0xC700 | R | Trigger NMI on **CPU B** (read value 0xFF) |
| 0xC700 | W | Acknowledge own NMI (CPU A, line -> clear) |
| 0xC800 | W | bg scroll Y, bits 0-7 |
| 0xC880 | W | bg scroll X, bits 0-7 |
| 0xC900 | W | bg scroll MSB: Bit1 = X bit 8, Bit0 = Y bit 8 (snk_v.cpp:577) |
| 0xC980 | W | tx layer attributes, partly unresolved (section 9, snk_v.cpp:591) |
| 0xCA00 | W | sp16 scroll Y, bits 0-7 |
| 0xCA80 | W | sp16 scroll X, bits 0-7 |
| 0xCB00 | W | sp32 scroll Y, bits 0-7 |
| 0xCB80 | W | sp32 scroll X, bits 0-7 |
| 0xCC00 | W | Hard flags: compare Y, bits 0-7 |
| 0xCC80 | W | Hard flags: compare X, bits 0-7 |
| 0xCD00 | W | Sprite scroll MSB: Bit5 = sp32-X8, Bit4 = sp16-X8, Bit3 = sp32-Y8, Bit2 = sp16-Y8 (snk_v.cpp:583) |
| 0xCD80 | W | Hard flags MSB: Bit7 = X bit 8, Bit6 = Y bit 8; bits 0-5 unclear (possibly radius) |
| 0xCE00/20/40/60/80/A0 | R | Hard flags result sprites 0-7 / 8-15 / ... / 40-47 |
| 0xCEE0 | R | Hard flags result sprites 48-49 (bits 0,1 **and** 4,5) |
| 0xD000-0xD7FF | R/W | bg VRAM, **shared with CPU B**, mirror 0xD800-0xDFFF |
| 0xE000-0xF7FF | R/W | Sprite RAM + work RAM, **shared with CPU B** |
| 0xF800-0xFFFF | R/W | tx VRAM + work RAM, **shared with CPU B** |

## 4. CPU B: Memory Map (`ikari_cpuB_map` snk.cpp:1600)

| Address | R/W | Function |
|---|---|---|
| 0x0000-0xBFFF | R | ROM `2.8p` |
| 0xC000 | R | Trigger NMI on **CPU A** (read value 0xFF) |
| 0xC000 | W | Acknowledge own NMI (CPU B) |
| + complete `ikari_common_map` | | 0xC980, hard flags (0xCC00-0xCEE0), bg VRAM, sprite/work RAM, tx VRAM; identical to CPU A |

CPU B has **no** access to inputs, DSW, sound latch or
scroll registers (except hard flags). All communication goes through
the shared RAM `0xD000-0xFFFF` plus the NMI handshake.

## 5. Shared Memory & CPU Handshake

Both main CPUs physically share the same memory from 0xD000 upward
(`.share()` in both maps): bg VRAM, sprite RAM, tx VRAM and the work RAM
located within them. Consequence for the runtime: one common
memory block; the write order between the CPUs is
relevant to the scheduler.

Handshake mechanism (snk.cpp:740-762), symmetric:

```text
CPU A: READ  0xC700  ->  NMI line of CPU B is ASSERTED
CPU B: WRITE 0xC000  ->  NMI line of CPU B is CLEARED (ack)

CPU B: READ  0xC000  ->  NMI line of CPU A is ASSERTED
CPU A: WRITE 0xC700  ->  NMI line of CPU A is CLEARED (ack)
```

The NMI line stays held until the target CPU acknowledges it itself
(level-triggered in the model; the Z80 NMI is edge-sensitive; the assert/clear pair
must be reproduced exactly).

**Timing of the line change:** MAME does not apply input line changes
between CPUs immediately, but via `scheduler().synchronize()`
(MAME core `src/emu/diexec.cpp:665-691`, `device_input::set_state_synced`;
sound latch/status explicitly in snk.cpp:897-940). As a result, the other CPUs
first catch up to the present of the triggering CPU. Mandatory for us:
CPU A writes a command directly after reset and, after 24 cycles, triggers
the first NMI on CPU B (0x0080-0x0088). If it hits CPU B before it has
executed `DI; LD SP,0xF000`, its stack is at 0xFFFF and the
RAM test overwrites it, as observed in a headless run with a coarse
time slice. The runtime therefore lets the target CPU catch up before every
line change (`catch_up` in `games/ikari/ikari_machine.cpp`).

**Command protocol A -> B** (from the program code, romtool listing): CPU A
writes a command to 0xFEC1 and reads 0xC700; in its NMI handler, CPU B branches
via `0x0108 + (command & 0x0F)` into a table of
`JP nn` instructions. Commands are multiples of 3 (0x00, 0x03, 0x06, 0x09,
0x0C, 0x0F). **Quirk of the original:** CPU A additionally sends 0x12
(0x0E27, 0x0E3F); after masking, 2 remains, CPU B jumps into the middle of a
`JP` instruction (0x010A), executes four `LD BC,nn` and one `DEC BC`, and
lands at table entry 0x0117 (`JP 0x013A`). The seventh entry 0x011A that was
actually intended is never reached.

## 6. Interrupt Sources

| CPU | Source | Trigger | Acknowledge |
|---|---|---|---|
| CPU A | INT | VBlank, every frame (`irq0_line_hold`, snk.cpp:4245) | implicit on interrupt acceptance |
| CPU A | NMI | CPU B reads 0xC000 | CPU A writes 0xC700 |
| CPU B | INT | VBlank (snk.cpp:4249) | implicit on acceptance |
| CPU B | NMI | CPU A reads 0xC700 | CPU B writes 0xC000 |
| Sound | INT | `(sound_status & 0x0B) != 0`: YM1 IRQ, YM2 IRQ or command pending (snk.cpp:893) | via status register 0xF800 (section 7) |
| Sound | NMI | not used (reset clear only, snk.cpp:734) | - |

Interrupt mode: **all three CPUs set IM 1 exclusively** (romtool,
2026-10-05: `IM 1` at 0x0099 in CPU A, 0x0095 in CPU B, 0x0098 in the
sound program; no other IM instruction in reachable code). INT therefore
goes to 0x0038 regardless of the bus value, NMI to 0x0066. MAME's `irq0_line_hold` holds the INT line
until acceptance; there are no daisy chain/IM2 vectors (discrete logic,
the bus presumably supplies 0xFF -> RST 38h in IM 1).

## 7. Sound System

### Sound CPU Memory Map (`YM3526_YM3526_sound_map` snk.cpp:1872 + `sound_common_map` snk.cpp:1864)

| Address | R/W | Function |
|---|---|---|
| 0x0000-0xBFFF | R | ROM `3.7k` |
| 0xC000-0xCFFF | R/W | RAM. MAME maps 4 KB without mirroring (`map(0xc000, 0xcfff).ram()`, snk.cpp:1867); the board carries a 2 KB 6116, so in reality it is presumably mirrored. The runtime follows MAME (4 KB flat); the difference is only visible if the program uses both halves separately. |
| 0xE000 | R | Read sound command latch |
| 0xE800 | R/W | YM3526 #1: read status / write address |
| 0xEC00 | W | YM3526 #1: write data |
| 0xF000 | R/W | YM3526 #2: read status / write address |
| 0xF400 | W | YM3526 #2: write data |
| 0xF800 | R/W | Sound status register |

### Sound Status Register 0xF800 (snk.cpp:837-940)

4 status bits ("athena onwards", applies to Ikari):

```text
Bit 0: IRQ request YM3526 #1
Bit 1: IRQ request YM3526 #2
Bit 2: Sound CPU busy
Bit 3: Sound command pending
```

Reading returns the bits. Writing: the lower nibble is always 0x0F, the upper
nibble is an **active-low clear mask**:

```text
Bit 4 = 0  ->  acknowledge YM1 IRQ   (clear status bit 0)
Bit 5 = 0  ->  acknowledge YM2 IRQ   (clear status bit 1)
Bit 6 = 0  ->  clear busy flag       (status bit 2)
Bit 7 = 0  ->  acknowledge command   (status bit 3)
```

INT line of the sound CPU = `status & 0x0B` (bits 0, 1, 3).

### Command Flow

```text
CPU A: WRITE 0xC400 (command)
  -> latch filled, status |= 0x0C (pending + busy), sound INT asserted
Sound CPU: READ 0xE000 -> fetch command
Sound CPU: WRITE 0xF800 (mask) -> acknowledge pending/busy/YM IRQs
CPU A: reads busy flag as input bit (IN0, section 10) for flow control
```

The YM IRQ callbacks (timers of the YM3526) set bits 0/1 (snk.cpp:897-907),
so the YM3526 timers must run along in the scheduler (ymfm supplies the
IRQ signals).

### YM3526 Integration (runtime since 2026-10-06)

- **Clock and output:** both chips 8 MHz / 2 = 4 MHz, gain 2.0 each onto
  one mono channel (snk.cpp:4273-4279). ymfm generates one sample per
  72 chip clocks (prescale 4 x 18 operators), i.e. 55,555.6 Hz, including
  YM3014 DAC rounding. MAME scales the 16-bit value by 1/32768
  (`ymfm_mame.h`, `put_int(..., 32768)`); the runtime mixes identically.
- **IRQ:** only the rising edge of the chip IRQ counts; it sets
  status bit 0/1 until the sound CPU clears it via 0xF800
  (`ymirq_callback_1/2`, snk.cpp:897-907, `if (state)`).
- **Timers:** ymfm reports timer durations in chip clocks (`ymfm_set_timer`); MAME
  uses this to set a timer from the time of access (`ymfm_mame.h:86`). The
  runtime stops the sound CPU at each expiration time; the interrupt
  takes effect, like all others, at the next instruction boundary.
- **Time of access:** bus callbacks see the clock at the start of the
  currently executing instruction (`Z80State::block_t`, set by the emitter before each
  instruction). Previously the block start applied; as a result, the timer start was up
  to ~300 clocks too early, and timer and command interrupts arrived in a different
  order than in MAME. MAME writes even more precisely (within the
  instruction); the remaining deviation is a few clocks.
- **Timer B phase depends on synthesis:** ymfm starts timer B in phase
  with a free-running 16-sample prescaler that it derives from its
  sample counter (`update_timer(1, ..., -(m_total_clocks & 15))`,
  ymfm_fm.ipp:1587). Synthesis must therefore run up to the
  present before every access, even if nobody is listening (MAME: `update_streams()` before
  `status_r`/`data_w`, ymfm_mame.h:181-186).

**Two variants of sample counting (open, to be decided):**

| Variant | Sample counter at time t | Source |
|---|---|---|
| Chip (runtime default) | floor(clocks / 72) | ymfm: prescale x operators |
| MAME | floor(t * 55555) + 1 | `disound.cpp:547-572`: stream rate = integer `clock / 72` (`ymfm_mame.h:196`), update includes the current sample |

MAME's counter lags behind the chip by ~0.56 samples per second. Because
timer B adopts the phase of this counter, its interrupts shift relative to
timer A by multiples of 72 clocks; where both timers are
close together, the sound program reads a different status bit and
updates the music one interrupt later. Measurement 2026-10-06
(3000 frames with input script): first deviation of the sound I/O sequence at
frame 477 (chip counting) or frame 1356 (`ikari_headless
--mame-sample-count`), respectively. The difference is not audible; the level
matches MAME to within < 1 dB in both variants. Which phase the
real prescaler has at power-on is unknown.

Update 2026-10-26: the stage M lockstep of
[arcade-oracles.md](arcade-oracles.md) counts samples as MAME does and
then matches MAME 0.285 in every YM3526 write and status read of 3000
attract frames and a 112,000-frame game, so the remaining deviation of
the chip variant is MAME's integer stream rate alone (finding F4 there).
The chip variant stays the runtime default.

## 8. Video Timing

- Resolution: 36x28 tiles = 288x224 px, visible 288x216 (lines 8-223),
  60 Hz (snk.cpp:4257-4260). Monitor rotated by 270 degrees (ROT270, portrait).
- VBlank INT on CPU A and CPU B once per frame each.
- Budget per frame (nominal): CPU A/B 55,833 cycles each, sound 66,667.
- Exact raster values (pixel clock, H/V total, VBlank duration) are not in the
  MAME driver -> look them up in the MiSTer core (open item). MAME
  synchronizes the three CPUs with a quantum of 1/6000 s (snk.cpp:4254);
  a reference point for the time slice size of our scheduler (~560 cycles).

## 9. Graphics Hardware

### Layer Structure and Render Order (`screen_update_ikari` snk_v.cpp:969)

```text
1. bg tilemap (opaque)
2. sp16 sprites #0-24   (low priority)
3. sp32 sprites #0-24
4. sp16 sprites #25-49  (high priority)
5. tx tilemap (text, transparent)
```

### tx Layer (Text)

- 8x8 px, 4bpp packed (`gfx_8x8x4_packed_lsb`), 512 tiles, palette base
  0x180 (snk.cpp:3991).
- 36x28 tiles, special scan `marvins_tx_scan_cols` (snk_v.cpp:64): the
  middle 32 columns from RAM page 1, the outer 2+2 columns from page 2
  (`offset 0x400+`). VRAM byte = tile code; attribute `tile_index` bit 10 ->
  `TILE_FORCE_LAYER0` (snk_v.cpp:86).
- Pen 15 transparent; Y offset scrolldy(8, 8). No scrolling in the game.
- Register 0xC980 (`ikari_unknown_video_w`, snk_v.cpp:591): Bit 0 =
  palette offset (<<4), Bit 4 = tile bank (+0x100). Normal value 0x20,
  test mode 0x31. **Meaning only partially resolved**: MAME TODO
  (snk.cpp:656-658): presumably also related to the FG color,
  which is why the color test in ikaria/ikarijp is still wrong.

### bg Layer

- 16x16 px, 4bpp packed, 1024 tiles, palette base 0x100 (snk.cpp:3992).
- Tilemap 32x32 (512x512 px), scan cols. 2 bytes per tile
  (snk_v.cpp:150): byte 0 = code bits 0-7; byte 1: bits 0-1 = code bits
  8-9, bits 4-6 = color (0-7).
- VRAM 0xD000-0xD7FF (2 KB = 1024 tiles x 2 bytes), mirror at 0xD800
  (ikari/victroad write to 0xD800, ikarijp to 0xD000, snk.cpp:1572).
- Scroll: 9-bit X/Y (registers section 3), render offset scrolldx(15, 24),
  scrolldy(8, -32).

### Sprites

Two independent groups, format 4 bytes per sprite (snk_v.cpp:784,
attribute documentation snk_v.cpp:835-857):

```text
Byte 0: Y position bits 0-7
Byte 1: tile number bits 0-7
Byte 2: X position bits 0-7
Byte 3: attributes
        Bits 0-3: color
        Bit 4:    Y position bit 8
        16x16: Bits 5-6 = tile bits 8-9
        32x32: Bit 6    = tile bit 8
        Bit 7:    X position bit 8
```

| Group | Count | Sprite RAM | GFX | Palette base |
|---|---|---|---|---|
| sp32 (32x32) | 25 | 0xE000 + 0x000, 4 bytes/sprite | 512 tiles, 3bpp planar | 0x080 |
| sp16 (16x16) | 50 | 0xE000 + 0x800, 4 bytes/sprite | 1024 tiles, 3bpp planar | 0x000 |

Position calculation (snk_v.cpp:803-822): `sx = xscroll + 300 - size - x`,
`sy = -yscroll + 7 - size + y`, both mod 512 with wraparound. No
hardware flip for Ikari sprites.

3bpp pens: 0-5 color, **pen 6 = shadow**, pen 7 = transparent
(snk_v.cpp:199-213): shadow replaces the destination color with palette entry
`index | 0x200`.

### Palette

- 1024 entries, RGB-444 from three bipolar PROMs (R/G/B 0x400 nibbles each),
  standard decoding `RGB_444_PROMS` (snk.cpp:4265), **not** the
  weighted tnk3 variant.
- Allocation: 0x000-0x07F sp16, 0x080-0x0FF sp32, 0x100-0x17F bg,
  0x180-0x1FF tx, 0x200-0x3FF shadow colors.

## 10. Hard Flags (Bounds-Check Hardware)

MAME model (snk.cpp:967-1039), explicitly marked as a **simulation**:
details possibly inaccurate (especially a possible size/radius component);
exact verification would require a hardware trojan. The simulation passes
the boot checks and makes in-game collision functional;
the bit order in `check8` is verified to be relevant.

- Write registers: 0xCC00 (Y low), 0xCC80 (X low), 0xCD80 (Bit7 = X bit 8,
  Bit6 = Y bit 8; bits 0-5 unclear).
- Check per sp16 sprite `n` (sprite RAM 0xE800 + 4n):

```text
x  = byte2 + ((byte3 & 0x80) << 1)
y  = byte0 + ((byte3 & 0x10) << 4)
dx = (x - hf_posx) & 0x1FF
dy = (y - hf_posy) & 0x1FF
Bit = 0  if  0x20 < dx <= 0x1E0  and  0x20 < dy <= 0x1E0,  otherwise 1
```

- 0xCE00+0x20*k returns the bits for sprites 8k...8k+7 (k = 0...5);
  0xCEE0 returns sprites 48/49 twice: bits 0/1 (boot test) and 4/5
  (game).
- Boot performs a "front hard check"; the game **additionally** does
  software collision; according to a MAME note, a fake that always returns "passed"
  is sufficient for the game to run (snk.cpp:595-598). A good
  bring-up shortcut; model exactly later.

## 11. Input Mapping (Set `ikari`, JAMMA, snk.cpp:2952)

All inputs active-low unless noted.

| Port | Address | Bit | Function |
|---|---|---|---|
| IN0 | 0xC000 | 0 | Sound busy (active-high, status bit 2 of the sound CPU) |
| | | 1 | Service (1 credit) |
| | | 4 / 5 | Coin 2 / Coin 1 |
| | | 6 / 7 | Start 2 / Start 1 |
| IN1 | 0xC100 | 0-3 | P1 joystick up/down/left/right (8-way) |
| | | 4-7 | P1 rotary (LS30, 12 positions) |
| IN2 | 0xC200 | 0-3 | P2 joystick |
| | | 4-7 | P2 rotary |
| IN3 | 0xC300 | 0 / 1 | P1 button 1 / 2 |
| | | 3 / 4 | P2 button 1 / 2 |
| DSW1 | 0xC500 | - | see below |
| DSW2 | 0xC600 | - | see below |

**Rotary:** 12-position rotary knob (LS30). The decode PROMs (MB7134,
`1.1d`/`1.2d`) are **NO_DUMP** in MAME; MAME simulates the decoded
4-bit value directly (POSITIONAL, 12 positions, wrap, inverted). The runtime
does the same: return position 0-11 on bits 4-7.

Key direction in MAME: `PORT_CODE_DEC(KEYCODE_Z)`, `PORT_CODE_INC(KEYCODE_X)`
with `PORT_REVERSE` (snk.cpp:2968, player 2 N/M snk.cpp:2975); the reversal
computes `m_reverse_val - value` (ioport.cpp:3785). Net effect: **Z increases the
value read**, X decreases it.

Evaluation by the game (observed 2026-10-06, rotary sweep in the
recompiled program, not from MAME): The program evaluates only the **change** in the
value; it keeps the last value read in 0xFDCD (player 1) or
0xFE1D (player 2), respectively. One position more rotates the soldier by 45 degrees
counterclockwise. The facing direction is stored in 0xFDB6 (player 1) and 0xFE06
(player 2) as 0-15 in 22.5-degree steps, 0 = top of screen, increasing
clockwise; one rotary position changes it by 2. The front ends use
this for aiming with the stick (`games/ikari/ikari_input.h`); the machine
itself never reads it.

**Coin counter** (write 0xC300, snk.cpp:1175): Bit 7 = 0 -> pulse counter 1,
Bit 6 = 0 -> pulse counter 2.

**DIP switches** (excerpt; complete in snk.cpp:2987-3035): DSW1: 1
kill-each-other, 2 fire buttons separate/combined, 3+DSW2:5,6 bonus lives,
4 lives 3/5, 5-6 Coin A, 7-8 Coin B. DSW2: 1-2 difficulty, 3-4
demo sound/freeze/cheat, 7 unused (strange test at 0x07CC), 8
continue yes/no.

## 12. Version Differences (Clones)

| Set | Difference |
|---|---|
| `ikaria`, `ikaria2` (22-way) | IN0 assigned differently: Bit 0/1 = Coin1/2, Bit 2 = Service, Bit 3/4 = Start1/2, Bit 5 = sound busy, Bit 7 = Tilt (snk.cpp:3038) |
| `ikarinc`, `ikarijp` | like ikaria, without continue (DSW2:8 unused) |
| `ikarijp` | writes bg VRAM at 0xD000 instead of 0xD800 (mirror covers both) |
| `ikarijpb`, `ikariram` (bootlegs) | no rotary; joystick mirrored onto rotary bits, code patched |
| `victroad` | same hardware, sound: YM3526 + Y8950 instead of 2x YM3526 (snk.cpp:4282), confirms the section 18 extension path |

## 13. Open Items

1. **0xC980**: function only partially known (MAME TODO); collect traces,
   color test in clones as a test case.
2. **Hard flags**: possible size/radius bits (0xCD80 bits 0-5) unclear;
   the MAME model is an approximation. Compare with the MiSTer implementation.
3. **Exact raster timing** (pixel clock, VBlank length, INT timing
   relative to the raster): extract from the MiSTer core. Partly done in
   [ikari-timing-reference.md](ikari-timing-reference.md): the MiSTer
   model gives 416 x 262 at 61.47 Hz (54,496 CPU cycles per frame), but
   no source measures the board.
4. ~~Upper 16 KB of the CPU ROMs~~, resolved: empty (0xFF), see section 2.
5. **Rotary decode PROMs** are missing worldwide (NO_DUMP); behavior defined only via
   the MAME simulation; sufficient for us.
6. ~~Z80 interrupt vector/IM~~, resolved: IM 1 on all three CPUs,
   see section 6.
7. **YM3526 timer B prescaler:** phase at power-on unknown; MAME
   and the chip model count samples differently (section 7, two variants). A
   MiSTer comparison of the OPL timer could clarify which side is closer to
   the hardware.
8. **Cycle-exact interrupt and bus timing:** MAME takes INT between
   instructions but never directly after an `EI` (MAME 0.289:
   `src/devices/cpu/z80/z80.cpp:608-612`, `ei()` sets `SA_AFTER_EI`, and
   the `check_interrupts` macro in `z80.lst:1021` skips INT while it is
   set), and synchronises all CPUs on every line change (section 5,
   `diexec.cpp` `set_state_synced`). The runtime takes interrupts between
   instructions as well, with the same `EI` rule (`runtime/z80_cpu.cpp`),
   times bus accesses at the start of their instruction and brings the
   other main CPU up to the time of every access to the memory CPU A and
   B share, so both see each other's accesses in time order (MAME:
   ordered by time slices). The program reads
   timing back (CPU A uses the R register as a random number, CPU B's
   collision check races CPU A's sprite copy), so this decides whether a
   replayed MAME game stays identical in MAMR (MAMR's own README, not published,
   "Verification against MAME"; the current method is docs/arcade-oracles.md). Not needed to run the game. Hardware, MiSTer, MAME and
   MAMR are compared rule by rule, with the measured causes of the
   divergences from frames 7989 and 9773, in
   [ikari-timing-reference.md](ikari-timing-reference.md).
