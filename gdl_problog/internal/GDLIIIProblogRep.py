from collections import defaultdict
from itertools import product
from problog.program import PrologString
from problog.engine import DefaultEngine, UnknownClause
from problog.logic import Term, Constant, Var
from .GDLIIIParser import GDLIIIParser, File_Format

#Marker used to declare predicates that may have no clauses in a game description. Anything derived from it is discarded.
DUMMY = "epi_dummy"
PREAMBLE = (f"ptrue({DUMMY}). does({DUMMY},{DUMMY}). knows({DUMMY},{DUMMY}). knows({DUMMY}). epi_cand({DUMMY}).\n"
            f"next({DUMMY}). sees({DUMMY},{DUMMY}). epi_out({DUMMY}).\n"
            "epi_out(next(F)) :- next(F).\nepi_out(sees(R,P)) :- sees(R,P).\n")
MAX_KNOWLEDGE_ITERATIONS = 50


class Seq(object):
    """A legal play sequence (Definition 3 of Thielscher & Schiffel, IJCAI-17) together with the state and knowledge it results in."""
    __slots__ = ("parent", "state", "hist", "moves", "factors", "knows", "db", "legal", "terminal",
                 "layer", "children", "succ", "cand", "held")

    def __init__(self, parent, state, hist, moves, factors):
        self.parent = parent
        self.state = state
        #Per role: the moves and percepts of that role so far, two sequences are indistinguishable for a role iff these are equal
        self.hist = hist
        self.moves = moves
        #Per role: product of 1/(number of legal moves), the prior probability of the moves taken by the other roles
        self.factors = factors
        self.knows = frozenset()
        self.db = None
        self.legal = None
        self.terminal = None
        self.layer = None
        self.children = {}
        #Successor sequences by joint move, only used along the actual play
        self.succ = {}
        #Cached evaluation results, valid as long as db is not rebuilt
        self.cand = None
        self.held = {}


class Layer(object):
    """The sequences of one length that are connected to the actual play via indistinguishability relations (closed under them)."""
    def __init__(self, nodes):
        self.nodes = nodes


class GDLIIIProblogRep(object):
    """
    Explicit possible-worlds implementation of GDL-III semantics.
    Only the sequences that are indistinguishable (transitively, for any player) from the actual play are kept, as
    knowledge of a sequence only depends on those. The random player does not take part in indistinguishability.
    """
    def __init__(self, program, fformat):
        self._engine = DefaultEngine()
        self._model = GDLIIIParser().output_model(program, fformat)
        self._randomIdentifier = Constant(0)
        knowsArgs = self._model.knows_arguments()
        self._common = any(a == 1 for (a, _) in knowsArgs)
        candidateRules = "".join(f"epi_cand({arg}) :- {arg}.\n" for (_, arg) in dict.fromkeys(knowsArgs))
        self._base = self._engine.prepare(PrologString(PREAMBLE + self._model.as_plain_problog() + "\n" + candidateRules))

        self._playerList = []
        roleTerms = self._ask(self._base, Term('role', Var('R')))
        self._roles = sorted(set(self._role_id(t.args[0]) for t in roleTerms))
        if len(self._roles) == 0:
            raise ValueError("The game description does not define any role")
        self._playerList = [Constant(r) for r in self._roles]
        self._knowers = [i for i, r in enumerate(self._roles) if r != 0]
        self._steps = 0

        root = Seq(None, frozenset(t.args[0] for t in self._ask(self._base, Term('init', Var('F')))),
                   tuple(() for _ in self._roles), (),
                   tuple(1.0 for _ in self._roles))
        self._finalise([root])
        root.layer = Layer([root])
        self._cur_node = root
        self._moveList = dict([(i, None) for i in self._playerList])
        self.terminal = bool(root.terminal)

    @staticmethod
    def _role_id(term):
        return int(str(term))

    #Evaluation of the game rules

    def _ask(self, db, term):
        try:
            results = self._engine.query(db, term)
        except UnknownClause:
            return []
        out = []
        for args in results:
            t = Term(term.functor, *args)
            if DUMMY not in str(t):
                out.append(t)
        return out

    def _holds(self, db, term):
        return len(self._ask(db, term)) > 0

    def _facts_db(self, node):
        db = self._base.extend()
        for f in node.state:
            db += Term('ptrue', f)
        for k in node.knows:
            db += k
        return db

    @staticmethod
    def _normalise(term):
        if isinstance(term, Var):
            return term
        if isinstance(term, Constant):
            if isinstance(term.value, str) and term.value.lstrip('-').isdigit():
                return Constant(int(term.value))
            return term
        if isinstance(term, Term):
            return Term(term.functor, *[GDLIIIProblogRep._normalise(a) for a in term.args])
        return term

    #Knowledge (Definition 3)

    @staticmethod
    def _classes(nodes, idx):
        classes = defaultdict(list)
        for n in nodes:
            classes[n.hist[idx]].append(n)
        return classes

    #Sets the knowledge, database, legal move and terminal information of every node of a set of sequences closed under indistinguishability
    def _finalise(self, nodes):
        classes = {i: self._classes(nodes, i) for i in self._knowers}
        common = {}
        if self._common:
            parent = {n: n for n in nodes}
            def find(n):
                while parent[n] is not n:
                    parent[n] = parent[parent[n]]
                    n = parent[n]
                return n
            for i in self._knowers:
                for group in classes[i].values():
                    for n in group[1:]:
                        parent[find(n)] = find(group[0])
            groups = defaultdict(list)
            for n in nodes:
                groups[find(n)].append(n)
            common = {n: groups[find(n)] for n in nodes}

        for n in nodes:
            n.knows = frozenset()
            n.db = None
        for _ in range(MAX_KNOWLEDGE_ITERATIONS):
            #Only nodes whose knowledge changed need a new database and fresh evaluations
            for n in nodes:
                if n.db is None:
                    n.db = self._facts_db(n)
                    n.cand = None
                    n.held = {}
            def holds(node, p):
                if p not in node.held:
                    node.held[p] = self._holds(node.db, p)
                return node.held[p]
            newKnows = {}
            for n in nodes:
                if n.cand is None:
                    n.cand = [c.args[0] for c in self._ask(n.db, Term('epi_cand', Var('P')))]
                known = set()
                for p in n.cand:
                    for i in self._knowers:
                        if all(holds(m, p) for m in classes[i][n.hist[i]]):
                            known.add(Term('knows', Constant(self._roles[i]), p))
                    if self._common and all(holds(m, p) for m in common[n]):
                        known.add(Term('knows', p))
                newKnows[n] = frozenset(known)
            changed = False
            for n in nodes:
                if newKnows[n] != n.knows:
                    n.knows = newKnows[n]
                    n.db = None
                    changed = True
            if not changed:
                break
        else:
            raise Exception("Knowledge did not converge, the game description may use knows cyclically")

        for n in nodes:
            n.terminal = self._holds(n.db, Term('terminal'))

    def _legal(self, node):
        if node.legal is None:
            legal = {r: [] for r in self._roles}
            for t in self._ask(node.db, Term('legal', Var('R'), Var('M'))):
                r = self._role_id(t.args[0])
                if r in legal and t.args[1] not in legal[r]:
                    legal[r].append(t.args[1])
            for r in legal:
                legal[r].sort(key=str)
            node.legal = legal
        return node.legal

    #Successor sequences

    def _successor(self, node, combo, legal):
        db = node.db.extend()
        for r, m in zip(self._roles, combo):
            db += Term('does', Constant(r), m)
        state = set()
        percepts = defaultdict(set)
        for t in self._ask(db, Term('epi_out', Var('X'))):
            out = t.args[0]
            if out.functor == 'next':
                state.add(out.args[0])
            else:
                percepts[self._role_id(out.args[0])].add(out.args[1])
        state = frozenset(state)
        hist = tuple(node.hist[i] + ((combo[i], frozenset(percepts[r])),) for i, r in enumerate(self._roles))
        factors = tuple(node.factors[i] / len(legal[r]) for i, r in enumerate(self._roles))
        return Seq(node, state, hist, tuple(combo), factors)

    def _cached_successor(self, node, combo):
        if combo not in node.succ:
            node.succ[combo] = self._successor(node, combo, self._legal(node))
        return node.succ[combo]

    #All successors of the given sequences. Moves in forced (role id -> move) are the only moves considered for those roles.
    def _expand(self, nodes, forced=None):
        out = []
        for n in nodes:
            if n.terminal:
                continue
            legal = self._legal(n)
            options = []
            for r in self._roles:
                if forced is not None and r in forced:
                    options.append([forced[r]] if forced[r] in legal[r] else [])
                else:
                    options.append(legal[r])
            for combo in product(*options):
                out.append(self._successor(n, combo, legal))
        return out

    #The set of sequences of the next layer that is indistinguishable (transitively) from start.
    #Indistinguishable sequences of a role share the move of that role, so only the successors that take one of the moves
    #already found for some role are generated, which avoids expanding every joint move of every sequence.
    def _component(self, layer, start):
        allowed = {i: {start.moves[i]} for i in self._knowers}
        while True:
            index = defaultdict(list)
            for n in layer.nodes:
                if n.terminal:
                    continue
                legal = self._legal(n)
                for combo in product(*[legal[r] for r in self._roles]):
                    if any(combo[i] in allowed[i] for i in self._knowers):
                        c = self._cached_successor(n, combo)
                        for i in self._knowers:
                            index[(i, c.hist[i])].append(c)
            seen = {start}
            stack = [start]
            while stack:
                c = stack.pop()
                for i in self._knowers:
                    for d in index[(i, c.hist[i])]:
                        if d not in seen:
                            seen.add(d)
                            stack.append(d)
            grew = False
            for c in seen:
                for i in self._knowers:
                    if c.moves[i] not in allowed[i]:
                        allowed[i].add(c.moves[i])
                        grew = True
            if not grew:
                return list(seen)

    #Interface

    def getMoveList(self):
        return self._moveList

    def undo(self, increment=1):
        for _ in range(increment):
            self._cur_node = self._cur_node.parent
        self._steps -= increment
        self._moveList = dict([(i, None) for i in self._playerList])
        self.terminal = bool(self._cur_node.terminal)

    #Legal moves of a player (Constant id) in the actual state, as a list of move terms
    def getLegalMovesForPlayer(self, player):
        return list(self._legal(self._cur_node)[self._role_id(player)])

    def submitAction(self, action, player):
        if action not in self.getLegalMovesForPlayer(player):
            raise Exception("{} is not a legal action".format(action))
        self._moveList[player] = action

    def applyActionsToModelAndUpdate(self):
        if (None in self._moveList.values()):
            raise Exception("Error: Must have submitted moves for all players before proceeding")
        node = self._cur_node
        combo = tuple(self._moveList[Constant(r)] for r in self._roles)
        if combo not in node.children:
            layer = node.layer
            child = self._cached_successor(node, combo)
            if child.layer is None:
                members = self._component(layer, child)
                newLayer = Layer(members)
                self._finalise(members)
                for m in members:
                    m.layer = newLayer
            node.children[combo] = child
        self._cur_node = node.children[combo]
        self._steps += 1
        self.terminal = bool(self._cur_node.terminal)
        self._moveList = dict([(i, None) for i in self._playerList])

    def _prior(self, node, observer):
        w = 1.0
        for i, f in enumerate(node.factors):
            if i != observer:
                w *= f
        return w

    #Probability distribution of the instances of query that the player considers possible, conditioned on everything the player has observed.
    #With step > 0, the distribution is over the state after the player takes every possible sequence of step actions (averaged),
    #without conditioning on observations that have not been made yet.
    def query(self, player, query, step=0):
        query = self._normalise(query)
        observer = self._roles.index(self._role_id(player))
        actual = self._cur_node
        info = [n for n in actual.layer.nodes if n.hist[observer] == actual.hist[observer]]
        if step == 0:
            results = [self._answer(info, observer, query)]
        else:
            results = [self._answer(final, observer, query) for final in self._speculate(info, actual.layer.nodes, observer, step)]
        total = defaultdict(float)
        for r in results:
            for (k, v) in r.items():
                total[k] += v / len(results)
        if len(results) == 0 or (len(total) == 0 and len(query.variables()) == 0):
            total[query] = 0.0
        return dict(total)

    #A query matches derived predicates as well as state fluents
    def _ask_query(self, db, query):
        found = set(self._ask(db, query))
        for t in self._ask(db, Term('ptrue', query)):
            found.add(t.args[0])
        return found

    def _answer(self, nodes, observer, query):
        weights = [self._prior(n, observer) for n in nodes]
        norm = sum(weights)
        out = defaultdict(float)
        if norm == 0:
            return out
        for n, w in zip(nodes, weights):
            for t in self._ask_query(n.db, query):
                out[t] += w / norm
        return out

    #Yields the possible info sets (successors of the info set) after the player took each possible sequence of step actions
    def _speculate(self, info, layer, observer, step):
        role = self._roles[observer]
        if step == 0:
            yield info
            return
        infoSet = set(info)
        actions = []
        for n in layer:
            if n in infoSet:
                for m in self._legal(n)[role]:
                    if m not in actions:
                        actions.append(m)
        for a in actions:
            successors = self._expand(layer, {role: a})
            if len(successors) == 0:
                continue
            members = set(successors)
            #Successors are closed under indistinguishability since their prefixes are
            nodes = list(members)
            self._finalise(nodes)
            newInfo = [n for n in nodes if n.parent in infoSet]
            if len(newInfo) > 0:
                yield from self._speculate(newInfo, nodes, observer, step - 1)
