"""Integration smoke tests: scenes render head-less and the turn flow works."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = json.loads((ROOT / "tests" / "solutions.json").read_text(encoding="utf-8"))
TUTORIAL_SOLUTIONS = json.loads(
    (ROOT / "tests" / "tutorial_solutions.json").read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    data_dir = tmp_path_factory.mktemp("data")
    os.environ["TAMWORTH_CHASE_DATA"] = str(data_dir)
    import pygame

    pygame.init()
    from game.app import ALL_FEATURES, App

    application = App(features=ALL_FEATURES)
    yield application
    pygame.quit()


def _render(app, frames: int = 2):
    for _ in range(frames):
        app.update(1 / 60)
    app.transition = 0.0
    return app.render_once()


def play_actions(app, actions):
    scene = app.scene
    from game.models import Direction

    for action in actions:
        direction = None if action == "wait" else Direction[action.upper()]
        scene._take_turn(direction)
        scene.animator.clear()
    for _ in range(80):
        app.update(1 / 60)
        if scene.result_shown:
            break
    return scene


def test_menu_renders(app):
    app.open_scene("menu")
    surface = _render(app)
    assert surface.get_size() == (1280, 840)


@pytest.mark.parametrize(
    "scene",
    ["level_select", "settings", "tutorial", "challenge", "daily", "editor", "achievement"],
)
def test_top_level_scenes_render(app, scene):
    app.open_scene(scene)
    surface = _render(app)
    assert surface.get_at((10, 10)) != (0, 0, 0)


def test_play_scene_renders_and_wins(app):
    app.start_level(app.levels[0])
    scene = app.scene
    scene._start_run()
    play_actions(app, SOLUTIONS["level_01"]["actions"])
    assert scene.sim.status.value == "won"
    assert scene.result_shown
    assert scene.modal is not None
    _render(app)


def test_play_scene_blocked_order_does_not_advance(app):
    from game.models import Direction

    app.start_level(app.levels[0])
    scene = app.scene
    scene._place_at((3, 1))
    scene._start_run()
    turns = scene.sim.turns
    scene._take_turn(Direction.WEST)
    assert scene.sim.turns == turns
    _render(app)


def test_play_scene_turn_limit_modal_offers_undo(app):
    from game.levels import parse_level

    level = parse_level(
        {
            "id": "tiny",
            "name": "小小牧场",
            "grid": ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
            "cow_facings": ["north"],
            "max_turns": 1,
        }
    )
    app.start_level(level)
    scene = app.scene
    scene._start_run()
    scene._take_turn(None)
    assert scene.sim.status.value == "lost_turns"
    for _ in range(80):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.modal is not None
    labels = [button.text for button in scene.modal.buttons]
    assert "撤销到上一回合" in labels
    assert "重开本关" in labels


def test_tutorial_chapter_scene_renders(app):
    app.open_tutorial_chapter("basics")
    _render(app)
    assert app.scene.chapter is not None
    assert len(app.scene.chapter.lessons) == 6


def test_tutorial_lesson_flow(app):
    app.start_tutorial_lesson("basics", "basics_01")
    scene = app.scene
    assert scene.mode == "tutorial"
    scene._start_run()
    play_actions(app, TUTORIAL_SOLUTIONS["basics"]["basics_01"]["actions"])
    assert scene.sim.status.value == "won"
    assert app.store.lesson_state("basics", "basics_01") == "completed"


def test_editor_export_import_flow(app, tmp_path, monkeypatch):
    from game import editor as editor_module

    monkeypatch.setattr(editor_module, "custom_levels_dir", lambda: tmp_path)
    app.open_scene("editor")
    scene = app.scene
    scene.model.set_tile((3, 3), __import__("game.models", fromlist=["TileKind"]).TileKind.TREE)
    scene._export()
    assert scene.exported_path is not None and scene.exported_path.exists()
    files = editor_module.list_custom_levels(tmp_path)
    assert files
    level = editor_module.import_level(files[0])
    assert level.tile_at((3, 3)).value == "tree"


def test_challenge_level_runs(app):
    level = app.challenges[0]
    app.start_level(level, mode="challenge", challenge_key=level.level_id, return_to="challenge")
    scene = app.scene
    assert scene.mode == "challenge"
    _render(app)


def test_daily_level_is_deterministic(app):
    from game.daily import generate_daily

    first = generate_daily()
    second = generate_daily()
    assert first.level_id == second.level_id
    assert first.rows == second.rows
