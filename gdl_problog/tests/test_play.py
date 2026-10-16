import os

import pytest
from problog.logic import Term, Var

from gdl_problog import File_Format, EXAMPLES_DIR
from gdl_problog import play


def run(argv, inputs=()):
    lines = []
    queue = list(inputs)
    play.main(argv, read=lambda prompt: queue.pop(0) if queue else None, out=lines.append)
    return "\n".join(lines)


def test_format_detection_on_all_examples():
    infix = {'montyhall'}
    for name in os.listdir(EXAMPLES_DIR):
        expected = File_Format.INFIX if name[:-len('.gdliii')] in infix else File_Format.PREFIX
        assert play.detect_format(os.path.join(EXAMPLES_DIR, name)) == expected, name


def test_resolve_game_by_name_and_path_and_missing():
    path = os.path.join(EXAMPLES_DIR, 'kuhn.gdliii')
    assert play.resolve_game('kuhn') == play.resolve_game(path) == path
    with pytest.raises(FileNotFoundError):
        play.resolve_game('no_such_game')


def test_parse_query_variables_and_constants():
    player, term = play.parse_query('ann isMuddy(X)')
    assert player == 'ann' and isinstance(term.args[0], Var)
    assert str(play.parse_term('hand(1,q)')) == 'hand(1,q)'
    with pytest.raises(ValueError):
        play.parse_query('only_player')


def test_auto_play_infix_game_reaches_terminal_with_goal():
    out = run(['montyhall', '--auto', 'first', '--seed', '0', '--query', 'candidate car(X)'])
    assert 'montyhall.gdliii (infix)' in out
    assert 'Terminal after 3 steps' in out and 'goal of candidate: 100' in out


def test_auto_play_is_reproducible_with_seed():
    argv = ['generals', '--auto', 'random', '--seed', '5', '--query', 'gb k1']
    assert run(argv) == run(argv)


def test_auto_play_works_for_every_example():
    for name in ('muddy', 'threeprisoners', 'montyfall', 'kuhn', 'birthday', 'guess'):
        out = run([name, '--auto', 'random', '--seed', '1', '--max-steps', '20'])
        assert 'Loaded' in out and ('Terminal' in out or 'Stopped' in out or 'no legal move' in out), name


def test_interactive_session_with_query_choice_and_undo():
    out = run(['kuhn', '--seed', '0'], ['', ':q p1 hand(1,C)', 'bet', ':undo', ':moves', ':bogus', ':quit'])
    assert 'p1 believes hand(1,C)' in out
    assert 'Step 1. Legal moves' in out
    assert 'Unknown command :bogus' in out
    assert out.count('Step 1. Legal moves') >= 2  # shown again after undo


def test_interactive_rejects_illegal_move_text():
    out = run(['kuhn', '--seed', '0'], ['', 'fold', 'check', ''])
    assert 'Not a legal move for p1' in out


def test_interactive_can_choose_random_role_moves():
    out = run(['threeprisoners', '--choose-random'], ['pardon(pb)', ''])
    assert 'random=pardon(pb)' in out
    assert 'Terminal after 2 steps' in out
