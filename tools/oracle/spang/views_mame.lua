-- Dump MAME 0.285's decrypted Kabuki views of the set spang for the
-- byte-for-byte check of romtool (docs/spang-oracles.md section 6).
-- Start through run_mame.sh with FH_VIEWS=DIR (the hash writer is not
-- loaded then). Writes DIR/op_fixed.bin and data_fixed.bin (opcode and
-- program space 0x0000-0x7FFF), op_bankNN.bin and data_bankNN.bin (both
-- spaces at 0x8000-0xBFFF with bank NN selected through MAME's bank
-- objects) and region.bin (the region :maincpu, which MAME overwrites
-- with the data view). Reads go through the debugger-free read_u8 of the
-- address spaces; the bank entries are restored afterwards.
local m = manager.machine
local dir = assert(os.getenv("FH_VIEWS"), "FH_VIEWS not set")
local cpu = m.devices[":maincpu"]
local ops = cpu.spaces["opcodes"]
local prog = cpu.spaces["program"]
local opbank = m.memory.banks[":opbank"]
local databank = m.memory.banks[":databank"]
local region = m.memory.regions[":maincpu"]

local function dump(name, space, lo, hi)
  local t = {}
  for a = lo, hi do t[#t + 1] = string.char(space:read_u8(a)) end
  local f = assert(io.open(dir .. "/" .. name, "wb"))
  f:write(table.concat(t))
  f:close()
end

local saveOp, saveData = opbank.entry, databank.entry
dump("op_fixed.bin", ops, 0x0000, 0x7fff)
dump("data_fixed.bin", prog, 0x0000, 0x7fff)
for b = 0, 15 do
  opbank.entry = b
  databank.entry = b
  dump(string.format("op_bank%02d.bin", b), ops, 0x8000, 0xbfff)
  dump(string.format("data_bank%02d.bin", b), prog, 0x8000, 0xbfff)
end
opbank.entry, databank.entry = saveOp, saveData
local t = {}
for a = 0, region.size - 1 do t[#t + 1] = string.char(region:read_u8(a)) end
local f = assert(io.open(dir .. "/region.bin", "wb"))
f:write(table.concat(t))
f:close()
m:exit()
