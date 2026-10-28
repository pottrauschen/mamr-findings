# Hardware Specification: NES (Famicom)

Register-level reference for the NES runtime (docs/nes-architecture.md).
Section 1 records the target cartridge, sections 2 and 3 the cartridge
header and the board skeleton of phase N1 (runtime/nes/), section 4 the
2A03 CPU core (recompiler/m6502_*, runtime/m6502_*), section 5 the open
hardware questions with the console test that would settle each. The PPU,
the APU and the DMA unit (phase N2) append their own sections later, each
with its own number, sources and "where the sources differ" list, so that
earlier sections stay untouched.

The hardware this specification describes is the one AccuracyCoin was
written for: an NTSC NES with an RP2A03G CPU and an RP2C02G PPU
(AccuracyCoin README). "The NES" is not one machine: CPU and PPU
revisions differ in documented details (AccuracyCoin skips some tests on
other revisions), and every hardware statement below is meant for the G
revisions unless it says otherwise.

**Sources:**

- **NESdev wiki** (www.nesdev.org/wiki, retrieved 2026-10-24), the
  counterpart of fullsnes on the SNES side: pages "INES", "NES 2.0",
  "CPU memory map", "Open bus behavior", "Standard controller",
  "Controller reading", "MMC3", "NROM", "MMC1", "CNROM" (the last two
  retrieved 2026-10-26), "CPU interrupts", "CPU unofficial
  opcodes", "CPU power up state", "Cycle reference chart", "PPU power up
  state", "DMA". Cited as [WIKI page]. The wiki collects test results,
  emulator experience and forum findings; it is DOC unless a page links
  a console measurement.
- **MOS 6502 data sheet** (MCS6500 family hardware and programming
  manuals) for the documented instructions, flags and cycle counts. Cited
  as [MOS].
- **blargg's mmc3_irq_tests readme** (christopherpow/nes-test-roms,
  commit 95d8f621ae55cee0d09b91519a8989ae0e64753b, directory
  mmc3_irq_tests): the MMC3 counter rules and the revision differences,
  run by the author on Crystalis (revision A) and Super Mario Bros. 3
  (revision B) boards. The collection has no licence; it is cited as a
  source and run locally, nothing of it is copied. Cited as [BLARGG-MMC3].
- **lidnariq, nesdev forum t=10340 and p=116018** (2013): oscilloscope
  measurement of the MMC3's A12-to-/IRQ delay and of the M2 duty cycle.
  Cited as [LIDNARIQ].
- **Competing statements on the MMC3 A12 filter:** the wiki text "after
  the line remains low for two falling edges of M2" (quoted in nesdev
  t=23164, 2021-05-31), the hypothesis "about 5 consecutive CPU clock
  cycles" (t=8807, after kevtris), and "conjectured to be about 12" dots
  (t=19413). Cited as [A12-FILTER].
- **blargg's CPU instruction tests** (same collection and commit:
  instr_test-v5 and blargg_nes_cpu_test5, readme and source): checksums
  of every instruction's results, with the opcodes whose results the
  author found unreliable marked "?" and left out. Cited as
  [BLARGG-CPU].
- **Cartridge identification:** NesCartDB profile 4527 (Super Mario
  Bros. 3, NES-TSROM-07, Sharp MMC3B, date code 9027), the 1200 dpi board
  scan archive.org/details/super-mario-bros-3_20240425 (NES-TSROM-07,
  Sharp MMC3B), nesdir A0B0B742_USA (TSROM-05, -06, -07, all MMC3B; ROM
  CRC32s), and a Bannister forum photo post of 2006-05-02 for the Japanese
  release (MMC3A). Cited as [CARTDB].
- **Die analysis of the 2A03** (the "Breaks" project, quoted in
  alewman/6502-python pull request 2): the decimal-adjust signals are cut
  on the die. Cited as [DIE].
- **Test programs with hardware expectations:** AccuracyCoin (MIT, Chris
  Siebert; docs/nes-test-evidence.md) and, locally only, blargg's suites
  and nestest. Cited as [ACC test name].
- **Emulators as references, not as hardware evidence:** MesenCE 2.2.1
  (GPL-3, nesdev-org/MesenCE tag 2.2.1, commit
  20ba206cef5ba207c21203176d02cb9f43dda9fb, read only) and MAME 0.285
  (tag mame0285, files under src/devices/bus/nes/ and
  src/devices/video/ppu2c0x.cpp, read only). Neither is a template for
  any code of this path (docs/nes-architecture.md section 1). Cited as
  [MESEN file] and [MAME file].
- **Transistor-level simulation:** perfect6502 (Michael Steil, Brian
  Silverman, Barry Silverman; MIT; github.com/mist64/perfect6502 at
  commit 09fc542877a84318291aa42dab143a3e2c3db974), a C port of the
  Visual6502 switch-level simulation that runs the Visual6502 netlist of
  the NMOS 6502 (Greg James, Brian Silverman, Barry Silverman, CC
  BY-NC-SA 3.0). The 2A03 carries the same core without the decimal
  adjust (section 4.1). It is run outside the repository, with a harness
  of our own that only sets the NMI and IRQ pins and reads the bus;
  nothing of it (netlist, code, tables, traces) is copied here. A result
  is recorded as a behavioural statement of class SIM with this source.
  Cited as [P6502].
- **Not used:** the Visual2A03 and Visual2C02 netlists themselves (CC
  BY-NC-SA): no tables, no timing numbers, no quotations. A fact known
  only through them is UNKNOWN here unless a simulation run as above
  states it (class SIM).

**Provenance classes** (as in docs/snes-hardware-spec.md):

| class | meaning |
|---|---|
| DATASHEET | data sheet, schematic, die analysis |
| SIM | a transistor-level simulation of the chip's netlist, run for this question ([P6502]) |
| MEASURED | measured on a console with an instrument |
| TEST-ROM-HW | a test ROM run on a console, result published |
| DOC | hardware documentation based on tests, method not given (NESdev wiki) |
| EMU-CONSENSUS | several independent emulators agree (here MesenCE and MAME) |
| IMPL | one emulator only |
| INFERENCE | concluded without direct evidence |
| UNKNOWN | no usable source |
| CHOICE | this runtime's decision where the sources are silent or differ |

A statement whose only evidence is AccuracyCoin's expectation is
TEST-ROM-HW in so far as the author ran the ROM on his RP2A03G/RP2C02G
console; the README states the target revisions but publishes no console
log, so where a single test decides something this specification names
the test.

## 1. Target cartridge: Super Mario Bros. 3

| release | board | mapper chip | PRG ROM | CHR ROM | class |
|---|---|---|---|---|---|
| USA, PRG0 | NES-TSROM-05/06/07 | Sharp MMC3B | 256 KiB, CRC32 C78D17D3 (whole ROM A0B0B742) | 128 KiB, CRC32 C2928C49 | DOC [CARTDB]; board and chip also MEASURED by photograph |
| USA, PRG1 | as PRG0 | Sharp MMC3B | 256 KiB, CRC32 A0ED7D20 (whole ROM 2E6301ED) | as PRG0 | DOC [CARTDB] |
| Japan | (HVC board) | MMC3A | | | INFERENCE (one forum photo, not archived) |
| Europe (PAL) | NES-TSROM-08 (to be confirmed) | unknown | 256 KiB, CRC32 80CD1919 (PRG + CHR 1ED5C801) | 128 KiB, CRC32 7970A157 | ROM hashes MEASURED (the file read on 2026-10-27); board UNKNOWN (section 5.4) |

TSROM: MMC3, 8 KiB PRG RAM without battery, CHR ROM, mirroring
controlled by the MMC3. `nes_cart_identify` (runtime/nes/nes_cart.cpp)
knows the two USA PRG ROMs by CRC32; the CRC32s are those of the
databases. The revision 1 file read on 2026-10-25 matches them (PRG
A0ED7D20, CHR C2928C49, PRG + CHR 2E6301ED; header mapper 4, 8 KiB PRG
RAM by the iNES 1.0 convention, no battery; all hashes in
docs/nes-test-evidence.md section 4.4); revision 0 has not been read.

The MMC3 revision decides the IRQ rule at a latch value of 0 (section
3.3). A forum analysis states that the game never writes 0 to the IRQ
latch ($C000), which would make the A/B difference irrelevant for it.
Logged in MAMR (`--pc-stats`) over two runs of 3000 frames (title, menu,
map, World 1-1): only $C0 and $C1 are written (section 5.3).

The European release (phase P, section 7) has its own PRG and CHR ROM.
The file read on 2026-10-27 (`Super Mario Bros. 3 (Europe).nes`, 393,232
bytes, SHA-1 of the file bd1a5b3c6918d3b01df0b2789ab0e726bb9209e0, of
PRG + CHR without the header 31144c7c436cc78d7fd3ac42b224eee3a6c2babc,
of the PRG ROM 8d389a0893beedf273e21ef865c9a8288a929184) has the same
iNES 1.0 header bytes as the USA file: mapper 4, 16 x 16 KiB PRG, 16 x 8
KiB CHR, byte 9 = 0 (NTSC). The database entry (`nes_cart_identify`,
PRG CRC32 80CD1919, with the SHA-1 of PRG + CHR) gives its region PAL
(section 7.5); the CRC32 agrees with the No-Intro name of the file
(DOC, the dump database; the board is not confirmed, section 5.4).

## 2. Cartridge header

### 2.1 iNES 1.0 [WIKI "INES"], DOC

| byte | content |
|---|---|
| 0-3 | "NES" $1A |
| 4 | PRG ROM size in 16 KiB units |
| 5 | CHR ROM size in 8 KiB units; 0 = the board has 8 KiB of CHR RAM |
| 6 | bit 0 mirroring (0 horizontal, 1 vertical), bit 1 battery, bit 2 512-byte trainer before the PRG ROM, bit 3 four-screen VRAM, bits 4-7 mapper bits 0-3 |
| 7 | bits 2-3 = 2 marks NES 2.0; bits 4-7 mapper bits 4-7 |
| 8 | PRG RAM size in 8 KiB units, 0 meaning 8 KiB |
| 9 | bit 0 TV system, 1 = PAL (rarely set; section 7.5) |
| 10-15 | unused; old dumps carry text ("DiskDude!") from byte 7 on |

Conventions of the parser (`nes_cart_parse`), CHOICE where the format is
silent: when any of bytes 12-15 is nonzero the header is treated as such
an old dump and bytes 7-15 are ignored (mapper from byte 6 only, 8 KiB of
PRG RAM); the PRG RAM is always present with 8 KiB unless byte 8 says
more, because both oracles provide it for every iNES 1.0 ROM (MesenCE
reports 8 KiB of work RAM for AccuracyCoin's NROM image, MAME 8 KiB
`m_prgram`; EMU-CONSENSUS for the convention, not hardware: a real NROM
board has no PRG RAM). With the battery bit the RAM counts as
battery-backed.

### 2.2 NES 2.0 [WIKI "NES 2.0"], DOC

Byte 7 bits 2-3 = 2. Byte 8: mapper bits 8-11 and the submapper; byte 9:
the high nibbles of the PRG and CHR sizes (nibble $F selects the
exponent-multiplier form 2^E * (2M + 1)); byte 10: PRG RAM and PRG NVRAM
as 64 << n bytes (0 = none); byte 11: CHR RAM and CHR NVRAM the same way;
byte 12 bits 0-1: timing (0 NTSC, 1 PAL, 2 multi-region, 3 Dendy).

### 2.3 NROM (mapper 0) [WIKI "NROM"], DOC

PRG ROM of 16 KiB (NROM-128, mirrored at $C000) or 32 KiB (NROM-256) at
$8000-$FFFF; CHR ROM (or RAM) of 8 KiB; mirroring fixed by the board
(solder pads, header bit 0). No registers, no IRQ. AccuracyCoin is an
NROM-256 image with 8 KiB CHR ROM and horizontal mirroring.

## 3. Board

### 3.1 CPU memory map [WIKI "CPU memory map"], DOC

| range | device | N1 implementation |
|---|---|---|
| $0000-$07FF | 2 KiB internal RAM | yes |
| $0800-$1FFF | mirrors of the RAM (A11, A12 ignored) | yes [ACC "RAM Mirroring"] |
| $2000-$2007 | PPU registers, mirrored every 8 bytes up to $3FFF | stand-in: writes are stored per register, reads return open bus |
| $4000-$4013, $4015 | APU | stand-in: open bus, writes ignored |
| $4014 | OAM DMA | stand-in (phase N2) |
| $4016 | write: controller strobe (bit 0); read: controller 1 | yes (section 3.6) |
| $4017 | read: controller 2; write: APU frame counter | controller 2 not connected; frame counter phase N2 |
| $4018-$401F | CPU test mode registers, disabled | open bus |
| $4020-$FFFF | cartridge | mapper (sections 2.3, 3.2, 3.9, 3.10) |

The board decides at which point of a CPU cycle a device samples an
access; every bus access carries the CPU cycle at its start
(runtime/m6502_bus.h).

### 3.2 MMC3 banking and PRG RAM [WIKI "MMC3"], DOC

Registers (mirrored across their 8 KiB range, even and odd addresses):

| address | function |
|---|---|
| $8000 even | bank select: bits 0-2 the register R0-R7 written next, bit 6 PRG mode, bit 7 CHR A12 inversion |
| $8001 odd | bank data for the selected register |
| $A000 even | mirroring: bit 0 = 0 vertical, 1 horizontal (no effect on four-screen boards) |
| $A001 odd | PRG RAM protect: bit 7 enable, bit 6 deny writes |
| $C000 even | IRQ latch |
| $C001 odd | IRQ reload: counter cleared, reloaded at the next clock |
| $E000 even | IRQ disable and acknowledge |
| $E001 odd | IRQ enable |

PRG windows of 8 KiB (-1 and -2 are the last and second-to-last bank):

| PRG mode | $8000 | $A000 | $C000 | $E000 |
|---|---|---|---|---|
| 0 | R6 | R7 | -2 | -1 |
| 1 | -2 | R7 | R6 | -1 |

R6 and R7 use 6 bits; bank numbers wrap at the ROM size. CHR windows of
1 KiB: without inversion R0 (2 KiB, bit 0 ignored) at $0000, R1 (2 KiB)
at $0800, R2-R5 (1 KiB each) at $1000-$1C00; with bit 7 set the two
halves swap.

Power-on state, UNKNOWN on the hardware: the bank registers R0-R7 are
0, 2, 4, 5, 6, 7, 0, 1 (`Mmc3Config::regs_power_on`; CHOICE after the
decision of 2026-10-25 to take the primary oracle's value where the
hardware value is unknown: MesenCE's power-on bytes; MAME has the same
CHR registers and the last two banks for R6 and R7; until 2026-10-25 MAMR
used 0, which showed in prgmap and chrmap of the first frames of Super
Mario Bros. 3 until the game set them); $A001 powers on as 0
(PRG RAM disabled) by default, matching MesenCE with its power-on bytes
0, while MAME starts with $80 (enabled). The value is a board parameter
(`Mmc3Config::ram_ctrl_power_on`); the oracles disagree, so it is not
EMU-CONSENSUS. A disabled PRG RAM reads as open bus.

Bank state of the block key (docs/nes-architecture.md section 3):
(PRG mode, R6, R7) after the wrap, `NesMmc3::bank_state`.

### 3.3 MMC3 IRQ counter and revisions

Rules [BLARGG-MMC3] (TEST-ROM-HW: run by the author on several MMC3
boards; Super Mario Bros. 3 for revision B) and [WIKI "MMC3"] (DOC):

- A counter clock is a filtered rising edge of PPU A12 (section 3.4).
  The counter can be clocked by $2006 writes that toggle A12, whatever
  $2000 selects for the pattern tables.
- On a clock: if the counter is 0 or the reload flag is set, the counter
  is loaded from the latch and the reload flag cleared; otherwise it is
  decremented.
- Revision B (Sharp MMC3B, also "new"; the target game): after the
  load or decrement, if the counter is 0 and the IRQ is enabled, the IRQ
  line is asserted. A latch of 0 therefore gives an IRQ on every clock.
- Revision A (MMC3A, Crystalis board; NEC MMC3B per the wiki): the IRQ
  is asserted only when a clock decrements a nonzero counter to 0, or
  reloads it after a $C001 clear; a counter that reaches 0 normally and
  reloads from a latch of 0 gives no IRQ.
- $C001 clears the counter and sets the reload flag; it never asserts
  the IRQ. $E000 disables the IRQ and releases the line; $E001 enables
  it. The counter runs when the IRQ is disabled and after the IRQ line
  is asserted.
- A pathological case (write $C001, clock, write $C001 again: on the
  next clock the counter is ORed with $80 on revision B, frozen on
  revision A) is described by the readme, used by no game the author
  tested, and not modelled.

The revision is a board parameter (`Mmc3Revision`, default B). The
hash lines record counter, latch, reload flag and enable; the IRQ line
itself is not part of the format because MesenCE hides the CPU's IRQ
state from Lua (docs/nes-oracle-format.md).

### 3.4 MMC3 A12 filter: a CHOICE with a test setup

The PPU fetches background and sprite patterns from both pattern tables
within a scanline, so A12 toggles several times per line; the MMC3 must
count only one rise per line. It does so with a filter on the low phase
of A12 that is referenced to M2, the CPU clock on the cartridge edge.

What is known:

- MEASURED [LIDNARIQ]: about 69 ns from the first rise of PPU A12 (2.4 V)
  to /IRQ falling (1.0 V); /IRQ follows A12 asynchronously, not on an M2
  edge. M2 is high for about 359 ns and low for about 199 ns of the 559 ns
  CPU cycle.
- Not measured [A12-FILTER]: how long A12 must stay low. The competing
  statements are two falling M2 edges (about 6 dots), about five CPU
  cycles (about 15 dots) and about 12 to 16 dots; emulators use 8, 15 or
  16 dots. One forum post notes that nobody has calibrated the threshold
  and that software keeps the events "very short or very long".
- blargg's tests require the IRQ at the same time as the first A12 rise
  of the line [BLARGG-MMC3], consistent with the asynchronous /IRQ.

The model (`NesMmc3::ppu_address`, `Mmc3Config`): a rise of A12 clocks
the counter when A12 was low across at least `m2_edges` falling edges of
M2, counted from the master clock of the fall of A12 to the master clock
of the rise. M2 falls `m2_fall_mclk` master clocks into each CPU cycle
(default 8, from the measured 359 ns high phase: 359 / 559 * 12 = 7.7);
`cpu_phase_mclk` is the master clock of the first CPU cycle's start (the
CPU/PPU alignment, section 3.7). Default `m2_edges` = 3, the value of the
architecture decision of 2026-10-24 (docs/nes-architecture.md section 10),
which sits between the two-edge statement and the five-cycle hypothesis
and separates the short A12 pulses within a line (8 dots of sprite
fetches between pattern table switches) from the long gaps between lines.
A rise in the same master clock as a fall of M2 does not count that fall.
Class: CHOICE. The parameter stays open until the measurement below; the
acceptance tests are blargg's mmc3_irq_tests (local, phase N2) and
blargg's mmc3_test_2, which separate the candidates only partly.

Super Mario Bros. 3 in MAMR (2026-10-25, docs/nes-oracles.md section 6):
`m2_edges` 1 and 2 break the status bar split from frame 12 (the game
runs correctly on the console, so these lengths are excluded, as by
blargg's tests); 3 to 6 give the same counter states as MesenCE in every
frame of a 3000-frame run through World 1-1; 8 to 12 leave the game
unchanged but swallow one A12 low phase of 6 or 7 M2 falls per frame. The
game does not separate 3 to 6.

Test setup to settle it: a Super Mario Bros. 3 board (NES-TSROM, Sharp
MMC3B) and a Crystalis board (MMC3A) in a front-loader with an RP2A03G;
a logic analyzer with at least 100 MS/s on PPU A12, M2 and /IRQ (and
PPU /RD for reference); a test ROM that, with rendering off, produces A12
pulses through $2006 writes (two writes put A12 high, two more put it
low) with a low phase of 1 to 10 CPU cycles in steps of one cycle,
followed by a long low phase and a rise that must clock, and reports
which low durations decremented the counter (counter read back through
the IRQ timing: latch 1, IRQ enabled, the IRQ handler counts). The
result is the smallest low duration in M2 falls that clocks, per board
and per CPU/PPU alignment (repeat over several resets). It replaces the
default of `m2_edges` and may show that the filter counts M2 rises or
uses an analog delay instead, in which case the model changes.

### 3.5 Open bus [WIKI "Open bus behavior"], DOC

A read of an address that no device drives returns the last value that
was on the CPU data bus, usually the last byte of the instruction or its
operand ([ACC "Open Bus"]). The board keeps that byte, updated by every
read that a device answers and by every write, without decay (the CPU
bus has no measurable decay at instruction time scales on the NES; the
PPU's own I/O latch with its decay is docs/nes-ppu-spec.md section 1.2).

The 2A03 has two data buses ([ACC "Internal Data Bus"], TEST-ROM-HW):

- the external bus, which every read and write changes except reads of
  $4015 (the register is inside the 2A03 and does not drive the pins),
  DMA reads included;
- the internal bus of the CPU core, which only the CPU's own read and
  write cycles change, not DMA reads.

A CPU read of $4015 returns bit 5 from the internal bus (the bit is not
driven by the APU); a DMA read that activates $4015 (section 3.8) takes
bit 5 from the external device that answers the DMA address ([ACC "APU
Register Activation"] test 7). Model: `NesBoard::open_bus_` and
`int_bus_`.

### 3.6 Controller port [WIKI "Standard controller", "Controller reading"], DOC

A write to $4016 with bit 0 = 1 holds the controller's shift register
in parallel load; the falling edge of the strobe latches the buttons.
Each read of $4016 returns the next bit in bit 0 (order A, B, Select,
Start, Up, Down, Left, Right) and shifts; after eight reads an official
controller returns 1. While the strobe is high every read returns the
state of A. Bits 1-4 come from the expansion port and the other
controller lines (0 with a standard controller), bits 5-7 are open bus.
The hash lines bind inputs to the strobe count (docs/nes-oracle-format.md
section 7); the board counts writes with bit 0 = 1 (`NesBoard::strobes`).

Phase N2 details, all TEST-ROM-HW:

- The 2A03's OUT0 pin follows the written bit 0 at the start of a put
  cycle (section 6.1), not at the write: a one-cycle strobe written in a
  get cycle (the read-modify-write of DEC $4016) strobes the controller,
  one written in a put cycle does not ([ACC "Controller Strobing"] tests
  3 and 4).
- Reads in consecutive CPU cycles from the same port clock the
  controller once (the /OE line stays low; NES front-loader behaviour,
  [ACC "Controller Clocking"] success code 1; the Famicom clocks twice,
  success code 2, which MesenCE 2.2.1 shows). The halted reads of a DMA
  count as such reads ([ACC "DMA + $4016 Read"]).
- A DMA read with the controller port activated (section 3.8) is a bus
  conflict: bits 0-4 come from the port, bits 5-7 from the device at the
  DMA address ([ACC "DMC DMA Bus Conflicts"]). The DMC receives the same
  byte (CHOICE: AccuracyCoin notes that the DMC's byte differs but cannot
  observe it).

### 3.7 Clocks and CPU/PPU alignment [WIKI "Cycle reference chart"], DOC

NTSC master clock 21.477272 MHz; CPU cycle = 12 master clocks
(1.789773 MHz), PPU dot = 4 master clocks, three dots per CPU cycle; 341
dots per line, 262 lines, the pre-render line one dot short in every
second frame when rendering is on. At power-on the CPU's divider and the
PPU's start in one of several relative phases (the wiki and AccuracyCoin
speak of four CPU/PPU alignments); which one is random on the hardware
(UNKNOWN which is more likely). MesenCE uses one fixed alignment (its
PPU 1 master clock behind the CPU divider, `NesCpu::Reset` without the
randomisation option), its PPU starts at scanline 0, dot 0, and its CPU
spends 8 cycles before the first opcode fetch ([MESEN NesCpu.cpp
NesPpu.cpp]); the interpreter's reset takes the 7 cycles of the reset
sequence (section 4.4). The board takes the alignment as a parameter
(`Mmc3Config::cpu_phase_mclk` so far) and records it in the hash header.

### 3.8 DMA (phase N2)

The DMA unit halts the CPU only on a read cycle and repeats that read
while it waits ([WIKI "DMA"], DOC). The evidence for the details is test
programs, not a published measurement ([ACC "Implicit DMA Abort",
"Explicit DMA Abort", "DMA + $2002 Read", "DMA + $2007 Read", "DMA +
$4016 Read", "DMC DMA Bus Conflicts", "DMA Landing on Write", "DMC DMA +
OAM DMA"], TEST-ROM-HW; blargg's dmc_dma_during_read4 and
sprdma_and_dmc_dma, local only); a logic analyzer trace with date and
person was not found (section 5.5). The model (`NesBoard::stall`, called
by the interpreter before every read cycle):

- OAM DMA ($4014 write in cycle w): the halt in the first read cycle
  after w, one alignment cycle when the halt falls on a get cycle
  (section 6.1), then 256 get/put pairs; 513 cycles when w is a get
  cycle, 514 when it is a put cycle. Gets read the page, puts write
  $2004.
- DMC DMA: a load DMA ($4015 bit 4 with the buffer empty) halts in the
  get cycle of the second APU cycle after the write; a reload DMA (the
  output unit emptied the buffer) halts in the put cycle of the next APU
  cycle. Halt, dummy, alignment until a get cycle, then the read: 3 or 4
  cycles. A DMC get takes precedence over an OAM get in the same cycle.
  Stopping the DMC ($4015 bit 4 = 0) in the APU cycle before a scheduled
  reload DMA leaves only its halt cycle ("explicit abort"); a sample that
  ended in the APU cycle of the reload request still requests it, and
  that DMA is aborted after its halt cycle ("implicit abort"); a halt
  delayed by write cycles cancels an aborted DMA entirely.
- The halted cycles repeat the CPU's read with its side effects ($2002
  clears the vertical blank flag, $2007 advances, $4016/$4017 clock the
  port under the consecutive-read rule of section 3.6).
- 2A03 register activation: when the halted CPU's address is in
  $4000-$401F, a DMA read activates the 2A03 register selected by the low
  five bits of the DMA address as well; with the CPU elsewhere, a DMA
  read of $4000-$401F reads open bus ([ACC "APU Register Activation"]).
- An interrupt poll on a read that the DMA halts is made after the
  halt: the CPU keeps sampling its lines while it waits (INFERENCE; the
  interpreter runs the stall hook before the poll, recompiler/
  m6502_exec.h).

### 3.9 MMC1 (mapper 1) [WIKI "MMC1"], DOC

Added for blargg's suites in nes-test-roms (docs/nes-test-evidence.md
section 4.2), not for the target game; a deviation from the phase plan
approved on 2026-10-26 (docs/nes-architecture.md section 10). Modelled:
the MMC1B on SxROM boards with up to 256 KiB of PRG ROM and 8 KiB of PRG
RAM (`NesMmc1`). Not modelled: SUROM and SXROM (512 KiB PRG ROM, CHR
register bit 4 as PRG A18), SOROM and SXROM (PRG RAM banked by CHR
register bits 2-3), SNROM's PRG RAM disable through CHR register bit 4,
the MMC1A (mapper 155) and the 2ME and NES-EVENT boards. The factory
refuses PRG ROM over 256 KiB and PRG RAM over 8 KiB.

Serial port at $8000-$FFFF (one shift register for all registers):

- A write with bit 7 set clears the shift register and ORs the control
  register with $0C (PRG mode 3); mirroring and CHR mode stay. DOC.
- Five writes with bit 7 clear load a register: bit 0 of each write,
  least significant bit first. On the fifth write address bits 14-13
  select the register and the shift register clears; lower address bits
  are ignored. DOC.
- Consecutive cycles: the wiki states that a serial port written on
  consecutive cycles "ignores every write after the first" (DOC; the
  two writes of a read-modify-write instruction; the wiki names games
  that depend on it). A reset write is never ignored and counts as the
  first write of a pair. The wiki believes the rule also holds when the
  first write does not go to the serial port. The mapper sees only the
  cartridge range $4020-$FFFF and counts every write there; a write
  outside it followed by a cartridge write on the next cycle does not
  occur on the 6502 (INFERENCE: back-to-back writes are the
  read-modify-write pair to one address and the stack pushes of JSR,
  BRK and interrupts, which a read follows).

| register | fifth write at | bits |
|---|---|---|
| control | $8000-$9FFF | 0-1 mirroring: 0 one-screen CIRAM $000, 1 one-screen CIRAM $400, 2 vertical (CIRAM A10 = PPU A10), 3 horizontal (PPU A11); 2-3 PRG mode; 4 CHR mode (0 one 8 KiB bank, 1 two 4 KiB banks) |
| CHR bank 0 | $A000-$BFFF | 4 KiB bank at PPU $0000; in 8 KiB mode the 8 KiB bank, low bit ignored |
| CHR bank 1 | $C000-$DFFF | 4 KiB bank at PPU $1000; ignored in 8 KiB mode |
| PRG bank | $E000-$FFFF | 0-3 the 16 KiB bank; 4 PRG RAM disable on the MMC1B (1 = disabled) |

| PRG mode | $8000-$BFFF | $C000-$FFFF |
|---|---|---|
| 0, 1 | 32 KiB bank (PRG bank AND $E) | its second half |
| 2 | first bank | PRG bank |
| 3 | PRG bank | last bank |

Bank numbers wrap at the ROM size; CHR banks wrap at the CHR ROM or RAM
size. NES 2.0 submapper 5 (SEROM, SHROM, SH1ROM): PRG A14 is not
connected, the 32 KiB are unbanked. A disabled PRG RAM reads as open bus
and ignores writes (INFERENCE: nothing drives the bus).

Power-on: PRG mode 3. The wiki reports tests in which every MMC1
version powered on in mode 3 and others in which this was fragile (DOC
with that reservation). The rest of the control register (one-screen
$000, 8 KiB CHR mode), both CHR banks, the PRG bank (so the PRG RAM is
enabled) and an empty shift register: CHOICE, UNKNOWN on the hardware
(section 5.8).

Bank state of the block key (docs/nes-architecture.md section 3): the
16 KiB banks at $8000 and $C000 after the wrap (`NesMmc1::bank_state`).
The shift register is not part of it: it changes no fetch before the
fifth write.

### 3.10 CNROM (mapper 3) [WIKI "CNROM"], DOC

Added with the MMC1 for the same suites (section 3.9). PRG ROM of 16 or
32 KiB, unbanked as on NROM (16 KiB mirrored at $C000). A write to
$8000-$FFFF loads the CHR bank latch: bits 1-0 select the 8 KiB bank on
the 32 KiB boards, bits 3-0 on the oversize variant (128 KiB). MAMR takes
the latch value modulo the number of 8 KiB banks, which keeps exactly
the connected bits for every power-of-two CHR size. Mirroring is fixed
by solder pads (header bit 0).

Bus conflict: the ROM drives the data bus during the write, the latch
gets the AND of both. The wiki: the original board always has AND-type
conflicts; NES 2.0 submapper 1 means none, 2 AND-type, 0 unknown. MAMR
applies the AND for submappers 0 and 2 (CHOICE for 0, after the wiki's
statement on the original board) and none for 1. The security diodes on
latch bits 4 and 5 are not modelled (the wiki: emulators need not);
mapper 185 (CHR chip selects) is not supported. Power-on value of the
latch: not documented; 0 (CHOICE). Bank state of the block key: 0, the
PRG mapping never changes.

## 4. CPU: the RP2A03 core

### 4.1 No decimal mode [DIE], DATASHEET

The 2A03 contains a 6502 core whose decimal-adjust signals are cut on
the die: the D flag is stored, pushed and pulled, but ADC and SBC are
always binary ([ACC "The Decimal Flag"]). Implemented in
runtime/m6502_ops.h.

### 4.2 Instruction set and cycles [MOS], DATASHEET; [WIKI "CPU unofficial opcodes"], DOC

Documented instructions: flags and cycle counts as in the data sheet;
every cycle is a bus access, the dummy reads of the indexed modes and the
double write of the read-modify-write instructions included ([ACC "Dummy
read cycles", "Dummy write cycles", "Implied Dummy Reads", "Branch Dummy
Reads"]). Verified against SingleStepTests/65x02 nes6502, which is
model-generated (class IMPL of its generator, never hardware) and
against nestest's log (an emulator log, IMPL; docs/nes-test-evidence.md).

Undocumented instructions, by class:

| class | opcodes | model | class of the model |
|---|---|---|---|
| stable combinations | SLO, RLA, SRE, RRA, SAX, LAX, DCP, ISC, ANC, ALR, ARR, SBX, LAS, the NOP forms with their dummy reads | the combination of the two documented operations | DOC [WIKI]; AccuracyCoin tests each addressing mode (TEST-ROM-HW) |
| unstable with a magic constant | ANE $8B, LXA $AB | ANE: A = (A OR $EE) AND X AND imm; LXA: A = X = (A OR $FF) AND imm, that is imm | ANE: UNKNOWN on the hardware (the constant depends on the chip and the bus state), $EE the common model (CHOICE). LXA: $FF, TEST-ROM-HW in the weak sense of [BLARGG-CPU]: the instruction checksums of instr_test-v5 and nes cpu test 5 pass only with $FF ($EE and $00 fail), and both readmes list LXA as tested while marking ANE, SHA, TAS and LAS as unreliable; no console log is published. AccuracyCoin accepts several outcomes for both |
| unstable address-high corruption | SHA $93 $9F, SHX $9E, SHY $9C, TAS $9B | value = register AND (high address byte + 1); on a page cross the high address byte is replaced by that value; when a DMA held the CPU in the read cycle before the write, the high-byte term is dropped | DOC for the base case; the DMA rule TEST-ROM-HW ([ACC "SHA (Indirect),Y"] etc., error code 7); AccuracyCoin accepts several base behaviours ("magic" values) and MAMR shows behaviour 1, as MesenCE |
| jam | KIL: $02 $12 $22 $32 $42 $52 $62 $72 $92 $B2 $D2 $F2 | the CPU stops; only a reset restarts it | DOC; the 11-cycle bus sequence before the halt is the SingleStepTests model (IMPL) |

The suite encodes the same model for the unstable opcodes; the harness
counts those cases separately (20,000 magic-constant, 50,000
address-high cases) so that agreement with a model is never reported as
hardware evidence. Super Mario Bros. 3 uses none of the unstable opcodes
(to be confirmed from the disassembly in phase N3).

### 4.3 Interrupts [WIKI "CPU interrupts"], DOC

- The NMI input is edge-sensitive (the board latches the edge), IRQ is
  level-sensitive. Both are sampled at the start of the last cycle of an
  instruction; an interrupt seen there is taken after the instruction.
  CLI, SEI and PLP change I in their last cycle, after the poll, so the
  poll still sees the old I; RTI restores P before its poll, so the new
  I applies.
- An indexed read without a page cross (abs,X, abs,Y, (zp),Y, the NOP
  abs,X forms) has no correction cycle; its last cycle is the read, and
  it polls at the start of that cycle only, not again at its end. SIM
  [P6502], 2026-10-26: LDA abs,X without a page cross takes an NMI or
  IRQ asserted from the start of its fourth cycle on only after the next
  instruction, exactly as LDA abs does; across a page the limit moves to
  the start of the fifth cycle. NMI and IRQ agree in every position. The
  rule is the wiki's (DOC). MAMR polled such a read a second time at its
  end until 2026-10-26 (recompiler/m6502_table.cpp m65_polls_at;
  docs/nes-architecture.md section 10).
- Branches poll at the start of cycle 2 and, when taken across a page,
  again at the start of cycle 4; a taken branch without a page cross does
  not poll in its third cycle, which delays an interrupt by one
  instruction. This holds for NMI exactly as for IRQ: SIM [P6502],
  2026-10-26 (section 5.7), with [ACC "Interrupt flag latency"]
  (TEST-ROM-HW, IRQ only), the wiki ("ignores IRQ/NMI during its last
  clock", DOC) and blargg's cpu_interrupts_v2 readme ("The same occurs
  for NMI, though that's not tested here", DOC) in agreement. MesenCE
  2.2.1 delays IRQ only (IMPL, `NesCpu.h` `BranchRelative`); Super Mario
  Bros. 3 shows the difference from frame 24 (docs/nes-oracles.md
  section 6, finding S1, a finding against MesenCE).
- Entry: two reads of PC, pushes of PCH, PCL and P (B clear), I set,
  vector read ($FFFA NMI, $FFFE IRQ and BRK). NMI has priority over IRQ.
- Hijack: an NMI seen at the start of the P push (cycle 5) of a BRK or
  an IRQ entry takes over the vector; the BRK or IRQ is lost. The window
  is five cycles: an NMI edge in the last cycle of the preceding
  instruction or in cycles 1-4 ([ACC "NMI Overlap BRK", "NMI Overlap
  IRQ"], TEST-ROM-HW; the wiki says "during the first four ticks").
- BRK and the interrupt entry sequence do not poll: an interrupt seen
  later is taken after the first instruction of the handler ([WIKI "CPU
  interrupts"], [ACC "NMI Overlap BRK"]).
- With a DMA halting the polled read, the poll comes after the halt
  (section 3.8).

### 4.4 Reset and power-on [WIKI "CPU power up state"], DOC

Reset: seven cycles (two reads of PC, three stack reads with S
decremented, the vector at $FFFC); I set; A, X, Y kept. At power-on S
starts at $00 and is $FD after the reset sequence; P = $34 as pushed
(I set). nestest's log starts after this sequence at CYC 7 with S = $FD
and P = $24. Power-on RAM is unspecified on the hardware (UNKNOWN; the
oracle runs use fill 00, MAME fills $00/$FF alternately).

## 5. Open questions and measurement setups

### 5.1 MMC3 A12 filter

Section 3.4 (CHOICE `m2_edges` = 3; test setup there).

### 5.2 MMC3 power-on state

The power-on values of R0-R7 and of $A001 are UNKNOWN; MesenCE and MAME
differ for $A001 (section 3.2). Test setup: a TSROM board, a test ROM in
a CHR-RAM-free variant is not possible on TSROM, so read the state
indirectly: at reset, before writing any MMC3 register, read $6000 twice
after writing a pattern (RAM enabled or not), and read a byte from each
PRG window whose bank content is known from the ROM to infer R6 and R7;
repeat over 20 power cycles with the console cold and warm.

### 5.3 MMC3 revision at latch 0 in the target game

Super Mario Bros. 3 is said never to write 0 to $C000. Check: log every
write to $C000-$DFFF in MesenCE over a play-through of all worlds (input
script, phase N2); if a 0 appears, the revision choice matters and must
follow the board photograph (Sharp MMC3B: revision B).

Result 2026-10-25 (MAMR, `nes_headless --pc-stats`, title, menu, World 1
map and World 1-1, 3000 frames each with and without input): 2953 and
2989 writes to $C000, values $C0 and $C1 only. The revision does not
matter in these runs; a play-through of all worlds is still open.

### 5.4 The PAL board

The board and MMC3 of the European release are unknown. Setup: open a
PAL cartridge, photograph the board name and the MMC3 marking, add the
row to section 1. Phase P (section 7) runs the European ROM; its board
stays UNKNOWN. What the game needs of the board is the same as on the
USA cartridge as far as the runs show (MMC3 registers, 8 KiB PRG RAM,
IRQ latch writes $C0, $C1 and $FF, never 0, docs/nes-smb3-survey.md section 5),
so the MMC3 revision question of section 5.3 is as moot for it.

### 5.5 DMC and OAM DMA cycles

Evidence is AccuracyCoin's expectation and blargg's tests. Setup: logic
analyzer on R/W, the address bus, M2 and RDY of an RP2A03G while the DMC
plays and the CPU reads $2007 or $4016 in a loop; record the halt cycle,
the repeated reads and the transfer cycles for each CPU cycle parity.

### 5.6 CPU/PPU alignment

Which alignments occur and how often is UNKNOWN. Setup: AccuracyCoin's
alignment-dependent tests over 50 power cycles on one console, the
result per run logged; the hash header records the alignment of every
MAMR run.

### 5.7 NMI during a taken branch

Decided 2026-10-26 by simulation (SIM [P6502]): a taken branch without
a page cross delays an NMI by one instruction, as it delays an IRQ.
Method: the program CLI, NOP, NOP, CLC, then a branch, run from reset in
perfect6502; the NMI pin (and, as the counter-check, the IRQ pin) pulled
low at every half-cycle from four cycles before the branch's opcode
fetch to seven cycles after it and held low; the return address pushed
by the interrupt entry tells after which instruction the vector was
fetched. Four variants: BCC taken inside the page, BCC taken across a
page, BCS not taken, and NOP NOP in place of the branch.

| variant (cycles) | the branch completes before the interrupt for an edge in | edges in the branch's later cycles |
|---|---|---|
| NOP, NOP (2 + 2) | the preceding instruction's last cycle and the NOP's first | - |
| not taken (2) | the preceding instruction's last cycle and cycle 1 | - |
| taken, no page cross (3) | the preceding instruction's last cycle and cycle 1 | cycles 2 and 3 are taken after the next instruction (one instruction late) |
| taken, page cross (4) | the preceding instruction's last cycle and cycles 1-3 | - (polls again at the start of cycle 4) |

NMI and IRQ gave the same return address for every edge position in all
four variants. The 2A03 has the same core (section 4.1), so the result
applies to it; what the simulation does not cover is the board's NMI
path from the PPU (the edge is taken as arriving at the CPU pin). MAMR
already applied the rule to NMI; MesenCE does not, so the course of
Super Mario Bros. 3 with input differs from frame 1182 on and that
difference is now a finding against MesenCE (docs/nes-oracles.md section
6). The console setup kept for a confirmation: a test ROM that syncs to
the PPU and places the VBlank NMI edge in steps of one CPU cycle around
the operand cycle of a taken `BNE` inside a page, the handler recording
the return address on the stack; RP2A03G front-loader, several power
cycles (all four alignments).

### 5.8 MMC1 power-on state

Only the PRG mode is documented (section 3.9). Setup: an SNROM board
with a test ROM whose every 16 KiB bank carries the same reset code;
before writing any MMC1 register it reads a marker byte from each PRG
window, writes and reads back $6000 (PRG RAM enabled or not), writes the
nametables through $2006/$2007 and reads them back through the four
nametable addresses (mirroring), and logs the result to PRG RAM; 20
power cycles cold and warm, on an MMC1B and an MMC1A board.

## 6. APU: the parts the CPU sees (phase N2)

Sources: [WIKI "APU", "APU Frame Counter", "APU Length Counter", "APU
DMC", "APU registers"] (DOC); blargg's APU tests (blargg_apu_2005.07.30,
apu_reset; readmes with the author's console results, local only) cited
as [BLARGG-APU name] (TEST-ROM-HW); AccuracyCoin as [ACC name]. Model:
runtime/nes/nes_apu. The waveform channels, the sweep and envelope units,
the mixer and the output stage (phase N4) are specified in
docs/nes-audio-spec.md; the quarter frame clock reaches the envelopes
and the triangle's linear counter, the half frame clock the length
counters and the sweep units there (DOC, [WIKI "APU Frame Counter"]).

### 6.1 Get and put cycles

An APU cycle is two CPU cycles: the first half (get) is where a DMA can
read, the second (put) where it can write ([WIKI "DMA"]). Which CPU
cycles are get cycles is random at power-on (UNKNOWN which is more
likely). CHOICE: the odd CPU cycles of MAMR's numbering (cycle 0 at
power-on), the alignment of the primary oracle. AccuracyCoin and
blargg's tests synchronise to the parity themselves, so the choice is
not visible to them.

### 6.2 Frame counter

- A $4017 write in cycle W starts the new mode at the first get cycle at
  or after W + 3: three cycles after a write in a put cycle, four after
  one in a get cycle ([WIKI "APU Frame Counter"], [ACC "Frame Counter
  IRQ"] tests A-D). Bit 7 set gives an immediate quarter and half frame
  clock one cycle before that.
- 4-step mode, cycles after the start: quarter frame 7457, quarter and
  half 14913, quarter 22371, IRQ flag 29828, quarter, half and IRQ flag
  29829, IRQ flag and restart 29830. 5-step mode: 7457, 14913, 22371,
  quarter and half 37281, restart 37282, no IRQ ([WIKI], [BLARGG-APU
  05.len_timing_mode0, 06.len_timing_mode1], [ACC "Frame Counter
  4-step", "5-step"]).
- The IRQ flag is set in cycles 29828 and 29829 even with the inhibit
  bit set and in 29830 follows the inhibit bit; the IRQ line is asserted
  only while the flag is set and the inhibit bit clear ([ACC "Frame
  Counter IRQ"] tests I-M, TEST-ROM-HW, "a fairly recent discovery").
- A $4015 read clears the flag at the start of the next get cycle, not
  at once: a second read in the following put cycle still sees it (tests
  6 and 7); a set in the clearing cycle wins (tests E-G). Writing $4017
  with bit 6 set clears it at once.
- Power-on: as if $00 were written to $4017 ten cycles before the first
  instruction (cycle -2; the first opcode fetch is cycle 8,
  docs/nes-ppu-spec.md section 13); [BLARGG-APU apu_reset 4017_timing]
  reports a delay of 10, within the readme's 9 to 12. Reset: the last
  value is written again at the same distance.

### 6.3 Length counters

- The load table of [WIKI "APU Length Counter"] (DOC). $4015 bits 0-3
  enable the counters of pulse 1, pulse 2, triangle and noise; a
  disabled counter is 0 and ignores loads. The enables are clear at
  power-on and reset; the triangle's counter keeps its value across a
  reset ([BLARGG-APU apu_reset 4015_cleared, len_ctrs_enabled]).
- Halt: bit 5 of $4000, $4004, $400C and bit 7 of $4008.
- Halt and reload writes reach the counter after the length clock of the
  next CPU cycle: a write in the cycle before a clock acts after that
  clock, and a reload that meets a clock is ignored when the counter was
  not 0 before it ([BLARGG-APU 10.len_halt_timing, 11.len_reload_timing],
  TEST-ROM-HW). Moving the clocks themselves one cycle earlier passes
  these two tests but fails 05/06 and AccuracyCoin's 4-step and 5-step
  tests, which read $4015; the delay belongs to the writes.
- $4015 read bits 0-3: counter > 0.

### 6.4 DMC

- Rate table of [WIKI "APU DMC"] (NTSC, in CPU cycles). The timer counts
  APU cycles and steps at the start of every put cycle; at 0 it clocks
  the output unit (as of the preceding get cycle, so that a DMA read in
  that cycle comes first; CHOICE) and reloads. The period of the next
  round is taken from $4010 one APU cycle after the reload, so a $4010
  write in the cycle of the reload already counts ([ACC "DMC Reload
  Timing"], TEST-ROM-HW; MesenCE 2.2.1 fails this test).
- Memory reader: start address $C000 + 64 * $4012, length 16 * $4013 +
  1, the address wraps from $FFFF to $8000; at the end of a sample the
  loop flag restarts it, otherwise the IRQ flag is set when $4010 bit 7
  is set. Clearing $4010 bit 7 or any $4015 write clears the DMC IRQ
  flag. $4011 sets the output level.
- DMA requests and their timing: section 3.8.
- $4015 read: bit 7 DMC IRQ, bit 6 frame IRQ, bit 4 bytes remaining >
  0, bit 5 from the internal data bus (section 3.5).
- The output level and its delta steps, the mixer and the cycle in which
  the level changes against the timer (finding A1 against MesenCE):
  docs/nes-audio-spec.md sections 6 and 7.

### 6.5 Open questions

- The get/put parity at power-on (section 6.1): AccuracyCoin's
  alignment tests over many power cycles, as in section 5.6.
- The byte the DMC receives in a bus conflict with the controller port
  (section 3.6): needs the RP2A03G's test mode (pin 30), as AccuracyCoin's
  author notes; not settled by any program.

## 7. PAL: the RP2A07 CPU and the RP2C07 PPU (phase P)

The European NES (PAL-B) carries an RP2A07 (the 2A03 with other clock
dividers and APU tables) and an RP2C07 PPU. MAMR runs it as the same
machine with a region parameter (`NesRegion`, docs/nes-architecture.md
section 11); everything not named in this section is the NTSC behaviour
of the sections above (INFERENCE: the wiki describes the PAL parts as
differences from the NTSC ones and names no others; where a test ROM
checks a part on a PAL console it is named). The PPU side is
docs/nes-ppu-spec.md section 18, the sound side docs/nes-audio-spec.md
section 11.

Sources, besides those at the head of this document:

- NESdev wiki pages "Cycle reference chart", "Clock rate", "CPU pin out
  and signal description", "PPU registers", "PPU OAM", "PPU rendering",
  "APU Frame Counter", "APU Noise", "APU DMC", "DMA", "NES 2.0", "INES"
  (retrieved 2026-10-27). Cited as [WIKI page], DOC.
- blargg's pal_apu_tests (christopherpow/nes-test-roms, commit as above,
  directory pal_apu_tests; no licence, run locally). Its readme states
  "They have been tested on a PAL NES and all give a passing result",
  and lists the frame sequencer delays for NTSC and PAL side by side.
  Cited as [BLARGG-PAL name], TEST-ROM-HW.
- blargg's nmi_sync (same collection, directory nmi_sync): a library
  and two demos, demo_pal.nes for PAL, whose readme describes the
  picture a PAL console shows (the left edge of a line drawn by timed
  writes, which "will change randomly each time you press reset" within
  the range the reference lines mark). Cited as [BLARGG-NMISYNC],
  TEST-ROM-HW for the range, not for one position.
- MesenCE 2.2.1 for the conventions of the primary oracle in PAL mode
  (its CPU/PPU alignment, the vertical blank lines, its DMA rule; read
  only, class IMPL), as section 3.7 does for NTSC.

### 7.1 Clocks and frame [WIKI "Cycle reference chart", "Clock rate"]

| quantity | NTSC (RP2A03G/RP2C02G) | PAL (RP2A07/RP2C07) | class |
|---|---|---|---|
| master clock | 236.25 MHz / 11 = 21.477272 MHz | 26.6017125 MHz (6 times the PAL colour subcarrier 4.43361875 MHz) | DOC |
| CPU cycle | 12 master clocks, 1.789773 MHz | 16 master clocks, 1.662607 MHz | DOC |
| PPU dot | 4 master clocks | 5 master clocks | DOC |
| dots per CPU cycle | 3 | 3.2 (16 / 5) | DOC |
| lines per frame | 262 | 312 | DOC |
| dots per line | 341 | 341 | DOC |
| visible lines | 0-239 | 0-239 (the 2C07 blanks line 0 and two columns at each side, PPU spec 18.4) | DOC |
| post-render line | 240 | 240 | DOC |
| vertical blank flag set | (241, 1) | (241, 1) | DOC for the 70 lines; line numbers INFERENCE, IMPL MesenCE (PPU spec 18.1) |
| vertical blank lines | 241-260 (20) | 241-310 (70) | DOC |
| pre-render line | 261 | 311 | INFERENCE from 312 lines with the NTSC order; IMPL MesenCE |
| odd-frame dot skip | yes, rendering on | none: every frame 341 x 312 = 106392 dots | DOC ([WIKI "Clock rate"] gives a fixed 106392; MesenCE: "PAL frames are always the same number of cycles") |
| CPU cycles per frame | 29780.5 (average) | 33247.5 | DOC |
| frame rate | 60.0988 Hz | 50.0070 Hz | DOC |
| vertical blank in CPU cycles | about 2273 | about 7459 | DOC |
| first-frame write block after power-on | about 29658 cycles | about 33132 cycles | DOC [WIKI "PPU registers"] |
| M2 duty cycle | 15/24 (2A03E/G/H) | 19/32 | DOC [WIKI "CPU pin out"] |

The frame rate comes from the console's crystal, not from the mains: the
50 Hz of the power line plays no part in any timing (DOC; the wiki gives
50.0070 Hz from the dividers alone). A PAL television shows 50 fields per
second; that is the frontend's business (docs/frontend.md).

Test proposal for the DOC-only rows: the frame length is settled by
[BLARGG-NMISYNC] demo_pal (its synchronisation measures the frame in CPU
cycles and the line lands inside the reference range only with 33247.5
cycles per frame and no skip); the line numbers of the vertical blank by
a ROM that polls $2002 from an NMI handler with a cycle-counted loop and
reports the cycles from NMI to the flag's clear (70 x 341 / 3.2, about
7459 + 1 dot), on a PAL console.

### 7.2 CPU/PPU alignment on PAL

On NTSC the two dividers (12 and 4) have the common factor 4, so the
relative phase at power-on falls into a few classes (section 3.7,
"four alignments"). On PAL 16 and 5 have no common factor: the pattern
of master clocks repeats every 80 master clocks, which are 5 CPU cycles
and 16 dots, and within it the CPU cycles see 3, 3, 3, 3 and 4 new dots
in some rotation (INFERENCE from the dividers of 7.1). Every power-on
phase gives the same pattern shifted against the CPU's cycle numbering
and the PPU's dot numbering; there is no alignment class a program
could tell apart except by where the pattern starts relative to the
frame, which is what [BLARGG-NMISYNC] demo_pal shows as the random start
position after every reset (TEST-ROM-HW for the randomness).

MAMR's model (CHOICE, the convention of the primary oracle, IMPL
[MESEN NesCpu.cpp] in PAL mode, as section 3.7 for NTSC): CPU cycle k
starts at master clock 16 + 16k of the CPU's count; a read samples the
PPU at 7 master clocks into the cycle, a write at 9, the interrupt
inputs at the end of the cycle (16); the PPU lags one master clock.
In dots processed since power-on (the PPU's dot n covering PPU master
clocks 5(n - 1) .. 5n):

| point of CPU cycle k | NTSC (dots processed) | PAL (dots processed) |
|---|---|---|
| read access | 3k + 4 = floor((12k + 16) / 4) | floor((16k + 22) / 5) |
| write access | 3k + 4 = floor((12k + 18) / 4) | floor((16k + 24) / 5) |
| end (NMI and IRQ sampled) | 3k + 5 = floor((12k + 23) / 4) | floor((16k + 31) / 5) |

On NTSC the read and write points fall into the same dot for every k, so
one number (`access_dot` = 4) describes both; on PAL they differ in two
of every five cycles (k mod 5 = 1 or 2: a write sees one dot more than a
read in the same cycle), so the board keeps the three master clock
offsets for PAL (`NesBoardConfig::pal_read_mclk` 22, `pal_write_mclk`
24, `pal_end_mclk` 31, each relative to 16k on the PPU's master clock
axis). The NTSC path is the old arithmetic, unchanged. The CPU's first
opcode fetch is cycle 8 in both regions (MesenCE's eight power-on
cycles, section 4.4). The MMC3's M2 phase follows: cycle k starts at PPU
master clock 16k + 15 on PAL (12k + 11 on NTSC), M2 falls 10 master
clocks into the cycle on PAL (8 on NTSC; CHOICE in proportion to the
duty cycles of 7.1: M2 high 9.5 of 16 against 7.5 of 12, both ending at
the same point before the cycle's end). Test proposal: [BLARGG-NMISYNC]
demo_pal must show its line inside the reference range (it does for
every phase on a console, so this checks only that MAMR's phase is one
of the possible ones); the MMC3 phase is checked by Super Mario Bros. 3
Europe's status bar split against both oracles (docs/nes-oracles.md
section 8).

### 7.3 APU tables

| quantity | NTSC | PAL | class |
|---|---|---|---|
| frame counter, 4-step, CPU cycles after the start: quarter / quarter+half / quarter / IRQ flag / quarter+half+IRQ / IRQ+restart | 7457, 14913, 22371, 29828, 29829, 29830 | 8313, 16627, 24939, 33252, 33253, 33254 | DOC [WIKI "APU Frame Counter"] (APU cycles 4156.5, 8313.5, 12469.5, 16626, 16626.5, 16627); TEST-ROM-HW [BLARGG-PAL 05.len_timing_mode0, 07.irq_flag_timing, 08.irq_timing] |
| frame counter, 5-step: quarter / quarter+half / quarter / quarter+half / restart | 7457, 14913, 22371, 37281, 37282 | 8313, 16627, 24939, 41565, 41566 | DOC (APU cycles 20782.5, 20783); TEST-ROM-HW [BLARGG-PAL 06.len_timing_mode1] |
| frame IRQ period | 29830 | 33254 | DOC, TEST-ROM-HW |
| noise periods (CPU cycles) | 4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068 | 4, 8, 14, 30, 60, 88, 118, 148, 188, 236, 354, 472, 708, 944, 1890, 3778 | DOC [WIKI "APU Noise"] |
| DMC rates (CPU cycles) | 428, 380, 340, 320, 286, 254, 226, 214, 190, 160, 142, 128, 106, 84, 72, 54 | 398, 354, 316, 298, 276, 236, 210, 198, 176, 148, 132, 118, 98, 78, 66, 50 | DOC [WIKI "APU DMC"] |
| length counter table, envelope, sweep, triangle, mixer | section 6.3, audio spec | the same | INFERENCE (the wiki names no difference); TEST-ROM-HW for the length table [BLARGG-PAL 02.len_table] |
| $4017 write delay (first get cycle >= W + 3), the IRQ flag in three consecutive cycles, the $4015 clear at the next get cycle | section 6.2 | the same | TEST-ROM-HW [BLARGG-PAL 03.irq_flag, 07.irq_flag_timing]: "the IRQ flag is actually effectively set three clocks in a row" for both regions |
| power-on $4017 write, 10 cycles before the first instruction | section 6.2 | the same | INFERENCE; TEST-ROM-HW only as far as [BLARGG-PAL 01.len_ctr] and 05 pass from power-on |
| DMC timer at power-on | 428 (first expiry, CHOICE) | 398, the rate-0 period (CHOICE by the same rule) | CHOICE |

The readme of [BLARGG-PAL] gives the PAL sequencer as the delays 8315,
8314, 8312, 8314 after a $4017 write of $00 (NTSC 7459, 7456, 7458,
7458): the steps fall 8315, 16629, 24941 and 33255 cycles after the
write, which is 2 cycles of write delay plus 8313, 16627, 24939 and
33253 (NTSC the same 2 plus 7457, 14913, 22371, 29829). Mode 1 (bit 7
set): 1, then 8314, 8314, 8312, 8314, 8312, i.e. the immediate clock and
then 8315, 16629, 24941, 33255, 41567 after the write. The model of
section 6.2 with the PAL numbers of the table gives exactly these.

The two DMC rates the wiki marks as off the intended tuning ($4 and $C)
are what the chip does (DOC); a game that plays them sounds as on the
console.

### 7.4 DMA on the RP2A07

[WIKI "DMA"] (DOC) says the 2A07 "fixes" the extra reads of the halted
CPU that corrupt controller and $2007 reads on the 2A03, that the
mechanism is not understood, and that it is not known whether the DMC
DMA bugs of section 3.8 exist on the 2A07; a collision of a joypad read
with a DMA read does not clock the other joypad there. MesenCE (IMPL)
lets a DMA halt the CPU only at the opcode fetch of an instruction on
PAL and never repeats a joypad read.

MAMR on PAL (CHOICE, decided 2026-10-27 by the rule of
docs/nes-architecture.md section 10 that an UNKNOWN hardware value takes
the primary oracle's): a DMA (DMC or OAM) halts the CPU only in an opcode
fetch cycle, the cycle with SYNC high, which is also the first cycle of
an interrupt entry (the fetch whose opcode is discarded); the halt, the
dummy and alignment cycles and the transfers are then those of section
3.8, repeating the opcode fetch. Reads of operands and data never halt.
This fits the wiki's statement that the 2A07 does not corrupt
controller and $2007 reads (the repeated read is always an opcode fetch)
but is not established by it. Runtime: `M65Bus::stall_sync_only`, set by
the board for PAL; the interpreter and the emitted blocks call the
stall hook only before the SYNC cycle then; on NTSC nothing changes.
Evidence from the comparison (docs/nes-oracles.md section 8): Super
Mario Bros. 3 Europe plays a DMC sample from frame 238 of the input
script; with the NTSC rule the game reads its input at other times than
in MesenCE from frame 551 on (the MMC3 IRQ meets the wait loop at
another instruction, frame 239), with the SYNC rule the strobes (inp) are
equal in all 3000 frames. The DMC DMA bugs of section 3.8 (the implicit
abort, the halt delayed by writes) are kept for PAL (UNKNOWN whether the
2A07 has them).

Test proposal: blargg's dmc_dma_during_read4 and sprdma_and_dmc_dma on a
PAL console (they print the observed cycle counts and reads; their NTSC
expectations do not apply), and AccuracyCoin's DMA pages on a PAL
console: with the SYNC rule a DMC fetch requested during a long
instruction waits for the next opcode fetch, so the cycle counts they
report would show it.

### 7.5 Region of a cartridge

The cartridge does not know the region; the header may say it and is
often wrong:

- iNES 1.0 byte 9 bit 0 (1 = PAL) is "rarely set" and honoured by few
  emulators; byte 10 bits 0-1 are not part of the official format
  ([WIKI "INES"], DOC). MAMR reads byte 9 bit 0 only (section 2.1) and
  never byte 10.
- NES 2.0 byte 12 bits 0-1: 0 RP2C02 (NTSC), 1 RP2C07 (PAL), 2
  multiple-region, 3 UA6538 (Dendy) ([WIKI "NES 2.0"], DOC). MAMR runs
  multiple-region as NTSC (CHOICE: the game adapts itself) and refuses
  Dendy (not modelled).
- The cartridge database (`nes_cart_identify`, section 1) names the
  region of the boards it knows. When it knows the ROM, its region wins
  over the header (CHOICE, the rule of this project: a header is a
  property of a dump, the database of the release). The Europe file of
  Super Mario Bros. 3 read on 2026-10-27 has an iNES 1.0 header with
  byte 9 = 0, i.e. NTSC; the database makes it PAL.
- A run may force the region (`nes_headless --region`, the machine option
  `region`), for test ROMs whose header says nothing: all ten
  [BLARGG-PAL] files and demo_pal.nes carry byte 9 = 0.

The resolved region and its source (database, header, forced) are
reported by the tools and recorded in the hash header (`region=`) and in
the save state (docs/machine-interface.md section 6, NES state version
3).
