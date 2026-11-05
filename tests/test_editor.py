"""Level editor model and JSON export/import tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.editor import (
    EditorModel,
    export_level,
    import_level,
    list_custom_levels,
)
from game.levels import parse_level
from game.models import CowPersonality, Direction, TileKind
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
    # cannot share a tile with the farmer
    assert model.move_cow((5, 5)) is False


def test_cycle_personality_and_facing(model):
    start = model.cows[0][2]
    model.cycle_cow_personality()
    assert model.cows[0][2] is not start
    facing = model.farmer_facing
    model.cycle_facing()
    assert model.farmer_facing is facing.clockwise()


def test_grid_round_trip(model):
    model.set_tile((4, 4), TileKind.POND)
    level = model.to_level()
    restored = EditorModel.from_level(level)
    assert restored.farmer == model.farmer
    assert restored.cows[0][0] == model.cows[0][0]
    assert restored.tiles[4][4] is TileKind.POND


def test_export_and_import(tmp_path: Path, model):
    model.name = "测试牧场"
    model.set_tile((3, 3), TileKind.HEDGE)
    level = model.to_level()
    path = export_level(level, tmp_path)
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["levels"][0]["name"] == "测试牧场"

    files = list_custom_levels(tmp_path)
    assert files and files[0] == path
    imported = import_level(path)
    assert imported.name == "测试牧场"
    assert imported.tile_at((3, 3)) is TileKind.HEDGE


def test_import_rejects_broken_file(tmp_path: Path):
    path = tmp_path / "broken.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(Exception):
        import_level(path)


def test_validation_flags_broken_limits(model):
    model.step_limit = 1
    assert model.validate()


def test_editor_tutorial_chapter_exists():
    catalog = TutorialCatalog.load()
    chapter = catalog.get("editor")
    assert chapter is not None
    assert len(chapter.lessons) == 3
    for lesson in chapter.lessons:
        assert lesson.extra.get("editor_task"), lesson.level_id
        assert lesson.extra.get("starter_grid")
        assert lesson.tips


def test_starter_grid_parses():
    catalog = TutorialCatalog.load()
    chapter = catalog.get("editor")
    for lesson in chapter.lessons:
        starter = lesson.extra["starter_grid"]
        level = parse_level(
            {
                "id": "starter",
                "name": "起手牧场",
                "grid": starter,
                "obstacle_limit": 3,
                "step_limit": 40,
            }
        )
        restored = EditorModel.from_level(level)
        assert restored.validate() == []
