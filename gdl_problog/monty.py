import os
from . import GDLIIIEngine, File_Format, EXAMPLES_DIR
from problog.logic import Term, Constant, Var

# We can figure this out from the GDLEngine too
PLAYER_NAME = 'candidate'

def main(seed=None):
    mod = GDLIIIEngine(os.path.join(EXAMPLES_DIR, 'montyhall.gdliii'), File_Format.INFIX, seed=seed)
    res = {}
    for i in range(0,1000):
        print(f"Game {i}")
        #Random initial door choice to begin with
        moves1 = mod.get_legal_moves()[PLAYER_NAME]
        mod.set_actions({PLAYER_NAME: mod.rng.choice(moves1)})
        mod.update_step()
        #Second step, can only choose noop
        mod.set_actions({PLAYER_NAME: mod.get_legal_moves()[PLAYER_NAME][0]})
        mod.update_step()
        #Important step to show game playing capability. Check whether we believe we are currently in a winning state
        #If yes, then choose noop, if no choose switch
        (p100,goal100) = mod.query(PLAYER_NAME, Term('goal', Constant(mod.player_to_id(PLAYER_NAME)), Constant('100')))[0]
        (p0,goal0) = mod.query(PLAYER_NAME, Term('goal', Constant(mod.player_to_id(PLAYER_NAME)), Constant('0')))[0]
        if (p100 > p0):
            #Perform Noop if we are more likely to be in the winning state already
            mod.set_actions({PLAYER_NAME:mod.get_legal_moves()[PLAYER_NAME][0]})
        else:
            #Perform switch if we are likely to be in the losing state
            mod.set_actions({PLAYER_NAME:mod.get_legal_moves()[PLAYER_NAME][1]})
        mod.update_step()
        # Add a counter to either goal(1,0) if we lost, or goal(1,100) if we won
        goal = mod.query(PLAYER_NAME, Term('goal', Constant(mod.player_to_id(PLAYER_NAME)), Var('_')))[0][1]
        res[str(goal)] = res.get(str(goal), 0) + 1
        # Go back to beginning of game
        for i in range(3):
            mod.undo_step()
    print(res)


if __name__ == "__main__":
    main()
