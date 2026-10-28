// aresref: headless ares Super Famicom reference that writes the SNES
// hash lines (docs/snes-oracle-format.md, version 4).
//
// Builds against an ares checkout at commit c76aaff with the patches in
// patches/ares/ applied (see build_aresref.sh). ares is ISC licensed; this file
// only uses it as an external library.
//
//   aresref ROM --frames N [options]
//     --out FILE           hash lines (default: stdout)
//     --input SCRIPT       input script (docs/snes-oracle-input-script.md)
//     --anchor PC[:TAG]    A line before each execution of PB:PC (hex);
//                          may be repeated
//     --ports              P lines for every APU port write
//     --fill 00|ff|native  power-on state: 00 = every value ares would
//                          draw at random is zero (default), ff = the same
//                          with WRAM, VRAM, OAM, CGRAM and APU RAM set to
//                          ff, native = ares' own deterministic
//                          pseudo-random fill
//     --dump-dir DIR       write the canonical field bytes of selected
//                          frames to DIR/f<frame>.<field>.bin
//     --dump-at F[,F...]   frames to dump
//     --dump-every K       dump every K-th frame
//     --inject F:ADDR:XOR  fault injection: at the sampling point of frame
//                          F (before hashing) XOR the WRAM byte ADDR
//                          (0-1ffff, hex) with XOR (hex)
//     --rom-id TEXT        value of the header key rom= (e.g. the SHA-1)
//     --trace-joypad       after each F line a comment line "# joy1=XXXX"
//                          with the last auto-read word ($4218/$4219)
//     --lines              after each F line an L line with one hash per
//                          picture row
//     --region auto|ntsc|pal  console region (default auto: from the ROM)
#include <mia/mia.hpp>
#include <sfc/sfc.hpp>

#include <cstdio>
#include <cstring>
#include <set>
#include <filesystem>
#include <string>
#include <vector>

namespace sfc = ares::SuperFamicom;

namespace {

constexpr u64 FnvBasis = 0xcbf29ce484222325ull;
constexpr u64 FnvPrime = 0x100000001b3ull;

u64 fnv(const std::vector<u8>& data, u64 h = FnvBasis) {
  for(u8 b : data) h = (h ^ b) * FnvPrime;
  return h;
}

void put16(std::vector<u8>& v, u32 x) { v.push_back(x & 0xff); v.push_back((x >> 8) & 0xff); }
void put64(std::vector<u8>& v, u64 x) { for(int i = 0; i < 8; i++) v.push_back((x >> (8 * i)) & 0xff); }

const char* const FieldNames[] = {"cpu", "smp", "apuio", "wram", "vram", "oam", "cgram", "ppu", "aram", "dsp", "img", "sram"};
constexpr int FieldCount = 12;
constexpr bool FieldRaw[] = {true, true, true, false, false, false, false, false, false, false, false, false};

// ---------------------------------------------------------------- input script

const char* const ButtonNames[] = {"B", "Y", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT", "A", "X", "L", "R"};

struct Command { int op; u32 a; u32 b; };  // op: 0 HOLD, 1 RELEASE, 2 WAIT, 3 WAIT_RAM8

struct Script {
  std::vector<Command> cmds;
  size_t pc = 0;
  long remaining = -1;
  u16 pad = 0;

  static std::string upper(std::string s) { for(auto& c : s) c = toupper((unsigned char)c); return s; }

  bool parse(const std::string& text, std::string& error) {
    size_t pos = 0; int lineNo = 0;
    while(pos <= text.size()) {
      size_t end = text.find('\n', pos);
      if(end == std::string::npos) end = text.size();
      std::string line = text.substr(pos, end - pos);
      pos = end + 1; lineNo++;
      if(auto hash = line.find('#'); hash != std::string::npos) line.resize(hash);
      std::vector<std::string> tok;
      size_t i = 0;
      while(i < line.size()) {
        while(i < line.size() && isspace((unsigned char)line[i])) i++;
        size_t j = i;
        while(j < line.size() && !isspace((unsigned char)line[j])) j++;
        if(j > i) tok.push_back(line.substr(i, j - i));
        i = j;
      }
      if(tok.empty()) { if(end == text.size()) break; continue; }
      auto op = upper(tok[0]);
      auto fail = [&](const char* what) { error = "line " + std::to_string(lineNo) + ": " + what; return false; };
      auto hexval = [](std::string s) -> long {
        if(!s.empty() && s[0] == '$') s = s.substr(1);
        if(s.size() > 2 && s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s = s.substr(2);
        if(s.empty()) return -1;
        char* e = nullptr; long v = strtol(s.c_str(), &e, 16);
        return *e ? -1 : v;
      };
      if(op == "HOLD" || op == "RELEASE") {
        if(tok.size() < 2) return fail("needs at least one button");
        u32 mask = 0;
        for(size_t k = 1; k < tok.size(); k++) {
          auto b = upper(tok[k]); int bit = -1;
          for(int n = 0; n < 12; n++) if(b == ButtonNames[n]) bit = 15 - n;
          if(bit < 0) return fail("unknown button");
          mask |= 1u << bit;
        }
        cmds.push_back({op == "HOLD" ? 0 : 1, mask, 0});
      } else if(op == "WAIT") {
        if(tok.size() != 2) return fail("WAIT needs one count");
        char* e = nullptr; long n = strtol(tok[1].c_str(), &e, 10);
        if(*e || n < 1) return fail("WAIT needs a count >= 1");
        cmds.push_back({2, (u32)n, 0});
      } else if(op == "WAIT_RAM8") {
        if(tok.size() != 3) return fail("WAIT_RAM8 needs an address and a value");
        long a = hexval(tok[1]), v = hexval(tok[2]);
        if(a >= 0x7e0000 && a <= 0x7fffff) a -= 0x7e0000;
        else if(a < 0 || a > 0x1fff) return fail("WRAM address out of range");
        if(v < 0 || v > 0xff) return fail("value out of range");
        cmds.push_back({3, (u32)a, (u32)v});
      } else {
        return fail("unknown command");
      }
      if(end == text.size()) break;
    }
    return true;
  }

  // One auto-joypad read (docs/snes-oracle-input-script.md, stepping rule).
  template<typename RAM> u16 onRead(RAM ram8) {
    while(pc < cmds.size()) {
      auto& c = cmds[pc];
      if(c.op == 0) pad |= c.a;
      else if(c.op == 1) pad &= ~c.a;
      else if(c.op == 2) {
        if(remaining < 0) remaining = c.a;
        if(remaining > 0) { remaining--; return pad; }
        remaining = -1;
      } else if(c.op == 3) {
        if(ram8(c.a) != c.b) return pad;
      }
      pc++;
    }
    return pad;
  }
};

// ---------------------------------------------------------------- state

struct Options {
  std::string rom, out, input, fill = "00", dumpDir, romId = "-";
  u32 frames = 0, dumpEvery = 0;
  std::set<u32> dumpAt;
  std::vector<std::pair<u32, std::string>> anchors;
  bool ports = false;
  bool traceJoypad = false;
  bool lines = false;
  std::string region = "auto";
  long injectFrame = -1; u32 injectAddr = 0; u8 injectXor = 0;
} opt;

FILE* out = stdout;
u32 frame = 0;       // number of F lines written
u64 anc = 0;         // auto-joypad reads so far
bool readInWindow = false;  // a read began after the sampling window opened
u64 chain = FnvBasis;
bool done = false;
Script script;
u16 pad = 0;
u8 ppuShadow[0x34] = {};
u8 ppuPrev[0x34] = {};
std::vector<std::pair<u32, u64>> anchorLast;  // pc, mclk of the previous hit (0 = none yet)

u16 brightness(u16 c, u32 b) {
  if(b >= 15) return c & 0x7fff;
  u32 r = (c & 0x1f) * b / 15, g = ((c >> 5) & 0x1f) * b / 15, bl = ((c >> 10) & 0x1f) * b / 15;
  return r | g << 5 | bl << 10;
}

std::vector<u8> pictureBytes;  // img taken by onPicture for the next F line
std::string pictureSize;

std::vector<u8> fieldBytes(int field, std::string& imgsz) {
  std::vector<u8> v;
  auto& cpu = sfc::cpu;
  auto& smp = sfc::smp;
  auto& ppu = sfc::ppuImpl;
  switch(field) {
  case 0:  // cpu
    put16(v, cpu.r.a.w); put16(v, cpu.r.x.w); put16(v, cpu.r.y.w); put16(v, cpu.r.s.w); put16(v, cpu.r.d.w);
    v.push_back((u8)cpu.r.b); v.push_back((u8)(cpu.r.pc.d >> 16)); v.push_back((u8)(u32)cpu.r.p); v.push_back(cpu.r.e ? 1 : 0);
    break;
  case 1: {  // smp
    v.push_back(smp.r.ya.byte.l); v.push_back(smp.r.x); v.push_back(smp.r.ya.byte.h); v.push_back(smp.r.s); v.push_back((u8)(u32)smp.r.p);
    u8 control = (smp.io.iplromEnable ? 0x80 : 0) | (smp.timer0.enable ? 1 : 0) | (smp.timer1.enable ? 2 : 0) | (smp.timer2.enable ? 4 : 0);
    v.push_back(control); v.push_back(smp.io.dspAddress);
    v.push_back(smp.timer0.target); v.push_back(smp.timer1.target); v.push_back(smp.timer2.target);
    v.push_back(smp.timer0.stage3); v.push_back(smp.timer1.stage3); v.push_back(smp.timer2.stage3);
    break;
  }
  case 2:  // apuio
    v.push_back(smp.io.apu0); v.push_back(smp.io.apu1); v.push_back(smp.io.apu2); v.push_back(smp.io.apu3);
    v.push_back(smp.io.cpu0); v.push_back(smp.io.cpu1); v.push_back(smp.io.cpu2); v.push_back(smp.io.cpu3);
    break;
  case 3: v.assign(cpu.wram, cpu.wram + 0x20000); break;
  case 4: for(u32 i = 0; i < 0x8000; i++) put16(v, ppu.vram.data[i]); break;
  case 5: for(u32 i = 0; i < 544; i++) v.push_back(ppu.oam.read(i)); break;
  case 6: for(u32 i = 0; i < 256; i++) put16(v, ppu.cgram[i] & 0x7fff); break;
  case 7:  // ppu
    for(u32 i = 0; i < 0x34; i++) v.push_back(ppuShadow[i]);
    for(u32 r = 0x0d; r <= 0x14; r++) v.push_back(ppuPrev[r]);
    for(u32 r = 0x1b; r <= 0x20; r++) v.push_back(ppuPrev[r]);
    put16(v, ppu.io.vramAddress & 0x7fff); put16(v, ppu.latch.vram);
    v.push_back(ppu.latch.oam); v.push_back(ppu.io.cgramAddress); v.push_back(ppu.io.cgramAddressLatch ? 1 : 0);
    v.push_back(ppu.latch.cgram); v.push_back(ppu.latch.bgofsPPU1); v.push_back(ppu.latch.bgofsPPU2 & 7); v.push_back(ppu.latch.mode7);
    break;
  case 8: v.assign(sfc::dsp.apuram, sfc::dsp.apuram + 0x10000); break;
  case 9: v.assign(sfc::dsp.registers, sfc::dsp.registers + 128); break;
  case 10: {  // img: rows v = 1..224 (1..239 with overscan) of the frame being drawn
    // Taken at the start of scanline vdisp (oracleHooks.picture, patch 0008),
    // before the PPU's frame code swaps the buffers at V=240: at the sampling
    // boundary itself the capture would race that swap when overscan puts
    // the window at V=240 (docs/snes-oracles.md section 2).
    if(!pictureBytes.empty()) {
      imgsz = pictureSize;
      v = pictureBytes;
      pictureBytes.clear();
      break;
    }
    auto pixels = ppu.screen->pixels(0).data();
    bool overscan = ppu.overscan(), interlace = ppu.interlace();
    u32 height = overscan ? 239 : 224;
    std::vector<u16> rows(height * 512);
    bool hires = false;
    for(u32 y = 0; y < height; y++) {
      // the row ares' DAC writes scanline y + 1 to (sfc/ppu/dac.cpp)
      u32 yScale = interlace ? 2 : 1;
      u32 row = (y + 1 + (overscan ? 0 : 8)) * yScale + (sfc::Region::PAL() ? 20 * yScale : 0)
              + (interlace && ppu.field() ? 1 : 0);
      // the horizontal border before the first half-pixel (sfc/ppu/dac.cpp)
      const u32* line = pixels + row * 564 + (sfc::Region::PAL() ? 22 : 26);
      for(u32 x = 0; x < 512; x++) {
        u32 e = line[x];
        rows[y * 512 + x] = brightness(e & 0x7fff, (e >> 15) & 15);
      }
      for(u32 x = 0; x < 256 && !hires; x++) if(rows[y * 512 + 2 * x] != rows[y * 512 + 2 * x + 1]) hires = true;
    }
    for(u32 y = 0; y < height; y++) {
      if(hires) for(u32 x = 0; x < 512; x++) put16(v, rows[y * 512 + x]);
      else for(u32 x = 0; x < 256; x++) put16(v, rows[y * 512 + 2 * x + 1]);
    }
    imgsz = std::to_string(hires ? 512 : 256) + "x" + std::to_string(height);
    break;
  }
  case 11:  // sram: the cartridge's save RAM (empty without one); without a
            // save file ares allocates it filled with $FF
    if(auto size = sfc::cartridge.ram.size()) v.assign(sfc::cartridge.ram.data(), sfc::cartridge.ram.data() + size);
    break;
  }
  return v;
}

void writeDump(int field, const std::vector<u8>& data, const std::string& imgsz) {
  char name[64];
  snprintf(name, sizeof name, "/f%06u.%s.bin", frame, FieldNames[field]);
  if(FILE* f = fopen((opt.dumpDir + name).c_str(), "wb")) { fwrite(data.data(), 1, data.size(), f); fclose(f); }
  if(field == 10) {
    snprintf(name, sizeof name, "/f%06u.imgsz.txt", frame);
    if(FILE* f = fopen((opt.dumpDir + name).c_str(), "w")) { fprintf(f, "%s\n", imgsz.c_str()); fclose(f); }
  }
}

void onPicture() {
  if(done) return;
  pictureBytes.clear();
  pictureBytes = fieldBytes(10, pictureSize);
}

void onFrame() {
  if(done) return;
  frame++;
  if((long)frame == opt.injectFrame) sfc::cpu.wram[opt.injectAddr & 0x1ffff] ^= opt.injectXor;
  bool dump = !opt.dumpDir.empty() && (opt.dumpAt.count(frame) || (opt.dumpEvery && frame % opt.dumpEvery == 0));
  // anc of the F line: reads begun before the sampling window opened
  u64 ancWindow = anc - (readInWindow ? 1 : 0);
  readInWindow = false;
  std::string line = "F " + std::to_string(frame) + " anc=" + std::to_string(ancWindow) + " mclk=" + std::to_string(sfc::oracleHooks.cpuClocks);
  char buf[64];
  snprintf(buf, sizeof buf, " pc=%06x", (u32)sfc::cpu.r.pc.d);
  line += buf;
  std::vector<u8> chainBuf;
  put64(chainBuf, chain);
  std::string imgsz = "-";
  std::string rowLine;
  for(int f = 0; f < FieldCount; f++) {
    auto data = fieldBytes(f, imgsz);
    if(f == 10 && opt.lines) {
      u32 width = imgsz.rfind("512", 0) == 0 ? 512 : 256;
      u32 rows = data.size() / (width * 2);
      rowLine = "L " + std::to_string(frame);
      for(u32 y = 0; y < rows; y++) {
        std::vector<u8> row(data.begin() + y * width * 2, data.begin() + (y + 1) * width * 2);
        snprintf(buf, sizeof buf, " %016llx", (unsigned long long)fnv(row));
        rowLine += buf;
      }
    }
    u64 h = fnv(data);
    put64(chainBuf, h);
    line += " "; line += FieldNames[f]; line += "=";
    if(FieldRaw[f]) { for(u8 b : data) { snprintf(buf, sizeof buf, "%02x", b); line += buf; } }
    else { snprintf(buf, sizeof buf, "%016llx", (unsigned long long)h); line += buf; }
    if(dump) writeDump(f, data, imgsz);
  }
  chain = fnv(chainBuf);
  snprintf(buf, sizeof buf, " all=%016llx", (unsigned long long)chain);
  line += " imgsz=" + imgsz + buf;
  fprintf(out, "%s\n", line.c_str());
  if(opt.lines) fprintf(out, "%s\n", rowLine.c_str());
  if(opt.traceJoypad) fprintf(out, "# joy1=%04x\n", (u32)sfc::cpu.io.joy1);
  if(frame >= opt.frames) { done = true; fflush(out); }
}

void onJoypad() {
  if(done) return;
  anc++;
  readInWindow = sfc::oracleHooks.framePending;
  pad = script.onRead([](u32 offset) -> u32 { return sfc::cpu.wram[offset & 0x1ffff]; });
}

void onInstruction(u32 pc) {
  if(done) return;
  for(auto& [apc, last] : anchorLast) {
    if(apc != pc) continue;
    u64 now = sfc::oracleHooks.cpuClocks;
    std::string tag = "-";
    for(auto& [p, t] : opt.anchors) if(p == pc) tag = t;
    if(last) fprintf(out, "A %u pc=%06x mclk=%llu d=%llu anc=%llu tag=%s\n", frame + 1, pc, (unsigned long long)now,
                     (unsigned long long)(now - last), (unsigned long long)anc, tag.c_str());
    else fprintf(out, "A %u pc=%06x mclk=%llu d=- anc=%llu tag=%s\n", frame + 1, pc, (unsigned long long)now,
                 (unsigned long long)anc, tag.c_str());
    last = now;
  }
}

void onPpuWrite(u8 reg, u8 data) {
  if(reg >= 0x34) return;
  ppuPrev[reg] = ppuShadow[reg];
  ppuShadow[reg] = data;
}

void onApuWrite(bool smpSide, u8 port, u8 data) {
  if(done || !opt.ports) return;
  if(smpSide) fprintf(out, "P %u s t=%llu port=%u val=%02x\n", frame + 1, (unsigned long long)(sfc::oracleHooks.smpClocks / 2), port, data);
  else fprintf(out, "P %u c t=%llu port=%u val=%02x\n", frame + 1, (unsigned long long)sfc::oracleHooks.cpuClocks, port, data);
}

struct Ref : ares::Platform {
  std::shared_ptr<mia::Pak> game, system;
  ares::Node::System root;
  auto pak(ares::Node::Object node) -> std::shared_ptr<vfs::directory> override {
    if(node->name() == "Super Famicom") return system->pak;
    if(node->name() == "Super Famicom Cartridge") return game->pak;
    return {};
  }
  auto video(ares::Node::Video::Screen, const u32*, u32, u32, u32) -> void override {}
  auto audio(ares::Node::Audio::Stream stream) -> void override {
    while(stream->pending()) { double s[2]; stream->read(s); }
  }
  auto input(ares::Node::Input::Input node) -> void override {
    auto b = node->cast<ares::Node::Input::Button>();
    if(!b) return;
    bool p1 = false;
    if(auto port = node->parent().lock()) if(auto pp = port->parent().lock()) p1 = pp->name() == "Controller Port 1";
    std::string name = Script::upper((const char*)node->name());
    bool pressed = false;
    for(int n = 0; n < 12; n++) if(name == ButtonNames[n]) pressed = pad >> (15 - n) & 1;
    b->setValue(p1 && pressed);
  }
};

int usage() {
  fprintf(stderr, "usage: aresref ROM --frames N [--out FILE] [--input SCRIPT] [--anchor PC[:TAG]]... [--ports]\n"
                  "       [--fill 00|ff|native] [--dump-dir DIR (--dump-at F,.. | --dump-every K)]\n"
                  "       [--inject F:ADDR:XOR] [--rom-id TEXT] [--trace-joypad] [--lines]\n"
                  "       [--region auto|ntsc|pal]\n");
  return 3;
}

int run(std::vector<std::string> args) {
  for(size_t i = 0; i < args.size(); i++) {
    auto& a = args[i];
    auto next = [&]() -> std::string { return i + 1 < args.size() ? args[++i] : std::string(); };
    if(a == "--frames") opt.frames = strtoul(next().c_str(), nullptr, 10);
    else if(a == "--out") opt.out = next();
    else if(a == "--input") opt.input = next();
    else if(a == "--ports") opt.ports = true;
    else if(a == "--trace-joypad") opt.traceJoypad = true;
    else if(a == "--lines") opt.lines = true;
    else if(a == "--region") opt.region = next();
    else if(a == "--fill") opt.fill = next();
    else if(a == "--dump-dir") opt.dumpDir = next();
    else if(a == "--dump-every") opt.dumpEvery = strtoul(next().c_str(), nullptr, 10);
    else if(a == "--rom-id") opt.romId = next();
    else if(a == "--dump-at") {
      auto list = next(); size_t p = 0;
      while(p < list.size()) { size_t e = list.find(',', p); if(e == std::string::npos) e = list.size();
        opt.dumpAt.insert(strtoul(list.substr(p, e - p).c_str(), nullptr, 10)); p = e + 1; }
    } else if(a == "--anchor") {
      auto s = next(); auto c = s.find(':');
      u32 pc = strtoul(s.substr(0, c).c_str(), nullptr, 16);
      opt.anchors.push_back({pc, c == std::string::npos ? "-" : s.substr(c + 1)});
      anchorLast.push_back({pc, 0});
    } else if(a == "--inject") {
      unsigned f, ad, x;
      if(sscanf(next().c_str(), "%u:%x:%x", &f, &ad, &x) != 3) return usage();
      opt.injectFrame = f; opt.injectAddr = ad; opt.injectXor = x;
    } else if(!a.empty() && a[0] == '-') return usage();
    else if(opt.rom.empty()) opt.rom = a;
    else return usage();
  }
  if(opt.rom.empty() || !opt.frames) return usage();
  if(opt.fill != "00" && opt.fill != "ff" && opt.fill != "native") return usage();
  if(opt.region != "auto" && opt.region != "ntsc" && opt.region != "pal") return usage();
  if(!opt.input.empty()) {
    FILE* f = fopen(opt.input.c_str(), "rb");
    if(!f) { fprintf(stderr, "aresref: cannot read %s\n", opt.input.c_str()); return 2; }
    std::string text; char b[4096]; size_t n;
    while((n = fread(b, 1, sizeof b, f)) > 0) text.append(b, n);
    fclose(f);
    std::string error;
    if(!script.parse(text, error)) { fprintf(stderr, "aresref: %s: %s\n", opt.input.c_str(), error.c_str()); return 3; }
  }
  if(!opt.out.empty()) {
    out = fopen(opt.out.c_str(), "w");
    if(!out) { fprintf(stderr, "aresref: cannot write %s\n", opt.out.c_str()); return 2; }
  }
  static char outBuffer[1 << 20];
  setvbuf(out, outBuffer, _IOFBF, sizeof outBuffer);

  ares::Memory::FixedAllocator::get();
  Ref ref;
  ares::platform = &ref;
  mia::setHomeLocation([]() -> string { return {Path::program(), "home/"}; });
  // Cartridge RAM must not survive a run (a saved game would make the next
  // run differ): saves go to a private directory that is removed at the end.
  static std::string saveDir;
  {
    std::string tmpl = (std::filesystem::temp_directory_path() / "aresref-XXXXXX").string();
    if(!mkdtemp(tmpl.data())) { fprintf(stderr, "aresref: cannot create a save directory\n"); return 2; }
    saveDir = tmpl + "/";
  }
  mia::setSaveLocation([]() -> string { return saveDir.c_str(); });
  ref.game = mia::Medium::create("Super Famicom");
  if(ref.game->load(opt.rom.c_str()) != successful) { fprintf(stderr, "aresref: cannot load %s\n", opt.rom.c_str()); return 2; }
  ref.system = mia::System::create("Super Famicom");
  if(ref.system->load() != successful) { fprintf(stderr, "aresref: system load failed\n"); return 2; }
  sfc::option("Pixel Accuracy", "true");
  sfc::option("Deterministic Entropy", "true");
  // fill 00/ff: every power-on value ares would draw from its random
  // generator is zero (patch 0005); memories are then set to the fill.
  if(opt.fill != "native") sfc::option("Zero Entropy", "true");
  bool pal = opt.region == "pal";
  if(opt.region == "auto") {
    // mia reports the regions of the cartridge, e.g. "PAL" or "NTSC, PAL"
    string regions = ref.game->pak->attribute("region");
    pal = regions.beginsWith("PAL");
  }
  if(!sfc::load(ref.root, pal ? "[Nintendo] Super Famicom (PAL)" : "[Nintendo] Super Famicom (NTSC)")) { fprintf(stderr, "aresref: core load failed\n"); return 2; }
  if(auto port = ref.root->find<ares::Node::Port>("Cartridge Slot")) { port->allocate(); port->connect(); }
  if(auto port = ref.root->find<ares::Node::Port>("Controller Port 1")) { port->allocate("Gamepad"); port->connect(); }
  ref.root->power();

  if(opt.fill == "ff") {
    u8 v = 0xff;
    memset(sfc::cpu.wram, v, sizeof sfc::cpu.wram);
    for(auto& w : sfc::ppuImpl.vram.data) w = v | v << 8;
    for(auto& c : sfc::ppuImpl.cgram) c = (v | v << 8) & 0x7fff;
    for(u32 i = 0; i < 544; i++) sfc::ppuImpl.oam.write(i, v);
    memset(sfc::dsp.apuram, v, sizeof sfc::dsp.apuram);
  }

  // ares clocks the APU with the measured 32040 Hz * 768 (clk=meas)
  fprintf(out, "H snesfh 4 oracle=aresref rom=%s fill=%s region=%s clk=meas core=ares-c76aaff\n", opt.romId.c_str(),
          opt.fill.c_str(), pal ? "pal" : "ntsc");
  sfc::oracleHooks.frame = onFrame;
  sfc::oracleHooks.picture = onPicture;
  sfc::oracleHooks.joypad = onJoypad;
  sfc::oracleHooks.ppuWrite = onPpuWrite;
  sfc::oracleHooks.apuWrite = onApuWrite;
  if(!opt.anchors.empty()) sfc::oracleHooks.instruction = onInstruction;

  while(!done) ref.root->run();
  fflush(out);
  if(out != stdout) fclose(out);
  std::error_code ec;
  std::filesystem::remove_all(saveDir, ec);
  return 0;
}

}  // namespace

// Own main instead of nall::main: nall's Arguments rewrites arguments that
// name existing directories into their parent path.
int main(int argc, char** argv) {
  std::vector<std::string> args(argv + 1, argv + argc);
  return run(args);
}
