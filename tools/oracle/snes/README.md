# SNES oracle tools

Front ends and scripts that write and compare the per-frame SNES hash
lines (phase S8 of docs/snes-architecture.md):

- `hashline.py`: reference implementation of the format, `compare.py`,
  `gates.py`, `input_script.py`
- `aresref/`: headless ares front end (built outside the repository)
- `mesen/`, `mame/`: Lua scripts for MesenCE and MAME

Documentation:

- docs/snes-oracle-format.md: hash line format, version 4
- docs/snes-oracle-input-script.md: the shared input script
- docs/snes-oracles.md: oracle setup, limits, gates and results
