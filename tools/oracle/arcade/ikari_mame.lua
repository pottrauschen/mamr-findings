-- Ikari Warriors hash lines (docs/arcade-oracle-format.md, afh version 1,
-- set ikari) for MAME 0.285 and mameref. Start it through run_mame.sh.
-- Environment:
--   FH_OUT          output file (required)
--   FH_FRAMES       number of F lines, then MAME exits (default 3000)
--   FH_REPLAY       input replay ("ikari replay v1", format section 3.2)
--   FH_INPUT_SHA1   value of the header key input= (run_mame.sh sets it)
--   FH_JUDGE        value of the header key judge= (run_mame.sh sets it)
--   FH_IMG          "1": hash the picture (field img), else img=-
--   FH_ACCLOG       file for the access log (format section 6), optional
--   FH_DUMP_DIR     directory for canonical field dumps
--   FH_DUMP_AT      "F,F,..." frames to dump; FH_DUMP_EVERY  K
--
-- Sampling (format section 3): the frame notifier comes at VBLANK start n,
-- after the scheduler has run every CPU to that time. A CPU may stand
-- inside an instruction there (MAME's Z80 stops where its cycle budget runs
-- out), so the memory fields are read in the notifier and each CPU's
-- registers at its next opcode fetch, which is the first instruction
-- boundary at or after VBLANK start (after an interrupt entry taken there).
--
-- Notifier and taps live in global variables: Lua's garbage collector
-- otherwise removes the subscriptions after a few dozen frames, silently.

local m = manager.machine
local out = assert(io.open(assert(os.getenv("FH_OUT"), "FH_OUT not set"), "w"))
local maxFrames = tonumber(os.getenv("FH_FRAMES") or "3000")
local wantImg = os.getenv("FH_IMG") == "1"
local dumpDir = os.getenv("FH_DUMP_DIR")
if dumpDir == "" then dumpDir = nil end
local dumpEvery = tonumber(os.getenv("FH_DUMP_EVERY") or "0")
local dumpAt = {}
for f in (os.getenv("FH_DUMP_AT") or ""):gmatch("%d+") do dumpAt[tonumber(f)] = true end

local PRIME = 0x100000001B3
local BASIS = -3750763034362895579 -- 0xcbf29ce484222325

local function fail(msg)
  out:write("# error: " .. msg .. "\n")
  out:close()
  m:exit()
  error(msg)
end

-- ------------------------------------------------------------ devices

local CPUS = {":maincpu", ":sub", ":audiocpu"}
local cpu, prog = {}, {}
for i, tag in ipairs(CPUS) do
  cpu[i] = m.devices[tag]
  if not cpu[i] then fail("no device " .. tag) end
  prog[i] = cpu[i].spaces["program"]
end
local scr = m.screens[":screen"]
local pal = m.palettes[":palette"]

local function item(dev, name)
  local d = m.devices[dev]
  local idx = d and d.items[name]
  if not idx then fail("no item " .. dev .. " " .. name) end
  return emu.item(idx)
end

-- memory shares through their save-state items (the share objects of
-- MAME 0.285's Lua interface have no block read)
local itBg = item(":maincpu", "0/:bg_videoram")
local itSpr = item(":maincpu", "0/:spriteram")
local itTx = item(":maincpu", "0/:tx_videoram")
local itSnd = item(":audiocpu", "0/c000-cfff")
local itLatch = item(":soundlatch", "0/m_latched_value")
local itStatus = item(":", "0/m_sound_status")
local VREG = {"m_bg_scrollx", "m_bg_scrolly", "m_sp16_scrollx", "m_sp16_scrolly", "m_sp32_scrollx",
              "m_sp32_scrolly", "m_hf_posx", "m_hf_posy", "m_tx_tile_offset"}
local itVreg = {}
for i, n in ipairs(VREG) do itVreg[i] = item(":", "0/" .. n) end
local itNmi, itIrq, itRef = {}, {}, {}
for i, tag in ipairs(CPUS) do
  itNmi[i] = item(tag, "0/m_nmi_state")
  itIrq[i] = item(tag, "0/m_irq_state")
  itRef[i] = item(tag, "0/m_ref")
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

local function le16(t, v) t[#t + 1] = v & 0xFF; t[#t + 1] = (v >> 8) & 0xFF end
local function le64(t, v) for i = 0, 7 do t[#t + 1] = (v >> (8 * i)) & 0xFF end end

-- ------------------------------------------------------------ time

-- CPU cycles of a machine time, exactly as MAME counts them: MAME advances
-- a CPU's local time by whole multiples of its attoseconds per cycle
-- (HZ_TO_ATTOSECONDS of the clock, truncated), so the cycle number is
-- floor(time / period). With 10^18 = Q * period + R the division needs no
-- number above 2^63 (seconds stay below 100 here).
local PERIOD = {298507462686, 298507462686, 250000000000} -- 3.35, 3.35, 4 MHz
local QUOT, REM = {}, {}
for i = 1, 3 do
  QUOT[i] = 1000000000000000000 // PERIOD[i]
  REM[i] = 1000000000000000000 % PERIOD[i]
end
local function cyclesAt(i, t)
  return t.seconds * QUOT[i] + (t.seconds * REM[i] + t.attoseconds) // PERIOD[i]
end
-- inside a tap the machine time is the local time of the executing CPU
local function nowCycles(i) return cyclesAt(i, m.time) end

-- ------------------------------------------------------------ inputs

-- Replay file: runs of frames with the same six ports, as ikari_headless
-- --replay reads them; entry f is what the program reads while frame f+1
-- runs, i.e. in window f+1 (format section 3.2). MAME applies a field value
-- at its next per-frame input update, which runs at VBLANK start before
-- the frame notifiers: a value set in the notifier of frame n is read from
-- VBLANK n+1 on, in window n+2. So entry n+1 is set in the notifier of
-- frame n, entry 1 before the first frame; entry 0 is the power-on state
-- of the ports.
local runs = {}
local replayPath = os.getenv("FH_REPLAY")
if replayPath and replayPath ~= "" then
  local fh = io.open(replayPath, "r")
  if not fh then fail("cannot read replay " .. replayPath) end
  local first = fh:read("l")
  if not (first and first:match("^# ikari replay v1%s*$")) then fail(replayPath .. ": not an ikari replay v1 file") end
  local no = 1
  for line in fh:lines() do
    no = no + 1
    if line:sub(1, 1) ~= "#" and line:match("%S") then
      local c, p1, p2, p3, p4, p5, p6 = line:match(
        "^%s*(%d+)%s+(%x%x)%s+(%x%x)%s+(%x%x)%s+(%x%x)%s+(%x%x)%s+(%x%x)%s*$")
      if not c or #c > 9 or tonumber(c) < 1 then fail(string.format("%s:%d: malformed replay line", replayPath, no)) end
      runs[#runs + 1] = {tonumber(c), tonumber(p1, 16), tonumber(p2, 16), tonumber(p3, 16),
                         tonumber(p4, 16), tonumber(p5, 16), tonumber(p6, 16)}
    end
  end
  fh:close()
  if #runs == 0 then fail(replayPath .. ": no entries") end
end

local ri, rpos, ridx = 1, 0, 0
local function entryAt(idx)
  while ridx < idx do
    ridx = ridx + 1
    rpos = rpos + 1
    if rpos >= runs[ri][1] then
      if ri < #runs then ri = ri + 1; rpos = 0 else rpos = runs[ri][1] - 1 end
    end
  end
  return runs[ri]
end

local ports = m.ioport.ports
local function fieldByMask(port, mask)
  for _, f in pairs(ports[port].fields) do if f.mask == mask then return f end end
  fail(string.format("no field %s mask %02x", port, mask))
end
local function dipByName(port, name)
  local f = ports[port] and ports[port].fields[name]
  if not f then fail("no dip " .. port .. " " .. name) end
  return f
end
-- digital fields, active low: {entry slot, mask, field}
local DIG = {}
local function digital(slot, port, masks)
  for _, mk in ipairs(masks) do DIG[#DIG + 1] = {slot, mk, fieldByMask(port, mk)} end
end
local DIPS, BONUS = {}, nil
if #runs > 0 then
  digital(2, ":IN0", {0x02, 0x10, 0x20, 0x40, 0x80})
  digital(3, ":IN1", {0x01, 0x02, 0x04, 0x08})
  digital(4, ":IN2", {0x01, 0x02, 0x04, 0x08})
  digital(5, ":IN3", {0x01, 0x02, 0x08, 0x10})
  DIPS = {
    {6, 0x01, dipByName(":DSW1", "Allow killing each other")},
    {6, 0x02, dipByName(":DSW1", "P1 & P2 Fire Buttons")},
    {6, 0x08, dipByName(":DSW1", "Lives")},
    {6, 0x30, dipByName(":DSW1", "Coin A")},
    {6, 0xC0, dipByName(":DSW1", "Coin B")},
    {7, 0x03, dipByName(":DSW2", "Difficulty")},
    {7, 0x0C, dipByName(":DSW2", "Game Mode")},
    {7, 0x40, fieldByMask(":DSW2", 0x40)},
    {7, 0x80, dipByName(":DSW2", "Allow Continue")},
  }
  BONUS = dipByName(":BONUS", "Bonus Life") -- DSW1 bit 2 and DSW2 bits 4-5
end
local lastDsw1, lastDsw2 = -1, -1
local function applyEntry(idx)
  if #runs == 0 then return end
  local r = entryAt(idx)
  for _, d in ipairs(DIG) do d[3]:set_value(((r[d[1]] & d[2]) == 0) and 1 or 0) end
  if r[6] ~= lastDsw1 or r[7] ~= lastDsw2 then
    for _, d in ipairs(DIPS) do d[3].user_value = r[d[1]] & d[2] end
    BONUS.user_value = (r[6] & 0x04) | (r[7] & 0x30)
    lastDsw1, lastDsw2 = r[6], r[7]
  end
end

-- ------------------------------------------------------------ windows

local frame = 0
local irqBytes, ymBytes, ymtBytes = {}, {}, {}
local acclog = nil
if os.getenv("FH_ACCLOG") and os.getenv("FH_ACCLOG") ~= "" then
  acclog = assert(io.open(os.getenv("FH_ACCLOG"), "w"))
end

local function z80Bytes(i)
  local s = cpu[i].state
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

-- YM3526 writes of the sound CPU: E800 chip 1 address, EC00 chip 1 data,
-- F000 chip 2 address, F400 chip 2 data (codes 0-3).
local YMCODE = {[0xE800] = 0, [0xEC00] = 1, [0xF000] = 2, [0xF400] = 3}
ikYm = prog[3]:install_write_tap(0xE800, 0xF7FF, "ik_ym", function(offset, data, mask)
  local code = YMCODE[offset]
  if not code then return end
  local c = nowCycles(3)
  ymBytes[#ymBytes + 1] = code
  ymBytes[#ymBytes + 1] = data & 0xFF
  ymtBytes[#ymtBytes + 1] = code
  ymtBytes[#ymtBytes + 1] = data & 0xFF
  le64(ymtBytes, c)
end)

-- Access log: every access of CPU A and B to 0xC000-0xFFFF and of the sound
-- CPU to 0xE000-0xFFFF, with the CPU's cycle (format section 6).
if acclog then
  local LO = {0xC000, 0xC000, 0xE000}
  for i = 1, 3 do
    _G["ikAccR" .. i] = prog[i]:install_read_tap(LO[i], 0xFFFF, "ik_accr" .. i, function(offset, data, mask)
      acclog:write(string.format("%d R %d %d %04x %02x\n", i - 1, frame + 1, nowCycles(i), offset, data & 0xFF))
    end)
    _G["ikAccW" .. i] = prog[i]:install_write_tap(LO[i], 0xFFFF, "ik_accw" .. i, function(offset, data, mask)
      acclog:write(string.format("%d W %d %d %04x %02x\n", i - 1, frame + 1, nowCycles(i), offset, data & 0xFF))
    end)
  end
end

-- ------------------------------------------------------------ sampling

local FIELDS = {"za", "zb", "zs", "bg", "spr", "tx", "snd", "vreg", "io", "pal", "irq", "ym", "ymt", "img"}
local RAW = {za = true, zb = true, zs = true, vreg = true, io = true}

out:write(string.format("H afh 1 oracle=mame core=mame-%s judge=%s set=ikari input=%s\n",
  emu.app_version(), os.getenv("FH_JUDGE") or "-", os.getenv("FH_INPUT_SHA1") or "-"))

local function hexs(t)
  local x = {}
  for i = 1, #t do x[i] = string.format("%02x", t[i]) end
  return table.concat(x)
end

local function dump(n, name, s)
  local f = assert(io.open(string.format("%s/f%06d.%s.bin", dumpDir, n, name), "wb"))
  f:write(s)
  f:close()
end

local palString = nil
local function palBytes()
  -- the colour PROMs never change: read once
  if palString then return palString end
  local t = {}
  local n = math.min(pal.entries, 0x400)
  if n ~= 0x400 then fail("palette has " .. pal.entries .. " entries") end
  for p = 0, n - 1 do
    local c = pal:pen_color(p)
    t[#t + 1] = c & 0xFF; t[#t + 1] = (c >> 8) & 0xFF; t[#t + 1] = (c >> 16) & 0xFF
  end
  palString = bytesToString(t)
  return palString
end

local chain = 0
local lastKey = nil
ikRemoved = {}
local pending = nil -- the frame being sampled: memory fields, then registers per CPU

local function finish(p)
  local parts = {string.format("F %d clka=%d clkb=%d clks=%d", p.n, p.clk[1], p.clk[2], p.clk[3])}
  local cb = {}
  le64(cb, chain)
  for _, name in ipairs(FIELDS) do
    local v = p.s[name]
    if v == nil then
      parts[#parts + 1] = name .. "=-"
      for i = 1, 8 do cb[#cb + 1] = 0 end
    else
      local hv = fnvString(v)
      le64(cb, hv)
      if RAW[name] then
        parts[#parts + 1] = name .. "=" .. hexs({string.byte(v, 1, -1)})
      else
        parts[#parts + 1] = string.format("%s=%016x", name, hv)
      end
    end
  end
  chain = fnvString(bytesToString(cb))
  parts[#parts + 1] = string.format("irqn=%d ymn=%d mid=%s all=%016x", p.irqn, p.ymn, p.mid, chain)
  out:write(table.concat(parts, " ") .. "\n")
  if dumpDir and (dumpAt[p.n] or (dumpEvery > 0 and p.n % dumpEvery == 0)) then
    for _, name in ipairs(FIELDS) do
      if p.s[name] then dump(p.n, name, p.s[name]) end
    end
  end
  if p.n >= maxFrames then
    out:close()
    if acclog then acclog:close() end
    m:exit()
  end
end

local function onFetch(i, offset)
  local p = pending
  if not p or p.clk[i] or (offset & 0xffff) ~= (cpu[i].state["CURPC"].value & 0xffff) then return end
  p.clk[i] = nowCycles(i)
  p.s[({"za", "zb", "zs"})[i]] = bytesToString(z80Bytes(i))
  p.left = p.left - 1
  -- one sample per CPU: remove the tap (MAME's tap entries are reference
  -- counted, so this is safe inside the callback); the Lua object is kept
  -- until the next notifier so that it is not collected while it runs
  local tp = _G["ikFetch" .. i]
  _G["ikFetch" .. i] = nil
  ikRemoved[#ikRemoved + 1] = tp
  tp:remove()
  if p.left == 0 then
    pending = nil
    finish(p)
  end
end

-- Interrupt entries (field irq): the first opcode fetch at 0x0038 or
-- 0x0066 is the first instruction boundary of the handler; record the CPU,
-- the vector, the cycle and the registers there. A data read of those
-- addresses (the ROM checksum) does not count: the fetch is recognised by
-- CURPC. (The program executes no RST 38 and never jumps to the vectors in
-- the runs measured; such a fetch would be recorded as well.)
for i = 1, 3 do
  for _, v in ipairs({0x0038, 0x0066}) do
    _G["ikIrq" .. i .. v] = prog[i]:install_read_tap(v, v, "ik_irq" .. i .. v, function(offset, data, mask)
      if (cpu[i].state["CURPC"].value & 0xffff) ~= offset then return end
      irqBytes[#irqBytes + 1] = i - 1
      irqBytes[#irqBytes + 1] = offset & 0xFF
      le64(irqBytes, nowCycles(i))
      for _, b in ipairs(z80Bytes(i)) do irqBytes[#irqBytes + 1] = b end
    end)
  end
end

-- the entries of the window grouped by CPU (A, B, sound), each CPU's in
-- time order (format section 3.1): independent of how MAME interleaves
-- the CPUs
function irqString()
  local parts = {{}, {}, {}}
  for i = 1, #irqBytes, 42 do
    local cpuId = irqBytes[i]
    local rec = parts[cpuId + 1]
    for k = i, i + 41 do rec[#rec + 1] = irqBytes[k] end
  end
  local all = {}
  for c = 1, 3 do for _, b in ipairs(parts[c]) do all[#all + 1] = b end end
  return bytesToString(all)
end

local function onFrame()
  local t = m.time
  local key = t.seconds * 1000000000000000000 + t.attoseconds
  if key == lastKey then return end
  lastKey = key
  if frame >= maxFrames then return end
  if pending then fail("frame " .. frame + 1 .. ": a CPU did not reach an instruction boundary") end
  frame = frame + 1
  local n = frame
  local mid = ""
  for i = 1, 3 do mid = mid .. (((itRef[i]:read(0) & 0xffffff) ~= 0xffff00) and "1" or "0") end
  local vreg = {}
  for i = 1, #itVreg do le16(vreg, itVreg[i]:read(0) & 0xFFFF) end
  local io = {itLatch:read(0) & 0xFF, itStatus:read(0) & 0xFF,
              itNmi[1]:read(0) ~= 0 and 1 or 0, itNmi[2]:read(0) ~= 0 and 1 or 0,
              itIrq[1]:read(0) ~= 0 and 1 or 0, itIrq[2]:read(0) ~= 0 and 1 or 0,
              (itStatus:read(0) & 0x0B) ~= 0 and 1 or 0}
  local img = nil
  if wantImg then
    local px, w, h = scr:pixels()
    if w ~= 288 or h ~= 216 then fail("unexpected screen size " .. w .. "x" .. h) end
    img = px
  end
  pending = {
    n = n, left = 3, clk = {}, mid = mid,
    irqn = #irqBytes // 42, ymn = #ymBytes // 2,
    s = {
      bg = itBg:read_block(0, 0x800),
      spr = itSpr:read_block(0, 0x1800),
      tx = itTx:read_block(0, 0x800),
      snd = itSnd:read_block(0, 0x1000),
      vreg = bytesToString(vreg),
      io = bytesToString(io),
      pal = palBytes(),
      irq = irqString(),
      ym = bytesToString(ymBytes),
      ymt = bytesToString(ymtBytes),
      img = img,
    },
  }
  irqBytes, ymBytes, ymtBytes = {}, {}, {}
  ikRemoved = {}
  applyEntry(n + 1)
  for i = 1, 3 do
    _G["ikFetch" .. i] = prog[i]:install_read_tap(0x0000, 0xffff, "ik_fetch" .. i, function(offset, data, mask)
      local ok, err = pcall(onFetch, i, offset)
      if not ok then fail(tostring(err)) end
    end)
  end
end

applyEntry(1)
ikFrame = emu.add_machine_frame_notifier(function()
  local ok, err = pcall(onFrame)
  if not ok then fail(tostring(err)) end
end)
