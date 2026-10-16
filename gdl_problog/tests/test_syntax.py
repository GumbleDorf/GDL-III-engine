import pytest
from problog.logic import Term, Var

from gdl_problog import GDLIIIEngine, File_Format

HEADER = """
(role a) (role random)
(<= (legal a go) (true (c 1)))
(<= (legal random x) (true (c 1)))
(init (c 1)) (init (c 2)) (init (c 3))
(<= terminal (true (c 9)))
(<= (goal a 100) (true (c 9)))
(<= (goal random 0) (true (c 9)))
"""


def answers(tmp_path, rules, pred, arity=1, header=HEADER):
    path = tmp_path / "g.gdliii"
    path.write_text(header + rules)
    mod = GDLIIIEngine(str(path), File_Format.PREFIX, seed=0)
    result = mod.query("a", Term(pred, *[Var(f"V{i}") for i in range(arity)]))
    return {tuple(str(x) for x in t.args) for _, t in result} if arity else {() for _ in result}


def test_distinct(tmp_path):
    got = answers(tmp_path, "(<= (p ?x ?y) (true (c ?x)) (true (c ?y)) (distinct ?x ?y))", "p", 2)
    assert got == {(str(x), str(y)) for x in (1, 2, 3) for y in (1, 2, 3) if x != y}


def test_or(tmp_path):
    got = answers(tmp_path, "(<= (p ?x) (true (c ?x)) (or (true (c 1)) (true (c 3))))", "p")
    assert got == {("1",), ("2",), ("3",)}
    got = answers(tmp_path, "(<= (q ?x) (true (c ?x)) (or (true (c 7)) (true (c 8))))", "q")
    assert got == set()


def test_not(tmp_path):
    got = answers(tmp_path, "(<= (p ?x) (true (c ?x)) (not (true (c 2))))", "p")
    assert got == set()
    got = answers(tmp_path, "(<= (p ?x) (true (c ?x)) (not (true (c 7))))", "p")
    assert got == {("1",), ("2",), ("3",)}


def test_arithmetic(tmp_path):
    got = answers(tmp_path, "(<= (p ?z) (true (c ?x)) (is ?z (+ ?x 10)))", "p")
    assert got == {("11",), ("12",), ("13",)}


def test_comparison(tmp_path):
    got = answers(tmp_path, "(<= (p ?x) (true (c ?x)) (> ?x 1))", "p")
    assert got == {("2",), ("3",)}


def test_nested_terms(tmp_path):
    got = answers(tmp_path, "(<= (p (f (g ?x))) (true (c ?x)))", "p")
    assert got == {("f(g(1))",), ("f(g(2))",), ("f(g(3))",)}


def test_iteration_shorthand(tmp_path):
    header = HEADER.replace("(init (c 1)) (init (c 2)) (init (c 3))", "(init (c 1)) (init (c 2)) ... (init (c 5))")
    got = answers(tmp_path, "(<= (p ?x) (true (c ?x)))", "p", header=header)
    assert got == {(str(i),) for i in range(1, 6)}


def test_trailing_comment_is_ignored(tmp_path):
    rules = "(<= (p ?x) (true (c ?x))) ; (init (c 9)) trailing\n"
    assert answers(tmp_path, rules, "p") == {("1",), ("2",), ("3",)}


def test_capitalised_atoms(tmp_path):
    header = HEADER.replace("(role a)", "(role A)").replace("(legal a", "(legal A").replace("(goal a", "(goal A")
    header = header.replace("(c ", "(C ")
    path = tmp_path / "g.gdliii"
    path.write_text(header + "(<= (Fact ?x) (true (C ?x)))")
    mod = GDLIIIEngine(str(path), File_Format.PREFIX, seed=0)
    assert [str(m) for m in mod.get_legal_moves("A")] == ["go"]
    got = {str(t) for _, t in mod.query("A", Term("Fact", Var("X")))}
    assert got == {"Fact(1)", "Fact(2)", "Fact(3)"}


def test_builtin_name_clash_is_renamed(tmp_path):
    got = answers(tmp_path, "(<= (member ?x) (true (c ?x)))", "member")
    assert got == {("1",), ("2",), ("3",)}
