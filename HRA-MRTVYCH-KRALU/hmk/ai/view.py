"""View: fog-honest perception and memory. The ONLY file in hmk/ai that may read the game's entity table.

Everything the AI knows comes from here: own entities, enemies the fog lets this side see (g.can_see), last-seen enemy
buildings (ghosts), public state (thrones, Relikvie, crates, drones, eclipses, night, Mist stage) and the fx stream.
"""
from .. import defs as D
from ..defs import W, H, ATTACK_TOWERS, DEFS, local_x
from ..maps import BUILD, WALK


class View:
    def __init__(self, g, side):
        self.g = g
        self.side = side
        self.foe = 1 - side
        self.sd = g.sd[side]
        self.ghosts = {}          # id -> [kind, x, y, lvl, path, t_seen] of enemy buildings seen earlier
        self.fx = []              # fx of the last tick this side may see
        self.events = []
        self._fxl = None
        self._fxn = 0
        self.my = []
        self.units = []
        self.blds = []
        self.foes = []            # visible enemy (foe side) entities
        self.zombies = []         # visible zombies
        self.kinds_seen = {}      # kind -> max count of that enemy kind seen at once
        self.mine_hint = 0.0      # game time of the last own unit death with no visible shooter
        self.sab_seen = False
        self._units_prev = {}
        self.ter_build = None

    # ------------------------------------------------ setup
    def set_deck(self, deck):
        """Own deck, chosen before the match starts (like a player in the lobby)."""
        if self.g.t <= 0:
            self.sd.deck = list(deck)

    def deck(self):
        return self.sd.deck

    # ------------------------------------------------ per tick
    def feed(self):
        """Collect the fx of the last tick (the list g.step appended to) through g.visible_fx, and drain the side's
        messages and events (an AI side has no client that would consume them)."""
        g, s = self.g, self.side
        out = []
        held = self._fxl
        if held is not None:
            new = held[self._fxn:] if len(held) >= self._fxn else held
            if new or g.pfx[s]:
                out = g.visible_fx(s, new)
        cur = g.fx
        self._fxl = cur
        self._fxn = len(cur)
        self.fx = out
        if g.evs[s]:
            self.events = g.evs[s]
            g.evs[s] = []
        else:
            self.events = []
        if g.msgs[s]:
            g.msgs[s] = []
        return out

    # ------------------------------------------------ per think
    def update(self):
        g, s, foe = self.g, self.side, self.foe
        my, foes, zs = [], [], []
        vis = g.vis[s]
        for e in g.ents.values():
            if e.dead:
                continue
            if e.side == s:
                my.append(e)
            elif g.can_see(s, e):
                if e.side == foe:
                    foes.append(e)
                else:
                    zs.append(e)
        self.my, self.foes, self.zombies = my, foes, zs
        self.units = [e for e in my if e.cat == 'u']
        self.blds = [e for e in my if e.cat == 'b']
        cnt = {}
        for e in foes:
            cnt[e.kind] = cnt.get(e.kind, 0) + 1
            if e.cat == 'b':
                self.ghosts[e.id] = [e.kind, e.cx, e.cy, e.lvl, e.path, g.t]
            if e.kind == 'saboter':
                self.sab_seen = True
        for k, n in cnt.items():
            if n > self.kinds_seen.get(k, 0):
                self.kinds_seen[k] = n
        seen_ids = set(e.id for e in foes)
        for gid in [i for i, gh in self.ghosts.items() if i not in seen_ids and vis[gh[2]][gh[1]]]:
            del self.ghosts[gid]       # the cell is visible and the building is not there any more
        # a unit of ours died where no enemy shooter was visible -> mines suspected
        now = {e.id: (e.x, e.y) for e in self.units}
        for gid, (x, y) in self._units_prev.items():
            if gid not in now and local_x(s, x) >= 9:
                shooter = any(o.cat == 'b' and (o.x - x) ** 2 + (o.y - y) ** 2 <= 60 for o in foes)
                if not shooter and not any(gh[0] in ATTACK_TOWERS and (gh[1] - x) ** 2 + (gh[2] - y) ** 2 <= 60
                                           for gh in self.ghosts.values()):
                    self.mine_hint = g.t
        self._units_prev = now

    # ------------------------------------------------ queries (own side)
    def mine(self, kind=None):
        return [e for e in self.my if kind is None or e.kind == kind]

    def count(self, kind):
        return sum(1 for e in self.my if e.kind == kind)

    def king(self):
        return self.sd.kral

    def foe_towers(self):
        """[(kind, x, y, lvl, path)] of enemy attack towers seen now or remembered."""
        return [(gh[0], gh[1], gh[2], gh[3], gh[4]) for gh in self.ghosts.values() if gh[0] in ATTACK_TOWERS]

    def foe_buildings(self):
        return [e for e in self.foes if e.cat == 'b']

    def free_cell(self, x, y):
        """Own building site: buildable terrain, nothing standing there, no King on it."""
        g = self.g
        return (0 <= x < W and 0 <= y < H and g.ter[y][x] in BUILD and g.bld[y][x] is None and g.mob[y][x] is None
                and not g.kral_near(x, y))

    def deploy_cell(self, x, y):
        g = self.g
        if not (0 <= x < W and 0 <= y < H) or g.ter[y][x] not in BUILD or g.mob[y][x] is not None:
            return False
        b = g.bld[y][x]
        return b is None or b.side == self.side

    def own_bld(self, x, y):
        b = self.g.bld[y][x]
        return b if b is not None and b.side == self.side else None

    def own_mob(self, x, y):
        m = self.g.mob[y][x]
        return m if m is not None and m.side == self.side else None

    def map_random(self):
        return self.g.map.random is not None

    def walk(self, x, y):
        return self.g.ter[y][x] in WALK

    def ter(self, x, y):
        return self.g.ter[y][x]

    def king_blocked(self, k, x, y):
        return self.g.kral_blocked(k, x, y)

    def buildable(self, x):
        return self.g.buildable(self.side, x)

    # ------------------------------------------------ public state
    def throne(self, side):
        return self.g.throne[side]

    def foe_shield(self):
        return self.g.sd[self.foe].shield

    def relic(self):
        return self.g.relic

    def relic_box(self):
        return self.g.map.relic

    def crates(self):
        return list(self.g.crates.values())

    def drones(self):
        return self.g.drones

    def eclipse(self):
        return self.g.eclipse()

    def ecl_times(self):
        return self.g.ecl_times()

    def ecl_len(self):
        return D.ECL_LEN

    def night(self):
        return self.g.night

    def stage(self):
        return self.g.stage

    def vis(self, x, y):
        return self.g.vis[self.side][y][x]

    def dps(self, kind, lvl=1):
        d = DEFS[kind]
        return d.get('dmg', 0) * (1.0, 1.35, 1.7)[lvl - 1] / max(0.1, d.get('rate', 1.0))
