"""Main menu."""

from __future__ import annotations

import math
from typing import List, Tuple

import pygame

from .. import art, theme, ui
from ..models import Direction
from .base import Scene, draw_footer

TITLE = "The Tamworth Chase"
SUBTITLE = "《塔姆沃斯追逐》"
TAGLINE = "守住出口，赶在牛逃走之前抓住它们。"


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
        notice = self.store.consume_notice()
        if notice:
            self.modal = ui.Modal(
                "存档迁移",
                notice,
                accent=theme.SKY_DEEP,
                buttons=[ui.Button(pygame.Rect(0, 0, 120, 40), "知道了", "dismiss", style="primary")],
                width=496,
                height=224,
            )
        self._scaled = {
            "farmer": pygame.transform.smoothscale(self.cache.farmer(Direction.SOUTH), (94, 94)),
            "cow": pygame.transform.smoothscale(
                self.cache.cow(Direction.WEST), (99, 99)
            ),
            "hat": art.build_hat(42),
            "bale": self.cache.prop("obstacle"),
            "fence": art.build_fence(46),
        }
        if not self.store.get_setting("seen_welcome"):
            self.store.set_setting("seen_welcome", True)

    def _build_buttons(self) -> List[ui.Button]:
        entries: List[Tuple[str, str, str]] = [("level_select", "主线关卡", "primary")]
        features = self.app.features
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
        y = 264
        for key, label, style in entries:
            buttons.append(
                ui.Button(
                    pygame.Rect(58, y, 264, 40),
                    label,
                    key,
                    style=style,
                    font_size=theme.FONT_BODY,
                )
            )
            y += 46
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
                    ui.Button(pygame.Rect(0, 0, 120, 40), "再玩一会", "stay", style="primary"),
                    ui.Button(pygame.Rect(0, 0, 120, 40), "退出", "quit", style="ghost"),
                ],
                width=416,
                height=216,
            )
            return
        self.app.open_scene(key)

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        super().update(dt)
        if self.modal is not None:
            self.modal.update(self.app.mouse_pos())

    def draw(self, surface: pygame.Surface) -> None:
        art.draw_meadow_background(surface, self.time * 0.6)
        self._draw_title(surface)
        self._draw_illustration(surface)
        for button in self.buttons:
            button.draw(surface, self.fonts)
        draw_footer(
            surface,
            self.fonts,
            "The Tamworth Chase · 离线单机 · 所有资源随游戏一起打包",
        )
        if self.modal is not None:
            self.modal.draw(surface, self.fonts)

    # ------------------------------------------------------------------
    def _draw_title(self, surface: pygame.Surface) -> None:
        card = pygame.Rect(42, 30, 352, 214)
        theme.soft_shadow(surface, card, radius=22, alpha=36, offset=(0, 6))
        theme.rounded_rect(surface, card, theme.WHITE_WARM, radius=22)
        theme.rounded_rect(surface, card, theme.PANEL_BORDER, radius=22, width=2)

        # small leaf badge
        pygame.draw.circle(surface, theme.LEAF, (card.left + 27, card.top + 27), 7)
        pygame.draw.circle(surface, theme.LEAF_DARK, (card.left + 27, card.top + 27), 7, 2)

        title = self.fonts.render(TITLE, 34, theme.INK, True)
        surface.blit(title, (card.left + 22, card.top + 21))
        theme.draw_text(
            surface, self.fonts, SUBTITLE, (card.left + 24, card.top + 67), theme.FONT_H3, theme.LEAF_DARK
        )
        pygame.draw.line(
            surface,
            theme.PANEL_BORDER,
            (card.left + 24, card.top + 102),
            (card.right - 24, card.top + 102),
            2,
        )
        text = self.fonts.wrap(TAGLINE, theme.FONT_SMALL, card.width - 48, theme.INK_SOFT)
        surface.blit(text, (card.left + 24, card.top + 114))
        theme.draw_text(
            surface,
            self.fonts,
            "手绘田园 · 网格解谜",
            (card.left + 24, card.bottom - 24),
            theme.FONT_TINY,
            theme.INK_LIGHT,
        )

    def _draw_illustration(self, surface: pygame.Surface) -> None:
        center = (720, 376)
        # soft meadow circle
        meadow = pygame.Surface((528, 448), pygame.SRCALPHA)
        pygame.draw.ellipse(meadow, (*theme.GRASS_LIGHT, 220), (0, 96, 528, 336))
        pygame.draw.ellipse(meadow, (*theme.GRASS, 190), (16, 120, 496, 296))
        surface.blit(meadow, (center[0] - 264, center[1] - 240))

        # trees
        for x, y, scale in ((480, 365, 1.48), (965, 397, 1.16)):
            tree = pygame.transform.smoothscale(art.build_tree(64), (int(64 * scale), int(64 * scale)))
            surface.blit(tree, tree.get_rect(midbottom=(x, y)))

        # fence
        fence = self._scaled["fence"]
        for index in range(11):
            surface.blit(fence, (501 + index * 46, 552))

        bob = math.sin(self.time * 2.2) * 3
        cow_bob = math.sin(self.time * 1.8 + 1.2) * 2
        farmer_rect = self._scaled["farmer"].get_rect(midbottom=(640, 541 + bob))
        cow_rect = self._scaled["cow"].get_rect(midbottom=(832, 549 + cow_bob))
        shadow = pygame.Surface((96, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (*theme.SHADOW, 40), shadow.get_rect())
        surface.blit(shadow, (farmer_rect.centerx - 48, farmer_rect.bottom - 13))
        surface.blit(shadow, (cow_rect.centerx - 48, cow_rect.bottom - 11))
        surface.blit(self._scaled["farmer"], farmer_rect)
        surface.blit(self._scaled["cow"], cow_rect)

        # hay bale
        surface.blit(self._scaled["bale"], (744, 517))

        # drifting petals
        for index, (speed, phase, size, sway) in enumerate(self._petals):
            t = (self.time * 0.22 * speed + phase) % 1.0
            x = 512 + int(416 * ((index * 0.13 + phase) % 1.0)) + int(math.sin(self.time + index) * 8)
            y = 144 + int(336 * t)
            color = (theme.PINK, theme.SUN_LIGHT, theme.WHITE_WARM)[index % 3]
            pygame.draw.circle(surface, color, (x, y), int(2 * size))

        # little floating hearts above the pair
        for index in range(2):
            t = (self.time * 0.5 + index * 0.5) % 1.0
            alpha = int(255 * (1 - t))
            layer = pygame.Surface((20, 20), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*theme.CLAY_LIGHT, alpha), (7, 8), 5)
            pygame.draw.circle(layer, (*theme.CLAY_LIGHT, alpha), (13, 8), 5)
            pygame.draw.polygon(layer, (*theme.CLAY_LIGHT, alpha), [(2, 10), (18, 10), (10, 19)])
            surface.blit(layer, (880 + index * 46, 520 - int(60 * t)))
