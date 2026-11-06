"""Author the tutorial chapter data and write the JSON files.

The tutorial is intentionally separate from the campaign.  This script keeps the
five basic, three advanced and three editor lessons together so the content can
be reviewed in one place, then writes ``tutorials/*.json``.

Usage::

    .venv/bin/python tools/build_tutorials.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.tutorial import TutorialCatalog  # noqa: E402

STARTER = [
    "##########",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#........#",
    "#F......C#",
    "##########",
]


def lesson(
    lesson_id: str,
    name: str,
    brief: str,
    goal: str,
    practice: str,
    tips: List[Dict[str, str]],
    level: Dict[str, Any],
    *,
    editor_task: Dict[str, Any] | None = None,
    starter_grid: List[str] | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": lesson_id,
        "name": name,
        "brief": brief,
        "goal": goal,
        "practice": practice,
        "tips": tips,
        "level": level,
    }
    if editor_task:
        payload["editor_task"] = editor_task
    if starter_grid:
        payload["starter_grid"] = starter_grid
    return payload


def level(
    lesson_id: str,
    name: str,
    grid: List[str],
    farmer_facing: str,
    cow_facings: List[str],
    *,
    max_turns: int = 12,
    initial_obstacles: int = 0,
    prediction_steps: int = 0,
    win_condition: str = "catch",
    pen_cells: List[List[int]] | None = None,
    cows_block_each_other: bool = False,
    s_threshold: int = 4,
    a_threshold: int = 7,
    b_threshold: int = 10,
    **extra: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": lesson_id,
        "name": name,
        "grid": grid,
        "farmer_facing": farmer_facing,
        "cow_facings": cow_facings,
        "max_turns": max_turns,
        "initial_obstacles": initial_obstacles,
        "prediction_steps": prediction_steps,
        "win_condition": win_condition,
        "pen_cells": pen_cells or [],
        "cows_block_each_other": cows_block_each_other,
        "s_threshold": s_threshold,
        "a_threshold": a_threshold,
        "b_threshold": b_threshold,
    }
    payload.update(extra)
    return payload


BASICS = {
    "title": "基础教程",
    "subtitle": "从走一步开始，学会追逐",
    "intro": "五节短课，每节只介绍一件事。可以跳过任何一节，也可以随时重玩。",
    "badge": "基础",
    "accent": "leaf",
    "lessons": [
        lesson(
            "basics_01",
            "第一步",
            "用方向键移动农夫，牛会在你之后走一步。",
            "抓住牛",
            "用方向键或 WASD 移动农夫，至少走一步。",
            [
                {"trigger": "start", "text": "用方向键或 WASD 移动农夫。你走一步，牛才会走一步。"},
                {"trigger": "move", "text": "注意：农夫先动，牛后动。牛撞到围栏时会顺时针转身。"},
                {"trigger": "win", "text": "和牛站在同一格就抓住了。基础教程开始！"},
            ],
            level(
                "basics_01",
                "第一步",
                [
                    "#######",
                    "#....C#",
                    "#.....#",
                    "#.....#",
                    "#.....#",
                    "#F....#",
                    "#######",
                ],
                "east",
                ["east"],
                max_turns=12,
                s_threshold=5,
                a_threshold=8,
                b_threshold=10,
            ),
        ),
        lesson(
            "basics_02",
            "转过墙角",
            "在牛的正前方放下干草垛，逼它右转。",
            "用一捆干草改变牛的路线，抓住它。",
            "先在牛的正前方放一捆干草，再开始。",
            [
                {"trigger": "start", "text": "把干草垛放在牛的正前方，它会原地右转。"},
                {"trigger": "place", "text": "放好了。干草垛会挡住牛，让它改变方向。"},
                {"trigger": "run", "text": "现在开始追逐，看看它拐向哪里。"},
                {"trigger": "win", "text": "墙角加干草，就能把牛的路线折回来。"},
            ],
            level(
                "basics_02",
                "转过墙角",
                [
                    "#######",
                    "#.....#",
                    "#..#C.#",
                    "#..#..#",
                    "#..#..#",
                    "#F....#",
                    "#######",
                ],
                "east",
                ["east"],
                max_turns=10,
                initial_obstacles=1,
                require_obstacle=1,
                s_threshold=4,
                a_threshold=6,
                b_threshold=8,
            ),
        ),
        lesson(
            "basics_03",
            "等一等",
            "按空格让农夫等待，牛会自己走过来。",
            "用等待抓住牛。",
            "按空格等待至少一回合，再抓住牛。",
            [
                {"trigger": "start", "text": "按空格可以让农夫原地等待，牛仍然会走一步。"},
                {"trigger": "wait", "text": "牛正在靠近。继续等，让它自己走进来。"},
                {"trigger": "win", "text": "等待也是一种策略：不用追，让牛来找你。"},
            ],
            level(
                "basics_03",
                "等一等",
                [
                    "#######",
                    "#.....#",
                    "#######",
                    "#F...C#",
                    "#######",
                    "#.....#",
                    "#######",
                ],
                "east",
                ["west"],
                max_turns=8,
                require_wait=True,
                s_threshold=4,
                a_threshold=6,
                b_threshold=7,
            ),
        ),
        lesson(
            "basics_04",
            "撤销一步",
            "放错了？按 U 收回干草垛，再重新想。",
            "先放下一捆干草并收回，再完成追逐。",
            "放一捆干草，按 U 收回，然后再放好开始。",
            [
                {"trigger": "start", "text": "放一捆干草，再按 U 把它收回。布局阶段可以反复调整。"},
                {"trigger": "place", "text": "放好了。现在按 U，或点击干草垛把它收回。"},
                {"trigger": "undo", "text": "收回来了。撤销之后可以重新放，直到你满意为止。"},
                {"trigger": "run", "text": "再放一捆干草，然后开始追逐。"},
                {"trigger": "win", "text": "会撤销，就能大胆试错。"},
            ],
            level(
                "basics_04",
                "撤销一步",
                [
                    "#######",
                    "#.....#",
                    "#..#C.#",
                    "#..#..#",
                    "#..#..#",
                    "#F....#",
                    "#######",
                ],
                "east",
                ["east"],
                max_turns=10,
                initial_obstacles=1,
                require_obstacle=1,
                require_undo=True,
                s_threshold=4,
                a_threshold=6,
                b_threshold=8,
            ),
        ),
        lesson(
            "basics_05",
            "看清前路",
            "按 P 打开路径预测，先看牛会走到哪里。",
            "打开 6 回合预测，规划路线抓住牛。",
            "按 P 打开预测，再开始追逐。",
            [
                {"trigger": "start", "text": "这一关的预测能看到 6 回合。按 P 打开它。"},
                {"trigger": "predict", "text": "半透明脚印就是牛接下来会走的路。先观察，再移动。"},
                {"trigger": "run", "text": "现在开始追逐。每走一步，脚印都会重新计算。"},
                {"trigger": "win", "text": "先看路，再走路，就能少绕很多圈。"},
            ],
            level(
                "basics_05",
                "看清前路",
                [
                    "#######",
                    "#F....#",
                    "#..#..#",
                    "#..#C.#",
                    "#..#..#",
                    "#.....#",
                    "#######",
                ],
                "east",
                ["east"],
                max_turns=15,
                prediction_steps=6,
                require_prediction=True,
                s_threshold=7,
                a_threshold=10,
                b_threshold=12,
            ),
        ),
    ],
}


ADVANCED = {
    "title": "进阶教程",
    "subtitle": "多头牛、围栏和循环提示",
    "intro": "三节进阶课：同时应付多头牛，把牛送进围栏，认识不会判负的循环提示。",
    "badge": "进阶",
    "accent": "sky",
    "lessons": [
        lesson(
            "advanced_01",
            "两头牛",
            "两头牛按固定顺序移动；抓住任意一头即可。",
            "抓住任意一头牛。",
            "观察两头牛的路线，抓住离你更近的一头。",
            [
                {"trigger": "start", "text": "场上有两头牛，它们按从左到右的固定顺序各走一步。"},
                {"trigger": "move", "text": "抓任意一头都算赢。先盯住离你最近的那一头。"},
                {"trigger": "win", "text": "多头牛时，选择一个目标，别在两条路线之间摇摆。"},
            ],
            level(
                "advanced_01",
                "两头牛",
                [
                    "##########",
                    "#........#",
                    "#.#....#.#",
                    "#...TT...#",
                    "##.CTT..##",
                    "#........#",
                    "#.#...C#.#",
                    "#.HHHHHH.#",
                    "#..#..#F.#",
                    "##########",
                ],
                "north",
                ["east", "west"],
                max_turns=20,
                prediction_steps=5,
                cows_block_each_other=True,
                s_threshold=7,
                a_threshold=10,
                b_threshold=13,
            ),
        ),
        lesson(
            "advanced_02",
            "围栏",
            "把所有牛赶进金色围栏格就获胜。",
            "让牛走进围栏格。",
            "等牛自己走进金色围栏格。",
            [
                {"trigger": "start", "text": "这一关的目标不是抓住牛，而是让牛走进金色围栏格。"},
                {"trigger": "wait", "text": "农夫无法进入围栏区。耐心等牛沿自己的路线走进来。"},
                {"trigger": "win", "text": "所有牛都进栏就获胜。围栏关里，牛可以不用被抓住。"},
            ],
            level(
                "advanced_02",
                "围栏",
                [
                    "########",
                    "#......#",
                    "#.####.#",
                    "#.#C.#.#",
                    "#.#..#.#",
                    "#.####.#",
                    "#F.....#",
                    "########",
                ],
                "east",
                ["east"],
                max_turns=8,
                prediction_steps=3,
                win_condition="pen",
                pen_cells=[[3, 4]],
                s_threshold=1,
                a_threshold=3,
                b_threshold=5,
            ),
        ),
        lesson(
            "advanced_03",
            "循环提示",
            "牛的状态重复时会出现提示，但不会判负。",
            "观察一次循环提示。",
            "连续按空格等待，直到循环提示出现。",
            [
                {"trigger": "start", "text": "连续按空格等待。牛的位置和朝向重复时，会看到循环提示。"},
                {"trigger": "wait", "text": "继续等。循环提示只是一条提醒，不是失败。"},
                {"trigger": "loop", "text": "看，牛进入了循环。你可以继续行动，或者回到布置阶段换一条路。"},
            ],
            level(
                "advanced_03",
                "循环提示",
                [
                    "#######",
                    "#.....#",
                    "#.###.#",
                    "#.#C#.#",
                    "#.###.#",
                    "#F....#",
                    "#######",
                ],
                "east",
                ["east"],
                max_turns=20,
                complete_on_loop=True,
                s_threshold=4,
                a_threshold=8,
                b_threshold=12,
            ),
        ),
    ],
}


EDITOR = {
    "title": "编辑器教程",
    "subtitle": "自己造一片牧场",
    "intro": "三节编辑器课：画地形、设置规则、导出与导入。",
    "badge": "编辑器",
    "accent": "clay",
    "lessons": [
        lesson(
            "editor_01",
            "画一面栅栏",
            "选择栅栏工具，在草地上画出三格。",
            "画出至少三格栅栏。",
            "选择「栅栏」，在草地上点击三次。",
            [
                {"trigger": "start", "text": "在右侧选择「栅栏」，然后在草地上点击三格。右键可以擦除。"},
                {"trigger": "place", "text": "继续点击。画好的栅栏会立刻出现在棋盘上。"},
            ],
            level(
                "editor_01",
                "画一面栅栏",
                STARTER,
                "east",
                ["north"],
                max_turns=40,
                initial_obstacles=3,
                prediction_steps=5,
                s_threshold=10,
                a_threshold=18,
                b_threshold=26,
            ),
            editor_task={"type": "paint_wall", "count": 3},
            starter_grid=STARTER,
        ),
        lesson(
            "editor_02",
            "设置新的规则",
            "把胜利条件改成围栏，再画出两格围栏格。",
            "设置围栏胜利，并画出两格围栏格。",
            "点「胜利：抓住」切换成围栏，再用围栏格工具画两格。",
            [
                {"trigger": "start", "text": "先点「胜利：抓住」切换成围栏，再用「围栏格」画两格。"},
                {"trigger": "place", "text": "金色格子就是围栏。围栏关里，牛要走到这里才算赢。"},
            ],
            level(
                "editor_02",
                "设置新的规则",
                STARTER,
                "east",
                ["north"],
                max_turns=40,
                initial_obstacles=3,
                prediction_steps=5,
                s_threshold=10,
                a_threshold=18,
                b_threshold=26,
            ),
            editor_task={"type": "set_rules", "pen_cells": 2},
            starter_grid=STARTER,
        ),
        lesson(
            "editor_03",
            "导出与导入",
            "把关卡保存成 JSON，再读回来。",
            "导出一次并导入一次。",
            "先点「导出关卡」，再点「导入关卡」选择刚才的文件。",
            [
                {"trigger": "start", "text": "「导出关卡」会把当前设计写进 custom_levels/，格式是普通 JSON。"},
                {"trigger": "place", "text": "导出之后点「导入关卡」，选择刚生成的文件就能读回来。"},
            ],
            level(
                "editor_03",
                "导出与导入",
                STARTER,
                "east",
                ["north"],
                max_turns=40,
                initial_obstacles=3,
                prediction_steps=5,
                s_threshold=10,
                a_threshold=18,
                b_threshold=26,
            ),
            editor_task={"type": "export_import"},
            starter_grid=STARTER,
        ),
    ],
}


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    for name, chapter in (("basics", BASICS), ("advanced", ADVANCED), ("editor", EDITOR)):
        path = root / "tutorials" / f"{name}.json"
        path.write_text(json.dumps(chapter, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(root)} ({len(chapter['lessons'])} lessons)")
    # A quick syntax / schema check through the real loader.
    catalog = TutorialCatalog.load()
    for chapter in catalog.all():
        for item in chapter.lessons:
            if chapter.chapter_id == "editor":
                continue
            print("  ok", item.level_id, item.max_turns, item.win_condition.value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
