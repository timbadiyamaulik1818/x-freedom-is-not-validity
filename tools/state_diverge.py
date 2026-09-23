#!/usr/bin/env python3
"""
State-level divergence localisation.

Compares RTL and gate-level state cycle-by-cycle through the correspondence
map and reports the FIRST state element to diverge -- the root cause -- as
distinct from the architectural symptom seen later on the PC.

usage: state_diverge.py <rtl.trace.state> <gls.trace.state> [label]
"""
import json, sys, collections

order = json.load(open('work/probe_order.json'))
widths = json.load(open('work/probe_widths.json'))
label = sys.argv[3] if len(sys.argv) > 3 else 'GLS'

def load_rtl(p):
    out = {}
    for line in open(p):
        t = line.split()
        if not t: continue
        cyc = int(t[0]); vals = {}
        for kv in t[1:]:
            k, v = kv.split('=', 1)
            vals[k] = v[::-1]          # index 0 = bit 0
        out[cyc] = vals
    return out

def load_gls(p):
    out = {}
    for line in open(p):
        t = line.split()
        if len(t) != 2: continue
        # _st MSB is order[0]; reverse so index i == order[i]
        out[int(t[0])] = t[1]
    return out

R, G = load_rtl(sys.argv[1]), load_gls(sys.argv[2])
common = sorted(set(R) & set(G))

first = None
per_elem = collections.Counter()
per_cycle = collections.Counter()
xonly = collections.Counter()

for cyc in common:
    gs = G[cyc]
    if len(gs) != len(order): continue
    rv = R[cyc]
    for i, (name, bit) in enumerate(order):
        gbit = gs[i]
        w = rv.get(name)
        if w is None or bit >= len(w): continue
        rbit = w[bit]
        if rbit == gbit: continue
        per_elem[name] += 1
        per_cycle[cyc] += 1
        if gbit in 'xzXZ' and rbit in '01':
            xonly[name] += 1
        if first is None:
            first = (cyc, name, bit, rbit, gbit)

print('=' * 68)
print('STATE-LEVEL DIVERGENCE LOCALISATION : %s' % label)
print('=' * 68)
print('cycles compared      : %d' % len(common))
if first is None:
    print('RESULT               : STATE MATCH - all %d flops identical every cycle'
          % len(order))
    sys.exit(0)

cyc, name, bit, rbit, gbit = first
print('RESULT               : STATE DIVERGENT')
print('diverging state bits : %d distinct storage words' % len(per_elem))
print()
print('--- ROOT CAUSE : first state element to differ -------------------')
print('  cycle            : %d' % cyc)
print('  state element    : %s[%d]' % (name, bit))
print('  RTL value        : %s' % rbit)
print('  gate value       : %s' % gbit)
if gbit in 'xzXZ' and rbit in '01':
    cls = 'X-ORIGIN (gate unknown, RTL determinate)'
elif rbit in 'xzXZ' and gbit in '01':
    cls = 'RTL-UNKNOWN (RTL unknown, gate determinate)'
else:
    cls = 'VALUE MISMATCH (both determinate)'
print('  classification   : %s' % cls)
print()
print('--- first cycle at which each storage word diverges --------------')
firstcyc = {}
for c in common:
    gs = G[c]
    if len(gs) != len(order): continue
    for i, (n, b) in enumerate(order):
        w = R[c].get(n)
        if w is None or b >= len(w): continue
        if w[b] != gs[i] and n not in firstcyc:
            firstcyc[n] = c
for n, c in sorted(firstcyc.items(), key=lambda x: (x[1], x[0]))[:14]:
    print('  cycle %-4d %-12s  (%d bit-cycles divergent, %d X-origin)'
          % (c, n, per_elem[n], xonly[n]))
