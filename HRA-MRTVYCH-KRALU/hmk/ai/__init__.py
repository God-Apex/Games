"""Computer opponent (MAI 5). It acts only through g.act(side, msg) and sees only what the fog shows (View).

make_ai(g, side, diff, seed, type, fac) -> AIPlayer. The Session calls ai.on_tick() before every g.step(TICK).
pick_fac(diff, R) / pick_deck(diff, fac, R) are the optional hooks session.build_game uses before the Game exists.
"""
import random

from .. import factions as F
from ..defs import DEFS
from . import profiles as PR
from .profiles import AI_NAMES, DIFF, DIFFS, DIFF_IDS
from .view import View
from .actuator import Actuator
from .planner import Planner
from .pilot import KingPilot
from .commander import Commander


def _strat_pick(diff, R):
    P = DIFF[diff]
    x = R.random()
    acc = 0.0
    for name, w in P['strats']:
        acc += w
        if x < acc:
            return name
    return P['strats'][-1][0]


def strat_deck(diff, strat):
    deck = list(PR.DECKS[strat])
    if diff == 'tezka' and 'hlaska' not in deck and 'nalet' in deck:
        deck[deck.index('nalet')] = 'dron'
    return deck


def pick_fac(diff, R):
    """SPEC 2.2: Lehká plays Bez frakce, Střední and Těžká rnd.choice(FAC_IDS) (every faction has a FACTION_PLAN)."""
    if diff not in DIFF or diff == 'lehka':
        return 'bez'
    ids = [f for f in F.FAC_IDS if f == 'bez' or f in PR.FACTION_PLAN]
    return R.choice(ids)


def pick_deck(diff, fac, R):
    if diff not in DIFF:
        return None
    plan = PR.FACTION_PLAN.get(fac)
    strat = _strat_pick(diff, R)
    if plan and plan.get('decks', {}).get(strat):
        return list(plan['decks'][strat])
    return strat_deck(diff, strat)


def _own_deck(diff, fac, strat):
    plan = PR.FACTION_PLAN.get(fac)
    if plan and plan.get('decks', {}).get(strat):
        return list(plan['decks'][strat])
    return strat_deck(diff, strat)


def _detect_strat(diff, fac, deck):
    """The strategy whose deck (for this faction) this deck is; a deck from outside (tools, tests) resembles one."""
    for name in PR.STRATEGIES:
        if sorted(_own_deck(diff, fac, name)) == sorted(deck):
            return name
    return max(PR.STRATEGIES, key=lambda n: (len(set(_own_deck(diff, fac, n)) & set(deck)), -PR.STRATEGIES.index(n)))


class AIPlayer:
    def __init__(self, g, side, diff, seed, type='vycvik', fac='bez'):
        if diff not in DIFF:
            diff = 'lehka'
        self.g, self.side, self.diff, self.type, self.fac = g, side, diff, type, fac
        self.seed = seed if seed is not None else (g.seed or 0)
        self.name = AI_NAMES.get(diff, 'AI')
        P = dict(DIFF[diff])
        plan = PR.FACTION_PLAN.get(fac)
        if plan:
            P.update(plan.get('P', {}))                  # faction overrides (kult: Tlupa whenever ready)
        if type == 'preziti':
            P.update(PR.PREZITI[diff])                   # Přežití profile: no pushes, crates and own Mist half only
        self.P = P
        self.rnd = random.Random(self.seed * 1000003 + side * 7919 + P['salt'])
        self.view = View(g, side)
        deck = list(self.view.deck())
        if type == 'preziti':
            # zombies only: the all-round deck whatever pick_deck gave (the deck is chosen before the start, like in the lobby)
            self.strat = 'mixed'
            plan_deck = (plan or {}).get('decks', {}).get('mixed') or PR.PREZITI_DECK
            if sorted(deck) != sorted(plan_deck) and all(k in DEFS for k in plan_deck):
                self.view.set_deck(plan_deck)
        else:
            self.strat = _detect_strat(diff, fac, deck)
        self.act = Actuator(g, side, P, self.rnd, self.view)
        self.plan = Planner(self)
        self.pilot = KingPilot(self) if g.mode == 'kral' else None
        self.cmd = Commander(self) if g.mode == 'strateg' else None
        self.next_think = 0.05 + self.rnd.random() * P['think']
        self.thinks = 0

    def on_tick(self):
        g = self.g
        if g.over:
            return
        fx = self.view.feed()
        if g.t >= self.next_think:
            self.next_think += self.P['think']
            if self.next_think < g.t:
                self.next_think = g.t + self.P['think']
            self.view.update()
            self.plan.think()
            if self.cmd is not None:
                self.cmd.think()
            elif self.pilot is not None:
                self.pilot.think()
            self.thinks += 1
        if self.pilot is not None:
            self.pilot.reflex(fx)
        self.act.flush()


def make_ai(g, side, diff, seed, type='vycvik', fac='bez'):
    return AIPlayer(g, side, diff, seed, type, fac)
