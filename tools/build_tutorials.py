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
    prediction_steps: int = 5,
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
    "subtitle": "从转向、前进到出口前的拦截",
    "intro": "七节短课：绝对方向转向、前进、出口、逃跑、地形遮挡、拦截，以及撤销与预测。",
    "badge": "基础",
    "accent": "leaf",
    "lessons": [
        lesson(
            "basics_01",
            "朝哪走",
            "W/A/S/D 或方向键改变绝对朝向，空格朝当前朝向走一格。",
            "用转向和前进抓住牛。",
            "先按 W/↑（当前已朝上）确认无效，再用转向和空格抓住牛。",
            [
                {"trigger": "start", "text": "W/↑ 朝上，S/↓ 朝下，A/← 朝左，D/→ 朝右，空格前进。每回合必须转向或前进。"},
                {"trigger": "invalid", "text": "已朝该方向。这次操作无效，回合数没有增加；也不能原地不动。"},
                {"trigger": "turn", "text": "转向会消耗一个回合，但不会移动。"},
                {"trigger": "forward", "text": "空格让农夫朝当前朝向前进一格。"},
                {"trigger": "win", "text": "抓住了！现在你已经会用绝对方向驾驶农夫。"},
            ],
            level(
                "basics_01",
                "朝哪走",
                ["#######", "#.....#", "#...C.#", "#.....#", "#.....#", "#F....#", "#######"],
                "north",
                ["east"],
                exit_cells=[[1, 1]],
                max_turns=14,
                exit_sight_range=0,
                s_threshold=6,
                a_threshold=9,
                b_threshold=12,
                require_invalid=True,
                require_forward=True,
            ),
        ),
        lesson(
            "basics_02",
            "撞墙的代价",
            "撞墙前进位置不变，但会消耗回合。",
            "先撞一次墙，再抓住牛。",
            "先按空格朝北撞一次墙，再转向抓牛。",
            [
                {"trigger": "start", "text": "农夫前面就是围栏。按空格前进，看看会发生什么。"},
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
                max_turns=18,
                exit_sight_range=0,
                s_threshold=9,
                a_threshold=12,
                b_threshold=15,
                require_block=True,
            ),
        ),
        lesson(
            "basics_03",
            "出口在哪",
            "牛看不到农夫时，会朝它看得见的出口走。",
            "观察牛的路线，在它到达出口前抓住它。",
            "先观察牛朝出口移动，再转向前进拦截。",
            [
                {"trigger": "start", "text": "金色格子是出口。牛看不到农夫时，会朝出口走。"},
                {"trigger": "step", "text": "牛正在靠近出口。判断它的下一步，再决定农夫的方向。"},
                {"trigger": "win", "text": "在出口前抓住了！你已经看懂牛的路线。"},
            ],
            level(
                "basics_03",
                "出口在哪",
                ["#######", "#.....#", "#...F.#", "#.....#", "#C....#", "#.....#", "#######"],
                "north",
                ["east"],
                exit_cells=[[4, 5]],
                max_turns=12,
                s_threshold=4,
                a_threshold=6,
                b_threshold=8,
                require_actions=3,
            ),
        ),
        lesson(
            "basics_04",
            "警觉的牛",
            "牛看到农夫时会逃跑，头顶出现警觉图标。",
            "从侧面或角落接近，抓住这头会躲的牛。",
            "观察警觉图标，先移动再转向，从侧面拦住它。",
            [
                {"trigger": "start", "text": "农夫和牛在同一条直线上，牛已经看到你了。留意它头顶的警觉图标。"},
                {"trigger": "step", "text": "牛会主动拉开距离。不要一直正面直线逼近，试着从侧面拦住它。"},
                {"trigger": "win", "text": "会躲的牛也会被边界困住。你学会了观察警觉状态。"},
            ],
            level(
                "basics_04",
                "警觉的牛",
                ["#######", "#.....#", "#.....#", "#F...C#", "#.....#", "#.....#", "#######"],
                "east",
                ["east"],
                exit_cells=[[3, 3]],
                max_turns=12,
                sight_range=6,
                s_threshold=6,
                a_threshold=8,
                b_threshold=10,
                require_actions=3,
            ),
        ),
        lesson(
            "basics_05",
            "墙后的伏击",
            "固定地形会挡住牛的视线；它看不到农夫时，会按出口路线走。",
            "利用墙挡住视线，再绕出来抓住牛。",
            "先向右，再向下，从墙后绕出来。",
            [
                {"trigger": "start", "text": "农夫和牛之间隔着一堵墙，所以牛暂时看不到你，会朝出口走。"},
                {"trigger": "step", "text": "墙挡住了牛的视线。绕到它的侧面，突然出现。"},
                {"trigger": "win", "text": "固定地形改变了牛的判断。善用墙，就能创造拦截机会。"},
            ],
            level(
                "basics_05",
                "墙后的伏击",
                ["#######", "#F....#", "##....#", "#C....#", "#.....#", "#.....#", "#######"],
                "east",
                ["west"],
                exit_cells=[[3, 5]],
                max_turns=10,
                s_threshold=4,
                a_threshold=6,
                b_threshold=8,
                require_actions=3,
            ),
        ),
        lesson(
            "basics_06",
            "出口前的拦截",
            "牛已经贴近出口，每一步都不能浪费。",
            "在牛到达出口前抓住它。",
            "先转向，再前进，抢在出口前拦住牛。",
            [
                {"trigger": "start", "text": "牛已经贴近出口。先转向，再前进，别让它走到金色格子。"},
                {"trigger": "step", "text": "每一步都要算好；牛跑到出口就失败了。"},
                {"trigger": "win", "text": "在出口前抓住了它！这就是紧迫感。"},
            ],
            level(
                "basics_06",
                "出口前的拦截",
                ["#######", "#...F.#", "#.....#", "#C....#", "#.....#", "#.....#", "#######"],
                "north",
                ["east"],
                exit_cells=[[3, 5]],
                max_turns=7,
                s_threshold=4,
                a_threshold=5,
                b_threshold=6,
                require_actions=3,
            ),
        ),
        lesson(
            "basics_07",
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
                "basics_07",
                "预判与撤销",
                ["#######", "#.....#", "#..#..#", "#..C..#", "#..#..#", "#F....#", "#######"],
                "north",
                ["east"],
                exit_cells=[[1, 1]],
                max_turns=14,
                prediction_steps=6,
                s_threshold=6,
                a_threshold=9,
                b_threshold=12,
                require_undo=True,
                require_prediction=True,
            ),
        ),
    ],
}


ADVANCED = {
    "title": "进阶教程",
    "subtitle": "会躲的牛、多头牛与出口前的双重压力",
    "intro": "三节进阶课：在更开阔的牧场里追会躲的牛、管理多头牛，并同时守住出口。",
    "badge": "进阶",
    "accent": "sky",
    "lessons": [
        lesson(
            "advanced_01",
            "更大的牧场",
            "牛看到农夫会优先逃跑；开阔地形更难直接追上。",
            "在开阔牧场里抓住这头会躲的牛。",
            "先追近它，再根据它的逃跑方向绕到侧面。",
            [
                {"trigger": "start", "text": "这头牛看到农夫会先逃跑。开阔地没有墙，你需要预判它的转向。"},
                {"trigger": "step", "text": "牛会优先拉开距离。把它逼向边界，再找机会靠近。"},
                {"trigger": "win", "text": "会躲的牛也会被墙角困住。"},
            ],
            level(
                "advanced_01",
                "更大的牧场",
                ["#########", "#.......#", "#.......#", "#F.....C#", "#.......#", "#.......#", "#.......#", "#.......#", "#########"],
                "east",
                ["east"],
                exit_cells=[[3, 4]],
                max_turns=18,
                sight_range=8,
                s_threshold=10,
                a_threshold=13,
                b_threshold=16,
            ),
        ),
        lesson(
            "advanced_02",
            "两头牛",
            "两头牛按固定顺序移动，全部抓住才算赢。",
            "抓住全部两头牛。",
            "先抓离出口更近的那一头，再回头找另一头。",
            [
                {"trigger": "start", "text": "两头牛都会奔向出口。按固定顺序移动，全部抓住才算赢。"},
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
                max_turns=22,
                sight_range=6,
                cows_block_each_other=True,
                s_threshold=16,
                a_threshold=19,
                b_threshold=22,
            ),
        ),
        lesson(
            "advanced_03",
            "双重压力",
            "两头牛分散在两侧，既有抓牛压力，也要盯住出口。",
            "抓住全部牛，同时别让任何一头到出口。",
            "用预测确认哪一头更接近出口，先拦住它。",
            [
                {"trigger": "start", "text": "两头牛会同时向出口移动。先看出口和它们的位置，再决定先追哪一头。"},
                {"trigger": "step", "text": "用预测确认路线。不要让任何一头先到出口。"},
                {"trigger": "win", "text": "抓牛与防逃同时完成。进阶教程结束！"},
            ],
            level(
                "advanced_03",
                "双重压力",
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
                exit_cells=[[1, 7]],
                max_turns=26,
                sight_range=6,
                cows_block_each_other=True,
                s_threshold=19,
                a_threshold=22,
                b_threshold=25,
            ),
        ),
    ],
}


EDITOR = {
    "title": "编辑器教程",
    "subtitle": "自己造一片有出口的牧场",
    "intro": "三节编辑器课：画地形、设置出口与视线规则、导出与导入。",
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
            "出口与视线",
            "画出出口，并设置牛是否会挡住农夫视线。",
            "画出两格出口，并打开「牛挡视线」。",
            "用出口格画两格，再点「牛挡视线」把它打开。",
            [
                {"trigger": "start", "text": "用「出口格」画两格出口；再点「牛挡视线」，其他牛就会挡住农夫看向这头牛的视线。"},
                {"trigger": "place", "text": "金色格子是出口。出口是牛的目标，也是玩家的失败点。"},
            ],
            level(
                "editor_02",
                "出口与视线",
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
            editor_task={"type": "set_exits", "count": 2, "block_sight": True},
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
            print("  ok", chapter.chapter_id, item.level_id, item.max_turns, item.exit_cells)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
