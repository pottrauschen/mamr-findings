#!/usr/bin/env python3
"""Kabuki views of the Super Pang program ROM, reference implementation.

A second, independent statement of the decryption in MAME 0.285
src/mame/capcom/kabuki.cpp (BSD-3-Clause, Nicola Salmoria), written as
in that file (two bit-pair swap functions); romtool's C++ version
(tools/romtool/kabuki.h) and MAME's own decrypted views must agree with
it byte for byte (docs/spang-oracles.md section 6).

    kabuki.py selftest
    kabuki.py views ROMDIR OUTDIR
        maincpu_op.bin / maincpu_data.bin (0x50000 bytes each, MAME's
        region layout) from the program files in ROMDIR (by name or SHA-1)
    kabuki.py compare DIR_A DIR_B [--mame]
        compare two view directories; with --mame DIR_B holds MAME's
        dump (views_mame.lua): its opcode space for the fixed part and
        each bank, and the data views

Exit codes: 0 equal / success, 1 different, 2 ROM missing, 3 usage error.
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # no __pycache__ in the source tree
import romset  # noqa: E402

SPANG = (0x45670123, 0x45670123, 0x5852, 0x43)  # swap_key1, swap_key2, addr_key, xor_key
REGION = 0x50000
BANKS = 16


def bitswap1(s, key, sel):
    if sel & (1 << ((key >> 0) & 7)):
        s = (s & 0xFC) | ((s & 0x01) << 1) | ((s & 0x02) >> 1)
    if sel & (1 << ((key >> 4) & 7)):
        s = (s & 0xF3) | ((s & 0x04) << 1) | ((s & 0x08) >> 1)
    if sel & (1 << ((key >> 8) & 7)):
        s = (s & 0xCF) | ((s & 0x10) << 1) | ((s & 0x20) >> 1)
    if sel & (1 << ((key >> 12) & 7)):
        s = (s & 0x3F) | ((s & 0x40) << 1) | ((s & 0x80) >> 1)
    return s


def bitswap2(s, key, sel):
    if sel & (1 << ((key >> 12) & 7)):
        s = (s & 0xFC) | ((s & 0x01) << 1) | ((s & 0x02) >> 1)
    if sel & (1 << ((key >> 8) & 7)):
        s = (s & 0xF3) | ((s & 0x04) << 1) | ((s & 0x08) >> 1)
    if sel & (1 << ((key >> 4) & 7)):
        s = (s & 0xCF) | ((s & 0x10) << 1) | ((s & 0x20) >> 1)
    if sel & (1 << ((key >> 0) & 7)):
        s = (s & 0x3F) | ((s & 0x40) << 1) | ((s & 0x80) >> 1)
    return s


def rol(s):
    return ((s & 0x7F) << 1) | ((s & 0x80) >> 7)


def bytedecode(s, k1, k2, x, sel):
    s = bitswap1(s, k1 & 0xFFFF, sel & 0xFF)
    s = rol(s)
    s = bitswap2(s, k1 >> 16, sel & 0xFF)
    s ^= x
    s = rol(s)
    s = bitswap2(s, k2 & 0xFFFF, sel >> 8)
    s = rol(s)
    s = bitswap1(s, k2 >> 16, sel >> 8)
    return s


def op(v, a, k=SPANG):
    return bytedecode(v, k[0], k[1], k[3], (a + k[2]) & 0xFFFF)


def data(v, a, k=SPANG):
    return bytedecode(v, k[0], k[1], k[3], ((a ^ 0x1FC0) + k[2] + 1) & 0xFFFF)


def views(raw, k=SPANG):
    """MAME mitchell_decode: fixed part at its addresses, each 16 KiB bank
    as if at 0x8000."""
    o, d = bytearray(raw), bytearray(raw)
    for a in range(0x8000):
        o[a], d[a] = op(raw[a], a, k), data(raw[a], a, k)
    for b in range(BANKS):
        for i in range(0x4000):
            x = 0x10000 + b * 0x4000 + i
            o[x], d[x] = op(raw[x], 0x8000 + i, k), data(raw[x], 0x8000 + i, k)
    return bytes(o), bytes(d)


def load_program(romdir):
    import tomllib
    with open(romset.DEFAULT_MANIFEST, "rb") as f:
        t = tomllib.load(f)
    raw = bytearray(REGION)
    for e in t["cpu"][0]["files"]:
        p = romset.find(romdir, e["file"], e["size"], e["sha1"])
        if p is None:
            return None
        with open(p, "rb") as f:
            raw[e["offset"]:e["offset"] + e["size"]] = f.read()
    return bytes(raw)


def rol_n(v, n):
    for _ in range(n):
        v = rol(v)
    return v


def selftest():
    # select = 0 swaps nothing: decode = rol3(src) ^ rol2(xor_key)
    for k in (SPANG, (0x01234567, 0x76543210, 0x6548, 0x24)):
        a = (-k[2]) & 0xFFFF          # opcode select 0
        for v in range(256):
            assert op(v, a, k) == rol_n(v, 3) ^ rol_n(k[3], 2)
        ad = ((-k[2] - 1) & 0xFFFF) ^ 0x1FC0   # data select 0
        for v in range(256):
            assert data(v, ad, k) == rol_n(v, 3) ^ rol_n(k[3], 2)
    # every select gives a permutation of the 256 byte values
    for sel in (0x0001, 0x00FF, 0x8000, 0xFFFF, 0x1234):
        assert len({bytedecode(v, SPANG[0], SPANG[1], SPANG[3], sel) for v in range(256)}) == 256
    print("kabuki selftest ok")
    return 0


def main(argv):
    if len(argv) >= 2 and argv[1] == "selftest":
        return selftest()
    if len(argv) == 4 and argv[1] == "views":
        raw = load_program(argv[2])
        if raw is None:
            print("kabuki.py: program ROM incomplete in " + argv[2])
            return 2
        o, d = views(raw)
        os.makedirs(argv[3], exist_ok=True)
        for name, v in (("maincpu_op.bin", o), ("maincpu_data.bin", d)):
            with open(os.path.join(argv[3], name), "wb") as f:
                f.write(v)
            print("%s sha1 %s" % (name, hashlib.sha1(v).hexdigest()))
        return 0
    if len(argv) >= 4 and argv[1] == "compare":
        a, b = argv[2], argv[3]
        mame = "--mame" in argv
        oa = open(os.path.join(a, "maincpu_op.bin"), "rb").read()
        da = open(os.path.join(a, "maincpu_data.bin"), "rb").read()
        ok = True
        if mame:
            # MAME's opcode space 0000-7FFF and 8000-BFFF per bank, its
            # program space likewise (data view), and its decrypted region
            checks = [("opcodes 0000-7fff", open(os.path.join(b, "op_fixed.bin"), "rb").read(), oa[:0x8000]),
                      ("program 0000-7fff", open(os.path.join(b, "data_fixed.bin"), "rb").read(), da[:0x8000]),
                      ("region :maincpu", open(os.path.join(b, "region.bin"), "rb").read(), da)]
            for bk in range(BANKS):
                lo = 0x10000 + bk * 0x4000
                checks.append(("opcodes bank %d" % bk, open(os.path.join(b, "op_bank%02d.bin" % bk), "rb").read(),
                               oa[lo:lo + 0x4000]))
                checks.append(("program bank %d" % bk, open(os.path.join(b, "data_bank%02d.bin" % bk), "rb").read(),
                               da[lo:lo + 0x4000]))
        else:
            checks = [("opcode view", open(os.path.join(b, "maincpu_op.bin"), "rb").read(), oa),
                      ("data view", open(os.path.join(b, "maincpu_data.bin"), "rb").read(), da)]
        for name, x, y in checks:
            n = sum(1 for i in range(min(len(x), len(y))) if x[i] != y[i]) + abs(len(x) - len(y))
            print("%-20s %6d bytes, %d differ" % (name, len(x), n))
            ok = ok and n == 0
        print("result: %s" % ("EQUAL" if ok else "DIFFERENT"))
        return 0 if ok else 1
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
