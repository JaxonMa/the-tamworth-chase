# The Tamworth Chase

*A cozy, hand-drawn chase through the meadow — now with tank steering and a gate to guard.*

Farmer John drives like a tank: forward, turn left, turn right or wait. The cows
have their own plan: they walk toward the golden exit, and some of them will run
away when they see the farmer. Catch every cow before any cow escapes through
the gate.

The whole game is offline. No accounts, no servers, no telemetry, no network
requests while it runs.

## Rename note

The project was previously released as **The Tamworth Two**. Starting with this
version the name is **The Tamworth Chase** (Chinese subtitle 《塔姆沃斯追逐》).
The save file lives at `~/.the_tamworth_chase/save.json`; an old save is migrated
automatically on first launch and is never deleted.

## Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Running](#running)
5. [Controls](#controls)
6. [Rules](#rules)
7. [Cows](#cows)
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

- **Pure driving.** Move Farmer John forward or turn in place; there is no
  placement phase and no player-placed obstacle.
- **Escape pressure.** Every level has golden exit cells. A cow that reaches any
  exit loses the run immediately.
- **Two cow behaviours.** `seek_exit` walks toward the exit and patrols when it
  cannot see one. `seek_exit_and_flee` first tries to increase its distance from
  the farmer when he is in sight.
- **All cows or nothing.** Every cow must be caught; one cow reaching the exit
  is enough to fail.
- **Multi-level undo.** Undo any turn, back to the opening position, including
  the farmer's facing, every cow's pose, caught flags and turn count.
- **Configurable preview.** Each level chooses how many cow steps to show
  (0–20, default 5). The preview assumes the farmer keeps his current position
  and facing, and the UI says so in Chinese.
- **Exit warnings.** Exits are drawn as wooden gates; when a cow is within three
  tiles the exit is highlighted and a Chinese warning appears.
- **Alert icons.** Fleeing cows display a small exclamation mark; the icons can
  be toggled in the top bar or Settings.
- **Independent tutorials.** 6 basic, 3 advanced and 3 editor lessons with their
  own progress, skip/replay/reset and practice gates.
- **Challenge and daily modes.** Five curated challenges and a local daily
  meadow generated from the date and verified solvable on the device.
- **Level editor.** Paint terrain, place the farmer and up to three cows, set
  exits, behaviours, sight ranges and turn budgets, test-play, export/import.
- **Procedural picture-book art.** Grass, fences, hedges, ponds, cows, farmer,
  gates and alert bubbles are drawn in code. No emoji are used for game objects.

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
comments and docstrings are English.

## Controls

| Input | Action |
|---|---|
| `W` / `↑` | Drive forward one tile |
| `A` / `←` | Turn left 90° in place |
| `D` / `→` | Turn right 90° in place |
| Space | Wait in place |
| `U` | Undo one turn |
| `R` | Restart the level |
| `P` | Toggle the path preview |
| `Esc` | Return to the previous screen |

The top bar also has **撤销**, **重开**, **预测** and **警觉** buttons. There is
no pause, single-step or speed control: the turn-based player sets the pace.

## Rules

### State machine

```
playing ⇄ undo / restart → win / loss
```

There is no placement phase. A level starts immediately in the playing state.
The result dialog offers **撤销到上一回合**, **重开本关** and **返回**.

### One turn

1. The player performs exactly one action: forward, turn left, turn right or
   wait.
2. Forward moves one tile in the current facing. If a wall, the board edge or a
   fixed obstacle blocks the tile, the position and facing stay unchanged, the
   turn is still consumed, and the game shows **前方受阻，本回合已消耗**.
3. If the farmer enters a cow's tile, that cow is caught.
4. If every cow is caught, the level is won immediately.
5. Every cow moves once, in level order.
6. After each cow move, arriving at an exit fails the run; sharing the farmer's
   tile catches that cow.
7. After all cows, all caught means victory; otherwise the turn counter
   increases. Reaching the level's turn budget without a win fails the run.

## Cows

### `seek_exit` (default)

- If an exit is in the cow's straight-line sight — same row or column, no wall,
  fixed obstacle or board edge between, within `exit_sight_range` — the cow
  turns toward it (or walks forward if already facing it).
- If several exits are visible, the nearest is chosen; ties are broken by
  `(row, column)`.
- If no exit is visible, the cow patrols: walk forward when possible, otherwise
  turn 90° clockwise and stay in place.

### `seek_exit_and_flee`

- If Farmer John is in sight, fleeing takes priority over the exit.
- Sight means same row or column, no terrain blocking, and a distance within
  `sight_range` (`-1` is unlimited). With `cows_block_sight`, another cow between
  them also blocks sight.
- The cow walks forward if that increases its Manhattan distance from the
  farmer. Otherwise it turns toward the side whose forward tile is farther from
  the farmer; ties use `flee_tiebreak`.
- If the farmer is not in sight, the cow uses the normal exit-seeking behaviour.

Cows never react to the farmer except through the flee rule. A cow caught by
entering the farmer's tile stops moving; caught cows are removed from the board
and do not block sight or movement.

## Winning and losing

- **Win:** all cows are caught. Single-cow levels require that cow; multi-cow
  levels require every cow.
- **Lose — escape:** any cow reaches any exit cell.
- **Lose — turns:** the turn counter reaches `max_turns` without a win.
- A winning move on the last allowed turn is still accepted.
- The failure dialog distinguishes **牛从出口逃走了** from **回合数用完了**.

## Prediction, alerts and loops

The preview shows up to `prediction_steps` future cow poses while Farmer John
stays at his current position and facing. It is drawn as translucent footprints
and dashed paths, with a Chinese caption stating the assumption. If a predicted
cow reaches an exit, the final point is marked in red. `0` disables the preview
for that level.

The top bar's **警觉** button toggles the alert icons above fleeing cows; the
same option is available in Settings.

If the complete pose — farmer position/facing, every cow position/facing and
caught flags — repeats, a Chinese **局面进入循环** hint appears. It never loses
the run. A chime and a toast are informational only.

## Campaign and ranks

- Ten 10×10 campaign levels. Clearing one unlocks the next; the first is always
  available.
- The best turn count and S/A/B/C rank are stored per level. Grades use the
  level's `s_threshold`, `a_threshold` and `b_threshold`.
- Levels 6, 7, 8 and 10 use fleeing cows. Levels 8 and 10 have two cows; level 9
  has `prediction_steps: 0`.
- Exits are part of the fixed terrain and are visible in the level cards.

## Tutorial chapters

| Chapter | File | Lessons | Focus |
|---|---|---|---|
| 基础教程 | `tutorials/basics.json` | 6 | drive, turn, wall bumps, exits, blocking lines, interception, undo + preview |
| 进阶教程 | `tutorials/advanced.json` | 3 | fleeing cows, two cows, mixed behaviour |
| 编辑器教程 | `tutorials/editor.json` | 3 | terrain, exits/behaviour, export/import |

- Each chapter has its own entry, progress, lesson list, skip and reset.
- Lessons unlock in order and can be replayed; skipping a lesson or chapter
  never touches the campaign.
- Practice gates: some lessons only complete after the required action — turn
  both ways, bump a wall forward, wait, open the preview or undo once. The
  practice is written in the tutorial box.
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
- Set an exit tool; click walkable cells to add/remove exits. At least one exit
  is required.
- Toggle fixed hay-bale obstacles.
- Edit `max_turns`, `prediction_steps`, `sight_range` and `exit_sight_range`.
- Cycle the active cow's behaviour, the exit/flee tiebreaks, and the
  `cows_block_sight` / `cows_block_each_other` flags.
- Test-play with the real simulation, then export to `custom_levels/` as JSON.
  Import reads the first level from a bundle.
- The level name is currently fixed to “我的牧场”; there is no text input.

## Level data schema

```json
{
  "id": "level_01",
  "name": "晨露草坪",
  "grid": ["##########", "#........#", "..."],
  "fj_start_direction": "north",
  "cow_facings": ["east"],
  "cow_behavior": "seek_exit",
  "exit_cells": [[1, 1]],
  "max_turns": 16,
  "prediction_steps": 5,
  "exit_sight_range": -1,
  "sight_range": 6,
  "exit_tiebreak": "right",
  "flee_tiebreak": "right",
  "cows_block_sight": false,
  "cows_block_each_other": false,
  "obstacles": [],
  "hint": "把农夫开到牛和出口之间；撞墙前进会浪费回合。",
  "goal": "抓住全部牛"
}
```

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | required | Unique level id |
| `name` | string | id | Chinese display name |
| `grid` | string[] | required | Terrain rows; `F` farmer, `C` cows |
| `fj_start_direction` | string | `north` | Farmer's initial facing (`up/right/down/left` accepted) |
| `cow_facings` | string[] | `east` | One facing per cow |
| `cow_behavior` | string or string[] | `seek_exit` | One value for all cows or one per cow |
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
`initial_obstacles`, `win_condition`, `pen_cells`, `cow_personalities`, item
fields and `speed`/`pause` are ignored; `step_limit` is used as a fallback for
`max_turns`. If no exit is supplied, a deterministic far-away walkable cell is
chosen and marked as a legacy default; old custom levels still load.

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

The suite covers tank movement and blocked moves, strict farmer-then-cow order,
cow sight and range, exit seeking, fleeing priority and tiebreaks, all-caught
wins, any-exit losses, multi-cow order and blocking, loop hints, prediction
assumptions and exit marks, undo/restart, legacy level fields, the save
migration, tutorial practice gates and isolation, editor round-trips, achievements,
daily determinism, offline scanning and every scene's head-less render.

## Project layout

```
main.py                     Entry point
game/
  models.py                 Head-less models: Action, CowBehavior, Level, TickResult
  core.py                   Tank turns, cow AI, exits, undo, prediction
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
- **Turn limit** is treated as a budget: reaching `max_turns` without a win
  fails. Winning on that same turn is checked first and is accepted.
- **Exit line of sight** follows the spec strictly: same row or column only.
  A diagonal exit is therefore not “visible”; the cow patrols instead. The
  parenthetical about a diagonal exit is unreachable under this definition.
- **Caught cows leave the board.** Their positions are kept in the snapshot for
  undo, but they are skipped by movement, sight, exit and rendering.
- **`cow_behavior`** accepts a single string (all cows) or a list (one per cow),
  which allows mixed-behaviour levels.
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
- Large levels are limited to the editor's 10×10 canvas; the parser itself is
  not limited to 10×10.
