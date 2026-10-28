# NES test evidence register

Every test program that MAMR's NES path runs or compares against, with
what its expected values rest on. The rule is the SNES one
(docs/snes-test-evidence.md, docs/snes-hardware-spec.md section 5.18):
neither a project description nor "runs on hardware" makes a test's
expected values TEST-ROM-HW; that class needs a console result with the
hardware revision. Without it a test counts as DOC (the author's
documented expectation), EMU-CONSENSUS or model data. Classes as in
docs/nes-hardware-spec.md. A test whose expectation is "the console of
its author" fixes that console's revision, not "the NES": AccuracyCoin
fixes the RP2A03G CPU and the RP2C02G PPU.

Columns: test id (as the ctest or the file is named); source and commit;
licence; origin of the expected values; hardware revision of the console
run, if any; raw data available; emulator comparison done here; where it
is used.

| test_id | source, commit | licence | expected values from | hardware revision | raw data | emulator comparison | used by |
|---|---|---|---|---|---|---|---|
| AccuracyCoin (147 tests plus 5 DRAW tests) | github.com/100thCoin/AccuracyCoin, commit b4b5952f8ef57618d798c8d97cd099ab352e62e6 (2026-10-23; ROM and source last changed in f530d1233be18787835507b7d2adfc1a2ba3b06d, "Added DMC Playback Rate test"); the author's assembled AccuracyCoin.nes of that commit (sha1 d3cc7e03476d0f2546395154e311724324779efe, NROM-256, 8 KiB CHR ROM, horizontal mirroring), AccuracyCoin.asm sha1 e75a817decaab5c36826180628df28df46f7df4b; local copy tests/data/accuracycoin (local, not distributed) | MIT (Copyright 2025 Chris Siebert, LICENSE read in full) | the author's PASS/FAIL expectation per test, written for and run on his NTSC console; several tests accept more than one behaviour (marked with a code) | RP2A03G, RP2C02G (README; no console log published) | the result bytes $0400-$04FF of a run (T line, docs/nes-oracle-format.md section 8); no console run of this commit published | MesenCE 2.2.1: 141/147, six fail (section 2); MAME 0.285: see section 2; MAMR 147/147 (section 4) | TEST-ROM-HW judge of the path (docs/nes-architecture.md section 7); ctest `nes_oracle_*_accuracycoin_all` records the oracles' results, `nes_mamr_accuracycoin_all` MAMR's |
| SingleStepTests/65x02, set nes6502 (v1) | github.com/SingleStepTests/65x02, commit 2f6980a2d95757486c7bee24355c360e40e2a224; local sparse clone tests/data/sst-6502 (local, not distributed) | MIT (Copyright 2024 Thomas Harte et al.) | generated from an emulator model that "conforms to all available documentation" (README): model data, not hardware; the unstable undocumented opcodes follow the common model | none (no console) | the JSON cases | the interpreter against all 2,560,000 cases with the bus cycle list (ctest `m6502_sst`); 20,000 magic-constant and 50,000 address-high cases counted separately, KIL 120,000 | 6502 core; class IMPL of its generator, never TEST-ROM-HW |
| nestest (kevtris, V1.00 2004) and nestest.log | christopherpow/nes-test-roms, commit 95d8f621ae55cee0d09b91519a8989ae0e64753b, other/nestest.nes (sha1 5b608f023b41399c34dfc6c847d8af084e0f7aeb), other/nestest.log (sha1 e32cd5de0b69a925871b213e8cfa8915d723f83a); local copy tests/data/nestest (local, not distributed) | none (no licence in the collection; local use only, nothing enters the repository) | the ROM's own result codes ($02, $03) by its author, who states that "a real NES" passes (nestest.txt); the log with registers and cycles is an emulator trace (Nintendulator per the community; class IMPL) | not stated | the log | the interpreter matches all 8991 log lines in PC, A, X, Y, P, S, CPU cycles and the derived PPU position, result bytes 0 (ctest `nes_nestest_local`, label local) | 6502 core cross-check beside SingleStepTests |
| blargg mmc3_irq_tests (1-6) | christopherpow/nes-test-roms, commit 95d8f621ae55cee0d09b91519a8989ae0e64753b, mmc3_irq_tests | none (local only) | the author's console runs on several MMC3 boards; revision A with a Crystalis board, revision B with Super Mario Bros. 3 (readme) | MMC3A (Crystalis), MMC3B (SMB3); console revision not stated | the readme | MAMR: all six pass (revision A test with `--mmc3-rev a`), also mmc3_test_2 1-6; filter lengths 3-8 M2 edges pass, 1-2 fail (section 4) | MMC3 counter rules (docs/nes-hardware-spec.md section 3.3, cited as source); acceptance of the A12 filter |
| blargg APU suites: apu_test (1-8 and the combined ROM), apu_reset (6), blargg_apu_2005.07.30 (11), dmc_tests (4) | christopherpow/nes-test-roms, commit 95d8f621ae55cee0d09b91519a8989ae0e64753b | none (local only) | apu_test, apu_reset, 2005: the author's documented expectations, the readmes name no console revision (DOC); [BLARGG-REF] (docs/nes-audio-spec.md) gives the author's console for his APU work, a 1988 NTSC NES with an RP2A03G. dmc_tests: no readme, no verdict; they click with $4011, wait on $4015 or the DMC IRQ and end with a fixed tone (heard) | not stated in the suites | the $6000 result protocol (format section 9) | MesenCE 2.2.1: all with a verdict pass; MAMR: section 4.6 | phase N2 timing (docs/nes-hardware-spec.md section 6), phase N4 local regression (`testroms.py run --oracles mamr`) |
| blargg apu_mixer (dmc, noise, square, triangle) with apu_mixer_recordings (4 MP3 files) | same collection and commit | none (local only) | heard: "near silence between the beeps" (the channel cancelled by the inverse wave on the DMC DAC); the recordings carry no metadata and the collection does not say where they come from (INFERENCE: recordings of the tests on a console, they show an analog noise floor) | not stated | the recordings | MAMR's residual measured against the recordings (section 4.6); MesenCE equal to MAMR in every hash field including apu | phase N4: the mixer's relative levels and nonlinearity |
| blargg pal_apu_tests (10 ROMs: 01-08, 10, 11) | christopherpow/nes-test-roms, commit 95d8f621ae55cee0d09b91519a8989ae0e64753b, pal_apu_tests | none (local only) | the author's runs: "They have been tested on a PAL NES and all give a passing result" (readme), with the PAL frame sequencer delays listed beside the NTSC ones | a PAL NES, CPU revision not stated (RP2A07) | the readme | MAMR 10/10, MesenCE 2.2.1 10/10, MAME 0.285 nespal 1/10 (section 4.7) | TEST-ROM-HW judge of the RP2A07 frame counter and length counters (docs/nes-hardware-spec.md section 7.3); phase P |
| blargg nmi_sync demo_pal | same collection and commit, nmi_sync | none (local only) | the readme's description of what a PAL console shows: the drawn line's left edge between the two reference lines, random within that range after each reset | PAL NES (readme) | the readme | MAMR inside the range, MesenCE one pixel outside, MAME draws no line (section 4.7) | TEST-ROM-HW for the range of the PAL CPU/PPU phase (docs/nes-hardware-spec.md section 7.2) |
| MAMR unit tests | tests/nes/test_nes_board.cpp, test_nes_ppu.cpp, test_nes_apu.cpp, test_nes_audio.cpp (phase N4), test_nes_dma.cpp, test_nes_hashline.cpp (own) | BSD-3 (this project) | the rules of the hardware and PPU specs, each with its class there | none | none | none | regression tests of decided rules, not evidence of their own |

## 1. AccuracyCoin: how it is run

`gates.py accuracycoin ORACLE ROM ASM` starts the oracle with the input
script `tools/oracle/nes/inputs/accuracycoin-all.txt` (wait for the menu,
press Start with the cursor on the page line: "run every test on the
ROM"), lets the writer report the result bytes in a T line 60 frames after
the pass ends, and decodes them with the test names from the pinned
AccuracyCoin.asm (`accuracycoin.py`). A test whose run makes no progress
for 1200 frames is reported as a hang and the run repeated with that test
marked skipped (the ROM's own skip mark, $FF in the result byte); in the
run of one page a pass that goes back to an earlier test counts as a hang
of the test that ran last. With
`--per-page` every menu page runs on its own from power-on (RIGHT to the
page, A on the page line), so a test that breaks the ROM's own state
affects only its page.

## 2. AccuracyCoin results of the oracles

Run 2026-10-24, NTSC, MesenCE fill 00, MAME with its fixed fill.

**MesenCE 2.2.1** (run of every test, 4132 frames, 38 s): ROM tally
141/147, no hang, identical in repeated runs. Failing tests (code = the
ROM's error number):

| page | test | result symbol | code |
|---|---|---|---|
| CPU Behavior 2 | DMC Reload Timing | result_DMCReloadTiming | 1 |
| Advanced Background Evaluation | BG Serial In | result_BGSerialIn | 2 |
| Advanced Background Evaluation | ALE + Read | result_ALERead | 2 |
| Advanced Background Evaluation | Hybrid Addresses | result_HybridAddresses | 2 |
| Advanced Sprite Evaluation | Stale Sprite Shift Regs | result_StaleSpriteShiftRegs | 3 |
| Advanced Sprite Evaluation | Frozen OAM2 Increment | result_FrozenOAM2Inc | 2 |

**MAME 0.285**: the run of every test does not survive MAME. It sticks in
"VBlank end" and "NMI Timing" (no progress), and with those skipped the
pass loop itself breaks (the ROM's test counter passes 147, pages are
repeated, the name printer loops at $F28F). Run page by page from power-on
(`--per-page`, 22 runs, 132 s), every page finishes except "Sprite
Evaluation", where "Misaligned OAM behavior" sends the page loop back to
an earlier test every time; with that test skipped: 85 of 147 pass, 61
fail, 1 skipped, identical in repeated runs. The failing tests by page
(the list with codes is the ctest `nes_oracle_mame_accuracycoin_all`):

| page | failing under MAME |
|---|---|
| CPU Behavior | Open Bus |
| Unofficial SH* | SHA (indirect),Y and absolute,Y; SHS; SHY; SHX; LAE |
| CPU Interrupts | Interrupt flag latency, NMI Overlap BRK, NMI Overlap IRQ |
| APU Registers and DMA | all ten DMA tests |
| APU Tests | Length Counter, Length Table, Frame Counter IRQ, 4-step, 5-step, Delta Modulation Channel, APU Register Activation, Controller Strobing |
| CPU Behavior 2 | Instruction Timing, Implied Dummy Reads, JSR Edge Cases, DMA Landing on Write, DMC Reload Timing, DMC Playback Rate |
| PPU Behavior | PPU Register Open Bus, Palette RAM Quirks |
| PPU VBlank Timing | all seven |
| Sprite Evaluation | Sprite 0 Hit behavior, $2002 flag timing, Suddenly Resize Sprite, Arbitrary Sprite zero, OAM Corruption (Misaligned OAM behavior skipped) |
| PPU Misc. | Address $2004 behavior, INC $4014, Rendering Flag Behavior, $2007 read w/ rendering, $2004 and $2007 Stress Tests |
| Advanced Background Evaluation | Stale BG Shift Registers, BG Serial In, ALE + Read |
| Advanced Sprite Evaluation | Sprites On Scanline 0, Stale Sprite Shift Regs, Frozen OAM2 Increment, Misaligned OAM2 Address |

Five of MesenCE's six failures fail under MAME too; "Hybrid Addresses"
passes under MAME and fails under MesenCE. MesenCE run page by page gives
the same 141/147 as its run of every test, so the page method does not
change results. The MAME writer reads only saved device items, the PPU's
video address space and a write tap on $4016 at frame end; it makes no
access to the CPU bus.

**Gate finding.** The research note of 2026-10-24 expected "140/140" for
both oracles. That count belongs to an older AccuracyCoin; the pinned
commit has 147 tests. MesenCE 2.2.1 (released 2026-06-05) fails six of
them. The ROM's history dates their first appearance: BG Serial In
2025-12-01, Stale Sprite Shift Regs 2026-04-05, ALE + Read 2026-06-04,
Hybrid Addresses 2026-06-26, Frozen OAM2 Increment 2026-09-01, DMC Reload
Timing 2026-10-05; three are newer than the MesenCE release, three are
not. MAME 0.285 is far from it: 85 of 147, with the CPU interrupt, DMA, APU,
VBlank and sprite evaluation pages largely failing, and one test that
breaks the ROM's page loop. MAME is therefore an oracle for the picture,
the memories and the mapper state of programs that do not depend on
those details, not for timing. Neither oracle
is therefore a complete AccuracyCoin reference: for a test that an
oracle fails, the AccuracyCoin expectation (TEST-ROM-HW for the G
revisions) decides, and MAMR's result is compared against the ROM's own
verdict, not against the oracle's.

Not in use, listed for the record:

| test_id | source | licence | expected values from | note |
|---|---|---|---|---|
| blargg's, bisqwit's and others' NES test ROMs | christopherpow/nes-test-roms | mostly none | the authors' console runs, mostly informal | catalogued and run through both oracles in section 3; local only |
| NTF2 System and Test cartridges; Nintendo World Class Service test cartridges (Control Deck, Joystick, Port, Power Pad) | Nintendo; listed with hashes in HTGDB (section 3.6) | Nintendo's property | Nintendo's own service tests, no published expectations | not usable: never a ROM source, catalogue entry only |
| Retro Regen NES Hardware Test Suite | retroregen.com (terms effective 2026-09-22) | freeware, no source; redistribution only as the unmodified ZIP, no derivatives | console diagnosis (RAM, video, audio, controllers), not an emulation accuracy test | not usable for the gates; not in the repository |
| Visual2A03 / Visual2C02 derived vectors | visual6502.org and derivatives | CC BY-NC-SA | transistor-level simulation | not used (docs/nes-architecture.md section 1); a simulation run for one question (perfect6502, class SIM) leaves only its stated result (docs/nes-hardware-spec.md section 5.7) |
| TriCNES | github.com/100thCoin/TriCNES | MIT (Copyright 2025 Chris Siebert) | an emulator by AccuracyCoin's author | candidate third oracle; not built |

## 3. Catalogue: nesdev wiki, nes-test-roms, TASVideos

Sources, all retrieved 2026-10-24:

- the NESdev wiki page "Emulator tests" (www.nesdev.org/wiki/Emulator_tests,
  revision 24362 of 2026-10-07): about 100 tests in the groups CPU, PPU,
  APU, mapper-specific, input and misc, with links to the authors' posts;
- the archive christopherpow/nes-test-roms, commit
  95d8f621ae55cee0d09b91519a8989ae0e64753b (2022-03-02), local copy
  outside the repository; the wiki points to it for dead links;
- TASVideos "NES Accuracy Tests" (tasvideos.org/EmulatorResources/NESAccuracyTests,
  revision 263 of 2026-09-15, substantive data mostly 2016-2019) with the
  per-test table of 156 ROMs, and its subpage "TestCriteria";
- the Hardware Target Game Database (frederic-mahe/Hardware-Target-Game-Database),
  puNES (punesemu/puNES) and the Retro Regen test suite, for the record.

AccuracyCoin is on neither the wiki page nor the TASVideos table.

### 3.1 Licences

The archive has no licence file, and the readmes of blargg's and
bisqwit's tests state none; that covers almost every CPU, PPU, APU and
MMC3 test of the collection. Those ROMs are used locally as external
judges only, and nothing of them (ROM, source, output, hash) enters the
repository; this register names them and records verdicts. Explicit
licences in the collection: nes15-1.0.0 (BSD-style, Mathew Brenaman
2011), dpcmletterbox and vaus-test (GNU All-Permissive, Damian Yerrick),
volume_tests (zlib-style permission notice), the neslib library inside
nrom368 (stated as public domain in its source). Outside the collection
tepples' GitHub projects (allpads, Zap Ruder, Holy Mapperel: zlib or
All-Permissive; the 240p test suite: GPL-2.0) and lidnariq's newer posts
(public domain or CC0) are permissive. Two items restrict use explicitly:
tvpassfail (a preview its author asked not to distribute) and PaddleTest3
("Don't steal my code!"). None of the permissive items tests what phase
N1 or N2 needs (they are controller, audio-level and mapper-detection
programs), so no test ROM of this catalogue is a candidate for the
repository.

### 3.2 Hardware provenance of the expected values

The authors' statements are mostly informal and NTSC: "tested on an
actual NES and all give a passing result" (blargg's 2005 suites,
branch_timing_tests, sprite_hit_tests, sprite_overflow_tests,
vbl_nmi_timing; class TEST-ROM-HW without a published log or revision);
cpu_timing_test6 passes on NTSC and not on PAL; oam_read reports the
four outcomes of the author's NTSC front-loader; oam_stress passes on an
NTSC NES in only one of four CPU/PPU alignments; ppu_vbl_nmi warns that a
console can power up in a phase that fails some tests;
blargg_ppu_tests' power_up_palette depends on the PPU revision (TASVideos
lists it failing on every hardware column). blargg's MMC3 tests name the
boards: revision A on Crystalis, revision B on Super Mario Bros. 3 and
Mega Man 3 (docs/nes-hardware-spec.md section 3.3). Several tests say
they were never checked on hardware (cpu_flag_concurrency, test_apu_2,
dma_sync_test_v2, mmc5test_v2, vrc6test); NEStress contains tests meant
to fail on hardware. Where a test's verdict depends on the power-up
alignment, the hardware passes it only sometimes; TASVideos' hardware
columns carry notes like "Pass (25% of time)".

### 3.3 TASVideos' criteria against our gates

TASVideos judges a ROM by its own on-screen verdict (the PASSED/FAILED
text, the error code or the CRC it prints); visual tests by eye against a
reference video; for two DMC DMA tests the TestCriteria page lists
several accepted outputs and CRCs (dma_2007_read: 159A7A8F or 5E3DF9C4;
double_2007_read: 85CFD627, F018C287, 440EF923 or E52F41A5), which
reflect the DMA phase. There is no partial credit and no rule for the
"sometimes" cells. A pass there means "the ROM's verdict was PASSED in
the emulator once".

Our gates are different and stricter: an oracle gate compares the hash
lines field by field and frame by frame (RAM, VRAM, OAM, palette, PPU
registers, mapper state, picture) against a reference file or the other
oracle; a ROM's verdict is only one input. A TASVideos pass is therefore
never a gate pass of ours, and a gate failure can coexist with a PASSED
screen (the same verdict reached in a different frame, with different
RAM). `testroms.py` reports the ROM's verdict (blargg's $6000 protocol
or the screen text, with the TestCriteria alternatives for the two DMA
tests) as a record of the oracles, the same kind of statement TASVideos
makes, and keeps it apart from the gates.

TASVideos' table has no MAME column and no Mesen2/MesenCE column (only
the original Mesen, without version). It lists Mesen, Nestopia 1.53.1
and BizHawk 2.3 with 156 of 156 in its summary; its per-test rows show
BizHawk failing scanline and tvpassfail and puNES failing
power_up_palette, nmi_sync, scanline and PaddleTest (summary 153). These
are hints only; the judges here remain MesenCE and MAME and the ROMs'
own expectations.

### 3.4 Results of the oracles

`tools/oracle/nes/testroms.py run DIR` runs the catalogued ROMs (91, the
ones relevant to phases N1 and N2: CPU, PPU timing and memory, APU and
DMA as far as the CPU sees them, controller reads, MMC3) through both
oracles one after the other; MesenCE with fill 00, MAME with its fill.
Run 2026-10-24.

Summary: MesenCE 87 of 90 pass. The three others are expected: the two
revision A tests (mmc3_test_2 6-MMC3_alt, mmc3_irq_tests 5.MMC3_rev_A)
can pass only on an emulation of the old MMC3, and MesenCE emulates
revision B, which the target game's board has (only one of each A/B pair
can pass); read_joy3 count_errors prints an error pattern of a
statistical test and has no verdict to decode. MAME 36 of 90 pass, 46
fail, 4 print nothing within the frame cap (three dmc_dma_during_read4
tests and read_joy3 thorough_test), 4 have no decodable verdict
(blargg_apu_2005 02.len_table shows four codes, both sprdma_and_dmc_dma
tests stop after their header, count_errors as above). MAME fails the
whole VBlank/NMI timing family (ppu_vbl_nmi, vbl_nmi_timing 1-7), most
APU timing tests, every MMC3 test, sprite 0 hit timing, three of five
sprite overflow tests, cpu_interrupts_v2, the CPU registers at power-on
and ppu_open_bus. This agrees with its AccuracyCoin result (section 2).

In the table "pass" and "fail N" are the ROM's own verdict (N its code),
"unclear" a screen without a verdict to decode, "no text" an empty
screen at the frame cap. Detail texts are in the TSV the tool writes
(local).

| ROM | MesenCE 2.2.1 | MAME 0.285 |
|---|---|---|
| instr_test-v5/official_only.nes | pass | pass |
| instr_test-v5/all_instrs.nes | pass | pass |
| instr_misc/instr_misc.nes | pass | pass |
| instr_timing/instr_timing.nes | pass | pass |
| cpu_timing_test6/cpu_timing_test.nes | pass | pass |
| branch_timing_tests/1.Branch_Basics.nes | pass | pass |
| branch_timing_tests/2.Backward_Branch.nes | pass | pass |
| branch_timing_tests/3.Forward_Branch.nes | pass | pass |
| cpu_dummy_reads/cpu_dummy_reads.nes | pass | pass |
| cpu_dummy_writes/cpu_dummy_writes_oam.nes | pass | pass |
| cpu_dummy_writes/cpu_dummy_writes_ppumem.nes | pass | pass |
| cpu_exec_space/test_cpu_exec_space_ppuio.nes | pass | pass |
| cpu_exec_space/test_cpu_exec_space_apu.nes | pass | fail 2 |
| cpu_interrupts_v2/cpu_interrupts.nes | pass | fail 1 |
| cpu_reset/registers.nes | pass | fail 2 |
| cpu_reset/ram_after_reset.nes | pass | pass |
| blargg_nes_cpu_test5/official.nes | pass | pass |
| blargg_nes_cpu_test5/cpu.nes | pass | pass |
| ppu_vbl_nmi/ppu_vbl_nmi.nes | pass | fail 1 |
| vbl_nmi_timing/1.frame_basics.nes | pass | fail |
| vbl_nmi_timing/2.vbl_timing.nes | pass | fail |
| vbl_nmi_timing/3.even_odd_frames.nes | pass | fail |
| vbl_nmi_timing/4.vbl_clear_timing.nes | pass | fail |
| vbl_nmi_timing/5.nmi_suppression.nes | pass | fail |
| vbl_nmi_timing/6.nmi_disable.nes | pass | fail |
| vbl_nmi_timing/7.nmi_timing.nes | pass | fail |
| ppu_open_bus/ppu_open_bus.nes | pass | fail 3 |
| ppu_read_buffer/test_ppu_read_buffer.nes | pass | pass |
| oam_read/oam_read.nes | pass | pass |
| oam_stress/oam_stress.nes | pass | fail 1 |
| blargg_ppu_tests_2005.09.15b/palette_ram.nes | pass | pass |
| blargg_ppu_tests_2005.09.15b/sprite_ram.nes | pass | pass |
| blargg_ppu_tests_2005.09.15b/vram_access.nes | pass | pass |
| blargg_ppu_tests_2005.09.15b/vbl_clear_time.nes | pass | fail 2 |
| blargg_ppu_tests_2005.09.15b/power_up_palette.nes | pass | fail 2 |
| sprite_hit_tests_2005.10.05/01.basics.nes | pass | pass |
| sprite_hit_tests_2005.10.05/02.alignment.nes | pass | pass |
| sprite_hit_tests_2005.10.05/03.corners.nes | pass | pass |
| sprite_hit_tests_2005.10.05/04.flip.nes | pass | pass |
| sprite_hit_tests_2005.10.05/05.left_clip.nes | pass | pass |
| sprite_hit_tests_2005.10.05/06.right_edge.nes | pass | pass |
| sprite_hit_tests_2005.10.05/07.screen_bottom.nes | pass | pass |
| sprite_hit_tests_2005.10.05/08.double_height.nes | pass | pass |
| sprite_hit_tests_2005.10.05/09.timing_basics.nes | pass | fail |
| sprite_hit_tests_2005.10.05/10.timing_order.nes | pass | fail |
| sprite_hit_tests_2005.10.05/11.edge_timing.nes | pass | pass |
| sprite_overflow_tests/1.Basics.nes | pass | pass |
| sprite_overflow_tests/2.Details.nes | pass | fail |
| sprite_overflow_tests/3.Timing.nes | pass | fail |
| sprite_overflow_tests/4.Obscure.nes | pass | fail |
| sprite_overflow_tests/5.Emulator.nes | pass | pass |
| apu_test/apu_test.nes | pass | fail 1 |
| apu_reset/4015_cleared.nes | pass | pass |
| apu_reset/4017_timing.nes | pass | fail 2 |
| apu_reset/4017_written.nes | pass | fail 2 |
| apu_reset/irq_flag_cleared.nes | pass | fail 3 |
| apu_reset/len_ctrs_enabled.nes | pass | pass |
| apu_reset/works_immediately.nes | pass | fail 2 |
| blargg_apu_2005.07.30/01.len_ctr.nes | pass | fail 4 |
| blargg_apu_2005.07.30/02.len_table.nes | pass | unclear |
| blargg_apu_2005.07.30/03.irq_flag.nes | pass | pass |
| blargg_apu_2005.07.30/04.clock_jitter.nes | pass | fail 2 |
| blargg_apu_2005.07.30/05.len_timing_mode0.nes | pass | fail 3 |
| blargg_apu_2005.07.30/06.len_timing_mode1.nes | pass | fail 3 |
| blargg_apu_2005.07.30/07.irq_flag_timing.nes | pass | fail 2 |
| blargg_apu_2005.07.30/08.irq_timing.nes | pass | fail 2 |
| blargg_apu_2005.07.30/09.reset_timing.nes | pass | pass |
| blargg_apu_2005.07.30/10.len_halt_timing.nes | pass | fail 3 |
| blargg_apu_2005.07.30/11.len_reload_timing.nes | pass | fail 2 |
| dmc_dma_during_read4/dma_2007_read.nes | pass | no text |
| dmc_dma_during_read4/dma_2007_write.nes | pass | no text |
| dmc_dma_during_read4/dma_4016_read.nes | pass | no text |
| dmc_dma_during_read4/double_2007_read.nes | pass | fail |
| dmc_dma_during_read4/read_write_2007.nes | pass | pass |
| sprdma_and_dmc_dma/sprdma_and_dmc_dma.nes | pass | unclear |
| sprdma_and_dmc_dma/sprdma_and_dmc_dma_512.nes | pass | unclear |
| read_joy3/count_errors.nes | unclear | unclear |
| read_joy3/thorough_test.nes | pass | no text |
| mmc3_test_2/rom_singles/1-clocking.nes | pass | fail 3 |
| mmc3_test_2/rom_singles/2-details.nes | pass | fail 2 |
| mmc3_test_2/rom_singles/3-A12_clocking.nes | pass | fail 4 |
| mmc3_test_2/rom_singles/4-scanline_timing.nes | pass | fail 14 |
| mmc3_test_2/rom_singles/5-MMC3.nes | pass | fail 2 |
| mmc3_test_2/rom_singles/6-MMC3_alt.nes | fail | fail 2 |
| mmc3_irq_tests/1.Clocking.nes | pass | fail |
| mmc3_irq_tests/2.Details.nes | pass | fail |
| mmc3_irq_tests/3.A12_clocking.nes | pass | fail |
| mmc3_irq_tests/4.Scanline_timing.nes | pass | fail |
| mmc3_irq_tests/5.MMC3_rev_A.nes | fail | fail |
| mmc3_irq_tests/6.MMC3_rev_B.nes | pass | fail |

blargg's tests that ask for a reset ($6000 = $81: cpu_reset, apu_reset)
get one from the writer 6 frames after the request, at most once in 300
frames; MAME runs its autoboot script again after a soft reset, which
the MAME writer guards against.

### 3.5 Overlap with AccuracyCoin

AccuracyCoin covers most of what the CPU, PPU-timing, DMA and APU tests
of the collection cover (instructions with their dummy cycles, unofficial
opcodes, interrupt latency and hijacks, DMA aborts and halted reads, the
frame counter and length counters, VBlank and NMI timing, sprite 0 hit
and overflow, open bus, the read buffer, OAM quirks), on one NROM
cartridge with a licence and a stated hardware revision. The collection
adds what AccuracyCoin cannot test: the MMC3 (blargg's mmc3_test_2 and
mmc3_irq_tests, the only acceptance tests of the target game's mapper,
run on its very board type), PAL behaviour (pal_apu_tests), the APU's
analog output (apu_mixer, with recordings), controller reads under DMC
DMA (read_joy3), and test programs in several revisions over time, whose
verdicts also show where an emulator's behaviour changed. For phase N2
the plan is: AccuracyCoin as the judge, blargg's MMC3 tests as the
mapper acceptance (locally), the rest of this catalogue as local
regression checks against the ROMs' own verdicts.

### 3.6 Other entries

- HTGDB (GPL-3.0) publishes SMDB text files (SHA-256, path, SHA-1, MD5,
  CRC32, size over the whole iNES file). Its NES 2.0 list has a folder of
  tool and service test cartridges, among them the NTF2 System and Test
  cartridges and the four World Class Service cartridges (Nintendo's
  property: catalogue entries "not usable"), tepples' allpads, vaus and
  overclock tests and the 240p test suite. It has no blargg test,
  AccuracyCoin, nestest or Holy Mapperel. Useful as a source of names
  and hashes, not of expectations.
- puNES (GPL-2.0) is named among the accurate emulators in community
  advice, beside Mesen and Nintendulator. It is a Qt program with
  command-line settings and `--hidden-gui`, but without scripting and
  without a way to run N frames, dump and exit; using it as a further
  oracle would mean patching it. Candidate only, not in phase N1.
- "Writing NES Emulator in Rust" (bugzmanov.github.io/nes_ebook) is a
  tutorial: a readable overview of CPU, bus, PPU and mappers, but a
  secondary source that retells the NESdev wiki, and emulator code that
  this project does not take over. It is no hardware authority; every
  statement in docs/nes-hardware-spec.md keeps its own source and class.

## 4. MAMR (phase N2)

Runs 2026-10-25, interpreter on the board (stage E; stage S gives the
same hash lines), fill 00.

### 4.1 AccuracyCoin

147 of 147 (run of every test, 4228 frames, 13 s; ctest
`nes_mamr_accuracycoin_all`). The way there, each step a correction
after AccuracyCoin's own explanation of the expected hardware behaviour
(TEST-ROM-HW), recorded in docs/nes-hardware-spec.md and
docs/nes-ppu-spec.md: SHA/SHX/SHY/TAS without the high-byte term after a
DMA; the frame IRQ flag cleared at the next get cycle, set for two
cycles under the inhibit bit, the $4017 delay of 3 or 4 cycles by
parity; the NMI hijack window of five cycles and no poll at the end of
BRK and interrupt entries; the controller strobe taken at put cycles;
the internal and external data buses; the DMC DMA bus conflict with the
controller port; the DMA read of $4015 with bit 5 from the external
device; the DMC period latched one APU cycle after the reload; $2002
sprite flags and $2004 at the end of the read; the X-byte range check in
sprite evaluation; the OAM row corruption after a mid-line rendering
stop; the garbage nametable fetch of dot 257 before the horizontal copy;
the sprite X counters with their counting and halted modes; the
secondary OAM address of the sprite fetch and its overflow freeze; the
background shift register load in the dot of the high pattern read; the
octal address latch meeting a $2007 read.

Compared with MesenCE (`accuracycoin.py diff`), seven results differ:
MAMR passes "DMC Reload Timing", "BG Serial In", "ALE + Read", "Hybrid
Addresses", "Stale Sprite Shift Regs" and "Frozen OAM2 Increment", which
MesenCE fails; "Controller Clocking" passes in both, with success code 1
in MAMR (NES front-loader: consecutive reads clock once) and code 2 in
MesenCE (Famicom behaviour). "Sprites On Scanline 0" gives code 1
(composite RP2C02) in both.

Alignment-dependent answers: "$2002 flag timing" takes the alternative
key of test 1 and the $40 variant of test 2 (AccuracyCoin: alignments 2
and 3); "OAM Corruption" calibrates to a 3-dot $2001 delay (alignments 1
and 2). docs/nes-ppu-spec.md section 15.11 records the mixture.

### 4.2 nes-test-roms

`testroms.py run DIR --oracles mamr` (run 2026-10-26): 88 of the 90
catalogued ROMs pass. power_up_palette fails with the fill palette and
passes with MesenCE's power-on palette (`--palette`); the hardware
palette is unspecified. read_joy3 count_errors has no verdict at the
frame cap (as in both oracles); run to frame 6000 it ends with
"Conflicts: 67/1000" and no failure: the read routine's compensation
works, and the count of a statistical test has no expected value.
Everything else passes, including all of blargg's APU 2005 tests and
apu_reset, the dmc_dma_during_read4 and sprdma_and_dmc_dma tests,
vbl_nmi_timing 1-7, the sprite hit and overflow tests, oam_read,
oam_stress, ppu_open_bus and every MMC3 test (the two revision A tests
with `--mmc3-rev a`). Four needed corrections in phase N2: the APU
channel enables clear at power-on, length halt and reload acting after
the next cycle's clock, separate $2007 read and write state machines,
and no pattern address at dot 0 of the pre-render line.

13 of them use MMC1 (instr_test-v5 official_only and all_instrs,
instr_misc, instr_timing, cpu_interrupts_v2, blargg_nes_cpu_test5
official and cpu, ppu_vbl_nmi, apu_test) or CNROM (cpu_dummy_reads,
ppu_read_buffer, read_joy3 count_errors and thorough_test) and ran in
MAMR only after these boards were added on 2026-10-26
(docs/nes-hardware-spec.md sections 3.9 and 3.10). With the boards,
nine passed at once; two corrections followed from the others, each
after the test's own expectation:

- LXA ($AB, "ATX #n") in all_instrs and blargg_nes_cpu_test5 cpu.nes:
  the instruction checksums pass only with A = X = imm (magic constant
  $FF); $EE and $00 fail. Both readmes list ATX as tested and mark the
  opcodes with unreliable results separately (XAA, AXA, XAS, LAR), so
  the author's consoles gave a stable LXA result. MAMR now uses $FF for
  LXA and keeps $EE for ANE (docs/nes-hardware-spec.md section 4.2);
  AccuracyCoin stays at 147/147, the SingleStepTests harness compares
  the 4,422 LXA cases in which the suite's $EE gives another result
  with the suite's value put in.
- ppu_vbl_nmi 10-even_odd_timing failed test 2 ("Clock is skipped too
  soon, relative to enabling BG"): the odd-frame skip decision now takes
  the rendering signal of the dot after (261, 339)
  (docs/nes-ppu-spec.md section 4.1); one dot later fails test 3.
  vbl_nmi_timing 3 and AccuracyCoin are unchanged.

MMC3 A12 filter sweep (`--mmc3-edges N`, mmc3_test_2 1-4 and
mmc3_irq_tests 1-4): N = 1 and 2 fail 2-details/2.Details and the
scanline timing tests, N = 3 to 8 pass all; the CHOICE stays 3.

### 4.3 Against MesenCE frame by frame

docs/nes-oracles.md section 6: without input equal in every field, cyc
and dot; with input instruction by instruction equal until frame 438,
where a DMC timer difference that AccuracyCoin decides against MesenCE
("DMC Reload Timing") moves a DMA by 21 cycles.

### 4.4 Super Mario Bros. 3

The target game of the path (docs/nes-architecture.md), local only, not
distributed:

| item | value |
|---|---|
| release | Super Mario Bros. 3 (USA) (Rev 1), iNES file of 393,232 bytes |
| header | `4E 45 53 1A 10 10 40 00`, rest 0: 16 x 16 KiB PRG, 16 x 8 KiB CHR, mapper 4, horizontal mirroring bit (the MMC3 decides), no battery, iNES 1.0 |
| PRG ROM | 256 KiB, CRC32 A0ED7D20 (revision 1) |
| CHR ROM | 128 KiB, CRC32 C2928C49 |
| PRG + CHR | CRC32 2E6301ED, SHA-1 bb894d104c796f69ba16587eb66c0275f5c2fc02 |
| file | SHA-1 6bd518e85eb46a4252af07910f61036e84b020d1 (the hash lines' `rom=`) |
| board | NES-TSROM, Sharp MMC3B (docs/nes-hardware-spec.md section 1) |

The CRC32s are those of the cartridge databases for revision 1, so the
dump agrees with them; `nes_cart_identify` names it. The European file
in the same folder (PRG CRC32 80CD1919, CHR CRC32 7970A157) is not a
target (PAL is not built).

Results, 2026-10-25, interpreter (stage E; stage S gives the same hash
lines over the 1600 frames of the ctest), fill 00, 3000 frames:

- Boot without input: the curtain from frame 11, the title nametable
  complete at frame 196 (behind the black screen of the intro), the logo
  from frame 407 (its palette cycle), the full title picture at frame 451,
  the menu nametable at frame 1584; then the title's attract loop.
  MesenCE shows the same picture in every one of these frames.
- With `tools/oracle/nes/inputs/smb3-1-1.txt` (not published): START at the curtain and
  in the menu, the World 1 map from frame 270, World 1-1 from frame 650
  (Goombas stomped, coin blocks, the pipe, a fall into a pit at frame
  1550, back on the map). The script does not take a mushroom: the
  question blocks it reaches give coins, and a search over jump timings
  did not find the power-up block.
- Against MesenCE (`gates.py ab`, docs/nes-oracles.md section 6): without
  input cpu, vram, oam, pal, prgram, prgmap, chrmap, mirq and inp are
  equal in all 3000 frames; four findings S1-S4 explain every other
  difference: S1 the NMI during a taken branch (MAMR follows the wiki
  and a 6502 transistor-level simulation, MesenCE does not; from frame
  24), S2 the $2007 read on an ALE dot
  ([ACC "ALE + Read"], which MesenCE fails; from frame 15), S3 the OAM
  row corruption (MesenCE's default has it off; from frame 114 with
  input), S4 the background prefetch after rendering is switched on
  again (line 194 in the level). With input S1 moves the strobes from
  frame 380 and the course of the game from frame 1182.
- MMC3: the IRQ latch is only ever $C0 or $C1 (never 0, so revisions A
  and B behave alike here); the A12 filter must count at least 3 M2
  falls (1 and 2 break the status bar), 3 to 6 agree with MesenCE.
- Code survey for phase N3 (instruction starts, jump tables, stack
  tricks, bank use): docs/nes-smb3-survey.md.
- ctests `nes_smb3_title_local` (label local) and
  `nes_mamr_ab_mesence_smb3` (label oracle), docs/nes-oracles.md
  section 7.

### 4.5 Phase N3: the emitted blocks

Runs 2026-10-26, the game artefacts that tests/nes builds from the local
ROMs (`nes_recomp`, docs/nes-architecture.md section 3), stage E, fill
00, through `nes_headless --cartridge`:

- AccuracyCoin: 147 of 147 natively (tally at frame 4228, the same frame
  as the interpreter; ctest `nes_native_accuracycoin_all_local`), and the
  full run's hash lines equal to the interpreter's (`nes_native_
  accuracycoin_local`). Discovery in four rounds from the reset vector
  and the miss logs (310, 4467, 4491 blocks); the misses that stay are
  the ROM's code in RAM ($0050-$0700, the NMI and IRQ handlers it
  installs), in the I/O and open-bus range ($2000-$5FFF: the open-bus
  execution tests) and the instruction at $FFFF whose operand wraps to
  $0000 ("PC Wraparound"): 35 miss-log entries, 8108 interpreted
  instructions of the run. Code below $8000 is not translated in phase
  N3.
- nestest: every one of the 8991 log lines equal, each instruction run by
  an emitted block with budget 0 (one instruction per block call, so
  every line is checked as in the interpreter; ctest
  `nes_nestest_native_local`). Its artefact comes from the vectors and
  the automation entry $C000 alone (no seed list for a ROM without a
  licence): 2614 blocks, 93 instructions interpreted; with the miss log
  of one run as seeds 2 (the code at $0300 in RAM). Nothing of nestest
  is distributed.
- Super Mario Bros. 3: docs/nes-smb3-survey.md section 4.

### 4.6 Phase N4: the APU channels and the mixer

Runs 2026-10-26 with the channels, the mixer and hash format 2
(docs/nes-audio-spec.md), GCC debug build, stage E, fill 00.

- AccuracyCoin: 147 of 147 in the interpreter and natively (ctests
  `nes_mamr_accuracycoin_all`, `nes_native_accuracycoin_all_local`); the
  channels change nothing a program can read.
- blargg's suites (`testroms.py run --oracles mamr`), MAMR's verdict and
  MesenCE 2.2.1's:

| ROM | MAMR | MesenCE 2.2.1 |
|---|---|---|
| apu_test/apu_test.nes (all 8) | pass | pass |
| apu_test/rom_singles/1-len_ctr.nes | pass | pass |
| apu_test/rom_singles/2-len_table.nes | pass | pass |
| apu_test/rom_singles/3-irq_flag.nes | pass | pass |
| apu_test/rom_singles/4-jitter.nes | pass | pass |
| apu_test/rom_singles/5-len_timing.nes | pass | pass |
| apu_test/rom_singles/6-irq_flag_timing.nes | pass | pass |
| apu_test/rom_singles/7-dmc_basics.nes | pass | pass |
| apu_test/rom_singles/8-dmc_rates.nes | pass | pass |
| apu_reset (4015_cleared, 4017_timing with delay 10, 4017_written, irq_flag_cleared, len_ctrs_enabled, works_immediately) | 6 pass | 6 pass |
| blargg_apu_2005.07.30 01-11 | 11 pass | 11 pass |
| dmc_dma_during_read4 (5), sprdma_and_dmc_dma (2) | 7 pass | 7 pass |
| dmc_tests (buffer_retained, latency, status, status_irq) | audible | audible |
| apu_mixer (dmc, noise, square, triangle) | audible | audible |

- dmc_tests and apu_mixer have no verdict a program can read. Both
  emulators run them alike: every hash field, apu included, equal with
  MesenCE in every frame (`gates.py ab`, dmc_tests 120 frames, apu_mixer
  to the end of each test). In MAMR every dmc_tests ROM reaches its final
  tone, so its waits on $4015 and on the DMC IRQ end.
- apu_mixer, measured: the audio of the run (`nes_headless --wav`, the
  output stage of docs/nes-audio-spec.md section 9) and the collection's
  recording, each as RMS over 50 ms windows; the middle part between the
  two beeps (without 0.2 s at each edge) against the mean of the beeps.
  The level of the recordings is their own; only the ratios compare.

| test | recording: middle mean (max) against the beeps | MAMR: middle mean (max) |
|---|---|---|
| dmc | -30.2 dB (-24.0 dB) | -35.5 dB (-32.7 dB) |
| noise | -18.8 dB (-13.8 dB) | -19.3 dB (-14.4 dB) |
| square | -37.5 dB (-22.6 dB) | -38.3 dB (-29.1 dB) |
| triangle | -33.9 dB (-30.2 dB) | -36.4 dB (-33.5 dB) |

  The noise test fades noise in and out against the DMC; its level
  relative to the beeps agrees within 0.5 dB, which checks the noise
  against the DMC in the tnd formula. In the three cancellation tests
  MAMR's residual lies 1 to 5 dB below the recording's: the formula
  cancels at least as well as the console (the recordings add an analog
  noise floor of about -54 dB and their own imperfections; the length of
  every part agrees to 0.1 s). No finding.
- Against MesenCE, the apu field (docs/nes-audio-spec.md section 10.2):
  Super Mario Bros. 3 equal without input in 3000 frames and with the
  World 1-1 script up to frame 528, after which finding S1 separates the
  games; with MesenCE's NMI rule switched on locally equal in 2990 of 3000
  frames, the other 10 being finding A1 (the DMC output clock one APU
  cycle later in MAMR relative to the timer; docs/nes-oracles.md section
  6).
- The machine with sound: `play_roundtrip_smb3` and `_interp` play the
  game with tests/machine/smb3-game.pads (title, map, World 1-1); 791
  different audio hashes in 1200 frames, the front end equal to the
  machine without it, the state of frame 600 repeating frames 601-1200
  with picture and sound; `machine_state_smb3_game` six states from the
  map to the level; `play_dummy_smb3` the sample count of 300 frames
  against the rates.

### 4.7 Phase P: PAL

Runs 2026-10-27 (docs/nes-architecture.md section 11), RelWithDebInfo
build, stage E, fill 00:

- NTSC unchanged: Super Mario Bros. 3 (USA) 3000 frames with the World
  1-1 script (stage E) and without input (stage S) byte-identical to the
  build before the PAL work; AccuracyCoin 147/147 in the interpreter and
  natively; nestest and the blargg suites of the ctests as before (ctest
  of every NES, 6502 and machine test: all pass).
- pal_apu_tests, forced PAL: 10 of 10 pass (MesenCE 10/10, MAME 1/10,
  docs/nes-oracles.md section 8.1). With the NTSC tables the same ROMs
  fail 05 and 08, so they see the region.
- demo_pal, forced PAL: the drawn line starts at x = 83 (two flashing
  pixels, solid from 85) between the reference lines at 82 and 84, as
  the readme describes a PAL console.
- Super Mario Bros. 3 (Europe), PAL from the cartridge database: G1
  (two runs byte-identical, stage S equal to stage E over 3000 frames
  with input); the comparison with MesenCE and MAME and its findings in
  docs/nes-oracles.md section 8.2; natively with smb3-eu.mamrcart equal
  to the interpreter in every hash line, 0 misses in both runs (section
  4.5 for the method; docs/nes-smb3-survey.md section 5).
