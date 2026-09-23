# ===========================================================================
#  Co-initialised lockstep GLS -- vendor flow
#
#  make map      build the state correspondence from the LEC matched points
#  make vector   generate one power-up vector -> both deposit files
#  make vcs      build+run under Synopsys VCS
#  make xrun     build+run under Cadence Xcelium
#  make questa   build+run under Siemens Questa
#  make sweep    sweep a constrained family of power-up vectors
#
#  Activity is only valid for the window named in work/equivalence.cert.
# ===========================================================================

RTL       ?= ../rtl/core_small.v
NETLIST   ?= ../syn/core_gate.v
CELLS     ?= ../lib/cells.v
TB        ?= tb/tb_lockstep.sv
TOP       ?= tb_lockstep
MAP       ?= work/map.json
LECRPT    ?= work/matched.rpt
MODE      ?= random
SEED      ?= 1
CONSTRAIN ?=
SDF       ?=
SDF_MTM   ?= "MAXIMUM"
DUMP      ?= FSDB          # FSDB | SAIF | VCD

DEFS = +define+DUMP_$(DUMP)
ifneq ($(SDF),)
DEFS += +define+SDF_FILE=\"$(SDF)\" +define+SDF_MTM=$(SDF_MTM)
endif

.PHONY: map vector vcs xrun questa sweep clean

map:
	python3 tools/map_from_lec.py $(LECRPT) $(MAP) --rtl-inst r --gate-inst g

vector:
	python3 tools/gen_deposit.py $(MAP) $(MODE) $(SEED) $(CONSTRAIN)

# --------------------------------------------------------------- Synopsys
#  -negdelay        : use negative delays from SDF rather than clamping to 0
#  +neg_tchk        : enable negative timing checks (else you get false X)
#  +nospecify       : drop specify blocks -- ONLY for the zero-delay pass
#  -xprop=tmerge    : X-propagation semantics for the RTL side
#  Do NOT use +notimingchecks on the timing pass; it hides the violations
#  whose X you are trying to account for.
vcs: vector
	vcs -full64 -sverilog -debug_access+all \
	    -timescale=1ns/1ps $(DEFS) \
	    +vcs+lic+wait -notice \
	    $(if $(SDF),-negdelay +neg_tchk,+nospecify +notimingchecks) \
	    $(RTL) $(NETLIST) $(CELLS) $(TB) -top $(TOP) -o work/simv \
	    -l work/vcs.compile.log
	./work/simv -l work/vcs.run.log
	@cat work/equivalence.cert

# ---------------------------------------------------------------- Cadence
xrun: vector
	xrun -64bit -sv -access +rwc \
	     -timescale 1ns/1ps $(DEFS) \
	     $(if $(SDF),-negdelay,-notimingchecks -nospecify) \
	     $(RTL) $(NETLIST) $(CELLS) $(TB) -top $(TOP) \
	     -l work/xrun.log
	@cat work/equivalence.cert

# ---------------------------------------------------------------- Siemens
questa: vector
	vlib work/qlib && vmap work work/qlib
	vlog -sv -timescale 1ns/1ps $(DEFS) $(RTL) $(NETLIST) $(CELLS) $(TB) \
	     -l work/vlog.log
	vopt +acc $(TOP) -o ${TOP}_opt -l work/vopt.log
	vsim -c ${TOP}_opt -do "run -all; quit" -l work/vsim.log
	@cat work/equivalence.cert

# Sweep a constrained family of legal power-up vectors.  Every member must
# certify; the spread in activity across members is the power-up-state
# sensitivity of the design.
sweep:
	@for s in 1 2 3 4 5 6 7 8 9 10; do \
	  echo "=== seed $$s ==="; \
	  $(MAKE) -s vcs SEED=$$s CONSTRAIN="$(CONSTRAIN)" || exit 1; \
	done

clean:
	rm -rf work/simv* work/csrc work/*.log work/qlib work/*.vcd work/*.fsdb
