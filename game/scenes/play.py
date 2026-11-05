"""The main gameplay screen: placing hay bales, running the herd, reading results."""

from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from .. import theme, ui
from ..core import Simulation
from ..models import GameStatus, Level, Pos, Rank
from ..playback import Playback
from ..render import BoardRenderer, BoardView, EffectSystem
from .base import Scene, draw_footer

RESULT_DELAYS = {
    GameStatus.WON: 1.55,
    GameStatus.LOST_LOOP: 1.35,
    GameStatus.LOST_STEPS: 0.9,
}

LOOP_COLOR = theme.SKY_DEEP


class PlayScene(Scene):
    """Renders and drives a single level attempt.

    The scene owns presentation and input only; all rules live in
    :mod:`game.core` and all persistence lives in :mod:`game.progress`.
    """

    def __init__(
        self,
        app,
        level: Level,
        *,
        mode: str = "main",
        level_number: int = 0,
        chapter: str = "",
        challenge_key: str = "",
        daily_key: str = "",
        return_to: str = "level_select",
    ) -> None:
        super().__init__(app)
        self.level = level
        self.mode = mode
        self.level_number = level_number
        self.chapter = chapter or level.group
        self.challenge_key = challenge_key
        self.daily_key = daily_key
        self.return_to = return_to

        self.renderer = BoardRenderer(self.cache, self.fonts)
        self.sim = Simulation(level)
        self.playback = Playback(self.sim, float(self.store.get_setting("speed", 1.0) or 1.0))
        self.effects = EffectSystem(bool(self.store.get_setting("low_effects", False)))
        self.show_prediction = bool(self.store.get_setting("preview", True))
        self.phase = "place"
        self.hover: Optional[Pos] = None
        self.hover_valid = True
        self.placed_order: List[Pos] = []
        self.result_timer = 0.0
        self.result_shown = False
        self.rank: Optional[Rank] = None
        self.new_record = False
        self.modal: Optional[ui.Modal] = None
        self.toast_text = ""
        self.toast_timer = 0.0
        self.loop_events = 0
        self.tutorial = None
        self._prediction_cache: Tuple = ()
        self._prediction_key = None
        self.buttons: List[ui.Button] = []
        self._build_buttons()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _build_buttons(self) -> None:
        self.start_button = ui.Button(
            pygame.Rect(764, 540, 210, 56), "开始游戏", "start", style="primary", font_size=theme.FONT_H3
        )
        self.secondary_button = ui.Button(
            pygame.Rect(990, 540, 218, 56), "撤销一步", "undo", style="default", font_size=theme.FONT_H3
        )
        self.restart_button = ui.Button(
            pygame.Rect(764, 606, 210, 48), "重开", "restart", style="ghost"
        )
        self.predict_button = ui.Button(
            pygame.Rect(990, 606, 218, 48), "预测：开", "predict", style="ghost"
        )
        self.speed_buttons = [
            ui.Button(pygame.Rect(764 + index * 152, 668, 140, 40), label, f"speed:{value}", style="ghost", font_size=theme.FONT_SMALL)
            for index, (label, value) in enumerate((("0.5x", 0.5), ("1x", 1.0), ("2x", 2.0)))
        ]
        self.skip_button = ui.Button(
            pygame.Rect(764, 720, 444, 44), "跳过本课", "skip", style="ghost", font_size=theme.FONT_SMALL
        )
        self.buttons = [
            self.start_button,
            self.secondary_button,
            self.restart_button,
            self.predict_button,
            *self.speed_buttons,
        ]
        if self.mode == "tutorial":
            self.buttons.append(self.skip_button)
        self.back_button = ui.Button(
            pygame.Rect(theme.WINDOW_WIDTH - 190, 36, 130, 52), "返回", "back", style="ghost"
        )

    def on_enter(self) -> None:
        if self.mode == "tutorial" and self.app.book is not None:
            self.app.book.begin_lesson(self.chapter, self.level.tutorial_id or self.level.level_id)
            from ..tutorial import TutorialSession

            self.tutorial = TutorialSession(self.level)
            self.tutorial.start()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _refresh_buttons(self) -> None:
        status = self.sim.status
        if status.is_finished:
            self.start_button.text = "再玩一次"
            self.start_button.enabled = True
            self.secondary_button.text = "返回关卡"
            self.secondary_button.enabled = True
        elif self.phase == "place":
            self.start_button.text = "开始游戏"
            self.start_button.enabled = True
            self.secondary_button.text = "撤销一步"
            self.secondary_button.enabled = bool(self.placed_order)
        elif self.playback.running:
            self.start_button.text = "暂停"
            self.secondary_button.text = "单步"
            self.secondary_button.enabled = True
        else:
            self.start_button.text = "继续"
            self.secondary_button.text = "单步"
            self.secondary_button.enabled = True
        self.restart_button.enabled = True
        self.predict_button.text = "预测：开" if self.show_prediction else "预测：关"
        for button in self.speed_buttons:
            value = float(button.key.split(":")[1])
            button.style = "primary" if abs(value - self.playback.speed) < 0.01 else "ghost"

    def _cell_at(self, pos: Tuple[int, int]) -> Optional[Pos]:
        local_x = pos[0] - theme.BOARD_ORIGIN[0]
        local_y = pos[1] - theme.BOARD_ORIGIN[1]
        if not (0 <= local_x < theme.CELL_SIZE * self.level.width):
            return None
        if not (0 <= local_y < theme.CELL_SIZE * self.level.height):
            return None
        return (local_y // theme.CELL_SIZE, local_x // theme.CELL_SIZE)

    def _prediction(self):
        key = (self.sim.state_key(), self.show_prediction)
        if key != self._prediction_key:
            self._prediction_key = key
            self._prediction_cache = tuple(self.sim.predict(3)) if self.show_prediction else ()
        return self._prediction_cache

    def _toast(self, text: str, duration: float = 2.2) -> None:
        self.toast_text = text
        self.toast_timer = duration

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.modal is not None:
            action = self.modal.handle_event(event)
            if action:
                self._modal_action(action)
            return

        if self.back_button.handle_event(event):
            self._leave()
            return

        for button in self.buttons:
            action = button.handle_event(event)
            if action:
                self._button_action(action)
                return

        if event.type == pygame.KEYDOWN:
            self._handle_key(event)
            return

        if event.type == pygame.MOUSEMOTION:
            cell = self._cell_at(event.pos)
            self.hover = cell
            if cell is not None and self.phase == "place" and self.sim.status is GameStatus.READY:
                self.hover_valid = self.sim.can_place_obstacle(cell).ok or cell in self.sim.obstacles
            else:
                self.hover_valid = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            cell = self._cell_at(event.pos)
            if cell is None or self.sim.status is not GameStatus.READY:
                return
            if event.button == 1:
                if cell in self.sim.obstacles:
                    self._remove_obstacle(cell)
                else:
                    self._place_obstacle(cell)
            elif event.button == 3:
                self._remove_obstacle(cell)

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            self._leave()
        elif event.key == pygame.K_SPACE:
            self._button_action("start" if self.phase == "place" else "pause")
        elif event.key in (pygame.K_s, pygame.K_RIGHT):
            self._button_action("step")
        elif event.key == pygame.K_r:
            self._button_action("restart")
        elif event.key == pygame.K_p:
            self._button_action("predict")
        elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
            speed = {pygame.K_1: 0.5, pygame.K_2: 1.0, pygame.K_3: 2.0}[event.key]
            self._set_speed(speed)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _button_action(self, action: str) -> None:
        if action == "start":
            self._handle_start()
        elif action == "pause":
            if self.playback.finished:
                return
            self.playback.toggle_pause()
            self.app.sound.play("paused" if not self.playback.running else "click")
            self._refresh_buttons()
        elif action == "step":
            self._handle_secondary()
        elif action == "undo":
            self._undo()
        elif action == "restart":
            self._restart()
        elif action == "predict":
            self.show_prediction = not self.show_prediction
            self.store.set_setting("preview", self.show_prediction)
            self._refresh_buttons()
        elif action.startswith("speed:"):
            self._set_speed(float(action.split(":")[1]))
        elif action == "skip":
            self._skip_tutorial()

    def _handle_start(self) -> None:
        if self.sim.status.is_finished:
            self._restart(clear_obstacles=True)
            return
        if self.phase == "place":
            required = int(self.level.extra.get("require_obstacle", 0) or 0)
            if self.sim.obstacle_count < required:
                self._toast(f"试着先放 {required} 个干草垛，再开始吧。")
                self.app.sound.play("error")
                return
            self.phase = "run"
            if self.tutorial is not None:
                self.tutorial.notify("run")
            self.playback.start()
            self.app.sound.play("start")
        else:
            self.playback.toggle_pause()
            self.app.sound.play("paused" if not self.playback.running else "click")
        self._refresh_buttons()

    def _handle_secondary(self) -> None:
        if self.sim.status.is_finished:
            self._leave()
            return
        if self.phase == "place":
            self._undo()
            return
        else:
            self.playback.step_once()
            self.app.sound.play("step")
            self._after_tick()
            self._refresh_buttons()

    def _set_speed(self, speed: float) -> None:
        self.playback.set_speed(speed)
        self.store.set_setting("speed", speed)
        self._refresh_buttons()

    def _place_obstacle(self, cell: Pos) -> None:
        result = self.sim.place_obstacle(cell)
        if result.ok:
            self.placed_order.append(cell)
            self.app.sound.play("place")
            if self.tutorial is not None:
                self.tutorial.notify("place")
        else:
            self._toast(result.message)
            self.app.sound.play("error")
        self._refresh_buttons()

    def _remove_obstacle(self, cell: Pos) -> None:
        if self.sim.remove_obstacle(cell):
            if cell in self.placed_order:
                self.placed_order.remove(cell)
            self.app.sound.play("undo")
            if self.tutorial is not None:
                self.tutorial.notify("remove")
        self._refresh_buttons()

    def _undo(self) -> None:
        if self.phase != "place" or self.sim.status is not GameStatus.READY:
            return
        while self.placed_order:
            cell = self.placed_order.pop()
            if self.sim.remove_obstacle(cell):
                self.app.sound.play("undo")
                if self.tutorial is not None:
                    self.tutorial.notify("remove")
                break
        self._refresh_buttons()

    def _restart(self, clear_obstacles: bool = False) -> None:
        obstacles = set() if clear_obstacles else self.sim.obstacles
        speed = self.playback.speed
        self.sim = Simulation(self.level, obstacles)
        self.playback = Playback(self.sim, speed)
        self.effects = EffectSystem(bool(self.store.get_setting("low_effects", False)))
        self.phase = "place"
        self.placed_order = [pos for pos in self.placed_order if pos in obstacles]
        self.result_timer = 0.0
        self.result_shown = False
        self.modal = None
        self.rank = None
        self.new_record = False
        self._prediction_key = None
        if self.mode == "tutorial":
            from ..tutorial import TutorialSession

            self.tutorial = TutorialSession(self.level)
            self.tutorial.start()
        self._refresh_buttons()

    def _skip_tutorial(self) -> None:
        if self.mode != "tutorial" or self.app.book is None:
            return
        self.app.book.skip_lesson(self.chapter, self.level.tutorial_id or self.level.level_id)
        self.app.sound.play("click")
        self.app.open_tutorial_chapter(self.chapter)

    def _leave(self) -> None:
        if self.mode == "tutorial":
            self.app.open_tutorial_chapter(self.chapter)
        elif self.mode == "editor":
            self.app.open_scene("editor")
        elif self.return_to == "challenge":
            self.app.open_scene("challenge")
        elif self.return_to == "daily":
            self.app.open_scene("daily")
        else:
            self.app.open_scene("level_select")

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        super().update(dt)
        if self.modal is not None:
            self.modal.update(pygame.mouse.get_pos())
            return
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)
        self.effects.update(dt)
        if not self.playback.finished:
            stepped = self.playback.update(dt)
            if stepped:
                self._after_tick()
        if self.playback.finished and self.phase != "result":
            self._finish()
        if self.phase == "result" and not self.result_shown:
            self.result_timer += dt
            delay = RESULT_DELAYS.get(self.sim.status, 1.0)
            if self.result_timer >= delay:
                self._show_result()

    def _after_tick(self) -> None:
        tick = self.sim.last_tick
        if tick is None:
            return
        if self.tutorial is not None and not tick.status.is_finished:
            self.tutorial.notify("step")
        self._refresh_buttons()

    def _finish(self) -> None:
        self.phase = "result"
        self.result_timer = 0.0
        status = self.sim.status
        self.rank = self.level.rank_for(self.sim.steps) if status is GameStatus.WON else None
        center = (
            theme.BOARD_ORIGIN[0] + (self.sim.farmer.pos[1] + 0.5) * theme.CELL_SIZE,
            theme.BOARD_ORIGIN[1] + (self.sim.farmer.pos[0] + 0.5) * theme.CELL_SIZE,
        )
        if status is GameStatus.WON:
            self.effects.burst_petals(center, 26 if not self.effects.low_effects else 0)
            self.effects.ring(center, theme.SUN, 120, 0.9)
            self.effects.flying_hat(center)
            self.app.sound.play("win")
            self._record_win()
            if self.tutorial is not None:
                self.tutorial.notify("win")
        elif status is GameStatus.LOST_LOOP:
            self.loop_events += 1
            self.effects.loop_swirl(center)
            self.app.sound.play("loop")
            if self.tutorial is not None:
                self.tutorial.notify("fail")
        else:
            self.app.sound.play("lose")
            if self.tutorial is not None:
                self.tutorial.notify("fail")
        self._refresh_buttons()

    def _record_win(self) -> None:
        steps = self.sim.steps
        rank = self.level.rank_for(steps)
        obstacles_used = self.sim.obstacle_count
        if self.mode == "main":
            self.new_record = self.store.record_main_clear(
                self.level.level_id, steps, rank, obstacles_used
            )
            self.app.on_level_cleared(self.level, self.sim, rank)
        elif self.mode == "tutorial" and self.app.book is not None:
            self.new_record = self.app.book.complete_lesson(
                self.chapter, self.level.tutorial_id or self.level.level_id
            )
        elif self.mode == "challenge":
            self.new_record = self.store.record_challenge_best(self.challenge_key, steps)
            self.app.on_level_cleared(self.level, self.sim, rank)
        elif self.mode == "daily" and self.daily_key:
            self.new_record = self.store.record_daily(
                self.daily_key,
                {
                    "cleared": True,
                    "steps": steps,
                    "rank": rank.value,
                    "level_id": self.level.level_id,
                },
            )

    # ------------------------------------------------------------------
    # Result dialogs
    # ------------------------------------------------------------------
    def _show_result(self) -> None:
        self.result_shown = True
        status = self.sim.status
        if status is GameStatus.WON:
            self._show_win_modal()
        elif status is GameStatus.LOST_LOOP:
            self.modal = ui.Modal(
                "时间闭环了",
                "农夫和牛回到了完全相同的状态，时间绕成了一个圈。\n"
                "试着调整干草垛的位置，让他们的节奏错开一点。",
                accent=LOOP_COLOR,
                buttons=[
                    ui.Button(pygame.Rect(0, 0, 160, 50), "再试一次", "retry", style="primary"),
                    ui.Button(pygame.Rect(0, 0, 150, 50), "返回", "leave", style="ghost"),
                ],
                width=620,
                height=330,
            )
            self.app.sound.play("lose")
        else:
            self.modal = ui.Modal(
                "步数用尽",
                f"牛还没有被抓住，步数已经走完了 {self.level.step_limit} 步。\n"
                "先看看前 3 步的预测虚线，再决定把干草垛放在哪里。",
                accent=theme.CLAY,
                buttons=[
                    ui.Button(pygame.Rect(0, 0, 160, 50), "再试一次", "retry", style="primary"),
                    ui.Button(pygame.Rect(0, 0, 150, 50), "返回", "leave", style="ghost"),
                ],
                width=620,
                height=330,
            )

    def _show_win_modal(self) -> None:
        steps = self.sim.steps
        rank = self.rank or self.level.rank_for(steps)
        if self.mode == "tutorial":
            body = f"用了 {steps} 步完成本课。\n{rank.comment}"
            self.modal = ui.Modal(
                "教程完成",
                body,
                accent=theme.LEAF,
                badge="教程",
                buttons=[
                    ui.Button(pygame.Rect(0, 0, 170, 50), "下一课", "next_lesson", style="primary"),
                    ui.Button(pygame.Rect(0, 0, 150, 50), "重玩本课", "retry", style="ghost"),
                    ui.Button(pygame.Rect(0, 0, 150, 50), "返回章节", "leave", style="ghost"),
                ],
                width=680,
                height=360,
            )
            return
        record_text = "新的最好成绩！" if self.new_record else ""
        body = (
            f"用了 {steps} 步，放下了 {self.sim.obstacle_count} 个干草垛。\n"
            f"{rank.comment}\n{record_text}"
        )
        buttons = [ui.Button(pygame.Rect(0, 0, 150, 50), "再玩一次", "retry", style="ghost")]
        if self.mode == "main" and self.level_number < len(self.app.levels):
            buttons.append(
                ui.Button(pygame.Rect(0, 0, 150, 50), "下一关", "next_level", style="primary")
            )
        buttons.append(ui.Button(pygame.Rect(0, 0, 150, 50), "返回", "leave", style="ghost"))
        self.modal = ui.Modal(
            "抓到啦！",
            body,
            accent=theme.SUN,
            badge=f"评价 {rank.value}",
            buttons=buttons,
            width=680,
            height=380,
        )
        self.app.sound.play("unlock")

    def _modal_action(self, action: str) -> None:
        self.app.sound.play("click")
        self.modal = None
        if action in ("retry", "dismiss"):
            self._restart(clear_obstacles=True)
        elif action == "leave":
            self._leave()
        elif action == "next_level":
            if self.level_number < len(self.app.levels):
                self.app.start_level(self.app.levels[self.level_number], mode="main")
            else:
                self.app.open_scene("level_select")
        elif action == "next_lesson":
            self.app.open_next_tutorial_lesson(self.chapter)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        self._draw_header(surface)
        self._draw_board(surface)
        self._draw_panel(surface)
        self._draw_footer(surface)
        self.back_button.draw(surface, self.fonts)
        if self.toast_timer > 0 and self.toast_text:
            self._draw_toast(surface)
        if self.modal is not None:
            self.modal.draw(surface, self.fonts)

    def _draw_background(self, surface: pygame.Surface) -> None:
        theme.vertical_gradient(
            surface, pygame.Rect(0, 0, theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT), theme.CREAM, theme.CREAM_DARK
        )
        layer = pygame.Surface((theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(layer, (*theme.GRASS_LIGHT, 34), (90, 760), 240)
        pygame.draw.circle(layer, (*theme.SKY, 22), (1220, 120), 220)
        surface.blit(layer, (0, 0))

    def _draw_header(self, surface: pygame.Surface) -> None:
        title = (
            f"第 {self.level_number:02d} 关 · {self.level.name}"
            if self.mode == "main"
            else self.level.name
        )
        theme.draw_text(surface, self.fonts, title, (62, 34), theme.FONT_H1, theme.INK, bold=True)
        badge = "教程" if self.mode == "tutorial" else "主线"
        badge_color = theme.SKY_DEEP if self.mode == "tutorial" else theme.LEAF
        width = self.fonts.size_of(title, theme.FONT_H1, True)[0]
        ui.draw_pill(surface, self.fonts, badge, (62 + width + 62, 58), badge_color)
        status_text = {
            "place": "布置阶段",
            "run": "追牛中" if self.playback.running else "已暂停",
            "result": "本局结束",
        }[self.phase]
        ui.draw_pill(surface, self.fonts, status_text, (62 + width + 160, 58), theme.CREAM_DARK, text_color=theme.INK_SOFT)
        pygame.draw.line(surface, theme.PANEL_BORDER, (60, 104), (1220, 104), 2)

    def _draw_board(self, surface: pygame.Surface) -> None:
        view = BoardView(
            level=self.level,
            sim=self.sim,
            playback=self.playback,
            hover=self.hover if self.phase == "place" else None,
            hover_valid=self.hover_valid,
            placement_mode=self.phase == "place" and self.sim.status is GameStatus.READY,
            show_prediction=self.show_prediction and not self.sim.status.is_finished,
            prediction=self._prediction(),
            effects=self.effects,
            pulse=self.time,
            highlight=self._highlight_cell(),
        )
        self.renderer.draw(surface, view)

    def _highlight_cell(self) -> Optional[Pos]:
        raw = self.level.extra.get("highlight")
        if not raw:
            return None
        try:
            return (int(raw[0]), int(raw[1]))
        except (TypeError, ValueError, IndexError):
            return None

    def _draw_panel(self, surface: pygame.Surface) -> None:
        theme.panel(surface, theme.PANEL_RECT)
        inner_left = theme.PANEL_RECT.left + 24
        inner_width = theme.PANEL_RECT.width - 48
        y = theme.PANEL_RECT.top + 20

        label = (
            f"第 {self.level_number:02d} 关" if self.mode == "main" else "本课目标"
        )
        theme.draw_text(surface, self.fonts, label, (inner_left, y), theme.FONT_SMALL, theme.INK_LIGHT)
        y += 26
        theme.draw_text(surface, self.fonts, self.level.name, (inner_left, y), theme.FONT_H2, theme.INK, bold=True)
        y += 46
        ui.draw_divider(surface, y, inner_left, inner_width)
        y += 18

        hint_text = self.level.goal_text or self.level.hint or self.level.description
        if self.tutorial is not None and self.tutorial.active:
            hint_text = None
        if hint_text:
            wrapped = self.fonts.wrap(hint_text, theme.FONT_SMALL, inner_width, theme.INK_SOFT)
            surface.blit(wrapped, (inner_left, y))
            y += wrapped.get_height() + 14

        # stat row
        themes = [
            ("步数", f"{self.sim.steps} / {self.level.step_limit}", theme.LEAF_DARK),
            ("障碍", f"{self.sim.obstacle_count} / {self.level.obstacle_limit}", theme.CLAY_DARK),
        ]
        box_w = (inner_width - 14) // 2
        for index, (title, value, color) in enumerate(themes):
            box = pygame.Rect(inner_left + index * (box_w + 14), y, box_w, 72)
            theme.rounded_rect(surface, box, theme.CREAM, radius=14)
            theme.rounded_rect(surface, box, theme.PANEL_BORDER, radius=14, width=2)
            theme.draw_text(
                surface, self.fonts, title, (box.left + 14, box.top + 10), theme.FONT_TINY, theme.INK_LIGHT
            )
            theme.draw_text(
                surface, self.fonts, value, (box.left + 14, box.top + 30), theme.FONT_H3, color, bold=True
            )
        y += 88

        # rating ladder
        ladder = (
            f"S ≤ {self.level.s_threshold} 步   "
            f"A ≤ {self.level.a_threshold}   "
            f"B ≤ {self.level.b_threshold}"
        )
        theme.draw_text(surface, self.fonts, ladder, (inner_left, y), theme.FONT_TINY, theme.INK_LIGHT)
        y += 30

        if self.tutorial is not None and self.tutorial.active:
            self._draw_tutorial_box(surface, inner_left, y, inner_width)
        elif self.phase == "place":
            helper = self.fonts.wrap(
                "点击草地放下干草垛，点击干草垛可以收回。开始后就不能再布置了。",
                theme.FONT_SMALL,
                inner_width,
                theme.INK_LIGHT,
            )
            surface.blit(helper, (inner_left, y))

        for button in self.buttons:
            if button is self.skip_button:
                continue
            button.draw(surface, self.fonts)
        if self.mode == "tutorial":
            self.skip_button.draw(surface, self.fonts)

    def _draw_tutorial_box(self, surface: pygame.Surface, x: int, y: int, width: int) -> None:
        box = pygame.Rect(x, y, width, 148)
        theme.rounded_rect(surface, box, theme.SKY_PALE, radius=16)
        theme.rounded_rect(surface, box, theme.SKY_DEEP, radius=16, width=2)
        ui.draw_pill(surface, self.fonts, "提示", (box.left + 44, box.top + 22), theme.SKY_DEEP)
        text = self.fonts.wrap(self.tutorial.active or "", theme.FONT_SMALL, width - 48, theme.INK)
        surface.blit(text, (box.left + 20, box.top + 44))
        ratio = self.tutorial.progress_ratio
        bar = pygame.Rect(box.left + 20, box.bottom - 20, width - 40, 8)
        theme.rounded_rect(surface, bar, theme.CREAM_DARK, radius=4)
        filled = pygame.Rect(bar.left, bar.top, int(bar.width * ratio), bar.height)
        theme.rounded_rect(surface, filled, theme.SKY_DEEP, radius=4)

    def _draw_footer(self, surface: pygame.Surface) -> None:
        if self.phase == "place":
            text = "点击草地放置干草垛 · 右键收回 · 空格开始 · R 重开"
        else:
            text = "空格 暂停/继续 · S 单步 · R 重开 · 1/2/3 切换速度 · P 预测"
        draw_footer(surface, self.fonts, text)
        if self.show_prediction:
            theme.draw_text(
                surface,
                self.fonts,
                "虚线 = 接下来 3 步的预测",
                (theme.BOARD_ORIGIN[0], 776),
                theme.FONT_TINY,
                theme.INK_LIGHT,
            )

    def _draw_toast(self, surface: pygame.Surface) -> None:
        body = self.fonts.wrap(self.toast_text, theme.FONT_SMALL, 420, theme.WHITE_WARM)
        rect = pygame.Rect(0, 0, body.get_width() + 40, body.get_height() + 24)
        rect.center = (theme.BOARD_ORIGIN[0] + theme.BOARD_SIZE // 2, 96)
        theme.soft_shadow(surface, rect, radius=14, alpha=60, offset=(0, 4))
        theme.rounded_rect(surface, rect, theme.CLAY, radius=14)
        surface.blit(body, (rect.left + 20, rect.top + 12))
