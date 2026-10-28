-- SNES hash lines (docs/snes-oracle-format.md, version 4) for MesenCE
-- 2.2.1 in test-runner mode. Start it through run_mesen.sh, which sets the
-- determinism switches. Configuration through the environment:
--   FH_OUT         output file (required)
--   FH_FRAMES      number of F lines (default 600)
--   FH_INPUT       input script file (docs/snes-oracle-input-script.md), optional
--   FH_ANCHORS     "PC[:TAG],PC[:TAG]" (hex PB:PC), optional
--   FH_PORTS       "1" for P lines
--   FH_DUMP_DIR    directory for canonical field dumps
--   FH_DUMP_AT     "F,F,..." frames to dump; FH_DUMP_EVERY  K
--   FH_INJECT      "F:ADDR:XOR" fault injection (hex ADDR and XOR)
--   FH_ROM_ID      value of the header key rom=
--   FH_TRACE_JOY   "1": after each F line a comment "# joy1=XXXX" with the
--                  last auto-read word ($4218/$4219)
--   FH_FILL        value of the header key fill= (run_mesen.sh sets it
--                  from MESEN_FILL)
--   FH_LINES       "1": after each F line an L line with one hash per
--                  picture row
--
-- Sampling point: the first instruction boundary at or after the endFrame
-- event, which MesenCE raises at the start of scanline 225 (240 with
-- overscan); the same point as aresref's frame hook.

local M = emu.memType
local PRIME = 0x100000001B3
local BASIS = -3750763034362895579 -- 0xcbf29ce484222325

local outPath = os.getenv("FH_OUT")
local out = assert(io.open(outPath, "w"))
local maxFrames = tonumber(os.getenv("FH_FRAMES") or "600")
local ports = os.getenv("FH_PORTS") == "1"
local traceJoy = os.getenv("FH_TRACE_JOY") == "1"
local dumpDir = os.getenv("FH_DUMP_DIR")
local dumpEvery = tonumber(os.getenv("FH_DUMP_EVERY") or "0")
local dumpAt = {}
for f in (os.getenv("FH_DUMP_AT") or ""):gmatch("%d+") do dumpAt[tonumber(f)] = true end
local injFrame, injAddr, injXor = -1, 0, 0
do
  local f, a, x = (os.getenv("FH_INJECT") or ""):match("^(%d+):(%x+):(%x+)$")
  if f then injFrame, injAddr, injXor = tonumber(f), tonumber(a, 16), tonumber(x, 16) end
end

-- ------------------------------------------------------------ input script

local BUTTONS = {"B", "Y", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT", "A", "X", "L", "R"}
local MESEN_KEY = {B = "b", Y = "y", SELECT = "select", START = "start", UP = "up", DOWN = "down",
                   LEFT = "left", RIGHT = "right", A = "a", X = "x", L = "l", R = "r"}
local BIT = {}
for i, b in ipairs(BUTTONS) do BIT[b] = 16 - i end

local function fail(msg)
  out:write("# error: " .. msg .. "\n")
  out:close()
  emu.stop(3)
  error(msg)
end

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
        if #tok ~= 2 or not c or c < 1 or math.type(c) ~= "integer" then fail("line " .. n .. ": WAIT needs a count >= 1") end
        cmds[#cmds + 1] = {op, c}
      elseif op == "WAIT_RAM8" then
        local a, v = parseHex(tok[2] or ""), parseHex(tok[3] or "")
        if #tok ~= 3 or not a or not v or v > 255 then fail("line " .. n .. ": bad WAIT_RAM8") end
        if a >= 0x7E0000 and a <= 0x7FFFFF then a = a - 0x7E0000
        elseif a > 0x1FFF then fail("line " .. n .. ": WRAM address out of range") end
        cmds[#cmds + 1] = {op, a, v}
      else
        fail("line " .. n .. ": unknown command")
      end
    end
  end
  fh:close()
end

local spc, remaining, pad = 1, nil, 0
local function scriptRead()
  while spc <= #cmds do
    local c = cmds[spc]
    if c[1] == "HOLD" then pad = pad | c[2]
    elseif c[1] == "RELEASE" then pad = pad & ~c[2]
    elseif c[1] == "WAIT" then
      if remaining == nil then remaining = c[2] end
      if remaining > 0 then remaining = remaining - 1; return end
      remaining = nil
    elseif c[1] == "WAIT_RAM8" then
      if emu.read(c[2], M.snesWorkRam, false) ~= c[3] then return end
    end
    spc = spc + 1
  end
end

local function padTable()
  local t = {}
  for i, b in ipairs(BUTTONS) do t[MESEN_KEY[b]] = (pad >> (16 - i)) & 1 == 1 end
  return t
end

-- ------------------------------------------------------------ hashing

local function fnvBytes(t, h)
  h = h or BASIS
  for i = 1, #t do h = (h ~ t[i]) * PRIME end
  return h
end

-- Canonical bytes of a memory region, as a Lua array of integers.
local function memBytes(mt, size, mask16hi)
  local t, rd = {}, emu.read
  for a = 0, size - 1 do t[a + 1] = rd(a, mt, false) end
  if mask16hi then for i = 2, #t, 2 do t[i] = t[i] & 0x7F end end
  return t
end

local function le16(t, v) t[#t + 1] = v & 0xFF; t[#t + 1] = (v >> 8) & 0xFF end
local function le64(t, v) for i = 0, 7 do t[#t + 1] = (v >> (8 * i)) & 0xFF end end
local function b(v) return v and 1 or 0 end

local shadow, prev = {}, {}
for r = 0, 0x33 do shadow[r] = 0; prev[r] = 0 end

local function ppuBytes(s)
  local t = {}
  for r = 0, 0x33 do t[#t + 1] = shadow[r] end
  for r = 0x0D, 0x14 do t[#t + 1] = prev[r] end
  for r = 0x1B, 0x20 do t[#t + 1] = prev[r] end
  le16(t, s["ppu.vramAddress"] & 0x7FFF); le16(t, s["ppu.vramReadBuffer"])
  t[#t + 1] = s["ppu.oamWriteBuffer"] & 0xFF
  t[#t + 1] = s["ppu.cgramAddress"] & 0xFF
  t[#t + 1] = b(s["ppu.cgramAddressLatch"])
  t[#t + 1] = s["ppu.cgramWriteBuffer"] & 0xFF
  t[#t + 1] = s["ppu.hvScrollLatchValue"] & 0xFF
  t[#t + 1] = s["ppu.hScrollLatchValue"] & 0x07
  t[#t + 1] = s["ppu.mode7.valueLatch"] & 0xFF
  return t
end

local function imgBytes(s)
  local buf = emu.getScreenBuffer()
  local size = emu.getScreenSize()
  local w = size.width
  -- MesenCE's 239-row buffer holds scanline v in row v - 1 with overscan,
  -- else in row v + 6 (rows 0-6 and 231-238 are blanked); hi-res and
  -- interlaced frames are 512 x 478 with every row doubled.
  local overscan = s["ppu.overscanMode"]
  local height = overscan and 239 or 224
  local first = overscan and 0 or 7
  local rowStep = (w == 512) and 2 or 1
  local rows = {}
  local hires = false
  for y = 0, height - 1 do
    local base = (first + y) * rowStep * w
    local row = {}
    for x = 0, w - 1 do
      local p = buf[base + x + 1]
      row[x + 1] = ((p >> 19) & 0x1F) | (((p >> 11) & 0x1F) << 5) | (((p >> 3) & 0x1F) << 10)
    end
    if w == 512 and not hires then
      for x = 1, 511, 2 do if row[x] ~= row[x + 1] then hires = true; break end end
    end
    rows[y + 1] = row
  end
  local t = {}
  for y = 1, height do
    local row = rows[y]
    if hires then
      for x = 1, 512 do le16(t, row[x]) end
    elseif w == 512 then
      for x = 2, 512, 2 do le16(t, row[x]) end
    else
      for x = 1, 256 do le16(t, row[x]) end
    end
  end
  return t, string.format("%dx%d", hires and 512 or 256, height)
end

local function fieldBytes(s)
  local f = {}
  local t = {}
  le16(t, s["cpu.a"]); le16(t, s["cpu.x"]); le16(t, s["cpu.y"]); le16(t, s["cpu.sp"]); le16(t, s["cpu.d"])
  t[#t + 1] = s["cpu.dbr"]; t[#t + 1] = s["cpu.k"]; t[#t + 1] = s["cpu.ps"]; t[#t + 1] = b(s["cpu.emulationMode"])
  f.cpu = t
  t = {s["spc.a"], s["spc.x"], s["spc.y"], s["spc.sp"], s["spc.ps"]}
  t[#t + 1] = (s["spc.romEnabled"] and 0x80 or 0) | b(s["spc.timer0.enabled"]) | (b(s["spc.timer1.enabled"]) << 1)
              | (b(s["spc.timer2.enabled"]) << 2)
  t[#t + 1] = s["spc.dspReg"]
  t[#t + 1] = s["spc.timer0.target"]; t[#t + 1] = s["spc.timer1.target"]; t[#t + 1] = s["spc.timer2.target"]
  t[#t + 1] = s["spc.timer0.output"] & 0x0F; t[#t + 1] = s["spc.timer1.output"] & 0x0F
  t[#t + 1] = s["spc.timer2.output"] & 0x0F
  f.smp = t
  f.apuio = {s["spc.cpuRegs[0]"], s["spc.cpuRegs[1]"], s["spc.cpuRegs[2]"], s["spc.cpuRegs[3]"],
             s["spc.outputReg[0]"], s["spc.outputReg[1]"], s["spc.outputReg[2]"], s["spc.outputReg[3]"]}
  f.wram = memBytes(M.snesWorkRam, 0x20000)
  f.vram = memBytes(M.snesVideoRam, 0x10000)
  f.oam = memBytes(M.snesSpriteRam, 544)
  f.cgram = memBytes(M.snesCgRam, 512, true)
  f.ppu = ppuBytes(s)
  f.aram = memBytes(M.spcRam, 0x10000)
  f.dsp = memBytes(M.spcDspRegisters, 128)
  local imgsz
  f.img, imgsz = imgBytes(s)
  f.sram = memBytes(M.snesSaveRam, emu.getMemorySize(M.snesSaveRam))
  return f, imgsz
end

local FIELDS = {"cpu", "smp", "apuio", "wram", "vram", "oam", "cgram", "ppu", "aram", "dsp", "img", "sram"}
local RAW = {cpu = true, smp = true, apuio = true}

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

local frame, reads, chain, done = 0, 0, BASIS, false
local lines = os.getenv("FH_LINES") == "1"

-- Header: region from the master clock rate, APU clock from the SPC clock
-- ratio (32040 Hz = clk=meas, 32000 Hz = clk=nom).
do
  local st = emu.getState()
  local rate = st.clockRate
  local region = (rate < 21400000) and "pal" or "ntsc"
  local spcRate = st["spc.clockRatio"] * rate / 64
  local clk = (math.abs(spcRate - 32040) < 1) and "meas" or ((math.abs(spcRate - 32000) < 1) and "nom"
              or string.format("%.0f", spcRate))
  out:write(string.format("H snesfh 4 oracle=mesence rom=%s fill=%s region=%s clk=%s core=mesence-2.2.1\n",
    os.getenv("FH_ROM_ID") or "-", os.getenv("FH_FILL") or "00", region, clk))
end

-- Cartridge save RAM without a save file starts as $FF in every fill
-- (format section 6); MesenCE fills it like the other RAM, so set it here,
-- before the first instruction. run_mesen.sh removes saved games first.
for a = 0, emu.getMemorySize(M.snesSaveRam) - 1 do emu.write(a, 0xFF, M.snesSaveRam) end

local function onPpuWrite(address, value)
  local r = address & 0xFF
  if r <= 0x33 then prev[r] = shadow[r]; shadow[r] = value & 0xFF end
end
for bank = 0, 0xBF do
  if bank < 0x40 or bank >= 0x80 then
    local base = bank << 16
    emu.addMemoryCallback(onPpuWrite, emu.callbackType.write, base + 0x2100, base + 0x2133,
                          emu.cpuType.snes, M.snesMemory)
  end
end

if ports then
  local function onCpuPort(address, value)
    if done then return end
    out:write(string.format("P %d c t=%d port=%d val=%02x\n", frame + 1, emu.getState().masterClock,
                            address & 3, value & 0xFF))
  end
  for bank = 0, 0xBF do
    if bank < 0x40 or bank >= 0x80 then
      local base = bank << 16
      emu.addMemoryCallback(onCpuPort, emu.callbackType.write, base + 0x2140, base + 0x217F,
                            emu.cpuType.snes, M.snesMemory)
    end
  end
  -- spc.cycle advances by two per SMP cycle (observed against aresref);
  -- t is in SMP cycles.
  emu.addMemoryCallback(function(address, value)
    if done then return end
    out:write(string.format("P %d s t=%d port=%d val=%02x\n", frame + 1, emu.getState()["spc.cycle"] // 2,
                            address - 0xF4, value & 0xFF))
  end, emu.callbackType.write, 0xF4, 0xF7, emu.cpuType.spc, M.spcMemory)
end

-- anc counts auto-joypad reads that have begun. MesenCE decides about the
-- read of a frame when it finishes the frame (inputPolled, after the
-- endFrame event and before the next instruction); the read itself starts
-- at internalRegisters.autoReadClockStart, which MesenCE sets right after
-- inputPolled. Until it is set it still holds the previous frame's value,
-- older than the frame's endFrame clock.
local readPending, pendingWindow = false, 0
local windowClock = 0
-- anc of the F line: reads begun before the sampling window opened, i.e.
-- the reads counted up to the endFrame event
local readsAtWindow = 0
local function ancAt(st)
  if readPending then
    local start = st["internalRegisters.autoReadClockStart"]
    if start < pendingWindow or st.masterClock < start then return reads - 1 end
    readPending = false
  end
  return reads
end

for item in (os.getenv("FH_ANCHORS") or ""):gmatch("[^,]+") do
  local pcs, tag = item:match("^(%x+):?(.*)$")
  local pc = tonumber(pcs, 16)
  if tag == "" then tag = "-" end
  local last = nil
  emu.addMemoryCallback(function()
    if done then return end
    local st = emu.getState()
    local now = st.masterClock
    out:write(string.format("A %d pc=%06x mclk=%d d=%s anc=%d tag=%s\n", frame + 1, pc, now,
                            last and tostring(now - last) or "-", ancAt(st), tag))
    last = now
  end, emu.callbackType.exec, pc, pc, emu.cpuType.snes, M.snesMemory)
end

emu.addEventCallback(function()
  if not done and emu.getState()["internalRegisters.enableAutoJoypadRead"] then
    reads = reads + 1
    readPending, pendingWindow = true, windowClock
    scriptRead()
  end
  emu.setInput(padTable(), 0)
end, emu.eventType.inputPolled)

-- The sample: called from the exec callback of the first instruction after
-- the endFrame event, i.e. at the first instruction boundary (before the
-- opcode fetch) at or after the start of scanline 225 (240 with overscan).
local function sample()
  frame = frame + 1
  if frame == injFrame then
    local v = emu.read(injAddr, M.snesWorkRam, false)
    emu.write(injAddr, v ~ injXor, M.snesWorkRam)
  end
  local s = emu.getState()
  local f, imgsz = fieldBytes(s)
  local dump = dumpDir and (dumpAt[frame] or (dumpEvery > 0 and frame % dumpEvery == 0))
  local parts = {string.format("F %d anc=%d mclk=%d pc=%02x%04x", frame, readsAtWindow, s.masterClock, s["cpu.k"],
                               s["cpu.pc"])}
  local cb = {}
  le64(cb, chain)
  for _, name in ipairs(FIELDS) do
    local t = f[name]
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
  if dump then
    local fh = io.open(string.format("%s/f%06d.imgsz.txt", dumpDir, frame), "w")
    fh:write(imgsz .. "\n")
    fh:close()
  end
  chain = fnvBytes(cb)
  parts[#parts + 1] = "imgsz=" .. imgsz
  parts[#parts + 1] = string.format("all=%016x", chain)
  out:write(table.concat(parts, " ") .. "\n")
  if lines then
    local w = tonumber(imgsz:match("^(%d+)x"))
    local img = f.img
    local row = {"L " .. frame}
    for y = 0, #img // (2 * w) - 1 do
      local h = BASIS
      for i = y * 2 * w + 1, (y + 1) * 2 * w do h = (h ~ img[i]) * PRIME end
      row[#row + 1] = string.format("%016x", h)
    end
    out:write(table.concat(row, " ") .. "\n")
  end
  if traceJoy then
    out:write(string.format("# joy1=%04x\n", s["internalRegisters.controllerData[0]"] & 0xFFFF))
  end
  if frame >= maxFrames then
    done = true
    out:close()
    emu.stop(0)
  end
end

local boundaryRef = nil
local function onBoundary()
  if boundaryRef == nil then return end
  emu.removeMemoryCallback(boundaryRef, emu.callbackType.exec, 0, 0xFFFFFF, emu.cpuType.snes, M.snesMemory)
  boundaryRef = nil
  if not done then sample() end
end

emu.addEventCallback(function()
  if done then return end
  windowClock = emu.getState().masterClock
  readsAtWindow = reads
  if boundaryRef == nil then
    boundaryRef = emu.addMemoryCallback(onBoundary, emu.callbackType.exec, 0, 0xFFFFFF, emu.cpuType.snes,
                                        M.snesMemory)
  end
end, emu.eventType.endFrame)
