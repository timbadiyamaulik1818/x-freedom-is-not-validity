#!/bin/bash
# =========================================================================
#  Reproduce every result reported in the article, end to end.
#
#  Requirements (free, no licence):
#      brew install icarus-verilog yosys        # macOS
#      sudo apt install iverilog yosys          # Debian / Ubuntu
#  plus python3 (3.8+).
#
#  Usage:   ./RUN_ALL.sh            full run, a few minutes
#           ./RUN_ALL.sh quick      headline result only, ~5 seconds
#           BENCH_N=41 ./RUN_ALL.sh more timing repetitions
# =========================================================================
set -e
set -o pipefail
cd "$(dirname "$0")"
mkdir -p work results

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 not found. See header."; exit 1; }; }
need iverilog; need yosys; need python3

hdr() { echo; echo "=============================================================="; echo " $1"; echo "=============================================================="; }

if [ "$1" = "quick" ]; then
  hdr "HEADLINE RESULT - three initialisation regimes, one simulation"
  iverilog -g2012 -o work/demo edaplayground/design.sv edaplayground/testbench.sv
  ./work/demo
  exit 0
fi

hdr "1/9  Assemble the benchmark program"
python3 tools/gen_prog.py

hdr "2/9  Synthesise RTL to a gate-level netlist"
yosys -q syn/synth.ys
yosys -q syn/preopt.ys

hdr "3/9  Build the state-element correspondence map"
python3 tools/build_map.py
python3 tools/gen_probes.py

hdr "4/9  All initialisation arms: architectural and state-level comparison"
./tools/final_results.sh
sed -n '/### 2\./,/### 5\./p' results/FINAL_RESULTS.txt

hdr "5/9  Switching activity and power"
sed -n '/### 5\./,$p' results/FINAL_RESULTS.txt

hdr "6/9  Seed sweep and power-up-state sensitivity"
python3 tools/sweep.py       | tee results/sweep_summary.txt
python3 tools/sweep_power.py | tee -a results/sweep_summary.txt

hdr "7/9  Checkpoint transplant"
./tools/checkpoint.sh

hdr "8/9  Two-state vs four-state comparison"
{ python3 tools/fold_pitfall.py work/f_rtl.trace.state work/f_gn.trace.state "no initialisation"
  echo
  python3 tools/fold_pitfall.py work/f_rtl.trace.state work/f_gr.trace.state "independent randomisation"
} | tee results/fold_pitfall.txt

hdr "9/9  Repeated equal-workload timing"
python3 tools/bench_repeat.py

hdr "SELF-CONTAINED TESTCASE (the one run on VCS and Questa)"
iverilog -g2012 -o work/demo edaplayground/design.sv edaplayground/testbench.sv
./work/demo | tee results/icarus_run.log

hdr "DONE - all outputs in results/"
ls -1 results/
