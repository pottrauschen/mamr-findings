# Zelda code authority

How much of The Legend of Zelda: A Link to the Past the block discovery
(recompiler/w65816_cfg) finds before the game runs, measured against a
complete disassembly of the US release, confirmed by a run through the
first minutes of the game, and carried over to the German release.
Status 2026-10-24; every number here was measured with the commands of
section 9 on that day. The ROMs, the clones of the references and every
list derived from them stay outside the repository (the ROM policy of
MAMR's README, docs/snes-cartridge-db.md).

## 1. Question and answer

The recompiler translates blocks ahead of time; a block that the
discovery does not find runs in the interpreter and shows up in the
runner's miss log. Until now the discovery followed only the vectors,
declared entries and the miss log of earlier runs (docs/snes-architecture.md
section 3), so the set of blocks depended on what had been played. The
question: does a static discovery find the code of the game before it
runs, and how is that known?

The answer, for the US release (Rev 0, SHA-1 6D4F10A8..., the release
of docs/snes-cartridge-db.md), measured in instruction starts of the
disassembly (section 4):

| entries | discovery before this work (no tables, no reset entry) | static discovery |
|---|---|---|
| the four native vectors | 635 of 125734 (0.5 %), 66 blocks | 124123 (98.7 %), 31371 blocks |
| the vectors and the native entry behind the reset code | 984 (0.8 %), 121 blocks | (included above) |
| plus the one declared entry of tests/snes-system/zelda-entries.txt | | 124862 (99.3 %), 31508 blocks |
| the vectors, the reset entry and the miss log of 6000 frames of the attract mode (1475 seeds; no declared entry, no reset entry before) | 8375 (6.7 %), 1793 blocks | 124862 (99.3 %), 31723 blocks |

With the declared entry, 4501 of the disassembly's 4584 functions are
found entirely, 15 partly and 68 not at all, and 2707 of the 2708
routines the zelda3 reimplementation names by an instruction start. The
discovery has 320 instruction starts the disassembly does not have
(section 5): 305 in data, 15 inside instructions; no run of section 7
enters them.

What is still missing (section 5) is code nothing in the program
reaches statically: dead code (most of it marked unreachable by the
disassembly), a debug handler, the intro's polyhedral thread without its
declared entry, and single instructions behind an unconditional
transfer or behind a width the analysis cannot see. The route through
the first minutes of the game (section 6) and the attract mode run
natively without a single dispatch miss (section 7).

## 2. References and their standing

Three outside readings of the program, all cloned outside the
repository (docs/snes-test-evidence.md has the commits and licences):

- usdasm (kan/spannerisms, GPL-3.0): a complete disassembly of the US
  ROM that reassembles to it byte for byte. It is the authority: every
  byte is either an instruction, a data item or free ROM, with a label
  per routine and a reference for every transfer. It is read and
  compared against; no code, no label, no address list and no table of
  it enters this repository, only counts and descriptions in this
  document's own words. tools/zelda_authority/usdasm_code.py reads its
  text into a plain list (instruction starts with their routine, data
  items, references with their kind) that lives next to the clone:
  125734 instruction starts in 4584 functions, 67647 data items, 28985
  references.
- zelda3 (snesrev, MIT): a C reimplementation whose function heads carry
  the ROM address of the routine each replaces; 2709 addresses, 2708 of
  them instruction starts of the disassembly (02:ED24, in its overworld
  source file, is not). A second reading of the function set; nothing of
  it is built. Neither its names nor the disassembly's labels are used in
  this document.
- snes2asm (nathancassano, Apache-2.0): a static disassembler with its
  own code-path tracing from the vectors. Run once on the US ROM (output
  outside the repository); section 4.5 has what it finds.

The miss log of the runner is the fourth source: what the interpreter
had to run because no block existed (docs/snes-architecture.md section
3). It is exact for the run it comes from and says nothing about the
rest of the game. snes_headless --pc-log records, for an interpreter-only
run, every (PB:PC, M, X) an instruction started at: the reached-code
record of section 6.

## 3. The static discovery

### 3.1 What the vectors alone reach, and why so little

From the four native vectors the discovery before this work found 66
blocks: the NMI and IRQ handlers and what they call, up to the first
indexed jump (00:8C7B). The main routine is reached only through the
reset code, which runs in emulation mode and was not followed; with the
reset entry the discovery gets 121 blocks and stops at the module
runner's pointer jump (00:80C6). Everything else in the game is reached
through tables, and tables were not followed on principle ("no
code/data heuristics"). The disassembly shows
what kinds of table the game uses; each of them has a fixed shape in the
instruction stream, and following that shape is not a guess about bytes
but a reading of the instructions around the transfer. The patterns, now
in recompiler/w65816_cfg (its header has the exact rules); the site
counts are those of the US ROM:

| pattern | shape | sites | what it reaches |
|---|---|---|---|
| indexed jump | `JMP (a,X)`, `JSR (a,X)`: a table of 16-bit targets at PB:a | 56 (30 JMP, 26 JSR) | the tile handlers (two tables of 256), the overworld overlays (128), dungeon room and ending routines, Link's states, submodules of the game modules, the NMI's update routines |
| dispatcher | a call whose callee pulls exactly its own return address before any push and ends in an indirect jump (in this ROM the local dispatcher at 00:8781 and the long one at 00:879C); the table follows the call, two bytes per entry in the caller's bank when the callee reads the pointer once, three when it reads the bank too; the fall-through of the call is not code | 212 (200 local, 12 long; the disassembly has 213 calls, 201 local: the last one stands in dead code) | the sprite preparation table (243 entries) and the state handlers of single sprites and bosses, dungeon routines, the text renderer, the intro, submodules of the game modules |
| return trick | `LDA table,Y` (16 bits), `DEC A`, `PHA`, `RTS`: the target is the entry + 1 - DECs; `PEA a`, `RTS` | 15 | the sprite main routines (243 entries), the overlords |
| pointer jump | `JMP (a)` or `JML [a]` through a RAM pointer whose bytes the same block, or the blocks that fall through into it, store right after loads from ROM tables | 9 | the 28 game modules (the jump at 00:80C6, three byte tables), the ancilla handlers (08:837C, 67 entries), four tables of the dungeon room drawing in bank 01 (4 to 248 entries) and three smaller ones (00:D88F, 00:F8AE, 08:F4E8) |
| reset entry | the reset vector's emulation-mode code up to `CLC; XCE`: the instruction after it is the first native entry (00:801D, M and X 8 bits) | 1 | the main routine |

A table ends at the first entry that lies at a leader found so far, at
the first entry at or past one of the table's own targets (a table does
not run into its handlers), at an entry that is no code address (a null
entry, all bytes zero, is a hole for an index the game never uses and
is skipped, up to eight in a row: the sprite tables have 13 of them), or
at 512 entries. Tables are read only after the walk of everything
reached so far has run dry, so that the leaders can end them.

Measured against the runs of `dw`/`dl` entries the disassembly has at
each table base: all 56 indexed-jump tables, 198 of the 212 dispatcher
tables and 13 of the 15 return-trick tables have the disassembly's
length, the 243-entry sprite tables, the two 256-entry tile tables and
the 128-entry overlay table among them. The other 16 run on by one to
five entries into what follows the table (its handlers' code or a data
table), where two bytes happen to form a code address; the pointer-jump
tables (split byte tables) were not compared this way. The surplus is
the source of most extra instruction starts of section 5. The
abs-indexed loads of the return trick and the pointer jumps are read in
the program bank (the data bank is taken to be PB, as the game's
`PHK; PLB` sets it); a game that reads such a table through another
data bank would need that rule widened.

### 3.2 Contexts

The emitter keys blocks by (PB:PC, M, X) and the dispatcher never enters
a block of another width, so a target found with the wrong width is a
block that never runs. Four rules give the targets their width:

- a dispatcher's targets get the context the dispatcher leaves (both
  dispatchers of this ROM end in `SEP #$30`); an indexed jump's and a
  return trick's targets the context at the transfer;
- the return site of a call gets the contexts the callee returns with:
  the contexts at the RTS/RTL blocks reachable from its entry inside
  the routine (through its own return sites and table targets, not
  into further callees), computed from the previous round of the
  discovery and refined until stable; an unknown width in that set
  stands for the call's width. Without it, a routine that calls a
  callee which changes M is decoded in the wrong width after the call;
- the return site of `JSR (a,X)` gets the union of the contexts the
  table's targets return with (a target whose contexts are unknown
  stands for the call's). Without it the route of section 6 met one
  dispatch miss: the call at 02:F27E reaches the overworld's map-scroll
  routines, which return with M and X 16 bits, and the block after the
  call existed only with 8 bits (02:F281, 74 times in 9000 frames);
- PLP gets the context of the PHP it balances, in the same block or
  in the chain of blocks that fall through into it (pushes and pulls
  counted, calls taken as balanced). Without it, a `PHP ... PLP`
  pair with a branch between them ends the routine with the width
  unknown.

The discovery runs in rounds until the return contexts and the PLP
contexts are stable: six rounds for this ROM, 0.7 s in all, 28 MB.

### 3.3 What is taken for data

Runs that meet BRK, COP, WDM or STP are taken for data (the disassembly
has none of the four in the whole program; a game that uses one sets
the list). 12 leaders of this ROM are dropped this way: 7 do not start
an instruction of the disassembly (targets of tables read past their
end), 5 do but are decoded in a wrong width; all 5 instructions are
found inside other blocks with the right width.

## 4. The measure against the disassembly

### 4.1 Method

tools/zelda_authority/cfg_compare.py takes the map snes_recomp writes
(`--map`: every block with its instruction starts, successors, callees,
tables and diagnostics) and the disassembly's list. "found" is an
instruction start of the disassembly that some block of the map starts
an instruction at; "extra" is a block instruction start the disassembly
has no instruction at (inside a data item, or inside an instruction). A
missed routine gets its cause from how the disassembly refers to it: by
a dispatcher table, by a pointer table, by a direct call or branch from
found code, from missed code only, or not at all.

### 4.2 Vectors and reset entry only

```text
disassembly: 125734 instruction starts in 4584 functions; map: 124443 instruction starts in 31371 blocks
found 124123 (98.7 %), missed 1611 (1.3 %), extra 320 (data 305, misaligned 15)
functions: 4479 found entirely, 15 partly (78 instructions missed inside them), 90 missed
missed functions by cause (functions / instructions):
  dispatch        2 /      68
  table           1 /      13
  indirect        0 /       0
  found-ref       0 /       0
  missed-ref     23 /     801
  unref          64 /     651
map diagnostics: indirect-jump 2, no-code 3, stop-opcode 12, unknown-width 1
zelda3: 2709 function addresses, 2708 are instruction starts of the disassembly, 2693 found by the map
```

The map has fewer distinct instruction starts (124443) than the
discovery has instructions (125391): the same address appears in blocks
of more than one context.

### 4.3 With the declared entry

tests/snes-system/zelda-entries.txt declares one entry, the intro's
polyhedral thread (section 5). With it:

```text
disassembly: 125734 instruction starts in 4584 functions; map: 125182 instruction starts in 31508 blocks
found 124862 (99.3 %), missed 872 (0.7 %), extra 320 (data 305, misaligned 15)
functions: 4501 found entirely, 15 partly (78 instructions missed inside them), 68 missed
missed functions by cause (functions / instructions):
  dispatch        2 /      68
  table           0 /       0
  indirect        0 /       0
  found-ref       0 /       0
  missed-ref      2 /      75
  unref          64 /     651
zelda3: 2709 function addresses, 2708 are instruction starts of the disassembly, 2707 found by the map
```

The zelda3 routine still missing is a sound helper at 08:8020 that
nothing calls. Adding the miss log of 6000 frames of the attract mode
changes no count of the disassembly (124862 found); it adds 215 blocks
in other contexts.

### 4.4 Unresolved transfers

Two indirect jumps are left: the dispatchers' own `JML [$0000]` at
00:8799 and 00:87BD, which are the mechanism the dispatcher pattern
reads around, not a gap. Every other indirect transfer of the program
is resolved by one of the patterns.

### 4.5 snes2asm as a third reading

snes2asm traces code paths from the vectors and decodes everything else
linearly (marked in its output by a hex comment). On the US ROM its
traced code is 1032 instruction starts, all in bank 00; 488 of them are
instruction starts of the disassembly. It decodes the reset code with a
16-bit accumulator (the CPU starts in emulation mode, 8 bits), so its
trace leaves the real instruction stream after the first immediate load
(00:8013), and it follows no table. As a code map it is far behind the
vectors-only discovery (635 instruction starts) and is not used further;
it confirms from the outside that a trace from the vectors without the
table patterns reaches almost nothing of this game.

## 5. The gaps, with causes

Missed instruction starts with the declared entry: 872 of 125734.

| cause | routines | instructions | detail |
|---|---|---|---|
| not referenced by anything in the disassembly | 64 | 651 | 55 of them marked unreachable by the disassembly itself; the other 9 are long-call wrappers, bounce stubs and sound helpers that nothing calls (7 of them, 2 to 3 instructions each) and two longer routines nothing calls |
| a dispatcher table inside dead code | 2 | 68 | two routines in bank 05 behind the one dispatcher call the discovery does not reach |
| reached only from missed code | 2 | 75 | a debug handler in bank 04 and the routine it calls |
| inside a found routine | 15 | 78 | the emulation-mode half of the reset code (12 instructions: it runs in the interpreter by design); a frame-step path of the main loop and the second-controller half of the joypad reader (29, nothing branches there); an input path of the name entry (12); 25 single instructions in 11 routines (below) |

The 25 single instructions: 15 stand after an unconditional transfer
(RTS, RTL, JMP, BRA, BRL) where no found code branches to them, one is
an RTS behind a dispatcher table (dead), 7 follow a PLP whose
PHP the analysis does not see (07:EEBE, the one unknown-width
diagnostic), and 2 lie in a decompressor (02:FEBB) that the discovery
reaches only with X 16 bits, where the disassembly reads its
`LDX #$00` at 02:FF66 with X 8 bits; the route of section 6 never
reaches that instruction, so the right width is not decided by a run.

Without the declared entry the polyhedral thread adds 22 routines and
739 instructions (the entry routine, 20 routines of the polyhedral
renderer and one exit stub): the thread's entry routine at 09:F7DE
copies a 13-byte register frame from
09:F810 to WRAM $1F32 with MVN, and the NMI and IRQ handlers switch
stacks into it (TSC; TAX; LDA $1F0A; TCS) and leave through PLB, PLD,
PLY, PLX, PLA and RTI. The thread's PC (09:F81D) and P ($30, M and X 8
bits) stand in that data item, never in an instruction. A pattern for a
routine entered through a stack frame built from ROM data is possible
but not written; the declared entry, read from the ROM bytes of the
frame, covers it, and the attract mode's miss log brings it as well.

Extra instruction starts: 320.

| cause | instructions | detail |
|---|---|---|
| a game table entry that points into free ROM | 295 | entry 0x7F of the overworld overlay table (0E:F664) is 0E:FB64, the start of 0x49C bytes of $FF up to the bank end; the walk decodes them as `SBC long,X`. The disassembly notes the entry as a null pointer; the game never uses that index |
| a dispatcher table read one entry too far | 9 | the table behind the call at 0C:C55E has 8 entries; the next word, the first of a data table, is a code address (0C:FFDA) |
| a game table entry that points at data | 1 | entry 0x25 of the ancilla table points at a data item (08:A8E3); a comment of the disassembly marks it as a wrong pointer that does no harm |
| tables read past their end, into code | 14 | the surplus entries of section 3.1 that land inside instructions of the handlers that follow the table (e.g. 1E:80A0, 1E:80B2 and their successors, 06:F808, 1E:FF01) |
| a wrong width | 1 | 02:FF69 in the decompressor above |

None of the extra blocks is entered by the attract mode or the route
(section 6): they lie where the program does not go, and the dispatcher
checks (PB:PC, M, X) before it enters a block.

## 6. The route through the first minutes

tests/snes-system/zelda-usa-route.txt (the shared input script grammar
of docs/snes-oracle-input-script.md, one step per auto-joypad read)
plays the US release from the power-on through the intro (with the
polyhedral triforce), the title screen, the file select, the name entry
(one letter), the new game, the opening text, Link's bed and house, the
yard with a message and a screen scroll north to the castle screen,
reached near frame 5000; 9000 frames cover it. It was written with
tools/zelda_authority/route_probe.py, which runs the interpreter and
prints WRAM bytes (the game module at $10, the submodule at $11,
Link's state at $5D, the sleep step at $037C, the coordinates at
$20/$22) every
few frames; the script waits on those bytes, so it does not depend on
exact frame counts where the game waits for a button.

The record of the run (snes_headless --interp-only --pc-log over 9000
frames, 116 million instructions) against the maps:

| run | map | distinct instruction starts executed | in the map | not in the map |
|---|---|---|---|---|
| the route, 9000 frames | vectors and reset entry | 18222 (14.5 % of the disassembly's code, 739 functions) | 17529 | 693, all in bank 09: the polyhedral thread |
| the route, 9000 frames | with the declared entry | 18222 | 18222 | 0 |
| the attract mode, 6000 frames without input | vectors and reset entry | 7104 (5.7 %, 280 functions) | 6411 | 693, the polyhedral thread |
| the attract mode, 6000 frames without input | with the declared entry | 7104 | 7104 | 0 |

Every instruction either run executed is an instruction start of the
disassembly; none lies outside it (no RAM code, no data executed), so
neither run enters one of the extra blocks of section 5. The
native check of the same route is section 7.

## 7. Native runs and ctests

The static block set with the declared entry (31508 blocks, 126132
instructions) is generated in 16 parts (`snes_recomp --parts 16`, 17
files of about 4.5 MB) and compiled as snes_headless_native: about 3.5 minutes
with four jobs, at most 1.0 GB per compiler.

| run | result |
|---|---|
| native against the interpreter, 6000 frames without input | every F line byte-identical |
| native, 6000 frames without input | 0 dispatch misses; 12 interpreted instructions (the emulation-mode reset), interpreter share 0.0 % |
| native against the interpreter, the route of section 6, 9000 frames | every F line byte-identical; 0 dispatch misses, 12 interpreted instructions |
| native against aresref, the route, 9000 frames, every field with mclk and pc (compare_oracle.py, stage S, the same input script on both sides) | equal |
| wall clock, RelWithDebInfo | 6000 frames without input: native 31.3 s, interpreter 35.4 s; the route: native 50.5 s, interpreter 57.3 s (the CPU is a small part of the system's time) |

The first native run of the route found one dispatch miss (02:F281,
the return site after an indexed call; section 3.2): the block existed
only in the width of the call. The return-context rule for `JSR (a,X)`
closed it; the block set grew by four blocks.

The ctests (label `local`, skipping without the ROM; configure with
`-DSNES_ZELDA_USA_ROM=...`, and for the German test the existing
`-DSNES_ZELDA_ROM=...`):

- `snes_discovery_zelda_usa_local`, `snes_discovery_zelda_de_local`
  (tests/snes-system/check_discovery.py): snes_recomp with the declared
  entry on each release; at least the measured blocks and instructions
  (USA 31508 and 126132, DE 31518 and 125892) and exactly 56
  indexed-jump, 212 dispatcher, 15 return-trick and 9 pointer-jump
  tables. Another release (by SHA-1) skips.
- `snes_native_zelda_usa_local`, `snes_native_zelda_usa_route_local`
  (tests/snes-system/compare_native.py), only in a tree configured with
  `-DMAMR_SNES_BLOCKS_CPP=` the 17 files of the static block set: the
  native run equals the interpreter over 6000 frames without input and
  over the route, both with no dispatch miss. A binary whose blocks are
  for another ROM skips.

## 8. The German release

The German ROM (SHA-1 2E624949..., PAL) has no disassembly. The US
discovery is carried over in two ways.

### 8.1 Block by block

tools/zelda_authority/de_transfer.py takes the two maps (vectors and
reset entry) and classifies every US block by its bytes and by its
skeleton (the same bytes with address operands, branch distances and
banks masked, the K and S lines of the map):

| US blocks | blocks | instructions | meaning |
|---|---|---|---|
| identical | 9261 (29.7 %) | 46230 (37.1 %) | the same bytes at the same address |
| skeleton | 1398 (4.5 %) | 7020 (5.6 %) | the same instructions at the same address, address operands point elsewhere |
| shifted | 9853 (31.6 %) | 49648 (39.8 %) | the same skeleton at another address of the same bank |
| contained | 14 (0.0 %) | 35 (0.0 %) | the skeleton inside German code cut into other blocks |
| different | 1669 (5.3 %) | 11480 (9.2 %) | no counterpart in the bank |
| trivial | 9020 (28.9 %) | 10302 (8.3 %) | blocks under four bytes, not classified (a lone RTS matches anywhere) |

So 82.5 % of the US instructions lie in blocks whose code the German
build has unchanged, in place or moved within the bank. The moves are
coherent per bank where whole regions moved (bank 01 by -38 or -32
bytes, bank 05 by -6, bank 06 by -5, bank 1D by -4, bank 1E by +3, bank
09 by +40, bank 0D by -160 to -216); banks 0C and 0E, the text and
overlay banks, move by thousands of bytes, and there short blocks may
match a skeleton elsewhere by chance, so "shifted" is an upper bound for
them. The 9.2 % that differ lie in 606 of the 4494 functions with a
block; by the disassembly's reading of those functions they fall into
three groups:

- text and menus: the variable-width font renderer, the name entry (the
  German one has another layout), the file select, copy and erase
  screens, the credits, the player-name insertion into messages, the
  message pointers;
- picture, scenes and timing, most likely the adaptation to the PAL
  console (not checked one by one): the overworld's fixed colour and
  scroll setup, the NMI's update list, the OAM preparation, the attract
  and intro scenes, the mirror warp's HDMA tables, a palette filter;
- the rest, not yet read one by one: two overworld overlays (336 and 167
  instructions), the Y-item menu drawing, the save-file setup, entrance
  cut scenes, the HUD timer and the floor indicator.

### 8.2 The static discovery on the German ROM

The static discovery on the German ROM finds 31381 blocks and 125151
instructions from the vectors and the reset entry, against 31371 and
125391 for the US ROM, with the same table counts (56 indexed jumps,
212 dispatchers, 15 return tricks, 9 pointer jumps); the diagnostics
differ slightly (3 unresolved indirect jumps instead of 2, 11 stop
opcodes instead of 12). The polyhedral thread's frame stands at the
same address with the same bytes in both releases, so zelda-entries.txt
holds for both: with it, 31518 blocks and 125892 instructions.

The check without a disassembly is the German run itself: the attract
mode of 6000 frames (interpreter, --pc-log) executes 7258 distinct
instruction starts. Without the declared entry 6565 of them are in the
static map and the other 693 are the polyhedral thread; with it all
7258 are. A German route (another name-entry layout) and a native
German build of the static set are open (section 10).

## 9. Commands

All from the repository root; `$USA` and `$DE` are the ROM paths,
`$REF` the directory of the clones, `$W` a work directory outside the
repository, `$IPL` the SPC700 IPL dump, `$B` the build tree, `$BN` a
second build tree for the native build.

```text
# the references (lists next to the clones)
python3 -I tools/zelda_authority/usdasm_code.py $REF/usdasm $W/usdasm-usa.txt \
    --dispatcher 00:8781 --dispatcher 00:879C
python3 -I tools/zelda_authority/zelda3_funcs.py $REF/zelda3/src $W/zelda3-funcs.txt

# the discovery before this work, the reset entry, the static discovery (sections 1, 4)
$B/tools/snes_recomp/snes_recomp $USA --no-tables --no-reset --out $W/out0.cpp --map $W/static0.map
$B/tools/snes_recomp/snes_recomp $USA --no-tables --out $W/out0r.cpp --map $W/static0r.map
$B/tools/snes_recomp/snes_recomp $USA --out $W/out1.cpp --map $W/static1.map
$B/tools/snes_recomp/snes_recomp $USA --seeds tests/snes-system/zelda-entries.txt \
    --out $W/out2.cpp --map $W/static2.map
python3 -I tools/zelda_authority/cfg_compare.py $W/static1.map $W/usdasm-usa.txt \
    --zelda3 $W/zelda3-funcs.txt --list $W/cmp-static1

# the miss log of the attract mode (section 1)
$B/tools/snes_headless/snes_headless $USA --frames 6000 --ipl $IPL --miss-log $W/seeds6000.txt \
    --stats --out $W/noblocks.hash
$B/tools/snes_recomp/snes_recomp $USA --seeds $W/seeds6000.txt --no-tables --no-reset \
    --out $W/outs0.cpp --map $W/seeded0.map

# the route (section 6)
python3 -I tools/zelda_authority/route_probe.py $B/tools/snes_headless/snes_headless $USA \
    --frames 9000 --every 50 --ipl $IPL --input tests/snes-system/zelda-usa-route.txt
$B/tools/snes_headless/snes_headless $USA --frames 9000 --ipl $IPL --interp-only \
    --input tests/snes-system/zelda-usa-route.txt --pc-log $W/route-pc.txt --out $W/route.hash
python3 -I tools/zelda_authority/cfg_compare.py $W/static2.map $W/usdasm-usa.txt --pc-log $W/route-pc.txt
$B/tools/snes_headless/snes_headless $USA --frames 6000 --ipl $IPL --interp-only \
    --pc-log $W/usa-pc6000.txt --out $W/usa6000.hash
python3 -I tools/zelda_authority/cfg_compare.py $W/static2.map $W/usdasm-usa.txt --pc-log $W/usa-pc6000.txt

# the native build of the static set (section 7)
$B/tools/snes_recomp/snes_recomp $USA --seeds tests/snes-system/zelda-entries.txt \
    --out $W/zelda_usa_static.cpp --parts 16
cmake -S . -B $BN -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    "-DMAMR_SNES_BLOCKS_CPP=<zelda_usa_static.cpp and the 16 part files, semicolon-separated>" \
    -DSNES_ZELDA_USA_ROM=$USA
cmake --build $BN -j4 --target snes_headless_native
ctest --test-dir $BN -L local -R zelda_usa
ARESREF=... python3 tests/snes-system/compare_oracle.py $BN/tools/snes_headless/snes_headless_native \
    $USA --frames 9000 --ipl $IPL --stages s --input tests/snes-system/zelda-usa-route.txt

# the German release (section 8)
$B/tools/snes_recomp/snes_recomp $DE --out $W/de.cpp --map $W/de-static1.map
python3 -I tools/zelda_authority/de_transfer.py $W/static1.map $W/de-static1.map \
    --usdasm $W/usdasm-usa.txt --list $W/de-transfer
$B/tools/snes_headless/snes_headless $DE --frames 6000 --ipl $IPL --interp-only \
    --pc-log $W/de-pc6000.txt --out $W/de6000.hash

# snes2asm (section 4.5), run from its clone without installing it
PYTHONPATH=$REF/snes2asm python3 -s $REF/snes2asm/bin/snes2asm -o $W/snes2asm-usa -nl $USA
```

## 10. Open points

- The decompressor at 02:FEBB: the discovery reaches it with X 16 bits,
  the disassembly reads `LDX #$00` at 02:FF66 with X 8 bits. A run that
  reaches 02:FF66 decides it; the native build would show a miss there
  if the discovery is wrong.
- A pattern for a thread entered through a stack frame built from ROM
  data (the polyhedral thread), so that the declared entry can go.
- The tables that run past their end (section 3.1): an end rule that
  stops at the start of the code the table's handlers occupy would
  take the 14 misaligned and the 9 data instructions off; they cost
  only output today.
- The German release: a route through its own name entry, a native
  build of its static set, and a reading of the 9.2 % of different US
  blocks against the German code.
