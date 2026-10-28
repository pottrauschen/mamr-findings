#!/usr/bin/env python3
"""Compare two arcade hash files (docs/arcade-oracle-format.md).

    compare.py selftest
    compare.py lines A B [--fields f1,f2,...] [--no-timing] [--frames N]
            [--skip-frames LIST] [--skip-field F:LIST] [--first K]
        frame by frame: the state fields (default: all of the set; a field
        written as "-" on either side is skipped) and the timing keys
        (unless --no-timing). Prints per field the number of differing
        frames, the first one, and the first divergence over all fields;
        --first K lists the first K differing frames of every field.
        --skip-frames and --skip-field exclude frames from the verdict (they
        are still counted). Exit 0 = equal.
    compare.py regs A B FRAME
        the register fields of one frame side by side, by register
    compare.py dumps A B --field F [--frame N]
        compare canonical dumps (DIR/f<N:06d>.<F>.bin) byte by byte
    compare.py acclog A B [--context N] [--cpu C]
        compare two access logs (format section 6): the first differing
        line per CPU with N lines of context

Exit codes: 0 equal, 1 different, 2 input missing, 3 usage error.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import afh  # noqa: E402


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


def compare_lines(pa, pb, fields=None, timing=True, frames=None, skip=(), skip_fields=None, first=0,
                  out=print):
    skip_fields = skip_fields or {}
    ha, fa, _ = afh.read_file(pa)
    hb, fb, _ = afh.read_file(pb)
    for h, p in ((ha, pa), (hb, pb)):
        if h.get("format") != "afh" or h.get("version") != afh.VERSION:
            out("%s: not an afh %d file" % (p, afh.VERSION))
            return False, {}
    setname = ha.get("set")
    if hb.get("set") != setname or setname not in afh.SETS:
        out("sets differ or unknown: %s / %s" % (setname, hb.get("set")))
        return False, {}
    spec = afh.SETS[setname]
    if ha.get("input") != hb.get("input"):
        out("note: header input differs: %s / %s" % (ha.get("input"), hb.get("input")))
    keys = [k for k in (fields or spec["fields"]) if k in spec["fields"]]
    if timing:
        keys = spec["timing"] + keys
    n = min(len(fa), len(fb))
    if frames is not None:
        n = min(n, frames)
    if len(fa) != len(fb) and frames is None:
        out("note: %d / %d F lines, comparing %d" % (len(fa), len(fb), n))
    diffs = {k: [] for k in keys}
    firstdiv = None
    for ra, rb in zip(fa[:n], fb[:n]):
        for k in keys:
            va, vb = ra.get(k, "-"), rb.get(k, "-")
            if k not in spec["timing"] and (va == "-" or vb == "-"):
                continue
            if va != vb:
                diffs[k].append(ra["n"])
                if firstdiv is None and ra["n"] not in skip and ra["n"] not in skip_fields.get(k, ()):
                    firstdiv = (ra["n"], k, va, vb)
    equal = firstdiv is None
    out("compared %d frames, set %s, keys: %s" % (n, setname, " ".join(keys)))
    for k in keys:
        lst = diffs[k]
        if lst:
            shown = ",".join(str(x) for x in lst[:max(first, 12)]) + (",..." if len(lst) > max(first, 12) else "")
            out("  %-5s %5d frames differ (first %d; %s)" % (k, len(lst), lst[0], shown))
        else:
            out("  %-5s equal" % k)
    if firstdiv:
        va, vb = firstdiv[2], firstdiv[3]
        if len(va) > 80:
            va, vb = va[:80] + "...", vb[:80] + "..."
        out("first divergence: frame %d field %s: %s / %s" % (firstdiv[0], firstdiv[1], va, vb))
    out("result: %s" % ("EQUAL" if equal else "DIFFERENT"))
    return equal, diffs


def compare_regs(pa, pb, frame, out=print):
    _, fa, _ = afh.read_file(pa)
    _, fb, _ = afh.read_file(pb)
    ra = next((r for r in fa if r["n"] == frame), None)
    rb = next((r for r in fb if r["n"] == frame), None)
    if not ra or not rb:
        out("frame %d missing" % frame)
        return False
    same = True
    for k in [k for k in ra["keys"] if (k.startswith("z") or k == "v30") and len(ra[k]) == 64]:
        dec = afh.v30_regs if k == "v30" else afh.z80_regs
        a, b = dec(ra[k]), dec(rb[k])
        d = [r for r in a if a[r] != b[r]]
        if d:
            same = False
        out("%s: %s" % (k, "equal" if not d else ", ".join("%s %x/%x" % (r, a[r], b[r]) for r in d)))
    for k in [k for k in ra["keys"] if k.startswith("clk")]:
        out("%s: %s / %s (%+d)" % (k, ra[k], rb[k], int(rb[k]) - int(ra[k])))
    return same


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


def read_acclog(path, cpu=None):
    with open(path, "r", encoding="ascii") as f:
        lines = [l.rstrip("\n") for l in f if l.strip() and not l.startswith("#")]
    if cpu is not None:
        lines = [l for l in lines if l.split()[0] == str(cpu)]
    return lines


def compare_acclog(pa, pb, context=5, cpu=None, out=print):
    equal = True
    for c in ([cpu] if cpu is not None else [0, 1, 2]):
        a, b = read_acclog(pa, c), read_acclog(pb, c)
        n = min(len(a), len(b))
        i = next((k for k in range(n) if a[k] != b[k]), None)
        if i is None and len(a) == len(b):
            out("cpu %d: %d accesses, equal" % (c, len(a)))
            continue
        equal = False
        if i is None:
            i = n
        out("cpu %d: %d / %d accesses, first difference at line %d" % (c, len(a), len(b), i + 1))
        for k in range(max(0, i - context), min(max(len(a), len(b)), i + context + 1)):
            la = a[k] if k < len(a) else "-"
            lb = b[k] if k < len(b) else "-"
            out("  %s %-40s | %s" % ("*" if la != lb else " ", la, lb))
    return equal


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    spec = afh.SETS["ikari"]
    paths = []
    for variant in (0, 1):
        prev = 0
        lines = ["H afh 1 oracle=x core=x judge=- set=ikari input=-"]
        for n in range(1, 4):
            fields = {name: bytes([n]) * spec["raw"].get(name, 4) for name in spec["fields"]}
            if variant and n == 2:
                fields["snd"] = b"\xff" * 4
            state, prev = afh.format_state("ikari", fields, prev)
            lines.append("F %d clka=%d clkb=%d clks=%d %s irqn=0 ymn=0 mid=000 all=%016x" % (n, n, n, n, state, prev))
        p = os.path.join(d, "v%d.hash" % variant)
        with open(p, "w") as f:
            f.write("\n".join(lines) + "\n")
        paths.append(p)
    msgs = []
    eq, diffs = compare_lines(paths[0], paths[1], out=msgs.append)
    ok = (not eq) and diffs["snd"] == [2] and all(not v for k, v in diffs.items() if k != "snd")
    eq2, _ = compare_lines(paths[0], paths[0], out=msgs.append)
    ok = ok and eq2
    print("compare selftest: %s" % ("ok" if ok else "FAILED\n" + "\n".join(msgs)))
    return ok


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 3
    cmd, rest = argv[1], argv[2:]
    if cmd == "selftest":
        return 0 if selftest() else 1
    opts, pos = {}, []
    multi = {"--skip-field": []}
    it = iter(rest)
    for a in it:
        if a in ("--no-timing",):
            opts[a] = True
        elif a in multi:
            multi[a].append(next(it))
        elif a.startswith("--"):
            opts[a] = next(it)
        else:
            pos.append(a)
    for p in pos[:2]:
        if not os.path.exists(p):
            print("missing: %s" % p)
            return 2
    if cmd == "lines" and len(pos) == 2:
        sf = {}
        for spec in multi["--skip-field"]:
            fld, _, fr = spec.partition(":")
            sf.setdefault(fld, set()).update(parse_frames(fr))
        eq, _ = compare_lines(pos[0], pos[1],
                              fields=opts["--fields"].split(",") if "--fields" in opts else None,
                              timing="--no-timing" not in opts,
                              frames=int(opts["--frames"]) if "--frames" in opts else None,
                              skip=parse_frames(opts.get("--skip-frames")), skip_fields=sf,
                              first=int(opts.get("--first", 0)))
        return 0 if eq else 1
    if cmd == "regs" and len(pos) == 3:
        return 0 if compare_regs(pos[0], pos[1], int(pos[2])) else 1
    if cmd == "dumps" and len(pos) == 2 and "--field" in opts:
        return 0 if compare_dumps(pos[0], pos[1], opts["--field"],
                                  int(opts["--frame"]) if "--frame" in opts else None) else 1
    if cmd == "acclog" and len(pos) == 2:
        return 0 if compare_acclog(pos[0], pos[1], int(opts.get("--context", 5)),
                                   int(opts["--cpu"]) if "--cpu" in opts else None) else 1
    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
