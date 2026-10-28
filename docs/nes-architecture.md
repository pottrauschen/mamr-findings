# NES Architecture Notes

Fourth target family after SNK Triple-Z80, Irem M72 and the SNES: the
Nintendo Entertainment System (Ricoh RP2A03 CPU, a 6502 core without the
decimal mode plus the APU and the DMA unit, and the RP2C02 PPU). First
game: Super Mario Bros. 3 (USA, board NES-TSROM with a Sharp MMC3B, 256
KiB PRG ROM, 128 KiB CHR ROM, 8 KiB work RAM; docs/nes-hardware-spec.md
section 1 records the board). Target platform is Linux (x86-64,
SDL). This note is the contract for the NES path; it follows
docs/snes-architecture.md, whose rules on blocks, oracles and evidence
carry over unchanged, and names the places where the NES differs.

## 1. Rules carried over, and the NES-specific ones

- One precisely defined ROM, SHA-1 verified. Code generated from it lives
  in `generated/` and is never distributed.
- The 6502 front end is built next to the Z80, V30, 65816 and SPC700
  ones. No file of another ISA or another board family is changed for
  the NES work; shared abstractions are extracted later, and only where
  both sides use them. In particular the 65816 table is not reused: the
  NES core has its own table (`recompiler/m6502_table`), because its
  cycle programs, its undocumented opcodes and its block model differ,
  and because two tables that must stay equal in two places is exactly
  what the one-table design avoids.
- No emulator code. MesenCE (GPL-3) and MAME (GPL-2+ / BSD-3) are
  external oracles only; neither is used as a template, not even the
  BSD-3 parts of MAME's NES driver, so that the licence question never
  arises for this path. The hardware is written from the public
  documentation (the NESdev wiki, the 6502 data sheets and the published
  cycle tables, blargg's and AccuracyCoin's test descriptions). Data
  derived from the Visual2A03 and Visual2C02 simulations is CC BY-NC-SA
  and is not used: no tables, no timing numbers, no quotations of their
  results. Where a fact is only known through them it is marked UNKNOWN
  in docs/nes-hardware-spec.md and settled by a test ROM on a console.
  Exception since 2026-10-26: a transistor-level simulation (perfect6502,
  MIT, running the Visual6502 netlist) may be run outside the repository
  to answer one question; nothing of it (netlist, code, tables, traces)
  enters the repository, and the answer is recorded as a behavioural
  statement of class SIM with its source (docs/nes-hardware-spec.md,
  sources).
- Test material with a licence may be built and run and may leave rows in
  the evidence register (section 7); material without a licence
  (blargg's suites, nestest) is used locally only and never enters the
  repository, not as a file, not as a hash of its output.
- Repository text is English and plain ASCII.

## 2. One table, three consumers

Every opcode of the 2A03 is described once, as data
(`recompiler/m6502_table`), and the interpreter, the C emitter and the
tracer are driven by that description. The row of an opcode holds:

- opcode, mnemonic, addressing mode, documented or undocumented, and for
  the undocumented ones the stability class (stable; unstable with a
  magic constant: ANE, LXA; unstable address-high corruption: SHA, SHX,
  SHY, TAS; jam: the twelve KIL opcodes);
- the cycle program: an ordered list of bus cycles, each with a kind
  (opcode fetch, operand fetch, data read, data write, dummy read, dummy
  write, stack push, stack pull, vector read), an address source
  (PC, zero page with its wrap, zero page plus index with its wrap,
  stack, absolute, absolute plus index uncorrected and corrected,
  pointer in the zero page, pointer plus Y uncorrected and corrected,
  indirect pointer with the page-wrap bug of JMP (a), vector), a byte
  index, a predicate (always, page crossed, branch taken, branch taken
  and page crossed) and the register or data byte the cycle moves. The
  6502 has one bus cycle per clock and no internal cycles: every cycle
  of the program is a read or a write of some address, which is why the
  dummy reads of the indexed modes and the double write of the
  read-modify-write instructions are first-class cycles and not costs;
- the poll mark: the cycle at the start of which the NMI edge and the
  IRQ level are sampled (the start of the last cycle, as on the 65816)
  and the rule for the I flag (CLI, SEI, PLP: the poll still sees the
  old I; RTI: the new I is live); the branch instructions poll at the
  start of their last cycle, which moves when the branch is taken or
  crosses a page, so a taken branch without a page cross does not poll
  in its extra cycle (the documented "branch delays an interrupt by one
  instruction" behaviour falls out of the cycle order);
- the semantics: an ALU expression over the operand, the flag mask and
  the register written; the 2A03 has no decimal mode (the D flag is
  stored, pushed and pulled but ADC/SBC are always binary);
- the control-flow class: linear, branch, direct jump, indirect jump,
  call, return, trap (BRK), jam (KIL);
- a side-effect flag for cycles that may hit I/O or a mapper register
  (every computed address and every absolute address outside $0000-$07FF
  and its mirrors).

The interpreter executes the cycle program against the bus. The emitter
(phase N3, recompiler/m6502_emit_c) folds constants (the operand bytes
and everything computed from them and from the instruction's address,
taken from the bank of the block's window), keeps one bus call per cycle
with its exact time stamp (the opcode and operand fetches too: they set
the open bus and the stall hook runs before them), and turns predicates
into static facts or run-time branches (the page cross of an index, the
branch condition). Folding the cost per block is the work of stage S
(section 4) and comes later; in phase N3 a block makes exactly the bus,
stall and poll calls of the interpreter. The tracer prints one line per bus cycle in
the SingleStepTests format (`[address, value, "read"|"write"]`), which is
how the table is validated before any ROM runs.

Semantics building blocks live in `runtime/m6502_ops.h` and are called
from the interpreter and from the emitted code.

## 3. Execution model

- Guest PC and guest stack are the only truth. JSR writes the return
  address to the emulated stack and jumps; RTS and RTI read their target
  from memory, set the PC and return to the dispatcher. No C call stack
  for guest calls.
- Block key: (bank, PC), where the bank is the 8 KiB PRG ROM bank that
  the mapper maps into the CPU window holding PC ($8000, $A000, $C000 or
  $E000; `NesMapper::prg_offset(window) / $2000`). The 2A03 has no
  M/X/E modes, so the decode context is empty, but the code at an
  address depends on which ROM bank is switched in there, and on nothing
  else: a block never leaves its 8 KiB window (below), its operands are
  folded from that window only, and every data access goes to the bus.
  So the bank of the PC's window is the whole key, for every mapper; the
  rest of the bank state (the other windows, the PRG mode) does not
  change the block. A block is translated against one bank and is
  entered only while the live mapping puts that bank in its window; the
  dispatcher asks the mapper on every entry. No block is ever chosen
  because it is the "nearest" variant. (Until 2026-10-26 the key was the
  full bank state of the mapper; section 10 has the measurement that
  replaced it.)
- Mapper writes end the block. On the NES a store to $8000-$FFFF is a
  mapper register write, and on MMC1 and MMC3 it may change the bank
  state under
  the running code. Every store whose target is statically in that range
  ends the block; a store with a computed target (indexed, indirect)
  is checked at run time by the block helper and makes the block return
  to the dispatcher when the target is at or above $8000. The
  dispatcher then re-evaluates the bank state and continues, in a block
  of the new state or in the interpreter.
- Blocks are basic blocks: a block ends at every control-flow
  instruction, conditional branches included, at BRK, at every mapper
  write (above) and at a KIL opcode. Where another path enters the
  middle of a block, the entry starts a block of its own, which cuts the
  first block there (there is no width variant to keep). Every later
  instruction start of a block is a resume point: the dispatcher enters
  the block there after a budget stop, an interrupt return or a miss-log
  seed (a seed that is a later instruction of a block is a resume point,
  not a cut). A taken branch or JMP back into the block loops inside its
  function after the interrupt and budget checks.
- A block does not run across the end of its 8 KiB window, for every
  mapper (the 16 KiB and 32 KiB windows of MMC1, NROM and CNROM are two
  and four such windows): the next byte may come from another bank
  register. An instruction whose bytes cross the end of a window is not
  translated and runs in the interpreter. PC wraps at $FFFF to $0000
  (AccuracyCoin "PC Wraparound"); the instruction at $FFFF is such a
  crossing one.
- Instructions that read or write I/O ($2000-$2007 and their mirrors up
  to $3FFF, $4000-$4017, $4020-$5FFF cartridge expansion, mapper
  registers) are sync points: the device model is brought up to the
  access's time stamp first. Plain RAM and ROM accesses need no sync.
  Event registers: $2000 (NMI enable), $2002 (reads clear VBlank, race
  with the NMI edge), $4014 (OAM DMA start), $4015 (DMC start and stop,
  IRQ flags), $4017 (frame counter mode, IRQ inhibit), $4010 (DMC IRQ
  enable), and the MMC3 registers $C000-$FFFF (IRQ latch, reload,
  disable, enable). After such an access a block asks the board for the
  next event again and looks at the interrupt lines.
- Time stamps: the CPU bus hands every access the CPU cycle count at the
  start of its cycle. The board decides where inside the cycle a device
  samples it (the PPU runs three dots per CPU cycle; a read lands in the
  dot the board computes from the cycle start).
- Stolen time (OAM DMA, DMC DMA) is decided by the board, not by the CPU
  code. The DMA unit halts the CPU only on a read cycle (RDY is ignored
  during writes), repeats that read while it waits for the alignment
  cycle, moves its bytes and lets the CPU's read complete afterwards.
  The bus contract therefore gives the board the start of every read
  cycle (`M65Bus::read8` with the time stamp) and an optional
  `M65Bus::stall` hook called before every read: the board returns the
  CPU cycles it took, performs the repeated reads of the halted address
  itself (they are visible at $2002, $4016, $4017 and on the MMC3's
  A12), and the interpreter and the blocks add the stolen cycles to the
  CPU's clock. Phase N1 defines the hook and keeps the board's side
  empty; phase N2 implements OAM DMA (513 or 514 cycles depending on the
  cycle parity at $4014) and DMC DMA (4 cycles, fewer when it lands on
  the CPU's own halt or dummy cycles; the "implicit abort" cases that
  AccuracyCoin tests) behind it.
- Code in RAM: pages of 256 bytes carry a generation counter that every
  write into a page with translated code bumps; a translated RAM block
  checks the counter at dispatch and falls back to the interpreter
  otherwise. Super Mario Bros. 3 runs no code from RAM as far as the
  disassembly and the runs show, so phase N3 does not build the
  mechanism: code below $8000 (internal RAM, PRG RAM, I/O, open bus) has
  no key and runs in the interpreter, counted as misses outside the PRG
  ROM (AccuracyCoin and nestest execute such code on purpose; section 8).
- Discovery (recompiler/m6502_cfg, tools/nes_recomp) is the reset, NMI
  and IRQ vectors, declared entry points, the windows declared fixed (the
  mapper's own: the last bank at $E000 on the MMC3; and those a game is
  known to keep, such as the second-to-last bank at $8000 in MMC3 PRG
  mode 1), one declared table pattern (the inline jump table behind a
  JSR whose callee consumes its own return address) and the dispatcher's
  miss log (bank, address). A transfer into another window whose bank is
  not declared is not followed statically; the miss log brings it. No
  code/data heuristics.

## 4. Timing model

Two stages from the same table, as for the SNES.

- The unit of time is the CPU cycle (1.789773 MHz on NTSC, 12 master
  clocks of 21.477272 MHz; one CPU cycle is three PPU dots). Every bus
  cycle costs one CPU cycle; there are no memory speeds and no internal
  cycles, so the cycle program's length is the instruction's cost, plus
  the dynamic cycles (page cross on a read with an index, taken branch,
  taken branch across a page).
- Stage S (fast, the game build): the CPU runs whole instructions up to
  the next event of the board's time skeleton (an NMI at the start of
  the vertical blank, a frame-counter IRQ, an MMC3 scanline IRQ, a DMA),
  which is then serviced; interrupt lines are sampled at the poll mark
  of the table (the start of the last cycle) and taken at the following
  instruction boundary. The PPU renders per scanline from a per-line
  write log and falls back to dot rendering for lines with register
  writes or sprite-0 hits inside the visible span. Stolen DMA cycles are
  booked at the read cycle where the hardware stops the CPU (section 3),
  through the same bus calls the interpreter and the blocks both make.
- Stage E (exact, the reference and test build): every bus cycle calls
  the hardware, the PPU advances three dots per CPU cycle, the MMC3 sees
  every PPU address bus change (A12 edges from the PPU's fetch pattern),
  NMI and IRQ are sampled per cycle, DMA halts through the stall hook.
  Stage E is the in-house oracle for stage S: both write one hash line
  per frame (section 7) and the lines are compared.
- CPU/PPU alignment at power-on: the hardware starts in one of four
  alignments of the CPU's clock divider against the PPU's; the oracles
  start in one fixed alignment each (documented in docs/nes-oracles.md).
  MAMR's board takes the alignment as a parameter, defaults to the
  oracle's and records it in the hash file header. A test that depends
  on it is recorded with the alignment it was run in.

Super Mario Bros. 3 (USA) is NTSC. PAL (RP2A07, 3.2 dots per CPU cycle,
312 lines) is a machine parameter since phase P (section 11), with
Super Mario Bros. 3 (Europe) as its game.

## 5. Sound

The APU is part of the 2A03 and is written from the documentation in
phase N2 and later: the frame counter (4- and 5-step modes, the IRQ, the
write delay that depends on the cycle parity), the length counters,
envelopes and sweeps, the two pulse channels, the triangle, the noise
and the DMC with its DMA (section 3). The DMC's DMA and the frame
counter's IRQ are system behaviour that stage E must get right before
any sound is heard; the mixer and the host output come last. Audio
output resamples to the host rate with dynamic rate control against
the video clock, as on the SNES.

Phase N4 (docs/nes-audio-spec.md): the channels run on the CPU cycle
time line in both stages, brought up to date in runs between their
events whenever their state changes, which equals stepping every cycle;
the mixer evaluates the nonlinear formulas in fixed point per cycle; the
levels of 8 cycles summed are the native samples (CPU clock / 8, exact
integers, hashed per frame as the field snd). The machine adapter
decimates them by 5 with a FIR to CPU clock / 40 (44,744.3 Hz) and
applies the console's analog filters (high-pass 90 Hz and 440 Hz,
low-pass 14 kHz); mamr_play resamples that to the device with the SNES
FIFO and rate control (docs/frontend.md section 5). Stage S and stage E
produce the same samples (gate G1).

## 6. Layout

```text
recompiler/m6502_table.{h,cpp}     opcode table with cycle programs,
                                   all 256 opcodes
recompiler/m6502_decode.{h,cpp}    decoder (length, flow class, block end)
recompiler/m6502_exec.{h,cpp}      interpreter driven by the table, with
                                   the interrupt entry and the poll rule
recompiler/m6502_trace.{h,cpp}     bus-cycle tracer (SingleStepTests
                                   format)
recompiler/m6502.cmake             source list (CMake hook, target
                                   jf_m6502)
runtime/m6502_context.h            register file, flags, timing fields
runtime/m6502_ops.h                semantics building blocks (binary
                                   ADC/SBC only)
runtime/m6502_bus.h                bus callbacks with 16-bit address, CPU
                                   cycle time stamp, interrupt poll and
                                   the stall hook
runtime/nes/                       board family: iNES/NES 2.0 header,
                                   cartridge descriptor, mappers (NROM,
                                   MMC1, CNROM, MMC3), CPU memory map,
                                   PPU and APU
                                   register stand-ins (jf_nes_board, own
                                   CMakeLists.txt)
runtime/nes/nes_hashline           hash lines (phase N2, with the PPU)
tools/oracle/nes/                  MesenCE and MAME Lua scripts, runner
                                   scripts, hashline.py, compare.py,
                                   gates.py, input scripts (inputs/)
tools/nes_headless/                the interpreter on the board, hash
                                   lines out; nes_pcstats: the code
                                   survey of a run (phase N2); with
                                   blocks (nes_headless_native, or any
                                   build with --cartridge) since N3
recompiler/m6502_emit_c.{h,cpp}    C emitter and block shape (phase N3)
recompiler/m6502_cfg.{h,cpp}       block discovery with the (bank, PC) key
runtime/m6502_block.h              block function type, manifest, the
                                   helpers the emitted code calls
runtime/m6502_dispatch.{h,cpp}     dispatcher: blocks, interpreter
                                   fallback, miss log
runtime/nes/nes_state, nes_palette save states; the picture's RGB palette
runtime/machine/nes_game           the NES behind the machine interface
tools/nes_recomp/                  discovery and emission for one ROM,
                                   the code map; nes_rounds.py: rounds of
                                   recomp, artefact and miss log
tests/m6502/                       table, decoder, interrupt tests;
                                   SingleStepTests harness
tests/nes/                         board tests; nestest run (local data)
tests/data/sst-6502/               SingleStepTests/65x02, nes6502 subset
                                   (local, not distributed; the test skips with
                                   exit code 2 when the data is missing)
docs/nes-hardware-spec.md          register-level specification with
                                   provenance classes
docs/nes-audio-spec.md             APU channels, mixer and output stage
                                   with provenance classes (phase N4)
runtime/nes/nes_audio_out          the output stage: FIR decimation and
                                   the analog filters (phase N4)
runtime/machine/pad_script         scripted pad input for machine_hash
                                   and mamr_play --pads
docs/nes-oracle-format.md          hash line format (nesfh version 2)
docs/nes-oracles.md                oracle setup, traps, gates, results
docs/nes-test-evidence.md          evidence register of the NES test
                                   programs
docs/nes-smb3-survey.md            code survey of the target game for
                                   phase N3
```

CMake hooks follow the SNES rule: one line at the end of the parent
`CMakeLists.txt` per area, the NES lines grouped after a blank line
(`include(${CMAKE_CURRENT_SOURCE_DIR}/m6502.cmake)` in `recompiler/`,
`add_subdirectory(nes)` in `runtime/`, `add_subdirectory(m6502)` and
`add_subdirectory(nes)` in `tests/`). Tests that need data which is not
distributed exit with code 2 and set `SKIP_RETURN_CODE 2`; oracle tests
carry the labels `oracle-free` and `oracle`; tests on local-only ROMs
carry the label `local`.

## 7. Verification, from the first day

- SingleStepTests/65x02, set `nes6502` (MIT, Thomas Harte et al.):
  10,000 cases per opcode, all 256 opcodes, with the full bus cycle list.
  The interpreter must pass all of them including the cycle list. The
  set is model-generated (the README: an implementation that "conforms
  to all available documentation"), never hardware; the unstable
  undocumented opcodes are compared against the suite's model and the
  model's choice is recorded as a known deviation class in the harness
  and in docs/nes-hardware-spec.md, never as hardware truth.
- Emitted blocks against the interpreter: random and fixed blocks and one
  block per sampled SingleStepTests case of every file (m6502_emit_diff,
  m6502_emit_sst: state, memory, cycles and every bus, stall and poll call
  in order), and every block of the game through the hash lines of whole
  runs (phase N3, section 8).
- Hardware tests: AccuracyCoin (MIT, Chris Siebert; 147 tests on one
  NROM cartridge, written for an NTSC console with an RP2A03G and an
  RP2C02G) is the TEST-ROM-HW judge of the path: every PASS/FAIL cell
  is a hardware expectation of its author, and a FAIL in MAMR is a
  finding, never a tolerance. blargg's suites and nestest (no licence)
  are run locally as further judges and their results documented, but
  nothing of them enters the repository.
- Oracles (docs/nes-oracles.md): MesenCE 2.2.1 is the primary oracle
  (its test-runner mode writes the hash lines from Lua), MAME 0.285 the
  second one (frame-level only; it writes what its Lua interface
  exposes). Neither is hardware; where they disagree, AccuracyCoin or a
  console run decides. Neither passes AccuracyCoin completely (MesenCE
  141/147, MAME 85/147; docs/nes-test-evidence.md section 2), so a test
  an oracle fails is judged by the ROM's own verdict.
- One hash line per frame with a chained hash and per-subsystem fields
  (docs/nes-oracle-format.md): cpu (A, X, Y, S, P), ram (2 KiB), vram
  (the 2 KiB CIRAM), oam (256 bytes), pal (32 bytes, canonical
  mirroring), prgram (the cartridge's PRG RAM), ppu (the canonical PPU
  register and latch set), prgmap and chrmap (the bank windows the
  mapper presents), mirq (the mapper's IRQ counter state), img (the 256
  by 240 picture as palette indices with the emphasis bits), and the
  timing keys cyc (CPU cycles since power-on) and dot (PPU dots), both
  compared only on request. Sampling point: the first instruction
  boundary at or after dot 0 of scanline 240 (the post-render line).
- Gates before any A/B: G1 MAMR against MAMR byte-identical (later also
  stage S against stage E), G2 each oracle against itself byte-identical
  and MesenCE against MAME with the differences recorded, G3 an injected
  fault shows up in the right frame and field and nowhere else.
- State anchors instead of frame numbers; inputs bound to the n-th
  controller strobe ($4016 write of 1 then 0), not to the emulator's
  frame.

## 8. Phases

Status 2026-10-26 in brackets.

- N1  6502/2A03 table, decoder, interpreter, tracer; SingleStepTests
      green; oracle pipeline (MesenCE, MAME, gates); AccuracyCoin in the
      evidence register with the oracles' results; board skeleton with
      iNES/NES 2.0 header, NROM and MMC3 bank logic, CPU memory map,
      register stand-ins; nestest in the interpreter against its log.
      [done 2026-10-24; results in docs/nes-oracles.md and
      docs/nes-test-evidence.md, hardware decisions in
      docs/nes-hardware-spec.md]
- N2  PPU (registers, VRAM access with the read buffer, sprite
      evaluation, dot renderer and line renderer), APU frame counter and
      DMC DMA with the stall hook, OAM DMA, MMC3 IRQ with the A12 filter
      against blargg's mmc3 tests and AccuracyCoin; hash lines from MAMR,
      gate G1; Super Mario Bros. 3 boots in the interpreter to its title
      screen and is compared against MesenCE frame by frame.
      [done 2026-10-25 except the game: AccuracyCoin
      147/147 in MAMR (MesenCE 141, MAME 85), blargg's MMC3, APU, DMA
      and PPU suites that run on NROM/MMC3 boards pass, MAMR equals
      MesenCE in every field, cyc and dot without input and instruction
      by instruction with input until the first test MesenCE fails;
      gate G1 with stage S against stage E as ctests. The line renderer
      is exact but not yet faster (docs/nes-ppu-spec.md section 14).
      2026-10-26: MMC1 and CNROM for blargg's suites (section
      10); nes-test-roms 88 of 90 in MAMR. PPU in docs/nes-ppu-spec.md, APU and DMA in
      docs/nes-hardware-spec.md sections 3.8 and 6, results in
      docs/nes-oracles.md and docs/nes-test-evidence.md.
      2026-10-25, the game: Super Mario Bros. 3 (USA, Rev 1) boots in
      the interpreter through the curtain to the title (nametable at
      frame 196, full picture at frame 451) and the menu (frame 1584),
      and plays World 1-1 with an input script; against MesenCE over
      3000 frames without input cpu, vram, oam, pal, prgram, prgmap,
      chrmap, mirq and inp are equal in every frame, and the remaining
      differences are four recorded findings, each with its judge
      (docs/nes-oracles.md section 6: S1 NMI during a taken branch, the
      wiki and a 6502 simulation against MesenCE; S2 $2007 on an ALE dot
      and S3 OAM row corruption, both AccuracyCoin against MesenCE; S4
      the background prefetch after rendering is switched on, likely
      AccuracyCoin against MesenCE). The MMC3 IRQ split agrees, the A12
      filter of 3 M2 falls holds (1 and 2 break the game). Code survey
      for N3 in docs/nes-smb3-survey.md. Phase N2 is done; S1, its one
      open hardware question, was decided on 2026-10-26 by simulation
      for MAMR's rule (docs/nes-hardware-spec.md section 5.7)]
- N3  C emitter and block model with the bank-state key; emitted blocks
      equal the interpreter on random blocks and on every block of the
      game; dispatcher, miss log, game layer. [done 2026-10-26.
      The emitter walks the table's cycle programs (the poll rule
      is one table function, m65_polls_at, for both consumers) and folds
      the instruction bytes; the differential test finds 0 differences
      in 1518 random and fixed blocks (182,160 cases, every bus, stall
      and poll call) and in 16,384 SingleStepTests blocks, 64 from each
      of the 256 files (ctest m6502_emit_sst); a one-off run with 1000
      cases from every file (M65_EMIT_SST_CASES=1000, 256,000 blocks,
      1,024,000 cases with random lines, DMA and budgets) found 0 as
      well, 16 cases skipped because they write into their own bytes. The key is (bank of the PC's window, PC)
      (section 10). Super Mario Bros. 3: statically 1010 blocks in the
      fixed banks, with the miss log of one round 6898 blocks with 24,696
      instructions in 18 banks; native runs of 3000 frames without input
      and with the World 1-1 script equal the interpreter in every hash
      line (all fields, cyc and dot) with 0 misses
      (docs/nes-smb3-survey.md section 4). AccuracyCoin native 147/147,
      its full run equal to the interpreter (misses only for its code in
      RAM and I/O and the instruction at $FFFF); nestest native equal to
      its log in every line. The NES behind runtime/machine (save
      states, SRAM, silent audio until N4), the game artefact
      smb3.mamrcart and mamr_play with --cartridge auto.]
- N4  APU channels and mixer, SDL front end, input; the game plays.
      [done 2026-10-26. docs/nes-audio-spec.md with a
      provenance class for every statement; the pulse, triangle, noise
      and DMC outputs and the mixer in runtime/nes/nes_apu, the output
      stage in runtime/nes/nes_audio_out; unit tests per channel without
      a ROM (tests/nes/test_nes_audio.cpp). Hash format 2 with the fields
      apu (comparable with MesenCE) and snd (MAMR's samples). Against
      MesenCE the apu field is equal in Super Mario Bros. 3 until finding
      S1 separates the games, and with MesenCE's NMI rule switched on
      locally in 2990 of 3000 frames, the rest being finding A1 (the DMC
      level against its timer, docs/nes-oracles.md section 6.1); blargg's
      dmc_tests and apu_mixer equal in every field. AccuracyCoin 147/147
      in the interpreter and native; blargg's apu_test (8), apu_reset (6)
      and 2005 suite (11) pass; apu_mixer measured against the
      collection's recordings: the noise test within 0.5 dB, the
      cancellation tests 1 to 5 dB quieter than the recordings
      (docs/nes-test-evidence.md section 4.6). Super Mario Bros. 3 plays
      with sound in mamr_play (native artefact and interpreter); the
      round trip and the game-state test play it with a pad script and
      compare the sound; save state version 2 with the channels and the
      output stage.]

- P   PAL: the RP2A07 and the RP2C07 as a region of the same machine,
      Super Mario Bros. 3 (Europe) as the seventh game. [done 2026-10-27
      (section 11): specification with a class per
      statement; the region from the cartridge database, the header or
      forced; the PAL time line, frame, OAM refresh, APU tables, hash
      header and save state version 3, NTSC byte-identical; MesenCE and
      MAME in PAL mode; blargg's pal_apu_tests 10/10 (MesenCE 10/10, MAME
      1/10), demo_pal inside its range; the European game against MesenCE
      over 3000 frames with input equal in inp, cpu (apart from S1),
      vram, pal, prgram, prgmap, chrmap, mirq, apu (apart from A1), with
      the recorded findings S1-S3, A1 and the new P1-P3
      (docs/nes-oracles.md section 8); native with 0 misses, its artefact
      smb3-eu.mamrcart, the play round trip with sound and the state
      check.]

## 9. Known limits of this phase

- Undocumented opcodes. The stable ones (SLO, RLA, SRE, RRA, SAX, LAX,
  DCP, ISC, ANC, ALR, ARR, SBX, LAS, the NOP forms, the double-length
  NOPs with their dummy reads) are documented behaviour and are compared
  against the suite in full. The unstable ones have no single hardware
  value: ANE ($8B) and LXA ($AB) AND the accumulator with a "magic"
  constant that depends on the chip and on the bus state; SHA ($93,
  $9F), SHX ($9E), SHY ($9C) and TAS ($9B) store (register AND high
  address byte) and corrupt the address high byte when the index
  crosses a page, with DMA and RDY interactions on top. MAMR implements
  the common model (magic constant $EE for ANE, the address corruption
  on a page cross) and the harness compares every case of the suite
  against it; where the suite's model chose otherwise, the harness names
  the cases and their number and the hardware spec records the class.
  LXA uses $FF since 2026-10-26 (blargg's instruction tests pass only
  with it, docs/nes-hardware-spec.md section 4.2); the suite has $EE,
  and the harness compares the differing LXA cases with the suite's
  value put in and counts them. Super Mario Bros. 3 uses none of them.
- The KIL opcodes jam the CPU: the interpreter stops the clock as for
  the 65816's STP and a block ends there.
- Power-on RAM is unspecified on the hardware; MesenCE runs with the
  fill 00 (or ff), MAME with its fixed $00/$FF pattern, and the hash file
  header records it. Comparisons of RAM
  bytes a program never wrote need the fill 00 / fill ff mask of the
  SNES note.
- CPU/PPU power-on alignment (section 4): one alignment, the primary
  oracle's, as a parameter (`NesBoardConfig::access_dot`); the PPU's
  first-frame write block (writes to $2000/$2001/$2005/$2006 ignored for
  about 29658 cycles after power-on) is a switch, off for the oracle
  comparison (docs/nes-ppu-spec.md section 12).
- Boards: NROM and MMC3 for the target, MMC1 (SxROM up to 256 KiB PRG
  ROM, MMC1B) and CNROM only for blargg's suites in nes-test-roms
  (docs/nes-hardware-spec.md sections 3.9 and 3.10); no other mapper.
- Not modelled in phase N2: the PPUCTRL bit 0 race, the $2003 OAM corruption, OAM and latch decay
  except the PPU I/O latch, palette corruption on rendering disable, PAL.

## 10. Decisions

- 2026-10-24, one table per ISA: the 2A03 gets its own opcode table and
  interpreter instead of a parameterised 65816 table. The two cores
  share no code; the pattern (table, interpreter, emitter, tracer,
  SingleStepTests) is the same.
- 2026-10-24, block key: (bank state, PC) with the bank state reduced by
  the board to the registers that decide what the CPU fetches; a mapper
  write ends the block (section 3).
- 2026-10-24, DMA stall interface: the board owns the DMA unit and the
  repeated reads; the CPU code sees stolen cycles through the stall hook
  of the bus and never implements DMA rules itself (section 3).
- 2026-10-24, undocumented opcodes: the common model, with the unstable
  ones compared against the suite and counted (section 9).
- 2026-10-24, MMC3 A12 filter: modelled on M2 falling edges with A12
  low (the A12 rise counts when A12 was low across at least three
  falling M2 edges), as a CHOICE with its test setup in
  docs/nes-hardware-spec.md; blargg's mmc3_irq_tests revision B set
  (tested by its author on a Super Mario Bros. 3 board) is the local
  acceptance test, AccuracyCoin has no MMC3 test (NROM cartridge).
  2026-10-25: blargg's mmc3_test_2 and mmc3_irq_tests pass for every
  filter length from three to eight M2 edges and fail for one and two,
  so the wiki's "two falling edges" does not fit this model; three stays.
- 2026-10-25, RDY in the CPU core: two effects of a halted read belong
  to the CPU, not to the DMA unit, and live in the interpreter: the poll
  of a stalled read is made after the stall, and SHA/SHX/SHY/TAS drop
  the high-byte term when the read before the write was held
  (docs/nes-hardware-spec.md sections 3.8 and 4.2). The emitter of phase
  N3 needs the same two rules.
- 2026-10-25, AccuracyCoin over the oracle: where AccuracyCoin
  (TEST-ROM-HW) and MesenCE disagree, MAMR follows AccuracyCoin (six
  tests); where AccuracyCoin leaves a choice between console variants,
  MAMR takes the NES front-loader with a composite RP2C02G (controller
  clocking, sprites on line 0), and where the hardware value is unknown
  (DMC timer at power-on, power-on palette) the primary oracle's value.
- 2026-10-25, MMC3 power-on registers: by the rule above R0-R7 power on
  as MesenCE's 0, 2, 4, 5, 6, 7, 0, 1 instead of 0
  (docs/nes-hardware-spec.md section 3.2); seen in the first frames of
  Super Mario Bros. 3.
- 2026-10-25, NMI during a taken branch: MAMR keeps the wiki's rule (the
  branch delays NMI as it delays IRQ) against MesenCE, which delays IRQ
  only (docs/nes-hardware-spec.md sections 4.3 and 5.7). With input the
  difference changes the course of Super Mario Bros. 3, so frame-by-frame
  comparisons of games against MesenCE end at the first such NMI.
  2026-10-26: decided by a transistor-level simulation of the 6502
  (perfect6502, class SIM): NMI and IRQ are delayed alike, so the rule
  stays and the difference is a finding against MesenCE.
- 2026-10-26, MMC1 and CNROM: a deviation from the phase plan, approved
  by the project owner, so that the 13 blargg suites of nes-test-roms
  on these boards run in MAMR (docs/nes-test-evidence.md section 4.2).
  Scope: the boards those ROMs use, no general mapper library. The MMC1
  ignores a serial write on the cycle after a write; the mapper decides
  this from the CPU cycle of each write, so the emitter of phase N3 must
  hand the mapper both writes of a read-modify-write instruction with
  their own cycles, as the interpreter does.
- 2026-10-26, LXA magic constant $FF instead of $EE (ANE keeps $EE),
  decided by the project owner after blargg's instr_test-v5 and nes cpu
  test 5 (docs/nes-test-evidence.md section 4.2).
- 2026-10-26, block key (phase N3): the bank of the PC's 8 KiB window
  instead of the mapper's full bank state (section 3). A block's code
  depends only on the bytes of its own window, so a key over the other
  windows only duplicates code: with input, Super Mario Bros. 3 entered
  blocks at 4019 keys (PRG mode, R6, R7, PC) for 2841 distinct PRG
  offsets, fixed-bank code up to 21 times; under the window key the same
  run has exactly 2841 keys, one per offset (`nes_headless --pc-stats`,
  line `blocks window_keys`; docs/nes-smb3-survey.md section 4). The
  window is 8 KiB for every mapper, the smallest PRG window of the
  boards in scope.
- 2026-10-26, the emitter and the interpreter read the poll rule from
  one table function (m65_polls_at) and the NMI hijack from one helper
  (m65_nmi_hijack), so a change of the rule reaches both. Phase N3 kept
  the rule of phase N1 bit for bit, including one property found on the
  way: an indexed read without a page cross (abs,X, abs,Y, (zp),Y)
  polled at the start of its last cycle and again at its end, the start
  of the absent correction cycle, so its interrupt latency was one
  cycle shorter than the "start of the last cycle" of section 2.
- 2026-10-26, the second poll of an indexed read without a page cross is
  removed, decided by the project owner: such a read polls at the start
  of its last cycle only. Sources: the NESdev wiki "CPU interrupts"
  (DOC) and a perfect6502 run (SIM, section 1; LDA abs,X without a page
  cross takes an interrupt exactly as LDA abs does,
  docs/nes-hardware-spec.md section 4.3); a console test is still to
  confirm it. Effect, measured the same day: SingleStepTests nes6502,
  m6502_emit_diff and m6502_emit_sst 0 differences; AccuracyCoin
  147/147 in the interpreter and native; blargg's cpu_interrupts_v2
  (local) passes all five tests with screen and result unchanged;
  Super Mario Bros. 3 over 3000 frames without and with input
  byte-identical to the runs before the change, so the comparison with
  MesenCE keeps its first differences (docs/nes-oracles.md section 6).
- 2026-10-26, code below $8000 is not translated in phase N3 (section 3,
  code in RAM): no target game needs it.
- 2026-10-26, audio (phase N4): the channels are not stepped in the
  per-cycle tick but brought up to date on demand (docs/nes-audio-spec.md
  section 1.2); a unit test runs the same register program both ways and
  requires identical samples. The native samples are integer sums so that
  the hash line's snd field is exact across compilers; the output stage
  (doubles) is deterministic per binary and saved in the state. The
  mixer uses the exact formulas, not the wiki's lookup approximation.
- 2026-10-26, hash format 2: apu holds only the channel state MesenCE
  can name in the same terms (no timers, sequencer positions, shift
  registers or sweep dividers); snd is MAMR's alone. The MesenCE
  reference file was written again in format 2.
- 2026-10-27, PAL (phase P, section 11): the region is a load-time
  parameter of the board, resolved from the cartridge database before the
  header; NTSC keeps its arithmetic, its hash header and its state version
  2, PAL writes state version 3 with a region chunk.
- 2026-10-27, the PAL CPU/PPU alignment and access points are MesenCE's
  convention (docs/nes-hardware-spec.md section 7.2), as on NTSC; with
  them MAMR and MesenCE agree in cyc and dot in every frame of the
  European game, and demo_pal lands inside its documented range.
- 2026-10-27, DMA on PAL halts the CPU only in the SYNC cycle
  (docs/nes-hardware-spec.md section 7.4): UNKNOWN on the console, the
  primary oracle's behaviour by the rule of 2026-10-25; a bus flag
  (`M65Bus::stall_sync_only`) the interpreter and the block helpers
  honour, so one binary runs both regions. To be confirmed by a PAL
  console run of the DMA test ROMs (test proposal there).
- 2026-10-26, the NES adapter keeps the saved controller state when a
  state is loaded (it used to take the loading host's pad), so a state
  serialized again right after loading equals the one loaded
  (machine_hash --state-check with a pad script); the host's pad is set
  before every frame as before.

## 11. PAL (phase P)

The European NES (RP2A07 CPU/APU, RP2C07 PPU) as the same machine with
a region parameter. Specification: docs/nes-hardware-spec.md section 7
(clocks, alignment, APU tables, DMA, region of a cartridge),
docs/nes-ppu-spec.md section 18, docs/nes-audio-spec.md section 11, each
statement with its class. Target game: Super Mario Bros. 3 (Europe), PRG
CRC32 80CD1919 (docs/nes-hardware-spec.md section 1).

Rules of the phase:

- The region is a parameter of the machine at load time (`NesRegion` in
  `NesBoardConfig`, resolved from the cartridge database, the header or
  a forced value; docs/nes-hardware-spec.md section 7.5), not a compile
  flag: one binary runs both, and the emitted blocks of a ROM do not
  depend on it (they make bus calls with CPU cycle time stamps; the
  board maps the stamps to dots).
- NTSC stays byte-identical: its time line keeps the arithmetic of
  section 4 (3k + access_dot), its hash files their header (`region=ntsc`
  was in the format from the start) and its save states version 2. Every
  NTSC test of phases N1-N4 runs unchanged as the check (AccuracyCoin
  147/147, blargg, the Super Mario Bros. 3 USA references).
- PAL gets its own identification where a file could be loaded into the
  wrong machine: the hash header says `region=pal`; the save state is
  version 3 with the region as its first chunk (NTSC keeps writing
  version 2, which reads as NTSC; a state of the other region is refused
  on load).
- The oracles run in PAL mode (MesenCE `--nes.region=Pal`, MAME driver
  `nespal`); where they differ from each other or from MAMR the
  difference is recorded and judged by a PAL test ROM or the
  documentation, never by aligning MAMR to one of them.

Plan:

- P1 specification (the three sections above), the test catalogue
  below.
- P2 run time: region resolution and override; board time line with the
  PAL master clock offsets (hardware spec 7.2); PPU frame of 312 lines
  without the skip, the forced OAM refresh, no row copy, emphasis order;
  APU tables by region; the machine's description (50.007 Hz, 41,565
  Hz audio), the border in the RGB picture; hash header and save state.
- P3 oracles: MesenCE and MAME in PAL mode, the PAL test ROMs, Super
  Mario Bros. 3 Europe over 3000 frames against both, the first
  difference of every field (docs/nes-oracles.md section 8).
- P4 native: discovery and emission for the European ROM, the artefact
  smb3-eu.mamrcart, a native run with 0 misses, the play round trip with
  sound.

Test catalogue (name, kind, judge):

| test | kind | judge |
|---|---|---|
| nes_board: region from database, header (iNES byte 9, NES 2.0 byte 12) and force; database wins | unit | DOC (hardware spec 7.5) |
| nes_ppu: PAL frame 106,392 dots with and without rendering; flag set (241, 1), clear (311, 1); OAM refresh moves OAMADDR by 140 per frame with rendering off; emphasis order; no row copy | unit | DOC (PPU spec 18) |
| nes_board: PAL access points of a read, a write and the cycle end for k = 0..9 | unit | CHOICE (hardware spec 7.2) |
| nes_apu / nes_audio: PAL frame counter steps in both modes and the IRQ period; noise periods; DMC rates; DMC timer at power-on | unit | DOC, TEST-ROM-HW |
| nes_hashline: header region=pal for a PAL machine, region=ntsc unchanged | unit | format |
| machine state: a PAL state is version 3 and loads into a PAL machine only; an NTSC state stays version 2 byte for byte | unit / machine_hash --state-check | format |
| blargg pal_apu_tests 01-11 (10 ROMs) forced PAL | local, testroms.py | TEST-ROM-HW |
| blargg nmi_sync demo_pal forced PAL: the line inside the reference range | local, picture | TEST-ROM-HW (range) |
| the same ROMs under MesenCE PAL and MAME nespal | local, oracle | EMU |
| Super Mario Bros. 3 Europe, 3000 frames without input and with an input script: MAMR against MesenCE PAL and MAME nespal, first difference per field | local, oracle | EMU, findings judged by the rows above |
| gate G1 for PAL: stage S against stage E, interpreter against native | local | MAMR |
| native run of the European ROM with 0 misses, play_roundtrip with sound, the artefact through the build | local | MAMR |
| every NTSC test of N1-N4 unchanged | ctest | the N1-N4 judges |
