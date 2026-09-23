#!/bin/bash
# Checkpoint transplant: capture RTL state at cycle 30, start gate-level
# simulation from it, and verify cycles 31..107 against the RTL run.
# Requires RUN_ALL steps 1-3 (netlist, state map, probes).
set -e
set -o pipefail
cd "$(dirname "$0")/.."
mkdir -p work results
python3 tools/gen_vector.py zeros >/dev/null
iverilog -g2005 -DINIT_DEPOSIT -o work/ck_rtl rtl/cpu.v tb/tb_rtl.v
./work/ck_rtl +trace=work/ck_rtl.trace +vcd=work/ck_rtl.vcd \
              +snap=work/ck30.snap +snapcyc=30 >/dev/null
python3 tools/snap_to_deposit.py work/ck30.snap
iverilog -g2005 -DINIT_CKPT -o work/ck_gls syn/cpu_netlist.v lib/cells.v tb/tb_gls.v
./work/ck_gls +trace=work/ck_gls.trace +vcd=work/ck_gls.vcd >/dev/null
{
python3 - <<'PY'
g = {int(l.split()[0]): l.split()[1:] for l in open('work/ck_rtl.trace')}
d = {int(l.split()[0]): l.split()[1:] for l in open('work/ck_gls.trace')}
c = sorted(set(g) & set(d)); bad = [k for k in c if g[k] != d[k]]
print('CHECKPOINT TRANSPLANT (RTL snapshot at cycle 30)')
print('  gate-level run starts at cycle : %d' % min(d))
print('  overlapping cycles             : %d  (%d..%d)' % (len(c), min(c), max(c)))
print('  architectural mismatches       : %d' % len(bad))
PY
python3 tools/state_diverge.py work/ck_rtl.trace.state work/ck_gls.trace.state "checkpoint transplant" \
  | sed -n '4,6p'
} | tee results/checkpoint.txt
