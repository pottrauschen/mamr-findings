-- SNES hash lines (docs/snes-oracle-format.md, version 4) for MAME 0.285,
-- the weak cross-check oracle. Start it through run_mame.sh. Environment:
--   FH_OUT     output file (required)
--   FH_FRAMES  number of F lines (default 600)
--   FH_SPC     "1" when a real IPL dump is installed: aram is then
--              written; otherwise every SPC-side field is "-"
--   FH_ROM_ID  value of the header key rom=
--   FH_INJECT  "F:ADDR:XOR" fault injection (hex)
--
-- Limits (docs/snes-oracles.md): the sampling point is MAME's frame_done
-- callback, not the first instruction boundary after scanline 225; anc is
-- not available ("-"; inputs are not driven); mclk is maincpu
-- m_totalcycles, which jitters by about 24 clocks per frame; OAM is only
-- kept decoded and the PPU registers not in the canonical form ("-");
-- MAME 0.285 exposes neither the DSP registers nor the APU ports nor the
-- S-SMP timers ("-"); smp, apuio and sram are "-".

local m = manager.machine
local out = assert(io.open(os.getenv("FH_OUT"), "w"))
local maxFrames = tonumber(os.getenv("FH_FRAMES") or "600")
local spc = os.getenv("FH_SPC") == "1"
local PRIME = 0x100000001B3
local BASIS = -3750763034362895579

local injFrame, injAddr, injXor = -1, 0, 0
do
  local f, a, x = (os.getenv("FH_INJECT") or ""):match("^(%d+):(%x+):(%x+)$")
  if f then injFrame, injAddr, injXor = tonumber(f), tonumber(a, 16), tonumber(x, 16) end
end

local function item(dev, name)
  local d = m.devices[dev]
  local idx = d and d.items[name]
  return idx and emu.item(idx)
end
local wram = assert(item(":maincpu", "0/:wram"), "wram item")
local aram = item(":soundcpu", "0/:aram")
local vram = assert(item(":ppu", "0/m_vram"), "vram item")
local cgram = assert(item(":ppu", "0/m_cgram"), "cgram item")
local cpu = m.devices[":maincpu"].state
local scr = m.screens[":screen"]

local function fnvString(s, mask16hi)
  local h = BASIS
  local byte = string.byte
  for i = 1, #s do
    local b = byte(s, i)
    if mask16hi and i % 2 == 0 then b = b & 0x7F end
    h = (h ~ b) * PRIME
  end
  return h
end

local function fnvBytes(t)
  local h = BASIS
  for i = 1, #t do h = (h ~ t[i]) * PRIME end
  return h
end

local function le16(t, v) t[#t + 1] = v & 0xFF; t[#t + 1] = (v >> 8) & 0xFF end

-- Canonical image from the 512-wide MAME bitmap: rows 0..223 hold
-- scanlines 1..224 (checked against aresref); a pair of equal half-pixels collapses to one pixel.
local function imgHash()
  local px, w, h = scr:pixels()
  local byte = string.byte
  local rows, hires = {}, false
  for y = 1, 224 do
    local row = {}
    for x = 0, w - 1 do
      local o = ((y - 1) * w + x) * 4 + 1
      local b8, g8, r8 = byte(px, o), byte(px, o + 1), byte(px, o + 2)
      row[x + 1] = (r8 >> 3) | ((g8 >> 3) << 5) | ((b8 >> 3) << 10)
    end
    if w == 512 and not hires then
      for x = 1, 511, 2 do if row[x] ~= row[x + 1] then hires = true; break end end
    end
    rows[y] = row
  end
  local t = {}
  for y = 1, 224 do
    local row = rows[y]
    if hires then for x = 1, 512 do le16(t, row[x]) end
    elseif w == 512 then for x = 2, 512, 2 do le16(t, row[x]) end
    else for x = 1, 256 do le16(t, row[x]) end end
  end
  return fnvBytes(t), string.format("%dx224", hires and 512 or 256)
end

local FIELDS = {"cpu", "smp", "apuio", "wram", "vram", "oam", "cgram", "ppu", "aram", "dsp", "img", "sram"}

-- The snes driver is NTSC; its APU runs at the nominal 24.576 MHz (clk=nom).
out:write(string.format("H snesfh 4 oracle=mame rom=%s fill=55 region=ntsc clk=nom core=mame-0.285%s\n",
  os.getenv("FH_ROM_ID") or "-", spc and "" or " ipl=placeholder"))

local frame, chain = 0, BASIS
emu.register_frame_done(function()
  if frame >= maxFrames then return end
  frame = frame + 1
  if frame == injFrame then
    local v = wram:read(injAddr)
    wram:write(injAddr, v ~ injXor)
  end
  local h, raw = {}, {}
  local c = {}
  le16(c, cpu["A"].value); le16(c, cpu["X"].value); le16(c, cpu["Y"].value); le16(c, cpu["S"].value)
  le16(c, cpu["D"].value)
  c[#c + 1] = cpu["DB"].value & 0xFF; c[#c + 1] = cpu["PB"].value & 0xFF; c[#c + 1] = cpu["P"].value & 0xFF
  c[#c + 1] = (cpu["E"].value ~= 0) and 1 or 0
  h.cpu = fnvBytes(c)
  local hex = {}
  for i = 1, #c do hex[i] = string.format("%02x", c[i]) end
  raw.cpu = table.concat(hex)
  h.wram = fnvString(wram:read_block(0, 0x20000))
  h.vram = fnvString(vram:read_block(0, 0x10000))
  h.cgram = fnvString(cgram:read_block(0, 512), true)
  if spc and aram then h.aram = fnvString(aram:read_block(0, 0x10000)) end
  local imgsz
  h.img, imgsz = imgHash()
  local parts = {string.format("F %d anc=- mclk=%d pc=%06x", frame, item(":maincpu", "0/m_totalcycles"):read(0),
                               cpu["PC"].value & 0xFFFFFF)}
  local cb = {}
  for i = 0, 7 do cb[#cb + 1] = (chain >> (8 * i)) & 0xFF end
  for _, name in ipairs(FIELDS) do
    local v = h[name]
    for i = 0, 7 do cb[#cb + 1] = v and ((v >> (8 * i)) & 0xFF) or 0 end
    if v == nil then parts[#parts + 1] = name .. "=-"
    elseif raw[name] then parts[#parts + 1] = name .. "=" .. raw[name]
    else parts[#parts + 1] = string.format("%s=%016x", name, v) end
  end
  chain = fnvBytes(cb)
  parts[#parts + 1] = "imgsz=" .. imgsz
  parts[#parts + 1] = string.format("all=%016x", chain)
  out:write(table.concat(parts, " ") .. "\n")
  if frame >= maxFrames then
    out:close()
    m:exit()
  end
end)
