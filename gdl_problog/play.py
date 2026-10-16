"""Generic runner for GDL-III games.

Usage: python -m gdl_problog.play GAME [options]
GAME is a path to a .gdliii file or the name of a file in gdl_problog/examples.

Interactive play prompts for the moves of every role that has a choice. Prompt input is a move index, the move text
or r for a random legal move. Commands start with a colon:
    :q PLAYER TERM   query the beliefs of PLAYER, TERM uses ProbLog syntax such as isMuddy(X) (capital letters are variables)
    :undo [N]        go back N steps
    :moves           show the legal moves again
    :quit
"""
import argparse
import os
import re
import sys

from problog.logic import Term, Constant, Var
from problog.program import PrologString

from . import GDLIIIEngine, File_Format, EXAMPLES_DIR

RANDOM_ROLE = 'random'


def resolve_game(game):
    if os.path.isfile(game):
        return game
    candidate = os.path.join(EXAMPLES_DIR, game if game.endswith('.gdliii') else game + '.gdliii')
    if os.path.isfile(candidate):
        return candidate
    raise FileNotFoundError("No game file or example named {}".format(game))


def detect_format(path):
    """Prefix files use (<= ...) rules or (role ...) facts, infix files use head <= body and role(...)."""
    with open(path) as f:
        text = "".join(l for l in f if not l.lstrip().startswith(";"))
    if "(<=" in text or re.search(r"\(\s*role\b", text):
        return File_Format.PREFIX
    return File_Format.INFIX


def parse_term(text):
    terms = list(PrologString(text.strip().rstrip('.') + '.'))
    if len(terms) != 1:
        raise ValueError("Expected exactly one term in {!r}".format(text))
    return terms[0]


def parse_query(text):
    parts = text.split(None, 1)
    if len(parts) != 2:
        raise ValueError("Expected a player and a term, for example: ann isMuddy(X)")
    return parts[0], parse_term(parts[1])


def format_beliefs(results):
    return "\n".join("    {:.4f}  {}".format(p, t) for p, t in results) if results else "    (nothing believed possible)"


def show_queries(mod, queries, out):
    for player, term in queries:
        try:
            out("  {} believes {}:\n{}".format(player, term, format_beliefs(mod.query(player, term))))
        except Exception as e:
            out("  query {} {} failed: {}".format(player, term, e))


def show_goals(mod, out):
    for player in mod.player_names:
        if player == RANDOM_ROLE:
            continue
        pid = Constant(mod.player_to_id(player))
        goals = ", ".join(str(t.args[1]) for _, t in mod.query(player, Term('goal', pid, Var('G'))))
        out("  goal of {}: {}".format(player, goals or "(no goal rule matches)"))


def pick(mod, player, text):
    """Resolves prompt input to one of the legal moves of the player, returns None for an invalid input."""
    legal = mod.get_legal_moves(player)
    text = text.strip()
    if text == 'r':
        return mod.rng.choice(legal)
    if text.isdigit() and int(text) < len(legal):
        return legal[int(text)]
    squashed = text.replace(" ", "")
    for m in legal:
        if str(m).replace(" ", "") == squashed:
            return m
    return None


def show_moves(mod, out):
    for player, legal in mod.get_legal_moves().items():
        out("  {}: {}".format(player, ", ".join("[{}] {}".format(i, m) for i, m in enumerate(legal))))


def play_auto(mod, strategy, queries, out, max_steps):
    steps = 0
    while not mod.is_terminal() and steps < max_steps:
        legal = mod.get_legal_moves()
        if any(len(m) == 0 for m in legal.values()):
            out("A role has no legal move, stopping.")
            return
        choose = (lambda m: m[0]) if strategy == 'first' else mod.rng.choice
        mod.set_actions({p: choose(m) for p, m in legal.items()})
        mod.update_step()
        steps += 1
        out("Step {}:".format(steps))
        show_queries(mod, queries, out)
    if mod.is_terminal():
        out("Terminal after {} steps.".format(steps))
        show_goals(mod, out)
    else:
        out("Stopped after {} steps without reaching a terminal state.".format(steps))


def play_interactive(mod, queries, choose_random, read, out):
    steps = 0
    while True:
        if mod.is_terminal():
            out("Terminal after {} steps.".format(steps))
            show_goals(mod, out)
            out("Use :undo to go back or :quit.")
        else:
            out("Step {}. Legal moves:".format(steps))
            show_moves(mod, out)
        chosen = {}
        done = False
        while not done:
            roles = [] if mod.is_terminal() else [p for p in mod.player_names
                                                  if (choose_random or p != RANDOM_ROLE) and len(mod.get_legal_moves(p)) > 1
                                                  and p not in chosen]
            prompt = "{}> ".format(roles[0]) if roles else ("(:undo, :quit)> " if mod.is_terminal() else "(enter to play)> ")
            line = read(prompt)
            if line is None:
                return
            line = line.strip()
            if line.startswith(':'):
                cmd, _, rest = line[1:].partition(' ')
                try:
                    if cmd in ('quit', 'q') and not rest:
                        return
                    elif cmd == 'q':
                        show_queries(mod, [parse_query(rest)], out)
                    elif cmd == 'undo':
                        mod.undo_step(int(rest) if rest else 1)
                        steps = mod._cur_step
                        chosen = {}
                        done = True
                    elif cmd == 'moves':
                        show_moves(mod, out)
                    else:
                        out("Unknown command :{}".format(cmd))
                except Exception as e:
                    out("Error: {}".format(e))
                continue
            if mod.is_terminal():
                continue
            if roles:
                move = pick(mod, roles[0], line if line else 'r')
                if move is None:
                    out("Not a legal move for {}.".format(roles[0]))
                    continue
                chosen[roles[0]] = move
                if len(roles) > 1:
                    continue
            #The engine samples the random role itself when it has no submitted move
            moves = {p: m[0] for p, m in mod.get_legal_moves().items() if p != RANDOM_ROLE and len(m) > 0}
            moves.update(chosen)
            try:
                mod.set_actions(moves)
                mod.update_step()
            except Exception as e:
                out("Error: {}".format(e))
                chosen = {}
                continue
            steps = mod._cur_step
            out("-- played: {}".format(", ".join("{}={}".format(p, m) for p, m in moves.items())))
            show_queries(mod, queries, out)
            done = True


def main(argv=None, read=None, out=print):
    ap = argparse.ArgumentParser(prog="python -m gdl_problog.play", description="Load and play any GDL-III game.")
    ap.add_argument('game', help="path to a .gdliii file or the name of an example")
    ap.add_argument('--format', choices=['prefix', 'infix'], help="syntax of the file, detected when omitted")
    ap.add_argument('--seed', type=int, help="seed of the random player")
    ap.add_argument('--auto', choices=['first', 'random'], help="play to the end without prompting, using the first or a random legal move for every role")
    ap.add_argument('--query', action='append', default=[], metavar='"PLAYER TERM"', help="belief query shown after every step, repeatable")
    ap.add_argument('--choose-random', action='store_true', help="prompt for the moves of the random role instead of sampling them")
    ap.add_argument('--max-steps', type=int, default=1000, help="step limit of --auto")
    args = ap.parse_args(argv)

    path = resolve_game(args.game)
    fmt = {'prefix': File_Format.PREFIX, 'infix': File_Format.INFIX}.get(args.format) or detect_format(path)
    mod = GDLIIIEngine(path, fmt, seed=args.seed)
    queries = [parse_query(q) for q in args.query]
    out("Loaded {} ({}), roles: {}".format(os.path.basename(path), fmt.name.lower(), ", ".join(mod.player_names)))
    if args.auto:
        play_auto(mod, args.auto, queries, out, args.max_steps)
    else:
        def default_read(prompt):
            try:
                return input(prompt)
            except EOFError:
                return None
        play_interactive(mod, queries, args.choose_random, read or default_read, out)


if __name__ == "__main__":
    main()
