#!/usr/bin/env python3
"""Hra mrtvych kralu - LAN server: serves the game and runs the authoritative 1v1 simulation.

Usage:  python server.py [port] [--no-browser] [--stats PATH] [--no-stats]   (default port 8095)
        env HMK_STATS works like --stats; default stats file <game dir>/stats.json
Needs only the Python 3.8+ standard library. The code lives in the hmk/ package.
"""
import sys

sys.dont_write_bytecode = True

from hmk.defs import *  # noqa: E402,F401,F403  (re-exports for tooling)
from hmk.game import Game  # noqa: E402,F401
from hmk.entity import Ent, Side  # noqa: E402,F401
from hmk.maps import bfs, bfs_from, WALK, BUILD  # noqa: E402,F401
from hmk.net import main_cli  # noqa: E402

if __name__ == '__main__':
    main_cli(sys.argv)
