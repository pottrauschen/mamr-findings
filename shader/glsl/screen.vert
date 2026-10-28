// mamr_play (MAMR), BSD 3-Clause License, see LICENSE.
//
// One triangle that covers the whole target: vertices (-1,-1), (3,-1)
// and (-1,3) from the vertex index, no vertex buffer. The fragment
// shaders work from gl_FragCoord (window pixels, origin top left).
#version 450

void main() {
    const vec2 p = vec2(float((gl_VertexIndex << 1) & 2), float(gl_VertexIndex & 2));
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
