#!/usr/bin/env python3
"""Sweep power-up vectors: does the arm reproduce RTL cycle-for-cycle, and
   what power does it report?  Arm C = simulator-side random init (RTL left
   X-optimistic).  Arm E = co-initialisation of both models."""
import subprocess, json, os, sys, statistics as st
os.makedirs('work', exist_ok=True)

def sh(c, must=True):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    if must and r.returncode != 0:
        sys.stderr.write("COMMAND FAILED: %s\n%s\n%s\n" % (c, r.stdout[-800:], r.stderr[-800:]))
        raise SystemExit(1)
    return r

def match(a, b):
    r = sh('python3 tools/state_diverge.py %s %s' % (a, b))
    return 'STATE MATCH' in r.stdout

def power(vcd, win):
    r = sh('python3 tools/power.py %s syn/cpu_netlist.json s 10 work/_p.json %d' % (vcd, win))
    return json.load(open('work/_p.json'))

SEEDS = list(range(1, 21))
rowsC, rowsE = [], []

# golden X-optimistic RTL (no deposit) -- used as reference by ARM C
sh('iverilog -g2005 -o work/s_rtl rtl/cpu.v tb/tb_rtl.v')
sh('./work/s_rtl +trace=work/s_rtl.trace +vcd=work/s_rtl.vcd')
ref_cycles = len(open('work/s_rtl.trace').readlines())

print('ARM C : simulator-side random init of the netlist only')
for s in SEEDS:
    sh('python3 tools/gen_initrandom.py %d' % s)
    sh('iverilog -g2005 -DINIT_RANDOM -o work/s_gc syn/cpu_netlist.v lib/cells.v tb/tb_gls.v')
    sh('./work/s_gc +trace=work/s_gc.trace +vcd=work/s_gc.vcd')
    m = match('work/s_rtl.trace.state', 'work/s_gc.trace.state')
    p = power('work/s_gc.vcd', ref_cycles)
    rowsC.append((s, m, p['clean_toggles'], p['signal_uW'], p['peak_uW'], p['peak_cycle'],
                  len(open('work/s_gc.trace').readlines())))

print('ARM E : co-initialisation of RTL and netlist from one vector')
for s in SEEDS:
    sh('python3 tools/gen_vector.py random %d' % s)
    sh('iverilog -g2005 -DINIT_DEPOSIT -o work/s_re rtl/cpu.v tb/tb_rtl.v')
    sh('iverilog -g2005 -DINIT_DEPOSIT -o work/s_ge syn/cpu_netlist.v lib/cells.v tb/tb_gls.v')
    sh('./work/s_re +trace=work/s_re.trace +vcd=work/s_re.vcd')
    sh('./work/s_ge +trace=work/s_ge.trace +vcd=work/s_ge.vcd')
    m = match('work/s_re.trace.state', 'work/s_ge.trace.state')
    n = len(open('work/s_re.trace').readlines())
    p = power('work/s_ge.vcd', n)
    rowsE.append((s, m, p['clean_toggles'], p['signal_uW'], p['peak_uW'], p['peak_cycle'], n))

def summarise(name, rows):
    ok = sum(1 for r in rows if r[1])
    print('\n%s' % name)
    print('  RTL-equivalence rate : %d/%d  (%.0f%%)' % (ok, len(rows), 100.0*ok/len(rows)))
    tg = [r[2] for r in rows]; sp = [r[3] for r in rows]; pk = [r[4] for r in rows]
    cy = [r[6] for r in rows]
    print('  toggles              : min %d  max %d  mean %.0f' % (min(tg), max(tg), st.mean(tg)))
    print('  signal power (uW)    : min %.2f max %.2f mean %.2f  spread %.1fx'
          % (min(sp), max(sp), st.mean(sp), (max(sp)/min(sp) if min(sp) else 0)))
    print('  peak power (uW)      : min %.1f max %.1f' % (min(pk), max(pk)))
    print('  run length (cycles)  : min %d max %d  distinct %s' % (min(cy), max(cy), sorted(set(cy))))

summarise('ARM C  (simulator random init)', rowsC)
summarise('ARM E  (co-initialisation)', rowsE)
json.dump({'C': rowsC, 'E': rowsE}, open('results/sweep.json','w'), indent=1)
