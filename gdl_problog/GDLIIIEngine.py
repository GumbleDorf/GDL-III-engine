from .internal.GDLIIIProblogRep import GDLIIIProblogRep
from .internal.GDLIIIParser import File_Format
from problog.logic import Term, Constant,Var, Clause
from random import Random

class GDLIIIEngine(object):
    #seed makes the random player's moves reproducible; self.rng can also be used by callers for their own choices
    def __init__(self, file_name, fformat, seed=None):
        self.rng = Random(seed)
        self._cur_step = 0
        self._gdl_rep = GDLIIIProblogRep(file_name, fformat)
        self._player_map = self._gdl_rep._model.player_map
        self.player_names = list(self._player_map.keys())
    #Must be called when inserting player name into a query clause
    def player_to_id(self, player):
        return self._player_map[player]
    # Make a query at the current step, alternatively, make a query to a future step using only currently known information
    # Query is made from the perspective of player names in player parameter
    # Returns a list of pairs, with probability in index 0 and the corresponding predicate in index 1
    def query(self, player, query, step=0):
        if (type(step) != int) or (step < 0):
            raise Exception("Expected step to be None or integer >= cur_step")
        if player not in self.player_names:
            raise Exception("{} is an undefined role".format(player))
        if player == 'random':
            raise Exception("Random player does not track knowledge state")
        return sorted([(prob, pred) for (pred, prob) in self._gdl_rep.query(Constant(self._player_map[player]), query, step).items()], \
            key=lambda a: a[0], reverse=True)
    # Get moves for every player, or alternatively, specify a player and only recieve current legal moves for them
    def get_legal_moves(self, player=None):
        if player is None:
            return {i: self.get_legal_moves(i) for i in self.player_names}
        return sorted(self._gdl_rep.getLegalMovesForPlayer(self._player_map[player]), key=lambda a: str(a))
    # Pass in a dict of actions for each player
    # Alternatively, pass in a dict containing only a subset of player actions
    def set_actions(self, moves):
        for (player, action) in moves.items():
            if player not in self.player_names:
                raise Exception("{} is an undefined role".format(player))
            self._gdl_rep.submitAction(action, Constant(self._player_map[player]))
    # Undo all actions and go back a step
    # Optionally, set increment to a value greater than 1 to undo multiple steps
    def undo_step(self, increment=1):
        if self._cur_step == 0:
            raise Exception("Cannot undo a game with 0 actions made")
        if type(increment) != int or increment < 1 or increment > self._cur_step:
            raise Exception("Expected increment to be an integer >= 1")
        self._gdl_rep.undo(increment)
        self._cur_step -= increment
    # Process the actions in the queue and move to the next step
    # Can only be called if every player has a valid move
    def update_step(self):
        if self.is_terminal():
            raise Exception("Cannot continue to next step, current state is terminal")
        random_id = self._gdl_rep._randomIdentifier
        if random_id in self._gdl_rep.getMoveList() and self._gdl_rep.getMoveList()[random_id] is None:
            self._gdl_rep.submitAction(self.rng.choice(tuple(self._gdl_rep.getLegalMovesForPlayer(random_id))), random_id)
        self._gdl_rep.applyActionsToModelAndUpdate()
        self._cur_step +=1

    def is_terminal(self):
        return self._gdl_rep.terminal
