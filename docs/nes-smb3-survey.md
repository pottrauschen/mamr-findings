# Super Mario Bros. 3: code survey for phase N3

Measurements on the target game (docs/nes-architecture.md section 8,
phase N2, last step) that phase N3 needs before it designs its block
discovery and dispatcher: how much code a run reaches, where it lives,
how control flow leaves the static picture, and how the game uses the
MMC3. Sections 1 to 3 only measure (phase N2); section 4 records what
the discovery and the native runs of phase N3 found.

ROM: Super Mario Bros. 3 (USA) (Rev 1), iNES, mapper 4, PRG CRC32
A0ED7D20, CHR CRC32 C2928C49 (docs/nes-test-evidence.md section 4.4).
Addresses below are CPU addresses with the bank mapped at the time;
`prg:XXXXX` is the byte offset into the 256 KiB PRG ROM (bank = offset /
$2000).

## 1. Method

`nes_headless ROM --frames 3000 --pc-stats FILE [--input SCRIPT]`
(tools/nes_headless/nes_pcstats.cpp) records at every instruction
boundary of the interpreter (stage E):

- the instruction start as PRG ROM offset (below $8000 as CPU address)
  and as block key (bank state, PC) of docs/nes-architecture.md section
  3, where the bank state is `NesMmc3::bank_state()` (PRG mode, R6, R7);
- a block entry wherever the instruction before ended a block
  (`M65Instruction::ends_block`: every control transfer, KIL, a static
  mapper write) or an interrupt entry ran;
- JSR and RTS against a shadow of the return addresses JSR pushed (per
  stack slot): an RTS whose pulled address is the one a JSR pushed there
  is "matched", any other RTS is a computed jump; a JSR site whose
  return never comes back is listed with its target;
- the targets of every JMP (a);
- every CPU write to the mapper ($8000-$FFFF), to the PRG RAM, to $4014
  and to the DMC registers (through `NesBoard::set_write_hook`).

Two runs of 3000 frames from power-on (fill 00): without input (curtain,
title, attract loop of the title screen) and with
`tools/oracle/nes/inputs/smb3-1-1.txt`, not published (menu, World 1 map, World 1-1
for about 900 frames, a fall into a pit, back on the map). The statistics
do not change the run (the hash lines are byte-identical with and
without `--pc-stats`). MAMR runs these frames as MesenCE does except for
the timing findings of docs/nes-oracles.md section 6; the game takes the
same code paths in both (with MesenCE's NMI rule MAMR equals MesenCE in
cpu, ram, vram, pal and inp over all 3000 frames of both runs).

## 2. Results

| quantity | no input | with input |
|---|---|---|
| instructions executed | 28,792,866 | 28,490,205 |
| NMI / IRQ entries | 2989 / 2989 | 2953 / 2948 |
| distinct instruction starts in PRG ROM | 2046 | 11103 |
| instruction starts below $8000 (RAM, PRG RAM) | 0 | 0 |
| distinct keys (bank state, PC) of instruction starts | 2071 | 15774 |
| block entries: keys / PCs / PRG offsets | 627 / 613 / 615 | 4019 / 2699 / 2841 |
| PCs entered under more than one bank state (maximum) | 14 (2) | 590 (21) |
| JSR sites / without return | 89 / 6 | 439 / 19 |
| RTS matched / computed | 114,523 / 0 | 258,509 / 1 |
| JMP (a) sites / targets | 1 / 26 | 7 / 65 |
| PRG RAM writes | 8196 | 124,939 |

**Code in RAM.** None in either run: no instruction starts below $8000,
neither in the internal RAM nor in the 8 KiB PRG RAM at $6000, which the
game writes heavily (level data). This agrees with the literature's
statement that the game copies no routines to RAM; it is a statement
about these two runs, not about the whole game.

**Banks with code** (8 KiB banks, instruction starts / executions):

| bank | no input | with input |
|---|---|---|
| 0 | | 1194 / 1,079,327 |
| 1 | | 144 / 890 |
| 4 | | 367 / 135,679 |
| 5 | | 507 / 84,667 |
| 7 | | 474 / 343,585 |
| 8 | | 1166 / 1,195,020 |
| 10 | | 904 / 423,873 |
| 11 | | 903 / 971,731 |
| 12 | | 197 / 23,087 |
| 14 | | 686 / 28,637 |
| 15 | | 33 / 2649 |
| 24 | 1511 / 26,720,222 | 699 / 1,958,971 |
| 26 | 42 / 39,250 | 679 / 2,047,099 |
| 27 | | 66 / 829 |
| 28 | 57 / 170,373 | 318 / 177,976 |
| 29 | | 282 / 230,098 |
| 30 | 87 / 217,731 | 1410 / 16,626,569 |
| 31 | 349 / 1,645,290 | 1074 / 3,159,518 |

Most executions without input are the wait loop of the title screen in
bank 24 ($A81C `LDA $10` / `BPL $A81C`, waiting for the NMI); with input,
bank 30 (fixed at $8000) carries most of the work.

**Jump tables.** The game dispatches through a routine at $FE99 in the
fixed bank 31 (prg:3fe99): it doubles A into the table index, pulls the
return address of the JSR into $00/$01, loads the table entry through
($00),Y into $02/$03 and jumps indirectly through $0002. The table is
inline: the two-byte entries follow the `JSR $FE99`, and the JSR never returns. Without input 5 such JSR sites
lead to 26 targets, with input 17 sites to 53 targets (all JMP (a)
targets of that run except 12 at six other JMP (a) sites in banks 0, 8
and 29, each with one to five targets).

**Stack tricks.** Besides the dispatcher: a routine at $DEB0 in bank 0
(prg:01eb0) ends with `PLA` / `PLA` / `RTS` on one path, dropping its own
return address and returning to the caller's caller (2 JSR sites without
return); a routine at $A8AF in bank 24 (prg:308af) reinitialises the zero
page and starts the game anew (1 site); and one RTS (bank 30, $9761,
prg:3d761) once returns to an address that no JSR pushed at that slot
(cause not traced). Push-push-RTS dispatch, which the literature
mentions, did not occur in these runs (0 and 1 computed RTS).

**MMC3 use** (with input; the run without input in brackets):

- PRG mode is always 1 (80,028 writes to $8000 with bit 6 set; [38,862]):
  $8000 holds bank 30 fixed, $A000 is R7, $C000 is R6, $E000 bank 31.
- R6 ($C000) values: 00 (7211), 06 (35), 0a (3339), 0e (160), 16 (1),
  19 (219), 1d (5919) [19, 1d]. R7 ($A000) values: 01, 04, 05, 07, 08,
  0b, 0c, 0f, 18, 1a (10,029), 1b, 1c (2953) [18, 1a, 1c].
- CHR registers: R0 and R1 (2 KiB) take 7 values each, R2-R5 (1 KiB)
  4 to 5 values; without input R0, R1, R4, R5 are constant.
- IRQ: one latch write per frame, values $C0 (2736) and $C1 (217) only
  [$C1]; one $C001 reload and one $E000 acknowledge per IRQ, two $E001
  per frame. The latch is never 0, so the difference between MMC3
  revisions A and B at latch 0 (docs/nes-hardware-spec.md sections 3.3
  and 5.3) does not arise in these runs.
- $A000 (mirroring) 5 writes, always 1 (horizontal) [1]; $A001 twice, 00
  then 80 (PRG RAM enabled) [the same].
- One OAM DMA per frame; 6212 writes to the DMC registers [5979].

## 3. What phase N3 can take from it

- The block key (PRG mode, R6, R7) gives 4019 block keys for 2841
  distinct PRG offsets with input: a block in a fixed window (banks 30
  and 31 in PRG mode 1) is keyed once per R6/R7 pair it runs under, up
  to 21 times. A key reduced per window (only the registers that map the
  block's own window) would give one key per offset for fixed-bank code.
- Static discovery must stop after `JSR $FE99` and read the inline table
  instead (entry Y = 2 A at the return address + 1); the entries are the
  targets. The table length is not encoded; the run reaches 53 entries.
- JSR is not always a call with a return: the dispatcher, the
  caller's-caller return and the restart routine discard the return
  slot. A block after a JSR site is only reachable when the callee
  returns, which the discovery cannot assume for these three routines.
- No RAM code: the dispatcher's miss log needs no RAM-code path for this
  game as far as the runs reach; whether later worlds differ is open.
- Instruction starts reached: 11103 of the 262,144 PRG bytes in 18 of 32
  banks after one level; a play-through is needed before the coverage
  means anything for the whole game.

## 4. Phase N3: discovery and native runs

2026-10-26, `tools/nes_recomp` (recompiler/m6502_cfg, key (bank of the
PC's 8 KiB window, PC), docs/nes-architecture.md section 3) and
`nes_headless --cartridge` with the dispatcher's miss log, 3000 frames
from power-on, fill 00, stage E, the same two runs as section 2.

**Key.** The run with input enters blocks at 2841 window keys (`--pc-stats`,
line `blocks window_keys`), exactly the 2841 PRG offsets of section 2,
against 4019 keys under the full bank state: every block is translated
once (docs/nes-architecture.md section 10).

**Round 0: static.** Entries: the three vectors (bank 31 at $E000, the
MMC3's fixed bank); declared fixed: bank 30 at $8000 (`--fixed 0:1E`,
PRG mode 1, section 2). Result: 1010 blocks with 3339 instructions, all
in banks 30 and 31; one inline table behind `JSR $FE99` (19 entries); 108
transfers into $A000-$DFFF, whose bank (R6, R7) is not known statically,
and one JMP (a) the pattern does not cover. Without the declaration
(only bank 31 fixed) 178 blocks with 534 instructions. Native runs on
these blocks equal the interpreter already (every miss is interpreted):

| run | block calls | misses (interpreted instructions) | miss-log entries | interpreted share of the CPU cycles |
|---|---|---|---|---|
| no input | 298,605 | 26,980,657 | 493 | 81,883,771 of 89,339,002 |
| with input | 581,330 | 9,209,144 | 2362 | 29,348,199 of 89,339,008 |

The wait loop of the title (bank 24) runs in the interpreter here, which
is why the run without input interprets most of its cycles.

**Round 1: with the miss log.** The 2662 distinct keys of both miss logs
(`tests/nes/smb3-seeds.txt`, block keys only) as seeds; seeds that are a
later instruction of another block become resume points of that block
instead of cutting it (an RTI or a stop at the frame's sampling point
returns there; a cut would make the title's wait loop leave its function
at every pass). Result: 6898 blocks with 24,696 instructions at 24,685
PRG offsets in the 18 banks of section 2; 30 inline tables with 399
entries in all (the runs used 17 sites with 53 targets: the static walk
reaches more `JSR $FE99` sites, and a table is read until code follows
it, so some entries past the real end may be extra, never-entered
blocks); diagnostics: 302 transfers into a window of unknown bank, one
transfer below $8000 (to $3028 from bank 7, not followed), nine
`JMP ($0000)` the pattern does not cover (banks 0, 8, 29 and 31; their
targets in the runs came through the miss log). Twice as many instruction
starts as the runs execute (11,103): the discovery follows every path of
the blocks it reaches, not only the ones the two runs take.

| run | block calls | misses | stops at the sampling point | interrupt entries (interpreter) |
|---|---|---|---|---|
| no input | 1,012,134 | 0 | 2999 | 5978 |
| with input | 2,648,846 | 0 | 2993 | 5901 |

Both runs are byte-identical to the interpreter in every hash line (all
fields, cyc and dot): ctests `nes_native_smb3_local`,
`nes_native_smb3_input_local`. The tricks of section 2 need no special
case: the `JSR $FE99` tables come from the table pattern, the
`PLA`/`PLA`/`RTS` of $DEB0, the restart at $A8AF and the RTS to a foreign
address at $9761 return through the dispatcher (no C call stack), and
their targets are in the seeds. No code runs below $8000.

Speed (GCC, RelWithDebInfo, the run without input, 3000 frames): the
interpreter 189 frames per second in stage E and 186 in stage S, the
blocks 224 and 233; all four runs give the same hash lines. The board
(the PPU dot by dot, the bus call of every cycle) dominates; phase N3
makes exactly the interpreter's bus calls, so the gain is small, and
the speed of stage S is later work (docs/nes-ppu-spec.md section 14).

The coverage holds for these two runs; later worlds will bring new keys
(the miss log of a longer play-through seeds the next round, and every
miss runs correctly in the interpreter meanwhile).


## 5. The European release (phase P)

Super Mario Bros. 3 (Europe), PRG CRC32 80CD1919, on the PAL machine
(docs/nes-architecture.md section 11; the region from the cartridge
database, the header says NTSC). 2026-10-27, RelWithDebInfo build, stage
E, fill 00, 3000 frames from power-on without input and with
tools/oracle/nes/inputs/smb3-1-1.txt (the USA script; on this ROM it
reaches the map, World 1-1 and a lost life, docs/nes-oracles.md section
8.2).

**The ROM.** The PRG ROM is not the USA one with other timing constants
patched in: 32,447 of its 262,144 bytes differ from the USA Rev 1 PRG,
and only one of the 32 8 KiB banks (bank 6) is identical. The code is
the same game rebuilt; the structure of section 2 holds: the MMC3 in
PRG mode 1 with bank 30 at $8000 and bank 31 at $E000, the inline jump
tables behind a JSR that consumes its return address, the vectors in
bank 31 (NMI $F486, reset $FF40, IRQ $F77B). MMC3 IRQ latch writes
($C000): $C0, $C1 and $FF (2741, 218 and 2959 with input; 2991 $C1 and
2991 $FF without), never 0, so the revision question of
docs/nes-hardware-spec.md section 5.3 does not arise either. The run with
input enters blocks at 2728 window keys, the run without at 622.

**Discovery** (`tools/nes_recomp/nes_rounds.py --fixed 0:1E` with both
runs and `--interp-check`): round 0 from the vectors and the declared
bank gives 1023 blocks with 3353 instructions (one inline table, 19
entries; 108 transfers into a window of unknown bank); its native runs
miss 30,226,737 and 8,086,191 instructions (493 and 2236 miss-log
entries). Round 1 with the 2729 keys of both miss logs as seeds
(`tests/nes/smb3-eu-seeds.txt`): 6882 blocks with 24,636 instructions, 30
inline tables with 399 entries; both runs miss nothing and equal the
interpreter in every hash line (all fields, cyc and dot). The artefact
`smb3-eu.mamrcart` is built by tests/nes from the local ROM and these
seeds (`nes_local_cartridge`); ctests `nes_native_smb3_eu_local`,
`nes_native_smb3_eu_input_local`.

**Speed** (the run without input): the interpreter 191 frames per second,
the blocks 235 (1,300,224 block calls, 0 misses, 41,867 interpreted cycles
of the interrupt entries), at 50 frames per second needed.
