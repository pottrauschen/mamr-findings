# SNES ROM survey: basis for version 1 of the cartridge contract

Every SNES ROM in the local set (roms/snes, local, not distributed) was
put through the cartridge loader, the interpreter path against aresref
in stage S and stage E, the recompiler frontend and the tracer, on
2026-10-24. The purpose is the contract between a game artefact (block
code plus block table plus manifest, loaded by the per-system runtime
through the versioned C ABI the S7 work is defining in
docs/machine-interface.md) and the runtime: the contract must carry
every game here, not only Zelda. Section 6 turns the findings into
requirements and proposals; section 3 keeps every difference against
aresref as a finding with its cause, not smoothed over.

Setup: MAMR as of 2026-10-24; GCC 15.2 RelWithDebInfo
(`cmake --preset linux`), aresref c76aaff with patches 0001-0007
(docs/snes-oracles.md section 2) from a local aresref build,
IPL dump tests/data/spc700.rom (local, not distributed), fill 00, hash line format 4, 3000
frames per run, 16-core x86-64 Linux. Short ids in the tables are the
file names of the input scripts in tests/snes-oracle/scripts/.

Contra III - The Alien Wars (USA), id contra3, went through the same
procedure on 2026-10-25 (MAMR as of that day, with Contra III added
to the cartridge database, same aresref and IPL); its rows are in every
table below, its header is finding F12.

## 1. The ROM set

23 files, 22 distinct images (the two Star Fox files are byte-identical).
SHA-1 over the image without a copier header (none has one); No-Intro
names where the DAT has them.

| id | Title | SHA-1 | ROM | Map, chipset ($FFD5/$FFD6) | SRAM | Country | Cartridge database |
|---|---|---|---|---|---|---|---|
| alien3 | Alien 3 (USA) (Rev 1) | 832e1b86c13fdd0c24480e4c72eec5d94edc4f82 | 8 Mbit | $30 LoROM fast, $00 | none | $01 | not listed |
| ct | Chrono Trigger (USA) | de5822f4f2f7a55acb8926d4c0eaa63d5d989312 | 32 Mbit | $31 HiROM fast, $02 | 8 KiB | $01 | SHVC-1J3M-20 |
| dkc | Donkey Kong Country (USA) (Rev 2) | cd606e77ab2034438e06891cd2d067dad69b4d1a | 32 Mbit | $31 HiROM fast, $02 | 2 KiB | $01 | SHVC-1J1M / BJ1M family |
| ff3 | Final Fantasy III (USA) | 4f37e4274ac3b2ea1bedb08aa149d8fc5bb676e7 | 24 Mbit | $31 HiROM fast, $02 | 8 KiB | $01 | SHVC-BJ3M-10 / -20 |
| iot | Illusion of Time (Germany) (Rev 1) | d3ff5adf858d7e56a67577ac6042c26565c240df | 16 Mbit | $31 HiROM fast, $02 | 8 KiB | $09 | SHVC-1J3M-20, PAL |
| zelda-de | Zelda - A Link to the Past (Germany) | 2e62494967fb0afdf5da1635607f9641df7c6559 | 8 Mbit | $20 LoROM, $02 | 8 KiB | $09 | SHVC-1A3B-13 / 1A3M-10, PAL |
| zelda-us | Zelda - A Link to the Past (USA) | 6d4f10a8b10e10dbe624cb23cf03b88bb8252973 | 8 Mbit | $20 LoROM, $02 | 8 KiB | $01 | SHVC-1A3B-12 / -13 / 1A3M-30 |
| soe | Secret of Evermore (USA) | 79e7738630fff5699217ef58ecc421bc8fcbcd89 | 24 Mbit | $31 HiROM fast, $02 | 8 KiB | $01 | SHVC-1J3M-20 |
| som | Secret of Mana (Europe) | d9aaf3119784887475da9548000738e1da84bee6 | 16 Mbit | $21 HiROM, $02 | 8 KiB | $02 | SHVC-1J3M-11, PAL |
| testprog | SNES Test Program (USA) | 89eea825c1d434a62cba9867001eec6aac75c469 | 8 Mbit | header all zero | none | $00 | not listed |
| sbm2 | Super Bomberman 2 (USA) | 14e4d0b3d00fd04f996eea86daa485a35e501853 | 8 Mbit | $31 HiROM fast, $00 | none | $01 | not listed |
| sbm5 | Super Bomberman 5 Gold Cartridge (Japan) | b10b1c1c6c5a5a6512fec91032a17498149ce40a | 16 Mbit | $31 HiROM fast, $02 | 8 KiB | $00 | not listed |
| smas | Super Mario All-Stars + Super Mario World (USA) | d245e41a2b590f7d63666b0772cbddfb26f254a2 | 20 Mbit | $20 LoROM, $02 | 8 KiB | $01 | not listed |
| smw | Super Mario World (USA) | 6b47bb75d16514b6a476aa0c73a683a2a4c18765 | 4 Mbit | $20 LoROM, $02 | 2 KiB | $01 | SHVC-1A1B-04 |
| metroid | Super Metroid (Japan, USA) | da957f0d63d14cb441d215462904c4fa8519c613 | 24 Mbit | $30 LoROM fast, $02 | 8 KiB | $00 | SHVC-3A3M-01 / BA3M-01 / -10 |
| starfox | Star Fox (USA) (Rev 2), two files | cf08148cd8f26d51f8c67c956179dfc594e7a4f1 | 8 Mbit | $20 LoROM, $13 | none | $01 | SuperFX (MC1) |
| contra3 | Contra III - The Alien Wars (USA) | 265886e3f665adf2507e7b2f08b6b2ed9d0018b2 | 8 Mbit | $53 ('S' of the title, F12), $00 | none | $01 | SHVC-1A0N-01 / -02 / -10 / -20 |
| smk | Super Mario Kart (USA) | 47e103d8398cf5b7cbb42b95df3a3c270691163b | 4 Mbit | $31 HiROM fast, $05 | 2 KiB | $01 | DSP-1 / DSP-1B |
| smrpg | Super Mario RPG (USA) | a4f7539054c359fe3f360b0e6b72e394439fe9df | 32 Mbit | $23 LoROM SA-1, $35 | 32 KiB | $01 | SA-1 |
| sfa2 | Street Fighter Alpha 2 (USA) | f4ede150b5281f7f5d7e3188c6d9163c2bc66475 | 32 Mbit | $32 LoROM S-DD1 fast, $43 | none | $01 | not listed (S-DD1) |
| sgb-w | Super Game Boy (World) (Rev 2) | 973e10840db683cf3faf61bd443090786b3a9f04 | 2 Mbit | $20 LoROM, $E3 | none | $00 | not listed |
| sgb-j | Super Game Boy (Japan) (V1.0) | 6ed55c4368333b57f6a2f8bbd70ccd87ed48058e | 2 Mbit | $20 LoROM, $E3 | none | $00 | not listed |

Header checksums match the computed sum for every image (Contra III:
stored 0c3c, complement f3c3, computed 0c3c) except the
Test Program (header all zero, computed e8bc) and Street Fighter Alpha
2 (stored db99, computed db9a; the S-DD1 image is refused anyway).

## 2. Recognition

`snes_headless ROM --frames 1` and the loader test. Known ROMs get the
board of the database; unknown ones the header heuristic with a
warning; chip images are refused before any map is built. Every
refusal is one message on stderr and exit code 1, no crash; the
refused images were also run through aresref for 2 frames, which
accepts them all (ares has the chips), so the ROM files themselves are
sound.

| id | Loader result | Board (type, rules) | Warning / message |
|---|---|---|---|
| alien3 | accepted, heuristic | LoROM (A0N): ROM 00-7D/80-FF:8000-FFFF, mirrors 40-7D/C0-FF:0000-7FFF; fast | "not in the cartridge database; board LoROM chosen from the header" |
| ct, dkc, ff3, soe | accepted, database | HiROM+SRAM: ROM 00-3F/80-BF:8000-FFFF and 40-7D/C0-FF; SRAM 20-3F/A0-BF:6000-7FFF; fast | none |
| iot, som | accepted, database, PAL | HiROM+SRAM as above (som: slow ROM) | none |
| zelda-de, zelda-us, smw | accepted, database | LoROM+SRAM (74LS139): ROM 00-1F/80-9F:8000-FFFF; SRAM 70-7D/F0-FF:0000-FFFF | none |
| metroid | accepted, database | LoROM+SRAM (MAD-1): ROM 00-7D/80-FF:8000-FFFF; SRAM 70-7D/F0-FF:0000-7FFF; fast; 3 MiB folded 2+1 | none |
| smas | accepted, heuristic | LoROM+SRAM (MAD-1), 2.5 MiB folded 2 MiB + 2 x 512 KiB | "not in the cartridge database; board LoROM+SRAM (MAD-1) chosen from the header" |
| sbm2 | accepted, heuristic | HiROM, no SRAM | warning as above (HiROM) |
| sbm5 | accepted, heuristic | HiROM+SRAM | warning as above (HiROM+SRAM) |
| testprog | accepted, heuristic | LoROM (A0N), slow; header empty, checksum_ok false | warning as above (LoROM); recognised by the reset vector $8000 alone |
| starfox | refused by name | - | "Star Fox (USA Rev 2) needs the SuperFX (MC1) chip, which this runtime does not provide" |
| contra3 | accepted, database (since F12; before: refused by header, "map mode $53 (LoROM with SA-1) is not supported") | LoROM (A0N), as alien3; speed bit not taken from the damaged byte | none |
| smk | refused by name | - | "Super Mario Kart (USA) needs the DSP-1 / DSP-1B chip, which this runtime does not provide" |
| smrpg | refused by name | - | "Super Mario RPG - Legend of the Seven Stars (USA) needs the SA-1 chip, which this runtime does not provide" |
| sfa2 | refused by header | - | "map mode $32 (LoROM with S-DD1) is not supported" |
| sgb-w, sgb-j | refused by header | - | "chipset $E3: enhancement chip Super Game Boy / Satellaview is not supported" |

Vectors (native NMI / IRQ, emulation RESET; full list in section 4):
all in ROM except Secret of Mana, whose native NMI ($0100) and IRQ
($0104) vectors point into the low-RAM mirror (the handlers are copied
to WRAM at start). Donkey Kong Country's unused COP/BRK/ABORT vectors
point to open bus, the Test Program's BRK vector to $4000; neither is
ever taken.

Tests: `snes_cart` (synthetic images) now also refuses S-DD1 and the
Super Game Boy and accepts an all-zero header; `snes_rom` (label-free,
skips without roms/snes) checks all 21 images: 15 accepted with board,
sizes, vectors, region and warning state, 6 refused with the reason in
the message. Both pass under GCC and Clang. Since F12, `snes_rom` also
checks Contra III (22 images, 16 accepted; vectors in ROM: reset $8000,
NMI $819B, IRQ, COP and BRK $8BE2) and `snes_cart` refuses a synthetic
unknown ROM with map mode $53 as implausible, not as SA-1.

## 3. Oracle comparison

Command per ROM (stage S and stage E, every field, mclk and pc):

```bash
ARESREF=<aresref binary> python3 tests/snes-system/compare_oracle.py $BUILD/tools/snes_headless/snes_headless "roms/snes/<file>.sfc" --frames 3000 --ipl <IPL dump> [--input tests/snes-oracle/scripts/<id>.txt] --work <dir>
```

Wall time per ROM for aresref plus both stages: 66 to 95 s (aresref
alone about 26 s for 3000 NTSC frames of Zelda, stage S 23 s, stage E
30 s; the PAL games and the 4 MiB fast-ROM games are the slow end).
The run without input was made twice: before and after the port-2 fix
of finding F1; the table shows the state after it. Stage S and stage E
give the same result on every ROM except Illusion of Time (F9, since
fixed, see there).

The input scripts (tests/snes-oracle/scripts/, grammar
docs/snes-oracle-input-script.md) wait through the title, press START
and the menu buttons the game needs and then move for the rest of the
run; checked on picture dumps every 150 or 300 frames: at frame 3000
Alien 3, Chrono Trigger, Donkey Kong Country, Illusion of Time, both
Zeldas, Secret of Evermore, Secret of Mana, Super Bomberman 2 and 5,
Super Mario World and All-Stars (Super Mario Bros. title) run game
code; Final Fantasy III is in its opening sequence (black between
scenes), Super Metroid still in its intro text (START does not skip it
within 3000 frames), the Test Program in its tests (section 5).
Contra III (script contra3: START at read 501 skips the logo to the
title, START at read 703 takes "1 PLAYER") is in stage 1 from about
frame 1400, runs right and shoots, loses its lives and shows the
continue screen from about frame 2700. Wall time for Contra III: 63 s
for aresref plus both stages.

| id | No input: first divergence (stage S = E) | No input: fields over 3000 frames | With input: first divergence | With input: fields | Finding |
|---|---|---|---|---|---|
| zelda-de | equal | - | equal | - | - |
| zelda-us | equal | - | equal | - | - |
| smw | equal (before F1: frame 242 cpu,wram,mclk) | - | equal | - | F1 fixed |
| alien3 | frame 2494 img | img 3 (2494, 2498, 2506) | equal | - | F2 |
| metroid | equal (before F3 was fixed: frame 197 wram, 1 frame) | - | equal (before: frame 197 wram, 1 frame) | - | F3 fixed |
| sbm2 | frame 90 anc | anc 1 | frame 90 anc | anc 2, wram 1 | F4 |
| ct | equal (before F3 was fixed: frame 108 cpu,smp,apuio,wram,aram; cpu 18, smp 18, apuio 18, wram 16, aram 18, mclk 17 in frames 108-125) | - | equal (before: the same) | - | F3 fixed |
| sbm5 | equal (before F3 was fixed: frame 133 cpu,smp,apuio,wram,aram,mclk and everything from 133 on; before F1: frame 30) | - | equal (before: the same) | - | F3 fixed |
| contra3 | equal (before F3 was fixed: frame 37 cpu,smp,apuio,aram,mclk; aram 2230, dsp 999, wram 932, smp 724, mclk 325, cpu 224, apuio 75, ppu 9; vram, oam, cgram, img, sram equal) | - | equal (before: frame 37; aram 1611, wram 1402, dsp 864, smp 654, mclk 553, cpu 342, apuio 72, ppu 9) | - | F3 fixed |
| dkc | frame 91 mclk | mclk 248, cpu 115, wram 115, dsp 41, smp 22, aram 19 (before F1: wram 2898, mclk 2424) | frame 91 mclk | mclk 1237, cpu 504, wram 440, dsp 254 | F1 fixed, F5 |
| ff3 | frame 21 smp | smp 2965 | frame 21 smp | smp 2965 | F6 |
| soe | frame 362 smp | everything from 377 on | frame 362 smp | everything from 377 on | F6 |
| smas | equal | - | frame 1817 cpu,wram,mclk | mclk 42, cpu 28, wram 478 (stack bytes), smp 2 | F7 |
| som | equal | - | frame 1062 img | img 243 | F8 |
| iot | S: frame 434 aram; E: frame 25 vram,oam,cgram | S: aram 2567, dsp 15; E: plus vram 2453, oam 2976, cgram 478, img 2760 | S: 434 aram; E: 25 | S: aram 1919, dsp 40 | F9 (stage E, fixed), F6-like open (aram) |
| testprog | frame 71 img | img 2638 | frame 71 img | img 805, wram 291 (841-1131) | F10, F11 |

### Findings

Each with the evidence, the cause as far as it is established, and the
proposal. "Transient" means the state converges again by itself.

**F1 (fixed): controller port 2 read as a connected pad.** Donkey Kong
Country reads $4017 bit 0 once per frame after the auto-read (code at
$80:C16A: `SEP #$20; LDA $4017; REP #$20; BIT #$0001; BNE`) to tell a
second pad from an empty port. MAMR modelled port 2 as a pad with
nothing pressed, which returns 1 after its 16th bit; ares (controller
port without a device) and MesenCE return 0. DKC therefore took a
118-clock branch every frame (anchor bisection: $80:C16A equal,
$80:C1B2 32833852 against 32833970) and wrote $14F9 differently, which
moved its idle loop and everything after it. The same rule explained
Super Mario World's divergence at frame 242 and the early divergences of
Super Bomberman 2 and 5. Fix: `Joypad::connected`, port 2 empty by
default as in the oracle runs (runtime/snes/snes_timing.h), unit test
in tests/snes/test_snes_timing.cpp, hardware-spec 2.6. After the fix
Super Mario World, Super Bomberman 2 and Super Mario All-Stars are
equal to aresref without input, DKC's difference shrinks to F5, both
Zeldas stay equal (3000 frames, S and E).

**F2: Mode 7 matrix written mid-scanline (Alien 3, 3 single-pixel
frames).** The title's rotating logo writes M7A-M7D ($211B-$211E, 16
writes at $81:C474-$81:C4B8) during scanline 3; a write at dot x ends in
one pixel at that dot: frame 2494 x=152 (MAMR 10c3, ares 4def), 2498
x=148 (0c62 / 0000), 2506 x=99 (0000 / 10c3), all in row 2 of the
picture (= scanline 3); every other pixel and every other frame equal.
Cause: which dot first uses a Mode 7 parameter written during the line
differs by one dot between MAMR's segment renderer and ares' per-dot
PPU (the same family as the undisbeliever INIDISP one-pixel findings,
docs/snes-oracles.md section 11, fixed there for INIDISP/SETINI). Not
smoothed over: the hardware latency of a mid-line M7x write is not
measured. Proposal: a ppu-spec entry (section 8, mid-line writes) and a
synthetic test ROM that writes M7A at controlled H positions, compared
with aresref and, when possible, a console; until then a known
deviation.

**F3 (oracle side, fixed 2026-10-25 by aresref patch 0009): APU port
writes become visible early at the sampling point in aresref (Chrono
Trigger, Super Bomberman 5, Super Metroid; Contra III since 2026-10-25).** Four independent games
diverge right after a sampling point while the CPU polls an APU port:

- Chrono Trigger frame 108: the CPU writes port 1 at 38188022 in MAMR,
  38187980 in ares, exactly one poll-loop turn (CMP $2140 24 clocks +
  BNE 18) later; the SPC's echo write (val 76) sits at the boundary
  38187696 (ares logs it as frame 107, MAMR as 108); from there the
  upload handshake runs 126 clocks per byte slower in MAMR until the
  upload ends at frame 126, then everything is equal again (18 frames).
- Super Bomberman 5 frame 133: identical pattern (echo ce at the
  boundary, CPU write 47132814 against 47132716, 98 clocks = one loop
  turn), and since the game keeps talking to the SPC afterwards the
  states never meet again within the run.
- Super Metroid frame 197: the pushed P at $1FF2 differs by the Z flag
  (65 against 67). The interrupted instruction is `CMP $002140` at
  $80:8092 executed at 69993278, the sampling clock of frame 196: MAMR's
  CPU read the port before the SPC's echo of $62, ares' after it.
- Contra III frame 37 (and once at frame 28, transient): the SPC's
  echo of the upload counter on port 0 ($1C at frame 37, $73 at 28)
  sits in ares' P lines before the sampling point, in MAMR's after it;
  the CPU's next port-1 write follows one poll-loop turn later in MAMR
  (12815018 against 12814966, 52 clocks; at frame 28 9598732 against
  9598680, and the byte after it is equal again). From frame 37 on the
  upload handshake runs 208 to 300 clocks per byte later in MAMR. In
  the attract run cpu, mclk and wram meet again (cpu last at frame 920,
  wram at 1073); the ARAM stays different from frame 853 to the end,
  the DSP and SMP registers in about a third of the frames, so the
  sound driver keeps a phase shift against the CPU (hypothesis: the
  later end of the upload moves every later command to the SPC; not
  traced). With input the CPU keeps a phase difference of up to about
  120 clocks at the sampling point; the WRAM bytes that differ after
  frame 1100 are stack bytes at $1DD0-$1DFF (pushed interrupt state)
  and one byte at $1F20 (one higher in ares). vram, oam, cgram and the
  picture are equal in all 3000 frames of both runs. MesenCE 2.2.1
  (3000 frames, no input) cannot arbitrate: it differs from aresref and
  from MAMR in wram from frame 1 on.

In all four the SPC write lands within the SMP instruction that
straddles the sampling clock. aresref's patch 0007 runs the SMP to its
first instruction boundary at or after that clock with the CPU clock
moved far ahead, so the write executed there is already in the port
latch when the CPU, back at its own clock, reads the port: ares' CPU
sees a write from its future. MAMR runs a copy of the SMP for the hash
line (`smp_at_sample`) and leaves the real one behind the CPU. The P
line times support this (the SPC write times differ by one SMP cycle in
the count convention only, every CPU write time is equal up to the
slip).

Fix (oracle pipeline, no change to MAMR): patch 0009 saves the SMP and
the DSP (ares' serializer, thread stacks included) before the run of
0007, and restores them after the F line, so the line shows the SMP at
its first boundary at or after the sampling clock as if the CPU stood
still, exactly MAMR's copy, and the emulated time line is that of ares
without the hook (docs/snes-oracles.md section 2, with the alternatives
that were weighed). The run of 0007 had broken the time line in both
directions: SMP port writes in the rest of the straddling instruction
were visible to CPU reads before their time (the cases above), and SMP
port reads there had already happened without a CPU write made in
between (on the test ROM traced once: one more turn of the IPL's poll
loop, the CPU's next writes 156 to 300 clocks late; which direction each
game case took was not traced). An own test ROM shows both (tests/snes-timing/rom/apuport.s, an endless
IPL upload; ctest `snes_timing_apuport*`, `snes_timing_aresref_apuport`):
the 0008 build differs from frame 9 on, the 0009 build is equal to MAMR
in every field and in all 569732 CPU port write times. Re-run with
0009, 3000 frames, stage S and E: Chrono Trigger, Super Bomberman 5 and
Super Metroid are equal in every field, mclk and pc included, without
input and with their scripts (table above). Contra III (USA) (the
fourth case above) is equal in every field over 3000 frames without
input and with its script: the lasting ARAM difference came from F3
alone. Zelda DE and USA, the
gilyon and the stall reference files are written byte for byte as
before.

**F4: auto-joypad read started by a late $4200 write (Super Bomberman
2).** Frame 90 (the game's first enable of the auto-read): anc 0 in
MAMR, 1 in ares, nothing else; with input a second such frame and one
transient WRAM byte. This is the enable-late rule (hardware-spec 2.5,
undisbeliever enable-autojoy-late-test-2, docs/snes-oracles.md section
11): ares starts a read for an enable inside the latch window where
MAMR does not. No state consequence here; stays with that open
question.

**F5: 6 clocks at the HDMA setup inside a WAI/BRA idle loop (Donkey Kong
Country).** DKC idles in `WAI; BRA` at $80:C0D4 with the IRQ line held
and I set (WAI returns at once, 18 clocks, 36 per turn; 79.9 million
clocks of the 3000 frames are spent there). In frame 91 the WAI anchors
agree up to 32877678, then MAMR needs 84 clocks for the turn and ares
78: the V=0 HDMA setup (DKC runs HDMA, 286310 bytes over the run) costs
MAMR 48 and ares 42 there, a 6-clock phase shift of the loop that lasts
until the NMI resyncs both. Afterwards the sampling boundary falls on
another instruction of the loop (mclk deltas 0 in 2752 frames, else
-72 to +72 in steps of 6), which drags cpu, wram and the SMP view with
it. The stall test ROM covers the HDMA setup against memory cycles but
not against a loop of internal cycles. Proposal: a stall ROM section
"WAI;BRA under IRQ with HDMA on" (tests/snes-timing) to pin which cycle
start the DMA edge is aligned to when the CPU runs internal cycles only;
hardware-spec 3.4 note.

**F6: timer 2 and CONTROL writes (Final Fantasy III, Secret of Evermore;
open decision now with a game on it).** The only differing byte of
FF3's smp field is the stage-3 counter of timer 2 ($FF), from frame 21
on in 2965 frames, mostly 3 behind; registers, targets, T0, T1, ARAM
and DSP are equal. Evermore's sound driver reads $FF: at frame 362 the
counter differs (0f against 00), from 368 the ARAM and from 377 the CPU.
ares clears timer 2's stages on every CONTROL write that does not raise
its enable bit (inverted against timers 0 and 1, `sfc/smp/io.cpp`),
MAMR clears all three on the rising edge only (docs/snes-audio-spec.md
section 9, "decision open"). With ares' rule built into a diagnostic
binary both games are equal to aresref over 1000 frames in every field,
so this is the whole cause. Not changed: fullsnes, blargg's snes_spc
and LakeSnes side with MAMR's rule, the arbiter is blargg's spc_timer
test on a console. Recorded in docs/snes-oracles.md section 10.
Proposal: run blargg's SPC timer tests (externally, no licence for the
repository); if ares is wrong, an aresref patch 0008 for the timer-2
rule so that Evermore can be compared further. Illusion of Time's
stage-S aram difference (frame 434) was not traced; it has the same
shape (ARAM only, then DSP) and the same driver family is possible.

**F7: a stray V-IRQ after the IRQ was given up (Super Mario All-Stars,
with input).** The All-Stars menu takes a per-frame IRQ up to frame
1792; the Super Mario Bros. title screen then runs without one. At the
window of frame 1817/1818 ares takes an IRQ (vector $83A9, entry 62
clocks after the window) and the NMI 1766 clocks later; MAMR takes the
NMI at the window and never an IRQ again (anchors on both vectors). 42
frames of cpu/mclk, the pushed stack bytes linger 478 frames, state
re-converges. Candidates: the V-IRQ time for a $4200 enable written
between MAMR's H=10 and ares' H=14 (the known HTIME=0 deviation) or a
TIMEUP flag re-armed by a $4200 write; the timer registers of that
frame were not traced. Open; small.

**F8: Mode 5 picture (Secret of Mana, with input).** The intro's Mana
Fortress scene runs BGMODE=5 with TM=TS=$13 (BG1, BG2, OBJ on both
screens, no SETINI bits). From frame 1062 the picture differs in 243
frames: at 1062 MAMR's canonical picture is 512 wide and ares' 256 (the
hi-res rule found unequal half-pixel pairs only in MAMR), at 1300 both
are 512 wide and 147039 of 229376 bytes differ; in a sample of 8192
half-pixel pairs 1440 are equal, 59 swapped, 979 agree in the even half
only and 1017 in the odd half only. Mode 5 is not covered by any test
ROM in use (gilyon, undisbeliever, the stall ROM, Zelda). Cause open
(the main/sub half-pixel order, BG2 in mode 5, OBJ or the window
masks in hi-res). Proposal: a ppu-spec case for modes 5/6 with a
synthetic ROM (two backgrounds, known tiles, a sprite) compared against
aresref, then the renderer fix.

**F9: stage E loses DMA writes into OAM and CGRAM (Illusion of Time,
PAL).** Stage S is equal to aresref in vram, oam and cgram at frame 25;
stage E differs in 102 VRAM bytes, 510 of 544 OAM bytes and 218 CGRAM
bytes while cpu, wram and the ppu register shadow are equal and both
stages ran the same 10 GP-DMAs with 173856 bytes. In stage E the OAM
holds its fill word only at address 0 and zeros behind it, CGRAM one
word and zeros: the first write of each transfer lands, the rest is
lost. Stage E on the PAL Zelda and on all NTSC games has no such
difference, so the suspect is the per-cycle board of stage E meeting
this game's DMA shape (several channels in one $420B write during the
PAL frame's blank). Not traced further; stage S is the game build, but
stage E is the exactness reference, so this is a bug to find:
proposal: dump the DMA parameters of frame 25 with the exact system's
statistics and reproduce with a synthetic ROM.

Fixed on 2026-10-24 (the PPU field shape of a
lagging PPU, found with Motive's HblankEmuTest, docs/snes-oracles.md
section 12). Stage E's PPU, synchronized only at CPU bus cycles, fell
back to the NTSC field shape while its field counter lagged the time
skeleton's, so in a PAL game it wrapped at 262 instead of 312 lines.
That the lost OAM and CGRAM writes are the PAL blank's lines taken for
active display is the likely reading, not traced separately; the
evidence is the result: with only snes_ppu.cpp reverted to its state
before that fix the frame 25 difference comes back (checked on
2026-10-24), and with the fix Illusion of Time is equal to aresref in
every field over 60 frames in both stages (re-checked 2026-10-25 on
main with tests/snes-system/compare_oracle.py, `--frames 60 --stages
s,e`).

**F10 (oracle side): aresref's picture is black in most 239-line
frames (SNES Test Program).** The Test Program sets overscan
(SETINI=$04, 239 rows) and keeps its menu on screen; INIDISP=$0F, TM=$03,
no mid-frame writes (`--ppu-stats`), the ppu field equal in every frame.
aresref's img is all zero in 2638 of 3000 frames and equal to MAMR's
menu picture in the other 362 (frames 72 and 300 black, 150 shown).
With overscan the window opens at V=240; the hook then reads ares'
frame buffer when ares has already started the next frame in some
frames and not in others. MAMR's picture matches what the program shows
on a console. Proposal for the oracle: take the picture from the
completed frame (ares' frame-done event) when overscan is latched;
until then img is not comparable on 239-line games.

**F11: $0048 bit 6 during the electronics test (SNES Test Program,
with input).** Frames 841 to 1131, the running electronics test: one
WRAM byte, $0048, is 51 in MAMR and 11 in ares; equal again afterwards
and the test reports a pass in MAMR (ares' verdict is hidden by F10).
Which sub-test sets bit 6 is not known without a disassembly of the
program; open, listed for the TEST-ROM-HW candidate in section 5.

**F12: the internal title overwrites the map mode byte (Contra III).**
The header at ROM offset $7FC0 (bank 00 $FFC0-$FFDF): $7FC0-$7FD5 hold
the title in ASCII, $7FD6-$7FDF the bytes 00 0A 00 01 A4 00 C3 F3 3C 0C.

The title "CONTRA3 THE ALIEN WARS" has 22 characters, one more than the
21-byte field; the 22nd, 'S' ($53), sits at $FFD5, the map mode byte.
Every byte after it is sound: chipset $00 (ROM only), ROM size $0A (1
MiB, the size of the image), SRAM $00, country $01 (USA), developer
$A4 (Konami), version $00, complement f3c3 plus checksum 0c3c = ffff,
and the computed sum is 0c3c. Class: own measurement on the dump; the
SHA-1 is the No-Intro entry "Contra III - The Alien Wars (USA)" (DAT
of the libretro mirror, read 2026-10-25; CRC32 84DA7CFE), so the dump
is good and the header is the one the cartridge carries. A valid map
mode byte reads 001S MMMM; $53 is none. The loader masked the low
nibble (3) and refused the ROM as "LoROM with SA-1", which was the
wrong reason.

How other loaders treat this (behaviour read from their sources, ares
as pinned for aresref and MesenCE 2.2.1; no code taken over):

- ares (mia) takes the map mode byte only when it is one of the defined
  values ($20/$30 LoROM, $21/$31 HiROM, $22/$32 S-DD1, $23/$33 SA-1,
  $25/$35 ExHiROM, $2A/$3A SPC7110); any other value falls back to the
  layout whose header scored best, with a source comment that many
  games store an extra title character there, and one title with a '!'
  in that byte is named explicitly. The chip comes from $FFD6. ares
  loads Contra III as LoROM (aresref ran it, section 3).
- MesenCE chooses the layout by a score (checksum pair, cartridge type
  and size bytes, the opcode under the reset vector); the map mode byte
  adds one point when it fits the layout, the chip comes from $FFD6.
  It sets its FastROM flag from bit 4 of $FFD5, which 'S' has; the flag
  is only logged, the ROM speed follows MEMSEL there as in ares and
  MAMR. Data Crystal lists Contra III as FastROM, which matches reading
  that bit and is no evidence for the speed.

Decision: the board chosen by SHA-1 is the intended path for such a
header. Contra III is in the cartridge database (LoROM A0N without SRAM,
PCB SHVC-1A0N-01 / -02 / -10 / -20 from the snescentral cartridge page,
DOC+photo); for a known ROM the map mode byte is not consulted, and the
speed bit is taken only from a valid map mode byte (`fast_rom` is
informational; a static scan of the image finds no absolute STA, STZ,
STX or STY to $420D, which does not rule out a direct-page write). The
header fallback stays strict: an unknown ROM with this byte is still
refused, now with "map mode $53 is implausible (high bits not 001,
header damaged or title overflow?) and the ROM is not in the cartridge
database" instead of the SA-1 reason. Zelda DE stays equal to its
aresref file over 3000 frames in stage S (every field, mclk).

Proposal, not implemented: a mild fallback for unknown ROMs, LoROM when
the map mode byte is implausible, the checksum and its complement are
valid and equal to the computed sum, the chipset byte is $00-$02, the
header lies at $7FC0 and the reset vector is at least $8000 (ares
accepts on less). In this set the case occurs once, it would be right
there, and the overflow damaged only $FFD5. A valid checksum keeps
random bytes out; the remaining risk is a chip cartridge whose title
also reaches $FFD6, not seen. Recommendation: stay strict until a
second unknown title needs it, and add such games to the database.

## 4. Static analysis and tracer

Static: the recompiler frontend over the cartridge's static ROM map,
vectors plus the seeds of a tracer run:

```bash
$BUILD/tools/snes_headless/snes_headless ROM --frames 3000 --ipl <IPL dump> --input tests/snes-oracle/scripts/<id>.txt --out /dev/null --miss-log <id>.miss --stats
$BUILD/tools/snes_recomp/snes_recomp ROM --stats --seeds <id>.miss
```

With no blocks linked every interpreted run starts with a miss, and the
miss log holds the first instruction of every interpreted run: the set
of (PB:PC, M, X) the dispatcher would need, which is what the block
discovery takes as seeds. Runs of about 20 to 34 s per game in the
interpreter.

Tracer, 3000 frames with the input script (second seed count: without
input):

| id | Instructions | Interrupts | Emulation-mode instr. | GP-DMAs (bytes) | HDMA bytes | WAI clocks | anc | Seeds with / without input |
|---|---|---|---|---|---|---|---|---|
| alien3 | 34667248 | 5982 | 4 | 24714 (4592672) | 0 | 0 | 2990 | 3329 / 1011 |
| ct | 39072807 | 2946 | 3 | 7409 (4095423) | 64101 | 0 | 2888 | 3046 / 2827 |
| dkc | 49071888 | 2477 | 2 | 4712 (2555606) | 286310 | 79939080 | 2914 | 2546 / 600 |
| ff3 | 42852163 | 4187 | 3 | 36934 (4723680) | 7109020 | 0 | 2533 | 2178 / 1143 |
| iot | 50492085 | 2414 | 3 | 5619 (3907872) | 22357 | 0 | 2997 | 1637 / 1061 |
| zelda-de | 47682784 | 4365 | 12 | 10996 (6181476) | 431448 | 0 | 2933 | 2282 / 1074 |
| zelda-us | 38923652 | 4379 | 12 | 10418 (5776220) | 418950 | 0 | 2919 | 2208 / 1078 |
| soe | 42119294 | 2821 | 4 | 7855 (1811446) | 0 | 0 | 2819 | 2809 / 3275 |
| som | 48768319 | 3879 | 2 | 7774 (2586825) | 68661 | 0 | 2984 | 4563 / 2205 |
| testprog | 43875968 | 2382 | 2 | 3235 (3767685) | 0 | 0 | 2541 | 685 / 59 |
| sbm2 | 39227689 | 2911 | 9 | 8655 (4789984) | 354816 | 0 | 2912 | 2250 / 611 |
| sbm5 | 47613744 | 5137 | 3 | 5836 (1928384) | 6518 | 0 | 2971 | 3043 / 1877 |
| smas | 38244952 | 4560 | 3 | 4804 (2798566) | 276513 | 0 | 2822 | 1885 / 338 |
| smw | 41153040 | 3575 | 12 | 39776 (4051268) | 965888 | 0 | 2714 | 2863 / 2952 |
| metroid | 45021880 | 2980 | 3 | 4203 (4689056) | 11638 | 0 | 2994 | 1327 / 2148 |
| contra3 | 32621375 | 2707 | 2 | 23332 (3782387) | 9070 | 0 | 2707 | 1711 / 876 |

Emulation mode is the reset sequence only (2 to 12 instructions per
run); no game runs code in E=1 afterwards. DKC is the only game that
waits in WAI (with the IRQ line held, F5). Interrupts are one NMI per
frame plus the H/V IRQ where used (Alien 3, FF3 and Bomberman 5 take
about two per frame).

Static analysis with the input-run seeds; "vectors only" is the cfg
from the four native vectors alone:

| id | Blocks (vectors only) | Instructions | No-code targets (region) | Unknown width | Indirect sites | Banks with code | Seeds: exact / other width / inside a block / dynamic only / not in ROM |
|---|---|---|---|---|---|---|---|
| alien3 | 6952 (54) | 20131 | 5 (ROM 1, WRAM mirror 3, open bus 1) | 34 | 0 | 5 | 36 / 10 / 0 / 3281 / 2 (WRAM mirror) |
| ct | 11653 (2) | 51836 | 220 (WRAM 205, WRAM mirror 3, open bus 12) | 17 | 80 | 14 | 0 / 4 / 0 / 2830 / 212 (WRAM 208) |
| dkc | 4839 (3) | 20855 | 2 (open bus) | 1 | 44 | 13 | 0 / 4 / 0 / 2542 / 0 |
| ff3 | 6831 (2) | 32506 | 279 (WRAM 277, WRAM mirror 2) | 41 | 28 | 8 | 0 / 4 / 0 / 1893 / 281 (WRAM 277) |
| iot | 5043 (6) | 18326 | 24 (ROM 1, WRAM mirror 16, open bus 7) | 11 | 16 | 10 | 0 / 6 / 0 / 1622 / 9 (WRAM mirror) |
| zelda-de | 5156 (66) | 23306 | 15 (ROM 1, WRAM mirror 8, open bus 6) | 20 | 25 | 19 | 53 / 7 / 0 / 2222 / 0 |
| zelda-us | 4969 (66) | 22423 | 2 (ROM 1, open bus 1) | 20 | 22 | 16 | 53 / 7 / 0 / 2148 / 0 |
| soe | 5141 (46) | 23439 | 0 | 4 | 43 | 8 | 33 / 4 / 0 / 2772 / 0 |
| som | 14025 (0) | 59257 | 1760 (WRAM 1712, WRAM mirror 46, open bus 2) | 33 | 31 | 16 | 0 / 0 / 0 / 2727 / 1836 (WRAM 1786, mirror 50) |
| testprog | 1695 (0) | 8204 | 2 (CPU I/O 1, WRAM mirror 1) | 23 | 4 | 2 | 0 / 0 / 0 / 685 / 0 |
| sbm2 | 6464 (187) | 29129 | 0 | 0 | 3 | 5 | 81 / 3 / 0 / 2166 / 0 |
| sbm5 | 4953 (156) | 16428 | 1 (SRAM) | 1 | 22 | 8 | 130 / 17 / 14 / 2882 / 0 |
| smas | 4155 (5) | 17176 | 0 | 1 | 26 | 5 | 2 / 8 / 0 / 1875 / 0 |
| smw | 8086 (207) | 31184 | 16 (B bus 1, ROM 1, WRAM 2, WRAM mirror 7, open bus 5) | 43 | 24 | 9 | 120 / 10 / 0 / 2732 / 1 (WRAM) |
| metroid | 2329 (452) | 9161 | 3 (WRAM mirror 2, open bus 1) | 5 | 40 | 11 | 216 / 40 / 29 / 1042 / 0 |
| contra3 | 2616 (244) | 10083 | 0 | 3 | 40 | 5 | 364 / 6 / 77 / 1264 / 0 (against the 1559-block cfg, see below) |

Instruction classes inside the static blocks (counts of instructions):

| id | REP/SEP | PLP | XCE | TCS/TXS | JMP (a)/(a,X)/[a] | JSR (a,X) | RTS/RTL | RTI | BRK/COP | WAI/STP | MVN/MVP | PEA/PER/PEI |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| alien3 | 197 | 116 | 0 | 3 | 0 | 0 | 1128 | 6 | 2 | 0 | 5 | 0 |
| ct | 2549 | 138 | 5 | 21 | 19 | 70 | 1326 | 14 | 190 | 4 | 159 | 58 |
| dkc | 560 | 8 | 0 | 10 | 37 | 9 | 709 | 1 | 0 | 11 | 1 | 20 |
| ff3 | 1493 | 132 | 1 | 1 | 13 | 15 | 617 | 6 | 0 | 0 | 6 | 10 |
| iot | 719 | 195 | 2 | 13 | 13 | 5 | 676 | 58 | 408 | 5 | 23 | 31 |
| zelda-de | 898 | 20 | 4 | 4 | 21 | 4 | 643 | 6 | 31 | 3 | 5 | 10 |
| zelda-us | 873 | 20 | 1 | 5 | 18 | 4 | 613 | 6 | 22 | 3 | 6 | 0 |
| soe | 631 | 9 | 0 | 4 | 29 | 14 | 549 | 1 | 3 | 2 | 3 | 93 |
| som | 4046 | 152 | 0 | 47 | 19 | 15 | 1946 | 23 | 58 | 0 | 21 | 5 |
| testprog | 467 | 73 | 3 | 3 | 4 | 0 | 108 | 5 | 18 | 0 | 6 | 1 |
| sbm2 | 2309 | 2 | 0 | 1 | 3 | 0 | 1354 | 3 | 1 | 0 | 2 | 0 |
| sbm5 | 617 | 5 | 0 | 3 | 19 | 3 | 720 | 6 | 8 | 0 | 6 | 0 |
| smas | 461 | 1 | 0 | 3 | 18 | 16 | 423 | 3 | 1 | 0 | 2 | 0 |
| smw | 761 | 53 | 3 | 15 | 5 | 23 | 793 | 10 | 149 | 0 | 8 | 9 |
| metroid | 367 | 160 | 4 | 6 | 20 | 21 | 424 | 7 | 144 | 1 | 7 | 34 |
| contra3 | 303 | 17 | 0 | 2 | 38 | 2 | 339 | 2 | 0 | 0 | 21 | 0 |

What the numbers say:

- **Discovery from the vectors alone finds almost nothing** (0 to 452
  blocks of 2000 to 14000): every game dispatches through jump tables
  (`JMP (a,X)`, `JSR (a,X)`, pushed addresses with RTS) right after the
  reset path, which runs in emulation mode and the interpreter. The
  miss log is the discovery, as the architecture says; a tracer run of
  3000 frames with input finds 2 to 3 times the seeds of the attract
  mode (except where the attract mode plays the game: Super Mario
  World, Super Metroid, Evermore). Blocks found only at run time are
  the rule, not the exception, for every game. (These counts are of the
  discovery before the table patterns of docs/snes-zelda-authority.md,
  added the same day; on Zelda those patterns take the vectors from 66
  to 31371 blocks. The other games of the survey have not been measured
  with them.)
- **Code outside ROM.** Secret of Mana runs 1786 of 4563 seed blocks
  from WRAM ($7E) and 50 from the low-RAM mirror, its NMI and IRQ
  handlers included; Chrono Trigger 212 of 3046; Final Fantasy III 281
  of 2178; Illusion of Time 9, Alien 3 2 and Super Mario World 1 in the
  low mirror. The static cfg sees these as no-code targets (CT 205
  WRAM targets, SoM 1712). Super Bomberman 5 jumps once into SRAM. The
  Square games are the "code in WRAM" case of docs/snes-architecture.md
  section 3, and they are a quarter of the set.
- **Width changes inside blocks.** REP/SEP are frequent everywhere
  (hundreds to thousands); PLP (M/X unknown after) 1 to 195 per game,
  XCE 0 to 5 (all in reset or mode-switch helpers); the cfg reports 0 to
  43 unknown-width stops per game. The width variants of the same
  address (seeds "other width") are 3 to 40 per game: a block key with
  M and X is needed, as designed.
- **Stack switches** (TCS/TXS) 1 to 47 per game, Secret of Mana the
  most: the runtime's guest stack must be whatever S says, no host
  assumption.
- **Interrupt entries**: NMI every frame; IRQ in Alien 3, FF3, Illusion
  of Time (408 BRK/COP: its engine uses COP as a call), Zelda, All-Stars
  menu, Super Mario World (149 BRK/COP), Super Metroid (144 BRK/COP). A
  block can be interrupted at any instruction boundary; the interrupt
  entry and the return address belong to the runtime.
- **Block moves** (MVN/MVP) in every game, up to 159 in CT; **WAI** in
  DKC's idle loop (F5), CT, Zelda, Illusion of Time, Evermore and
  Metroid at least once.
- **Banks with code**: 2 (Test Program) to 19 (Zelda DE); HiROM games
  run from $C0-$FF and $80-$BF (bank $00 holds only the reset path),
  LoROM games from $00-$1F or $80-$9F.

Contra III was measured on 2026-10-25, after the table patterns of
docs/snes-zelda-authority.md were in: its rows above use
`--no-tables` so they compare with the other games (vectors alone 244
blocks, all in bank 00; the class counts are of that cfg with the
input seeds). With the patterns the vectors alone give 1559 blocks
(8028 instructions, banks 00, 02 and 03, 3 indirect sites), and the
seed classes in the table are against that cfg; with the patterns and
the input seeds 3676 blocks, 15432 instructions, banks 00-04 and 1D, 4
unknown-width stops; with both miss logs (1711 seeds with input, 876
without) 3927 blocks and 16405 instructions, 10 indexed-jump and 2
pointer-jump tables. No seed lies outside ROM: Contra III runs no code
from WRAM or SRAM. Its reset path is 2 instructions in emulation mode
(`CLC; XCE` at $00:8000), it never waits in WAI, and it takes about
one interrupt per frame (2707 with input, 2712 without; IRQ, COP and
BRK share the vector $8BE2).

Native run: the 3927 blocks from both miss logs (`snes_recomp --seeds
<with input> --seeds <without> --parts 4`, five files of 0.9 to 2.5
MB) compiled as snes_headless_native, then
`tests/snes-system/compare_native.py` over 3000 frames: without input
and with the contra3 script, every F line of the native run equals the
interpreter's, with 0 dispatch misses and 2 interpreted instructions
(the emulation-mode reset), interpreter share 0.0 %. Wall time 17.7 s
native against 19.3 s interpreted without input, 16.2 s against 17.7
s with input. The block set covers the runs it was built from; a run
along another route would still miss blocks.

## 5. SNES Test Program

Nintendo's 1991 factory test cartridge (header all zero; the loader
takes it on the reset vector alone, section 2). Without input it shows
its test menu with six entries (electronics, character, controller,
sound, colour and accessories tests; SELECT chooses, START begins) and
stays there, so the attract comparison tests only the menu
rendering: equal to aresref in every field except img (F10, the
oracle's overscan picture), 3000 frames.

With the input script (START at read 700, SELECT twice and START for
the next tests) it runs the electronics test (frames 841 to about 1130,
first a running message, then a pass message with the hint to leave by
SELECT), then the character test (test pictures with moving sprites and
BG mode pictures), then the controller test. In this run every field but
img and one WRAM byte is equal to aresref over 3000 frames (F11: $0048
bit 6 during the electronics test, verdict pass on MAMR; the program's
criteria are not documented, a disassembly would be needed to say what
bit 6 means). The program uses no HDMA, 3235 GP-DMAs, no WAI, 685
blocks from 2 banks, 23 unknown-width stops, 73 PLP.

As TEST-ROM-HW material it is weaker than it looks: it passes on the
hardware by construction, but its pass criteria are hidden in its code
and its picture cannot be compared with aresref until F10 is fixed.
Keep it as a smoke test (the electronics test must report a pass on
MAMR, checked by the picture or by the text buffer), not as a reference
for timing; register it in docs/snes-test-evidence.md as "class CHOICE,
verdict by eye".

## 6. Requirements for the cartridge contract

Property, which game needs it, and what follows for the artefact ABI
(the loadable game library: block code, block table, manifest) and the
runtime. "All" means every accepted game in this set.

| Property | Needed by | Artefact ABI | Runtime |
|---|---|---|---|
| Board by ROM identity (LoROM A0N, LoROM+SRAM 74LS139 / MAD-1 / heuristic, HiROM, fast or slow, SRAM 2 to 8 KiB, odd ROM sizes folded) | all; HiROM: ct, dkc, ff3, iot, soe, som, sbm2, sbm5; 20 Mbit folding: smas; 24 Mbit: ff3, soe, metroid; damaged header byte: contra3 (F12) | manifest carries the SHA-1 of the image, the board type and the sizes it was translated for; the runtime refuses a different image (snes_headless already does this by SHA-1) | one Map built from BoardDesc; the heuristic path stays for unknown ROMs with the warning in the log |
| Region per artefact (PAL: iot, som, zelda-de) | PAL games | manifest field region (from the database or the header); not a runtime option, since block timing and the SMP ratio depend on it | Timing built NTSC or PAL from the manifest; the oracle comparisons need `--region` only for diagnosis |
| Blocks keyed by (mapping, PB:PC, M, X) with resume points | all (3 to 40 width variants per game, REP/SEP inside blocks) | block table rows: start, context bits, function, resume list (W65BlockInfo as is) | dispatcher checks live M, X, E and the mapping; never enters a block for another width |
| Discovery from the miss log, not from static analysis alone | all (vectors give 0 to 452 of thousands of blocks) | the artefact records the seed set it was built from (tracer run, input script, frames) so a rebuild is reproducible; a second artefact version adds seeds | the runtime keeps a miss log in the game build too (`--miss-log` already), so a player's runs can feed the next build |
| Code in WRAM and in the low-RAM mirror | som (1786 blocks, NMI and IRQ handlers), ct (212), ff3 (281), iot, alien3, smw (a few) | blocks over RAM addresses carry the bytes they were translated from (or a hash) and a page-generation check at entry; the table marks the mapping id "RAM"; version 1 may ship these games interpreter-only for their RAM code, but the table format must already allow RAM blocks | 256-byte page generation counters bumped by every write into a page with translated code (architecture section 3); a RAM block whose bytes changed falls back to the interpreter per block |
| Code in SRAM | sbm5 (one target) | same as RAM blocks, mapping id "SRAM" | SRAM is battery RAM: the save file is loaded before any block check |
| Interrupt entries at any boundary | all (NMI per frame, IRQ in 7 games, COP/BRK as calls in iot, smw, metroid) | block functions return at the poll point when a line is up (as now); the vectors are read from ROM by the runtime, not baked into the artefact, since som's vectors point into WRAM | the runtime does the entry sequence, the pushes and the vector fetch; the dispatcher continues at the handler's block |
| Dispatcher continuation point in the save state | all; dkc and the WAI games in particular | the save state holds guest PC, PB, M, X, E, the pending line, the WAI/STP state and the block-local resume state (MVN/MVP byte position); never a host return address | a state restored mid-block resumes through the dispatcher at a resume point, so blocks must only stop at instruction boundaries (as they do) |
| Stack wherever S points | all (TCS/TXS 1 to 47 per game) | nothing in the ABI assumes a stack page | guest stack in guest memory only |
| APU: SPC700 program from the game, IPL from the user's dump or the own boot program, measured clock | all | manifest: none (the SPC code is data the game uploads); the IPL choice is a runtime setting | the port model with the copy at the sampling point (F3 shows why); the timer-2 rule as decided (F6) |
| DMA, HDMA, refresh at the cycle grid | all (HDMA in 10 games, up to 7.1 million bytes in FF3) | none | the board, as now; F5 is a runtime bug to fix (F9 is fixed), not an ABI matter |
| PPU modes beyond Zelda's | som (mode 5), alien3 (mode 7 mid-line writes), testprog (overscan 239 lines), hi-res pictures 512 wide | none | renderer work (F2, F8); the frame buffer must be 512 x 239 capable from the start |
| Controller ports | dkc (reads $4017 beyond bit 16), testprog (controller test) | none | port 2 empty by default, a second pad as a front-end option (F1) |
| Refusal of chips and unsupported mappings | starfox (SuperFX), smk (DSP-1), smrpg (SA-1), sfa2 (S-DD1), sgb (Super Game Boy) | the builder refuses before translating; the message names the chip | the loader's messages as they are (section 2); a DSP-1 firmware path (Mario Kart) would be a later ABI extension: firmware blob by hash in the manifest, never in the artefact |
| Large ROMs | 32 Mbit: ct, dkc (4 MiB); up to 4 MiB LoROM/HiROM supported, ExHiROM refused | the artefact does not contain the ROM; the runtime loads the image and checks the hash | none beyond the map |

Proposals for docs/machine-interface.md (suggestions only, the file
belongs to the S7 work):

1. Manifest fields: `rom_sha1`, `board` (type, rom_size, sram_size,
   fast), `region`, `block_count`, `abi_version`, `built_from` (tracer
   frames, input script name, seed count), `ram_code` flag.
2. Block table row: start (24-bit), context bits, function pointer,
   resume list, mapping id (ROM / WRAM / SRAM), and for RAM rows the
   byte hash and length of the source bytes.
3. Save state: a versioned struct with the CPU registers plus
   `int_pending`, `wai`, `stp`, the MVN/MVP position, the board and PPU
   state, SMP/DSP state and the dispatcher's "next key"; the state
   never contains host pointers.
4. The runtime exposes `miss_log()` and `stats()` through the ABI so
   the front end can write the seeds of a play run.
5. Version 1 scope: the 12 games equal or transient against aresref
   (both Zeldas, Super Mario World, All-Stars, Secret of Mana without
   the intro picture, Alien 3, Super Metroid, Super Bomberman 2, Chrono
   Trigger, Super Bomberman 5 and Contra III (equal since F3 was fixed
   on the oracle, 2026-10-25), Illusion of Time in stage S); Evermore and FF3 wait for F6, DKC for
   F5; the chip titles are refused.

## 7. Open points

- F3 is fixed on the oracle (patch 0009, 2026-10-25); CT, Bomberman 5,
  Metroid and Contra III are equal; Contra III showed that its lasting
  ARAM difference after the upload was F3 alone. MesenCE also catches its real SMP up to an
  instruction boundary when it finishes the frame (snes-oracle-format.md
  section 3); whether that leaks into its time line the same way was not
  examined (the handshake ROM would show it).
- F6: timer-2 CONTROL rule, hardware truth unknown; blargg's spc_timer
  on a console, or an aresref patch to compare Evermore further.
- F5 (DKC, 6 clocks at the HDMA setup in a WAI/BRA loop), F8 (mode 5),
  F2 (mid-line Mode 7 writes), F7 (stray V-IRQ in All-Stars): runtime
  work, each with a test ROM proposal above. F9 (stage E DMA into
  OAM/CGRAM on Illusion of Time) is fixed (2026-10-24).
- F10: the oracle's overscan picture; until fixed the Test Program's
  img is not comparable.
- Illusion of Time's stage-S aram difference at frame 434 was not
  traced (probably F6).
- F12: whether the header fallback should become mild for an
  implausible map mode byte with a valid checksum (proposal in F12);
  until then a game with a damaged map mode byte needs a database entry.
- Super Metroid's intro cannot be skipped within 3000 frames; a longer
  run or a WAIT_RAM8 on its game state byte would reach play.
- The input scripts hold no WRAM addresses on purpose; a script that
  waits on a game-state byte would be shorter and more robust.
- Super Mario Kart (DSP-1) is the only chip title with a plausible
  path (firmware by hash); SuperFX, SA-1, S-DD1 and the Super Game Boy
  stay refused.
