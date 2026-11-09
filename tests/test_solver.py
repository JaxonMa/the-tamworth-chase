"""Shared solver tests: shortest wins, unsolvable worlds and consistency."""

from __future__ import annotations

from game.core import Simulation
from game.levels import load_level_file, load_levels, parse_level
from game.models import Action, GameStatus
from game.solver import solve_level


def small_level():
    return load_levels()[0]


def unsolvable_level():
    return parse_level(
        {
            "id": "solver_blocked",
            "name": "围死",
            "grid": [
                "#######",
                "#F....#",
                "##....#",
                "#C#####",
                "##....#",
                "#.....#",
                "#######",
            ],
            "fj_start_direction": "north",
            "cow_facings": ["north"],
            "exit_cells": [[1, 5]],
            "max_turns": 30,
        }
    )


def test_solver_finds_shortest_win_and_replays():
    level = small_level()
    result = solve_level(level)
    assert result.status == "solved"
    assert result.turns > 0
    assert result.actions
    sim = Simulation(level)
    for item in result.actions:
        sim.apply_action(Action(item))
    assert sim.status is GameStatus.WON
    assert sim.turns == result.turns


def test_solver_is_deterministic():
    first = solve_level(small_level())
    second = solve_level(small_level())
    assert first.status == second.status == "solved"
    assert first.turns == second.turns
    assert first.actions == second.actions
    assert first.explored == second.explored


def test_solver_marks_exhausted_search_unsolvable():
    result = solve_level(unsolvable_level(), max_nodes=100_000)
    assert result.status == "unsolvable"
    assert result.explored > 0


def test_solver_reports_limit_instead_of_claiming_unsolvable():
    result = solve_level(unsolvable_level(), max_nodes=1)
    assert result.status == "limit"
    assert result.is_limit


def test_all_shipped_levels_are_solvable():
    for level in load_levels():
        result = solve_level(level, max_nodes=100_000)
        assert result.solved, level.level_id
        assert result.turns <= level.max_turns

    from game.paths import project_root

    for level in load_level_file(project_root() / "levels" / "challenges.json", source="challenge"):
        result = solve_level(level, max_nodes=100_000)
        assert result.solved, level.level_id
        assert result.turns <= level.max_turns
