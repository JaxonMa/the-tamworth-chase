"""Scene base class and shared chrome (backgrounds, headers, footers)."""

from __future__ import annotations

from typing import Optional, Tuple

import pygame

from .. import art, theme, ui


class Scene:
    """Base class for every screen."""

    #: Set to True when the scene wants the mouse cursor hidden.
    hides_cursor = False

    def __init__(self, app) -> None:
        self.app = app
        self.time = 0.0

    # -- convenience ---------------------------------------------------
    @property
    def fonts(self) -> theme.FontBook:
        return self.app.fonts

    @property
    def cache(self) -> art.ArtCache:
        return self.app.cache

    @property
    def store(self):
        return self.app.store

    # -- lifecycle -----------------------------------------------------
    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    # -- loop ----------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, surface: pygame.Surface) -> None:
        pass


def draw_background(surface: pygame.Surface, *, warm: bool = False) -> None:
    """Soft cream backdrop shared by the menu-like scenes."""
    width, height = surface.get_size()
    top = theme.PARCHMENT if warm else theme.CREAM
    theme.vertical_gradient(surface, pygame.Rect(0, 0, width, height), top, theme.CREAM_DARK)
    layer = pygame.Surface((width, height), pygame.SRCALPHA)
    for cx, cy, radius, color, alpha in (
        (140, 120, 210, theme.SKY, 26),
        (width - 200, 90, 240, theme.SUN_LIGHT, 30),
        (width - 90, height - 60, 260, theme.GRASS_LIGHT, 40),
        (120, height - 40, 220, theme.GRASS_LIGHT, 34),
    ):
        pygame.draw.circle(layer, (*color, alpha), (cx, cy), radius)
    surface.blit(layer, (0, 0))


def draw_header(
    surface: pygame.Surface,
    fonts: theme.FontBook,
    title: str,
    subtitle: str = "",
    badge: str = "",
    badge_color: Tuple[int, int, int] = theme.LEAF,
) -> None:
    theme.draw_text(surface, fonts, title, (62, 34), theme.FONT_H1, theme.INK, bold=True)
    x = 62
    width = fonts.size_of(title, theme.FONT_H1, True)[0]
    if badge:
        pill_rect = ui.draw_pill(
            surface,
            fonts,
            badge,
            (x + width + 60, 58),
            badge_color,
        )
        width += pill_rect.width + 24
    if subtitle:
        theme.draw_text(surface, fonts, subtitle, (x + width + 24, 50), theme.FONT_SMALL, theme.INK_SOFT)
    pygame.draw.line(surface, theme.PANEL_BORDER, (60, 104), (60 + 1160, 104), 2)


def draw_footer(surface: pygame.Surface, fonts: theme.FontBook, text: str) -> None:
    theme.draw_text(surface, fonts, text, (62, 808), theme.FONT_TINY, theme.INK_LIGHT)


def make_back_button(key: str = "back") -> ui.Button:
    return ui.Button(pygame.Rect(theme.WINDOW_WIDTH - 190, 36, 130, 52), "返回", key, style="ghost")


def draw_close_hint(surface: pygame.Surface, fonts: theme.FontBook) -> None:
    theme.draw_text(
        surface,
        fonts,
        "Esc 返回",
        (theme.WINDOW_WIDTH - 210, 66),
        theme.FONT_TINY,
        theme.INK_LIGHT,
        anchor="midleft",
    )
