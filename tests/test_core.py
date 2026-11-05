"""Unit tests for the head-less simulation rules."""

from __future__ import annotations

import pytest

from game.core import Simulation, advance_actor, step_forward
from game.levels import LevelError, parse_level
from game.models import CowPersonality, Direction, GameStatus, Rank, TileKind

CORRIDOR = [
    "#####",
    "#.F.#",
    "#####",
    "#.C.#",
    "#####",
]

OPEN = [
    "#####",
    "#...#",
    "#...#",
    "#...#",
    "#####",
]

OPEN7 = [
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
        "obstacle_limit": 3,
        "step_limit": 40,
        "s_threshold": 12,
        "a_threshold": 20,
        "b_threshold": 30,
    }
    data.update(overrides)
    return parse_level(data)


def level_with_farmer_cow(farmer, farmer_facing, cow, cow_facing, grid=OPEN, **overrides):
    rows = [list(row) for row in grid]
    rows[farmer[0]][farmer[1]] = "F"
    rows[cow[0]][cow[1]] = "C"
    return make_level(
        ["".join(row) for row in rows],
        farmer_facing=farmer_facing,
        cow_facings=[cow_facing],
        **overrides,
    )


# ---------------------------------------------------------------------------
# Basic movement
# ---------------------------------------------------------------------------
def test_step_forward_offsets():
    assert step_forward((2, 2), Direction.NORTH) == (1, 2)
    assert step_forward((2, 2), Direction.EAST) == (2, 3)
    assert step_forward((2, 2), Direction.SOUTH) == (3, 2)
    assert step_forward((2, 2), Direction.WEST) == (2, 1)


def test_direction_clockwise_cycle():
    direction = Direction.NORTH
    order = []
    for _ in range(4):
        direction = direction.clockwise()
        order.append(direction)
    assert order == [Direction.EAST, Direction.SOUTH, Direction.WEST, Direction.NORTH]
    assert Direction.EAST.counter_clockwise() is Direction.NORTH


def test_actor_moves_forward_when_free():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    farmer_tick = sim.step().farmer
    assert farmer_tick.moved is True
    assert farmer_tick.end_pos == (1, 2)
    assert farmer_tick.end_facing is Direction.EAST


def test_blocked_actor_turns_clockwise_and_stays():
    # The farmer faces the east border wall.
    level = level_with_farmer_cow((1, 3), "east", (3, 3), "north")
    sim = Simulation(level)
    farmer_tick = sim.step().farmer
    assert farmer_tick.moved is False
    assert farmer_tick.end_pos == (1, 3)
    assert farmer_tick.start_facing is Direction.EAST
    assert farmer_tick.end_facing is Direction.SOUTH


def test_blocked_actor_turn_is_90_degrees_only():
    level = level_with_farmer_cow((1, 1), "north", (3, 3), "north")
    sim = Simulation(level)
    tick = sim.step().farmer
    assert tick.end_facing is Direction.EAST
    assert tick.moved is False


# ---------------------------------------------------------------------------
# Synchronous movement
# ---------------------------------------------------------------------------
def test_actors_swap_tiles_without_catching():
    """Both next states are computed before either is committed."""
    level = level_with_farmer_cow((2, 2), "east", (2, 3), "west")
    sim = Simulation(level)
    result = sim.step()
    assert result.caught is False
    assert result.status is GameStatus.PLAYING
    assert sim.farmer.pos == (2, 3)
    assert sim.cows[0].pos == (2, 2)


def test_simultaneous_movement_uses_old_positions():
    """A delayed (sequential) implementation would catch the cow here."""

    def blocked(pos):
        return False

    farmer = __import__("game.models", fromlist=["Actor"]).Actor((2, 2), Direction.EAST)
    cow = __import__("game.models", fromlist=["Actor"]).Actor((2, 3), Direction.WEST)
    farmer_tick = advance_actor(farmer, blocked)
    cow_tick = advance_actor(cow, blocked)
    assert farmer_tick.end_pos == (2, 3)
    assert cow_tick.end_pos == (2, 2)


def test_catch_wins():
    # The cow is blocked by the border and turns; the farmer walks into it.
    level = level_with_farmer_cow((2, 2), "east", (2, 3), "east")
    sim = Simulation(level)
    result = sim.step()
    assert result.caught is True
    assert result.status is GameStatus.WON
    assert sim.farmer.pos == sim.cows[0].pos


def test_catch_checked_before_loop_detection():
    level = level_with_farmer_cow((2, 2), "east", (2, 3), "east")
    sim = Simulation(level)
    sim.step()
    assert sim.status is GameStatus.WON
    # Stepping a finished game is a no-op.
    assert sim.step() is None


# ---------------------------------------------------------------------------
# Loop detection and step budget
# ---------------------------------------------------------------------------
def test_repeating_state_triggers_time_loop():
    level = make_level(CORRIDOR, step_limit=50)
    sim = Simulation(level)
    sim.start()
    while sim.status is GameStatus.PLAYING:
        sim.step()
    assert sim.status is GameStatus.LOST_LOOP
    assert sim.steps < 50


def test_step_limit_reached_loses():
    level = make_level(CORRIDOR, step_limit=3)
    sim = Simulation(level)
    for _ in range(3):
        sim.step()
    assert sim.status is GameStatus.LOST_STEPS
    assert sim.steps == 3


def test_state_key_contains_obstacles():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    first = Simulation(level)
    second = Simulation(level)
    second.place_obstacle((2, 2))
    assert first.state_key() != second.state_key()
    assert first.state_key()[2] == frozenset()
    assert second.state_key()[2] == frozenset({(2, 2)})


def test_state_key_contains_facing():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    first = Simulation(level)
    second = Simulation(level)
    second.farmer = second.farmer.turned(Direction.SOUTH)
    assert first.state_key() != second.state_key()


# ---------------------------------------------------------------------------
# Obstacles
# ---------------------------------------------------------------------------
def test_obstacle_blocks_movement():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    result = sim.place_obstacle((1, 2))
    assert result.ok
    tick = sim.step().farmer
    assert tick.moved is False
    assert tick.end_pos == (1, 1)
    assert tick.end_facing is Direction.SOUTH


def test_obstacle_on_wall_rejected():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    result = sim.place_obstacle((0, 2))
    assert result.ok is False
    assert "围栏" in result.message


def test_obstacle_outside_rejected():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    assert sim.place_obstacle((-1, 2)).ok is False
    assert sim.place_obstacle((9, 9)).ok is False


def test_obstacle_on_actors_rejected():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    assert sim.place_obstacle((1, 1)).ok is False
    assert sim.place_obstacle((3, 3)).ok is False
    assert sim.obstacle_count == 0


def test_obstacle_limit_enforced():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north", obstacle_limit=1)
    sim = Simulation(level)
    assert sim.place_obstacle((1, 2)).ok
    second = sim.place_obstacle((2, 2))
    assert second.ok is False
    assert "用完" in second.message
    assert sim.obstacles_left == 0


def test_obstacle_not_allowed_after_start():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    sim.start()
    assert sim.place_obstacle((1, 2)).ok is False
    sim2 = Simulation(level)
    sim2.step()
    assert sim2.place_obstacle((1, 2)).ok is False


def test_duplicate_obstacle_rejected():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    assert sim.place_obstacle((2, 2)).ok
    assert sim.place_obstacle((2, 2)).ok is False


def test_undo_obstacle():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    sim.place_obstacle((2, 2))
    assert sim.remove_obstacle((2, 2)) is True
    assert sim.obstacle_count == 0
    assert sim.remove_obstacle((2, 2)) is False


def test_reset_keeps_obstacles():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    sim.place_obstacle((2, 2))
    sim.step()
    sim.reset()
    assert sim.status is GameStatus.READY
    assert sim.steps == 0
    assert sim.obstacle_count == 1
    assert sim.farmer.pos == (1, 1)


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------
def test_prediction_matches_real_steps():
    level = level_with_farmer_cow((1, 1), "east", (5, 5), "north", grid=OPEN7, step_limit=50)
    sim = Simulation(level)
    frames = sim.predict(3)
    assert len(frames) == 3
    positions = []
    for _ in range(3):
        sim.step()
        positions.append((sim.farmer.pos, sim.cows[0].pos))
    assert [(frame.farmer_pos, frame.cow_positions[0]) for frame in frames] == positions


def test_prediction_does_not_mutate_state():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    before = (sim.farmer, sim.cows, sim.steps, sim.status)
    sim.predict(5)
    assert (sim.farmer, sim.cows, sim.steps, sim.status) == before


def test_prediction_stops_after_win():
    level = level_with_farmer_cow((2, 2), "east", (2, 3), "east")
    sim = Simulation(level)
    frames = sim.predict(3)
    assert frames and frames[0].status is GameStatus.WON
    assert len(frames) == 1


# ---------------------------------------------------------------------------
# Level parsing and scoring
# ---------------------------------------------------------------------------
def test_invalid_level_without_farmer():
    with pytest.raises(LevelError):
        parse_level({"id": "x", "name": "坏关卡", "grid": ["###", "#C#", "###"]})


def test_invalid_level_without_cow():
    with pytest.raises(LevelError):
        parse_level({"id": "x", "name": "坏关卡", "grid": ["###", "#F#", "###"]})


def test_invalid_level_row_length():
    with pytest.raises(LevelError):
        parse_level({"id": "x", "name": "坏关卡", "grid": ["#####", "#FC#", "###"]})


def test_invalid_level_unknown_char():
    with pytest.raises(LevelError):
        parse_level({"id": "x", "name": "坏关卡", "grid": ["#####", "#FX.#", "#####"]})


def test_rank_thresholds():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north", s_threshold=10, a_threshold=20, b_threshold=30)
    assert level.rank_for(8) is Rank.S
    assert level.rank_for(10) is Rank.S
    assert level.rank_for(11) is Rank.A
    assert level.rank_for(21) is Rank.B
    assert level.rank_for(31) is Rank.C


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


def test_obstacle_cannot_be_placed_on_decor_wall():
    level = make_level(
        [
            "#####",
            "#.T.#",
            "#..C#",
            "#.F.#",
            "#####",
        ]
    )
    sim = Simulation(level)
    assert sim.place_obstacle((1, 2)).ok is False


def test_personality_defaults_to_normal():
    level = level_with_farmer_cow((1, 1), "east", (3, 3), "north")
    sim = Simulation(level)
    assert sim.cows[0].personality is CowPersonality.NORMAL
