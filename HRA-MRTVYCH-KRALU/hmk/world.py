"""Zombies, crates, drones, the Relikvie, eclipses, the Mist and checkmate."""
import math

from . import defs as D
from .defs import (W, H, HALF, MIST, TICK, N4, N8, LVL_MULT, DEFS, CMDS, RESEARCH, RARITY, KRAL, ABILITIES,  # noqa: F401
                   ATTACK_TOWERS, BASE_KIT, KING_DEAD, STREAK, home_col, own_half, local_x, roman)
from .maps import bfs, bfs_from, WALK, BUILD  # noqa: F401


class WorldMixin:
    def spawn_zombies(self, kinds, cols, target, own=-1):
        """own >= 0: the zombies belong to that side (Tlupa, Hnízdo); stops at OWNED_CAP (FAC 3)."""
        n = 0
        for kind in kinds:
            if own >= 0 and not self.may_own(own):
                break
            free = [(x, y) for x in cols for y in range(H)
                    if self.ter[y][x] in WALK and not self.mob[y][x] and not self.bld[y][x]]
            if not free:
                break
            x, y = self.R.choice(free)
            z = self.spawn(kind, 2, x, y)
            z.tgt = target
            if own >= 0:
                self.set_own(z, own)
            n += 1
        return n

    def wave(self):
        self.wave_n += 1
        n = 1 + self.wave_n // 2
        kinds = ['bezec' if self.t > 120 and self.R.random() < 0.3 else 'chodec' for _ in range(n)]
        if self.t > 300 and self.wave_n % 3 == 0:
            kinds.append('obr')
        for kind in kinds:
            pairs = [(x, y) for x in self.map.spawn[0] for y in range(H)
                     if self.ter[y][x] in WALK and not self.mob[y][x] and not self.mob[y][W - 1 - x]]
            if not pairs:
                break
            x, y = self.R.choice(pairs)
            first = self.R.randint(0, 1)          # neither side may always get the older (lower id) zombie
            for tgt in (first, 1 - first):
                self.spawn(kind, 2, x if tgt == 0 else W - 1 - x, y).tgt = tgt
        for s in (0, 1):
            if 'bio3' in self.sd[s].techs:
                foe = 1 - s
                self.spawn_zombies(['chodec', 'chodec'], self.map.spawn[foe], foe)
        self.say('Z Mlhy se valí vlna %d!' % self.wave_n)
        self.event(None, 'wave', self.wave_n)

    def drop_crate(self, x=None, y=None, rarity=None, land=10.0, min_rar=0):
        if x is None:
            cells = [(cx, cy) for cx in self.map.mid for cy in self.map.crate_rows
                     if self.ter[cy][cx] in WALK and not any(c['x'] == cx and c['y'] == cy for c in self.crates.values())]
            if not cells:
                return
            x, y = self.R.choice(cells)
        if rarity is None:
            roll = self.R.uniform(0, sum(r[1] for r in RARITY))
            rarity = 0
            for i, r in enumerate(RARITY):
                roll -= r[1]
                if roll <= 0:
                    rarity = i
                    break
            rarity = max(min_rar, rarity)
        cid = self.nid
        self.nid += 1
        self.crates[cid] = {'id': cid, 'x': x, 'y': y, 'r': rarity, 'land': land, 'ttl': 60.0, 'ch': [0.0, 0.0], 'con': False, 'now': False}
        if land > 0:
            self.crate_n += 1
            self.say('Do Mlhy padá zásobovací bedna (%s)!' % RARITY[rarity][0])
            self.event(None, 'crate', cid, rarity)

    def collect(self, s, c):
        self.crates.pop(c['id'], None)
        name, _, e, sc, v, n = RARITY[c['r']]
        sd = self.sd[s]
        sd.e += e
        sd.s += sc
        sd.v += v
        got = []
        for _ in range(n):
            card = self.R.choice(ABILITIES)
            sd.free[card] = sd.free.get(card, 0) + 1
            got.append(DEFS[card]['name'])
        sd.stats['crates'] += 1
        text = 'Bedna (%s): +%d ⚡ +%d 🔩' % (name, e, sc)
        if v:
            text += ' +%d 🧪' % v
        if got:
            text += ', zdarma: ' + ', '.join(got)
        self.say(text, s)
        self.say('Soupeř sebral zásobovací bednu (%s).' % name, 1 - s)
        self.fx.append(['o', c['x'], c['y'], c['r'], 0, s])

    def crates_tick(self, dt):
        for c in list(self.crates.values()):
            if c['land'] > 0:
                c['land'] -= dt
                continue
            c['ttl'] -= dt
            if c['ttl'] <= 0:
                del self.crates[c['id']]
                continue
            here = self.at_crate(c)
            c['now'] = len(here) == 2
            if c['now']:                  # contested: both channels freeze
                if not c['con']:
                    c['con'] = True
                    self.event(None, 'contest', c['id'])
                continue
            ch = c['ch']
            for s in (0, 1):
                ch[s] = ch[s] + dt * here[s] if s in here else max(0.0, ch[s] - dt)
                if ch[s] >= D.CRATE_CH:
                    self.collect(s, c)
                    break

    def at_crate(self, c):
        """{side: channel rate} for crate c: a unit on its cell (Mrchožrout 2x), the King within 0.7 or a hovering drone."""
        here = {}
        m = self.mob[c['y']][c['x']]
        if m is not None and m.cat == 'u':
            here[m.side] = DEFS[m.kind].get('chan', 1.0)
        for sd in self.sd:
            k = sd.kral
            if k and (k.x - c['x']) ** 2 + (k.y - c['y']) ** 2 <= 0.49:
                here[k.side] = max(here.get(k.side, 1.0), 1.0)
        for d in self.drones:
            if d['h'] and d['cid'] == c['id']:
                here[d['s']] = max(here.get(d['s'], 1.0), 1.0)
        return here

    def drones_tick(self, dt):
        keep = []
        for d in self.drones:
            c = self.crates.get(d['cid'])
            if c is None:
                continue
            if any(o.side == 1 - d['s'] and o.cat in 'uk' and (o.x - d['x']) ** 2 + (o.y - d['y']) ** 2 <= 2.25
                   for o in self.ents.values()):
                self.fx.append(['b', round(d['x'], 2), round(d['y'], 2), 0.4, 0, d['s']])
                continue
            dx, dy = c['x'] - d['x'], c['y'] - d['y']
            dist = math.hypot(dx, dy)
            step = d.get('v', 4.0) * dt

            if dist <= step:
                d['x'], d['y'], d['h'] = float(c['x']), float(c['y']), True
            else:
                d['x'] += dx / dist * step
                d['y'] += dy / dist * step
            keep.append(d)
        self.drones = keep

    def relic_tick(self, dt):
        """Relikvie: units or the King of exactly one side (no zombies) hold the zone D.RELIC_TIME s to take it."""
        rl = self.relic
        if self.t < D.RELIC_FROM:
            return
        if not rl['on']:
            rl['on'] = True
            self.event(None, 'relic_on', 1)
            self.say('V Mlze se probudila Relikvie! Obsaď ji ' + ('jednotkou nebo Králem.' if self.mode == 'kral' else 'jednotkou – pošli 2–3 jednotky do Mlhy.'))
        x0, x1, y0, y1 = self.map.relic
        sides, zombies = set(), False
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                m = self.mob[y][x]
                if m is not None:
                    zombies |= m.cat == 'z'
                    if m.cat == 'u':
                        sides.add(m.side)
        for sd in self.sd:
            k = sd.kral
            if k and x0 <= k.cx <= x1 and y0 <= k.cy <= y1:
                sides.add(k.side)
        s = next(iter(sides)) if len(sides) == 1 else -1
        if s >= 0 and s != rl['own'] and not zombies:
            if rl['by'] != s:
                rl['by'], rl['p'] = s, 0.0
            rl['p'] += dt
            if rl['p'] >= D.RELIC_TIME:
                rl.update(own=s, by=-1, p=0.0, vt=0.0)
                self.fx.append(['R', self.map.relic_fx, (y0 + y1) // 2, 0, 0, s])
                self.event(None, 'relic', s)
                self.say('Relikvie je tvoje: +2 ⚡/s a 🧪 každých 40 s.', s)
                self.say('Soupeř obsadil Relikvii!', 1 - s, 'w')
        elif not zombies and len(sides) < 2:
            rl['p'] = max(0.0, rl['p'] - dt)
            if rl['p'] <= 0:
                rl['by'] = -1
        if rl['own'] >= 0:
            rl['vt'] += dt
            self.sd[rl['own']].stats['relic_s'] += dt
            if rl['vt'] >= D.RELIC_SAMPLE:
                rl['vt'] -= D.RELIC_SAMPLE
                self.sd[rl['own']].v += 1
                self.say('Relikvie: +1 🧪', rl['own'])

    def eclipse(self):
        """[phase, secs]: 0 none left, 1 next eclipse starts in secs, 2 eclipse active for secs more."""
        if not self.night:
            for a in self.ecl_times():
                if self.t < a:
                    return [1, int(math.ceil(a - self.t))]
                if self.t < a + D.ECL_LEN:
                    return [2, int(math.ceil(a + D.ECL_LEN - self.t))]
        return [0, 0]

    def dark(self):
        return self.night or self.eclipse()[0] == 2

    def mist(self):
        return max(0, MIST[0] - self.stage), min(W - 1, MIST[1] + self.stage)

    def checkmate(self, dt):
        for s in (0, 1):
            foe = 1 - s
            sd = self.sd[s]
            hc = home_col(s)
            rows = {e.cy for e in self.ents.values() if e.cat == 'u' and e.side == foe and e.cx == hc}
            if self.mode == 'kral':
                helpless = sd.kral is None
            else:
                helpless = sd.cd.get('cmd_odstrel', 0) > 0 and sd.cd.get('cmd_stit', 0) > 0 and sd.shield <= 0
            if len(rows) >= 3 and helpless:
                if sd.check == 0:
                    self.say('ŠACH! Ubraň aspoň jednu řadu u trůnu, jinak za 10 s prohraješ.', s, 'w')
                    self.say('Dáváš ŠACH! Udrž útok u trůnu 10 s.', foe)
                sd.check += dt
                if sd.check >= D.CHECK_TIME and not self.over:
                    self.over = {'winner': foe, 'reason': 'Šach-mat! Trůn hráče %s byl obklíčen.' % self.names[s],
                                 'code': 'mat'}
            elif sd.check > 0:
                sd.check = 0.0
                self.say('Šach odvrácen.', s)
                self.say('Soupeř se ze šachu vymanil.', foe)
