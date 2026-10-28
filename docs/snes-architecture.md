# SNES Architecture Notes

Third target family after SNK Triple-Z80 and Irem M72: the Super Nintendo
(WDC 65816 main CPU, Sony SPC700 sound CPU with the S-DSP, the two PPU
chips). First game: The Legend of Zelda: A Link to the Past (LoROM, 1 MiB,
no enhancement chip, MAME software list entry `zelda3u`). Target platform
is Linux (x86-64, SDL). This note fixes the design of the SNES path;
concept.md sections 17 and 18 stay in force.

## 1. Rules carried over

- One precisely defined ROM, SHA-1 verified. Code generated from it lives
  in `generated/` and is never distributed.
- The 65816 and SPC700 front ends are built in parallel to the Z80 and V30
  ones. No file under `recompiler/`, `runtime/` or `games/` that belongs to
  Z80, V30, Ikari or R-Type is changed for the SNES work. Shared
  abstractions are extracted later, and only where both sides use them.
- MAME 0.289 stays a test oracle, never part of the program. For the SNES
  it is a weak oracle for timing (DMA costs no cycles, no DRAM refresh,
  NMI delayed by a per-game hack) and for sound (S-DSP is an OpenSPC port
  with a known echo bug), so timing and audio are additionally checked
  against ares (ISC) and MesenCE (GPL-3, the continuation of Mesen2), both
  only as external tools.
- Licence: MAME's SNES PPU, S-SMP, S-DSP and cartridge mapper files are
  GPL-2.0+ / LGPL-2.1+ and are NOT used as templates, unlike the BSD-3
  modules behind the M72 and SNK work. Only MAME's CPU cores
  (`g65816`, `spc700`), `snes.cpp` and `snes_m.cpp` are BSD-3. The SNES
  hardware is written from the public documentation (fullsnes, Anomie's
  documents, the SNESdev wiki) with ares (ISC, permissive) as a structure
  reference. Where code follows ares closely it is derived work under
  ISC and listed in third_party/ares/LICENSE; for the PPU that includes
  the formulas that must match the silicon bit for bit (Mode 7 origin
  rounding, colour math, sprite size table), whose numbers and rules
  are checked against the documentation in docs/snes-ppu-spec.md. The
  Gaussian table is rewritten from the specification with a source
  note. The 64-byte SPC700
  IPL ROM is Sony's; MAMR ships its own functionally equivalent boot
  program and accepts a user-supplied dump as an alternative.
- Repository text is English and plain ASCII.

## 2. One table, three consumers

The Z80 and V30 front ends keep the interpreter (`*_exec.cpp`) and the C
emitter (`*_emit_c.cpp`) in sync case by case and prove their equivalence
with differential tests. The SNES front ends go one step further: every
opcode is described once, as data, and the interpreter, the emitter and
the tracer are driven by that description.

For each opcode the table row holds:

- opcode, mnemonic, addressing mode, width class (fixed, follows M,
  follows X), length rule, behaviour in emulation mode (normal or special
  path; there is no "interpreter only" class, because E=1 always runs in
  the interpreter, section 3);
- the cycle program: an ordered list of bus cycles, each with a kind
  (opcode fetch, operand fetch, data read, data write, stack push, stack
  pull, vector read, idle, idle-or-pc-read, idle-write for the
  emulation-mode read-modify-write cycle that puts the unmodified byte on
  the bus without VDA, halt for WAI/STP), an address source (PB:PC,
  direct page with its wrap class, stack with its wrap class, DBR:base
  plus index with 24-bit carry, long, pointer in bank 0, pointer in PB,
  vector, block-move source or destination), a byte index, a predicate
  (always, M=0, M=1 and native, X=0, D.l != 0, X=0 or page cross, branch
  taken, taken and E and page cross, native, E, waiting for WAI without a
  wake-up condition), and a lock mark for read-modify-write. Stack wrap
  classes: the 6502 instructions keep S in page 1 in emulation mode, PHB
  and PHK included; the 65816 instructions (PEA, PEI, PER, PHD, PLD, JSL,
  RTL, JSR (a,X) and PLB) do not wrap while they run and set S.h = 1
  afterwards;
- the poll mark: the cycle before which NMI/IRQ are sampled (the last
  present cycle), plus the rule whether the I flag takes effect before or
  after the instruction (CLI/SEI/REP/SEP/PLP: poll first; RTI: new I is
  live at once). BRK, COP and the IRQ and NMI entry set I (and clear D)
  before the vector reads, so the poll in the entry's last cycle already
  sees the new I and does not take the same IRQ again;
- the semantics: an ALU expression over named operands and the width,
  the flag mask, decimal-mode behaviour;
- the mode effect: M/X/E set statically (immediate REP/SEP) or dynamically
  (PLP, RTI, XCE), index-high clear on X=1, S.h fix in emulation mode;
- the control-flow class: linear, branch, direct jump, indirect jump,
  call, return, trap, wait, stop, block-move loop;
- a side-effect flag for accesses that may hit I/O.

The interpreter executes the cycle program against the bus. The emitter
folds constants (operands, ROM bytes in the block's own or a board-fixed
slot), sums the cycle costs per block, keeps the per-access master-clock
offsets so the bus callbacks see exact timestamps, and turns predicates
into static facts or run-time branches. The tracer prints one line per
bus cycle in the SingleStepTests format, which is how the table is
validated before any game runs.

The SPC700 table has the same shape minus the poll mark (the SPC700's
interrupt lines are not connected in the SNES) and plus a marker for
accesses that can touch its I/O page (dummy reads clear the timer
counters). It also needs a halt rule (after SLEEP and STOP every step is
a dummy read of PC plus an idle cycle, so time keeps flowing for the
timers and the DSP) and semantic steps between bus accesses (INCW/DECW
and the (X)+ store compute between two cycles, not once per
instruction).

Semantics building blocks live in header files under `runtime/` and are
called from both the interpreter and the emitted code, as for the Z80
(`runtime/z80_ops.h`).

## 3. Execution model

- Guest PC and guest stack are the only truth. JSR/JSL write the return
  address to the emulated stack and jump; RTS/RTL/RTI read their target
  from memory, set the PC and return to the dispatcher. No C call stack
  for guest calls.
- Block key: (mapping id, PB:PC, M, X). Emulation mode (E=1) runs in the
  interpreter only; the interpreter is complete for both modes because the
  table takes E as a parameter.
- The dispatcher checks the live M, X and E flags and the live mapping.
  A block for another width is never entered; the interpreter runs
  instead. No block is ever chosen because it is the "nearest" variant.
- Blocks are basic blocks: a block ends at every control-flow
  instruction, conditional branches included, at WAI and STP, at PLP,
  RTI and XCE (M/X/E unknown afterwards), and at MVN/MVP. XCE may only
  continue after a statically known CLC (it stays in native mode; the
  block still checks E at run time); SEC; XCE enters emulation mode and
  always ends the block. REP/SEP with a constant do not end a block: the
  new M/X are known and the following instructions decode with them.
  Where another path enters the middle of a block, the entry starts a
  block of its own: with the same M/X it cuts the first block there,
  with other M/X the new block decodes with those and the first block
  runs on. (Every later instruction start of a block is still a resume
  point, for the runner's budget stops.)
- A block does not run across a bank boundary (PC wraps inside the bank).
- Instructions that read or write I/O ($2100-$21FF, $4000-$44FF, the
  cartridge's register window) are sync points: the device model is
  brought up to the access's timestamp first. Plain WRAM and ROM accesses
  need no sync. The event registers (`w65_event_reg` in
  `runtime/w65816_block.h`) are the writes to $2133 (SETINI: field length
  and VBlank line), $4200 (NMI/IRQ enable), $4201 (a falling bit 7
  latches the H/V counters), $4207-$420A (H/V timers), $420B (DMA start)
  and $420C (HDMA enable), and the reads of $4210 and $4211: after such
  an access a block asks the board for the next event again (the
  horizon may only move earlier) and looks at the interrupt lines, since
  an access may raise one at once without an event (NMI enabled while
  RDNMI stands). Only accesses through an operand address are checked;
  stack pushes and pulls into the register window (S pointing at $42xx)
  are not, which no program does. $420D (MEMSEL) only changes the ROM
  speed; the cost of a ROM cycle is asked from the bus at run time, so
  it does not end the block.
- Timestamps: the CPU bus hands every access the start of its bus cycle.
  The board computes the moment the device samples it, as ares does: a
  read at start + cost - 4, a write at start + cost.
- Stolen time (DRAM refresh, HDMA, DMA) is decided by the board, not by
  the CPU code: the board places it at the CPU's cycle grid, which it
  recovers from the bus calls, and the stolen clocks are added to the
  CPU's clock after the run (section 4, "Stall at the cycle grid"). The
  emitted blocks and the interpreter know nothing of it beyond the bus
  contract.
- DBR and D are run-time registers. Addresses formed with them are never
  folded into constants, even where a preceding PLB, PLD or TCD looks
  constant; only the operand bytes and the ROM bytes are folded.
- Port model: the SPC700 is a port slave. Before every CPU access to
  $2140-$217F (four ports, mirrored) it is caught up to the timestamp of
  that bus cycle (section 5); it never runs ahead of the CPU. CPU writes
  wait in a queue with their time until the SPC700 reaches it; a CPU
  read runs the SPC700's last instructions before that time as a
  throw-away probe (docs/snes-audio-spec.md).
- MVN/MVP are emitted as a loop that charges and checks the time per
  byte and leaves the registers and PC so that the interpreter or the
  dispatcher can continue at the same instruction after an interrupt.
- Code in WRAM: pages of 256 bytes carry a generation counter that every
  write into a page with translated code bumps; a translated WRAM block
  checks the counter (or a hash of its bytes) at dispatch and falls back
  to the interpreter otherwise. Validity is decided per block, never per
  function: a function whose tail was rewritten must still run its
  unchanged blocks translated and only the changed ones in the
  interpreter (a lesson from ct-recomp). Zelda runs no code from WRAM;
  the Square JRPGs do, and this is where their support will be added.
- Discovery is static first: the vectors, the native entry behind the
  reset code, declared entry points, and the ROM tables that indirect
  transfers read, each found by a fixed pattern of the instruction
  stream (JMP/JSR (a,X); a callee that consumes its own return address,
  with its table behind the call; the return trick, PHA of a table
  entry or PEA, then RTS; JMP (a) / JML [a] through a RAM pointer filled
  from ROM tables). Return sites and the code after PLP get the widths
  the callee returns with and the PHP saw, refined in rounds; runs that
  meet BRK, COP, WDM or STP are taken for data (recompiler/w65816_cfg.h
  has the exact rules). There is no scan of the ROM for pointer-looking
  words and no other code/data guessing: a block that is never entered
  costs nothing but output. What the patterns cannot see stays open: a
  code address that only exists as data (a register frame for RTI, a
  pointer set in another routine), code nothing references, and a width
  the analysis cannot follow. The interpreter's miss log (bank, address,
  M, X) remains the fallback for all of it, and every run reports its
  misses. Measured on Zelda (USA) against a complete disassembly
  (docs/snes-zelda-authority.md): 98.7 % of its instruction starts from
  the vectors alone, 99.3 % with one declared entry; the attract mode
  and a route through the first minutes run natively without a miss.

## 4. Timing model

Two stages from the same table.

- Stage S (fast, the game build): MAMR's existing style of scheduler.
  Every bus cycle is priced by the memory region (6, 8 or 12 master
  clocks; ROM speed from MEMSEL), asked from the bus per access
  (bus->speed) in the blocks as in the interpreter; the cycle programs
  add the dynamic cycles (D.l != 0, index page cross, taken branch). A scanline
  has 1364 clocks and 340 dots (not 341): dots 323 and 327 take 6 clocks
  instead of 4. DRAM refresh (40 clocks per scanline, at H=530 on CPU
  version 1 and alternately at H=534 and H=538 on version 2, depending on
  the line start modulo 8), HDMA (per line at H=1104, setup at V=0) and
  DMA (8 clocks per byte plus overhead, aligned to the 8-clock counter)
  are charged as time stolen from the CPU at the CPU cycle where the
  hardware stops it (below, "Stall at the cycle grid"). Interrupt lines are sampled at the poll point inside
  the instruction (the poll mark of the table); a block compares the
  poll-point time with the event horizon, and the interrupt is delivered
  at the following instruction boundary. So the poll mark decides whether
  an event during an instruction is taken after it or after the next
  one.
  The PPU renders per scanline from a per-line write log and falls back
  to dot rendering only for lines with register writes inside the visible
  span (segmented rendering first, dot rendering for OAM/CGRAM accesses
  and force-blank changes inside the line).
- Stage S bus and time rules as built in phase S5b
  (runtime/snes/snes_system): the 65816 hands every bus cycle over with
  the master clock of its start; the board samples a read at start +
  cost - 4 and a write at start + cost (ares sfc/cpu/memory.cpp). The CPU
  runs whole instructions up to the next event of the time skeleton,
  which is then serviced; clocks an event steals inside a run delay the
  later bus cycles of that run and are added to the CPU clock after it.
  Where they are stolen is the next bullet. Power-on runs the reset
  sequence as ares times it (first opcode at clock 186) with the stack
  cycles as reads.
- Stall at the cycle grid (stage S since the stall fix; rules and
  sources in docs/snes-hardware-spec.md section 3.6). The hardware stops
  the CPU between two of its cycles: DRAM refresh at the end of the CPU
  step that reaches its position (the start of the next cycle, or the
  sampling moment of a read or write); GP-DMA and HDMA at the start of
  the second CPU cycle that begins at or after the $420B write or the
  HDMA trigger (the first one still runs), aligned to the 8-clock counter
  from that start and resynced to that cycle's length, 6, 8 or 12 clocks.
  The poll of an instruction's last cycle comes before the DMA of that
  cycle. Internal cycles count like memory cycles here.
  - Before the fix (phase S5b/S5c): System::stall_before charged
    whatever the time skeleton stole at the first access whose sampling
    moment was at or past the event. For refresh that is already the
    rule above. HDMA ran at its trigger, aligned from it and resynced to
    an assumed 8-clock cycle (Board::cpu_cycle_hint), one or two CPU
    cycles early, and GP-DMA ran after the instruction that wrote $420B,
    with the next opcode fetch moved behind it, resynced to a guess of
    the following cycle. Internal cycles were invisible to the board: the
    blocks fold them into one addition per instruction, the interpreter
    adds idle_clocks without a bus call. Blocks stop at the first
    instruction boundary at or past their budget (the next event) and
    poll only from the horizon on. Zelda (PAL) against ares: the sampling
    clock off by -82..+80 clocks in 72 of 1400 frames, all after the
    first HDMA frame (1325), without drift.
  - Candidate (a): the CPU code books the stall. The board announces a
    pending stall (time, cost, kind) through next_event; the block or the
    interpreter applies it at the first cycle whose start is at or past
    the time (RDY), alignment included. It needs a check before every
    cycle, internal ones too, which the emitter folds today: the blocks
    would lose that folding and grow a test per cycle in the hot path,
    and the emitter, the interpreter and the block helpers would all
    carry the DMA unit's rules (two cycles, alignment, resync, the poll
    order), which must then stay equal in two code generators.
  - Candidate (b): the runner stops a block before the event and lets
    the interpreter run the instruction that spans it, inserting the
    stall between two cycles of its program. Blocks would have to stop
    at the last boundary before the event, which they cannot know
    without the instruction's dynamic cost; the request is served one
    or two cycles later, so the span is up to two instructions; and the
    interpreter gets the DMA unit's rules. The emitter stays as it is,
    but the budget contract changes and every event costs extra
    interpreted instructions.
  - Chosen: a variant of (a) with the RDY logic behind the bus. Every
    memory cycle reaches read8/write8 with its start and every poll
    comes at a cycle start; the clocks between two such calls are
    internal cycles of exactly idle_clocks each. So the bus can recover
    every cycle start (W65CycleGrid, runtime/w65816_block.h) and report
    it to the board, which implements the DMA unit once
    (Board::cpu_cycle, after ares dmaEdge) for both timing stages. No
    change to the emitter, the interpreter, the table or the block
    contract; blocks and the interpreter make the same bus calls (the
    differential test tests/w65816/w65816_emit_diff checks it with a
    stalling bus, requests at every phase of every cycle kind) and so
    stall identically. Hot path: one test per access (a request waits
    or an event is due by the end of the cycle), the grid walked only
    near events. Two rules in the system keep the blocks honest: a stall
    inside a run ends the run after the instruction in progress and
    drops the poll horizon to 0 (the horizon is in the CPU's clock,
    which the stall left behind), and while a request waits the next
    event is "now", so the CPU runs one instruction at a time and polls
    at every poll point until it is served. Result: Zelda (PAL) against
    ares 0 differing frames in every field over 3000 frames; the run
    time of stage S unchanged within the measurement noise.
  - Stage E calls Board::cpu_cycle at every cycle start and
    Board::cpu_sample at every sampling moment itself and needs no grid.
- Stage E (exact, the reference and test build): every bus cycle calls
  the hardware, the PPU advances in dots per CPU cycle, NMI and IRQ are
  sampled every 4 master clocks, DMA stalls through RDY. Stage E is built
  from the same table and is the in-house oracle for stage S: both run
  the same ROM with the same input file and write one hash line per frame
  over the observable state, sampled at the first 65816 instruction
  boundary at or after the start of scanline 225, H=0 (scanline 240 with
  overscan), with the SMP and DSP caught up to that time stamp. (Format
  version 1 samples exactly at line 225, H=0, which can fall inside an
  instruction; the oracle tools move the sampling point to the boundary,
  see docs/snes-oracle-format.md.) The lines are compared; a
  difference is analysed by dumping the first differing frame. Stage E
  itself is held against the external oracles. Self-agreement is never
  accuracy.
- Stage E as built (runtime/snes/snes_system_exact, `snes_headless
  --exact`): SystemExact uses the parts of the stage S system (memory
  map, time skeleton with its registers, DMA channel registers and HDMA
  steps, S-SMP, PPU, input script) and runs the table-driven interpreter
  one step at a time (instruction, interrupt entry, WAI step, MVN/MVP
  byte); no blocks, no budget, no event horizon. The board keeps its own
  master clock and runs each bus cycle in place when the interpreter
  calls it (read8, write8, and W65816Bus::idle for the internal cycles):
  the DMA edge at the start of the cycle, the clocks in pieces (a read
  cost - 4, sample, 4; a write cost, then the device takes the byte; an
  internal cycle 6), one step of the multiply/divide unit per cycle, the
  PPU pipeline synced to the end of the cycle. After every piece the
  time skeleton is synced (its NMI/IRQ logic on the 4-clock raster, the
  joypad, the field structure); a DRAM refresh that became due holds the
  CPU 40 clocks at once, an HDMA trigger marks the HDMA pending. DMA and
  HDMA hold the CPU through RDY: a request is noticed at the start of a
  CPU cycle, which still runs; at the start of the next cycle the DMA
  unit takes the bus, aligns to the 8-clock counter, moves its bytes
  (refresh between the halves of a byte, HDMA at GP-DMA byte
  boundaries) and resyncs to the length of the cycle that waited.
  Interrupts are sampled at the poll point of the cycle program (the
  start of the last cycle, before its DMA edge) and taken at the
  instruction boundary; a poll right after a $4200 write (no clock in
  between) sees no line, so an interrupt the write enabled comes after
  the following instruction. The rules and their provenance are in
  docs/snes-hardware-spec.md sections 2.8 and 3; where the hardware is
  not known the coupling follows ares (IMPL), the timing oracle.
  Results (docs/snes-oracles.md section 6): stage E equals aresref in
  every field, mclk and pc included, on the PAL target game over 1400
  frames and on the gilyon ROMs (since WDM is priced as a signature
  fetch, section 9, in every field, mclk and pc included). Not covered: the S-CPU version 1
  positions, coprocessors, the SMP run per cycle (it stays a port slave,
  caught up at every port access and at the sampling point, which is
  exact by construction), emitted blocks (stage E never enters them;
  they are held against the interpreter by the emitter tests and run in
  stage S). Taken from ares without hardware evidence (IMPL, spec 2.8):
  the cycle that still runs after a DMA request is noticed, a refresh
  starting between a read's start and its sample, the multiply/divide
  unit standing still while the CPU is held. Speed on the development
  machine (interpreter, the PAL game, 1400 frames): about 51 million
  master clocks per second, 2.4 times real time; stage S runs 65 million
  in the interpreter and 77 million with emitted blocks.

Stage S is built first. The table carries everything stage E needs.

PAL (both ROMs at hand are PAL releases) is part of the board, not a
later port: master clock 21.281370 MHz, 312 lines per field (313 in
interlace field 0), no short line, instead a long line V=311 of 1368
clocks in interlace field 1; SPC700 to master clock ratio 102400/2128137
(NTSC: 5632/118125). The register-level details belong in
docs/snes-hardware-spec.md.

## 5. Sound

- The SPC700 is interpreted (about 2 to 5 percent of one core together
  with the DSP). Its program is uploaded at run time into the 64 KiB
  audio RAM; the drivers of the target games are static after the upload
  but a recompiled sound CPU would save almost nothing. The table-driven
  interpreter is the deliverable; an emitter is optional later.
- The S-SMP frame (four ports, CONTROL, three timers with the edge rule,
  the test register, RAM under the I/O page and under the IPL) and MAMR's
  own IPL boot program. The games re-enter the IPL at run time (reset
  command of the Square driver, song bank uploads in Zelda), so the boot
  program must behave like the original at protocol and state level
  (RAM image, every port write, registers at the entry points). It is not
  cycle-identical (64 bytes leave no room for that without Sony's code),
  so hash comparisons against ares run with the user-supplied IPL dump.
- The S-DSP is written from the documentation in the 32-step model (one
  sample per 32 steps of 24 clocks of the 24.576 MHz APU crystal, not
  S-CPU master clocks; voices pipelined, echo in steps 22 to 30), caught
  up before every SPC700 bus access in the same thread, not once per
  instruction. The
  512-entry Gaussian table is generated at start from the closed formula.
  BRR decoding, Gaussian interpolation with its clamps, envelope rates
  and offsets, noise, the echo FIR with its overflow order and the volume
  math must be exact per sample.
- Coupling: the SPC700 is a port slave. Catch-up before every CPU access
  to $2140-$217F (to the timestamp of that bus cycle), at the end of each
  frame and when the audio buffer runs low is exact as long as the SPC
  never runs ahead of the CPU. The plain SPC700 runner may end up to one
  instruction past its target; the S-SMP frame therefore stops at the
  last instruction boundary at or before the target and handles CPU
  writes through the queue and CPU reads through the probe (section 3).
- Clock: MAMR runs in the 32040 Hz mode (APU clock 32040 * 768 Hz, as
  ares) for parity with the primary oracle; the nominal 24.576 MHz
  (32000 Hz) stays selectable. 32040 Hz is an emulator convention, not a
  measured mean: real consoles were measured at 31965 to 32182 Hz (mean
  32076, docs/snes-audio-spec.md section 3), so the rate is a run-time
  parameter of the system (`SystemOptions::dsp_rate`, `snes_headless
  --dsp-rate`) and a game build may pick a console-like value; the
  oracle comparisons keep 32040.
- Audio output resamples 32 kHz to the host rate with dynamic rate
  control against the video clock; the audio callback is a consumer only.

## 6. Layout

```text
recompiler/w65816_decode.{h,cpp}   decoder with M/X/E context
recompiler/w65816_table.{h,cpp}    opcode table with cycle programs
recompiler/w65816_exec.{h,cpp}     interpreter driven by the table, with
                                   the bus-cycle tracer hook
recompiler/w65816_emit_c.{h,cpp}   C emitter driven by the table
recompiler/w65816_cfg.{h,cpp}      block discovery, miss-log seed format
recompiler/spc700_decode.{h,cpp}
recompiler/spc700_table.{h,cpp}
recompiler/spc700_exec.{h,cpp}
recompiler/spc700_trace.{h,cpp}    bus-cycle tracer
recompiler/w65816.cmake, spc700.cmake   source lists (CMake hooks)
runtime/w65816_context.h           register file, flags, timing fields
runtime/w65816_ops.h               semantics building blocks
runtime/w65816_bus.h               bus callbacks with 24-bit address and
                                   master-clock timestamp
runtime/w65816_block.h             block contract and the helpers the
                                   emitted code calls
runtime/w65816_cpu.{h,cpp}         runner: blocks, dispatcher, fallback
runtime/spc700_context.h, spc700_ops.h, spc700_bus.h, spc700_cpu.{h,cpp}
                                   (spc700_cpu is the runner: reset and
                                   run-until; no block dispatcher)
runtime/w65816.cmake, spc700.cmake      source lists (CMake hooks)
runtime/snes/                      board family: memory map (LoROM,
                                   HiROM), WRAM, DMA/HDMA, timing
                                   skeleton (master clock, H/V counters,
                                   NMI/IRQ, auto-joypad), PPU, cartridge
                                   descriptor (jf_snes_board, own
                                   CMakeLists.txt)
runtime/snes/snes_smp, snes_ipl, snes_dsp, snes_audio_out
                                   S-SMP frame, own IPL, S-DSP, host
                                   audio output (jf_snes_audio, source
                                   list runtime/snes/audio.cmake)
runtime/snes/snes_ppu*             PPU registers, memories, line renderer
                                   (jf_snes_ppu, in runtime/snes/
                                   CMakeLists.txt)
runtime/snes/snes_system, snes_input, snes_hashline
                                   65816 runner, board, S-SMP and a PPU
                                   stand-in wired together; input script;
                                   hash lines (jf_snes_system, source
                                   list runtime/snes/system.cmake)
runtime/snes/snes_system_exact     stage E: the same parts run per bus
                                   cycle (section 4)
tools/spcplay/                     .spc player (WAV, DSP register stream)
tools/snes_headless/, tools/snes_recomp/
                                   headless system with F lines; block
                                   generator for a ROM
games/zelda/                       game layer: ROM identity, entry
                                   points, config, headless and SDL
                                   front ends
tests/w65816/, tests/spc700/, tests/snes/, tests/snes-audio/,
tests/snes-oracle/, tests/snes-system/, tests/snes-ppu/
tests/data/sst-65816/, tests/data/sst-spc700/   SingleStepTests (local,
                                   not distributed; the tests skip with exit
                                   code 2 when the data is missing)
tools/oracle/snes/                 aresref (headless ares front end),
                                   MesenCE and MAME Lua scripts,
                                   hashline.py, compare.py, gates.py,
                                   input_script.py
docs/snes-hardware-spec.md         register-level specification with
                                   sources: memory map, time skeleton,
                                   DMA/HDMA, CPU decisions
docs/snes-audio-spec.md            S-SMP, timers, IPL protocol, S-DSP
docs/snes-ppu-spec.md              PPU registers and behaviour (phase S6)
docs/snes-oracle-format.md         hash line format (F/A/P lines)
docs/snes-oracle-input-script.md   shared input script
docs/snes-oracles.md               oracle setup, limits, gates, results
```

CMake hooks: every area is hooked in with one line at the end of the
parent `CMakeLists.txt`, the SNES lines grouped after a blank line.

- `recompiler/` and `runtime/` keep their sources flat, so there is no
  subdirectory to add: each area has a source list
  `<dir>/<area>.cmake` (targets `jf_w65816`, `jf_spc700` in
  `recompiler/`; `jf_w65816_cpu`, `jf_spc700_cpu` in `runtime/`), hooked
  in with `include(${CMAKE_CURRENT_SOURCE_DIR}/<area>.cmake)`. Paths in
  these files use `${CMAKE_CURRENT_LIST_DIR}`.
- The audio unit and the system live in `runtime/snes/` but have their
  own source lists, hooked in from `runtime/CMakeLists.txt` with
  `include(${CMAKE_CURRENT_SOURCE_DIR}/snes/audio.cmake)` and
  `.../snes/system.cmake` (targets `jf_snes_audio`, `jf_snes_system`).
  The PPU (`jf_snes_ppu`) is defined in `runtime/snes/CMakeLists.txt`
  next to `jf_snes_board`.
- A subdirectory with its own `CMakeLists.txt` is hooked in with
  `add_subdirectory(<dir>)`: `runtime/snes` (target `jf_snes_board`),
  `tools/spcplay`, `tools/snes_headless`, `tools/snes_recomp` and every
  test area (`tests/w65816`, `tests/spc700`, `tests/snes`,
  `tests/snes-oracle`, `tests/snes-audio`, `tests/snes-system`,
  `tests/snes-ppu`).
- Tests that need data which is not distributed exit with code 2 and set
  `SKIP_RETURN_CODE 2`; the oracle tests carry the labels `oracle-free`
  and `oracle`.

## 7. Verification, from the first day

- SingleStepTests/65816 and SingleStepTests/spc700 (MIT): 10,000 cases
  per opcode (65816: native and emulation mode) with the full bus cycle
  list. The interpreter must pass all of them including the cycle list.
  Known model limits (flat RAM, no SNES memory speeds, MVN/MVP with few
  cases) are documented in the harness, not skipped silently.
- Emitted blocks against the interpreter: random blocks (as
  `tests/emit` does for the Z80) and later every block of the game.
- Hardware tests: gilyon/snes-tests (MIT, CPU), undisbeliever's
  snes-test-roms (Zlib, HDMA and PPU timing), blargg's SPC tests (as
  binaries only), AccuracyCoin-style suites where they exist.
- One hash line per frame with a chained hash and per-subsystem hashes
  (CPU registers, WRAM, VRAM, OAM, CGRAM, APU RAM, PPU registers, the
  picture as 15-bit colour plus brightness, the cycle counter) written in
  the same format by MAMR and by the oracle scripts
  (docs/snes-oracle-format.md). Oracles (docs/snes-oracles.md): ares
  (headless front end `aresref`) is the primary oracle and the timing
  reference, MesenCE 2.2.1 the second one, MAME only a cross-check (it
  needs a user-supplied IPL dump for anything on the SPC side, has no
  DRAM refresh, runs the SPC700 at a different clock and its cycle
  counter jitters per frame).
- Gates before any A/B (docs/snes-oracles.md): G1 MAMR against MAMR
  byte-identical (later also stage S against stage E), G2 each oracle
  against itself byte-identical, G3 an injected fault shows up in the
  right frame and field and nowhere else.
- State anchors instead of frame numbers (wait until a RAM address holds
  a value), cycle deltas per PC anchor instead of per frame. Inputs and
  anchors are bound to the n-th auto-joypad read, not to the emulator's
  frame: the shared input script advances once per auto-joypad read, and
  hash lines can be paired by that count (`anc`) when two emulators end
  their frames at different points.
- Always-on rings (block entries, bus writes with timestamps) queried
  backwards from a debug interface; no breakpoints, no arm-then-record.

## 8. Phases

Status 2026-10-25 in brackets.

- S1  65816 table, decoder, interpreter, tracer; SingleStepTests green.
      [done]
- S2  SPC700 table, decoder, interpreter; SingleStepTests green. [done]
- S3  65816 emitter and block model; emitted blocks equal the
      interpreter on random blocks. [done]
- S4  S-SMP frame, own IPL, S-DSP, .spc player tool; blargg tests green,
      PCM against ares on own .spc dumps. [done; PCM bit-exact against
      ares, the blargg SPC tests have not been run yet]
- S5  Board runtime: memory map, WRAM, DMA/HDMA, timing skeleton, PPU
      registers; Zelda boots headless to its first frame. Done in three
      steps: S5a board skeleton (NTSC and PAL), S5b the system (65816
      runner, board, S-SMP wired together, headless program with hash
      lines), S5c the S6 PPU in the system and the gilyon test ROMs
      through the full system as ctest. [done]
- S6  PPU rendering (Mode 1 and 0, sprites, windows, colour math, HDMA,
      mosaic, Mode 7) per scanline with segment rendering; frame hashes
      against ares, MesenCE and MAME. [done; picture and PPU state equal
      to aresref on the gilyon ROMs and on Zelda (PAL) over 1400 frames;
      since the stall fix (section 4, "Stall at the cycle grid") every
      field of Zelda's F lines, the sampling clock included, is equal to
      aresref over 3000 frames; stage E equals aresref there as well]
- S7  Zelda game layer: entry points and CFG against the disassembly
      authority, headless attract mode with hash comparison, SDL front
      end, input. [code authority done 2026-10-24,
      docs/snes-zelda-authority.md: the static discovery finds 99.3 %
      of the US disassembly's instruction starts with one declared
      entry, the attract mode and a route through the first minutes run
      natively without a dispatch miss (ctests snes_discovery_zelda_*,
      snes_native_zelda_usa_*); the game layer and the front end are
      open]
- S8  Oracle pipeline as ctest: MAME Lua, ares harness, hash lines,
      gates; homebrew and test ROMs for CI without commercial ROMs.
      [done; hash line format 4]
- Across phases: stage E (section 4) [built: interpreter-only lockstep
  per bus cycle, equal to aresref on the PAL target game and the gilyon
  ROMs]; code in WRAM (section 3) [open].
- Then FF IV, FF VI and Chrono Trigger with WRAM code support.

## 9. Decisions

- 2026-10-24, 65816 (dp,X) in emulation mode with D.l != 0: MAMR follows
  the hardware behaviour that gilyon/snes-tests checks (matched by ares):
  the pointer's high byte is read from D+dp+X+1 with the +1 wrapping
  inside the page. SingleStepTests/65816 expects the plain +1; the 264
  affected cases are marked in the harness (`tests/w65816/w65816_sst.cpp`)
  as a known deviation, checked to differ exactly in that read.
  Details and sources: docs/snes-hardware-spec.md section 4.
- 2026-10-25, 65816 reset: the three stack cycles of the reset sequence
  are reads (WDC W65C816S datasheet section 2.25 and table 5-7 note 10:
  RWB stays high), so nothing is written to $01FD-$01FF. ares writes the
  three pushes there; that is an ares artefact, and reference hash files
  made with it carry it in the wram field.
- 2026-10-25, APU clock: the 32040 Hz mode (section 5) for parity with
  ares.
- 2026-10-24 (research package A), S-SMP clock: the DSP sample rate is a
  run-time parameter (`SystemOptions::dsp_rate`, default 32040 Hz, the
  ares/MesenCE convention, so no oracle result changes); the measured
  console range 31965 to 32182 Hz is documented as the valid range
  (docs/snes-audio-spec.md section 3, MEASURED).
- 2026-10-24 (research package A), WDM ($42): the second cycle is a
  signature fetch at PB:PC+1 (VPA, the byte discarded), as BRK/COP's
  second cycle in the WDC data sheet and as ares, MesenCE, MAME and
  LakeSnes do; from SlowROM it costs 8 clocks, not the 6 of an internal
  cycle. SingleStepTests/65816 records the internal cycle; the 20,000
  cases of opcode $42 are a known deviation in the harness
  (`tests/w65816/w65816_sst.cpp`), compared in full with the second
  cycle rewritten. With this price stage S and stage E meet aresref in
  every field, mclk and pc included, on gilyon's cputest ROMs. Open
  until a console measurement; the test setup is in
  docs/snes-hardware-spec.md section 4.2.
