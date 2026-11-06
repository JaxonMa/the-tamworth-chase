"""Unit tests for the head-less turn-based chase rules."""

from __future__ import annotations

import pytest

from game.core import Simulation, advance_actor, step_forward
from game.levels import LevelError, parse_level
from game.models import Actor, Direction, GameStatus, Rank, TileKind

OPEN = [
    "#######",
    "#.....#",
    "#.....#",
    "#.....#",
    "#.....#",
    "#.....#",
    "#######",
]

CORRIDOR = [
    "#######",
    "#.F...#",
    "#.C...#",
    "#.....#",
    "#######",
]


def make_level(grid, **overrides):
    data = {
        "id": "test",
        "name": "测试关卡",
        "grid": grid,
        "max_turns": 20,
        "initial_obstacles": 3,
        "prediction_steps": 5,
        "s_threshold": 5,
        "a_threshold": 10,
        "b_threshold": 15,
    }
    data.update(overrides)
    return parse_level(data)


def level_with(farmer, farmer_facing, cow, cow_facing, grid=OPEN, **overrides):
    rows = [list(row) for row in grid]
    rows[farmer[0]][farmer[1]] = "F"
    rows[cow[0]][cow[1]] = "C"
    return make_level(
        ["".join(row) for row in rows],
        farmer_facing=farmer_facing,
        cow_facings=[cow_facing],
        **overrides,
    )


def started(level, obstacles=()):
    sim = Simulation(level, obstacles)
    sim.start()
    return sim


# ---------------------------------------------------------------------------
# Geometry and basic movement
# ---------------------------------------------------------------------------
def test_step_forward_offsets():
    assert step_forward((2, 2), Direction.NORTH) == (1, 2)
    assert step_forward((2, 2), Direction.EAST) == (2, 3)
    assert step_forward((2, 2), Direction.SOUTH) == (3, 2)
    assert step_forward((2, 2), Direction.WEST) == (2, 1)


def test_direction_cycle():
    assert Direction.NORTH.clockwise() is Direction.EAST
    assert Direction.WEST.clockwise() is Direction.NORTH
    assert Direction.NORTH.counter_clockwise() is Direction.WEST
    assert Direction.EAST.opposite() is Direction.WEST


def test_cow_moves_forward_when_free():
    level = level_with((1, 1), "east", (3, 3), "north")
    sim = started(level)
    tick = sim.order(None)
    assert tick.cows[0].moved is True
    assert tick.cows[0].end_pos == (2, 3)
    assert tick.cows[0].end_facing is Direction.NORTH


def test_cow_turns_clockwise_when_blocked():
    level = level_with((1, 1), "east", (1, 2), "north")
    sim = started(level)
    tick = sim.order(None)
    assert tick.cows[0].moved is False
    assert tick.cows[0].end_pos == (1, 2)
    assert tick.cows[0].end_facing is Direction.EAST


def test_advance_actor_is_pure():
    tick = advance_actor(Actor((2, 2), Direction.NORTH), lambda pos: False)
    assert tick.end_pos == (1, 2)
    blocked = advance_actor(Actor((2, 2), Direction.NORTH), lambda pos: True)
    assert blocked.end_pos == (2, 2)
    assert blocked.end_facing is Direction.EAST


@pytest.mark.parametrize(
    "key, target",
    [
        (Direction.NORTH, (2, 3)),
        (Direction.SOUTH, (4, 3)),
        (Direction.EAST, (3, 4)),
        (Direction.WEST, (3, 2)),
    ],
)
def test_farmer_moves_in_four_directions(key, target):
    level = level_with((3, 3), "north", (1, 1), "north")
    sim = started(level)
    tick = sim.order(key)
    assert tick.farmer.moved is True
    assert sim.farmer.pos == target
    assert sim.farmer.facing is key


def test_farmer_wait_consumes_a_turn_and_cows_move():
    level = level_with((3, 3), "north", (1, 1), "south")
    sim = started(level)
    tick = sim.order(None)
    assert tick.farmer.moved is False
    assert sim.turns == 1
    assert sim.cows[0].pos == (2, 1)


def test_farmer_cannot_leave_the_board():
    level = level_with((1, 1), "west", (3, 3), "north")
    sim = started(level)
    before = (sim.farmer, sim.cows, sim.turns)
    result = sim.order(Direction.WEST)
    assert result.blocked is True
    assert result.turns == 0
    assert (sim.farmer, sim.cows, sim.turns) == before
    assert sim.status is GameStatus.PLAYING


def test_farmer_blocked_by_wall_does_not_consume_a_turn():
    level = make_level(
        [
            "#####",
            "#.F.#",
            "#.~.#",
            "#.C.#",
            "#####",
        ],
        cow_facings=["north"],
    )
    sim = started(level)
    result = sim.order(Direction.SOUTH)
    assert result.blocked is True
    assert sim.turns == 0
    assert sim.cows[0].pos == (3, 2)


def test_farmer_blocked_by_obstacle_does_not_consume_a_turn():
    level = level_with((2, 2), "east", (5, 5), "north", grid=OPEN)
    sim = Simulation(level, [(2, 3)])
    sim.start()
    result = sim.order(Direction.EAST)
    assert result.blocked is True
    assert sim.turns == 0
    assert sim.farmer.pos == (2, 2)


def test_blocked_result_has_a_chinese_message():
    level = level_with((1, 1), "north", (3, 3), "north")
    sim = started(level)
    result = sim.order(Direction.NORTH)
    assert result.blocked
    assert "回合" in result.message


# ---------------------------------------------------------------------------
# Turn order and win conditions
# ---------------------------------------------------------------------------
def test_farmer_moving_into_cow_wins_before_cows_move():
    level = level_with((2, 2), "east", (2, 3), "east")
    sim = started(level)
    tick = sim.order(Direction.EAST)
    assert tick.caught is True
    assert tick.status is GameStatus.WON
    assert tick.cows == ()
    assert sim.cows[0].pos == (2, 3)
    assert sim.turns == 1


def test_cow_moving_into_farmer_wins_after_cow_move():
    level = level_with((2, 2), "east", (2, 3), "west")
    sim = started(level)
    tick = sim.order(None)
    assert tick.caught is True
    assert tick.status is GameStatus.WON
    assert tick.cows[0].moved is True


def test_catching_is_checked_before_the_turn_limit():
    level = level_with((2, 2), "east", (2, 3), "east", max_turns=1)
    sim = started(level)
    tick = sim.order(Direction.EAST)
    assert tick.status is GameStatus.WON
    assert sim.turns == 1


def test_turn_order_commits_farmer_first():
    # The farmer escapes east while the cow walks into the old tile.
    level = level_with((2, 2), "east", (2, 1), "east")
    sim = started(level)
    tick = sim.order(Direction.EAST)
    assert tick.caught is False
    assert sim.farmer.pos == (2, 3)
    assert sim.cows[0].pos == (2, 2)


def test_cows_move_in_fixed_order_and_block_each_other():
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
        cows_block_each_other=True,
    )
    sim = started(level)
    tick = sim.order(None)
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
    level = make_level(grid, cow_facings=["east", "east"])
    sim = started(level)
    sim.order(None)
    assert sim.cows[0].pos == (2, 3)
    assert sim.cows[1].pos == (2, 4)


def test_multi_cow_order_is_deterministic():
    level = make_level(
        [
            "#######",
            "#F....#",
            "#.CC..#",
            "#.....#",
            "#.....#",
            "#.....#",
            "#######",
        ],
        cow_facings=["north", "east"],
        cows_block_each_other=True,
    )
    first = started(level)
    second = started(level)
    a = first.order(None)
    b = second.order(None)
    assert [(c.pos, c.facing) for c in first.cows] == [
        (c.pos, c.facing) for c in second.cows
    ]
    assert a.cows == b.cows


def test_pen_win_when_cow_enters_pen():
    level = make_level(
        [
            "#######",
            "#F....#",
            "#.C...#",
            "#.....#",
            "#.....#",
            "#.....#",
            "#######",
        ],
        cow_facings=["east"],
        win_condition="pen",
        pen_cells=[[2, 3]],
    )
    sim = started(level)
    tick = sim.order(None)
    assert tick.penned is True
    assert tick.status is GameStatus.WON
    assert sim.penned_count == 1


def test_pen_requires_every_cow():
    level = make_level(
        [
            "#######",
            "#F....#",
            "#.CC..#",
            "#.....#",
            "#.....#",
            "#.....#",
            "#######",
        ],
        cow_facings=["east", "east"],
        win_condition="pen",
        pen_cells=[[2, 3]],
    )
    sim = started(level)
    tick = sim.order(None)
    assert tick.penned is False
    assert sim.status is GameStatus.PLAYING
    assert sim.penned_count == 1


def test_catch_still_wins_on_a_pen_level():
    level = make_level(
        [
            "#######",
            "#.....#",
            "#.FC..#",
            "#.....#",
            "#.....#",
            "#.....#",
            "#######",
        ],
        cow_facings=["east"],
        win_condition="pen",
        pen_cells=[[5, 5]],
    )
    sim = started(level)
    tick = sim.order(Direction.EAST)
    assert tick.caught is True
    assert tick.status is GameStatus.WON


# ---------------------------------------------------------------------------
# Loop hint and turn budget
# ---------------------------------------------------------------------------
def test_repeating_cow_pose_is_a_hint_not_a_loss():
    level = make_level(
        [
            "#######",
            "#F....#",
            "#.###.#",
            "#.#C#.#",
            "#.###.#",
            "#.....#",
            "#######",
        ],
        cow_facings=["north"],
        max_turns=30,
    )
    sim = started(level)
    hints = 0
    for _ in range(8):
        tick = sim.order(None)
        hints += int(tick.loop_hint)
        assert sim.status is GameStatus.PLAYING
    assert hints >= 1
    assert sim.loop_events >= 1
    assert sim.status is GameStatus.PLAYING


def test_turn_limit_loses():
    level = level_with((1, 1), "east", (5, 5), "north", max_turns=3)
    sim = started(level)
    for _ in range(3):
        sim.order(None)
    assert sim.status is GameStatus.LOST_TURNS
    assert sim.turns == 3


def test_turn_limit_does_not_cancel_a_win():
    level = make_level(
        [
            "#######",
            "#FC...#",
            "#.....#",
            "#.....#",
            "#.....#",
            "#.....#",
            "#######",
        ],
        cow_facings=["north"],
        max_turns=2,
    )
    sim = started(level)
    sim.order(None)
    assert sim.status is GameStatus.PLAYING
    tick = sim.order(Direction.EAST)
    assert tick.turns == 2
    assert tick.status is GameStatus.WON


def test_orders_are_ignored_after_the_game_ended():
    level = level_with((2, 2), "east", (2, 3), "east")
    sim = started(level)
    sim.order(Direction.EAST)
    before = (sim.farmer, sim.cows, sim.turns, sim.status)
    result = sim.order(None)
    assert result.blocked is True
    assert (sim.farmer, sim.cows, sim.turns, sim.status) == before


# ---------------------------------------------------------------------------
# Undo / redo
# ---------------------------------------------------------------------------
def test_undo_restores_everything():
    level = level_with((2, 2), "east", (5, 5), "north", max_turns=20)
    sim = Simulation(level, [(4, 4)])
    sim.start()
    sim.order(Direction.EAST)
    after_one = (sim.farmer, sim.cows, sim.turns, sim.obstacles)
    sim.order(Direction.SOUTH)
    after_two = (sim.farmer, sim.cows, sim.turns, sim.obstacles)
    sim.order(None)
    assert sim.undo() is True
    assert (sim.farmer, sim.cows, sim.turns, sim.obstacles) == after_two
    assert sim.undo() is True
    assert (sim.farmer, sim.cows, sim.turns, sim.obstacles) == after_one
    assert sim.undo() is True
    assert sim.turns == 0
    assert sim.status is GameStatus.PLAYING
    assert sim.undo() is True
    assert sim.status is GameStatus.READY
    assert sim.obstacles == frozenset({(4, 4)})
    assert sim.undo() is False


def test_undo_to_any_turn():
    level = level_with((2, 2), "east", (5, 5), "north", max_turns=20)
    sim = started(level)
    for _ in range(6):
        sim.order(None)
    assert sim.turns == 6
    assert sim.undo_to_turn(2) is True
    assert sim.turns == 2
    assert sim.farmer.pos == (2, 2)


def test_undo_placement_and_start():
    level = level_with((2, 2), "east", (5, 5), "north")
    sim = Simulation(level)
    sim.place_obstacle((3, 3))
    assert sim.obstacle_count == 1
    assert sim.undo() is True
    assert sim.obstacle_count == 0
    sim.place_obstacle((3, 3))
    sim.start()
    assert sim.undo() is True
    assert sim.status is GameStatus.READY
    assert sim.obstacle_count == 1


def test_redo_after_undo():
    level = level_with((2, 2), "east", (5, 5), "north")
    sim = started(level)
    sim.order(Direction.EAST)
    position = sim.farmer.pos
    sim.undo()
    assert sim.redo() is True
    assert sim.farmer.pos == position


def test_reset_keeps_layout_and_clears_turns():
    level = level_with((2, 2), "east", (5, 5), "north")
    sim = Simulation(level, [(3, 3)])
    sim.start()
    sim.order(None)
    sim.reset()
    assert sim.status is GameStatus.READY
    assert sim.turns == 0
    assert sim.obstacles == frozenset({(3, 3)})
    assert sim.can_undo is False


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
def test_prediction_uses_the_configured_number_of_steps():
    level = level_with((1, 1), "east", (5, 5), "north", prediction_steps=4)
    sim = started(level)
    frames = sim.predict()
    assert len(frames) == 4
    assert [frame.step for frame in frames] == [1, 2, 3, 4]


def test_prediction_zero_means_off():
    level = level_with((1, 1), "east", (5, 5), "north", prediction_steps=0)
    sim = started(level)
    assert sim.predict() == []


def test_prediction_does_not_mutate_state():
    level = level_with((1, 1), "east", (5, 5), "north")
    sim = started(level)
    before = (sim.farmer, sim.cows, sim.turns, sim.status)
    sim.predict(5)
    assert (sim.farmer, sim.cows, sim.turns, sim.status) == before


def test_prediction_matches_actual_waiting_turns():
    level = level_with((1, 1), "east", (5, 5), "north")
    sim = started(level)
    frames = sim.predict(3)
    actual = []
    for _ in range(3):
        sim.order(None)
        actual.append(tuple(cow.pos for cow in sim.cows))
    assert [frame.cow_positions for frame in frames] == actual


def test_prediction_works_during_placement():
    level = level_with((1, 1), "east", (5, 5), "north")
    sim = Simulation(level)
    frames = sim.predict(2)
    assert sim.status is GameStatus.READY
    assert len(frames) == 2


# ---------------------------------------------------------------------------
# Parsing and scoring
# ---------------------------------------------------------------------------
def test_rank_thresholds_use_turns():
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


def test_pen_cells_are_required_for_pen_levels():
    with pytest.raises(LevelError):
        make_level(
            [
                "#######",
                "#F....#",
                "#..C..#",
                "#.....#",
                "#######",
            ],
            win_condition="pen",
        )


def test_pen_cell_on_a_wall_is_rejected():
    with pytest.raises(LevelError):
        make_level(
            [
                "#######",
                "#F....#",
                "#..C..#",
                "#.....#",
                "#######",
            ],
            win_condition="pen",
            pen_cells=[[0, 0]],
        )


def test_invalid_condition_is_rejected():
    with pytest.raises(LevelError):
        make_level(
            [
                "#######",
                "#F....#",
                "#..C..#",
                "#.....#",
                "#######",
            ],
            win_condition="teleport",
        )


def test_legacy_step_and_obstacle_limits_are_read():
    level = parse_level(
        {
            "id": "legacy_limits",
            "name": "旧限制",
            "grid": ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
            "step_limit": 12,
            "obstacle_limit": 1,
            "cow_facings": ["north"],
        }
    )
    assert level.max_turns == 12
    assert level.initial_obstacles == 1


def test_legacy_personalities_and_items_are_ignored():
    level = parse_level(
        {
            "id": "legacy",
            "name": "旧关卡",
            "grid": ["#####", "#FC.#", "#####"],
            "cow_personalities": ["stubborn"],
            "item_counts": {"apple": 2},
            "placed_items": [{"kind": "apple", "pos": [2, 2]}],
            "apples": [[2, 2]],
        }
    )
    assert len(level.cow_positions) == 1
    assert level.max_turns == 30
    assert level.initial_obstacles == 3


def test_unknown_cow_characters_are_read_as_cows():
    level = parse_level({"id": "x", "name": "旧牛", "grid": ["#####", "#FDG#", "#####"]})
    assert len(level.cow_positions) == 2


def test_tile_kinds_blocking():
    level = make_level(
        [
            "#####",
            "#.T.#",
            "#~C.#",
            "#HF.#",
            "#####",
        ]
    )
    assert level.tile_at((1, 2)) is TileKind.TREE
    assert level.tile_at((2, 1)) is TileKind.POND
    assert level.tile_at((3, 1)) is TileKind.HEDGE
    assert level.is_blocking((1, 2)) is True
    assert level.is_blocking((1, 1)) is False
    assert level.is_blocking((-1, 1)) is True


def test_obstacle_limits_and_validation():
    level = level_with((1, 1), "east", (3, 3), "north", initial_obstacles=1)
    sim = Simulation(level)
    assert sim.place_obstacle((1, 2)).ok is True
    assert sim.place_obstacle((2, 2)).ok is False
    assert sim.place_obstacle((0, 0)).ok is False
    assert sim.place_obstacle((1, 1)).ok is False
    assert sim.place_obstacle((3, 3)).ok is False


def test_obstacles_block_the_farmer_and_cows():
    level = level_with((1, 1), "east", (3, 3), "north", initial_obstacles=2)
    sim = Simulation(level, [(2, 2), (4, 4)])
    sim.start()
    assert sim.walkable_for_farmer((2, 2)) is False
    assert sim.blocked((2, 2)) is True
    assert sim.blocked((4, 4)) is True


def test_state_key_tracks_turns_and_obstacles():
    level = level_with((1, 1), "east", (3, 3), "north")
    first = Simulation(level)
    second = Simulation(level)
    second.place_obstacle((2, 2))
    assert first.state_key() != second.state_key()
    second.start()
    second.order(None)
    assert first.state_key() != second.state_key()


def test_snapshot_is_json_friendly():
    level = level_with((1, 1), "east", (3, 3), "north")
    sim = started(level)
    snapshot = sim.snapshot()
    assert snapshot["turns"] == 0
    assert snapshot["status"] == "playing"
    assert snapshot["farmer"][1] == int(Direction.EAST)
    assert snapshot["cows"][0][1] == int(Direction.NORTH)
