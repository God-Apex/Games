"""Profiles, XP, levels, Elo, achievements, cosmetics (META 1-3, SPEC 5.4-5.6). Stdlib only, no asyncio, unit-testable.

Public API (the callers are hmk/session.py and hmk/lobby.py):
  Store(path|None)  .load() .save() .data .dirty .ensure(key, name)      persistence (path None = memory only)
  key(name)         profile key, None = no profile (empty name or the 'Kral' placeholder)
  need(lvl) title(lvl) lvl_of(xp) bounds(xp)                             level maths (cap 30)
  xp_gain(summary, side, prof=None) -> [[label, n], ...]                 the XP parts of one human side
  elo_update(a, b, score, ka=24, kb=None) -> (a', b')
  ACH, COSM                                                              catalogs (SPEC 5.5 / 5.6)
  record(store, summary, now=None) -> {side: result}                     a finished game (SPEC 5.4 summary) -> profiles
  profile_view(store, key, name=None) -> dict|None                       the 'me' payload
  stats_view(store, key) -> dict|None                                    the 'stats' reply {prof, hist, hof, h2h}
  hof(store), cos_for(store, key), set_cos(store, key, v, name=None), owned_cos(prof), clean_cos(prof, v)
  public_catalogs() -> {cosm, ach, lvls, titles}                         merged into the 'defs' message
record() only changes memory (store.dirty = True). The caller saves right after the 'end' broadcast
(store.save()) and, 2 s after a cosmetics change, debounced.
"""
import copy
import datetime
import json
import math
import os
import shutil
import time

SCHEMA = 1
MAX_PROFILES = 500
MAX_MATCHES = 50
SER_KEEP = 10                 # only the newest matches keep their time series
MIN_LEN = 60                  # shorter games are not recorded (puzzle and vyuka excepted)
LVL_CAP = 30
MAX_H2H = 100
SER_MAX_LEN = 1500            # samples per series kept in the history

TYPES = ('souboj', 'preziti', 'vycvik', 'puzzle', 'vyuka')
MODES = ('kral', 'strateg')
DIFFS = ('lehka', 'stredni', 'tezka')
FACS = ('bez', 'prez', 'korp', 'kult')
TOT_KEYS = ('m', 'w', 'l', 'd', 'time', 'zk', 'uk', 'bk', 'kk', 'cr', 'parry', 'relic_s')
REC_IDS = ('fast_win', 'kills', 'crates', 'parry', 'relic_s', 'surv')
BY_KEYS = tuple(['souboj.' + m for m in MODES] + ['preziti.' + m for m in MODES] +
                ['vycvik.%s.%s' % (m, d) for m in MODES for d in DIFFS])

XP_BASE = {'souboj': 50, 'preziti': 40, 'vycvik': 30}
XP_WIN = {'souboj': 80, 'preziti': 60, 'vycvik': 40}
XP_DRAW = 30                                  # souboj only
XP_PER_MIN, XP_TIME_MAX = 4, 60
XP_VYUKA = 100
XP_PUZZLE_FIRST, XP_PUZZLE_REPEAT = 40, 5
DIFF_MULT = {'lehka': 0.5, 'stredni': 0.8, 'tezka': 1.0}

TITLES = [(1, 'Panoš'), (3, 'Zbrojnoš'), (5, 'Rytíř'), (8, 'Pán hradu'), (12, 'Baron'), (16, 'Hrabě'),
          (20, 'Vévoda'), (25, 'Kníže'), (30, 'Mrtvý král')]

# ---------------------------------------------------------------------------------------------- levels, keys


def key(name):
    """Profile key, or None when the name has no profile (empty or the 'Král' placeholder)."""
    k = ' '.join(name.split()).casefold() if isinstance(name, str) else ''
    return None if not k or k == 'král' else k


def need(lvl):
    """Total XP needed for level lvl (need(1) = 0)."""
    return 100 * (lvl - 1) + 25 * (lvl - 1) * (lvl - 2)


def title(lvl):
    t = TITLES[0][1]
    for at, name in TITLES:
        if lvl >= at:
            t = name
    return t


def lvl_of(xp):
    lvl = 1
    while lvl < LVL_CAP and xp >= need(lvl + 1):
        lvl += 1
    return lvl


def bounds(xp):
    """(lvl, cur, next): the XP bounds of the current level, for the XP bar. At the cap the bar is full
    (cur = need(29), next = need(30), xp >= next)."""
    lvl = lvl_of(xp)
    if lvl >= LVL_CAP:
        return lvl, need(LVL_CAP - 1), need(LVL_CAP)
    return lvl, need(lvl), need(lvl + 1)


# ---------------------------------------------------------------------------------------------- small helpers


def _rnd(x):
    """Round half away from zero (deterministic, sign-symmetric)."""
    return int(math.floor(abs(x) + 0.5)) * (1 if x >= 0 else -1)


def _int(v, lo, hi, default=0):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return default
    if isinstance(v, float) and not math.isfinite(v):
        return default
    return max(lo, min(hi, _rnd(v)))


def _num(v, lo, hi, default=0.0):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return default
    if isinstance(v, float) and not math.isfinite(v):
        return default
    return max(lo, min(hi, float(v)))


def _ints(v, n, hi=10 ** 9):
    """A list of n clamped ints, or None when v is not a list of (at least) n numbers."""
    if not isinstance(v, (list, tuple)) or len(v) < n:
        return None
    for x in v[:n]:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            return None
    return [_int(x, 0, hi) for x in v[:n]]


def _clean_name(n):
    return ' '.join(n.split())[:40] if isinstance(n, str) else ''


def _fmt_at(now):
    return now.strftime('%Y-%m-%dT%H:%M')


def _fmt_day(now):
    return now.strftime('%Y-%m-%d')


def _now(now):
    if now is None:
        return datetime.datetime.now()
    if isinstance(now, (int, float)):
        return datetime.datetime.fromtimestamp(now)
    return now


# ---------------------------------------------------------------------------------------------- cosmetics (SPEC 5.5)

COS_SLOTS = ('ban', 'kor', 'zab', 'vit')
# (slot, id, name, unlock)  unlock = None (default) | {'lvl': n} | {'ach': id}
COSM = [
    ('ban', 'rod', 'Rodový znak', None),
    ('ban', 'lebka', 'Lebka', {'ach': 'ucednik'}),
    ('ban', 'havran', 'Havran', {'ach': 'hrobnik'}),
    ('ban', 'klice', 'Zkřížené klíče', {'ach': 'relikvie'}),
    ('kor', 'zlata', 'Zlatá', None),
    ('kor', 'trnova', 'Trnová', {'ach': 'zrcadlo'}),
    ('kor', 'kostena', 'Kostěná', {'lvl': 6}),
    ('zab', 'jiskry', 'Jiskry', None),
    ('zab', 'duse', 'Odcházející duše', {'lvl': 3}),
    ('zab', 'vrany', 'Vrány', {'ach': 'sach_mat'}),
    ('vit', 'zlate', 'Zlaté jiskry', None),
    ('vit', 'zvony', 'Zvony', {'lvl': 10}),
    ('vit', 'svatozar', 'Svatozář', {'ach': 'tri_cesty'}),
]
COS_DEFAULT = {'ban': 'rod', 'kor': 'zlata', 'zab': 'jiskry', 'vit': 'zlate'}
_COS_BY_ID = dict((c[1], c) for c in COSM)


def _cos_open(c, lvl, ach):
    u = c[3]
    if not u:
        return True
    if 'lvl' in u:
        return lvl >= u['lvl']
    return u.get('ach') in ach


def owned_cos(prof):
    """Ids of every cosmetic the profile may use (defaults, level and achievement unlocks), in COSM order."""
    lvl = lvl_of(prof.get('xp', 0))
    ach = prof.get('ach') or {}
    return [c[1] for c in COSM if _cos_open(c, lvl, ach)]


def clean_cos(prof, v):
    """The cos dict {ban,kor,zab,vit} to use. v: wanted ids (a slot missing from v keeps the profile's current choice).
    A locked or unknown id falls back to the slot default. prof None = no profile = defaults."""
    own = owned_cos(prof) if prof else [c[1] for c in COSM if not c[3]]
    cur = (prof.get('cos') if prof else None) or {}
    want = v if isinstance(v, dict) else {}
    out = {}
    for slot in COS_SLOTS:
        x = want.get(slot, cur.get(slot))
        c = _COS_BY_ID.get(x) if isinstance(x, str) else None
        out[slot] = x if c and c[0] == slot and x in own else COS_DEFAULT[slot]
    return out


def cos_for(store, key):
    """The validated cosmetics of a profile key (defaults for no profile / no store / the AI)."""
    prof = store.data['players'].get(key) if store is not None and key else None
    return clean_cos(prof, None)


def set_cos(store, key, v, name=None):
    """Apply the `cos` message. Returns the validated dict, or None when there is no profile to write to.
    Creates the profile when it does not exist yet. The caller debounces store.save() by 2 s."""
    if store is None or not key:
        return None
    prof = store.ensure(key, name)
    prof['cos'] = clean_cos(prof, v)
    store.dirty = True
    return dict(prof['cos'])


# ---------------------------------------------------------------------------------------------- achievements (SPEC 5.6)


class _Ctx(object):
    """What an achievement test may look at (read-only)."""
    __slots__ = ('prof', 'S', 'side', 'p', 'st', 'typ', 'code', 'win', 'diff', 'players', 'own_t')


def _t_korunovace(c):
    if not c.win:
        return False
    if c.typ == 'souboj':
        return True
    if c.typ == 'preziti':
        return c.players == 2
    return c.typ == 'vycvik' and c.diff in ('stredni', 'tezka')


def _t_ucednik(c):
    return c.typ == 'vyuka' and c.code == 'throne' and c.S.get('winner') == c.side


def _t_sach_mat(c):
    return c.win and c.code == 'mat'


def _t_zrcadlo(c):
    return _sv(c.st, 'parry') >= 10


def _t_hrobnik(c):
    return c.prof['tot']['zk'] >= 1000


def _t_relikvie(c):
    return _sv(c.st, 'relic_s') >= 240


def _t_sberatel(c):
    return _sv(c.st, 'crates') >= 6


def _t_noc(c):
    return c.win and c.code == 'night'


def _t_tri_cesty(c):
    return all(f in c.prof['qf'] for f in ('prez', 'korp', 'kult'))


def _t_mistr(c):
    return c.win and c.typ == 'vycvik' and c.diff == 'tezka'


def _t_nezlomny(c):
    return c.typ == 'preziti' and c.own_t >= 720


def _t_velmistr(c):
    ids = _puzzle_ids()
    return bool(ids) and all((c.prof['puz'].get(i) or [0])[0] >= 1 for i in ids)


# (id, name, desc, xp, test)
ACH = [
    ('korunovace', 'Korunovace', 'Vyhraj první Souboj, Přežití 1v1 nebo Výcvik proti Střední či Těžké.', 100, _t_korunovace),
    ('ucednik', 'Učedník', 'Dokonči Výuku.', 50, _t_ucednik),
    ('sach_mat', 'Šach a mat', 'Vyhraj zápas šachmatem.', 150, _t_sach_mat),
    ('zrcadlo', 'Zrcadlo', 'Odraz v jednom zápase aspoň 10 útoků.', 150, _t_zrcadlo),
    ('hrobnik', 'Hrobník', 'Znič celkem 1000 zombie.', 200, _t_hrobnik),
    ('relikvie', 'Strážce relikvie', 'Drž Relikvii v jednom zápase aspoň 240 sekund.', 150, _t_relikvie),
    ('sberatel', 'Sběratel', 'Seber v jednom zápase aspoň 6 beden.', 100, _t_sberatel),
    ('noc', 'Přežil jsem noc', 'Vyhraj zápas, který se rozhodl v noci.', 100, _t_noc),
    ('tri_cesty', 'Tři cesty', 'Vyhraj za Přeživší, Korporaci i Kult (Souboj nebo Výcvik proti Těžké).', 300, _t_tri_cesty),
    ('mistr_vycviku', 'Mistr výcviku', 'Poraž Těžkou umělou inteligenci ve Výcviku.', 200, _t_mistr),
    ('nezlomny', 'Nezlomný', 'Vydrž v Přežití aspoň 720 sekund.', 200, _t_nezlomny),
    ('velmistr', 'Velmistr', 'Vyřeš všechna puzzle aspoň na jednu hvězdu.', 300, _t_velmistr),
]
_ACH_BY_ID = dict((a[0], a) for a in ACH)


def _puzzle_ids():
    """Ids of the shipped puzzles (hmk.puzzle once M3-B2 lands, p01-p10 until then)."""
    try:
        from . import puzzle
        ids = sorted(puzzle.PUZZLES)
        if ids:
            return ids
    except Exception:
        pass
    return ['p%02d' % i for i in range(1, 11)]


def ach_progress(prof):
    """{id: [n, goal]} for the cumulative achievements (progress bars in the Úspěchy tab)."""
    ids = _puzzle_ids()
    return {
        'hrobnik': [min(prof['tot']['zk'], 1000), 1000],
        'tri_cesty': [len([f for f in ('prez', 'korp', 'kult') if f in prof['qf']]), 3],
        'velmistr': [len([i for i in ids if (prof['puz'].get(i) or [0])[0] >= 1]), len(ids)],
    }


# ---------------------------------------------------------------------------------------------- Elo


def elo_k(n):
    """K factor: 40 for the first 10 rated games (elo_n < 10), then 24."""
    return 40 if n < 10 else 24


def elo_update(a, b, score, ka=24, kb=None):
    """New ratings (a', b') after a game. score = result of a (1 win, 0.5 draw, 0 loss). Both updates use the
    pre-game ratings; with ka == kb the rating sum is conserved exactly."""
    kb = ka if kb is None else kb
    ea = 1.0 / (1.0 + 10 ** ((b - a) / 400.0))
    da = _rnd(ka * (score - ea))
    db = _rnd(kb * ((1.0 - score) - (1.0 - ea)))
    return a + da, b + db


# ---------------------------------------------------------------------------------------------- profile schema


def _new_prof(name, day=''):
    return {
        'name': name or '', 'created': day, 'last': '',
        'xp': 0, 'lvl': 1, 'elo': 1000, 'elo_n': 0,
        'tot': dict((k, 0) for k in TOT_KEYS),
        'by': {}, 'fac': {}, 'h2h': {}, 'rec': {}, 'streak': [0, 0],
        'ach': {}, 'puz': {}, 'surv': {}, 'qf': [],
        'cos': dict(COS_DEFAULT), 'tut': 0,
    }


def _norm_prof(raw, k):
    """A clean profile from whatever the file held (wrong types dropped, numbers clamped, defaults filled)."""
    if not isinstance(raw, dict):
        return None
    d = _new_prof(_clean_name(raw.get('name')) or k)
    for f in ('created', 'last'):
        v = raw.get(f)
        if isinstance(v, str) and len(v) <= 24:
            d[f] = v
    d['xp'] = _int(raw.get('xp'), 0, 10 ** 8)
    d['lvl'] = lvl_of(d['xp'])
    d['elo'] = _int(raw.get('elo'), 100, 4000, 1000)
    d['elo_n'] = _int(raw.get('elo_n'), 0, 10 ** 6)
    tot = raw.get('tot')
    if isinstance(tot, dict):
        for f in TOT_KEYS:
            d['tot'][f] = _int(tot.get(f), 0, 10 ** 9)
    by = raw.get('by')
    if isinstance(by, dict):
        for f in BY_KEYS:
            v = _ints(by.get(f), 4)
            if v:
                d['by'][f] = v
    fac = raw.get('fac')
    if isinstance(fac, dict):
        for f in FACS:
            v = _ints(fac.get(f), 2)
            if v:
                d['fac'][f] = v
    h2h = raw.get('h2h')
    if isinstance(h2h, dict):
        items = []
        for f, v in h2h.items():
            v = _ints(v, 3)
            if isinstance(f, str) and f and len(f) <= 80 and v:
                items.append((f, v))
        items.sort(key=lambda it: (-sum(it[1]), it[0]))
        for f, v in items[:MAX_H2H]:
            d['h2h'][f] = v
    rec = raw.get('rec')
    if isinstance(rec, dict):
        for f in REC_IDS:
            v = rec.get(f)
            if isinstance(v, (list, tuple)) and len(v) >= 2 and not isinstance(v[0], bool) \
                    and isinstance(v[0], (int, float)) and isinstance(v[1], int) and not isinstance(v[1], bool):
                val = _int(v[0], 0, 10 ** 9)
                if val > 0:
                    day = v[2] if len(v) > 2 and isinstance(v[2], str) and len(v[2]) <= 24 else ''
                    d['rec'][f] = [val, _int(v[1], 0, 10 ** 9), day]
    st = _ints(raw.get('streak'), 2, 10 ** 6)
    if st:
        d['streak'] = st
    ach = raw.get('ach')
    if isinstance(ach, dict):
        for a in ACH:
            v = ach.get(a[0])
            if isinstance(v, str):
                d['ach'][a[0]] = v[:24]
    puz = raw.get('puz')
    if isinstance(puz, dict):
        for f in sorted(puz)[:64]:
            v = puz[f]
            if isinstance(f, str) and 0 < len(f) <= 16 and isinstance(v, (list, tuple)) and len(v) >= 2:
                stars = _int(v[0], 0, 3)
                if stars:
                    d['puz'][f] = [stars, round(_num(v[1], 0.0, 10 ** 6), 1)]
    surv = raw.get('surv')
    if isinstance(surv, dict):
        for f in sorted(surv)[:64]:
            v = _ints(surv[f], 2, 10 ** 6)
            if isinstance(f, str) and 0 < len(f) <= 48 and v:
                d['surv'][f] = v
    qf = raw.get('qf')
    if isinstance(qf, (list, tuple)):
        d['qf'] = [f for f in FACS if f in qf]
    d['tut'] = 1 if raw.get('tut') in (1, True) else 0
    cos = raw.get('cos')
    d['cos'] = clean_cos(d, cos if isinstance(cos, dict) else None)
    return d


def _norm_ser(ser):
    if not isinstance(ser, dict):
        return None
    out = {'dt': _num(ser.get('dt'), 0.5, 600.0, 5.0)}
    for f in ('th', 'inc', 'army'):
        v = ser.get(f)
        if not isinstance(v, (list, tuple)) or len(v) != 2 or not all(isinstance(x, (list, tuple)) for x in v):
            return None
        out[f] = [[_int(x, 0, 10 ** 8) for x in line[:SER_MAX_LEN]] for line in v]
    ecl = ser.get('ecl')
    out['ecl'] = [[_num(a, 0, 10 ** 6), _num(b, 0, 10 ** 6)] for a, b in
                  (e for e in (ecl if isinstance(ecl, list) else []) if isinstance(e, (list, tuple)) and len(e) == 2)][:40]
    n = ser.get('night')
    out['night'] = _num(n, 0, 10 ** 6) if isinstance(n, (int, float)) and not isinstance(n, bool) else None
    return out


def _norm_match(m):
    if not isinstance(m, dict) or not isinstance(m.get('id'), int) or isinstance(m.get('id'), bool):
        return None
    if not isinstance(m.get('p'), list) or not all(isinstance(x, dict) for x in m['p']):
        return None
    if m.get('type') not in TYPES:
        return None
    m = dict(m)
    if 'ser' in m:
        s = _norm_ser(m['ser'])
        if s is None:
            del m['ser']
        else:
            m['ser'] = s
    return m


def _blank():
    return {'v': SCHEMA, 'next_id': 1, 'players': {}, 'matches': []}


def normalize(raw):
    """Clean data for the store from whatever the file held. Never raises."""
    out = _blank()
    try:
        if not isinstance(raw, dict):
            return out
        players = raw.get('players')
        if isinstance(players, dict):
            for k in sorted(players):
                if isinstance(k, str) and 0 < len(k) <= 64:
                    p = _norm_prof(players[k], k)
                    if p:
                        out['players'][k] = p
        while len(out['players']) > MAX_PROFILES:
            del out['players'][_oldest(out['players'])]
        ms = []
        for m in (raw.get('matches') if isinstance(raw.get('matches'), list) else []):
            m = _norm_match(m)
            if m:
                ms.append(m)
        ms = ms[:MAX_MATCHES]
        for i, m in enumerate(ms):
            if i >= SER_KEEP:
                m.pop('ser', None)
        out['matches'] = ms
        top = max([m['id'] for m in ms] + [0]) + 1
        out['next_id'] = max(_int(raw.get('next_id'), 1, 10 ** 9, 1), top)
    except Exception:
        return _blank()
    return out


def _oldest(players, skip=None):
    return min((k for k in sorted(players) if k != skip), key=lambda k: (players[k].get('last', ''), k))


# ---------------------------------------------------------------------------------------------- Store


class Store(object):
    """stats.json: load/save with .bak and atomic replace. path None = memory only (--no-stats)."""

    def __init__(self, path=None):
        self.path = path
        self.data = _blank()
        self.dirty = False

    # -- reading
    @staticmethod
    def _read(path):
        """(data, state) state: 'ok' | 'missing' | 'bad'."""
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                raw = json.load(f)
        except FileNotFoundError:
            return None, 'missing'
        except (OSError, ValueError):
            return None, 'bad'
        if not isinstance(raw, dict):
            return None, 'bad'
        return raw, 'ok'

    def _quarantine(self):
        """Rename the unreadable main file to stats.corrupt-YYYYMMDD-HHMMSS.json. Returns the new name or '?'."""
        name = 'stats.corrupt-%s.json' % time.strftime('%Y%m%d-%H%M%S')
        try:
            os.replace(self.path, os.path.join(os.path.dirname(self.path), name))
            return name
        except OSError:
            return '?'

    def load(self):
        """Load self.path. Missing = a new file (a deleted stats.json is a deliberate reset). Corrupt = try .bak, then
        rename the bad file and start fresh. Never raises."""
        self.data = _blank()
        self.dirty = False
        if not self.path:
            return
        try:
            raw, state = self._read(self.path)
            if state == 'ok':
                self.data = normalize(raw)
                return
            if state == 'missing':
                return
            braw, bstate = self._read(self.path + '.bak')
            old = self._quarantine()
            if bstate == 'ok':
                self.data = normalize(braw)
                print('  ! stats.json poskozen, nactena zaloha .bak (stary: %s)' % old)
                self.dirty = True
            else:
                print('  ! stats.json poskozen, zalozen novy (stary: %s)' % old)
        except Exception as e:   # never raise from load
            self.data = _blank()
            print('  ! stats.json nelze nacist (%s), zalozen novy' % type(e).__name__)

    # -- writing
    @staticmethod
    def _retry(fn):
        for attempt in range(4):          # the first try + 3 retries at 50 ms (antivirus, open editor)
            try:
                return fn()
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.05)

    def save(self):
        """Atomic save: tmp -> fsync -> .bak copy of the old file -> replace. Returns True when written.
        On failure the data stays in memory and dirty stays True (the next trigger saves again)."""
        if not self.path:
            self.dirty = False
            return True
        tmp = self.path + '.tmp'

        def write_tmp():
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(blob)
                f.flush()
                os.fsync(f.fileno())
        try:
            blob = json.dumps(self.data, ensure_ascii=False, separators=(',', ':'))
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            self._retry(write_tmp)
            if os.path.exists(self.path):
                # a copy, not a move: the main file never disappears, so a crash cannot leave only a stale .bak
                self._retry(lambda: shutil.copyfile(self.path, self.path + '.bak'))
            self._retry(lambda: os.replace(tmp, self.path))
        except (OSError, ValueError, TypeError) as e:
            self.dirty = True
            print('  ! stats.json nelze ulozit (%s), zkusim to znovu pozdeji' % type(e).__name__)
            return False
        self.dirty = False
        return True

    # -- profiles
    def get(self, k):
        return self.data['players'].get(k)

    def ensure(self, k, name=None, now=None):
        """The profile of key k, created when missing (the 501st profile evicts the one with the oldest `last`)."""
        players = self.data['players']
        p = players.get(k)
        if p is None:
            if len(players) >= MAX_PROFILES:
                del players[_oldest(players, skip=k)]
            p = players[k] = _new_prof(_clean_name(name) or k, _fmt_day(_now(now)))
        return p


# ---------------------------------------------------------------------------------------------- XP (META 1.5, SPEC 5.6)


def _sv(st, k):
    """A non-negative number from the side stats dict (0 when missing)."""
    v = st.get(k) if isinstance(st, dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v >= 0 else 0.0


def _at(v, i):
    """v[i] when v is a list/tuple long enough, else 0."""
    return v[i] if isinstance(v, (list, tuple)) and len(v) > i else 0


def _pair2(v):
    """[a, b] of floats rounded to 0.1 from a list of two numbers, else [0.0, 0.0]."""
    if isinstance(v, (list, tuple)) and len(v) >= 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                              and math.isfinite(x) for x in v[:2]):
        return [round(max(0.0, min(1e6, float(x))), 1) for x in v[:2]]
    return [0.0, 0.0]


def _surv_players(S):
    sv = S.get('surv')
    return _int(sv.get('players'), 1, 2, 1) if isinstance(sv, dict) else 1


def _winner(S):
    w = S.get('winner')
    return w if w in (0, 1) and not isinstance(w, bool) else None


def _is_solo_surv(S):
    return S.get('type') == 'preziti' and _surv_players(S) == 1


def _leaver(S, side):
    """True when this side left the game (code disc or quit): the non-winner, or the only human of a solo game."""
    if S.get('code') not in ('disc', 'quit'):
        return False
    p = S.get('p') or [{}, {}]
    one_human = sum(1 for x in p if isinstance(x, dict) and x.get('human')) == 1
    return one_human or _winner(S) != side


def _result(S, side):
    """'w' | 'l' | 'd' of this side (solo Přežití has no opponent: 'd')."""
    if _is_solo_surv(S):
        return 'd'
    if _leaver(S, side):
        return 'l'
    w = _winner(S)
    return 'd' if w is None else ('w' if w == side else 'l')


def xp_gain(rec, side, prof=None):
    """XP parts [[label, n], ...] of one human side of a finished game (rec = the SPEC 5.4 summary).
    prof = the profile before the game (decides "first time" for Výuka and puzzles; None = first time).
    Achievement XP is added by record(). Only parts with n > 0 are returned."""
    typ = rec.get('type')
    code = rec.get('code')
    prof = prof or {}
    if typ == 'puzzle':
        pz = rec.get('puzzle') or {}
        if not pz.get('ok'):
            return []
        old = (prof.get('puz') or {}).get(pz.get('id'))
        return [['Vyřešení puzzle', XP_PUZZLE_REPEAT if old and old[0] >= 1 else XP_PUZZLE_FIRST]]
    if typ == 'vyuka':
        done = code == 'throne' and rec.get('winner') == side
        return [['Dokončení výuky', XP_VYUKA]] if done and not prof.get('tut') else []
    if typ not in XP_BASE:
        return []
    if code == 'disc' and _leaver(rec, side):
        return []                                 # a disconnect earns the leaver nothing
    length = _num(rec.get('len'), 0, 10 ** 6)
    ai = rec.get('ai')
    mult = DIFF_MULT.get(ai.get('diff'), 1.0) if typ == 'vycvik' and isinstance(ai, dict) else 1.0
    res = _result(rec, side)
    win = 0
    label = 'Vítězství'
    if typ == 'souboj' and res == 'd':
        win, label = XP_DRAW, 'Remíza'
    elif res == 'w' and not (typ == 'preziti' and _surv_players(rec) < 2):
        win = XP_WIN[typ]
        if code in ('disc', 'quit'):
            win = win // 2                        # the opponent left: half the win bonus
    time_xp = min(XP_TIME_MAX, XP_PER_MIN * int(length // 60))
    parts = [['Odehraná hra', _rnd(XP_BASE[typ] * mult)], ['Čas ve hře', _rnd(time_xp * mult)], [label, _rnd(win * mult)]]
    return [p for p in parts if p[1] > 0]


# ---------------------------------------------------------------------------------------------- record


def _ser_entry(S):
    ser = S.get('ser')
    if not isinstance(ser, dict):
        return None
    ser = dict(ser)
    ser['ecl'] = S.get('ecl') if isinstance(S.get('ecl'), list) else []
    ser['night'] = S.get('night')
    return _norm_ser(ser)


def _better(rid, new, old):
    return new < old if rid == 'fast_win' else new > old


def _record(store, S, now):
    if store is None or not isinstance(S, dict):
        return {}
    typ, code = S.get('type'), S.get('code')
    if typ not in TYPES or code == 'error':
        return {}
    length = _num(S.get('len'), 0.0, 10 ** 6)
    if typ in ('puzzle', 'vyuka'):
        if code in ('quit', 'disc'):
            return {}                             # not recorded
    elif length < MIN_LEN:
        return {}
    plist = S.get('p')
    if not isinstance(plist, list) or len(plist) != 2 or not all(isinstance(x, dict) for x in plist):
        return {}
    keys = [x.get('k') if x.get('human') and isinstance(x.get('k'), str) and x.get('k') else None for x in plist]
    if keys[0] is None and keys[1] is None:
        return {}
    if keys[0] == keys[1]:
        return {}                                 # the same profile on both seats: the stats would mix
    now = _now(now)
    day, at = _fmt_day(now), _fmt_at(now)
    games = typ not in ('puzzle', 'vyuka')        # counted in tot/by/fac/history
    ai = S.get('ai') if isinstance(S.get('ai'), dict) else None
    diff = ai.get('diff') if ai else None
    mode = S.get('mode') if S.get('mode') in MODES else 'kral'
    players = _surv_players(S)
    sv = S.get('surv') if isinstance(S.get('surv'), dict) else {}
    pz = S.get('puzzle') if isinstance(S.get('puzzle'), dict) else {}

    # work on copies, commit at the end (a failure never leaves half a record behind)
    work = {}
    for s in (0, 1):
        if keys[s]:
            store.ensure(keys[s], plist[s].get('n'), now)
            work[keys[s]] = copy.deepcopy(store.data['players'][keys[s]])
    res = dict((s, _result(S, s)) for s in (0, 1))
    pre = dict((s, copy.deepcopy(work[keys[s]])) for s in (0, 1) if keys[s])

    # Elo: souboj between two named humans, pre-game ratings on both sides
    elo = {}
    if typ == 'souboj' and keys[0] and keys[1]:
        a, b = work[keys[0]], work[keys[1]]
        score = {'w': 1.0, 'd': 0.5, 'l': 0.0}[res[0]]
        na, nb = elo_update(a['elo'], b['elo'], score, elo_k(a['elo_n']), elo_k(b['elo_n']))
        elo = {0: [a['elo'], na], 1: [b['elo'], nb]}

    out = {}
    entry_p = []
    for s in (0, 1):
        p = plist[s]
        st = p.get('st') if isinstance(p.get('st'), dict) else {}
        fac = p.get('fac') if p.get('fac') in FACS else 'bez'
        ent = {'k': keys[s], 'n': _clean_name(p.get('n')) or 'Král', 'h': bool(p.get('human')), 'fac': fac,
               'res': res[s], 'th': _int(p.get('th'), 0, 10 ** 6), 'doba': _int(p.get('doba'), 0, 9),
               'dmg': _int(p.get('dmg'), 0, 10 ** 9)}
        ent['inc'] = _pair2(p.get('inc'))
        for f, g in (('zk', 'zk'), ('uk', 'uk'), ('bk', 'bk'), ('kk', 'kk'), ('cr', 'crates'), ('lost', 'lost'),
                     ('parry', 'parry'), ('relic_s', 'relic_s'), ('spent', 'spent')):
            ent[f] = _rnd(_sv(st, g))
        entry_p.append(ent)
        if not keys[s]:
            continue

        prof = work[keys[s]]
        if ent['n'] != 'Král':
            prof['name'] = ent['n']
        prof['last'] = at
        win = res[s] == 'w' and code not in ('disc', 'quit') and not _is_solo_surv(S)
        parts = xp_gain(S, s, pre[s])
        new_rec = []
        t_own = _num(_at(sv.get('t'), s), 0, 10 ** 6)
        wave_own = _int(_at(sv.get('wave'), s), 0, 10 ** 6)

        if typ == 'puzzle' and pz.get('ok'):
            pid = pz.get('id')
            if isinstance(pid, str) and 0 < len(pid) <= 16:
                stars = max(1, _int(pz.get('stars'), 0, 3))
                t = round(_num(pz.get('t'), 0.0, 10 ** 6), 1)
                old = prof['puz'].get(pid)
                if not old or stars > old[0] or (stars == old[0] and t < old[1]):
                    prof['puz'][pid] = [stars, t]
        elif typ == 'vyuka' and code == 'throne' and S.get('winner') == s:
            prof['tut'] = 1

        if games:
            tot = prof['tot']
            tot['m'] += 1
            tot[res[s]] += 1
            tot['time'] += _rnd(length)
            for f, g in (('zk', 'zk'), ('uk', 'uk'), ('bk', 'bk'), ('kk', 'kk'), ('cr', 'crates'), ('parry', 'parry'),
                         ('relic_s', 'relic_s')):
                tot[f] += ent[f]
            byk = '%s.%s' % (typ, mode) + ('.' + diff if typ == 'vycvik' and diff in DIFFS else '')
            if byk in BY_KEYS:
                row = prof['by'].setdefault(byk, [0, 0, 0, 0])
                row[0] += 1
                row[{'w': 1, 'l': 2, 'd': 3}[res[s]]] += 1
            fr = prof['fac'].setdefault(fac, [0, 0])
            fr[0] += 1
            fr[1] += 1 if res[s] == 'w' else 0
            o = keys[1 - s]
            if o and typ in ('souboj', 'preziti') and not _is_solo_surv(S):
                row = prof['h2h'].setdefault(o, [0, 0, 0])
                row[{'w': 0, 'l': 1, 'd': 2}[res[s]]] += 1
                if len(prof['h2h']) > MAX_H2H:
                    del prof['h2h'][sorted(prof['h2h'], key=lambda q: (sum(prof['h2h'][q]), q))[0]]
            cur, best = prof['streak']
            if res[s] == 'w':
                cur += 1
                best = max(best, cur)
            elif res[s] == 'l':
                cur = 0
            prof['streak'] = [cur, best]
            if s in elo:
                prof['elo'] = elo[s][1]
                prof['elo_n'] += 1
            if win and (typ == 'souboj' or (typ == 'vycvik' and diff == 'tezka')) and fac in ('prez', 'korp', 'kult') \
                    and fac not in prof['qf']:
                prof['qf'] = [f for f in FACS if f in prof['qf'] or f == fac]
            if typ == 'preziti':
                sk = '%s|%s' % (S.get('map') if isinstance(S.get('map'), str) else '?', mode)
                old = prof['surv'].get(sk)
                if wave_own > 0 and (not old or wave_own > old[0] or (wave_own == old[0] and t_own > old[1])):
                    prof['surv'][sk] = [wave_own, _rnd(t_own)]
            # records (souboj and Výcvik only, except `surv`, which belongs to Přežití)
            cand = {}
            if typ in ('souboj', 'vycvik'):
                if win and (typ == 'souboj' or diff in ('stredni', 'tezka')):
                    cand['fast_win'] = _rnd(length)
                cand['kills'] = ent['zk'] + ent['uk']
                cand['crates'] = ent['cr']
                cand['parry'] = ent['parry']
                cand['relic_s'] = ent['relic_s']
            elif typ == 'preziti':
                cand['surv'] = _rnd(t_own)
            for rid in REC_IDS:
                val = cand.get(rid, 0)
                if val <= 0:
                    continue
                old = prof['rec'].get(rid)
                if old is None or _better(rid, val, old[0]):
                    prof['rec'][rid] = [val, store.data['next_id'], day]
                    if old is not None:
                        new_rec.append(rid)

        # achievements
        ctx = _Ctx()
        ctx.prof, ctx.S, ctx.side, ctx.p, ctx.st = prof, S, s, p, st
        ctx.typ, ctx.code, ctx.win, ctx.diff, ctx.players, ctx.own_t = typ, code, win, diff, players, t_own
        new_ach = []
        for a in ACH:
            if a[0] in prof['ach']:
                continue
            try:
                ok = bool(a[4](ctx))
            except Exception:
                ok = False
            if ok:
                prof['ach'][a[0]] = day
                new_ach.append(a[0])
                parts.append(['Úspěch: ' + a[1], a[3]])
        gain = sum(x[1] for x in parts)
        lvl0 = lvl_of(pre[s]['xp'])
        before = owned_cos(pre[s])
        prof['xp'] = min(10 ** 8, prof['xp'] + gain)
        prof['lvl'] = lvl_of(prof['xp'])
        ent['xp'] = gain
        if s in elo:
            ent['elo'] = elo[s]
        lvl, cur, nxt = bounds(prof['xp'])
        out[s] = {'xp_parts': parts, 'xp': gain, 'xp_tot': prof['xp'], 'lvl0': lvl0, 'lvl': lvl, 'ttl': title(lvl),
                  'cur': cur, 'next': nxt, 'lvlup': lvl > lvl0, 'new_ach': new_ach,
                  'new_cos': [c for c in owned_cos(prof) if c not in before], 'new_rec': new_rec,
                  'elo': list(elo[s]) if s in elo else None}

    # commit
    for k in sorted(work):
        store.data['players'][k] = work[k]
    if games:
        nid = store.data['next_id']
        store.data['next_id'] = nid + 1
        m = {'id': nid, 'at': at, 'type': typ, 'mode': mode, 'map': S.get('map') if isinstance(S.get('map'), str) else '?',
             'len': _rnd(length), 'code': code, 'win': _winner(S), 'ai': None, 'p': entry_p}
        if ai:
            m['ai'] = {'diff': diff if diff in DIFFS else None, 'fac': ai.get('fac') if ai.get('fac') in FACS else 'bez'}
        if typ == 'preziti':
            m['surv'] = {'players': players, 'wave': [_int(_at(sv.get('wave'), i), 0, 10 ** 6) for i in (0, 1)],
                         't': [_rnd(_num(_at(sv.get('t'), i), 0, 10 ** 6)) for i in (0, 1)]}
        ser = _ser_entry(S)
        if ser:
            m['ser'] = ser
        store.data['matches'].insert(0, m)
        del store.data['matches'][MAX_MATCHES:]
        for old in store.data['matches'][SER_KEEP:]:
            old.pop('ser', None)
    store.dirty = True
    return out


def record(store, summary, now=None):
    """Record a finished game (SPEC 5.4 summary) into the store. Returns {side: result} for the human sides that have
    a profile key: {xp_parts, xp, xp_tot, lvl0, lvl, ttl, cur, next, lvlup, new_ach, new_cos, new_rec, elo}.
    Returns {} when the game is not recorded (< 60 s, error, quit/disc in puzzle or vyuka, nobody with a key).
    Changes memory only; the caller saves. Never raises: a failure prints a line and records nothing."""
    try:
        return _record(store, summary, now)
    except Exception as e:
        print('  ! statistiky: zapis hry selhal (%s: %s)' % (type(e).__name__, e))
        return {}


# ---------------------------------------------------------------------------------------------- views


def profile_view(store, k, name=None):
    """The 'me' payload `prof` for profile key k (None for no key / no store). A profile that does not exist yet is
    shown with the defaults (level 1); it is created on the first recorded game or cosmetics change."""
    if store is None or not k:
        return None
    p = store.data['players'].get(k) or _new_prof(_clean_name(name) or k)
    lvl, cur, nxt = bounds(p['xp'])
    return {'key': k, 'name': p['name'], 'lvl': lvl, 'ttl': title(lvl), 'xp': p['xp'], 'cur': cur, 'next': nxt,
            'elo': p['elo'], 'cos': clean_cos(p, p['cos']), 'own': owned_cos(p),
            'ach': [a[0] for a in ACH if a[0] in p['ach']], 'tut': p['tut'], 'm': p['tot']['m'],
            'puz': dict((i, list(v)) for i, v in sorted(p['puz'].items())),
            'surv': dict((i, list(v)) for i, v in sorted(p['surv'].items())),
            'prog': ach_progress(p)}


def hof(store):
    """Síň slávy: profiles with >= 5 souboj games by Elo, top 10, as [name, lvl, ttl, elo, m, w]."""
    rows = []
    for k in sorted(store.data['players']):
        p = store.data['players'][k]
        m = w = 0
        for bk in ('souboj.kral', 'souboj.strateg'):
            row = p['by'].get(bk)
            if row:
                m += row[0]
                w += row[1]
        if m >= 5:
            lvl = lvl_of(p['xp'])
            rows.append([p['name'], lvl, title(lvl), p['elo'], m, w])
    rows.sort(key=lambda r: (-r[3], -r[4], r[0].casefold()))
    return rows[:10]


def stats_view(store, k):
    """The 'stats' reply for profile key k: {prof, hist, hof, h2h}, or None when that profile does not exist.
    prof = profile_view plus tot/by/fac/rec/streak/ach_at/created/last/elo_n. hist = up to 50 games involving k
    (newest first, `ser` only on the newest 10). h2h = {opponent key: [w, l, d, name]}, top 8 by games."""
    if store is None or not k or k not in store.data['players']:
        return None
    p = store.data['players'][k]
    prof = profile_view(store, k)
    prof.update({'tot': dict(p['tot']), 'by': dict((i, list(v)) for i, v in sorted(p['by'].items())),
                 'fac': dict((i, list(v)) for i, v in sorted(p['fac'].items())),
                 'rec': dict((i, list(v)) for i, v in sorted(p['rec'].items())),
                 'streak': list(p['streak']), 'ach_at': dict(sorted(p['ach'].items())),
                 'created': p['created'], 'last': p['last'], 'elo_n': p['elo_n']})
    hist = [m for m in store.data['matches'] if any(x.get('k') == k for x in m['p'])][:MAX_MATCHES]
    top = sorted(p['h2h'], key=lambda q: (-sum(p['h2h'][q]), q))[:8]
    h2h = {}
    for o in top:
        op = store.data['players'].get(o)
        h2h[o] = list(p['h2h'][o]) + [op['name'] if op else o]
    return {'prof': prof, 'hist': copy.deepcopy(hist), 'hof': hof(store), 'h2h': h2h}


def public_catalogs():
    """The meta part of the 'defs' message: cosm, ach, lvls (need for levels 1..30), titles."""
    goals = {'hrobnik': 1000, 'tri_cesty': 3, 'velmistr': len(_puzzle_ids())}
    return {
        'cosm': [{'id': c[1], 'slot': c[0], 'name': c[2], 'unlock': dict(c[3]) if c[3] else None} for c in COSM],
        'ach': [{'id': a[0], 'name': a[1], 'desc': a[2], 'xp': a[3], 'goal': goals.get(a[0])} for a in ACH],
        'lvls': [need(i) for i in range(1, LVL_CAP + 1)],
        'titles': [[lvl, name] for lvl, name in TITLES],
    }
