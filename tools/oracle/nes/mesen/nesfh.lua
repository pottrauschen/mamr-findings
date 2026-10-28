-- NES hash lines (docs/nes-oracle-format.md, version 2) for MesenCE 2.2.1
-- in test-runner mode. Start it through run_mesen.sh, which sets the
-- determinism switches and installs the index palette. Configuration
-- through the environment:
--   FH_OUT         output file (required)
--   FH_FRAMES      number of F lines (default 600)
--   FH_INPUT       input script file (format section 7), optional
--   FH_DUMP_DIR    directory for canonical field dumps
--   FH_DUMP_AT     "F,F,..." frames to dump; FH_DUMP_EVERY  K
--   FH_INJECT      "F:ADDR:XOR" fault injection into the internal RAM (hex)
--   FH_ROM_ID      value of the header key rom=
--   FH_FILL        value of the header key fill= (run_mesen.sh sets it)
--   FH_ACC         "1": write the T line of AccuracyCoin (format section 8)
--   FH_STOP_AFTER_T "1": end the run after the T line
--   FH_ACC_FLAG     zero page address (hex) of the "running" flag: 35 (default)
--                   for the run of every test, 34 for the run of one page
--   FH_ACC_HANG     K: stop with a "# hang" comment when the running test
--                   (page $14, index $16) has not changed for K frames, or
--                   when the run of one page goes back to an earlier test
--   FH_BLARGG       "1": watch the result protocol at $6000 (format section 9):
--                   R line when a result is there, a reset when one is
--                   requested; with FH_STOP_AFTER_T the run ends at the R line
--   FH_TRACE_PC     "A,A-B" (hex): a comment line "# pc A cyc N" each time an
--                   instruction at one of these addresses starts (debugging;
--                   MAMR's nes_headless --trace-pc writes the same lines)
--   FH_SCREEN       "1": after the last F line an N line with $2000-$2FFF
--   FH_ACC_SKIP     "ADDR,ADDR" (hex): result bytes set to $FF before the run,
--                   which marks those tests skipped as the B button does
--
-- Sampling point: the first instruction boundary after the endFrame event,
-- which MesenCE raises when its PPU starts scanline 240, dot 0
-- (NesPpu::ProcessScanlineFirstCycle). The exec callback of the next
-- opcode fetch is that boundary; an IRQ or NMI taken at the boundary has
-- been entered by then.

local M = emu.memType
local NES = emu.cpuType.nes
local PRIME = 0x100000001B3
local BASIS = -3750763034362895579 -- 0xcbf29ce484222325

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
local injFrame, injAddr, injXor = -1, 0, 0
do
  local f, a, x = (os.getenv("FH_INJECT") or ""):match("^(%d+):(%x+):(%x+)$")
  if f then injFrame, injAddr, injXor = tonumber(f), tonumber(a, 16), tonumber(x, 16) end
end

local function fail(msg)
  out:write("# error: " .. msg .. "\n")
  out:close()
  emu.stop(3)
  error(msg)
end

-- ------------------------------------------------------------ input script

local BUTTONS = {"A", "B", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT"}
local MESEN_KEY = {A = "a", B = "b", SELECT = "select", START = "start", UP = "up", DOWN = "down",
                   LEFT = "left", RIGHT = "right"}
local BIT = {}
for i, b in ipairs(BUTTONS) do BIT[b] = i - 1 end

local function parseHex(s)
  s = s:gsub("^%$", ""):gsub("^0[xX]", "")
  if not s:match("^%x+$") then return nil end
  return tonumber(s, 16)
end

local cmds = {}
local inputPath = os.getenv("FH_INPUT")
if inputPath and inputPath ~= "" then
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
        if #tok ~= 3 or not a or not v or v > 255 then fail("line " .. n .. ": bad WAIT_RAM8") end
        if a > 0x7FF then fail("line " .. n .. ": RAM address out of range") end
        cmds[#cmds + 1] = {op, a, v}
      else
        fail("line " .. n .. ": unknown command")
      end
    end
  end
  fh:close()
end

local spc, remaining, pad = 1, nil, 0
-- One step of the script per controller strobe.
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
      if emu.read(c[2], M.nesInternalRam, false) ~= c[3] then return end
    end
    spc = spc + 1
  end
end

local function applyPad()
  local t = {}
  for i, b in ipairs(BUTTONS) do t[MESEN_KEY[b]] = (pad >> (i - 1)) & 1 == 1 end
  emu.setInput(t, 0)
end

-- ------------------------------------------------------------ hashing

local function fnvBytes(t, h)
  h = h or BASIS
  for i = 1, #t do h = (h ~ t[i]) * PRIME end
  return h
end

local function memBytes(mt, first, size)
  local t, rd = {}, emu.read
  for a = 0, size - 1 do t[a + 1] = rd(first + a, mt, false) end
  return t
end

local function le16(t, v) t[#t + 1] = v & 0xFF; t[#t + 1] = (v >> 8) & 0xFF end
local function le32(t, v) for i = 0, 3 do t[#t + 1] = (v >> (8 * i)) & 0xFF end end
local function le64(t, v) for i = 0, 7 do t[#t + 1] = (v >> (8 * i)) & 0xFF end end
local function b(v) return v and 1 or 0 end

-- The last bytes written to $2000 and $2001 (MesenCE keeps PPUCTRL only as
-- decoded flags, without bit 6). Writes during the first frame count: the
-- run uses MesenCE's default RestrictPpuAccessOnFirstFrame = false.
local ctrlShadow, maskShadow = 0, 0
emu.addMemoryCallback(function(address, value)
  local r = address & 7
  if r == 0 then ctrlShadow = value & 0xFF elseif r == 1 then maskShadow = value & 0xFF end
end, emu.callbackType.write, 0x2000, 0x3FFF, NES, M.nesMemory)

local function ppuBytes(s)
  local t = {ctrlShadow & 0xFC, maskShadow,
             (b(s["ppu.statusFlags.verticalBlank"]) << 7) | (b(s["ppu.statusFlags.sprite0Hit"]) << 6)
             | (b(s["ppu.statusFlags.spriteOverflow"]) << 5),
             s["ppu.spriteRamAddr"] & 0xFF}
  le16(t, s["ppu.videoRamAddr"] & 0x7FFF)
  le16(t, s["ppu.tmpVideoRamAddr"] & 0x7FFF)
  t[#t + 1] = s["ppu.xScroll"] & 7
  t[#t + 1] = b(s["ppu.writeToggle"])
  t[#t + 1] = s["ppu.memoryReadBuffer"] & 0xFF
  return t
end

local function palBytes()
  local t = {}
  for i = 0, 31 do
    local src = i
    if i == 0x10 or i == 0x14 or i == 0x18 or i == 0x1C then src = i - 0x10 end
    t[i + 1] = emu.read(src, M.nesPaletteRam, false) & 0x3F
  end
  return t
end

-- Byte offset of the window at addr in its source memory, or $FFFFFFFF.
local function mapOffset(addr, mt)
  local r = emu.convertAddress(addr, mt)
  if r == nil or r.address == nil or r.address < 0 then return 0xFFFFFFFF end
  return r.address
end

local function prgmapBytes()
  local t = {}
  for i = 0, 3 do le32(t, mapOffset(0x8000 + i * 0x2000, M.nesMemory)) end
  return t
end

local function chrmapBytes()
  local t = {}
  for i = 0, 7 do le32(t, mapOffset(i * 0x400, M.nesPpuMemory)) end
  return t
end

-- MMC3 (MesenCE MMC3::Serialize): counter, latch, reload flag, enable.
local function mirqBytes(s)
  local c = s["mapper.irqCounter"]
  if c == nil then return {0, 0, 0, 0} end
  return {c & 0xFF, s["mapper.irqReloadValue"] & 0xFF, b(s["mapper.irqReload"]), b(s["mapper.irqEnabled"])}
end

-- Canonical pixel (format section 5). The palette run_mesen.sh installs
-- maps pen p (colour index plus emphasis bits 6-8) to the RGB value p.
local BLACK = {}
for _, c in ipairs({0x0D, 0x0E, 0x0F, 0x1D, 0x1E, 0x1F, 0x2E, 0x2F, 0x3E, 0x3F}) do BLACK[c] = true end
local CANON = {}
for p = 0, 511 do
  local idx, emph = p & 0x3F, p >> 6
  if idx == 0x30 then idx = 0x20 end
  local v
  if BLACK[idx] then v = 0x0F
  elseif emph == 7 and idx == 0x20 then v = 0x10
  else v = idx | (emph << 6) end
  CANON[p] = v
end

local function imgBytes()
  local buf = emu.getScreenBuffer()
  local size = emu.getScreenSize()
  if size.width ~= 256 or size.height ~= 240 then fail("screen is not 256x240") end
  local t = {}
  local n = 0
  for i = 1, 61440 do
    local p = buf[i]
    if p > 511 then fail(string.format("pixel %06x is not an index (palette not installed)", p)) end
    local v = CANON[p]
    t[n + 1] = v & 0xFF
    t[n + 2] = v >> 8
    n = n + 2
  end
  return t
end

local function prgramBytes()
  local mt = M.nesSaveRam
  local size = emu.getMemorySize(mt)
  if size == 0 then
    mt = M.nesWorkRam
    size = emu.getMemorySize(mt)
  end
  return memBytes(mt, 0, size)
end

-- The APU channel state (format section 3, field apu) from MesenCE's
-- state keys (apu.square1 ..., read through emu.getState). MesenCE keeps
-- the noise and DMC periods in CPU cycles minus 1 and the DMC sample
-- address and length as the values the registers select, and the sweep
-- period as P + 1 (0 before the first $4001 write); the inverse mappings
-- below give the register values back. The sweep divider is not part of
-- the field: MesenCE's counter runs free before the first $4001 write. snd (the samples) is
-- not exposed to Lua and written as "-".
local NOISE_PERIOD = {4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068}
local DMC_PERIOD = {428, 380, 340, 320, 286, 254, 226, 214, 190, 160, 142, 128, 106, 84, 72, 54}
local function indexOf(tab, v)
  for i, x in ipairs(tab) do if x == v then return i - 1 end end
  return 0xFF
end

local function apuBytes(s)
  local t = {}
  for _, ch in ipairs({"apu.square1.", "apu.square2."}) do
    local e = ch .. "envelope."
    t[#t + 1] = s[ch .. "duty"] & 3
    t[#t + 1] = s[e .. "volume"] & 15
    t[#t + 1] = b(s[e .. "constantVolume"]) | (b(s[e .. "lengthCounter.halt"]) << 1) | (b(s[e .. "start"]) << 2)
    t[#t + 1] = s[e .. "divider"] & 0xFF
    t[#t + 1] = s[e .. "counter"] & 0xFF
    t[#t + 1] = s[e .. "lengthCounter.counter"] & 0xFF
    t[#t + 1] = (b(s[ch .. "sweepEnabled"]) << 7) | (math.max(s[ch .. "sweepPeriod"] - 1, 0) & 7) << 4
                | (b(s[ch .. "sweepNegate"]) << 3) | (s[ch .. "sweepShift"] & 7)
    t[#t + 1] = b(s[ch .. "reloadSweep"])
    le16(t, s[ch .. "realPeriod"] & 0x7FF)
  end
  t[#t + 1] = s["apu.triangle.linearCounter"] & 0x7F
  t[#t + 1] = s["apu.triangle.linearCounterReload"] & 0x7F
  t[#t + 1] = b(s["apu.triangle.linearControlFlag"]) | (b(s["apu.triangle.linearReloadFlag"]) << 1)
  t[#t + 1] = s["apu.triangle.lengthCounter.counter"] & 0xFF
  le16(t, s["apu.triangle.timer.period"] & 0x7FF)
  local e = "apu.noise.envelope."
  t[#t + 1] = s[e .. "volume"] & 15
  t[#t + 1] = b(s[e .. "constantVolume"]) | (b(s[e .. "lengthCounter.halt"]) << 1) | (b(s[e .. "start"]) << 2)
  t[#t + 1] = s[e .. "divider"] & 0xFF
  t[#t + 1] = s[e .. "counter"] & 0xFF
  t[#t + 1] = s[e .. "lengthCounter.counter"] & 0xFF
  t[#t + 1] = (b(s["apu.noise.modeFlag"]) << 7) | indexOf(NOISE_PERIOD, s["apu.noise.timer.period"] + 1)
  t[#t + 1] = (b(s["apu.dmc.irqEnabled"]) << 7) | (b(s["apu.dmc.loopFlag"]) << 6)
              | indexOf(DMC_PERIOD, s["apu.dmc.timer.period"] + 1)
  t[#t + 1] = s["apu.dmc.outputLevel"] & 0x7F
  t[#t + 1] = ((s["apu.dmc.sampleAddr"] - 0xC000) // 64) & 0xFF
  t[#t + 1] = ((s["apu.dmc.sampleLength"] - 1) // 16) & 0xFF
  le16(t, (s["apu.dmc.currentAddr"] & 0xFFFF) | 0x8000)
  le16(t, s["apu.dmc.bytesRemaining"] & 0xFFFF)
  local full = not s["apu.dmc.bufferEmpty"]
  t[#t + 1] = b(full)
  t[#t + 1] = full and (s["apu.dmc.readBuffer"] & 0xFF) or 0
  t[#t + 1] = b(s["apu.square1.envelope.lengthCounter.enabled"]) | (b(s["apu.square2.envelope.lengthCounter.enabled"]) << 1)
              | (b(s["apu.triangle.lengthCounter.enabled"]) << 2) | (b(s["apu.noise.envelope.lengthCounter.enabled"]) << 3)
  t[#t + 1] = ((s["apu.frameCounter.stepMode"] == 1) and 0x80 or 0) | (b(s["apu.frameCounter.inhibitIRQ"]) << 6)
  return t
end

local function fieldBytes(s)
  local f = {}
  f.cpu = {s["cpu.a"] & 0xFF, s["cpu.x"] & 0xFF, s["cpu.y"] & 0xFF, s["cpu.sp"] & 0xFF,
           (s["cpu.ps"] & 0xCF) | 0x20}
  f.ram = memBytes(M.nesInternalRam, 0, 0x800)
  f.vram = memBytes(M.nesPpuMemory, 0x2000, 0x1000)
  f.oam = memBytes(M.nesSpriteRam, 0, 256)
  for i = 3, 256, 4 do f.oam[i] = f.oam[i] & 0xE3 end -- attribute bits 2-4 do not exist
  f.pal = palBytes()
  f.prgram = prgramBytes()
  f.ppu = ppuBytes(s)
  f.prgmap = prgmapBytes()
  f.chrmap = chrmapBytes()
  f.mirq = mirqBytes(s)
  f.img = imgBytes()
  f.apu = apuBytes(s)
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

local frame, chain, done = 0, BASIS, false
local strobes, strobesAtWindow = 0, 0
local accRunning, accDone, accHung = false, false, false

-- Header. align is MesenCE's PPU offset in master clocks against the CPU
-- divider (NesCpu::Reset: 1 unless RandomizeCpuPpuAlignment is set).
-- dotClocks: master clocks per PPU dot, 4 on NTSC, 5 on PAL
-- (docs/nes-hardware-spec.md section 7.1).
local dotClocks = 4
do
  local st = emu.getState()
  local region = ({Ntsc = "ntsc", Pal = "pal"})[st.region]
  if region == nil then fail("unsupported region " .. tostring(st.region)) end
  if region == "pal" then
    -- The RP2A07's tables (docs/nes-hardware-spec.md section 7.3).
    dotClocks = 5
    NOISE_PERIOD = {4, 8, 14, 30, 60, 88, 118, 148, 188, 236, 354, 472, 708, 944, 1890, 3778}
    DMC_PERIOD = {398, 354, 316, 298, 276, 236, 210, 198, 176, 148, 132, 118, 98, 78, 66, 50}
  end
  out:write(string.format("H nesfh 2 oracle=mesence rom=%s fill=%s region=%s core=mesence-2.2.1 align=1\n",
    os.getenv("FH_ROM_ID") or "-", os.getenv("FH_FILL") or "00", region))
end

-- Controller strobe: a write to $4016 with bit 0 set. The script steps
-- before the write reaches the controller, so the latched state is the
-- new one.
emu.addMemoryCallback(function(address, value)
  if done or (value & 1) == 0 then return end
  strobes = strobes + 1
  scriptStep()
  applyPad()
end, emu.callbackType.write, 0x4016, 0x4016, NES, M.nesMemory)

-- MesenCE clears the controller state once per frame (scanline 241) and
-- raises inputPolled; the held buttons are set again there.
emu.addEventCallback(function() applyPad() end, emu.eventType.inputPolled)

-- AccuracyCoin's "run every test" pass (AccuracyCoin.asm,
-- AutomaticallyRunEveryTestInROM) sets zero page $35 to 1 while it runs and
-- clears it before it counts the results and draws the table with the NMI
-- off; the count is complete well within 60 frames after the clear. The
-- run of one page (AutomaticallyRunEveryTestInSuite) uses $34 the same way
-- and counts nothing (the tally is then the old content of $37/$38).
local accEnd = nil
local function accCheck(f)
  if not accMode or accDone then return end
  local rd = function(a) return emu.read(a, M.nesInternalRam, false) end
  if not accRunning then for _, a in ipairs(accSkip) do emu.write(a, 0xFF, M.nesInternalRam) end end
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
  local rd = function(a) return emu.read(a, M.nesMemory, false) end
  if rd(0x6001) ~= 0xDE or rd(0x6002) ~= 0xB0 or rd(0x6003) ~= 0x61 then return end
  local st = rd(0x6000)
  if st == 0x81 then
    -- After a reset the ROM needs time before it updates $6000: no second
    -- reset within 300 frames.
    if f < resetHold then return end
    if resetAt == nil then resetAt = f + 6 end
    if f >= resetAt then resetAt = nil; resetHold = f + 300; emu.reset() end
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
  for a = 0x2000, 0x2FFF do t[#t + 1] = string.format("%02x", emu.read(a, M.nesPpuMemory, false)) end
  out:write(string.format("N %d nt=%s\n", f, table.concat(t)))
end

local function sample()
  frame = frame + 1
  if frame == injFrame then
    local v = emu.read(injAddr, M.nesInternalRam, false)
    emu.write(injAddr, v ~ injXor, M.nesInternalRam)
  end
  local s = emu.getState()
  local f = fieldBytes(s)
  local dump = dumpDir and (dumpAt[frame] or (dumpEvery > 0 and frame % dumpEvery == 0))
  local parts = {string.format("F %d inp=%d cyc=%d dot=%d pc=%04x", frame, strobesAtWindow, s["cpu.cycleCount"],
                               s["ppu.masterClock"] // dotClocks, s["cpu.pc"] & 0xFFFF)}
  local cb = {}
  le64(cb, chain)
  for _, name in ipairs(FIELDS) do
    local t = f[name]
    if t == nil then
      le64(cb, 0)
      parts[#parts + 1] = name .. "=-"
      goto continue
    end
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
    ::continue::
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
    emu.stop(0)
  end
end

local tracePc = os.getenv("FH_TRACE_PC")
if tracePc and tracePc ~= "" then
  for a in string.gmatch(tracePc, "[^,]+") do
    local lo, hi = string.match(a, "^(%x+)-(%x+)$")
    lo = tonumber(lo or a, 16)
    hi = tonumber(hi or a, 16)
    emu.addMemoryCallback(function(address)
      if done then return end
      local st = emu.getState()
      out:write(string.format("# pc %04x cyc %d\n", address & 0xFFFF, st["cpu.cycleCount"]))
    end, emu.callbackType.exec, lo, hi, NES, M.nesMemory)
  end
end

local boundaryRef = nil
local function onBoundary()
  if boundaryRef == nil then return end
  emu.removeMemoryCallback(boundaryRef, emu.callbackType.exec, 0, 0xFFFF, NES, M.nesMemory)
  boundaryRef = nil
  if not done then sample() end
end

emu.addEventCallback(function()
  if done then return end
  strobesAtWindow = strobes
  if boundaryRef == nil then
    boundaryRef = emu.addMemoryCallback(onBoundary, emu.callbackType.exec, 0, 0xFFFF, NES, M.nesMemory)
  end
end, emu.eventType.endFrame)
