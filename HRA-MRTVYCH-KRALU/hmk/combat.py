"""Passives, damage, kills, towers and area effects."""
import math

from . import defs as D
from .defs import (W, H, HALF, MIST, TICK, N4, N8, LVL_MULT, DEFS, CMDS, RESEARCH, RARITY, KRAL, ABILITIES,  # noqa: F401
                   ATTACK_TOWERS, BASE_KIT, KING_DEAD, STREAK, home_col, own_half, local_x, roman)
from .maps import bfs, bfs_from, WALK, BUILD  # noqa: F401


class CombatMixin:
    def passives(self, ents, dt):
        self.reflectors = [[e for e in ents if e.kind == 'hlaska' and e.path == 'B' and e.side == s] for s in (0, 1)]
        lights = self.reflectors[0] + self.reflectors[1]
        shields = [e for e in ents if e.kind == 'gen' and e.path == 'B' and e.off <= 0]
        jammers = [e for e in ents if e.kind == 'rusicka' and e.off <= 0]
        facon = self.facon
        repairs = [e for e in ents if e.kind == 'dilna' and e.path == 'B' and e.off <= 0] if facon else None
        self.masked = set()
        for j in jammers:
            if j.path == 'A':
                for e in ents:
                    if e.cat == 'b' and e.side == j.side and (e.x - j.x) ** 2 + (e.y - j.y) ** 2 <= 2.56:
                        self.masked.add(e.id)
        lo, hi = self.mist()
        for e in ents:
            if e.dead:
                continue
            e.mark = max(0.0, e.mark - dt)
            e.slow_t = max(0.0, e.slow_t - dt)
            if facon:
                self.fac_passive(e, dt, repairs)
            if e.cat == 'b':
                e.shield = any(g.side == e.side and g is not e and max(abs(g.cx - e.cx), abs(g.cy - e.cy)) <= 1 for g in shields)
                if 'ing2' in self.techs(e.side) and e.hp < e.maxhp:
                    e.hp = min(e.maxhp, e.hp + 3 * dt)
                if lo <= e.cx <= hi:
                    self.damage(e, max(3.0, 0.02 * e.maxhp) * dt, None)
            else:
                e.lit = any(h.side != e.side and (h.x - e.x) ** 2 + (h.y - e.y) ** 2 <= self.vision(h) ** 2 for h in lights)
                slow = e.slowk if e.slow_t > 0 else 0.0
                for j in jammers:
                    if j.side == e.side:
                        continue
                    r, f = (2.4, 0.45) if j.path == 'B' else ((2.0, 0.30) if j.lvl >= 2 else (1.6, 0.25))
                    if (j.x - e.x) ** 2 + (j.y - e.y) ** 2 <= r * r:
                        slow = max(slow, f)
                e.slowf = 1.0 / (1.0 - slow)
                if e.cat in 'uk' and lo <= e.cx <= hi:
                    self.damage(e, (2.0 if e.cat == 'k' else 1.5) * dt, None)
            if e.burn > 0 and not e.dead:
                e.burn -= dt
                self.damage(e, 6 * dt, e.burn_src)
            if e.kind == 'medik' and not e.dead:
                for o in ents:
                    if (o.side == e.side and o.cat in 'uk' and o is not e and not o.dead and o.hp < o.maxhp
                            and (o.x - e.x) ** 2 + (o.y - e.y) ** 2 <= 2.25):
                        o.hp = min(o.maxhp, o.hp + 6 * dt)

    def damage(self, tgt, amount, src_side, src_kind=None, src=None, ranged=False):
        if isinstance(tgt, int):          # a throne
            if self.sd[tgt].shield > 0:
                amount *= 0.2
            if src_side in (0, 1) and src_side != tgt:
                self.dealt[src_side] += max(0.0, min(amount, self.throne[tgt]))
            self.throne[tgt] -= amount
            return
        if tgt.dead:
            return
        if tgt.cat == 'k':
            sd = self.sd[tgt.side]
            if sd.dash_t > 0:
                return
            if sd.block_t >= 0:
                if ranged and self.t - sd.block_t <= KRAL['parry']:
                    sd.stats['parry'] += 1
                    back = src is not None and not src.dead
                    self.fx.append(['p', round(tgt.x, 2), round(tgt.y, 2), round(src.x, 2) if back else -1,
                                    round(src.y, 2) if back else -1, tgt.side])   # -1 = no return shot (0,0 is a real cell)
                    sd.ult = min(100.0, sd.ult + 20)
                    if back:
                        self.damage(src, amount, tgt.side, None, tgt)
                    return
                if amount >= 1:           # a real hit, not a tick of Mist or burn damage
                    self.fx.append(['g', round(tgt.x, 2), round(tgt.y, 2), 0, 0, tgt.side])
                amount *= 0.3
        mult = 1.0
        if ranged and tgt.kind == 'obrnenec':
            mult *= 0.6                   # Pancíř
        if tgt.cat == 'u' and ((src is not None and src.cat == 'b') or (ranged and src is None)):
            mult *= self.cry(tgt)         # towers and the throne gun vs war cry / Útok!
        if tgt.mark > 0:
            mult *= 1.25
        if tgt.lit:
            mult *= 1.15
        if tgt.cat == 'b':
            if tgt.shield:
                mult *= 0.7
            if src_kind:
                mult *= DEFS[src_kind].get('bld', 1.0)
        hit = amount * mult
        if self.facon:
            hit = self.fac_damage(tgt, hit, src, ranged)     # zdmg_in, Exo shield, thorns
            if tgt.dead:
                return
        if tgt.cat == 'b' and src_side in (0, 1) and src_side != tgt.side:
            self.dealt[src_side] += min(tgt.hp, hit)
        tgt.hp -= hit
        if tgt.hp <= 0:
            self.kill(tgt, src_side, src)

    def kill(self, e, src_side, src=None):
        self.remove(e)
        killer = src_side if src_side in (0, 1) else -1
        self.fx_of(e, ['x', round(e.x, 2), round(e.y, 2), 0, 0, e.cat, e.id, e.kind, e.side, killer],
                   public=killer >= 0 and killer != e.side)
        if src is not None and not src.dead and src.side != e.side:
            if src.cat == 'k':
                self.sd[src.side].ult = min(100.0, self.sd[src.side].ult + 6)
            elif src.cat == 'u':
                src.kills += 1
                if src.kills >= 3 and not src.vet:
                    self.make_vet(src)
        if killer >= 0 and e.side == 1 - killer:
            self.enemy_kill(killer)
        if e.side in (0, 1) and e.cat in 'bu':
            self.sd[e.side].stats['lost'] += 1
        if e.cat == 'k':
            sd = self.sd[e.side]
            sd.kral = None
            sd.respawn = sd.respawn_len if sd.respawn_len is not None else 0.0
            sd.block_t = -1.0
            sd.dash = False
            sd.ult_t = 0.0
            if sd.respawn_len is not None:
                self.say('Tvůj Král padl! Vrátí se za %d s, do té doby nemůžeš stavět.' % round(sd.respawn_len), e.side, 'w')
            else:
                self.say('Tvůj Král padl a už se nevrátí.', e.side, 'w')
            self.event(None, 'kk', killer)
            if killer == 1 - e.side:
                self.sd[killer].stats['kk'] += 1
                self.sd[killer].s += 20
                self.say('Zabil jsi soupeřova Krále! +20 🔩', killer)
            return
        if killer >= 0:
            sd = self.sd[killer]
            if e.cat == 'z':
                if not (e.own >= 0 and self.fm(e.own).get('noloot')):     # Kult: its zombies give no loot
                    le, ls = DEFS[e.kind]['loot']
                    if src is not None and src.kind == 'mrchozrout':
                        k = DEFS['mrchozrout']['zloot']
                        le, ls = le * k, ls * k
                    sd.e += le
                    sd.s += ls
                    v = DEFS[e.kind].get('vz', 0) or (1 if self.R.random() < 0.05 else 0)
                    sd.v += v
                sd.stats['kills'] += 1
                sd.stats['zk'] += 1
            elif e.cat == 'u' and e.side != killer:
                sd.s += 15 if e.vet else 6
                sd.stats['kills'] += 1
                sd.stats['uk'] += 1
                if ('bio2' in sd.techs and self.ter[e.cy][e.cx] in WALK and not self.mob[e.cy][e.cx]
                        and self.may_own(killer)):
                    z = self.spawn('chodec', 2, e.cx, e.cy)
                    z.tgt = e.side
                    self.set_own(z, killer)
            elif e.cat == 'b' and e.side == 1 - killer:
                sd.stats['bk'] += 1
        if self.facon and e.cat in 'uz':
            self.raise_check(e)
        if e.kind == 'alfa':
            ax, ay = self.rules.alfa_crate(self, killer, e.cx, e.cy)
            self.drop_crate(ax, ay, len(RARITY) - 1, land=0.0)
            self.say('Alfa padla! Na jejím místě leží legendární bedna.')
            self.event(None, 'alfa_dead', killer)

    def enemy_kill(self, s):
        """First blood and kill streaks: enemy units, buildings and Kings, each at most STREAK s after the last."""
        if not self.first_blood:
            self.first_blood = True
            self.event(None, 'fb', s)
        sd = self.sd[s]
        sd.streak = sd.streak + 1 if self.t - sd.streak_t <= STREAK else 1
        sd.streak_t = self.t
        if sd.streak in (2, 3) or sd.streak >= 5:
            self.event(s, 'streak', sd.streak)

    def make_vet(self, e):
        e.vet = True
        self.refresh_hp(e)
        self.fx_of(e, ['v', e.cx, e.cy, 0, 0, e.side])

    def foes_in(self, e, r2):
        return [o for o in self.ents.values()
                if not o.dead and o.cat in 'uzk' and o.side != e.side
                and (o.x - e.cx) ** 2 + (o.y - e.cy) ** 2 <= r2 and o.own != e.side and self.can_see(e.side, o)]

    def near_key(self, side, x, y):
        """Sort key for picking targets: nearest to (x, y), then nearest to own throne, then row.
        Never the entity id, so neither side gets the older targets first."""
        return lambda o: ((o.x - x) ** 2 + (o.y - y) ** 2, local_x(side, o.x), o.y)

    def tower(self, e, dt):
        k = e.kind
        if k not in ATTACK_TOWERS:
            if k == 'hnizdo':
                self.nest_tick(e, dt)
            return
        if self.sd[e.side].outage > 0 or e.off > 0:
            e.aim = None
            return
        r = self.rng(e)
        r2 = r * r
        dmg = self.dmg_of(e)
        rate = DEFS[k]['rate']
        if k == 'sniper' and e.aim is not None:
            o = e.aim
            if o.dead or (o.x - e.cx) ** 2 + (o.y - e.cy) ** 2 > r2 or not self.can_see(e.side, o):
                e.aim = None
                e.cd = 0.3
                return
            e.aim_t -= dt
            if e.aim_t > 0:
                return
            hits = [o]
            if e.path == 'A':
                near = self.near_key(e.side, e.cx, e.cy)
                hits += sorted((f for f in self.foes_in(e, r2) if f is not o), key=lambda f: (-f.hp,) + near(f))[:2]
            for h in hits:
                self.fx.append(['s', e.cx, e.cy, round(h.x, 2), round(h.y, 2), e.side])
                if e.path == 'B':
                    h.mark = 5.0
                self.damage(h, dmg, e.side, None, e, ranged=True)
            e.aim = None
            e.cd = rate
            return
        e.cd -= dt
        if e.cd > 0:
            return
        foes = self.foes_in(e, r2)
        if not foes:
            e.cd = 0.1
            return
        near = self.near_key(e.side, e.cx, e.cy)
        if k == 'kulomet':
            foes.sort(key=lambda o: (local_x(e.side, o.x),) + near(o))
            hits = foes[:2] if e.path == 'B' else foes[:1]
            if e.path == 'B':
                dmg *= 1.5
            if e.path == 'A':
                rate /= 2
            for o in hits:
                self.fx.append(['k', e.cx, e.cy, round(o.x, 2), round(o.y, 2), e.side])
                self.damage(o, dmg, e.side, None, e, ranged=True)
        elif k == 'plamen':
            self.fx.append(['f', e.cx, e.cy, round(r, 2), 0, e.side])
            for o in foes:
                self.damage(o, dmg, e.side, None, e)
                if e.path == 'A' and not o.dead:
                    o.burn = 4.0
                    o.burn_src = e.side
        elif k == 'sniper':
            o = min(foes, key=lambda f: (-f.hp,) + near(f))
            e.aim = o
            e.aim_t = DEFS[k]['aim']
            self.fx.append(['a', e.cx, e.cy, round(o.x, 2), round(o.y, 2), e.side, o.id])
            return
        elif k == 'tesla':
            n = 5 if e.path == 'A' else 3
            foes.sort(key=near)
            chain = [foes[0]]
            pool = [o for o in self.ents.values()
                    if not o.dead and o.cat in 'uzk' and o.side != e.side and o.own != e.side and self.can_see(e.side, o)]
            while len(chain) < n:
                last = chain[-1]
                nxt = min((o for o in pool if o not in chain and (o.x - last.x) ** 2 + (o.y - last.y) ** 2 <= 2.56),
                          key=self.near_key(e.side, last.x, last.y), default=None)
                if nxt is None:
                    break
                chain.append(nxt)
            px, py = e.cx, e.cy
            for o in chain:
                self.fx.append(['z', round(px, 2), round(py, 2), round(o.x, 2), round(o.y, 2), e.side])
                px, py = o.x, o.y
                if e.path == 'B':
                    o.stun = max(o.stun, 0.8)
                self.damage(o, dmg, e.side, None, e, ranged=True)
        elif k == 'hangar':
            foes.sort(key=near)
            for o in foes[:2] if e.path == 'A' else foes[:1]:
                self.fx.append(['H', e.cx, e.cy, round(o.x, 2), round(o.y, 2), e.side])
                if e.path == 'B':
                    o.slow_t, o.slowk = 1.5, 0.4
                self.damage(o, dmg, e.side, None, e, ranged=True)
        e.cd = rate

    def throne_gun(self, s, dt):
        self.throne_cd[s] -= dt
        if self.throne_cd[s] > 0:
            return
        best = min((e for e in self.ents.values() if e.cat in 'uzk' and e.side != s and not e.dead
                    and local_x(s, e.x) <= 1.5 and e.own != s and self.can_see(s, e)),
                   key=lambda e: (local_x(s, e.x), abs(e.y - H // 2), e.y), default=None)
        if best:
            self.throne_cd[s] = 0.6
            sx = -0.7 if s == 0 else W - 0.3
            self.fx.append(['t', sx, round(best.y, 2), round(best.x, 2), round(best.y, 2), s])
            self.damage(best, 16, s, None, None, ranged=True)

    def mines(self):
        for m in [e for e in self.ents.values() if e.kind == 'mina']:
            o = self.mob[m.cy][m.cx]
            hit = o is not None and o.side != m.side and o.own != m.side
            if not hit:
                for sd in self.sd:
                    k = sd.kral
                    if k and k.side != m.side and (k.x - m.cx) ** 2 + (k.y - m.cy) ** 2 <= 0.25:
                        hit = True
            if hit:
                self.remove(m)
                dmg = self.dmg_of(m)
                for v in list(self.ents.values()):
                    if (v.cat in 'uzk' and v.side != m.side and not v.dead and v.own != m.side
                            and (v.x - m.cx) ** 2 + (v.y - m.cy) ** 2 <= 1.44):
                        if m.path == 'A':
                            v.slow_t, v.slowk = 5.0, 0.5

                        elif m.path == 'B':
                            v.stun = max(v.stun, 2.5)
                        self.damage(v, dmg, m.side)
                self.fx.append(['b', m.cx, m.cy, 1.2, 0, m.side])

    def strikes_tick(self, dt):
        keep = []
        for st in self.strikes:
            st[3] -= dt
            if st[3] > 0:
                keep.append(st)
                continue
            s, x, y = st[0], st[1], st[2]
            for o in list(self.ents.values()):
                if not o.dead and o.side != s and abs(o.x - x) <= 1.5 and abs(o.y - y) <= 1.5:
                    self.damage(o, 150, s)
            self.fx.append(['b', x, y, 1.6, 0, s])
        self.strikes = keep

    def charges_tick(self, dt):
        keep = []
        for c in self.charges:
            c[2] -= dt
            if c[2] > 0:
                keep.append(c)
                continue
            kind, ref = c[1]
            if kind == 't':
                self.damage(ref, 260, c[0])
            else:
                b = self.ents.get(ref)
                if b is None or b.dead:
                    continue
                self.damage(b, 260, c[0])
            self.fx.append(['b', c[3], c[4], 1.0, 0, c[0]])
        self.charges = keep
