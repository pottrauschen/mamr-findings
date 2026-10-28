// The tube profiles of the GPU path (docs/frontend.md section 12): the
// constants of glsl/crt.frag with their evidence class and source,
// the raster of each machine (pixel rate, rotation), and the shader's
// uniforms and mask tile computed from them for one picture rectangle.
#pragma once
#include "runtime/machine/machine.h"

#include <cstdint>
#include <string>
#include <vector>

namespace jf::play {

// One constant: its key (for --crt-param key=value), value and unit, its
// evidence class as in the emulation (DATASHEET, DOC, CHOICE), the range
// a CHOICE may take, and where it comes from.
struct CrtParam {
    const char* key;
    double value;
    const char* unit;
    const char* cls;
    const char* range;
    const char* source;
};

struct CrtProfile {
    std::string name;
    std::vector<CrtParam> params;

    double get(const char* key) const;
    // key=value; false with a message for an unknown key or a value
    // that is no number.
    bool set(const std::string& assignment, std::string* error);
    // The table, one line per constant (--crt-list).
    std::string describe() const;
};

// "arcade" (the profile Automat: a Wells-Gardner K7000 class RGB
// monitor); false for an unknown name.
bool crt_profile(const std::string& name, CrtProfile* out);

// What the tube needs to know about the machine's picture: the pixel
// rate along a scanline (pixels of the frame's nominal width per second
// of active line time) and whether the monitor is rotated (the frame's
// columns are the scanlines). From the machine's identity
// (Description::id, system, region): the interface does not carry them.
struct CrtRaster {
    double pixel_rate_hz = 6.0e6;
    bool rotated = false;
    const char* cls = "CHOICE";
    const char* source = "";
};
CrtRaster crt_raster(const jf::machine::Description& d);

// The uniform block of glsl/crt.frag (std140: vec4 members only).
struct CrtUniforms {
    float dst[4];
    float src[4];
    float signal[4];
    float beam[4];
    float mask[4];
    float mask_mean[4];
};

// The mask tile: `length` texels of RGBA8 (R, G, B, 255) along the
// scanline direction, one per window pixel.
struct CrtMaskTile {
    int length = 0;
    std::vector<std::uint8_t> rgba;
    float mean[3] = {0, 0, 0};
    float max_ratio = 1;
    double period_px = 0; // the triad pitch in window pixels before rounding
};
CrtMaskTile crt_mask_tile(const CrtProfile& p, double line_extent_px);

// The uniforms for a frame of fw x fh pixels with pixel aspect `par`
// (the machine's nominal is d_par) drawn into the rectangle x, y, w, h.
void crt_uniforms(const CrtProfile& p, const CrtRaster& r, double x, double y, double w, double h, unsigned fw,
                  unsigned fh, double par, double d_par, const CrtMaskTile& tile, CrtUniforms* u);

} // namespace jf::play
