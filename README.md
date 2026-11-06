# The Tamworth Chase

*A cozy, hand-drawn, turn-based grid chase puzzle made entirely with Python.*

Farmer John wants to catch his cow. Every turn the player moves the farmer one
tile (or waits), and only then does the cow walk one step of its own. The cow
always walks forward when it can and turns 90° clockwise when a fence, a tree,
the board edge or a hay bale blocks it. Read the route, use the hay, undo a bad
guess, and catch the cow before the turn budget runs out.

The whole game is offline. No accounts, no servers, no telemetry, no network
requests while it runs.

## Rename note

The project was previously released as **The Tamworth Two**. Starting with this
version the name is **The Tamworth Chase** (Chinese subtitle 《塔姆沃斯追逐》).
The save file moved to `~/.the_tamworth_chase/save.json`; an old save is
migrated automatically on first launch and is never deleted.

## Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Virtual environment and installation](#virtual-environment-and-installation)
4. [Running the game](#running-the-game)
5. [Controls](#controls)
6. [Game rules](#game-rules)
7. [Campaign, ranks and unlocks](#campaign-ranks-and-unlocks)
8. [Tutorial chapters](#tutorial-chapters)
9. [Challenge, daily and achievements](#challenge-daily-and-achievements)
10. [Level editor](#level-editor)
11. [Level data schema](#level-data-schema)
12. [Save data](#save-data)
13. [Fonts and licensing](#fonts-and-licensing)
14. [Art and audio](#art-and-audio)
15. [Offline promise](#offline-promise)
16. [Tests](#tests)
17. [Project layout](#project-layout)
18. [Design notes and assumptions](#design-notes-and-assumptions)
19. [Known limitations](#known-limitations)

## Features

- **Direct control.** The player moves Farmer John with the arrow keys or WASD,
  or waits with Space. The cow reacts afterwards, so every turn is a small
  decision instead of a pre-run simulation.
- **10 campaign levels** on 10×10 meadows, including two-cow levels and a
  no-prediction level. Levels unlock one at a time; turns decide the S/A/B/C
  grade.
- **Multi-level undo.** Undo any turn, or step all the way back to the
  placement phase. Placement actions are undoable too, before or after the
  chase starts.
- **Configurable path preview.** Each level chooses how many future cow steps
  to show (0–20, default 5). The preview is drawn as translucent hoof prints
  and can be toggled at any time with `P`.
- **Loop hint, not a loss.** When the cows' positions and facings repeat, a
  Chinese hint appears. The game keeps going; the player can break the loop.
- **Two win conditions.** Catch any cow, or — on pen levels — have every cow
  inside a marked pen cell at the same time.
- **Independent tutorial chapters.** 5 basic, 3 advanced and 3 editor lessons.
  The tutorial has its own entry, its own progress and its own skip/replay/reset
  controls. Tutorial completion never unlocks a campaign level.
- **Challenge and daily modes.** Five curated side levels, plus a local daily
  meadow generated from the calendar date and verified solvable on the device.
- **Level editor.** Paint terrain, place the farmer and up to three cows, set
  the turn budget, obstacle count, prediction depth and win condition, paint pen
  cells, test-play, then export/import plain JSON.
- **Achievements.** One-turn catch, obstacle-free clear, pen clear, loop-free
  run, and full campaign completion, all stored locally.
- **Procedural picture-book art.** Grass, fences, hedges, ponds, trees, the
  farmer, cows, hay bales and pen tiles are drawn in code. No bitmap sprite
  sheets and no emoji are used.
- **Bundled Chinese font.** CEF Fonts CJK is shipped with the game and loaded
  locally.

## Requirements

- Python 3.10 or newer (developed and tested with Python 3.14.7)
- `pygame-ce` 2.5.x
- `pytest` for the test suite only
- macOS, Linux or Windows with a desktop session for the graphical window

## Virtual environment and installation

The project uses its own `.venv`; dependencies are never installed into the
global Python.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On Windows the interpreter path is `.venv\Scripts\python.exe`.

## Running the game

```bash
.venv/bin/python main.py
```

The window is 1280×840. All player-facing text is Simplified Chinese; the code,
comments and docstrings are English.

## Controls

| Input | Action |
|---|---|
| Arrow keys / `W` `A` `S` `D` | Move Farmer John one tile |
| Space | Wait one turn (or start the chase during placement) |
| Mouse left click | Place / remove a hay bale during placement |
| Mouse right click | Remove a hay bale during placement |
| `U` | Undo one action (placement or turn) |
| `R` | Restart the level in the placement phase |
| `P` | Toggle the path preview |
| `Esc` | Return to the previous screen |

The UI also shows clickable **撤销**, **重开** and **预测** buttons at the top.
Paused, single-step and speed controls do not exist: the player sets the pace.

## Game rules

### State machine

```
placement → playing ⇄ undo / restart → win / loss
```

- **Placement:** place up to the level's allowed number of hay bales. Hay cannot
  be placed on the farmer, a cow, a wall or another bale. Press Space or the
  start button to begin.
- **Playing:** each turn is one player action followed by one cow step.
- **Finished:** a win or loss opens a result dialog. The player can restart,
  undo to the previous turn (loss) or go to the next lesson/level (win).

### Turn order

1. The player orders Farmer John to move north/east/south/west, or to wait.
2. If the farmer's target is a wall, the board edge or a hay bale, the order is
   rejected. It does not consume a turn; a Chinese toast explains why.
3. The farmer moves and faces the direction of travel. Waiting keeps the facing.
4. If the farmer shares a tile with a cow, the level is won immediately.
5. Every cow moves once, in fixed list order. A cow walks forward when the
   target tile is free; otherwise it turns 90° clockwise and stays put.
6. If a cow shares the farmer's tile after moving, the level is won.
7. In pen levels, if every cow is on a pen cell, the level is won.
8. The turn counter increases. Reaching the level's `max_turns` without a win
   loses.

Farmer John and the cows never block each other: only terrain, the board edge
and hay bales do. The farmer may step onto a cow to catch it.

### Cows and cow order

- Cows are deterministic. They never chase, flee or react to the farmer.
- With several cows, index order decides who moves first. Earlier cows are
  committed before later cows move.
- `cows_block_each_other` (default `false`) makes a cow treat another cow's
  current tile as an obstacle, so a queue of cows can push the rear cow into a
  turn. This is tested and used by one campaign/challenge level.

### Winning and losing

- **Catch:** the farmer and any cow occupy the same tile, checked after the
  farmer moves and again after the cows move. Catching always wins, including
  on pen levels.
- **Pen:** all cows are inside the level's pen cells at the same time. Pen
  levels are usually built as sealed rooms so the farmer cannot catch the cow;
  the pen is the intended solution.
- **Turn limit:** the level fails when the turn counter reaches `max_turns`
  without a win. The winning turn may be the last allowed turn.
- **Loop hint:** repeating cow poses produce a Chinese hint and a soft chime,
  but never a loss.
- **Undo:** restores the farmer, every cow, the hay bales, the turn counter and
  the loop history. The failure dialog offers **撤销到上一回合** and
  **重开本关**.

### Path preview

The preview simulates the cows only, assuming the farmer waits. It shows at most
`prediction_steps` future cow poses as dashed lines and hoof prints. `0` turns
the preview off for that level; the `P` shortcut then explains that the level has
no preview. The preview never mutates the live game state.

## Campaign, ranks and unlocks

- Ten levels, `level_01` … `level_10`, all 10×10.
- Clearing a level unlocks the next one. The first level is always available.
- The grade is based on the number of turns: each level defines
  `s_threshold`, `a_threshold` and `b_threshold`. Lower is better.
- Best turn counts and ranks are stored per level. Tutorial progress is stored
  in a different section and never affects campaign unlocking.
- Levels 8 and 10 have two cows; level 9 has `prediction_steps: 0`.

## Tutorial chapters

The tutorial is a separate book with three independent chapters:

| Chapter | File | Lessons | Focus |
|---|---|---|---|
| 基础教程 (basics) | `tutorials/basics.json` | 5 | moving, corner turns, waiting, undo, prediction |
| 进阶教程 (advanced) | `tutorials/advanced.json` | 3 | multiple cows, pen victory, loop hint |
| 编辑器教程 (editor) | `tutorials/editor.json` | 3 | painting, new rule fields, export/import |

- Each chapter has its own progress, entry point, lesson list, skip button and
  reset button. Lessons unlock in order and can be replayed.
- A lesson can be skipped individually, a whole chapter can be skipped, or all
  tutorial progress can be reset from Settings.
- Some lessons enforce a practice step before they count as complete: placing
  hay, undoing a placement, opening the preview, or waiting at least one turn.
  The panel shows the practice text under the hint.
- Tutorial lessons do not receive S/A/B/C grades.
- The loop lesson completes when the loop hint appears, so it never needs an
  artificial loss.

## Challenge, daily and achievements

- **Challenge:** five side levels (`levels/challenges.json`) with local best
  turn counts. They do not consume campaign progress.
- **Daily:** a meadow generated from the local date with a fixed seed. The
  generator performs a bounded search on the device and falls back to campaign
  level 1 only if no candidate is winnable. A seven-day local history is kept.
- **Achievements:** `one_step`, `no_obstacles`, `fenced_cow`, `loop_free`,
  `all_levels`. They are awarded once and stored in the save file.

## Level editor

- Paint grass, fence, hedge, tree or pond.
- Place the farmer, move the first cow, and add up to three cows.
- Set `initial_obstacles` (0–9), `max_turns` (5–120), `prediction_steps` (0–20)
  and `cows_block_each_other`.
- Switch the win condition between catch and pen; with the pen tool, click
  walkable cells to toggle pen cells.
- Test-play with the real simulation, then export. Exports are written to
  `custom_levels/` as ordinary JSON bundles. Importing reads the first level from
  a bundle.
- The editor tutorial teaches painting, the new rule fields and export/import.
  The level name is currently fixed to “我的牧场”; there is no text input.

## Level data schema

Levels are JSON objects inside `levels/*.json` or `tutorials/*.json`:

```json
{
  "id": "level_01",
  "name": "晨露草坪",
  "grid": ["##########", "#........#", "..."],
  "farmer_facing": "east",
  "cow_facings": ["north"],
  "max_turns": 20,
  "initial_obstacles": 1,
  "prediction_steps": 5,
  "win_condition": "catch",
  "pen_cells": [],
  "cows_block_each_other": false,
  "s_threshold": 8,
  "a_threshold": 12,
  "b_threshold": 16,
  "hint": "先按方向键走一步，看看牛怎么动。",
  "description": "新的一天从一片开阔的草地开始。",
  "goal": "抓住牛",
  "practice": "用方向键移动农夫。",
  "tips": [{"trigger": "start", "text": "..."}]
}
```

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | required | Unique level id |
| `name` | string | id | Chinese display name |
| `grid` | string[] | required | Rows of the meadow |
| `farmer_facing` | string | `east` | Visual facing; movement is free |
| `cow_facings` | string[] | `east` | One facing per cow, in order |
| `max_turns` | int | 30 | Turn budget |
| `initial_obstacles` | int | 3 | Hay bales placeable before the chase |
| `prediction_steps` | int | 5 | Preview depth; 0 disables it |
| `win_condition` | `"catch"` / `"pen"` | `catch` | Win rule |
| `pen_cells` | [row, col][] | `[]` | Required for `pen` |
| `cows_block_each_other` | bool | false | Cows treat each other as obstacles |
| `s/a/b_threshold` | int | derived | Grade thresholds in turns |
| `hint` / `description` / `goal` / `practice` | string | `""` | Chinese UI text |
| `tips` | `{trigger, text}[]` | `[]` | Tutorial hints |

Grid characters: `.` grass, `,` flowers, `#` fence, `T` tree, `~` pond,
`H` hedge, `F` farmer, `C` cow. Legacy maps that use `D`, `G` or `S` for cows
still load; they are read as ordinary cows because personalities were removed.

**Backward compatibility.** Old files that use `step_limit` or `obstacle_limit`
are read as fallbacks for `max_turns` and `initial_obstacles`. Fields that only
belonged to the removed automatic simulation (`speed`, `pause`, items, apples,
cow personalities) are ignored. Missing new fields take their defaults.

## Save data

Progress is stored as JSON outside the repository:

- Default: `~/.the_tamworth_chase/save.json`
- Override: set `TAMWORTH_CHASE_DATA` to a directory before starting.
  The pre-rename environment variable is still read for compatibility.
- On the first launch after the rename, the old save is copied to the new
  location, the old file is left untouched, and a startup dialog reports the
  migration. A corrupt old file produces a message and a fresh save; it never
  crashes the game.

The file keeps these sections apart: `settings`, `main` (campaign), `tutorial`,
`achievements`, `challenges`, `daily`, `custom`. Writes are atomic and a
corrupt file falls back to a fresh save. Save version 4 renames step records to
turn records and drops the removed speed setting.

## Fonts and licensing

- `assets/fonts/CEFFontsCJK-Regular.ttf` — bundled CEF Fonts CJK, SIL Open Font
  License 1.1. The full license text is in `assets/fonts/OFL.txt`.
- The font is loaded from the repository at runtime; no font is downloaded.
- CEF Fonts CJK draws the digit `1` in a way that resembles a slash, so digit
  runs are rendered with a system rounded font (SF Rounded, Avenir Next,
  Helvetica Neue, DejaVu Sans or Arial) while Chinese and Latin text keeps the
  handwritten face. If the font is missing, the UI falls back to system CJK
  fonts instead of showing boxes.

## Art and audio

- Every visual is procedural: soft grass textures, connecting wooden fences,
  hedges, tree groves, ponds, four farmer facings, cow sprites, hay bales and
  pen tiles. Tiles are drawn at a higher resolution and smoothed down.
- No emoji are used for game objects.
- All sound effects are synthesised at start-up from simple waveforms in
  `game/audio.py`; the repository ships no audio files. Sound can be muted and
  the volume adjusted in Settings.

## Offline promise

- The game does not import networking modules and makes no network requests.
- The only binary asset is the bundled font.
- No accounts, rooms, matchmaking, servers, WebSockets, cloud saves or online
  leaderboards are involved.
- Daily seeds come from the local date, not from a server.

## Tests

```bash
.venv/bin/python -m pytest -q
```

The suite covers farmer movement in all four directions, blocked orders that do
not consume a turn, strict farmer-then-cow turn order, multi-cow order and
blocking, catch and pen wins, the turn budget, loop hints that never lose,
undo/restart and full state restoration, configurable previews, legacy level
fields, the save migration, tutorial isolation and practice gates, editor JSON
round-trips, achievement rules, daily determinism, offline scanning, and a
head-less render smoke test for every scene.

## Project layout

```
main.py                     Entry point
game/
  models.py                 Head-less data models
  core.py                   Turn-based simulation, undo, previews
  levels.py                 Level schema, parsing and serialisation
  tutorial.py               Tutorial catalogue, state machine, hints
  progress.py               Local save sections and migration
  achievements.py           Achievement rules
  editor.py                 Editor model and JSON exchange
  daily.py                  Local daily seed + solvability search
  animation.py              One-turn interpolation
  render.py                 Board, footprints, pen cells, effects
  theme.py                  Palette, fonts, layout
  ui.py                     Buttons, toggles, modal dialogs
  art.py                    Procedural artwork
  audio.py                  Synthesised cues
  app.py                    Window and scene routing
  scenes/                   Menu, level select, play, tutorial, challenge,
                            daily, editor, achievements, settings
levels/                     Campaign and challenge JSON
tutorials/                  Three tutorial chapters
assets/fonts/               Bundled CJK font and OFL text
tests/                      Unit, integration and data tests
tools/                      Solver, tutorial builder, screenshot helper
```

The custom level export directory `custom_levels/` and the save directory are
not tracked by Git.

## Design notes and assumptions

- **Catch is always a win.** The rules state that stepping onto a cow wins, so
  this holds on pen levels too. Pen levels are built as sealed rooms where the
  farmer cannot reach any cow, which makes the pen the only practical solution.
- **Cows never react to the farmer.** Their routes depend only on terrain, hay
  and each other. This keeps them predictable and makes the preview exact.
- **Prediction assumes the farmer waits.** It is a map of the cows' future
  poses, not a promise of the player's own route.
- **Loop hints are informational.** The cow state is the tuple of positions and
  facings; a repeat sets the hint and a counter but does not end the attempt.
- **Undo is state based.** Each placement or turn pushes a complete snapshot
  (farmer, cows, hay, turn count, loop history). Undo restores the snapshot;
  redo is available internally but not bound to a key.
- **Waiting is a real turn.** It consumes the turn budget and lets every cow
  move.
- **No hidden time pressure.** There is no real-time clock while playing; the
  turn budget is the only limit.

## Known limitations

- The graphical UI is verified head-less with rendered screenshots and injected
  events. It has not been manually play-tested on a physical display in this
  environment.
- Audio is synthesised and its code path runs with a dummy device; it has not
  been auditioned here.
- The editor uses a fixed level name and does not provide text input.
- The daily generator falls back to campaign level 1 if every candidate fails
  the bounded solvability search.
- Undo keeps at most 256 snapshots per attempt.
- Large custom levels are limited to the editor's 10×10 canvas.
