#!/usr/bin/env python3
"""Compare two Super Pang hash files (docs/spang-oracle-format.md).

    compare.py selftest
    compare.py lines A B [--fields f1,f2,...] [--no-timing] [--frames N]
            [--skip-frames LIST] [--skip-field F:LIST] [--report FILE]
        frame by frame: the state fields (default: all; a field written
        as "-" on either side is skipped) and zclk (unless --no-timing).
        --skip-frames excludes frames (e.g. "613,1216" or "600-620") from
        the verdict; they are still listed. --skip-field does the same for
        one field only (e.g. "img:5"; repeatable). Prints the first
        divergence and a per-field count of differing frames. Exit 0 =
        equal.
    compare.py dumps A B --field F [--frame N]
        compare the canonical dumps (DIR/f<N:06d>.<F>.bin) of two
        directories byte by byte: differing offsets with both values
    compare.py pixels A B [--png PREFIX]
        compare two picture dumps (field img, DIR/f<N:06d>.img.bin) pixel
        by pixel: the count of differing pixels, their bounding box and
        the most frequent value pairs (xRGB444). With --png the two
        pictures and a difference mask are written as PREFIX-a.png,
        PREFIX-b.png and PREFIX-diff.png.
    compare.py iolog A B [--context N]
        compare two I/O logs (format section 7) line by line: the first
        differing line with N lines of context (default 5), and the count
        of lines per kind

Exit codes: 0 equal, 1 different, 2 input missing, 3 usage error.
"""
import collections
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True  # no __pycache__ in the source tree
import hashline as H  # noqa: E402


def parse_frames(spec):
    out = set()
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def parse_field_skips(specs):
    """["img:5", "pal:7-9"] -> {"img": {5}, "pal": {7, 8, 9}}"""
    out = {}
    for spec in specs or ():
        field, _, frames = spec.partition(":")
        out.setdefault(field, set()).update(parse_frames(frames))
    return out


def compare_lines(path_a, path_b, fields=None, timing=True, frames=None, skip=(), out=print, skip_fields=None):
    """Returns (equal, per-field differing frame lists)."""
    skip_fields = skip_fields or {}
    ha, fa, _ = H.read_file(path_a)
    hb, fb, _ = H.read_file(path_b)
    for h, p in ((ha, path_a), (hb, path_b)):
        if h.get("format") != "spfh" or h.get("version") != H.VERSION:
            out("%s: not an spfh %d file" % (p, H.VERSION))
            return False, {}
    for k in ("input", "ym2413"):
        if ha.get(k) != hb.get(k):
            out("note: header %s differs: %s / %s" % (k, ha.get(k), hb.get(k)))
    keys = [k for k in (fields or H.FIELDS) if k in H.FIELDS]
    if timing:
        keys = ["zclk"] + keys
    n = min(len(fa), len(fb))
    if frames is not None:
        n = min(n, frames)
    if len(fa) != len(fb) and frames is None:
        out("note: %d / %d F lines, comparing %d" % (len(fa), len(fb), n))
    diffs = {k: [] for k in keys}
    first = None
    for ra, rb in zip(fa[:n], fb[:n]):
        for k in keys:
            va, vb = ra.get(k, "-"), rb.get(k, "-")
            if k != "zclk" and (va == "-" or vb == "-"):
                continue
            if va != vb:
                diffs[k].append(ra["n"])
                if first is None and ra["n"] not in skip and ra["n"] not in skip_fields.get(k, ()):
                    first = (ra["n"], k, va, vb)
    equal = first is None
    out("compared %d frames, fields: %s" % (n, " ".join(keys)))
    for k in keys:
        lst = diffs[k]
        if lst:
            shown = ",".join(str(x) for x in lst[:12]) + (",..." if len(lst) > 12 else "")
            out("  %-5s %5d frames differ (first %d; %s)" % (k, len(lst), lst[0], shown))
        else:
            out("  %-5s equal" % k)
    if skip:
        out("  skipped frames: %s" % ",".join(str(x) for x in sorted(skip)[:20]))
    for k in sorted(skip_fields):
        out("  skipped frames of %s: %s" % (k, ",".join(str(x) for x in sorted(skip_fields[k])[:20])))
    if first:
        out("first divergence: frame %d field %s: %s / %s" % first)
    out("result: %s" % ("EQUAL" if equal else "DIFFERENT"))
    return equal, diffs


def compare_dumps(da, db, field, frame=None, out=print, limit=64):
    names = sorted(x for x in os.listdir(da) if x.endswith("." + field + ".bin"))
    if frame is not None:
        names = ["f%06d.%s.bin" % (frame, field)]
    equal = True
    for name in names:
        pa, pb = os.path.join(da, name), os.path.join(db, name)
        if not os.path.exists(pa) or not os.path.exists(pb):
            out("%s: missing on one side" % name)
            equal = False
            continue
        a, b = open(pa, "rb").read(), open(pb, "rb").read()
        d = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
        if len(a) != len(b):
            out("%s: sizes %d / %d" % (name, len(a), len(b)))
            equal = False
        if d:
            equal = False
            out("%s: %d bytes differ" % (name, len(d)))
            for i in d[:limit]:
                out("  +%04x: %02x / %02x" % (i, a[i], b[i]))
    return equal


IMG_W, IMG_H = 384, 240


def write_png(path, rgb, w=IMG_W, h=IMG_H):
    """8-bit RGB PNG from w*h*3 bytes."""
    raw = b"".join(b"\0" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def img_pixels(data):
    return [data[i] | data[i + 1] << 8 for i in range(0, len(data) - 1, 2)]


def img_rgb(px):
    return bytes(c for v in px for c in (((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17))


def compare_pixels(pa, pb, png=None, out=print):
    with open(pa, "rb") as f:
        a = img_pixels(f.read())
    with open(pb, "rb") as f:
        b = img_pixels(f.read())
    if len(a) != IMG_W * IMG_H or len(b) != IMG_W * IMG_H:
        out("not a %d x %d picture: %d / %d pixels" % (IMG_W, IMG_H, len(a), len(b)))
        return False
    d = [i for i in range(len(a)) if a[i] != b[i]]
    out("%d pixels differ" % len(d))
    if d:
        xs, ys = [i % IMG_W for i in d], [i // IMG_W for i in d]
        out("  box x %d-%d, y %d-%d" % (min(xs), max(xs), min(ys), max(ys)))
        pairs = collections.Counter((a[i], b[i]) for i in d).most_common(8)
        out("  values (a / b, count): " + ", ".join("%03x/%03x %d" % (x, y, n) for (x, y), n in pairs))
    if png:
        write_png(png + "-a.png", img_rgb(a))
        write_png(png + "-b.png", img_rgb(b))
        mask = [0xFFF if a[i] != b[i] else 0 for i in range(len(a))]
        write_png(png + "-diff.png", img_rgb(mask))
    return not d


def read_iolog(path):
    with open(path, "r", encoding="ascii") as f:
        return [line.rstrip("\n") for line in f if line.strip() and not line.startswith("#")]


def compare_iolog(pa, pb, context=5, out=print):
    a, b = read_iolog(pa), read_iolog(pb)
    for name, lines in ((pa, a), (pb, b)):
        kinds = {}
        for line in lines:
            t = line.split()
            key = t[0] + " " + t[3] if len(t) >= 4 else t[0]
            kinds[key] = kinds.get(key, 0) + 1
        out("%s: %d lines (%s)" % (name, len(lines), " ".join("%s:%d" % kv for kv in sorted(kinds.items()))))
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            out("first difference at line %d:" % (i + 1))
            for j in range(max(0, i - context), min(n, i + context + 1)):
                mark = ">" if j == i else " "
                out("%s %-40s | %s" % (mark, a[j], b[j]))
            return False
    if len(a) != len(b):
        out("equal over %d lines, lengths differ" % n)
        return False
    out("I/O logs equal")
    return True


def selftest():
    import tempfile
    fields = {"z80": bytes(32), "wram": bytes(0x2000), "vram": bytes(0x1800), "obj": bytes(0x1000),
              "pal": bytes(0x1000), "bank": bytes(6), "irq": bytes(40), "eep": bytes(148), "ym": b"", "oki": b"", "img": None}
    lines_a, lines_b = [], []
    pa = pb = 0
    for n in range(1, 6):
        fa = dict(fields)
        fb = dict(fields)
        if n >= 4:
            fb["wram"] = bytes([n]) + bytes(0x1FFF)
        la, pa = H.format_fline(n, H.frame_cycles(n), fa, pa)
        lb, pb = H.format_fline(n, H.frame_cycles(n), fb, pb)
        lines_a.append(la)
        lines_b.append(lb)
    with tempfile.TemporaryDirectory() as td:
        a, b = os.path.join(td, "a"), os.path.join(td, "b")
        for p, ls in ((a, lines_a), (b, lines_b)):
            with open(p, "w") as f:
                f.write("H spfh 1 oracle=test set=spang\n" + "\n".join(ls) + "\n")
        quiet = lambda s: None
        eq, d = compare_lines(a, a, out=quiet)
        assert eq
        eq, d = compare_lines(a, b, out=quiet)
        assert not eq and d["wram"] == [4, 5] and d["z80"] == [] and d["zclk"] == []
        eq, _ = compare_lines(a, b, skip={4, 5}, out=quiet)
        assert eq
        eq, _ = compare_lines(a, b, skip_fields=parse_field_skips(["wram:4-5"]), out=quiet)
        assert eq
        eq, _ = compare_lines(a, b, skip_fields=parse_field_skips(["z80:4-5"]), out=quiet)
        assert not eq
        eq, _ = compare_lines(a, b, fields=["z80", "pal"], out=quiet)
        assert eq
        eq, _ = compare_lines(a, b, frames=3, out=quiet)
        assert eq
        assert parse_frames("3,10-12") == {3, 10, 11, 12}
        # I/O logs
        la, lb = os.path.join(td, "a.io"), os.path.join(td, "b.io")
        with open(la, "w") as f:
            f.write("W 1 100 02 0a\nR 1 120 05 f7\n")
        with open(lb, "w") as f:
            f.write("W 1 100 02 0a\nR 1 121 05 f7\n")
        assert compare_iolog(la, la, out=quiet)
        assert not compare_iolog(la, lb, out=quiet)
        # dumps
        da, db = os.path.join(td, "da"), os.path.join(td, "db")
        os.mkdir(da)
        os.mkdir(db)
        open(os.path.join(da, "f000001.wram.bin"), "wb").write(b"\x00\x01")
        open(os.path.join(db, "f000001.wram.bin"), "wb").write(b"\x00\x02")
        assert compare_dumps(da, da, "wram", out=quiet)
        assert not compare_dumps(da, db, "wram", out=quiet)
        # pictures
        ia, ib = os.path.join(td, "a.img.bin"), os.path.join(td, "b.img.bin")
        pic = bytearray(IMG_W * IMG_H * 2)
        open(ia, "wb").write(bytes(pic))
        pic[2 * (10 * IMG_W + 20)] = 0x0F
        open(ib, "wb").write(bytes(pic))
        lines = []
        assert compare_pixels(ia, ia, out=quiet)
        assert not compare_pixels(ia, ib, os.path.join(td, "p"), out=lines.append)
        assert lines[0] == "1 pixels differ" and lines[1] == "  box x 20-20, y 10-10"
        assert open(os.path.join(td, "p-diff.png"), "rb").read(8) == b"\x89PNG\r\n\x1a\n"
    print("compare selftest ok")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    cmd, args = argv[1], argv[2:]
    if cmd == "selftest":
        return selftest()

    def opt(name, default=None):
        if name in args:
            i = args.index(name)
            v = args[i + 1]
            del args[i:i + 2]
            return v
        return default

    def flag(name):
        if name in args:
            args.remove(name)
            return True
        return False

    if cmd == "lines":
        fields = opt("--fields")
        frames = opt("--frames")
        skip = parse_frames(opt("--skip-frames"))
        field_skips = []
        while "--skip-field" in args:
            field_skips.append(opt("--skip-field"))
        report = opt("--report")
        timing = not flag("--no-timing")
        if len(args) != 2:
            return 3
        for p in args:
            if not os.path.exists(p):
                print("missing: " + p)
                return 2
        lines = []

        def out(s):
            print(s)
            lines.append(s)
        eq, _ = compare_lines(args[0], args[1], fields.split(",") if fields else None, timing,
                              int(frames) if frames else None, skip, out, parse_field_skips(field_skips))
        if report:
            with open(report, "w") as f:
                f.write("\n".join(lines) + "\n")
        return 0 if eq else 1
    if cmd == "dumps":
        field = opt("--field")
        frame = opt("--frame")
        if len(args) != 2 or not field:
            return 3
        return 0 if compare_dumps(args[0], args[1], field, int(frame) if frame else None) else 1
    if cmd == "pixels":
        png = opt("--png")
        if len(args) != 2:
            return 3
        for p in args:
            if not os.path.exists(p):
                print("missing: " + p)
                return 2
        return 0 if compare_pixels(args[0], args[1], png) else 1
    if cmd == "iolog":
        context = int(opt("--context", "5"))
        if len(args) != 2:
            return 3
        return 0 if compare_iolog(args[0], args[1], context) else 1
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
