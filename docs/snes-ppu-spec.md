# SNES PPU Specification

Register and behaviour specification of the two SNES picture chips
(S-PPU1 5C77, S-PPU2 5C78) for phase S6 of docs/snes-architecture.md.
It is written so that the renderer can be built from this text alone,
without reading another implementation. The timing model it serves is
the one of docs/snes-architecture.md section 4: stage S renders per
scanline from a time-stamped write log, renders segments where writes
fall inside the visible span, and falls back to dot rendering for the
cases listed in section 8; stage E (dot exact) is built later from the
same description.

The board side (memory map, H/V counters, NMI/IRQ, DMA/HDMA cost) is
specified in docs/snes-hardware-spec.md sections 1 to 3; this document
refers to it instead of repeating it. It is a standalone document;
docs/snes-hardware-spec.md continues with the CPU in its section 4.

## 0. Sources, notation, provenance

**Sources** (all retrieved 2026-10-24):

- **fullsnes** (Martin Korth, problemkaputt.de/fullsnes.htm). Cited by
  section title: [FS "SNES PPU Window"].
- **Anomie's documents**: register doc regs.txt (revision 1157,
  2007-07-12), timing doc timing.txt (revision 1160, 2008-12-21), open
  bus and wrapping doc ob-wrap.txt (revision 1126, 2007-04-21). Cited as
  [AN-R "2105"] (register entry) or [AN-R SPRITES] (chapter), [AN-T
  S-PPU] and [AN-O].
- **SNESdev wiki** (snes.nesdev.org): pages PPU registers, Backgrounds,
  Sprites, Windows, Color math, Offset-per-tile, Timing, Errata,
  Tricky-to-emulate games, Uncommon graphics mode games, Emulator tests.
  Cited as [WIKI page].
- **Test ROMs with hardware findings**: undisbeliever/snes-test-roms
  (Zlib, commit ac6ef80), cited as [UB test-name]; results of the
  sprite tests as reported on the nesdev forum (thread post 292526,
  linked from [WIKI Sprites]) and on undisbeliever.net register pages.
- **ares** (ISC, ares-emulator/ares commit c76aaff, the version pinned
  by the oracle pipeline). Cited as [ARES path:line] with paths relative
  to `ares/sfc/`; `ppu/` is the dot renderer, `ppu-performance/` the
  scanline renderer. A number taken only from ares is marked IMPL and
  never stands alone where a document exists.
- **zelda3** (snesrev/zelda3, MIT, commit 45a149d) and public
  disassemblies for the scope of section 9.

The structure and decomposition of MAMR's PPU code follow ares under
its ISC licence: the background fetch, Mode 7, the sprite evaluation and
fetch with the size tables, the compositor with the window test and the
priority encoding, and the register and port parts of the register bank
are close translations of the ares files named in
third_party/ares/LICENSE, which lists them function by function. The
numbers and rules in this document come from the documentation and the
test ROMs; where only ares gives a value it is marked IMPL. No code of
the other sources is taken over. MAME's PPU (GPL-2.0+) was not used.

**Provenance classes** (the same as docs/snes-hardware-spec.md, plus two):

| Class | Meaning |
|---|---|
| DOC | hardware documentation based on console tests (fullsnes, Anomie, SNESdev wiki) |
| TEST | a test ROM whose result on a console is published |
| IMPL | what ares does (an emulator, not a hardware claim) |
| CONS | emulator consensus only: two or more emulators agree, no hardware document or test |
| CHOICE | MAMR's decision where the sources are silent or differ |
| OPEN | unknown; S6 must measure or leave it out |

**Notation.** H is the position inside a scanline in master clocks
(0..1363; NTSC 21.477 MHz, PAL in 7.5); "dot" is the H/V latch unit ($213C), 340 per
line, normally 4 clocks (section 7.1). V is the scanline (0..261 NTSC, 0..311 PAL).
"Visible line" means V=1..224 (1..239 with overscan). "Active display"
means a visible line while force blank is off. "Rendering period" means
V < vdisp (225 or 240) with force blank off; it includes line 0 and the
HBlank of those lines. Hex values are written $xx. Bits are numbered
from 0 = least significant. A write to a "write twice" register is one
byte; the PPU has internal latches that combine bytes.

## 1. Registers $2100-$213F

### 1.1 Overview and timing classes

The two PPU chips decode the B-bus addresses $2100-$213F (mirrored in banks
$00-$3F and $80-$BF at $2100-$213F) [FS "SNES I/O Map"]. $2100-$2133 are
write-only, $2134-$213F read-only. Every write is a byte write at the
time stamp of the CPU or DMA bus cycle.

Each register has a **timing class**, which tells the renderer when a
new value takes effect. The classes are defined by the stage of the
PPU pipeline that reads the value (section 7.3 gives the clock
positions):

| Class | Read by | When a write takes effect |
|---|---|---|
| P (pixel) | the compositor, once per pixel | from the next pixel whose compose time is after the write |
| F (fetch) | the BG tile fetcher, once per tile column and layer | from the next tile column whose name-table fetch slot is after the write |
| O (object) | sprite evaluation (line N) and sprite tile fetch (HBlank of N) | for the sprites drawn on line N+1 if the write is before the respective window; mixed when inside |
| M (memory port) | the CPU port of VRAM, OAM, CGRAM | at once, subject to the access rules of 1.5 |
| L (line/frame) | latched once per line or frame | named per register |

In ares nearly every register is read live by the stage that uses it,
which is how the classes above were derived [ARES ppu/main.cpp:212-221,
ppu/background.cpp:27-121, ppu/dac.cpp:31-136]; Anomie lists "when
writing to them is effective" as unresolved [AN-R BACKGROUNDS "Unresolved
Issues"]. The exact clock offsets are therefore IMPL and are the first
calibration target of section 10.

### 1.2 Register table

All write registers power on with unknown content; for oracle runs they
are 0 (docs/snes-oracle-format.md section 6, "fill=00"), except the two
open-bus latches (1.6).

| Addr | Name | Bits (7..0) | Meaning | Class |
|---|---|---|---|---|
| $2100 | INIDISP | `F--- BBBB` | F force blank; B master brightness 0-15 | P (brightness, blank output); O (blank stops sprite evaluation); see 1.4 |
| $2101 | OBSEL | `SSSN NbBB` | S size pair (3.2); N name select: second table at base + (N+1)*$1000 words; bBB name base, word address bBB<<13 | O |
| $2102 | OAMADDL | `AAAA AAAA` | OAM word address bits 0-7 | M, see 1.3 |
| $2103 | OAMADDH | `P--- ---B` | B word address bit 8 (table select); P priority rotation | M; P is L (3.4) |
| $2104 | OAMDATA | data | OAM write, see 1.3 | M |
| $2105 | BGMODE | `4321 PMMM` | M mode 0-7; P mode 1 BG3 priority; 1-4 BGn 16x16 tiles | F (depth, tile size); P (priority order) |
| $2106 | MOSAIC | `SSSS 4321` | S size-1 (0 = 1x1 .. 15 = 16x16); 1-4 enable per BG | P (horizontal), L (vertical counter, 6) |
| $2107-$210A | BG1SC-BG4SC | `AAAA AAYX` | name table word address A<<10; X 2 maps wide; Y 2 maps tall | F |
| $210B | BG12NBA | `BBBB AAAA` | character base, word address A<<12 (BG1), B<<12 (BG2) | F |
| $210C | BG34NBA | `DDDD CCCC` | as $210B for BG3 (C), BG4 (D) | F |
| $210D | BG1HOFS / M7HOFS | write twice | 10-bit BG1 H scroll and 13-bit signed Mode 7 H scroll, two latches (1.3) | F (BG1), P (Mode 7) |
| $210E | BG1VOFS / M7VOFS | write twice | as above, vertical | F, P |
| $210F-$2114 | BG2HOFS..BG4VOFS | write twice | 10-bit scroll | F |
| $2115 | VMAIN | `I--- RRSS` | I increment after high (1) or low (0) byte; R address remap; S step 1, 32, 128, 128 | M |
| $2116/$2117 | VMADDL/H | word address | VRAM word address; writing loads the read buffer | M |
| $2118/$2119 | VMDATAL/H | data | VRAM write low/high byte | M |
| $211A | M7SEL | `RF-- --YX` | R tilemap repeat off; F fill with character 0 (else transparent) when R=1; Y/X flip the 256x256 screen | P |
| $211B-$211E | M7A-M7D | write twice | signed 8.8 matrix; M7A also 16-bit multiplicand, M7B high byte 8-bit multiplier | P (Mode 7), M (product) |
| $211F/$2120 | M7X/M7Y | write twice | signed 13-bit centre | P |
| $2121 | CGADD | address | CGRAM word address; resets the byte flip-flop | M |
| $2122 | CGDATA | data | CGRAM write, see 1.3 | M |
| $2123 | W12SEL | `DdCc BbAa` | per BG1 (Aa = window 1, Bb = window 2) and BG2 (Cc, Dd): capital = enable, small = invert | P |
| $2124 | W34SEL | as $2123 | BG3, BG4 | P |
| $2125 | WOBJSEL | as $2123 | OBJ (low nibble), colour window (high nibble) | P |
| $2126-$2129 | WH0-WH3 | position | window 1 left, right; window 2 left, right (0-255) | P |
| $212A | WBGLOG | `4433 2211` | window combine logic per BG: 0 OR, 1 AND, 2 XOR, 3 XNOR | P |
| $212B | WOBJLOG | `---- CCOO` | logic for OBJ (O) and colour window (C) | P |
| $212C | TM | `---O 4321` | main screen enable | P |
| $212D | TS | `---O 4321` | sub screen enable | P |
| $212E | TMW | `---O 4321` | apply windows to the main screen layer | P |
| $212F | TSW | `---O 4321` | apply windows to the sub screen layer | P |
| $2130 | CGWSEL | `MMSS --AD` | M main black region, S math prevent region (5.3); A addend is sub screen; D direct colour | P |
| $2131 | CGADSUB | `SHBO 4321` | S subtract; H half; B backdrop, O OBJ (palettes 4-7), 1-4 BG math enable | P |
| $2132 | COLDATA | `BGRC CCCC` | C intensity, written to each of B, G, R whose bit is set | P |
| $2133 | SETINI | `EX-- HOoI` | E external sync (0); X Mode 7 EXTBG; H pseudo hi-res; O overscan (239 lines); o OBJ interlace; I interlace | see 1.4 |
| $2134-$2136 | MPYL/M/H | read | signed M7A * (signed high byte of M7B), 24 bit | M |
| $2137 | SLHV | read | latches H/V counters if WRIO ($4201) bit 7 = 1; returns CPU open bus | M |
| $2138 | RDOAM | read | OAM read, see 1.3 | M |
| $2139/$213A | RDVRAML/H | read | VRAM read buffer, see 1.3 | M |
| $213B | RDCGRAM | read twice | CGRAM read, see 1.3 | M |
| $213C | OPHCT | read twice | latched H counter, 9 bit | M |
| $213D | OPVCT | read twice | latched V counter, 9 bit | M |
| $213E | STAT77 | `TRM- VVVV` | T time over, R range over, M master/slave (0), V PPU1 version (1) | M |
| $213F | STAT78 | `FL-P VVVV` | F interlace field; L counter latch flag; P 1 = PAL; V PPU2 version (1-3) | M |

Bit fields: [FS "SNES PPU Control", "BG Control", "Rotation/Scaling",
"Window", "Color-Math", "Timers and Status", "SNES Memory OAM/VRAM/CGRAM
Access"], [AN-R 2100-213f], [WIKI PPU registers] (DOC). They agree
except for the points listed in 1.7.

### 1.3 Latches and data ports

**Scroll latches ($210D-$2114).** Two 8-bit latches are shared by all
eight BGnxOFS registers, a third by the Mode 7 registers:

```text
BGnHOFS = (data << 8) | (bgofs_latch & ~7) | (bghofs_latch & 7)
          bgofs_latch = data; bghofs_latch = data
BGnVOFS = (data << 8) | bgofs_latch
          bgofs_latch = data
writes to $210D / $210E additionally:
M7HOFS / M7VOFS = (data << 8) | mode7_latch;  mode7_latch = data
```

Values are kept to 10 bits for BGn and 13 bits (signed) for Mode 7.
[WIKI PPU registers BGnHOFS, BGnVOFS, M7HOFS] (DOC), the same structure
in [ARES ppu/io.cpp:309-372] (IMPL). Anomie writes the low three bits of
BGnHOFS as `((CurrentValue >> 8) & 7)` instead of a separate latch
[AN-R "210d"], see 1.7.

**Mode 7 latch ($211B-$2120 and $210D/$210E).** `reg = (data << 8) |
mode7_latch; mode7_latch = data` for M7A, M7B, M7C, M7D, M7X, M7Y, and
for M7HOFS/M7VOFS as above. The latch is shared with M7HOFS/M7VOFS but
not with the BG scroll latches [AN-R "211b"], [FS "SNES PPU
Rotation/Scaling"], [WIKI PPU registers M7A] (DOC). Consequence: an HDMA
or interrupt write to $210D/$210E or any M7 register between the two
bytes of an M7A write corrupts the multiplier input [WIKI Errata "Mode
7 multiplier"] (DOC).

**Multiplier ($2134-$2136).** Result = (signed 16-bit M7A) * (signed
8-bit: the last byte written to M7B, i.e. M7B >> 8), 24-bit two's
complement, available at once [WIKI PPU registers MPY] (DOC), [ARES
ppu/io.cpp:77-92] (IMPL). fullsnes adds that in Mode 7 during the
drawing period the multiplier is busy with the matrix and the registers
show intermediate products [FS "SNES PPU Rotation/Scaling", "M7A/M7B
Port Notes"] (DOC); ares does not model this (IMPL). The target games
are not known to read MPY during Mode 7 display; S6 implements the
plain product and logs reads of $2134-$2136 during Mode 7 active display.

**OAM port ($2102-$2104, $2138).** The internal address is 10 bits:
bit 9 selects the high table (32 bytes, mirrored over $200-$3FF), bits
0-8 the byte. Writing $2102 or $2103 copies the 9-bit word address
(OAMADDH bit 0 : OAMADDL) to internal address bits 1-9 and clears bit 0
[FS "SNES Memory OAM Access"], [AN-R "2102"] (DOC).

```text
write $2104:  if (addr & 1) == 0: oam_latch = data
              if addr < $200 and (addr & 1) == 1:
                  OAM[addr-1] = oam_latch; OAM[addr] = data
              if addr >= $200: OAM[$200 + (addr & $1F)] = data
              addr = (addr + 1) & $3FF
read  $2138:  data = OAM[addr] (high table mirrored); addr = (addr + 1) & $3FF
```

The low table is only written on the odd byte, with the even byte taken
from the latch; the latch is only loaded by even-byte writes, so mixing
reads and writes gives Anomie's "01 02 01 03" example [AN-R "2104",
SPRITES] (DOC). Every OAM data access also re-derives the priority
rotation start (3.4) [ARES ppu/io.cpp:103, 235] (IMPL).

**OAM address reset.** At the start of VBlank (V = vdisp) the internal
address is reloaded from the last $2102/$2103 value, but only if force
blank is off then; the same reload happens when force blank is turned
off (INIDISP bit 7 from 1 to 0) during line V = vdisp [FS "SNES Memory
OAM Access"], [AN-T "OAM RESET"], [AN-R "2100"] (DOC). Anomie quotes
byuu: the reset happens at H=10 dots of that line and on any 1-to-0
transition of INIDISP bit 7 [AN-T "OAM RESET"] (DOC, second hand). ares
resets at the start of line vdisp when force blank is off, and on a
write to INIDISP during line vdisp while force blank was on [ARES
ppu/object.cpp:31, ppu/io.cpp:195] (IMPL). CHOICE: as ares, reset at
V=vdisp H=0 if force blank is off, and on a write to $2100 that clears
bit 7 during line vdisp. byuu's H=10 dots is not followed: the internal
address is not part of the oracle `ppu` field (format version 4, because
emulators differ right at the sampling point), and no target game
accesses OAM in the first 40 clocks of line vdisp. The "any 1-to-0
transition" variant is OPEN (test with [UB
inidisp_enable_display_mid_frame]).

**VRAM port ($2115-$2119, $2139/$213A).** Word address, 15 bits used
(bit 15 ignored with 64 KiB) [FS "SNES Memory VRAM Access"] (DOC).
Address remapping by VMAIN bits 2-3, applied at each access, not to the
stored address [FS], [WIKI PPU registers VMAIN] (DOC):

```text
R=0: a
R=1: (a & $FF00) | ((a & $001F) << 3) | ((a >> 5) & 7)      8-bit rotate
R=2: (a & $FE00) | ((a & $003F) << 3) | ((a >> 6) & 7)      9-bit rotate
R=3: (a & $FC00) | ((a & $007F) << 3) | ((a >> 7) & 7)      10-bit rotate
```

Write $2118 (low) / $2119 (high) stores one byte; the address is
incremented by the step after the low byte if VMAIN bit 7 = 0, after
the high byte if 1. Reads use a 16-bit buffer:

```text
write $2116 or $2117: buffer = VRAM[remap(addr)]
read $2139: data = buffer.low;  if VMAIN.7 == 0: buffer = VRAM[remap(addr)]; addr += step
read $213A: data = buffer.high; if VMAIN.7 == 1: buffer = VRAM[remap(addr)]; addr += step
```

The buffer is loaded before the increment, so the first read after
setting the address returns the old word twice; writes never touch the
buffer [FS "SNES Memory VRAM Access"], [WIKI PPU registers VMDATAREAD]
(DOC). Access rules in 1.5.

**CGRAM port ($2121, $2122, $213B).** Byte flip-flop, reset by writing
$2121. Write: first byte to a latch, second byte stores the word
`(data & $7F) << 8 | latch` and increments the word address; read:
first read returns the low byte, second read bits 0-6 of the high byte
with bit 7 from the PPU2 open bus, then increments [FS "SNES Memory
CGRAM Access"], [WIKI PPU registers CGDATA, CGDATAREAD] (DOC), [ARES
ppu/io.cpp:128-135, 469-476] (IMPL). The flip-flop is shared between
reads and writes [AN-R "2122"] (DOC).

**H/V counter latch ($2137, $213C, $213D, $213F).**

- Latch events: read of $2137, a 1-to-0 change of WRIO ($4201) bit 7, a
  light gun on controller port 2 pin 6. All of them latch only while
  WRIO bit 7 is 1 (or was 1 for the 1-to-0 change) [FS "SNES PPU Timers
  and Status"], [AN-R "2137", "213c"] (DOC), [ARES ppu/io.cpp:96,
  cpu/io.cpp:144] (IMPL). MAME latches without the WRIO check (noted in
  the preparatory research as a MAME fault).
- The WRIO latch is one dot later than a $2137 read in the same bus
  cycle [AN-T introduction] (DOC).
- Latched H is the dot number (long dots folded, 7.1), latched V the
  line; STAT78 bit 6 is set [ARES ppu/io.cpp:1-6] (IMPL).
- $213C and $213D each have their own read flip-flop: first read bits
  0-7, second read bit 8 in bit 0 and bits 1-7 from the PPU2 open bus.
  The flip-flops are reset only by reading $213F, not by a new latch
  [FS], [AN-R "213c"] (DOC).
- Reading $213F returns the latch flag in bit 6 and clears it (Anomie:
  only when WRIO bit 7 is set [AN-R "213f"]; ares returns 1 in bit 6
  while WRIO bit 7 is 0 [ARES ppu/io.cpp:172-177], IMPL), and resets
  both flip-flops.

**STAT77 / STAT78.** STAT77 bit 7 time over (more than 34 sprite tiles
on a line), bit 6 range over (more than 32 sprites), bit 5 master/slave
pin (0), bit 4 PPU1 open bus, bits 0-3 version 1 [FS], [AN-R "213e"]
(DOC). Both flags are set whether or not OBJ is enabled in TM/TS, and
cleared at the end of VBlank (V=0); fullsnes adds "but NOT during
forced blank" [FS "SNES PPU Timers and Status"] (DOC); ares clears them
at V=0 regardless [ARES ppu/main.cpp:9, ppu/object.cpp:11-14] (IMPL).
CHOICE: clear at V=0 only when force blank is off (fullsnes). STAT78
bit 7 field (toggles at V=0 H=1 dot [AN-T S-PPU REGISTERS]), bit 6
latch, bit 5 PPU2 open bus, bit 4 50 Hz, bits 0-3 PPU2 version; MAMR
reports version 3 (the ares default [ARES ppu/ppu.cpp:52]) and PPU1
version 1.

### 1.4 Registers with special timing

- **INIDISP force blank (bit 7).** Output becomes black at once
  (compositor, class P) [ARES ppu/dac.cpp:44, 83] (IMPL). Sprite
  evaluation and the sprite tile fetch are suspended while it is set,
  so the line after a force-blank period has no (or broken) sprites
  [ARES ppu/object.cpp:36, 98] (IMPL), [WIKI PPU registers INIDISP
  "CAUTIONS"] (DOC: "current and next scanline will contain sprite
  glitches"), [UB inidisp_enable_display_mid_frame] (TEST: cleared in
  HBlank, sprite tiles corrupt or missing on the next line; cleared
  mid-line, BG and OBJ corruption on that line and missing OBJ on the
  next two lines). BG garbage for about 16-24 pixels after force blank
  is cleared mid-line, because the PPU fetches 2-3 tiles ahead [AN-T
  S-PPU RENDERING], [AN-R "2100"] (DOC). ares does not produce the BG
  garbage (its fetcher keeps running in force blank) (IMPL). Force blank
  keeps HDMA, NMI and IRQ running [FS "SNES PPU Control"] (DOC).
- **INIDISP brightness (bits 0-3).** Class P. Two analog effects are
  documented and are not reproduced by the digital oracles: the change
  is not instant (about 2.5 dots on a 3-chip console, 72 dots or more on
  a 1-chip) [WIKI Errata], [UB inidisp_brightness_delay] (DOC/TEST),
  and brightness 0 is not fully black [UB inidisp_brightness_0] (TEST).
  The "early read" glitch (about one dot rendered with the previous bus
  value when INIDISP is written during display) is probabilistic
  [WIKI Errata], [UB inidisp-early-read-glitch] (TEST). MAMR renders
  the written value from the write's pixel on (CHOICE, matches the
  oracle convention of 5.6).
- **SETINI.** Overscan (bit 2) moves vdisp to 240 at once; the visible
  height of the frame and the interlace state used for line counting
  are latched at V=0 [ARES ppu/main.cpp:2-4, ppu/io.cpp:642] (IMPL).
  Anomie measured the mid-frame behaviour: a change on line $E0 before
  the NMI point acts for the whole frame; clearing it at the start of
  line X ($E1 <= X <= $F0) gives NMI on line X and the last HDMA on X-1;
  setting it late has effect only on line $E1; VRAM locking follows the
  bit even when the picture does not [AN-R "2133"] (DOC). Interlace
  (bit 0) reaches the field timing through a latch that follows the
  register outside VBlank and holds from the start of VBlank to V=0: a
  write before V=vdisp shapes the running field, one in VBlank the next
  (DATASHEET + INFERENCE: Quietust's Visual 5C78/5C77 netlists; ares
  latches at V=128 [ARES ppu/counter/inline.hpp:20-25], IMPL;
  docs/snes-hardware-spec.md 2.1, 5.8).
  Pseudo hi-res (bit 3) and EXTBG (bit 6) are class P; OBJ interlace
  (bit 1) is class O. SETINI also has an early-read glitch [UB
  setini-early-read-obj, setini-early-read-mode7ex] (TEST, probabilistic,
  not modelled).
- **BGMODE.** The bit depths and the fetch pattern (7.3) are class F,
  the priority order class P. A mode change inside the fetch span of a
  line mixes fetch patterns; this is a dot fallback trigger (8.2).
- **OAMADDH bit 7 and OAMADD.** The rotation start (3.4) is derived when
  OAMADD is written or OAM data is accessed and latched at the start of
  each line [ARES ppu/object.cpp:6-9, 17] (IMPL).

### 1.5 Access rules during rendering

| Memory | Writable / readable when | During the rendering period otherwise | Class |
|---|---|---|---|
| VRAM | force blank, or V >= vdisp | writes ignored, reads give invalid data; the address still increments | DOC [WIKI PPU registers VMDATA, VMDATAREAD], [FS "SNES PPU Control"]; TEST [UB vram-mid-scanline-test] (result not published in the repo) |
| OAM | force blank, or V >= vdisp | the access goes to the address the sprite logic is using at that moment | DOC (address "invalidated" [AN-R "2102", SPRITES]); the exact address is IMPL |
| CGRAM | force blank, V = 0, V >= vdisp, or H outside [88, 1096) clocks | the access goes to the palette entry the compositor looked up last | IMPL [ARES ppu/io.cpp:47-61, ppu/dac.cpp:158-161]; DOC that it goes to "the wrong address" [WIKI PPU registers CGDATA]; no hardware test |

Details:

- VRAM: ares returns $0000 for a blocked read [ARES ppu/io.cpp:19-23]
  (IMPL). The block covers the whole line including HBlank [ARES
  ppu/io.cpp:20, 26] (IMPL) and line 0. Mesen-S found games that depend
  on the ignored write (Hook) and on the increment (Kick Off)
  [WIKI Tricky-to-emulate games] (CONS).
- OAM: ares redirects to the object it is evaluating or fetching: a
  low-table access goes to byte `obj*4 + (addr & 1)`, a high-table access
  to `$200 + obj/4` [ARES ppu/io.cpp:31-45, ppu/object.cpp:44, 103]
  (IMPL). The ares scanline renderer uses the fixed address $218 instead
  [ARES ppu-performance/io.cpp:31-39] (IMPL), which MAME also does as a
  hack for Uniracers. Uniracers is the known game [WIKI
  Tricky-to-emulate games] (CONS). fullsnes notes that Mario Kart turns
  on force blank to change OAM mid-screen [FS "SNES Timing PPU Memory
  Accesses"] (DOC). Writes in a force-blank period that began outside
  VBlank only work as expected if $2102/$2103 were written during that
  period [AN-R "2104"] (DOC).
- CGRAM: the window [88, 1096) is IMPL [ARES ppu/io.cpp:50, 58,
  ppu-performance/io.cpp:44, 52]; it matches the documented output span
  (88 to 1111, 7.2) at the left edge and the HBlank flag (1096) at the
  right. fullsnes knows of no exact CGRAM timing and reports that writes
  work at certain spots in HBlank only [FS "SNES Timing PPU Memory
  Accesses"] (DOC). HDMA to CGRAM at H=1104 is in the free window, which
  is what HDMA colour gradients rely on [UB hdma-to-cgram] (example
  ROM, self-checking).

### 1.6 Open bus (PPU1 and PPU2 MDR)

- **PPU1 MDR** is set by every read of $2134-$2136, $2138-$213A, $213E.
  It is returned in full by reads of the write-only addresses $21x4,
  $21x5, $21x6, $21x8, $21x9, $21xA for x = 0, 1, 2 (that is $2104-$2106,
  $2108-$210A, $2114-$2116, $2118-$211A, $2124-$2126, $2128-$212A), and
  in STAT77 bit 4 [FS "SNES Unpredictable Things"], [AN-R introduction],
  [AN-O] (DOC), the same list in [ARES ppu/io.cpp:68-74] (IMPL).
- **PPU2 MDR** is set by reads of $213B-$213D and $213F. It shows in
  $213B second read bit 7, $213C/$213D second read bits 1-7, and STAT78
  bit 5 [FS], [AN-R] (DOC). Reads update only the defined bits; the rest
  keep the MDR [AN-O] (DOC), [ARES ppu/io.cpp:128-155] (IMPL).
- All other PPU addresses ($21x0-$21x3, $21x7, $21xB-$21xF and $2137)
  return the CPU open bus value (the last byte on the data bus) [FS],
  [AN-R introduction] (DOC). This is the board's MDR
  (docs/snes-hardware-spec.md).
- Power-on value of both MDRs: not documented (fullsnes and Anomie are
  silent). ares draws them with a bias to $FF [ARES ppu/ppu.cpp:102,
  105], which aresref keeps with its zero-entropy option
  (docs/snes-oracle-format.md section 6). CHOICE: $FF, as aresref; a
  game that reads a write-only PPU register before any PPU read sees it
  in the cpu field. VMAIN bit 7, which ares also draws with a bias (to
  1) [ARES ppu/ppu.cpp:161], stays 0 (fill=00): it is no field and no
  program writes VRAM before setting VMAIN.

### 1.7 Where the register sources differ

| Point | Sources | Choice |
|---|---|---|
| Low 3 bits of BGnHOFS on write | Anomie: `(CurrentValue >> 8) & 7` [AN-R "210d"]; wiki and ares: a separate `bghofs_latch & 7`, loaded by HOFS writes only [WIKI PPU registers BGnHOFS], [ARES ppu/io.cpp:313] | wiki/ares: newer, two sources, and matches every game that writes both bytes |
| Name of STAT77 bits 6/7 | fullsnes and Anomie: bit 7 time over (> 34 tiles), bit 6 range over (> 32 sprites); the wiki labels the bits the same but swaps the explanations in parentheses [WIKI PPU registers STAT77] | fullsnes/Anomie |
| Overflow flag clear during force blank | fullsnes: not cleared during force blank; ares: always cleared at V=0 | fullsnes (CHOICE, test with [UB object-dropout-test] in force blank) |
| OAM reset trigger | Anomie/fullsnes: start of VBlank without force blank, or force blank cleared during line vdisp; byuu via Anomie: any 1-to-0 change of INIDISP bit 7 | first variant; the second is OPEN |
| Brightness 0 | fullsnes: "0 = screen black"; undisbeliever: not black on the console [UB inidisp_brightness_0]; ares: about 1/64 of full [ARES ppu/color.cpp:9] | oracle convention c*B/15 gives 0 (5.6); the analog level is outside the hash |
| MPY during Mode 7 display | fullsnes: shows matrix intermediates; wiki and ares: plain product | plain product, reads logged |

## 2. Backgrounds

### 2.1 Modes

| Mode | BG1 | BG2 | BG3 | BG4 | Notes |
|---|---|---|---|---|---|
| 0 | 2 bpp | 2 bpp | 2 bpp | 2 bpp | each BG has its own 32 colours: BGn uses CGRAM (n-1)*32 + pal*4 |
| 1 | 4 bpp | 4 bpp | 2 bpp | - | BG3 priority bit in BGMODE bit 3 |
| 2 | 4 bpp | 4 bpp | OPT | - | offset per tile from BG3's map |
| 3 | 8 bpp | 4 bpp | - | - | BG1 direct colour possible |
| 4 | 8 bpp | 2 bpp | OPT | - | one offset per column, H or V |
| 5 | 4 bpp | 2 bpp | - | - | 512 half-pixel hi-res, 16-pixel-wide tiles |
| 6 | 4 bpp | - | OPT | - | hi-res with OPT |
| 7 | 8 bpp | (EXTBG 7 bpp) | - | - | matrix transform, 128x128 map |

[FS "SNES PPU BG Control"], [AN-R BACKGROUNDS], [WIKI Backgrounds]
(DOC). Colour 0 of every palette is transparent [AN-R BACKGROUNDS]
(DOC). Palette base for a tile: mode 0: (BG-1)*32 + pal*4; 2 bpp in
other modes: pal*4; 4 bpp: pal*16; 8 bpp: 0, the palette bits are
ignored except for direct colour (2.9) [AN-R BACKGROUNDS Mode 0-6]
(DOC), [ARES ppu/background.cpp:111-113] (IMPL).

### 2.2 Priority

Front to back. Sn = sprites with OAM priority n; nH/nL = BGn tile
priority bit 1/0 [AN-R "2105"], [FS "SNES Picture Processing Unit"
priority chart], [WIKI PPU registers BGMODE] (DOC; the three tables
agree):

```text
Mode 0:            S3 1H 2H S2 1L 2L S1 3H 4H S0 3L 4L
Mode 1, bit3 = 0:  S3 1H 2H S2 1L 2L S1 3H    S0 3L
Mode 1, bit3 = 1:  3H S3 1H 2H S2 1L 2L S1    S0 3L
Modes 2-5:         S3 1H    S2 2H    S1 1L    S0 2L
Mode 6:            S3 1H    S2       S1 1L    S0
Mode 7:            S3       S2       S1 1     S0
Mode 7 + EXTBG:    S3       S2 2H    S1 1     S0 2L      (2H/2L = BG2 pixel bit 7)
backdrop behind everything
```

Implementation hint: give each (layer, priority) a rank per mode and
take the highest non-transparent rank per pixel; ares uses exactly
such per-mode rank tables [ARES ppu/io.cpp:641-743] (IMPL). Only the
frontmost sprite pixel takes part (3.4).

### 2.3 Name tables (tilemaps)

- A map is 32x32 entries of one word; BGnSC bits 0-1 give 1, 2 (wide),
  2 (tall) or 4 maps. Word address of the entry for tile column tx and
  row ty (counted in tiles of the layer's size) [AN-R BACKGROUNDS] (DOC):

```text
addr = SC_base + (ty & 31) * 32 + (tx & 31)
     + ((tx & 32) && X ? $400 : 0)
     + ((ty & 32) && Y ? (X ? $800 : $400) : 0)
```

- Entry: bits 0-9 character, 10-12 palette, 13 priority, 14 H flip, 15
  V flip [FS "SNES PPU Video Memory (VRAM)"] (DOC).
- Addresses wrap within the 32K-word VRAM [WIKI PPU registers] (DOC).

### 2.4 Character data and tile size

- Bit planes: 2 bpp = 8 words per 8x8 tile (word = plane 0 low byte,
  plane 1 high byte, one word per row); 4 bpp = 16 words (planes 2/3 in
  words 8-15); 8 bpp = 32 words. Bit 7 is the leftmost pixel [FS "SNES
  PPU Video Memory (VRAM)"], [AN-R BACKGROUNDS] (DOC).
- Character word address = NBA_base + char * (4 * bpp) + row, masked to
  the VRAM size [AN-R BACKGROUNDS] (DOC), [ARES
  ppu/background.cpp:104-109] (IMPL).
- 16x16 tiles (BGMODE bits 4-7, modes 0-4): the entry names the top-left
  8x8 tile; right half +1, lower half +16, with carry (tile $2FF gives
  $2FF, $300, $30F, $310; $3FF wraps to $000), flips mirror the whole
  16x16 block [AN-R BACKGROUNDS], [FS "SNES PPU Video Memory (VRAM)"]
  (DOC). Sprites do not carry (3.3).
- Modes 5/6 always use 16-pixel-wide tiles (in half-pixels: 16 per tile,
  8 normal pixels); BGMODE selects 16x8 or 16x16 [AN-R "2105"], [WIKI
  Backgrounds] (DOC). Mode 7 always 8x8.

### 2.5 Scrolling

- Pixel of BGn at screen (x, y): `bx = x + HOFS`, `by = y + VOFS`, both
  wrapped to the layer size, which is 256 << tile16 << X (horizontal) and
  256 << tile16 << Y (vertical), i.e. 256 to 1024 pixels. HOFS/VOFS are
  10 bits; values beyond the size wrap [AN-R "210f", BACKGROUNDS] (DOC),
  [ARES ppu/background.cpp:71-76] (IMPL).
- y is the scanline V (1..224). Because line 0 is rendered but never
  shown, VOFS = 0 hides the first BG row; games set VOFS = -1 (interlace:
  -2) [AN-R BACKGROUNDS "BG Scrolling"], [WIKI PPU registers "Scroll"]
  (DOC).
- Hi-res modes 5/6: horizontal scroll counts in normal pixels (2
  half-pixels); with interlace the vertical position is `2*V + field`
  and VOFS counts in half-lines [AN-R "210f"], [FS "SNES PPU Resolution"
  "Hires Notes"] (DOC), [ARES ppu/background.cpp:38-41] (IMPL).
- A mid-frame scroll change counts from the top-left of the screen, not
  from the line where it is written [WIKI PPU registers "Scroll"] (DOC):
  the renderer simply uses the current value for the current V.

### 2.6 Offset per tile (modes 2, 4, 6)

BG3 is not displayed; its name table supplies scroll values for BG1 and
BG2 per 8-pixel column [WIKI Offset-per-tile], [AN-R BACKGROUNDS Mode 2,
4, 6] (DOC):

- Entry format: bits 0-9 value; bit 13 applies to BG1; bit 14 to BG2;
  bit 15 (mode 4 only) 0 = horizontal, 1 = vertical.
- Two rows are read: the row at BG3's VOFS gives horizontal values, the
  row at VOFS + 8 gives vertical values (as if 8 were added to VOFS,
  possibly crossing into the next map). The row does not depend on the
  screen line. The column is `(screen column - 1) + (BG3HOFS >> 3)`;
  the low 3 bits of BG3HOFS/VOFS are ignored. Mode 4 reads one row only;
  its word is the vertical value when bit 15 is set. ares instead takes
  the vertical value from the second word, which it never fetches in
  mode 4 [ARES ppu/background.cpp:57-64, ppu/main.cpp:149-158] (IMPL);
  CHOICE: the documented single word, now with MEASURED support
  (2026-10-24): lidnariq's PPU bus trace (`cooked.csv` in
  higan/snes-test-roms, logic-analyzer clips on the VRAM chips of his
  console, 12 MHz samples, CSYNC plus the PPU address bus; his ROM
  `ppubusact.sfc` steps BGMODE through 0-6 in bands of 32 lines by HDMA,
  BG3SC = $78 so BG3's name table lies at word $7800) shows per line 33
  fetches from the BG3 name table in the mode 4 band against 66 in the
  mode 2 and mode 6 bands (and 33 plus the BG3 character fetches in
  modes 0 and 1): mode 4 fetches one offset word per column, so a
  vertical offset from a second word, as ares applies it, cannot come
  from the bus. What the single word means (bit 15 selects V) stays DOC.
  MAMR's picture of that ROM therefore differs from aresref in the mode 4
  band (rows 129-159) by design (docs/snes-oracles.md sections 10 and
  12.1).
- **Column rule:** the leftmost (partly visible) tile column of BG1/BG2
  is never affected; entry 0 applies to the second visible column, so
  33 columns can be covered [WIKI Offset-per-tile], [WIKI Errata], [AN-R
  BACKGROUNDS Mode 2] (DOC). In ares the offsets fetched in one column
  slot are used for the next column, and they start as 0 on each line
  [ARES ppu/background.cpp:17-18, 52-69, 123-148] (IMPL).
- Horizontal value replaces HOFS except its low 3 bits (fine scroll
  stays); vertical value replaces VOFS entirely.
- 16x16 tiles on BG3 make the H and V rows identical for even rows; mode
  6 treats BG3 entries as 16-half-pixel columns [WIKI Offset-per-tile]
  (DOC).
- Mesen-S lists wrap-around and implementation bugs in this logic that
  broke Chrono Trigger's menu and Axelay [WIKI Tricky-to-emulate games]
  (CONS).

### 2.7 Mode 1 BG3 priority

BGMODE bit 3 in mode 1 moves BG3 tiles with priority bit 1 in front of
everything (2.2). It has no effect in other modes [AN-R "2105"] (DOC).

### 2.8 Mode 7

**Memory.** VRAM words $0000-$3FFF: the low byte of word `ty*128 + tx`
is the map entry (character 0-255, no attributes) for the 128x128 map;
the high byte of word `char*64 + py*8 + px` is the 8-bit pixel
[FS "SNES PPU Video Memory (VRAM)"], [AN-R BACKGROUNDS Mode 7] (DOC).
BGnSC, NBA and the tile size bits are ignored [AN-R] (DOC).

**Registers.** M7A-D signed 1.7.8 fixed point (value/256); M7X, M7Y,
M7HOFS, M7VOFS signed 13-bit integers [AN-R "211b", "211f"], [FS "SNES
PPU Rotation/Scaling"] (DOC).

**Bit-exact transform** (Anomie's formula [AN-R "211f"], the same in
substance in [FS "SNES PPU Rotation/Scaling" "Formula"], DOC; the same
code structure in [ARES ppu/mode7.cpp:26-32], IMPL):

```text
CLIP(n) = (n & $2000) ? (n | ~$3FF) : (n & $3FF)     n = 13-bit difference
sy = V, minus the vertical mosaic offset if BG1 mosaic is on (6.3)
if M7SEL.Y: sy = 255 - sy        (8-bit flip)
X0 = ((A * CLIP(HOFS - CX)) & ~63) + ((B * CLIP(VOFS - CY)) & ~63)
   + ((B * sy) & ~63) + (CX << 8)
Y0 = ((C * CLIP(HOFS - CX)) & ~63) + ((D * CLIP(VOFS - CY)) & ~63)
   + ((D * sy) & ~63) + (CY << 8)
for screen x = 0..255:
    sx = M7SEL.X ? 255 - x : x
    PX = (X0 + A * sx) >> 8          (arithmetic shift)
    PY = (Y0 + C * sx) >> 8
```

The per-pixel steps A*sx and C*sx are not rounded; only the four
origin products are truncated to multiples of 64 [AN-R "211f"] (DOC).
fullsnes writes the origin clip as "AND NOT $1C00, OR $1C00 if
negative", which is the same mapping onto a sign-extended 10-bit range
for 13-bit inputs (CHOICE: Anomie's CLIP, matching ares).

**Map lookup and screen over (M7SEL bits 6-7):**

```text
out = (PX | PY) & ~$3FF           (outside 1024x1024)
tile = (R == 1 and F == 1 and out) ? 0 : map[(PY >> 3) & 127][(PX >> 3) & 127]
pix  = (R == 1 and F == 0 and out) ? 0 (transparent)
                                   : chr[tile][PY & 7][PX & 7]
```

R=0 wraps within the 1024x1024 field (M7SEL value 1 behaves like 0);
R=1, F=0 transparent outside; R=1, F=1 character 0 outside, still
transformed [FS], [AN-R "211a"], [WIKI PPU registers M7SEL] (DOC),
[ARES ppu/mode7.cpp:39-42] (IMPL).

**Flip** mirrors the 256x256 screen, not the tiles; Mode 7 has no
per-tile flip [FS "SNES PPU BG Control"] (DOC).

**EXTBG** (SETINI bit 6, mode 7 only): BG2 is the same pixel as BG1 with
bit 7 as priority (2.2) and bits 0-6 as colour (CGRAM index 0-127);
BG2 uses the Mode 7 registers, not BG2HOFS. In modes 0-6 EXTBG shows
garbage [FS "EXTBG"], [AN-R "2133", BACKGROUNDS Mode 7], [WIKI
Backgrounds EXTBG] (DOC). Expected results: rainwarrior's extbgtest
(no licence, not distributed).

**Timing.** The transform state is per line; mid-line writes are class
P in ares (it reads the registers per pixel [ARES ppu/mode7.cpp:2-10])
(IMPL), while Mesen-S latches the scroll offsets at the start of the
line (NHL '94 needs it) [WIKI Tricky-to-emulate games] (CONS). The two
disagree only for mid-line writes; see 8.

### 2.9 Direct colour

CGWSEL bit 0 with an 8-bpp BG1 (modes 3, 4, 7): pixel value `BBGGGRRR`
plus the tile's palette bits `bgr` give the colour
`R = RRRr0, G = GGGg0, B = BBb00` (5 bits each); value 0 stays
transparent [FS "SNES PPU Color Palette Memory"], [AN-R BACKGROUNDS
"Direct Color Mode"] (DOC):

```text
r   = ((p & 7) << 2)        | ((pal & 1) << 1)
g   = (((p >> 3) & 7) << 2) | (pal & 2)
b   = (((p >> 6) & 3) << 3) | (pal & 4)
c15 = r | (g << 5) | (b << 10)
```

(red bits 4-2 from p bits 2-0 and bit 1 from pal bit 0; green bits 4-2
from p bits 5-3 and bit 1 from pal bit 1; blue bits 4-3 from p bits
7-6 and bit 2 from pal bit 2; all other bits 0.) Mode 7 has no palette
bits, so `bgr = 0` there; EXTBG BG2 never uses direct colour [AN-R],
[WIKI Backgrounds EXTBG] (DOC), [ARES ppu/dac.cpp:163-170,
ppu/mode7.cpp:57] (IMPL). Mesen-S found a wrong Mode 7 direct colour
in Aerobiz [WIKI Tricky-to-emulate games] (CONS).

## 3. Sprites (OBJ)

### 3.1 OAM layout

544 bytes. Low table: 128 records of 4 bytes `X(0-7), Y, char(0-7),
attr`; attr = `VHPP CCCN`: V/H flip, PP priority 0-3, CCC palette (CGRAM
128 + CCC*16), N character bit 8 (name table select). High table: 32
bytes, 2 bits per sprite (sprite n in byte n/4, bits 2*(n&3) = X bit 8,
2*(n&3)+1 = size) [FS "SNES PPU Sprites (OBJs)"], [AN-R SPRITES OAM],
[WIKI Sprites OAM] (DOC). X is 9-bit signed (-256..255); Y is 8 bits and
wraps (a sprite at Y >= 240 comes in at the top) [AN-R SPRITES] (DOC).

### 3.2 Sizes

OBSEL bits 5-7 select the pair; the OAM size bit picks small (0) or
large (1) [FS "SNES PPU Sprites"], [AN-R "2101"], [WIKI PPU registers
OBJSEL] (DOC):

| S | small | large |
|---|---|---|
| 0 | 8x8 | 16x16 |
| 1 | 8x8 | 32x32 |
| 2 | 8x8 | 64x64 |
| 3 | 16x16 | 32x32 |
| 4 | 16x16 | 64x64 |
| 5 | 32x32 | 64x64 |
| 6 | 16x32 | 32x64 |
| 7 | 16x32 | 32x32 |

Quirks of the undocumented sizes 6 and 7:

- With OBJ interlace (SETINI bit 1) a 16x32 small sprite of S = 6 or 7
  is treated as 16x16 (the lower half is ignored, the upper half squashed
  to 16x8); 32x64 behaves normally [WIKI Errata] (DOC, forum report),
  [ARES ppu/oam.cpp:67] (IMPL: small height 16 when interlace and S >= 6).
- Vertical flip of a rectangular sprite flips the two square halves
  independently (rows 01234567 become 32107654) [AN-R SPRITES], [WIKI
  Errata] (DOC), [ARES ppu/object.cpp:111-119] (IMPL).

With OBJ interlace every sprite is drawn at half height: the row used is
`2*(line - Y) + field` [FS "SNES PPU Control" SETINI], [ARES
ppu/object.cpp:53, 109, 121-123] (IMPL for the formula).

### 3.3 Character address

```text
word address of row r (0-7) of the 8x8 tile in sprite column cx, row cy:
  c    = OAM character byte (char bits 0-7)
  col  = ((c & $0F) + cx) & $0F
  row  = ((c >> 4) + cy) & $0F
  base = OBSEL bBB << 13;  name = OBSEL NN
  addr = (base + (N ? (name + 1) << 12 : 0) + (row * 16 + col) * 16 + r) & $7FFF
  planes 0/1 at addr, planes 2/3 at addr + 8
```

The character grid is 16x16 tiles per name table and wraps in both
directions without carry (tile $FF of a 16x16 sprite gives $FF, $F0,
$0F, $00) [AN-R SPRITES "Character table in VRAM"], [FS "SNES PPU Video
Memory (VRAM)"] (DOC), [ARES ppu/object.cpp:128-147] (IMPL). Horizontal
flip reverses the column order and the pixels within each tile.

### 3.4 Priority among sprites and rotation

- Sprite-to-sprite order: the sprite with the lowest index, counted from
  the first sprite, is in front; only the frontmost non-transparent
  sprite pixel competes with the BGs, with its own priority (a low-index
  sprite with priority 0 hides a higher-index sprite with priority 3
  behind a BG) [AN-R SPRITES "Sprite Priority"], [WIKI Sprites] (DOC).
- First sprite: 0 if OAMADDH bit 7 = 0, else `(internal address >> 2) &
  127`, i.e. (OAMADD word address >> 1) & 127, taken from the internal
  address as left by the last OAMADD write and OAM data accesses (not by
  the rendering invalidation) [AN-R SPRITES], [WIKI PPU registers
  OAMADD] (DOC), [ARES ppu/object.cpp:6-9] (IMPL). After the OAM reset at
  VBlank the value follows the reloaded address.
- Anomie's oddity: after writing OAMADD = A and then 4n + 2*(A&1) + 1
  bytes, the first sprite is ((addr >> 1) + Y) & 127 with Y the current
  sprite line [AN-R SPRITES] (DOC); not modelled by ares (IMPL), OPEN.
- Super Mario World needs the rotation [WIKI Tricky-to-emulate games]
  (CONS).

### 3.5 Per-line evaluation (range) and tile fetch (time)

The process for the sprites drawn on line N+1 runs during line N
[AN-T "DETAILED RENDERER TIMING"], [AN-R SPRITES "Drawing the Sprites"],
[WIKI Sprites "Rendering"] (DOC), confirmed on hardware by
undisbeliever's object-dropout-test [WIKI Sprites references], [UB
object-dropout-test] (TEST):

1. **Range.** Starting at the first sprite, walk all 128 sprites in
   index order (wrapping 127 to 0). A sprite is in range when line N is
   within `[Y, Y + height)` modulo 256 (height halved with OBJ interlace)
   and it is horizontally on screen: `-width < X < 256`, where a sprite
   with X = 256 (written as -256, $100) counts as being at X = 0 for this
   test. The first 32 in range are kept. If a 33rd is found, set STAT77
   bit 6 (range over); later sprites are dropped. fullsnes: the flag is
   set at "V = Y, H = index*2 dots" [FS "SNES PPU Timers and Status"]
   (DOC); ares evaluates one sprite every 8 clocks from H = 0 to 1016
   [ARES ppu/main.cpp:214, ppu/object.cpp:35-55] (IMPL).
2. **Time.** Take the kept sprites in reverse order (last kept first).
   For each, add its 8-pixel slivers on the line from left to right (in
   screen order, also when flipped). A sliver counts only if `-8 < x <
   256`, except that all slivers of a sprite at X = 256 count. After 34
   slivers set STAT77 bit 7 (time over) and drop the rest. Because of the
   reverse order the frontmost (lowest index) sprites lose slivers first,
   and within a sprite the rightmost slivers [AN-R SPRITES], [WIKI
   Sprites], [WIKI Errata] (DOC), [UB object-dropout-test] (TEST),
   [ARES ppu/object.cpp:95-160] (IMPL). Flag timing per fullsnes: bit 7
   set at "V = Y+1, H = 0" (DOC).
3. **Fetch.** Each kept sliver costs two VRAM words (4 bpp). The slivers
   are fetched in HBlank: ares from H = 1080 to at most 1352, 8 clocks
   per sliver [ARES ppu/main.cpp:92-95, ppu/object.cpp:150-155] (IMPL);
   Anomie: 68 memory slots for 34 slivers in HBlank (DOC); lidnariq's bus
   trace: 33 BG slivers (264 slots), 8 idle, 34 OBJ slivers (68 slots)
   (DOC, forum measurement).
4. **Draw** on line N+1 from the second buffer: slivers drawn with the
   lowest index in front; palette index 0 is transparent [ARES
   ppu/object.cpp:57-89] (IMPL).

Consequences for the renderer:

- A sprite with Y = n appears from line n+1 on (sprites are "one line
  lower than their Y") [WIKI Sprites OAM] (DOC). Line 0 is evaluated so
  that line 1 has sprites; the evaluation of the last visible line feeds
  the (invisible) line vdisp.
- Flags are set even if OBJ is disabled in TM and TS [AN-R "213e"] (DOC).
- The evaluation uses OAM, OBSEL size and SETINI bit 1 during line N;
  the fetch uses OBSEL base/name and OAM again in HBlank of N. A change
  of these between the two (an HDMA write at H=1104 is inside the fetch
  window) gives mixed results (section 8).
- Force blank during line N (any part of the evaluation or fetch window)
  leaves line N+1 without (or with partial) sprites (1.4).
- The SNES development manual reports a spurious time over with a large
  first sprite at X 0-255 and others at negative X [WIKI Errata] (DOC,
  unspecified); not modelled, OPEN.

### 3.6 Rendering switched off mid-frame

What is documented (and nothing more is claimed):

- Force blank set and cleared inside the frame: sprite and BG garbage as
  in 1.4; OAM writes in such a period go to a wrong address unless
  OAMADD is rewritten after force blank began [AN-R "2104"] (DOC).
- OAM reset at VBlank is skipped when force blank is on at V = vdisp, so
  a game that turns force blank on before VBlank keeps the internal
  address it left (1.3) (DOC).
- [UB inidisp_forgot_to_force_blank] uploads VRAM/OAM/CGRAM at line 40
  without force blank (TEST ROM; the expected corruption is shown on
  screen, results on undisbeliever.net). OAM writes then land on the
  evaluated sprite (IMPL, 1.5), CGRAM writes on the palette entry being
  drawn (IMPL, 1.5): "palette corruption".
- No document describes a corruption of OAM content caused by switching
  force blank alone (without writes). S6 does not model one (CHOICE).

## 4. Windows

[FS "SNES PPU Window"], [AN-R "2123"-"212f", WINDOWS], [WIKI Windows]
(DOC).

- Two windows, each with left L and right R (0-255). Window n is "in" at
  screen x when `L <= x <= R`; L = R gives one pixel; L > R gives an empty
  window (with invert: everywhere).
- Per layer (BG1-4, OBJ, colour) and window: enable bit and invert bit.
  Disabled window: contributes nothing (invert has no effect).
- Combination per layer: no window enabled = 0 (not masked); one enabled
  = that window (inverted if set); both = `w1 op w2` with op from
  WBGLOG/WOBJLOG: 0 OR, 1 AND, 2 XOR, 3 XNOR (= not XOR), applied after
  the inversions.
- The result masks the layer on the main screen if its TMW bit is set
  and on the sub screen if its TSW bit is set (a masked pixel is
  transparent for that screen). For the colour window the result feeds
  CGWSEL (5.3).
- Mode 7 layers are masked like the others (Mesen-S found Atlas and
  MechWarrior broken without it) [WIKI Tricky-to-emulate games] (CONS).
- Hi-res: window positions are in full pixels; in pseudo hi-res the sub
  screen half-pixel is masked when the main pixel to its left is masked
  [AN-R "2133"], [FS "SNES PPU Resolution"] (DOC; "odd glitch" reported,
  not specified).

**Edge rule for mid-line writes.** ares does not compare ranges; it
keeps two flags per window, sets "active" when x == L and "stopped"
after x == R, and tests `active and not stopped` [ARES
ppu/window.cpp:7-15] (IMPL). For a constant line this equals `L <= x <=
R` including L = R (one pixel) and L > R (empty). It differs only when
WHx is written while the line is drawn: a new L below the current x
never starts the window, a new R below x cannot stop it. The ares
scanline renderer uses the range compare [ARES
ppu-performance/window.cpp:1-38] (IMPL). CHOICE: range compare per segment, plus the dot fallback
when a WHx write moves an edge across the current pixel (8.2). The
hardware behaviour is OPEN.

## 5. Colour math and output

### 5.1 Main and sub screen

For every pixel the PPU determines two pixels by priority (2.2) [FS
"SNES PPU Color-Math"], [AN-R RENDERING THE SCREEN] (DOC):

- **Main pixel**: the frontmost non-transparent pixel of the layers
  enabled in TM and not masked by TMW windows; else the backdrop
  (CGRAM entry 0). It remembers its source layer.
- **Sub pixel**: the same with TS/TSW; else "transparent", which means
  the fixed colour (COLDATA) acts as the addend. In hi-res (modes 5/6
  and pseudo hi-res) a transparent sub pixel shows CGRAM entry 0 instead
  [FS "SNES PPU Resolution" "Hires Notes"] (DOC), [ARES
  ppu/dac.cpp:71] (IMPL).
- Fixed colour: COLDATA writes set the selected channels to the
  intensity; the three channels are independent registers [FS "SNES PPU
  Color-Math" 2132h], [WIKI PPU registers COLDATA] (DOC).

### 5.2 Math enable per main pixel

Math is applicable if the main pixel's source has its CGADSUB bit: BG1-4
(bits 0-3), OBJ (bit 4, only for sprite palettes 4-7, CGRAM 192-255),
backdrop (bit 5) [FS], [AN-R "2131", RENDERING THE SCREEN], [WIKI Color
math "Masking"] (DOC). On the sub screen sprites of all palettes count
as a normal source [WIKI Sprites] (DOC).

### 5.3 Colour window: clip to black and prevent math

Let W be the colour window result (4) at x (W = 0 if no colour window
is enabled, so "outside" everywhere [WIKI PPU registers CGWSEL]):

```text
region(v) : 0 = never, 1 = where W = 0 (outside), 2 = where W = 1 (inside), 3 = always
clip    = region(CGWSEL bits 6-7)    main colour becomes black (0)
prevent = region(CGWSEL bits 5-4)    no math
```

[FS "SNES PPU Color-Math"] (DOC: "3 = always, 2 = math window, 1 = not
math window, 0 = never" for both fields), [AN-R "2130"] (DOC: "01
outside color window only, 10 inside"), [WIKI PPU registers CGWSEL]
(DOC). The three sources agree once fullsnes' "MathWindow" is read as
"inside". ares encodes the same with the table {always, W, not W,
never} for "main colour kept" and "math allowed" [ARES
ppu/window.cpp:42-45] (IMPL).

### 5.4 The operation

```text
main  = clip ? 0 : colour of the main pixel
if prevent or not math_enabled(main source):
    out = main
else:
    if CGWSEL.1 (addend = sub screen) and sub pixel not transparent:
        addend = sub colour;   half = CGADSUB.6
    elif CGWSEL.1 and sub pixel transparent:
        addend = fixed colour; half = 0          (backdrop exception)
    else:
        addend = fixed colour; half = CGADSUB.6
    if clip: half = 0
    per channel r, g, b (5 bit):
        v = CGADSUB.7 ? main - addend : main + addend
        if half: v = v >> 1        (sum >> 1; for subtraction clamp first)
        out = clamp(v, 0, 31)
```

Sources: add or subtract per channel, optional halving, saturation to
0..31 [FS "SNES PPU Color-Math"], [WIKI Color math "Blend operations"]
(DOC). Halving is skipped when the sub screen is the addend but the sub
pixel is transparent (fixed colour used), and when the main colour is
clipped: [FS 2131h: half-colour is ignored with Force Main Screen
Black, "also ignored on transparent subscreen pixels"], [AN-R
"2131", RENDERING THE SCREEN "Color Math" table], (DOC), [ARES
ppu/dac.cpp:120-135] (IMPL). With addend = fixed colour (CGWSEL.1 = 0)
the halving does apply ([FS 2132h] "one exception", DOC). For
subtraction, halving after clamping to 0 equals halving before, since a
negative result clamps to 0 either way; the bit-parallel formula of ares
does exactly that [ARES ppu/dac.cpp:138-156] (IMPL).

Clip with math still allowed adds to black: "colour addition can still
be applied" [FS "Force Main Screen Black"] (DOC). Snes9x 1.43 and ZSNES
get this wrong [WIKI PPU registers CGWSEL] (DOC), so the region bits are
a known trap.

### 5.5 Hi-res and pseudo hi-res

- Modes 5/6 and SETINI bit 3 produce 512 half-pixels per line: even
  half-pixel = sub screen, odd = main screen [WIKI PPU registers SETINI],
  [AN-R "2133"] (DOC), [ARES ppu/dac.cpp:34-40] (IMPL). Mode 5/6 BGs put
  their even half-pixels on the sub screen and odd ones on the main
  screen, so TM and TS usually hold the same layers [AN-R BACKGROUNDS
  Mode 5] (DOC).
- Colour math in hi-res also applies to the sub half-pixel: it uses the
  decision of the previous (left) main pixel; if that pixel had no math,
  none; if it added/subtracted the fixed colour, the same; if it used the
  sub screen, the sub half-pixel is combined with the original (pre-math)
  main colour of that pixel [AN-R RENDERING THE SCREEN "Color Math"]
  (DOC), [ARES ppu/dac.cpp:43-80] (IMPL). Jurassic Park depends on it
  [WIKI Tricky-to-emulate games] (CONS).
- The first sub half-pixel of a line: unknown [AN-R "Unresolved Issues"]
  (OPEN); ares starts the line with "no math" and CGRAM 0 [ARES
  ppu/dac.cpp:18-28] (IMPL). CHOICE: as ares.
- fullsnes: "Mode 5/6 don't support screen addition/subtraction" [FS
  "SNES PPU BG Control"]; Anomie, ares and the hi-res math above say
  they do. CHOICE: math applies (Anomie, ares).

### 5.6 Master brightness and the output word

- The PPU2 scales the RGB output by brightness B: "Brightness*(N+1)/16",
  0 = black [FS "SNES PPU Control"] (DOC), linear steps [WIKI PPU
  registers INIDISP] (DOC); analog deviations in 1.4.
- Force blank outputs black regardless of CGRAM, COLDATA and B; the TV
  border is always black [FS "SNES PPU Color Palette Memory" "Forced
  Blank Color", "Screen Border Color"] (DOC).
- MAMR's output word per half-pixel is the BGR555 colour after colour
  math plus the 4-bit brightness in force (ares does the same, `B << 15 |
  colour` [ARES ppu/dac.cpp:39-40]) (IMPL). The oracle picture applies
  `channel * B / 15` (integer division) and 0 in force blank
  (docs/snes-oracle-format.md section 5, CHOICE of the oracle format).
  The analog scale `(B+1)/16` is only for display.

## 6. Mosaic

[AN-R "2106", RENDERING THE SCREEN "Mosaic"], [FS "SNES PPU BG
Control" 2106h] (DOC).

### 6.1 Size and horizontal blocks

- Size s = MOSAIC bits 4-7 plus 1 (1..16). For each enabled BG, every
  s x s block shows the top-left pixel of the block. Horizontally the
  first block starts at screen x = 0 on every line; scrolling does not
  move the blocks.
- Mosaic acts after scrolling and before windows, colour math and hi-res
  interleave, so a block can be partly clipped or mathed [AN-R "2106"]
  (DOC). Sprites are never mosaicked.
- Hi-res modes 5/6: blocks are 2s half-pixels wide (s = 1 already merges
  each pair of half-pixels); with interlace 2s half-lines high. Pseudo
  hi-res: normal [AN-R "2106", "2133"], [FS "SNES PPU Resolution"]
  (DOC).
- Mode 7: BG1 as usual, in screen space; EXTBG BG2 uses BG1's enable
  bit for the vertical and its own bit for the horizontal mosaic
  [AN-R "2106", RENDERING THE SCREEN] (DOC), [ARES ppu/mode7.cpp:12-21]
  (IMPL).

### 6.2 Vertical counter over the frame

- Vertically a block covers s lines; for a line in a block the BG is
  rendered as if V were the first line of the block, i.e. the vertical
  index inside the block is subtracted from VOFS [FS 2106h] (DOC). For
  Mode 7 the same offset is subtracted from the transform's sy (2.8).
- Start line: the first visible line (V = 1) of the frame
  [AN-R "2106"], [FS 2106h] (DOC).
- Mid-frame changes: fullsnes: after a mid-frame size change the
  hardware completes the current block with the old vertical size and
  only then uses the new one (DOC, paraphrased). Anomie: writing
  $2106 mid-frame makes the current line the start of a new block, but
  writing the same value does not, and which changes do is unknown
  (DOC, marked "XXX"). ares: a down-counter reloaded with the current
  size whenever it runs out, restarted at V = 1 and when mosaic goes from
  all-disabled to enabled; the offset is the current size minus the
  counter [ARES ppu/mosaic.cpp:9-21, ppu/io.cpp:252-264] (IMPL).

With a constant size the three agree. After a size change inside a
block they do not: ares keeps counting the old block down but computes
the offset with the new size, which neither finishes the block with the
old size (fullsnes) nor starts a new one (Anomie). Example: size 8,
changed to 2 in the HBlank of line 2 (VOFS 0); ares gives line 3 the
offset 2 - 6 = -4 and shows BG row 7, fullsnes would show row 1, Anomie
row 3.

CHOICE: ares (IMPL), as the primary oracle; the documented variants are
OPEN until an oracle or test ROM decides (the FF VI and Chrono Trigger
mosaic transitions of section 9 are the scenes to compare):

```text
at the start of line 1:      counter = enabled ? s + 1 : 0
at the start of every line:  if counter > 0: counter -= 1, and if it
                             reaches 0: counter = enabled ? s : 0
on a $2106 write that enables mosaic while all BGs were disabled:
                             counter = s + 1
vertical offset (unsigned 32 bit) = s - counter, s = the current size
BG row used = V + VOFS - offset; Mode 7 sy = V - offset (2.8)
```

"enabled" means any BG enable bit set.

## 7. Time skeleton of the PPU

Clocks are master clocks inside the line (H = 0..1363). Board side:
docs/snes-hardware-spec.md section 2.

### 7.1 Line, dots, long dots

- A line has 1364 clocks; the H/V latch counts 340 dots (0-339). Two
  descriptions of the 4 extra clocks exist:
  - **Variant A**: dots 323 and 327 last 6 clocks, all others 4 [AN-T
    S-PPU RENDERING] (DOC), [ARES ppu/counter/inline.hpp:61-77] (IMPL);
    fullsnes' own latch statistics show H=323 and H=327 six times as
    often as other values, i.e. 6 clocks each [FS "SNES Timing H/V
    Events" "PPU H-Counter-Latch Quantities"] (DOC).
  - **Variant B**: four dots of 5 clocks [FS "SNES Timing H/V Counters"],
    [WIKI Timing] (DOC); fullsnes also calls 323 and 327 "long PPU dots
    but not long CPU dots".
  - CHOICE: variant A for the latch (as docs/snes-hardware-spec.md 2.1).
    For the renderer the choice does not matter: both long dots lie in
    HBlank after the last pixel and the sprite fetch.
  - Clock to dot, variant A, on a 1364-clock line:
    `dot = (H - 2*(H > 1292) - 2*(H > 1310)) >> 2`; on the short line
    `dot = H >> 2` [ARES ppu/counter/inline.hpp:71-77] (IMPL).
- Short line: NTSC, interlace off, field 1, V = 240: 1360 clocks, all
  dots 4 clocks; long line: PAL, interlace on, field 1, V = 311: 1368
  clocks [FS "SNES Timing H/V Counters"], [WIKI Timing] (DOC). Both are
  in VBlank and do not affect the picture.

### 7.2 Frame and visible area

| Item | Value | Source |
|---|---|---|
| lines | 262 NTSC (263 in field 0 with interlace), 312 PAL | DOC [FS "SNES Timing H/V Events"] |
| line 0 | rendered (fetches, sprite evaluation) but never output | DOC [AN-T DETAILED RENDERER TIMING], [WIKI Timing] |
| visible lines | 1-224, 1-239 with overscan | DOC |
| VBlank | from V = 225 (240), H = 0, to V = 0 H = 0 | DOC [AN-T BLANKING PERIODS] |
| HBlank flag | set at dot 274 (H = 1096), cleared at dot 1 (Anomie); the board reads it as H <= 2 or H >= 1096 clocks | DOC [AN-T REGISTERS], IMPL [ARES cpu/io.cpp:35], docs/snes-hardware-spec.md 2.5 |
| output pixels | dots 22-277, H = 88 to 1111, 4 clocks per pixel | DOC [AN-T S-PPU RENDERING], [WIKI Timing] ("left edge at clock 88 until 1112"), [AN-R "213c"] |
| overscan and interlace for the frame | latched at V = 0 | IMPL [ARES ppu/main.cpp:2-4] |
| field flag | toggles at V = 0 | DOC [FS "H/V Events"] |

Interlace: in field 1 the lines are shifted down half a line; only modes
5/6 render double vertical resolution (2.5), OBJ interlace halves sprite
height (3.2), other modes just jitter [WIKI PPU registers SETINI], [AN-R
"2133"] (DOC). The oracle picture keeps only the current field.

### 7.3 Pipeline: fetches and pixel output

The documents describe the order, ares gives positions (IMPL):

- **BG fetch.** 33 tile columns per line, 8 VRAM slots of 4 clocks per
  column, from H = 0 to 1055 (264 slots) [ARES ppu/main.cpp:215], [AN-T
  DETAILED RENDERER TIMING] (DOC: the PPU loads the third tile while the
  first is output, 2-3 tiles ahead), lidnariq trace (DOC: 264 BG slots).
  Column k is fetched at H = 32k to 32k+31. Slot order per column
  [ARES ppu/main.cpp:107-183] (IMPL), with NT = name table word, Cn =
  character word n (two bit planes), OPT = BG3 offset entry:

```text
mode 0: NT4 NT3 NT2 NT1  C4 C3 C2 C1
mode 1: NT3 NT2 NT1 C3   C2a C2b C1a C1b
mode 2: NT2 NT1 OPTh OPTv C2a C2b C1a C1b
mode 3: NT2 NT1 C2a C2b  C1a C1b C1c C1d
mode 4: NT2 NT1 OPT C2   C1a C1b C1c C1d
mode 5: NT2 NT1 C2(l) C2(r)  C1a(l) C1a(r) C1b(l) C1b(r)
mode 6: NT2 NT1 OPTh OPTv C1a(l) C1a(r) C1b(l) C1b(r)
mode 7: map and pixel read per pixel (low and high VRAM chip)
```

  In ares the name-table slot decides everything about the column
  (scroll, map address, character address, palette, flip); the
  character slots only read VRAM [ARES ppu/background.cpp:27-121,
  150-170] (IMPL). Line 0 fetches but outputs nothing.
- **Pixel compose.** ares starts the BG pixel shifters at H = 56 (after
  dropping `HOFS & 7` pixels of column 0) and composes pixel x
  (0..255) at H = 56 + 4x (sub screen) and 58 + 4x (main screen, window,
  OBJ, colour math) [ARES ppu/main.cpp:216-219,
  ppu/background.cpp:22-25] (IMPL). The documented output of pixel x is
  at H = 88 + 4x (7.2). The 32 clocks between are the output pipeline;
  where in that span a register is sampled is not documented (OPEN).
- **Sprite evaluation.** Sprite i (counted from the first sprite) at
  H = 8i, i = 0..127, H = 0 to 1016 [ARES ppu/main.cpp:214] (IMPL);
  fullsnes: OAM step 1 takes 128 * 2 dots and sets the range flag at
  H = index*2 dots (DOC) - the same 8 clocks per sprite.
- **Sprite tile fetch.** H = 1080 to at most 1352, 8 clocks per sliver,
  slivers in the reverse order of 3.5 [ARES ppu/main.cpp:92-95] (IMPL);
  Anomie: 68 slots in HBlank (DOC).
- **Mode 7** per pixel, no column fetch; the origin is computed per line
  (2.8).

Calibration constants for S6 (one place in the code, CHOICE): `T_FETCH(k,
slot) = 32k + 4*slot`, `T_PIX(x) = 58 + 4x` (ares) with the alternative
`88 + 4x` (output); `T_EVAL(i) = 8i`; `T_OBJFETCH = 1080..1352`.
Section 10 names the test ROMs that decide them.

### 7.4 HDMA relative to rendering

- HDMA initialises at V = 0 (H = 12 or 16 in ares and MAMR's board,
  "H = 6" in fullsnes, docs/snes-hardware-spec.md 2.2)
  and transfers once per line for V = 0 .. vdisp-1 at H = 1104 (ares,
  [ARES cpu/timing.cpp:77]) or dot 278 = H 1112 (Anomie [AN-T HDMA],
  fullsnes "H=278") (docs/snes-hardware-spec.md 2.2 and its list of
  differences).
- Both positions are after the last composed pixel (ares 1078) and the
  last output pixel (1111) and after the CGRAM window (1096). HDMA
  writes in the HBlank of line N are therefore in force for the whole
  line N+1; the first table entry is written at the end of line 0 and
  applies to line 1 [UB hdma-timing-demonstration] (TEST ROM, source of
  the wiki diagram), [AN-T HDMA] (DOC). zelda3 applies HDMA in exactly
  this order (section 9).
- The HDMA span overlaps the sprite fetch (1080-1352): HDMA writes to
  OBSEL or SETINI bit 1 change the sprites of the next line partly
  (8.1). HDMA to VRAM and OAM during the rendering period is blocked or
  redirected (1.5).
- HDMA cost: about 18 clocks per line plus 8 per active channel, 16 per
  indirect address load, 8 per byte [AN-T HDMA] (DOC). With many
  channels and indirect mode the transfers run past H = 1363 into the
  next line, where the BG fetch of column 0 starts at H = 0: the late
  writes then hit fetch and compose of that line (8.2 trigger).

### 7.5 PAL (50 Hz)

The target ROMs on hand include PAL versions (the German ALttP, region
9, and the European Secret of Mana, region 2), so the runtime supports
both timings. Everything in sections 1 to 6 and 7.1 to 7.4 applies to
PAL unchanged except the points below.

| Item | NTSC | PAL | Source |
|---|---|---|---|
| master clock | 21.47727 MHz (6 x 3.579545 MHz colour carrier) | 21.28137 MHz (17.734475 MHz crystal x 6/5 = 4.8 x 4.43361875 MHz carrier) | DOC [FS "SNES Timing Oscillators"], [WIKI Timing]; IMPL [ARES system/system.cpp:77-83], ares/ares.hpp:66-67 |
| dot clock | master / 4 = 5.369 MHz | master / 4 = 5.320 MHz | DOC [FS "SNES Timing Oscillators"] |
| clocks per line | 1364 | 1364 | DOC [FS "SNES Timing H/V Counters"] |
| lines per field | 262; 263 in field 0 with interlace | 312; 313 in field 0 with interlace | DOC [FS "SNES Timing H/V Events"] ("V=262/312 extra scanline, only in interlace field 0"); IMPL [ARES ppu/counter/inline.hpp:20-33] |
| odd line length | short line: interlace off, field 1, V = 240, 1360 clocks | long line: interlace on, field 1, V = 311, 1368 clocks; no short line | DOC [FS "SNES Timing H/V Counters"], [WIKI Timing]; IMPL [ARES ppu/counter/inline.hpp:38-39] |
| dots on the odd line | 340 dots of 4 clocks | 341 dots (0-340), the latch can return H = 340 | DOC [FS "SNES Timing H/V Counters", "PPU H-Counter-Latch Quantities"]; ares: "it is not known what happens for PAL 1368 clock scanlines" [ARES ppu/counter/inline.hpp:66] |
| clocks per field | 357368 / 357364 alternating without interlace | 425568 (312 x 1364) without interlace; with interlace field 0 = 313 x 1364 = 426932, field 1 = 312 x 1364 + 4 = 425572 | DOC [FS "SNES Timing Oscillators", "Long and Short Scanlines (Purpose)"]; the field split follows the event list of [FS "H/V Events"] and ares (see below) |
| field rate | 60.0988 Hz | 50.00698 Hz | DOC [FS "SNES Timing Oscillators"] |
| VBlank start | V = 225, 240 with overscan | the same: V = 225, 240 with overscan | DOC [FS "SNES Timing H/V Events"], [WIKI Timing]; IMPL [ARES ppu/io.cpp:642] |
| VBlank length | 37 lines (22 with overscan) | 87 lines (72 with overscan) | DOC [WIKI Timing] |
| visible lines | 1-224 (1-239) | 1-224 (1-239); a PAL TV shows about 264 lines, so both modes have black borders | DOC [FS "SNES PPU Resolution", "Screen Border Color"] |
| STAT78 bit 4 | 0 | 1 (PPU2 pin 30) | DOC [FS "SNES PPU Timers and Status"], [WIKI PPU registers STAT78]; IMPL [ARES ppu/io.cpp:171] |
| PPU chip versions | PPU1 1, PPU2 1-3 | the same chips; no PAL-specific register behaviour documented | DOC [FS], [AN-R "213f"] |

fullsnes' summary table gives the interlaced PAL value as one number,
426936 = 313 x 1364 + 4, which combines the extra line and the long
line in one field, while its own event list puts the extra line in
field 0 and the long line in field 1 [FS "Long and Short Scanlines
(Purpose)", "H/V Events"]. ares follows the event list (extra line when
interlace is latched with field 0 at V = 128, long line in field 1 at
V = 311) [ARES ppu/counter/inline.hpp:20-39]. CHOICE: the event list,
with the interlace bit latched at the start of VBlank (the netlists,
docs/snes-hardware-spec.md 5.8): the S-PPU1's field length mux, the
NTSC short line and the PAL long line read only the latched bit.
The two descriptions agree on the length of a field pair (852504
clocks). fullsnes also reports a picture glitch of the long line: the
first visible lines of an interlaced PAL picture are shifted right by
about one pixel [FS "Long and Short Scanlines"] (DOC, analog, not
modelled).

**What changes in the renderer for PAL:**

- Nothing in the picture logic: same registers, same 1364-clock line
  with the same fetch, compose and sprite schedule (7.3), same VBlank
  start, same visible lines. The extra VBlank lines 241-311 are idle for
  the PPU [ARES ppu/main.cpp:55-58] (IMPL).
- The line counter wraps at 312 (313); the odd line is the long line in
  VBlank (no effect on the picture). The CGRAM window, the OAM reset and
  the force-blank rules use vdisp, which is the same.
- STAT78 returns bit 4 = 1.
- Longer VBlank: games may upload more per frame, and DMA that ran past
  VBlank on NTSC (a section 8 fallback case) usually ends in VBlank on
  PAL.
- Output framing only: ares places the PAL picture 20 lines lower in its
  288-line buffer and 4 half-pixels further left [ARES ppu/dac.cpp:6-15,
  ppu/ppu.hpp:79, ppu/main.cpp:36-45] (IMPL); this is presentation, not
  part of the oracle picture, which always holds lines 1-224 (1-239)
  (docs/snes-oracle-format.md section 5).
- Oracle runs: aresref selects "[Nintendo] Super Famicom (PAL)" [ARES
  system/system.cpp:6-11, 80-83] (IMPL); the sampling clock of each
  frame, with the field lengths of both regions, is defined in
  docs/snes-oracle-format.md.
- Game scope: section 9.1 was derived from zelda3, which reimplements
  the US version. Whether the German PAL version writes other PPU values
  (for example SETINI overscan, or adapted HDMA tables) is unproven and
  is checked by comparing the `ppu` write-shadow field of the oracle
  lines of both versions.

## 8. What is correct per line, and what needs dots

### 8.1 Effects

"Line" = render the line in one piece with the state at its start;
"segment" = split the line at the pixel or column where a write takes
effect (classes P/F of 1.1) and render each piece with its state; "dot" =
run the stage E dot renderer for this line.

| Effect | Class | Rule |
|---|---|---|
| any PPU register written by HDMA at H = 1104 / 1112 (scroll, mode, windows, colour math, COLDATA, Mode 7 matrix, INIDISP brightness, TM/TS, MOSAIC) | line | state for line N+1 = state after HDMA of line N plus CPU writes before the line's first use; Mode 7 origin per line |
| CGRAM written by HDMA or CPU at H >= 1096 or H < 88 | line | outside the CGRAM window; normal write |
| VRAM write during the rendering period | line | ignored, address still increments (1.5) |
| OAMADD write (priority rotation) | line | the first sprite is latched at the line start (3.4) |
| sprite range/time limits and STAT77 flags | line | per line from OAM as it was during evaluation (3.5); flags OR-ed over the frame |
| force blank for whole lines, toggled in HBlank (H >= 1096) | line, with the sprite rule | line N+1 has no sprites if force blank was on during the evaluation or fetch of line N (1.4); BG unaffected |
| mosaic size change mid-frame | line | vertical counter rule of 6.2 |
| overscan change mid-frame | line | vdisp and NMI/HDMA end per [AN-R "2133"] (1.4) |
| interlace change | frame | latched at V = 0 |
| CPU write (IRQ split) of a class P register inside the visible span (TM, TS, TMW, TSW, W*SEL, W*LOG, CGWSEL, CGADSUB, COLDATA, INIDISP brightness, SETINI bit 3, Mode 7 matrix/centre/scroll, M7SEL) | segment | cut at the first pixel x with T_PIX(x) at or after the write (a pixel composed on the write's own clock already sees the new value: ares runs the PPU's work of a clock after a CPU write of that clock; undisbeliever inidisp-hammer-0f-long and setini-early-read-mode7ex release force blank on a compose clock and decide it, docs/snes-oracles.md section 11) |
| CPU write of a class F register (BGnHOFS/VOFS, BGnSC, BGnNBA, BGMODE tile size bits) inside H = 0 .. 1055 | segment, per layer and column | column k of a layer uses the new value if its name-table slot T_FETCH(k, slot) is at or after the write; pixels of a column follow their column, not their own time |
| window edge (WHx) written while the line is drawn | segment, or dot | segment with range compare unless the new edge passes the current x (4); then dot |
| BGMODE mode bits written inside H = 0 .. 1078 | dot | the fetch pattern changes inside a column |
| any write while an OPT mode is active, to BG3 scroll, BG1/BG2 scroll or BGMODE, inside H = 0 .. 1055 | dot | the offsets of one column feed the next (2.6) |
| force blank set or cleared inside H = 0 .. 1095 of a line V < vdisp | dot | BG garbage, sprite loss on this and the next lines (1.4); a change at H >= 1096 is the HBlank row above |
| OAM write or read during the rendering period (CPU or HDMA) | dot | redirected to the sprite being evaluated or fetched (1.5) |
| CGRAM write or read at 88 <= H < 1096 of a visible line | dot | redirected to the palette entry being drawn (1.5) |
| OBSEL or SETINI bit 1 written during H = 0 .. 1352 of a line V < vdisp - 1 (CPU or HDMA) | dot (sprites of line N+1 only) | evaluation and fetch see different values (3.5) |
| HDMA of line N still running at H >= 1364 | segment / dot | its late writes are CPU-like writes at their real time in line N+1 |
| brightness ramp, INIDISP/SETINI early-read glitches | not modelled | analog or probabilistic; the oracles do not model them either |

Why the line rule is exact for the common case: every PPU state a
line uses is read at or after H = 0 of that line (BG fetch) and before
its HBlank, HDMA writes come after H = 1096, and the documented memory
access rules forbid VRAM/OAM changes during the rendering period. The
two pipeline effects that cross line borders are the sprite double
buffer (3.5) and the BG prefetch of column 0 from H = 0, which is why
the line state is "state at H = 0", not "state at the first pixel".

### 8.2 Fallback rules (checked and extended)

The preparatory research proposed: render a visible line without
force blank and without PPU writes in H in [56, 1078] in one piece with
the state at H = 56; segment it when writes fall inside; full dot
emulation only for OAM or CGRAM access in the active line, force-blank
changes inside the line or around V = vdisp, writes that hit running BG
fetches, and offset-per-tile with mid-line writes; count the fallbacks
per frame. Checked against sections 1 to 7, with these corrections:

1. **Quiet window.** Class F registers are read from H = 0 (column 0 is
   fetched at H = 0..31), not from H = 56; class P registers from
   T_PIX(0). The one-piece rule therefore uses the state at H = 0 for F
   and the state at T_PIX(0) for P, and the quiet window is H in [0,
   1080) for F and [T_PIX(0), T_PIX(255)] for P.
2. **Fetch-relevant writes are segmentable.** Scroll, map base, character
   base and tile size writes need no dot rendering: in the fetch model
   the name-table slot of each column decides the column (7.3), so the
   segment boundary is per layer and per column. Dot rendering is only
   needed when the fetch pattern itself changes (BGMODE mode bits) or in
   OPT modes.
3. **Sprite stage.** New trigger: OBSEL, SETINI bit 1 or OAM changes
   between H = 0 and 1352 of a rendering line, including HDMA writes at
   1104 (inside the sprite fetch), affect the next line's sprites; the
   dot renderer is needed for the sprite stage of that line pair only.
4. **Force blank.** Kept: a change inside the line is dot; additionally a
   force-blank state that covers any part of H = 0..1352 of line N
   empties or corrupts line N+1's sprites even when the change happens
   in HBlank, which the line renderer handles with the rule of 8.1
   (no dot rendering), and the OAM reset at V = vdisp depends on the
   force-blank state then (1.3).
5. **CGRAM/OAM.** Kept, with the windows of 1.5: CGRAM only at 88 <= H
   < 1096 of lines 1..vdisp-1; OAM on all lines 0..vdisp-1 including
   HBlank.
6. **HDMA overrun.** New trigger: if the HDMA of line N ends at or after
   H = 1364, its remaining writes are treated as writes in line N+1 at
   their time stamps (segment rule, dot rule for OAM/CGRAM).
7. **Window edges.** New trigger (optional, log first): a WHx write
   whose new value crosses the current pixel.
8. **Counters.** One counter per trigger kind and frame, written to the
   diagnostic output, so that the scenes that need dot rendering are
   found and compared against ares with "Pixel Accuracy" first.

The order of evaluation per line: collect the line's writes (CPU, DMA,
HDMA) with time stamps; if any dot trigger fires, run the dot renderer
for this line (and the sprite stage of the next); else split class F
writes per layer and column and class P writes per pixel, and render
the segments.

## 9. Scope per target game

Evidence classes in this section: **asserted** (the reimplementation
stops if the state differs), **observed** (values the game code writes),
**disassembly** (a write found in a public disassembly), **doc** (a
listing on the wiki or in fullsnes), **unproven** (no evidence found;
memory of players or developers only).

### 9.1 The Legend of Zelda: A Link to the Past (from zelda3)

zelda3 (snesrev/zelda3, MIT, commit 45a149d) runs the game's logic in
C on its own scanline PPU (snes/ppu.c) with asserts active in its
default build (Makefile:5-6, no NDEBUG). The game writes the PPU
registers through RAM shadows that the NMI copies once per frame
(src/nmi.c:67-107, 152; src/variables.h:15-18, 101-110); VRAM, CGRAM
and OAM are copied in the NMI (src/nmi.c:212, 218). All writes pass
zelda3's PPU write function (src/zelda_rtl.c:63-66).

**Asserted** (snes/ppu.c): OBSEL = 2, i.e. 8x8/16x16 sprites at word
$4000 (:1331); OAMADDH bit 7 = 0, no priority rotation (:1340); BGMODE
is 7 or 9, i.e. mode 1 with BG3 priority or mode 7, and 8x8 BG tiles
only (:1357-1359); VMAIN without remap (:1420); M7SEL = $80, transparent
outside the field, no flip (:1445); WBGLOG = WOBJLOG = 0, window logic
OR only (:1502, :1505); no direct colour (:1520); SETINI = 0, so no
interlace, overscan, pseudo hi-res, OBJ interlace or EXTBG (:1539); HDMA
tables from a fixed list (src/zelda_rtl.c:76-98). The renderer has only
mode 1 and mode 7 paths (snes/ppu.c:816-840).

**Observed** writes: BGMODE only 9 and 7, mode 7 only for the world map
(src/messaging.c:1110) and the attract-mode map (src/attract.c:503);
MOSAIC on BG1+2 or BG1-3 with sizes 1-16 (e.g. src/overworld.c:286,
src/load_gfx.c:1269); 32x32 and 64x64 maps (src/ending.c:490-492,
src/attract.c:991-992); BG12NBA/BG34NBA constant $22/$07 (src/nmi.c:
105-106); windows: W12SEL {0, 3, $33}, W34SEL {0, 3}, WOBJSEL {0, $30,
$33, $B0}, window 2 only in the attract legend scene, window 2 never
inverted; TMW {0, 3, $16, = TM}, TSW {0, 1, = TS}; BG4 never enabled;
CGWSEL {$00, $02, $10, $20, $80, $82}; CGADSUB 16 distinct values with
add, subtract and half; COLDATA from 53 code sites; INIDISP brightness
fades 0-15 and force blank $80 (src/load_gfx.c:447-450). Mode 7: M7B and
M7C are always 0 and M7A/M7D come from HDMA, so the map is scaled and
tilted but never rotated (src/nmi.c:95-104).

**HDMA** (channels 6 and 7 only, HDMAEN once per frame,
src/zelda_rtl.c:180-183): window shapes WH0/WH1 by indirect HDMA (iris
and spotlight, src/load_gfx.c:1432; desert prayer, src/messaging.c:397;
mirror warp, Agahnim, dungeon water), WH0-WH3 direct in the attract
legend (src/attract.c:428), per-line BG1HOFS/BG2HOFS (mirror-warp wave,
src/overworld.c:340), band scroll BG2HOFS in the credits
(src/ending.c:2465), M7A+M7D per line for the perspective of the world
map (src/messaging.c:250, 1273) and the attract zoom (src/messaging.c:
1219-1222, writing M7A/M7D while still in mode 1, which the PPU must
accept). No colour-gradient HDMA, no HDMA to CGRAM, INIDISP, TM or
BGMODE.

**IRQ split:** one, before line 128, writing BG3HOFS and BG3VOFS on the
name entry screen (src/zelda_rtl.c:203-211, src/select_file.c:739).
zelda3 performs it between lines, so the game needs it to take effect
from line 128 on; on the console the write lands somewhere in line 127
or 128 depending on the IRQ position, and S6 must check which line the
oracles show (section 10).

**Line order:** per line i: the IRQ split at i = 128, zelda3's line
renderer for line i, then HDMA of channels 6 and 7 (src/zelda_rtl.c:202-216); line 0 draws
nothing and the sprites of line i come from line i-1 (snes/ppu.c:162,
173). This is the order of 7.4.

**Sprites:** the 32/34 limits exist but are off by default
(snes/ppu.c:1244, zelda3.ini:44), so the game does not depend on
dropout for correct play, but the console shows it and the oracles
compare it: S6 implements 3.5 in full. Evaluation starts at sprite 0
(snes/ppu.c:1243); only 8x8/16x16.

**Not used** (absent from zelda3 or asserted off): modes 0 and 2-6,
16x16 BG tiles, BG4, direct colour, EXTBG, hi-res and pseudo hi-res,
interlace, overscan, window logic other than OR, Mode 7 flip, fill and
wrap, VMAIN remap, priority rotation, rectangular sprite sizes, reads of
$2137-$213F (zelda3's PPU read function returns $FF except $2134-$2136, snes/ppu.c:
1311-1320, and the game never calls it), H-IRQ timing.

**Not Mode 7:** the Triforce intro is a CPU polygon renderer
(src/poly.c:90-96, 241-267) drawing into 4 bpp tiles that the NMI copies
to VRAM $5800 (src/nmi.c:455-460), in BGMODE 9 (src/ending.c:488,
681-695).

**Conclusion for S6, ALttP:** mode 1 with BG3 priority, mode 7 with
per-line M7A/M7D, sprites 8x8/16x16 with the full limits, windows 1/2
with OR and inversion, colour math with sub screen and fixed colour
(add, subtract, half, clip and prevent regions), mosaic on BG1-3, HDMA
direct and indirect, one IRQ split, brightness fades. Every line of the
game is a "line" case of 8.1 except the IRQ split, which is a class F
write (segment rule) if it lands inside the visible span.

### 9.2 Final Fantasy IV, Final Fantasy VI, Chrono Trigger

Sources: everything8215/ff4 (commit a360e2e) and everything8215/ff6
(commit 8130132), both GPL-3 and read for knowledge only (only file
paths and label names are cited); ThisIsAkill/ChronoRET (commit
af992bd, MIT, byte-exact Chrono Trigger disassembly; paths below are
relative to its root); ThisIsAkill/ct-recomp (commit a6b4925, MIT), a
Chrono Trigger recompilation whose THIRD_PARTY.md lists what its
zelda3-derived PPU had to gain; the wiki pages named. Paths are given
per repository; all are "disassembly" evidence unless marked otherwise.

**Final Fantasy IV** (US: Final Fantasy II):

- Modes: $09 (mode 1, BG3 priority; towns, dungeons, battle), $07 (world
  map, solar-system cutscene), $01 (title), $00 (menu) (field/field.asm:
  693-694, 1072-1077; battle/battle.asm:485-486; cutscene/cutscene.asm:
  1159-1160; field/title_en.asm:47-48; menu/menu.asm:3878); mode 0 menu
  also listed by [WIKI Uncommon graphics mode games] (doc). Mode 0 is
  also set briefly to use the PPU multiplier (field/field.asm:2691-2708):
  MPY must work outside Mode 7. No 16x16 BG tiles.
- Mode 7: world map, airship and whale with M7A and M7D per line by
  indirect HDMA (zoom and tilt) and the whole matrix rewritten once per
  frame for rotation (field/field.asm:1745-1800, 2878-2893); the
  solar-system cutscene changes the full matrix per line
  (cutscene/cutscene.asm:802-828). M7SEL only $00 or $80; no EXTBG.
- Windows: OR logic only (field/hardware.asm:72-73); HDMA window shape
  only for the telescope (field/special.asm:348-369).
- Colour math: half-add with the sub screen on sub-maps, subtract fades
  with the fixed colour, transparent monsters in battle (CGADSUB $41),
  CGADSUB per line by HDMA in battle (field/field.asm:728-748;
  btlgfx/btlgfx.asm:4396-4410, 4597-4606). Direct colour bit set in mode
  1 without effect (field/field.asm:1083-1086): the renderer must ignore
  CGWSEL bit 0 outside modes 3, 4, 7.
- Mosaic: battle-entry blur and event mosaic up to size 16
  (field/field.asm:939-956; field/event.asm:1716-1723).
- IRQ splits: the dialogue window writes BG3HOFS/BG3VOFS from a V-IRQ
  after a short delay loop (field/window.asm:1843-1897); the screen wipe
  writes INIDISP (brightness, then force blank $80) from V-IRQs mid-frame
  (field/field.asm:1911-1948); the fat-chocobo menu switches TM (BG4)
  and BG4VOFS (menu/fat_choco.asm:225-260). The INIDISP writes land near
  the start of a line after the IRQ entry and a short delay: a force
  blank change inside the line, i.e. a dot case of 8.1 every frame of a
  wipe.
- Not used: hi-res, interlace, overscan (SETINI always 0,
  field/hardware.asm:83), offset per tile.

**Final Fantasy VI** (US: Final Fantasy III):

- Modes: $09 field and menus, $07 world map, cutscenes and credits, $02
  for the world-map sky, $01 cutscenes (src/field/reset.asm:831-832;
  src/world/world_start.asm:120, 128; src/cutscene/the_end.asm:63). In
  battle an indirect HDMA channel writes BGMODE, MOSAIC, BG1SC and BG2SC
  per screen region, so mode 1 and mode 2 alternate down the screen
  (src/btlgfx/interrupt_2.asm:28-41, 294, 300; src/btlgfx/init.asm:
  563-568); battle sets 16x16 tiles for BG1 and BG3
  (src/btlgfx/gfx_cmd.asm:4545-4591).
- Offset per tile: the Setzer slot menu region runs in mode 2 "for
  per-tile scroll" with its OPT map at VRAM $4000 (src/btlgfx/init.asm:
  566-567, 604-606); the world-map sky in mode 2 has its BG3 vertical
  offset row rewritten from the rotation angle (src/world/rotate.asm:
  305-335; reading of the code, the comments do not say OPT).
- Mode 7: world map with M7A-M7D per line by four indirect HDMA channels,
  rotation plus perspective (src/world/world_start.asm:662-674); credits
  with M7X/M7Y per line (src/menu/menu_init_2.asm:280-336); the opening
  switches BGMODE 1 to 7 at line 84 by HDMA (src/cutscene/opening.asm:
  505-580, 643-646). M7SEL $00 or $80; no EXTBG.
- **Mid-line write:** the world map uses an H+V IRQ with HTIME = 200 at
  the horizon line, whose handler writes BGMODE = 7 (mode 2 sky above,
  mode 7 ground below) (src/world/world_start.asm:90-100, 141-147;
  src/world/interrupt.asm:223-243). The write lands around dot 200 plus
  the IRQ latency, inside the visible span: a BGMODE change in the fetch
  span, a dot case of 8.1 on one line per frame. The chocobo variant
  waits for HBlank first, latches the counters with SLHV and reads
  OPVCT twice (src/world/interrupt.asm:245-280): the H/V latch and the
  $213C/$213D flip-flops (1.3) are needed.
- Windows: WH0-WH3 by HDMA on the world map and in battle
  (src/world/world_start.asm:697-701; src/btlgfx/interrupt_2.asm:48-53);
  WBGLOG/WOBJLOG are written per region by HDMA in battle
  (src/btlgfx/interrupt_2.asm:10-16), but only the value 0 was found
  (non-OR logic: unproven).
- Colour math: COLDATA gradients by HDMA (field in 8-line strips, world
  sky), CGWSEL/CGADSUB/COLDATA/TSW per line in battle, add, half-add and
  subtract (src/field/hdma.asm:68-112; src/world/world_start.asm:
  688-693; src/btlgfx/interrupt_2.asm:43-62); the flying-map sky
  gradient is also named by [WIKI Color math] (doc). No direct colour.
- Mosaic by HDMA in the field and per region in battle
  (src/field/hdma.asm:34-43; src/world/move.asm:165-177).
- HDMA: all eight channels in the field (src/field/hdma.asm:22-125).
- IRQ split: a V-IRQ at line 215 turns HDMA off, sets force blank and
  uploads tiles (src/field/reset.asm:308-343): force blank from about
  that line on; whether the write is inside the line or in HBlank
  decides line or dot case (8.1).
- Not used: hi-res, interlace, overscan (SETINI only 0,
  src/field/reset.asm:872-873), direct colour, EXTBG.

**Chrono Trigger** (US 1.0):

- Modes: $09 written every NMI for field, menu and battle
  (asm/bankC0/bankC0.asm:4962-4963); mode 7 in several scenes
  (asm/bankFD/bankFD.asm:9068-9069; asm/bankC2/bankC2.asm:19008; bank
  $C3 module); mode 2 (asm/bankC3/packed/module.asm:8208-8221); mode 3
  with an 8-bpp BG1 for one ending screen (module.asm:8712-8740); battle
  effects use $49 = mode 1 with BG3 priority and 16x16 BG1 tiles
  (asm/include/constants_battle.inc:1372). ct-recomp had to add OBSEL
  decoding, BG3 priority and 16x16 tiles to the zelda3 PPU
  (ct-recomp THIRD_PARTY.md:50-59). Modes 0, 4, 5, 6: unproven.
- **Offset per tile** (mode 2): the bank $C3 module programs 2 and 3
  (a wave on the vertical offset row; program 3 scrolls the OPT table
  with BG3HOFS) (module.asm:8208-8221, 8437-8445, 9515-9530); the wiki
  lists the title ("Trigger" vertical wave), the intro (Black Omen,
  horizontal OPT) and the menu (scrolling text with more than three
  party members) [WIKI Uncommon graphics mode games] (doc); Mesen-S
  found the menu broken by OPT bugs [WIKI Tricky-to-emulate games]
  (doc); ct-recomp had to add OPT (THIRD_PARTY.md:67-69).
- **Interlace and EXTBG:** bank $C3 program 6 writes SETINI = $41 (EXTBG
  plus interlace) for a turning Mode 7 plane with a mode 1 strip
  (module.asm:12578-12582); the wiki names the view out of the Epoch
  crashing into Lavos (doc); the link between the two is an inference.
  fullsnes lists the same scene as Chrono Trigger's interlace use [FS
  "SNES PPU Resolution" "Hires Software"] (doc). Battle HDMA streams
  CGWSEL, CGADSUB, COLDATA and SETINI per line (asm/bankCD/bankCD.asm:
  1993-2003); the SETINI values sent there are unproven.
- Mode 7 with per-line matrices by HDMA: the jet-bike race (which also
  switches mode 1 to 7 by HDMA), $C3 programs 2, 4, 6, the bank $FD
  scene with M7X/M7Y per line and an iris window, and the swirl and
  perspective scene routines (module.asm:2692-2708, 3980-3995;
  asm/bankFD/bankFD.asm:9046-9085; asm/bankC2/bankC2.asm:21152-21201;
  asm/bankC6/bankC6.asm:1693-1760). Mode 7 for Epoch flight or the
  Lavos battle: unproven.
- Windows: battle effect scripts can set W12SEL/W34SEL/WOBJSEL and
  WBGLOG/WOBJLOG from script data (asm/bankCD/bankCD.asm:9320-9356,
  9560-9592): non-OR logic is possible, the values used are unproven,
  so S6 implements all four logic functions. Window shapes by HDMA in
  the field and in scenes (asm/bankFD/bankFD.asm:3549-3565).
- Colour math: field gradient with add in one half and subtract in the
  other, subtract fades, half-add, COLDATA gradients by HDMA
  (asm/include/constants_engine.inc:822-829; asm/bankC6/bankC6.asm:
  130-161). No direct colour found.
- Mosaic: battle effects (asm/bankCD/bankCD.asm:9191-9224), scene fades
  around the map view (asm/include/constants_menu.inc:266-288).
- HDMA: all eight channels, all indirect, in the field (BGnSC, scrolls,
  TM-TSW, WH0-WH3, CGADSUB/COLDATA) and in battle (adds BGMODE, MOSAIC,
  CGWSEL-SETINI) (asm/bankFD/bankFD.asm:3549-3620;
  asm/bankCD/bankCD.asm:1993-2003). Eight indirect channels with several
  bytes each approach the HDMA overrun of 7.4: S6 measures the end time
  per line (trigger 6 of 8.2).
- IRQ split: a V-IRQ at line 211 waits for HBlank, then sets force
  blank, turns HDMA off and uploads tiles (asm/bankC0/bankC0.asm:
  5301-5323): an HBlank force-blank change, a line case of 8.1.
- Timing-sensitive outside the PPU picture: MAME delays NMI by about 12
  cycles because Chrono Trigger locks up otherwise (MAME
  src/mame/nintendo/snes_m.cpp:154-157); CT polls RDNMI
  (asm/bankC0/bankC0.asm:30089-30095); its random number generator mixes
  in the latched OPHCT/OPVCT values including the open-bus bits and the
  flip-flop phase (asm/bankC3/bankC3.asm:652-697), so 1.3 and 1.6 must
  be exact for CT to stay in step with the oracles.

### 9.3 Combined scope

| Feature | ALttP | FF IV | FF VI | CT |
|---|---|---|---|---|
| mode 0 | no | menu | unproven | unproven |
| mode 1, BG3 priority | yes | yes | yes | yes |
| mode 2 offset per tile | no | no | battle slot menu, world sky | title, intro, menu, scenes |
| mode 3 / 4 (8 bpp) | no | no | no | mode 3, one screen |
| modes 5 / 6 hi-res, pseudo hi-res | no | no | no | no |
| mode 7 | world map (scale) | world map, cutscene | world map, opening, credits | race, scenes |
| Mode 7 EXTBG, interlace | no | no | no | yes (one scene) |
| 16x16 BG tiles | no | no | battle | battle effects |
| BGMODE by HDMA per region | no | no | battle | race, battle |
| mid-line BGMODE write (dot case) | no | no | world map horizon | unproven |
| window logic other than OR | no | no | unproven | possible (scripts) |
| colour math add/sub/half | yes | yes | yes | yes |
| COLDATA gradient by HDMA | no | no | yes | yes |
| mosaic | yes | yes | yes | yes |
| HDMA channels at once | 2 | up to 4 (battle) | 8 | 8, all indirect |
| IRQ split | BG3 scroll at line 128 | BG3 scroll, INIDISP wipe, TM/BG4 | BGMODE at H=200, force blank at 215 | force blank at 211 (HBlank) |
| H/V latch read | no | no | yes (chocobo) | yes (RNG) |
| sprite size pairs | OBSEL 2 only | unproven | unproven | more than OBSEL 2 (ct-recomp had to decode OBSEL) |

Order for S6 that follows from this: everything ALttP needs first
(9.1), then OPT, 16x16 tiles, BGMODE per region and the dot fallback
for mid-line BGMODE and INIDISP writes (FF IV wipe, FF VI horizon),
then interlace and EXTBG for the one CT scene. Hi-res is not needed by
any target game; it stays specified (5.5) but is built last.

## 10. Verification plan for S6

### 10.1 Test material and licences

| Source | Licence | Use | PPU coverage |
|---|---|---|---|
| undisbeliever/snes-test-roms (commit ac6ef80) | Zlib | in the repository's test path after an own build (bass-untech); results as hashes | INIDISP brightness and mid-frame enable, force blank forgotten, HDMA timing and HDMAEN latch, object-dropout-test (32/34 limits, X = 256, flips), vram-mid-scanline-test, INIDISP/SETINI early-read glitches (not compared), window logic demo, HDMA examples, hdma-to-cgram (self-checking), VMAIN remap |
| gilyon/snes-tests | MIT | CI already | no PPU tests |
| PeterLemon/SNES (commit 350b394) | none (all rights reserved) | external runs only, not distributed; hashes not published | BG maps 2/4/8 bpp and map sizes, tile flip, colour math high-colour demos, HDMA (gradients, Mode 7, indirect, wave), interlace, Mode 7 (perspective, rot-zoom), mosaic modes 3/5, window HDMA; many ship a console screenshot |
| rainwarrior SNES_stuff | none | external runs only, not distributed | extbgtest (documented expected result), colourmath, twoship (mode 5 interlace), dizworld (mode 7) |
| 240p Test Suite | GPL-2.0 | external tool only | grids incl. 240-line and mode 7, colour bars, scroll |
| own homebrew (libSFX or pvsneslib, MIT) | MIT | in the repository | scenes the above miss: colour math region matrix, mosaic counter, OPT, hi-res math, STAT77 flags, $2137/$213C latch |

What no available ROM tests on hardware: colour math details, mosaic,
open bus, CGRAM access timing, offset per tile. For those the oracles
(ares with "Pixel Accuracy", MesenCE) are the reference, and the
results are CONS, not DOC.

### 10.2 Picture comparison

- Format: docs/snes-oracle-format.md (oracle notes in
  docs/snes-oracles.md): field `img` = BGR555
  after colour math with brightness applied as `channel * B / 15`
  (integer division) per pixel, force blank 0, rows = lines 1..224
  (239), 256 wide unless any half-pixel pair differs, then 512; current
  field only. MAMR's renderer writes the raw word of 5.6 (colour plus B
  per half-pixel) and converts with the same function as
  tools/oracle/snes/hashline.py.
- Oracles: aresref (ares c76aaff with "Pixel Accuracy", the dot
  renderer) first, MesenCE 2.2.1 second; both pinned; gate G2 (each
  oracle twice byte identical) before any comparison.
- **Line hashes**: the format's optional L line (one hash per picture
  row, outside the chain), or its dump option (`DIR/f<frame>.img.bin`)
  compared row by
  row, gives the first differing line; within the line the first
  differing pixel and the layer stack at that pixel (debug dump of
  main/sub source, priority, window and math flags) localise the stage.
- Together with the write log of that line (and the fallback counters
  of 8.2) the difference is assigned to a stage: fetch (class F), compose
  (class P), sprite (class O) or memory port.

### 10.3 Order of scenes

1. Register and port tests without a picture: VRAM read buffer, OAM and
   CGRAM latches, $2137/$213C/$213F flip-flops with WRIO, MPY, open bus
   (own homebrew; oracle state field `ppu`).
2. Static pictures: PeterLemon BG map ROMs (2/4/8 bpp, map sizes, flip)
   against their screenshots and the oracles.
3. Sprites: undisbeliever object-dropout-test (hardware-confirmed
   results, 3.5).
4. Windows and colour math: undisbeliever window-mask-logic, PeterLemon
   Blend ROMs, own region matrix (all 16 CGWSEL region combinations with
   add/sub/half and sub-screen backdrop).
5. HDMA: hdma-timing-demonstration, HDMA examples, hdma-to-cgram,
   PeterLemon HDMA ROMs.
6. INIDISP: inidisp_enable_display_mid_frame (force blank rules and
   sprite loss), inidisp_forgot_to_force_blank (redirection).
7. Mosaic, Mode 7 (PeterLemon Mosaic and Mode7, the ALttP world map).
8. ALttP scenes by state anchor: title and attract (mode 7 zoom, window
   iris), overworld with mosaic transition, dungeon with colour math
   and window water, the name entry screen (IRQ split at line 128), the
   mirror-warp wave, the credits band scroll.
9. Then the FF IV, FF VI and CT scenes of 9.2, starting with those that
   need OPT, interlace or many HDMA channels.

### 10.4 The three points to check first

1. **Where a mid-line write takes effect (T_PIX, T_FETCH).** ares
   composes pixel x at H = 56 + 4x, the documents put the output at
   88 + 4x, and BG columns are fetched up to 2-3 tiles ahead (7.3).
   Every segment boundary of stage S and the ALttP line-128 split depend
   on these constants. Test: undisbeliever
   inidisp_enable_display_mid_frame and an own ROM that writes BG1HOFS
   and COLDATA from an H-IRQ at stepped HTIME values, compared against
   aresref pixel by pixel.
2. **Colour math corner cases (5.3, 5.4).** Half math with a transparent
   sub pixel, clip with math still on, the region encoding of CGWSEL,
   OBJ palettes 4-7 only. ALttP sets CGWSEL and CGADSUB on almost every
   screen change (9.1); a wrong rule shows on half the scenes. Test: own
   region-matrix ROM plus PeterLemon Blend, against aresref and MesenCE.
3. **The sprite pipeline (3.5).** Evaluation on line N for line N+1, the
   reverse sliver order of the 34 limit, X = 256, the force-blank rule
   and the OAM reset at VBlank. Test: undisbeliever object-dropout-test
   (hardware results published) and inidisp_enable_display_mid_frame.

## 11. Runtime interface (runtime/snes/snes_ppu.h)

The PPU of phase S6 lives in runtime/snes/snes_ppu.{h,cpp} with the
parts snes_ppu_bg.cpp (fetch, offset per tile), snes_ppu_mode7.cpp,
snes_ppu_obj.cpp (sprites) and snes_ppu_math.cpp (windows, compositor,
colour math), library `jf_snes_ppu` (links `jf_snes_board`). Tests:
tests/snes-ppu/.

### 11.1 Model

The renderer is the pipeline of 7.3 run on the master clock: per line
the BG fetch slots (4 clocks each from H = 0, the name-table slot of a
layer decides its column), pixel compose at T_PIX(x) = 58 + 4x, sprite
evaluation of sprite i at H = 8i, the sprite tile fetch at H = 1080 for
the next line, and the line-start actions (fine scroll, mosaic counter,
OAM reset at V = vdisp, sprite buffer swap, STAT77 clear at V = 0).
Before every register access at time t the pipeline runs to t with the
registers as they are, then the access is applied. Consequences:

- A line without PPU writes is drawn in one piece from the state at its
  start (the "line" case of 8.1).
- A write inside the visible span cuts the line: class P registers take
  effect from the first pixel composed at or after the write, class F
  registers from the first column whose name-table slot is at or after
  it (the segment rules of 8.2, points 1 and 2). "At or after": the
  pipeline runs strictly before the access time t, so the dot work of
  clock t sees the written value, as in ares (Ppu::advance_line).
- OAM and CGRAM accesses during rendering are redirected to the sprite
  the evaluation or fetch points at and to the CGRAM entry the
  compositor looked up last (1.5), force blank and BGMODE take effect
  at their pixel and slot.
- The cases of 8.1 that this model reproduces only approximately are
  counted per field in `Ppu::stats` (`last_stats` for the field before):
  BGMODE change in the fetch span, writes in OPT modes, force blank
  changed before H = 1096, OAM access during rendering, CGRAM access at
  88 <= H < 1096, OBSEL or SETINI bit 1 changed during H = 0..1352 of a
  sprite line, a WHx write crossing the current pixel. What remains
  inexact in these cases: the BG garbage after force blank, the slot
  order inside one column on a mode change, the sliver-by-sliver fetch
  between H = 1080 and 1352 (done at once at 1080), the window edge state
  machine (range compare used). These are the stage E items.
- Each visible line keeps its writes (`Ppu::line_log`: H clock,
  register, value) for diagnostics.

### 11.2 Wiring

```text
Board board;  board.init(cart);
Ppu ppu;      ppu.pal = <region>;   ppu.attach(board.map, board.timing);
              ppu.reset();          // power-on: fill = 00
```

- `attach` sets `Map::ppu` ($2100-$213F; CPU accesses and DMA/HDMA on
  the B-bus arrive with their bus-cycle time stamps) and
  `Timing::on_counter_latch` (WRIO bit 7 going 1 to 0). Call it after
  `Board::init`, which leaves both hooks alone.
- SETINI writes call `Timing::set_interlace` and `set_overscan` at the
  write's time; the PPU reads the field shape (`Timing::shape`,
  `frame`) and `Timing::position` (H/V latch, STAT78 field bit) from the
  time skeleton and never calls `Timing::sync` itself, so a PPU access
  from inside a Timing event (HDMA) is safe.
- `$2137` latches only while `Timing::wrio` bit 7 is set (1.3).

### 11.3 What the system calls

- `ppu.sync(t)`: run the pipeline to t. The PPU does this itself on
  every register access; the system must call it at least once per
  line, which keeps the frame buffer complete when a game does not touch
  the PPU for a while. Recommended: from `Board::on_event` for every
  `EventKind::Refresh` (one per line) with `e.at`, and for
  `EventKind::NmiFlag` (V = vdisp) before the frame is sampled.
- `ppu.render_line(v)`: the same as `sync` to the end of line v of the
  current field, for a caller that counts lines itself.
- Frame sample (oracle F line at V = vdisp, H = 0): after `sync(t)`,
  `ppu.image(bytes, w, h)` gives the `img` field (rows 1..224 or 1..239,
  256 or 512 wide, BGR555 LE with brightness applied as channel * B / 15,
  docs/snes-oracle-format.md 5), `ppu.register_bytes(out)` the
  `PPU_REGISTER_BYTES` (77) bytes of the `ppu` field (format version 4,
  section 4 of that document), and `vram` (32K words),
  `oam` (544 bytes, $2138 layout) and `cgram` (256 words) the memory
  fields.
- `ppu.frames_done` counts fields whose visible part is complete;
  `ppu.out_color` / `out_bright` hold the raw output (512 half-pixels
  per line, row = V) for a front end.

### 11.4 Points of this specification that the build made precise

1. The single OPT word of mode 4 (2.6): documented behaviour, not ares.
2. The first sub half-pixel of a hi-res line is black, because it takes
   the math decision of a main pixel that does not exist (5.5, as ares).
3. Sprite tile fetch at one point (H = 1080): an HDMA write to OBSEL at
   H = 1104 therefore acts from the sprites of line N+2 on; on hardware
   it splits the fetch of line N's slivers. Counted as ObjWindow.
4. The compose time T_PIX(x) = 58 + 4x and the CGRAM window
   [88, 1096) come from different places of ares (7.3, 1.5); the
   redirect target is the entry looked up for the last composed pixel.
   At a write whose clock equals a compose, fetch or evaluation clock the
   write goes first (ares' thread order; checked by undisbeliever's
   inidisp-hammer-0f-long and setini-early-read-mode7ex, where the
   force-blank release lands on T_PIX(29) and T_PIX(159): before
   2026-10-24 MAMR drew those pixels black, one pixel late).
5. The field length is the time skeleton's: the PPU follows
   `Timing::shape` and derives the line lengths from it, including the
   PAL field shapes of snes_timing (7.5). While the PPU's field counter
   differs from the skeleton's (it catches up in one piece after a long
   WAI, stage E synchronizes it only at CPU bus cycles) it takes the
   shape of its own field in the skeleton's video system; a fallback to
   NTSC there wrapped a PAL field at 262 lines and shifted the line
   counter by 50 lines per field (Motive's HblankEmuTest, 2026-10-24,
   docs/snes-oracles.md section 12.1).
6. STAT77 flags are cleared at V = 0 only without force blank (1.3,
   CHOICE fullsnes); ares clears them always.
7. Brightness is stored per pixel, the colour per half-pixel; the
   oracle conversion applies the pixel's brightness to both halves.
8. 16x16 and 16-wide tiles: the +1 / +16 neighbours wrap within the
   10-bit character number (2.4), before the character base is added.
9. Mode 7 uses ares' 32-bit wrapping arithmetic (unsigned products with
   the screen coordinates, logical shift). It differs from exact signed
   arithmetic only when the vertical mosaic offset is "negative" after a
   size change (6.2), where it keeps the low coordinate bits and makes
   the pixel count as out of bounds.
10. Mosaic after a size change inside a block: ares, not the documents
    (6.2).

### 11.5 State of verification

- tests/snes-ppu/test_ppu_regs.cpp, test_ppu_render.cpp and
  test_ppu_edges.cpp: register semantics and synthetic scenes with
  literal expected pixels (section 10.3 steps 1 to 7 on synthetic data).
  Fifteen injected faults (size table entry, OAM reset in force blank,
  VRAM lock on line 0, BG3 priority bit in mode 0, OBJ math palettes,
  direct colour mode check, STAT77 clear in force blank, CGRAM window,
  vertical flip of rectangular sprites, EXTBG priority, colour and OBJ
  window logic sources, 10-bit character wrap, VRAM address bit 15,
  power-on open bus) each fail at least one of them.
- tests/snes-system (snes_system_gilyon_*): gilyon cputest-basic,
  cputest-full and spctest, 600 frames each through the full system
  (snes_headless: 65816, board, S-SMP, PPU); every field of the hash
  lines, `img`, `ppu`, `vram`, `oam` and `cgram` included, equals the
  aresref reference in tests/snes-oracle/reference (text, palette and
  the progress screens), apart from the cpu field in the frames that
  depend on the open WDM timing decision.
- Not yet compared against an oracle: sprites, windows, colour math,
  mosaic, Mode 7 and the other modes on real ROMs (section 10.3 steps 3
  to 9), and the three first points of 10.4.
