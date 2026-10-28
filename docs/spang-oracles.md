# Super Pang oracle kit and lockstep

The oracle for Super Pang is MAME 0.285 (the Ubuntu package on the
development machine) running the parent set `spang`. This document covers
the kit in `tools/oracle/spang/` (phase P1), the proof for the Kabuki
preprocessing (P2), the lockstep of MAMR's machine against MAME (P3), the
picture (P4), the sound (P5), the recompiled blocks (P6), and every
deviation found on the way. The line format is
[spang-oracle-format.md](spang-oracle-format.md), the hardware facts are
[spang-hardware-spec.md](spang-hardware-spec.md).

## 1. Files

| file | purpose |
|---|---|
| `run_mame.sh OUT [FRAMES]` | MAME headless with a private work directory (fresh cfg and nvram per run), the ROM path prepared by `romset.py`, `spfh_mame.lua` as autoboot script |
| `spfh_mame.lua` | the hash line writer, input script, I/O log, dumps |
| `views_mame.lua` | MAME's decrypted Kabuki views (run_mame.sh with `FH_VIEWS=DIR`) |
| `romset.py` | links the set under MAME's file names (found by name or SHA-1 from games/spang/spang.toml) and writes the YM2413 instrument file |
| `hashline.py` | reference implementation of the format, input script parser, the placeholder |
| `compare.py` | `lines` (frame by frame, `--skip-field F:LIST` for one field), `dumps` (byte offsets), `pixels` (two picture dumps pixel by pixel, `--png` writes both pictures and a difference mask), `iolog` (first differing access) |
| `kabuki.py` | second implementation of the Kabuki cipher, views from the ROM files |
| `gates.py` | `determinism`, `lockstep` (`--img`, `--eeprom-set`), `audio`, `views` (section 5) |
| `audio.py` | `compare`: two recordings of a route, level curve per frame (section 9) |
| `entries.py` (not published) | `update`: miss logs of spang_headless into games/spang/spang-entries.txt, reduced (section 10) |
| `inputs/coin-start.txt` (not published) | coin, start, a stretch of play |

The kit needs Python 3.11 or later (tomllib), MAME 0.285 and the set in
`roms/spang` (or `SPANG_ROMS`). MAME finds loose files only under their
MAME names; the set circulates with older names, hence the links.

## 2. Running

```text
tools/oracle/spang/run_mame.sh attract.hash 3000
FH_INPUT=tools/oracle/spang/inputs/coin-start.txt tools/oracle/spang/run_mame.sh coin.hash 3000
spang_headless --frames 3000 --out mamr.hash [--input SCRIPT] [--iolog FILE] [--stats]
               [--no-img] [--eeprom FILE]
tools/oracle/spang/compare.py lines attract.hash mamr.hash
FH_IMG=1 FH_DUMP_DIR=m FH_DUMP_AT=613 tools/oracle/spang/run_mame.sh m.hash 613
spang_headless --frames 613 --out r.hash --dump-dir r --dump-at 613
tools/oracle/spang/compare.py pixels m/f000613.img.bin r/f000613.img.bin --png diff
```

Environment of run_mame.sh: `MAME`, `MAME_WORK`, `SPANG_ROMS`,
`SPANG_YM2413`, `SPANG_EEPROM` (a start EEPROM, written as MAME's nvram
file), `SPANG_WAV` (MAME records its sound there, `-wavwrite`), and the
`FH_*` options of spfh_mame.lua (`FH_IMG=1` for
the picture, `FH_IOLOG`, `FH_DUMP_DIR` with `FH_DUMP_AT`/`FH_DUMP_EVERY`).
MAME runs one after the other on this machine (memory), the ctests hold
the resource lock `spang_oracle`.

## 3. The YM2413 instrument ROM

MAME 0.285's YM2413 device requires the ROM `ym2413_instruments.bin`
(144 bytes, CRC 6f582d01, SHA-1 bb553771...) and refuses to start
without it (src/devices/sound/ymopl.cpp:218-224, "This is not the exact
format"). It holds the chip's built-in instrument patches: data from
inside a Yamaha chip, not licensed by MAME and not part of the MAME source
tree. It is treated like a game ROM: never in the repository, never
distributed. No copy exists on the development machine.

- **Placeholder (default).** `romset.py` writes the 144 bytes of
  `ym2413::s_default_instruments` from ymfm's `ymfm_opl.cpp` (vendored
  in the MAMR source tree as third_party/ymfm; BSD-3-Clause, Aaron Giles; according to
  its comment the "copyright-free OPLL(x) ROM patches" of 2015, tweaked
  values, not the chip's). CRC f30b33da; MAME warns "WRONG CHECKSUMS" and
  runs. The header says `ym2413=placeholder`.
- **Real dump.** `SPANG_YM2413=FILE` copies a user's own dump instead
  (`ym2413=rom`). MAMR's `Ym2413::set_instruments` takes the same 144
  bytes (not wired to a command line option yet).
- **Consequence.** With the placeholder both MAME and MAMR (which uses
  the same ymfm table by default) sound alike, but not like the board:
  the instruments are approximations. The program never reads the chip
  (no status, no IRQ), so the instruments cannot change the game state.
  The hash line therefore compares the **YM2413 write stream** (field
  `ym`: port and value of every write) and not audio samples; the same
  holds for the OKI (field `oki`). An audio comparison belongs to P5.

## 4. MAME findings and run times

**F1, uninitialised registers (MEASURED-EMU, frames 4-7).** Runs of the
same input differed in `vram` and `obj` in frames 4 to 7 only: the program
fills D000-DFFF before its first write to port 0x07, and MAME's
`m_video_bank` is never initialised (spang-hardware-spec.md section 5,
U5), so the fill went to tile RAM in some runs and to sprite RAM in
others (the dumps showed the two memories swapped). Two runs in a row
often agree, which is how a 2 x 3000-frame check of the feasibility study
passed. The kit writes 0 to ports 0x00 and 0x07 before the first
instruction; since then 8 of 8 runs were byte-identical.

**F2, the Z80 stops inside instructions (MEASURED-EMU, nearly every
frame).** At the frame notifier MAME's Z80 stood inside an instruction in
2931 of 3000 attract frames (`m_ref` other than 0xffff00, e.g. inside a
JR Z of the VBLANK wait loop, or between the read and the write of an
LDIR iteration). Sampled there, `z80` and `zclk` differed in almost every
frame and single bytes of RAM in four frames (the byte the LDIR iteration
was about to write). This is a property of the sampling point, not of
the emulation: interrupts are checked only at instruction boundaries, and
the cycle of every interrupt entry agrees (field `irq`). The writer
samples at the next instruction boundary (format section 3); `mid=` keeps
the observation.

**F3, the picture is one frame behind (MEASURED-EMU, MAME src/emu/screen.cpp).**
MAME's screen draws into one of two bitmaps at VBLANK start and swaps
them right after (`update_quads`, the screen is live under `-video none`);
the Lua `pixels` call in the frame notifier reads the current bitmap,
i.e. the frame drawn at the previous VBLANK, and resolves the pens through
the palette of now. First comparison over 300 attract frames: the picture
changed in 12 frames, and in 11 of them MAME's `img` equalled MAMR's
picture of the frame before; frame 1 was MAME's never-drawn bitmap. The
format defines `img` that way (spang-oracle-format.md section 3); a front
end shows the frame drawn at the VBLANK just begun.

**F4, the picture of a half-executed instruction (MEASURED-EMU, frames 5
and 613).** MAME draws at its VBLANK timer, where the Z80 may stand inside
an instruction (F2); a write whose bus cycle starts at or after the stop
cycle is missing from the picture. Frame 5 of every route: at VBLANK 4 an
LDIR at power-on fills tile RAM with 0xFF (HL = D1E5, DE = D1E6 after the
iteration that crossed the VBLANK start, `mid=1`); MAME's picture has the
old tile 242 (bytes D1E4/D1E5) where MAMR's had the filled one, 63 pixels
of one 8 x 8 tile. Frame 613 of the flip route: an LDIR in bank 5 at 0x83A8
copying into tile RAM (DE = D84D), one tile again. MAMR now draws the
hash picture without the writes of the straddling instruction whose bus
cycle starts at or after cycle floor(VBLANK start / 125e9): the offset of
each write in its instruction comes from the semantics building blocks
(`acc_t`, runtime/cpu_context.h, MAME z80.lst: an LDI/LDIR write at 11
T-states); a straddling video write of another form would be taken as done
and counted (`--stats`: "straddling video writes of unknown timing", 0 in
every run). With that, both frames are equal.

**Run times** (3000 frames = 52.2 s of machine time, this machine, one
run at a time):

| run | wall clock |
|---|---|
| MAME, hash lines, no picture | 6.5 s (3.4 s before the fetch tap of F2) |
| MAME with the picture (`FH_IMG=1`, the Lua pixel loop) | 55 s (64 s with a parallel ctest) |
| spang_headless, interpreter only, unoptimised build | 15 s, 24 s with the picture |
| romtool views + reference + MAME views (`gates.py views`) | 2.8 s |

## 5. Gates and ctests

- **G1 determinism**: `gates.py determinism 3000 [--input S]`, two MAME
  runs byte-identical. ctests `spang_oracle_determinism_attract`,
  `spang_oracle_determinism_coin`.
- **Views**: `gates.py views ROMTOOL [--no-mame]`, section 6. ctests
  `spang_kabuki_views_reference` (ROM set only) and
  `spang_kabuki_views_mame`.
- **Lockstep**: `gates.py lockstep 3000 --headless EXE [--input S]
  [--img] [--eeprom-set OFF=VAL] [--iolog]`, sections 7 and 8. ctests
  `spang_lockstep_attract`, `spang_lockstep_coin`, `spang_lockstep_flip`
  (all with the picture; flip: EEPROM byte 2 = 1, the coin/start route).
- **Sound**: `gates.py audio 3000 --headless EXE [--input S]`, section 9.
  ctests `spang_audio_attract`, `spang_audio_coin`.
- **Native**: `gates.py native 3000 --headless EXE [--input S]
  [--eeprom-set OFF=VAL]`, section 10, no MAME. ctests
  `spang_native_attract`, `spang_native_coin`, `spang_native_flip` (label
  `local`).
- **Kit selftests** (label `oracle-free`, no MAME and no ROM):
  `spang_oracle_{hashline,compare,romset,gates,audio,entries}_selftest`.
- **Unit tests** (no label): `spang_kabuki` (cipher on synthetic bytes),
  `spang_keyed_cpu` (decoder with two views, runner with block keys, RAM
  code, miss log, the discovery rules of section 10), `spang_chips`
  (EEPROM, OKI).

The oracle tests carry the label `oracle` and exit 2 (skipped) without
MAME or ROM set; the Super Pang targets exist only when `roms/spang` was
present at configure time.

## 6. Kabuki proof (P2)

`gates.py views` compares, byte by byte, the opcode and data views
(0x50000 bytes each, MAME's region layout) of

1. romtool (`--dump-views`, tools/romtool/kabuki.h),
2. the reference implementation `kabuki.py`, written the way kabuki.cpp
   writes the cipher (two bit-pair swap functions), and
3. MAME's address spaces: the opcode space 0000-7FFF and 8000-BFFF with
   each of the 16 banks selected through MAME's bank objects, the program
   space likewise, and the region `:maincpu` (which MAME overwrites with
   the data view).

Result: 0 differing bytes in all 35 comparisons. Reset vector: opcode
bytes F3 ED 56 C3, the operands from the data view: DI; IM 1; JP.

## 7. Lockstep results (P3)

spang_headless against MAME, 3000 frames each, every field but `img`,
zclk included:

| field | attract (no input) | coin/start route |
|---|---|---|
| zclk | equal | equal |
| z80 | equal | equal |
| wram | equal | equal |
| vram (tile + attribute RAM) | equal | equal |
| obj | equal | equal |
| pal | equal | equal |
| bank | equal | equal |
| irq (cycle and registers at all 5945 entries) | equal | equal |
| eep (contents and state machine) | equal | equal |
| ym (YM2413 writes) | equal | equal |
| oki (OKI commands) | equal | equal |

With `--iolog` the I/O logs of the coin/start route are identical line by
line: 287,932 port accesses with the same cycle and value.

**Findings of P3.** The only deviations on the way were F1 and F2 of
section 4, both on the oracle side; no deviation of MAMR against MAME
remains in the two routes. MAME's own simplifications (spang-hardware-spec.md
section 9) are copied, not corrected, so they do not show as deviations:

- **U1, VBLANK until line 28.** MAMR reproduces the 2500 us: the program
  polls port 0x05 bit 3 in the VBLANK wait loop at 0x0187 and in lines
  11-28, and the agreeing `irq`, `wram` and I/O log show it takes MAME's
  branches. Against the board this is unverified.
- **U2, 256 lines.** MAMR's IRQ and VBLANK times are MAME's (256 lines of
  68.03 us); the PCB note implies 264 lines of 65.94 us.

**Interpreter statistics** (`--stats`, attract, phase P3): 51.8 million
instructions interpreted, 0 blocks (phase P6 adds them), RAM code only at
FD10-FD1B (14,833 calls), 519 block starts in the fixed ROM and 847 in
banks, no unmapped port access, no fetch from the unmapped opcode space,
no I/O instruction other than IN A,(n) / OUT (n),A.

## 8. Picture lockstep (P4)

MAMR's renderer (games/spang/spang_video.h, after MAME's
`mitchell_state::screen_update`; hardware spec section 8) against MAME,
3000 frames each, every field of section 7 plus `img`:

| route | img | other fields |
|---|---|---|
| attract (no input) | equal | equal |
| coin/start (with a life lost after frame 2400) | equal | equal |
| coin/start, screen flip (EEPROM byte 2 = 1) | equal | equal |

The two findings on the way, F3 (one frame behind) and F4 (half-executed
instruction), are properties of MAME's sampling, reproduced in the hash
picture of `spang_headless`, not in what a front end shows. The flip
setting was found by toggling each of the EEPROM's first 16 bytes in
turn: byte 2 (high byte of word 1) set to 1 makes the program write
gfxctrl with bit 2 set (MEASURED-EMU, MAMR and MAME alike). Sprite
priority (later entries drawn over earlier ones, all above the tilemap)
and palette changes inside a frame cannot show in a comparison against
MAME: MAME draws the whole frame at VBLANK start and has no priority
logic beyond the drawing order (hardware spec section 9, U3).

## 9. Sound (P5)

MAMR's sound (games/spang/spang_machine.h `machine_audio`): the YM2413
through ymfm with ymfm's replacement instrument table, the OKI MSM6295
(runtime/okim6295.h), mixed as mitchell.cpp routes them into one speaker
(YM2413 gain 1.0, OKI 0.30, MAME's scaling of each), mono at the YM2413's
4 MHz / 72 = 55,556 Hz; the OKI's 7,576 Hz are held. `spang_headless
--wav FILE` writes it.

**What is compared.** The command streams are equal already (fields `ym`
and `oki`, section 7). The samples are not comparable: MAME's ROM file
`ym2413_instruments.bin` is the placeholder (section 3), so neither side
sounds like the board; MAME resamples everything to 48 kHz with its own
filter; MAMR holds the OKI samples where MAME resamples them; and MAME's
OKI stream runs at 7,575 Hz (an integer sample rate) where MAMR's runs at
1 MHz / 132 = 7,575.76 Hz. So the check is one of plausibility:
`audio.py compare` takes MAME's `-wavwrite` recording and MAMR's WAV of
the same route and compares the RMS level per frame window.

| route | level correlation (lag 0) | best lag | level MAME / MAMR | windows with sound on one side only |
|---|---|---|---|---|
| attract | 0.991 | 0 | 0.87 | 0 / 0 |
| coin/start | 0.993 | 0 | 0.95 | 0 / 0 |

**Finding S1, the rhythm section was missing (MAMR, fixed).** The first
coin/start comparison correlated at 0.90 only, with 70 frame windows
(806-875, right after the start) in which only MAME had sound: the
program switches the YM2413 to rhythm mode there (register 0x0E = 0x3C).
ymfm's OPLL has two outputs, the melody channels and the rhythm section,
and MAME routes both to the speaker (ALL_OUTPUTS); runtime/ym2413.cpp took
the first only. It sums both now.

**Open point S2, the level.** MAME's recording is 5 to 13 percent quieter
(YM2413-only windows of the attract mode 0.88, OKI-only windows 0.92).
A 22 kHz low-pass of MAMR's output changes its level by 1 percent only, so
MAME's resampling filter does not explain it. UNKNOWN: MAME's output stage
between the speaker and `-wavwrite` was not traced; the gains MAMR uses are
those of mitchell.cpp and the scale factors of ymfm_mame.h and
okim6295.cpp.

## 10. Recompiled blocks (P6)

romtool translates the program into C blocks under the block key (bank,
PC) (tools/romtool/romtool_banked.h, generated/spang/maincpu_blocks.cpp);
spang_headless runs them unless `--interpret`. The fixed ROM and each bank
are analysed separately, every bank as it appears in the window; M1 bytes
come from the opcode view, all other instruction bytes and inline tables
from the data view (recompiler/cfg.h, two views).

**Entries and rules.**

- Vectors: reset 0x0000, and 0x0038 because the program selects IM 1
  only (one IM instruction, at 0x0001). No NMI.
- RST 18h and CALL 781Ch are dispatchers (ROM): the routine pops its
  return address as the address of a table of code addresses right after
  the RST or CALL and jumps to entry A / 2 (RST 18h: ADD A,L ... JP (HL))
  or entry A (781Ch: ADD A,A, the word to DE, EX DE,HL, JP (HL)). Rule:
  no return site, the words after the call are its targets, read while
  they point below 0xC000 and stop at a byte that is code or a leader
  already (57 tables in the final analysis). A table read too far adds
  leaders nothing reaches; it does not hide code.
- OUT (02),A switches the bank under the window: a block ends after it,
  and the runner looks the next block up under the new key.
- Every other entry comes from the miss log (`spang_headless --miss-log`):
  the keys where the interpreter had to start in the oracle routes.
  `entries.py update` merges the logs, drops the keys that code reaches
  anyway (a direct target, a table entry, a return site) and puts back
  any miss key that is then no block key, until all are covered:
  games/spang/spang-entries.txt, 167 keys (48 in the fixed ROM, 119 in
  banks 0-5). The rest are computed jumps of the form LD HL,table; ADD A,L ...;
  JP (HL) with the table right after the jump (35 indirect sites stay
  open statically) and the entries of the bank code, which the fixed ROM
  reaches through the RAM routine at FD10 (83 window targets of the fixed
  ROM whose bank is not known statically).

**Rounds** (3000 frames each, attract, coin/start, coin/start flipped):

| | blocks | misses attract / coin / flip | interpreted instructions (attract) |
|---|---|---|---|
| static only (reset, IRQ, the rules) | 223 | 1307 / 1430 / 1430 (1755 keys) | 50,967,846 |
| with the entries file | 4388 (26,173 keys incl. resume points) | 0 / 0 / 0 | 103,832 (the RAM routine only) |

In both rounds the native hash files are byte-identical to the
interpreter's (every field including `zclk` and the picture); 3000
attract frames take 6.9 s native against 15.3 s interpreted
(unoptimised build, no picture).

**I/O timing per instruction.** A port access is timed at the start of
its instruction plus `acc_t`, which the semantics building blocks set for
every port access and for the block transfers (runtime/cpu_context.h,
runtime/z80_ops.h): the same in a block as in the interpreter, so the
I/O log and the EEPROM, IRQ-source and VBLANK reads stay cycle-equal
(the native hash files say so). spang_headless counts any port access
without it (`--stats`: "I/O with assumed timing", 0).

**Finding B1, the miss log missed jumps to the next address (MAMR,
fixed).** The first second round still had 10 misses: a JP (HL) at
0xB621 of bank 0 whose table starts at 0xB622, the byte after the jump,
and the like. The runner counted a fallback entry only where the PC was
not the address after the instruction, so the jump to entry 0 looked
like falling through. An unconditional transfer now always counts
(runtime/z80_cpu.cpp); with that, the first round logs these keys and
the second round has no miss.

## 11. Not covered yet

- Gameplay beyond the short route: later stages, continue, high score
  entry (EEPROM writes), the service mode, more RAM code; code they reach
  runs on the interpreter (correct, counted as misses) until its keys are
  added to the entries file.
- Audio samples beyond the plausibility check of section 9; the real
  YM2413 instrument ROM.
- The picture on the board: line timing of palette writes, sprite
  buffering (port 0x06), the gfxctrl bits MAME ignores (hardware spec
  section 9).
- Two writers on one machine only; determinism across MAME builds not
  checked.
