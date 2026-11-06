"""The main gameplay screen: laying out hay, chasing the herd, reading results.

The scene owns presentation and input only.  Every rule lives in
:mod:`game.core`; persistence lives in :mod:`game.progress`.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from .. import theme, ui
from ..animation import TurnAnimator
from ..core import Simulation
from ..models import Direction, GameStatus, Level, Pos, Rank
from ..render import BoardRenderer, BoardView, EffectSystem
from .base import Scene, draw_footer

RESULT_DELAY = 0.95
LOOP_COLOR = theme.SKY_DEEP


class PlayScene(Scene):
    """Renders and drives one turn-based attempt."""

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
        self.animator = TurnAnimator()
        self.effects = EffectSystem(bool(self.store.get_setting("low_effects", False)))
        self.show_prediction = bool(self.store.get_setting("preview", True))
        if level.extra.get("require_prediction"):
            self.show_prediction = False
        self.phase = "place"
        self.hover: Optional[Pos] = None
        self.hover_valid = True
        self.result_timer = 0.0
        self.result_shown = False
        self.rank: Optional[Rank] = None
        self.new_record = False
        self.modal: Optional[ui.Modal] = None
        self.toast_text = ""
        self.toast_timer = 0.0
        self.loop_events = 0
        self.trail_farmer: List[Pos] = []
        self.trail_cows: List[List[Pos]] = []
        self.undo_performed = False
        self.prediction_used = self.show_prediction
        self.tutorial = None
        self._prediction_cache: Tuple = ()
        self._prediction_key = None
        self.buttons: List[ui.Button] = []
        self._seed_trails()
        self._build_buttons()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _build_buttons(self) -> None:
        self.undo_button = ui.Button(
            pygame.Rect(356, 112, 108, 44), "撤销 U", "undo", style="ghost", font_size=theme.FONT_TINY
        )
        self.restart_button = ui.Button(
            pygame.Rect(472, 112, 108, 44), "重开 R", "restart", style="ghost", font_size=theme.FONT_TINY
        )
        self.predict_button = ui.Button(
            pygame.Rect(588, 112, 122, 44), "预测 开", "predict", style="ghost", font_size=theme.FONT_TINY
        )
        self.start_button = ui.Button(
            pygame.Rect(764, 590, 444, 54),
            "开始追逐",
            "start",
            style="primary",
            font_size=theme.FONT_H3,
        )
        self.skip_button = ui.Button(
            pygame.Rect(764, 664, 444, 40),
            "跳过本课",
            "skip",
            style="ghost",
            font_size=theme.FONT_SMALL,
        )
        self.buttons = [
            self.undo_button,
            self.restart_button,
            self.predict_button,
            self.start_button,
        ]
        if self.mode == "tutorial":
            self.buttons.append(self.skip_button)
        self.back_button = ui.Button(
            pygame.Rect(theme.WINDOW_WIDTH - 190, 36, 130, 52), "返回", "back", style="ghost"
        )

    def on_enter(self) -> None:
        if self.mode == "tutorial" and self.app.book is not None:
            self.app.book.begin_lesson(
                self.chapter, self.level.tutorial_id or self.level.level_id
            )
            from ..tutorial import TutorialSession

            self.tutorial = TutorialSession(self.level)
            self.tutorial.start()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _sync_phase(self) -> None:
        if self.sim.status is GameStatus.READY:
            self.phase = "place"
        elif self.sim.status.is_finished:
            self.phase = "result"
        else:
            self.phase = "run"

    def _refresh_buttons(self) -> None:
        self._sync_phase()
        self.undo_button.enabled = self.sim.can_undo and not self.animator.busy
        self.restart_button.enabled = True
        self.predict_button.enabled = self.level.prediction_steps > 0
        self.predict_button.text = "预测 开" if self.show_prediction else "预测 关"
        if self.phase == "place":
            self.start_button.text = "开始追逐"
        elif self.phase == "result":
            self.start_button.text = "再玩一次"
        else:
            self.start_button.text = "重新布置"

    def _cell_at(self, pos: Tuple[int, int]) -> Optional[Pos]:
        local_x = pos[0] - theme.BOARD_ORIGIN[0]
        local_y = pos[1] - theme.BOARD_ORIGIN[1]
        if not (0 <= local_x < theme.CELL_SIZE * self.level.width):
            return None
        if not (0 <= local_y < theme.CELL_SIZE * self.level.height):
            return None
        return (local_y // theme.CELL_SIZE, local_x // theme.CELL_SIZE)

    def _seed_trails(self) -> None:
        self.trail_farmer = [self.sim.farmer.pos]
        self.trail_cows = [[cow.pos] for cow in self.sim.cows]

    def _prediction(self):
        count = self.level.prediction_steps
        key = (self.sim.state_key(), self.show_prediction, count)
        if key != self._prediction_key:
            self._prediction_key = key
            self._prediction_cache = (
                tuple(self.sim.predict(count)) if self.show_prediction else ()
            )
        return self._prediction_cache

    def _toast(self, text: str, duration: float = 2.2) -> None:
        self.toast_text = text
        self.toast_timer = duration

    def _tutorial_event(self, event: str) -> None:
        if self.tutorial is not None:
            self.tutorial.notify(event)

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
            if cell is not None and self.phase == "place":
                self.hover_valid = (
                    cell not in self.sim.obstacles and self.sim.can_place_obstacle(cell).ok
                )
            else:
                self.hover_valid = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            cell = self._cell_at(event.pos)
            if cell is None or self.phase != "place":
                return
            if event.button == 1:
                if cell in self.sim.obstacles:
                    self._remove_at(cell)
                else:
                    self._place_at(cell)
            elif event.button == 3:
                self._remove_at(cell)

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            self._leave()
            return
        if event.key == pygame.K_r:
            self._restart()
            return
        if event.key == pygame.K_u:
            self._undo()
            return
        if event.key == pygame.K_p:
            self._toggle_prediction()
            return
        if self.phase == "place" and event.key == pygame.K_SPACE:
            self._start_run()
            return
        if self.phase != "run" or self.animator.busy:
            return
        mapping = {
            pygame.K_UP: Direction.NORTH,
            pygame.K_w: Direction.NORTH,
            pygame.K_RIGHT: Direction.EAST,
            pygame.K_d: Direction.EAST,
            pygame.K_DOWN: Direction.SOUTH,
            pygame.K_s: Direction.SOUTH,
            pygame.K_LEFT: Direction.WEST,
            pygame.K_a: Direction.WEST,
        }
        if event.key == pygame.K_SPACE:
            self._take_turn(None)
        elif event.key in mapping:
            self._take_turn(mapping[event.key])

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _button_action(self, action: str) -> None:
        if action == "start":
            if self.sim.status.is_finished or self.phase == "run":
                self._restart()
            else:
                self._start_run()
        elif action == "undo":
            self._undo()
        elif action == "restart":
            self._restart()
        elif action == "predict":
            self._toggle_prediction()
        elif action == "skip":
            self._skip_tutorial()

    def _start_run(self) -> None:
        if self.sim.status is not GameStatus.READY:
            return
        required = int(self.level.extra.get("require_obstacle", 0) or 0)
        if self.sim.obstacle_count < required:
            self._toast(f"试着先放 {required} 个干草垛，再开始吧。")
            self.app.sound.play("error")
            return
        if self.level.extra.get("require_undo") and not self.undo_performed:
            self._toast("先放一捆干草，再把它收回来试试。")
            self.app.sound.play("error")
            return
        if self.level.extra.get("require_prediction") and not self.prediction_used:
            self._toast("先按 P 打开路径预测，看看牛会往哪里走。")
            self.app.sound.play("error")
            return
        self.sim.start()
        self.phase = "run"
        self._tutorial_event("run")
        self.app.sound.play("start")
        self._refresh_buttons()

    def _take_turn(self, direction: Optional[Direction]) -> None:
        if self.phase != "run" or self.animator.busy:
            return
        result = self.sim.order(direction)
        if result.blocked:
            self._toast(result.message or "这一下不算回合。")
            self.app.sound.play("error")
            self._tutorial_event("blocked")
            self._refresh_buttons()
            return
        self.animator.play(result)
        self.trail_farmer.append(self.sim.farmer.pos)
        for index, cow in enumerate(self.sim.cows):
            if index < len(self.trail_cows):
                self.trail_cows[index].append(cow.pos)
        self._tutorial_event("wait" if direction is None else "move")
        if result.loop_hint:
            self.loop_events += 1
            self._toast("牛进入了循环。它还会继续走，你可以换个方向或去拦它。", 2.8)
            self.app.sound.play("loop")
            self._tutorial_event("loop")
        if result.status.is_finished:
            self._begin_result()
        else:
            self._tutorial_event("step")
        self._refresh_buttons()

    def _begin_result(self) -> None:
        if self.phase == "result":
            return
        self.phase = "result"
        self.result_timer = 0.0
        self.result_shown = False
        status = self.sim.status
        self.rank = self.level.rank_for(self.sim.turns) if status is GameStatus.WON else None
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
            self._tutorial_event("win")
        else:
            self.app.sound.play("lose")
            self._tutorial_event("fail")
        self._refresh_buttons()

    def _record_win(self) -> None:
        turns = self.sim.turns
        rank = self.level.rank_for(turns)
        obstacles_used = self.sim.obstacle_count
        if self.mode == "main":
            self.new_record = self.store.record_main_clear(
                self.level.level_id, turns, rank, obstacles_used
            )
            self.app.on_level_cleared(
                self.level, self.sim, rank, loops=self.loop_events, mode="main"
            )
            unlocked = self.app.achievements.newly_unlocked
            if unlocked:
                self._toast(f"成就解锁：{unlocked[-1].name}", 3.0)
        elif self.mode == "tutorial" and self.app.book is not None:
            self.new_record = self.app.book.complete_lesson(
                self.chapter, self.level.tutorial_id or self.level.level_id
            )
        elif self.mode == "challenge":
            self.new_record = self.store.record_challenge_best(self.challenge_key, turns)
            self.app.on_level_cleared(
                self.level, self.sim, rank, loops=self.loop_events, mode="challenge"
            )
            unlocked = self.app.achievements.newly_unlocked
            if unlocked:
                self._toast(f"成就解锁：{unlocked[-1].name}", 3.0)
        elif self.mode == "daily" and self.daily_key:
            self.new_record = self.store.record_daily(
                self.daily_key,
                {
                    "cleared": True,
                    "turns": turns,
                    "rank": rank.value,
                    "level_id": self.level.level_id,
                },
            )

    def _undo(self) -> None:
        if self.animator.busy:
            return
        if not self.sim.undo():
            self._toast("没有可以撤销的步骤了。")
            self.app.sound.play("error")
            return
        self.undo_performed = True
        self.animator.clear()
        self.modal = None
        self.result_shown = False
        self.result_timer = 0.0
        self.rank = None
        self.new_record = False
        self._seed_trails()
        self._sync_phase()
        self._tutorial_event("undo")
        self.app.sound.play("undo")
        if self.sim.status is GameStatus.READY:
            self._toast("已撤销到布置阶段。")
        else:
            self._toast(f"已撤销，回到第 {self.sim.turns} 回合。")
        self._refresh_buttons()

    def _restart(self) -> None:
        self.sim.reset()
        self.animator.clear()
        self.modal = None
        self.result_shown = False
        self.result_timer = 0.0
        self.rank = None
        self.new_record = False
        self.undo_performed = False
        self.loop_events = 0
        self._seed_trails()
        self._sync_phase()
        if self.mode == "tutorial":
            from ..tutorial import TutorialSession

            self.tutorial = TutorialSession(self.level)
            self.tutorial.start()
        self.app.sound.play("click")
        self._refresh_buttons()

    def _toggle_prediction(self) -> None:
        if self.level.prediction_steps <= 0:
            self._toast("这一关没有开启路径预测。")
            self.app.sound.play("error")
            return
        self.show_prediction = not self.show_prediction
        self.prediction_used = self.prediction_used or self.show_prediction
        self.store.set_setting("preview", self.show_prediction)
        self._tutorial_event("predict")
        self.app.sound.play("click")
        self._refresh_buttons()

    def _place_at(self, cell: Pos) -> None:
        result = self.sim.place_obstacle(cell)
        if result.ok:
            self.app.sound.play("place")
            self._tutorial_event("place")
            self.hover_valid = cell not in self.sim.obstacles
        else:
            self._toast(result.message)
            self.app.sound.play("error")
        self._refresh_buttons()

    def _remove_at(self, cell: Pos) -> None:
        if self.sim.remove_obstacle(cell):
            self.undo_performed = True
            self.app.sound.play("undo")
            self._tutorial_event("remove")
        if self.phase == "place":
            self.hover_valid = self.sim.can_place_obstacle(cell).ok
        self._refresh_buttons()

    def _skip_tutorial(self) -> None:
        if self.mode != "tutorial" or self.app.book is None:
            return
        self.app.book.skip_lesson(
            self.chapter, self.level.tutorial_id or self.level.level_id
        )
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
        was_busy = self.animator.busy
        self.animator.update(dt)
        if was_busy and not self.animator.busy:
            self._refresh_buttons()
        self.effects.update(dt)
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)
        if self.modal is not None:
            self.modal.update(pygame.mouse.get_pos())
            return
        if self.phase == "result" and not self.result_shown:
            self.result_timer += dt
            if self.result_timer >= RESULT_DELAY:
                self._show_result()

    # ------------------------------------------------------------------
    # Result dialogs
    # ------------------------------------------------------------------
    def _show_result(self) -> None:
        self.result_shown = True
        self._refresh_buttons()
        if self.sim.status is GameStatus.WON:
            self._show_win_modal()
            return
        remaining = len(self.sim.cows) - self.sim.penned_count
        if self.level.is_pen_level:
            detail = f"还有 {remaining} 头牛没有进围栏。"
        else:
            detail = "牛还没有被抓住。"
        self.modal = ui.Modal(
            "回合用尽",
            f"{detail}本关最多 {self.level.max_turns} 回合。\n"
            "可以撤销到上一回合继续，也可以重新布置干草垛。",
            accent=theme.CLAY,
            buttons=[
                ui.Button(pygame.Rect(0, 0, 190, 50), "撤销到上一回合", "undo_result", style="primary"),
                ui.Button(pygame.Rect(0, 0, 170, 50), "重开本关", "retry", style="default"),
                ui.Button(pygame.Rect(0, 0, 130, 50), "返回", "leave", style="ghost"),
            ],
            width=680,
            height=340,
        )

    def _show_win_modal(self) -> None:
        turns = self.sim.turns
        rank = self.rank or self.level.rank_for(turns)
        if self.mode == "tutorial":
            body = f"用了 {turns} 回合完成本课。\n{rank.comment}"
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
        title = "全部进栏！" if self.sim.last_tick and self.sim.last_tick.penned else "抓到啦！"
        body = (
            f"用了 {turns} 回合，放下了 {self.sim.obstacle_count} 个干草垛。\n"
            f"{rank.comment}\n{record_text}"
        )
        buttons = [ui.Button(pygame.Rect(0, 0, 150, 50), "再玩一次", "retry", style="ghost")]
        if self.mode == "main" and self.level_number < len(self.app.levels):
            buttons.append(
                ui.Button(pygame.Rect(0, 0, 150, 50), "下一关", "next_level", style="primary")
            )
        buttons.append(ui.Button(pygame.Rect(0, 0, 150, 50), "返回", "leave", style="ghost"))
        self.modal = ui.Modal(
            title,
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
        if action == "undo_result":
            self._undo()
        elif action in ("retry", "dismiss"):
            self._restart()
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
        self._draw_top_bar(surface)
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
            surface,
            pygame.Rect(0, 0, theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT),
            theme.CREAM,
            theme.CREAM_DARK,
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
        badge_map = {
            "main": ("主线", theme.LEAF),
            "tutorial": ("教程", theme.SKY_DEEP),
            "challenge": ("挑战", theme.CLAY),
            "daily": ("每日", theme.SKY_DEEP),
            "editor": ("试玩", theme.SUN),
        }
        badge, badge_color = badge_map.get(self.mode, ("主线", theme.LEAF))
        width = self.fonts.size_of(title, theme.FONT_H1, True)[0]
        ui.draw_pill(surface, self.fonts, badge, (62 + width + 62, 58), badge_color)
        pygame.draw.line(surface, theme.PANEL_BORDER, (60, 104), (1220, 104), 2)

    def _draw_top_bar(self, surface: pygame.Surface) -> None:
        self._draw_stat(
            surface, 60, 112, 150, "回合", f"{self.sim.turns} / {self.level.max_turns}"
        )
        self._draw_stat(
            surface,
            218,
            112,
            130,
            "干草垛",
            f"{self.sim.obstacle_count} / {self.level.initial_obstacles}",
        )
        for button in (self.undo_button, self.restart_button, self.predict_button):
            button.draw(surface, self.fonts)

    def _draw_stat(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        label: str,
        value: str,
    ) -> None:
        rect = pygame.Rect(x, y, width, 44)
        theme.rounded_rect(surface, rect, theme.PANEL_BG, radius=12)
        theme.rounded_rect(surface, rect, theme.PANEL_BORDER, radius=12, width=2)
        theme.draw_text(
            surface,
            self.fonts,
            label,
            (rect.left + 10, rect.centery),
            theme.FONT_TINY,
            theme.INK_LIGHT,
            anchor="midleft",
        )
        theme.draw_text(
            surface,
            self.fonts,
            value,
            (rect.right - 10, rect.centery),
            theme.FONT_H3,
            theme.INK,
            anchor="midright",
            bold=True,
        )

    def _draw_board(self, surface: pygame.Surface) -> None:
        view = BoardView(
            level=self.level,
            sim=self.sim,
            animator=self.animator,
            hover=self.hover if self.phase == "place" else None,
            hover_valid=self.hover_valid,
            placement_mode=self.phase == "place",
            show_prediction=self.show_prediction and not self.sim.status.is_finished,
            prediction=self._prediction(),
            effects=self.effects,
            pulse=self.time,
            highlight=self._highlight_cell(),
            trails=tuple([self.trail_farmer] + self.trail_cows),
            trail_colors=[theme.DENIM, theme.CLAY, theme.LEAF_DARK],
            pen_cells=self.level.pen_cells,
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
        left = theme.PANEL_RECT.left + 24
        width = theme.PANEL_RECT.width - 48
        y = theme.PANEL_RECT.top + 20

        label_map = {
            "main": f"第 {self.level_number:02d} 关",
            "tutorial": "本课目标",
            "challenge": "挑战目标",
            "daily": "今日牧场",
            "editor": "自建关卡",
        }
        theme.draw_text(
            surface,
            self.fonts,
            label_map.get(self.mode, "本关目标"),
            (left, y),
            theme.FONT_SMALL,
            theme.INK_LIGHT,
        )
        y += 26
        theme.draw_text(
            surface, self.fonts, self.level.name, (left, y), theme.FONT_H2, theme.INK, bold=True
        )
        y += 44
        ui.draw_divider(surface, y, left, width)
        y += 16

        hint_text = self.level.goal_text or self.level.hint or self.level.description
        if self.tutorial is not None and self.tutorial.active:
            hint_text = self.level.goal_text or self.level.description
        if hint_text:
            wrapped = self.fonts.wrap(hint_text, theme.FONT_SMALL, width, theme.INK_SOFT)
            surface.blit(wrapped, (left, y))
            y += wrapped.get_height() + 10

        if self.level.is_pen_level:
            goal = f"目标：{self.sim.penned_count} / {len(self.sim.cows)} 头牛进栏"
        else:
            goal = "目标：抓住牛"
        ui.draw_pill(surface, self.fonts, goal, (left + 52, y + 18), theme.LEAF_DARK)
        y += 50

        if self.tutorial is not None and self.tutorial.active:
            self._draw_tutorial_box(surface, left, y, width)
        elif self.phase == "place":
            helper = self.fonts.wrap(
                "点击草地放干草垛，点击干草垛可以收回。开始后不能改布局，但可以按 U 撤销回布置阶段。",
                theme.FONT_SMALL,
                width,
                theme.INK_LIGHT,
            )
            surface.blit(helper, (left, y))
        elif self.phase == "run":
            helper = self.fonts.wrap(
                "方向键 / WASD 移动农夫，空格原地等待。牛会在你之后走一步。",
                theme.FONT_SMALL,
                width,
                theme.INK_LIGHT,
            )
            surface.blit(helper, (left, y))
        else:
            helper = self.fonts.wrap(
                "可以撤销到上一回合继续，或重新布置干草垛。",
                theme.FONT_SMALL,
                width,
                theme.INK_LIGHT,
            )
            surface.blit(helper, (left, y))

        self.start_button.draw(surface, self.fonts)
        if self.mode == "tutorial":
            self.skip_button.enabled = not self.sim.status.is_finished
            self.skip_button.draw(surface, self.fonts)

    def _draw_tutorial_box(self, surface: pygame.Surface, x: int, y: int, width: int) -> None:
        box = pygame.Rect(x, y, width, 132)
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
            text = "点击草地放干草垛 · 右键收回 · 空格开始 · U 撤销 · R 重开"
        else:
            text = "方向键/WASD 移动 · 空格等待 · U 撤销 · R 重开 · P 预测"
        draw_footer(surface, self.fonts, text)
        if self.show_prediction and self.level.prediction_steps > 0:
            theme.draw_text(
                surface,
                self.fonts,
                f"半透明脚印 = 牛接下来 {self.level.prediction_steps} 回合的路线（假设农夫等待）",
                (theme.BOARD_ORIGIN[0], 752),
                theme.FONT_TINY,
                theme.INK_LIGHT,
            )

    def _draw_toast(self, surface: pygame.Surface) -> None:
        body = self.fonts.wrap(self.toast_text, theme.FONT_SMALL, 460, theme.WHITE_WARM)
        rect = pygame.Rect(0, 0, body.get_width() + 40, body.get_height() + 24)
        rect.center = (
            theme.BOARD_ORIGIN[0] + theme.BOARD_SIZE // 2,
            theme.BOARD_ORIGIN[1] + theme.BOARD_SIZE - 8,
        )
        theme.soft_shadow(surface, rect, radius=14, alpha=60, offset=(0, 4))
        theme.rounded_rect(surface, rect, theme.CLAY, radius=14)
        surface.blit(body, (rect.left + 20, rect.top + 12))
