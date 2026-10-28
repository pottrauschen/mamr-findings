#!/usr/bin/env python3
"""Compare two NES hash files (docs/nes-oracle-format.md).

    compare.py selftest
    compare.py lines A B [--fields f1,f2,...] [--timing] [--frames N] [--align inp|frame]
        frame by frame: every state field present in both files (a field
        written as "-" on either side is skipped), inp by default, cyc and
        dot only with --timing. Prints the first divergence and a per-field
        count of differing frames. Exit 0 = equal, 1 = different.
    compare.py mask OUT DIR... --frame F [--field ram]
        write the bytes that are equal in all dumps of frame F (fill 00
        and fill ff runs) as a mask file (1 = defined)
    compare.py dumps A B [--field ram] [--mask FILE]
        compare the canonical dumps of two directories byte by byte,
        optionally only in the masked bytes

Exit codes: 0 equal, 1 different, 2 input missing, 3 usage error.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hashline as H  # noqa: E402


def usage(msg=None):
    if msg:
        print("compare.py: " + msg)
    print(__doc__)
    return 3


def parse_opts(args, flags, valued):
    opts = {f: False for f in flags}
    opts.update({v: None for v in valued})
    rest = []
    while args:
        a = args.pop(0)
        if a in flags:
            opts[a] = True
        elif a in valued:
            if not args:
                raise ValueError("option %s needs a value" % a)
            opts[a] = args.pop(0)
        else:
            rest.append(a)
    return opts, rest


def compare_lines(path_a, path_b, fields=None, timing=False, frames=None, align="frame", out=print):
    """Returns (equal, per-field differing frame counts)."""
    ha, fa, _ = H.read_file(path_a)
    hb, fb, _ = H.read_file(path_b)
    if ha.get("version") != H.VERSION or hb.get("version") != H.VERSION:
        out("version mismatch: %s / %s" % (ha.get("version"), hb.get("version")))
        return False, {}
    if ha.get("region") != hb.get("region"):
        out("region differs: %s / %s" % (ha.get("region"), hb.get("region")))
        return False, {}
    for k in ("rom", "fill"):
        if ha.get(k) != hb.get(k):
            out("note: header %s differs: %s / %s" % (k, ha.get(k), hb.get(k)))
    keys = list(fields) if fields else list(H.FIELDS)
    keys = [k for k in keys if k in H.FIELDS]
    cmp_keys = keys + (["inp"] if "inp" not in keys else [])
    if timing:
        cmp_keys += ["cyc", "dot"]
    if align == "inp":
        pairs = []
        ib = {r["inp"]: r for r in fb}
        for ra in fa:
            rb = ib.get(ra["inp"])
            if rb is not None:
                pairs.append((ra, rb))
        cmp_keys = [k for k in cmp_keys if k != "inp"]
    else:
        n = min(len(fa), len(fb))
        pairs = list(zip(fa[:n], fb[:n]))
    if frames is not None:
        pairs = pairs[:frames]
    if not pairs:
        out("no frames to compare")
        return False, {}
    diffs = {k: 0 for k in cmp_keys}
    first = None
    for ra, rb in pairs:
        bad = []
        for k in cmp_keys:
            va, vb = ra.get(k), rb.get(k)
            if va is None or vb is None or va == "-" or vb == "-":
                continue
            if va != vb:
                diffs[k] += 1
                bad.append(k)
        if bad and first is None:
            first = (ra["n"], rb["n"], bad)
    if len(fa) != len(fb):
        out("frame counts differ: %d / %d (compared %d)" % (len(fa), len(fb), len(pairs)))
    if first is None:
        out("equal in %d frames: %s" % (len(pairs), " ".join(cmp_keys)))
        return len(fa) == len(fb) or frames is not None, diffs
    out("first divergence: frame %d/%d fields %s" % (first[0], first[1], " ".join(first[2])))
    out("differing frames per field: " + " ".join("%s=%d" % (k, v) for k, v in diffs.items() if v))
    return False, diffs


def dump_frames(d, field):
    frames = []
    for name in os.listdir(d):
        if name.startswith("f") and name.endswith(".%s.bin" % field):
            frames.append(int(name[1:7]))
    return sorted(frames)


def compare_dumps(dir_a, dir_b, field="ram", mask=None, out=print):
    frames = [f for f in dump_frames(dir_a, field) if f in set(dump_frames(dir_b, field))]
    if not frames:
        out("no common dumped frames for " + field)
        return False
    m = None
    if mask:
        with open(mask, "rb") as f:
            m = f.read()
    equal = True
    for fr in frames:
        with open(H.dump_path(dir_a, fr, field), "rb") as f:
            a = f.read()
        with open(H.dump_path(dir_b, fr, field), "rb") as f:
            b = f.read()
        if len(a) != len(b):
            out("frame %d: sizes differ %d / %d" % (fr, len(a), len(b)))
            equal = False
            continue
        bad = [i for i in range(len(a)) if a[i] != b[i] and (m is None or (i < len(m) and m[i]))]
        if bad:
            equal = False
            out("frame %d %s: %d bytes differ, first at %04x (%02x / %02x)" % (fr, field, len(bad), bad[0],
                                                                              a[bad[0]], b[bad[0]]))
        else:
            out("frame %d %s: equal%s" % (fr, field, " (masked)" if m is not None else ""))
    return equal


def make_mask(out_path, dirs, frame, field="ram", out=print):
    datas = []
    for d in dirs:
        with open(H.dump_path(d, frame, field), "rb") as f:
            datas.append(f.read())
    n = min(len(x) for x in datas)
    mask = bytes(1 if all(x[i] == datas[0][i] for x in datas) else 0 for i in range(n))
    with open(out_path, "wb") as f:
        f.write(mask)
    out("mask %s: %d of %d bytes defined" % (out_path, sum(mask), n))


def selftest():
    import tempfile
    fails = []

    def check(cond, what):
        if not cond:
            fails.append(what)

    def write(path, frames, fault=None, missing=None):
        fields = {"cpu": H.cpu_bytes(1, 2, 3, 0xFD, 0x24), "ram": bytes(2048), "vram": bytes(4096),
                  "oam": bytes(256), "pal": bytes(32), "prgram": bytes(8192), "ppu": bytes(11),
                  "prgmap": bytes(16), "chrmap": bytes(32), "mirq": bytes(4), "img": bytes(H.FIXED_SIZES["img"])}
        chain = H.FNV_BASIS
        with open(path, "w") as f:
            f.write(H.format_header("t", "0" * 40) + "\n")
            for n in range(1, frames + 1):
                fl = dict(fields)
                if fault and fault[0] == n:
                    fl["ram"] = bytes([0x5A]) + bytes(2047)
                if missing:
                    fl[missing] = None
                line, chain = H.format_f(n, n - 1, 100 * n, None, 0xC000, fl, chain)
                f.write(line + "\n")

    d = tempfile.mkdtemp()
    try:
        a, b, c, e = [os.path.join(d, x + ".hash") for x in "abce"]
        write(a, 10)
        write(b, 10)
        write(c, 10, fault=(6, 0))
        write(e, 10, missing="img")
        logs = []
        ok, _ = compare_lines(a, b, out=logs.append)
        check(ok, "equal files")
        ok, diffs = compare_lines(a, c, out=logs.append)
        check(not ok and diffs["ram"] == 1 and "frame 6/6 fields ram" in logs[-2], "fault found: %r" % logs[-2:])
        ok, _ = compare_lines(a, e, out=logs.append)
        check(ok, "missing field skipped")
        ok, _ = compare_lines(a, c, fields=["cpu"], out=logs.append)
        check(ok, "field selection")
        ok, _ = compare_lines(a, c, frames=5, out=logs.append)
        check(ok, "frame limit")
    finally:
        import shutil
        shutil.rmtree(d)
    if fails:
        print("compare selftest FAILED:", ", ".join(fails))
        return 1
    print("compare selftest ok")
    return 0


def main(argv):
    if len(argv) < 2:
        return usage()
    cmd = argv[1]
    if cmd == "selftest":
        return selftest()
    try:
        if cmd == "lines":
            opts, rest = parse_opts(argv[2:], ["--timing"], ["--fields", "--frames", "--align"])
            if len(rest) != 2:
                return usage("lines needs two files")
            for p in rest:
                if not os.path.exists(p):
                    print("missing: " + p)
                    return 2
            fields = opts["--fields"].split(",") if opts["--fields"] else None
            frames = int(opts["--frames"]) if opts["--frames"] else None
            ok, _ = compare_lines(rest[0], rest[1], fields, opts["--timing"], frames, opts["--align"] or "frame")
            return 0 if ok else 1
        if cmd == "mask":
            opts, rest = parse_opts(argv[2:], [], ["--frame", "--field"])
            if len(rest) < 3 or not opts["--frame"]:
                return usage("mask needs OUT, two or more DIRs and --frame")
            make_mask(rest[0], rest[1:], int(opts["--frame"]), opts["--field"] or "ram")
            return 0
        if cmd == "dumps":
            opts, rest = parse_opts(argv[2:], [], ["--field", "--mask"])
            if len(rest) != 2:
                return usage("dumps needs two directories")
            return 0 if compare_dumps(rest[0], rest[1], opts["--field"] or "ram", opts["--mask"]) else 1
    except ValueError as e:
        return usage(str(e))
    return usage("unknown command " + cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
