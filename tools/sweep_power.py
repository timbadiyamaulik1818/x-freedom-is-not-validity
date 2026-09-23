#!/usr/bin/env python3
"""Power-up-state sensitivity sweep on the FULL workload.

All vectors satisfy the architectural constraint the boot guard depends on
(rf[5]=0), so every run executes the same 107-cycle program.  Any remaining
variation in activity and power is genuinely caused by the power-up state of
the other 651 flops -- a quantity that is simply unmeasurable when the
gate-level model is X-corrupted.
"""
import subprocess, json, os, sys, statistics as st
os.makedirs('work', exist_ok=True)

def sh(c, must=True):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    if must and r.returncode != 0:
        sys.stderr.write("COMMAND FAILED: %s\n%s\n%s\n" % (c, r.stdout[-800:], r.stderr[-800:]))
        raise SystemExit(1)
    return r

rows = []
for s in range(1, 21):
    sh("python3 tools/gen_vector.py random %d 'rf[5]=0'" % s)
    sh('iverilog -g2005 -DINIT_DEPOSIT -o work/w_re rtl/cpu.v tb/tb_rtl.v')
    sh('iverilog -g2005 -DINIT_DEPOSIT -o work/w_ge syn/cpu_netlist.v lib/cells.v tb/tb_gls.v')
    sh('./work/w_re +trace=work/w_re.trace +vcd=work/w_re.vcd')
    sh('./work/w_ge +trace=work/w_ge.trace +vcd=work/w_ge.vcd')
    m = 'STATE MATCH' in sh('python3 tools/state_diverge.py work/w_re.trace.state work/w_ge.trace.state').stdout
    n = len(open('work/w_re.trace').readlines())
    sh('python3 tools/power.py work/w_ge.vcd syn/cpu_netlist.json s 10 work/_p.json %d' % n)
    p = json.load(open('work/_p.json'))
    rows.append((s, m, n, p['clean_toggles'], p['signal_uW'], p['total_uW'],
                 p['peak_uW'], p['peak_cycle']))

ok = sum(1 for r in rows if r[1])
tg = [r[3] for r in rows]; sp = [r[4] for r in rows]
tp = [r[5] for r in rows]; pk = [r[6] for r in rows]; pc = [r[7] for r in rows]
cy = [r[2] for r in rows]

print('POWER-UP STATE SENSITIVITY SWEEP  (20 legal vectors, full workload)')
print('  RTL/GLS equivalence  : %d/%d (%.0f%%)' % (ok, len(rows), 100.0*ok/len(rows)))
print('  workload length      : %s cycles' % sorted(set(cy)))
print('  toggles              : %d .. %d   (mean %.0f, sigma %.0f)'
      % (min(tg), max(tg), st.mean(tg), st.pstdev(tg)))
print('  signal power   (uW)  : %.2f .. %.2f  (mean %.2f, %.1f%% spread)'
      % (min(sp), max(sp), st.mean(sp), 100.0*(max(sp)-min(sp))/st.mean(sp)))
print('  total power    (uW)  : %.2f .. %.2f  (mean %.2f, %.1f%% spread)'
      % (min(tp), max(tp), st.mean(tp), 100.0*(max(tp)-min(tp))/st.mean(tp)))
print('  peak power     (uW)  : %.1f .. %.1f  (%.1f%% spread)'
      % (min(pk), max(pk), 100.0*(max(pk)-min(pk))/st.mean(pk)))
print('  peak-power cycle     : %s' % sorted(set(pc)))
json.dump(rows, open('results/sweep_power.json','w'), indent=1)
