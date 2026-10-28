#!/usr/bin/env python3
"""Decode the T line of AccuracyCoin runs (docs/nes-oracle-format.md
section 8) into per-test results, with the test names read from the ROM's
own source (AccuracyCoin.asm of the pinned commit, outside the repository).

    accuracycoin.py selftest
    accuracycoin.py decode ASM HASHFILE [--all]
        print the tally and every test that did not pass (with --all every
        test); exit 0 when every counted test passed, 1 otherwise
    accuracycoin.py diff ASM HASHFILE_A HASHFILE_B
        the tests whose result differs between two runs; exit 0 when none

A result byte (AccuracyCoin.asm, AutomaticallyRunEveryTestInROM): 0 not
run, $FF skipped, bit 0 set passed, else failed. The code printed beside a
result is the byte shifted right by two (for a pass it marks one of several
accepted behaviours). Tests that store their result on page 3 are the
"DRAW" tests, which print information and are not counted.

Exit codes: 0 all passed / no difference, 1 otherwise, 2 input missing,
3 usage error.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hashline as H  # noqa: E402

RESULT_DEF = re.compile(r"^(result_\w+)\s*=\s*\$([0-9A-Fa-f]+)")
SUITE = re.compile(r"^(Suite_\w+):")
ENTRY = re.compile(r"^\s*(table|tblf1|tblf2)\s+(.*)$")
STR_DEF = re.compile(r"^(str_\w+)\s*=\s*\$([0-9A-Fa-f]+)")
STR_TEXT = {"str_Indirect": "(Indirect)", "str_ZeroPage": "Zero Page", "str_Absolute": "Absolute",
            "str_Immediate": "Immediate"}


def split_args(text):
    """Macro arguments: quoted strings and bare tokens, comma separated."""
    out, cur, quoted = [], "", False
    for ch in text:
        if ch == '"':
            quoted = not quoted
            cur += ch
        elif ch == "," and not quoted:
            out.append(cur.strip())
            cur = ""
        elif ch == ";" and not quoted:
            break
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def parse_asm(path):
    """Returns the list of tests in ROM order: dicts with suite (title),
    page (index of the suite in TableTable, the menu page), index (the
    entry's position on its page, DRAW tests included), name, symbol,
    address."""
    results, tests = {}, []
    suite = None
    label = None
    index = 0
    pending_title = False
    with open(path, encoding="latin-1") as f:
        lines = f.read().splitlines()
    pages = []
    in_table = False
    for line in lines:
        m = RESULT_DEF.match(line)
        if m:
            results[m.group(1)] = int(m.group(2), 16)
        if line.startswith("TableTable:"):
            in_table = True
        elif line.startswith("EndTableTable:"):
            in_table = False
        elif in_table:
            w = re.match(r"^\s*\.word\s+(Suite_\w+)", line)
            if w:
                pages.append(w.group(1))
    for line in lines:
        m = SUITE.match(line)
        if m:
            label = m.group(1)
            suite = label[len("Suite_"):]
            index = 0
            pending_title = True
            continue
        if suite is None:
            continue
        if pending_title:
            t = re.match(r'^\s*\.byte\s+"([^"]*)"', line)
            if t:
                suite = t.group(1)
                pending_title = False
                continue
        m = ENTRY.match(line)
        if not m:
            continue
        args = split_args(m.group(2))
        name_parts = []
        symbol = None
        for a in args:
            if a.startswith('"'):
                name_parts.append(a.strip('"'))
            elif a in STR_TEXT:
                name_parts.append(STR_TEXT[a])
            elif a.startswith("result_"):
                symbol = a
        if symbol is None or symbol not in results:
            continue
        name = " ".join(p.strip() for p in name_parts if p.strip())
        tests.append({"suite": suite, "page": pages.index(label) if label in pages else -1, "index": index,
                      "name": name, "symbol": symbol, "address": results[symbol]})
        index += 1
    return tests


def test_at(tests, page, index):
    """The test the ROM runs at menu page and index (zero page $14, $16)."""
    for t in tests:
        if t["page"] == page and t["index"] == index:
            return t
    return None


def decode_byte(b):
    if b == 0:
        return "not run", None
    if b == 0xFF:
        return "skipped", None
    code = b >> 2
    if b & 1:
        return "pass", code if code else None
    return "fail", code


def read_t(path):
    _, _, tallies = H.read_file(path)
    if not tallies:
        raise ValueError("no T line in " + path)
    t = tallies[-1]
    passed, run = (int(x) for x in t["tally"].split("/"))
    return t["n"], passed, run, bytes.fromhex(t["results"])


def results_of(tests, data):
    rows = []
    for t in tests:
        a = t["address"]
        if not 0x400 <= a <= 0x4FF:
            continue
        status, code = decode_byte(data[a - 0x400])
        rows.append(dict(t, status=status, code=code))
    return rows


def decode(asm, path, show_all=False, out=print):
    tests = parse_asm(asm)
    frame, passed, run, data = read_t(path)
    rows = results_of(tests, data)
    counted = [r for r in rows if r["status"] != "skipped"]
    npass = sum(1 for r in counted if r["status"] == "pass")
    out("frame %d: ROM tally %d/%d; decoded %d tests, %d passed, %d failed, %d skipped, %d not run" % (
        frame, passed, run, len(rows), npass, sum(1 for r in rows if r["status"] == "fail"),
        sum(1 for r in rows if r["status"] == "skipped"), sum(1 for r in rows if r["status"] == "not run")))
    for r in rows:
        if show_all or r["status"] != "pass":
            out("  %-28s %-34s $%03X %s%s" % (r["suite"][:28], r["name"][:34], r["address"], r["status"],
                                             "" if r["code"] is None else " code %X" % r["code"]))
    return npass == len(counted) and passed == run


def diff(asm, path_a, path_b, out=print):
    tests = parse_asm(asm)
    ra = results_of(tests, read_t(path_a)[3])
    rb = results_of(tests, read_t(path_b)[3])
    n = 0
    for a, b in zip(ra, rb):
        if (a["status"], a["code"]) != (b["status"], b["code"]):
            n += 1
            out("  %-28s %-34s %s%s / %s%s" % (a["suite"][:28], a["name"][:34], a["status"],
                                              "" if a["code"] is None else " %X" % a["code"], b["status"],
                                              "" if b["code"] is None else " %X" % b["code"]))
    out("%d tests differ" % n)
    return n == 0


def selftest():
    import tempfile
    fails = []
    asm = "\n".join([
        "result_A = $0401", "result_B = $402", "result_D = $0300",
        "TableTable:", "\t.word Suite_X", "EndTableTable:",
        "Suite_X:", '\t.byte "Page X", $FF',
        '\ttable "Test A", $FF, result_A, TEST_A',
        '\ttblf1 "$07   SLO", str_ZeroPage, $FF, result_B, TEST_B',
        '\ttable "Draw D", $FF, result_D, TEST_D',
        "\t.byte $FF", ""])
    d = tempfile.mkdtemp()
    try:
        ap = os.path.join(d, "a.asm")
        with open(ap, "w") as f:
            f.write(asm)
        tests = parse_asm(ap)
        if [t["name"] for t in tests] != ["Test A", "$07   SLO Zero Page", "Draw D"]:
            fails.append("parse names %r" % [t["name"] for t in tests])
        if tests[1]["address"] != 0x402 or tests[0]["suite"] != "Page X":
            fails.append("parse address/suite")
        if tests[2]["index"] != 2 or tests[0]["page"] != 0 or test_at(tests, 0, 1)["symbol"] != "result_B":
            fails.append("page/index")
        if decode_byte(1) != ("pass", None) or decode_byte(0x0A) != ("fail", 2) or decode_byte(0xFF)[0] != "skipped" \
                or decode_byte(0x05) != ("pass", 1):
            fails.append("decode_byte")
        res = bytearray(256)
        res[1], res[2] = 1, 0x0A
        hp = os.path.join(d, "r.hash")
        with open(hp, "w") as f:
            f.write(H.format_header("t", None) + "\n" + H.format_t(9, 1, 2, bytes(res)) + "\n")
        logs = []
        if decode(ap, hp, out=logs.append) or "2 tests, 1 passed, 1 failed" not in logs[0]:
            fails.append("decode %r" % logs[:1])
    finally:
        import shutil
        shutil.rmtree(d)
    if fails:
        print("accuracycoin selftest FAILED:", ", ".join(fails))
        return 1
    print("accuracycoin selftest ok")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    cmd = argv[1]
    if cmd == "selftest":
        return selftest()
    args = argv[2:]
    show_all = "--all" in args
    args = [a for a in args if a != "--all"]
    for p in args:
        if not os.path.exists(p):
            print("missing: " + p)
            return 2
    try:
        if cmd == "decode" and len(args) == 2:
            return 0 if decode(args[0], args[1], show_all) else 1
        if cmd == "diff" and len(args) == 3:
            return 0 if diff(args[0], args[1], args[2]) else 1
    except ValueError as e:
        print("accuracycoin.py: " + str(e))
        return 1
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
