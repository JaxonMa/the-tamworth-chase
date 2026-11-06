"""Visual theme: palette, fonts and reusable rounded UI primitives.

The game never loads a font from the network.  It always tries the bundled
hand-written CJK font first and falls back to a system sans/rounded font when
the file is missing, so the interface stays readable on any machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import pygame

from .paths import asset_path

# ---------------------------------------------------------------------------
# Palette - fresh, natural, low saturation
# ---------------------------------------------------------------------------
CREAM = (251, 246, 233)
CREAM_DARK = (243, 233, 210)
PARCHMENT = (247, 240, 223)
WHITE_WARM = (255, 253, 246)

GRASS_LIGHT = (206, 233, 182)
GRASS = (189, 220, 160)
GRASS_DARK = (170, 206, 138)
GRASS_SHADOW = (148, 187, 119)

DIRT = (220, 197, 162)
DIRT_DARK = (199, 172, 134)
DIRT_LIGHT = (234, 216, 185)

WOOD = (187, 140, 92)
WOOD_DARK = (140, 96, 62)
WOOD_LIGHT = (217, 180, 133)

SKY = (191, 227, 242)
SKY_DEEP = (143, 203, 227)
SKY_PALE = (225, 243, 250)

CLAY = (197, 107, 79)
CLAY_DARK = (166, 84, 60)
CLAY_LIGHT = (219, 145, 118)

SUN = (242, 193, 78)
SUN_LIGHT = (251, 225, 150)

INK = (74, 59, 42)
INK_SOFT = (122, 104, 84)
INK_LIGHT = (160, 143, 121)

LEAF = (128, 170, 105)
LEAF_DARK = (95, 134, 77)
LEAF_LIGHT = (176, 205, 152)

BERRY = (186, 96, 96)
BERRY_LIGHT = (214, 138, 132)
PINK = (233, 183, 178)
PINK_DEEP = (214, 148, 143)
COW_WHITE = (250, 244, 232)
DENIM = (122, 157, 176)
DENIM_DARK = (98, 130, 148)
COW_BROWN = (139, 104, 78)
COW_PINK = (232, 174, 168)

STONE = (176, 168, 152)
STONE_DARK = (146, 139, 124)

WATER = (156, 205, 219)
WATER_DEEP = (126, 178, 198)

SHADOW = (74, 59, 42)

PANEL_BG = (255, 252, 243)
PANEL_BORDER = (228, 211, 181)
PANEL_SHADOW = (74, 59, 42)

BUTTON_BG = (255, 252, 243)
BUTTON_HOVER = (252, 236, 199)
BUTTON_DOWN = (244, 220, 172)
BUTTON_BORDER = (211, 186, 148)
BUTTON_TEXT = INK

PRIMARY_BG = (142, 184, 118)
PRIMARY_HOVER = (155, 197, 130)
PRIMARY_DOWN = (126, 168, 104)
PRIMARY_BORDER = (111, 151, 90)

DANGER_BG = (204, 118, 90)
DANGER_HOVER = (217, 134, 106)

# Reward colours
RANK_COLORS = {
    "S": (226, 168, 57),
    "A": (128, 170, 105),
    "B": (118, 160, 190),
    "C": (170, 154, 132),
}

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
FONT_TITLE = 62
FONT_H1 = 40
FONT_H2 = 30
FONT_H3 = 25
FONT_BODY = 22
FONT_SMALL = 20
FONT_TINY = 18

FONT_RELATIVE_PATH = ("fonts", "CEFFontsCJK-Regular.ttf")

# CEF Fonts CJK draws "1" as a bare slash, so digits come from a rounded
# system face while Chinese and Latin letters keep the hand-written look.
DIGIT_FONT_NAMES: Sequence[str] = (
    "sfnsrounded",
    "avenirnext",
    "helveticaneue",
    "dejavusans",
    "arial",
)

FALLBACK_FONT_NAMES: Sequence[str] = (
    "pingfangsc",
    "hiraginosansgb",
    "stheiti",
    "heitisc",
    "notosanscjksc",
    "microsoftyahei",
    "simhei",
    "sourcehansanssc",
    "arialunicodems",
    "dejavusans",
)

_BOLD_OFFSET = 1

# Closing punctuation should not start a new line in Chinese text.
_NO_LINE_START = "，。！？；：、）》」』】%"


class FontBook:
    """Caches pygame fonts and rendered text surfaces."""

    def __init__(self, font_path: Optional[Path] = None) -> None:
        self.font_path: Optional[Path] = Path(font_path) if font_path else asset_path(*FONT_RELATIVE_PATH)
        self.source = "bundled"
        if not self.font_path.exists():
            self.font_path = self._find_fallback()
            self.source = "system" if self.font_path else "default"
        self.digit_path: Optional[Path] = self._find_digit_font()
        self._fonts: Dict[int, pygame.font.Font] = {}
        self._digit_fonts: Dict[int, pygame.font.Font] = {}
        self._text_cache: Dict[Tuple[str, int, Tuple[int, int, int], bool], pygame.Surface] = {}
        self._wrapped_cache: Dict[Tuple[str, int, int, bool], pygame.Surface] = {}

    @staticmethod
    def _find_fallback() -> Optional[Path]:
        for name in FALLBACK_FONT_NAMES:
            match = pygame.font.match_font(name)
            if match:
                return Path(match)
        return None

    @staticmethod
    def _find_digit_font() -> Optional[Path]:
        for name in DIGIT_FONT_NAMES:
            match = pygame.font.match_font(name)
            if match:
                return Path(match)
        return None

    @property
    def display_name(self) -> str:
        if self.source == "bundled":
            return "CEF Fonts CJK"
        if self.font_path:
            return self.font_path.stem
        return "系统默认字体"

    def get(self, size: int) -> pygame.font.Font:
        font = self._fonts.get(size)
        if font is None:
            if self.font_path is not None:
                font = pygame.font.Font(str(self.font_path), size)
            else:
                font = pygame.font.SysFont(None, size)
            self._fonts[size] = font
        return font

    def get_digit_font(self, size: int) -> pygame.font.Font:
        font = self._digit_fonts.get(size)
        if font is None:
            if self.digit_path is not None:
                font = pygame.font.Font(str(self.digit_path), size)
            else:
                font = self.get(size)
            self._digit_fonts[size] = font
        return font

    # -- text rendering ------------------------------------------------
    @staticmethod
    def _split_runs(text: str):
        runs = []
        current = ""
        current_digit: Optional[bool] = None
        for char in text:
            is_digit = char.isdigit() or char in ".,:%/"
            if current_digit is None or is_digit == current_digit:
                current += char
                current_digit = is_digit
            else:
                runs.append((current_digit, current))
                current = char
                current_digit = is_digit
        if current:
            runs.append((bool(current_digit), current))
        return runs

    def _render_run(self, text: str, size: int, color, bold: bool, digit: bool) -> pygame.Surface:
        font = self.get_digit_font(size) if digit else self.get(size)
        base = font.render(text, True, color)
        if bold and digit:
            width = base.get_width() + _BOLD_OFFSET
            layered = pygame.Surface((width, base.get_height()), pygame.SRCALPHA)
            layered.blit(base, (0, 0))
            layered.blit(base, (_BOLD_OFFSET, 0))
            return layered
        return base

    def render(
        self,
        text: str,
        size: int = FONT_BODY,
        color: Tuple[int, int, int] = INK,
        bold: bool = False,
    ) -> pygame.Surface:
        key = (text, size, color, bold)
        cached = self._text_cache.get(key)
        if cached is not None:
            return cached
        has_digits = self.digit_path is not None and any(char.isdigit() for char in text)
        if not has_digits:
            font = self.get(size)
            base = font.render(text, True, color)
            if bold:
                width = base.get_width() + _BOLD_OFFSET
                layered = pygame.Surface((width, base.get_height()), pygame.SRCALPHA)
                layered.blit(base, (0, 0))
                layered.blit(base, (_BOLD_OFFSET, 0))
                base = layered
        else:
            runs = self._split_runs(text)
            rendered = [self._render_run(run, size, color, bold, digit) for digit, run in runs]
            width = sum(surface.get_width() for surface in rendered)
            height = max(surface.get_height() for surface in rendered)
            base = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)
            ascent = self.get_digit_font(size).get_ascent()
            x = 0
            for surface in rendered:
                base.blit(surface, (x, 0))
                x += surface.get_width()
        if len(self._text_cache) > 900:
            self._text_cache.clear()
        self._text_cache[key] = base
        return base

    def size_of(self, text: str, size: int, bold: bool = False) -> Tuple[int, int]:
        return self.render(text, size, INK, bold).get_size()

    def ellipsize(self, text: str, size: int, max_width: int) -> str:
        """Shorten ``text`` with an ellipsis so it fits ``max_width``."""
        if self.size_of(text, size)[0] <= max_width:
            return text
        ellipsis = "…"
        accumulated = ""
        for char in text:
            if self.size_of(accumulated + char + ellipsis, size)[0] > max_width:
                break
            accumulated += char
        return (accumulated + ellipsis) if accumulated else ellipsis

    def wrap(self, text: str, size: int, max_width: int, color=INK, bold=False) -> pygame.Surface:
        """Render text with word wrapping.  CJK falls back to per-character wrapping."""
        key = (text, size, max_width, bold)
        cached = self._wrapped_cache.get(key)
        if cached is not None:
            return cached
        font = self.get(size)
        lines: list[str] = []
        for paragraph in text.split("\n"):
            current = ""
            for char in paragraph:
                candidate = current + char
                if self.size_of(candidate, size, bold)[0] > max_width and current:
                    if char in _NO_LINE_START and len(current) > 1:
                        lines.append(current[:-1])
                        current = current[-1] + char
                    else:
                        lines.append(current)
                        current = char
                else:
                    current = candidate
            lines.append(current)
        line_height = font.get_linesize()
        surface = pygame.Surface((max_width, max(1, line_height * len(lines))), pygame.SRCALPHA)
        for index, line in enumerate(lines):
            rendered = self.render(line, size, color, bold)
            surface.blit(rendered, (0, index * line_height))
        if len(self._wrapped_cache) > 300:
            self._wrapped_cache.clear()
        self._wrapped_cache[key] = surface
        return surface


# ---------------------------------------------------------------------------
# Shape helpers
# ---------------------------------------------------------------------------
def rounded_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: Tuple[int, int, int],
    radius: int = 14,
    width: int = 0,
) -> pygame.Rect:
    return pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)


def soft_shadow(
    surface: pygame.Surface,
    rect: pygame.Rect,
    radius: int = 18,
    offset: Tuple[int, int] = (0, 5),
    alpha: int = 34,
    spread: int = 0,
) -> None:
    """Draw a translucent rounded shadow behind a panel."""
    shadow_rect = rect.move(offset).inflate(spread * 2, spread * 2)
    layer = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(
        layer,
        (*SHADOW, alpha),
        pygame.Rect(0, 0, shadow_rect.width, shadow_rect.height),
        border_radius=radius,
    )
    surface.blit(layer, shadow_rect.topleft)


def panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    color: Tuple[int, int, int] = PANEL_BG,
    border: Tuple[int, int, int] = PANEL_BORDER,
    radius: int = 20,
    shadow: bool = True,
    border_width: int = 2,
) -> pygame.Rect:
    if shadow:
        soft_shadow(surface, rect, radius=radius)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border_width:
        pygame.draw.rect(surface, border, rect, width=border_width, border_radius=radius)
    return rect


def vertical_gradient(
    surface: pygame.Surface,
    rect: pygame.Rect,
    top: Tuple[int, int, int],
    bottom: Tuple[int, int, int],
) -> None:
    """Fill ``rect`` with a smooth two-colour vertical gradient."""
    height = max(1, rect.height)
    for row in range(height):
        t = row / max(1, height - 1)
        color = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        pygame.draw.line(surface, color, (rect.left, rect.top + row), (rect.right, rect.top + row))


def lighten(color: Tuple[int, int, int], amount: float) -> Tuple[int, int, int]:
    return tuple(min(255, int(c + (255 - c) * amount)) for c in color)  # type: ignore[return-value]


def darken(color: Tuple[int, int, int], amount: float) -> Tuple[int, int, int]:
    return tuple(max(0, int(c * (1.0 - amount))) for c in color)  # type: ignore[return-value]


def with_alpha(color: Tuple[int, int, int], alpha: int) -> Tuple[int, int, int, int]:
    return (color[0], color[1], color[2], alpha)


def draw_text(
    surface: pygame.Surface,
    fonts: FontBook,
    text: str,
    pos: Tuple[int, int],
    size: int = FONT_BODY,
    color: Tuple[int, int, int] = INK,
    *,
    anchor: str = "topleft",
    bold: bool = False,
    shadow: bool = False,
) -> pygame.Rect:
    image = fonts.render(text, size, color, bold)
    rect = image.get_rect(**{anchor: pos})
    if shadow:
        shade = fonts.render(text, size, darken(color, 0.35), bold)
        surface.blit(shade, rect.move(0, 2))
    surface.blit(image, rect)
    return rect


# ---------------------------------------------------------------------------
# Layout constants shared by every scene
# ---------------------------------------------------------------------------
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 840
FPS = 60

CELL_SIZE = 56
BOARD_ORIGIN = (60, 180)
BOARD_SIZE = CELL_SIZE * 10

PANEL_RECT = pygame.Rect(740, 104, 492, 700)
HEADER_RECT = pygame.Rect(60, 28, 1172, 76)
FOOTER_RECT = pygame.Rect(60, 792, 1172, 34)
