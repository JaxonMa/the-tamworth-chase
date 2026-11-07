"""Unit tests for the absolute-steering, exit-escape rules."""

from __future__ import annotations

import pytest

from game.core import Simulation, direction_between, manhattan, step_forward
from game.levels import LevelError, parse_level
from game.models import Action, Actor, Direction, GameStatus, Rank

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


def level_with(farmer, farmer_facing, cow, cow_facing, grid=OPEN, *, exits=((5, 5),), **overrides):
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


def advance(sim):
    """Consume one turn by turning to a different absolute direction."""
    target = Direction.EAST if sim.farmer.facing is not Direction.EAST else Direction.NORTH
    return sim.apply_action(Action.turn_to(target))


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
    level = level_with(start, facing, (1, 1), "north", sight_range=0)
    sim = Simulation(level)
    sim.apply_action(action)
    assert sim.farmer.pos == end_pos
    assert sim.farmer.facing is end_facing
    assert sim.turns == 1


@pytest.mark.parametrize(
    "initial, action, end_facing",
    [
        (Direction.SOUTH, Action.TURN_TO_UP, Direction.NORTH),
        (Direction.NORTH, Action.TURN_TO_RIGHT, Direction.EAST),
        (Direction.NORTH, Action.TURN_TO_DOWN, Direction.SOUTH),
        (Direction.NORTH, Action.TURN_TO_LEFT, Direction.WEST),
    ],
)
def test_turn_to_absolute_direction(initial, action, end_facing):
    level = level_with((3, 3), initial, (1, 1), "north", exits=((5, 5),), sight_range=0)
    sim = Simulation(level)
    tick = sim.apply_action(action)
    assert sim.farmer.pos == (3, 3)
    assert sim.farmer.facing is end_facing
    assert sim.turns == 1
    assert tick.invalid is False


def test_same_direction_turn_is_invalid_and_free():
    level = level_with((3, 3), "north", (1, 1), "north", exits=((5, 5),), sight_range=0)
    sim = Simulation(level)
    before = (sim.farmer, sim.cows, sim.caught, sim.turns)
    tick = sim.apply_action(Action.TURN_TO_UP)
    assert tick.invalid is True
    assert tick.message == "已朝该方向"
    assert (sim.farmer, sim.cows, sim.caught, sim.turns) == before
    assert sim.can_undo is False


def test_wait_action_is_removed():
    assert not hasattr(Action, "WAIT")
    with pytest.raises(ValueError):
        Action("wait")


def test_blocked_forward_consumes_a_turn():
    level = level_with((1, 1), "north", (5, 5), "north", exits=((4, 4),), sight_range=0)
    sim = Simulation(level)
    tick = sim.apply_action(Action.FORWARD)
    assert sim.farmer.pos == (1, 1)
    assert sim.farmer.facing is Direction.NORTH
    assert sim.turns == 1
    assert tick.blocked is True
    assert "本回合已消耗" in tick.message
    assert sim.blocked_events == 1


def test_farmer_can_enter_exit_tile():
    level = level_with((3, 4), "west", (1, 1), "north", exits=((3, 3),), sight_range=0)
    sim = Simulation(level)
    sim.apply_action(Action.FORWARD)
    assert sim.farmer.pos == (3, 3)


# ---------------------------------------------------------------------------
# Catching and winning
# ---------------------------------------------------------------------------
def test_forward_into_cow_catches_it_and_wins_single_cow():
    level = level_with((3, 3), "east", (3, 4), "west", sight_range=0)
    sim = Simulation(level)
    tick = sim.apply_action(Action.FORWARD)
    assert tick.caught == (True,)
    assert tick.status is GameStatus.WON
    assert sim.turns == 1
    assert sim.all_caught


def test_partial_catch_does_not_win():
    grid = ["#######", "#F....#", "#.C...#", "#..C..#", "#.....#", "#.....#", "#######"]
    level = make_level(grid, cow_facings=["east", "east"], exit_cells=[[5, 5]], sight_range=0)
    sim = Simulation(level)
    sim.farmer = Actor((2, 1), Direction.EAST)
    tick = sim.apply_action(Action.FORWARD)
    assert tick.caught[0] is True
    assert tick.caught[1] is False
    assert sim.status is GameStatus.PLAYING


def test_all_caught_after_a_cow_walks_into_farmer_wins():
    level = level_with((3, 3), "east", (3, 4), "west", exits=((3, 2),), sight_range=0)
    sim = Simulation(level)
    tick = sim.apply_action(Action.TURN_TO_UP)
    assert tick.caught == (True,)
    assert tick.caught_now == (0,)
    assert tick.status is GameStatus.WON


def test_caught_cow_does_not_move_or_block():
    level = level_with((2, 1), "east", (2, 2), "east", exits=((5, 5),), sight_range=0)
    sim = Simulation(level)
    sim.apply_action(Action.FORWARD)
    assert sim.all_caught
    assert sim.status is GameStatus.WON
    before = (sim.farmer, sim.cows, sim.turns, sim.status)
    tick = sim.apply_action(Action.TURN_TO_DOWN)
    assert tick.blocked is True
    assert (sim.farmer, sim.cows, sim.turns, sim.status) == before
    assert sim.cows[0].pos == (2, 2)


def test_multi_cow_all_caught_required():
    # Add a second cow explicitly; level_with only writes one C.
    grid = ["#######", "#.....#", "#.....#", "#..FCC#", "#.....#", "#.....#", "#######"]
    level = parse_level(
        {
            "id": "multi",
            "name": "两头",
            "grid": grid,
            "fj_start_direction": "east",
            "cow_facings": ["east", "east"],
            "exit_cells": [[5, 5]],
            "sight_range": 0,
            "max_turns": 30,
        }
    )
    sim = Simulation(level)
    tick = sim.apply_action(Action.FORWARD)
    assert tick.caught == (True, False)
    assert sim.status is GameStatus.PLAYING


# ---------------------------------------------------------------------------
# Turn order and cow blocking
# ---------------------------------------------------------------------------
def test_farmer_moves_before_cows():
    level = level_with((3, 3), "east", (3, 1), "east", exits=((5, 5),), sight_range=0)
    sim = Simulation(level)
    sim.apply_action(Action.FORWARD)
    assert sim.farmer.pos == (3, 4)
    assert sim.cows[0].pos == (3, 2)


def test_cows_move_in_fixed_order_and_block_each_other():
    grid = ["#######", "#F....#", "#.CC..#", "#.....#", "#.....#", "#.....#", "#######"]
    level = make_level(
        grid,
        cow_facings=["east", "east"],
        exit_cells=[[5, 5]],
        sight_range=0,
        cows_block_each_other=True,
    )
    sim = Simulation(level)
    tick = advance(sim)
    assert tick.cows[0].moved is False
    assert tick.cows[0].end_facing is Direction.SOUTH
    assert tick.cows[1].moved is True
    assert sim.cows[0].pos == (2, 2)
    assert sim.cows[1].pos == (2, 4)


def test_cows_do_not_block_by_default():
    grid = ["#######", "#F....#", "#.CC..#", "#.....#", "#.....#", "#.....#", "#######"]
    level = make_level(
        grid, cow_facings=["east", "east"], exit_cells=[[5, 5]], sight_range=0
    )
    sim = Simulation(level)
    advance(sim)
    assert sim.cows[0].pos == (2, 3)
    assert sim.cows[1].pos == (2, 4)


def test_multi_cow_order_is_deterministic():
    grid = ["#######", "#F....#", "#.CC..#", "#.....#", "#.....#", "#.....#", "#######"]
    level = make_level(
        grid,
        cow_facings=["north", "east"],
        exit_cells=[[5, 5]],
        sight_range=0,
        cows_block_each_other=True,
    )
    first = Simulation(level)
    second = Simulation(level)
    actions = [Action.TURN_TO_DOWN, Action.FORWARD, Action.TURN_TO_LEFT]
    ticks1 = []
    ticks2 = []
    for action in actions:
        ticks1.append(first.apply_action(action))
        ticks2.append(second.apply_action(action))
    assert [(c.pos, c.facing) for c in first.cows] == [
        (c.pos, c.facing) for c in second.cows
    ]
    assert ticks1 == ticks2


# ---------------------------------------------------------------------------
# Sight
# ---------------------------------------------------------------------------
def test_fj_sight_same_row_clear():
    level = level_with((3, 1), "east", (3, 5), "east", exits=((5, 5),))
    sim = Simulation(level)
    assert sim.cow_is_fleeing(0) is True


def test_fj_sight_blocked_by_wall():
    grid = ["#######", "#.....#", "#.....#", "#F#..C#", "#.....#", "#.....#", "#######"]
    level = make_level(
        grid,
        fj_start_direction="east",
        cow_facings=["east"],
        exit_cells=[[1, 5]],
    )
    assert Simulation(level).cow_is_fleeing(0) is False


def test_fj_sight_blocked_by_fixed_obstacle():
    level = make_level(
        ["#######", "#.....#", "#.....#", "#F...C#", "#.....#", "#.....#", "#######"],
        fj_start_direction="east",
        cow_facings=["east"],
        exit_cells=[[1, 5]],
        obstacles=[[3, 3]],
    )
    assert Simulation(level).cow_is_fleeing(0) is False


def test_fj_sight_respects_range():
    close = level_with((3, 1), "east", (3, 5), "east", exits=((5, 5),), sight_range=2)
    assert Simulation(close).cow_is_fleeing(0) is False
    unlimited = level_with((3, 1), "east", (3, 5), "east", exits=((5, 5),))
    assert Simulation(unlimited).cow_is_fleeing(0) is True


def test_cow_blocks_sight_when_enabled():
    grid = ["#######", "#.....#", "#.....#", "#F.C.C#", "#.....#", "#.....#", "#######"]
    blocked = make_level(
        grid,
        fj_start_direction="east",
        cow_facings=["east", "east"],
        exit_cells=[[1, 5]],
        cows_block_sight=True,
    )
    assert Simulation(blocked).cow_is_fleeing(1) is False
    clear = make_level(
        grid,
        fj_start_direction="east",
        cow_facings=["east", "east"],
        exit_cells=[[1, 5]],
        cows_block_sight=False,
    )
    assert Simulation(clear).cow_is_fleeing(1) is True


# ---------------------------------------------------------------------------
# Exit seeking and patrol
# ---------------------------------------------------------------------------
def test_cow_seeks_exit_when_farmer_out_of_sight():
    level = level_with((1, 1), "east", (3, 3), "north", exits=((3, 5),), sight_range=0)
    sim = Simulation(level)
    advance(sim)
    assert sim.cows[0].pos == (3, 3)
    assert sim.cows[0].facing is Direction.EAST
    advance(sim)
    assert sim.cows[0].pos == (3, 4)


def test_cow_seeks_exit_moves_when_facing_it():
    level = level_with((1, 1), "east", (3, 3), "east", exits=((3, 5),), sight_range=0)
    sim = Simulation(level)
    advance(sim)
    assert sim.cows[0].pos == (3, 4)


def test_cow_patrols_forward_when_exit_not_visible():
    level = level_with((1, 1), "east", (3, 3), "north", exits=((5, 5),), sight_range=0)
    sim = Simulation(level)
    tick = advance(sim)
    assert tick.cows[0].moved is True
    assert sim.cows[0].pos == (2, 3)


def test_cow_patrols_with_clockwise_turn_when_blocked():
    grid = ["#######", "#F....#", "#..#..#", "#..C..#", "#.....#", "#.....#", "#######"]
    level = level_with(
        (1, 1), "east", (3, 3), "north", grid=grid, exits=((5, 5),), sight_range=0
    )
    sim = Simulation(level)
    advance(sim)
    assert sim.cows[0].pos == (3, 3)
    assert sim.cows[0].facing is Direction.EAST


def test_exit_behind_uses_configured_tiebreak():
    left = level_with(
        (1, 1), "east", (3, 3), "north", exits=((5, 3),), exit_tiebreak="left", sight_range=0
    )
    sim = Simulation(left)
    advance(sim)
    assert sim.cows[0].facing is Direction.WEST
    right = level_with(
        (1, 1), "east", (3, 3), "north", exits=((5, 3),), exit_tiebreak="right", sight_range=0
    )
    sim2 = Simulation(right)
    advance(sim2)
    assert sim2.cows[0].facing is Direction.EAST


def test_exit_sight_range_controls_seeking():
    far = level_with(
        (1, 1), "east", (3, 3), "north", exits=((3, 5),), exit_sight_range=1, sight_range=0
    )
    sim = Simulation(far)
    advance(sim)
    assert sim.cows[0].pos == (2, 3)
    near = level_with(
        (1, 1), "east", (3, 3), "north", exits=((3, 5),), exit_sight_range=2, sight_range=0
    )
    sim2 = Simulation(near)
    advance(sim2)
    assert sim2.cows[0].pos == (3, 3)
    assert sim2.cows[0].facing is Direction.EAST


def test_seek_exit_picks_nearest_visible_exit():
    level = level_with(
        (1, 1), "east", (3, 3), "east", exits=((3, 5), (3, 4)), sight_range=0
    )
    sim = Simulation(level)
    tick = advance(sim)
    assert tick.status is GameStatus.LOST_EXIT
    assert tick.escaped_index == 0
    assert sim.cows[0].pos == (3, 4)


def test_seek_exit_breaks_distance_ties_by_coordinate():
    level = level_with(
        (1, 1), "east", (3, 3), "north", exits=((3, 1), (3, 5)), sight_range=0
    )
    sim = Simulation(level)
    advance(sim)
    assert sim.cows[0].facing is Direction.WEST


# ---------------------------------------------------------------------------
# Fleeing
# ---------------------------------------------------------------------------
def test_cow_flees_by_default_when_farmer_visible():
    level = level_with((3, 1), "east", (3, 4), "east", exits=((5, 5),))
    sim = Simulation(level)
    assert sim.cow_is_fleeing(0) is True
    tick = advance(sim)
    assert tick.cows[0].moved is True
    assert sim.cows[0].pos == (3, 5)


def test_flee_turns_when_forward_reduces_distance():
    level = level_with((3, 1), "east", (3, 5), "west", exits=((5, 5),))
    sim = Simulation(level)
    advance(sim)
    assert sim.cows[0].pos == (3, 5)
    assert sim.cows[0].facing in (Direction.NORTH, Direction.SOUTH)


def test_flee_tie_uses_flee_tiebreak():
    data = {
        "id": "flee_tie",
        "name": "逃跑平局",
        "grid": ["#######", "#.....#", "#.....#", "#.CF..#", "#.....#", "#.....#", "#######"],
        "fj_start_direction": "north",
        "cow_facings": ["east"],
        "exit_cells": [[5, 5]],
        "flee_tiebreak": "left",
    }
    sim = Simulation(parse_level(data))
    advance(sim)
    assert sim.cows[0].facing is Direction.NORTH
    data["flee_tiebreak"] = "right"
    sim_right = Simulation(parse_level(data))
    advance(sim_right)
    assert sim_right.cows[0].facing is Direction.SOUTH


def test_flee_cow_seeks_exit_when_farmer_out_of_sight():
    level = level_with(
        (1, 1), "east", (3, 3), "east", exits=((3, 5),), sight_range=0
    )
    sim = Simulation(level)
    advance(sim)
    assert sim.cows[0].pos == (3, 4)


def test_flee_has_priority_over_exit():
    level = level_with((3, 4), "east", (3, 3), "east", exits=((3, 5),))
    sim = Simulation(level)
    tick = advance(sim)
    assert sim.cows[0].pos == (3, 3)
    assert tick.status is GameStatus.PLAYING


# ---------------------------------------------------------------------------
# Exit failure, turn limit
# ---------------------------------------------------------------------------
def test_cow_reaching_exit_loses():
    level = level_with((1, 1), "east", (3, 4), "east", exits=((3, 5),), sight_range=0)
    sim = Simulation(level)
    tick = advance(sim)
    assert tick.status is GameStatus.LOST_EXIT
    assert tick.escaped_index == 0
    assert sim.turns == 1


def test_any_cow_reaching_exit_loses():
    grid = ["#######", "#F....#", "#.C...#", "#...C.#", "#.....#", "#.....#", "#######"]
    level = make_level(
        grid,
        cow_facings=["east", "east"],
        exit_cells=[[3, 5]],
        max_turns=30,
        sight_range=0,
    )
    sim = Simulation(level)
    tick = advance(sim)
    assert tick.status is GameStatus.LOST_EXIT
    assert tick.escaped_index == 1


def test_exit_failure_takes_priority_over_catching():
    level = level_with((1, 1), "east", (3, 3), "east", exits=((3, 4),), sight_range=0)
    sim = Simulation(level)
    sim.farmer = Actor((3, 4), Direction.WEST)
    tick = advance(sim)
    assert tick.status is GameStatus.LOST_EXIT
    assert tick.caught == (False,)


def test_turn_limit_loses():
    level = level_with((1, 1), "east", (5, 5), "north", exits=((1, 5),), max_turns=2, sight_range=0)
    sim = Simulation(level)
    advance(sim)
    assert sim.status is GameStatus.PLAYING
    advance(sim)
    assert sim.status is GameStatus.LOST_TURNS
    assert sim.turns == 2


def test_winning_on_last_turn_is_allowed():
    level = level_with((3, 3), "east", (3, 4), "west", exits=((5, 5),), max_turns=1, sight_range=0)
    sim = Simulation(level)
    tick = sim.apply_action(Action.FORWARD)
    assert tick.status is GameStatus.WON


# ---------------------------------------------------------------------------
# Loop hint
# ---------------------------------------------------------------------------
def test_repeating_state_is_a_hint_not_a_loss():
    grid = ["#######", "#F....#", "#.###.#", "#.#C#.#", "#.###.#", "#.....#", "#######"]
    level = make_level(
        grid,
        fj_start_direction="east",
        cow_facings=["north"],
        exit_cells=[[5, 5]],
        max_turns=30,
        sight_range=0,
    )
    sim = Simulation(level)
    hints = 0
    for _ in range(8):
        tick = advance(sim)
        hints += int(tick.loop_hint)
    assert hints >= 1
    assert sim.loop_events >= 1
    assert sim.status is GameStatus.PLAYING


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
def test_prediction_count_and_zero():
    level = level_with((1, 1), "east", (3, 3), "north", exits=((5, 5),), prediction_steps=3)
    frames = Simulation(level).predict()
    assert len(frames) == 3
    assert [f.step for f in frames] == [1, 2, 3]
    level0 = level_with((1, 1), "east", (3, 3), "north", exits=((5, 5),), prediction_steps=0)
    assert Simulation(level0).predict() == []


def test_prediction_keeps_farmer_fixed_and_matches_projected_cows():
    level = level_with((3, 1), "east", (3, 5), "east", exits=((5, 5),), prediction_steps=3)
    sim = Simulation(level)
    farmer = sim.farmer
    frames = sim.predict(3)
    actual = []
    probe = Simulation(level)
    for _ in range(3):
        advance(probe)
        actual.append(tuple(cow.pos for cow in probe.cows))
    assert sim.farmer == farmer
    assert [f.cow_positions for f in frames] == actual


def test_prediction_marks_exit():
    level = level_with((1, 1), "east", (3, 4), "east", exits=((3, 5),), sight_range=0)
    frames = Simulation(level).predict(3)
    assert frames
    assert frames[0].status is GameStatus.LOST_EXIT
    assert frames[0].escaped_index == 0


def test_prediction_records_caught_flags():
    level = level_with((3, 3), "east", (3, 4), "west", exits=((3, 2),), sight_range=0)
    frames = Simulation(level).predict(2)
    assert frames[0].caught == (True,)


def test_prediction_does_not_mutate_state():
    level = level_with((1, 1), "east", (3, 3), "north", exits=((5, 5),))
    sim = Simulation(level)
    before = (sim.farmer, sim.cows, sim.caught, sim.turns, sim.status)
    sim.predict(5)
    assert (sim.farmer, sim.cows, sim.caught, sim.turns, sim.status) == before


# ---------------------------------------------------------------------------
# Undo / reset
# ---------------------------------------------------------------------------
def test_undo_restores_everything():
    level = level_with((3, 3), "east", (5, 5), "north", exits=((1, 5),), sight_range=0)
    sim = Simulation(level)
    sim.apply_action(Action.FORWARD)
    after_one = (sim.farmer, sim.cows, sim.caught, sim.turns)
    sim.apply_action(Action.TURN_TO_UP)
    sim.apply_action(Action.TURN_TO_DOWN)
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
    sim = Simulation(level)
    for _ in range(5):
        advance(sim)
    assert sim.undo_to_turn(2) is True
    assert sim.turns == 2


def test_undo_after_exit_failure_restores_play():
    level = level_with((1, 1), "east", (3, 4), "east", exits=((3, 5),), sight_range=0)
    sim = Simulation(level)
    advance(sim)
    assert sim.status is GameStatus.LOST_EXIT
    assert sim.undo() is True
    assert sim.status is GameStatus.PLAYING
    assert sim.turns == 0
    assert sim.cows[0].pos == (3, 4)


def test_reset_restores_initial_state():
    level = level_with((3, 3), "east", (5, 5), "north", exits=((1, 5),))
    sim = Simulation(level)
    sim.apply_action(Action.FORWARD)
    sim.reset()
    assert sim.turns == 0
    assert sim.farmer.pos == (3, 3)
    assert sim.farmer.facing is Direction.EAST
    assert sim.caught == (False,)
    assert sim.status is GameStatus.PLAYING


def test_undo_restores_caught_flags():
    level = level_with((3, 3), "east", (3, 4), "west", exits=((5, 5),), sight_range=0)
    sim = Simulation(level)
    sim.apply_action(Action.FORWARD)
    assert sim.all_caught
    assert sim.undo() is True
    assert sim.caught == (False,)
    assert sim.status is GameStatus.PLAYING
    assert sim.turns == 0


def test_caught_cow_stops_moving_while_others_continue():
    grid = ["#######", "#.....#", "#.C...#", "#..C..#", "#.....#", "#F....#", "#######"]
    level = parse_level(
        {
            "id": "partial",
            "name": "部分抓住",
            "grid": grid,
            "fj_start_direction": "north",
            "cow_facings": ["east", "east"],
            "exit_cells": [[1, 5]],
            "max_turns": 30,
            "sight_range": 0,
        }
    )
    sim = Simulation(level)
    sim.farmer = Actor((2, 1), Direction.EAST)
    sim.apply_action(Action.FORWARD)
    caught_position = sim.cows[0].pos
    assert sim.caught[0] is True
    assert sim.caught[1] is False
    advance(sim)
    assert sim.cows[0].pos == caught_position
    assert sim.cows[1].pos != (3, 3) or sim.cows[1].facing is not Direction.EAST


# ---------------------------------------------------------------------------
# Schema, geometry, scoring
# ---------------------------------------------------------------------------
def test_defaults_are_up_and_unlimited_sight():
    level = parse_level(
        {
            "id": "defaults",
            "name": "默认",
            "grid": ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
            "exit_cells": [[1, 5]],
        }
    )
    assert level.farmer_facing is Direction.NORTH
    assert level.sight_range == -1
    assert level.exit_sight_range == -1
    assert level.cows_block_sight is False
    assert level.cows_block_each_other is False


def test_legacy_fields_fall_back_and_removed_fields_are_ignored():
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
            "cow_behavior": ["seek_exit", "seek_exit_and_flee"],
            "cow_personalities": ["stubborn"],
        }
    )
    assert level.max_turns == 12
    assert level.farmer_facing is Direction.EAST
    assert level.exit_cells
    assert level.extra.get("legacy_exit") is True
    assert level.obstacles == ()
    assert "cow_behavior" not in level.extra
    assert not hasattr(level, "cow_behaviors")


def test_cow_behavior_is_ignored_not_rejected():
    level = make_level(
        ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
        cow_behavior="sleep",
        exit_cells=[[1, 5]],
    )
    assert not hasattr(level, "cow_behaviors")


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
    assert Simulation(level).board.walkable((2, 4)) is False


def test_invalid_exit_on_wall_is_rejected():
    with pytest.raises(LevelError):
        make_level(
            ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
            exit_cells=[[0, 0]],
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
    level = level_with((3, 3), "east", (3, 4), "west", sight_range=0)
    sim = Simulation(level)
    sim.apply_action(Action.FORWARD)
    before = (sim.farmer, sim.cows, sim.turns, sim.status)
    tick = sim.apply_action(Action.TURN_TO_UP)
    assert tick.blocked is True
    assert (sim.farmer, sim.cows, sim.turns, sim.status) == before


def test_near_exit_and_blocked_cows_move():
    level = level_with((1, 1), "north", (3, 3), "north", exits=((5, 5),), sight_range=0)
    sim = Simulation(level)
    assert (5, 5) not in sim.near_exit(3)
    before = sim.cows[0].pos
    tick = sim.apply_action(Action.FORWARD)
    assert tick.blocked is True
    assert sim.cows[0].pos != before


def test_state_key_tracks_facing_and_caught():
    level = level_with((3, 3), "east", (3, 4), "west", sight_range=0)
    first = Simulation(level)
    second = Simulation(level)
    assert first.state_key() == second.state_key()
    first.apply_action(Action.FORWARD)
    assert first.caught == (True,)
    assert first.state_key() != second.state_key()


def test_clone_is_independent_and_deterministic():
    level = level_with((3, 3), "east", (5, 5), "north", exits=((1, 5),), sight_range=0)
    first = Simulation(level)
    advance(first)
    clone = first.clone()
    clone.apply_action(Action.FORWARD)
    assert first.turns == 1
    assert clone.turns == 2
    assert first.cows == first.clone().cows
