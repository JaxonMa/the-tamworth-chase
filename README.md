# The Tamworth Two

*A cozy, hand-drawn grid-chase puzzle game made entirely with Python.*

Farmer John and his cow both walk the same way: one step forward if the next
tile is free, otherwise turn 90° clockwise and stay put. They move at exactly
the same time, forever. Your job is to place a few hay bales before the chase
starts so that the two paths fold into each other and the farmer catches the
cow — without running out of steps and without falling into a time loop.

The whole game is offline. No accounts, no servers, no telemetry, no network
requests while it runs.

---

## Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Virtual environment and installation](#virtual-environment-and-installation)
4. [Running the game](#running-the-game)
5. [Controls](#controls)
6. [Game rules](#game-rules)
7. [Progression, ranks and unlocks](#progression-ranks-and-unlocks)
8. [Tutorial chapters](#tutorial-chapters)
9. [Fonts and licensing](#fonts-and-licensing)
10. [Art, audio and offline assets](#art-audio-and-offline-assets)
11. [Save data](#save-data)
12. [Tests](#tests)
13. [Project layout](#project-layout)
14. [Design notes and assumptions](#design-notes-and-assumptions)

---

## Features

- 10 hand-made 10×10 campaign meadows with a rising difficulty curve.
- A synchronous two-body chase simulation with strict time-loop detection.
- Place limited hay bales, undo them, and forecast the next three steps.
- Playback controls: start, pause, single step, 0.5× / 1× / 2× speed, restart.
- S/A/B/C step-based ratings and locally stored best results.
- Level select with sequential unlocking, plus a settings screen.
- Interface, level names, hints and dialogs are entirely in Simplified Chinese.
- Programmatic artwork: grass, wooden fences, hedges, trees, ponds, the farmer
  and the cows are all drawn with code, no bitmap sprite sheets.

> **Milestone status.** This build is the playable MVP: the full campaign,
> simulation, interface, ratings and save system. The independent tutorial
> chapters, extra cow personalities, items, challenge modes and the level
> editor are the next milestone; their data files and APIs are already wired
> into the layout below so they can be added without touching the rules.

## Requirements

- Python 3.10 or newer (developed and verified on CPython 3.14).
- A desktop session with a window system (macOS, Windows or Linux).
- `pygame-ce` for windowing, drawing and audio; `pytest` for the test suite.

## Virtual environment and installation

The repository expects a local virtual environment in `.venv/`.

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you prefer an explicit interpreter path instead of activating the
environment:

```bash
.venv/bin/python main.py
.venv/bin/python -m pytest
```

Dependencies are pinned to compatible ranges in `requirements.txt`:

| Package | Version | Purpose |
| --- | --- | --- |
| pygame-ce | >=2.5,<2.6 | Window, rendering, input and sound mixing |
| pytest | >=8,<9 | Unit tests only |

## Running the game

```bash
.venv/bin/python main.py
```

There are no command-line modes required to play. All progress is stored in a
local JSON file (see [Save data](#save-data)).

## Controls

| Input | Action |
| --- | --- |
| Left click | Place a hay bale on the meadow (before the chase starts) |
| Left click on a hay bale | Pick it back up |
| Right click | Pick up the hay bale under the cursor |
| `Space` | Start the chase, or pause / resume |
| `S` or `→` | Advance a single tick |
| `R` | Restart the attempt |
| `1` / `2` / `3` | Set playback speed to 0.5× / 1× / 2× |
| `P` | Toggle the three-step forecast |
| `Esc` | Go back |

Every action is also available from the on-screen buttons on the right-hand
panel.

## Game rules

1. The board is a 10×10 meadow surrounded by fence.
2. Farmer John and every cow stand on a tile and face one of the four cardinal
   directions.
3. On every tick both actors are advanced **simultaneously**: the next state of
   the farmer and of every cow is computed from the current state, and only
   then are all of them committed.
4. If the tile directly in front is walkable, the actor moves one tile forward
   and keeps its facing. Otherwise it rotates 90° clockwise in place and does
   not move on that tick.
5. Fences, hedges, trees, ponds, board edges and hay bales block movement.
   Actors never block each other; they can step through the same tile in
   opposite directions without meeting.
6. If the farmer and a cow occupy the same tile after a tick, the cow is caught
   and the level is won immediately.
7. If a complete state repeats — farmer pose, every cow pose and the obstacle
   layout — the simulation has entered a time loop and the attempt is lost.
8. If the step budget is exhausted before a catch, the attempt is lost.

The simulation lives in `game/core.py` and has no pygame dependency, so every
rule above is covered by unit tests.

## Progression, ranks and unlocks

- Campaign levels unlock in order: finishing a level opens the next one.
- The rating depends only on the number of steps used:
  - **S** – at or below the level's S threshold
  - **A** – at or below the A threshold
  - **B** – at or below the B threshold
  - **C** – finished the level above the B threshold
- The best step count and the best rank are stored per level; the best rank
  never downgrades.
- Tutorial progress is stored in a **separate** section of the save file and
  never affects campaign unlocking. Campaign progress never marks a tutorial
  lesson as completed.

## Tutorial chapters

The tutorial will be an independent chapter system with its own entry on the
main menu, its own lesson list and its own state machine
(`not_started` / `in_progress` / `completed` / `skipped`). The data schema and
the save-layer separation are already in place (`game/tutorial.py`,
`game/progress.py`); the lesson content and screens ship with the next
milestone.

Planned chapters:

| Chapter | File | Focus |
| --- | --- | --- |
| 基础教程 | `tutorials/basics.json` | Movement, turning, placing and undoing hay bales, synchronous movement, the three-step forecast, catching, time loops |
| 进阶教程 | `tutorials/advanced.json` | A second cow, cow personalities, items |
| 编辑器教程 | `tutorials/editor.json` | Using the level editor, exporting and importing levels |

## Fonts and licensing

The interface uses **CEF Fonts CJK** (快去写作业CJK), a hand-written style font
drawn entirely with a mouse, which gives the interface its picture-book feel.

- Font: CEF Fonts CJK, Regular
- Author: Partyb0ssishere
- Source repository: <https://github.com/Partyb0ssishere/cef-fonts-cjk>
- License: SIL Open Font License, Version 1.1
- Bundled file: `assets/fonts/CEFFontsCJK-Regular.ttf`
- License text: `assets/fonts/OFL.txt`

The font is downloaded once during development and shipped inside the
repository. The game never fetches a font at runtime. The OFL permits free use,
embedding and redistribution as long as the license text is retained and the
font files themselves are not sold on their own.

Two practical details are handled by `game/theme.py`:

1. **Fallback chain.** If the bundled font is missing the game falls back to a
   system rounded/sans CJK font and then to the system default, so Chinese text
   stays readable on any machine.
2. **Digit legibility.** CEF Fonts CJK draws the digit `1` as a bare stroke that
   is easily confused with `/`. Numbers are therefore rendered with a rounded
   system face (SF Rounded → Avenir Next → Helvetica Neue → DejaVu Sans →
   Arial → the bundled font) while Chinese and Latin letters keep the
   hand-written look. Body text is never smaller than 18 px.

The font file is redistributed unmodified under the SIL OFL 1.1; see
`assets/fonts/OFL.txt` for the full license text.

## Art, audio and offline assets

- **Art** – every visual element is drawn procedurally at runtime by
  `game/art.py` and `game/render.py`: grass tiles with soft texture, wooden
  fence segments that connect to their neighbours, hedges, tree groves, ponds,
  the farmer, four cow views per personality, hay bales and item props. The
  game ships no sprite sheets.
- **Audio** – all sound effects are synthesised at start-up in `game/audio.py`
  from simple waveforms, so there are no audio files to download. Sound can be
  muted in the settings screen.
- **Offline** – the game makes no network calls. The only binary asset in the
  repository is the bundled font.

## Save data

Progress is stored as JSON outside the repository:

- Default: `~/.the_tamworth_two/save.json`
- Override: set the environment variable `TAMWORTH_TWO_DATA` to a directory
  before starting the game.

The file keeps the following sections apart: `settings`, `main` (campaign),
`tutorial`, `achievements`, `challenges`, `daily`. Writes are atomic, and a
corrupt file falls back to a fresh save instead of crashing.

## Tests

```bash
.venv/bin/python -m pytest -q
```

The suite covers the head-less rules (forward movement, clockwise turning,
synchronous commits, catches, time loops, step limits, obstacle placement and
undo, forecasting), the shipped campaign data and reference solutions, the save
store and the tutorial state machine.

## Project layout

```
main.py                     Application entry point
game/app.py                 Window, scene routing, main loop
game/models.py              Enums and immutable data models
game/core.py                Pure simulation (no pygame import)
game/levels.py              Level JSON parsing and validation
game/tutorial.py            Tutorial catalogue, state machine and hint session
game/progress.py            Separate campaign / tutorial save storage
game/theme.py               Palette, fonts, rounded UI primitives
game/art.py                 Procedural tiles, characters and props
game/render.py              Board rendering, forecasting overlay, effects
game/playback.py            Playback clock and move interpolation
game/ui.py                  Buttons, cards, toggles, sliders, modals
game/audio.py               Synthesised sound effects
game/scenes/                One module per screen
levels/levels.json          Campaign level data
tutorials/*.json            Tutorial chapter data
assets/fonts/               Bundled CJK font + OFL license
tests/                      pytest suite and reference solutions
tools/                      Development helpers (solver, builders, screenshots)
```

## Design notes and assumptions

- **Synchronous by construction.** The tick computes every actor's next state
  first and commits afterwards, which is the only way to keep the rule honest
  when actors swap tiles.
- **Time loop state key.** The key contains the farmer's tile and facing, every
  cow's tile and facing, and the obstacle layout. A new tick that reproduces a
  key already seen ends the attempt as a time loop.
- **Step budget.** A level with a limit of *n* steps allows exactly *n* moves;
  failing to catch the cow by then loses the attempt.
- **Hay bales** are the only pre-chase placement in the campaign. They cannot be
  placed on fences, trees, ponds, hedges, outside the meadow, on the actors or
  on an existing bale, and they cannot be placed once the chase has started.
- **Ratings** are derived from step counts so they are deterministic and
  testable; no hidden timers are involved.
- The renderer runs at 60 FPS and falls back to a low-effects mode (no
  particles or complex flourishes) from the settings screen.

## License

The game code in this repository is provided for personal and educational use.
The bundled font is covered by the SIL Open Font License 1.1, reproduced in
`assets/fonts/OFL.txt`.
