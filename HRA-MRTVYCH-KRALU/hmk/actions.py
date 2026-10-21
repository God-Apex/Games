"""Player actions (messages from the client or the AI)."""
import math

from . import defs as D
from .defs import (W, H, HALF, MIST, TICK, N4, N8, LVL_MULT, DEFS, CMDS, RESEARCH, RARITY, KRAL, ABILITIES,  # noqa: F401
                   ATTACK_TOWERS, BASE_KIT, KING_DEAD, STREAK, home_col, own_half, local_x, roman)
from .maps import bfs, bfs_from, WALK, BUILD  # noqa: F401

ACT_TYPES = ('in', 'res', 'horde', 'conv', 'upg', 'sell', 'build', 'unit', 'card', 'cmd', 'scrap', 'squad')

SQUAD_CD = 20.0                       # relic squad cooldown (s)
SQUAD_AT = (0.0, 4.0, 5.0)            # member deploy delays (s)
SQUAD_ROWS = (4, 4, 3)                # member target rows


class ActionsMixin:
    def act(self, s, m):
        if self.over or not self.rules.allow(self, s, m):
            return
        t = m.get('t')
        if t not in ACT_TYPES:
            return self.rules.on_msg(self, s, m)
        if t == 'in':
            return self.king_input(s, m)
        if t == 'res':
            return self.research(s, m.get('id'))
        if t == 'horde':
            return self.horde(s)
        if t == 'conv':
            return self.convert(s)
        if t == 'squad':
            return self.squad(s, m.get('id'))
        if t in ('upg', 'sell'):
            eid = m.get('id')
            e = self.ents.get(eid) if isinstance(eid, int) else None
            if not e or e.side != s or e.cat != 'b':
                return
            return self.upgrade(s, e, m.get('path')) if t == 'upg' else self.sell(s, e)
        try:
            x, y = int(m.get('x', -1)), int(m.get('y', -1))
        except (TypeError, ValueError, OverflowError):
            return
        kind = m.get('kind') if t in ('build', 'unit') else m.get('id')
        if not isinstance(kind, str) and t != 'scrap':
            return
        if t == 'build':
            self.build(s, kind, x, y)
        elif t == 'unit':
            self.deploy(s, kind, x, y)
        elif t == 'card':
            self.cast(s, kind, x, y)
        elif t == 'cmd':
            self.command(s, kind, x, y)
        elif t == 'scrap':
            self.scrap(s, x, y)

    def kral_near(self, x, y):
        return any(sd.kral and abs(sd.kral.x - x) < 0.8 and abs(sd.kral.y - y) < 0.8 for sd in self.sd)

    def build(self, s, kind, x, y):
        sd = self.sd[s]
        d = DEFS.get(kind)
        if not d or d['cat'] != 'b' or not (0 <= x < W and 0 <= y < H):
            return
        if kind not in BASE_KIT and kind not in sd.deck:
            return
        need = self.need_doba(s, kind)
        if sd.doba < need:
            return self.say('%s vyžaduje Dobu %s.' % (d['name'], roman(need)), s, 'e')
        if self.mode == 'kral' and sd.kral is None:
            return self.say(KING_DEAD, s, 'e')
        if not self.buildable(s, x):
            return self.say('Stavět můžeš jen na své polovině mimo Mlhu.', s, 'e')
        if self.ter[y][x] not in BUILD or self.bld[y][x] or self.mob[y][x] or self.kral_near(x, y):
            return self.say('Tady stavět nejde.', s, 'e')
        if 'max' in d and self.count(s, kind) >= d['max']:
            return self.say('%s smíš mít nejvýš %d.' % (d['name'], d['max']), s, 'e')
        cost = self.price(s, kind)
        if sd.e < cost[0] or sd.s < cost[1]:
            return self.say('Nedostatek surovin.', s, 'e')
        sd.e -= cost[0]
        sd.s -= cost[1]
        sd.stats['spent'] += cost[0]
        e = self.spawn(kind, s, x, y)
        e.spent = cost
        sd.stats['built'] += 1
        self.fx_of(e, ['n', x, y, 0, 0, s, kind])

    def deploy(self, s, kind, x, y):
        sd = self.sd[s]
        d = DEFS.get(kind)
        if not d or d['cat'] != 'u' or kind not in sd.deck or not (0 <= x < W and 0 <= y < H):
            return
        need = self.need_doba(s, kind)
        if sd.doba < need:
            return self.say('%s vyžaduje Dobu %s.' % (d['name'], roman(need)), s, 'e')
        if not self.buildable(s, x):
            return self.say('Jednotky nasazuješ jen na své polovině mimo Mlhu.', s, 'e')
        b = self.bld[y][x]
        if self.ter[y][x] not in BUILD or self.mob[y][x] or (b and b.side != s):
            return self.say('Sem jednotku nepostavíš.', s, 'e')
        if kind == 'dama' and self.count(s, 'dama'):
            return self.say('Hlídku smíš mít jen jednu.', s, 'e')
        if 'max' in d and self.count(s, kind) >= d['max']:
            return self.say('%s smíš mít nejvýš %d.' % (d['name'], d['max']), s, 'e')
        cost = self.price(s, kind)
        if sd.e < cost[0]:
            return self.say('Nedostatek energie.', s, 'e')
        sd.e -= cost[0]
        sd.stats['spent'] += cost[0]
        e = self.spawn(kind, s, x, y)
        if sd.mobil > 0:
            e.fast = True
            sd.mobil -= 1
        sd.stats['units'] += 1
        self.fx_of(e, ['n', x, y, 1, 0, s, kind])

    def upgrade(self, s, e, path):
        sd = self.sd[s]
        if e.lvl >= 3:
            return self.say('Stavba už má maximální úroveň.', s, 'e')
        if self.mode == 'kral' and sd.kral is None:
            return self.say(KING_DEAD, s, 'e')
        needs_path = e.lvl == 2 and 'paths' in DEFS[e.kind]
        if needs_path and path not in ('A', 'B'):
            return self.say('Na úroveň 3 vyber cestu A nebo B.', s, 'e')
        ce, cs = DEFS[e.kind]['up'][e.lvl - 1]
        if sd.e < ce or sd.s < cs:
            return self.say('Nedostatek surovin na vylepšení.', s, 'e')
        sd.e -= ce
        sd.s -= cs
        sd.stats['spent'] += ce
        e.spent[0] += ce
        e.spent[1] += cs
        e.lvl += 1
        if needs_path:
            e.path = path
        self.refresh_hp(e)
        self.fx_of(e, ['u', e.cx, e.cy, e.lvl, 0, s, e.path])

    def sell(self, s, e):
        sd = self.sd[s]
        if self.mode == 'kral' and sd.kral is None:
            return self.say(KING_DEAD, s, 'e')
        k = 0.5 * max(0.0, e.hp / e.maxhp)
        sd.e += e.spent[0] * k
        sd.s += e.spent[1] * k
        self.fx_of(e, ['r', e.cx, e.cy, 0, 0, s])
        self.remove(e)

    def convert(self, s):
        sd = self.sd[s]
        if self.t < sd.conv_t:
            return
        if sd.doba < D.CONV[2]:
            return self.say('Přetavení vyžaduje Dobu %s.' % roman(D.CONV[2]), s, 'e')
        if sd.e < D.CONV[0]:
            return self.say('Přetavení stojí %d ⚡.' % D.CONV[0], s, 'e')
        sd.e -= D.CONV[0]
        sd.s += D.CONV[1]
        sd.conv_t = self.t + 0.5

    def scrap(self, s, x, y):
        if not (0 <= x < W and 0 <= y < H) or not own_half(s, x) or self.ter[y][x] != '#':
            return
        if self.sd[s].job:
            return self.say('Čety už rozebírají jiné trosky.', s, 'e')
        self.sd[s].job = [x, y, 0.0]

    def horde(self, s):
        if self.rules.horde(self, s):
            return
        sd = self.sd[s]
        cost, cd = self.horde_cost(s)
        if sd.horde_cd > 0:
            return
        if sd.e < cost:
            return self.say('Tlupa stojí %d energie.' % cost, s, 'e')
        sd.e -= cost
        sd.stats['spent'] += cost
        sd.horde_cd = cd
        foe = 1 - s
        kinds = list(self.fm(s).get('horde_kinds') or ['chodec'] * 4 + ['bezec'])
        if self.t > 360:
            kinds.append('obr')
        n = self.spawn_zombies(kinds, self.map.spawn[foe], foe, own=s)
        self.say('Vypustil jsi tlupu (%d zombie).' % n, s)
        self.say('Soupeř na tebe poslal tlupu zombie!', foe, 'w')
        self.event(foe, 'horde', s)

    def research(self, s, rid):
        sd = self.sd[s]
        r = RESEARCH.get(rid) if isinstance(rid, str) else None
        if not r or rid in sd.techs:
            return
        if r['tier'] > 1 and '%s%d' % (r['branch'], r['tier'] - 1) not in sd.techs:
            return self.say('Nejdřív vyzkoumej předchozí stupeň.', s, 'e')
        rc = self.fm(s)['res1'] if r['tier'] == 1 and 'res1' in self.fm(s) else r['cost']
        if sd.v < rc:
            return self.say('Nemáš dost Vzorků 🧪.', s, 'e')
        sd.v -= rc
        old = sd.doba
        sd.techs.add(rid)
        sd.stats['techs'] += 1
        if rid in ('ing1', 'arm2'):
            cat = 'b' if rid == 'ing1' else 'u'
            for e in self.ents.values():
                if e.side == s and e.cat == cat:
                    self.refresh_hp(e)
        self.say('Vyzkoumáno: %s.' % r['name'], s)
        if sd.doba > old:
            self.say('Nastala Doba %s!%s' % (roman(sd.doba), ' Odemkly se silnější karty.' if sd.doba == 2 else ' +2 ⚡/s.'), s)
            self.say('Soupeř vstoupil do Doby %s.' % roman(sd.doba), 1 - s, 'w')

    def cast(self, s, card, x, y):
        sd = self.sd[s]
        d = DEFS.get(card)
        if not d or d['cat'] != 'a':
            return
        free = sd.free.get(card, 0) > 0
        if not free:
            if card not in sd.deck or sd.cd.get(card, 0) > 0:
                return
            need = self.need_doba(s, card)
            if sd.doba < need:
                return self.say('%s vyžaduje Dobu %s.' % (d['name'], roman(need)), s, 'e')
            if sd.e < self.price(s, card)[0]:
                return self.say('Nedostatek energie.', s, 'e')
        tg = d.get('target')
        if tg is not None:
            if not (0 <= x < W and 0 <= y < H):
                return
            if tg == 'vis' and not self.vis[s][y][x]:
                return self.say('Cíl musíš vidět.', s, 'e')
            if tg == 'mist' and not (MIST[0] <= x <= MIST[1]):
                return self.say('Karanténu jde použít jen v Mlze.', s, 'e')
            if card == 'navnada' and self.ter[y][x] not in WALK:
                return self.say('Návnadu polož na volné pole.', s, 'e')
        if free:
            sd.free[card] -= 1
            if sd.free[card] <= 0:
                del sd.free[card]
        else:
            cost = self.price(s, card)[0]
            sd.e -= cost
            sd.stats['spent'] += cost
            sd.cd[card] = self.card_cd(s, card)
        sd.stats['cast'] += 1
        foe = 1 - s
        if card == 'nalet':
            self.strikes.append([s, x, y, 1.5])
        elif card == 'vypadek':
            self.sd[foe].outage = 5.0
            self.say('Výpadek proudu! Tvoje věže 5 s nestřílí.', foe, 'w')
            self.say('Soupeřovy věže jsou 5 s bez proudu.', s)
        elif card == 'karantena':
            self.barriers = [b for b in self.barriers if b[0] != y] + [[y, 10.0]]
        elif card == 'navnada':
            self.lure = [x, y, 15.0, bfs_from(self.ter, [(x, y)])]
        elif card == 'dron':
            m = self.fm(s).get('dron')
            sd.reveals.append([x, y, 10.0, m[2] if m else 2.5])
        elif card == 'mobilizace':
            sd.mobil = 3
        elif card == 'emp':
            self.emp(s, x, y)
        elif card == 'mor':
            self.clouds.append([s, x, y, d['dur']])
            self.fx.append(['M', x, y, 1.5, 0, s])

    def command(self, s, cid, x, y):
        sd = self.sd[s]
        c = self.cmd_of(s, cid)
        if self.mode != 'strateg' or not c or sd.cd.get('cmd_' + cid, 0) > 0:
            return
        need = c.get('doba', 1)
        if sd.doba < need:
            return self.say('%s vyžaduje Dobu %s.' % (c['name'], roman(need)), s, 'e')
        inside = 0 <= x < W and 0 <= y < H
        if cid == 'oprava':
            b = self.bld[y][x] if inside else None
            if not b or b.side != s:
                return self.say('Klikni na svou stavbu.', s, 'e')
            b.hp = min(b.maxhp, b.hp + 0.4 * b.maxhp)
            self.fx.append(['h', x, y, 0, 0, s])
            sp = c.get('splash')
            if sp:                                    # Svépomoc (Přeživší)
                for o in self.ents.values():
                    if o.cat == 'b' and o.side == s and o is not b and max(abs(o.cx - x), abs(o.cy - y)) <= 1:
                        o.hp = min(o.maxhp, o.hp + sp * o.maxhp)
                        self.fx.append(['h', o.cx, o.cy, 0, 0, s])
        elif cid == 'odstrel':
            if not inside or not self.vis[s][y][x]:
                return self.say('Cíl musíš vidět.', s, 'e')
            for o in list(self.ents.values()):
                if not o.dead and o.side != s and o.cx == x and o.cy == y and o.kind != 'mina':
                    self.damage(o, c['dmg'], s)
            self.drones = [d for d in self.drones if d['s'] == s or (round(d['x']), round(d['y'])) != (x, y)]
            sd.reveals.append([x, y, 5.0, 1.5])
            self.fx.append(['b', x, y, 0.6, 0, s])
        elif cid == 'sber':
            crate = next((c2 for c2 in self.crates.values() if c2['x'] == x and c2['y'] == y), None)
            if not crate:
                return self.say('Klikni na zásobovací bednu.', s, 'e')
            dr = {'s': s, 'x': -0.5 if s == 0 else W - 0.5, 'y': float(H // 2), 'cid': crate['id'], 'h': False}
            if 'speed' in c:                          # Dronová letka (Korporace)
                dr['v'], dr['sc'] = c['speed'], c.get('scan', 0.0)
            self.drones.append(dr)
        elif cid == 'stit':
            sd.shield = c['dur']
        elif cid == 'utok':
            sd.cry_t = c['dur']
            self.event(None, 'utok', s)
            if c.get('turn'):                         # Volání mrtvých (Kult)
                lo, hi = self.mist()
                self.turn_zombies(s, [z for z in self.ents.values()
                                      if z.cat == 'z' and z.kind != 'alfa' and z.tgt == s and lo <= z.cx <= hi])

        sd.cd['cmd_' + cid] = c['cd']
        sd.stats['cast'] += 1

    # ------------------------------------------------ Četa na Relikvii (SPEC 4.4, Stratég only)
    def squad_kit(self, s):
        """(deck has unit cards, kinds of the 3 squad members the side may deploy now, [] if none)."""
        sd = self.sd[s]
        units = [k for k in sd.deck if k in DEFS and DEFS[k]['cat'] == 'u']
        usable = [k for k in units if sd.doba >= self.need_doba(s, k)]
        if not usable:
            return bool(units), []
        if 'obrnenec' in usable and 'pesak' in usable:
            return True, ['obrnenec', 'pesak', 'pesak']
        order = {k: i for i, k in enumerate(DEFS)}
        usable.sort(key=lambda k: (self.price(s, k)[0], order[k]))
        kit = usable[:3]
        while len(kit) < 3:
            kit.append(kit[0])
        return True, kit

    def squad(self, s, rid):
        sd = self.sd[s]
        if self.mode != 'strateg' or rid != 'relic':
            return
        if not self.relic['on']:
            return self.say('Relikvie ještě není aktivní.', s, 'e')
        left = sd.cd.get('squad', 0)
        if left > 0:
            return self.say('Další četu můžeš poslat za %d s.' % math.ceil(left), s, 'e')
        has_units, kit = self.squad_kit(s)
        if not has_units:
            return self.say('V balíčku nemáš jednotky.', s, 'e')
        if not kit:
            return self.say('Jednotky z balíčku ještě nemáš odemčené.', s, 'e')
        if sd.e < min(self.price(s, k)[0] for k in kit):
            return self.say('Na člena čety nemáš energii.', s, 'e')
        sd.cd['squad'] = SQUAD_CD
        for kind, delay, row in zip(kit, SQUAD_AT, SQUAD_ROWS):
            self.pending.append([self.t + delay, s, kind, row])
        self.say('Četa vyráží k Relikvii.', s)

    def squad_cell(self, s, row):
        """Cell for a squad member: the furthest-forward own buildable column that has a free row, nearest to `row`."""
        cols = range(HALF - 1, -1, -1) if s == 0 else range(W - HALF, W)
        rows = sorted(range(H), key=lambda y: (abs(y - row), y))
        for x in cols:
            if not self.buildable(s, x):
                continue
            for y in rows:
                b = self.bld[y][x]
                if self.ter[y][x] in BUILD and self.mob[y][x] is None and (b is None or b.side == s):
                    return x, y
        return None

    def squad_member(self, s, kind, row):
        """One squad member goes out (called from timers when its delay is over)."""
        if self.sd[s].e < self.price(s, kind)[0]:
            return self.say('Na člena čety nemáš energii.', s, 'e')
        cell = self.squad_cell(s, row)
        if cell is None:
            return self.say('Pro člena čety není místo.', s, 'e')
        self.deploy(s, kind, cell[0], cell[1])
