"""Local daily seed challenge: one meadow per calendar day, stored locally."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pygame

from .. import theme, ui
from ..daily import date_key
from .base import Scene, draw_background, draw_footer, draw_header, make_back_button, make_thumbnail


class DailyScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.back_button = make_back_button()
        self.level = None
        self.thumbnail: Optional[pygame.Surface] = None
        self.start_button = ui.Button(
            pygame.Rect(0, 0, 208, 45), "开始今日挑战", "start", style="primary", font_size=theme.FONT_H3
        )
        self.start_button.rect.topleft = (510, 552)

    def on_enter(self) -> None:
        self.level = self.app.daily_level()
        self.thumbnail = make_thumbnail(self.cache, self.level, cell=11)
        self.start_button.enabled = True

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_button.handle_event(event):
            self.app.open_scene("menu")
            return
        if self.start_button.handle_event(event):
            if self.level is not None:
                self.app.sound.play("click")
                self.app.start_level(
                    self.level,
                    mode="daily",
                    daily_key=date_key(),
                    return_to="daily",
                )
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.open_scene("menu")

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        today = date.today()
        draw_header(
            surface,
            self.fonts,
            "每日挑战",
            f"{today.year} 年 {today.month} 月 {today.day} 日 · 本地种子",
            badge="每日",
            badge_color=theme.SKY_DEEP,
        )
        self.back_button.draw(surface, self.fonts)

        # today card
        card = pygame.Rect(240, 112, 544, 384)
        theme.soft_shadow(surface, card, radius=26, alpha=44, offset=(0, 8))
        theme.rounded_rect(surface, card, theme.PANEL_BG, radius=26)
        theme.rounded_rect(surface, card, theme.SKY_DEEP, radius=26, width=3)
        theme.draw_text(
            surface, self.fonts, f"{today.month} 月 {today.day} 日的牧场", (card.left + 26, card.top + 18),
            theme.FONT_H2, theme.INK, bold=True,
        )
        theme.draw_text(
            surface,
            self.fonts,
            "同一天打开，永远是同一片牧场。",
            (card.left + 26, card.top + 50),
            theme.FONT_SMALL,
            theme.INK_SOFT,
        )
        if self.thumbnail is not None:
            frame = self.thumbnail.get_rect(center=(card.centerx, card.top + 206))
            theme.rounded_rect(surface, frame.inflate(10, 10), theme.CREAM_DARK, radius=10)
            surface.blit(self.thumbnail, frame)
            theme.rounded_rect(surface, frame.inflate(10, 10), theme.PANEL_BORDER, radius=10, width=2)

        record = self.store.daily_result(date_key(today))
        if record and record.get("cleared"):
            theme.draw_text(
                surface,
                self.fonts,
                f"今日最好成绩：{record.get('turns')} 回合",
                (card.centerx, card.top + 274),
                theme.FONT_H3,
                theme.LEAF_DARK,
                anchor="center",
                bold=True,
            )
        else:
            theme.draw_text(
                surface,
                self.fonts,
                "今天还没有完成挑战。",
                (card.centerx, card.top + 274),
                theme.FONT_SMALL,
                theme.INK_LIGHT,
                anchor="center",
            )

        # last seven days
        history = pygame.Rect(240, 512, 544, 77)
        theme.rounded_rect(surface, history, theme.CREAM, radius=18)
        theme.rounded_rect(surface, history, theme.PANEL_BORDER, radius=18, width=2)
        theme.draw_text(
            surface, self.fonts, "最近七天", (history.left + 16, history.top + 10), theme.FONT_TINY, theme.INK_LIGHT
        )
        for index in range(7):
            day = today - timedelta(days=6 - index)
            key = date_key(day)
            result = self.store.daily_result(key)
            cell = pygame.Rect(history.left + 16 + index * 74, history.top + 29, 67, 44)
            done = bool(result and result.get("cleared"))
            color = theme.LEAF_LIGHT if done else theme.CREAM_DARK
            theme.rounded_rect(surface, cell, color, radius=10)
            theme.draw_text(
                surface,
                self.fonts,
                f"{day.month}/{day.day}",
                (cell.centerx, cell.top + 6),
                theme.FONT_TINY,
                theme.INK_SOFT,
                anchor="midtop",
            )
            label = f"{result['turns']} 回合" if done else "—"
            theme.draw_text(
                surface,
                self.fonts,
                label,
                (cell.centerx, cell.top + 23),
                theme.FONT_TINY,
                theme.INK if done else theme.INK_LIGHT,
                anchor="midtop",
            )
        self.start_button.rect.topleft = (card.centerx - 104, card.bottom - 59)
        self.start_button.draw(surface, self.fonts)
        draw_footer(surface, self.fonts, "每日挑战只用本地日期作为种子，不上传、不联网")
