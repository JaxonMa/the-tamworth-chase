"""Independent tutorial chapter system.

The tutorial is intentionally modelled separately from the campaign:

* It has its own data files (``tutorials/*.json``) and its own catalogue.
* It has its own save section, its own state machine
  (``not_started`` / ``in_progress`` / ``completed`` / ``skipped``).
* It never influences campaign unlocking.

Each chapter is an independent entry point; lessons inside a chapter unlock in
order, but skipping a lesson or a whole chapter only affects that chapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from .levels import TUTORIAL_FILES, LevelError, parse_level
from .models import Level, Tip
from .paths import project_root
from .progress import (
    TUTORIAL_COMPLETED,
    TUTORIAL_IN_PROGRESS,
    TUTORIAL_NOT_STARTED,
    TUTORIAL_SKIPPED,
    ProgressStore,
)

CHAPTER_ORDER = ("basics", "advanced", "editor")


@dataclass(frozen=True)
class TutorialChapter:
    chapter_id: str
    title: str
    subtitle: str
    intro: str
    badge: str
    accent: str
    lessons: Tuple[Level, ...]
    file_name: str = ""

    @property
    def lesson_ids(self) -> Tuple[str, ...]:
        return tuple(lesson.level_id for lesson in self.lessons)

    def lesson(self, lesson_id: str) -> Optional[Level]:
        for lesson in self.lessons:
            if lesson.level_id == lesson_id:
                return lesson
        return None

    def index_of(self, lesson_id: str) -> int:
        for index, lesson in enumerate(self.lessons):
            if lesson.level_id == lesson_id:
                return index
        return -1


@dataclass(frozen=True)
class ChapterProgress:
    chapter_id: str
    completed: int
    total: int
    skipped: int

    @property
    def done(self) -> int:
        return self.completed + self.skipped

    @property
    def finished(self) -> bool:
        return self.total > 0 and self.done >= self.total

    @property
    def percent(self) -> float:
        return self.done / self.total if self.total else 0.0


@dataclass(frozen=True)
class LessonStatus:
    lesson_id: str
    state: str
    unlocked: bool
    completed: bool
    skipped: bool

    @property
    def replayable(self) -> bool:
        return self.completed or self.skipped


class TutorialCatalog:
    """Loads every tutorial chapter from the ``tutorials`` directory."""

    def __init__(self, chapters: Mapping[str, TutorialChapter]) -> None:
        self._chapters: Dict[str, TutorialChapter] = dict(chapters)

    @classmethod
    def load(cls, root: Optional[Path] = None) -> "TutorialCatalog":
        base = Path(root) if root else project_root()
        chapters: Dict[str, TutorialChapter] = {}
        for chapter_id, relative in TUTORIAL_FILES.items():
            path = base / relative
            if not path.exists():
                continue
            chapters[chapter_id] = _load_chapter(chapter_id, path)
        if not chapters:
            raise LevelError("没有找到任何教程数据文件")
        return cls(chapters)

    def get(self, chapter_id: str) -> Optional[TutorialChapter]:
        return self._chapters.get(chapter_id)

    def require(self, chapter_id: str) -> TutorialChapter:
        chapter = self._chapters.get(chapter_id)
        if chapter is None:
            raise KeyError(f"unknown tutorial chapter: {chapter_id}")
        return chapter

    def all(self) -> Tuple[TutorialChapter, ...]:
        ordered = [self._chapters[cid] for cid in CHAPTER_ORDER if cid in self._chapters]
        extras = [c for cid, c in self._chapters.items() if cid not in CHAPTER_ORDER]
        return tuple(ordered) + tuple(sorted(extras, key=lambda c: c.chapter_id))

    def chapter_ids(self) -> Tuple[str, ...]:
        return tuple(chapter.chapter_id for chapter in self.all())

    def find_lesson(self, chapter_id: str, lesson_id: str) -> Optional[Level]:
        chapter = self._chapters.get(chapter_id)
        return chapter.lesson(lesson_id) if chapter else None

    def __len__(self) -> int:
        return len(self._chapters)


def _load_chapter(chapter_id: str, path: Path) -> TutorialChapter:
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LevelError(f"教程文件 {path.name} 不是合法的 JSON：{exc.msg}") from exc

    lessons: List[Level] = []
    for index, item in enumerate(raw.get("lessons") or []):
        level_data = dict(item.get("level") or {})
        level_data.setdefault("id", item.get("id") or f"{chapter_id}_{index + 1}")
        level_data.setdefault("name", item.get("name") or level_data["id"])
        level_data.setdefault("description", item.get("brief") or "")
        level_data.setdefault("goal", item.get("goal") or "")
        level_data.setdefault("practice", item.get("practice") or "")
        level_data.setdefault("tips", item.get("tips") or [])
        if item.get("editor_task"):
            level_data["editor_task"] = item["editor_task"]
        if item.get("starter_grid"):
            level_data["starter_grid"] = item["starter_grid"]
        lesson = parse_level(
            level_data,
            source="tutorial",
            group=chapter_id,
            order=index,
            tutorial_id=str(item.get("id") or level_data["id"]),
        )
        lessons.append(lesson)

    return TutorialChapter(
        chapter_id=chapter_id,
        title=str(raw.get("title") or chapter_id),
        subtitle=str(raw.get("subtitle") or ""),
        intro=str(raw.get("intro") or ""),
        badge=str(raw.get("badge") or "教程"),
        accent=str(raw.get("accent") or "leaf"),
        lessons=tuple(lessons),
        file_name=path.name,
    )


class TutorialBook:
    """Tutorial state machine bound to a :class:`ProgressStore`.

    Every mutation goes through the ``tutorial`` section of the save file; the
    campaign section is never touched.
    """

    def __init__(self, store: ProgressStore, catalog: TutorialCatalog) -> None:
        self.store = store
        self.catalog = catalog

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def chapter_progress(self, chapter_id: str) -> ChapterProgress:
        chapter = self.catalog.require(chapter_id)
        completed = 0
        skipped = 0
        for lesson_id in chapter.lesson_ids:
            state = self.store.lesson_state(chapter_id, lesson_id)
            if state == TUTORIAL_COMPLETED:
                completed += 1
            elif state == TUTORIAL_SKIPPED:
                skipped += 1
        return ChapterProgress(chapter_id, completed, len(chapter.lessons), skipped)

    def lesson_status(self, chapter_id: str, lesson_id: str) -> LessonStatus:
        chapter = self.catalog.require(chapter_id)
        index = chapter.index_of(lesson_id)
        state = self.store.lesson_state(chapter_id, lesson_id)
        unlocked = index == 0
        if index > 0:
            previous_id = chapter.lesson_ids[index - 1]
            unlocked = self.store.lesson_state(chapter_id, previous_id) in (
                TUTORIAL_COMPLETED,
                TUTORIAL_SKIPPED,
            )
        # A chapter that was skipped wholesale enables every lesson for replay.
        if self.store.chapter_skipped(chapter_id):
            unlocked = True
        return LessonStatus(
            lesson_id=lesson_id,
            state=state,
            unlocked=unlocked,
            completed=state == TUTORIAL_COMPLETED,
            skipped=state == TUTORIAL_SKIPPED,
        )

    def next_lesson(self, chapter_id: str) -> Optional[Level]:
        chapter = self.catalog.require(chapter_id)
        for lesson in chapter.lessons:
            status = self.lesson_status(chapter_id, lesson.level_id)
            if status.unlocked and status.state in (TUTORIAL_NOT_STARTED, TUTORIAL_IN_PROGRESS):
                return lesson
        return None

    def chapter_state(self, chapter_id: str) -> str:
        progress = self.chapter_progress(chapter_id)
        if progress.total == 0:
            return TUTORIAL_NOT_STARTED
        if progress.finished:
            if progress.completed == 0:
                return TUTORIAL_SKIPPED
            return TUTORIAL_COMPLETED
        if progress.done > 0:
            return TUTORIAL_IN_PROGRESS
        return TUTORIAL_NOT_STARTED

    def any_progress(self) -> bool:
        for chapter in self.catalog.all():
            if self.chapter_progress(chapter.chapter_id).done:
                return True
        return False

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------
    def begin_lesson(self, chapter_id: str, lesson_id: str) -> None:
        state = self.store.lesson_state(chapter_id, lesson_id)
        if state in (TUTORIAL_COMPLETED, TUTORIAL_SKIPPED):
            return
        self.store.set_lesson_state(chapter_id, lesson_id, TUTORIAL_IN_PROGRESS, count_attempt=True)

    def complete_lesson(self, chapter_id: str, lesson_id: str) -> bool:
        state = self.store.lesson_state(chapter_id, lesson_id)
        if state == TUTORIAL_COMPLETED:
            return False
        self.store.set_lesson_state(chapter_id, lesson_id, TUTORIAL_COMPLETED, count_attempt=True)
        return True

    def skip_lesson(self, chapter_id: str, lesson_id: str) -> None:
        self.store.skip_lesson(chapter_id, lesson_id)

    def skip_chapter(self, chapter_id: str) -> None:
        chapter = self.catalog.require(chapter_id)
        self.store.skip_chapter(chapter_id, chapter.lesson_ids)

    def reset_chapter(self, chapter_id: str) -> None:
        self.store.reset_chapter(chapter_id)

    def reset_all(self) -> None:
        self.store.reset_tutorial()


class TutorialSession:
    """Per-lesson hint state machine.

    Tips are declared in lesson order and each one is bound to a gameplay
    trigger.  Only the tip that matches the current step can fire, which keeps
    the guidance readable instead of showing a wall of text.
    """

    def __init__(self, level: Level) -> None:
        self.level = level
        self.tips: Tuple[Tip, ...] = level.tips
        self.index = 0
        self.active: Optional[str] = None
        self.history: List[str] = []
        self.fired_events: List[str] = []
        self.completed = False
        self.skipped = False

    @property
    def has_tips(self) -> bool:
        return bool(self.tips)

    @property
    def current_trigger(self) -> Optional[str]:
        if self.index < len(self.tips):
            return self.tips[self.index].trigger
        return None

    def start(self) -> Optional[str]:
        """Fire the opening tip (if any) and return the visible text."""
        self._fire_all_matching("start")
        return self.active

    def notify(self, event: str) -> Optional[str]:
        """Inform the session that ``event`` happened.

        Returns the newly displayed tip text, or ``None`` when nothing changed.
        """
        self.fired_events.append(event)
        new_text = self._fire_all_matching(event)
        if event == "win":
            self.completed = True
        return new_text

    def _fire_all_matching(self, event: str) -> Optional[str]:
        changed = None
        while self.index < len(self.tips) and self.tips[self.index].trigger == event:
            tip = self.tips[self.index]
            self.active = tip.text
            self.history.append(tip.text)
            self.index += 1
            changed = tip.text
            # A tip may also be informational: stop after showing one per event.
            break
        return changed

    def skip(self) -> None:
        self.skipped = True

    @property
    def progress_ratio(self) -> float:
        if not self.tips:
            return 1.0
        return min(1.0, self.index / len(self.tips))
