// mamr_play (MAMR), BSD 3-Clause License, see LICENSE.
//
// The tube (docs/frontend.md section 12): one pass from the machine's
// frame to the window, written for MAMR. The chain, per window pixel:
//
//   1. signal   the frame's values are the video voltages. Along the
//               scanline the amplifier's bandwidth smears them: each
//               source pixel is a box (the DAC holds its value for one
//               pixel time) convolved with a Gaussian of sigma_h source
//               pixels (from the -3 dB bandwidth and the pixel rate,
//               play_crt.cpp), integrated in closed form with erf. The
//               window pixel is sampled at its centre.
//   2. tube     the voltage becomes beam current and light with the
//               tube's power law (gamma_tube): from here on linear light.
//   3. beam     across the scanlines each line is a Gaussian spot
//               profile, one per gun, whose width grows with that gun's
//               brightness: sigma = beam_sigma + beam_growth * L lines.
//               The profile is normalized to its area, so a line gives
//               the same light whatever its width (the beam's charge does
//               not change with the spot size): a dark line is thin with
//               dark gaps beside it, a bright one fills the gaps. The
//               five nearest lines are summed.
//   4. mask     the phosphor stripes: a small tile drawn on the CPU
//               (play_crt.cpp), repeated along the scanline in window
//               pixels; each channel's tile is divided by its mean, so
//               on average the mask neither darkens nor brightens.
//   5. balance  where the mask would push a channel above full scale, its
//               strength is reduced until it just fits: the mask fades
//               out towards white, and the light of every triad stays
//               what the beam gave.
//   6. output   back to the display's signal with 1 / gamma_out.
//
// Rotated monitors (Ikari Warriors): the scanlines run down the window
// (the frame's columns) and the stripes across it.
#version 450

layout(set = 2, binding = 0) uniform sampler2D frame_tex;
layout(set = 2, binding = 1) uniform sampler2D mask_tex;

// The layout matches struct CrtUniforms in play_crt.h.
layout(set = 3, binding = 0, std140) uniform Crt {
    vec4 dst;       // picture rectangle in window pixels: x, y, w, h
    vec4 src;       // frame size in pixels: w, h; z: 1 = rotated (lines are columns); w: unused
    vec4 signal;    // x: sigma_h in source pixels (0 = nearest), y: gamma_tube, z: 1 / gamma_out, w: unused
    vec4 beam;      // x: beam_sigma (lines), y: beam_growth (lines per unit light), z: window pixel
                    // variance across the lines (lines^2), w: 1 = beam profile on, 0 = flat lines
    vec4 mask;      // x: strength (0 = off), y: tile length in texels, z: largest tile / mean, w: unused
    vec4 mask_mean; // per channel mean of the tile
};

layout(location = 0) out vec4 out_color;

// erf, Abramowitz and Stegun 7.1.26 (absolute error below 1.5e-7).
float erf_as(float x) {
    const float t = 1.0 / (1.0 + 0.3275911 * abs(x));
    const float y = 1.0 - t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 +
                    t * (-1.453152027 + t * 1.061405429)))) * exp(-x * x);
    return x < 0.0 ? -y : y;
}

vec3 pixel(int along, int line) {
    const bool rot = src.z > 0.5;
    const ivec2 size = ivec2(src.xy);
    const ivec2 t = rot ? ivec2(line, along) : ivec2(along, line);
    if (t.x < 0 || t.y < 0 || t.x >= size.x || t.y >= size.y) return vec3(0.0); // blanking
    return texelFetch(frame_tex, t, 0).rgb;
}

// The amplifier's weights for the three source pixels a0 - 1, a0, a0 + 1
// around position a (source pixels along the line): the part of a
// Gaussian of sigma centred at a that falls on each pixel's box, from
// the erf at the four box edges. They depend on the position only, so
// they are computed once for all the lines.
vec3 lowpass_weights(float a, int a0, float sigma) {
    const float k = 0.70710678 / sigma;
    const float e0 = erf_as((float(a0 - 1) - a) * k), e1 = erf_as((float(a0) - a) * k);
    const float e2 = erf_as((float(a0 + 1) - a) * k), e3 = erf_as((float(a0 + 2) - a) * k);
    return 0.5 * vec3(e1 - e0, e2 - e1, e3 - e2);
}

// The signal of scanline `line` at the position the weights belong to.
vec3 line_signal(int a0, vec3 w, int line) {
    if (signal.x <= 0.0) return pixel(a0, line);
    return pixel(a0 - 1, line) * w.x + pixel(a0, line) * w.y + pixel(a0 + 1, line) * w.z;
}

void main() {
    const vec2 p = gl_FragCoord.xy - dst.xy;
    if (p.x < 0.0 || p.y < 0.0 || p.x >= dst.z || p.y >= dst.w) {
        out_color = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    const bool rot = src.z > 0.5;
    const vec2 s = p / dst.zw * src.xy;      // frame coordinates
    const float a = rot ? s.y : s.x;         // along the scanline
    const float l = rot ? s.x : s.y;         // across: the line coordinate
    // Without a stage's blur its axis is the pass-through's nearest
    // neighbour, rounded to 1/256 pixel as there (copy.frag).
    const float ar = floor(a * 256.0 + 0.5) / 256.0, lr = floor(l * 256.0 + 0.5) / 256.0;
    const int a0 = int(floor(signal.x > 0.0 ? a : ar));
    const int l0 = int(floor(beam.w > 0.5 ? l : lr));
    const vec3 w = signal.x > 0.0 ? lowpass_weights(a, a0, signal.x) : vec3(0.0, 1.0, 0.0);
    const float gamma_tube = signal.y;

    vec3 light;
    if (beam.w > 0.5) {
        light = vec3(0.0);
        for (int j = l0 - 2; j <= l0 + 2; ++j) {
            const vec3 lin = pow(max(line_signal(a0, w, j), vec3(0.0)), vec3(gamma_tube));
            const float d = l - (float(j) + 0.5);
            const vec3 sg = beam.x + beam.y * lin;
            const vec3 var = max(sg * sg + beam.z, vec3(1e-4)); // beam_sigma 0: no division by 0
            light += lin * exp(-0.5 * d * d / var) * inversesqrt(6.2831853 * var);
        }
    } else {
        light = pow(max(line_signal(a0, w, l0), vec3(0.0)), vec3(gamma_tube));
    }

    if (mask.x > 0.0) {
        const float along_px = rot ? p.y : p.x;
        const int n = int(mask.y);
        const int i = int(floor(along_px)) % n;
        const vec3 ratio = texelFetch(mask_tex, ivec2(i, 0), 0).rgb / mask_mean.rgb;
        // Largest strength per channel that keeps the brightest cell of
        // the tile at or below full scale.
        const vec3 fit = (1.0 / max(light, vec3(1e-6)) - 1.0) / (mask.z - 1.0);
        const vec3 k = clamp(min(vec3(mask.x), fit), 0.0, 1.0);
        light *= mix(vec3(1.0), ratio, k);
    }

    out_color = vec4(pow(clamp(light, 0.0, 1.0), vec3(signal.z)), 1.0);
}
