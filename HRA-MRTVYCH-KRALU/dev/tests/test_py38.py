"""Python 3.8 guard (MAI section 1): server.py and every hmk/**/*.py must stay runnable on Python 3.8, stdlib only.

Checks (all on the AST, so strings and comments never cause false alarms):
  * ast.parse(feature_version=(3, 8)): no match statement, no parenthesized with-items, no except*, no PEP 614
    decorators, no star expressions in subscripts, ...
  * banned APIs: str.removeprefix / removesuffix, int.bit_count, functools.cache, zoneinfo, asyncio.to_thread,
    random.randbytes, itertools.pairwise, math.lcm, zip(strict=), dataclass(slots/kw_only), datetime.UTC
  * runtime `X | None` (and `X | Y` inside annotations without `from __future__ import annotations`), dict `|` / `|=`
  * builtin generics at runtime (`list[int]`, `dict[str, int]`, ...), which fail on 3.8
  * f-string expressions that contain a backslash or re-use the f-string's own quote (only legal from 3.12)
  * imports: standard library, `hmk` and `server` only
The checker has a self-test (TestChecker) so that a broken guard cannot pass silently.
"""
import ast
import io
import os
import sys
import tokenize
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

BANNED_ATTRS = {'removeprefix': 'str.removeprefix (3.9)', 'removesuffix': 'str.removesuffix (3.9)',
                'bit_count': 'int.bit_count (3.10)', 'to_thread': 'asyncio.to_thread (3.9)',
                'randbytes': 'random.randbytes (3.9)', 'pairwise': 'itertools.pairwise (3.10)',
                'lcm': 'math.lcm (3.9)', 'nextafter': 'math.nextafter (3.9)', 'is_relative_to': 'Path.is_relative_to (3.9)',
                'with_stem': 'Path.with_stem (3.9)', 'readlink': None, 'UTC': 'datetime.UTC (3.11)'}
BANNED_ATTRS = {k: v for k, v in BANNED_ATTRS.items() if v}
BANNED_IMPORT_NAMES = {('functools', 'cache'): 'functools.cache (3.9)', ('itertools', 'pairwise'): 'itertools.pairwise (3.10)',
                       ('math', 'lcm'): 'math.lcm (3.9)', ('asyncio', 'to_thread'): 'asyncio.to_thread (3.9)',
                       ('datetime', 'UTC'): 'datetime.UTC (3.11)'}
BANNED_MODULES = {'zoneinfo': 'zoneinfo (3.9)', 'graphlib': 'graphlib (3.9)', 'tomllib': 'tomllib (3.11)'}
GENERIC_BUILTINS = {'list', 'dict', 'set', 'frozenset', 'tuple', 'type'}
STDLIB = set(getattr(sys, 'stdlib_module_names', ())) | {'hmk', 'server', '__future__'}


def _is_none(n):
    return isinstance(n, ast.Constant) and n.value is None


def _dictish(n):
    return (isinstance(n, (ast.Dict, ast.DictComp)) or
            (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'dict') or
            (isinstance(n, ast.Name) and n.id == 'dict'))


def paren_with_lines(src):
    """Line numbers of `with (a as x, b as y):` (3.9+ grammar; ast.parse(feature_version=(3, 8)) does not reject it)."""
    toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type not in (tokenize.COMMENT, tokenize.NL)]
    found = []
    skip = (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)
    for i, t in enumerate(toks):
        if t.type == tokenize.NAME and t.string == 'with' and i + 1 < len(toks) and toks[i + 1].string == '(':
            prev = toks[i - 1] if i else None
            if prev is not None and not (prev.type in skip or prev.string in ('async', ':')):
                continue
            depth = 0
            for u in toks[i + 1:]:
                if u.string in '([{' and u.type == tokenize.OP:
                    depth += 1
                elif u.string in ')]}' and u.type == tokenize.OP:
                    depth -= 1
                    if depth == 0:
                        break
                elif depth == 1 and u.type == tokenize.NAME and u.string == 'as':
                    found.append(t.start[0])
                    break
    return found


def check_source(src, name='<src>'):
    """-> list of problem strings (empty = fine)."""
    out = []
    try:
        tree = ast.parse(src, filename=name, feature_version=(3, 8))
    except SyntaxError as e:
        return ['%s:%s: not valid Python 3.8 syntax: %s' % (name, e.lineno, e.msg)]
    for ln in paren_with_lines(src):
        out.append('%s:%s: parenthesized with-items (3.9)' % (name, ln))
    future_ann = any(isinstance(n, ast.ImportFrom) and n.module == '__future__' and any(a.name == 'annotations' for a in n.names)
                     for n in ast.walk(tree))
    ann_nodes = set()
    for n in ast.walk(tree):
        anns = []
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
                if arg is not None and arg.annotation is not None:
                    anns.append(arg.annotation)
            if n.returns is not None:
                anns.append(n.returns)
        elif isinstance(n, ast.AnnAssign):
            anns.append(n.annotation)
        for an in anns:
            for sub in ast.walk(an):
                ann_nodes.add(id(sub))

    def add(node, msg):
        out.append('%s:%s: %s' % (name, getattr(node, 'lineno', '?'), msg))

    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):
            if n.attr in BANNED_ATTRS:
                add(n, 'banned API ' + BANNED_ATTRS[n.attr])
            if n.attr == 'cache' and isinstance(n.value, ast.Name) and n.value.id == 'functools':
                add(n, 'banned API functools.cache (3.9)')
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ''
            if n.level == 0 and mod.split('.')[0] in BANNED_MODULES:
                add(n, 'banned module ' + BANNED_MODULES[mod.split('.')[0]])
            for a in n.names:
                if (mod, a.name) in BANNED_IMPORT_NAMES:
                    add(n, 'banned API ' + BANNED_IMPORT_NAMES[(mod, a.name)])
            if n.level == 0 and mod.split('.')[0] not in STDLIB:
                add(n, 'import of a non-stdlib module: ' + mod)
        elif isinstance(n, ast.Import):
            for a in n.names:
                top = a.name.split('.')[0]
                if top in BANNED_MODULES:
                    add(n, 'banned module ' + BANNED_MODULES[top])
                if top not in STDLIB:
                    add(n, 'import of a non-stdlib module: ' + a.name)
        elif isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name) and n.func.id == 'zip' and any(k.arg == 'strict' for k in n.keywords):
                add(n, 'zip(strict=) (3.10)')
            fn = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, 'id', '')
            if fn == 'dataclass' and any(k.arg in ('slots', 'kw_only', 'match_args') for k in n.keywords):
                add(n, 'dataclass(slots/kw_only) (3.10)')
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
            if _is_none(n.left) or _is_none(n.right):
                add(n, 'runtime `X | None` (3.10); use Optional or a comment')
            elif _dictish(n.left) or _dictish(n.right):
                add(n, 'dict `|` (3.9)')
            elif id(n) in ann_nodes and not future_ann:
                add(n, 'annotation `X | Y` without `from __future__ import annotations` (3.10)')
        elif isinstance(n, ast.AugAssign) and isinstance(n.op, ast.BitOr) and _dictish(n.value):
            add(n, 'dict `|=` (3.9)')
        elif isinstance(n, ast.Subscript):
            if isinstance(n.value, ast.Name) and n.value.id in GENERIC_BUILTINS:
                if not (id(n) in ann_nodes and future_ann):
                    add(n, 'builtin generic `%s[...]` at runtime (3.9)' % n.value.id)
        elif isinstance(n, ast.JoinedStr):
            seg = ast.get_source_segment(src, n) or ''
            body = seg.lstrip('fFrRbBuU')
            q = body[:3] if body[:3] in ('"""', "'''") else body[:1]
            for fv in n.values:
                if isinstance(fv, ast.FormattedValue):
                    es = ast.get_source_segment(src, fv.value) or ''
                    if '\\' in es:
                        add(n, 'backslash inside an f-string expression (3.12)')
                    elif q and q in es:
                        add(n, 'f-string expression re-uses the f-string quote (3.12)')
    return out


def source_files():
    files = []
    srv = os.path.join(_paths.GAME, 'server.py')
    if os.path.isfile(srv):
        files.append(srv)
    pkg = os.path.join(_paths.GAME, 'hmk')
    for root, dirs, names in os.walk(pkg):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        files += [os.path.join(root, f) for f in sorted(names) if f.endswith('.py')]
    return files


class TestPy38(unittest.TestCase):
    def test_server_and_hmk_are_python38_stdlib(self):
        files = source_files()
        if not any(os.sep + 'hmk' + os.sep in f for f in files):
            self.skipTest('hmk/ package not present yet')
        problems = []
        for f in files:
            with open(f, encoding='utf-8') as fh:
                problems += check_source(fh.read(), os.path.relpath(f, _paths.GAME))
        self.assertEqual(problems, [], '\n' + '\n'.join(problems))


class TestChecker(unittest.TestCase):
    """The guard must flag known-bad snippets and accept known-good ones."""
    BAD = {
        'removeprefix': "x = 'ab'.removeprefix('a')",
        'removesuffix': "x = s.removesuffix('a')",
        'match': "match x:\n    case 1:\n        pass\n",
        'functools.cache': "import functools\n@functools.cache\ndef f(): pass",
        'from functools import cache': "from functools import cache",
        'zoneinfo': "import zoneinfo",
        'X | None annotation': "def f(a: int | None): pass",
        'X | None runtime': "x = int | None",
        'dict union': "a = {}\nb = a | {'x': 1}",
        'dict |=': "a = {}\na |= {'x': 1}",
        'builtin generic': "x = list[int]",
        'zip strict': "x = zip(a, b, strict=True)",
        'bit_count': "x = (5).bit_count()",
        'to_thread': "import asyncio\nasyncio.to_thread(f)",
        'parenthesized with': "with (open('a') as f, open('b') as g):\n    pass",
        'except*': "try:\n    pass\nexcept* ValueError:\n    pass",
        'f-string backslash': "x = f\"{'\\n'.join(a)}\"",
        'f-string same quote': "x = f\"{d[\"k\"]}\"",
        'third party import': "import numpy",
    }
    GOOD = {
        'optional': "from typing import Optional\ndef f(a: Optional[int]): pass",
        'bit flags': "x = 1 | 2\ny = a | b",
        'set union': "x = set() | {1}",
        'future annotations': "from __future__ import annotations\ndef f(a: int | str): pass",
        'dict merge': "d = dict(a, **b)\nd2 = {**a, **b}",
        'typing generic': "from typing import List\nx = List[int]",
        'f-string': "x = f\"{a!r} {b:>5} {c['k']}\"",
        'lru_cache': "import functools\n@functools.lru_cache(maxsize=None)\ndef f(): pass",
        'stdlib imports': "import os, sys, json, asyncio\nfrom collections import deque\nfrom . import defs as D\nfrom hmk.defs import W",
        'words in strings': "x = 'removeprefix match case'  # match x:",
        'with paren expr': "with (open('a')) as f:\n    pass\nwith (a, b):\n    pass",
        'soft keywords as names': "match = 1\ncase = 2\nprint(match, case)",
    }

    def test_bad_snippets_are_flagged(self):
        missed = [k for k, src in self.BAD.items() if not check_source(src, k)]
        self.assertEqual(missed, [], 'not flagged: %s' % missed)

    def test_good_snippets_pass(self):
        false = {k: check_source(src, k) for k, src in self.GOOD.items() if check_source(src, k)}
        self.assertEqual(false, {}, 'false alarms: %s' % false)


if __name__ == '__main__':
    unittest.main()
