#!/usr/bin/env python3
"""
Cycle-accurate divergence tracker.

Compares a gate-level architectural trace against the golden RTL trace and
reports the FIRST divergent cycle, classifies the divergence, and attributes
it to the instruction retiring in that cycle.

usage: diverge.py <golden.trace> <dut.trace> [label]
"""
import sys, collections

OPN = {0:'NOP',1:'ADD',2:'SUB',3:'AND',4:'OR',5:'XOR',6:'SHL',7:'SHR',
       8:'LI',9:'BNZ',10:'LD',11:'ST',15:'HALT'}
FIELDS = ['pc','halted','retire_v','retire_pc','retire_op','retire_rd','retire_val']

def load(p):
    rows = []
    for line in open(p):
        t = line.split()
        if len(t) == 8:
            rows.append({'cyc': int(t[0]), 'pc': t[1], 'halted': t[2],
                         'retire_v': t[3], 'retire_pc': t[4], 'retire_op': t[5],
                         'retire_rd': t[6], 'retire_val': t[7]})
    return rows

def hasx(v):
    return 'x' in v.lower() or 'z' in v.lower()

g = load(sys.argv[1]); d = load(sys.argv[2])
label = sys.argv[3] if len(sys.argv) > 3 else sys.argv[2]

n = min(len(g), len(d))
first = None
div_cycles = 0
x_cycles = 0
field_hits = collections.Counter()
x_field = collections.Counter()

for i in range(n):
    bad = [f for f in FIELDS if g[i][f] != d[i][f]]
    xf  = [f for f in FIELDS if hasx(d[i][f]) and not hasx(g[i][f])]
    if xf: x_cycles += 1
    for f in xf: x_field[f] += 1
    if bad:
        div_cycles += 1
        for f in bad: field_hits[f] += 1
        if first is None:
            first = (i, bad, xf)

print('=' * 66)
print('DIVERGENCE REPORT : %s' % label)
print('=' * 66)
print('golden cycles %d   dut cycles %d   compared %d' % (len(g), len(d), n))
if len(g) != len(d):
    print('!! LENGTH MISMATCH - execution length differs by %d cycles' % abs(len(g)-len(d)))

if first is None:
    print('RESULT            : MATCH  - bit-identical for all %d cycles' % n)
    print('X-corrupted cycles: 0')
    sys.exit(0)

i, bad, xf = first
print('RESULT            : DIVERGENT')
print('divergent cycles  : %d / %d  (%.1f%%)' % (div_cycles, n, 100.0*div_cycles/n))
print('X-corrupted cycles: %d / %d  (%.1f%%)' % (x_cycles, n, 100.0*x_cycles/n))
print()
print('--- FIRST DIVERGENCE ------------------------------------------')
print('cycle             : %d' % g[i]['cyc'])
print('fields            : %s' % ', '.join(bad))
print('X-corrupted here  : %s' % (', '.join(xf) if xf else 'none (value mismatch, not X)'))
try:
    op = int(g[i]['retire_op'], 16)
except ValueError:
    op = -1
print('retiring instr    : pc=0x%s  op=%s  rd=r%s'
      % (g[i]['retire_pc'], OPN.get(op, '?'), g[i]['retire_rd']))
print('  golden          : %s' % ' '.join('%s=%s' % (f, g[i][f]) for f in bad))
print('  dut             : %s' % ' '.join('%s=%s' % (f, d[i][f]) for f in bad))
print()
print('--- FIELD BREAKDOWN -------------------------------------------')
for f in FIELDS:
    if field_hits[f]:
        print('  %-11s diverged %3d cycles   (X-corrupt in %3d)'
              % (f, field_hits[f], x_field[f]))
print()
print('--- CONTEXT (cycles %d..%d) -----------------------------------' % (max(0,i-2), min(n-1,i+4)))
print('  %-5s %-9s %-9s %-4s %-9s | %-9s %-4s %-9s' %
      ('cyc','G:pc','G:rpc','G:op','G:rval','D:pc','D:op','D:rval'))
for k in range(max(0,i-2), min(n, i+5)):
    mark = '<<' if k == i else '  '
    print('%s%-5s %-9s %-9s %-4s %-9s | %-9s %-4s %-9s' %
          (mark, g[k]['cyc'], g[k]['pc'], g[k]['retire_pc'], g[k]['retire_op'],
           g[k]['retire_val'], d[k]['pc'], d[k]['retire_op'], d[k]['retire_val']))
