"""Scratch pad: test candidate grids against the solver."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from game.levels import parse_level
from game.core import Simulation
from game.models import GameStatus
from tools.solve import solve, render_solution

def trace(level, obstacles=()):
    sim = Simulation(level, obstacles)
    sim.start()
    path = []
    while sim.status is GameStatus.PLAYING:
        sim.step()
        path.append((sim.farmer.pos, sim.cows[0].pos))
    return path

def show(grid, name="cand", maxobs=3, farmer_facing="east", cow_facings=None):
    data = {"id": name, "name": name, "grid": grid, "obstacle_limit": maxobs, "step_limit": 60,
            "farmer_facing": farmer_facing}
    if cow_facings:
        data["cow_facings"] = cow_facings
    lv = parse_level(data)
    t0 = time.time()
    r = solve(lv, verbose=False)
    print(f"--- {name}: solved={r.solved} steps={r.steps} obs={r.obstacles} ({time.time()-t0:.1f}s)")
    if r.solved:
        print(render_solution(lv, r.obstacles))
    return lv, r

if __name__ == "__main__":
    grids = {
    "empty": [
"##########",
"#........#",
"#........#",
"#..F.....#",
"#........#",
"#........#",
"#....C...#",
"#........#",
"#........#",
"##########"],
    "pillars": [
"##########",
"#........#",
"#..#..#..#",
"#..F.....#",
"#........#",
"#..#..#..#",
"#....C...#",
"#........#",
"#........#",
"##########"],
    "spiralA": [
"##########",
"#F.......#",
"#.######.#",
"#.#....#.#",
"#.#.C..#.#",
"#.#....#.#",
"#.######.#",
"#........#",
"#........#",
"##########"],
    }
    for n,g in grids.items():
        show(g, n)
