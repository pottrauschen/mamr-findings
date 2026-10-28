#!/usr/bin/env python3
"""SNES per-frame hash lines (format version 4), reference implementation.

The format is specified in docs/snes-oracle-format.md. This module is the
reference: the oracle front ends (aresref, the MesenCE and MAME Lua
scripts) and MAMR's runtime must produce byte-identical lines.

    hashline.py selftest
    hashline.py fline DUMPDIR FRAME [--anc N] [--mclk N] [--prev HASH]
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

VERSION = 4
REGIONS = ("ntsc", "pal")
# clk: the APU oscillator the run used. meas = 32040 Hz * 768 (the measured
# rate ares and MesenCE use), nom = 24.576 MHz (32000 Hz * 768).
CLOCKS = ("meas", "nom")
MASTER_HZ = {"ntsc": 21477272.7, "pal": 21281370.0}
FNV_BASIS = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
MASK64 = 0xFFFFFFFFFFFFFFFF

# State fields of an F line, in line order and in chain order.
FIELDS = ["cpu", "smp", "apuio", "wram", "vram", "oam", "cgram", "ppu", "aram", "dsp", "img", "sram"]
# Small fields are printed as raw hex of their canonical bytes; the others
# as the FNV-1a 64 of their canonical bytes.
RAW_FIELDS = {"cpu": 14, "smp": 13, "apuio": 8}
FIXED_SIZES = {"wram": 0x20000, "vram": 0x10000, "oam": 544, "cgram": 512,
               "ppu": 77, "aram": 0x10000, "dsp": 128}
# Non-state keys of an F line (informative or timing).
TIMING_KEYS = ["anc", "mclk"]
INFO_KEYS = ["pc", "imgsz"]

BUTTONS = ["B", "Y", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT", "A", "X", "L", "R"]

# PPU shadow: $2100-$2133 last written byte, then the byte written before
# the last one for the double-write registers.
PPU_DOUBLE = list(range(0x0D, 0x15)) + list(range(0x1B, 0x21))


def fnv1a64(data, h=FNV_BASIS):
    """FNV-1a 64 over bytes, byte by byte."""
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & MASK64
    return h


def le16(v):
    return struct.pack("<H", v & 0xFFFF)


def le64(v):
    return struct.pack("<Q", v & MASK64)


# ---------------------------------------------------------------- timing

def field_clocks(region, field, interlace=False):
    """Master clocks of one field (frame) of the given parity. NTSC: 262
    lines of 1364 clocks; without interlace line 240 of field 1 has 1360;
    with interlace field 0 has 263 lines. PAL: 312 lines; with interlace
    field 0 has 313 lines and line 311 of field 1 has 1368 clocks. Field
    parity starts at 0 at power-on."""
    if region == "ntsc":
        if interlace:
            return 263 * 1364 if field == 0 else 262 * 1364
        return 262 * 1364 - (4 if field == 1 else 0)
    if interlace:
        return 313 * 1364 if field == 0 else 312 * 1364 + 4
    return 312 * 1364


def window_mclk(n, region="ntsc", overscan=False, interlace=False):
    """Master clock (from power-on) at which the sampling window of frame n
    opens: V=225 (240 with overscan), H=0 of field n - 1. The F line's mclk
    is the first CPU instruction boundary at or after this clock. Assumes
    the interlace and overscan settings held since power-on."""
    t = (240 if overscan else 225) * 1364
    for k in range(n - 1):
        t += field_clocks(region, k & 1, interlace)
    return t


# ---------------------------------------------------------------- encoders

def cpu_bytes(a, x, y, s, d, db, pb, p, e):
    """65816 registers without PC: A X Y S D (16-bit LE) DB PB P E."""
    return le16(a) + le16(x) + le16(y) + le16(s) + le16(d) + bytes([db & 0xFF, pb & 0xFF, p & 0xFF, 1 if e else 0])


def smp_bytes(a, x, y, sp, psw, ipl_enable, timer_enable, dsp_addr, targets, outputs):
    """SPC700 registers without PC plus the S-SMP I/O state.

    timer_enable: three booleans (CONTROL bits 0-2); targets: three bytes
    ($FA-$FC); outputs: three 4-bit stage-3 counters ($FD-$FF, not read
    destructively)."""
    control = (0x80 if ipl_enable else 0) | sum((1 << i) for i in range(3) if timer_enable[i])
    return bytes([a & 0xFF, x & 0xFF, y & 0xFF, sp & 0xFF, psw & 0xFF, control, dsp_addr & 0xFF]
                 + [t & 0xFF for t in targets] + [o & 0x0F for o in outputs])


def apuio_bytes(cpu_to_smp, smp_to_cpu):
    """The four values the CPU wrote to $2140-$2143 (the SMP reads them at
    $F4-$F7), then the four values the SMP wrote to $F4-$F7."""
    return bytes([v & 0xFF for v in cpu_to_smp] + [v & 0xFF for v in smp_to_cpu])


def ppu_bytes(shadow, prev, vram_addr, vram_prefetch, oam_buffer,
              cgram_addr, cgram_flip, cgram_buffer, bgofs1, bgofs2, mode7_latch):
    """Canonical PPU register set (77 bytes), see docs/snes-oracle-format.md.
    The internal OAM address is not part of it (it runs during sprite
    evaluation); OAMADD as written is in the shadow."""
    assert len(shadow) == 0x34 and len(prev) == len(PPU_DOUBLE)
    out = bytes(v & 0xFF for v in shadow) + bytes(v & 0xFF for v in prev)
    out += le16(vram_addr & 0x7FFF) + le16(vram_prefetch)
    out += bytes([oam_buffer & 0xFF, cgram_addr & 0xFF, 1 if cgram_flip else 0, cgram_buffer & 0xFF,
                  bgofs1 & 0xFF, bgofs2 & 0x07, mode7_latch & 0xFF])
    assert len(out) == FIXED_SIZES["ppu"]
    return out


def cgram_bytes(words):
    return b"".join(le16(w & 0x7FFF) for w in words)


def apply_brightness(c15, brightness):
    """Master brightness convention: each 5-bit channel times B / 15,
    rounded down (B = INIDISP bits 0-3). Force blank gives 0."""
    if brightness >= 15:
        return c15 & 0x7FFF
    r = (c15 & 0x1F) * brightness // 15
    g = ((c15 >> 5) & 0x1F) * brightness // 15
    b = ((c15 >> 10) & 0x1F) * brightness // 15
    return r | (g << 5) | (b << 10)


def img_canonical(rows):
    """rows: list of lines, each a list of 512 15-bit colours (after colour
    math and brightness) in hi-res order (even = sub screen half-pixel,
    odd = main screen half-pixel; a non-hi-res pixel appears twice).
    Returns (bytes, width, height): 256 wide when every pair is equal,
    else 512 wide."""
    hires = any(r[2 * i] != r[2 * i + 1] for r in rows for i in range(256))
    out = bytearray()
    for r in rows:
        if hires:
            for c in r:
                out += le16(c & 0x7FFF)
        else:
            for i in range(256):
                out += le16(r[2 * i + 1] & 0x7FFF)
    return bytes(out), (512 if hires else 256), len(rows)


# ---------------------------------------------------------------- lines

def format_header(oracle, rom_sha1, fill="00", region="ntsc", clk="meas", extra=None):
    parts = ["H", "snesfh", str(VERSION), "oracle=" + oracle, "rom=" + rom_sha1, "fill=" + fill,
             "region=" + region, "clk=" + clk]
    for k, v in (extra or {}).items():
        parts.append("%s=%s" % (k, v))
    return " ".join(parts)


def field_hash(data):
    return fnv1a64(data) if data is not None else None


def chain_next(prev, hashes):
    """all_n = FNV-1a 64 over LE64(all_{n-1}) and LE64 of every field hash
    in FIELDS order; a missing field contributes LE64(0)."""
    buf = le64(prev) + b"".join(le64(hashes.get(f) or 0) for f in FIELDS)
    return fnv1a64(buf)


def format_f(frame, anc, mclk, pc, fields, prev_chain=FNV_BASIS, imgsz=None):
    """fields: dict name -> canonical bytes or None (not available).
    Returns (line, chain)."""
    hashes = {f: field_hash(fields.get(f)) for f in FIELDS}
    parts = ["F", str(frame), "anc=%d" % anc, "mclk=%s" % ("-" if mclk is None else str(mclk)),
             "pc=%s" % ("-" if pc is None else "%06x" % pc)]
    for f in FIELDS:
        data = fields.get(f)
        if data is None:
            parts.append(f + "=-")
        elif f in RAW_FIELDS:
            assert len(data) == RAW_FIELDS[f], (f, len(data))
            parts.append(f + "=" + data.hex())
        else:
            if f in FIXED_SIZES:
                assert len(data) == FIXED_SIZES[f], (f, len(data))
            parts.append(f + "=%016x" % hashes[f])
    parts.append("imgsz=" + (imgsz or "-"))
    chain = chain_next(prev_chain, hashes)
    parts.append("all=%016x" % chain)
    return " ".join(parts), chain


def format_l(frame, img, imgsz):
    """Diagnostic L line: one FNV-1a 64 per picture row of the canonical
    image bytes (not part of the chain)."""
    w = int(imgsz.split("x")[0])
    rows = [fnv1a64(img[y * 2 * w:(y + 1) * 2 * w]) for y in range(len(img) // (2 * w))]
    return "L %d " % frame + " ".join("%016x" % h for h in rows)


def parse_line(line):
    """Returns a dict with 'type' and the keys of the line, or None for
    blank and comment lines."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    tok = line.split()
    t = tok[0]
    if t == "H":
        if len(tok) < 3 or tok[1] != "snesfh":
            raise ValueError("bad header: " + line)
        rec = {"type": "H", "version": int(tok[2])}
        for kv in tok[3:]:
            k, _, v = kv.partition("=")
            rec[k] = v
        return rec
    if t == "F":
        rec = {"type": "F", "frame": int(tok[1])}
        for kv in tok[2:]:
            k, _, v = kv.partition("=")
            rec[k] = v
        missing = [f for f in FIELDS if f not in rec]
        if missing:
            raise ValueError("F line without %s: %s" % (",".join(missing), line))
        return rec
    if t == "A":
        rec = {"type": "A", "frame": int(tok[1])}
        for kv in tok[2:]:
            k, _, v = kv.partition("=")
            rec[k] = v
        return rec
    if t == "L":
        return {"type": "L", "frame": int(tok[1]), "rows": tok[2:]}
    if t == "P":
        rec = {"type": "P", "frame": int(tok[1]), "side": tok[2]}
        for kv in tok[3:]:
            k, _, v = kv.partition("=")
            rec[k] = v
        return rec
    raise ValueError("unknown line type: " + line)


def read_file(path):
    """Returns (header or None, list of records)."""
    header, recs = None, []
    with open(path, encoding="ascii") as f:
        for n, line in enumerate(f, 1):
            try:
                rec = parse_line(line)
            except ValueError as e:
                raise ValueError("%s:%d: %s" % (path, n, e))
            if rec is None:
                continue
            if rec["type"] == "H":
                header = rec
            else:
                recs.append(rec)
    return header, recs


# ---------------------------------------------------------------- dumps

def dump_path(d, frame, field):
    return os.path.join(d, "f%06d.%s.bin" % (frame, field))


def load_dump(d, frame):
    """Canonical bytes per field from an oracle dump directory (missing
    files give None). The image size is in f<frame>.imgsz.txt."""
    fields = {}
    for f in FIELDS:
        p = dump_path(d, frame, f)
        if os.path.exists(p):
            with open(p, "rb") as fh:
                fields[f] = fh.read()
        else:
            fields[f] = None
    imgsz = None
    p = os.path.join(d, "f%06d.imgsz.txt" % frame)
    if os.path.exists(p):
        with open(p) as fh:
            imgsz = fh.read().strip()
    return fields, imgsz


# ---------------------------------------------------------------- self test

def selftest():
    ok = True

    def check(cond, what):
        nonlocal ok
        if not cond:
            print("FAIL", what)
            ok = False

    # Published FNV-1a 64 test vectors.
    check(fnv1a64(b"") == 0xCBF29CE484222325, "fnv empty")
    check(fnv1a64(b"a") == 0xAF63DC4C8601EC8C, "fnv a")
    check(fnv1a64(b"foobar") == 0x85944171F73967E8, "fnv foobar")
    # Incremental hashing equals one-shot hashing.
    check(fnv1a64(b"bar", fnv1a64(b"foo")) == fnv1a64(b"foobar"), "fnv incremental")

    cpu = cpu_bytes(0x1234, 0x56, 0x78, 0x1FF, 0, 0x7E, 0x80, 0x34, True)
    check(cpu.hex() == "341256007800ff0100007e803401", "cpu layout " + cpu.hex())
    smp = smp_bytes(1, 2, 3, 0xEF, 0x02, True, [True, False, True], 0x4C, [0, 0x80, 0xFF], [1, 0x1F, 0])
    check(smp.hex() == "010203ef02854c0080ff010f00", "smp layout " + smp.hex())
    check(apuio_bytes([0xAA, 0xBB, 0, 0], [1, 2, 3, 4]).hex() == "aabb000001020304", "apuio layout")
    ppu = ppu_bytes([i for i in range(0x34)], [0xEE] * 14, 0x1234, 0xBEEF, 1, 2, True, 3, 4, 0xFF, 5)
    check(len(ppu) == 77 and ppu[0x33] == 0x33 and ppu[0x34] == 0xEE and ppu[66:68] == b"\x34\x12", "ppu layout")
    check(ppu[70:77] == bytes([1, 2, 1, 3, 4, 7, 5]), "ppu latches " + ppu[70:77].hex())

    check(apply_brightness(0x7FFF, 15) == 0x7FFF, "brightness 15")
    check(apply_brightness(0x7FFF, 0) == 0, "brightness 0")
    check(apply_brightness(0x001F, 7) == 14, "brightness 7 (31*7//15 = 14)")

    rows = [[c for c in range(256) for _ in (0, 1)] for _ in range(224)]
    img, w, h = img_canonical(rows)
    check((w, h, len(img)) == (256, 224, 256 * 224 * 2), "img 256")
    rows[5][10] = 0x7C00
    img, w, h = img_canonical(rows)
    check((w, h, len(img)) == (512, 224, 512 * 224 * 2), "img hi-res")

    fields = {"cpu": cpu, "smp": smp, "apuio": bytes(8), "wram": bytes(0x20000), "vram": bytes(0x10000),
              "oam": bytes(544), "cgram": bytes(512), "ppu": ppu, "aram": bytes(0x10000), "dsp": bytes(128),
              "img": img, "sram": bytes([0xFF]) * 0x2000}
    l1, c1 = format_f(1, 0, 306900, 0x008000, fields, imgsz="512x224")
    r1 = parse_line(l1)
    check(r1["frame"] == 1 and r1["cpu"] == cpu.hex() and r1["wram"] == "%016x" % fnv1a64(bytes(0x20000)),
          "parse F")
    check(r1["all"] == "%016x" % c1, "chain printed")
    l2, c2 = format_f(2, 1, 664268, None, dict(fields, img=None), prev_chain=c1)
    r2 = parse_line(l2)
    check(r2["img"] == "-" and r2["pc"] == "-", "missing field")
    check(c2 != c1 and chain_next(c1, {f: field_hash(dict(fields, img=None)[f]) for f in FIELDS}) == c2,
          "chain recompute")
    # A one-byte change in any field changes the field hash and the chain.
    w2 = bytearray(fields["wram"])
    w2[0x1234] ^= 1
    l3, c3 = format_f(1, 0, 306900, 0x008000, dict(fields, wram=bytes(w2)), imgsz="512x224")
    check(parse_line(l3)["wram"] != r1["wram"] and c3 != c1, "fault visible")

    h = parse_line(format_header("selftest", "0" * 40, region="pal"))
    check(h["version"] == VERSION and h["oracle"] == "selftest" and h["region"] == "pal" and h["clk"] == "meas",
          "header")
    # Sampling windows: NTSC frames alternate 357368 and 357364 clocks
    # (short line 240 in field 1), PAL frames are 425568 clocks.
    check([window_mclk(n) for n in (1, 2, 3, 4)] == [306900, 664268, 1021632, 1379000], "ntsc windows")
    check(window_mclk(5) == 306900 + 357368 * 4 - 4 * 2, "ntsc formula")
    check([window_mclk(n, "pal") for n in (1, 2, 3)] == [306900, 732468, 1158036], "pal windows")
    check(window_mclk(3, "pal", interlace=True) == 306900 + 313 * 1364 + 312 * 1364 + 4, "pal interlace")
    check(window_mclk(2, "ntsc", overscan=True) == 240 * 1364 + 357368, "overscan window")
    lline = parse_line(format_l(1, img, "512x224"))
    check(lline["type"] == "L" and len(lline["rows"]) == 224
          and lline["rows"][5] != lline["rows"][6] and lline["rows"][6] == lline["rows"][7], "L line")
    a = parse_line("A 12 pc=008260 mclk=123 d=- anc=11 tag=loop")
    check(a["pc"] == "008260" and a["tag"] == "loop", "A line")
    p = parse_line("P 3 s t=1000 port=1 val=aa")
    check(p["side"] == "s" and p["val"] == "aa", "P line")
    print("hashline selftest:", "ok" if ok else "FAILED")
    return 0 if ok else 1


def verify(path, frames=None):
    """Returns a list of problems (empty when the file is consistent)."""
    try:
        header, recs = read_file(path)
    except (OSError, ValueError) as e:
        return [str(e)]
    bad = []
    if header is None or header.get("version") != VERSION:
        bad.append("%s: no version %d header" % (path, VERSION))
    elif header.get("region") not in REGIONS or header.get("clk") is None:
        bad.append("%s: header without region= (ntsc|pal) or clk=" % path)
    region = (header or {}).get("region", "ntsc")
    chain, expect, last_mclk, imgsz = FNV_BASIS, 1, -1, {}
    for r in recs:
        if r["type"] == "L":
            w = imgsz.get(r["frame"])
            if w and len(r["rows"]) != int(w.split("x")[1]):
                bad.append("%s: L %d has %d rows for imgsz %s" % (path, r["frame"], len(r["rows"]), w))
            continue
        if r["type"] != "F":
            continue
        imgsz[r["frame"]] = r.get("imgsz")
        if r["mclk"] != "-" and region in REGIONS:
            m = int(r["mclk"])
            if m < window_mclk(r["frame"], region) or m <= last_mclk:
                bad.append("%s: F %d: mclk %d before the sampling window (%d) or not increasing" % (
                    path, r["frame"], m, window_mclk(r["frame"], region)))
            last_mclk = m
        if r["frame"] != expect:
            bad.append("%s: F %d where F %d was expected" % (path, r["frame"], expect))
            break
        expect += 1
        hashes = {}
        for f in FIELDS:
            v = r[f]
            if v == "-":
                hashes[f] = None
            elif f in RAW_FIELDS:
                if len(v) != 2 * RAW_FIELDS[f]:
                    bad.append("%s: F %d: %s has %d hex digits" % (path, r["frame"], f, len(v)))
                hashes[f] = fnv1a64(bytes.fromhex(v))
            else:
                if len(v) != 16:
                    bad.append("%s: F %d: %s is not a 64-bit hash" % (path, r["frame"], f))
                hashes[f] = int(v, 16)
        chain = chain_next(chain, hashes)
        if r.get("all") != "%016x" % chain:
            bad.append("%s: F %d: chain all=%s, recomputed %016x" % (path, r["frame"], r.get("all"), chain))
            break
    if frames is not None and expect - 1 != frames:
        bad.append("%s: %d F lines, expected %d" % (path, expect - 1, frames))
    return bad


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
                print("%016x  %s" % (fnv1a64(f.read()), p))
        return 0
    if cmd == "verify":
        files = [a for a in argv[2:]]
        frames = None
        if "--frames" in files:
            i = files.index("--frames")
            frames = int(files[i + 1])
            del files[i:i + 2]
        if not files:
            print(__doc__)
            return 3
        problems = []
        for p in files:
            problems += verify(p, frames)
        for p in problems:
            print(p)
        print("verified %d file(s): %s" % (len(files), "ok" if not problems else "%d problem(s)" % len(problems)))
        return 1 if problems else 0
    if cmd == "fline":
        if len(argv) < 4:
            print(__doc__)
            return 3
        d, frame = argv[2], int(argv[3])
        opts = dict(zip(argv[4::2], argv[5::2]))
        fields, imgsz = load_dump(d, frame)
        prev = int(opts.get("--prev", "%x" % FNV_BASIS), 16)
        mclk = opts.get("--mclk")
        line, _ = format_f(frame, int(opts.get("--anc", "0")), int(mclk) if mclk else None, None,
                           fields, prev, imgsz)
        print(line)
        return 0
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
