#!/usr/bin/env python3
"""
Two-state vs four-state state comparison.

A tempting shortcut for per-cycle lockstep is to reduce each state bit to
two states -- e.g. accumulate a signature over (bit === 1) -- and compare the
reduced vectors.  That maps x (and z) onto 0.  This script measures, on the
real divergence data, what such a comparison misses.

It compares the reduced *vectors exactly*, so any miss is caused by the
x->0 mapping itself, not by hash collisions.

usage: fold_pitfall.py <rtl.trace.state> <gls.trace.state> <label>
"""
import json, sys

order  = json.load(open('work/probe_order.json'))

def load_rtl(p):
    out = {}
    for line in open(p):
        t = line.split()
        if not t: continue
        vals = {}
        for kv in t[1:]:
            k, v = kv.split('=', 1); vals[k] = v[::-1]      # index = bit
        out[int(t[0])] = vals
    return out

def load_gls(p):
    return {int(l.split()[0]): l.split()[1] for l in open(p) if len(l.split()) == 2}

R, G = load_rtl(sys.argv[1]), load_gls(sys.argv[2])
label = sys.argv[3] if len(sys.argv) > 3 else 'arm'
two = lambda b: '1' if b == '1' else '0'

cycles = sorted(set(R) & set(G))
div4 = miss_cycles = bits4 = bits_x0 = 0
first4 = first2 = None
for cyc in cycles:
    gs = G[cyc]
    if len(gs) != len(order): continue
    d4 = d2 = False
    for i, (name, bit) in enumerate(order):
        w = R[cyc].get(name)
        if w is None or bit >= len(w): continue
        r, g = w[bit], gs[i]
        if r != g:
            d4 = True; bits4 += 1
            if two(r) == two(g): bits_x0 += 1
            if first4 is None: first4 = (cyc, '%s[%d]' % (name, bit), r, g)
        if two(r) != two(g):
            d2 = True
            if first2 is None: first2 = (cyc, '%s[%d]' % (name, bit), r, g)
    if d4:
        div4 += 1
        if not d2: miss_cycles += 1

print('=' * 64)
print('TWO-STATE vs FOUR-STATE COMPARISON : %s' % label)
print('=' * 64)
print('cycles compared                     : %d' % len(cycles))
print('cycles divergent (four-state)       : %d' % div4)
print('  of which two-state sees NOTHING   : %d' % miss_cycles)
print('divergent bit-cycles (four-state)   : %d' % bits4)
pct = (100.0 * bits_x0 / bits4) if bits4 else 0.0
print('  invisible to two-state (x vs 0)   : %d  (%.1f%%)' % (bits_x0, pct))
f = lambda t: 'none' if t is None else 'cycle %d  %s  RTL=%s GATE=%s' % t
print('first divergence, four-state        : %s' % f(first4))
print('first divergence, two-state         : %s' % f(first2))
