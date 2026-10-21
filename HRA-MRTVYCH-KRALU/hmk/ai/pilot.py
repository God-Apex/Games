"""KingPilot (mode Král, MAI 5.5): goals, A* path on the cell grid, steering and parry/dash reflexes.

It sends the same 'in' messages as the browser: mx/my in {-1, 0, 1}, b/r held, d/u as rising edges.
"""
import heapq
import math

from ..defs import W, H, DEFS, KRAL, ATTACK_TOWERS, home_col, local_x, own_half

N8 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


class KingPilot:
    def __init__(self, ai):
        self.ai = ai
        self.g, self.s, self.v, self.act, self.P, self.rnd = ai.g, ai.side, ai.view, ai.act, ai.P, ai.rnd
        self.foe = 1 - self.s
        self.path = []                  # waypoints (cells) to the goal
        self.goal = None                # (x, y) float
        self.rep = False
        self.dir = (0, 0)
        self.dir_t = -9.0
        self.sent = None
        self.want = {'mx': 0, 'my': 0, 'b': False, 'r': False, 'd': False, 'u': False}
        self.block = None               # [t_press, t_release]
        self.dash_at = None             # [t, mx, my]
        self.retreat = False
        self.crate_id = None
        self.crate_t = 0.0
        self.crate_skip = set()
        self.last_pos = None
        self.last_move_t = 0.0
        self.goal_kind = 'idle'
        self.parries = 0
        self.fp = ai.plan.fp                # faction rules (None for Bez frakce)

    def rx(self, lx):
        return lx if self.s == 0 else W - 1 - lx

    # ------------------------------------------------ goals (each think)
    def think(self):
        g, v, P = self.g, self.v, self.P
        k = v.king()
        if k is None:
            self.path, self.goal, self.rep = [], None, False
            return
        s = self.s
        hp = k.hp / k.maxhp
        if hp < P['retreat']:
            self.retreat = True
        elif hp > P['retreat'] + 0.25:
            self.retreat = False
        tx, ty, rep, kind = self.rx(P['idle_lx']), 4, False, 'idle'
        threats = [e for e in v.foes + v.zombies if e.cat in 'uz' and local_x(s, e.x) <= 5
                   and (e.cat == 'u' or e.tgt == s)] if P['guard'] else []
        crate = None
        # the King never heals by himself: a hurt King only runs home while enemies are close or he is abroad,
        # otherwise he keeps doing the safe jobs (guard from further back, repair)
        danger = self.retreat and (not own_half(s, k.cx) or any(
            (e.x - k.x) ** 2 + (e.y - k.y) ** 2 <= 16 for e in v.foes + v.zombies if e.cat in 'uzk'))
        if danger:
            tx, ty, kind = home_col(s), 4, 'retreat'
        elif threats:
            e = min(threats, key=lambda o: (local_x(s, o.x), o.id))
            back = 3 if self.retreat else 2
            tx, ty, kind = self.rx(max(0, int(round(local_x(s, e.x))) - back)), e.cy, 'guard'
        elif self.retreat or (P['guard'] and v.night()):
            # hurt, or Poslední noc: stay home and keep the defence standing (no crates, Relikvie or escort)
            b = self.repair_target()
            if b is not None:
                tx, ty = b.cx - (1 if s == 0 else -1), b.cy
                if not (0 <= tx < W) or v.king_blocked(k, tx, ty):
                    tx, ty = b.cx, b.cy + (1 if b.cy < H - 1 else -1)
                rep, kind = True, 'repair'
        else:
            crate = self.pick_crate(k)
            if crate is not None:
                tx, ty, kind = crate['x'], crate['y'], 'crate'
            elif self.relic_ok(k):
                x0, x1, y0, y1 = v.relic_box()
                tx, ty, kind = (x0 if s == 0 else x1), (y0 + y1 + 1) // 2, 'relic'
            else:
                b = self.repair_target()
                if b is not None:
                    tx, ty = b.cx - (1 if s == 0 else -1), b.cy
                    if not (0 <= tx < W) or v.king_blocked(k, tx, ty):
                        tx, ty = b.cx, b.cy + (1 if b.cy < H - 1 else -1)
                    rep, kind = True, 'repair'
                    if P['conv'] == 'yes' and v.sd.s < 5 and v.sd.e > 200 and not self.act.busy(('conv',)):
                        self.act.push({'t': 'conv'}, 30, ('conv',))
                else:
                    lead = self.escort_lead(k)
                    if lead is not None:
                        tx, ty, kind = lead.x - (1.5 if s == 0 else -1.5), lead.y, 'escort'
        self.goal_kind = kind
        self.rep = rep
        tx = max(0.0, min(W - 1.0, tx))
        ty = max(0.0, min(H - 1.0, ty))
        self.goal = (tx, ty)
        self.path = self.astar(k, (int(round(tx)), int(round(ty))))

    def pick_crate(self, k):
        g, v, P = self.g, self.v, self.P
        if k.hp < 0.6 * k.maxhp:
            return None
        best, bd = None, None
        for c in v.crates():
            if c['land'] > 2.0 or c['id'] in self.crate_skip:
                continue
            mid = 7 if self.s == 0 else 8
            if P['crates'] == 'own' and c['x'] != mid:
                continue
            d2 = (c['x'] - k.x) ** 2 + (c['y'] - k.y) ** 2
            if d2 > 36:
                continue
            foe_hp = sum(o.hp for o in v.foes if o.cat in 'uk' and (o.x - c['x']) ** 2 + (o.y - c['y']) ** 2 <= 6.25)
            if foe_hp > (k.hp if P['crates'] == 'all' else 0.5 * k.hp):
                continue
            if bd is None or d2 < bd:
                best, bd = c, d2
        if best is not None:
            if self.crate_id != best['id']:
                self.crate_id, self.crate_t = best['id'], g.t
            elif g.t - self.crate_t > 20:
                self.crate_skip.add(best['id'])
                return None
        return best

    def relic_ok(self, k):
        g, v = self.g, self.v
        rl = v.relic()
        if not rl['on'] or rl['own'] == self.s or k.hp < 0.6 * k.maxhp:
            return False
        if not self.P['king_relic']:
            # leave the Relikvie to the units while an enemy King or units are near it (the King never heals)
            x0, x1, y0, y1 = v.relic_box()
            if any(e.cat in 'uk' and x0 - 2 <= e.cx <= x1 + 2 and y0 - 2 <= e.cy <= y1 + 2 for e in v.foes):
                return False
        if self.P['relic'] == 'lehka' and g.t < 300:
            return False
        return True

    def repair_target(self):
        v = self.v
        if not self.P['repair']:
            return None
        if v.sd.s <= 2 and not (self.P['conv'] == 'yes' and v.sd.e > 200):
            return None
        hurt = [b for b in v.blds if b.hp < self.P.get('repair_hp', 0.85) * b.maxhp and v.buildable(b.cx)]
        if not hurt:
            return None
        return min(hurt, key=lambda b: (b.hp / b.maxhp, b.id))

    def escort_lead(self, k):
        if not self.P['escort'] or k.hp < 0.45 * k.maxhp:
            return None
        us = [e for e in self.v.units if local_x(self.foe, e.x) <= 9]
        if not us:
            return None
        return min(us, key=lambda e: (local_x(self.foe, e.x), e.id))

    # ------------------------------------------------ path
    def danger_grid(self, k):
        d = self.P['danger']
        if d == 'never' or (d == 'hurt' and k.hp >= 0.5 * k.maxhp):
            return None
        grid = [[0.0] * W for _ in range(H)]
        for kind, tx, ty, lvl, path in self.v.foe_towers():
            r = DEFS[kind].get('range', 2.0) + 0.5
            ri = int(math.ceil(r))
            for y in range(max(0, ty - ri), min(H, ty + ri + 1)):
                for x in range(max(0, tx - ri), min(W, tx + ri + 1)):
                    if (x - tx) ** 2 + (y - ty) ** 2 <= r * r:
                        grid[y][x] = 3.0
        return grid

    def astar(self, k, goal):
        v = self.v
        start = (k.cx, k.cy)
        if start == goal:
            return []
        danger = self.danger_grid(k)
        free = {}

        def ok(c):
            r = free.get(c)
            if r is None:
                r = free[c] = not v.king_blocked(k, float(c[0]), float(c[1]))
            return r
        gx, gy = goal
        if not ok(goal):
            alts = [(gx + dx, gy + dy) for dx, dy in N8 if 0 <= gx + dx < W and 0 <= gy + dy < H]
            alts = [c for c in alts if ok(c)]
            if not alts:
                return []
            goal = min(alts, key=lambda c: (abs(c[0] - start[0]) + abs(c[1] - start[1]), c))
            gx, gy = goal
        openq = [(0.0, 0, start)]
        cost = {start: 0.0}
        prev = {}
        n = 0
        while openq:
            _, _, c = heapq.heappop(openq)
            if c == goal:
                break
            cx, cy = c
            for dx, dy in N8:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < W and 0 <= ny < H) or not ok((nx, ny)):
                    continue
                if dx and dy and not (ok((cx + dx, cy)) and ok((cx, cy + dy))):
                    continue
                nc = cost[c] + (1.414 if dx and dy else 1.0) + (danger[ny][nx] if danger else 0.0)
                if nc < cost.get((nx, ny), 1e9):
                    cost[(nx, ny)] = nc
                    prev[(nx, ny)] = c
                    n += 1
                    heapq.heappush(openq, (nc + max(abs(nx - gx), abs(ny - gy)), n, (nx, ny)))
        if goal not in prev:
            return []
        out = [goal]
        while out[-1] in prev and prev[out[-1]] != start:
            out.append(prev[out[-1]])
        out.reverse()
        return out

    # ------------------------------------------------ every tick
    def reflex(self, fx):
        g, v, P = self.g, self.v, self.P
        k = v.king()
        w = self.want
        if k is None:
            w.update(mx=0, my=0, b=False, r=False, d=False, u=False)
            self.block = self.dash_at = None
            self.send()
            return
        t = g.t
        sd = v.sd
        for f in fx:
            if f[0] == 'a' and f[5] == self.foe and len(f) > 6 and f[6] == k.id:
                self.on_aim(k, f, t)
        # block (parry)
        b = False
        if self.block is not None:
            if t >= self.block[1]:
                self.block = None
            elif t >= self.block[0]:
                b = True
        # steering
        mx, my = self.steer(k, t)
        d = False
        if self.dash_at is not None and t >= self.dash_at[0]:
            mx, my = self.dash_at[1], self.dash_at[2]
            d = sd.dash_cd <= 0
            self.dash_at = None
            self.dir, self.dir_t = (mx, my), t
        elif (self.retreat and P['dash_p'] > 0 and sd.dash_cd <= 0 and (mx or my) and not own_half(self.s, k.cx)
              and not w['d']):
            d = True
        u = False
        if sd.ult >= 100 and not own_half(self.s, k.cx) and not w['u']:
            pals = sum(1 for e in v.units if (e.x - k.x) ** 2 + (e.y - k.y) ** 2 <= 9)
            u = pals >= 2
        if (not u and sd.ult >= 100 and not w['u'] and self.fp is not None and self.fp.fac == 'kult'
                and self.fp.cry_zombies(k) >= 4):
            u = True                          # Pán mrtvých: the cry turns the zombies around the King
        near = self.goal is not None and (self.goal[0] - k.x) ** 2 + (self.goal[1] - k.y) ** 2 < 1.4
        w.update(mx=mx, my=my, b=b, r=bool(self.rep and near), d=bool(d and not w['d']), u=bool(u and not w['u']))
        self.send()

    def on_aim(self, k, f, t):
        P, sd = self.P, self.v.sd
        m, sdv = P['parry_ms']
        r = max(0.18, min(0.7, self.rnd.gauss(m, sdv) / 1000.0))
        can_block = sd.block_cd <= 0 and sd.block_t < 0 and self.block is None
        if can_block:
            if self.rnd.random() < P['parry_p']:
                self.block = [t + r, t + r + 0.35]
                self.parries += 1
            return
        if P['dash_p'] > 0 and sd.dash_cd <= 0 and self.dash_at is None and self.rnd.random() < P['dash_p']:
            dx, dy = f[3] - f[1], f[4] - f[2]
            px, py = -dy, dx
            mx = 0 if abs(px) < 0.35 * abs(py) else (1 if px > 0 else -1)
            my = 0 if abs(py) < 0.35 * abs(px) else (1 if py > 0 else -1)
            if not (mx or my):
                my = 1
            if self.v.king_blocked(k, k.x + mx * 1.0, k.y + my * 1.0):
                mx, my = -mx, -my
            self.dash_at = [t + r, mx, my]

    def steer(self, k, t):
        P = self.P
        if self.goal is None:
            want = (0, 0)
        else:
            while self.path and abs(self.path[0][0] - k.x) < 0.45 and abs(self.path[0][1] - k.y) < 0.45 and len(self.path) > 1:
                self.path.pop(0)
            if self.path and len(self.path) > 1:
                tx, ty = self.path[0]
                tol = 0.12
            else:
                tx, ty = self.goal
                tol = max(0.15, KRAL['speed'] * P['steer'] * 0.4)
            dx, dy = tx - k.x, ty - k.y
            want = (0 if abs(dx) < tol else (1 if dx > 0 else -1), 0 if abs(dy) < tol else (1 if dy > 0 else -1))
        # stuck: nudge sideways
        if self.last_pos is None or (k.x - self.last_pos[0]) ** 2 + (k.y - self.last_pos[1]) ** 2 > 0.09:
            self.last_pos, self.last_move_t = (k.x, k.y), t
        elif want != (0, 0) and t - self.last_move_t > 1.5:
            want = (want[0], self.rnd.choice((-1, 1))) if want[1] == 0 else (self.rnd.choice((-1, 1)), want[1])
            self.last_move_t = t
            self.dir, self.dir_t = want, t
            return want
        if want != self.dir and t - self.dir_t >= P['steer']:
            self.dir, self.dir_t = want, t
        return self.dir

    def send(self):
        w = self.want
        cur = (w['mx'], w['my'], w['b'], w['r'], w['d'], w['u'])
        if cur != self.sent:
            self.sent = cur
            self.act.now({'t': 'in', 'mx': w['mx'], 'my': w['my'], 'b': w['b'], 'r': w['r'], 'd': w['d'], 'u': w['u']})
