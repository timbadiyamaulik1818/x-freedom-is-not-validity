// ===========================================================================
//  tb_lockstep.sv
//
//  Runs the RTL model and the gate-level netlist side by side from ONE shared
//  power-up state vector, compares their full mapped state every cycle, and
//  emits an equivalence certificate covering the cycles over which the two
//  models were bit-identical.  Switching activity is only trustworthy for
//  cycles inside that window.
//
//  Each cycle the full mapped state is compared with one four-state case
//  inequality (which distinguishes x from 0); a bitwise scan to localise the
//  divergence runs only when that comparison fails.
//
//  Vendor-specific calls are guarded so the harness can be smoke-tested on an
//  open-source simulator before it is run under licence.
// ===========================================================================
`timescale 1ns/1ps

module tb_lockstep;

  // ---- knobs -------------------------------------------------------------
  int unsigned MAXCYC   = 100000;
  int unsigned SETTLE   = 1;        // ns after the clock edge to sample
  string       CERT     = "work/equivalence.cert";
  bit          STOP_ON_DIV = 1;    // activity past the divergence is invalid anyway
  real         PERIOD   = 10.0;

  logic clk = 1'b0, rst_n = 1'b0;
  always #(PERIOD/2.0) clk = ~clk;

  // =========================================================================
  //  DUT PAIR.  Replace this block for your design: instantiate the RTL model
  //  as `r` and the gate netlist as `g`, driven by identical stimulus.  Keep
  //  the instance names -- the generated deposit and probe files use them.
  // =========================================================================
`ifdef DEMO_CORE
  wire [3:0] r_pc, g_pc;  wire r_h, g_h, r_v, g_v;  wire [7:0] r_val, g_val;
  core_rtl  r (.clk(clk), .rst_n(rst_n), .pc_o(r_pc), .halted_o(r_h),
               .rv_o(r_v), .rval_o(r_val));
  core_gate g (.clk(clk), .rst_n(rst_n), .pc_o(g_pc), .halted_o(g_h),
               .rv_o(g_v), .rval_o(g_val));
  wire arch_equal = ({r_pc,r_h,r_v,r_val} === {g_pc,g_h,g_v,g_val});
  wire both_done  = (r_h === 1'b1) && (g_h === 1'b1);
`else
  // <your RTL instance>   r ( ... );
  // <your gate instance>  g ( ... );
  wire arch_equal = 1'b1;
  wire both_done  = 1'b0;
`endif

  // ---- generated: rtl_state, gate_state, NST, fold(), st_name() ----------
  `include "work/probe.vh"

  // ---- SDF annotation for the gate model ---------------------------------
`ifdef SDF_FILE
  initial $sdf_annotate(`SDF_FILE, g, , "work/sdf.log", `SDF_MTM);
`endif

  // ---- activity dumping ---------------------------------------------------
  initial begin
`ifdef DUMP_FSDB                       // Verdi / PrimePower / PowerArtist
    $fsdbDumpfile("work/gate.fsdb");
    $fsdbDumpvars(0, g, "+all");
`elsif DUMP_SAIF                       // direct SAIF for the power engine
    $set_gate_level_monitoring("on");
    $set_toggle_region(g);
`else
    $dumpfile("work/gate.vcd");
    $dumpvars(0, g);
`endif
  end

  // ---- co-initialisation --------------------------------------------------
  // The deposit must not be undone.  An x->0 transition on an asynchronous
  // reset IS a negedge and will fire the reset path over the deposited state,
  // so the vector is applied after reset has flushed and between clock edges,
  // and reset is then released without a further asserting edge.
  task automatic co_initialise();
    rst_n = 1'b0;
    repeat (4) @(posedge clk);
    @(negedge clk);
    `include "work/deposit_rtl.vh"
    `include "work/deposit_gate.vh"
    rst_n = 1'b1;
  endtask

  // ---- lockstep -----------------------------------------------------------
  int unsigned cyc, cert_from, cert_to;
  int          first_c = -1, first_i = -1;
  bit          diverged = 0;
  int unsigned x_origin = 0, val_mism = 0;
  int fh;

  task automatic localise(int unsigned c);
    for (int i = 0; i < NST; i++) begin
      if (gate_state[i] !== rtl_state[i]) begin
        if (first_c < 0) begin first_c = c; first_i = i; end
        if (gate_state[i] === 1'bx && rtl_state[i] !== 1'bx) x_origin++;
        else                                                val_mism++;
      end
    end
  endtask

  initial begin
    co_initialise();
    cyc = 0; cert_from = 1;

    forever begin
      @(posedge clk); #SETTLE;
      cyc++;

      // 4-state compare: distinguishes x from 0, unlike a 2-state hash
      if (rtl_state !== gate_state) begin        // escalate only on mismatch
        localise(cyc);
        if (!diverged) begin
          diverged = 1;
          cert_to  = cyc - 1;
          $display("");
          $display("*** DIVERGENCE at cycle %0d", cyc);
          $display("    state point : %s", st_name(first_i));
          $display("    RTL = %b   GATE = %b", rtl_state[first_i], gate_state[first_i]);
          $display("    class       : %s",
                   (gate_state[first_i] === 1'bx) ? "X-ORIGIN" : "VALUE MISMATCH");
`ifdef DEMO_CORE
          $display("    RTL pc=%h halted=%b   GATE pc=%h halted=%b",
                   r_pc, r_h, g_pc, g_h);
`endif
          $display("    -> activity beyond cycle %0d is NOT valid for power", cert_to);
        end
      end

      if ((diverged && STOP_ON_DIV) || both_done || cyc >= MAXCYC) begin
        if (!diverged) cert_to = cyc;
        break;
      end
    end

    // ---- equivalence certificate ------------------------------------------
    fh = $fopen(CERT, "w");
    $fwrite(fh, "state_points %0d\n", NST);
    $fwrite(fh, "cycles_run   %0d\n", cyc);
    $fwrite(fh, "equivalent   %0s\n", diverged ? "NO" : "YES");
    if (cert_to < cert_from) $fwrite(fh, "window       none\n");
    else                     $fwrite(fh, "window       %0d..%0d\n", cert_from, cert_to);
    if (diverged) begin
      $fwrite(fh, "first_cycle  %0d\n", first_c);
      $fwrite(fh, "first_point  %0s\n", st_name(first_i));
      $fwrite(fh, "x_origin     %0d\n", x_origin);
      $fwrite(fh, "value_mism   %0d\n", val_mism);
    end
    $fclose(fh);

    $display("");
    $display("=========================================================");
    $display(" state points compared : %0d", NST);
    $display(" cycles run            : %0d", cyc);
    $display(" EQUIVALENT            : %s", diverged ? "NO" : "YES");
    if (cert_to < cert_from)
      $display(" certified window      : NONE - no activity is usable");
    else
      $display(" certified window      : %0d..%0d", cert_from, cert_to);
    $display(" certificate           : %s", CERT);
    $display("=========================================================");
    $display("");
    $finish;
  end

endmodule
