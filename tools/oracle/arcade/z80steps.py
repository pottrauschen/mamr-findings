#!/usr/bin/env python3
"""Z80 machine-cycle steps of MAME 0.285's Z80 core, from its z80.lst.

MAME's Z80 (src/devices/cpu/z80/z80.lst, expanded by z80make.py) runs an
instruction as a sequence of steps. A step is either a bus access
("N !! access": the access happens at the start of the step, then N cycles
pass) or N internal cycles ("+ N"). The CPU checks its cycle budget after
every step and stops there when it is used up, so a time slice of MAME's
scheduler can end inside an instruction (docs/arcade-oracle-format.md
section 3). MAMR's stage M (games/ikari/ikari_stage_m.h) needs these steps
to stop where MAME stops; this script derives them from the listing.

    z80steps.py dump Z80_LST [KEY...]
        the step variants of the given instructions (or all), e.g. "77",
        "cb46", "dd21", "ddcb06", "ed b0" (hex bytes of the opcode chain,
        prefixes included, displacement and immediates left out)
    z80steps.py emit Z80_LST OUT
        write the C++ table runtime/z80_steps_table.inc
    z80steps.py check Z80_LST SST_DIR [--limit N]
        compare the steps with the SingleStepTests z80 cycle traces (a
        second emulator model, class IMPLEMENTATION): every test's length,
        and the start cycle and kind of every bus access (opcode and
        operand fetches included) must match one variant
    z80steps.py selftest Z80_LST

Step kinds: F opcode fetch (M1), A operand fetch, R data read, W data
write, I port read, O port write, - internal. F and A are not bus calls in
MAMR (code bytes come from the code image); R, W, I and O are.

The listing is read as data (BSD-3-Clause, copyright Juergen Buchmueller,
Andrei I. Holub); the table this script writes is derived from it and
listed in third_party/mame/LICENSE.
"""
import itertools
import json
import re
import sys

CYCLES = {"m_memrq_cycles": 3, "m_m1_cycles-2": 2, "m_m1_cycles": 4, "m_iorq_cycles": 4}
KIND_OF_ACCESS = [
    ("opcode_read", "F"), ("arg_read", "A"), ("data_read", "R"), ("stack_read", "R"),
    ("data_write", "W"), ("stack_write", "W"), ("m_io.read", "I"), ("m_io.write", "O"),
]


class Listing:
    def __init__(self, path):
        self.macros = {}   # name -> (args, lines)
        self.entries = {}  # "00ab" -> lines
        cur = None
        with open(path, encoding="ascii") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line.strip() or line.lstrip().startswith("#") and not line.startswith(("\t", " ")):
                    if not line.strip():
                        continue
                    if line.startswith("#"):
                        continue
                if line.startswith(("\t", " ", "{", "}")):
                    if cur is not None:
                        cur.append(line.strip())
                    continue
                tok = line.split()
                if tok[0] == "macro":
                    name = tok[1]
                    if ":" in name:  # a variant for another CPU type (r800:, z80n:, ...)
                        cur = []
                        continue
                    args = tok[2:]
                    cur = []
                    self.macros[name] = (args, cur)
                elif re.fullmatch(r"[0-9a-f]{4}", tok[0]):
                    cur = []
                    self.entries[tok[0]] = cur
                elif re.fullmatch(r"[0-9a-f]{2}:[0-9a-f]{4}", tok[0]) or ":" in tok[0]:
                    cur = []  # a variant opcode for another CPU type
                else:
                    cur = None


def strip_comment(s):
    i = s.find("//")
    return s[:i].strip() if i >= 0 else s.strip()


def subst(lines, names, values):
    out = []
    for l in lines:
        for n, v in sorted(zip(names, values), key=lambda p: -len(p[0])):
            l = l.replace(n, v)
        out.append(l)
    return out


def split_args(s):
    s = s.strip()
    if not s:
        return []
    return [a.strip() for a in s.split(",")]


class Expander:
    """Expands an entry into its step variants: a list of tuples of
    (cycles, kind) per possible path through the conditionals."""

    def __init__(self, listing):
        self.l = listing

    def expand_lines(self, lines, ops):
        """lines: statements; ops: remaining opcode bytes for jump_prefixed.
        Returns a list of (steps, ops_left)."""
        variants = [((), list(ops))]
        i = 0
        while i < len(lines):
            s = strip_comment(lines[i])
            i += 1
            if not s:
                continue
            m = re.match(r"^(?:\}\s*)?if\s*\(.*\)\s*\{$", s) if s.startswith("if") else None
            if m:
                branches, i = self.collect_if(lines, i - 1)
                new = []
                for steps, ops_left in variants:
                    for blines in branches:
                        for bsteps, bops in self.expand_lines(blines, ops_left):
                            new.append((steps + bsteps, bops))
                variants = dedupe(new)
                continue
            if s == "{" or s == "}" or s.startswith("} else"):
                continue
            if s.startswith("if") and not s.endswith("{"):
                continue  # one-statement conditional: never guards a step
            mm = re.match(r"^(\S+)\s*!!\s*(.*)$", s)
            if mm:
                cyc = CYCLES.get(mm.group(1).replace(" ", ""))
                if cyc is None:
                    cyc = int(mm.group(1))
                kind = next((k for key, k in KIND_OF_ACCESS if key in mm.group(2)), None)
                if kind is None:
                    raise ValueError("unknown access: %s" % s)
                variants = [(steps + ((cyc, kind),), o) for steps, o in variants]
                continue
            mm = re.match(r"^\+\s*(\d+)$", s)
            if mm:
                variants = [(steps + ((int(mm.group(1)), "-"),), o) for steps, o in variants]
                continue
            mm = re.match(r"^(\d+)\s*\*\s*@(\w+)\s*(.*)$", s)
            if mm:
                for _ in range(int(mm.group(1))):
                    variants = self.call(variants, mm.group(2), mm.group(3))
                continue
            mm = re.match(r"^@(\w+)\s*(.*)$", s)
            if mm:
                if mm.group(1) == "jump":
                    variants = self.jump(variants, mm.group(2).strip(), None)
                elif mm.group(1) == "jump_prefixed":
                    variants = self.jump(variants, None, int(mm.group(2).strip(), 16))
                else:
                    variants = self.call(variants, mm.group(1), mm.group(2))
                continue
            # any other statement: no step
        return variants

    def collect_if(self, lines, i):
        """lines[i] is 'if (...) {'. Returns (branches, index after the
        whole if/else chain); a missing else adds an empty branch."""
        branches = []
        has_else = False
        while True:
            depth = 1
            i += 1
            body = []
            while True:
                s = strip_comment(lines[i])
                opens = s.count("{")
                closes = s.count("}")
                if s.startswith("}") and depth == 1:
                    break
                depth += opens - closes
                body.append(lines[i])
                i += 1
            branches.append(body)
            s = strip_comment(lines[i])
            if re.match(r"^\}\s*else\s+if\s*\(.*\)\s*\{$", s):
                continue
            if re.match(r"^\}\s*else\s*\{$", s):
                has_else = True
                depth = 1
                i += 1
                body = []
                while True:
                    s2 = strip_comment(lines[i])
                    if s2.startswith("}") and depth == 1:
                        break
                    depth += s2.count("{") - s2.count("}")
                    body.append(lines[i])
                    i += 1
                branches.append(body)
                i += 1
                break
            i += 1
            break
        if not has_else:
            branches.append([])
        return branches, i

    def call(self, variants, name, argstr):
        if name not in self.l.macros:
            raise ValueError("unknown macro %s" % name)
        names, lines = self.l.macros[name]
        body = subst(lines, names, split_args(argstr)) if names else lines
        new = []
        for steps, ops in variants:
            for s2, o2 in self.expand_lines(body, ops):
                new.append((steps + s2, o2))
        return dedupe(new)

    def jump(self, variants, entry, prefix):
        new = []
        for steps, ops in variants:
            if prefix is not None:
                if not ops:
                    raise ValueError("jump_prefixed without an opcode byte")
                key = "%02x%02x" % (prefix, ops[0])
                rest = ops[1:]
            else:
                key = entry
                rest = ops
            for s2, o2 in self.expand_lines(self.l.entries[key], rest):
                new.append((steps + s2, o2))
        return dedupe(new)

    def instruction(self, opbytes):
        """Step variants of the instruction with these opcode bytes (the
        prefix chain and the final opcode; DD CB d op given as dd cb op):
        the opcode fetch of the ROP entry, then the entry of the first
        byte."""
        rop = self.expand_lines(["@rop"], [])
        variants = []
        for steps, _ in rop:
            for s2, o2 in self.expand_lines(self.l.entries["00%02x" % opbytes[0]], list(opbytes[1:])):
                if o2:
                    raise ValueError("unused opcode bytes for %s" % opbytes)
                variants.append(steps + s2)
        return sorted(set(variants), key=lambda v: (sum(c for c, _ in v), v))


def dedupe(variants):
    seen, out = set(), []
    for v in variants:
        key = (v[0], tuple(v[1]))
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def all_keys():
    keys = []
    for op in range(256):
        if op in (0xCB, 0xDD, 0xED, 0xFD):
            continue
        keys.append((op,))
    for op in range(256):
        keys.append((0xCB, op))
        keys.append((0xED, op))
    for p in (0xDD, 0xFD):
        for op in range(256):
            if op == 0xCB:
                continue
            keys.append((p, op))
        for op in range(256):
            keys.append((p, 0xCB, op))
    return keys


def fmt(v):
    return " ".join("%d%s" % (c, k) for c, k in v)


def emit(listing, out):
    ex = Expander(listing)
    rows = []
    for key in all_keys():
        try:
            variants = ex.instruction(key)
        except ValueError as e:
            if "without an opcode byte" in str(e):
                continue  # a prefix followed by another prefix: two instructions for MAMR
            raise
        totals = [sum(c for c, _ in v) for v in variants]
        if len(set(totals)) != len(totals):
            raise ValueError("ambiguous totals for %s: %s" % (bytes(key).hex(), totals))
        # the runtime times data accesses from the longest variant before
        # the path is known: every variant's data accesses must start at
        # the same cycles as the longest one's first ones
        data = [[(pos, k) for (pos, k), (_c, kk) in zip(variant_accesses(v), [x for x in v if x[1] != "-"])
                 if kk in "RWIO"] for v in variants]
        longest = data[totals.index(max(totals))]
        for d in data:
            if d != longest[:len(d)]:
                raise ValueError("data accesses of %s differ between paths: %s" % (bytes(key).hex(), data))
        rows.append((key, variants))
    with open(out, "w", encoding="ascii") as f:
        f.write("// GENERATED by tools/oracle/arcade/z80steps.py from MAME 0.285\n"
                "// src/devices/cpu/z80/z80.lst (BSD-3-Clause, copyright Juergen Buchmueller,\n"
                "// Andrei I. Holub); derived work, notice in third_party/mame/LICENSE.\n"
                "// Do not edit. One line per instruction and path: the prefix group\n"
                "// (0 none, 1 CB, 2 ED, 3 DD, 4 FD, 5 DD CB, 6 FD CB), the opcode, then the\n"
                "// steps as a string of (cycles, kind) pairs (runtime/z80_steps.h).\n")
        group = {(): 0, (0xCB,): 1, (0xED,): 2, (0xDD,): 3, (0xFD,): 4, (0xDD, 0xCB): 5, (0xFD, 0xCB): 6}
        for key, variants in rows:
            g = group[tuple(key[:-1])]
            for v in variants:
                f.write('{%d, 0x%02X, "%s"},\n' % (g, key[-1], "".join("%d%s" % (c, k) for c, k in v)))
    return rows


def sst_accesses(cycles):
    """[(start cycle, kind)] of the bus accesses of an SST cycle trace: a
    read or write strobe marks T2 (memory) or T2/T3 (I/O) of a machine
    cycle; the access starts one cycle earlier (T1). r-m- read, -wm- write,
    r--i port read, -w-i port write."""
    out = []
    prev = "----"
    for i, (_addr, _data, pins) in enumerate(cycles):
        if pins != "----" and pins != prev:
            kind = {"r-m-": "r", "-wm-": "w", "r--i": "I", "-w-i": "O"}.get(pins)
            if kind is None:
                raise ValueError("pins %r" % pins)
            out.append((i - 1 if kind in "rw" else i - 2, kind))
        prev = pins
    return out


def variant_accesses(v):
    pos, out = 0, []
    for c, k in v:
        if k != "-":
            out.append((pos, {"F": "r", "A": "r", "R": "r", "W": "w", "I": "I", "O": "O"}[k]))
        pos += c
    return out


def check(path, sstdir, limit=None):
    import os
    ex = Expander(Listing(path))
    bad = files = tests = 0
    for name in sorted(os.listdir(sstdir)):
        if not name.endswith(".json"):
            continue
        parts = [p for p in name[:-5].split() if p != "__"]
        key = tuple(int(p, 16) for p in parts)
        try:
            variants = ex.instruction(key)
        except (ValueError, KeyError):
            continue
        cands = [(sum(c for c, _ in v), variant_accesses(v)) for v in variants]
        with open(os.path.join(sstdir, name)) as f:
            data = json.load(f)
        files += 1
        for t in data[:limit]:
            tests += 1
            got = (len(t["cycles"]), sst_accesses(t["cycles"]))
            if got not in cands:
                bad += 1
                if bad <= 20:
                    print("%s %s: sst %s, mame %s" % (name, t["name"], got, cands))
    print("z80steps check: %d files, %d tests, %d without a matching variant" % (files, tests, bad))
    return bad == 0


def selftest(path):
    ex = Expander(Listing(path))
    want = {
        (0x00,): ["2F 2-"],                         # NOP: 4
        (0x77,): ["2F 2- 3W"],                      # LD (HL),A: write at 4
        (0xC5,): ["2F 2- 1- 3W 3W"],                # PUSH BC: writes at 5, 8
        (0xE3,): ["2F 2- 3R 3R 1- 3W 3W 1- 1-"],    # EX (SP),HL: 19
        (0x18,): ["2F 2- 3A 1- 1- 1- 1- 1-"],       # JR: 12
        (0xED, 0xB0): ["2F 2- 2F 2- 3R 3W 1- 1-", "2F 2- 2F 2- 3R 3W 1- 1- 1- 1- 1- 1- 1-"],
    }
    ok = True
    for key, exp in want.items():
        got = [fmt(v) for v in ex.instruction(key)]
        if got != exp:
            print("z80steps: %s: %s, expected %s" % (bytes(key).hex(), got, exp))
            ok = False
    print("z80steps selftest: %s" % ("ok" if ok else "FAILED"))
    return ok


def main(argv):
    if len(argv) >= 3 and argv[1] == "dump":
        ex = Expander(Listing(argv[2]))
        keys = [tuple(bytes.fromhex(k.replace(" ", ""))) for k in argv[3:]] or all_keys()
        for key in keys:
            for v in ex.instruction(key):
                print("%-8s %3d  %s" % (bytes(key).hex(), sum(c for c, _ in v), fmt(v)))
        return 0
    if len(argv) == 4 and argv[1] == "emit":
        emit(Listing(argv[2]), argv[3])
        return 0
    if len(argv) >= 4 and argv[1] == "check":
        limit = int(argv[5]) if len(argv) == 6 and argv[4] == "--limit" else None
        return 0 if check(argv[2], argv[3], limit) else 1
    if len(argv) == 3 and argv[1] == "selftest":
        return 0 if selftest(argv[2]) else 1
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main(sys.argv))
