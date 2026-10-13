"""What a scenario and a scenario group are.

A group is a module in `groups/` exporting `GROUP = Group(...)`; its `build` takes a
`Context` and returns scenarios in a fixed order (append new ones at the end, so `go <n>`
keeps meaning the same; verdicts are keyed by title). A group may include others, which
run after its own scenarios.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from missions import Mission


@dataclass
class Scenario:
    title: str
    mission: Mission
    steps: str = ""
    # Launcher commands sent once the mission is running, in order (e.g. "/title 2").
    commands: list[str] = field(default_factory=list)
    # Locations this scenario waits for; any other check is called out.
    expect: list[int] = field(default_factory=list)
    # Pass by itself once every expected check arrives (fail if they don't in time).
    # For scenarios with nothing to look at.
    auto: bool = False
    # Seconds an auto scenario waits for its checks, from its last command (or the
    # mission starting, without commands)
    timeout: int = 30
    # Items sent before the scenario starts. The mission's own Access item is sent
    # unless it's in `locked`.
    give: list[str] = field(default_factory=list)
    # Levels that must still be locked (their Access never sent this session).
    locked: list[str] = field(default_factory=list)
    # Load the mission again even if it's the one already running.
    reload: bool = False
    # Filled in by groups.build: the group the verdict is recorded under.
    origin: str = ""


@dataclass
class Context:
    games: dict[str, list[Mission]]   # game key -> missions, from missions.load()

    def mission(self, game: str, name: str) -> Mission:
        return next(m for m in self.games[game] if m.name == name)


@dataclass(frozen=True)
class Group:
    name: str
    summary: str
    build: Callable[[Context], list[Scenario]]
    includes: tuple[str, ...] = ()
