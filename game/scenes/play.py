"""The gameplay screen for the tank-driving, exit-escape chase."""

from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from .. import theme, ui
from ..animation import TurnAnimator
from ..core import Simulation
from ..models import Action, Direction, GameStatus, Level, Pos, Rank
from ..render import BoardRenderer, BoardView, EffectSystem
from .base import Scene, draw_footer

RESULT_DELAY = 0.95
LOOP_COLOR = theme.SKY_DEEP
EXIT_COLOR = theme.CLAY


class PlayScene(Scene):
    """Renders and drives one escape attempt."""

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
        self.show_alerts = bool(self.store.get_setting("alerts", True))
        self.phase = "run"
        self.turns_since_result = 0.0
        self.result_timer = 0.0
        self.result_shown = False
        self.practice_failed = False
        self.rank: Optional[Rank] = None
        self.new_record = False
        self.modal: Optional[ui.Modal] = None
        self.toast_text = ""
        self.toast_timer = 0.0
        self.loop_events = 0
        self.action_count = 0
        self.forward_count = 0
        self.turn_directions: set[Direction] = set()
        self.blocked_count = 0
        self.undo_count = 0
        self.invalid_count = 0
        self.prediction_used = self.show_prediction
        self.trail_farmer: List[Pos] = []
        self.trail_cows: List[List[Pos]] = []
        self._prediction_cache: Tuple = ()
        self._prediction_key = None
        self.buttons: List[ui.Button] = []
        self.tutorial = None
        self._seed_trails()
        self._build_buttons()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _build_buttons(self) -> None:
        self.undo_button = ui.Button(
            pygame.Rect(336, 112, 90, 44), "撤销", "undo", style="ghost", font_size=theme.FONT_TINY
        )
        self.restart_button = ui.Button(
            pygame.Rect(434, 112, 90, 44), "重开", "restart", style="ghost", font_size=theme.FONT_TINY
        )
        self.predict_button = ui.Button(
            pygame.Rect(532, 112, 100, 44), "预测 开", "predict", style="ghost", font_size=theme.FONT_TINY
        )
        self.alert_button = ui.Button(
            pygame.Rect(640, 112, 90, 44), "警觉 开", "alerts", style="ghost", font_size=theme.FONT_TINY
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
            self.alert_button,
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
    def _refresh_buttons(self) -> None:
        self.undo_button.enabled = self.sim.can_undo and not self.animator.busy
        self.restart_button.enabled = True
        self.predict_button.enabled = self.level.prediction_steps > 0
        if self.level.prediction_steps <= 0:
            self.predict_button.text = "预测 无"
        else:
            self.predict_button.text = "预测 开" if self.show_prediction else "预测 关"
        self.alert_button.text = "警觉 开" if self.show_alerts else "警觉 关"
        self.skip_button.enabled = not self.sim.status.is_finished

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

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            self._leave()
            return
        if event.key == pygame.K_u:
            self._undo()
            return
        if event.key == pygame.K_r:
            self._restart()
            return
        if event.key == pygame.K_p:
            self._toggle_prediction()
            return
        if self.animator.busy or self.phase != "run":
            return
        if event.key in (pygame.K_w, pygame.K_UP):
            self._take_action(Action.TURN_TO_UP)
        elif event.key in (pygame.K_s, pygame.K_DOWN):
            self._take_action(Action.TURN_TO_DOWN)
        elif event.key in (pygame.K_a, pygame.K_LEFT):
            self._take_action(Action.TURN_TO_LEFT)
        elif event.key in (pygame.K_d, pygame.K_RIGHT):
            self._take_action(Action.TURN_TO_RIGHT)
        elif event.key == pygame.K_SPACE:
            self._take_action(Action.FORWARD)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _button_action(self, action: str) -> None:
        if action == "undo":
            self._undo()
        elif action == "restart":
            self._restart()
        elif action == "predict":
            self._toggle_prediction()
        elif action == "alerts":
            self._toggle_alerts()
        elif action == "skip":
            self._skip_tutorial()

    def _take_action(self, action: Action) -> None:
        if self.phase != "run" or self.animator.busy:
            return
        result = self.sim.apply_action(action)
        if result.invalid:
            self.invalid_count += 1
            self._toast(result.message or "已朝该方向")
            self.app.sound.play("error")
            self._tutorial_event("invalid")
            self._refresh_buttons()
            return

        self.action_count += 1
        if action is Action.FORWARD:
            self.forward_count += 1
        else:
            self.turn_directions.add(action.direction)

        self.animator.play(result)
        self.trail_farmer.append(self.sim.farmer.pos)
        for index, cow in enumerate(self.sim.cows):
            if index < len(self.trail_cows):
                self.trail_cows[index].append(cow.pos)

        if result.blocked:
            self.blocked_count += 1
            self._toast(result.message)
            self.app.sound.play("error")
            self._tutorial_event("blocked")
        elif action is Action.FORWARD:
            self._tutorial_event("forward")
        else:
            self._tutorial_event("turn")

        if result.caught_now:
            for index in result.caught_now:
                if index < len(self.sim.cows):
                    pos = self.sim.cows[index].pos
                    center = self.board_center(pos)
                    self.effects.ring(center, theme.SUN, 70, 0.6)
            self._toast(f"抓住了 {len(result.caught_now)} 头牛！", 1.6)
            self.app.sound.play("place")
            self._tutorial_event("catch")

        if result.loop_hint:
            self.loop_events += 1
            self._toast("局面进入循环。你仍然可以继续操作，换一个方向试试。", 2.8)
            self.app.sound.play("loop")
            self._tutorial_event("loop")

        if result.escaped_index is not None:
            self._toast("牛从出口逃走了", 3.0)
            self.app.sound.play("lose")
            self._tutorial_event("exit")
            self._begin_result()
        elif result.status.is_finished:
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
        self.rank = self.level.rank_for(self.sim.turns) if self.sim.status is GameStatus.WON else None
        center = self.board_center(self.sim.farmer.pos)
        if self.sim.status is GameStatus.LOST_EXIT and self.sim.last_tick is not None:
            escaped = self.sim.last_tick.escaped_index
            if escaped is not None and escaped < len(self.sim.cows):
                center = self.board_center(self.sim.cows[escaped].pos)
        if self.sim.status is GameStatus.WON:
            self.effects.burst_petals(center, 28 if not self.effects.low_effects else 0)
            self.effects.ring(center, theme.SUN, 130, 0.9)
            self.effects.flying_hat(center)
            self.app.sound.play("win")
            if self._practice_missing():
                self.practice_failed = True
                self.app.sound.play("error")
            else:
                self._record_win()
                self._tutorial_event("win")
        elif self.sim.status is GameStatus.LOST_EXIT:
            self.effects.ring(center, theme.CLAY, 90, 0.7)
            self.app.sound.play("lose")
        else:
            self.app.sound.play("lose")
        self._refresh_buttons()

    def _practice_missing(self) -> bool:
        if self.mode != "tutorial":
            return False
        extra = self.level.extra
        required = {str(name).lower() for name in (extra.get("require_directions") or [])}
        if required:
            used = {direction.name.lower() for direction in self.turn_directions}
            if not required.issubset(used):
                return True
        if extra.get("require_turn") and len(self.turn_directions) < 2:
            return True
        if extra.get("require_forward") and self.forward_count == 0:
            return True
        if extra.get("require_actions") and self.action_count < int(extra["require_actions"]):
            return True
        if extra.get("require_block") and self.blocked_count == 0:
            return True
        if extra.get("require_invalid") and self.invalid_count == 0:
            return True
        if extra.get("require_undo") and self.undo_count == 0:
            return True
        if extra.get("require_prediction") and not self.prediction_used:
            return True
        return False

    def _record_win(self) -> None:
        turns = self.sim.turns
        rank = self.level.rank_for(turns)
        if self.mode == "main":
            self.new_record = self.store.record_main_clear(self.level.level_id, turns, rank)
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
        self.undo_count += 1
        self.animator.clear()
        self.modal = None
        self.result_shown = False
        self.result_timer = 0.0
        self.practice_failed = False
        self.rank = None
        self.new_record = False
        self._seed_trails()
        self.phase = "run"
        self._tutorial_event("undo")
        self.app.sound.play("undo")
        self._toast(f"已撤销，回到第 {self.sim.turns} 回合。")
        self._refresh_buttons()

    def _restart(self) -> None:
        self.sim.reset()
        self.animator.clear()
        self.modal = None
        self.result_shown = False
        self.result_timer = 0.0
        self.practice_failed = False
        self.rank = None
        self.new_record = False
        self.action_count = 0
        self.forward_count = 0
        self.turn_directions: set[Direction] = set()
        self.blocked_count = 0
        self.undo_count = 0
        self.invalid_count = 0
        self.loop_events = 0
        self.phase = "run"
        self._seed_trails()
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

    def _toggle_alerts(self) -> None:
        self.show_alerts = not self.show_alerts
        self.store.set_setting("alerts", self.show_alerts)
        self.app.sound.play("click")
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
        if self.practice_failed:
            self.modal = ui.Modal(
                "还差一个练习",
                f"这一课还要完成：{self.level.practice_text or '指定动作'}。\n"
                "重开本课，完成练习后再抓住全部牛。",
                accent=theme.SKY_DEEP,
                badge="练习",
                buttons=[
                    ui.Button(pygame.Rect(0, 0, 170, 50), "重开本课", "retry", style="primary"),
                    ui.Button(pygame.Rect(0, 0, 150, 50), "返回章节", "leave", style="ghost"),
                ],
                width=640,
                height=330,
            )
            return
        if self.sim.status is GameStatus.WON:
            self._show_win_modal()
            return
        if self.sim.status is GameStatus.LOST_EXIT:
            title = "牛从出口逃走了"
            body = "一头牛抵达了金色出口，本局失败。\n可以撤销到上一回合，或重新开始。"
        else:
            title = "回合数已用完"
            body = f"本关最多 {self.level.max_turns} 回合，牛还没有全部抓住。\n可以撤销到上一回合，或重新开始。"
        self.modal = ui.Modal(
            title,
            body,
            accent=EXIT_COLOR,
            buttons=[
                ui.Button(pygame.Rect(0, 0, 190, 50), "撤销到上一回合", "undo_result", style="primary"),
                ui.Button(pygame.Rect(0, 0, 170, 50), "重开本关", "retry", style="default"),
                ui.Button(pygame.Rect(0, 0, 130, 50), "返回", "leave", style="ghost"),
            ],
            width=680,
            height=350,
        )

    def _show_win_modal(self) -> None:
        turns = self.sim.turns
        rank = self.rank or self.level.rank_for(turns)
        if self.mode == "tutorial":
            body = f"用了 {turns} 回合，抓住全部牛。\n{rank.comment}"
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
            f"用了 {turns} 回合，抓住了 {len(self.sim.cows)} 头牛。\n"
            f"{rank.comment}\n{record_text}"
        )
        buttons = [ui.Button(pygame.Rect(0, 0, 150, 50), "再玩一次", "retry", style="ghost")]
        if self.mode == "main" and self.level_number < len(self.app.levels):
            buttons.append(
                ui.Button(pygame.Rect(0, 0, 150, 50), "下一关", "next_level", style="primary")
            )
        buttons.append(ui.Button(pygame.Rect(0, 0, 150, 50), "返回", "leave", style="ghost"))
        self.modal = ui.Modal(
            "全部抓住！",
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

    def board_center(self, pos: Pos) -> Tuple[int, int]:
        return (
            theme.BOARD_ORIGIN[0] + int((pos[1] + 0.5) * theme.CELL_SIZE),
            theme.BOARD_ORIGIN[1] + int((pos[0] + 0.5) * theme.CELL_SIZE),
        )

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
        status_text = "追逐中" if self.phase == "run" else "本局结束"
        ui.draw_pill(
            surface,
            self.fonts,
            status_text,
            (62 + width + 170, 58),
            theme.CREAM_DARK,
            text_color=theme.INK_SOFT,
        )
        pygame.draw.line(surface, theme.PANEL_BORDER, (60, 104), (1220, 104), 2)

    def _draw_top_bar(self, surface: pygame.Surface) -> None:
        self._draw_stat(surface, 60, 112, 140, "回合", f"{self.sim.turns} / {self.level.max_turns}")
        self._draw_stat(
            surface,
            208,
            112,
            120,
            "牛",
            f"{self.sim.caught_count} / {len(self.sim.cows)}",
        )
        for button in (self.undo_button, self.restart_button, self.predict_button, self.alert_button):
            button.draw(surface, self.fonts)

    def _draw_stat(self, surface, x, y, width, label, value):
        rect = pygame.Rect(x, y, width, 44)
        theme.rounded_rect(surface, rect, theme.PANEL_BG, radius=12)
        theme.rounded_rect(surface, rect, theme.PANEL_BORDER, radius=12, width=2)
        theme.draw_text(
            surface, self.fonts, label, (rect.left + 10, rect.centery), theme.FONT_TINY,
            theme.INK_LIGHT, anchor="midleft",
        )
        theme.draw_text(
            surface, self.fonts, value, (rect.right - 10, rect.centery), theme.FONT_H3,
            theme.INK, anchor="midright", bold=True,
        )

    def _draw_board(self, surface: pygame.Surface) -> None:
        view = BoardView(
            level=self.level,
            sim=self.sim,
            animator=self.animator,
            show_prediction=self.show_prediction and not self.sim.status.is_finished,
            prediction=self._prediction(),
            effects=self.effects,
            pulse=self.time,
            highlight=self._highlight_cell(),
            show_alerts=self.show_alerts,
            trails=tuple([self.trail_farmer] + self.trail_cows),
            trail_colors=[theme.DENIM, theme.CLAY, theme.LEAF_DARK],
            near_exits=self.sim.near_exit(3),
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
            surface, self.fonts, label_map.get(self.mode, "本关目标"), (left, y),
            theme.FONT_SMALL, theme.INK_LIGHT,
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

        ui.draw_pill(
            surface, self.fonts, "目标：抓住全部牛", (left + 76, y + 18), theme.LEAF_DARK
        )
        y += 50
        if self.sim.near_exit(3) and not self.sim.status.is_finished:
            ui.draw_pill(
                surface, self.fonts, "出口就在附近！", (left + 80, y + 12), EXIT_COLOR
            )
            y += 34

        if self.tutorial is not None and self.tutorial.active:
            self._draw_tutorial_box(surface, left, y, width)
        else:
            card = pygame.Rect(left, 438, width, 124)
            theme.rounded_rect(surface, card, theme.CREAM, radius=14)
            theme.rounded_rect(surface, card, theme.PANEL_BORDER, radius=14, width=2)
            theme.draw_text(
                surface, self.fonts, "本关规则", (card.left + 16, card.top + 10),
                theme.FONT_TINY, theme.INK_LIGHT,
            )
            lines = [
                "W/↑ 朝上 · S/↓ 朝下 · A/← 朝左 · D/→ 朝右",
                "空格前进 · U 撤销 · R 重开 · P 预测",
                f"回合上限 {self.level.max_turns} · 预测 {self.level.prediction_steps} 步",
            ]
            line_y = card.top + 34
            for line in lines:
                theme.draw_text(
                    surface, self.fonts, line, (card.left + 16, line_y),
                    theme.FONT_SMALL, theme.INK_SOFT,
                )
                line_y += 26

        if self.mode == "tutorial":
            self.skip_button.draw(surface, self.fonts)

    def _draw_tutorial_box(self, surface: pygame.Surface, x: int, y: int, width: int) -> None:
        box = pygame.Rect(x, y, width, 176)
        theme.rounded_rect(surface, box, theme.SKY_PALE, radius=16)
        theme.rounded_rect(surface, box, theme.SKY_DEEP, radius=16, width=2)
        ui.draw_pill(surface, self.fonts, "提示", (box.left + 44, box.top + 22), theme.SKY_DEEP)
        text = self.fonts.wrap(self.tutorial.active or "", theme.FONT_SMALL, width - 48, theme.INK)
        surface.blit(text, (box.left + 20, box.top + 44))
        if self.level.practice_text:
            ui.draw_pill(surface, self.fonts, "练习", (box.left + 44, box.top + 108), theme.CREAM_DARK)
            practice = self.fonts.wrap(
                self.level.practice_text, theme.FONT_TINY, width - 110, theme.INK_SOFT
            )
            surface.blit(practice, (box.left + 84, box.top + 98))
            if practice.get_height() > 40:
                bar_y = box.bottom - 14
            else:
                bar_y = box.bottom - 16
        else:
            bar_y = box.bottom - 16
        ratio = self.tutorial.progress_ratio
        bar = pygame.Rect(box.left + 20, bar_y, width - 40, 8)
        theme.rounded_rect(surface, bar, theme.CREAM_DARK, radius=4)
        filled = pygame.Rect(bar.left, bar.top, int(bar.width * ratio), bar.height)
        theme.rounded_rect(surface, filled, theme.SKY_DEEP, radius=4)

    def _draw_footer(self, surface: pygame.Surface) -> None:
        draw_footer(
            surface,
            self.fonts,
            "W/↑ 朝上，S/↓ 朝下，A/← 朝左，D/→ 朝右，空格前进，U 撤销，R 重开",
        )
        if self.show_prediction and self.level.prediction_steps > 0 and self.toast_timer <= 0:
            text = self.fonts.wrap(
                f"半透明脚印 = 牛接下来 {self.level.prediction_steps} 回合的路线（基于 Farmer John 当前位置与朝向不变）",
                theme.FONT_TINY,
                theme.BOARD_SIZE,
                theme.INK_LIGHT,
            )
            surface.blit(text, (theme.BOARD_ORIGIN[0], 752))

    def _draw_toast(self, surface: pygame.Surface) -> None:
        body = self.fonts.wrap(self.toast_text, theme.FONT_SMALL, 460, theme.WHITE_WARM)
        rect = pygame.Rect(0, 0, body.get_width() + 40, body.get_height() + 24)
        rect.center = (theme.BOARD_ORIGIN[0] + theme.BOARD_SIZE // 2, 770)
        theme.soft_shadow(surface, rect, radius=14, alpha=60, offset=(0, 4))
        theme.rounded_rect(surface, rect, theme.CLAY, radius=14)
        surface.blit(body, (rect.left + 20, rect.top + 12))
