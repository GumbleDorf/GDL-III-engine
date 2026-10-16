import os
from . import GDLIIIEngine, File_Format, EXAMPLES_DIR
from problog.logic import Term, Var

# We can figure this out from the GDLEngine too
PLAYER_NAME = 'player'

def main():
    mod = GDLIIIEngine(os.path.join(EXAMPLES_DIR, 'guess.gdliii'), File_Format.PREFIX)
    res = {}
    for i in range(1,11):
        res[i] = 0
    res['lost'] = 0
    #Choose a move
    for i in range(0,1000):
        guesses = 0
        mov = mod.get_legal_moves()
        mod.set_actions({'player':mov['player'][0]})
        mod.update_step()
        while not mod.is_terminal():
            mov = mod.get_legal_moves()
            pmoves = sorted(mov[PLAYER_NAME],key=lambda a: int(str(a.args[0])))
            possible_nums = sorted([a[1] for a in mod.query('player',Term('secret', Var('_')))], key=lambda a: int(str(a.args[0])))
            num = int(str(possible_nums[round(len(possible_nums)/2)].args[0]))-1
            mod.set_actions({'player':pmoves[num]})
            mod.update_step()
            guesses +=1
        result = mod.query('player',Term('secret', Var('_')))
        if len(result) == 1:
            res[guesses] += 1
        else:
            res['lost'] +=1
        mod.undo_step(guesses + 1)
        print(f'Game {i} Complete')
    print(res)


if __name__ == "__main__":
    main()
