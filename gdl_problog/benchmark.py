"""Times loading, playing and querying the example games. Usage: python -m gdl_problog.benchmark [game ...]"""
import os
import sys
from time import perf_counter

from problog.logic import Term, Constant, Var

from . import GDLIIIEngine, File_Format, EXAMPLES_DIR

#name -> (file format, query run after the game is played to terminal)
GAMES = {
    'muddy': (File_Format.PREFIX,     lambda m: m.query(m.player_names[0], Term('isMuddy', Var('_')))),
    'muddy3': (File_Format.PREFIX, lambda m: m.query(m.player_names[0], Term('isMuddy', Var('_')))),
    'muddy4': (File_Format.PREFIX, lambda m: m.query(m.player_names[0], Term('isMuddy', Var('_')))),
    'guess': (File_Format.PREFIX, lambda m: m.query('player', Term('secret', Var('_')))),
    'montyhall': (File_Format.INFIX, lambda m: m.query('candidate', Term('car', Var('_')))),
}


def play_first_moves(mod):
    steps = 0
    while not mod.is_terminal():
        mod.set_actions({p: mod.get_legal_moves(p)[0] for p in mod.player_names})
        mod.update_step()
        steps += 1
    return steps


def bench(name):
    fmt, query = GAMES[name]
    path = os.path.join(EXAMPLES_DIR, f'{name}.gdliii')
    t0 = perf_counter()
    mod = GDLIIIEngine(path, fmt, seed=0)
    t1 = perf_counter()
    steps = play_first_moves(mod)
    t2 = perf_counter()
    query(mod)
    t3 = perf_counter()
    print(f"{name:10} load {t1 - t0:6.2f}s  play {steps} steps {t2 - t1:6.2f}s  query {t3 - t2:6.2f}s")


def main(names=None):
    for name in names or GAMES:
        bench(name)


if __name__ == "__main__":
    main(sys.argv[1:])
