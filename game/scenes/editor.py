"""Local level editor scene, including the editor tutorial lessons."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import pygame

from .. import art, editor, theme, ui
from ..editor import EditorModel, PAINT_TILES, export_level, import_level, list_custom_levels
from ..levels import LevelError
from ..models import CowPersonality, Direction, ItemKind, Level, Pos, TileKind
from ..render import CELL, ORIGIN, draw_grid
from .base import Scene, draw_background, draw_footer, make_back_button

TOOL_TERRAIN = "terrain"
TOOL_FARMER = "farmer"
TOOL_COW = "cow"

TERRAIN_LABELS = {
    TileKind.GRASS: "草地",
    TileKind.FENCE: "栅栏",
    TileKind.HEDGE: "树篱",
    TileKind.TREE: "树木",
    TileKind.POND: "水塘",
}

TASK_TEXT = {
    "paint_wall": "在草地上画出 {count} 格栅栏。",
    "place_actors": "移动农夫和牛，给它们换个位置。",
    "export_import": "导出一份关卡，再把它导入回来。",
}


class EditorScene(Scene):
    def __init__(self, app, tutorial_chapter: str = "", tutorial_lesson: Optional[Level] = None) -> None:
        super().__init__(app)
        self.tutorial_chapter = tutorial_chapter
        self.tutorial_lesson = tutorial_lesson
        self.back_button = make_back_button()
        self.model: EditorModel = EditorModel()
        self.tool = TOOL_TERRAIN
        self.brush: TileKind = TileKind.FENCE
        self.hover: Optional[Pos] = None
        self.toast_text = ""
        self.toast_timer = 0.0
        self.modal: Optional[ui.Modal] = None
        self.import_buttons: List[ui.Button] = []
        self.task_done = False
        self.painted_walls: set = set()
        self.farmer_moved = False
        self.cow_moved = False
        self.exported_path: Optional[Path] = None
        self.imported_once = False
        self.buttons: List[ui.Button] = []
        self._build_widgets()

    # ------------------------------------------------------------------
    def on_enter(self) -> None:
        if self.app.editor_model is not None and not self.tutorial_lesson:
            self.model = self.app.editor_model
        elif self.tutorial_lesson is not None:
            starter = self.level.extra.get("starter_grid")
            if starter:
                from ..levels import parse_level

                payload = {
                    "id": "editor_starter",
                    "name": self.level.name,
                    "grid": starter,
                    "obstacle_limit": 3,
                    "step_limit": 40,
                }
                try:
                    self.model = EditorModel.from_level(
                        parse_level(payload, source="custom")
                    )
                except LevelError:
                    self.model = EditorModel()
            else:
                self.model = EditorModel()
        self._build_widgets()
        if self.tutorial_lesson is not None and self.app.book is not None:
            self.app.book.begin_lesson(self.tutorial_chapter, self.level.tutorial_id or self.level.level_id)

    @property
    def level(self) -> Level:
        if self.tutorial_lesson is not None:
            return self.tutorial_lesson
        return self.app.levels[0]

    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        self.buttons = []
        self.terrain_buttons: List[ui.Button] = []
        for index, kind in enumerate(PAINT_TILES):
            row, col = divmod(index, 4)
            self.terrain_buttons.append(
                ui.Button(
                    pygame.Rect(764 + col * 112, 156 + row * 54, 104, 48),
                    TERRAIN_LABELS[kind],
                    f"paint:{kind.value}",
                    style="ghost",
                    font_size=theme.FONT_SMALL,
                )
            )
        self.actor_buttons = [
            ui.Button(pygame.Rect(764, 296, 140, 44), "农夫", "actor:farmer", style="ghost", font_size=theme.FONT_SMALL),
            ui.Button(pygame.Rect(916, 296, 140, 44), "牛", "actor:cow", style="ghost", font_size=theme.FONT_SMALL),
        ]
        self.facing_button = ui.Button(
            pygame.Rect(1068, 296, 140, 44), "朝向", "cycle_facing", style="ghost", font_size=theme.FONT_SMALL
        )
        self.personality_button = ui.Button(
            pygame.Rect(764, 348, 444, 44), "牛的性格：", "cycle_personality", style="ghost", font_size=theme.FONT_SMALL
        )
        self.obstacle_minus = ui.Button(pygame.Rect(764, 426, 46, 40), "−", "obstacle:-", style="ghost")
        self.obstacle_plus = ui.Button(pygame.Rect(964, 426, 46, 40), "+", "obstacle:+", style="ghost")
        self.steps_minus = ui.Button(pygame.Rect(764, 474, 46, 40), "−", "steps:-", style="ghost")
        self.steps_plus = ui.Button(pygame.Rect(964, 474, 46, 40), "+", "steps:+", style="ghost")
        self.play_button = ui.Button(pygame.Rect(764, 606, 210, 52), "试玩", "play", style="primary", font_size=theme.FONT_H3)
        self.export_button = ui.Button(pygame.Rect(990, 606, 218, 52), "导出关卡", "export", style="default", font_size=theme.FONT_H3)
        self.import_button = ui.Button(pygame.Rect(764, 670, 210, 46), "导入关卡", "import", style="ghost")
        self.clear_button = ui.Button(pygame.Rect(990, 670, 218, 46), "清空重来", "clear", style="ghost")
        self.buttons = [
            *self.terrain_buttons,
            *self.actor_buttons,
            self.facing_button,
            self.personality_button,
            self.obstacle_minus,
            self.obstacle_plus,
            self.steps_minus,
            self.steps_plus,
            self.play_button,
            self.export_button,
            self.import_button,
            self.clear_button,
        ]

    # ------------------------------------------------------------------
    def _cell_at(self, pos: Tuple[int, int]) -> Optional[Pos]:
        local_x = pos[0] - ORIGIN[0]
        local_y = pos[1] - ORIGIN[1]
        if not (0 <= local_x < CELL * self.model.width and 0 <= local_y < CELL * self.model.height):
            return None
        return (local_y // CELL, local_x // CELL)

    def _toast(self, text: str, duration: float = 2.4) -> None:
        self.toast_text = text
        self.toast_timer = duration

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.modal is not None:
            action = self.modal.handle_event(event)
            if action:
                self._modal_action(action)
            return
        if self.back_button.handle_event(event):
            self.app.editor_model = self.model
            self.app.open_scene("menu")
            return
        for button in self.buttons:
            action = button.handle_event(event)
            if action:
                self._action(action)
                return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.editor_model = self.model
                self.app.open_scene("menu")
            elif event.key == pygame.K_1:
                self._action("paint:fence")
            elif event.key == pygame.K_2:
                self._action("paint:grass")
        elif event.type == pygame.MOUSEMOTION:
            self.hover = self._cell_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            cell = self._cell_at(event.pos)
            if cell is None:
                return
            if event.button == 1:
                self._paint(cell)
            elif event.button == 3:
                self.model.set_tile(cell, TileKind.GRASS)

    def _paint(self, cell: Pos) -> None:
        if self.tool == TOOL_FARMER:
            if self.model.move_farmer(cell):
                self.farmer_moved = True
                self.app.sound.play("place")
            return
        if self.tool == TOOL_COW:
            if self.model.move_cow(cell):
                self.cow_moved = True
                self.app.sound.play("place")
            return
        if self.model.set_tile(cell, self.brush):
            if self.brush is TileKind.FENCE:
                self.painted_walls.add(cell)
            self.app.sound.play("place")

    # ------------------------------------------------------------------
    def _action(self, action: str) -> None:
        if action.startswith("paint:"):
            self.tool = TOOL_TERRAIN
            self.brush = TileKind(action.split(":", 1)[1])
            self.app.sound.play("click")
        elif action.startswith("actor:"):
            self.tool = action.split(":", 1)[1]
            self.app.sound.play("click")
        elif action == "cycle_facing":
            self.model.cycle_facing()
            self.app.sound.play("click")
        elif action == "cycle_personality":
            self.model.cycle_cow_personality()
            self.app.sound.play("click")
        elif action.startswith("obstacle:"):
            delta = 1 if action.endswith("+") else -1
            self.model.obstacle_limit = max(0, min(9, self.model.obstacle_limit + delta))
        elif action.startswith("steps:"):
            delta = 10 if action.endswith("+") else -10
            self.model.step_limit = max(10, min(120, self.model.step_limit + delta))
        elif action == "play":
            self._test_play()
        elif action == "export":
            self._export()
        elif action == "import":
            self._open_import()
        elif action == "clear":
            self.model = EditorModel()
            self.painted_walls.clear()
            self.farmer_moved = self.cow_moved = False
            self._toast("牧场已经清空。")

    def _test_play(self) -> None:
        problems = self.model.validate()
        if problems:
            self._toast(problems[0])
            self.app.sound.play("error")
            return
        try:
            level = self.model.to_level("custom_preview")
        except LevelError as exc:
            self._toast(str(exc))
            self.app.sound.play("error")
            return
        self.app.editor_model = self.model
        self.app.start_level(level, mode="editor", return_to="editor")

    def _export(self) -> None:
        problems = self.model.validate()
        if problems:
            self._toast(problems[0])
            self.app.sound.play("error")
            return
        try:
            level = self.model.to_level()
            path = export_level(level)
        except (LevelError, OSError) as exc:
            self._toast(f"导出失败：{exc}")
            self.app.sound.play("error")
            return
        self.exported_path = path
        self.app.sound.play("unlock")
        self._toast(f"已导出到 custom_levels/{path.name}")
        self._check_task()

    def _open_import(self) -> None:
        files = list_custom_levels()
        if not files:
            self._toast("custom_levels 里还没有导出的关卡。")
            self.app.sound.play("error")
            return
        self.import_buttons = []
        buttons: List[ui.Button] = []
        for index, path in enumerate(files[:5]):
            buttons.append(
                ui.Button(
                    pygame.Rect(0, 0, 460, 46),
                    path.stem[:28],
                    f"file:{index}",
                    style="ghost",
                    font_size=theme.FONT_SMALL,
                )
            )
        self._import_files = files[:5]
        cancel = ui.Button(pygame.Rect(0, 0, 150, 46), "取消", "cancel", style="ghost")
        self.import_buttons = buttons
        self.modal = ui.Modal(
            "导入关卡",
            "选择一个之前导出的关卡文件：",
            accent=theme.SKY_DEEP,
            buttons=[cancel],
            width=620,
            height=420,
        )
        # place the file buttons inside the modal
        y = self.modal.rect.top + 150
        for button in buttons:
            button.rect.topleft = (self.modal.rect.left + 60, y)
            y += 54
        self.modal.buttons = buttons + [cancel]

    def _modal_action(self, action: str) -> None:
        if action == "cancel":
            self.modal = None
            return
        if action.startswith("file:"):
            index = int(action.split(":", 1)[1])
            try:
                level = import_level(self._import_files[index])
                self.model = EditorModel.from_level(level)
            except (LevelError, OSError, ValueError) as exc:
                self.modal = None
                self._toast(f"导入失败：{exc}")
                return
            self.modal = None
            self.imported_once = True
            self.app.sound.play("unlock")
            self._toast(f"已导入《{level.name}》")
            self._check_task()
            return
        if action == "tutorial_done":
            self.modal = None
            if self.app.book is not None:
                self.app.open_tutorial_chapter(self.tutorial_chapter)
            return
        if action == "tutorial_next":
            self.modal = None
            self.app.open_next_tutorial_lesson(self.tutorial_chapter)

    # ------------------------------------------------------------------
    def _task(self) -> Optional[dict]:
        if self.tutorial_lesson is None:
            return None
        task = self.tutorial_lesson.extra.get("editor_task")
        return task if isinstance(task, dict) else None

    def _task_progress(self) -> Tuple[int, int]:
        task = self._task()
        if not task:
            return (0, 0)
        kind = task.get("type")
        if kind == "paint_wall":
            target = int(task.get("count", 3))
            return (min(len(self.painted_walls), target), target)
        if kind == "place_actors":
            done = int(self.farmer_moved) + int(self.cow_moved)
            return (done, 2)
        if kind == "export_import":
            done = int(self.exported_path is not None) + int(self.imported_once)
            return (done, 2)
        return (0, 1)

    def _check_task(self) -> None:
        if self.task_done or self.tutorial_lesson is None:
            return
        done, total = self._task_progress()
        if total == 0 or done < total:
            return
        self.task_done = True
        if self.app.book is not None:
            self.app.book.complete_lesson(
                self.tutorial_chapter, self.tutorial_lesson.tutorial_id or self.tutorial_lesson.level_id
            )
        self.app.sound.play("win")
        self.modal = ui.Modal(
            "教程完成",
            "这一课的目标完成了！\n编辑器里的改动可以随时导出成 JSON 文件。",
            accent=theme.LEAF,
            badge="教程",
            buttons=[
                ui.Button(pygame.Rect(0, 0, 170, 50), "下一课", "tutorial_next", style="primary"),
                ui.Button(pygame.Rect(0, 0, 150, 50), "返回章节", "tutorial_done", style="ghost"),
            ],
            width=640,
            height=340,
        )

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        super().update(dt)
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)
        if self.modal is not None:
            self.modal.update(pygame.mouse.get_pos())
        if self.tutorial_lesson is not None and not self.task_done and self.modal is None:
            self._check_task()

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        title = "关卡编辑器"
        badge = "编辑器"
        badge_color = theme.CLAY
        if self.tutorial_lesson is not None:
            badge = "教程"
            badge_color = theme.SKY_DEEP
        theme.draw_text(surface, self.fonts, title, (62, 34), theme.FONT_H1, theme.INK, bold=True)
        ui.draw_pill(surface, self.fonts, badge, (62 + 300, 58), badge_color)
        theme.draw_text(
            surface,
            self.fonts,
            self.model.name,
            (62 + 400, 50),
            theme.FONT_SMALL,
            theme.INK_SOFT,
        )
        pygame.draw.line(surface, theme.PANEL_BORDER, (60, 104), (1220, 104), 2)
        self.back_button.draw(surface, self.fonts)

        self._draw_board(surface)
        self._draw_panel(surface)
        draw_footer(surface, self.fonts, "左键绘制 · 右键擦除为草地 · 导出文件保存在 custom_levels/")
        if self.toast_timer > 0 and self.toast_text:
            self._draw_toast(surface)
        if self.modal is not None:
            self.modal.draw(surface, self.fonts)

    def _draw_board(self, surface: pygame.Surface) -> None:
        frame = pygame.Rect(ORIGIN[0] - 14, ORIGIN[1] - 14, CELL * self.model.width + 28, CELL * self.model.height + 28)
        theme.soft_shadow(surface, frame, radius=26, alpha=42, offset=(0, 7))
        theme.rounded_rect(surface, frame, theme.WOOD_LIGHT, radius=26)
        theme.rounded_rect(surface, frame, theme.WOOD_DARK, radius=26, width=3)
        pygame.draw.rect(surface, theme.GRASS_DARK, frame.inflate(-8, -8), border_radius=22)

        def kind_at(row: int, col: int) -> TileKind:
            return self.model.tiles[row][col]

        draw_grid(surface, self.cache, self.model.width, self.model.height, kind_at)
        if self.hover is not None:
            rect = pygame.Rect(
                ORIGIN[0] + self.hover[1] * CELL, ORIGIN[1] + self.hover[0] * CELL, CELL, CELL
            )
            layer = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
            pygame.draw.rect(layer, (*theme.SUN, 70), layer.get_rect().inflate(-4, -4), border_radius=12)
            pygame.draw.rect(layer, (*theme.SUN, 200), layer.get_rect().inflate(-4, -4), width=2, border_radius=12)
            surface.blit(layer, rect.topleft)
        # actors
        cow_scale = 1.0
        for pos, facing, personality in self.model.cows:
            sprite = self.cache.cow(facing, personality)
            surface.blit(
                sprite,
                sprite.get_rect(
                    center=(
                        ORIGIN[0] + pos[1] * CELL + CELL // 2,
                        ORIGIN[1] + pos[0] * CELL + CELL // 2,
                    )
                ),
            )
        sprite = self.cache.farmer(self.model.farmer_facing)
        surface.blit(
            sprite,
            sprite.get_rect(
                center=(
                    ORIGIN[0] + self.model.farmer[1] * CELL + CELL // 2,
                    ORIGIN[1] + self.model.farmer[0] * CELL + CELL // 2,
                )
            ),
        )

    def _draw_panel(self, surface: pygame.Surface) -> None:
        theme.panel(surface, theme.PANEL_RECT)
        left = theme.PANEL_RECT.left + 24
        y = theme.PANEL_RECT.top + 20
        theme.draw_text(surface, self.fonts, "地形", (left, y), theme.FONT_SMALL, theme.INK_LIGHT)
        y += 30
        for index, button in enumerate(self.terrain_buttons):
            button.style = "primary" if (self.tool == TOOL_TERRAIN and button.key == f"paint:{self.brush.value}") else "ghost"
            button.draw(surface, self.fonts)

        theme.draw_text(surface, self.fonts, "角色", (left, 272), theme.FONT_SMALL, theme.INK_LIGHT)
        for button in self.actor_buttons:
            button.style = "primary" if button.key == f"actor:{self.tool}" else "ghost"
            button.draw(surface, self.fonts)
        self.facing_button.text = f"朝 {self.model.farmer_facing.label}"
        self.facing_button.draw(surface, self.fonts)
        personality = self.model.cows[0][2] if self.model.cows else CowPersonality.NORMAL
        self.personality_button.text = f"牛的性格：{personality.label}"
        self.personality_button.draw(surface, self.fonts)

        theme.draw_text(surface, self.fonts, "规则", (left, 402), theme.FONT_SMALL, theme.INK_LIGHT)
        theme.draw_text(
            surface, self.fonts, "障碍上限", (left + 58, 446), theme.FONT_BODY, theme.INK, anchor="midleft"
        )
        theme.draw_text(
            surface,
            self.fonts,
            str(self.model.obstacle_limit),
            (left + 165, 446),
            theme.FONT_H3,
            theme.CLAY_DARK,
            anchor="center",
            bold=True,
        )
        theme.draw_text(
            surface, self.fonts, "步数上限", (left + 58, 494), theme.FONT_BODY, theme.INK, anchor="midleft"
        )
        theme.draw_text(
            surface,
            self.fonts,
            str(self.model.step_limit),
            (left + 165, 494),
            theme.FONT_H3,
            theme.CLAY_DARK,
            anchor="center",
            bold=True,
        )
        for button in (self.obstacle_minus, self.obstacle_plus, self.steps_minus, self.steps_plus):
            button.draw(surface, self.fonts)

        if self.tutorial_lesson is not None:
            self._draw_task_box(surface, left, 528)
        else:
            hint = self.fonts.wrap(
                "从空白牧场开始：画出围栏、摆好农夫和牛，再用试玩验证能否抓住。",
                theme.FONT_SMALL,
                444,
                theme.INK_SOFT,
            )
            surface.blit(hint, (left, 528))

        for button in (self.play_button, self.export_button, self.import_button, self.clear_button):
            button.draw(surface, self.fonts)

    def _draw_task_box(self, surface: pygame.Surface, x: int, y: int) -> None:
        box = pygame.Rect(x, y, 444, 66)
        theme.rounded_rect(surface, box, theme.SKY_PALE, radius=14)
        theme.rounded_rect(surface, box, theme.SKY_DEEP, radius=14, width=2)
        task = self._task() or {}
        text = TASK_TEXT.get(str(task.get("type")), "完成编辑器练习。").format(count=task.get("count", 3))
        wrapped = self.fonts.wrap(text, theme.FONT_SMALL, 400, theme.INK)
        surface.blit(wrapped, (box.left + 16, box.top + 8))
        done, total = self._task_progress()
        theme.draw_text(
            surface,
            self.fonts,
            f"{done} / {total}",
            (box.right - 16, box.bottom - 10),
            theme.FONT_TINY,
            theme.INK_SOFT,
            anchor="bottomright",
        )

    def _draw_toast(self, surface: pygame.Surface) -> None:
        body = self.fonts.wrap(self.toast_text, theme.FONT_SMALL, 520, theme.WHITE_WARM)
        rect = pygame.Rect(0, 0, body.get_width() + 40, body.get_height() + 24)
        rect.center = (ORIGIN[0] + CELL * 5, 96)
        theme.soft_shadow(surface, rect, radius=14, alpha=60, offset=(0, 4))
        theme.rounded_rect(surface, rect, theme.CLAY, radius=14)
        surface.blit(body, (rect.left + 20, rect.top + 12))
