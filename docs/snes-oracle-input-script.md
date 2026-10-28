# Shared input script

One input file drives every oracle and MAMR, so that their hash lines
(snes-oracle-format.md) can be compared. Reference parser and interpreter:
`input_script.py`; aresref (`--input FILE`) and the MesenCE script
(`FH_INPUT=FILE`) implement the same grammar and stepping rule. The MAME
script does not drive inputs (snes-oracles.md). File names without a directory refer to `tools/oracle/snes/`.

## Grammar

One command per line, keywords and button names case-insensitive, `#`
starts a comment, blank lines are ignored.

```text
HOLD <button> [<button> ...]      press the buttons (they stay pressed)
RELEASE <button> [<button> ...]   release them
WAIT <n>                          let n auto-joypad reads pass, n >= 1
WAIT_RAM8 <addr> <value>          wait until the WRAM byte holds value
```

Buttons: `B Y SELECT START UP DOWN LEFT RIGHT A X L R` (controller 1).
In the 16-bit word an auto-joypad read stores in $4218/$4219, B is bit 15
and R bit 4, in this order.

`<addr>` is hex with an optional `$` or `0x`: $7E0000-$7FFFFF, or
$0000-$1FFF for the low-RAM mirror. `<value>` is a hex byte.

## Stepping rule

The script advances once per auto-joypad read (snes-oracle-format.md
section 7), never per emulator frame. At each read the interpreter executes commands until
one blocks:

- `HOLD` and `RELEASE` change the pad state and continue;
- `WAIT n` blocks for n reads: these n reads see the current state, the
  command after it is executed at read n + 1;
- `WAIT_RAM8` checks the byte at the moment of the read; while it differs
  the read sees the current state; once it matches, execution continues
  within the same read;
- after the last command the pad keeps its state for good.

So `HOLD START` / `WAIT 2` / `RELEASE START` holds START for exactly two
reads, starting with the first read. Manual reads of $4016/$4017 see the
state of the most recent auto-joypad read.

## Example

```text
# title screen: wait for the game mode byte, then press START once
WAIT_RAM8 7E0010 01
HOLD START
WAIT 2
RELEASE START
WAIT 120
HOLD A RIGHT
WAIT 30
RELEASE A RIGHT
```

`input_script.py simulate FILE N` prints the joypad word for reads 1 to N
(with WRAM all zero, so a `WAIT_RAM8` on a non-zero value never matches).
