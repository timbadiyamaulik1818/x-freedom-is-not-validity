#!/usr/bin/env python3
"""
Repeated, equal-workload timing of the method's cost components.

Single wall-clock samples of sub-second simulations are dominated by process
start-up and scheduler noise, and an uninitialised gate-level run never halts,
so it cannot be timed against an initialised one without capping both at the
same cycle count.  This benchmark therefore:

  * caps every run at the same cycle count (+maxcyc),
  * writes VCD to one scratch file for every configuration,
  * interleaves configurations round-robin to spread drift evenly,
  * reports median and inter-quartile range over N repetitions.

Cost components measured:
  deposit      GLS with vs without the co-initialisation deposit (1 cycle)
  lockstep     co-initialised GLS with vs without the per-cycle state dump
  compare      offline four-state comparison of the dumped state
  slowdown     gate-level vs RTL simulation, same workload, no state dump
  checkpoint   full co-initialised GLS vs GLS started at cycle 30

Requires RUN_ALL steps 1-4 and tools/checkpoint.sh to have been run.
"""
import subprocess, time, statistics, json, os, sys

N = int(os.environ.get('BENCH_N', '21'))
os.makedirs('work', exist_ok=True)

def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write('COMMAND FAILED: %s\n%s\n' % (c, r.stderr[-600:])); sys.exit(1)

def q(xs):
    xs = sorted(xs); n = len(xs)
    return statistics.median(xs), xs[n // 4], xs[(3 * n) // 4]

sh('python3 tools/gen_vector.py zeros')
NL = 'syn/cpu_netlist.v lib/cells.v tb/tb_gls.v'
builds = {
  'rtl':        'iverilog -g2005 -DINIT_DEPOSIT -DNO_PROBE -o work/bn_rtl rtl/cpu.v tb/tb_rtl.v',
  'gls_plain':  'iverilog -g2005 -DNO_PROBE -o work/bn_gp ' + NL,
  'gls_dep':    'iverilog -g2005 -DINIT_DEPOSIT -DNO_PROBE -o work/bn_gd ' + NL,
  'gls_lock':   'iverilog -g2005 -DINIT_DEPOSIT -o work/bn_gl ' + NL,
}
for c in builds.values(): sh(c)

A = '+trace=work/bn.trace +vcd=work/bn_null.vcd +snap=work/bn.snap'
cfg = {
  'rtl_107':        './work/bn_rtl %s +maxcyc=107' % A,
  'gls_dep_107':    './work/bn_gd  %s +maxcyc=107' % A,
  'gls_lock_107':   './work/bn_gl  %s +maxcyc=107' % A,
  'gls_plain_1':    './work/bn_gp  %s +maxcyc=1'   % A,
  'gls_dep_1':      './work/bn_gd  %s +maxcyc=1'   % A,
}
have_ckpt = os.path.exists('work/ck_gls')
if have_ckpt:
  cfg['gls_full_107'] = './work/bn_gl %s +maxcyc=107' % A
  cfg['gls_ckpt_31_107'] = './work/ck_gls +trace=work/bn_ck.trace +vcd=work/bn_null.vcd +maxcyc=107'

t = {k: [] for k in cfg}
for k in cfg: sh(cfg[k])                      # warm-up, discarded
for _ in range(N):
    for k, c in cfg.items():
        s = time.perf_counter(); sh(c); t[k].append(time.perf_counter() - s)

# offline comparison cost
sh('./work/bn_gl +trace=work/bn_cmp_g.trace +vcd=work/bn_null.vcd +maxcyc=107')
sh('./work/bn_rtl +trace=work/bn_dummy.trace +vcd=work/bn_null.vcd +maxcyc=107')
sh('iverilog -g2005 -DINIT_DEPOSIT -o work/bn_rtl_p rtl/cpu.v tb/tb_rtl.v')
sh('./work/bn_rtl_p +trace=work/bn_cmp_r.trace +vcd=work/bn_null.vcd +snap=work/bn.snap +maxcyc=107')
cmp_t = []
for _ in range(max(5, N // 2)):
    s = time.perf_counter()
    sh('python3 tools/state_diverge.py work/bn_cmp_r.trace.state work/bn_cmp_g.trace.state')
    cmp_t.append(time.perf_counter() - s)
map_t = []
for _ in range(max(5, N // 2)):
    s = time.perf_counter(); sh('python3 tools/build_map.py'); map_t.append(time.perf_counter() - s)

res = {k: dict(zip(('median', 'p25', 'p75'), q(v))) for k, v in t.items()}
res['compare'] = dict(zip(('median', 'p25', 'p75'), q(cmp_t)))
res['build_map'] = dict(zip(('median', 'p25', 'p75'), q(map_t)))
json.dump({'N': N, 'results': res}, open('results/bench_repeat.json', 'w'), indent=1)

ms = lambda k: res[k]['median'] * 1e3
iqr = lambda k: '%.1f-%.1f' % (res[k]['p25'] * 1e3, res[k]['p75'] * 1e3)
out = []
P = out.append
P('REPEATED EQUAL-WORKLOAD TIMING   (N=%d per configuration, median [IQR], ms)' % N)
P('')
for k, lab in [('rtl_107','RTL, 107 cycles, no dump'),
               ('gls_dep_107','GLS co-init, 107 cycles, no dump'),
               ('gls_lock_107','GLS co-init + per-cycle state dump, 107 cyc'),
               ('gls_plain_1','GLS, no deposit, 1 cycle'),
               ('gls_dep_1','GLS, with deposit, 1 cycle')] + \
              ([('gls_full_107','GLS co-init, cycles 1-107'),
                ('gls_ckpt_31_107','GLS from checkpoint, cycles 31-107')] if have_ckpt else []) + \
              [('compare','offline four-state compare (680 flops)'),
               ('build_map','build correspondence map')]:
    P('  %-46s %8.1f   [%s]' % (lab, ms(k), iqr(k)))
P('')
P('derived (medians):')
P('  deposit cost              %+.1f ms  (%+.1f%% of a 1-cycle GLS run)'
  % (ms('gls_dep_1') - ms('gls_plain_1'), 100 * (ms('gls_dep_1') / ms('gls_plain_1') - 1)))
P('  per-cycle state dump      %+.1f ms  (%+.1f%% over co-init GLS, 107 cycles)'
  % (ms('gls_lock_107') - ms('gls_dep_107'), 100 * (ms('gls_lock_107') / ms('gls_dep_107') - 1)))
P('  GLS / RTL slowdown        %.2fx' % (ms('gls_dep_107') / ms('rtl_107')))
if have_ckpt:
    P('  checkpoint run            %.1f%% of full run' % (100 * ms('gls_ckpt_31_107') / ms('gls_full_107')))
P('')
P('note: every run is a separate process of well under one second, so fixed')
P('process start-up and elaboration cost is included in every figure and')
P('dominates at this design size; percentages understate what per-cycle')
P('costs would be on a long workload and should not be extrapolated.')
txt = '\n'.join(out); print(txt); open('results/bench_repeat.txt', 'w').write(txt + '\n')
