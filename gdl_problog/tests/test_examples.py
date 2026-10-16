import os
import random
from itertools import product

import pytest
from problog.logic import Term, Constant, Var

from gdl_problog import GDLIIIEngine, File_Format, EXAMPLES_DIR


def load(name, fmt=File_Format.PREFIX, seed=0):
    return GDLIIIEngine(os.path.join(EXAMPLES_DIR, f'{name}.gdliii'), fmt, seed=seed)


def play_muddy(example, pattern):
    """Plays the muddy children game for the given pattern (1 = muddy). Returns the say-moves per step and the final engine."""
    mod = load(example)
    children = [p for p in mod.player_names if p != 'random']
    said = []
    first = True
    while not mod.is_terminal():
        moves = mod.get_legal_moves()
        mov = {c: moves[c][0] for c in children}
        mov['random'] = Term('muddy', *[Constant(int(c)) for c in pattern]) if first else moves['random'][0]
        first = False
        mod.set_actions(mov)
        mod.update_step()
        said.append({c: str(mov[c]) for c in children})
    return said, mod


def muddy_cases(n):
    return [''.join(p) for p in product('01', repeat=n) if '1' in p]


@pytest.mark.parametrize('example,n', [('muddy', 2), ('muddy3', 3), ('muddy4', 4)])
def test_muddy_children_all_patterns(example, n):
    """With k muddy children, all of them first say yes in round k and the clean ones are silent until they deduce it."""
    for pattern in muddy_cases(n):
        k = pattern.count('1')
        said, _ = play_muddy(example, pattern)
        # said[0] is the random setup step, said[r] is round r
        children = list(said[1].keys())
        for r in range(1, k):
            assert all(v == 'say(no)' for v in said[r].values()), (pattern, r, said)
        assert said[k] == {c: ('say(yes)' if pattern[i] == '1' else 'say(no)') for i, c in enumerate(children)}, (pattern, said)


def test_muddy_all_muddy_three_children_regression():
    said, _ = play_muddy('muddy3', '111')
    assert [all(v == 'say(no)' for v in s.values()) for s in said[1:3]] == [True, True]
    assert all(v == 'say(yes)' for v in said[3].values())


def test_muddy_clean_children_learn_after_muddy_speak():
    said, mod = play_muddy('muddy3', '110')
    assert said[2]['cat'] == 'say(no)'
    # cat deduces it is clean once the muddy children have answered
    p = dict((str(t), pr) for pr, t in mod.query('cat', Term('isMuddy', Constant(3))))
    assert p['isMuddy(3)'] == pytest.approx(0.0)


def test_muddy_belief_before_any_announcement():
    mod = load('muddy3')
    mod.set_actions({'ann': mod.get_legal_moves('ann')[0], 'bob': mod.get_legal_moves('bob')[0],
                     'cat': mod.get_legal_moves('cat')[0],
                     'random': Term('muddy', Constant(1), Constant(1), Constant(0))})
    mod.update_step()
    # ann sees one muddy child, so she believes she is muddy with probability 0.5
    assert mod.query('ann', Term('isMuddy', Constant(1)))[0][0] == pytest.approx(0.5)


def test_montyhall_beliefs_and_strategy():
    mod = load('montyhall', File_Format.INFIX)
    assert set(mod.player_names) == {'candidate', 'random'}
    mod.set_actions({'candidate': mod.get_legal_moves('candidate')[0]})  # choose(1)
    mod.update_step()
    mod.set_actions({'candidate': mod.get_legal_moves('candidate')[0]})
    mod.update_step()
    # the car is in the chosen door with probability 1/3 and in the other closed door with probability 2/3
    probs = {str(t): p for p, t in mod.query('candidate', Term('car', Var('_')))}
    assert sorted(round(p, 6) for p in probs.values()) == [round(1 / 3, 6), round(2 / 3, 6)]
    assert probs['car(1)'] == pytest.approx(1 / 3)
    assert sum(probs.values()) == pytest.approx(1.0)


def test_montyhall_switching_wins_two_thirds():
    random.seed(1)
    mod = load('montyhall', File_Format.INFIX)
    wins = 0
    games = 300
    for _ in range(games):
        mod.set_actions({'candidate': random.choice(mod.get_legal_moves('candidate'))})
        mod.update_step()
        mod.set_actions({'candidate': mod.get_legal_moves('candidate')[0]})
        mod.update_step()
        mod.set_actions({'candidate': mod.get_legal_moves('candidate')[1]})  # switch
        mod.update_step()
        assert mod.is_terminal()
        goal = mod.query('candidate', Term('goal', Constant(1), Var('_')))[0][1]
        wins += str(goal) == 'goal(1,100)'
        mod.undo_step(3)
    assert 0.55 < wins / games < 0.78


def test_undo_restores_state():
    mod = load('montyhall', File_Format.INFIX)
    before = mod.get_legal_moves()
    mod.set_actions({'candidate': before['candidate'][0]})
    mod.update_step()
    assert mod.get_legal_moves() != before
    mod.undo_step()
    assert mod.get_legal_moves() == before
    with pytest.raises(Exception):
        mod.undo_step()


def test_lookahead_query_montyhall():
    mod = load('montyhall', File_Format.INFIX)
    mod.set_actions({'candidate': mod.get_legal_moves('candidate')[0]})
    mod.update_step()
    mod.set_actions({'candidate': mod.get_legal_moves('candidate')[0]})
    mod.update_step()
    # Before choosing, goal beliefs one step ahead average over the two possible actions (noop wins 1/3, switch 2/3)
    goals = {str(t): p for p, t in mod.query('candidate', Term('goal', Constant(1), Var('_')), 1)}
    assert sum(goals.values()) == pytest.approx(1.0)
    assert goals['goal(1,100)'] == pytest.approx(0.5)


def test_undo_and_replay_gives_same_beliefs():
    mod = load('muddy3')
    def run():
        mod.set_actions({'ann': mod.get_legal_moves('ann')[0], 'bob': mod.get_legal_moves('bob')[0],
                         'cat': mod.get_legal_moves('cat')[0],
                         'random': Term('muddy', Constant(1), Constant(1), Constant(1))})
        mod.update_step()
        return mod.query('ann', Term('isMuddy', Constant(1)))
    first = run()
    mod.undo_step()
    assert run() == first


def test_illegal_action_rejected():
    mod = load('montyhall', File_Format.INFIX)
    with pytest.raises(Exception):
        mod.set_actions({'candidate': Term('open_door', Constant(1))})


def test_guess_number_binary_search():
    mod = load('guess')
    mod.set_actions({'player': mod.get_legal_moves('player')[0], 'random': Term('choose', Constant(5))})
    mod.update_step()
    guesses = 0
    while not mod.is_terminal():
        possible = sorted(int(str(t.args[0])) for _, t in mod.query('player', Term('secret', Var('_'))))
        mid = possible[len(possible) // 2]
        mod.set_actions({'player': Term('ask_if_less', Constant(mid))})
        mod.update_step()
        guesses += 1
        assert guesses <= 12
    result = mod.query('player', Term('secret', Var('_')))
    assert len(result) == 1 and str(result[0][1]) == 'secret(5)'
    assert result[0][0] == pytest.approx(1.0)


def play_birthday(month, day):
    mod = load('birthday')
    mod.set_actions({'albert': mod.get_legal_moves('albert')[0], 'bernard': mod.get_legal_moves('bernard')[0],
                     'cheryl': Term('choose', Term(month), Constant(day))})
    mod.update_step()
    return mod


def advance(mod, **chosen):
    moves = {p: mod.get_legal_moves(p)[0] for p in ('albert', 'bernard', 'cheryl')}
    moves.update({p: Term(m) for p, m in chosen.items()})
    mod.set_actions(moves)
    mod.update_step()


def test_birthday_cheryl_july_16():
    mod = play_birthday('jul', 16)
    assert [str(m) for m in mod.get_legal_moves('albert')] == ['sayUnknown']
    advance(mod, albert='sayUnknown')
    assert [str(m) for m in mod.get_legal_moves('bernard')] == ['sayKnown']
    advance(mod, bernard='sayKnown')
    assert [str(m) for m in mod.get_legal_moves('albert')] == ['sayKnown']
    advance(mod, albert='sayKnown')
    assert mod.is_terminal()
    assert mod.query('albert', Term('birthday', Var('M'), Var('D')))[0][0] == pytest.approx(1.0)
    assert str(mod.query('bernard', Term('birthday', Var('M'), Var('D')))[0][1]) == 'birthday(jul,16)'


@pytest.mark.parametrize('month,day', [('may', 15), ('may', 19), ('jun', 18), ('jun', 17)])
def test_birthday_albert_cannot_claim_ignorance_in_may_june(month, day):
    # Albert only knows that Bernard cannot know the date if the month has no unique day
    assert play_birthday(month, day).get_legal_moves('albert') == []


@pytest.mark.parametrize('month,day', [('jul', 14), ('aug', 14), ('aug', 15), ('aug', 17)])
def test_birthday_only_july_16_is_solved(month, day):
    mod = play_birthday(month, day)
    assert [str(m) for m in mod.get_legal_moves('albert')] == ['sayUnknown']
    advance(mod, albert='sayUnknown')
    bernard_knows = [str(m) for m in mod.get_legal_moves('bernard')] == ['sayKnown']
    assert bernard_knows == ((month, day) in [('aug', 15), ('aug', 17)])
    if bernard_knows:
        advance(mod, bernard='sayKnown')
        # Albert cannot tell 15 from 17 in August
        assert mod.get_legal_moves('albert') == []


def write_game(tmp_path, text):
    p = tmp_path / 'game.gdliii'
    p.write_text(text)
    return str(p)


def test_comment_lines_may_contain_brackets(tmp_path):
    path = tmp_path / 'game.gdliii'
    path.write_text('; a comment (with brackets) and a 0.\n(role a) (role random)\n(init p)\n(<= (legal a go) (true p))\n(<= (legal random noop) (true p))\n(<= terminal (does a go))\n')
    mod = GDLIIIEngine(str(path), File_Format.PREFIX)
    assert sorted(mod.player_names) == ['a', 'random']


def test_missing_file_rejected():
    with pytest.raises(FileNotFoundError):
        GDLIIIEngine('does_not_exist.gdliii', File_Format.PREFIX)


@pytest.mark.parametrize('text', ['(role a) (<= (legal a x) (true', '(role a)) (init p)', '(role a) (<= (legal a x) (true p)'])
def test_unmatched_parentheses_rejected(tmp_path, text):
    with pytest.raises(ValueError, match='parentheses'):
        GDLIIIEngine(write_game(tmp_path, text), File_Format.PREFIX)


def test_no_roles_rejected(tmp_path):
    with pytest.raises(ValueError, match='role'):
        GDLIIIEngine(write_game(tmp_path, '(init p) (<= terminal (true p))'), File_Format.PREFIX)


def test_unknown_player_and_random_query_rejected():
    mod = load('montyhall', File_Format.INFIX)
    with pytest.raises(Exception):
        mod.query('nobody', Term('car', Var('_')))
    with pytest.raises(Exception):
        mod.query('random', Term('car', Var('_')))


def test_update_without_all_moves_rejected():
    mod = load('muddy3')
    with pytest.raises(Exception):
        mod.update_step()


def test_seed_makes_random_player_reproducible():
    def run(seed):
        mod = load('montyhall', File_Format.INFIX, seed=seed)
        mod.set_actions({'candidate': mod.get_legal_moves('candidate')[0]})
        mod.update_step()
        mod.set_actions({'candidate': mod.get_legal_moves('candidate')[0]})
        mod.update_step()
        return sorted((str(t), p) for p, t in mod.query('candidate', Term('car', Var('_'))))
    assert run(7) == run(7)


def test_cannot_step_past_terminal():
    mod = load('montyhall', File_Format.INFIX)
    for i in range(3):
        mod.set_actions({'candidate': mod.get_legal_moves('candidate')[0]})
        mod.update_step()
    assert mod.is_terminal()
    with pytest.raises(Exception):
        mod.update_step()
