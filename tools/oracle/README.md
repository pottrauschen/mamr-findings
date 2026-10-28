# Oracle kit

Scripts that make emulators write one hash line per frame (a fingerprint
of every machine field: CPU registers and clocks, RAM, video and sound
chip state, picture), and that compare two such files field by field and
frame by frame. An emulator used this way is called a judge. MAMR writes
the same lines from its own runs; MAMR itself is not part of this
repository, but any program that writes the format can be compared.

| Directory | Machine | Judges | Format | Setup, gates, findings |
|---|---|---|---|---|
| [snes/](snes/) | SNES | aresref (ares with [patches/ares](../../patches/ares/)), MesenCE 2.2.1, MAME | [snes-oracle-format.md](../../docs/snes-oracle-format.md), input script [snes-oracle-input-script.md](../../docs/snes-oracle-input-script.md) | [snes-oracles.md](../../docs/snes-oracles.md) |
| [nes/](nes/) | NES (NTSC and PAL) | MesenCE 2.2.1, MAME 0.285 | [nes-oracle-format.md](../../docs/nes-oracle-format.md) | [nes-oracles.md](../../docs/nes-oracles.md), [nes-test-evidence.md](../../docs/nes-test-evidence.md) |
| [arcade/](arcade/) | Ikari Warriors, R-Type | MAME 0.285, mameref (MAME 0.285 with [patches/mame](../../patches/mame/), built by [mame/build_mameref.sh](mame/build_mameref.sh)) | [arcade-oracle-format.md](../../docs/arcade-oracle-format.md) | [arcade-oracles.md](../../docs/arcade-oracles.md) |
| [spang/](spang/) | Super Pang | MAME 0.285 | [spang-oracle-format.md](../../docs/spang-oracle-format.md) | [spang-oracles.md](../../docs/spang-oracles.md) |

## What it needs

- Python 3.11 or later (the Super Pang kit reads TOML), a POSIX shell.
- The judges, installed or built by the user: MAME 0.285 (a distribution
  package works; mameref is built from source), MesenCE 2.2.1, and for
  aresref an ares checkout at commit c76aaff plus cmake and a C++20
  compiler (`snes/aresref/build_aresref.sh --fetch ARES_DIR`). The scripts
  find them through environment variables (`MAME`, `MESEN`, `ARESREF`)
  or in `PATH`; each script's header lists its variables.
- The ROMs, supplied by the user. Nothing here contains ROM data: the
  scripts find files by name or SHA-1 (`arcade/romset.py` from
  `mame -listroms`, `spang/romset.py` from
  [spang/spang-set.toml](spang/spang-set.toml)), and the documents name
  the expected releases by SHA-1. Test ROMs are named in the evidence
  registers ([snes-test-evidence.md](../../docs/snes-test-evidence.md),
  [nes-test-evidence.md](../../docs/nes-test-evidence.md)) with their
  sources; they are not included either.
- `xvfb-run` helps with MesenCE, which wants a display; the scripts
  otherwise run headless.

## Quick check

Every Python script has a self-test that needs neither a judge nor a ROM:

```sh
for f in tools/oracle/*/*.py; do python3 -I "$f" selftest; done
```

`arcade/z80steps.py` needs MAME's listing:
`python3 -I tools/oracle/arcade/z80steps.py selftest MAME_DIR/src/devices/cpu/z80/z80.lst`
(the loop above prints its usage and exits 3).

## Not included

- MAMR's own writers (`snes_headless`, `nes_headless`, `ikari_headless`,
  `rtype_headless`, `spang_headless`, `machine_hash`): the gates that run
  them (`gates.py g1`, `lockstep`, the `mamr` oracle) skip when they are
  not found.
- Input scripts that play commercial games (the Super Mario Bros. 3
  World 1-1 script, the Super Pang coin-and-play script) and route files:
  the documents describe them and give their results. The AccuracyCoin
  input script ([nes/inputs/accuracycoin-all.txt](nes/inputs/accuracycoin-all.txt))
  is included.
- Reference hash files from ROM runs, miss logs, replays.

Licence: BSD 3-Clause ([LICENSE](../../LICENSE)). `spang/kabuki.py` and
the keys in `spang/spang-set.toml` follow MAME's kabuki.cpp, and
`arcade/z80steps.py` reads MAME's z80.lst as data
([third_party/mame/LICENSE](../../third_party/mame/LICENSE)).
