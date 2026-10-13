# Testing without playing

## Launcher tests (no game)

```
~/Projects/MoreProjects/Archipelago-src/.venv/bin/python tools/launcher_test.py [-k name]
```

Generates a seed from `apworld/`, hosts it on a local server, runs the launcher under Wine
in test mode (`HALOAP_TEST`: no game directory, no mod files, no MCC), and plays the DLL's
part with `tools/fake_dll`. Each test sends the pipe messages the hooks would send
(`CHAPTER:`, `G_CHAPTER:`, `G_COMPLETE:`, ...) and checks which locations reach the server.
Covers chapter/skull/completion mapping, the locked-mission guard, chapters sent on a win,
checks made while the server is down, and the debug commands. Logs land in `build/test/`.

To test a new message or mapping, add a `@test` function to `tools/launcher_test.py`.

## CE chapter titles (no game)

```
python3 tools/ce_chapter_titles.py --check
```

Reads every CE campaign map: each cutscene title's index (what the chapter hook reports),
its text, the scripts that show it, and whether that's inside a skippable cutscene.
`--check` compares the result with `HaloAP_launcher/Data/chapter_map.h`.

## Which chapters can actually be seen (no game)

```
python3 tools/chapter_audit.py [--game ce|h2a|h3|reach|h4] [-v]
```

Reads the mission scripts from the official editing kits (HCEEK, H2EK, H3EK, H4EK, HREK in
the Steam library; extracted once into `~/.cache/haloap/kits`). For every chapter location
it finds the script that shows the card and follows the scripts that start it back to
mission start, so it can tell whether the card is shown on every playthrough, only on some
difficulties or solo, only if a cutscene isn't skipped, or never. `-v` prints the script
path. Halo 4 only runs with `--game h4`: its kit scripts differ from the shipped game.

Chapters the tables send another way (on mission load, or at a CE cutscene's mission
segment) and chapters removed as locations are marked and not counted; the last line counts
what's left, which should be 0.

Findings on 2026-10-13: H3 The Storm "Think Big" and H2 Gravemind's last three cards are
never shown, and were removed as locations (`unused=True` in missions.py keeps their IDs
reserved; older seeds get them when the mission loads). CE "Reveille" is solo Normal only,
and six cards are in skippable cutscenes; those are sent on load or at the cutscene.

### Halo 2 against the shipped maps

```
python3 tools/h2_shipped_chapters.py [<map> ...] [-v]
```

H2's kit scripts and the shipped game can differ, so this reads the compiled scripts from
MCC's own H2 maps (decompressed on the fly) and checks every H2 chapter the same way.

## Hooks in the game (one mission load)

Run the launcher with `HALOAP_DEBUG=1`, load any mission, and type in the launcher window:

| Command | Does | Games |
|---|---|---|
| `/title <n>` | shows chapter title `<n>` (Reach: the chapter's string_id, from `tools/reach_chapter_sids.json`) | all |
| `/win` | wins the mission | all |
| `/deathlink` | receives a Death Link | all |
| `/hs <expr>` | runs a HaloScript expression, e.g. `/hs (map_reset)` | all |

`/hs` goes through engine vtable slot 9 (on the object `CreateGameEngine` makes), which
queues a console line; the engine's command drain runs lines that start `HS: ` as script
and drops anything not prefixed (`halo1+0x954F6`). Every game DLL has the `HS: ` prefix.

It can't load a mission: MCC's builds stub out the dev map-launch functions. `map_name`
(CE, H2, H3, Reach) and `game_start` (H2, H3, Reach) have handlers that only return
(e.g. `halo1+0xACCF44`, `halo3+0x1065F4`); H4's table wasn't matched but is presumably
the same. `map_reset` and `game_won` are real. Loading a mission from the harness needs
MCC's own launch path instead (not mapped yet).

In CE, H2, H3 and H4 they go through the real hooks, so the launcher logs and sends
whatever the hook would (`[ap] Chapter: ...`, the completion and its chapters, the
post-win quit). Reach's chapter and win script functions have no implementation apart
from their evaluators (which need a script thread), so there the DLL does what they do:
`/title` writes the string_id to the HUD's chapter slot and clears it 5 s later; `/win`
sets the won byte and ends the game, then clears the byte as the real win's hook does.
Neither runs Reach's chapter or win hook itself.

## Play-test scenarios (APTest)

```
~/Projects/MoreProjects/Archipelago-src/.venv/bin/python tools/aptest/aptest.py --list-groups
~/Projects/MoreProjects/Archipelago-src/.venv/bin/python tools/aptest/aptest.py --group smoke
```

Like the Half-Life 2 harness: scenario groups (modules in `tools/aptest/groups/`) run
back to back, and each gets a verdict. It generates a seed with every game (every final
open, Death Link on), hosts it locally, and starts the game through
`build/release/HaloAP-Linux/halo-ap.sh` (run `./build.sh` first) with the launcher's
console in the same terminal. Type `next` once the DLL connects.

For each scenario the harness sends the mission's Access item, gets the mission running,
sends the scenario's commands (`/title`, `/win`, `/deathlink`), and reports every check
that arrives as expected or unexpected. Verdicts: `pass`, `fail <what happened>`,
`note <text>`; the next open scenario then starts. Scenarios with nothing to look at
(`auto`) pass or fail by themselves. `help` lists the rest. Verdicts go to
`build/aptest/results.txt`; `next` skips scenarios that already passed.

**Loading missions.** The harness can't load missions itself (see `/hs` above), so it
says which mission to start from the menu and carries on once that mission is running.

| Group | What |
|---|---|
| `smoke` | per game: a chapter card (auto) and a win that returns to the menu |
| `cards` (`cards_ce`, `cards_h2`, `cards_h3`, `cards_h4`, `cards_reach`) | every chapter card shows the chapter it's mapped to |
| `first_cards` | every mission's first card arrives by itself (auto, don't skip cutscenes) |
| `fixes` | the 2026-10-13 bug reports |
| `deathlink` | Death Link in and out, per game |

`--fake` runs the whole thing without the game (the fake DLL acts out the commands), to
check the harness itself or a new group; its results go to `build/aptest-fake/`.
