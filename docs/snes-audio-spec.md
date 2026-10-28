# SNES Audio Unit: S-SMP, Timers, IPL, S-DSP

Register-level specification of the SNES sound unit as MAMR implements it
(phase S4 of docs/snes-architecture.md): the S-SMP frame around the SPC700
(`runtime/snes/snes_smp.{h,cpp}`), MAMR's own boot program
(`runtime/snes/snes_ipl.{h,cpp}`), the S-DSP (`runtime/snes/snes_dsp.{h,cpp}`),
the host output stage (`runtime/snes/snes_audio_out.{h,cpp}`) and the .spc
player (`tools/spcplay/`). The SPC700 core itself is phase S2
(`runtime/spc700_*`, `recompiler/spc700_*`). This specification stands on
its own next to docs/snes-hardware-spec.md (board, CPU) and
docs/snes-ppu-spec.md.

**Sources:**

- **fullsnes** (Martin Korth, nocash), chapters "SNES APU Memory and I/O
  Map", "SNES APU SPC700 I/O Ports", "SNES APU Main CPU Communication Port",
  "SNES APU DSP BRR Samples", "DSP BRR Pitch", "DSP ADSR/Gain Envelope",
  "DSP Volume Registers", "DSP Control Registers", "DSP Echo Registers",
  "SNES APU Low Level Timings". The primary specification. References:
  `[FS chapter]`.
- **SNESdev wiki**, pages "S-DSP" and "DSP envelopes" (rate counter: start
  value, wrap, per-rate offsets). References: `[SD page]`.
- **ares** (ISC), commit c76aaff, `ares/sfc/smp/*.cpp` (timer stages, I/O
  behaviour, bus timing): a permissive structure reference for the S-SMP
  frame. References: `[ares file]`. For the S-DSP, ares is only the
  external oracle (black box: PCM output and register state); the DSP is
  written from fullsnes and the SNESdev wiki alone, without reading any
  emulator's DSP source (ares' DSP carries the structure of blargg's LGPL
  SPC_DSP).
- **MAME 0.289** `s_smp.cpp`, `s_dsp.cpp` (LGPL): not used, not read for
  this work. blargg's snes_spc (LGPL): not used.

Where sources differ, section 9 lists both readings and what MAMR does.

## 1. Memory map and I/O page

| Address | Content |
|---|---|
| $0000-$00EF | RAM |
| $00F0-$00FF | I/O registers; every write also lands in the RAM below `[FS I/O Map]` |
| $0100-$01FF | RAM, SPC700 stack |
| $0200-$FFBF | RAM |
| $FFC0-$FFFF | IPL ROM when CONTROL bit 7 is set (reads only), RAM otherwise; writes always reach the RAM |

| Reg | Name | Read | Write |
|---|---|---|---|
| $F0 | TEST | 0 | stored; see below |
| $F1 | CONTROL | 0 | bits 0-2 timer enables, 4 clear input ports 0/1, 5 clear 2/3, 7 IPL ROM |
| $F2 | DSPADDR | value | value |
| $F3 | DSPDATA | DSP register (DSPADDR & $7F) | DSP register if DSPADDR < $80 |
| $F4-$F7 | CPUIO0-3 | latch written by the 65816 | latch read by the 65816 |
| $F8/$F9 | AUXIO4/5 | value | value (unconnected pins act as storage) |
| $FA-$FC | T0-T2 target | 0 | target, 0 = 256 |
| $FD-$FF | T0-T2 output | 4-bit counter, then cleared | ignored |

Power-on and reset: CONTROL $B0 (IPL mapped, input ports cleared, timers
off) `[FS I/O Ports]`, TEST $0A. RAM, the DSP register file and all other
latches are 0 at power-on: that is MAMR's power-on fill, the same as the
oracle pipeline's `fill=00` (real hardware holds garbage, fullsnes
describes typical patterns).

TEST ($F0) `[FS I/O Ports]`: bit 0 stops the timers, bit 1 enables RAM
writes, bit 2 crashes the CPU, bit 3 enables the timers, bits 4-7 add wait
states. MAMR stores the value, gates the timer clock with bits 0 and 3 and
SPC700 RAM writes with bit 1, as ares does `[ares smp/timing.cpp,
memory.cpp]`. Not modelled: bit 2. Writes to TEST are ignored while the P
flag is set `[ares smp/io.cpp]`; fullsnes does not mention that condition.

Wait states (DOC, 2026-10-24): fullsnes gives two 2-bit fields that add
0, 1, 4 or 9 cycles to an access of their class (a plain access takes 1
cycle, so 1, 2, 5 or 10): bits 4-5 for RAM accesses, bits 6-7 for I/O
and ROM accesses; internal cycles take the RAM or the I/O access time by
a table of their own; 4 and 9 waits fail with some opcodes and only 0
and 1 are stable `[FS "00F0h - TEST"]` (the SNESdev wiki calls bits 6-7
the internal and bits 4-5 the external wait state `[WIKI S-SMP]`, names
only). blargg's `test_speed` (docs/snes-oracles.md section 12.1) runs
its counting loop from $00F4-$00F6, inside the I/O page: the screenshot
on the snescentral article shows its count unchanged for TEST = 1A, 2A,
3A (bits 4-5) and halved for 4A-7A and divided by ten for CA-FA (bits
6-7), which fits fullsnes' assignment with the loop's fetches and its
internal cycles all in the I/O class. MAMR models that (`Smp::step`):
after an instruction every RAM cycle costs `WAIT_CYCLES[bits 4-5]`
more, every I/O register or IPL ROM cycle `WAIT_CYCLES[bits 6-7]` more,
and every internal cycle the rate of the class the opcode was fetched
from, with {0, 1, 4, 9}; the stamps inside the instruction keep their
nominal places (CHOICE, the internal-cycle table fullsnes mentions is
not published; the modes are test-only). The timers and the DSP keep
their own clock, so the slow CPU sees more timer ticks per instruction,
as blargg's timer tests expect. ares follows byuu's measurements in
blargg's notes.txt instead (per-opcode step tables); on test_speed MAMR
prints 251 for 0A-3A, 126 for 4A-7A and 25 for CA-FA, the screenshot
252/251, 126 and 25, aresref 251, 126 and 26; the five speed and
timer-speed ROMs differ between MAMR and aresref, in both stages alike,
from frame 11 (test_speed: smp, wram), 8 (test_timer_speed, 2 and 3:
smp) and 4 (test_timer_speed_2: cpu, apuio, wram, aram, mclk) on
(known deviation, run 2026-10-24 with the model, 300 frames; docs/snes-oracles.md section 10).

## 2. Timers

Three timers on a common divided clock `[ares smp/timing.cpp]`, `[FS I/O
Ports]`:

1. Stage 0/1: a divider toggles the stage-1 line every 64 SPC700 clocks
   (T0, T1) or every 8 clocks (T2). It runs from power-on, independent of
   the enable bits.
2. The line passes the TEST gate (bit 3 set and bit 0 clear). Each falling
   edge of the gated line increments stage 2 of an enabled timer: T0/T1 at
   8 kHz, T2 at 64 kHz.
3. Stage 2 is an 8-bit counter compared with the target after each
   increment; on a match it restarts at 0 and stage 3 increments. Target 0
   matches after 256 increments.
4. Stage 3 is a 4-bit counter ($FD-$FF). A read returns it and clears it.
   Dummy reads clear it too: the SPC700 reads the destination of most
   writes first, so `MOV $FD,A` clears T0's output (the S2 core performs
   that dummy read as a real bus read).
5. Setting an enable bit from 0 to 1 clears stages 2 and 3. Writing 1 to a
   timer that is already enabled keeps both. A disabled timer keeps its
   stage-3 value readable. This is ares' rule (also LakeSnes and blargg's
   snes_spc). fullsnes reads differently: "0=Disable, set TnOUT=0 &
   reload divider", i.e. writing 0 already clears. Both agree that a
   re-enabled timer starts from 0; they differ only in what a read of a
   disabled timer returns (section 9).

A TEST write that changes the gate can itself produce a falling edge (ares
re-evaluates the line on TEST writes; MAMR does the same).

Edges relative to power-on: the first T0/T1 edge comes after 128 clocks,
the first T2 edge after 16. fullsnes states that the timers advance in
sync with DSP steps T1 and T17 of its access chart; MAMR (like ares) ties
them to the SPC700 clock count from power-on, see section 9.

## 3. Clock, time stamps and catch-up

**Clock.** The SPC700 clock is the 24.576 MHz audio resonator divided by
24 (fullsnes names only this value). ares and MesenCE run the APU at
32040 Hz * 768 instead; that is an emulator convention, not a measured
mean. On consoles the DSP sample rate was measured (MEASURED, research
package A, question A14) at 31965 to 32182 Hz, mean 32076 Hz over 143
consoles (TASBot survey 2025, reported by Time Extension 2025-03-10;
tool smpspeed-usb2snes, MIT, https://github.com/TASBotL3C/smpspeed-usb2snes),
with 32010 to 32152 Hz in lidnariq's earlier series (nesdev t=24610,
https://forums.nesdev.org/viewtopic.php?t=24610, S-CPU measuring an
S-SMP delay loop against the master crystal, checked with an
oscilloscope on a PAL 1CHIP: 32.08 kHz cold, 32.09 kHz warm) and
undisbeliever's logs 2023-2026
(https://undisbeliever.net/blog/20250313-smpspeed.html: 32036 to 32155
Hz across five consoles, 2/1/3 three-chip SFC 32147 to 32156, 1CHIP SFC
32040 to 32048, 1/1/1 SFC 32085 to 32098, PAL 1CHIP 32087 to 32095).
Warming adds 8 to 10 Hz; the console-to-console spread (217 Hz) is far
larger. The claim that consoles speed up with age is an interpretation
of the press, not shown by the data. A second, independent research
pass over the same question gives the SNESdev wiki's range instead,
"about 32000 to 32160 Hz" with a temperature drift (DOC,
https://snes.nesdev.org/wiki/Timing, method not stated); the two
ranges come from different methods and are kept apart, not merged. The
nominal rate 24.576 MHz / 768 = 32000 Hz is DATASHEET arithmetic from
the resonator's rating. The relation to the master clock is
kept as an exact fraction; the system takes the DSP rate as a parameter
(`SystemOptions::dsp_rate`, `smp_clock_for(rate, pal)` in
runtime/snes/snes_system.h: rate * 32 SMP clocks per second against
ares' integer master clock, reduced; `snes_headless --dsp-rate HZ`),
default 32040 Hz for oracle parity. The named fractions in use:

| Name | APU clock | Master clock | SPC700 clocks per master clock | Used by |
|---|---|---|---|---|
| `SMP_CLOCK_NOMINAL` (snes_smp.h) | 24.576 MHz | 236.25 / 11 MHz (NTSC) | 5632 / 118125 | `Smp` default, spcplay, the audio tests |
| `SMP_CLOCK_MEASURED` (snes_smp.h) | 32040 * 768 Hz | 236.25 / 11 MHz | 15664 / 328125 | spcplay `--measured-clock` |
| `SMP_CLOCK_ARES_NTSC` (snes_system.h) | 32040 * 768 Hz | 21477273 Hz (ares' rounded integer) | 341760 / 7159091 | the system (default `smp_measured`), NTSC |
| `SMP_CLOCK_ARES_PAL` (snes_system.h) | 32040 * 768 Hz | 21281370 Hz (ares) | 34176 / 709379 | the system, PAL |

The system also has a nominal PAL fraction (102400 / 2128137,
snes_system.cpp) for `smp_measured = false`. The name `MEASURED` is kept
for compatibility; read it as "ares/MesenCE convention". The system uses
ares' integer master clock rather than the exact one because the 1.3e-8
difference decides port polling races against ares (snes_system.h).
`smp_clock_for(32040, pal)` reproduces the two ARES fractions exactly
(static_assert); another rate, e.g. 32076 Hz (342144 / 7159091 NTSC),
gives a console-like pitch and port timing, and a hash file written at
it carries `clk=dsp32076` so that it is never compared with an oracle
file by mistake. A frontend passes `System::dsp_rate()` to
`AudioOut::init` as the input rate.

**Time of an access.** A bus cycle with stamp s (SPC700 clock number) takes
place at the end of clock s, i.e. at SPC700 time s + 1. Reads of the input
ports $F4-$F7 sample in the middle of the cycle, at time s + 1/2 (ares
splits these reads in two half cycles around the sampling point `[ares
smp/memory.cpp]`). A 65816 port access at master clock t happens at SPC700
time t * num / den. Comparisons are done in integers (doubled SPC700 time
times den against doubled master time times num), so no rounding enters.

**Visibility.** A 65816 read at t sees the last SPC700 write to that port
with time <= t; an SPC700 port read sees the last 65816 write with time <=
its sampling point. CONTROL bits 4/5 clear the input latches at the time
of the write (65816 writes queued before that time are applied first).

**Catch-up (`Smp::run_to(t)`).** The SPC700 executes whole instructions as
long as the instruction ends at or before t; it never starts one that
would end later, so it never runs ahead of the 65816. An instruction's end
is known before it runs: all instructions that fit with 12 clocks to spare
run directly, the last few are first executed as a throw-away probe to get
their exact length (a branch's length depends on its condition). A branch
can depend on a DSP register (CBNE, DBNZ, BBS/BBC on $F3); the DSP runs in
step with the SPC700's committed clock, so for a read through $F3 the
probe first brings the real DSP up to the moment of that read. That is
safe because the probed instruction is the next one to run and has not
written anything yet: nothing the SPC700 does can come between. If the
same instruction wrote something before the $F3 read (only INCW/DECW and
similar read-modify-write forms on $F2/$F3), the probe reports the value
as possibly stale and the catch-up assumes the instruction's longest
form. Without this a CBNE on OUTX let the SPC700 end up to two clocks
ahead of t in about a third of the phase positions (test
`test_catchup_dsp_branch`).

**65816 writes** are queued with their time and applied when the SPC700
reaches that time (lazily at its port reads and CONTROL clears; whatever
every later read will see is folded into the latches at the end of each
catch-up, so the queue holds at most a few entries).

**65816 reads** first catch up to t. The instruction that straddles t may
write the port before t (MOVW writes its low byte one cycle before the
instruction ends; DBNZ dp, INCW/DECW and taken-branch tails have the same
shape). If the opcode at PC carries the table's I/O mark, it is executed
as a probe: a copy of the register file, RAM writes into an overlay, timer
outputs from a copy advanced to the access, input ports including queued
65816 writes; the last write to the requested port with time <= t is
returned. Apart from bringing the DSP forward to a $F3 read (as above),
the probe has no side effect on the frame. The one remaining
approximation: an $F3 read that follows a write in the same instruction
sees the DSP as of the start of the instruction.

With these rules the port traffic is exact per bus cycle in both
directions. tests/snes-audio/test_snes_smp.cpp checks it against a closed
formula for every third master clock over 60,000 clocks at both clock
rates (reads, including the cycle in which only the probe knows the
value) and for 65816 writes echoed back by the SPC700.

**DSP phase.** The DSP advances one step per SPC700 clock (section 5).
When the SPC700 accesses the bus in clock s, the DSP has completed the
step of clock s + 1. This is the phase ares produces (its DSP thread runs
until its clock passes the SMP's); with any other phase KON writes near the
poll step land in a different sample and the PCM no longer matches ares
(section 8). The hardware starts both chips from the same reset signal
`[FS Low Level Timings]`; the sub-step phase is not documented.

**65816 side (IoPort form).** `Smp::io_read(ctx, addr, open_bus, t)` and
`Smp::io_write(ctx, addr, data, t)` have the signature of the board's
`IoPort` hooks (runtime/snes/snes_map.h): addr
$2140-$217F, port = addr & 3, t = master clock of the access. Optional
hooks: `port_trace` (direction, time, port, value; the P lines of the
oracle format, t in master clocks for 65816 writes and SPC700 clocks for
SPC700 writes) and `io_trace` (every SPC700 write to $F0-$FF with its
clock; spcplay derives the DSP register stream from it).

## 4. IPL: upload protocol and MAMR's boot program

### 4.1 Protocol

From fullsnes "Main CPU Communication Port" (uploader and boot ROM
description). Observable behaviour of the boot program:

1. Entry at $FFC0 (reset vector $FFFE/$FFFF). SP = $EF; RAM $01-$EF is
   cleared from $EF downwards (with the direct page selected by P; $00 is
   left, it is overwritten in step 4).
2. Ready: $AA to port 0, $BB to port 1. The 65816 waits for $BBAA.
3. Wait until port 0 reads $CC (the first kick).
4. Command: ports 2/3 to RAM $00/$01 (destination or entry address); the
   command byte from port 1; the kick from port 0 is written back to port 0
   (acknowledge).
5. Command != 0, transfer: wait until port 0 reads 0. Then for each byte
   with expected index Y: wait until port 0 equals Y; read the data from
   port 1, write Y to port 0 (acknowledge), store the data at [$00]+Y,
   Y = Y + 1, on wrap $01 = $01 + 1. A port 0 value that is not Y and lies
   1..128 ahead of Y (bit 7 of Y - port0 set) is the next kick: back to 4.
   The uploader sends kick = (length + 2) | 1.
6. Command == 0: JMP [$0000+X] with X = 0. State at the entry point:
   A = X = Y = 0, SP = $EF, N = 0, Z = 1, C = result of the last
   comparison (1 after the $CC wait; Y >= kick after a transfer), V, H, I,
   B, P unchanged since the entry at $FFC0.

Games enter the boot program again at run time (driver reset commands,
song bank uploads), and some homebrew uses $FFC9 (step 2 without the
clear) as a dummy entry point `[FS Communication Port]`.

### 4.2 MAMR's program

Written from the protocol above, hand-assembled (runtime/snes/snes_ipl.cpp
carries the commented byte listing). The register use is MAMR's own: X
holds the expected index (compared with port 0 and sent back as the
acknowledge), Y the store offset, both advance together; the command code
clears Y before it branches, a port 0 value ahead of the index returns to
the command code through BMI.

```text
FFC0  mov  a,#$00          ; stack and zero page
FFC2  mov  x,#$EF
FFC4  mov  sp,x
FFC5  clr: mov (x),a       ; $EF down to $01
FFC6  dec  x
FFC7  bne  clr
FFC9  mov  a,#$AA          ; ready: both bytes with one word write
FFCB  mov  y,#$BB
FFCD  movw $F4,ya
FFCF  mov  a,#$CC
FFD1  wcc: cmp a,$F4       ; wait for the first kick
FFD3  bne  wcc
FFD5  cmd: movw ya,$F6     ; address to $00/$01
FFD7  movw $00,ya
FFD9  mov  y,#$00          ; store offset
FFDB  mov  a,$F5           ; command byte
FFDD  mov  $F4,$F4         ; acknowledge the kick
FFE0  bne  xfer
FFE2  mov  x,a             ; A = X = Y = 0
FFE3  jmp  [$0000+x]
FFE6  xfer: mov x,$F4      ; wait for index 0
FFE8  bne  xfer
FFEA  miss: bmi cmd        ; port 0 ahead by 1..128: next command
FFEC  byte: cmp x,$F4
FFEE  bne  miss
FFF0  mov  a,$F5           ; data
FFF2  mov  $F4,x           ; acknowledge
FFF4  mov  [$00]+y,a       ; store
FFF6  inc  x
FFF7  inc  y
FFF8  bne  byte
FFFA  inc  $01             ; next page
FFFC  bra  byte
FFFE  dw   $FFC0
```

Only MOV, MOVW, CMP, INC, DEC and branches are used, so V, H, I, B and P
are never touched, as in the original. N = 0, Z = 1 at the jump come from
`mov x,a` with A = 0; C comes from the last comparison (`cmp a,$F4` after
the $CC wait, `cmp x,$F4` after a transfer), the same rule as the
original's.

**Identity.** CRC-32 of MAMR's 64 bytes: `2ecad97f` (an earlier version,
`3a4af6e8`, shared the original's transfer loop and is replaced). Sony's
ROM (MAME's `spc700.rom`): `44bb3a40`. The test suite checks both values.
Measured against a user dump of the original (common byte sequences
anywhere in the two images, not only at the same position):

| Common sequence | MAMR | Original | Content |
|---|---|---|---|
| 4 bytes | $FFD5 | $FFEF | `movw ya,$F6; movw $00,ya` (copy the address) |
| 4 bytes | $FFC5 | $FFC5 | `mov (x),a; dec x; bne` (the clear loop body) |
| 3 bytes | $FFE3 | $FFFB | `jmp [$0000+x]` (the protocol's final jump) |
| 3 bytes | $FFC2 | $FFC0 | `mov x,#$EF; mov sp,x` |
| 3 bytes | $FFF3 | $FFE1 | operand $F4 followed by `mov [$00]+y,a` |
| 3 bytes | $FFD2, $FFE7 | $FFD7 | operand $F4 followed by `bne` back over a 2-byte poll |

No common sequence is longer than 4 bytes; 23 bytes of MAMR's 64 lie in
common sequences of 3 or more (20 without the final jump), 8 bytes have
the same value at the same position. Counting pairs as well, 39 bytes lie
in common sequences of 2 or more: mostly an opcode with a port operand
(`mov a,$F5`, `$F4` polls, `bne` over two bytes), which any program that
speaks this protocol through the same ports produces. The two 4-byte
sequences are the shortest SPC700 code for what they do (a 16-bit copy
from the ports to $00, a 4-clock clear loop through X that ends with
SP = $EF in 9 bytes so that the ready code stays at $FFC9). Sony's code
is not part of MAMR; a user dump can be loaded instead (`ipl_load_dump`,
CRC checked; spcplay `--ipl`, test_snes_ipl with an argument).

### 4.3 Comparison with the original

Checked with a user dump of the original (not in the repository), each
with two access timings of a simulated 65816: (a) a zero-page block, a
300-byte block across page boundaries, the program, its jump back to
$FFC0, a second upload ending with a 254-byte block; (b) one upload with
a block across $8000 (address high bytes with bit 7 set, the original's
alternative carry path), blocks of 256 and 257 bytes (index wraps, small
next kick) and 255 bytes last. Equal on both programs: the whole 64 KiB
RAM image afterwards, the sequence of all SPC700 port writes (values and
ports; 594 in (a), 1041 handshake steps in (b)), A, X, Y, SP and PSW at
every entry point (C = 0 and C = 1 cases). `ctest -R
snes_audio_ipl_vs_dump` runs this when `tests/data/spc700.rom` (local, not
distributed) exists and skips otherwise.

Timing, from the two listings (clocks are SPC700 clocks):

| Step | Original | MAMR |
|---|---|---|
| clear loop ($FFC0 to the first ready write) | 2394 | 2394 |
| ready: $AA / $BB written after the clear | +4 / +9 | +7 / +8 |
| $CC poll period | 9 | 7 |
| CC sampled to acknowledge | 26 | 22 |
| command: start of the command code to the acknowledge | 18 | 19 |
| index poll period (waiting for the next byte) | 11 | 9 |
| per byte (data available, acknowledged, stored, back) | 25 | 27 |
| index seen to acknowledge | 11 | 11 |
| page carry, destination page < $80 / >= $80 | 8 / 13 | 8 / 8 |
| block end: first look at the kick to its acknowledge | 32 | 30 |
| command code to the entry point (command 0) | 31 | 30 |

The acknowledges come at the same time or earlier; the byte loop needs
two clocks more before it looks for the next index (two index registers
instead of one), so an uploader that is faster than the loop takes up to
8 percent longer for a large block (the test bounds this at 9 percent;
measured 5.7 and 7.1 percent in the two scenarios). An uploader that does
not wait for the acknowledges and sends bytes closer than 27 clocks apart
would work with the original (25) but not with MAMR's program; none is
known, the protocol's own acknowledge exists for this. The original reads
port 0 a second time before it accepts a new kick; MAMR's program decides
on the first read. The outcome differs only if the 65816 changes $2140
again within a few SPC700 clocks of writing a kick, which no uploader that
waits for the acknowledge does. Consequence for oracle work: MAMR with its
own IPL is not clock-identical to an emulator running Sony's ROM after the
first handshake; for per-frame hash comparisons against ares or MesenCE
run MAMR with the user dump.

## 5. S-DSP

The DSP (`runtime/snes/snes_dsp.cpp`) is written from fullsnes and the
SNESdev wiki only. No emulator's DSP source was read for it; ares served
as a black-box oracle (its PCM output and register state, section 8).
Where the documents leave a detail open or contradict the measured
behaviour, the rule below says so and gives the reading MAMR uses.

### 5.1 Pipeline

One output sample takes 32 steps; one step is 24 clocks of the 24.576 MHz
crystal, i.e. one SPC700 clock, so the sample rate is 32 kHz (32.04 kHz
in the measured mode). The DSP runs a step plan of 32 rows built from the
access chart in `[FS Low Level Timings]`: plan row s is the chart's
T(s+1), and each row lists the jobs whose register and RAM accesses the
chart puts there. A job does the computation that needs its access.

| Job (voice v) | Accesses | Work |
|---|---|---|
| Source | VxSRCN | latch the source number |
| DirEntry | RAM DIR entry, VxADSR1, VxPITCHL | entry address DIR * $100 + SRCN * 4 from the DIR latch of that moment; start address on the first start-up sample, loop address otherwise |
| PitchHigh | VxPITCHH | latch 6 bits |
| BrrHeader | RAM header, first data byte | latch the current block's header and the pair's first byte |
| Envelope | VxADSR2 or VxGAIN, FLG.7 | pitch step with PMON, key-on start-up, sample (Gauss or noise) times level, OUTX/ENVX values, release and key events, envelope |
| BrrData | RAM second data byte, VxVOLL | decode, pair and block advance, pitch counter, left mix |
| VolumeRight | VxVOLR | right mix, end-of-block event (the voice's ENDX bit) |
| StoreEndx, StoreOutx, StoreEnvx | ENDX, VxOUTX, VxENVX | register updates |

| Row | Jobs | Row | Jobs |
|---|---|---|---|
| 0 | VolumeRight 0, DirEntry 1 | 16 | StoreEnvx 4, PitchHigh/BrrHeader/Envelope 6 |
| 1 | PitchHigh/BrrHeader/Envelope 1 | 17 | Source 0, StoreEndx 5, BrrData 6 |
| 2 | StoreEndx 0, BrrData 1, Source 3 | 18 | StoreOutx 5, VolumeRight 6, DirEntry 7 |
| 3 | StoreOutx 0, VolumeRight 1, DirEntry 2 | 19 | StoreEnvx 5, PitchHigh/BrrHeader/Envelope 7 |
| 4 | StoreEnvx 0, PitchHigh/BrrHeader/Envelope 2 | 20 | Source 1, StoreEndx 6, BrrData 7 |
| 5 | StoreEndx 1, BrrData 2, Source 4 | 21 | StoreOutx 6, VolumeRight 7, DirEntry 0 |
| 6 | StoreOutx 1, VolumeRight 2, DirEntry 3 | 22 | PitchHigh 0, StoreEnvx 6, echo left in, FIR0 |
| 7 | StoreEnvx 1, PitchHigh/BrrHeader/Envelope 3 | 23 | StoreEndx 7, echo right in, FIR1-2 |
| 8 | StoreEndx 2, BrrData 3, Source 5 | 24 | StoreOutx 7, FIR3-5 |
| 9 | StoreOutx 2, VolumeRight 3, DirEntry 4 | 25 | BrrHeader 0, StoreEnvx 7, FIR6-7 |
| 10 | StoreEnvx 2, PitchHigh/BrrHeader/Envelope 4 | 26 | left output, echo feedback (MVOLL, EVOLL, EFB) |
| 11 | StoreEndx 3, BrrData 4, Source 6 | 27 | PMON latch, right output and frame (MVOLR, EVOLR) |
| 12 | StoreOutx 3, VolumeRight 4, DirEntry 5 | 28 | NON, EON, DIR latches, FLG.5 |
| 13 | StoreEnvx 3, PitchHigh/BrrHeader/Envelope 5 | 29 | echo left out, EDL, ESA, FLG.5, sample-pair turnover |
| 14 | StoreEndx 4, BrrData 5, Source 7 | 30 | KOFF/KON poll, rate counter, noise; Envelope 0; echo right out |
| 15 | StoreOutx 4, VolumeRight 5, DirEntry 6 | 31 | BrrData 0, Source 2 |

Within a row the jobs run in the listed order (only row 30 depends on it:
the poll and the counter come before voice 0's envelope). Voice 0's work
is spread around the echo reads (rows 21, 22, 25, 30, 31, 0), as in the
chart. PMON is latched with bit 0 forced to 0 (voice 0 cannot be
modulated).

**Where the chart and the measurement differ.** The chart lists the ENVX
and OUTX register accesses of voice v in T(3v+2) and T(3v+3) and the ENDX
bit in T(3v+1). Against ares on the target game (section 8) the register
contents only agree when ENDX, OUTX and ENVX are updated two, three and
four rows after the voice's VolumeRight row (StoreEndx/StoreOutx/StoreEnvx
in the table). With the chart's slots taken literally, the dsp field of
the hash lines differs from aresref in 115 of 1400 frames of the target
game (from frame 395 on); with the measured rows only in the 7 frames
that follow the CPU-side timing differences after frame 1324. The chart
says what the chip accesses in a slot, not when a value becomes visible
to the SPC700; MAMR takes the measured timing. The voice's ENDX bit
itself is set by the end-of-block event in VolumeRight.

### 5.2 BRR decoding

`[FS BRR Samples]`. Block = header (shift bits 7-4, filter 3-2, end/loop
1-0) + 8 bytes = 16 nibbles, high nibble first. Per nibble n (-8..7):

```text
s = (n << shift) >> 1                 shift 0..12
s = ((n >> 3) << 12) >> 1             shift 13..15 (-$800 or 0)
filter 1: s += old + ((-old) >> 4)
filter 2: s += old*2 + ((-old*3) >> 5) - older + (older >> 4)
filter 3: s += old*2 + ((-old*13) >> 6) - older + ((older*3) >> 4)
s = clamp to -$8000..$7FFF, then keep 15 bits signed (bit 14 is the sign)
```

old/older are the previous two decoded 15-bit samples. Four samples (one
byte pair) are decoded in BrrData when the pitch counter has reached
$4000. When the last pair of a block is done, end code bit 0 (codes 1 and
3) continues at the loop address and raises the voice's end event (its
ENDX bit, set in VolumeRight), other codes continue 9 bytes on. Code 1
additionally forces release with level 0 in every Envelope job that sees
the code-1 header, from the second start-up sample on (the first one
still holds the previous block's header). The decoder keeps running in
release and for noise voices.

### 5.3 Pitch and Gaussian interpolation

`[FS BRR Pitch]`. Pitch counter: `counter = (counter & $3FFF) + step`,
limited to $7FFF, in BrrData after the interpolation; step = PITCH (14
bits), with PMON bit x (x >= 1): `step += ((out(x-1) >> 4) * step) >> 10`
(out is the previous voice's 15-bit output of this sample). Bits 14-12
select the window start in the 12-sample ring, bits 11-4 the
interpolation index i:

```text
out =       (g[$0FF-i] * oldest) >> 10
out = out + (g[$1FF-i] * older)  >> 10
out = out + (g[$100+i] * old)    >> 10
out = (int16) out                          16-bit wrap
out = out + (g[$000+i] * new)    >> 10
out = clamp16(out) >> 1                    15-bit result
```

The table is generated at start from a closed formula, a
Blackman-windowed sinc: for n = 0..511, k = n + 0.5:
`r(n) = sin(pi*k*1.28/1024)/k * (0.42 + 0.5 cos(2 pi k/1023) + 0.08
cos(4 pi k/1023))`, stored at entry 511 - n; each tap group {i, 255-i,
256+i, 511-i} is scaled to sum 2048 and rounded (x + 0.5, truncated). The
formula is a mathematical description of the measured table (it was
first noted in ares' sources, ISC); the values are checked against the
table printed in fullsnes, 512 of 512 identical (rows 0, 1, 15, 16, 30
and 31 are unit-tested). No value lies closer than 3e-5 to a rounding
boundary, so the result does not depend on the platform's sin/cos or on
compiler flags. The tap sum $801 overflows for full-scale input: three
-8 << 12 samples give +$3FF8 for some indices, as fullsnes describes
(tested).

### 5.4 Envelope

`[FS ADSR/Gain Envelope]`, `[SD DSP envelopes]`. In every Envelope job
the next level is computed; it is stored only when the global rate
counter hits the mode's rate. Release ignores the rate.

| Mode | Rate | Step |
|---|---|---|
| attack (ADSR) | A*2+1 | +32, or +1024 at rate 31 |
| decay (ADSR) | D*2+16 | -1, then -(level >> 8) |
| sustain (ADSR) | SR | -1, then -(level >> 8) |
| release | every sample | -8, floor 0 |
| GAIN direct (bit 7 = 0) | 31 | level = value * 16 |
| GAIN 4 linear decrease | bits 4-0 | -32 |
| GAIN 5 exponential decrease | bits 4-0 | -1, then -(level >> 8) |
| GAIN 6 linear increase | bits 4-0 | +32 |
| GAIN 7 bent increase | bits 4-0 | +32 while the previous sample's next level, cut to 11 bits, is below $600, else +8 |

Phase changes are evaluated on the next level every sample, whether the
rate hits or not, in GAIN mode as well: attack becomes decay when the
next level, taken as unsigned, exceeds $7FF (a negative next level, e.g.
a linear decrease from 0, counts as above); decay becomes sustain when
the unclipped next level >> 8 equals the boundary, bits 7-5 of the
register read in the Envelope job (ADSR2, or GAIN in GAIN mode: the
garbage boundary fullsnes documents). Stored levels are clipped to
0..$7FF.

Key-on (fullsnes "KON"): level 0, attack, the voice's ENDX bit cleared,
and the bent-line memory (the previous next level) set to 0. Five start-up
samples follow: the first moves to the start address of the DIR entry,
the second to fourth decode one byte pair each, the pitch counter stays
at 0, the output is 0 (level 0). The envelope is first updated in the
fifth start-up sample. An end-of-block event in the sample that keys the
voice on does not set its ENDX bit. KOFF and FLG bit 7 switch to release;
FLG bit 7 and end code 1 also set the level to 0.

Rate counter: starts at 0, counts down once per sample (row 30), wraps
from 0 to 30719 (30720 = $7800, a multiple of every period). Rate r fires
when `(counter + offset(r)) % period(r) == 0`:

| r | period | r | period | r | period | r | period |
|---|---|---|---|---|---|---|---|
| 0 | never | 8 | 384 | 16 | 64 | 24 | 10 |
| 1 | 2048 | 9 | 320 | 17 | 48 | 25 | 8 |
| 2 | 1536 | 10 | 256 | 18 | 40 | 26 | 6 |
| 3 | 1280 | 11 | 192 | 19 | 32 | 27 | 5 |
| 4 | 1024 | 12 | 160 | 20 | 24 | 28 | 4 |
| 5 | 768 | 13 | 128 | 21 | 20 | 29 | 3 |
| 6 | 640 | 14 | 96 | 22 | 16 | 30 | 2 |
| 7 | 512 | 15 | 80 | 23 | 12 | 31 | 1 |

offset(r) = 0 for r mod 3 = 1, 1040 for r mod 3 = 2, 536 for r mod 3 = 0
`[SD DSP envelopes]`. Noise uses the same counter with the FLG rate.

### 5.5 Noise, output, mixer

Noise `[FS Control Registers]`: 15-bit LFSR, start $4000,
`level = (level >> 1) | ((bit0 ^ bit1) << 14)` at the FLG rate (row 30,
after the counter); a voice with its NON bit outputs the LFSR value
(15-bit signed) instead of the interpolated sample, the BRR decoder keeps
running.

Voice output: `out = (sample * level) >> 11` (15-bit); OUTX = out >> 7,
ENVX = level >> 4 (both taken in the Envelope job before the release and
key events, stored by StoreOutx/StoreEnvx).

Mixer `[FS Volume Registers]`: per voice and channel
`amp = (out * VxVOL) >> 6`, added to the main sum and, with the voice's
EON bit, to the echo sum, each addition saturated to 16 bits. Output
(row 26 for left, 27 for right):
`(int16)((main * MVOL) >> 7) + (int16)((fir * EVOL) >> 7)`, saturated. FLG
bit 6 mutes the amplifier: the frame is zeroed as it leaves the chip in
row 27, both channels by the FLG value of that moment (a FLG write between
rows 26 and 27 must not mute only one channel). fullsnes lists a final
phase inversion by the analogue post-amplifier; it is outside the chip
and not applied.

### 5.6 Echo

`[FS Echo Registers]`. Buffer at ESA * $100, EDL * 2 KiB (EDL 0 = 4 bytes),
4 bytes per sample (left, right, 16-bit each).

- Row 22: history position + 1; echo address = latched ESA * $100 +
  index; read left (RAM value >> 1 into the history); FIR0 tap for both
  channels. Row 23: read right; FIR1, FIR2. Row 24: FIR3..5.
- Row 25: FIR6, then `s = (int16)(sum of taps 0..6) + (int16) tap7;
  s = clamp16(s) & ~1`. Tap i = `(history[pos + i + 1] * FIRi) >> 6`:
  FIR0 on the oldest, FIR7 on the newest entry. The first seven additions
  wrap; tap 7 is itself a 16-bit value (FIR7 = -128 on -$4000 gives
  -$8000, the multiply overflow fullsnes warns about), the last addition
  saturates.
- Row 26: echo input = `clamp16(echo_sum + (int16)((fir * EFB) >> 7)) & ~1`,
  in the same accumulator as the voice sum.
- Row 28: latch FLG bit 5 (echo writes off).
- Row 29: latch ESA; when the index is 0 take the size from EDL; index
  += 4, back to 0 at the size; write left (unless the latch says off),
  clear the left accumulator; latch FLG bit 5 again.
- Row 30: write right, clear the right accumulator.

So a new ESA takes effect one sample late for writes, a new EDL only when
the index wraps (up to 240 ms), as fullsnes describes.

### 5.7 Register file

The 128 registers are a RAM-like array; $80-$FF read as mirrors and ignore
writes. Special cases:

- KON: a write replaces the pending KON bits; the poll (row 30 of every
  other sample) takes them. When the next sample pair begins (row 29), the
  bits taken at the last poll leave the pending value. So two quick writes
  usually leave only the second (fullsnes), and a voice's bit written
  again within the two samples after its poll is lost (measured against
  ares; a voice keyed twice in that window starts once).
- KOFF is taken from the register at every poll.
- ENDX: any write clears all eight bits; StoreEndx writes each voice's
  bit from its end state.
- ENVX/OUTX: plain writes, overwritten at the voice's next StoreEnvx /
  StoreOutx (fullsnes: "overwritten at 32000 Hz").
- FLG is also kept as an internal copy that resets to $E0 (soft reset,
  mute, echo writes off, noise off) while the array reads back the
  power-on fill `[FS DSP Registers]`.

All other registers are read by the job whose access the plan lists.

## 6. Host output stage

`AudioOut` (snes_audio_out.h): the DSP fills a 32 kHz ring (8192 frames,
oldest dropped on overflow). The host thread drains it into the resampler:
cubic Hermite (Catmull-Rom) interpolation, step = DSP rate / host rate,
scaled by `1 + max_delta * (2 * fill / capacity - 1)` with max_delta 0.5
percent, so a filling FIFO slows production and an emptying one speeds it
up. The audio callback only calls `pull()`; underruns repeat the last
frame. With max_delta 0 the ratio is fixed (spcplay `--rate`).

## 7. .spc snapshots

Layout: signature, PC at $25 (LE16), A, X, Y, PSW, SP at $27-$2B, optional
ID666 text tag at $2E, 64 KiB RAM at $100, 128 DSP registers at $10100,
the 64 RAM bytes hidden under the IPL at $101C0. Loading (spc_load): power
on, RAM, then the hidden bytes to $FFC0-$FFFF (the IPL overlays them when
CONTROL bit 7 is set), I/O registers from the RAM image at $F0-$FF
(CONTROL, DSPADDR, timer enables, targets and outputs, $F8/$F9; the port
bytes serve both directions because the file keeps no 65816 writes), the
DSP registers through the normal write path except that KON does not key
voices on again and ENDX is restored as stored, the SPC700 registers.
Voices start silent; the snapshot's driver keys them on again.

## 8. Verification

Unit tests (tests/snes-audio, no data files): timers, ports, RAM under
I/O, IPL overlay, catch-up, DSP phase; IPL protocol and re-entry; BRR
vectors, Gaussian rows and overflow, rate table, ADSR/release, KON
polling, ENDX, noise, a square tone with exact plateau values, echo FIR
impulse response, echo write-back, echo voice input; .spc round trip, IPL
in a snapshot, resampler. Fault injection (removing the probe, shifting
the port sampling point, removing the DSP lead) turns the respective tests
red.

External oracle: a small harness on top of the ares core (not part of the
repository) loads an .spc file into ares' SMP and DSP at power-on and
records the DSP's output samples before ares' own resampler, plus every
$F3 write with its clock. Test files were generated by a script: four
hand-written programs (square tone; BRR chain over all shifts and filters
with fractional pitch, ADSR, KON/KOFF on timer ticks, pitch sweep and GAIN
mode changes; echo with the "bugged" FIR example from fullsnes, negative
EVOL, noise rate sweep and PMON; KON/KOFF races, soft reset, mute, ENDX
and ENVX/OUTX writes) and 128 random register streams (about 4000 to
6000 random DSP register writes each at random 64 kHz timer intervals,
random BRR data and DIR tables, echo buffers overlapping the samples).
Result for the DSP written from the documentation: the PCM is identical
sample for sample in all 132 files (30 s for the hand-written ones, 10 s
for the random ones, about 45 million stereo frames), and the DSP
register write streams are identical in value, order and SPC700 clock
(ares stamps the end of the cycle, MAMR its start: a constant 1; two
random files differ in their write streams for an S-SMP reason that
predates the rewrite, their PCM is identical).

Each rule of section 5 that the documents leave open was settled against
this corpus: the first sample of a mismatch was traced through the
voice and echo state (and, where needed, through the public `voice()`
state of the previous implementation run as a black box) until one
documented reading explained it. The full system confirms it: the
target game (LoROM, PAL) against aresref over 1400 frames agrees in the
dsp, aram, smp and apuio fields in every frame up to 1324 (afterwards the
known CPU-side HDMA jitter moves the SPC700 handshake), and MAMR with the
rewritten DSP is byte-identical in every hash field to MAMR before the
rewrite over 6000 frames of that game and 6000 frames of a HiROM game.

In the tree: `tests/snes-audio/oracle/spcgen.py` regenerates the four
hand-written programs and eight random streams byte for byte (own SPC700
mini assembler, fixed xorshift generator, so the files do not depend on
the machine or the Python version); `pcm_crc.txt` holds the CRC-32 of the
first 5 s of ares' PCM for each, and `ctest -R snes_audio_pcm_vs_ares`
plays them through spcplay and compares (about 2 s; skipped without
Python). All twelve were checked against ares for 10 s each. This test
catches DSP faults the unit tests miss (a PMON shift of 5 instead of 4, a
wrapping instead of saturating last FIR tap: 8 of 12 files red).

Not yet run: blargg's SPC test ROMs (spc_smp, spc_timer, spc_dsp6,
spc_mem_access_times) need the 65816 side (phase S5); the MiSTer core's
GHDL test bench for its SPC700/DSP RTL (`smpsim`) no longer matches the
RTL's current port list and was not adapted.

## 9. Where the sources differ, open points

- **Port read during a write from the other side (not modelled).**
  Anomie regs.txt ($2140, DOC): a read that coincides with an SPC700
  write returns the bitwise OR of the old and the new value;
  undisbeliever (smpspeed blog, 2025): a port read at the moment of a
  write returns corrupted data. No measurement of
  the window in which the two accesses collide exists (research package
  A, A16). MAMR does not model it, for three reasons. The two clocks are
  asynchronous (the S-CPU's crystal, the APU's resonator with its
  console-specific rate, section 3): "the same clock" is not defined on
  the hardware, only a collision window of unknown width. In the model
  every SPC700 port write has an exact time on the master clock (the end
  of its SPC700 clock, keyed as 2 * clock * den) and a 65816 read samples
  at one master clock (start + cost - 4); the read sees the write when
  the write's key is at or before the read's (the catch-up and probe of
  section 3), in stage S and in stage E alike (stage E keeps the S-SMP a
  port slave). Keys coincide only when the master clock is a multiple of
  the fraction's denominator (every 7159091 clocks at 32040 Hz NTSC), so
  an OR rule on exact equality would fire about three times a second at
  most and only when a write lands on that clock; a rule over a window
  would need the window measured first. ares does not model it either
  (`CPU::readAPU` synchronizes the SMP and returns `SMP::portRead`, the
  latch as it stands; the primary oracle), nor does MesenCE. Changing
  this without a measurement would only move MAMR away from the oracle;
  the PAL target game's 3000-frame equality (docs/snes-oracles.md) was
  not put at risk. Test setup that would measure the window: the S-SMP
  writes $0F and $F0 alternately to $F4 in a tight loop while the S-CPU
  reads $2140 in a cycle-exact loop and counts values outside {$0F,
  $F0} ($FF for the OR rule); the clock spread (section 3) walks the
  phase through all offsets by itself; then the mirror image for $F4.
- **Timer enable and disable (decision open).** fullsnes ($F1 bits 0-2):
  "0=Disable, set TnOUT=0 & reload divider": a write of 0 clears the
  output and the divider. ares, LakeSnes and blargg's snes_spc clear on
  the 0->1 edge instead and leave a disabled timer's output readable.
  MAMR follows ares (oracle parity). Observable difference: reading
  $FD-$FF while the timer is disabled (fullsnes 0, ares the old value).
  Additionally ares' timer 2 clears on every CONTROL write that does not
  raise its enable bit (the condition is inverted against timers 0 and 1,
  `ares/sfc/smp/io.cpp`); MAMR uses one rule for all three. blargg's
  spc_timer test ROM is the arbiter once phase S5 can run it.
- **Timer phase.** fullsnes: timers advance in sync with DSP steps T1 and
  T17. MAMR and ares: edges after 128 (16) SPC700 clocks from power-on.
  The two descriptions differ at most by the unknown alignment of
  fullsnes' T numbering; not observable by software except against the
  DSP.
- **Stage-3 power-on value.** ares starts the timer outputs at 0, MesenCE
  at 15 (oracle pipeline findings); MAMR uses 0 (fill 00). DOC against
  DOC (the SNESdev wiki 0, Anomie $F), no measurement (CHOICE 0;
  docs/snes-hardware-spec.md section 5.2). blargg's
  `timer_at_power_reset`, named here before 2026-10-26, does not read
  the S-SMP at all (disassembled; it measures the CPU/PPU phase, 5.4).
- **TEST register.** Wait states (bits 4-7) and the crash bit are not
  modelled; the P-flag condition for TEST writes comes from ares only.
  Bit 1 (RAM write enable) blocks SPC700 writes only; fullsnes says it
  also blocks S-DSP writes (echo buffer). MAMR follows ares (decision
  open; no known software clears the bit).
- **Port read during a write.** fullsnes: if the SPC700 writes an output
  port while the 65816 reads it, the 65816 reads the OR of old and new
  value ("possibly" also the other way round). Not modelled (no emulator
  does; handshake drivers read twice).
- **Attack to decay threshold.** fullsnes: switch at level >= $7E0. MAMR,
  ares and blargg switch when the level passes $7FF (with +32 steps from
  $7E0 that is the very next step; with the +1024 step of rate 31 the two
  readings differ). Part of the DSP rewrite.
- **APU clock.** The system runs the ares convention (32040 Hz * 768)
  by default (docs/snes-architecture.md, decision of 2026-10-25); the
  `Smp` class and spcplay default to nominal. The DSP rate follows the
  clock (32.04 kHz) and the host resampler takes the actual rate.
- **Post-amplifier inversion** (fullsnes mixer notes) not applied, as in
  the emulators.
- **DSP: where fullsnes is not followed literally** (all decided by the
  measurement in section 8): the ENVX/OUTX/ENDX register update rows
  (section 5.1); ENDX is set when the block with an end code is finished,
  where fullsnes says "at the START of decoding the BRR block"; attack
  becomes decay when the next level exceeds $7FF, where fullsnes says
  "at Level>=7E0h" (with a negative next level counting as above, which
  also matches fullsnes' 11-bit reading: -32 cut to 11 bits is $7E0); the
  decay-to-sustain test uses the unclipped next level (fullsnes:
  "Level<=Boundary"); KON bits taken at a poll leave the pending value at
  the next sample pair, which fullsnes' "KON-changed" bit does not
  describe. Open in the documents and settled by the measurement: the
  envelope's first update in the last start-up sample, the key-on reset
  of the bent-line memory, the DIR entry address formed at the DIR access,
  the 16-bit FIR7 tap, the mute on the whole frame.
- **Probe and $F3.** An $F3 read after a write within the same probed
  instruction sees the DSP as of the start of that instruction; the
  catch-up then assumes the longest form (section 3).
