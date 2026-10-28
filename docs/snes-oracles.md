# SNES oracles: setup, limits, results

Phase S8 of snes-architecture.md. The oracles write the hash lines of
snes-oracle-format.md; `compare.py` compares them, `gates.py` runs the
gates. MAMR itself is not part of any of this yet (gate G1 is prepared,
section 7). Results below are from 2026-10-24 on x86-64 Linux. File names without a directory refer to `tools/oracle/snes/`.

| oracle | role | licence | build | F/A/P lines | speed, 600 frames |
|---|---|---|---|---|---|
| aresref (ares c76aaff) | primary oracle, timing reference | ISC | external checkout plus 9 patches | all fields | about 150 frames/s (4 s); 126 on the PAL game |
| MesenCE 2.2.1 | second oracle (NTSC only, see 3) | GPL-3 (external tool) | release binary | all fields | 31 frames/s; 12 with P lines on spctest; 14 on the PAL game |
| MAME 0.285 | weak cross-check | GPL-2+ / BSD-3 (external tool) | distribution package | cpu, wram, vram, cgram, img (aram with an IPL dump) | 30 frames/s |
| bsnes (libretro) | not used | GPL-3 | | none | |
| snes9x | smoke test only | non-commercial | | none | |
| MiSTer smpsim | candidate audio oracle | GPL-3 | not built | none | |

None of them is linked into MAMR or shipped with it.

## 1. Test ROMs

gilyon/snes-tests v1.4 (MIT), release asset `snes-tests.zip` from
`https://github.com/gilyon/snes-tests/releases/download/v1.4/snes-tests.zip`,
unpacked to `tests/data/snes-homebrew/v1.4/` (local, not distributed):

| file | SHA-256 / SHA-1 |
|---|---|
| snes-tests.zip | sha256 `c3a39e15a9f3789fe143e54dfa035c988204576eafacf97df8ff3546a917c5e9`, sha1 `462e60618686d83bd0d5d4334da1f03fc1d624c4` |
| cputest/cputest-basic.sfc | sha1 `61e0403898fb295cd491cdf5eb5816b5856be85d` |
| cputest/cputest-full.sfc | sha1 `f91d99ec1dc89f3b201c503f32adad499d246c6c` |
| spctest/spctest.sfc | sha1 `1139b6cc092aa5862177a0d33dcdfc6bce2bcb3f` |

By frame 600 all three show "Success" (cputest-full test number 0649,
spctest 0557) in aresref and MesenCE, checked on the dumped pictures by
eye, not by a gate. PeterLemon/SNES has no licence and is not used. The
gates and ctest use only these ROMs; the commercial target game is run
locally (section 6) and nothing of it enters the repository.

## 2. aresref

`aresref/aresref.cpp` is a headless ares front end (an `ares::Platform`
without GUI) that writes F, A and P lines, reads the shared input script,
dumps canonical field bytes and injects faults. Build:

```bash
tools/oracle/snes/aresref/build_aresref.sh --fetch ARES_DIR [BUILD_DIR]
```

clones ares at commit `c76aaffa6e69778baf9a66d1da04298ac2ed7d1d` (or uses
an existing checkout or git worktree there), applies `patches/ares/*.patch` to its
working tree and builds only the `sfc` core, `mia` and aresref (about two
minutes with 16 cores). The applied patch set is recorded in
`ARES_DIR/.aresref-patches`; a later run with changed patches restores the
patched files from git first. Usage: `aresref ROM --frames N [options]`,
see the head of aresref.cpp. The region (NTSC or PAL) comes from the
cartridge (`--region` overrides); cartridge RAM is saved to a private
temporary directory that is removed after the run, so a saved game never
leaks into the next run. Without a save file ares allocates the save RAM
filled with $FF; the `sram` field hashes it.

The patches:

| patch | why |
|---|---|
| 0001-build-without-gui | ruby, hiro, desktop-ui and .github are skipped when `ARESREF_SOURCE_DIR` is set (they pull in GTK 3); the aresref directory is added instead |
| 0002-video-unthreaded | `Video::Threaded = false`: the threaded screen refresh made runs differ |
| 0003-absolute-clocks | `Thread::clock()` is rebased at every `Scheduler::exit`; an absolute master-clock counter per CPU tick and an SMP clock counter in `SMP::step` give `mclk` and the P line times |
| 0004-oracle-hooks | hooks for the sampling point (the window opens at line 225, or 240 with the overscan latched at V=0; the frame hook runs at the next instruction boundary in `CPU::main`, after SMP, DSP and PPU are synchronized), the auto-joypad read, the PC anchor (before every instruction), PPU writes (the write shadow) and APU port writes; the SMP and CPU members the front end reads are made public |
| 0005-zero-entropy-option | option "Zero Entropy": every value ares would draw at power-on from its generator is 0, which matches MesenCE's AllZeros (snes-oracle-format.md section 6) |
| 0006-reset-stack-reads | the reset sequence performs its stack cycles as reads, as the WDC W65C816S datasheet specifies (section 2.25, table 5-7); unpatched ares writes them and leaves $24 at $0001FD. MAMR follows the datasheet; with this patch the reference files can be met, and aresref agrees with MesenCE |
| 0008-picture-at-vdisp | the picture is copied at the start of scanline vdisp (225, 240 with overscan), from CPU::scanline after the PPU has been synchronized to the CPU, through a new hook `oracleHooks.picture`; before, `img` was read at the sampling boundary from `screen->pixels(0)`, which with overscan raced ares' buffer swap in `screen->frame()` at V=240 H=0 and came back black in 208 of 300 frames of the SNES Test Program (U). Without overscan the copy is the same rows as before (checked: cputest-basic 600 frames and Zelda DE and USA 3000 frames unchanged; the rebuilt aresref writes the same Zelda files byte for byte, section 12.1) |
| 0007-smp-instruction-boundary | at the sampling point the SMP runs to its first instruction boundary at or after the CPU's clock instead of stopping inside an SMP instruction (`Thread::synchronize` stops at a bus cycle); the CPU clock is moved far ahead while it runs so that the SMP does not yield, then restored. The DSP follows in `SMP::step`. Format version 3 requires this point, and MAMR samples there. Alone it let the CPU see what the SMP did in that run (finding F3, closed by 0009) |
| 0009-smp-sample-on-copy | the run of 0007 happens on a copy: before it the SMP and the DSP are saved with ares' own serializer (`SMP::serialize`, `DSP::serialize`; outside a synchronizing save `Thread::serialize` copies the thread's whole stack, so the suspended SMP and DSP threads are saved mid-instruction), after the frame hook they are restored, and the SMP clock counter of patch 0003 with them; SMP port writes made during the run do not call `apuWrite` (`oracleHooks.smpAhead`), they are logged when they happen for real. The hash line is the same as before, the emulated time line is that of ares without the sampling point (trap below) |

Trap with overscan, closed by patch 0008 (2026-10-24): ares presents the
picture at V=240 H=0 (`ppu/main.cpp`, `screen->frame()` swaps the two
pixel buffers before line 240 is drawn); with SETINI bit 2 that clock is
the sampling window, and an `img` taken at the first instruction
boundary after it read either the finished frame or the other buffer,
depending on which thread ran first (the SNES Test Program (U): black in
208 of 300 frames, section 12.1). The picture is now copied in
CPU::scanline at the start of line vdisp, right after the PPU was
synchronized to the CPU: the PPU has drawn every line before it and has
not entered its code for the line, so the copy is deterministic in both
cases. No reference file uses overscan.

Trap at the sampling point, closed by patch 0009 (2026-10-25; finding F3
of docs/snes-rom-survey.md): with 0007 alone the SMP really executed the
rest of the instruction that straddles the sampling clock T, up to its
next boundary B (at most one SMP instruction, a few hundred master
clocks), while the CPU stood at T; then the CPU went on from T against an
SMP that was already at B. ares' only coupling between the two are the
four port pairs (`CPU::readAPU`/`writeAPU` and `SMP::readIO`/`writeIO`
synchronize first, then use the latch), so the time line broke there in
both directions: an SMP write to $F4-$F7 in (T, B] was in the latch for
CPU reads before its time, and an SMP read of $F4-$F7 in (T, B] had
already taken place without a CPU write made after T but before the
read. Both show on the handshake test ROM (`tests/snes-timing/rom/apuport.s`,
an endless IPL upload, 600 frames). Without its two poll-counter
instructions the ROM shows them only in the P lines: in 16 frames the
CPU's port writes come 156 to 300 clocks late over the next four to six
bytes (once, frame 506, up to 1548 clocks over 230 writes), and the
handshake catches up before the next sampling point, so every F line
stays equal; a draft that kept the ARAM address in X also showed the
other direction (writes 52 clocks early, one CPU poll-loop turn: the
echo seen early). One of the late cases, traced in the P lines:
sampling clock 4952670,
the CPU's write of the next index to $2140 30 clocks later; in the run
of 0007 the SMP read port 0 before that write, took one more turn of the
IPL's poll loop ($FFDA-$FFE9, 11 SMP cycles), echoed 11 SMP cycles late,
and the CPU's next write came 300 clocks late. The final version of the ROM
counts its poll turns in X and WRAM; against it the 0008 build differs
from frame 9 on in cpu, smp, wram and mclk (cpu 591 frames, smp 592,
apuio 591, wram 592, aram 588, mclk 500), and its CPU port writes run up
to 1096 clocks early. With 0009 every F line and all 569732 CPU port
writes (P lines with their times) are equal to MAMR stage S and E.
Chrono Trigger, Super Bomberman 5, Super Metroid and Contra III were
affected the same way (docs/snes-rom-survey.md, F3).

The alternatives that were weighed:

| option | effect | why not |
|---|---|---|
| run the SMP only to the CPU's clock (the state before 0007) | no time line effect | the SMP is caught inside an instruction: half-done registers and bus state; contradicts format version 3, MAMR and MesenCE sample at the boundary |
| sample at the last SMP boundary before T | no run ahead | needs either a snapshot at every SMP boundary inside the window (64 KiB of ARAM per instruction while a GP-DMA delays the CPU boundary) or an undo log of every SMP and DSP write; the DSP state at that earlier clock is not available at all; it is a different rule from MAMR's and MesenCE's and would need a new format version |
| defer the SMP fields until the real SMP reaches its boundary | no run ahead | CPU port writes between T and that boundary would enter the line, which MAMR's copy never sees; the F line would be assembled from two moments |
| hold back the SMP's port writes (a latch with time stamps) | fixes the SMP-to-CPU direction | the CPU-to-SMP direction remains: an SMP read in the run has already happened (the late cases of the test ROM) |
| save, run, sample, restore (chosen) | the line is the state at B as if the CPU stood still at T, exactly MAMR's `smp_at_sample` copy; the emulated time line is that of ares without the hook | none found: it uses the mechanism of ares' own save states, costs two serializer passes per frame (about 300 KB; Zelda DE 3000 frames still 26 s) |

Completeness was checked once with a diagnostic build (not published): before the save and after the restore the raw bytes of the
SMP, DSP and CPU objects and both thread stacks were compared at every
sampling point; no difference in 1000 samples of the handshake ROM and
3000 of Zelda USA. MAMR's sampling needed no change: its rule (a copy of
the SMP run to its first boundary at or after T, the real one stays
behind) is what the format describes, and the oracle now does the same.
With 0009 the earlier reference files are reproduced byte for byte: Zelda
DE and USA 3000 frames (local hash files, not published), the three
gilyon files (tests/snes-oracle/reference) and both stall files
(tests/snes-timing/reference).

The patch files are changes to ares and carry ares source lines as
context; they are under ares' ISC licence (text and notice in
third_party/ares/LICENSE), not under the repository's BSD-3.

Traps found on the way: nall's `Arguments` rewrites any argument naming
an existing directory into its parent path (aresref therefore has its own
`main`); mia needs its `Database/` next to the executable (copied by the
build).

## 3. MesenCE

MesenCE 2.2.1 (`nesdev-org/MesenCE`, successor of SourMesen/Mesen2),
`Mesen_2.2.1_Linux_x64.zip`, sha256
`c88ff4d251b407515c43d3332d641927655cd69fb538996b6a21da4509dbb58f`.
`mesen/run_mesen.sh rom.sfc mesen/snesfh.lua` starts it in test-runner
mode with `--snes.ramPowerOnState=AllZeros` (or AllOnes with
`MESEN_FILL=ff`), `--snes.disableFrameSkipping=true`,
`--debug.scriptWindow.allowIoOsAccess=true` and
`--snes.port1.type=SnesController`; the script is configured through
`FH_*` variables (head of snesfh.lua).

Traps:

- Without `$HOME/.config/MesenCE/settings.json` (note: `MesenCE`, not
  `Mesen2`) MesenCE ignores `--testrunner` and opens its graphical setup
  wizard. run_mesen.sh creates the file (content `{}`) in a private HOME
  (`MESEN_HOME`, default `~/.cache/mamr-mesen-home`) and runs MesenCE
  under `xvfb-run` when present, otherwise without DISPLAY, so no window
  can appear.
- With that empty configuration no controller is plugged into port 1 and
  `emu.setInput` does nothing; hence `--snes.port1.type=SnesController`.
- `emu.getScreenBuffer()` is 256 x 239 with scanline v in row v + 6
  (rows 0-6 and 231-238 blanked) unless overscan is on.
- `ppu.cgramAddress` is the incremented CGRAM address,
  `ppu.internalCgramAddress` the one the renderer uses.
- `spc.cycle` advances by two per SMP cycle.
- The SMP runs behind the CPU and is caught up when MesenCE finishes the
  frame (before the sampling point) and on port accesses.
- MesenCE writes battery RAM to `Saves/<rom>.srm` in its home and loads it
  at the next start; run_mesen.sh deletes `Saves/` and `Debugger/` before
  each run.
- PAL timing is wrong in MesenCE 2.2.1: the NTSC short scanline (line 240
  with 1360 clocks in every second frame without interlace) is applied
  in PAL too, and the PAL long line (1368 clocks at V=311 of interlace
  field 1) is missing (`SnesPpu::ProcessEndOfScanline`, no region check).
  PAL frames are therefore 2 clocks shorter on average than in ares and
  on the hardware (312 lines, no short line), and the CPU phase against
  the picture drifts. MesenCE is not a PAL timing oracle.
- MesenCE fills cartridge save RAM according to the RAM power-on switch
  (00 or $FF); the script writes $FF over it before the first instruction
  (format section 6).
- The SMP is caught up when MesenCE finishes the frame, to its first
  instruction boundary at or after that moment, a few clocks before the
  sampling point; aresref and MAMR use the sampling point itself.
- The SPC clock is the measured 32040 Hz (`SpcClockSpeedAdjustment`
  default 40, `spc.clockRatio` 0.095476), the same as ares: `clk=meas`.
- MesenCE starts the auto-joypad read 128 master clocks earlier than ares
  (first multiple of 256 clocks after H=130, minus 128).

Sampling: the script registers an exec callback over the whole address
space at each `endFrame` event (raised inside the instruction that crosses
the window) and removes it at its first call, which is the first
instruction boundary after the window; `mclk` is MesenCE's master clock
there. On cputest-basic it agrees with aresref in all 600 frames.

## 4. MAME 0.285 (weak cross-check)

`mame/run_mame.sh rom.sfc` with `mame/snesfh_mame.lua`. Limits:

- MAME refuses to start without `snes/spc700.rom` (the 64-byte IPL, Sony's
  code; it is never part of the repository). With `MAME_IPL=<dump>` the
  dump is used and `aram` is written. Without a dump the script installs
  a 64-byte zero placeholder: MAME starts with a checksum warning, the
  SPC700 runs garbage, only the CPU side is meaningful, and every SPC-side
  field is `-`. This is documented, not worked around; spctest
  accordingly fails under MAME without a dump.
- No DRAM refresh (the anchor delta on cputest's loop is 52 only, ares
  and MesenCE alternate 52 and 92), SPC700 at the nominal 24.576 MHz / 12
  (`clk=nom`; compare against aresref with `--allow-clk`), DMA costs no
  CPU time. The `snes` driver is NTSC (`region=ntsc`).
- `m_totalcycles` per frame jitters by about 24 clocks; `mclk` is that
  counter and not comparable.
- Sampling point is `frame_done` (frame 1 at clock 357382, one full frame
  later than scanline 225 of frame 1); `anc` is `-`, inputs are not driven.
- OAM is kept only decoded, the PPU registers not in canonical form, the
  DSP registers, APU ports and S-SMP timers are not exposed: `oam`, `ppu`,
  `dsp`, `apuio`, `smp` are `-`.
- Power-on fill is $55 (`fill=55`); the debugger, if enabled, slows MAME
  down to a third.
- Deterministic: two runs of spctest gave byte-identical files.

Against aresref on cputest-full (600 frames): `cgram` equal in every
frame, `img` equal except one frame (the frame boundaries differ), `vram`
equal from frame 164 on (before that the $55 fill shows), `cpu` and
`wram` differ (sampling point, fill).

## 5. Other candidates

- bsnes through libretro (GPL-3) builds, but the libretro interface
  exports no memory, only a save-state blob, and `ppu_fast`/`dsp_fast`
  are on by default. Not used.
- snes9x fails gilyon cputest-full at test 27; smoke test only.
- MiSTer `smpsim` (SNES_MiSTer, checked at bdcd33c, GPL-3): a GHDL test
  bench for the SPC700 plus S-DSP RTL (`rtl/SPC700/*`, `rtl/SMP.vhd`,
  `rtl/DSP.vhd`); ARAM and audio output are C functions bound through
  VHPIDIRECT (`aram_c.c` reads `snes.spc`, `audio_c.c` writes `snes.aud`,
  32 kHz stereo 16-bit raw). GHDL 5.0.1 is available on Ubuntu 26.04. Not
  built here (only documented); as an audio oracle it needs an `.spc`
  writer on our side (ARAM, DSP registers and SMP registers are already
  in the dumps) and a PCM comparison. The IPL constant inside
  `rtl/SMP.vhd` is Sony's.

## 6. Gate results

Format version 3 (sampling at the first instruction boundary after the
window), fill 00, 600 frames, P lines on, unless noted; 2026-10-25.

**G2** (each oracle twice, byte-identical):

| ROM | aresref | MesenCE |
|---|---|---|
| cputest-basic | identical, 161 frames/s | identical, 32 frames/s |
| cputest-full | identical, 158 frames/s | identical, 32 frames/s |
| spctest | identical, 143 frames/s | identical, 12 frames/s |
| the PAL target game (local only, no input, P lines off) | identical, 131 frames/s | identical, 15 frames/s |

**G3** (WRAM byte $1000 XOR $5A at frame 60, 120 frames): for both
oracles compare.py reports `first divergence: frame 60 fields wram` and
nothing else. **Dump check**: the dumps of both oracles rehashed by
hashline.py reproduce every field of their F lines, so the C++, Lua and
Python implementations of the format agree.

**Cross-check aresref against MesenCE, cputest-basic, 600 frames**
(`gates.py cross ROM --dump-every 50`, format version 3):

- Every field except smp is equal in all 600 frames, and so is mclk (the
  sampling boundary) and anc: cpu, apuio, wram (unmasked), vram, oam,
  cgram, ppu, aram, dsp, img, sram (empty: no save RAM).
- wram in the bytes the program defined (mask from fill 00 and fill ff
  runs of both oracles; 106 bytes at frame 50, 630 from frame 150 on):
  equal in all 12 dumps. With patch 0006 the unmasked wram is equal too
  (format version 1 showed $0001FD = $24 from ares' reset writes).
- smp differs in every frame only in its last three bytes: the S-SMP
  timer stage-3 counters power on as 0 in ares and as 15 in MesenCE (the
  program never enables a timer). The hardware value is unknown here.
  The SMP registers, CONTROL, DSPADDR and the targets are equal.
- A lines on $00:8260 (cputest's wait loop): identical in pc, mclk and d.
  Their `anc` (compared only with --timing) differs for hits between the
  two read starts, since MesenCE starts the auto-joypad read 128 clocks
  earlier.

**cputest-full and spctest** (informative): the CPU phase of the two
emulators differs by a few clocks in parts of the programs. On
cputest-full the time between two hits of the anchor $00:8263 that span
the code after the wait loop is 39166 clocks in ares and 39176 in MesenCE
(frame 21); afterwards the sampling boundary falls on different
instructions in 580 of 600 frames, and cpu differs in 86 frames; the SMP
side (smp without the timer counters, aram, dsp, apuio) is equal in all
frames. On spctest the port traces are identical in sequence on both
sides (155350 CPU writes, 80413 SMP writes) but the CPU write times
differ by -24 to +126 clocks: the CPU/SMP handshake runs at a different
pace in the two emulators, so the SMP program is at a different point
when either is sampled. With patch 0007 (and 0009, which writes the
same aresref file for spctest), cpu differs in 59 frames, aram
in 60, apuio in 42, wram and vram in 2; even in the 30 frames whose
sampling clock is equal in both oracles the SMP state differs in 19.
This is not a sampling question and cannot be compared away; which
emulator is right is not established (candidates: DMA and NMI entry
timing, the handshake itself). For SMP-side comparisons of MAMR, aresref
is the reference.

**MAMR against aresref (reported by the 65816 emitter work, S5b
headless front end, format version 2 with this aresref):** cputest-basic
and cputest-full are identical over 600 frames including mclk once WDM
is charged as an 8-clock signature fetch as ares does. MAMR kept the 6
clocks of SingleStepTests until the research of 2026-10-24
(docs/snes-hardware-spec.md section 4.2); since then the table fetches
the byte and the cputest tests compare mclk and pc as well, with no
tolerated frames. The remaining differences were in smp, aram and dsp
from ares stopping the SMP inside an instruction, which patch 0007
removes.

**The PAL target game, 600 frames without input** (local only, ROM and
hashes stay outside the repository): both oracles detect PAL and
`clk=meas`; G2 holds for both. img, oam, cgram and sram (8 KiB, the game
writes 8 bytes during the intro) are equal in all 600 frames. vram
differs in 88 frames (from frame 68), wram in 408 (in the defined bytes
only 1 to 7 stack bytes at $0001FC-$0001FF per dumped frame), cpu in 333,
aram in 340, dsp in 209, apuio in 45, ppu in 1 (frame 170: the sampling
points are 246 clocks apart, so the VRAM address and the last $2118 byte
differ; with format version 3 ppu differed in 44 frames through the
internal OAM address): the CPU phase differs, partly from
MesenCE's PAL timing (section 3; its frames are on average 2 clocks
shorter, 425566.1 against 425568.0 master clocks per frame), partly from
the CPU phase differences also seen on cputest-full (the same ROM forced
to NTSC in both oracles still differs in cpu, wram and vram). For PAL
titles aresref is the only timing oracle; MesenCE remains a picture
oracle. (An earlier version of this note reported img differing in 491
frames and blamed MesenCE's timing; the cause was aresref reading PAL
rows from the NTSC border offset, 26 instead of 22 half-pixels, which
shifted the PAL picture by 2 pixels. Found by the 65816 emitter work
against MAMR, fixed in aresref.)

**Stage E against aresref** (2026-10-24, format version 4, fill 00, no
input, original IPL dump; `snes_headless --exact`, docs/snes-architecture.md
section 4):

- The PAL target game, 1400 frames: equal in every field, mclk and pc
  included, in every frame (0 differences; local only). Repeated on
  2026-10-24 after the research package A changes (WDM fetch, the SMP
  clock as a parameter) over 3000 frames, stage S and stage E: equal in
  every field, mclk and pc included. The game writes SETINI = 0 in every
  dumped frame (no interlace), so the PAL long line (hardware-spec 2.1)
  is never reached in this run; ares applies the same rule.
- cputest-basic, cputest-full, spctest, 600 frames: equal in every state
  field, anc, mclk and pc (ctest `snes_system_exact_gilyon_*`, strict
  since 2026-10-24). Before the WDM decision (docs/snes-hardware-spec.md
  section 4.2) the cputest sampling clock was 2 clocks early per WDM
  executed (MAMR priced its second cycle as internal, 6 clocks; ares
  fetches it, 8), and the boundary moved by a loop turn in some frames
  (+18 to +26 clocks), which showed as a different N/Z in the cpu field
  of 1 (basic) and 11 (full) frames. With the fetch both stages equal
  aresref in every field, mclk and pc included, on both cputest ROMs.
- The stall timing acceptance ROM (tests/snes-timing, NTSC and PAL, 600
  frames): equal to its aresref references in every field, mclk
  included, in every section (HDMA sets, GP-DMA start variants, GP-DMA
  meeting the line HDMA, refresh only). It found the one stage E error
  of the first build: an HDMA due at the DMA edge after a channel's last
  byte must still run inside the GP-DMA (sections 3 and 7).
- A synthetic ROM that enables NMI with a 16-bit STA $4200 in VBlank:
  aresref and stage E take the NMI after the following instruction,
  stage S after the STA (hardware-spec 2.8).

**Stage S against stage E** (gate G1 between the stages,
tests/snes-system/compare_stages.py). After the stage S stall fix
(DMA, HDMA and refresh booked at the CPU cycle grid, section 4 of
docs/snes-architecture.md): equal on the PAL target game over 1400
frames in every field, mclk and pc included, and on the gilyon ROMs and
the stall ROM (both stages equal to the references). Before the fix:

- gilyon cputest-basic, cputest-full, spctest, 600 frames: equal in every
  field, mclk and pc included (ctest `snes_system_stages_gilyon_*`).
- The PAL target game, 1400 frames: 74 frames differ, all from frame 1325
  on, the first sampling point after the game's first HDMA (1325-1329,
  1331-1334, 1336-1400): mclk in 72 (stage S minus stage E -82 to +80 clocks, no
  drift), wram in 67, pc in 41, cpu in 43, smp in 15, aram in 12, dsp in
  7; never anc, apuio, vram, oam, cgram, ppu, img or sram. Stage S
  against aresref gives the same list, since stage E equals aresref.
  The picture and the PPU state stay equal: the stage S HDMA coupling
  (start at the trigger clock plus alignment, resync to a constant 8
  instead of the cycle that waited, hardware-spec 3.4) moves the end of
  the HDMA by a few clocks, and that moves the sampling boundary by one
  turn of the game's wait loop (about 72 to 82 clocks), with the CPU,
  WRAM and SMP state of that other boundary.

With the same input script both oracles latch the same joypad word at
every auto-joypad read (checked with `--trace-joypad` / `FH_TRACE_JOY`).

**APU clock.** aresref (`apuFrequency = 32040 * 768`) and MesenCE (32000 +
40 Hz) both run the measured rate, `clk=meas`. MAMR runs in its 32040 Hz
mode for every hash comparison against them; the nominal 24.576 MHz
(`clk=nom`, MAME) is a separate timing and is compared only with
`--allow-clk`.

**CPU clock rounding in ares.** ares sets a thread's frequency as
`frequency + 0.5` truncated (`Thread::setFrequency`), so the NTSC master
clock 236.25 MHz / 11 = 21477272.7 Hz becomes 21477273 Hz, and the SMP to
CPU ratio follows from that integer. With the exact 236.25/11 MHz MAMR
lost a port-polling race on spctest (frame 28). For `clk=meas`, MAMR
therefore uses the SMP clocks per master clock of ares,
1025280 / 21477273 (32040 Hz * 32 SMP cycles per sample = 1025280 SMP
cycles per second).

**Cartridge save RAM.** Without a save file ares allocates it filled with
$FF; MAMR does the same. The target game checks a $55AA signature in it at
start, so its content enters the game state; from format version 3 it is
the field `sram`.

## 7. Gate G1 (MAMR against MAMR), for later

Once MAMR's runtime writes hash lines (snes-oracle-format.md section 11):

```bash
python3 tools/oracle/snes/gates.py g1 --cmd "$BUILD/games/zelda/zelda_headless --frames 600 --hash-out {out}"
```

runs the command twice and requires byte-identical output; `--cmd2` gives
a second command (stage S against stage E). The command line above is a
placeholder for the front end that does not exist yet. For the headless
system, stage S against stage E is
`tests/snes-system/compare_stages.py HEADLESS ROM --frames N [--ipl FILE]
[--list]` (snes_headless with and without `--exact`).

## 8. ctest

`tests/snes-oracle/CMakeLists.txt`:

- label `oracle-free`: self tests of hashline.py, input_script.py,
  compare.py and gates.py on synthetic data, and the format and chain
  check of the reference files `tests/snes-oracle/reference/*.hash`
  (aresref, fill 00, F lines only, 600 frames, one per gilyon ROM).
- label `oracle`: one test per oracle (`snes_oracle_aresref_cputest_basic`,
  `snes_oracle_mesence_cputest_basic`), so a missing MesenCE cannot hide
  an aresref failure: G2 on cputest-basic over 300 frames, then aresref
  equal to the reference in every field and in mclk, MesenCE in every
  field except smp (`MESEN_REFERENCE_FIELDS` in gates.py). Both files must
  hold at least 300 F lines. A test skips (exit 2) only when its ROM or
  its oracle is missing. Oracles from the cache variables `SNES_ARESREF`,
  `SNES_MESEN` or the environment (`ARESREF`, `MESEN`) or PATH.

```bash
ctest --test-dir $BUILD -L '^oracle-free$'
```

```bash
ctest --test-dir $BUILD -L '^oracle$'
```

When MAMR runs, the oracle-free reference comparison turns into MAMR
against these files.

`tests/snes-system/CMakeLists.txt`, label `oracle-free`: MAMR's stage S
(`snes_system_gilyon_*`) and stage E (`snes_system_exact_gilyon_*`,
spctest with `--mclk`) against these files, and stage S against stage E
(`snes_system_stages_gilyon_*`, every field, mclk and pc); the screens
of eight undisbeliever auto-joypad ROMs against their expected tables
(`snes_system_undisbeliever_*`, section 11). Label `oracle`: all 27
undisbeliever ROMs (eight with a recorded finding, section 11) and
wrmpyb-in-flight (stage E, section 12) against aresref
(`snes_oracle_undisbeliever_*`). Label `local`:
`snes_system_exact_zelda_local`, stage E against an aresref file of the
PAL target game made on the local machine (cache variables
`SNES_ZELDA_ROM`, `SNES_ZELDA_REF`; 1400 frames, no input, every field
with mclk and pc); it skips without them.

```bash
ctest --test-dir $BUILD -L '^local$'
```

## 9. Stall timing test ROM

`tests/snes-timing/` holds an own test ROM (65816 source plus a small
Python assembler, NTSC and PAL builds) that makes HDMA (direct and
indirect, 1, 2 and 4 bytes per line, up to 6 channels), the HDMA setup,
GP-DMA on 1, 3 and 8 channels (also across V=0) and DRAM refresh hit
6-, 8- and 12-clock CPU bus cycles at every phase, and logs the latched
H/V counters into WRAM after each stall. Each frame runs one of eight
sections from a clock fixed by the program, so a difference stays in its
frame. aresref and MesenCE pass G2 on both builds. On NTSC they agree in
every field and in mclk in all sections except the two where a GP-DMA
meets the per-line HDMA (sections 3 and 7: wram in 73 and 66 of 75
frames, mclk in 54 and 45, -36 to +60 clocks); on PAL MesenCE's frame
timing differs as described in section 3. The reference files
(`tests/snes-timing/reference/`, 600 frames) come from aresref;
`snes_timing_stall_ntsc` / `_pal` (label oracle-free) compare MAMR with
them in every field including mclk. Since the stall fix (stage S books
DMA, HDMA and refresh at the CPU cycle grid, docs/snes-architecture.md
section 4) MAMR is equal to them in every frame of every section on both
builds, and on the PAL target game in every field over 3000 frames, the
sampling clock included; the tests are strict. Details, the rule cases for
the board and the Zelda script `run_zelda_timing.py` (not published):
tests/snes-timing/README.md.

The same directory holds a second own ROM for the SMP side of the
sampling point (`rom/apuport.s`, an endless upload through the IPL
protocol, so that both processors poll the APU ports at every sampling
point). It is the test for patch 0009 (section 2): aresref with it and
MAMR in both stages agree in every field, mclk and pc over 600 frames
(`snes_timing_apuport`, `snes_timing_apuport_exact`, label oracle-free,
need the IPL dump; `snes_timing_aresref_apuport`, label oracle, fails
with an aresref built without 0009).

## 10. Known deviations against aresref

Where MAMR follows a hardware source against ares, the comparison with
aresref differs by design. The list (kept current; everything not listed
here is expected to be equal in every field, mclk and pc included):

| Item | MAMR | ares / aresref | Source for MAMR | Where it shows |
|---|---|---|---|---|
| HV-IRQ with HTIME=0 | TIMEUP at H=10, like the V-IRQ | H=14 | TEST-ROM-HW paulb_nl, plus byuu/Anomie's 10-clock V-IRQ delay (hardware-spec 2.4) | an IRQ handler entered 4 clocks earlier; no gilyon ROM or the PAL target game uses HTIME=0. undisbeliever's auto-joypad ROMs align every pass with an HTIME=0 IRQ (VTIME=210), so against aresref cpu, wram, vram, img and mclk differ from frame 5 on in joypad-latch-set/clear-during-autojoy, blip-autojoy-test, enable-autojoy-late-test-2, joyser0-read-during-autojoy (and the three clear-autojoy ROMs below); with ares' H=14 built in for a check, those five were equal in every field over 300 frames (section 11) |
| HV-IRQ with VTIME=0, HTIME=339 | two IRQs per field (H=6 of line 0 and of line 1) | one (line 1 only) | TEST-ROM-HW paulb_nl, one console (hardware-spec 2.4) | only with that register pair; ctest `snes_system` and `snes_system_exact` |
| Reset stack cycles | reads at S, S-1, S-2 of the present S, S.l 3 lower, no write | writes PC and P there (unpatched ares) | DATASHEET WDC 2.25 and MEASURED (srg320's capture of the S-CPU reset, hardware-spec 5.5) | aresref carries patch 0006 (section 2), so the reference files agree with MAMR; unpatched ares differs in wram at $0001FD-$0001FF; both start from S=$01FF at power-on |
| Reset button (Timing::reset, Board::reset) | the PPU counters start from V=0 H=0 of field 0 at the release, interlace and overscan off, the clock grids from there; HTIME/VTIME, maths and $43xx kept | restarts the counters and resets every register (`like_ares`) | DATASHEET + INFERENCE (Visual 5C78/5C77 netlists, rgalland's S-CPU-A) and MEASURED (spla: the button pulls /RESET of both PPUs), hardware-spec 2.8, 5.4 | none: no runner presses the button |
| Auto-joypad latch pulse | 256 clocks, T0-128 to T0+128, following $4200 bit 0 inside the pulse; a clear during the read shifts in a bit already sampled | 128 clocks (T0 to T0+128) | width MEASURED (Ownasaurus, 12.04 us), position DATASHEET + INFERENCE (rgalland's S-CPU-A schematic, 2026-10-26; hardware-spec 2.5, 2.6, 5.3) | a manual $4016 read or write, or a $4200 write, between T0-128 and T0: enable-autojoy-late-test-2 and clear-autojoy-1st-vb-sl print 0000 (pads latched) in the boundary rows where aresref prints FFFF (screen tables accept both; the oracle tests' recorded first divergence and fields are unchanged); a clear in a clock-low phase (clear-autojoy-after-autojoy-active with B held: JOY1 0001); no gilyon ROM and not Zelda |
| Interlace latch (SETINI bit 0 for the field length, short and long line) | the value at the start of VBlank (latch transparent outside VBlank) | the value at V=128 | DATASHEET + INFERENCE (Visual 5C78/5C77 netlists, hardware-spec 2.1, 5.8) | a SETINI bit 0 write between V=128 and V=225 (240): the field length differs by one line; Zelda and Two Ship unchanged |
| V-IRQ with VTIME=0 (V-only mode) | TIMEUP at H=6 of line 0 (H=10 on every other line); in every mode the comparator sees V=0 from H=6 of line 0, the last line at H=2 | H=10 of line 0 | DATASHEET + INFERENCE (rgalland's S-CPU-A schematic: V cleared from the VBLANK fall one sample before the HBLANK fall steps it; the edge order fixed by paulb_nl's (0,339)/(261,339) results; hardware-spec 2.4, 5.17); paulb_nl's frame_timing_test expects it | frame_timing_test (MAMR 64/64); HTIME=338 with VTIME=261 or 0 across the field start; no gilyon ROM, no undisbeliever ROM, not Zelda |
| GP-DMA cut by HDMA in byuu's test_dma | the sampling clock 2 to 6 clocks earlier from frame 3, cpu in frame 4 | - | not traced (hardware-spec 5.11) | test_dma (section 12.1); both pass the ROM's checks |
| WDM ($42) | signature fetch, 8 clocks from SlowROM | the same | CHOICE after the data sheet analogue (hardware-spec 4.2) | none since 2026-10-24 (the earlier 6-clock price was the tolerated difference) |
| APU port read during an SPC700 write | the write's value when its time is at or before the read's sample, else the old one (no OR) | the same (synchronize, then the latch) | DOC says OR of old and new (Anomie); the collision window is unmeasured, not modelled (audio-spec 9) | none |
| HVBJOY bit 0 after $4200 bit 0 is cleared inside the latch phase (T0..T0+256) | stays set until the read stops at step 2 (T0+256) | reads 0 at once (`io.autoJoypadPoll && counter < 33`, cpu/io.cpp readCPU $4212) | TEST-ROM-HW indirect: undisbeliever clear-autojoy-during-autojoy, clear-autojoy-1st-vb-sl, clear-autojoy-timing-test; MesenCE's model was fitted to the author's console tables of the first two (Mesen2 commit d1aa957) and MAMR prints MesenCE's tables on all three (hardware-spec 2.5) | those three ROMs: the HVBJOY poll count after the clear (aresref 0000 where MAMR prints 0002, aresref 01 in every row of the timing test); ctest `snes_system_undisbeliever_*` checks the screens, not aresref |
| WRMPYB written again 7 CPU cycles after a WRMPYB (the product's 8th cycle) | stage E restarts the product (A x B2), as ares; stage S computes every product at once | restarts (A x B2) | the console clears RDMPY and ends 0 (TEST-ROM-HW, undisbeliever wrmpyb-in-flight, three consoles; hardware-spec 2.7); not modelled, the full tables are behind the forum login | wrmpyb-in-flight: stage E equal to aresref (ctest `snes_oracle_undisbeliever_wrmpyb-in-flight`, stage E only), both wrong against the console in the 7-cycle column; stage S differs from aresref in every in-flight column (section 12) |
| img with overscan (SETINI bit 2) | the picture of every frame | the same since patch 0008 (before: `img` raced ares' buffer swap at V=240 and came back black in 208 of 300 frames of the SNES Test Program) | oracle artefact, closed (section 2) | none since 2026-10-24: the SNES Test Program (U) is equal in every field in both stages (ctest `snes_oracle_test_program_local`) |
| SMP TEST register ($F0) bits 4-7, the wait states | modelled after fullsnes since 2026-10-24: RAM and I/O/IPL ROM access classes, 0, 1, 4 or 9 extra cycles, internal cycles in the class of the opcode fetch (audio-spec 1, CHOICE for the internal cycles) | modelled after byuu's notes (the table in blargg's notes.txt) | nobody but byuu/blargg measured the slow modes; no game uses them | blargg's test_speed, test_timer_speed, test_timer_speed2/3, test_timer_speed_2 (section 12.1) differ: the two models disagree (test_speed CA-FA: MAMR 25 like the screenshot, aresref 26); his timer_stop, timer_at_power_reset, controller strobebehavior, speed_2_freezes2, ram_disable_ipl are equal |
| Offset-per-tile in mode 4: one offset word per column, vertical when bit 15 is set | the documented single word (ppu-spec 2.6) | the vertical value from a second word that mode 4 never fetches | DOC (Anomie, the wiki) plus MEASURED: lidnariq's bus trace shows 33 BG3 name-table fetches per line in the mode 4 band against 66 in modes 2 and 6, one word per column (ppu-spec 2.6, 2026-10-24) | lidnariq's ppubusact.sfc (section 12.1): rows 129-159 (the mode 4 band), 6 to 300 half-pixels per row, from frame 3 on; the mode 5 band differs too (rows 168-185; open: the white 2bpp text "Layer 1" of that band, palette entries 0-3 on both the main and the sub half, stands one half-pixel further left in MAMR than in aresref, a horizontal displacement of a hi-res 2bpp layer, not a row shift; the cause between the two renderers is not isolated) |
| ROMs that stop the CPU (STP) | snes_headless ends with exit code 4 after the last complete frame | aresref samples at an instruction boundary that never comes and writes nothing | none | jonasquinn/byuu test_dmavalid (section 12): MAMR 5 F lines then STP at mclk 1862648, aresref no output within two minutes |
| PPU register write on a dot's own clock (compose, fetch or evaluation clock equal to the write time) | the write goes first, the dot sees the new value | the same (the PPU thread stops at the CPU's clock, the write is applied, then the PPU runs that clock) | CHOICE following ares; on the console the PPU samples INIDISP/SETINI even earlier in the write cycle (undisbeliever's early-read glitches), so a write cannot act later than its own clock (ppu-spec 8.1) | none since 2026-10-24; before, inidisp-hammer-0f-long, inidisp-hammer-long-0f2100 and setini-early-read-mode7ex differed by one pixel (img, frame 5: the force-blank release landing on T_PIX(x)) |
| S-SMP timer 2 on a CONTROL ($F1) write | stages 2 and 3 cleared only when bit 2 rises (one rule for all three timers) | cleared on every write that does not raise bit 2 (the condition is inverted against timers 0 and 1, `sfc/smp/io.cpp`) | DOC fullsnes against ares; blargg's snes_spc and LakeSnes clear on the rising edge; open until blargg's spc_timer test runs on a console (audio-spec 9) | Final Fantasy III (smp only, the $FF counter, from frame 21) and Secret of Evermore (its driver reads $FF: everything from frame 362); with ares' rule built in both are equal over 1000 frames (docs/snes-rom-survey.md) |

Run of 2026-10-27 for the RAM-code games (docs/snes-ram-code.md
section 5): `compare_oracle.py` over the first 3000 frames of
tests/snes-system/ct-route.txt, ff3-route.txt and som-route.txt, stage S
and stage E, first divergence per field, recorded as found and not
smoothed over:

| Game | Stage S | Stage E | Cause |
|---|---|---|---|
| Chrono Trigger (USA) | equal in every field | equal in every field | - |
| Final Fantasy III (USA) | smp from frame 21 (2965 frames), every other field equal | the same | the S-SMP timer 2 item above (survey finding F6) |
| Secret of Mana (Europe) | img from frame 1062 (243 frames), every other field equal | the same | the mode 5 picture of the intro (survey finding F8, cause open) |

Both findings are the survey's (docs/snes-rom-survey.md section 3),
frame for frame: the routes start with the survey scripts' input. The
native artefacts of the three games equal the interpreter in every F
line; the oracle differences are differences of the interpreter.

The items come from the hardware research of 2026-10-24 (package A);
the open hardware questions and their test setups are in
docs/snes-hardware-spec.md section 5.

## 11. undisbeliever test ROMs (hardware-tested, zlib)

undisbeliever/snes-test-roms (Marcus Rowe,
https://github.com/undisbeliever/snes-test-roms, zlib licence, checked
at commit ac6ef8006809c0ff5dabc8ff137a4623967697fe of 2026-05-01) holds
test programs the author ran on a 1CHIP SFC, a three-chip SFC and a PAL
console; the expected behaviour is written in the head of each `.asm`.
zlib is BSD-compatible, so the ROMs may be built and run as TEST-ROM-HW
material; they are never part of this repository (research package A,
A18). The repository has no prebuilt binaries for the tests of interest
(the 2021 release predates them); they are assembled with the author's
bass-untech (the `tools/bass-untech` submodule, built by the
GNUmakefile) from a clone outside the repository and copied flat to
`tests/data/undisbeliever/<name>.sfc` (local, not distributed), next to a copy of
the LICENSE and a PROVENANCE file naming the commit and the clone.

The tests picked for the open questions of package A:

| Directory | ROMs | Question |
|---|---|---|
| hardware-glitch-tests/inidisp-early-read-glitch | inidisp-d7-glitch-test, inidisp-hammer-0f, -0f-long, -0f00, -0f0f, -0f8f, -0f8f-fast, -8f0f, -long-0f2100 | INIDISP read early in the write cycle (the "INIDISP early read glitch", A11's neighbour) |
| hardware-glitch-tests/inidisp-early-read-glitch-hdma | hdma-2100-glitch, -2ch-0a, -2ch-81, hdma-21ff-glitch, hdma-21ff-2100-glitch, hdma-21ff-2100-0f-glitch | the same glitch through HDMA |
| hardware-glitch-tests | setini-early-read-mode7ex, setini-early-read-obj | SETINI sampled early in the write cycle (A8's neighbour) |
| hardware-tests/auto-joypad | joypad-latch-set-during-autojoy, joypad-latch-clear-during-autojoy, blip-autojoy-test, clear-autojoy-timing-test, clear-autojoy-during-autojoy, clear-autojoy-after-autojoy-active, clear-autojoy-1st-vb-sl, enable-autojoy-late-test, enable-autojoy-late-test-2, joyser0-read-during-autojoy | the auto-joypad read against $4016 writes and $4200 bit 0 changes (A3) |

ctest (`tests/snes-system/CMakeLists.txt`): for all 27 ROMs (and, stage E
only, wrmpyb-in-flight of section 12)
`snes_oracle_undisbeliever_<name>` (label oracle): `compare_oracle.py`
runs aresref on the ROM, then snes_headless in stage S and in stage E,
300 frames with the IPL dump, no input, and compares every field, mclk
and pc; a missing ROM or aresref skips the test. On the eight
auto-joypad ROMs on which aresref is not the reference, that test holds
the recorded difference (`--known FRAME:FIRST/ALL`: it passes while the
first divergence and the set of differing fields stay exactly as
recorded, and fails when the difference moves or disappears), and
in addition
`snes_system_undisbeliever_<name>` (label oracle-free):
`undisbeliever_screen.py` decodes the table the ROM prints (its
TextBuffer in WRAM) at five frames of both stages and compares it with
`tests/snes-system/undisbeliever/<name>.txt`, whose comment head gives
the provenance of every cell. The oracle comparison is MAMR against the
timing oracle, not against the console: where a ROM shows a glitch only
some of the time on the hardware (the INIDISP and SETINI tests say "~20%
of the time", depending on the CPU/PPU phase at reset), neither emulator
reproduces the phase, and the author's expected picture is checked by
eye from a dump. A difference between MAMR and aresref on one of these
ROMs is a finding to record here with its first frame and fields, not
something to smooth over.

Results (2026-10-24, ROMs assembled at commit ac6ef80 with bass-untech,
aresref as of 2026-10-24, MesenCE 2.2.1 as a third voice):

| ROMs | aresref against MAMR S and E, 300 frames | Finding | Decision |
|---|---|---|---|
| 14 of the 17 glitch ROMs | equal in every field, mclk and pc | neither emulator shows the author's INIDISP/SETINI early-read glitch (on his consoles in about 20% of the resets, CPU/PPU phase at reset); both start from the same phase (master clock 0 at V=0 H=0, CPU and PPU in step), so there is no phase to compare | ctest `snes_oracle_undisbeliever_*` unchanged |
| inidisp-hammer-0f-long, inidisp-hammer-long-0f2100, setini-early-read-mode7ex | img differed in frame 5 only: one pixel of the line on which the first INIDISP write releases force blank (x=29 of row 114; x=159 of row 34) | the write's clock equalled T_PIX(x); MAMR composed that pixel before applying the write (`<=` in Ppu::advance_line), ares after it (the PPU thread stops at the CPU clock, the write is applied, then the PPU's work of that clock runs). Hardware: the glitch itself says the PPU samples the data bus before the end of the write cycle, so the write cannot act later than its clock | fixed: the pipeline runs strictly before the access clock (ppu-spec 8.1, 11); Zelda 3000 frames and gilyon unchanged; all 17 glitch ROMs equal |
| clear-autojoy-after-autojoy-active, enable-autojoy-late-test | equal | (without input the first prints zeros; the author's console numbers in its head need B held) | ctest `snes_oracle_undisbeliever_*` |
| joypad-latch-set-during-autojoy, joypad-latch-clear-during-autojoy, blip-autojoy-test, enable-autojoy-late-test-2, joyser0-read-during-autojoy | cpu, wram, vram, img and mclk differ from frame 5 on | the ROMs align each pass with an IRQ at VTIME=210, HTIME=0: MAMR takes it at H=10, ares at H=14 (section 10); with H=14 built into MAMR for the check, all five were equal in every field. The screens (TextBuffer at $7E2000) of aresref, MesenCE and MAMR print the same tables, cell by cell, over frames 40..300 | the screen the ROM prints is checked against the expected table in `tests/snes-system/undisbeliever/<rom>.txt` (ctest `snes_system_undisbeliever_*`, five frames, both stages) |
| clear-autojoy-during-autojoy, clear-autojoy-1st-vb-sl, clear-autojoy-timing-test | cpu, wram, vram, img, mclk (and anc) differ, 233-296 frames | the HTIME=0 shift plus a real difference: after a clear of $4200 bit 0 inside the latch phase ares reads HVBJOY bit 0 as 0 at once, MAMR until step 2 (T0+256). MesenCE 2.2.1 prints MAMR's tables (6-8/4-6/2-4/1-2/1 polls for clears 0/64/128/192/256 clocks after the bit was seen; aresref prints 1 everywhere); MesenCE's model was fitted to the author's console tables of the first two ROMs (Mesen2 commit d1aa957, 2024-12-17) | known deviation (section 10, hardware-spec 2.5 raised to TEST-ROM-HW indirect); screen check as above |

The MAMR implementation against ares, point by point: $4016 writes and reads during the auto-read behave as in ares
(latch OR, early release, one bit consumed) and the screens agree;
$4200 bit 0 written inside T0..T0+128 moves the auto-read's latch as in
ares; a clear from step 2 on stops the read as in ares; the only
difference is HVBJOY bit 0 during T0..T0+256 after a clear (above).
MesenCE differs from both in two kinds of cell (clear-autojoy-1st-vb-sl
V=224 H=324 and V=225 H=0; enable-autojoy-late-test-2 V=225 H=16..48):
its pads are latched where aresref and MAMR show none, the 128-clock
latch question of hardware-spec 2.5; the expected tables accept both
values there and say so.

The screens are not single numbers: the ROMs' main loops are not
frame-locked, so the CPU phase against the read drifts from pass to pass
and the poll counts and boundary manual reads take several values on
every emulator (and on a console: the timing test prints MIN and MAX).
The expected tables hold the union of the values MAMR stage S, stage E
and MesenCE printed in frames 40..300; `undisbeliever_screen.py` reads
the screen at frames 100, 150, 200, 250 and 300. MesenCE was run
through the oracle pipeline (section 3) only for these screens; it is
not part of the ctest.

Check of 2026-10-26 (the latch position from the S-CPU schematic,
hardware-spec 2.5): all fourteen auto-joypad ROMs of the clone (the ten
above plus auto-joy-timing-test, blip-autojoy-latches-joypad-test,
blip-autojoy-test-automatic and blip-autojoy-timing-test, assembled in
the same clone, run locally only) through MAMR stage S, 400 frames,
without input and with B held, once with ares' latch position and once
with the schematic's. Five ROMs print differently between the two:
enable-autojoy-late-test-2 and clear-autojoy-1st-vb-sl (the boundary
rows, now MesenCE's values), clear-autojoy-during-autojoy,
joyser0-read-during-autojoy and blip-autojoy-latches-joypad-test; the
expected tables of the eight ctest ROMs pass with both, and the oracle
tests keep their recorded first divergence and fields. The only console
values written into a source are those of clear-autojoy-after-autojoy-
active ("0001 0001" and "0008 1000" on the author's 1-CHIP SFC with B
held, depending on a 2-clock change of the delay): independent of the
latch position, MAMR printed "0000 0001" and "0000 8000"; with the
forced shift on a clear (hardware-spec 2.5) it prints "0001 0001" in the
passes whose clear lands in the first clock-low phase, "0008 1000"
never (open).

Every test ROM in use, these included, has a row in the test evidence
register docs/snes-test-evidence.md.

## 12. SNESdev wiki "Emulator tests" (2026-10-24)

The wiki page https://snes.nesdev.org/wiki/Emulator_tests names, beyond
undisbeliever's ROMs, blargg's tests and the TASVideos list, four items
not yet in use here. Licence rule as in the evidence register: only
ISC/MIT/BSD/zlib/CC0 material goes under tests/data; everything else is
run from a directory of its own under the oracle folder outside the
repository and named there. Nothing was built for this check.

| Item | Source, licence, where | Run (aresref against MAMR S and E, 300 frames, picture included) | Finding |
|---|---|---|---|
| "Writing $4203 twice too fast gives erroneous result (not emulated)" (nesdev t=24087, 2022-08) | undisbeliever's `hardware-tests/wrmpyb-in-flight.asm` from the same clone and commit as section 11 (zlib; the ROM was already assembled there and is copied to tests/data/undisbeliever); Myself086's "Mul Div Test.sfc" and the result photographs are forum attachments behind the login, not fetched; rainwarrior's dizworld is in bbbradsmith/SNES_stuff (no licence) | stage E equal in every field, mclk and pc; stage S differs from frame 7 on (wram, vram, img: the printed table) | the ROM writes WRMPYB twice 2..9 cycles apart and prints RDMPY (A=FF, B1=FF, B2=FF..00 by default). Stage E prints ares' table: partial products F708 EF10 DF20 BF40 7F80 for 2..6 cycles, A x B2 from 7 on. The console prints 0 at 7 cycles (undisbeliever, three consoles): an ares-side deviation MAMR stage E shares, recorded in section 10 and hardware-spec 2.7 (TEST-ROM-HW, not modelled). Stage S prints A x B2 in every column (results at once, CHOICE 2.7): a stage S limit of no consequence for code that waits the 8 cycles. ctest: stage E against aresref |
| rainwarrior "Two Ship" (mode 5 plus interlace against mode 1, nesdev p=279303, 2022-05) | bbbradsmith/SNES_stuff `twoship/twoship.sfc` (sha1 d97d938c...), readme without a licence (the art is CC-BY 3.0 and CC0): external only, oracle folder `snes_stuff/twoship/`; the author ran it on his console (CRT over composite, upscaler, modern sets), no revision named, no photograph; TEST-ROM-HW only for "the picture appears", no numbers | equal in every field, mclk and pc, in both stages: 120 frames without input (mode 1) and 300 frames with A pressed at read 60 (mode 5, SETINI bit 0, 512 x 224 picture, fields of 263 and 262 lines) | green; the NTSC interlace field length gives ares' result on this ROM, with the V=128 sampling of SETINI bit 0 and, since 2026-10-26, with the VBlank latch (hardware-spec 5.8; re-run 2026-10-26, equal in both stages): it switches once and never between V=128 and VBlank, so it does not decide A8 |
| lidnariq "PPU bus activity" (modes 0-6 in bands of 32 lines by HDMA, logic-analyzer traces of the PPU bus, nesdev p=174494, 2016) | the ROM (`ppubusactivity_rev2_sfc.7z`) and the traces are forum attachments; the download needs a forum account (the server answers with its information page); no licence statement. The ROM (`ppubusact.sfc`) and the trace were found later in the higan/snes-test-roms collection (section 12.1) | see section 12.1 | the trace read in section 12.1: one offset word per column in mode 4 (ppu-spec 2.6, MEASURED); the mode 5 band is open |
| NovaSquirrel "gradient-test" (CGWSEL, "to demonstrate inaccurate emulator behaviour") | https://bin.smwcentral.net/u/1780/gradient-test.sfc (sha1 2d22d9e7...), 256 KiB LoROM "GRADIENT TEST"; no licence or source found (the author's GitHub holds no repository of that name): external only, oracle folder `novasquirrel/`; no console photograph, the ROM states its own expectation on screen | equal in every field, mclk and pc, in both stages | green; the picture (frame 300) shows the gradient, black borders and white text the ROM asks for ("THERE SHOULD BE A GRADIENT EFFECT AND BLACK BORDERS AND WHITE TEXT"), so MAMR and ares pass the author's own criterion; class DOC (the author's expectation), no hardware run known |

"Tricky-to-emulate games" (https://snes.nesdev.org/wiki/Tricky-to-emulate_games),
checked against the local shelf (roms/snes, 2026-10-24; the survey of
the shelf itself is docs/snes-rom-survey.md): three of the page's games
are here.

| Game on the shelf | Page's hardware corner | Where it lives in the spec |
|---|---|---|
| Chrono Trigger (USA) | offset-per-tile bugs (with Axelay) | ppu-spec 2.6 (modes 2/4/6), 8.1 OPT rows |
| Illusion of Time (Germany) = Illusion of Gaia | BRK/COP implementation; SPC timing "1 cycle at a time, not 1 instruction" | hardware-spec 4 (vectors, E flag), audio-spec (the S-SMP runs per cycle) |
| Super Mario World (U), and the same game in Super Mario All-Stars + Super Mario World (USA) | ORA [d] (direct page indirect long); OAMADD priority sprite rotation | hardware-spec 4 / SingleStepTests; ppu-spec 3.4 |

The other games on the shelf (Zelda DE and USA, Secret of Mana, Final
Fantasy III, Donkey Kong Country, Star Fox, Street Fighter Alpha 2,
Super Metroid, Super Mario Kart, Super Mario RPG, Secret of Evermore,
Super Bomberman 2 and 5, Super Game Boy, SNES Test Program, Alien 3)
are not on the page. Pocky & Rocky (HDMA direction flag, late NMI) and
RoboCop versus The Terminator (V-IRQ enable on the current line) are
cited in hardware-spec 2.3 to 2.6 and 3.4 from other sources but are not
on the shelf.

### 12.1 higan/snes-test-roms collection and blargg's archive

Second find site (2026-10-24): https://gitlab.com/higan/snes-test-roms
(Near's collection for higan; no licence of its own, one per ROM;
shallow clone in the oracle folder, `higan-snes-test-roms/`). It
holds lidnariq's `ppubusact.sfc` with the bus trace, Jonas Quinn's
collection (blargg's ADC/SBC/OAM/TSC tests, byuu's test_dmavalid,
test_hdmasync), KungFuFurby's 2005-2008 IRQ/NMI/HDMA tests, Motive's
two ROMs, tepples' tellinglys (zlib), 93143's HBlank VRAM DMA test with
a console photograph, Ladida's HDMA test with a console video, Sour's
and VitorVilela7's tests, the undisbeliever INIDISP set, blargg's SPC
set 6 (already in use, docs/snes-audio-spec.md) and PeterLemon's CPU
and GSU tests. Not in it: Two Ship, gradient-test, a $4203 test. Third
find site: blargg's 2010 SNES archive (snescentral article 1115,
the oracle folder, `blargg-snes/`). Everything below stays
external (no licence) except tellinglys (zlib, needs button input with
timing, not yet scripted). Runs: aresref against MAMR S and E, 300
frames unless the ROM stops the CPU (then up to its last complete
frame; aresref writes nothing for such a ROM, section 10).

| ROM | Hardware expectation on record | Result | Finding |
|---|---|---|---|
| blargg test_adc, test_sbc, test_oam, snes_test_tsc, blargg_near_cd_quality (jonasquinn) | the ROMs' own pass/fail codes | equal, both stages | green |
| byuu test_dmavalid (jonasquinn) | none | MAMR 5 frames then STP; aresref no output | both end; no comparison here; compared through the snescentral copies with the STP replaced (row below) |
| byuu/KungFuFurby test_irq4200 (52 frames), test_irq4209 (75), test_nmi (57), test_irq (23), test_hdma (10), test_hdmatiming (26), test_hdmasync, demo_nmitest, irq, nmi | none written down (the Mesen-S thread: the games Alien vs Predator and Jaki Crush rely on test_nmi/test_irq behaviour) | equal, both stages | green; the STP ROMs up to their last frame |
| KungFuFurby demo_irqtest | none | frame 26 only: cpu (A bit 7 and N after an I/O read, same mclk and pc), both stages | a flag read 4 clocks off, most likely the HTIME=0 timing of section 10; not traced further |
| Motive HblankEmuTest (an H-IRQ sets force blank at H about 980 on every line, an HDMA channel clears it at H about 1130; "the sprites should not load and the correct emulator screen appears"; a PAL ROM) | console: the text "THIS IS CORRECT BEHAVIOUR" (Motive, four consoles plus an SFC per hardware-spec 5.18) | stage S equal to aresref (the text); stage E, before the fix: img from frame 11 on in 290 frames, rows 90-99 black | found and fixed (2026-10-24): the CPU waits in WAI for every H-IRQ, so stage E's PPU, synchronized only at CPU bus cycles, catches up hundreds of lines in one piece; while its field counter lagged the time skeleton's, `Ppu::field_lines` fell back to the NTSC shape and the PAL field wrapped at 262 lines, shifting the PPU's line counter by 50 lines per field (195 instead of 95 by frame 11), so the HDMA's INIDISP write and the pixels of those lines landed on the wrong rows. The fallback now takes the skeleton's video system. Both stages equal aresref over 300 frames; Zelda DE and USA 3000 frames unchanged. ctest `snes_system_stages_hblank_emu_test` (S against E) and `snes_oracle_hblank_emu_test` with `SNES_HIGAN_TEST_ROMS` set |
| Motive SplitScreen (mode 3 beside mode 5, windows hide the middle) | console: the right mode stands still; "on hardware it's a mess" (Motive) | img from frame 15 in 286 frames, both stages: MAMR draws the right half (the mode 5 "High Res" block) in full, aresref only fragments at the far right | neither matches Motive's description of the console; open, a mid-line BGMODE and window case (ppu-spec 8.1 "dot" rows) |
| tepples tellinglys (zlib) | an NTSC 1/1/1 console passes | equal (title screen; the test needs twelve presses with timing) | no input script yet; the ROM is a candidate for tests/data once scripted |
| 93143 hvdma (eight HDMA channels force blank, write a VRAM address and 20 bytes, turn the screen on, every line) | console photograph in the collection: X pattern above, the overwritten tile below, blue sprite background | img: row 107 only (the line after the tile-overwrite burst), both stages: aresref 0000 where MAMR draws the backdrop colour; sram 300 frames: aresref 128 KiB of $FF for a header with RAM size 0, MAMR none | MAMR's picture matches the photograph; on the console that row shows "white flickering segments despite white being nowhere in the palette" (93143), which neither emulator draws; the sram difference is a cartridge heuristic of ares, no hardware question |
| 93143 hvdma_max | as above | sram only | green apart from the sram heuristic |
| Ladida_lol (HDMA enabled mid-frame, DoTransfer flag) | console video in the collection | equal, both stages | green |
| tukuyomi demo_mode3 | none | equal | green |
| lidnariq ppubusact | the bus trace (CSV, logic-analyzer clips on the VRAM chips of his console at 12 MHz), no screen photograph | img from frame 3 in 298 frames, both stages: mode 4 band rows 129-159 and mode 5 band rows 168-185 | the trace, read 2026-10-24 (CSYNC pulses of 54-55 samples mark the lines, 762-763 samples apart; the BGMODE bands show as fetch patterns: four name tables plus BG3 characters in mode 0, 66 BG3 name-table fetches per line in modes 2 and 6, 33 in mode 4, none in modes 3 and 5): mode 4 fetches one offset word per column, the documented rule MAMR follows and ares does not (section 10, ppu-spec 2.6 MEASURED). The mode 5 band stays open: the white 2bpp text layer of that band stands one half-pixel further left in MAMR than in aresref (section 10); the trace says only that the fetch cadence equals mode 3's (lidnariq) |
| VitorVilela7 speed_test_v51 | the author's expected MHz table | not run: map mode $23 (SA-1), unsupported | out of scope |
| blargg 2010: controller strobebehavior, test_timer_stop, test_timer_stop2, timer_at_power_reset, speed_2_freezes2, test_ram_disable_ipl | screenshots on the article page (origin not stated; timer_at_power_reset shows "000E / Press reset", then "Passed" after a reset) | equal, both stages; MAMR's timer_at_power_reset screen reads "000E / Press reset" like the screenshot | green; timer_at_power_reset is no S-SMP test (disassembled 2026-10-26): 000E is the CPU/PPU phase after an H-IRQ at power-on (hardware-spec 5.4), the reset half needs the button; the screenshot's origin is unknown |
| blargg 2010: test_speed, test_timer_speed, test_timer_speed2, test_timer_speed3, test_timer_speed_2 | the article's screenshots (test_speed: 252/252/251/251 for modes 0A-3A, 126 for 4A-7A, 25 for CA-FA) | with the wait-state model, both stages alike: test_speed from frame 11 (smp, wram), test_timer_speed, 2 and 3 from frame 8 (smp), test_timer_speed_2 from frame 4 (cpu, apuio, wram, aram, mclk); before the model MAMR's test_speed screen read 251/251/251/252 and then 251/252 throughout; with it (2026-10-24) 251/252 for 0A-3A, 126 for 4A-7A, 25 for CA-FA; aresref 251/251/251/252, 126 x4, 26 x4 | the SMP TEST register wait states (section 10, audio-spec 1): MAMR follows fullsnes' access classes and meets the screenshot, ares' per-opcode model lands within one count of it |

Two more sets (2026-10-26), external or local only (no
licence; docs/snes-test-evidence.md):

| ROM | Hardware expectation on record | Result | Finding |
|---|---|---|---|
| paulb_nl snes_frame_timing_test (MiSTer issue #520) | the expected values in its source (the published "PASSED 64/64" picture is the MiSTer core's) | 400 frames, results read from VRAM: MAMR stage S and E 64/64 since 2026-10-26 (59/64 before), aresref 48/64; against aresref wram, vram, img, cpu, ppu and mclk differ from frame 43 (from frame 59 before that change) | MAMR missed the five rows of a pure V-IRQ at VTIME=0 (expected one dot earlier than at VTIME=1) until the S-CPU schematic decided them (hardware-spec 2.4, 5.17); aresref misses those five plus HTIME=0 (H0V0, H0V1) and the first IRQ at (0,339), the deviations of section 10 |
| byuu test_dma, test_dmasync, test_dmavalid, test_hdma, test_hdmasync, test_hdmatiming v1/v2, test_hdmadisable, test_mdrhdma v1/v2 (snescentral article 1123; STP replaced by STA $2100 / BRA * in local copies) | pass/fail per MiSTer issue #105 on a 1CHIP and a GPM-01 (hdmasync and hdmatiming unstable on the consoles) | 300 frames (hdmasync 1300): all blue in MAMR S, E and aresref; equal in every field except test_dma (mclk, section 10); test_dmavalid equal since 2026-10-26 (the invalid $2180-to-WRAM DMA writes 00 as byuu's console; before MAMR wrote the bus value $EA), MAMR's SRAM after it byte-identical to the test_dmavalid.srm image of the higan collection | green for pass/fail; one difference recorded in section 10 |

Decision for the auto-joypad question: controller strobebehavior (blargg)
equal in every field adds a second ROM to the $4016-during-auto-read
consensus of hardware-spec 2.6.
