"""Level editor model and JSON export/import tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.editor import EditorModel, export_level, import_level, list_custom_levels
from game.levels import parse_level
from game.models import CowBehavior, Direction, TileKind, TieBreak
from game.tutorial import TutorialCatalog


@pytest.fixture()
def model() -> EditorModel:
    return EditorModel()


def test_default_model_is_valid(model):
    assert model.width == 10 and model.height == 10
    assert model.validate() == []
    level = model.to_level()
    assert len(level.cow_positions) == 1
    assert level.farmer_start == model.farmer
    assert level.exit_cells == ((1, 1),)
    assert level.max_turns == 30
    assert level.prediction_steps == 5
    assert level.cow_behaviors == (CowBehavior.SEEK_EXIT,)


def test_paint_and_erase(model):
    assert model.set_tile((3, 3), TileKind.TREE)
    assert model.tiles[3][3] is TileKind.TREE
    assert model.set_tile((3, 3), TileKind.GRASS)
    assert model.tiles[3][3] is TileKind.GRASS


def test_cannot_paint_on_actors(model):
    assert model.set_tile(model.farmer, TileKind.FENCE) is False
    assert model.set_tile(model.cows[0][0], TileKind.FENCE) is False


def test_move_actors(model):
    assert model.move_farmer((5, 5))
    assert model.farmer == (5, 5)
    assert model.move_cow((2, 2))
    assert model.cows[0][0] == (2, 2)
    assert model.move_cow((5, 5)) is False


def test_add_remove_and_choose_cows(model):
    assert model.add_cow((3, 3)) is True
    assert len(model.cows) == 2
    assert model.active_cow == 1
    assert model.add_cow((3, 4)) is True
    assert model.add_cow((3, 5)) is False
    assert model.remove_cow() is True
    assert len(model.cows) == 2
    model.cycle_active_cow()
    assert model.active_cow in (0, 1)


def test_exit_tool_toggles_and_validates(model):
    assert model.toggle_exit((4, 4)) is True
    assert (4, 4) in model.exits
    assert model.toggle_exit((4, 4)) is True
    assert (4, 4) not in model.exits
    assert model.toggle_exit(model.farmer) is False
    assert model.toggle_exit(model.cows[0][0]) is False
    assert model.validate() == []


def test_fixed_obstacle_toggle(model):
    assert model.toggle_obstacle((4, 4)) is True
    assert (4, 4) in model.obstacles
    assert model.validate() == []
    assert model.toggle_obstacle((0, 0)) is False
    assert model.toggle_obstacle((4, 4)) is True
    assert (4, 4) not in model.obstacles


def test_behavior_and_tiebreak_controls(model):
    assert model.cows[0][2] is CowBehavior.SEEK_EXIT
    model.cycle_behavior()
    assert model.cows[0][2] is CowBehavior.SEEK_EXIT_AND_FLEE
    model.cycle_exit_tiebreak()
    assert model.exit_tiebreak is TieBreak.LEFT
    model.cycle_flee_tiebreak()
    assert model.flee_tiebreak is TieBreak.LEFT
    model.toggle_block_sight()
    model.toggle_block_each_other()
    assert model.cows_block_sight is True
    assert model.cows_block_each_other is True


def test_grid_round_trip(model):
    model.set_tile((4, 4), TileKind.POND)
    model.max_turns = 45
    model.prediction_steps = 8
    model.sight_range = 5
    model.exit_sight_range = 7
    model.toggle_exit((5, 5))
    model.toggle_obstacle((6, 6))
    model.cycle_behavior()
    level = model.to_level()
    restored = EditorModel.from_level(level)
    assert restored.farmer == model.farmer
    assert restored.cows[0][0] == model.cows[0][0]
    assert restored.tiles[4][4] is TileKind.POND
    assert restored.max_turns == 45
    assert restored.prediction_steps == 8
    assert restored.sight_range == 5
    assert restored.exit_sight_range == 7
    assert restored.exits == model.exits
    assert restored.obstacles == model.obstacles
    assert restored.cows[0][2] is CowBehavior.SEEK_EXIT_AND_FLEE


def test_export_and_import(tmp_path: Path, model):
    model.name = "测试牧场"
    model.set_tile((3, 3), TileKind.HEDGE)
    level = model.to_level()
    path = export_level(level, tmp_path)
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["levels"][0]["name"] == "测试牧场"
    assert payload["levels"][0]["exit_cells"]
    files = list_custom_levels(tmp_path)
    assert files and files[0] == path
    imported = import_level(path)
    assert imported.name == "测试牧场"
    assert imported.tile_at((3, 3)) is TileKind.HEDGE
    assert imported.exit_cells


def test_import_rejects_broken_file(tmp_path: Path):
    path = tmp_path / "broken.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(Exception):
        import_level(path)


def test_validation_flags_broken_limits(model):
    model.max_turns = 1
    assert model.validate()
    model.max_turns = 30
    model.exits.clear()
    assert model.validate()


def test_editor_tutorials_have_new_tasks():
    catalog = TutorialCatalog.load()
    chapter = catalog.get("editor")
    assert chapter is not None
    assert len(chapter.lessons) == 3
    types = {lesson.extra.get("editor_task", {}).get("type") for lesson in chapter.lessons}
    assert {"paint_wall", "set_exits", "export_import"} <= types
    for lesson in chapter.lessons:
        assert lesson.extra.get("starter_grid")


def test_starter_grid_parses_with_exit():
    catalog = TutorialCatalog.load()
    chapter = catalog.get("editor")
    for lesson in chapter.lessons:
        starter = lesson.extra["starter_grid"]
        level = parse_level(
            {
                "id": "starter",
                "name": "起手牧场",
                "grid": starter,
                "max_turns": 40,
                "initial_dummy": 0,
                "exit_cells": [[1, 1]],
            }
        )
        restored = EditorModel.from_level(level)
        assert restored.validate() == []
