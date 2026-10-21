"""Shared path and server-loading helpers for every dev/tests tool. Paths are relative to this file only.

Game dir = ../..  (this file lives in <game>/dev/tests).
HMK_SERVER (env) overrides the server under test: a path to a server.py-like file, or to a game folder that holds
server.py. Relative values are resolved against the game dir. Default: <game>/server.py.
The frozen 0.5 copy is SERVER_05 (golden/server_05.py, never edited).
"""
import importlib.util
import inspect
import os
import random
import sys

sys.dont_write_bytecode = True

TESTS = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.normpath(os.path.join(TESTS, '..', '..'))
DEV = os.path.join(GAME, 'dev')
GOLDEN = os.path.join(TESTS, 'golden')
BAL = os.path.join(TESTS, 'bal')
OUT = os.path.join(TESTS, '_out')
SERVER_05 = os.path.join(GOLDEN, 'server_05.py')


def server_path(spec=None):
    """Resolve HMK_SERVER (or `spec`) to the server.py file under test."""
    spec = spec if spec is not None else os.environ.get('HMK_SERVER', '')
    if not spec:
        return os.path.join(GAME, 'server.py')
    p = spec if os.path.isabs(spec) else os.path.join(GAME, spec)
    p = os.path.normpath(p)
    return os.path.join(p, 'server.py') if os.path.isdir(p) else p


def load_server(spec=None):
    """Import the server module under the name 'server' (cached). Its folder goes first on sys.path so that the
    `hmk` package next to it is importable. server.py parses sys.argv at import time, so argv is blanked."""
    if 'server' in sys.modules and spec is None:
        return sys.modules['server']
    path = server_path(spec)
    if not os.path.isfile(path):
        raise FileNotFoundError('server not found: ' + path)
    folder = os.path.dirname(path)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    modspec = importlib.util.spec_from_file_location('server', path)
    mod = importlib.util.module_from_spec(modspec)
    argv, sys.argv = sys.argv, [sys.argv[0]]
    sys.modules['server'] = mod
    try:
        modspec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop('server', None)
        raise
    finally:
        sys.argv = argv
    return mod


def is_hmk(S):
    """True when the loaded server runs the 1.0 package layout (its Game class lives in the hmk package)."""
    return getattr(S.Game, '__module__', '').startswith('hmk')


def defs_module(S):
    """The module that owns the tunables: hmk.defs on 1.0, the server module itself on 0.5."""
    if is_hmk(S):
        import importlib
        return importlib.import_module('hmk.defs')
    return S


def game_params(S):
    return inspect.signature(S.Game.__init__).parameters


def new_game(S, names, decks, mode, seed=None, compat05=True, **kw):
    """Create a Game on either the 0.5 or the 1.0 server.
    seed given -> random.seed(seed) first. On 1.0 the Game draws from the module `random` (rng=random) so the draw
    order equals 0.5, and `compat05` (default True: the 0.5 rules) is passed."""
    if seed is not None:
        random.seed(seed)
    params = game_params(S)
    if 'rng' in params:
        kw.setdefault('rng', random)
    if 'compat05' in params:
        kw['compat05'] = compat05
    return S.Game(names, decks, mode, **kw)
