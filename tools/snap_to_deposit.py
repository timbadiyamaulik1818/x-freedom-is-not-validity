#!/usr/bin/env python3
"""
Checkpoint transplant: convert an RTL state snapshot taken at cycle N into a
gate-level deposit file, so gate-level simulation can be STARTED at cycle N
instead of replaying the whole boot sequence.
"""
import json, sys, re
snap = sys.argv[1] if len(sys.argv) > 1 else 'work/rtl.snap'
_m = json.load(open('work/state_map.json'))
smap = _m['elements']

vals, cyc = {}, None
for line in open(snap):
    if line.startswith('#'):
        m = re.search(r'cycle (\d+)', line)
        if m: cyc = int(m.group(1))
        continue
    t = line.split()
    if len(t) == 2: vals[t[0]] = t[1]

def bit_of(name, b):
    v = vals.get(name)          # canonical binary, MSB first
    if v is None: return 'x'
    idx = len(v) - 1 - b        # bit b counted from the LSB
    return v[idx] if 0 <= idx < len(v) else 'x'

nx = 0
with open('work/deposit_ckpt.vh','w') as f:
    f.write('// checkpoint transplant from %s (RTL cycle %s)\n' % (snap, cyc))
    for e in smap:
        b = bit_of(e['rtl_name'], e['rtl_bit'])
        if b not in '01': nx += 1; b = '0'
        f.write("  dut.%s.Q = 1'b%s;\n" % (e['inst'], b))
with open('work/ckpt_cycle.vh','w') as f:
    f.write('  cyc = %d;\n' % cyc)
print('checkpoint at RTL cycle %s -> %d flops (%d were X, forced to 0)' % (cyc, len(smap), nx))
