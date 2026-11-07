"""Author the tutorial chapter data and write tutorials/*.json.

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


def level(
    lesson_id: str,
    name: str,
    grid: List[str],
    facing: str,
    cow_facings: List[str],
    *,
    exit_cells: List[List[int]],
    max_turns: int,
    prediction_steps: int = 0,
    cow_behavior: Any = "seek_exit",
    exit_sight_range: int = -1,
    sight_range: int = -1,
    cows_block_sight: bool = False,
    cows_block_each_other: bool = False,
    s_threshold: int = 5,
    a_threshold: int = 9,
    b_threshold: int = 13,
    **extra: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": lesson_id,
        "name": name,
        "grid": grid,
        "fj_start_direction": facing,
        "cow_facings": cow_facings,
        "cow_behavior": cow_behavior,
        "exit_cells": exit_cells,
        "max_turns": max_turns,
        "prediction_steps": prediction_steps,
        "exit_sight_range": exit_sight_range,
        "sight_range": sight_range,
        "exit_tiebreak": "right",
        "flee_tiebreak": "right",
        "cows_block_sight": cows_block_sight,
        "cows_block_each_other": cows_block_each_other,
        "s_threshold": s_threshold,
        "a_threshold": a_threshold,
        "b_threshold": b_threshold,
    }
    payload.update(extra)
    return payload


def lesson(
    lesson_id: str,
    name: str,
    brief: str,
    goal: str,
    practice: str,
    tips: List[Dict[str, str]],
    level_data: Dict[str, Any],
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
        "level": level_data,
    }
    if editor_task:
        payload["editor_task"] = editor_task
    if starter_grid:
        payload["starter_grid"] = starter_grid
    return payload


BASICS = {
    "title": "基础教程",
    "subtitle": "从一脚油门到出口前的拦截",
    "intro": "六节短课：开动、转向、看出口、利用墙、抢在牛前面，以及撤销与预测。",
    "badge": "基础",
    "accent": "leaf",
    "lessons": [
        lesson(
            "basics_01",
            "第一步",
            "前进、左转、右转；转向会消耗回合。",
            "抓住牧场上的牛。",
            "先按 A/← 和 D/→ 各转一次，再抓住牛。",
            [
                {"trigger": "start", "text": "W/↑ 前进，A/← 左转，D/→ 右转。转向不移动，但会消耗一个回合。"},
                {"trigger": "step", "text": "注意农夫有朝向：前进只会朝当前方向走一格。"},
                {"trigger": "win", "text": "抓住了！接下来学会看出口。"},
            ],
            level(
                "basics_01",
                "第一步",
                ["#######", "#.....#", "#...C.#", "#.....#", "#.....#", "#F....#", "#######"],
                "north",
                ["east"],
                exit_cells=[[1, 1]],
                max_turns=20,
                exit_sight_range=0,
                s_threshold=6,
                a_threshold=10,
                b_threshold=14,
                require_turn=True,
            ),
        ),
        lesson(
            "basics_02",
            "撞墙的代价",
            "撞墙前进位置不变，但会消耗回合。",
            "先撞一次墙，再抓住牛。",
            "先按 W/↑ 撞一次墙，再转向抓牛。",
            [
                {"trigger": "start", "text": "农夫前面就是围栏。先按 W/↑ 试试，看看会发生什么。"},
                {"trigger": "blocked", "text": "前方受阻，本回合已消耗。位置和朝向都不变。"},
                {"trigger": "step", "text": "先转向，再前进。农场里的每一回合都很宝贵。"},
                {"trigger": "win", "text": "撞墙不移动，但会浪费回合。记住这一点。"},
            ],
            level(
                "basics_02",
                "撞墙的代价",
                ["#######", "#F....#", "#...C.#", "#.....#", "#.....#", "#.....#", "#######"],
                "north",
                ["east"],
                exit_cells=[[1, 5]],
                max_turns=24,
                exit_sight_range=0,
                s_threshold=8,
                a_threshold=12,
                b_threshold=16,
                require_block=True,
            ),
        ),
        lesson(
            "basics_03",
            "出口在哪",
            "牛会朝它看得见的出口走；这一关的出口就在右边。",
            "观察牛的路线，用等待抓住它。",
            "先按空格等待至少一回合，让牛自己走过来。",
            [
                {"trigger": "start", "text": "金色格子是出口。牛会朝它看得见的出口走。"},
                {"trigger": "wait", "text": "牛正在靠近。按空格让农夫等待，观察它的路线。"},
                {"trigger": "win", "text": "牛走进了农夫所在的格子。抓住它！"},
            ],
            level(
                "basics_03",
                "出口在哪",
                ["#######", "#.....#", "#.....#", "#C..F.#", "#.....#", "#.....#", "#######"],
                "east",
                ["east"],
                exit_cells=[[3, 5]],
                max_turns=10,
                s_threshold=3,
                a_threshold=5,
                b_threshold=7,
                require_wait=True,
            ),
        ),
        lesson(
            "basics_04",
            "挡住直线",
            "固定地形会挡住牛的视线，让它改为沿墙巡逻。",
            "利用中间那堵墙改变牛的巡逻路线。",
            "观察牛因为墙而右转。",
            [
                {"trigger": "start", "text": "牛和出口之间有一堵墙，所以它看不到出口，只能沿墙右转巡逻。"},
                {"trigger": "step", "text": "利用它撞墙右转的规律，把农夫开到它的下一格。"},
                {"trigger": "win", "text": "固定地形改变了牛的路线，这就是关卡设计的力量。"},
            ],
            level(
                "basics_04",
                "挡住直线",
                ["#######", "#F....#", "#.....#", "#C.#..#", "#.....#", "#.....#", "#######"],
                "north",
                ["east"],
                exit_cells=[[3, 5]],
                max_turns=18,
                s_threshold=6,
                a_threshold=10,
                b_threshold=14,
            ),
        ),
        lesson(
            "basics_05",
            "出口前的拦截",
            "抢在牛到达出口前拦住它。",
            "在牛到达出口前抓住它。",
            "先转向，再前进，抢在出口前拦住牛。",
            [
                {"trigger": "start", "text": "牛已经贴近出口。先转向，再前进，别让它走到金色格子。"},
                {"trigger": "step", "text": "每一步都要算好；牛跑到出口就失败了。"},
                {"trigger": "win", "text": "在出口前抓住了它！这就是紧迫感。"},
            ],
            level(
                "basics_05",
                "出口前的拦截",
                ["#######", "#...F.#", "#.....#", "#C....#", "#.....#", "#.....#", "#######"],
                "north",
                ["east"],
                exit_cells=[[3, 5]],
                max_turns=8,
                s_threshold=3,
                a_threshold=5,
                b_threshold=7,
            ),
        ),
        lesson(
            "basics_06",
            "预判与撤销",
            "预测路线，撤销走错的回合。",
            "打开预测，撤销一次，再抓住牛。",
            "先按 P 打开预测，再按 U 撤销至少一次，完成本课。",
            [
                {"trigger": "start", "text": "这一关把预测和撤销放在一起。按 P 打开 6 步预测，再按 U 撤销走错的回合。"},
                {"trigger": "predict", "text": "脚印显示牛接下来的路线。根据它决定农夫的方向。"},
                {"trigger": "undo", "text": "撤销会把农夫、牛和回合数一起恢复。放心试错。"},
                {"trigger": "win", "text": "预测加撤销，让你可以大胆规划。"},
            ],
            level(
                "basics_06",
                "预判与撤销",
                ["#######", "#.....#", "#..#..#", "#..C..#", "#..#..#", "#F....#", "#######"],
                "north",
                ["east"],
                exit_cells=[[1, 1]],
                max_turns=25,
                prediction_steps=6,
                s_threshold=6,
                a_threshold=10,
                b_threshold=14,
                require_undo=True,
                require_prediction=True,
            ),
        ),
    ],
}


ADVANCED = {
    "title": "进阶教程",
    "subtitle": "会躲的牛与多头牛的压力",
    "intro": "三节进阶课：看到农夫先逃跑的牛、两头牛，以及同时抓牛和防逃。",
    "badge": "进阶",
    "accent": "sky",
    "lessons": [
        lesson(
            "advanced_01",
            "会躲的牛",
            "seek_exit_and_flee：看到农夫时，牛会优先拉开距离。",
            "抓住这头会躲的牛。",
            "留意牛头顶的警觉图标：它说明牛正在逃跑。",
            [
                {"trigger": "start", "text": "这头牛看到农夫会先逃跑。留意它头顶的警觉图标。"},
                {"trigger": "step", "text": "它想拉开距离。把它逼向角落，再找机会靠近。"},
                {"trigger": "win", "text": "会躲的牛也会被墙角困住。进阶教程开始！"},
            ],
            level(
                "advanced_01",
                "会躲的牛",
                ["#######", "#.....#", "#.....#", "#F...C#", "#.....#", "#.....#", "#######"],
                "east",
                ["east"],
                exit_cells=[[3, 3]],
                max_turns=15,
                cow_behavior="seek_exit_and_flee",
                sight_range=6,
                s_threshold=6,
                a_threshold=9,
                b_threshold=12,
            ),
        ),
        lesson(
            "advanced_02",
            "两头牛",
            "两头牛按固定顺序移动，全部抓住才算赢。",
            "抓住全部两头牛。",
            "先抓离出口更近的那一头，再回头找另一头。",
            [
                {"trigger": "start", "text": "两头牛都会奔向出口。按顺序移动，全部抓住才算赢。"},
                {"trigger": "step", "text": "先解决离出口更近的那头；另一头会继续走。"},
                {"trigger": "win", "text": "两头都抓住了！多牛关卡需要分配注意力。"},
            ],
            level(
                "advanced_02",
                "两头牛",
                ["#######", "#.....#", "#.C.C.#", "#.....#", "#.....#", "#F....#", "#######"],
                "north",
                ["east", "east"],
                exit_cells=[[5, 5]],
                max_turns=28,
                cow_behavior="seek_exit_and_flee",
                sight_range=6,
                cows_block_each_other=True,
                s_threshold=18,
                a_threshold=22,
                b_threshold=26,
            ),
        ),
        lesson(
            "advanced_03",
            "双重压力",
            "一头牛只奔出口，另一头会躲；它们的行为不一样。",
            "抓住全部牛，同时别让任何一头到出口。",
            "先看两头牛的行为，再决定先追哪一头。",
            [
                {"trigger": "start", "text": "一头牛只奔向出口，另一头看到农夫会逃跑。先看它们的行为，再决定目标。"},
                {"trigger": "step", "text": "用预测确认哪一头更接近出口，先拦住它。"},
                {"trigger": "win", "text": "抓牛与防逃同时完成。进阶教程结束！"},
            ],
            level(
                "advanced_03",
                "双重压力",
                ["#######", "#.....#", "#.C.C.#", "#.....#", "#.....#", "#F....#", "#######"],
                "north",
                ["east", "east"],
                exit_cells=[[5, 5]],
                max_turns=24,
                cow_behavior=["seek_exit", "seek_exit_and_flee"],
                sight_range=6,
                cows_block_each_other=True,
                s_threshold=16,
                a_threshold=20,
                b_threshold=23,
            ),
        ),
    ],
}


EDITOR = {
    "title": "编辑器教程",
    "subtitle": "自己造一片有出口的牧场",
    "intro": "三节编辑器课：画地形、设置出口与牛的行为、导出与导入。",
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
                "north",
                ["north"],
                exit_cells=[[1, 1]],
                max_turns=40,
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
            "出口与行为",
            "画出出口，并让一头牛看到农夫时先逃跑。",
            "画出两格出口，并把一头牛改成「躲避」。",
            "用出口格工具画两格，再点「行为」切换成躲避。",
            [
                {"trigger": "start", "text": "用「出口格」画两格出口；再用「行为」把一头牛切成「躲避」。"},
                {"trigger": "place", "text": "金色格子是出口。出口是牛的目标，也是玩家的失败点。"},
            ],
            level(
                "editor_02",
                "出口与行为",
                STARTER,
                "north",
                ["north"],
                exit_cells=[[1, 1]],
                max_turns=40,
                prediction_steps=5,
                s_threshold=10,
                a_threshold=18,
                b_threshold=26,
            ),
            editor_task={"type": "set_exits", "count": 2},
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
                "north",
                ["north"],
                exit_cells=[[1, 1]],
                max_turns=40,
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
    catalog = TutorialCatalog.load()
    for chapter in catalog.all():
        for item in chapter.lessons:
            if chapter.chapter_id == "editor":
                continue
            print("  ok", item.level_id, item.max_turns, item.exit_cells)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
