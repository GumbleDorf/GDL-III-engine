# GDL-III (Thielscher & Schiffel, IJCAI-17) on ProbLog

Implementation of GDL-III epistemic game descriptions. Game rules are evaluated with ProbLog and knowledge (`knows/1,2`) is computed over explicit possible play sequences.

## Setup and tests

```
pip install -r gdl_problog/requirements.txt pytest
cd gdl_problog
python -m pytest
```

## Usage

Run from `gdl_problog/` (modules import `internal.*` relative to it):

```python
from GDLIIIEngine import GDLIIIEngine
from internal.GDLIIIParser import File_Format

g = GDLIIIEngine('./examples/montyhall.gdliii', File_Format.INFIX)
g.get_legal_moves(); g.set_actions({...}); g.update_step(); g.query('candidate', term)
```

Examples are in `gdl_problog/examples/` (`.gdliii`, prefix or infix syntax); demo scripts: `monty.py`, `muddy.py`, `number_game.py`.
