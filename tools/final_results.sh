#!/bin/bash
cd "$(dirname "$0")/.."
exec > results/FINAL_RESULTS.txt 2>&1
echo "================================================================="
echo " EXPERIMENTAL RESULTS - cycle-accurate GLS for pre-silicon power"
echo " design: tinycpu  3-stage 32-bit pipelined CPU"
echo "================================================================="
echo
echo "### 1. DESIGN / SYNTHESIS CHARACTERISATION"
yosys syn/synth.ys 2>/dev/null | sed -n '/=== tinycpu ===/,/Chip area/p'
echo
python3 tools/build_map.py
echo
echo "### 2. EQUIVALENCE : ARM B  (gate-level, no initialisation)"
python3 tools/gen_prog.py >/dev/null
iverilog -g2005 -o work/f_rtl rtl/cpu.v tb/tb_rtl.v
iverilog -g2005 -o work/f_gn syn/cpu_netlist.v lib/cells.v tb/tb_gls.v
./work/f_rtl +trace=work/f_rtl.trace +vcd=work/f_rtl.vcd >/dev/null
./work/f_gn  +trace=work/f_gn.trace  +vcd=work/f_gn.vcd  >/dev/null
python3 tools/diverge.py work/f_rtl.trace work/f_gn.trace "ARM B: no init"
echo
python3 tools/state_diverge.py work/f_rtl.trace.state work/f_gn.trace.state "ARM B: no init"
echo
echo "### 3. EQUIVALENCE : ARM C  (simulator-side random init, RTL untouched)"
python3 tools/gen_initrandom.py 7 >/dev/null
iverilog -g2005 -DINIT_RANDOM -o work/f_gr syn/cpu_netlist.v lib/cells.v tb/tb_gls.v
./work/f_gr +trace=work/f_gr.trace +vcd=work/f_gr.vcd >/dev/null
python3 tools/diverge.py work/f_rtl.trace work/f_gr.trace "ARM C: +initreg random seed7"
echo
echo "### 4. EQUIVALENCE : ARM E  (co-initialisation, this method)"
python3 tools/gen_vector.py zeros >/dev/null
iverilog -g2005 -DINIT_DEPOSIT -o work/f_re rtl/cpu.v tb/tb_rtl.v
iverilog -g2005 -DINIT_DEPOSIT -o work/f_ge syn/cpu_netlist.v lib/cells.v tb/tb_gls.v
./work/f_re +trace=work/f_re.trace +vcd=work/f_re.vcd >/dev/null
./work/f_ge +trace=work/f_ge.trace +vcd=work/f_ge.vcd >/dev/null
python3 tools/diverge.py work/f_re.trace work/f_ge.trace "ARM E: co-init"
echo
python3 tools/state_diverge.py work/f_re.trace.state work/f_ge.trace.state "ARM E: co-init"
echo
echo "### 5. SWITCHING ACTIVITY AND POWER  (common 107-cycle window)"
python3 tools/power.py work/f_ge.vcd syn/cpu_netlist.json "REF co-init (cycle-accurate)" 10 results/p_ref.json 107
python3 tools/power.py work/f_gn.vcd syn/cpu_netlist.json "ARM B no init (X-corrupt)"    10 results/p_b.json   107
python3 tools/power.py work/f_gr.vcd syn/cpu_netlist.json "ARM C simulator random init"  10 results/p_c.json   107
echo
python3 - <<'PY'
import json
r=json.load(open('results/p_ref.json')); b=json.load(open('results/p_b.json')); c=json.load(open('results/p_c.json'))
print('%-30s %10s %12s %12s %12s'%('arm','toggles','err vs ref','Psig(uW)','err vs ref'))
for n,d in (('REF co-init',r),('ARM B no init',b),('ARM C sim-random',c)):
    et=100.0*(d['clean_toggles']-r['clean_toggles'])/r['clean_toggles']
    ep=100.0*(d['signal_uW']-r['signal_uW'])/r['signal_uW']
    print('%-30s %10d %11.1f%% %12.2f %11.1f%%'%(n,d['clean_toggles'],et,d['signal_uW'],ep))
print()
print('%-30s %12s %10s %14s'%('arm','peak(uW)','peak cyc','X-transitions'))
for n,d in (('REF co-init',r),('ARM B no init',b),('ARM C sim-random',c)):
    print('%-30s %12.1f %10d %14d (%.1f%%)'%(n,d['peak_uW'],d['peak_cycle'],d['xz_transitions'],100*d['xz_fraction']))
PY
echo
