# Next steps, benchmarks and comparisons

Status as of the last session: 74 fast tests pass, plus one `slow` test. The engine is an explicit possible-worlds implementation of GDL-III semantics on ProbLog. `python -m gdl_problog.play GAME` loads and plays any `.gdliii` game.

## Benchmarks (measured)

`knows` evaluation costs about 7 ms per possible world, so first-step time grows roughly linearly with the number of worlds.

| Sum-product worlds | First step |
|---|---|
| 72 | 0.3 s |
| 182 | 0.9 s |
| 342 | 1.8 s |
| 812 | 4.5 s |
| 2,352 (`sumproduct100`) | 16.4 s |

- The full `sumproduct100` dialogue takes about 17 s, of which step 0 is about 15 s. Later steps add only about 2.4 s in total.
- `python -m gdl_problog.benchmark [game ...]` times load, play and query for the examples. It does not yet include `sumproduct100`.

## Improvements

**Performance**
- Profile the per-world `knows` evaluation in `internal/GDLIIIProblogRep.py` (the main cost). Likely options are caching ground rule evaluation per state and sharing work between indistinguishable worlds.
- Add `sumproduct100` to the benchmark and record results here after each optimisation.
- Check whether the `knows` fixpoint (up to `MAX_KNOWLEDGE_ITERATIONS=50`) converges earlier on typical games and can stop sooner.

**Syntax gaps** (see `tests/test_syntax.py` for what is covered)
- Infix format has no `or`, and assumes exactly one `<=` per rule.
- The random role must be named exactly `random`.
- `problog_builtins.txt` is incomplete, so a game predicate named like an unlisted ProbLog builtin would break.

**Semantics**
- Other players are modelled as uniformly random when weighting beliefs. Allow a configurable opponent model.

**Repo**
- The game-specific `monty.py`, `muddy.py` and `number_game.py` runners have been retired; use `play.py` for interactive games.
- The stale files in `data/` (`guessmodel.prob`, `model.prob`, `testmonty.prob`, `translated.prob`, `guessinfix.gdliii`) are kept on purpose for history. Only `problog_builtins.txt` and `predicates.problog` are used.

## Next games

- More imperfect-information and probabilistic puzzles, written with `play.py` and a test each.
- Larger variants of existing games, to find where performance becomes a limit.

## Comparison with other engines

Everything in this section comes from memory or web-search summaries and has **not** been verified. Check each source before citing it.

| Tool | Kind | Why compare |
|---|---|---|
| SMCDEL | Symbolic model checker for dynamic epistemic logic | Muddy children, sum-and-product and similar puzzles. Good reference for correctness and speed on epistemic puzzles. |
| MCMAS / MCK | Model checkers for multi-agent systems | Verification of epistemic properties on larger systems. |
| DEMO | Explicit-model DEL tool | Close to our explicit-worlds design. |
| eclingo | Epistemic logic programs on ASP | Another logic-programming route to epistemic reasoning. |
| OpenSpiel | Game framework (includes imperfect-information games such as Kuhn poker) | Reference values for game outcomes. |
| ProbLog / PRISM | Probabilistic logic programming | Reference for the probabilistic part. |
| DAEDALUS, Aletheia, MEPK, deep | Recent epistemic planners | From searches. They solve planning, not GDL-III play, so compare on the shared puzzles only. |
| EPDDL | Epistemic planning language (arXiv 2601.20969) | Possible modelling language for cross-tool inputs. |
| Epistemic benchmarks for language models | "Beyond Memorization" (arXiv 2603.21350), MindGames, ToMBench | Possible source of puzzle sets. |

No released GDL-III reasoner other than this one was found.

**Suggested plan**
1. Encode muddy children (3 and 4 children) and sum-and-product in SMCDEL and compare answers with the tests in `test_examples.py` and `test_puzzles.py`.
2. Time the same puzzles on both tools for several sizes.
3. Fetch the DAEDALUS paper and the Aletheia repository and see whether any of their benchmarks map onto GDL-III games.
