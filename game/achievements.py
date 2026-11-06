"""Local achievements.

Each achievement is unlocked once and stored in the save file.  The tracker is
called after every campaign / challenge clear and never blocks gameplay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

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
    Achievement("one_step", "一步抓牛", "只用一个回合就抓住了牛。", "让牛被挡住，农夫只差一步。"),
    Achievement("no_obstacles", "零障碍通关", "没有放下任何干草垛就抓住了牛。", "有些牧场本来就会相遇。"),
    Achievement("fenced_cow", "围栏里的牛", "把牛赶进围栏，或把它逼进死角。", "围栏关里让所有牛同时进栏。"),
    Achievement("loop_free", "一气呵成", "整局没有出现牛的循环提示。", "看准牛的路线，一次走对。"),
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
        if sim.obstacle_count == 0:
            self._unlock("no_obstacles")
        if sim.penned_count == len(sim.cows) or self._cow_in_corner(level, sim):
            self._unlock("fenced_cow")
        if loops == 0:
            self._unlock("loop_free")
        if mode == "main":
            completed = sum(
                1 for record in store.main_levels.values() if record.get("cleared")
            )
            if completed >= 10:
                self._unlock("all_levels")
        return list(self.newly_unlocked)

    @staticmethod
    def _cow_in_corner(level: Level, sim: Simulation) -> bool:
        blocked = set(level.wall_positions) | set(sim.obstacles)
        for cow in sim.cows:
            row, col = cow.pos
            sides = 0
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                if (row + dr, col + dc) in blocked:
                    sides += 1
            if sides >= 3:
                return True
        return False

    # ------------------------------------------------------------------
    def unlocked(self) -> List[Achievement]:
        return [a for a in ACHIEVEMENTS if self.store.has_achievement(a.achievement_id)]

    def locked(self) -> List[Achievement]:
        return [a for a in ACHIEVEMENTS if not self.store.has_achievement(a.achievement_id)]
