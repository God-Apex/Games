"""Actuator: delayed, APM-limited message queue (MAI 5.1). Every message reaches the game through g.act(side, msg)."""


class Actuator:
    def __init__(self, g, side, P, rnd, view):
        self.g, self.side, self.P, self.rnd, self.view = g, side, P, rnd, view
        self.q = []                   # [due, seq, msg, cost, key, check]
        self.seq = 0
        self.gap = 60.0 / P['apm']
        self.next_ok = 0.0
        self.refused = {}             # key -> game time until which it is not retried
        self.fails = {}               # key -> refusals in a row
        self.checks = []              # [t_check, key, check]
        self.reserved = 0.0           # energy promised to queued messages
        self.sent_n = 0

    def delay(self):
        m, sd = self.P['react']
        return max(0.12, self.rnd.gauss(m, sd))

    def busy(self, key):
        if key is None:
            return False
        if self.refused.get(key, -1.0) > self.g.t:
            return True
        return any(it[4] == key for it in self.q)

    def bad(self, key):
        """Refused 3 times in a row: the AI gives up on this exact action."""
        return self.fails.get(key, 0) >= 3

    def push(self, msg, cost=0.0, key=None, check=None, delay=None):
        if key is not None and self.busy(key):
            return False
        self.seq += 1
        due = self.g.t + (self.delay() if delay is None else delay)
        self.q.append([due, self.seq, msg, cost, key, check])
        self.reserved += cost
        return True

    def pending(self):
        return len(self.q)

    def queued(self, t, kind):
        """Queued (not yet sent) messages of type t for this kind, e.g. builds of 'gen' still on their way."""
        return sum(1 for it in self.q if it[2].get('t') == t and it[2].get('kind') == kind)

    def flush(self):
        g = self.g
        t = g.t
        if self.checks:
            keep = []
            for c in self.checks:
                if c[0] > t:
                    keep.append(c)
                elif not c[2]():
                    self.refused[c[1]] = t + 3.0
                    self.fails[c[1]] = self.fails.get(c[1], 0) + 1
                else:
                    self.fails.pop(c[1], None)
            self.checks = keep
        if not self.q or t < self.next_ok:
            return
        best = None
        for it in self.q:
            if it[0] <= t and (best is None or (it[0], it[1]) < (best[0], best[1])):
                best = it
        if best is None:
            return
        self.q.remove(best)
        self.reserved = max(0.0, self.reserved - best[3])
        self.next_ok = t + self.gap
        self.sent_n += 1
        g.act(self.side, best[2])
        if best[5] is not None and best[4] is not None:
            self.checks.append([t + 0.25, best[4], best[5]])

    def now(self, msg):
        """Immediate message (King input: exempt from delay and APM)."""
        self.g.act(self.side, msg)
