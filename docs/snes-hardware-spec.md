# Hardware Specification: SNES (Super Famicom)

Register-level reference for the SNES runtime (docs/snes-architecture.md).
Sections 1 to 3 cover the board skeleton of phase S5: memory map, time
skeleton and DMA/HDMA (runtime/snes/); section 4 records decisions about
the 65816 core (phase S1); section 5 keeps the open hardware questions
of the research package A (2026-10-24) with their evidence, the choice
the code makes and the console test that would settle each. Later work
streams append their sections (PPU, S-SMP and S-DSP, 65816 bus timing),
each with its own number, sources and "where the sources differ" list,
so that earlier sections stay untouched.

**Sources:**

- **fullsnes** (Martin Korth, problemkaputt.de/fullsnes.htm, retrieved
  2026-10-24). Cited by section title, e.g. [FS "SNES Memory Map"].
- **Anomie's documents** timing.txt, regs.txt, memmap.txt and the DMA
  text, read through the mirrors wiki.superfamicom.org (timing,
  registers, memory-mapping, dma-and-hdma) and snesdev.mesen.ca,
  retrieved 2026-10-24. Cited as [ANOMIE file].
- **SNESdev wiki** (snes.nesdev.org, pages Timing, MMIO registers and DMA
  registers, retrieved 2026-10-24). Often a copy of fullsnes, then not an
  independent source. Cited as [WIKI page].
- **nesdev forum thread t=24391** (paulb_nl, September 2026): IRQ timing
  measured with test ROMs on one console (CPU 2, PPU1 1, PPU2 3). Cited as
  [PAULB].
- **Primary sources added on 2026-10-26** (the primary-source review; found by
  the measurement search of 2026-10-25, re-checked here as stated per item):
  srg320's logic-analyzer captures of a console in
  MiSTer-devel/SNES_MiSTer, folder `hw/LA captures/`
  (https://github.com/MiSTer-devel/SNES_MiSTer, commits 9a1955e6
  2024-09-18, f0e6d4db 2024-09-25, 68fe1a8c 2025-09-20; images only,
  about 85 MHz, revision not named), cited as [SRG320 LA]; Ownasaurus'
  logic-analyzer measurement of the controller port (MiSTer SNES_MiSTer
  issue #208, comment of 2020-02-13; US console, revision not named,
  PNG only), cited as [OWNA]; Quietust's transistor netlists of the
  S-PPU1 and S-PPU2 from die photographs (Visual 5C77 and Visual 5C78,
  https://www.qmtpro.com/~nes/chipimages/visual5c77/ and /visual5c78/,
  no licence seen: cited, nothing copied; read statically, not
  simulated, here 2026-10-26), cited as [VISUAL 5C77] and [VISUAL 5C78];
  rgalland's S-CPU-A schematic (https://github.com/rgalland/SNES_S-CPU_Schematics,
  GPL-3, read as a netlist by the search of 2026-10-25), cited as
  [RGALLAND]; khaydarian's spla oscilloscope survey of both PPUs
  (https://github.com/khaydarian/spla, blog 2020-03-07, SNS-CPU-RGB-02,
  S-CPU B, 5C77-01, 5C78-03), cited as [SPLA].
- **MAME software list** hash/snes.xml (CC0, mamedev/mame commit
  9d8a6727a206fc822b8b69d67a51e6fd7dbf4d4b): PCB names of known ROMs.
- **Emulators as references, not as hardware evidence:** ares (ISC,
  ares-emulator/ares commit c76aaffa6e69778baf9a66d1da04298ac2ed7d1d:
  `ares/sfc/cpu/timing.cpp`, `irq.cpp`, `dma.cpp`, `memory.cpp`,
  `io.cpp`, `cpu.cpp`, `ares/sfc/ppu/counter/inline.hpp`,
  `ares/sfc/memory/inline.hpp`, `mia/medium/super-famicom.cpp`,
  `ares/System/Super Famicom/boards.bml`), cited as [ARES file function];
  MesenCE (GPL-3, commit 4b8a196e, read only), cited as [MESEN]; LakeSnes
  (angelo-wf/LakeSnes, archived; no licence file was found by the
  research of 2026-10-24, so it is cited as a behaviour reference only,
  never as code and never as MIT), cited by name.

ares is a structure reference. Most of the code is written from the
documentation, but two parts follow ares structurally: the order of the
HDMA steps (reload, transfer, advance; the count byte read every line;
the do-transfer flag set at setup; the shortened indirect reload at the
end of the last active channel) and the board rule model with its
address-bit removal and the folding of odd ROM sizes (cart_drop_bits,
cart_mirror, after ares Bus::reduce and Bus::mirror). The ISC notice is
in third_party/ares/LICENSE.

Provenance classes (as in the hardware facts research of 2026-10-25):

| Class | Meaning |
|---|---|
| DATASHEET | data sheet, schematic, die analysis |
| MEASURED | measured on a console with an instrument |
| TEST-ROM-HW | a test ROM run on a console, result published |
| DOC | hardware documentation based on tests, method not given (fullsnes, Anomie, SNESdev wiki) |
| EMU-CONSENSUS | several emulator lines agree (bsnes/higan/ares count as one line) |
| IMPL | one emulator line only (usually ares) |
| INFERENCE | concluded without direct evidence |
| UNKNOWN | no usable source |
| CHOICE | this runtime's decision where the sources are silent or differ |

All times are master clocks since power-on: 21.477273 MHz (945/44 MHz)
on NTSC, 21.281370 MHz (17.734475 MHz x 6/5) on PAL (DOC [FS "SNES
Timing Oscillators"], [WIKI Timing]). The system is chosen at power-on
from the cartridge (2.9).

## 1. Memory map

Code: runtime/snes/snes_cart.{h,cpp}, snes_map.{h,cpp}.

### 1.1 Address space

| Banks | Offset | Region | Class |
|---|---|---|---|
| 00-3F, 80-BF | 0000-1FFF | first 8 KiB of WRAM | DOC [FS "SNES Memory Map"] |
| 00-3F, 80-BF | 2000-20FF, 2200-3FFF | unused (open bus) | DOC |
| 00-3F, 80-BF | 2100-21FF | B-bus: PPU $00-$3F, S-SMP ports $40-$7F (four, mirrored), WRAM port $80-$83, expansion $84-$FF | DOC [FS "SNES I/O Map"] |
| 00-3F, 80-BF | 4000-43FF | CPU registers (joypad serial, NMI/IRQ, maths, DMA); unused ones open bus | DOC [ANOMIE memmap.txt], [FS "SNES I/O Map"] |
| 00-3F, 80-BF | 4400-5FFF | unused A-bus (open bus) | DOC [ANOMIE memmap.txt] |
| 00-3F, 80-BF | 6000-7FFF | expansion; cartridge only on boards that map it (HiROM SRAM) | DOC |
| 7E-7F | 0000-FFFF | WRAM, 128 KiB | DOC |
| everything else | | cartridge, by the board rules of 1.2 | DOC |

Open bus: a CPU read of nothing returns the last byte on the data bus
(MDR). Reads of the CPU's own registers $4000-$43FF do not drive the bus
and leave the MDR unchanged (DOC [ANOMIE memmap.txt note 1]; ares, bsnes
and MesenCE agree). CPU writes and every DMA byte set the MDR (CHOICE;
MesenCE has not counted CPU writes since 2025). How long the console
holds the value is MEASURED with a conflict between two measurements
and is board-dependent: lidnariq, 2023-03-22, console revision 1-1-1,
a cartridge carrying only an SST39SF040 and a CIC, logic analyzer, raw
data attached to nesdev t=24536
(https://forums.nesdev.org/viewtopic.php?t=24536): "There is only
normal open bus, and it decays fairly quickly (roughly 2 vsyncs)"; an
earlier post in the same thread measured "the value experimentally does
not decay", later annotated that lidnariq's findings contradict it
"unless it varies by cartridge or console chipset"; the SNESdev wiki
(https://snes.nesdev.org/wiki/Open_bus) notes that the cartridge can
hold the value. Not modelled (the MDR never decays here; a game that
reads open bus later than a frame after the last driven cycle would see
a board-dependent value on the console). Unused
bits: $4016 bits 7-2, $4017 bits 7-5, $4210 bits 6-4, $4211 bits 6-0,
$4212 bits 5-1 [FS "SNES Unpredictable Things"] (DOC).

WRAM port [FS "SNES Memory Work RAM Access"] (DOC): WMDATA $2180 reads or
writes WRAM at the 17-bit address WMADDL/M/H ($2181-$2183, write-only,
reads are open bus) and increments it, wrapping at 128 KiB.

### 1.2 Cartridge, header and boards

Header at $FFC0-$FFFF of bank 00: ROM offset $7FC0 (LoROM), $FFC0 (HiROM),
$40FFC0 (ExHiROM) [FS "SNES Cartridge ROM Header"] (DOC). Fields: title
21 bytes, $FFD5 map mode (bit 4 FastROM, low nibble 0 LoROM, 1 HiROM, 2
S-DD1, 3 SA-1, 5 ExHiROM, A SPC7110), $FFD6 chipset (00-02 plain, x3 and
above a coprocessor, high nibble = chip), $FFD7 ROM size and $FFD8 SRAM
size as (1 << n) KiB, $FFD9 country, $FFDB version, $FFDC complement,
$FFDE checksum, $FFEA NMI and $FFFC reset vector.

- Country: 50 Hz for 02-0C and 11, 60 Hz for 00, 01, 0D, 0F and 10
  (Brazil, PAL-M at 60 Hz) (DOC [FS "SNES Cartridge ROM Header"]); 0E and
  12 and above are unknown in fullsnes and taken as 60 Hz (CHOICE, as
  LakeSnes; ares takes 50 Hz, MesenCE 50 Hz for 12); 0B is "China, Hong
  Kong", 50 Hz, in fullsnes and "ROC", 60 Hz, in ares. The console, not
  the cartridge, decides the region: for a known ROM the profile (1.2,
  identity) wins and a different header code gives a warning.
- Copier header: present when (image size AND 3FFh) = 200h, 512 bytes,
  removed before anything else (DOC). The SHA-1 identity is over the ROM
  data without it (MAMR convention, tools/romtool/hash.h).
- Checksum: all ROM bytes added with the header's four checksum bytes
  counted as FF,FF,00,00; a size that is no power of two is first
  mirrored up to the next one: the largest power-of-two part, then the
  rest repeated (10 Mbit = 8 Mbit + 4 x 2 Mbit) (DOC). The same fold
  maps such ROMs into the address space (cart_mirror).
- Detection (CHOICE): each candidate header scores complement + checksum
  = FFFFh (4), stored = computed checksum (2), map mode in 20h-3Fh (1)
  and matching the layout (2), plausible size code (1), printable title
  (1); a reset vector below $8000 rules a candidate out. The layout, not
  the map mode byte, decides LoROM or HiROM (ares mia instead looks at
  the map mode byte first and scores the opcode under the reset vector).
  Refused with a message: ExHiROM (header at $40FFC0 or mode 5), ROMs
  above 4 MiB, map modes 2/3/5/A, chipsets above 02h, images below
  32 KiB or not a multiple of 32 KiB.

Board choice: by ROM identity, not by ROM size. The cartridge database
docs/snes-cartridge-db.md (runtime/snes/snes_cart.cpp KNOWN_ROMS, 116
releases of 2026-10-24 from two merged research passes, with mapper,
SRAM, chip, PCB, region, source and class) gives the board: the PCB's family where a source names the PCB
(74LS139 boards -> LoRomSramB, MAD-1 boards -> LoRomSramMad), else the
board the mapper and SRAM size imply. The three first entries and their
sources: Zelda (Germany) 2e62494967fb0afdf5da1635607f9641df7c6559,
SHVC-1A3B-13 (DOC [MAME snes.xml zelda3g] and the snescentral cartridge
page) against SHVC-1A3M-10 (the snescentral PAL board photo), a
conflict recorded in the database, decoded as 74LS139 (the verified
board; the same map for this ROM either way);
Zelda (USA) 6d4f10a8b10e10dbe624cb23cf03b88bb8252973, SHVC-1A3B-12 (DOC
[MAME snes.xml zelda3u]); Secret of Mana (Europe)
d9aaf3119784887475da9548000738e1da84bee6, HiRom, SHVC-1J3M-11
(INFERENCE: MAME manaa names no PCB; manag, Germany, is SHVC-1J3M-11).
A known ROM with an enhancement chip (SA-1, SuperFX, DSP-1 in the
database) is refused by name; which chips would need a firmware dump is
in the database's section 2.

Only an unknown ROM gets a board from its header (IMPL, after ares mia's
heuristic), with a warning: LoROM without SRAM -> LoRom, LoROM with SRAM
up to 2 MiB -> LoRomSramAny, above -> LoRomSramMad, HiROM -> HiRom.

Board rules (offset = address with the masked bits removed, then folded
into the size):

| Board type | ROM | SRAM | Class |
|---|---|---|---|
| LoRom (A0N: 1A0N, 2A0N, BA0N, YA0N) | 00-7D, 80-FF:8000-FFFF and 40-7D, C0-FF:0000-7FFF, mask 8000h (ROM /OE on /ROMSEL, A15 not connected) | - | DOC [FS "SNES Cart LoROM Mapping"] + board analysis |
| LoRomSramB (74LS139: 1A1B, 1A3B-11..13, 1A5B) | 00-1F, 80-9F:8000-FFFF, mask 8000h; 20-3F open | 70-7D, F0-FF:0000-FFFF, mask 8000h | DOC [FS], board analysis |
| LoRomSram2A (2A3B) | 00-3F, 80-BF:8000-FFFF, mask 8000h | 70-7D, F0-FF:0000-7FFF | DOC [FS] |
| LoRomSramMad (MAD-1: 1A3M and relatives) | 00-7D, 80-FF:8000-FFFF, mask 8000h | 70-7D, F0-FF:0000-7FFF | DOC [FS], MAD-1 dump |
| LoRomSramAny (heuristic only) | 00-3F, 80-BF:8000-FFFF | 70-7D, F0-FF:0000-FFFF | IMPL [ARES boards.bml LOROM-RAM#A]: the union of B and 2A3B |
| HiRom (1J0N, 1J3M and relatives) | 00-3F, 80-BF:8000-FFFF and 40-7D, C0-FF:0000-FFFF | 20-3F, A0-BF:6000-7FFF, mask E000h (one 8 KiB page per bank) | DOC [FS "SNES Cart HiROM Mapping"] |

Not modelled: HiROM boards 2J3M/2J5M with SRAM at 10-1F/30-3F/90-9F/B0-BF.

### 1.3 Bus cycle costs

| Address | Clocks | Class |
|---|---|---|
| 00-3F, 80-BF:0000-1FFF | 8 | DOC [ANOMIE memmap.txt v1.1, measured per 256-byte block], [FS "SNES Memory Map"] |
| 00-3F, 80-BF:2000-3FFF | 6 | DOC |
| 00-3F, 80-BF:4000-41FF | 12 | DOC |
| 00-3F, 80-BF:4200-5FFF | 6 | DOC |
| 00-3F, 80-BF:6000-7FFF | 8 | DOC |
| 00-3F:8000-FFFF, 40-7F:0000-FFFF | 8 | DOC |
| 80-BF:8000-FFFF, C0-FF:0000-FFFF | 8, or 6 with MEMSEL ($420D) bit 0 | DOC [FS "SNES Memory Control"] |
| internal CPU cycle | 6 | DOC [WIKI Timing] |

Same table as [ARES memory.cpp wait].

### 1.4 I/O hooks and bus timestamps (runtime/snes/snes_map.h)

```text
struct IoPort {
    u8 (*read)(void* ctx, u16 addr, u8 open_bus, u64 t);
    void (*write)(void* ctx, u16 addr, u8 data, u64 t);
    void* ctx;
};
Map::ppu      B-bus $2100-$213F   addr = $2100 + reg
Map::apu      B-bus $2140-$217F   addr = $2140 + reg (device masks to 4 ports)
Map::bbus_ext B-bus $2184-$21FF
Map::cpu_io   $4000-$43FF         addr = 16-bit offset (bank does not matter)
```

`t` is the moment the data is sampled, `open_bus` the value a read
returns for undriven bits. The same B-bus hooks serve CPU accesses
through $21xx and DMA (Map::bbus_read/write).

Timestamps: the 65816 bus passes the start of each bus cycle;
Map::read8/write8 take that start and hand the devices the sample time,
bus_read_time = start + cost - 4 and bus_write_time = start + cost, cost
= speed(addr) (IMPL [ARES memory.cpp read/write]: step(cost - 4), read,
step(4); step(cost), write). The hold windows of RDNMI and TIMEUP, the
HBlank edges of HVBJOY and the S-SMP port catch-up are measured against
these times. DMA calls bus_read/bus_write with sample times directly
(3.2).

Where the sources differ (section 1):

- Open bus decay: lidnariq 2023 (decays in about two frames, one
  console, one bare cartridge) against the earlier "does not decay" in
  the same thread; the cartridge's bus drivers decide it. Both kept as
  measurements; not modelled.

- Plain LoROM mirror at 40-7D:0000-7FFF: in fullsnes and in ares'
  database boards (SHVC-1A0N, 2A0N, BA0N, YA0N); only ares' heuristic
  board leaves it open, MesenCE never maps it. Taken from fullsnes.
- LoROM with SRAM: the board is a matter of the PCB, not of the ROM
  size. The earlier rule "up to 2 MiB -> ROM 00-3F" is ares' heuristic
  and mapped ROM into 20-3F for Zelda; Zelda's 74LS139 board maps
  00-1F only. The heuristic stays for unknown ROMs only.
- Big LoROM (> 2 MiB): fullsnes' prose says banks 40 and up appear in
  both halves of 40-6F; its own board table and the MAD-1 /ROMCE logic
  (A15 = 1 in LoROM mode) say upper halves only. Taken as upper halves.
- HiROM SRAM: fullsnes' overview says 30-3F, "usually also mirrored to
  20-2F"; its board table (1J3M) and ares say 20-3F. Taken as 20-3F.

## 2. Time skeleton

Code: runtime/snes/snes_timing.{h,cpp}.

### 2.1 Lines, fields, dots

| Item | Value | Class |
|---|---|---|
| line | 1364 clocks | DOC [FS "SNES Timing H/V Counters"], [WIKI Timing] |
| short line | NTSC only: V=240 of field 1 ($213F bit 7 = 1) without interlace, 1360 clocks, all dots 4 clocks | DOC |
| long line | PAL only, and only with interlace on: V=311 of field 1, 1368 clocks, 341 dots, dot 340 = clocks 1364-1367; a progressive PAL field has 312 lines of 1364 and no short line | DOC [FS "Long and Short Scanlines"; "H=340, V=311, F=1 this is last PPU-dot in long scanlines (50Hz+Interlace)"], [WIKI Timing: "Long scanline: PAL with interlace on, field=1, V=311", "Short scanline: NTSC with interlace off, field=1, V=240"]; ares does the same (counter/inline.hpp: PAL, interlace, field 1, V=311 -> +4); dot mapping IMPL [ARES counter hdot]; structure of the extra clocks UNKNOWN. ctest `snes_timing` checks both shapes; the PAL target game writes SETINI=0 throughout, so its 3000-frame equality with aresref (docs/snes-oracles.md) does not exercise the long line |
| lines per field | 262 NTSC, 312 PAL; one more in field 0 with interlace | DOC [FS "H/V Events"], [WIKI Timing] |
| field pair | NTSC 714732 clocks ((262+262)*1364-4), interlaced 716100; PAL 851136, interlaced 852504 (313*1364 + 311*1364+1368) | DOC; sums derived (fullsnes' "426936" is a typo) |
| dots | 340 per line (0-339); 341 = 1364/4 is a count of 4-clock units | DOC [ANOMIE timing.txt] |
| long dots | 323 and 327 take 6 clocks (H 1292-1297, 1310-1315), not on the short line | DOC [ANOMIE] + TEST-ROM-HW (fullsnes' own latch statistics: dots 323 and 327 six times each) + MEASURED (lidnariq 2016) |
| power-on | V=0, H=0, field 0 | DOC [FS "H/V Events"] |
| interlace latch | SETINI bit 0 passes a latch that follows the register outside VBlank and holds from the start of VBlank (V=225, 240 with overscan) to V=0; the field length (263/313), the NTSC short line and the PAL long line read only the latched bit, so a write before V=vdisp shapes the running field, a write in VBlank the next one | DATASHEET + INFERENCE [VISUAL 5C78] node 3440, [VISUAL 5C77] node 2702 and the field length mux (5.8); the closing about one dot after the V step is taken at the line boundary (CHOICE); ares V=128, MesenCE V=0/240, LakeSnes V=225 (IMPL) |
| overscan | SETINI bit 2 counts at once | IMPL [ARES ppu/io.cpp]; no DOC |
| VBlank | from V=225, V=240 with overscan, to V=0; both systems (PAL 87/72 lines) | DOC [WIKI Timing] |

### 2.2 Events of a field

All events are scheduled in closed form from the field start; the NMI and
IRQ logic samples every 4 clocks at clocks 2 mod 4 and looks at the
counters 2 (NMI) or 10 (IRQ) clocks back [ARES timing.cpp step, irq.cpp]
[MESEN schematic model] (EMU-CONSENSUS). The positions in a line are the
same on PAL (IMPL: ares and MesenCE have no region case; INFERENCE: the
S-CPU has no PAL input; no PAL measurement known).

| Event | When | Effect | Class |
|---|---|---|---|
| HDMA setup | V=0, H = 12 + (field start mod 8) = 12 or 16; always clock 4 mod 8 | channels reload (3.4); the first table byte is read at H=28 or 32 here | trigger EMU-CONSENSUS (ares version 2, MesenCE); that it fits Anomie's "about V=0 H=6" (dots, 24 clocks) is INFERENCE |
| DRAM refresh | every line, H = 538 - (line start mod 8) = 538 or 534 | CPU loses 40 clocks in one piece | position DOC [ANOMIE timing.txt: 538 first, then the multiple of 8 closest to 536] + TEST-ROM-HW (fullsnes latch statistics fit the 534 phase); the 40 clocks in one piece MEASURED [SRG320 LA] (5.6) |
| HDMA line | V=0..vdisp-1, trigger H=1104 | one HDMA step (3.4); its first byte is written at H=1124 or 1128 here (read 4 earlier) | trigger EMU-CONSENSUS (bsnes/ares, MesenCE, LakeSnes); that Anomie's "transfer begins at dot 278" (= 1112) means the first byte after this trigger is INFERENCE |
| NMI flag | V=vdisp, H=2 | RDNMI bit 7 set, held 4 clocks | DOC (Anomie, fullsnes "H=0.5") + EMU-CONSENSUS (hold) |
| NMI | V=vdisp, H=6, when $4200 bit 7 is set then | NMI edge to the CPU | EMU-CONSENSUS (ares, MesenCE schematic model) |
| NMI flag clear | V=0, H=2 | RDNMI bit 7 cleared | CHOICE: EMU-CONSENSUS (ares; MesenCE's schematic reading: the PPU clears VBLANK at H=0, "which will be picked up on H=2") over DOC H=0 (Anomie, fullsnes), see below |
| IRQ flag | first tick at which the comparator rises (2.4) | TIMEUP bit 7 set, held 4 clocks | DOC + TEST-ROM-HW (2.4) |
| IRQ | 4 clocks after the flag | IRQ line to the CPU (level, until TIMEUP is read) | EMU-CONSENSUS |
| joypad start | V=vdisp, the one clock that is a multiple of 256 with 130 <= H <= 384, when $4200 bit 0 is set | auto-read (2.6) | DOC [ANOMIE: "begins between dots 32.5 and 95.5 of the first V-Blank scanline" = 130..382, "thereafter some multiple of 256 cycles after the start of the previous read"] + TEST-ROM-HW (Jonas Quinn's tests, cited in bsnes PR #78 by Near, https://github.com/bsnes-emu/bsnes/pull/78: Anomie's dots times 4 give 130-382, on the 256-cycle grid that becomes 130-384, "Jonas Quinn confirmed that with his testing"); ares and MesenCE use the grid |
| joypad end | 2 x 128 + 16 x 256 = 4224 clocks later | JOY1-4 valid, HVBJOY bit 0 clear | DOC [ANOMIE: "ends 4224 master cycles later"] + TEST-ROM-HW (bsnes PR #78: "2x128 + 16x256 ... 34 total states"); the latch pulse: MEASURED twice, 12.04 us = 258.6 clocks [OWNA] and "a 12us wide, positive going data latch pulse on pin 3" (J. Christy, "SNES Protocols", 1996, https://www.repairfaq.org/REPAIR/F_SNES.html; revision unknown), i.e. both 128-clock latch steps; the clock period 11.91 us = 255.8 clocks with 5.9 us = 126.7 clocks low [OWNA] (2.6, 5.3) |
| field end | after the last line | next field | DOC |

The S-CPU version (1 or 2) changes the refresh and HDMA setup positions
in ares only (IMPL, a single forum statement by byuu, 2016); not modelled
(CHOICE): no other source supports it, version 1 (5A22-01) is only in
early NTSC consoles, and every PAL console reports 2. RDNMI reports the
version. Inside the 40 clocks the REFRESH line pulses with an 8-clock
period (srg320's statement of five pulses; lidnariq's revision 1 trace
shows the 8-clock period and the 40-clock envelope, 5.6); the CPU sees
one hold. The revision 1 positions stay open (5.6).

The grids (refresh phase, HDMA setup phase, the 256-clock joypad grid
and the 8-clock DMA counter) count from power-on, after a reset from
the release of the button (both modes; ares restarts its counter too).
Anomie says the DMA counter runs "since reset"; the reset button
restarts the grids and the PPU counters together at its release (2.8,
5.4).

### 2.3 NMI, RDNMI ($4210), NMITIMEN ($4200)

- RDNMI bit 7 is set at the start of VBlank whether NMI is enabled or not
  and cleared at its end (DOC [FS "SNES PPU Interrupts"]).
- A read returns the flag and clears it, except during the 4-clock hold
  after it was set (EMU-CONSENSUS; Terranigma depends on it). The read's
  sample time is 4 clocks before the end of its bus cycle (1.4).
- Bits 3-0: CPU version 2 (S-CPU A, S-CPU B and S-CPUN A all report 2)
  (DOC [WIKI MMIO registers]).
- Setting $4200 bit 7 while the flag stands gives an NMI; disabling and
  enabling again during VBlank gives another one (DOC [WIKI MMIO
  registers NMITIMEN]). The CPU takes it after the following instruction
  (DOC [WIKI errata]; Alien vs. Predator, Pocky & Rocky, Jaki Crush);
  the time skeleton sets nmi_pending at once, with an Nmi event at the
  write's clock (2.8), and the runner adds the delay.
- Interrupts and DMA: an NMI or IRQ that arrives while a DMA holds the
  CPU is taken after the following instruction (DOC [ANOMIE timing.txt]:
  24-30 clocks between the end of the DMA and the handler); a $4200
  write that enables one likewise. This is a rule for the runner, not a
  hardware "lock" flag (ares' irqLock is an emulator construct).

### 2.4 Timer IRQ, TIMEUP ($4211), $4207-$420A

- HTIME and VTIME are 9 bits, power-on $1FF (DOC [WIKI MMIO registers]),
  unchanged by a reset (DOC [FS "SNES I/O Map"]; ares resets them, IMPL).
- The comparator is a level in the 4-clock raster; TIMEUP is set on its
  rising edge, the CPU line follows 4 clocks later as a level (EMU-
  CONSENSUS ares, MesenCE; RoboCop versus The Terminator).
- TIMEUP times, clocks from the line start (DOC [ANOMIE timing.txt],
  TEST-ROM-HW [PAULB]):

  | Mode / value | TIMEUP at |
  |---|---|
  | V-IRQ (mode 2) | H=10 of line VTIME; H=6 of line 0 for VTIME=0 |
  | HTIME=0 (modes 1 and 3) | H=10, like the V-IRQ |
  | HTIME=1..338 | H = 14 + 4*HTIME (338: 2 clocks into the next line) |
  | HTIME=339 | 1370: H=6 of the next line, compared with the previous line's V |
  | HTIME>=340 | never (on the PAL long line 340 can match, IMPL) |

  In ares' form: HTIME counts as (HTIME+1)*4 against the H counter 10
  clocks back, except HTIME=0, which counts as 0.
- HTIME=0 at H=10, the same moment as the V-IRQ: TEST-ROM-HW [PAULB]
  (2026-09, and nesdev t=24391 page 97: on his console the V-IRQ and the
  HV-IRQ with HTIME=0 have the same timing, HTIME=1 comes "2 pixels
  later than HTIME == 0 or V-IRQ"), with a second, older support:
  byuu and Anomie, "the delay is 10 clocks for VIRQ, 14 clocks for
  [V]HIRQ" (nesdev p=21890) and "V-IRQ: V=VTIME, H=~2.5" dots
  (board.zsnes.com t=4746), both TEST-ROM-HW of the time; together they
  put HTIME=0 at the V-IRQ's 10 clocks. ares and MesenCE give H=14
  (IMPL). byuu's `test_irqb` passes 20/20 on a console (MiSTer
  SNES_MiSTer issue #164).
- Across the field start the V counter reads 0 from H=2 of line 0 on, so
  with VTIME=0 and HTIME=339 two IRQs come per field (line 0 and line 1,
  H=6), with VTIME = last line and HTIME=339 none; the short line never
  matches HTIME=339 (DOC [ANOMIE: no IRQ for dot $153 on the short and on
  the last line] + TEST-ROM-HW [PAULB], single source: one console of
  unknown revision, reported through MiSTer SNES_MiSTer PR #513 commit
  e98ca40, https://github.com/MiSTer-devel/SNES_MiSTer/pull/513: the core
  had fired at (261,339) and once at (0,339), while "paulb-nl's
  console fires (0,339) twice and never (261,339)"; MesenCE matches;
  ares gives one IRQ for VTIME=0, docs/snes-oracles.md section 10).
- The circuit behind both (DATASHEET + INFERENCE, the schematic review, 2026-10-26:
  rgalland's S-CPU-A schematic, https://github.com/rgalland/SNES_S-CPU_Schematics
  at commit 1c9d162, GPL-3, read as a netlist and simulated at gate
  level outside the repository): the S-CPU has its own 9-bit H and V
  counters. H is cleared asynchronously by a one-dot pulse from an
  HBLANK fall detector (two flops clocked by ~XIN/4, cells
  TBHT, TBIG, TBIY), which also clocks V; the first H count after the
  clear is swallowed, so H holds 0 for two dots (this is why HTIME=0
  matches at the V-IRQ's H=10 and HTIME=n at 14 + 4n). V is cleared by a
  separate one-dot pulse from a VBLANK fall detector (TAQM, TAOI, QAUT,
  QBBI). The comparators are plain 9-bit equalities (QBDE, FAOQ), the
  mode multiplexer selects V, H or both (SBFO0, SBFO1, SBFU), and a
  rising-edge detector (SBMW, SBPL, SBQS) sets TIMEUP (SBRW), which a
  $4211 read clears; the CPU's /IRQ is the flag gated combinationally.
  All flops sample every 4 clocks. With the PPU's VBLANK fall one dot
  before its HBLANK fall at the start of line 0, V reaches 0 one sample
  earlier than any other V value: the sample at H=2 of line 0 still sees
  the last line, the sample at H=6 sees V=0. Of the possible PPU edge
  orders only this one gives the measured double IRQ at (0,339) and none
  at (261,339) (both edges in one sample window gives one IRQ at
  (0,339) and one at (261,339); VBLANK two samples early would make
  line 0 read V=1), so the measured facts fix the order and the
  schematic gives the rest. Consequences, applied in every mode since
  the schematic review: a pure V-IRQ at VTIME=0 sets TIMEUP at H=6 of line 0 (H=10
  for every other line), which is what paulb_nl's frame_timing_test
  expects (5.17); HTIME=338 (H=2 of the next line) still counts for the
  last line (VTIME=261 fires at H=2 of line 0, VTIME=0 only at H=2 of
  line 1); HTIME=339 fires at H=6 of line 0 for V=0, as before. Before
  the schematic review the code applied V=0 from H=2 of line 0 in H and HV mode only
  (MesenCE's schematic model) and kept H=10 for the V-IRQ (CHOICE). The
  MiSTer core drops both blanks on the same dot and has no early
  V=0. One race in the schematic is not decided by the drawing (at the
  HBLANK fall edge of line 0 the V clock and the release of the V clear
  arrive together); the measured facts require that the clear wins.
  ctest: `snes_timing` (the comparator, both rules) and `snes_system` /
  `snes_system_exact` (`test_hv_irq_field_start`: the CPU takes both
  IRQs in stage S and stage E).
- PAL with interlace, field 1: its last line (V=311) is the long line,
  1368 clocks, and the HTIME=339 match (1370) lies 2 clocks into line 0,
  where the V counter already reads 0: this runtime fires at V=0 H=2
  (the previous line's match) and at line 1 H=6 (line 0's match), two
  IRQs as on NTSC (INFERENCE from the comparator rule; MiSTer PR #513
  notes the case as not measured: "(311,339) fires and (0,339) fires
  once; hardware has not been measured for that case").
- H-only mode (1) with HTIME=339 at the field start fires at H=6 of
  line 0 (DATASHEET + INFERENCE since the schematic review: in the S-CPU schematic the
  mode multiplexer passes the H comparator alone in mode 1, and H runs
  through 339 at the end of every line, the last one included; before:
  CHOICE, INFERENCE): the comparator that gives the measured second IRQ
  for VTIME=0 at that clock ([PAULB]) has no V gate in mode 1, and
  MesenCE's schematic model (H counter 339 and V reset at hClock 2 of
  line 0) fires there too. Anomie's "no IRQ ... for dot $153 on the
  last scanline of any frame" (no mode named) and ares (V=0 H=6 blocked
  in every mode) say it does not; nobody measured mode 1. Open question,
  test: count the IRQs per field with mode 1 and HTIME=339 (262 or 261).
- A read returns the flag and clears it except within the 4 clocks after
  it was set (DOC fullsnes "lasts for 4-8 master cycles", EMU-CONSENSUS 4).
  Clearing $4200 bits 5-4 acknowledges (DOC). Writes to $4211 do nothing
  (CHOICE with ares and MesenCE; MAME and Anomie's old regs.txt
  acknowledge on write).
- Writes to $4207-$420A: the comparator follows the new value from the
  end of the write cycle; a rising level sets TIMEUP at the next 4-clock
  tick, a falling one ends the level at once, so writing the match back
  gives another IRQ on the same line (EMU-CONSENSUS ares, MesenCE, MAME;
  Doom, Shin Nihon Pro Wrestling '95). An enable write ($4200) that ends
  2 clocks before the trigger still fires (DOC [ANOMIE]: HV-IRQ at (0,1),
  write ending at 1372, trigger at 1374). Switching to V-only mode with
  TIMEUP standing raises the line at once (IMPL [ARES nmitimenUpdate]).

### 2.5 HVBJOY ($4212)

Bit 7 VBlank (V >= vdisp), bit 6 HBlank (H <= 2 or H >= 1096 clocks;
IMPL [ARES io.cpp], DOC H=1 / H=274 dots), bit 0 auto-joypad busy: set
at T0 when $4200 bit 0 is set then, cleared at T0+4224 or when the read
is stopped. Clearing $4200 bit 0 inside the latch phase (T0..T0+256)
does not clear the bit; the read stops at T0+256 (step 2) and the bit
drops there; a clear from T0+256 on stops the read and clears the bit
at once; a 1-0-1 blip inside the latch phase leaves the read running
(TEST-ROM-HW indirect, 2026-10-24: undisbeliever's
clear-autojoy-during-autojoy, clear-autojoy-1st-vb-sl and
clear-autojoy-timing-test; the author's console tables are not
published, but Mesen2 commit d1aa957 of 2024-12-17 fitted MesenCE to the
console results of the first two, and MAMR prints the same tables as
MesenCE 2.2.1 on all three, including the timing test's poll counts
8/6/3/2/1 for clears 0/64/128/192/256 clocks after the bit was first
seen. ares ANDs the bit with $4200 bit 0, so it reads 0 the moment bit 0
is cleared and prints 1 in every row of the timing test:
docs/snes-oracles.md section 10. Before 2026-10-24 this was IMPL
[MESEN].)

Where the latch pulse lies against bit 0 (DATASHEET + INFERENCE, schematic
review, 2026-10-26; before: CHOICE after ares): rgalland's S-CPU-A schematic
(2.4), read as a netlist and simulated at gate level outside the
repository. JP_CLK is XIN/256 (128 clocks high, 128 low, on the grid
counted from reset). The VBLANK pad is sampled on the falling edges of
JP_CLK by an edge detector (VAFA, VAFH, VAGJ, VAGU); there is no H
counter term in the start. The latch request is combinational: NOT
$4200 bit 0 OR the edge detector's one-period pulse (VAAA), and the
controller pin is that request OR $4016 bit 0 (WAYX, WAZZ). HVBJOY bit
0 (AUTO_JP_READING) comes from a flop (VAMM, then VAWR) that samples the
request on the rising edge of JP_CLK, half a period later. So:

| event | clock |
|---|---|
| latch rises (if $4200 bit 0 is set) | T0-128 |
| HVBJOY bit 0 rises, JOY1-4 cleared | T0, on the 256-clock grid |
| latch falls | T0+128 |
| pad clock low / high, n = 0..15 | T0+256+256n / T0+384+256n, data taken on the rising edge |
| HVBJOY bit 0 falls | T0+4224 (the 16th rising edge) |

Whatever edge polarity the cells really use, the bit-0 flop samples the
latch request itself on the opposite JP_CLK edge, so the offset is 128
clocks. The table fills the measured figures (latch 256 clocks, clock
period 256 with 128 low, 4224 clocks from rise to fall of bit 0). This
is MesenCE's position (fitted to undisbeliever's console tables, Mesen2
commits e4d3176 and d1aa957, and citing the same schematic), not ares'
(latch from T0 for 128 clocks). Since the schematic review the code follows it: the
latch from T0-128 to T0+128, and inside it the latch is $4200 bit 0
(the request is combinational), so a clear between T0-128 and T0 drops
the latch and there is no read in that field, an enable inside that
window raises it and the read runs. The first sample stays at T0+256 in
the code: the data line holds the bit from the previous clock edge on,
so the value is the same as at the rising edge at T0+384 (INFERENCE).
undisbeliever's enable-autojoy-late-test-2 (rows V=225 H=16..48) and
clear-autojoy-1st-vb-sl (rows V=224 H=324, V=225 H=0) now print the
manual read 0000 (pads latched) where MesenCE does and aresref does not;
the expected tables (tests/snes-system/undisbeliever/*.txt) accept both
values there.

Clearing $4200 bit 0 in the schematic: before T0 it cuts the latch and
no read starts (above); during the read (from T0+256) HVBJOY bit 0 falls
at once and the pad clock is forced high, so a clear while the clock is
low (a bit sampled, its shift pending) still shifts that bit in: the
code does this since the schematic review (simulated: a clear at T0+264 leaves JOY1 =
$0001). undisbeliever's clear-autojoy-after-autojoy-active (hold B)
names the 1-CHIP console's results in its source: "0001 0001" (JOY1,
manual read) for the delay the ROM uses, which MAMR now prints in the
passes whose clear lands in the first clock-low phase; in the other
passes MAMR's clear lands before T0+256 and it prints "0000 8000", which
the author did not list. His other result, "0008 1000" (occasionally,
for a 2 to 4 clocks shorter delay), is not reproduced and not explained
by the schematic (open, 5.3). A clear between T0 and T0+256: the
schematic asserts the set and the reset of the bit-0 flop together and
does not show which wins; the code keeps the bit until T0+256 and stops
the read there (TEST-ROM-HW indirect, above).

Test setup for the rest (5.3): a logic analyzer on controller pin 3
(latch) and pin 2 (clock) with $4212 polled in a fixed loop; the poll
gives bit 0 against the latch edge (128 clocks expected), and a clear of
$4200 bit 0 at T0+64 shows which side of the flop wins.

### 2.6 Joypads ($4016, $4017, $4218-$421F)

- Standard pad: 16-bit shift register, B first (JOY1 bit 15) down to the
  four ID bits; 1 = pressed; returns 1 after 16 bits; while latched it
  returns B (DOC [FS "SNES Controllers I/O Ports - Automatic Reading"]).
- $4016 write bit 0 latches both ports. $4016 read: d0 of port 1 in bit 0
  (bit 1 = multitap line, 0 here). $4017 read: port 2 in bit 0, bits 4-2
  read 1 (grounded) (DOC [FS "Manual Reading"]).
- An empty port returns 0 in its data bits on every read, before and
  after the 16th clock (EMU-CONSENSUS ares `ControllerPort::data`,
  MesenCE; no pad drives the line). Games tell a pad from an empty port
  by the bits after the 16th: Donkey Kong Country reads $4017 bit 0 once
  per frame and takes a 118-clock branch when it sees 0. This runtime
  leaves port 2 empty, as the oracle runs do (`Joypad::connected`,
  docs/snes-rom-survey.md); a second pad is a front-end option.
- Auto-read, 33 steps of 128 clocks from T0: step 0 clears JOY1-4,
  step 1 releases the latch (raised at T0-128, 2.5), steps 2-33
  alternately sample and shift, 16 bits each (duration DOC [ANOMIE]; the
  steps EMU-CONSENSUS bsnes/ares, MesenCE). Clearing $4200 bit 0 from
  T0+256 on stops the read, the registers keep the bits read so far
  (DOC + TEST-ROM-HW indirect: Jonas Quinn's tests as cited by bsnes and
  MesenCE); a bit already sampled whose shift is pending still goes in
  (DATASHEET + INFERENCE, 2.5). Enabling later in the field does not
  start it (Pocky & Rocky).
- $4016 writes and reads during the auto-read: a write of 1 holds the
  latch (the read delivers zeros), a write of 0 releases the pad early
  and the manual read then sees the remaining bits, a read consumes one
  bit (JOY1 ends with bit 0 set): aresref, MesenCE 2.2.1 and MAMR print
  the same screens on undisbeliever's joypad-latch-set-during-autojoy,
  joypad-latch-clear-during-autojoy and joyser0-read-during-autojoy
  (EMU-CONSENSUS; the console tables are not published; ctest
  `snes_system_undisbeliever_*`). The code follows ares here (the latch
  is the OR of OUT0 and the auto-read's latch; a $4200 write inside
  T0..T0+128 moves the auto-read's latch with bit 0).
- The strobe (latch line) during the auto-read: ares raises it at T0
  for 128 clocks, MesenCE 128 clocks earlier for 256 clocks. On the
  console the pulse is 12.04 us wide and the clock period 11.91 us with
  5.9 us low (MEASURED [OWNA], logic analyzer during a TAS replay on a US
  console, revision not named; J. Christy 1996: about 12 us), i.e. 256
  clocks of latch, then 16 periods of 256 clocks, 128 low. MAMR (since
  the schematic review, 2026-10-26): the latch from T0-128 to T0+128, inside it the
  latch is $4200 bit 0 (DATASHEET + INFERENCE from the S-CPU schematic,
  2.5; MesenCE the same; after the primary-source review T0 to T0+256, before
  that ares' T0 to T0+128). The undisbeliever screen tables, their
  aresref comparisons and Zelda are unchanged; deviation from ares in
  docs/snes-oracles.md section 10.

### 2.7 Maths ($4202-$4206, $4214-$4217), WRIO, MEMSEL

- WRMPYB starts an unsigned 8x8 product into RDMPY and sets RDDIV =
  WRMPYB; WRDIVB starts 16/8 division (RDDIV quotient, RDMPY remainder);
  divisor 0 gives FFFFh and the dividend (DOC [FS "SNES Maths
  Multiply/Divide"]). The hardware needs 8 (multiply) and 16 (divide)
  CPU cycles (DOC) and shows partial results before. Stage S: results
  are ready at once (CHOICE). Stage E (2.8) steps the unit once per CPU
  cycle, bit-serially: multiply adds the shifted WRMPYB for each set bit
  of WRMPYA from bit 0 up, divide subtracts WRDIVB << 15..0 (IMPL [ARES
  timing.cpp aluEdge, io.cpp]); a write to $4203/$4206 clears RDMPY (or
  sets it to the dividend) and is otherwise ignored while the unit runs
  (IMPL); the unit does not step while the CPU is held by DMA and steps
  five times during a refresh (IMPL, not measured).
- A second WRMPYB write while the product is in flight (TEST-ROM-HW,
  nesdev t=24087, 2022-08; SNESdev wiki "Emulator tests"): the console
  clears RDMPY and does not restart the product. With 2 to 6 CPU cycles
  between the writes the unit goes on adding the remaining partial
  products (FF x FF then FF: F708, EF10, DF20, BF40, 7F80), which ares,
  bsnes and MAMR stage E print as well. With 7 cycles between the writes
  (the unit's 8th cycle) the console still treats the unit as busy and
  RDMPY ends 0, where bsnes v115, ares and MAMR stage E restart and print
  A x B2 (undisbeliever's `wrmpyb-in-flight.asm`, 2/1/3 SFC, the 1/1/1
  and 1CHIP consoles equal on the initial inputs; "only the 7-cycles
  output differed between real-hardware (0) and emulator (A*B2)").
  Myself086's "Mul Div Test" on rainwarrior's console: a write on Mul
  cycle 8 and on Div cycle 16 is blocked (RDMPY 0, RDDIV 8077 on cycle
  8). regiscaelus (FPGA simulation of the 5A22 netlist, 2022-08-30):
  WRMPYB always clears RDMPY, starts a new product only when the current
  one is complete (more than 8 cycles), and loads RDDIV with
  WRMPYB:WRMPYA when complete or on the last cycle (more than 7); WRDIVB
  always copies WRDIV to RDMPY and starts a new division only when the
  current one is complete (more than 16). Not modelled (2026-10-24): the
  result tables are screenshots behind the forum's attachment login,
  Mesen2 commit 20c2a24 (2025-03-23, "Fixed mul/div edge cases when
  writing to mul/div registers while mul/div is still running") carries
  them in GPL code that this project does not read; MAMR stage E keeps
  ares' rule and the deviation is on record (docs/snes-oracles.md
  sections 10 and 12). Stage S differs further: results at once, so the
  ROM prints A x B2 in every column (CHOICE above). Test: the author's
  ROM with A=FF, B1=FF, B2 stepped, read 2 to 9 cycles apart, on a
  console per revision, the table photographed; then the stage E rule
  (busy through the 8th cycle, RDDIV load on the 8th).
- $4201 bit 7 going from 1 to 0 latches the PPU counters (hook to the
  PPU); $4213 returns the WRIO value (DOC).
- $420D bit 0: ROM speed 6 instead of 8 for 80-FF (1.3) (DOC).

### 2.8 Service contract, power-on and reset

The runner is System (runtime/snes/snes_system.h, phase S5b;
docs/snes-architecture.md section 4). System::run_until and
System::run_to_sample run the CPU (w65816_run), in whole instructions or
emitted blocks, up to Timing::next_event() or their target, and then
call service(): Timing::advance_to(cycles) runs the due events and
returns the clock pushed later by what they stole (refresh, HDMA), plus
take_stolen() for what register accesses ran themselves. The board
contract it relies on:

- Bus accesses come with the start of the bus cycle; Map::read8/write8
  derive the sample time (1.4: a read at start + cost - 4, a write at
  start + cost). The CPU register window syncs the time skeleton to that
  time before every access ($4016/$4017, $4200-$421F, $420B, $420C,
  $43xx), so an overdue event runs before a register changes.
- The CPU side reports the start and length of every CPU cycle to
  Board::cpu_cycle and its sampling moments to Board::cpu_sample
  (Board::cpu_cycles set; 3.6). The system does it from the bus calls
  (it recovers the internal cycles from the gaps between them, see
  docs/snes-architecture.md section 4) whenever an event is due by the
  end of the cycle or a DMA request waits; stage E does it for every
  cycle. What the board steals there delays this and every later bus
  cycle of the run.
- The interrupt poll syncs to its clock and reads nmi_pending and
  irq_line(t). Every register access that raises a line at once shows
  up as an event at or before its clock (the late $4200 bit 7 NMI as an
  Nmi event at the write; the V-only IRQ with TIMEUP standing as an Irq
  event), so a runner that only stops at events sees it.
- A $420B write and an HDMA trigger raise a request that
  Board::cpu_cycle serves at the start of the second CPU cycle that
  begins at or after it (3.6), through Board::run_dma for a GP-DMA, its
  own stolen clocks included; refresh and HDMA cut in at their times, an
  HDMA step reached from inside a DMA byte (a byte that reads
  $4210-$421F) runs at the next byte boundary. While a request waits,
  System reports its next event as due, so the CPU runs one instruction
  at a time and polls at every poll point.
- The PPU calls Timing::sync(t) before it reads the counters and
  Timing::set_interlace/set_overscan on SETINI writes.

Per-cycle path (stage E, runtime/snes/snes_system_exact.h,
docs/snes-architecture.md section 4). The board keeps its own master
clock; the interpreter runs one step at a time and every bus cycle calls
it: read8 and write8 for the memory cycles, W65816Bus::idle for the
internal ones (the time stamps the interpreter passes are not used, they
do not know the held clocks). Per cycle:

- DMA edge at the start (RDY): a DMA unit that noticed a request at an
  earlier cycle start takes the bus now; outside a GP-DMA an HDMA first
  aligns to the 8-clock counter (2..8) and afterwards resyncs to the
  length of this cycle, counted from the alignment (3.3); a GP-DMA does
  the same around its whole run, with a DMA edge after its start, after
  each channel start and after each byte, where a pending HDMA runs
  without alignment or resync (a channel counts as running through the
  edge after its last byte); a request not yet noticed is noticed
  here and this cycle still runs, so DMA and HDMA start one CPU cycle
  later (IMPL [ARES timing.cpp dmaEdge]; Anomie's "the CPU finishes its
  cycle" is the DOC side, the extra cycle is not documented).
- The clocks in pieces: a read cost - 4, then the device samples, then
  4; a write cost, then the device takes the byte; an internal cycle 6; a
  DMA byte 4 (source read), 4 (destination written). After every piece
  the time skeleton is synced to the clock (2.2: NMI and IRQ logic every
  4 clocks, joypad, field structure), then: a DRAM refresh that became
  due runs at once and holds the CPU 40 clocks (not counted into a DMA's
  resync); a reached HDMA trigger makes the HDMA pending (setup: every
  channel's completed and do-transfer flags clear first; pending when a
  channel is enabled, for a line when one is active). The refresh is at
  clock 2 mod 8, the sample of an 8-clock read starting at 0 mod 8 is at
  4 mod 8: most refreshes start between a read's start and its sample
  and move the sample 40 clocks later (IMPL; where the CPU is stopped
  inside its cycle is UNKNOWN, see below).
- One multiply/divide step per cycle (2.7): after a read or an internal
  cycle, before a write.
- The PPU pipeline is synced to the end of the cycle; the S-SMP is
  caught up at every port access (it is a port slave) and at the
  sampling point.
- Interrupt poll at the start of the instruction's last cycle, before its
  DMA edge: nmi_pending and irq_line at the end of the previous cycle.
  When the previous cycle wrote $4200 (no clock in between: a 16-bit STA
  $4200, or $4200 written by the next-to-last cycle) the poll sees no
  line, so the interrupt the write enabled is taken after the following
  instruction (2.3; IMPL [ARES irq.cpp nmitimenUpdate irqLock], checked
  against aresref on a synthetic ROM). ares sets the same lock after DMA
  and HDMA, but its resync step clears it before any poll, so it has no
  effect there and stage E does not model it.

Reset sequence (System::reset_sequence, SystemExact::reset_sequence_exact):
132 clocks, then the CPU's reset entry: a dummy read of PB:PC (8
clocks), an internal cycle (6), three stack cycles (8 each), the vector
$FFFC/$FFFD (8 each); the first opcode fetch starts at H=186 (IMPL [ARES
cpu.cpp main]: step(132) before the reset interrupt, "H=186"; no
documentation or measurement of the 132 is known). The three stack
cycles are reads with the address stepping down, 0,S / 0,S-1 / 0,S-2
(DATASHEET: WDC W65C816S 2024-03-13,
https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf,
section 2.25 "RWB remains in the high state during the stack address
cycles", table 5-7 row 22a with note 10 "RWB remains high during Reset"
and note 7, one cycle fewer in emulation mode, so three stack cycles);
nothing is written. MEASURED on the S-CPU [SRG320 LA] `SCPU&SMP reset
timing.png` (commit 9a1955e6, 2024-09-18, triggered 2024-09-11; read
by the measurement search of 2026-10-25): after one cycle at the old PB:PC
the bus shows $0001E5, $0001E4, $0001E3, then $00FFFC/$00FFFD and
$008000, with CPUWR_N inactive throughout; S was $01E5 before, so S.l
is kept and the three cycles count it down by 3. The S-SMP in the same
capture: $01CA, $01C9, $01C8, then $FFFE/$FFFF, no write either.
Whether /RD is active in each of the three S-CPU stack cycles cannot be
counted from the image; the absence of /WR is clear. Registers after
the sequence (DATASHEET 2.25): D = $0000, S.h = $01, X.h = Y.h = $00, DBR
= PBR = $00, E = 1, M = X = 1, I = 1, D flag = 0; A, X.l, Y.l and S.l are
"Not Initialized" on the chip and are kept here (S.l kept is MEASURED;
Garth Wilson's W65C816S bus logs, 6502.org t=4129, 2016, show six
different S values after reset, MEASURED on the WDC chip). The code
(since 2026-10-26, `w65816_reset_registers`, System::reset_sequence,
SystemExact::reset_sequence_exact) reads S, S-1, S-2 of the present S
and leaves S.l 3 lower: there is no fixed end value. CHOICE: at power-on
this runtime starts A, X, Y at 0 and S at $01FF before the sequence, so
S ends at $01FC there, as ares (the oracle files carry that S in the cpu
field); the S of a real cold start is UNKNOWN. ctest `w65816_cpu`,
`snes_system`, `snes_system_exact` (`test_reset_from_s`: S=$01E5 before,
reads at $01E5-$01E3, S=$01E2 after, A, X.l, Y.l kept, no write).
System::cpu_reset runs the CPU's sequence from its present state;
System::reset_button and SystemExact::reset_button press the whole
button (Board::reset, Ppu::reset_line, Smp::reset, the CPU's sequence;
docs/machine-interface.md section 7.1), the front end's reset calls them,
the headless runners and the oracles do not. ares writes the three
stack cycles (unpatched; aresref carries patch 0006 and reads them,
docs/snes-oracles.md section 2 and 10). Open: which of A, X.l, Y.l
survive the button on the 5A22. Test setup (A5): set A/X/Y patterns
before pressing reset, save TXA/TXY/TSX first in the handler.

Power-on (Timing::power): every register at its power-on value, V=0 H=0
of field 0. Reset button (Timing::reset, Board::reset), after [FS "SNES
I/O Map"] (values in brackets survive a reset) (DOC):

| Register | Power-on | Reset |
|---|---|---|
| $4200 NMITIMEN | 00 | 00 |
| $4201 WRIO | FF | FF |
| $4202-$4206 WRMPYA, WRDIV | FF | unchanged |
| $4207-$420A HTIME, VTIME | 1FF | unchanged |
| $420B/$420C MDMAEN, HDMAEN | 00 | 00 |
| $420D MEMSEL | 00 | 00 |
| $4210/$4211 flags | 0 | 0 |
| $4214-$4217 RDDIV, RDMPY | 0 | unchanged |
| $4218-$421F JOY | 00 | 00 |
| $2181-$2183 WMADD | 00 | 00 |
| $43x0-$43xB, $43xF DMA | FF | unchanged |

The PPU counters do not run over a reset (since 2026-10-26; DATASHEET +
INFERENCE, 5.4): while /RESET is low the S-PPU2 forces its 9 H and 9 V
counter bits to 0 and stops the dot divider (`_/hvcres` = `_+/reset` AND
`_/hvcmode`, each bit NOT(NAND(slave, reset)) [VISUAL 5C78]; the S-PPU1
the same [VISUAL 5C77], its field flip-flop to 0), and the reset button
pulls /RESET of both PPUs low (MEASURED [SPLA]). Timing::reset(t) takes
t as the release: V=0 H=0 of field 0 at t, interlace and overscan off
(the netlists clear SETINI bits 0 and 2 and set force blank; the PPU's
own registers are not wired to Board::reset), the clock grids from t.
The S-CPU side after [RGALLAND]: HTIME/VTIME, the $43xx parameters and
the maths operands and results have no reset input (their values
above, now DATASHEET besides DOC); $4200, $420D, the cycle-length,
DMA and maths sequencing flip-flops and the S-CPU's internal H/V
counters are on ~MRST (DATASHEET + INFERENCE). ares resets all of these
and the counters (IMPL); `like_ares` does the same for oracle runs.

### 2.9 PAL

- Master clock 21.281370 MHz (DOC [FS "SNES Timing Oscillators"]; MAME's
  21218370 is a digit swap, -2960 ppm).
- 312 lines per field, 313 in field 0 with interlace; no short line; the
  long line V=311 of field 1 with interlace has 1368 clocks (2.1).
  425568 clocks per progressive field, 50.00698 Hz (DOC [FS]); interlaced
  426932 + 425572 per pair.
- VBlank 225/240, refresh, HDMA, auto-joypad and IRQ positions as on NTSC
  (INFERENCE, 2.2; partial TEST-ROM-HW: MiSTer SNES_MiSTer PR #513
  reports paulb_nl's `irqprobe` and `busprobe` ROMs on PAL agreeing with
  hardware recordings for the lines they probe, 17/18 and 22/23; no PAL
  measurement of the refresh, NMI or joypad H positions is published).
  A progressive PAL field is 0 mod 8, so the HDMA setup phase stays the
  same from field to field; the joypad start moves by 96 clocks (mod
  256) per field. VTIME runs to 311 (312 in field 0 with interlace).
  Test setup for the rest (research package A, A9): on SNSP-CPU-01/02
  and SNSP-1CHIP latch the H counter through $2137 at fixed events (NMI
  entry, the $4212 bit 0 edge, the refresh gap found with a loop
  counter) and compare with NTSC; measure the long line as the count
  difference between V=310 and V=0 in field 1 with interlace on and
  off.
- The system comes from Cart::pal at power-on (Board::init): the known
  ROM profile, else the header country (1.2).
- The S-SMP clock does not depend on the region, so its ratio to the
  master clock differs on PAL (nominal 24.576 MHz / 24 against 21.28137
  MHz: 102400/2128137). The system's default is ares' 32040 Hz
  convention instead (SMP_CLOCK_ARES_NTSC 341760/7159091,
  SMP_CLOCK_ARES_PAL 34176/709379, runtime/snes/snes_system.h). The DSP
  rate of real consoles is MEASURED: 31965 to 32182 Hz, mean 32076 Hz
  (TASBot survey 2025, 143 consoles; lidnariq's smpspeed series with an
  oscilloscope check, nesdev t=24610; undisbeliever's logs 2023-2026,
  undisbeliever.net/blog/20250313-smpspeed.html), warming adds 8 to 10
  Hz; the SNESdev wiki gives "about 32000 to 32160 Hz" (DOC, method not
  stated), a second range kept apart from the first; nominal 24.576 MHz
  / 768 = 32000 Hz is DATASHEET arithmetic (5.14); the rate is a run-time parameter (`SystemOptions::dsp_rate`,
  `smp_clock_for`), 32040 by default for the oracle comparisons; details
  and sources in docs/snes-audio-spec.md section 3.

Where the sources differ (section 2):

- Long dots: fullsnes and the SNESdev wiki say four dots of 5 clocks per
  normal line; Anomie and ares two dots of 6 (323 and 327). fullsnes'
  own latch statistics (dots 323 and 327 six times each) contradict its
  text; taken as two 6-clock dots.
- fullsnes' header line says the short line occurs "in Field.Bit=1 of
  Interlace"; its detail list and the wiki say interlace off. Taken as
  interlace off.
- Refresh: Anomie's rule gives 538/534 alternating (ares version 2,
  MesenCE); fullsnes "around H=133.5" (= 534) is the 534 phase. ares'
  version 1 (530 fixed) is not modelled.
- Refresh inside a CPU cycle: where the CPU is stopped when the refresh
  position falls into one of its cycles is not documented (fullsnes and
  Anomie give only the position and the 40 clocks; ares notes a 5-3
  pattern from a logic analyzer). ares starts it at the end of the piece
  of time that reaches the position, which for a read can be between the
  address and the data sample. Stage S delays the first access whose
  sample is at or after the position (the same cycle starts and the same
  read samples as ares); stage E does what ares does (2.8). Only the
  sample time of a read that crosses the position depends on it.
- HDMA per line: trigger H=1104 (bsnes, ares, MesenCE, LakeSnes) against
  "dot 278" (= 1112) in Anomie and fullsnes. That both mean the same
  moment (the CPU stops at 1104, the first byte follows after the end of
  the CPU cycle, the alignment and the 8-clock start) is INFERENCE,
  supported by bsnes' fast core, which triggered at 1112 to save that
  modelling. Taken: 1104 with the cost model (CHOICE); here the first
  byte is read at 1120 or 1124 and written at 1124 or 1128, in ares one
  CPU cycle later. In ares an event (refresh, HDMA, DMA) becomes active at the end
  of the piece of time that reaches it (a read is two pieces, split at
  its sample), a refresh runs right there, and HDMA and GP-DMA run one
  full CPU cycle after the cycle start that notices them; stage S
  charges at the exact clock, stage E follows ares (2.8).
- HDMA setup: ares 12/16 (version 2) against Anomie "about H=6"
  (dots, 24 clocks) and fullsnes "H=6": compatible once the CPU cycle
  end, alignment and start cost are added. Taken from ares.
- NMI flag clear: ares and MesenCE V=0 H=2; fullsnes and Anomie H=0.
  Taken: H=2. The DOC values are given in dots (Anomie also sets the
  flag at "H=0.5", i.e. clock 2); the interrupt logic samples at clocks
  2 mod 4, which puts both edges at H=2, and MesenCE derives the same
  from the schematic. The difference shows only for a read sampled at
  V=0 H=0..1.
- Auto-joypad window end: Anomie's dots give 382, bsnes, ares and MesenCE
  384 after Jonas Quinn's tests. Taken: 384 (a start at H=384 happens,
  e.g. in field 34 after power-on).
- HV-IRQ with HTIME=0: Anomie (the HTIME=0 special case "1374 master
  cycles after the previous line start" = H=10), fullsnes, [PAULB] and
  the older byuu / Anomie 10-clock V-IRQ delay give H=10; ares and
  MesenCE H=14. Taken from the measurement (2.4); the second research
  pass holds the measurement unconfirmed (one console), 5.17.
- HTIME=339 with VTIME=0: [PAULB] (one console, via MiSTer PR #513) and
  MesenCE two IRQs, ares one. Taken from the measurement; a second
  console has not confirmed it (2.4).
- Auto-joypad start: Anomie "dot 74.5 on the first frame" (H=298) is a
  power-on value of one console; the 256-clock grid from clock 0 gives
  H=300 in field 0 (ares, MesenCE). Taken as the grid rule.
- PAL: MesenCE applies the NTSC short line to PAL as well and has no long
  line; MAME has neither and no 313-line field; fullsnes' "426936" and
  "+4/2" for interlaced PAL are typos. ares follows the documentation.

## 3. DMA and HDMA

Code: runtime/snes/snes_dma.{h,cpp}, wiring in snes_board.{h,cpp}.

### 3.1 Registers

$43x0 DMAP (bit 7 direction B to A, 6 indirect HDMA, 5 unused R/W, 4-3
A-bus step 0 increment / 2 decrement / 1, 3 fixed, 2-0 mode), $43x1 BBAD,
$43x2-4 A1T/A1B, $43x5-7 DAS/DASB, $43x8-9 A2A, $43xA NTRL, $43xB and
$43xF one R/W byte, $43xC-E open bus; $420B MDMAEN starts GP-DMA, $420C
HDMAEN (DOC [FS "SNES DMA and HDMA Channel 0..7 Registers", "Start/Enable
Registers"]). Power-on FFh, unchanged by a reset (DOC [FS "SNES I/O
Map"]; A1Bx is "(xxh)" there, unknown); ares restores FFh on reset
(IMPL). Channel 0 runs first; HDMA has priority over GP-DMA.

B-bus offsets per byte of a unit: mode 0: 0; 1: 0,1; 2: 0,0; 3: 0,0,1,1;
4: 0,1,2,3; 5: 0,1,0,1; 6 = 2; 7 = 3. Unit sizes 1,2,2,4,4,4,2,4 (DOC).
GP-DMA repeats the pattern every 4 bytes and counts bytes, not units; DAS
= 0 means 65536 and holds 0 at the end (DOC). The A-bus address steps in
16 bits, the bank stays.

### 3.2 Byte timing

Every byte takes 8 clocks (DOC [FS "SNES DMA and HDMA Notes"]): the
source is read 4 clocks into the slot, the destination written at its end
(IMPL [ARES dma.cpp readA/readB]; the position in the slot is unknown on
hardware). The byte moved becomes the bus value (MDR).

### 3.3 GP-DMA cost

From the clock the DMA takes the bus (ares: one CPU cycle after the $420B
write): to the next multiple of 8 of the master clock, 2..8 clocks (the
clock is even at every bus cycle boundary, 8 - clock mod 8); 8; per
enabled channel 8, plus 8 per byte; then to the end of the CPU cycle the
CPU resumes with: cycle - (elapsed mod cycle), never 0, counted over
everything since the start including HDMA inside (DOC [ANOMIE
timing.txt]: "2-8" alignment, 8 + 8 per channel + 8 per byte, resync,
"12-24 overhead" in regs.txt; IMPL [ARES timing.cpp dmaEdge, dma.cpp
dmaRun] for the exact form). A DMA whose channels were all cleared (by an
HDMA setup) before it starts costs nothing (IMPL [ARES dmaEdge]). Refresh
during a DMA steals its 40 clocks as usual and does not count into the
resync (IMPL: bsnes v108.13, a fix for Battle Grand Prix; not measured).
One channel, N bytes, from a multiple of 8, 8-clock cycle: 8 + 8 + 8 + 8N
+ 8 = 32 + 8N.

### 3.4 HDMA

- Setup (V=0): every channel's completed and do-transfer flags clear;
  if any channel is enabled: 8 clocks, do-transfer set on all eight
  channels, then per enabled channel A2A = A1T, NTRL = 0 and a reload.
  Reload: read the byte at A1B:A2A (8 clocks, every line, used or not);
  when NTRL bits 6-0 are 0 it is the new NTRL, A2A + 1, count 0 ends the
  channel for the field; indirect mode then reads the 16-bit address into
  DAS (16 clocks), the high byte skipped when the channel just ended and
  no later channel is active (DOC [ANOMIE]: about 18 + 8 per channel + 16
  indirect, "one oddity" for the last address byte; order IMPL [ARES
  dma.cpp hdmaReload]).
- Line (H=1104, V < vdisp), when a channel is active: 8 clocks; per
  active channel with do-transfer one unit from A1B:A2A (direct) or
  DASB:DAS (indirect), 8 clocks per byte; then per active channel NTRL -
  1, do-transfer = NTRL bit 7, reload (DOC for the table format: count
  01h-80h = one unit then pause, 81h-FFh = repeat; order IMPL).
- HDMA started mid-frame: the do-transfer rule above is the whole model
  of fullsnes' "Case 1" and "Case 2". When HDMAEN was 0 at V=0 the new
  channel starts with do-transfer clear and reads its first entry as a
  count (Case 1); when it was not 0, do-transfer was set on all eight
  channels and the first table bytes go out as data (Case 2) (TEST-ROM-HW:
  ladida's test ROM on a console, byuu 2017; EMU-CONSENSUS).
- HDMA on a channel stops a GP-DMA on that channel (IMPL).
- HDMA inside a GP-DMA starts at the DMA's byte boundary, with no
  alignment of its own; when a DMA byte that reads $4210-$421F reaches
  the HDMA event during the read, the step waits for the end of that
  byte (IMPL: in ares HDMA runs between DMA bytes, dmaEdge).
- HDMA that runs past H=1364 just continues (EMU-CONSENSUS; no hardware
  evidence; the worst case of 466 clocks from H=1104 ends at about 1578,
  so it can happen on the console; open, test setup in 5.7).
- Outside a GP-DMA an HDMA step waits for the CPU and is aligned and
  resynced like GP-DMA (3.3, 3.6). A board driven without a CPU
  (Board::cpu_cycles clear, the board tests) runs it at its trigger,
  aligned from there and resynced to Board::cpu_cycle_hint (8). Stage E
  (2.8) keeps its own implementation of the same rule: the step starts
  at the start of the second CPU cycle that begins after the trigger and
  resyncs to the length of that cycle; it equals aresref on the PAL
  target game in every frame (docs/snes-oracles.md section 6).

### 3.5 Invalid transfers

- A-bus addresses (banks 00-3F/80-BF): reads of $2100-$21FF,
  $4000-$41FF, $4300-$437F return the present bus value (MDR); writes to
  those and to $4200-$421F are dropped (CHOICE, see below).
- WRAM to WMDATA or back (A-bus 7E-7F or the 0000-1FFF mirror): A to B
  into $2180-$2183 is dropped and the WRAM address does not move; B to A
  from $2180 does not read the port, WMADD stays and WRAM gets 00
  (TEST-ROM-HW since the schematic review: byuu's test_dmavalid comment "[00] DMA
  write did occur, but wrote unknown value (not MDR, which would be
  #$ea)", one console, 5.11; DOC [ANOMIE regs.txt]: "DMA from WRAM to
  these registers has no effect"; Anomie's "the value written is
  (initially) the Open Bus value" was the code's value before). The
  S-CPU schematic shows why the bus value is not the answer: in such a
  cycle the S-CPU asserts /PARD with PA=$80, /WR and /RAMSEL together,
  has no gate that inhibits any of them, and leaves the data bus
  undriven (DATASHEET + INFERENCE, rgalland, 2.4); the byte is decided
  inside the S-WRAM, which sees a port read and a write in one cycle.
- Deliberately not modelled: the S-CPU-A (5A22 version 2, early
  S-CPU-A boards) failure of a GP-DMA that follows an HDMA to or from
  INIDISP (BBAD = $00): "Nothing will happen and the DMA size registers
  (DASnL, DASnH) will be unchanged" ([WIKI PPU registers INIDISP], DOC
  on the basis of TEST-ROM-HW; nesdev t=24822 "Investigating a HDMA
  failure", undisbeliever and Ramsis, TEST-ROM-HW on S-CPU-A: the
  failure shows when the dummy DMA ends just after the start of line 0).
  "S-CPU (the first version), S-CPU-B and the 1-CHIP SNES are not
  affected". It is a board-revision defect, not a rule of the design;
  this runtime models the unaffected revisions (CHOICE, 5.11).

Where the sources differ (section 3):

- Readable A-bus I/O: fullsnes says DMA reads of $4210-$421F work;
  Anomie blocks only $420B/$420C and $4300-$437F; ares, MAME and the
  SNESdev wiki ([WIKI DMA registers]) block $2100-$21FF, $4000-$41FF,
  $4200-$421F and $4300-$437F. Reads follow fullsnes, writes follow ares
  (CHOICE): fullsnes names the readable ports from its own tests
  ("these do work"), the others give one blocked range without a test;
  no source says a DMA write to $4200-$421F works, and dropping it is
  the safe side.
- The value of an invalid read: fullsnes' FFh came from an XBOO pull-up
  (its own correction); ares, bsnes and MAME read 00h, MesenCE and MiSTer
  FFh, none with a stated test. Taken as the bus value.
- WRAM-to-WRAM B to A: ares writes 00h (byuu's console value, taken
  since the schematic review), MesenCE and MiSTer FFh; WRAM source to $2181-$2183:
  ares, MesenCE and MiSTer write WMADD normally, only Anomie says it has
  no effect. Taken from Anomie.
- When HDMA stops a GP-DMA mid-byte ares skips the byte counter
  decrement of that byte; here DAS counts every transferred byte
  (CHOICE): fullsnes describes DAS as the count of bytes still to move
  ("decremented during transfer"); ares' skip follows from the shape of
  its loop, not from a test.

### 3.6 The DMA unit and the CPU cycle

When DMA or HDMA takes the bus, and for how long the CPU waits
(runtime/snes/snes_board Board::cpu_cycle):

| Rule | Value | Class |
|---|---|---|
| pause point | the CPU is stopped between two of its cycles, never inside one; possibly inside an instruction | DOC [ANOMIE timing.txt]: the current CPU cycle "is completed before pausing" |
| GP-DMA start | after the $420B write the CPU runs one more cycle, then the DMA unit takes the bus at the start of the cycle after it | DOC [ANOMIE]: "After $420B is written, the CPU gets one more CPU cycle before the pause"; IMPL [ARES timing.cpp dmaEdge]: the first cycle start after the write marks the unit active, the next one runs the DMA |
| HDMA start | the same for the trigger (V=0 setup, H=1104 line): the first CPU cycle that starts at or after it runs, the HDMA step comes at the start of the cycle after it | DOC [ANOMIE]: "the exact timing for the HDMA pause is the same as that for DMA" (presumed there); IMPL [ARES dmaEdge] for the cycle count |
| request seen | a trigger counts from the end of the CPU's step that reaches its clock: a cycle start, or the sampling moment of a read (start + cost - 4); so the "first cycle that starts at or after the trigger" is meant literally. A trigger during a DMA's own steps, its resync included, is seen there: the unit is active again at the end of that cycle start, and the step comes at the next one | IMPL [ARES timing.cpp step, memory.cpp read, dmaEdge]; equal to the plain reading for every cycle kind |
| alignment | from the start of the cycle the unit takes: 8 - (clock mod 8), 2..8, the 8-clock counter counting from power-on (2.2) | DOC [ANOMIE] "2-8 master cycles to reach a whole multiple of 8 master cycles since reset" |
| resync | to the length (6, 8 or 12; internal cycles 6) of that same cycle, the one the CPU resumes with: length - (clocks since the pause mod length), never 0; DRAM refresh inside does not count | DOC [ANOMIE]: the speed of the next CPU cycle after the DMA "determines the CPU Clock speed"; IMPL [ARES dmaEdge] for the formula; refresh: 3.3 |
| HDMA and GP-DMA at the same cycle start | HDMA first, without alignment or resync of its own (the bus stays the DMA unit's), then the GP-DMA aligned and resynced | DOC [ANOMIE] "HDMA takes priority over DMA"; IMPL [ARES dmaEdge] for the alignment |
| a request with nothing to do | (HDMAEN or every MDMAEN channel cleared in between) costs nothing; the unit stays active, so the next request is served at the next cycle start | IMPL [ARES dmaEdge]; UNKNOWN on hardware |
| interrupt poll | the poll at the start of an instruction's last cycle comes before the DMA unit's edge of that cycle, so a line that rises during the transfer is taken after the following instruction | IMPL [ARES lastCycle before read/idle]; DOC [ANOMIE]: an NMI during DMA "will trigger after the DMA completes", with a delay |
| DRAM refresh | 40 clocks at the end of the CPU step that reaches its position (2.2): before the cycle that starts at or after it, or before the sampling moment of a read or write that reaches it | DOC [ANOMIE] (position, 40 clocks); IMPL [ARES timing.cpp step] (the step boundaries) |

Before this rule stage S started an HDMA step at the first access
sampled after the trigger, aligned from the trigger and resynced to an
assumed 8-clock cycle, and ran a GP-DMA after the instruction that wrote
$420B, with the next opcode fetch moved behind it; on Zelda (PAL) the
sampling clock then differed from ares by -82..+80 clocks in 72 of the
first 1400 frames, none before the first HDMA frame.

## 4. CPU (65816)

Code: recompiler/w65816_table.{h,cpp}, recompiler/w65816_exec.cpp,
runtime/w65816_ops.h; harness tests/w65816/w65816_sst.cpp.

Additional sources for this section:

- **gilyon/snes-tests** v1.4 (MIT), `cputest/README.md`, section "What
  undocumented behavior is tested?". Cited as [GILYON].
- **SingleStepTests/65816** (MIT, generated with Clock Signal), the
  per-opcode test suite of phase S1. Cited as [SST].
- **ares** as above: `ares/component/processor/wdc65816/memory.cpp`.

### 4.1 (dp,X) in emulation mode with D.l != 0

With E=1 and the low byte of D not zero, the (dp,X) addressing mode
reads the pointer's low byte from D+dp+X (no page wrap, as in native
mode) and its high byte from D+dp+X+1 with the +1 wrapping inside the
page. Example from [GILYON]: E=1, D=$11A, X=$EE, `LDA ($F7,X)`:
$F7+$11A+$EE = $2FF, low byte from $2FF, high byte from $200. Only this
addressing mode behaves so, not the other indirect modes (DOC [GILYON]).
ares does the same (IMPL [ARES memory.cpp readDirectX]); both ares and
MesenCE pass cputest-full, which checks it (docs/snes-oracles.md
section 1).

MAMR follows this behaviour (CHOICE, 2026-10-24, recorded in
docs/snes-architecture.md section 9). The `DpIndX` address source of
the table carries the rule.

Class TEST-ROM-HW (one source, a 5A22 in a console; research package A,
A13): gilyon found it with the cputest ROM on the console, nesdev
t=24940 (2023-11-06, https://forums.nesdev.org/viewtopic.php?t=24940):
in emulation mode with a nonzero low byte of D, the (direct,X) mode
adds direct_addr+X+D without a page wrap, but the +1 for the high byte
of the pointer wraps inside the page (paraphrased from the post). The releases record the path
(https://github.com/gilyon/snes-tests/releases: v1.1 "Temporarily
disable (dp,X) emulation mode tests until further research", v1.2 "Test
undocumented behavior of (direct,x) addressing mode"). No second
independent measurement is known. The data sheet (section 7.2) names
other modes with special E=1 / DL=0 behaviour, [d], [d],Y and PEI
("which will increment ... into the Stack area"), and gives the full
0000-FFFF range for DL != 0; candidates for the same test on the
console: (d), (d),Y, JSR (a,X) and the stack wrap of PEA/PER/PHD/PLD/RTL
(section 7.1). SingleStepTests/65816 issue #3 (SBC ($b0,X), case 8668,
https://github.com/SingleStepTests/65816/issues/3) is the fixture-side
dispute of the same quirk.

### 4.2 WDM ($42): the second cycle is a signature fetch

WDM is two bytes and two cycles. Its second cycle fetches the byte at
PB:PC+1 with VPA (a program fetch) and discards it, as the signature
fetch of BRK and COP does; on the S-CPU that cycle costs speed(PC+1), 8
clocks from SlowROM or WRAM, 6 from FastROM (CHOICE, 2026-10-24,
recorded in docs/snes-architecture.md section 9). The table row carries
it (`recompiler/w65816_table.cpp`, WDM).

What the sources say:

- DATASHEET: the WDC W65C816S data sheet (2024-03-13,
  https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf)
  lists WDM in the opcode matrix (table 5-4) as addressing mode "i" with
  "2,2" (2 bytes, 2 cycles) and in table 5-5 as "WDM* No Operation 42",
  but table 5-7 (the bus cycles) has no row for it: row 19a "Implied"
  names 25 one-byte opcodes with an internal second cycle (VDA = VPA =
  0), WDM not among them; the nearest row with a second byte is 22j
  BRK/COP, whose cycle 2 is a program fetch of "PBR,PC+1 ... Signature".
  The data sheet does not decide the question.
- DOC/INFERENCE: 6502.org "65C816 opcodes"
  (https://6502.org/tutorials/65c816opcodes.html): "acts like a 2-byte,
  2-cycle NOP ... The second byte is read, but ignored"; no measurement.
- EMU-CONSENSUS for the fetch: ares (`instructionPrefix`, `L fetch()`),
  MesenCE (`AddrMode_Imm8(); WDM()`), LakeSnes (`cpu_readOpcode`), MAME
  (`OPER_8_IMM()`), none with a cited test.
- IMPL against it: SingleStepTests/65816 (generated with Clock Signal,
  `op(implied, WDM)`) records the second cycle as internal, no VPA, no
  data; hackbench PR #659 (2026, not cycle accurate) says "WDM makes no
  bus read".
- MEASURED/TEST-ROM-HW: none found (research of 2026-10-24); gilyon's
  cputest checks WDM's register result only, not its clocks.

Why the fetch: it is the data sheet's nearest analogue (22j), the four
emulator lines agree, and it is the only price under which stage S and
stage E meet aresref in every field, mclk and pc included, on gilyon's
cputest-basic and cputest-full (docs/snes-oracles.md section 6; before
the change the WDM frames were the single tolerated difference). The
20,000 SingleStepTests cases of opcode $42 are a known deviation of the
harness, compared in full with the second cycle rewritten to the fetch
(`tests/w65816/w65816_sst.cpp`), beside the 264 (dp,X) cases of 4.1.

Measurement that would settle it (not done; nobody has published one):
from SlowROM (bank $00-$3F, $420D = 0), block A of 64 x `WDM #$EA`,
block B of 64 x `NOP NOP` (the same byte count); latch the H/V counters
through $2137 before and after each block and read $213C/$213D. A fetch
costs 8 + 8 clocks per WDM, an internal cycle 8 + 6: over 64
instructions 128 master clocks, 32 dots, far above any latch jitter.
Counter-check from FastROM ($80:xxxx, $420D = 1), where both forms cost
6 + 6 and the difference must vanish.

Where the sources differ (section 4):

- WDM: [SST] (internal second cycle, 6 clocks) against the data sheet's
  BRK/COP analogue and ares, MesenCE, MAME, LakeSnes (fetch, 8 clocks
  from SlowROM). Taken as the fetch (4.2); the harness counts the 20,000
  suite cases of opcode $42 as a known deviation.
- [SST] has no such quirk and expects the high byte from D+dp+X+1
  without wrap ($300 in the example). This concerns 264 emulation-mode
  cases (opcodes $01 $21 $41 $61 $81 $A1 $C1 $E1 with D.l != 0 and
  (D+dp+X) & $FF = $FF). The harness names them, checks that the first
  difference is exactly that pointer read at the wrapped address, and
  counts them as a known deviation instead of a failure; every other of
  the 5,080,400 cases matches the suite in state, memory and bus cycle
  list.
- The [GILYON] README does not say how the behaviour was established;
  that the ROM is meant to pass on the console and that ares implements
  it independently is the evidence here.

## 5. Open hardware questions and measurement plans (research package A)

State of 2026-10-24 after two independent external research passes
over the same 18 questions (A1-A18; the question list and both answer
sets are not published). The first pass (R1) found the newer
measurements and forum findings quoted below; the second pass (R2) read
the standard documents only, rates almost every question as open for
want of raw traces and board revisions, and is the conservative floor
of each entry. Both are named per question; where they differ, both
readings stand. Each entry: what the sources say with their class, what
the code does, and the console test that would decide it. "CHOICE"
means the sources are silent or differ and the code follows the
hardware-nearest one; "open" means nothing beyond INFERENCE exists.
The primary-source review (2026-10-26) reclassified A3, A4, A5, A6, A8, A10,
A11 and A14 on primary sources found by a targeted search on 2026-10-25
(repositories, issue comments, netlists, archived dumps; the search
notes are not published); each entry names the source, author,
date, console and revision as far as given, and whether raw data exist.
The code follows the new evidence where it contradicted a CHOICE (A3,
A4, A5, A8); everything else stays as it was. The schematic review
(2026-10-26) read rgalland's S-CPU-A schematic as a netlist (no further
web search) and decided three questions left open by the primary-source review: the V-IRQ
at VTIME=0 (A17, 2.4), the latch position against HVBJOY bit 0 (A3,
2.5) and the $2180-to-WRAM value (A11, 3.5).
URLs of the sources used in this section:

- WDC W65C816S data sheet (2024-03-13):
  https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf
- SNESdev wiki: https://snes.nesdev.org/wiki/Timing,
  https://snes.nesdev.org/wiki/S-SMP, https://snes.nesdev.org/wiki/PPU_registers,
  https://snes.nesdev.org/wiki/MMIO_registers, https://snes.nesdev.org/wiki/PPU_pinout
- Anomie's documents: https://wiki.superfamicom.org/timing,
  https://wiki.superfamicom.org/registers; the older mirror
  https://snesdev.mesen.ca/wiki/index.php?title=SPC700
- fullsnes mirror: https://patrickjohnston.org/ASM/ROM%20data/snestek.htm
- bsnes PR #78 (auto-joypad): https://github.com/bsnes-emu/bsnes/pull/78
- MiSTer SNES_MiSTer PR #513 (IRQ, PAL, HDMAEN latch; a draft marked
  "not complete" by paulb_nl): https://github.com/MiSTer-devel/SNES_MiSTer/pull/513
- nesdev forum: t=24391 (paulb_nl, IRQ), t=24610 (lidnariq, S-SMP
  clock), t=24822 (HDMA failure), t=24940 (gilyon), t=10881 and t=13725
  (blargg, timer clear), t=14544 (refresh), t=22339 (cycle penalties),
  p=21890 (byuu, IRQ delays): https://forums.nesdev.org/viewtopic.php?t=NNNNN
- undisbeliever: https://undisbeliever.net/blog/20250313-smpspeed.html,
  https://github.com/undisbeliever/snes-test-roms
- TASBot smpspeed tool: https://github.com/TASBotL3C/smpspeed-usb2snes
- J. Christy, SNES Protocols (1996): https://www.repairfaq.org/REPAIR/F_SNES.html
- gilyon/snes-tests: https://github.com/gilyon/snes-tests
- VitorVilela SnesSpeedTest: https://github.com/VitorVilela7/SnesSpeedTest
- 6502.org 65C816 opcodes: https://6502.org/tutorials/65c816opcodes.html
- R2's additional pages: https://sneslab.net/wiki/WDM,
  https://github.com/undisbeliever/snesdev-notes/blob/master/pages/65816-opcodes.md,
  https://snes.nesdev.org/wiki/Controller_connector,
  https://snes.nesdev.org/wiki/Controller_reading,
  https://snes.nesdev.org/wiki/DMA_registers,
  https://snes.nesdev.org/wiki/Reading_and_writing_PPU_memory,
  https://emuverse.ru/downloads/datasheets/processors/65816/65816_programming.pdf

### 5.1 WDM ($42): fetch or internal cycle (A1)

CHOICE, fetch (4.2). R1: DATASHEET undecided, EMU-CONSENSUS fetch,
[SST] internal, no measurement. R2: open; "2 cycles" is DOC (SnesLab,
undisbeliever's opcode notes, Anomie) and says nothing about a 6-clock
I/O cycle against an 8-clock fetch on the ROM bus. Two research rounds found no primary evidence: only an own
measurement can settle it. Test: the WDM-against-NOP sweep from SlowROM
with the $2137 latch (4.2); R2 adds logging VPA/VDA/RWB and the CPU
clock at the 5A22, on at least one console per CPU revision, and a
sweep over all 256 signature bytes with registers, flags and open-bus
follow-up values compared.

### 5.2 S-SMP timer outputs $FD-$FF after power-on and reset (A2)

CHOICE: 0 (the code; ares; docs/snes-audio-spec.md section 9). R1 and
R2 agree that it is open and unmeasured. DOC against DOC: the SNESdev wiki S-SMP page says "On power-on: TxOUT = 0 /
On reset: TxOUT = 0"; Anomie's SPC700 document (mesen.ca mirror,
MesenCE's source) says "On power on, all three TnOUT have the value $F"
and "On power on, all three TnTARGET have the value $0". No touchstone:
blargg's `timer_at_power_reset`, named here until 2026-10-26, does not
test the S-SMP timers (disassembled 2026-10-26, see 5.4: the ROM never
addresses $2140-$2143, uploads no SPC700 code and measures the CPU/PPU
phase after an H-IRQ). Whether a $F raw value could even be seen after
the IPL depends on CONTROL: a 0 to 1 edge of an enable bit clears stages 2 and 3 (Anomie,
confirmed by blargg's spc-timer-clear on hardware, nesdev t=10881), and
the IPL does not enable the timers (audio-spec 4). Test: run
an SPC program whose first instructions read $FD-$FF and return them
through $F4-$F7, run once cold and once by the reset button; separately on a two-chip APU and a
1CHIP; R2: record cold start, warm start, the reset button and the
timer enable edges apart, and log the IPL run time as a factor. The
code switches to blargg's expectation once a console result exists.

Overload (Kris Bleakley) recorded SPC700 bus cycles with a logic
analyzer (nesdev t=16140, 2017-06; higan v103r03-r06): cycle 3 of the
(X)+ instructions reads no I/O, so it does not clear $FD-$FF (MEASURED,
traces unpublished); it says nothing about the start value.

### 5.3 Auto-joypad strobe, latch length, HVBJOY bit 0 (A3)

Raised (primary-source review): the latch pulse and the clock pulse are MEASURED.
Ownasaurus (TASBot), logic analyzer on the controller port of a US
console during a Super Mario World TAS replay with his TAStm32, MiSTer
SNES_MiSTer issue #208 (https://github.com/MiSTer-devel/SNES_MiSTer/issues/208,
comment of 2020-02-13; console revision and analyzer model not named;
raw data only as a PNG): latch pulse 12.04 us, latch distance 16.64 ms
(once per frame), clock pulse 5.9 us, clock period 11.91 us. At 21.477273
MHz that is 258.6, 126.7 and 255.8 clocks: the 256-clock grid, 128
clocks low, and a latch of 256 clocks (both 128-clock latch steps), not
ares' 128 (2.2, 2.6). J. Christy's "12us" (1996) agrees. Code since
2026-10-26: the latch from T0 to T0+256 (2.5, 2.6). Not measured: the
latch position against VBlank (Ownasaurus offered a measurement against
the video signal on 2020-02-27; none was published) and the HVBJOY bit
0 edge against the latch (the 128-clock question). The schematic review (2026-10-26)
decided the second from the S-CPU schematic: the latch rises 128 clocks
before bit 0 (DATASHEET + INFERENCE, 2.5; the code since then T0-128 to
T0+128); the first stays as before (T0 on the 256-clock grid in
H=130..384 of the first VBlank line, DOC + TEST-ROM-HW). Open from the
same review: undisbeliever's "0008 1000" on his 1-CHIP console in
clear-autojoy-after-autojoy-active (2.5), and which side of the bit-0
flop wins for a clear between T0 and T0+256. Jonas Quinn's hardware tests (higan caed1556,
2020-08-20; bsnes 4ea984b6, 2021-04-04: the shift registers start at 0
and clearing $4200 bit 0 during the read stops it; TEST-ROM-HW, ROM not
published) agree with 2.6. Earlier state: the 256-clock grid, the
130..384 window and 4224 clocks DOC + TEST-ROM-HW (2.2); R2 kept them as
DOC. undisbeliever's auto-joypad ROMs (TEST-ROM-HW, zlib) are the ctest
material (docs/snes-oracles.md section 11); HVBJOY bit 0 after a clear
inside the latch phase is TEST-ROM-HW indirect (2.5); enable-autojoy-
late-test-2 and clear-autojoy-1st-vb-sl were the evidence for
MesenCE's earlier pulse position (2.5) and agree with the schematic.

### 5.4 PPU and counters over the reset button (A4)

Raised (primary-source review) from CHOICE to DATASHEET + INFERENCE (die netlists)
with MEASURED support; the code's former CHOICE "the PPU counters keep
running" contradicted it and was reversed on 2026-10-26 (2.8).

- PPU side, [VISUAL 5C78] (S-PPU2) and [VISUAL 5C77] (S-PPU1), read
  statically on 2026-10-25 and again in detail on 2026-10-26 (not
  simulated): the S-PPU2's /reset pad becomes the XIN-synchronous
  `_+/reset`; `_/hvcres` = `_+/reset` AND `_/hvcmode` (`hvcmode` is a
  test input that otherwise isolates the VRAM bus). Each of the 9 H and
  9 V counter bits is NOT(NAND(slave, reset)), i.e. forced to 0 while
  /RESET is low, not frozen, and the dot dividers stop; at the release
  the counters start from 0. The S-PPU1 (the timing master: it drives
  /HCLD, /VCLD and FIELD, the S-PPU2's own 261/311 decode is unused)
  forces its counters the same way, without a synchroniser, and its
  field flip-flop to 0. /RESET also clears SETINI bits 0 (register and
  latch), 2, 6 (S-PPU2) and 7 (S-PPU1) and sets force blank; SETINI bit
  1 is not reset; VBlank cannot be set during reset. Confidence: high for
  the logic, medium for dot-exact timing.
- The reset button reaches both PPUs: spla (khaydarian, oscilloscope
  pin survey, 2020-03-07, SNS-CPU-RGB-02 with S-CPU B, 5C77-01, 5C78-03,
  NTSC): PPU1 pin 98 /RESET "high, except when reset switch is held",
  PPU2 /RESOUT0/1 the same (MEASURED [SPLA]). fullsnes' "The two PPU
  chips ... aren't affected by the /RESET signal" concerns the cartridge
  bus reset, not the button.
- S-CPU side, [RGALLAND] read as a netlist by the search of 2026-10-25
  (DATASHEET, own derivation INFERENCE): without a reset input
  (preserved) HTIME/VTIME $4207-$420A (reset pins marked no-connect),
  the $43xx channel parameters (D-latch arrays, also the HDMA address
  latch and reload flag) and the maths operands and results; on ~MRST
  $4200, $420D, the cycle-length flip-flops, the DMA and maths
  sequencing and the S-CPU's internal H/V counters. This supports the
  values of the table in 2.8 (DATASHEET besides DOC); the no-connect
  marks should be checked on the die photograph.
- paulb_nl (nesdev t=24391 pages 97-100, MiSTer issue #520, 2026-10):
  the refresh position read by his frame_timing_test differs between
  power-on and reset (85/90 against 8F/86 in REFRESH+2/+4, the ROM's
  comments); his console is "2/1/3"; MesenCE meets it only with $2133
  bit 0 = 1 at power-on (TEST-ROM-HW by his word, one console, cause
  open).
- byuu v097r32 (higan 06d44b48, 2016-04-03): a patch crashed on a
  console only after the reset button; consistent with S.l - 3 (5.5).
- blargg's `timer_at_power_reset` (snescentral article 1115, archive
  2010, no licence, external only) belongs here, not to A2: disassembled
  2026-10-26 (HiROM, reset vector $891A), it sets HTIME=$D2 and the H-IRQ
  only, syncs the CPU to the H-IRQ by WAI (avoiding V=$EF), latches
  $2137 twice and prints 4 x H2 - 576 + 2 x ((H1 xor H2) and 1): the
  position of the second latch in master clocks from dot 144 with
  2-clock resolution, i.e. the phase between the CPU clock and the dot
  clock after the sync. It passes when the value is $000E at power-on
  and again after the reset button (a WRAM marker at $0203 tells the
  two apart). It does not show whether the counters run over the reset,
  only whether the reset shifts that phase. MAMR and aresref print
  "000E / Press reset" at power-on; the reset half cannot run (no
  button in System). The article's screenshot shows 000E, its origin is
  not stated.
- Earlier documentation: Anomie "HTIME is initialized to $1FF on power
  on, unchanged on reset", TIMEUP "cleared on power on or reset" (DOC);
  ares and MesenCE restart the counters (EMU-CONSENSUS, derived).

Code (2.8): Timing::reset(t) takes t as the release of the button: the
PPU counters at V=0 H=0 of field 0, interlace and overscan off, the
clock grids from t; HTIME/VTIME, maths and $43xx kept (like_ares resets
them as ares). Ppu::reset_line(t) clears SETINI bits 0, 2, 6, 7, sets
force blank, clears the field flip-flop and restarts the pipeline at t;
the rest of the PPU's registers is kept. The button is pressed by the
machine interface's reset (docs/machine-interface.md section 7.1), not
by snes_headless or the oracles, so nothing in the oracle comparisons
changes. Open: the PPU register state after the button in full (only
SETINI and force blank are traced), A, X.l, Y.l (5.5), and the phase
question of timer_at_power_reset on a console. Test: as before, patterns
into HTIME/VTIME, WRMPY/WRDIV, every $43xx and the PPU write registers,
press reset, latch $2137 first in the handler; run timer_at_power_reset
cold and by the button; undisbeliever's `reset-position-test.asm`
(results not published); krom's CPUMSC reset test (PeterLemon/SNES,
licence unclear, external only; runs on an SD2SNES with the reset
through the cartridge port; ares v127, issue #427, and bsnes, issue
#235, fail it: a difference against aresref is an ares-side deviation).

### 5.5 Reset sequence: stack cycles and register survival (A5)

Raised (primary-source review) to MEASURED for the bus cycles and the end value of S:
[SRG320 LA] `SCPU&SMP reset timing.png` (MiSTer-devel/SNES_MiSTer,
`hw/LA captures/`, commit 9a1955e6, 2024-09-18, trigger 2024-09-11;
logic analyzer at about 85 MHz on a console, revision not named, most
likely the reset button since S was $01E5; raw data only as a PNG;
channels SYSCLK, CA, D, CPURD_N, CPUWR_N and the S-SMP's clock, address,
data and write strobe). S-CPU: one cycle at the old PB:PC, then $0001E5,
$0001E4, $0001E3, then $00FFFC/$00FFFD and $008000, CPUWR_N inactive
throughout. S-SMP: $01CA, $01C9, $01C8, then $FFFE/$FFFF and the IPL from
$FFC0, SMP_WE_N inactive. So the data sheet's three read cycles with
the address stepping down hold on the 5A22, S.l is kept over the reset
and counts down by 3 (no fixed $01FC), and the S-SMP's reset has the
same shape. Support: Garth Wilson's W65C816S bus logs (6502.org t=4129,
2016) give six different S values after reset (MEASURED, the WDC chip);
byuu v097r32 (2016) fits S.l - 3 (his "pushes" is refuted: nothing is
written). Code since 2026-10-26: the stack cycles read S, S-1, S-2 of
the present S, A, X.l, Y.l and S.l are kept (2.8; ctest
`test_reset_from_s` in `w65816_cpu`, `snes_system`, `snes_system_exact`);
power-on starts at S=$01FF (CHOICE), so Zelda and the oracle files are
unchanged. R2 had rated the sequence open for the 5A22; that is
superseded. The S-SMP's reset sequence is not modelled as a bus
sequence (the SMP starts at the IPL; docs/snes-audio-spec.md). Open:
which of A, X.l, Y.l survive the button, and the S of a real cold start.
Test in 2.8.

### 5.6 DRAM refresh: pulse shape, DMA, revision 1 (A6)

Position and duration DOC + TEST-ROM-HW (2.2: 40 clocks, 538 then the
multiple of 8 nearest 536; fullsnes "H=133.5 ... duration 40 clks/10
dots"). Raised (primary-source review):

- 40 clocks in one piece, MEASURED: [SRG320 LA] `SA-1 Speed Test
  @85Mhz/WRAM - ROM (refresh).png` (commit 68fe1a8c, 2025-09-20, trigger
  2025-09-19; real SA-1 cartridge, console revision not named; PNG
  only), evaluated by pixel count by the search of 2026-10-25: SYSCLK
  stays low for about 43 clocks (40 extra) at the cartridge port, /RD
  inactive, and the CPU continues without a phase shift. The CPU sees
  one 40-clock hold: the code's model (2.2, 2.8).
- The pulse structure on the REFRESH line, MEASURED as a statement: srg320
  in MiSTer issue #350 (2025-08-13, paulb-nl agreeing 2025-08-18): the
  REFRESH line is the 2.68 MHz SYSCLK "with a length of 5 cycles", five
  pulses of 8 clocks; no image of the channel. ares' note "5-3 per logic
  analyzer" (`ares/sfc/cpu/timing.cpp:23`) came with higan v106r62
  (commit c2d0ed4c, 2018-09-10); byuu's reason (nesdev t=17779, 2018-09-09)
  is a remembered logic-analyzer report and the SA-1 throughput measured
  by VitorVilela, which fits the pulsed model; older: byuu, nesdev
  p=128588 (2014-05-09), an unnamed person's oscilloscope, "5 cycles
  high, 3 cycles low; repeated five times". fullsnes' four pulses of 10
  clocks is the minority reading.
- Revision 1, re-evaluated 2026-10-26: lidnariq's Saleae CSV traces
  (nesdev p=173441, t=14281 page 8, 2016-06-13; a "1-1-1" console, S-CPU
  revision 1; 24 MS/s; channels VA14, VAA13, VAA12, VAB13, VAB12, /VRD,
  REFRESH, /CSYNC; seven files, one per BG mode, about 85 ms each; raw
  data yes, not redistributed, no licence stated). /CSYNC gives 1524.27 samples
  per line (master clock 21.4766 MHz from the fit, 262-line fields with
  the short line every other field). The REFRESH channel shows only
  one-sample spikes (42 ns, 4595 of them, never two samples wide; rest
  level 0), on 22 % to 87 % of the lines depending on the file, in
  clusters of 1 to 3 per line; lidnariq called the probe "suspect". Not
  usable as a waveform: pulse width, the 5:3 duty cycle and the number of
  pulses per line cannot be read (a clean 5-clock high phase would show
  as 5 to 6 samples). Usable as timing marks: every spike lies 778 to
  823 samples (696.5 to 736.7 clocks) after the falling /CSYNC edge, on
  a 4-clock raster, the spread within a position 4 to 15 ns; within a
  line the spikes are 9, 18, 27 or 36 samples (8, 16, 24, 32 clocks)
  apart, never more. So on revision 1 the REFRESH pulses have an 8-clock
  period (four pulses of 10 clocks would give 11, 22 or 34 samples, never
  seen), at most five of them, inside a 40-clock envelope, and the
  start moves by 0, 4 or 8 clocks from line to line (a CPU cycle
  boundary). The absolute H position (534/538 against a revision 1
  value) cannot be decided: the /CSYNC edge against H=0 is not known to
  better than 10 to 20 clocks (MEASURED raw data, INFERENCE for the
  reading).
- DMA paused or cut: no measurement. MiSTer's core (commit bd4d8fbe,
  2024-10-01, "based on S-CPU schematics and hardware research") takes
  REFRESHED only at the bus edge and stops CPU and DMA together, so a DMA
  pauses between two bytes (IMPL from DATASHEET [RGALLAND]); it supports
  the code's choice.

CHOICE unchanged: the CPU is held 40 clocks; stage E steps the
multiply/divide unit five times during it after ares (2.7, IMPL,
compatible with five pulses). Revision 1 positions not modelled (2.2).
Test for the rest: a logic analyzer at 100 MHz or more on REFRESH,
SYSCLK and /WRAMSEL, a GP-DMA across the refresh, on a version 1 and a
version 2 S-CPU, with a known H reference (HBLANK at PPU2 against a
$2137 latch loop).

### 5.7 HDMA past the end of the line (A7)

Open, EMU-CONSENSUS only (3.4: it continues); R1 and R2 agree, and a
second round found no primary evidence either: only an own measurement.
By Anomie's costs the
worst case is 18 + 8 x (8 + 16 + 32) = 466 clocks (the SNESdev wiki
gives the same maximum), from H=1104 ending at about 1578 > 1364, so
the console must do something. VitorVilela's SnesSpeedTest (TEST-ROM-HW,
licence unknown) shows only the total cost of eight indirect channels
(2.60 MHz without, 1.82 MHz with HDMA on ROM/WRAM), not the line-end
behaviour. Test: eight indirect channels in the 4-byte mode with the
repeat bit, destination $2122/$2121 (CGRAM) so that every unit is
visible as a colour, the CPU time-stamping its resumption each line
through $2137; a logic analyzer on /PAWR over two lines shows a cut, a
continuation or a shifted next start.

### 5.8 Interlace: when SETINI bit 0 is sampled (A8)

Raised (primary-source review) from CHOICE (V=128, after ares) to DATASHEET +
INFERENCE; the code follows since 2026-10-26 (2.1). Static reading of
[VISUAL 5C78] and [VISUAL 5C77] (search of 2026-10-25, traced in detail
2026-10-26; not simulated):

- S-PPU2: the register bit `_screen_interlace` (node 2826) reaches the
  storage node 11741 through a transmission gate (transistors t5871,
  t38392) clocked by NOT `_+vblank`, with a feedback gate clocked by
  `_+vblank`; the output is node 3440 `_/interlaced_enabled_this_frame`.
  The latch is transparent outside VBlank and holds during it.
  `_vblank` is an SR latch set from the registered V decoder 225 (240
  with overscan; the overscan select uses the register bit directly,
  not latched) and cleared at V=0, about one dot after the V step. The
  raw bit feeds nothing but the latch.
- S-PPU1 (the timing master): the same latch (register bit 2698,
  storage 26469, output node 2702 `_/interlace_en`). Its consumers: the
  field length mux (node 3011: in field 0 with the latched bit, /VCLD
  comes from the one-line-delayed copy of the 261/311 decode, so the
  field has 263 or 313 lines), the NTSC short line (node 3008, the same
  term as the S-PPU2's node 3702: V=240, NTSC, field 1, not interlaced),
  the PAL long line (node 27058, one more dot on V=311 in field 1) and
  the mode 5/6 interlace. The field flip-flop toggles at every fall of V
  bit 8, with no interlace input.
- Hence: the value at the start of VBlank decides the field length, the
  short line and the long line of that field; a write in VBlank acts
  from the next field; during the active picture the latch follows the
  register at once. No sampling point at V=0 or V=128 exists. MesenCE
  (V=0/240) and LakeSnes (V=225) are closer than ares (V=128).

Code: Timing::set_interlace changes the running field's shape for a
write before V=vdisp, the next field's for a write in VBlank (ctest
`snes_timing`). Against aresref the two differ only for a write between
V=128 and the start of VBlank; Zelda (SETINI 0 throughout) and
rainwarrior's Two Ship (mode 5 interlace from read 60, 300 frames) stay
equal in every field in both stages. Other earlier material:
undisbeliever's `setini-early-read-*` (TEST-ROM-HW, zlib; the EXTBG
early-read glitch, a different question; not modelled). Confirmation
still wanted: a V-IRQ sweep toggling SETINI bit 0 at line N per frame
and measuring the frame length through $2137 latches at V=0; or a
simulation in Visual 5C78.

### 5.9 PAL: line structure and event positions (A9)

Raised: the long line only with interlace on, field 1, V=311, 1368
clocks, no PAL short line (2.1, DOC, two documents, ares the same;
ctest; R2: DOC, no board-revision trace behind it, the PAL event
positions and the SNSP-CPU-01/02/1CHIP comparison open). Event positions on PAL as on NTSC: INFERENCE with partial
TEST-ROM-HW from MiSTer PR #513 (2.9); its own note: on the interlaced
PAL field the last line is the long line, (311,339) and (0,339) fire
once each, and "hardware has not been measured for that case". Test
in 2.9.

### 5.10 Power-on contents of WRAM, VRAM, OAM, CGRAM (A10)

The code and the oracles fill with 00 (docs/snes-oracle-format.md
section 6, a comparison convention, CHOICE; unchanged). Raised (primary-source
review) for the hardware statement: blargg's power-on dumps from
snescentral article 1115 (`mem_dumps.zip` of 2008-08-09: WRAM, VRAM,
OAM, CGRAM of two consoles named "big" and "mini"; `wram.zip` of
2010-03-14: WRAM of the same two; no licence, no documentation: local,
not distributed; MEASURED raw dumps, method, cold-start
conditions and console models not stated, "big"/"mini" probably a
SNES-001 and a SNS-101, INFERENCE). Statistics (search of 2026-10-25,
WRAM re-checked 2026-10-26):

| Dump | Most frequent bytes | WRAM same console 2008 against 2010 |
|---|---|---|
| WRAM big | $55 (71 % in 2008, 58 % in 2010), then $5D, $57 | 80.3 % of the bytes equal, 2.9 % of the bits differ |
| WRAM mini | $F5, $5F, $05 (about 9 to 11 % each) | 88.6 % equal (shifted by one byte), 1.5 % of the bits |
| VRAM big | $00 50 %, $FF 50 %, in stripes of 52 bytes on average | - |
| VRAM mini | $00 33 %, $FF 32 % | - |
| OAM, CGRAM | mixed | - |

Between the two consoles 0.5 % of the WRAM bytes are equal and 47 % of
the bits differ (chance). So the power-on content is console-specific,
strongly biased and stable over two years: a fingerprint of the DRAM
cells, not noise. byuu's model (higan v104r04/r05, 2017-08-24, "modeled
after one of my SHVC 2/1/3 systems": stripes of $00/$FF, rarely one or
two flipped bits; DOC) fits the VRAM picture; his own dumps (board
thread t=1758, a tweet of 2017-08-23 about four consoles) are not
reachable (the byuu domains are excluded from the Wayback Machine). byuu
2010 (forums.bannister.org #60751): WRAM "completely unpredictable",
some games run only with a $55 fill (DOC, no titles). MiSTer's "Initial
WRAM" options SNES1/SNES2 could not be traced to a dump. For MAMR the
00 fill stays right for the oracle comparison; a game that depends on
the power-on content would need a console-specific pattern, which the
runtime does not offer. Test for a statistic: 20 or more cold starts per
console with a recorded time unpowered, WRAM to SRAM by DMA, VRAM, OAM
and CGRAM through the read ports.

### 5.11 Invalid DMA cases (A11)

The S-CPU-A failure after an HDMA to INIDISP is the one newly
documented case (R1; DOC on TEST-ROM-HW, 3.5, deliberately not
modelled). R2: the whole matrix open; the SNESdev DMA page itself marks
$4000-$41FF as an unclear A-bus target.
The other cases of 3.5 (WRAM to WMDATA, A-bus on $21xx/$43xx, the HDMA
table in register space, DAS = 0, GP-DMA and HDMA on one channel, $420B
during HDMA) stay at fullsnes/Anomie and the CHOICEs recorded there;
MiSTer PR #513's `hdmaen_latch_test_2` has "no hardware count" (bsnes
52, MesenCE 28-32, EMU in conflict). Test: one case per round (WRAM to
$2180, A-bus on $21xx/$43xx, HDMA table in $43xx, DAS = 0, MDMAEN
during an active HDMA on the same channel); after each read DASn, A1Tn
and the target RAM, on S-CPU, S-CPU-A, S-CPU-B and 1CHIP.

Raised in part (primary-source review): byuu's DMA/HDMA tests (snescentral article
1123, https://snescentral.com/article.php?id=1123, "DMA and HDMA tests",
Evan G, 2017-06-24; author byuu, 2005-2010, sources included, no licence:
"Do not use material on this site without permission"; kept under
tests/data (local, not distributed)) pass on consoles: MiSTer
SNES_MiSTer issue #105 (https://github.com/MiSTer-devel/SNES_MiSTer/issues/105),
James-F2, 2019-06-26, passes per runs on a Snes Jr (1CHIP) and an
SNS-CPU-GPM-01: test_dma 5/5 and 10/10, test_dmasync 5/5 and 10/10,
test_dmavalid 5/5 and 10/10, test_hdma 18/20 and 18/20, test_hdmasync
2/10 and 4/10, test_hdmatiming 4/18 and 4/20, test_mdrhdma 10/10 and
10/10; MP2E the same day on a 1chip-03: all but test_hdmatiming
(TEST-ROM-HW; the HDMA tests are unstable on the consoles themselves).
test_dmavalid checks the two invalid WRAM cases: WRAM to $2180 (the
write does not happen, WMADD does not move, $43x2 counts up, DAS to 0,
the DMA takes its time) and $2180 to WRAM (the same, but a byte is
written; byuu's source comment gives his console's value: "[00] DMA
write did occur, but wrote unknown value (not MDR, which would be
#$ea)"; the test only requires that it is not the old $AA). Run
2026-10-26 (docs/snes-test-evidence.md, docs/snes-oracles.md section
12.1): every ROM shows the pass colour in MAMR stage S and E and in
aresref. The value written by $2180 to WRAM differs: aresref 00 (byuu's
console value), MAMR the bus value $EA (CHOICE after Anomie's
"(initially) the Open Bus value", 3.5): a finding against the CHOICE
(TEST-ROM-HW by the author's comment, one value, console not named).
Decided in the schematic review (2026-10-26): 00. Besides byuu's comment, the higan
test-ROM collection keeps an SRAM image next to the ROM
(jonasquinn-test-roms/test_dmavalid_v01/test_dmavalid.srm, origin not
stated, most likely the author's console run behind his comments): its
32 KiB equal MAMR's SRAM after the run byte for byte, the H/V counter
values $CE/$36 of all three tests and the 00 included; the S-CPU
schematic excludes the bus value as the source (3.5). test_dmavalid is
now equal to aresref in every field in both stages. Which of two S-WRAM
behaviours gives the 00 (the port's read driver held off during the
write and an internal 0 stored, or the port driving a cell that reads
00) is open; test: run the $2180-to-WRAM DMA with WRAM[WMADD] = $5A and
again with $A5 and read the target: a byte that follows WRAM[WMADD]
means the port drives. Two more partial
supports (INFERENCE from games on consoles): HDMA ends a GP-DMA on the
same channel (bsnes v0.017, 2006-08-27: Bugs Bunny Rabbit Rampage and
World Class Rugby run only so); $420C=0 during a running HDMA finishes
the line with the latched channels (Weaponlord, MiSTer #486, PR #502,
2026-06/07).

### 5.12 WAI latency (A12)

DOC plus DATASHEET reading, the console latency unmeasured. R2 cites
Anomie timing.txt: WAI ends 12 master clocks, two I/O cycles, after
/IRQ or /NMI (DOC, a described timing-test method, no trace or
revision). The code does exactly that (`recompiler/w65816_exec.cpp`,
the wait step, ctest `w65816_cpu`): the idle cycle whose poll saw the
line runs to its end and one more internal cycle follows, 12 clocks,
then the interrupt entry; a line already present at WAI's own poll
costs nothing extra, since the two internal cycles of the WAI row are
those cycles. The data sheet (table 5-7 row 19d with note 9 "Wait at
cycle 2 for 2 cycles after NMIB or IRQB active input"; section 2.24: RDY
is pulled low and returned high "when a RESB, ABORTB, NMIB, or IRQB
external interrupt is active") is read the same way by ares and
MesenCE (EMU-CONSENSUS, the code's model), but its wording also admits
6 clocks more (18), depending on where "IRQB active" lies against the
poll; R1 lists that as the open point. MiSTer PR #513 carries an
"IRQ_LINE_DLY = 9" from the flag to /IRQ, "provisional until hardware
separates the flag time from the /IRQ time" (IMPL). Test: an
H-IRQ at a fixed HTIME; variant A waits in WAI, variant B runs a NOP
loop from FastROM; the handler latches $2137 at once; the H difference
over 64 HTIME phases, averaged, gives the WAI latency in 6-clock
resolution.

Primary-source review: class unchanged (the WAI latency on the S-CPU is still not
extracted from a measurement). New material: [SRG320 LA]
`mode7_wai_ops83.png` (commit f0e6d4db, 2024-09-25; HTIME 0/1/2, with
H/V counter and HBLANK channels; PNG only, the exact clock count not
evaluated, its H_CNT probably counted by the analyzer from the HBLANK
edge) shows the order: a discarded opcode read at PC+1, four stack
writes, the vector. gfoot's oscilloscope on a WDC 65C02 (6502.org
t=7732, 2023-08-30/31) shows WAI cycle 2 repeated and then cycle 3,
"two cycles and change" to the next instruction (MEASURED, other chip),
which supports the two cycles after the detection; Garth Wilson's
W65C816S logs (t=4129) show RDY pulled in cycle 2. paulb_nl's
`snes_frame_timing_test` (MiSTer SNES_MiSTer issue #520 and PR #519,
2026-10-22; source with expected values, no licence; the "HW 2/1/3 ...
PASSED 64/64" picture in the issue is byte-identical to the PR's "After"
picture, the output of the fixed MiSTer core, not a console photograph;
"HW c/p1/p2" is read from $4210/$213E/$213F at run time) has 15 WAI
rows and "WAI SEI 10 WAI": MAMR stage S and E meet the author's values
in all of them except WAI+2 and WAI+4 with a pure V-IRQ at VTIME=0, a
question of the IRQ position at V=0, not of the WAI latency (5.17).
That is consistent with the 12-clock model; it is not TEST-ROM-HW,
because the expected values have no published console run (DOC: the
author's documented expectation).

### 5.13 (dp,X) in emulation mode with D.l != 0 (A13)

Raised to TEST-ROM-HW, one source on a 5A22 (4.1); related modes to
check listed there. R2 rates the README alone as DOC plus a test ROM
candidate ("only TEST-ROM-HW once a console run's result protocol is
produced"), stresses that the README says only this addressing mode is
affected and that the test checks no cycles or MMIO. The README's
example (E=1, D=$011A, X=$EE, operand $F7: pointer low from $02FF, high
from $0200) is a single ctest case (`w65816_cpu`,
`test_dpx_gilyon_example`) beside the 264 suite cases.

### 5.14 S-SMP clock in real consoles (A14)

MEASURED, now two series with different methods (primary-source review), kept apart:

- R1: 31965 to 32182 Hz DSP rate, mean 32076 Hz over 143 consoles
  (TASBot survey 2025, warm consoles, one tool); warming adds 8 to 10
  Hz.
- Second series with the APU board revision: a table of 16 consoles
  measured "from logic analyzers" by Artemio (240p Test Suite,
  MDFourier) and plgDavid (Plogue), with infiniteneslives and Lugerius,
  passed on by ghogan42 in MiSTer SNES_MiSTer issue #208 (2020-03-01;
  columns owner, APU type, serial, warm and cold DSP rate; no raw data).
  Examples: SHVC-SOUND rev A 32097.0 / 32089.2 Hz, rev C 32108.4 /
  32100.7, rev D 32075.9 / 32070.0 and 32018.3 / 32010.7, rev E 32111.3
  / 32104.9, rev F 32075.4 / 32073.9; GPM-02 32119 / 32116.9; three
  SNS-101 (Jr) 32020.3 to 32058.9; mean about 32066.5 Hz. Warm is always
  2 to 10 Hz above cold; two rev D modules lie 58 Hz apart, so the rate
  is a property of the resonator, not of the board revision.
- srg320 measured SCLK with a logic analyzer at 50 MHz (MiSTer issue
  #395, 2025-11-01): 4105740 to 4105815 Hz, i.e. 32076.1 to 32076.7 Hz;
  a second console 32074 Hz by smpspeed.
- The S-SMP clock pin: jwdonal measured CPUK at 2.048 MHz with 50 %
  duty (high-impedance probe and a 250 MHz logic analyzer, nesdev
  t=10458, 2013-09-18) and PD3 as the clock enable that halves it to an
  effective 1.024 MHz (t=10518, 2013-09-22/23); blargg had read 1.025
  MHz at 75 % with a frequency counter (t=10458, 2013-09-05), which
  nocash put down to probe loading, and once saw 2.048 MHz. Consistent:
  pin 2.048 MHz, instruction clock 1.024 MHz (nominal 24.576 MHz / 12
  and / 24).
- 24606720 Hz is a calculation, not a measurement: 32040 x 768, first
  written by byuu on 2009-08-14 (forums.bannister.org, post 52693:
  "S-SMP stock is 24576000hz. Clocked at 24606720hz.") and repeated by
  Near in nesdev t=10518 (2013-09-24: the APU sample rate "around
  32040hz. * 768 gets you 24606720hz"); the 32040 Hz is the sample rate
  Alpha-II measured (alpha-ii.com/Info/snes-spdif.html, (c) 2003, an
  oscilloscope picture) and, by Near's memory, anomie. jwdonal wrote in
  the same thread that he cannot get a precise frequency from a logic
  analyzer; later posts calling 24606720 "measured" refer to Near's
  figure. bsnes and ares use 32040 x 768 as apuFrequency (IMPL). The
  figure is not used in this repository.

Other values: the SNESdev wiki's "about 32000 to 32160 Hz" (DOC, method
not stated, footnote nesdev t=24610); nominal 24.576 MHz / 768 = 32000
Hz is DATASHEET arithmetic (the resonator's rating). The rate is a
run-time parameter (2.9, docs/snes-audio-spec.md section 3); 32040 Hz
stays the default for oracle parity. R2's test: a known SPC with a
stable tone against a calibrated frequency counter, cold and warm, with
the resonator's part number.

### 5.15 S-DSP revisions (A15)

Open (R1 and R2, and a second round), no source with hardware origin
for differences between S-DSP, S-DSP A and the 1CHIP variants in echo
overflow, noise, the Gaussian table or clamping
(docs/snes-audio-spec.md): only an own measurement. R2: blargg's
reference implementation is not to be equated with recordings; the
snescentral collection (5.2) has memory dumps (mem_dumps.zip, wram.zip)
of unknown console and licence. Test: three SPC test files
(echo with EFB = $7F/$80 and saturation, noise over all 32 rates, a
Gaussian stress with a pitch sweep on a one-sample impulse), recorded on
a two-chip APU module and a 1CHIP from the digital path (the serial bus
into the DAC) and compared sample by sample with the DSP, the clock
drift of 5.14 removed.

### 5.16 APU port collision (A16)

DOC (Anomie: the OR of old and new); the collision window is unmeasured
(R1 and R2: open, no port trace with a revision); not modelled, reasons
and test in docs/snes-audio-spec.md section 9; R2's test: several
hundred collisions per phase offset and board, both directions logged.

### 5.17 HTIME=0 at H=10; VTIME=0 with HTIME=339 (A17)

Raised (R1): HTIME=0 at H=10 is TEST-ROM-HW with two supports (paulb_nl,
and byuu/Anomie's 10-clock V-IRQ delay, 2.4), and since the schematic review also
DATASHEET + INFERENCE (the S-CPU's H counter holds 0 for two dots after
its clear, 2.4); the double IRQ at (0,339)
and none at (261,339) is TEST-ROM-HW from one console (2.4, ctest in
both stages); the PAL interlace case is unmeasured (5.9).

Conflict recorded (R2): R2 cites Anomie's older formula, TIMEUP at
14 + 4 * HTIME clocks for HTIME > 0 and a special case for HTIME = 0,
"1374 master cycles after the previous line start" (DOC), and holds the
H=10 measurement to be unconfirmed: R2 knew it only second-hand, not
from an independent raw trace, from one console of unknown revision. The
two readings do not contradict each other in the number: 1374 clocks
after the previous line's start is H=10 of the line (1364 + 10), the
same moment as the V-IRQ, which is what paulb_nl measured and what the
code does (2.4, `htime_match`); what remains open is the independent
confirmation, and R2's point stands that one console is not a
confirmation. Decision unchanged: H=10 (TEST-ROM-HW plus the DOC
special case) against ares' and MesenCE's H=14 (IMPL). R2's test: an
HTIME sweep over 0, 1, 338, 339 with a handler toggling a CPU I/O pin
and an analyzer against the H/V edge, separately for VTIME=0, NTSC and
PAL, revisions 1 and 2, and HTIME=339 across the frame boundary. paulb_nl wrote on
2026-10-06 that the MiSTer fix "is not complete" and that test ROMs for
the full HV-IRQ behaviour are in work; a second console has not
confirmed the double IRQ. undisbeliever's auto-joypad ROMs use an
HTIME=0 IRQ (VTIME=210) to align every test; against aresref MAMR's CPU
phase is therefore 4 clocks earlier and the HVBJOY poll counts shift by
one (docs/snes-oracles.md section 11). The ROMs do not measure the IRQ
moment, so they add nothing to the H=10 question.

Primary-source review: paulb_nl's `snes_frame_timing_test` (5.12; expected values in
the source, the published picture is the MiSTer core's output, so DOC,
not a second console) encodes both rules: H0V0 and H0V1 rows with
HTIME=0 at the V-IRQ's time and two IRQs for HTIME=339 with VTIME=0 (at
V=0 and V=1), none for VTIME=261 and none for HTIME=340. Run 2026-10-26
(400 frames, the result read from VRAM): MAMR stage S and E 59 of 64,
aresref 48 of 64; aresref misses exactly the two known deviations of
docs/snes-oracles.md section 10 (H0V0, H0V1: H=14; the first IRQ at
(0,339)) besides the five rows MAMR misses as well. Those five are a new
finding: a pure V-IRQ with VTIME=0 (rows "+2 V0", "+4 V0", "+6 V0" of the
IRQ flag page and "WAI+2 V0", "WAI+4 V0") is expected one dot earlier
than with VTIME=1, where both emulators give the same moment as for
VTIME=1 (H=10; the code keeps H=10 for a pure V-IRQ at V=0, CHOICE in
2.4). If the expected values are the author's console (his 2/1/3, by his
other posts), the V-IRQ at line 0 comes 4 clocks earlier, as the V
counter reads 0 from H=2 of line 0 (2.4). Not changed in the primary-source review.
Decided in the schematic review (2026-10-26) from the S-CPU schematic (2.4): V
reaches 0 through its own clear from the VBLANK fall, one sample before
the V step of every other line, so the V-IRQ at VTIME=0 sets TIMEUP at
H=6 of line 0 (DATASHEET + INFERENCE; the PPU edge order it needs is
the one the measured (0,339)/(261,339) results force). The code applies
V=0 from the sample at H=6 of line 0 in every mode; frame_timing_test
now passes 64 of 64 in MAMR stage S and E (aresref 48). Measurement that
would confirm it directly: in V-only mode read $4211 with its sample
7-9 clocks into line 0 (VTIME=0, bit 7 expected set) and into line 1
(VTIME=1, expected clear), or a logic analyzer on the S-CPU's VBLANK and
HBLANK inputs at the 261-to-0 transition (VBLANK expected to fall about
4 clocks first). srg320's WAI
capture with HTIME 0/1/2 (5.12) is independent raw material for the
HTIME=0 moment once the offset between the HBLANK edge and the PPU's
H=0 is measured; byuu v106r49 (higan 65a3e6c6, 2018-07-19): an IRQ on the
last dot of a field is suppressed, "verified on real hardware in the
past" (TEST-ROM-HW, weak).

### 5.18 Test ROMs with hardware expectations (A18)

Usable in CI by licence: gilyon/snes-tests (MIT; cputest, spctest; the
reference files of docs/snes-oracles.md) and undisbeliever/snes-test-
roms (zlib; docs/snes-oracles.md section 11). R2's rule, adopted:
neither a project description nor "runs on hardware" makes expected
values TEST-ROM-HW by itself; every test ROM in use is listed in the
test evidence register docs/snes-test-evidence.md with its commit,
licence, the origin of its expected values, the board revision, the raw
data and the emulator comparison, and SingleStepTests (65816 and
SPC700) are model-generated, never TEST-ROM-HW. Hardware-run but with
unknown or unclear licences, usable only as external, uncommitted
oracles: PeterLemon (SNES CPUTest/PPU/GSU, "I only test with a real SNES
using a SD2SNES"), blargg's SPC tests (`timer_at_power_reset`,
`spc-timer-clear`; the SNES set is at snescentral, article 1115, with
no licence and no documentation: external runs only, nothing copied), byuu's `test_irqb` (20/20 on a console), paulb_nl's
`irqprobe`, `busprobe`, `mode7_tests`, `contra_test_fb`, `bg_fb`,
`bg_dense` (MiSTer issues #274, #423, #430), Motive's HblankEmuTest
(four consoles plus an SFC), Ramsis' DMA/HDMA collision test, lidnariq's
`smpspeed.sfc` (the usb2snes script is MIT), VitorVilela's
SnesSpeedTest.

Added in the primary-source review (docs/snes-test-evidence.md): paulb_nl's
`snes_frame_timing_test` (MiSTer issue #520, no licence, external only;
DOC, its published picture is the MiSTer core's) and byuu's DMA/HDMA
tests from snescentral article 1123 (no licence, under tests/data (local,
not distributed); TEST-ROM-HW through MiSTer issue #105 for pass/fail). blargg's
`timer_at_power_reset` moved from the A2 to the A4 question (5.4).
