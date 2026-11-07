"""Local save data: main campaign progress, tutorial progress and settings.

The save file is a single JSON document with clearly separated sections.  The
tutorial section is fully independent from the main campaign section: clearing
tutorial lessons never unlocks a campaign level, and campaign progress never
marks a tutorial lesson as done.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .models import LevelResult, Rank
from .paths import data_override, ensure_data_dir, legacy_save_path, save_path

SAVE_VERSION = 5

TUTORIAL_NOT_STARTED = "not_started"
TUTORIAL_IN_PROGRESS = "in_progress"
TUTORIAL_COMPLETED = "completed"
TUTORIAL_SKIPPED = "skipped"

TUTORIAL_STATES = (
    TUTORIAL_NOT_STARTED,
    TUTORIAL_IN_PROGRESS,
    TUTORIAL_COMPLETED,
    TUTORIAL_SKIPPED,
)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "sound": True,
    "volume": 0.6,
    "low_effects": False,
    "preview": True,
    "alerts": True,
    "seen_welcome": False,
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _empty_tutorial_chapter() -> Dict[str, Any]:
    return {"lessons": {}, "skipped": False, "completed_at": ""}


def default_save() -> Dict[str, Any]:
    return {
        "version": SAVE_VERSION,
        "settings": copy.deepcopy(DEFAULT_SETTINGS),
        "main": {"levels": {}},
        "tutorial": {"chapters": {}, "intro_dismissed": False},
        "achievements": {},
        "challenges": {},
        "daily": {},
        "custom": {"last_result": None},
    }


class ProgressStore:
    """Load / mutate / persist the local save file.

    The store keeps a plain dictionary internally so that future versions can
    add keys without breaking older save files.
    """

    def __init__(
        self, path: Optional[Path] = None, legacy_path: Optional[Path] = None
    ) -> None:
        self.path = Path(path) if path else save_path()
        if legacy_path is not None:
            self.legacy_path: Optional[Path] = Path(legacy_path)
        elif path is None and not data_override():
            self.legacy_path = legacy_save_path()
        else:
            self.legacy_path = None
        self.data: Dict[str, Any] = default_save()
        self.load_error: str = ""
        self.migrated_from: str = ""
        self.notice: str = ""

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
            return None
        return raw if isinstance(raw, dict) else None

    def load(self) -> "ProgressStore":
        raw = self._read_json(self.path)
        if raw is not None:
            self.data = self._migrate(raw)
            if raw.get("version") != SAVE_VERSION:
                self.save()
            return self

        # First launch after the rename: migrate the old save exactly once.
        if (
            self.legacy_path is not None
            and self.path != self.legacy_path
            and not self.path.exists()
        ):
            if self.legacy_path.exists():
                legacy_raw = self._read_json(self.legacy_path)
                if legacy_raw is not None:
                    self.data = self._migrate(legacy_raw)
                    self.migrated_from = str(self.legacy_path)
                    self.notice = (
                        "已把旧存档迁移到新的存档目录，原有进度已保留。\n"
                        "旧文件不会被删除。"
                    )
                    self.save()
                    return self
                self.load_error = "旧存档无法读取，已使用全新的存档（旧文件没有被删除）"
                self.notice = self.load_error
                self.data = default_save()
                return self

        try:
            self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.data = default_save()
            return self
        except OSError:
            pass
        self.data = default_save()
        self.load_error = "存档文件损坏，已使用全新的存档"
        return self

    def consume_notice(self) -> str:
        """Return and clear a one-shot startup message for the interface."""
        text = self.notice
        self.notice = ""
        return text

    def _migrate(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        base = default_save()
        for section in ("settings", "main", "tutorial", "achievements", "challenges", "daily"):
            if isinstance(raw.get(section), dict):
                base[section].update(raw[section])
        base["version"] = SAVE_VERSION
        # Settings are merged shallowly so that new options get defaults.
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        settings.update(raw.get("settings") or {})
        settings.pop("speed", None)  # real-time speed no longer exists
        base["settings"] = settings
        for record in base["main"].get("levels", {}).values():
            if isinstance(record, dict):
                record.pop("obstacles", None)
        # Renamed counters from step based saves.
        for record in base["main"].get("levels", {}).values():
            if isinstance(record, dict) and "best_steps" in record:
                record.setdefault("best_turns", record.pop("best_steps"))
        for entry in base["daily"].values():
            if isinstance(entry, dict) and "steps" in entry:
                entry.setdefault("turns", entry.pop("steps"))
        return base

    def save(self) -> None:
        try:
            ensure_data_dir()
            payload = json.dumps(self.data, ensure_ascii=False, indent=2)
            directory = self.path.parent
            directory.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=".save-", suffix=".json", dir=str(directory))
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_name, self.path)
        except OSError:
            # A read-only home directory must never crash the game.
            pass

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    @property
    def settings(self) -> Dict[str, Any]:
        return self.data.setdefault("settings", copy.deepcopy(DEFAULT_SETTINGS))

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, DEFAULT_SETTINGS.get(key, default))

    def set_setting(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self.save()

    # ------------------------------------------------------------------
    # Main campaign
    # ------------------------------------------------------------------
    @property
    def main_levels(self) -> Dict[str, Any]:
        return self.data.setdefault("main", {}).setdefault("levels", {})

    def main_result(self, level_id: str) -> LevelResult:
        record = self.main_levels.get(level_id) or {}
        rank_raw = record.get("rank")
        return LevelResult(
            level_id=level_id,
            cleared=bool(record.get("cleared")),
            best_turns=record.get("best_turns", record.get("best_steps")),
            rank=Rank(rank_raw) if rank_raw in {r.value for r in Rank} else None,
        )

    def record_main_clear(
        self,
        level_id: str,
        turns: int,
        rank: Rank,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        """Store a campaign win.  Returns True when a new turn record was set."""
        record = self.main_levels.setdefault(level_id, {"cleared": False})
        previous = record.get("best_turns", record.get("best_steps"))
        improved = previous is None or turns < int(previous)
        record["cleared"] = True
        record["attempts"] = int(record.get("attempts", 0)) + 1
        record["cleared_at"] = _now()
        if improved:
            record["best_turns"] = int(turns)
        record.pop("best_steps", None)
        best_rank = record.get("rank")
        if best_rank is None or _rank_value(rank) > _rank_value(Rank(best_rank)):
            record["rank"] = rank.value
        if extra:
            record.update(dict(extra))
        self.save()
        return improved

    def record_main_attempt(self, level_id: str) -> None:
        record = self.main_levels.setdefault(level_id, {"cleared": False})
        record["attempts"] = int(record.get("attempts", 0)) + 1
        self.save()

    def main_cleared(self, level_id: str) -> bool:
        return bool((self.main_levels.get(level_id) or {}).get("cleared"))

    def main_unlocked_count(self, ordered_ids: Iterable[str]) -> int:
        """Number of campaign levels available, derived only from main clears."""
        ids = list(ordered_ids)
        if not ids:
            return 0
        count = 1
        while count < len(ids) and self.main_cleared(ids[count - 1]):
            count += 1
        return count

    def is_main_unlocked(self, ordered_ids: List[str], level_id: str) -> bool:
        if level_id not in ordered_ids:
            return False
        index = ordered_ids.index(level_id)
        if index == 0:
            return True
        return self.main_cleared(ordered_ids[index - 1])

    def total_main_turns(self) -> int:
        total = 0
        for record in self.main_levels.values():
            if record.get("cleared"):
                best = record.get("best_turns", record.get("best_steps"))
                if best:
                    total += int(best)
        return total

    # ------------------------------------------------------------------
    # Tutorial
    # ------------------------------------------------------------------
    @property
    def tutorial(self) -> Dict[str, Any]:
        return self.data.setdefault("tutorial", {"chapters": {}, "intro_dismissed": False})

    def _chapter(self, chapter_id: str) -> Dict[str, Any]:
        chapters = self.tutorial.setdefault("chapters", {})
        chapter = chapters.setdefault(chapter_id, _empty_tutorial_chapter())
        chapter.setdefault("lessons", {})
        chapter.setdefault("skipped", False)
        return chapter

    def lesson_state(self, chapter_id: str, lesson_id: str) -> str:
        lesson = self._chapter(chapter_id)["lessons"].get(lesson_id) or {}
        state = str(lesson.get("state") or TUTORIAL_NOT_STARTED)
        return state if state in TUTORIAL_STATES else TUTORIAL_NOT_STARTED

    def lesson_attempts(self, chapter_id: str, lesson_id: str) -> int:
        lesson = self._chapter(chapter_id)["lessons"].get(lesson_id) or {}
        return int(lesson.get("attempts", 0) or 0)

    def set_lesson_state(
        self, chapter_id: str, lesson_id: str, state: str, *, count_attempt: bool = False
    ) -> None:
        if state not in TUTORIAL_STATES:
            raise ValueError(f"unknown tutorial state: {state}")
        chapter = self._chapter(chapter_id)
        lesson = chapter["lessons"].setdefault(lesson_id, {"state": TUTORIAL_NOT_STARTED})
        lesson["state"] = state
        lesson["updated_at"] = _now()
        if count_attempt:
            lesson["attempts"] = int(lesson.get("attempts", 0)) + 1
        if state == TUTORIAL_COMPLETED:
            lesson["completed_at"] = _now()
            chapter["skipped"] = False
        self.save()

    def skip_lesson(self, chapter_id: str, lesson_id: str) -> None:
        self.set_lesson_state(chapter_id, lesson_id, TUTORIAL_SKIPPED)

    def skip_chapter(self, chapter_id: str, lesson_ids: Iterable[str] = ()) -> None:
        chapter = self._chapter(chapter_id)
        chapter["skipped"] = True
        for lesson_id in lesson_ids:
            chapter["lessons"].setdefault(lesson_id, {"state": TUTORIAL_NOT_STARTED})
        for lesson in chapter["lessons"].values():
            if lesson.get("state") != TUTORIAL_COMPLETED:
                lesson["state"] = TUTORIAL_SKIPPED
        self.tutorial.setdefault("intro_dismissed", True)
        self.save()

    def reset_chapter(self, chapter_id: str) -> None:
        chapters = self.tutorial.get("chapters", {})
        chapters[chapter_id] = _empty_tutorial_chapter()
        self.save()

    def reset_tutorial(self) -> None:
        self.data["tutorial"] = {"chapters": {}, "intro_dismissed": True}
        self.save()

    def chapter_summary(self, chapter_id: str, lesson_ids: Iterable[str]) -> Tuple[int, int]:
        ids = list(lesson_ids)
        done = sum(
            1
            for lesson_id in ids
            if self.lesson_state(chapter_id, lesson_id) in (TUTORIAL_COMPLETED, TUTORIAL_SKIPPED)
        )
        return done, len(ids)

    def chapter_skipped(self, chapter_id: str) -> bool:
        return bool(self._chapter(chapter_id).get("skipped"))

    def tutorial_intro_dismissed(self) -> bool:
        return bool(self.tutorial.get("intro_dismissed", False))

    def dismiss_tutorial_intro(self) -> None:
        self.tutorial["intro_dismissed"] = True
        self.save()

    # ------------------------------------------------------------------
    # Achievements / challenges / daily
    # ------------------------------------------------------------------
    @property
    def achievements(self) -> Dict[str, str]:
        return self.data.setdefault("achievements", {})

    def unlock_achievement(self, achievement_id: str) -> bool:
        """Unlock an achievement.  Returns True when it is newly unlocked."""
        if achievement_id in self.achievements:
            return False
        self.achievements[achievement_id] = _now()
        self.save()
        return True

    def has_achievement(self, achievement_id: str) -> bool:
        return achievement_id in self.achievements

    def record_challenge_best(self, key: str, turns: int) -> bool:
        challenges = self.data.setdefault("challenges", {})
        previous = challenges.get(key)
        if previous is None or turns < int(previous):
            challenges[key] = int(turns)
            self.save()
            return True
        return False

    def challenge_best(self, key: str) -> Optional[int]:
        value = self.data.get("challenges", {}).get(key)
        return int(value) if value is not None else None

    def record_daily(self, date_key: str, payload: Mapping[str, Any]) -> bool:
        daily = self.data.setdefault("daily", {})
        previous = daily.get(date_key)
        if previous is None or (
            payload.get("cleared") and not previous.get("cleared")
        ) or (
            payload.get("cleared")
            and previous.get("cleared")
            and int(payload.get("turns", 9999)) < int(previous.get("turns", 9999))
        ):
            daily[date_key] = dict(payload)
            self.save()
            return True
        return False

    def daily_result(self, date_key: str) -> Optional[Dict[str, Any]]:
        return self.data.get("daily", {}).get(date_key)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------
    def reset_main(self) -> None:
        self.data["main"] = {"levels": {}}
        self.data["challenges"] = {}
        self.data["achievements"] = {}
        self.save()

    def reset_everything(self) -> None:
        self.data = default_save()
        self.save()


def _rank_value(rank: Rank) -> int:
    return {"C": 1, "B": 2, "A": 3, "S": 4}[rank.value]


def load_default_store() -> ProgressStore:
    """Convenience helper used by the application entry point."""
    return ProgressStore().load()
