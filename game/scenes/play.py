"""The gameplay screen for the tank-driving, exit-escape chase."""

from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from .. import theme, ui
from ..animation import TurnAnimator
from ..core import Simulation
from ..models import Action, GameStatus, Level, Pos, Rank
from ..render import BoardRenderer, BoardView, EffectSystem
from ..solver import solve_level_cached
from .base import Scene, draw_footer

RESULT_DELAY = 0.95
HINT_DELAY = 9.0
DEMO_START_DELAY = 0.4
DEMO_STEP_DELAY = 0.46
DEMO_END_HOLD = 1.3
DEMO_MAX_NODES = 100_000
DEMO_MAX_SECONDS = 3.0
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
        challenge_key: str = "",
        daily_key: str = "",
        return_to: str = "level_select",
    ) -> None:
        super().__init__(app)
        self.level = level
        self.mode = mode
        self.level_number = level_number
        self.challenge_key = challenge_key
        self.daily_key = daily_key
        self.return_to = return_to
        self.panel_rect = theme.PLAY_PANEL_RECT
        self.stage_origin = theme.PLAY_BOARD_STAGE_ORIGIN
        self.board_origin = self._centered_board_origin(level)

        self.renderer = BoardRenderer(self.cache, self.fonts, origin=self.board_origin)
        self.sim = Simulation(level)
        self.animator = TurnAnimator()
        self.effects = EffectSystem(bool(self.store.get_setting("low_effects", False)))
        self.show_prediction = bool(self.store.get_setting("preview", True))
        self.show_alerts = bool(self.store.get_setting("alerts", True))
        self.show_hints = bool(self.store.get_setting("hints", True))
        self.hint_index = 0
        self.hint_timer = 0.0
        self.phase = "run"
        self.turns_since_result = 0.0
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
        self._prediction_cache: Tuple = ()
        self._prediction_key = None
        self._failure_sim: Optional[Simulation] = None
        self._failure_loop_events = 0
        self.demo_actions: Tuple[Action, ...] = ()
        self.demo_index = 0
        self.demo_timer = 0.0
        self.demo_paused = False
        self.demo_done = False
        self.demo_done_timer = 0.0
        self.demo_last_action: Optional[Action] = None
        self.hint_card_rect: Optional[pygame.Rect] = None
        self.buttons: List[ui.Button] = []
        self._seed_trails()
        self._build_buttons()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    @staticmethod
    def _centered_board_origin(level: Level) -> Tuple[int, int]:
        """Center a board inside the right-hand stage."""
        stage_x, stage_y = theme.PLAY_BOARD_STAGE_ORIGIN
        return (
            stage_x + (theme.BOARD_SIZE - level.width * theme.CELL_SIZE) // 2,
            stage_y + (theme.BOARD_SIZE - level.height * theme.CELL_SIZE) // 2,
        )

    def _build_buttons(self) -> None:
        self.undo_button = ui.Button(
            pygame.Rect(868, 112, 80, 44), "[U] 撤销", "undo", style="ghost", font_size=theme.FONT_TINY
        )
        self.restart_button = ui.Button(
            pygame.Rect(954, 112, 80, 44), "[R] 重开", "restart", style="ghost", font_size=theme.FONT_TINY
        )
        self.predict_button = ui.Button(
            pygame.Rect(1040, 112, 100, 44), "[P] 预测 开", "predict", style="ghost", font_size=theme.FONT_TINY
        )
        self.alert_button = ui.Button(
            pygame.Rect(1146, 112, 74, 44), "警觉 开", "alerts", style="ghost", font_size=theme.FONT_TINY
        )
        self.buttons = [
            self.undo_button,
            self.restart_button,
            self.predict_button,
            self.alert_button,
        ]
        self.demo_pause_button = ui.Button(
            pygame.Rect(868, 112, 80, 44), "暂停", "demo_pause", style="ghost", font_size=theme.FONT_TINY
        )
        self.demo_exit_button = ui.Button(
            pygame.Rect(954, 112, 100, 44), "退出演示", "demo_exit", style="ghost", font_size=theme.FONT_TINY
        )
        self.demo_buttons = [self.demo_pause_button, self.demo_exit_button]
        self.hint_next_button = ui.Button(
            pygame.Rect(0, 0, 104, 36),
            "下一条",
            "hint_next",
            style="sky",
            font_size=theme.FONT_TINY,
        )
        self.hint_next_button.visible = False
        self.back_button = ui.Button(
            pygame.Rect(theme.WINDOW_WIDTH - 190, 36, 130, 52), "返回", "back", style="ghost"
        )

    def on_enter(self) -> None:
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _refresh_buttons(self) -> None:
        running = self.phase == "run"
        self.undo_button.enabled = running and self.sim.can_undo and not self.animator.busy
        self.restart_button.enabled = running
        self.predict_button.enabled = self.level.prediction_steps > 0
        if self.level.prediction_steps <= 0:
            self.predict_button.text = "[P] 预测 无"
        else:
            self.predict_button.text = "[P] 预测 开" if self.show_prediction else "[P] 预测 关"
        self.alert_button.text = "警觉 开" if self.show_alerts else "警觉 关"
        self.demo_pause_button.text = "继续" if self.demo_paused else "暂停"

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

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.modal is not None:
            action = self.modal.handle_event(event)
            if action:
                self._modal_action(action)
            return

        if self.phase == "demo":
            for button in self.demo_buttons:
                action = button.handle_event(event)
                if action:
                    self._demo_button_action(action)
                    return
            return

        if self.phase == "run" and self.hint_next_button.visible:
            hint_action = self.hint_next_button.handle_event(event)
            if hint_action:
                self._advance_hint(play_sound=True)
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

    def _hint_texts(self) -> Tuple[str, ...]:
        if self.level.hint_text:
            return self.level.hint_text
        if self.level.hint:
            return (self.level.hint,)
        return ()

    def _advance_hint(self, *, play_sound: bool = False) -> bool:
        texts = self._hint_texts()
        if not texts or self.hint_index >= len(texts) - 1:
            return False
        self.hint_index += 1
        self.hint_timer = 0.0
        if play_sound:
            self.app.sound.play("click")
        return True

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

    def _take_action(self, action: Action) -> None:
        if self.phase != "run" or self.animator.busy:
            return
        result = self.sim.apply_action(action)
        if result.invalid:
            self._toast(result.message or "已朝该方向")
            self.app.sound.play("error")
            self._refresh_buttons()
            return

        self.animator.play(result)
        self.trail_farmer.append(self.sim.farmer.pos)
        for index, cow in enumerate(self.sim.cows):
            if index < len(self.trail_cows):
                self.trail_cows[index].append(cow.pos)

        if result.blocked:
            self._toast(result.message)
            self.app.sound.play("error")

        if result.caught_now:
            for index in result.caught_now:
                if index < len(self.sim.cows):
                    pos = self.sim.cows[index].pos
                    center = self.board_center(pos)
                    self.effects.ring(center, theme.SUN, 70, 0.6)
            self._toast(f"抓住了 {len(result.caught_now)} 头牛！", 1.6)
            self.app.sound.play("place")

        if result.loop_hint:
            self.loop_events += 1
            self._toast("局面进入循环。你仍然可以继续操作，换一个方向试试。", 2.8)
            self.app.sound.play("loop")

        if result.escaped_index is not None:
            self._toast("牛从出口逃走了", 3.0)
            self.app.sound.play("lose")
            self._begin_result()
        elif result.status.is_finished:
            self._begin_result()
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
            self._record_win()
        elif self.sim.status is GameStatus.LOST_EXIT:
            self.effects.ring(center, theme.CLAY, 90, 0.7)
            self.app.sound.play("lose")
        else:
            self.app.sound.play("lose")
        self._refresh_buttons()

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

    # ------------------------------------------------------------------
    # Solution playback
    # ------------------------------------------------------------------
    def _start_solution_demo(self) -> None:
        """Solve the level from its opening state and start a replay."""
        if (
            self.phase != "result"
            or self._failure_sim is not None
            or not self.sim.status.is_failure
        ):
            return
        result = solve_level_cached(
            self.level,
            max_nodes=DEMO_MAX_NODES,
            max_seconds=DEMO_MAX_SECONDS,
        )
        if not result.solved:
            notice = "暂时无法给出解法"
            if result.status == "limit":
                notice += "（搜索超时或超出限制）"
            if self.modal is not None:
                self.modal.notice = notice
            self._toast(notice, 3.0)
            self.app.sound.play("error")
            return

        self._failure_sim = self.sim
        self._failure_loop_events = self.loop_events
        self.sim = Simulation(self.level)
        self.modal = None
        self.phase = "demo"
        self.demo_actions = tuple(Action(item) for item in result.actions)
        self.demo_index = 0
        self.demo_timer = DEMO_START_DELAY
        self.demo_paused = False
        self.demo_done = False
        self.demo_done_timer = 0.0
        self.demo_last_action = None
        self.result_shown = False
        self.result_timer = 0.0
        self.animator.clear()
        self.effects.clear()
        self._prediction_key = None
        self.hint_timer = 0.0
        self._seed_trails()
        self._refresh_buttons()
        self.app.sound.play("click")
        self._toast("自动演示中：结束后回到失败时的局面。", 2.6)

    def _demo_button_action(self, action: str) -> None:
        if action == "demo_pause":
            self.demo_paused = not self.demo_paused
            self._refresh_buttons()
            self._toast("演示已暂停。" if self.demo_paused else "继续演示。", 1.4)
            self.app.sound.play("click")
        elif action == "demo_exit":
            self.app.sound.play("click")
            self._restore_after_demo()

    def _advance_demo(self) -> None:
        if self.demo_done:
            return
        if self.demo_index >= len(self.demo_actions):
            self.demo_done = True
            self.demo_done_timer = 0.0
            self._toast("演示结束。", 1.6)
            return

        action = self.demo_actions[self.demo_index]
        self.demo_timer = DEMO_STEP_DELAY
        result = self.sim.apply_action(action)
        self.demo_index += 1
        self.demo_last_action = action
        if not result.invalid:
            self.animator.play(result)
            self.trail_farmer.append(self.sim.farmer.pos)
            for index, cow in enumerate(self.sim.cows):
                if index < len(self.trail_cows):
                    self.trail_cows[index].append(cow.pos)
            if result.caught_now:
                for index in result.caught_now:
                    if index < len(self.sim.cows):
                        self.effects.ring(
                            self.board_center(self.sim.cows[index].pos), theme.SUN, 70, 0.6
                        )
                self.app.sound.play("place")
            if result.loop_hint:
                self._toast("演示路线遇到重复局面，继续按求解器路线行动。", 2.0)
        if result.status is GameStatus.WON:
            self.demo_done = True
            self.demo_done_timer = 0.0
            if self.sim.last_tick is not None:
                self.effects.burst_petals(
                    self.board_center(self.sim.farmer.pos),
                    18 if not self.effects.low_effects else 0,
                )
            self.app.sound.play("unlock")
            self._toast("演示完成：这条路线可以通关。", 2.4)
        elif result.status.is_finished:
            self.demo_done = True
            self.demo_done_timer = 0.0
            self._toast("演示未能通关，即将回到失败局面。", 2.2)
        elif self.demo_index >= len(self.demo_actions):
            self.demo_done = True
            self.demo_done_timer = 0.0
            self._toast("演示结束。", 1.6)
        self._refresh_buttons()

    def _restore_after_demo(self) -> None:
        if self._failure_sim is None:
            return
        self.sim = self._failure_sim
        self._failure_sim = None
        self.demo_actions = ()
        self.demo_index = 0
        self.demo_timer = 0.0
        self.demo_paused = False
        self.demo_done = False
        self.demo_done_timer = 0.0
        self.demo_last_action = None
        self.animator.clear()
        self.effects.clear()
        self._prediction_key = None
        self.loop_events = self._failure_loop_events
        self.phase = "result"
        self.result_shown = True
        self.result_timer = 0.0
        self.toast_timer = 0.0
        self._seed_trails()
        self._refresh_buttons()
        self._show_demo_end_modal()

    def _show_demo_end_modal(self) -> None:
        """Dedicated dialog after a playback returns to the failed run."""
        self.modal = ui.Modal(
            "演示结束",
            "电脑已经演示完这条通关路线，已恢复到你失败时的局面。\n"
            "可以再次演示，或重开本关自己再试一次。演示不计入成绩。",
            accent=theme.SKY_DEEP,
            badge="演示未计成绩",
            buttons=[
                ui.Button(pygame.Rect(0, 0, 160, 50), "再次演示", "show_solution", style="primary"),
                ui.Button(pygame.Rect(0, 0, 110, 50), "重开", "retry", style="default"),
                ui.Button(pygame.Rect(0, 0, 190, 50), "撤销到上一回合", "undo_result", style="ghost"),
                ui.Button(pygame.Rect(0, 0, 110, 50), "返回", "leave", style="ghost"),
            ],
            width=760,
            height=360,
        )

    def _undo(self) -> None:
        if self.animator.busy:
            return
        if not self.sim.undo():
            self._toast("没有可以撤销的步骤了。")
            self.app.sound.play("error")
            return
        self.animator.clear()
        self.modal = None
        self.result_shown = False
        self.result_timer = 0.0
        self.rank = None
        self.new_record = False
        self._seed_trails()
        self.phase = "run"
        self.app.sound.play("undo")
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
        self.hint_index = 0
        self.hint_timer = 0.0
        self.loop_events = 0
        self.phase = "run"
        self._seed_trails()
        self.app.sound.play("click")
        self._refresh_buttons()

    def _toggle_prediction(self) -> None:
        if self.level.prediction_steps <= 0:
            self._toast("这一关没有开启路径预测。")
            self.app.sound.play("error")
            return
        self.show_prediction = not self.show_prediction
        self.store.set_setting("preview", self.show_prediction)
        self.app.sound.play("click")
        self._refresh_buttons()

    def _toggle_alerts(self) -> None:
        self.show_alerts = not self.show_alerts
        self.store.set_setting("alerts", self.show_alerts)
        self.app.sound.play("click")
        self._refresh_buttons()

    def _leave(self) -> None:
        if self.mode == "editor":
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
    def _update_demo(self, dt: float) -> None:
        if not self.demo_paused:
            was_busy = self.animator.busy
            self.animator.update(dt)
            if was_busy and not self.animator.busy:
                self._refresh_buttons()
            self.effects.update(dt)
            if self.demo_done:
                if not self.animator.busy:
                    self.demo_done_timer += dt
                    if self.demo_done_timer >= DEMO_END_HOLD:
                        self._restore_after_demo()
                        return
            elif not self.animator.busy:
                self.demo_timer -= dt
                if self.demo_timer <= 0.0:
                    self._advance_demo()
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.phase == "demo":
            self._update_demo(dt)
            return
        was_busy = self.animator.busy
        self.animator.update(dt)
        if was_busy and not self.animator.busy:
            self._refresh_buttons()
        self.effects.update(dt)
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)
        if self.modal is not None:
            self.modal.update(self.app.mouse_pos())
            return
        hint_texts = self._hint_texts()
        if self.phase == "run" and self.show_hints and len(hint_texts) > 1:
            self.hint_timer += dt
            if self.hint_timer >= HINT_DELAY:
                self._advance_hint()
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
        self._show_failure_modal()

    def _show_failure_modal(self) -> None:
        if self.sim.status is GameStatus.LOST_EXIT:
            title = "牛从出口逃走了"
            body = (
                "一头牛抵达了金色出口，本局失败。\n"
                "可以撤销到上一回合、重开本关，或让电脑演示一条通关路线。"
            )
        else:
            title = "回合数已用完"
            body = (
                f"本关最多 {self.level.max_turns} 回合，牛还没有全部抓住。\n"
                "可以撤销到上一回合、重开本关，或让电脑演示一条通关路线。"
            )
        self.modal = ui.Modal(
            title,
            body,
            accent=EXIT_COLOR,
            buttons=[
                ui.Button(pygame.Rect(0, 0, 190, 50), "撤销到上一回合", "undo_result", style="primary"),
                ui.Button(pygame.Rect(0, 0, 160, 50), "显示解法", "show_solution", style="sky"),
                ui.Button(pygame.Rect(0, 0, 150, 50), "重开本关", "retry", style="default"),
                ui.Button(pygame.Rect(0, 0, 110, 50), "返回", "leave", style="ghost"),
            ],
            width=780,
            height=370,
        )

    def _show_win_modal(self) -> None:
        turns = self.sim.turns
        rank = self.rank or self.level.rank_for(turns)
        record_text = "新的最好成绩！" if self.new_record else ""
        teaching = (
            f"本关学习：{self.level.learning_objective}\n"
            if self.level.learning_objective
            else ""
        )
        is_teaching = self.mode == "main" and bool(self.level.learning_objective)
        grade_text = "" if is_teaching else f"{rank.comment}\n"
        body = (
            f"用了 {turns} 回合，抓住了 {len(self.sim.cows)} 头牛。\n"
            f"{teaching}{grade_text}{record_text}"
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
            badge="教学关" if is_teaching else f"评价 {rank.value}",
            buttons=buttons,
            width=680,
            height=380,
        )
        self.app.sound.play("unlock")

    def _modal_action(self, action: str) -> None:
        if action == "show_solution":
            self._start_solution_demo()
            return
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
        if self.phase != "demo":
            self.back_button.draw(surface, self.fonts)
        if self.toast_timer > 0 and self.toast_text:
            self._draw_toast(surface)
        if self.modal is not None:
            self.modal.draw(surface, self.fonts)

    def board_center(self, pos: Pos) -> Tuple[int, int]:
        return (
            self.board_origin[0] + int((pos[1] + 0.5) * theme.CELL_SIZE),
            self.board_origin[1] + int((pos[0] + 0.5) * theme.CELL_SIZE),
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
            "challenge": ("挑战", theme.CLAY),
            "daily": ("每日", theme.SKY_DEEP),
            "editor": ("试玩", theme.SUN),
        }
        badge, badge_color = badge_map.get(self.mode, ("主线", theme.LEAF))
        width = self.fonts.size_of(title, theme.FONT_H1, True)[0]
        ui.draw_pill(surface, self.fonts, badge, (62 + width + 62, 58), badge_color)
        status_text = {
            "run": "追逐中",
            "demo": "解法演示",
        }.get(self.phase, "本局结束")
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
        self._draw_stat(
            surface,
            660,
            112,
            118,
            "回合",
            f"{self.sim.turns} / {self.level.max_turns}",
            value_size=theme.FONT_SMALL,
        )
        self._draw_stat(
            surface,
            782,
            112,
            80,
            "牛",
            f"{self.sim.caught_count} / {len(self.sim.cows)}",
            value_size=theme.FONT_SMALL,
        )
        if self.phase == "demo":
            self.demo_pause_button.draw(surface, self.fonts)
            self.demo_exit_button.draw(surface, self.fonts)
            progress = (
                "完成"
                if self.demo_done
                else f"{self.demo_index} / {len(self.demo_actions)}"
            )
            self._draw_stat(
                surface, 1060, 112, 160, "演示", progress, value_size=theme.FONT_SMALL
            )
        else:
            for button in (
                self.undo_button,
                self.restart_button,
                self.predict_button,
                self.alert_button,
            ):
                button.draw(surface, self.fonts)

    def _draw_stat(self, surface, x, y, width, label, value, *, value_size=theme.FONT_H3):
        rect = pygame.Rect(x, y, width, 44)
        theme.rounded_rect(surface, rect, theme.PANEL_BG, radius=12)
        theme.rounded_rect(surface, rect, theme.PANEL_BORDER, radius=12, width=2)
        theme.draw_text(
            surface, self.fonts, label, (rect.left + 8, rect.centery), theme.FONT_TINY,
            theme.INK_LIGHT, anchor="midleft",
        )
        theme.draw_text(
            surface, self.fonts, value, (rect.right - 8, rect.centery), value_size,
            theme.INK, anchor="midright", bold=True,
        )

    def _draw_board(self, surface: pygame.Surface) -> None:
        view = BoardView(
            level=self.level,
            sim=self.sim,
            animator=self.animator,
            show_prediction=(
                self.show_prediction
                and not self.sim.status.is_finished
                and self.phase == "run"
            ),
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
        panel = self.panel_rect
        theme.panel(surface, panel)
        left = panel.left + 24
        width = panel.width - 48
        y = panel.top + 20
        self.hint_card_rect = None
        self.hint_next_button.visible = False

        label_map = {
            "main": f"第 {self.level_number:02d} 关",
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
        y += 18

        if self.phase == "demo":
            self._draw_demo_panel(surface, left, width)
            return

        objective = self.level.learning_objective if self.show_hints else ""
        if objective:
            theme.draw_text(
                surface, self.fonts, "本关学习", (left, y), theme.FONT_TINY,
                theme.SKY_DEEP, bold=True,
            )
            y += 24
            wrapped = self.fonts.wrap(objective, theme.FONT_BODY, width, theme.INK)
            surface.blit(wrapped, (left, y))
            y += wrapped.get_height() + 12

        if self.level.description and self.level.description != objective:
            if objective:
                theme.draw_text(
                    surface, self.fonts, "关卡说明", (left, y), theme.FONT_TINY,
                    theme.INK_LIGHT,
                )
                y += 24
            wrapped = self.fonts.wrap(
                self.level.description, theme.FONT_SMALL, width, theme.INK_SOFT
            )
            surface.blit(wrapped, (left, y))
            y += wrapped.get_height() + 12

        ui.draw_pill(
            surface, self.fonts, "目标：抓住全部牛", (left + 76, y + 18), theme.LEAF_DARK
        )
        y += 46
        theme.draw_text(
            surface,
            self.fonts,
            "金色出口：牛可进入，农夫不可通行",
            (left, y),
            theme.FONT_TINY,
            theme.INK_LIGHT,
        )
        y += 32
        if self.sim.near_exit(3) and not self.sim.status.is_finished:
            ui.draw_pill(
                surface, self.fonts, "出口就在附近！", (left + 80, y + 12), EXIT_COLOR
            )
            y += 34

        if self.show_hints and self.phase == "run":
            texts = self._hint_texts()
            if texts:
                self._draw_hint_card(surface, left, max(438, y), width)

    def _draw_demo_panel(self, surface: pygame.Surface, left: int, width: int) -> None:
        y = self.panel_rect.top + 130
        theme.draw_text(
            surface,
            self.fonts,
            "电脑演示通关路线",
            (left, y),
            theme.FONT_H2,
            theme.INK,
            bold=True,
        )
        y += 42
        body = self.fonts.wrap(
            "求解器使用与本局完全相同的规则。\n"
            "演示期间不响应玩家操作，也不会计入成绩或解锁记录。",
            theme.FONT_SMALL,
            width,
            theme.INK_SOFT,
        )
        surface.blit(body, (left, y))
        y += body.get_height() + 18
        ui.draw_pill(
            surface,
            self.fonts,
            "不计入成绩",
            (left + 76, y + 4),
            theme.SKY_DEEP,
        )
        y += 34

        progress = pygame.Rect(left, y, width, 142)
        theme.rounded_rect(surface, progress, theme.CREAM, radius=16)
        theme.rounded_rect(surface, progress, theme.PANEL_BORDER, radius=16, width=2)
        theme.draw_text(
            surface,
            self.fonts,
            "演示进度",
            (progress.left + 18, progress.top + 14),
            theme.FONT_TINY,
            theme.INK_LIGHT,
        )
        total = len(self.demo_actions)
        theme.draw_text(
            surface,
            self.fonts,
            f"{self.demo_index} / {total}",
            (progress.left + 18, progress.top + 40),
            theme.FONT_H1,
            theme.INK,
            bold=True,
        )
        if self.demo_done:
            state_text = "演示完成"
            state_color = theme.LEAF_DARK
        elif self.demo_paused:
            state_text = "已暂停"
            state_color = theme.CLAY_DARK
        else:
            state_text = "自动播放中"
            state_color = theme.SKY_DEEP
        ui.draw_pill(
            surface,
            self.fonts,
            state_text,
            (progress.right - 90, progress.top + 55),
            state_color,
        )
        last_text = (
            f"上一步：{self.demo_last_action.label}"
            if self.demo_last_action is not None
            else "准备开始演示"
        )
        theme.draw_text(
            surface,
            self.fonts,
            last_text,
            (progress.left + 18, progress.top + 108),
            theme.FONT_SMALL,
            theme.INK_SOFT,
        )

        card_y = progress.bottom + 20
        card = pygame.Rect(left, card_y, width, 166)
        theme.rounded_rect(surface, card, theme.CREAM, radius=16)
        theme.rounded_rect(surface, card, theme.PANEL_BORDER, radius=16, width=2)
        theme.draw_text(
            surface,
            self.fonts,
            "演示控制",
            (card.left + 18, card.top + 14),
            theme.FONT_TINY,
            theme.INK_LIGHT,
        )
        lines = [
            "顶部「暂停 / 继续」：冻结或恢复自动播放",
            "顶部「退出演示」：立即回到失败时的局面",
            "演示结束后自动恢复，并打开演示结束弹窗",
        ]
        line_y = card.top + 46
        for line in lines:
            theme.draw_text(
                surface,
                self.fonts,
                line,
                (card.left + 18, line_y),
                theme.FONT_SMALL,
                theme.INK_SOFT,
            )
            line_y += 32

    def _draw_hint_card(
        self, surface: pygame.Surface, left: int, top: int, width: int
    ) -> None:
        texts = self._hint_texts()
        if not texts:
            return
        index = min(self.hint_index, len(texts) - 1)
        multi = bool(self.level.hint_text)
        height = 190 if multi else 140
        card = pygame.Rect(left, top, width, height)
        theme.soft_shadow(surface, card, radius=18, alpha=32, offset=(0, 5))
        theme.rounded_rect(surface, card, theme.SKY_PALE, radius=18)
        theme.rounded_rect(surface, card, theme.SKY_DEEP, radius=18, width=3)
        label = (
            "教学提示"
            if self.level.learning_objective or "教学" in self.level.tags
            else "关卡提示"
        )
        ui.draw_pill(
            surface, self.fonts, label, (card.left + 58, card.top + 25), theme.SKY_DEEP
        )

        next_visible = multi and index < len(texts) - 1
        self.hint_next_button.rect = pygame.Rect(card.right - 120, card.top + 8, 104, 36)
        self.hint_next_button.visible = next_visible
        if next_visible:
            self.hint_next_button.draw(surface, self.fonts)

        if multi:
            counter = self.fonts.render(
                f"{index + 1}/{len(texts)}", theme.FONT_TINY, theme.INK_LIGHT, True
            )
            if next_visible:
                counter_x = self.hint_next_button.rect.left - 16 - counter.get_width()
            else:
                counter_x = card.right - 20 - counter.get_width()
            surface.blit(counter, (counter_x, card.top + 15))

        body_text = texts[index]
        body = self.fonts.wrap(body_text, theme.FONT_BODY, card.width - 40, theme.INK)
        max_height = 96 if multi else 72
        if body.get_height() > max_height:
            body = self.fonts.wrap(body_text, theme.FONT_SMALL, card.width - 40, theme.INK)
        surface.blit(body, (card.left + 20, card.top + 56))

        if multi:
            dot_y = card.bottom - 25
            for dot_index in range(len(texts)):
                color = theme.SKY_DEEP if dot_index == index else theme.PANEL_BORDER
                pygame.draw.circle(
                    surface,
                    color,
                    (card.left + 24 + dot_index * 18, dot_y),
                    4 if dot_index == index else 3,
                )
            auto_text = (
                "提示自动推进 · 也可点「下一条」"
                if next_visible
                else "提示已全部展开"
            )
            auto = self.fonts.render(auto_text, theme.FONT_TINY, theme.INK_LIGHT)
            surface.blit(auto, (card.left + 150, dot_y - auto.get_height() // 2))

        self.hint_card_rect = card

    def _draw_footer(self, surface: pygame.Surface) -> None:
        if self.phase == "demo":
            draw_footer(
                surface,
                self.fonts,
                "演示中不响应玩家操作 · 顶部按钮可暂停/继续或退出演示",
                x=self.stage_origin[0],
            )
            return
        draw_footer(
            surface,
            self.fonts,
            "WASD/方向键 转向 · 空格 前进 · U 撤销 · R 重开 · P 预测",
            x=self.stage_origin[0],
        )
        if self.show_prediction and self.level.prediction_steps > 0 and self.toast_timer <= 0:
            text = self.fonts.wrap(
                f"半透明脚印 = 牛接下来 {self.level.prediction_steps} 回合的路线（基于农夫当前位置与朝向不变）",
                theme.FONT_TINY,
                theme.BOARD_SIZE,
                theme.INK_LIGHT,
            )
            surface.blit(text, (self.stage_origin[0], 760))

    def _draw_toast(self, surface: pygame.Surface) -> None:
        body = self.fonts.wrap(self.toast_text, theme.FONT_SMALL, 460, theme.WHITE_WARM)
        rect = pygame.Rect(0, 0, body.get_width() + 40, body.get_height() + 24)
        rect.center = (self.stage_origin[0] + theme.BOARD_SIZE // 2, 770)
        theme.soft_shadow(surface, rect, radius=14, alpha=60, offset=(0, 4))
        theme.rounded_rect(surface, rect, theme.CLAY, radius=14)
        surface.blit(body, (rect.left + 20, rect.top + 12))
