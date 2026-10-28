# SNES hash lines, format version 4

One text file per run. MAMR's runtime and every oracle front end
(`aresref`, `mesen/snesfh.lua`, `mame/snesfh_mame.lua`) write the same
lines; `hashline.py` is the reference implementation, `compare.py`
compares two files, `gates.py` runs the gates of
snes-architecture.md section 7. File names without a directory refer to `tools/oracle/snes/`.

Changes from version 3: the internal OAM address is no longer part of
`ppu` (now 77 bytes, section 4). It runs during sprite evaluation and is
reloaded from OAMADD at the start of the vertical blank, right at the
sampling window; emulators differ there in when they do it (on the PAL
target game 150 frames differed between MAMR and aresref for this alone).
OAMADD as written is in the write shadow.

Changes from version 2 to 3: a twelfth state field `sram` (cartridge save
RAM, section 3) with the power-on rule of section 6; the SMP is sampled at
its first instruction boundary at or after the sampling time in every
oracle.

Changes from version 1 to 2: the sampling point is the first CPU
instruction boundary after the start of scanline 225 instead of that
clock itself (section 3); the header must give the region and the APU
clock (section 2); `anc` of an F line counts the reads begun before the
sampling window opened; the VRAM address in `ppu` is 15 bits; PAL frame
timing; optional L lines (section 10). `compare.py` refuses files of
another version.

Plain ASCII, one record per line, fields separated by one space, `key=value`
pairs in the order given here. Lines starting with `#` are comments. All
hex is lower case.

## 1. Hash function

FNV-1a 64 over bytes, byte by byte:

```text
h = 0xcbf29ce484222325
for each byte b: h = (h XOR b) * 0x100000001b3   (mod 2^64)
```

Test vectors: `""` gives `cbf29ce484222325`, `"a"` gives
`af63dc4c8601ec8c`, `"foobar"` gives `85944171f73967e8`.

Why FNV-1a 64 and not XXH3: the lines are written by C++ (MAMR, aresref)
and by Lua 5.4 scripts inside MesenCE and MAME, which have no native hash
function and no block read. FNV-1a is three integer operations per byte,
uses only wrapping 64-bit multiplication (native in C++, Python with a
mask, and Lua 5.4 integers), and has published test vectors. XXH3 would
need a Lua port of a large, endian-sensitive algorithm and gains nothing
here: the input is not adversarial, and the speed is dominated by reading
the emulator memory (MesenCE: about 13 ms per 256 KiB from Lua). Since
every step `h -> (h XOR b) * p` is a bijection on 64-bit values, two
inputs of equal length that differ in exactly one byte always hash
differently, which is what the fault-injection gate relies on.

## 2. Header line

```text
H snesfh 4 oracle=<name> rom=<sha1 or -> fill=<00|ff|55|native> region=<ntsc|pal> clk=<meas|nom> [key=value ...]
```

`fill` names the power-on state of the run (section 6). `region` and
`clk` are mandatory:

- `region=ntsc|pal`: the console timing (section 3). aresref takes it
  from the cartridge (`--region` overrides), MesenCE derives it from its
  master clock rate.
- `clk=meas|nom`: the APU oscillator. `meas` is 32040 Hz * 768 =
  24.607 MHz (the measured mean rate ares, `apuFrequency`, and MesenCE,
  SPC rate 32000 + 40, use), `nom` is the nominal 24.576 MHz (MAME). The
  SMP-side fields, the P line times and through the port handshake also
  the CPU side depend on it. For comparisons against aresref MAMR runs in
  its 32040 Hz mode and writes `clk=meas`. `compare.py` refuses files with
  different `region` or `clk` (`--allow-clk` overrides the latter).

Extra keys are informative (`core=` names the emulator build; MAMR adds
`ipl=`, `blocks=` and `stage=e` for its exact stage, `snes_headless --exact`).

## 3. F line: one per frame

```text
F <n> anc=<reads> mclk=<clocks> pc=<pbpc> cpu=<raw> smp=<raw> apuio=<raw>
  wram=<h> vram=<h> oam=<h> cgram=<h> ppu=<h> aram=<h> dsp=<h> img=<h>
  sram=<h> imgsz=<w>x<h> all=<h>
```

(one line in the file). `<n>` counts the F lines from 1.

**Sampling window.** The window of a frame opens at the start of scanline
225 (scanline 240 when overscan was latched at V=0 of that frame), H=0.
Counted from power-on (V=0, H=0, field 0), the window of frame n opens at

```text
W(n) = 225 * 1364 + L(0) + L(1) + ... + L(n-2)     (240 * 1364 with overscan)
```

with the field lengths L(k) (k = 0, 1, 2, ...; parity k mod 2):

| timing | field 0 (even) | field 1 (odd) |
|---|---|---|
| NTSC, no interlace | 262 * 1364 = 357368 | 357364 (line 240 has 1360 clocks) |
| NTSC, interlace | 263 * 1364 = 358732 | 262 * 1364 = 357368 |
| PAL, no interlace | 312 * 1364 = 425568 | 425568 |
| PAL, interlace | 313 * 1364 = 426932 | 312 * 1364 + 4 = 425572 (line 311 has 1368 clocks) |

So without interlace W(n) = 306900 + 357368 (n - 1) - 4 floor((n - 1) / 2)
for NTSC and 306900 + 425568 (n - 1) for PAL. The master clock is
21.477272 MHz (NTSC) or 21.281370 MHz (PAL). (`hashline.window_mclk`;
the interlace and overscan rows assume the setting held since power-on.)

**Sampling point.** The first CPU instruction boundary at or after W(n):
the moment before the opcode fetch of the next instruction. An interrupt
entry (NMI, IRQ) that starts at the boundary is completed first, so the
point is then before the first opcode of the handler; a DMA in progress
delays it until the DMA ends; while the CPU waits in WAI the point is the
first opcode after the wake-up. The CPU registers and every memory are
therefore at an instruction boundary, which MAMR's stage S can reach. In
aresref this is the instruction hook after the window (patch 0004), in
MesenCE the first exec callback after the `endFrame` event (which MesenCE
raises inside the instruction that crosses W(n)). The PPU state, the
picture and the shadow are taken at the same time. The SMP is brought to
its first instruction boundary at or after the sampling time (it may run
ahead of the CPU for the rest of one SMP instruction), the S-DSP to the
SMP's time. That run is made on a copy, as if the CPU stood still at the
sampling point: nothing the SMP does in it (a port write, a port read)
reaches the emulated time line, which goes on from the sampling point
with the SMP where it was. MAMR runs a copy of its SMP
(`smp_at_sample`); aresref saves the SMP and the DSP, runs them (patch
0007) and restores them after the line (patch 0009; without it the CPU
saw the SMP's future port writes, docs/snes-oracles.md section 2).
MesenCE catches its SMP up to the first instruction boundary at or after
the moment it finishes the frame, which lies a few clocks before the
sampling point. A CPU that never fetches another opcode (STP) produces
no further F lines.

**Keys besides the state:**

- `anc`: auto-joypad reads that began before the sampling window opened
  (section 7). The read of the frame itself starts after W(n) and is
  never counted, whether it begins before or after the sampling point,
  so frame n carries anc = n - 1 while auto-read is enabled. Compared by
  default (`compare.py --align anc` pairs F lines by it instead of by
  frame).
- `mclk`: master clocks from power-on to the sampling point, DRAM refresh
  and DMA included; never below W(n). Compared only on request
  (`compare.py --timing`).
- `pc`: PB:PC of the next instruction (at the sampling point),
  informative.

**State fields.** Each field is a fixed byte sequence (its canonical
bytes). `cpu`, `smp` and `apuio` are printed as the raw hex of those
bytes, all other fields as the 16-hex-digit FNV-1a 64 of them. A field an
oracle cannot provide is `-`; `compare.py` skips it.

| field | bytes | content, in this order |
|---|---|---|
| cpu | 14 | A, X, Y, S, D as 16-bit little endian, then DB, PB, P, E (0 or 1). No PC. A and the index registers with their full 16 bits as held (in 8-bit modes the hidden high byte of A stays; X/Y high bytes are 0 when the X flag is set). |
| smp | 13 | SPC700 A, X, Y, SP, PSW (no PC); then CONTROL as `ipl_enable << 7 | timer2 << 2 | timer1 << 1 | timer0`; DSPADDR ($F2); timer targets T0, T1, T2 ($FA-$FC); the 4-bit stage-3 counters T0, T1, T2 ($FD-$FF), sampled without the clearing read. |
| apuio | 8 | the four bytes the SMP would read at $F4-$F7 (the CPU's writes to $2140-$2143, after any clear through CONTROL bits 4 and 5), then the four bytes the CPU would read at $2140-$2143 (the SMP's writes to $F4-$F7). |
| wram | 131072 | $7E0000-$7FFFFF, byte by byte. |
| vram | 65536 | word address 0 to $7FFF, each word low byte first. |
| oam | 544 | the 512-byte low table, then the 32-byte high table, in the layout $2138 reads them. Decoding emulators re-encode. |
| cgram | 512 | 256 words, low byte first, bit 15 cleared. |
| ppu | 77 | the canonical PPU register set, section 4. |
| aram | 65536 | the 64 KiB audio RAM, byte by byte; the RAM under the I/O page and under the IPL, not the IPL ROM. |
| dsp | 128 | the S-DSP register file $00-$7F as $F3 reads it (ENVX, OUTX, ENDX as last updated by the DSP). |
| img | w * h * 2 | the picture, section 5. |
| sram | cartridge | the cartridge's save RAM (battery RAM) as the cartridge maps it, byte by byte from offset 0; empty (hash cbf29ce484222325) for a cartridge without one. RAM of enhancement chips is not included. |

**Chain.** `all` chains the frames:

```text
all_0 = 0xcbf29ce484222325
all_n = FNV-1a 64 over LE64(all_{n-1}) followed by LE64(hash of each
        state field in the table order); a field written as "-" adds
        eight zero bytes
```

where the hash of a raw field is the FNV-1a 64 of its bytes, not the
printed hex. Timing keys are not part of the chain.

## 4. The canonical PPU register set (field `ppu`)

The PPU's write-only registers are not readable, and the emulators keep
them decoded in incompatible ways. The canonical set is therefore defined
on the write stream, which every implementation sees, plus the internal
latches that are part of the state.

| offset | bytes | content |
|---|---|---|
| 0x00 | 52 | write shadow: for each of $2100-$2133 the last byte written to it (CPU, DMA or HDMA, any mirror bank), 0 if never written |
| 0x34 | 14 | for the double-write registers $210D-$2114 (8) and $211B-$2120 (6), in address order, the byte written before the last one |
| 0x42 | 2 | VRAM word address (after the increments), 15 bits (bit 15 is not observable and is cleared), LE |
| 0x44 | 2 | VRAM read prefetch latch, LE |
| 0x46 | 1 | OAM write low-byte latch |
| 0x47 | 1 | internal CGRAM word address (after the increments) |
| 0x48 | 1 | CGRAM byte flip-flop (0 = next access is the low byte) |
| 0x49 | 1 | CGRAM write low-byte latch |
| 0x4A | 1 | BG scroll latch of PPU1 (the previous scroll byte) |
| 0x4B | 1 | BG scroll latch of PPU2 (3 bits) |
| 0x4C | 1 | Mode 7 latch (the previous Mode 7 byte) |

Not included: the internal OAM address. It is the $2104/$2138 access
address, but during active display it is used and changed by the sprite
evaluation, and at the start of the vertical blank it is reloaded from
OAMADD; its value at the sampling point is an emulator-internal state.
What a program set is OAMADD ($2102/$2103), which is in the shadow; the
effect of $2104 writes is in `oam`.

Writes to the data ports ($2104, $2118, $2119, $2122) land in the shadow
too; their effect is in `oam`, `vram`, `cgram`. Wrong decoding of a
correct write stream shows in `img`, not in `ppu`.

## 5. The picture (field `img`)

Every pixel is the 15-bit BGR555 colour after colour math, with the master
brightness applied by the convention

```text
B = INIDISP bits 0-3 at the time the pixel was output
channel' = channel * B / 15   (integer division, per 5-bit channel)
```

(B = 15 keeps the colour; force blank gives 0). The hardware applies the
brightness in the analog domain; this rule is a convention that MesenCE
implements as is and that aresref computes from ares' raw output (colour
plus brightness). Pixels are stored as 16-bit little endian, bit 15 = 0.

Rows are scanlines 1 to 224 (1 to 239 when overscan was latched at V=0);
scanline 0 is never output. In an interlaced frame only the current field
is taken.

Width, the hi-res rule: the frame is rendered 512 half-pixels wide (even
= sub screen half-pixel, odd = main screen half-pixel in modes 5 and 6
and pseudo hi-res; a normal pixel gives two equal halves). If in the whole
frame every pair of half-pixels is equal, the canonical image is 256 wide
(one value per pair), else 512 wide (every half-pixel). The rule depends
only on the picture, so implementations that render 256 wide in normal
modes agree with those that always render 512 wide. `imgsz` gives the
resulting `<w>x<h>`.

## 6. Power-on state and masks

Hardware RAM powers on with unspecified content. Comparisons need a
defined start:

- `fill=00`: every memory (WRAM, VRAM, OAM, CGRAM, APU RAM) and every
  register value an emulator would otherwise randomise is 0 at power-on.
  This is the default of aresref (ares patched with "Zero Entropy") and of
  MesenCE (`--snes.ramPowerOnState=AllZeros`), and the setting MAMR uses
  for oracle runs. Exceptions in ares: values drawn with a bias keep the
  bias (PPU1 and PPU2 open bus $FF, VRAM increment mode 1); none of them
  is part of a field. The S-SMP stage-3 timer counters power on as 0 in
  ares and as 15 in MesenCE (hardware value unknown); they enter `smp`.
- The reset sequence of the 65816 does not write: its stack cycles are
  read cycles (WDC W65C816S datasheet, section 2.25 and table 5-7). ares
  writes them (patched in aresref, patch 0006); MAMR follows the
  datasheet. WRAM $0001FD-$0001FF therefore keep their power-on fill.
- `fill=ff`: as `00`, but the five memories are set to $FF. MesenCE
  (AllOnes) also sets the S-DSP registers to $FF, aresref does not.
- Cartridge save RAM without a save file starts as $FF in every fill (as
  ares allocates it; MAMR does the same; the MesenCE script writes $FF
  over it before the first instruction, because MesenCE fills it like the
  other RAM). Oracle runs never load a save file: aresref saves into a
  private directory removed after the run, run_mesen.sh deletes MesenCE's
  saves first. A test with a prepared save file is a separate case and
  must say so in the header (`save=<sha1>`).
- `fill=55`: MAME's fixed fill (not selectable).
- `fill=native`: ares' own deterministic pseudo-random state.

Mask for start values the program never wrote: run the same oracle (or
several) with `fill=00` and `fill=ff`, dump a frame, and keep the bytes
that are equal in both runs (`compare.py mask OUT DIR00 DIRFF ... --frame
F`). Bytes that still differ hold power-on data (or values derived from
it). `compare.py dumps A B --mask OUT` compares only the defined bytes.
Hash lines cannot be masked after the fact; masked comparisons work on
dumps.

**Dumps.** With their dump option the oracles write, for selected frames,
the canonical bytes of every field to `DIR/f<frame:06d>.<field>.bin`
(and the image size to `DIR/f<frame:06d>.imgsz.txt`).
`hashline.py fline DIR FRAME` rebuilds the F line from a dump, which
checks a writer's hashing against the reference.

## 7. Anchors and inputs: the auto-joypad read

Emulators end their frames at different points (MesenCE at scanline 225,
ares at 241, MAME after the screen update), so inputs and anchors are
bound to the n-th auto-joypad read instead of an emulator frame. An
auto-joypad read begins in scanline 225 when NMITIMEN bit 0 is set: in
ares at the first multiple of 256 clocks at or after H=130, in MesenCE
128 clocks earlier. The shared input script (snes-oracle-input-script.md)
advances once per auto-joypad read; frames without one (auto-read
disabled) do not step it. MesenCE decides when it finishes the frame
(after W(n)) from the NMITIMEN bit whether this frame's read happens.

## 8. A line: PC anchor

```text
A <n> pc=<pbpc> mclk=<clocks> d=<delta|-> anc=<reads> tag=<tag>
```

Written before each execution of the instruction at `pc` (an anchor given
to the oracle). `<n>` is the frame the hit falls into (number of F lines
written so far plus one), `d` the master clocks since the previous hit of
the same anchor (`-` for the first), `anc` the auto-joypad reads begun before
the hit. Cycle deltas per anchor replace cycle counts per frame
(architecture notes section 7). Compared as a sequence: pc and tag; with
`--timing` also anc, mclk and d (anc is a timing value here: a hit
shortly after the sampling point falls before or after the start of the
frame's joypad read depending on the implementation's read timing).

## 9. P line: APU port trace

```text
P <n> c t=<mclk> port=<0-3> val=<hh>
P <n> s t=<smp cycles> port=<0-3> val=<hh>
```

One line per write to an APU port: `c` for a CPU write to $2140-$217F
(port = address bits 0-1, DMA included), `s` for an SMP write to $F4-$F7.
`t` is the master clock for `c` and the SMP cycle count (1.024 MHz
nominal) for `s`; the frame `<n>` of an `s` line depends on how far the
emulator has run the SMP and is not compared. Compared as two sequences
(port, val per side); with `--timing` also `t`.

## 10. L line: picture rows (diagnostic, optional)

```text
L <n> <h1> <h2> ... <hH>
```

Written right after the F line of frame n when requested (aresref
`--lines`, MesenCE `FH_LINES=1`): one FNV-1a 64 per row of the canonical
`img` bytes of that frame, rows in order, H as in `imgsz`. Not part of
the chain and never compared on its own; when `img` differs and both
files carry L lines, `compare.py` reports the first differing row, which
localises a renderer difference to a scanline (snes-ppu-spec.md 10.2).

## 11. What a writer must do, in short

1. Power on with `fill=00` (zero WRAM, VRAM, OAM, CGRAM, APU RAM and all
   PPU, DSP and S-SMP state that is otherwise random; save RAM $FF); the
   reset sequence reads the stack, it does not write it. Run the APU at 32040 Hz * 768
   for comparisons against aresref (`clk=meas`).
2. Keep the PPU write shadow (section 4) on every write to $2100-$2133,
   HDMA included.
3. Count auto-joypad reads; step the input script at each.
4. Open the sampling window at the start of scanline 225 (240 with the
   latched overscan); at the next instruction boundary run a copy of the
   SMP to its first instruction boundary at or after that time stamp (and
   the DSP along; the emulation goes on with the original), build the
   twelve canonical byte sequences,
   print the F line (anc = reads begun before the window) and update the
   chain.
5. Optionally print A lines (anchors), P lines (port writes) and L lines
   (picture rows), and write dumps.
