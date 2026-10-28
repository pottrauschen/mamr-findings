#!/usr/bin/env python3
"""Arcade frame hash lines (format afh 1), reference implementation.

The format is specified in docs/arcade-oracle-format.md. The MAME writers
(ikari_mame.lua, rtype_mame.lua) and MAMR's ikari_headless / rtype_headless
must produce byte-identical lines; compare.py and gates.py build on this
module.

    afh.py selftest
    afh.py verify FILE... [--frames N]
        format check: header, consecutive F lines (exactly N when given),
        the keys of the set in order, raw field widths, and the chain
        recomputed from the printed field hashes
    afh.py fline DUMPDIR FRAME SET [--prev HASH]
        rebuild the state part of an F line from the canonical dumps a
        writer made with its dump option (DUMPDIR/f<FRAME:06d>.<field>.bin)

Exit codes: 0 success, 1 failure, 3 usage error.
"""
import os
import struct
import sys

VERSION = 1
FNV_BASIS = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
MASK64 = 0xFFFFFFFFFFFFFFFF

# Per set: timing keys (compared unless --no-timing, not in the chain),
# state fields in line and chain order, raw fields with their width,
# informative keys after the state fields.
SETS = {
    "ikari": {
        "timing": ["clka", "clkb", "clks"],
        "fields": ["za", "zb", "zs", "bg", "spr", "tx", "snd", "vreg", "io", "pal", "irq", "ym", "ymt",
                   "img"],
        "raw": {"za": 32, "zb": 32, "zs": 32, "vreg": 18, "io": 7},
        "sizes": {"bg": 0x800, "spr": 0x1800, "tx": 0x800, "snd": 0x1000, "pal": 0x400 * 3,
                  "img": 288 * 216 * 4},
        "info": ["irqn", "ymn", "mid"],
        # the parts of the fields, for compare.py dumps (field -> [(offset, size, name)])
        "parts": {
            "vreg": [(0, 2, "bg_scrollx"), (2, 2, "bg_scrolly"), (4, 2, "sp16_scrollx"),
                     (6, 2, "sp16_scrolly"), (8, 2, "sp32_scrollx"), (10, 2, "sp32_scrolly"),
                     (12, 2, "hf_posx"), (14, 2, "hf_posy"), (16, 2, "tx_tile_offset")],
            "io": [(0, 1, "latch"), (1, 1, "status"), (2, 1, "nmi_a"), (3, 1, "nmi_b"),
                   (4, 1, "int_a"), (5, 1, "int_b"), (6, 1, "int_s")],
        },
    },
    "rtype": {
        "timing": ["clkm", "clks"],
        "fields": ["v30", "zs", "ram", "spr", "sbuf", "pal", "vram", "snd", "vreg", "io", "pic", "irq", "ym",
                   "ymt", "img"],
        "raw": {"v30": 32, "zs": 32, "vreg": 12, "io": 7, "pic": 10},
        "sizes": {"ram": 0x4000, "spr": 0x400, "sbuf": 0x400, "pal": 0x1800, "vram": 0x8000, "snd": 0x10000,
                  "img": 384 * 256 * 4},
        "info": ["irqn", "ymn", "mid"],
        "parts": {
            "vreg": [(0, 2, "scrollx0"), (2, 2, "scrollx1"), (4, 2, "scrolly0"), (6, 2, "scrolly1"),
                     (8, 2, "raster"), (10, 1, "video_off"), (11, 1, "flip")],
            "io": [(0, 1, "latch"), (1, 1, "latch_written"), (2, 1, "rst_inputs"), (3, 1, "z80_int"),
                   (4, 1, "z80_held"), (5, 1, "v30_int"), (6, 1, "v30_nmi")],
            "pic": [(0, 1, "state"), (1, 1, "isr"), (2, 1, "irr"), (3, 1, "imr"), (4, 1, "prio"),
                    (5, 1, "irq_lines"), (6, 1, "read_select"), (7, 1, "level_trig"), (8, 1, "auto_eoi"),
                    (9, 1, "base")],
        },
    },
}
V30_REGS = ["AW", "CW", "DW", "BW", "SP", "BP", "IX", "IY", "DS1", "PS", "SS", "DS0", "IP", "PSW"]
Z80_REGS = ["PC", "AF", "BC", "DE", "HL", "AF'", "BC'", "DE'", "HL'", "IX", "IY", "SP", "WZ"]


def fnv1a64(data, h=FNV_BASIS):
    """FNV-1a 64 over bytes, byte by byte."""
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & MASK64
    return h


def le64(v):
    return struct.pack("<Q", v & MASK64)


def chain(setname, prev, hashes):
    """FNV-1a 64 over LE64(prev) followed by LE64 of each field hash in
    field order; a field missing from `hashes` (written "-") adds eight
    zero bytes."""
    buf = bytearray(le64(prev))
    for name in SETS[setname]["fields"]:
        h = hashes.get(name)
        buf += le64(h) if h is not None else bytes(8)
    return fnv1a64(buf)


def field_hash(setname, name, value):
    if value == "-":
        return None
    if name in SETS[setname]["raw"]:
        return fnv1a64(bytes.fromhex(value))
    return int(value, 16)


def format_state(setname, fields, prev):
    """fields: name -> canonical bytes or None. Returns (state part, all)."""
    spec = SETS[setname]
    parts, hashes = [], {}
    for name in spec["fields"]:
        data = fields.get(name)
        if data is None:
            parts.append("%s=-" % name)
            continue
        hashes[name] = fnv1a64(data)
        if name in spec["raw"]:
            parts.append("%s=%s" % (name, bytes(data).hex()))
        else:
            parts.append("%s=%016x" % (name, hashes[name]))
    a = chain(setname, prev, hashes)
    return " ".join(parts), a


def parse_line(line):
    tok = line.split()
    if not tok:
        return None
    if tok[0] == "H":
        rec = {"kind": "H", "format": tok[1] if len(tok) > 1 else None}
        rec["version"] = int(tok[2]) if len(tok) > 2 and tok[2].isdigit() else None
        for t in tok[3:]:
            if "=" in t:
                k, v = t.split("=", 1)
                rec[k] = v
        return rec
    if tok[0] == "F":
        rec = {"kind": "F", "n": int(tok[1]), "keys": []}
        for t in tok[2:]:
            k, _, v = t.partition("=")
            rec[k] = v
            rec["keys"].append(k)
        return rec
    return None


def read_file(path):
    """(header, [F records], comments)"""
    header, frames, comments = {}, [], []
    with open(path, "r", encoding="ascii") as f:
        for line in f:
            if line.startswith("#"):
                comments.append(line.rstrip("\n"))
                continue
            rec = parse_line(line)
            if rec is None:
                continue
            if rec["kind"] == "H":
                header = rec
            else:
                frames.append(rec)
    return header, frames, comments


def verify(path, frames=None, out=print):
    header, recs, comments = read_file(path)
    ok = True
    for c in comments:
        if c.startswith("# error"):
            out("%s: %s" % (path, c))
            ok = False
    if header.get("format") != "afh" or header.get("version") != VERSION:
        out("%s: not an afh %d file" % (path, VERSION))
        return False
    setname = header.get("set")
    if setname not in SETS:
        out("%s: unknown set %s" % (path, setname))
        return False
    spec = SETS[setname]
    want = spec["timing"] + spec["fields"] + spec["info"] + ["all"]
    prev = 0
    for i, r in enumerate(recs):
        if r["n"] != i + 1:
            out("%s: F line %d has number %d" % (path, i + 1, r["n"]))
            return False
        if r["keys"] != want:
            out("%s: frame %d keys %s" % (path, r["n"], " ".join(r["keys"])))
            return False
        hashes = {}
        for name in spec["fields"]:
            v = r[name]
            if v != "-" and name in spec["raw"] and len(v) != 2 * spec["raw"][name]:
                out("%s: frame %d field %s has %d hex digits" % (path, r["n"], name, len(v)))
                ok = False
            hashes[name] = field_hash(setname, name, v)
        a = chain(setname, prev, hashes)
        if "%016x" % a != r["all"]:
            out("%s: frame %d chain %016x, line says %s" % (path, r["n"], a, r["all"]))
            return False
        prev = a
    if frames is not None and len(recs) != frames:
        out("%s: %d F lines, expected %d" % (path, len(recs), frames))
        ok = False
    out("%s: %d F lines, set %s, %s" % (path, len(recs), setname, "ok" if ok else "FAILED"))
    return ok


def fline(dumpdir, frame, setname, prev=0):
    fields = {}
    for name in SETS[setname]["fields"]:
        p = os.path.join(dumpdir, "f%06d.%s.bin" % (frame, name))
        fields[name] = open(p, "rb").read() if os.path.exists(p) else None
    return format_state(setname, fields, prev)


def z80_regs(raw):
    """The 32 bytes of a z80 field as a dict (format section 3)."""
    b = bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
    d = {r: b[2 * i] << 8 | b[2 * i + 1] for i, r in enumerate(Z80_REGS)}
    d.update({"I": b[26], "R": b[27], "IFF1": b[28], "IFF2": b[29], "IM": b[30], "HALT": b[31]})
    return d


def v30_regs(raw):
    """The 32 bytes of a v30 field as a dict (format section 4.1)."""
    b = bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
    d = {r: b[2 * i] << 8 | b[2 * i + 1] for i, r in enumerate(V30_REGS)}
    d.update({"prefetch": b[28], "no_interrupt": b[29], "halted": b[30]})
    return d


def selftest():
    ok = True
    for data, want in ((b"", 0xCBF29CE484222325), (b"a", 0xAF63DC4C8601EC8C), (b"foobar", 0x85944171F73967E8)):
        if fnv1a64(data) != want:
            print("fnv1a64(%r) = %016x" % (data, fnv1a64(data)))
            ok = False
    fields = {name: bytes([i]) * SETS["ikari"]["raw"].get(name, 4) for i, name in enumerate(SETS["ikari"]["fields"])}
    fields["img"] = None
    state, a = format_state("ikari", fields, 0)
    line = "F 1 clka=1 clkb=2 clks=3 %s irqn=0 ymn=0 mid=000 all=%016x" % (state, a)
    rec = parse_line(line)
    hashes = {n: field_hash("ikari", n, rec[n]) for n in SETS["ikari"]["fields"]}
    if "%016x" % chain("ikari", 0, hashes) != rec["all"]:
        print("chain mismatch")
        ok = False
    if z80_regs(bytes(range(32)))["SP"] != 0x1617:
        print("z80_regs")
        ok = False
    print("afh selftest: %s" % ("ok" if ok else "FAILED"))
    return ok


def main(argv):
    if len(argv) >= 2 and argv[1] == "selftest":
        return 0 if selftest() else 1
    if len(argv) >= 3 and argv[1] == "verify":
        frames = None
        files = []
        it = iter(argv[2:])
        for a in it:
            if a == "--frames":
                frames = int(next(it))
            else:
                files.append(a)
        return 0 if all(verify(f, frames) for f in files) else 1
    if len(argv) >= 5 and argv[1] == "fline":
        prev = 0
        if len(argv) == 7 and argv[5] == "--prev":
            prev = int(argv[6], 16)
        state, a = fline(argv[2], int(argv[3]), argv[4], prev)
        print("%s all=%016x" % (state, a))
        return 0
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main(sys.argv))
