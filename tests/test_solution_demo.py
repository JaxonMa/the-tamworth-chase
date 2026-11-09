"""Failure-dialog solution playback, restore and failure handling."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ["TAMWORTH_CHASE_DATA"] = str(tmp_path_factory.mktemp("demo-data"))
    import pygame

    pygame.init()
    from game.app import ALL_FEATURES, App

    application = App(features=ALL_FEATURES)
    yield application
    pygame.quit()


def _click(scene, pos):
    import pygame

    for event_type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        scene.handle_event(pygame.event.Event(event_type, button=1, pos=pos))


def _render(app):
    app.transition = 0.0
    app.update(1 / 60)
    return app.render_once()


def _demo_level():
    from game.levels import parse_level

    # The opening forward move wins; turning away lets the cow escape.
    return parse_level(
        {
            "id": "solution_demo",
            "name": "演示关",
            "grid": [
                "#######",
                "#.....#",
                "#.....#",
                "#..FC.#",
                "#.....#",
                "#.....#",
                "#######",
            ],
            "fj_start_direction": "east",
            "cow_facings": ["east"],
            "exit_cells": [[3, 5]],
            "max_turns": 10,
            "learning_objective": "用演示检查一条合法路线",
            "hint_text": ["这只是一条提示。"],
        }
    )


def _open_custom_failure(app):
    from game.models import Action

    app.start_level(_demo_level())
    scene = app.scene
    scene._take_action(Action.TURN_TO_UP)
    scene.animator.clear()
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.modal is not None
    assert scene.sim.status.value == "lost_exit"
    return scene


def test_failure_modal_offers_solution_and_restores_failure(app):
    scene = _open_custom_failure(app)
    labels = [button.text for button in scene.modal.buttons]
    assert "显示解法" in labels
    assert "撤销到上一回合" in labels
    assert "重开本关" in labels

    button = next(button for button in scene.modal.buttons if button.text == "显示解法")
    _click(scene, button.rect.center)
    assert scene.phase == "demo"
    assert scene.sim.turns == 0
    assert scene.sim.status.value == "playing"
    assert len(scene.demo_actions) == 1
    assert scene.modal is None

    import pygame
    from game.models import Action

    # Player controls are ignored while the computer drives.
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    assert scene.phase == "demo"
    assert scene.sim.turns == 0
    _render(app)

    for _ in range(180):
        app.update(1 / 60)
        if scene.demo_done:
            break
    assert scene.demo_done is True
    assert scene.sim.status.value == "won"
    assert scene.sim.turns == 1
    assert app.store.main_cleared("solution_demo") is False
    _render(app)

    for _ in range(180):
        app.update(1 / 60)
        if scene.phase == "result":
            break
    assert scene.phase == "result"
    assert scene.sim.status.value == "lost_exit"
    assert scene.sim.turns == 1
    assert scene._failure_sim is None
    assert scene.modal is not None
    assert scene.modal.title == "牛从出口逃走了"

    undo = next(button for button in scene.modal.buttons if button.text == "撤销到上一回合")
    _click(scene, undo.rect.center)
    assert scene.phase == "run"
    assert scene.sim.turns == 0
    assert scene.sim.status.value == "playing"
    assert scene.modal is None


def test_demo_pause_resume_and_exit_restore(app):
    from game.models import Action

    scene = _open_custom_failure(app)
    button = next(button for button in scene.modal.buttons if button.text == "显示解法")
    _click(scene, button.rect.center)
    assert scene.phase == "demo"

    pause = scene.demo_pause_button
    _click(scene, pause.rect.center)
    assert scene.demo_paused is True
    assert pause.text == "继续"
    before = scene.demo_index
    for _ in range(120):
        app.update(1 / 60)
    assert scene.demo_paused is True
    assert scene.demo_index == before
    _render(app)

    _click(scene, pause.rect.center)
    assert scene.demo_paused is False
    for _ in range(180):
        app.update(1 / 60)
        if scene.demo_index:
            break
    assert scene.demo_index == 1

    _click(scene, scene.demo_exit_button.rect.center)
    assert scene.phase == "result"
    assert scene.sim.status.value == "lost_exit"
    assert scene.sim.turns == 1
    assert scene.modal is not None
    assert scene.modal.title == "牛从出口逃走了"


def test_demo_uses_a_longer_route_and_can_be_paused(app):
    from game.models import Action

    app.start_level(app.levels[2])
    scene = app.scene
    for action in (
        Action.TURN_TO_DOWN,
        Action.TURN_TO_UP,
        Action.TURN_TO_DOWN,
        Action.TURN_TO_UP,
    ):
        scene._take_action(action)
        scene.animator.clear()
    for _ in range(120):
        app.update(1 / 60)
        if scene.result_shown:
            break
    assert scene.sim.status.value == "lost_exit"
    assert scene.modal is not None

    solution = next(button for button in scene.modal.buttons if button.text == "显示解法")
    _click(scene, solution.rect.center)
    assert scene.phase == "demo"
    assert len(scene.demo_actions) > 1

    pause = scene.demo_pause_button
    _click(scene, pause.rect.center)
    for _ in range(120):
        app.update(1 / 60)
    assert scene.demo_index == 0
    _render(app)

    _click(scene, pause.rect.center)
    for _ in range(240):
        app.update(1 / 60)
        if scene.demo_index >= 2 or scene.phase == "result":
            break
    assert scene.demo_index >= 2
    assert scene.phase == "demo"
    _click(scene, scene.demo_exit_button.rect.center)
    assert scene.phase == "result"
    assert scene.sim.status.value == "lost_exit"


@pytest.mark.parametrize(
    ("status", "reason", "needle"),
    [
        ("unsolvable", "state space exhausted", "暂时无法给出解法"),
        ("limit", "time limit", "搜索超时"),
    ],
)
def test_solution_unavailable_keeps_other_buttons(app, monkeypatch, status, reason, needle):
    from game.scenes import play as play_scene
    from game.solver import SolveResult

    scene = _open_custom_failure(app)
    monkeypatch.setattr(
        play_scene,
        "solve_level_cached",
        lambda *args, **kwargs: SolveResult(status, reason=reason),
    )
    show = next(button for button in scene.modal.buttons if button.text == "显示解法")
    _click(scene, show.rect.center)
    assert scene.phase == "result"
    assert scene.modal is not None
    assert needle in scene.modal.notice
    assert scene.toast_text.startswith("暂时无法给出解法")
    labels = [button.text for button in scene.modal.buttons]
    assert "重开本关" in labels
    _render(app)

    retry = next(button for button in scene.modal.buttons if button.text == "重开本关")
    _click(scene, retry.rect.center)
    assert scene.phase == "run"
    assert scene.sim.turns == 0
    assert scene.modal is None
