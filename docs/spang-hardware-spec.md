# Super Pang hardware specification

Hardware reference for the third arcade game, **Super Pang** (Mitchell,
1990, MAME ROM set `spang`, "Super Pang (World 900914)"), phases P1 to P3
of the Super Pang plan and the picture of phase P4: what the board does
as far as the CPU side, the EEPROM, the sound chips and the video are
concerned. Status (2026-10-26): phases P1 to P7 done; the sound output
(P5) and the recompiled blocks (P6) are described with their results in
[spang-oracles.md](spang-oracles.md) sections 9 and 10, the machine
behind the front end (P7) in [machine-interface.md](machine-interface.md)
and [frontend.md](frontend.md).

**Target: MAME-equal, not board-equal.** The oracle is MAME 0.285; where
MAME models the board in a simplified way (VBLANK length, line count,
sprite DMA), MAMR follows MAME and the difference is listed in section 9.

## 0. Sources and origin classes

Every statement carries an origin class, as in
[rtype-hardware-spec.md](rtype-hardware-spec.md):

| class | meaning |
|---|---|
| MAME | stated or implemented in a MAME 0.285 source file (tag mame0285); `file:line` |
| DATASHEET | manufacturer data sheet (93C46, MSM6295, YM2413) |
| MEASURED-EMU | observed in a MAME 0.285 run of the oracle kit; never a hardware fact |
| ROM | read from the program itself (decrypted code); content not reproduced |
| IMPLEMENTATION | a choice of MAMR where no source decides |
| UNKNOWN | not known; the measurement that would settle it is named |

MAME files used, all BSD-3-Clause: `src/mame/capcom/mitchell.cpp`
(Nicola Salmoria; one file, there is no `mitchell.h` in 0.285),
`src/mame/capcom/kabuki.cpp` (Nicola Salmoria), `src/devices/machine/eepromser.cpp`
and `eeprom.cpp` (Aaron Giles), `src/devices/sound/okim6295.cpp` (Mirko
Buffoni, Aaron Giles), `okiadpcm.cpp` (Andrew Gardner, Aaron Giles),
`ymopl.cpp` (Aaron Giles), `src/devices/cpu/z80/z80.cpp`, `z80.lst`,
`z80make.py` (Juergen Buchmueller, Andre I. Holub), `src/emu/screen.cpp`,
`src/emu/schedule.cpp` (Aaron Giles). Paths below are relative to
`src/mame/capcom/` unless given in full. No GPL or LGPL file is in the
Super Pang path. The derived MAMR parts are listed in
`third_party/mame/LICENSE`.

## 1. Clocks and frame

| item | value | class | source |
|---|---|---|---|
| crystal | 16 MHz | MAME | mitchell.cpp:1819, 1842, 1845 |
| Z80 (Kabuki) | 8 MHz (16/2), "verified on PCB" | MAME | mitchell.cpp:1819; PCB note mitchell.cpp:65 |
| YM2413 | 4 MHz (16/4), "verified on PCB" | MAME | mitchell.cpp:1845 |
| OKI MSM6295 | 1 MHz (16/16), pin 7 high, "verified on PCB" | MAME | mitchell.cpp:1842 |
| frame rate | 57.42 Hz, "verified on PCB" | MAME | mitchell.cpp:1829 |
| raster | 512 x 256 total, visible x 64-447, y 8-247 (384 x 240) | MAME | mitchell.cpp:1831-1832 |
| VBLANK | 2500 us from line 248, "not accurate" | MAME | mitchell.cpp:1830 |
| frame period | 17,415,534,656,913,966 attoseconds (HZ_TO_ATTOSECONDS(57.42), a double division) | MEASURED-EMU | screen item m_frame_period |
| line period | frame period / 256 = 68,029,432,253,570 as | MAME, MEASURED-EMU | screen.cpp:999 |
| Z80 cycles per frame | 139,324.277 (not an integer) | calculation | - |
| OKI sample rate | 1,000,000 / 132 = 7575 Hz (integer in MAME) | MAME | okim6295.cpp:120-121 |
| YM2413 sample rate | 4,000,000 / 72 | MAME/ymfm | ymfm_opl.h (opll_base) |

The PCB note for Pang gives VSync 57.4450 Hz and HSync 15.16452 kHz
(mitchell.cpp:68-69), i.e. 264 lines per frame; MAME uses 256 (section 9).

**How MAME reaches an event (MAME, schedule.cpp:409-492; z80make.py:85-130).**
The scheduler runs the CPU up to the next timer: it computes
floor((T - local time) / 125e9) cycles; the Z80 core of 0.285 returns
after any M-cycle step once its budget is used up, also inside an
instruction. Interrupts are checked only at instruction boundaries, so an
interrupt raised at T is taken at the first instruction boundary at or
after cycle floor(T / 125e9); MAMR's runner stops at that boundary and
takes it there too (runtime/z80_cpu.h). The state MAME shows at the
moment of the timer, however, can be half an instruction (MEASURED-EMU:
2931 of 3000 attract frames at VBLANK start, `m_ref != 0xffff00`); the
oracle kit therefore samples at the next instruction boundary
([spang-oracle-format.md](spang-oracle-format.md) section 3).

## 2. CPU and interrupts

- One Z80 in IM 1 (`DI; IM 1` at 0x0000; ROM). The only IM instruction
  executed is the one at 0x0001 (MEASURED-EMU). No NMI.
- **Power-on registers** (MAME, src/devices/cpu/z80/z80.cpp:643-721, 761-777): every
  register 0, IX = IY = 0xFFFF, F = 0x40 (Z set), IFF1 = IFF2 = 0, IM 0,
  I = R = 0. MAMR's machine sets these after the generic reset
  (IMPLEMENTATION; the chip's power-on values are not defined).
- **IRQ** (MAME, mitchell.cpp:1772-1782): a scanline timer calls the
  handler at every line; at lines 0 and 240 it asserts IRQ 0 with
  HOLD_LINE (released when the Z80 takes it) and sets
  `m_irq_source = (line == 240)`. Two IRQs per frame (MEASURED-EMU,
  5945 entries in 3000 frames). The handler reads the source in port 0x05
  bit 0 (ROM).
- Line 0 lies 8 lines after VBLANK start (line 248), line 240 248 lines
  after it (MAME, src/emu/screen.cpp:1577 time_until_pos, which counts
  lines from the end of the visible area).
- IM 1 entry: 13 T-states, as in MAMR's runner (MEASURED-EMU: the cycle
  of every interrupt entry, field `irq`, equals MAMR's in 3000 frames).
- **Port timing** (MAME, z80.lst:14-18 and the `rop`/`arg` macros
  47-67): the I/O cycle of IN A,(n) and OUT (n),A begins 7 T-states
  after the instruction (opcode fetch 4, operand 3). The program uses only
  these two forms (MEASURED-EMU; spang_headless counts any other form).
- Watchdog: none in MAME.

## 3. Memory map (MAME, mitchell.cpp:723-738)

| range | program space (read/write) | opcode space (M1) |
|---|---|---|
| 0000-7FFF | fixed ROM, data view; writes ignored | fixed ROM, opcode view |
| 8000-BFFF | bank 0-15 (port 0x02 bits 0-3), data view; writes ignored | the same bank, opcode view |
| C000-C7FF | palette RAM window, 2 KiB, half selected by port 0x00 bit 5 (mitchell.cpp:493-501) | unmapped (reads 0) |
| C800-CFFF | attribute RAM, 2 KiB | unmapped |
| D000-DFFF | tile RAM or sprite RAM, 4 KiB each, port 0x07 != 0 selects sprite RAM (mitchell.cpp:397-415, 751) | unmapped |
| E000-FFFF | work RAM 8 KiB, battery-backed, default 0 (mitchell.cpp:730, 1849-1852) | the same RAM, unencrypted (mitchell.cpp:737) |

- Data and opcode bank switch together: one bank register
  (mitchell.cpp:584-589).
- Code runs from the fixed ROM, banks 0, 1, 2, 3, 5 and RAM FD10-FD1B in
  the attract mode (MEASURED-EMU; MAMR's miss log: 519 fixed-ROM and 847
  banked block starts in the attract mode, 780 and 822 with the coin/start
  route).
- MAME reads 0 from unmapped space (IMPLEMENTATION in MAMR to follow it;
  the program never fetches from C000-DFFF in the measured runs).
- Dispatchers (ROM): RST 18h and the routine at 0x781C take the return
  address as a table of code addresses right after the call and jump
  through entry A / 2 and entry A; other computed jumps load a table
  address into HL with the table right after their JP (HL). The code
  discovery of phase P6 uses the first two as rules
  ([spang-oracles.md](spang-oracles.md) section 10).

## 4. Kabuki

**Cipher** (MAME, kabuki.cpp:5-69, 102-159). The Kabuki is a Z80 with a
decryption stage; its key sits in battery-backed RAM inside the chip. Per
byte: swap of bit pairs, rotate left, swap, XOR with `xor_key`, rotate,
swap, rotate, swap. Which pairs swap depends on a 16-bit `select`, bits
0-7 for the first two swap stages, bits 8-15 for the last two:

- opcode fetch (M1): `select = address + addr_key` (kabuki.cpp:152)
- every other read: `select = (address XOR 0x1FC0) + addr_key + 1`
  (kabuki.cpp:156)

Keys of the World set: `swap_key1 = 0x45670123`, `swap_key2 = 0x45670123`,
`addr_key = 0x5852`, `xor_key = 0x43` (MAME, kabuki.cpp:82, 179). Japan
(`spangj`) and USA (`sbbros`) have their own keys (kabuki.cpp:83-84,
180-181): program ROM and Kabuki belong together.

**Layout** (MAME, kabuki.cpp:163-173; mitchell.cpp:3132-3141). The fixed
ROM is decrypted at its own addresses, every 16 KiB bank as if at 0x8000
(the window it appears in). MAME keeps the data view in the region and
the opcode view in a separate buffer.

**Which bytes are M1** (MAME, z80.lst:47-67 `rop` and `arg`): the opcode,
the prefixes CB, DD, ED, FD and the byte after a prefix. Immediates,
addresses, displacements, and both the displacement and the final opcode
of DD CB d op / FD CB d op are ordinary reads. MAMR's decoder takes M1
bytes from the opcode view and the rest from the data view
(recompiler/z80_decode.h). Whether the real Kabuki treats the last byte of
DD CB d op that way is UNKNOWN (no DDCB/FDCB instruction in the measured
runs, MEASURED-EMU).

**RAM fetches** are not decrypted (MAME, mitchell.cpp:737). How the chip
tells RAM from ROM fetches is UNKNOWN; the copy protection depends on it.

**Preprocessing.** romtool decrypts the program region into both views
(`isa = "z80-banked"` in games/spang/spang.toml; tools/romtool/kabuki.h).
Proof (MEASURED-EMU, `gates.py views`): romtool's views, the independent
reference implementation `tools/oracle/spang/kabuki.py` and MAME's own
opcode and program spaces (fixed part and each of the 16 banks, and the
decrypted region) are byte-identical; opcode view SHA-1 184c89ca...,
data view SHA-1 95b72f59... (local set, files with older names).

**Copy protection** (MAME, mitchell.cpp:12-16; MEASURED-EMU, study run
`fd10`): the program copies the EEPROM to FD00-FD7F; a stub at FD10 calls
a ROM routine that rewrites FD10-FD1B into a 12-byte bank switch routine
(EXX, load a pointer, store, OUT (02),A, EXX, RET), called about five
times per frame. In MAMR it runs on the interpreter as RAM code (miss
log: FD10, FD11, FD14, FD15, FD18, FD1A, FD1B; 14,833 calls in 3000
attract frames, the same count MAME's study run found).

## 5. I/O ports (MAME, mitchell.cpp:740-755; global mask 0xFF)

| port | read | write |
|---|---|---|
| 0x00 | IN0 | gfxctrl: bit 1 coin counter, bit 2 flip, bit 4 OKI bank, bit 5 palette bank; bits 0, 3, 6, 7 unknown (mitchell.cpp:427-461) |
| 0x01 | IN1 | no effect on Super Pang (`input_w`, input type 3) |
| 0x02 | IN2 | bank, bits 0-3 |
| 0x03 | - | YM2413 data |
| 0x04 | - | YM2413 address |
| 0x05 | SYS0 (below) | OKI command |
| 0x06 | - | no device (`noprw`, "watchdog? IRQ ack? video buffering?") |
| 0x07 | - | video bank: != 0 maps sprite RAM at D000 |
| 0x08 / 0x10 / 0x18 | - | EEPROM CS / CLK / DI (bit 0) (mitchell.cpp:562-575) |

Other ports have no device; MAME reads 0 there (MAMR follows, and counts
such accesses: none in the measured runs).

**Port 0x05** (MAME, mitchell.cpp:550-560, 1225-1233): bit 0 the IRQ
source, bit 1 service switch (active low), bit 3 VBLANK (active low,
`screen_device::vblank`), bit 7 EEPROM DO (active high), bits 2, 4, 5, 6
read 1.

**Inputs** (MAME, mitchell.cpp:1235-1262, all active low): IN0 bit 1
start 2, bit 3 start 1, bit 6 service 1, bit 7 coin 1; IN1/IN2 bit 2
button 2 (service mode only), bit 3 button 1, bits 4-7 right, left, down,
up. No DIP switches; the settings live in the EEPROM.

**Uninitialised registers** (MAME, mitchell.cpp:214-216, 1737-1744):
`m_video_bank`, `m_paletteram_bank` and `m_flipscreen` are set neither in
machine_start nor in machine_reset, and are not in the save state. MAME
runs therefore start with whatever the allocation left there; the program
fills D000-DFFF before its first write to port 0x07, and the fill lands in
tile or sprite RAM depending on it (MEASURED-EMU: runs differed in frames
4-7). MAMR powers on with 0 in all three, and the oracle kit writes 0 to
ports 0x00 and 0x07 before the first instruction (IMPLEMENTATION; the
board's power-on state is UNKNOWN).

## 6. EEPROM 93C46

- 64 words of 16 bits, 6 address bits (MAME, mitchell.cpp:1825;
  eepromser.cpp:1100). Commands after the start bit: 10 READ, 01 WRITE,
  11 ERASE, 00 11 EWEN, 00 00 EWDS, 00 10 ERAL, 00 01 WRAL (DATASHEET;
  MAME, eepromser.cpp:20-27). Write-protected after power-up (DATASHEET;
  MAME, eepromser.cpp:208).
- DO shows the ready status while the chip waits for a start bit after a
  programming command, the data during READ after a dummy 0, else 1 (MAME,
  eepromser.cpp:283-311, 658). A start bit counts only when the chip is
  ready and the clock edge comes strictly after the CS rising edge (MAME,
  eepromser.cpp:385-393).
- Programming times in MAME: WRITE 1750 us, ERASE 1000 us, WRAL/ERAL
  8000 us (MAME, eeprom.cpp:42-45), i.e. 14000, 8000 and 64000 Z80
  cycles. The data sheet gives a maximum, not these values; the program
  polls DO, so MAME's values decide game time (section 9).
- Default contents: region `eeprom`, big-endian words (MAME,
  mitchell.cpp:2660-2661; eeprom.cpp:210-245).
- Use (MEASURED-EMU): 64 READs at frames 26/27, EWEN and ERASE+WRITE of
  words 0-7 at frames 68-70; the contents after 3000 frames are unchanged.
- MAMR: runtime/eeprom93c46.h, with MAME's state machine where the data
  sheet leaves room (state order, no sequential read).

## 7. Sound

- **YM2413** only written (ports 0x04 address, 0x03 data); no status, no
  IRQ (MAME, mitchell.cpp:747-748; ymfm_opl.h opll_base returns 0). Mono,
  gain 1.0, all outputs to the speaker (mitchell.cpp:1845-1846): ymfm's
  OPLL has two, the melody channels and the rhythm section (ymfm_opl.cpp
  opll_base::generate), and the program uses rhythm mode during play
  (MEASURED-EMU). MAMR: runtime/ym2413.h over ymfm, the two outputs summed.
- **Instrument ROM:** MAME's ym2413 device requires
  `ym2413_instruments.bin` (144 bytes, CRC 6f582d01), "not the exact
  format" (MAME, ymopl.cpp:218-224). It is chip data, not vendored; see
  [spang-oracles.md](spang-oracles.md) section 3 for the placeholder.
- **OKI MSM6295** at port 0x05 (write only; the status is not readable on
  this board), 1 MHz, pin 7 high (divisor 132), gain 0.30 (MAME,
  mitchell.cpp:1842-1843; okim6295.cpp:120). The ROM is the 512 KiB region
  `oki`, 128 KiB populated; gfxctrl bit 4 selects the 256 KiB half (MAME,
  mitchell.cpp:452-453); the attract mode stays in bank 0 (MEASURED-EMU).
- OKI protocol (DATASHEET; MAME, okim6295.cpp:232-306): a byte with bit 7
  set selects phrase 1-127, the next byte gives the voices (bits 4-7) and
  the attenuation (bits 0-3); a byte with bit 7 clear stops the voices in
  bits 3-6. Phrase table: 8 bytes per phrase, 18-bit start and end. A
  start on a voice that still plays is ignored, and a phrase whose end is
  not above its start does not play (MAME, okim6295.cpp:251, 266). A
  phrase plays 2 * (end - start + 1) nibbles, high nibble first (MAME,
  okim6295.cpp:272, 348).
- ADPCM (DATASHEET; MAME, okiadpcm.cpp): 49 step sizes 16 ... 1552
  (= floor(16 * 1.1^n), MAME computes them that way), index change
  -1, -1, -1, -1, 2, 4, 6, 8, signal clamped to -2048..2047. MAMR:
  runtime/okim6295.h, clean-room after the data sheet with the MAME
  details named there.
- No sound CPU, no latch: the music runs in the line-0 IRQ of the main
  Z80 (MEASURED-EMU). 511 YM writes and 21 OKI commands in 3000 attract
  frames.
- **Mix** (MAME, mitchell.cpp:1842-1846; ymfm_mame.h put_int range 32768;
  okim6295.cpp:352 add_int range 2048): one speaker, YM2413 1.0, OKI 0.30.
  MAMR's mix and its output rate: spang-oracles.md section 9.

## 8. Video (MAME, mitchell.cpp:350-358, 362-372, 505-541, 1631-1697, 1795-1806)

- **Raster:** 512 x 256, visible 64-447 x 8-247 (384 x 240), section 1.
  MAME's screen bitmap holds palette entries; the palette (2048 entries,
  `xRGB_444`, two bytes little-endian: bits 8-11 red, 4-7 green, 0-3 blue;
  each 4-bit value times 0x11 gives 8 bits) is resolved when the picture
  is shown.
- **Frame:** the bitmap is cleared to entry 0, the tilemap is drawn with
  pen 15 transparent, then the sprites. No priority logic beyond that
  drawing order; MAME draws the whole frame once at VBLANK start from the
  live memories (no partial updates in the driver).
- **Tilemap:** 64 x 32 tiles of 8 x 8, rows first. Tile i: code = tile RAM
  byte 2i | byte 2i+1 << 8 (taken modulo the 32768 tiles), attribute byte
  i: bits 0-6 colour (entries colour * 16 + pen, all 2048 entries), bit 7
  flip X. No scroll.
- **Tiles in ROM** (`charlayout`): 16 bytes per tile, two bytes per row,
  each byte four pixels of two planes (one per nibble). In MAME's terms:
  planes { 0x80000*8+4, 0x80000*8+0, 4, 0 } (the first the most
  significant pen bit, bits counted from the MSB of each byte), x offsets
  0-3 and 8-11, 16 bits per row; the second half of the `chars` region
  (0x80000 on) holds the two upper planes.
- **Sprites:** 128 entries of 32 bytes in sprite RAM, drawn from 0xFC0
  down to 0 (the later drawn, lower address, on top); the entry at 0xFE0
  is skipped (MAME: "the last entry is not a sprite"). Byte 0 code bits
  0-7, byte 1 bits 0-3 colour (entries 0-255), bit 4 x bit 8, bits 5-7
  code bits 8-10; byte 2 y, byte 3 x. Screen position x (0-511), y =
  ((byte 2 + 8) & 0xFF) - 8; 16 x 16 pixels, pen 15 transparent, clipped
  to the visible area. ROM layout `spritelayout`: 64 bytes per sprite,
  planes { 0x20000*8+4, 0x20000*8+0, 4, 0 }, columns 8-15 32 bytes
  further on.
- **Flip** (gfxctrl bit 2): MAME flips every tilemap in X and Y
  (src/emu/tilemap.cpp set_flip_all); with the visible area centred in the
  512 x 256 tilemap the scroll offsets come out 0, so screen pixel (x, y)
  shows tilemap pixel (511 - x, 255 - y). Sprites: x = 496 - x, y = 240 - y,
  drawn flipped in both directions. The program sets the bit from EEPROM
  byte 2 (the high byte of word 1; 1 = flipped; MEASURED-EMU).
- **Palette bank** (gfxctrl bit 5) only selects which half the CPU sees at
  C000-C7FF; the video always uses all 2048 entries.
- MAMR: games/spang/spang_video.h, after this part of mitchell.cpp and
  tilemap.cpp's flip handling (third_party/mame/LICENSE). The oracle's
  picture differs from what is drawn at a VBLANK in two ways that belong
  to MAME's sampling (spang-oracles.md section 4, F3 and F4).

## 9. MAME model against the board

| # | topic | MAME | why it matters | class |
|---|---|---|---|---|
| U1 | VBLANK length | 2500 us from line 248, i.e. into line 28 of the next frame, "not accurate" | the program reads port 0x05 bit 3 there; MAMR copies the 2500 us | MAME mitchell.cpp:1830 |
| U2 | line count | 256 (PCB note: 264) | IRQ times and line length are MAME's construction | MAME mitchell.cpp:68-69, 1831 |
| U3 | sprite DMA | port 0x06 ignored, sprites from live RAM | board probably buffers (one frame later) | MAME mitchell.cpp:750 |
| U4 | gfxctrl bits 0, 3, 6, 7 | no effect | layer enables would flicker Super Pang | MAME mitchell.cpp:435-459 |
| U5 | uninitialised registers | video bank, palette bank, flip | runs differ in frames 4-7 without the kit's writes (section 5) | MAME, MEASURED-EMU |
| U6 | Kabuki on RAM fetch | unencrypted | the protection needs it; mechanism UNKNOWN | MAME mitchell.cpp:737 |
| U7 | DD CB d op | last byte as data | UNKNOWN on the chip; not executed | MAME z80.lst:4070-4074 |
| U8 | EEPROM times | 1750/1000/8000 us | game time while saving depends on them | MAME eeprom.cpp:42-45 |
| U9 | frame rate | 57.42 Hz (PCB note 57.4450) | audio drift only | MAME mitchell.cpp:68, 1829 |
| U10 | OKI start on a playing voice | ignored | | MAME okim6295.cpp:251 |
| U11 | Z80 stops inside instructions | its state at a timer can be half an instruction | the kit samples at the next boundary | MAME z80make.py:85-130, MEASURED-EMU |
| U12 | unmapped I/O and opcode space | read 0 | never touched in the measured runs | MAME |
