#!/usr/bin/env python3
"""Compare SNES hash-line files and canonical dumps (docs/snes-oracle-format.md).

    compare.py lines A.hash B.hash [options]
        F lines frame by frame, A and P lines as sequences. Reports the
        first divergence (frame and fields) and how many frames differ per
        field.
          --fields f,g     compare only these state fields (default: all)
          --ignore f,g     leave these fields out
          --timing         also compare mclk (F), mclk and d (A), t (P)
          --align anc      pair F lines by their anc value instead of frame
          --frames N       compare the first N frames; both files must
                           have at least N F lines
          --no-seq         skip the A and P sequences
          --allow-clk      compare files of different APU clocks (clk=)
        Both files need the version header with the same region; their F
        lines must be numbered 1, 2, 3, ... without gaps, and without
        --frames both must have the same number of them. When the picture
        differs and both files carry L lines, the first differing row is
        reported.

    compare.py dumps DIR_A DIR_B [--field wram] [--mask FILE] [--page N]
        byte-wise comparison of the dumped frames both directories share;
        histogram of the addresses that differ permanently (in every dumped
        frame from their first difference on), grouped in pages of N bytes
        (default 256)

    compare.py mask OUT DIR_00 DIR_FF [DIR_00 DIR_FF ...] --frame F [--field wram]
        mask of the bytes the program defined: 1 where the dump of fill 00
        equals the dump of fill ff in every given pair, else 0

    compare.py selftest

Exit codes: 0 equal, 1 different, 2 input missing (skip), 3 usage or
format error.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hashline as H  # noqa: E402


def usage(msg=None):
    if msg:
        print("compare.py:", msg, file=sys.stderr)
    print(__doc__, file=sys.stderr)
    return 3


def parse_opts(args, flags, valued):
    pos, opts = [], {}
    i = 0
    while i < len(args):
        a = args[i]
        if a in flags:
            opts[a] = True
        elif a in valued:
            if i + 1 >= len(args):
                raise ValueError("option %s needs a value" % a)
            opts[a] = args[i + 1]
            i += 1
        elif a.startswith("--"):
            raise ValueError("unknown option " + a)
        else:
            pos.append(a)
        i += 1
    return pos, opts


def check_numbering(recs, path, out):
    """F lines must be numbered 1, 2, 3, ... Returns False on a gap."""
    expect = 1
    for r in recs:
        if r["type"] != "F":
            continue
        if r["frame"] != expect:
            out("F line missing in %s: F %d where F %d was expected" % (path, r["frame"], expect))
            return False
        expect += 1
    return True


def first_row(la, lb, frame):
    """First differing picture row of frame from the L lines, or None."""
    xa = next((r["rows"] for r in la if r["frame"] == frame), None)
    xb = next((r["rows"] for r in lb if r["frame"] == frame), None)
    if xa is None or xb is None:
        return None
    k = next((i for i, (x, y) in enumerate(zip(xa, xb)) if x != y), None)
    if k is None and len(xa) != len(xb):
        k = min(len(xa), len(xb))
    return k


def compare_lines(path_a, path_b, fields=None, timing=False, align="frame", frames=None, seq=True, out=print,
                  allow_clk=False):
    for p in (path_a, path_b):
        if not os.path.exists(p):
            out("missing input: " + p)
            return 2
    try:
        ha, ra = H.read_file(path_a)
        hb, rb = H.read_file(path_b)
    except ValueError as e:
        out("format error: %s" % e)
        return 3
    for h, p in ((ha, path_a), (hb, path_b)):
        if h is None or h.get("version") != H.VERSION:
            out("format error: %s has no version %d header" % (p, H.VERSION))
            return 3
    if ha.get("region") != hb.get("region"):
        out("error: different regions (%s, %s)" % (ha.get("region"), hb.get("region")))
        return 3
    if ha.get("clk") != hb.get("clk"):
        if not allow_clk:
            out("error: different APU clocks (clk=%s, clk=%s); --allow-clk to compare anyway" % (
                ha.get("clk"), hb.get("clk")))
            return 3
        out("warning: different APU clocks (clk=%s, clk=%s)" % (ha.get("clk"), hb.get("clk")))
    if not check_numbering(ra, path_a, out) or not check_numbering(rb, path_b, out):
        return 1
    if ha.get("rom", "-") != "-" and hb.get("rom", "-") != "-" and ha["rom"] != hb["rom"]:
        out("warning: different ROMs (%s, %s)" % (ha["rom"], hb["rom"]))
    fields = fields or list(H.FIELDS)
    keys = fields + (["anc"] if align == "frame" else []) + (["mclk"] if timing else [])
    fa = [r for r in ra if r["type"] == "F"]
    fb = [r for r in rb if r["type"] == "F"]
    if align == "anc":
        def by_anc(recs):
            d = {}
            for r in recs:
                d.setdefault(r["anc"], r)
            return d
        da, db = by_anc(fa), by_anc(fb)
        common = sorted(set(da) & set(db), key=int)
        pairs = [(da[k], db[k]) for k in common]
    else:
        pairs = list(zip(fa, fb))
    status = 0
    if not fa or not fb:
        out("no F lines in %s" % (path_a if not fa else path_b))
        return 1
    if frames:
        short = [(p, len(x)) for p, x in ((path_a, fa), (path_b, fb)) if len(x) < frames]
        for p, n in short:
            out("%s has %d F lines, %d required" % (p, n, frames))
        if short:
            status = 1
        pairs = pairs[:frames]
    first, first_fields, counts = None, [], {}
    for x, y in pairs:
        diff = [k for k in keys if x.get(k) != y.get(k) and x.get(k) != "-" and y.get(k) != "-"]
        for k in diff:
            counts[k] = counts.get(k, 0) + 1
        if diff and first is None:
            first, first_fields = (x["frame"], y["frame"]), diff
    out("compared %d F lines (%s: %d, %s: %d)" % (len(pairs), ha.get("oracle"), len(fa), hb.get("oracle"), len(fb)))
    if not frames and align == "frame" and len(fa) != len(fb):
        out("F line count differs: %d vs %d" % (len(fa), len(fb)))
        status = 1
    if first is None:
        out("F lines: equal")
    else:
        status = 1
        where = "frame %d" % first[0] if first[0] == first[1] else "frames %d / %d" % first
        out("first divergence: %s fields %s" % (where, ",".join(first_fields)))
        if "img" in first_fields:
            row = first_row([r for r in ra if r["type"] == "L"], [r for r in rb if r["type"] == "L"], first[0])
            if row is not None:
                out("first differing picture row (L lines): %d (scanline %d)" % (row, row + 1))
        out("frames differing per field: " + " ".join("%s=%d" % (k, counts[k]) for k in keys if k in counts))
    if seq:
        for kind, keyset in (("A", ["pc", "tag"] + (["anc", "mclk", "d"] if timing else [])),
                             ("P", ["side", "port", "val"] + (["t"] if timing else []))):
            sa = [r for r in ra if r["type"] == kind]
            sb = [r for r in rb if r["type"] == kind]
            if frames:
                sa = [r for r in sa if r["frame"] <= frames]
                sb = [r for r in sb if r["frame"] <= frames]
            for side in (("c", "s") if kind == "P" else (None,)):
                xa = [r for r in sa if side is None or r["side"] == side]
                xb = [r for r in sb if side is None or r["side"] == side]
                if not xa and not xb:
                    continue
                name = kind + ("" if side is None else " " + side)
                k = next((i for i, (x, y) in enumerate(zip(xa, xb))
                          if any(x.get(f) != y.get(f) for f in keyset)), None)
                if k is None and len(xa) == len(xb):
                    out("%s lines: %d, equal" % (name, len(xa)))
                elif k is None:
                    status = 1
                    out("%s lines: %d vs %d, equal over the common prefix" % (name, len(xa), len(xb)))
                else:
                    status = 1
                    out("%s lines: first divergence at entry %d (frame %d / %d): %s | %s" % (
                        name, k, xa[k]["frame"], xb[k]["frame"],
                        " ".join("%s=%s" % (f, xa[k].get(f)) for f in keyset),
                        " ".join("%s=%s" % (f, xb[k].get(f)) for f in keyset)))
    return status


def dump_frames(d, field):
    suffix = "." + field + ".bin"
    return sorted(int(n[1:7]) for n in os.listdir(d) if n.startswith("f") and n.endswith(suffix))


def compare_dumps(dir_a, dir_b, field="wram", mask=None, page=256, out=print):
    for d in (dir_a, dir_b):
        if not os.path.isdir(d):
            out("missing input: " + d)
            return 2
    frames = sorted(set(dump_frames(dir_a, field)) & set(dump_frames(dir_b, field)))
    if not frames:
        out("no common %s dumps" % field)
        return 2
    if mask is not None:
        with open(mask, "rb") as f:
            mask = f.read()
    first_diff, last_state, status = {}, {}, 0
    for fr in frames:
        with open(H.dump_path(dir_a, fr, field), "rb") as f:
            a = f.read()
        with open(H.dump_path(dir_b, fr, field), "rb") as f:
            b = f.read()
        if len(a) != len(b):
            out("frame %d: %s sizes differ (%d, %d)" % (fr, field, len(a), len(b)))
            status = 1
            continue
        diff = [i for i in range(len(a)) if a[i] != b[i] and (mask is None or mask[i])]
        out("frame %d: %s %d bytes differ%s" % (fr, field, len(diff), " (masked)" if mask is not None else ""))
        if diff:
            status = 1
        ds = set(diff)
        for i in diff:
            first_diff.setdefault(i, fr)
        for i in list(first_diff):
            if i not in ds:
                last_state[i] = False
            elif i not in last_state:
                last_state[i] = True
        last = (a, b)
    permanent = sorted(i for i in first_diff if last_state.get(i, True))
    out("permanently differing %s addresses: %d" % (field, len(permanent)))
    if permanent:
        hist = {}
        for i in permanent:
            hist[i // page] = hist.get(i // page, 0) + 1
        for p in sorted(hist):
            out("  %06x-%06x: %d" % (p * page, p * page + page - 1, hist[p]))
        a, b = last
        out("  first addresses (offset: A B since frame): " + " ".join(
            "%05x:%02x/%02x@%d" % (i, a[i], b[i], first_diff[i]) for i in permanent[:16]))
    return status


def make_mask(out_path, pairs, frame, field="wram", out=print):
    mask = None
    for d00, dff in pairs:
        for d in (d00, dff):
            if not os.path.exists(H.dump_path(d, frame, field)):
                out("missing input: " + H.dump_path(d, frame, field))
                return 2
        with open(H.dump_path(d00, frame, field), "rb") as f:
            a = f.read()
        with open(H.dump_path(dff, frame, field), "rb") as f:
            b = f.read()
        m = bytes(1 if x == y else 0 for x, y in zip(a, b))
        mask = m if mask is None else bytes(x & y for x, y in zip(mask, m))
    with open(out_path, "wb") as f:
        f.write(mask)
    out("mask %s: %d of %d bytes defined" % (out_path, sum(mask), len(mask)))
    return 0


def selftest():
    import tempfile
    ok = True
    log = []

    def check(cond, what):
        nonlocal ok
        if not cond:
            print("FAIL", what)
            print("\n".join(log))
            ok = False

    def write(path, frames, fault=None, oracle="t", skip=None, field_fault=None, clk="meas", lines_l=False):
        chain = H.FNV_BASIS
        lines = [H.format_header(oracle, "-", clk=clk)]
        for fr in range(1, frames + 1):
            if fr == skip:
                continue
            wram = bytearray(0x20000)
            wram[0x100] = fr & 0xFF
            if fault and fr >= fault[0]:
                wram[fault[1]] ^= 0x01
            fields = {"cpu": bytes(14), "smp": bytes(13), "apuio": bytes(8), "wram": bytes(wram),
                      "vram": bytes(0x10000), "oam": bytes(544), "cgram": bytes(512), "ppu": bytes(77),
                      "aram": bytes(0x10000), "dsp": bytes(128), "img": bytes(256 * 224 * 2),
                      "sram": bytes([0xFF]) * 0x2000}
            if field_fault and fr == field_fault[0]:
                v = bytearray(fields[field_fault[1]])
                v[field_fault[2]] ^= 0x01
                fields[field_fault[1]] = bytes(v)
            line, chain = H.format_f(fr, fr - 1, H.window_mclk(fr) + 2, None, fields, chain, "256x224")
            lines.append(line)
            if lines_l:
                lines.append(H.format_l(fr, fields["img"], "256x224"))
            lines.append("P %d c t=%d port=0 val=%02x" % (fr, fr * 1000, fr & 0xFF))
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")

    with tempfile.TemporaryDirectory() as d:
        a, b, c = (os.path.join(d, n) for n in ("a.hash", "b.hash", "c.hash"))
        write(a, 20)
        write(b, 20)
        write(c, 20, fault=(7, 0x1234))
        log.clear()
        check(compare_lines(a, b, out=log.append) == 0, "equal files")
        log.clear()
        rc = compare_lines(a, c, out=log.append)
        check(rc == 1 and any("first divergence: frame 7 fields wram" == l for l in log), "fault at 7")
        check(any("wram=14" in l for l in log), "fault persists 14 frames")
        log.clear()
        check(compare_lines(a, c, fields=["vram"], out=log.append) == 0, "field filter")
        # A truncated file is never equal: neither with --frames beyond its
        # end nor without --frames.
        t, hdr, gap, one, nclk = (os.path.join(d, n) for n in ("t.hash", "h.hash", "g.hash", "o.hash", "k.hash"))
        write(t, 12)
        log.clear()
        check(compare_lines(a, t, out=log.append) == 1, "truncated file, no --frames")
        log.clear()
        check(compare_lines(a, t, frames=15, out=log.append) == 1 and any("12 F lines, 15 required" in l for l in log),
              "truncated file, --frames 15")
        log.clear()
        check(compare_lines(a, t, frames=12, out=log.append) == 0, "common prefix of 12 frames")
        with open(hdr, "w") as f:
            f.write(H.format_header("t", "-") + "\n")
        log.clear()
        check(compare_lines(a, hdr, frames=5, out=log.append) == 1, "header only")
        log.clear()
        check(compare_lines(hdr, hdr, out=log.append) == 1, "header only against itself")
        # A missing F line (frame 9 left out) is reported, not paired off.
        write(gap, 20, skip=9)
        log.clear()
        check(compare_lines(a, gap, out=log.append) == 1 and any("F 10 where F 9" in l for l in log), "missing line")
        # A difference in exactly one field is reported as that field only.
        for fld, off in (("cgram", 0x10), ("aram", 0xFFFF), ("img", 256 * 2 * 100 + 6), ("sram", 0x1FF0)):
            write(one, 20, field_fault=(11, fld, off), lines_l=True)
            write(b, 20, lines_l=True)
            log.clear()
            rc = compare_lines(b, one, out=log.append)
            check(rc == 1 and "first divergence: frame 11 fields " + fld in log
                  and "frames differing per field: %s=1" % fld in log, "single field " + fld + " | ".join(log))
            if fld == "img":
                check(any("first differing picture row (L lines): 100" in l for l in log), "L line row")
        # Different APU clocks are refused unless allowed.
        write(nclk, 20, clk="nom")
        log.clear()
        check(compare_lines(a, nclk, out=log.append) == 3, "clk mismatch refused")
        log.clear()
        check(compare_lines(a, nclk, allow_clk=True, out=log.append) == 0, "clk mismatch allowed")
        log.clear()
        check(compare_lines(a, os.path.join(d, "none"), out=log.append) == 2, "missing input")
        with open(os.path.join(d, "bad.hash"), "w") as f:
            f.write("X nonsense\n")
        log.clear()
        check(compare_lines(a, os.path.join(d, "bad.hash"), out=log.append) == 3, "format error")
        # Dumps and masks.
        for name, fill, fault in (("d00", 0, False), ("dff", 0xFF, False), ("e00", 0, True)):
            os.mkdir(os.path.join(d, name))
            for fr in (10, 20):
                w = bytearray([fill]) * 0x20000
                w[0:0x100] = bytes(range(256))
                if fault and fr >= 10:
                    w[0x42] ^= 0x80
                if fault and fr == 10:
                    w[0x43] ^= 0x01
                with open(H.dump_path(os.path.join(d, name), fr, "wram"), "wb") as f:
                    f.write(bytes(w))
        log.clear()
        mpath = os.path.join(d, "mask.bin")
        check(make_mask(mpath, [(os.path.join(d, "d00"), os.path.join(d, "dff"))], 20, out=log.append) == 0
              and "256 of 131072" in log[-1], "mask " + " ".join(log))
        log.clear()
        check(compare_dumps(os.path.join(d, "d00"), os.path.join(d, "dff"), mask=mpath, out=log.append) == 0,
              "masked equal")
        log.clear()
        rc = compare_dumps(os.path.join(d, "d00"), os.path.join(d, "e00"), out=log.append)
        check(rc == 1 and "permanently differing wram addresses: 1" in log, "permanent " + " | ".join(log))
    print("compare selftest:", "ok" if ok else "FAILED")
    return 0 if ok else 1


def main(argv):
    if len(argv) < 2:
        return usage()
    cmd, rest = argv[1], argv[2:]
    try:
        if cmd == "selftest":
            return selftest()
        if cmd == "lines":
            pos, o = parse_opts(rest, {"--timing", "--no-seq", "--allow-clk"},
                                {"--fields", "--ignore", "--align", "--frames"})
            if len(pos) != 2:
                return usage("lines needs two files")
            fields = o["--fields"].split(",") if "--fields" in o else list(H.FIELDS)
            if "--ignore" in o:
                fields = [f for f in fields if f not in o["--ignore"].split(",")]
            bad = [f for f in fields if f not in H.FIELDS]
            if bad:
                return usage("unknown fields " + ",".join(bad))
            align = o.get("--align", "frame")
            if align not in ("frame", "anc"):
                return usage("--align is frame or anc")
            return compare_lines(pos[0], pos[1], fields, "--timing" in o, align,
                                 int(o["--frames"]) if "--frames" in o else None, "--no-seq" not in o,
                                 allow_clk="--allow-clk" in o)
        if cmd == "dumps":
            pos, o = parse_opts(rest, set(), {"--field", "--mask", "--page"})
            if len(pos) != 2:
                return usage("dumps needs two directories")
            return compare_dumps(pos[0], pos[1], o.get("--field", "wram"), o.get("--mask"), int(o.get("--page", "256")))
        if cmd == "mask":
            pos, o = parse_opts(rest, set(), {"--frame", "--field"})
            if len(pos) < 3 or len(pos) % 2 == 0 or "--frame" not in o:
                return usage("mask needs OUT, pairs of directories and --frame")
            pairs = list(zip(pos[1::2], pos[2::2]))
            return make_mask(pos[0], pairs, int(o["--frame"]), o.get("--field", "wram"))
    except ValueError as e:
        return usage(str(e))
    return usage("unknown command " + cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
