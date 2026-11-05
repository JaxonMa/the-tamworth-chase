"""Tutorial entry screens: chapter selection and lesson list.

The tutorial lives behind its own menu entry and never touches the campaign
level list or its unlock chain.
"""

from __future__ import annotations

from typing import List, Optional

import pygame

from .. import theme, ui
from ..models import Level
from ..progress import TUTORIAL_COMPLETED, TUTORIAL_IN_PROGRESS, TUTORIAL_NOT_STARTED, TUTORIAL_SKIPPED
from ..tutorial import TutorialChapter
from .base import Scene, draw_background, draw_footer, draw_header, make_back_button

ACCENTS = {
    "leaf": theme.LEAF,
    "sky": theme.SKY_DEEP,
    "clay": theme.CLAY,
    "sun": theme.SUN,
}

STATE_LABELS = {
    TUTORIAL_NOT_STARTED: "未开始",
    TUTORIAL_IN_PROGRESS: "进行中",
    TUTORIAL_COMPLETED: "已完成",
    TUTORIAL_SKIPPED: "已跳过",
}


class TutorialSelectScene(Scene):
    """Chapter picker shown from the main menu."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.back_button = make_back_button()
        self.cards: List[ui.Card] = []
        self.hovered_key: Optional[str] = None
        self.modal: Optional[ui.Modal] = None
        self.skip_button = ui.Button(
            pygame.Rect(theme.WINDOW_WIDTH - 400, theme.WINDOW_HEIGHT - 92, 190, 46),
            "跳过全部教程",
            "skip_all",
            style="ghost",
            font_size=theme.FONT_SMALL,
        )

    def on_enter(self) -> None:
        self.cards = []
        if self.app.catalog is None or self.app.book is None:
            return
        chapters = self.app.catalog.all()
        width, height = 350, 430
        gap = 30
        total = len(chapters) * width + max(0, len(chapters) - 1) * gap
        x = (theme.WINDOW_WIDTH - total) // 2
        y = 168
        for chapter in chapters:
            progress = self.app.book.chapter_progress(chapter.chapter_id)
            card = ui.Card(
                rect=pygame.Rect(x, y, width, height),
                title=chapter.title,
                key=chapter.chapter_id,
                accent=ACCENTS.get(chapter.accent, theme.LEAF),
                completed=progress.finished and progress.completed > 0,
            )
            self.cards.append(card)
            x += width + gap

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.modal is not None:
            action = self.modal.handle_event(event)
            if action:
                self._modal_action(action)
            return
        if self.back_button.handle_event(event):
            self.app.open_scene("menu")
            return
        if self.skip_button.handle_event(event):
            self._ask_skip_all()
            return
        for card in self.cards:
            action = card.handle_event(event)
            if action:
                self.app.sound.play("click")
                self.app.open_tutorial_chapter(action)
                return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.open_scene("menu")

    def _ask_skip_all(self) -> None:
        self.app.sound.play("click")
        self.modal = ui.Modal(
            "跳过全部教程？",
            "三个章节都会标记为已跳过，进度单独保存，主线关卡不受影响。\n之后仍可以在这里重玩任意一节课。",
            accent=theme.SKY_DEEP,
            badge="教程",
            buttons=[
                ui.Button(pygame.Rect(0, 0, 150, 50), "再想想", "cancel", style="ghost"),
                ui.Button(pygame.Rect(0, 0, 160, 50), "全部跳过", "confirm", style="primary"),
            ],
            width=620,
            height=330,
        )

    def _modal_action(self, action: str) -> None:
        self.modal = None
        if action == "confirm" and self.app.book is not None and self.app.catalog is not None:
            for chapter in self.app.catalog.all():
                self.app.book.skip_chapter(chapter.chapter_id)
            self.app.sound.play("unlock")
            self.on_enter()

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.modal is not None:
            self.modal.update(pygame.mouse.get_pos())
        self.hovered_key = next((card.key for card in self.cards if card.hovered), None)

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        completed = 0
        total = 0
        if self.app.book is not None and self.app.catalog is not None:
            for chapter in self.app.catalog.all():
                progress = self.app.book.chapter_progress(chapter.chapter_id)
                completed += progress.done
                total += progress.total
        draw_header(
            surface,
            self.fonts,
            "新手教程",
            f"完成 {completed} / {total} 节课 · 独立进度",
            badge="教程",
            badge_color=theme.SKY_DEEP,
        )
        if not self.cards:
            theme.panel(surface, pygame.Rect(340, 300, 600, 200))
            theme.draw_text(
                surface,
                self.fonts,
                "还没有找到教程数据文件。",
                (640, 380),
                theme.FONT_H2,
                theme.INK_SOFT,
                anchor="center",
            )
        for card in self.cards:
            self._draw_chapter_card(surface, card)
        if self.cards:
            self.skip_button.draw(surface, self.fonts)
        self.back_button.draw(surface, self.fonts)
        draw_footer(surface, self.fonts, "教程有独立入口和独立进度，与主线关卡互不影响")
        if self.modal is not None:
            self.modal.draw(surface, self.fonts)

    def _draw_chapter_card(self, surface: pygame.Surface, card: ui.Card) -> None:
        chapter = self.app.catalog.require(card.key) if self.app.catalog else None
        if chapter is None:
            return
        rect = card.rect
        # Custom header so the badge, title and subtitle never collide.
        lift = -3 if card.hovered else 0
        rect = rect.move(0, lift)
        theme.soft_shadow(surface, rect, radius=18, alpha=44 if card.hovered else 30, offset=(0, 7))
        theme.rounded_rect(surface, rect, theme.PANEL_BG, radius=18)
        theme.rounded_rect(
            surface,
            rect,
            theme.SUN_LIGHT if card.hovered else theme.PANEL_BORDER,
            radius=18,
            width=3 if card.hovered else 2,
        )
        accent_rect = pygame.Rect(rect.left + 22, rect.top + 22, 10, 34)
        theme.rounded_rect(surface, accent_rect, card.accent, radius=5)
        theme.draw_text(
            surface, self.fonts, chapter.title, (rect.left + 44, rect.top + 20), theme.FONT_H2, theme.INK, bold=True
        )
        badge_center = (rect.left + 44 + self.fonts.size_of(chapter.title, theme.FONT_H2, True)[0] + 44, rect.top + 38)
        ui.draw_pill(surface, self.fonts, chapter.badge, badge_center, card.accent)
        theme.draw_text(
            surface, self.fonts, chapter.subtitle, (rect.left + 44, rect.top + 64), theme.FONT_SMALL, theme.INK_SOFT
        )
        pygame.draw.line(
            surface, theme.PANEL_BORDER, (rect.left + 26, rect.top + 100), (rect.right - 26, rect.top + 100), 2
        )
        description = self.fonts.wrap(chapter.intro, theme.FONT_SMALL, rect.width - 60, theme.INK_SOFT)
        surface.blit(description, (rect.left + 30, rect.top + 118))

        progress = self.app.book.chapter_progress(card.key) if self.app.book else None
        if progress is not None:
            bar = pygame.Rect(rect.left + 30, rect.bottom - 118, rect.width - 60, 14)
            theme.rounded_rect(surface, bar, theme.CREAM_DARK, radius=7)
            if progress.total:
                filled = pygame.Rect(bar.left, bar.top, int(bar.width * progress.percent), bar.height)
                theme.rounded_rect(surface, filled, card.accent, radius=7)
            theme.draw_text(
                surface,
                self.fonts,
                f"{progress.done} / {progress.total} 节课",
                (rect.left + 30, rect.bottom - 96),
                theme.FONT_SMALL,
                theme.INK_SOFT,
            )
        button = pygame.Rect(rect.left + 30, rect.bottom - 62, rect.width - 60, 42)
        theme.rounded_rect(surface, button, card.accent, radius=12)
        theme.draw_text(
            surface,
            self.fonts,
            "进入章节",
            button.center,
            theme.FONT_BODY,
            theme.WHITE_WARM,
            anchor="center",
            bold=True,
        )


class TutorialChapterScene(Scene):
    """Lesson list for one chapter."""

    ROW_HEIGHT = 84
    ROW_GAP = 12

    def __init__(self, app, chapter_id: str) -> None:
        super().__init__(app)
        self.chapter_id = chapter_id
        self.chapter: Optional[TutorialChapter] = None
        self.back_button = make_back_button()
        self.modal: Optional[ui.Modal] = None
        self.hover_index: Optional[int] = None
        self.start_button = ui.Button(
            pygame.Rect(96, 594, 360, 54), "继续学习", "continue", style="primary", font_size=theme.FONT_H3
        )
        self.skip_button = ui.Button(pygame.Rect(96, 662, 174, 46), "跳过本章", "skip", style="ghost")
        self.reset_button = ui.Button(pygame.Rect(282, 662, 174, 46), "重置本章", "reset", style="ghost")
        self.lesson_buttons: List[ui.Button] = []

    def on_enter(self) -> None:
        if self.app.catalog is None:
            self.app.open_scene("tutorial")
            return
        self.chapter = self.app.catalog.require(self.chapter_id)
        self.lesson_buttons = []
        start_y = 168
        for index, lesson in enumerate(self.chapter.lessons):
            row_y = start_y + index * (self.ROW_HEIGHT + self.ROW_GAP)
            self.lesson_buttons.append(
                ui.Button(
                    pygame.Rect(1024, row_y + 20, 156, 44),
                    "开始",
                    f"lesson:{index}",
                    style="ghost",
                    font_size=theme.FONT_SMALL,
                )
            )

    # ------------------------------------------------------------------
    def _lesson_row_rect(self, index: int) -> pygame.Rect:
        start_y = 168
        return pygame.Rect(486, start_y + index * (self.ROW_HEIGHT + self.ROW_GAP), 714, self.ROW_HEIGHT)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.modal is not None:
            action = self.modal.handle_event(event)
            if action:
                self._modal_action(action)
            return
        if self.back_button.handle_event(event):
            self.app.open_scene("tutorial")
            return
        for button in (self.start_button, self.skip_button, self.reset_button):
            action = button.handle_event(event)
            if action:
                self._action(action)
                return
        for button in self.lesson_buttons:
            action = button.handle_event(event)
            if action:
                self._action(action)
                return
        if event.type == pygame.MOUSEMOTION:
            self.hover_index = None
            for index in range(len(self.chapter.lessons) if self.chapter else 0):
                if self._lesson_row_rect(index).collidepoint(event.pos):
                    self.hover_index = index
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.hover_index is not None:
                self._start_lesson(self.hover_index)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.open_scene("tutorial")

    def _action(self, action: str) -> None:
        self.app.sound.play("click")
        if action == "continue":
            lesson = self.app.book.next_lesson(self.chapter_id) if self.app.book else None
            if lesson is not None:
                self.app.start_tutorial_lesson(self.chapter_id, lesson.tutorial_id or lesson.level_id)
            else:
                self.app.open_scene("tutorial")
        elif action == "skip":
            self._ask_skip()
        elif action == "reset":
            self._ask_reset()
        elif action.startswith("lesson:"):
            self._start_lesson(int(action.split(":")[1]))

    def _start_lesson(self, index: int) -> None:
        if self.chapter is None or self.app.book is None:
            return
        if index >= len(self.chapter.lessons):
            return
        lesson = self.chapter.lessons[index]
        status = self.app.book.lesson_status(self.chapter_id, lesson.level_id)
        if not status.unlocked:
            self.app.sound.play("error")
            return
        self.app.sound.play("click")
        if lesson.extra.get("editor_task"):
            self.app.start_editor_tutorial(self.chapter_id, lesson)
            return
        self.app.start_tutorial_lesson(self.chapter_id, lesson.tutorial_id or lesson.level_id)

    def _ask_skip(self) -> None:
        self.modal = ui.Modal(
            "跳过本章？",
            "本章所有未完成的课程会标记为已跳过。\n教程进度与主线进度分开保存，主线不会受到影响。",
            accent=theme.SKY_DEEP,
            badge="教程",
            buttons=[
                ui.Button(pygame.Rect(0, 0, 150, 50), "再想想", "cancel", style="ghost"),
                ui.Button(pygame.Rect(0, 0, 160, 50), "跳过本章", "confirm_skip", style="primary"),
            ],
            width=620,
            height=330,
        )

    def _ask_reset(self) -> None:
        self.modal = ui.Modal(
            "重置本章进度？",
            "本章的完成与跳过记录会清空，可以重新体验每一节课。",
            accent=theme.CLAY,
            buttons=[
                ui.Button(pygame.Rect(0, 0, 150, 50), "取消", "cancel", style="ghost"),
                ui.Button(pygame.Rect(0, 0, 160, 50), "确认重置", "confirm_reset", style="danger"),
            ],
            width=600,
            height=310,
        )

    def _modal_action(self, action: str) -> None:
        self.modal = None
        if self.app.book is None:
            return
        if action == "confirm_skip":
            self.app.book.skip_chapter(self.chapter_id)
            self.app.sound.play("unlock")
            self.on_enter()
        elif action == "confirm_reset":
            self.app.book.reset_chapter(self.chapter_id)
            self.app.sound.play("unlock")
            self.on_enter()

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        super().update(dt)
        if self.modal is not None:
            self.modal.update(pygame.mouse.get_pos())

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        if self.chapter is None:
            self.back_button.draw(surface, self.fonts)
            return
        progress = self.app.book.chapter_progress(self.chapter_id) if self.app.book else None
        draw_header(
            surface,
            self.fonts,
            self.chapter.title,
            f"{progress.done} / {progress.total} 节课" if progress else "",
            badge="教程",
            badge_color=ACCENTS.get(self.chapter.accent, theme.LEAF),
        )
        self.back_button.draw(surface, self.fonts)

        # chapter intro panel
        intro_panel = pygame.Rect(80, 150, 380, 570)
        theme.panel(surface, intro_panel)
        theme.draw_text(
            surface,
            self.fonts,
            self.chapter.subtitle,
            (intro_panel.left + 26, intro_panel.top + 26),
            theme.FONT_H2,
            theme.INK,
            bold=True,
        )
        body = self.fonts.wrap(self.chapter.intro, theme.FONT_SMALL, intro_panel.width - 52, theme.INK_SOFT)
        surface.blit(body, (intro_panel.left + 26, intro_panel.top + 76))
        if progress is not None:
            bar = pygame.Rect(intro_panel.left + 26, intro_panel.top + 200, intro_panel.width - 52, 14)
            theme.rounded_rect(surface, bar, theme.CREAM_DARK, radius=7)
            filled = pygame.Rect(bar.left, bar.top, int(bar.width * progress.percent), bar.height)
            theme.rounded_rect(surface, filled, theme.LEAF, radius=7)
            theme.draw_text(
                surface,
                self.fonts,
                f"已完成 {progress.completed} 节 · 跳过 {progress.skipped} 节",
                (intro_panel.left + 26, intro_panel.top + 226),
                theme.FONT_SMALL,
                theme.INK_SOFT,
            )
        tips = [
            "每节课只介绍一个新机制。",
            "可以随时跳过单节课或整个章节。",
            "教程不会获得 S/A/B/C 评价。",
        ]
        y = intro_panel.top + 282
        for tip in tips:
            pygame.draw.circle(surface, theme.LEAF, (intro_panel.left + 34, y + 10), 4)
            wrapped = self.fonts.wrap(tip, theme.FONT_SMALL, intro_panel.width - 80, theme.INK_SOFT)
            surface.blit(wrapped, (intro_panel.left + 48, y))
            y += wrapped.get_height() + 14

        self.start_button.draw(surface, self.fonts)
        self.skip_button.draw(surface, self.fonts)
        self.reset_button.draw(surface, self.fonts)

        # lesson rows
        for index, lesson in enumerate(self.chapter.lessons):
            self._draw_lesson_row(surface, index, lesson)

        draw_footer(surface, self.fonts, "教程进度单独保存 · Esc 返回章节选择")
        if self.modal is not None:
            self.modal.draw(surface, self.fonts)

    def _draw_lesson_row(self, surface: pygame.Surface, index: int, lesson: Level) -> None:
        if self.app.book is None:
            return
        status = self.app.book.lesson_status(self.chapter_id, lesson.level_id)
        rect = self._lesson_row_rect(index)
        hovered = self.hover_index == index and status.unlocked
        theme.soft_shadow(surface, rect, radius=16, alpha=36 if hovered else 22, offset=(0, 5))
        background = theme.PANEL_BG if status.unlocked else theme.CREAM_DARK
        theme.rounded_rect(surface, rect, background, radius=16)
        border = theme.SUN_LIGHT if hovered else theme.PANEL_BORDER
        theme.rounded_rect(surface, rect, border, radius=16, width=3 if hovered else 2)

        badge_color = {
            TUTORIAL_COMPLETED: theme.PRIMARY_BG,
            TUTORIAL_SKIPPED: theme.INK_LIGHT,
            TUTORIAL_IN_PROGRESS: theme.SKY_DEEP,
        }.get(status.state, theme.CREAM_DARK)
        circle_center = (rect.left + 42, rect.centery)
        pygame.draw.circle(surface, badge_color, circle_center, 20)
        number_color = theme.WHITE_WARM if status.unlocked else theme.INK_LIGHT
        number = self.fonts.render(str(index + 1), theme.FONT_BODY, number_color, True)
        surface.blit(number, number.get_rect(center=circle_center))

        title_color = theme.INK if status.unlocked else theme.INK_LIGHT
        theme.draw_text(
            surface, self.fonts, lesson.name, (rect.left + 78, rect.top + 16), theme.FONT_H3, title_color, bold=True
        )
        brief = lesson.description or lesson.hint
        brief = self.fonts.ellipsize(brief, theme.FONT_SMALL, 460)
        theme.draw_text(
            surface,
            self.fonts,
            brief,
            (rect.left + 78, rect.top + 52),
            theme.FONT_SMALL,
            theme.INK_SOFT if status.unlocked else theme.INK_LIGHT,
        )
        ui.draw_pill(
            surface,
            self.fonts,
            STATE_LABELS.get(status.state, "未开始"),
            (rect.right - 250, rect.centery),
            badge_color,
            text_color=theme.WHITE_WARM,
        )
        button = self.lesson_buttons[index] if index < len(self.lesson_buttons) else None
        if button is not None:
            label = "开始" if status.state == TUTORIAL_NOT_STARTED else ("重玩" if status.unlocked else "未解锁")
            if status.state == TUTORIAL_IN_PROGRESS:
                label = "继续"
            if not status.unlocked:
                label = "未解锁"
            button.text = label
            button.enabled = status.unlocked and not lesson.extra.get("editor_task")
            button.draw(surface, self.fonts)
            if lesson.extra.get("editor_task"):
                theme.draw_text(
                    surface,
                    self.fonts,
                    "在编辑器中开学",
                    (button.rect.centerx, button.rect.bottom + 2),
                    theme.FONT_TINY,
                    theme.INK_LIGHT,
                    anchor="midtop",
                )
