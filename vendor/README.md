# Co-initialised lockstep GLS — production flow

Drop-in flow for VCS / Xcelium / Questa on a real core. It makes gate-level
simulation reproduce RTL cycle-for-cycle, proves it, and only then lets
switching activity reach the power engine.

**Status: written against tool documentation and validated end-to-end on an
open-source simulator only.** The logic is exercised (see below), but the
vendor command lines and the LEC report parsing have not been run under
licence. Expect to adjust `PAT` in `map_from_lec.py` and the switch lists.

---

## Step 1 — correspondence map, from the equivalence checker

Do **not** name-match by hand. Your LEC already solved this, survives retiming
and re-encoding, and reports what it could *not* match.

    # Formality
    match
    report_matched_points -point_type DFF > work/matched.rpt

    # Conformal
    report mapped points -type DFF > work/matched.rpt

    make map

Check the unmatched count. Unmatched state points are exactly the ones a
name-based script would have silently mis-seeded. On the reference design,
17.8% of flops were renamed by synthesis.

Add `"has_reset": true` to points driven by resettable cells (trivial from the
netlist cell type). The vector deposits only non-resettable state — reset owns
the rest, and depositing over it after the reset flush destroys what reset just
established.

## Step 2 — one vector, two models

    make vector MODE=random SEED=1
    make vector MODE=random SEED=1 CONSTRAIN="--constrain u_core/rf=0"

Emits `deposit_rtl.vh`, `deposit_gate.vh`, `probe.vh` from a single assignment.
The same bit, identified by index, reaches both models. That sharing is the
mechanism — not that the state is determinate.

## Step 3 — run lockstep

    make vcs                                   # zero-delay
    make vcs SDF=../syn/core.sdf SDF_MTM=MAXIMUM   # timing-annotated
    make xrun DUMP=SAIF
    make questa

Produces `work/equivalence.cert`:

    state_points 58
    cycles_run   5
    equivalent   YES
    window       1..5

On divergence it names the first offending state point and classifies it:

    *** DIVERGENCE at cycle 2
        state point : pc[1]
        RTL = 1   GATE = x
        class       : X-ORIGIN

**X-ORIGIN** — residual unknown state, X-pessimism, or an incomplete vector.
**VALUE MISMATCH** — a real netlist/RTL discrepancy, *or* an X-optimistic RTL
construct that was masking a genuine dependence on uninitialised state.

## Step 4 — power

Feed activity to the power engine **only** for the certified window.

    # PrimePower
    read_vcd -strip_path tb_lockstep/g work/gate.fsdb
    set_power_analysis_options -waveform_interval <certified window>

    # PowerArtist / Joules: restrict the analysis window identically

An uncertified window is not a less accurate power number, it is a power number
for a workload you did not run.

---

## Switches that matter

| Tool | Switch | Why |
|---|---|---|
| VCS | `-negdelay +neg_tchk` | use SDF negative delays; without `+neg_tchk` you get false X from clamped checks |
| VCS | `+nospecify +notimingchecks` | zero-delay pass **only** — never on the timing pass, it hides the violations whose X you are accounting for |
| VCS | `-xprop=tmerge` | X-semantics on the RTL side; makes RTL less optimistic, complementary to this method, not a substitute |
| Xcelium | `-negdelay`, `-xprop` | as above |
| Questa | `-access=rw+/.` `-voptargs="+acc=npr"` | **confirmed required** -- without it vopt folds the flop instances away and the deposits cannot bind |
| all | register-init switches (`+vcs+initreg` etc.) | **leave these off.** They initialise each model independently — measured 0/20 reproduction of RTL, with zero X to warn you |

That last row is the point of the whole flow.

## Scaling

`rtl_state` / `gate_state` are packed concatenations compared with a single
4-state `!==` per cycle — one simulator operation, and it distinguishes `x`
from `0`. For very large state, partition them into chunks and compare
chunk-wise so localisation only rescans the failing chunk.

Do not reduce the state to two states before comparing (for example a hash over
`s[i] === 1'b1`). That maps `x` onto `0`: the comparison can no longer see an
unknown value, cannot classify an X-origin divergence, and misses any divergence
confined to bits whose reference value is `0`. `tools/fold_pitfall.py` measures
this on the reference design: 82.1% of divergent bits in the uninitialised run
were invisible to a two-state comparison.

## Validation performed

`tb_lockstep.sv` and both generators were exercised against a 58-flop
synthesised core on Icarus Verilog 13.0:

| Arm | Result |
|---|---|
| both uninitialised | DIVERGENCE cycle 2, `pc[1]`, X-ORIGIN, window `1..1` |
| gate randomised, RTL untouched | DIVERGENCE cycle 1, `acc_w[0]`, VALUE MISMATCH, window none |
| co-initialised | EQUIVALENT, all 58 points, window `1..5` |

The self-contained formulation in `../edaplayground/` was additionally run under
**Synopsys VCS X-2025.06-SP1** and **Siemens QuestaSim 2025.2**, both
reproducing the open-source numbers exactly across all 23 result lines
(1449/1449 X-origin at cycle 2 `pc[1]`; 500 divergent with zero X at cycle 1
`acc_w[0]`; RTL halts at 12 vs gate at 5; all co-initialised arms bit-identical).
Three independently implemented simulators agreeing to the count means the
effect follows from LRM four-valued semantics, not from a simulation algorithm.
Neither commercial run was given a register-init switch, and both reported the
full X complement in the baseline arm -- so the comparison was not rigged by a
silently pre-initialised baseline.

Note VCS lists `BUFX1` as a second top-level module: it is a library cell this
netlist happens not to use, elaborated unconnected. Harmless.

    iverilog -g2012 -DDEMO_CORE -o work/vlock ../edaplayground/design.sv tb/tb_lockstep.sv
