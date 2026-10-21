"""Fog lint (SPEC 3.4, MAI 5.1): only hmk/ai/view.py may touch the game's hidden state.

No other file in hmk/ai/ may contain `g.ents`, `.ents.`, `.aim`, `.length`, `sd[1 - ` or read a deck attribute
(`.deck` is allowed only as the View accessor `.deck()`, which returns the AI's own deck). Comments and docstrings
count too, so the rule stays a plain grep."""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
AI = os.path.normpath(os.path.join(HERE, '..', '..', 'hmk', 'ai'))
BANNED = [re.compile(re.escape(p)) for p in ('g.ents', '.ents.', '.aim', '.length', 'sd[1 - ')]
DECK = re.compile(r'\.deck\b(?!\(\))')


class TestAIFog(unittest.TestCase):
    def test_lint(self):
        files = sorted(f for f in os.listdir(AI) if f.endswith('.py'))
        self.assertIn('view.py', files)
        bad = []
        for f in files:
            if f == 'view.py':
                continue
            with open(os.path.join(AI, f), encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    for rx in BANNED + [DECK]:
                        if rx.search(line):
                            bad.append('%s:%d: %s' % (f, n, line.strip()))
        self.assertEqual(bad, [], 'fog lint:\n' + '\n'.join(bad))

    def test_lint_catches(self):
        for s in ('for e in g.ents.values():', 'x = self.g.sd[1 - s].deck', 'g.length', 'e.aim'):
            self.assertTrue(any(rx.search(s) for rx in BANNED + [DECK]), s)
        self.assertFalse(any(rx.search('k in self.v.deck()') for rx in BANNED + [DECK]))


if __name__ == '__main__':
    unittest.main()
