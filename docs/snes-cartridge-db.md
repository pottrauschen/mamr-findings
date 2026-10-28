# SNES cartridge database

The releases this runtime knows by SHA-1 (runtime/snes/snes_cart.cpp
KNOWN_ROMS): their mapper, SRAM size, enhancement chip, PCB and region,
with the source of each row and its provenance class. The board is
chosen by ROM identity, not by ROM size (docs/snes-hardware-spec.md
section 1.2): a known ROM gets the board of its PCB family where a
source names the PCB, else the board its mapper and SRAM size imply; an
unknown ROM falls back to the header heuristic with a warning; a known
ROM with a chip is refused by name.

Data: research of 2026-10-24 in two independent passes (A and B),
combined here. Pass B checked the hashes against the No-Intro SNES DAT version
2026.10.07 (libretro mirror,
https://raw.githubusercontent.com/libretro/libretro-database/master/metadat/no-intro/Nintendo%20-%20Super%20Nintendo%20Entertainment%20System.dat)
and took the PCB families from the snescentral cartridge pages; pass A
took the "ROM Information" blocks of superfamicom.org (No-Intro names of
2011-12-24) and snescentral PCB pages. Rule of the merge: B's hash and
data where B has them, A only where B says "not found" (Zelda JPN Rev
0-2, Tenchi Souzou, Super Mario Kart JPN and EUR, the Spanish releases,
the SRAM sizes B left open), each row naming its source; where the two
disagree both readings stand, marked CONFLICT. SHA-1 is over the ROM
data without a copier header. Sizes in Mbit (8 Mbit = 1 MiB), SRAM in
Kbit (64 Kbit = 8 KiB).

Classes: DOC = a No-Intro DAT or superfamicom.org listing; DOC+photo =
the PCB from a snescentral cartridge page or board photograph;
INFERENCE = a related release or a forum guess, marked and not used for
the board; "not found" = not found by either pass (which says nothing
about whether the data exists).

Conflicts recorded, not resolved:

- Zelda (Germany) PCB: B (cartridge page) and MAME snes.xml say
  SHVC-1A3B-13, A (the PAL board photo SPAL-ZL-0) says SHVC-1A3M-10.
  Both are LoROM with 64 Kbit SRAM; the families differ in the mask ROM
  package and the decoder (74LS139 against MAD-1), without consequence
  for this 1 MiB ROM with 8 KiB SRAM. The code keeps the 74LS139
  decoding it was verified with against aresref over 3000 frames.
- Super Mario Kart mapper: B says LoROM, A says HiROM. The ROM is
  refused for its DSP-1 either way; the header's map mode byte would
  tell.
- Where a title's boards span both LoROM+SRAM families (Zelda USA and
  EUR, Final Fantasy II USA, Super Mario World EUR), the 74LS139
  decoding is taken for the code (the families give the same map for
  these ROM sizes); the database names every board.

Caveats from the passes: A's No-Intro names are the 2011 listing, and A
checked only Zelda (Germany) against a 2026 DAT (spludlow mirror of
2026-07-28); B's hashes are against the 2026.10.07 DAT. A's Zelda
(France) PCB SHVC-1A3B-SP1 is a forum guess ("I guess", nesdev t=19999)
and is not used. Secret of Mana (Europe)'s PCB was an inference from
the German release before pass B named it. A's "Starwing (Germany)" is
a different ROM from B's: A's hash is listed as the Super Weekend
Competition release without a No-Intro name; both are kept.

Later additions, one source pass each: Contra III - The Alien Wars
(USA), 2026-10-25, for the ROM survey (docs/snes-rom-survey.md F12):
hash against the No-Intro DAT of the libretro mirror, PCB from the
snescentral cartridge page.

## 1. Releases

| Title | Region / revision | SHA-1 | Size | Mapper | SRAM | Chip | PCB | Source | Class |
|---|---|---|---|---|---|---|---|---|---|
| The Legend of Zelda - A Link to the Past | USA | 6D4F10A8B10E10DBE624CB23CF03B88BB8252973 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-12 / SHVC-1A3B-13 / SHVC-1A3M-30 (B; MAME snes.xml zelda3u: SHVC-1A3B-12. Mixed 74LS139 and MAD-1 families: the 74LS139 decoding is taken (same map for this ROM)) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0164 | DOC+photo |
| The Legend of Zelda - A Link to the Past | EUR | 7C073A222569B9B8E8CA5FCB5DFEC3B5E31DA895 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-13 / SHVC-1A3M-10 (B names both families, A SHVC-1A3M-10; the 74LS139 decoding is taken) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0164; A: superfamicom.org (No-Intro 2011-12-24) | DOC+photo |
| The Legend of Zelda - A Link to the Past | DEU | 2E62494967FB0AFDF5DA1635607F9641DF7C6559 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-13 / SHVC-1A3M-10 (CONFLICT: B (snescentral cartridge page) and MAME snes.xml zelda3g say SHVC-1A3B-13, A (snescentral PCB page, PAL board SPAL-ZL-0) says SHVC-1A3M-10. Both LoROM with 64 Kbit SRAM; the families differ in the mask ROM package and decoder, without consequence for this 1 MiB ROM with 8 KiB SRAM. The code keeps the 74LS139 decoding it was verified with against aresref. SHA-1 checked against the DAT of 2026.10.07 (B) and 2026-07-28 (A)) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0164; A: superfamicom.org (No-Intro 2011-12-24) | DOC+photo |
| The Legend of Zelda - A Link to the Past | FRA | 229364A1B92A05167CD38609B1AA98F7041987CC | 8 Mbit | LoROM | 64 Kbit | - | B: the FRA board not found; A: SHVC-1A3B-SP1 is a forum guess (nesdev t=19999), not used | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0164; A: superfamicom.org (No-Intro 2011-12-24) | DOC |
| The Legend of Zelda - A Link to the Past | CAN (FRA) | C1C6C7F76FFF936C534FF11F87A54162FC0AA100 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3M-20 (B: SNS-ZF-0 on SHVC-1A3M-20) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0164 | DOC+photo |
| Zelda no Densetsu - Kamigami no Triforce | JPN Rev 0 | E7E852F0159CE612E3911164878A9B08B3CB9060 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-12 / SHVC-1A3B-13 (B: SHVC-1A3B-12/-13 and the SHVC-ZL-0/-1/-2 boards; A: SHVC-ZL-0 photo) | B (PCB families only, no hashes extracted); A: superfamicom.org (No-Intro 2011-12-24) (hashes) | DOC (hash A, PCB B) |
| Zelda no Densetsu - Kamigami no Triforce | JPN Rev 1 | 52F470C80157F6843839C39E3BF52AFBB42FB957 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-12 / SHVC-1A3B-13 (as Rev 0) | B (PCB families only, no hashes extracted); A: superfamicom.org (No-Intro 2011-12-24) (hashes) | DOC (hash A, PCB B) |
| Zelda no Densetsu - Kamigami no Triforce | JPN Rev 2 | 6D9FA9006C160A0C81DB913BCD0EA3E7CC249BC9 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-12 / SHVC-1A3B-13 (as Rev 0) | B (PCB families only, no hashes extracted); A: superfamicom.org (No-Intro 2011-12-24) (hashes) | DOC (hash A, PCB B) |
| Secret of Mana | USA | 8133041A363E3CC68CEDEF40B49B6D20D03C505D | 16 Mbit | HiROM | 64 Kbit | - | SHVC-2J3M-01 / SHVC-1J3M-01 / SHVC-1J3M-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0603 | DOC+photo |
| Secret of Mana | EUR | D9AAF3119784887475DA9548000738E1DA84BEE6 | 16 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-11 (B (snescentral); before: INFERENCE from MAME manag) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0603 | DOC+photo |
| Secret of Mana | EUR Rev 1 | CF57DC4183C6E5AADBA25019D82E61C44C0DE113 | 16 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0603 | DOC+photo |
| Secret of Mana | DEU | AB8A31BFB4CF0CE19B96893A31442FFBFD8D0BEB | 16 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-11 (also MAME snes.xml manag) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0603 | DOC+photo |
| Secret of Mana | FRA | D5601BE19DE691E58EDD55194E10496C77E464E5 | 16 Mbit | HiROM | 64 Kbit | - | the FRA board not found | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| Secret of Mana | FRA Rev 1 | C1FF73EA67833748DBD4ECD393D3565E3AE1925D | 16 Mbit | HiROM | 64 Kbit | - |  | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| Seiken Densetsu 2 | JPN | B78A9A844D165345631CEA1B5246C8FCBCDBC162 | 16 Mbit | HiROM | 64 Kbit | - |  | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| Final Fantasy II (FF IV) | USA | 2FA447E3E010CE8BA5B4E746F6609AA0E324D947 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-12 / SHVC-1A3B-11 / SHVC-1A3B-13 (B; A: SNS-F4-1 on SHVC-1A3M-10 (revision not assigned). Mixed families: the 74LS139 decoding is taken) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0028; A: superfamicom.org (No-Intro 2011-12-24) | DOC+photo |
| Final Fantasy II (FF IV) | USA Rev 1 | 41A74EB369A7A91815529EF99AB1B20E2BDF3E26 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-12 / SHVC-1A3B-11 / SHVC-1A3B-13 / SHVC-1A3M-10 (B: Rev 1 also on 1A3M-10; mixed families, 74LS139 decoding taken) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0028; A: superfamicom.org (No-Intro 2011-12-24) | DOC+photo |
| Final Fantasy IV | JPN | 7502ED13FE969B294AAB9EA3600DD8341713CD03 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0028 | DOC+photo |
| Final Fantasy IV | JPN Rev 1 | EAC14578B3465FFCE874119005F9B244E8565A79 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0028 | DOC+photo |
| Final Fantasy IV - Easy Type | JPN | A2D04C5F3948CA930D2C0BC4E6F34D62F06A9FA5 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0028 | DOC+photo |
| Final Fantasy V | JPN | E937B54FFF99838E2E853697E4F559359AA91FD6 | 16 Mbit | HiROM | 64 Kbit | - | SRAM: B not found, A 64 Kbit | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Final Fantasy III (FF VI) | USA | 4F37E4274AC3B2EA1BEDB08AA149D8FC5BB676E7 | 24 Mbit | HiROM | 64 Kbit | - | SHVC-BJ3M-10 / SHVC-BJ3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0043 | DOC+photo |
| Final Fantasy III (FF VI) | USA Rev 1 | 057ADA1C641E3E0B3CA34E6E4F4EB1B05A87143A | 24 Mbit | HiROM | 64 Kbit | - | SHVC-BJ3M-10 / SHVC-BJ3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0043 | DOC+photo |
| Final Fantasy VI | JPN | 1C6A6DD90D3463F4532202199885A2C0E9A485F6 | 24 Mbit | HiROM | 64 Kbit | - | SHVC-3J3M-01 / SHVC-BJ3M-10 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0043 | DOC+photo |
| Chrono Trigger | USA | DE5822F4F2F7A55ACB8926D4C0EAA63D5D989312 | 32 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0282 | DOC+photo |
| Chrono Trigger | JPN | A82F0FBA9BB111FFD0A878853A4563917D9B67BB | 32 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0282 | DOC+photo |
| Terranigma | EUR | 911239B4B21106AE4A284454D345C55554985525 | 32 Mbit | HiROM | 64 Kbit | - | SRAM: B not found, A 64 Kbit | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Terranigma | DEU | 018701E5CE385E0B32E61B8F8BB2F9ABF8ABF8F0 | 32 Mbit | HiROM | 64 Kbit | - | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Terranigma | DEU Rev 1 | 9A64CE79BEA16D01AB71B58B11DF0BCF0EEDD889 | 32 Mbit | HiROM | 64 Kbit | - | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Terranigma | FRA | 4F8A5771CB11757A31A026E5892B9434A3A405CB | 32 Mbit | HiROM | 64 Kbit | - | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Terranigma | ESP | 1E1A85CF28BCB69CB34FC71F48347279D7CFEA7E | 32 Mbit | HiROM | 64 Kbit | - | A only | A: superfamicom.org (No-Intro 2011-12-24) | DOC |
| Tenchi Souzou (Terranigma) | JPN | F787672E766A43A73D9BD310FCB3C2CAC024B227 | 32 Mbit | HiROM | 64 Kbit | - | A only (B: hash not extracted) | A: superfamicom.org (No-Intro 2011-12-24) | DOC |
| Illusion of Gaia | USA | 38DE0C84DD2BC3BDFC0A3D7AB0220C79B70887C3 | 16 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-11 / SHVC-1J3B-01 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0387 | DOC+photo |
| Illusion of Time | EUR | D1CF72EA3971EDB4B706A0BD3CA756B016A6B17E | 16 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0387 | DOC+photo |
| Illusion of Time | DEU | 24711CE599F1F61E9B3CAC3D117D5D9C37FF759F | 16 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0387 | DOC+photo |
| Illusion of Time | DEU Rev 1 | D3FF5ADF858D7E56A67577AC6042C26565C240DF | 16 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0387 | DOC+photo |
| Illusion of Time | FRA | 025ED8B698B66100DBBEB66B8A91AF2EA9D742F9 | 16 Mbit | HiROM | 64 Kbit | - | the FRA board not found | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| Illusion of Time | ESP | F236E4A5FFAA7431540DBAEB98716B3E84CFA455 | 16 Mbit | HiROM | 64 Kbit | - | A only | A: superfamicom.org (No-Intro 2011-12-24) | DOC |
| Gaia Gensouki | JPN | 01BD54E220D5208433ECFDF0B9FA1A08B2260A89 | 16 Mbit | HiROM | 64 Kbit | - | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Super Metroid | JPN+USA | DA957F0D63D14CB441D215462904C4FA8519C613 | 24 Mbit | LoROM | 64 Kbit | - | SHVC-3A3M-01 / SHVC-BA3M-01 / SHVC-BA3M-10 (B: JPN boards; the US board not extracted) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0885 | DOC+photo |
| Super Metroid | EUR | 082ADAC9E38F86240F4378A6AA400DEE1716AE87 | 24 Mbit | LoROM | 64 Kbit | - | SHVC-BA3M-10 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0885 | DOC+photo |
| Super Mario World | USA | 6B47BB75D16514B6A476AA0C73A683A2A4C18765 | 4 Mbit | LoROM | 16 Kbit | - | SHVC-1A1B-04 (A adds SHVC-1A1B-05) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0000; A: superfamicom.org (No-Intro 2011-12-24) | DOC+photo |
| Super Mario World | EUR | 56265120A74B55260FF7CACC00DA1F21CBCB64F4 | 4 Mbit | LoROM | 16 Kbit | - | SHVC-1A1B-05 / SHVC-1A1B-06 / SHVC-1A1M-20 (mixed families: the 74LS139 decoding is taken) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0000 | DOC+photo |
| Super Mario World | EUR Rev 1 | 46BF36BE1C3A2CE9DE7581323370BD2D891AD5A1 | 4 Mbit | LoROM | 16 Kbit | - | SHVC-1A1B-05 / SHVC-1A1B-06 / SHVC-1A1M-20 (as Rev 0) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0000 | DOC+photo |
| Super Mario World - Super Mario Bros. 4 | JPN | F977AFABF24ED269D86366209A460450BBC37E76 | 4 Mbit | LoROM | 16 Kbit | - | SHVC-1A1B-01 / SHVC-1A1B-03 / SHVC-1A1B-06 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0000 | DOC+photo |
| Seiken Densetsu 3 | JPN | 209C55FD2A8D7963905E3048B7D40094D6BEA965 | 32 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=1038 | DOC+photo |
| EarthBound | USA | D67A8EF36EF616BC39306AA1B486E1BD3047815A | 24 Mbit | HiROM | 64 Kbit | - | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Mother 2 - Gyiyg no Gyakushuu | JPN | 8738CFF9E38A8B86AE30BFE0E5FBCB2828C2B16E | 24 Mbit | HiROM | 64 Kbit | - | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Breath of Fire II | USA | 1F7707E606B7E9FA8FB3908BBDDFCB5DEA93D776 | 24 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0251 | DOC+photo |
| Breath of Fire II | EUR | D429DBCBFAE8C8D1749029841002A8DEC6F55890 | 24 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0251 | DOC+photo |
| Breath of Fire II - Shimei no Ko | JPN | 9A1CFC03F27710DE04083D709A4C18F90B431947 | 20 Mbit | HiROM | 64 Kbit | - | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Breath of Fire II - Shimei no Ko | JPN Rev 1 | 1062FB9E1F70E4855EDFB55811B93CEA55F918EB | 20 Mbit | HiROM | 64 Kbit | - | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Lufia II - Rise of the Sinistrals | USA | A89931C1F29B161B8BE717DFAB4A4ADB54B42B84 | 20 Mbit | LoROM | 64 Kbit | - | SHVC-1A3M-30 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0063 | DOC+photo |
| Lufia (Lufia II) | EUR | 495686E039759B400B557D1EC3CF040336ADF343 | 20 Mbit | LoROM | 64 Kbit | - | SHVC-1A3M-30 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0063 | DOC+photo |
| Lufia (Lufia II) | DEU | 858197F17AC8081BD7D43F4089A75785A2016C6C | 24 Mbit | LoROM | 64 Kbit | - | SHVC-1A3M-30 (B: PAL family SHVC-1A3M-30) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0063 | DOC+photo |
| Estpolis Denki II | JPN | FB532E487094037ABA6CFFA0F3D922383E73CB5F | 20 Mbit | LoROM | 64 Kbit | - | SHVC-BA3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0063 | DOC+photo |
| Donkey Kong Country | USA | 0FCEE45D9AF5D2F62995ED4B04D22146B906C86B | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M / SHVC-BJ1M family | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0105 | DOC+photo |
| Donkey Kong Country | USA Rev 1 | 8EE954E15B7D77A7941B107C8243B27ACEBDCBC0 | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M / SHVC-BJ1M family | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0105 | DOC+photo |
| Donkey Kong Country | USA Rev 2 | CD606E77AB2034438E06891CD2D067DAD69B4D1A | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M / SHVC-BJ1M family | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0105 | DOC+photo |
| Donkey Kong Country | EUR | 535A5B674859A78852A1ED70B00ECA5EA5BE8417 | 32 Mbit | HiROM | 16 Kbit | - | SHVC-BJ1M-10 / SHVC-BJ1M-20 / SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0105 | DOC+photo |
| Donkey Kong Country | EUR Rev 1 | 6F246ABAE39820E3267704BDF342AD1D27121F19 | 32 Mbit | HiROM | 16 Kbit | - | SHVC-BJ1M-10 / SHVC-BJ1M-20 / SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0105 | DOC+photo |
| Super Donkey Kong | JPN | 6F02031B6B50D033958C4923AD05333ED78F22D8 | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0105 | DOC+photo |
| Super Donkey Kong | JPN Rev 1 | DF02860E691FBEE453E345DD343C08B6DA08D4EA | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0105 | DOC+photo |
| Donkey Kong Country 2 - Diddy's Kong Quest | USA | 3EC2035962918B5523D8B4745406F46F2A739B8D | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 / SHVC-BJ1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0311 | DOC+photo |
| Donkey Kong Country 2 - Diddy's Kong Quest | USA Rev 1 | 69D0F91BFD05837B44023E33A6699AA28FCA19CB | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 / SHVC-BJ1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0311 | DOC+photo |
| Donkey Kong Country 2 - Diddy's Kong Quest | EUR Rev 1 | 29601B586C57C1F5DA8956B640E5FC48DCC4364F | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0311 | DOC+photo |
| Donkey Kong Country 2 - Diddy's Kong Quest | DEU | DC6A271AD77B49E59CB86CBA0B7799845D7347A0 | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0311 | DOC+photo |
| Donkey Kong Country 2 - Diddy's Kong Quest | DEU Rev 1 | 5A5EE7C1E3D36530C3EBF98BDCED2C9C3A0313AB | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0311 | DOC+photo |
| Super Donkey Kong 2 - Dixie & Diddy | JPN | 5ED7ECD3AA25BB37B6605BACC6120F5EBCD9AA5F | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0311 | DOC+photo |
| Super Donkey Kong 2 - Dixie & Diddy | JPN Rev 1 | 710903D52EC009BB7A54CD5CCDFDC93594E440E2 | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0311 | DOC+photo |
| Donkey Kong Country 3 - Dixie Kong's Double Trouble! | USA | D737E90D91DBA8620FD5C2985EB6FF2CDA7F23F9 | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0040 | DOC+photo |
| Donkey Kong Country 3 - Dixie Kong's Double Trouble! | EUR | C79CBE60E4CD8EE086BB6C5F6B2DEA5ACEBCC940 | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0040 | DOC+photo |
| Super Donkey Kong 3 - Nazo no Krems-tou | JPN | 6FA9DF8CF91F062D067C2206622E4B7244322F6F | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0040 | DOC+photo |
| Super Donkey Kong 3 - Nazo no Krems-tou | JPN Rev 1 | E4137A6E9D9A7AC836F8E568D44BDAF0451C664E | 32 Mbit | HiROM | 16 Kbit | - | SHVC-1J1M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0040 | DOC+photo |
| Super Mario RPG - Legend of the Seven Stars | USA | A4F7539054C359FE3F360B0E6B72E394439FE9DF | 32 Mbit | LoROM (SA-1) | 256 Kbit | SA-1 | SHVC-1L5B-10 / SHVC-1L5B-02 / SHVC-1L5B-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0049 | DOC+photo |
| Super Mario RPG | JPN | A9CD97041C4F8ACF135D1FFB0A172748B5B976DE | 32 Mbit | LoROM (SA-1) | 256 Kbit | SA-1 | SHVC-1L5B-02 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0049 | DOC+photo |
| Star Fox | USA | 1F5355534CCFAF26AE6C8F055F3E4768F9D72A7E | 8 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (MC1) | the US board not extracted | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0636 | DOC |
| Star Fox | USA Rev 1 | 1D1CCFFF6B4EB5389C28A91F754C12B7614158C3 | 8 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (MC1) | B only | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0636 | DOC |
| Star Fox | USA Rev 2 | CF08148CD8F26D51F8C67C956179DFC594E7A4F1 | 8 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (MC1) |  | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0636 | DOC |
| Star Fox | JPN | A2DCEAB341EF20C836D4D3426F37F0EC396BBDCB | 8 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (MC1) | SHVC-1C0N / SHVC-1C0N5S-01 / SHVC-1C0N5S-02 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0636 | DOC+photo |
| Star Fox | JPN Rev 1 | 39FF7354A7FA02295C899B7A7EC3556998AC2636 | 8 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (MC1) | SHVC-1C0N / SHVC-1C0N5S-01 / SHVC-1C0N5S-02 (A listed the hash without data; size, mapper and chip from B) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0636; A: superfamicom.org (No-Intro 2011-12-24) | DOC+photo |
| Starwing | EUR | 7BA89019F33F690715BDBD52E13D888228EE4B9C | 8 Mbit | LoROM (GSU) | 256 Kbit | SuperFX | SNSP-1C0N5S family | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0636 | DOC+photo |
| Starwing | EUR Rev 1 | 0510647F8CF9B87FAC1C08A7009932CEEAE1E0BD | 8 Mbit | LoROM (GSU) | 256 Kbit | SuperFX | SNSP-1C0N5S family | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0636 | DOC+photo |
| Starwing | DEU | 7C365C325B3CE27A17FC88744B6928741FAB1996 | 8 Mbit | LoROM (GSU) | 256 Kbit | SuperFX | SNSP-1C0N5S-01 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0636 | DOC+photo |
| Starwing (Super Weekend Competition) | DEU | DAF6C7BDBF8C9733705B1C586C85BE9EDD864A23 | 8 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (MC1) | A only, listed there as the DEU Super Weekend release without a No-Intro name; not in B | A: superfamicom.org (No-Intro 2011-12-24) | DOC |
| Super Mario World 2 - Yoshi's Island | USA | C807F2856F44FB84326FAC5B462340DCDD0471F8 | 16 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (GSU-2) | the US board not extracted | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0674 | DOC |
| Super Mario World 2 - Yoshi's Island | USA Rev 1 | 34612A93741F156D6E497462AB7F253CB8A959A0 | 16 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (GSU-2) |  | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0674 | DOC |
| Super Mario World 2 - Yoshi's Island | EUR | 512E0B2AB74081FDA5FF5459162948D28226FC0B | 16 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (GSU-2) | SHVC-1CB5B-01 / SHVC-1CB5B-20 family | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0674 | DOC+photo |
| Super Mario World 2 - Yoshi's Island | EUR Rev 1 | 1E1DC02C684652F9E927F3873AF65EA4B374BB80 | 16 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (GSU-2) | SHVC-1CB5B-01 / SHVC-1CB5B-20 family | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0674 | DOC+photo |
| Super Mario World 2 - Yoshi's Island | EUR Rev 2 | 09402FF319D4517409F961B4012E5EEB1B89AC5C | 16 Mbit | LoROM (GSU) | 256 Kbit | SuperFX (GSU-2) | SHVC-1CB5B-01 / SHVC-1CB5B-20 family | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0674 | DOC+photo |
| Super Mario Kart | USA | 47E103D8398CF5B7CBB42B95DF3A3C270691163B | 4 Mbit | LoROM (B) / HiROM (A) | 16 Kbit | DSP-1 / DSP-1B | SHVC-1K1B-01 / SHVC-1K1X-10 (CONFLICT on the mapper: B says LoROM, A says HiROM; not resolved here (refused for the chip either way; the header's map mode byte would tell). A: SHVC-1K1B-01 (1992), later SHVC-1K1X-10) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0166; A: superfamicom.org (No-Intro 2011-12-24) | DOC+photo |
| Super Mario Kart | JPN | CBB853BF911255C1D8EB27CD34FC7855A0DDA218 | 4 Mbit | LoROM (B) / HiROM (A) | 16 Kbit | DSP-1 | hash from A (B: not extracted); mapper conflict as USA | A: superfamicom.org (No-Intro 2011-12-24); B (mapper) | DOC |
| Super Mario Kart | EUR | 27D9B4F30D39AF75075691344B7BDEEDBD32AC19 | 4 Mbit | LoROM (B) / HiROM (A) | 16 Kbit | DSP-1 / DSP-1A / DSP-1B | SHVC-1K1B-01 / SHVC-1K1X-01 / SHVC-1K1X-10 (hash from A (B: not extracted); chip and board by production batch (A and B); mapper conflict as USA) | A: superfamicom.org (No-Intro 2011-12-24); B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0166 | DOC+photo |
| Kirby Super Star | USA | CCA1E67FA230BF4F60154F5EA55D06568229DC5D | 32 Mbit | LoROM (SA-1) | 64 Kbit | SA-1 | SRAM: B not found, A 64 Kbit | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Kirby's Fun Pak | EUR | CE325AD271E91735CE19E9C2B8E0AD04DC103AE1 | 32 Mbit | LoROM (SA-1) | none / not found | SA-1 | B only; SRAM not found | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| Hoshi no Kirby Super Deluxe | JPN | 2F2FF2C75EAFA705363FEB435A88D2C914D301CF | 32 Mbit | LoROM (SA-1) | none / not found | SA-1 | B only; SRAM not found | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| Hoshi no Kirby Super Deluxe | JPN Rev 1 | 63F47B5F47BEC60147B9E75A71B3F038E5E0969E | 32 Mbit | LoROM (SA-1) | none / not found | SA-1 | B only; SRAM not found | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| Hoshi no Kirby Super Deluxe | JPN Rev 2 | 9AE2DB3BCB2699394937BC007CD6835609B7E18F | 32 Mbit | LoROM (SA-1) | 64 Kbit | SA-1 | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |
| Secret of Evermore | USA | 79E7738630FFF5699217EF58ECC421BC8FCBCD89 | 24 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0602 | DOC+photo |
| Secret of Evermore | EUR | AE17166919FDFDF26CC5771F83CFD19EAF71806C | 24 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0602 | DOC+photo |
| Secret of Evermore | DEU | 5E5C2082526690D05F962C3FFBD7E080C681BFA4 | 24 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0602 | DOC+photo |
| Secret of Evermore | FRA | 8A430C9D6A3DCEF974252FE8D946A0D619BB1A61 | 24 Mbit | HiROM | 64 Kbit | - | SHVC-1J3M-20 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0602 | DOC+photo |
| Secret of Evermore | ESP | 4363CE4B19E76261F9325AC9A0CCE27D97490DF2 | 24 Mbit | HiROM | 64 Kbit | - | A only | A: superfamicom.org (No-Intro 2011-12-24) | DOC |
| Super Castlevania IV | USA | 684C1DFAFF8E5999422C24D48054D96BB12DA2F4 | 8 Mbit | LoROM | none / not found | - | SHVC-1A0N-01 / Majesco MAXI-1A0N-30 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0002 | DOC+photo |
| Super Castlevania IV | EUR | 14F37BECE9B419B59911325C4595C975E5746823 | 8 Mbit | LoROM | none / not found | - | SHVC-1A0N-02 / SHVC-1A0N-20 (B only) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0002 | DOC+photo |
| Akumajou Dracula | JPN | 9DF4028BC19EE63DE884C26921135C721C882E34 | 8 Mbit | LoROM | none / not found | - |  | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| Contra III - The Alien Wars | USA | 265886E3F665ADF2507E7B2F08B6B2ED9D0018B2 | 8 Mbit | LoROM | none | - | SHVC-1A0N-01 / SHVC-1A0N-02 / SHVC-1A0N-10 / SHVC-1A0N-20 (mask ROM SNS-CS-0 on all four, by production date; A0N: no SRAM, no decoder). Header map mode byte $FFD5 holds the 22nd title character 'S' ($53), so the board can only come from this entry (docs/snes-rom-survey.md F12) | No-Intro DAT of the libretro mirror, read 2026-10-25 (CRC32 84DA7CFE); https://snescentral.com/article.php?id=0294; header bytes measured on the dump (chipset $00, SRAM $00, country $01, checksum 0c3c valid) | DOC+photo |
| Mega Man X | USA | 449A00631208FBCC8D58209E66D0D488674B7FB1 | 12 Mbit | LoROM | none / not found | - | SHVC-2A0N-01 / SHVC-2A0N-11 / Majesco MAXI-1A0N-30-2 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0472 | DOC+photo |
| Mega Man X | USA Rev 1 | C65216760BA99178100A10D98457CF11496C2097 | 12 Mbit | LoROM | none / not found | - | SHVC-2A0N-01 / SHVC-2A0N-11 / Majesco MAXI-1A0N-30-2 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0472 | DOC+photo |
| Mega Man X | EUR | 8A32570FAD3BFC92C0508C88022FB20412DD7BED | 12 Mbit | LoROM | none / not found | - | SHVC-2A0N-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0472 | DOC+photo |
| Rockman X | JPN | 86C18BA1FC762B6D0BCDEE7314A29B5C97CAC082 | 12 Mbit | LoROM | none / not found | - |  | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| Rockman X | JPN Rev 1 | 03F8F99D27874465F8D3E5EC9628927AC5BE6FAE | 12 Mbit | LoROM | none / not found | - |  | B: No-Intro DAT 2026.10.07 (libretro mirror) | DOC |
| ActRaiser | USA | E8365852CC20178D42C93CD188A7AE9AF45369D7 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-11 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0177 | DOC+photo |
| ActRaiser | EUR | B76621E0B9D882C8B8463203F5423CA7D45CC5BF | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-13 | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0177 | DOC+photo |
| ActRaiser | DEU | 2BE890711DEC987CA1375C0B5D0844997DE96566 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-13 (B: PAL family SHVC-1A3B-13) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0177 | DOC+photo |
| ActRaiser | FRA | 2F913B33F8C2B4EA2CA18AC91F3ED08F02285227 | 8 Mbit | LoROM | 64 Kbit | - | SHVC-1A3B-13 (B: PAL family SHVC-1A3B-13) | B: No-Intro DAT 2026.10.07 (libretro mirror); https://snescentral.com/article.php?id=0177 | DOC+photo |
| Actraiser | JPN | F031FC983A2EED4D69E223B256ECE5F037FB5D5D | 8 Mbit | LoROM | 64 Kbit | - | SRAM from A | B: No-Intro DAT 2026.10.07 (libretro mirror); A: superfamicom.org (No-Intro 2011-12-24) (SRAM) | DOC |

Gaps (not in the code table):

| Title | Region | What is missing | Source |
|---|---|---|---|
| Lufia II | ESP, NLD, FRA | B: no separate DAT entry for FRA; A: Spain hash EAF67E123573CA50D7FB8828C59E4F7A1DF23FA2 without size or mapper, Netherlands name only | both passes |
| Yoshi's Island | JPN | hash not extracted (B: GSU-2 / GSU-2-SP1, SHVC-1CB5B-01/-20, 2 MiB, 256 Kbit) | B, https://snescentral.com/article.php?id=0674 |
| Super Mario Kart | DEU, FRA | no separate DAT entry | B |
| Donkey Kong Country | DEU, FRA | no separate DAT entry (A: page truncated) | both passes |
| Seiken Densetsu 3, EarthBound, Super Mario RPG, Secret of Evermore (JPN) | outside JPN / USA | not released, per B | B |
| Final Fantasy IV, V, VI; Chrono Trigger; Terranigma (USA) | PAL / USA | no original release in the DAT, per B | B |

## 2. Enhancement chips and firmware

Of the chips above, this runtime provides none; a known ROM with one is
refused by name, an unknown one by its header (map mode or chipset).
Which chips need a firmware dump: pass B read ares' resource manifest
(https://github.com/ares-emulator/ares/blob/master/mia/resource/resource.bml):
ares lists external firmware for Cx4, DSP-1, DSP-1B, DSP-2, DSP-3,
DSP-4, ST010 and ST011, and none for SA-1, GSU, S-DD1, SPC7110, OBC1
and S-RTC (a statement about ares, not about whether a chip has an
internal mask ROM). Pass A read the higan import documentation
(https://higan.readthedocs.io/en/stable/guides/import/), which agrees
and adds ST018. Sizes and SHA-1 of the firmware files per pass B
(resource.bml and the retrobios catalogue,
https://github.com/Abdess/retrobios/blob/main/install/bizhawk.json,
which also gives SHA-256 values):

| Chip | Firmware for ares | Size | SHA-1 | Titles in section 1 |
|---|---|---|---|---|
| DSP-1 | yes | 8192 bytes | 188D471FEFEA71EB53F0EE7064697FF0971B1014 | Super Mario Kart |
| DSP-1B | yes | 8192 | 78B724811F5F18D8C67669D9390397EB1A47A5E2 | Super Mario Kart (later batches) |
| DSP-2 | yes | 8192 | 198C4B1C3BFC6D69E734C5957AF3DBFA26238DFB | none |
| DSP-3 | yes | 8192 | 558DA7CB3BD3876A6CA693661FFC6C110E948CF9 | none |
| DSP-4 | yes | 8192 | AF6478AECB6F1B67177E79C82CA04C56250A8C72 | none |
| ST010 | yes | 53248 | 6472828403DE3589433A906E2C3F3D274C0FF008 | none |
| ST011 | yes | 53248 | FECBAE2CEC76C710422486BAA186FFA7CA1CF925 | none |
| ST018 | per higan yes (program 131072 + data 32768); not in ares' manifest | | the higan documentation lists the same SHA-256 values as for ST011, very likely a copy error there; verify before use | none |
| Cx4 | yes (data ROM) | 3072 | A002F4EFBA42775A31185D443F3ED1790B0E949A | none (Mega Man X has no Cx4; X2 and X3 have one) |
| SA-1 | no | | | Super Mario RPG, Kirby Super Star / Fun Pak / Super Deluxe |
| SuperFX GSU-1 (MC1), GSU-2 | no | | | Star Fox / Starwing (MC1), Yoshi's Island (GSU-2) |
| S-DD1, SPC7110, OBC1, S-RTC | no | | | none |

Liberal implementations of these chips: ares (ISC, main licence; the
repository also carries separately licensed third-party components)
for every chip above; no hardware-tested test ROM for any of them was
found by either pass. LakeSnes, cited in the specifications as a
behaviour reference only: no licence file found (pass B, repository
archived), so it is not to be called MIT, ISC or BSD anywhere in this
repository.

## 3. Zelda - A Link to the Past: releases

Internal title and header checksum per release (pass A, superfamicom.org;
pass B confirmed the USA, EUR, DEU, FRA and CAN hashes against the DAT
and could not extract the JPN hashes or the header fields):

| Release | SHA-1 | Internal title | Checksum |
|---|---|---|---|
| USA Rev 0 | 6D4F10A8B10E10DBE624CB23CF03B88BB8252973 (SHA-256 66871D66...9CFB) | THE LEGEND OF ZELDA | AF0D |
| JPN Rev 0 | E7E852F0159CE612E3911164878A9B08B3CB9060 | ZELDANODENSETSU | CDC8 |
| JPN Rev 1 | 52F470C80157F6843839C39E3BF52AFBB42FB957 | ZELDANODENSETSU | 0D90 |
| JPN Rev 2 | 6D9FA9006C160A0C81DB913BCD0EA3E7CC249BC9 | ZELDANODENSETSU | 0BE3 |
| EUR | 7C073A222569B9B8E8CA5FCB5DFEC3B5E31DA895 | THE LEGEND OF ZELDA | 75B9 |
| DEU | 2E62494967FB0AFDF5DA1635607F9641DF7C6559 | THE LEGEND OF ZELDA | 50B6 |
| FRA | 229364A1B92A05167CD38609B1AA98F7041987CC | LA LEGENDE DE ZELDA | 65AE |
| CAN (FRA) | C1C6C7F76FFF936C534FF11F87A54162FC0AA100 | LA LEGENDE DE ZELDA | B8BC |

snesrev/zelda3 (MIT, v0.3) is built on the USA ROM only; a German ROM
serves it only to extract the dialogue; neither pass found PAL code
support, symbol or address tables for the German release, or 50 Hz
timing notes. A local dump of the German release matches the SHA-1
above (ctest `snes_rom`, with the ROM present).
