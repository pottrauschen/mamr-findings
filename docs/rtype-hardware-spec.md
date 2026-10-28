# Hardware Specification: R-Type (Irem M72, 1987)

Technical reference for the R-Type runtime (docs/concept.md, game 2).
Sections 1 to 8 cover the sound board (phase R2), sections 9 to 14 the main
CPU, the interrupt controller, the memory and I/O maps, the video hardware
and the inputs (phases R3 and R4).

**Sources:**

- **Schematic:** Nanao Corporation drawings of the M72 board set (1987),
  CPU board M72-A-C sheets 2/10 (I/O decode PALs, output port, inputs),
  3/10 (sound CPU, RAM, latch, interrupt logic) and 4/10 (YM2151, DAC,
  audio amplifier). Scan as distributed with the MiSTer core
  (`docs/Irem_M72_schematics.pdf`, MiSTer-devel/Arcade-IremM72_MiSTer
  commit 15c370e6e034a5e8baeea5a6fa651ff95b216c2b; PDF pages 16 to 18).
  References: `[SCH A-C 3/10 zone]`, IC numbers as printed. Not part of the
  repository.
- **Data sheets:** Yamaha YM2151 (catalog LSI-2121512, 1991) and YM3012
  (LSI-2130123, 1992), the scans on bitsavers.org. The YM3014 (the DAC on
  the board) is the single-channel variant with the same serial interface;
  its own data sheet was not consulted.
- **Nuked-OPM** (nukeykt, LGPL, `opm.c`): a YM2151 model derived from the
  die, read only for the channel order of the serial output. Class
  IMPLEMENTATION; the die itself was not inspected here.
- **MAME 0.289** (`mame0289` tag of `mamedev/mame`):
  `src/mame/irem/m72.cpp` (machine configuration, address maps, line
  timer), `src/mame/irem/m72_v.cpp` (`port02_w`, video), `src/devices/
  machine/rstbuf.cpp` and `rstbuf.h` (RST buffer), `src/devices/machine/
  gen_latch.cpp` (sound latch), `src/devices/machine/pic8259.cpp`
  (interrupt controller), `src/devices/cpu/nec/` (V30 core: necinstr.hxx,
  necmacro.h, nec.cpp), `src/emu/tilemap.cpp` and `drawgfx.cpp` (tilemap
  and sprite semantics), `src/devices/cpu/z80/z80.lst` with `z80make.py`
  (Z80 cycle steps) and the ymfm OPM core MAME builds (`3rdparty/ymfm`,
  vendored in the MAMR source tree as third_party/ymfm). References name the function or
  address map.
- **SingleStepTests/v20** (MIT): about 10,000 cases per opcode measured on
  a NEC D70108C-8 (V20), the hardware reference for the instruction
  semantics (tests/differential/sst_v20_runner). Bus timing is V20 (8-bit)
  and is not used.
- **MiSTer core** (same commit): `rtl/sound.sv`, read only for comparison.
- **Oracle kit:** MAME 0.289 runs of the set `rtype`
  (tests/data/rtype-oracle, local, not distributed).
- **Arcade oracle kit:** MAME 0.285 with the hash line writer
  `tools/oracle/arcade/rtype_mame.lua`, the judge of the frame lockstep
  ([arcade-oracles.md](arcade-oracles.md)).

Neither MAME nor MiSTer is ground truth: every statement carries its
provenance class.

**Reference ROM set:** `rtype` (World, MAME parent set). The sound program is
`rt_r-l1-b.3c` (CRC32 0df3573d, SHA-1
0144c846fd0bdb3e4d790f6cb7bb64829e931b76), see games/rtype/rtype.toml.

Provenance classes (as in docs/ikari-timing-reference.md):

| Class | Meaning |
|---|---|
| MEASURED | measured on a real board or chip |
| SCHEMATIC | schematic, datasheet or manufacturer manual |
| MAME | taken from MAME's driver or devices |
| IMPLEMENTATION | what an FPGA core or emulator does (not a hardware claim) |
| MEASURED-EMU | observed in a MAME run of the oracle kit; never hardware evidence |
| ROM | read from the program code itself |
| HACK/ASSUMPTION | interpretation or assumption |
| UNKNOWN | no usable source |

---

## 1. Scope of phase R2

The sound board runs on its own: the Z80 sound program, recompiled, with the
YM2151, the sound latch and the interrupt vector logic. The main CPU is
replaced by a recorded MAME run: its sound commands (`<tag>_latch.txt`) and
the time it releases the Z80 reset (`<tag>_events.txt`). The board model is
in games/rtype/rtype_sound.{h,cpp}, the oracle runner in
games/rtype/rtype_sound_headless.cpp.

## 2. Clocks and frame

| Item | Value | Class | Ref |
|---|---|---|---|
| Master clock | 32 MHz | MAME | m72.cpp `MASTER_CLOCK` |
| Main CPU | NEC V30, 32 MHz / 4 = 8 MHz | MAME | m72.cpp `m72_base` (V30) |
| Pixel clock, frame | 8 MHz, 512 x 284 per frame: 145408 main CPU clocks, 55.0176 Hz | MAME | m72.cpp `set_raw(MASTER_CLOCK/4, 512, ..., 284, ...)` |
| Sound clock | separate 3.579545 MHz oscillator module | SCHEMATIC | [SCH A-C 3/10 A10] |
| Sound CPU | D780C-1 (Z80A), CLK from the oscillator through an LS02 (IC52) | SCHEMATIC | [SCH A-C 3/10 B-C 10] |
| YM2151 | phiM (pin 24) on the same clock net as the Z80 | SCHEMATIC | [SCH A-C 4/10 B3], [SCH A-C 3/10 G10] |
| Output rate | clock / 64 = 55930.4 Hz (MAME stream: 55930 Hz) | MAME | ymfm_opm.h; ymfm_mame.h |

Time base of the board model: Z80 T-states since power-on. A main CPU clock
c corresponds to Z80 time floor(c x 3579545 / 8000000) (HACK/ASSUMPTION:
the sound oscillator and the 32 MHz master clock are unrelated crystals; the
model starts both at power-on without phase offset).

## 3. Sound RAM, code image and reset

| Item | Value | Class | Ref |
|---|---|---|---|
| Sound CPU memory | 64 KiB: two 256 Kbit SRAMs (IC70, IC71), selected by A15 through an LS139 (IC68); no ROM | SCHEMATIC | [SCH A-C 3/10 E-F 6-10] |
| Main CPU access | address and data reach the sound RAM through LS244 (IC31, IC42) and LS245 (IC18, IC41) buffers while BRQ is active | SCHEMATIC | [SCH A-C 3/10 B 5-10] |
| Reset | BRQ drives, through an LS02 and transistor TR3 (2SC1815), the Z80's RESET and BUSRQ together, plus a power-on RC (22k, 47 uF); the same net (SRESET) resets the YM2151 (IC) | SCHEMATIC | [SCH A-C 3/10 B-D 1-2], [SCH A-C 4/10 C2] |
| BRQ source | main CPU I/O port 0x02 bit 4 (1 = release): the write strobe FSET from PAL IC19 (A1-A3, A6, A7, M/IO, IOWR) clocks an LS174 (IC1), whose Q1 (pin 2, D1 = data bit 4) is the BRQ net; the LS174 is cleared by RESET, so the Z80 is held after power-on until the program writes the bit. The other bits of the same latch: bit 5 BANK (CN3 21B), bit 3 CBLK (display blank, through LS32 IC63), bit 2 NL (flip, xor DSW through LS86 IC57), bits 1/0 the coin counters (TR2, TR1) | SCHEMATIC, MAME (bit meaning) | [SCH A-C 2/10 B8-10] (LS174), [SCH A-C 2/10 D1-2] (PAL IC19); m72_v.cpp `port02_w` |
| Program loading | the main CPU copies the first 0x8000 bytes of rt_r-l1-b.3c into the sound RAM | MEASURED-EMU | oracle kit: sound RAM image equals the ROM bytes after the copy |
| Release time | frame 298, main CPU clock 43206734 (GENPC 0x00437) in every oracle run | MEASURED-EMU | `<tag>_events.txt` |
| RAM at release | code image in 0x0000-0x7FFF; 0x8000-0xFFFF zero (the main CPU writes patterns there before the copy and clears them; at the end of frame 298 only what the Z80 itself wrote is non-zero) | MEASURED-EMU | `<tag>_snd.bin` frames 296-298 |
| Code area writes | the Z80 never writes into 0x0000-0x7FFF | MEASURED-EMU | attract and stage1 runs |

The recompiled blocks are translated from that image (`mapped_end` =
0x8000). The board stops with an error on a write into the code image,
because the blocks would no longer match it.

## 4. Interrupts

| Item | Value | Class | Ref |
|---|---|---|---|
| Interrupt mode | IM 0 (instruction at 0x0001) | ROM | rt_r-l1-b.3c 0x0001: ED 46 |
| NMI | not used: NMI and WAIT pulled up to VCC | SCHEMATIC | [SCH A-C 3/10 C3] |
| Command flag | LS74 (IC69): D tied high, clocked by the main CPU's command write (SND, the same strobe that loads the LS374 latch), cleared asynchronously by the acknowledge decode (CLR) | SCHEMATIC | [SCH A-C 3/10 B-C 2-3] |
| INT | LS02 (IC52) NOR of the command flag (Q) and the inverted YM2151 IRQ: INT is active while either request is pending (level, no synchronizer) | SCHEMATIC | [SCH A-C 3/10 D-G 1-3] |
| Data bus byte | during the acknowledge cycle (M1 and IORQ, LS32 IC63) an LS367 (IC64) drives D5 = /flag and D4 = /IRQ of the YM2151; D0-D3, D6, D7 float to 1 through 10k pull-ups (RA9): 0xDF = RST 18h (command), 0xEF = RST 28h (YM2151), 0xCF = RST 08h (both) | SCHEMATIC | [SCH A-C 3/10 D 7-8, E-F 3-4] |
| Same in MAME | `rst_neg_buffer_device::get_vector` = 0xFF xor inputs (0x20 latch, 0x10 YM2151) | MAME | rstbuf.h; m72.cpp `m72_audio_chips` |
| Same in MiSTer | `{2'b11, ~latch_ready, irq_n, 4'b1111}` | IMPLEMENTATION | rtl/sound.sv |
| Program side | the handlers at 0x0018 (command, via 0x0068) and 0x0028/0x0008 (YM2151, via 0x0076) match these vectors | ROM | rt_r-l1-b.3c |
| RST 08h | taken in the oracle runs (11 times in the coverage runs, once in stage1) | MEASURED-EMU | oracle code map |
| Entry timing | IM 0 with RST n: PC pushed, PC = n, 13 T-states (same as IM 1) | MAME | z80.lst `take_interrupt` |
| Request changes | take effect at once on the board (combinational, asynchronous clear); MAME delays them through `scheduler().synchronize` (rstbuf.cpp `sync_input`); the model follows the board | SCHEMATIC | as above |
| Flag at power-on | undefined: the reset does not clear the LS74; the program acknowledges first thing (0x00A1: OUT (0x06),A) | SCHEMATIC, ROM | [SCH A-C 3/10 B2]; rt_r-l1-b.3c 0x00A1 |

## 5. I/O map

| Item | Value | Class | Ref |
|---|---|---|---|
| Decoder | LS139 (IC68) enabled by IORQ, inputs A1 (A) and A2 (B); A3-A7 not decoded: every port repeats every 8 addresses | SCHEMATIC | [SCH A-C 3/10 E-F 4-6] |
| Y0 (ports 0/1) | YM2151 chip select (SCS), A0 = register/data, RD/WR direct | SCHEMATIC | [SCH A-C 3/10 F5], [SCH A-C 4/10 C2] |
| Y1 (ports 2/3) | with RD: output enable of the command latch (LS374 IC30); a write does nothing | SCHEMATIC | [SCH A-C 3/10 F4-5] |
| Y3 (ports 6/7) | with WR: clears the command flag (acknowledge, any data); a read does nothing | SCHEMATIC | [SCH A-C 3/10 F-G 3-5] |
| Y2 (ports 4/5) | not connected | SCHEMATIC | [SCH A-C 3/10 F5] |
| Reads nobody answers | 0xFF (pull-ups RA9 on D0-D7) | SCHEMATIC | [SCH A-C 3/10 D7] |
| YM2151 read at port 0 | 0xFF (ymfm `ym2151::read`; the chip's behaviour at A0 = 0 is not checked) | MAME | ymfm_opm.cpp |
| MAME | `rtype_sound_portmap`: 0x00-0x01 YM2151, 0x02 latch read, 0x06 acknowledge, `global_mask(0xff)`, no mirrors | MAME | m72.cpp |
| MiSTer | YM2151 only when A1-A7 = 0; latch and acknowledge on A1/A2 as on the board | IMPLEMENTATION | rtl/sound.sv |

The sound program uses only ports 0x00, 0x01, 0x02 and 0x06, so mirrors
and the empty decodes never matter for R-Type; the model decodes like the
board (A0-A2) and counts accesses no device answers.

Sound latch: the command byte stays readable until the next command; reading
does not clear the flag, only the acknowledge does (SCHEMATIC, above; MAME
`generic_latch_8` with `set_separate_acknowledge(true)`). The command handler
at 0x0068 acknowledges first (`OUT (0x06),A`), then reads the latch (ROM).

I/O cycle time: in `IN A,(n)` and `OUT (n),A` the port access follows the
opcode fetch (4 T) and the operand read (3 T), i.e. 7 T after the start of
the instruction (MAME z80.lst `@arg` then `@in`/`@out`; z80make.py performs
the access before it subtracts the step's cycles; SCHEMATIC for the order of
the machine cycles: Zilog Z80 CPU User Manual). The board model times every
port access at instruction start + 7; the sound program uses no other I/O
instruction forms (romtool port-io diagnostics: six sites, all `(n)`).
This decides when a YM2151 timer starts and whether a status read sees a
timer flag that is set during the instruction.

The main CPU writes the command to its I/O port 0x00 (MAME m72.cpp
`m72_portmap`: `map(0x00, 0x00).w("soundlatch", ...)`).

## 6. YM2151 and audio output

| Item | Value | Class | Ref |
|---|---|---|---|
| Chip | YM2151 (IC104) | SCHEMATIC | [SCH A-C 4/10 B-E 3] |
| IRQ | open drain with a 4.7k pull-up (R6) to the interrupt logic (SIRQ) | SCHEMATIC | [SCH A-C 4/10 D-E 3-4] |
| Core in the model | ymfm OPM, the code MAME 0.289 builds | MAME | third_party/ymfm |
| Busy flag | 64 input clocks after a data write (32 x prescale 2) | MAME | ymfm_opm.cpp; ymfm_mame.h `ymfm_set_busy_end` |
| Timer A | 64 x (1024 - NA) input clocks | MAME | ymfm_fm.ipp `update_timer` |
| Timer B | 1024 x (256 - NB) input clocks | MAME | ymfm_fm.ipp `update_timer` |
| Timer reload | from the expiry time | MAME | ymfm_fm.ipp `engine_timer_expired` |
| DAC | YM3014 (IC103), a single-channel DAC, fed with SO, the clock and SH1 only (SH2 not connected): the board outputs one of the two YM2151 channels | SCHEMATIC | [SCH A-C 4/10 C-D 4-5] |
| Analog path | buffer (op amp "064D", IC102), active low-pass (4.7k / 3300 pF / 1200 pF / 6800 pF), volume VR1 50k, power amplifier M51516L (IC101), one speaker | SCHEMATIC | [SCH A-C 4/10 C-F 5-10] |
| MAME | both channels summed into one speaker, gain 0.33 each; no analog filter | MAME | m72.cpp `ymsnd.add_route(ALL_OUTPUTS, "speaker", 0.33)` |
| Which channel SH1 carries | the serial word sent before the SH1 pulse: the YM3012 data sheet (SAM1, "CH1 sampling period", timing figure 3) latches the preceding word on the trailing edge of SAM1 into CH1, and SAM2 the other word into CH2. Which YM2151 channel that is, the data sheets do not say ("left-right/2-channel"); in the die-derived Nuked-OPM the SH1 edge latches the right-channel word (register 0x20-0x27 bit 7) and SH2 the left one. For R-Type the question has no audible consequence: every RL write of the sound program sets both bits (attract 482, stage1 1906 writes, all RL = 3), so the one DAC channel carries the whole mix. The model keeps MAME's sum of both channels for the comparison | SCHEMATIC (data sheet), IMPLEMENTATION (Nuked-OPM), MEASURED-EMU (RL writes) | YM3012 data sheet pin 5/6, figure 3; YM2151 data sheet "SO", "SH1, SH2"; Nuked-OPM `OPM_DAC`, `OPM_Mixer`; oracle kit `*_sio.txt` |
| YM2151 reset | held in reset with the Z80 (SRESET) until the release; MAME runs it from power-on. The model does the same by default and resets the chip at the release with `ym_reset_at_release` (`--ym-reset` of the runners): registers, timers, busy flag, IRQ and the sample grid restart there. Measured on the kit runs, the switch changes nothing that the program can observe: the I/O sequence stays identical (attract 115427, stage1 520068 accesses, `--check`) because the program programs the timers itself before it reads them, and the WAV on MAME's sample grid is bit-identical to the power-on run. On the board the sample grid stands at the release plus multiples of 64 T; the model reproduces that grid only with the switch | SCHEMATIC (reset), MEASURED-EMU (no observable difference) | [SCH A-C 4/10 C2]; `rtype_sound_headless --ym-reset --check` |

R-Type enables both outputs (register 0x20-0x27 bits 7 and 6) for every
voice it sets (482 writes in attract, 1906 in stage1, all with both bits;
MEASURED-EMU), so both channels carry the same signal: the single-channel
DAC and MAME's sum differ only in level (MAME: 0.66 x one channel) and in the
analog filter. The model writes MAME's mix, for the comparison.

The program drives its tick with timer A (NA = 800: 14336 clocks, about
249.7 Hz) and polls the busy flag before every register write (routine at
0x008D, ROM).

## 7. Oracle results (phase R2)

Runs: attract (3000 frames, 497 commands) and stage1 (10000 frames, 1824
commands), MAME 0.289, `rtype_sound_headless --mame-sample-count`. The
ctests `rtype_sound_oracle_attract` and `rtype_sound_oracle_stage1` repeat
the I/O comparison with `rtype_sound_headless --check` whenever the kit
runs exist locally: port and data of every access must match (the data of
an acknowledge write is not compared, see below) and the access time may
differ by at most 64 T, one sample.

| Check | Result |
|---|---|
| Static coverage | all 1359 sound CPU addresses executed in MAME lie in translated blocks |
| Interpreter fallbacks | 0 in both runs |
| Sound I/O sequence | identical to MAME in every access: attract 115427, stage1 520068 (YM2151 writes, status reads with their values, latch reads, acknowledges) |
| Access times | status reads 2 T-states before MAME (the release lands 2 T earlier); writes after a command within -21..+12 T |
| WAV (attract) | level equal (-25.9 dBFS), correlation 0.987, residual -15.7 dB; 91 % of the samples bit-identical |

The WAV difference comes from write timing below one sample (64 T): a
write a few T-states earlier than in MAME can land in the previous sample.
With the release moved by 2 T (a calibration to MAME, not used) 98 % of the
samples are bit-identical. The data byte of the first acknowledge write
differs (A after reset: 0xFF in the model, 0x00 in MAME; undefined on the
chip, ignored by the flag).

## 8. Differences between the sources

| Point | Board (schematic) | MAME 0.289 | MiSTer | Model |
|---|---|---|---|---|
| Port decode | A0-A2, mirrors every 8 | full 8 bits, no mirrors | YM2151 A0-A7, latch A0-A2 | board |
| Unanswered reads | 0xFF (pull-ups) | unmapped read | 0xFF | board |
| Request changes | immediate | delayed to a scheduler sync | immediate | board |
| Sound NMI | pulled up, unused | none | second latch drives NMI | none |
| YM2151 reset | with the Z80 (SRESET) | never | with BRQ | from power-on by default; with the Z80 under `--ym-reset` (section 6: no observable difference) |
| Audio output | one channel, YM3014, analog low-pass | both channels x 0.33 | stereo outputs of both channels | MAME mix |

## 9. Main CPU

| Item | Value | Class | Ref |
|---|---|---|---|
| CPU | NEC V30 at 8 MHz, 20-bit addresses, 16-bit data | MAME | m72.cpp `m72_base` |
| Reset | PS = FFFF, IP = 0, flags clear, MD = 1; first instruction at FFFF0 | MAME | nec.cpp `device_reset` |
| Reset vector | FFFF0: EA 00 08 00 3F, jump to 3F00:0800 | ROM | code map |
| Instruction semantics | 8086/80186 set plus the NEC additions; every opcode validated against the SingleStepTests/v20 data (3,025,000 cases, 362 opcode files, 0 failures; the 8087 escapes and the two undefined 66/67 prefixes are skipped) | MEASURED | sst_v20 test |
| Clock model | MAME's nec core, V30 column of its CLKS/CLKW/CLKM tables; prefetch queue of 6 bytes at 2 clocks per byte, emptied by every control transfer (`do_prefetch`, an admitted approximation of the chip); not measured, the SST v20 cycle counts differ from MAME's V20 column in 77 to 86 per cent of the cases (arcade-oracles.md section 8) | MAME | nec.cpp, necinstr.hxx |
| Interrupt entry | PSW pushed, BRK and IE cleared, vector from the acknowledge cycle after the push, PS and IP pushed: 8 clocks (the PSW push only, as MAME charges it) | MAME | nec.cpp `nec_interrupt` |
| Interrupt acceptance | NMI edge, INT level while IE = 1, neither directly after MOV/POP into a segment register or BUSLOCK; STI does not delay the next INT in MAME (the NEC manual delays it by one instruction, not modelled) | MAME | nec.cpp `execute_run` |
| REP | interruptible between iterations; the pushed IP is that of the prefix, so the instruction restarts with the remaining count after IRET | MAME | necinstr.hxx `cont_rep` |
| Boot lockstep | every instruction start of the first 320 frames (3,676,169 instructions) agrees with a MAME debugger trace in registers, PSW and clock, including the sound program upload and the Z80 release in frame 298 | MEASURED-EMU | rtype_headless --mame-trace |
| Recompiled blocks | the boot lockstep holds with the main CPU on its recompiled blocks (2,167,580 block runs, no interpreter unit); the attract run of 1,200 frames and the stage 1 replay of 10,000 frames produce byte-identical RAM, video, sound and I/O dumps with and without `--interpreter` | MEASURED-EMU | rtype_headless, v30_emit_differential |

Where the measured chip and MAME define a result differently, the model
follows the chip (origin class MEASURED, SingleStepTests/v20); each place is
marked in runtime/v30_ops.h. The deviations from MAME 0.289:

| Instruction | Chip (SST v20) | MAME |
|---|---|---|
| BLT (7C), BGE (7D) | S xor V, as documented | the other way round |
| 63 | consumes a ModRM byte | no operand |
| CHKIND | signed bound compare | unsigned |
| MOV sreg (8C, 8E) | the register field is taken modulo 4 | field 4-7 unused |
| ADJ4A/ADJ4S, ADJBA/ADJBS | the measured adjust rules (also for non-BCD input) | different for digits above 9 |
| TEST1 | flags from the masked value | flags from the operand |
| ROL4, ROR4 | AL written last (ror4 al is a no-op) | AL written first |
| INS | the offset register is updated before the insert | after |
| REPC/REPNC | the carry condition applies to CMPS/SCAS only; MOVS/STOS/LODS/INS/OUTS repeat unconditionally | always conditional |
| ADD4S/SUB4S/CMP4S | binary add/subtract per byte with the decimal adjust | per-digit arithmetic |
| PREPARE | copies through the old BP, SP moved last (80186 definition) | SP moved first |
| Shift group /6 | alias of SHL | undefined |
| F6 /1, F7 /1 | alias of TEST | undefined |
| FF /7 | alias of PUSH; PUSH SP pushes the decremented value | undefined |
| NEG | all flags as 0 - x (AC, V included) | CY and S/Z/P only |
| MUL (signed byte/word) | CY = V = (the product is not the sign extension of its low half) | high half non-zero |
| CVTBD (AAM) | divides by its immediate; immediate 0 sets AH = FF and leaves AL | always divides by 10 |
| D6 | TRANS (XLAT) | SETALC |

MAME artefact not reproduced: MAME runs the CPUs in 1.5 us time slices (12
clocks, `add_quantum` for the first 25 seconds) and charges the two REP
clocks again at every continuation of a string instruction after a slice
(`cont_rep` into `do_rep`). The model runs a REP in one piece and charges
them once, so a long REP finishes earlier than in MAME (about 12 per cent
of its time for REP MOVSW). The lockstep comparison adopts MAME's clock at
those points (459 times in the first 320 frames, 1.9 million clocks in
total) and reports them; from frame 285 on the free-running machine is
therefore ahead of MAME by whole frames, and the per-frame RAM and video
hashes of the oracle kit no longer line up (the game itself stays in step
with VBlank, so frames of a played run compare at the same index, see
section 13).

A time-slice mode that reproduces the artefact was examined and not
built. The slice ends are not on a grid the main CPU alone could
reproduce: in the first 4 million trace lines MAME continues 954,246 REP
pieces, and their end clocks modulo 12 (relative to the line timer, which
restarts the slices every 512 clocks) are spread evenly over the even
residues instead of sitting at 0. The reason is in schedule.cpp
`timeslice`: after every slice the base time moves to the local time of
the last CPU that ran, which is the Z80 at 3.579545 MHz with a cycle of
279,365,114 attoseconds, and the YM2151 timers cut slices in the same
domain. Reproducing the grid would need MAME's Z80 cycle accounting to
the cycle, and the sound comparison (section 7) shows ours differs from
it by up to 21 T. The comparisons therefore use the lockstep's resync and
snapshots matched by frame offset.

Update 2026-10-26: the time-slice mode now exists as a verification
stage (stage M, [arcade-oracles.md](arcade-oracles.md) section 5). With
MAME's Z80 steps (z80.lst), MAME's scheduler arithmetic and the
synchronisation of latch, RST buffer, reset and interrupt lines it
reproduces the slice grid: the boot trace runs through all 976,402 REP
continuations without a resync, and every field of the hash line equals
MAME 0.285 over 3000 attract frames and 10,000 frames of the stage 1
replay, except the picture of frames 117-193 (MAME's palette starts as a
rainbow, finding F6 there). The game build keeps the single-piece REP.

Update 2026-10-27: "single piece" holds for the clocks, not for the runs.
The game build stops a REP at its own run targets too (the line events
every 512 clocks, the frame end, a raised INT), and until then charged
the 2 REP clocks again at each such continuation, the V30 runner's
default. At the boot's first REP (the sprite RAM clear in frame 53, 4
continuations) that put it 8 clocks behind mameref. The machine now
turns the charge off (`rep_cont_charge` false in `machine_init`), so the
clock count of a REP no longer depends on where a run ends; the game
build then equals mameref on the main CPU side over 3000 attract frames
and 10,000 frames of stage 1 ([arcade-oracles.md](arcade-oracles.md)
section 10.3, finding E7).
The V30 clock model is MAME's table model and not measured; the judge
decision (SST v20 for the semantics, MAME for the board and, as a
model, the timing) is arcade-oracles.md section 8.

## 10. Interrupt controller

| Item | Value | Class | Ref |
|---|---|---|---|
| Chip | uPD71059 (8259 compatible) at I/O 0x40-0x43, registers on the even addresses (8-bit device on the low byte lane) | MAME | m72.cpp `m72_portmap` `umask16(0x00ff)` |
| Model | transcription of MAME's pic8259: ICW1-4, OCW1-3, fixed and rotating priority, edge or level trigger, automatic EOI, x86 acknowledge (base + level); the 8080 acknowledge sequence is not implemented | MAME | runtime/pic8259 |
| Program setup | ICW1 0x17, ICW2 0x20, ICW4 0x0F at boot (edge triggered, single, x86 mode, automatic EOI, base vector 0x20) | MEASURED-EMU | <tag>_io.txt |
| IR0 | VBlank: raised at the start of screen line 256, dropped at line 257 | MAME | m72.cpp `scanline_interrupt` |
| IR2 | raster: raised at the start of the line programmed through I/O 0x06 ((data & 0x1FF) - 128), dropped on every other line; a write to 0x06 also drops it | MAME | m72.cpp, m72_v.cpp `irq_line_w` |
| Vectors | 0x20 (VBlank), 0x22 (raster); the table in ROM points every other vector at a RETI stub | ROM | code map |
| INT line | the controller's INT output drives the V30's INT; MAME recomputes it with a zero-length timer after every change, which the CPU sees at its next instruction boundary either way | MAME | pic8259.cpp `irq_timer_tick` |

## 11. Memory and I/O map of the main CPU

Memory (m72.cpp `rtype_map`, `m72_cpu1_common_map`; origin class MAME):

| Range | Device |
|---|---|
| 00000-3FFFF | program ROM: L0/H0 interleaved at 00000, L1/H1 at 20000 |
| 40000-43FFF | work RAM, 16 KiB |
| C0000-C03FF | sprite RAM (the program's copy; the hardware shows the DMA buffer) |
| C8000-C8BFF | palette 0 (sprites): words, R at 000-0FF, G at 200-2FF, B at 400-4FF, 5 bits each; A9 is not connected so 100-1FF mirrors 000-0FF in every bank; reads return D0-D4 with the upper bits set |
| CC000-CCBFF | palette 1 (tiles), same layout |
| D0000-D3FFF | video RAM 1 (foreground tilemap, Ax tile ROMs) |
| D8000-DBFFF | video RAM 2 (background tilemap, Bx tile ROMs) |
| E0000-EFFFF | the sound CPU's 64 KiB RAM (byte accesses; the program is loaded through this window, section 3) |
| FFFF0-FFFFF | ROM, the L1/H1 pair again (reset vector) |

Unmapped reads return 0 (MAME's default for this address space); the model
counts them.

I/O (m72.cpp `m72_portmap`; origin class MAME):

| Port | Access | Device |
|---|---|---|
| 00-01 | read | IN0 (joystick and buttons, active low) |
| 02-03 | read | IN1 (start, coin, service, test; bit 7 "sprite DMA done" reads 1 in MAME) |
| 04-05 | read | DSW (MAME default 0xFDFB) |
| 00 | write | sound command latch (section 5) |
| 02 | write | bit 0/1 coin counters, bit 2 flip (xor DSW bit 8), bit 3 display off, bit 4 sound CPU reset release (1 = run), bit 5 BANK; the LS174 output latch of sheet 2/10, see section 3 |
| 04 | write | sprite DMA: the hardware takes a copy of the sprite RAM |
| 06-07 | write | raster interrupt line (section 10) |
| 40-43 | read/write | interrupt controller (section 10) |
| 80-87 | write | scroll registers: 80 fg y, 82 fg x, 84 bg y, 86 bg x |

A word write to a byte port reaches the byte handler with its low lane and
leaves the odd address unmapped, as MAME's dispatcher does (the program's
word writes to 0x00 and 0x02 count as unmapped writes to 0x01 and 0x03).

## 12. Line timing and the frame

| Item | Value | Class | Ref |
|---|---|---|---|
| Frame | 284 lines of 512 clocks, 145408 clocks, 55.0176 Hz | MAME | m72.cpp `set_raw` |
| Visible | lines 0-255, columns 64-447 of 512 (384 x 256) | MAME | m72.cpp `set_raw` |
| Frame origin | MAME measures the frame from the start of VBlank (line 256); the line timer runs at 512-clock steps from there, the first event 28 lines after reset at line 0 | MAME | screen_device `time_until_pos`; m72.cpp `machine_reset` |
| First VBlank request | one full frame after reset (clock 145408) | MAME | as above |
| CPU scheduling | the main CPU runs to each line event, overshooting by at most one instruction (a REP stops at an iteration boundary); the sound board follows in step | MAME (semantics), model | rtype_machine.cpp |

## 13. Video

| Item | Value | Class | Ref |
|---|---|---|---|
| Tilemaps | two of 64 x 64 tiles of 8 x 8 (512 x 512 pixels); word 0: bits 0-13 tile code, bit 14 flip x, bit 15 flip y; word 1: bits 0-3 palette, bits 6-7 priority group | MAME | m72_v.cpp `m72_m81_get_tile_info` |
| Tile ROMs | foreground from the four Ax ROMs, background from the four Bx ROMs, 4 planes of one ROM each, 8 bytes per tile and plane, bits from the MSB | MAME | m72.cpp `tilelayout`, `gfx_m72` |
| Scroll | x as written; y plus 128 (`set_scrolldy(-128, -128)`); the tilemap pixel is at (column + x, line + y + 128) modulo 512 | MAME | m72_v.cpp VIDEO_START m72; tilemap.cpp |
| Priority groups | foreground: group 0 all pens low; 1 pens 8-15 high, 1-7 low; 2 and 3 pens 1-15 high. Background: group 0 all pens low including pen 0; 1 pens 8-15 high, 0-7 low; 2 and 3 pens 1-15 high, pen 0 low | MAME | m72_v.cpp `set_transmask` |
| Draw order | high-priority pens of both maps mark the priority buffer; then both maps' low pens, then both maps' high pens again, background first; background group 2 counts as low priority in those two passes | MAME | m72_v.cpp `screen_update` |
| Sprites | 4 words: y (bits 0-8, 384 - y - 16 x height), code, attributes (bits 0-3 palette, bit 10 flip y, bit 11 flip x, bits 12-13 height, bits 14-15 width, as powers of two), x (bits 0-9, x - 256); a wide sprite takes width entries; drawn from the last list entry to the first, a pixel only where the priority buffer is 0, every non-transparent pixel marks it 31 | MAME | m72_v.cpp `draw_sprites`, drawgfx `prio_transpen` |
| Sprite ROMs | 16 x 16, 32 bytes per sprite and plane: columns 0-7 in bytes 0-15, 8-15 in bytes 16-31; the 32 KiB ROMs are loaded twice | MAME | m72.cpp `spritelayout`, ROM_RELOAD |
| Palette | 5 bits per component, (v << 3) or (v >> 2); sprites use palette 0, tiles palette 1 | MAME | m72.cpp `changecolor`, pal5bit |
| Display off | port 0x02 bit 3 blanks the screen | MAME | m72_v.cpp `screen_update` |
| Flip screen | port 0x02 bit 2 xor DSW bit 8 (both flip the picture); the tilemaps are mirrored around the visible area (tilemap.cpp draws the pixmap from the last row and column; the scroll offsets become visible extent - map size + scroll, extents 512 x 256, so the mirrored source is (column - x, line + 128 - y)); sprites mirror their position in the 512 x 284 bitmap (512 - 16 width - x, 284 - 16 height - y) and invert their own flips | MAME | m72_v.cpp `port02_w`, `draw_sprites`; tilemap.cpp `effective_rowscroll`, `effective_colscroll`, `draw_common` |
| Raster split | at the raster interrupt line m72 updates the screen up to that line (`update_partial(vpos)`): the rows above show the scroll registers, video RAM and sprite buffer of that moment, the rows from there to 255 the state at the start of VBlank. R-Type sets the line to 239 (port 0x06 = 0x16F) and writes a third of its scroll values after it, for the status bar | MAME, MEASURED-EMU (R-Type's use) | m72.cpp `scanline_interrupt`; oracle kit `*_io.txt` |

The renderer (games/rtype/rtype_video) keeps the frame in an indexed
bitmap with a priority buffer as MAME does; the machine's `on_raster`
hook draws the rows up to the raster line, the front end finishes the
frame at VBlank and resolves the palette then (MAME converts the indexed
bitmap at that point, so palette writes are not split per line either).
Checked against the kit's stage 1 snapshots: the tilemaps and the status
bar below the raster line are pixel-identical; the remaining differences
are sprite positions, which follow the main CPU time (section 9, the REP
time slices). The flipped picture was only inspected by eye (no flipped
oracle run).

## 14. Inputs

| Port | Bits (active low) | Class | Ref |
|---|---|---|---|
| IN0 | 0 right, 1 left, 2 down, 3 up, 4 button 4, 5 button 3, 6 button 2 (force), 7 button 1 (fire); bits 8-15 the same for the cocktail player 2 | MAME | m72.cpp INPUT_PORTS common |
| IN1 | 0 start 1, 1 start 2, 2 coin 1, 3 coin 2, 4 service credit, 5 test, 7 sprite DMA done (reads 1) | MAME | m72.cpp |
| DSW | 0-1 lives, 2 demo sounds, 3 bonus life, 4-7 coinage, 8 flip, 9 cabinet, 10 coin mode, 11 difficulty, 12 continue, 13 stop mode, 14 invulnerability, 15 service mode; default 0xFDFB | MAME | m72.cpp INPUT_PORTS rtype |
