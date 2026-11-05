"""Render an art contact sheet to a PNG for visual inspection."""
from __future__ import annotations
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pygame
from game import art, theme
from game.models import CowPersonality, Direction, TileKind
from game.levels import load_levels

pygame.init()
pygame.display.set_mode((1, 1))
fonts = theme.FontBook()
width, height = 1180, 760
surface = pygame.Surface((width, height))
surface.fill(theme.CREAM)

art_cache = art.ArtCache(64)
# tiles row
x, y = 20, 40
theme.draw_text(surface, fonts, "地块", (x, y), theme.FONT_H2, theme.INK)
y += 40
for i, kind in enumerate(TileKind):
    tile = art_cache.tile(kind, i)
    surface.blit(tile, (x + i * 72, y))
    theme.draw_text(surface, fonts, kind.value, (x + i * 72, y + 68), theme.FONT_TINY, theme.INK_SOFT)

# characters
y += 130
theme.draw_text(surface, fonts, "角色", (x, y), theme.FONT_H2, theme.INK)
y += 40
labels = []
cx = x
for facing in (Direction.SOUTH, Direction.NORTH, Direction.EAST, Direction.WEST):
    surface.blit(art_cache.farmer(facing), (cx, y))
    theme.draw_text(surface, fonts, f"农夫{facing.label}", (cx, y + 68), theme.FONT_TINY, theme.INK_SOFT)
    cx += 80
cx += 20
for personality in (CowPersonality.NORMAL, CowPersonality.STUBBORN, CowPersonality.GREEDY, CowPersonality.TIMID):
    for facing in (Direction.SOUTH, Direction.EAST):
        surface.blit(art_cache.cow(facing, personality), (cx, y))
        theme.draw_text(surface, fonts, f"{personality.label}{facing.label}", (cx, y + 68), theme.FONT_TINY, theme.INK_SOFT)
        cx += 72
    cx += 8

# props
y += 110
theme.draw_text(surface, fonts, "道具", (x, y), theme.FONT_H2, theme.INK)
y += 36
for i, name in enumerate(["obstacle", "apple", "mud", "signpost", "horn", "crate", "portal_a", "portal_b", "marker"]):
    surface.blit(art_cache.prop(name), (x + i * 76, y))
    theme.draw_text(surface, fonts, name, (x + i * 76, y + 68), theme.FONT_TINY, theme.INK_SOFT)

# a real board
y += 110
levels = load_levels()
level = levels[4]
theme.draw_text(surface, fonts, f"地图演示：{level.name}", (x, y), theme.FONT_H2, theme.INK)
y += 36
for r in range(level.height):
    for c in range(level.width):
        kind = level.tile_at((r, c))
        tile = art_cache.tile(kind, (r * 7 + c * 13) % 4)
        surface.blit(tile, (x + c * 40, y + r * 40))
# actors
fr = level.farmer_start
surface.blit(pygame.transform.smoothscale(art_cache.farmer(level.farmer_facing), (40, 40)), (x + fr[1] * 40, y + fr[0] * 40))
cow = level.cow_positions[0]
sprite = art_cache.cow(level.cow_facings[0], CowPersonality.NORMAL)
surface.blit(pygame.transform.smoothscale(sprite, (40, 40)), (x + cow[1] * 40, y + cow[0] * 40))
out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/art_preview.png")
pygame.image.save(surface, str(out))
print("saved", out)
