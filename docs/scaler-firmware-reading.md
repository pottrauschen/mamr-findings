# Scaler firmware read: how the OSSC and MiSTer draw scanlines and masks

Sources, read on 2026-10-27:

- GitHub marqs85/ossc: `rtl/scanconverter.v` and
  `software/sys_controller/inc/avconfig.h` (GPL-3.0, state of
  2026-09-28).
- GitHub MiSTer-devel/Template_MiSTer: `sys/shadowmask.sv` (GPL-2.0,
  state of 2026-10-16).
- Licences checked through the GitHub API on 2026-10-27:
  marqs85/ossc_pro GPL-3.0, ramapcsx2/gbs-control GPL-3.0,
  MiSTer-devel/Main_MiSTer GPL-3.0; RetroTINK has no published source.

Only methods and parameters, in own words; all of it is GPL and nothing
is taken over. The RetroTINK is closed (documentation only: masks as BMP
of at most 16 x 16, profiles, energy normalization).

## MiSTer `shadowmask.sv` (136 lines)

- **Principle:** a tile of at most 16 x 16 cells is repeated over the
  output picture. Each cell holds an 11-bit value: three bits say per
  colour channel "on" or "off", plus two 4-bit intensities (on/off).
  Each channel is multiplied by its intensity (5-bit fixed point, values
  0 to 1 in sixteenths; "on" can amplify up to 1.9375; the result is
  clipped at 255).
- **Counters:** a column and a row counter run up to the tile's
  `hmax`/`vmax` and wrap; they are reset at the start of the picture
  (vsync, border), so the tile is bound to the screen, not to the source.
- **Options:** `2x` (every cell twice as large, counters halved),
  `rotate` (row and column index swapped, the mask stands vertical). No
  beam profile, no dependence on brightness, no gamma spaces: a plain
  multiplication in the output RGB.
- **For MAMR:** exactly what a fragment shader does with a tiny mask
  texture and `texture(mask, fragcoord mod size)`. The gain "on > 1" is
  the brightness compensation. Rotation is an index swap.

## OSSC `scanconverter.v` (647 lines) and `avconfig.h`

- **Pipeline:** line buffer, source selection, Y from RGB (R+2G+B, a
  coarse luma), **shadow mask** (3 clocks), **scanlines** (5 clocks),
  test pattern and mask overlay. The mask therefore sits *before* the
  scanlines.
- **Shadow mask:** a tile as in MiSTer (counters up to `SHMASK_IV_X/Y`,
  4 bits each, so at most 16 x 16), 11-bit cells with three channel bits
  and two intensities, a 5-bit multiplier, clipping at 255. The same data
  model; probably a common origin.
- **Scanlines, rows and columns:** a row counter runs up to `SL_IV_Y`
  (patterns of up to 6 lines), a column counter up to `SL_IV_X` (up to 10
  columns). Per position an overlay bit (draw the line or not) and a
  strength 0 to 15 (`SL_L_STR[6]`, `SL_C_STR[10]`). This allows line
  patterns at 2x to 6x and vertical "column scanlines" (`sl_type`:
  lines, columns; `sl_mode` off/auto/manual).
- **Strength:** `sl_str` 0 to 15 becomes the threshold
  `(str+1)*16-1`, i.e. 15 to 255. **Hybrid** (`sl_hybr_str` 0 to 28):
  the threshold is lowered by a brightness-dependent reference value
  formed from luma (or per channel) times hybrid strength times scanline
  strength; bright pixels thus get weaker scanlines, dark ones full ones.
  This is the OSSC's version of "scanline width depends on brightness",
  as a linear formula instead of a Gaussian.
- **Two methods:** `sl_method` 0 = subtraction (pixel minus strength,
  clipped at 0), 1 = multiplication (pixel times (255-strength)/256).
  Switchable; subtraction turns dark areas black sooner ("black crush"),
  multiplication keeps the ratios.
- **Bob alternation:** when deinterlacing, the scanline phase changes per
  field (`SL_BOB_ALTERN`), so that 480i bob does not flicker on a fixed
  line.
- **BFI:** black frame insertion as a special case of the same stage
  (the whole picture at a fixed strength, multiplication), its strength
  fixed at 0 in the code.
- **No** gamma linearisation, no low-pass in the scanline path (a video
  LPF sits in the sampler, `VIDEO_LPF_MAX 5`, which is analogue input
  filtering), no beam profile, no energy conservation of mask before
  scanline.

## What follows for MAMR

- Both devices confirm the research report (evaluated in
  [crt-research-evaluation.md](crt-research-evaluation.md)): hardware
  does **tile mask times scanline factor**, nothing else. Everything
  that looks "physical" (beam profile, linearisation, glow) exists only
  in software shaders.
- Two ideas are worth taking over in own form: (1) the 11-bit cell mask
  with an "on" gain above 1 as a cheap brightness compensation, (2) the
  OSSC hybrid formula as a comparison mode next to the Gaussian profile,
  because it shows how hardware users know "adaptive scanlines".
- The RetroTINK remains the only hardware with energy normalization and
  TVL profiles; there is no source for them, only RetroRGB's
  description.
