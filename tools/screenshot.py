"""Render game scenes to PNG files without opening a window.

Usage::

    .venv/bin/python tools/screenshot.py menu /tmp/menu.png
    .venv/bin/python tools/screenshot.py all /tmp/shots
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("TAMWORTH_CHASE_DATA", "/tmp/tamworth_chase_shots_data")
os.makedirs("/tmp/tamworth_chase_shots_data", exist_ok=True)
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame

from game.app import ALL_FEATURES, App
from game.models import Action

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = json.loads((ROOT / "tests" / "solutions.json").read_text(encoding="utf-8"))


def frames(app: App, count: int = 3, dt: float = 1 / 60) -> None:
    for _ in range(count):
        app.update(dt)


def draw(app: App, path: Path) -> None:
    app.transition = 0.0
    surface = app.render_once()
    pygame.image.save(surface, str(path))
    print("saved", path)


def scenario_menu(app: App, path: Path) -> None:
    frames(app, 30, 1 / 30)
    draw(app, path)


def scenario_level_select(app: App, path: Path) -> None:
    app.open_scene("level_select")
    frames(app, 5)
    draw(app, path)


def scenario_settings(app: App, path: Path) -> None:
    app.open_scene("settings")
    frames(app, 5)
    draw(app, path)


def scenario_play(app: App, path: Path) -> None:
    app.start_level(app.levels[0])
    frames(app, 5)
    draw(app, path)


def scenario_play_flee(app: App, path: Path) -> None:
    app.start_level(app.levels[3])
    frames(app, 5)
    draw(app, path)


def scenario_play_win(app: App, path: Path) -> None:
    app.start_level(app.levels[0])
    scene = app.scene
    for action in SOLUTIONS["level_01"]["actions"]:
        scene._take_action(Action(action))
        scene.animator.clear()
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    draw(app, path)


def scenario_play_exit(app: App, path: Path) -> None:
    from game.levels import parse_level

    level = parse_level(
        {
            "id": "exit_shot",
            "name": "出口失守",
            "grid": ["#######", "#F....#", "#.....#", "#...C.#", "#.....#", "#.....#", "#######"],
            "fj_start_direction": "north",
            "cow_facings": ["east"],
            "exit_cells": [[3, 5]],
            "max_turns": 20,
        }
    )
    app.start_level(level)
    scene = app.scene
    scene._take_action(Action.TURN_TO_LEFT)
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    draw(app, path)


def scenario_challenge(app: App, path: Path) -> None:
    app.open_scene("challenge")
    frames(app, 5)
    draw(app, path)


def scenario_daily(app: App, path: Path) -> None:
    app.open_scene("daily")
    frames(app, 5)
    draw(app, path)


def scenario_achievements(app: App, path: Path) -> None:
    app.open_scene("achievement")
    frames(app, 5)
    draw(app, path)


def scenario_editor(app: App, path: Path) -> None:
    app.open_scene("editor")
    scene = app.scene
    scene._action("paint:fence")
    for cell in ((4, 3), (4, 4), (4, 5), (5, 3), (3, 6)):
        scene._paint(cell)
    scene._action("tool:exit")
    scene._paint((2, 7))
    scene._action("actor:cow")
    scene._paint((6, 6))
    frames(app, 5)
    draw(app, path)


SCENARIOS = {
    "menu": scenario_menu,
    "level_select": scenario_level_select,
    "settings": scenario_settings,
    "play": scenario_play,
    "play_flee": scenario_play_flee,
    "play_win": scenario_play_win,
    "play_exit": scenario_play_exit,
    "challenge": scenario_challenge,
    "daily": scenario_daily,
    "achievements": scenario_achievements,
    "editor": scenario_editor,
}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: screenshot.py <scene|all> <output>")
        return 2
    name, target = argv[1], Path(argv[2])
    app = App(features=ALL_FEATURES)
    if name == "all":
        target.mkdir(parents=True, exist_ok=True)
        for key, fn in SCENARIOS.items():
            app.open_scene("menu")
            fn(app, target / f"{key}.png")
    else:
        fn = SCENARIOS.get(name)
        if fn is None:
            print("unknown scene", name)
            return 2
        fn(app, target)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
