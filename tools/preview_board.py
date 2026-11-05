"""Render a play-board mock-up to PNG for visual inspection."""
from __future__ import annotations
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pygame
from game import art, theme
from game.levels import load_levels
from game.models import CowPersonality, Direction
from game.core import Simulation

pygame.init()
pygame.display.set_mode((1, 1))
fonts = theme.FontBook()
level = load_levels()[4]
CELL = 64
surface = pygame.Surface((CELL * 10, CELL * 10))
cache = art.ArtCache(CELL)
sim = Simulation(level)
sim.place_obstacle((4, 4))
for r in range(10):
    for c in range(10):
        surface.blit(cache.tile(level.tile_at((r, c)), (r * 7 + c * 13) % 4), (c * CELL, r * CELL))
surface.blit(cache.prop("obstacle"), (4 * CELL, 4 * CELL))
cs = sim.cows[0]
surface.blit(cache.cow(cs.facing, cs.personality), (cs.pos[1] * CELL, cs.pos[0] * CELL))
surface.blit(cache.farmer(sim.farmer.facing), (sim.farmer.pos[1] * CELL, sim.farmer.pos[0] * CELL))
out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/board.png")
pygame.image.save(surface, str(out))
print("saved", out)

# character close-ups
scale = 2
close = pygame.Surface((CELL * 4 * scale * 2 + 40, CELL * 3 * scale), pygame.SRCALPHA)
close.fill(theme.CREAM)
for i, facing in enumerate(Direction):
    sprite = cache.farmer(facing)
    close.blit(pygame.transform.scale(sprite, (CELL * scale, CELL * scale)), (10 + i * CELL * scale, 10))
    cow = cache.cow(facing, CowPersonality.STUBBORN)
    close.blit(pygame.transform.scale(cow, (CELL * scale, CELL * scale)), (10 + i * CELL * scale, 10 + CELL * scale + 10))
pygame.image.save(close, "/tmp/characters.png")
print("saved /tmp/characters.png")
