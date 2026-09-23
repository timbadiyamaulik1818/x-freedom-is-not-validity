#!/usr/bin/env python3
"""Emit simulator-style independent randomisation of the NETLIST flops only
   -- the equivalent of `+vcs+initreg+random` / Xcelium's random init.  The
   RTL model is left untouched, exactly as a simulator switch would leave it."""
import json, random, sys, hashlib
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
rnd = random.Random(seed)
_m = json.load(open('work/state_map.json'))
fp, smap = _m['fingerprint'], _m['elements']
with open('work/initrandom_gls.vh','w') as f:
    f.write('// simulator-style independent random init (seed=%d)\n' % seed)
    for e in smap:
        f.write("  dut.%s.Q = 1'b%d;\n" % (e['inst'], rnd.getrandbits(1)))
print('wrote work/initrandom_gls.vh (seed=%d, %d flops)' % (seed, len(smap)))
