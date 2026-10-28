# MAMR: Multiple Arcade Machine Recompiler

## Project Idea

**MAMR** investigates the static recompilation of **SNK Ikari Warriors (1986)** from the original arcade hardware to a modern native PC build.

The goal is **not** to run the game through a full emulator such as MAME. Instead, the original Z80 machine code from the arcade ROMs is to be analyzed, statically translated into portable C/C++ code, and then compiled into native x86-64 code with a regular compiler.

Simplified:

```text
Ikari Warriors ROMs
        v
Z80 Static Analyzer
        v
Control-Flow / Basic Blocks
        v
portable C/C++ code
        v
Clang / GCC / MSVC
        v
native x86-64 code
```

The original SNK arcade hardware is not fully emulated; instead, it is replicated by a small, game-specific runtime layer.

---

## 1. Inspiration and Similar Projects

The basic principle of static recompilation is by now being used successfully by several projects.

### N64Recomp

N64Recomp analyzes MIPS code from Nintendo 64 ROMs and generates portable C code from it. This code is then compiled for modern platforms.

Key ideas for MAMR:

- static control-flow analysis
- basic block detection
- translation of individual CPU instructions to C
- handling of direct and indirect jumps
- use of a regular host compiler for x86-64 / ARM64

Project:
https://github.com/N64Recomp/N64Recomp

### NeoGeoRecomp

NeoGeoRecomp is probably the most important technical reference for MAMR.

It translates the Motorola 68000 code of Neo Geo games ahead of time into C. The Neo Geo hardware is provided separately by a runtime.

The verification mode is particularly interesting:

```text
identical CPU state
          |
    +-----+-----+
    v           v
Reference CPU   recompiled block
    |           |
    +-----+-----+
          v
       compare
```

CPU registers, flags, memory accesses, and other state changes are compared.

We should adopt this principle for Z80 code.

Project:
https://github.com/sp00nznet/neogeorecomp

### Daytona USA Static Recompilation

This project shows that static recompilation also works well on real arcade hardware.

The original arcade code is translated statically. The specific Sega Model 2 hardware is modeled separately in C++.

MAME can serve as a reference and test oracle.

Project:
https://github.com/alphanu1/daytona-arcade-recomp

### GB Recompiled

GB Recompiled is particularly interesting for us because the Game Boy CPU is closely related to the Z80.

Interesting approaches:

- ROM -> C
- control-flow detection
- interpreter fallback for unknown jump targets
- differential tests
- replay systems
- audio/frame capture for verification

Project:
https://github.com/arcanite24/gb-recompiled

### Other Interesting Projects

- SNESRecomp
- GBARecomp
- jamulator
- various static recompilation projects around PS1/N64

---

## 2. Ikari Warriors Arcade Hardware

Ikari Warriors is based on SNK hardware with several Z80 processors.

Roughly:

```text
Main Z80A       approx. 3.35 MHz
Sub Z80A        approx. 3.35 MHz
Sound Z80A      approx. 4.00 MHz

YM3526 OPL #1
YM3526 OPL #2

SNK video/sprite hardware
Palette
Rotary Controller
Hard Flags/collision hardware
```

This makes the hardware considerably more manageable than later console or 3D arcade systems.

That makes Ikari Warriors a good candidate for static recompilation in principle.

Important:

> The actual translation of individual Z80 instructions is probably not the hardest part.

The bigger challenge lies in:

- multi-CPU synchronization
- interrupts/NMIs
- memory-mapped I/O
- SNK-specific graphics logic
- Hard Flags/collision hardware
- sound timing
- indirect jumps
- correct cycle counting

---

## 3. Target Architecture

The software should consist of two major components:

```text
                 +---------------------+
ROMs ----------> | Z80 RECOMPILER      |
                 |                     |
                 | Decode              |
                 | Control Flow        |
                 | Basic Blocks        |
                 | C/C++ Generator     |
                 +---------+-----------+
                           |
                     generated C++
                           |
                           v
                      Clang/MSVC
                           |
                           v
                    native x86-64
                           |
          +----------------+----------------+
          |                                 |
          v                                 v
   recompiled                          MAMR
   game code                          RUNTIME
                                     |
                                     +- Memory Bus
                                     +- Scheduler
                                     +- Video
                                     +- Sprites
                                     +- Palette
                                     +- Hard Flags
                                     +- YM3526 x2
                                     +- Input
                                     +- SDL
```

### Difference from Classic Emulation

Classic emulation:

```text
read Z80 opcode
v
interpret opcode
v
update CPU state
v
read next opcode
v
...
```

MAMR:

```text
Z80 code
v
analyze once at build time
v
generate C/C++
v
compile to x86-64
v
native host CPU executes game code directly
```

The arcade hardware is still replicated by a runtime.

---

## 4. Why C/C++ as an Intermediate Stage

Emitting x86-64 machine code directly would be possible, but unnecessarily complicated for version 0.1.

Better:

```text
Z80
 v
our C/C++ generator
 v
Clang / GCC / MSVC
 v
x86-64 / ARM64
```

Advantages:

- much easier to debug
- platform-independent
- the host compiler takes care of optimization
- Windows/Linux/macOS possible later
- ARM64 possible without a new compiler backend
- easy comparison with reference implementations

LLVM can be added later as an optional backend.

---

## 5. Z80 Recompiler

The recompiler must handle the complete Z80 instruction set.

This includes:

```text
Normal Opcodes
CB xx
ED xx
DD xx
FD xx
DD CB xx xx
FD CB xx xx
```

CPU state to be modeled:

```text
AF
BC
DE
HL

AF'
BC'
DE'
HL'

IX
IY
SP
PC

I
R

IFF1
IFF2
Interrupt Mode
HALT
```

The exact Z80 flags are especially important.

Example:

Original:

```asm
LD A,(HL)
INC A
LD (HL),A
CP 10
JR NZ,$42AC
```

Possible generated form:

```cpp
A = read8(HL);

A = inc8(A, &F);

write8(HL, A);

cp8(A, 10, &F);

if (!(F & FLAG_Z))
    goto block_42AC;
```

The host compiler then turns this into native x86-64 code.

---

## 6. Code vs. Data Detection

A ROM does not consist exclusively of executable code.

Example:

```text
$0000 Code
$0172 Data
$0220 Code
$1740 Jump Table
$1800 Lookup Table
$1A00 Code
...
```

That is why you cannot simply disassemble the entire ROM linearly.

What is needed is a control-flow analyzer.

Starting points can be:

- Reset Vector
- IRQ Vector
- NMI Vector
- known entry points
- known callback addresses

The analyzer then follows:

- CALL
- JP
- JR
- conditional jumps

This produces a control-flow graph.

```text
              block_0120
                  |
             +----+----+
             v         v
        block_0143  block_0168
             |         |
             +----+----+
                  v
             block_0190
```

---

## 7. Indirect Jumps

Direct jumps are simple:

```asm
JP $3812
```

becomes:

```text
block_3812
```

Harder:

```asm
JP (HL)
```

Here the target may be statically unknown.

Possible solution:

```cpp
switch (HL) {
    case 0x1000: return block_1000(cpu);
    case 0x1052: return block_1052(cpu);
    case 0x1A73: return block_1A73(cpu);
}
```

Alternatively:

```cpp
dispatch[HL](cpu);
```

### Interpreter Fallback

For version 0.1, a fallback interpreter makes sense.

```text
unknown jump target
        v
Z80 Interpreter
        v
log target
        v
next build includes target statically
```

The end goal remains:

```text
100% static coverage
```

But during development, the interpreter fallback prevents individual unknown jump targets from blocking the entire project.

---

## 8. Multi-Z80 Scheduler

Ikari Warriors has three Z80 processors:

```text
CPU A
CPU B
Sound CPU
```

These should not simply run as three independent host threads.

That would make timing and reproducibility harder.

Instead, a deterministic scheduler should be used.

Example:

```text
CPU A   -> 200 cycles
CPU B   -> 200 cycles
Sound   -> 240 cycles

check events

CPU A   -> ...
CPU B   -> ...
Sound   -> ...
```

Every recompiled basic block returns the original Z80 cycles it consumed.

Example:

```cpp
return 73;
```

The scheduler then coordinates:

- CPU A
- CPU B
- Sound CPU
- NMI
- IRQ
- Video Timing
- YM3526 Timer
- Frame Events

---

## 9. Memory Bus

Initially, memory accesses should not go directly to host RAM.

Instead:

```cpp
read8(cpu, address)
write8(cpu, address, value)
```

Because an arcade address can represent various things:

```text
RAM
ROM
VRAM
Sprite RAM
Palette RAM
Input
Sound Command
NMI Trigger
Scroll Register
YM3526 Register
Hard Flags
```

Later, regular RAM accesses can be optimized as a fast path.

---

## 10. Hard Flags / Collision Hardware

Ikari Warriors has special hardware that MAME refers to as **Hard Flags**.

It appears to provide functions for bounds and collision checks.

Simplified:

```text
Z80
 |
 | write position / object values
 v
Hard Flags Hardware
 |
 | read flags / collision result
 v
Z80
```

This hardware has to be modeled separately in the runtime.

It is probably one of the more interesting and riskier parts of the project.

Important:

- use MAME as the reference
- compare against the MiSTer/FPGA implementation
- check behavior with traces
- make no unnecessary assumptions

---

## 11. Graphics

For version 0.1, a simple software renderer should be used.

Not:

```text
Vulkan
Direct3D 12
complicated GPU pipeline
```

But rather:

```text
SNK tile/sprite hardware
          v
Software Renderer
          v
indexed framebuffer
          v
SDL Texture
          v
PC
```

Things to model include:

- Text Layer
- Background Tiles
- 16x16 sprites
- 32x32 sprites
- Palette
- sprite priorities
- Scroll Register
- shadow/highlight effects
- layer order

Possible render order:

```text
Background
v
low-priority sprites
v
32x32 sprites
v
high-priority sprites
v
Text Layer
```

Possible later:

- Integer Scaling
- CRT Shader
- Scanlines
- Bezel
- Fullscreen
- modern controllers
- widescreen artwork

---

## 12. Sound

The sound architecture:

```text
recompiled sound Z80
        v
YM3526 #1 registers
YM3526 #2 registers
        v
OPL Emulation
        v
PCM
        v
SDL Audio
```

A good possible foundation is:

**ymfm**
https://github.com/aaronsgiles/ymfm

ymfm supports the YM3526 and can handle the FM synthesis.

We still have to model correctly:

- YM3526 register accesses
- Timer
- IRQ
- Sound Command Queue
- Sound CPU Busy State
- synchronization with the scheduler

---

## 13. Reference Z80 for Differential Tests

Although MAMR is a recompiler, a regular Z80 core should be integrated as a reference.

Not for running the final game, but for tests.

```text
identical input state
          |
    +-----+-----+
    v           v
Reference Z80   recompiled block
    |           |
    +-----+-----+
          v
     comparison
```

The following are compared:

```text
A / F
BC
DE
HL
IX / IY
SP
PC
alternate registers
I / R
IFF1 / IFF2
Memory Writes
I/O Writes
Cycles
```

Example error output:

```text
BLOCK $4712

expected F = A4
actual   F = 84

Memory writes: OK
Cycles: OK
Register mismatch: F
```

This makes it possible to pinpoint recompiler bugs exactly.

Possible Z80 reference cores:

- superzazu/z80
- kosarev/z80
- other tested Z80 cores

---

## 14. MAME as Test Oracle

MAME should not be used as the runtime.

It is, however, an excellent reference implementation.

Test principle:

```text
MAME
v
Boot
v
Coin
v
Start
v
deterministic input sequence
v
record frame state
```

To be recorded:

```text
CPU Register
RAM Hash
VRAM Hash
Sprite RAM Hash
Interrupts
Sound Commands
Frame Counter
```

Then:

```text
MAMR
v
same inputs
v
same checkpoints
v
compare
```

Example:

```text
Frame 1842
MAME RAM Hash   = 9A72...
MAMR            = 9A72...

Frame 1843
MAME RAM Hash   = 44F1...
MAMR            = 31B9...

-> the divergence lies between frame 1842 and 1843
```

This allows extremely targeted debugging.

---

## 15. MiSTer / FPGA as a Second Reference

Besides MAME, there is a MiSTer FPGA core for Ikari Warriors as well as a more general SNK Triple-Z80 core.

This is very valuable.

It gives us several independent references:

```text
Original PCB
   |
   +-- MAME
   |
   +-- MiSTer FPGA
```

If MAME and MiSTer implement the same hardware behavior differently, we can compare both approaches.

Projects:

https://github.com/MiSTer-devel/Arcade-IkariWarriors_MiSTer

https://github.com/MiSTer-devel/Arcade-SNK_TripleZ80_MiSTer

---

## 16. Proposed Project Structure

```text
mamr/
|
+-- recompiler/
|   +-- z80_decode.cpp
|   +-- z80_semantics.cpp
|   +-- analyzer.cpp
|   +-- cfg.cpp
|   +-- discover.cpp
|   +-- emit_c.cpp
|
+-- runtime/
|   +-- cpu_context.cpp
|   +-- scheduler.cpp
|   +-- bus.cpp
|   +-- interrupts.cpp
|   +-- ikari_video.cpp
|   +-- ikari_sprites.cpp
|   +-- hardflags.cpp
|   +-- ym3526.cpp
|   +-- input.cpp
|   +-- platform_sdl.cpp
|
+-- tools/
|   +-- romtool/
|   +-- tracer/
|   +-- verifier/
|   +-- replay/
|
+-- tests/
|   +-- z80/
|   +-- differential/
|   +-- ikari/
|
+-- games/
|   +-- ikari/
|       +-- ikari.toml
|       +-- entrypoints.txt
|       +-- patches/
|
+-- generated/
```

---

## 17. Project Layers

The architecture should be deliberately separated. Since the decision to
make MAMR multi-ISA (section 18), there are four layers instead of three:
what used to be "Generic" is split into an ISA-independent part and one
part per CPU family.

### Generic (ISA-independent)

```text
Block / CFG model concepts (address, block, edge, entry point)
Scheduler fundamentals
Verification tooling (differential tests, MAME oracle, replays)
Build and ROM handling (hash verification, generated/ code)
```

### CPU family (one per ISA)

```text
Z80:      decoder, semantics, interpreter, C emitter, CFG analysis,
          reference core for differential tests
NEC V30:  the same set of parts, built in parallel to the Z80 one
          (no shared base classes until both run, see section 18)
```

### Board family

```text
SNK Triple-Z80:   CPU communication, NMI/IRQ, memory bus,
                  basic video structure, sound communication
Irem M72:         V30 + Z80 sound CPU, PIC 8259, sound latch and
                  sound CPU reset line, two scroll layers with a raster
                  split, sprite DMA, YM2151
```

### Game

```text
Ikari Warriors:   ROM layout, memory map, hard flags, rotary input,
                  game-specific registers, special graphics rules
R-Type:           ROM layout, entry points and handler tables,
                  raster line of the status bar, input mapping
```

This way, a shared SNK framework, and later a shared Irem framework, may
eventually emerge.

---

## 18. Don't Generalize Right Away

Version 0.1 should explicitly support **only Ikari Warriors**.

Not:

```text
Universal Z80 Arcade Recompiler
```

But rather:

```text
one precisely defined Ikari Warriors ROM version
```

With:

- a specific ROM set
- SHA hashes
- a defined MAME revision
- a reproducible build
- reproducible test replays

Only once Ikari works completely should we abstract.

Ikari Warriors runs completely since phase 7. The second target is
**R-Type** (Irem, 1987, MAME set `rtype`, the World version) on Irem M72
hardware: an NEC V30 main CPU (8 MHz) and a Z80 sound CPU with a YM2151.
This makes MAMR a multi-ISA recompiler. The rules of this section stay in
force for the second target:

- one precisely defined ROM set (`rtype`, SHA-1 verified), MAME 0.289 as
  the oracle with the complete set (including the 2 PROMs and 3 PLDs that
  MAME requires since 0.250)
- the V30 front end, its semantics and its interpreter are built **in
  parallel** to the Z80 ones; the verified Z80 and Ikari code is not
  refactored to make room for a second ISA
- shared abstractions (common block model, common runtime parts) are
  extracted only once both games run, and only where both actually use
  them
- the sound side reuses the Z80 recompiler as it is; what R-Type needs in
  addition (IM 0 with a vector, a held reset line, code uploaded into RAM)
  is added as runtime features, not as a second Z80 path

Possible later targets, after both games run:

```text
SNK triple-Z80:  Victory Road, TNK III, Athena, Psycho Soldier,
                 Guerrilla War
Irem M72 family: further M72/M81/M84 games without protection MCU
```

---

## 19. Development Phases

### Phase 1: Z80 Recompiler

Goal:

```text
synthetic Z80 program
        v
Recompiler
        v
C/C++
        v
x86-64
        v
correct result
```

Requirements:

- complete decoder
- correct flags
- correct registers
- cycle counting
- basic blocks
- direct jumps
- CALL/RET
- interrupt fundamentals

---

### Phase 2: Differential Verifier

Run recompiled blocks against the reference Z80.

Goal:

```text
1,000,000+ executed blocks
0 mismatches
```

---

### Phase 3: Ikari ROM Analysis

- load ROMs
- verify SHA
- determine entry points
- generate CFG
- detect jump tables
- log unknown indirect targets
- measure coverage

No graphics yet.

---

### Phase 4: CPU A + CPU B

Implement:

- Memory Map
- NMI communication
- Shared State
- Scheduler
- Interrupts

Goal:

```text
Boot / self-test runs headless
```

---

### Phase 5: Video

Implement:

- Tilemap
- Sprite RAM
- Palette
- Layer Priority
- Scroll
- Hard Flags

Goal:

```text
Attract mode visually correct
```

---

### Phase 6: Sound

Implement:

- Sound Z80
- YM3526 #1
- YM3526 #2
- Timer
- IRQ
- Audio Output

Goal:

```text
Attract mode + music + sound effects
```

---

### Phase 7: Eliminate Interpreter Fallback

Replay:

```text
Boot
Coin
Start
Gameplay
Level 1
Level 2
...
```

Measure coverage.

End goal:

```text
0 unknown code targets
0 interpreter fallbacks
```

Then it can be said:

> Ikari Warriors runs entirely on statically recompiled Z80 game code.

### Game 2: R-Type (Irem M72)

The second target follows the same order: verify one piece before building
on it, keep the MAME oracle next to every step.

- **Phase R1: Oracle kit and code map** (data under `tests/data/`, local,
  not distributed): pinned MAME 0.289 launcher, Lua trace with
  sound latch and sound I/O logs, reference runs (boot, attract mode,
  stage 1), instruction coverage of both CPUs, code map (entry points,
  indirect transfer sites and their targets, handler tables, never
  executed code).
- **Phase R2: Sound board.** The sound program is the 32 KB image the V30
  copies into sound RAM before it releases the Z80. Recompile it with the
  existing Z80 recompiler, add IM 0, the held reset line and a YM2151
  (ymfm OPM), and drive it with the sound commands recorded in MAME.
  Compare the sound I/O and the WAV output against MAME.
- **Phase R3: V30 reference interpreter.** Decoder and semantics for the
  V30 (8086/80186 plus the NEC instructions R-Type uses), validated
  against single-step test data and against MAME's NEC core as the clock
  reference. It becomes the interpreter fallback and the emitter
  reference, the role `z80_exec` has for the Z80.
- **Phase R4: M72 machine.** V30 on the interpreter, PIC 8259 (edge
  triggered, auto EOI, VBlank and raster interrupt), memory and I/O map,
  video with the raster split, sprites, input. RAM, video state and sound
  commands compared against the reference runs.
- **Phase R5: V30 static front end.** Blocks from the code map are
  recompiled to C; indirect targets go through a runtime dispatcher with
  the interpreter as fallback, as for Ikari before phase 7. Done: the
  blocks come from the control-flow analysis (`recompiler/v30_cfg`),
  which reproduces the kit's static code map, and the emitter is checked
  by a differential test against the interpreter.
- **Phase R6: Eliminate the V30 interpreter fallback** (as phase 7).
  The boot, the attract mode and the kit's stage 1 replay run without a
  fallback and the tests fail on one; the coverage of the later stages
  is open.

### Platform: Original Xbox

A console port of the finished Ikari Warriors, after both games run on the
PC. The point is the proof: the machine and the recompiled code have no
operating system dependency, so they go wherever a C++ compiler goes. The
original Xbox is first because it is a Pentium III with 64 MB, i.e. the
same ISA as the PC, and a softmodded one with a free toolchain (nxdk) is at
hand. Details: docs/xbox-port.md.

- **Phase X1: Toolchain and chain.** nxdk on a Linux host, its SDL sample
  built and started on the console over FTP. Done.
- **Phase X2: Front end and build.** `platform/xbox/`: an SDL 2 front end
  with the same machine, renderer and input mapping as the PC, a Makefile
  on top of the nxdk one, a script that copies the sources to the host,
  builds and uploads. Measurements are written next to the XBE.
- **Phase X3: Measure, then optimise.** Frame work time on the console
  against the 16.7 ms budget; only then the levers (split of the main CPU
  blocks, LTO, renderer).

Later consoles follow the same cut: nothing of the port enters the core.

---

## 20. Things We Deliberately Do Later

Not part of the first proof of concept, and not part of the second target
either:

```text
direct x86-64 code generator
LLVM Backend
Vulkan
DirectX 12
multithreading the CPUs
Widescreen
Mods
Achievements
Launcher
multiple ROM revisions (also for R-Type: only the World set rtype)
further games beyond Ikari Warriors and R-Type
further consoles beyond the original Xbox (the Wii is the candidate)
a third CPU family
shared Z80/V30 abstractions before both games run
cocktail / flip screen support for R-Type
Netplay
CRT Shader
```

Functionality and correctness first.

Then convenience.

---

## 21. ROMs and Distribution

The original ROMs should not be in the repository.

Repository:

```text
Recompiler       yes
Runtime          yes
Hardware model   yes
Tests            yes
Configs          yes

Arcade ROMs      no
Graphics ROMs    no
Sound ROMs       no
```

Workflow:

```text
user owns ikari.zip
        v
ROM Hash Verification
        v
local analysis
        v
local recompilation
        v
generated/
        v
Host Compiler
        v
native executable
```

Code generated from the ROMs should likewise not necessarily be distributed with the repository.

---

## 22. Biggest Technical Risks

### Indirect Jumps

```asm
JP (HL)
```

Static targets must be detected or logged at runtime.

### Timing

Three CPUs plus sound and video must be synchronized deterministically.

### Interrupts

- IRQ
- NMI
- YM Timer
- CPU handshakes

must be modeled accurately enough.

### Z80 Quirks

In particular:

- undocumented flags
- R register
- alternate registers
- EI delay
- HALT
- interrupt modes

### Hard Flags

The SNK-specific collision/bounds hardware must be understood correctly.

### Code from RAM

If the game writes code into RAM dynamically and executes it later, pure ROM recompilation is not enough.

So instrument early:

```text
PC in RAM region?
        v
log it
```

If this never happens, the case can be ruled out later.

---

## 23. Biggest Advantage of the Project

Ikari Warriors is small enough that the system can be understood completely.

We also have several reference sources:

```text
MAME
+
MiSTer FPGA
+
ROM traces
+
Z80 reference core
```

This allows the recompilation to be verified very systematically.

The project is therefore not just a porting attempt, but also an interesting experiment:

> Can a classic multi-Z80 arcade game be transferred completely ahead of time into native modern host code?

---

## 24. Project Strategy

Name:

# MAMR: Multiple Arcade Machine Recompiler (SNK Z80 first, Irem V30 second)

First target:

```text
Ikari Warriors
SNK
1986
```

Second target (section 18, phases R1 to R6 in section 19):

```text
R-Type
Irem M72 (NEC V30 + Z80 sound)
1987
```

The visible game is not the first proof of concept.

The first technical milestone is:

```text
Ikari Main ROM
      v
Analyzer
      v
Z80 -> C/C++
      v
Clang
      v
x86-64
      v
Differential Test

millions of basic blocks
0 mismatches
```

Once this point is reached, the most important technical core of the project is proven.

Graphics, audio, controllers, and windowing are then much more conventional runtime tasks.

---

## 25. Recommended References

### Recompilation

- N64Recomp  
  https://github.com/N64Recomp/N64Recomp

- NeoGeoRecomp  
  https://github.com/sp00nznet/neogeorecomp

- Daytona USA Static Recompilation  
  https://github.com/alphanu1/daytona-arcade-recomp

- GB Recompiled  
  https://github.com/arcanite24/gb-recompiled

- Namco System 22 Decompilation (methodology reference, different hardware)  
  https://github.com/spacestate1/namco22-decompile  
  Ghidra decompilation or tool-based translation to C with manual correction,
  checked against MAME; sound/DSP programs are generated at build time from
  the user's own game files. Relevant for MAME comparison and
  building from ROMs (Phase 4/5), not for the Z80 recompiler.

### Ikari / SNK Hardware

- MAME SNK Driver  
  https://github.com/mamedev/mame/blob/master/src/mame/snk/snk.cpp

- MiSTer Ikari Warriors Core  
  https://github.com/MiSTer-devel/Arcade-IkariWarriors_MiSTer

- MiSTer SNK Triple-Z80 Core  
  https://github.com/MiSTer-devel/Arcade-SNK_TripleZ80_MiSTer

### R-Type / Irem M72 Hardware

- MAME Irem M72 Driver (oracle, MAME 0.289)  
  https://github.com/mamedev/mame/blob/mame0289/src/mame/irem/m72.cpp

- MiSTer Irem M72 Core (schematics, PROM contents; read only, GPL-2.0,
  not vendored; statements are checked individually)  
  https://github.com/MiSTer-devel/Arcade-IremM72_MiSTer

- MAME NEC V20/V30 core (BSD-3-Clause; candidate clock reference for the
  V30, needs approval as third-party code)  
  https://github.com/mamedev/mame/tree/mame0289/src/devices/cpu/nec

- SingleStepTests v20 (MIT; per-instruction test data measured on
  hardware, without timing)  
  https://github.com/SingleStepTests/v20

### Audio

- ymfm  
  https://github.com/aaronsgiles/ymfm  
  (YM3526 for Ikari Warriors; the OPM part for R-Type's YM2151)

---

## 26. Next Concrete Step

The next step should be to create a **technical hardware specification for Ikari Warriors**.

It should contain at least:

```text
ROM Layout
CPU A Memory Map
CPU B Memory Map
Sound CPU Memory Map
I/O Ports
NMI/IRQ sources
CPU Handshake
Video RAM
Sprite RAM
Palette
Scroll Register
Hard Flags Register
Sound Command Register
YM3526 Mapping
Input Mapping
Frame Timing
```

After that, version `0.1` of the recompiler can be implemented concretely.

---

## Summary

MAMR is meant to take:

```text
Ikari Warriors Arcade ROM
        v
static Z80 recompilation
        v
native C/C++
        v
x86-64
```

and turn it into a native PC port.

The entire arcade machine is not emulated in the classic way.

Instead:

```text
Game code -> statically recompiled
Hardware  -> small native runtime
```

The most sensible technical blueprint is a combination of:

```text
NeoGeoRecomp
+
N64Recomp
+
GB Recompiled
+
MAME
+
MiSTer
```

The project is technically demanding, but realistic enough to start with a clearly scoped Ikari Warriors proof of concept.
