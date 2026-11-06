"""Challenge data and reference-solution tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.core import Simulation
from game.levels import load_level_file
from game.models import Direction, GameStatus, WinCondition
from game.paths import project_root

SOLUTIONS = json.loads(
    (Path(__file__).resolve().parent.parent / "tests" / "challenge_solutions.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture(scope="module")
def challenges():
    return load_level_file(project_root() / "levels" / "challenges.json", source="challenge")


def test_challenge_count_and_ids(challenges):
    assert len(challenges) == 5
    assert len({level.level_id for level in challenges}) == 5


def test_challenges_have_new_fields(challenges):
    for level in challenges:
        assert level.max_turns >= 5
        assert 0 <= level.initial_obstacles <= 9
        assert 0 <= level.prediction_steps <= 20
        assert level.win_condition in (WinCondition.CATCH, WinCondition.PEN)
        if level.is_pen_level:
            assert level.pen_cells


def test_challenge_solutions_win(challenges):
    for level in challenges:
        solution = SOLUTIONS[level.level_id]
        sim = Simulation(level, [tuple(pos) for pos in solution["obstacles"]])
        sim.start()
        for action in solution["actions"]:
            sim.order(None if action == "wait" else Direction[action.upper()])
        assert sim.status is GameStatus.WON, level.level_id
        assert sim.turns <= level.max_turns


def test_challenges_cover_variety(challenges):
    assert any(len(level.cow_positions) > 1 for level in challenges)
    assert any(level.is_pen_level for level in challenges)
    assert any(level.prediction_steps == 0 for level in challenges)
    assert any(level.cows_block_each_other for level in challenges)
