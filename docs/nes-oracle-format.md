# NES hash lines, format version 2

One text file per run. MAMR's runtime (from phase N2) and every oracle
front end (`mesen/nesfh.lua`, `mame/nesfh_mame.lua`) write the same lines;
`hashline.py` is the reference implementation, `compare.py` compares two
files, `gates.py` runs the gates of nes-architecture.md section 7. File
names without a directory refer to `tools/oracle/nes/`. The format follows
docs/snes-oracle-format.md (version 4) in structure; this note gives only
what differs.

Versions: 1 (phase N2) had eleven state fields; 2 (phase N4, 2026-10-26)
appends `apu` (the APU's channel state) and `snd` (the frame's native
audio samples). The tools read version 2 only; MAMR's MesenCE
reference file (tests/nes-oracle/reference) was written again in version 2,
its eleven version 1 fields unchanged.

Plain ASCII, one record per line, fields separated by one space, `key=value`
pairs in the order given here. Lines starting with `#` are comments. All
hex is lower case.

## 1. Hash function

FNV-1a 64 over bytes, byte by byte, as in the SNES format (section 1
there; test vectors `""` gives `cbf29ce484222325`, `"a"` gives
`af63dc4c8601ec8c`, `"foobar"` gives `85944171f73967e8`).

## 2. Header line

```text
H nesfh 2 oracle=<name> rom=<sha1 or -> fill=<00|ff|00ff> region=<ntsc|pal> [key=value ...]
```

`fill` names the power-on RAM state of the run (section 6), `region` the
console timing: `ntsc` (RP2C02, 262 lines) or `pal` (RP2C07, 312 lines,
3.2 dots per CPU cycle; phase P). The F lines are the same in both; a
PAL frame has 312 x 341 = 106,392 dots and no short frame, and `dot`
counts dots of 5 master clocks (MesenCE's `ppu.masterClock / 5`). Extra keys are informative: `core=` names the emulator
build, `align=` the CPU/PPU power-on alignment the writer uses (MesenCE:
its PPU offset in master clocks, 1; `-` when the writer cannot say),
`input=` the SHA-1 of the input script.

## 3. F line: one per frame

```text
F <n> inp=<strobes> cyc=<cpu cycles> dot=<dots|-> pc=<pc> cpu=<raw> ram=<h>
  vram=<h> oam=<h> pal=<h> prgram=<h> ppu=<raw|-> prgmap=<h|-> chrmap=<h|->
  mirq=<raw|-> img=<h|-> apu=<h|-> snd=<h|-> all=<h>
```

(one line in the file). `<n>` counts the F lines from 1.

**Sampling window.** The window of frame n opens at dot 0 of scanline 240
(the post-render line) for the n-th time since power-on. An NTSC frame
has 262 scanlines of 341 dots (89342 dots); when rendering is enabled the
pre-render line of every second frame is one dot short (89341). The PPU
runs three dots per CPU cycle. Where the PPU starts at power-on is the
writer's convention and recorded with it: MesenCE starts at scanline 0,
dot 0, so its first window opens 81840 dots after power-on
(`hashline.window_dot`).

**Sampling point.** The first CPU instruction boundary at or after the
window opens: the moment before the opcode fetch of the next instruction.
An interrupt entry (NMI) that starts at the boundary is completed first,
so the point is then before the first opcode of the handler; a DMA in
progress delays it until the DMA ends. In MesenCE this is the first exec
callback after the `endFrame` event (which MesenCE raises when its PPU
reaches scanline 240, dot 0). MAME's writer samples in the frame-done
callback instead, which is the end of scanline 239 and may fall inside an
instruction (docs/nes-oracles.md section 3); its `cpu` and `pc` are
therefore not comparable at the instruction level. A jammed CPU (KIL)
produces no further F lines.

**Keys besides the state:**

- `inp`: controller strobes before the sampling window opened: the
  number of writes to $4016 with bit 0 = 1 since power-on. Inputs are
  bound to the n-th strobe (section 7). Compared by default.
- `cyc`: CPU cycles from power-on to the sampling point (the oracle's
  own count: MesenCE's `cpu.cycleCount` in the callback of the opcode
  fetch, which counts its 8 power-on cycles before the first fetch; MAME's
  `m_totalcycles`). Compared only on request (`compare.py --timing`).
- `dot`: PPU dots from power-on to the sampling point, `-` when the
  writer cannot say. Compared only with `--timing`.
- `pc`: PC of the next instruction, informative.

**State fields.** Each field is a fixed byte sequence (its canonical
bytes). `cpu`, `ppu` and `mirq` are printed as the raw hex of those bytes,
all other fields as the 16-hex-digit FNV-1a 64 of them. A field an oracle
cannot provide is `-`; `compare.py` skips it.

| field | bytes | content, in this order |
|---|---|---|
| cpu | 5 | A, X, Y, S, P. P with bit 5 = 1 and bit 4 = 0 (the two bits do not exist in the register). No PC. |
| ram | 2048 | the internal RAM $0000-$07FF, byte by byte. |
| vram | 4096 | the nametable window $2000-$2FFF of the PPU address space as a PPU read would see it, mirroring applied (so a two-screen board shows each 1 KiB of CIRAM twice). The 2 KiB of CIRAM are recovered from it by the mirroring; a four-screen board shows its 4 KiB. |
| oam | 256 | the primary OAM, byte by byte, the attribute byte of every sprite (offset 4k + 2) masked with $E3: its bits 2-4 do not exist in the PPU and read back as 0 (NESdev wiki "PPU OAM"); MesenCE stores the byte masked, MAME unmasked. |
| pal | 32 | palette RAM, each entry masked to 6 bits; entries $10, $14, $18 and $1C are written as copies of entries $00, $04, $08 and $0C (the hardware mirrors them; emulators store them in both ways). |
| prgram | board | the cartridge's PRG RAM at $6000-$7FFF, byte by byte from offset 0, as many bytes as the board has (8 KiB when an iNES 1.0 header gives no size, the convention both oracles follow; battery-backed or not). A board without PRG RAM writes the empty hash cbf29ce484222325. |
| ppu | 11 | the canonical PPU register set, section 4. |
| prgmap | 16 | four little-endian 32-bit byte offsets into the PRG ROM: the 8 KiB windows at $8000, $A000, $C000, $E000. |
| chrmap | 32 | eight little-endian 32-bit byte offsets into the CHR memory (ROM or RAM, whichever the board has): the 1 KiB windows at $0000 to $1C00. |
| mirq | 4 | the mapper's IRQ counter state: counter, latch, reload flag (1 = reload pending), enable (1 = enabled). All zero for a mapper without an IRQ counter (NROM). The asserted IRQ line is not part of the format: MesenCE does not expose the CPU's IRQ state to Lua. |
| img | 122880 | the picture, section 5. |
| apu | 44 | the APU's channel state, section 4.1. |
| snd | 4 per sample | the native audio samples completed since the previous sampling point (power-on for frame 1): MAMR's sums of the mixer level over 8 CPU cycles (docs/nes-audio-spec.md section 9), sample j covering CPU cycles 8j to 8j + 7 from power-on, each as a little-endian 32-bit value; a sample belongs to the frame at whose sampling point its last cycle is complete. Only MAMR writes it; MesenCE and MAME write `-`. |

**Chain.** `all` chains the frames exactly as in the SNES format: FNV-1a
64 over LE64 of the previous `all` followed by LE64 of each state field's
hash in the table order (a field written as `-` adds eight zero bytes).
Timing keys are not part of the chain.

## 4. The canonical PPU register set (field `ppu`)

| offset | bytes | content |
|---|---|---|
| 0x00 | 1 | PPUCTRL: bits 2-7 of the last byte written to $2000 (bits 0-1, the nametable select, live in `t` and are written as 0) |
| 0x01 | 1 | PPUMASK: the last byte written to $2001 |
| 0x02 | 1 | PPUSTATUS flags: bit 7 vertical blank, bit 6 sprite 0 hit, bit 5 sprite overflow; bits 0-4 = 0 |
| 0x03 | 1 | OAMADDR: the internal OAM address |
| 0x04 | 2 | v, the current VRAM address (15 bits), LE |
| 0x06 | 2 | t, the temporary VRAM address (15 bits), LE |
| 0x08 | 1 | x, the fine X scroll (3 bits) |
| 0x09 | 1 | w, the first/second write toggle (0 = next write is the first) |
| 0x0A | 1 | the $2007 read buffer |

A writer that holds its PPU state in another shape derives these bytes;
one that cannot writes `-`. MesenCE exposes every item except the raw
PPUCTRL byte (it keeps decoded flags without bit 6), so its writer records
the last bytes written to $2000 and $2001 through a write callback. MAME
keeps the rendering address (`m_refresh_data`) and the address of $2007
accesses (`m_videomem_addr`) as two registers, so there is no single `v`,
and its `ppu` is `-` (docs/nes-oracles.md).

### 4.1 The APU channel state (field `apu`)

The state of docs/nes-audio-spec.md that both MAMR and MesenCE can name
(44 bytes). Flags bytes: bit 0 constant volume, bit 1 loop (the
register's halt bit), bit 2 envelope start.

| offset | bytes | content |
|---|---|---|
| 0x00 | 10 | pulse 1: duty (0-3), V, flags, envelope divider, decay level, length counter, the $4001 bits (enable 7, period 4-6, negate 3, shift 0-2), sweep reload flag (0/1), period (11 bits, LE) |
| 0x0A | 10 | pulse 2, the same |
| 0x14 | 6 | triangle: linear counter, its reload value, flags (bit 0 control, bit 1 reload flag), length counter, period (LE) |
| 0x1A | 6 | noise: V, flags, envelope divider, decay level, length counter, mode (bit 7) and period index (bits 0-3) |
| 0x20 | 10 | DMC: the $4010 bits (IRQ enable 7, loop 6, rate 0-3), output level, $4012, $4013, current address with bit 15 set (LE; the counter's A15 is always 1), bytes remaining (LE), sample buffer full (0/1), the buffer byte (0 when empty) |
| 0x2A | 1 | the length counter enables ($4015 bits 0-3) |
| 0x2B | 1 | frame counter: bit 7 five-step mode, bit 6 IRQ inhibit |

Not in the field: the timers and sequencer positions, the noise shift
register and the DMC timer, shift register and bit count, which change
every few cycles and whose representation differs between the
emulators, and the sweep dividers (MesenCE's counter runs free before
the first $4001 write; docs/nes-oracles.md section 6). MesenCE's writer
maps its keys: the noise and DMC periods (CPU cycles minus 1) back to
their indices, the sample address and length back to the register
values, the sweep period from P + 1 to P.

## 5. The picture (field `img`)

The 256 by 240 output of the PPU, rows 0 to 239 (every scanline, the NTSC
overscan included), each pixel as a 16-bit little-endian value:

```text
pixel = colour index (bits 0-5) | emphasis bits (bits 6-8: R, G, B as in PPUMASK bits 5-7)
```

The emphasis bits are in colour order: bit 6 red, 7 green, 8 blue. On
the NTSC 2C02 that is PPUMASK bits 5-7 as written; on the PAL 2C07,
where PPUMASK bit 5 emphasises green and bit 6 red (docs/nes-ppu-spec.md
section 18.4), bit 6 of the pixel is PPUMASK bit 6 and bit 7 is PPUMASK
bit 5 (MesenCE stores them so in PAL mode; MAME's writer swaps the
device's pen bits for the driver nespal). The 2C07's black border is not
part of the picture: every pixel keeps the index the PPU selected.

canonicalised, because the emulators expose RGB and their palettes do not
distinguish every index:

1. colour $30 is written as $20 (in every emphasis set);
2. the ten blacks $0D, $0E, $0F, $1D, $1E, $1F, $2E, $2F, $3E and $3F are
   written as $0F with the emphasis bits cleared;
3. with all three emphasis bits set, $20 (and $30 by rule 1) is written
   as $10 with the emphasis bits cleared.

MesenCE renders through an index-encoding user palette installed by
`run_mesen.sh`, so its screen buffer yields the index and the emphasis
directly; MAME's writer inverts the PPU device's 512-pen palette (the
three rules are exactly the pens that palette does not keep apart).
MAMR writes its PPU output through the same rules. `imgsz` is not written:
the picture is always 256x240.

## 6. Power-on state and masks

- `fill=00`: the internal RAM, the CIRAM, OAM, palette RAM and the PRG
  RAM are 0 at power-on; every register value an emulator would otherwise
  randomise is 0. MesenCE: `--nes.ramPowerOnState=AllZeros`; MAMR's
  default for oracle runs.
- `fill=ff`: the same memories set to $FF (MesenCE `AllOnes`).
- `fill=00ff`: MAME's fixed fill of the internal RAM, $00 at even and
  $FF at odd addresses (not selectable; nes.cpp machine start).

The hardware powers on with unspecified RAM, and the CPU/PPU alignment is
one of four (nes-architecture.md section 4). Masks for bytes the program
never wrote work as in the SNES format: dump a frame under fill 00 and
fill ff and keep the equal bytes (`compare.py mask`).

**Dumps.** With their dump option the oracles write, for selected frames,
the canonical bytes of every field to `DIR/f<frame:06d>.<field>.bin`;
`hashline.py fline DIR FRAME` rebuilds the F line from a dump.

## 7. Inputs: the controller strobe

Inputs are bound to the n-th controller strobe (a write of 1 to $4016),
not to the emulator's frame. The input script is the SNES one
(docs/snes-oracle-input-script.md: `HOLD`, `RELEASE`, `WAIT n`,
`WAIT_RAM8 addr value`, comments with `#`) with the NES button names A, B,
SELECT, START, UP, DOWN, LEFT, RIGHT; it advances once per strobe, and
`WAIT_RAM8` reads the internal RAM ($0000-$07FF). Both Lua writers
implement it; a frame without a strobe does not step the script.

## 8. T line: test tally (AccuracyCoin)

```text
T <n> tally=<passed>/<run> results=<hex>
```

Written once when the writer is started with `FH_ACC=1`: after the F
line of the 60th frame after AccuracyCoin's "run every test" pass ended
(zero page $35 is 1 while it runs; after the clear the ROM counts the
results and draws its table, which takes far less than 60 frames).
`tally` is the ROM's own count (zero page $38 passed of $37 run),
`results` the raw result bytes $0400-$04FF (0 not run, $FF skipped, bit 0
set passed, else failed; the code beside a result is the byte shifted
right by two). `accuracycoin.py` decodes the bytes into the table of
docs/nes-test-evidence.md with the test names from the ROM's source.

With `FH_ACC_SKIP=ADDR,...` the writer sets those result bytes to $FF
before the pass starts, which the ROM treats as tests marked skipped (as
the B button does). With `FH_ACC_HANG=K` it stops with the comment line

```text
# hang page=<P> index=<I> frame=<n> reason=<stuck|restart>
```

when the running test (menu page $14, entry $16) has not changed for K
frames (stuck), or, in the run of one page (`FH_ACC_FLAG=34`, zero page
$34 instead of $35), when the pass goes back to an earlier entry
(restart; the entry named is the one that ran last); `gates.py accuracycoin` then reruns with that test skipped and
reports it.

## 9. R and N lines: verdicts of other test ROMs

```text
R <n> status=<hh> text=<hex|->
N <n> nt=<hex>
```

With `FH_BLARGG=1` the writer watches blargg's result protocol: when
$6001-$6003 hold $DE $B0 $61, $6000 is $80 while the test runs, $81 when
the test asks for a reset (the writer presses reset 6 frames later), and
otherwise the result code (0 = passed). The R line is written after the F
line of the frame in which a result first appears: `status` the code,
`text` the zero-terminated text from $6004 as hex. With `FH_SCREEN=1`
the writer adds, after the last F line, an N line with the 4096 bytes of
the nametable window $2000-$2FFF as a PPU read sees it (attribute tables
included); the older tests print their verdict there with tile numbers
equal to ASCII codes, some of them scrolling through all four
nametables. `testroms.py` decodes both (docs/nes-test-evidence.md
section 3). R and N lines are not part of the chain.

## 10. What a writer must do, in short

1. Power on with `fill=00`, NTSC, the alignment it records in the header;
   audio off, no frame skipping.
2. Count controller strobes; step the input script at each.
3. Open the sampling window at scanline 240, dot 0; at the next
   instruction boundary build the thirteen canonical byte sequences (or
   `-` for those it cannot give), print the F line (inp = strobes before
   the window) and update the chain.
4. Optionally write dumps and the T line.
