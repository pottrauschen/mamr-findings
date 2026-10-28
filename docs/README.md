# Documents

The findings of MAMR, a static recompiler for retro games, as documents:
hardware specifications with the origin of every statement, the hash line
formats the judges write, the setup and results of each judge, and the
deviations found on the way. The documents are licensed under CC BY 4.0
([LICENSE-docs](LICENSE-docs)).

**Paths.** Paths under `docs/`, `tools/oracle/`, `patches/` and `shader/`
are files of this repository. Every other path a document names
(`runtime/...`, `recompiler/...`, `games/...`, `tests/...`, `platform/...`,
`tools/<name>` other than `tools/oracle`, CMake targets and ctest names,
`tests/data/...`, `roms/...`) is a file or test of MAMR's own source tree,
which is not published, or local data that is not distributed (ROMs,
test ROMs, recordings). `$BUILD` stands for a build directory of that tree.
Line references written `[MAMR file:line]` point into the same tree.

## Method

| File | Content |
|---|---|
| [concept.md](concept.md) | the project concept: static recompilation with an interpreter fallback, verification against emulators as judges, phases, risks, references |
| [machine-interface.md](machine-interface.md) | the common game interface of all machines: description, life cycle, outputs, inputs, SRAM, save states, the cartridge ABI of game artefacts, ROM sets loaded at run time, reset |

## SNES

| File | Content |
|---|---|
| [snes-architecture.md](snes-architecture.md) | the SNES path: 65816 and SPC700, board, two timing stages (fast S, exact E), phases S1-S8 |
| [snes-hardware-spec.md](snes-hardware-spec.md) | memory map, timing frame, DMA/HDMA, CPU decisions, with sources and origin classes; includes a reading of the S-CPU schematic |
| [snes-audio-spec.md](snes-audio-spec.md) | S-SMP, timers, IPL protocol, S-DSP |
| [snes-ppu-spec.md](snes-ppu-spec.md) | PPU registers and behaviour |
| [snes-oracle-format.md](snes-oracle-format.md) | hash line format, version 4 |
| [snes-oracle-input-script.md](snes-oracle-input-script.md) | the input script all SNES judges share |
| [snes-oracles.md](snes-oracles.md) | judges aresref, MesenCE, MAME: setup, the nine ares patches, gates, known deviations |
| [snes-test-evidence.md](snes-test-evidence.md) | evidence register of the test programs: source, licence, origin of the expected values, results |
| [snes-cartridge-db.md](snes-cartridge-db.md) | cartridge database: releases by SHA-1 with board, PCB and region |
| [snes-rom-survey.md](snes-rom-survey.md) | 22 ROM images through loader, judges and tracer; findings F1-F12; requirements for the cartridge contract |
| [snes-zelda-authority.md](snes-zelda-authority.md) | code authority for A Link to the Past: static block discovery checked against a disassembly and a reimplementation (counts only), native runs |
| [snes-wram-code-study.md](snes-wram-code-study.md) | study: code executed from work RAM in Chrono Trigger, Final Fantasy III and Secret of Mana, options |
| [snes-ram-code.md](snes-ram-code.md) | the follow-up: measurement tool, interpreted share per game situation, decision for version 1 |

## NES

| File | Content |
|---|---|
| [nes-architecture.md](nes-architecture.md) | the NES path (NTSC and PAL): 2A03, board, block keys, DMA stall, phases N1-N4, decisions |
| [nes-hardware-spec.md](nes-hardware-spec.md) | CPU, memory map, MMC3/MMC1/CNROM, interrupts, open bus, with origin classes; open questions with measurement setups |
| [nes-ppu-spec.md](nes-ppu-spec.md) | PPU RP2C02G: registers, delays, pipelines, sprite evaluation, choices with measurement setups |
| [nes-audio-spec.md](nes-audio-spec.md) | APU channels, mixer, output stage |
| [nes-oracle-format.md](nes-oracle-format.md) | hash line format nesfh, version 2 |
| [nes-oracles.md](nes-oracles.md) | judges MesenCE 2.2.1 and MAME 0.285: traps, sampling points, gates, findings |
| [nes-test-evidence.md](nes-test-evidence.md) | evidence register: AccuracyCoin, SingleStepTests, nestest, blargg's suites, with results |
| [nes-smb3-survey.md](nes-smb3-survey.md) | code survey of Super Mario Bros. 3 (counts, banks, dispatch patterns) |

## Arcade

| File | Content |
|---|---|
| [hardware-spec.md](hardware-spec.md) | Ikari Warriors (SNK, 1986): memory maps, interrupts, video, sound, hard flags |
| [ikari-timing-reference.md](ikari-timing-reference.md) | Ikari timing: board, MiSTer, MAME and MAMR compared; causes of the replay divergence |
| [rtype-hardware-spec.md](rtype-hardware-spec.md) | R-Type (Irem M72): clocks, sound board, V30, interrupt controller, memory and I/O map, video |
| [spang-hardware-spec.md](spang-hardware-spec.md) | Super Pang (Mitchell, Kabuki Z80): MAME's timing model, memory map, Kabuki, EEPROM, sound, video, MAME model against the board |
| [arcade-oracle-format.md](arcade-oracle-format.md) | hash line format afh 1 (Ikari, R-Type) |
| [arcade-oracles.md](arcade-oracles.md) | judges MAME 0.285 and mameref, findings F1-F10 (MAME) and E1-E7 (MAMR), what may be claimed |
| [spang-oracle-format.md](spang-oracle-format.md) | hash line format spfh 1 |
| [spang-oracles.md](spang-oracles.md) | Super Pang kit, MAME findings, lockstep per field, picture, sound, blocks |

## Front end and picture

| File | Content |
|---|---|
| [frontend.md](frontend.md) | MAMR's window front end: timing model, audio rate control, picture path, measurements; section 12 the tube shader |
| [crt-research-evaluation.md](crt-research-evaluation.md) | what the research on tube rendering established, and what it did not |
| [scaler-firmware-reading.md](scaler-firmware-reading.md) | how the OSSC and MiSTer firmware draw scanlines and masks (procedure only) |
| [frontend-landscape.md](frontend-landscape.md) | research: ES-DE, RetroArch's run loop, the libretro contract, a plan in three stages |
| [xbox-port.md](xbox-port.md) | Ikari Warriors on the original Xbox: toolchain and front end (not built) |
