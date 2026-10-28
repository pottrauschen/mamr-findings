# Tube shader (arcade profile)

A one-pass shader that draws an emulated frame as an arcade RGB monitor
of the Wells-Gardner K7000 class would show it, with every constant
tagged by its evidence class (DATASHEET, DOC, CHOICE) and source, as the
machine emulation tags hardware behaviour. It was written for MAMR's
front end from the research summarised in
[docs/crt-research-evaluation.md](../docs/crt-research-evaluation.md)
and [docs/scaler-firmware-reading.md](../docs/scaler-firmware-reading.md);
the full description, with measurements, is
[docs/frontend.md](../docs/frontend.md) section 12. crt-lottes (public
domain) and crt-beans (MIT) were read as examples of the chain; nothing
is taken from GPL shaders or firmware.

## Files

| Path | What |
|---|---|
| [glsl/crt.frag](glsl/crt.frag) | the tube: signal low-pass, power law, beam profile, mask, balance, output (formulas in its header comment) |
| [glsl/copy.frag](glsl/copy.frag) | the pass-through (nearest neighbour, the same bytes as an SDL renderer with nearest scaling) |
| [glsl/screen.vert](glsl/screen.vert) | full-screen triangle |
| [spirv/](spirv/) | SPIR-V of the three shaders as C arrays, generated with `glslangValidator -V --target-env vulkan1.0 --vn spirv_<name> -o spirv/<name>.h glsl/<file>`; regenerating them from the GLSL here gives the same bytes |
| [src/play_crt.h](src/play_crt.h), [src/play_crt.cpp](src/play_crt.cpp) | the profile table (constant, value, unit, class, range, source), the pixel rate and rotation per machine, the mask tile and the uniform block |
| [src/play_video.h](src/play_video.h), [src/play_video.cpp](src/play_video.cpp) | how MAMR's front end drives it on SDL 3's GPU API (Vulkan), with the SDL renderer as fallback |

The C++ sources are published for reading: they include
`runtime/machine/machine.h` of MAMR's unpublished source tree, from
which `play_crt.cpp` uses only `Description::id`, `system` and `region`
to pick the pixel rate, and `play_video.cpp` the machine's `Frame` (the
picture handed over each frame). The GLSL files stand alone.

## The chain, per window pixel

1. **Signal.** The frame's values are video voltages. Along the scanline
   each source pixel is a box one pixel time long, convolved with a
   Gaussian whose sigma follows from the amplifier's -3 dB bandwidth B and
   the pixel rate R (sigma_h = 0.1323 R / B source pixels), integrated in
   closed form with erf. The window pixel is sampled at its centre.
2. **Tube.** Voltage to light with the power law gamma_tube 2.4
   (ITU-R BT.1886); from here on linear light per gun.
3. **Beam.** Across the lines a Gaussian spot whose sigma grows with the
   gun's light L: sigma = beam_sigma + beam_growth * L lines, normalised
   to its area, so a line keeps its light whatever its width. The five
   nearest lines are summed.
4. **Mask.** Phosphor stripes as a small RGB tile, one texel per window
   pixel along the scanline, each channel divided by its tile mean so the
   mask neither darkens nor brightens on average.
5. **Balance.** Where the mask would push a channel above full scale its
   strength is lowered per channel until the brightest cell fits; the
   mask fades out towards white.
6. **Output.** Back to the display signal with 1/gamma_out.

Rotated monitors (Ikari Warriors): the frame's columns are the scanlines,
the mask runs along the window's vertical axis.

## Evidence

| Constant | Value | Class | Range | Source |
|---|---|---|---|---|
| gamma_tube | 2.4 | DOC | | ITU-R BT.1886 (2011) Annex 1, the reference EOTF of a CRT |
| gamma_out | 2.4 | CHOICE | 2.2-2.4 | a television decoding BT.1886 |
| bandwidth_mhz | 12 | DATASHEET | | Wells-Gardner K7000 service manual (1987), video amplifier at -3 dB; the Gaussian shape is a CHOICE |
| beam_sigma | 0.20 lines | CHOICE | 0.15-0.30 | spot at zero current; Gaussian form after Naiman and Makous 1992 (Proc. SPIE 1666); no width against brightness found for colour or arcade tubes |
| beam_growth | 0.25 lines | CHOICE | 0.15-0.35 | the spot grows with beam current (AAPM TG18, monochrome medical monitors) |
| mask_pitch_mm | 0.82 mm | DATASHEET | | K7000 service manual, stripe pitch |
| tube_width_mm | 365 mm | CHOICE | 340-390 | visible width of a 19 inch 4:3 tube |
| mask_gap | 0.15 pitch | CHOICE | 0-0.3 | own drawing |
| mask_strength | 0.15 / 0.5 | CHOICE | 0-1 | below / above 5 window pixels per triad |

Pixel rates per machine (Ikari Warriors 6.083 MHz, R-Type 8 MHz, Super
Pang 7.764 MHz, SNES and NES 5.37 MHz) with their classes and sources are
in [docs/frontend.md](../docs/frontend.md) section 12. At 12 MHz the
K7000's amplifier barely touches these boards (sigma_h 0.06 to 0.09
source pixels); the softness one sees is the beam's, across the lines.

## Using it elsewhere

The shader needs two textures and one uniform block (set 2: `frame_tex`
binding 0, `mask_tex` binding 1; set 3: the block `Crt`, laid out as
`struct CrtUniforms` in `play_crt.h`, std140 with vec4 members only).
`crt_mask_tile` and `crt_uniforms` in `play_crt.cpp` compute the tile and
the block from the profile, the pixel rate and the picture rectangle;
they depend on nothing but the C++ standard library apart from the
`Description` lookup in `crt_raster`.

Licence: BSD 3-Clause ([LICENSE](../LICENSE)).
