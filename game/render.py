"""Board rendering, animation and playful effects."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Set, Tuple

import pygame

from . import art, theme
from .core import Simulation
from .models import (
    Actor,
    CowPersonality,
    Direction,
    GameStatus,
    ItemKind,
    Level,
    Pos,
    PredictionFrame,
    TileKind,
)
from .playback import Playback, VisualActor

CELL = theme.CELL_SIZE
ORIGIN = theme.BOARD_ORIGIN


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------
@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: Tuple[int, int, int]
    size: float
    spin: float
    angle: float
    gravity: float
    shape: str = "petal"


@dataclass
class Ring:
    x: float
    y: float
    radius: float
    max_radius: float
    life: float
    max_life: float
    color: Tuple[int, int, int]
    width: int = 3


@dataclass
class FlyingHat:
    x: float
    y: float
    vx: float
    vy: float
    angle: float
    spin: float
    life: float
    max_life: float


class EffectSystem:
    """Small, self-contained particle + flourish system."""

    def __init__(self, low_effects: bool = False) -> None:
        self.low_effects = low_effects
        self.particles: List[Particle] = []
        self.rings: List[Ring] = []
        self.hats: List[FlyingHat] = []
        self.time = 0.0
        self.rng = random.Random(20240501)

    def set_low_effects(self, value: bool) -> None:
        self.low_effects = value
        if value:
            self.particles.clear()
            self.rings.clear()

    def update(self, dt: float) -> None:
        self.time += dt
        for particle in self.particles:
            particle.life -= dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vy += particle.gravity * dt
            particle.angle += particle.spin * dt
            particle.vx *= 0.99
        self.particles = [p for p in self.particles if p.life > 0]
        for ring in self.rings:
            ring.life -= dt
            ratio = 1.0 - ring.life / ring.max_life
            ring.radius = ring.max_radius * (0.25 + ratio * 0.75)
        self.rings = [r for r in self.rings if r.life > 0]
        for hat in self.hats:
            hat.life -= dt
            hat.x += hat.vx * dt
            hat.y += hat.vy * dt
            hat.vy += 420 * dt
            hat.angle += hat.spin * dt
        self.hats = [h for h in self.hats if h.life > 0]

    # -- spawners ------------------------------------------------------
    def burst_petals(self, center: Tuple[float, float], count: int = 18) -> None:
        if self.low_effects:
            return
        colors = (theme.SUN_LIGHT, theme.PINK, theme.WHITE_WARM, theme.GRASS_LIGHT)
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(60, 220)
            life = self.rng.uniform(0.7, 1.5)
            self.particles.append(
                Particle(
                    x=center[0],
                    y=center[1],
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed - 80,
                    life=life,
                    max_life=life,
                    color=self.rng.choice(colors),
                    size=self.rng.uniform(3.0, 6.0),
                    spin=self.rng.uniform(-6, 6),
                    angle=self.rng.uniform(0, math.tau),
                    gravity=260.0,
                )
            )

    def ring(self, center: Tuple[float, float], color=theme.SUN, max_radius: float = 90.0, life: float = 0.7) -> None:
        if self.low_effects:
            return
        self.rings.append(
            Ring(x=center[0], y=center[1], radius=10, max_radius=max_radius, life=life, max_life=life, color=color)
        )

    def flying_hat(self, center: Tuple[float, float]) -> None:
        if self.low_effects:
            return
        self.hats.append(
            FlyingHat(
                x=center[0],
                y=center[1],
                vx=self.rng.uniform(-40, 40),
                vy=-300.0,
                angle=0.0,
                spin=self.rng.uniform(-360, 360),
                life=1.6,
                max_life=1.6,
            )
        )

    def loop_swirl(self, center: Tuple[float, float]) -> None:
        self.ring(center, color=theme.SKY_DEEP, max_radius=110, life=1.4)
        if self.low_effects:
            return
        for index in range(14):
            angle = math.tau * index / 14
            self.particles.append(
                Particle(
                    x=center[0] + math.cos(angle) * 70,
                    y=center[1] + math.sin(angle) * 70,
                    vx=-math.cos(angle) * 40,
                    vy=-math.sin(angle) * 40,
                    life=1.2,
                    max_life=1.2,
                    color=theme.SKY_DEEP,
                    size=4.0,
                    spin=4.0,
                    angle=angle,
                    gravity=0.0,
                    shape="dot",
                )
            )

    # -- drawing -------------------------------------------------------
    def draw(self, surface: pygame.Surface, origin: Tuple[int, int]) -> None:
        ox, oy = origin
        for ring in self.rings:
            alpha = max(0, int(180 * (ring.life / ring.max_life)))
            radius = int(ring.radius)
            if radius <= 0:
                continue
            layer = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(
                layer,
                (*ring.color, alpha),
                (radius + 4, radius + 4),
                radius,
                ring.width,
            )
            surface.blit(layer, (ox + int(ring.x) - radius - 4, oy + int(ring.y) - radius - 4))
        for particle in self.particles:
            ratio = max(0.0, particle.life / particle.max_life)
            size = max(1.0, particle.size * (0.4 + 0.6 * ratio))
            pos = (ox + int(particle.x), oy + int(particle.y))
            if particle.shape == "dot":
                pygame.draw.circle(surface, particle.color, pos, int(size))
            else:
                petal = pygame.Surface((int(size * 2), int(size * 2)), pygame.SRCALPHA)
                pygame.draw.ellipse(
                    petal,
                    (*particle.color, int(230 * ratio)),
                    pygame.Rect(0, 0, int(size * 2), int(size)),
                )
                rotated = pygame.transform.rotate(petal, math.degrees(particle.angle) % 360)
                surface.blit(rotated, (pos[0] - rotated.get_width() // 2, pos[1] - rotated.get_height() // 2))
        for hat in self.hats:
            sprite = art.build_hat(46)
            rotated = pygame.transform.rotozoom(sprite, hat.angle, 1.0)
            surface.blit(rotated, (ox + int(hat.x) - rotated.get_width() // 2, oy + int(hat.y) - rotated.get_height() // 2))


# ---------------------------------------------------------------------------
# Board view description
# ---------------------------------------------------------------------------
@dataclass
class BoardView:
    level: Level
    sim: Simulation
    playback: Optional[Playback] = None
    hover: Optional[Pos] = None
    hover_valid: bool = True
    placement_mode: bool = False
    show_prediction: bool = True
    prediction: Sequence[PredictionFrame] = ()
    highlight: Optional[Pos] = None
    disabled: bool = False
    overlay_alpha: int = 0
    effects: Optional[EffectSystem] = None
    show_facing_marks: bool = True
    pulse: float = 0.0
    hover_sprite: Optional[pygame.Surface] = None


class BoardRenderer:
    """Draws the meadow, the actors and every overlay."""

    def __init__(self, cache: art.ArtCache, fonts: theme.FontBook) -> None:
        self.cache = cache
        self.fonts = fonts
        self._frame_rect = pygame.Rect(
            ORIGIN[0] - 14, ORIGIN[1] - 14, CELL * 10 + 28, CELL * 10 + 28
        )

    # -- helpers -------------------------------------------------------
    @staticmethod
    def cell_center(pos: Tuple[float, float]) -> Tuple[int, int]:
        return (
            ORIGIN[0] + int((pos[1] + 0.5) * CELL),
            ORIGIN[1] + int((pos[0] + 0.5) * CELL),
        )

    @staticmethod
    def cell_rect(pos: Pos) -> pygame.Rect:
        return pygame.Rect(ORIGIN[0] + pos[1] * CELL, ORIGIN[1] + pos[0] * CELL, CELL, CELL)

    # -- public API ----------------------------------------------------
    def draw(self, surface: pygame.Surface, view: BoardView) -> None:
        self._draw_frame(surface)
        self._draw_tiles(surface, view)
        if view.show_prediction and view.prediction:
            self._draw_prediction(surface, view)
        self._draw_highlight(surface, view)
        self._draw_placeables(surface, view)
        self._draw_hover(surface, view)
        self._draw_actors(surface, view)
        if view.effects is not None:
            view.effects.draw(surface, ORIGIN)
        if view.overlay_alpha:
            overlay = pygame.Surface((CELL * 10, CELL * 10), pygame.SRCALPHA)
            overlay.fill((*theme.CREAM, view.overlay_alpha))
            surface.blit(overlay, ORIGIN)

    # -- pieces --------------------------------------------------------
    def _draw_frame(self, surface: pygame.Surface) -> None:
        theme.soft_shadow(surface, self._frame_rect, radius=26, alpha=42, offset=(0, 7))
        theme.rounded_rect(surface, self._frame_rect, theme.WOOD_LIGHT, radius=26)
        theme.rounded_rect(surface, self._frame_rect, theme.WOOD_DARK, radius=26, width=3)
        inner = self._frame_rect.inflate(-8, -8)
        pygame.draw.rect(surface, theme.GRASS_DARK, inner, border_radius=22)

    def _draw_tiles(self, surface: pygame.Surface, view: BoardView) -> None:
        level = view.level

        def kind_at(row: int, col: int) -> TileKind:
            return level.tile_at((row, col))

        draw_grid(surface, self.cache, level.width, level.height, kind_at)

    @staticmethod
    def _fence_variant(level: Level, row: int, col: int, kind: TileKind = TileKind.FENCE) -> int:
        """Bit mask of connecting tiles: 1=left, 2=right, 4=up, 8=down."""
        mask = 0
        for bit, (dr, dc) in ((1, (0, -1)), (2, (0, 1)), (4, (-1, 0)), (8, (1, 0))):
            r, c = row + dr, col + dc
            if level.is_inside((r, c)) and level.tile_at((r, c)) is kind:
                mask |= bit
        return mask

    def _draw_highlight(self, surface: pygame.Surface, view: BoardView) -> None:
        if view.highlight is None:
            return
        rect = self.cell_rect(view.highlight)
        pulse = 0.5 + 0.5 * math.sin(view.pulse * 3.4)
        layer = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        pygame.draw.rect(
            layer,
            (*theme.SUN, int(70 + 60 * pulse)),
            layer.get_rect().inflate(-6, -6),
            width=4,
            border_radius=14,
        )
        surface.blit(layer, rect.topleft)

    def _draw_prediction(self, surface: pygame.Surface, view: BoardView) -> None:
        frames = view.prediction
        if not frames:
            return
        farmer_points = [self.cell_center(view.sim.farmer.pos)]
        cow_points = [[self.cell_center(cow.pos)] for cow in view.sim.cows]
        for frame in frames:
            farmer_points.append(self.cell_center(frame.farmer_pos))
            for index, pos in enumerate(frame.cow_positions):
                if index < len(cow_points):
                    cow_points[index].append(self.cell_center(pos))

        layer = pygame.Surface((CELL * 10, CELL * 10), pygame.SRCALPHA)
        offset = (-ORIGIN[0], -ORIGIN[1])
        shifted = [(x + offset[0], y + offset[1]) for x, y in farmer_points]
        self._dashed_polyline(layer, shifted, (*theme.DENIM, 150))
        for points in cow_points:
            shifted_cow = [(x + offset[0], y + offset[1]) for x, y in points]
            self._dashed_polyline(layer, shifted_cow, (*theme.CLAY, 140))
        surface.blit(layer, ORIGIN)

        for index, frame in enumerate(frames):
            label = str(index + 1)
            for pos, color, show_label in (
                (frame.farmer_pos, theme.DENIM, True),
                (frame.cow_positions[0] if frame.cow_positions else frame.farmer_pos, theme.CLAY, False),
            ):
                center = self.cell_center(pos)
                token = pygame.Surface((28, 28), pygame.SRCALPHA)
                pygame.draw.circle(token, (*color, 145), (14, 14), 11)
                pygame.draw.circle(token, (*theme.WHITE_WARM, 190), (14, 14), 11, 2)
                surface.blit(token, (center[0] - 14, center[1] - 14))
                if show_label:
                    text = self.fonts.render(label, 16, theme.WHITE_WARM, True)
                    surface.blit(text, text.get_rect(center=center))

    @staticmethod
    def _dashed_polyline(surface: pygame.Surface, points: Sequence[Tuple[int, int]], color) -> None:
        for start, end in zip(points, points[1:]):
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            if length < 1:
                continue
            step = 8
            for offset in range(0, int(length), step * 2):
                a = offset / length
                b = min(1.0, (offset + step) / length)
                pygame.draw.line(
                    surface,
                    color,
                    (start[0] + dx * a, start[1] + dy * a),
                    (start[0] + dx * b, start[1] + dy * b),
                    3,
                )

    def _draw_placeables(self, surface: pygame.Surface, view: BoardView) -> None:
        sprite = self.cache.prop("obstacle")
        for pos in view.sim.obstacles:
            surface.blit(sprite, self.cell_rect(pos).topleft)

        portal_index = 0
        for pos, item in sorted(view.sim.items.items(), key=lambda pair: (pair[0][0], pair[0][1])):
            kind = item.kind
            if kind is ItemKind.SIGNPOST:
                angle = {Direction.EAST: 0, Direction.NORTH: 90, Direction.WEST: 180, Direction.SOUTH: 270}[
                    item.facing
                ]
                image = self.cache.rotated("signpost", angle)
                surface.blit(
                    image,
                    image.get_rect(center=self.cell_rect(pos).center),
                )
                continue
            if kind is ItemKind.PORTAL:
                name = "portal_a" if portal_index % 2 == 0 else "portal_b"
                portal_index += 1
                surface.blit(self.cache.prop(name), self.cell_rect(pos).topleft)
                continue
            if kind is ItemKind.CRATE:
                surface.blit(self.cache.prop("crate"), self.cell_rect(pos).topleft)
                continue
            if kind is ItemKind.APPLE:
                surface.blit(self.cache.prop("apple"), self.cell_rect(pos).topleft)
                continue
            if kind is ItemKind.MUD:
                surface.blit(self.cache.prop("mud"), self.cell_rect(pos).topleft)
                continue
            if kind is ItemKind.HORN:
                surface.blit(self.cache.prop("horn"), self.cell_rect(pos).topleft)

    def _draw_hover(self, surface: pygame.Surface, view: BoardView) -> None:
        if view.hover is None or not view.placement_mode:
            return
        rect = self.cell_rect(view.hover)
        color = theme.PRIMARY_BG if view.hover_valid else theme.CLAY
        layer = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        pygame.draw.rect(layer, (*color, 60), layer.get_rect().inflate(-4, -4), border_radius=14)
        pygame.draw.rect(layer, (*color, 200), layer.get_rect().inflate(-4, -4), width=3, border_radius=14)
        surface.blit(layer, rect.topleft)
        if view.hover_valid:
            ghost = (view.hover_sprite or self.cache.prop("obstacle")).copy()
            ghost.set_alpha(150)
            surface.blit(ghost, rect.topleft)

    def _draw_actors(self, surface: pygame.Surface, view: BoardView) -> None:
        sim = view.sim
        farmer_visual: VisualActor
        cow_visuals: Tuple[VisualActor, ...]
        if view.playback is not None:
            farmer_visual, cow_visuals = view.playback.actor_visuals()
        else:
            farmer_visual = VisualActor(
                float(sim.farmer.pos[0]), float(sim.farmer.pos[1]), sim.farmer.facing, False, 0.0, False
            )
            cow_visuals = tuple(
                VisualActor(float(cow.pos[0]), float(cow.pos[1]), cow.facing, False, 0.0, False)
                for cow in sim.cows
            )

        drawables = []
        for index, cow in enumerate(sim.cows):
            visual = cow_visuals[index]
            sprite = self.cache.cow(visual.facing, cow.personality)
            drawables.append((visual.row, visual.col, sprite, visual.wobble, index * 0.02))
        farmer_sprite = self.cache.farmer(farmer_visual.facing)
        drawables.append((farmer_visual.row, farmer_visual.col, farmer_sprite, farmer_visual.wobble, 0.5))
        drawables.sort(key=lambda item: (item[0], item[1]))

        for row, col, sprite, wobble, _ in drawables:
            center = self.cell_center((row, col))
            image = sprite
            if abs(wobble) > 0.5:
                image = pygame.transform.rotozoom(sprite, wobble, 1.0)
            rect = image.get_rect(center=center)
            surface.blit(image, rect.topleft)

        if view.show_facing_marks:
            self._draw_facing_mark(surface, farmer_visual, theme.WOOD_DARK, 0.85)
            for visual in cow_visuals:
                self._draw_facing_mark(surface, visual, theme.CLAY_DARK, 0.7)

    def _draw_facing_mark(
        self, surface: pygame.Surface, visual: VisualActor, color, alpha: float
    ) -> None:
        """A tiny arrow below the actor so the walk direction is unmistakable."""
        center = self.cell_center((visual.row, visual.col))
        dx, dy = visual.facing.delta
        base = (center[0], center[1] + 22)
        tip = (base[0] + dy * 7, base[1] + dx * 7)
        left = (base[0] - dy * 5 + dx * 3, base[1] - dx * 5 + dy * 3)
        right = (base[0] + dy * 5 + dx * 3, base[1] + dx * 5 + dy * 3)
        shade = tuple(int(c * 0.82) for c in color)
        pygame.draw.polygon(surface, shade, [tip, left, right])


def draw_grid(
    surface: pygame.Surface,
    cache: art.ArtCache,
    width: int,
    height: int,
    kind_at,
    origin: Tuple[int, int] = ORIGIN,
    cell: int = CELL,
) -> None:
    """Draw a grid of tiles, connecting fences and ponds to their neighbours."""

    def mask_for(row: int, col: int, kind: TileKind) -> int:
        mask = 0
        for bit, (dr, dc) in ((1, (0, -1)), (2, (0, 1)), (4, (-1, 0)), (8, (1, 0))):
            r, c = row + dr, col + dc
            if 0 <= r < height and 0 <= c < width and kind_at(r, c) is kind:
                mask |= bit
        return mask

    for row in range(height):
        for col in range(width):
            kind = kind_at(row, col)
            variant = (row * 7 + col * 13) % 4
            mask = None
            if kind in (TileKind.FENCE, TileKind.POND):
                mask = mask_for(row, col, kind)
            tile = cache.tile(kind, variant, fence_mask=mask)
            surface.blit(tile, (origin[0] + col * cell, origin[1] + row * cell))


# ---------------------------------------------------------------------------
# Shared decorations
# ---------------------------------------------------------------------------
def draw_board_caption(
    surface: pygame.Surface,
    fonts: theme.FontBook,
    text: str,
    pos: Tuple[int, int],
) -> None:
    theme.draw_text(surface, fonts, text, pos, theme.FONT_SMALL, theme.INK_SOFT)
