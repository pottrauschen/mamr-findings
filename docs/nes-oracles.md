# NES oracles: setup, limits, results

Phases N1 and N2 of docs/nes-architecture.md. The oracles write the hash
lines of docs/nes-oracle-format.md; `compare.py` compares them,
`gates.py` runs the gates, `accuracycoin.py` decodes AccuracyCoin's
results. Since phase N2 MAMR writes the same lines (tools/nes_headless,
section 6). Results below are from 2026-10-24 and 2026-10-25 on x86-64
Linux. File names without a directory refer to `tools/oracle/nes/`.

| oracle | role | licence | build | fields | speed |
|---|---|---|---|---|---|
| MesenCE 2.2.1 | primary oracle | GPL-3 (external tool) | release binary | all fields | about 110 frames/s (AccuracyCoin run of every test: 4132 frames in 38 s) |
| MAME 0.285 | second oracle | GPL-2+ / BSD-3 (external tool) | distribution package | all except ppu and dot | about 50 frames/s |
| TriCNES | candidate | MIT | not built | | |

Neither is linked into MAMR or shipped with it, and neither is a template
for MAMR code (docs/nes-architecture.md section 1).

## 1. Test ROMs

AccuracyCoin (MIT), commit b4b5952f8ef57618d798c8d97cd099ab352e62e6, the
author's assembled ROM of that commit; ROM and source go to
`tests/data/accuracycoin/` (local, not distributed). Details, hashes and results in
docs/nes-test-evidence.md. nestest is local only (no licence) and runs in
the interpreter, not in the oracles.

## 2. MesenCE

MesenCE 2.2.1 (`nesdev-org/MesenCE`), `Mesen_2.2.1_Linux_x64.zip`, sha256
`c88ff4d251b407515c43d3332d641927655cd69fb538996b6a21da4509dbb58f`; the
setting names below were read from the source of tag 2.2.1 (commit
20ba206cef5ba207c21203176d02cb9f43dda9fb: `UI/Config/NesConfig.cs`,
`UI/Config/ConfigManager.cs`, `UI/Utilities/TestRunner.cs`,
`Core/Debugger/LuaApi.cpp`, `Core/NES/NesCpu.cpp`, `Core/NES/NesPpu.cpp`,
`Core/NES/Mappers/Nintendo/MMC3.h`).

`mesen/run_mesen.sh rom.nes mesen/nesfh.lua` starts it in test-runner mode
(`--testrunner`) under `xvfb-run` with a private HOME (`MESEN_NES_HOME`,
default `~/.cache/mamr-mesen-nes-home`) and the switches
`--nes.ramPowerOnState=AllZeros` (`AllOnes` with `MESEN_FILL=ff`),
`--nes.region=Ntsc`, `--nes.autoConfigureInput=false`,
`--nes.port1.type=NesController` and
`--debug.scriptWindow.allowIoOsAccess=true`. The script is configured
through `FH_*` variables (head of nesfh.lua); the runner scripts remove
the output file before every run, so a failed run never leaves an old
file behind.

Traps:

- Without `$HOME/.config/MesenCE/settings.json` MesenCE ignores
  `--testrunner` and opens its setup wizard. run_mesen.sh writes the file
  before every run with one setting: `Nes.UserPalette`, a 512-entry
  palette whose entry p is the RGB value p. With a 512-entry palette
  MesenCE uses it as the full emphasis palette (`NesConfig.ApplyConfig`,
  `NesDefaultVideoFilter::GetFullPalette`), so `emu.getScreenBuffer()`
  returns the colour index plus the emphasis bits of every pixel, and the
  script canonicalises them (format section 5). The test runner never
  writes settings back (`ConfigManager.DisableSaveSettings`).
- Without `--nes.port1.type=NesController` no controller is plugged in
  and `emu.setInput` has no effect. MesenCE clears the controller state
  once per frame (scanline 241, `BaseControlManager::UpdateInputState`)
  and raises `inputPolled`; the script sets the held buttons again there
  and at every strobe write ($4016 with bit 0 set), in the write callback
  that runs before the write reaches the controller.
- The NES has no frame-skipping switch in MesenCE (only SNES, PC Engine
  and GBA have `DisableFrameSkipping`); the test runner does not render.
- The CPU's IRQ and NMI flags are hidden from Lua (`NesCpu::Serialize`
  writes them only outside the Lua map format), so the format's mirq has
  no IRQ-line byte.
- PPUCTRL is kept only as decoded flags without bit 6; the script
  records the last bytes written to $2000 and $2001 with a write callback.
- Power-on: the PPU starts at scanline 0, dot 0 (`NesPpu::Reset`); the
  CPU spends 8 cycles before the first opcode fetch (`NesCpu::Reset`,
  "The CPU takes 8 cycles before it starts executing the ROM's code"), so
  `cpu.cycleCount` is 8 at the first fetch; the CPU/PPU alignment is
  fixed (PPU offset 1 master clock) unless `RandomizeCpuPpuAlignment`
  is set; header key `align=1`. `dot` is `ppu.masterClock / 4`.
- The MMC3's power-on registers come from `GetPowerOnByte`, which is 0
  without `RandomizeMapperPowerOnState`; $A001 is therefore 0 (PRG RAM
  disabled). MAME differs (section 3).
- For an iNES 1.0 NROM image MesenCE provides 8 KiB of work RAM at $6000
  (`nesWorkRam`); the `prgram` field hashes it.
- The OAM row corruption after a mid-line rendering stop is off by
  default (`Nes.EnablePpuOamRowCorruption = false`, `NesConfig.cs`;
  `NesPpu.cpp` checks it before corrupting), and the oracle runs keep the
  default. MAMR models the corruption (docs/nes-ppu-spec.md section 6.6),
  so every game that switches rendering off inside a line differs in oam
  (Super Mario Bros. 3, section 6). With
  `--nes.enablePpuOamRowCorruption=true` MesenCE corrupts too, but not in
  the same rows as MAMR (not traced further).
- The MMC3's bank registers power on as R0-R7 = 0, 2, 4, 5, 6, 7, 0, 1
  (`MMC3.h` `ResetMmc3`, `GetPowerOnByte` with these defaults); MAMR
  takes the same values (docs/nes-hardware-spec.md section 3.2).

Sampling: `endFrame` is raised when the PPU starts scanline 240, dot 0
(`NesPpu::ProcessScanlineFirstCycle`, `SendFrame`), inside the CPU cycle
that runs those dots. The script then registers an exec callback over the
whole address space and removes it at its first call, which is the opcode
fetch of the next instruction (an IRQ entry at that boundary has run by
then); `cpu.pc` there is the address of that opcode.

## 3. MAME 0.285

`mame/run_mame.sh rom.nes` with `mame/nesfh_mame.lua` (driver `nes`, no
BIOS; `-cart` loads the file, the board comes from the iNES header). The
item and space names below were read from the source of tag mame0285
(`src/mame/nintendo/nes.cpp`, `src/devices/video/ppu2c0x.cpp`,
`src/devices/bus/nes/nes_slot.cpp`, `mmc3.cpp`) and checked against the
running driver. Limits:

- Sampling point is the `frame_done` callback, at the end of the screen
  frame, not the first instruction boundary after scanline 240, dot 0:
  its frame n lies about 2500 CPU cycles (22 lines) after MesenCE's frame
  n on AccuracyCoin (MAME frame 1 at cycle 29780, MesenCE at 27281). cpu
  and pc are not comparable at the instruction level; `dot` is `-`.
- `ppu` is `-`: the 2C02 device keeps the rendering address
  (`m_refresh_data`) and the address of $2007 accesses
  (`m_videomem_addr`) apart; `t` is `m_refresh_latch`, but there is no
  single `v`.
- RAM fill: $00 at even and $FF at odd addresses (`nes.cpp` machine
  start), header `fill=00ff`. AccuracyCoin's zero page $35 is therefore
  $FF at power-on, which the AccuracyCoin logic of the writers takes into
  account (the pass counts as running only while $35 is exactly 1).
- MMC3 $A001 powers on as $80 (PRG RAM enabled, `nes_txrom_device`
  `mmc3_start`), against 0 in MesenCE.
- Inputs: the script steps the input script at every strobe (a write tap
  on $4016) and sets the ioport fields of `:ctrl1:joypad:JOYPAD`; MAME
  applies field values at its next per-frame input update, not at the
  strobe. The write tap object must stay referenced (a global), or Lua's
  garbage collector removes the tap silently (found here: no strobes
  were counted until then).
- The picture: `screen:pixels()` gives RGB; the script inverts the 512
  pens of the PPU device's palette. Pens with equal RGB are exactly those
  the canonical rules merge (format section 5); the script would record
  `pencollisions=` in the header otherwise (none found).
- prgmap from `m_prg_bank` (8 KiB bank numbers), chrmap from
  `m_chr_orig` (byte offsets), mirq from the MMC3 device's
  `m_irq_count`, `m_irq_count_latch`, `m_irq_clear`, `m_irq_enable`.
- Deterministic: two runs give byte-identical files (G2, section 5).

## 4. AccuracyCoin under the oracles

`gates.py accuracycoin ORACLE ROM ASM` (docs/nes-test-evidence.md
section 1). MesenCE runs every test in one pass (141/147). MAME 0.285
does not survive that pass: it sticks in "VBlank end" and "NMI Timing",
and with those skipped the pass loop breaks (the ROM's counter of started
tests passes 147, pages repeat, its name printer loops at $F28F). The
recorded MAME result therefore comes from `--per-page`: every menu page
from power-on (RIGHT presses to the page, A on the page line, the writer
watching zero page $34), 22 runs in 132 s, 85 of 147 passed, 61 failed,
and "Misaligned OAM behavior" skipped because after it the page loop
always goes back to an earlier test (detected as `reason=restart`).
MesenCE gives 141/147 with either method. The tables are in
docs/nes-test-evidence.md section 2.

Hang detection in the writers (`FH_ACC_HANG`, 1200 frames): a test that
makes no progress, or (in the run of one page) a pass that goes back to
an earlier test, ends the run with a `# hang` comment (`reason=stuck` or
`reason=restart`); `gates.py` reruns with the test marked
skipped and reports it. The longest test of the pinned commit takes well
under 300 frames in MesenCE.

## 5. Gates

AccuracyCoin, no input unless stated, 2026-10-24.

**G2, each oracle twice** (300 frames): MesenCE identical (90293 bytes,
about 100 frames/s), MAME identical (81957 bytes, about 65 frames/s with
the per-frame hashing). The full AccuracyCoin runs were repeated with
identical T lines for both.

**G3** (internal RAM byte $0100 XOR $5A at frame 60, 120 frames): for both
oracles compare.py reports `first divergence: frame 60 fields ram` and no
other field. **Dump check**: the dumps of frames 1, 60 and 120, rehashed
by hashline.py, reproduce every field of both oracles' F lines, so the
Lua and the Python implementations of the format agree.

**MesenCE against the reference** (`tests/nes-oracle/reference/accuracycoin-mesence.hash`,
300 frames): equal in every field and in inp, cyc and dot.

**G2 between the oracles, MesenCE against MAME** (300 frames, `gates.py
cross --from 60`):

| field | differing frames | reason |
|---|---|---|
| prgram, prgmap, chrmap, mirq | 0 | NROM: nothing changes |
| oam | 0 | after the attribute mask of the format (MAME stores bits 2-4 of the attribute byte, MesenCE does not; before the mask 297 frames differed) |
| pal | 2 (frames 1-2) | the palette RAM before the ROM writes it |
| vram | 28 (up to frame 50) | boot timing: AccuracyCoin's power-on tests wait for VBlank and take a different number of frames in the two oracles (MAME reaches the menu's first strobe at frame 52, MesenCE at frame 29) |
| img | 53 (up to frame 53) | as vram; the picture of frame n is not the same screen while the boot differs |
| cpu | 40 (up to frame 52) | the sampling points differ (section 3); in the menu's idle loop the registers agree |
| ram | 300 | 248 bytes differ at frame 300: 215 odd addresses that hold MAME's $FF fill and were never written; the rest in $0340-$0374 (written by the ROM during its boot; their origin in the source was not traced), stack bytes at $01E4-$01E7 and $01FD, and $000E and $0012 |
| inp | 276 | the strobe count, shifted by the boot difference |
| ppu, dot | not compared | MAME writes `-` |

From frame 60 on, vram, oam, pal, img, prgram, prgmap, chrmap and mirq are
equal in every frame; the ctest requires exactly that. The comparison is a
record of what the two oracles share, not a statement about the hardware;
where they differ, AccuracyCoin's expectation or a console run decides.

## 5a. Further test ROMs (nes-test-roms)

`testroms.py run DIR` runs 90 ROMs of christopherpow/nes-test-roms (local
only, no licence) through both oracles with the R and N lines of the
format (section 9 there: blargg's $6000 protocol with reset requests, or
the text on the nametables). MesenCE passes 87 (the other three are the
two MMC3 revision A tests, which a revision B emulation cannot pass, and
one statistical test without a verdict), MAME 36. The catalogue with the
licences, the hardware provenance, TASVideos' criteria against our gates
and the full table is docs/nes-test-evidence.md section 3. A ROM's
verdict is recorded there as the oracle's behaviour; it is not a gate.

## 6. MAMR: its writer, gate G1 and the comparison with MesenCE

`nes_headless ROM --frames N [--out FILE] [--input SCRIPT] [--fill 00|ff]
[--stage e|s] [--palette FILE] ...` runs the interpreter on the board and
writes the hash lines (header keys `oracle=mamr core=mamr-interp align=1
stage=e|s`), the T line of AccuracyCoin (`--acc`), blargg's R line and
the N line (`--blargg --screen`), dumps (`--dump-dir`, `--dump-at`) and
fault injection (`--inject`). `--trace-pc A,A-B` writes a comment line
`# pc A cyc N` at every instruction start at those addresses; the
MesenCE writer does the same with `FH_TRACE_PC`, so that two runs can be
compared instruction by instruction (cycle numbers agree: MAMR's `cyc` is
the last completed cycle, MesenCE's `cpu.cycleCount`). `--trace-write A-B`
writes a comment line `# w ADDR=VV pc P cyc N line L dot D` at every CPU
write to that range (P is the address after the writing instruction),
`--pc-stats FILE` the code survey of docs/nes-smb3-survey.md. `gates.py` and
`testroms.py` take `mamr` as a third "oracle" (`MAMR` or the default
build path). Since phase N3 the same program runs the emitted blocks of a
game artefact (`--cartridge FILE`, header key `core=mamr-native`, the
dispatcher's counts with `--stats`, its miss log with `--miss-log
FILE`); `nes_headless_native` links the blocks of one ROM
(`MAMR_NES_BLOCKS_CPP`) and takes `--interp` for the interpreter alone.
`gates.py ... --mamr-args "--cartridge FILE"` runs any gate natively;
`tests/nes/compare_native.py` compares a native run with the
interpreter line by line.

**G1** (`gates.py g1`): MAMR twice byte-identical, and stage S (the line
renderer) against stage E in every field with cyc and dot; AccuracyCoin
with its input script, 900 frames: identical. G3 and the dump check as
for the oracles: pass (frame 60, field ram only; frames 1, 60, 120
rehashed by hashline.py equal).

**MAMR against MesenCE** (`gates.py ab`): MesenCE runs with a dump of
frame 1, MAMR starts from that dump's palette RAM (the power-on palette
is unspecified on the hardware; MesenCE takes a fixed table), then every
field, inp, cyc and dot are compared.

- AccuracyCoin without input, 300 frames: equal in every field, cyc and
  dot. Against the reference file without the oracle (MAMR with
  its own power-on palette): equal except pal and img in frames 1-2 and
  the bytes $0340-$035F of ram, where the ROM keeps a copy of the
  power-on palette.
- AccuracyCoin with its input script (the run of every test): the
  instruction traces agree in address and cycle for 4.3 million
  instructions, until frame 438. Two earlier field differences come
  from tests MesenCE fails: frame 402 (img, 8 pixels on line 1 during
  "NMI Overlap IRQ": MAMR draws the halted sprite shift registers when
  rendering is switched on, [ACC "Stale Sprite Shift Regs"]); and the
  instruction divergence at frame 438 ("Implicit DMA Abort", the DMC DMA
  of its sync loop lands 21 cycles apart): a $4010 write one cycle after
  a DMC timer expiry (MAMR's numbering), which AccuracyCoin's "DMC Reload
  Timing" counts as a write in the cycle of the reload (new period) and
  MesenCE does not (it fails that test). From there the runs differ in
  timing; both pass every test they share. Before the fix of the DMC
  timer's power-on phase (docs/nes-hardware-spec.md section 6.4) the
  first divergence was at frame 241.
- The full results by test: docs/nes-test-evidence.md section 4.

**Super Mario Bros. 3** (USA, Rev 1; docs/nes-test-evidence.md section
4.4), 3000 frames each, `gates.py ab` (MesenCE with its default
settings, MAMR from MesenCE's power-on palette). The instruction traces
(`--trace-pc 0000-ffff`, `FH_TRACE_PC`) agree in address and cycle for
the first 218,723 instructions (frame 24). Every difference found has a
cause; none was adjusted:

| | field, first frame | cause | judge |
|---|---|---|---|
| S1 | cpu timing: cyc, dot, pc from frame 24, ram from 25 | NMI during a taken branch: the VBlank NMI rises in the operand cycle of `BPL` (the title's wait loop at $A81C). MAMR applies the wiki's "a taken non-page-crossing branch ignores IRQ/NMI during its last clock" to NMI as well and takes the NMI one instruction later; MesenCE applies it to IRQ only (`NesCpu.h` `BranchRelative` touches `_runIrq`, not `_prevNeedNmi`) | SIM for MAMR: a transistor-level simulation of the 6502 (perfect6502) delays NMI and IRQ alike (docs/nes-hardware-spec.md section 5.7, 2026-10-26); the wiki and blargg's cpu_interrupts_v2 readme say the same (DOC); AccuracyCoin tests the rule with IRQ only. A finding against MesenCE |
| S2 | ppu (the $2007 read buffer only) from frame 15; img from frame 1818 | the status bar IRQ at line 193 sets v = $0B00 and reads $2007 during the sprite fetches. When the PPU access falls on an ALE dot (odd dot), MAMR feeds the octal latch from the data bus ([ACC "ALE + Read"]); the buffer differs in 1180 of 1506 such reads and never on even dots (1482). The next fetch reads through that latch, so a sprite's pattern on line 194 differs in 108 frames (8 pixels, the walking figure of the title) | [ACC "ALE + Read"], TEST-ROM-HW: MAMR passes, MesenCE fails |
| S3 | oam from frame 114 (with input), img line 194 in the level | the level's IRQ handler switches rendering off at line 193, dots 7-29, and on at dots 331-340 (or early on line 194). MAMR corrupts OAM row (dot - 1) / 2 when rendering comes back (docs/nes-ppu-spec.md section 6.6); MesenCE has the corruption switched off (section 2). At frame 112 the menu switches rendering off at line 1, dot 263 (the CHOICE range 257-320) | [ACC "OAM Corruption"], TEST-ROM-HW, for dots 1-256; dots 257-320 CHOICE |
| S4 | img, a few pixels of line 194 in the level (608 frames with input) | rendering switched on again inside a background prefetch at the end of line 193: the first pixels of line 194 come from partly fetched tiles; equal whenever the write lands on dot 338 of line 193 or dots 0 and 8 of line 194, different on the other dots | MAMR follows [ACC "Stale BG Shift Registers", "BG Serial In"]; MesenCE fails "BG Serial In" (INFERENCE that this is the cause) |

Without input every other field (cpu, vram, oam, pal, prgram, prgmap,
chrmap, mirq, inp) is equal in all 3000 frames; ram differs from frame 25
only as a consequence of S1 (with the diagnostic NMI rule below it is
equal). With input, S1 also moves the strobes: inp
differs from frame 380 and the game takes another course from frame 1182
(the input script is bound to strobes, not to game states).

As a diagnosis only (a local diagnostic switch that made MAMR take an
NMI in the last cycle of a taken branch, as MesenCE does), MAMR equals
MesenCE in cpu, ram, vram, pal, prgram, mirq, inp, cyc and dot over all
3000 frames of both runs; then only S2, S3, S4 remain. So S1 is the only
timing difference, and the MMC3 IRQ timing agrees as far as the fields
show it (mirq, cyc and the picture of the split in every frame).
Rerun 2026-10-26 after S1 was decided by simulation (MAMR unchanged, the
input run of 3000 frames): cyc and dot from frame 24, ram from 25, inp
from 380, cpu and prgmap from 1182, as before; the game's course after
frame 1182 is MAMR's, MesenCE's NMI rule is the deviation.

MMC3 A12 filter (`--mmc3-edges N`, the diagnostic NMI rule, input run):
N = 1 and 2 break the game (the IRQ counter differs from frame 12, the
status bar split moves, everything diverges); N = 3 to 6 give MesenCE's
mirq and every other state in all 3000 frames; N = 8 to 12 keep the game
equal but leave the counter one clock higher at the sampling point in
2106 frames (an A12 low phase of 6 or 7 M2 falls, counted with N = 6 and
swallowed with N = 8; N = 7 was not run). The game itself (it runs on the console) excludes 1 and 2, as
blargg's tests do; the CHOICE 3 stays.

Sprite 0 and scroll splits: the status bar split comes from the MMC3 IRQ
at line 193 (`--trace-write`); its writes ($2006, $2005, $2000, and in
the level $2001) give the same v, t, x, PPUSTATUS (with the sprite 0 and
overflow flags) and picture in every frame apart from S2 to S4.

### 6.1 Audio (phase N4): the apu field

Hash format 2 (docs/nes-oracle-format.md) adds `apu`, the channel state
both writers can name, and `snd`, MAMR's native samples. MesenCE's Lua
interface exposes its APU state (`emu.getState()`, keys `apu.square1.*`,
`apu.triangle.*`, `apu.noise.*`, `apu.dmc.*`, `apu.frameCounter.*`, read
at the sampling point), but no audio output, so its writer gives `apu`
and writes `snd` as `-`; MAME's writer gives neither. Found while
building the field (both now part of the format): MesenCE keeps the sweep
period as P + 1 (0 before the first $4001 write) and lets its sweep
divider run free before that write, and holds the DMC's current address
as 0 before the first sample; the divider is left out of the field and
the address written with bit 15 set.

Results 2026-10-26 (docs/nes-audio-spec.md section 10.2,
docs/nes-test-evidence.md section 4.6):

- Super Mario Bros. 3 without input, 3000 frames: apu equal in every
  frame (the game is silent without input).
- Super Mario Bros. 3 with inputs/smb3-1-1.txt (not published): apu equal up to frame
  528; from 529 the games play different effects because of S1 (the
  input moves by a strobe from frame 380). With the diagnostic NMI rule
  above, apu is equal in 2990 of 3000 frames; the other ten are A1.
- blargg's dmc_tests and apu_mixer: every field equal in every frame.
- AccuracyCoin (300 frames of the reference): apu equal; required by
  `nes_mamr_reference_accuracycoin`, and by `nes_mamr_ab_mesence_smb3`.

| | field, frames | cause | judge |
|---|---|---|---|
| A1 | apu, the DMC output level by one step (2) or the sample buffer, 10 frames of 3000 with the diagnostic NMI rule (790, 792, 794, 1114, 1118, 1442, 1749, 2181, 2469, 2901) | a DMC sample plays and the sampling point falls next to an output clock: both sides are in the same CPU cycle with the same bytes remaining, MesenCE's timer reads 0 with the delta step and the buffer refill done, MAMR's timer reads 0 with them still due (MAMR clocks the output unit one APU cycle later relative to its timer, after the DMA read of the get cycle; docs/nes-hardware-spec.md section 6.4). Taking the period at the reload instead of one APU cycle later (the rule of [ACC "DMC Reload Timing"]) does not remove them | the output level cannot be read by a program; the DMA timing, which can, passes AccuracyCoin's DMC and DMA tests in MAMR. UNKNOWN on the hardware (docs/nes-audio-spec.md section 12); a CHOICE, recorded |

## 7. ctest

`tests/nes-oracle/CMakeLists.txt`:

- label `oracle-free`: self tests of hashline.py, compare.py, gates.py,
  accuracycoin.py and testroms.py on synthetic data, and the format and chain check
  of the reference file `tests/nes-oracle/reference/accuracycoin-mesence.hash`
  (MesenCE, fill 00, no input, 300 frames).
- label `oracle`, one test per oracle and question, all serialised
  (`RESOURCE_LOCK nes_oracle`): `nes_oracle_mesence_accuracycoin` (G2 over
  300 frames, then equal to the reference in every field, cyc and dot);
  `nes_oracle_mame_accuracycoin` (G2 over 300 frames);
  `nes_oracle_mesence_accuracycoin_all` and
  `nes_oracle_mame_accuracycoin_all` (the full AccuracyCoin runs against
  the recorded results of section 4); `nes_oracle_cross_accuracycoin`
  (MesenCE against MAME over 300 frames, the fields of section 5 must be
  equal in every frame). A test skips (exit 2) only when its ROM or its
  oracle is missing. Oracles from the cache variables `NES_MESEN`,
  `NES_MAME`, the environment (`MESEN`, `MAME`) or PATH; AccuracyCoin from
  `NES_ACCURACYCOIN_DIR` (default `tests/data/accuracycoin`, local, not
  distributed).

```bash
ctest --test-dir $BUILD -L '^oracle-free$'
```

```bash
ctest --test-dir $BUILD -L '^oracle$'
```

- label `mamr` (no emulator, the local AccuracyCoin data; skip without
  it): `nes_mamr_g1_accuracycoin` (G1 with stage S against stage E),
  `nes_mamr_g3_accuracycoin`, `nes_mamr_dumpcheck_accuracycoin`,
  `nes_mamr_reference_accuracycoin` (against the MesenCE reference file,
  pal and img from frame 3), `nes_mamr_accuracycoin_all` (147/147); and
  under label `oracle` `nes_mamr_ab_mesence_accuracycoin` (MAMR against
  MesenCE from the same palette, 300 frames, every field).
- Super Mario Bros. 3 (local ROM, `NES_SMB3_ROM`, default
  `roms/nes/Super Mario Bros. 3 (USA) (Rev 1).nes`; skip without it):
  `nes_smb3_title_local` (label `local`: G1 over 1600 frames without
  input, stage S against stage E, and four recorded fields that MesenCE
  shares: vram of frame 196, the title nametable; img of frame 451, the
  full title picture; vram of frame 1584, the menu; img of frame 1600)
  and `nes_mamr_ab_mesence_smb3` (label `oracle`: 1600 frames, every
  field except ram, ppu, cyc and dot, which S1 and S2 explain).

```bash
ctest --test-dir $BUILD -L '^mamr$'
```

`tests/nes/CMakeLists.txt`: `nes_board`, `nes_ppu`, `nes_apu`, `nes_dma`,
`nes_hashline` (oracle-free unit tests) and `nes_nestest_local` (label
`local`, the local nestest data).

## 8. PAL (phase P)

The oracles in PAL mode (docs/nes-architecture.md section 11):

- **MesenCE**: `run_mesen.sh` with `MESEN_REGION=Pal` passes
  `--nes.region=Pal` (setting name of `NesConfig.Region`, read from the
  same source as section 2; MesenCE's `Auto` is never used, its choice
  depends on the file name). The Lua state then reports `region` Pal,
  which the writer puts in the header; `dot` is `ppu.masterClock / 5`;
  the apu field maps MesenCE's noise and DMC periods back through the
  RP2A07 tables. Power-on as on NTSC: PPU at (0, 0), eight CPU cycles
  before the first fetch, PPU offset 1 master clock (`align=1`); a CPU
  cycle is 16 master clocks with the read access 7 and the write access
  9 into it (docs/nes-hardware-spec.md section 7.2). G2: two runs of
  Super Mario Bros. 3 Europe byte-identical.
- **MAME**: `run_mame.sh` with `MAME_DRIVER=nespal` (the PAL console of
  `src/mame/nintendo/nes.cpp`); the writer names the region from
  `machine.system.name` and swaps the device's pen bits 6 and 7 into
  colour order (format section 5). Its other limits are those of section
  3 (sampling at the end of the frame, input applied at its next frame
  update, fill 00ff). Trap found on 2026-10-27: MAME's SDL front end
  opens the desktop's display even with `-video none`, and with a busy
  desktop it hung at start-up with 0 % CPU (also the NTSC ctests
  `nes_oracle_mame_accuracycoin*` timed out); `run_mame.sh` now unsets
  `DISPLAY` and `WAYLAND_DISPLAY` and selects SDL's dummy video and audio
  drivers.
- **gates.py**: `NES_REGION=pal` runs every oracle on a PAL console,
  `NES_REGION=auto` lets MAMR take the region from its database while
  MesenCE and MAME run PAL; `testroms.py` runs the PAL entries of its
  catalogue (phase "P") that way.

### 8.1 PAL test ROMs

blargg's pal_apu_tests (tested by the author on a PAL NES, TEST-ROM-HW)
and nmi_sync's demo_pal (docs/nes-hardware-spec.md section 7), the
headers forced to PAL (they say NTSC), 2026-10-27:

| ROM | MAMR | MesenCE 2.2.1 Pal | MAME 0.285 nespal |
|---|---|---|---|
| pal_apu_tests/01.len_ctr | pass | pass | fail #4 |
| pal_apu_tests/02.len_table | pass | pass | fail #1G |
| pal_apu_tests/03.irq_flag | pass | pass | pass |
| pal_apu_tests/04.clock_jitter | pass | pass | fail #2 |
| pal_apu_tests/05.len_timing_mode0 | pass | pass | fail #3 |
| pal_apu_tests/06.len_timing_mode1 | pass | pass | fail #3 |
| pal_apu_tests/07.irq_flag_timing | pass | pass | fail #2 |
| pal_apu_tests/08.irq_timing | pass | pass | fail #3 |
| pal_apu_tests/10.len_halt_timing | pass | pass | fail #3 |
| pal_apu_tests/11.len_reload_timing | pass | pass | fail #2 |
| nmi_sync/demo_pal (frame 120, the drawn line's left edge against the reference lines at x = 82 and 84) | 83 (flashing pixels 83-84, solid from 85): inside | 81 (flashing 81-82, solid from 83): one pixel left of the documented farthest-left position | no line drawn (the synchronisation fails) |

The two oracles disagree on every pal_apu_test but 03; the ROMs decide
(TEST-ROM-HW): MAME's PAL frame counter is not the RP2A07's. As a check
that the tests discriminate, MAMR with the NTSC tables (`--region ntsc`)
fails 05 (#2) and 08 (#3) and passes 01. demo_pal's readme gives a range,
not a position (the phase is random on a console): MAMR's line lies in
it; MesenCE's flashing edge lies one pixel outside it, although its
CPU/PPU alignment is MAMR's (equal cyc and dot in every frame of the game
below), so the difference is where a $2001 write takes effect on PAL
(finding P2 below).

### 8.2 Super Mario Bros. 3 (Europe), 3000 frames

`NES_REGION=auto gates.py ab` (MAMR from MesenCE's frame-1 palette) and
`gates.py cross`, without input and with tools/oracle/nes/inputs/
smb3-1-1.txt (the USA script, bound to the strobes; on the European ROM it
reaches the map, enters World 1-1 at frame 700 and loses a life by frame
1400). First differing frame and number of differing frames per field;
MAMR with the rules of this phase (the SYNC rule of
docs/nes-hardware-spec.md section 7.4 included):

| field | MAMR / MesenCE, no input | MAMR / MesenCE, input | MAMR / MAME, no input | MAMR / MAME, input | MesenCE / MAME, no input |
|---|---|---|---|---|---|
| inp | equal | equal | equal | 228, 2150 | equal |
| cyc | 12, 1030 (S1) | 12, 1227 (S1) | 1, 3000 (sampling point) | 1, 3000 | 1, 3000 |
| dot | 12, 1030 (S1) | 12, 1227 (S1) | not written by MAME | - | - |
| cpu | equal | 228, 13 (S1) | 3, 2 (sampling point) | 3, 2542 | 3, 2 |
| ram | 12, 1235 (S1) | 12, 1215 (S1) | 1, 3000 (fill 00ff) | 1, 3000 | 1, 3000 |
| vram | equal | equal | 9, 1 | 9, 131 | 9, 1 |
| oam | equal | 635, 429 (S3) | 9, 2 | 9, 2652 | 9, 2 |
| pal | equal | equal | 1, 9 (power-on palette) | 1, 43 | 1, 9 |
| prgram | equal | equal | equal | 227, 2564 | equal |
| ppu | 9, 2418 (P1 in frames 9-10, S2 from 11) | 9, 187 | not written by MAME | - | - |
| prgmap | equal | 233, 1 (S1) | 1, 3 | 1, 80 | 1, 3 |
| chrmap | equal | equal | 9, 2 | 9, 10 | 9, 2 |
| mirq | equal | equal | 9, 2992 (sampling point) | 9, 2992 | 9, 2992 |
| img | 12, 1930 (S2) | 12, 88 (S2) | 1, 3000 (sampling point) | 1, 2312 | 1, 3000 |
| apu | equal | 266, 94 (A1) | not written by MAME | - | - |

Without input MAMR's relation to MAME is exactly MesenCE's (the same
first frames and counts in every field): what separates MAME is its
sampling point at the end of the frame, its RAM fill and power-on
palette (section 3), as on NTSC, where `gates.py cross` on the USA ROM
gives the same picture (mirq 2989, img 3000 frames). With input MAME
takes the buttons at its frame update, so from frame 228 it plays
another game (inp); that is the trap of section 3, not a PAL finding.

With MesenCE's NMI rule switched on locally in MAMR (the diagnostic of
section 6, not part of the regular build) the run without input is equal in every field
but ppu (P1, S2) and img (S2) in all 3000 frames, cyc and dot included;
with input the only further differences are apu (A1, from frame 266),
oam (S3, from frame 635) and one more S1 point (frame 841).

Findings, each with its judge:

| | field, first frame | cause | judge |
|---|---|---|---|
| S1 | cyc, dot, ram from frame 12 | as on NTSC (section 6): the NMI during a taken `BPL` of a wait loop (the title's at $A81C, the game's at $96F6) | SIM, as section 6 |
| S2 | ppu (read buffer) from 11, img from 12 | as on NTSC, the $2007 read of the status bar IRQ on an ALE dot; on PAL the read lands in the background prefetch of line 193 (dots 321-336) instead of the sprite fetches, so the first 8 pixels of line 194 differ (the tile fetched through the latch) in 1930 frames of the title | [ACC "ALE + Read"], TEST-ROM-HW, as section 6 |
| S3 | oam from 635 (input) | as on NTSC: OAM row corruption after the level's mid-line rendering stop (MesenCE has it switched off) | [ACC "OAM Corruption"] for the 2C02; on the 2C07 UNKNOWN (docs/nes-ppu-spec.md section 18.3) |
| A1 | apu from 266 (input) | as on NTSC: the DMC output level one delta step apart (MesenCE clocks the output unit one APU cycle earlier) | CHOICE / UNKNOWN, docs/nes-audio-spec.md section 12 |
| P1 | ppu (OAMADDR) in frames 9 and 10 | new on PAL: the title switches rendering off at line 9, dot 73 (+3), inside sprite evaluation (on NTSC the same write falls outside it); MAMR leaves OAMADDR at $18 (six sprites stepped by 4), MesenCE at $19 | none: no test ROM reads OAMADDR after a rendering stop inside evaluation; UNKNOWN, docs/nes-ppu-spec.md section 18.3 |
| P2 | (picture of demo_pal) | MesenCE's line starts two dots earlier than MAMR's with equal CPU/PPU timing; INFERENCE: the $2001 write takes effect two dots earlier in MesenCE's PAL mode | [BLARGG-NMISYNC] demo_pal's documented range: MAMR inside, MesenCE one pixel outside (section 8.1) |
| P3 | inp from 551, game course (with input, before the SYNC rule) | DMC DMA on the RP2A07: with the NTSC rule (halt on any read) the MMC3 IRQ of frame 239 meets the wait loop at another instruction than in MesenCE, which halts only at an opcode fetch; with the SYNC rule (docs/nes-hardware-spec.md section 7.4) inp is equal in all 3000 frames | UNKNOWN on the console; CHOICE for MesenCE's behaviour by the rule of docs/nes-architecture.md section 10; test proposal in the hardware spec |

The MMC3 IRQ split (the status bar) agrees with MesenCE in every frame
(mirq equal, and the picture apart from S2), so the PAL M2 phase of
docs/nes-hardware-spec.md section 7.2 and the A12 filter of three M2
falls hold on PAL as well.
