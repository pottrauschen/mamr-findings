# Tube look: evaluation of the research (2026-10-27)

Sources: this document evaluates three research reports on CRT shaders
and tube behaviour (a main report with 88 sources and two follow-up
reports on the same open questions, called A and B below; the reports
are not published), plus own checks of licences on 2026-10-27: the MAME
artwork masks (artwork/LICENSE, CC0 1.0), PAL-CRT by LMP88959 (README:
free use, credit requested but not required) and palgen-persune by
Persune (MIT-0).

## What is established and enough to build on

- **Chain** (consensus of all projects): linearise, signal low-pass,
  beam profile per line (Gaussian, width grows with brightness), mask at
  screen resolution, brightness compensation; optionally glow and
  curvature. Permissive examples: crt-lottes (public domain), crt-beans
  (MIT), the Blur Busters beam simulator (MIT), the MAME mask PNGs (CC0,
  checked), the Pally encoder/decoder (MIT-0), PAL-CRT (free, credit
  requested). GPL, read only: crt-guest, koko-aio, crt-royale, crt-geom,
  MAME's shaders.
- **Beam profile**: horizontally Gaussian in shape, qualitatively
  (Naiman & Makous 1992, Proc. SPIE 1666, DOI 10.1117/12.135955); the
  non-linearity acts along the line (superadditive between neighbouring
  pixels), not between lines; spot 0.1 to 0.2 mm, growing with beam
  current (AAPM TG18, monochrome medical monitors); the 5 percent
  diameter is about twice the 50 percent diameter. **No** half-width
  against brightness was found for colour television or arcade tubes, so
  width and growth stay CHOICE with a documented range (MAME crt-geom for
  comparison: spot_size 0.3, growth 0.1, power 3).
- **P22 afterglow**: contradictory (microseconds against milliseconds).
  Kuhn 2002 (IEEE S&P) measures both: a fast decay within one pixel time
  plus an afterglow over milliseconds; Sherr 1993 gives the decay to 10
  percent as R 1.5 / G 6.0 / B 4.8 ms (secondary citation). No
  manufacturer data sheet. Consequence: afterglow as an option with two
  time constants, values CHOICE.
- **Arcade**: Wells-Gardner K7000 (1987): 0.82 mm stripe pitch (19 and
  25 inch), 12 MHz at -3 dB, 560 x 240 resolvable, P22. No
  chassis-exact profile in MAME or MiSTer; the MAME documentation says
  there is "no one correct appearance". **Vertical monitors**: the
  MiSTer presets explicitly rotate scanlines and mask with the monitor
  (`maskmode=1x rotated`, filter axes swapped); MAME BGFX rotates the
  scanline axis through swap_xy. Consequence for Ikari: vertical
  scanlines, mask rotated with them.
- **PAL NES** (nesdev wiki "PAL video", 2C07): colour subcarrier
  4.43361875 MHz = master / 6, 5 master clocks per pixel, burst at 120
  degrees (not standard-conforming) = phase 7, the phase jumps by 60
  degrees per line, giving a 6-line pattern with no change per field
  (312 is divisible by 6: "dirty stills, OK movement", nesdev wiki),
  pixel aspect ratio about 1.386, black border (1 line, 2 pixels), hue
  -15 degrees against the 2C02 (burst at $x7), emphasis red/green
  swapped (test ROMs palblend/palphase). Televisions: a 64 microsecond
  delay line (TDA4510, 1986) averages the chroma with the previous line;
  cheap sets have none. **Open**: the absolute 2C07 DAC levels (NES-CVBS
  uses the 2C02's), the luma/chroma bandwidths of the televisions, the RF
  path. Tools: Pally `ppu_composite.py` (encoder from the 9-bit pixel,
  PAL phase table) plus a delay-line decoder; PAL-CRT (EMMIR) decodes
  6/9-bit NES pixels as a whole picture; NES-CVBS has a raster encoder,
  its decoder is empty.
- **Developer intent**: thin, and it stays thin. Established: an RGB
  monitor for drawing, a television for checking; Hoshi (HAL) and Sega's
  artists aimed at the home television; Shibuya (Square) said that what
  showed on the tube was all there was to his pixel art. Nintendo's
  monitor models, Irem's "Tetsujin", SNK's workstation: not found, not in
  Japanese primary sources either. Consequence: no further search; the
  target picture is "a home television, well adjusted", fine detail by
  eye.
- **Checking without a tube**: nobody compares shaders against
  calibrated photographs. Feasible for MAMR: NES colours against
  2C07_wiki.pal (Pally, from the signal model), the test pictures of the
  240p Test Suite (since 2026 with 288p/576i patterns), grey scale and
  gamma against the BT.1886 curve; beam shape and mask stay judgement by
  eye with a documented choice.

## Contradictions between the reports (decided)

- MAME mask PNGs: report A CC0, report B "not found". Decision: **CC0**
  (artwork/LICENSE checked locally). The crt-geom mask
  `aperture_1_2_bgr.png` lies outside artwork/ and is GPL like the
  shader: not used.
- Hue -15 degrees and the emphasis swap: A "not measured", B documents
  them through the wiki and test ROMs. Decision: take class
  **DOC/TEST-ROM**, -15 degrees as DOC.
- cgwg's second paper: A names Weibrecht et al. 1997 (DOI
  10.1117/12.273901), B considers it uncertain. Decision: list both as
  candidates; neither is needed for numbers.

## Consequences for MAMR (a basis for decisions, not a commitment)

Note: the arcade profile has been built since, on the GPU picture path
of item 1; see [frontend.md](frontend.md) section 12.

1. **Picture path**: move mamr_play to SDL's GPU API (Vulkan/SPIR-V,
   render passes); the SDL_Renderer cannot run shaders. Front-end work
   only, the emulation is untouched. Precondition for everything else.
2. **Three profiles, one program**: arcade (RGB, 12 MHz, 0.82 mm,
   scanlines and mask rotatable, 55/57.42/60 Hz), SNES PAL (BGR555 to
   the RGB SCART path, a 288-line raster with borders, 50 Hz), NES PAL
   (9-bit pixel to a composite encoder to a decoder with or without delay
   line to the tube). For the NES MAMR is true to the signal, which no
   RGB shader can be.
3. **Television limits**: 1080p is enough for scanlines and the beam
   profile; the mask becomes believable only at 4K; the beam simulator
   needs 120 Hz; 50/55/57 Hz on 60 Hz judders without VRR. The target
   television's data (resolution, refresh rate, VRR) decide which stages
   are built at all.
4. **Evidence classes** in the documentation as in the emulation:
   DATASHEET (K7000, TDA4510, the nesdev signal description), DOC (-15
   degrees, burst at 120 degrees), CHOICE (beam width, afterglow, mask
   strength), each with range and source.
