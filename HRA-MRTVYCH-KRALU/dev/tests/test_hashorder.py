"""Hash-order guard: PYTHONHASHSEED changes the iteration order of a set of str between processes, so hmk/ must never
let that order reach the game state (SPEC 3.1: "never iterate a set of str without sorted()").

Static part (AST, whole hmk/ package; server.py too):
  A name/attribute counts as a set when it is assigned set(), frozenset(), {a, b}, a set comprehension, a set
  operation (| & - ^ union intersection ...) of a set, or a function that returns only sets. It is flagged when it
  is iterated (for, comprehension, list/tuple/enumerate/zip/reversed/iter/join, *unpacking, dict.fromkeys) or `.pop()`ed
  without sorted(). Not flagged: `x in S`, len/min/max/sorted/any/all/set/frozenset(S), a generator inside
  any/all/min/max/sorted/set/frozenset, `next(iter(S))`, a set comprehension.
  A deliberate case (a set of small ints, say) is marked with a trailing comment `# hashorder-ok`.
Dynamic part: the same short harness game under PYTHONHASHSEED=1 and 2 must give identical state hashes.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

MARK = 'hashorder-ok'
# Known benign sites, as (file with forward slashes, enclosing function): lan_ips only filters a set of IP strings
# and sorts the result afterwards (display order of the start-up banner, never game state).
ALLOW = {('dev/tests/golden/server_05.py', 'lan_ips'), ('server.py', 'lan_ips')}
SET_METHODS = {'union', 'intersection', 'difference', 'symmetric_difference', 'copy'}
SET_OPS = (ast.BitOr, ast.BitAnd, ast.Sub, ast.BitXor)
SAFE_CONSUMERS = {'sorted', 'any', 'all', 'min', 'max', 'set', 'frozenset', 'len', 'bool'}
ORDER_CONSUMERS = {'list', 'tuple', 'enumerate', 'zip', 'reversed', 'iter'}


class Scope:
    """Set-typed names of one module: plain names per function, attribute names and function names module-wide."""

    def __init__(self):
        self.attrs = set()
        self.funcs = set()
        self.gnames = set()           # module-level set constants (WALK, BUILD, ...), also seen as module.NAME


def _name_of(n):
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        return n.attr
    return None


def is_set_expr(n, local, scope):
    if isinstance(n, (ast.Set, ast.SetComp)):
        return True
    if isinstance(n, ast.Call):
        f = n.func
        if isinstance(f, ast.Name) and f.id in ('set', 'frozenset'):
            return True
        if isinstance(f, ast.Attribute) and f.attr in SET_METHODS:
            return is_set_expr(f.value, local, scope)
        return _name_of(f) in scope.funcs
    if isinstance(n, ast.BinOp) and isinstance(n.op, SET_OPS):
        return is_set_expr(n.left, local, scope) or is_set_expr(n.right, local, scope)
    if isinstance(n, ast.Name):
        return n.id in local or n.id in scope.gnames
    if isinstance(n, ast.Attribute):
        return n.attr in scope.attrs
    if isinstance(n, ast.IfExp):
        return is_set_expr(n.body, local, scope) and is_set_expr(n.orelse, local, scope)
    return False


def _ann_is_set(a):
    t = ast.dump(a)
    return any(k in t for k in ("id='set'", "id='Set'", "id='frozenset'", "id='FrozenSet'", "id='AbstractSet'"))


def _stmt_nodes(fn):
    """Nodes that belong to `fn` itself; for a Module: the top-level statements, without function/class bodies."""
    if isinstance(fn, ast.Module):
        return [x for b in fn.body if not isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                for x in ast.walk(b)]
    return list(ast.walk(fn))


def collect(tree, scope):
    """Fill scope.attrs / scope.funcs (two passes so that set-returning helpers are found)."""
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for _ in range(2):
        for fn in funcs + [tree]:
            local = local_sets(fn, scope)
            for n in _stmt_nodes(fn):
                if isinstance(n, ast.Assign) and is_set_expr(n.value, local, scope):
                    for t in n.targets:
                        if isinstance(t, ast.Attribute):
                            scope.attrs.add(t.attr)
                elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Attribute) and (
                        _ann_is_set(n.annotation) or (n.value is not None and is_set_expr(n.value, local, scope))):
                    scope.attrs.add(n.target.attr)
            if fn is tree:
                scope.gnames.update(local)
                scope.attrs.update(local)
            else:
                rets = [n.value for n in ast.walk(fn) if isinstance(n, ast.Return) and n.value is not None]
                if rets and all(is_set_expr(r, local, scope) for r in rets):
                    scope.funcs.add(fn.name)


def local_sets(fn, scope):
    """Plain names assigned a set inside `fn` (module level when fn is the Module)."""
    names = set()
    nodes = _stmt_nodes(fn)
    for _ in range(2):
        for n in nodes:
            if isinstance(n, ast.Assign) and is_set_expr(n.value, names, scope):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
            elif isinstance(n, ast.Assign) and isinstance(n.value, ast.Tuple):
                for t in n.targets:
                    if isinstance(t, ast.Tuple) and len(t.elts) == len(n.value.elts):
                        for x, y in zip(t.elts, n.value.elts):
                            if isinstance(x, ast.Name) and is_set_expr(y, names, scope):
                                names.add(x.id)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and (
                    _ann_is_set(n.annotation) or (n.value is not None and is_set_expr(n.value, names, scope))):
                names.add(n.target.id)
            elif isinstance(n, ast.arg) and n.annotation is not None and _ann_is_set(n.annotation):
                names.add(n.arg)
    return names


def check_source(src, name, scope=None):
    tree = ast.parse(src, filename=name)
    lines = src.split('\n')
    scope = scope or Scope()
    collect(tree, scope)
    out = []

    parents = {}
    for p in ast.walk(tree):
        for c in ast.iter_child_nodes(p):
            parents[id(c)] = p

    def enclosing(node):
        while node is not None:
            node = parents.get(id(node))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return ''

    def flag(node, what):
        ln = getattr(node, 'lineno', 0)
        if 0 < ln <= len(lines) and MARK in lines[ln - 1]:
            return
        if (name.replace(os.sep, '/'), enclosing(node)) in ALLOW:
            return
        out.append('%s:%s: %s' % (name, ln, what))

    def visit(fn, local):
        for n in ast.walk(fn):
            if isinstance(n, (ast.For, ast.AsyncFor)) and is_set_expr(n.iter, local, scope):
                flag(n, 'for-loop over a set (use sorted())')
            elif isinstance(n, ast.comprehension) and is_set_expr(n.iter, local, scope):
                comp = parents.get(id(n))
                par = parents.get(id(comp))
                safe = (isinstance(comp, ast.SetComp) or
                        (isinstance(comp, ast.GeneratorExp) and isinstance(par, ast.Call) and isinstance(par.func, ast.Name)
                         and par.func.id in SAFE_CONSUMERS))
                if not safe:
                    flag(comp or n, 'comprehension over a set (use sorted())')
            elif isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name) and f.id in ORDER_CONSUMERS:
                    par = parents.get(id(n))
                    if f.id == 'iter' and isinstance(par, ast.Call) and isinstance(par.func, ast.Name) and par.func.id == 'next':
                        continue
                    if any(is_set_expr(a, local, scope) for a in n.args):
                        flag(n, '%s() of a set (use sorted())' % f.id)
                elif isinstance(f, ast.Attribute) and f.attr == 'join' and n.args and is_set_expr(n.args[0], local, scope):
                    flag(n, 'join() of a set (use sorted())')
                elif isinstance(f, ast.Attribute) and f.attr == 'fromkeys' and n.args and is_set_expr(n.args[0], local, scope):
                    flag(n, 'dict.fromkeys() of a set (use sorted())')
                elif isinstance(f, ast.Attribute) and f.attr == 'pop' and not n.args and is_set_expr(f.value, local, scope):
                    flag(n, 'set.pop() returns an arbitrary element')
                for a in n.args:
                    if isinstance(a, ast.Starred) and is_set_expr(a.value, local, scope):
                        flag(n, '*set unpacking (use sorted())')
            elif isinstance(n, (ast.List, ast.Tuple)):
                for a in n.elts:
                    if isinstance(a, ast.Starred) and is_set_expr(a.value, local, scope):
                        flag(n, '*set unpacking (use sorted())')

    visit(tree, local_sets(tree, scope))
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        visit(fn, local_sets(fn, scope))
    # a node inside a nested function is visited by both walks; keep unique messages
    return sorted(set(out), key=lambda m: (m.split(':')[0], int(m.split(':')[1])))


def source_files():
    files = []
    srv = os.path.join(_paths.GAME, 'server.py')
    if os.path.isfile(srv):
        files.append(srv)
    for root, dirs, names in os.walk(os.path.join(_paths.GAME, 'hmk')):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        files += [os.path.join(root, f) for f in sorted(names) if f.endswith('.py')]
    return files


def check_files(files):
    """The attribute/function set names are collected over ALL files first (a mixin iterates `sd.techs` that Side sets)."""
    scope = Scope()
    srcs = []
    for f in files:
        with open(f, encoding='utf-8') as fh:
            src = fh.read()
        srcs.append((os.path.relpath(f, _paths.GAME), src))
        collect(ast.parse(src), scope)
    problems = []
    for name, src in srcs:
        problems += check_source(src, name, scope)
    return problems


class TestHashOrder(unittest.TestCase):
    def test_no_unsorted_set_iteration_in_hmk(self):
        files = source_files()
        if not any(os.sep + 'hmk' + os.sep in f for f in files):
            self.skipTest('hmk/ package not present yet')
        problems = check_files(files)
        self.assertEqual(problems, [], '\n' + '\n'.join(problems) +
                         '\n(sort it, or mark a deliberate case with a trailing "# %s")' % MARK)

    def test_state_independent_of_hashseed(self):
        """Two processes with different PYTHONHASHSEED play the same bot match: the state hashes must be equal."""
        outs = []
        for seed in ('1', '2'):
            with tempfile.TemporaryDirectory() as d:
                out = os.path.join(d, 'g.json')
                env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE='1')
                p = subprocess.run([sys.executable, os.path.join(_paths.GOLDEN, 'golden.py'), '--worker', '--seeds', '4',
                                    '--modes', 'kral,strateg', '--secs', '180', '--every', '600', '--procs', '1',
                                    '--out', out], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(p.returncode, 0, p.stdout.decode('utf-8', 'replace')[-2000:])
                with open(out, encoding='utf-8') as f:
                    outs.append([(r['mode'], r['hashes'], r['over']) for r in json.load(f)])
        self.assertEqual(outs[0], outs[1], 'game state depends on PYTHONHASHSEED (set/str iteration order)')


class TestChecker(unittest.TestCase):
    BAD = {
        'global set constant': "WALK = frozenset('.~')\ndef f():\n    for ch in WALK:\n        pass",
        'for over set attr': "class A:\n    def __init__(self):\n        self.techs = set()\n    def f(self):\n        for t in self.techs:\n            pass",
        'for over local set': "def f():\n    s = set()\n    for x in s:\n        pass",
        'for over set literal': "def f():\n    for x in {'a', 'b'}:\n        pass",
        'listcomp over set': "def f(a):\n    s = {1, 2}\n    return [x for x in s]",
        'list(set)': "def f(a):\n    s = set(a)\n    return list(s)",
        'join set': "def f(a):\n    s = set(a)\n    return ','.join(s)",
        'set op': "def f(a, b):\n    s = set(a) | set(b)\n    for x in s:\n        pass",
        'set pop': "def f(a):\n    s = set(a)\n    return s.pop()",
        'returned set': "def mk(a):\n    h = set()\n    h.add(a)\n    return h\ndef f(a):\n    for x in mk(a):\n        pass",
        'starred': "def f(a):\n    s = set(a)\n    return [*s]",
        'dictcomp': "def f(a):\n    s = set(a)\n    return {x: 1 for x in s}",
    }
    GOOD = {
        'sorted': "def f(a):\n    s = set(a)\n    for x in sorted(s):\n        pass",
        'membership': "def f(a):\n    s = set(a)\n    return 3 in s, len(s)",
        'any generator': "def f(a):\n    s = set(a)\n    return any(x > 1 for x in s)",
        'set comp': "def f(a):\n    s = set(a)\n    return {x + 1 for x in s}",
        'next iter single': "def f(a):\n    s = set(a)\n    return next(iter(s)) if len(s) == 1 else -1",
        'marked': "def f(a):\n    s = set(a)\n    for x in s:  # hashorder-ok (ints)\n        pass",
        'list not set': "def f(a):\n    s = [1, 2]\n    for x in s:\n        pass",
        'dict keys': "def f(d):\n    for k in d.keys():\n        pass",
        'min max': "def f(a):\n    s = set(a)\n    return min(s), max(s)",
    }

    def test_bad_snippets_are_flagged(self):
        missed = [k for k, src in self.BAD.items() if not check_source(src, k)]
        self.assertEqual(missed, [], 'not flagged: %s' % missed)

    def test_good_snippets_pass(self):
        false = {k: check_source(src, k) for k, src in self.GOOD.items() if check_source(src, k)}
        self.assertEqual(false, {}, 'false alarms: %s' % false)

    def test_0_5_server_is_clean(self):
        """The frozen 0.5 server is known to be hash-order safe (single-element next(iter(...)) idiom included)."""
        self.assertEqual(check_files([_paths.SERVER_05]), [])


if __name__ == '__main__':
    unittest.main()
