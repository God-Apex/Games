"""Commander (mode Stratég, MAI 5.5): Oprava, Odstřel, Sběrný dron, Štít trůnu and Útok! through 'cmd' messages.

The harness commands() with SMART on (Střední/Těžká): never leave both Odstřel and Štít on cooldown by choice.
"""
from ..defs import local_x, own_half


class Commander:
    def __init__(self, ai):
        self.ai = ai
        self.g, self.s, self.v, self.act, self.P, self.rnd = ai.g, ai.side, ai.view, ai.act, ai.P, ai.rnd
        self.foe = 1 - self.s
        self.last_throne = self.v.throne(self.s)
        self.fp = ai.plan.fp                # faction rules (None for Bez frakce)
        self.zombies_only = ai.type == 'preziti'

    def rdy(self, cid):
        sd = self.v.sd
        if sd.cd.get('cmd_' + cid, 0) > 0 or self.act.busy(('cmd', cid)):
            return False
        c = self.g.cmd_of(self.s, cid)
        return bool(c) and sd.doba >= c.get('doba', 1)

    def send(self, cid, x=0, y=0):
        self.act.push({'t': 'cmd', 'id': cid, 'x': int(x), 'y': int(y)}, 0, ('cmd', cid))

    def think(self):
        g, v, P, s = self.g, self.v, self.P, self.s
        sd = v.sd
        smart = P['anti_mate']
        busy = {c: not self.rdy(c) for c in ('odstrel', 'stit')}

        def keep(other):
            return not smart or not busy[other] or sd.check > 0 or sd.shield > 0
        attacking = sum(1 for e in v.units if local_x(self.foe, e.x) <= 8)
        # Sběrný dron on a crate that lands within 3 s
        if self.rdy('sber') and P['crates'] != 'own':
            cr = [c for c in v.crates() if c['land'] <= 3.0]
            if P['crates'] == 'free':
                cr = [c for c in cr if not any(d['s'] == self.foe for d in v.drones())]
            if cr:
                c = min(cr, key=lambda c: (c['land'], c['id']))
                self.send('sber', c['x'], c['y'])
        elif self.rdy('sber') and P['crates'] == 'own':
            mid = 7 if s == 0 else 8
            cr = [c for c in v.crates() if c['land'] <= 3.0 and c['x'] == mid]
            if cr:
                self.send('sber', cr[0]['x'], cr[0]['y'])
        # Oprava below 60 % HP
        if self.rdy('oprava'):
            hurt = [b for b in v.blds if b.hp < 0.6 * b.maxhp]
            if hurt:
                b = min(hurt, key=lambda b: (b.hp / b.maxhp, b.id))
                self.send('oprava', b.cx, b.cy)
        # Odstřel
        if self.rdy('odstrel') and keep('stit'):
            tgt = None
            if P['crates'] == 'all':
                for d in v.drones():
                    x, y = int(round(d['x'])), int(round(d['y']))
                    if d['s'] != s and d['h'] and 0 <= x < 16 and 0 <= y < 9 and v.vis(x, y):
                        tgt = (x, y)
                        break
            if tgt is None and P['relic'] in ('contest', 'retake'):
                rl = v.relic()
                if rl['on'] and rl['by'] == self.foe and rl['p'] > 0:
                    x0, x1, y0, y1 = v.relic_box()
                    cap = [e for e in v.foes if e.cat in 'uk' and x0 <= e.cx <= x1 and y0 <= e.cy <= y1]
                    if cap:
                        e = min(cap, key=lambda e: (e.hp, e.id))
                        tgt = (e.cx, e.cy)
            if tgt is None and self.zombies_only:
                # Přežití: the strongest zombie that marches on us and stands in the Mist or at the walls
                zs = [z for z in v.zombies if z.tgt == s and v.vis(z.cx, z.cy)]
                if zs:
                    z = max(zs, key=lambda z: (z.hp, -z.id))
                    if z.hp >= 150:
                        tgt = (z.cx, z.cy)
            if tgt is None and not self.zombies_only:
                foes = [e for e in v.foes if e.kind != 'mina' and v.vis(e.cx, e.cy)]
                inside = sorted([e for e in foes if e.cat == 'u' and own_half(s, e.cx)], key=lambda e: (-e.hp, e.id))
                if inside:
                    tgt = (inside[0].cx, inside[0].cy)
                elif attacking >= 2:
                    bl = sorted([e for e in foes if e.cat == 'b'], key=lambda e: (e.hp, e.id))
                    if bl:
                        tgt = (bl[0].cx, bl[0].cy)
            if tgt is not None:
                self.send('odstrel', tgt[0], tgt[1])
                busy['odstrel'] = True
        # Útok! when >= 3 units are at enemy local x <= 8
        if self.rdy('utok') and (attacking >= 3 or (self.fp is not None and self.fp.fac == 'kult' and self.fp.calls())):
            self.send('utok')
        # Štít trůnu
        th = v.throne(s)
        if self.rdy('stit'):
            hit = th < self.last_throne - 15
            if (hit and keep('odstrel')) or (smart and sd.check > 0):
                self.send('stit')
        self.last_throne = th
