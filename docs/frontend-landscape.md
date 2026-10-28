# Frontend landscape: launchers, RetroArch's run loop, libretro, and a plan for MAMR

MAMR's games are native programs with the ROM data compiled in; there is
no emulator process and no ROM file at run time. What is still missing
between a finished game and a television is everything an emulator
frontend normally supplies: a menu to pick system and game, controller
handling, audio and video pacing, save states, and the return to the
menu. This document reads the three projects that solve those problems
best and derives a plan. Concept section 20 lists "Launcher" among the
things done later; this is the groundwork, not the start.

Sources read (clones outside the repository, commit and date in
brackets; nothing was built):

| project | licence | what we take |
|---|---|---|
| ES-DE, EmulationStation Desktop Edition (a529a9d, 2026-10-10) | MIT | launcher design: system and game lists, launching and return, input, 10-foot rules |
| EmulationStation by Alec Lofquist (9cc42ad, 2018) and the RetroPie fork (d9efd74, 2026-10-18) | MIT | the original, smaller design and its mapping dialog |
| RetroArch (7ae9257, 2026-10-24) | GPL-3 | run-time concepts only: rate control, pacing, states, SRAM, hotkeys, paths; no code |
| libretro-common, `include/libretro.h` (4ed412f, 2026-10-24) | MIT (header) | the core contract |

Rules: no code from RetroArch, ever; from EmulationStation and ES-DE
concepts, and code only if small, clearly better and marked with its
notice in `third_party/`; the libretro header may be vendored unchanged.
File references name the project's file and function with the line
numbers of the commit above, so that each claim can be checked in the
clone.

The five recommendations, in order:

1. **Build the common machine interface in libretro's shape** (frame,
   audio batch, input poll and state, serialize, memory map, timing,
   region); the SDL3 front end and the libretro adapter are then two
   thin consumers of one interface (sections 3.2, 4.1).
2. **Keep audio and video locked by dynamic rate control plus a pacing
   choice by refresh deviation**: ratio = nominal times `1 + 0.005 *
   direction`; vsync-locked when the content rate is within 5 percent
   of the display, otherwise a 50 Hz mode, VRR, or clock pacing with
   repeated frames. MAMR's `AudioOut` already has the formula (sections
   2.1 to 2.3, 4.1).
3. **Ship a libretro adapter early** (one file, one `.so` per game):
   RetroArch and ES-DE become the television front end at once, with
   menus, hotkeys, shaders and run-ahead for free and no code of theirs
   in MAMR (sections 3.8, 4.2).
4. **Make every MAMR binary launchable from ES-DE without libretro**:
   fullscreen by itself, exit code 0, quiet stdout, no lingering child
   holding stdout, a placeholder file per game, one custom system entry
   (section 5).
5. **Write an own launcher only if ES-DE falls short**, and then small:
   a carousel, a list with cover and description, a TOML manifest,
   `posix_spawn` and `waitpid`, SDL3 and a font rasteriser as the only
   dependencies (section 4.3).

## 1. What a launcher does: ES-DE and its ancestors

ES-DE (EmulationStation Desktop Edition, MIT, commit a529a9d of
2026-10-10) is the current descendant of Alec Lofquist's EmulationStation
(MIT, last commit 2018) by way of the RetroPie fork (MIT). All three share
one design: a list of systems, each with a directory of game files and a
command line template, a full-screen controller-driven menu, and a
blocking launch of an external emulator. Line numbers below refer to the
clone of each project; paths are relative to its root.

### 1.1 System list: es_systems.xml

One `<system>` element per system (ES-DE
`resources/systems/linux/es_systems.xml`, 2575 lines for about 200
systems):

```xml
<!-- abridged: the bundled entry lists ten commands and more extensions -->
<system>
    <name>snes</name>
    <fullname>Nintendo SNES (Super Nintendo)</fullname>
    <path>%ROMPATH%/snes</path>
    <extension>.sfc .SFC .smc .SMC .zip .ZIP</extension>
    <command label="Snes9x - Current">%EMULATOR_RETROARCH% -L %CORE_RETROARCH%/snes9x_libretro.so %ROM%</command>
    <command label="bsnes (Standalone)">%EMULATOR_BSNES% --fullscreen %ROM%</command>
    <platform>snes</platform>
    <theme>snes</theme>
</system>
```

Parsed by `SystemData::loadConfig` (`es-app/src/SystemData.cpp`
812-1180): `name`, `fullname`, `path`, `extension` and at least one
`command` are mandatory (1110-1120); `extension` is a whitespace list,
case-sensitive, each with its dot (1023); several `command` elements need
`label` attributes and the first is the default (1031-1053,
`FileData.cpp` 1055); `platform` serves only the scraper; `theme`
defaults to the name (1106). A system whose directory is missing or
holds no matching file is dropped from the menu (993-1008, 1160-1166).
The user's own file `~/ES-DE/custom_systems/es_systems.xml` is read
before the bundled one, and the first definition of a name wins
(`getConfigPath` 1324-1372, duplicate check 963-975), so a custom file
overrides single systems and adds new ones; `<loadExclusive/>` at its
root drops the bundled list altogether (860-895). The ROM root is
`~/ROMs/` unless the `ROMDirectory` setting says otherwise
(`FileData::getROMDirectory`, `es-app/src/FileData.cpp` 273-305); every
bundled system uses `%ROMPATH%/<name>`.

The placeholders are substituted in `FileData::launchGame`
(`FileData.cpp` 955-2396). The ones that matter outside RetroArch:
`%ROM%` (absolute path, shell-escaped with backslashes, 1955-1963 and
`FileSystemUtil.cpp` 480-502), `%ROMRAW%` (unescaped), `%BASENAME%`
(stem), `%FILENAME%`, `%ROMPATH%`, `%GAMEDIR%`, `%ESPATH%`,
`%EMULATOR_X%` (resolved through the find rules, 1334), `%STARTDIR%=dir`
(working directory of the child, created if missing, 1610-1711),
`%INJECT%=file` (splices up to 4096 bytes of a text file into the
command, 1713-1836), `%RUNINBACKGROUND%` (do not wait for the child,
1097-1109). The classic EmulationStation had only `%ROM%`, `%BASENAME%`
and `%ROM_RAW%`.

Emulators are located through `es_find_rules.xml` (`FindRules::
loadFindRules`, `SystemData.cpp` 44-215; `FileData::findEmulator`,
`FileData.cpp` 2398-2763): `systempath` rules search `$PATH`,
`staticpath` rules try fixed paths with `*` wildcards (AppImages in
`~/Applications`). Without an `%EMULATOR_` placeholder the first token
of the command is taken as the executable; an existing absolute path is
used as is, otherwise `$PATH` is searched ("method 2", 2707-2763). So a
custom system can name a binary by absolute path with no find rule.

### 1.2 Game list: gamelist.xml and folders

Games are the files in the system directory that match an extension
(`SystemData::populateFolder`, 613-760); the display name is the file
stem (`FileData.cpp` 19-31), or the MAME title for arcade systems. The
optional `~/ES-DE/gamelists/<system>/gamelist.xml` adds metadata per
`<game>` with a `<path>` relative to the system directory
(`GamelistFileParser.cpp` 234-242); fields and defaults are in
`MetaData.cpp` 23-49: `name`, `sortname`, `desc`, `rating`,
`releasedate`, `developer`, `publisher`, `genre`, `players`, `favorite`,
`completed`, `kidgame`, `hidden`, `broken`, `playcount`, `playtime`,
`lastplayed`, `altemulator`. Media are not listed; they are found by file
name under `~/ES-DE/downloaded_media/<system>/<type>/`. The file is
rewritten at every metadata save point by default (after each launch,
`FileData.cpp` 2394-2395; setting `SaveGamelistsMode`), and only changed
nodes are replaced (`updateGamelist` 383-597). Without a gamelist the
menu still works; entries whose file disappeared are skipped with a
warning. Subdirectories become folders in the list; a directory named
like a game file with the same-named file inside counts as one entry
(1069-1083).

Scraping (ScreenScraper and TheGamesDB, `es-app/src/scrapers/`) fills
the metadata and media directories; MAMR has a handful of games whose
artwork is copied by hand, so this is noted and not used.

### 1.3 Views and themes

ES-DE knows two views, `system` and `gamelist` (`ThemeData.cpp` 29-32),
and in each the theme picks exactly one primary element: `carousel`,
`grid` or `textlist` (`THEMES.md` 1699-1703; `SystemView.cpp` 575-600,
`GamelistView.cpp` 165-205). The classic "basic / detailed / video /
grid" gamelist views are gone; a detailed layout is a textlist plus
image, video, text and metadata elements placed by the theme. A theme is
a tree of `theme.xml` files with `<view>`, element and property nodes,
`<include>`, variants, colour schemes, aspect ratios (the list is
hard-coded, 16:9, 4:3, 3:2, 5:4, their vertical twins and more,
`ThemeData.cpp` 66-91) and a mandatory `capabilities.xml`. Positions and
sizes are normalised to 0..1 of the screen (`THEMES.md` 326-329). The
default theme is `linear-es-de`.

The classic EmulationStation and the RetroPie fork keep the four
gamelist views (basic, detailed, video, grid; `ViewController::
getGameListView` picks "detailed" as soon as one game has a picture)
and a system carousel of logos, which is the model most people picture:
a horizontal carousel of systems, press A, a text list of games with a
picture and description panel, press A to launch. The numbers behind
that look (Aloshi clone, `es-app/src/views/SystemView.cpp` 12-14,
258-330): logo cell 0.25 of the width by 0.155 of the height, the
selected logo scaled by 1.5 and drawn opaque, the others at half
opacity, a translucent band across the middle, indices wrapped so the
carousel is circular, the camera offset eased with `t*t*t + 1`. The
detailed view (`DetailedGameListView.cpp` 21-66) puts the list on the
right half, the picture centred in the left half at 0.4 of the height,
labelled metadata rows under it and a scrolling description from 0.65
of the height down. Held directions auto-repeat in tiers
(`es-core/src/components/IList.h` 37-48): 500 ms before the first
repeat, then one step per 114 ms for five seconds, then one per 8 ms.
Views are placed on a virtual plane and a camera slides between them
in 400 ms, or fades through black in 240 ms (`ViewController.cpp`
106-149).

### 1.4 Fonts, focus and other 10-foot-UI rules

- Font sizes are fractions of the shorter screen side
  (`es-core/src/resources/Font.h` 40-95): mini 0.030, small 0.035,
  medium 0.045, large 0.085; line spacing 1.5. At 1080p "medium" is
  about 49 px, "large" about 92 px, which reads from a sofa.
- The help bar at the bottom (`HelpComponent`, y = 0.9515 of the
  height) lists the buttons that do something in the current view, with
  icons drawn for the controller type the user chose (Xbox, PlayStation,
  Switch, SNES; `HelpComponent.cpp` 437-575). This is how the user learns
  the mapping without a manual.
- Exactly one component has focus: input goes to the top of the GUI
  stack only (`Window::input`), the list has one cursor. There is no
  mouse handling at all (no `SDL_MOUSEBUTTON` anywhere; the cursor is
  hidden at start, `Renderer.cpp` 70).
- Long names scroll horizontally inside the list
  (`TextListComponent.h` 216-226), descriptions scroll vertically.
- Fullscreen-desktop at native resolution by default; `--resolution`
  switches to a window; `--screenrotate 0|90|180|270` for vertical
  screens; `--fullscreen-padding` for displays that cut the edges;
  VSync on with swap interval 1 (`RendererOpenGL.cpp` 390-407).
- UI modes `full`, `kiosk`, `kid` restrict menus for guests; the unlock
  sequence is the Konami code on the pad (`Settings.cpp` 383).

### 1.5 Input configuration

ES-DE uses the SDL2 game controller API: every joystick that
`SDL_IsGameController` recognises is opened, mappings come from SDL's
built-in database plus `~/ES-DE/controllers/es_controller_mappings.cfg`
(`InputManager.cpp` 58-122). The first-start mapping wizard of the
classic EmulationStation (`GuiDetectDevice`, `GuiInputConfig`) still
exists but runs only on request (`--force-input-config` or the menu);
by default a pad works at once with the logical set Up, Down, Left,
Right, A, B, X, Y, Start, Back, shoulders, triggers, stick directions
and stick clicks (`loadDefaultControllerConfig` 594-627). Keyboard
defaults: arrows, Return = A, Backspace = B, Delete = X, Insert = Y,
F1 = Back, Escape = Start, PageUp/PageDown = shoulders
(`loadDefaultKBConfig` 561-592). Deadzones: triggers 18000, sticks 23000
of 32767 (`InputManager.h` 69-70). Hot-plug is handled even while a game
runs (`PlatformUtil.cpp` 284-289). A `Swap A/B` setting exists for
Nintendo-layout pads (`InputConfig.cpp` 146-157). The stored form is
`~/ES-DE/settings/es_input.xml`: one `<inputConfig type deviceName
deviceGUID>` with `<input name type id value/>` children
(`InputConfig::writeToXML` 201-227).

The classic EmulationStation had no controller database and therefore
owned the problem. Its first-start dialog is still the cleanest design
for a mapping screen (Aloshi clone, `es-core/src/guis/
GuiDetectDevice.cpp` and `GuiInputConfig.cpp`):

1. "WELCOME. N GAMEPAD(S) DETECTED. HOLD A BUTTON ON YOUR DEVICE TO
   CONFIGURE IT." Any button or key held for 1000 ms picks the device;
   the device name fades while holding, releasing early cancels
   (`GuiDetectDevice.cpp` 12, 80-110). The keyboard is a device like
   any other, with id -1.
2. A list of logical inputs, each with an icon, the name and a status
   column that reads PRESS ANYTHING, then the assigned "BUTTON 3" or
   "AXIS 1-", or ALREADY TAKEN (`GuiInputConfig.cpp` 10-16, 229-247).
   Aloshi asked for ten: Up, Down, Left, Right, A, B, Start, Select,
   PageUp, PageDown; RetroPie for 25 including X, Y, shoulders,
   triggers, both sticks and HotKeyEnable, of which only the d-pad and
   A are mandatory.
3. An input is taken on release, not on press, from the device being
   configured only; a button already used for another row is refused;
   holding any input for 5 s (RetroPie: 1 s) skips an optional row with
   a countdown (85-133, 181-204, 253-273). Afterwards the user can move
   to a row and remap it alone; OK writes the file.
4. Raw SDL joystick events are reduced to digital inputs: an axis
   counts only when it crosses a dead zone of 23000 of 32767, hats and
   buttons as they are; a saved config is matched to a device by GUID
   first, then by name (`InputManager.cpp` 170-242, 244-271).

With SDL3's gamepad API and its mapping database the dialog is not
needed for the menu itself, but the same screen, reduced to the game's
buttons, is how a player would remap "fire" and "grenade" on a pad the
database does not know.

### 1.6 Launching a game and coming back

`ViewController::launch` (`es-app/src/views/ViewController.cpp`
1019-1088) shows a launch screen for 3 s by default, plays the launch
sound, blocks input, then calls `FileData::launchGame`, which builds the
command line and calls `Utils::Platform::launchGameUnix`
(`es-core/src/utils/PlatformUtil.cpp` 226-328). That function is the
whole contract:

- The command becomes `cd <startdir> && <command> 2>&1 &` and is run
  through `popen(..., "r")`, so `/bin/sh` parses it (231, 253-256).
- ES-DE then loops on `select()` over the pipe, reading the child's
  merged stdout and stderr into a 5 MiB buffer and draining SDL events,
  of which only controller add and remove are processed (272-290).
  Rendering stops; the ES-DE window stays open, full-screen, and is
  never minimised (`SDL_HINT_VIDEO_MINIMIZE_ON_FOCUS_LOSS` = 0,
  `Renderer.cpp` 195). One black frame is swapped before the launch
  (`FileData.cpp` 2168-2172). The audio device is paused, not closed
  (`AudioManager::stop`).
- The loop ends at end-of-file on the pipe, which happens when the last
  process holding the inherited stdout exits. `pclose() >> 8` is taken
  as the return code (292-295). Because the shell put the command in
  the background with `&`, the shell itself exits immediately with 0,
  and that is the status `pclose` reports; the game's own exit code is
  lost on Linux. (Reading of the source; the ES-DE author's own comment
  at 233-235 calls the background path "very crude". Verify on a real
  installation before relying on an error popup.) A non-zero code would show
  `ERROR LAUNCHING GAME '<name>' (ERROR CODE n)` for 6 s and log the
  captured output (`FileData.cpp` 2317-2325).
- On return: play count and last-played are updated, the gamelist is
  written, the launch screen closes, and input is unblocked one frame
  later "so that any keys or button presses used for exiting the
  emulator are not captured" (`ViewController.cpp` 1083-1086). ES-DE
  does not rescan the directory.
- ES-DE never passes a fullscreen flag by itself and never signals or
  kills the child; the user guide tells users to enable fullscreen in
  each emulator (`USERGUIDE.md` 1174-1178). Only a build with
  `DEINIT_ON_LAUNCH` closes the window and the audio device around the
  launch, for KMS and framebuffer emulators.

The classic EmulationStation did the same more bluntly
(`es-app/src/SystemData.cpp` `SystemData::launchGame` 107-147):
`AudioManager::deinit()` (the comment: "else SDL hogs audio resources
and emulators might fail to start"), `window->deinit()` (joysticks
closed, textures freed, SDL window and GL context destroyed), then a
blocking `system(command)`, then `window->init()` and
`normalizeNextUpdate()` so the first frame after the return does not
see a delta of minutes. A non-zero exit code was only logged. RetroPie
kept this and put its `runcommand.sh` between the two, as the command
in `es_systems.cfg`, to choose the emulator and the video mode; the
script is not part of the EmulationStation sources. RetroPie also
restarts itself through a wrapper script that watches marker files in
`/tmp` (`emulationstation.sh`).

### 1.7 Hotkeys inside the launcher

Start opens the main menu; A selects or launches; B goes back; X opens
the media viewer; Y toggles favourite; a stick click picks a random
game; Back (Select) opens the gamelist options (`GamelistBase.cpp`
71-269, `ViewController.cpp` 1273-1301). Quit is a menu entry; F4,
Ctrl+Q or Alt+Q optionally quit from the keyboard, Alt+F4 is left to the
window manager (`InputManager.cpp` 394-428). There is no controller
combination that quits ES-DE and no "exit emulator" hotkey: leaving the
game is the emulator's business (RetroArch's own hotkey, section 2.8).
The classic version quit on F4 from anywhere and asked "REALLY QUIT?"
from the menu; RetroPie's mapping dialog tells the user that the
HotKeyEnable button "IS REQUIRED FOR EXITING GAMES WITH A CONTROLLER",
which is the emulator's hotkey, configured downstream, not ES's.

### 1.8 Audio in the menu

`AudioManager` opens one SDL2 device at 44100 Hz, float, stereo, 1024
samples, callback-driven (`AudioManager.cpp` 71-83). The callback zeroes
the buffer, mixes the playing navigation sounds with
`SDL_MixAudioFormat`, then pulls video-preview audio from an
`SDL_AudioStream` (152-234). Seven theme sounds: systembrowse,
quicksysselect, select, back, scroll, favorite, launch (`Sound.cpp`
192-215). The device is paused whenever nothing plays and when a game
starts, so the emulator gets the hardware.

### 1.9 Screensaver

Types dim (brightness to 0.4), black, slideshow and video, default
video, after 5 minutes (`Screensaver.cpp` 62-66, 363-379;
`Settings.cpp` 200-201). Any input cancels; in the video and slideshow
modes left and right skip to another game, A launches the game shown,
Y jumps to it in the list (`Window.cpp` 290-335). It never starts while
a game runs.

### 1.10 Command line and files of ES-DE itself

`es-de --display N --resolution W H --screenrotate R --vsync 0|1
--no-splash --gamelist-only --ignore-gamelist --force-kiosk
--force-input-config --home PATH --debug` (`main.cpp` 406-435). Data
lives under `~/ES-DE/`: `settings/es_settings.xml`,
`settings/es_input.xml`, `custom_systems/`, `gamelists/`,
`downloaded_media/`, `themes/`, `controllers/`, `logs/es_log.txt`.

### 1.11 What of this MAMR needs

MAMR has three systems, at most a dozen games, no ROM files at run time
and one user. Needed, in some form:

| part | needed | why |
|---|---|---|
| system list and game list from a file | yes | three systems, each with its own binary; a manifest replaces the directory scan |
| placeholder substitution in a command template | yes, minimal | one binary per game, a few flags |
| blocking launch, window stays, input re-armed on return | yes | the core of the loop; ES-DE's one-frame input block after return is worth copying |
| controller detection via the SDL gamepad database | yes | SDL3 does this for free; no mapping wizard needed |
| help bar with button icons | yes | the only way to make the mapping discoverable from the sofa |
| font sizes as a fraction of the screen, one focus, no mouse | yes | 10-foot rules |
| gamelist.xml metadata, scraping, media download | no | hand-placed artwork per game is enough; a `cover` path in the manifest |
| themes, variants, colour schemes, aspect-ratio sets | no | one layout, drawn in code |
| folders, collections, favourites, kiosk and kid modes | no | not enough games |
| find rules | no | the manifest names the binary |
| screensaver | later | dim after N minutes is twenty lines; video attract modes are the games' own |
| navigation sounds | optional | pleasant, cheap, not required |

## 2. What RetroArch gets right at run time

RetroArch is GPL-3; this section takes concepts, formulas and defaults
and names the file and function where each lives (clone of commit
7ae9257, 2026-10-24), so that a reader can check the idea against the
source without any of it entering MAMR. Line numbers refer to that
commit. The checkout is far ahead of the releases most write-ups
describe; where a mechanism is a recent refinement on top of the
classic design it is marked "(newer)".

### 2.1 Dynamic rate control

The core produces audio at its own rate; the sound card consumes at its
own; the display paces the loop. Without correction one of the two
buffers drifts until a sample is dropped or repeated. RetroArch instead
nudges the resampling ratio by a fraction of a percent, inaudible as
pitch, so that the output buffer stays half full
(`audio/audio_driver.c`, `audio_driver_compute_rate_adjust`, lines
1497-1596; `audio_driver_init_internal`, 4908-4911):

```text
ratio_orig  = out_rate / in_rate                 (device rate over core rate)
avail       = free space in the device buffer, clamped to buffer_size
direction   = (avail - buffer_size/2) / (buffer_size/2)     in [-1, +1]
adjust      = 1 + delta * direction
ratio       = ratio_orig * adjust
```

with `delta` = `audio_rate_control_delta`, default 0.005
(`config.def.h` 1490; menu range 0 to 0.020). An emptier buffer
(positive direction) raises the ratio and produces more output samples
per input sample; a fuller one lowers it. The controller is purely
proportional and the excursion is bounded to plus or minus `delta`
around nominal. Newer refinements: `delta` is divided by `ratio_orig`
when that is above 1 to keep the loop gain constant at high output
rates (1577-1585); the adjustment is recomputed once per video frame
rather than per batch, so the fill level is measured at the same point
of each frame (`audio_driver_update_drc_threshold`, 2116-2132); a
direction below zero is forced to zero while a blocking write is what
paces the loop, because a full buffer held by the writer is not a rate
error (1553-1576); and a slow integral term estimates the crystal
offset between host and sound card in ppm (1492-1495). The first
formula is what MAMR already has in `runtime/snes/snes_audio_out.h`,
written as `step = in/out * (1 + d * (2 * fill/capacity - 1))` from the
producer's side, same `d` = 0.005.

**Timing skew.** Before the ratio is formed, the core's sample rate is
retargeted so that one core frame of audio lasts exactly one display
frame, provided the two rates are close
(`retroarch.c`, `audio_driver_monitor_adjust_system_rates`, 1504-1532):

```text
target = refresh;  if round(refresh / fps) > 1: target /= (bfi + 1) * swap_interval * subframes
skew   = |1 - fps / target|
if skew <= audio_max_timing_skew:  in_rate' = in_rate * target / fps   else unchanged
```

`audio_max_timing_skew` defaults to 0.05 (`config.def.h` 1494); its menu
text describes it as the largest allowed change of the audio input rate,
where a larger value permits big timing changes at the price of a wrong
pitch, with PAL cores on NTSC displays as the example. For a 60.0985 Hz SNES on a
60 Hz display the skew is 0.16 percent: the core runs locked to the
display, the audio is 0.16 percent slow, and rate control absorbs the
rest. For a 55.0176 Hz R-Type on 60 Hz the skew is 8.3 percent, outside
the limit, and section 2.3 applies.

### 2.2 Frame pacing and vsync strategies

The decision of what holds the loop is made once per iteration from a
set of facts (`runloop.c`, the limiter block at the end of
`runloop_iterate`, 10230-10400; `runloop.h`, `runloop_pace_sources`,
826-872; `runloop_sync_plan_for`, 705-733):

- **Vsync holds** (`video_vsync` default on, `config.def.h` 413): the
  swap blocks, the loop never sleeps, rate control absorbs the drift.
  This is the normal case whenever the core's rate is at or below the
  display's.
- **Audio holds**: with `audio_sync` on, a full device buffer makes the
  write block, and that blocking write becomes the pace source. This is
  what keeps a core slower than the display honest (section 2.3).
- **A timer holds** when neither can: fast-forward, pause, VRR mode, or
  the "gap limiter" (newer) that runs the loop at the display period
  when vsync is off but rate control is on (`runloop_pace_gap_engages`,
  552-558). The timer is a nanosecond schedule anchored on the previous
  due time (`runloop_pace_schedule`, 583-601): sleep until `due -
  margin`, spin the rest; if a frame is late by less than a period, no
  sleep and catch up next time; if later than that, re-anchor to now
  and do not chase. The margin tracks observed oversleep, at least 2 ms,
  at most a quarter period (604-631). `ikari_sdl.cpp` 262-266 is the
  same idea with a 10-frame re-anchor and no spin.
- **Core faster than the display** (a 60 Hz core on a 50 Hz TV): the
  plan lacks `VSYNC_HOLDS`, vsync is switched to non-blocking with the
  log line "Game FPS > Monitor FPS. Cannot rely on VSync." and audio
  paces (`retroarch.c` 1678-1698).
- **VRR mode** (`vrr_runloop_enable`, default off, `config.def.h`
  1772; menu text "Sync to Exact Content Framerate (G-Sync, FreeSync):
  No deviation from core requested timing"): audio is not retargeted,
  swap interval is forced to 1, the timer paces at exactly the core's
  rate and the variable-refresh display follows (`runloop.c`
  10164-10198). On a VRR television this is the right mode for all
  three MAMR machines.
- **Swap interval** (`video_swap_interval` default 1, 0 = auto): auto
  picks `n = round(refresh / fps)` when `fps` is within the skew of
  `refresh / n` (`runloop.h` 654-679), so 30 Hz content on 60 Hz
  presents every second refresh instead of leaning on rate control.
- **Frame delay** (`video_frame_delay`, default 0, max 99;
  `gfx/video_driver.c`, `video_frame_delay`, 10203-10350): after the
  swap returns, sleep N ms before running the core so that input is
  sampled as late as possible; values of 20 and above mean percent of
  the frame. The automatic variant targets three quarters of the frame,
  raises the delay by 1 ms when frames land near target, and drops it by
  1 to 3 ms when an 8-frame average exceeds 1.25, 1.5 or 1.75 times the
  target (9865-10200). Menu text: "Reduces latency at the cost of a
  higher risk of video stuttering."
- **Hard GPU sync** (`video_hard_sync`, frames 0 to 3): a GL fence per
  frame, wait when more than N are outstanding (`gfx/drivers/gl2.c`
  3143-3160); **swapchain depth** `video_max_swapchain_images` default
  3, range 2 to 4; **adaptive vsync** maps to `EXT_swap_control_tear`;
  **black frame insertion** and **shader subframes** multiply the
  presents per content frame and divide the effective refresh in the
  formulas above. One sentence each because MAMR's renderer is SDL's.

### 2.3 50 Hz content on a 60 Hz display

The case of the PAL Zelda. By default (vsync on, 60 Hz display, core at
50.007 Hz): auto swap interval gives 1; the skew is 16.7 percent, so the
log says "Timings deviate too much. Will not adjust." (`retroarch.c`
1647-1650) and the audio is not retargeted; vsync stays blocking, so the
swap alone would run the core at 60 fps, 20 percent fast. What prevents
that is the audio: the core produces 1/50 s of sound per frame, the
device drains 1/60 s per display frame, the buffer fills, the write
blocks, and the blocking write paces the core at 50 fps. The display
shows 50 unique frames on a 60 Hz cadence: one repeated frame every
fifth, which is the judder PAL players know. With `audio_sync` off the
game simply runs 20 percent fast. Raising the skew limit to 0.17 makes
the core run at 60 Hz with audio 20 percent fast and a fifth higher,
the "PAL cores on NTSC displays" case of the menu text. The clean
answers are a 50 Hz display mode (RetroArch's CRT SwitchRes does this
for CRTs, `crt_switch_resolution`; on a modern TV the frontend sets the
mode) or a VRR display in VRR mode. RetroArch also estimates the real
refresh from 2048 swap intervals (`gfx/video_driver.c`,
`video_monitor_fps_statistics`, 4516-4560: mean and standard deviation
of the interval) and lets the user adopt the estimate as
`video_refresh_rate`, because 59.94 and 60.00 differ by more than rate
control alone would like to carry forever.

For MAMR this means: pass the exact content rate to the display layer,
measure the display, and choose between vsync-locked (within 5 percent),
a 50 Hz mode when the TV offers one, VRR, or clock-paced with repeated
frames. R-Type at 55 Hz has no matching TV mode and will always be
clock-paced on a fixed-rate display; on VRR it is exact.

### 2.4 Audio latency and buffer sizes

`audio_latency` defaults to 64 ms (`config.def.h` 1440; 128 on Android),
with a floor of 8 ms, range 0 to 512. The SDL2 driver
(`audio/drivers/sdl2_audio.c` 53-59, 664-668, 745-770) asks SDL for a
device buffer of one quarter of the latency, rounded down to a power of
two and at least 64 frames, and keeps its own ring of the full latency
in front of it, at least twice the device buffer; the ring is what
`buffer_size` reports, and half of it is the rate-control set point, so
the steady-state latency is about half the configured value. Output
rate 48000 by default. Underruns are the driver's business: the callback
fills silence and counts. The frontend keeps the last 8192 fill
readings and shows statistics (`audio_compute_buffer_statistics`,
9900-9966): saturation `1 - mean(free) / size`, its standard deviation,
and the percentages of readings with more than three quarters free
(close to underrun) or less than a quarter free (close to blocking). A
healthy stream sits at 50 percent with a small deviation. MAMR's
`AudioOut` exposes `fill()`, `underruns()` and `last_step()`; the same
four numbers on a debug overlay would show at a glance whether pacing
is right. Resampler: windowed sinc with quality levels; the ratio
passed per batch is the actuator.

### 2.5 Save-state slots and autosave

(`runloop.c` `runloop_get_savestate_path` 10562-10584; `command.c`
6279-6720; `tasks/task_save.c`.)

- Slot `state_slot` from -1 to 999. File names: slot -1 is
  `<name>.state.auto`, slot 0 `<name>.state`, slot N `<name>.stateN`;
  a thumbnail is `<state>.png` next to it (`savestate_thumbnail_enable`
  on by default on desktop). States live under
  `<states dir>/<core name>/` by default (`sort_savestates_enable`).
- `savestate_auto_save` (default off): on content close write
  `.state.auto`; `savestate_auto_load` (default off): load it at start.
  The menu text says the same: a state is made when content closes and
  loaded at start when "Auto Load" is on.
- `savestate_auto_index` (default off): before a save, increment the
  slot; at load, set the slot to the highest existing index;
  `savestate_max_keep` deletes the oldest beyond N.
- Undo, one deep (`task_save.c` 98-110, 1014-1090, 231-395): before a
  save overwrites a file its old contents go to a buffer, before a load
  the current state is serialised to another; "undo save" and "undo
  load" restore them. Cheap, and it removes the fear of the wrong slot.
- The file is a small container ("RASTATE", tagged blocks for the core
  blob, achievements and replay data), compressed by default
  (`savestate_file_compression` on desktop), written in 100 KiB chunks
  under a 2 ms per-tick budget so the save never stalls a frame, to a
  temporary name and renamed.
- Contract detail worth copying: `retro_serialize_size` 0 blocks a save
  but a load is still attempted, because a core may be able to restore
  where it cannot currently serialise (`task_save.c` 2209-2215).
- Rewind (`state_manager.c`) keeps reverse deltas in a 20 MiB ring,
  comparing 16-bit words and storing only changed runs, pushed every
  `rewind_granularity` frames; off by default. Mentioned for
  completeness; MAMR's machines are small enough that full states per
  frame would also do.

### 2.6 SRAM write intervals

Save RAM goes to `<saves dir>/<core name>/<content>.srm`. It is written
on core unload and on quit (`save.c`, `event_save_files` 608-625,
`content_save_ram_file` 520-600): the file is compared with memory
first and the write skipped when identical, otherwise written to a
temporary file and renamed. `autosave_interval` (default 0 = off on
desktop, 10 s on some consoles, `config.def.h` 1620-1623) starts a
thread per memory region (`autosave_thread`, `save.c` 97-172) that
takes a snapshot of the region at a safe point, compares it with the
last written copy by `memcmp`, writes only on change, and sleeps the
interval. Menu text: "Automatically save the non-volatile SaveRAM at a
regular interval (in seconds)." `block_sram_overwrite` (default off)
preserves SRAM across a state load. The `--sram-mode` switch
(`noload-nosave` and friends) exists for test runs; MAMR's oracle runs
need the same (`snes-oracles.md` section 2: aresref saves cartridge RAM to a
private temporary directory).

### 2.7 Input latency

- `input_poll_type_behavior` (default 2 = late, `config.def.h` 2023):
  0 polls before `retro_run`, 1 when the core calls the poll callback,
  2 on the core's first `retro_input_state` of the frame
  (`runloop.c` 6426-6447, 11060-11168). Late polling plus frame delay
  moves the sample as close to presentation as the frame budget allows.
- Run-ahead (`runahead.c`, `runahead_run` 1581-1800): run the frame,
  serialise, run N more frames with video and audio suspended and the
  same input, show the last of those, restore. The displayed frame is N
  frames ahead of the game's own internal lag. A second-instance variant
  keeps a copy of the core N frames ahead so audio is never rolled back.
  Preemptive frames (`preempt_run` 2143-2228) keep a ring of N states
  and re-run only when input changed. Mentioned only: it needs fast,
  complete serialisation, which MAMR's machines can offer later.
- Fewer swapchain images and hard sync with 0 frames shorten the queue
  between core and display at the price of stutter when a frame runs
  long.

### 2.8 Hotkey model

(`input/input_driver.c` 190-200, 13885-13905, 2029-2235;
`config.def.keybinds.h` from 1019; `runloop.c` `HOTKEY_CHECK` 7555-7563.)

- One optional modifier, "Hotkey Enable". Unbound: hotkeys fire
  directly. Bound and not held: hotkeys are ignored. Held: after
  `input_hotkey_block_delay` frames (default 5) all pad input to the
  core is blocked while the modifier stays down, so a modifier that is
  also a game button (Select) still passes a short tap to the game.
- Hotkeys fire on the rising edge (a static previous state per key);
  hold variants (fast-forward hold, slow-motion hold) act on level.
- Desktop keyboard defaults: F1 menu, Escape quit (twice within 3 s
  when `confirm_quit` is on, default on: "Press again to quit"),
  Space fast-forward toggle, l fast-forward hold, e slow motion, r
  rewind, p pause, k frame advance, h reset, F2 save state, F4 load
  state, F6 and F7 previous and next slot, F8 screenshot, F9 mute, f
  fullscreen, F11 grab mouse, Scroll Lock game focus (hotkeys off,
  keyboard to the core). Pad bindings of hotkeys default to none.
- Gamepad combos for menu and quit (`input/input_defines.h` 227-240):
  none, Down+Y+L+R, L3+R3, L1+R1+Start+Select, Start+Select, L3+R,
  L+R, hold Start, hold Select, Down+Select, L2+R2; the hold variants
  fire once after 2 s and re-arm on release. Desktop default is none.

For MAMR: Back held as the modifier, the five-frame rule, rising-edge
detection and "hold Start 2 s to quit" cover everything a sofa needs.

### 2.9 Configuration files and paths

(`configuration.c`, `open_default_config_file` 6785-6835;
`frontend/drivers/platform_unix.c`, `frontend_unix_get_env` 3487-3700;
`config_load_override` 8022-8220; `config_load_remap` 8319-8440.)

- `retroarch.cfg` is looked for in `$XDG_CONFIG_HOME/retroarch/`, else
  `~/.config/retroarch/`, then `~/.retroarch.cfg`; if none exists it is
  created in the first place, seeded from `/etc/retroarch.cfg` when
  that template exists. `-c FILE` replaces the search; `--appendconfig
  A|B` layers files on top.
- Every data directory defaults to a sibling of the config: `cores`,
  `saves`, `states`, `system`, `config`, `config/remaps`, `assets`,
  `playlists`, `screenshots`, `logs`, `thumbnails`, `downloads`, `temp`.
  RetroArch keeps all of it under `XDG_CONFIG_HOME` rather than
  splitting data into `XDG_DATA_HOME`; MAMR should split (config in
  `XDG_CONFIG_HOME/mamr`, saves and states in `XDG_DATA_HOME/mamr`,
  logs in `XDG_STATE_HOME/mamr`) since that is what backups and
  distribution packages expect.
- Overrides: `config/<core>/<core>.cfg`, `<content dir>.cfg`,
  `<game>.cfg`, applied in that order on top of the base, each holding
  only the keys that differ. Remaps `<core>/<game>.rmp` first found
  wins (game, directory, core). Core options
  `<core>/<game>.opt` likewise, else the global
  `retroarch-core-options.cfg`. All of these are one flat format:
  `key = "value"` per line, `#` comments, one parser.
- Command line that a launcher uses: `retroarch -L core.so content`,
  `-f` fullscreen, `-c` and `--appendconfig`, `-v`, `--log-file`,
  `--max-frames N` (exit after N frames, for tests), `-e N` entry slot,
  `-M` SRAM mode, `--load-menu-on-error`. Exit code 1 when the core or
  content fails to load from the command line, 0 otherwise.

### 2.10 Fast-forward and slow motion

`fastforward_ratio` (default 0 = unlimited, max 50) sets the timer
period to `1 / (fps * ratio)` and makes both swap and audio write
non-blocking; `fastforward_frameskip` (default on) drops presents so the
display still sees about one per refresh; audio is discarded beyond
what the device accepts (default), sped up with pitch
(`audio_fastforward_speedup`) or muted. `slowmotion_ratio` (default 3)
multiplies the resampling ratio, so the blocking audio write holds the
core at a third speed with lower pitch, and each frame is presented
three times. Cores learn the actual rate through
`GET_THROTTLE_STATE` (section 3.4).

### 2.11 The rest of the frontend, in one paragraph

RetroArch's own 10-foot menus are `rgui` (software, runs anywhere),
`xmb` (horizontal icon bar), `ozone` (the current desktop and console
default with sidebar and large thumbnails) and `glui` for touch; all
are driven by RetroPad input. Its game lists are JSON playlists (`.lpl`)
with path, label, core and database name, plus `content_history.lpl`
and `content_favorites.lpl`, and a runtime log per entry (`.lrtl`) for
play time and last played. Netplay and the shader system exist and are
out of scope here. ES-DE starts RetroArch through this command line
(section 1.1); with a MAMR core (section 3.8) all of this comes for
free.

## 3. The libretro API: the minimal core contract

Source: `include/libretro.h` of libretro-common (commit 4ed412f,
2026-10-24), 9334 lines. Line numbers below refer to that file. Nothing
in this section is RetroArch code; the header is the published
interface that every libretro frontend (RetroArch, ares, Mesen-S,
others) and every core implement.

### 3.1 Licence of the header

Lines 1-28 of the header carry an MIT (Expat) grant, copyright 2010-2024
The RetroArch team, with the sentence "The following license statement
only applies to this libretro API header (libretro.h)". The
libretro-common clone has no top-level LICENSE file; every file carries
its own MIT header instead. A BSD-3 project may vendor the header
unchanged: keep lines 1-28 intact, do not relicense it, and list it in
the third-party notices (`third_party/libretro/LICENSE` in the pattern
of `third_party/ares/LICENSE`). Nothing more is required, in source or
binary form.

### 3.2 Call order and the 25 exported symbols

A frontend loads the shared object, resolves the 25 `retro_*` symbols by
name, and calls them in this order (ordering guarantees from the header
in brackets):

| step | call | notes |
|---|---|---|
| 1 | `retro_api_version()` (line 9106) | must return `RETRO_API_VERSION` = 1 (line 97) |
| 2 | `retro_set_environment(cb)` (8999) | before `retro_init` (8996). The core announces here what it needs: `SET_SUPPORT_NO_GAME` is legal only here (1050); options are registered here or in `retro_load_game` |
| 3 | the five setters `retro_set_video_refresh`, `retro_set_audio_sample`, `retro_set_audio_sample_batch`, `retro_set_input_poll`, `retro_set_input_state` (9008-9044) | all before the first `retro_run` |
| 4 | `retro_init()` (9070) | globals may be stale from an earlier session in the same process; initialise everything explicitly (9052-9069) |
| 5 | `retro_get_system_info(info)` (9115) | callable at any time, even before init; the struct must be static (9109-9114). Fields: `library_name`, `library_version`, `valid_extensions` ("bin|rom|iso"), `need_fullpath`, `block_extract` (7361-7408) |
| 6 | `retro_load_game(game)` (9249) | `struct retro_game_info` {`path`, `data`, `size`, `meta`} (8210-8223); `game` is NULL for a content-less core (9243). `SET_PIXEL_FORMAT` belongs here or in step 7 (866-867) |
| 7 | `retro_get_system_av_info(info)` (9130) | only after a successful load (9120). Geometry: `base_width`, `base_height`, `max_width`, `max_height`, `aspect_ratio` (7624-7673); timing: `fps`, `sample_rate` as doubles (7676-7682) |
| 8 | `retro_set_controller_port_device(port, device)` (9161) | default is `RETRO_DEVICE_JOYPAD` on every port (9135) |
| 9 | `retro_run()` (9182), once per video frame | must call the input poll callback at least once (9172); a dropped frame is passed as NULL to the video callback when `GET_CAN_DUPE` said yes (9174-9179) |
| 10 | `retro_serialize_size` / `retro_serialize` / `retro_unserialize` (9195-9218) | at any time between load and unload; the size may never grow during a session (9187-9190) |
| 11 | `retro_get_memory_data` / `retro_get_memory_size(id)` (9314, 9328) | `RETRO_MEMORY_SAVE_RAM` 0, `RTC` 1, `SYSTEM_RAM` 2, `VIDEO_RAM` 3 (503-524); NULL and 0 when not applicable |
| 12 | `retro_reset()` (9168), `retro_get_region()` (9300: NTSC 0, PAL 1), `retro_cheat_reset` / `retro_cheat_set` (9225, 9236) | region means the TV standard, not the country (9289-9298) |
| 13 | `retro_unload_game()` (9286), then `retro_deinit()` (9095) | deinit must reset every global, the library may not be unloaded (9073-9094) |

`retro_load_game_special` (9273) serves subsystems only and may return
false. `RETRO_API` expands to default visibility on GCC and `dllexport`
on Windows (53-83), so a core can be built with hidden visibility and
still export exactly these symbols.

### 3.3 The callbacks

- **Video** (`retro_video_refresh_t`, 8836-8854): a pointer to a
  framebuffer, width and height in pixels, pitch in bytes. The format is
  0RGB1555 unless the core called `SET_PIXEL_FORMAT` (10); the header
  calls 0RGB1555 deprecated and recommends `RGB565` (2); `XRGB8888` (1)
  is the other common one (6925-6948). A packed frame is "highly
  recommended".
- **Audio** (8858-8883): either one stereo frame per call or, preferred,
  a batch of interleaved int16 L/R pairs; the batch returns the number
  of frames the frontend took, the only back-pressure signal in the base
  API (8881). Only one of the two may be used (8870). The header does
  not say how many frames a `retro_run` must deliver; by construction it
  is about `sample_rate / fps`, and RetroArch's rate control absorbs the
  rest (section 2.1).
- **Input** (8958-8988): `retro_input_poll_t` once per frame, then
  `retro_input_state_t(port, device, index, id)` per button.
  `RETRO_DEVICE_JOYPAD` is "modelled after a SNES controller" (156-176):
  ids B 0, Y 1, SELECT 2, START 3, UP 4, DOWN 5, LEFT 6, RIGHT 7, A 8,
  X 9, L 10, R 11, L2 12, R2 13, L3 14, R3 15 (320-371). With
  `GET_INPUT_BITMASKS` (51) the id `RETRO_DEVICE_ID_JOYPAD_MASK` = 256
  returns all sixteen buttons in one call (380, 1828-1844). Analog
  sticks: device `RETRO_DEVICE_ANALOG`, index LEFT 0 / RIGHT 1, id X / Y,
  range -0x8000..0x7fff (240-260, 389-393).
- **Environment** (`retro_environment_t(cmd, data)`, 8834): returns
  false for anything the frontend does not know. The calls a small
  software-rendered core needs are listed in 3.4.

### 3.4 Environment calls a MAMR core would use

| call (id) | data | purpose | lines |
|---|---|---|---|
| `SET_PIXEL_FORMAT` (10) | `const enum retro_pixel_format *` | choose XRGB8888 or RGB565 | 857-870 |
| `GET_CAN_DUPE` (3) | `bool *` | may pass NULL for a repeated frame | 760-768 |
| `GET_LOG_INTERFACE` (27) | `struct retro_log_callback *` | frontend log; stderr fallback is allowed | 1240-1248 |
| `GET_SYSTEM_DIRECTORY` (9), `GET_SAVE_DIRECTORY` (31) | `const char **` | where BIOS-like files and per-game saves live; may be NULL | 839-855, 1300-1331 |
| `SET_INPUT_DESCRIPTORS` (11) | `const struct retro_input_descriptor *` | names for the buttons ("Fire", "Grenade", "Coin") shown in the frontend's remap menu; no later than `retro_load_game` | 872-887, 7340-7352 |
| `SET_CONTROLLER_INFO` (35) | `const struct retro_controller_info *` | the device types per port (a joypad, a rotary stick) | 1451-1511 |
| `GET_CORE_OPTIONS_VERSION` (52), `SET_CORE_OPTIONS_V2` (67), `GET_VARIABLE` (15), `GET_VARIABLE_UPDATE` (17) | see below | core options; the core polls `GET_VARIABLE_UPDATE` each frame and re-reads changed keys | 952-1039, 1849-1871, 2305-2362 |
| `SET_SUPPORT_NO_GAME` (18) | `const bool *` | the core runs without a content file; only in `retro_set_environment` | 1041-1056 |
| `SET_MEMORY_MAPS` (36, experimental) | `const struct retro_memory_map *` | emulated address space for cheats and achievements; complements, does not replace, `retro_get_memory_data` | 1513-1535, 4651-4850 |
| `SET_GEOMETRY` (37) | `const struct retro_game_geometry *` | change the visible size or aspect inside the declared maxima without a driver reinit; only inside `retro_run` | 1537-1559 |
| `SET_SYSTEM_AV_INFO` (32) | `const struct retro_system_av_info *` | change fps, sample rate or maxima; may reinitialise the frontend's drivers | 1333-1370 |
| `SET_SERIALIZATION_QUIRKS` (44) | `uint64_t *` | flags INCOMPLETE, MUST_INITIALIZE, CORE_VARIABLE_SIZE, FRONT_VARIABLE_SIZE, SINGLE_SESSION, ENDIAN_DEPENDENT, PLATFORM_DEPENDENT | 1687-1701, 4594-4636 |
| `GET_SAVESTATE_CONTEXT` (72, experimental) | `enum retro_savestate_context *` | NORMAL, RUNAHEAD_SAME_INSTANCE, RUNAHEAD_SAME_BINARY, ROLLBACK_NETPLAY: lets a core skip validation when the state never leaves the process | 2441-2453, 7036-7091 |
| `GET_AUDIO_VIDEO_ENABLE` (47, experimental) | `int *` bitmask | VIDEO, AUDIO, FAST_SAVESTATES, HARD_DISABLE_AUDIO: run-ahead frames may skip rendering | 1770-1790, 4386-4452 |
| `SET_FRAME_TIME_CALLBACK` (21) | `const struct retro_frame_time_callback *` | microseconds since the last `retro_run`, or the reference 1000000/fps when the frontend is not in real time | 1077-1093, 6303-6318 |
| `GET_THROTTLE_STATE` (71, experimental) | `struct retro_throttle_state *` | the rate at which the frontend actually calls `retro_run` (NONE, FRAME_STEPPING, FAST_FORWARD, SLOW_MOTION, REWINDING, VSYNC, UNBLOCKED) | 2436-2440, 8404-8478 |
| `GET_TARGET_REFRESH_RATE` (50), `GET_TARGET_SAMPLE_RATE` (81), `SET_AUDIO_BUFFER_STATUS_CALLBACK` (62), `SET_MINIMUM_AUDIO_LATENCY` (63) | | a core may learn the host refresh rate and buffer occupancy, or ask for a minimum latency | 1826, 2611, 2133, 2171 |

Not needed: `SET_HW_RENDER` (14) and `GET_PREFERRED_HW_RENDER` (56),
since MAMR renders in software; `SET_AUDIO_CALLBACK` (22), which the
header reserves for cores with asynchronous audio (1101-1102);
`SET_SUBSYSTEM_INFO` (34).

**Core options.** Version 0 (`SET_VARIABLES`, 16) takes
`{key, "Title; a|b|c"}` pairs, the first value being the default
(7712-7753). Version 2 (`SET_CORE_OPTIONS_V2`, 67) takes categories and
definitions with `key`, `desc`, `info`, `category_key`, up to 128
`values` with labels, and `default_value` (7929-8120). The customary
helper `libretro_core_options.h` in `samples/core_options/` picks the
version the frontend supports at run time. Keys are prefixed with the
core name.

### 3.5 Save states and memory

`retro_serialize_size` is fixed for the session unless the core sets
`CORE_VARIABLE_SIZE` (4594-4636). The header says nothing about calling
the serialize functions from another thread, so a frontend serialises on
the emulation thread between two `retro_run` calls, and so should the
adapter. `RETRO_MEMORY_SAVE_RAM` is "battery-backed cartridge RAM"; the
frontend reads the pointer and size, writes the file on unload and, in
RetroArch, at the autosave interval (section 2.6). A core whose save
data does not fit one buffer uses `GET_SAVE_DIRECTORY` and flushes
itself (1309-1310).

### 3.6 Timing

The header states that `fps` is the video refresh rate and `sample_rate`
the audio rate (7678-7681), that `retro_run` runs one frame (9170), and
that the frontend controls time: the frame-time callback receives the
reference duration instead of wall time when the frontend frame-steps
or fast-forwards (1081-1083), and fast-forward at ratio 5 means
`retro_run` is called at 300 Hz for a 60 Hz core (8357-8361). How the
frontend paces and resamples is left to the frontend; RetroArch's
answer is section 2.

### 3.7 Threading

No general single-thread rule is written down, but every ordering
sentence assumes one. Only the asynchronous audio callback is declared
callable "from any thread" (1120-1121). An adapter should assume the
whole `retro_*` surface is single-threaded.

### 3.8 What a MAMR game would deliver as a core

A MAMR core is one shared object per game, `ikari_libretro.so`,
`rtype_libretro.so`, `zelda3_libretro.so`, because the recompiled game
code and the ROM-derived data are compiled in (concept section 21). The
adapter (section 4.2) is one C++ file against the common machine
interface; each game links it with its machine. Per game it supplies:

- `retro_get_system_info`: name, version, `valid_extensions` empty,
  `need_fullpath` false; `SET_SUPPORT_NO_GAME` true, so RetroArch shows
  the core under "Start Core" and ES-DE can launch it without a ROM
  argument (section 4.2 for the ES-DE command).
- `retro_get_system_av_info`: base and max size equal to the machine's
  frame (Ikari 216 x 288 portrait, R-Type 384 x 256, SNES 256 x 224 with
  max 512 x 478), `aspect_ratio` 3:4 or 4:3 as the cabinet or TV shows
  it, `fps` exactly the machine's rate (60, 55.0176, 60.0985, 50.0070)
  and `sample_rate` the machine's native rate (Ikari 55556, R-Type
  55930, SNES 32040 as the two SDL front ends and `AudioOut` already use
  them) or a fixed 48000 after the machine's own resampler. Passing the native rate and letting
  the frontend resample is the libretro way; MAMR's own `AudioOut` is
  then bypassed in the core build.
- `retro_run`: one `machine_run_frame`, one video callback with the
  frame in XRGB8888, one audio batch with the frame's samples, input
  taken through `retro_input_state` with the SNES-style ids
  (Ikari: d-pad walk, A fire, B grenade, L/R rotate, SELECT coin, START
  start; SNES: the natural 1:1 map).
- `retro_serialize*` from the machine's save-state function;
  `retro_get_memory_data(SAVE_RAM)` returns the SNES cartridge RAM (the
  arcade games return NULL; their high-score NVRAM, if any, goes the
  same way).
- `retro_get_region`: PAL for the PAL Zelda, NTSC otherwise.
- `SET_INPUT_DESCRIPTORS` with the game's button names, and a handful
  of core options (region where it applies, the YM reset variant of
  R-Type, the `--follow` camera of Ikari).

A `<name>_libretro.info` text file next to the core is RetroArch's own
convention (display name, extensions, firmware), not part of the API;
nothing in libretro-common describes it. RetroArch loads a core without
one, with a generic name in the menu.

## 4. Recommendation for MAMR, in three stages

The target picture: a Linux machine with its own GPU at the television,
a controller, a menu that lists Arcade, SNES and NES, and games that
start and return without a keyboard. The stages build on each other;
each is usable on its own.

### 4.1 Stage a: common machine interface and one SDL3 front end

The two SDL front ends (`games/ikari/ikari_sdl.cpp`,
`games/rtype/rtype_sdl.cpp`) and the SNES audio stage already contain
the right ideas; stage a makes them one program. (Done in phase S7:
both are now builds of `mamr_play` with one machine, docs/frontend.md;
the line numbers into them in this document refer to the earlier
standalone programs.) The common interface should expose, per
machine:

- `run_frame()`, the frame geometry and the exact frame rate as a
  rational or double (60, 55.0176, 60.0985, 50.0070), the native audio
  rate (55556, 55930, 32040) and the region;
- the frame as a packed 32-bit buffer, the frame's audio as interleaved
  stereo (mono doubled) int16 or float, the input as the game's own
  button set behind a per-game descriptor list (name per button, so the
  front end can draw the help bar and a remap screen);
- `serialize_size()`, `serialize()`, `unserialize()` and a pointer plus
  size for cartridge RAM where it exists.

These are the libretro primitives one to one (section 3.2); naming them
that way costs nothing and makes stage b a thin file. The SDL3 front end
then does the things RetroArch does in its run loop, taken as concepts
(section 2):

1. **Dynamic rate control** on the audio stream: the ratio
   `1 + d * (2 * fill / capacity - 1)` with `d` = 0.005, which
   `runtime/snes/snes_audio_out.h` already implements and
   `ikari_sdl.cpp` 236-255 approximates with `SDL_SetAudioStream
   FrequencyRatio`. Use the SNES `AudioOut` for all machines; the SDL3
   stream then only converts format and rate once, with a fixed ratio.
2. **Pace by the display when it is close, by the machine when it is
   not**: measure the display's refresh (SDL3 reports it in
   `SDL_DisplayMode::refresh_rate`; RetroArch also measures it from
   swap timestamps), compare with the machine's rate, and if the
   deviation is under 5 percent run vsync-locked and let rate control
   absorb the rest; otherwise (50 Hz Zelda on a 60 Hz screen, 55 Hz
   R-Type anywhere) pace by a monotonic clock as `ikari_sdl.cpp`
   262-266 does, present without blocking, and accept a repeated frame
   every tenth frame or so. The user-facing fix for 50 Hz content is a
   50 Hz display mode (SDL3 `SDL_SetWindowFullscreenMode` with a 50 Hz
   mode when the TV offers one; most do), which the launcher can select
   per game from the manifest.
3. **Audio buffer of about 64 ms**, measured in frames of the output
   rate, with the fill level driving rate control; underruns repeat the
   last frame, never silence, and are counted for a debug overlay.
4. **Input polled once per frame, as late as possible** before
   `run_frame`, from SDL3's gamepad API; a frame delay setting is not
   worth it until someone measures.
5. **Save states in slots** `<game>.state0..9` under
   `$XDG_DATA_HOME/mamr/states/`, plus `<game>.state.auto` written on
   quit and offered on start; one-deep undo of a load.
6. **Cartridge RAM** written on quit and, when it changed, every 10 s
   (a memcmp against a copy, as RetroArch's autosave thread does).
7. **One hotkey modifier** (Back or Select held) that turns the other
   buttons into fast-forward, save, load, slot up and down, reset,
   screenshot and quit, with the game's inputs suppressed while the
   modifier is held, and the same actions on keyboard keys without a
   modifier. Quit asks nothing; it writes RAM and the autosave state and
   exits with code 0.
8. **Config and paths under XDG**: `$XDG_CONFIG_HOME/mamr/mamr.toml`
   for the settings, `$XDG_DATA_HOME/mamr/{saves,states,screenshots}`,
   `$XDG_STATE_HOME/mamr/log.txt`; one flat key = value file, with
   `--config FILE` to point elsewhere.

The binary contract that makes the same program start from ES-DE, from
RetroArch's "Start Core" via stage b, or from the stage c launcher:

```text
<game>_sdl [--fullscreen] [--display N] [--mode WxH@Hz] [--scale N]
           [--frames N] [--no-sound] [--config FILE] [--state FILE] [game-specific flags]
exit code 0 on a normal quit, 1 on a start-up failure (device, config),
stdout quiet, errors on stderr, no forked children, fullscreen-desktop
by default when started from a launcher, window otherwise.
```

### 4.2 Stage b: a libretro adapter

One file, `platform/libretro/mamr_libretro.cpp`, linked once per game
into `<game>_libretro.so`, implementing section 3.8 over the stage a
interface. Everything the adapter needs is a straight mapping:
`retro_run` is `run_frame` plus three callbacks; `retro_serialize*` are
the save-state functions; `retro_get_memory_data` returns the cartridge
RAM; `retro_get_system_av_info` returns the machine's geometry and
rates. The header is vendored under `third_party/libretro/` with its
MIT notice. Core options cover what the command line covers.

What this buys: RetroArch's menu, hotkeys, rate control, VRR and
50 Hz handling, shaders, run-ahead, save-state thumbnails and rewind,
with no code of RetroArch in MAMR; and ES-DE lists the game as a
RetroArch core with one line in a custom `es_systems.xml`
(`%EMULATOR_RETROARCH% -L %CORE_RETROARCH%/zelda3_libretro.so
%INJECT%=nothing`, the form ES-DE uses for its content-less Bomberman
and Minecraft cores, with a `.game` placeholder file per game). ares and the
other libretro frontends work the same way. It also buys a second
oracle path: the same core can be driven headless by a tiny test
frontend that calls `retro_run` and hashes frames.

Cost: about 400 lines, a CMake target per game, and the discipline of
never calling SDL from the machine layer, which stage a already
requires.

### 4.3 Stage c: an own launcher, only if ES-DE does not fit

ES-DE needs a ROM directory with a placeholder file per game and a
custom system entry per MAMR system (section 5); that is a one-time
setup of three files and it handles themes, controllers and the TV.
Reasons to still write a launcher: ES-DE links FFmpeg, FreeImage,
Poppler, libgit2, HarfBuzz, ICU, curl and SDL2 (its `CMakeLists.txt`
121-142) for a menu of twelve entries; it
cannot pass a 50 Hz display mode per game; its launch path runs through
`/bin/sh` and loses the exit code; and the whole experience should be
"from one piece", a single binary that starts at boot. If that matters,
the launcher is small:

**Screens** (one focus, no mouse, help bar at the bottom with the
icons of the detected pad type):

1. *Systems*: a horizontal carousel of three to four logos (Arcade,
   SNES, NES, later more), selected logo scaled 1.5, others at half
   opacity, circular, eased in 400 ms (section 1.3). Left/right choose,
   A enters, Start opens settings, hold Back for 3 s to quit.
2. *Games*: a text list on the right half (medium font, 0.045 of the
   height, line spacing 1.5), cover or screenshot on the left at 0.4 of
   the height, under it two lines of metadata from the manifest (year,
   players, region, last played), under that a scrolling description.
   Up/down choose with the three scroll tiers, left/right switch
   system, A launches, B back, Y toggles favourite (written back to the
   manifest's sidecar), X opens the per-game options (display mode,
   region, the game's own flags, remap).
3. *Launch*: a 1 s overlay with the game title and "Hold Back + Start
   to return", then the child is started with `posix_spawn` and the
   launcher's window is hidden (`SDL_HideWindow`) and its audio device
   closed; the launcher keeps polling the gamepad subsystem for hot-plug
   only and waits with `waitpid`. On return the window is shown again,
   input is ignored for one frame (ES-DE's lesson), the exit code is
   read from `waitpid` (so an error can actually be shown) and the
   manifest sidecar gets play count and last-played.
4. *Settings*: audio device and volume, display and refresh policy
   (match content rate: yes / no / only 50 Hz), screensaver minutes,
   pad type for the icons, remap per game, quit.
5. *Screensaver*: dim to 40 percent after 5 min, any input cancels;
   an attract mode that launches a game with `--frames` and no input
   can come later.

**Manifest** (`$XDG_CONFIG_HOME/mamr/library.toml`, written by the
builder and editable by hand; TOML because `games/*/*.toml` already use
it):

```toml
[[system]]
id = "arcade"
name = "Arcade"
logo = "arcade.png"

[[system]]
id = "snes"
name = "Super Nintendo"
logo = "snes.png"

[[game]]
system = "arcade"
id = "ikari"
title = "Ikari Warriors"
year = 1986
players = 2
exe = "ikari_sdl"            # relative to the launcher's bin directory, or absolute
args = ["--fullscreen"]
rate = 60.0                  # content frame rate, for the display mode choice
rotation = 270
cover = "ikari.png"          # relative to the manifest's media directory
desc = "..."

[[game]]
system = "snes"
id = "zelda3-pal"
title = "The Legend of Zelda: A Link to the Past"
region = "pal"
rate = 50.007
exe = "zelda3_sdl"
args = ["--fullscreen", "--region", "pal"]
```

A sidecar `library-state.toml` holds per game `favorite`, `playcount`,
`lastplayed` and the chosen options, so the manifest stays
hand-editable and the builder can regenerate it.

**Navigation model**: a stack of screens; the top one owns input; a
screen receives logical inputs (up, down, left, right, a, b, x, y,
start, back, l, r) that the launcher derives from SDL3 gamepad events
and the fixed keyboard map of section 1.5; held directions repeat in
tiers. Every screen reports its help prompts; the help bar renders them.
Rendering is SDL3's 2D renderer with a texture atlas for text, sized
from the screen height, no theme engine: the layout constants above are
the theme. One binary, SDL3 and a TrueType rasteriser (SDL_ttf or
stb_truetype) as the only dependencies, under 3000 lines.

Whether stage c happens is decided after stage b has run on the
television behind ES-DE for a while.

### 4.4 Sources of the ideas and their licences

| idea | source | licence | how taken |
|---|---|---|---|
| system and game list from a config file, one command template per system, placeholder substitution | EmulationStation `es-app/src/SystemData.cpp` (`loadConfig`, `writeExampleConfig`), ES-DE `es-app/src/FileData.cpp` (`launchGame`) | MIT | concept; the manifest is TOML, not XML |
| blocking launch, window hidden or torn down, audio device closed, input ignored for one frame on return, play count written after | EmulationStation `SystemData::launchGame`, ES-DE `ViewController::launch`, `PlatformUtil::launchGameUnix` | MIT | concept; MAMR uses `posix_spawn` and `waitpid` |
| carousel geometry and easing, detailed view layout, scroll tiers, marquee | EmulationStation `es-app/src/views/SystemView.cpp`, `DetailedGameListView.cpp`, `es-core/src/components/IList.h`, `TextListComponent.h` | MIT | numbers reused, code written new |
| font sizes as fractions of the screen, help bar with pad icons at the bottom | EmulationStation and ES-DE `es-core/src/resources/Font.h`, `HelpComponent` | MIT | concept |
| hold-a-button device detection, press-on-release mapping dialog, already-taken check, skip by holding | EmulationStation `es-core/src/guis/GuiDetectDevice.cpp`, `GuiInputConfig.cpp` | MIT | concept, for the per-game remap screen |
| SDL gamepad database instead of a mapping wizard | ES-DE `es-core/src/InputManager.cpp` | MIT | concept; SDL3 provides it |
| dim screensaver, launch from screensaver | EmulationStation `Window::onSleep`, ES-DE `Screensaver.cpp` | MIT | concept |
| dynamic rate control formula and limits, timing-skew threshold, buffer sizing from latency | RetroArch `audio/audio_driver.c`, `gfx/video_driver.c` (section 2.1) | GPL-3 | concept and formula only; MAMR's `AudioOut` predates this document |
| pacing choice by refresh-rate deviation, VRR mode, frame delay | RetroArch `runloop.c`, `gfx/video_driver.c` (section 2.2, 2.3) | GPL-3 | concept only |
| save-state slots, autosave state, undo buffer, SRAM autosave by comparison | RetroArch `tasks/task_save.c`, `tasks/task_autosave.c` (section 2.5, 2.6) | GPL-3 | concept only |
| hotkey modifier that blocks game input, hotkey set | RetroArch `input/input_driver.c` (section 2.8) | GPL-3 | concept only |
| XDG paths, flat config, per-game overrides | RetroArch `frontend/drivers/platform_unix.c`, `configuration.c` (section 2.9) | GPL-3 | concept only |
| core contract, callbacks, memory and serialize interface | `libretro.h` | MIT (header) | vendored unchanged with notice |

No code from RetroArch is in MAMR or is to be put in it. Code from
EmulationStation or ES-DE is not needed either; should a small piece
ever be copied, it carries the MIT notice in `third_party/`.

## 5. Checklist: a MAMR binary under ES-DE, without libretro

What ES-DE needs from a program that is not RetroArch, derived from
`FileData::launchGame` and `launchGameUnix` (section 1.6) and from how
ES-DE's own bundled systems treat programs without ROMs.

1. **One file per game that matches an extension.** ES-DE lists what it
   finds in the system directory; it has no notion of a game without a
   file. ES-DE's own practice for programs without ROMs is a small text
   file: `.sh` and `.desktop` entries in the `ports` system, `.game`
   files for Bomberman and Minecraft (started with `%INJECT%=nothing`
   so that no `%ROM%` is passed), `.scummvm` files (`es_systems.xml`
   1722-1732, 1899-1906; `USERGUIDE.md` 2786, 2990-3019). For MAMR the
   simplest form is one shell script per game,
   `~/ROMs/mamr/Ikari Warriors.sh`, containing
   `exec /opt/mamr/bin/ikari_sdl --fullscreen`. The file stem is the
   displayed name.
2. **A custom system entry**, `~/ES-DE/custom_systems/es_systems.xml`.
   The `OS-SHELL` find rule runs the script as `bash <script>`
   (`es_find_rules.xml` 4-10), so no execute bit is needed:

```xml
<?xml version="1.0"?>
<systemList>
    <system>
        <name>mamr</name>
        <fullname>MAMR</fullname>
        <path>%ROMPATH%/mamr</path>
        <extension>.sh</extension>
        <command label="MAMR">%EMULATOR_OS-SHELL% %ROM%</command>
        <platform>arcade</platform>
        <theme>arcade</theme>
    </system>
</systemList>
```

   The alternative is a dispatcher binary by absolute path,
   `<command>/opt/mamr/bin/mamr-run %ROM%</command>`, which needs no
   find rule (`FileData.cpp` 2707-2763, "method 2") and reads a `.mamr`
   file. A command must begin with an executable or an `%EMULATOR_`
   placeholder: the first token is looked up as a file or in `$PATH`,
   so a command that starts with `%INJECT%` fails with "COULDN'T FIND
   EMULATOR". One system per MAMR system (`mamr-arcade`, `mamr-snes`)
   if the carousel should show them separately, each with its own
   directory and `<theme>` so the theme's artwork applies. A system with
   no matching files is hidden.
3. **Start directory**: the command runs through `/bin/sh` with
   `cd <dir> &&` only if `%STARTDIR%=...` is given; otherwise the
   working directory is ES-DE's. Resolve config and data paths from
   XDG, never from the working directory.
4. **Exit code**: return 0 on a normal quit and non-zero on a start-up
   failure. On Linux the code that reaches ES-DE is the shell's after
   backgrounding (`PlatformUtil.cpp` 231, 292-295), so by the reading of
   the source it is always 0 and the error popup never shows; on
   Windows `launchGameWindows` waits on the process and the code counts.
   Write errors to stderr: ES-DE captures merged stdout and stderr into
   `~/ES-DE/logs/es_log.txt`, 5 MiB cap, and logs it at debug level when
   the code is 0, at error level otherwise.
5. **End of the run is end of file on the pipe**, not process exit.
   Never leave a child process or thread holding the inherited stdout
   or stderr (a detached helper, a logger); ES-DE would wait for it.
   Keep stdout quiet; a frame-rate trace at 60 lines per second fills
   the log.
6. **Fullscreen is the program's job.** ES-DE's window stays open,
   full-screen desktop, never minimised, with one black frame swapped
   before the launch; it passes no flag (`USERGUIDE.md` 1174-1178). The
   program must create its own fullscreen-desktop window and raise it;
   `--fullscreen` as the default when a parent is a launcher, or
   simply always with `--window` to opt out. On return the window
   manager has to give focus back to ES-DE's still-mapped window; on a
   plain X11 or Wayland session with one app at a time this works, and
   ES-DE's guide warns that `RunInBackground` makes window switching
   unreliable (`USERGUIDE.md` 542).
7. **Audio**: ES-DE pauses but does not close its SDL2 audio device.
   With PipeWire or PulseAudio a second client is no problem; with bare
   ALSA and `hw:` devices it would be, and only a `DEINIT_ON_LAUNCH`
   build of ES-DE closes the device. Open the default device, never
   a hardware address.
8. **Input**: ES-DE keeps its controllers open and drains events, so
   the program opens the same pads through SDL3 without conflict. The
   button that quits the game should be released before the program
   exits (ES-DE ignores input for one frame after the return, so a
   quick release is enough).
9. **Hot-plug and quit**: the program handles its own pad add and
   remove; a controller combination to quit (hold Start 2 s, or
   Back+Start) is required because there is no keyboard at the TV and
   ES-DE will not kill the child.
10. **Artwork**: a cover and a screenshot per game under
    `~/ES-DE/downloaded_media/mamr/covers/<stem>.png` and
    `.../screenshots/<stem>.png`, named like the placeholder file, are
    picked up without scraping (`INSTALL.md` 2192-2193).

Items 4 to 6 apply to any launcher, including a future own one, which
should take the exit code from `waitpid` instead.
