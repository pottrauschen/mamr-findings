# Arcade oracles: Ikari Warriors and R-Type against MAME

The judge for Ikari Warriors and R-Type is MAME 0.285 (the Ubuntu
package on the development machine), running the sets `ikari` and
`rtype`, plus a patched build of the same version, "mameref" (section 2).
This document covers the kit in `tools/oracle/arcade/` (section 3), the
MAME-faithful scheduling stage of both machines that the lockstep runs
(stage M, sections 4 and 5), every deviation found and its cause
(section 6), the gates and their results (section 7), the decision on the
judge for the V30 (section 8), what the results allow MAMR to claim
(section 9) and the runs against mameref (section 10). The line format is
[arcade-oracle-format.md](arcade-oracle-format.md); the hardware facts are
[hardware-spec.md](hardware-spec.md) and
[ikari-timing-reference.md](ikari-timing-reference.md) for Ikari,
[rtype-hardware-spec.md](rtype-hardware-spec.md) for R-Type. The method is
the one of the Super Pang kit ([spang-oracles.md](spang-oracles.md)).

Provenance classes (MEASURED, SCHEMATIC, MAME, HACK/ASSUMPTION, UNKNOWN,
IMPLEMENTATION, MEASURED-EMU) are those of ikari-timing-reference.md. A
MAME run is MEASURED-EMU: evidence about MAME, never about the board.
Citations `MAME <path>:<line>` refer to the tag mame0285; every MAME file
cited is BSD-3-Clause.

## 1. Summary

| | Ikari Warriors | R-Type |
|---|---|---|
| hash line, MAME writer and headless writer | `ikari_mame.lua`, `ikari_headless --hash` | `rtype_mame.lua`, `rtype_headless --hash` |
| MAME determinism (two runs) | byte-identical, 3000 frames | byte-identical, 3000 frames |
| stage M against MAME 0.285, attract mode | every field equal, 3000 frames, picture included | every field equal, 3000 frames, except the picture in frames 117-193 (finding F6) |
| stage M against MAME 0.285, replay | every field equal, all 112,000 frames of the bot game (picture not compared) | every field equal, 10,000 frames of stage 1, picture included, except frames 117-193 (F6) |
| stage M against mameref (section 10) | every field equal (mode `cycle`): 3000 attract frames with the picture, 112,000 frames of the bot game | every field equal (mode `mameref`), picture included without skipped frames: 3000 attract frames, 10,000 frames of stage 1 |
| stage S (the game) against MAME 0.285 | first divergence frame 1 (`clkb`), section 7.2 | first divergence frame 53 (`clkm`), section 7.2 |
| stage S against mameref | first divergence frame 1 (`clkb`), fewer fields and frames differ (section 10.3) | every main CPU field equal (`clkm`, `v30`, memory, video, picture) over 3000 attract frames and 10,000 frames of stage 1; the sound side differs from frame 284 (section 10.3) |
| the MAME findings | F1-F5, F9 | F2, F5-F10 |

Stage M is MAMR's chips under MAME's scheduler. That it equals MAME in
every field means: on the code these runs execute, MAMR's CPU semantics,
bus decoding, video, sound chip registers, interrupt logic and the clock
tables give MAME's results exactly (the V30 instructions where MAMR
follows SST v20 instead of MAME, rtype-hardware-spec.md section 9, do not
change the state in these runs), and every difference between the game
build (stage S) and MAME comes from how the CPUs and events are
interleaved in time. Section 6
sorts those differences into MAME artefacts (the judge is wrong about the
board) and MAMR simplifications.

## 2. The judge: MAME 0.285 and mameref

MAME 0.285 is the judge as installed (`mame -version`: 0.285). MAME is
not ground truth for the board (ikari-timing-reference.md, Decision);
where it is known to differ from the board, a patch for mameref states
the board's behaviour instead. The patches are in
`patches/mame/`, each a few lines of BSD-3-Clause MAME
sources:

| patch | file | change | finding |
|---|---|---|---|
| 0001-ikari-cycle-interleave | src/mame/snk/snk.cpp | perfect quantum on CPU A instead of 1/6000 s (`MAMEREF_IKARI_STOCK_QUANTUM` restores the original) | F1, F3 |
| 0002-m72-palette-from-ram-at-start | src/mame/irem/m72_v.cpp | every pen black at video start instead of the palette device's rainbow | F6 |
| 0003-nec-rep-continuation-no-double-charge | src/devices/cpu/nec/necinstr.hxx | a REP continued in the next time slice does not charge its 2 start-up clocks again | F7 |

`tools/oracle/mame/build_mameref.sh [--fetch] MAME_DIR` clones the tag
(commit f379cd06), applies the patches once (stamp file) and builds only
the two drivers (`SUBTARGET=mameref SOURCES=src/mame/snk/snk.cpp,
src/mame/irem/m72.cpp`); the binary is `MAME_DIR/mameref`, given to the
kit as `MAME=MAME_DIR/mameref`. All three patches apply to 0.285
(`git apply --check`). **Status: built** on the development machine
(`mameref -version`: 0.285 (mame0285-dirty); `-listfull` holds the snk.cpp
and m72.cpp sets, among them `ikari` and `rtype`; the stamp's checksum is
that of `patches/mame/`). Stage M has a mode that predicts mameref for each
game (Ikari `cycle`, R-Type `mameref`, sections 4 and 5); the gates run
against either judge (section 7.1), the results against mameref are
section 10.

## 3. The kit

| file | purpose |
|---|---|
| `run_mame.sh SET OUT [FRAMES]` | MAME headless with a private work directory (fresh cfg and nvram), the ROM path prepared by `romset.py`, `SET_mame.lua` as autoboot script; exit 2 without MAME or ROM |
| `ikari_mame.lua`, `rtype_mame.lua` | the hash line writers, replay input, dumps, access log |
| `romset.py` | links the set's files under MAME's names, found by SHA-1 from `mame -listroms` |
| `afh.py` | reference implementation of the format: `verify`, `fline` (a line from dumps), `selftest` |
| `compare.py` | `lines` (frame by frame per field, `--skip-field F:LIST`), `regs` (register diff of one frame), `dumps` (byte offsets), `acclog` (first differing access) |
| `gates.py` | `determinism`, `lockstep` (`--stage-m`: Ikari `stock`/`cycle`, R-Type `stock`/`mameref`), `z80steps` (section 7) |
| `z80steps.py` | the Z80 step plans of MAME's z80.lst (`dump`, `emit` writes `runtime/z80_steps_table.inc`, `check` against the SingleStepTests z80 cycle traces) |

```text
tools/oracle/arcade/run_mame.sh ikari m.hash 3000
FH_REPLAY=tests/data/ikari-full-game/full_game.replay tools/oracle/arcade/run_mame.sh ikari m.hash 112000
ikari_headless --frames 3000 --stage-m stock --hash r.hash [--no-img] [--replay FILE]
rtype_headless --roms roms/rtype --frames 3000 --stage-m [mameref] --hash r.hash [--replay FILE]
tools/oracle/arcade/compare.py lines m.hash r.hash [--skip-field img:117-193]
```

The replay file under tests/data/ikari-full-game is local and not
distributed (a MAME bot game, see ikari-timing-reference.md MEAS-4).

`FH_IMG=1` adds the picture to a MAME run (MAME then draws every frame);
the headless runners hash it unless `--no-img`. MAME is deterministic for
both sets: two runs of 3000 frames give byte-identical files (gates
`ikari_oracle_determinism`, `rtype_oracle_determinism`).

**Mid-instruction stops** (finding F2 of the Super Pang kit). MAME's Z80
runs an instruction as a list of steps (`MAME src/devices/cpu/z80/z80.lst`,
expanded by z80make.py) and checks its cycle budget after every step, so
a time slice, and the frame notifier, can end inside an instruction. The
format samples the registers at the next instruction start and the memory
at the notifier (arcade-oracle-format.md section 3.1); stage M stops
where MAME stops. The steps are derived from the listing by
`z80steps.py` and checked against the SingleStepTests z80 cycle traces
(1604 files, 1,604,000 tests: every test's length and the start cycle
and kind of every bus access match a variant; gate
`arcade_oracle_z80steps`).

## 4. Ikari stage M

`games/ikari/ikari_stage_m.h` runs the machine as MAME 0.285's scheduler
does (`MAME src/emu/schedule.cpp:393` timeslice, `src/emu/diexec.cpp`,
`src/mame/snk/snk.cpp`):

- time slices from the base time to the next timer or base + quantum;
  CPU A, CPU B and the sound CPU in device order run every step that
  starts before the slice end, the cycle count with MAME's shifted
  divisor (`runtime/mame_time.h` MameDivider); a CPU that ends early moves
  the slice end back for the CPUs after it (`schedule.cpp:490`);
- timers: VBLANK start (n * 16,666,666,666,666,666 attoseconds, then the
  frame notifier and the VBlank interrupts), VBLANK end, the sound
  manager's 50 Hz update, the YM3526 timers;
- every line change, the sound latch and the sound status go through
  `scheduler().synchronize()` (`schedule.cpp:634`), a zero-length timer
  fired after the slice; input lines through the per-line event queue of
  `diexec.cpp:663` set_state_synced (only the first event of an empty
  queue starts a timer). A CPU whose access puts a timer at the head of
  the list stops after that access step;
- YM3526 samples counted at MAME's integer stream rate
  (`Ym3526::mame_sample_count`, finding F4);
- quantum "stock" (1/6000 s, `snk.cpp:4254`) or "cycle" (one CPU A cycle,
  the mameref patch 0001).

Bus accesses happen at the start of their step (MAME: "N !! access"),
not at the start of the instruction as in stage S. `ikari_headless
--stage-m stock|cycle`; 600 frames take 0.80 s (stock) and 1.91 s
(cycle) against 0.55 s in stage S (MEASURED-EMU, gcc RelWithDebInfo).

## 5. R-Type stage M

`games/rtype/rtype_stage_m.h` does the same for the M72 board (`MAME
src/mame/irem/m72.cpp` and its devices):

- the quantum is 1.5 us (12 V30 clocks) for the first 25 seconds
  (`m72.cpp:227-231` synch_callback, `add_quantum(MASTER_CLOCK/4/12, 25 s)`),
  1/60 s afterwards; the V30 first, then the sound Z80;
- the V30 runs whole instructions and REP iterations while its budget
  lasts; a REP left at a slice end continues in the next slice through
  `cont_rep` (`MAME src/devices/cpu/nec/necinstr.hxx:19-35`), which
  charges the REP's 2 start-up clocks again (finding F7); the Z80 runs
  steps as for Ikari;
- timers: VBLANK start, the line timer of scanline_interrupt
  (`m72.cpp:256`), the sound update, the YM2151 timers and pic8259's
  zero-length output timer;
- synchronised: the sound latch, the RST buffer inputs
  (`MAME src/devices/machine/rstbuf.cpp`), the reset and INT lines of the
  sound CPU, the INT line of the V30, the YM2151 mode register;
- the sound CPU held in reset eats its cycles; a release resets PC, WZ,
  I, R and the interrupt flip-flops only (`MAME
  src/devices/cpu/z80/z80.cpp` device_reset);
- mode "stock" (MAME 0.285) or "mameref": a REP continued in the next
  slice does not charge its 2 clocks again (patch 0003). The V30 runner
  then runs that continuation without the 2 clocks in the budget check,
  the clock count and the prefetch accounting, as the patch takes them
  out of `m_icount` and `m_cur_cycles` (`V30Cpu::rep_cont_charge`): in a
  block when the blocks carry the mark of code kind 8 (the runner sets
  `V30_REP_CONT_FREE` in `rep_params` just before the call, the block
  clears it and passes `charge = false` to `v30_rep`), else in the
  interpreter (`v30_exec`). `V30State` keeps its layout (cartridge ABI 2,
  docs/machine-interface.md section 10). mameref's black start
  palette (patch 0002) needs nothing: MAMR takes the colours from the
  palette RAM, which is zero at power-on.

`rtype_headless --stage-m [stock|mameref]`. A V30 instruction trace of 3,676,169
instructions (320 frames, MAME 0.289 kit trace `v30long`) is matched
instruction by instruction, including 976,402 REP continuations, with no
resynchronisation.

## 6. Findings

### 6.1 MAME findings (the judge differs from the board, or is a model choice)

| id | finding | MAME | board | class | effect on the comparison | handled by |
|---|---|---|---|---|---|---|
| F1 | CPU A and B run in 1/6000 s slices; one sees the other's shared RAM writes only at slice ends | `snk.cpp:4254` set_maximum_quantum(6000 Hz) | one clock, one shared bus: every write visible at its bus cycle (SCHEMATIC, ikari-timing-reference.md section 9) | MAME (model) | stage M stock against stage M cycle over 3000 attract frames: bg 105 frames (the power-on test screen 211-301), spr 2821, img 298, clkb 2912 (MEASURED-EMU) | stage M stock reproduces it; mameref 0001 removes it |
| F2 | the Z80 stops inside instructions at slice ends and at the frame notifier | z80.lst steps | the chip has no slices | IMPLEMENTATION | registers and memory at the notifier belong to different moments | the format's sampling point; stage M stops where MAME stops |
| F3 | line changes, latch and status writes take effect at the end of the current slice (synchronize, event queues) | `schedule.cpp:634`, `diexec.cpp:663` | wires: immediately (SCHEMATIC) | MAME (model) | delays of up to one quantum (Ikari 1/6000 s, R-Type 12 clocks) | stage M reproduces it; with 0001 one CPU A cycle |
| F4 | the YM3526 stream runs at an integer sample rate, which shifts timer B's phase | `MAME src/emu/sound.cpp:297` (u32 sample rate) | the chip divides its own clock by 72 exactly, while MAME's integer rate lags by about 0.56 samples per second; the prescaler's phase at power-on is UNKNOWN (hardware-spec.md section 7) | MAME (model) | the sound CPU's YM status reads and the I/O sequence drift (first in frame 350 of the attract mode) | `--mame-sample-count`; stage M always counts as MAME |
| F5 | Z80 power-on registers: all 0, IX = IY = 0xFFFF, F = 0x40 | `z80.cpp:685-695`, `z80.cpp:720-721` | undefined (UNKNOWN) | HACK/ASSUMPTION | registers of frame 1 | MAMR takes MAME's values (all three Ikari CPUs, R-Type's sound CPU) |
| F6 | the palette device starts as a rainbow; R-Type's pens the program has not written yet show it | `MAME src/emu/dipalette.cpp:379-381` | palette RAM content at power-on not known (UNKNOWN) | MAME (model) | img of R-Type frames 117-193 (boot test screen), 73 frames in each run; confirmed by drawing MAMR's picture with MAME's start-up colours, which removes every difference | `--skip-field img:117-193` against MAME 0.285; mameref 0002 removes it (section 10) |
| F7 | a REP continued in the next slice charges its 2 start-up clocks again | `necinstr.hxx:19-35` with `do_rep*` CLK(2) | the chip has no slices | MAME (artefact) | 459 REP instructions of the boot split into 976,402 pieces, 1,952,804 extra clocks in 320 frames (6522 per frame in the boot, about 338 per frame in the game); R-Type stage S diverges from frame 53 | stage M stock reproduces it; mameref 0003 removes it, stage M mode `mameref` follows (section 10); stage S had the same charge at its own split points (E7) |
| F8 | pic8259 differs between 0.285 and 0.289: OCW3 read selection encoding, IRR cleared on ICW1 | `MAME src/devices/machine/pic8259.cpp` | uPD71059 data sheet (SCHEMATIC) | IMPLEMENTATION | the raw `m_ocw3` and `current_level` are version-specific | the `pic` field holds the read selection's meaning (format section 4.1) |
| F9 | Ikari's frame is HZ_TO_ATTOSECONDS(60) without raw screen timing | `snk.cpp:4258` set_refresh_hz(60) | frame length and VBLANK position not measured (UNKNOWN, ikari-timing-reference.md section 12) | MAME (model) | every VBLANK time | stage M uses MAME's truncated period |
| F10 | the V30 timing is a table model (section 8) | `MAME src/devices/cpu/nec/` | not measured | MAME (model) | every V30 clock count | section 8 |

### 6.2 MAMR deviations found and fixed

| id | deviation | evidence | class of the fix | stages |
|---|---|---|---|---|
| E1 | the VBlank interrupt was raised at the start of every frame, also at power-on (one INT more than MAME before the first VBLANK) | Ikari frame 1 irq | MAME (VBLANK start n is n frame periods after power-on; the board's first VBLANK is UNKNOWN) | all (with the first Ikari hash line writer) |
| E2 | the frame thresholds not computed with MAME's truncated cycle periods | clka/clkb/clks of frame 1 | IMPLEMENTATION (MAME's arithmetic, `runtime/mame_time.h`) | M |
| E3 | bus accesses at the start of the instruction | the access log against MAME's (`compare.py acclog`) | SCHEMATIC (Z80 M-cycle timing, Zilog UM0080) and IMPLEMENTATION (SST z80 cycle traces, z80.lst) | M (stage S keeps the instruction start, E3 is open there) |
| E4 | EX (SP),HL/IX/IY wrote the low byte first | R-Type snd, 2 bytes on the sound CPU's stack; the SST z80 bus order check (`sst_runner`, "exec bus access order") | SCHEMATIC (Zilog UM0080: SP+1 written first) and IMPLEMENTATION (SST, MAME) | all (`runtime/z80_ops.h`) |
| E5 | R-Type's line event was taken before the VBLANK notifier at the same moment | R-Type io and pic in the first frames | MAME (timer order at equal expiry: by insertion) | all |
| E6 | Z80 power-on registers (F5) | zs of frame 1 | HACK/ASSUMPTION (MAME's values) | all (Ikari with its first hash line writer, R-Type in a later fix) |
| E7 | R-Type stage S split a REP at its own run targets (the line events every 512 clocks, the frame end) and charged the REP's 2 clocks again at every such continuation, the V30 runner's default (`V30Cpu::rep_cont_charge`, MAME 0.285's F7); the boot's first REP lost 8 clocks in frame 53 | the V30 lockstep against a mameref instruction trace (section 10.3) | IMPLEMENTATION (the split points are MAMR's own; the chip has none, as for patch 0003; rtype-hardware-spec.md section 9 already specified a single charge) | S (`machine_init` sets `rep_cont_charge` false; stage M sets it per mode; the blocks continue such a REP themselves since code kind 8) |

## 7. Gates and results

### 7.1 Gates

`tools/oracle/arcade/gates.py`, registered in `tests/arcade-oracle/`
(label `oracle`; exit 2 = skipped without MAME, ROM set, replay or data;
`ARCADE_MAME` selects the MAME binary; with `-DARCADE_MAMEREF=ON` it is
mameref, and the four lockstep gates run stage M `cycle` (Ikari) and
`mameref` (R-Type) and compare R-Type's picture without skipped frames;
times against mameref in section 10.1):

| test | content | time |
|---|---|---|
| `arcade_oracle_{afh,compare,romset,gates}_selftest` | the tools against synthetic data (label `oracle-free`) | < 1 s |
| `arcade_oracle_z80steps` | the step table re-emitted from z80.lst equals `runtime/z80_steps_table.inc`, and the SST z80 check (`ARCADE_MAME_SRC` = a MAME 0.285 source tree) | 45 s |
| `ikari_oracle_determinism`, `rtype_oracle_determinism` | two MAME runs of 3000 frames byte-identical | 17 s, 35 s |
| `ikari_lockstep_attract` | stage M stock against MAME, 3000 frames, every field and the picture | 25 s |
| `ikari_lockstep_full_game` | the same over the 112,000 frames of tests/data/ikari-full-game/full_game.replay (local, not distributed), without the picture | 7-9 min |
| `rtype_lockstep_attract` | stage M against MAME, 3000 frames, picture included, `--skip-field img:117-193` | about 1 min |
| `rtype_lockstep_stage1` | the same over the 10,000 frames of the stage 1 replay | about 3 min |

### 7.2 First divergence per field

Against MAME 0.285 (stock), 3000 frames of the attract mode; the first
frame that differs, `=` for equal in every frame. "before" is the first
revision with the hash line writer (for Ikari it already contains
E1 and E6), stage S, the only stage then; "S" the game
build now, "M" stage M now.

| Ikari | clka | clkb | clks | za | zb | zs | bg | spr | tx | snd | vreg | io | pal | irq | ym | ymt | img |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| before | 341 | 1 | 350 | 341 | 1 | 343 | 11 | 1 | 14 | 346 | 1920 | 515 | = | 1 | 350 | 2 | 23 |
| S | 341 | 1 | 350 | 341 | 1 | 343 | 11 | 1 | 14 | 346 | 1920 | 515 | = | 1 | 350 | 2 | 23 |
| M | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = |

| R-Type | clkm | clks | v30 | zs | ram | spr | sbuf | pal | vram | snd | vreg | io | pic | irq | ym | ymt | img |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| before | 53 | 285 | 53 | 1 | 92 | 179 | 287 | 179 | 113 | 132 | 286 | 1 | 1 | 286 | 285 | 285 | 117 |
| S before E7 | 53 | 285 | 53 | 285 | 92 | 179 | 287 | 179 | 113 | 132 | 286 | 285 | = | 286 | 285 | 285 | 117 |
| S | 53 | 284 | 53 | 284 | 92 | 178 | 287 | 179 | 113 | 132 | 286 | 284 | = | 285 | 285 | 285 | 117 |
| M | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = | 117 (F6 only) |

R-Type "before" differs in zs, io and pic from frame 1: the power-on
registers of the sound CPU (E6), the line event order (E5) and, for pic,
the raw OCW3 register the first writer version compared (F8). Stage S
diverges at frame 53, where the first REP of the boot is continued
across slices in MAME, each continuation charged 2 clocks more (F7;
`clkm` 7,706,625 in MAME against 7,706,632 in stage S). From there the
V30 of stage S is ahead of MAME's in the program, and every later
difference follows from that. Until E7 stage S charged the same 2 clocks
at its own, far fewer split points (4 in that REP, `clkm` 7,706,629,
row "S before E7"); without them stage S equals mameref in every main
CPU field (section 10.3), so the difference to MAME 0.285 on the V30
side is F7 alone. Over the 10,000 frames of the
stage 1 replay stage M is equal in every field except img 117-193.

Stage S of Ikari gives the same lines as that first revision: E2 and E3 concern
stage M, E4 does not show in the attract mode of stage S, and E1 and E6
were made in that revision itself (against the revision before it they move the
first VBlank interrupt to the end of frame 1 and set MAME's power-on
registers). Stage S against mameref (section 10.3) still differs
from frame 1 in clkb (+10, CPU B one polling-loop instruction further)
and in zb, spr, irq; the most likely cause is E3 (stage S's accesses at
the instruction start let CPU B see CPU A's write a few cycles early),
not verified.

## 8. The judge for the V30

**Question.** MAME's nec core (`MAME src/devices/cpu/nec/`) is a table
model: one clock count per instruction form from the V20/V30/V33 columns,
effective address calculation without extra cost, no wait states, a
prefetch queue model (V30: 6 bytes at 2 clocks), every conditional
branch emptying the queue. The SingleStepTests v20 suite (3,025,000
cases, a recorded V20 with an 8-bit bus) is the only per-instruction
reference with cycles.

**Analysis** (MEASURED-EMU on MAME's V20 column against the SST v20
cycle counts, 3,019,974 cases): with a full queue 23.1 % of the cases have
MAME's exact count (mean +5.04 clocks on the chip), with an empty queue
14.3 % (+6.22). Execution-unit differences that carry over to the V30:
Jcc taken +3, LOOP taken +2, REP start-up 11-16 clocks instead of 2,
LODS/SCAS per iteration 9/10 clocks instead of 4, MUL/DIV dependent on
the data (MAME fixed). No measured V30 timing exists; the NEC manual
differs from MAME in both directions. For R-Type the estimated error of
MAME's model is -1000 to +9600 clocks per game frame (-0.7 % to +6.6 %,
sign unknown; 99.6 % of a game frame ends in the idle loop, so the game
logic is not affected); the boot memory test would take 44 to 70 frames
longer on the board, the game starting near frame 340-370 instead of 298
(testable on a board).

**Decision.** SST v20 is the judge of the V30's semantics (registers,
flags, memory: `sst_v20`, 3,025,000 cases, 0 failures, the 10 FPU
escape opcodes skipped); MAME 0.285 is the judge of the board (the
interleaving, the devices, the interrupts) and of the V30 timing as a
model. The V30 timing is "MAME's model, not measured". mameref carries
only the REP fix (0003), which is certain (the chip has no slices);
corrections from the V20 data (Jcc, shifts, RETI, string iterations) are
not applied, since V20 bus timing is not V30 timing and no V30 data
exists to check them.

## 9. What may be claimed

- Ikari Warriors: stage M is **identical to MAME 0.285** (mode `stock`)
  and **identical to mameref** (mode `cycle`) in every field of the hash
  line over 3000 attract frames (picture included) and the 112,000 frames
  of a full bot game. Its CPU, video and sound chip models give both
  judges' results on all of that code, with MAME's 1/6000 s slices and
  with the CPUs interleaved by single cycles, as on the board's shared
  bus. The game build (stage S) is **not** cycle-identical to either
  judge; its differences are MAME's scheduling (F3, F4; against MAME 0.285
  also F1) and MAMR's instruction-granular bus timing (E3).
- R-Type: stage M is identical to MAME 0.285 in every field over 3000
  attract frames and 10,000 frames of stage 1, except 73 frames of the
  picture explained by F6, and **identical to mameref** (mode `mameref`)
  in every field of the same runs, the picture included without
  exception. The game build (stage S) is **identical to mameref on the
  main CPU side** of the same runs: the V30's clock and registers at every
  notifier, work RAM, sprite RAM and buffer, palettes, video RAM, video
  registers, the interrupt controller and the picture; its sound side
  (the sound CPU, its RAM, the YM2151 writes and their clocks) is not,
  from the release of the sound CPU in frame 284 on (section 10.3). The
  V30 semantics match SST v20. The V30 timing is MAME's
  table model (with or without F7); **"cycle-accurate" is not claimed**
  for R-Type, and for Ikari only against the two judges (stage M), not
  against the board.
- "Identical to mameref" is the stronger statement only where a patch
  states the board's behaviour (one shared bus, SCHEMATIC; no REP double
  charge, the chip has no slices); the black start palette is an
  assumption (palette RAM at power-on is UNKNOWN, F6). The patches are
  reasoned, not measured (section 2), and mameref keeps MAME's synchronisation (F3),
  sample rate (F4), frame timing (F9) and V30 table model (F10).
- Neither game's timing is verified against a board: frame length,
  VBLANK position, wait states and the V30's clock counts are UNKNOWN
  (ikari-timing-reference.md section 12, rtype-hardware-spec.md).

## 10. Against mameref

mameref (section 2), the drivers `ikari` and `rtype`, against stage M in
the mode that predicts it: Ikari `cycle` (patch 0001: one CPU A cycle as
quantum), R-Type `mameref` (patch 0003, section 5; patch 0002 needs no
mode). Measured on 2026-10-27, gcc RelWithDebInfo, the runs one after
the other (MEASURED-EMU). The commands are those of the gates
(`MAME=.../mameref gates.py lockstep SET N --headless EXE --stage-m MODE
[--img] [--replay FILE]`, or ctest with `-DARCADE_MAME=.../mameref
-DARCADE_MAMEREF=ON`).

### 10.1 Gates

| gate | judge | result | time (MAME / MAMR) |
|---|---|---|---|
| `ikari_oracle_determinism` | mameref | byte-identical | 14.0 s + 13.7 s |
| `ikari_lockstep_attract`, stage M `cycle`, picture | mameref | every field equal | 24.7 s / 13.1 s |
| `ikari_lockstep_full_game`, stage M `cycle`, 112,000 frames | mameref | every field equal | 536 s / 510 s |
| `rtype_oracle_determinism` | mameref | byte-identical | 16.3 s + 16.2 s |
| `rtype_lockstep_attract`, stage M `mameref`, picture, nothing skipped | mameref | every field equal | 35.0 s / 13.0 s |
| `rtype_lockstep_stage1`, stage M `mameref`, picture, nothing skipped | mameref | every field equal | 133 s / 44 s |
| `ikari_lockstep_attract`, stage M `stock` | MAME 0.285 | every field equal | 17.7 s / 4.0 s |
| `rtype_lockstep_attract`, stage M `stock`, img 117-193 skipped | MAME 0.285 | every field equal | 30.5 s / 11.7 s |
| `rtype_lockstep_stage1`, stage M `stock`, img 117-193 skipped | MAME 0.285 | every field equal | 108 s / 41 s |
| `arcade_oracle_z80steps` (`MAME_SRC` = the mameref tree; z80.lst is not patched) | - | table equal, SST check passed | 28 s |

R-Type's stage M `stock` is byte-identical to that of the revision before the mode switch over
3000 attract frames (the mode switch changes nothing in stock). With the
perfect quantum mameref takes about 1.4 (picture drawn) to 1.6 times (no
picture) as long as MAME 0.285 on Ikari's attract mode; the full game
gate takes 17.5 min against 7-9 min.

### 10.2 First divergence per field

3000 attract frames, mameref against the run named in the row: the first
frame that differs and, in brackets, the number of differing frames; `=`
for equal in every frame. "M cycle" / "M mameref" is the gate; "MAME
0.285" is the other judge (equal, frame by frame, to "M stock", the stage
M that reproduces it, except R-Type's img, where MAME 0.285 has F6 from
frame 117 and M stock differs from 181 on).

| Ikari | clka | clkb | clks | za | zb | zs | bg | spr | tx | snd | vreg | io | pal | irq | ym | ymt | img |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M cycle | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = |
| M stock | 2547 (307) | 1 (2912) | 2800 (181) | 2547 (452) | 1 (2874) | 2800 (201) | 11 (105) | 1 (2821) | 14 (404) | 347 (184) | 1920 (422) | 2544 (83) | = | 1 (2566) | 2801 (158) | 347 (281) | 23 (298) |
| MAME 0.285 | as M stock | | | | | | | | | | | | | | | | |
| S | 341 (3) | 1 (2921) | 350 (1041) | 341 (3) | 1 (2677) | 343 (1100) | 11 (1) | 1 (2452) | 14 (44) | 346 (907) | 2030 (22) | 515 (15) | = | 1 (2664) | 350 (426) | 2 (2158) | 23 (19) |

| R-Type | clkm | clks | v30 | zs | ram | spr | sbuf | pal | vram | snd | vreg | io | pic | irq | ym | ymt | img |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M mameref | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = | = |
| M stock | 53 (2732) | 284 (2435) | 53 (2571) | 284 (2717) | 92 (2753) | 178 (2107) | 287 (2093) | 179 (1856) | 113 (2051) | 132 (2778) | 286 (1864) | 284 (858) | = | 285 (2716) | 285 (2652) | 285 (2716) | 181 (2588) |
| MAME 0.285 | as M stock except img 117 (2648) | | | | | | | | | | | | | | | | |
| S before E7 | 53 (2453) | 284 (1707) | 53 (2252) | 284 (2717) | 97 (2179) | 178 (2) | = | 179 (5) | 113 (16) | 132 (2354) | = | 284 (81) | = | 285 (2716) | 285 (729) | 285 (2716) | 181 (4) |
| S | = | 284 (2402) | = | 284 (1321) | = | = | = | = | = | 319 (71) | = | 332 (3) | = | 285 (2716) | 397 (8) | 285 (2716) | = |

The "M stock" rows are the controls: the patches change the judge in
the fields and frames section 6 predicts (Ikari: F1's bg 105, spr 2821,
img 298, clkb 2912 frames, the numbers of stage M stock against stage M
cycle; R-Type: F7 from frame 53, F6 in img from frame 117).

### 10.3 Stage S against mameref

Stage S (the game build) has none of MAME's 1/6000 s slices and, since
E7, no REP double charge, so mameref is the closer judge for it. Against
MAME 0.285 (section 7.2) it differs in the same first frames, but in far
more frames: Ikari bg 105, tx 427, vreg 422, io 92, img 304 frames
against 1, 44, 22, 15, 19 against mameref; R-Type spr 2107, sbuf 2093,
pal 1856, vram 2051, vreg 1864, img 2648 against none at all.

**R-Type frame 53 (E7).** Before E7 stage S diverged from mameref at
frame 53: `clkm` 7,706,632 (mameref) against 7,706,629 (S), mameref's
V30 one instruction further in the checksum loop of the boot (IP 0867
against 0865). A V30 instruction trace of mameref (the debugger's trace
command with a tracelog of GENPC, the registers, PSW and `totalcycles`,
as the kit's `rtype_v30_trace.lua`; 54 frames, 619,708 lines) run
against stage S with `rtype_headless --mame-trace` gives the cause:

- every one of the first 619,519 instructions is equal in registers,
  flags and clock; the boot polls with DBNZ loops until frame 53 and
  executes no REP before;
- the first REP is the clear of sprite RAM at 3F854 (`rep stmw`, CW =
  0x200, DS1 = C000), started at clock 7,667,868. mameref runs it in 190
  pieces of its 12-clock slices (the quantum of the first 25 s), without
  charging the continuations (patch 0003); the next instruction starts
  at 7,669,918;
- stage S ran it to the line events at 7,668,224, 7,668,736, 7,669,248
  and 7,669,760 and charged the REP's 2 clocks again at each of these 4
  continuations: the runner's default `rep_cont_charge` is MAME 0.285's
  F7, and only stage M set it. The next instruction started at
  7,669,926, 8 clocks late, and at the notifier of frame 53 the V30 stood
  one instruction behind.

The line events and the frame end are MAMR's run targets; the chip has
none, and rtype-hardware-spec.md section 9 already specified a REP
charged once. So this was a MAMR fault in stage S, class IMPLEMENTATION,
fixed as E7: `machine_init` sets `rep_cont_charge` to false, and stage M
still sets it per mode (stock true, mameref false). The first version
of the fix ran every such continuation in the interpreter (section 5):
37,928 units in the stage 1 replay, 35,831 over 3000 frames of the pad
script, so the native tests (`--expect-native`, interpreted 0) failed.
Since code kind 8 the blocks continue the REP themselves without the
charge, on the runner's mark (section 5, docs/machine-interface.md
section 10): over the pad script `machine_hash` reports blocks
23,398,934, interpreted 0, with the same hash lines as the interpreter
(`arcade_native_rtype`); an artefact without the mark (built before code kind 8) leaves
the 35,831 continuations to the interpreter and gives the same hash lines
(`arcade_older_rtype`). `v30_emit_diff` enters every REP string
instruction of the blocks as a continuation, charged and marked, against
the interpreter (209 cases, 0 mismatches). Test `v30_cpu`
(`test_rep_split_points`): the boot's `rep stmw` split at run targets of
512, 333, 97, 12 and 1 clocks ends on the same clock as in one piece
without the charge, and on 2 clocks per continuation later with it. With
the fix the same trace runs through frame 54 without a single resync.
The explanation by the sampling point given here before was wrong.

**Result** (2026-10-27, mameref and MAME 0.285 against stage S, the
picture compared without skipped frames):

| run | judge | equal | differing (first frame, frames) |
|---|---|---|---|
| attract, 3000 frames | mameref | clkm, v30, ram, spr, sbuf, pal, vram, vreg, pic, img | clks 284 (2402), zs 284 (1321), snd 319 (71), io 332 (3), irq 285 (2716), ym 397 (8), ymt 285 (2716) |
| stage 1 replay, 10,000 frames | mameref | clkm, v30, ram, spr, sbuf, pal, vram, vreg, pic, img | clks 284 (8613), zs 284 (4685), snd 319 (350), io 332 (11), irq 285 (9716), ym 397 (62), ymt 285 (9716) |
| attract, 3000 frames | MAME 0.285 | pic | every other field from frame 53 (`clkm`, `v30`) on: F7 |

On the main CPU side stage S is therefore identical to mameref in both
runs: clock and registers at every notifier, every memory field, the
video registers, the interrupt controller and the picture. The sound
CPU does not feed back into these fields (the main CPU only writes the
sound latch). The remaining differences:

- R-Type sound side from frame 284, the frame in which the main CPU
  releases the sound CPU from reset (io: "held in reset" 1 in frame 283,
  0 in 284): at the frame 284 notifier stage S's sound CPU is 17 cycles
  further (`clks` 18,477,574 against 18,477,557, one iteration of a RAM
  loop: BC, DE, HL one step on), and mameref's stands inside an
  instruction (`mid` 01). Consistent with F3 (MAME delays the reset line
  through synchronize and the line's event queue, stage S releases at the
  port write) and with the Z80's mid-instruction stops (F2); `irq` and
  `ymt` carry the sound CPU's cycles and differ in every frame from 285.
  Not analysed further.
- Ikari frame 1, clkb 55,847 (mameref) against 55,837 (S): E3, as in
  section 7.2, not verified. Ikari has no counterpart of E7: the Z80
  runner splits only at instruction boundaries and charges nothing at a
  resumption, and the Z80's block instructions (LDIR and the like) are
  one instruction per iteration on the chip too (z80_cpu.h). The stage S
  run against mameref of 2026-10-27 (3000 attract frames) gives the same
  lines as section 10.2.
- The sound fields (Ikari zs, snd, ym from frame 343-350; R-Type as
  above) follow F3 and F4, which mameref keeps.

## 11. Open

- R-Type stage S: the sound side against mameref from frame 284 (section
  10.3), if the game build is to follow the board.
- E3 in stage S, if the game build is to follow the board's bus timing:
  stage M cycle is about 3.5 times slower than stage S.
- A board measurement of the R-Type boot length (section 8) would test
  MAME's V30 model; a board measurement of the frame and of CPU A/B
  interleaving would test patch 0001.
