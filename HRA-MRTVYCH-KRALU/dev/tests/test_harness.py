"""Smoke and self tests of the balance harness (bal/harness.py): a short bot match runs and is reproducible,
variants patch and reset_rules() restores everything (constants, DEFS, Game methods and mixin methods)."""
import copy
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'bal'))
import harness as H  # noqa: E402
import run as R  # noqa: E402
import variants  # noqa: E402

S, D = H.S, H.D


def scen(secs=60):
    return {'p0': R.MIXED, 'p1': R.ATT, 'length': 720, 't_end': secs}


def play(mode='kral', seed=1, secs=60, variant='base'):
    return H.run_game({'variant': variant, 'scen': scen(secs), 'scen_name': 'smoke', 'mode': mode, 'seed': seed,
                       'compat05': True})


class TestHarness(unittest.TestCase):
    def tearDown(self):
        H.reset_rules()
        H.TICK_HOOKS[:] = []

    def test_short_match_runs_in_both_modes(self):
        for mode in ('kral', 'strateg'):
            r = play(mode)
            self.assertEqual(r['mode'], mode)
            self.assertGreaterEqual(r['t'], 59)
            self.assertIn('throne', r)

    def test_same_seed_same_result(self):
        a, b = play('kral', 3), play('kral', 3)
        self.assertEqual(a, b)
        self.assertNotEqual(a, play('kral', 4))

    def test_tick_hook_runs_and_can_be_removed(self):
        seen = []
        H.TICK_HOOKS[:] = [lambda g, n: seen.append(n)]
        play('kral', 1, 5)
        self.assertEqual(seen[:3], [1, 2, 3])
        self.assertGreaterEqual(len(seen), 99)

    def test_setc_sets_the_tunable_everywhere(self):
        old = D.CRATE_CH
        H.setc('CRATE_CH', 0.5)
        self.assertEqual(D.CRATE_CH, 0.5)
        if S is not D and hasattr(S, 'CRATE_CH'):
            self.assertEqual(S.CRATE_CH, 0.5)
        H.reset_rules()
        self.assertEqual(D.CRATE_CH, old)

    def test_reset_rules_restores_constants_defs_and_methods(self):
        defs0 = copy.deepcopy(S.DEFS)
        conv0 = D.CONV
        game_cls_methods = {k: v for k, v in S.Game.__dict__.items() if callable(v)}
        for v in ('fcv40', 'xcry', 'fpromo', 'xchan', 'sn_dmg30', 'u_hp20'):
            variants.apply(v)
        self.assertNotEqual(S.DEFS['sniper']['dmg'], defs0['sniper']['dmg'])
        self.assertNotEqual(D.CONV, conv0)
        # patch one method of every mixin base as well (1.0 splits Game into mixins; 0.5 has none)
        patched = []
        for cls in S.Game.__mro__[1:]:
            if cls is object:
                continue
            for k, v in list(cls.__dict__.items()):
                if callable(v) and not k.startswith('__'):
                    patched.append((cls, k, v))
                    setattr(cls, k, lambda *a, **kw: None)
                    break
        S.Game.brand_new_method = lambda self: 1
        H.reset_rules()
        self.assertEqual(S.DEFS, defs0)
        self.assertEqual(D.CONV, conv0)
        self.assertFalse(hasattr(S.Game, 'brand_new_method'))
        for k, v in game_cls_methods.items():
            self.assertIs(S.Game.__dict__.get(k), v, 'Game.%s not restored' % k)
        for cls, k, v in patched:
            self.assertIs(cls.__dict__[k], v, '%s.%s not restored' % (cls.__name__, k))

    def test_variant_is_applied_and_next_game_is_clean(self):
        base = play('kral', 2, 100)
        var = play('kral', 2, 100, variant='xchan')      # crates open at once: a different game
        self.assertEqual(var['variant'], 'xchan')
        same = all(base[k] == var[k] for k in base if k != 'variant')
        self.assertFalse(same, 'variant xchan changed nothing')
        self.assertTrue(base == play('kral', 2, 100), 'reset_rules did not undo the variant')


if __name__ == '__main__':
    unittest.main()
