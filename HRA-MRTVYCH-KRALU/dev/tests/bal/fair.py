"""Side fairness from an out_<tag>.json: wins and zombie loot per side for the mirrored scenarios.
usage: python fair.py <file.json> [scen,scen]"""
import json
import statistics as st
import sys

res = json.load(open(sys.argv[1], encoding='utf-8'))
scens = sys.argv[2].split(',') if len(sys.argv) > 2 else sorted({r.get('scen') for r in res})
print('%-34s %-10s %-8s %4s %4s %4s %4s %8s %8s %6s %8s %8s' % ('variant', 'scen', 'mode', 'n', 'W0', 'W1', 'D', 'zloot0', 'zloot1', 'B/A', 'kills0', 'kills1'))
for v in sorted({r['variant'] for r in res}):
    for sc in scens:
        for mode in ('kral', 'strateg', 'ALL'):
            rows = [r for r in res if r['variant'] == v and r['scen'] == sc and (mode == 'ALL' or r['mode'] == mode)]
            if not rows:
                continue
            z = [st.mean(r['scrap_src'][s].get('zombie', 0) for r in rows) for s in (0, 1)]
            k = [st.mean(r['kills'][s]) if 'kills' in r else 0 for s in (0, 1) for r in rows[:0]] or [
                st.mean(r['kills'][s] for r in rows) if 'kills' in rows[0] else 0 for s in (0, 1)]
            print('%-34s %-10s %-8s %4d %4d %4d %4d %8.1f %8.1f %6.2f %8.1f %8.1f' % (
                v[:34], sc, mode, len(rows), sum(r['winner'] == 0 for r in rows), sum(r['winner'] == 1 for r in rows),
                sum(r['winner'] == -1 for r in rows), z[0], z[1], z[1] / z[0] if z[0] else 0, k[0], k[1]))
