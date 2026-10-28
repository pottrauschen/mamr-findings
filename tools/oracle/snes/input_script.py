#!/usr/bin/env python3
"""Shared input script for the SNES oracles (see docs/snes-oracle-input-script.md).

Reference parser and interpreter. The C++ (aresref) and Lua (MesenCE)
front ends implement the same grammar and the same stepping rule.

    input_script.py check SCRIPT          parse, print the command list
    input_script.py simulate SCRIPT N     joypad words for reads 1..N with
                                          WRAM all zero (no WAIT_RAM8 match)
    input_script.py selftest

Exit codes: 0 success, 1 parse error or failed self test, 3 usage error.
"""
import sys

BUTTONS = ["B", "Y", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT", "A", "X", "L", "R"]
# Bit of each button in the 16-bit joypad word as auto-read into
# $4218/$4219 (JOY1L/JOY1H): B is bit 15, R is bit 4.
BUTTON_BIT = {name: 15 - i for i, name in enumerate(BUTTONS)}


class ScriptError(ValueError):
    pass


def parse_addr(tok):
    t = tok.lstrip("$")
    if t.lower().startswith("0x"):
        t = t[2:]
    v = int(t, 16)
    if 0x7E0000 <= v <= 0x7FFFFF:
        return v - 0x7E0000
    if v <= 0x1FFF:
        return v                      # low-RAM mirror in bank $00
    raise ScriptError("WRAM address out of range: " + tok)


def parse(text):
    """Returns a list of commands: ("HOLD", mask), ("RELEASE", mask),
    ("WAIT", n), ("WAIT_RAM8", offset, value)."""
    cmds = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tok = line.split()
        op = tok[0].upper()
        try:
            if op in ("HOLD", "RELEASE"):
                if len(tok) < 2:
                    raise ScriptError("%s needs at least one button" % op)
                mask = 0
                for b in tok[1:]:
                    b = b.upper()
                    if b not in BUTTON_BIT:
                        raise ScriptError("unknown button " + b)
                    mask |= 1 << BUTTON_BIT[b]
                cmds.append((op, mask))
            elif op == "WAIT":
                if len(tok) != 2 or int(tok[1]) < 1:
                    raise ScriptError("WAIT needs one count >= 1")
                cmds.append(("WAIT", int(tok[1])))
            elif op == "WAIT_RAM8":
                if len(tok) != 3:
                    raise ScriptError("WAIT_RAM8 needs an address and a value")
                val = int(tok[2].lstrip("$").replace("0x", ""), 16)
                if not 0 <= val <= 0xFF:
                    raise ScriptError("value out of range")
                cmds.append(("WAIT_RAM8", parse_addr(tok[1]), val))
            else:
                raise ScriptError("unknown command " + tok[0])
        except ValueError as e:
            raise ScriptError("line %d: %s" % (n, e))
    return cmds


class Player:
    """Steps the script once per auto-joypad read.

    At read k the interpreter executes commands until one blocks:
    HOLD/RELEASE change the pad and continue; WAIT n blocks for n reads
    (the n reads see the current pad); WAIT_RAM8 blocks while the WRAM byte
    differs and continues within the same read once it matches. After the
    last command the pad keeps its state."""

    def __init__(self, cmds):
        self.cmds = cmds
        self.pc = 0
        self.pad = 0
        self.remaining = None
        self.reads = 0

    def on_read(self, ram8=lambda off: 0):
        self.reads += 1
        while self.pc < len(self.cmds):
            c = self.cmds[self.pc]
            if c[0] == "HOLD":
                self.pad |= c[1]
            elif c[0] == "RELEASE":
                self.pad &= ~c[1]
            elif c[0] == "WAIT":
                if self.remaining is None:
                    self.remaining = c[1]
                if self.remaining > 0:
                    self.remaining -= 1
                    return self.pad
                self.remaining = None
            elif c[0] == "WAIT_RAM8":
                if ram8(c[1]) != c[2]:
                    return self.pad
            self.pc += 1
        return self.pad


def selftest():
    ok = True

    def check(cond, what):
        nonlocal ok
        if not cond:
            print("FAIL", what)
            ok = False

    p = Player(parse("HOLD START\nWAIT 2\nRELEASE start\nHOLD a b # both\nWAIT 1\nRELEASE A B\n"))
    seq = [p.on_read() for _ in range(5)]
    st, a, b = 1 << 12, 1 << 7, 1 << 15
    check(seq == [st, st, a | b, 0, 0], "hold/wait sequence %s" % seq)
    ram = {0x10: 0}
    p = Player(parse("WAIT_RAM8 7E0010 07\nHOLD A\nWAIT 1\nRELEASE A"))
    out = []
    for k in range(6):
        if k == 3:
            ram[0x10] = 7
        out.append(p.on_read(lambda off: ram.get(off, 0)))
    check(out == [0, 0, 0, a, 0, 0], "wait_ram8 sequence %s" % out)
    check(parse_addr("$0010") == 0x10 and parse_addr("7F0000") == 0x10000, "addresses")
    for bad in ["HOLD", "HOLD Z", "WAIT 0", "WAIT_RAM8 7E0000", "WAIT_RAM8 800000 00", "JUMP 1"]:
        try:
            parse(bad)
            check(False, "accepted bad line " + bad)
        except ScriptError:
            pass
    check(Player([]).on_read() == 0, "empty script")
    print("input_script selftest:", "ok" if ok else "FAILED")
    return 0 if ok else 1


def main(argv):
    if len(argv) >= 2 and argv[1] == "selftest":
        return selftest()
    if len(argv) >= 3 and argv[1] in ("check", "simulate"):
        try:
            with open(argv[2]) as f:
                cmds = parse(f.read())
        except ScriptError as e:
            print("%s: %s" % (argv[2], e), file=sys.stderr)
            return 1
        if argv[1] == "check":
            for c in cmds:
                print(*c)
            return 0
        p = Player(cmds)
        for k in range(1, int(argv[3]) + 1 if len(argv) > 3 else 61):
            print(k, "%04x" % p.on_read())
        return 0
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
