"""The scenario group registry: every module here exporting `GROUP`. Adding a group is
adding a file."""

from __future__ import annotations

import importlib
import pkgutil

from scenario import Context, Group, Scenario


def discover() -> dict[str, Group]:
    found: dict[str, Group] = {}
    for info in pkgutil.iter_modules(__path__):
        group = getattr(importlib.import_module(f"{__name__}.{info.name}"), "GROUP", None)
        if isinstance(group, Group):
            if group.name in found:
                raise ValueError(f"two groups named {group.name!r}")
            found[group.name] = group
    for group in found.values():
        for included in group.includes:
            if included not in found:
                raise ValueError(f"group {group.name!r} includes unknown {included!r}")
    return dict(sorted(found.items()))


def members(name: str, groups: dict[str, Group], path: tuple[str, ...] = ()) -> list[str]:
    """`name` and every group it includes, depth first, each once"""
    if name in path:
        raise ValueError(f"groups include each other: {' -> '.join(path + (name,))}")
    order = [name]
    for included in groups[name].includes:
        for member in members(included, groups, path + (name,)):
            if member not in order:
                order.append(member)
    return order


def build(name: str, groups: dict[str, Group], ctx: Context) -> list[Scenario]:
    scenarios: list[Scenario] = []
    seen: set[tuple[str, str]] = set()
    for member in members(name, groups):
        for s in groups[member].build(ctx):
            s.origin = s.origin or member
            key = (s.origin, s.title)
            if key in seen:
                continue
            seen.add(key)
            scenarios.append(s)
    return scenarios
