# Arcade hash lines, format afh 1

One text file per run. The MAME writers (`tools/oracle/arcade/<set>_mame.lua`)
and MAMR's headless front ends (`ikari_headless --hash`, `rtype_headless
--hash`) write the same lines; `afh.py` is the reference implementation,
`compare.py` compares two files, `gates.py` runs the gates of
[arcade-oracles.md](arcade-oracles.md) section 7. File names without a
directory refer to `tools/oracle/arcade/`. The structure follows
[spang-oracle-format.md](spang-oracle-format.md); this note gives the
whole format, since the fields differ per set.

Plain ASCII, one record per line, fields separated by one space,
`key=value` pairs in the order given here. Lines starting with `#` are
comments (a writer that fails writes `# error: ...`). All hex is lower
case.

## 1. Hash function

FNV-1a 64 over bytes, byte by byte (test vectors: `""` gives
`cbf29ce484222325`, `"a"` gives `af63dc4c8601ec8c`, `"foobar"` gives
`85944171f73967e8`).

## 2. Header line

```text
H afh 1 oracle=<mame|mamr> core=<build> judge=<judge|-> set=<ikari|rtype> input=<sha1|->
```

`judge` names the MAME build of a MAME run (`mame-0.285` for the Ubuntu
package, `mameref-0.285` for the patched build of arcade-oracles.md
section 2), `input` the SHA-1 of the replay file (`-` without one).

## 3. Set ikari

### 3.1 F line

```text
F <n> clka=<c> clkb=<c> clks=<c> za=<raw> zb=<raw> zs=<raw> bg=<h> spr=<h> tx=<h>
  snd=<h> vreg=<raw> io=<raw> pal=<h> irq=<h> ym=<h> ymt=<h> img=<h|-> irqn=<k> ymn=<k>
  mid=<abc> all=<h>
```

(one line in the file). `<n>` counts the F lines from 1.

**Sampling point.** VBLANK start n is n frame periods after power-on, the
frame period being HZ_TO_ATTOSECONDS(60) = 16,666,666,666,666,666
attoseconds (MAME screen.cpp: the screen starts at the beginning of
VBLANK, and the first VBLANK start comes one frame later). For each CPU
the threshold is the cycle floor(VBLANK start n / cycle period) with
MAME's truncated cycle periods (298,507,462,686 attoseconds for CPU A and
B, 250,000,000,000 for the sound CPU).

- The memory fields (bg ... pal, img) are the state at VBLANK start: every
  access whose machine cycle starts before the threshold of its CPU has
  happened, no later one. MAME's frame notifier comes at that moment; a
  CPU may stand inside an instruction there (MAME's Z80 stops where its
  cycle budget runs out, arcade-oracles.md section 4).
- The register fields za, zb, zs and the timing keys are taken at each
  CPU's first instruction start at or after its threshold, after an
  interrupt entry the CPU takes there (MAME: the next opcode fetch, an
  opcode-space read at the address CURPC; the VBlank interrupt raised at
  VBLANK start is usually taken at that very boundary).
- MAMR stage M stops its CPUs exactly as MAME does; stage S runs every CPU
  to its first instruction boundary at or after the threshold and leaves
  out of the memory fields what the instruction then in progress changed
  with accesses at or after it (Machine::late).

**Window.** Window n holds what happened between VBLANK start n-1 and n
(window 1 starts at power-on): interrupt entries whose handler starts
before the threshold of its CPU, YM3526 writes whose machine cycle starts
before the sound CPU's threshold.

**Keys besides the state:**

- `clka`, `clkb`, `clks`: the cycle of each CPU at its sampling point,
  counted from power-on. Compared by default (`compare.py --no-timing`
  leaves them out).
- `irqn`, `ymn`: number of interrupt entries and YM3526 writes in the
  window; `mid`: three digits, 1 where CPU A, B or the sound CPU stood
  inside an instruction at VBLANK start (MAME: m_ref other than
  0xffff00). Informative.

**State fields.** Each field is a fixed byte sequence. Raw fields are
printed as the hex of their bytes, the others as the 16-hex-digit FNV-1a
64 of them. A field a writer cannot provide is `-` (img without the
picture option); compare.py skips it.

| field | bytes | content, in this order |
|---|---|---|
| za, zb, zs | 32 | CPU A, CPU B, sound CPU: PC, AF, BC, DE, HL, AF', BC', DE', HL', IX, IY, SP, WZ as big-endian 16-bit words; I; R (bit 7 included); IFF1; IFF2; IM; HALT |
| bg | 2048 | background video RAM 0xD000-0xD7FF (mirrored at 0xD800) |
| spr | 6144 | sprite RAM and work RAM 0xE000-0xF7FF |
| tx | 2048 | text video RAM and work RAM 0xF800-0xFFFF |
| snd | 4096 | sound CPU RAM 0xC000-0xCFFF |
| vreg | 18 | 16-bit little-endian: bg scroll x, bg scroll y, sp16 scroll x, sp16 scroll y, sp32 scroll x, sp32 scroll y (msb from 0xC900/0xCD00 included), hard flags position x and y, the text tile offset of 0xC980 |
| io | 7 | sound latch, sound status, NMI line of A, NMI line of B, INT line of A, INT line of B, INT line of the sound CPU (status & 0x0B); lines 1 = asserted |
| pal | 3072 | the 1024 pens of the colour PROMs, each blue, green, red (8 bits, MAME's RGB_444_PROMS weights) |
| irq | 42 per entry | for every interrupt entry of the window, grouped by CPU (A, B, sound) and in time order within a CPU (so the field does not depend on how an emulator interleaves the CPUs): CPU (0 A, 1 B, 2 sound), vector low byte (0x38 or 0x66), the cycle of the handler's first opcode fetch (little-endian 64-bit), the 32 z80 bytes at that moment |
| ym | 2 per write | for every YM3526 write of the window: code (0 chip 1 address, 1 chip 1 data, 2 chip 2 address, 3 chip 2 data), value |
| ymt | 10 per write | the same with the sound CPU cycle of the write (little-endian 64-bit) |
| img | 248832 | the picture, 288 x 216 in MAME's bitmap orientation (the monitor is rotated, ROT270), each pixel 4 bytes blue, green, red, 0xFF: what MAME's `screen_device::pixels` returns at the notifier, which is the frame drawn at the previous VBLANK start (spang-oracles.md F3); frame 1 shows the never-drawn bitmap, pen 0 everywhere |

**Chain.** `all` = FNV-1a 64 over LE64 of the previous `all` (0 before
frame 1) followed by LE64 of each state field's hash in the table order
(a field written as `-` adds eight zero bytes). The timing and
informative keys are not part of the chain.

### 3.2 Power-on and inputs

- RAM 0 everywhere, every register of the three Z80s 0 except
  IX = IY = 0xFFFF and F = 0x40 (MAME's z80.cpp; the chip leaves them
  undefined).
- Replay file: "ikari replay v1" as `ikari_headless --replay` reads it:
  runs of frames with the six port values IN0-IN3, DSW1, DSW2 (active
  low); entry f is what the program reads while frame f+1 runs. The
  values change at VBLANK start, the hardware event the program reads its
  inputs after: MAME applies field values at its per-frame input update
  inside vblank_begin, before the frame notifier, so the writer sets
  entry n+1 in the notifier of frame n (entry 1 before the first frame;
  entry 0 is the power-on state of the ports). Applied: the digital fields
  of IN0-IN3 and every DIP field; not applied: the sound busy bit (a read
  line), unused bits and the rotary nibbles (positional fields; the bot
  game keeps them at rest).

## 4. Set rtype

### 4.1 F line

```text
F <n> clkm=<c> clks=<c> v30=<raw> zs=<raw> ram=<h> spr=<h> sbuf=<h> pal=<h> vram=<h>
  snd=<h> vreg=<raw> io=<raw> pic=<raw> irq=<h> ym=<h> ymt=<h> img=<h|-> irqn=<k>
  ymn=<k> mid=<ab> all=<h>
```

**Sampling point.** MAME's frame notifier at VBLANK start n (screen line
256 of the 55.0 Hz M72 screen; MAMR stage M: the VBLANK timer of
arcade-oracles.md section 5). The V30 stands at an instruction boundary
there: MAME's nec core checks its cycle budget only between instructions
and between the iterations of a REP. Its registers are read with the
memory fields at the notifier. The sound CPU can stand inside an
instruction, so as for Ikari its registers and `clks` are taken at its
next opcode fetch; while the main CPU holds it in reset it has no next
instruction, and both are taken at the notifier.

**Window.** Window n holds what happened between the notifiers of frame
n-1 and n (window 1 starts at power-on), in MAME's time order: interrupt
entries of the V30 before the notifier, those of the sound CPU before its
sampling point, YM2151 writes before the notifier.

**Keys besides the state:**

- `clkm`: the V30's total cycle count at the notifier (MAME
  `m_totalcycles`), `clks`: the sound CPU's cycle at its sampling point,
  the machine time divided by the truncated Z80 period
  (279,365,114,840 attoseconds). Compared by default.
- `irqn`, `ymn` as for Ikari; `mid`: two digits, the second 1 where the
  sound CPU stood inside an instruction at the notifier (the first, the
  V30, is always 0). Informative.

**State fields.**

| field | bytes | content, in this order |
|---|---|---|
| v30 | 32 | AW, CW, DW, BW, SP, BP, IX, IY, DS1, PS, SS, DS0, IP, PSW as big-endian 16-bit words; prefetch queue length; the no-interrupt flag of a segment prefix or MOV/POP to a segment register; HALT; 0 |
| zs | 32 | the sound Z80, as za in section 3.1 |
| ram | 16384 | main CPU work RAM 0x40000-0x43FFF |
| spr | 1024 | sprite RAM 0xC0000-0xC03FF |
| sbuf | 1024 | the copy of sprite RAM the sprite DMA (a write to port 0x04) takes, the one the video draws |
| pal | 6144 | palette RAM 1 then palette RAM 2, 3072 bytes each |
| vram | 32768 | video RAM 1 (playfield A) then video RAM 2 (playfield B), 16 KB each |
| snd | 65536 | the sound CPU's RAM 0x0000-0xFFFF (the main CPU loads its program there) |
| vreg | 12 | 16-bit little-endian: scroll x of playfield A and B, scroll y of A and B (the low 16 bits of MAME's s32 registers), the raster interrupt line; then one byte each: video off, flip screen |
| io | 7 | sound latch, latch written flag, the RST buffer inputs (rstbuf.cpp: bit 0 the latch request, bit 1 the YM2151 IRQ), INT line of the sound CPU, sound CPU held in reset, INT line of the V30, NMI line of the V30; lines 1 = asserted |
| pic | 10 | the uPD71059 (pic8259): state, ISR, IRR, IMR, priority, IRQ lines, read selection (0 IRR, 1 ISR, 2 none: the meaning of OCW3's low bits, not the version-specific raw register), level trigger mode, auto EOI, vector base |
| irq | 42 per entry | as for Ikari, grouped by CPU (0 V30, 1 sound CPU): CPU, vector (V30: the table index; Z80: the RST address 0x08, 0x18 or 0x28 of mode 0), cycle (little-endian 64-bit), the 32 register bytes of the CPU after the entry. V30: the cycle is that of the read of the vector's segment word, 8 clocks after the PSW push that starts the entry; the registers are taken there with SP lowered by 4, PS:IP the vector and bytes 29-31 zero (MAME's taps do not see the handler's first opcode fetch, which goes through its memory cache). Z80: at the handler's first opcode fetch |
| ym | 2 per write | for every YM2151 write of the window: port (0 address, 1 data), value |
| ymt | 10 per write | the same with the sound CPU cycle of the write (little-endian 64-bit) |
| img | 393216 | the picture, 384 x 256, each pixel 4 bytes blue, green, red, 0xFF: MAME's `screen_device::pixels` at the notifier, the frame drawn up to the previous VBLANK start (with its partial updates at the raster interrupts), its pens resolved through the palette at the notifier |

**Chain** as in section 3.1, over these fields.

### 4.2 Power-on and inputs

- RAM 0 everywhere; the V30 as MAME's nec.cpp resets it (PS = 0xFFFF,
  every other register and flag 0 except the mode flag MD); the sound CPU held in reset with
  the registers of section 3.2 until the main CPU releases it (port
  0x02); a release resets PC, WZ, I, R and the interrupt flip-flops only,
  as MAME's z80.cpp device_reset does.
- Palette: MAME's palette device starts every pen as a rainbow colour and
  changes a pen only when the program writes it (arcade-oracles.md
  section 6, finding F6); MAMR's pens are black until written.
- Replay file: "rtype replay v1" as `rtype_headless --replay` reads it:
  runs of frames with the three 16-bit ports IN0, IN1 and DSW as the main
  CPU read them; entry f is what the program reads while frame f+1 runs.
  As for Ikari, the writer sets entry n+1 in the notifier of frame n.
  Applied: every field of IN0, the start, coin and service fields of IN1
  (bits 0-5; bit 7 is the sprite DMA flag, not an input) and every DIP
  field.

## 5. Dumps

With their dump option (`FH_DUMP_DIR`/`FH_DUMP_AT`/`FH_DUMP_EVERY`,
`--dump-dir`/`--dump-at`/`--dump-every`) the writers store the canonical
bytes of every field as `DIR/f<frame:06d>.<field>.bin`; `afh.py fline DIR
FRAME SET` rebuilds the state part of the F line, `compare.py dumps A B
--field F` lists the differing offsets.

## 6. Access log

With `FH_ACCLOG=FILE` (MAME) or `--acclog FILE` (ikari_headless) every
access of CPU A and B to 0xC000-0xFFFF and of the sound CPU to
0xE000-0xFFFF is logged (R-Type, MAME only: every V30 port write and
every sound CPU port access):

```text
<cpu> <R|W> <window> <cycle> <addr> <value>
```

`<cycle>` is the CPU cycle at the start of the access's machine cycle
(MAMR stage S: the start of the instruction), addr and value in hex.
`compare.py acclog A B [--cpu C]` prints the first differing access per
CPU with context.
