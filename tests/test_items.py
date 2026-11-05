"""Tests for cow personalities and the placeable item system."""

from __future__ import annotations

from typing import Optional, Sequence

import pytest

from game.core import Simulation
from game.levels import LevelError, parse_level
from game.models import (
    CRATE_LIFETIME,
    CowPersonality,
    Direction,
    GameStatus,
    ItemKind,
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


def make_level(
    grid: Sequence[str] = OPEN,
    *,
    items: Sequence[tuple] = (),
    counts: Optional[dict] = None,
    farmer_facing: str = "east",
    cow_facings: Sequence[str] = ("north",),
    personalities: Optional[Sequence[str]] = None,
    obstacle_limit: int = 3,
    step_limit: int = 40,
):
    data = {
        "id": "items",
        "name": "道具测试",
        "grid": list(grid),
        "farmer_facing": farmer_facing,
        "cow_facings": list(cow_facings),
        "obstacle_limit": obstacle_limit,
        "step_limit": step_limit,
    }
    if personalities:
        data["cow_personalities"] = list(personalities)
    if items:
        data["placed_items"] = [{"kind": kind, "pos": list(pos)} for kind, pos in items]
    if counts:
        data["item_counts"] = counts
    return parse_level(data)


def grid_with(farmer=(1, 1), cow=(5, 5), walls=()):
    rows = [list(row) for row in OPEN]
    rows[farmer[0]][farmer[1]] = "F"
    rows[cow[0]][cow[1]] = "C"
    for r, c in walls:
        rows[r][c] = "#"
    return ["".join(row) for row in rows]


# ---------------------------------------------------------------------------
# Cow personalities
# ---------------------------------------------------------------------------
def test_stubborn_cow_turns_counter_clockwise():
    grid = grid_with(farmer=(5, 1), cow=(1, 1), walls=((0, 1),))
    level = make_level(grid, cow_facings=["north"], personalities=["stubborn"])
    sim = Simulation(level)
    tick = sim.step()
    assert tick.cows[0].moved is False
    assert tick.cows[0].end_facing is Direction.WEST


def test_normal_cow_turns_clockwise():
    grid = grid_with(farmer=(5, 1), cow=(1, 1), walls=())
    level = make_level(grid, cow_facings=["north"], personalities=["normal"])
    sim = Simulation(level)
    tick = sim.step()
    # north is blocked by the border, so it turns east
    assert tick.cows[0].end_facing is Direction.EAST


def test_greedy_cow_prefers_adjacent_apple():
    grid = grid_with(farmer=(5, 1), cow=(2, 2), walls=((2, 3),))
    level = make_level(
        grid,
        items=[("apple", (1, 2))],
        cow_facings=["east"],
        personalities=["greedy"],
    )
    sim = Simulation(level)
    tick = sim.step()
    assert tick.cows[0].moved is True
    assert sim.cows[0].pos == (1, 2)
    assert sim.cows[0].facing is Direction.NORTH
    assert (1, 2) not in sim.items


def test_normal_cow_does_not_chase_apples():
    grid = grid_with(farmer=(5, 1), cow=(2, 2), walls=((2, 3),))
    level = make_level(
        grid,
        items=[("apple", (1, 2))],
        cow_facings=["east"],
        personalities=["normal"],
    )
    sim = Simulation(level)
    sim.step()
    assert sim.cows[0].pos == (2, 2)
    assert (1, 2) in sim.items


def test_timid_cow_retreats_when_horn_blows():
    grid = grid_with(farmer=(1, 1), cow=(3, 3), walls=())
    level = make_level(
        grid,
        items=[("horn", (1, 2))],
        cow_facings=["east"],
        personalities=["timid"],
        step_limit=40,
    )
    sim = Simulation(level)
    sim.step()  # farmer steps on the horn
    assert sim.horn_events == 1
    cow = sim.cows[0]
    # the cow walked east, then the horn turned it around and it stepped back
    assert cow.facing is Direction.WEST
    assert cow.pos == (3, 3)


def test_horn_reverses_normal_cow_without_retreat():
    grid = grid_with(farmer=(1, 1), cow=(3, 3), walls=())
    level = make_level(
        grid,
        items=[("horn", (1, 2))],
        cow_facings=["east"],
        personalities=["normal"],
    )
    sim = Simulation(level)
    sim.step()
    assert sim.cows[0].facing is Direction.WEST
    assert sim.cows[0].pos == (3, 4)


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------
def test_apple_is_eaten_when_walked_over():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    level = make_level(grid, items=[("apple", (1, 2))])
    sim = Simulation(level)
    sim.step()
    assert sim.farmer.pos == (1, 2)
    assert (1, 2) not in sim.items


def test_mud_makes_actor_stuck_for_one_tick():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    level = make_level(grid, items=[("mud", (1, 2))])
    sim = Simulation(level)
    sim.step()
    assert sim.farmer.pos == (1, 2)
    sim.step()
    # stuck: turned clockwise (east -> south) and stayed put
    assert sim.farmer.pos == (1, 2)
    assert sim.farmer.facing is Direction.SOUTH
    sim.step()
    assert sim.farmer.pos == (2, 2)


def test_crate_blocks_then_crumbles():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    level = make_level(grid, items=[("crate", (1, 2))])
    sim = Simulation(level)
    assert sim.blocked((1, 2)) is True
    sim.step()
    assert sim.farmer.pos == (1, 1)
    assert sim.farmer.facing is Direction.SOUTH
    for _ in range(CRATE_LIFETIME - 1):
        sim.step()
    assert (1, 2) not in sim.items
    assert sim.blocked((1, 2)) is False


def test_signpost_turns_actor():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    level = parse_level(
        {
            "id": "sign",
            "name": "路标",
            "grid": grid,
            "farmer_facing": "east",
            "cow_facings": ["north"],
            "obstacle_limit": 1,
            "step_limit": 20,
            "placed_items": [{"kind": "signpost", "pos": [1, 2], "facing": "south"}],
        }
    )
    sim = Simulation(level)
    sim.step()
    assert sim.farmer.pos == (1, 2)
    assert sim.farmer.facing is Direction.SOUTH


def test_portal_teleports_actor():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    level = make_level(
        grid,
        items=[("portal", (1, 2)), ("portal", (4, 5))],
    )
    sim = Simulation(level)
    assert sim.items[(1, 2)].pair == (4, 5)
    sim.step()
    assert sim.farmer.pos == (4, 5)


def test_unpaired_portal_is_dropped_on_start():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    level = make_level(grid, counts={"portal": 2})
    sim = Simulation(level)
    assert sim.place_item(ItemKind.PORTAL, (1, 2)).ok
    assert sim.items[(1, 2)].pair is None
    sim.start()
    assert (1, 2) not in sim.items


def test_odd_number_of_placed_portals_is_rejected():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    with pytest.raises(LevelError):
        make_level(grid, items=[("portal", (1, 2))])


def test_item_placement_rules():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    level = make_level(grid, counts={"apple": 2})
    sim = Simulation(level)
    assert sim.item_left(ItemKind.APPLE) == 2
    assert sim.place_item(ItemKind.APPLE, (2, 2)).ok
    assert sim.place_item(ItemKind.APPLE, (2, 2)).ok is False
    assert sim.place_item(ItemKind.APPLE, (1, 1)).ok is False
    assert sim.place_item(ItemKind.APPLE, (0, 1)).ok is False
    assert sim.place_item(ItemKind.APPLE, (3, 3)).ok
    assert sim.item_left(ItemKind.APPLE) == 0
    assert sim.place_item(ItemKind.APPLE, (4, 4)).ok is False
    sim.start()
    assert sim.place_item(ItemKind.APPLE, (4, 4)).ok is False


def test_item_cannot_overlap_obstacle():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    level = make_level(grid, counts={"apple": 1})
    sim = Simulation(level)
    sim.place_obstacle((2, 2))
    assert sim.place_item(ItemKind.APPLE, (2, 2)).ok is False
    assert sim.can_place_obstacle((2, 2)).ok is False
    sim.place_item(ItemKind.APPLE, (3, 3))
    assert sim.place_obstacle((3, 3)).ok is False


def test_portal_pairing_in_placement():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    level = make_level(grid, counts={"portal": 2})
    sim = Simulation(level)
    assert sim.place_item(ItemKind.PORTAL, (2, 2)).ok
    assert sim.items[(2, 2)].pair is None
    assert sim.place_item(ItemKind.PORTAL, (4, 4)).ok
    assert sim.items[(2, 2)].pair == (4, 4)
    assert sim.items[(4, 4)].pair == (2, 2)
    sim.remove_item((4, 4))
    assert sim.items[(2, 2)].pair is None


def test_state_key_includes_items():
    grid = grid_with(farmer=(1, 1), cow=(5, 5))
    first = Simulation(make_level(grid, counts={"apple": 1}))
    second = Simulation(make_level(grid, counts={"apple": 1}))
    second.place_item(ItemKind.APPLE, (2, 2))
    assert first.state_key() != second.state_key()


def test_prediction_matches_reality_with_items():
    grid = grid_with(farmer=(1, 1), cow=(4, 4))
    level = make_level(grid, items=[("mud", (1, 2)), ("apple", (1, 3))])
    sim = Simulation(level)
    frames = sim.predict(4)
    positions = []
    for _ in range(4):
        sim.step()
        positions.append((sim.farmer.pos, sim.cows[0].pos, sim.items.keys()))
    for frame, (farmer_pos, cow_pos, items) in zip(frames, positions):
        assert frame.farmer_pos == farmer_pos
        assert frame.cow_positions[0] == cow_pos
    assert frames


def test_second_cow_is_simulated():
    grid = [
        "#######",
        "#F....#",
        "#.....#",
        "#....C#",
        "#C....#",
        "#.....#",
        "#######",
    ]
    level = make_level(
        grid,
        cow_facings=["east", "north"],
        personalities=["normal", "stubborn"],
    )
    sim = Simulation(level)
    assert len(sim.cows) == 2
    tick = sim.step()
    assert len(tick.cows) == 2
    assert sim.cows[1].personality is CowPersonality.STUBBORN


def test_catching_either_cow_wins():
    grid = [
        "#######",
        "#FC..#C",
        "#.....#",
        "#.....#",
        "#.....#",
        "#.....#",
        "#######",
    ]
    level = make_level(grid, cow_facings=["north", "east"])
    sim = Simulation(level)
    tick = sim.step()
    assert tick.caught is True
    assert sim.status is GameStatus.WON
