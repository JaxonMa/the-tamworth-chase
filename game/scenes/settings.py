"""Settings screen: sound, effects, prediction and local progress resets."""

from __future__ import annotations

from typing import List

import pygame

from .. import theme, ui
from .base import Scene, draw_background, draw_footer, draw_header, make_back_button


class SettingsScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.back_button = make_back_button()
        self.modal: ui.Modal | None = None
        self.pending_reset = ""
        self.widgets: List = []

    def on_enter(self) -> None:
        store = self.store
        self.sound_toggle = ui.Toggle(
            pygame.Rect(118, 210, 520, 46), "音效", "sound", bool(store.get_setting("sound", True))
        )
        self.volume_slider = ui.Slider(
            pygame.Rect(118, 262, 520, 54),
            "音量",
            "volume",
            float(store.get_setting("volume", 0.6)),
            0.0,
            1.0,
            0.05,
        )
        self.effects_toggle = ui.Toggle(
            pygame.Rect(118, 336, 520, 46),
            "低配模式（关闭粒子与复杂动效）",
            "low_effects",
            bool(store.get_setting("low_effects", False)),
        )
        self.preview_toggle = ui.Toggle(
            pygame.Rect(118, 398, 520, 46),
            "默认显示路径预测",
            "preview",
            bool(store.get_setting("preview", True)),
        )
        self.alerts_toggle = ui.Toggle(
            pygame.Rect(118, 454, 520, 46),
            "显示牛的警觉图标",
            "alerts",
            bool(store.get_setting("alerts", True)),
        )
        self.hints_toggle = ui.Toggle(
            pygame.Rect(118, 500, 520, 46),
            "显示教学目标与提示",
            "hints",
            bool(store.get_setting("hints", True)),
        )
        self.reset_main_button = ui.Button(
            pygame.Rect(118, 564, 250, 46), "重置主线进度", "reset_main", style="ghost"
        )
        self.widgets = [
            self.sound_toggle,
            self.volume_slider,
            self.effects_toggle,
            self.preview_toggle,
            self.alerts_toggle,
            self.hints_toggle,
        ]

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.modal is not None:
            action = self.modal.handle_event(event)
            if action:
                self._modal_action(action)
            return
        if self.back_button.handle_event(event):
            self.app.open_scene("menu")
            return
        for widget in self.widgets:
            changed = widget.handle_event(event)
            if changed:
                self._apply(widget)
        action = self.reset_main_button.handle_event(event)
        if action:
            self._ask_reset(action)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.open_scene("menu")

    def _apply(self, widget) -> None:
        if widget is self.sound_toggle:
            self.store.set_setting("sound", widget.value)
            self.app.sound.set_enabled(widget.value)
        elif widget is self.volume_slider:
            self.store.set_setting("volume", round(widget.value, 2))
            self.app.sound.set_volume(widget.value)
            self.app.sound.play("click")
        elif widget is self.effects_toggle:
            self.store.set_setting("low_effects", widget.value)
        elif widget is self.preview_toggle:
            self.store.set_setting("preview", widget.value)
        elif widget is self.alerts_toggle:
            self.store.set_setting("alerts", widget.value)
        elif widget is self.hints_toggle:
            self.store.set_setting("hints", widget.value)

    def _ask_reset(self, key: str) -> None:
        self.app.sound.play("click")
        title = "重置主线进度？"
        body = "所有关卡的通关记录、最好回合数和评价都会清空。\n这个操作无法撤销。"
        confirm = "确认重置"
        self.pending_reset = "main"
        self.modal = ui.Modal(
            title,
            body,
            accent=theme.CLAY,
            buttons=[
                ui.Button(pygame.Rect(0, 0, 150, 50), "取消", "cancel", style="ghost"),
                ui.Button(pygame.Rect(0, 0, 170, 50), confirm, "confirm", style="danger"),
            ],
            width=600,
            height=320,
        )

    def _modal_action(self, action: str) -> None:
        self.modal = None
        if action != "confirm":
            return
        self.store.reset_main()
        self.pending_reset = ""
        self.app.sound.play("unlock")
        self.app.open_scene("settings")

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        super().update(dt)
        if self.modal is not None:
            self.modal.update(pygame.mouse.get_pos())

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        draw_header(surface, self.fonts, "设置", "所有设置都保存在本地")
        self.back_button.draw(surface, self.fonts)

        panel_top = 150
        panel_height = 500
        theme.panel(surface, pygame.Rect(80, panel_top, 620, panel_height))
        for widget in self.widgets:
            widget.draw(surface, self.fonts)
        ui.draw_divider(surface, 550, 118, 520)
        self.reset_main_button.draw(surface, self.fonts)

        info = pygame.Rect(740, panel_top, 460, panel_height)
        theme.panel(surface, info)
        theme.draw_text(surface, self.fonts, "关于", (info.left + 26, info.top + 22), theme.FONT_H2, theme.INK, bold=True)
        ui.draw_divider(surface, info.top + 70, info.left + 26, info.width - 52)
        lines = [
            "游戏名：The Tamworth Chase",
            "中文副标题：《塔姆沃斯追逐》",
            "版本：1.7.1",
            "界面字体：CEF Fonts CJK（本地内置）",
            "全部美术由程序绘制，运行时不联网。",
            "",
            "操作：W/↑ 朝上，S/↓ 朝下，",
            "A/← 朝左，D/→ 朝右，",
            "空格前进，U 撤销，R 重开，P 预测。",
            "同方向转向无效；出口对农夫不可通行。",
        ]
        content_left = info.left + 26
        content_width = info.width - 52
        y = info.top + 88
        for line in lines:
            if not line:
                y += 34
                continue
            wrapped = self.fonts.wrap(
                line, theme.FONT_SMALL, content_width, theme.INK_SOFT
            )
            surface.blit(wrapped, (content_left, y))
            y += wrapped.get_height() + 10
        if self.modal is not None:
            self.modal.draw(surface, self.fonts)
        draw_footer(surface, self.fonts, "设置会在关闭后自动保存")
