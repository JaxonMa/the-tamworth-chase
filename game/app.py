"""Application shell: window, scene routing and the main loop."""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Set

import pygame

from . import art, theme
from .audio import AudioManager
from .achievements import AchievementTracker
from .levels import LevelError, load_level_file, load_levels
from .models import CowPersonality, Direction, Level, Rank
from .paths import ensure_data_dir, project_root
from .progress import ProgressStore
from .scenes.base import Scene
from .scenes.level_select import LevelSelectScene
from .scenes.menu import MenuScene
from .scenes.play import PlayScene
from .scenes.settings import SettingsScene
from .tutorial import TutorialBook, TutorialCatalog

GAME_TITLE = "The Tamworth Chase · 塔姆沃斯追逐"


def project_path(relative: str):
    return project_root() / relative

MVP_FEATURES = {"main", "settings"}
ALL_FEATURES = {"main", "tutorial", "challenge", "daily", "editor", "achievement", "settings"}
TUTORIAL_FEATURES = {"main", "tutorial", "settings"}


class App:
    """Owns the window and the shared services used by every scene."""

    def __init__(self, features: Optional[Set[str]] = None) -> None:
        pygame.init()
        pygame.display.set_caption(GAME_TITLE)
        self.screen = pygame.display.set_mode((theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.features = set(features) if features is not None else set(ALL_FEATURES)

        self.fonts = theme.FontBook()
        self.cache = art.ArtCache(theme.CELL_SIZE)
        self.store = ProgressStore().load()
        self.sound = AudioManager(
            enabled=bool(self.store.get_setting("sound", True)),
            volume=float(self.store.get_setting("volume", 0.6)),
        )
        self.levels = load_levels()
        self.levels_by_id: Dict[str, Level] = {level.level_id: level for level in self.levels}
        try:
            self.challenges = load_level_file(
                project_path("levels/challenges.json"), source="challenge"
            )
        except LevelError:
            self.challenges = ()
        self.challenges_by_id: Dict[str, Level] = {
            level.level_id: level for level in self.challenges
        }
        self.achievements = AchievementTracker(self.store)
        self.daily_cache: Dict[str, Level] = {}
        self.book: Optional[TutorialBook] = None
        self.catalog: Optional[TutorialCatalog] = None
        self.editor_model = None
        if "tutorial" in self.features:
            self._load_tutorials()

        self.scene: Optional[Scene] = None
        self.transition = 1.0
        self._set_icon()
        self.open_scene("menu")

    # ------------------------------------------------------------------
    def _set_icon(self) -> None:
        try:
            icon = pygame.Surface((64, 64), pygame.SRCALPHA)
            icon.blit(self.cache.cow(Direction.SOUTH, CowPersonality.NORMAL), (0, 0))
            pygame.display.set_icon(icon)
        except pygame.error:
            pass

    def _load_tutorials(self) -> None:
        try:
            self.catalog = TutorialCatalog.load()
            self.book = TutorialBook(self.store, self.catalog)
        except LevelError:
            self.catalog = None
            self.book = None
            self.features.discard("tutorial")

    # ------------------------------------------------------------------
    # Scene routing
    # ------------------------------------------------------------------
    def open_scene(self, key: str) -> None:
        scene: Optional[Scene] = None
        if key == "menu":
            scene = MenuScene(self)
        elif key == "level_select":
            scene = LevelSelectScene(self)
        elif key == "settings":
            scene = SettingsScene(self)
        elif key == "tutorial":
            from .scenes.tutorial_select import TutorialSelectScene

            scene = TutorialSelectScene(self)
        elif key == "challenge":
            from .scenes.challenge import ChallengeScene

            scene = ChallengeScene(self)
        elif key == "daily":
            from .scenes.daily import DailyScene

            scene = DailyScene(self)
        elif key == "editor":
            from .scenes.editor import EditorScene

            scene = EditorScene(self)
        elif key == "achievement":
            from .scenes.achievements import AchievementScene

            scene = AchievementScene(self)
        if scene is None:
            scene = MenuScene(self)
        if self.scene is not None:
            self.scene.on_exit()
        self.scene = scene
        self.scene.on_enter()
        self.transition = 1.0

    def start_level(
        self,
        level: Level,
        *,
        mode: str = "main",
        chapter: str = "",
        challenge_key: str = "",
        daily_key: str = "",
        return_to: str = "level_select",
    ) -> None:
        number = 0
        for index, item in enumerate(self.levels):
            if item.level_id == level.level_id:
                number = index + 1
                break
        if self.scene is not None:
            self.scene.on_exit()
        self.scene = PlayScene(
            self,
            level,
            mode=mode,
            level_number=number,
            chapter=chapter,
            challenge_key=challenge_key,
            daily_key=daily_key,
            return_to=return_to,
        )
        self.scene.on_enter()
        self.transition = 1.0

    def open_tutorial_chapter(self, chapter_id: str) -> None:
        from .scenes.tutorial_select import TutorialChapterScene

        if self.catalog is None or self.book is None:
            self.open_scene("menu")
            return
        if self.scene is not None:
            self.scene.on_exit()
        self.scene = TutorialChapterScene(self, chapter_id)
        self.scene.on_enter()
        self.transition = 1.0

    def start_editor_tutorial(self, chapter_id: str, lesson) -> None:
        """Open the level editor with a tutorial task (added with the editor)."""
        from .scenes.editor import EditorScene

        if self.scene is not None:
            self.scene.on_exit()
        self.scene = EditorScene(self, tutorial_chapter=chapter_id, tutorial_lesson=lesson)
        self.scene.on_enter()
        self.transition = 1.0

    def start_tutorial_lesson(self, chapter_id: str, lesson_id: str) -> None:
        if self.catalog is None or self.book is None:
            self.open_scene("menu")
            return
        lesson = self.catalog.find_lesson(chapter_id, lesson_id)
        if lesson is None:
            self.open_tutorial_chapter(chapter_id)
            return
        self.start_level(lesson, mode="tutorial", chapter=chapter_id, return_to="tutorial")

    def open_next_tutorial_lesson(self, chapter_id: str) -> None:
        if self.book is None:
            self.open_scene("menu")
            return
        lesson = self.book.next_lesson(chapter_id)
        if lesson is None:
            self.open_tutorial_chapter(chapter_id)
            return
        self.start_tutorial_lesson(chapter_id, lesson.tutorial_id or lesson.level_id)

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def on_level_cleared(self, level: Level, sim, rank: Rank, **kwargs) -> None:
        """Evaluate achievements after any clear."""
        self.achievements.on_level_cleared(level, sim, rank, self.store, **kwargs)

    def daily_level(self) -> Level:
        from .daily import date_key, generate_daily

        key = date_key()
        if key not in self.daily_cache:
            self.daily_cache[key] = generate_daily()
        return self.daily_cache[key]

    def quit(self) -> None:
        self.running = False

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if self.scene is not None:
            self.scene.handle_event(event)

    def update(self, dt: float) -> None:
        if self.scene is not None:
            self.scene.update(dt)
        if self.transition > 0:
            self.transition = max(0.0, self.transition - dt * 4.0)

    def draw(self) -> None:
        if self.scene is not None:
            self.scene.draw(self.screen)
        if self.transition > 0:
            overlay = pygame.Surface((theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT))
            overlay.fill(theme.CREAM)
            overlay.set_alpha(int(255 * min(1.0, self.transition)))
            self.screen.blit(overlay, (0, 0))

    def run(self) -> int:
        while self.running:
            dt = min(0.05, self.clock.tick(theme.FPS) / 1000.0)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()
        return 0

    # ------------------------------------------------------------------
    # Automation helpers (used by the screenshot tool)
    # ------------------------------------------------------------------
    def render_once(self) -> pygame.Surface:
        self.update(1 / 60)
        self.draw()
        return self.screen.copy()
