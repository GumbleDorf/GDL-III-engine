import sys
from GDLIIIEngine import GDLIIIEngine
from internal.GDLIIIParser import File_Format
from problog.logic import Term, Constant,Var, Clause
from random import choice

# Usage: python muddy.py [muddy2|muddy3] [pattern], where pattern is e.g. 110 (1 = muddy, in role order)
def main(example='muddy', pattern=None):
    mod = GDLIIIEngine(f'./examples/{example}.gdliii', File_Format.PREFIX)
    children = [p for p in mod.player_names if p != 'random']
    step = 0
    while not mod.is_terminal():
        moves = mod.get_legal_moves()
        rmove = choice(moves['random'])
        if pattern is not None and step == 0:
            rmove = Term('muddy', *[Constant(int(c)) for c in pattern])
        #Children only ever have a single legal move (noop or one of say yes/say no)
        mov = {c: moves[c][0] for c in children}
        mov['random'] = rmove
        print(f"Step {step}: {mov}")
        mod.set_actions(mov)
        mod.update_step()
        for c in children:
            print(f"  {c} knows muddy: {mod.query(c, Term('isMuddy', Constant(mod.player_to_id(c))))}")
        step += 1

if __name__ == "__main__":
    main(*(sys.argv[1:3] if len(sys.argv) > 1 else ['muddy']))
