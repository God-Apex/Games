"""Fog of war and secrecy."""
import math

from . import defs as D
from .defs import (W, H, HALF, MIST, TICK, N4, N8, LVL_MULT, DEFS, CMDS, RESEARCH, RARITY, KRAL, ABILITIES,  # noqa: F401
                   ATTACK_TOWERS, BASE_KIT, KING_DEAD, STREAK, home_col, own_half, local_x, roman)
from .maps import bfs, bfs_from, WALK, BUILD  # noqa: F401


class VisionMixin:
    def secret(self, e):
        """Mines, saboteurs and buildings masked by a Rušička: the enemy must not learn about them from fx."""
        if e.kind in ('mina', 'saboter') or e.id in self.masked:
            return True
        return e.cat == 'b' and any(j.kind == 'rusicka' and j.path == 'A' and j.side == e.side
                                    and (e.x - j.x) ** 2 + (e.y - j.y) ** 2 <= 2.56 for j in self.ents.values())

    def fx_of(self, e, f, public=False):
        if not public and e.side in (0, 1) and self.secret(e):
            self.pfx[e.side].append(f)
        else:
            self.fx.append(f)

    def base_vis(self, side):
        return [[own_half(side, x) for x in range(W)] for _ in range(H)]

    def compute_vis(self, side, ents):
        """In darkness (Zatmění, Poslední noc) only the throne lights its 2 back columns, buildings see 1.5
        (Reflektor 3), units half; the King is the lamp and keeps his full vision."""
        dark = self.dark()
        if dark:
            hc = home_col(side)
            vis = [[abs(x - hc) <= 1 for x in range(W)] for _ in range(H)]
        else:
            vis = self.base_vis(side)
        srcs = []
        for e in ents:
            if e.side != side or e.dead:
                continue
            r = self.vision(e)
            if dark and e.cat == 'b':
                r = 3.0 if (e.kind == 'hlaska' and e.path == 'B') or e.kind == 'hangar' else min(r, 1.5)
            elif dark and e.cat == 'u':
                r *= 0.5
            srcs.append((e.x, e.y, r))
        srcs += [(r[0], r[1], r[3]) for r in self.sd[side].reveals]
        srcs += [(d['x'], d['y'], 1.0) for d in self.drones if d['s'] == side and d['h']]   # Odstřel can break a contested crate
        srcs += [(d['x'], d['y'], d['sc']) for d in self.drones if d['s'] == side and not d['h'] and d.get('sc')]  # Dronová letka

        for sx, sy, r in srcs:
            ri = int(math.ceil(r))
            cx, cy = int(round(sx)), int(round(sy))
            r2 = r * r + 0.01
            for y in range(max(0, cy - ri), min(H, cy + ri + 1)):
                dy2 = (y - sy) ** 2
                row = vis[y]
                for x in range(max(0, cx - ri), min(W, cx + ri + 1)):
                    if (x - sx) ** 2 + dy2 <= r2:
                        row[x] = True
        return vis

    def hidden_kind(self, e):
        return e.kind in ('mina', 'saboter') or e.id in self.masked

    def detects(self, side, e):
        """Hidden things are found by a Reflektor (Hláska B), or by walking right next to them."""
        for h in self.reflectors[side]:
            if (h.x - e.x) ** 2 + (h.y - e.y) ** 2 <= self.vision(h) ** 2:
                return True
        if e.kind == 'mina':
            return False
        r2 = 2.25 if e.kind == 'saboter' else 1.44
        for o in self.ents.values():
            if o.side == side and not o.dead and (o.x - e.x) ** 2 + (o.y - e.y) ** 2 <= r2:
                return True
        return False

    def can_see(self, side, e):
        if e.side == side:
            return True
        if not (0 <= e.cy < H and 0 <= e.cx < W) or not self.vis[side][e.cy][e.cx]:
            return False
        return not self.hidden_kind(e) or self.detects(side, e)
