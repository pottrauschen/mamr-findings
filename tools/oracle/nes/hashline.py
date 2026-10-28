#!/usr/bin/env python3
"""NES per-frame hash lines (format version 2), reference implementation.

The format is specified in docs/nes-oracle-format.md. The oracle front
ends (the MesenCE and MAME Lua scripts) and MAMR's runtime must produce
byte-identical lines.

    hashline.py selftest
    hashline.py fline DUMPDIR FRAME [--inp N] [--cyc N] [--dot N] [--pc N] [--prev HASH]
        rebuild the F line of FRAME from the canonical dumps an oracle wrote
        with its dump option (DUMPDIR/f<FRAME:06d>.<field>.bin)
    hashline.py fnv FILE...
        FNV-1a 64 of whole files
    hashline.py verify FILE... [--frames N]
        format check of hash files: header, consecutive F lines (exactly N
        when given), field widths, and the chain recomputed from the
        printed field hashes

Exit codes: 0 success, 1 failure, 3 usage error.
"""
import os
import struct
import sys

VERSION = 2
REGIONS = ("ntsc", "pal")
FNV_BASIS = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
MASK64 = 0xFFFFFFFFFFFFFFFF

# State fields of an F line, in line order and in chain order.
FIELDS = ["cpu", "ram", "vram", "oam", "pal", "prgram", "ppu", "prgmap", "chrmap", "mirq", "img", "apu", "snd"]
# Small fields are printed as raw hex of their canonical bytes; the others
# as the FNV-1a 64 of their canonical bytes.
RAW_FIELDS = {"cpu": 5, "ppu": 11, "mirq": 4}
FIXED_SIZES = {"ram": 2048, "vram": 4096, "oam": 256, "pal": 32, "prgmap": 16, "chrmap": 32, "img": 256 * 240 * 2,
               "apu": 44}
TIMING_KEYS = ["inp", "cyc", "dot"]
INFO_KEYS = ["pc"]

BUTTONS = ["A", "B", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT"]

# The ten colour indices every NES palette renders black.
BLACKS = {0x0D, 0x0E, 0x0F, 0x1D, 0x1E, 0x1F, 0x2E, 0x2F, 0x3E, 0x3F}


def fnv1a64(data, h=FNV_BASIS):
    """FNV-1a 64 over bytes, byte by byte."""
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & MASK64
    return h


def le16(v):
    return struct.pack("<H", v & 0xFFFF)


def le32(v):
    return struct.pack("<I", v & 0xFFFFFFFF)


def le64(v):
    return struct.pack("<Q", v & MASK64)


# ---------------------------------------------------------------- timing

DOTS_PER_LINE = 341
LINES_NTSC = 262
LINES_PAL = 312


def window_dot(n, start_line=0, odd_short=False, region="ntsc"):
    """PPU dot (from power-on) at which the sampling window of frame n
    opens: scanline 240, dot 0. start_line is the scanline the PPU powers on
    in, at dot 0 (0 in MesenCE, -1 for the pre-render line). With odd_short
    every second frame is one dot short (rendering enabled; NTSC only, the
    PAL 2C07 has no skip)."""
    lines = LINES_PAL if region == "pal" else LINES_NTSC
    t = (240 - start_line) * DOTS_PER_LINE
    for k in range(n - 1):
        t += lines * DOTS_PER_LINE - (1 if (odd_short and region != "pal" and k % 2 == 1) else 0)
    return t


# ---------------------------------------------------------------- encoders

def cpu_bytes(a, x, y, s, p):
    """A X Y S P; P with bit 5 set and bit 4 clear."""
    return bytes([a & 0xFF, x & 0xFF, y & 0xFF, s & 0xFF, (p & 0xCF) | 0x20])


def oam_bytes(raw):
    """256 OAM bytes; the attribute byte of each sprite (4k + 2) masked
    with $E3 (bits 2-4 do not exist in the PPU's OAM)."""
    return bytes((v & 0xE3) if i % 4 == 2 else (v & 0xFF) for i, v in enumerate(raw[:256]))


def pal_bytes(entries):
    """32 palette entries as stored; mirrors $10/$14/$18/$1C taken from
    $00/$04/$08/$0C, values masked to 6 bits."""
    out = bytearray(32)
    for i in range(32):
        src = i - 0x10 if i in (0x10, 0x14, 0x18, 0x1C) else i
        out[i] = entries[src] & 0x3F
    return bytes(out)


def ppu_bytes(ctrl, mask, status, oamaddr, v, t, x, w, readbuf):
    return bytes([ctrl & 0xFC, mask & 0xFF, status & 0xE0, oamaddr & 0xFF]) + le16(v & 0x7FFF) + le16(t & 0x7FFF) + \
        bytes([x & 7, 1 if w else 0, readbuf & 0xFF])


def prgmap_bytes(offsets):
    return b"".join(le32(o) for o in offsets[:4])


def chrmap_bytes(offsets):
    return b"".join(le32(o) for o in offsets[:8])


def mirq_bytes(counter, latch, reload, enable):
    return bytes([counter & 0xFF, latch & 0xFF, 1 if reload else 0, 1 if enable else 0])


def apu_bytes(pulses, tri, noise, dmc, enables, fc):
    """The canonical APU channel state (format section 3, field apu).
    pulses: two dicts with duty, vol, constant, loop, start, div, decay,
    length, sweep_en, sweep_period, sweep_neg, sweep_shift, sweep_reload,
    period; tri: lin, lin_reload, control, reload_flag,
    length, period; noise: vol, constant, loop, start, div, decay, length,
    mode, period_index; dmc: irq, loop, rate, level, addr_reg, len_reg,
    addr, left, full, buffer; enables: $4015 bits 0-3; fc: (mode5, inhibit)."""
    b = bytearray()
    for p in pulses:
        b += bytes([p["duty"] & 3, p["vol"] & 15,
                    (1 if p["constant"] else 0) | (2 if p["loop"] else 0) | (4 if p["start"] else 0),
                    p["div"] & 15, p["decay"] & 15, p["length"] & 0xFF,
                    (0x80 if p["sweep_en"] else 0) | (p["sweep_period"] & 7) << 4 | (8 if p["sweep_neg"] else 0) |
                    (p["sweep_shift"] & 7),
                    1 if p["sweep_reload"] else 0])
        b += le16(p["period"] & 0x7FF)
    b += bytes([tri["lin"] & 0x7F, tri["lin_reload"] & 0x7F,
                (1 if tri["control"] else 0) | (2 if tri["reload_flag"] else 0), tri["length"] & 0xFF])
    b += le16(tri["period"] & 0x7FF)
    b += bytes([noise["vol"] & 15,
                (1 if noise["constant"] else 0) | (2 if noise["loop"] else 0) | (4 if noise["start"] else 0),
                noise["div"] & 15, noise["decay"] & 15, noise["length"] & 0xFF,
                (0x80 if noise["mode"] else 0) | (noise["period_index"] & 15)])
    b += bytes([(0x80 if dmc["irq"] else 0) | (0x40 if dmc["loop"] else 0) | (dmc["rate"] & 15), dmc["level"] & 0x7F,
                dmc["addr_reg"] & 0xFF, dmc["len_reg"] & 0xFF])
    b += le16(dmc["addr"] | 0x8000) + le16(dmc["left"])
    b += bytes([1 if dmc["full"] else 0, dmc["buffer"] & 0xFF if dmc["full"] else 0, enables & 15,
                (0x80 if fc[0] else 0) | (0x40 if fc[1] else 0)])
    return bytes(b)


def snd_bytes(samples):
    """The native samples of a frame, LE32 each (format section 3, field snd)."""
    return b"".join(le32(v) for v in samples)


def canonical_pixel(index, emphasis):
    """Canonical 9-bit pixel value (section 5 of the format)."""
    index &= 0x3F
    emphasis &= 7
    if index == 0x30:
        index = 0x20
    if index in BLACKS:
        return 0x0F
    if emphasis == 7 and index == 0x20:
        return 0x10
    return index | (emphasis << 6)


def img_bytes(pixels):
    """pixels: 61440 (index, emphasis) pairs or raw 9-bit values, row by row."""
    out = bytearray()
    for p in pixels:
        if isinstance(p, tuple):
            v = canonical_pixel(p[0], p[1])
        else:
            v = canonical_pixel(p & 0x3F, (p >> 6) & 7)
        out += le16(v)
    return bytes(out)


# ---------------------------------------------------------------- lines

def format_header(oracle, rom_sha1, fill="00", region="ntsc", extra=None):
    s = "H nesfh %d oracle=%s rom=%s fill=%s region=%s" % (VERSION, oracle, rom_sha1 or "-", fill, region)
    for k, v in (extra or []):
        s += " %s=%s" % (k, v)
    return s


def field_hash(data):
    return fnv1a64(data)


def chain_next(prev, hashes):
    """hashes: per field in FIELDS order, the FNV of its bytes or None."""
    buf = le64(prev)
    for h in hashes:
        buf += le64(0 if h is None else h)
    return fnv1a64(buf)


def format_f(frame, inp, cyc, dot, pc, fields, prev_chain=FNV_BASIS):
    """fields: dict field -> canonical bytes (missing or None = '-').
    Returns (line, new_chain)."""
    parts = ["F %d inp=%s cyc=%s dot=%s pc=%04x" % (frame, inp, cyc, "-" if dot is None else dot, pc)]
    hashes = []
    for name in FIELDS:
        data = fields.get(name)
        if data is None:
            parts.append("%s=-" % name)
            hashes.append(None)
            continue
        if name in RAW_FIELDS:
            if len(data) != RAW_FIELDS[name]:
                raise ValueError("%s: %d bytes, expected %d" % (name, len(data), RAW_FIELDS[name]))
            parts.append("%s=%s" % (name, data.hex()))
        else:
            if name in FIXED_SIZES and len(data) != FIXED_SIZES[name]:
                raise ValueError("%s: %d bytes, expected %d" % (name, len(data), FIXED_SIZES[name]))
            parts.append("%s=%016x" % (name, field_hash(data)))
        hashes.append(field_hash(data))
    chain = chain_next(prev_chain, hashes)
    parts.append("all=%016x" % chain)
    return " ".join(parts), chain


def format_t(frame, passed, run, results):
    return "T %d tally=%d/%d results=%s" % (frame, passed, run, results.hex())


def parse_line(line):
    """Returns (kind, dict) for H, F and T lines; (None, None) for comments
    and blank lines."""
    line = line.rstrip("\n")
    if not line or line.startswith("#"):
        return None, None
    tok = line.split(" ")
    if tok[0] == "H":
        if len(tok) < 3 or tok[1] != "nesfh":
            raise ValueError("bad header: " + line)
        d = {"version": int(tok[2])}
        for kv in tok[3:]:
            k, _, v = kv.partition("=")
            d[k] = v
        return "H", d
    if tok[0] in ("F", "T", "R", "N"):
        d = {"n": int(tok[1])}
        for kv in tok[2:]:
            k, _, v = kv.partition("=")
            d[k] = v
        return tok[0], d
    raise ValueError("unknown record: " + line)


def read_extra(path):
    """R and N lines of a file (format section 9): (list of R dicts, list of
    N dicts)."""
    rs, ns = [], []
    with open(path) as f:
        for line in f:
            kind, d = parse_line(line)
            if kind == "R":
                rs.append(d)
            elif kind == "N":
                ns.append(d)
    return rs, ns


def read_file(path):
    """Returns (header dict, list of F dicts, list of T dicts)."""
    header, frames, tallies = None, [], []
    with open(path) as f:
        for line in f:
            kind, d = parse_line(line)
            if kind == "H":
                if header is not None:
                    raise ValueError("two headers in " + path)
                header = d
            elif kind == "F":
                frames.append(d)
            elif kind == "T":
                tallies.append(d)
    if header is None:
        raise ValueError("no header in " + path)
    return header, frames, tallies


def dump_path(d, frame, field):
    return os.path.join(d, "f%06d.%s.bin" % (frame, field))


def load_dump(d, frame):
    fields = {}
    for name in FIELDS:
        p = dump_path(d, frame, name)
        if os.path.exists(p):
            with open(p, "rb") as f:
                fields[name] = f.read()
    return fields


# ---------------------------------------------------------------- checks

def verify(path, frames=None):
    """Format check. Returns a list of problems (empty = ok)."""
    problems = []
    try:
        header, recs, _ = read_file(path)
    except (ValueError, OSError) as e:
        return [str(e)]
    if header.get("version") != VERSION:
        problems.append("version %s, expected %d" % (header.get("version"), VERSION))
    for k in ("oracle", "rom", "fill", "region"):
        if k not in header:
            problems.append("header lacks " + k)
    if header.get("region") not in REGIONS:
        problems.append("region %r" % header.get("region"))
    chain = FNV_BASIS
    for i, r in enumerate(recs):
        if r["n"] != i + 1:
            problems.append("F line %d numbered %d" % (i + 1, r["n"]))
            break
        hashes = []
        for name in FIELDS:
            v = r.get(name)
            if v is None:
                problems.append("frame %d lacks %s" % (r["n"], name))
                hashes.append(None)
                continue
            if v == "-":
                hashes.append(None)
                continue
            want = RAW_FIELDS[name] * 2 if name in RAW_FIELDS else 16
            if len(v) != want or any(c not in "0123456789abcdef" for c in v):
                problems.append("frame %d field %s malformed" % (r["n"], name))
                hashes.append(None)
                continue
            hashes.append(fnv1a64(bytes.fromhex(v)) if name in RAW_FIELDS else int(v, 16))
        for k in TIMING_KEYS + INFO_KEYS + ["all"]:
            if k not in r:
                problems.append("frame %d lacks %s" % (r["n"], k))
        chain = chain_next(chain, hashes)
        if r.get("all") != "%016x" % chain:
            problems.append("frame %d chain mismatch" % r["n"])
            break
    if frames is not None and len(recs) != frames:
        problems.append("%d F lines, expected %d" % (len(recs), frames))
    return problems


def selftest():
    fails = []

    def check(cond, what):
        if not cond:
            fails.append(what)

    check(fnv1a64(b"") == FNV_BASIS, "fnv empty")
    check(fnv1a64(b"a") == 0xAF63DC4C8601EC8C, "fnv a")
    check(fnv1a64(b"foobar") == 0x85944171F73967E8, "fnv foobar")
    check(cpu_bytes(1, 2, 3, 0xFD, 0xFF) == bytes([1, 2, 3, 0xFD, 0xEF]), "cpu bytes")
    pal = list(range(32))
    pb = pal_bytes(pal)
    check(pb[0x10] == 0 and pb[0x14] == 4 and pb[0x11] == 0x11, "pal mirrors")
    check(pal_bytes([0xFF] * 32)[0] == 0x3F, "pal mask")
    check(oam_bytes(bytes([0xFF] * 256))[:4] == bytes([0xFF, 0xFF, 0xE3, 0xFF]), "oam mask")
    check(canonical_pixel(0x30, 0) == 0x20, "pixel white")
    check(canonical_pixel(0x1D, 5) == 0x0F, "pixel black")
    check(canonical_pixel(0x20, 7) == 0x10 and canonical_pixel(0x30, 7) == 0x10, "pixel emphasis white")
    check(canonical_pixel(0x21, 7) == (0x21 | 7 << 6), "pixel keeps emphasis")
    check(len(img_bytes([(0x0F, 0)] * 61440)) == FIXED_SIZES["img"], "img size")
    check(ppu_bytes(0xFF, 0x1E, 0xFF, 0, 0x7FFF, 0x2000, 7, True, 0x42) ==
          bytes([0xFC, 0x1E, 0xE0, 0, 0xFF, 0x7F, 0x00, 0x20, 7, 1, 0x42]), "ppu bytes")
    check(window_dot(1) == 240 * 341, "window 1")
    check(window_dot(1, start_line=-1) == 241 * 341, "window 1 from pre-render")
    check(window_dot(2) == 240 * 341 + 262 * 341, "window 2")
    check(window_dot(3, odd_short=True) == 240 * 341 + 2 * 262 * 341 - 1, "window 3 short")
    check(window_dot(3, odd_short=True, region="pal") == 240 * 341 + 2 * 312 * 341, "window 3 PAL")
    check(mirq_bytes(0x12, 0x34, True, False) == bytes([0x12, 0x34, 1, 0]), "mirq bytes")
    fields = {"cpu": cpu_bytes(0, 0, 0, 0xFD, 0x24), "ram": bytes(2048), "vram": bytes(4096), "oam": bytes(256),
              "pal": bytes(32), "prgram": bytes(8192), "ppu": bytes(11), "prgmap": bytes(16), "chrmap": bytes(32),
              "mirq": bytes(4), "img": bytes(FIXED_SIZES["img"]), "apu": bytes(44), "snd": snd_bytes([1, 2])}
    pz = dict(duty=0, vol=0, constant=False, loop=False, start=False, div=0, decay=0, length=0, sweep_en=False,
              sweep_period=0, sweep_neg=False, sweep_shift=0, sweep_reload=False, period=0)
    ab = apu_bytes([dict(pz, duty=2, period=0x1AB, sweep_en=True, sweep_period=3, sweep_shift=1), pz],
                   dict(lin=5, lin_reload=127, control=True, reload_flag=False, length=10, period=0x7FF),
                   dict(vol=4, constant=True, loop=False, start=True, div=0, decay=15, length=2, mode=True,
                        period_index=12),
                   dict(irq=True, loop=False, rate=15, level=64, addr_reg=0x10, len_reg=0x20, addr=0x4401, left=513,
                        full=True, buffer=0x55), 0x0F, (True, False))
    check(len(ab) == FIXED_SIZES["apu"], "apu size")
    check(ab[:10] == bytes([2, 0, 0, 0, 0, 0, 0xB1, 0, 0xAB, 0x01]), "apu pulse bytes")
    check(ab[20:26] == bytes([5, 127, 1, 10, 0xFF, 0x07]), "apu triangle bytes")
    check(ab[26:32] == bytes([4, 5, 0, 15, 2, 0x8C]), "apu noise bytes")
    check(ab[32:] == bytes([0x8F, 64, 0x10, 0x20, 0x01, 0xC4, 0x01, 0x02, 1, 0x55, 0x0F, 0x80]), "apu dmc bytes")
    line1, c1 = format_f(1, 0, 7, 21, 0xC000, fields)
    line2, c2 = format_f(2, 1, 29800, None, 0xC000, dict(fields, img=None), c1)
    text = format_header("test", "0" * 40) + "\n" + line1 + "\n" + line2 + "\n"
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".hash", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        check(verify(path) == [], "verify ok: %r" % verify(path))
        check(verify(path, frames=3) != [], "verify frame count")
        bad = text.replace("all=%016x" % c2, "all=%016x" % (c2 ^ 1))
        with open(path, "w") as f:
            f.write(bad)
        check(any("chain" in p for p in verify(path)), "verify chain")
        kind, d = parse_line(line2)
        check(kind == "F" and d["n"] == 2 and d["img"] == "-" and d["inp"] == "1", "parse")
        kind, d = parse_line("R 9 status=00 text=50617373")
        check(kind == "R" and d["status"] == "00" and bytes.fromhex(d["text"]) == b"Pass", "parse R")
        kind, d = parse_line(format_t(5, 140, 147, bytes([1, 0xFF, 2])))
        check(kind == "T" and d["tally"] == "140/147" and d["results"] == "01ff02", "parse T")
    finally:
        os.unlink(path)
    if fails:
        print("hashline selftest FAILED:", ", ".join(fails))
        return 1
    print("hashline selftest ok")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    cmd = argv[1]
    if cmd == "selftest":
        return selftest()
    if cmd == "fnv":
        for p in argv[2:]:
            with open(p, "rb") as f:
                print("%016x %s" % (fnv1a64(f.read()), p))
        return 0
    if cmd == "verify":
        frames = None
        files = []
        args = argv[2:]
        while args:
            a = args.pop(0)
            if a == "--frames":
                frames = int(args.pop(0))
            else:
                files.append(a)
        rc = 0
        for p in files:
            problems = verify(p, frames)
            print("%s: %s" % (p, "ok" if not problems else "; ".join(problems[:5])))
            if problems:
                rc = 1
        return rc
    if cmd == "fline":
        if len(argv) < 4:
            print(__doc__)
            return 3
        d, frame = argv[2], int(argv[3])
        opts = {"--inp": "0", "--cyc": "0", "--dot": None, "--pc": "0", "--prev": None}
        args = argv[4:]
        while args:
            a = args.pop(0)
            if a in opts:
                opts[a] = args.pop(0)
            else:
                print("unknown option " + a)
                return 3
        prev = int(opts["--prev"], 16) if opts["--prev"] else FNV_BASIS
        fields = load_dump(d, frame)
        line, _ = format_f(frame, opts["--inp"], opts["--cyc"], None if opts["--dot"] is None else opts["--dot"],
                           int(opts["--pc"], 16), fields, prev)
        print(line)
        return 0
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
