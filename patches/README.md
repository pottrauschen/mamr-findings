# Patches against the judges

MAMR is checked against emulators used as judges (see
[docs/README.md](../docs/README.md)). Where a judge's behaviour had to be
changed to sample a frame deterministically, or where it differs from the
hardware in a way that was documented as a finding, the change is a small
patch kept here. Each patch is explained, with the evidence for it, in the
document named below.

| Directory | Applies to | Licence of the patches | Built by | Explained in |
|---|---|---|---|---|
| [ares/](ares/) | ares, commit c76aaffa6e69778baf9a66d1da04298ac2ed7d1d | ISC (the ares licence), see [third_party/ares/LICENSE](../third_party/ares/LICENSE) | [tools/oracle/snes/aresref/build_aresref.sh](../tools/oracle/snes/aresref/build_aresref.sh) | [docs/snes-oracles.md](../docs/snes-oracles.md) section 2 |
| [mame/](mame/) | MAME 0.285, tag mame0285 (commit f379cd06) | BSD 3-Clause (the licence of each patched MAME file), see [third_party/mame/LICENSE](../third_party/mame/LICENSE) | [tools/oracle/mame/build_mameref.sh](../tools/oracle/mame/build_mameref.sh) | [docs/arcade-oracles.md](../docs/arcade-oracles.md) section 2 |

## ares (aresref)

| Patch | Purpose |
|---|---|
| 0001-build-without-gui | build the core without the GUI toolkits and add the aresref front end |
| 0002-video-unthreaded | unthreaded screen refresh: runs are repeatable |
| 0003-absolute-clocks | absolute master clock and SMP clock counters for the hash lines |
| 0004-oracle-hooks | hooks for the sampling point, auto-joypad read, PC anchors, PPU and APU port writes |
| 0005-zero-entropy-option | power-on values that ares draws at random set to zero |
| 0006-reset-stack-reads | the reset sequence's stack cycles as reads (WDC W65C816S datasheet) |
| 0007-smp-instruction-boundary | sample the SMP at an instruction boundary |
| 0008-picture-at-vdisp | copy the picture at the start of line vdisp (overscan race) |
| 0009-smp-sample-on-copy | run the SMP to its boundary on a saved copy (finding F3) |

Apply by hand:

```sh
git clone https://github.com/ares-emulator/ares.git ares
git -C ares checkout c76aaffa6e69778baf9a66d1da04298ac2ed7d1d
for p in patches/ares/*.patch; do git -C ares apply "$PWD/$p"; done
```

or let `tools/oracle/snes/aresref/build_aresref.sh --fetch ARES_DIR`
clone, patch and build the headless front end.

## MAME (mameref)

| Patch | Purpose | Finding |
|---|---|---|
| 0001-ikari-cycle-interleave | Ikari Warriors: CPU A and CPU B interleaved by single cycles instead of 1/6000 s slices (they share one bus on the board); `MAMEREF_IKARI_STOCK_QUANTUM` restores the original | F1, F3 |
| 0002-m72-palette-from-ram-at-start | R-Type: pens never written start black instead of the palette device's start-up colours | F6 |
| 0003-nec-rep-continuation-no-double-charge | V30: a REP continued in the next time slice does not charge its 2 start clocks again | F7 |

The patches are argued from the board and the chip, not measured on
them; [docs/arcade-oracles.md](../docs/arcade-oracles.md) says which
statements "equal to mameref" supports. Apply by hand:

```sh
git clone --depth 1 --branch mame0285 https://github.com/mamedev/mame.git mame
for p in patches/mame/*.patch; do git -C mame apply "$PWD/$p"; done
```

or run `tools/oracle/mame/build_mameref.sh --fetch MAME_DIR`, which
builds only the two drivers needed (snk.cpp, m72.cpp).
