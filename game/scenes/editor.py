"""Local level editor scene with export-time solvability checks."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import pygame

from .. import theme, ui
from ..editor import EditorModel, PAINT_TILES, export_level, import_level, list_custom_levels
from ..levels import LevelError
from ..models import Direction, Pos, TileKind
from ..render import CELL, ORIGIN, draw_grid
from ..solver import solve_level
from .base import Scene, draw_background, draw_footer, draw_header, make_back_button

TOOL_TERRAIN = "terrain"
TOOL_FARMER = "farmer"
TOOL_COW = "cow"
TOOL_EXIT = "exit"
TOOL_OBSTACLE = "obstacle"

TERRAIN_LABELS = {
    TileKind.GRASS: "草地",
    TileKind.FENCE: "栅栏",
    TileKind.HEDGE: "树篱",
    TileKind.TREE: "树木",
    TileKind.POND: "水塘",
}

class EditorScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.back_button = make_back_button()
        self.model: EditorModel = EditorModel()
        self.tool = TOOL_TERRAIN
        self.brush: TileKind = TileKind.FENCE
        self.hover: Optional[Pos] = None
        self.toast_text = ""
        self.toast_timer = 0.0
        self.modal: Optional[ui.Modal] = None
        self.import_buttons: List[ui.Button] = []
        self.exported_path: Optional[Path] = None
        self.pending_export = None
        self.buttons: List[ui.Button] = []
        self._build_widgets()

    # ------------------------------------------------------------------
    def on_enter(self) -> None:
        if self.app.editor_model is not None:
            self.model = self.app.editor_model
        self._build_widgets()

    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        self.buttons = []
        self.terrain_buttons: List[ui.Button] = []
        for index, kind in enumerate(PAINT_TILES):
            self.terrain_buttons.append(
                ui.Button(
                    pygame.Rect(611 + index * 72, 120, 64, 30),
                    TERRAIN_LABELS[kind],
                    f"paint:{kind.value}",
                    style="ghost",
                    font_size=theme.FONT_TINY,
                )
            )
        self.actor_buttons = [
            ui.Button(pygame.Rect(611, 157, 64, 30), "农夫", "actor:farmer", style="ghost", font_size=theme.FONT_TINY),
            ui.Button(pygame.Rect(684, 157, 64, 30), "牛", "actor:cow", style="ghost", font_size=theme.FONT_TINY),
            ui.Button(pygame.Rect(757, 157, 64, 30), "加牛", "actor:add", style="ghost", font_size=theme.FONT_TINY),
            ui.Button(pygame.Rect(830, 157, 64, 30), "减牛", "actor:remove", style="ghost", font_size=theme.FONT_TINY),
            ui.Button(pygame.Rect(903, 157, 64, 30), "换牛", "actor:cycle", style="ghost", font_size=theme.FONT_TINY),
        ]
        self.exit_button = ui.Button(
            pygame.Rect(611, 194, 112, 30), "出口格", "tool:exit", style="ghost", font_size=theme.FONT_TINY
        )
        self.obstacle_button = ui.Button(
            pygame.Rect(730, 194, 112, 30), "固定障碍", "tool:obstacle", style="ghost", font_size=theme.FONT_TINY
        )
        self.facing_button = ui.Button(
            pygame.Rect(611, 230, 173, 30), "农夫朝向", "cycle_facing", style="ghost", font_size=theme.FONT_TINY
        )
        self.cow_facing_button = ui.Button(
            pygame.Rect(790, 230, 176, 30), "牛朝向", "cycle_cow_facing", style="ghost", font_size=theme.FONT_TINY
        )
        self.exit_tie_button = ui.Button(
            pygame.Rect(611, 267, 173, 30), "出口平局：右", "tie_exit", style="ghost", font_size=theme.FONT_TINY
        )
        self.flee_tie_button = ui.Button(
            pygame.Rect(790, 267, 176, 30), "逃跑平局：右", "tie_flee", style="ghost", font_size=theme.FONT_TINY
        )
        self.block_sight_button = ui.Button(
            pygame.Rect(611, 304, 173, 30), "牛挡视线：关", "block_sight", style="ghost", font_size=theme.FONT_TINY
        )
        self.block_cows_button = ui.Button(
            pygame.Rect(790, 304, 176, 30), "牛互相阻挡：关", "block_cows", style="ghost", font_size=theme.FONT_TINY
        )
        self.rule_minus: List[ui.Button] = []
        self.rule_plus: List[ui.Button] = []
        for index in range(4):
            y = 350 + index * 34
            self.rule_minus.append(
                ui.Button(pygame.Rect(611, y, 34, 27), "−", f"rule:{index}:-", style="ghost")
            )
            self.rule_plus.append(
                ui.Button(pygame.Rect(770, y, 34, 27), "+", f"rule:{index}:+", style="ghost")
            )
        self.play_button = ui.Button(
            pygame.Rect(611, 531, 168, 40), "试玩", "play", style="primary", font_size=theme.FONT_H3
        )
        self.export_button = ui.Button(
            pygame.Rect(792, 531, 174, 40), "导出关卡", "export", style="default", font_size=theme.FONT_H3
        )
        self.import_button = ui.Button(
            pygame.Rect(611, 579, 168, 34), "导入关卡", "import", style="ghost"
        )
        self.clear_button = ui.Button(
            pygame.Rect(792, 579, 174, 34), "清空重来", "clear", style="ghost"
        )
        self.buttons = [
            *self.terrain_buttons,
            *self.actor_buttons,
            self.exit_button,
            self.obstacle_button,
            self.facing_button,
            self.cow_facing_button,
            self.exit_tie_button,
            self.flee_tie_button,
            self.block_sight_button,
            self.block_cows_button,
            *self.rule_minus,
            *self.rule_plus,
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
                self.model.exits.discard(cell)
                self.model.obstacles.discard(cell)

    def _paint(self, cell: Pos) -> None:
        if self.tool == TOOL_FARMER:
            if self.model.move_farmer(cell):
                self.app.sound.play("place")
            return
        if self.tool == TOOL_COW:
            if self.model.move_cow(cell):
                self.app.sound.play("place")
            return
        if self.tool == TOOL_EXIT:
            if self.model.toggle_exit(cell):
                self.app.sound.play("place")
            else:
                self._toast("出口不能放在障碍或角色脚下。")
                self.app.sound.play("error")
            return
        if self.tool == TOOL_OBSTACLE:
            if self.model.toggle_obstacle(cell):
                self.app.sound.play("place")
            else:
                self._toast("固定障碍不能放在墙或角色脚下。")
                self.app.sound.play("error")
            return
        if self.model.set_tile(cell, self.brush):
            self.app.sound.play("place")

    # ------------------------------------------------------------------
    def _action(self, action: str) -> None:
        if action.startswith("paint:"):
            self.tool = TOOL_TERRAIN
            self.brush = TileKind(action.split(":", 1)[1])
            self.app.sound.play("click")
        elif action == "actor:farmer":
            self.tool = TOOL_FARMER
            self.app.sound.play("click")
        elif action == "actor:cow":
            self.tool = TOOL_COW
            self.app.sound.play("click")
        elif action == "actor:add":
            if self.model.add_cow():
                self.app.sound.play("place")
            else:
                self._toast("最多放三头牛，或者找不到空格。")
                self.app.sound.play("error")
        elif action == "actor:remove":
            if self.model.remove_cow():
                self.app.sound.play("undo")
            else:
                self._toast("至少要留下一头牛。")
        elif action == "actor:cycle":
            self.model.cycle_active_cow()
            self.app.sound.play("click")
        elif action == "tool:exit":
            self.tool = TOOL_EXIT
            self.app.sound.play("click")
        elif action == "tool:obstacle":
            self.tool = TOOL_OBSTACLE
            self.app.sound.play("click")
        elif action == "cycle_facing":
            self.model.cycle_facing()
            self.app.sound.play("click")
        elif action == "cycle_cow_facing":
            self.model.cycle_cow_facing()
            self.app.sound.play("click")
        elif action == "tie_exit":
            self.model.cycle_exit_tiebreak()
            self.app.sound.play("click")
        elif action == "tie_flee":
            self.model.cycle_flee_tiebreak()
            self.app.sound.play("click")
        elif action == "block_sight":
            self.model.toggle_block_sight()
            self.app.sound.play("click")
        elif action == "block_cows":
            self.model.toggle_block_each_other()
            self.app.sound.play("click")
        elif action.startswith("rule:"):
            _, index_text, sign = action.split(":")
            self._change_rule(int(index_text), 1 if sign == "+" else -1)
        elif action == "play":
            self._test_play()
        elif action == "export":
            self._export()
        elif action == "import":
            self._open_import()
        elif action == "clear":
            self.model = EditorModel()
            self._toast("牧场已经清空。")

    def _change_rule(self, index: int, delta: int) -> None:
        if index == 0:
            self.model.max_turns = max(5, min(120, self.model.max_turns + delta * 5))
        elif index == 1:
            self.model.prediction_steps = max(0, min(20, self.model.prediction_steps + delta))
        elif index == 2:
            self.model.sight_range = max(-1, min(20, self.model.sight_range + delta))
        else:
            self.model.exit_sight_range = max(-1, min(20, self.model.exit_sight_range + delta))

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
        except LevelError as exc:
            self._toast(str(exc))
            self.app.sound.play("error")
            return
        result = solve_level(level, max_nodes=50_000)
        if result.solved:
            self._finish_export(level, {"status": "solved", "shortest_turns": result.turns})
            return
        if result.status == "unsolvable":
            self._toast("无法导出：求解器确认该关卡无解。请调整布局、出口或回合上限。")
            self.app.sound.play("error")
            return
        self.pending_export = (level, result.reason or "limit")
        self.modal = ui.Modal(
            "可解性验证未完成",
            "求解器在限定范围内没有找到解。\n"
            "仍然导出时，文件会标记为「未验证」，导入与试玩时会提示。",
            accent=theme.CLAY,
            badge="未验证",
            buttons=[
                ui.Button(pygame.Rect(0, 0, 128, 40), "取消", "cancel", style="ghost"),
                ui.Button(pygame.Rect(0, 0, 176, 40), "仍然导出（未验证）", "export_unverified", style="primary"),
            ],
            width=560,
            height=312,
        )

    def _finish_export(self, level, verification) -> None:
        try:
            path = export_level(level, verification=verification)
        except (LevelError, OSError) as exc:
            self._toast(f"导出失败：{exc}")
            self.app.sound.play("error")
            return
        self.exported_path = path
        self.pending_export = None
        self.modal = None
        self.app.sound.play("unlock")
        if verification.get("status") == "solved":
            self._toast(f"已导出并通过可解性验证：{path.name}")
        else:
            self._toast(f"已导出（未验证）：{path.name}")

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
                    pygame.Rect(0, 0, 368, 37),
                    path.stem[:28],
                    f"file:{index}",
                    style="ghost",
                    font_size=theme.FONT_SMALL,
                )
            )
        self._import_files = files[:5]
        cancel = ui.Button(pygame.Rect(0, 0, 120, 37), "取消", "cancel", style="ghost")
        self.import_buttons = buttons
        self.modal = ui.Modal(
            "导入关卡",
            "选择一个之前导出的关卡文件：",
            accent=theme.SKY_DEEP,
            buttons=[cancel],
            width=560,
            height=400,
        )
        y = self.modal.rect.top + 110
        for button in buttons:
            button.rect.topleft = (self.modal.rect.left + 96, y)
            y += 42
        self.modal.buttons = buttons + [cancel]

    def _modal_action(self, action: str) -> None:
        if action == "cancel":
            self.modal = None
            self.pending_export = None
            return
        if action == "export_unverified":
            if self.pending_export is not None:
                level, reason = self.pending_export
                self._finish_export(
                    level,
                    {"status": "unverified", "reason": reason},
                )
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
            self.app.sound.play("unlock")
            verification = level.extra.get("verification")
            if isinstance(verification, dict) and verification.get("status") != "solved":
                self._toast(f"已导入《{level.name}》；该关卡未通过自动可解性验证。")
            else:
                self._toast(f"已导入《{level.name}》")

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        super().update(dt)
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)
        if self.modal is not None:
            self.modal.update(self.app.mouse_pos())

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        draw_header(
            surface,
            self.fonts,
            "关卡编辑器",
            self.model.name,
            badge="编辑器",
            badge_color=theme.CLAY,
        )
        self.back_button.draw(surface, self.fonts)

        self._draw_board(surface)
        self._draw_panel(surface)
        draw_footer(
            surface,
            self.fonts,
            "左键绘制 · 右键擦除 · 出口与固定障碍在右侧选择 · 导出文件保存在 custom_levels/",
        )
        if self.toast_timer > 0 and self.toast_text:
            self._draw_toast(surface)
        if self.modal is not None:
            self.modal.draw(surface, self.fonts)

    def _draw_board(self, surface: pygame.Surface) -> None:
        frame = pygame.Rect(
            ORIGIN[0] - 14, ORIGIN[1] - 14, CELL * self.model.width + 28, CELL * self.model.height + 28
        )
        theme.soft_shadow(surface, frame, radius=26, alpha=42, offset=(0, 7))
        theme.rounded_rect(surface, frame, theme.WOOD_LIGHT, radius=26)
        theme.rounded_rect(surface, frame, theme.WOOD_DARK, radius=26, width=3)
        pygame.draw.rect(surface, theme.GRASS_DARK, frame.inflate(-8, -8), border_radius=22)

        def kind_at(row: int, col: int) -> TileKind:
            return self.model.tiles[row][col]

        draw_grid(surface, self.cache, self.model.width, self.model.height, kind_at)
        exit_sprite = self.cache.exit_tile()
        for pos in self.model.exits:
            surface.blit(exit_sprite, (ORIGIN[0] + pos[1] * CELL, ORIGIN[1] + pos[0] * CELL))
        for pos in self.model.obstacles:
            sprite = self.cache.prop("obstacle")
            surface.blit(sprite, (ORIGIN[0] + pos[1] * CELL, ORIGIN[1] + pos[0] * CELL))
        if self.hover is not None:
            rect = pygame.Rect(ORIGIN[0] + self.hover[1] * CELL, ORIGIN[1] + self.hover[0] * CELL, CELL, CELL)
            layer = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
            pygame.draw.rect(layer, (*theme.SUN, 70), layer.get_rect().inflate(-4, -4), border_radius=12)
            pygame.draw.rect(
                layer, (*theme.SUN, 200), layer.get_rect().inflate(-4, -4), width=2, border_radius=12
            )
            surface.blit(layer, rect.topleft)
        for index, (pos, facing) in enumerate(self.model.cows):
            sprite = self.cache.cow(facing)
            center = (ORIGIN[0] + pos[1] * CELL + CELL // 2, ORIGIN[1] + pos[0] * CELL + CELL // 2)
            surface.blit(sprite, sprite.get_rect(center=center))
            if index == self.model.active_cow:
                pygame.draw.circle(surface, theme.SUN, center, CELL // 2 - 3, 2)
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
        left = theme.PANEL_RECT.left + 19
        theme.draw_text(surface, self.fonts, "地形", (left, 98), theme.FONT_TINY, theme.INK_LIGHT)
        for button in self.terrain_buttons:
            button.style = (
                "primary"
                if (self.tool == TOOL_TERRAIN and button.key == f"paint:{self.brush.value}")
                else "ghost"
            )
            button.draw(surface, self.fonts)
        for button in self.actor_buttons:
            active = (
                (button.key == "actor:farmer" and self.tool == TOOL_FARMER)
                or (button.key == "actor:cow" and self.tool == TOOL_COW)
            )
            button.style = "primary" if active else "ghost"
            button.draw(surface, self.fonts)
        self.exit_button.style = "primary" if self.tool == TOOL_EXIT else "ghost"
        self.exit_button.draw(surface, self.fonts)
        self.obstacle_button.style = "primary" if self.tool == TOOL_OBSTACLE else "ghost"
        self.obstacle_button.draw(surface, self.fonts)
        active_cow = self.model.cows[self.model.active_cow] if self.model.cows else None
        self.facing_button.text = f"农夫朝向：{self.model.farmer_facing.label}"
        self.facing_button.draw(surface, self.fonts)
        cow_facing = active_cow[1] if active_cow else Direction.NORTH
        self.cow_facing_button.text = f"牛朝向：{cow_facing.label}"
        self.cow_facing_button.draw(surface, self.fonts)
        self.exit_tie_button.text = f"出口平局：{'左' if self.model.exit_tiebreak.value == 'left' else '右'}"
        self.exit_tie_button.draw(surface, self.fonts)
        self.flee_tie_button.text = f"逃跑平局：{'左' if self.model.flee_tiebreak.value == 'left' else '右'}"
        self.flee_tie_button.draw(surface, self.fonts)
        self.block_sight_button.text = f"牛挡视线：{'开' if self.model.cows_block_sight else '关'}"
        self.block_sight_button.draw(surface, self.fonts)
        self.block_cows_button.text = (
            f"牛互相阻挡：{'开' if self.model.cows_block_each_other else '关'}"
        )
        self.block_cows_button.draw(surface, self.fonts)

        rules = [
            ("回合上限", self.model.max_turns),
            ("预测步数", self.model.prediction_steps),
            ("视野距离", self.model.sight_range if self.model.sight_range >= 0 else "∞"),
            ("出口视野", self.model.exit_sight_range if self.model.exit_sight_range >= 0 else "∞"),
        ]
        for index, (label, value) in enumerate(rules):
            y = 350 + index * 34
            theme.draw_text(
                surface, self.fonts, label, (left + 40, y + 14), theme.FONT_SMALL, theme.INK,
                anchor="midleft",
            )
            theme.draw_text(
                surface, self.fonts, str(value), (left + 120, y + 14), theme.FONT_H3,
                theme.CLAY_DARK, anchor="center", bold=True,
            )
            self.rule_minus[index].draw(surface, self.fonts)
            self.rule_plus[index].draw(surface, self.fonts)

        hint = self.fonts.wrap(
            "画地形、摆农夫与牛、设置出口和视线规则；导出前会自动做可解性验证。",
            theme.FONT_SMALL,
            355,
            theme.INK_SOFT,
        )
        surface.blit(hint, (left, 483))

        for button in (self.play_button, self.export_button, self.import_button, self.clear_button):
            button.draw(surface, self.fonts)

    def _draw_toast(self, surface: pygame.Surface) -> None:
        body = self.fonts.wrap(self.toast_text, theme.FONT_SMALL, 416, theme.WHITE_WARM)
        rect = pygame.Rect(0, 0, body.get_width() + 32, body.get_height() + 19)
        rect.center = (ORIGIN[0] + CELL * 5, 77)
        theme.soft_shadow(surface, rect, radius=14, alpha=60, offset=(0, 4))
        theme.rounded_rect(surface, rect, theme.CLAY, radius=14)
        surface.blit(body, (rect.left + 20, rect.top + 12))
