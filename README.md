# MAMR findings

MAMR is a static recompiler for retro games: it translates a game's
machine code ahead of time into native code and keeps an interpreter for
whatever the translation did not reach. It covers the SNES, the NES and
three arcade boards (Ikari Warriors, R-Type, Super Pang). This repository
publishes what the work on it found out, and the tools used to find it:

- **documents**: hardware specifications in which every statement carries
  the origin of its evidence, the per-frame hash line formats, the setup
  and results of every judge, and the deviations found on the way, both
  in MAMR and in the emulators it is compared with ([docs/](docs/README.md));
- **the oracle kit**: scripts that make emulators write the hash lines,
  compare two runs field by field, and run the gates
  ([tools/oracle/](tools/oracle/README.md));
- **patches against the judges**: nine for ares, three for MAME 0.285,
  each explained in the documents ([patches/](patches/README.md));
- **the tube shader**: a one-pass arcade monitor shader whose constants
  carry their evidence class and source ([shader/](shader/README.md)).

## What this repository is not

- **No games, no ROMs, no game data.** Nothing here contains bytes of a
  game, a BIOS or a test ROM. ROMs are named by title and SHA-1 only.
- **No recompiler, no runtime, no front end to download.** The recompiler,
  the machine runtimes, the generated code, the game artefacts and the
  player program are not part of this repository. Documents that name
  their source files refer to MAMR's own, unpublished source tree.
- **No claim about the hardware beyond the evidence.** Where a statement
  rests on an emulator, the documents say so.

## The method

Every machine has a hash line format: at a fixed sampling point in every
frame, one fingerprint per field of the machine (CPU registers and clock
counts, work RAM, video and sound chip state, the picture). Independent
emulators write the same lines; they are the judges: ares (with nine
patches, "aresref") and MesenCE for the SNES, MesenCE and MAME for the
NES, MAME 0.285 (stock and with three patches, "mameref") for the arcade
boards. Two runs are compared field by field, frame by frame; the first
frame at which a field differs is the result, and every difference that
remains is traced to a cause and written down as a finding, whichever
side it is on.

A judge is evidence about itself, not about the console. A MAME run, for
example, is classed as evidence about MAME (MEASURED-EMU in the arcade
documents); equality with a judge is reported as equality with that
judge, never as accuracy to the board.

## Two numbers per game

For each game two numbers say how far it got:

1. **Native coverage:** how many instructions on a real route still run
   in the interpreter (a "miss" is a jump into code the recompiler had not
   translated).
2. **Agreement with an independent judge:** at which frame, and in which
   fields, the game first differs from an emulator it did not come from.

The documents give both numbers with their conditions. Some examples
from them:

| Game | Native coverage | Against the judge | Where |
|---|---|---|---|
| A Link to the Past (USA) | 0 misses, 12 interpreted instructions (the reset code) on a 9000-frame route | native against aresref on that route (fast timing stage): equal in every field, master clock and program counter included | [snes-zelda-authority.md](docs/snes-zelda-authority.md) section 7 |
| Chrono Trigger, Final Fantasy III, Secret of Mana | 0 misses in ROM; code the games unpack into RAM stays in the interpreter: 7.0 to 9.9 percent of the instructions on the routes | native equal to the interpreter in every hash line | [snes-ram-code.md](docs/snes-ram-code.md) |
| Super Mario Bros. 3 | 0 misses | against MesenCE every difference over 3000 frames traced to one of the findings S1-S4 | [nes-oracles.md](docs/nes-oracles.md), [nes-smb3-survey.md](docs/nes-smb3-survey.md) |
| AccuracyCoin (NES test ROM) | | 147 of 147 tests | [nes-test-evidence.md](docs/nes-test-evidence.md) |
| R-Type | boot, attract mode and the stage 1 replay without interpreter fallback | against MAME instruction by instruction over the 3,676,169 instructions of the first 320 frames, with one MAME rule adopted; the game build equal to mameref on the main CPU side, picture included | [arcade-oracles.md](docs/arcade-oracles.md) |
| Ikari Warriors | no interpreter fallback since phase 7 | not cycle-accurate against MAME: a replayed MAME game parts ways at frame 9773; the reasons are documented | [concept.md](docs/concept.md), [ikari-timing-reference.md](docs/ikari-timing-reference.md) |

## How to read a finding

Findings have short identifiers per document (F1-F10 and E1-E7 in
[arcade-oracles.md](docs/arcade-oracles.md), F1-F12 in
[snes-rom-survey.md](docs/snes-rom-survey.md), S1-S4 and A1 for the NES,
and so on). A finding names the side it is on (the judge or MAMR), the
first frame and field where it shows, the cause as far as it was traced,
whether it is fixed, patched in the judge, or left documented, and the
evidence class of every hardware statement it rests on.

**Evidence classes** (the exact sets per machine are defined at the top of
each hardware specification):

| Class | Meaning |
|---|---|
| DATASHEET | data sheet, schematic, die analysis |
| MEASURED | measured on the hardware with an instrument |
| TEST-ROM-HW | a test ROM run on the hardware, result published |
| SIM | a transistor-level simulation of the chip (NES) |
| DOC | hardware documentation based on tests, method not given |
| EMU-CONSENSUS, EMU | several independent emulators agree / one emulator says so |
| MEASURED-EMU | a run of an emulator: evidence about that emulator only (arcade) |
| INFERENCE | concluded without direct evidence |
| CHOICE | a decision where the sources are silent or differ, with the range it may take |
| UNKNOWN | no usable source |

## Contributing

Most open questions in the specifications end with a measurement setup:
what to connect, what to run, what to read. Contributions that help:

- **measurements** on real hardware (logic analyser captures, test ROM
  results with the console revision named);
- **photos** of boards and chips that settle a revision or a part number;
- **corrections**: a wrong statement, a wrong evidence class, a better
  source.

Please open an issue with the document and section, what you observed,
and how. Do not attach ROMs or parts of them.

## Layout

```text
docs/           documents (doc map: docs/README.md), CC BY 4.0
tools/oracle/   oracle kit: hash line writers, compare, gates (BSD-3-Clause)
patches/ares/   patches against ares, ISC like ares
patches/mame/   patches against MAME 0.285, BSD-3-Clause like the patched files
shader/         tube shader: GLSL, SPIR-V, profile and driver sources (BSD-3-Clause)
third_party/    licence notes for the material derived from MAME and ares
```

## Licence

Code (tools/, shader/): BSD 3-Clause, [LICENSE](LICENSE). Documents:
CC BY 4.0, [docs/LICENSE-docs](docs/LICENSE-docs). Patches: under the
licence of the project they patch, see [patches/README.md](patches/README.md)
and [third_party/](third_party/). Game and product names belong to their
owners and are used only to identify the hardware and software described.
