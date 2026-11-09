# The Tamworth Chase

English · [Simplified Chinese](README.md)

*A cozy, hand-drawn chase through the meadow: drive the farmer, guard the gate.*

The game uses absolute-direction steering. On each turn, Farmer John either turns
to face up, down, left or right, or moves one tile forward in the direction he is
facing. Cows head for the exits. They dodge the farmer when he comes into view,
but as soon as fleeing no longer increases the distance they head straight back
to an exit. Catch every cow before one escapes.

The Tamworth Chase is a single-player, turn-based puzzle game. It runs fully
offline: there are no accounts, servers or telemetry, and the game makes no
network requests at runtime.

## Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Running](#running)
5. [Controls](#controls)
6. [Rules](#rules)
7. [Cow behaviour](#cow-behaviour)
8. [Winning and losing](#winning-and-losing)
9. [Solution playback](#solution-playback)
10. [Campaign teaching](#campaign-teaching)
11. [Prediction, alerts and loops](#prediction-alerts-and-loops)
12. [Challenge, daily and achievements](#challenge-daily-and-achievements)
13. [Editor and solver](#editor-and-solver)
14. [Level data format](#level-data-format)
15. [Save data](#save-data)
16. [Fonts and licensing](#fonts-and-licensing)
17. [Art and audio](#art-and-audio)
18. [Offline promise](#offline-promise)
19. [Tests](#tests)
20. [Project layout](#project-layout)
21. [Design notes](#design-notes)
22. [Known limitations](#known-limitations)
23. [License](#license)

## Features

- **Pure driving.** There is no placement phase, the player cannot place
  obstacles, and a level begins immediately.
- **Mirrored play layout.** The objective and teaching hints sit in the left
  sidebar; the board, turn and cow statistics, and action buttons sit on the
  right. The editor keeps its board on the left and its tools on the right.
- **Absolute steering.** `W`/`↑` faces up, `S`/`↓` faces down, `A`/`←` faces
  left, `D`/`→` faces right, and Space moves one tile in the current direction.
  Turning to the direction already faced is invalid and costs no turn.
- **No waiting.** Every valid turn either turns the farmer or moves him forward.
- **Cows head for the exits.** A cow flees when it sees the farmer, but if
  neither moving forward nor turning left or right increases the distance, it
  returns to seeking the exit instead of spinning in a corner.
- **The farmer cannot use exits.** Exits are passable for cows only; Farmer John
  cannot enter or remain on an exit tile. Trying to move into one spends the turn
  and shows a short exit-blocked message. This prevents the player from blocking
  a gate by standing on it.
- **One escape ends the run.** If any cow reaches any exit, the run is lost.
- **Every cow must be caught.**
- **Multi-step undo.** Undo restores the farmer's position and facing, every
  cow's position and facing, all caught flags, and the turn count.
- **Solution playback after a failure.** The failure dialog can play a shortest
  winning route with pause, continue and exit controls. Playback never counts as
  a player clear.
- **Adjustable prediction.** Each level chooses how many cow steps to preview
  (0–20, default 5), assuming the farmer keeps his current position and facing.
- **Teaching built into the campaign.** There is no separate tutorial entry,
  chapter picker or tutorial save section; the first eight campaign levels teach
  the mechanics.
- **Teaching objectives never gate progress.** `learning_objective` is used for
  guidance and the post-level summary only. Any valid clear unlocks the next
  level.
- **Challenges, daily runs and achievements.** Five curated challenge levels, a
  daily meadow generated from the local date and verified by the shared solver,
  and five achievements.
- **Level editor.** Paint terrain, place the farmer and up to three cows, set
  exits, fixed obstacles, sight ranges and turn budgets, then test-play, export
  and import JSON. Export validation runs before a file is written.
- **Picture-book procedural art.** Grass, fences, hedges, ponds, cows, the
  farmer, exit gates and alert bubbles are all drawn in code. No emoji are used
  as game objects.
- **Background music.** A bundled CC0 solo-harp loop, “Meadow Thoughts” by
  Écrivain, plays quietly beneath the sound effects.

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

On Windows, use `.venv\Scripts\python.exe`.

## Running

```bash
.venv/bin/python main.py
```

The window is 1280×840. In-game copy is Simplified Chinese; code identifiers,
comments, docstrings and commit messages are English.

## Controls

| Input | Action |
|---|---|
| `W` / `↑` | Face up (no turn is spent if already facing up) |
| `S` / `↓` | Face down (no turn is spent if already facing down) |
| `A` / `←` | Face left (no turn is spent if already facing left) |
| `D` / `→` | Face right (no turn is spent if already facing right) |
| Space | Move one tile in the current direction |
| `U` | Undo one turn |
| `R` | Restart the level |
| `P` | Toggle the path preview |
| `Esc` | Return to the previous screen |

Pressing the direction already faced shows a short “already facing that way”
notice and costs no turn. The right toolbar prints shortcuts on the buttons:
`[U]` Undo, `[R]` Restart, `[P]` Preview on/off, plus Alerts. The left sidebar
shows the level objective, description, goal and current teaching card. Teaching
hints can be turned off in Settings.

There is no wait action and no player-controlled gameplay pause, single-step or
speed setting. The only pause occurs inside solution playback.

## Rules

### State machine

```
Playing <-> Undo / Restart -> Win / Loss
```

A level starts immediately; there is no placement phase. The failure dialog
offers four actions: undo to the previous turn, show a solution, restart the
level, and go back.

### One turn

1. The player performs exactly one action: face up, down, left or right, or move
   forward.
2. Turning to a different direction changes the facing and spends one turn. A
   turn to the current facing is invalid and costs nothing.
3. Moving forward:
   - A fence, board edge or fixed obstacle blocks the move. Position and facing
     stay unchanged, the turn is spent, and a short blocked-move message appears.
   - An exit tile blocks the farmer. Position and facing stay unchanged, the turn
     is spent, and a short exit-blocked message appears.
   - A cow in the destination tile is caught as the farmer enters it.
4. If every cow is caught after the farmer moves, the level is won immediately.
5. Every cow then moves once, in a fixed order. After each cow move, reaching an
   exit loses the run; sharing the farmer's tile catches that cow.
6. The turn counter then increases. If every cow is caught, the level is won;
   otherwise, reaching the level's turn limit loses the run.

A winning action on the final allowed turn is resolved before the limit and is
accepted. Loading a level rejects a farmer start position on an exit.

## Cow behaviour

All cows use the same decision order.

### 1. Can the cow see the farmer?

All of the following must be true:

- They share a row or a column.
- No wall, fixed obstacle or board edge lies between them.
- Their Manhattan distance is within `sight_range` (`-1` means unlimited).
- If `cows_block_sight` is true, other cows also block the line of sight.

### 2. Try a temporary escape

- If the forward tile is passable and moving there strictly increases the
  Manhattan distance to the farmer, the cow moves forward.
- Otherwise it considers turning left or right. A side is a valid escape only
  when its forward tile is passable and the resulting distance is strictly
  larger.
- If at least one side is a valid escape, the cow turns toward the side with the
  greater distance. Ties use `flee_tiebreak` (default `right`).
- If neither side offers a useful escape, the cow does not turn in place. It
  immediately falls through to the exit logic below. This is what prevents the
  old corner-spinning behaviour.

### 3. Seek the exit

- An exit is visible when it is in the cow's straight line, nothing blocks the
  path, and the distance is within `exit_sight_range` (`-1` means unlimited).
- If several exits are visible, the nearest one wins. Ties use row-then-column
  order.
- If the cow already faces the chosen exit and the forward tile is passable, it
  moves forward. Otherwise it turns toward the exit. When the exit is directly
  behind, `exit_tiebreak` (default `right`) decides which way the first 90-degree
  turn goes.
- If no exit is visible, the cow patrols along walls: move forward when possible;
  otherwise turn 90 degrees clockwise in place.
- If all four adjacent cells are blocked, the cow stays still instead of rotating
  forever. Shipped levels avoid this state; it is a defensive fallback.

### 4. Multiple cows and determinism

- Cows move in the order defined by the level, giving a fixed and deterministic
  result.
- When `cows_block_each_other` is true, another active cow blocks the forward
  tile. It is off by default.
- A caught cow is skipped by movement, sight, exit checks and rendering. Its
  position remains in the undo snapshot.

## Winning and losing

- **Win:** all cows are caught.
- **Lose:** any cow reaches any exit tile.
- **Lose:** the turn count reaches `max_turns` without a win.
- **Failure dialog:** it distinguishes an exit escape from running out of turns.
- **Teaching objectives are not win conditions.** Hints, solver analysis and the
  post-level summary may use them; wins, unlocks and ratings depend only on the
  normal win condition.

## Solution playback

After a failure, the player can choose the solution action in the failure dialog
to watch a computer-generated solution.

- The solver starts from the level's opening position and uses the real
  `Simulation` and shared BFS to find a shortest winning route. There is no
  second rule implementation.
- Playback uses a separate simulation. The failed position and its undo history
  stay untouched, so the computer's moves never affect clears, best turns or
  achievements.
- The board remains visible. The top-right area shows pause/resume, exit playback
  and the current step count. A caption explains that the playback is not scored;
  normal action buttons and teaching hints are hidden.
- Player input, restart shortcuts and the back button are ignored during
  playback. Only the two playback controls respond.
- After the final step, the game pauses briefly, restores the failed position,
  and shows a dedicated playback-finished dialog instead of the failure dialog.
  It offers replay, restart, undo to the previous turn, and back. Exiting playback
  immediately restores the failed position and opens the same dialog; undo,
  restart and replay remain available.
- The synchronous search is limited by `DEMO_MAX_NODES` (100,000) and
  `DEMO_MAX_SECONDS` (3.0). If the state space is exhausted or a limit is
  reached, the dialog stays open and reports that no solution is available right
  now; the other buttons remain usable.
- Solved and exhausted results are cached by
  `game.solver.solve_level_cached`. The cache key includes `RULES_VERSION`, the
  level's rule-relevant data and the search limits, so rule or level changes
  trigger a fresh search. Resource-limited attempts are not cached, allowing the
  player to retry.
- Playback uses a fixed 0.46-second interval per action, plus the normal
  0.2-second movement animation. There is no speed slider.

## Campaign teaching

The ten campaign levels form one continuous teaching sequence:

| # | Level | Teaching focus | Cows | Turn limit | Shortest |
|---|---|---|---:|---:|---:|
| 01 | Which Way? | absolute turns and forward movement | 1 | 14 | 6 |
| 02 | The Cost of a Wall | a blocked move wastes a turn | 1 | 18 | 9 |
| 03 | Where Is the Exit? | cows head for the exit | 1 | 12 | 4 |
| 04 | The Alert Cow | fleeing, then returning to the exit | 1 | 12 | 7 |
| 05 | The Exit Is Closed | the farmer cannot use exits | 1 | 14 | 7 |
| 06 | Ambush Behind the Wall | fixed terrain blocks sight | 1 | 10 | 4 |
| 07 | Intercept Before the Exit | stop the cow before it escapes | 1 | 9 | 4 |
| 08 | Prediction and Undo | preview and undo | 1 | 14 | 6 |
| 09 | Mossy Heights | handling multiple cows | 2 | 27 | 19 |
| 10 | The Last Pasture | multiple cows and exit pressure | 2 | 33 | 25 |

The table uses English translations of the in-game level titles.

- Levels 1–8 teach the mechanics; levels 9–10 combine them.
- Each level has a `learning_objective` and a list of `hint_text` strings. The
  objective and description appear in the left sidebar, while the current hint
  appears in the teaching card below it (the former rules slot), with a page
  count, a Next button and progress dots. The card advances automatically after
  nine seconds of real play, regardless of movement or animation, and can also
  be paged manually.
- An unfinished teaching objective never blocks unlocking and never asks the
  player to replay the level. Any valid clear counts.
- Teaching levels hide the S/A/B/C badge in the victory summary; the internal
  turn thresholds remain for data compatibility.
- There is no separate tutorial entry, tutorial progress, or tutorial skip/reset
  UI.

## Prediction, alerts and loops

The preview shows up to `prediction_steps` future cow positions and facings
while the farmer stays at his current position and facing. It is drawn as
translucent footprints and dashed paths, with an on-screen caption explaining
the assumption. A cow that would reach an exit is marked in red. `0` disables
the preview for that level.

The Alerts button in the right toolbar toggles the exclamation icons above
fleeing cows. Settings also has a switch for teaching objectives and hints. The
preview caption sits below the board on the right. Playback hides the preview so
the replay is easier to follow.

If the complete position repeats — farmer position and facing, every cow's
position and facing, and all caught flags — the game shows a loop hint. It does
not lose the run; the player can continue and break the loop.

## Challenge, daily and achievements

- **Challenge:** five curated side levels with local best turns.
- **Daily:** a meadow generated from the local date and verified with the shared
  solver. It falls back to campaign level 1 only if no candidate is solvable.
- **Achievements:** `one_step`, `close_call`, `flawless`, `loop_free` and
  `all_levels`.
  - `one_step`: catch every cow in one turn.
  - `close_call`: win on the final allowed turn.
  - `flawless`: never bump a wall while moving forward.
  - `loop_free`: never trigger the loop hint.
  - `all_levels`: clear all ten campaign levels.

## Editor and solver

- Paint grass, fence, hedge, tree and pond.
- Place the farmer, move, add or remove up to three cows, and choose the active
  cow.
- Use the exit tool to add or remove exits. Exits cannot contain the farmer, a
  cow, a wall or a fixed obstacle.
- Toggle fixed hay-bale obstacles.
- Adjust `max_turns`, `prediction_steps`, `sight_range` and `exit_sight_range`.
- Cycle cow facing, exit and flee tiebreaks, `cows_block_sight` and
  `cows_block_each_other`. All cows share one behaviour; there is no separate
  behaviour switch.
- **Export validation:** before writing, the editor calls the same
  `game.solver.solve_level` used by the game and tests. An exhausted search with
  no solution rejects the export and explains why. If the search reaches its
  limit, a dialog lets the player cancel or export as unverified.
  Verified files include `verification: {status, shortest_turns}`; unverified
  files are marked and the import screen warns about them.
- **Export vs. playback:** export validation performs a fresh bounded search;
  the failure dialog uses the cached `solve_level_cached` path. Both run the same
  BFS over `Simulation`.
- Import reads the first level in a bundle. There is no name field: new levels
  use a fixed default name, and imported levels keep theirs.

## Level data format

```json
{
  "version": 5,
  "game": "The Tamworth Chase",
  "levels": [
    {
      "id": "level_01",
      "name": "Which Way?",
      "grid": ["#######", "#F....#", "#..C..#", "#.....#", "#######"],
      "fj_start_direction": "north",
      "cow_facings": ["east"],
      "exit_cells": [[3, 5]],
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
      "chapter": "Basic Driving",
      "learning_objective": "Turning and moving: every turn must turn or move.",
      "hint_text": ["W/Up faces up; S/Down faces down...", "Space moves forward..."],
      "hint": "Turn first, then move.",
      "description": "The first of ten short lessons."
    }
  ]
}
```

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | required | Unique level id |
| `name` | string | id | Display name |
| `grid` | string[] | required | Terrain rows; `F` is the farmer and `C` is a cow |
| `fj_start_direction` | string | `north` | Farmer's initial facing (`up/right/down/left` also accepted) |
| `cow_facings` | string[] | `east` | One facing per cow |
| `exit_cells` | `[row,col][]` | required | At least one exit; must not overlap a wall, fixed obstacle, the farmer's start or a cow |
| `max_turns` | int | 30 | Turn limit |
| `prediction_steps` | int | 5 | Preview depth; 0 disables |
| `exit_sight_range` | int | -1 | Exit visibility range; -1 means unlimited |
| `sight_range` | int | -1 | Farmer visibility range; -1 means unlimited |
| `exit_tiebreak` / `flee_tiebreak` | `right` / `left` | `right` | Preferred side when distances tie |
| `cows_block_sight` | bool | false | Cows block the farmer's line of sight |
| `cows_block_each_other` | bool | false | Cows block each other's movement |
| `walls` | `[row,col][]` | `[]` | Optional extra fence coordinates, folded into the grid |
| `obstacles` | `[row,col][]` | `[]` | Optional fixed hay-bale blockers |
| `chapter` | string | level group | Chapter label on the level-select screen |
| `learning_objective` | string | `""` | Teaching text; empty on ordinary levels |
| `hint_text` | string or string[] | `[]` | Progressive hints |
| `s/a/b_threshold` | int | derived | Turn thresholds for grades |
| `hint` / `description` | string | `""` | UI copy |
| `verification` | object | absent | Solver metadata from an editor export |

Grid characters: `.` grass, `,` flowers, `#` fence, `T` tree, `~` pond, `H` hedge,
`F` farmer, `C` cow. Legacy `D/G/S` cow characters are read as normal cows. A cow
may not start on an exit, and the farmer may never start on one either.

**Backward compatibility.** Old fields such as `step_limit`, `obstacle_limit`,
`initial_obstacles`, `win_condition`, `pen_cells`, `cow_behavior`, cow personality
fields and item fields are ignored; `step_limit` falls back to `max_turns`. Old
`tips` and `practice` tutorial fields are also ignored. When a level has no exit,
a deterministic far-away walkable cell is chosen and marked in
`extra["legacy_exit"]`.

## Save data

- Default: `~/.the_tamworth_chase/save.json`
- Override the directory with `TAMWORTH_CHASE_DATA`.
- Save version **6** removes the independent `tutorial` section. Known completed
  old tutorial lessons are mapped onto their corresponding campaign levels
  (`basics_01` to `level_01`, ..., `advanced_03` to `level_10`); unmapped tutorial
  records are ignored. Campaign records gained a `cleared` field so the normal
  unlock chain continues.
- Sections: `settings`, `main`, `achievements`, `challenges`, `daily` and `custom`.
  Writes are atomic; the `hints` setting defaults to on.
- A corrupt save produces a prompt and a fresh save instead of a crash.

## Fonts and licensing

- `assets/fonts/CEFFontsCJK-Regular.ttf` is bundled CEF Fonts CJK under the SIL
  Open Font License 1.1; the full text is in `assets/fonts/OFL.txt`.
- The font is loaded from local disk at runtime.
- CEF renders the digit `1` like a slash, so digit runs use a system rounded font
  (SF Rounded, Avenir Next, Helvetica Neue, DejaVu Sans, Arial). CJK and Latin
  letters keep the handwritten face. Missing fonts fall back to system CJK faces.

## Art and audio

- Terrain, fences, ponds, cows, the farmer, exit gates, hay bales and alert
  bubbles are procedural. Tiles are drawn at a higher resolution and smoothed
  down.
- There are no bitmap sprite sheets and no emoji game objects.
- Sound cues are synthesised at start-up in `game/audio.py`.
- Background music is “Meadow Thoughts” by Écrivain, a solo-harp loop bundled as
  `assets/music/meadow_thoughts.ogg` under CC0 1.0. Full credit is in
  `assets/music/README.md`.
- Settings can toggle sound and music together and adjust the master volume.
  Background music is mixed lower than sound effects.

## Offline promise

- The game imports no network modules and makes no network requests at runtime.
- There are no accounts, rooms, matchmaking, servers, WebSockets, cloud saves or
  online leaderboards.
- The binary assets are the bundled font and the CC0 background music; both load
  from local disk.
- Daily seeds come from the local date.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Coverage includes absolute steering, same-direction turns, blocked moves,
exit-blocked moves, start-position validation, farmer-before-cow order, cow sight
and range, the unified flee priority, the fallback from fleeing to exit seeking,
boxed-in cows, exit seeking, exit and flee tiebreaks, all-caught wins, any-exit
losses, multi-cow order and blocking, loop hints, prediction assumptions and exit
marks, undo and restart, legacy fields, save version 6 migration, teaching
objectives not blocking clears, the mirrored play layout, dynamic board centering,
key-labelled buttons, the sidebar teaching card and its next control, editor
export checks, achievements, daily determinism, offline scanning and headless
rendering of every scene.

Playback has dedicated tests for the failure-dialog action, ignored player input,
pause/resume, early exit, automatic restore, the playback-finished dialog,
replay/restart from that dialog, no-solution notices, time limits and cache
invalidation.

Reference solutions live in `tests/solutions.json` and
`tests/challenge_solutions.json`. The shared solver also powers the editor and
the command-line tool:

```bash
.venv/bin/python tools/solve.py levels/levels.json
```

## Project layout

```
main.py                     Entry point
LICENSE                     MIT project license
THIRD_PARTY_NOTICES.md      Font and music license notices
README.md                   Simplified Chinese README (default)
README_EN.md                English README
game/
  models.py                 Headless models: Action, Level, TickResult
  core.py                   Absolute steering, cow AI, exits, undo, prediction
  solver.py                 Shared bounded BFS, limits and playback cache
  levels.py                 Schema parsing, validation, serialisation
  progress.py               Save sections and v6 tutorial merge
  achievements.py           Achievement rules
  editor.py                 Editor model and JSON exchange
  daily.py                  Local daily seed and shared solver check
  animation.py              One-turn interpolation
  render.py                 Board, gates, alerts, prediction, effects
  theme.py                  Palette, fonts, layout
  ui.py                     Buttons, toggles, modals
  art.py                    Procedural art
  audio.py                  Synthesised cues and background music
  app.py                    Window and scene routing
  scenes/                   Menu, levels, play, challenge, daily, editor,
                            achievements, settings
levels/                     Campaign and challenge JSON
assets/fonts/               Bundled CJK font and OFL text
assets/music/               Bundled CC0 background loop and credit
tests/                      Unit, integration and data tests
tools/                      Solver CLI and screenshot helper
```

`custom_levels/` and the save directory are not tracked by Git.

## Design notes

- **All cows must be caught; any cow reaching an exit loses the run.** This is
  enforced for both single-cow and multi-cow levels.
- **The turn limit is a budget.** Reaching `max_turns` without a win loses. A
  winning action on the same turn is resolved first and is accepted.
- **Turning to the current facing is invalid and free.**
- **Fleeing is temporary.** If moving forward or turning left or right cannot
  increase the distance, the cow returns to the exit logic. If every adjacent
  cell is blocked, it stays still.
- **Exits are cow-only.** The farmer's walkability check excludes exits, and
  loading rejects a farmer/exit overlap. Cows may enter an exit and immediately
  lose the run, so standing on a gate cannot block it.
- **Exit sight is strictly straight-line.** Only the same row or column counts;
  diagonal exits are invisible and cows patrol along walls.
- **Caught cows leave the board.** Their positions remain in the undo snapshot,
  but movement, sight, exit checks and rendering skip them.
- **Teaching objectives are hints only.** They never affect wins, ratings or
  unlocks.
- **Only the play screen is mirrored.** The editor keeps its board on the left
  and tool panel on the right.
- **There is no standalone rules card.** The turn limit appears in the compact
  top stats, the prediction depth in the caption below the board, and the exit
  reminder as one line in the sidebar. Shortcuts are printed on the toolbar and
  footer.
- **Hint-card rules:** levels with `hint_text` get a paged card; levels with only
  `hint` get a compact single-hint card; levels with neither leave the lower
  sidebar empty. Turning hints off hides the card.
- **Terrain is fixed:** the grid plus optional `walls` and `obstacles`.
- **Prediction covers cows only**, with the farmer held still. A preview of
  candidate farmer actions is not implemented.
- **Solver limits** combine deterministic node caps with an optional wall-clock
  limit. An exhausted search is `unsolvable`; reaching a cap is `limit`. The
  editor treats the latter as unverified, and the failure dialog reports that no
  solution is available right now.
- **Solution playback is a teaching aid, not a skip.** It restores the failed
  position and never records a clear, best time or achievement.
- **Solution cache invalidation** uses `RULES_VERSION` and the rule-relevant
  level data (terrain, actors, exits, obstacles, turn limit, sight and tiebreaks),
  not the current attempt's position.
- **Playback searches synchronously** with a three-second cap. The hardest
  shipped level currently takes about 1.4 seconds on the development machine, so
  the interface blocks briefly.
- **Playback pace is fixed.** The action interval is constant; speed and
  single-step controls are future work.

## Known limitations

- The GUI is verified headlessly with screenshots and injected events; it has not
  been manually play-tested on a physical display.
- Sound effects are synthesised and the CC0 harp loop is bundled. Both were
  verified with a dummy audio device and have not been auditioned on physical
  hardware.
- The editor has no level-name field and uses a fixed 10×10 canvas.
- The daily generator falls back to campaign level 1 if no candidate is solvable.
- Undo keeps at most 256 snapshots.
- Challenge levels are intentionally tighter than the teaching levels; two have a
  shortest solution equal to their turn limit.
- A fully boxed-in cow holds still. This is a safe fallback, not an interesting
  puzzle state; shipped levels avoid it.
- The parser itself does not impose 10×10; the editor canvas does.
- Solution search is synchronous, so a difficult custom level can pause the
  interface for up to three seconds before reporting that no solution is
  available right now.
- Playback has a fixed pace and no speed or single-step controls.

## License

The Tamworth Chase is released under the **MIT License**. See
[LICENSE](LICENSE) for the full text.

The MIT license covers the original source code and procedural artwork. Bundled
third-party assets keep their own licenses:

- **CEF Fonts CJK** — SIL Open Font License 1.1; full text in
  `assets/fonts/OFL.txt`.
- **“Meadow Thoughts”** by Écrivain — CC0 1.0; source and SHA-256 in
  `assets/music/README.md`.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the complete notices.
