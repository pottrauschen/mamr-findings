# SNES code in RAM: measurement, key figure, decision

Three of the SNES games in the local set run part of their program from
WRAM: Chrono Trigger (USA), Final Fantasy III (USA) and Secret of Mana
(Europe). The block dispatcher keys blocks by PB:PC in the static ROM
map only (docs/snes-architecture.md section 3), so that code runs in the
interpreter, the reference of the machine, and the ROM code around it in
blocks. This file records how much that is, how it is measured and
gated, and why it stays so for version 1. It covers phases W1
(measuring tool, routes, table) and W2 (native game artefacts of the
three games with the RAM code interpreted) of the WRAM study of
2026-10-27; the study's options for translating RAM code (content keys
with page generations, ABI section `MAMR_CODE_W65816_WRAM_BLOCKS`) are
not built (section 7).

Provenance: every number here is MEASURED-EMU (MAMR stage S, the
interpreter, MAMR as of 2026-10-27), never a hardware claim.

## 1. What the game does with WRAM

From the study, confirmed by the writer record of section 2 on the
routes of section 3:

- **Unpacked, not copied.** Chrono Trigger and Final Fantasy III unpack
  an LZ-packed module into WRAM: literals through WMDATA ($2180) and
  back references by MVN (CT) or WMDATA only (FF3). Secret of Mana
  unpacks with a small MVN unpacker that itself runs in low RAM
  ($7E:01C9-01F6, copied there from $C1:4C07 and patched by ROM code).
  The large routines are not byte sequences of the ROM; only stubs of
  4 to 46 bytes are.
- **Fixed content.** Of 1068 (CT), 2122 (FF3) and 7587 (SoM) keys
  (address, M, X) executed on the routes, 3, 2 and 21 saw more than one
  byte sequence, and only in SoM did an opcode change (15 keys: the
  unpacker stub and generated MVN stubs; section 4 of the study). The
  modules share their memory with data and are unpacked again,
  identically, before use.
- **Trampolines.** The NMI and IRQ vectors go through WRAM in all three
  ($7E:0500 CT, $7E:1500/1504 FF3, $7E:0100/0104 SoM): one interpreted
  instruction per interrupt.
- **Wait loops.** Most RAM instructions are a busy-wait: in CT 62 % of
  them are the idle loop at $7E:3023 (`JSR $3176` / `RTS`), in FF3 74 %
  the loop at $7E:7206 (`LDA` / `BNE`), on the routes of section 3.

## 2. Measuring tool: snes_headless --ram-stats

`snes_headless ROM --frames N --ram-stats FILE [--ram-frames FILE]`
(tools/snes_headless/snes_ram_stats.{h,cpp}) counts every instruction
the interpreter starts (the `W65816Cpu::on_interp` hook) and writes:

- **one text line** on stderr at the end (next to `--stats`),
- **a JSON report** in FILE (`"format": "mamr-ram-stats 1"`; `-` for
  the line only),
- with `--ram-frames` **one CSV row per frame**: `frame, insns,
  outside_rom, wram, wram_mirror, sram, other, outside_percent`.

Definitions:

| Item | Definition |
|---|---|
| instruction | one interpreter unit: an instruction, MVN/MVP per byte moved (the interpreter's own unit; `--stats` counts the same) |
| region | of PB:PC on the cartridge's board (`map_decode`): ROM, WRAM ($7E-$7F), WRAM mirror (low 8 KiB in banks $00-$3F/$80-$BF), SRAM, other (I/O, open bus) |
| share outside ROM | instructions outside ROM / all instructions, in percent |
| key | (region, address, M, X, E); for WRAM and the mirror the address is the WRAM offset |
| variant | a distinct byte sequence of the instruction at a key, read from memory when it executes (length from the opcode and M/X) |
| cluster | a run of executed WRAM bytes, gaps of up to 16 unexecuted bytes joined (the study's convention) |
| writer | of each executed WRAM byte, who wrote it last before its first execution: CPU store, block move (MVN/MVP), WMDATA ($2180) written by the CPU, GP-DMA, none (power-on) |
| miss entries by region | the CPU's miss log (`--miss-log`) by region of the address: a native run's ROM entries are blocks the artefact lacks |

The writer record wraps the system's CPU bus `write8` (it calls the
original with the same arguments) and derives GP-DMA writes from the
channel registers at the `$420B` write: A-bus to WMDATA, or B-bus into a
WRAM address. HDMA into WMDATA is not followed (none of the three games
was seen doing it). It runs in stage S without blocks only; with
blocks the counts are those of the interpreted instructions (the report
says `"mode": "native"`), in stage E the writers are left out.

Checks:

- ctest `snes_ram_stats` (tests/snes-system/test_snes_ram_stats.cpp): a
  synthetic LoROM image writes four routines into WRAM, one per writer
  (CPU stores, WMDATA, GP-DMA into WMDATA, MVN), patches an operand of
  one and an opcode of another and calls them, one also through the
  mirror; every count, cluster and writer is checked exactly, the run
  with the bus wrapper equals the run without it, and a run with blocks
  on and none registered classifies its miss log by region.
- Against the study's own tool: Final Fantasy III over the study's
  12000-frame route gives the study's numbers exactly (169,737,305
  instructions, 15,265,644 in WRAM) and hash lines byte-identical to the
  study's `--interp-only` run; Chrono Trigger over the survey script,
  3000 frames: 39,072,807 instructions, 27.918 % outside ROM (study:
  27.9 %).
- Zelda (null probe): no instruction outside ROM (survey scripts,
  3000 frames: Germany 47,682,784 instructions, USA 38,923,652).

## 3. Routes

Pad scripts in the shared input format (docs/snes-oracle-input-script.md,
one step per auto-joypad read), from power-on:

| Route | Frames | Reaches |
|---|---|---|
| tests/snes-system/ct-route.txt | 9100 | title and attract, battle mode and name, the world-map flyover of the intro (Mode 7), Crono's room with the dialogue, the menu (X), the stairs and the ground floor, the world map |
| tests/snes-system/ff3-route.txt | 14700 | title, opening text, the Magitek march, the cliff, Narshe, the battle against the guards, the field after it, the menu (X) |
| tests/snes-system/som-route.txt | 9300 | title and game select, the opening text and scenes, the river flyover (Mode 7), the log bridge and the fall, the waterfall basin, the river and the meadow to the south-west |

How they were made: fixed read counts, found on MAMR stage S with save
states between the steps and checked picture by picture, then checked
again in one run from power-on. `WAIT_RAM8` is in the format but is not
used: no RAM map of these games was verified for this work, and a
condition on a guessed byte is worse than a count that is exact in every
runner that steps the script per auto-joypad read (MAMR and the
oracles). A runtime change that moves a game's input reads would move
the route; the gates of section 5 compare native and interpreter on the
same script and do not depend on reaching a scene.

Not reached: a battle in Chrono Trigger (the first one is Gato at the
fair, Leene Square), a Mode 7 scene of Final Fantasy III's game (the
airship), and in Secret of Mana the sword, the first enemies (Rabites)
and the ring menu (it does not open before the sword). Weapons, shops,
saving and later chapters are not on any route.

## 4. Table: share of instructions outside ROM

Interpreter run of each route (`--ram-stats`, `--ram-frames`); the frame
ranges are where the part shows on the pictures. "Attract" is a separate
run of 3000 frames without input. Peak: the largest share of a single
frame in the range.

| Game | Part | Frames | Outside ROM | Peak frame |
|---|---|---|---|---|
| CT | title and attract | 1-1300 | 75.6 % | 100 % |
| CT | intro: world-map flyover (Mode 7) | 1950-3600 | 0.006 % | 0.0 % |
| CT | field: room and dialogue | 4600-6090 | 0.014 % | 0.0 % |
| CT | menu | 6140-6190 | 0.006 % | 0.0 % |
| CT | field: stairs, ground floor | 6200-8050 | 0.020 % | 13.1 % |
| CT | world map | 8100-9100 | 0.006 % | 0.0 % |
| CT | whole route | 1-9100 | 8.34 % | |
| CT | attract without input | 1-3000 | 51.4 % | |
| FF3 | title | 1-1500 | 58.0 % | 100 % |
| FF3 | opening text, Magitek march, cliff | 1501-10500 | 1.27 % | 100 % |
| FF3 | field: Narshe | 10550-11450 | 0.014 % | 0.0 % |
| FF3 | battle (guards) | 11650-13200 | 0.007 % | 0.0 % |
| FF3 | field after the battle | 13300-14050 | 0.015 % | 0.0 % |
| FF3 | menu | 14085-14205 | 0.007 % | 0.0 % |
| FF3 | whole route | 1-14700 | 7.01 % | |
| FF3 | attract without input | 1-3000 | 86.7 % | |
| SoM | title and game select | 1-1500 | 62.7 % | 100 % |
| SoM | opening text and scenes | 1550-4750 | 0.006 % | 0.0 % |
| SoM | river flyover (Mode 7) | 4800-5250 | 5.63 % | 93.5 % |
| SoM | log bridge, dialogue | 5400-7350 | 0.006 % | 0.0 % |
| SoM | field: basin, river, meadow | 7450-9300 | 0.006 % | 0.0 % |
| SoM | whole route | 1-9300 | 9.93 % | |
| SoM | attract without input | 1-3000 | 97.7 % | |

The rest of the route-wide figures (route runs):

| | CT | FF3 | SoM |
|---|---|---|---|
| instructions | 131,035,206 | 207,569,370 | 154,181,510 |
| outside ROM: WRAM / mirror / SRAM / other | 10,910,332 / 12,619 / 0 / 0 | 14,531,649 / 24,979 / 0 / 0 | 14,550,279 / 764,202 / 0 / 0 |
| keys / with more than one byte sequence / with another opcode | 1068 / 3 / 0 | 2122 / 2 / 0 | 7587 / 21 / 15 |
| executed WRAM bytes, clusters, largest cluster | 2357, 22, 445 bytes at $7E:5B99 | 4696, 20, 597 bytes at $7E:57F3 | 13506, 73, 1431 bytes at $7E:992B |
| writers at first execution (bytes) | WMDATA 1201, MVN 1144, CPU 12 | WMDATA 4688, CPU 8 | MVN 13403, CPU 103 |
| hottest key | $7E:3023 JSR, idle loop | $7E:7206 LDA, idle loop | $7E:A2AE LDA |

What it says: the RAM code is the title, the attract mode and parts of
the intro: FF3 runs its module again in the black screen between the
cliff and Narshe (frames 10214-10373 of the route), SoM during the river
flyover; CT's one frame of 13 % in the house is the name entry opening
(frames 7072-7073). Every part of the play measured here,
battle and menu included, stays at or below 0.02 %: the trampolines and
a few calls. The study's question for phase W3, a part of the play with
more than about 10 % RAM instructions, is answered no for every part the
routes reach. The attract runs without input are the worst case (51 to
98 %) and are a demo loop, not play.

## 5. Key figure and native artefacts (W2)

**Key figure "interpreted share":** the instructions a native run of
the game artefact leaves to the interpreter, divided by the
instructions of the interpreter run of the same script. It is the share
outside ROM of section 4 plus the reset instructions in emulation mode
(2 or 3 per run, no block exists for E=1), because with no ROM miss
every ROM instruction runs in a block. The gate checks that identity:
the native run's interpreted instructions outside ROM equal the
interpreter run's.

**Build chain** (the one of Contra III, docs/snes-rom-survey.md section
4):

1. Three interpreter runs per game with `--miss-log`: the route of
   section 3, 3000 frames without input, and the survey script
   tests/snes-oracle/scripts/<id>.txt over 3000 frames.
2. `snes_recomp ROM --out <id>_blocks.cpp --no-tables --parts 4 --seeds
   <route> --seeds <none> --seeds <survey>`. `--no-tables` is needed:
   with the table patterns of docs/snes-zelda-authority.md the static
   discovery decodes data as code (from the vectors alone 209,470
   blocks for CT and 281,967 for FF3; SoM, whose vectors point into
   WRAM, is not affected). The WRAM seeds of the miss logs end as
   "no-code" targets and are dropped.
3. A build tree per game, `-DMAMR_SNES_BLOCKS_CPP=<the five files>
   -DMAMR_SNES_CARTRIDGE_NAME=<id> -DJF_WITH_SDL=OFF`, target
   `mamr_cartridge` (and `snes_headless_native`); about 4 minutes each
   with `-j4`.
4. The artefact as a copy stripped of debug information (`strip
   --strip-debug`), with SHA256SUMS, as for the arcade artefacts.

| | CT | FF3 | SoM |
|---|---|---|---|
| seed entries (route + none + survey) | 10,774 | 11,357 | 13,045 |
| blocks / instructions | 12,729 / 57,665 | 14,168 / 61,787 | 13,790 / 56,724 |
| no-code targets (WRAM, mirror) | 266 (251, 2) | 522 (509, 2, open bus 1) | 2184 (2039, 58) |
| unknown width / indirect sites / stop opcodes | 7 / 72 / 22 | 14 / 85 / 58 | 9 / 33 / 32 |
| artefact `<id>.mamrcart` (stripped) | 19,985,200 bytes | 21,565,168 bytes | 19,823,568 bytes |
| exports, needed | `mamr_cartridge`, libc | `mamr_cartridge`, libc | `mamr_cartridge`, libc |

The cartridge database already had the three releases by SHA-1 (HiROM,
SoM PAL; SRAM size from the header) and tests/snes/test_snes_rom.cpp
checks their rows; nothing changed there, and the header fallback for
unknown ROMs stays as strict as for Contra III.

**Gates** (`snes_headless --cartridge FILE` loads the artefact into the
interpreter build; tests/snes-system/compare_native.py with
`--cartridge`, `--max-rom-misses 0`, `--ram-report`):

| Run | F lines | miss entries ROM / WRAM / mirror | interpreted share | wall time native / interpreter |
|---|---|---|---|---|
| CT route, 9100 frames | equal | 0 / 208 / 5 | 8.336 % (10,922,954 of 131,035,206) | 60.2 s / 68.1 s |
| CT attract, 3000 frames | equal | 0 / 252 / 3 | 51.42 % | 21.0 s / 21.7 s |
| FF3 route, 14700 frames | equal | 0 / 455 / 6 | 7.013 % (14,556,631 of 207,569,370) | 99.6 s / 108.9 s |
| FF3 attract, 3000 frames | equal | 0 / 323 / 1 | 86.66 % | 22.3 s / 21.2 s |
| SoM route, 9300 frames | equal | 0 / 1786 / 59 | 9.933 % (15,314,483 of 154,181,510) | 61.4 s / 65.9 s |
| SoM attract, 3000 frames | equal | 0 / 1987 / 54 | 97.66 % | 22.2 s / 21.5 s |

Every F line of the native run equals the interpreter's, no block is
missing in ROM, and the native run interprets exactly the interpreter
run's instructions outside ROM plus the 2 or 3 reset instructions in
emulation mode. Wall times: one run each, the same binary, on a host
shared with other build and test jobs; on the routes the artefact saves
7 to 12 %, on the attract runs (mostly RAM code) nothing measurable.

ctests (label `local`, skip without the ROM or the artefact): per game
`snes_native_<id>_route_local` and `snes_native_<id>_attract_local`, ids
`ct`, `ff3`, `som`; the artefacts come from the folder
`SNES_JRPG_CARTRIDGES`, the ROMs from `SNES_CT_ROM`, `SNES_FF3_ROM`,
`SNES_SOM_ROM` (default `roms/snes/<No-Intro name>.sfc`). The test log
prints the share per part of the route.

Front end: `check_play_roundtrip.py` with `--play-arg --cartridge` over
600 frames, state at 300, is ok for all three (picture and audio equal
to machine_hash in the interpreter, frames 301-600 repeated from the
state file), and `mamr_play --cartridge auto` finds each artefact by the
ROM's SHA-1 in the cartridge folder.

**Against the oracle** (aresref, `compare_oracle.py`, both stages, 3000
frames of each route, docs/snes-oracles.md section 10): Chrono Trigger
equal in every field in stage S and stage E; Final Fantasy III differs
in `smp` only, from frame 21 (the S-SMP timer 2 rule, survey finding
F6); Secret of Mana in `img` only, from frame 1062 in 243 frames (the
mode 5 picture of the intro, survey finding F8, cause open). The first
3000 frames of the routes use the survey scripts' input up to their
last command, and the findings are the survey's, frame for frame. The
gate of the artefacts is native equal to the interpreter, which holds
in every case.

## 6. Decision and reasons

RAM code stays in the interpreter for version 1 (option D of the
study), measured and gated:

1. **Little to gain in play.** On every part of the play reached, at
   most 0.02 % of the instructions run from RAM; the large shares are
   the title, the attract mode and intro sequences.
2. **The content is unpacked.** Translating it statically needs either
   a capture run of the unpacked image or an unpacker per game, plus a
   validity check at run time because the memory is reused and stubs
   are patched (option A with page generations, 5 to 7 working days, a
   possible ABI version 3).
3. **The interpreter is the reference** and is not the bottleneck: the
   machine time is in the PPU, DMA/HDMA and the S-SMP (section 5: the
   native artefacts save 7 to 12 % of the wall time of a route against
   the pure interpreter, and nothing measurable where RAM code
   dominates).
4. **It is honest and gated.** The share is a number in every gate run
   (ctest output), and a ROM miss fails the gate, so "native" means:
   all ROM code in blocks, all RAM code in the interpreter, nothing
   else.

Revisit (phase W3 of the study) when a route shows a part of the play
with more than about 10 % RAM instructions, or when "100 % native"
becomes a goal of its own. The ABI reservation
`MAMR_CODE_W65816_WRAM_BLOCKS` stays.

## 7. Not done

- Phases W3-W5 (content keys with page generations, capture run,
  emitter rules, ABI section 2 or version 3).
- The table patterns of docs/snes-zelda-authority.md on these games:
  with them the static discovery decodes data as code (section 5).
- `WAIT_RAM8` conditions in the routes (section 3).
