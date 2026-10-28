#!/usr/bin/env python3
"""Plausibility check of Super Pang sound (docs/spang-oracles.md section 9).

    audio.py compare A.wav B.wav [--window SECONDS] [--skip SECONDS]
        two recordings of the same route (MAME's -wavwrite, MAMR's
        spang_headless --wav) at any rates: the RMS level of each window
        (default one frame, 1/57.42 s), the correlation of the two level
        curves, their best lag in windows, the level ratio, and the windows
        where one side is silent and the other is not. Exit 0 when the
        curves correlate at 0.9 or more at a lag of at most one window.
    audio.py selftest

The samples themselves are not compared: the YM2413 instruments are the
placeholder on both sides, MAME resamples to 48 kHz with its own filter,
and MAMR holds the OKI samples (games/spang/spang_machine.h
machine_audio). Plain Python, no third-party modules.
"""
import array
import math
import os
import sys
import tempfile
import wave

FRAME_S = 1.0 / 57.42


def read_wav(path):
    """(rate, mono samples as floats in -1..1)."""
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("%s: 16-bit PCM expected" % path)
        ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
        a = array.array("h")
        a.frombytes(w.readframes(n))
    if sys.byteorder != "little":
        a.byteswap()
    if ch > 1:
        a = [sum(a[i:i + ch]) / ch for i in range(0, len(a), ch)]
    return rate, [x / 32768.0 for x in a]


def levels(rate, pcm, window, skip=0.0):
    out = []
    t = skip
    while True:
        i0, i1 = int(t * rate), int((t + window) * rate)
        if i1 > len(pcm):
            break
        seg = pcm[i0:i1]
        mean = sum(seg) / len(seg)
        out.append(math.sqrt(sum((x - mean) ** 2 for x in seg) / len(seg)))
        t += window
    return out


def correlation(a, b):
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def compare(pa, pb, window=FRAME_S, skip=0.0, out=print):
    ra, a = read_wav(pa)
    rb, b = read_wav(pb)
    out("A: %d Hz, %.2f s   B: %d Hz, %.2f s" % (ra, len(a) / ra, rb, len(b) / rb))
    la, lb = levels(ra, a, window, skip), levels(rb, b, window, skip)
    best = (-2.0, 0)
    for lag in range(-5, 6):
        c = correlation(la[max(lag, 0):], lb[max(-lag, 0):])
        if c > best[0]:
            best = (c, lag)
    c0 = correlation(la, lb)
    n = min(len(la), len(lb))
    sa, sb = sum(la[:n]), sum(lb[:n])
    ratio = sa / sb if sb else float("inf")
    quiet = 1e-4
    only_a = sum(1 for i in range(n) if la[i] > 10 * quiet and lb[i] < quiet)
    only_b = sum(1 for i in range(n) if lb[i] > 10 * quiet and la[i] < quiet)
    out("windows %d of %.2f ms; level correlation %.4f (lag 0), best %.4f at lag %+d" %
        (n, window * 1000, c0, best[0], best[1]))
    out("level ratio A/B %.3f; windows with sound on one side only: A %d, B %d" % (ratio, only_a, only_b))
    ok = best[0] >= 0.9 and abs(best[1]) <= 1
    out("result: %s" % ("PLAUSIBLE" if ok else "NOT PLAUSIBLE"))
    return ok


def write_wav(path, rate, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        a = array.array("h", (max(-32768, min(32767, int(round(x * 32767)))) for x in samples))
        if sys.byteorder != "little":
            a.byteswap()
        w.writeframes(a.tobytes())


def selftest():
    # the same bursts of a tone at two rates must correlate; a shifted
    # burst pattern must not at lag 0
    def burst(rate, offset):
        out = []
        for i in range(int(rate * 2.0)):
            t = i / rate
            on = int((t + offset) * 4) % 2 == 0
            out.append(0.5 * math.sin(2 * math.pi * 440 * t) if on else 0.0)
        return out
    with tempfile.TemporaryDirectory() as td:
        a, b, c = (os.path.join(td, x) for x in ("a.wav", "b.wav", "c.wav"))
        write_wav(a, 48000, burst(48000, 0.0))
        write_wav(b, 55556, burst(55556, 0.0))
        write_wav(c, 48000, burst(48000, 0.125))
        quiet = lambda s: None
        assert compare(a, b, out=quiet)
        assert not compare(a, c, out=quiet)
    print("audio selftest ok")
    return 0


def main(argv):
    if len(argv) >= 2 and argv[1] == "selftest":
        return selftest()
    if len(argv) < 4 or argv[1] != "compare":
        print(__doc__)
        return 3
    args = argv[2:]

    def opt(name, default):
        if name in args:
            i = args.index(name)
            v = args[i + 1]
            del args[i:i + 2]
            return float(v)
        return default
    window, skip = opt("--window", FRAME_S), opt("--skip", 0.0)
    if len(args) != 2:
        return 3
    for p in args:
        if not os.path.exists(p):
            print("missing: " + p)
            return 2
    return 0 if compare(args[0], args[1], window, skip) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
