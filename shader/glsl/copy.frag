// mamr_play (MAMR), BSD 3-Clause License, see LICENSE.
//
// The pass-through: every window pixel inside the picture rectangle
// shows the frame pixel under its centre (nearest neighbour), every
// other one is black. This is what the renderer path does with
// SDL_SCALEMODE_NEAREST, and the two give the same bytes
// (a test of the unpublished front end).
//
// Where a centre falls exactly on the edge between two frame pixels
// (3.75 times: every other edge), single precision lands a hair below
// or above it. A sampler rounds the position to 1/256 of a texel before
// it takes the texel (Vulkan's subTexelPrecisionBits, 8 on the drivers
// tried); the shader does the same, so an edge goes to the right or
// lower pixel, as exact arithmetic has it.
#version 450

layout(set = 2, binding = 0) uniform sampler2D frame_tex;

// SDL GPU: fragment uniform buffers are set 3. The layout matches
// struct ScreenUniforms in play_video.cpp.
layout(set = 3, binding = 0, std140) uniform Screen {
    vec4 dst; // picture rectangle in window pixels: x, y, w, h
    vec4 src; // frame size in pixels: w, h, 0, 0
};

layout(location = 0) out vec4 out_color;

void main() {
    const vec2 p = gl_FragCoord.xy - dst.xy;
    if (p.x < 0.0 || p.y < 0.0 || p.x >= dst.z || p.y >= dst.w) {
        out_color = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    const ivec2 size = ivec2(src.xy);
    const vec2 q = floor(p / dst.zw * src.xy * 256.0 + 0.5) / 256.0;
    const ivec2 t = clamp(ivec2(floor(q)), ivec2(0), size - 1);
    out_color = vec4(texelFetch(frame_tex, t, 0).rgb, 1.0);
}
