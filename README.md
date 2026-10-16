# GDL-III on ProbLog

Implementation of GDL-III epistemic game descriptions. Game rules are evaluated with ProbLog and knowledge (`knows/1,2`) is computed over explicit possible play sequences.

## Setup and tests

Run everything from the repository root.

```
pip install -e .[dev]     # or: pip install -r requirements.txt
python -m pytest
```

## Usage

```python
from gdl_problog import GDLIIIEngine, File_Format, EXAMPLES_DIR

g = GDLIIIEngine(EXAMPLES_DIR + '/guess.gdliii', File_Format.PREFIX, seed=1)
g.get_legal_moves(); g.set_actions({...}); g.update_step(); g.query('candidate', term)
```

`seed` fixes the random player's moves; `g.rng` is the same generator, for callers that need reproducible choices.

## GDL-III syntax: prefix and infix

**Prefix form is recommended for new games.** It is the more expressive of the two supported notations and makes rule structure explicit. Infix form is available for programs written in a more Prolog-like style. Both are translated to the same internal model, so choosing a notation does not change the game semantics.

These rules express the same legal move.

Prefix:

```lisp
(<= (legal player (ask_if_less ?n))
    (number ?n)
    (not (true (step 0))))
```

Infix:

```prolog
legal(player, ask_if_less(?n)) <= number(?n), not true(step(0)).
```

| | Prefix (recommended) | Infix |
|---|---|---|
| Facts and terms | `(role player)`, `(true (step 0))` | `role(player).`, `true(step(0)).` |
| Rules | `(<= HEAD BODY...)`; multiple body terms mean conjunction | `HEAD <= BODY, BODY.`; commas mean conjunction |
| Alternatives | Can be written explicitly with `(or ...)`, including inside a rule body | Write alternatives as separate rules with the same head; there is no direct infix equivalent of `(or ...)` |
| Repeated facts | Supports the `...` shorthand between two compatible terms, such as `(number 1) ... (number 32)` | No equivalent shorthand; write out each fact or generate the program externally |

Both parsers implement this project's supported GDL-III subset; neither is a general Prolog parser or a complete parser for every GDL dialect. Infix parsing is deliberately simple: periods end statements, commas split top-level rule-body terms, and the supported rule form is `head <= body, ...`. Use the documented terms and `not` form rather than relying on arbitrary Prolog operators or expression syntax. Prefix form also has parser constraints, but its explicit nesting and `(or ...)` form cover the constructs used by the examples more directly.

The command-line runner guesses the format from the file's opening syntax. If a file is ambiguous, set it explicitly with `--format prefix` or `--format infix`; the Python API takes `File_Format.PREFIX` or `File_Format.INFIX`.

Examples are in `gdl_problog/examples/` (`.gdliii`, prefix or infix syntax). Lines starting with `;` are comments.

| Game | Roles | What it demonstrates |
|---|---|---|
| `montyhall` | candidate | 1/3 vs 2/3 posterior |
| `montyfall` | candidate | host opens at random, a revealed goat gives 1/2 vs 1/2 |
| `threeprisoners` | ann | named prisoner is never pardoned, so the other one rises to 2/3 |
| `muddy`, `muddy3`, `muddy4` | children | nested knowledge via public announcements |
| `birthday`, `sumproduct` | two speakers | Cheryl's birthday and Freudenthal's puzzle (solution 1 and 4) |
| `sumproduct100` | two speakers | classic range 2 to 100 (2,352 worlds, about 17s, solution 4 and 13). Run `pytest -m "not slow"` to skip |
| `mostbaffling` | reader | sequential nested-knowledge puzzle; a random public relabeling makes the guilty identity uniform, and the final report identifies it |
| `russiancards` | alice, bob, eve | Alice announces a Fano plane; Bob learns her hand while Eve cannot identify any one of her cards |
| `whatquestion` | alice | choosing a yes/no query to decode a response whose truthfulness and symbol meaning depend on hidden state |
| `whoismad` | alice | nested, potentially false beliefs; the Knave of Hearts is sane in every assignment satisfying the gardeners' six claims |
| `guess` | player | binary search with yes/no percepts |
| `kuhn` | p1, p2 | imperfect information poker with showdown payoffs |
| `generals` | ga, gb | nested knowledge `k1`..`k4` grows per delivered message, common knowledge never |

Scripts:

```
python -m gdl_problog.play GAME [--auto first|random] [--seed N] [--query "PLAYER TERM"] [--choose-random]
```

`play` is the generic runner: `GAME` is a path to any `.gdliii` file or the name of an example, and the syntax (prefix or infix) is detected. Without `--auto` it prompts for moves (index, move text or `r` for random) and understands `:q PLAYER TERM`, `:undo [N]`, `:moves` and `:quit`. Queries use ProbLog syntax where capital letters are variables, e.g. `--query "ann isMuddy(X)"` is shown after every step. For example:

```
python -m gdl_problog.play generals --auto random --seed 3 --query "ga k2"
python -m gdl_problog.play kuhn
python -m gdl_problog.play path/to/new_game.gdliii --auto first
```

Older single-game demos:

```
python -m gdl_problog.monty
python -m gdl_problog.muddy muddy3 110
python -m gdl_problog.number_game
python -m gdl_problog.benchmark [game ...]   # load/play/query timings
```

## References

- Michael Thielscher. [“GDL-III: A Description Language for Epistemic General Game Playing”](https://doi.org/10.24963/ijcai.2017/177). *Proceedings of the 26th International Joint Conference on Artificial Intelligence (IJCAI-17)*, 2017.
