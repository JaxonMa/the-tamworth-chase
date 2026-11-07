"""Integration smoke tests: scenes render head-less and the driving flow works."""

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


def _click(scene, pos):
    import pygame

    for event_type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        scene.handle_event(pygame.event.Event(event_type, button=1, pos=pos))


def play_actions(app, actions, *, animate: bool = False):
    from game.models import Action

    scene = app.scene
    for action in actions:
        scene._take_action(Action(action))
        scene.animator.clear()
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    return scene


def test_menu_renders(app):
    app.open_scene("menu")
    surface = _render(app)
    assert surface.get_size() == (1280, 840)


def test_menu_main_button_opens_level_select_and_play(app):
    from game.scenes.level_select import LevelSelectScene
    from game.scenes.play import PlayScene

    app.open_scene("menu")
    menu = app.scene
    main_button = next(button for button in menu.buttons if button.text == "主线关卡")
    _click(menu, main_button.rect.center)

    assert isinstance(app.scene, LevelSelectScene)
    assert len(app.scene.cards) == len(app.levels)
    _render(app)

    card = app.scene.cards[0]
    assert card.unlocked
    _click(app.scene, card.rect.center)

    assert isinstance(app.scene, PlayScene)
    _render(app)
    app.open_scene("menu")


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
    scene = play_actions(app, SOLUTIONS["level_01"]["actions"])
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


def test_same_direction_key_is_invalid(app):
    from game.models import Action

    app.start_level(app.levels[0])
    scene = app.scene
    assert scene.sim.farmer.facing.name == "NORTH"
    scene._take_action(Action.TURN_TO_UP)
    assert scene.sim.turns == 0
    assert scene.toast_text == "已朝该方向"
    assert scene.invalid_count == 1
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
    scene._take_action(Action.TURN_TO_LEFT)
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
    scene._take_action(Action.TURN_TO_LEFT)
    scene.animator.clear()
    scene._take_action(Action.TURN_TO_RIGHT)
    for _ in range(100):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.modal is not None
    assert scene.modal.title == "回合数已用完"


def test_tutorial_chapter_scene_renders(app):
    app.open_tutorial_chapter("basics")
    _render(app)
    assert app.scene.chapter is not None
    assert len(app.scene.chapter.lessons) == 7


def test_tutorial_lesson_with_direction_practice(app):
    from game.models import Action

    app.start_tutorial_lesson("basics", "basics_01")
    scene = app.scene
    for action in TUTORIAL_SOLUTIONS["basics"]["basics_01"]["actions"]:
        scene._take_action(Action(action))
        scene.animator.clear()
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.sim.status.value == "won"
    assert app.store.lesson_state("basics", "basics_01") == "completed"


def test_tutorial_block_practice(app):
    from game.models import Action

    app.store.set_lesson_state("basics", "basics_02", "not_started")
    app.start_tutorial_lesson("basics", "basics_02")
    scene = app.scene
    for action in TUTORIAL_SOLUTIONS["basics"]["basics_02"]["actions"]:
        scene._take_action(Action(action))
        scene.animator.clear()
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.sim.status.value == "won"
    assert app.store.lesson_state("basics", "basics_02") == "completed"


def test_tutorial_practice_gate_rejects_win_without_block(app):
    from game.models import Action

    app.store.set_lesson_state("basics", "basics_02", "not_started")
    app.start_tutorial_lesson("basics", "basics_02")
    scene = app.scene
    # A winning route that never attempts the required blocked forward.
    for action in (
        Action.TURN_TO_RIGHT,
        Action.FORWARD,
        Action.FORWARD,
        Action.TURN_TO_UP,
        Action.TURN_TO_DOWN,
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
    assert scene.modal is not None
    assert app.store.lesson_state("basics", "basics_02") != "completed"


def test_tutorial_preview_and_undo_practice(app):
    from game.models import Action

    app.store.set_lesson_state("basics", "basics_07", "not_started")
    app.start_tutorial_lesson("basics", "basics_07")
    scene = app.scene
    assert scene.show_prediction is False
    scene._toggle_prediction()
    assert scene.show_prediction is True
    first = TUTORIAL_SOLUTIONS["basics"]["basics_07"]["actions"][0]
    scene._take_action(Action(first))
    scene.animator.clear()
    scene._undo()
    for action in TUTORIAL_SOLUTIONS["basics"]["basics_07"]["actions"]:
        scene._take_action(Action(action))
        scene.animator.clear()
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.sim.status.value == "won"
    assert app.store.lesson_state("basics", "basics_07") == "completed"


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
    assert "cow_behavior" not in editor_module.level_to_dict(level)


def test_editor_set_exits_tutorial_task(app):
    lesson = app.catalog.find_lesson("editor", "editor_02")
    app.start_editor_tutorial("editor", lesson)
    scene = app.scene
    scene._action("tool:exit")
    scene._paint((3, 3))
    scene._paint((3, 4))
    scene._action("block_sight")
    scene.update(1 / 60)
    assert scene.task_done
    assert app.store.lesson_state("editor", "editor_02") == "completed"


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
    assert first.exit_cells
    assert not hasattr(first, "cow_behaviors")


def test_keyboard_controls_are_absolute(app):
    import pygame
    from game.models import Action

    app.start_level(app.levels[0])
    scene = app.scene
    pygame.event.clear()
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w))
    assert scene.sim.turns == 0
    assert scene.toast_text == "已朝该方向"
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    scene.animator.clear()
    assert scene.sim.farmer.facing.name == "WEST"
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w))
    scene.animator.clear()
    assert scene.sim.farmer.facing.name == "NORTH"
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    scene.animator.clear()
    assert scene.sim.turns == 3
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_u))
    assert scene.sim.turns == 2
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


def test_actions_do_not_include_wait():
    from game.models import Action

    with pytest.raises(ValueError):
        Action("wait")
    labels = {action.value for action in Action}
    assert labels == {"turn_to_up", "turn_to_down", "turn_to_left", "turn_to_right", "forward"}
