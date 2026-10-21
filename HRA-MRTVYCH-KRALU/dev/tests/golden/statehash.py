"""Reference state hash. It is THE definition (SPEC section 3.2): Game.state_hash() on the 1.0 server must return
exactly state_hash(g) for the same game. It reads plain attributes, so it works on the frozen 0.5 server as well.

  sha1( json.dumps([ round(g.t, 6),
                     [[sd.e, sd.s, sd.v] for sd in g.sd],
                     list(g.throne),
                     sorted([e.id, e.kind, e.side, round(e.x, 6), round(e.y, 6), round(e.hp, 6), e.lvl, e.path]
                            for e in g.ents.values()) ]) )

Energy, scrap and throne HP are NOT rounded (bit-identical floats are required); only t, x, y and hp are rounded.
json.dumps with its default separators (', ' and ': '), ensure_ascii default, utf-8 encoded, hexdigest returned.
"""
import hashlib
import json


def state_data(g):
    return [round(g.t, 6),
            [[sd.e, sd.s, sd.v] for sd in g.sd],
            list(g.throne),
            sorted([e.id, e.kind, e.side, round(e.x, 6), round(e.y, 6), round(e.hp, 6), e.lvl, e.path]
                   for e in g.ents.values())]


def state_hash(g):
    return hashlib.sha1(json.dumps(state_data(g)).encode('utf-8')).hexdigest()
