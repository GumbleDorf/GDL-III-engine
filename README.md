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

Examples are in `gdl_problog/examples/` (`.gdliii`, prefix or infix syntax). Scripts:

```
python -m gdl_problog.monty
python -m gdl_problog.muddy muddy3 110
python -m gdl_problog.number_game
python -m gdl_problog.benchmark [game ...]   # load/play/query timings
```
