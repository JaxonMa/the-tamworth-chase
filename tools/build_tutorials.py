"""Build the tutorial chapter JSON files and verify every lesson is winnable.

Usage::

    .venv/bin/python -m tools.build_tutorials
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from game.levels import parse_level
from game.models import GameStatus
from tools.search import search
from tools.solve import solve, run

ROOT = Path(__file__).resolve().parent.parent


def lesson(
    lesson_id: str,
    name: str,
    brief: str,
    goal: str,
    practice: str,
    grid: Sequence[str],
    *,
    farmer_facing: str = "east",
    cow_facings: Sequence[str] = ("east",),
    obstacle_limit: int = 1,
    tips: Sequence[Dict[str, str]] = (),
    extra: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    level = {
        "id": lesson_id,
        "name": name,
        "grid": list(grid),
        "farmer_facing": farmer_facing,
        "cow_facings": list(cow_facings),
        "obstacle_limit": obstacle_limit,
        "step_limit": 60,
    }
    if extra:
        level.update(extra)
    return {
        "id": lesson_id,
        "name": name,
        "brief": brief,
        "goal": goal,
        "practice": practice,
        "tips": list(tips),
        "level": level,
    }


# ---------------------------------------------------------------------------
# 基础教程
# ---------------------------------------------------------------------------
B1_GRID = [
    "##########",
    "#......#.#",
    "#......#.#",
    "#.......C#",
    "#........#",
    "#........#",
    "#....F...#",
    "#........#",
    "#........#",
    "##########",
]
B2_GRID = [
    "##########",
    "#........#",
    "#........#",
    "#....C#..#",
    "#........#",
    "#.#......#",
    "#.......F#",
    "#........#",
    "#........#",
    "##########",
]
B4_GRID = [
    "##########",
    "#F.......#",
    "#.####...#",
    "#....#...#",
    "#....#..C#",
    "#....#...#",
    "#....#####",
    "#........#",
    "#........#",
    "##########",
]
B5_GRID = [
    "##########",
    "#F....#..#",
    "#.....#..#",
    "#..####..#",
    "#.....#..#",
    "#..C..#..#",
    "#.....#..#",
    "#........#",
    "#........#",
    "##########",
]
B6_GRID = [
    "##########",
    "#...F.##.#",
    "#.....#..#",
    "#........#",
    "#........#",
    "#..####..#",
    "#.######.#",
    "#.#.##.#.#",
    "#C..##...#",
    "##########",
]

BASICS = {
    "version": 1,
    "chapter": "basics",
    "title": "基础教程",
    "subtitle": "从认识牧场开始",
    "intro": "六节短课，从同步移动到时间闭环。每节课只讲一个新机制，随时可以跳过。",
    "badge": "基础",
    "accent": "leaf",
    "lessons": [
        lesson(
            "basics_01",
            "一起出发",
            "先看看农夫和牛是怎么一起走路的。",
            "观察同步移动，让他们自然相遇。",
            "点击「开始游戏」，看两位主角一起动起来。",
            B1_GRID,
            farmer_facing="east",
            cow_facings=["south"],
            obstacle_limit=0,
            tips=[
                {"trigger": "start", "text": "农夫和牛每回合同时移动：前方能走就前进，否则顺时针转 90°。"},
                {"trigger": "run", "text": "现在点「开始游戏」，看他们一起动。"},
                {"trigger": "step", "text": "每一回合两人同时走一步，注意看他们的朝向。"},
                {"trigger": "win", "text": "碰到一起就算抓住！这就是最基础的追逐。"},
            ],
        ),
        lesson(
            "basics_02",
            "第一捆干草",
            "把干草垛放在牛的正前方，逼它转弯。",
            "用一捆干草改变牛的路线。",
            "点击草地放下干草垛，然后开始游戏。",
            B2_GRID,
            farmer_facing="east",
            cow_facings=["north"],
            obstacle_limit=1,
            extra={"require_obstacle": 1},
            tips=[
                {"trigger": "start", "text": "这次只靠等待抓不到。点击草地，把干草垛放在牛的正前方。"},
                {"trigger": "place", "text": "干草垛挡住了牛，它只好向右转身。"},
                {"trigger": "run", "text": "现在开始游戏，看看路线会怎么改变。"},
                {"trigger": "win", "text": "障碍改变了路线，这就是这个游戏的核心。"},
            ],
        ),
        lesson(
            "basics_03",
            "收回来再想想",
            "布局阶段可以反复调整，点击干草垛就能收回。",
            "学会撤销：先放一捆干草，再收回来。",
            "放下一捆干草，然后点击它把它收回来。",
            B2_GRID,
            farmer_facing="east",
            cow_facings=["north"],
            obstacle_limit=1,
            extra={"require_undo": True},
            tips=[
                {"trigger": "start", "text": "先放一捆干草，再点同一格把它收回来。"},
                {"trigger": "place", "text": "放好了。现在点击干草垛，或按「撤销一步」。"},
                {"trigger": "remove", "text": "收回来了！布局阶段可以反复调整，直到开始为止。"},
                {"trigger": "run", "text": "重新放好干草垛，然后开始吧。"},
                {"trigger": "win", "text": "调整路线就是解谜的过程。"},
            ],
        ),
        lesson(
            "basics_04",
            "看清三步",
            "虚线是接下来三步的预测，布局会实时改变它。",
            "利用前三步预测完成关卡。",
            "先观察预测虚线，再放下两块干草。",
            B4_GRID,
            farmer_facing="east",
            cow_facings=["north"],
            obstacle_limit=2,
            tips=[
                {"trigger": "start", "text": "虚线表示接下来 3 步的预测，先看看两位主角会走到哪里。"},
                {"trigger": "place", "text": "预测会随布局实时变化，换个位置再看看。"},
                {"trigger": "run", "text": "开始之后，每走一步预测都会重新计算。"},
                {"trigger": "win", "text": "善用预测，可以少走很多弯路。"},
            ],
        ),
        lesson(
            "basics_05",
            "时间闭环",
            "如果状态完全重复，时间就会绕成一个圈。",
            "先见识一次时间闭环，再打破它。",
            "不妨先不加干草，直接开始看看。",
            B5_GRID,
            farmer_facing="east",
            cow_facings=["north"],
            obstacle_limit=1,
            tips=[
                {"trigger": "start", "text": "如果两位主角回到完全相同的状态，时间就会绕成闭环。"},
                {"trigger": "run", "text": "先不加干草垛，直接开始看看会发生什么。"},
                {"trigger": "step", "text": "他们在重复同一段路线……"},
                {"trigger": "fail", "text": "时间闭环了。重复的状态意味着永远抓不到，必须改变路线。"},
                {"trigger": "place", "text": "加一捆干草，打破这个循环。"},
                {"trigger": "win", "text": "打破循环，就能抓到牛。"},
            ],
        ),
        lesson(
            "basics_06",
            "抓牛小考",
            "两块干草，一头牛，一节课学到的都用上。",
            "用两捆干草抓住牛。",
            "结合预测与转角，把两块干草放在关键位置。",
            B6_GRID,
            farmer_facing="east",
            cow_facings=["north"],
            obstacle_limit=2,
            extra={"require_obstacle": 2},
            tips=[
                {"trigger": "start", "text": "最后来一次小测验：两捆干草，抓住牛。"},
                {"trigger": "place", "text": "位置很重要，先看看预测虚线。"},
                {"trigger": "win", "text": "基础教程完成！主线关卡里还有更多牧场等着你。"},
            ],
        ),
    ],
}


def _find_solution(level):
    """Use the item-aware search when the lesson ships tools, else the solver."""
    if level.item_counts:
        return search(level, max_tries=400000)
    return solve(level, level.obstacle_limit, verbose=False)



# ---------------------------------------------------------------------------
# 进阶教程
# ---------------------------------------------------------------------------
A1_GRID = [
    "##########",
    "#F.......#",
    "#........#",
    "#..###...#",
    "#........#",
    "#.......C#",
    "#........#",
    "#..C.....#",
    "#........#",
    "##########",
]
A2_GRID = [
    "##########",
    "#F.......#",
    "#....#...#",
    "#........#",
    "#....#..D#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "##########",
]
A3_GRID = [
    "##########",
    "#........#",
    "#.#......#",
    "#..###...#",
    "#........#",
    "#F.......#",
    "#........#",
    "#....G...#",
    "#...#....#",
    "##########",
]
A4_GRID = [
    "##########",
    "#......F.#",
    "#...#....#",
    "#........#",
    "#........#",
    "#.....S..#",
    "#.#......#",
    "#........#",
    "#........#",
    "##########",
]
A5_GRID = [
    "##########",
    "#...F.##.#",
    "#.....#..#",
    "#........#",
    "#........#",
    "#..####..#",
    "#.######.#",
    "#.#.##.#.#",
    "#C..##...#",
    "##########",
]

ADVANCED = {
    "version": 1,
    "chapter": "advanced",
    "title": "进阶教程",
    "subtitle": "新的牛与新的道具",
    "intro": "学会和性格各异的牛打交道，并用苹果、喇叭、泥地和路标改变追逐的节奏。",
    "badge": "进阶",
    "accent": "clay",
    "lessons": [
        lesson(
            "advanced_01",
            "牧场来了第二头牛",
            "抓住任意一头牛就算赢。",
            "同时盯着两头牛的路线，抓住其中一头。",
            "用两捆干草制造一次相遇。",
            A1_GRID,
            farmer_facing="east",
            cow_facings=["north", "west"],
            obstacle_limit=2,
            tips=[
                {"trigger": "start", "text": "牧场上有两头牛，抓住任意一头就算胜利。"},
                {"trigger": "place", "text": "两捆干草可以分别影响两条路线。"},
                {"trigger": "run", "text": "注意两束预测虚线，找到最早的交点。"},
                {"trigger": "win", "text": "面对多头牛时，先解决离农夫最近的那一头。"},
            ],
        ),
        lesson(
            "advanced_02",
            "倔脾气的牛",
            "倔牛被挡住时会逆时针转身。",
            "利用倔牛与众不同的转身方向。",
            "先挡住倔牛，再让农夫绕过去。",
            A2_GRID,
            farmer_facing="east",
            cow_facings=["north"],
            obstacle_limit=2,
            tips=[
                {"trigger": "start", "text": "这头牛被挡住时会逆时针转身，和普通牛正好相反。"},
                {"trigger": "place", "text": "挡在它前面，它会转向左边。"},
                {"trigger": "run", "text": "倔牛会往反方向拐，路线会比你想的更绕。"},
                {"trigger": "win", "text": "记住它的转向，下一次就能提前预判。"},
            ],
        ),
        lesson(
            "advanced_03",
            "贪吃的牛",
            "贪吃牛被挡住时会优先走向旁边的苹果。",
            "用一颗苹果把贪吃牛引到农夫面前。",
            "选择苹果工具，点在牛身边；再补一捆干草。",
            A3_GRID,
            farmer_facing="south",
            cow_facings=["north"],
            obstacle_limit=2,
            extra={"item_counts": {"apple": 1}},
            tips=[
                {"trigger": "start", "text": "贪吃牛被挡住时，会优先走向旁边的苹果。"},
                {"trigger": "place", "text": "把苹果放在它转向后能碰到的地方。"},
                {"trigger": "run", "text": "苹果会把它引向农夫，注意时机。"},
                {"trigger": "win", "text": "用苹果当诱饵，比硬挡更有效。"},
            ],
        ),
        lesson(
            "advanced_04",
            "胆小的牛",
            "喇叭响起时所有牛掉头，胆小牛还会后退一步。",
            "把喇叭放在农夫会经过的位置，吓退胆小牛。",
            "选择喇叭工具，放在农夫的必经之路上。",
            A4_GRID,
            farmer_facing="north",
            cow_facings=["west"],
            obstacle_limit=1,
            extra={"item_counts": {"horn": 1}},
            tips=[
                {"trigger": "start", "text": "喇叭被踩到时会响：所有牛掉头，胆小牛还会后退一步。"},
                {"trigger": "place", "text": "把喇叭放在农夫路上，等他自己去踩。"},
                {"trigger": "run", "text": "喇叭只响一次，时机比位置更重要。"},
                {"trigger": "win", "text": "胆小牛的后退常常会把它送到农夫身边。"},
            ],
        ),
        lesson(
            "advanced_05",
            "泥地与路标",
            "泥地会让人陷住一回合，路标会强行改变朝向。",
            "利用已经摆好的泥地和路标完成追逐。",
            "观察机关的位置，用两捆干草补上最后一段路。",
            A5_GRID,
            farmer_facing="east",
            cow_facings=["north"],
            obstacle_limit=2,
            extra={
                "placed_items": [
                    {"kind": "mud", "pos": [4, 2]},
                    {"kind": "signpost", "pos": [2, 4], "facing": "south"},
                ]
            },
            tips=[
                {"trigger": "start", "text": "泥地会让人陷住一回合，路标会强行改变朝向。"},
                {"trigger": "place", "text": "机关已经摆好，你只需要补上干草垛。"},
                {"trigger": "run", "text": "看看谁踩进泥地，谁又被路标带走。"},
                {"trigger": "win", "text": "道具组合起来，能把整条路线重新编排。"},
            ],
        ),
    ],
}


def verify(chapter: Dict[str, object], strict: bool = True) -> Dict[str, object]:
    solutions: Dict[str, object] = {}
    for item in chapter["lessons"]:  # type: ignore[index]
        payload = item["level"]
        level = parse_level({**payload, "step_limit": 100})
        limit = int(payload.get("obstacle_limit", 0))
        zero_status, zero_steps = run(level, ())
        best = None
        for cap in range(0, limit + 1):
            if level.item_counts:
                probe = parse_level({**payload, "obstacle_limit": cap, "step_limit": 100})
                result = search(probe, cap, max_tries=400000)
            else:
                result = solve(level, cap, verbose=False)
            if result.solved:
                best = result
                break
        if best is None:
            raise SystemExit(f"{item['id']} is not solvable with {limit} obstacles")
        minimum = best.steps
        payload["step_limit"] = minimum + 20
        if int(payload.get("obstacle_limit", 0)) == 0:
            payload["step_limit"] = max(12, minimum + 10)
        payload["s_threshold"] = max(1, minimum)
        payload["a_threshold"] = minimum + 4
        payload["b_threshold"] = minimum + 10
        solutions[item["id"]] = {
            "obstacles": [list(pos) for pos in best.obstacles],
            "items": [[kind.value, list(pos)] for kind, pos in getattr(best, "items", ())],
            "steps": minimum,
        }
        print(
            f"  {item['id']} {item['name']}: min={minimum} bales={len(best.obstacles)} "
            f"zero={zero_status.value}@{zero_steps} limit={payload['step_limit']}"
        )
        if strict and zero_status is GameStatus.WON and limit > 0:
            print("    note: this lesson can be won without placing anything (fine for demos)")
    return solutions


def main() -> int:
    print("verify basics chapter")
    solutions = verify(BASICS)
    path = ROOT / "tutorials" / "basics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(BASICS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    solution_path = ROOT / "tests" / "tutorial_solutions.json"
    existing = {}
    if solution_path.exists():
        try:
            existing = json.loads(solution_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing["basics"] = solutions
    solution_path.write_text(json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("verify advanced chapter")
    advanced_solutions = verify(ADVANCED)
    advanced_path = ROOT / "tutorials" / "advanced.json"
    advanced_path.write_text(json.dumps(ADVANCED, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    existing["advanced"] = advanced_solutions
    solution_path.write_text(json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path}, {advanced_path} and {solution_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
