"""Achievements screen."""

from __future__ import annotations

from typing import List

import pygame

from .. import achievements as achievement_data
from .. import theme, ui
from .base import Scene, draw_background, draw_footer, draw_header, make_back_button


class AchievementScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.back_button = make_back_button()
        self.cards: List[ui.Card] = []
        self.entries = list(achievement_data.ACHIEVEMENTS)

    def on_enter(self) -> None:
        self.cards = []
        columns = 3
        width, height = 358, 190
        gap_x, gap_y = 24, 26
        start_x, start_y = 62, 150
        for index, achievement in enumerate(self.entries):
            row, col = divmod(index, columns)
            rect = pygame.Rect(
                start_x + col * (width + gap_x), start_y + row * (height + gap_y), width, height
            )
            self.cards.append(
                ui.Card(
                    rect=rect,
                    title=achievement.name,
                    key=achievement.achievement_id,
                    accent=theme.SUN,
                    completed=self.store.has_achievement(achievement.achievement_id),
                )
            )

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_button.handle_event(event):
            self.app.open_scene("menu")
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.open_scene("menu")

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        unlocked = sum(1 for entry in self.entries if self.store.has_achievement(entry.achievement_id))
        draw_header(
            surface,
            self.fonts,
            "成就",
            f"已解锁 {unlocked} / {len(self.entries)}",
            badge="成就",
            badge_color=theme.SUN,
        )
        self.back_button.draw(surface, self.fonts)
        for card, achievement in zip(self.cards, self.entries):
            self._draw_card(surface, card, achievement)
        draw_footer(surface, self.fonts, "成就保存在本地存档里，与主线进度分开记录")

    def _draw_card(self, surface: pygame.Surface, card: ui.Card, achievement) -> None:
        unlocked = self.store.has_achievement(achievement.achievement_id)
        rect = card.rect
        background = theme.PANEL_BG if unlocked else theme.CREAM_DARK
        theme.soft_shadow(surface, rect, radius=18, alpha=30, offset=(0, 6))
        theme.rounded_rect(surface, rect, background, radius=18)
        theme.rounded_rect(
            surface, rect, theme.SUN if unlocked else theme.PANEL_BORDER, radius=18, width=3 if unlocked else 2
        )
        medal_center = (rect.left + 54, rect.centery)
        pygame.draw.circle(surface, theme.SUN if unlocked else theme.CREAM_DARK, medal_center, 30)
        pygame.draw.circle(surface, theme.SUN if unlocked else theme.PANEL_BORDER, medal_center, 30, 3)
        if unlocked:
            pygame.draw.lines(
                surface,
                theme.WHITE_WARM,
                False,
                [
                    (medal_center[0] - 12, medal_center[1]),
                    (medal_center[0] - 3, medal_center[1] + 9),
                    (medal_center[0] + 13, medal_center[1] - 10),
                ],
                4,
            )
        else:
            pygame.draw.rect(
                surface,
                theme.INK_LIGHT,
                pygame.Rect(medal_center[0] - 10, medal_center[1] - 2, 20, 16),
                border_radius=4,
            )
            pygame.draw.arc(
                surface,
                theme.INK_LIGHT,
                pygame.Rect(medal_center[0] - 7, medal_center[1] - 14, 14, 18),
                0,
                3.14,
                3,
            )
        theme.draw_text(
            surface,
            self.fonts,
            achievement.name,
            (rect.left + 96, rect.top + 22),
            theme.FONT_H3,
            theme.INK if unlocked else theme.INK_LIGHT,
            bold=True,
        )
        description = self.fonts.wrap(
            achievement.description, theme.FONT_SMALL, rect.width - 108, theme.INK_SOFT
        )
        surface.blit(description, (rect.left + 96, rect.top + 58))
        hint = self.fonts.wrap(achievement.hint, theme.FONT_TINY, rect.width - 116, theme.INK_LIGHT)
        surface.blit(hint, (rect.left + 96, rect.bottom - 64))
        date_text = self.store.achievements.get(achievement.achievement_id)
        if unlocked and date_text:
            theme.draw_text(
                surface,
                self.fonts,
                date_text[:10],
                (rect.right - 16, rect.top + 16),
                theme.FONT_TINY,
                theme.INK_LIGHT,
                anchor="topright",
            )
