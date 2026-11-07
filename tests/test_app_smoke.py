"""Integration smoke tests: scenes render head-less and the tank flow works."""

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
    from game.models import Action

    scene = app.scene
    for action in actions:
        scene._take_action(Action(action))
        scene.animator.clear()
    for _ in range(100):
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
    play_actions(app, SOLUTIONS["level_01"]["actions"])
    assert scene.sim.status.value == "won"
    assert scene.result_shown
    assert scene.modal is not None
    _render(app)


def test_blocked_forward_consumes_a_turn(app):
    from game.levels import parse_level
    from game.models import Action

    level = parse_level(
        {
            "id": "blocked",
            "name": "撞墙",
            "grid": ["#######", "#F....#", "#...C.#", "#.....#", "#######"],
            "fj_start_direction": "north",
            "cow_facings": ["west"],
            "exit_cells": [[1, 5]],
            "max_turns": 20,
        }
    )
    app.start_level(level)
    scene = app.scene
    scene._take_action(Action.FORWARD)
    assert scene.sim.turns == 1
    assert scene.toast_text.startswith("前方受阻")
    _render(app)


def test_exit_failure_modal(app):
    from game.levels import parse_level
    from game.models import Action

    level = parse_level(
        {
            "id": "escape",
            "name": "出口",
            "grid": ["#######", "#F....#", "#.....#", "#...C.#", "#.....#", "#.....#", "#######"],
            "fj_start_direction": "north",
            "cow_facings": ["east"],
            "exit_cells": [[3, 5]],
            "max_turns": 20,
        }
    )
    app.start_level(level)
    scene = app.scene
    scene._take_action(Action.WAIT)
    assert scene.sim.status.value == "lost_exit"
    for _ in range(100):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.modal is not None
    assert scene.modal.title == "牛从出口逃走了"
    labels = [button.text for button in scene.modal.buttons]
    assert "撤销到上一回合" in labels
    assert "重开本关" in labels


def test_turn_limit_modal(app):
    from game.levels import parse_level
    from game.models import Action

    level = parse_level(
        {
            "id": "short",
            "name": "短局",
            "grid": ["#######", "#F....#", "#...C.#", "#.....#", "#######"],
            "fj_start_direction": "north",
            "cow_facings": ["west"],
            "exit_cells": [[1, 5]],
            "max_turns": 2,
        }
    )
    app.start_level(level)
    scene = app.scene
    scene._take_action(Action.WAIT)
    scene.animator.clear()
    scene._take_action(Action.WAIT)
    for _ in range(100):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.modal is not None
    assert scene.modal.title == "回合数用完了"


def test_tutorial_chapter_scene_renders(app):
    app.open_tutorial_chapter("basics")
    _render(app)
    assert app.scene.chapter is not None
    assert len(app.scene.chapter.lessons) == 6


def test_tutorial_lesson_with_turn_practice(app):
    from game.models import Action

    app.start_tutorial_lesson("basics", "basics_01")
    scene = app.scene
    for action in (
        Action.TURN_LEFT,
        Action.TURN_RIGHT,
        Action.TURN_RIGHT,
        Action.FORWARD,
        Action.FORWARD,
        Action.FORWARD,
        Action.FORWARD,
    ):
        scene._take_action(action)
        scene.animator.clear()
    for _ in range(100):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.sim.status.value == "won"
    assert app.store.lesson_state("basics", "basics_01") == "completed"


def test_tutorial_wait_practice(app):
    from game.models import Action

    app.start_tutorial_lesson("basics", "basics_03")
    scene = app.scene
    for action in (Action.WAIT, Action.TURN_LEFT, Action.TURN_LEFT):
        scene._take_action(action)
        scene.animator.clear()
    for _ in range(100):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.sim.status.value == "won"
    assert app.store.lesson_state("basics", "basics_03") == "completed"


def test_tutorial_practice_gate_rejects_win(app):
    from game.models import Action

    app.store.set_lesson_state("basics", "basics_03", "not_started")
    app.start_tutorial_lesson("basics", "basics_03")
    scene = app.scene
    # Winning without the required wait must not complete the lesson.
    for action in (Action.TURN_LEFT, Action.TURN_LEFT, Action.FORWARD):
        scene._take_action(action)
        scene.animator.clear()
    for _ in range(100):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.modal is not None
    assert app.store.lesson_state("basics", "basics_03") != "completed"


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
    assert level.exit_cells


def test_editor_set_exits_tutorial_task(app):
    lesson = app.catalog.find_lesson("editor", "editor_02")
    app.start_editor_tutorial("editor", lesson)
    scene = app.scene
    scene._action("tool:exit")
    scene._paint((3, 3))
    scene._action("behavior")
    scene.update(1 / 60)
    assert scene.task_done
    assert app.store.lesson_state("editor", "editor_02") == "completed"


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


def test_keyboard_controls_and_prediction(app):
    import pygame
    from game.models import Action

    app.start_level(app.levels[0])
    scene = app.scene
    pygame.event.clear()
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w))
    scene.animator.clear()
    assert scene.sim.turns == 1
    facing = scene.sim.farmer.facing
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    scene.animator.clear()
    assert scene.sim.farmer.facing is facing.counter_clockwise()
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))
    scene.animator.clear()
    assert scene.sim.farmer.facing is facing
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    scene.animator.clear()
    turns = scene.sim.turns
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_u))
    assert scene.sim.turns == turns - 1
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))
    assert scene.show_prediction is False
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    assert scene.sim.turns == 0


def test_no_prediction_level_shows_disabled_button(app):
    app.start_level(app.levels[8])
    scene = app.scene
    assert scene.level.prediction_steps == 0
    assert scene.predict_button.enabled is False
    assert scene.predict_button.text == "预测 无"
    assert scene._prediction() == ()


def test_alert_toggle_persists(app):
    app.start_level(app.levels[0])
    scene = app.scene
    before = scene.show_alerts
    scene._toggle_alerts()
    assert scene.show_alerts is not before
    assert app.store.get_setting("alerts") is scene.show_alerts


def test_tutorial_block_practice(app):
    from game.models import Action

    app.store.set_lesson_state("basics", "basics_02", "not_started")
    app.start_tutorial_lesson("basics", "basics_02")
    scene = app.scene
    for action in (
        Action.FORWARD,
        Action.FORWARD,
        Action.TURN_RIGHT,
        Action.FORWARD,
        Action.TURN_RIGHT,
        Action.FORWARD,
        Action.FORWARD,
        Action.FORWARD,
        Action.FORWARD,
    ):
        scene._take_action(action)
        scene.animator.clear()
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.sim.status.value == "won"
    assert app.store.lesson_state("basics", "basics_02") == "completed"


def test_tutorial_preview_and_undo_practice(app):
    from game.models import Action

    app.store.set_lesson_state("basics", "basics_06", "not_started")
    app.start_tutorial_lesson("basics", "basics_06")
    scene = app.scene
    assert scene.show_prediction is False
    scene._toggle_prediction()
    assert scene.show_prediction is True
    scene._take_action(Action.TURN_LEFT)
    scene.animator.clear()
    scene._undo()
    for action in (Action.TURN_RIGHT, Action.FORWARD, Action.FORWARD, Action.FORWARD, Action.FORWARD):
        scene._take_action(action)
        scene.animator.clear()
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.sim.status.value == "won"
    assert app.store.lesson_state("basics", "basics_06") == "completed"


def test_editor_paint_wall_tutorial_task(app):
    lesson = app.catalog.find_lesson("editor", "editor_01")
    app.start_editor_tutorial("editor", lesson)
    scene = app.scene
    scene._action("paint:fence")
    for cell in ((4, 3), (4, 4), (4, 5)):
        scene._paint(cell)
    scene.update(1 / 60)
    assert scene.task_done
    assert app.store.lesson_state("editor", "editor_01") == "completed"
