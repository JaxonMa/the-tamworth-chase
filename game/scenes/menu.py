"""Main menu."""

from __future__ import annotations

import math
from typing import List, Tuple

import pygame

from .. import art, theme, ui
from ..models import CowPersonality, Direction, TileKind
from .base import Scene, draw_footer

TITLE = "The Tamworth Two"
SUBTITLE = "塔姆沃斯的两个小家伙"
TAGLINE = "在牧场上放下篱笆，让农夫抓住那头牛。"


class MenuScene(Scene):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.buttons: List[ui.Button] = []
        self.close_button: ui.Button | None = None
        self.modal: ui.Modal | None = None
        self.modal_action = ""
        self._scaled: dict = {}
        self._petals = [
            (0.2, 0.3, 0.5 + 0.1 * i, 1.0 + 0.15 * i) for i in range(9)
        ]

    # ------------------------------------------------------------------
    def on_enter(self) -> None:
        self.buttons = self._build_buttons()
        self._scaled = {
            "farmer": pygame.transform.smoothscale(self.cache.farmer(Direction.SOUTH), (118, 118)),
            "cow": pygame.transform.smoothscale(
                self.cache.cow(Direction.WEST, CowPersonality.NORMAL), (124, 124)
            ),
            "hat": art.build_hat(52),
            "bale": self.cache.prop("obstacle"),
            "fence": art.build_fence(58),
        }
        if not self.store.get_setting("seen_welcome"):
            self.store.set_setting("seen_welcome", True)

    def _build_buttons(self) -> List[ui.Button]:
        entries: List[Tuple[str, str, str]] = [("main", "主线关卡", "primary")]
        features = self.app.features
        if "tutorial" in features:
            entries.append(("tutorial", "新手教程", "sky"))
        if "challenge" in features:
            entries.append(("challenge", "挑战模式", "default"))
        if "daily" in features:
            entries.append(("daily", "每日挑战", "default"))
        if "editor" in features:
            entries.append(("editor", "关卡编辑器", "default"))
        if "achievement" in features:
            entries.append(("achievement", "成就", "default"))
        entries.append(("settings", "设置", "ghost"))
        entries.append(("quit", "退出游戏", "ghost"))

        buttons = []
        y = 330
        for key, label, style in entries:
            buttons.append(
                ui.Button(
                    pygame.Rect(72, y, 330, 50),
                    label,
                    key,
                    style=style,
                    font_size=theme.FONT_BODY,
                )
            )
            y += 58
        return buttons

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.modal is not None:
            action = self.modal.handle_event(event)
            if action:
                self.modal = None
                if action == "quit":
                    self.app.quit()
            return
        for button in self.buttons:
            action = button.handle_event(event)
            if action:
                self._activate(action)
                return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._activate("quit")

    def _activate(self, key: str) -> None:
        self.app.sound.play("click")
        if key == "quit":
            self.modal = ui.Modal(
                "要离开牧场了吗？",
                "今天的阳光很好，随时欢迎回来。",
                accent=theme.LEAF,
                buttons=[
                    ui.Button(pygame.Rect(0, 0, 150, 50), "再玩一会", "stay", style="primary"),
                    ui.Button(pygame.Rect(0, 0, 150, 50), "退出", "quit", style="ghost"),
                ],
                width=520,
                height=270,
            )
            return
        self.app.open_scene(key)

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        super().update(dt)
        if self.modal is not None:
            self.modal.update(pygame.mouse.get_pos())

    def draw(self, surface: pygame.Surface) -> None:
        art.draw_meadow_background(surface, self.time * 0.6)
        self._draw_title(surface)
        self._draw_illustration(surface)
        for button in self.buttons:
            button.draw(surface, self.fonts)
        draw_footer(
            surface,
            self.fonts,
            "The Tamworth Two · 离线单机 · 所有资源随游戏一起打包",
        )
        if self.modal is not None:
            self.modal.draw(surface, self.fonts)

    # ------------------------------------------------------------------
    def _draw_title(self, surface: pygame.Surface) -> None:
        card = pygame.Rect(52, 38, 440, 268)
        theme.soft_shadow(surface, card, radius=28, alpha=36, offset=(0, 8))
        theme.rounded_rect(surface, card, theme.WHITE_WARM, radius=28)
        theme.rounded_rect(surface, card, theme.PANEL_BORDER, radius=28, width=2)

        # small leaf badge
        pygame.draw.circle(surface, theme.LEAF, (card.left + 34, card.top + 34), 9)
        pygame.draw.circle(surface, theme.LEAF_DARK, (card.left + 34, card.top + 34), 9, 2)

        title = self.fonts.render(TITLE, 46, theme.INK, True)
        surface.blit(title, (card.left + 28, card.top + 26))
        theme.draw_text(
            surface, self.fonts, SUBTITLE, (card.left + 30, card.top + 84), theme.FONT_H3, theme.LEAF_DARK
        )
        pygame.draw.line(
            surface,
            theme.PANEL_BORDER,
            (card.left + 30, card.top + 128),
            (card.right - 30, card.top + 128),
            2,
        )
        text = self.fonts.wrap(TAGLINE, theme.FONT_SMALL, card.width - 60, theme.INK_SOFT)
        surface.blit(text, (card.left + 30, card.top + 142))
        theme.draw_text(
            surface,
            self.fonts,
            "手绘田园 · 网格解谜",
            (card.left + 30, card.bottom - 30),
            theme.FONT_TINY,
            theme.INK_LIGHT,
        )

    def _draw_illustration(self, surface: pygame.Surface) -> None:
        center = (900, 470)
        # soft meadow circle
        meadow = pygame.Surface((660, 560), pygame.SRCALPHA)
        pygame.draw.ellipse(meadow, (*theme.GRASS_LIGHT, 220), (0, 120, 660, 420))
        pygame.draw.ellipse(meadow, (*theme.GRASS, 190), (20, 150, 620, 370))
        surface.blit(meadow, (center[0] - 330, center[1] - 300))

        # trees
        for x, y, scale in ((600, 456, 1.85), (1206, 496, 1.45)):
            tree = pygame.transform.smoothscale(art.build_tree(64), (int(64 * scale), int(64 * scale)))
            surface.blit(tree, tree.get_rect(midbottom=(x, y)))

        # fence
        fence = self._scaled["fence"]
        for index in range(11):
            surface.blit(fence, (626 + index * 58, 690))

        bob = math.sin(self.time * 2.2) * 4
        cow_bob = math.sin(self.time * 1.8 + 1.2) * 3
        farmer_rect = self._scaled["farmer"].get_rect(midbottom=(800, 676 + bob))
        cow_rect = self._scaled["cow"].get_rect(midbottom=(1040, 686 + cow_bob))
        shadow = pygame.Surface((120, 30), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (*theme.SHADOW, 40), shadow.get_rect())
        surface.blit(shadow, (farmer_rect.centerx - 60, farmer_rect.bottom - 16))
        surface.blit(shadow, (cow_rect.centerx - 60, cow_rect.bottom - 14))
        surface.blit(self._scaled["farmer"], farmer_rect)
        surface.blit(self._scaled["cow"], cow_rect)

        # hay bale
        surface.blit(self._scaled["bale"], (930, 646))

        # drifting petals
        for index, (speed, phase, size, sway) in enumerate(self._petals):
            t = (self.time * 0.22 * speed + phase) % 1.0
            x = 640 + int(520 * ((index * 0.13 + phase) % 1.0)) + int(math.sin(self.time + index) * 10)
            y = 180 + int(420 * t)
            color = (theme.PINK, theme.SUN_LIGHT, theme.WHITE_WARM)[index % 3]
            pygame.draw.circle(surface, color, (x, y), int(3 * size))

        # little floating hearts above the pair
        for index in range(2):
            t = (self.time * 0.5 + index * 0.5) % 1.0
            alpha = int(255 * (1 - t))
            layer = pygame.Surface((24, 24), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*theme.CLAY_LIGHT, alpha), (8, 10), 6)
            pygame.draw.circle(layer, (*theme.CLAY_LIGHT, alpha), (16, 10), 6)
            pygame.draw.polygon(layer, (*theme.CLAY_LIGHT, alpha), [(2, 12), (22, 12), (12, 23)])
            surface.blit(layer, (880 + index * 46, 520 - int(60 * t)))
