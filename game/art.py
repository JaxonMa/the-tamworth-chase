"""Procedural artwork.

Every visual element in the game is drawn with code: soft grass tiles, wooden
fences, hedges, trees, ponds, the farmer and the cows.  Sprites are rendered at
a higher resolution and smoothed down, which gives clean anti-aliased edges
without shipping any bitmap assets.

Only the bundled CJK font is a binary asset.
"""

from __future__ import annotations

import math
import random
import zlib
from typing import Dict, Optional, Tuple

import pygame

from . import theme
from .models import Direction, TileKind

BASE_CELL = 64
SPRITE_SCALE = 3


# ---------------------------------------------------------------------------
# Small drawing helpers (all coordinates are in the enlarged sprite space)
# ---------------------------------------------------------------------------
def _ellipse(surface, color, rect, width: int = 0) -> None:
    pygame.draw.ellipse(surface, color, pygame.Rect(rect), width)


def _circle(surface, color, center, radius: int, width: int = 0) -> None:
    pygame.draw.circle(surface, color, center, int(radius), width)


def _line(surface, color, start, end, width: int = 1) -> None:
    pygame.draw.line(surface, color, start, end, width)


def _polygon(surface, color, points) -> None:
    pygame.draw.polygon(surface, color, points)


def _rounded(surface, color, rect, radius: int, width: int = 0) -> None:
    pygame.draw.rect(surface, color, pygame.Rect(rect), width=width, border_radius=radius)


def _soft_blob(surface, color, center, radius: int, alpha: int = 40) -> None:
    blob = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(blob, (*color, alpha), (radius, radius), radius)
    surface.blit(blob, (center[0] - radius, center[1] - radius))


# ---------------------------------------------------------------------------
# Ground tiles
# ---------------------------------------------------------------------------
_painters = {}


def tile_painter(kind: TileKind):
    def decorator(fn):
        _painters[kind] = fn
        return fn

    return decorator


_GRASS_LAYERS: Dict[Tuple[int, int], pygame.Surface] = {}


def grass_base(size: int, variant: int = 0) -> pygame.Surface:
    """Return the shared grass layer for a tile variant.

    Every tile kind blits this exact layer so neighbouring tiles blend without
    visible seams, even when a tree or hedge sits next to plain grass.
    """
    key = (size, variant % 4)
    cached = _GRASS_LAYERS.get(key)
    if cached is not None:
        return cached
    rng = random.Random(zlib.crc32(f"grass-{variant % 4}".encode()))
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    base = theme.GRASS_LIGHT
    surface.fill(base)
    lighter = theme.lighten(base, 0.16)
    darker = theme.darken(base, 0.10)
    for _ in range(5):
        cx = rng.randrange(size)
        cy = rng.randrange(size)
        radius = rng.randrange(size // 9, size // 5)
        _soft_blob(surface, lighter, (cx, cy), radius, 18)
    for _ in range(16):
        x = rng.randrange(2, size - 2)
        y = rng.randrange(4, size - 2)
        _line(surface, darker, (x, y), (x + rng.choice((-2, -1, 1, 2)), y - rng.randrange(4, 9)), 2)
    _GRASS_LAYERS[key] = surface
    return surface


def _base_grass(size: int, rng: random.Random, shade: int = 0, variant: int = 0) -> pygame.Surface:
    return grass_base(size, variant)


@tile_painter(TileKind.GRASS)
def paint_grass(surface, size, rng, variant=0, extra=None):
    surface.blit(grass_base(size, variant), (0, 0))


@tile_painter(TileKind.FLOWERS)
def paint_flowers(surface, size, rng, variant=0, extra=None):
    surface.blit(grass_base(size, variant), (0, 0))
    petals = (theme.SUN_LIGHT, theme.PINK, theme.WHITE_WARM, theme.CLAY_LIGHT)
    for _ in range(3):
        x = rng.randrange(size // 6, size - size // 6)
        y = rng.randrange(size // 5, size - size // 5)
        color = rng.choice(petals)
        _line(surface, theme.LEAF_DARK, (x, y), (x, y + size // 12), 2)
        for angle in range(0, 360, 72):
            px = x + int(math.cos(math.radians(angle)) * size // 22)
            py = y + int(math.sin(math.radians(angle)) * size // 22)
            _circle(surface, color, (px, py), size // 30)
        _circle(surface, theme.SUN, (x, y), size // 36)


def _fence_shape(surface, size, mask: int, rng: random.Random) -> None:
    """Draw a fence connection given a neighbour bit mask (1=L,2=R,4=U,8=D)."""
    unit = size / 64.0
    left, right = bool(mask & 1), bool(mask & 2)
    up, down = bool(mask & 4), bool(mask & 8)
    if not (left or right or up or down):
        # A single fence post standing on its own looks better than a cross.
        shadow = pygame.Surface((size, size), pygame.SRCALPHA)
        _rounded(shadow, (*theme.SHADOW, 40), (26 * unit, 10 * unit, 16 * unit, 50 * unit), 6)
        surface.blit(shadow, (0, 0))
        _rounded(surface, theme.WOOD_DARK, (26 * unit, 6 * unit, 13 * unit, 52 * unit), int(4 * unit))
        _rounded(surface, theme.WOOD, (28 * unit, 8 * unit, 9 * unit, 48 * unit), int(3 * unit))
        _ellipse(surface, theme.WOOD_LIGHT, (27 * unit, 4 * unit, 11 * unit, 7 * unit))
        _line(surface, theme.WOOD_DARK, (30 * unit, 24 * unit), (36 * unit, 24 * unit), 2)
        _line(surface, theme.WOOD_DARK, (30 * unit, 40 * unit), (36 * unit, 40 * unit), 2)
        return

    shadow = pygame.Surface((size, size), pygame.SRCALPHA)
    if left or right:
        _rounded(shadow, (*theme.SHADOW, 42), (0, 44 * unit, size, 16 * unit), 6)
    if up or down:
        _rounded(shadow, (*theme.SHADOW, 42), (30 * unit, 0, 16 * unit, size), 6)
    surface.blit(shadow, (0, 0))

    if left or right:
        x0 = 0 if left else size / 2
        x1 = size if right else size / 2
        for y in (24 * unit, 40 * unit):
            _rounded(surface, theme.WOOD_DARK, (x0, y, x1 - x0, 9 * unit), 1)
            _rounded(surface, theme.WOOD_LIGHT, (x0, y + 1.5 * unit, x1 - x0, 5 * unit), 1)
    if up or down:
        y0 = 0 if up else size / 2
        y1 = size if down else size / 2
        for x in (22 * unit, 40 * unit):
            _rounded(surface, theme.WOOD_DARK, (x, y0, 9 * unit, y1 - y0), 1)
            _rounded(surface, theme.WOOD_LIGHT, (x + 1.5 * unit, y0, 5 * unit, y1 - y0), 1)

    post_x = 26 * unit
    _rounded(surface, theme.WOOD_DARK, (post_x, 6 * unit, 13 * unit, 52 * unit), int(4 * unit))
    _rounded(surface, theme.WOOD, (post_x + 2 * unit, 8 * unit, 9 * unit, 48 * unit), int(3 * unit))
    _ellipse(surface, theme.WOOD_LIGHT, (post_x + 1 * unit, 4 * unit, 11 * unit, 7 * unit))
    _line(surface, theme.WOOD_DARK, (post_x + 3 * unit, 24 * unit), (post_x + 9 * unit, 24 * unit), 2)
    _line(surface, theme.WOOD_DARK, (post_x + 3 * unit, 40 * unit), (post_x + 9 * unit, 40 * unit), 2)


@tile_painter(TileKind.FENCE)
def paint_fence(surface, size, rng, variant=0, extra=0):
    """``extra`` is a bit mask: 1=left, 2=right, 4=up, 8=down."""
    surface.blit(grass_base(size, variant), (0, 0))
    _fence_shape(surface, size, extra or 0, rng)
    unit = size / 64.0
    for _ in range(3):
        x = rng.randrange(2, size - 4)
        _line(surface, theme.GRASS_SHADOW, (x, size - 3 * unit), (x + 2, size - 10 * unit), 2)


def build_fence(size: int, mask: int = 3) -> pygame.Surface:
    """A fence segment without a grass background, used in menu scenery."""
    work = size * 3
    canvas = _actor_canvas(work)
    _fence_shape(canvas, work, mask, random.Random(5))
    return pygame.transform.smoothscale(canvas, (size, size))


@tile_painter(TileKind.HEDGE)
def paint_hedge(surface, size, rng, variant=0, extra=None):
    surface.blit(grass_base(size, variant), (0, 0))
    unit = size / 64.0
    shadow = pygame.Surface((size, size), pygame.SRCALPHA)
    _rounded(shadow, (*theme.SHADOW, 40), (4 * unit, 30 * unit, 56 * unit, 30 * unit), int(14 * unit))
    surface.blit(shadow, (0, 0))
    blobs = [
        (16, 34, 16, theme.LEAF_DARK),
        (34, 28, 18, theme.LEAF),
        (50, 34, 15, theme.LEAF_DARK),
        (26, 44, 16, theme.LEAF),
        (44, 44, 15, theme.LEAF_LIGHT),
        (32, 36, 17, theme.LEAF),
    ]
    for x, y, radius, color in blobs:
        _circle(surface, color, (x * unit, y * unit), radius * unit)
    for x, y, radius in ((30, 30, 8), (42, 36, 7), (22, 40, 6)):
        _circle(surface, theme.lighten(theme.LEAF, 0.22), (x * unit, y * unit), radius * unit)
    if rng.random() < 0.5:
        _circle(surface, theme.PINK, (20 * unit, 30 * unit), 2.5 * unit)


@tile_painter(TileKind.TREE)
def paint_tree(surface, size, rng, variant=0, extra=None):
    surface.blit(grass_base(size, variant), (0, 0))
    unit = size / 64.0
    shadow = pygame.Surface((size, size), pygame.SRCALPHA)
    _ellipse(shadow, (*theme.SHADOW, 52), (10 * unit, 40 * unit, 48 * unit, 18 * unit))
    surface.blit(shadow, (0, 0))
    _rounded(surface, theme.WOOD_DARK, (28 * unit, 48 * unit, 9 * unit, 11 * unit), int(3 * unit))
    _rounded(surface, theme.WOOD, (30 * unit, 48 * unit, 5 * unit, 9 * unit), int(2 * unit))
    canopy = [
        (20, 34, 15, theme.LEAF_DARK),
        (44, 34, 15, theme.LEAF_DARK),
        (32, 28, 19, theme.LEAF),
        (22, 44, 13, theme.LEAF),
        (44, 44, 13, theme.LEAF),
        (32, 38, 17, theme.LEAF_LIGHT),
    ]
    for x, y, radius, color in canopy:
        _circle(surface, color, (x * unit, y * unit), radius * unit)
    for x, y, radius in ((27, 26, 8), (41, 34, 6), (26, 42, 5)):
        _circle(surface, theme.lighten(theme.LEAF, 0.24), (x * unit, y * unit), radius * unit)


@tile_painter(TileKind.POND)
def paint_pond(surface, size, rng, variant=0, extra=None):
    unit = size / 64.0
    mask = extra or 0
    surface.blit(grass_base(size, variant), (0, 0))
    deep = theme.WATER_DEEP
    water = theme.WATER
    _rounded(surface, deep, (2 * unit, 2 * unit, 60 * unit, 60 * unit), int(16 * unit))
    _rounded(surface, water, (5 * unit, 5 * unit, 54 * unit, 54 * unit), int(14 * unit))
    # extend the water towards connected neighbours so a row of ponds reads as a stream
    for bit, rect in (
        (1, (0, 4 * unit, 10 * unit, 56 * unit)),
        (2, (54 * unit, 4 * unit, 10 * unit, 56 * unit)),
        (4, (4 * unit, 0, 56 * unit, 10 * unit)),
        (8, (4 * unit, 54 * unit, 56 * unit, 10 * unit)),
    ):
        if mask & bit:
            pygame.draw.rect(surface, deep, pygame.Rect(rect))
    for bit, rect in (
        (1, (0, 6 * unit, 11 * unit, 52 * unit)),
        (2, (53 * unit, 6 * unit, 11 * unit, 52 * unit)),
        (4, (6 * unit, 0, 52 * unit, 11 * unit)),
        (8, (6 * unit, 53 * unit, 52 * unit, 11 * unit)),
    ):
        if mask & bit:
            pygame.draw.rect(surface, water, pygame.Rect(rect))
    for _ in range(3):
        x = rng.randrange(12, 52)
        y = rng.randrange(14, 52)
        width = rng.randrange(10, 22)
        pygame.draw.arc(
            surface,
            theme.lighten(theme.WATER, 0.35),
            pygame.Rect((x - width // 2) * unit, y * unit, width * unit, 8 * unit),
            0.2,
            2.9,
            max(1, int(1.6 * unit)),
        )
    # lily pads
    for x, y, radius in ((20, 44, 7), (42, 24, 5)):
        _circle(surface, theme.LEAF, (x * unit, y * unit), radius * unit)
        _polygon(
            surface,
            water,
            [
                (x * unit, y * unit),
                ((x + radius) * unit, (y - 2) * unit),
                ((x + radius) * unit, (y + 2) * unit),
            ],
        )
        if rng.random() < 0.7:
            _circle(surface, theme.PINK, ((x + 2) * unit, (y - 1) * unit), 2.4 * unit)
    # reeds
    for x, y, height in ((8, 54, 10), (56, 12, 9)):
        _line(surface, theme.LEAF_DARK, (x * unit, y * unit), (x * unit, (y - height) * unit), 2)
        _ellipse(surface, theme.WOOD, ((x - 1.6) * unit, (y - height - 3) * unit, 3.6 * unit, 6 * unit))


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------
SKIN = (246, 217, 184)
SKIN_SHADE = (223, 187, 152)
DENIM = (122, 157, 176)
DENIM_DARK = (98, 130, 148)
BOOT = (120, 83, 56)
STRAW = (238, 203, 118)
STRAW_LIGHT = (250, 229, 166)
STRAW_DARK = (205, 163, 82)


def _actor_canvas(size: int) -> pygame.Surface:
    return pygame.Surface((size, size), pygame.SRCALPHA)


def _shadow(surface, cx: int, cy: int, rx: int, ry: int, alpha: int = 52) -> None:
    layer = pygame.Surface((rx * 2, ry * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(layer, (*theme.SHADOW, alpha), layer.get_rect())
    surface.blit(layer, (cx - rx, cy - ry))


def _draw_farmer_south(surface, s: int) -> None:
    u = s / 192.0
    _shadow(surface, int(96 * u), int(172 * u), int(54 * u), int(15 * u))
    # boots
    _ellipse(surface, theme.WOOD_DARK, (62 * u, 148 * u, 28 * u, 26 * u))
    _ellipse(surface, theme.WOOD_DARK, (102 * u, 148 * u, 28 * u, 26 * u))
    _ellipse(surface, BOOT, (64 * u, 149 * u, 24 * u, 20 * u))
    _ellipse(surface, BOOT, (104 * u, 149 * u, 24 * u, 20 * u))
    # arms behind torso
    _ellipse(surface, DENIM_DARK, (32 * u, 104 * u, 26 * u, 50 * u))
    _ellipse(surface, DENIM_DARK, (134 * u, 104 * u, 26 * u, 50 * u))
    _circle(surface, SKIN, (45 * u, 150 * u), 12 * u)
    _circle(surface, SKIN, (147 * u, 150 * u), 12 * u)
    # torso
    _ellipse(surface, DENIM, (54 * u, 92 * u, 84 * u, 68 * u))
    _ellipse(surface, theme.lighten(DENIM, 0.12), (58 * u, 95 * u, 76 * u, 56 * u))
    # shirt collar + sleeves
    _ellipse(surface, theme.CREAM, (60 * u, 84 * u, 72 * u, 30 * u))
    _rounded(surface, theme.CREAM, (68 * u, 92 * u, 56 * u, 16 * u), int(8 * u))
    # overall straps
    _rounded(surface, DENIM_DARK, (76 * u, 82 * u, 11 * u, 32 * u), int(4 * u))
    _rounded(surface, DENIM_DARK, (105 * u, 82 * u, 11 * u, 32 * u), int(4 * u))
    _circle(surface, theme.SUN, (81 * u, 106 * u), 4 * u)
    _circle(surface, theme.SUN, (110 * u, 106 * u), 4 * u)
    # head
    _circle(surface, SKIN, (96 * u, 64 * u), 36 * u)
    _circle(surface, SKIN_SHADE, (62 * u, 70 * u), 7 * u)
    _circle(surface, SKIN_SHADE, (130 * u, 70 * u), 7 * u)
    # hair peeking out under the hat
    _ellipse(surface, theme.WOOD_DARK, (58 * u, 56 * u, 18 * u, 16 * u))
    _ellipse(surface, theme.WOOD_DARK, (116 * u, 56 * u, 18 * u, 16 * u))
    # straw hat
    _ellipse(surface, STRAW_DARK, (20 * u, 28 * u, 152 * u, 34 * u))
    _ellipse(surface, STRAW_LIGHT, (24 * u, 30 * u, 144 * u, 28 * u))
    _ellipse(surface, STRAW, (60 * u, -2 * u, 72 * u, 46 * u))
    _ellipse(surface, STRAW_LIGHT, (66 * u, 2 * u, 60 * u, 32 * u))
    _rounded(surface, theme.CLAY, (62 * u, 32 * u, 68 * u, 9 * u), int(4 * u))
    _line(surface, STRAW_DARK, (98 * u, 4 * u), (95 * u, 24 * u), 2)
    # face below the brim
    _circle(surface, theme.INK, (80 * u, 76 * u), 5 * u)
    _circle(surface, theme.INK, (112 * u, 76 * u), 5 * u)
    _circle(surface, theme.WHITE_WARM, (82 * u, 74 * u), 1.8 * u)
    _circle(surface, theme.WHITE_WARM, (114 * u, 74 * u), 1.8 * u)
    _circle(surface, theme.PINK, (67 * u, 88 * u), 7 * u)
    _circle(surface, theme.PINK, (125 * u, 88 * u), 7 * u)
    pygame.draw.arc(
        surface,
        theme.INK_SOFT,
        pygame.Rect(84 * u, 82 * u, 24 * u, 16 * u),
        math.radians(200),
        math.radians(340),
        max(1, int(2.2 * u)),
    )


def _draw_farmer_north(surface, s: int) -> None:
    u = s / 192.0
    _shadow(surface, int(96 * u), int(172 * u), int(54 * u), int(15 * u))
    _ellipse(surface, theme.WOOD_DARK, (62 * u, 148 * u, 28 * u, 26 * u))
    _ellipse(surface, theme.WOOD_DARK, (102 * u, 148 * u, 28 * u, 26 * u))
    _ellipse(surface, BOOT, (64 * u, 149 * u, 24 * u, 20 * u))
    _ellipse(surface, BOOT, (104 * u, 149 * u, 24 * u, 20 * u))
    _ellipse(surface, DENIM_DARK, (32 * u, 104 * u, 26 * u, 50 * u))
    _ellipse(surface, DENIM_DARK, (134 * u, 104 * u, 26 * u, 50 * u))
    _circle(surface, SKIN_SHADE, (45 * u, 150 * u), 12 * u)
    _circle(surface, SKIN_SHADE, (147 * u, 150 * u), 12 * u)
    _ellipse(surface, DENIM, (54 * u, 92 * u, 84 * u, 68 * u))
    _ellipse(surface, DENIM_DARK, (58 * u, 95 * u, 76 * u, 56 * u))
    _rounded(surface, theme.CREAM, (68 * u, 88 * u, 56 * u, 20 * u), int(8 * u))
    # crossed straps on the back
    _line(surface, theme.lighten(DENIM, 0.28), (76 * u, 96 * u), (116 * u, 140 * u), max(2, int(5 * u)))
    _line(surface, theme.lighten(DENIM, 0.28), (116 * u, 96 * u), (76 * u, 140 * u), max(2, int(5 * u)))
    # head from behind + hair
    _circle(surface, SKIN_SHADE, (96 * u, 66 * u), 36 * u)
    _ellipse(surface, theme.WOOD_DARK, (58 * u, 58 * u, 76 * u, 42 * u))
    # hat from behind
    _ellipse(surface, STRAW_DARK, (20 * u, 28 * u, 152 * u, 34 * u))
    _ellipse(surface, STRAW_LIGHT, (24 * u, 30 * u, 144 * u, 28 * u))
    _ellipse(surface, STRAW, (60 * u, -2 * u, 72 * u, 46 * u))
    _ellipse(surface, theme.darken(STRAW, 0.06), (66 * u, 2 * u, 60 * u, 32 * u))
    _rounded(surface, theme.CLAY, (62 * u, 32 * u, 68 * u, 9 * u), int(4 * u))
    _line(surface, STRAW_DARK, (98 * u, 4 * u), (95 * u, 24 * u), 2)


def _draw_farmer_east(surface, s: int) -> None:
    u = s / 192.0
    _shadow(surface, int(96 * u), int(172 * u), int(54 * u), int(15 * u))
    _ellipse(surface, theme.WOOD_DARK, (64 * u, 150 * u, 26 * u, 24 * u))
    _ellipse(surface, BOOT, (66 * u, 151 * u, 22 * u, 18 * u))
    _ellipse(surface, theme.WOOD_DARK, (106 * u, 150 * u, 26 * u, 24 * u))
    _ellipse(surface, BOOT, (108 * u, 151 * u, 22 * u, 18 * u))
    _ellipse(surface, DENIM, (58 * u, 94 * u, 76 * u, 66 * u))
    _ellipse(surface, DENIM_DARK, (64 * u, 100 * u, 64 * u, 54 * u))
    _ellipse(surface, theme.CREAM, (60 * u, 86 * u, 72 * u, 30 * u))
    # one visible arm swinging forward
    _ellipse(surface, DENIM_DARK, (114 * u, 106 * u, 24 * u, 46 * u))
    _circle(surface, SKIN, (126 * u, 150 * u), 11 * u)
    # head profile
    _circle(surface, SKIN, (100 * u, 66 * u), 35 * u)
    _circle(surface, SKIN, (126 * u, 74 * u), 12 * u)  # nose
    _circle(surface, SKIN_SHADE, (70 * u, 72 * u), 7 * u)
    _ellipse(surface, theme.WOOD_DARK, (64 * u, 58 * u, 18 * u, 16 * u))
    # hat tilted forward
    _ellipse(surface, STRAW_DARK, (26 * u, 28 * u, 140 * u, 32 * u))
    _ellipse(surface, STRAW_LIGHT, (30 * u, 30 * u, 132 * u, 26 * u))
    _ellipse(surface, STRAW, (62 * u, -2 * u, 72 * u, 44 * u))
    _ellipse(surface, STRAW_LIGHT, (68 * u, 2 * u, 60 * u, 30 * u))
    _rounded(surface, theme.CLAY, (64 * u, 32 * u, 68 * u, 9 * u), int(4 * u))
    _line(surface, STRAW_DARK, (100 * u, 4 * u), (97 * u, 24 * u), 2)
    # face profile below the brim
    _circle(surface, theme.INK, (114 * u, 78 * u), 4.5 * u)
    _circle(surface, theme.WHITE_WARM, (116 * u, 76 * u), 1.6 * u)
    _circle(surface, theme.PINK, (92 * u, 90 * u), 5.5 * u)
    pygame.draw.arc(
        surface,
        theme.INK_SOFT,
        pygame.Rect(108 * u, 84 * u, 18 * u, 14 * u),
        math.radians(0.2),
        math.radians(2.9),
        max(1, int(2.2 * u)),
    )


def _draw_cow_base(surface, u: float, facing: Direction) -> None:
    """Body shared by every cow view."""
    if facing is Direction.NORTH:
        _shadow(surface, int(96 * u), int(172 * u), int(56 * u), int(16 * u))
        for x in (58, 84, 108, 134):
            _ellipse(surface, theme.WOOD_DARK, (x * u, 146 * u, 20 * u, 24 * u))
        _ellipse(surface, theme.COW_WHITE, (38 * u, 74 * u, 116 * u, 84 * u))
        _ellipse(surface, theme.darken(theme.COW_WHITE, 0.06), (44 * u, 82 * u, 104 * u, 68 * u))
        _ellipse(surface, theme.COW_BROWN, (62 * u, 96 * u, 38 * u, 30 * u))
        _ellipse(surface, theme.COW_BROWN, (108 * u, 88 * u, 30 * u, 26 * u))
        # tail
        pygame.draw.arc(
            surface,
            theme.COW_BROWN,
            pygame.Rect(88 * u, 52 * u, 40 * u, 46 * u),
            math.radians(60),
            math.radians(250),
            max(2, int(5 * u)),
        )
        _circle(surface, theme.COW_BROWN, (126 * u, 60 * u), 7 * u)
        # ears from behind
        _ellipse(surface, theme.COW_WHITE, (46 * u, 52 * u, 28 * u, 18 * u))
        _ellipse(surface, theme.COW_WHITE, (118 * u, 52 * u, 28 * u, 18 * u))
        _ellipse(surface, theme.COW_PINK, (52 * u, 56 * u, 16 * u, 10 * u))
        _ellipse(surface, theme.COW_PINK, (124 * u, 56 * u, 16 * u, 10 * u))
        _ellipse(surface, theme.COW_BROWN, (52 * u, 30 * u, 88 * u, 40 * u))
        _ellipse(surface, theme.COW_BROWN, (66 * u, 40 * u, 60 * u, 26 * u))
        return

    _shadow(surface, int(96 * u), int(170 * u), int(56 * u), int(16 * u))
    # legs
    for x in (58, 84, 108, 134):
        _ellipse(surface, theme.WOOD_DARK, (x * u, 142 * u, 18 * u, 26 * u))
        _ellipse(surface, BOOT, (x * u, 146 * u, 16 * u, 18 * u))
    _ellipse(surface, theme.COW_WHITE, (36 * u, 80 * u, 120 * u, 74 * u))
    _ellipse(surface, theme.darken(theme.COW_WHITE, 0.05), (42 * u, 86 * u, 108 * u, 62 * u))
    _ellipse(surface, theme.COW_BROWN, (50 * u, 94 * u, 42 * u, 30 * u))
    _ellipse(surface, theme.COW_BROWN, (104 * u, 110 * u, 38 * u, 24 * u))
    _ellipse(surface, theme.COW_BROWN, (98 * u, 84 * u, 22 * u, 16 * u))


def _draw_cow_head_front(surface, u: float) -> None:
    # ears
    _ellipse(surface, theme.COW_WHITE, (44 * u, 54 * u, 30 * u, 20 * u))
    _ellipse(surface, theme.COW_WHITE, (118 * u, 54 * u, 30 * u, 20 * u))
    _ellipse(surface, theme.COW_PINK, (50 * u, 58 * u, 18 * u, 11 * u))
    _ellipse(surface, theme.COW_PINK, (124 * u, 58 * u, 18 * u, 11 * u))
    # horns
    _polygon(surface, theme.CREAM_DARK,
             [(70 * u, 32 * u), (64 * u, 14 * u), (78 * u, 24 * u)])
    _polygon(surface, theme.DIRT_LIGHT,
             [(122 * u, 32 * u), (128 * u, 14 * u), (114 * u, 24 * u)])
    # head
    _circle(surface, theme.COW_WHITE, (96 * u, 66 * u), 42 * u)
    _circle(surface, theme.darken(theme.COW_WHITE, 0.05), (96 * u, 70 * u), 38 * u)
    # forelock
    _ellipse(surface, theme.COW_BROWN, (76 * u, 24 * u, 40 * u, 22 * u))
    # muzzle
    _ellipse(surface, theme.COW_PINK, (70 * u, 78 * u, 52 * u, 34 * u))
    _ellipse(surface, theme.PINK_DEEP, (74 * u, 82 * u, 44 * u, 26 * u))
    _circle(surface, theme.darken(theme.PINK_DEEP, 0.35), (86 * u, 94 * u), 3 * u)
    _circle(surface, theme.darken(theme.PINK_DEEP, 0.35), (106 * u, 94 * u), 3 * u)
    # eyes
    _circle(surface, theme.INK, (78 * u, 66 * u), 7 * u)
    _circle(surface, theme.INK, (114 * u, 66 * u), 7 * u)
    _circle(surface, theme.WHITE_WARM, (80 * u, 63 * u), 2.6 * u)
    _circle(surface, theme.WHITE_WARM, (116 * u, 63 * u), 2.6 * u)


def _draw_cow_head_east(surface, u: float) -> None:
    _ellipse(surface, theme.COW_WHITE, (108 * u, 52 * u, 28 * u, 18 * u))
    _ellipse(surface, theme.COW_PINK, (116 * u, 56 * u, 16 * u, 10 * u))
    _polygon(surface, theme.DIRT_LIGHT, [(102 * u, 30 * u), (98 * u, 14 * u), (110 * u, 24 * u)])
    _ellipse(surface, theme.COW_WHITE, (70 * u, 40 * u, 52 * u, 52 * u))
    _ellipse(surface, theme.COW_PINK, (104 * u, 60 * u, 34 * u, 26 * u))
    _circle(surface, theme.darken(theme.PINK_DEEP, 0.35), (110 * u, 70 * u), 2.6 * u)
    _circle(surface, theme.darken(theme.PINK_DEEP, 0.35), (110 * u, 78 * u), 2.6 * u)
    _circle(surface, theme.INK, (108 * u, 52 * u), 6.5 * u)
    _circle(surface, theme.WHITE_WARM, (110 * u, 49 * u), 2.4 * u)
    _ellipse(surface, theme.COW_BROWN, (78 * u, 34 * u, 34 * u, 20 * u))


def build_farmer(size: int, facing: Direction) -> pygame.Surface:
    work = size * SPRITE_SCALE
    canvas = _actor_canvas(work)
    if facing is Direction.SOUTH:
        _draw_farmer_south(canvas, work)
    elif facing is Direction.NORTH:
        _draw_farmer_north(canvas, work)
    elif facing is Direction.EAST:
        _draw_farmer_east(canvas, work)
    else:
        mirrored = _actor_canvas(work)
        _draw_farmer_east(mirrored, work)
        canvas.blit(pygame.transform.flip(mirrored, True, False), (0, 0))
    return pygame.transform.smoothscale(canvas, (size, size))


def build_cow(size: int, facing: Direction) -> pygame.Surface:
    work = size * SPRITE_SCALE
    canvas = _actor_canvas(work)
    u = work / 192.0
    if facing is Direction.NORTH:
        _draw_cow_base(canvas, u, facing)
        return pygame.transform.smoothscale(canvas, (size, size))

    if facing is Direction.SOUTH:
        _draw_cow_base(canvas, u, facing)
        _draw_cow_head_front(canvas, u)
    else:
        # Profile view: body drawn compactly, head to the east.
        _shadow(canvas, int(96 * u), int(170 * u), int(58 * u), int(16 * u))
        for x in (54, 76, 116, 138):
            _ellipse(canvas, theme.WOOD_DARK, (x * u, 142 * u, 18 * u, 26 * u))
            _ellipse(canvas, BOOT, (x * u, 146 * u, 16 * u, 18 * u))
        _ellipse(canvas, theme.COW_WHITE, (36 * u, 82 * u, 116 * u, 70 * u))
        _ellipse(canvas, theme.darken(theme.COW_WHITE, 0.05), (42 * u, 88 * u, 104 * u, 58 * u))
        _ellipse(canvas, theme.COW_BROWN, (52 * u, 94 * u, 38 * u, 28 * u))
        _ellipse(canvas, theme.COW_BROWN, (84 * u, 112 * u, 34 * u, 20 * u))
        # tail
        pygame.draw.arc(
            canvas,
            theme.COW_BROWN,
            pygame.Rect(24 * u, 88 * u, 30 * u, 40 * u),
            math.radians(120),
            math.radians(300),
            max(2, int(4 * u)),
        )
        _circle(canvas, theme.COW_BROWN, (30 * u, 116 * u), 6 * u)
        _draw_cow_head_east(canvas, u)

    if facing is Direction.WEST:
        canvas = pygame.transform.flip(canvas, True, False)
    return pygame.transform.smoothscale(canvas, (size, size))


# ---------------------------------------------------------------------------
# Props
# ---------------------------------------------------------------------------
def build_obstacle(size: int) -> pygame.Surface:
    """A hay bale - the obstacle the player places."""
    work = size * 3
    canvas = _actor_canvas(work)
    u = work / 64.0
    _shadow(canvas, int(32 * u), int(54 * u), int(22 * u), int(7 * u), 58)
    _rounded(canvas, theme.WOOD_DARK, (10 * u, 20 * u, 44 * u, 32 * u), int(9 * u))
    _rounded(canvas, STRAW, (12 * u, 21 * u, 40 * u, 29 * u), int(8 * u))
    for offset in (0, 8, 16):
        _line(canvas, STRAW_DARK, (13 * u, (24 + offset) * u), (51 * u, (30 + offset) * u), max(1, int(1.2 * u)))
    _rounded(canvas, theme.CLAY, (24 * u, 21 * u, 7 * u, 29 * u), int(2 * u))
    _line(canvas, STRAW_DARK, (30 * u, 24 * u), (30 * u, 48 * u), max(1, int(1.2 * u)))
    _circle(canvas, STRAW_LIGHT, (18 * u, 28 * u), 3 * u)
    _circle(canvas, STRAW_LIGHT, (41 * u, 42 * u), 2.6 * u)
    return pygame.transform.smoothscale(canvas, (size, size))


def build_apple(size: int) -> pygame.Surface:
    work = size * 3
    canvas = _actor_canvas(work)
    u = work / 64.0
    _shadow(canvas, int(32 * u), int(50 * u), int(14 * u), int(5 * u), 50)
    _circle(canvas, theme.BERRY, (30 * u, 34 * u), 15 * u)
    _circle(canvas, theme.BERRY_LIGHT, (36 * u, 30 * u), 12 * u)
    _circle(canvas, theme.lighten(theme.BERRY, 0.35), (26 * u, 27 * u), 4 * u)
    _line(canvas, theme.WOOD_DARK, (32 * u, 20 * u), (34 * u, 12 * u), max(2, int(2.4 * u)))
    _ellipse(canvas, theme.LEAF, (34 * u, 10 * u, 14 * u, 8 * u))
    return pygame.transform.smoothscale(canvas, (size, size))


def build_mud(size: int) -> pygame.Surface:
    work = size * 3
    canvas = _actor_canvas(work)
    u = work / 64.0
    _ellipse(canvas, theme.DIRT_DARK, (6 * u, 22 * u, 52 * u, 30 * u))
    _ellipse(canvas, theme.DIRT, (10 * u, 25 * u, 44 * u, 22 * u))
    for x, y in ((20, 34), (34, 30), (42, 38)):
        _ellipse(canvas, theme.darken(theme.DIRT, 0.12), (x * u, y * u, 8 * u, 4 * u))
    return pygame.transform.smoothscale(canvas, (size, size))


def build_signpost(size: int) -> pygame.Surface:
    work = size * 3
    canvas = _actor_canvas(work)
    u = work / 64.0
    _shadow(canvas, int(34 * u), int(54 * u), int(14 * u), int(5 * u), 50)
    _rounded(canvas, theme.WOOD_DARK, (30 * u, 16 * u, 6 * u, 40 * u), int(2 * u))
    _rounded(canvas, theme.WOOD_LIGHT, (10 * u, 20 * u, 38 * u, 16 * u), int(4 * u))
    _polygon(canvas, theme.WOOD_LIGHT, [(48 * u, 20 * u), (58 * u, 28 * u), (48 * u, 36 * u)])
    _line(canvas, theme.WOOD_DARK, (16 * u, 28 * u), (40 * u, 28 * u), max(1, int(2 * u)))
    return pygame.transform.smoothscale(canvas, (size, size))


def build_horn(size: int) -> pygame.Surface:
    work = size * 3
    canvas = _actor_canvas(work)
    u = work / 64.0
    _circle(canvas, theme.CLAY, (22 * u, 34 * u), 16 * u)
    _circle(canvas, theme.CLAY_LIGHT, (18 * u, 30 * u), 10 * u)
    _polygon(canvas, theme.SUN, [(34 * u, 30 * u), (58 * u, 16 * u), (56 * u, 44 * u)])
    _polygon(canvas, theme.SUN_LIGHT, [(36 * u, 30 * u), (54 * u, 20 * u), (53 * u, 38 * u)])
    _circle(canvas, theme.WOOD_DARK, (22 * u, 34 * u), 5 * u)
    return pygame.transform.smoothscale(canvas, (size, size))


PORTAL_COLORS = ((151, 188, 214), (206, 170, 200))


def build_portal(size: int, variant: int = 0) -> pygame.Surface:
    work = size * 3
    canvas = _actor_canvas(work)
    u = work / 64.0
    color = PORTAL_COLORS[variant % len(PORTAL_COLORS)]
    _ellipse(canvas, theme.darken(color, 0.2), (10 * u, 8 * u, 44 * u, 52 * u))
    _ellipse(canvas, color, (14 * u, 12 * u, 36 * u, 44 * u))
    for index, radius in enumerate((14, 9, 5)):
        pygame.draw.arc(
            canvas,
            theme.lighten(color, 0.35 - index * 0.06),
            pygame.Rect((32 - radius) * u, (34 - radius) * u, radius * 2 * u, radius * 2 * u),
            index * 1.4,
            index * 1.4 + 3.6,
            max(1, int(1.8 * u)),
        )
    return pygame.transform.smoothscale(canvas, (size, size))


def build_crate(size: int) -> pygame.Surface:
    work = size * 3
    canvas = _actor_canvas(work)
    u = work / 64.0
    _shadow(canvas, int(32 * u), int(54 * u), int(20 * u), int(6 * u), 50)
    _rounded(canvas, theme.WOOD_DARK, (12 * u, 16 * u, 40 * u, 38 * u), int(5 * u))
    _rounded(canvas, theme.WOOD, (15 * u, 19 * u, 34 * u, 32 * u), int(4 * u))
    _line(canvas, theme.WOOD_DARK, (18 * u, 22 * u), (46 * u, 48 * u), max(2, int(2 * u)))
    _line(canvas, theme.WOOD_DARK, (46 * u, 22 * u), (18 * u, 48 * u), max(2, int(2 * u)))
    return pygame.transform.smoothscale(canvas, (size, size))


def build_hat(size: int) -> pygame.Surface:
    """A straw hat that pops off the farmer's head when he catches a cow."""
    work = size * 3
    canvas = _actor_canvas(work)
    u = work / 64.0
    _ellipse(canvas, theme.CREAM_DARK, (2 * u, 26 * u, 60 * u, 24 * u))
    _ellipse(canvas, STRAW_LIGHT, (4 * u, 27 * u, 56 * u, 20 * u))
    _ellipse(canvas, STRAW, (18 * u, 12 * u, 28 * u, 26 * u))
    _ellipse(canvas, STRAW_LIGHT, (21 * u, 14 * u, 22 * u, 18 * u))
    _rounded(canvas, theme.CLAY, (19 * u, 28 * u, 26 * u, 6 * u), int(3 * u))
    return pygame.transform.smoothscale(canvas, (size, size))


def build_tree(size: int) -> pygame.Surface:
    """A tree without a grass background, for menu decorations."""
    work = size * 3
    canvas = _actor_canvas(work)
    u = work / 64.0
    shadow = pygame.Surface((work, work), pygame.SRCALPHA)
    _ellipse(shadow, (*theme.SHADOW, 48), (10 * u, 48 * u, 48 * u, 14 * u))
    canvas.blit(shadow, (0, 0))
    _rounded(canvas, theme.WOOD_DARK, (28 * u, 44 * u, 9 * u, 16 * u), int(3 * unit_u(u)))
    _rounded(canvas, theme.WOOD, (30 * u, 44 * u, 5 * u, 14 * u), int(2 * unit_u(u)))
    for x, y, radius, color in (
        (20, 34, 15, theme.LEAF_DARK),
        (44, 34, 15, theme.LEAF_DARK),
        (32, 28, 19, theme.LEAF),
        (22, 44, 13, theme.LEAF),
        (44, 44, 13, theme.LEAF),
        (32, 38, 17, theme.LEAF_LIGHT),
    ):
        _circle(canvas, color, (x * u, y * u), radius * u)
    for x, y, radius in ((27, 26, 8), (41, 34, 6), (26, 42, 5)):
        _circle(canvas, theme.lighten(theme.LEAF, 0.24), (x * u, y * u), radius * u)
    return pygame.transform.smoothscale(canvas, (size, size))


def unit_u(u: float) -> float:
    return max(1.0, u)


def build_target_marker(size: int) -> pygame.Surface:
    """Soft ring used to highlight a tutorial goal tile."""
    work = size * 2
    canvas = _actor_canvas(work)
    for index, radius in enumerate((work * 0.44, work * 0.36)):
        alpha = 150 if index == 0 else 90
        layer = pygame.Surface((work, work), pygame.SRCALPHA)
        pygame.draw.circle(layer, (*theme.SUN, alpha), (work // 2, work // 2), int(radius), 3)
        canvas.blit(layer, (0, 0))
    return pygame.transform.smoothscale(canvas, (size, size))


# ---------------------------------------------------------------------------
# Decorative scenery for menus
# ---------------------------------------------------------------------------
def draw_meadow_background(surface: pygame.Surface, time_s: float = 0.0) -> None:
    """Sky, sun, clouds and rolling hills used behind the menus."""
    width, height = surface.get_size()
    # Start from grass so no transparent/black gaps can peek through anywhere.
    surface.fill(theme.GRASS)
    theme.vertical_gradient(surface, pygame.Rect(0, 0, width, int(height * 0.62)), theme.SKY_PALE, theme.SKY)
    horizon = int(height * 0.58)

    # sun
    sun_layer = pygame.Surface((220, 220), pygame.SRCALPHA)
    for radius, alpha in ((86, 26), (64, 34), (48, 255)):
        pygame.draw.circle(sun_layer, (*theme.SUN_LIGHT, alpha), (110, 110), radius)
    surface.blit(sun_layer, (width - 300, 40))

    # clouds
    rng = random.Random(7)
    for index in range(4):
        cx = int((index * 340 + time_s * 12) % (width + 280)) - 140
        cy = 70 + index * 44
        cloud = pygame.Surface((220, 90), pygame.SRCALPHA)
        for dx, dy, radius in ((50, 50, 34), (95, 38, 42), (145, 50, 32), (110, 58, 30)):
            pygame.draw.circle(cloud, (*theme.WHITE_WARM, 210), (dx, dy), radius)
        surface.blit(cloud, (cx, cy))

    # hills
    hill = pygame.Surface((width, height - horizon), pygame.SRCALPHA)
    pygame.draw.ellipse(hill, theme.GRASS_LIGHT, (-180, -120, width * 0.7, 320))
    pygame.draw.ellipse(hill, theme.GRASS, (width * 0.35, -160, width * 0.8, 360))
    surface.blit(hill, (0, horizon - 60))
    pygame.draw.rect(surface, theme.GRASS, pygame.Rect(0, horizon + 100, width, height - horizon))
    theme.vertical_gradient(
        surface,
        pygame.Rect(0, horizon + 100, width, height - horizon - 100),
        theme.GRASS,
        theme.GRASS_DARK,
    )

    # fence line
    fence_y = horizon + 150
    for x in range(-10, width + 40, 64):
        pygame.draw.rect(surface, theme.WOOD_DARK, (x, fence_y - 4, 10, 46), border_radius=3)
        pygame.draw.rect(surface, theme.WOOD_LIGHT, (x + 2, fence_y - 2, 6, 42), border_radius=2)
    for rail_y in (fence_y + 6, fence_y + 26):
        pygame.draw.rect(surface, theme.WOOD_DARK, (0, rail_y, width, 8), border_radius=4)
        pygame.draw.rect(surface, theme.WOOD_LIGHT, (0, rail_y + 2, width, 4), border_radius=2)

    # flower sprinkles
    for _ in range(46):
        x = rng.randrange(0, width)
        y = rng.randrange(horizon + 170, height - 8)
        color = rng.choice((theme.SUN_LIGHT, theme.PINK, theme.WHITE_WARM))
        pygame.draw.circle(surface, color, (x, y), rng.choice((2, 3)))
        pygame.draw.line(surface, theme.LEAF_DARK, (x, y), (x, y + 4), 1)


# ---------------------------------------------------------------------------
# Cached sprite factory
# ---------------------------------------------------------------------------
class ArtCache:
    """Caches tiles and character sprites for a given cell size."""

    def __init__(self, cell: int = BASE_CELL) -> None:
        self.cell = cell
        self._tiles: Dict[Tuple, pygame.Surface] = {}
        self._farmers: Dict[Direction, pygame.Surface] = {}
        self._cows: Dict[Direction, pygame.Surface] = {}
        self._props: Dict[str, pygame.Surface] = {}
        self._rotated: Dict[Tuple[str, int, int], pygame.Surface] = {}

    # -- tiles ---------------------------------------------------------
    def tile(self, kind: TileKind, variant: int = 0, fence_mask: Optional[int] = None) -> pygame.Surface:
        mask = (fence_mask or 0) & 15 if kind in (TileKind.FENCE, TileKind.POND) else None
        key = (kind, variant % 4, mask)
        cached = self._tiles.get(key)
        if cached is not None:
            return cached
        size = self.cell
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        rng = random.Random(zlib.crc32(f"{kind.value}-{variant}".encode()))
        painter = _painters.get(kind, paint_grass)
        painter(surface, size, rng, variant % 4, mask)
        self._tiles[key] = surface
        return surface

    # -- characters ----------------------------------------------------
    def farmer(self, facing: Direction) -> pygame.Surface:
        sprite = self._farmers.get(facing)
        if sprite is None:
            sprite = build_farmer(self.cell, facing)
            self._farmers[facing] = sprite
        return sprite

    def cow(self, facing: Direction) -> pygame.Surface:
        sprite = self._cows.get(facing)
        if sprite is None:
            sprite = build_cow(self.cell, facing)
            self._cows[facing] = sprite
        return sprite

    # -- props ---------------------------------------------------------
    def prop(self, name: str) -> pygame.Surface:
        sprite = self._props.get(name)
        if sprite is not None:
            return sprite
        builders = {
            "obstacle": lambda: build_obstacle(self.cell),
            "apple": lambda: build_apple(self.cell),
            "mud": lambda: build_mud(self.cell),
            "signpost": lambda: build_signpost(self.cell),
            "horn": lambda: build_horn(self.cell),
            "crate": lambda: build_crate(self.cell),
            "marker": lambda: build_target_marker(self.cell),
            "portal_a": lambda: build_portal(self.cell, 0),
            "portal_b": lambda: build_portal(self.cell, 1),
        }
        builder = builders.get(name)
        if builder is None:
            raise KeyError(f"unknown prop sprite: {name}")
        sprite = builder()
        self._props[name] = sprite
        return sprite

    def rotated(self, name: str, angle: int) -> pygame.Surface:
        """Rotate a prop by a multiple of 15 degrees (cached)."""
        snapped = int(round(angle / 15.0)) * 15
        key = (name, snapped, self.cell)
        cached = self._rotated.get(key)
        if cached is None:
            cached = pygame.transform.rotozoom(self.prop(name), snapped, 1.0)
            self._rotated[key] = cached
        return cached

    def slot_sprite(self, kind: str, size: int = 44) -> pygame.Surface:
        """Small icon used in the item palette / HUD."""
        key = f"slot_{kind}_{size}"
        cached = self._props.get(key)
        if cached is not None:
            return cached
        builders = {
            "apple": build_apple,
            "mud": build_mud,
            "signpost": build_signpost,
            "horn": build_horn,
            "crate": build_crate,
            "obstacle": build_obstacle,
            "portal": lambda s: build_portal(s, 0),
        }
        builder = builders.get(kind, build_obstacle)
        sprite = builder(size)
        self._props[key] = sprite
        return sprite
