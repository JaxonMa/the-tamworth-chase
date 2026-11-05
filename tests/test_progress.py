"""Tests for the local save store and the campaign/tutorial separation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.models import Rank
from game.progress import (
    TUTORIAL_COMPLETED,
    TUTORIAL_IN_PROGRESS,
    TUTORIAL_NOT_STARTED,
    TUTORIAL_SKIPPED,
    ProgressStore,
)


@pytest.fixture()
def store(tmp_path: Path) -> ProgressStore:
    return ProgressStore(tmp_path / "save.json").load()


def test_defaults(store):
    assert store.get_setting("speed") == 1.0
    assert store.get_setting("sound") is True
    assert store.main_levels == {}
    assert store.lesson_state("basics", "b1") == TUTORIAL_NOT_STARTED


def test_save_and_reload(tmp_path: Path):
    path = tmp_path / "save.json"
    first = ProgressStore(path).load()
    first.set_setting("speed", 2.0)
    first.record_main_clear("level_01", 9, Rank.A, 1)
    assert path.exists()

    second = ProgressStore(path).load()
    assert second.get_setting("speed") == 2.0
    assert second.main_result("level_01").cleared is True
    assert second.main_result("level_01").best_steps == 9
    assert second.main_result("level_01").rank is Rank.A


def test_best_steps_keep_minimum(store):
    store.record_main_clear("level_01", 12, Rank.B, 2)
    store.record_main_clear("level_01", 8, Rank.S, 1)
    store.record_main_clear("level_01", 15, Rank.C, 2)
    result = store.main_result("level_01")
    assert result.best_steps == 8
    assert result.rank is Rank.S


def test_attempts_are_counted(store):
    store.record_main_attempt("level_01")
    store.record_main_clear("level_01", 10, Rank.A, 0)
    assert store.main_levels["level_01"]["attempts"] == 2


def test_unlock_progression(store):
    ids = ["a", "b", "c"]
    assert store.main_unlocked_count(ids) == 1
    assert store.is_main_unlocked(ids, "a") is True
    assert store.is_main_unlocked(ids, "b") is False

    store.record_main_clear("a", 10, Rank.A, 1)
    assert store.main_unlocked_count(ids) == 2
    assert store.is_main_unlocked(ids, "b") is True
    assert store.is_main_unlocked(ids, "c") is False

    store.record_main_clear("b", 10, Rank.A, 1)
    assert store.main_unlocked_count(ids) == 3
    assert store.is_main_unlocked(ids, "c") is True


def test_tutorial_completion_does_not_unlock_campaign(store):
    ids = ["a", "b"]
    store.set_lesson_state("basics", "b1", TUTORIAL_COMPLETED)
    store.set_lesson_state("basics", "b2", TUTORIAL_COMPLETED)
    assert store.main_unlocked_count(ids) == 1
    assert store.is_main_unlocked(ids, "b") is False


def test_campaign_completion_does_not_touch_tutorial(store):
    store.record_main_clear("a", 10, Rank.S, 1)
    assert store.lesson_state("basics", "b1") == TUTORIAL_NOT_STARTED
    assert store.chapter_summary("basics", ["b1", "b2"]) == (0, 2)


def test_tutorial_states(store):
    store.set_lesson_state("basics", "b1", TUTORIAL_IN_PROGRESS, count_attempt=True)
    assert store.lesson_state("basics", "b1") == TUTORIAL_IN_PROGRESS
    assert store.lesson_attempts("basics", "b1") == 1
    store.set_lesson_state("basics", "b1", TUTORIAL_COMPLETED)
    assert store.lesson_state("basics", "b1") == TUTORIAL_COMPLETED
    store.skip_lesson("basics", "b2")
    assert store.lesson_state("basics", "b2") == TUTORIAL_SKIPPED
    assert store.chapter_summary("basics", ["b1", "b2"]) == (2, 2)


def test_skip_chapter(store):
    store.set_lesson_state("basics", "b1", TUTORIAL_COMPLETED)
    store.skip_chapter("basics", ["b1", "b2"])
    assert store.chapter_skipped("basics") is True
    assert store.lesson_state("basics", "b1") == TUTORIAL_COMPLETED
    assert store.lesson_state("basics", "b2") == TUTORIAL_SKIPPED


def test_reset_tutorial_keeps_campaign(store):
    store.record_main_clear("level_01", 8, Rank.S, 1)
    store.set_lesson_state("basics", "b1", TUTORIAL_COMPLETED)
    store.reset_tutorial()
    assert store.lesson_state("basics", "b1") == TUTORIAL_NOT_STARTED
    assert store.main_result("level_01").cleared is True


def test_reset_main_keeps_tutorial(store):
    store.record_main_clear("level_01", 8, Rank.S, 1)
    store.set_lesson_state("basics", "b1", TUTORIAL_COMPLETED)
    store.reset_main()
    assert store.main_result("level_01").cleared is False
    assert store.lesson_state("basics", "b1") == TUTORIAL_COMPLETED


def test_corrupt_save_falls_back(tmp_path: Path):
    path = tmp_path / "save.json"
    path.write_text("{not json", encoding="utf-8")
    store = ProgressStore(path).load()
    assert store.load_error
    assert store.main_levels == {}
    store.set_setting("speed", 2.0)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["settings"]["speed"] == 2.0


def test_achievements_and_daily(store):
    assert store.unlock_achievement("first_catch") is True
    assert store.unlock_achievement("first_catch") is False
    assert store.has_achievement("first_catch") is True
    assert store.record_daily("2026-01-01", {"cleared": True, "steps": 12}) is True
    assert store.daily_result("2026-01-01")["steps"] == 12


def test_challenge_best(store):
    assert store.challenge_best("level_01/min") is None
    assert store.record_challenge_best("level_01/min", 14) is True
    assert store.record_challenge_best("level_01/min", 20) is False
    assert store.challenge_best("level_01/min") == 14
