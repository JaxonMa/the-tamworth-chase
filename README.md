# The Tamworth Chase

*A cozy, hand-drawn chase through the meadow — steer the farmer, guard the gate.*

Farmer John drives with absolute-direction steering: every command turns him to
face up, down, left or right, or moves him one tile forward. Cows always keep the
exit in mind: they flee when the farmer is in sight, but fleeing is only a
temporary detour — when no escape move is useful they fall back to the exit.
Catch every cow before any cow escapes.

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
9. [Show solution playback](#show-solution-playback)
10. [Progressive main campaign](#progressive-main-campaign)
11. [Prediction, alerts and loops](#prediction-alerts-and-loops)
12. [Challenge, daily and achievements](#challenge-daily-and-achievements)
13. [Level editor and solver](#level-editor-and-solver)
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

- **Pure driving.** No placement phase and no player-placed obstacle. A level
  starts immediately; every turn the player turns or moves.
- **Mirrored play layout.** Level guidance and teaching hints live in the left
  sidebar; the board, turn/cow stats and action buttons are on the right.
- **Absolute steering.** `W`/`↑` faces up, `S`/`↓` faces down, `A`/`←` faces
  left, `D`/`→` faces right, and Space moves one tile in the current direction.
  The direction matching the current facing is invalid and free.
- **No waiting.** Every valid turn changes the facing or moves the farmer.
- **Exit-first cow AI.** Cows seek the exit; seeing the farmer triggers a
  temporary flee. If no escape move actually increases the distance, the cow
  immediately falls back to seeking the exit instead of spinning in a corner.
- **Farmer cannot use exits.** Exit gates are passable for cows only. The farmer
  cannot enter or occupy an exit; trying to move onto one consumes the turn and
  shows **出口不可通行，本回合已消耗**. This prevents blocking the exit by
  standing on it.
- **Escape pressure.** A cow reaching any exit loses the run immediately.
- **All cows or nothing.** Every cow must be caught.
- **Multi-level undo.** Undo back to the opening position, including facing,
  every cow's pose, caught flags and turn count.
- **Show solution after a failure.** The failure dialog can replay a shortest
  winning route with pause/continue and exit controls; it never counts as a
  player clear.
- **Configurable preview.** Each level chooses how many cow steps to show
  (0–20, default 5), assuming the farmer keeps his current position and facing.
- **Progressive teaching in the campaign.** The main campaign itself teaches
  the mechanics. There is no separate tutorial entry, chapter picker or tutorial
  save section.
- **Teaching objectives never gate progress.** `learning_objective` is shown as
  guidance; clearing a level by any valid route unlocks the next one.
- **Challenge and daily modes.** Five curated challenges and a local daily
  meadow generated from the date and verified with the shared solver.
- **Level editor.** Paint terrain, place the farmer and up to three cows, set
  exits, fixed obstacles, sight ranges and turn budgets, test-play, export and
  import JSON. Export is checked by the shared solver first.
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
does not consume a turn. The right-hand toolbar labels its shortcuts directly
on the buttons: **`[U] 撤销`**, **`[R] 重开`**, **`[P] 预测 开/关`**, plus
**警觉**. The left sidebar shows the level objective, a short description, the
goal and the current teaching card. Teaching hints can be switched off in
Settings. There is no wait command and no player-controlled gameplay pause,
single-step or speed control. The only pause is the optional pause inside
solution playback.

## Rules

### State machine

```
playing ⇄ undo / restart → win / loss
```

There is no placement phase. A failure dialog offers **撤销到上一回合**,
**显示解法**, **重开本关** and **返回**; the solution button is covered below.

### One turn

1. The player performs exactly one action: face up/down/left/right, or move
   forward.
2. A turn to a different direction changes the facing, keeps the position and
   consumes the turn. A turn to the current facing is invalid and costs nothing.
3. Forward moves one tile in the current facing:
   - A fence, board edge or fixed obstacle blocks the move; the turn is consumed
     and **前方受阻，本回合已消耗** is shown.
   - An exit cell blocks the farmer; the turn is consumed and
     **出口不可通行，本回合已消耗** is shown.
   - A cow in the destination is caught.
4. If every cow is caught, the level is won immediately.
5. Every cow moves once, in level order. After each cow move, reaching an exit
   fails the run; sharing the farmer's tile catches that cow.
6. After all cows, all caught means victory; otherwise the turn counter
   increases. Reaching the level's turn budget without a win fails the run.

A winning move on the last allowed turn is checked before the budget and is
accepted. Level loading rejects an initial farmer position on an exit.

## The cows

All cows use the same decision order.

### 1. Can the cow see the farmer?

Sight means:

- same row or same column;
- no wall, fixed obstacle or board edge between the two;
- Manhattan distance within `sight_range` (`-1` means unlimited);
- optionally, other cows block sight when `cows_block_sight` is true.

### 2. Attempt a temporary flee

- If the forward tile is passable and moving there strictly increases the
  Manhattan distance to the farmer, the cow moves forward.
- Otherwise it considers left/right turns. A side is an escape option only when
  its forward cell is passable and its distance is strictly larger.
- If at least one side is an escape option, the cow turns toward the farther
  passable side. Ties use `flee_tiebreak` (default `right`).
- If neither side is a useful escape, the cow does **not** turn in place. It
  immediately falls through to the exit logic. This is the fix for cows that
  used to spin in corners while the farmer was visible.

### 3. Seek the exit

- A visible exit is in the cow's straight line (same row or column), no terrain
  blocks it, and its distance is within `exit_sight_range` (`-1` unlimited).
- If several exits are visible, the nearest wins; ties use `(row, column)` order.
- If the cow already faces the chosen exit and the forward tile is passable, it
  moves forward. Otherwise it turns toward the exit; if the exit is directly
  behind, `exit_tiebreak` (default `right`) chooses the first 90° turn.
- If no exit is visible, it patrols: move forward when possible; otherwise turn
  90° clockwise in place.
- If every adjacent cell is blocked, the cow holds still instead of rotating
  forever. Shipped levels avoid this state; it is a defensive fallback.

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
- **Teaching objectives are never win conditions.** They only drive hints and
  the post-level summary. Any valid win unlocks the next level.

## Show solution playback

A failed attempt can be inspected with **显示解法** in the failure dialog.

- The button asks the shared `game.solver` for a shortest win **from the level's
  opening state**, using the real `Simulation`; no second rule implementation
  is involved.
- Playback opens a separate simulation. The failed run object and its undo
  history are left untouched, so progress, achievements and best times are not
  changed by the computer's moves.
- The board stays visible. The right-hand toolbar shows **暂停 / 继续**, **退出演示**, and
  the current step count. The panel explains that the playback is not scored.
  Tutorial hints and the normal action buttons are hidden during playback.
- Player actions, restart shortcuts and the back button are ignored while the
  computer is driving. Only the two playback controls respond.
- After the final action the win is held briefly, then the original failed state
  is restored. A dedicated **演示结束** dialog appears instead of the earlier
  failure dialog; it offers **再次演示**, **重开**, **撤销到上一回合** and
  **返回**. **退出演示** restores the failed state immediately and opens the
  same end dialog. Undo, restart and another playback are available again.
- The search is synchronous and bounded by `DEMO_MAX_NODES` (100,000) and
  `DEMO_MAX_SECONDS` (3.0). If it exhausts the state space or reaches a limit,
  the dialog stays open and shows **暂时无法给出解法**; the other buttons keep
  working.
- Solved and exhausted results are cached in
  `game.solver.solve_level_cached`, keyed by `RULES_VERSION` plus the level's
  rule-relevant data and search limits. A rule change or a changed level
  calculates a fresh route. Resource-limited attempts are not cached, so the
  player can retry a transient timeout.
- The playback pace is fixed at 0.46 seconds per action plus the normal 0.2 s
  movement animation. There is no speed slider.

## Progressive main campaign

The ten main levels are a single learning sequence:

| # | Level | Teaching focus | Cows | Max | Shortest |
|---|---|---|---:|---:|---:|
| 01 | 朝哪走 | absolute turns and forward | 1 | 14 | 6 |
| 02 | 撞墙的代价 | a blocked forward wastes a turn | 1 | 18 | 9 |
| 03 | 出口在哪 | cows seek the exit | 1 | 12 | 4 |
| 04 | 警觉的牛 | fleeing and falling back to the exit | 1 | 12 | 7 |
| 05 | 出口不可通行 | exits block the farmer | 1 | 14 | 7 |
| 06 | 墙后的伏击 | terrain blocks sight | 1 | 10 | 4 |
| 07 | 出口前的拦截 | intercept before the exit | 1 | 9 | 4 |
| 08 | 预判与撤销 | prediction and undo | 1 | 14 | 6 |
| 09 | 苔藓高地 | multiple cows | 2 | 27 | 19 |
| 10 | 最后的牧场 | multiple cows and exit pressure | 2 | 33 | 25 |

- Levels 1–8 are teaching levels; 9–10 combine the mechanics.
- Each level has a Chinese `learning_objective` and a list of `hint_text`
  prompts. The objective and description appear in the left sidebar; the current
  hint appears in a high-contrast card in the lower sidebar (the old rules slot),
  with a page count, **下一条** button and progress dots. The card advances
  automatically after 9 seconds or manually through the button.
- Completion unlocks the next level regardless of which mechanics were used.
  There are no practice gates and no separate tutorial progress.
- Teaching levels hide the S/A/B/C badge in the victory dialog; the internal
  turn thresholds are kept for data compatibility but never block progress.
- Clearing a level by another route always counts as a normal clear.

## Prediction, alerts and loops

The preview shows up to `prediction_steps` future cow poses while Farmer John
stays at his current position and facing. It is drawn as translucent footprints
and dashed paths, with a Chinese caption explaining the assumption. A predicted
cow reaching an exit is marked in red. `0` disables the preview for that level.

The right-hand toolbar's **警觉** button toggles alert icons above fleeing cows;
Settings also has a **显示教学目标与提示** switch for teaching guidance. The
prediction caption sits below the right-hand board. During solution playback the
preview is hidden so the replay stays easy to read.

If the complete pose — farmer position/facing, every cow position/facing and
caught flags — repeats, a Chinese **局面进入循环** hint appears. It never loses
the run; the player can continue and break the loop.

## Challenge, daily and achievements

- **Challenge:** five curated side levels with local best turns.
- **Daily:** a meadow generated from the local date, checked with the shared
  solver; falls back to campaign level 1 only if no candidate is winnable.
- **Achievements:** `one_step`, `close_call`, `flawless`, `loop_free`,
  `all_levels`.
  - `one_step`: catch all cows in one turn.
  - `close_call`: win on the last allowed turn.
  - `flawless`: never bump a wall while moving forward.
  - `loop_free`: never trigger the loop hint.
  - `all_levels`: clear all ten campaign levels.

## Level editor and solver

- Paint grass, fence, hedge, tree or pond.
- Place the farmer, move/add/remove up to three cows, and choose the active cow.
- Use the exit tool to add/remove exits. Exits cannot hold the farmer, a cow or
  a fixed obstacle.
- Toggle fixed hay-bale obstacles.
- Edit `max_turns`, `prediction_steps`, `sight_range` and `exit_sight_range`.
- Cycle cow facing, exit/flee tiebreaks, `cows_block_sight` and
  `cows_block_each_other`. Cow behaviour is always unified.
- **Export validation:** before writing, the editor calls the same
  `game.solver.solve_level` used by tests and playback. An exhausted search
  rejects the export with a Chinese explanation. A search limit opens a dialog:
  cancel, or export as **unverified**. Verified exports include
  `verification: {status, shortest_turns}`; unverified files are marked and the
  import screen warns about them.
- **Playback versus export:** the editor uses a fresh bounded search for export
  validation; the failure dialog uses the cached playback entry point. Both call
  the same BFS over `Simulation`.
- Import reads the first level from a bundle. The editor level name is fixed to
  “我的牧场”; there is no text input.

## Level data schema

```json
{
  "version": 5,
  "game": "The Tamworth Chase",
  "levels": [
    {
      "id": "level_01",
      "name": "朝哪走",
      "grid": ["#######", "#.....#", "..."],
      "fj_start_direction": "north",
      "cow_facings": ["east"],
      "exit_cells": [[1, 1]],
      "max_turns": 14,
      "prediction_steps": 5,
      "exit_sight_range": -1,
      "sight_range": -1,
      "exit_tiebreak": "right",
      "flee_tiebreak": "right",
      "cows_block_sight": false,
      "cows_block_each_other": false,
      "walls": [],
      "obstacles": [],
      "chapter": "基础驾驶",
      "learning_objective": "转向与前进：每回合必须转向或前进",
      "hint_text": ["W/↑ 朝上，S/↓ 朝下…", "空格前进…"],
      "hint": "先转向，再前进。",
      "description": "七节短课的第一课。"
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
| `exit_cells` | `[row,col][]` | required | At least one walkable exit; rejected if it overlaps a wall, fixed obstacle or the farmer |
| `max_turns` | int | 30 | Turn budget |
| `prediction_steps` | int | 5 | Preview depth; 0 disables |
| `exit_sight_range` | int | -1 | Exit visibility range; -1 unlimited |
| `sight_range` | int | -1 | Farmer visibility range; -1 unlimited |
| `exit_tiebreak` / `flee_tiebreak` | `right` / `left` | `right` | Tie-breaking side |
| `cows_block_sight` | bool | false | Cows block the farmer's line of sight |
| `cows_block_each_other` | bool | false | Cows block each other's movement |
| `walls` | `[row,col][]` | `[]` | Optional extra fence coordinates folded into the grid |
| `obstacles` | `[row,col][]` | `[]` | Optional fixed hay-bale blockers |
| `chapter` | string | group | Level-select chapter label |
| `learning_objective` | string | `""` | Chinese teaching text; empty for ordinary levels |
| `hint_text` | string or string[] | `[]` | Progressive Chinese hints |
| `s/a/b_threshold` | int | derived | Grade thresholds in turns |
| `hint` / `description` | string | `""` | Chinese UI text |
| `verification` | object | absent | Editor-export solver metadata |

Grid characters: `.` grass, `,` flowers, `#` fence, `T` tree, `~` pond,
`H` hedge, `F` farmer, `C` cow. Legacy `D/G/S` cow characters are read as normal
cows. A cow may not start on an exit; the farmer may never start on an exit.

**Backward compatibility.** Old fields `step_limit`, `obstacle_limit`,
`initial_obstacles`, `win_condition`, `pen_cells`, `cow_behavior`,
`cow_personalities`, item fields, tutorial `tips`/`practice`, and
`speed`/`pause` are ignored; `step_limit` falls back to `max_turns`. If no exit
is supplied, a deterministic far-away walkable cell is chosen and marked in
`extra["legacy_exit"]`; old custom levels still load.

## Save data

- Default: `~/.the_tamworth_chase/save.json`
- Override: `TAMWORTH_CHASE_DATA`
- The pre-rename environment variable is still read for compatibility.
- On first launch after the rename, the old save is copied to the new location
  and the old file is never deleted; a Chinese startup dialog reports this.
- Save version **6** removes the independent `tutorial` section. Known completed
  old tutorial lessons are mapped onto the corresponding main levels
  (`basics_01`→`level_01`, …, `advanced_03`→`level_10`); unmapped or skipped
  old tutorial records are ignored. Main records gain `cleared` so the normal
  unlock chain continues.
- Sections: `settings`, `main`, `achievements`, `challenges`, `daily`,
  `custom`. Writes are atomic. The `hints` setting defaults to true.

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

Coverage includes absolute-turn actions, same-direction invalidity, blocked
moves, exit-blocked moves, initial-position validation, strict farmer-then-cow
order, cow sight and range, unified flee priority, flee-to-exit fallback,
boxed-in cows, exit seeking, exit/flee tiebreaks, all-caught wins, any-exit
losses, multi-cow order and blocking, loop hints, prediction assumptions and
exit marks, undo/restart, legacy fields, save version 6 migration, teaching
objectives not gating clears, the mirrored play layout, dynamic board centering,
key-labelled toolbar buttons, the sidebar teaching card and its next control,
editor solver export checks, achievements, daily determinism, offline scanning
and every scene's head-less render. Playback tests
cover the failure-dialog button, ignored player input, pause/resume, early exit,
automatic restore, the dedicated **演示结束** dialog, replay/restart from that
dialog, no-solution notices, time limits and cache invalidation.

Reference solutions live in `tests/solutions.json` and
`tests/challenge_solutions.json`. The shared solver also powers the editor:

```bash
.venv/bin/python tools/solve.py levels/levels.json
```

## Project layout

```
main.py                     Entry point
game/
  models.py                 Head-less models: Action, Level, TickResult
  core.py                   Absolute steering, cow AI, exits, undo, prediction
  solver.py                 Shared bounded BFS, limits and playback cache
  levels.py                 Schema parsing, validation, serialisation
  progress.py               Save sections, v6 tutorial merge
  achievements.py           Achievement rules
  editor.py                 Editor model and JSON exchange
  daily.py                  Local daily seed + shared solver check
  animation.py              One-turn interpolation
  render.py                 Board, gates, alerts, prediction, effects
  theme.py                  Palette, fonts, layout
  ui.py                     Buttons, toggles, modals
  art.py                    Procedural art
  audio.py                  Synthesised cues
  app.py                    Window and scene routing
  scenes/                   Menu, levels, play, challenge, daily, editor,
                            achievements, settings
levels/                     Campaign and challenge JSON
assets/fonts/               Bundled CJK font and OFL text
tests/                      Unit, integration and data tests
tools/                      Solver CLI and screenshot helper
```

`custom_levels/` and the save directory are not tracked by Git.

## Design notes and assumptions

- **All cows must be caught; any exit loses.** Implemented literally for single-
  and multi-cow levels.
- **Turn limit** is a budget: reaching `max_turns` without a win fails. A
  winning action on that same turn is checked first and is accepted.
- **Same-direction turns** are invalid and free.
- **Fleeing is temporary.** If neither forward nor either passable side can
  increase the distance, the cow does not turn in place; it immediately seeks
  the exit. If all adjacent cells are blocked, it holds still.
- **Exit cells are cow-only.** The farmer's walkability check excludes exits;
  the parser rejects an initial farmer/exit overlap. Cows can enter an exit and
  immediately lose the run. This avoids trying to block a gate by standing on it.
- **Exit line of sight** is strict: same row or column only.
- **Caught cows leave the board.** Their positions remain in the undo snapshot
  but are skipped by movement, sight, exit and rendering.
- **Teaching objectives** are hints only. They never affect victory, ranking or
  unlocking; only the normal win condition does.
- **The play screen is mirrored, not every scene.** The editor keeps its board on
  the left and its tool panel on the right.
- **The old rules card is gone.** The turn limit stays in the compact top stats,
  the prediction step count stays in the caption below the board, and the
  one-line exit reminder remains in the sidebar. Shortcuts are printed on the
  toolbar and footer.
- **Teaching promotion rules:** levels with `hint_text` get a paged card; levels
  with only `hint` get a compact single-hint card; levels with neither leave the
  lower sidebar empty. Turning hints off hides the card.
- **Fixed terrain** is the grid plus optional `walls` and `obstacles`.
- **Prediction** covers cows only, with the farmer fixed. The optional
  “candidate farmer action” preview is not implemented.
- **Solver limits** are deterministic node caps plus an optional wall-clock
  limit. Exhausted search is `unsolvable`; reaching a cap is `limit`, which the
  editor treats as “unverified” and the failure dialog reports as
  **暂时无法给出解法**.
- **Solution playback is a teaching aid, not a skip.** It restores the failed
  state afterwards and never records a clear, best time or achievement.
- **Solution cache invalidation** uses `RULES_VERSION` and the rule-relevant
  level data (terrain, actors, exits, obstacles, turn budget, sight and
  tiebreaks), not the current attempt's position.
- **Playback searches synchronously** with a three-second cap. The worst shipped
  level currently takes about 1.4 s on the development machine; the interface
  briefly blocks while the search runs.
- **Fixed playback pace:** the action interval is deliberately constant; a
  speed control is future work.

## Known limitations

- The GUI is verified head-less with screenshots and injected events; it has not
  been manually play-tested on a physical display here.
- Audio is synthesised and runs with a dummy device; it has not been auditioned.
- The editor uses a fixed level name and a 10×10 canvas.
- The daily generator falls back to campaign level 1 if no candidate is solvable.
- Undo keeps at most 256 snapshots.
- Challenge levels are intentionally tighter than the main teaching levels; two
  have a shortest solution equal to their turn budget.
- A fully boxed-in cow holds still, which is a safe fallback but not an
  interesting puzzle state; shipped levels avoid it.
- Large levels are limited to the editor's 10×10 canvas; the parser itself is
  not limited to 10×10.
- The solution search is synchronous, so a difficult custom level can pause the
  interface for up to three seconds before reporting **暂时无法给出解法**.
- Solution playback has a fixed pace and no step-by-step or speed controls.
