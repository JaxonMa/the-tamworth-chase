"""Local achievements.

Each achievement is unlocked once and stored in the save file.  The tracker is
called after every campaign / challenge clear and never blocks gameplay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from .core import Simulation
from .models import GameStatus, Level, Rank
from .progress import ProgressStore


@dataclass(frozen=True)
class Achievement:
    achievement_id: str
    name: str
    description: str
    hint: str


ACHIEVEMENTS: Sequence[Achievement] = (
    Achievement("one_step", "一步抓牛", "只用一个回合就抓住了所有牛。", "把农夫停在牛群的必经之路上。"),
    Achievement("close_call", "最后一回合", "在回合上限的最后一回合完成抓捕。", "别急着放弃，最后一刻也可能翻盘。"),
    Achievement("flawless", "毫发无损", "整局没有一次前进撞墙。", "先转向，再前进。"),
    Achievement("loop_free", "一气呵成", "整局没有出现循环提示。", "看准牛的路线，一次开对。"),
    Achievement("all_levels", "牧场主", "通关全部十个主线关卡。", "主线通关后自然获得。"),
)

ACHIEVEMENTS_BY_ID: Dict[str, Achievement] = {item.achievement_id: item for item in ACHIEVEMENTS}


class AchievementTracker:
    """Evaluates unlock conditions and writes them to the save store."""

    def __init__(self, store: ProgressStore) -> None:
        self.store = store
        self.newly_unlocked: List[Achievement] = []

    def reset_transient(self) -> None:
        self.newly_unlocked = []

    # ------------------------------------------------------------------
    def _unlock(self, achievement_id: str) -> None:
        if self.store.unlock_achievement(achievement_id):
            achievement = ACHIEVEMENTS_BY_ID.get(achievement_id)
            if achievement is not None:
                self.newly_unlocked.append(achievement)

    def on_level_cleared(
        self,
        level: Level,
        sim: Simulation,
        rank: Rank,
        store: ProgressStore,
        *,
        loops: int = 0,
        mode: str = "main",
    ) -> List[Achievement]:
        self.reset_transient()
        if sim.status is not GameStatus.WON:
            return []
        if sim.turns <= 1:
            self._unlock("one_step")
        if sim.turns == level.max_turns:
            self._unlock("close_call")
        if sim.blocked_events == 0:
            self._unlock("flawless")
        if loops == 0:
            self._unlock("loop_free")
        if mode == "main":
            completed = sum(
                1 for record in store.main_levels.values() if record.get("cleared")
            )
            if completed >= 10:
                self._unlock("all_levels")
        return list(self.newly_unlocked)

    # ------------------------------------------------------------------
    def unlocked(self) -> List[Achievement]:
        return [a for a in ACHIEVEMENTS if self.store.has_achievement(a.achievement_id)]

    def locked(self) -> List[Achievement]:
        return [a for a in ACHIEVEMENTS if not self.store.has_achievement(a.achievement_id)]
