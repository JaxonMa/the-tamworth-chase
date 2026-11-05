"""Campaign level selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pygame

from .. import theme, ui
from ..models import Level
from .base import Scene, draw_background, draw_footer, draw_header, make_back_button, make_thumbnail


@dataclass
class LevelCard:
    rect: pygame.Rect
    level: Level
    unlocked: bool
    index: int
    best_steps: Optional[int]
    rank: Optional[str]
    thumbnail: pygame.Surface
    hovered: bool = False

    def contains(self, pos) -> bool:
        return self.rect.collidepoint(pos)


class LevelSelectScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.cards: List[LevelCard] = []
        self.back_button = make_back_button()
        self.hover_card: Optional[LevelCard] = None

    def on_enter(self) -> None:
        self.cards = self._build_cards()

    # ------------------------------------------------------------------
    def _build_cards(self) -> List[LevelCard]:
        levels = self.app.levels
        cards: List[LevelCard] = []
        columns = 5
        card_w, card_h = 214, 300
        gap_x, gap_y = 22, 26
        start_x, start_y = 62, 138
        for index, level in enumerate(levels):
            row, col = divmod(index, columns)
            rect = pygame.Rect(
                start_x + col * (card_w + gap_x),
                start_y + row * (card_h + gap_y),
                card_w,
                card_h,
            )
            record = self.store.main_result(level.level_id)
            cards.append(
                LevelCard(
                    rect=rect,
                    level=level,
                    unlocked=self.store.is_main_unlocked(
                        [lvl.level_id for lvl in levels], level.level_id
                    ),
                    index=index,
                    best_steps=record.best_steps,
                    rank=record.rank.value if record.rank else None,
                    thumbnail=self._thumbnail(level),
                )
            )
        return cards

    def _thumbnail(self, level: Level) -> pygame.Surface:
        return make_thumbnail(self.cache, level)

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.back_button.handle_event(event):
            self.app.open_scene("menu")
            return
        if event.type == pygame.MOUSEMOTION:
            self.hover_card = next((card for card in self.cards if card.contains(event.pos)), None)
            for card in self.cards:
                card.hovered = card is self.hover_card
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for card in self.cards:
                if card.contains(event.pos):
                    if card.unlocked:
                        self.app.sound.play("click")
                        self.app.start_level(card.level, mode="main")
                    else:
                        self.app.sound.play("error")
                    return
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.open_scene("menu")

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        cleared = sum(1 for card in self.cards if card.best_steps is not None)
        draw_header(
            surface,
            self.fonts,
            "主线关卡",
            f"已通关 {cleared} / {len(self.cards)}",
            badge="主线",
            badge_color=theme.LEAF,
        )
        for card in self.cards:
            self._draw_card(surface, card)
        draw_footer(
            surface,
            self.fonts,
            "通关上一关即可解锁下一关 · 步数越少，评价越高",
        )
        self.back_button.draw(surface, self.fonts)
        if self.hover_card is not None and not self.hover_card.unlocked:
            ui.draw_tooltip(
                surface,
                self.fonts,
                "完成上一关后就能进入这片牧场。",
                pygame.mouse.get_pos(),
            )

    # ------------------------------------------------------------------
    def _draw_card(self, surface: pygame.Surface, card: LevelCard) -> None:
        lift = -4 if card.hovered and card.unlocked else 0
        rect = card.rect.move(0, lift)
        theme.soft_shadow(
            surface, rect, radius=20, alpha=44 if card.hovered else 30, offset=(0, 8)
        )
        background = theme.PANEL_BG if card.unlocked else theme.CREAM_DARK
        theme.rounded_rect(surface, rect, background, radius=20)
        border = theme.SUN_LIGHT if card.hovered and card.unlocked else theme.PANEL_BORDER
        theme.rounded_rect(surface, rect, border, radius=20, width=3 if card.hovered else 2)

        # number ribbon
        ribbon = pygame.Rect(rect.left, rect.top, rect.width, 44)
        theme.rounded_rect(surface, ribbon, theme.LEAF_LIGHT if card.unlocked else theme.CREAM_DARK, radius=20)
        pygame.draw.rect(
            surface,
            theme.LEAF_LIGHT if card.unlocked else theme.CREAM_DARK,
            pygame.Rect(ribbon.left, ribbon.bottom - 20, ribbon.width, 20),
        )
        theme.draw_text(
            surface,
            self.fonts,
            f"第 {card.index + 1:02d} 关",
            (rect.left + 14, rect.top + 9),
            theme.FONT_SMALL,
            theme.INK if card.unlocked else theme.INK_LIGHT,
            bold=True,
        )
        if card.rank:
            ui.draw_pill(
                surface,
                self.fonts,
                card.rank,
                (rect.right - 26, rect.top + 22),
                theme.RANK_COLORS.get(card.rank, theme.INK_LIGHT),
            )

        name = self.fonts.render(
            self.fonts.ellipsize(card.level.name, theme.FONT_H3, rect.width - 28),
            theme.FONT_H3,
            theme.INK if card.unlocked else theme.INK_LIGHT,
            True,
        )
        surface.blit(name, name.get_rect(midtop=(rect.centerx, rect.top + 54)))

        thumb_rect = card.thumbnail.get_rect(center=(rect.centerx, rect.top + 158))
        thumb_frame = thumb_rect.inflate(10, 10)
        theme.rounded_rect(surface, thumb_frame, theme.CREAM_DARK, radius=10)
        surface.blit(card.thumbnail, thumb_rect)
        theme.rounded_rect(surface, thumb_frame, theme.PANEL_BORDER, radius=10, width=2)

        detail = (
            f"最好成绩 {card.best_steps} 步"
            if card.best_steps is not None
            else ("障碍 " + str(card.level.obstacle_limit) + " · 步数 " + str(card.level.step_limit))
        )
        theme.draw_text(
            surface,
            self.fonts,
            detail,
            (rect.centerx, rect.bottom - 52),
            theme.FONT_TINY,
            theme.INK_SOFT,
            anchor="center",
        )
        hint = card.level.hint if card.unlocked else "完成上一关后解锁"
        hint = self.fonts.ellipsize(hint, theme.FONT_TINY, rect.width - 26)
        theme.draw_text(
            surface,
            self.fonts,
            hint,
            (rect.centerx, rect.bottom - 26),
            theme.FONT_TINY,
            theme.INK_LIGHT,
            anchor="center",
        )

        if not card.unlocked:
            veil = pygame.Surface(rect.size, pygame.SRCALPHA)
            veil.fill((*theme.CREAM, 168))
            surface.blit(veil, rect.topleft)
            # padlock
            cx, cy = rect.centerx, rect.centery
            pygame.draw.circle(surface, theme.CREAM_DARK, (cx, cy), 30)
            pygame.draw.circle(surface, theme.PANEL_BORDER, (cx, cy), 30, 2)
            body = pygame.Rect(cx - 15, cy - 2, 30, 22)
            theme.rounded_rect(surface, body, theme.INK_LIGHT, radius=6)
            pygame.draw.arc(
                surface,
                theme.INK_LIGHT,
                pygame.Rect(cx - 10, cy - 18, 20, 24),
                0.0,
                3.14,
                4,
            )
