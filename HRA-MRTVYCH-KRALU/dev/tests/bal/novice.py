"""NoviceBot (MAI 5.6): a scripted baseline that plays like a first-time player.

3 generators, 3 Kulomets at local x 4 (middle rows first, skipping cells that are not buildable), 2 Pěšák every 60 s,
no upgrades. Research is clicked whenever a point is ready (ing1 arm1 ing2 ing3 arm2). The King stands at home (and, like the harness bots, picks up crates near him).
Stratég: only Štít and Oprava, no Odstřel tricks.
Like a real first-timer it does not sit on its energy: once the script above is done, spare energy (>= 220) buys one
more tower from the deck (Kulomet 60 %, Plamenomet 30 %, Odstřelovač 10 %) on a random free own cell at local x 1-4,
at most one every 8 s and NOVICE_TOWERS towers in all, and above 450 it sends one extra random unit. Never upgrades.
"""
import harness as HB

NOVICE_TOWERS = 18
NOVICE_DECK = ['kulomet', 'plamen', 'sniper', 'hlaska', 'pesak', 'jezdec', 'obrnenec', 'dron']


class NoviceBot(HB.Planner):
    def __init__(self, g, s, cfg):
        super().__init__(g, s, cfg)
        self.next_wave = cfg.get('first_wave', 60.0)
        self.wave_q = []
        self.next_spare = 0.0
        self.steps = [self.s_gens(3), self.s_kulomets(3)]

    def s_kulomets(self, n):
        def f():
            g, s = self.g, self.s
            have = [e for e in HB.mine(g, s, 'kulomet')]
            if len(have) >= n:
                return 'done'
            for lx in (4, 3):
                for y in HB.ROW_ORDER:
                    x = HB.real_x(s, lx)
                    if not HB.free_cell(g, x, y) or not g.buildable(s, x) or g.ter[y][x] not in HB.S.BUILD:
                        continue
                    r = HB.try_build(g, s, 'kulomet', lx, y)
                    if r == 'ok':
                        return 'did'
                    if r == 'poor':
                        return 'wait'
            return 'done'
        return f

    def commands_novice(self):
        g, s = self.g, self.s
        if g.mode != 'strateg':
            return
        sd = g.sd[s]
        rdy = lambda c: sd.cd.get('cmd_' + c, 0) <= 0
        if rdy('oprava'):
            hurt = [b for b in HB.mine(g, s) if b.cat == 'b' and b.hp < 0.5 * b.maxhp]
            if hurt:
                b = min(hurt, key=lambda b: b.hp / b.maxhp)
                g.act(s, {'t': 'cmd', 'id': 'oprava', 'x': b.cx, 'y': b.cy})
        if rdy('stit') and g.throne[s] < self.last_throne - 15:
            g.act(s, {'t': 'cmd', 'id': 'stit', 'x': 0, 'y': 0})
        self.last_throne = g.throne[s]

    def waves(self):
        g, s = self.g, self.s
        if g.t >= self.next_wave:
            self.next_wave += 60.0
            self.wave_q += [g.t, g.t + 1.0]
        left = []
        for when in self.wave_q:
            if when > g.t:
                left.append(when)
                continue
            ok = False
            for y in (4, 3, 5, 2, 6):
                r = HB.deploy(g, s, 'pesak', HB.front_lx(g, s), y)
                if r == 'ok':
                    ok = True
                    break
                if r == 'poor':
                    break
            if not ok and g.t - when < 20:
                left.append(when)
        self.wave_q = left

    def spare(self):
        g, s = self.g, self.s
        sd = g.sd[s]
        if g.t < self.next_spare or sd.e < 220:
            return
        self.next_spare = g.t + 8.0
        towers = [e for e in HB.mine(g, s) if e.cat == 'b' and e.kind != 'gen']
        if len(towers) < NOVICE_TOWERS:
            x = self.rnd.random()
            kind = 'kulomet' if x < 0.6 else ('plamen' if x < 0.9 else 'sniper')
            cells = [(lx, y) for lx in (1, 2, 3, 4) for y in range(HB.S.H)
                     if HB.free_cell(g, HB.real_x(s, lx), y) and g.buildable(s, HB.real_x(s, lx))]
            if cells:
                lx, y = cells[self.rnd.randrange(len(cells))]
                HB.try_build(g, s, kind, lx, y)
        if sd.e >= 450:
            kind = self.rnd.choice(['pesak', 'jezdec', 'obrnenec'])
            HB.deploy(g, s, kind, HB.front_lx(g, s), self.rnd.randrange(HB.S.H))

    def tick(self):
        self.king('idle')
        self.commands_novice()
        self.research(['ing1', 'arm1', 'ing2', 'ing3', 'arm2'])
        if self.run_steps(self.steps) != 'wait':
            self.waves()
            self.spare()


HB.BOTS['novice'] = NoviceBot
