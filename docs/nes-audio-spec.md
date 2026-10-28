# NES Audio: APU Channels, Mixer and Output

Register-level specification of the sound side of the 2A03 as MAMR
implements it in phase N4 (docs/nes-architecture.md sections 5 and 8):
the two pulse channels with their envelopes and sweep units, the
triangle with its linear counter, the noise channel, the output side of
the DMC, the nonlinear mixer, and the output stage that turns the mixer
level into host samples. Model: `runtime/nes/nes_apu.{h,cpp}` (channels,
mixer, native samples) and `runtime/nes/nes_audio_out.{h,cpp}` (output
stage). The parts of the APU the CPU sees (frame counter and its IRQ,
length counters, $4015, the DMC's memory reader and its DMA) are phase N2
and stay in docs/nes-hardware-spec.md sections 3.8 and 6; this
specification refers to them and does not repeat them. It follows
docs/snes-audio-spec.md in structure.

The hardware described is the one of docs/nes-hardware-spec.md: an NTSC
NES with an RP2A03G. The PAL RP2A07 (phase P) is section 11.

**Sources:**

- **NESdev wiki** (www.nesdev.org/wiki, retrieved 2026-10-26 as wiki
  text): pages "APU", "APU Pulse" (with the sweep unit; "APU Sweep" is a
  redirect to it), "APU Envelope", "APU Triangle", "APU Noise", "APU DMC",
  "APU Mixer", "APU Length Counter", "APU Frame Counter", "CPU power up
  state". Cited as [WIKI page]. DOC unless a statement names a console
  measurement.
- **blargg's "NES APU Sound Hardware Reference"** (apu_ref.txt, linked
  from [WIKI "APU Mixer"] as the source of the mixer formulas, retrieved
  2026-10-26 from www.nesdev.org/apu_ref.txt). Its introduction states
  that it rests on the author's tests on a 1988 US NTSC NES with the G
  revision of the 2A03 and the NES-CPU-07 main board. Cited as
  [BLARGG-REF section].
  Its statements are results of the author's test programs on that
  console, without published logs (TEST-ROM-HW); the mixer formulas are
  the author's fit to measurements of the console's output (MEASURED,
  third party: the wiki points to "blargg's data and analysis" in nesdev
  forum post p=44255; the measurement data are not reproduced here).
- **blargg's APU test ROMs** (christopherpow/nes-test-roms, commit
  95d8f621ae55cee0d09b91519a8989ae0e64753b: apu_test, apu_reset,
  blargg_apu_2005.07.30, apu_mixer with the author's console recordings
  in apu_mixer_recordings, and dmc_tests without a readme). The
  collection has no licence: run locally, nothing of it enters the
  repository (docs/nes-test-evidence.md). Cited as [BLARGG-APU name].
- **AccuracyCoin** (MIT; docs/nes-test-evidence.md). Cited as [ACC test].
- **MesenCE 2.2.1** is the oracle of the comparison (section 10), used as
  a black box: its Lua state keys `apu.*` are read at the sampling point.
  Its source is not a template for anything here
  (docs/nes-architecture.md section 1); neither is MAME.

**Provenance classes** as in docs/nes-hardware-spec.md (DATASHEET, SIM,
MEASURED, TEST-ROM-HW, DOC, EMU-CONSENSUS, IMPL, INFERENCE, UNKNOWN,
CHOICE). Every statement below carries its class.

## 1. Time line

### 1.1 CPU cycles and APU cycles

- The APU runs on the CPU clock (1.789773 MHz NTSC, master clock / 12;
  DOC, docs/nes-hardware-spec.md section 3.7). An APU cycle is two CPU
  cycles, a get and a put half (DOC, [WIKI "APU Frame Counter"], [WIKI
  "DMA"]); which CPU cycles are get cycles is the power-on CHOICE of
  docs/nes-hardware-spec.md section 6.1.
- The triangle's timer is clocked every CPU cycle; the pulse, noise and
  DMC timers every APU cycle, "and thus produce only even periods" (DOC,
  [WIKI "APU"] "Glossary").
- The pulse and noise timers step at the start of the put cycles, as the
  DMC timer does (CHOICE: the wiki does not say which half; the half is
  not visible to a program, only to the phase of the output).

### 1.2 How MAMR runs the channels

The board calls `NesApu::tick(k)` at the start of every CPU cycle k (frame
counter, length counter updates, DMC timer); the waveform timers are not
stepped there. `NesApu::run_to(k)` brings them up to the start of cycle k:
it advances all timers over the cycles in which no timer expires in one
step and steps cycle by cycle only at expiries; the triangle's expiries
count as events only while its sequencer is gated on, otherwise its timer
is advanced in closed form. Every change of a channel's state calls
`run_to` first: a register write in cycle k (`run_to(k + 1)`, so the
write acts from cycle k + 1 on), a quarter or half frame clock and a
length counter update in cycle k (`run_to(k)`), a DMC output clock. The
result equals stepping every cycle (unit test `nes_audio`, "batches equal
cycles": the same random register program with `run_to` after every
cycle and only where needed gives identical samples and channel state).
This is a property of the implementation, not of the hardware.

The level of cycle k is the mixer output after the timer steps of cycle k
and before the register write of cycle k (CHOICE: the order of a write
against the waveform steps within one cycle is not visible to a program).

## 2. Envelope (pulse 1, pulse 2, noise)

DOC, [WIKI "APU Envelope"]; [BLARGG-REF "Envelope Generator"] agrees
(TEST-ROM-HW; it describes the start flag as "a write to the fourth
channel register since the last clock").

- Registers $4000, $4004, $400C: bit 5 the loop flag (also the length
  counter's halt), bit 4 the constant volume flag, bits 0-3 V (the
  constant volume and the divider's reload value; the divider's period is
  V + 1 quarter frames).
- A write to $4003, $4007 or $400F sets the start flag.
- At a quarter frame clock: with the start flag set, the start flag is
  cleared, the decay level is set to 15 and the divider to V. Otherwise the
  divider is clocked: at 0 it is reloaded with V and clocks the decay
  level, which counts down to 0 and, with the loop flag set, wraps from 0
  to 15; otherwise the divider counts down.
- Output: V with the constant volume flag set, the decay level otherwise.
  The decay level runs in both modes.
- The loop flag takes the written bit at once; the length counter's halt,
  the same bit, acts after the next cycle's length clock
  (docs/nes-hardware-spec.md section 6.3, TEST-ROM-HW). Whether the
  envelope sees the bit at once or with the length counter's delay is not
  stated (CHOICE: at once; visible only to a write in the cycle before a
  quarter frame clock that also changes the decay level from 0).

## 3. Pulse channels

### 3.1 Sequencer and duty

DOC, [WIKI "APU Pulse"] "Sequencer operation", "Duty Cycle Sequences".

- $4000/$4004 bits 6-7 select the duty. The output waveforms, step 0
  first: duty 0 `0 1 0 0 0 0 0 0` (12.5 %), 1 `0 1 1 0 0 0 0 0` (25 %), 2
  `0 1 1 1 1 0 0 0` (50 %), 3 `1 0 0 1 1 1 1 1` (25 % negated).
- The sequencer counts down from 0 and reads the lookup table (rows `0 0 0
  0 0 0 0 1`, `0 0 0 0 0 0 1 1`, `0 0 0 0 1 1 1 1`, `1 1 1 1 1 1 0 0`) at
  positions 0, 7, 6, ..., 1, which gives the waveforms above ([WIKI "APU
  Pulse"] "Implementation details", DOC).
- A write to $4003/$4007 restarts the sequencer at step 0 (DOC; [BLARGG-REF
  "Square Channel"]: "When the fourth register is written to, the
  sequencer is restarted", TEST-ROM-HW). Writing the duty does not move
  the sequencer ([BLARGG-REF]: "without resetting the position of the
  sequencer", TEST-ROM-HW).
- Some Famiclones swap duties 1 and 2 (DOC); not modelled.

### 3.2 Timer

- The period t (11 bits: $4002/$4006 low, bits 0-2 of $4003/$4007 high)
  plus one APU cycles between sequencer steps; the waveform repeats every
  16 (t + 1) CPU cycles (DOC). The timer counts t, t - 1, ..., 0 and steps
  the sequencer when it goes from 0 to t (DOC).
- A period write changes the reload value; the count in progress runs on
  and the new period starts at the next reload (DOC, [WIKI "APU"]: "doesn't
  take effect until that unit's next internal cycle begins").
- At power-on the timers are 0 (CHOICE; the registers are 0, [WIKI "CPU
  power up state"], DOC; the counter itself is not given).

### 3.3 Sweep unit

DOC, [WIKI "APU Pulse"] "Sweep control" and "Sweep unit operation".

- $4001/$4005: bit 7 enable, bits 4-6 the divider period P (P + 1 half
  frames), bit 3 negate, bits 0-2 the shift count S. A write sets the
  reload flag.
- Target period: change = period >> S; without negate target = period +
  change; with negate pulse 1 adds the ones' complement (target = period
  - change - 1) and pulse 2 the two's complement (target = period -
  change); a negative sum is 0. The wiki's example: making 20 negative
  gives -21 on pulse 1 and -20 on pulse 2 (unit test).
- Muting: a target above $7FF silences the channel whether the sweep is
  enabled or not (so with S = 0 and negate clear any period of $400 or
  more mutes; programs write $08 to disable it), and a period below 8
  silences it (DOC).
- At a half frame clock: if the divider is 0, the sweep is enabled, S is
  not 0 and the sweep unit is not muting, the period becomes the target;
  then, if the divider is 0 or the reload flag is set, the divider is
  loaded with P and the reload flag cleared, otherwise the divider counts
  down (DOC).
- "Not muting" in the update rule: the wiki lists the target above $7FF
  under the sweep unit and the period below 8 under the mixer output.
  [BLARGG-REF "Sweep Unit"] names both: with a period below 8 or a shifter
  result above $7FF the channel's DAC gets 0 and the sweep unit leaves the
  period unchanged (TEST-ROM-HW). MAMR blocks the update in both cases.
- The order within a half frame clock: the wiki updates on a divider of 0
  and then reloads it (above); [BLARGG-REF] clocks the divider first and
  resets it afterwards when $4001 was written since the last clock, with
  the divider's period P + 1. Both give an update every P + 1 half frames;
  they can differ in the first clock after a write. MAMR follows the wiki,
  the newer text (DOC).
- The divider at power-on is 0 (CHOICE; UNKNOWN on the hardware; the
  first $4001 write sets the reload flag and makes it defined).

### 3.4 Output

The channel sends its envelope output (section 2) to the mixer, and 0
when the sequencer's output is 0, the sweep unit mutes (section 3.3), the
length counter is 0 or the period is below 8 (DOC, [WIKI "APU Pulse"]
"Mixer output").

## 4. Triangle

### 4.1 Sequencer and timer

DOC, [WIKI "APU Triangle"]; [BLARGG-REF "Triangle Channel"] agrees
(TEST-ROM-HW).

- The 32-step sequence 15, 14, ..., 1, 0, 0, 1, ..., 14, 15.
- The timer counts CPU cycles: period t (11 bits, $400A and bits 0-2 of
  $400B) plus one; f = CPU clock / (32 (t + 1)).
- The timer always runs; its expiry steps the sequencer only while the
  linear counter and the length counter are both nonzero. Halting holds
  the current step: the output stays at its level, it does not drop to 0
  (DOC, [WIKI "APU Triangle"] "Halting triangle").
- At power-on MAMR starts at step 0 (output 15; CHOICE: [WIKI "CPU power
  up state"] gives "?" for the phase at power-on). The held 15 is a DC
  level that the output stage's high-pass filters remove after power-on.

### 4.2 Linear counter

DOC, [WIKI "APU Triangle"]; [BLARGG-REF "Linear Counter"] agrees
(TEST-ROM-HW).

- $4008: bit 7 the control flag (also the length counter's halt), bits
  0-6 the reload value. A write to $400B sets the reload flag.
- At a quarter frame clock: with the reload flag set the counter is
  loaded with the reload value, otherwise a nonzero counter counts down;
  then, if the control flag is clear, the reload flag is cleared.
- The control flag takes the written bit at once (CHOICE, as the envelope
  loop flag in section 2).

### 4.3 Ultrasonic periods

At periods 0 and 1 the sequence repeats at 55.9 kHz and 28 kHz. [WIKI
"APU Triangle"]: "Due to external filtering, ultrasonic frequencies are
averaged into constant output at roughly half amplitude" (DOC);
[BLARGG-REF]: "the DAC effectively outputs a value half way between 7 and
8" (TEST-ROM-HW). Games that "silence" the triangle this way make an
audible pop at the transition (DOC). MAMR has no special case: the steps
run at their rate on the CPU time line and the output stage averages them
(unit test: the native samples of a round at period 0 lie between the
mixer levels of 7 and 8).

## 5. Noise

DOC, [WIKI "APU Noise"]; [BLARGG-REF "Noise Channel"] agrees for the
shift register (TEST-ROM-HW).

- $400C: envelope as in section 2. $400E: bit 7 the mode flag, bits 0-3
  the period index. $400F: bits 3-7 the length counter load; the write
  restarts the envelope.
- Periods in CPU cycles (NTSC), index 0 to 15: 4, 8, 16, 32, 64, 96, 128,
  160, 202, 254, 380, 508, 762, 1016, 2034, 4068 (DOC; the timer counts
  APU cycles, so the reload value is half the table value minus 1).
- The 15-bit shift register: at every timer expiry the feedback is bit 0
  XOR bit 6 (mode flag set) or bit 1 (clear), the register shifts right
  and the feedback enters bit 14. Mode 0 repeats after 32767 steps, mode 1
  after 93 or 31 steps depending on the state when the mode was set (DOC;
  unit test from the power-on value).
- Output: the envelope output, 0 while bit 0 of the register is set or
  the length counter is 0 (DOC). The register is clocked whether the
  channel is audible or not (DOC, the timer drives it directly).
- Power-on value: the sources differ. [WIKI "APU Noise"] and [BLARGG-REF
  "Noise Channel"]: "On power-up, the shift register is loaded with the
  value 1" (the reference lists the power-up state among its open
  points); [WIKI "CPU power up state"]: "$0000 (all 0s, first clock shifts
  in a 1)" with a forum log as its source. Both give $4000 after the first clock and differ only in
  bit 0 before it, which only a length counter loaded within the first
  4068 cycles could show. MAMR: 1 (CHOICE). Reset leaves it unchanged
  (DOC, [WIKI "APU Noise"]).
- The earliest 2A03 revisions have no mode flag and a period of 2046 at
  index 15 (DOC); not the target revision, not modelled.

## 6. DMC output

The memory reader, its DMA and the timer are docs/nes-hardware-spec.md
sections 3.8 and 6.4. The output side, DOC [WIKI "APU DMC"] and
[BLARGG-REF "Delta Modulation Channel (DMC)"] (TEST-ROM-HW):

- A 7-bit output level, sent to the mixer whether the channel is enabled
  or not (DOC).
- $4011 sets the level (bits 0-6) directly, also while a sample plays
  (DOC). [WIKI "APU DMC"] adds that a $4011 write in the same cycle as an
  output clock is "occasionally" not taken (DOC, a forum report); MAMR
  takes the write, which comes after the clock in the cycle (CHOICE; not
  modelled).
- At each output clock, unless the silence flag is set: bit 0 of the
  shift register 1 raises the level by 2 if it is below 126, 0 lowers it
  by 2 if it is above 1; so the level stays within 0..127 and never wraps
  (DOC). Then the shift register shifts right; after 8 bits a new cycle
  starts with the sample buffer, or silence when the buffer is empty
  (DOC).
- Rates: the NTSC table of docs/nes-hardware-spec.md section 6.4 (DOC;
  unit test: one level step every rate period).
- When the level changes relative to the timer count: MAMR clocks the
  output unit at the start of the put cycle after the timer was found at
  0, as of the preceding get cycle, so that a DMA read in that get cycle
  comes first (CHOICE of docs/nes-hardware-spec.md section 6.4). MesenCE
  shows the new level one APU cycle earlier relative to its timer (finding
  A1, section 10.2). The DMA timing, which programs can observe, is
  judged by AccuracyCoin and passes in MAMR; the level itself is not
  readable by a program. UNKNOWN on the hardware; setup in section 12.

## 7. Mixer

MEASURED (third party: blargg, [BLARGG-REF "DAC Output"], cited by [WIKI
"APU Mixer"] as the formula's source, with the author's data and analysis
in nesdev forum post p=44255):

```text
output    = pulse_out + tnd_out
pulse_out = 95.88 / (8128 / (pulse1 + pulse2) + 100)
tnd_out   = 159.79 / (1 / (triangle / 8227 + noise / 12241 + dmc / 22638) + 100)
```

with pulse1, pulse2, triangle, noise 0..15 and dmc 0..127; a group whose
inputs are all 0 contributes 0 (DOC, the reference: "When the
sub-denominator of a group is zero, its output is 0"). The output spans
0.0 to 1.0. The DACs' nonlinearity makes the DMC level act as a volume
control for triangle and noise (DOC, [WIKI "APU Mixer"]: Super Mario
Bros. and StarTropics use it).

MAMR evaluates the two formulas exactly in double once per input
combination (31 pulse sums, 16 x 16 x 128 tnd inputs) and keeps them as
fixed point with 1.0 = 2^20 (`NES_MIX_ONE`), rounded to nearest. The
wiki's lookup-table approximation (95.52 / (8128 / n + 100) and 163.67 /
(24329 / n + 100), within 4 percent) and its linear approximation are not
used. The level of every CPU cycle is the sum of the two table values
(unit test: values, zero groups, nonlinearity, monotony).

The hardware follows the DACs with analog filters (section 9). The 2A03's
two audio pins (pulses on one, triangle, noise and DMC on the other) are
mixed on the main board; the formulas describe the result at the NES's
output (MEASURED as above).

## 8. Power-on and reset

- Power-on: every register $4000-$4013 is 0 (DOC, [WIKI "CPU power up
  state"], measured on an NTSC front-loader with an RP2A03G); the channel
  enables of $4015 are clear (DOC, docs/nes-hardware-spec.md section
  6.3); the DMC level is 0 (DOC); the noise register 1 (section 5,
  CHOICE); the triangle at step 0 (section 4.1, CHOICE); all timers,
  dividers and the sequencer positions 0 (CHOICE).
- Reset: $4015 is cleared (the triangle's length counter keeps its value),
  $4017 is written again (docs/nes-hardware-spec.md sections 6.2 and 6.3,
  TEST-ROM-HW); the DMC level keeps bit 0 only ("[$4011] &= 1", DOC, [WIKI
  "CPU power up state"]); the triangle restarts at step 0 ("0 (output =
  15)", DOC, same page); the pulse, triangle and noise registers are
  "unchanged?" on that page and stay unchanged in MAMR (INFERENCE).

## 9. Output stage (host samples)

Not hardware; MAMR's way from the mixer level to the host
(`runtime/nes/nes_audio_out`, used by the machine adapter
runtime/machine/nes_game and by `nes_headless --wav`):

1. Native samples (in `NesApu`): the levels of 8 CPU cycles summed
   (`NES_AUDIO_DIV`), counted from power-on; one sample per 8 cycles,
   223,722 Hz NTSC. The sums are integers and exact; they are what the
   hash line's `snd` field covers (docs/nes-oracle-format.md).
2. Decimation by 5 (`NES_AUDIO_DECIMATE`): a low-pass FIR of 128 taps
   (Blackman-windowed sinc, cutoff 16 kHz, unit gain at DC) at the native
   rate, every fifth output kept: CPU clock / 40 = 44,744.3 Hz (CHOICE:
   pulses above the host's Nyquist frequency would otherwise alias).
3. The console's analog path as given for the NES: a first-order
   high-pass filter at 90 Hz, another at 440 Hz, a first-order low-pass
   filter at 14 kHz (DOC, [WIKI "APU Mixer"], with lidnariq's matching of
   the board's components to filters in the forum post the page links).
   The Famicom has only a first-order high-pass at 37 Hz plus its RF path
   (DOC); not modelled. One-pole filters, coefficient RC / (RC + dt) for
   the high-pass and dt / (RC + dt) for the low-pass, RC = 1 / (2 pi f).
4. Gain: mixer 1.0 = 65534 (`NES_AUDIO_GAIN`, twice the int16 range),
   clamped to int16 (CHOICE: after the high-pass filters games stay far
   below a swing of 0.5; Super Mario Bros. 3 peaks near 0.25, about 16,000
   of 32,767). The mono signal goes to both channels.

The machine's `audio()` is this stereo int16 at
`audio_rate_hz` = 236250000 / 5280 Hz; mamr_play resamples it to the
device rate with the rate control of docs/frontend.md section 5. The
stage's state (FIR history, phase, filter states) is part of the save
state, so a loaded state continues with the same samples.

## 10. Verification

### 10.1 Unit tests (no ROM), tests/nes/test_nes_audio.cpp

Pulse sequences for both channels and all four duties (steps, order, the
step length 2 (t + 1) at put cycles, the silence below period 8); sweep
targets (ones' and two's complement, the clamp at 0), mute conditions,
updates at the half frame clocks with the divider and reload flag, no
update with a muting target or S = 0; envelope (start, divider, decay,
loop, constant volume); the length table for all four counters; the
triangle's 32 steps, the step length t + 1, the linear counter with and
without the control flag, the held step, the ultrasonic average; the
noise periods for all 16 indices, the LFSR lengths 32767 and 31/93, the
output gate; the DMC level steps with the limits 126 and 1 and the rate;
the mixer values; the batched run against the run cycle by cycle; the
reset; the output stage (FIR gain, DC removal, sample count, level).

### 10.2 Against MesenCE (the apu field)

The hash line's `apu` field (docs/nes-oracle-format.md section 3) holds
the channel state that MesenCE exposes to Lua; `snd` (the samples) MesenCE
cannot give. Results 2026-10-26:

- Super Mario Bros. 3, 3000 frames without input: apu equal in every
  frame. The game makes no sound without input, so this shows only the
  idle state.
- Super Mario Bros. 3 with tools/oracle/nes/inputs/smb3-1-1.txt, not published (title,
  map, World 1-1; the map and level tunes and the effects): apu equal in
  frames 1 to 528. From frame 529 the games differ by finding S1
  (docs/nes-oracles.md section 6: the NMI after a taken branch moves the
  input by a strobe from frame 380, so Mario acts at other frames and
  other effects play). With MesenCE's NMI rule switched on locally in
  MAMR (a temporary diagnostic change) the games run alike for 3000
  frames and apu is equal in 2990 of them. The other 10 (frames 790, 792,
  794, 1114, 1118, 1442, 1749, 2181, 2469, 2901) are finding A1: a DMC
  sample plays, both sides are in the same cycle with the same bytes
  remaining, and MesenCE's level is one delta step (2) ahead or its
  sample buffer already refilled, because it clocks the output unit one
  APU cycle earlier relative to its timer (MesenCE's timer reads 0 with
  the step done; MAMR's timer reads 0 with the step still due). A
  second diagnostic (MAMR taking the DMC period at once instead of one
  APU cycle after the reload) changed nothing, so the reload rule of
  [ACC "DMC Reload Timing"] is not the cause.
- blargg's dmc_tests (4 ROMs, 120 frames) and apu_mixer (4 ROMs, to
  their end): every field including apu equal in every frame.
- AccuracyCoin, the 300 frames of the reference file: apu equal (ctest
  `nes_mamr_reference_accuracycoin` requires it).

### 10.3 Hardware

blargg's suites and apu_mixer against the console recordings:
docs/nes-test-evidence.md section 4.6.

## 11. PAL: the RP2A07 (phase P)

The RP2A07's APU is the 2A03's with other tables and another clock
(docs/nes-hardware-spec.md section 7.3, with the class of every number):

- Time line: the CPU cycle is 16 master clocks of 26.6017125 MHz
  (1,662,607 Hz); the APU cycle is two CPU cycles as on NTSC; get and put
  cycles as section 1.1 (INFERENCE).
- Frame counter: 4-step 8313, 16627, 24939, 33252-33254; 5-step 8313,
  16627, 24939, 41565, restart 41566 (DOC, TEST-ROM-HW [BLARGG-PAL]).
  The envelopes, the linear counter, the length counters and the sweep
  units are clocked by it exactly as in sections 2-4; their rates in
  time are 200 / 100 Hz instead of 240 / 120 Hz.
- Noise periods (CPU cycles): 4, 8, 14, 30, 60, 88, 118, 148, 188, 236,
  354, 472, 708, 944, 1890, 3778 (DOC [WIKI "APU Noise"]). The reload
  value is half the table value minus 1, as in section 5; all entries
  are even.
- DMC rates (CPU cycles): 398, 354, 316, 298, 276, 236, 210, 198, 176,
  148, 132, 118, 98, 78, 66, 50 (DOC [WIKI "APU DMC"]); $4 and $C are off
  the tuning of the others ([WIKI "Errata"], DOC), which is the chip.
  The DMC timer starts with the rate-0 period at power-on (398, CHOICE,
  the rule of the NTSC value).
- Pulse, triangle, envelope, sweep, length table and the mixer: as
  sections 2-7 (INFERENCE: no source names a difference; the length
  table is TEST-ROM-HW [BLARGG-PAL 02.len_table]).
- Native samples: the levels of 8 CPU cycles summed, as section 9:
  207,825.9 Hz on PAL; the hash line's snd field is these sums in both
  regions.
- Output stage: decimation by 5 to CPU clock / 40 = 41,565.2 Hz
  (26,601,712.5 / 640), the FIR cutoff 16 kHz below its Nyquist
  frequency of 20.8 kHz; the analog filters of section 9 with the same
  corner frequencies (INFERENCE: the PAL front-loader's audio path is
  not documented separately; the wiki's values are for "the NES"). The
  machine's `audio_rate_hz` is 53203425 / 1280 Hz.

Verification: unit tests (tests/nes/test_nes_audio.cpp) for the PAL
frame counter steps, the noise periods and the DMC rates; blargg's
pal_apu_tests (10 ROMs, local) in MAMR (docs/nes-test-evidence.md
section 4.7); the apu field against MesenCE in PAL mode on Super Mario
Bros. 3 Europe (docs/nes-oracles.md section 8).

## 12. Where the sources differ, open points

| Question | Sources | MAMR | Class | Setup that would settle it |
|---|---|---|---|---|
| Sweep update with a period below 8 | [WIKI] names the muting sweep unit in the update rule and the period below 8 under the output; [BLARGG-REF] names both conditions | no update in both cases | TEST-ROM-HW ([BLARGG-REF]) | settled by the reference; a check: period 4, sweep add with S = 1, P = 0, and listen or scope the pulse pin for a tone that must not appear |
| Divider order in the half frame clock | [WIKI]: update on 0, then reload; [BLARGG-REF]: clock first, then reset after a write | the wiki's order | DOC | a test ROM that writes $4001 at known distances before a half frame clock and hears (or scopes) when the first period change comes |
| Noise register at power-on | [WIKI "APU Noise"] and [BLARGG-REF] 1; [WIKI "CPU power up state"] 0 with the first clock shifting in 1 | 1 | CHOICE | not needed: equal from the first clock on |
| DMC level change against the timer (A1) | none; MesenCE one APU cycle earlier | after the DMA read of the get cycle | CHOICE / UNKNOWN | oscilloscope on the 2A03's second audio pin and M2: a looping sample of alternating bits at rate $F, the level steps counted in M2 cycles from a $4015 write; or AccuracyCoin-style: no program can read the level |
| $4011 write meeting an output clock | [WIKI "APU DMC"]: occasionally ignored (forum report) | the write wins | CHOICE | scope as above with $4011 writes swept across the clock |
| Envelope loop and linear control flag timing | the length halt has a one-cycle delay (TEST-ROM-HW); the other uses of the bit are not stated | at once | CHOICE | a test ROM that writes the bit in the cycle before a quarter frame clock and reads the effect through the length counter of another channel cannot see it; needs the analog output |
| Get or put half of the pulse and noise timers | not stated | put | CHOICE | not visible to programs; phase of the analog output against M2 |
| Duty swap on Famiclones | [WIKI] | not modelled | DOC | not the target hardware |
