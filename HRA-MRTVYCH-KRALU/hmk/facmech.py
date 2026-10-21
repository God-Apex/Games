"""FactionMixin: faction mechanics (FAC 3-4) and owned zombies (FAC 1 [global]).

Hooks that only matter with a faction run only when g.facon (some side is not 'bez'). Randomness comes only from g.R
and never in a bez-bez game. When g.compat05 is set, no zombie is ever owned (own stays -1), so they stay hostile to
everyone exactly as in 0.5."""
from .defs import W, H, DEFS
from .factions import OWNED_CAP


class FactionMixin:
    # ------------------------------------------------ owned zombies
    def owned_n(self, s):
        return sum(1 for e in self.ents.values() if e.cat == 'z' and e.own == s)

    def may_own(self, s):
        """False when side s already has OWNED_CAP owned zombies (compat05: always True, nothing is owned)."""
        return self.compat05 or self.owned_n(s) < OWNED_CAP

    def set_own(self, z, s):
        if not self.compat05:
            z.own = s

    def turn_zombies(self, s, zs):
        """Pán mrtvých / Volání mrtvých: the zombies march on the foe as side s's own (capped). Event turn when n >= 3."""
        foe = 1 - s
        n = 0
        left = OWNED_CAP - self.owned_n(s)
        for z in zs:
            if z.dead or z.own == s:
                continue
            if left <= 0 and not self.compat05:
                break
            z.tgt = foe
            self.set_own(z, s)
            left -= 1
            n += 1
            self.fx.append(['W', round(z.x, 2), round(z.y, 2), 0, 0, s])
        if n >= 3:
            self.event(None, 'turn', s, n)
        return n

    def raise_dead(self, e, s):
        """A chodec of side s rises on the dead entity's cell when it is free plain ground (FAC 3 Raise)."""
        x, y = e.cx, e.cy
        if not (0 <= x < W and 0 <= y < H) or self.ter[y][x] != '.' or self.mob[y][x] or self.bld[y][x]:
            return None
        if not self.may_own(s):
            return None
        z = self.spawn('chodec', 2, x, y)
        z.tgt = 1 - s
        self.set_own(z, s)
        self.fx.append(['Z', x, y, 0, 0, s])
        return z

    def raise_check(self, e):
        """Called from kill() for a dead unit or zombie: Mor plague first, then a Nekromant nearby."""
        if e.cat == 'u' and e.plague >= 0 and self.t - e.plague_t < 0.2:
            if self.raise_dead(e, e.plague):
                return
        for nk in self.ents.values():
            if nk.kind != 'nekromant' or nk.dead or nk.rcd > 0:
                continue
            s = nk.side
            if e.cat == 'u':
                if e.side != 1 - s:
                    continue
            elif not (e.tgt == s and e.own != s):
                continue
            r = DEFS['nekromant']['raise']
            if (nk.x - e.x) ** 2 + (nk.y - e.y) ** 2 <= r * r:
                if self.raise_dead(e, s):
                    nk.rcd = DEFS['nekromant']['raise_cd']
                return

    # ------------------------------------------------ per-tick hooks
    def fac_passive(self, e, dt, repairs):
        """Per entity in passives(): EMP countdown, Opravna healing, Exo shield regen, Nekromant cooldown."""
        if e.cat == 'b':
            if e.off > 0:
                e.off = max(0.0, e.off - dt)
            if repairs and e.hp < e.maxhp and any(r.side == e.side and r is not e and max(abs(r.cx - e.cx), abs(r.cy - e.cy)) <= 1
                                                  for r in repairs):
                e.hp = min(e.maxhp, e.hp + 5 * dt)
        elif e.kind == 'exo':
            d = DEFS['exo']
            e.sh_t += dt
            if e.sh_t >= d['sh_wait'] and e.sh < d['sh']:
                e.sh = min(float(d['sh']), e.sh + d['sh_regen'] * dt)
        elif e.kind == 'nekromant' and e.rcd > 0:
            e.rcd = max(0.0, e.rcd - dt)

    def fac_damage(self, tgt, hit, src, ranged):
        """Faction damage rules on one hit: Kult zdmg_in, Exo shield, thorns. Returns the hit that lands."""
        if src is not None and src.cat == 'z' and tgt.cat in 'uk' and tgt.side in (0, 1):
            zi = self.fm(tgt.side).get('zdmg_in')
            if zi:
                hit *= zi
        if tgt.kind == 'exo' and tgt.sh > 0:
            if hit >= 1:
                tgt.sh_t = 0.0
            a = min(tgt.sh, hit)
            tgt.sh -= a
            hit -= a
        elif tgt.kind == 'exo' and hit >= 1:
            tgt.sh_t = 0.0
        th = DEFS[tgt.kind].get('thorns') if tgt.cat == 'b' else None
        if th and not ranged and src is not None and not src.dead and src.cat in 'uz' and hit > 0:
            self.damage(src, hit * th, tgt.side)
        return hit

    def scrap_income(self, s):
        """Dílna scrap per second (path A Šrotiště +0.6); a Dílna that is off produces nothing."""
        v = 0.0
        for e in self.ents.values():
            if e.kind == 'dilna' and e.side == s and e.off <= 0:
                v += DEFS['dilna']['scrap'][e.lvl - 1] + (0.6 if e.path == 'A' else 0.0)
        return v

    def nest_tick(self, e, dt):
        """Hnízdo: every `every[lvl-1]` s a release from the Mist on the foe (A: 2 Běžci, B: every 5th an Obr). Paused while off."""
        if e.off > 0:
            return
        e.ht += dt
        if e.ht < DEFS['hnizdo']['every'][e.lvl - 1]:
            return
        e.ht = 0.0
        e.hn += 1
        if e.path == 'B' and e.hn % 5 == 0:
            kinds = ['obr']
        elif e.path == 'A':
            kinds = ['bezec', 'bezec']
        else:
            kinds = ['chodec']
        foe = 1 - e.side
        self.spawn_zombies(kinds, self.map.spawn[foe], foe, own=e.side)

    def clouds_tick(self, dt):
        """Mor clouds: 10 dmg/s to foe units and the King within 1.5 (Chebyshev) of the centre; marks them for the raise."""
        dps = DEFS['mor']['dps']
        keep = []
        for c in self.clouds:
            s, x, y = c[0], c[1], c[2]
            for o in list(self.ents.values()):
                if (not o.dead and o.side == 1 - s and o.cat in 'uk'
                        and abs(o.x - x) <= 1.5 and abs(o.y - y) <= 1.5):
                    o.plague, o.plague_t = s, self.t
                    self.damage(o, dps * dt, s)
            c[3] -= dt
            if c[3] > 0:
                keep.append(c)
        self.clouds = keep

    # ------------------------------------------------ cards and perks
    def emp(self, s, x, y):
        """EMP výboj: enemy buildings in the 3x3 are off for `dur` s; enemy units, the King and every zombie there are stunned."""
        d = DEFS['emp']
        for o in self.ents.values():
            if o.dead or abs(o.cx - x) > 1 or abs(o.cy - y) > 1:
                continue
            if o.cat == 'b':
                if o.side == 1 - s:
                    o.off = d['dur']
                    o.aim = None
            elif o.cat == 'z' or (o.cat in 'uk' and o.side == 1 - s):
                o.stun = max(o.stun, d['stun'])
        self.fx.append(['E', x, y, 1.5, 0, s])

    def tesla_glove(self, k, first, arc):
        """Tesla-rukavice (Korporace King): every arc[0]-th shot jumps to up to arc[1] more visible foes within arc[2]."""
        k.shots += 1
        if k.shots % arc[0]:
            return
        r2 = arc[2] * arc[2]
        pool = [o for o in self.ents.values() if not o.dead and o.side != k.side and o.kind != 'mina'
                and o.own != k.side and o is not first and self.can_see(k.side, o)]
        last = first
        for _ in range(arc[1]):
            nxt = min((o for o in pool if not o.dead and (o.x - last.x) ** 2 + (o.y - last.y) ** 2 <= r2),
                      key=self.near_key(k.side, last.x, last.y), default=None)
            if nxt is None:
                break
            pool.remove(nxt)
            self.fx.append(['z', round(last.x, 2), round(last.y, 2), round(nxt.x, 2), round(nxt.y, 2), k.side])
            self.damage(nxt, 14, k.side, None, k, ranged=True)
            last = nxt
