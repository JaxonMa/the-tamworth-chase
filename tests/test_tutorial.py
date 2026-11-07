"""Tutorial catalogue, state machine, isolation and hint tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.core import Simulation
from game.levels import load_levels
from game.models import Action, GameStatus, Rank
from game.progress import (
    TUTORIAL_COMPLETED,
    TUTORIAL_IN_PROGRESS,
    TUTORIAL_NOT_STARTED,
    TUTORIAL_SKIPPED,
    ProgressStore,
)
from game.tutorial import TutorialBook, TutorialCatalog, TutorialSession

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = json.loads((ROOT / "tests" / "tutorial_solutions.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog() -> TutorialCatalog:
    return TutorialCatalog.load()


@pytest.fixture()
def store(tmp_path: Path) -> ProgressStore:
    return ProgressStore(tmp_path / "save.json").load()


@pytest.fixture()
def book(store: ProgressStore, catalog: TutorialCatalog) -> TutorialBook:
    return TutorialBook(store, catalog)


def test_chapter_counts(catalog):
    counts = {chapter.chapter_id: len(chapter.lessons) for chapter in catalog.all()}
    assert counts == {"basics": 7, "advanced": 3, "editor": 3}


def test_tutorial_lessons_are_not_campaign_levels(catalog):
    campaign_ids = {level.level_id for level in load_levels()}
    for chapter in catalog.all():
        for lesson in chapter.lessons:
            assert lesson.level_id not in campaign_ids
            assert lesson.source == "tutorial"


def test_every_playable_lesson_has_exit_and_unified_cows(catalog):
    for chapter in catalog.all():
        for lesson in chapter.lessons:
            assert lesson.exit_cells
            assert lesson.max_turns >= 5
            assert lesson.cow_positions
            assert not hasattr(lesson, "cow_behaviors")


def test_lesson_solutions_win(catalog):
    for chapter in catalog.all():
        if chapter.chapter_id == "editor":
            continue
        for lesson in chapter.lessons:
            solution = SOLUTIONS[chapter.chapter_id].get(lesson.level_id)
            if solution is None or solution.get("status") != "won":
                continue
            sim = Simulation(lesson)
            for action in solution["actions"]:
                sim.apply_action(Action(action))
            assert sim.status is GameStatus.WON, lesson.level_id
            assert sim.turns <= lesson.max_turns


def test_practice_metadata_is_present(catalog):
    by_id = {lesson.level_id: lesson for chapter in catalog.all() for lesson in chapter.lessons}
    assert by_id["basics_01"].extra.get("require_invalid") is True
    assert by_id["basics_01"].extra.get("require_forward") is True
    assert by_id["basics_02"].extra.get("require_block") is True
    assert by_id["basics_03"].extra.get("require_actions") == 3
    assert by_id["basics_07"].extra.get("require_undo") is True
    assert by_id["basics_07"].extra.get("require_prediction") is True
    assert by_id["basics_07"].prediction_steps == 6
    assert all("require_wait" not in lesson.extra for lesson in by_id.values())


def test_advanced_lessons_cover_multi_cow_pressure(catalog):
    advanced = catalog.get("advanced")
    assert advanced is not None
    assert len(advanced.lessons) == 3
    assert advanced.lessons[0].exit_cells
    assert any(len(lesson.cow_positions) > 1 for lesson in advanced.lessons)
    assert len(advanced.lessons[2].cow_positions) >= 2
    assert all(not hasattr(lesson, "cow_behaviors") for lesson in advanced.lessons)


def test_editor_tasks(catalog):
    editor = catalog.get("editor")
    assert editor is not None
    types = {lesson.extra.get("editor_task", {}).get("type") for lesson in editor.lessons}
    assert {"paint_wall", "set_exits", "export_import"} <= types
    exits_task = next(
        lesson.extra["editor_task"] for lesson in editor.lessons
        if lesson.extra.get("editor_task", {}).get("type") == "set_exits"
    )
    assert exits_task.get("block_sight") is True


def test_initial_states(book, catalog):
    chapter = catalog.all()[0]
    assert book.lesson_status(chapter.chapter_id, chapter.lesson_ids[0]).state == TUTORIAL_NOT_STARTED
    assert book.chapter_state(chapter.chapter_id) == TUTORIAL_NOT_STARTED


def test_first_lesson_unlocked_rest_locked(book, catalog):
    chapter = catalog.get("basics")
    statuses = [book.lesson_status("basics", lesson_id) for lesson_id in chapter.lesson_ids]
    assert statuses[0].unlocked is True
    assert all(not status.unlocked for status in statuses[1:])


def test_completing_lesson_unlocks_next(book, catalog):
    chapter = catalog.get("basics")
    book.begin_lesson("basics", chapter.lesson_ids[0])
    assert book.lesson_status("basics", chapter.lesson_ids[0]).state == TUTORIAL_IN_PROGRESS
    assert book.complete_lesson("basics", chapter.lesson_ids[0]) is True
    assert book.lesson_status("basics", chapter.lesson_ids[0]).state == TUTORIAL_COMPLETED
    assert book.lesson_status("basics", chapter.lesson_ids[1]).unlocked is True
    assert book.chapter_state("basics") == TUTORIAL_IN_PROGRESS


def test_complete_is_idempotent(book, catalog):
    first = catalog.get("basics").lesson_ids[0]
    assert book.complete_lesson("basics", first) is True
    assert book.complete_lesson("basics", first) is False
    assert book.store.lesson_attempts("basics", first) == 1


def test_skip_lesson_unlocks_next(book, catalog):
    first, second = catalog.get("basics").lesson_ids[:2]
    book.skip_lesson("basics", first)
    assert book.lesson_status("basics", first).state == TUTORIAL_SKIPPED
    assert book.lesson_status("basics", second).unlocked is True
    assert book.complete_lesson("basics", second) is True


def test_skip_chapter_marks_everything_and_opens_replay(book, catalog):
    chapter = catalog.get("basics")
    book.skip_chapter("basics")
    for lesson_id in chapter.lesson_ids:
        assert book.store.lesson_state("basics", lesson_id) == TUTORIAL_SKIPPED
        assert book.lesson_status("basics", lesson_id).unlocked is True
    assert book.chapter_state("basics") == TUTORIAL_SKIPPED


def test_reset_chapter(book, catalog):
    chapter = catalog.get("basics")
    book.complete_lesson("basics", chapter.lesson_ids[0])
    book.skip_chapter("basics")
    book.reset_chapter("basics")
    assert book.lesson_status("basics", chapter.lesson_ids[0]).state == TUTORIAL_NOT_STARTED
    assert book.lesson_status("basics", chapter.lesson_ids[1]).unlocked is False


def test_next_lesson_follows_unlock_order(book, catalog):
    chapter = catalog.get("basics")
    next_lesson = book.next_lesson("basics")
    assert next_lesson is not None and next_lesson.level_id == chapter.lesson_ids[0]
    book.complete_lesson("basics", chapter.lesson_ids[0])
    next_lesson = book.next_lesson("basics")
    assert next_lesson is not None and next_lesson.level_id == chapter.lesson_ids[1]


def test_replaying_completed_lesson_keeps_completion(book, catalog):
    lesson_id = catalog.get("basics").lesson_ids[0]
    book.complete_lesson("basics", lesson_id)
    book.begin_lesson("basics", lesson_id)
    assert book.lesson_status("basics", lesson_id).state == TUTORIAL_COMPLETED
    assert book.lesson_status("basics", lesson_id).replayable is True


def test_tutorial_progress_does_not_unlock_campaign(book, store, catalog):
    level_ids = [level.level_id for level in load_levels()]
    assert store.main_unlocked_count(level_ids) == 1
    for lesson_id in catalog.get("basics").lesson_ids:
        book.complete_lesson("basics", lesson_id)
    assert store.main_unlocked_count(level_ids) == 1
    assert store.main_result(level_ids[0]).cleared is False


def test_campaign_progress_does_not_touch_tutorial(book, store, catalog):
    level_ids = [level.level_id for level in load_levels()]
    store.record_main_clear(level_ids[0], 8, Rank.S)
    assert book.lesson_status("basics", catalog.get("basics").lesson_ids[0]).state == TUTORIAL_NOT_STARTED


def test_tutorial_settings_reset_leaves_campaign(book, store):
    level_ids = [level.level_id for level in load_levels()]
    store.record_main_clear(level_ids[0], 8, Rank.A)
    book.complete_lesson("basics", "basics_01")
    book.reset_all()
    assert store.main_result(level_ids[0]).cleared is True
    assert store.lesson_state("basics", "basics_01") == TUTORIAL_NOT_STARTED


def test_campaign_reset_leaves_tutorial(book, store):
    book.complete_lesson("basics", "basics_01")
    store.reset_main()
    assert store.lesson_state("basics", "basics_01") == TUTORIAL_COMPLETED


def test_hint_session_tolerates_action_order(catalog):
    lesson = catalog.find_lesson("basics", "basics_02")
    session = TutorialSession(lesson)
    assert session.start() is not None
    assert session.notify("win") is not None
    assert session.completed is True


def test_hint_session_skip(catalog):
    lesson = catalog.find_lesson("basics", "basics_01")
    session = TutorialSession(lesson)
    session.start()
    session.skip()
    assert session.skipped is True


def test_every_lesson_has_tips_and_chinese_name(catalog):
    for chapter in catalog.all():
        for lesson in chapter.lessons:
            assert lesson.tips, f"{lesson.level_id} needs guidance tips"
            assert lesson.goal_text or lesson.description
            assert any("\u4e00" <= ch <= "\u9fff" for ch in lesson.name)
