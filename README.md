# GDL-III (Thielscher & Schiffel, IJCAI-17) on ProbLog

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

g = GDLIIIEngine(EXAMPLES_DIR + '/montyhall.gdliii', File_Format.INFIX, seed=1)
g.get_legal_moves(); g.set_actions({...}); g.update_step(); g.query('candidate', term)
```

`seed` fixes the random player's moves; `g.rng` is the same generator, for callers that need reproducible choices.

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
