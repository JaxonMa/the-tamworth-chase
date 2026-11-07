"""Unit tests for the tank-driving, exit-escape rules."""

from __future__ import annotations

import pytest

from game.core import Simulation, direction_between, manhattan, step_forward
from game.levels import LevelError, parse_level
from game.models import (
    Action,
    Actor,
    CowBehavior,
    Direction,
    GameStatus,
    Rank,
    TieBreak,
)

OPEN = [
    "#######",
    "#.....#",
    "#.....#",
    "#.....#",
    "#.....#",
    "#.....#",
    "#######",
]


def make_level(grid, **overrides):
    data = {
        "id": "test",
        "name": "测试关卡",
        "grid": grid,
        "max_turns": 30,
        "prediction_steps": 5,
        "exit_cells": [[5, 5]],
        "fj_start_direction": "north",
        "cow_facings": ["north"],
    }
    data.update(overrides)
    return parse_level(data)


def level_with(
    farmer,
    farmer_facing,
    cow,
    cow_facing,
    grid=OPEN,
    *,
    exits=((5, 5),),
    **overrides,
):
    rows = [list(row) for row in grid]
    rows[farmer[0]][farmer[1]] = "F"
    rows[cow[0]][cow[1]] = "C"
    return make_level(
        ["".join(row) for row in rows],
        fj_start_direction=farmer_facing,
        cow_facings=[cow_facing],
        exit_cells=[list(pos) for pos in exits],
        **overrides,
    )


def sim_for(level):
    return Simulation(level)


# ---------------------------------------------------------------------------
# Geometry and farmer actions
# ---------------------------------------------------------------------------
def test_geometry_helpers():
    assert step_forward((3, 3), Direction.NORTH) == (2, 3)
    assert manhattan((1, 1), (4, 5)) == 7
    assert direction_between((2, 2), (2, 5)) is Direction.EAST
    assert direction_between((2, 2), (5, 2)) is Direction.SOUTH
    assert direction_between((2, 2), (3, 3)) is None


@pytest.mark.parametrize(
    "start, facing, action, end_pos, end_facing",
    [
        ((3, 3), Direction.NORTH, Action.FORWARD, (2, 3), Direction.NORTH),
        ((3, 3), Direction.EAST, Action.FORWARD, (3, 4), Direction.EAST),
        ((3, 3), Direction.SOUTH, Action.FORWARD, (4, 3), Direction.SOUTH),
        ((3, 3), Direction.WEST, Action.FORWARD, (3, 2), Direction.WEST),
    ],
)
def test_forward_in_each_direction(start, facing, action, end_pos, end_facing):
    level = level_with(start, facing, (1, 1), "north")
    sim = sim_for(level)
    sim.apply_action(action)
    assert sim.farmer.pos == end_pos
    assert sim.farmer.facing is end_facing


def test_turn_left_and_right_do_not_move():
    level = level_with((3, 3), "north", (1, 1), "north")
    sim = sim_for(level)
    sim.apply_action(Action.TURN_LEFT)
    assert sim.farmer.pos == (3, 3)
    assert sim.farmer.facing is Direction.WEST
    sim.apply_action(Action.TURN_RIGHT)
    assert sim.farmer.pos == (3, 3)
    assert sim.farmer.facing is Direction.NORTH
    assert sim.turns == 2


def test_wait_does_not_move_or_turn():
    level = level_with((3, 3), "south", (1, 1), "north")
    sim = sim_for(level)
    before = sim.farmer
    tick = sim.apply_action(Action.WAIT)
    assert sim.farmer == before
    assert tick.farmer.moved is False
    assert tick.farmer.turned is False
    assert sim.turns == 1


def test_blocked_forward_consumes_a_turn():
    level = level_with((1, 1), "north", (5, 5), "north", exits=((4, 4),))
    sim = sim_for(level)
    tick = sim.apply_action(Action.FORWARD)
    assert sim.farmer.pos == (1, 1)
    assert sim.farmer.facing is Direction.NORTH
    assert sim.turns == 1
    assert tick.blocked is True
    assert "本回合已消耗" in tick.message
    assert sim.blocked_events == 1


def test_farmer_can_enter_exit_tile():
    level = level_with((3, 4), "west", (1, 1), "north", exits=((3, 3),))
    sim = sim_for(level)
    sim.apply_action(Action.FORWARD)
    assert sim.farmer.pos == (3, 3)


# ---------------------------------------------------------------------------
# Catching and winning
# ---------------------------------------------------------------------------
def test_forward_into_cow_catches_it_and_wins_single_cow():
    level = level_with((3, 3), "east", (3, 4), "west")
    sim = sim_for(level)
    tick = sim.apply_action(Action.FORWARD)
    assert tick.caught == (True,)
    assert tick.status is GameStatus.WON
    assert sim.turns == 1
    assert sim.all_caught


def test_partial_catch_does_not_win():
    grid = [
        "#######",
        "#F....#",
        "#.C...#",
        "#..C..#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        cow_facings=["east", "east"],
        exit_cells=[[5, 5]],
        max_turns=30,
    )
    sim = sim_for(level)
    # Farmer moves east into the first cow at (2,2)? Farmer starts (1,1).
    sim.farmer = Actor((2, 1), Direction.EAST)
    tick = sim.apply_action(Action.FORWARD)
    assert tick.caught[0] is True
    assert tick.caught[1] is False
    assert sim.status is GameStatus.PLAYING


def test_all_caught_after_cow_walks_into_farmer_wins():
    level = level_with((3, 3), "east", (3, 4), "west")
    sim = sim_for(level)
    tick = sim.apply_action(Action.WAIT)
    assert tick.caught == (True,)
    assert tick.caught_now == (0,)
    assert tick.status is GameStatus.WON


def test_caught_cow_does_not_move_or_block():
    grid = [
        "#######",
        "#F....#",
        "#.C...#",
        "#.....#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        cow_facings=["east"],
        exit_cells=[[5, 5]],
        cows_block_each_other=True,
    )
    sim = sim_for(level)
    # Catch the cow manually through a forward move.
    sim.farmer = Actor((2, 1), Direction.EAST)
    sim.apply_action(Action.FORWARD)
    assert sim.all_caught
    assert sim.status is GameStatus.WON
    tick = sim.apply_action(Action.WAIT)
    assert tick.blocked is True
    assert sim.cows[0].pos == (2, 2)


# ---------------------------------------------------------------------------
# Turn order
# ---------------------------------------------------------------------------
def test_farmer_moves_before_cows():
    level = level_with((3, 3), "east", (3, 1), "east", exits=((5, 5),))
    sim = sim_for(level)
    sim.apply_action(Action.FORWARD)
    # The farmer is at (3,4); the cow walks into the old tile (3,3).
    assert sim.farmer.pos == (3, 4)
    assert sim.cows[0].pos == (3, 2)


def test_cows_move_in_fixed_order():
    grid = [
        "#######",
        "#F....#",
        "#.CC..#",
        "#.....#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        cow_facings=["east", "east"],
        exit_cells=[[5, 5]],
        cows_block_each_other=True,
    )
    sim = sim_for(level)
    tick = sim.apply_action(Action.WAIT)
    assert tick.cows[0].moved is False
    assert tick.cows[0].end_facing is Direction.SOUTH
    assert tick.cows[1].moved is True
    assert sim.cows[0].pos == (2, 2)
    assert sim.cows[1].pos == (2, 4)


def test_cows_do_not_block_by_default():
    grid = [
        "#######",
        "#F....#",
        "#.CC..#",
        "#.....#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(grid, cow_facings=["east", "east"], exit_cells=[[5, 5]])
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (2, 3)
    assert sim.cows[1].pos == (2, 4)


def test_multi_cow_order_is_deterministic():
    grid = [
        "#######",
        "#F....#",
        "#.CC..#",
        "#.....#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        cow_facings=["north", "east"],
        exit_cells=[[5, 5]],
        cows_block_each_other=True,
    )
    first = sim_for(level)
    second = sim_for(level)
    a = first.apply_action(Action.WAIT)
    b = second.apply_action(Action.WAIT)
    assert [(c.pos, c.facing) for c in first.cows] == [(c.pos, c.facing) for c in second.cows]
    assert a.cows == b.cows


# ---------------------------------------------------------------------------
# Sight ranges
# ---------------------------------------------------------------------------
def test_fj_sight_same_row_clear():
    level = level_with(
        (3, 1),
        "east",
        (3, 5),
        "east",
        exits=((5, 5),),
        cow_behavior="seek_exit_and_flee",
    )
    sim = sim_for(level)
    assert sim.cow_is_fleeing(0) is True


def test_fj_sight_blocked_by_wall():
    grid = [
        "#######",
        "#.....#",
        "#.....#",
        "#F#..C#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        fj_start_direction="east",
        cow_facings=["east"],
        exit_cells=[[1, 5]],
        cow_behavior="seek_exit_and_flee",
    )
    sim = sim_for(level)
    assert sim.cow_is_fleeing(0) is False


def test_fj_sight_respects_range():
    level = level_with(
        (3, 1),
        "east",
        (3, 5),
        "east",
        exits=((5, 5),),
        cow_behavior="seek_exit_and_flee",
        sight_range=2,
    )
    sim = sim_for(level)
    assert sim.cow_is_fleeing(0) is False
    level2 = level_with(
        (3, 1),
        "east",
        (3, 5),
        "east",
        exits=((5, 5),),
        cow_behavior="seek_exit_and_flee",
        sight_range=-1,
    )
    assert sim_for(level2).cow_is_fleeing(0) is True


def test_cow_blocks_sight_when_enabled():
    grid = [
        "#######",
        "#.....#",
        "#.....#",
        "#F.C.C#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        fj_start_direction="east",
        cow_facings=["east", "east"],
        exit_cells=[[1, 5]],
        cow_behavior="seek_exit_and_flee",
        cows_block_sight=True,
    )
    sim = sim_for(level)
    assert sim.cow_is_fleeing(1) is False
    level2 = make_level(
        grid,
        fj_start_direction="east",
        cow_facings=["east", "east"],
        exit_cells=[[1, 5]],
        cow_behavior="seek_exit_and_flee",
        cows_block_sight=False,
    )
    assert sim_for(level2).cow_is_fleeing(1) is True


# ---------------------------------------------------------------------------
# Exit seeking
# ---------------------------------------------------------------------------
def test_seek_exit_turns_then_moves():
    level = level_with((1, 1), "east", (3, 3), "north", exits=((3, 5),))
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (3, 3)
    assert sim.cows[0].facing is Direction.EAST
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (3, 4)


def test_seek_exit_moves_when_facing_it():
    level = level_with((1, 1), "east", (3, 3), "east", exits=((3, 5),))
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (3, 4)


def test_patrol_turns_right_when_exit_not_visible():
    grid = [
        "#######",
        "#F....#",
        "#..#..#",
        "#..C..#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = level_with((1, 1), "east", (3, 3), "north", grid=grid, exits=((5, 5),))
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (3, 3)
    assert sim.cows[0].facing is Direction.EAST


def test_patrol_moves_forward_when_clear():
    level = level_with((1, 1), "east", (3, 3), "north", exits=((5, 5),))
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    # The first patrol turn moved north (not the second); assert through a fresh sim.
    fresh = sim_for(level)
    tick = fresh.apply_action(Action.WAIT)
    assert tick.cows[0].moved is True
    assert fresh.cows[0].pos == (2, 3)


def test_exit_behind_uses_configured_tiebreak():
    level = level_with(
        (1, 1),
        "east",
        (3, 3),
        "north",
        exits=((5, 3),),
        exit_tiebreak="left",
    )
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].facing is Direction.WEST
    right = level_with(
        (1, 1),
        "east",
        (3, 3),
        "north",
        exits=((5, 3),),
        exit_tiebreak="right",
    )
    sim2 = sim_for(right)
    sim2.apply_action(Action.WAIT)
    assert sim2.cows[0].facing is Direction.EAST


# ---------------------------------------------------------------------------
# Fleeing
# ---------------------------------------------------------------------------
def test_flee_forward_increases_distance():
    level = level_with(
        (3, 1),
        "east",
        (3, 4),
        "east",
        exits=((5, 5),),
        cow_behavior="seek_exit_and_flee",
    )
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (3, 5)
    assert sim.farmer.pos == (3, 1)


def test_flee_turns_when_forward_reduces_distance():
    level = level_with(
        (3, 1),
        "east",
        (3, 5),
        "west",
        exits=((5, 5),),
        cow_behavior="seek_exit_and_flee",
    )
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (3, 5)
    assert sim.cows[0].facing in (Direction.NORTH, Direction.SOUTH)


def test_flee_tie_uses_flee_tiebreak():
    level = parse_level(
        {
            "id": "flee_tie",
            "name": "逃跑平局",
            "grid": ["#######", "#..#..#", "#..C..#", "#..F..#", "#.....#", "#.....#", "#######"],
            "fj_start_direction": "north",
            "cow_facings": ["north"],
            "exit_cells": [[5, 5]],
            "cow_behavior": "seek_exit_and_flee",
            "flee_tiebreak": "left",
        }
    )
    sim = Simulation(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].facing is Direction.WEST


def test_flee_cow_seeks_exit_when_farmer_out_of_sight():
    grid = [
        "#######",
        "#F....#",
        "#..#..#",
        "#..#C.#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        fj_start_direction="east",
        cow_facings=["east"],
        exit_cells=[[3, 5]],
        cow_behavior="seek_exit_and_flee",
    )
    sim = sim_for(level)
    # The wall blocks sight; the cow should still move toward the visible exit.
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (3, 5)


def test_exit_sight_range_controls_seeking():
    level = level_with(
        (1, 1),
        "east",
        (3, 3),
        "north",
        exits=((3, 5),),
        exit_sight_range=1,
    )
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (2, 3)
    assert sim.cows[0].facing is Direction.NORTH
    near = level_with(
        (1, 1),
        "east",
        (3, 3),
        "north",
        exits=((3, 5),),
        exit_sight_range=2,
    )
    sim2 = sim_for(near)
    sim2.apply_action(Action.WAIT)
    assert sim2.cows[0].pos == (3, 3)
    assert sim2.cows[0].facing is Direction.EAST


def test_flee_has_priority_over_exit():
    level = level_with(
        (3, 4),
        "east",
        (3, 3),
        "east",
        exits=((3, 5),),
        cow_behavior="seek_exit_and_flee",
    )
    sim = sim_for(level)
    tick = sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (3, 3)
    assert tick.caught == (False,)


# ---------------------------------------------------------------------------
# Exit failure and turn limit
# ---------------------------------------------------------------------------
def test_cow_reaching_exit_loses():
    level = level_with((1, 1), "east", (3, 4), "east", exits=((3, 5),))
    sim = sim_for(level)
    tick = sim.apply_action(Action.WAIT)
    assert tick.status is GameStatus.LOST_EXIT
    assert tick.escaped_index == 0
    assert sim.turns == 1


def test_any_cow_reaching_exit_loses():
    grid = [
        "#######",
        "#F....#",
        "#.C...#",
        "#...C.#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        cow_facings=["east", "east"],
        exit_cells=[[3, 5]],
        max_turns=30,
    )
    sim = sim_for(level)
    tick = sim.apply_action(Action.WAIT)
    assert tick.status is GameStatus.LOST_EXIT
    assert tick.escaped_index == 1


def test_turn_limit_loses():
    level = level_with((1, 1), "east", (5, 5), "north", exits=((1, 5),), max_turns=2)
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.status is GameStatus.PLAYING
    sim.apply_action(Action.WAIT)
    assert sim.status is GameStatus.LOST_TURNS
    assert sim.turns == 2


def test_turn_limit_does_not_cancel_win():
    level = level_with((3, 3), "east", (3, 4), "west", exits=((5, 5),), max_turns=1)
    sim = sim_for(level)
    tick = sim.apply_action(Action.FORWARD)
    assert tick.status is GameStatus.WON


# ---------------------------------------------------------------------------
# Loop hint
# ---------------------------------------------------------------------------
def test_repeating_state_is_a_hint_not_a_loss():
    grid = [
        "#######",
        "#F....#",
        "#.###.#",
        "#.#C#.#",
        "#.###.#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        fj_start_direction="east",
        cow_facings=["north"],
        exit_cells=[[5, 5]],
        max_turns=30,
    )
    sim = sim_for(level)
    hints = 0
    for _ in range(8):
        tick = sim.apply_action(Action.WAIT)
        hints += int(tick.loop_hint)
    assert hints >= 1
    assert sim.loop_events >= 1
    assert sim.status is GameStatus.PLAYING


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
def test_prediction_count_and_zero():
    level = level_with((1, 1), "east", (3, 3), "north", exits=((5, 5),), prediction_steps=3)
    sim = sim_for(level)
    frames = sim.predict()
    assert len(frames) == 3
    assert [f.step for f in frames] == [1, 2, 3]
    level0 = level_with((1, 1), "east", (3, 3), "north", exits=((5, 5),), prediction_steps=0)
    assert sim_for(level0).predict() == []


def test_prediction_keeps_farmer_fixed_and_matches_waiting():
    level = level_with((3, 1), "east", (3, 5), "east", exits=((5, 5),))
    sim = sim_for(level)
    frames = sim.predict(3)
    assert all(f.cow_positions for f in frames)
    actual = []
    for _ in range(3):
        sim.apply_action(Action.WAIT)
        actual.append(tuple(cow.pos for cow in sim.cows))
    assert [f.cow_positions for f in frames] == actual


def test_prediction_marks_exit():
    level = level_with((1, 1), "east", (3, 4), "east", exits=((3, 5),))
    sim = sim_for(level)
    frames = sim.predict(3)
    assert frames
    assert frames[0].status is GameStatus.LOST_EXIT
    assert frames[0].escaped_index == 0


def test_prediction_records_caught_flags():
    level = level_with((3, 3), "east", (3, 4), "west")
    sim = sim_for(level)
    frames = sim.predict(2)
    assert frames[0].caught == (True,)


def test_prediction_does_not_mutate_state():
    level = level_with((1, 1), "east", (3, 3), "north", exits=((5, 5),))
    sim = sim_for(level)
    before = (sim.farmer, sim.cows, sim.caught, sim.turns, sim.status)
    sim.predict(5)
    assert (sim.farmer, sim.cows, sim.caught, sim.turns, sim.status) == before


# ---------------------------------------------------------------------------
# Undo / reset
# ---------------------------------------------------------------------------
def test_undo_restores_everything():
    level = level_with((3, 3), "east", (5, 5), "north", exits=((1, 5),))
    sim = sim_for(level)
    sim.apply_action(Action.FORWARD)
    after_one = (sim.farmer, sim.cows, sim.caught, sim.turns)
    sim.apply_action(Action.TURN_LEFT)
    sim.apply_action(Action.WAIT)
    assert sim.undo() is True
    assert (sim.farmer, sim.cows, sim.caught, sim.turns) != after_one
    assert sim.undo() is True
    assert (sim.farmer, sim.cows, sim.caught, sim.turns) == after_one
    assert sim.undo() is True
    assert sim.turns == 0
    assert sim.status is GameStatus.PLAYING
    assert sim.undo() is False


def test_undo_to_any_turn():
    level = level_with((3, 3), "east", (5, 5), "north", exits=((1, 5),), max_turns=30)
    sim = sim_for(level)
    for _ in range(5):
        sim.apply_action(Action.WAIT)
    assert sim.undo_to_turn(2) is True
    assert sim.turns == 2


def test_reset_restores_initial_state():
    level = level_with((3, 3), "east", (5, 5), "north", exits=((1, 5),))
    sim = sim_for(level)
    sim.apply_action(Action.FORWARD)
    sim.reset()
    assert sim.turns == 0
    assert sim.farmer.pos == (3, 3)
    assert sim.farmer.facing is Direction.EAST
    assert sim.caught == (False,)
    assert sim.status is GameStatus.PLAYING


# ---------------------------------------------------------------------------
# Schema compatibility and scoring
# ---------------------------------------------------------------------------
def test_legacy_fields_fall_back():
    level = parse_level(
        {
            "id": "legacy",
            "name": "旧关卡",
            "grid": ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
            "farmer_facing": "east",
            "cow_facings": ["north"],
            "step_limit": 12,
            "obstacle_limit": 1,
            "initial_obstacles": 2,
            "pen_cells": [[5, 5]],
            "win_condition": "pen",
            "cow_personalities": ["stubborn"],
        }
    )
    assert level.max_turns == 12
    assert level.farmer_facing is Direction.EAST
    assert level.exit_cells
    assert level.extra.get("legacy_exit") is True
    assert level.obstacles == ()


def test_missing_behavior_defaults_to_seek_exit():
    level = level_with((1, 1), "east", (3, 3), "north")
    assert level.cow_behaviors == (CowBehavior.SEEK_EXIT,)


def test_behavior_list_is_per_cow():
    level = make_level(
        ["#######", "#F....#", "#.CC..#", "#.....#", "#######"],
        cow_facings=["east", "west"],
        exit_cells=[[3, 5]],
        cow_behavior=["seek_exit", "seek_exit_and_flee"],
    )
    assert level.cow_behaviors == (
        CowBehavior.SEEK_EXIT,
        CowBehavior.SEEK_EXIT_AND_FLEE,
    )


def test_fixed_walls_and_obstacles():
    level = make_level(
        ["#######", "#F....#", "#.....#", "#....C#", "#######"],
        fj_start_direction="east",
        cow_facings=["east"],
        exit_cells=[[1, 5]],
        walls=[[2, 3]],
        obstacles=[[2, 4]],
    )
    assert level.tile_at((2, 3)).blocking
    assert level.obstacles == ((2, 4),)
    assert level.is_blocking((2, 4))
    sim = Simulation(level)
    assert sim.board.walkable((2, 4)) is False


def test_invalid_exit_on_wall_is_rejected():
    with pytest.raises(LevelError):
        make_level(
            ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
            exit_cells=[[0, 0]],
        )


def test_invalid_behavior_is_rejected():
    with pytest.raises(LevelError):
        make_level(
            ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
            cow_behavior="sleep",
        )


def test_rank_thresholds():
    level = level_with(
        (1, 1),
        "east",
        (3, 3),
        "north",
        s_threshold=10,
        a_threshold=20,
        b_threshold=30,
    )
    assert level.rank_for(8) is Rank.S
    assert level.rank_for(10) is Rank.S
    assert level.rank_for(11) is Rank.A
    assert level.rank_for(21) is Rank.B
    assert level.rank_for(31) is Rank.C


def test_actions_after_finish_are_ignored():
    level = level_with((3, 3), "east", (3, 4), "west")
    sim = sim_for(level)
    sim.apply_action(Action.FORWARD)
    before = (sim.farmer, sim.cows, sim.turns, sim.status)
    tick = sim.apply_action(Action.WAIT)
    assert tick.blocked is True
    assert (sim.farmer, sim.cows, sim.turns, sim.status) == before


def test_near_exit():
    level = level_with((1, 1), "east", (3, 4), "north", exits=((3, 5),))
    sim = sim_for(level)
    assert (3, 5) in sim.near_exit(3)


def test_blocked_forward_still_moves_cows():
    level = level_with((1, 1), "north", (3, 3), "north", exits=((5, 5),))
    sim = sim_for(level)
    before = sim.cows[0].pos
    tick = sim.apply_action(Action.FORWARD)
    assert tick.blocked is True
    assert sim.cows[0].pos != before


def test_exit_failure_takes_priority_over_catching():
    level = level_with(
        (1, 1),
        "east",
        (3, 3),
        "east",
        exits=((3, 4),),
    )
    sim = sim_for(level)
    # Put the farmer on the exit; the cow walks into him and the exit.
    sim.farmer = Actor((3, 4), Direction.WEST)
    tick = sim.apply_action(Action.WAIT)
    assert tick.status is GameStatus.LOST_EXIT
    assert tick.caught == (False,)


def test_seek_exit_picks_nearest_visible_exit():
    level = level_with(
        (1, 1),
        "east",
        (3, 1),
        "east",
        exits=((3, 5), (3, 3)),
    )
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == (3, 2)


def test_seek_exit_breaks_distance_ties_by_coordinate():
    level = level_with(
        (1, 1),
        "east",
        (3, 3),
        "north",
        exits=((3, 1), (3, 5)),
    )
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    # Both exits are distance 2; the lexicographically smaller (3,1) wins.
    assert sim.cows[0].facing is Direction.WEST


def test_flee_tiebreak_right():
    level = parse_level(
        {
            "id": "flee_tie_right",
            "name": "逃跑平局右",
            "grid": ["#######", "#..#..#", "#..C..#", "#..F..#", "#.....#", "#.....#", "#######"],
            "fj_start_direction": "north",
            "cow_facings": ["north"],
            "exit_cells": [[5, 5]],
            "cow_behavior": "seek_exit_and_flee",
            "flee_tiebreak": "right",
        }
    )
    sim = Simulation(level)
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].facing is Direction.EAST


def test_fixed_obstacle_blocks_sight():
    level = level_with(
        (3, 1),
        "east",
        (3, 5),
        "east",
        exits=((1, 5),),
        cow_behavior="seek_exit_and_flee",
    )
    level = parse_level(
        {
            "id": "obstacle_sight",
            "name": "障碍挡视线",
            "grid": ["#######", "#.....#", "#.....#", "#F...C#", "#.....#", "#.....#", "#######"],
            "fj_start_direction": "east",
            "cow_facings": ["east"],
            "exit_cells": [[1, 5]],
            "cow_behavior": "seek_exit_and_flee",
            "obstacles": [[3, 3]],
        }
    )
    sim = Simulation(level)
    assert sim.cow_is_fleeing(0) is False


def test_undo_after_exit_failure_restores_play():
    level = level_with((1, 1), "east", (3, 4), "east", exits=((3, 5),))
    sim = sim_for(level)
    sim.apply_action(Action.WAIT)
    assert sim.status is GameStatus.LOST_EXIT
    assert sim.undo() is True
    assert sim.status is GameStatus.PLAYING
    assert sim.turns == 0
    assert sim.cows[0].pos == (3, 4)


def test_prediction_does_not_move_farmer():
    level = level_with((3, 1), "east", (3, 5), "east", exits=((5, 5),))
    sim = sim_for(level)
    farmer = sim.farmer
    sim.predict(4)
    assert sim.farmer == farmer


def test_near_exit_only_when_close():
    level = level_with((1, 1), "east", (3, 2), "north", exits=((3, 5),))
    sim = sim_for(level)
    assert sim.near_exit(2) == ()
    assert (3, 5) in sim.near_exit(3)


def test_undo_restores_caught_flags():
    level = level_with((3, 3), "east", (3, 4), "west", exits=((5, 5),))
    sim = sim_for(level)
    sim.apply_action(Action.FORWARD)
    assert sim.all_caught
    assert sim.undo() is True
    assert sim.caught == (False,)
    assert sim.status is GameStatus.PLAYING
    assert sim.turns == 0


def test_caught_cow_stops_moving_while_others_continue():
    grid = [
        "#######",
        "#.....#",
        "#.C...#",
        "#..C..#",
        "#.....#",
        "#F....#",
        "#######",
    ]
    level = parse_level(
        {
            "id": "partial",
            "name": "部分抓住",
            "grid": grid,
            "fj_start_direction": "north",
            "cow_facings": ["east", "east"],
            "exit_cells": [[1, 5]],
            "max_turns": 30,
            "cow_behavior": "seek_exit",
        }
    )
    sim = Simulation(level)
    # Move the farmer directly next to the first cow, then catch it.
    sim.farmer = Actor((2, 1), Direction.EAST)
    sim.apply_action(Action.FORWARD)
    caught_position = sim.cows[0].pos
    assert sim.caught[0] is True
    assert sim.caught[1] is False
    sim.apply_action(Action.WAIT)
    assert sim.cows[0].pos == caught_position
    assert sim.cows[1].pos != (3, 3) or sim.cows[1].facing is not Direction.EAST
