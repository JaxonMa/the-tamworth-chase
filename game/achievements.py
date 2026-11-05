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
    Achievement("one_step", "一步抓牛", "只移动一回合就抓住了牛。", "让牛被挡住，农夫只差一步。"),
    Achievement("no_obstacles", "零障碍通关", "没有放下任何干草垛就抓住了牛。", "有些牧场本来就会相遇。"),
    Achievement("fenced_cow", "围栏里的牛", "牛被三面围住时抓住它。", "把牛逼进墙角再动手。"),
    Achievement("loop_free", "一气呵成", "重新调整路线后，没有再撞上时间闭环。", "失败后调整布局，再一口气通关。"),
    Achievement("all_levels", "牧场主", "通关全部十个主线关卡。", "主线通关后自然获得。"),
    Achievement("item_master", "道具达人", "在挑战模式里用道具抓住牛。", "苹果、喇叭、泥地、路标和传送门都能帮忙。"),
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
        if sim.steps <= 1:
            self._unlock("one_step")
        if sim.obstacle_count == 0:
            self._unlock("no_obstacles")
        if self._cow_in_corner(level, sim):
            self._unlock("fenced_cow")
        if loops == 0:
            self._unlock("loop_free")
        if mode == "challenge" and sim.items:
            placed = sum(
                1 for pos in sim.items if pos not in {item.pos for item in level.items}
            )
            if placed:
                self._unlock("item_master")
        if mode == "main":
            completed = sum(
                1 for record in store.main_levels.values() if record.get("cleared")
            )
            if completed >= 10:
                self._unlock("all_levels")
        return list(self.newly_unlocked)

    @staticmethod
    def _cow_in_corner(level: Level, sim: Simulation) -> bool:
        from .models import ItemKind

        blocked = set(level.wall_positions) | set(sim.obstacles)
        blocked.update(pos for pos, item in sim.items.items() if item.kind is ItemKind.CRATE)
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
