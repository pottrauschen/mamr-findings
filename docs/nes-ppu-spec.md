# NES PPU Specification

Register and behaviour specification of the NES picture chip (Ricoh
RP2C02, NTSC) for phase N2 of docs/nes-architecture.md. It is written so
that the PPU of runtime/nes/ can be built from this text alone, without
reading another implementation. The board side (CPU memory map, the
cartridge, the MMC3 and its A12 filter, the DMA unit, the APU frame
counter) is specified in docs/nes-hardware-spec.md; this document refers
to it instead of repeating it.

The chip described is the RP2C02G, the revision AccuracyCoin was written
for (docs/nes-hardware-spec.md, introduction). Older revisions differ in
documented details (OAMDATA not readable, palette RAM not readable);
those are named where they matter and not modelled.

## 0. Sources, notation, provenance

**Sources** (all retrieved 2026-10-24):

- **NESdev wiki** (www.nesdev.org/wiki): pages "PPU registers", "PPU
  scrolling", "PPU rendering", "PPU sprite evaluation", "PPU frame
  timing", "PPU OAM", "PPU palettes", "PPU power up state", "PPU memory
  map", "Open bus behavior", "NMI", "MMC3" (section "IRQ Specifics").
  Cited as [WIKI page]. Class DOC: the wiki collects console tests,
  forum findings and emulator experience; several of its timing details
  were confirmed with the Visual 2C02 simulation, which this project
  does not use (below).
- **Brad Taylor, "NTSC 2C02 technical reference"**, 5th release
  2004-04-23 (nesdev.org/2C02 technical reference.TXT). Cited as
  [TAYLOR]. Class DOC; older than the wiki and superseded by it where
  they differ (section 15).
- **AccuracyCoin** (MIT, Chris Siebert; commit and hashes in
  docs/nes-test-evidence.md), written for and run on an RP2A03G/RP2C02G
  console. Every test is a hardware expectation of its author. Cited as
  [ACC test name], class TEST-ROM-HW in the sense of
  docs/nes-hardware-spec.md (the author's console, no published log).
- **blargg's PPU test ROMs** (christopherpow/nes-test-roms, commit
  95d8f621ae55cee0d09b91519a8989ae0e64753b; no licence, run locally,
  nothing copied): ppu_vbl_nmi, vbl_nmi_timing, ppu_open_bus,
  ppu_read_buffer, oam_read, oam_stress, sprite_hit_tests,
  sprite_overflow_tests, blargg_ppu_tests. Cited as [BLARGG name];
  TEST-ROM-HW where the readme states a console run (docs/nes-test-
  evidence.md section 3.2).
- **MesenCE 2.2.1** (GPL-3, read only) for the conventions of the
  primary oracle: its CPU/PPU alignment, its power-on sequence and its
  sampling point (section 13). Never a template for code. Cited as
  [MESEN file], class IMPL.
- **Not used:** Visual 2C02 and everything derived from it (CC BY-NC-SA):
  no tables, no timing diagrams, no node names, no quotations of its
  results. Where the wiki states a detail that it attributes only to
  the simulation, this document gives the wiki as the source and marks
  the class DOC, and the detail is confirmed by an AccuracyCoin test or
  listed in section 15.

**Provenance classes:** as in docs/nes-hardware-spec.md (DATASHEET,
MEASURED, TEST-ROM-HW, DOC, EMU-CONSENSUS, IMPL, INFERENCE, UNKNOWN,
CHOICE).

**Notation.** A *dot* is one PPU clock (4 master clocks of 21.477272 MHz
on NTSC; three dots per CPU cycle). The PPU position is (line, dot) with
line 0..261 and dot 0..340; lines 0-239 are visible, 240 is the
post-render line, 241-260 are vertical blank, 261 is the pre-render
line (also called -1). "Rendering enabled" means PPUMASK bit 3 or bit 4
is set (section 1.3); "rendering lines" are 0-239 and 261. Hex values
are written $xx. Bits are numbered from 0 = least significant. *Process
dot (l, d)* means the PPU's work in that dot; the position counter is
advanced first and the dot then processed, so the power-on position
(0, 0) is never processed in the first frame (section 12).

## 1. Registers

### 1.1 Address decoding [WIKI "PPU registers"], DOC

The PPU decodes CPU A0-A2 when the CPU accesses $2000-$3FFF: eight
registers mirrored every eight bytes ([ACC "PPU Register Mirroring"]).
OAMDMA at $4014 is a 2A03 register, not a PPU register (docs/nes-
hardware-spec.md section 3.8).

| reg | name | access | content |
|---|---|---|---|
| $2000 | PPUCTRL | W | bit 7 NMI enable, 6 EXT output (never set on a console), 5 sprite size 8x16, 4 BG pattern table $1000, 3 sprite pattern table $1000 (8x8 only), 2 increment 32, 1-0 nametable (into t) |
| $2001 | PPUMASK | W | bit 7 emphasis blue, 6 green, 5 red (NTSC order), 4 sprites on, 3 background on, 2 sprites in the left 8 pixels, 1 background in the left 8 pixels, 0 greyscale |
| $2002 | PPUSTATUS | R | bit 7 vertical blank, 6 sprite 0 hit, 5 sprite overflow, 4-0 I/O latch (open bus) |
| $2003 | OAMADDR | W | OAM address |
| $2004 | OAMDATA | RW | OAM data |
| $2005 | PPUSCROLL | Wx2 | X then Y scroll (into t and x) |
| $2006 | PPUADDR | Wx2 | VRAM address high then low (into t, then v) |
| $2007 | PPUDATA | RW | VRAM data through v |

### 1.2 The I/O latch (PPU open bus) [WIKI "PPU registers" section "MMIO registers", "Open bus behavior"], DOC

The PPU has an internal 8-bit data latch between its registers and the
CPU. Every write to any register (also to $2002) fills it with the value
written; a read of $2002, $2004 or $2007 fills it with the bits the read
drives. A read of a write-only register returns the latch; the unused
bits of $2002 (4-0) return the latch's bits; a read of palette RAM
returns the latch in bits 7-6 (section 3.3). The latch is dynamic: a bit
not refreshed decays to 0 "after 3 ms to 30 ms, faster when the PPU is
warm" (DOC, with a forum test by lidnariq). Each bit is refreshed only
when a write fills it or a read drives it, so the bits decay
independently ([BLARGG ppu_open_bus], [ACC "PPU Register Open Bus"]).

Model: one time stamp per bit, the value of a frame counter that
advances at dot (240, 0); a bit reads as 0 once the counter has moved
more than `decay_frames` past the frame in which the bit was last
driven. `decay_frames` is a CHOICE (section 15.4), default 3 (50 to 67
ms), longer than the published range so that no test that expects a
value to survive a frame sees it decay, and short enough for
[ACC "PPU Register Open Bus"] and [BLARGG ppu_open_bus], which wait for
the decay.

### 1.3 PPUCTRL ($2000 write) [WIKI "PPU registers", "PPU scrolling"], DOC

- t bits 10-11 = value bits 0-1.
- NMI enable is the other input of the NMI output (section 4.4):
  setting it while the vertical blank flag is 1 raises the NMI output
  immediately ([ACC "NMI Control"], TEST-ROM-HW); clearing it lowers the
  output.
- Bit 6 is stored and ignored (EXT output; the console grounds EXT, so
  the backdrop stays palette entry 0).
- A write that starts on dot 257 of a rendering line with a horizontal
  nametable arrangement makes the next line take the left nametable for
  some alignments ("bit 0 race", [WIKI "PPU registers"], DOC). Not
  modelled (CHOICE, section 15.6).

### 1.4 PPUMASK ($2001 write) [WIKI "PPU registers"], DOC

- Rendering is enabled when bit 3 or bit 4 is set. "Toggling rendering
  takes effect approximately 3-4 dots after the write" (DOC). Model: the
  rendering-enabled signal used by the fetch, increment and evaluation
  logic follows the written value `render_delay` dots after the write
  (CHOICE, default 3, section 15.2); greyscale, emphasis, the left-8
  clips and the per-layer enables take effect on the next dot.
- Greyscale ANDs every output colour with $30, also the value returned
  by a palette read (section 3.3); the stored palette is unchanged.
- Emphasis bits 5-7 go to the output pixel unchanged (section 8).
- Turning rendering off mid-line with v in $3C00-$3FFF can corrupt
  palette RAM (DOC, cause unknown); not modelled (UNKNOWN, section 15).

### 1.5 PPUSTATUS ($2002 read) [WIKI "PPU registers", "PPU frame timing"], DOC

- Returns vertical blank (bit 7), sprite 0 hit (bit 6), sprite overflow
  (bit 5) and the I/O latch in bits 4-0; bits 7-5 refresh the latch,
  bits 4-0 do not.
- Clears the vertical blank flag and w.
- Race with the setting of the flag (section 4.3): a read at the
  position just before the dot that sets the flag returns 0 and the flag
  is not set in this frame; a read at the setting dot or one dot later
  returns 1 and clears it, and the NMI of that frame does not occur
  ([BLARGG vbl_nmi_timing], [ACC "VBlank beginning", "NMI Suppression"],
  TEST-ROM-HW). In the model the second case needs no rule: the read
  clears the flag before the CPU's next edge sample (section 13).
- The vertical blank flag is latched at the start of the read (M2
  rising), the sprite 0 hit and overflow flags at its end (M2 falling,
  about 1.9 dots later on the RP2A03G, whose M2 is high for 15/24 of the
  cycle) ([ACC "$2002 flag timing"], TEST-ROM-HW). Model: the board
  brings the PPU to the end of the CPU cycle (one dot past the access
  point of section 13) and the sprite flags are taken as the following
  dot will leave them (`NesPpu::finish_status_read`): the flags pending
  for the next dot count, the clear of dot (261, 1) counts when that is
  the next dot. This is the second dot after the access point (CHOICE,
  section 15.11).

### 1.6 OAMADDR ($2003 write) and OAMDATA ($2004) [WIKI "PPU registers", "PPU OAM", "PPU sprite evaluation"], DOC

- $2003 sets the OAM address. On the 2C02G a write is said to corrupt
  OAM by copying a row; "the exact corruption isn't fully described"
  (DOC). Not modelled (UNKNOWN, section 15.7).
- $2004 write outside rendering: OAM[OAMADDR] = value, OAMADDR + 1.
  During rendering (rendering lines with rendering enabled) the byte is
  not written and OAMADDR is "glitchily" incremented by 4 (the high six
  bits; DOC, "for emulation purposes it is probably best to completely
  ignore writes during rendering"). Model: no write, OAMADDR += 4
  (CHOICE between the two wiki statements; [ACC "Address $2004
  behavior"] decides).
- $2004 read outside rendering returns OAM[OAMADDR] (attribute bytes
  with bits 2-4 read as 0, section 3.4) and does not increment. During
  rendering it returns the value the evaluation logic has on its OAM
  data bus (section 6.5): $FF during the secondary OAM clear, the byte
  just read or written during evaluation and fetch. The value is taken
  at the end of the CPU read: the board advances the PPU one dot past the
  access point first ([BLARGG oam_read], [ACC "Address $2004 behavior",
  "$2004 Stress Test"], TEST-ROM-HW: with the value at the access point
  every result is one dot early).
- OAMADDR is set to 0 in every dot 257-320 of a rendering line while
  rendering is enabled.

### 1.7 PPUSCROLL ($2005) and PPUADDR ($2006) [WIKI "PPU scrolling"], DOC

| write | effect |
|---|---|
| $2005, w = 0 | t bits 0-4 = value bits 3-7; x = value bits 0-2; w = 1 |
| $2005, w = 1 | t bits 12-14 = value bits 0-2; t bits 5-9 = value bits 3-7; w = 0 |
| $2006, w = 0 | t bits 8-13 = value bits 0-5; t bit 14 = 0; w = 1 |
| $2006, w = 1 | t bits 0-7 = value; w = 0; v = t after a delay |

The copy t -> v of the second $2006 write happens "1 to 1.5 dots after
the write completes" (DOC). Model: `v_delay` dots after the write
(CHOICE, default 3, chosen with [ACC "t Register Quirks"] and the
oracle's behaviour; section 15.3). A coarse X or Y increment of the
rendering logic in the same dot as the copy is overwritten by it.

### 1.8 PPUDATA ($2007) [WIKI "PPU registers", "PPU scrolling"], DOC

- Outside rendering (or rendering disabled): a write stores the value
  at v (14 bits, through the mapper; $3F00-$3FFF into palette RAM), a
  read returns the read buffer and loads the buffer with the byte at v;
  then v += 1 or 32 (PPUCTRL bit 2), 15 bits wide.
- Palette reads ($3F00-$3FFF): the palette entry is returned at once in
  bits 5-0 (greyscale applied), bits 7-6 from the I/O latch; the buffer
  is loaded with the nametable byte "underneath" (address & $2FFF)
  ([ACC "PPU Read Buffer", "Palette RAM Quirks"], [BLARGG
  ppu_read_buffer]).
- Timing. A read returns the buffer at once; the PPU's own access
  happens `data_delay` = 5 dots after the access point (about 4 dots
  after the end of the CPU read, the "PPU DATA state machine" of
  AccuracyCoin: ALE two dots after the end of the read, the read two
  dots later), then v is incremented one dot later. Reads and writes
  have separate state machines: a write one CPU cycle after a read (the
  dummy read and write of STA $2007,X) leaves both intact ([BLARGG
  dmc_dma_during_read4 read_write_2007], TEST-ROM-HW); a second read
  before the first one's access is ignored and returns the I/O latch
  ([BLARGG dmc_dma_during_read4 double_2007_read]).
- During rendering (rendering lines, rendering enabled) an access does
  not add 1 or 32: it performs a coarse X increment and a Y increment of
  v together (section 2.2), whatever PPUCTRL bit 2 says ([WIKI "PPU
  scrolling"]: "it will update v in an odd way"). A read refills the
  buffer with what the fetch logic reads in that dot: when the access
  falls on a read dot of the fetches (even dots), the fetched byte (the
  nametable, attribute or pattern byte of that dot); when it falls on an
  ALE dot, the octal latch is driven by the data bus instead of the new
  low address byte (it keeps the byte read in the dot before), the byte
  read through it goes into the buffer and back into the latch, and the
  next fetch reads through that latch ([ACC "$2007 read w/ rendering",
  "$2007 Stress Test", "ALE + Read"], TEST-ROM-HW; section 9). A write
  stores the value at the address on the bus.
- CHR ROM is not writable ([ACC "CHR ROM is not writable"]); the write
  goes to the mapper, which ignores it.

## 2. Internal registers v, t, x, w [WIKI "PPU scrolling"], DOC

v and t are 15 bits: fine Y (12-14), nametable (10-11), coarse Y (5-9),
coarse X (0-4); x is the fine X scroll (3 bits); w the write toggle.
v is the VRAM address for $2007 and the scroll position during
rendering.

### 2.1 Coarse X increment

If coarse X = 31: coarse X = 0 and bit 10 toggles; else coarse X + 1.

### 2.2 Y increment

If fine Y < 7: fine Y + 1. Else fine Y = 0 and coarse Y: 29 -> 0 with
bit 11 toggled; 31 -> 0 without the toggle; else + 1 (rows 30 and 31
are the attribute table read as tiles).

### 2.3 Updates by the rendering logic (rendering enabled, rendering lines)

| dots | action |
|---|---|
| 8, 16, ..., 256 and 328, 336 | coarse X increment |
| 256 | Y increment (after the coarse X increment of the same dot) |
| 257 | v bits 0-4 and 10 = t bits 0-4 and 10 |
| 280-304, pre-render line only | v bits 5-9, 11-14 = t bits 5-9, 11-14 |

## 3. Memory

### 3.1 PPU address space [WIKI "PPU memory map"], DOC

$0000-$1FFF pattern tables (cartridge CHR, through the mapper);
$2000-$2FFF nametables (CIRAM or cartridge VRAM, arranged by the
mapper; docs/nes-hardware-spec.md section 3.2); $3000-$3EFF mirror of
$2000-$2EFF; $3F00-$3FFF palette RAM inside the PPU (the address bus
still carries the address; the cartridge sees a nametable read there).

### 3.2 Pattern tables and tile fetches [WIKI "PPU pattern tables", "PPU rendering"], DOC

A tile is 16 bytes: plane 0 at +0..7, plane 1 at +8..15, row r at +r.
Pixel x of a row is bit 7-x of each plane; the pixel value is
plane1 << 1 | plane0, 0 = transparent.

### 3.3 Palette RAM [WIKI "PPU palettes"], DOC

32 entries of 6 bits at $3F00-$3F1F, mirrored to $3FFF. Entries $10,
$14, $18, $1C are the same cells as $00, $04, $08, $0C ([ACC "Palette
RAM Quirks"]). Entry $00 is the backdrop. Reads return bits 7-6 from
the I/O latch. Power-on content is unspecified (section 12).

### 3.4 OAM [WIKI "PPU OAM"], DOC

256 bytes, 64 sprites of four bytes: Y (top line minus 1), tile index,
attributes, X. Attribute bits: 7 vertical flip, 6 horizontal flip, 5
priority (1 = behind the background), 1-0 palette (4-7 of the sprite
palettes); bits 2-4 do not exist and read back as 0. 8x16 sprites take
the pattern table from tile bit 0 and the top tile from bits 7-1.
OAM is DRAM and decays when not refreshed; decay is not modelled
(CHOICE, as both oracles; [WIKI "PPU OAM" "Dynamic RAM decay"]).

Secondary OAM: 32 bytes for the eight sprites of the next line
(section 6). Not visible to the CPU except through $2004 reads during
rendering.

## 4. Frame timing [WIKI "PPU rendering", "PPU frame timing", "NMI"], DOC

### 4.1 Lines and dots

262 lines of 341 dots. With rendering enabled at the decision point,
the pre-render line of every odd frame skips its last dot: the position
goes from (261, 339) straight to (0, 0), and the work of dot (261, 340)
is done there. The odd/even flag toggles every frame, rendering or not
([BLARGG vbl_nmi_timing 3.even_odd_frames], [ACC "Rendering Flag
Behavior"]). Decision point: the skip happens when the delayed
rendering signal (section 15.2) is on for the dot the position advances
into from (261, 339); a $2001 write counts when its delay ends with that
step. TEST-ROM-HW in relation to the delay CHOICE: [BLARGG ppu_vbl_nmi
10-even_odd_timing] (expected output 08 08 09 07) passes with this
point; one dot earlier (the signal of (261, 339) itself, the model until
2026-10-26) fails its test 2 ("skipped too soon, relative to enabling
BG"), one or two dots later fail test 3 ("too late").

### 4.2 Status flag clear

Vertical blank, sprite 0 hit and sprite overflow are cleared in dot 1
of the pre-render line ([ACC "VBlank end"]).

### 4.3 Vertical blank flag set

The flag is set in dot 1 of line 241, unless a $2002 read happened at
the position (241, 0), i.e. after dot (241, 0) was processed and before
dot (241, 1) (section 1.5).

### 4.4 The NMI output

The PPU's /NMI output is active while the vertical blank flag and
PPUCTRL bit 7 are both 1. The CPU detects the falling edge of /NMI (here:
the rise of the boolean "NMI output") by sampling it once per CPU cycle
(docs/nes-hardware-spec.md section 4.3); the sampling point inside the
CPU cycle is the alignment convention of section 13. Consequences, all
TEST-ROM-HW [ACC "NMI Control", "NMI Timing", "NMI Suppression", "NMI
at VBlank end", "NMI disabled at VBlank"]:

- enabling NMI during vertical blank with the flag set gives an NMI
  after the next instruction (the edge is seen at the end of the write
  cycle, after that instruction's poll);
- reading $2002 in the dot of the flag's setting or one dot later
  suppresses the NMI (the output is active for less than one sampling
  interval);
- disabling NMI in the same CPU cycle as the flag's setting suppresses
  it; enabling it at the end of vertical blank (the flag is cleared in
  dot 1 of line 261) gives no NMI when the write lands after the clear.

## 5. Background pipeline [WIKI "PPU rendering", "PPU scrolling"], DOC

### 5.1 Fetches

In dots 1-256 and 321-336 of a rendering line (rendering enabled), each
8-dot group fetches, two dots per access:

| dots of the group | address | latch |
|---|---|---|
| 1-2 | $2000 \| (v & $0FFF) | nametable byte |
| 3-4 | $23C0 \| (v & $0C00) \| ((v >> 4) & $38) \| ((v >> 2) & $07) | attribute byte; the two bits for the tile are selected by coarse Y bit 1 and coarse X bit 1 at fetch time |
| 5-6 | PPUCTRL bit 4 * $1000 + tile * 16 + fine Y | pattern plane 0 |
| 7-8 | the same + 8 | pattern plane 1 |

Dots 337-340 fetch the nametable byte twice (337-338 and 339-340) at
the same address as the first fetch of the next line. Dots 257-320
belong to the sprite fetches (section 7.1); the garbage nametable fetch
of dot 257 still uses v before the horizontal copy of that dot ([ACC
"$2007 Stress Test"], TEST-ROM-HW). In each access the full address is
on the bus in the first dot (ALE) and the read happens in the second
dot with the latched low byte and the high bits of that dot (section
9).

### 5.2 Shift registers and pixel selection

Two 16-bit pattern shift registers and two 8-bit attribute shift
registers fed by 1-bit latches. In every fetch dot (1-256 and 321-336)
every register shifts left by one; the pattern registers shift in a
constant (0 for plane 0, 1 for plane 1, [WIKI "PPU rendering"]). In the
dot of the high pattern read (8, 16, ..., 256 and 328, 336), after the
shift, the low byte of the pattern registers is loaded from the plane
latches and the attribute latches from the selected attribute bits. In
dot d of 1-256 the background pixel for x = d - 1 is bit 15 - x_fine of
the pattern registers and bit 7 - x_fine of the attribute registers, as
the previous dot left them. The wiki describes the same pipeline one
dot later (shifts in 2-257, loads in 9, ..., 257, the pixel after the
shift); for continuous rendering both give the same picture, but with
rendering switched off and on again the load must belong to the dot of
the high pattern read: a load missed in forced blank then shows the
serial input ([ACC "BG Serial In"], TEST-ROM-HW; MesenCE 2.2.1 fails
it).

The background pixel is 0 when PPUMASK bit 3 is clear, or when x < 8
and PPUMASK bit 1 is clear.

### 5.3 Rendering toggled mid-frame

With rendering disabled the fetches, shifts, increments and the
evaluation stop at once (after the delay of section 1.4); the latches
and shift registers keep their contents ([ACC "Stale BG Shift
Registers"]). The wiki states that they decay to 0 in about two frames;
decay is not modelled (CHOICE, section 15.8). "BG Serial In", "ALE +
Read" and "Hybrid Addresses" test the constant shifted in and the
two-dot address latch; MesenCE fails all three (docs/nes-test-
evidence.md section 2), MAMR passes them with sections 5.2, 1.8 and 9.

## 6. Sprite evaluation [WIKI "PPU sprite evaluation"], DOC

Only on visible lines 0-239 with rendering enabled (either layer); not
on the pre-render line.

### 6.1 Dots 1-64: clear

Odd dots read (the read returns $FF), even dots write $FF to secondary
OAM at index (dot / 2 - 1). $2004 reads $FF.

### 6.2 Dots 65-256: evaluation

The OAM address starts at OAMADDR as it is at dot 65 (normally 0;
[ACC "Misaligned OAM behavior", "Arbitrary Sprite zero"]). n is the
sprite (OAMADDR bits 2-7), m the byte (bits 0-1). Odd dots read
OAM[4n + m]; even dots write the byte read to secondary OAM at the next
free index, or, when secondary OAM is full, read it instead. The state
machine:

1. Copy the byte (a Y coordinate) to secondary OAM. If line - Y is in
   0..7 (8..15 with 8x16 sprites), the sprite is in range: the address
   + 1, copy the next three bytes (each + 1), then go to 2. Otherwise
   the address + 4, aligned down to a multiple of 4 ((address + 4) AND
   $FC), and go to 2. The fourth byte (X) goes through the same range
   check as Y: when it is out of range the address after it is aligned
   down to a multiple of 4 as well ([ACC "Misaligned OAM behavior"]
   tests 2-7, TEST-ROM-HW; invisible with an aligned address).
2. If the address wrapped past $FF: go to 4. If fewer than eight
   sprites were found: go to 1. If eight: secondary OAM is full (writes
   become reads of its byte 0), go to 3.
3. Evaluate OAM[address] as a Y coordinate. In range: the sprite
   overflow flag is set (visible after the next dot, as sprite 0 hit,
   section 7.3), then the next three bytes are read (address + 1 each,
   the X check of step 1 applies to the third: [ACC "$2004 Stress Test"]
   test 3), and go to 4. Not in range: n + 1 and m + 1 without carry
   from m into n (the hardware bug; with an aligned address this is +5,
   [ACC "Misaligned OAM behavior"] test 3); if the address wrapped, go
   to 4, else repeat 3.
4. Read OAM[address] and attempt a write (which fails), address + 4,
   wrapping, until dot 256.

Sprite 0 in range: when the first sprite copied (the byte at the start
address, normally sprite 0) is in range, the "sprite 0 on the next
line" flag is set for the hit logic (section 7.3).

Misaligned start (OAMADDR not a multiple of 4 at dot 65): evaluation
starts at that byte and reads it as a Y coordinate, the following bytes
as the rest of the entry; it ends when the address wraps past $FF
([WIKI "PPU registers" OAMADDR], [ACC "Misaligned OAM behavior"]).

### 6.3 OAMADDR at render start: the row copy [WIKI "PPU sprite evaluation" notes], DOC

On the 2C02G and 2C02H, when sprite evaluation starts with OAMADDR >=
8, the 8 bytes at OAMADDR & $F8 are copied over OAM bytes 0-7. Model:
at the first dot 65 of a frame at which evaluation runs (line 0, or the
first visible line after rendering is enabled mid-frame), if OAMADDR >=
8 the copy is made (DOC; no AccuracyCoin test isolates it, and section
6.6 is a different effect).

### 6.4 Dots 257-320: fetch from secondary OAM

For each sprite slot i = 0..7 (8 dots each) bytes are read from
secondary OAM at its own address, which is reset to 0 in dot 257 and
incremented in slot dots 0, 1 and 2 (Y, tile, attribute) and 7; in slot
dots 3-7 the byte at the same address (X) is read repeatedly. The
address stands still while rendering is off, so a fetch interrupted by
forced blank continues out of step ([ACC "Misaligned OAM2 Address"],
TEST-ROM-HW). The address is five bits; its overflow (in the
evaluation when secondary OAM fills up, and in dot 320 at the end of
the fetch) sets a flag that freezes it at 0, cleared in dots 63, 255 and
339 when rendering is on ([ACC "Frozen OAM2 Increment"], TEST-ROM-HW,
"a brand new discovery"; MesenCE 2.2.1 fails it): with rendering off in
dot 255 or 339 the next fetch reads byte 0 for every slot. Empty slots
hold $FF (the first empty slot after a full scan holds the last Y read
in step 4). OAMADDR is 0 in every dot of 257-320 (section 1.6). The
effect of the freeze on the clear of dots 1-64 is not modelled.

### 6.5 What $2004 returns during rendering

The byte on the evaluation's OAM data bus in that dot: $FF during
dots 1-64; during 65-256 the byte read in the last odd dot (in even
dots a successful write shows the byte written, a failed write the
byte read from secondary OAM); during 257-320 the byte read from
secondary OAM; during 321-340 and dot 0 the byte of secondary OAM at its
address, normally byte 0 ([WIKI "PPU sprite evaluation"], [BLARGG
oam_read], [ACC "$2004 Stress Test", "Misaligned OAM2 Address"]).

### 6.6 Rendering stopped mid-line: the OAM row corruption

When rendering is switched off inside a rendering line (dots 1-320),
the secondary OAM address at that moment is a "seed": at the first
rendering dot after rendering is switched on again (on a rendering
line), the 8 bytes of OAM row 0 are copied over row `seed` (bytes 8 *
seed to 8 * seed + 7), and secondary OAM byte 0 over secondary OAM byte
`seed` ([ACC "OAM Corruption"], TEST-ROM-HW). The secondary address is
(dot - 1) / 2 in dots 1-64, the evaluation's next index rounded up to a
multiple of 4 in dots 65-256, and the fetch address of section 6.4 in
dots 257-320 (CHOICE: the value before the dot's increment;
AccuracyCoin notes that the alignments differ there and does not test
it). With the switch-off delay of section 1.4 (3 dots) the test's
calibration row is 5; AccuracyCoin reports 2 dots for alignments 0 and 3
and 3 dots for alignments 1 and 2.
MesenCE 2.2.1 has this corruption switched off by default
(docs/nes-oracles.md section 2); Super Mario Bros. 3 triggers it in every
frame of a level, where its IRQ handler switches rendering off at line
193 (finding S3 of docs/nes-oracles.md section 6).

## 7. Sprites

### 7.1 Fetches, dots 257-320 [WIKI "PPU rendering"], DOC

Per slot: two garbage nametable fetches (dots 1-4 of the slot, the
nametable address of the next line's first tile), then pattern plane 0
(dots 5-6) and plane 1 (dots 7-8). The pattern address: 8x8 sprites
PPUCTRL bit 3 * $1000 + tile * 16 + row; 8x16 sprites (tile & 1) * $1000
+ (tile & $FE) * 16, + 16 for the bottom half, + row & 7; row = (line
AND $FF) - Y, flipped (7 - row, 15 - row) with attribute bit 7. Empty
slots fetch tile $FF (8x8: in the selected table; 8x16: $1FF0) and the
result is replaced by transparent data; on the pre-render line the row
is 261 AND $FF = 5, so secondary OAM left over from line 239 or from
before a forced blank can load a sprite for line 0 ([ACC "Sprites On
Scanline 0"]). Horizontal flip reverses the fetched bytes. The
attribute byte is loaded in dot 3 of the slot, the X counter in dot 4.

### 7.2 Output units

Eight units, each with two 8-bit shift registers, the attribute and an
X counter with two modes, counting and halted (AccuracyCoin's
description, [ACC "Stale Sprite Shift Regs"], TEST-ROM-HW; MesenCE
2.2.1 fails that test):

- The counter is loaded with X during the fetch (section 7.1) and set to
  counting in dot 339 if rendering is on then. Without rendering in dot
  339 the units stay halted and draw their shift registers from the
  first rendered pixel ([ACC "Stale BG Shift Registers"] test 4,
  "Stale Sprite Shift Regs" tests 5 and 6).
- In each pixel dot of a visible line (x = 0..255) a counting unit
  decrements its counter, and at 0 it switches to halted. The counters
  run in forced blank as well (test 2); the shift registers do not
  (test 3).
- A halted unit shifts out one pixel per rendered pixel dot.
- After the odd-frame skip (section 4.1) every unit puts out a pixel at
  x = 0 of line 0, the counting ones included, which then go on
  counting: a sprite on line 0 shows its first pixel at x = 0 and the
  rest one pixel to the left in every second frame (composite RP2C02;
  the RGB PPUs do not; [ACC "Sprites On Scanline 0"] test 3).

Unit 0 has the highest priority among sprites; the first unit with an
opaque pixel wins, even when its priority bit puts it behind the
background ("sprite priority quirk"). The sprite pixel is 0 when PPUMASK
bit 4 is clear or when x < 8 and bit 2 is clear.

### 7.3 Sprite 0 hit [WIKI "PPU OAM"], DOC

Set when, at pixel x, unit 0 holds the sprite of evaluation index 0
(section 6.2), its pixel is opaque, the background pixel is opaque, x
!= 255, both layers are enabled, and not (x < 8 and either left clip is
active). Priority does not matter. The flag becomes visible to $2002
reads one dot after the pixel is composed: "sprite 0 hit acts as if the
image starts at cycle 2" ([WIKI "PPU rendering"], [ACC "Sprite 0 Hit
behavior", "$2002 flag timing"]; [BLARGG sprite_hit_tests 09-11]).

### 7.4 Priority multiplexer

| BG | sprite | priority | output |
|---|---|---|---|
| 0 | 0 | - | backdrop ($3F00) |
| 0 | 1-3 | - | sprite |
| 1-3 | 0 | - | background |
| 1-3 | 1-3 | 0 | sprite |
| 1-3 | 1-3 | 1 | background |

Background index $00 | attr << 2 | pixel, sprite $10 | palette << 2 |
pixel.

## 8. Output pixel

The palette entry of the multiplexer's index, ANDed with $30 under
greyscale, with the emphasis bits 5-7 of PPUMASK. With rendering
disabled the picture is the backdrop, except that when v (14 bits)
points into $3F00-$3FFF the entry at v is shown instead ("backdrop
override", [WIKI "PPU rendering" "Rendering disabled"]). The PPU writes
the picture of lines 0-239, 256 pixels each, as 9-bit values (colour
index | emphasis << 6); the hash lines canonicalise them
(docs/nes-oracle-format.md section 5).

## 9. The PPU address bus and the mapper [WIKI "PPU rendering" "PPU address bus contents", "MMC3"], DOC

The PPU multiplexes the low 8 address lines with the data bus: the first
dot of an access drives the full 14-bit address and latches the low
byte externally (ALE), the second dot drives only the high six bits and
reads or writes through the latched low byte. The cartridge sees PPU
A10-A13 at all times, so the mapper sees every change of the high bits.
During rendering the bus carries the fetch addresses of sections 5.1
and 7.1; outside rendering it carries v (also after every $2006 and
$2007 change of v). Dot 0 of a rendering line carries the pattern
address computed from the garbage nametable fetch of dots 337-340 (an
ALE dot, [ACC "$2007 Stress Test"] notes), except on the pre-render
line, where the line before did not fetch and A12 stays low until dot
5 ([BLARGG mmc3_test_2 4-scanline_timing] test 8, TEST-ROM-HW: with
$2000 = $10 the first counter clock of a frame comes 256 dots before
the one with $2000 = $08), and except after the odd-frame skip, where
(0, 0) does the read of dot 340 ([WIKI "PPU frame timing"]). The read
dots use the octal latch: the address is the current A8-A13 with the
latched low byte, which is normally the low byte of the ALE dot before;
a $2007 read in an ALE dot changes it (section 1.8), and a $2006 copy
between the two dots gives a "hybrid" address (new high bits, old low
byte; [ACC "Hybrid Addresses"], MesenCE 2.2.1 fails it). This is what
clocks the MMC3:
with the background at $0000 and 8x8 sprites at $1000, A12 rises once
per line at the first sprite pattern fetch (dot 261 for slot 0); with
the tables swapped, at the first background pattern fetch of the next
line (dot 325). The filter that turns these rises into counter clocks
is the board's (docs/nes-hardware-spec.md section 3.4).

Model: the PPU reports the address of the first dot of every access
(and every change of v outside rendering) to the mapper with the master
clock of that dot; the mapper decides what an A12 change means.
`NesPpu::octal_` is the external latch, `ad_` the AD0-AD7 lines.

## 10. Rendering-dependent side effects, summary

| effect | when | section |
|---|---|---|
| v increments | rendering lines, rendering enabled | 2.3 |
| $2007 access increments X and Y | rendering lines, rendering enabled | 1.8 |
| $2004 write ignored, OAMADDR + 4 | rendering lines, rendering enabled | 1.6 |
| OAMADDR = 0 | dots 257-320 of rendering lines | 1.6 |
| odd frame dot skip | pre-render line | 4.1 |
| sprite evaluation, row copy | visible lines | 6 |

## 11. Not modelled

PAL is section 18 (phase P; until then it was listed here). The
2C03/2C04/2C05 RGB PPUs, EXT output, OAM and latch decay of OAM and of
the shift registers, the $2003 corruption, palette corruption on
rendering disable, the PPUCTRL bit 0 race, the colour of the border
region and the NTSC signal. Each is recorded in section 15 where a
source exists.

## 12. Power-up and reset [WIKI "PPU power up state"], DOC

At power-on PPUCTRL, PPUMASK, t, x, w and the read buffer are 0; OAMADDR
is 0; v is 0 (MesenCE; the wiki leaves v open); the status flags are 0
(the wiki: vertical blank "random at power", often set; CHOICE 0, as the
oracles with fill 00); OAM, palette RAM and CIRAM are unspecified and
take the run's fill value (format "fill"; MesenCE starts its palette
with a fixed table that its source attributes to blargg's power-up
palette test, so the comparison against MesenCE starts MAMR from the
oracle's frame-1 palette, `nes_headless --palette`, docs/nes-oracles.md
section 6). The PPU starts at position
(0, 0) of an even frame (the wiki: "at the top of the picture"; MesenCE
the same), so the first vertical blank flag is set in dot (241, 1) of
the first frame, 82182 dots after power-on.

Writes to $2000, $2001, $2005 and $2006 are ignored for about 29658 CPU
cycles after power-on (until the end of the first vertical blank)
([WIKI "PPU power up state"], [ACC "PPU Reset Flag"]). MesenCE ignores
nothing by default (`RestrictPpuAccessOnFirstFrame` off). Model: a
board parameter `ignore_first_frame_writes`, default off for oracle
comparison (CHOICE), on for the hardware judge AccuracyCoin, whose
result is recorded both ways (docs/nes-test-evidence.md).

## 13. CPU/PPU alignment and the sampling points

The CPU cycle is 12 master clocks, the dot 4; the relative phase of the
two dividers at power-on is one of several (UNKNOWN which on a given
console; the wiki speaks of four alignments [WIKI "PPU frame timing"]).
MAMR fixes the relation by one number, the dot count at which a CPU
access samples the PPU:

- CPU cycles are numbered from power-on, the first cycle being 0. A
  register access of cycle k (read or write) sees the PPU after
  3k + 4 dots have been processed (dots 1 .. 3k + 4 counted from the
  power-on position, section 0) and before the next.
- The CPU's interrupt inputs are sampled at the end of cycle k, after
  3k + 5 dots.
- At power-on the CPU spends one idle cycle and the seven cycles of the
  reset sequence (docs/nes-hardware-spec.md section 4.4) before the
  first opcode fetch in cycle 8.

These are the conventions of MesenCE 2.2.1 without its alignment
randomisation (its CPU master clock starts one CPU period in, its PPU
lags one master clock, it runs eight CPU cycles before the first fetch
and runs the PPU to the access point before every access; [MESEN
NesCpu.cpp NesPpu.h], IMPL). They are one of the hardware's alignments
in the sense of [WIKI "PPU frame timing"] (paraphrased: a read sees a
flag change exactly when the read starts at or after the PPU dot in
which the flag changes); which of the four the console prefers is section 15.1. The
hash header records them as `align=1`, as MesenCE's writer does.

The hash lines' sampling point (docs/nes-oracle-format.md section 3) is
the first instruction boundary after the PPU processed dot (240, 0);
`cyc` and `dot` there are the oracle's numbers (section 15.1 of
docs/nes-oracles.md records how MAMR's counters map to them).

## 14. Dot renderer and line renderer

The dot renderer processes one dot at a time exactly as sections 4-9
describe; it is the reference (stage E). The line renderer processes a
whole rendering line (dots 0-340) in one call with the same results: the
same picture row, the same v, the same secondary OAM and sprite units,
the same flags with the same dots of setting, the same OAMADDR, and the
same PPU address sequence reported to the mapper with the same master
clocks. It may be used only when the line starts at dot 0, nothing
outside the PPU reads or writes a PPU register before the line ends,
and the rendering-enabled signal does not change inside the line. The
board (stage S) calls it when it advances the PPU over a whole line
with no CPU access to $2000-$3FFF inside it; otherwise it runs the dot
renderer. Stage S and stage E must give byte-identical hash lines
(gate G1, docs/nes-architecture.md section 7).

Status of phase N2: the line renderer is the dot work of the whole line
in one call (`NesPpu::line_renderer` runs the 341 dots without the
board's per-cycle bookkeeping); it is exact by construction and gate G1
checks stage S against stage E, but it is not yet faster in the dots
themselves. A renderer that composes a line from whole tiles is open
(phase N3, where the emitted CPU blocks make the PPU the larger cost);
it must keep the effects of sections 6-9 that happen inside a line
(A12 rises for the mapper, the secondary OAM address, the OAM bus value
read by $2004).

## 15. Where the sources differ, and the open questions

Each item is a CHOICE with a test that would settle it on a console
(RP2A03G + RP2C02G front-loader unless stated).

**15.1 CPU/PPU alignment.** UNKNOWN which alignments occur and how often.
CHOICE: the MesenCE alignment (section 13). Setup: AccuracyCoin's
alignment-dependent tests ("VBlank beginning", "NMI Timing", "$2002 flag
timing") and blargg's vbl_nmi_timing over 50 power cycles, each run's
result logged; the distribution names the alignments. The board takes
the alignment as a parameter (`NesBoardConfig::ppu_access_dot`).

**15.2 PPUMASK delay and the odd-frame decision.** Wiki: "approximately
3-4 dots"; AccuracyCoin's OAM corruption calibration: 2 dots on
alignments 0 and 3, 3 on 1 and 2; CHOICE 3 (`render_delay`), which with
MesenCE's alignment passes every AccuracyCoin test. The odd-frame skip uses the
delayed signal of the dot after (261, 339) (section 4.1). Setup: a ROM that enables rendering at a
CPU cycle swept across dots 330-341 of the pre-render line over many
frames with sprite 0 hit at a fixed position, measuring the frame length
by a cycle-counted $2002 loop; and one that disables rendering at
swept dots inside a visible line while sprite 0 is at x = 0..15, reading
the hit flag.

**15.3 The $2006 copy delay.** Wiki "1 to 1.5 dots"; CHOICE 3 dots,
because [ACC "t Register Quirks"] and MesenCE agree on it (to be
re-checked when AccuracyCoin's test fails). Setup: a second $2006 write
swept across dots 250-260 of a visible line with distinct nametable
content on both sides of the copy, the picture photographed.

**15.4 I/O latch decay.** Measured range 3-30 ms (forum, one tester,
temperature-dependent). CHOICE 3 frames (section 1.2). Setup: write $FF to $2002, read
$2000 after delays of 1 ms to 100 ms in steps, cold and warm, per bit;
the console's spread replaces the default.

**15.5 Address of a $2007 access during rendering.** Settled by
AccuracyCoin (TEST-ROM-HW): the byte the fetch reads in that dot, with
the octal latch behaviour of an ALE dot (sections 1.8 and 9; [ACC "$2007
Stress Test", "ALE + Read"]). The unstable reads (a read meeting a
fetch's ALE and read at once with different bytes) are analogue on the
console; the model gives the stable result of the feedback after one
pass.

**15.6 PPUCTRL bit 0 race at dot 257.** Not modelled; the wiki ties it
to "specific CPU-PPU alignments". Setup: as in the wiki's forum
reference, a $2000 write swept across dots 255-259 with distinct left
and right nametables, per alignment.

**15.7 The $2003 write corruption.** UNKNOWN in detail; not modelled.
Setup: blargg's oam_stress and a ROM that fills OAM with the index of
each byte, writes $2003 with chosen values and reads OAM back through
$2004 outside rendering.

**15.8 Decay of the background latches and shift registers** ("about 2
frames", DOC). Not modelled; [ACC "Stale BG Shift Registers"] and
"Stale Sprite Shift Regs" test stale contents within a frame, which the
model keeps.

**15.9 MMC3 clock source: A12 or A13.** [TAYLOR] names A13 and "42 times
per scanline"; the wiki, blargg's tests and the MMC3 schematic name A12
(docs/nes-hardware-spec.md section 3.4). A12 is used; Taylor is
superseded here.

**15.10 Sprite 0 hit visibility.** The wiki's "acts as if the image
starts at cycle 2" fixes the earliest dot; MAMR makes every hit and the
overflow flag visible one dot after the dot that finds them (section
7.3). [ACC "$2002 flag timing"] passes with it, together with 15.11;
[BLARGG sprite_hit_tests 09-11] pass.

**15.11 Where a $2002 read samples the sprite flags.** AccuracyCoin:
"approximately 1.875 PPU cycles after the vblank flag is read" and two
accepted answer keys by alignment. MAMR samples as the second dot after
the access point leaves them (section 1.5); that gives the alternative
key of test 1 and the $40 variant of test 2, both of which AccuracyCoin
attributes to alignments 2 and 3, while the render delay of 15.2 and the
OAM corruption row point to alignments 1 or 2: MAMR's alignment is a
mixture that no single console has (CHOICE until a console run per
alignment is logged, setup 15.1).

**15.12 The seed of the OAM corruption during the sprite fetch.** Before
or after the increment of the secondary address in that dot,
alignment-dependent per AccuracyCoin; CHOICE before (section 6.6). Setup:
switch rendering off in each of dots 257-264 and read OAM back.

**15.13 Dot 0.** The pattern address at dot 0 of a rendering line (ACC's
description), none on the pre-render line (blargg's MMC3 timing) and
the dot-340 read after the odd-frame skip (the wiki): three sources for
three cases, consistent with each other and with MesenCE.

## 16. Verification

- Unit tests without a ROM (tests/nes/test_nes_ppu.cpp): the vertical
  blank set and clear dots, the $2002 race, the NMI output, the frame
  length with and without rendering (odd-frame skip), the scroll
  registers and w, the data port with its delay, increments, palette
  mirror, palette reads and the buffer underneath, OAM access with the
  attribute mask and the I/O latch, sprite overflow, the sprite 0 hit dot
  and its exceptions, the picture of a solid tile and of the backdrop,
  one MMC3 counter clock per line, and the line renderer against the dot
  renderer over three frames.
- AccuracyCoin, every PPU page: all tests pass (docs/nes-test-evidence.md
  section 4.1); seven of the PPU-related corrections of phase N2 came
  from it.
- blargg's PPU suites that run on NROM/MMC3 boards (vbl_nmi_timing 1-7,
  ppu_open_bus, oam_read, oam_stress, sprite_hit_tests 1-11,
  sprite_overflow_tests 1-5, blargg_ppu_tests): pass, power_up_palette
  only with an oracle's palette; ppu_vbl_nmi (MMC1) and ppu_read_buffer
  (CNROM) pass since these boards were added on 2026-10-26, ppu_vbl_nmi
  after the odd-frame decision point of section 4.1 (section 4.2
  there).
- Hash lines against MesenCE: equal in every field for AccuracyCoin's
  first 300 frames, and with input until the first test MesenCE fails
  (docs/nes-oracles.md section 6). Gate G1 checks stage S against stage
  E. Super Mario Bros. 3 against MesenCE: docs/nes-oracles.md section 6
  and docs/nes-test-evidence.md section 4.4.

## 17. Runtime interface (runtime/nes/nes_ppu.h)

`NesPpu` holds the registers, OAM, secondary OAM, palette RAM, the
pipeline state, the position and the picture. The board owns it and
gives it the cartridge side (`NesMapper` and the CIRAM). The board
advances it with `run(dots)` (the dot renderer, or the line renderer
for whole lines when allowed) and accesses its registers with
`read(reg)` and `write(reg, value)` after advancing it to the access
point of section 13. `nmi_output()` is the /NMI state; `frame_done()`
tells the board that dot (240, 0) was processed. The canonical hash
bytes (ppu, oam, pal, vram, img) are produced by
runtime/nes/nes_hashline.

## 18. PAL: the RP2C07 (phase P)

The 2C07 renders as the 2C02 ([WIKI "PPU rendering"]: "the same
rendering behavior as NTSC PPUs except for the border", DOC); it differs
in the frame, the CPU/PPU clock ratio, the OAM refresh, the emphasis
bits and the border. Sources: [WIKI "PPU rendering", "PPU registers",
"PPU OAM", "Errata", "Clock rate", "Cycle reference chart"] (retrieved
2026-10-27, DOC); MesenCE 2.2.1 in PAL mode for the oracle's conventions
(IMPL); the clocks and the alignment are docs/nes-hardware-spec.md
sections 7.1 and 7.2. The region is a board parameter
(`NesPpuConfig::pal`); with it off nothing below applies and the NTSC
PPU is unchanged.

### 18.1 Lines and dots

312 lines of 341 dots: 0-239 visible, 240 post-render, 241-310 vertical
blank (70 lines, DOC), 311 the pre-render line (INFERENCE from the 312
lines and the NTSC order; IMPL MesenCE: vertical blank set at line 241,
its last vertical blank line 310). Everything section 4 says of line 261
holds for line 311: the status flags clear in dot (311, 1), the
pre-render line's fetches, the vertical copy of dots 280-304. There is no
odd-frame skip: every frame has 106,392 dots, rendering or not (DOC
[WIKI "Clock rate"]; IMPL MesenCE). The vertical blank flag is set in dot
(241, 1) with the same $2002 race as section 4.3 (INFERENCE: [WIKI "PPU
frame timing"] covers "only the NTSC PPU, though most probably applies
to the PAL PPU"). The sampling point of the hash lines stays dot (240, 0).

Test proposal: on a PAL console, a cycle-counted $2002 loop started from
the NMI measures the distance from the flag's setting to its clear
(70 x 341 dots); a second loop with rendering on over two frames shows
that the frame length does not alternate.

### 18.2 The forced OAM refresh

During lines 265-310 (24 lines after the vertical blank starts) the 2C07
refreshes OAM: OAMADDR is incremented once every two dots, in dots 2, 4,
..., 340 of each line, not in dot 0 ([WIKI "PPU OAM"], DOC: "The OAM
address increments once every 2 pixels, except at pixel 0"). Sprite
evaluation "can never be fully disabled" on the 2C07 ([WIKI "PPU
registers"], DOC), so the refresh runs whether rendering is on or not
(DOC; IMPL MesenCE the same). Effects a program can see: OAMADDR moves
in those lines (46 x 170 increments, 7820, which is 140 modulo 256), and
OAM "can't be written" there, so OAM DMA belongs to the first 24 lines
of the vertical blank ([WIKI "PPU registers"], DOC).

What a $2004 write in the refresh lines does is not stated. MAMR: the
write lands as in the vertical blank (at OAMADDR, then OAMADDR + 1), and
the refresh increments run besides it (CHOICE). MesenCE (IMPL) writes
the byte and increments OAMADDR only on odd dots other than 339. Test
proposal: write a known pattern with $2004 at a cycle swept through line
280 on a PAL console, read OAM back in the next vertical blank through
$2004 at lines 241-264. Super Mario Bros. 3 writes OAM by DMA from its
NMI handler, which starts at line 241 and ends before line 247.

### 18.3 OAMADDR at render start and the row corruption

The 2C02's row copy when evaluation starts with OAMADDR >= 8 (section
6.3) does not exist on the 2C07: "OAMADDR works as intended" on it
([WIKI "PPU registers"], DOC; IMPL MesenCE the same). MAMR: switch
`NesPpuConfig::oam_row_copy` off for PAL.

The OAM row corruption after rendering is stopped inside a line (section
6.6) is not described for the 2C07 by any source; the forum statement
MesenCE quotes is about $2003 writes being buffered on the 2C07, not
about this corruption. MAMR keeps the 2C02 behaviour on PAL (INFERENCE:
the evaluation logic is described as the same; class UNKNOWN for the
hardware). MesenCE corrupts no rows on PAL (IMPL), as on NTSC by
default, so this is expected to separate the oam fields as finding S3
does on the USA game (docs/nes-oracles.md section 6). Test proposal: the
setup of section 15 for S3 (AccuracyCoin's "OAM Corruption" page) on a
PAL console.

OAMADDR after rendering is switched off inside sprite evaluation (dots
65-256) is the evaluation's address at the stop in MAMR (the 2C02 model
of section 6.2, also on PAL); MesenCE in PAL mode leaves a different value
in Super Mario Bros. 3 Europe's frames 9 and 10 ($19 against MAMR's $18,
finding P1, docs/nes-oracles.md section 8.2). No program in the test
material reads OAMADDR there; UNKNOWN. Test proposal: on a PAL console,
switch rendering off at a cycle swept through dots 65-100 of a line with
known sprites, then read $2004 in the vertical blank before line 265 (the
refresh) and compare the byte with OAM to find the address.

### 18.4 Emphasis and border

- Emphasis: PPUMASK bit 5 emphasises green and bit 6 red on the 2C07,
  bit 7 blue as on the 2C02 ([WIKI "PPU registers"], [WIKI "Errata"],
  DOC). MAMR's picture keeps the emphasis in colour order (pen bit 6
  red, 7 green, 8 blue) in both regions, so the 2C07 stores PPUMASK bit 6
  in pen bit 6 and bit 5 in pen bit 7; the RGB palette (runtime/nes/
  nes_palette) and the hash line's img field (docs/nes-oracle-format.md
  section 5) read the pen the same way in both regions. MesenCE does the
  same (its PAL mode swaps the two bits when PPUMASK is written, IMPL).
- Border: the 2C07 outputs black in line 0 and in the two leftmost and
  two rightmost columns of every line, rendering or not; emphasis and
  greyscale do not reach it, and sprite 0 hit is unaffected ([WIKI "PPU
  rendering"], DOC). The border is part of the video signal, not of the
  colour index the pixel pipeline selects: the picture (`picture()`) and
  the img field keep the indices of section 8 (CHOICE, so img compares
  with both oracles, which keep the full picture in their index buffers),
  and the frontend's RGB conversion paints the border black for PAL
  (runtime/machine/nes_game).

### 18.5 Power-up

As section 12, with the first-frame write block lasting about 33,132 CPU
cycles (DOC [WIKI "PPU registers"]; the switch stays off for the oracle
comparison, as on NTSC). The PPU starts at (0, 0) of frame 0; the first
vertical blank flag is set 82,182 dots after power-on in both regions.

### 18.6 Verification

- Unit tests without a ROM (tests/nes/test_nes_ppu.cpp): frame length
  106,392 dots with and without rendering, the flag set at (241, 1) and
  cleared at (311, 1), OAMADDR after the refresh lines with rendering
  off, the emphasis bit order of the picture.
- [BLARGG-NMISYNC] demo_pal.nes (docs/nes-hardware-spec.md section 7):
  the drawn line inside the reference range (result 2026-10-27: inside,
  docs/nes-test-evidence.md section 4.7).
- Against MesenCE and MAME in PAL mode: Super Mario Bros. 3 Europe over
  3000 frames, every field (docs/nes-oracles.md section 8).
