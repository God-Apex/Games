"""The King (mode Kral)."""
import math

from . import defs as D
from .defs import (W, H, HALF, MIST, TICK, N4, N8, LVL_MULT, DEFS, CMDS, RESEARCH, RARITY, KRAL, ABILITIES,  # noqa: F401
                   ATTACK_TOWERS, BASE_KIT, KING_DEAD, STREAK, home_col, own_half, local_x, roman)
from .maps import bfs, bfs_from, WALK, BUILD  # noqa: F401


class KingMixin:
    def king_input(self, s, m):
        if self.mode != 'kral':
            return
        sd = self.sd[s]

        def axis(v):
            try:
                return max(-1, min(1, int(v)))
            except (TypeError, ValueError, OverflowError):
                return 0
        b, d, u = bool(m.get('b')), bool(m.get('d')), bool(m.get('u'))
        old = sd.inp
        sd.inp = {'mx': axis(m.get('mx')), 'my': axis(m.get('my')), 'b': b, 'r': bool(m.get('r')), 'd': d, 'u': u}
        if b and not old['b'] and sd.kral and sd.block_cd <= 0 and sd.block_t < 0:
            sd.block_t = self.t
        elif not b and old['b'] and sd.block_t >= 0:
            sd.block_t = -1.0
            sd.block_cd = KRAL['block_cd']
        if d and not old['d'] and sd.kral:
            sd.dash = True
        k = sd.kral
        if u and not old['u'] and k and sd.ult >= 100:
            sd.ult = 0.0
            sd.ult_t = KRAL['cry']
            self.fx.append(['U', round(k.x, 2), round(k.y, 2), KRAL['cry_r'], 0, s])
            self.event(None, 'ult', s)
            r = self.fm(s).get('cry_turn')
            if r:                                     # Pán mrtvých (Kult)
                self.turn_zombies(s, [z for z in self.ents.values() if z.cat == 'z' and z.kind != 'alfa' and z.own != s
                                      and (z.x - k.x) ** 2 + (z.y - k.y) ** 2 <= r * r])

    def kral_blocked(self, k, x, y):
        r = KRAL['radius']
        if x < -0.5 + r or x > W - 0.5 - r or y < -0.5 + r or y > H - 0.5 - r:
            return True
        for cy in range(int(math.floor(y - r + 0.5)), int(math.floor(y + r + 0.5)) + 1):
            for cx in range(int(math.floor(x - r + 0.5)), int(math.floor(x + r + 0.5)) + 1):
                if 0 <= cx < W and 0 <= cy < H:
                    c = self.ter[cy][cx]
                    if (c != '.' and c not in WALK) or self.blocked_cell(cx, cy) or (self.may_enter is not None and not self.may_enter(self, k, cx, cy)):
                        return True
                    b = self.bld[cy][cx]
                    if b is not None and b.side != k.side and b.kind != 'mina':
                        return True
        return False

    def kral_slide(self, k, v, step, ahead, here, prefer):
        """Blocked head-on: drift towards the centre of a neighbouring free lane so the King slips around corners.
        Ties go towards `prefer` (own throne column for sideways slides) so both sides behave the same."""
        r = int(round(v))
        lanes = {math.floor(v), math.ceil(v), r - 1, r + 1}
        for c in sorted((c for c in lanes if abs(c - v) <= 1.0), key=lambda c: (abs(c - v), abs(c - prefer))):
            if not self.kral_blocked(k, *ahead(c)):
                nv = v + max(-step, min(step, c - v))
                return nv if not self.kral_blocked(k, *here(nv)) else v
        return v

    def dash(self, k, sd):
        """Výpad: up to KRAL['dash'] cells in the WASD direction (forward if none), stopping where the King would be blocked.
        Applied within one tick; clients draw it as a 0.18 s streak from the 'D' fx."""
        mx, my = sd.inp['mx'], sd.inp['my']
        if not (mx or my):
            mx = k.fwd()
        n = math.hypot(mx, my)
        x0, y0 = k.x, k.y
        for i in range(1, 26):
            nx, ny = x0 + mx / n * KRAL['dash'] * i / 25, y0 + my / n * KRAL['dash'] * i / 25
            if self.kral_blocked(k, nx, ny):
                break
            k.x, k.y = nx, ny
        if (k.x - x0) ** 2 + (k.y - y0) ** 2 < 0.04:
            k.x, k.y = x0, y0
            return
        k.cx, k.cy = int(round(k.x)), int(round(k.y))
        sd.dash_cd = KRAL['dash_cd']
        sd.dash_t = KRAL['dash_inv']
        self.fx.append(['D', round(x0, 2), round(y0, 2), round(k.x, 2), round(k.y, 2), k.side])

    def kral_tick(self, k, dt):
        sd = self.sd[k.side]
        k.fx_t -= dt
        if k.stun > 0:
            k.stun -= dt
            sd.dash = False
            return
        if sd.dash:
            sd.dash = False
            if sd.dash_cd <= 0:
                self.dash(k, sd)
        blocking = sd.block_t >= 0
        mx, my = sd.inp['mx'], sd.inp['my']
        if mx or my:
            sp = KRAL['speed'] * (0.4 if blocking else 1.0) / k.slowf
            if self.ter[k.cy][k.cx] == '~':
                sp *= 1.25                        # canal: the King runs faster
            if mx and my:
                sp *= 0.7071
            step = sp * dt
            stuck = self.kral_blocked(k, k.x, k.y)
            nx = k.x + mx * step
            if stuck or not self.kral_blocked(k, nx, k.y):
                k.x = nx
            elif not my:
                k.y = self.kral_slide(k, k.y, step, lambda c: (nx, c), lambda c: (k.x, c), 0)
            ny = k.y + my * step
            if stuck or not self.kral_blocked(k, k.x, ny):
                k.y = ny
            elif not mx:
                k.x = self.kral_slide(k, k.x, step, lambda c: (c, ny), lambda c: (c, k.y), home_col(k.side))
            r = KRAL['radius']
            k.x = min(W - 0.5 - r, max(-0.5 + r, k.x))
            k.y = min(H - 0.5 - r, max(-0.5 + r, k.y))
            k.cx, k.cy = int(round(k.x)), int(round(k.y))
        if sd.inp['r'] and sd.s >= 0.1:
            best, bd = None, 2.25
            for b in self.ents.values():
                if b.cat == 'b' and b.side == k.side and b.hp < b.maxhp:
                    d2 = (b.x - k.x) ** 2 + (b.y - k.y) ** 2
                    if d2 <= bd:
                        best, bd = b, d2
            if best:
                fm = self.fm(k.side)
                rep, per = fm.get('repair', KRAL['repair']), fm.get('repair_hp', 10)    # Kovář (Přeživší)
                heal = min(rep * dt, best.maxhp - best.hp, sd.s * per)
                best.hp += heal
                sd.s -= heal / per
                if k.fx_t <= 0:
                    k.fx_t = 0.5
                    self.fx.append(['h', best.cx, best.cy, 0, 0, k.side])
        k.cd -= dt
        if k.cd <= 0 and not blocking:
            r2 = KRAL['range'] ** 2
            best = min((o for o in self.ents.values() if o.side != k.side and not o.dead and o.kind != 'mina'
                        and (o.x - k.x) ** 2 + (o.y - k.y) ** 2 <= r2 and o.own != k.side and self.can_see(k.side, o)),
                       key=self.near_key(k.side, k.x, k.y), default=None)
            if best:
                k.cd = KRAL['rate'] * (0.5 if sd.ult_t > 0 else 1.0)
                self.fx.append(['q', round(k.x, 2), round(k.y, 2), round(best.x, 2), round(best.y, 2), k.side])
                self.damage(best, KRAL['dmg'], k.side, None, k, ranged=True)
                if self.facon:
                    arc = self.fm(k.side).get('arc')
                    if arc:
                        self.tesla_glove(k, best, arc)

            else:
                k.cd = 0.1
