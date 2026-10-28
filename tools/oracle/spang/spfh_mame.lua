-- Super Pang hash lines (docs/spang-oracle-format.md, spfh version 1) for
-- MAME 0.285, set spang. Start it through run_mame.sh. Environment:
--   FH_OUT          output file (required)
--   FH_FRAMES       number of F lines, then MAME exits (default 3000)
--   FH_INPUT        input script (format section 6), optional
--   FH_INPUT_SHA1   value of the header key input= (run_mame.sh sets it)
--   FH_YM2413       value of the header key ym2413= (rom or placeholder)
--   FH_IMG          "1": hash the picture (field img), else img=-
--   FH_IOLOG        file for the I/O log (format section 7), optional
--   FH_DUMP_DIR     directory for canonical field dumps
--   FH_DUMP_AT      "F,F,..." frames to dump; FH_DUMP_EVERY  K
--
-- Sampling point: MAME's frame notifier, called when the screen's VBLANK
-- begins (vpos 248, hpos 0). The CPU has then run to the first instruction
-- boundary at or after that time (MAME's scheduler stops a timeslice
-- there), which is the sampling point MAMR uses too.
--
-- Notifier and taps live in global variables: Lua's garbage collector
-- otherwise removes the subscriptions after a few dozen frames, silently.

local m = manager.machine
local out = assert(io.open(assert(os.getenv("FH_OUT"), "FH_OUT not set"), "w"))
local maxFrames = tonumber(os.getenv("FH_FRAMES") or "3000")
local wantImg = os.getenv("FH_IMG") == "1"
local dumpDir = os.getenv("FH_DUMP_DIR")
local dumpEvery = tonumber(os.getenv("FH_DUMP_EVERY") or "0")
local dumpAt = {}
for f in (os.getenv("FH_DUMP_AT") or ""):gmatch("%d+") do dumpAt[tonumber(f)] = true end

local PRIME = 0x100000001B3
local BASIS = -3750763034362895579 -- 0xcbf29ce484222325
local ATTOS_PER_CYCLE = 125000000000 -- 8 MHz

local function fail(msg)
  out:write("# error: " .. msg .. "\n")
  out:close()
  m:exit()
  error(msg)
end

local main = m.devices[":maincpu"]
local iosp = main.spaces["io"]
local scr = m.screens[":screen"]

local function item(dev, name)
  local d = m.devices[dev]
  local idx = d and d.items[name]
  if not idx then fail("no item " .. dev .. " " .. name) end
  return emu.item(idx)
end

-- memory shares through their save-state items (the share objects of
-- MAME 0.285's Lua interface have no block read)
local shareWram = item(":maincpu", "0/:nvram")
local shareVram = item(":maincpu", "0/:videoram")
local shareCram = item(":maincpu", "0/:colorram")
local shareObj = item(":", "0/:objram")
local itPal = item(":", "0/m_paletteram")
local itIrqSrc = item(":", "0/m_irq_source")
local itIrqLine = item(":maincpu", "0/m_irq_state")
local itTotal = item(":maincpu", "0/m_totalcycles")
local itRef = item(":maincpu", "0/m_ref")
local itOkiBank = item(":oki", "0/m_cur_bank")
local databank = m.memory.banks[":databank"]

local ee = {}
for _, n in ipairs({"m_data", "m_state", "m_cs_state", "m_clk_state", "m_di_state", "m_locked", "m_command",
                    "m_bits_accum", "m_command_address_accum", "m_address", "m_shift_register",
                    "m_completion_time.seconds", "m_completion_time.attoseconds"}) do
  ee[n] = item(":eeprom", "0/" .. n)
end

-- ------------------------------------------------------------ hashing

local function fnvString(s, h)
  h = h or BASIS
  local byte = string.byte
  local n = #s
  local i = 1
  while i + 7 <= n do
    local a, b, c, d, e, f, g, k = byte(s, i, i + 7)
    h = (h ~ a) * PRIME; h = (h ~ b) * PRIME; h = (h ~ c) * PRIME; h = (h ~ d) * PRIME
    h = (h ~ e) * PRIME; h = (h ~ f) * PRIME; h = (h ~ g) * PRIME; h = (h ~ k) * PRIME
    i = i + 8
  end
  while i <= n do h = (h ~ byte(s, i)) * PRIME; i = i + 1 end
  return h
end

local function bytesToString(t)
  local parts = {}
  for i = 1, #t, 4096 do
    parts[#parts + 1] = string.char(table.unpack(t, i, math.min(i + 4095, #t)))
  end
  return table.concat(parts)
end

local function le32(t, v)
  for i = 0, 3 do t[#t + 1] = (v >> (8 * i)) & 0xFF end
end

local function shareBytes(it)
  return it:read_block(0, it.count * it.size)
end

-- machine time in attoseconds since power-on (fits: 2^63 as is 9.2 s ...
-- so keep seconds and attoseconds apart and convert to cycles directly)
local function nowCycles()
  local t = m.time
  return t.seconds * 8000000 + t.attoseconds // ATTOS_PER_CYCLE
end

-- ------------------------------------------------------------ input script

local FIELDS_BY_BUTTON = {
  COIN1 = {":IN0", "Coin 1"}, SERVICE1 = {":IN0", "Service 1"},
  START1 = {":IN0", "1 Player Start"}, START2 = {":IN0", "2 Players Start"},
  P1_UP = {":IN1", "P1 Up"}, P1_DOWN = {":IN1", "P1 Down"}, P1_LEFT = {":IN1", "P1 Left"},
  P1_RIGHT = {":IN1", "P1 Right"}, P1_B1 = {":IN1", "P1 Button 1"}, P1_B2 = {":IN1", "P1 Button 2"},
  P2_UP = {":IN2", "P2 Up"}, P2_DOWN = {":IN2", "P2 Down"}, P2_LEFT = {":IN2", "P2 Left"},
  P2_RIGHT = {":IN2", "P2 Right"}, P2_B1 = {":IN2", "P2 Button 1"}, P2_B2 = {":IN2", "P2 Button 2"},
  SERVICE = {":SYS0", "Service Mode"},
}
local fieldOf = {}
for b, pf in pairs(FIELDS_BY_BUTTON) do
  local port = m.ioport.ports[pf[1]]
  local fld = port and port.fields[pf[2]]
  if not fld then fail("no input field " .. pf[1] .. " " .. pf[2]) end
  fieldOf[b] = fld
end

local script = {} -- frame -> set of buttons held from that frame's sampling point on
local inputPath = os.getenv("FH_INPUT")
if inputPath and inputPath ~= "" then
  local fh = io.open(inputPath, "r")
  if not fh then fail("cannot read input script " .. inputPath) end
  local n, last = 0, 1
  for raw in fh:lines() do
    n = n + 1
    local line = raw:gsub("#.*$", "")
    local tok = {}
    for t in line:gmatch("%S+") do tok[#tok + 1] = t end
    if #tok > 0 then
      local f = tonumber(tok[1])
      if not f or math.type(f) ~= "integer" or f < 2 or f <= last then
        fail("input script line " .. n .. ": frames must be integers >= 2, ascending")
      end
      last = f
      local held = {}
      for k = 2, #tok do
        local b = tok[k]:upper()
        if b ~= "-" then
          if not fieldOf[b] then fail("input script line " .. n .. ": unknown button " .. tok[k]) end
          held[b] = true
        end
      end
      script[f] = held
    end
  end
  fh:close()
end

-- MAME applies a field value at its next per-frame input update, which
-- runs before this script's notifier: values set in the notifier of frame
-- F-1 are what the program reads from the sampling point of frame F on.
local function applyInputs(frame)
  local held = script[frame + 1]
  if not held then return end
  for b, fld in pairs(fieldOf) do fld:set_value(held[b] and 1 or 0) end
end

-- ------------------------------------------------------------ power-on

-- MAME 0.285 never initialises m_video_bank, m_paletteram_bank and
-- m_flipscreen (mitchell.cpp: not set in machine_start/machine_reset), so
-- their power-on values are whatever the allocation left there. The game
-- fills 0xD000-0xDFFF before its first write to port 0x07, so the video
-- bank decides whether tile or sprite RAM gets that fill: runs differ in
-- frames 4-7 (docs/spang-oracles.md section 4). Write 0 to ports 0x00 and
-- 0x07 before the first instruction; MAMR powers on with the same zeros.
iosp:write_u8(0x00, 0x00)
iosp:write_u8(0x07, 0x00)

-- ------------------------------------------------------------ I/O taps

local frame = 0
local port0, port7 = 0, 0
local ymBytes, okiBytes, irqBytes = {}, {}, {}
local iolog = nil
if os.getenv("FH_IOLOG") and os.getenv("FH_IOLOG") ~= "" then
  iolog = assert(io.open(os.getenv("FH_IOLOG"), "w"))
end

spfhIoWrite = iosp:install_write_tap(0x00, 0xff, "spfh_iow", function(offset, data, mask)
  local p = offset & 0xff
  data = data & 0xff
  if p == 0x00 then port0 = data
  elseif p == 0x07 then port7 = data
  elseif p == 0x03 or p == 0x04 then ymBytes[#ymBytes + 1] = p; ymBytes[#ymBytes + 1] = data
  elseif p == 0x05 then okiBytes[#okiBytes + 1] = data end
  if iolog then iolog:write(string.format("W %d %d %02x %02x\n", frame + 1, nowCycles(), p, data)) end
end)
if iolog then
  spfhIoRead = iosp:install_read_tap(0x00, 0xff, "spfh_ior", function(offset, data, mask)
    iolog:write(string.format("R %d %d %02x %02x\n", frame + 1, nowCycles(), offset & 0xff, data & 0xff))
  end)
end

-- ------------------------------------------------------------ fields

local function z80Bytes()
  local s = main.state
  local z = {}
  for _, r in ipairs({"PC", "AF", "BC", "DE", "HL", "AF2", "BC2", "DE2", "HL2", "IX", "IY", "SP", "WZ"}) do
    local v = s[r].value
    z[#z + 1] = (v >> 8) & 0xFF
    z[#z + 1] = v & 0xFF
  end
  z[#z + 1] = s["I"].value & 0xFF
  z[#z + 1] = s["R"].value & 0xFF
  z[#z + 1] = s["IFF1"].value & 1
  z[#z + 1] = s["IFF2"].value & 1
  z[#z + 1] = s["IM"].value & 3
  z[#z + 1] = s["HALT"].value & 1
  return z
end

-- Interrupt entries (field irq): the first opcode fetch at 0x0038 after
-- IM 1 has pushed PC is an instruction boundary; record the cycle and
-- the registers there. (The program never executes an RST 38 opcode in
-- the runs measured; such a fetch would be recorded as well.)
spfhIrq = main.spaces["opcodes"]:install_read_tap(0x0038, 0x0038, "spfh_irq", function(offset, data, mask)
  local c = nowCycles()
  for i = 0, 7 do irqBytes[#irqBytes + 1] = (c >> (8 * i)) & 0xFF end
  for _, b in ipairs(z80Bytes()) do irqBytes[#irqBytes + 1] = b end
end)

local function eepBytes(nowSec, nowAtto)
  local t = {}
  local data = ee.m_data:read_block(0, 128)
  for i = 1, 128 do t[i] = string.byte(data, i) end
  local cs, ca = ee["m_completion_time.seconds"]:read(0), ee["m_completion_time.attoseconds"]:read(0)
  local busy = (cs > nowSec or (cs == nowSec and ca > nowAtto)) and 1 or 0
  t[#t + 1] = ee.m_state:read(0) & 0xFF
  t[#t + 1] = ee.m_cs_state:read(0) & 0xFF
  t[#t + 1] = ee.m_clk_state:read(0) & 0xFF
  t[#t + 1] = ee.m_di_state:read(0) & 0xFF
  t[#t + 1] = ee.m_locked:read(0) & 0xFF
  t[#t + 1] = ee.m_command:read(0) & 0xFF
  t[#t + 1] = ee.m_bits_accum:read(0) & 0xFF
  t[#t + 1] = busy
  le32(t, ee.m_command_address_accum:read(0))
  le32(t, ee.m_address:read(0))
  le32(t, ee.m_shift_register:read(0))
  return t
end

-- canonical picture: 384 x 240 pixels, each the xRGB444 value of its
-- colour, 16-bit little-endian (format section 4)
local function imgString()
  local px, w, h = scr:pixels()
  if w ~= 384 or h ~= 240 then fail("unexpected screen size " .. w .. "x" .. h) end
  local byte, char = string.byte, string.char
  local rows = {}
  for y = 0, h - 1 do
    local row = {}
    for x = 0, w - 1 do
      local o = (y * w + x) * 4 + 1
      local b8, g8, r8 = byte(px, o, o + 2)
      local v = (r8 >> 4 << 8) | (g8 >> 4 << 4) | (b8 >> 4)
      row[#row + 1] = char(v & 0xFF, v >> 8)
    end
    rows[#rows + 1] = table.concat(row)
  end
  return table.concat(rows)
end

local function hexs(t)
  local x = {}
  for i = 1, #t do x[i] = string.format("%02x", t[i]) end
  return table.concat(x)
end

local function dump(name, s)
  local f = assert(io.open(string.format("%s/f%06d.%s.bin", dumpDir, frame, name), "wb"))
  f:write(s)
  f:close()
end

local FIELDS = {"z80", "wram", "vram", "obj", "pal", "bank", "irq", "eep", "ym", "oki", "img"}
local RAW = {z80 = true, bank = true}

out:write(string.format("H spfh 1 oracle=mame core=mame-%s set=spang ym2413=%s input=%s\n",
  emu.app_version(), os.getenv("FH_YM2413") or "-", os.getenv("FH_INPUT_SHA1") or "-"))

applyInputs(0)
local chain = 0
local lastKey = nil
-- The sample of frame n: taken at the first instruction boundary at or
-- after VBLANK start n. MAME's Z80 stops where its cycle budget runs out,
-- also inside an instruction (z80make.py: every step returns when
-- m_icount <= 0), so the frame notifier may see a half-executed
-- instruction (m_ref ~= 0xffff00). The notifier therefore only notes the
-- VBLANK time, the picture and whether the CPU stood inside an
-- instruction (key mid=), and arms an opcode-fetch tap; the state is read
-- at the next fetch of an instruction's first byte (address == CURPC),
-- which is MAMR's sampling point: its runner stops at the first
-- instruction boundary at or after the target cycle.
local pending = nil

local function sample(p)
  frame = p.n
  local z = z80Bytes()
  local bank = {databank.entry & 0xFF, itOkiBank:read(0) & 0xFF, port0, port7,
                itIrqSrc:read(0) & 0xFF, itIrqLine:read(0) & 1}
  local s = {
    z80 = bytesToString(z),
    wram = shareBytes(shareWram),
    vram = shareBytes(shareVram) .. shareBytes(shareCram),
    obj = shareBytes(shareObj),
    pal = itPal:read_block(0, 0x1000),
    bank = bytesToString(bank),
    irq = bytesToString(irqBytes),
    eep = bytesToString(eepBytes(p.sec, p.atto)),
    ym = bytesToString(ymBytes),
    oki = bytesToString(okiBytes),
    img = p.img,
  }

  local parts = {string.format("F %d zclk=%d", frame, nowCycles())}
  local cb = {}
  for i = 0, 7 do cb[#cb + 1] = (chain >> (8 * i)) & 0xFF end
  for _, name in ipairs(FIELDS) do
    local v = s[name]
    if v == nil then
      parts[#parts + 1] = name .. "=-"
      for i = 1, 8 do cb[#cb + 1] = 0 end
    else
      local hv = fnvString(v)
      for i = 0, 7 do cb[#cb + 1] = (hv >> (8 * i)) & 0xFF end
      if RAW[name] then
        parts[#parts + 1] = name .. "=" .. hexs({string.byte(v, 1, -1)})
      else
        parts[#parts + 1] = string.format("%s=%016x", name, hv)
      end
    end
  end
  chain = fnvString(bytesToString(cb))
  parts[#parts + 1] = string.format("ymn=%d okin=%d irqn=%d mid=%d all=%016x", #ymBytes // 2, #okiBytes,
    #irqBytes // 40, p.mid, chain)
  out:write(table.concat(parts, " ") .. "\n")

  if dumpDir and (dumpAt[frame] or (dumpEvery > 0 and frame % dumpEvery == 0)) then
    for _, name in ipairs(FIELDS) do
      if s[name] then dump(name, s[name]) end
    end
  end
  ymBytes, okiBytes, irqBytes = {}, {}, {}

  if frame >= maxFrames then
    out:close()
    if iolog then iolog:close() end
    m:exit()
  end
end

local function onFetch(offset)
  if not pending or (offset & 0xffff) ~= (main.state["CURPC"].value & 0xffff) then return end
  local p = pending
  pending = nil
  sample(p)
end

local function onFrame()
  local t = m.time
  local key = t.seconds * 1000000000000000000 + t.attoseconds
  if key == lastKey then return end
  lastKey = key
  if frame >= maxFrames or pending then return end
  local n = frame + 1
  pending = {n = n, sec = t.seconds, atto = t.attoseconds,
             mid = (itRef:read(0) & 0xffffff) ~= 0xffff00 and 1 or 0,
             img = wantImg and imgString() or nil}
  applyInputs(n)
end

spfhFetch = main.spaces["opcodes"]:install_read_tap(0x0000, 0xffff, "spfh_fetch", function(offset, data, mask)
  if pending then
    local ok, err = pcall(onFetch, offset)
    if not ok then fail(tostring(err)) end
  end
end)

spfhFrame = emu.add_machine_frame_notifier(function()
  local ok, err = pcall(onFrame)
  if not ok then fail(tostring(err)) end
end)
