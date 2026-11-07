# The Tamworth Chase

*A cozy, hand-drawn chase through the meadow — steer the farmer, guard the gate.*

Farmer John now drives with absolute-direction steering: every command turns him
to face up, down, left or right, or moves him forward one tile. The cows are
always alert: when the farmer is in sight they run away; otherwise they head for
the golden exit or patrol along the fences. Catch every cow before any cow
reaches an exit.

The game is a single-player, turn-based puzzle. It runs fully offline: no
accounts, servers, telemetry or network requests at runtime.

## Rename note

The project was previously released as **The Tamworth Two**. The name is now
**The Tamworth Chase** (Chinese subtitle 《塔姆沃斯追逐》). The save file lives at
`~/.the_tamworth_chase/save.json`; an old save is copied there once and is never
deleted.

## Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Running](#running)
5. [Controls](#controls)
6. [Rules](#rules)
7. [The cows](#the-cows)
8. [Winning and losing](#winning-and-losing)
9. [Prediction, alerts and loops](#prediction-alerts-and-loops)
10. [Campaign and ranks](#campaign-and-ranks)
11. [Tutorial chapters](#tutorial-chapters)
12. [Challenge, daily and achievements](#challenge-daily-and-achievements)
13. [Level editor](#level-editor)
14. [Level data schema](#level-data-schema)
15. [Save data](#save-data)
16. [Fonts and licensing](#fonts-and-licensing)
17. [Art and audio](#art-and-audio)
18. [Offline promise](#offline-promise)
19. [Tests](#tests)
20. [Project layout](#project-layout)
21. [Design notes and assumptions](#design-notes-and-assumptions)
22. [Known limitations](#known-limitations)

## Features

- **Pure driving.** There is no placement phase and no player-placed obstacle.
  The level starts immediately; every turn the player turns or moves.
- **Absolute steering.** `W`/`↑` faces up, `S`/`↓` faces down, `A`/`←` faces
  left, `D`/`→` faces right, and Space moves one tile in the current direction.
  The direction key matching the current facing is invalid and costs no turn.
- **No waiting.** Every valid turn changes the facing or moves the farmer.
- **Unified cow instinct.** Every cow flees when it can see the farmer. When it
  cannot, it seeks a visible exit or patrols. There is no per-cow behaviour
  switch.
- **Escape pressure.** Every level has golden exit cells. A cow reaching any
  exit loses the run immediately.
- **All cows or nothing.** Every cow must be caught; multi-cow levels only end
  when the last cow is caught.
- **Multi-level undo.** Undo back to the opening position, including the
  farmer's facing, every cow's pose, caught flags and turn count.
- **Configurable preview.** Each level chooses how many cow steps to show
  (0–20, default 5). The preview assumes the farmer keeps his current position
  and facing; the UI states that assumption in Chinese.
- **Exit warnings.** Exits are drawn as wooden gates; a cow within three tiles
  highlights the gate and a Chinese warning appears.
- **Alert icons.** Fleeing cows display a small exclamation mark; the icons can
  be toggled in the top bar or Settings.
- **Independent tutorials.** Seven basic, three advanced and three editor
  lessons with their own progress, skip/replay/reset and practice gates.
- **Challenge and daily modes.** Five curated challenges and a local daily
  meadow generated from the date and verified solvable on the device.
- **Level editor.** Paint terrain, place the farmer and up to three cows, set
  exits, fixed obstacles, sight ranges and turn budgets, test-play, export and
  import JSON.
- **Procedural picture-book art.** Grass, fences, hedges, ponds, cows, the
  farmer, gates and alert bubbles are drawn in code. No emoji are used as game
  objects.

## Requirements

- Python 3.10 or newer (tested with 3.14.7)
- `pygame-ce` 2.5.x
- `pytest` for tests only
- A desktop session for the game window

## Installation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On Windows use `.venv\Scripts\python.exe`.

## Running

```bash
.venv/bin/python main.py
```

The window is 1280×840. All player-facing text is Simplified Chinese; code,
comments, docstrings and commit messages are English.

## Controls

| Input | Action |
|---|---|
| `W` / `↑` | Face up (consumes a turn when different) |
| `S` / `↓` | Face down (consumes a turn when different) |
| `A` / `←` | Face left (consumes a turn when different) |
| `D` / `→` | Face right (consumes a turn when different) |
| Space | Move forward one tile |
| `U` | Undo one turn |
| `R` | Restart the level |
| `P` | Toggle the path preview |
| `Esc` | Return to the previous screen |

Pressing the direction that matches the current facing shows **已朝该方向** and
does not consume a turn. The top bar also has **撤销**, **重开**, **预测** and
**警觉** buttons. There is no wait command, pause, single-step or speed control.

## Rules

### State machine

```
playing ⇄ undo / restart → win / loss
```

There is no placement phase. A level starts in the playing state. The result
dialog offers **撤销到上一回合**, **重开本关** and **返回**.

### One turn

1. The player performs exactly one action: face up/down/left/right, or move
   forward.
2. A turn to a different direction changes the facing, keeps the position and
   consumes the turn. A turn to the current facing is invalid and costs nothing.
3. Forward moves one tile in the current facing. If a fence, the board edge or a fixed
   obstacle blocks the tile, the position and facing stay
   unchanged, the turn is still consumed, and the game shows
   **前方受阻，本回合已消耗**.
4. If the farmer enters a cow's tile, that cow is caught.
5. If every cow is caught, the level is won immediately.
6. Every cow moves once, in level order. After each cow move, arriving at an
   exit fails the run; sharing the farmer's tile catches that cow.
7. After all cows, all caught means victory; otherwise the turn counter
   increases. Reaching the level's turn budget without a win fails the run.

A winning move on the last allowed turn is checked before the budget and is
accepted.

## The cows

All cows use the same decision order.

### 1. Can the cow see the farmer?

Sight means:

- same row or same column;
- no wall, fixed obstacle or board edge between the two;
- Manhattan distance within `sight_range` (`-1` means unlimited);
- optionally, other cows block sight when `cows_block_sight` is true.

### 2. Flee when the farmer is visible

- If the forward tile is passable and moving there strictly increases the
  Manhattan distance to the farmer, the cow moves forward.
- Otherwise it turns toward the side whose forward tile is farther from the
  farmer. Ties use `flee_tiebreak` (default `right`).
- If neither side increases the distance, it still turns according to that
  comparison; it does not fall back to patrol.

### 3. Otherwise seek the exit

- A visible exit is in the cow's straight line (same row or column), no terrain
  blocks it, and its distance is within `exit_sight_range` (`-1` unlimited).
- If several exits are visible, the nearest wins; ties use `(row, column)` order.
- If the cow already faces the chosen exit and the forward tile is passable, it
  moves forward. Otherwise it turns toward the exit; if the exit is directly
  behind, `exit_tiebreak` (default `right`) chooses the first 90° turn. It keeps
  turning on later turns.
- If no exit is visible, it patrols: move forward when possible; otherwise turn
  90° clockwise in place.

### 4. Multi-cow order

- Cows move in level order, deterministically.
- `cows_block_each_other` (default false) makes another active cow block the
  forward tile.
- A caught cow is skipped for movement, sight, exits and rendering; its stored
  position is retained only for undo.

## Winning and losing

- **Win:** all cows are caught.
- **Lose — escape:** any cow reaches any exit cell.
- **Lose — turns:** the turn budget is reached without a win.
- **Failure dialog:** distinguishes **牛从出口逃走了** from **回合数已用完**.
- **Undo:** available from the failure dialog and at any time during play.

Exits belong to the fixed terrain. The farmer may stand on an exit, but a cow
entering that exit while the farmer is there still escapes; exit resolution
happens before catching.

## Prediction, alerts and loops

The preview shows up to `prediction_steps` future cow poses while Farmer John
stays at his current position and facing. It is drawn as translucent footprints
and dashed paths, with a Chinese caption explaining the assumption. If a
predicted cow reaches an exit, the final point is marked in red. `0` disables
the preview for that level.

The top bar's **警觉** button toggles the alert icons above fleeing cows; the
same option is available in Settings.

If the complete pose — farmer position/facing, every cow position/facing and
caught flags — repeats, a Chinese **局面进入循环** hint appears. It never loses
the run. The hint is informational; the player can continue and break the loop.

## Campaign and ranks

- Ten 10×10 campaign levels. Clearing one unlocks the next; the first is always
  available.
- The best turn count and S/A/B/C rank are stored per level. Grades use the
  level's `s_threshold`, `a_threshold` and `b_threshold`.
- Every campaign cow now uses the unified "flee when seen, otherwise seek the
  exit" instinct. Levels 8 and 10 have two cows; level 9 has
  `prediction_steps: 0`.
- Exits are part of the fixed terrain and are visible in the level cards.

## Tutorial chapters

| Chapter | File | Lessons | Focus |
|---|---|---|---|
| 基础教程 | `tutorials/basics.json` | 7 | absolute turns, forward, wall penalty, exit route, fleeing, wall cover, interception, undo + preview |
| 进阶教程 | `tutorials/advanced.json` | 3 | larger flee chase, two cows, exit pressure |
| 编辑器教程 | `tutorials/editor.json` | 3 | terrain, exits and sight rules, export/import |

- Each chapter has its own entry, progress, lesson list, skip and reset.
- Lessons unlock in order and can be replayed; skipping never touches the
  campaign.
- Practice gates: the first lesson requires a same-direction attempt and a
  forward move; other lessons require a blocked forward, a minimum number of
  turns, a preview/undo, or the editor task. The practice is written in the
  tutorial box.
- Tutorial lessons do not receive S/A/B/C grades.

## Challenge, daily and achievements

- **Challenge:** five curated side levels with local best turns.
- **Daily:** a meadow generated from the local date, checked by a bounded
  breadth-first search; falls back to campaign level 1 only if no candidate is
  winnable.
- **Achievements:** `one_step`, `close_call`, `flawless`, `loop_free`,
  `all_levels`.
  - `one_step`: catch all cows in one turn.
  - `close_call`: win on the last allowed turn.
  - `flawless`: never bump a wall while moving forward.
  - `loop_free`: never trigger the loop hint.
  - `all_levels`: clear all ten campaign levels.

## Level editor

- Paint grass, fence, hedge, tree or pond.
- Place the farmer, move/add/remove up to three cows, and choose the active cow.
- Use the exit tool to add/remove exits on walkable cells. At least one exit is
  required.
- Toggle fixed hay-bale obstacles.
- Edit `max_turns`, `prediction_steps`, `sight_range` and `exit_sight_range`.
- Cycle the active cow's facing, the exit/flee tiebreaks, and the
  `cows_block_sight` / `cows_block_each_other` flags. Cow behaviour is always
  unified; there is no behaviour switch.
- Test-play with the real simulation, then export to `custom_levels/` as JSON.
  Import reads the first level from a bundle.
- The editor level name is currently fixed to “我的牧场”; there is no text
  input.

## Level data schema

```json
{
  "version": 4,
  "game": "The Tamworth Chase",
  "levels": [
    {
      "id": "level_01",
      "name": "晨露草坪",
      "grid": ["##########", "#........#", "..."],
      "fj_start_direction": "north",
      "cow_facings": ["east"],
      "exit_cells": [[1, 1]],
      "max_turns": 16,
      "prediction_steps": 5,
      "exit_sight_range": -1,
      "sight_range": -1,
      "exit_tiebreak": "right",
      "flee_tiebreak": "right",
      "cows_block_sight": false,
      "cows_block_each_other": false,
      "walls": [],
      "obstacles": [],
      "hint": "把农夫开到牛和出口之间；撞墙前进会浪费回合。",
      "goal": "抓住全部牛"
    }
  ]
}
```

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | required | Unique level id |
| `name` | string | id | Chinese display name |
| `grid` | string[] | required | Terrain rows; `F` farmer, `C` cows |
| `fj_start_direction` | string | `north` | Farmer's initial facing (`up/right/down/left` accepted) |
| `cow_facings` | string[] | `east` | One facing per cow |
| `exit_cells` | `[row,col][]` | required | At least one walkable exit |
| `max_turns` | int | 30 | Turn budget |
| `prediction_steps` | int | 5 | Preview depth; 0 disables |
| `exit_sight_range` | int | -1 | Exit visibility range; -1 unlimited |
| `sight_range` | int | -1 | Farmer visibility range; -1 unlimited |
| `exit_tiebreak` / `flee_tiebreak` | `right` / `left` | `right` | Tie-breaking side |
| `cows_block_sight` | bool | false | Cows block the farmer's line of sight |
| `cows_block_each_other` | bool | false | Cows block each other's movement |
| `walls` | `[row,col][]` | `[]` | Optional extra fence coordinates folded into the grid |
| `obstacles` | `[row,col][]` | `[]` | Optional fixed hay-bale blockers |
| `s/a/b_threshold` | int | derived | Grade thresholds in turns |
| `hint` / `description` / `goal` / `practice` | string | `""` | Chinese UI text |
| `tips` | `{trigger,text}[]` | `[]` | Tutorial hints |

Grid characters: `.` grass, `,` flowers, `#` fence, `T` tree, `~` pond,
`H` hedge, `F` farmer, `C` cow. Legacy `D/G/S` cow characters are read as normal
cows. A cow may not start on an exit.

**Backward compatibility.** Old fields `step_limit`, `obstacle_limit`,
`initial_obstacles`, `win_condition`, `pen_cells`, `cow_behavior`,
`cow_personalities`, item fields and `speed`/`pause` are ignored; `step_limit`
is used as a fallback for `max_turns`. If no exit is supplied, a deterministic
far-away walkable cell is chosen and marked as a legacy default; old custom
levels still load. `cow_behavior` is deliberately ignored: every cow now uses
the unified instinct.

## Save data

- Default: `~/.the_tamworth_chase/save.json`
- Override: `TAMWORTH_CHASE_DATA`
- The pre-rename environment variable is still read for compatibility.
- On first launch after the rename, the old save is copied to the new location
  and the old file is never deleted; a Chinese startup dialog reports this.
  A corrupt old save produces a message and a fresh save instead of a crash.
- The save is split into `settings`, `main`, `tutorial`, `achievements`,
  `challenges`, `daily` and `custom`. Writes are atomic.
- Save version 5 removes the old obstacle counters, adds the `alerts` setting
  and keeps turn records. Campaign records store `best_turns` and `rank`.

## Fonts and licensing

- `assets/fonts/CEFFontsCJK-Regular.ttf` — bundled CEF Fonts CJK under the SIL
  Open Font License 1.1; full text in `assets/fonts/OFL.txt`.
- The font is loaded locally at runtime.
- Digit runs use a system rounded font (SF Rounded, Avenir Next, Helvetica Neue,
  DejaVu Sans, Arial) because CEF's `1` resembles a slash; Chinese and Latin keep
  the handwritten face. Missing fonts fall back to system CJK faces.

## Art and audio

- Terrain, fences, ponds, cows, the farmer, gates, hay bales and alert bubbles
  are procedural. Tiles are drawn at a higher resolution and smoothed down.
- No bitmap sprite sheets and no emoji game objects.
- All sounds are synthesised at start-up in `game/audio.py`; no audio files are
  shipped. Sound and volume can be changed in Settings.

## Offline promise

- No network modules and no network requests at runtime.
- No accounts, rooms, matchmaking, servers, WebSockets, cloud saves or online
  leaderboards.
- The only binary asset is the bundled font.
- Daily seeds come from the local date.

## Tests

```bash
.venv/bin/python -m pytest -q
```

The suite covers absolute-turn actions, same-direction invalidity, blocked
moves, strict farmer-then-cow order, cow sight and range, unified flee priority,
exit seeking, exit/flee tiebreaks, all-caught wins, any-exit losses, multi-cow
order and blocking, loop hints, prediction assumptions and exit marks,
undo/restart, legacy level fields, save migration, tutorial practice gates and
isolation, editor round-trips, achievements, daily determinism, offline scanning
and every scene's head-less render.

Reference solutions live in `tests/solutions.json`,
`tests/challenge_solutions.json` and `tests/tutorial_solutions.json`. The
offline solver can regenerate a route:

```bash
.venv/bin/python tools/solve.py levels/levels.json
```

## Project layout

```
main.py                     Entry point
game/
  models.py                 Head-less models: Action, Level, TickResult
  core.py                   Absolute steering, cow AI, exits, undo, prediction
  levels.py                 Schema parsing, validation, serialisation
  tutorial.py               Tutorial catalogue, progress state machine, hints
  progress.py               Save sections and migrations
  achievements.py           Achievement rules
  editor.py                 Editor model and JSON exchange
  daily.py                  Local daily seed + bounded solver
  animation.py              One-turn interpolation
  render.py                 Board, gates, alerts, prediction, effects
  theme.py                  Palette, fonts, layout
  ui.py                     Buttons, toggles, modals
  art.py                    Procedural art
  audio.py                  Synthesised cues
  app.py                    Window and scene routing
  scenes/                   Menu, levels, play, tutorials, challenge, daily,
                            editor, achievements, settings
levels/                     Campaign and challenge JSON
tutorials/                  Three tutorial chapters
assets/fonts/               Bundled CJK font and OFL text
tests/                      Unit, integration and data tests
tools/                      Solver, tutorial builder, screenshot helper
```

`custom_levels/` and the save directory are not tracked by Git.

## Design notes and assumptions

- **All cows must be caught; any exit loses.** This is implemented literally for
  single- and multi-cow levels.
- **Turn limit** is a budget: reaching `max_turns` without a win fails. A
  winning action on that same turn is checked first and is accepted.
- **Same-direction turns** are invalid and free. This is the only way to avoid
  changing the board without moving, and it keeps the rule that every valid turn
  changes the state.
- **Exit line of sight** follows the strict definition: same row or column only.
  A diagonal exit is not visible; the cow patrols instead.
- **Caught cows leave the board.** Their positions remain in the snapshot for
  undo, but they are skipped by movement, sight, exit and rendering.
- **Unified cow instinct.** `cow_behavior` is gone; every cow flees first when
  it sees the farmer and seeks the exit otherwise.
- **Fixed terrain** comes from the grid plus optional `walls` and `obstacles`
  coordinates. `walls` are folded into the grid; `obstacles` are fixed hay bales.
- **Prediction** covers the cows only, with the farmer fixed. It does not show
  “what each candidate farmer action would cause”; that optional advanced view
  was not implemented.
- **Practice gates** are tutorial-only and never apply to campaign levels.

## Known limitations

- The GUI is verified head-less with screenshots and injected events; it has not
  been manually play-tested on a physical display here.
- Audio is synthesised and runs with a dummy device; it has not been auditioned.
- The editor uses a fixed level name and a 10×10 canvas.
- The daily generator falls back to campaign level 1 if no candidate is solvable.
- Undo keeps at most 256 snapshots.
- A cow trapped in a corner with another cow directly ahead may alternate its
  turn direction. The shipped levels do not use that combination; the behaviour
  is deterministic rather than random.
- Large levels are limited to the editor's 10×10 canvas; the parser itself is
  not limited to 10×10.
