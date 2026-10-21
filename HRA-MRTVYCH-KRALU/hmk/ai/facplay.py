"""Faction play for the AI (M3-C): the FAC 8 FacMixin rules, ported to the View / Planner / Actuator route.

Everything goes through the Planner primitives (try_build, try_upgrade, cast), so prices, Doba requirements and the
`max` limits come from the game (g.price, g.need_doba) and every message is delayed and APM-limited like any other.
The data (decks, template inserts, comps, DIFF overrides) is in profiles.FACTION_PLAN.

  prez  Dílna 1 after the 3rd Generátor, Dílna 2 after the 5th (path A), Ostnatá zeď upgrades at >= 60 scrap
        (the walls themselves are template items), Mrchožrout in the comps and the relic squad, King repairs eagerly.
  korp  Tesla and Hangár (path B) are template items, EMP on the 3x3 holding most enemy attack towers when >= 3 own
        units are within 3 columns, Exo only from Doba II and at most 3 (else Obrněnec).
  kult  2 Hnízda (path A) after the 4th Generátor, Tlupa whenever ready (horde_spare 60), Mor on the 3x3 holding
        most enemy units (>= 2), King war cry when >= 4 zombies are near him, Volání mrtvých when >= 4 zombies
        that march on us stand in the Mist.
In Přežití (ai.type == 'preziti') only the passive and defensive parts stay on: no Hnízda, EMP or Mor.
"""
from ..defs import ATTACK_TOWERS, own_half
from . import profiles as PR

FAC_UNIT = {'prez': 'mrchozrout', 'korp': 'exo', 'kult': 'nekromant'}      # the faction's unit card
BACK = {'dilna': [(0, 1), (0, 7), (1, 1), (1, 7), (0, 0), (0, 8)],
        'hnizdo': [(0, 0), (0, 8), (0, 1), (0, 7), (1, 0), (1, 8)]}


class FacPlay:
    def __init__(self, ai, planner):
        self.ai, self.pl = ai, planner
        self.g, self.s, self.v, self.act, self.P = ai.g, ai.side, ai.view, ai.act, ai.P
        self.fac = ai.fac
        self.plan = PR.FACTION_PLAN.get(self.fac) or {}
        self.live = ai.type != 'preziti'
        self.next_unit = 90.0                 # earliest time of the next lone faction unit (see unit())

    # ------------------------------------------------ planner step (after the defence template)
    def step(self):
        fac = self.fac
        if fac == 'prez':
            return self._prez()
        if fac == 'korp':
            return self._korp()
        if fac == 'kult' and self.live:
            return self._kult()
        return 'done'

    def towers(self):
        return sum(1 for b in self.v.blds if b.kind in ATTACK_TOWERS)

    def _back(self, kind, want):
        """Keep `want` buildings of this kind standing, on the safe cells behind the line."""
        pl, v = self.pl, self.v
        if want <= 0 or not pl.has(kind):
            return 'done'
        if v.count(kind) + self.act.queued('build', kind) >= want:
            return 'done'
        for lx, y in BACK[kind]:
            r = pl.try_build(kind, lx, y, misplace=False)
            if r == 'did':
                return 'did'
            if r in ('poor', 'wait'):
                return 'wait'
        return 'done'

    def _upgrade(self, kind, path, min_e, t0=150.0):
        pl, v = self.pl, self.v
        if self.g.t < t0 or pl.energy() < min_e:
            return 'done'
        for b in sorted(v.mine(kind), key=lambda e: (e.lvl, e.id)):
            if b.lvl < 3 and v.buildable(b.cx):
                r = pl.try_upgrade(b, path)
                if r == 'did':
                    return 'did'
        return 'done'

    def unit(self):
        """Pushes are rare and comps only reach the faction unit late, so keep one of them in the field: when none is
        alive or on its way and energy is plentiful, one goes out alone on the push lane every 60 s (also keeps
        the card in use: A9). Exo needs Doba II and at most 3 stand."""
        pl, v, g = self.pl, self.v, self.g
        kind = FAC_UNIT.get(self.fac)
        if not self.live or kind is None or not pl.has(kind) or g.t < self.next_unit or not pl.doba_ok(kind):
            return 'done'
        if v.count(kind) + self.act.queued('unit', kind) >= 1 or any(it[0] == kind for it in pl.queue):
            return 'done'
        if pl.energy() < g.price(self.s, kind)[0] + 200:
            return 'done'
        rows = [y for y in (pl.lane, pl.lane - 1, pl.lane + 1) if 0 <= y < 9 and pl.cross[y]] or [4]
        pl.queue.append([kind, g.t, rows])
        self.next_unit = g.t + 60.0
        return 'did'

    def _prez(self):
        v = self.v
        r = self.unit()
        if r != 'done':
            return r
        gens, towers = v.count('gen'), self.towers()
        want = 2 if (gens >= 5 and towers >= 4) else 1 if (gens >= 3 and towers >= 2) else 0
        r = self._back('dilna', want)
        if r != 'done':
            return r
        r = self._upgrade('dilna', 'A', 140.0)
        if r != 'done':
            return r
        if v.sd.s >= 60:
            for b in sorted(v.mine('ostnata'), key=lambda e: (e.lvl, e.id)):
                if b.lvl < 3:
                    if self.pl.try_upgrade(b) == 'did':       # walls have no paths
                        return 'did'
        return 'done'

    def _korp(self):
        r = self.unit()
        if r != 'done':
            return r
        return self._upgrade('hangar', 'B', 150.0)

    def _kult(self):
        v = self.v
        r = self.unit()
        if r != 'done':
            return r
        want = 2 if (v.count('gen') >= 4 and self.towers() >= 3) else 0
        r = self._back('hnizdo', want)
        if r != 'done':
            return r
        return self._upgrade('hnizdo', 'A', 160.0)

    # ------------------------------------------------ attack composition
    def comp(self, name, base):
        c = self.plan.get('comps', {}).get(name)
        if not c:
            return base
        deck = self.v.deck()
        return [k for k in c if k in deck] or base

    def sub(self, kind):
        """Unit card that cannot be deployed right now -> its plain replacement (Exo needs Doba II, max 3)."""
        if kind == 'exo':
            v = self.v
            if (v.sd.doba < self.g.need_doba(self.s, 'exo')
                    or v.count('exo') + self.act.queued('unit', 'exo') >= 3):
                return 'obrnenec' if 'obrnenec' in v.deck() else 'pesak'
        return kind

    def squad_kinds(self, kinds):
        """Prez sends a Mrchožrout instead of one Pěšák on the relic squad."""
        if self.fac == 'prez' and 'mrchozrout' in self.v.deck() and 'pesak' in kinds:
            kinds = list(kinds)
            kinds[kinds.index('pesak')] = 'mrchozrout'
        return kinds

    # ------------------------------------------------ abilities (Planner.push_abilities)
    def abilities(self):
        if not self.live:
            return
        if self.fac == 'korp':
            self.emp()
        elif self.fac == 'kult':
            self.mor()

    def emp(self):
        """EMP on the 3x3 centred on the visible enemy attack tower with most towers around it (>= 2), when >= 3 own
        units are within 3 columns of it."""
        v = self.v
        if 'emp' not in v.deck():
            return
        sd = v.sd
        if sd.cd.get('emp', 0) > 0:
            return
        ts = [b for b in v.foe_buildings() if b.kind in ATTACK_TOWERS]
        best, bn = None, 0
        for c in sorted(ts, key=lambda b: b.id):
            n = sum(1 for o in ts if abs(o.cx - c.cx) <= 1 and abs(o.cy - c.cy) <= 1)
            if n > bn:
                best, bn = c, n
        if best is not None and bn >= 2:
            near = sum(1 for u in v.units if abs(u.x - best.cx) <= 3.0)
            if near >= 3:
                self.pl.cast('emp', best.cx, best.cy)
                return
        # defence: >= 3 enemy units in one 3x3 inside our half are stunned for 1.5 s under our towers' fire
        us = [e for e in v.foes if e.cat == 'u' and own_half(self.s, e.cx) and v.vis(e.cx, e.cy)]
        best, bn = None, 0
        for c in sorted(us, key=lambda e: e.id):
            n = sum(1 for o in us if abs(o.cx - c.cx) <= 1 and abs(o.cy - c.cy) <= 1)
            if n > bn:
                best, bn = c, n
        if best is not None and bn >= 3:
            self.pl.cast('emp', best.cx, best.cy)

    def mor(self):
        """Mor on the visible 3x3 that holds the most enemy units (>= 2). The cloud only hurts the enemy."""
        v = self.v
        if 'mor' not in v.deck() or v.sd.cd.get('mor', 0) > 0:
            return
        us = [e for e in v.foes if e.cat in 'uk' and e.kind != 'mina']
        if len(us) < 2:
            return
        best, bn = None, 0
        for c in sorted(us, key=lambda e: e.id):
            if not v.vis(c.cx, c.cy):
                continue
            n = sum(1 for o in us if abs(o.x - c.x) <= 1.5 and abs(o.y - c.y) <= 1.5)
            if n > bn:
                best, bn = c, n
        if best is not None and bn >= 2:
            self.pl.cast('mor', best.cx, best.cy)

    # ------------------------------------------------ King and Stratég hooks
    def cry_zombies(self, k):
        """Zombies (not Alfa) within 3 cells of the King that the war cry of Pán mrtvých would turn."""
        s = self.s
        return sum(1 for z in self.v.zombies if z.kind != 'alfa' and getattr(z, 'own', -1) != s
                   and (z.x - k.x) ** 2 + (z.y - k.y) ** 2 <= 9.0)

    def calls(self):
        """Volání mrtvých: >= 4 zombies marching on us stand in the Mist."""
        s = self.s
        n = sum(1 for z in self.v.zombies if z.tgt == s and z.kind != 'alfa' and getattr(z, 'own', -1) != s
                and 6 <= z.cx <= 9)
        return n >= 4
