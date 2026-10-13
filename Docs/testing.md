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

## Hooks in the game (one mission load)

Run the launcher with `HALOAP_DEBUG=1`, load any mission, and type in the launcher window:

| Command | Does | Games |
|---|---|---|
| `/title <n>` | shows chapter title `<n>` (Reach: the chapter's string_id, from `tools/reach_chapter_sids.json`) | all |
| `/win` | wins the mission | all |
| `/deathlink` | receives a Death Link | all |

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

**Loading missions.** When you're already in a mission of the same game, the harness
asks the DLL to load the next one through the engine's level-load call (`/load`). That is
known to exist in CE; for H2, H3, H4 and Reach it's a guess at the same interface and the
paths are unverified. When it can't (at the menu, another game, or the load doesn't show
the mission within 90 s), it says which mission to start from the menu and carries on
once that mission is running.

| Group | What |
|---|---|
| `smoke` | per game: a chapter card (auto) and a win that returns to the menu |
| `cards` (`cards_ce`, `cards_h2`, `cards_h3`, `cards_h4`, `cards_reach`) | every chapter card shows the chapter it's mapped to |
| `first_cards` | every mission's first card arrives by itself (auto, don't skip cutscenes) |
| `fixes` | the 2026-10-13 bug reports |
| `deathlink` | Death Link in and out, per game |

`--fake` runs the whole thing without the game (the fake DLL acts out the commands), to
check the harness itself or a new group; its results go to `build/aptest-fake/`.
