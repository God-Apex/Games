"""Entities (buildings, units, zombies, the King) and per-side state."""
from . import defs as D
from .defs import DEFS, KRAL


class Ent:
    def __init__(self, gid, kind, side, x, y, rng):
        d = DEFS[kind]
        self.id = gid
        self.kind = kind
        self.cat = d['cat']
        self.side = side          # 0, 1, or 2 = zombie
        self.cx, self.cy = int(round(x)), int(round(y))
        self.x, self.y = float(x), float(y)
        self.ax, self.ay, self.at, self.adur = self.x, self.y, 1.0, 1.0
        self.lvl = 1
        self.path = ''
        self.maxhp = self.hp = float(d['hp'])
        self.cd = rng.uniform(0.1, 0.5)
        self.mcd = rng.uniform(0.2, 0.8)
        self.wait = 0.0
        self.burn = 0.0
        self.burn_src = None
        self.mark = 0.0
        self.lit = False
        self.shield = False
        self.stun = 0.0
        self.slow_t = 0.0
        self.slowf = 1.0
        self.vet = False
        self.kills = 0
        self.fast = False
        self.tgt = 0              # zombie: which throne it marches to
        self.spent = list(d.get('cost', [0, 0]))
        self.dead = False
        self.aim = None           # sniper target while aiming
        self.aim_t = 0.0
        self.fx_t = 0.0
        # factions (FAC 2-4); never touch rng here (draw order must equal 0.5)
        self.own = -1             # zombie sent/raised/turned by side `own` (never set when compat05)
        self.off = 0.0            # building switched off by EMP (s left)
        self.sh = float(d.get('sh', 0))   # Exoskelet shield
        self.sh_t = 0.0           # seconds since the last real hit (shield regen)
        self.rcd = 0.0            # Nekromant raise cooldown
        self.plague = -1          # side whose Mor cloud last hit this entity
        self.plague_t = -99.0     # game time of that hit
        self.ht = 0.0             # Hnízdo timer
        self.hn = 0               # Hnízdo releases so far
        self.shots = 0            # King shots (Tesla-rukavice)
        self.slowk = 0.5          # slow factor while slow_t > 0 (Chemická mina 0.5, Rušivý dron 0.4)

    def fwd(self):
        if self.cat == 'z':
            return -1 if self.tgt == 0 else 1
        return 1 if self.side == 0 else -1


class Side:
    def __init__(self, idx, name, deck, fac='bez'):
        self.idx = idx
        self.name = name
        self.deck = deck
        self.fac = fac
        self.respawn_len = KRAL['respawn']   # None = the King never comes back
        self.e, self.s, self.v = D.START_RES[0], D.START_RES[1], 0
        self.techs = set()
        self.cd = {}              # card id or 'cmd_<id>' -> seconds left
        self.free = {}            # ability id -> free charges from crates
        self.mobil = 0
        self.outage = 0.0         # own towers silenced by enemy Výpadek proudu
        self.shield = 0.0         # Stratég: throne shield time left
        self.check = 0.0          # seconds in check
        self.kral = None
        self.respawn = 0.0
        self.inp = {'mx': 0, 'my': 0, 'b': False, 'r': False, 'd': False, 'u': False}
        self.block_t = -1.0       # game time the current block started, -1 = not blocking
        self.block_cd = 0.0
        self.dash = False         # Výpad requested, done on the next tick
        self.dash_cd = 0.0
        self.dash_t = 0.0         # invulnerable after a Výpad
        self.ult = 0.0            # Válečný pokřik meter 0-100
        self.ult_t = 0.0          # war cry aura time left
        self.cry_t = 0.0          # Stratég: Útok! time left
        self.conv_t = 0.0         # earliest game time of the next Přetavení
        self.streak, self.streak_t = 0, -99.0
        self.horde_cd = 0.0
        self.job = None
        self.reveals = []         # [x, y, seconds, radius] from Průzkumný dron and Odstřel
        # kills = zk + uk. zk/uk/bk/kk: zombie, enemy unit, enemy building, King kills (credited to the killer);
        # lost: own units+buildings destroyed; relic_s: seconds holding the Relikvie; spent: energy spent; cast: abilities+commands
        self.stats = {'kills': 0, 'units': 0, 'built': 0, 'crates': 0, 'techs': 0,
                      'zk': 0, 'uk': 0, 'bk': 0, 'kk': 0, 'lost': 0, 'parry': 0, 'relic_s': 0.0, 'spent': 0, 'cast': 0}

    @property
    def doba(self):
        n = len(self.techs)
        return 3 if n >= D.DOBA_AT[1] else 2 if n >= D.DOBA_AT[0] else 1

