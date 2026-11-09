"""Integration smoke tests: scenes render head-less and the driving flow works."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = json.loads((ROOT / "tests" / "solutions.json").read_text(encoding="utf-8"))


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


def test_menu_renders_without_tutorial_entry(app):
    app.open_scene("menu")
    surface = _render(app)
    assert surface.get_size() == (1024, 672)
    labels = [button.text for button in app.scene.buttons]
    assert "新手教程" not in labels
    assert not hasattr(app, "catalog")
    assert not hasattr(app, "book")


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
    ["level_select", "settings", "challenge", "daily", "editor", "achievement"],
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
    assert level.extra["verification"]["status"] == "solved"


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

    app.store.set_setting("preview", True)
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


def test_learning_hints_progress_without_blocking(app):
    from game.scenes.level_select import LevelSelectScene

    app.open_scene("level_select")
    assert isinstance(app.scene, LevelSelectScene)
    card = app.scene.cards[0]
    assert card.level.learning_objective
    app.start_level(card.level)
    scene = app.scene
    assert scene.show_hints is True
    assert scene.level.hint_text
    assert scene.hint_index == 0
    scene.update(9.1)
    assert scene.hint_index == 1
    _render(app)


def test_learning_objective_does_not_gate_clear(app):
    from dataclasses import replace

    app.store.reset_main()
    level = replace(
        app.levels[0],
        learning_objective="使用预测与撤销（仅作提示）",
        hint_text=("这是提示，不是通关条件。",),
    )
    app.start_level(level)
    scene = play_actions(app, SOLUTIONS["level_01"]["actions"])
    assert scene.sim.status.value == "won"
    assert app.store.main_cleared("level_01") is True
    ids = [item.level_id for item in app.levels]
    assert app.store.is_main_unlocked(ids, "level_02") is True
    assert scene.modal is not None
    assert "另一种解法" not in scene.modal.body


def test_hints_setting_can_disable_teaching_hints(app):
    app.store.set_setting("hints", False)
    app.start_level(app.levels[0])
    scene = app.scene
    assert scene.show_hints is False
    _render(app)
    app.store.set_setting("hints", True)


def test_farmer_cannot_step_onto_exit_in_ui(app):
    from game.levels import parse_level
    from game.models import Action

    level = parse_level(
        {
            "id": "exit_block",
            "name": "出口受阻",
            "grid": ["#######", "#.....#", "#..C..#", "#.....#", "#F....#", "#.....#", "#######"],
            "fj_start_direction": "east",
            "cow_facings": ["north"],
            "exit_cells": [[4, 2]],
            "max_turns": 20,
        }
    )
    app.start_level(level)
    scene = app.scene
    scene._take_action(Action.FORWARD)
    assert scene.sim.turns == 1
    assert scene.sim.farmer.pos == (4, 1)
    assert scene.toast_text == "出口不可通行，本回合已消耗"
    _render(app)


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


def test_editor_rejects_unsolvable_export(app, tmp_path, monkeypatch):
    from game import editor as editor_module
    from game.scenes import editor as editor_scene
    from game.solver import SolveResult

    monkeypatch.setattr(editor_module, "custom_levels_dir", lambda: tmp_path)
    monkeypatch.setattr(
        editor_scene,
        "solve_level",
        lambda level, max_nodes=50_000: SolveResult("unsolvable", reason="state space exhausted"),
    )
    app.open_scene("editor")
    scene = app.scene
    scene._export()
    assert scene.exported_path is None
    assert "无解" in scene.toast_text
    assert not list(tmp_path.glob("*.json"))


def test_editor_can_export_unverified_after_timeout(app, tmp_path, monkeypatch):
    from game import editor as editor_module
    from game.scenes import editor as editor_scene
    from game.solver import SolveResult

    monkeypatch.setattr(editor_module, "custom_levels_dir", lambda: tmp_path)
    monkeypatch.setattr(
        editor_scene,
        "solve_level",
        lambda level, max_nodes=50_000: SolveResult("limit", reason="node limit"),
    )
    app.open_scene("editor")
    scene = app.scene
    scene._export()
    assert scene.modal is not None
    scene._modal_action("export_unverified")
    assert scene.exported_path is not None
    payload = json.loads(scene.exported_path.read_text(encoding="utf-8"))
    assert payload["levels"][0]["verification"]["status"] == "unverified"


def test_play_layout_is_mirrored_and_hint_card_has_no_rules_slot(app):
    from game import theme

    app.store.set_setting("hints", True)
    app.store.set_setting("preview", True)
    app.store.set_setting("alerts", True)
    app.start_level(app.levels[0])
    scene = app.scene
    assert scene.panel_rect == theme.PLAY_PANEL_RECT
    assert scene.panel_rect.right < scene.board_origin[0]
    assert scene.board_origin == (595, 211)
    assert scene.renderer.origin == scene.board_origin
    assert scene.undo_button.text == "[U] 撤销"
    assert scene.restart_button.text == "[R] 重开"
    assert scene.predict_button.text == "[P] 预测 开"
    assert scene.alert_button.text == "警觉 开"
    assert scene.undo_button.rect.left > scene.panel_rect.right

    _render(app)
    assert scene.hint_card_rect is not None
    assert scene.hint_card_rect.size == (356, 152)
    assert scene.hint_next_button.visible is True


def test_predict_button_click_toggles_only_once(app):
    app.store.set_setting("hints", True)
    app.store.set_setting("preview", True)
    app.start_level(app.levels[0])
    scene = app.scene
    assert scene.show_prediction is True
    _click(scene, scene.predict_button.rect.center)
    assert scene.show_prediction is False
    assert scene.predict_button.text == "[P] 预测 关"
    _click(scene, scene.predict_button.rect.center)
    assert scene.show_prediction is True


def test_hint_card_next_button_advances_and_hides_on_last(app):
    app.store.set_setting("hints", True)
    app.start_level(app.levels[0])
    scene = app.scene
    _render(app)
    assert scene.hint_index == 0
    assert scene.hint_next_button.visible
    _click(scene, scene.hint_next_button.rect.center)
    assert scene.hint_index == 1
    _render(app)
    assert scene.hint_next_button.visible

    while scene.hint_index < len(scene.level.hint_text) - 1:
        _click(scene, scene.hint_next_button.rect.center)
        _render(app)
    assert scene.hint_index == len(scene.level.hint_text) - 1
    assert scene.hint_next_button.visible is False


def test_hints_setting_hides_the_sidebar_hint_card(app):
    app.store.set_setting("hints", True)
    app.start_level(app.levels[0])
    _render(app)
    assert app.scene.hint_card_rect is not None
    app.store.set_setting("hints", False)
    app.start_level(app.levels[0])
    scene = app.scene
    _render(app)
    assert scene.hint_card_rect is None
    assert scene.hint_next_button.visible is False
    app.store.set_setting("hints", True)


def test_single_hint_level_uses_hint_card_without_paging(app):
    level = app.challenges[0]
    app.start_level(level, mode="challenge", challenge_key=level.level_id, return_to="challenge")
    scene = app.scene
    assert scene.level.hint_text == ()
    assert scene.level.hint
    _render(app)
    assert scene.hint_card_rect is not None
    assert scene.hint_card_rect.height == 112
    assert scene.hint_next_button.visible is False


def test_ten_by_ten_board_fills_right_stage(app):
    app.start_level(app.levels[9])
    scene = app.scene
    assert scene.board_origin == (528, 144)
    assert scene.renderer.origin == (528, 144)
    _render(app)
    assert scene.hint_card_rect is not None


def test_editor_keeps_original_board_and_panel_sides(app):
    from game import theme

    app.open_scene("editor")
    _render(app)
    assert theme.PANEL_RECT.left == 592
    assert theme.BOARD_ORIGIN == (48, 144)
    app.open_scene("menu")


def test_window_renders_natively_at_1024(app):
    from game import theme

    assert app.display.get_size() == (1024, 672)
    assert app.screen.get_size() == (1024, 672)
    assert theme.WINDOW_WIDTH == 1024
    assert theme.WINDOW_HEIGHT == 672
    assert _render(app).get_size() == (1024, 672)


def test_tutorial_hints_auto_advance_while_the_player_acts(app):
    from game.models import Action

    app.store.set_setting("hints", True)
    app.start_level(app.levels[0])
    scene = app.scene
    assert scene.hint_index == 0
    scene._take_action(Action.TURN_TO_DOWN)
    scene.animator.clear()
    scene.update(4.6)
    scene._take_action(Action.TURN_TO_UP)
    scene.animator.clear()
    scene.update(4.6)
    assert scene.hint_index == 1


def test_native_mouse_click_reaches_button(app):
    import pygame

    from game.scenes.level_select import LevelSelectScene

    app.open_scene("menu")
    button = next(button for button in app.scene.buttons if button.text == "主线关卡")
    for event_type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        app.handle_event(pygame.event.Event(event_type, button=1, pos=button.rect.center))
    assert isinstance(app.scene, LevelSelectScene)
    app.present()
    app.open_scene("menu")


def test_native_scene_widgets_stay_inside_the_window(app):
    dimensions = [(1024, 672)]
    for scene_key in ("menu", "level_select", "settings", "challenge", "daily", "editor", "achievement"):
        app.open_scene(scene_key)
        _render(app)
        scene = app.scene
        for widget in getattr(scene, "buttons", []) + getattr(scene, "widgets", []):
            rect = getattr(widget, "rect", None)
            if rect is not None:
                assert rect.right <= dimensions[0][0], scene_key
                assert rect.bottom <= dimensions[0][1], scene_key
        for card in getattr(scene, "cards", []):
            assert card.rect.right <= dimensions[0][0], scene_key
            assert card.rect.bottom <= dimensions[0][1], scene_key
        start_button = getattr(scene, "start_button", None)
        if start_button is not None:
            assert start_button.rect.right <= dimensions[0][0]
            assert start_button.rect.bottom <= dimensions[0][1]
    app.open_scene("menu")
