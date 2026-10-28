-- R-Type hash lines (docs/arcade-oracle-format.md, afh version 1, set
-- rtype) for MAME 0.285 and mameref. Start it through run_mame.sh.
-- Environment:
--   FH_OUT          output file (required)
--   FH_FRAMES       number of F lines, then MAME exits (default 3000)
--   FH_REPLAY       input replay ("rtype replay v1", format section 4.2)
--   FH_INPUT_SHA1   value of the header key input= (run_mame.sh sets it)
--   FH_JUDGE        value of the header key judge= (run_mame.sh sets it)
--   FH_IMG          "1": hash the picture (field img), else img=-
--   FH_ACCLOG       file for the access log (format section 6), optional
--   FH_DUMP_DIR     directory for canonical field dumps
--   FH_DUMP_AT      "F,F,..." frames to dump; FH_DUMP_EVERY  K
--
-- Sampling (format section 4.1): the frame notifier comes at VBLANK start
-- n (screen line 256). The V30 stands at an instruction boundary there
-- (MAME's nec core checks its cycle budget between instructions and
-- between the iterations of a REP), so its registers are read in the
-- notifier with the memory fields; the sound CPU may stand inside an
-- instruction, so its registers are read at its next opcode fetch.
--
-- Notifier and taps live in global variables (Lua's garbage collector
-- would remove them otherwise).

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
local BASIS = -3750763034362895579

local function fail(msg)
  out:write("# error: " .. msg .. "\n")
  out:close()
  m:exit()
  error(msg)
end

local main = m.devices[":maincpu"]
local snd = m.devices[":soundcpu"]
local mprog = main.spaces["program"]
local sprog = snd.spaces["program"]
local sio = snd.spaces["io"]
local scr = m.screens[":screen"]

local function item(dev, name)
  local d = m.devices[dev]
  local idx = d and d.items[name]
  if not idx then fail("no item " .. dev .. " " .. name) end
  return emu.item(idx)
end

local itRam = item(":maincpu", "0/40000-43fff")
local itSpr = item(":maincpu", "0/:spriteram")
local itSbuf = item(":spriteram", "0/m_buffered")
local itPal1 = item(":maincpu", "0/:paletteram1")
local itPal2 = item(":maincpu", "0/:paletteram2")
local itVram1 = item(":maincpu", "0/:videoram1")
local itVram2 = item(":maincpu", "0/:videoram2")
local itSnd = item(":soundcpu", "0/:soundram")
local itScrollX = item(":", "0/m_scrollx")
local itScrollY = item(":", "0/m_scrolly")
local itRaster = item(":", "0/m_raster_irq_position")
local itVideoOff = item(":", "0/m_video_off")
local itFlip = item(":", "0/m_flip_screen_x")
local itLatch = item(":soundlatch", "0/m_latched_value")
local itLatchW = item(":soundlatch", "0/m_latch_written")
local itRst = item(":soundirq", "0/m_input_buffer")
local itZIrq = item(":soundcpu", "0/m_irq_state")
local itZSusp = item(":soundcpu", "0/m_suspend")
local itZRef = item(":soundcpu", "0/m_ref")
local itVIrq = item(":maincpu", "0/m_irq_state")
local itVNmi = item(":maincpu", "0/m_nmi_state")
local itVTotal = item(":maincpu", "0/m_totalcycles")
local itVIp = item(":maincpu", "0/m_ip")
local itVPrefetch = item(":maincpu", "0/m_prefetch_count")
local itVNoInt = item(":maincpu", "0/m_no_interrupt")
local itVHalted = item(":maincpu", "0/m_halted")
local PIC = {"m_state", "m_isr", "m_irr", "m_imr", "m_prio", "m_irq_lines", "m_ocw3", "m_level_trig_mode",
             "m_auto_eoi", "m_base"}
local itPic = {}
for i, n in ipairs(PIC) do itPic[i] = item(":upd71059c", "0/" .. n) end

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
local function be16(t, v) t[#t + 1] = (v >> 8) & 0xFF; t[#t + 1] = v & 0xFF end
local function le64(t, v) for i = 0, 7 do t[#t + 1] = (v >> (8 * i)) & 0xFF end end

-- ------------------------------------------------------------ time

-- V30 8 MHz: 125,000,000,000 attoseconds per clock, exact. Z80
-- 3.579545 MHz: HZ_TO_ATTOSECONDS truncates the period; cycles are
-- floor(time / period) as MAME counts them.
local VP = 125000000000
local ZP = 1000000000000000000 // 3579545
local ZQ, ZR = 1000000000000000000 // ZP, 1000000000000000000 % ZP
local function vCycles(t) return t.seconds * 8000000 + t.attoseconds // VP end
local function zCycles(t) return t.seconds * ZQ + (t.seconds * ZR + t.attoseconds) // ZP end

-- ------------------------------------------------------------ inputs

-- Replay ("rtype replay v1"): runs of frames with the three 16-bit ports
-- IN0, IN1, DSW as the main CPU read them; entry f is what it reads while
-- frame f+1 runs (window f+1). As for Ikari, entry n+1 is set in the
-- notifier of frame n (MAME applies field values at its next per-frame
-- input update, at VBLANK start).
local runs = {}
local replayPath = os.getenv("FH_REPLAY")
if replayPath and replayPath ~= "" then
  local fh = io.open(replayPath, "r")
  if not fh then fail("cannot read replay " .. replayPath) end
  local first = fh:read("l")
  if not (first and first:match("^# rtype replay v1%s*$")) then fail(replayPath .. ": not an rtype replay v1 file") end
  local no = 1
  for line in fh:lines() do
    no = no + 1
    if line:sub(1, 1) ~= "#" and line:match("%S") then
      local c, p1, p2, p3 = line:match("^%s*(%d+)%s+(%x%x%x%x)%s+(%x%x%x%x)%s+(%x%x%x%x)%s*$")
      if not c or tonumber(c) < 1 then fail(string.format("%s:%d: malformed replay line", replayPath, no)) end
      runs[#runs + 1] = {tonumber(c), tonumber(p1, 16), tonumber(p2, 16), tonumber(p3, 16)}
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
-- digital fields of IN0 (every bit) and IN1 (start, coin, service), active
-- low; IN1 bit 7 is the sprite DMA flag (not an input). DSW: every DIP
-- field gets the bits of the recorded value.
local DIG, DIPS = {}, {}
if #runs > 0 then
  for _, f in pairs(m.ioport.ports[":IN0"].fields) do DIG[#DIG + 1] = {2, f.mask, f} end
  for _, f in pairs(m.ioport.ports[":IN1"].fields) do
    if f.mask & 0x3F ~= 0 then DIG[#DIG + 1] = {3, f.mask, f} end
  end
  for _, f in pairs(m.ioport.ports[":DSW"].fields) do DIPS[#DIPS + 1] = {4, f.mask, f} end
end
local lastDsw = -1
local function applyEntry(idx)
  if #runs == 0 then return end
  local r = entryAt(idx)
  for _, d in ipairs(DIG) do d[3]:set_value(((r[d[1]] & d[2]) == 0) and 1 or 0) end
  if r[4] ~= lastDsw then
    for _, d in ipairs(DIPS) do d[3].user_value = r[4] & d[2] end
    lastDsw = r[4]
  end
end

-- ------------------------------------------------------------ records

local frame = 0
local irqBytes, ymBytes, ymtBytes = {}, {}, {}
local acclog = nil
if os.getenv("FH_ACCLOG") and os.getenv("FH_ACCLOG") ~= "" then
  acclog = assert(io.open(os.getenv("FH_ACCLOG"), "w"))
end

local function v30Bytes()
  local s = main.state
  local t = {}
  for _, r in ipairs({"AW", "CW", "DW", "BW", "SP", "BP", "IX", "IY", "DS1", "PS", "SS", "DS0"}) do
    be16(t, s[r].value)
  end
  be16(t, itVIp:read(0))
  be16(t, s["PSW"].value)
  t[#t + 1] = itVPrefetch:read(0) & 0xFF
  t[#t + 1] = itVNoInt:read(0) & 0xFF
  t[#t + 1] = itVHalted:read(0) ~= 0 and 1 or 0
  t[#t + 1] = 0
  return t
end

local function z80Bytes()
  local s = snd.state
  local z = {}
  for _, r in ipairs({"PC", "AF", "BC", "DE", "HL", "AF2", "BC2", "DE2", "HL2", "IX", "IY", "SP", "WZ"}) do
    be16(z, s[r].value)
  end
  z[#z + 1] = s["I"].value & 0xFF
  z[#z + 1] = s["R"].value & 0xFF
  z[#z + 1] = s["IFF1"].value & 1
  z[#z + 1] = s["IFF2"].value & 1
  z[#z + 1] = s["IM"].value & 3
  z[#z + 1] = s["HALT"].value & 1
  return z
end

-- YM2151 writes of the sound CPU: port 0 address, port 1 data (codes 0, 1)
rtYm = sio:install_write_tap(0x00, 0x01, "rt_ym", function(offset, data, mask)
  local c = zCycles(m.time)
  ymBytes[#ymBytes + 1] = offset & 1
  ymBytes[#ymBytes + 1] = data & 0xFF
  ymtBytes[#ymtBytes + 1] = offset & 1
  ymtBytes[#ymtBytes + 1] = data & 0xFF
  le64(ymtBytes, c)
end)

-- Interrupt entries (field irq). V30: nec_interrupt reads the vector from
-- the table at 4 * vector; the entry is recorded at the next instruction
-- start (the handler's first opcode fetch, address PS * 16 + IP). Z80:
-- the first opcode fetch at an RST vector of mode 0 (0x08, 0x18, 0x28).
-- V30 entries: nec_interrupt pushes PSW, reads the offset word at
-- 4 * vector and the segment word after it, then pushes PS and IP and
-- jumps. The entry is recorded when the segment word is read (the opcode
-- fetches go through MAME's memory cache, which taps do not see), with the
-- registers as they are after the entry: PS:IP = the vector, SP 4 lower.
-- The time is then the entry's start plus the 8 clocks of the PSW push.
-- A data read of the table by the program (the ROM checksum) is not
-- preceded by a PSW push; it is told apart by the push (a stack word write
-- exactly the 8 clocks of i_pushf before).
local vOff = nil
local lastPush = nil -- {time key, value} of the last stack word write
rtIvt = mprog:install_read_tap(0x00000, 0x003FF, "rt_ivt", function(offset, data, mask)
  if mask ~= 0xFFFF then return end
  if offset & 3 == 0 then
    vOff = {offset >> 2, data & 0xFFFF}
  elseif offset & 3 == 2 and vOff and vOff[1] == offset >> 2 then
    local s = main.state
    local t = m.time
    local key = t.seconds * 1000000000000000000 + t.attoseconds
    if lastPush and key - lastPush[1] == 8 * VP then
      local b = v30Bytes()
      local sp = (s["SP"].value - 4) & 0xFFFF
      b[9], b[10] = sp >> 8, sp & 0xFF
      b[19], b[20] = (data >> 8) & 0xFF, data & 0xFF       -- PS
      b[25], b[26] = (vOff[2] >> 8) & 0xFF, vOff[2] & 0xFF -- IP
      b[29], b[30], b[31] = 0, 0, 0
      irqBytes[#irqBytes + 1] = 0
      irqBytes[#irqBytes + 1] = vOff[1] & 0xFF
      le64(irqBytes, vCycles(t))
      for _, x in ipairs(b) do irqBytes[#irqBytes + 1] = x end
    end
    vOff = nil
  end
end)
-- the PSW push of an entry: a word write to the stack
rtPush = mprog:install_write_tap(0x40000, 0x43FFF, "rt_push", function(offset, data, mask)
  if mask ~= 0xFFFF then return end
  local t = m.time
  lastPush = {t.seconds * 1000000000000000000 + t.attoseconds, data & 0xFFFF}
end)
for _, v in ipairs({0x0008, 0x0018, 0x0028}) do
  _G["rtZIrq" .. v] = sprog:install_read_tap(v, v, "rt_zirq" .. v, function(offset, data, mask)
    if (snd.state["CURPC"].value & 0xffff) ~= offset then return end
    irqBytes[#irqBytes + 1] = 1
    irqBytes[#irqBytes + 1] = offset & 0xFF
    le64(irqBytes, zCycles(m.time))
    for _, b in ipairs(z80Bytes()) do irqBytes[#irqBytes + 1] = b end
  end)
end

-- Access log: every V30 I/O write and every sound CPU port access.
if acclog then
  rtAccV = main.spaces["io"]:install_write_tap(0x00, 0xFF, "rt_accv", function(offset, data, mask)
    acclog:write(string.format("0 O %d %d %02x %04x %04x\n", frame + 1, vCycles(m.time), offset, data & 0xFFFF, mask))
  end)
  rtAccZw = sio:install_write_tap(0x00, 0xFF, "rt_acczw", function(offset, data, mask)
    acclog:write(string.format("1 O %d %d %02x %02x\n", frame + 1, zCycles(m.time), offset, data & 0xFF))
  end)
  rtAccZr = sio:install_read_tap(0x00, 0xFF, "rt_acczr", function(offset, data, mask)
    acclog:write(string.format("1 I %d %d %02x %02x\n", frame + 1, zCycles(m.time), offset, data & 0xFF))
  end)
end

-- ------------------------------------------------------------ sampling

local FIELDS = {"v30", "zs", "ram", "spr", "sbuf", "pal", "vram", "snd", "vreg", "io", "pic", "irq", "ym", "ymt",
                "img"}
local RAW = {v30 = true, zs = true, vreg = true, io = true, pic = true}

out:write(string.format("H afh 1 oracle=mame core=mame-%s judge=%s set=rtype input=%s\n",
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

-- grouped by CPU (V30, then sound CPU), each in time order
local function irqString()
  local parts = {{}, {}}
  for i = 1, #irqBytes, 42 do
    local rec = parts[irqBytes[i] + 1]
    for k = i, i + 41 do rec[#rec + 1] = irqBytes[k] end
  end
  local all = {}
  for c = 1, 2 do for _, b in ipairs(parts[c]) do all[#all + 1] = b end end
  return bytesToString(all)
end

local chain = 0
local lastKey = nil
local pending = nil
rtRemoved = {}

local function finish(p)
  local parts = {string.format("F %d clkm=%d clks=%d", p.n, p.clkm, p.clks)}
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

local function onZFetch(offset)
  local p = pending
  if not p or (offset & 0xffff) ~= (snd.state["CURPC"].value & 0xffff) then return end
  p.clks = zCycles(m.time)
  p.s.zs = bytesToString(z80Bytes())
  local tp = rtZFetch
  rtZFetch = nil
  rtRemoved[#rtRemoved + 1] = tp
  tp:remove()
  pending = nil
  finish(p)
end

local function onFrame()
  local t = m.time
  local key = t.seconds * 1000000000000000000 + t.attoseconds
  if key == lastKey then return end
  lastKey = key
  if frame >= maxFrames then return end
  if pending then fail("frame " .. frame + 1 .. ": the sound CPU did not reach an instruction boundary") end
  frame = frame + 1
  local held = itZSusp:read(0) ~= 0 -- held in reset until the main CPU releases it
  local vreg = {}
  -- s32 m_scrollx[2], m_scrolly[2]: the low 16 bits of each
  local sx, sy = itScrollX:read_block(0, 8), itScrollY:read_block(0, 8)
  for k = 0, 1 do
    le16(vreg, string.byte(sx, 4 * k + 1) | string.byte(sx, 4 * k + 2) << 8)
  end
  for k = 0, 1 do
    le16(vreg, string.byte(sy, 4 * k + 1) | string.byte(sy, 4 * k + 2) << 8)
  end
  le16(vreg, itRaster:read(0) & 0xFFFF)
  vreg[#vreg + 1] = itVideoOff:read(0) & 0xFF
  vreg[#vreg + 1] = itFlip:read(0) & 0xFF
  local io = {itLatch:read(0) & 0xFF, itLatchW:read(0) & 0xFF, itRst:read(0) & 0xFF,
              itZIrq:read(0) ~= 0 and 1 or 0, held and 1 or 0,
              itVIrq:read(0) ~= 0 and 1 or 0, itVNmi:read(0) ~= 0 and 1 or 0}
  -- pic8259 0.285: read selection in OCW3 bits 0-1 (2 IRR, 3 ISR, else
  -- none); the field holds the selection, not the version's raw OCW3
  local pic = {}
  for i = 1, #itPic do pic[#pic + 1] = itPic[i]:read(0) & 0xFF end
  local o3 = pic[7] & 3
  pic[7] = (o3 == 2) and 0 or ((o3 == 3) and 1 or 2)
  local img = nil
  if wantImg then
    local px, w, h = scr:pixels()
    if w ~= 384 or h ~= 256 then fail("unexpected screen size " .. w .. "x" .. h) end
    img = px
  end
  local p = {
    n = frame, clkm = itVTotal:read(0), mid = ((itZRef:read(0) & 0xffffff) ~= 0xffff00) and "01" or "00",
    irqn = #irqBytes // 42, ymn = #ymBytes // 2,
    s = {
      v30 = bytesToString(v30Bytes()),
      ram = itRam:read_block(0, 0x4000),
      spr = itSpr:read_block(0, 0x400),
      sbuf = itSbuf:read_block(0, 0x400),
      pal = itPal1:read_block(0, 0xC00) .. itPal2:read_block(0, 0xC00),
      vram = itVram1:read_block(0, 0x4000) .. itVram2:read_block(0, 0x4000),
      snd = itSnd:read_block(0, 0x10000),
      vreg = bytesToString(vreg),
      io = bytesToString(io),
      pic = bytesToString(pic),
      irq = irqString(),
      ym = bytesToString(ymBytes),
      ymt = bytesToString(ymtBytes),
      img = img,
    },
  }
  irqBytes, ymBytes, ymtBytes = {}, {}, {}
  rtRemoved = {}
  applyEntry(frame + 1)
  if held then
    -- a Z80 held in reset has no next instruction: its registers now
    p.clks = zCycles(m.time)
    p.s.zs = bytesToString(z80Bytes())
    finish(p)
    return
  end
  pending = p
  rtZFetch = sprog:install_read_tap(0x0000, 0xffff, "rt_zfetch", function(offset, data, mask)
    local ok, err = pcall(onZFetch, offset)
    if not ok then fail(tostring(err)) end
  end)
end

applyEntry(1)
rtFrame = emu.add_machine_frame_notifier(function()
  local ok, err = pcall(onFrame)
  if not ok then fail(tostring(err)) end
end)
