"""Render game scenes to PNG files without opening a window.

Usage::

    .venv/bin/python tools/screenshot.py menu /tmp/menu.png
    .venv/bin/python tools/screenshot.py all /tmp/shots
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("TAMWORTH_TWO_DATA", "/tmp/tamworth_shots_data")
os.makedirs("/tmp/tamworth_shots_data", exist_ok=True)
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame

from game.app import ALL_FEATURES, App
from game.models import Direction, GameStatus


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


def scenario_play_place(app: App, path: Path) -> None:
    app.start_level(app.levels[0])
    frames(app, 5)
    draw(app, path)


def scenario_play_run(app: App, path: Path) -> None:
    app.start_level(app.levels[3])
    scene = app.scene
    for pos in ((1, 4), (3, 3)):
        scene._place_at(pos)
    scene._handle_start()
    frames(app, 22)
    draw(app, path)


def scenario_play_win(app: App, path: Path) -> None:
    app.start_level(app.levels[0])
    scene = app.scene
    scene._place_at((1, 2))
    scene._handle_start()
    for _ in range(400):
        app.update(1 / 60)
        if scene.phase == "result" and scene.result_shown:
            break
    frames(app, 2)
    draw(app, path)


def scenario_tutorial(app: App, path: Path) -> None:
    app.open_scene("tutorial")
    frames(app, 5)
    draw(app, path)


def scenario_tutorial_chapter(app: App, path: Path) -> None:
    app.open_tutorial_chapter("basics")
    frames(app, 5)
    draw(app, path)


def scenario_play_tutorial(app: App, path: Path) -> None:
    app.start_tutorial_lesson("basics", "basics_02")
    scene = app.scene
    scene._place_at((2, 7))
    frames(app, 5)
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
    scene._action("actor:cow")
    scene._paint((6, 6))
    frames(app, 5)
    draw(app, path)


def scenario_play_loop(app: App, path: Path) -> None:
    level = app.levels[9]
    app.start_level(level)
    scene = app.scene
    scene._handle_start()
    for _ in range(2000):
        app.update(1 / 60)
        if scene.phase == "result" and scene.result_shown:
            break
    frames(app, 2)
    draw(app, path)


SCENARIOS = {
    "menu": scenario_menu,
    "level_select": scenario_level_select,
    "settings": scenario_settings,
    "play_place": scenario_play_place,
    "play_run": scenario_play_run,
    "play_win": scenario_play_win,
    "play_loop": scenario_play_loop,
    "tutorial": scenario_tutorial,
    "tutorial_chapter": scenario_tutorial_chapter,
    "play_tutorial": scenario_play_tutorial,
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
