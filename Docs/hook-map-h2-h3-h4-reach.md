# Chapter / mission-complete hook map: H2, H3, H4, Reach

Mappings for the equivalents of the Halo CE hooks in `HaloAP_DLL/hooks/chapter_title.cpp`
(chapter reached) and `mission_complete.cpp` (mission won + current mission name).
Not implemented yet. Every hook below was hit live under x64dbg (MCC on Proton, EAC off)
on 2026-09-28.

RVAs are relative to each game's DLL. The DLLs are relocated on every load, so resolve
them with the patterns (`FindPatternInModule`), not with fixed addresses. Patterns were
generated from the shipped DLLs and each one matches exactly once in `.text`.

## DLL lifetime

MCC loads every game DLL (`halo1.dll` … `haloreach.dll`, `groundhog.dll`) at startup and
again each time you return to the menu. Starting a mission **unloads every other game's
DLL**, so hooks have to be installed per game after its DLL is (re)loaded.

## Hooks

| Game | Event | RVA | Pattern | Notes |
|---|---|---|---|---|
| H2 | chapter | `halo2+0x6F5280` | `40 57 48 83 EC 20 48 8B 05 ? ? ? ? 0F B7 F9` | `(short title_index)`. Fired idx 0 at The Armory start and Cairo Station "Home Field Advantage". |
| H2 | mission won | `halo2+0x6A7AD0` | `48 83 EC 28 E8 ? ? ? ? 84 C0 74 ? 48 8D 0D ? ? ? ?` | Fired at the end of The Armory. |
| H3 | chapter | `halo3+0x189114` | `48 83 EC 28 8B 15 ? ? ? ? 45 33 C0` | `(short title_index, float)`, same shape as CE's `cinematic_set_title`. Fired idx 0 at Sierra 117's opening title. |
| H3 | mission won | `halo3+0xF053C` | `48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 E8 ? ? ? ? 33 FF` | Fired at the end of Arrival. |
| H4 | chapter | `halo4+0x12D738` | `48 83 EC 28 8B 15 ? ? ? ? 45 33 DB 65 48 8B 04 25 58 00 00 00 44 8B D1` | `(short title_index, float)`. The index is into the map's title block and does **not** start at 0: Dawn's first title was idx 5. |
| H4 | mission won | `halo4+0x9CCA8` | `48 83 EC 28 E8 ? ? ? ? 84 C0 74 ? 8B 0D ? ? ? ? 65 48 8B 04 25 58 00 00 00 BA 40 00 00 00 48 8B 04 C8 48 8B 0C 02` | Fired at the end of Prologue. Do **not** hook its callee `+0x9CDF0`: that one also fires when quitting to the menu. |
| Reach | chapter | `haloreach+0x1B45B4` | body pattern below; function start = match − `0x2E` | Script function #1309 `chud_show_screen_chapter_title (string_id)`. See the Reach section below. |
| Reach | mission won | `haloreach+0x1B0810` | `48 83 EC 28 44 8B D2 E8 ? ? ? ? 84 C0 74 ? 8B 0D ? ? ? ? 65 48 8B 04 25 58 00 00 00 BA 48 00 00 00` | Fired at the end of Noble Actual. Do **not** hook its callee `+0x59330`: that one also fires when quitting to the menu. |

Reach chapter body pattern (anchored at `+0x1B45E2`):
`8B 15 ? ? ? ? 8B 00 65 48 8B 0C 25 58 00 00 00 41 B8 B0 05 00 00 48 8B 0C D1 4A 8B 14 01 8B CB 89 82 6C 01 00 00`

### Reach chapter titles are different

Reach does **not** show chapter cards through `cinematic_set_title`. That's
`haloreach+0xD388C` (pattern `48 83 EC 28 8B 15 ? ? ? ? 45 33 C0 65 48 8B 04 25 58 00 00 00 41 BA E0 00 00 00`),
and missions only use it for transmission and objective cards.
Chapter cards come from `global_scripts.hsc`:

```
(script static void (f_hud_chapter (string_id string_hud))
    (chud_cinematic_fade 0 30) (sleep 10)
    (chud_show_screen_chapter_title string_hud)          ; <- hook this
    (chud_fade_chapter_title_for_player player0 1 30) ... (sleep 120) ...
    (chud_show_screen_chapter_title "")                   ; clears it again
    (sleep 10) (chud_cinematic_fade 1 30))
```

Reach's script function names are stripped from the DLL. Function #1309 was identified from
its signature (a single `string_id`), then confirmed live: it runs between the two
`chud_cinematic_fade` calls (#1275) that bracket the per-player title fades (#1273).
It has no separate implementation routine. The script entry point itself stores the
string_id at `[TLS slot + 0x5B0] + 0x16C` (the store is at `+0x1B4603`, with the value in `eax`).
Two ways to hook it:

- detour the entry point, then read `+0x16C` after the original returns: non-zero means a
  chapter card went up, 0 means the `""` clear call;
- or detour mid-function at `+0x1B4603`.

string_ids are specific to each map, so identify the chapter by `(mission, order of non-zero calls)`,
or resolve the string_id through the map's string table.

## Current mission

Every game keeps a copy of the loaded map's cache header in its DLL's `.data`:
build date string, then the map name at `+0x20`, then the scenario path at `+0x40`.
This is the equivalent of CE's `halo1.dll+0x1BE9C80`.

| Game | Map name | Scenario path | Example | Also |
|---|---|---|---|---|
| H2 | not found yet | `halo2+0x15A0B0C` | `scenarios\solo\01b_spacestation\...` | |
| H3 | `halo3+0x20A9118` | `halo3+0x20A9138` | `010_jungle`, `levels\solo\010_jungle\010_jungle` | Second copy at `+0x20F6650`/`+0x20F6670`; game-options path at `+0xB447C0` |
| H4 | `halo4+0x2A30268` | `halo4+0x2A30288` | `m10_crash`, `environments\solo\m10_crash\m10_crash` | Game-options path at `+0x1159C80` |
| Reach | `haloreach+0x274DD70` | `haloreach+0x274DD90` | `m10`, `levels\solo\m10\m10` | Game-options path at `+0xFD7140` |

These offsets hold for the current MCC build: H3 "Dec 21 2023 22:31:37",
H4 "Apr 1 2023 17:35:22", Reach "Jun 21 2023 15:35:31". Each was checked with only one
mission loaded, so confirm it updates on a mission change before relying on it. H4 also
prints `data_mine_usability_set_mission_segment: <segment>` via `OutputDebugString`
(e.g. `mission_start`, `m10_cryo`, `m10_lab`), which could serve as a second signal.

## Reach chapter titles per mission (from HREK mission scripts)

| Map | Chapter string_ids (script order) |
|---|---|
| m05 | none (cinematic mission) |
| m10 | `chapter_01` ("Noble Team", verified), `chapter_02`, `chapter_03` |
| m20 | `ct_courtyard`, `ct_return`, `ct_sword`, `ct_valley` |
| m30 | `ct_quiet`, `ct_mule`, `ct_settlement` |
| m35 | `chapter_01`, `chapter_02`, `chapter_03` |
| m45 | `ct_beach`, `ct_wafer`, `ct_corvette` / `ct_corvette_alt` (picked at random) |
| m50 | `ct_act1`, `ct_act2`, `ct_act3` |
| m52 | `ct_start`, `ct_final` |
| m60 | `ct_start`, `ct_courtyard`, `ct_ice_cave` |
| m70 | `ct_blockade`, `ct_dirtroad`, `ct_platform`, `ct_wall` |
| m70_a | none |
| m70_bonus | `ct_hill` |

The script-order column is alphabetical where the scripts didn't make the order clear.
The H2/H3/H4 editing kits (`H2EK`, `H3EK`, `H4EK` in the Steam library) include mission
scripts that can be mined the same way for per-mission title indices.
