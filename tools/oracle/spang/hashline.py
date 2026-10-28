#!/usr/bin/env python3
"""Super Pang per-frame hash lines (format spfh 1), reference implementation.

The format is specified in docs/spang-oracle-format.md. The MAME writer
(spfh_mame.lua) and MAMR's spang_headless must produce byte-identical
lines.

    hashline.py selftest
    hashline.py fline DUMPDIR FRAME [--zclk N] [--prev HASH]
        rebuild the F line of FRAME from the canonical dumps a writer made
        with its dump option (DUMPDIR/f<FRAME:06d>.<field>.bin)
    hashline.py verify FILE... [--frames N]
        format check of hash files: header, consecutive F lines (exactly N
        when given), field widths, and the chain recomputed from the
        printed field hashes
    hashline.py inputs SCRIPT [--frames N]
        parse an input script (format section 6) and print the port
        values per change
    hashline.py placeholder OUT [--ymfm FILE]
        write the 144-byte YM2413 instrument placeholder: the table
        ym2413::s_default_instruments of the vendored ymfm
        (third_party/ymfm/ymfm_opl.cpp), see docs/spang-oracles.md section 3

Exit codes: 0 success, 1 failure, 3 usage error.
"""
import os
import re
import struct
import sys
import zlib

VERSION = 1
FNV_BASIS = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
MASK64 = 0xFFFFFFFFFFFFFFFF

# State fields of an F line, in line order and in chain order.
FIELDS = ["z80", "wram", "vram", "obj", "pal", "bank", "irq", "eep", "ym", "oki", "img"]
# Small fields are printed as raw hex of their canonical bytes, the others
# as the FNV-1a 64 of their canonical bytes.
RAW_FIELDS = {"z80": 32, "bank": 6}
FIXED_SIZES = {"wram": 0x2000, "vram": 0x1800, "obj": 0x1000, "pal": 0x1000, "eep": 148,
               "img": 384 * 240 * 2}
TIMING_KEYS = ["zclk"]
INFO_KEYS = ["ymn", "okin", "irqn", "mid"]
DUMP_FIELDS = ["z80", "wram", "vram", "obj", "pal", "bank", "irq", "eep", "ym", "oki"]

# Z80 clock and frame timing of the MAME model (docs/spang-hardware-spec.md
# section 1): 8 MHz, 57.42 Hz, attoseconds as MAME computes them.
ATTOS_PER_CYCLE = 125_000_000_000
FRAME_ATTOS = int(10**18 / 57.42)  # HZ_TO_ATTOSECONDS: double division, truncated

# Input script buttons -> (port, bit), all active low (spec section 6).
BUTTONS = {
    "COIN1": ("in0", 7), "SERVICE1": ("in0", 6), "START1": ("in0", 3), "START2": ("in0", 1),
    "P1_UP": ("in1", 7), "P1_DOWN": ("in1", 6), "P1_LEFT": ("in1", 5), "P1_RIGHT": ("in1", 4),
    "P1_B1": ("in1", 3), "P1_B2": ("in1", 2),
    "P2_UP": ("in2", 7), "P2_DOWN": ("in2", 6), "P2_LEFT": ("in2", 5), "P2_RIGHT": ("in2", 4),
    "P2_B1": ("in2", 3), "P2_B2": ("in2", 2),
    "SERVICE": ("sys0", 1),
}

PLACEHOLDER_CRC = 0xF30B33DA


def fnv1a64(data, h=FNV_BASIS):
    """FNV-1a 64 over bytes, byte by byte."""
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & MASK64
    return h


def le64(v):
    return struct.pack("<Q", v & MASK64)


def frame_cycles(n):
    """Z80 cycle at which the sampling window of frame n closes: the
    first cycle at or after VBLANK start n (n * frame period)."""
    return (n * FRAME_ATTOS) // ATTOS_PER_CYCLE


# ---------------------------------------------------------------- lines

def chain(prev, hashes):
    """FNV-1a 64 over LE64(prev) followed by LE64 of each field hash in
    FIELDS order; a field missing from `hashes` (written "-") adds eight
    zero bytes."""
    buf = bytearray(le64(prev))
    for name in FIELDS:
        h = hashes.get(name)
        buf += le64(h) if h is not None else bytes(8)
    return fnv1a64(buf)


def field_hash(name, value):
    """Hash of a printed field value: raw fields hash their bytes."""
    if value == "-":
        return None
    if name in RAW_FIELDS:
        return fnv1a64(bytes.fromhex(value))
    return int(value, 16)


def format_fline(n, zclk, fields, prev, info=None):
    """fields: name -> canonical bytes or None. Returns (line, all)."""
    parts = ["F %d zclk=%d" % (n, zclk)]
    hashes = {}
    for name in FIELDS:
        data = fields.get(name)
        if data is None:
            parts.append("%s=-" % name)
            continue
        hashes[name] = fnv1a64(data)
        if name in RAW_FIELDS:
            parts.append("%s=%s" % (name, bytes(data).hex()))
        else:
            parts.append("%s=%016x" % (name, hashes[name]))
    for k in INFO_KEYS:
        parts.append("%s=%s" % (k, (info or {}).get(k, "-")))
    a = chain(prev, hashes)
    parts.append("all=%016x" % a)
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
        rec = {"kind": "F", "n": int(tok[1])}
        for t in tok[2:]:
            k, v = t.split("=", 1)
            rec[k] = v
        return rec
    return {"kind": tok[0], "text": line}


def read_file(path):
    """Returns (header dict, list of F records, list of other records)."""
    header, frames, other = {}, [], []
    with open(path, "r", encoding="ascii") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            rec = parse_line(line)
            if rec is None:
                continue
            if rec["kind"] == "H":
                header = rec
            elif rec["kind"] == "F":
                frames.append(rec)
            else:
                other.append(rec)
    return header, frames, other


def verify_file(path, frames=None, out=print):
    header, fr, _ = read_file(path)
    ok = True
    if header.get("format") != "spfh" or header.get("version") != VERSION:
        out("%s: header is not spfh %d" % (path, VERSION))
        return False
    prev = 0
    for i, r in enumerate(fr):
        if r["n"] != i + 1:
            out("%s: F line %d has number %d" % (path, i + 1, r["n"]))
            return False
        hashes = {}
        for name in FIELDS:
            v = r.get(name)
            if v is None:
                out("%s: frame %d lacks field %s" % (path, r["n"], name))
                return False
            if v != "-":
                if name in RAW_FIELDS:
                    if len(v) != 2 * RAW_FIELDS[name] or not re.fullmatch("[0-9a-f]+", v):
                        out("%s: frame %d field %s has a bad width" % (path, r["n"], name))
                        ok = False
                elif not re.fullmatch("[0-9a-f]{16}", v):
                    out("%s: frame %d field %s is not a 64-bit hash" % (path, r["n"], name))
                    ok = False
            hashes[name] = field_hash(name, v)
        hashes = {k: v for k, v in hashes.items() if v is not None}
        a = chain(prev, hashes)
        if "%016x" % a != r.get("all"):
            out("%s: frame %d chain mismatch" % (path, r["n"]))
            return False
        prev = a
    if frames is not None and len(fr) != frames:
        out("%s: %d F lines, expected %d" % (path, len(fr), frames))
        ok = False
    return ok


def fline_from_dumps(d, frame, zclk=0, prev=0):
    fields = {}
    for name in FIELDS:
        p = os.path.join(d, "f%06d.%s.bin" % (frame, name))
        if os.path.exists(p):
            with open(p, "rb") as f:
                fields[name] = f.read()
    line, _ = format_fline(frame, zclk, fields, prev)
    return line


# ---------------------------------------------------------------- inputs

def parse_inputs(text):
    """Input script (format section 6): '<frame> [BUTTON ...]' per line,
    the buttons held from the sampling point of <frame> on. Returns a list
    of (frame, {port: value}) with active-low port bytes."""
    out = []
    last = 1
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tok = line.split()
        if not tok[0].isdigit():
            raise ValueError("line %d: frame number expected" % n)
        frame = int(tok[0])
        if frame < 2 or frame <= last:
            raise ValueError("line %d: frames must be >= 2 and ascending" % n)
        last = frame
        ports = {"in0": 0xFF, "in1": 0xFF, "in2": 0xFF, "sys0": 0xFF}
        for b in tok[1:]:
            if b == "-":
                continue
            if b.upper() not in BUTTONS:
                raise ValueError("line %d: unknown button %s" % (n, b))
            port, bit = BUTTONS[b.upper()]
            ports[port] &= ~(1 << bit) & 0xFF
        out.append((frame, ports))
    return out


# ---------------------------------------------------------------- placeholder

def ymfm_default_instruments(path):
    """The 144 bytes of ym2413::s_default_instruments from ymfm_opl.cpp."""
    with open(path, "r", encoding="ascii", errors="replace") as f:
        src = f.read()
    m = re.search(r"uint8_t const ym2413::s_default_instruments\[\]\s*=\s*\{(.*?)\};", src, re.S)
    if not m:
        raise ValueError("ym2413::s_default_instruments not found in " + path)
    body = re.sub(r"//[^\n]*", "", m.group(1))
    data = bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", body))
    if len(data) != 144:
        raise ValueError("instrument table has %d bytes, expected 144" % len(data))
    return data


def default_ymfm_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                        "third_party", "ymfm", "ymfm_opl.cpp")


# ---------------------------------------------------------------- selftest

def selftest():
    assert fnv1a64(b"") == 0xCBF29CE484222325
    assert fnv1a64(b"a") == 0xAF63DC4C8601EC8C
    assert fnv1a64(b"foobar") == 0x85944171F73967E8
    assert FRAME_ATTOS == 17415534656913966, FRAME_ATTOS
    assert frame_cycles(1) == 139324 and frame_cycles(3000) == 417972831
    # a line round trip with every field kind
    fields = {"z80": bytes(range(32)), "wram": bytes(0x2000), "vram": bytes(0x1800),
              "obj": bytes(0x1000), "pal": bytes(0x1000), "bank": bytes([10, 0, 0xC1, 0, 1, 0]),
              "irq": bytes(80), "eep": bytes(148), "ym": b"\x04\x10\x03\x20", "oki": b"", "img": None}
    line, a = format_fline(1, 139324, fields, 0, {"ymn": 1, "okin": 0, "irqn": 2, "mid": 0})
    rec = parse_line(line)
    assert rec["kind"] == "F" and rec["n"] == 1 and rec["zclk"] == "139324"
    assert rec["img"] == "-" and rec["bank"] == "0a00c1000100"
    assert rec["oki"] == "%016x" % FNV_BASIS
    hashes = {k: field_hash(k, rec[k]) for k in FIELDS}
    hashes = {k: v for k, v in hashes.items() if v is not None}
    assert chain(0, hashes) == a
    line2, a2 = format_fline(2, 278648, fields, a)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "t.hash")
        with open(p, "w") as f:
            f.write("H spfh 1 oracle=test set=spang\n" + line + "\n" + line2 + "\n")
        assert verify_file(p, 2, out=lambda s: None)
        with open(p, "w") as f:
            f.write("H spfh 1 oracle=test set=spang\n" + line2.replace("F 2", "F 1") + "\n")
        assert not verify_file(p, out=lambda s: None)
        # dumps rebuild the same line
        dd = os.path.join(td, "d")
        os.mkdir(dd)
        for k, v in fields.items():
            if v is not None:
                with open(os.path.join(dd, "f%06d.%s.bin" % (1, k)), "wb") as f:
                    f.write(v)
        assert fline_from_dumps(dd, 1, 139324).split(" all=")[1] == line.split(" all=")[1]
    # input scripts
    s = parse_inputs("# test\n2\n300 COIN1\n306 -\n400 START1 P1_LEFT\n")
    assert s[1] == (300, {"in0": 0x7F, "in1": 0xFF, "in2": 0xFF, "sys0": 0xFF})
    assert s[3][1]["in0"] == 0xF7 and s[3][1]["in1"] == 0xDF
    for bad in ("1 COIN1\n", "5\n5\n", "5 JUMP\n", "x\n"):
        try:
            parse_inputs(bad)
        except ValueError:
            continue
        raise AssertionError("accepted bad script " + repr(bad))
    # the placeholder from the vendored ymfm
    p = default_ymfm_path()
    if os.path.exists(p):
        data = ymfm_default_instruments(p)
        assert zlib.crc32(data) == PLACEHOLDER_CRC, "%08x" % zlib.crc32(data)
    print("hashline selftest ok")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    cmd, args = argv[1], argv[2:]
    if cmd == "selftest":
        return selftest()
    if cmd == "fline" and len(args) >= 2:
        zclk, prev = 0, 0
        if "--zclk" in args:
            zclk = int(args[args.index("--zclk") + 1])
        if "--prev" in args:
            prev = int(args[args.index("--prev") + 1], 16)
        print(fline_from_dumps(args[0], int(args[1]), zclk, prev))
        return 0
    if cmd == "verify" and args:
        frames = None
        if "--frames" in args:
            i = args.index("--frames")
            frames = int(args[i + 1])
            args = args[:i] + args[i + 2:]
        ok = all([verify_file(p, frames) for p in args])
        print("verify: %s" % ("ok" if ok else "FAILED"))
        return 0 if ok else 1
    if cmd == "inputs" and args:
        with open(args[0], "r", encoding="ascii") as f:
            for frame, ports in parse_inputs(f.read()):
                print("%d in0=%02x in1=%02x in2=%02x sys0=%02x" % (
                    frame, ports["in0"], ports["in1"], ports["in2"], ports["sys0"]))
        return 0
    if cmd == "placeholder" and args:
        src = default_ymfm_path()
        if "--ymfm" in args:
            src = args[args.index("--ymfm") + 1]
        data = ymfm_default_instruments(src)
        with open(args[0], "wb") as f:
            f.write(data)
        return 0
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
