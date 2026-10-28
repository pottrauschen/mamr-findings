// See play_crt.h.
#include "play_crt.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace jf::play {

namespace {

// The profile Automat (docs/frontend.md section 12): an arcade RGB
// monitor of the Wells-Gardner K7000 class, 19 inch, P22 phosphors.
const CrtParam kArcade[] = {
    {"gamma_tube", 2.4, "", "DOC", "-",
     "ITU-R BT.1886 (2011) Annex 1: reference EOTF exponent of a CRT; the frame's values are the voltages"},
    {"gamma_out", 2.4, "", "CHOICE", "2.2-2.4",
     "the television assumed to decode BT.1886; equal to gamma_tube, so a flat area keeps its value"},
    {"bandwidth_mhz", 12.0, "MHz", "DATASHEET", "-",
     "Wells-Gardner K7000 service manual (1987): video amplifier 12 MHz at -3 dB; Gaussian response (CHOICE)"},
    {"beam_sigma", 0.20, "lines", "CHOICE", "0.15-0.30",
     "spot sigma at zero current; Gaussian form: Naiman & Makous 1992 (SPIE 1666); no width found for colour "
     "tubes (research 2026-10-27); MAME crt-geom spot 0.3 for comparison"},
    {"beam_growth", 0.25, "lines", "CHOICE", "0.15-0.35",
     "sigma increase at full current (spot grows with beam current, AAPM TG18); sigma at white 0.45 >= "
     "1/sqrt(2 pi) keeps a white line at or below full scale"},
    {"mask_pitch_mm", 0.82, "mm", "DATASHEET", "-", "Wells-Gardner K7000 service manual: stripe pitch 0.82 mm"},
    {"tube_width_mm", 365.0, "mm", "CHOICE", "340-390",
     "visible width of a 19 inch 4:3 tube (about 18 inch viewable), the picture filling it"},
    {"mask_gap", 0.15, "pitch", "CHOICE", "0-0.3", "dark part of each pitch between the stripes (own drawing)"},
    {"mask_strength", -1.0, "", "CHOICE", "0-1 or -1",
     "-1: mask_strength_fine below mask_fine_px window pixels per triad, else mask_strength_coarse"},
    {"mask_strength_fine", 0.15, "", "CHOICE", "0-0.3",
     "1080p: a triad is about 3 window pixels, on the television's own subpixel grid; a strong mask gives "
     "colour fringes and moire (research 2026-10-27: believable from 4K)"},
    {"mask_strength_coarse", 0.5, "", "CHOICE", "0.3-1", "4K: 6 to 7 window pixels per triad"},
    {"mask_fine_px", 5.0, "px", "CHOICE", "4-6", "the pitch below which the fine strength applies"},
    {"lowpass", 1, "on/off", "CHOICE", "0, 1", "stage switch: the amplifier's bandwidth (step 1)"},
    {"beam", 1, "on/off", "CHOICE", "0, 1", "stage switch: the spot profile across the lines (step 3)"},
    {"mask", 1, "on/off", "CHOICE", "0, 1", "stage switch: the phosphor stripes (steps 4 and 5)"},
};

// sigma of a Gaussian impulse response whose -3 dB point is at frequency
// 1: |H(f)| = exp(-2 pi^2 sigma^2 f^2) = 10^(-3/20).
const double kSigmaAt3dB = std::sqrt(std::log(std::pow(10.0, 3.0 / 20.0)) / (2.0 * 3.14159265358979 * 3.14159265358979)); // 0.13228

} // namespace

double CrtProfile::get(const char* key) const {
    for (const CrtParam& p : params)
        if (std::string(p.key) == key) return p.value;
    std::fprintf(stderr, "mamr_play: crt profile %s has no %s\n", name.c_str(), key);
    std::abort();
}

bool CrtProfile::set(const std::string& assignment, std::string* error) {
    const size_t eq = assignment.find('=');
    const std::string key = assignment.substr(0, eq);
    const std::string value = eq == std::string::npos ? "" : assignment.substr(eq + 1);
    char* end = nullptr;
    const double v = std::strtod(value.c_str(), &end);
    if (eq == std::string::npos || value.empty() || !end || *end) {
        if (error) *error = "--crt-param " + assignment + ": key=number";
        return false;
    }
    for (CrtParam& p : params)
        if (key == p.key) {
            p.value = v;
            return true;
        }
    if (error) *error = "--crt-param: profile " + name + " has no " + key + " (--crt-list shows the table)";
    return false;
}

std::string CrtProfile::describe() const {
    std::string s = "crt profile " + name + ":\n";
    char buf[96];
    for (const CrtParam& p : params) {
        std::snprintf(buf, sizeof(buf), "  %-21s %8g %-6s %-9s %-10s ", p.key, p.value, p.unit, p.cls, p.range);
        s += buf;
        s += p.source;
        s += "\n";
    }
    return s;
}

bool crt_profile(const std::string& name, CrtProfile* out) {
    if (name != "arcade") return false;
    out->name = name;
    out->params.assign(std::begin(kArcade), std::end(kArcade));
    return true;
}

CrtRaster crt_raster(const jf::machine::Description& d) {
    CrtRaster r;
    if (d.id == "ikari") {
        // 60 Hz (MAME snk.cpp set_refresh_hz) x 264 lines x 384 pixels per
        // line, 288 of them visible: MAME gives no raw timing, the lines
        // and the line length are the usual 15.8 kHz raster.
        r.pixel_rate_hz = 60.0 * 264 * 384;
        r.rotated = true;
        r.cls = "CHOICE";
        r.source = "60 Hz x 264 lines x 384 pixels (MAME snk.cpp: 60 Hz, no raw timing); ROT270 (DOC)";
    } else if (d.id == "rtype") {
        r.pixel_rate_hz = 8.0e6;
        r.cls = "DOC";
        r.source = "MAME m72.cpp set_raw(MASTER_CLOCK/4, 512, ..., 284): 8 MHz (docs/rtype-hardware-spec.md)";
    } else if (d.id == "spang") {
        r.pixel_rate_hz = 15164.52 * 512;
        r.cls = "DOC/CHOICE";
        r.source = "line rate 15.16452 kHz (PCB note, MAME mitchell.cpp:68) x 512 pixels per line (CHOICE)";
    } else if (d.system == "snes" || d.system == "nes") {
        const bool pal = d.region == "pal";
        r.pixel_rate_hz = pal ? (d.system == "snes" ? 21281370.0 / 4 : 26601712.0 / 5) : 21477272.0 / 4;
        r.cls = "DOC";
        r.source = pal ? "PAL master clock / dot length" : "NTSC master clock 21.477 MHz / 4";
    } else {
        r.source = "unknown machine: 6 MHz assumed";
    }
    return r;
}

CrtMaskTile crt_mask_tile(const CrtProfile& p, double line_extent_px) {
    CrtMaskTile t;
    const double triads = p.get("tube_width_mm") / p.get("mask_pitch_mm");
    t.period_px = line_extent_px / triads;
    const int n = std::max(3, static_cast<int>(std::lround(t.period_px)));
    t.length = n;
    t.rgba.assign(static_cast<size_t>(n) * 4, 0);
    // Stripe c (R, G, B) covers [c/3 + g/6, (c+1)/3 - g/6) of the pitch;
    // texel i covers [i/n, (i+1)/n): the texel's value is the overlap.
    const double g = std::clamp(p.get("mask_gap"), 0.0, 0.9);
    double sum[3] = {0, 0, 0};
    for (int i = 0; i < n; ++i) {
        const double a = static_cast<double>(i) / n, b = static_cast<double>(i + 1) / n;
        for (int c = 0; c < 3; ++c) {
            const double s0 = c / 3.0 + g / 6.0, s1 = (c + 1) / 3.0 - g / 6.0;
            const double cover = std::max(0.0, std::min(b, s1) - std::max(a, s0)) * n;
            const int v = static_cast<int>(std::lround(std::clamp(cover, 0.0, 1.0) * 255.0));
            t.rgba[static_cast<size_t>(i) * 4 + static_cast<size_t>(c)] = static_cast<std::uint8_t>(v);
            sum[c] += v / 255.0;
        }
        t.rgba[static_cast<size_t>(i) * 4 + 3] = 255;
    }
    // Mean and largest ratio from the stored (rounded) texels, so the
    // shader's normalization is exact for what it reads.
    for (int c = 0; c < 3; ++c) t.mean[c] = static_cast<float>(sum[c] / n);
    for (int i = 0; i < n; ++i)
        for (int c = 0; c < 3; ++c)
            if (t.mean[c] > 0)
                t.max_ratio = std::max(t.max_ratio, static_cast<float>(t.rgba[static_cast<size_t>(i) * 4 +
                                                                              static_cast<size_t>(c)] /
                                                                      255.0 / t.mean[c]));
    return t;
}

void crt_uniforms(const CrtProfile& p, const CrtRaster& r, double x, double y, double w, double h, unsigned fw,
                  unsigned fh, double par, double d_par, const CrtMaskTile& tile, CrtUniforms* u) {
    *u = CrtUniforms{};
    u->dst[0] = static_cast<float>(x);
    u->dst[1] = static_cast<float>(y);
    u->dst[2] = static_cast<float>(w);
    u->dst[3] = static_cast<float>(h);
    u->src[0] = static_cast<float>(fw);
    u->src[1] = static_cast<float>(fh);
    u->src[2] = r.rotated ? 1.0f : 0.0f;
    // Along the scanline: the amplifier's sigma in source pixels (a frame
    // with narrower pixels than the machine's nominal, SNES hi-res, has
    // the higher pixel rate). Three taps reach 0.33 source pixels. The
    // window pixel is sampled at its centre: a box of its width would act
    // on the voltages here, where the power law turns every blur into
    // lost light, and the amplifier's own sigma already spans 0.25 to
    // 0.35 window pixels at 1080 lines.
    const double rate = r.pixel_rate_hz * (par > 0 ? d_par / par : 1.0);
    double sigma_h = kSigmaAt3dB * rate / (p.get("bandwidth_mhz") * 1e6);
    if (p.get("lowpass") == 0) sigma_h = 0;
    // Across the lines the window pixel's height is a box of the same
    // variance added to the spot's (linear light, so no light is lost).
    const double across_px = r.rotated ? w : h;
    const double q_across = (r.rotated ? fw : fh) / across_px; // source lines per window pixel
    u->signal[0] = static_cast<float>(std::min(sigma_h, 0.33));
    u->signal[1] = static_cast<float>(p.get("gamma_tube"));
    u->signal[2] = static_cast<float>(1.0 / p.get("gamma_out"));
    u->beam[0] = static_cast<float>(p.get("beam_sigma"));
    u->beam[1] = static_cast<float>(p.get("beam_growth"));
    u->beam[2] = static_cast<float>(q_across * q_across / 12.0);
    u->beam[3] = p.get("beam") != 0 ? 1.0f : 0.0f;
    double strength = p.get("mask_strength");
    if (strength < 0)
        strength = tile.period_px < p.get("mask_fine_px") ? p.get("mask_strength_fine") : p.get("mask_strength_coarse");
    if (p.get("mask") == 0 || tile.max_ratio <= 1.0f) strength = 0;
    u->mask[0] = static_cast<float>(std::clamp(strength, 0.0, 1.0));
    u->mask[1] = static_cast<float>(tile.length);
    u->mask[2] = tile.max_ratio;
    for (int c = 0; c < 3; ++c) u->mask_mean[c] = tile.mean[c];
}

} // namespace jf::play
