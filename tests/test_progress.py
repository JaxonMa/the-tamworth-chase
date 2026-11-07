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
    assert store.get_setting("sound") is True
    assert store.get_setting("preview") is True
    assert store.get_setting("alerts") is True
    assert store.main_levels == {}
    assert store.lesson_state("basics", "b1") == TUTORIAL_NOT_STARTED


def test_save_and_reload(tmp_path: Path):
    path = tmp_path / "save.json"
    first = ProgressStore(path).load()
    first.set_setting("volume", 0.9)
    first.record_main_clear("level_01", 9, Rank.A)
    assert path.exists()

    second = ProgressStore(path).load()
    assert second.get_setting("volume") == 0.9
    assert second.main_result("level_01").cleared is True
    assert second.main_result("level_01").best_turns == 9
    assert second.main_result("level_01").rank is Rank.A


def test_best_turns_keep_minimum(store):
    store.record_main_clear("level_01", 12, Rank.B)
    store.record_main_clear("level_01", 8, Rank.S)
    store.record_main_clear("level_01", 15, Rank.C)
    result = store.main_result("level_01")
    assert result.best_turns == 8
    assert result.rank is Rank.S


def test_attempts_are_counted(store):
    store.record_main_attempt("level_01")
    store.record_main_clear("level_01", 10, Rank.A)
    assert store.main_levels["level_01"]["attempts"] == 2


def test_unlock_progression(store):
    ids = ["a", "b", "c"]
    assert store.main_unlocked_count(ids) == 1
    assert store.is_main_unlocked(ids, "a") is True
    assert store.is_main_unlocked(ids, "b") is False

    store.record_main_clear("a", 10, Rank.A)
    assert store.main_unlocked_count(ids) == 2
    assert store.is_main_unlocked(ids, "b") is True
    assert store.is_main_unlocked(ids, "c") is False

    store.record_main_clear("b", 10, Rank.A)
    assert store.main_unlocked_count(ids) == 3
    assert store.is_main_unlocked(ids, "c") is True


def test_tutorial_completion_does_not_unlock_campaign(store):
    ids = ["a", "b"]
    store.set_lesson_state("basics", "b1", TUTORIAL_COMPLETED)
    store.set_lesson_state("basics", "b2", TUTORIAL_COMPLETED)
    assert store.main_unlocked_count(ids) == 1
    assert store.is_main_unlocked(ids, "b") is False


def test_campaign_completion_does_not_touch_tutorial(store):
    store.record_main_clear("a", 10, Rank.S)
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
    store.record_main_clear("level_01", 8, Rank.S)
    store.set_lesson_state("basics", "b1", TUTORIAL_COMPLETED)
    store.reset_tutorial()
    assert store.lesson_state("basics", "b1") == TUTORIAL_NOT_STARTED
    assert store.main_result("level_01").cleared is True


def test_reset_main_keeps_tutorial(store):
    store.record_main_clear("level_01", 8, Rank.S)
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
    store.set_setting("volume", 0.9)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["settings"]["volume"] == 0.9


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


def test_legacy_save_is_migrated_once(tmp_path: Path):
    new_path = tmp_path / "new" / "save.json"
    old_path = tmp_path / "old" / "save.json"
    old_path.parent.mkdir(parents=True)
    legacy = ProgressStore(old_path).load()
    legacy.set_setting("sound", False)
    legacy.record_main_clear("level_01", 7, Rank.S)

    store = ProgressStore(new_path, legacy_path=old_path).load()
    assert store.migrated_from == str(old_path)
    assert store.notice
    assert new_path.exists()
    assert store.get_setting("sound") is False
    assert store.main_result("level_01").best_turns == 7
    assert old_path.exists(), "the old save must never be deleted"

    # A later launch reads the new file and does not migrate again.
    store.consume_notice()
    again = ProgressStore(new_path, legacy_path=old_path).load()
    assert again.migrated_from == ""
    assert again.notice == ""
    assert again.main_result("level_01").cleared is True


def test_corrupt_legacy_save_reports_instead_of_crashing(tmp_path: Path):
    new_path = tmp_path / "new" / "save.json"
    old_path = tmp_path / "old" / "save.json"
    old_path.parent.mkdir(parents=True)
    old_path.write_text("{broken", encoding="utf-8")

    store = ProgressStore(new_path, legacy_path=old_path).load()
    assert store.load_error
    assert store.notice
    assert not new_path.exists()
    assert old_path.exists()
    assert store.main_levels == {}


def test_legacy_step_records_are_migrated(tmp_path: Path):
    path = tmp_path / "save.json"
    path.write_text(
        json.dumps(
            {
                "version": 3,
                "settings": {"speed": 2.0, "volume": 0.5},
                "main": {
                    "levels": {
                        "level_01": {
                            "cleared": True,
                            "best_steps": 9,
                            "rank": "A",
                            "obstacles": 1,
                        }
                    }
                },
                "daily": {"2026-01-01": {"cleared": True, "steps": 12}},
            }
        ),
        encoding="utf-8",
    )
    store = ProgressStore(path).load()
    assert store.data["version"] == 5
    assert "speed" not in store.settings
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 5
    result = store.main_result("level_01")
    assert result.best_turns == 9
    assert result.rank is Rank.A
    assert store.daily_result("2026-01-01")["turns"] == 12
    assert "obstacles" not in store.main_levels["level_01"]
