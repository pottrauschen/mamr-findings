# JRPG code in WRAM: survey of three ROMs and options for MAMR

Study of 2026-10-27; the follow-up measurements are in [snes-ram-code.md](snes-ram-code.md).

Sources: measurements with a local measurement tool (about 400 lines,
not published) against MAMR as of 2026-10-26 (no change since then under
runtime/snes, runtime/w65816* and recompiler/w65816*). ROMs: Chrono
Trigger (USA) (SHA-1 de5822f4...9312), Secret of Mana (Europe)
(d9aaf311...4bee6), Final Fantasy III (USA) (4f37e427...76e7).
Documents: [docs/snes-architecture.md](snes-architecture.md) section 3
(code in WRAM) and section 8 (phases),
[docs/machine-interface.md](machine-interface.md) section 10 (cartridge
ABI) and section 11 (points 2, 4, 5),
[docs/snes-rom-survey.md](snes-rom-survey.md) (seed count of code
outside ROM, finding tables),
[docs/snes-zelda-authority.md](snes-zelda-authority.md) section 7 (Zelda
native against the interpreter, wall times). Figures for Chrono Trigger
from the projects ct-recomp and ChronoRET are self-reported figures of
those projects.

Status: 2026-10-27. Nothing in the MAMR source tree was changed for this
study. Built outside the source tree only: the measurement tool (one
file, linked against the existing MAMR libraries) and a native FF3 test
build (section 5.1). No oracle run.

Evidence conventions:
- **Addresses** in the 65816 form `BB:AAAA`. WRAM addresses are written
  `7E:xxxx`, also when the code runs through the mirror `00:0xxx` (the
  column "PC" then gives the real PC).
- **Measured** means: counted in a run of this tool (provenance class
  MEASURED-EMU, MAMR interpreter stage S, never hardware evidence).
- **Self-reported** means: a figure from ct-recomp or ChronoRET as those
  projects report it, not re-checked.
- **(Assumption)** marks everything that is neither measured nor
  documented.

Measurement data, scripts, routes and traces stay local and are not
published; appendix A lists what they contain.

---

## 1. Summary

- **RAM code is unpacked code in all three games, not copied code.**
  Chrono Trigger and Final Fantasy III unpack an LZ module through
  WMDATA (`$2180`) into WRAM, Secret of Mana through an MVN unpacker that
  itself runs in low RAM. None of the large routines stands in the ROM as
  a byte sequence (search without result). The option "recognise the copy
  source in ROM and translate it as a ROM block" therefore carries only
  for stubs of 4 to 46 bytes.
- **The content is fixed.** Over the measured routes every executed
  instruction address always saw the same bytes, except 4 in CT, 1 in
  FF3 and 21 in SoM of 1068 / 2130 / 7587 keys (address, M, X). The
  memory is used for data in between and the module is unpacked again,
  identically (CT: module bytes written 13 times in the median). Real
  self-modification was found only in small stubs (SoM unpacker, MVN
  stubs, trampolines) and in one SoM routine with a patched operand (99
  variants of a page byte).
- **The share depends on the game phase.** Over 12000 frames 6.3 % (CT),
  7.7 % (SoM) and 9.0 % (FF3) of all instructions ran in RAM. In the
  title and intro (frames 1 to 1500) it is 58 to 66 %, in the play part
  of the routes after that 0.01 % (CT), 0.31 % (SoM) and 1.6 % (FF3). In
  CT 83 % and in FF3 71 % of the RAM instructions are a wait loop.
- **Falling back to the interpreter costs little** (section 5.1): for
  Zelda the native build saves about 12 % of the wall time against the
  pure interpreter (31.3 s against 35.4 s,
  [docs/snes-zelda-authority.md](snes-zelda-authority.md) section 7).
  Measured on FF3: in the native test build the ROM code runs 100 %
  natively (0 ROM misses), the RAM code stays interpreted (10.5 % of the
  CPU clocks), the hash lines equal the interpreter's, and fully native
  against fully interpreted differs in wall time only within the noise
  (102.7 s against 102.5 s for 12000 frames).
- **Recommendation:** for version 1 RAM code stays in the interpreter.
  This is measured and secured with gates (W1-W2). Content keys with page
  generations (option A) are built only if a longer route shows a part of
  the play with a high RAM share (W3-W5, about 5-7 working days). The
  ABI reservation `MAMR_CODE_W65816_WRAM_BLOCKS` stays in place for it.

---

## 2. Measurement setup

**Tool.** The local measurement tool (about 400 lines, not published)
runs the MAMR SNES machine (stage S, `use_blocks = false`, so every
instruction in the interpreter) and hooks in at two places:
1. `W65816Cpu::on_interp` before every instruction: PC, region (through
   `map_decode`), M/X/E, instruction length from `w65_row`/`w65_length`,
   the bytes of the instruction at the time of execution. Per key (WRAM
   address, M, X, E) every distinct byte sequence is counted with its
   count and first frame.
2. `W65816Bus::read8/write8`, redirected to wrappers that call the
   original. Per WRAM byte it records: number of writes, value changes,
   changes after the first execution, last writer (CPU store with PC,
   MVN/MVP with PC, GP-DMA through `$2180`, CPU write to WMDATA `$2180`
   with WMADD) and a source address.
   - For MVN/MVP and DMA the source address is exact: the read of the
     same instruction, for DMA `A1B:A1T` plus the step.
   - For CPU stores it is a heuristic: the last data read of one of the
     eight preceding instructions, without opcode fetches.

The run is bit-identical with `snes_headless --interp-only`: the same
instruction count (CT 39072807) and the same final clock (mclk
1072404908) over 3000 frames, cross-checked with `snes_headless
--pc-log`.

**Evaluation.** A part of the tool forms clusters of executed bytes,
joining gaps of up to 16 bytes. Per cluster it determines size,
instruction count, variants, writers, source region, whether the bytes
at their first execution equal the ROM byte at the source address
("verbatim"), and searches the ROM for the longest contiguous executed
byte sequence.

**Routes.** The survey scripts `tests/snes-oracle/scripts/{ct,som,ff3}.txt`
(3000 frames) were extended to 12000 frames by a local script: the
endless key at the end is dropped, then follows a pattern of walking in
four directions, A and B. With the IPL dump tests/data/spc700.rom
(local, not distributed). Picture check every 750 frames (contact
sheets):
- **CT:** settings menu, world map intro, from about frame 3750 Crono's
  room. The stairs are not hit; two further pattern variants also stayed
  in the room. No Leene Square, no battle.
- **SoM:** title, intro (title lettering, Mana tree, river), from about
  frame 4500 the boy at the waterfall near Potos.
- **FF3:** title, intro text, Magitek march in the snow, from about frame
  9000 Narshe. No battle, no world map, no menu.

---

## 3. Survey per game

### 3.1 Table (route of 12000 frames)

| | Chrono Trigger (USA) | Secret of Mana (Europe, PAL) | Final Fantasy III (USA) |
|---|---|---|---|
| instructions in all (interpreter units, MVN per byte) | 173,321,941 | 200,300,969 | 169,737,305 |
| of them in WRAM | 10,925,714 (**6.30 %**) | 15,317,181 (**7.65 %**) | 15,265,644 (**8.99 %**) |
| of them through the mirror `00:0000-1FFF` | 20,225 | 766,902 | 21,684 |
| SRAM / other regions | 0 / 0 | 0 / 0 | 0 / 0 |
| clock share of the WRAM instructions (approximation, clocks up to the next instruction) | 9.5 % | 8.3 % | 9.0 % |
| frames 1-1500 (title, intro) | 66.2 % | 62.7 % | 58.0 % |
| frames 1501-12000 (play part of the route) | 0.012 % | 0.31 % | 1.58 % |
| peak frame | frame 89: 100 % | frame 19: 100 % | frame 306: 100 % |
| of it wait loop | 83 % (`7E:3023 JSR $3176`, then `RTS`, `LDA $00`, `BEQ`) | 7 % (`7E:A2AE LDA/AND/BEQ`) | 71 % (`7E:7206 LDA/BNE`) |
| executed WRAM bytes | 2,357 | 13,506 | 4,711 |
| keys (address, M, X) | 1,068 | 7,587 | 2,130 |
| routines (clusters, gap up to 16 bytes) | 22 (largest 452 bytes) | 76 (largest 1,455 bytes) | 21 (largest 605 bytes) |
| WRAM range | `7E:0500`, `7E:3000-8A00`, `7E:9690` | `7E:0100-0107`, `7E:01C9-01F6`, `7E:02C5`, `7E:05A7-05D8`, `7E:0B00-0B30`, `7E:805F-D6E1` | `7E:1500-1507`, `7E:5000-7B42` |
| keys with more than one byte sequence | 4 (none with another opcode) | 21 (15 with another opcode) | 1 (none with another opcode) |
| writers of the code bytes (first execution) | unpacker `C3:05A0-0633`: literals through WMDATA, back references by MVN `C3:0633` | unpacker stub in low RAM: MVN `00:01F0` (literals from ROM), MVN `00:01E1` (back references 7E to 7E); the stub itself by MVN `C1:4C58` from `C1:4C07` | unpacker `C2:FFB5` / `C2:FFDD`, both through WMDATA |
| source in ROM (literals) | `C3:1316-C3:5AEB` (packed) | `C7:7C5D-C7:B469` (packed) | `C2:686F-C2:89A8` (packed) |
| longest executed sequence found in ROM | no (a 22-byte sequence by chance at file offset `030CE2`) | no | no |
| first execution | frame 35 (trampoline), module from frame 83 | frame 1 (stub), module from frame 12 | frame 49 (trampoline), module from frame 59 |

Origin of the numbers: the local raw data of the 12000-frame runs
(summary, per-frame table, per-instruction table, cluster table and
report per game). The 3000-frame runs show the same routines. There the
share is 27.9 % (CT), 30.3 % (SoM) and 30.2 % (FF3), because the intro
is a larger part of the route. The survey counted seed blocks outside
ROM on the same material: CT 212, FF3 281, SoM 1786
([docs/snes-rom-survey.md](snes-rom-survey.md)).

The clock shares are an approximation. Counted are the clocks from one
instruction start to the next, including stolen time that falls into
that span. Gaps over 100,000 clocks are left out.

### 3.2 Over time (share of WRAM instructions per 750 frames)

| Frames | CT | SoM | FF3 |
|---|---|---|---|
| 1-750 | 73.0 % | 91.0 % | 51.0 % |
| 751-1500 | 59.7 % | 35.3 % | 65.4 % |
| 1501-4500 | 0.0 % | 0.0 % | 0.0 % |
| 4501-5250 | 0.0 % | 4.2 % (`7E:0B00`) | 0.0 % |
| 5251-8250 | 0.0 % | 0.0-0.3 % | 0.0 % |
| 8251-9000 | 0.0 % | 0.0 % | 21.9 % (new clusters from the same module, first execution frames 8741-8859) |
| 9001-12000 | 0.0 % | 0.0 % | 0.0 % |

"0.0 %" means below 0.05 % here: the trampolines run every frame, but
with 1 to 2 instructions.

**What the phases are (assumption, from pictures and literature):**
- **CT:** according to ChronoRET the module at `7E:3000` is the program
  of the jet bike race, which the title uses as well (self-reported).
  ct-recomp reports 59.7 % of the boot instructions at `7E:3176`
  (self-reported). Measured: 2,273,543 calls of `JSR $3176` from the idle
  loop at `7E:3023`, and `$3176` is an `RTS`.
- **FF3:** the module `7E:5000-7B42` runs in the title and intro and
  again from frame 8741 (the picture between the Magitek march and
  Narshe). Whether it is the world map or Mode 7 program is not checked
  (assumption).
- **SoM:** the unpacked program `7E:805F-D6E1` (a range of about 22 KB,
  13.5 KB executed) runs only in the intro. In the play part run the IRQ
  handler `7E:A275` (through the trampoline `7E:0104`), the NMI redirect
  `7E:0100` and from frame 4793 the routine `7E:0B00`.

**Not measured** (the routes do not reach them): battles, menus, world
map, Mode 7 scenes in the game (CT race and Epoch, FF3 airship), shops,
saving. ct-recomp gives for CT in battle 1.1 % interpreted instructions
from the trampolines `$0500/$0504` alone (self-reported, ct-recomp issue
#105). So no large RAM share is to be expected for the CT battle
(assumption).

### 3.3 Immutability and reuse

- **Measure:** instead of a hash per routine at fixed times the tool
  counts the bytes of every instruction at every execution. A routine
  counts as unchanged if every one of its instructions had only one byte
  sequence over the whole route; this is stricter than a hash at sample
  times and equivalent to "hash of the executed bytes constant".
- **One run:** in CT and FF3 not a single instruction address saw
  another opcode, in SoM only the 15 keys of the stubs of section 4. In
  CT and FF3 nearly all executed bytes were nevertheless overwritten
  after their first execution: 2355 of 2357 and 4171 of 4711. They were
  written several times (median: CT 13 times, FF3 8 times). At the end of
  the run only 114 and 550 of these bytes still equal the executed
  content. So the module shares its memory with data (for example CT
  clears the range from `7E:2E00` by DMA with the fixed source byte
  `C2:9510`, seen in the DMA table) and is unpacked again, identically,
  before it is used again.
- **Two runs:** all 2357 / 13457 / 2807 bytes executed both in the
  3000-frame and in the 12000-frame run are identical. The evidence is
  limited, because the routes have the same script up to frame 3000.
- **Consequence for the options:** a block bound to its address and
  invalidated only by writes loses its validity at every new unpacking,
  although the content stays the same. Validity must therefore depend on
  the content (hash); writes are good only as a cheap trigger for a
  re-check.

---

## 4. Patterns

Classes; shares refer to the WRAM instructions of the 12000-frame route
(cluster table, column `class`).

| Class | CT | SoM | FF3 |
|---|---|---|---|
| (a) fixed routine, always the same bytes | 20 clusters, 99.8 % | 72 clusters, 95.0 % | 19 clusters, 99.9 % |
| (b) operand patch | 1 cluster (`7E:9690`), < 0.1 % | 1 cluster (`7E:0B00`), 3.6 % | 0 |
| (c) opcode changes (self-modification, generated code) | 0 | 2 clusters (`7E:01C9`, `7E:05A7`), 1.3 % | 0 |
| (d) trampoline | `7E:0500` | `7E:0100-0107` | `7E:1500-1507` (and `7E:5A62`, 4 bytes, in the module) |

### (a) Fixed routines: unpacked, not copied

Evidence CT: cluster `7E:30D8-7E:3208` (305 bytes, 22 % of the WRAM
instructions of the 3000-frame route). The writers are `move/C3:0633`
for 121 bytes (source WRAM, so an LZ back reference) and
`wmdata/C3:060C` or `C3:05FB` for 184 bytes (source ROM
`C3:13FC-C3:150C`). Each of the 184 literal bytes equals the ROM byte at
its source address, but the contiguous sequence does not stand in the
ROM. The same picture in FF3 (`C2:FFB5`/`C2:FFDD`, literals from
`C2:6C52...`) and SoM (`MVN` at `00:01F0` with source bank `C7`, back
references `MVN 7E,7E` at `00:01E1`).

Trace SoM, unpacker in low RAM (frame 11):

```
pc=0001e1 MVN  54 7e 7e    a=0004 x=c936 y=cbb0 d=01c5 db=c7   back reference: 5 bytes 7E:C936 -> 7E:CBB0
pc=0001e9 JSL  22 c0 4c c1 a=0000 ...                          next control byte (ROM routine C1:4CC0)
pc=0001f0 MVN  54 7e c7    a=0001 x=ad67 y=cbb5 db=c7          literal: 2 bytes C7:AD67 -> 7E:CBB5
pc=0001f5 BRA  80 f1
```

So (a) is **in content ROM code at another address, but not byte for
byte in the ROM**. Translating it statically needs the unpacked image:
either captured from a run or made by a rebuilt unpacker per game (this
is how ct-recomp does it for CT, self-reported).

### (b) Operand patch

- **SoM `7E:0B00`** (frame 4793 on, 544,687 instructions). The routine is
  written by ROM code `00:998E`. After that `00:9A11`/`00:9A13` patch,
  before every pass, the page byte of two `LDA $xx00,Y` from a ROM table
  at `C6:8343`. Measured: 99 distinct values (`$28`, `$29`, ..., `$00`,
  `$FF`, ..., `$E8`) at `7E:0B02` and `7E:0B18`. Trace:
  ```
  pc=000b00 LDA  b9 00 28    y=00fa d=0b00 db=c7
  pc=000b1d STA  8f 80 21 00                      -> WMDATA, so back into WRAM
  ```
  Variant log: `frame=4793 pc=000b00 op=LDA old=b90028 new=b90029 writers=2:1/009a11/srcc68343`.
- **CT `7E:9690`**, the MVN stub of the menu: `MVN $7E,$xx` with a
  patched source bank. Measured in frame 1471/1472: values `DC`, `D2`,
  `D4`, `D3`, `DE`, `D5`, writers `C2:F761` and `C2:F70D`. This agrees
  with ChronoRET's routine that moves the menu's NMI code
  (self-reported).

### (c) Opcode changes

- **SoM `7E:01C9-01F6`, the unpacker itself.**
  - Frame 1: `C1:4C58` copies it by MVN from `C1:4C07`.
  - Frame 12: a second, different version is copied over the first (for
    example at `7E:01E2` first `MVN 7F,7F`, then `JSL $C14CC0`).
  - After that ROM code patches the bank bytes of the MVN instructions
    (`C1:4C63`, `C1:4C65`, `C1:4C67`) and the target of a BNE (`C1:4C81`
    writes the displacement: `D0 E1`, then `D0 E2`, then `D0 E0`).
  - From frame 15 RAM code (`7E:C3F1`...) writes an MVN at `7E:01D7`.

  Evidence: the variant log of the run, entries of frames 12, 15 and 17.
- **SoM `7E:05A7-05D8`, generated MVN stubs.** The routine `7E:C3EF`
  writes `LDA #$54 / STA $01 / LDA $01,S / STA $02 / LDA $01,S / STA $03 /
  LDA #$6B / STA $04` with D at `$05xx`, that is `MVN dst,src ; RTL` at a
  D-relative, changing address. Then it calls the stub. Depending on the
  position `7E:05AA` holds once `RTL`, once `MVN 7F,7F` (variant log
  frame 832/833). Trace: `pc=0005b2 MVN 54 7f 7f a=00fe x=4500 y=4501
  d=05b1` (frame 832).

Real self-modification in large routines, as ChronoRET reports it for
the CT module at more than ten places (idle JSR `$3023`, Mode 7 loop),
did not occur on the CT route. The JSR operand at `7E:3023` always stood
at `$3176`. According to ChronoRET those places belong to programs of the
module the route does not reach (race, Mode 7 scenes).

### (d) Trampolines

- **CT `7E:0500`** (NMI, vector `00:FF10` to `JML $000500`). The target
  changes between `C3:08B3`, `C0:EA63`, `C2:840E` and `C2:015E`. It is
  written once by ROM code `C0:0B66/0B6C/0B7D` (the NMI install routine
  according to ChronoRET), once by MVN `C2:80A5` from the ROM image
  `C2:8407` (`5C 0E 84 C2`). Trace: `f=1529 pc=000500 JML 5c 0e 84 c2`.
- **FF3 `7E:1500/1504`** (NMI/IRQ). First ROM code `C0:0575...0589` sets
  `JML $C00182`. Then the unpacked module installs its handlers itself
  (code from `7E:5062`): it stores the JML opcode at `$1500` and `$1504`
  and behind them the targets `7E:7233` (NMI) and `7E:7264` (IRQ). The
  NMI then runs in RAM (`7E:7233`, 970 entries from frame 369); the IRQ
  entry points to `7E:7264` and was not executed on the route.
- **SoM `7E:0100/0104`** (vectors into the low-RAM mirror).
  - At `7E:0100` stands first `RTI`, from frame 1061 `JML $C020A7`
    (writer `C0:2890...289E`), from frame 1578 `JML $00C0A8` (writer
    `00:BC8C`).
  - `7E:0104` holds `JML $7EA275`: the IRQ handler lies in the unpacked
    program.

The trampolines cost one interpreted instruction per interrupt (CT
20,225, FF3 21,684 executions in 12000 frames).

---

## 5. Options

### 5.1 Option D: keep the interpreter fallback (current state)

**What happens today:**
1. The dispatcher finds no block for a WRAM PC.
2. The interpreter executes the instruction, logs the miss and hands
   control back to the dispatcher.
3. ROM blocks continue natively.

This is described as the state in
[docs/machine-interface.md](machine-interface.md) section 11 point 2
("the games above run in the interpreter for that code").

**Costs, measured and derived:**
- Share of instructions: see 3.1. On average 6-9 %, in the intro up to
  100 % of single frames, in the play part of the routes 0.01-1.6 %.
- Wall time: the interpreter is not the bottleneck of the machine.
  - Zelda: 6000 frames 31.3 s native against 35.4 s interpreted, route
    50.5 s against 57.3 s
    ([docs/snes-zelda-authority.md](snes-zelda-authority.md) section 7).
  - Contra III: 17.7 s against 19.3 s
    ([docs/snes-rom-survey.md](snes-rom-survey.md)).
  - So the native build saves 8-12 % of the run time against the pure
    interpreter. If 6-9 % of the instructions stay interpreted, that
    costs roughly 0.5-1 % of the wall time (estimate, assumption).
- **Native FF3 test build:**
  - Setup: seeds from the miss log of the route and of a 3000-frame run
    without input. `snes_recomp --no-tables --parts 4` gave 7660 blocks
    and 35,951 instructions. Built as `snes_headless_native` in a
    separate tree (`-DJF_WITH_SDL=OFF`, -j4, 1 min 43 s).
  - Equality: over the 12000-frame route the hash lines of the native
    and the `--interp-only` run are equal, except the header line
    (`blocks=7660` against `0`).
  - What stays interpreted: 15,265,647 instructions. These are exactly
    the WRAM instructions of 3.1 plus 3 in emulation mode. Of 482 miss
    entries 476 lie in bank `7E`, 6 are the trampoline through the
    mirror (`00:1500`, `00:1504`). There were no ROM misses.
  - Clock share: the interpreter comes to 10.5 % of the CPU clocks
    (361,834,570 of 3,452,028,258).
  - Wall time (the same binary, one after the other, while an unrelated
    ctest -j2 ran): native 102.7 s / 90.5 s against interpreted 102.5 s
    / 91.8 s.
  - Conclusion: for FF3 the difference between fully native and fully
    interpreted lies below the noise. The machine time is in the PPU,
    DMA and HDMA (44.7 MB HDMA, 835 million stolen clocks) and in the
    SMP. The cost of the RAM instructions is therefore unmeasurably small
    on this machine. For CT and SoM this is not measured.
- Interpreted, the three games run here at about 120 frames per second,
  about twice real time (12000 frames in about 97 s including the
  measurement wrappers). A frame with 100 % RAM code is therefore no
  real-time problem on this computer. On weaker hardware this is not
  checked.

**Effects:**

| Area | Effect |
|---|---|
| contract | none; `snes-architecture.md` section 3 already says that an invalid WRAM block falls into the interpreter |
| hash lines | none |
| save states | none |
| ABI | none |
| emitter | none |
| Zelda equality | untouched |

**Effort:** 1-2 working days for the measurement tool, routes, native
artefacts of the three games from miss logs and gates (W1-W2).

**Risk:** low for correctness; the interpreter is the reference. Two
points remain:
- The goal "100 % native" is missed for these games. There is a
  precedent: the Super Pang stub stays interpreted as well.
- The miss log fills with WRAM seeds that `snes_recomp` drops as
  "no-code target". That does no harm, but should be counted separately
  in the report.

### 5.2 Option A: extend the block key by a content hash

**Idea.** A WRAM block is valid as long as the bytes it was translated
from stand in WRAM. The key is (mapping RAM, PB:PC, M, X, hash of the
block bytes); PB has to be part of it, because `00:0100` and `7E:0100`
are the same bytes with different PB. The bytes come from a capture run,
no unpacker is needed. The run (interpreter, like the miss log today)
writes for every executed WRAM block address, M, X, length and bytes.
`snes_recomp` decodes from this image instead of the ROM.

**Validity at run time** (this is option C as a building block, see
5.4). Every 256-byte WRAM page with registered blocks has a generation
counter that every write increments: CPU store, WMDATA, DMA. The
dispatcher checks the generation at entry. If it is unchanged, the block
runs. Otherwise it hashes the block bytes again and compares. If they
are equal it remembers the new generation, else it jumps into the
interpreter. ct-recomp measures +0.38 % on the boot for this
(self-reported). Because CT and FF3 unpack their modules again (3.3),
the generation check fails once after every unpacking; after that the
hash carries.

**Mandatory rules the contract needs:**
1. **Validity per block, not per function.** This is already in
   `snes-architecture.md` section 3.
2. **Self hit:** a WRAM block that writes into WRAM must check after
   every store whether a page with its own code was hit. If so, it ends
   after that instruction at the resume point. This concerns the SoM
   unpacker, which does not write its own MVN bytes itself (ROM code
   does), and the MVN stub generators, which write into another page. No
   case was measured in which a block changes its own next instruction.
   The rule is needed for correctness all the same.
3. **Operand patches (b)** without a flood of variants: known patch
   places are translated as a run-time read and taken out of the hash;
   this is ct-recomp's proposal #97. Otherwise SoM `7E:0B00` would get 99
   block variants. The capture run can deliver the patch places: bytes of
   a block with more than one variant whose opcode stays the same.
4. MVN/MVP, PLP, RTI and so on as for ROM blocks. DB and D are not
   folded; that is in the contract.

**Effects:**

| Area | Effect |
|---|---|
| contract (`snes-architecture.md` 3) | new key for mapping RAM; rules 2 and 3 new; mirror rule PB |
| hash lines | format unchanged. The gate "native equal to the interpreter, every line" must run over the title and intro of the three games, where the RAM code is |
| save states | format unchanged. Generations and the validity cache are run-time state: after loading everything counts as unconfirmed, the first entry hashes. `machine-interface.md` 11 point 4 (continuation through PB:PC) still holds |
| cartridge ABI | new section `MAMR_CODE_W65816_WRAM_BLOCKS` (2), table with PB, PC, M, X, length, hash, function and resume points. If the self-hit check needs a new bus callback or a pointer to the generations in `W65816Bus`, the layout of an ABI structure changes. That is then **ABI version 3**, and all artefacts are rebuilt (section 10: "A change to any of them bumps the version") |
| emitter | new byte source (image instead of ROM), patch places as reads, self-hit check after WRAM stores, only in WRAM blocks |
| discovery | capture run as part of the artefact build (like the miss log, `machine-interface.md` 11 point 1); a static CFG in the captured image from the observed entries is possible, but only over bytes already written at capture time |
| Zelda equality | Zelda executes no RAM code (`snes-zelda-authority.md`: "no RAM code"). Generated C and hash lines stay the same as long as the new checks stand only in WRAM blocks and the page generation is counted only when blocks are registered on the page. Gate: Zelda artefact byte-identical before and after the change, `snes_native_zelda_*` green |
| ROM data in the artefact | hashes and operands as for ROM blocks, no image in the artefact |

**Effort:** 5-7 working days:
- capture: 0.5
- recompiler with image input and mapping RAM: 1
- run time (generations in `Map::write8`, WMDATA and DMA; second table
  in the dispatcher; hash): 1.5
- emitter rules 2 and 3: 1-1.5
- ABI section and possibly version 3: 0.5
- gates (lockstep on three intros, CI test program with
  self-modification): 1-1.5

Scale as in earlier MAMR work (the R-Type phases R1-R6); an estimate by
analogy, not verified.

**Risk:** medium.
- Errors show as a silent deviation when a write path does not increment
  the generation. On this path DMA is easy to overlook: according to the
  runtime a `$2180` DMA from WRAM writes a 00
  ([docs/snes-hardware-spec.md](snes-hardware-spec.md) section 3.5).
- The lockstep native against interpreter catches that, but only on the
  measured routes.
- Little benefit for the measured parts of the play.

### 5.3 Option B: recognise the copy source in ROM, translate it as a ROM block with address translation

**Measured finding against it:** the large routines are unpacked (3.1,
row "longest executed sequence found in ROM": no for all three). Copied
verbatim are only:
- the SoM unpacker stub (46 bytes from `C1:4C07`, patched afterwards),
- CT's NMI trampoline from `C2:8407` (4 bytes),
- the trampolines written by ROM code (FF3, CT, SoM).

These are exactly the places that are patched afterwards.

**Variant B':** rebuild the unpacker per game (CT `C3:0557`, FF3
`C2:FF6x`, SoM `C1:4Cxx` plus the RAM stub). The module is unpacked
offline and translated statically (the ct-recomp way). Advantage over A:
the whole module is visible, including the roughly 6 KB of the CT module
that according to ChronoRET no tracing reaches. Disadvantages:
- Game-specific code in the game layer.
- The run-time validity of A is still needed, because the memory is
  reused (3.3) and stubs are patched.

**Effects:**
- As A.
- In addition a game layer per title (unpacker plus the test "call for
  call against the ROM routine" as in ct-recomp).
- The question of origin is harder. ct-recomp attributes the CT MVN stub
  `7E:9690` wrongly to the module (self-reported); the writer data here
  show it correctly as menu code `C2:F70D/F761`.

**Effort:** A plus 1-1.5 working days per game.

**Risk:** medium to high (unpacker errors, game specifics). Not sensible
as a replacement for A, conceivable as a later addition to A if capture
runs find too few entries.

### 5.4 Option C: write guard on RAM code pages

**On its own** (blocks bound to the address, invalid on a write, back
into the interpreter): insufficient. First, the same address holds
different code at different times: the SoM stub `7E:01C9` has different
opcodes in frame 1 and frame 12. A block translated ahead of time must
therefore know its content, and that is option A. Second, a pure guard
without a hash would fall into the interpreter for good after every new
unpacking; CT and FF3 unpack again all the time (3.3).

**As a building block of A** there are three variants:
- **C1:** hash at every entry. Simple, cost per entry proportional to the
  block length.
- **C2:** page generation plus a hash only on a change. The ct-recomp
  way, +0.38 % (self-reported).
- **C3:** write bitmap per byte with block assignment. More precise, more
  memory.

Recommendation within A: C2. Extra cost for games without RAM code: one
test per WRAM write whether the page is marked; not measured.

**Effects:** as A, run-time part. Hash lines and save states untouched.

**Effort:** included in A (1.5 working days run time).

### 5.5 Comparison

| | D interpreter | A content hash (+C2) | B copy source | B' unpacker per game | C alone |
|---|---|---|---|---|---|
| covers (a) fixed modules | interpreted | native | no (packed) | native | no (new unpacking) |
| covers (b) patches | interpreted | native with patch rule | no | with patch rule | no |
| covers (c) generated code | interpreted | interpreter fallback | no | fallback | no |
| covers (d) trampolines | 1 instruction interpreted | native or fallback | partly | partly | no |
| contract | unchanged | extended | extended | extended | extended |
| hash lines / save state format | unchanged | unchanged | unchanged | unchanged | unchanged |
| ABI | unchanged | section 2, possibly version 3 | as A | as A | version 3 possible |
| emitter | unchanged | new rules | address translation | as A | unchanged |
| Zelda | untouched | gate needed | gate needed | gate needed | gate needed |
| working days | 1-2 | 5-7 | A + 1 | A + 1-1.5 per game | (part of A) |
| risk | low | medium | - | medium to high | - |
| measured benefit on the routes | - | 6-9 % of the instructions, nearly only intro | a few stubs | as A plus undiscovered entries | - |

---

## 6. Recommendation and phase plan

**Recommendation:**
1. RAM code stays in the interpreter for version 1 (option D), and the
   share is kept as a key figure per game and route. Reason: over the
   measured routes 6-9 % of the instructions are affected, in the play
   part 0.01-1.6 %. The content is unpacked and accessible for static
   translation only through a capture run or an unpacker per game. The
   interpreter is the reference and costs little wall time.
2. Option A is built only when a longer route (battle, menu, world map,
   Mode 7 scene) shows a part of the play with a high RAM share, or when
   "100 % native" explicitly becomes a goal. Then as A with C2 and the
   patch rule, not as B.
3. The ABI reservation stays; a move to ABI version 3 is decided only
   with A.

**Phase plan** (WD: working days):

| Phase | Content | Result / gate | WD |
|---|---|---|---|
| W1 | RAM statistics as a repository tool: `snes_headless --ram-stats` (share per frame, clusters, writers, variants), output next to `--stats`. Longer routes for CT, FF3, SoM with battle, menu, world map and Mode 7 scene; routes by `WAIT_RAM8` instead of blind patterns | table 3.1 for five game situations per game; basis for the decision on W3 | 1 |
| W2 | native artefacts of the three games from miss logs (ROM code), RAM code interpreted; ctests native equal to the interpreter over title, intro and route; interpreter share as a key figure in the test log | gate: every hash line equal, 0 ROM misses on the route | 1-1.5 |
| W3 (conditional) | run time for A: page generations (CPU store, WMDATA, DMA), second block table for mapping RAM, validity C2; first with test blocks registered by hand | synthetic CI ROM with self-modification, lockstep equal | 1.5-2 |
| W4 (conditional) | capture run, `snes_recomp` with image input, emitter rules (self hit, patch places), ABI section 2 / version 3 | CT, FF3, SoM native including the RAM code in the intro, lockstep equal | 2-2.5 |
| W5 (conditional) | gates and documentation: Zelda artefact byte-identical, `snes_native_zelda_*` green, contract and machine-interface 11 updated | done | 0.5-1 |

Sum: W1-W2 2-2.5 working days. With W3-W5 7-9.5 working days.

---

## 7. What to measure first

1. **Host time share instead of instruction share:**
   - Native build of the ROM blocks per game, then `--stats` on the
     route: interpreter share in clocks and wall time against the pure
     interpreter run. Measured for FF3 in this study (5.1): the
     difference lies below the noise; CT and SoM are missing.
   - For CT and FF3 report the wait loops separately; they distort the
     instruction share.
2. **Parts of the play with battle, menu, world map, Mode 7:**
   - Routes with `WAIT_RAM8` on game mode bytes or from a recording.
   - For CT: reach ChronoRET's self-modifying places in the module (idle
     JSR `$3023`, Mode 7 loop) and count them.
   - The question behind it: is there a part of the play with more than
     about 10 % RAM instructions?
3. **Variants per block** on these routes: the number of byte variants
   and opcode changes decides between "the patch rule is enough" and "a
   fallback is needed".
4. **Cost of the generation counter** for games without RAM code (Zelda,
   Contra III): wall time with and without counting in `Map::write8`.

---

## 8. Side findings

- **FF3 and the table patterns of the discovery.** `snes_recomp` with the
  Zelda table patterns (the default) on the FF3 seeds of the route gives
  319,332 blocks, 1,477,975 instructions, 135,121 stop-opcode diagnostics
  and about 1.1 GB of C in nine files: data is decoded as code. With
  `--no-tables` it is 7,660 blocks and 35,951 instructions (21 MB). The
  survey calls the patterns "not measured" for other games. This has to
  be settled before any FF3 artefact; a follow-up task outside this
  study.
- **CT route.** The survey script reaches the room in 12000 frames, but
  not the stairs. Three blind patterns did not get further. W1 needs
  routes with `WAIT_RAM8`.
- **Limit of the measurement tool.** The source address of CPU stores is
  a heuristic (last data read). It is enough for the conclusions drawn
  here, because the code writers are WMDATA/MVN (exact source). For
  trampolines it partly shows WRAM helper variables.
- **DMA into code ranges** is counted by the tool conservatively as a
  change (value unknown at the time of the `$420B` write). This explains
  part of the "overwritten" bytes in 3.3. The statement "memory reused,
  unpacked again identically" rests on the variants per instruction, not
  on this count.

---

## 9. Not checked

- Battles, menus, world map, Mode 7 scenes, shops, saving, later parts of
  the games (routes too short, CT stays in the room).
- FF IV, FF V, EarthBound and Illusion of Time (the latter has 9 seeds in
  the low mirror according to the survey) were not measured; FF IV and
  FF V are not in the local ROM set.
- Host time share of a native build for CT and SoM. FF3 is measured
  (5.1), but on a machine with other load and with two runs per mode.
- The cost of option A (generation counter, hash) is not measured, only
  taken over from ct-recomp (self-reported +0.38 %).
- Whether the unpacked images are equal between different routes is
  checked only for the common start of the routes.
- The reading of the phases (which program a module is) rests on pictures
  and ChronoRET, not on a disassembly.
- Stage E (exact sequence per bus cycle) was not used; RAM code does not
  depend on the stage, though.
- Weaker target hardware: no run.

---

## Appendix A: local measurement data (not published)

The local measurement tool and its data are not part of any repository.
They hold: the tool itself (section 2) and its evaluation part
(clusters, origin, classes, report); the route extension script and the
three 12000-frame routes (survey script plus the walking pattern, two
failed CT variants); a converter from `img` dumps to contact sheets; raw
data of the 3000-frame and the 12000-frame runs per game (summary,
per-frame table, every variant per instruction, entries, variant log,
DMA table, byte arrays, cluster table, report); the cross-check with
`snes_headless --pc-log`; picture dumps and contact sheets; the trace
excerpts of section 4; and for the native FF3 build the seeds, the
generated C (`--no-tables`), the build and its runs (5.1).
