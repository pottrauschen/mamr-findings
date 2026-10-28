# Super Pang hash lines, format spfh 1

One text file per run. The MAME writer (`spfh_mame.lua`) and MAMR's
`spang_headless` write the same lines; `hashline.py` is the reference
implementation, `compare.py` compares two files, `gates.py` runs the gates
of [spang-oracles.md](spang-oracles.md) section 5. File names without a
directory refer to `tools/oracle/spang/`. The structure follows
[snes-oracle-format.md](snes-oracle-format.md) and
[nes-oracle-format.md](nes-oracle-format.md); this note gives the whole
format, since the fields differ.

Plain ASCII, one record per line, fields separated by one space,
`key=value` pairs in the order given here. Lines starting with `#` are
comments. All hex is lower case.

## 1. Hash function

FNV-1a 64 over bytes, byte by byte (test vectors: `""` gives
`cbf29ce484222325`, `"a"` gives `af63dc4c8601ec8c`, `"foobar"` gives
`85944171f73967e8`).

## 2. Header line

```text
H spfh 1 oracle=<mame|mamr> core=<build> set=spang ym2413=<placeholder|rom|-> input=<sha1|->
```

`ym2413` names the YM2413 instrument data of the run (spang-oracles.md
section 3), `input` the SHA-1 of the input script file (`-` without one).

## 3. F line: one per frame

```text
F <n> zclk=<cycles> z80=<raw> wram=<h> vram=<h> obj=<h> pal=<h> bank=<raw>
  irq=<h> eep=<h> ym=<h> oki=<h> img=<h|-> ymn=<k> okin=<k> irqn=<k> mid=<0|1> all=<h>
```

(one line in the file). `<n>` counts the F lines from 1.

**Sampling point.** VBLANK start n is the time n x frame period (17,415,534,656,913,966
attoseconds) after power-on: power-on is the start of VBLANK of frame 0
in MAME's screen model. The sampling point of frame n is the first Z80
instruction boundary at or after cycle floor(VBLANK start n / 125e9),
before the next instruction (or interrupt entry). MAMR's runner stops
exactly there. MAME's frame notifier comes when the scheduler has run the
Z80 to that cycle, but MAME 0.285's Z80 stops wherever its cycle budget
runs out, inside instructions too (spang-hardware-spec.md section 1), so
the MAME writer only notes the time there and samples at the next fetch of
an instruction's first byte (an opcode-space read at the address CURPC).
`mid=1` records that MAME stood inside an instruction at the notifier
(informative; MAMR writes 0).

**Window.** Window n is the time between sampling points n-1 and n
(window 1 starts at power-on); the command fields `ym`, `oki` and `irq`
collect what happened in it.

**Keys besides the state:**

- `zclk`: Z80 T-states from power-on to the sampling point. Compared by
  default (`compare.py --no-timing` leaves it out).
- `ymn`, `okin`, `irqn`: number of YM2413 writes, OKI writes and interrupt
  entries in the window; informative.

**State fields.** Each field is a fixed byte sequence (its canonical
bytes). `z80` and `bank` are printed as the raw hex of those bytes, the
other fields as the 16-hex-digit FNV-1a 64 of them. A field a writer
cannot provide is `-` (`spang_headless --no-img`, MAME without
`FH_IMG=1`); `compare.py` skips it.

| field | bytes | content, in this order |
|---|---|---|
| z80 | 32 | PC, AF, BC, DE, HL, AF', BC', DE', HL', IX, IY, SP, WZ as big-endian 16-bit words; I; R (bit 7 included); IFF1; IFF2; IM; HALT (each 0 or 1 except IM) |
| wram | 8192 | work RAM E000-FFFF |
| vram | 6144 | tile RAM (4096 bytes, the D000 window with video bank 0), then attribute RAM C800-CFFF (2048) |
| obj | 4096 | sprite RAM (the D000 window with video bank != 0) |
| pal | 4096 | palette RAM, 2048 entries of 2 bytes little-endian, both halves of the C000 window |
| bank | 6 | ROM bank (port 0x02), OKI bank (gfxctrl bit 4), last byte written to port 0x00, last byte written to port 0x07, IRQ source bit, IRQ line (1 = asserted, not yet taken) |
| irq | 40 per entry | for every interrupt entry of the window: the cycle of the first opcode fetch of the handler (little-endian 64-bit) and the 32 z80 bytes at that moment (PC = 0x0038); empty when there was none |
| eep | 148 | the 64 EEPROM words, each little-endian; state, CS, CLK, DI, locked, command, bit counter (low byte), busy at the sampling point; command/address accumulator, address, shift register as little-endian 32-bit values (below) |
| ym | 2 per write | for every YM2413 write of the window: the port (0x04 address or 0x03 data) and the value |
| oki | 1 per write | every byte written to the OKI command port in the window |
| img | 184320 | the picture, 384 x 240, each pixel the xRGB444 value of its colour (16-bit little-endian), rows top to bottom: what MAME's `screen_device::pixels` returns at the sampling point (below) |

**The picture.** MAME draws the frame once, at its VBLANK timer, from the
live memories, into one of two bitmaps, and then swaps them
(src/emu/screen.cpp update_quads); `pixels` reads the current one, which
therefore holds the frame drawn at the previous VBLANK start, and looks
each pen up in the palette of now. So `img` of frame n is the frame drawn
at VBLANK start n-1, resolved through the palette at VBLANK start n;
frame 1 shows the never-drawn bitmap (pen 0 everywhere, through the
palette of frame 1). "At VBLANK start" means MAME's state at its timer,
where the Z80 may stand inside an instruction: a memory or port write
whose bus cycle starts at or after cycle floor(VBLANK start / 125e9) has
not happened yet (spang-oracles.md section 4, F3 and F4). MAMR's
`spang_headless` reproduces both (games/spang/spang_video.h
video_hash_picture).

The EEPROM state values are those of MAME's serial EEPROM device:
state 0 in reset, 1 waiting for the start bit, 2 waiting for the command,
3 reading data, 4 waiting for data, 5 waiting for completion; command
0 none, 1 READ, 2 WRITE, 3 ERASE, 4 lock (EWDS), 5 unlock (EWEN),
6 WRAL, 7 ERAL; busy = the last programming operation ends after VBLANK
start n.

**Chain.** `all` = FNV-1a 64 over LE64 of the previous `all` (0 before
frame 1) followed by LE64 of each state field's hash in the table order
(a field written as `-` adds eight zero bytes). zclk and the informative
keys are not part of the chain.

**Dumps.** With their dump option (`FH_DUMP_DIR`/`FH_DUMP_AT`,
`--dump-dir`/`--dump-at`) the writers store the canonical bytes of every
field as `DIR/f<frame:06d>.<field>.bin`; `hashline.py fline DIR FRAME`
rebuilds the F line, `compare.py dumps A B --field F` lists the differing
offsets.

## 4. Power-on

- Work RAM 0 (MAME's NVRAM default for a fresh run, nvram and cfg removed
  before every MAME run), EEPROM = the set's default image.
- Ports 0x00 and 0x07 written with 0 before the first instruction: MAME
  leaves the video bank, palette bank and flip registers uninitialised
  (spang-hardware-spec.md section 5); MAMR powers on with 0.
- Z80 registers as MAME's (spang-hardware-spec.md section 2).

## 5. Determinism and limits

Two MAME runs of the same frames and input script are byte-identical
(gate G1). `img` costs most of the MAME run time (spang-oracles.md
section 4).

Both writers take a start EEPROM other than the set's default (MAME
`SPANG_EEPROM`, `spang_headless --eeprom`): 128 bytes in the layout of
the set's file, 64 big-endian words. An interrupt taken right at the sampling point would put the
MAME sample after the entry and the MAMR sample before it; this needs an
IRQ held back by DI across VBLANK start and has not occurred.

## 6. Input script

One line per change, `#` starts a comment:

```text
<frame> [BUTTON ...]
```

From the sampling point of `<frame>` on, exactly the listed buttons are
held (none, or `-`, releases everything) until the next line. Frames are
integers >= 2, ascending. Buttons: `COIN1`, `SERVICE1`, `START1`,
`START2`, `P1_UP`, `P1_DOWN`, `P1_LEFT`, `P1_RIGHT`, `P1_B1`, `P1_B2`, the
same for `P2_`, and `SERVICE` (the service mode switch, port 0x05 bit 1).
The MAME writer sets the input fields in the notifier of frame
`<frame>` - 1; MAME applies field values at its next per-frame input
update, which runs at VBLANK start before the notifier (MEASURED-EMU: a
coin at frame 700 is read from window 701 on). spang_headless switches its
port values after sampling frame `<frame>`. Example:
`inputs/coin-start.txt` (an input script of the oracle kit, not
published: it plays the game).

## 7. I/O log

With `FH_IOLOG=FILE` (MAME) or `--iolog FILE` (spang_headless) every port
access is logged:

```text
<R|W> <window> <cycle> <port> <value>
```

`<cycle>` is the Z80 cycle of the I/O cycle (instruction start + 7 for
IN A,(n)/OUT (n),A), port and value in hex. `compare.py iolog A B` prints
the first differing access with context.
