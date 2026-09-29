# Chapter / mission-complete hook map: H2, H3, H4, Reach

Mappings for the equivalents of the Halo CE hooks in `HaloAP_DLL/hooks/chapter_title.cpp`
(chapter reached) and `mission_complete.cpp` (mission won + current mission name).
Implemented in `HaloAP_DLL/hooks/game_hooks.cpp`. Every hook below was hit live under x64dbg (MCC on Proton, EAC off)
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
| H4 | chapter | `halo4+0x12D738` | `48 83 EC 28 8B 15 ? ? ? ? 45 33 DB 65 48 8B 04 25 58 00 00 00 44 8B D1` | `(short title_index, float)`. The index is into the map's title block, which also holds objective popups; see "H4 chapter title indices per mission". |
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

## H4 chapter title indices per mission

H4's chapter cards go through the same hook (`halo4+0x12D738`) and the same per-map
`cutscene_title` block as its objective popups (">><<", ">>NEW OBJECTIVE<<", objective
text). So a chapter check must fire only for the indices below and ignore every other
index. Indices come from each map's title block; card names are the in-game cards per
Halopedia (`H4:<Level>` transcripts). Map names differ from level names: Infinity is
`m60_rescue` and Reclaimer is `m40_invasion`.

| Level | Map | Chapter cards (index: name) | Live-verified |
|---|---|---|---|
| Prologue | `m05_prologue` | none | |
| Dawn | `m10_crash` | none (idx 5 is the "2557 - Four years after" card; hooks fire, but it isn't a chapter) | idx 5 |
| Requiem | `m020` | 15 and 19: Requiem (same card twice in the block), 16: A Star to Steer By, 17: The Gateway | |
| Forerunner | `m30_cryptum` | 35: Buried and Forgotten, 36: Enemy of My Enemy, 37: Almost Home, 38: Next Stop, Certain Death | |
| Infinity | `m60_rescue` | 36: Infinity, 37: Reunited, 39: The Gun Show, 40: Shining Armor, 41: Eviction Proceedings | idx 36 |
| Reclaimer | `m40_invasion` | 67: Size Matters, 66: The Gravity of the Situation | |
| Shutdown | `m70_liftoff` | 16: Once More Unto the Breach, 18: Change of Plan | |
| Composer | `m80_delta` | 1: Any Landing You Can Walk Away From, 2: The Composer, 4: All Things Lost and Found... | idx 1, full table matched |
| Midnight | `m90_sacrifice` | 0: One Last Shot, 2: From the Cradle..., 3: ...To the Grave, 10: Old Friends | |
| Epilogue | `m95_epilogue` | none | |

Other title entries with chapter-style names exist but aren't shown in the shipped game:
m60 38 "Exfiltration"; m40 68 "Three Sides to Every Story"; m70 15 "To Infinity...",
17 "Under His Watchful Gaze", 19 "Only in the Leap from the Lion's Head"; m80 0 "Boarding
Action", 3 "A Fighting Chance", 5 "We Deserve to be Forgotten"; m90 4 "I Am Your Shield,
I Am Your Sword". The H4EK scripts predate the shipped build, so they only partly match.
The Composer and Infinity blocks in memory matched the offline extraction entry for entry,
including where each block starts.

## H2 / H3 chapter title indices per mission

Taken from each map's `ui\chapter_titles` string list (H2EK, H3EK). Live hits matched
index 0 on H2 01a and 01b and on H3 010. The other indices assume the string list order
equals the scenario's title block order, which the names suggest but hasn't been checked
per map.

**H2** (every entry below is a chapter, except where noted):

| Map | Chapter cards |
|---|---|
| `00a_introduction` | none (0, 1 are cinematic location cards) |
| `01a_tutorial` | 0: One Size Fits All |
| `01b_spacestation` | 0: Home Field Advantage, 1: Priority Shift, 2: Authorized Personnel Only, 3: Return to Sender (4 `title_gun_alt` is empty) |
| `03a_oldmombasa` | 0: They'll Regret That Too, 1: A Day at the Beach, 2: Speed Zone Ahead |
| `03b_newmombasa` | 0/1/2: Ladies Like... (one card, text varies by difficulty), 3: This Town Ain't Big Enough for Both of Us, 4: Field Expedient |
| `04a_gasgiant` | 0: A Whisper in the Storm, 1: To the Hunt |
| `04b_floodlab` | 0: Juggernaut, 1: Hey, Watch This!, 2: Dead or Alive...Actually, Just Dead |
| `05a_deltaapproach` | 0: Helljumpers, 1: You Break It, You Buy It, 2: Off the Rock, Through the Bush, Nothing But Jackal |
| `05b_deltatowers` | 0: Testament, 1: One-Way Ticket, 2: Pressure (`title_2alt`), 3: Sorry, Were You in the Middle of Something? |
| `06a_sentinelwalls` | 0: Uncomfortable Silence, 1: Buyer's Remorse, 2: 100,000 Years' War (3 is a cinematic location card) |
| `06b_floodzone` | 0: Objects in Mirror are Larger Than They Appear, 1: Healthy Competition, 2: Shooting Gallery, 3: That Old, Familiar Feeling |
| `07a_highcharity` | 0: Inside Job, 1: You Can Thank Me Later, 2: Grudge-Match, 3: Turning in Their Graves |
| `07b_forerunnership` | 0: Cross-Purposes, 1: Please, Make Yourself at Home, 2: Sanctified, 3: Once More, With Feeling |
| `08a_deltacliffs` | 0: Oh, So That's How it Is, 1: Step Aside, Let the Man Go Through, 2: Fight Club |
| `08b_deltacontrol` | 0: Your Ass, My Size-24 Hoof, 1: Backseat Driver, 2: Delusions and Grandeur |

Whether 05b's "Pressure" is shown in the shipped game (vs. "One-Way Ticket") is unchecked.

**H3**: the block holds the chapter cards (`title_N`) followed by objectives (`obj_N`).
Only the `title_N` indices below are chapters.

| Map | Chapter cards |
|---|---|
| `005_intro`, `130_epilogue` | none |
| `010_jungle` | 0: Walk It Off, 1: Charlie Foxtrot, 2: Quid Pro Quo |
| `020_base` | 0: Know Your Role..., 1: Gift with Purchase, 2: Last One Out, Get the Lights |
| `030_outskirts` | 0: Full Contact Safari, 1: The Broken Path |
| `040_voi` | 0: Ghost Town, 1: Think Big, 2: Judgment |
| `050_floodvoi` | 0: It Followed Me Home, 1: Shadow of Intent, 2: Infinite Devil Machine |
| `070_waste` | 0: Installation 00, 1: Forward Unto Dawn, 2: Real Men Don't Read Maps |
| `100_citadel` | 0: Trident, 1: If You Want it Done Right..., 2: Journey's End, 3: Revelation |
| `110_hc` | 0: Rampant, 1: Nor Hell a Fury... |
| `120_halo` | 0: Full Circle, 1: The Way the World Ends |

The H2/H3/H4 editing kits (`H2EK`, `H3EK`, `H4EK` in the Steam library) include mission
scripts that can be mined the same way for per-mission title indices.

## After a win

MCC loads the next mission after a win, which may be locked. What sends each game back to
the menu instead (tested live 2026-09-28 by patching memory at the win):

| Game | How MCC decides | Return to the menu by |
|---|---|---|
| H2 | the game advances itself after `game_won` (won byte at `[globals+0x1818]`, globals pointer at `halo2+0xE80A78`; clearing it doesn't help) | replacing the next engine shell command with the quit sequence |
| H3 | `game_won` notifies MCC directly (`host->vfunc[0x18](2)`); clearing its won byte (`[TLS+0x48]+0xFB80`) doesn't help | same as H2 |
| H4 | the won byte `[TLS+0x40]+0x2CF60`, read after the game ends (`+0x9CDF0`) | clearing the won byte after the win function returns |
| Reach | the won byte `[TLS+0x48]+0x1EAC0`, read after the game ends (`+0x59330`) | same as H4 |

The shell commands are CE's: `CreateGameEngine` stores the engine object in a global, and
its vtable slot 3 is `(engine, int type, void* ctx)`. Quitting from the pause menu sends
`0` (pause), `0xD` (teardown), `1` (resume); during play MCC sends type `5` every few seconds.
H2's engine object is a wrapper whose slot 3 forwards to an inner handler; the messages are
the same.

## Skull pickups

H4 and Reach have no skull pickups in their campaigns. H2 and H3 award skulls through
script functions, found at runtime through their script definitions (the definition holds
a pointer to the name and, 0x18 bytes on, the evaluator, which calls the implementation
right after `mov ecx, [rax]`):

| Game | Script function | Implementation | Arguments |
|---|---|---|---|
| H2 | `ice_cream_flavor_stock` | `halo2+0x6EF410` | `(flavor)`, 0–14 |
| H3 | `campaign_metagame_award_primary_skull` | `halo3+0x136088` | `(player, skull)`, skull 0–8 |
| H3 | `campaign_metagame_award_secondary_skull` | `halo3+0x136580` | `(player, skull)`, skull 1–4 |

H3's mission scripts call these for player0..3 once the skull weapon is held. Only 8 of H2's
15 `ice_cream_flavor_stock` calls are in the H2EK mission scripts (others are commented out),
but the table of skull events it sends MCC covers all 15 and nothing else reads it, so the
shipped maps are assumed to call it for every skull. Per-map skulls and keys are in
`apworld/halo_mcc/data/missions.py` (`SKULL_PICKUPS`).
