-- NES hash lines (docs/nes-oracle-format.md, version 2) for MAME 0.285,
-- the second oracle. Start it through run_mame.sh. Environment:
--   FH_OUT          output file (required)
--   FH_FRAMES       number of F lines (default 600)
--   FH_INPUT        input script file (format section 7), optional
--   FH_ROM_ID       value of the header key rom=
--   FH_INJECT       "F:ADDR:XOR" fault injection into the internal RAM (hex)
--   FH_DUMP_DIR     directory for canonical field dumps
--   FH_DUMP_AT      "F,F,..." frames to dump; FH_DUMP_EVERY  K
--   FH_ACC          "1": write the T line of AccuracyCoin (format section 8)
--   FH_STOP_AFTER_T "1": end the run after the T line
--   FH_ACC_FLAG     zero page address (hex) of the "running" flag: 35 (default)
--                   for the run of every test, 34 for the run of one page
--   FH_ACC_HANG     K: stop with a "# hang" comment when the running test
--                   (page $14, index $16) has not changed for K frames, or
--                   when the run of one page goes back to an earlier test
--   FH_BLARGG       "1": watch the result protocol at $6000 (format section 9):
--                   R line when a result is there, a reset when one is
--                   requested; with FH_STOP_AFTER_T the run ends at the R line
--   FH_SCREEN       "1": after the last F line an N line with $2000-$2FFF
--   FH_ACC_SKIP     "ADDR,ADDR" (hex): result bytes set to $FF before the run,
--                   which marks those tests skipped as the B button does
--
-- Limits (docs/nes-oracles.md section 3): the sampling point is MAME's
-- frame_done callback, not the first instruction boundary after scanline
-- 240, dot 0; cpu and pc are therefore not comparable at the instruction
-- level. dot is "-". apu and snd are "-" (format version 2): this writer
-- does not read MAME's APU device. ppu is "-": the 2C02 device keeps the rendering
-- address (m_refresh_data) and the $2007 address (m_videomem_addr) apart,
-- so there is no single v. Inputs are set through the ioport fields, which
-- MAME applies at its next per-frame input update, not at the strobe.

-- MAME runs the autoboot script again after a soft reset (blargg's tests
-- ask for one): the second run must not open the output a second time.
if nesfhLoaded then return end
nesfhLoaded = true

local m = manager.machine
local out = assert(io.open(os.getenv("FH_OUT"), "w"))
local maxFrames = tonumber(os.getenv("FH_FRAMES") or "600")
local dumpDir = os.getenv("FH_DUMP_DIR")
local dumpEvery = tonumber(os.getenv("FH_DUMP_EVERY") or "0")
local dumpAt = {}
for f in (os.getenv("FH_DUMP_AT") or ""):gmatch("%d+") do dumpAt[tonumber(f)] = true end
local accMode = os.getenv("FH_ACC") == "1"
local stopAfterT = os.getenv("FH_STOP_AFTER_T") == "1"
local accHang = tonumber(os.getenv("FH_ACC_HANG") or "0")
local accFlag = tonumber(os.getenv("FH_ACC_FLAG") or "35", 16)
local hangKey, hangSince = nil, 0
local blarggMode = os.getenv("FH_BLARGG") == "1"
local screenMode = os.getenv("FH_SCREEN") == "1"
local accSkip = {}
for x in (os.getenv("FH_ACC_SKIP") or ""):gmatch("%x+") do accSkip[#accSkip + 1] = tonumber(x, 16) end
local PRIME = 0x100000001B3
local BASIS = -3750763034362895579

local injFrame, injAddr, injXor = -1, 0, 0
do
  local f, a, x = (os.getenv("FH_INJECT") or ""):match("^(%d+):(%x+):(%x+)$")
  if f then injFrame, injAddr, injXor = tonumber(f), tonumber(a, 16), tonumber(x, 16) end
end

local function fail(msg)
  out:write("# error: " .. msg .. "\n")
  out:close()
  m:exit()
  error(msg)
end

local function item(dev, name)
  local d = m.devices[dev]
  local idx = d and d.items[name]
  return idx and emu.item(idx)
end

local cart
for tag, _ in pairs(m.devices) do
  if tag:match("^:nes_slot:[%w_]+$") then cart = tag end
end
if not cart then fail("no cartridge device under :nes_slot") end

local ram = assert(item(":maincpu", "0/:mainram"), "mainram item")
local spriteram = assert(item(":ppu", "0/m_spriteram"), "spriteram item")
local palram = assert(item(":ppu", "0/m_palette_ram"), "palette item")
local prgram = item(cart, "0/m_prgram")
local prgbank = item(cart, "0/m_prg_bank")
local chrorig = item(cart, "0/m_chr_orig")
local irqCount = item(cart, "0/m_irq_count")
local irqLatch = item(cart, "0/m_irq_count_latch")
local irqClear = item(cart, "0/m_irq_clear")
local irqEnable = item(cart, "0/m_irq_enable")
local totalcycles = item(":maincpu", "0/m_totalcycles")
local vspace = m.devices[":ppu"].spaces["videoram"]
local pspace = m.devices[":maincpu"].spaces["program"]
local cpu = m.devices[":maincpu"].state
local scr = m.screens[":screen"]

-- ------------------------------------------------------------ input script

local BUTTONS = {"A", "B", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT"}
local FIELD = {A = "P1 A", B = "P1 B", SELECT = "P1 Select", START = "P1 Start", UP = "P1 Up", DOWN = "P1 Down",
               LEFT = "P1 Left", RIGHT = "P1 Right"}
local BIT = {}
for i, b in ipairs(BUTTONS) do BIT[b] = i - 1 end
local joypad = m.ioport.ports[":ctrl1:joypad:JOYPAD"]

local function parseHex(s)
  s = s:gsub("^%$", ""):gsub("^0[xX]", "")
  if not s:match("^%x+$") then return nil end
  return tonumber(s, 16)
end

local cmds = {}
local inputPath = os.getenv("FH_INPUT")
if inputPath and inputPath ~= "" then
  if not joypad then fail("no joypad in port 1") end
  local fh = io.open(inputPath, "r")
  if not fh then fail("cannot read input script " .. inputPath) end
  local n = 0
  for raw in fh:lines() do
    n = n + 1
    local line = raw:gsub("#.*$", "")
    local tok = {}
    for t in line:gmatch("%S+") do tok[#tok + 1] = t end
    if #tok > 0 then
      local op = tok[1]:upper()
      if op == "HOLD" or op == "RELEASE" then
        if #tok < 2 then fail("line " .. n .. ": needs a button") end
        local mask = 0
        for k = 2, #tok do
          local bit = BIT[tok[k]:upper()]
          if not bit then fail("line " .. n .. ": unknown button") end
          mask = mask | (1 << bit)
        end
        cmds[#cmds + 1] = {op, mask}
      elseif op == "WAIT" then
        local c = tonumber(tok[2] or "")
        if #tok ~= 2 or not c or c < 1 or math.type(c) ~= "integer" then
          fail("line " .. n .. ": WAIT needs a count >= 1")
        end
        cmds[#cmds + 1] = {op, c}
      elseif op == "WAIT_RAM8" then
        local a, v = parseHex(tok[2] or ""), parseHex(tok[3] or "")
        if #tok ~= 3 or not a or not v or v > 255 or a > 0x7FF then fail("line " .. n .. ": bad WAIT_RAM8") end
        cmds[#cmds + 1] = {op, a, v}
      else
        fail("line " .. n .. ": unknown command")
      end
    end
  end
  fh:close()
end

local spc, remaining, pad = 1, nil, 0
local function scriptStep()
  while spc <= #cmds do
    local c = cmds[spc]
    if c[1] == "HOLD" then pad = pad | c[2]
    elseif c[1] == "RELEASE" then pad = pad & ~c[2]
    elseif c[1] == "WAIT" then
      if remaining == nil then remaining = c[2] end
      if remaining > 0 then remaining = remaining - 1; return end
      remaining = nil
    elseif c[1] == "WAIT_RAM8" then
      if ram:read(c[2]) ~= c[3] then return end
    end
    spc = spc + 1
  end
end

local function applyPad()
  if not joypad then return end
  for i, b in ipairs(BUTTONS) do
    local f = joypad.fields[FIELD[b]]
    if f then f:set_value((pad >> (i - 1)) & 1) end
  end
end

-- ------------------------------------------------------------ hashing

local function fnvBytes(t, h)
  h = h or BASIS
  for i = 1, #t do h = (h ~ t[i]) * PRIME end
  return h
end

local function itemBytes(it, n)
  local t = {}
  for i = 0, n - 1 do t[i + 1] = it:read(i) & 0xFF end
  return t
end

local function le32(t, v) for i = 0, 3 do t[#t + 1] = (v >> (8 * i)) & 0xFF end end
local function le64(t, v) for i = 0, 7 do t[#t + 1] = (v >> (8 * i)) & 0xFF end end

-- Pen inversion: the PPU's 512 pens (colour index plus emphasis bits 6-8)
-- by RGB. Pens with the same RGB must have the same canonical value
-- (format section 5); the script stops otherwise.
-- The driver nespal (docs/nes-oracles.md section 8) runs the 2C07, whose
-- PPUMASK bit 5 emphasises green and bit 6 red; the device's pens carry
-- the PPUMASK bits as written, the format wants them in colour order
-- (red, green, blue: docs/nes-ppu-spec.md section 18.4).
local palRegion = m.system.name == "nespal"
local BLACK = {}
for _, c in ipairs({0x0D, 0x0E, 0x0F, 0x1D, 0x1E, 0x1F, 0x2E, 0x2F, 0x3E, 0x3F}) do BLACK[c] = true end
local function canon(p)
  local idx, emph = p & 0x3F, p >> 6
  if palRegion then emph = (emph & 4) | ((emph & 1) << 1) | ((emph & 2) >> 1) end
  if idx == 0x30 then idx = 0x20 end
  if BLACK[idx] then return 0x0F end
  if emph == 7 and idx == 0x20 then return 0x10 end
  return idx | (emph << 6)
end
local PEN = {}
local penCollisions = 0
do
  local pal = m.palettes[":ppu"]
  if not pal or pal.entries < 512 then fail("PPU palette with 512 pens not found") end
  for p = 0, 511 do
    local rgb = pal:pen_color(p) & 0xFFFFFF
    local c = canon(p)
    if PEN[rgb] ~= nil and PEN[rgb] ~= c then
      penCollisions = penCollisions + 1
    elseif PEN[rgb] == nil then
      PEN[rgb] = c
    end
  end
end

local function imgBytes()
  local px, w, h = scr:pixels()
  if w ~= 256 or h < 240 then fail(string.format("screen bitmap %dx%d", w, h)) end
  local byte = string.byte
  local t, n = {}, 0
  for y = 0, 239 do
    for x = 0, 255 do
      local o = (y * w + x) * 4 + 1
      local rgb = byte(px, o) | (byte(px, o + 1) << 8) | (byte(px, o + 2) << 16)
      local v = PEN[rgb]
      if v == nil then fail(string.format("pixel %06x is no PPU pen", rgb)) end
      t[n + 1] = v & 0xFF
      t[n + 2] = v >> 8
      n = n + 2
    end
  end
  return t
end

local function fieldBytes()
  local f = {}
  f.cpu = {cpu["A"].value & 0xFF, cpu["X"].value & 0xFF, cpu["Y"].value & 0xFF, cpu["SP"].value & 0xFF,
           (cpu["P"].value & 0xCF) | 0x20}
  f.ram = itemBytes(ram, 0x800)
  local v = {}
  for a = 0x2000, 0x2FFF do v[#v + 1] = vspace:read_u8(a) end
  f.vram = v
  f.oam = itemBytes(spriteram, 256)
  for i = 3, 256, 4 do f.oam[i] = f.oam[i] & 0xE3 end -- attribute bits 2-4 do not exist; MAME stores them
  local p = {}
  for i = 0, 31 do
    local src = i
    if i == 0x10 or i == 0x14 or i == 0x18 or i == 0x1C then src = i - 0x10 end
    p[i + 1] = palram:read(src) & 0x3F
  end
  f.pal = p
  f.prgram = prgram and itemBytes(prgram, prgram.count) or {}
  if prgbank then
    local t = {}
    for i = 0, 3 do le32(t, prgbank:read(i) * 0x2000) end
    f.prgmap = t
  end
  if chrorig then
    local t = {}
    for i = 0, 7 do le32(t, chrorig:read(i)) end
    f.chrmap = t
  end
  if irqCount and irqLatch and irqClear and irqEnable then
    f.mirq = {irqCount:read(0) & 0xFF, irqLatch:read(0) & 0xFF, (irqClear:read(0) ~= 0) and 1 or 0,
              (irqEnable:read(0) ~= 0) and 1 or 0}
  else
    f.mirq = {0, 0, 0, 0}
  end
  f.img = imgBytes()
  return f
end

local FIELDS = {"cpu", "ram", "vram", "oam", "pal", "prgram", "ppu", "prgmap", "chrmap", "mirq", "img", "apu", "snd"}
local RAW = {cpu = true, ppu = true, mirq = true}

local function writeDump(frame, name, t)
  local fh = io.open(string.format("%s/f%06d.%s.bin", dumpDir, frame, name), "wb")
  local parts, chunk = {}, {}
  for i = 1, #t do
    chunk[#chunk + 1] = t[i]
    if #chunk == 4096 then parts[#parts + 1] = string.char(table.unpack(chunk)); chunk = {} end
  end
  if #chunk > 0 then parts[#parts + 1] = string.char(table.unpack(chunk)) end
  fh:write(table.concat(parts))
  fh:close()
end

-- ------------------------------------------------------------ callbacks

out:write(string.format("H nesfh 2 oracle=mame rom=%s fill=00ff region=%s core=mame-0.285 align=-%s\n",
  os.getenv("FH_ROM_ID") or "-", palRegion and "pal" or "ntsc",
  penCollisions > 0 and (" pencollisions=" .. penCollisions) or ""))

local frame, chain, done = 0, BASIS, false
local strobes = 0
local accRunning, accDone, accHung = false, false, false

-- The tap object must stay referenced (here: a global), or the garbage
-- collector removes the tap.
nesfhStrobeTap = pspace:install_write_tap(0x4016, 0x4016, "nesfh_strobe", function(offset, data, mask)
  if not done and (data & 1) == 1 then
    strobes = strobes + 1
    scriptStep()
    applyPad()
  end
end)

-- AccuracyCoin's "run every test" pass (AccuracyCoin.asm,
-- AutomaticallyRunEveryTestInROM) sets zero page $35 to 1 while it runs and
-- clears it before it counts the results and draws the table with the NMI
-- off; the count is complete well within 60 frames after the clear. The
-- run of one page (AutomaticallyRunEveryTestInSuite) uses $34 the same way
-- and counts nothing (the tally is then the old content of $37/$38).
local accEnd = nil
local function accCheck(f)
  if not accMode or accDone then return end
  local rd = function(a) return ram:read(a) end
  if not accRunning then for _, a in ipairs(accSkip) do ram:write(a, 0xFF) end end
  if rd(accFlag) == 1 then
    accRunning = true
    accEnd = nil
    local key = rd(0x14) * 256 + rd(0x16)
    -- Index $FF is the page line (before the first test of a pass).
    if rd(0x16) == 0xFF then return end
    if accHang > 0 and accFlag == 0x34 and hangKey ~= nil and key < hangKey then
      -- The page pass went back to an earlier test: the one that ran last
      -- broke the ROM's loop. (Only in the run of one page: in the run of
      -- every test the ROM sets the page before it resets the index.)
      out:write(string.format("# hang page=%d index=%d frame=%d reason=restart\n", hangKey >> 8, hangKey & 0xFF, f))
      accDone = true
      accHung = true
      return
    end
    if key ~= hangKey then hangKey, hangSince = key, f end
    if accHang > 0 and f - hangSince >= accHang then
      out:write(string.format("# hang page=%d index=%d frame=%d reason=stuck\n", rd(0x14), rd(0x16), f))
      accDone = true
      accHung = true
    end
    return
  end
  if accRunning and accEnd == nil then accEnd = f + 60 end
  if accEnd ~= nil and f >= accEnd then
    accDone = true
    local res = {}
    for a = 0x400, 0x4FF do res[#res + 1] = string.format("%02x", rd(a)) end
    out:write(string.format("T %d tally=%d/%d results=%s\n", f, rd(0x38), rd(0x37), table.concat(res)))
  end
end

-- blargg's result protocol: $6001-$6003 = DE B0 61 marks it; $6000 is
-- $80 while the test runs, $81 when it wants a reset (pressed 6 frames
-- later here, at most once in 300 frames), else the result code; text
-- from $6004, zero-terminated.
local blarggDone, resetAt, resetHold = false, nil, -1
local function blarggCheck(f)
  if not blarggMode or blarggDone then return end
  local rd = function(a) return pspace:read_u8(a) end
  if rd(0x6001) ~= 0xDE or rd(0x6002) ~= 0xB0 or rd(0x6003) ~= 0x61 then return end
  local st = rd(0x6000)
  if st == 0x81 then
    -- After a reset the ROM needs time before it updates $6000: no second
    -- reset within 300 frames.
    if f < resetHold then return end
    if resetAt == nil then resetAt = f + 6 end
    if f >= resetAt then resetAt = nil; resetHold = f + 300; manager.machine:soft_reset() end
    return
  end
  if st >= 0x80 then return end
  local txt = {}
  for a = 0x6004, 0x60FF do
    local v = rd(a)
    if v == 0 then break end
    txt[#txt + 1] = string.format("%02x", v)
  end
  out:write(string.format("R %d status=%02x text=%s\n", f, st, #txt > 0 and table.concat(txt) or "-"))
  blarggDone = true
end

local function screenLine(f)
  local t = {}
  for a = 0x2000, 0x2FFF do t[#t + 1] = string.format("%02x", vspace:read_u8(a)) end
  out:write(string.format("N %d nt=%s\n", f, table.concat(t)))
end

emu.register_frame_done(function()
  if done then return end
  frame = frame + 1
  if frame == injFrame then ram:write(injAddr, ram:read(injAddr) ~ injXor) end
  local f = fieldBytes()
  local dump = dumpDir and (dumpAt[frame] or (dumpEvery > 0 and frame % dumpEvery == 0))
  local parts = {string.format("F %d inp=%d cyc=%d dot=- pc=%04x", frame, strobes, totalcycles:read(0),
                               cpu["PC"].value & 0xFFFF)}
  local cb = {}
  le64(cb, chain)
  for _, name in ipairs(FIELDS) do
    local t = f[name]
    if t == nil then
      le64(cb, 0)
      parts[#parts + 1] = name .. "=-"
    else
      local h = fnvBytes(t)
      le64(cb, h)
      if RAW[name] then
        local hex = {}
        for i = 1, #t do hex[i] = string.format("%02x", t[i]) end
        parts[#parts + 1] = name .. "=" .. table.concat(hex)
      else
        parts[#parts + 1] = string.format("%s=%016x", name, h)
      end
      if dump then writeDump(frame, name, t) end
    end
  end
  chain = fnvBytes(cb)
  parts[#parts + 1] = string.format("all=%016x", chain)
  out:write(table.concat(parts, " ") .. "\n")
  accCheck(frame)
  blarggCheck(frame)
  local last = frame >= maxFrames or (stopAfterT and (accDone or blarggDone))
  if last and screenMode then screenLine(frame) end
  if last then
    done = true
    out:close()
    m:exit()
  end
end)
