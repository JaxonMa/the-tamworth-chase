"""Reusable interface widgets: buttons, cards, toggles, sliders and modals.

All labels are Chinese; the code identifiers and docstrings stay English.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pygame

from . import theme
from .theme import FontBook


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------
BUTTON_STYLES: Dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]] = {
    # background, hover, pressed, border, text
    "default": (theme.BUTTON_BG, theme.BUTTON_HOVER, theme.BUTTON_DOWN, theme.BUTTON_BORDER, theme.BUTTON_TEXT),
    "primary": (theme.PRIMARY_BG, theme.PRIMARY_HOVER, theme.PRIMARY_DOWN, theme.PRIMARY_BORDER, theme.WHITE_WARM),
    "danger": (theme.DANGER_BG, theme.DANGER_HOVER, theme.CLAY_DARK, theme.CLAY_DARK, theme.WHITE_WARM),
    "ghost": (theme.CREAM_DARK, theme.CREAM, theme.PARCHMENT, theme.PANEL_BORDER, theme.INK_SOFT),
    "sky": (theme.SKY, theme.SKY_PALE, theme.SKY_DEEP, theme.SKY_DEEP, theme.INK),
}


class Button:
    """A rounded, softly shadowed button with an optional small icon."""

    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        key: str,
        *,
        style: str = "default",
        font_size: int = theme.FONT_BODY,
        enabled: bool = True,
        icon: Optional[pygame.Surface] = None,
        radius: int = 14,
        tooltip: str = "",
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.text = text
        self.key = key
        self.style = style
        self.font_size = font_size
        self.enabled = enabled
        self.icon = icon
        self.radius = radius
        self.tooltip = tooltip
        self.hovered = False
        self.pressed = False
        self.visible = True

    # -- geometry ------------------------------------------------------
    def contains(self, pos: Tuple[int, int]) -> bool:
        return self.visible and self.rect.collidepoint(pos)

    # -- events --------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if not self.visible or not self.enabled:
            return None
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
                self.hovered = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_pressed = self.pressed
            self.pressed = False
            if was_pressed and self.rect.collidepoint(event.pos):
                return self.key
        return None

    # -- drawing -------------------------------------------------------
    def draw(self, surface: pygame.Surface, fonts: FontBook) -> None:
        if not self.visible:
            return
        background, hover, pressed, border, text_color = BUTTON_STYLES.get(
            self.style, BUTTON_STYLES["default"]
        )
        if not self.enabled:
            background = theme.CREAM_DARK
            border = theme.PANEL_BORDER
            text_color = theme.INK_LIGHT
        elif self.pressed:
            background = pressed
        elif self.hovered:
            background = hover

        rect = self.rect
        if self.enabled and not self.pressed:
            theme.soft_shadow(surface, rect, radius=self.radius, alpha=26, offset=(0, 3))
        else:
            rect = rect.move(0, 0 if self.pressed else 0)
        theme.rounded_rect(surface, rect, background, radius=self.radius)
        theme.rounded_rect(surface, rect, border, radius=self.radius, width=2)
        if self.hovered and self.enabled and not self.pressed:
            pygame.draw.rect(
                surface,
                tuple(min(255, c + 12) for c in background),
                rect.inflate(-6, -6),
                width=0,
                border_radius=max(4, self.radius - 4),
            )

        text_surface = fonts.render(self.text, self.font_size, text_color, bold=True)
        if self.icon is not None:
            total_width = self.icon.get_width() + 8 + text_surface.get_width()
            start_x = rect.centerx - total_width // 2
            icon_rect = self.icon.get_rect(midleft=(start_x, rect.centery))
            surface.blit(self.icon, icon_rect)
            surface.blit(
                text_surface,
                text_surface.get_rect(midleft=(icon_rect.right + 8, rect.centery)),
            )
        else:
            surface.blit(text_surface, text_surface.get_rect(center=rect.center))


# ---------------------------------------------------------------------------
# Toggle switch
# ---------------------------------------------------------------------------
class Toggle:
    def __init__(self, rect: pygame.Rect, label: str, key: str, value: bool = False) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.key = key
        self.value = value
        self.hovered = False

    @property
    def switch_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.right - 62, self.rect.centery - 15, 62, 30)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.value = not self.value
                return self.key
        return None

    def draw(self, surface: pygame.Surface, fonts: FontBook) -> None:
        if self.hovered:
            theme.rounded_rect(surface, self.rect.inflate(10, 4), theme.CREAM_DARK, radius=12)
        theme.draw_text(
            surface, fonts, self.label, (self.rect.left, self.rect.centery), theme.FONT_BODY,
            theme.INK, anchor="midleft",
        )
        switch = self.switch_rect
        track = theme.PRIMARY_BG if self.value else theme.CREAM_DARK
        border = theme.PRIMARY_BORDER if self.value else theme.BUTTON_BORDER
        theme.rounded_rect(surface, switch, track, radius=15)
        theme.rounded_rect(surface, switch, border, radius=15, width=2)
        knob_x = switch.right - 17 if self.value else switch.left + 17
        pygame.draw.circle(surface, theme.WHITE_WARM, (knob_x, switch.centery), 11)
        pygame.draw.circle(surface, border, (knob_x, switch.centery), 11, 2)


# ---------------------------------------------------------------------------
# Slider
# ---------------------------------------------------------------------------
class Slider:
    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        key: str,
        value: float = 0.5,
        minimum: float = 0.0,
        maximum: float = 1.0,
        step: float = 0.05,
        formatter: Optional[Callable[[float], str]] = None,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.key = key
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.formatter = formatter or (lambda v: f"{int(v * 100)}%")
        self.dragging = False

    @property
    def track_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.left, self.rect.top + 36, self.rect.width - 90, 8)

    def _value_from_x(self, x: int) -> float:
        track = self.track_rect
        ratio = (x - track.left) / max(1, track.width)
        ratio = max(0.0, min(1.0, ratio))
        raw = self.minimum + ratio * (self.maximum - self.minimum)
        steps = round((raw - self.minimum) / self.step)
        value = self.minimum + steps * self.step
        return max(self.minimum, min(self.maximum, value))

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self.value = self._value_from_x(event.pos[0])
                return self.key
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.value = self._value_from_x(event.pos[0])
            return self.key
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return self.key
        return None

    def draw(self, surface: pygame.Surface, fonts: FontBook) -> None:
        theme.draw_text(
            surface, fonts, self.label, (self.rect.left, self.rect.top + 12), theme.FONT_BODY,
            theme.INK, anchor="midleft",
        )
        track = self.track_rect
        theme.rounded_rect(surface, track, theme.CREAM_DARK, radius=4)
        ratio = (self.value - self.minimum) / max(0.001, self.maximum - self.minimum)
        filled = pygame.Rect(track.left, track.top, int(track.width * ratio), track.height)
        theme.rounded_rect(surface, filled, theme.PRIMARY_BG, radius=4)
        knob = (track.left + int(track.width * ratio), track.centery)
        pygame.draw.circle(surface, theme.WHITE_WARM, knob, 12)
        pygame.draw.circle(surface, theme.PRIMARY_BORDER, knob, 12, 2)
        theme.draw_text(
            surface, fonts, self.formatter(self.value),
            (self.rect.right, track.centery), theme.FONT_SMALL, theme.INK_SOFT, anchor="midright",
        )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
class Tabs:
    def __init__(self, rect: pygame.Rect, items: Sequence[Tuple[str, str]], active: str) -> None:
        self.rect = pygame.Rect(rect)
        self.items = list(items)
        self.active = active
        self.hovered: Optional[str] = None
        self._rects: List[Tuple[str, pygame.Rect]] = []
        self._layout()

    def _layout(self) -> None:
        self._rects = []
        if not self.items:
            return
        width = self.rect.width // len(self.items)
        for index, (key, _label) in enumerate(self.items):
            self._rects.append(
                (key, pygame.Rect(self.rect.left + index * width, self.rect.top, width - 6, self.rect.height))
            )

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = next((key for key, rect in self._rects if rect.collidepoint(event.pos)), None)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for key, rect in self._rects:
                if rect.collidepoint(event.pos) and key != self.active:
                    self.active = key
                    return key
        return None

    def draw(self, surface: pygame.Surface, fonts: FontBook) -> None:
        for key, rect in self._rects:
            active = key == self.active
            background = theme.PRIMARY_BG if active else theme.CREAM_DARK
            border = theme.PRIMARY_BORDER if active else theme.PANEL_BORDER
            if self.hovered == key and not active:
                background = theme.CREAM
            theme.rounded_rect(surface, rect, background, radius=12)
            theme.rounded_rect(surface, rect, border, radius=12, width=2)
            label = next(label for k, label in self.items if k == key)
            color = theme.WHITE_WARM if active else theme.INK_SOFT
            theme.draw_text(surface, fonts, label, rect.center, theme.FONT_BODY, color, anchor="center", bold=active)


# ---------------------------------------------------------------------------
# Level / chapter cards
# ---------------------------------------------------------------------------
@dataclass
class Card:
    rect: pygame.Rect
    title: str
    key: str
    subtitle: str = ""
    badge: str = ""
    progress: str = ""
    locked: bool = False
    completed: bool = False
    accent: Tuple[int, int, int] = theme.LEAF
    hovered: bool = False
    enabled: bool = True
    footnote: str = ""

    def contains(self, pos: Tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.enabled and self.rect.collidepoint(event.pos):
                return self.key
        return None

    def draw(self, surface: pygame.Surface, fonts: FontBook) -> None:
        lift = -3 if self.hovered and self.enabled else 0
        rect = self.rect.move(0, lift)
        shadow_alpha = 46 if self.hovered and self.enabled else 30
        theme.soft_shadow(surface, rect, radius=18, alpha=shadow_alpha, offset=(0, 6 + (2 if lift else 0)))
        background = theme.PANEL_BG if not self.locked else theme.CREAM_DARK
        theme.rounded_rect(surface, rect, background, radius=18)
        if self.hovered and self.enabled:
            theme.rounded_rect(surface, rect, theme.SUN_LIGHT, radius=18, width=3)
        else:
            theme.rounded_rect(surface, rect, theme.PANEL_BORDER, radius=18, width=2)

        # accent bar
        accent_rect = pygame.Rect(rect.left + 16, rect.top + 16, 6, rect.height - 32)
        theme.rounded_rect(surface, accent_rect, self.accent, radius=3)

        title_x = rect.left + 34
        theme.draw_text(surface, fonts, self.title, (title_x, rect.top + 20), theme.FONT_H3, theme.INK, bold=True)
        if self.badge:
            badge_surface = fonts.render(self.badge, theme.FONT_TINY, theme.WHITE_WARM, True)
            badge_rect = badge_surface.get_rect()
            badge_rect.topleft = (title_x, rect.top + 54)
            pad = 8
            frame = badge_rect.inflate(pad * 2, pad - 2)
            theme.rounded_rect(surface, frame, self.accent, radius=9)
            surface.blit(badge_surface, badge_rect)
        if self.subtitle:
            theme.draw_text(
                surface, fonts, self.subtitle,
                (title_x, rect.top + 84 if self.badge else rect.top + 56),
                theme.FONT_SMALL, theme.INK_SOFT,
            )
        if self.progress:
            theme.draw_text(
                surface, fonts, self.progress, (rect.right - 18, rect.top + 22),
                theme.FONT_SMALL, theme.INK_SOFT, anchor="topright",
            )
        if self.footnote:
            theme.draw_text(
                surface, fonts, self.footnote, (rect.right - 18, rect.bottom - 18),
                theme.FONT_TINY, theme.INK_LIGHT, anchor="bottomright",
            )
        if self.completed:
            self._draw_check(surface, (rect.right - 34, rect.top + 34))
        if self.locked:
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            overlay.fill((*theme.CREAM, 150))
            surface.blit(overlay, rect.topleft)
            self._draw_lock(surface, (rect.centerx, rect.centery - 6))

    @staticmethod
    def _draw_check(surface: pygame.Surface, center: Tuple[int, int]) -> None:
        pygame.draw.circle(surface, theme.PRIMARY_BG, center, 14)
        pygame.draw.circle(surface, theme.PRIMARY_BORDER, center, 14, 2)
        pygame.draw.lines(
            surface,
            theme.WHITE_WARM,
            False,
            [(center[0] - 6, center[1]), (center[0] - 1, center[1] + 5), (center[0] + 7, center[1] - 5)],
            3,
        )

    @staticmethod
    def _draw_lock(surface: pygame.Surface, center: Tuple[int, int]) -> None:
        body = pygame.Rect(center[0] - 16, center[1] - 2, 32, 24)
        theme.rounded_rect(surface, body, theme.INK_LIGHT, radius=6)
        pygame.draw.circle(surface, theme.INK_LIGHT, (center[0], center[1] - 6), 10, 4)


# ---------------------------------------------------------------------------
# Modal dialog
# ---------------------------------------------------------------------------
class Modal:
    """A centred dialog with a title, wrapped body and a row of buttons."""

    def __init__(
        self,
        title: str,
        body: str = "",
        *,
        accent: Tuple[int, int, int] = theme.LEAF,
        buttons: Sequence[Button] = (),
        width: int = 620,
        height: int = 380,
        badge: str = "",
        dismissable: bool = False,
    ) -> None:
        self.title = title
        self.body = body
        self.accent = accent
        self.buttons = list(buttons)
        self.badge = badge
        self.dismissable = dismissable
        screen = pygame.Rect(0, 0, theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT)
        self.rect = pygame.Rect(0, 0, width, height)
        self.rect.center = screen.center
        self._layout_buttons()

    def _layout_buttons(self) -> None:
        if not self.buttons:
            return
        gap = 16
        total_width = sum(button.rect.width for button in self.buttons) + gap * (len(self.buttons) - 1)
        x = self.rect.centerx - total_width // 2
        y = self.rect.bottom - 78
        for button in self.buttons:
            button.rect.topleft = (x, y)
            x += button.rect.width + gap

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        for button in self.buttons:
            action = button.handle_event(event)
            if action:
                return action
        if self.dismissable and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "dismiss"
        return None

    def update(self, mouse_pos: Tuple[int, int]) -> None:
        for button in self.buttons:
            button.hovered = button.rect.collidepoint(mouse_pos)

    def draw(self, surface: pygame.Surface, fonts: FontBook) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((*theme.SHADOW, 110))
        surface.blit(overlay, (0, 0))

        theme.soft_shadow(surface, self.rect, radius=26, alpha=70, offset=(0, 10))
        theme.rounded_rect(surface, self.rect, theme.PANEL_BG, radius=26)
        theme.rounded_rect(surface, self.rect, self.accent, radius=26, width=3)

        header = pygame.Rect(self.rect.left + 28, self.rect.top + 22, self.rect.width - 56, 46)
        theme.draw_text(
            surface, fonts, self.title, (header.left, header.top), theme.FONT_H1, theme.INK, bold=True
        )
        if self.badge:
            badge_surface = fonts.render(self.badge, theme.FONT_TINY, theme.WHITE_WARM, True)
            badge_rect = badge_surface.get_rect(topright=(self.rect.right - 30, self.rect.top + 32))
            theme.rounded_rect(surface, badge_rect.inflate(18, 10), self.accent, radius=10)
            surface.blit(badge_surface, badge_rect)

        line_y = self.rect.top + 92
        pygame.draw.line(
            surface, theme.PANEL_BORDER, (self.rect.left + 28, line_y), (self.rect.right - 28, line_y), 2
        )

        if self.body:
            text = fonts.wrap(self.body, theme.FONT_BODY, self.rect.width - 72, theme.INK_SOFT)
            surface.blit(text, (self.rect.left + 36, self.rect.top + 108))

        for button in self.buttons:
            button.draw(surface, fonts)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def draw_divider(surface: pygame.Surface, y: int, left: int, width: int, color=theme.PANEL_BORDER) -> None:
    pygame.draw.line(surface, color, (left, y), (left + width, y), 2)


def draw_tooltip(
    surface: pygame.Surface,
    fonts: FontBook,
    text: str,
    pos: Tuple[int, int],
    *,
    max_width: int = 320,
) -> pygame.Rect:
    """Draw a floating tooltip clamped inside the window."""
    body = fonts.wrap(text, theme.FONT_SMALL, max_width, theme.WHITE_WARM)
    padding = 12
    rect = pygame.Rect(0, 0, body.get_width() + padding * 2, body.get_height() + padding * 2)
    rect.topleft = (pos[0] + 14, pos[1] + 14)
    rect.clamp_ip(pygame.Rect(0, 0, theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT))
    theme.soft_shadow(surface, rect, radius=10, alpha=60, offset=(0, 4))
    theme.rounded_rect(surface, rect, theme.INK_SOFT, radius=10)
    surface.blit(body, (rect.left + padding, rect.top + padding - 2))
    return rect


def draw_pill(
    surface: pygame.Surface,
    fonts: FontBook,
    text: str,
    center: Tuple[int, int],
    color: Tuple[int, int, int],
    *,
    text_color: Tuple[int, int, int] = theme.WHITE_WARM,
    font_size: int = theme.FONT_TINY,
) -> pygame.Rect:
    label = fonts.render(text, font_size, text_color, True)
    rect = label.get_rect(center=center)
    frame = rect.inflate(20, 10)
    theme.rounded_rect(surface, frame, color, radius=frame.height // 2)
    surface.blit(label, rect)
    return frame


def rank_color(rank: Optional[str]) -> Tuple[int, int, int]:
    return theme.RANK_COLORS.get(rank or "", theme.INK_LIGHT)
