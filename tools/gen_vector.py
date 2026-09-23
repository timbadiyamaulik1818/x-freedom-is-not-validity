#!/usr/bin/env python3
"""
Generate ONE power-up state vector and emit two consistent deposit files:
  work/deposit_rtl.vh  - hierarchical deposits into the RTL model
  work/deposit_gls.vh  - hierarchical deposits into the gate netlist flops
Both are derived from the same vector via work/state_map.json, so the two
models start from a bit-identical power-up state.

usage: gen_vector.py <mode> [seed]      mode = zeros | ones | random
"""
import json, sys, random, collections, re, hashlib

mode = sys.argv[1] if len(sys.argv) > 1 else 'random'
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
rnd = random.Random(seed)

# Optional architectural constraints on the power-up vector, e.g. state that
# boot firmware or the reset sequence is guaranteed to establish.  Remaining
# state is free, so a family of legal power-up vectors can be swept.
constraints = {}
for a in sys.argv[3:]:
    k, v = a.split('=')
    constraints[k] = int(v, 0)

_m = json.load(open('work/state_map.json'))
fp, smap = _m['fingerprint'], _m['elements']

# widths of each RTL storage word
width = collections.defaultdict(int)
for e in smap:
    width[e['rtl_name']] = max(width[e['rtl_name']], e['rtl_bit'] + 1)

def bitval():
    if mode == 'zeros':  return 0
    if mode == 'ones':   return 1
    return rnd.getrandbits(1)

# vector over every bit of every RTL storage word (superset of netlist flops)
vec = {}
for name, w in sorted(width.items()):
    if name in constraints:
        cv = constraints[name]
        for b in range(w):
            vec[(name, b)] = (cv >> b) & 1
    else:
        for b in range(w):
            vec[(name, b)] = bitval()

# ---- RTL deposits : whole-word literals -------------------------------
with open('work/deposit_rtl.vh', 'w') as f:
    f.write('// auto-generated power-up state vector (mode=%s seed=%d)\n' % (mode, seed))
    for name, w in sorted(width.items()):
        val = 0
        for b in range(w):
            val |= vec[(name, b)] << b
        f.write("  dut.%s = %d'h%0*x;\n" % (name, w, (w + 3) // 4, val))

# ---- GLS deposits : per-flop Q ---------------------------------------
with open('work/deposit_gls.vh', 'w') as f:
    f.write('// auto-generated power-up state vector (mode=%s seed=%d)\n' % (mode, seed))
    for e in smap:
        v = vec[(e['rtl_name'], e['rtl_bit'])]
        f.write("  dut.%s.Q = 1'b%d;\n" % (e['inst'], v))

nb = sum(width.values())
print('vector mode=%s seed=%d : %d RTL bits, %d netlist flops%s'
      % (mode, seed, nb, len(smap),
         (' | constrained: ' + ' '.join('%s=%d' % kv for kv in constraints.items()))
         if constraints else ''))
print('  -> work/deposit_rtl.vh, work/deposit_gls.vh')
