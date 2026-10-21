"""Units and zombies: chess movement and melee."""
import math

from . import defs as D
from .defs import (W, H, HALF, MIST, TICK, N4, N8, LVL_MULT, DEFS, CMDS, RESEARCH, RARITY, KRAL, ABILITIES,  # noqa: F401
                   ATTACK_TOWERS, BASE_KIT, KING_DEAD, STREAK, home_col, own_half, local_x, roman)
from .maps import bfs, bfs_from, WALK, BUILD  # noqa: F401


class MoveMixin:
    def blocked_cell(self, x, y):
        return MIST[0] <= x <= MIST[1] and any(b[0] == y for b in self.barriers)

    def can_enter(self, e, x, y):
        if not (0 <= x < W and 0 <= y < H):
            return False
        c = self.ter[y][x]
        if (c != '.' and c not in WALK) or self.mob[y][x] is not None or self.blocked_cell(x, y):
            return False
        if self.may_enter is not None and not self.may_enter(self, e, x, y):    # rules.unit_may_enter
            return False
        b = self.bld[y][x]
        if b is None or b.kind == 'mina':     # traps never block: enemies walk onto them
            return True
        return e.cat == 'u' and b.side == e.side

    def kral_in(self, x, y, side):
        for sd in self.sd:
            k = sd.kral
            if k and not k.dead and k.side != side and k.cx == x and k.cy == y:
                return k
        return None

    def target_at(self, e, x, y):
        """Hostile thing in cell (x, y) for attacker e, or None. Off-board columns are thrones."""
        if not (0 <= y < H):
            return None
        own = e.own                       # an owned zombie never targets its owner's things (never set when compat05)
        if x < 0 or x >= W:
            side = 0 if x < 0 else 1
            return side if (side != own if e.cat == 'z' else side != e.side) else None

        m = self.mob[y][x]
        if (m is not None and not m.dead and m.side != e.side and not (e.cat == 'z' and m.cat == 'z')
                and m.side != own and m.own != e.side):
            return m
        k = self.kral_in(x, y, e.side)
        if k and k.side != own:
            return k
        b = self.bld[y][x]
        if b is not None and not b.dead and b.side != e.side and b.kind != 'mina' and b.side != own:
            return b
        return None

    def attack_cells(self, e):
        f = e.fwd()
        k = e.kind
        if k == 'pesak':
            return ((f, 1), (f, -1), (f, 0))
        if k == 'jezdec':
            return ((2 * f, 1), (2 * f, -1), (f, 2), (f, -2), (f, 0), (-f, 2), (-f, -2), (-2 * f, 1), (-2 * f, -1))
        if k == 'obrnenec':
            return ((f, 0), (0, 1), (0, -1), (-f, 0))
        if k == 'strelec':
            return ((f, 1), (f, -1), (-f, 1), (-f, -1), (f, 0))
        if k in ('medik', 'nekromant'):
            return ((f, 0), (0, 1), (0, -1))
        if k in ('dama', 'exo'):
            return N8
        if k == 'mrchozrout':
            return ((f, 0), (f, 1), (f, -1), (0, 1), (0, -1))
        return ((f, 0),) + N8

    def move_cells(self, e):
        f = e.fwd()
        k = e.kind
        if k in ('pesak', 'saboter'):
            return ((f, 0),), ((0, 1), (0, -1))
        if k == 'jezdec':
            return ((2 * f, 1), (2 * f, -1), (f, 2), (f, -2)), ((0, 1), (0, -1))
        if k == 'strelec':
            return ((f, 1), (f, -1)), ((0, 1), (0, -1))
        if k in ('medik', 'mrchozrout', 'nekromant'):
            return ((f, 0), (f, 1), (f, -1)), ((0, 1), (0, -1))
        if k in ('dama', 'exo'):

            return ((f, 0), (f, 1), (f, -1), (0, 1), (0, -1)), ((-f, 0), (-f, 1), (-f, -1))
        if e.cat == 'z' and self.lure:
            return N4, N4
        return ((f, 0), (0, 1), (0, -1)), ((0, 1), (0, -1), (-f, 0))

    def mobile(self, e, dt):
        if e.at < 1.0:
            e.at = min(1.0, e.at + dt / e.adur)
            e.x = e.ax + (e.cx - e.ax) * e.at
            e.y = e.ay + (e.cy - e.ay) * e.at
        e.cd -= dt
        e.mcd -= dt
        if e.stun > 0:
            e.stun -= dt
            return
        if e.kind == 'saboter':
            return self.saboteur(e)
        tgt = None
        for dx, dy in self.attack_cells(e):
            tgt = self.target_at(e, e.cx + dx, e.cy + dy)
            if tgt is not None:
                break
        if tgt is not None:
            if e.cd <= 0 and e.at >= 1.0:
                e.cd = DEFS[e.kind]['rate']
                if isinstance(tgt, int):
                    tx, ty = (-0.5 if tgt == 0 else W - 0.5), e.y
                else:
                    tx, ty = tgt.x, tgt.y
                self.fx.append(['m', round(e.x, 2), round(e.y, 2), round(tx, 2), round(ty, 2), e.side])
                self.damage(tgt, self.dmg_of(e), e.side, e.kind, e)
                if e.kind == 'strelec' and not isinstance(tgt, int) and tgt.cat == 'b':
                    foe = self.sd[tgt.side]
                    stolen = min(foe.e, 4.0)
                    foe.e -= stolen
                    self.sd[e.side].e += stolen
            e.wait = 0.0
            return
        if e.mcd > 0 or e.at < 1.0:
            return
        self.advance(e, dt)

    def advance(self, e, dt):
        if e.cat == 'z':
            dist = self.lure[3] if self.lure else self.dist[e.tgt]
        else:
            dist = self.dist[1 - e.side]
        cur = dist[e.cy][e.cx]
        main, side_moves = self.move_cells(e)
        best = None
        for dx, dy in main:
            nx, ny = e.cx + dx, e.cy + dy
            if self.can_enter(e, nx, ny) and dist[ny][nx] < cur:
                score = dist[ny][nx] + self.R.random() * 0.5
                if best is None or score < best[0]:
                    best = (score, nx, ny)
        if best is None and e.wait > 1.5:
            for dx, dy in side_moves:
                nx, ny = e.cx + dx, e.cy + dy
                if self.can_enter(e, nx, ny) and dist[ny][nx] <= cur + 1:
                    score = dist[ny][nx] + self.R.random() * 2
                    if best is None or score < best[0]:
                        best = (score, nx, ny)
        if best is None:
            e.wait += dt
            return
        _, nx, ny = best
        self.mob[e.cy][e.cx] = None
        e.ax, e.ay = e.x, e.y
        e.cx, e.cy = nx, ny
        self.mob[ny][nx] = e
        e.at = 0.0
        step = self.step_of(e)
        e.adur = min(0.45, step * 0.6)
        e.mcd = step
        e.wait = 0.0
        if e.kind == 'pesak':
            if nx == home_col(1 - e.side):
                self.promote(e)
            elif not e.vet and (nx > MIST[1] if e.side == 0 else nx < MIST[0]):
                self.make_vet(e)

    def promote(self, e):
        """Proměna pěšce: on the enemy throne column a Pěšák becomes a Dáma, keeping its wounds.
        Only one Dáma per side, so a stream of pawns cannot turn into a wall of tanks on the throne."""
        if not self.rules.promotion:
            return
        if self.count(e.side, 'dama'):
            return
        frac = e.hp / e.maxhp
        self.remove(e)
        n = self.spawn('dama', e.side, e.cx, e.cy)
        n.hp = max(1.0, n.maxhp * frac)
        n.kills, n.fast = e.kills, e.fast
        n.x, n.y, n.ax, n.ay, n.at, n.adur = e.x, e.y, e.ax, e.ay, e.at, e.adur     # finish the pawn's step
        self.fx.append(['P', e.cx, e.cy, 0, 0, e.side])
        self.event(None, 'promo', e.side)

    def saboteur(self, e):
        if e.at >= 1.0:
            f = e.fwd()
            if e.cx == home_col(1 - e.side):
                self.charges.append([e.side, ('t', 1 - e.side), 2.0, e.cx + f * 0.5, e.cy])
                self.fx.append(['c', e.cx, e.cy, 0, 0, e.side])
                return self.remove(e)
            for dx, dy in ((f, 0), (0, 1), (0, -1), (-f, 0)):
                x, y = e.cx + dx, e.cy + dy
                if 0 <= x < W and 0 <= y < H:
                    b = self.bld[y][x]
                    if b and not b.dead and b.side in (0, 1) and b.side != e.side and b.kind != 'mina':
                        self.charges.append([e.side, ('e', b.id), 2.0, x, y])
                        self.fx.append(['c', x, y, 0, 0, e.side])
                        return self.remove(e)
        if e.mcd > 0 or e.at < 1.0:
            return
        self.advance(e, TICK)
