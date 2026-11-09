"""Challenge mode: curated side puzzles with local best-step records."""

from __future__ import annotations

from typing import List, Optional

import pygame

from .. import theme, ui
from ..models import Level
from .base import Scene, draw_background, draw_footer, draw_header, make_back_button, make_thumbnail


class ChallengeScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.back_button = make_back_button()
        self.cards: List[ui.Card] = []
        self.levels: List[Level] = []
        self.hovered: Optional[str] = None

    def on_enter(self) -> None:
        self.levels = list(self.app.challenges)
        self.cards = []
        self.thumbnails = {}
        width, height = 286, 189
        gap_x, gap_y = 19, 19
        start_x, start_y = 50, 120
        for index, level in enumerate(self.levels):
            row, col = divmod(index, 3)
            rect = pygame.Rect(
                start_x + col * (width + gap_x),
                start_y + row * (height + gap_y),
                width,
                height,
            )
            best = self.store.challenge_best(level.level_id)
            card = ui.Card(
                rect=rect,
                title="",
                key=level.level_id,
                accent=theme.CLAY,
            )
            self.cards.append(card)
            self.thumbnails[level.level_id] = make_thumbnail(self.cache, level, cell=6)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_button.handle_event(event):
            self.app.open_scene("menu")
            return
        for card in self.cards:
            action = card.handle_event(event)
            if action:
                level = self.app.challenges_by_id.get(action)
                if level is not None:
                    self.app.sound.play("click")
                    self.app.start_level(
                        level,
                        mode="challenge",
                        challenge_key=level.level_id,
                        return_to="challenge",
                    )
                return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.open_scene("menu")

    def update(self, dt: float) -> None:
        super().update(dt)
        self.hovered = next((card.key for card in self.cards if card.hovered), None)

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        cleared = sum(
            1 for level in self.levels if self.store.challenge_best(level.level_id) is not None
        )
        draw_header(
            surface,
            self.fonts,
            "挑战模式",
            f"完成 {cleared} / {len(self.levels)} 个挑战",
            badge="挑战",
            badge_color=theme.CLAY,
        )
        self.back_button.draw(surface, self.fonts)

        for card in self.cards:
            self._draw_card(surface, card)
        draw_footer(surface, self.fonts, "挑战不占用主线进度 · 记录本地最好回合数")
        if not self.levels:
            theme.draw_text(
                surface,
                self.fonts,
                "还没有挑战数据。",
                (512, 320),
                theme.FONT_H2,
                theme.INK_LIGHT,
                anchor="center",
            )

    def _draw_card(self, surface: pygame.Surface, card: ui.Card) -> None:
        card.draw(surface, self.fonts)
        level = self.app.challenges_by_id.get(card.key)
        if level is None:
            return
        rect = card.rect
        thumbnail = self.thumbnails.get(card.key)
        if thumbnail is not None:
            frame = thumbnail.get_rect(topleft=(rect.left + 27, rect.top + 13))
            theme.rounded_rect(surface, frame.inflate(6, 6), theme.CREAM_DARK, radius=6)
            surface.blit(thumbnail, frame)
            theme.rounded_rect(surface, frame.inflate(6, 6), theme.PANEL_BORDER, radius=6, width=2)
        text_left = rect.left + 106
        theme.draw_text(
            surface,
            self.fonts,
            level.name,
            (text_left, rect.top + 14),
            theme.FONT_H3,
            theme.INK,
            bold=True,
        )
        best_value = self.store.challenge_best(card.key)
        theme.draw_text(
            surface,
            self.fonts,
            f"最好 {best_value} 回合" if best_value is not None else "未挑战",
            (rect.right - 14, rect.top + 18),
            theme.FONT_SMALL,
            theme.INK_SOFT,
            anchor="topright",
        )
        description = self.fonts.wrap(level.description, theme.FONT_SMALL, rect.width - 122, theme.INK_SOFT)
        surface.blit(description, (text_left, rect.top + 40))
        best = self.store.challenge_best(card.key)
        theme.draw_text(
            surface,
            self.fonts,
            f"最好成绩：{best} 回合" if best is not None else "还没有完成过",
            (rect.left + 30, rect.bottom - 32),
            theme.FONT_SMALL,
            theme.INK_SOFT,
        )
        tag = " / ".join(level.tags[:2]) if level.tags else "挑战"
        ui.draw_pill(surface, self.fonts, tag, (rect.right - 56, rect.bottom - 27), theme.CLAY)
