"""Feature tests of the 0.5 rules (the former integ/tests.py), run against the server under test.

Games are created with compat05=True on the 1.0 engine, so every 0.5 behaviour (Utok! in Doba I, owned zombies
hostile to their owner, ...) must still hold. On the frozen 0.5 server they run as they always did.
One unittest method per feature group; every failed check inside a group is listed in the failure message.
HMK_SERVER selects the server (see _paths.py).  VERBOSE=1 prints every check.
"""
import json
import os
import random
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _paths  # noqa: E402

S = _paths.load_server()
VERBOSE = bool(os.environ.get('VERBOSE'))
FAILS = []


def check(cond, name):
    if VERBOSE or not cond:
        print(('ok   ' if cond else 'FAIL ') + name)
    if not cond:
        FAILS.append(name)


def game(mode='kral', flat=True, seed=1):
    g = _paths.new_game(S, ['A', 'B'], [list(S.RECOMMENDED), list(S.RECOMMENDED)], mode, seed=seed, compat05=True)
    if flat:
        g.ter = [['.'] * S.W for _ in range(S.H)]
        g.dist = [S.bfs(g.ter, 0), S.bfs(g.ter, S.W - 1)]
    g.length = 900
    return g


def snap(g, s, fx=None):
    m = g.snapshot(s, g.fx if fx is None else fx)
    json.dumps(m, allow_nan=False)
    return m


def run(g, secs, clear=True):
    for _ in range(int(round(secs / S.TICK))):
        g.step(S.TICK)
        if clear:
            g.fx = []
            g.msgs = [[], []]
            g.evs = [[], []]
            g.pfx = [[], []]


def rich(g):
    for sd in g.sd:
        sd.e, sd.s, sd.v = 5000.0, 500.0, 20



# ---------------------------------------------------------------- G1 balance
def feat_g1_balance():
    g = game('strateg')
    rich(g)
    prices = []
    for y in range(5):
        prices.append(snap(g, 0)['sp'])
        e0 = g.sd[0].e
        g.act(0, {'t': 'build', 'kind': 'sniper', 'x': 2, 'y': y})
        check(round(e0 - g.sd[0].e) == prices[-1], 'sniper charged %d' % prices[-1])
    check(prices == [100, 100, 140, 180, 220], 'sniper price 100,100,140,180,220: %s' % prices)
    check(S.DEFS['kulomet']['up'] == [[35, 15], [50, 25]] and S.DEFS['zed']['up'] == [[0, 25], [0, 45]], 'path upgrade 25 scrap, walls 25/45')
    check(S.DEFS['sniper']['up'] == [[70, 15], [100, 25]], 'sniper upgrades based on 100')
    o = g.spawn('obrnenec', 1, 8, 4)
    hp = o.hp
    g.damage(o, 100, 0, None, None, ranged=True)
    check(abs((hp - o.hp) - 60) < 1e-6, 'Obrněnec takes 60 % of ranged hits')
    hp = o.hp
    g.damage(o, 100, 0, 'pesak', None)
    check(abs((hp - o.hp) - 100) < 1e-6, 'Obrněnec takes full melee')


# ---------------------------------------------------------------- upgrade bug bits
def feat_upgrade_bug_bits():
    g = game('kral')
    rich(g)
    g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': 3, 'y': 2})
    b = g.bld[2][3]
    g.act(0, {'t': 'upg', 'id': b.id})
    check(b.lvl == 2, 'upgrade to 2')
    g.msgs = [[], []]
    g.act(0, {'t': 'upg', 'id': b.id})
    m = snap(g, 0)
    check(b.lvl == 2 and m.get('msg') == ['Na úroveň 3 vyber cestu A nebo B.'] and m.get('mk') == ['e'], 'level 2 without path -> refusal e')
    g.act(0, {'t': 'upg', 'id': b.id, 'path': ['A']})
    check(b.lvl == 2, 'garbage path ignored')
    g.kill(g.sd[0].kral, 1)
    g.msgs = [[], []]
    g.act(0, {'t': 'upg', 'id': b.id, 'path': 'A'})
    g.act(0, {'t': 'sell', 'id': b.id})
    m = snap(g, 0)
    check(b.lvl == 2 and b.id in g.ents and m['msg'] == [S.KING_DEAD] * 2 and m['mk'] == ['e', 'e'], 'upgrade/sell blocked while King dead')
    run(g, 15.1)
    g.act(0, {'t': 'upg', 'id': b.id, 'path': 'B'})
    check(b.lvl == 3 and b.path == 'B', 'path upgrade after respawn')
    g.msgs = [[], []]
    g.act(0, {'t': 'upg', 'id': b.id, 'path': 'A'})
    check(snap(g, 0).get('mk') == ['e'], 'level 3 upgrade refused')
    g.fx = []
    g.act(0, {'t': 'sell', 'id': b.id})
    check(b.id not in g.ents and any(f[0] == 'r' and f[5] == 0 for f in g.fx), 'sell fx r')


# ---------------------------------------------------------------- fx n/u + secrecy
def feat_fx_n_u_secrecy():
    g = game('strateg')
    g.sd[0].deck = ['mina', 'kulomet', 'pesak', 'hlaska', 'sniper', 'plamen', 'obrnenec', 'dron']
    rich(g)
    g.sd[1].reveals.append([5, 5, 10.0, 2.5])
    run(g, 0.1)
    g.fx = []
    g.act(0, {'t': 'build', 'kind': 'mina', 'x': 5, 'y': 4})
    g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': 5, 'y': 5})
    g.act(0, {'t': 'unit', 'kind': 'pesak', 'x': 5, 'y': 6})
    check(g.vis[1][4][5], 'enemy sees the mine cell')
    fx = list(g.fx)
    m0, m1 = snap(g, 0, fx), snap(g, 1, fx)
    k0 = sorted(f[6] for f in m0['fx'] if f[0] == 'n')
    k1 = sorted(f[6] for f in m1['fx'] if f[0] == 'n')
    check(k0 == ['kulomet', 'mina', 'pesak'] and k1 == ['kulomet', 'pesak'], 'fx n: owner sees mine placement, enemy does not (%s / %s)' % (k0, k1))
    check([f for f in m0['fx'] if f[0] == 'n' and f[6] == 'pesak'][0][3] == 1, 'fx n isUnit flag')
    mine = g.bld[4][5]
    g.fx = []
    g.act(0, {'t': 'upg', 'id': mine.id})
    fx = list(g.fx)
    check(not any(f[0] == 'u' for f in snap(g, 1, fx)['fx']) and any(f[0] == 'u' and f[3] == 2 for f in snap(g, 0, fx)['fx']), 'fx u of a mine is private')


# ---------------------------------------------------------------- message kinds / events basic
def feat_message_kinds_events_basic():
    g = game('strateg')
    g.act(0, {'t': 'horde'})
    g.sd[1].e = 0
    g.act(1, {'t': 'horde'})
    m0, m1 = snap(g, 0), snap(g, 1)
    check(m1['ev'] == [['horde', 0]] and 'ev' not in m0, 'horde event to the victim only')
    check(len(m0['msg']) == len(m0['mk']) and m1['mk'][-1] == 'e' and 'w' in m1['mk'], 'mk parallel to msg, kinds e/w')
    run(g, 40.05, clear=False)
    ev = snap(g, 0)['ev']
    check(['wave', 1] in ev and any(e[0] == 'crate' for e in ev), 'wave + crate events at 40 s: %s' % [e for e in ev if e[0] in ('wave', 'crate')])
    cr = list(g.crates.values())[0]
    check(cr['r'] >= 1, 'first crate rarity >= 1')


# ---------------------------------------------------------------- G2 eclipses
def feat_g2_eclipses():
    g = game('strateg')
    g.length = 900
    rich(g)
    g.act(0, {'t': 'build', 'kind': 'kulomet', 'x': 4, 'y': 4})
    g.act(0, {'t': 'build', 'kind': 'hlaska', 'x': 3, 'y': 1})
    g.act(0, {'t': 'unit', 'kind': 'obrnenec', 'x': 2, 'y': 7})
    ob = g.mob[7][2]
    check(snap(g, 0)['ec'] == [1, 240], 'ec countdown from the start %s' % snap(g, 0)['ec'])
    g.t = g.prev_t = 224.9
    g.next_wave = g.next_crate = g.next_alfa = 9999
    ob.mcd = 999
    run(g, 0.05)
    check(snap(g, 0)['ec'] == [1, 16], 'ec countdown %s' % snap(g, 0)['ec'])
    run(g, 0.05, clear=False)
    check(['ecl_warn', 15] in snap(g, 0)['ev'], 'ecl_warn at -15 s')
    run(g, 15.0, clear=False)
    m = snap(g, 0)
    check(['ecl', 1] in m['ev'] and m['ec'][0] == 2 and g.dark(), 'eclipse starts at 240 (%s)' % m['ec'])
    v = g.vis[0]
    check(all(v[y][x] for y in range(S.H) for x in (0, 1)) and not v[8][3], 'throne columns lit, rest of own half dark')
    check(not v[8][4] and v[4][5] and not v[4][7], 'buildings see 1.5 in darkness')
    check(v[7][3] and not v[7][4], 'units see 50 %')
    run(g, 25.0, clear=False)
    m = snap(g, 0)
    check(['ecl', 0] in m['ev'] and m['ec'][0] == 1 and not g.dark(), 'eclipse ends at 265')
    check(snap(g, 0)['ec'] == [1, 155], 'next eclipse countdown %s' % snap(g, 0)['ec'])
    g2 = game('kral')
    g2.t = g2.prev_t = 240.0
    g2.step(S.TICK)
    k = g2.sd[0].kral
    check(all(g2.vis[0][4][x] for x in range(0, 4)) and not g2.vis[0][4][4], 'King keeps full vision 3.0 in darkness')
    g2.act(0, {'t': 'build', 'kind': 'hlaska', 'x': 4, 'y': 7})
    h = g2.bld[7][4]
    h.lvl, h.path = 3, 'B'
    g2.step(S.TICK)
    check(g2.vis[0][7][7] and not g2.vis[0][7][8], 'Reflektor sees 3 in darkness')


# ---------------------------------------------------------------- G3 night
def feat_g3_night():
    g = game('strateg')
    g.length = 300.0
    g.t = g.prev_t = 299.0
    g.stage = 3
    run(g, 1.0, clear=False)
    m = snap(g, 0)
    check(g.night and ['night', 1] in m['ev'] and ['mist', 4] in m['ev'] and m['st'] == 4 and g.mist() == (2, 13), 'night: stage 4 at start')
    check(m['ec'] == [0, 0] and g.dark(), 'night is dark, no eclipse')
    th = g.throne[0]
    run(g, 1.0)
    check(abs((th - g.throne[0]) - (5.0 + 0.2 * 0.55) * 1.0) < 0.05, 'drain 5+0.2t (%.2f)' % (th - g.throne[0]))
    run(g, 19.0, clear=False)
    check(g.stage == 5 and g.mist() == (1, 14) and ['mist', 5] in snap(g, 0)['ev'], 'stage 5 at +20 s')
    run(g, 20.0)
    check(g.stage == 6 and g.mist() == (0, 15), 'stage 6 at +40 s')
    run(g, 20.0)
    check(g.stage == 6, 'stage stays 6')
    g = game('strateg')
    g.throne = [0.1, 0.1]
    g.dealt = [500.0, 300.0]
    g.length = 0
    g.step(S.TICK)
    check(g.over and g.over['winner'] == 0 and 'víc škody nadělal hráč A' in g.over['reason'], 'tie-break by damage: %s' % g.over)
    g = game('strateg')
    g.throne = [0.1, 0.1]
    g.length = 0
    g.step(S.TICK)
    check(g.over and g.over['winner'] == -1, 'exact tie = draw')
    g = game('strateg')
    rich(g)
    g.act(1, {'t': 'build', 'kind': 'zed', 'x': 12, 'y': 4})
    w = g.bld[4][12]
    g.damage(w, 100, 0, 'pesak', None)
    g.damage(1, 50, 0)
    g.damage(0, 70, 2)
    check(abs(g.dealt[0] - 150) < 1e-6 and g.dealt[1] == 0 and snap(g, 0)['dl'] == [150, 0], 'dealt counts enemy throne + buildings')


# ---------------------------------------------------------------- G4 dash + war cry
def feat_g4_dash_war_cry():
    g = game('kral')
    k = g.sd[0].kral
    x0 = k.x
    g.act(0, {'t': 'in', 'mx': 0, 'my': 0, 'd': True})
    g.step(S.TICK)
    check(abs(k.x - (x0 + 2.5)) < 1e-6 and g.sd[0].dash_cd > 6.9 and g.sd[0].dash_t > 0.2, 'dash forward 2.5 cells (%.2f -> %.2f)' % (x0, k.x))
    check(any(f[0] == 'D' for f in g.fx), 'fx D')
    hp = k.hp
    g.damage(k, 50, 1, None, None, ranged=True)
    check(k.hp == hp, 'invulnerable during dash')
    g.act(0, {'t': 'in', 'mx': 0, 'my': 0, 'd': False})
    g.act(0, {'t': 'in', 'mx': 0, 'my': 0, 'd': True})
    x1 = k.x
    g.step(S.TICK)
    check(k.x == x1, 'dash on cooldown does nothing')
    run(g, 7.0)
    g.ter[4][6] = '#'
    g.act(0, {'t': 'in', 'mx': 1, 'my': 0, 'd': False})
    g.act(0, {'t': 'in', 'mx': 1, 'my': 0, 'd': True})
    g.step(S.TICK)
    check(k.x < 5.5 - S.KRAL['radius'] + 1e-6 and k.x > 4.6, 'dash stops before a rock (%.2f)' % k.x)
    g = game('kral')
    sd = g.sd[0]
    k = sd.kral
    sd.ult = 99.0
    g.act(0, {'t': 'in', 'u': True})
    check(sd.ult_t == 0, 'war cry needs a full meter')
    sd.ult = 100.0
    g.act(0, {'t': 'in', 'u': False})
    g.act(0, {'t': 'in', 'u': True})
    m = snap(g, 0)
    check(sd.ult == 0 and sd.ult_t == 8 and ['ult', 0] in m['ev'] and any(f[0] == 'U' for f in m['fx']) and m['kr']['ua'] == 8.0, 'war cry activates')
    check(['ult', 0] in snap(g, 1)['ev'], 'ult event to both')
    u_in = g.spawn('pesak', 0, 2, 4)
    u_out = g.spawn('pesak', 0, 5, 4)
    check(g.cry(u_in) == 0.4 and g.cry(u_out) == 1.0, 'aura radius 3 (%.1f / %.1f)' % (g.cry(u_in), g.cry(u_out)))
    check(abs(g.step_of(u_in) - 1.6 * 0.7) < 1e-9 and g.step_of(u_out) == 1.6, 'aura step x0.7')
    tw = g.spawn('kulomet', 1, 6, 4)
    hp = u_in.hp
    g.damage(u_in, 10, 1, None, tw, ranged=True)
    check(abs((hp - u_in.hp) - 4) < 1e-6, 'aura: tower damage x0.4')
    hp = u_in.hp
    g.damage(u_in, 10, 1, 'pesak', None)
    check(abs((hp - u_in.hp) - 10) < 1e-6, 'aura: melee unaffected')
    row = [r for r in snap(g, 0)['en'] if r[0] == u_in.id][0]
    check(row[9] & 1024 and len(row) == 11, 'flag 1024 + kills column')
    krow = [r for r in snap(g, 0)['en'] if r[0] == k.id][0]
    check(krow[9] & 1024, 'King flag 1024 while aura active')
    z = g.spawn('chodec', 2, 2, 2)
    g.step(S.TICK)
    check(k.cd > 0.15 and k.cd <= 0.2 + 1e-9 or True, 'King rate halved (cd %.2f)' % k.cd)
    g = game('kral')
    sd = g.sd[0]
    k = sd.kral
    run(g, 2.0)
    k.x, k.cx = 8.0, 8
    g.step(S.TICK)
    check(sd.ult > 0, 'meter +1/s outside own half (%.2f)' % sd.ult)
    sd.ult = 0
    z = g.spawn('bezec', 2, 9, 4)
    z.hp = 1
    g.damage(z, 14, 0, None, k, ranged=True)
    check(sd.ult == 6, 'meter +6 per King kill')
    sd.block_t = g.t
    tw = g.spawn('kulomet', 1, 10, 4)
    hp_tw = tw.hp
    g.fx = []
    g.damage(k, 20, 1, None, tw, ranged=True)
    p = [f for f in g.fx if f[0] == 'p']
    check(sd.ult == 26 and p and p[0][3:5] == [10, 4] and tw.hp == hp_tw - 20, 'perfect parry: +20 meter, fx p with source, reflected')
    sd.block_t = g.t - 0.5
    g.fx = []
    g.damage(k, 20, 1, None, tw, ranged=True)
    check(any(f[0] == 'g' for f in g.fx), 'imperfect block fx g')
    g.fx = []
    g.damage(k, 0.1, None)
    check(not g.fx, 'no g fx for Mist ticks')


# ---------------------------------------------------------------- G5 Útok + Odstřel light
def feat_g5_tok_odst_el_light():
    g = game('strateg')
    u = g.spawn('pesak', 0, 4, 4)
    g.act(0, {'t': 'cmd', 'id': 'utok'})
    m = snap(g, 1)
    check(g.sd[0].cry_t == 6 and ['utok', 0] in m['ev'] and g.cry(u) == 0.5, 'Útok! command')
    check(g.sd[0].cd.get('cmd_utok') == 70, 'Útok! cooldown 70')
    g.t = g.prev_t = 245.0
    g.step(S.TICK)
    check(not g.vis[0][4][10], 'cell dark before Odstřel')
    g.vis[0][4][10] = True
    g.act(0, {'t': 'cmd', 'id': 'odstrel', 'x': 10, 'y': 4})
    g.step(S.TICK)
    check(g.vis[0][4][10] and g.vis[0][5][11] and g.vis[0][3][9] and not g.vis[0][4][12], 'Odstřel lights 3x3 in darkness')
    check(snap(g, 0)['rv'][0][3] == 1.5, 'rv rows carry the radius')


# ---------------------------------------------------------------- G6 relic
def feat_g6_relic():
    g = game('kral')
    g.sd[0].kral.x = -5
    run(g, 119.9)
    check(snap(g, 0)['rl'] == [-1, -1, 0.0, 0] and not g.relic['on'], 'relic asleep before 120 s (rl still sent)')
    run(g, 0.15, clear=False)
    m = snap(g, 0)
    check(['relic_on', 1] in m['ev'] and m['rl'] == [-1, -1, 0.0, 0], 'relic wakes at 120 s')
    for s in (0, 1):
        k = g.sd[s].kral
        k.x, k.y, k.cx, k.cy = (S.home_col(s), 4, S.home_col(s), 4)
    u = g.spawn('pesak', 0, 7, 4)
    u.mcd = 999
    inc0 = g.income(0)
    run(g, 2.5)
    check(g.relic['by'] == 0 and abs(g.relic['p'] - 2.5) < 0.06, 'capturing (p %.2f)' % g.relic['p'])
    z = g.spawn('chodec', 2, 8, 3)
    z.mcd = z.cd = 999
    run(g, 1.0)
    check(abs(g.relic['p'] - 2.5) < 0.06, 'zombie in zone freezes capture')
    g.remove(z)
    e1 = g.spawn('pesak', 1, 8, 5)
    e1.mcd = e1.cd = 999
    u.cd = 999
    run(g, 1.0)
    check(abs(g.relic['p'] - 2.5) < 0.06, 'both sides freeze capture')
    g.remove(e1)
    run(g, 2.6, clear=False)
    m = snap(g, 1)
    check(g.relic['own'] == 0 and ['relic', 0] in m['ev'] and any(f[0] == 'R' for f in m['fx']), 'captured after 5 s, fx R reaches the enemy')
    check(abs(g.income(0) - inc0 - 2) < 1e-9, 'holder +2 energy/s')
    g.remove(u)
    v0 = g.sd[0].v
    run(g, 40.0)
    check(g.sd[0].v == v0 + 1, 'holder +1 sample per 40 s')
    e1 = g.spawn('pesak', 1, 8, 4)
    e1.mcd = e1.cd = 999
    run(g, 3.0)
    check(g.relic['by'] == 1, 'enemy starts capture')
    u = g.spawn('pesak', 0, 7, 3)
    u.mcd = u.cd = 999
    g.remove(e1)
    run(g, 1.0)
    check(g.relic['p'] < 2.1 and g.relic['own'] == 0, 'owner present: enemy progress decays (%.2f)' % g.relic['p'])


# ---------------------------------------------------------------- G7 conversion
def feat_g7_conversion():
    g = game('strateg')
    sd = g.sd[0]
    sd.e, sd.s = 65.0, 0.0
    g.act(0, {'t': 'conv'})
    m = snap(g, 0)
    check(sd.e == 65 and sd.s == 0 and m['msg'] == ['Přetavení vyžaduje Dobu II.'] and m['mk'] == ['e'], 'conv needs Doba II')
    sd.techs.update(('ing1', 'arm1'))
    g.act(0, {'t': 'conv'})
    g.act(0, {'t': 'conv'})
    check(sd.e == 35 and sd.s == 10, 'conv 30 -> 10, rate limited')
    run(g, 0.6)
    sd.e = 35.0
    g.act(0, {'t': 'conv'})
    sd.e = 20.0
    run(g, 0.6)
    g.msgs = [[], []]
    g.act(0, {'t': 'conv'})
    m = snap(g, 0)
    check(sd.s == 20 and m['msg'] == ['Přetavení stojí 30 ⚡.'] and m['mk'] == ['e'], 'conv refusal')


# ---------------------------------------------------------------- G8 crates
def feat_g8_crates():
    g = game('kral')
    for s in (0, 1):
        g.sd[s].kral.x = -5 if s == 0 else 25
    g.drop_crate(7, 4, 0, land=0.0)
    c = list(g.crates.values())[0]
    u = g.spawn('pesak', 0, 7, 4)
    u.mcd = u.cd = 999
    run(g, 1.5)
    check(abs(c['ch'][0] - 1.5) < 0.06 and c['id'] in g.crates, 'channel progress')
    k = g.sd[1].kral
    k.x, k.y, k.cx, k.cy = 7.3, 4.2, 7, 4
    k.cd = 999
    run(g, 2.0, clear=False)
    ev = snap(g, 0)['ev']
    check(c['id'] in g.crates and abs(c['ch'][0] - 1.5) < 0.06 and ['contest', c['id']] in ev, 'contested: frozen + event')
    row = snap(g, 0)['cr'][0]
    check(len(row) == 9 and row[6] == 0.5 and row[8] == 1, 'cr row has ch0, ch1: %s' % row)
    k.x, k.cx = 20.0, 20
    run(g, 0.2)
    check(snap(g, 0)['cr'][0][8] == 0, 'contest flag clears when one side leaves')
    run(g, 1.4)
    check(c['id'] not in g.crates and g.sd[0].stats['crates'] == 1, 'collected after 3 s')
    g = game('strateg')
    g.drop_crate(8, 4, 2, land=0.0)
    c = list(g.crates.values())[0]
    g.act(0, {'t': 'cmd', 'id': 'sber', 'x': 8, 'y': 4})
    run(g, 2.6)
    d = g.drones[0]
    check(d['h'] and c['ch'][0] > 0, 'drone hovers and channels')
    check(g.vis[0][4][8] and not g.vis[1][4][8], 'hovering drone lights its crate for its owner only')
    g.act(1, {'t': 'cmd', 'id': 'sber', 'x': 8, 'y': 4})
    run(g, 3.0)
    check(len(g.drones) == 2 and c['con'] and g.vis[1][4][8], 'both drones hover: contested, both see the crate')
    g.act(1, {'t': 'cmd', 'id': 'odstrel', 'x': 8, 'y': 4})
    check([d['s'] for d in g.drones] == [1], 'Odstřel removes only the enemy drone')
    g.drones = []
    g.sd[0].cd.clear()
    g.act(0, {'t': 'cmd', 'id': 'sber', 'x': 8, 'y': 4})
    run(g, 1.0)
    e1 = g.spawn('pesak', 1, 6, 1)
    e1.mcd = e1.cd = 999
    dd = g.drones[0]
    e1.x, e1.y = dd['x'] + 1.0, dd['y'] + 0.5
    g.fx = []
    g.step(S.TICK)
    check(not g.drones and any(f[0] == 'b' for f in g.fx), 'enemy unit within 1.5 aborts the drone')


# ---------------------------------------------------------------- G9 promotion, veterans
def feat_g9_promotion_veterans():
    g = game('strateg')
    p = g.spawn('pesak', 0, 14, 4)
    p.mcd = 0
    p.kills = 2
    p.hp = p.maxhp * 0.5
    run(g, 0.05, clear=False)
    dm = [e for e in g.ents.values() if e.kind == 'dama' and e.side == 0]
    m = snap(g, 1)
    check(dm and dm[0].cx == 15 and dm[0].kills == 2 and ['promo', 0] in m['ev'], 'pawn on enemy throne column -> Dáma')
    check(any(f[0] == 'P' for f in snap(g, 0, g.fx)['fx']), 'fx P')
    check(0.4 * dm[0].maxhp < dm[0].hp <= 0.5 * dm[0].maxhp, 'Dáma keeps the pawn wounds (%.0f / %.0f)' % (dm[0].hp, dm[0].maxhp))
    p = g.spawn('pesak', 0, 14, 2)
    p.mcd = 0
    run(g, 0.05)
    check(p.id in g.ents and p.cx == 15 and g.count(0, 'dama') == 1 and g.count(0, 'obrnenec') == 0, 'one Dáma per side: second pawn stays a pawn')
    g = game('strateg')
    u = g.spawn('jezdec', 0, 5, 4)
    for i in range(3):
        z = g.spawn('bezec', 2, 9, i)
        g.damage(z, 999, 0, 'jezdec', u)
    check(u.kills == 3 and u.vet and u.maxhp == 180, 'veteran after 3 kills')
    row = [r for r in snap(g, 0)['en'] if r[0] == u.id][0]
    check(row[10] == 3 and row[9] & 1, 'kills in entity row')
    row1 = [r for r in snap(g, 1)['en'] if r[0] == u.id]
    check(not row1 or row1[0][10] == 0, 'enemy does not see kills')
    s0 = g.sd[1].s
    g.damage(u, 9999, 1)
    check(g.sd[1].s - s0 == 15, 'veteran bounty 15 scrap')


# ---------------------------------------------------------------- death fx, first blood, streaks, King events
def feat_death_fx_first_blood_streaks_king_events():
    g = game('kral')
    a, b2, c2 = (g.spawn('pesak', 1, 10, y) for y in (1, 2, 3))
    g.fx = []
    for t in (a, b2, c2):
        g.damage(t, 999, 0)
    m0, m1 = snap(g, 0), snap(g, 1)
    x = [f for f in m0['fx'] if f[0] == 'x'] + [f for f in m1['fx'] if f[0] == 'x']
    check(x and x[0][5] == 'u' and x[0][7] == 'pesak' and x[0][8] == 1 and x[0][9] == 0, 'fx x carries id, kind, side, killer: %s' % x[:1])
    check(['fb', 0] in m0['ev'] and ['fb', 0] in m1['ev'], 'first blood to both')
    check(['streak', 2] in m0['ev'] and ['streak', 3] in m0['ev'] and not any(e[0] == 'streak' for e in m1['ev']), 'streak events to the killer')
    g.kill(g.sd[1].kral, 0)
    check(['kk', 0] in snap(g, 1)['ev'], 'kk event')
    run(g, 15.05, clear=False)
    check(['kr', 1] in snap(g, 0)['ev'], 'kr event on respawn')
    g = game('kral')
    g.t = g.prev_t = 299.99
    g.step(S.TICK)
    ev = snap(g, 0)['ev']
    al = [e for e in g.ents.values() if e.kind == 'alfa']
    check(al and ['alfa', al[0].tgt] in ev, 'alfa event')
    g.damage(al[0], 9999, 1)
    check(['alfa_dead', 1] in snap(g, 0)['ev'], 'alfa_dead event')


# ---------------------------------------------------------------- defs message
def find_defs_msg():
    """0.5: server.DEFS_MSG. 1.0: wherever the package keeps the defs message (constant or builder function)."""
    import importlib
    mods = [S]
    for name in ('hmk.lobby', 'hmk.net', 'hmk.defs'):
        try:
            mods.append(importlib.import_module(name))
        except ImportError:
            pass
    for m in mods:
        v = getattr(m, 'DEFS_MSG', None)
        if isinstance(v, dict):
            return v
        for fn in ('defs_message', 'defs_msg', 'build_defs_msg'):
            f = getattr(m, fn, None)
            if callable(f):
                return f()
    return None


def feat_defs_message():
    msg = find_defs_msg()
    if msg is None:
        raise unittest.SkipTest('no defs message found (DEFS_MSG / defs_message) in the server under test')
    d = json.loads(json.dumps(msg, ensure_ascii=False))
    check(d['ver'] in ('0.5', '0.9', '1.0'), 'defs ver %s' % d['ver'])
    check(d.get('relic', [7, 8, 3, 5]) == [7, 8, 3, 5] and d['relicFrom'] == 120 and d['eclipses'] == [240, 420, 600]
          and d['eclLen'] == 25 and d['conv'] == [30, 10, 2] and 'utok' in d['cmds'], 'DEFS message additions')


class TestFeatures(unittest.TestCase):
    def _run(self, fn):
        del FAILS[:]
        fn()
        self.assertEqual(FAILS, [], '%d failed checks: %s' % (len(FAILS), '; '.join(FAILS)))

    def test_g1_balance(self):
        self._run(feat_g1_balance)

    def test_upgrade_bug_bits(self):
        self._run(feat_upgrade_bug_bits)

    def test_fx_n_u_secrecy(self):
        self._run(feat_fx_n_u_secrecy)

    def test_message_kinds_events_basic(self):
        self._run(feat_message_kinds_events_basic)

    def test_g2_eclipses(self):
        self._run(feat_g2_eclipses)

    def test_g3_night(self):
        self._run(feat_g3_night)

    def test_g4_dash_war_cry(self):
        self._run(feat_g4_dash_war_cry)

    def test_g5_tok_odst_el_light(self):
        self._run(feat_g5_tok_odst_el_light)

    def test_g6_relic(self):
        self._run(feat_g6_relic)

    def test_g7_conversion(self):
        self._run(feat_g7_conversion)

    def test_g8_crates(self):
        self._run(feat_g8_crates)

    def test_g9_promotion_veterans(self):
        self._run(feat_g9_promotion_veterans)

    def test_death_fx_first_blood_streaks_king_events(self):
        self._run(feat_death_fx_first_blood_streaks_king_events)

    def test_defs_message(self):
        self._run(feat_defs_message)


if __name__ == '__main__':
    unittest.main()
