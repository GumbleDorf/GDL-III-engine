from problog.logic import Term, Constant,Var, Clause
from problog.program import PrologFile, PrologString,LogicProgram
from problog.engine import DefaultEngine, ClauseDB
from copy import deepcopy
from enum import Enum, auto
from io import StringIO
from .utility import NestedView
import re


import os
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

GDL_KEYWORDS = frozenset(['ptrue', 'legal', 'does', 'terminal', 'knows', 'sees', 'goal', 'init', 'next', 'role'])

#str that renders as a quoted problog atom while still comparing equal to the plain name
class _QuotedAtom(str):
    def __str__(self):
        return "'" + str.__str__(self) + "'"

#Base class of all gdl objects
class GDLMetaObject(object):
    def __init__(self, pred, *args):
        self.pred = pred
        self.args = []
        for i in args:
            if not issubclass(type(i), GDLMetaObject):
                self.args.append(GDLTerm(i))
            else:
                self.args.append(i)

    def __getitem__(self,key):
        return self.args[key]
    def __setitem__(self, key, value):
        if not issubclass(type(value), GDLMetaObject):
            self.args[key] = GDLTerm(value)
        else:
            self.args[key] = value
    def __deepcopy__(self, memo):
        return type(self)(deepcopy(self.pred, memo), *deepcopy(self.args, memo))

    def __add__(self, b):
        if type(b) == str:
            return str(self) + b
        elif type(b) == GDLMetaObject:
            return str(self) + str(b)
        else:
            raise Exception("Unexpected type in __add__ for {}".format(type(self)))
    #Number of arguments, atomic terms have length of 0
    def __len__(self):
        return len(self.args)
    def replace(self, orig, repl) -> None:
        if self.pred == orig:
            self.pred = repl
        for i in range(len(self)):
            self[i].replace(orig,repl)
    def __eq__(self, other):
        if issubclass(type(other), GDLMetaObject) or type(other) == str:
            return str(self) == str(other)
        return NotImplemented
    def __hash__(self):
        return hash(str(self))
    def generate_thinks(self, excluded_predicates = set()) -> None:
        return None
                

#Class for a rule
class GDLRule(GDLMetaObject):
    #Assumption, lhs is single term, rhs is list of 1 or more terms
    def __init__(self, lhs,*rhs):
        super().__init__(None, lhs,*rhs)
    def __str__(self):
        return f"{self.args[0]} :- " + ",".join(map(str,self.args[1:]))
    def generate_thinks(self, excluded_predicates = set()) -> GDLMetaObject:
        if self[0].pred in excluded_predicates:
            return None
        else:
            lhs = self[0].generate_thinks(excluded_predicates)
            rhs = [i.generate_thinks(excluded_predicates) for i in self.args[1:]]
            if lhs is None or len(rhs) == 0:
                return None
            else:
                return GDLRule(lhs, GDLTerm("role", "R"), *rhs)
    
#Class for predicates and atomics
#Atomic will have an argument length of 0, len(term) == 0, predicates will have len(term) > 0
class GDLTerm(GDLMetaObject):
    def __init__(self, pred, *args):
        super().__init__(pred,*args)
    def __str__(self):
        if len(self) == 2 and self.pred == "distinct":
            return str(self[0]) + " \\= " + str(self[1])
        elif len(self) > 0:
            return str(self.pred) + "(" + ",".join(map(str,self.args)) + ")"
        else:
            return str(self.pred)
    def generate_thinks(self, excluded_predicates = set()) -> GDLMetaObject:
        if str(self.pred) == "distinct" or str(self.pred) == "role":
            return self
        #Assumption, ptrue and next only have one argument
        if str(self.pred) == 'ptrue':
            return GDLTerm('thinks', 'R', self.args[0])
        elif str(self.pred) == "knows":
            #Taking into account knows/1 and knows/2
            return GDLTerm("thinks", "R", self)
        elif str(self.pred) == 'next' or str(self.pred) == "not":
            return GDLTerm(self.pred, self.args[0].generate_thinks(excluded_predicates))
        elif str(self.pred) not in excluded_predicates:
            return GDLTerm("thinks", "R", self)
        else:
            return self
#Class for modelling or clauses
class GDLOr(GDLMetaObject):
    def __init__(self, *args):
        super().__init__(None,*args)
    def __str__(self):
        return "(" + ";".join(map(str,self.args)) + ")"
    def generate_thinks(self, excluded_predicates = set()) -> GDLMetaObject:
        return GDLOr(*[i.generate_thinks(excluded_predicates) for i in self.args])

#GDLAnd is implicitly used by comma (,) separation, or can be called explicitly in prefix form by having an argument sequence with no predicate name
#Useful for complex Or conditions
class GDLAnd(GDLMetaObject):
    def __init__(self, *args):
        super().__init__(None,*args)
    def __str__(self):
        return "(" + ",".join(map(str,self.args)) + ")"
    def generate_thinks(self, excluded_predicates = set()) -> GDLMetaObject:
        return GDLAnd(*[i.generate_thinks(excluded_predicates) for i in self.args])

#Class to model a ... iterative structure shorthand in gdliii, takes in lhs and rhs, which must be the same predicate with the same number of arguments
#__str__ method generates every predicate in sequence from from_term to to_term
# Assumptions, GDLTerms are identical with the exception of integer values
# Of the integer values, they must either be identical, or have a constant difference (same difference across every pair of non matching integers)
class GDLIterative(GDLMetaObject):
    def __init__(self, from_term: GDLTerm, to_term: GDLTerm):
        super().__init__(None, from_term, to_term)
        self._it_args = []
        self._from = NestedView(self.args[0])
        _to = NestedView(self.args[1])
        self._difference = 0
        self._unfurled_it = []
        for seq in self._get_integer_args(self.args[0]):
            from_val = self._from.get_item_with_index_sequence(seq)
            to_val = _to.get_item_with_index_sequence(seq)
            if (from_val.pred != to_val.pred):
                self._difference = to_val.pred - from_val.pred
                self._it_args.append(seq)
    def _get_integer_args(self, gdl: GDLTerm) -> [list]:
        index_args = []
        if type(gdl.pred) == int:
            return [[]]
        for i in range(len(gdl)):
            ret_val = self._get_integer_args(gdl[i])
            for sublist in ret_val:
                sublist.insert(0,i)
            index_args.extend(ret_val)
        return index_args
    def __str__(self):
        init_str = [str(self._from.obj)]
        values = [self._from.get_item_with_index_sequence(self._it_args[i]).pred for i in range(len(self._it_args))]
        for _ in range(self._difference):
            for i in range(len(self._it_args)):
                values[i] += 1
                self._from.set_item_with_index_sequence(self._it_args[i], values[i])
            init_str.append(str(self._from.obj))
        for i in range(len(self._it_args)):
            self._from.set_item_with_index_sequence(self._it_args[i],self._from.get_item_with_index_sequence(self._it_args[i]).pred - self._difference)
        return ".\n".join(init_str)

#Class representing entire gdliii program, does not inherit from GDLMetaObject
'''
Attributes:
player_map: A map of string player names to a corresponding integer used to represent them in the problog program
Methods:
as_problog() -> str: returns a PrologString object corresponding to the currently constructed program
'''
class GDLProgram(object):
    def __init__(self):
        self._lines = []
        self._player_num = 1
        self.player_map = {}
        self._converted = False
        self._extra_rules = None
    def _add_gdl(self, gdl) -> None:
        if type(gdl) == GDLTerm and str(gdl.pred) == "role" and len(gdl) == 1:
            if str(gdl[0]) == "random":
                self.player_map[str(gdl[0])] = 0
            else:
                self.player_map[str(gdl[0])] = self._player_num
                self._player_num += 1
        self._lines.append(gdl)
    def __str__(self) -> str:
        return ".\n".join(map(str,self._lines)) + "."
    def _finalise_model(self, replacement_map = {}, extra_rules = []) -> None:
        if self._converted:
            raise Exception("Cannot call _finalise_model more than once per GDLProgram object")
        self._extra_rules = extra_rules
        new_lines = []
        var_num = 1
        var_map = {}
        for statement in self._lines:
            for (original, replacement) in {**self.player_map, **replacement_map}.items():
                statement.replace(original,replacement)
            var_num = self._translate_variables(statement, var_num, var_map)
            self._quote_atoms(statement)
        self._plain_len = len(self._lines)
        indep_terms = set()
        while (any([self._add_independent_term(line, indep_terms) for line in self._lines])):
            pass
        for statement in self._lines:
            if type(statement) == GDLRule:
                new_rule = statement.generate_thinks(indep_terms)
                if new_rule is not None:
                    new_lines.append(new_rule)
        self._lines.extend(new_lines)
        self._converted = True

    #Returns the objective GDL rules (without the generated thinks rules) as problog text
    def as_plain_problog(self) -> str:
        return ".\n".join(map(str, self._lines[:self._plain_len])) + "."

    #(arity, argument) of every knows/1 and knows/2 occurring in the objective rules, argument as problog text
    def knows_arguments(self) -> list:
        found = []
        def walk(obj):
            if type(obj) == GDLTerm and str(obj.pred) == "knows" and len(obj) in (1, 2):
                found.append((len(obj), str(obj[len(obj) - 1])))
            for a in obj.args:
                walk(a)
        for line in self._lines[:self._plain_len]:
            walk(line)
        return list(dict.fromkeys(found))


    #Excluded list is made from non-game defined single predicated (e.g. psucc in guess.gdliii), and rule that has only terms of this nature on rhs is not to be duplicated
    #Evaluates a term and updates the curr_deps set accordingly, returns true if gdl is an independent term
    def _add_independent_term(self, statement: GDLMetaObject, curr_deps: set) -> bool:
        if (type(statement) == GDLTerm and str(statement.pred) not in GDL_KEYWORDS and str(statement.pred) not in curr_deps):
            curr_deps.add(str(statement.pred))
            return True
        elif (type(statement) == GDLIterative and str(statement[0].pred) not in GDL_KEYWORDS and str(statement[0].pred) not in curr_deps):
            curr_deps.add(str(statement[0].pred))
            return True
        elif (type(statement) == GDLRule) and str(statement[0].pred) not in GDL_KEYWORDS \
            and str(statement[0].pred) not in curr_deps and all([self._is_independent_term(arg,curr_deps) for arg in statement[1:]]):
                curr_deps.add(str(statement[0].pred))
                return True
        return False

    #Function to evaluate whether a term, and, or clause is independent
    def _is_independent_term(self, gdl: GDLMetaObject, curr_deps: set) -> bool:
        if type(gdl) == GDLTerm:
            return str(gdl.pred) in curr_deps
        elif type(gdl) == GDLAnd:
            return all([self._is_independent_term(arg, curr_deps) for arg in gdl.args])
        elif type(gdl) == GDLOr:
            return any([self._is_independent_term(arg, curr_deps) for arg in gdl.args])
        else:
            raise Exception("Unexpected type provided to _is_independent_term, expected GDLTerm, GDLAnd or GDLOr")

    
    #GDL variables are ?x, so a capitalised name is an atom, but problog would read it as a variable
    def _quote_atoms(self, gdl: GDLMetaObject) -> None:
        if type(gdl.pred) == str and gdl.pred[:1].isupper() and not re.fullmatch(r"Var\d+", gdl.pred):
            gdl.pred = _QuotedAtom(gdl.pred)
        if isinstance(gdl.pred, GDLMetaObject):
            self._quote_atoms(gdl.pred)
        for a in gdl.args:
            self._quote_atoms(a)

    def _translate_variables(self, gdl: GDLMetaObject, next_var_num: int, var_map: dict) -> int:
        for i in range(len(gdl)):
            if len(gdl[i]) > 0:
                next_var_num = self._translate_variables(gdl[i], next_var_num, var_map)
            elif type(gdl[i].pred) == str and gdl[i].pred.startswith("?"):
                if gdl[i].pred not in var_map.keys():
                    var_map[gdl[i].pred] = "Var"+str(next_var_num)
                    next_var_num += 1 
                gdl[i].pred = var_map[gdl[i].pred]
        return next_var_num
    #Returns the problog string of the program
    def as_problog(self) -> PrologString:
        if not self._converted:
            raise Exception("Cannot extract Problog representation without finalising the model by calling _finalise_model")
        return PrologString("\n".join(self._extra_rules) + "\n" + str(self))

class File_Format(Enum):
    PREFIX = auto()
    INFIX = auto()

class GDLIIIParser(object):
    def __init__(self):
        #TODO: Grab the full list of problog builtins and populate this with them
        #If we are trying to define a predicate that is the same as a builtin, prepend a p
        self._existing_builtins = {}
        for line in open(os.path.join(_DATA_DIR, 'problog_builtins.txt')):
            self._existing_builtins[line.rstrip()] = f"p{line.rstrip()}"

    def output_model(self, program_file: str, file_format: File_Format) -> GDLProgram:

        process_func = {
            File_Format.INFIX: lambda a: self._process_program_infix(a),
            File_Format.PREFIX: lambda a: self._process_program_prefix(a)
        }[file_format]
        with open(program_file) as f:
            program = "".join(l.split(";", 1)[0] + "\n" for l in f).replace("\n","")
        depth = 0
        for c in program:
            depth += (c == "(") - (c == ")")
            if depth < 0:
                break
        if depth != 0:
            raise ValueError("Unmatched parentheses in {}".format(program_file))
        gdl_spec = process_func(program)
        gdl_spec._finalise_model(self._existing_builtins, self._populate_predefined_preds())
        return gdl_spec

    def _infix_rule_rhs_split(self, gdl) -> [GDLMetaObject]:
        term = ""
        paren_count = 0
        term_list = []
        for c in gdl:
            if c == "(":
                paren_count += 1
            elif c == ")":
                paren_count -= 1
            elif c == "," and paren_count == 0:
                term_list.append(self._process_line_infix(term))
                term = ""
                continue
            term += c
        term_list.append(self._process_line_infix(term))
        return term_list

    def _process_program_infix(self, gdl: str) -> GDLProgram:
        gdl_spec = GDLProgram()
        for line in gdl.split("."):
            line = line.strip(" \n")
            if line != "":
                gdl_spec._add_gdl(self._process_line_infix(line))
        return gdl_spec

    def _process_line_infix(self, gdl: str) -> GDLMetaObject:
        gdl = gdl.strip()
        if gdl.startswith("not") and (len(gdl) == 3 or not (gdl[3].isalnum() or gdl[3] == "_")):
            gdl = gdl.replace("not ", "not(", 1)
            gdl = gdl + ")"
        if ("<=" not in gdl and "(" not in gdl):
            try:
                return int(gdl)
            except:
                return gdl
        if ("<=" in gdl):
            #Assumption, there are only two subgdl parts of the gdl line
            subgdl = gdl.split("<=")
            return GDLRule(self._process_line_infix(subgdl[0]), *self._infix_rule_rhs_split(subgdl[1]))
        #Else it is a Fact (Term)
        term = ""
        paren_count = 0
        args = []
        for c in gdl:
            if c == "(":
                if paren_count == 0:
                    #For the very first term, we want it as the raw string as it is the predicate name
                    args.append(term)
                    term = ""
                else:
                    term += c
                paren_count += 1
            elif c == ")":
                paren_count -= 1
                if paren_count == 0:
                    args.append(self._process_line_infix(term))
                    term = ""
                else:
                    term += c
            elif c == ",":
                if paren_count == 1:
                    args.append(self._process_line_infix(term))
                    term = ""
                else:
                    term += c
            else:
                term += c
        return GDLTerm(args[0], *args[1:])

    def _process_statement_prefix(self, statement: str) -> GDLMetaObject:
        paren_count = 0
        statement = statement.replace("(", " (")
        statement = statement.replace(")", ") ")
        statement = statement.strip()
        term = ""
        args = []
        primitive = True
        for c in statement:
            if c == "(":
                paren_count += 1
                if paren_count > 1:
                    primitive = False
            elif c == ")":
                paren_count -= 1

            if (primitive and c not in ["(", ")", " "]) or (not primitive):
                term += c

            if not primitive and paren_count == 1:
                args.append(self._process_statement_prefix(term))
                term = ""
                primitive = True
            elif primitive and term != "" and (c == " " or c == ")"):
                try:
                    args.append(GDLTerm(int(term)))
                except:
                    args.append(GDLTerm(term))
                term = ""

        if paren_count != 0:
            raise Exception("Unmatched parentheses in statement {}".format(statement))
        if args[0].pred == "<=":
            return GDLRule(args[1], *args[2:])
        elif len(args[0]) > 0:
            return GDLAnd(*args)
        elif args[0].pred == "or":
            return GDLOr(*args[1:])
        else:
            return GDLTerm(args[0], *args[1:])

    #Assumptions:
    # ... only appears outside of terms to denote an iterative generation of a predicate
    def _process_program_prefix(self, gdl: str) -> GDLProgram:
        gdl_spec = GDLProgram()
        gdl = gdl.replace("...", "!")
        paren_count = 0
        term = ""
        iterative = False
        for c in gdl:
            if c == "(":
                paren_count += 1
            elif c == ")":
                paren_count -= 1
                if paren_count == 0:
                    term += c
                    gdl_spec._add_gdl(self._process_statement_prefix(term))
                    term = ""
                    if iterative:
                        t2 = gdl_spec._lines.pop()
                        t1 = gdl_spec._lines.pop()
                        gdl_spec._add_gdl(GDLIterative(t1,t2))
                        iterative = False
            if paren_count > 0:
                term += c
            elif paren_count == 0 and c == "!":
                iterative = True
        return gdl_spec

    #Return a list of predefined predicates that are required for the model to run
    def _populate_predefined_preds(self):
        return [line.strip() for line in open(os.path.join(_DATA_DIR, 'predicates.problog'))]



#Parser testing
if __name__ == "__main__":
    p = GDLIIIParser()
    #print(p.output_model('./examples/montyhall.gdliii', File_Format.INFIX))
    q = p.output_model('./examples/birthday.gdliii', File_Format.PREFIX)
    print(q)