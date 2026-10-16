import os
from itertools import product

import pytest
from problog.logic import Term, Constant, Var

from gdl_problog import GDLIIIEngine, File_Format, EXAMPLES_DIR


def load(name, seed=0):
    return GDLIIIEngine(os.path.join(EXAMPLES_DIR, f'{name}.gdliii'), File_Format.PREFIX, seed=seed)


def step(mod, **chosen):
    """Plays one step: every role takes its first legal move unless a move is given by role name."""
    moves = {p: mod.get_legal_moves(p)[0] for p in mod.player_names}
    moves.update(chosen)
    mod.set_actions(moves)
    mod.update_step()


def beliefs(mod, player, query):
    return {str(t): p for p, t in mod.query(player, query)}


def goal(mod, player):
    result = mod.query(player, Term('goal', Constant(mod.player_to_id(player)), Var('G')))
    assert len(result) == 1 and result[0][0] == pytest.approx(1.0)
    return int(str(result[0][1].args[1]))


# Three prisoners

def play_prisoners(pardoned, named):
    mod = load('threeprisoners')
    step(mod, random=Term('pardon', Term(pardoned)))
    step(mod, random=Term('name', Term(named)))
    return mod


def test_prisoners_prior_is_uniform():
    mod = load('threeprisoners')
    step(mod, random=Term('pardon', Term('pa')))
    assert beliefs(mod, 'ann', Term('pardoned', Var('P'))) == pytest.approx({'pardoned(pa)': 1 / 3, 'pardoned(pb)': 1 / 3, 'pardoned(pc)': 1 / 3})


@pytest.mark.parametrize('pardoned,named', [('pa', 'pb'), ('pc', 'pb'), ('pa', 'pc'), ('pb', 'pc')])
def test_prisoners_named_prisoner_is_never_pardoned(pardoned, named):
    mod = play_prisoners(pardoned, named)
    other = ({'pb', 'pc'} - {named}).pop()
    b = beliefs(mod, 'ann', Term('pardoned', Var('P')))
    # Ann's own chance stays at 1/3, but the prisoner that was not named inherits the rest
    assert b == pytest.approx({'pardoned(pa)': 1 / 3, f'pardoned({other})': 2 / 3})


def test_prisoners_warden_cannot_name_ann_or_pardoned():
    mod = load('threeprisoners')
    step(mod, random=Term('pardon', Term('pb')))
    assert [str(m) for m in mod.get_legal_moves('random')] == ['name(pc)']
    mod.undo_step()
    step(mod, random=Term('pardon', Term('pa')))
    assert [str(m) for m in mod.get_legal_moves('random')] == ['name(pb)', 'name(pc)']


# Monty Fall

def play_montyfall_to_open(hidden, chosen, opened):
    mod = load('montyfall')
    step(mod, random=Term('hide', Constant(hidden)), candidate=Term('choose', Constant(chosen)))
    step(mod, random=Term('open', Constant(opened)))
    return mod


def test_montyfall_goat_revealed_is_fifty_fifty():
    mod = play_montyfall_to_open(1, 1, 2)
    assert not mod.is_terminal()
    assert beliefs(mod, 'candidate', Term('car', Var('D'))) == pytest.approx({'car(1)': 0.5, 'car(3)': 0.5})


def test_montyfall_car_revealed_ends_game():
    mod = play_montyfall_to_open(2, 1, 2)
    assert mod.is_terminal()
    assert beliefs(mod, 'candidate', Term('car', Var('D'))) == pytest.approx({'car(2)': 1.0})
    assert goal(mod, 'candidate') == 0


def test_montyfall_stay_and_switch_win_equally_given_goat():
    wins = {'stay': 0.0, 'switch': 0.0}
    revealed = 0.0
    for hidden, opened in product((1, 2, 3), (2, 3)):
        mod = play_montyfall_to_open(hidden, 1, opened)
        if mod.is_terminal():
            revealed += 1 / 6
            continue
        for action in ('stay', 'switch'):
            step(mod, candidate=Term(action))
            wins[action] += (1 / 6) * (goal(mod, 'candidate') == 100)
            mod.undo_step()
    assert revealed == pytest.approx(1 / 3)
    # Conditioned on a goat being revealed, both strategies win half of the time
    assert wins['stay'] / (1 - revealed) == pytest.approx(0.5)
    assert wins['switch'] / (1 - revealed) == pytest.approx(0.5)


# Sum and Product

SECRET = Term('secret', Var('X'), Var('Y'))


def pairs(mod, player):
    return {str(t): p for p, t in mod.query(player, SECRET)}


def start_sumproduct(x, y):
    mod = load('sumproduct')
    step(mod, random=Term('choose', Constant(x), Constant(y)))
    return mod


def test_sumproduct_dialogue_belief_updates():
    mod = start_sumproduct(1, 4)
    assert pairs(mod, 'sam') == pytest.approx({'secret(1,4)': 0.5, 'secret(2,3)': 0.5})
    assert pairs(mod, 'pete') == pytest.approx({'secret(1,4)': 0.5, 'secret(2,2)': 0.5})
    step(mod)  # Sam: I know that you do not know the numbers
    assert pairs(mod, 'pete') == pytest.approx({'secret(1,4)': 1.0})
    assert pairs(mod, 'sam') == pytest.approx({'secret(1,4)': 0.5, 'secret(2,3)': 0.5})
    step(mod)  # Pete: now I know
    assert pairs(mod, 'sam') == pytest.approx({'secret(1,4)': 1.0})
    step(mod)  # Sam: now I know too
    assert mod.is_terminal()


def test_sumproduct_only_one_pair_supports_the_whole_dialogue():
    mod = load('sumproduct')
    complete = []
    for x in range(1, 11):
        for y in range(x, 11):
            step(mod, random=Term('choose', Constant(x), Constant(y)))
            while not mod.is_terminal():
                moves = mod.get_legal_moves()
                if any(len(m) == 0 for m in moves.values()):
                    break
                step(mod)
            if mod.is_terminal():
                complete.append((x, y))
            while mod._cur_step > 0:
                mod.undo_step()
    assert complete == [(1, 4)]


def test_sumproduct_dialogue_breaks_for_other_pairs():
    mod = start_sumproduct(2, 3)
    step(mod)
    # Pete holds product 6 which is ambiguous even after Sam's statement
    assert mod.get_legal_moves('pete') == []


# Kuhn poker

RANK = {'j': 0, 'q': 1, 'k': 2}


def kuhn_goals(hands, line):
    """Reference payoffs of both players as the goal values 50 + 25 * net chips."""
    if line[-1] == 'fold':
        loser = 'p1' if len(line) == 3 else 'p2'
        winner = 'p2' if loser == 'p1' else 'p1'
        gain = 1
    else:
        winner = 'p1' if RANK[hands[0]] > RANK[hands[1]] else 'p2'
        gain = 2 if 'call' in line else 1
    return {p: 50 + 25 * (gain if p == winner else -gain) for p in ('p1', 'p2')}


def explore_kuhn(mod, hands, line, seen):
    if mod.is_terminal():
        assert {p: goal(mod, p) for p in ('p1', 'p2')} == kuhn_goals(hands, line), (hands, line)
        seen.append(tuple(line))
        return
    moves = mod.get_legal_moves()
    acting = [p for p in ('p1', 'p2') if [str(m) for m in moves[p]] != ['noop']]
    assert len(acting) == 1
    for m in moves[acting[0]]:
        step(mod, **{acting[0]: m})
        explore_kuhn(mod, hands, line + [str(m)], seen)
        mod.undo_step()


def test_kuhn_every_deal_and_line_has_correct_payoff():
    mod = load('kuhn')
    seen = []
    deals = [(a, b) for a in RANK for b in RANK if a != b]
    for hands in deals:
        step(mod, random=Term('deal', Term(hands[0]), Term(hands[1])))
        explore_kuhn(mod, hands, [], seen)
        mod.undo_step()
    lines = {('check', 'check'), ('check', 'bet', 'fold'), ('check', 'bet', 'call'), ('bet', 'fold'), ('bet', 'call')}
    assert set(seen) == lines and len(seen) == 6 * len(lines)


def test_kuhn_legal_moves_follow_the_betting_structure():
    mod = load('kuhn')
    assert len(mod.get_legal_moves('random')) == 6
    step(mod, random=Term('deal', Term('q'), Term('k')))
    assert [str(m) for m in mod.get_legal_moves('p1')] == ['bet', 'check']
    step(mod, p1=Term('check'))
    assert [str(m) for m in mod.get_legal_moves('p2')] == ['bet', 'check']
    step(mod, p2=Term('bet'))
    assert [str(m) for m in mod.get_legal_moves('p1')] == ['call', 'fold']


def test_kuhn_beliefs_about_opponent_card():
    mod = load('kuhn')
    step(mod, random=Term('deal', Term('q'), Term('k')))
    hand = lambda p: beliefs(mod, 'p1', Term('hand', Constant(mod.player_to_id(p)), Var('C')))
    assert hand('p1') == pytest.approx({'hand(%d,q)' % mod.player_to_id('p1'): 1.0})
    p2 = mod.player_to_id('p2')
    assert hand('p2') == pytest.approx({f'hand({p2},j)': 0.5, f'hand({p2},k)': 0.5})
    step(mod, p1=Term('bet'))
    # Showdown reveals the opponent's card
    step(mod, p2=Term('call'))
    assert hand('p2') == pytest.approx({f'hand({p2},k)': 1.0})


def test_kuhn_knowing_to_hold_the_best_card():
    mod = load('kuhn')
    step(mod, random=Term('deal', Term('k'), Term('q')))
    p1, p2 = mod.player_to_id('p1'), mod.player_to_id('p2')
    assert beliefs(mod, 'p1', Term('knowsBest', Var('P'))) == pytest.approx({f'knowsBest({p1})': 1.0})
    mod.undo_step()
    step(mod, random=Term('deal', Term('q'), Term('k')))
    # p1 does not know whether p2 holds the king, p2 does
    assert beliefs(mod, 'p1', Term('knowsBest', Var('P'))) == pytest.approx({f'knowsBest({p2})': 0.5})
    assert beliefs(mod, 'p2', Term('knowsBest', Var('P'))) == pytest.approx({f'knowsBest({p2})': 1.0})


# Coordinated attack

KNOWLEDGE_OWNER = {'k1': 'gb', 'k2': 'ga', 'k3': 'gb', 'k4': 'ga'}


def play_generals(delivered, plan='attack', stop_after=5):
    """Plays the generals game where the first `delivered` messages arrive and every later message is dropped."""
    mod = load('generals')
    step(mod, random=Term('decide', Term(plan)))
    for k in range(1, stop_after):
        send = Term('send')
        moves = {p: (send if send in mod.get_legal_moves(p) else mod.get_legal_moves(p)[0]) for p in ('ga', 'gb')}
        moves['random'] = Term('deliver' if k <= delivered else 'drop')
        mod.set_actions(moves)
        mod.update_step()
    return mod


@pytest.mark.parametrize('delivered', range(5))
def test_generals_knowledge_depth_equals_delivered_messages(delivered):
    mod = play_generals(delivered)
    assert mod.is_terminal()
    for j, (level, owner) in enumerate(KNOWLEDGE_OWNER.items(), start=1):
        expected = 1.0 if j <= delivered else 0.0
        assert dict((str(t), p) for p, t in mod.query(owner, Term(level))) == pytest.approx({level: expected}), (level, delivered)
    for player in ('ga', 'gb'):
        assert mod.query(player, Term('ck')) == [(0.0, Term('ck'))]


def test_generals_message_content_matters():
    mod = play_generals(4, plan='hold')
    assert mod.query('gb', Term('k1')) == [(0.0, Term('k1'))]


def test_generals_sender_cannot_tell_loss_from_silence():
    mod = play_generals(1, stop_after=3)
    # ga sent, gb answered but the answer was dropped: ga sees nothing and weighs 1/3 for message 1 having arrived
    assert beliefs(mod, 'ga', Term('recv', Constant(1))) == pytest.approx({'recv(1)': 1 / 3})
    mod = play_generals(1, stop_after=2)
    assert beliefs(mod, 'ga', Term('recv', Constant(1))) == pytest.approx({'recv(1)': 0.5})
