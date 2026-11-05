"""Build ``levels/levels.json`` from curated layouts.

The layouts in this file were selected with the exhaustive solver: each one is
checked to be solvable with its obstacle budget, and the rating thresholds are
derived from the shortest discovered solution.  Run with::

    .venv/bin/python -m tools.build_levels
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from game.levels import parse_level
from game.models import GameStatus
from tools.solve import solve, run

LevelSpec = Dict[str, object]

SPECS: List[LevelSpec] = [
    {
        "id": "level_01",
        "name": "晨露草坪",
        "description": "新的一天从一片开阔的草地开始。",
        "hint": "把障碍放在牛的正前方，它会向右转身。",
        "tags": ["入门"],
        "obstacle_limit": 1,
        "farmer_facing": "north",
        "cow_facings": ["north"],
        "grid": [
            "##########",
            "#........#",
            "#........#",
            "#.F......#",
            "#........#",
            "#........#",
            "#.....##C#",
            "#.TT.###.#",
            "#.TT..##.#",
            "##########",
        ],
    },
    {
        "id": "level_02",
        "name": "牧场小径",
        "description": "狭长的小径上，谁先拐弯？",
        "hint": "挡住农夫，让他提前转向也是好办法。",
        "tags": ["入门"],
        "obstacle_limit": 1,
        "farmer_facing": "south",
        "cow_facings": ["east"],
        "grid": [
            "##########",
            "#.......C#",
            "#........#",
            "#........#",
            "#........#",
            "#........#",
            "#....F...#",
            "#........#",
            "#....HHHH#",
            "##########",
        ],
    },
    {
        "id": "level_03",
        "name": "老屋后院",
        "description": "屋后的岔路不少，别让他们绕远。",
        "hint": "先预测三步，再决定石头放在哪里。",
        "tags": ["入门", "转角"],
        "obstacle_limit": 2,
        "farmer_facing": "south",
        "cow_facings": ["north"],
        "grid": [
            "##########",
            "#........#",
            "#.....C..#",
            "#..TT.####",
            "#..TT.#.##",
            "#..TT.#.##",
            "#..#######",
            "#..##.#..#",
            "#F.......#",
            "##########",
        ],
    },
    {
        "id": "level_04",
        "name": "石堆迷宫",
        "description": "两块石头，能改变两段路线。",
        "hint": "一块挡住牛，一块留给农夫。",
        "tags": ["节奏"],
        "obstacle_limit": 2,
        "farmer_facing": "south",
        "cow_facings": ["west"],
        "grid": [
            "##########",
            "#....F...#",
            "#.#####..#",
            "###..##..#",
            "##.......#",
            "##T.C.#..#",
            "##T...#..#",
            "##TTTT#..#",
            "##TTTT#..#",
            "##########",
        ],
    },
    {
        "id": "level_05",
        "name": "对称牧场",
        "description": "左右对称的围栏，藏着不对称的时机。",
        "hint": "注意两位主角的朝向，先让谁转身？",
        "tags": ["对称", "节奏"],
        "obstacle_limit": 2,
        "farmer_facing": "west",
        "cow_facings": ["north"],
        "grid": [
            "##########",
            "#..HHHH..#",
            "#....#...#",
            "#........#",
            "#..~~~~..#",
            "#.C.##...#",
            "#.#....#.#",
            "#........#",
            "#...TTF..#",
            "##########",
        ],
    },
    {
        "id": "level_06",
        "name": "蜿蜒沟渠",
        "description": "沟渠之间，只差几步的时间。",
        "hint": "有时需要让牛多绕一圈。",
        "tags": ["长路"],
        "obstacle_limit": 3,
        "farmer_facing": "south",
        "cow_facings": ["west"],
        "grid": [
            "##########",
            "#........#",
            "#...C....#",
            "#....HHHH#",
            "##HH..HH##",
            "#........#",
            "#...TTTT.#",
            "#........#",
            "#...TTF..#",
            "##########",
        ],
    },
    {
        "id": "level_07",
        "name": "双屋之间",
        "description": "两间小屋，一条窄缝。",
        "hint": "窄缝是唯一的近路，也可能是陷阱。",
        "tags": ["窄道"],
        "obstacle_limit": 3,
        "farmer_facing": "north",
        "cow_facings": ["west"],
        "grid": [
            "##########",
            "#.#.HHH..#",
            "#.#...#..#",
            "#F#..C#..#",
            "#.#...#..#",
            "#.HHH.#..#",
            "#........#",
            "#........#",
            "#........#",
            "##########",
        ],
    },
    {
        "id": "level_08",
        "name": "苔藓高地",
        "description": "三块苔石，三条岔路。",
        "hint": "把三块石头用在关键的两个转角上。",
        "tags": ["三石"],
        "obstacle_limit": 3,
        "farmer_facing": "north",
        "cow_facings": ["east"],
        "grid": [
            "##########",
            "#........#",
            "#.#....#.#",
            "#...TT...#",
            "##.CTT..##",
            "#........#",
            "#.#....#.#",
            "#.HHHHHH.#",
            "#..#..#F.#",
            "##########",
        ],
    },
    {
        "id": "level_09",
        "name": "荆棘窄门",
        "description": "门只有一扇，时机只有一次。",
        "hint": "先看牛会绕到哪里，再决定农夫的路线。",
        "tags": ["精算"],
        "obstacle_limit": 3,
        "farmer_facing": "north",
        "cow_facings": ["north"],
        "grid": [
            "##########",
            "##.T.#.C.#",
            "##.T.#...#",
            "#.T.#....#",
            "#.#.#....#",
            "#..#..#.##",
            "#F.#.....#",
            "#........#",
            "#.##..T..#",
            "##########",
        ],
    },
    {
        "id": "level_10",
        "name": "最后的围栏",
        "description": "最后的牧场，慢慢来。",
        "hint": "三步预测看不出结果时，试着先放两块石头。",
        "tags": ["终章", "精算"],
        "obstacle_limit": 3,
        "farmer_facing": "east",
        "cow_facings": ["north"],
        "grid": [
            "##########",
            "#........#",
            "#......#.#",
            "#......#.#",
            "#..T..#..#",
            "#F.....###",
            "#........#",
            "#....##..#",
            "#....T..C#",
            "##########",
        ],
    },
]


def decorate(rows: Sequence[str]) -> Tuple[List[str], int]:
    """Grids already carry their decorative tiles; count them for the report."""
    count = sum(1 for row in rows for char in row if char in "TH~")
    return list(rows), count


def build(verbose: bool = True) -> Dict[str, object]:
    levels: List[Dict[str, object]] = []
    for spec in SPECS:
        payload = dict(spec)
        grid, converted = decorate(payload["grid"])  # type: ignore[arg-type]
        payload["grid"] = grid
        probe = parse_level({**payload, "step_limit": 200, "s_threshold": 1, "a_threshold": 2, "b_threshold": 3})
        result = solve(probe, int(payload["obstacle_limit"]), verbose=False)
        if not result.solved:
            raise SystemExit(f"level {payload['id']} is not solvable: {result}")
        minimum = result.steps
        limit = minimum + 22
        payload.update(
            {
                "step_limit": limit,
                "s_threshold": minimum + 2,
                "a_threshold": minimum + 7,
                "b_threshold": minimum + 14,
            }
        )
        if verbose:
            print(
                f"{payload['id']} {payload['name']}: min={minimum} obstacles={len(result.obstacles)} "
                f"decorated={converted} limit={limit}"
            )
            print("\n".join("   " + row for row in grid))
        levels.append(payload)
    return {"version": 1, "game": "The Tamworth Two", "levels": levels}


def main() -> int:
    bundle = build()
    path = Path(__file__).resolve().parent.parent / "levels" / "levels.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} with {len(bundle['levels'])} levels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
